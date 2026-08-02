from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings


ROOT = Path("research/hype/15m-multidimensional-trend-pyramiding")
ARTIFACT_DIR = ROOT / "artifacts"
FAMILY = "HYPE-15M-Multidimensional-Trend-Pyramiding"
STRATEGY_ID = "HYPE-15M-MDTP-V1"
PRIMARY_SYMBOL = "HYPE/USDT:USDT"
TRANSFER_SYMBOLS = (
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "TRX/USDT:USDT",
)
EXCHANGE = "binance"
TIMEFRAME = "15m"
M15_PER_YEAR = 365.0 * 24.0 * 4.0
HOURS_PER_YEAR = 365.0 * 24.0
RUN_DATE = "2026-07-31"
V35_KERNEL = Path("research/_shared-kernels/ema-trend-breakout/v1/engine.py")
V35_KERNEL_SHA256 = "4ce1923e5ef3e5d6f43d22304266f18155ba51da3628b63e8b8a749947101e32"


@dataclass(frozen=True, slots=True)
class FeatureWindows:
    h1_momentum: tuple[int, int, int] = (8, 24, 72)
    h4_momentum: tuple[int, int, int] = (2, 6, 18)
    h1_er: int = 24
    h4_er: int = 18
    h1_donchian: int = 72
    h4_donchian: int = 18
    h1_volume: int = 24
    h4_volume: int = 18
    h1_scale: int = 720
    h4_scale: int = 180
    slow_ema_h1: int = 96
    atr_h1: int = 24
    vol_target_m15: int = 96


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    regime_threshold: float = 0.18
    sprout_threshold: float = 0.10
    confirm_threshold: float = 0.24
    mature_threshold: float = 0.38
    decay_threshold: float = 0.06
    sprout_fraction: float = 0.25
    confirm_fraction: float = 0.60
    mature_fraction: float = 1.00
    target_annual_vol: float = 0.90
    max_allocation: float = 2.50
    min_rebalance: float = 0.10
    trail_atr: float = 4.0
    extension_atr: float = 2.5
    max_jump_concentration: float = 0.55
    recovery_lookback: int = 3
    slow_exit_window_h1: int = 48
    max_hold_bars: int = 0
    fee_per_fill: float = 0.001
    slippage_per_fill: float = 0.0004
    warmup_days: int = 45


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    include_volume: bool
    jump_adjustment: bool
    jump_gate: bool
    staged_position: bool
    recovery_add: bool
    extension_gate: bool
    score_decay_exit: bool


@dataclass(slots=True)
class Campaign:
    direction: int
    entry_ts: pd.Timestamp
    entry_bar: int
    entry_price: float
    average_entry: float
    entry_equity: float
    allocation: float
    peak_allocation: float
    allocation_sum: float
    allocation_bars: int
    highest: float
    lowest: float
    trailing_stop: float
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    add_count: int = 0
    reduce_count: int = 0
    fee_return: float = 0.0
    slippage_return: float = 0.0
    funding_return: float = 0.0


@dataclass(frozen=True, slots=True)
class RunResult:
    name: str
    metrics: dict[str, Any]
    equity: pd.Series
    returns: pd.Series
    weights: pd.Series
    trades: pd.DataFrame
    actions: pd.DataFrame
    state: pd.DataFrame


VARIANTS = (
    Variant(
        name="price_only",
        include_volume=False,
        jump_adjustment=False,
        jump_gate=False,
        staged_position=True,
        recovery_add=False,
        extension_gate=False,
        score_decay_exit=True,
    ),
    Variant(
        name="price_volume",
        include_volume=True,
        jump_adjustment=False,
        jump_gate=False,
        staged_position=True,
        recovery_add=False,
        extension_gate=False,
        score_decay_exit=True,
    ),
    Variant(
        name="full",
        include_volume=True,
        jump_adjustment=True,
        jump_gate=True,
        staged_position=True,
        recovery_add=True,
        extension_gate=True,
        score_decay_exit=True,
    ),
)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    primary_frame, primary_funding, primary_quality = load_symbol_data(
        warehouse,
        PRIMARY_SYMBOL,
    )
    windows = FeatureWindows()
    config = StrategyConfig()
    feature_set = build_feature_set(primary_frame, windows)

    main_runs: dict[str, dict[str, RunResult]] = {}
    for variant in VARIANTS:
        main_runs[variant.name] = run_cost_ladder(
            primary_frame,
            primary_funding,
            feature_set,
            windows,
            config,
            variant,
        )

    v35_runs = run_v35_cost_ladder(primary_frame, primary_funding)
    ablations = run_ablations(
        primary_frame,
        primary_funding,
        feature_set,
        windows,
        config,
    )
    walk_forward = run_walk_forward(
        primary_frame,
        primary_funding,
        feature_set,
        windows,
        config,
        VARIANTS,
    )
    stability_rows, heatmap_rows = run_threshold_stability(
        primary_frame,
        primary_funding,
        feature_set,
        windows,
        config,
    )
    window_rows = run_window_stability(
        primary_frame,
        primary_funding,
        windows,
        config,
    )
    monotonicity = score_monotonicity(feature_set["h1_native"])
    transfer_rows, transfer_quality = run_cross_asset_transfer(
        warehouse,
        windows,
        config,
    )

    net_runs = {
        name: scenarios["net"]
        for name, scenarios in main_runs.items()
    }
    period_breakdowns = {
        name: {
            "years": period_metrics(run, "year"),
            "market_states": market_state_metrics(run),
            "recent_slices": recent_slices(run),
        }
        for name, run in net_runs.items()
    }
    v35_net = v35_runs["standard_net"]
    period_breakdowns["v35_standard_cost"] = {
        "years": period_metrics(v35_net, "year"),
        "market_states": [],
        "recent_slices": recent_slices(v35_net),
    }

    comparison = build_main_comparison(v35_runs, main_runs)
    cost_ladders = {
        "v35": {name: run.metrics for name, run in v35_runs.items()},
        **{
            variant: {scenario: run.metrics for scenario, run in scenarios.items()}
            for variant, scenarios in main_runs.items()
        },
    }
    data_contract = {
        "primary": primary_quality,
        "transfer": transfer_quality,
        "feature_windows": asdict(windows),
        "strategy_config": asdict(config),
        "variants": [asdict(variant) for variant in VARIANTS],
        "execution": {
            "higher_timeframes": (
                "1h and 4h are resampled from closed 15m bars; each higher-timeframe "
                "feature is shifted one completed bin before forward-fill to 15m."
            ),
            "orders": (
                "15m close computes desired state; position changes execute at the next "
                "15m open. No same-bar close decision is filled at that close."
            ),
            "intrabar": (
                "ATR trailing stop active from the next bar; gap through stop fills at "
                "the worse open. Stop is checked before discretionary rebalancing."
            ),
        },
        "costs": {
            "canonical_v35": "0.00085 combined per filled allocation plus funding",
            "standard_binance": {
                "fee_per_fill": config.fee_per_fill,
                "adverse_slippage_per_fill": config.slippage_per_fill,
                "funding": "actual Binance funding aligned to 15m timestamps",
            },
        },
    }

    payload = {
        "family": FAMILY,
        "strategy_id": STRATEGY_ID,
        "status": "explore / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_contract": data_contract,
        "comparison": comparison,
        "cost_ladders": cost_ladders,
        "walk_forward": walk_forward,
        "ablations": {name: run.metrics for name, run in ablations.items()},
        "period_breakdowns": period_breakdowns,
        "parameter_stability": {
            "threshold_exit_grid": stability_rows,
            "heatmap": heatmap_rows,
            "adjacent_windows": window_rows,
            "selection_policy": (
                "No row was selected as a replacement. The predeclared default config "
                "remains the reported V1 research baseline."
            ),
        },
        "score_monotonicity": monotonicity,
        "cross_asset_transfer": transfer_rows,
        "limitations": [
            "HYPE Binance perp history begins 2025-05-30, so HYPE has only partial 2025 and 2026 year buckets.",
            "Historical HYPE data in this repository was already examined by prior projects; rolling folds are chronological pseudo-OOS, not untouched prospective OOS.",
            "Only OHLCV and funding are used. Order-book depth, taker buy volume, open interest, liquidation flow, and basis are outside V1.",
            "V35 is HYPE-specific and historically selected on this sample; its matched-window results are a benchmark, not fresh OOS evidence.",
        ],
    }

    write_json(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_research_{RUN_DATE}.json",
        payload,
    )
    write_main_csvs(
        v35_runs,
        main_runs,
        ablations,
        stability_rows,
        heatmap_rows,
        window_rows,
        transfer_rows,
        monotonicity,
    )
    write_report(payload)
    print_summary(payload)


def load_symbol_data(
    warehouse: DuckDBWarehouse,
    symbol: str,
    *,
    require_raw_parity: bool = True,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    columns = [
        "ts",
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
        "timeframe",
    ]
    normalized = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=symbol,
        timeframe=TIMEFRAME,
        columns=columns,
    )
    if normalized.empty:
        raise RuntimeError(f"missing normalized 15m data for {symbol}")
    duplicate_before = int(pd.to_datetime(normalized["ts"], utc=True).duplicated().sum())
    normalized = prepare_ohlcv(normalized)
    frame = normalized.loc[
        normalized["is_closed"].fillna(False).astype(bool)
    ].copy()
    expected = pd.date_range(frame.index.min(), frame.index.max(), freq="15min", tz="UTC")
    missing = expected.difference(frame.index)
    critical = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]
    nulls = {
        column: int(frame[column].isna().sum())
        for column in critical
        if column in frame.columns
    }
    invalid = (
        frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
        | frame["volume"].lt(0.0)
    )

    raw_check = raw_normalized_check(warehouse, symbol, frame)
    funding_frame = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=symbol,
        columns=["ts", "funding_rate", "source"],
    )
    if funding_frame.empty:
        funding = pd.Series(0.0, index=frame.index, name="funding_rate")
        funding_quality = {
            "rows": 0,
            "non_zero_aligned_rows": 0,
            "coverage_warning": "missing funding dataset; zero fill is a blocker",
        }
    else:
        funding_frame["ts"] = pd.to_datetime(
            funding_frame["ts"],
            utc=True,
        ).dt.floor("15min")
        funding_frame["funding_rate"] = pd.to_numeric(
            funding_frame["funding_rate"],
            errors="coerce",
        )
        raw_funding = (
            funding_frame.sort_values("ts")
            .drop_duplicates("ts", keep="last")
            .set_index("ts")["funding_rate"]
        )
        funding = raw_funding.reindex(frame.index).fillna(0.0).rename("funding_rate")
        funding_quality = {
            "rows": int(len(funding_frame)),
            "start": funding_frame["ts"].min().isoformat(),
            "end": funding_frame["ts"].max().isoformat(),
            "null_rates": int(funding_frame["funding_rate"].isna().sum()),
            "non_zero_aligned_rows": int(funding.ne(0.0).sum()),
            "aligned_sum_rate": float(funding.sum()),
        }

    quality = {
        "symbol": symbol,
        "exchange": EXCHANGE,
        "market_type": "perp",
        "timeframe": TIMEFRAME,
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "duplicate_ts_before_dedup": duplicate_before,
        "missing_15m_bars": int(len(missing)),
        "first_missing_15m_bars": [ts.isoformat() for ts in missing[:10]],
        "critical_nulls": nulls,
        "invalid_ohlcv_rows": int(invalid.sum()),
        "is_utc_index": str(frame.index.tz) == "UTC",
        "sources": {
            str(key): int(value)
            for key, value in frame["source"].value_counts().to_dict().items()
        },
        "raw_vs_normalized": raw_check,
        "funding": funding_quality,
        "accepted": bool(
            duplicate_before == 0
            and len(missing) == 0
            and sum(nulls.values()) == 0
            and int(invalid.sum()) == 0
            and raw_check.get("accepted", False)
            and funding_quality.get("rows", 0) > 0
            and funding_quality.get("null_rates", 0) == 0
        ),
    }
    quality["normalized_checks_pass"] = bool(
        duplicate_before == 0
        and len(missing) == 0
        and sum(nulls.values()) == 0
        and int(invalid.sum()) == 0
        and funding_quality.get("rows", 0) > 0
        and funding_quality.get("null_rates", 0) == 0
    )
    quality["evidence_status"] = (
        "accepted"
        if quality["accepted"]
        else "explore / untrusted: raw-normalized parity unavailable"
    )
    if require_raw_parity and not quality["accepted"]:
        raise RuntimeError(f"data quality blocker for {symbol}: {quality}")
    if not require_raw_parity and not quality["normalized_checks_pass"]:
        raise RuntimeError(f"normalized data quality blocker for {symbol}: {quality}")
    return (
        frame[["open", "high", "low", "close", "volume"]].copy(),
        funding,
        quality,
    )


def prepare_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    out = out.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ):
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def raw_normalized_check(
    warehouse: DuckDBWarehouse,
    symbol: str,
    normalized: pd.DataFrame,
) -> dict[str, Any]:
    columns = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
    ]
    try:
        raw = warehouse.load_dataset(
            layer="raw",
            kind=DatasetKind.OHLCV,
            exchange=EXCHANGE,
            market_type=MarketType.PERP,
            symbol=symbol,
            timeframe=TIMEFRAME,
            columns=columns,
        )
    except Exception as exc:
        return {
            "available": False,
            "accepted": False,
            "reason": f"raw loader/schema unavailable: {type(exc).__name__}: {exc}",
        }
    if raw.empty:
        return {
            "available": False,
            "accepted": False,
            "reason": "missing raw OHLCV dataset",
        }
    raw = prepare_ohlcv(raw)
    if "is_closed" in raw.columns:
        raw = raw.loc[raw["is_closed"].fillna(False).astype(bool)]
    common = raw.index.intersection(normalized.index)
    compare_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]
    max_diff: dict[str, float] = {}
    for column in compare_columns:
        left = pd.to_numeric(raw.loc[common, column], errors="coerce")
        right = pd.to_numeric(normalized.loc[common, column], errors="coerce")
        diff = (left - right).abs()
        max_diff[column] = float(diff.max()) if len(diff) else float("nan")
    accepted = (
        len(common) == len(normalized)
        and all(np.isfinite(value) and value <= 1e-10 for value in max_diff.values())
    )
    return {
        "available": True,
        "accepted": bool(accepted),
        "raw_rows": int(len(raw)),
        "normalized_rows": int(len(normalized)),
        "common_rows": int(len(common)),
        "max_abs_diff": max_diff,
    }


def resample_ohlcv(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        frame[["open", "high", "low", "close", "volume"]]
        .resample(rule, label="left", closed="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open", "high", "low", "close", "volume"])
    )


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        (
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ),
        axis=1,
    ).max(axis=1)


def causal_scaled(series: pd.Series, window: int) -> pd.Series:
    min_periods = min(window, max(4, window // 3))
    trailing_mean = series.rolling(window, min_periods=min_periods).mean().shift(1)
    trailing_std = series.rolling(window, min_periods=min_periods).std(ddof=0).shift(1)
    z = (series - trailing_mean) / trailing_std.replace(0.0, np.nan)
    return z.clip(-3.0, 3.0) / 3.0


def signed_efficiency(close: pd.Series, window: int) -> tuple[pd.Series, pd.Series]:
    changes = close.diff()
    path = changes.abs().rolling(window, min_periods=window).sum()
    displacement = close - close.shift(window)
    er = displacement / path.replace(0.0, np.nan)
    jump = changes.abs().rolling(window, min_periods=window).max() / path.replace(
        0.0,
        np.nan,
    )
    return er, jump


def donchian_position(frame: pd.DataFrame, window: int) -> pd.Series:
    prior_high = frame["high"].shift(1).rolling(window, min_periods=window).max()
    prior_low = frame["low"].shift(1).rolling(window, min_periods=window).min()
    return (
        2.0
        * (frame["close"] - prior_low)
        / (prior_high - prior_low).replace(0.0, np.nan)
        - 1.0
    ).clip(-1.5, 1.5)


def timeframe_features(
    frame: pd.DataFrame,
    momentum_windows: tuple[int, int, int],
    er_window: int,
    donchian_window: int,
    volume_window: int,
    scale_window: int,
    slow_ema: int,
    atr_window: int,
) -> pd.DataFrame:
    log_close = np.log(frame["close"])
    log_return = log_close.diff()
    realized = log_return.rolling(
        max(momentum_windows),
        min_periods=max(momentum_windows),
    ).std(ddof=0)
    out = pd.DataFrame(index=frame.index)
    momentum_columns: list[str] = []
    for horizon in momentum_windows:
        name = f"mom_{horizon}"
        raw = (log_close - log_close.shift(horizon)) / (
            realized * math.sqrt(horizon)
        ).replace(0.0, np.nan)
        out[name] = causal_scaled(raw, scale_window)
        momentum_columns.append(name)

    er, jump = signed_efficiency(frame["close"], er_window)
    out["signed_er"] = causal_scaled(er, scale_window)
    out["jump_concentration"] = jump.clip(0.0, 1.0)
    out["jump_adjusted_er"] = causal_scaled(
        er * (1.0 - jump.clip(0.0, 1.0)),
        scale_window,
    )
    out["donchian"] = causal_scaled(
        donchian_position(frame, donchian_window),
        scale_window,
    )
    signed_volume = frame["volume"] * np.sign(log_return.fillna(0.0))
    imbalance = signed_volume.rolling(
        volume_window,
        min_periods=volume_window,
    ).sum() / frame["volume"].rolling(
        volume_window,
        min_periods=volume_window,
    ).sum().replace(0.0, np.nan)
    out["volume_imbalance"] = causal_scaled(imbalance, scale_window)
    prior_median_volume = (
        frame["volume"]
        .rolling(volume_window, min_periods=volume_window)
        .median()
        .shift(1)
    )
    relative_volume = np.log(
        frame["volume"] / prior_median_volume.replace(0.0, np.nan)
    )
    direction = np.sign(log_close - log_close.shift(momentum_windows[0]))
    out["signed_rvol"] = causal_scaled(
        relative_volume * direction,
        scale_window,
    )
    out["slow_ema"] = frame["close"].ewm(
        span=slow_ema,
        adjust=False,
        min_periods=slow_ema,
    ).mean()
    out["atr"] = true_range(frame).rolling(
        atr_window,
        min_periods=atr_window,
    ).mean()
    out["prior_exit_high"] = (
        frame["high"]
        .shift(1)
        .rolling(48, min_periods=48)
        .max()
    )
    out["prior_exit_low"] = (
        frame["low"]
        .shift(1)
        .rolling(48, min_periods=48)
        .min()
    )
    out["pullback_return"] = frame["close"] / frame["close"].shift(3) - 1.0
    out["pullback_volume_ratio"] = frame["volume"].rolling(
        3,
        min_periods=3,
    ).mean() / prior_median_volume.replace(0.0, np.nan)
    out["reclaim_long"] = frame["close"].gt(
        frame["high"].shift(1).rolling(3, min_periods=3).max()
    )
    out["reclaim_short"] = frame["close"].lt(
        frame["low"].shift(1).rolling(3, min_periods=3).min()
    )
    out["price_score_plain"] = out[
        momentum_columns + ["signed_er", "donchian"]
    ].mean(axis=1)
    out["price_score_jump"] = out[
        momentum_columns + ["jump_adjusted_er", "donchian"]
    ].mean(axis=1)
    out["price_volume_score_plain"] = out[
        momentum_columns
        + ["signed_er", "donchian", "volume_imbalance", "signed_rvol"]
    ].mean(axis=1)
    out["price_volume_score_jump"] = out[
        momentum_columns
        + ["jump_adjusted_er", "donchian", "volume_imbalance", "signed_rvol"]
    ].mean(axis=1)
    return out


def build_feature_set(
    frame: pd.DataFrame,
    windows: FeatureWindows,
) -> dict[str, pd.DataFrame]:
    h1 = resample_ohlcv(frame, "1h")
    h4 = resample_ohlcv(frame, "4h")
    h1_native = timeframe_features(
        h1,
        windows.h1_momentum,
        windows.h1_er,
        windows.h1_donchian,
        windows.h1_volume,
        windows.h1_scale,
        windows.slow_ema_h1,
        windows.atr_h1,
    )
    h4_native = timeframe_features(
        h4,
        windows.h4_momentum,
        windows.h4_er,
        windows.h4_donchian,
        windows.h4_volume,
        windows.h4_scale,
        max(24, windows.slow_ema_h1 // 4),
        max(6, windows.atr_h1 // 4),
    )
    h1_native["_close"] = h1["close"]
    h1_aligned = h1_native.shift(1).reindex(frame.index, method="ffill")
    h4_aligned = h4_native.shift(1).reindex(frame.index, method="ffill")
    m15_log_return = np.log(frame["close"]).diff()
    realized_annual_vol = (
        m15_log_return.rolling(
            windows.vol_target_m15,
            min_periods=windows.vol_target_m15,
        ).std(ddof=0)
        * math.sqrt(M15_PER_YEAR)
    )
    m15 = pd.DataFrame(
        {
            "realized_annual_vol": realized_annual_vol,
            "atr": true_range(frame).rolling(96, min_periods=96).mean(),
        },
        index=frame.index,
    )
    return {
        "h1_native": h1_native,
        "h4_native": h4_native,
        "h1": h1_aligned,
        "h4": h4_aligned,
        "m15": m15,
    }


def score_column(variant: Variant) -> str:
    if variant.include_volume and variant.jump_adjustment:
        return "price_volume_score_jump"
    if variant.include_volume:
        return "price_volume_score_plain"
    if variant.jump_adjustment:
        return "price_score_jump"
    return "price_score_plain"


def build_state(
    frame: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    config: StrategyConfig,
    variant: Variant,
) -> pd.DataFrame:
    score_name = score_column(variant)
    h1 = features["h1"]
    h4 = features["h4"]
    state = pd.DataFrame(index=frame.index)
    state["h1_score"] = h1[score_name]
    state["h4_score"] = h4[score_name]
    state["direction"] = np.where(
        state["h4_score"].ge(config.regime_threshold),
        1,
        np.where(state["h4_score"].le(-config.regime_threshold), -1, 0),
    )
    aligned_score = state["direction"] * state["h1_score"]
    stage = np.where(
        aligned_score.ge(config.mature_threshold),
        3,
        np.where(
            aligned_score.ge(config.confirm_threshold),
            2,
            np.where(aligned_score.ge(config.sprout_threshold), 1, 0),
        ),
    )
    if not variant.staged_position:
        stage = np.where(aligned_score.ge(config.confirm_threshold), 3, 0)
    state["stage"] = stage.astype("int64")

    pullback = state["direction"] * h1["pullback_return"]
    reclaim = np.where(
        state["direction"].eq(1),
        h1["reclaim_long"],
        np.where(state["direction"].eq(-1), h1["reclaim_short"], False),
    )
    recovery = (
        state["direction"].ne(0)
        & pullback.shift(1).lt(0.0)
        & h1["pullback_volume_ratio"].shift(1).lt(1.0)
        & pd.Series(reclaim, index=state.index).fillna(False)
        & aligned_score.ge(config.confirm_threshold)
    )
    state["recovery"] = recovery & variant.recovery_add
    state.loc[state["recovery"], "stage"] = 3

    fractions = pd.Series(
        np.select(
            (
                state["stage"].eq(1),
                state["stage"].eq(2),
                state["stage"].eq(3),
            ),
            (
                config.sprout_fraction,
                config.confirm_fraction,
                config.mature_fraction,
            ),
            default=0.0,
        ),
        index=state.index,
        dtype="float64",
    )
    vol_scale = (
        config.target_annual_vol
        / features["m15"]["realized_annual_vol"].replace(0.0, np.nan)
    ).clip(lower=0.0, upper=config.max_allocation)
    state["target_allocation"] = (
        fractions * vol_scale
    ).clip(0.0, config.max_allocation)
    state["target_weight"] = state["direction"] * state["target_allocation"]
    state["extension_atr"] = (
        (frame["close"] - h1["slow_ema"]).abs()
        / h1["atr"].replace(0.0, np.nan)
    )
    state["jump_concentration"] = pd.concat(
        (
            h1["jump_concentration"],
            h4["jump_concentration"],
        ),
        axis=1,
    ).max(axis=1)
    state["block_add"] = False
    if variant.extension_gate:
        state["block_add"] |= state["extension_atr"].gt(config.extension_atr)
    if variant.jump_gate:
        state["block_add"] |= state["jump_concentration"].gt(
            config.max_jump_concentration
        )
    state["donchian_exit_long"] = frame["close"].lt(h1["prior_exit_low"])
    state["donchian_exit_short"] = frame["close"].gt(h1["prior_exit_high"])
    state["score_decay"] = aligned_score.lt(config.decay_threshold)
    state["regime_label"] = np.where(
        state["h4_score"].ge(0.35),
        "strong_up",
        np.where(
            state["h4_score"].le(-0.35),
            "strong_down",
            np.where(
                state["h4_score"].abs().lt(config.regime_threshold),
                "range",
                "transition",
            ),
        ),
    )
    return state


def run_cost_ladder(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, pd.DataFrame],
    windows: FeatureWindows,
    config: StrategyConfig,
    variant: Variant,
) -> dict[str, RunResult]:
    del windows
    scenarios = {
        "gross": (0.0, 0.0, False),
        "fee_only": (config.fee_per_fill, 0.0, False),
        "fee_slippage": (
            config.fee_per_fill,
            config.slippage_per_fill,
            False,
        ),
        "net": (
            config.fee_per_fill,
            config.slippage_per_fill,
            True,
        ),
    }
    state = build_state(frame, features, config, variant)
    return {
        scenario: simulate(
            name=f"{variant.name}_{scenario}",
            frame=frame,
            funding=funding,
            state=state,
            features=features,
            config=config,
            variant=variant,
            fee_per_fill=fee,
            slippage_per_fill=slippage,
            include_funding=include_funding,
        )
        for scenario, (fee, slippage, include_funding) in scenarios.items()
    }


def simulate(
    *,
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    state: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    config: StrategyConfig,
    variant: Variant,
    fee_per_fill: float,
    slippage_per_fill: float,
    include_funding: bool,
    active_start: pd.Timestamp | None = None,
    active_end: pd.Timestamp | None = None,
) -> RunResult:
    start_bar = max(
        int(config.warmup_days * 24 * 4),
        2,
    )
    equity = 1.0
    campaign: Campaign | None = None
    previous_close = float(frame["close"].iloc[start_bar - 1])
    equity_values: list[float] = []
    return_values: list[float] = []
    weight_values: list[float] = []
    index_values: list[pd.Timestamp] = []
    trades: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    long_contribution = 0.0
    short_contribution = 0.0
    turnover = 0.0
    fee_total = 0.0
    slippage_total = 0.0
    funding_total = 0.0
    active_start = (
        pd.Timestamp(active_start).tz_convert("UTC")
        if active_start is not None
        else frame.index[start_bar]
    )
    active_end = (
        pd.Timestamp(active_end).tz_convert("UTC")
        if active_end is not None
        else frame.index[-1]
    )

    for i in range(start_bar, len(frame)):
        ts = pd.Timestamp(frame.index[i])
        if ts > active_end:
            break
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        start_equity = equity
        in_active = ts >= active_start
        exited_this_bar = False

        if campaign is not None:
            gap_return = (
                campaign.direction
                * campaign.allocation
                * (open_price / previous_close - 1.0)
            )
            equity *= max(1e-9, 1.0 + gap_return)
            if campaign.direction == 1:
                long_contribution += gap_return
            else:
                short_contribution += gap_return

            if include_funding:
                funding_return = (
                    -campaign.direction
                    * campaign.allocation
                    * float(funding.iloc[i])
                )
                equity *= max(1e-9, 1.0 + funding_return)
                funding_total += funding_return
                campaign.funding_return += funding_return

            stop_hit = (
                low <= campaign.trailing_stop
                if campaign.direction == 1
                else high >= campaign.trailing_stop
            )
            if stop_hit:
                raw_exit = (
                    min(open_price, campaign.trailing_stop)
                    if campaign.direction == 1
                    else max(open_price, campaign.trailing_stop)
                )
                segment_return = (
                    campaign.direction
                    * campaign.allocation
                    * (raw_exit / open_price - 1.0)
                )
                equity *= max(1e-9, 1.0 + segment_return)
                if campaign.direction == 1:
                    long_contribution += segment_return
                else:
                    short_contribution += segment_return
                cost = close_campaign(
                    campaign=campaign,
                    equity=equity,
                    raw_exit_price=raw_exit,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="atr_trailing_stop",
                    trades=trades,
                    actions=actions,
                    fee_per_fill=fee_per_fill,
                    slippage_per_fill=slippage_per_fill,
                )
                equity *= max(1e-9, 1.0 - cost["total"])
                fee_total += cost["fee"]
                slippage_total += cost["slippage"]
                turnover += campaign.allocation
                campaign = None
                exited_this_bar = True

        signal_bar = i - 1
        desired_direction = int(state["direction"].iloc[signal_bar])
        desired_allocation = float(state["target_allocation"].iloc[signal_bar])
        exit_reason: str | None = None
        if campaign is not None:
            if desired_direction != campaign.direction:
                exit_reason = "regime_exit"
            elif campaign.direction == 1 and bool(
                state["donchian_exit_long"].iloc[signal_bar]
            ):
                exit_reason = "slow_donchian_exit"
            elif campaign.direction == -1 and bool(
                state["donchian_exit_short"].iloc[signal_bar]
            ):
                exit_reason = "slow_donchian_exit"
            elif variant.score_decay_exit and bool(
                state["score_decay"].iloc[signal_bar]
            ):
                exit_reason = "trend_score_decay"
            elif (
                config.max_hold_bars > 0
                and i - campaign.entry_bar >= config.max_hold_bars
            ):
                exit_reason = "timeout"

        if campaign is not None and exit_reason is not None and not exited_this_bar:
            cost = close_campaign(
                campaign=campaign,
                equity=equity,
                raw_exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=exit_reason,
                trades=trades,
                actions=actions,
                fee_per_fill=fee_per_fill,
                slippage_per_fill=slippage_per_fill,
            )
            equity *= max(1e-9, 1.0 - cost["total"])
            fee_total += cost["fee"]
            slippage_total += cost["slippage"]
            turnover += campaign.allocation
            campaign = None
            exited_this_bar = True

        if not in_active:
            desired_direction = 0
            desired_allocation = 0.0
        if ts == active_end and campaign is not None:
            desired_allocation = 0.0

        if (
            campaign is None
            and not exited_this_bar
            and desired_direction != 0
            and desired_allocation > 0.0
        ):
            initial_allocation = desired_allocation
            if variant.staged_position:
                initial_allocation = min(
                    desired_allocation,
                    config.sprout_fraction * config.max_allocation,
                )
            atr_value = float(features["m15"]["atr"].iloc[signal_bar])
            if np.isfinite(atr_value) and atr_value > 0.0:
                fee_cost = fee_per_fill * initial_allocation
                slippage_cost = slippage_per_fill * initial_allocation
                equity *= max(1e-9, 1.0 - fee_cost - slippage_cost)
                fee_total += fee_cost
                slippage_total += slippage_cost
                turnover += initial_allocation
                initial_stop = (
                    open_price - desired_direction * config.trail_atr * atr_value
                )
                campaign = Campaign(
                    direction=desired_direction,
                    entry_ts=ts,
                    entry_bar=i,
                    entry_price=open_price,
                    average_entry=open_price,
                    entry_equity=start_equity,
                    allocation=initial_allocation,
                    peak_allocation=initial_allocation,
                    allocation_sum=0.0,
                    allocation_bars=0,
                    highest=open_price,
                    lowest=open_price,
                    trailing_stop=initial_stop,
                    fee_return=fee_cost,
                    slippage_return=slippage_cost,
                )
                actions.append(
                    {
                        "ts": ts,
                        "action": "entry",
                        "direction": desired_direction,
                        "allocation_before": 0.0,
                        "allocation_after": initial_allocation,
                        "price": open_price,
                        "stage": int(state["stage"].iloc[signal_bar]),
                        "recovery": bool(state["recovery"].iloc[signal_bar]),
                        "block_add": bool(state["block_add"].iloc[signal_bar]),
                    }
                )

        if campaign is not None and not exited_this_bar:
            target = (
                desired_allocation
                if desired_direction == campaign.direction
                else 0.0
            )
            delta = target - campaign.allocation
            if abs(delta) >= config.min_rebalance:
                is_add = delta > 0.0
                profitable = (
                    campaign.direction * (open_price / campaign.average_entry - 1.0)
                    > 0.0
                )
                blocked = bool(state["block_add"].iloc[signal_bar])
                if not is_add or (profitable and not blocked):
                    fee_cost = fee_per_fill * abs(delta)
                    slippage_cost = slippage_per_fill * abs(delta)
                    equity *= max(1e-9, 1.0 - fee_cost - slippage_cost)
                    fee_total += fee_cost
                    slippage_total += slippage_cost
                    turnover += abs(delta)
                    campaign.fee_return += fee_cost
                    campaign.slippage_return += slippage_cost
                    before = campaign.allocation
                    if is_add:
                        campaign.average_entry = (
                            campaign.average_entry * campaign.allocation
                            + open_price * delta
                        ) / target
                        campaign.add_count += 1
                    else:
                        campaign.reduce_count += 1
                    campaign.allocation = target
                    campaign.peak_allocation = max(
                        campaign.peak_allocation,
                        campaign.allocation,
                    )
                    actions.append(
                        {
                            "ts": ts,
                            "action": "add" if is_add else "reduce",
                            "direction": campaign.direction,
                            "allocation_before": before,
                            "allocation_after": target,
                            "price": open_price,
                            "stage": int(state["stage"].iloc[signal_bar]),
                            "recovery": bool(state["recovery"].iloc[signal_bar]),
                            "block_add": blocked,
                        }
                    )
                    if target <= 1e-12:
                        cost = close_campaign(
                            campaign=campaign,
                            equity=equity,
                            raw_exit_price=open_price,
                            exit_ts=ts,
                            exit_bar=i,
                            reason="target_flat",
                            trades=trades,
                            actions=actions,
                            fee_per_fill=0.0,
                            slippage_per_fill=0.0,
                        )
                        del cost
                        campaign = None
                        exited_this_bar = True

        if campaign is not None and not exited_this_bar:
            intrabar_return = (
                campaign.direction
                * campaign.allocation
                * (close / open_price - 1.0)
            )
            equity *= max(1e-9, 1.0 + intrabar_return)
            if campaign.direction == 1:
                long_contribution += intrabar_return
            else:
                short_contribution += intrabar_return
            campaign.highest = max(campaign.highest, high)
            campaign.lowest = min(campaign.lowest, low)
            campaign.mfe_pct = max(
                campaign.mfe_pct,
                campaign.direction
                * (
                    (
                        campaign.highest
                        if campaign.direction == 1
                        else campaign.lowest
                    )
                    / campaign.average_entry
                    - 1.0
                ),
            )
            adverse_price = (
                campaign.lowest
                if campaign.direction == 1
                else campaign.highest
            )
            campaign.mae_pct = min(
                campaign.mae_pct,
                campaign.direction
                * (adverse_price / campaign.average_entry - 1.0),
            )
            atr_value = float(features["m15"]["atr"].iloc[i])
            if np.isfinite(atr_value) and atr_value > 0.0:
                candidate_stop = (
                    campaign.highest - config.trail_atr * atr_value
                    if campaign.direction == 1
                    else campaign.lowest + config.trail_atr * atr_value
                )
                campaign.trailing_stop = (
                    max(campaign.trailing_stop, candidate_stop)
                    if campaign.direction == 1
                    else min(campaign.trailing_stop, candidate_stop)
                )
            campaign.allocation_sum += campaign.allocation
            campaign.allocation_bars += 1

        if ts >= active_start:
            index_values.append(ts)
            equity_values.append(equity)
            return_values.append(equity / start_equity - 1.0)
            weight_values.append(
                0.0
                if campaign is None
                else campaign.direction * campaign.allocation
            )
        previous_close = close

    if campaign is not None and index_values:
        ts = index_values[-1]
        raw_exit = float(frame.loc[ts, "close"])
        cost = close_campaign(
            campaign=campaign,
            equity=equity,
            raw_exit_price=raw_exit,
            exit_ts=ts,
            exit_bar=int(frame.index.get_loc(ts)),
            reason="end_of_window",
            trades=trades,
            actions=actions,
            fee_per_fill=fee_per_fill,
            slippage_per_fill=slippage_per_fill,
        )
        equity *= max(1e-9, 1.0 - cost["total"])
        fee_total += cost["fee"]
        slippage_total += cost["slippage"]
        turnover += campaign.allocation
        if equity_values:
            equity_values[-1] = equity
            return_values[-1] = equity / (
                equity_values[-2] if len(equity_values) > 1 else 1.0
            ) - 1.0
            weight_values[-1] = 0.0

    index = pd.DatetimeIndex(index_values)
    equity_series = pd.Series(equity_values, index=index, name=name)
    returns_series = pd.Series(
        return_values,
        index=index,
        name=f"{name}_return",
    )
    weights_series = pd.Series(
        weight_values,
        index=index,
        name=f"{name}_weight",
    )
    trades_frame = pd.DataFrame(trades)
    actions_frame = pd.DataFrame(actions)
    metrics = compute_metrics(
        equity_series,
        returns_series,
        weights_series,
        trades_frame,
        turnover,
        fee_total,
        slippage_total,
        funding_total,
        long_contribution,
        short_contribution,
    )
    return RunResult(
        name=name,
        metrics=metrics,
        equity=equity_series,
        returns=returns_series,
        weights=weights_series,
        trades=trades_frame,
        actions=actions_frame,
        state=state.loc[index].copy(),
    )


def close_campaign(
    *,
    campaign: Campaign,
    equity: float,
    raw_exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    fee_per_fill: float,
    slippage_per_fill: float,
) -> dict[str, float]:
    fee_cost = fee_per_fill * campaign.allocation
    slippage_cost = slippage_per_fill * campaign.allocation
    final_equity = equity * max(1e-9, 1.0 - fee_cost - slippage_cost)
    campaign.fee_return += fee_cost
    campaign.slippage_return += slippage_cost
    trades.append(
        {
            "entry_ts": campaign.entry_ts,
            "exit_ts": exit_ts,
            "direction": campaign.direction,
            "entry_price": campaign.entry_price,
            "average_entry": campaign.average_entry,
            "exit_price": raw_exit_price,
            "entry_bar": campaign.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - campaign.entry_bar,
            "hold_hours": (exit_bar - campaign.entry_bar) / 4.0,
            "entry_allocation": campaign.peak_allocation
            if campaign.add_count == 0
            else np.nan,
            "peak_allocation": campaign.peak_allocation,
            "average_allocation": (
                campaign.allocation_sum / campaign.allocation_bars
                if campaign.allocation_bars
                else campaign.allocation
            ),
            "add_count": campaign.add_count,
            "reduce_count": campaign.reduce_count,
            "mfe_pct": campaign.mfe_pct,
            "mae_pct": campaign.mae_pct,
            "exit_reason": reason,
            "raw_price_return": (
                campaign.direction
                * (raw_exit_price / campaign.average_entry - 1.0)
            ),
            "trade_return": final_equity / campaign.entry_equity - 1.0,
            "fee_return_sum": campaign.fee_return,
            "slippage_return_sum": campaign.slippage_return,
            "funding_return_sum": campaign.funding_return,
            "entry_equity": campaign.entry_equity,
            "exit_equity": final_equity,
        }
    )
    actions.append(
        {
            "ts": exit_ts,
            "action": "exit",
            "direction": campaign.direction,
            "allocation_before": campaign.allocation,
            "allocation_after": 0.0,
            "price": raw_exit_price,
            "stage": 0,
            "recovery": False,
            "block_add": False,
            "reason": reason,
        }
    )
    return {
        "fee": fee_cost,
        "slippage": slippage_cost,
        "total": fee_cost + slippage_cost,
    }


def compute_metrics(
    equity: pd.Series,
    returns: pd.Series,
    weights: pd.Series,
    trades: pd.DataFrame,
    turnover: float,
    fee_total: float,
    slippage_total: float,
    funding_total: float,
    long_contribution: float,
    short_contribution: float,
) -> dict[str, Any]:
    if equity.empty:
        return empty_metrics()
    years = max(
        (equity.index[-1] - equity.index[0]).total_seconds()
        / (365.0 * 24.0 * 3600.0),
        1.0 / 365.0,
    )
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = (
        float(equity.iloc[-1] ** (1.0 / years) - 1.0)
        if equity.iloc[-1] > 0.0
        else -1.0
    )
    drawdown = equity / equity.cummax() - 1.0
    volatility = float(returns.std(ddof=0))
    downside = float(returns.loc[returns.lt(0.0)].std(ddof=0))
    sharpe = (
        0.0
        if volatility == 0.0
        else float(returns.mean() / volatility * math.sqrt(M15_PER_YEAR))
    )
    sortino = (
        0.0
        if downside == 0.0 or not np.isfinite(downside)
        else float(returns.mean() / downside * math.sqrt(M15_PER_YEAR))
    )
    max_drawdown = float(drawdown.min())
    calmar = 0.0 if max_drawdown >= 0.0 else cagr / abs(max_drawdown)
    if trades.empty:
        win_rate = payoff = profit_factor = avg_hold = 0.0
        wins = losses = pd.Series(dtype="float64")
    else:
        wins = trades.loc[trades["trade_return"].gt(0.0), "trade_return"]
        losses = trades.loc[trades["trade_return"].le(0.0), "trade_return"]
        win_rate = float(len(wins) / len(trades))
        payoff = (
            0.0
            if losses.empty or float(losses.mean()) == 0.0
            else float(wins.mean() / abs(losses.mean()))
        )
        profit_factor = (
            float("inf")
            if losses.empty or float(losses.sum()) == 0.0
            else float(wins.sum() / abs(losses.sum()))
        )
        avg_hold = float(trades["hold_hours"].mean())
    return {
        "start": equity.index[0].isoformat(),
        "end": equity.index[-1].isoformat(),
        "bars": int(len(equity)),
        "years": round(years, 4),
        "total_return_pct": round(total_return * 100.0, 4),
        "cagr_pct": round(cagr * 100.0, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_drawdown_pct": round(max_drawdown * 100.0, 4),
        "calmar": round(calmar, 4),
        "trades": int(len(trades)),
        "win_rate_pct": round(win_rate * 100.0, 4),
        "payoff_ratio": round(payoff, 4),
        "profit_factor": (
            "inf" if not np.isfinite(profit_factor) else round(profit_factor, 4)
        ),
        "avg_hold_hours": round(avg_hold, 4),
        "turnover_total": round(turnover, 4),
        "turnover_annualized": round(turnover / years, 4),
        "avg_abs_allocation": round(float(weights.abs().mean()), 4),
        "max_abs_allocation": round(float(weights.abs().max()), 4),
        "long_return_contribution_pct": round(long_contribution * 100.0, 4),
        "short_return_contribution_pct": round(short_contribution * 100.0, 4),
        "fee_return_sum_pct": round(fee_total * 100.0, 4),
        "slippage_return_sum_pct": round(slippage_total * 100.0, 4),
        "funding_return_sum_pct": round(funding_total * 100.0, 4),
        "long_trades": (
            int(trades["direction"].eq(1).sum()) if not trades.empty else 0
        ),
        "short_trades": (
            int(trades["direction"].eq(-1).sum()) if not trades.empty else 0
        ),
        "exit_counts": (
            {
                str(key): int(value)
                for key, value in trades["exit_reason"].value_counts().to_dict().items()
            }
            if not trades.empty
            else {}
        ),
    }


def empty_metrics() -> dict[str, Any]:
    return {
        "total_return_pct": 0.0,
        "cagr_pct": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "max_drawdown_pct": 0.0,
        "calmar": 0.0,
        "trades": 0,
        "win_rate_pct": 0.0,
        "payoff_ratio": 0.0,
        "profit_factor": 0.0,
        "avg_hold_hours": 0.0,
        "turnover_total": 0.0,
        "turnover_annualized": 0.0,
        "long_return_contribution_pct": 0.0,
        "short_return_contribution_pct": 0.0,
    }


def load_v35_kernel() -> Any:
    digest = hashlib.sha256(V35_KERNEL.read_bytes()).hexdigest()
    if digest != V35_KERNEL_SHA256:
        raise RuntimeError(
            f"V35 kernel SHA mismatch: expected {V35_KERNEL_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location("mdtp_v35_frozen", V35_KERNEL)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen V35 kernel")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_v35_cost_ladder(
    frame: pd.DataFrame,
    funding: pd.Series,
) -> dict[str, RunResult]:
    kernel = load_v35_kernel()
    scenarios = {
        "canonical_legacy_net": kernel.V35Config(
            cost_mode="legacy_cost",
            trade_cost_rate=0.00085,
            execution_mode="legacy_exact",
        ),
        "standard_gross": kernel.V35Config(
            cost_mode="explicit",
            fee_per_fill=0.0,
            adverse_slippage_per_fill=0.0,
            execution_mode="gap_open",
        ),
        "standard_fee_only": kernel.V35Config(
            cost_mode="explicit",
            fee_per_fill=0.001,
            adverse_slippage_per_fill=0.0,
            execution_mode="gap_open",
        ),
        "standard_fee_slippage": kernel.V35Config(
            cost_mode="explicit",
            fee_per_fill=0.001,
            adverse_slippage_per_fill=0.0004,
            execution_mode="gap_open",
        ),
        "standard_net": kernel.V35Config(
            cost_mode="explicit",
            fee_per_fill=0.001,
            adverse_slippage_per_fill=0.0004,
            execution_mode="gap_open",
        ),
    }
    out: dict[str, RunResult] = {}
    for name, config in scenarios.items():
        features = kernel.build_signals(
            kernel.build_features(frame, config),
            config,
            kernel.SignalFlags(),
        )
        selected_funding = (
            funding if name in {"canonical_legacy_net", "standard_net"} else None
        )
        result = kernel.run_backtest(
            f"v35_{name}",
            frame,
            selected_funding,
            features,
            config,
        )
        out[name] = adapt_v35_run(result, frame)
    return out


def adapt_v35_run(result: Any, frame: pd.DataFrame) -> RunResult:
    equity = result.equity_curve
    returns = result.period_returns
    trades = result.trades.copy()
    if not trades.empty:
        trades["hold_hours"] = trades["hold_bars"] / 4.0
    weights = pd.Series(0.0, index=equity.index)
    for trade in trades.to_dict(orient="records"):
        start = pd.Timestamp(trade["entry_ts"])
        end = pd.Timestamp(trade["exit_ts"])
        weights.loc[(weights.index >= start) & (weights.index < end)] = (
            int(trade["direction"]) * float(trade["allocation"])
        )
    long_contribution = float(
        returns.loc[weights.gt(0.0)].sum()
    )
    short_contribution = float(
        returns.loc[weights.lt(0.0)].sum()
    )
    turnover = (
        float(2.0 * trades["allocation"].sum())
        if not trades.empty
        else 0.0
    )
    metrics = compute_metrics(
        equity,
        returns,
        weights,
        trades,
        turnover,
        float(result.metrics.get("trading_costs_pct", 0.0)) / 100.0,
        0.0,
        float(result.metrics.get("funding_pnl_pct", 0.0)) / 100.0,
        long_contribution,
        short_contribution,
    )
    return RunResult(
        name=result.name,
        metrics=metrics,
        equity=equity,
        returns=returns,
        weights=weights,
        trades=trades,
        actions=pd.DataFrame(),
        state=pd.DataFrame(index=equity.index),
    )


def run_ablations(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, pd.DataFrame],
    windows: FeatureWindows,
    config: StrategyConfig,
) -> dict[str, RunResult]:
    variants = (
        replace(VARIANTS[2], name="full_no_jump", jump_adjustment=False, jump_gate=False),
        replace(VARIANTS[2], name="full_no_extension", extension_gate=False),
        replace(VARIANTS[2], name="full_no_recovery_add", recovery_add=False),
        replace(VARIANTS[2], name="full_no_score_decay", score_decay_exit=False),
        replace(VARIANTS[2], name="full_no_staging", staged_position=False),
    )
    return {
        variant.name: run_cost_ladder(
            frame,
            funding,
            features,
            windows,
            config,
            variant,
        )["net"]
        for variant in variants
    }


def run_walk_forward(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, pd.DataFrame],
    windows: FeatureWindows,
    config: StrategyConfig,
    variants: Iterable[Variant],
) -> dict[str, Any]:
    del windows
    start = frame.index.min() + pd.Timedelta(days=180)
    end = frame.index.max()
    folds: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = start
    while cursor < end:
        fold_end = min(cursor + pd.Timedelta(days=60) - pd.Timedelta(minutes=15), end)
        if fold_end > cursor:
            folds.append((cursor, fold_end))
        cursor += pd.Timedelta(days=60)

    output: dict[str, Any] = {
        "contract": {
            "initial_context_days": 180,
            "test_days": 60,
            "step_days": 60,
            "overlapping_tests": False,
            "parameter_selection": "none; fixed predeclared config in every fold",
            "feature_calibration": "trailing-only rolling scaling; no test labels",
        },
        "variants": {},
    }
    for variant in variants:
        state = build_state(frame, features, config, variant)
        rows: list[dict[str, Any]] = []
        stitched_returns: list[pd.Series] = []
        for fold_id, (fold_start, fold_end) in enumerate(folds, start=1):
            run = simulate(
                name=f"{variant.name}_wf_{fold_id}",
                frame=frame,
                funding=funding,
                state=state,
                features=features,
                config=config,
                variant=variant,
                fee_per_fill=config.fee_per_fill,
                slippage_per_fill=config.slippage_per_fill,
                include_funding=True,
                active_start=fold_start,
                active_end=fold_end,
            )
            rows.append(
                {
                    "fold": fold_id,
                    "test_start": fold_start.isoformat(),
                    "test_end": fold_end.isoformat(),
                    **run.metrics,
                }
            )
            stitched_returns.append(run.returns)
        combined = combine_fold_returns(stitched_returns)
        output["variants"][variant.name] = {
            "folds": rows,
            "combined": combined,
            "positive_fold_ratio": (
                round(
                    sum(row["total_return_pct"] > 0.0 for row in rows) / len(rows),
                    4,
                )
                if rows
                else 0.0
            ),
        }
    return output


def combine_fold_returns(returns_list: list[pd.Series]) -> dict[str, Any]:
    if not returns_list:
        return empty_metrics()
    combined_returns = pd.concat(returns_list).sort_index()
    combined_returns = combined_returns[
        ~combined_returns.index.duplicated(keep="last")
    ]
    equity = (1.0 + combined_returns).cumprod()
    weights = pd.Series(0.0, index=equity.index)
    return compute_metrics(
        equity,
        combined_returns,
        weights,
        pd.DataFrame(),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )


def run_threshold_stability(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, pd.DataFrame],
    windows: FeatureWindows,
    config: StrategyConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del windows
    variant = VARIANTS[2]
    rows: list[dict[str, Any]] = []
    for regime in (0.14, 0.18, 0.22):
        for confirm in (0.20, 0.24, 0.28):
            for trail in (3.5, 4.0, 4.5):
                candidate = replace(
                    config,
                    regime_threshold=regime,
                    confirm_threshold=confirm,
                    mature_threshold=confirm + 0.14,
                    trail_atr=trail,
                )
                state = build_state(frame, features, candidate, variant)
                run = simulate(
                    name=f"stability_r{regime}_c{confirm}_t{trail}",
                    frame=frame,
                    funding=funding,
                    state=state,
                    features=features,
                    config=candidate,
                    variant=variant,
                    fee_per_fill=candidate.fee_per_fill,
                    slippage_per_fill=candidate.slippage_per_fill,
                    include_funding=True,
                )
                rows.append(
                    {
                        "regime_threshold": regime,
                        "confirm_threshold": confirm,
                        "trail_atr": trail,
                        "extension_atr": config.extension_atr,
                        **run.metrics,
                    }
                )
    grid = pd.DataFrame(rows)
    heatmap = (
        grid.groupby(
            ["regime_threshold", "confirm_threshold"],
            as_index=False,
        )
        .agg(
            median_cagr_pct=("cagr_pct", "median"),
            min_cagr_pct=("cagr_pct", "min"),
            median_calmar=("calmar", "median"),
            min_calmar=("calmar", "min"),
            positive_fraction=("total_return_pct", lambda s: float((s > 0.0).mean())),
            median_trades=("trades", "median"),
        )
        .to_dict(orient="records")
    )
    return rows, heatmap


def scaled_windows(base: FeatureWindows, scale: float) -> FeatureWindows:
    def scale_tuple(values: tuple[int, int, int]) -> tuple[int, int, int]:
        return tuple(max(2, int(round(value * scale))) for value in values)  # type: ignore[return-value]

    return FeatureWindows(
        h1_momentum=scale_tuple(base.h1_momentum),
        h4_momentum=scale_tuple(base.h4_momentum),
        h1_er=max(4, int(round(base.h1_er * scale))),
        h4_er=max(4, int(round(base.h4_er * scale))),
        h1_donchian=max(8, int(round(base.h1_donchian * scale))),
        h4_donchian=max(6, int(round(base.h4_donchian * scale))),
        h1_volume=max(8, int(round(base.h1_volume * scale))),
        h4_volume=max(6, int(round(base.h4_volume * scale))),
        h1_scale=max(240, int(round(base.h1_scale * scale))),
        h4_scale=max(60, int(round(base.h4_scale * scale))),
        slow_ema_h1=max(24, int(round(base.slow_ema_h1 * scale))),
        atr_h1=max(8, int(round(base.atr_h1 * scale))),
        vol_target_m15=max(32, int(round(base.vol_target_m15 * scale))),
    )


def run_window_stability(
    frame: pd.DataFrame,
    funding: pd.Series,
    base_windows: FeatureWindows,
    config: StrategyConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, scale in (("shorter_0.8x", 0.8), ("base_1.0x", 1.0), ("longer_1.2x", 1.2)):
        windows = scaled_windows(base_windows, scale)
        features = build_feature_set(frame, windows)
        run = run_cost_ladder(
            frame,
            funding,
            features,
            windows,
            config,
            VARIANTS[2],
        )["net"]
        rows.append(
            {
                "window_variant": label,
                "scale": scale,
                "windows": asdict(windows),
                **run.metrics,
            }
        )
    return rows


def score_monotonicity(h1_features: pd.DataFrame, horizon: int = 24) -> dict[str, Any]:
    score = h1_features["price_volume_score_jump"]
    valid_score = score.dropna()
    # Reconstruct prices from score input is intentionally impossible here; caller
    # adds close before this function when needed.
    if "_close" not in h1_features.columns:
        return {
            "status": "BLOCKED",
            "reason": "h1 feature frame missing retained close used only for label audit",
        }
    close = h1_features["_close"]
    future_return = close.shift(-horizon) / close - 1.0
    future_paths = pd.concat(
        [close.shift(-step) / close - 1.0 for step in range(1, horizon + 1)],
        axis=1,
    )
    signed_direction = np.sign(score).replace(0.0, np.nan)
    directional_return = signed_direction * future_return
    directional_paths = future_paths.mul(signed_direction, axis=0)
    magnitude = score.abs()
    valid = (
        valid_score.index
        .intersection(future_return.dropna().index)
        .intersection(magnitude.dropna().index)
    )
    signed_bins = pd.qcut(
        score.loc[valid],
        q=5,
        labels=False,
        duplicates="drop",
    )
    magnitude_bins = pd.qcut(
        magnitude.loc[valid],
        q=5,
        labels=False,
        duplicates="drop",
    )
    signed_rows: list[dict[str, Any]] = []
    magnitude_rows: list[dict[str, Any]] = []
    for bucket in sorted(pd.Series(signed_bins).dropna().unique()):
        mask = signed_bins.eq(bucket)
        selected = valid[mask.to_numpy()]
        signed_rows.append(
            {
                "quintile": int(bucket) + 1,
                "count": int(len(selected)),
                "score_mean": float(score.loc[selected].mean()),
                "future_return_mean_pct": float(future_return.loc[selected].mean() * 100.0),
                "future_return_median_pct": float(future_return.loc[selected].median() * 100.0),
            }
        )
    for bucket in sorted(pd.Series(magnitude_bins).dropna().unique()):
        mask = magnitude_bins.eq(bucket)
        selected = valid[mask.to_numpy()]
        paths = directional_paths.loc[selected]
        magnitude_rows.append(
            {
                "quintile": int(bucket) + 1,
                "count": int(len(selected)),
                "abs_score_mean": float(magnitude.loc[selected].mean()),
                "directional_return_mean_pct": float(
                    directional_return.loc[selected].mean() * 100.0
                ),
                "mfe_mean_pct": float(paths.max(axis=1).mean() * 100.0),
                "mae_mean_pct": float(paths.min(axis=1).mean() * 100.0),
            }
        )
    signed_means = [row["future_return_mean_pct"] for row in signed_rows]
    directional_means = [
        row["directional_return_mean_pct"] for row in magnitude_rows
    ]
    return {
        "status": "PASS",
        "horizon_hours": horizon,
        "signed_score_quintiles": signed_rows,
        "absolute_score_quintiles": magnitude_rows,
        "signed_future_return_monotone": bool(
            all(left <= right for left, right in zip(signed_means, signed_means[1:]))
        ),
        "conviction_directional_return_monotone": bool(
            all(
                left <= right
                for left, right in zip(directional_means, directional_means[1:])
            )
        ),
        "note": "Labels are constructed after features and are never read by the strategy.",
    }


def run_cross_asset_transfer(
    warehouse: DuckDBWarehouse,
    windows: FeatureWindows,
    config: StrategyConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    quality: dict[str, Any] = {}
    for symbol in TRANSFER_SYMBOLS:
        frame, funding, symbol_quality = load_symbol_data(
            warehouse,
            symbol,
            require_raw_parity=False,
        )
        features = build_feature_set(frame, windows)
        # Retain close only inside the analysis copy used by monotonicity.
        features["h1_native"]["_close"] = resample_ohlcv(frame, "1h")["close"]
        run = run_cost_ladder(
            frame,
            funding,
            features,
            windows,
            config,
            VARIANTS[2],
        )["net"]
        oos_start = frame.index.min() + pd.Timedelta(days=180)
        oos_equity = run.equity.loc[run.equity.index >= oos_start]
        oos_returns = run.returns.reindex(oos_equity.index)
        oos_weights = run.weights.reindex(oos_equity.index)
        oos_trades = (
            run.trades.loc[
                pd.to_datetime(run.trades["entry_ts"], utc=True).ge(oos_start)
            ].copy()
            if not run.trades.empty
            else pd.DataFrame()
        )
        oos_metrics = (
            compute_metrics(
                oos_equity / float(oos_equity.iloc[0]),
                oos_returns,
                oos_weights,
                oos_trades,
                0.0,
                0.0,
                0.0,
                0.0,
                float(oos_returns.loc[oos_weights.gt(0.0)].sum()),
                float(oos_returns.loc[oos_weights.lt(0.0)].sum()),
            )
            if not oos_equity.empty
            else empty_metrics()
        )
        rows.append(
            {
                "symbol": symbol,
                "data_start": frame.index.min().isoformat(),
                "data_end": frame.index.max().isoformat(),
                "evidence_status": symbol_quality["evidence_status"],
                "full": run.metrics,
                "post_180d": oos_metrics,
            }
        )
        quality[symbol] = symbol_quality
    return rows, quality


def period_metrics(run: RunResult, period: str) -> list[dict[str, Any]]:
    if run.equity.empty:
        return []
    if period != "year":
        raise ValueError("only year period is supported")
    rows: list[dict[str, Any]] = []
    for year, equity in run.equity.groupby(run.equity.index.year):
        normalized = equity / float(equity.iloc[0])
        returns = run.returns.reindex(equity.index)
        drawdown = normalized / normalized.cummax() - 1.0
        trades = (
            run.trades.loc[
                pd.to_datetime(run.trades["entry_ts"], utc=True).dt.year.eq(year)
            ]
            if not run.trades.empty
            else pd.DataFrame()
        )
        rows.append(
            {
                "year": int(year),
                "start": equity.index.min().isoformat(),
                "end": equity.index.max().isoformat(),
                "return_pct": float((normalized.iloc[-1] - 1.0) * 100.0),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
                "sharpe": (
                    0.0
                    if float(returns.std(ddof=0)) == 0.0
                    else float(
                        returns.mean()
                        / returns.std(ddof=0)
                        * math.sqrt(M15_PER_YEAR)
                    )
                ),
                "trades": int(len(trades)),
            }
        )
    return rows


def market_state_metrics(run: RunResult) -> list[dict[str, Any]]:
    if run.state.empty:
        return []
    rows: list[dict[str, Any]] = []
    labels = run.state["regime_label"].dropna().unique()
    for label in labels:
        mask = run.state["regime_label"].eq(label)
        selected_returns = run.returns.loc[mask]
        contribution = float(selected_returns.sum())
        volatility = float(selected_returns.std(ddof=0))
        rows.append(
            {
                "market_state": str(label),
                "bars": int(mask.sum()),
                "return_contribution_pct": contribution * 100.0,
                "mean_bar_return_bps": float(selected_returns.mean() * 10000.0),
                "sharpe": (
                    0.0
                    if volatility == 0.0
                    else float(
                        selected_returns.mean()
                        / volatility
                        * math.sqrt(M15_PER_YEAR)
                    )
                ),
            }
        )
    return rows


def recent_slices(run: RunResult) -> list[dict[str, Any]]:
    if run.equity.empty:
        return []
    end = run.equity.index.max()
    windows: dict[str, pd.Timedelta | None] = {
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
        start = run.equity.index.min() if delta is None else end - delta
        equity = run.equity.loc[run.equity.index >= start]
        if equity.empty:
            continue
        normalized = equity / float(equity.iloc[0])
        drawdown = normalized / normalized.cummax() - 1.0
        trades = (
            run.trades.loc[
                pd.to_datetime(run.trades["entry_ts"], utc=True).ge(
                    equity.index.min()
                )
            ]
            if not run.trades.empty
            else pd.DataFrame()
        )
        rows.append(
            {
                "window": label,
                "start": equity.index.min().isoformat(),
                "end": equity.index.max().isoformat(),
                "return_pct": float((normalized.iloc[-1] - 1.0) * 100.0),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
                "trades": int(len(trades)),
            }
        )
    return rows


def build_main_comparison(
    v35_runs: dict[str, RunResult],
    main_runs: dict[str, dict[str, RunResult]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "variant": "V35 canonical 8.5bps",
            "cost_scenario": "canonical_legacy_net",
            **v35_runs["canonical_legacy_net"].metrics,
        },
        {
            "variant": "V35 standard 14bps",
            "cost_scenario": "standard_net",
            **v35_runs["standard_net"].metrics,
        },
    ]
    for name, scenarios in main_runs.items():
        rows.append(
            {
                "variant": name,
                "cost_scenario": "net",
                **scenarios["net"].metrics,
            }
        )
    return rows


def write_main_csvs(
    v35_runs: dict[str, RunResult],
    main_runs: dict[str, dict[str, RunResult]],
    ablations: dict[str, RunResult],
    stability_rows: list[dict[str, Any]],
    heatmap_rows: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    transfer_rows: list[dict[str, Any]],
    monotonicity: dict[str, Any],
) -> None:
    metrics_rows: list[dict[str, Any]] = []
    for name, run in v35_runs.items():
        metrics_rows.append({"family": "V35", "variant": name, **run.metrics})
    for variant, scenarios in main_runs.items():
        for scenario, run in scenarios.items():
            metrics_rows.append(
                {
                    "family": FAMILY,
                    "variant": variant,
                    "cost_scenario": scenario,
                    **run.metrics,
                }
            )
    for name, run in ablations.items():
        metrics_rows.append(
            {
                "family": FAMILY,
                "variant": name,
                "cost_scenario": "net",
                **run.metrics,
            }
        )
    pd.DataFrame(metrics_rows).to_csv(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_metrics_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(stability_rows).to_csv(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_parameter_stability_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(heatmap_rows).to_csv(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_stability_heatmap_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(window_rows).to_csv(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_window_stability_{RUN_DATE}.csv",
        index=False,
    )
    pd.json_normalize(transfer_rows, sep=".").to_csv(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_cross_asset_{RUN_DATE}.csv",
        index=False,
    )
    for key in ("signed_score_quintiles", "absolute_score_quintiles"):
        if key in monotonicity:
            pd.DataFrame(monotonicity[key]).to_csv(
                ARTIFACT_DIR / f"hype_15m_mdtp_v1_{key}_{RUN_DATE}.csv",
                index=False,
            )
    trade_frames: list[pd.DataFrame] = []
    action_frames: list[pd.DataFrame] = []
    equity_frames: list[pd.DataFrame] = []
    for variant, scenarios in main_runs.items():
        run = scenarios["net"]
        if not run.trades.empty:
            trades = run.trades.copy()
            trades.insert(0, "variant", variant)
            trade_frames.append(trades)
        if not run.actions.empty:
            actions = run.actions.copy()
            actions.insert(0, "variant", variant)
            action_frames.append(actions)
        equity_frames.append(run.equity.rename(variant).to_frame())
    if trade_frames:
        pd.concat(trade_frames, ignore_index=True).to_csv(
            ARTIFACT_DIR / f"hype_15m_mdtp_v1_trades_{RUN_DATE}.csv",
            index=False,
        )
    if action_frames:
        pd.concat(action_frames, ignore_index=True).to_csv(
            ARTIFACT_DIR / f"hype_15m_mdtp_v1_actions_{RUN_DATE}.csv",
            index=False,
        )
    pd.concat(equity_frames, axis=1).to_csv(
        ARTIFACT_DIR / f"hype_15m_mdtp_v1_equity_{RUN_DATE}.csv",
        index_label="ts",
    )


def write_report(payload: dict[str, Any]) -> None:
    comparison = pd.DataFrame(payload["comparison"])
    walk = payload["walk_forward"]["variants"]
    ablations = pd.DataFrame(
        [
            {"variant": name, **metrics}
            for name, metrics in payload["ablations"].items()
        ]
    )
    window_rows = pd.DataFrame(
        payload["parameter_stability"]["adjacent_windows"]
    )
    transfer = payload["cross_asset_transfer"]
    monotonicity = payload["score_monotonicity"]
    primary = payload["data_contract"]["primary"]

    comparison_table = markdown_table(
        comparison[
            [
                "variant",
                "total_return_pct",
                "cagr_pct",
                "sharpe",
                "sortino",
                "max_drawdown_pct",
                "calmar",
                "trades",
                "win_rate_pct",
                "payoff_ratio",
                "profit_factor",
                "avg_hold_hours",
                "turnover_annualized",
                "long_return_contribution_pct",
                "short_return_contribution_pct",
            ]
        ]
    )
    ablation_table = markdown_table(
        ablations[
            [
                "variant",
                "total_return_pct",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
                "calmar",
                "trades",
                "turnover_annualized",
            ]
        ]
    )
    window_table = markdown_table(
        window_rows[
            [
                "window_variant",
                "total_return_pct",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
                "calmar",
                "trades",
            ]
        ]
    )
    transfer_table = markdown_table(
        pd.DataFrame(
            [
                {
                    "symbol": row["symbol"],
                    "evidence_status": row["evidence_status"],
                    "full_return_pct": row["full"]["total_return_pct"],
                    "full_mdd_pct": row["full"]["max_drawdown_pct"],
                    "full_sharpe": row["full"]["sharpe"],
                    "full_trades": row["full"]["trades"],
                    "post180_return_pct": row["post_180d"]["total_return_pct"],
                    "post180_mdd_pct": row["post_180d"]["max_drawdown_pct"],
                    "post180_sharpe": row["post_180d"]["sharpe"],
                    "post180_trades": row["post_180d"]["trades"],
                }
                for row in transfer
            ]
        )
    )
    wf_rows = []
    for name, data in walk.items():
        wf_rows.append(
            {
                "variant": name,
                "positive_fold_ratio": data["positive_fold_ratio"],
                **data["combined"],
            }
        )
    wf_table = markdown_table(
        pd.DataFrame(wf_rows)[
            [
                "variant",
                "positive_fold_ratio",
                "total_return_pct",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
                "calmar",
            ]
        ]
    )
    signed_table = markdown_table(
        pd.DataFrame(monotonicity.get("signed_score_quintiles", []))
    )
    magnitude_table = markdown_table(
        pd.DataFrame(monotonicity.get("absolute_score_quintiles", []))
    )
    full_metrics = next(
        row for row in payload["comparison"] if row["variant"] == "full"
    )
    v35_metrics = next(
        row
        for row in payload["comparison"]
        if row["variant"] == "V35 standard 14bps"
    )
    decision = decide(full_metrics, v35_metrics, walk["full"], transfer)
    report = f"""# {FAMILY} V1 初始研究与回测

## 结论

**{decision["status"]}**。{decision["summary"]}

- 相对标准成本 V35：净总收益差 `{full_metrics["total_return_pct"] - v35_metrics["total_return_pct"]:+.2f}pp`，Sharpe 差 `{full_metrics["sharpe"] - v35_metrics["sharpe"]:+.2f}`，最大回撤差 `{full_metrics["max_drawdown_pct"] - v35_metrics["max_drawdown_pct"]:+.2f}pp`。
- 滚动历史伪 OOS：full 版本正收益 fold 比例 `{walk["full"]["positive_fold_ratio"]:.2%}`；这是严格时间顺序但不是未揭示 prospective OOS。
- 纸面交易判断：{decision["paper"]}

## 数据与 V35 冻结对照

- 主数据：Binance USD-M `HYPE/USDT:USDT` `15m`，`{primary["start"]}` 至 `{primary["end"]}`，`{primary["rows"]}` 根已闭合 K。
- 数据质量：缺口 `{primary["missing_15m_bars"]}`、重复 `{primary["duplicate_ts_before_dedup"]}`、无效 OHLCV `{primary["invalid_ohlcv_rows"]}`；raw/normalized 全字段逐行对齐 `{primary["raw_vs_normalized"]["accepted"]}`。
- V35 当前逻辑：15m EMA96/384 定方向，ADX28 与 192 根量能过滤，上一根完整 1h ADX/DI 或 EMA 确认；K0 收盘信号、跳过 K1、K2 open 入场；ATR672 波动率仓位，long target `2.0%`、short target `1.8%`、cap `3x`；固定 `TP5ATR / SL7ATR`；ADX<22 连续 3 根时下一根 open 退出，MFE>=1.5ATR 后关闭指标退出；384 根 timeout；无固定冷却。
- V35 历史成本：每次 fill 合并 `8.5bps` + funding。公平对照另跑仓库当前 Binance 标准成本：手续费 `10bps` + adverse slippage `4bps` 每次 fill + funding。
- 新分支没有继承 V35 身份、参数或 promotion 状态。

## 新框架

- 4h：多周期波动率标准化收益、Signed Kaufman ER、Donchian 位置、方向成交量失衡、signed RVOL 等权形成方向分数；绝对分数低于阈值时空仓。
- 1h：同构分数识别萌芽、确认、成熟与缩量回调后的恢复；所有 1h/4h 特征只在完整高周期 K 结束后可见。
- 15m：上一根 15m 收盘生成目标，下一根 open 调仓。趋势分数决定方向和阶段仓位，15m 实现波动率控制实际 allocation。
- 只对盈利 campaign 加仓；过度延伸或 jump concentration 过高时禁止增加仓位，减仓与退出不受阻。
- 退出：ATR trailing、慢速 1h Donchian、4h regime 反转/空档或趋势分数衰减；无固定止盈。

## 四组主对照

{comparison_table}

`V35 canonical` 仅用于历史复现；策略优劣判断使用同为 `10bps fee + 4bps slippage + funding` 的 V35 standard 与三个新版本。

## 成本拆分

完整 gross / fee-only / fee+slippage / net 结果见 [JSON](../artifacts/hype_15m_mdtp_v1_research_{RUN_DATE}.json) 与 [metrics CSV](../artifacts/hype_15m_mdtp_v1_metrics_{RUN_DATE}.csv)。拆分使用顺序反事实，因费用会改变复利路径，各项差值不应机械相加。

## 严格时间顺序滚动测试

- 初始上下文 180 天；随后每 60 天一个不重叠 test fold；固定参数，fold 内不选参。
- 所有标准化仅使用当时之前的滚动数据；MFE/MAE/未来收益标签只在事后诊断生成。
- 由于仓库此前已研究过 HYPE 同一历史，以下只能称 chronological pseudo-OOS，不能称 prospective OOS。

{wf_table}

## 模块消融

{ablation_table}

模块有效性由相对 full 的收益、回撤、Sharpe、Calmar、换手共同判断；单一收益提升不自动视为有效。

## 参数与窗口稳定性

阈值网格覆盖 regime `0.14/0.18/0.22`、confirm `0.20/0.24/0.28`、ATR trail `3.5/4.0/4.5`，extension 固定为预声明的 `2.5ATR`，共 27 行；未从中挑选替代默认参数。完整网格见 [CSV](../artifacts/hype_15m_mdtp_v1_parameter_stability_{RUN_DATE}.csv)，二维稳定区汇总见 [heatmap CSV](../artifacts/hype_15m_mdtp_v1_stability_heatmap_{RUN_DATE}.csv)。

相邻窗口：

{window_table}

## 趋势分数单调性

Signed score 五分组（未来 24h 原始收益应随分数上升）：

{signed_table}

绝对强度五分组（按分数方向计算未来 24h 净方向收益、MFE、MAE）：

{magnitude_table}

- signed future return 单调：`{monotonicity.get("signed_future_return_monotone")}`。
- conviction directional return 单调：`{monotonicity.get("conviction_directional_return_monotone")}`。

## 跨币种固定参数迁移

以下全部直接使用 HYPE V1 固定参数，没有按币种调参。`post180` 仅表示每个币种前 180 天作为历史上下文后的时间段，不是未揭示 prospective OOS。若 raw loader/schema 不能完成 raw-normalized parity，该币种结果标记为 `explore / untrusted`，不得用于 promotion。

{transfer_table}

## 年份、市场状态与近期分片

逐版本的 `2025/2026`、strong-up/strong-down/range/transition，以及最近 `1d/7d/1m/3m/6m/1y` 明细保存在 [JSON](../artifacts/hype_15m_mdtp_v1_research_{RUN_DATE}.json)。HYPE 历史只有约 14 个月，不足以证明跨年度稳定。

## 改善来源与限制

{chr(10).join(f"- {item}" for item in decision["drivers"])}

限制：

{chr(10).join(f"- {item}" for item in payload["limitations"])}

## 证据

- [完整结果 JSON](../artifacts/hype_15m_mdtp_v1_research_{RUN_DATE}.json)
- [主指标 CSV](../artifacts/hype_15m_mdtp_v1_metrics_{RUN_DATE}.csv)
- [交易明细](../artifacts/hype_15m_mdtp_v1_trades_{RUN_DATE}.csv)
- [调仓动作](../artifacts/hype_15m_mdtp_v1_actions_{RUN_DATE}.csv)
- [权益曲线](../artifacts/hype_15m_mdtp_v1_equity_{RUN_DATE}.csv)
- [参数稳定性](../artifacts/hype_15m_mdtp_v1_parameter_stability_{RUN_DATE}.csv)
- [相邻窗口](../artifacts/hype_15m_mdtp_v1_window_stability_{RUN_DATE}.csv)
- [跨币种](../artifacts/hype_15m_mdtp_v1_cross_asset_{RUN_DATE}.csv)
- [复现脚本](../scripts/research_hype_15m_mdtp.py)
"""
    (ROOT / "diagnostics").mkdir(parents=True, exist_ok=True)
    (ROOT / "diagnostics" / f"hype-15m-mdtp-v1-initial-research-{RUN_DATE}.md").write_text(
        report,
        encoding="utf-8",
    )


def decide(
    full: dict[str, Any],
    v35: dict[str, Any],
    walk: dict[str, Any],
    transfer: list[dict[str, Any]],
) -> dict[str, Any]:
    improves_risk_adjusted = (
        full["sharpe"] > v35["sharpe"]
        and full["max_drawdown_pct"] >= v35["max_drawdown_pct"]
        and full["calmar"] > v35["calmar"]
    )
    fold_ok = walk["positive_fold_ratio"] >= 0.60
    accepted_transfer = [
        row for row in transfer if row.get("evidence_status") == "accepted"
    ]
    transfer_positive = sum(
        row["post_180d"]["total_return_pct"] > 0.0 for row in accepted_transfer
    )
    transfer_ok = (
        len(accepted_transfer) >= 3
        and transfer_positive
        >= max(3, math.ceil(len(accepted_transfer) * 0.6))
    )
    status = "PAPER-WATCH / NOT PROMOTED" if improves_risk_adjusted and fold_ok else "NO-GO / NOT PROMOTED"
    paper = (
        "可进入只记录信号、不下单的 prospective paper-watch；必须从当前数据末端开始冻结。"
        if improves_risk_adjusted and fold_ok and transfer_ok
        else "不值得进入带资金纸面仿真；最多保留为机制诊断，先修复失败门禁。"
    )
    drivers = [
        (
            "风险调整后改善门禁通过：full 同时提高 Sharpe/Calmar 且不加深回撤。"
            if improves_risk_adjusted
            else "风险调整后改善门禁失败：full 未能同时提高 Sharpe、Calmar 并控制回撤。"
        ),
        (
            f"滚动 fold 稳定性：正收益比例 {walk['positive_fold_ratio']:.2%}。"
        ),
        (
            f"可采信跨币种 post-180d 正收益 {transfer_positive}/{len(accepted_transfer)}；固定参数迁移"
            + ("支持" if transfer_ok else "不支持")
            + "普适性。"
        ),
        "jump、extension、recovery、staging 与 score-decay 的独立作用以消融表为准；不因理论好看而保留。",
    ]
    return {
        "status": status,
        "paper": paper,
        "drivers": drivers,
        "summary": (
            "完整版本通过了风险调整后改善与时间折叠门禁，但历史并非真正未揭示样本。"
            if improves_risk_adjusted and fold_ok
            else "完整版本没有在公平成本与时间折叠下证明相对 V35 的真实改善。"
        ),
    }


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_无可用数据_"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else f"{value:.4f}"
            )
    headers = [str(column) for column in display.columns]
    rows = [
        [str(value) for value in row]
        for row in display.itertuples(index=False, name=None)
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )


def json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialize {type(value)!r}")


def print_summary(payload: dict[str, Any]) -> None:
    print(f"{payload['family']} {payload['strategy_id']}")
    print(
        f"data {payload['data_contract']['primary']['start']} -> "
        f"{payload['data_contract']['primary']['end']} "
        f"rows={payload['data_contract']['primary']['rows']}"
    )
    for row in payload["comparison"]:
        print(
            f"{row['variant']:>24} "
            f"return={row['total_return_pct']:>10.2f}% "
            f"cagr={row['cagr_pct']:>9.2f}% "
            f"dd={row['max_drawdown_pct']:>8.2f}% "
            f"sharpe={row['sharpe']:>6.2f} "
            f"trades={row['trades']:>4}"
        )


if __name__ == "__main__":
    main()
