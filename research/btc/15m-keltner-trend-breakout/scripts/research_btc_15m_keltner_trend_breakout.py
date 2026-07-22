from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
from itertools import product
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-keltner-trend-breakout"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_AUDIT = (
    ROOT
    / "research/btc/15m-ema-trend-breakout/artifacts"
    / "btc_binance_15m_data_quality_latest.json"
)
OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
SYMBOL_FILE = "symbol=btc_usdt_usdt.parquet"

DATE = "2026-07-20"
AUDIT_PATH = ARTIFACT_DIR / f"btc_15m_keltner_data_quality_{DATE}.json"
CANDIDATES_PATH = ARTIFACT_DIR / f"btc_15m_keltner_search_candidates_{DATE}.csv"
SEARCH_SUMMARY_PATH = ARTIFACT_DIR / f"btc_15m_keltner_search_summary_{DATE}.json"
SELECTION_PATH = ARTIFACT_DIR / f"btc_15m_keltner_frozen_selection_{DATE}.json"
REVEAL_PATH = ARTIFACT_DIR / f"btc_15m_keltner_holdout_reveal_{DATE}.json"
TRADES_PATH = ARTIFACT_DIR / f"btc_15m_keltner_holdout_trades_{DATE}.csv"
WALK_FORWARD_PATH = ARTIFACT_DIR / f"btc_15m_keltner_dev_walk_forward_{DATE}.csv"

BAR = pd.Timedelta(minutes=15)
FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
ALLOCATION = 1.0
TOP_TRADE_SHARE_MAX = 0.35
TOP3_TRADE_SHARE_MAX = 0.70

KELTNER_EMAS = (10, 20, 40)
KELTNER_ATRS = (10, 20)
KELTNER_MULTS = (1.5, 2.0, 2.5)
REGIMES = (
    ("none", 0, 0, 0),
    ("ema", 12, 48, 0),
    ("ema_slope", 12, 48, 4),
    ("ema", 24, 96, 0),
    ("ema_slope", 24, 96, 4),
    ("ema", 48, 192, 0),
    ("ema_slope", 48, 192, 4),
)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    keltner_ema: int
    keltner_atr: int
    keltner_mult: float
    regime_mode: str
    h1_ema_fast: int
    h1_ema_slow: int
    h1_slope_lag: int
    exit_mode: str
    initial_stop_atr: float
    take_profit_atr: float
    trailing_stop_atr: float
    max_hold_bars: int
    side_mode: str = "both"
    fee_per_fill: float = FEE_PER_FILL
    slippage_per_fill: float = SLIPPAGE_PER_FILL
    allocation: float = ALLOCATION


@dataclass(frozen=True, slots=True)
class FeatureSet:
    mid: np.ndarray
    atr: np.ndarray
    upper: np.ndarray
    lower: np.ndarray
    long_regime: np.ndarray
    short_regime: np.ndarray


@dataclass(frozen=True, slots=True)
class SimulationResult:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series


EXIT_PROFILES = (
    {
        "exit_mode": "midline",
        "initial_stop_atr": 2.5,
        "take_profit_atr": 0.0,
        "trailing_stop_atr": 0.0,
        "max_hold_bars": 96,
    },
    {
        "exit_mode": "trailing",
        "initial_stop_atr": 2.5,
        "take_profit_atr": 0.0,
        "trailing_stop_atr": 2.5,
        "max_hold_bars": 96,
    },
    {
        "exit_mode": "trailing",
        "initial_stop_atr": 3.5,
        "take_profit_atr": 0.0,
        "trailing_stop_atr": 3.5,
        "max_hold_bars": 128,
    },
    {
        "exit_mode": "bracket",
        "initial_stop_atr": 2.5,
        "take_profit_atr": 4.0,
        "trailing_stop_atr": 0.0,
        "max_hold_bars": 64,
    },
    {
        "exit_mode": "bracket",
        "initial_stop_atr": 3.0,
        "take_profit_atr": 6.0,
        "trailing_stop_atr": 0.0,
        "max_hold_bars": 96,
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frozen BTCUSDT perpetual 15m Keltner trend-breakout study."
    )
    parser.add_argument("stage", choices=("search", "reveal", "smoke"))
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace same-identity artifacts. A different identity is always rejected.",
    )
    return parser.parse_args()


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


def finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return "inf" if number > 0 else "-inf"
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    complete = finite(payload)
    complete["payload_sha256"] = payload_sha256(complete)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def read_verified_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("payload_sha256")
    if expected != payload_sha256(payload):
        raise RuntimeError(f"payload SHA mismatch: {path}")
    return payload


def research_contract() -> dict[str, Any]:
    return {
        "family": "BTC-15M-Keltner-Trend-Breakout",
        "research_identity": "BTC-15M-KTB-INITIAL-FROZEN-SEARCH-2026-07-20",
        "market": "Binance USD-M Futures BTCUSDT perpetual",
        "timeframe": "15m",
        "signal": (
            "close crosses beyond EMA-mid plus/minus Keltner-mult times Wilder ATR; "
            "optional last-closed 1h EMA regime"
        ),
        "execution": {
            "entry": "signal bar close confirmation; next 15m open market fill",
            "exit": "gap-aware stop-market, stop-first intrabar, or next-open indicator exit",
            "allocation": ALLOCATION,
            "fee_per_fill": FEE_PER_FILL,
            "adverse_slippage_per_fill": SLIPPAGE_PER_FILL,
            "funding": "official audited historical rate, event-by-event return debit",
        },
        "universe": {
            "keltner_ema": KELTNER_EMAS,
            "keltner_atr": KELTNER_ATRS,
            "keltner_mult": KELTNER_MULTS,
            "regimes": REGIMES,
            "exit_profiles": EXIT_PROFILES,
            "side_mode": "both",
            "count": (
                len(KELTNER_EMAS)
                * len(KELTNER_ATRS)
                * len(KELTNER_MULTS)
                * len(REGIMES)
                * len(EXIT_PROFILES)
            ),
        },
        "development_gates": {
            "train_return_gt_pct": 0.0,
            "validation_return_gt_pct": 0.0,
            "train_mdd_abs_lte_pct": 25.0,
            "validation_mdd_abs_lte_pct": 25.0,
            "train_trades_min": 24,
            "validation_trades_min": 12,
            "train_pf_min": 1.05,
            "validation_pf_min": 1.05,
            "top_trade_positive_pnl_share_max": TOP_TRADE_SHARE_MAX,
            "top3_trade_positive_pnl_share_max": TOP3_TRADE_SHARE_MAX,
            "double_cost_train_and_validation_positive": True,
            "neighbor_train_validation_positive_ratio_min": 0.60,
        },
        "selection_rule": (
            "among complete gate passes maximize the lower of train and validation "
            "return, then lower PF, then total trades; otherwise freeze best near-miss"
        ),
        "holdout_rule": (
            "selection is frozen before one reveal; cross-family period exposure means "
            "the result is diagnostic OOS, not untouched future evidence"
        ),
    }


def contract_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(research_contract()))


def source_audit() -> dict[str, Any]:
    audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    if audit.get("total_blocker_count") != 0:
        raise RuntimeError("source BTC 15m audit has data-quality blockers")
    if audit.get("exchange") != "binance" or audit.get("symbol") != "BTCUSDT":
        raise RuntimeError("source BTC 15m audit identity mismatch")
    if audit.get("timeframe") != "15m":
        raise RuntimeError("source BTC 15m audit timeframe mismatch")
    return audit


def split_contract(audit: dict[str, Any]) -> dict[str, pd.Timestamp]:
    data_start = pd.Timestamp(audit["research_start"])
    data_end = pd.Timestamp(audit["closed_bar_cutoff_exclusive"])
    splits = {
        "data_start": data_start,
        "data_end": data_end,
        "train_start": pd.Timestamp("2024-07-17T14:45:00Z"),
        "validation_start": pd.Timestamp("2025-07-17T14:45:00Z"),
        "holdout_start": pd.Timestamp("2026-01-17T14:45:00Z"),
        "holdout_end": pd.Timestamp("2026-07-17T14:45:00Z"),
    }
    if data_end != splits["holdout_end"]:
        raise RuntimeError(
            f"source audit end changed: expected {splits['holdout_end']}, got {data_end}"
        )
    if not (
        data_start
        <= splits["train_start"]
        < splits["validation_start"]
        < splits["holdout_start"]
        < splits["holdout_end"]
    ):
        raise RuntimeError("invalid frozen split ordering")
    return splits


def date_paths(root: Path, start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    dates = pd.date_range(
        start.normalize(),
        (end - pd.Timedelta(nanoseconds=1)).normalize(),
        freq="1D",
    )
    paths = [root / f"date={date:%Y-%m-%d}" / SYMBOL_FILE for date in dates]
    missing = [path for path in paths if not path.exists()]
    if missing:
        sample = ", ".join(str(path.relative_to(ROOT)) for path in missing[:3])
        raise FileNotFoundError(f"missing standard data-lake partitions: {sample}")
    return paths


def load_data(
    splits: dict[str, pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    start = splits["data_start"]
    end = splits["data_end"]
    market_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    market_pieces = [
        pd.read_parquet(path, columns=market_columns)
        for path in date_paths(OHLCV_ROOT, start, end)
    ]
    frame = pd.concat(market_pieces, ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.loc[(frame["ts"] >= start) & (frame["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )

    funding_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "funding_rate",
        "source",
    ]
    funding_pieces = [
        pd.read_parquet(path, columns=funding_columns)
        for path in date_paths(FUNDING_ROOT, start, end)
    ]
    funding = pd.concat(funding_pieces, ignore_index=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.loc[(funding["ts"] >= start) & (funding["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )

    expected_index = pd.date_range(start, end - BAR, freq=BAR)
    checks = {
        "market_rows_match": len(frame) == len(expected_index),
        "market_continuity": pd.DatetimeIndex(frame["ts"]).equals(expected_index),
        "market_duplicates": not frame["ts"].duplicated().any(),
        "market_identity": bool(
            frame["exchange"].eq("binance").all()
            and frame["symbol"].eq("BTC/USDT:USDT").all()
            and frame["market_type"].eq("perp").all()
            and frame["timeframe"].eq("15m").all()
        ),
        "market_closed": bool(frame["is_closed"].all()),
        "market_critical_nulls": not frame[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
            ]
        ]
        .isna()
        .any()
        .any(),
        "market_ohlc_valid": bool(
            frame["high"].ge(frame[["open", "close", "low"]].max(axis=1)).all()
            and frame["low"].le(frame[["open", "close", "high"]].min(axis=1)).all()
        ),
        "funding_nonempty": not funding.empty,
        "funding_duplicates": not funding["ts"].duplicated().any(),
        "funding_identity": bool(
            funding["exchange"].eq("binance").all()
            and funding["symbol"].eq("BTC/USDT:USDT").all()
            and funding["market_type"].eq("perp").all()
        ),
        "funding_critical_nulls": not funding[["ts", "funding_rate", "source"]]
        .isna()
        .any()
        .any(),
        "funding_max_gap_lte_8h": bool(
            funding["ts"].diff().dropna().max() <= pd.Timedelta(hours=8)
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    quality = {
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "source_audit_sha256": sha256_bytes(SOURCE_AUDIT.read_bytes()),
        "exchange": "binance",
        "market_type": "perp",
        "symbol": "BTC/USDT:USDT",
        "timeframe": "15m",
        "start": frame["ts"].min().isoformat(),
        "end": frame["ts"].max().isoformat(),
        "end_exclusive": end.isoformat(),
        "market_rows": len(frame),
        "funding_rows": len(funding),
        "funding_first": funding["ts"].min().isoformat(),
        "funding_last": funding["ts"].max().isoformat(),
        "checks": checks,
        "blockers": failed,
    }
    if failed:
        raise RuntimeError(f"BTC 15m Keltner data-quality checks failed: {failed}")
    return frame.set_index("ts"), funding, quality


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(
        alpha=2.0 / (window + 1.0),
        adjust=False,
        min_periods=window,
    ).mean()


def wilder_atr(frame: pd.DataFrame, window: int) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()


def hourly_bars(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.resample("1h", origin="epoch", label="left", closed="left")
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        count=("open", "count"),
    )
    return bars.loc[bars["count"].eq(4)].drop(columns="count")


def mapped_hourly_regime(
    frame: pd.DataFrame,
    h1: pd.DataFrame,
    mode: str,
    fast: int,
    slow: int,
    slope_lag: int,
) -> tuple[np.ndarray, np.ndarray]:
    if mode == "none":
        return np.ones(len(frame), dtype=bool), np.ones(len(frame), dtype=bool)
    htf = h1.copy()
    fast_ema = ema(htf["close"], fast)
    slow_ema = ema(htf["close"], slow)
    long = fast_ema.gt(slow_ema) & htf["close"].gt(slow_ema)
    short = fast_ema.lt(slow_ema) & htf["close"].lt(slow_ema)
    if mode == "ema_slope":
        slope = slow_ema - slow_ema.shift(slope_lag)
        long &= slope.gt(0.0)
        short &= slope.lt(0.0)
    elif mode != "ema":
        raise ValueError(f"unknown regime mode: {mode}")

    h1_close_ns = (h1.index + pd.Timedelta(hours=1)).asi8
    signal_close_ns = (frame.index + BAR).asi8
    mapped = np.searchsorted(h1_close_ns, signal_close_ns, side="right") - 1
    valid = mapped >= 0
    long_out = np.zeros(len(frame), dtype=bool)
    short_out = np.zeros(len(frame), dtype=bool)
    long_values = long.fillna(False).to_numpy(dtype=bool)
    short_values = short.fillna(False).to_numpy(dtype=bool)
    long_out[valid] = long_values[mapped[valid]]
    short_out[valid] = short_values[mapped[valid]]
    return long_out, short_out


def feature_cache(
    frame: pd.DataFrame,
) -> dict[tuple[int, int, float, str, int, int, int], FeatureSet]:
    h1 = hourly_bars(frame)
    mid_cache = {window: ema(frame["close"], window) for window in KELTNER_EMAS}
    atr_cache = {window: wilder_atr(frame, window) for window in KELTNER_ATRS}
    regime_cache = {
        regime: mapped_hourly_regime(frame, h1, *regime) for regime in REGIMES
    }
    cache: dict[tuple[int, int, float, str, int, int, int], FeatureSet] = {}
    for keltner_ema, keltner_atr, mult, regime in product(
        KELTNER_EMAS,
        KELTNER_ATRS,
        KELTNER_MULTS,
        REGIMES,
    ):
        mode, fast, slow, slope_lag = regime
        mid = mid_cache[keltner_ema]
        atr = atr_cache[keltner_atr]
        upper = mid + mult * atr
        lower = mid - mult * atr
        long_regime, short_regime = regime_cache[regime]
        key = (
            keltner_ema,
            keltner_atr,
            mult,
            mode,
            fast,
            slow,
            slope_lag,
        )
        cache[key] = FeatureSet(
            mid=mid.to_numpy(dtype=float),
            atr=atr.to_numpy(dtype=float),
            upper=upper.to_numpy(dtype=float),
            lower=lower.to_numpy(dtype=float),
            long_regime=long_regime,
            short_regime=short_regime,
        )
    return cache


def candidate_universe() -> list[StrategyConfig]:
    candidates: list[StrategyConfig] = []
    for keltner_ema, keltner_atr, mult, regime, exit_profile in product(
        KELTNER_EMAS,
        KELTNER_ATRS,
        KELTNER_MULTS,
        REGIMES,
        EXIT_PROFILES,
    ):
        mode, fast, slow, slope_lag = regime
        candidates.append(
            StrategyConfig(
                keltner_ema=keltner_ema,
                keltner_atr=keltner_atr,
                keltner_mult=mult,
                regime_mode=mode,
                h1_ema_fast=fast,
                h1_ema_slow=slow,
                h1_slope_lag=slope_lag,
                **exit_profile,
            )
        )
    expected = research_contract()["universe"]["count"]
    if len(candidates) != expected:
        raise AssertionError(f"candidate count mismatch: {len(candidates)} != {expected}")
    return candidates


def feature_key(config: StrategyConfig) -> tuple[int, int, float, str, int, int, int]:
    return (
        config.keltner_ema,
        config.keltner_atr,
        config.keltner_mult,
        config.regime_mode,
        config.h1_ema_fast,
        config.h1_ema_slow,
        config.h1_slope_lag,
    )


def signal_arrays(
    close: np.ndarray,
    features: FeatureSet,
    side_mode: str,
) -> tuple[np.ndarray, np.ndarray]:
    previous_close = np.roll(close, 1)
    previous_upper = np.roll(features.upper, 1)
    previous_lower = np.roll(features.lower, 1)
    long_signal = (
        (close > features.upper)
        & (previous_close <= previous_upper)
        & features.long_regime
    )
    short_signal = (
        (close < features.lower)
        & (previous_close >= previous_lower)
        & features.short_regime
    )
    long_signal[0] = False
    short_signal[0] = False
    valid = (
        np.isfinite(close)
        & np.isfinite(features.mid)
        & np.isfinite(features.atr)
        & np.isfinite(features.upper)
        & np.isfinite(features.lower)
    )
    long_signal &= valid
    short_signal &= valid
    if side_mode == "long":
        short_signal[:] = False
    elif side_mode == "short":
        long_signal[:] = False
    elif side_mode != "both":
        raise ValueError(f"unknown side mode: {side_mode}")
    return long_signal, short_signal


def funding_cumulative_by_bar(
    index: pd.DatetimeIndex,
    funding: pd.DataFrame,
) -> np.ndarray:
    funding_ns = pd.DatetimeIndex(funding["ts"]).asi8
    rates = pd.to_numeric(funding["funding_rate"], errors="raise").to_numpy(float)
    cumulative = np.concatenate(([0.0], np.cumsum(rates)))
    locations = np.searchsorted(funding_ns, index.asi8, side="right")
    return cumulative[locations]


def adverse_fill(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    slippage: float,
) -> float:
    order_side = direction if is_entry else -direction
    return raw_price * (1.0 + order_side * slippage)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    returns = pd.to_numeric(trades["trade_return"], errors="coerce").dropna()
    gains = float(returns.loc[returns > 0.0].sum())
    losses = abs(float(returns.loc[returns < 0.0].sum()))
    if losses == 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / losses


def concentration(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return 1.0, 1.0
    positive = (
        pd.to_numeric(trades["trade_return"], errors="coerce")
        .dropna()
        .loc[lambda values: values > 0.0]
        .sort_values(ascending=False)
    )
    total = float(positive.sum())
    if total <= 0.0:
        return 1.0, 1.0
    return (
        float(positive.iloc[:1].sum() / total),
        float(positive.iloc[:3].sum() / total),
    )


def metrics_from_paths(
    equity: pd.Series,
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    if equity.empty:
        raise RuntimeError(f"empty equity path for {start} -> {end}")
    initial_and_path = np.concatenate(([1.0], equity.to_numpy(dtype=float)))
    drawdown = initial_and_path / np.maximum.accumulate(initial_and_path) - 1.0
    period_returns = equity.pct_change().fillna(equity.iloc[0] - 1.0)
    volatility = float(period_returns.std(ddof=0))
    top_one, top_three = concentration(trades)
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "bars": len(equity),
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "sharpe": float(
            0.0
            if volatility == 0.0
            else period_returns.mean()
            / volatility
            * math.sqrt(365.0 * 24.0 * 4.0)
        ),
        "trades": len(trades),
        "win_rate": float(
            0.0 if trades.empty else trades["trade_return"].gt(0.0).mean()
        ),
        "profit_factor": float(profit_factor(trades)),
        "long_trades": int(
            0 if trades.empty else trades["direction"].eq("long").sum()
        ),
        "short_trades": int(
            0 if trades.empty else trades["direction"].eq("short").sum()
        ),
        "top_trade_positive_pnl_share": top_one,
        "top3_trade_positive_pnl_share": top_three,
    }


def simulate(
    frame: pd.DataFrame,
    funding_cumulative: np.ndarray,
    features: FeatureSet,
    config: StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    label: str,
) -> SimulationResult:
    index = frame.index
    start_i = int(index.searchsorted(start))
    end_i = int(index.searchsorted(end))
    if start_i >= end_i:
        raise RuntimeError(f"empty simulation window: {start} -> {end}")

    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    long_signal, short_signal = signal_arrays(close, features, config.side_mode)

    realized_equity = 1.0
    position: dict[str, Any] | None = None
    pending_direction = 0
    pending_atr = math.nan
    pending_exit_reason: str | None = None
    trades: list[dict[str, Any]] = []
    curve_values: list[float] = []
    curve_index: list[pd.Timestamp] = []

    def close_position(i: int, raw_exit: float, reason: str) -> None:
        nonlocal realized_equity, position
        if position is None:
            raise AssertionError("cannot close an empty position")
        direction = int(position["direction"])
        exit_fill = adverse_fill(
            raw_exit,
            direction,
            is_entry=False,
            slippage=config.slippage_per_fill,
        )
        price_ratio = exit_fill / float(position["entry_fill"])
        funding_return = (
            -direction
            * config.allocation
            * (funding_cumulative[i] - float(position["funding_at_entry"]))
        )
        trade_return = config.allocation * (
            direction * (price_ratio - 1.0)
            - config.fee_per_fill
            - price_ratio * config.fee_per_fill
        ) + funding_return
        equity_before = float(position["equity_before"])
        equity_after = equity_before * (1.0 + trade_return)
        trades.append(
            {
                "label": label,
                "direction": "long" if direction == 1 else "short",
                "signal_ts": position["signal_ts"],
                "entry_ts": position["entry_ts"],
                "exit_ts": index[i],
                "entry_fill": position["entry_fill"],
                "exit_fill": exit_fill,
                "signal_atr": position["signal_atr"],
                "exit_reason": reason,
                "hold_bars": i - int(position["entry_i"]),
                "funding_return": funding_return,
                "trade_return": trade_return,
                "equity_before": equity_before,
                "equity_after": equity_after,
            }
        )
        realized_equity = equity_after
        position = None

    for i in range(start_i, end_i):
        ts = index[i]

        if position is not None and pending_exit_reason is not None:
            close_position(i, open_[i], pending_exit_reason)
            pending_exit_reason = None

        if position is None and pending_direction:
            entry_fill = adverse_fill(
                open_[i],
                pending_direction,
                is_entry=True,
                slippage=config.slippage_per_fill,
            )
            initial_stop = entry_fill - pending_direction * (
                config.initial_stop_atr * pending_atr
            )
            take_profit = (
                entry_fill
                + pending_direction * config.take_profit_atr * pending_atr
                if config.take_profit_atr > 0.0
                else math.nan
            )
            position = {
                "direction": pending_direction,
                "signal_ts": index[i - 1],
                "entry_i": i,
                "entry_ts": ts,
                "entry_fill": entry_fill,
                "signal_atr": pending_atr,
                "initial_stop": initial_stop,
                "active_stop": initial_stop,
                "take_profit": take_profit,
                "funding_at_entry": funding_cumulative[i],
                "equity_before": realized_equity,
            }
            pending_direction = 0
            pending_atr = math.nan

        if position is not None:
            direction = int(position["direction"])
            hold_bars = i - int(position["entry_i"])
            active_stop = float(position["active_stop"])
            exit_reason: str | None = None
            raw_exit = math.nan

            if hold_bars >= config.max_hold_bars:
                exit_reason = "time_open"
                raw_exit = open_[i]
            elif direction == 1:
                if open_[i] <= active_stop:
                    exit_reason = "stop_gap"
                    raw_exit = open_[i]
                elif low[i] <= active_stop:
                    exit_reason = "stop"
                    raw_exit = active_stop
                elif (
                    config.exit_mode == "bracket"
                    and high[i] >= float(position["take_profit"])
                ):
                    exit_reason = "take_profit"
                    raw_exit = float(position["take_profit"])
            else:
                if open_[i] >= active_stop:
                    exit_reason = "stop_gap"
                    raw_exit = open_[i]
                elif high[i] >= active_stop:
                    exit_reason = "stop"
                    raw_exit = active_stop
                elif (
                    config.exit_mode == "bracket"
                    and low[i] <= float(position["take_profit"])
                ):
                    exit_reason = "take_profit"
                    raw_exit = float(position["take_profit"])

            if exit_reason is not None:
                close_position(i, raw_exit, exit_reason)

        if position is not None:
            direction = int(position["direction"])
            if config.exit_mode == "trailing" and np.isfinite(features.atr[i]):
                proposed = close[i] - direction * (
                    config.trailing_stop_atr * features.atr[i]
                )
                if direction == 1:
                    position["active_stop"] = max(
                        float(position["active_stop"]),
                        proposed,
                    )
                else:
                    position["active_stop"] = min(
                        float(position["active_stop"]),
                        proposed,
                    )
            if config.exit_mode == "midline" and np.isfinite(features.mid[i]):
                if direction == 1 and close[i] < features.mid[i]:
                    pending_exit_reason = "midline_next_open"
                elif direction == -1 and close[i] > features.mid[i]:
                    pending_exit_reason = "midline_next_open"

        if position is None:
            if long_signal[i]:
                pending_direction = 1
                pending_atr = float(features.atr[i])
            elif short_signal[i]:
                pending_direction = -1
                pending_atr = float(features.atr[i])

        if position is None:
            marked_equity = realized_equity
        else:
            direction = int(position["direction"])
            price_ratio = close[i] / float(position["entry_fill"])
            open_trade_return = config.allocation * (
                direction * (price_ratio - 1.0) - config.fee_per_fill
            ) - direction * config.allocation * (
                funding_cumulative[i] - float(position["funding_at_entry"])
            )
            marked_equity = float(position["equity_before"]) * (
                1.0 + open_trade_return
            )
        curve_index.append(ts)
        curve_values.append(marked_equity)

    if position is not None:
        final_i = end_i - 1
        close_position(final_i, close[final_i], "window_end")
        curve_values[-1] = realized_equity

    equity = pd.Series(curve_values, index=pd.DatetimeIndex(curve_index), name=label)
    trades_frame = pd.DataFrame(trades)
    metrics = metrics_from_paths(equity, trades_frame, start, end)
    return SimulationResult(metrics=metrics, trades=trades_frame, equity=equity)


def candidate_id(config: StrategyConfig) -> str:
    body = asdict(config)
    digest = sha256_bytes(canonical_json_bytes(body))[:12]
    return f"ktb-{digest}"


def development_gate(
    train: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if train["return_pct"] <= 0.0:
        failures.append("train_return")
    if validation["return_pct"] <= 0.0:
        failures.append("validation_return")
    if abs(train["max_drawdown_pct"]) > 25.0:
        failures.append("train_mdd")
    if abs(validation["max_drawdown_pct"]) > 25.0:
        failures.append("validation_mdd")
    if train["trades"] < 24:
        failures.append("train_sample")
    if validation["trades"] < 12:
        failures.append("validation_sample")
    if train["profit_factor"] < 1.05:
        failures.append("train_pf")
    if validation["profit_factor"] < 1.05:
        failures.append("validation_pf")
    for name, metrics in (("train", train), ("validation", validation)):
        if metrics["top_trade_positive_pnl_share"] > TOP_TRADE_SHARE_MAX:
            failures.append(f"{name}_top_trade_concentration")
        if metrics["top3_trade_positive_pnl_share"] > TOP3_TRADE_SHARE_MAX:
            failures.append(f"{name}_top3_trade_concentration")
    return not failures, failures


def failure_score(
    train: dict[str, Any],
    validation: dict[str, Any],
    failures: list[str],
) -> float:
    return float(
        len(failures) * 10.0
        + max(0.0, -train["return_pct"]) / 5.0
        + max(0.0, -validation["return_pct"]) / 5.0
        + max(0.0, 24 - train["trades"]) / 4.0
        + max(0.0, 12 - validation["trades"]) / 2.0
        + max(0.0, 1.05 - train["profit_factor"]) * 10.0
        + max(0.0, 1.05 - validation["profit_factor"]) * 10.0
    )


def evaluate_config(
    frame: pd.DataFrame,
    funding_cumulative: np.ndarray,
    cache: dict[tuple[int, int, float, str, int, int, int], FeatureSet],
    config: StrategyConfig,
    splits: dict[str, pd.Timestamp],
    *,
    stress: bool = False,
) -> dict[str, Any]:
    active = (
        replace(
            config,
            fee_per_fill=config.fee_per_fill * 2.0,
            slippage_per_fill=config.slippage_per_fill * 2.0,
        )
        if stress
        else config
    )
    suffix = "_2x_cost" if stress else ""
    identifier = candidate_id(config)
    features = cache[feature_key(config)]
    train = simulate(
        frame,
        funding_cumulative,
        features,
        active,
        splits["train_start"],
        splits["validation_start"],
        label=f"{identifier}_train{suffix}",
    )
    validation = simulate(
        frame,
        funding_cumulative,
        features,
        active,
        splits["validation_start"],
        splits["holdout_start"],
        label=f"{identifier}_validation{suffix}",
    )
    return {"train": train.metrics, "validation": validation.metrics}


def rank_key(row: dict[str, Any]) -> tuple[float, float, int]:
    train = row["train"]
    validation = row["validation"]
    return (
        min(train["return_pct"], validation["return_pct"]),
        min(train["profit_factor"], validation["profit_factor"]),
        train["trades"] + validation["trades"],
    )


def neighboring_configs(config: StrategyConfig) -> list[StrategyConfig]:
    neighbors: dict[str, StrategyConfig] = {}

    def add(candidate: StrategyConfig) -> None:
        neighbors[candidate_id(candidate)] = candidate

    for value in KELTNER_EMAS:
        if value != config.keltner_ema:
            add(replace(config, keltner_ema=value))
    for value in KELTNER_ATRS:
        if value != config.keltner_atr:
            add(replace(config, keltner_atr=value))
    for value in sorted(
        {
            max(1.0, config.keltner_mult - 0.25),
            config.keltner_mult + 0.25,
        }
    ):
        add(replace(config, keltner_mult=value))
    if config.initial_stop_atr > 0.5:
        add(replace(config, initial_stop_atr=config.initial_stop_atr - 0.5))
    add(replace(config, initial_stop_atr=config.initial_stop_atr + 0.5))
    if config.exit_mode == "trailing":
        if config.trailing_stop_atr > 0.5:
            add(replace(config, trailing_stop_atr=config.trailing_stop_atr - 0.5))
        add(replace(config, trailing_stop_atr=config.trailing_stop_atr + 0.5))
    if config.exit_mode == "bracket":
        if config.take_profit_atr > 1.0:
            add(replace(config, take_profit_atr=config.take_profit_atr - 1.0))
        add(replace(config, take_profit_atr=config.take_profit_atr + 1.0))
    return list(neighbors.values())


def build_single_features(
    frame: pd.DataFrame,
    config: StrategyConfig,
) -> FeatureSet:
    mid = ema(frame["close"], config.keltner_ema)
    atr = wilder_atr(frame, config.keltner_atr)
    h1 = hourly_bars(frame)
    long_regime, short_regime = mapped_hourly_regime(
        frame,
        h1,
        config.regime_mode,
        config.h1_ema_fast,
        config.h1_ema_slow,
        config.h1_slope_lag,
    )
    return FeatureSet(
        mid=mid.to_numpy(float),
        atr=atr.to_numpy(float),
        upper=(mid + config.keltner_mult * atr).to_numpy(float),
        lower=(mid - config.keltner_mult * atr).to_numpy(float),
        long_regime=long_regime,
        short_regime=short_regime,
    )


def neighbor_audit(
    frame: pd.DataFrame,
    funding_cumulative: np.ndarray,
    config: StrategyConfig,
    splits: dict[str, pd.Timestamp],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for neighbor in neighboring_configs(config):
        features = build_single_features(frame, neighbor)
        train = simulate(
            frame,
            funding_cumulative,
            features,
            neighbor,
            splits["train_start"],
            splits["validation_start"],
            label=f"{candidate_id(neighbor)}_neighbor_train",
        ).metrics
        validation = simulate(
            frame,
            funding_cumulative,
            features,
            neighbor,
            splits["validation_start"],
            splits["holdout_start"],
            label=f"{candidate_id(neighbor)}_neighbor_validation",
        ).metrics
        rows.append(
            {
                "candidate_id": candidate_id(neighbor),
                "config": asdict(neighbor),
                "train_return_pct": train["return_pct"],
                "validation_return_pct": validation["return_pct"],
                "both_positive": (
                    train["return_pct"] > 0.0 and validation["return_pct"] > 0.0
                ),
            }
        )
    positive = sum(bool(row["both_positive"]) for row in rows)
    ratio = 0.0 if not rows else positive / len(rows)
    return {
        "neighbors": rows,
        "positive_count": positive,
        "count": len(rows),
        "train_validation_positive_ratio": ratio,
        "gate_pass": ratio >= 0.60,
    }


def flatten_search_row(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "candidate_id": row["candidate_id"],
        "config_json": json.dumps(row["config"], sort_keys=True),
        "development_gate": row["development_gate"],
        "stress_gate": row.get("stress_gate", False),
        "gate_failures": "|".join(row["gate_failures"]),
        "failure_score": row["failure_score"],
    }
    for split_name in (
        "train",
        "validation",
        "stress_2x_train",
        "stress_2x_validation",
    ):
        metrics = row.get(split_name)
        if metrics is None:
            continue
        for key, value in metrics.items():
            flat[f"{split_name}_{key}"] = value
    return flat


def run_search(force: bool) -> None:
    contract = research_contract()
    audit = source_audit()
    splits = split_contract(audit)
    frame, funding, quality = load_data(splits)
    funding_cumulative = funding_cumulative_by_bar(frame.index, funding)
    cache = feature_cache(frame)

    atomic_write_json(AUDIT_PATH, quality)
    rows: list[dict[str, Any]] = []
    candidates = candidate_universe()
    for number, config in enumerate(candidates, start=1):
        evaluated = evaluate_config(
            frame,
            funding_cumulative,
            cache,
            config,
            splits,
        )
        passed, failures = development_gate(
            evaluated["train"],
            evaluated["validation"],
        )
        rows.append(
            {
                "candidate_id": candidate_id(config),
                "config": asdict(config),
                "train": evaluated["train"],
                "validation": evaluated["validation"],
                "development_gate": passed,
                "gate_failures": failures,
                "failure_score": failure_score(
                    evaluated["train"],
                    evaluated["validation"],
                    failures,
                ),
            }
        )
        if number % 50 == 0 or number == len(candidates):
            print(f"evaluated {number}/{len(candidates)} candidates", flush=True)

    preliminary = [row for row in rows if row["development_gate"]]
    stress_targets = preliminary if preliminary else sorted(
        rows,
        key=lambda item: item["failure_score"],
    )[:10]
    for row in stress_targets:
        config = StrategyConfig(**row["config"])
        stress = evaluate_config(
            frame,
            funding_cumulative,
            cache,
            config,
            splits,
            stress=True,
        )
        row["stress_2x_train"] = stress["train"]
        row["stress_2x_validation"] = stress["validation"]
        row["stress_gate"] = (
            stress["train"]["return_pct"] > 0.0
            and stress["validation"]["return_pct"] > 0.0
        )
        if not row["stress_gate"]:
            row["gate_failures"].append("double_cost_return")

    full_passes = [
        row
        for row in rows
        if row["development_gate"] and row.get("stress_gate", False)
    ]
    if full_passes:
        selected = max(full_passes, key=rank_key)
    else:
        selected = min(rows, key=lambda item: item["failure_score"])
        if "no_complete_gate_pass" not in selected["gate_failures"]:
            selected["gate_failures"].append("no_complete_gate_pass")

    selected_config = StrategyConfig(**selected["config"])
    neighbors = neighbor_audit(
        frame,
        funding_cumulative,
        selected_config,
        splits,
    )
    role = (
        "candidate"
        if selected["development_gate"]
        and selected.get("stress_gate", False)
        and neighbors["gate_pass"]
        else "diagnostic_near_miss"
    )

    sorted_rows = sorted(
        rows,
        key=lambda item: (
            bool(item["development_gate"]),
            bool(item.get("stress_gate", False)),
            rank_key(item),
        ),
        reverse=True,
    )
    atomic_write_csv(
        CANDIDATES_PATH,
        pd.DataFrame([flatten_search_row(row) for row in sorted_rows]),
    )
    summary = {
        "contract": contract,
        "contract_sha256": contract_sha256(),
        "splits": {key: value.isoformat() for key, value in splits.items()},
        "data_quality_artifact": str(AUDIT_PATH.relative_to(ROOT)),
        "candidate_count": len(rows),
        "development_gate_pass_count": len(preliminary),
        "complete_gate_pass_count_before_neighbors": len(full_passes),
        "selected_candidate_id": selected["candidate_id"],
        "selected_role": role,
        "selected_metrics": {
            key: selected.get(key)
            for key in (
                "train",
                "validation",
                "stress_2x_train",
                "stress_2x_validation",
            )
        },
        "selected_gate_failures": selected["gate_failures"],
        "neighbor_audit": neighbors,
    }
    selection = {
        "family": contract["family"],
        "research_identity": contract["research_identity"],
        "contract_sha256": contract_sha256(),
        "candidate_metrics_sha256": sha256_bytes(CANDIDATES_PATH.read_bytes()),
        "splits": {key: value.isoformat() for key, value in splits.items()},
        "selected_candidate_id": selected["candidate_id"],
        "selected_role": role,
        "config": selected["config"],
        "development_metrics": summary["selected_metrics"],
        "gate_failures": selected["gate_failures"],
        "neighbor_audit": neighbors,
        "holdout_status": "not_read_by_search",
    }

    if SELECTION_PATH.exists() and not force:
        existing = read_verified_json(SELECTION_PATH)
        comparable = {
            key: existing.get(key)
            for key in (
                "research_identity",
                "contract_sha256",
                "candidate_metrics_sha256",
                "selected_candidate_id",
                "selected_role",
                "config",
            )
        }
        proposed = {key: selection.get(key) for key in comparable}
        if comparable != proposed:
            raise RuntimeError(
                "frozen selection already exists with a different identity; refusing overwrite"
            )
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return

    atomic_write_json(SEARCH_SUMMARY_PATH, summary)
    atomic_write_json(SELECTION_PATH, selection)
    print(json.dumps(finite(summary), ensure_ascii=False, indent=2))


def buy_and_hold(
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    close = frame.loc[(frame.index >= start) & (frame.index < end), "close"]
    equity = close / float(close.iloc[0])
    drawdown = equity / equity.cummax() - 1.0
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
    }


def fixed_window_audit(
    frame: pd.DataFrame,
    funding_cumulative: np.ndarray,
    features: FeatureSet,
    config: StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cursor = start + pd.Timedelta(days=60)
    number = 0
    while cursor < end:
        window_end = min(cursor + pd.Timedelta(days=30), end)
        result = simulate(
            frame,
            funding_cumulative,
            features,
            config,
            cursor,
            window_end,
            label=f"fixed_window_{number:02d}",
        )
        rows.append({"window": number, **result.metrics})
        cursor = window_end
        number += 1
    return pd.DataFrame(rows)


def recent_slices(
    frame: pd.DataFrame,
    funding_cumulative: np.ndarray,
    features: FeatureSet,
    config: StrategyConfig,
    end: pd.Timestamp,
) -> dict[str, Any]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    output: dict[str, Any] = {}
    for name, delta in windows.items():
        start = max(frame.index.min(), end - delta)
        output[name] = simulate(
            frame,
            funding_cumulative,
            features,
            config,
            start,
            end,
            label=f"recent_{name}",
        ).metrics
    return output


def run_reveal() -> None:
    if REVEAL_PATH.exists():
        print(json.dumps(read_verified_json(REVEAL_PATH), ensure_ascii=False, indent=2))
        return
    selection = read_verified_json(SELECTION_PATH)
    if selection["contract_sha256"] != contract_sha256():
        raise RuntimeError("frozen selection contract no longer matches script")
    if selection["candidate_metrics_sha256"] != sha256_bytes(
        CANDIDATES_PATH.read_bytes()
    ):
        raise RuntimeError("candidate metrics changed after selection freeze")

    audit = source_audit()
    splits = split_contract(audit)
    expected_splits = {key: value.isoformat() for key, value in splits.items()}
    if selection["splits"] != expected_splits:
        raise RuntimeError("frozen split mismatch")
    frame, funding, quality = load_data(splits)
    if quality["blockers"]:
        raise RuntimeError("data quality changed before reveal")
    funding_cumulative = funding_cumulative_by_bar(frame.index, funding)
    config = StrategyConfig(**selection["config"])
    features = build_single_features(frame, config)

    holdout = simulate(
        frame,
        funding_cumulative,
        features,
        config,
        splits["holdout_start"],
        splits["holdout_end"],
        label="holdout",
    )
    stress = simulate(
        frame,
        funding_cumulative,
        features,
        replace(
            config,
            fee_per_fill=config.fee_per_fill * 2.0,
            slippage_per_fill=config.slippage_per_fill * 2.0,
        ),
        splits["holdout_start"],
        splits["holdout_end"],
        label="holdout_2x_cost",
    )
    long_only = simulate(
        frame,
        funding_cumulative,
        features,
        replace(config, side_mode="long"),
        splits["holdout_start"],
        splits["holdout_end"],
        label="holdout_long_only",
    )
    short_only = simulate(
        frame,
        funding_cumulative,
        features,
        replace(config, side_mode="short"),
        splits["holdout_start"],
        splits["holdout_end"],
        label="holdout_short_only",
    )
    walk_forward = fixed_window_audit(
        frame,
        funding_cumulative,
        features,
        config,
        splits["train_start"],
        splits["holdout_start"],
    )
    atomic_write_csv(WALK_FORWARD_PATH, walk_forward)
    atomic_write_csv(TRADES_PATH, holdout.trades)

    positive_windows = int((walk_forward["return_pct"] > 0.0).sum())
    reveal_gates = {
        "holdout_return_positive": holdout.metrics["return_pct"] > 0.0,
        "holdout_trades_gte_30": holdout.metrics["trades"] >= 30,
        "holdout_mdd_abs_lte_25": abs(holdout.metrics["max_drawdown_pct"]) <= 25.0,
        "holdout_profit_factor_gte_1_05": holdout.metrics["profit_factor"] >= 1.05,
        "holdout_2x_cost_positive": stress.metrics["return_pct"] > 0.0,
        "development_fixed_windows_positive_ratio_gt_50": (
            positive_windows / len(walk_forward) > 0.50
        ),
        "selection_was_candidate": selection["selected_role"] == "candidate",
    }
    final_role = "research_candidate" if all(reveal_gates.values()) else "failed_diagnostic"
    payload = {
        "family": selection["family"],
        "research_identity": selection["research_identity"],
        "selection_payload_sha256": selection["payload_sha256"],
        "selected_candidate_id": selection["selected_candidate_id"],
        "selected_role_before_reveal": selection["selected_role"],
        "final_role": final_role,
        "config": selection["config"],
        "splits": expected_splits,
        "holdout_exposure_note": (
            "This period was not read by this search, but prior BTC family research "
            "exposed the same calendar window; it is diagnostic OOS, not untouched future OOS."
        ),
        "holdout": holdout.metrics,
        "holdout_2x_cost": stress.metrics,
        "holdout_long_only": long_only.metrics,
        "holdout_short_only": short_only.metrics,
        "buy_and_hold_holdout": buy_and_hold(
            frame,
            splits["holdout_start"],
            splits["holdout_end"],
        ),
        "recent_slices": recent_slices(
            frame,
            funding_cumulative,
            features,
            config,
            splits["holdout_end"],
        ),
        "development_fixed_window_audit": {
            "window_count": len(walk_forward),
            "positive_count": positive_windows,
            "positive_ratio": positive_windows / len(walk_forward),
            "artifact": str(WALK_FORWARD_PATH.relative_to(ROOT)),
        },
        "reveal_gates": reveal_gates,
        "artifacts": {
            "selection": str(SELECTION_PATH.relative_to(ROOT)),
            "holdout_trades": str(TRADES_PATH.relative_to(ROOT)),
            "walk_forward": str(WALK_FORWARD_PATH.relative_to(ROOT)),
        },
    }
    atomic_write_json(REVEAL_PATH, payload)
    print(json.dumps(finite(payload), ensure_ascii=False, indent=2))


def smoke() -> None:
    contract = research_contract()
    candidates = candidate_universe()
    if contract["universe"]["count"] != len(candidates):
        raise AssertionError("smoke candidate count mismatch")
    identifiers = {candidate_id(config) for config in candidates}
    if len(identifiers) != len(candidates):
        raise AssertionError("candidate identifiers are not unique")
    print(
        json.dumps(
            {
                "contract_sha256": contract_sha256(),
                "candidate_count": len(candidates),
                "status": "PASS",
            },
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    if args.stage == "smoke":
        smoke()
    elif args.stage == "search":
        run_search(args.force)
    else:
        run_reveal()


if __name__ == "__main__":
    main()
