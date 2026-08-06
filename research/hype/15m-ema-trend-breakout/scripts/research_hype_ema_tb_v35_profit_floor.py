from __future__ import annotations

import json
import time
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings


SYMBOL = "HYPE/USDT:USDT"
EXCHANGE = "binance"
TIMEFRAME = "15m"
M15_PER_YEAR = 365 * 24 * 4
ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
DEFAULT_SINCE = "2025-05-30T10:30:00Z"


@dataclass(frozen=True, slots=True)
class V35Config:
    long_target_atr_pct: float = 0.020
    short_target_atr_pct: float = 0.018
    max_allocation: float = 3.0
    ema_fast: int = 96
    ema_slow: int = 384
    adx_window: int = 28
    volume_window: int = 192
    atr_window: int = 672
    h1_adx_window: int = 21
    h1_ema_fast: int = 24
    h1_ema_slow: int = 96
    warmup_bars: int = 1600
    long_adx_min: float = 28.0
    short_adx_min: float = 36.0
    long_vol_min: float = 0.25
    short_vol_min: float = 0.50
    h1_long_adx_min: float = 18.0
    entry_delay_bars: int = 2
    take_profit_atr: float = 5.0
    hard_stop_atr: float = 7.0
    adx_exit: float = 22.0
    delayed_bars: int = 3
    disable_after_mfe_atr: float = 1.5
    max_hold_bars: int = 384
    trade_cost_rate: float = 0.00085


@dataclass(frozen=True, slots=True)
class ProfitFloorConfig:
    """tiers: ((mfe_threshold, floor_offset_atr), ...)，按 MFE 阈值从低到高。

    breakeven_mfe_atr 非 None 时，MFE 达到该值即把保护线抬到覆盖开/平成本的近保本价。
    cooldown_bars_after_floor: profit_floor 退出后禁止再入场的 15m K 数（0 = 沿用 V35 无冷却）。
    """

    enabled: bool
    tiers: tuple[tuple[float, float], ...] = ()
    breakeven_mfe_atr: float | None = None
    cooldown_bars_after_floor: int = 0
    update_timing: str = "close_next_bar"


@dataclass(slots=True)
class Position:
    direction: int
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    mfe_atr: float = 0.0
    weak_bars: int = 0
    floor_offset_atr: float = 0.0


@dataclass(frozen=True, slots=True)
class RunResult:
    name: str
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    trades: pd.DataFrame
    equity_curve: pd.Series
    period_returns: pd.Series
    open_position: dict[str, Any] | None


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    run_label = args.source
    if args.source == "data_lake":
        warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
        frame, funding, quality = load_data(warehouse)
    else:
        frame, funding, quality = load_binance_api_data(args.since, args.until)
        save_api_inputs(frame, funding)
    features = build_features(frame, V35Config())
    config = V35Config()
    variants = [
        ("v35_base", ProfitFloorConfig(enabled=False)),
        # 上一轮否决的宽口径参照：1.5 保本 + 3.0 锁 1.5 + 4.0 锁 2.5
        (
            "floor_staged_wide_ref",
            ProfitFloorConfig(enabled=True, breakeven_mfe_atr=1.5, tiers=((3.0, 1.5), (4.0, 2.5))),
        ),
        # 窄口径：只保护已接近 TP 的单
        ("floor_30_lock10", ProfitFloorConfig(enabled=True, tiers=((3.0, 1.0),))),
        ("floor_35_lock15", ProfitFloorConfig(enabled=True, tiers=((3.5, 1.5),))),
        ("floor_40_lock20", ProfitFloorConfig(enabled=True, tiers=((4.0, 2.0),))),
        ("floor_40_lock25", ProfitFloorConfig(enabled=True, tiers=((4.0, 2.5),))),
        ("floor_45_lock30", ProfitFloorConfig(enabled=True, tiers=((4.5, 3.0),))),
        # 极窄口径：只在几乎到 TP 时启动，容忍很浅回撤
        ("floor_45_lock35", ProfitFloorConfig(enabled=True, tiers=((4.5, 3.5),))),
        ("floor_475_lock40", ProfitFloorConfig(enabled=True, tiers=((4.75, 4.0),))),
        ("floor_475_lock425", ProfitFloorConfig(enabled=True, tiers=((4.75, 4.25),))),
        ("floor_49_lock44", ProfitFloorConfig(enabled=True, tiers=((4.9, 4.4),))),
        # 窄口径 + floor 退出后 16 根 15m 冷却，抑制立即重进
        (
            "floor_40_lock25_cd16",
            ProfitFloorConfig(enabled=True, tiers=((4.0, 2.5),), cooldown_bars_after_floor=16),
        ),
        (
            "floor_35_lock15_cd16",
            ProfitFloorConfig(enabled=True, tiers=((3.5, 1.5),), cooldown_bars_after_floor=16),
        ),
    ]
    runs = [run_backtest(name, frame, funding, features, config, floor_cfg) for name, floor_cfg in variants]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V35 profit-floor diagnostic",
        "symbol": SYMBOL,
        "exchange": EXCHANGE,
        "market_type": MarketType.PERP.value,
        "timeframe": TIMEFRAME,
        "source": args.source,
        "data_quality": quality,
        "assumptions": {
            "execution": "K0 close signal, K2 open entry, entry ATR from K1, TP/SL intrabar by 15m high/low, indicator/timeout next open.",
            "cost": "V35 canonical override: 0.00085 per fill, interpreted as taker fee plus 4 bps slippage.",
            "funding": "Actual Binance funding timestamps reindexed to 15m bars; missing bars use 0.",
            "profit_floor": {
                "timing": "MFE is updated on a closed 15m bar; a raised profit floor becomes active from the next bar.",
                "tiers": "Per-variant (mfe_threshold, floor_offset_atr) tiers; floor only moves in the favorable direction.",
                "floor_fill": "If next open has already crossed the floor, fill at open; otherwise fill at the floor stop price.",
                "cooldown": "Optional re-entry cooldown (15m bars) applied only after a profit_floor exit.",
            },
        },
        "config": asdict(config),
        "variant_configs": {name: asdict(cfg) for name, cfg in variants},
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "slices": run.slices,
                "open_position": run.open_position,
                "last_trades": _last_trades(run.trades, 8),
            }
            for run in runs
        ],
        "comparison": build_comparison(runs),
    }
    summary_path, trades_path, equity_path = artifact_paths(run_label)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)
    print(f"data: {quality.get('start')} ~ {quality.get('end')} rows={quality.get('rows')}")
    print(f"summary -> {summary_path}")
    for run in runs:
        m = run.metrics
        print(
            f"{run.name:>24}  ret {m['return_pct']:>10.2f}%  dd {m['max_drawdown_pct']:>7.2f}%  "
            f"sharpe {m['sharpe']:>5.2f}  trades {m['trades']:>4}  win {m['win_rate_pct']:>6.2f}%  "
            f"exits {m['exit_counts']}"
        )
    print()
    print("slice returns (window: base | variant...):")
    header = "window  " + "  ".join(f"{run.name[:20]:>20}" for run in runs)
    print(header)
    for idx, base_slice in enumerate(runs[0].slices):
        cells = "  ".join(f"{run.slices[idx]['return_pct']:>20.2f}" for run in runs)
        print(f"{base_slice['window']:>6}  {cells}")


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--source", choices=["data_lake", "binance_api"], default="data_lake")
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--until", default="")
    return parser.parse_args()


def artifact_paths(run_label: str) -> tuple[Path, Path, Path]:
    stem = f"hype_ema_tb_v35_profit_floor_variants_{run_label}_2026-07-07"
    return (
        ARTIFACT_DIR / f"{stem}.json",
        ARTIFACT_DIR / f"{stem}_trades.csv",
        ARTIFACT_DIR / f"{stem}_equity.csv",
    )


def load_data(warehouse: DuckDBWarehouse) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    normalized = warehouse.load_trusted_ohlcv(
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
    )
    if normalized.empty:
        raise RuntimeError("Missing normalized Binance HYPEUSDT 15m OHLCV data.")
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    frame = normalized.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    if "is_closed" in frame.columns:
        frame = frame.loc[frame["is_closed"].fillna(False).astype(bool)].copy()
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    funding_frame = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        columns=["ts", "funding_rate", "source"],
    )
    if funding_frame.empty:
        funding = pd.Series(0.0, index=frame.index, name="funding_rate")
        funding_quality = {"rows": 0, "non_zero_aligned_rows": 0, "null_rates": 0}
    else:
        funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True).dt.floor("15min")
        funding_frame["funding_rate"] = pd.to_numeric(funding_frame["funding_rate"], errors="coerce")
        funding_raw = funding_frame.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")["funding_rate"]
        funding = funding_raw.reindex(frame.index).fillna(0.0).rename("funding_rate")
        funding_quality = {
            "rows": int(len(funding_frame)),
            "start": funding_frame["ts"].min().isoformat(),
            "end": funding_frame["ts"].max().isoformat(),
            "null_rates": int(funding_frame["funding_rate"].isna().sum()),
            "non_zero_aligned_rows": int(funding.ne(0.0).sum()),
            "aligned_sum_rate": float(funding.sum()),
        }

    quality = build_quality_report(warehouse, normalized, frame, funding_quality)
    return frame[["open", "high", "low", "close", "volume"]].copy(), funding, quality


def load_binance_api_data(since_text: str, until_text: str) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    since = pd.Timestamp(since_text).tz_convert("UTC") if pd.Timestamp(since_text).tzinfo else pd.Timestamp(since_text, tz="UTC")
    if until_text:
        until = pd.Timestamp(until_text).tz_convert("UTC") if pd.Timestamp(until_text).tzinfo else pd.Timestamp(until_text, tz="UTC")
    else:
        until = pd.Timestamp.now("UTC").floor("15min") - pd.Timedelta(minutes=15)
    ohlcv = fetch_binance_klines(since, until)
    funding_raw = fetch_binance_funding(since, until)
    funding = funding_raw.reindex(ohlcv.index).fillna(0.0).rename("funding_rate")
    quality = build_api_quality_report(ohlcv, funding_raw, funding, since, until)
    return ohlcv[["open", "high", "low", "close", "volume"]].copy(), funding, quality


def fetch_binance_klines(since: pd.Timestamp, until: pd.Timestamp) -> pd.DataFrame:
    rows: list[list[Any]] = []
    interval_ms = 15 * 60 * 1000
    cursor = int(since.timestamp() * 1000)
    end_ms = int(until.timestamp() * 1000)
    while cursor <= end_ms:
        data = binance_get(
            "/fapi/v1/klines",
            {
                "symbol": "HYPEUSDT",
                "interval": "15m",
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1500,
            },
        )
        if not data:
            break
        if rows:
            data = [row for row in data if int(row[0]) > int(rows[-1][0])]
        if not data:
            break
        rows.extend(data)
        cursor = int(rows[-1][0]) + interval_ms
        time.sleep(0.05)
        if int(rows[-1][0]) >= end_ms:
            break
    if not rows:
        raise RuntimeError("Binance API returned no HYPEUSDT 15m klines")
    frame = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    out = pd.DataFrame(index=pd.to_datetime(frame["open_time"], unit="ms", utc=True))
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]:
        out[column] = pd.to_numeric(frame[column], errors="coerce").to_numpy()
    out["vwap"] = out["quote_volume"] / out["volume"].replace(0.0, np.nan)
    out["vwap"] = out["vwap"].fillna((out["high"] + out["low"] + out["close"]) / 3.0)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.loc[out.index <= until]


def fetch_binance_funding(since: pd.Timestamp, until: pd.Timestamp) -> pd.Series:
    rows: list[dict[str, Any]] = []
    cursor = int(since.timestamp() * 1000)
    end_ms = int(until.timestamp() * 1000)
    while cursor <= end_ms:
        data = binance_get(
            "/fapi/v1/fundingRate",
            {
                "symbol": "HYPEUSDT",
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1000,
            },
        )
        if not data:
            break
        new_rows = [row for row in data if not rows or int(row["fundingTime"]) > int(rows[-1]["fundingTime"])]
        if not new_rows:
            break
        rows.extend(new_rows)
        cursor = int(rows[-1]["fundingTime"]) + 1
        time.sleep(0.05)
        if int(rows[-1]["fundingTime"]) >= end_ms:
            break
    if not rows:
        return pd.Series(dtype="float64", name="funding_rate")
    frame = pd.DataFrame(rows)
    frame["ts"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True).dt.floor("15min")
    frame["funding_rate"] = pd.to_numeric(frame["fundingRate"], errors="coerce")
    return frame.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")["funding_rate"]


def binance_get(path: str, params: dict[str, Any]) -> Any:
    url = f"https://fapi.binance.com{path}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "strategy-lab/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def build_api_quality_report(
    frame: pd.DataFrame,
    funding_raw: pd.Series,
    funding: pd.Series,
    requested_since: pd.Timestamp,
    requested_until: pd.Timestamp,
) -> dict[str, Any]:
    expected = pd.date_range(frame.index.min(), frame.index.max(), freq="15min", tz="UTC")
    missing = expected.difference(frame.index)
    nulls = {column: int(frame[column].isna().sum()) for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]}
    invalid_ohlc = int(
        (
            frame["high"].lt(frame[["open", "close"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close"]].min(axis=1))
            | frame["high"].lt(frame["low"])
            | frame["volume"].lt(0)
        ).sum()
    )
    return {
        "source": "binance_futures_public_api_live_fetch",
        "requested_since": requested_since.isoformat(),
        "requested_until": requested_until.isoformat(),
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "duplicate_ts_before_dedup": 0,
        "missing_15m_bars": int(len(missing)),
        "first_missing_15m_bars": [ts.isoformat() for ts in missing[:10]],
        "critical_nulls": nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "is_utc_index": str(frame.index.tz) == "UTC",
        "raw_vs_normalized": {"available": False, "reason": "API fetch is the raw public source for this supplemental run"},
        "funding": {
            "rows": int(len(funding_raw)),
            "start": funding_raw.index.min().isoformat() if len(funding_raw) else None,
            "end": funding_raw.index.max().isoformat() if len(funding_raw) else None,
            "null_rates": int(funding_raw.isna().sum()) if len(funding_raw) else 0,
            "non_zero_aligned_rows": int(funding.ne(0.0).sum()),
            "aligned_sum_rate": float(funding.sum()),
        },
    }


def save_api_inputs(frame: pd.DataFrame, funding: pd.Series) -> None:
    ohlcv_path = ARTIFACT_DIR / "hype_ema_tb_v35_profit_floor_binance_api_ohlcv_2026-07-07.csv"
    funding_path = ARTIFACT_DIR / "hype_ema_tb_v35_profit_floor_binance_api_funding_2026-07-07.csv"
    # 同日多轮运行时不覆盖已被报告引用的输入证据
    if not ohlcv_path.exists():
        frame.to_csv(ohlcv_path, index_label="ts")
    if not funding_path.exists():
        funding.rename("funding_rate").to_csv(funding_path, index_label="ts")


def build_quality_report(
    warehouse: DuckDBWarehouse,
    normalized_before_dedup: pd.DataFrame,
    frame: pd.DataFrame,
    funding_quality: dict[str, Any],
) -> dict[str, Any]:
    expected = pd.date_range(frame.index.min(), frame.index.max(), freq="15min", tz="UTC")
    missing = expected.difference(frame.index)
    critical_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    nulls = {
        column: int(frame[column].isna().sum())
        for column in critical_columns
        if column in frame.columns
    }
    invalid_ohlc = int(
        (
            frame["high"].lt(frame[["open", "close"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close"]].min(axis=1))
            | frame["high"].lt(frame["low"])
            | frame["volume"].lt(0)
        ).sum()
    )
    source_counts = frame["source"].astype("string").value_counts(dropna=False).to_dict() if "source" in frame.columns else {}
    raw_compare = compare_raw_normalized(warehouse, frame)
    return {
        "normalized_rows_before_dedup": int(len(normalized_before_dedup)),
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "duplicate_ts_before_dedup": int(normalized_before_dedup["ts"].duplicated().sum()),
        "missing_15m_bars": int(len(missing)),
        "first_missing_15m_bars": [ts.isoformat() for ts in missing[:10]],
        "critical_nulls": nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "is_utc_index": str(frame.index.tz) == "UTC",
        "is_closed_false_or_null_before_filter": int((~normalized_before_dedup.get("is_closed", pd.Series(True, index=normalized_before_dedup.index)).fillna(False).astype(bool)).sum()),
        "source_counts": {str(key): int(value) for key, value in source_counts.items()},
        "raw_vs_normalized": raw_compare,
        "funding": funding_quality,
    }


def compare_raw_normalized(warehouse: DuckDBWarehouse, normalized: pd.DataFrame) -> dict[str, Any]:
    raw = warehouse.load_dataset(
        layer="raw",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
    )
    if raw.empty:
        return {"available": False, "reason": "raw OHLCV dataset not found by warehouse filters"}
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    raw = raw.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    common_columns = [column for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"] if column in raw.columns and column in normalized.columns]
    joined = raw[common_columns].join(
        normalized[common_columns],
        how="inner",
        lsuffix="_raw",
        rsuffix="_normalized",
    )
    max_abs_diff: dict[str, float] = {}
    mismatch_rows: dict[str, int] = {}
    for column in common_columns:
        raw_values = pd.to_numeric(joined[f"{column}_raw"], errors="coerce")
        normalized_values = pd.to_numeric(joined[f"{column}_normalized"], errors="coerce")
        diff = (raw_values - normalized_values).abs()
        max_abs_diff[column] = float(diff.max()) if not diff.empty else 0.0
        mismatch_rows[column] = int(diff.gt(1e-12).sum())
    return {
        "available": True,
        "raw_rows": int(len(raw)),
        "compared_rows": int(len(joined)),
        "common_columns": common_columns,
        "max_abs_diff": max_abs_diff,
        "mismatch_rows": mismatch_rows,
    }


def build_features(frame: pd.DataFrame, config: V35Config) -> pd.DataFrame:
    features = frame.copy()
    features["atr"] = true_range(features).rolling(config.atr_window, min_periods=config.atr_window).mean()
    features["ema_fast"] = features["close"].ewm(span=config.ema_fast, adjust=False, min_periods=config.ema_fast).mean()
    features["ema_slow"] = features["close"].ewm(span=config.ema_slow, adjust=False, min_periods=config.ema_slow).mean()
    features["ema_spread"] = features["ema_fast"] / features["ema_slow"] - 1.0
    adx, plus_di, minus_di = adx_di(features, config.adx_window)
    features["adx"] = adx
    features["plus_di"] = plus_di
    features["minus_di"] = minus_di
    volume_ma = features["volume"].rolling(config.volume_window, min_periods=config.volume_window).mean()
    features["volume_surge"] = features["volume"] / volume_ma - 1.0

    h1 = resample_ohlcv(features, "1h")
    h1_adx, h1_plus_di, h1_minus_di = adx_di(h1, config.h1_adx_window)
    h1_ema_fast = h1["close"].ewm(span=config.h1_ema_fast, adjust=False, min_periods=config.h1_ema_fast).mean()
    h1_ema_slow = h1["close"].ewm(span=config.h1_ema_slow, adjust=False, min_periods=config.h1_ema_slow).mean()
    h1_features = pd.DataFrame(
        {
            "h1_adx": h1_adx,
            "h1_plus_di": h1_plus_di,
            "h1_minus_di": h1_minus_di,
            "h1_ema_spread": h1_ema_fast / h1_ema_slow - 1.0,
        },
        index=h1.index,
    ).shift(1)
    h1_aligned = h1_features.reindex(features.index, method="ffill")
    features = features.join(h1_aligned)
    features["long_signal"] = (
        features["ema_spread"].gt(0.0)
        & features["adx"].ge(config.long_adx_min)
        & features["volume_surge"].ge(config.long_vol_min)
        & features["h1_adx"].gt(config.h1_long_adx_min)
        & features["h1_plus_di"].gt(features["h1_minus_di"])
    )
    features["short_signal"] = (
        features["ema_spread"].lt(0.0)
        & features["adx"].ge(config.short_adx_min)
        & features["volume_surge"].ge(config.short_vol_min)
        & features["h1_ema_spread"].lt(0.0)
    )
    conflict = features["long_signal"] & features["short_signal"]
    features.loc[conflict, ["long_signal", "short_signal"]] = False
    return features


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def adx_di(frame: pd.DataFrame, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(frame)
    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0),
        index=frame.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0),
        index=frame.index,
    )
    alpha = 1.0 / window
    atr_w = tr.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=window).mean() / atr_w
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=window).mean() / atr_w
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def resample_ohlcv(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        frame[["open", "high", "low", "close", "volume"]]
        .resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
    )


def run_backtest(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: V35Config,
    floor_cfg: ProfitFloorConfig,
) -> RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    entry_blocked_until = -1  # profit_floor 退出后的再入场冷却边界（含）
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, cost = close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_pnl = -position.direction * position.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        if position is None and not exited_this_bar and i > last_exit_bar and i > entry_blocked_until:
            signal_i = i - config.entry_delay_bars
            direction = 0
            if bool(features["long_signal"].iloc[signal_i]) and not bool(features["short_signal"].iloc[signal_i]):
                direction = 1
            elif bool(features["short_signal"].iloc[signal_i]) and not bool(features["long_signal"].iloc[signal_i]):
                direction = -1
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                target = config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
                allocation = min(config.max_allocation, target / (entry_atr / open_price))
                cost = config.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )

        if position is not None:
            intrabar = check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
            )
            if intrabar is not None:
                reason, exit_price = intrabar
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                if reason == "profit_floor" and floor_cfg.cooldown_bars_after_floor > 0:
                    entry_blocked_until = i + floor_cfg.cooldown_bars_after_floor
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (close / position.previous_price - 1.0)
                equity *= 1.0 + pnl
                position.previous_price = close
                update_position_on_close(position, high, low, config, floor_cfg)
                can_indicator_exit = position.mfe_atr < config.disable_after_mfe_atr
                if can_indicator_exit and float(features["adx"].iloc[i]) < config.adx_exit:
                    position.weak_bars += 1
                else:
                    position.weak_bars = 0
                if can_indicator_exit and position.weak_bars >= config.delayed_bars:
                    pending_exit = "indicator_exit"
                if pending_exit is None and i - position.entry_bar >= config.max_hold_bars:
                    pending_exit = "timeout"

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)
        weight_values.append(0.0 if position is None else position.direction * position.allocation)

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=name)
    returns = pd.Series(period_returns, index=index, name=f"{name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{name}_weight")
    trades_frame = pd.DataFrame(trades)
    metrics = metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    return RunResult(
        name=name,
        metrics=metrics,
        slices=slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position_summary(position, frame.index[-1]) if position is not None else None,
    )


def check_intrabar_exit(
    *,
    position: Position,
    open_price: float,
    high: float,
    low: float,
    config: V35Config,
) -> tuple[str, float] | None:
    take = position.entry_price + position.direction * config.take_profit_atr * position.entry_atr
    hard_stop = position.entry_price - position.direction * config.hard_stop_atr * position.entry_atr
    effective_stop = hard_stop
    floor_active = position.floor_offset_atr > 0.0
    if floor_active:
        floor_price = position.entry_price + position.direction * position.floor_offset_atr * position.entry_atr
        effective_stop = max(hard_stop, floor_price) if position.direction == 1 else min(hard_stop, floor_price)

    if position.direction == 1:
        if low <= effective_stop:
            if floor_active and effective_stop > hard_stop:
                return "profit_floor", min(open_price, effective_stop) if open_price <= effective_stop else effective_stop
            return "stop_loss", hard_stop
        if high >= take:
            return "take_profit", take
    else:
        if high >= effective_stop:
            if floor_active and effective_stop < hard_stop:
                return "profit_floor", max(open_price, effective_stop) if open_price >= effective_stop else effective_stop
            return "stop_loss", hard_stop
        if low <= take:
            return "take_profit", take
    return None


def update_position_on_close(
    position: Position,
    high: float,
    low: float,
    config: V35Config,
    floor_cfg: ProfitFloorConfig,
) -> None:
    if position.direction == 1:
        excursion = (high - position.entry_price) / position.entry_atr
    else:
        excursion = (position.entry_price - low) / position.entry_atr
    position.mfe_atr = max(position.mfe_atr, float(excursion))
    if not floor_cfg.enabled:
        return
    next_floor = position.floor_offset_atr
    for mfe_threshold, floor_offset in floor_cfg.tiers:
        if position.mfe_atr >= mfe_threshold:
            next_floor = max(next_floor, floor_offset)
    if floor_cfg.breakeven_mfe_atr is not None and position.mfe_atr >= floor_cfg.breakeven_mfe_atr:
        breakeven_offset = (position.entry_price * config.trade_cost_rate * 2.0) / position.entry_atr
        next_floor = max(next_floor, breakeven_offset)
    position.floor_offset_atr = next_floor


def close_position(
    *,
    equity: float,
    position: Position,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    config: V35Config,
) -> tuple[float, float]:
    pnl = position.direction * position.allocation * (exit_price / position.previous_price - 1.0)
    cost = config.trade_cost_rate * position.allocation
    exit_equity = equity * (1.0 + pnl - cost)
    raw_price_return = position.direction * (exit_price / position.entry_price - 1.0)
    trades.append(
        {
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "mfe_atr": position.mfe_atr,
            "floor_offset_atr": position.floor_offset_atr,
            "exit_reason": reason,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "raw_price_return": raw_price_return,
            "trade_return": exit_equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": exit_equity,
        }
    )
    return exit_equity, cost


def metrics_from_series(
    *,
    equity_curve: pd.Series,
    returns: pd.Series,
    weights: pd.Series,
    trades: pd.DataFrame,
    trading_costs: float,
    funding_pnl: float,
) -> dict[str, Any]:
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    volatility = float(returns.std(ddof=0))
    exit_counts = trades["exit_reason"].value_counts().to_dict() if not trades.empty else {}
    wins = int(trades["trade_return"].gt(0.0).sum()) if not trades.empty else 0
    return {
        "start": equity_curve.index.min().isoformat(),
        "end": equity_curve.index.max().isoformat(),
        "bars": int(len(equity_curve)),
        "return_pct": pct(float(equity_curve.iloc[-1] - 1.0)),
        "max_drawdown_pct": pct(float(drawdown.min())),
        "sharpe": round(float(0.0 if volatility == 0.0 else returns.mean() / volatility * np.sqrt(M15_PER_YEAR)), 2),
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": pct(wins / len(trades)) if len(trades) else 0.0,
        "long_trades": int(trades["direction"].eq(1).sum()) if not trades.empty else 0,
        "short_trades": int(trades["direction"].eq(-1).sum()) if not trades.empty else 0,
        "exit_counts": {str(key): int(value) for key, value in exit_counts.items()},
        "avg_abs_allocation": round(float(weights.abs().mean()), 4),
        "max_abs_allocation": round(float(weights.abs().max()), 4),
        "trading_costs_pct": pct(trading_costs),
        "funding_pnl_pct": pct(funding_pnl),
    }


def slice_metrics(equity_curve: pd.Series, trades: pd.DataFrame) -> list[dict[str, Any]]:
    end = equity_curve.index.max()
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=182),
        "1y": pd.Timedelta(days=365),
        "full": None,
    }
    rows: list[dict[str, Any]] = []
    for label, delta in windows.items():
        start = equity_curve.index.min() if delta is None else end - delta
        sliced = equity_curve.loc[equity_curve.index >= start]
        if sliced.empty:
            continue
        normalized = sliced / float(sliced.iloc[0])
        drawdown = normalized / normalized.cummax() - 1.0
        if trades.empty:
            trade_count = 0
        else:
            trade_count = int(pd.to_datetime(trades["exit_ts"], utc=True).ge(sliced.index.min()).sum())
        rows.append(
            {
                "window": label,
                "start": sliced.index.min().isoformat(),
                "end": sliced.index.max().isoformat(),
                "return_pct": pct(float(normalized.iloc[-1] - 1.0)),
                "max_drawdown_pct": pct(float(drawdown.min())),
                "closed_trades": trade_count,
            }
        )
    return rows


def open_position_summary(position: Position, data_end: pd.Timestamp) -> dict[str, Any]:
    return {
        "data_end": pd.Timestamp(data_end).isoformat(),
        "direction": position.direction,
        "entry_ts": position.entry_ts.isoformat(),
        "entry_price": position.entry_price,
        "entry_atr": position.entry_atr,
        "allocation": position.allocation,
        "mfe_atr": position.mfe_atr,
        "weak_bars": position.weak_bars,
        "floor_offset_atr": position.floor_offset_atr,
        "floor_price": position.entry_price + position.direction * position.floor_offset_atr * position.entry_atr
        if position.floor_offset_atr > 0.0
        else None,
    }


def build_comparison(runs: list[RunResult]) -> list[dict[str, Any]]:
    if len(runs) < 2:
        return []
    base = runs[0]
    rows: list[dict[str, Any]] = []
    for run in runs[1:]:
        rows.append(
            {
                "variant": run.name,
                "return_pct": run.metrics["return_pct"],
                "base_return_pct": base.metrics["return_pct"],
                "return_delta_pct": round(run.metrics["return_pct"] - base.metrics["return_pct"], 2),
                "max_drawdown_pct": run.metrics["max_drawdown_pct"],
                "max_drawdown_delta_pct": round(run.metrics["max_drawdown_pct"] - base.metrics["max_drawdown_pct"], 2),
                "sharpe": run.metrics["sharpe"],
                "sharpe_delta": round(run.metrics["sharpe"] - base.metrics["sharpe"], 2),
                "trades": run.metrics["trades"],
                "trade_delta": int(run.metrics["trades"] - base.metrics["trades"]),
                "profit_floor_exits": int(run.metrics["exit_counts"].get("profit_floor", 0)),
                "slice_return_delta_pct": [
                    {
                        "window": run_slice["window"],
                        "delta": round(run_slice["return_pct"] - base_slice["return_pct"], 2),
                        "variant_return_pct": run_slice["return_pct"],
                        "base_return_pct": base_slice["return_pct"],
                    }
                    for base_slice, run_slice in zip(base.slices, run.slices, strict=True)
                ],
            }
        )
    return rows


def write_artifacts(runs: list[RunResult], *, trades_path: Path, equity_path: Path) -> None:
    trade_frames = []
    equity_frames = []
    for run in runs:
        trades = run.trades.copy()
        if not trades.empty:
            trades.insert(0, "variant", run.name)
            trade_frames.append(trades)
        equity_frames.append(run.equity_curve.rename(run.name).to_frame())
    if trade_frames:
        pd.concat(trade_frames, ignore_index=True).to_csv(trades_path, index=False)
    pd.concat(equity_frames, axis=1).to_csv(equity_path, index_label="ts")


def _last_trades(trades: pd.DataFrame, count: int) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "mfe_atr",
        "floor_offset_atr",
        "exit_reason",
        "hold_bars",
        "trade_return",
    ]
    out = trades.tail(count)[columns].copy()
    out["trade_return_pct"] = out["trade_return"].map(pct)
    out = out.drop(columns=["trade_return"])
    return out.to_dict("records")


def pct(value: float) -> float:
    return round(float(value) * 100.0, 2)


if __name__ == "__main__":
    main()
