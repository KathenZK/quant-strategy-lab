from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import json

import numpy as np
import pandas as pd

from strategy_lab.data.factors.engine import compute_factor_bundle
from strategy_lab.data.factors.hype_15m import hype_15m_registry
from strategy_lab.data.features.builder import FeatureBuilder
from strategy_lab.data.features.store import FeatureStore
from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.settings import default_settings
from strategy_lab.data.warehouse import DuckDBWarehouse
from strategy_lab.data.models import MarketType


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_QUALITY_REPORT = ARTIFACTS_DIR / "data_quality/hype_15m_data_quality_round2.json"


@dataclass(frozen=True)
class DataIdentity:
    exchange: str = "binance"
    symbol: str = "HYPE/USDT:USDT"
    market_type: str = "perp"
    timeframe: str = "15m"


IDENTITY = DataIdentity()


@dataclass(frozen=True)
class TripleBarrierConfig:
    horizon_bars: int = 12
    take_profit_atr: float = 1.5
    stop_loss_atr: float = 1.0
    fee_rate_per_fill: float = 0.001
    slippage_bps_per_fill: float = 4.0
    min_net_edge_bps: float = 0.0

    @property
    def round_trip_cost_rate(self) -> float:
        return 2.0 * (self.fee_rate_per_fill + self.slippage_bps_per_fill / 10_000.0)


def _barrier_outcome(
    frame: pd.DataFrame,
    index: int,
    *,
    direction: int,
    config: TripleBarrierConfig,
) -> tuple[float, int, str]:
    entry_index = index + 1
    if entry_index >= len(frame):
        return np.nan, -1, "insufficient_future"
    atr_pct = float(frame.iloc[index]["atr_pct_14"])
    entry_open = float(frame.iloc[entry_index]["open"])
    if not np.isfinite(atr_pct) or atr_pct <= 0.0 or not np.isfinite(entry_open) or entry_open <= 0.0:
        return np.nan, -1, "invalid_entry"

    if direction == 1:
        take_profit = entry_open * (1.0 + config.take_profit_atr * atr_pct)
        stop_loss = entry_open * (1.0 - config.stop_loss_atr * atr_pct)
    else:
        take_profit = entry_open * (1.0 - config.take_profit_atr * atr_pct)
        stop_loss = entry_open * (1.0 + config.stop_loss_atr * atr_pct)

    last_index = min(len(frame) - 1, entry_index + config.horizon_bars - 1)
    exit_index = last_index
    exit_price = float(frame.iloc[last_index]["close"])
    reason = "timeout"
    for j in range(entry_index, last_index + 1):
        bar = frame.iloc[j]
        bar_open = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        if direction == 1:
            if bar_open <= stop_loss:
                exit_index, exit_price, reason = j, bar_open, "stop_gap"
                break
            if bar_open >= take_profit:
                exit_index, exit_price, reason = j, bar_open, "take_profit_gap"
                break
            if low <= stop_loss:
                exit_index, exit_price, reason = j, stop_loss, "stop"
                break
            if high >= take_profit:
                exit_index, exit_price, reason = j, take_profit, "take_profit"
                break
        else:
            if bar_open >= stop_loss:
                exit_index, exit_price, reason = j, bar_open, "stop_gap"
                break
            if bar_open <= take_profit:
                exit_index, exit_price, reason = j, bar_open, "take_profit_gap"
                break
            if high >= stop_loss:
                exit_index, exit_price, reason = j, stop_loss, "stop"
                break
            if low <= take_profit:
                exit_index, exit_price, reason = j, take_profit, "take_profit"
                break

    gross_return = exit_price / entry_open - 1.0 if direction == 1 else entry_open / exit_price - 1.0
    net_return = gross_return - config.round_trip_cost_rate
    return net_return * 10_000.0, exit_index, reason


def add_triple_barrier_labels(frame: pd.DataFrame, config: TripleBarrierConfig | None = None) -> pd.DataFrame:
    config = config or TripleBarrierConfig()
    result = frame.sort_values("ts").reset_index(drop=True).copy()
    opens = result["open"].to_numpy(dtype="float64")
    highs = result["high"].to_numpy(dtype="float64")
    lows = result["low"].to_numpy(dtype="float64")
    closes = result["close"].to_numpy(dtype="float64")
    atrs = result["atr_pct_14"].to_numpy(dtype="float64")
    timestamps = result["ts"].to_numpy()
    long_values: list[float] = []
    short_values: list[float] = []
    long_exit: list[object] = []
    short_exit: list[object] = []
    long_reason: list[str] = []
    short_reason: list[str] = []
    for index in range(len(result)):
        entry_index = index + 1
        if entry_index >= len(result) or not np.isfinite(atrs[index]) or atrs[index] <= 0.0 or not np.isfinite(opens[entry_index]) or opens[entry_index] <= 0.0:
            long_bps, short_bps = np.nan, np.nan
            long_index = short_index = -1
            long_why = short_why = "invalid_entry"
        else:
            last_index = min(len(result) - 1, entry_index + config.horizon_bars - 1)
            entry_open = opens[entry_index]
            atr_pct = atrs[index]
            long_take = entry_open * (1.0 + config.take_profit_atr * atr_pct)
            long_stop = entry_open * (1.0 - config.stop_loss_atr * atr_pct)
            short_take = entry_open * (1.0 - config.take_profit_atr * atr_pct)
            short_stop = entry_open * (1.0 + config.stop_loss_atr * atr_pct)

            long_index, long_price, long_why = last_index, closes[last_index], "timeout"
            short_index, short_price, short_why = last_index, closes[last_index], "timeout"
            for j in range(entry_index, last_index + 1):
                if opens[j] <= long_stop:
                    long_index, long_price, long_why = j, opens[j], "stop_gap"
                    break
                if opens[j] >= long_take:
                    long_index, long_price, long_why = j, opens[j], "take_profit_gap"
                    break
                if lows[j] <= long_stop:
                    long_index, long_price, long_why = j, long_stop, "stop"
                    break
                if highs[j] >= long_take:
                    long_index, long_price, long_why = j, long_take, "take_profit"
                    break
            for j in range(entry_index, last_index + 1):
                if opens[j] >= short_stop:
                    short_index, short_price, short_why = j, opens[j], "stop_gap"
                    break
                if opens[j] <= short_take:
                    short_index, short_price, short_why = j, opens[j], "take_profit_gap"
                    break
                if highs[j] >= short_stop:
                    short_index, short_price, short_why = j, short_stop, "stop"
                    break
                if lows[j] <= short_take:
                    short_index, short_price, short_why = j, short_take, "take_profit"
                    break
            long_bps = (long_price / entry_open - 1.0 - config.round_trip_cost_rate) * 10_000.0
            short_bps = (entry_open / short_price - 1.0 - config.round_trip_cost_rate) * 10_000.0
        long_values.append(long_bps)
        short_values.append(short_bps)
        long_exit.append(timestamps[long_index] if long_index >= 0 else pd.NaT)
        short_exit.append(timestamps[short_index] if short_index >= 0 else pd.NaT)
        long_reason.append(long_why)
        short_reason.append(short_why)

    result["long_outcome_bps"] = long_values
    result["short_outcome_bps"] = short_values
    result["long_exit_ts"] = pd.to_datetime(long_exit, utc=True)
    result["short_exit_ts"] = pd.to_datetime(short_exit, utc=True)
    result["long_outcome_reason"] = long_reason
    result["short_outcome_reason"] = short_reason
    best = result[["long_outcome_bps", "short_outcome_bps"]].max(axis=1)
    result["direction_label"] = np.select(
        [result["long_outcome_bps"].ge(result["short_outcome_bps"]) & result["long_outcome_bps"].gt(config.min_net_edge_bps), result["short_outcome_bps"].gt(config.min_net_edge_bps)],
        [1, -1],
        default=0,
    ).astype("int8")
    result["label_best_outcome_bps"] = best
    result["label_config"] = json.dumps(asdict(config), sort_keys=True)
    return result


def _read_many(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        return pd.DataFrame()
    frame = pd.concat((pd.read_parquet(path) for path in paths), ignore_index=True)
    if "ts" in frame.columns:
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame


def _deduplicate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "ts" not in frame.columns:
        return frame
    keys = [column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in frame.columns]
    return frame.sort_values("ts").drop_duplicates(subset=keys, keep="last").reset_index(drop=True)


def load_hype_market_frame() -> tuple[pd.DataFrame, dict[str, object]]:
    if not DATA_QUALITY_REPORT.exists():
        raise RuntimeError(
            "Round 2 data-quality report is missing; run refresh_hype_15m_data.py first"
        )
    upstream_quality = json.loads(DATA_QUALITY_REPORT.read_text(encoding="utf-8"))
    if int(upstream_quality.get("total_blocker_count", -1)) != 0:
        raise RuntimeError("Round 2 upstream data-quality report contains blockers")
    ohlcv_root = DATA_DIR / "normalized" / "ohlcv" / "exchange=binance" / "market_type=perp" / "timeframe=15m"
    raw_ohlcv_root = DATA_DIR / "raw" / "ohlcv" / "exchange=binance" / "market_type=perp" / "timeframe=15m"
    mark_root = DATA_DIR / "normalized" / "mark_price_klines" / "exchange=binance" / "market_type=perp" / "timeframe=15m"
    funding_path = DATA_DIR / "normalized" / "funding" / "exchange=binance" / "market_type=perp" / "symbol=hype_usdt_usdt" / "funding.parquet"

    ohlcv = _deduplicate(_read_many(sorted(ohlcv_root.glob("**/symbol=hype_usdt_usdt.parquet"))))
    raw_ohlcv = _read_many(sorted(raw_ohlcv_root.glob("**/symbol=hype_usdt_usdt.parquet")))
    if "open_time" in raw_ohlcv.columns:
        raw_ohlcv = raw_ohlcv.rename(columns={"open_time": "ts"})
    raw_ohlcv = _deduplicate(raw_ohlcv)
    mark = _deduplicate(_read_many(sorted(mark_root.glob("**/symbol=hype_usdt_usdt.parquet"))))
    funding = _deduplicate(_read_many([funding_path] if funding_path.exists() else []))
    if ohlcv.empty:
        raise RuntimeError(f"HYPE normalized OHLCV is missing under {ohlcv_root}")

    if "is_closed" not in ohlcv.columns or not bool(ohlcv["is_closed"].all()):
        raise RuntimeError("HYPE 15m OHLCV contains missing or unclosed bars")
    if not (ohlcv["high"] >= ohlcv[["open", "close"]].max(axis=1)).all():
        raise RuntimeError("HYPE 15m OHLCV has high below open or close")
    if not (ohlcv["low"] <= ohlcv[["open", "close"]].min(axis=1)).all():
        raise RuntimeError("HYPE 15m OHLCV has low above open or close")
    if not (ohlcv["high"] >= ohlcv["low"]).all():
        raise RuntimeError("HYPE 15m OHLCV has high below low")

    raw_normalized_mismatches: dict[str, int] = {}
    if raw_ohlcv.empty:
        raise RuntimeError("HYPE raw OHLCV is missing; raw/normalized parity cannot be verified")
    common = ohlcv.set_index("ts").join(raw_ohlcv.set_index("ts"), lsuffix="_normalized", rsuffix="_raw", how="outer", sort=True)
    if len(common) != len(ohlcv) or common.index.isna().any():
        raise RuntimeError("HYPE raw/normalized OHLCV timestamp coverage differs")
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
    ):
        left = pd.to_numeric(common[f"{column}_normalized"], errors="coerce")
        right = pd.to_numeric(common[f"{column}_raw"], errors="coerce")
        raw_normalized_mismatches[column] = int((~np.isclose(left.to_numpy(), right.to_numpy(), equal_nan=True, rtol=0.0, atol=1e-12)).sum())
    raw_normalized_mismatches["is_closed"] = int((common["is_closed_normalized"].astype(bool) != common["is_closed_raw"].astype(bool)).sum())
    if any(raw_normalized_mismatches.values()):
        raise RuntimeError(f"HYPE raw/normalized OHLCV mismatch: {raw_normalized_mismatches}")

    ts = ohlcv["ts"].sort_values().drop_duplicates()
    deltas = ts.diff().dropna()
    unexpected = deltas[deltas != pd.Timedelta(minutes=15)]
    if not unexpected.empty:
        raise RuntimeError(f"HYPE 15m OHLCV has {len(unexpected)} non-15m gaps")

    frame = ohlcv.copy()
    if not mark.empty:
        mark = mark[["ts", "open", "high", "low", "close"]].rename(
            columns={
                "open": "mark_open",
                "high": "mark_high",
                "low": "mark_low",
                "close": "mark_price",
            }
        )
        frame = frame.merge(mark, on="ts", how="left", validate="one_to_one")
    else:
        frame["mark_price"] = pd.NA
    if funding.empty:
        frame["funding_rate"] = pd.NA
        frame["funding_ts"] = pd.NaT
    else:
        funding = funding[["ts", "funding_rate"]].sort_values("ts")
        frame = pd.merge_asof(
            frame.sort_values("ts"),
            funding.rename(columns={"ts": "funding_ts"}),
            left_on="ts",
            right_on="funding_ts",
            direction="backward",
        )
    frame = frame.sort_values("ts").reset_index(drop=True)
    frame["funding_age_hours"] = (frame["ts"] - frame["funding_ts"]).dt.total_seconds() / 3600.0

    quality = {
        "rows": int(len(frame)),
        "start": frame["ts"].min().isoformat(),
        "end": frame["ts"].max().isoformat(),
        "closed_rows": int(frame["is_closed"].sum()),
        "ohlcv_nulls": {key: int(value) for key, value in frame[["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]].isna().sum().items() if value},
        "mark_coverage": float(frame["mark_price"].notna().mean()),
        "funding_coverage": float(frame["funding_rate"].notna().mean()),
        "source_values": sorted(frame["source"].dropna().astype(str).unique().tolist()),
        "raw_normalized_mismatches": raw_normalized_mismatches,
        "upstream_data_quality_report": str(DATA_QUALITY_REPORT),
        "upstream_data_quality_sha256": hashlib.sha256(
            DATA_QUALITY_REPORT.read_bytes()
        ).hexdigest(),
    }
    upstream_ohlcv = upstream_quality["ohlcv"]
    if quality["start"] != upstream_ohlcv["first_ts"]:
        raise RuntimeError("factor input start differs from the audited OHLCV start")
    if quality["end"] != upstream_ohlcv["last_ts"]:
        raise RuntimeError("factor input end differs from the audited OHLCV end")
    if quality["rows"] != int(upstream_ohlcv["rows"]):
        raise RuntimeError("factor input row count differs from the audited OHLCV rows")
    return frame, quality


def build_hype_factor_dataset() -> tuple[pd.DataFrame, dict[str, object]]:
    market, quality = load_hype_market_frame()
    registry = hype_15m_registry()
    factors = compute_factor_bundle(market, registry)
    factor_columns = registry.names()
    merge_keys = ["ts", "exchange", "symbol", "market_type", "timeframe"]
    market_without_collisions = market.drop(columns=[name for name in factor_columns if name in market.columns])
    dataset = market_without_collisions.merge(factors, on=merge_keys, how="inner", validate="one_to_one")
    coverage = {name: float(dataset[name].notna().mean()) for name in factor_columns}
    manifest = {
        "family": "HYPE-15M-Factor-ML",
        "identity": asdict(IDENTITY),
        "data_quality": quality,
        "factor_count": len(factor_columns),
        "factor_names": factor_columns,
        "factor_coverage": coverage,
        "factor_specs": registry.specs(),
        "factor_versions": {
            name: registry.get(name).version() for name in factor_columns
        },
        "low_coverage_factors": [name for name, value in coverage.items() if value < 0.95],
        "feature_policy": "model candidates require coverage >= 0.95; low-coverage fields remain diagnostics only",
    }
    return dataset, manifest


def persist_hype_features(dataset: pd.DataFrame) -> dict[str, dict[str, str]]:
    settings = default_settings()
    layout = DataLakeLayout.from_settings(settings)
    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=hype_15m_registry(),
    )
    factor_names = builder.registry.names()
    bundle = dataset[["ts", "exchange", "symbol", "market_type", "timeframe", *factor_names]]
    return builder.persist_bundle(
        bundle,
        exchange=IDENTITY.exchange,
        symbol=IDENTITY.symbol,
        market_type=MarketType.PERP,
        timeframe=IDENTITY.timeframe,
    )


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
