from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    ExitSpec,
    FilterSpec,
    SearchResult,
    SignalSpec,
    add_features,
    build_market_arrays,
    ema_pairs,
    evaluate_trades,
    load_data,
    passes_filter,
    pct_slug,
    selected_trades,
    signal_state,
    simulate_trades,
    value_slug,
)


FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
ABLATIONS_DIR = FAMILY_DIR / "ablations"
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_full_ablation.py"

SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_full_ablation_2026-06-26.json"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_full_ablation_summary_2026-06-26.csv"
VALIDATION_SLICES_CSV_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_full_ablation_validation_slices_2026-06-26.csv"
)
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_full_ablation_rolling_2026-06-26.csv"
WEEKLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_full_ablation_weekly_2026-06-26.csv"
MONTHLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_full_ablation_monthly_2026-06-26.csv"
MARKDOWN_PATH = ABLATIONS_DIR / "hype-15m-mii-full-ablation-2026-06-26.md"

CACHE_PATH = Path("data/cache/hypeusdt_15m_fapi.csv")
TIMEFRAME_MINUTES = 15


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    strategy_name: str
    signal: SignalSpec
    exit: ExitSpec
    filter: FilterSpec
    exposure: float


@dataclass(frozen=True, slots=True)
class VariantSpec:
    label: str
    family: str
    parameter: str
    value: Any
    config: StrategyConfig


BASELINE = StrategyConfig(
    strategy_name=(
        "HYPE_15M_MII_rsi_reversal_w7_lo30_hi60_"
        "fixed_tp90p0_sl280p0_hold16_macd0p0_atr60p0to280p0_x1p5"
    ),
    signal=SignalSpec(
        name="rsi_reversal_w7_lo30_hi60",
        kind="rsi_reversal",
        window=7,
        low=30.0,
        high=60.0,
    ),
    exit=ExitSpec(
        kind="fixed",
        take_profit_pct=0.009,
        stop_pct=0.028,
        max_hold_bars=16,
    ),
    filter=FilterSpec(
        min_dir_macd=0.0,
        min_atr_pct96=0.006,
        max_atr_pct96=0.028,
    ),
    exposure=1.5,
)


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "m").replace("/", "_").replace(" ", "")


def rsi_signal(window: int, low: float, high: float) -> SignalSpec:
    return SignalSpec(
        name=f"rsi_reversal_w{window}_lo{value_slug(low)}_hi{value_slug(high)}",
        kind="rsi_reversal",
        window=window,
        low=low,
        high=high,
    )


def bb_signal(kind: str, window: int, k: float) -> SignalSpec:
    return SignalSpec(
        name=f"{kind}_w{window}_k{value_slug(k)}",
        kind=kind,
        window=window,
        k=k,
    )


def ema_signal(fast: int, slow: int) -> SignalSpec:
    return SignalSpec(
        name=f"ema_cross_f{fast}_s{slow}",
        kind="ema_cross",
        fast=fast,
        slow=slow,
    )


def fixed_exit(take_profit_pct: float, stop_pct: float, max_hold_bars: int) -> ExitSpec:
    return ExitSpec(
        kind="fixed",
        take_profit_pct=take_profit_pct,
        stop_pct=stop_pct,
        max_hold_bars=max_hold_bars,
    )


def trailing_exit(
    activation_pct: float,
    trail_pct: float,
    stop_pct: float,
    max_hold_bars: int,
) -> ExitSpec:
    return ExitSpec(
        kind="trailing",
        activation_pct=activation_pct,
        trail_pct=trail_pct,
        stop_pct=stop_pct,
        max_hold_bars=max_hold_bars,
    )


def filter_with(**changes: Any) -> FilterSpec:
    values = asdict(BASELINE.filter)
    values.update(changes)
    return FilterSpec(**values)


def config_with(
    *,
    signal: SignalSpec | None = None,
    exit_spec: ExitSpec | None = None,
    filter_spec: FilterSpec | None = None,
    exposure: float | None = None,
) -> StrategyConfig:
    return StrategyConfig(
        strategy_name=BASELINE.strategy_name,
        signal=signal or BASELINE.signal,
        exit=exit_spec or BASELINE.exit,
        filter=filter_spec or BASELINE.filter,
        exposure=BASELINE.exposure if exposure is None else exposure,
    )


def add_variant(
    variants: list[VariantSpec],
    *,
    parameter: str,
    value: Any,
    family: str,
    config: StrategyConfig,
) -> None:
    variants.append(
        VariantSpec(
            label=f"{parameter}_{label_value(value)}",
            family=family,
            parameter=parameter,
            value=value,
            config=config,
        )
    )


def build_variants() -> list[VariantSpec]:
    variants = [
        VariantSpec(
            label="baseline",
            family="baseline",
            parameter="baseline",
            value="search_best",
            config=BASELINE,
        )
    ]

    for value in (14, 21):
        add_variant(
            variants,
            parameter="rsi_window",
            value=value,
            family="signal",
            config=config_with(signal=rsi_signal(value, BASELINE.signal.low, BASELINE.signal.high)),
        )
    for value in (20.0, 40.0):
        add_variant(
            variants,
            parameter="rsi_low",
            value=value,
            family="signal",
            config=config_with(signal=rsi_signal(BASELINE.signal.window, value, BASELINE.signal.high)),
        )
    for value in (70.0, 80.0):
        add_variant(
            variants,
            parameter="rsi_high",
            value=value,
            family="signal",
            config=config_with(signal=rsi_signal(BASELINE.signal.window, BASELINE.signal.low, value)),
        )

    for signal in (
        bb_signal("bb_reversion", 48, 1.5),
        bb_signal("bb_breakout", 96, 2.5),
        ema_signal(89, 377),
    ):
        add_variant(
            variants,
            parameter="signal_family_probe",
            value=signal.name,
            family="signal_replacement_probe",
            config=config_with(signal=signal),
        )

    for value in (0.004, 0.006, 0.012, 0.018, 0.026):
        add_variant(
            variants,
            parameter="take_profit_pct",
            value=value,
            family="exit",
            config=config_with(
                exit_spec=fixed_exit(value, BASELINE.exit.stop_pct, BASELINE.exit.max_hold_bars)
            ),
        )
    for value in (0.0035, 0.005, 0.008, 0.012, 0.018):
        add_variant(
            variants,
            parameter="stop_pct",
            value=value,
            family="exit",
            config=config_with(
                exit_spec=fixed_exit(BASELINE.exit.take_profit_pct or 0.0, value, BASELINE.exit.max_hold_bars)
            ),
        )
    for value in (4, 8, 32, 64):
        add_variant(
            variants,
            parameter="max_hold_bars",
            value=value,
            family="exit",
            config=config_with(
                exit_spec=fixed_exit(BASELINE.exit.take_profit_pct or 0.0, BASELINE.exit.stop_pct, value)
            ),
        )
    for activation, trail in ((0.01, 0.005), (0.024, 0.005), (0.04, 0.012)):
        add_variant(
            variants,
            parameter="exit_family_probe",
            value=f"trail_act{pct_slug(activation)}_trail{pct_slug(trail)}",
            family="exit_replacement_probe",
            config=config_with(
                exit_spec=trailing_exit(
                    activation,
                    trail,
                    BASELINE.exit.stop_pct,
                    BASELINE.exit.max_hold_bars,
                )
            ),
        )

    add_variant(
        variants,
        parameter="filter_set",
        value="none",
        family="filter",
        config=config_with(filter_spec=FilterSpec()),
    )
    add_variant(
        variants,
        parameter="macd_filter",
        value="removed",
        family="filter",
        config=config_with(filter_spec=filter_with(min_dir_macd=-99.0)),
    )
    add_variant(
        variants,
        parameter="atr_band",
        value="removed",
        family="filter",
        config=config_with(
            filter_spec=filter_with(min_atr_pct96=0.0, max_atr_pct96=99.0)
        ),
    )
    for value in (0.0, 0.0035, 0.009):
        add_variant(
            variants,
            parameter="min_atr_pct96",
            value=value,
            family="filter",
            config=config_with(filter_spec=filter_with(min_atr_pct96=value)),
        )
    for value in (0.035, 0.04, 99.0):
        add_variant(
            variants,
            parameter="max_atr_pct96",
            value=value,
            family="filter",
            config=config_with(filter_spec=filter_with(max_atr_pct96=value)),
        )
    for value in ("long", "short"):
        add_variant(
            variants,
            parameter="side",
            value=value,
            family="filter",
            config=config_with(filter_spec=filter_with(side=value)),
        )
    for value in (16.0, 22.0, 28.0):
        add_variant(
            variants,
            parameter="min_adx14",
            value=value,
            family="added_filter",
            config=config_with(filter_spec=filter_with(min_adx14=value)),
        )
    for value in (0.75, 1.0, 1.3):
        add_variant(
            variants,
            parameter="min_rvol96",
            value=value,
            family="added_filter",
            config=config_with(filter_spec=filter_with(min_rvol96=value)),
        )
    for parameter, value, filter_spec in (
        ("min_h1_dir_spread", 0.0, filter_with(min_h1_dir_spread=0.0)),
        ("min_h4_dir_spread", 0.0, filter_with(min_h4_dir_spread=0.0)),
        ("min_dir_ret48", 0.0, filter_with(min_dir_ret48=0.0)),
        ("max_atr_ratio96_672", 1.6, filter_with(max_atr_ratio96_672=1.6)),
        (
            "dir_rsi14_band",
            "48_to_78",
            filter_with(min_dir_rsi14=48.0, max_dir_rsi14=78.0),
        ),
        ("cooldown_bars", 12, filter_with(cooldown_bars=12)),
    ):
        add_variant(
            variants,
            parameter=parameter,
            value=value,
            family="added_filter",
            config=config_with(filter_spec=filter_spec),
        )

    for value in (0.5, 1.0, 2.0, 2.5, 3.0):
        add_variant(
            variants,
            parameter="exposure",
            value=value,
            family="sizing",
            config=config_with(exposure=value),
        )

    return variants


def json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return str(value)


def data_quality_report(frame: pd.DataFrame) -> dict[str, Any]:
    expected = pd.Timedelta(minutes=TIMEFRAME_MINUTES)
    duplicated_ts = int(frame["ts"].duplicated().sum())
    gaps = frame["ts"].diff().dropna()
    invalid_ohlc = int(
        (
            (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
            | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
            | (frame["volume"] < 0)
        ).sum()
    )
    standard_data_lake_matches = list(
        Path("data/normalized/ohlcv").glob(
            "exchange=binance/market_type=perp/timeframe=15m/**/*HYPE*"
        )
    )
    return {
        "rows": int(len(frame)),
        "first_ts": str(frame["ts"].min()),
        "last_ts": str(frame["ts"].max()),
        "timeframe": "15m",
        "gap_count": int((gaps != expected).sum()),
        "duplicated_ts": duplicated_ts,
        "critical_nulls": int(frame[["ts", "open", "high", "low", "close", "volume"]].isna().sum().sum()),
        "invalid_ohlc_rows": invalid_ohlc,
        "cache_path": str(CACHE_PATH),
        "standard_data_lake_found": bool(standard_data_lake_matches),
        "quote_volume_trade_count_vwap_available": False,
    }


def cache_key(config: StrategyConfig) -> tuple[str, str]:
    return config.signal.name, config.exit.name


def calculate_raw_trades(
    *,
    states: dict[str, Any],
    market: Any,
    config: StrategyConfig,
    raw_trade_cache: dict[tuple[str, str], list[Any]],
) -> list[Any]:
    key = cache_key(config)
    if key not in raw_trade_cache:
        state = states.get(config.signal.name)
        if state is None:
            raise ValueError(f"missing signal state: {config.signal.name}")
        raw_trade_cache[key] = simulate_trades(market, state, config.exit)
    return raw_trade_cache[key]


def evaluate_config(
    *,
    config: StrategyConfig,
    raw_trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> SearchResult | None:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    return evaluate_trades(
        trades=raw_trades,
        filter_spec=config.filter,
        exposure=config.exposure,
        period_days=period_days,
        exit_spec=config.exit,
        start_ts=start_ts,
        end_ts=end_ts,
    )


def empty_slice_metrics(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> dict[str, Any]:
    return {
        "start_ts": str(start_ts),
        "end_ts": str(end_ts),
        "final_equity": 1.0,
        "total_return_pct": 0.0,
        "annual_return_pct": 0.0,
        "annual_equity_multiple": 1.0,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": 0.0,
        "trades": 0,
        "trades_per_day": 0.0,
        "profit_factor": 0.0,
        "avg_trade_pct": 0.0,
        "median_trade_pct": 0.0,
        "worst_trade_pct": 0.0,
        "stop_trades": 0,
        "tp_trades": 0,
        "trail_trades": 0,
        "max_hold_trades": 0,
        "target_return_pass": False,
        "target_drawdown_pass": False,
        "target_win_rate_pass": False,
        "frequency_preference_pass": False,
        "meets_core_target": False,
        "meets_full_preference": False,
    }


def evaluate_slice(
    *,
    config: StrategyConfig,
    raw_trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    window_trades = [trade for trade in raw_trades if start_ts <= trade.entry_ts < end_ts]
    result = evaluate_config(
        config=config,
        raw_trades=window_trades,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if result is None:
        return empty_slice_metrics(start_ts, end_ts)
    return asdict(result)


def validation_windows(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> list[dict[str, Any]]:
    midpoint = start_ts + (end_ts - start_ts) / 2
    quarter = (end_ts - start_ts) / 4
    windows = [
        {"slice": "full", "start": start_ts, "end": end_ts},
        {"slice": "first_half", "start": start_ts, "end": midpoint},
        {"slice": "second_half", "start": midpoint, "end": end_ts},
        {"slice": "last_90d", "start": max(start_ts, end_ts - pd.Timedelta(days=90)), "end": end_ts},
        {"slice": "is_2025_05_30_to_2026_03_01", "start": start_ts, "end": pd.Timestamp("2026-03-01", tz="UTC")},
        {"slice": "val_2026_03_01_to_2026_06_01", "start": pd.Timestamp("2026-03-01", tz="UTC"), "end": pd.Timestamp("2026-06-01", tz="UTC")},
        {"slice": "oos_2026_06_01_to_latest", "start": pd.Timestamp("2026-06-01", tz="UTC"), "end": end_ts},
    ]
    for idx in range(4):
        windows.append(
            {
                "slice": f"q{idx + 1}",
                "start": start_ts + quarter * idx,
                "end": start_ts + quarter * (idx + 1),
            }
        )
    return [
        item
        for item in windows
        if item["end"] > start_ts and item["start"] < end_ts and item["end"] > item["start"]
    ]


def calendar_month_windows(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> list[dict[str, Any]]:
    starts = pd.date_range(start_ts.floor("D").replace(day=1), end_ts, freq="MS", tz="UTC")
    windows: list[dict[str, Any]] = []
    for month_start in starts:
        month_end = month_start + pd.offsets.MonthBegin(1)
        left = max(start_ts, pd.Timestamp(month_start))
        right = min(end_ts, pd.Timestamp(month_end))
        if right > left:
            windows.append(
                {
                    "window": left.strftime("%Y-%m"),
                    "start": left,
                    "end": right,
                }
            )
    return windows


def weekly_windows(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    left = start_ts
    idx = 1
    while left < end_ts:
        right = min(left + pd.Timedelta(days=7), end_ts)
        windows.append(
            {
                "window": f"week_{idx:03d}_{left.strftime('%Y%m%d')}_{(right - pd.Timedelta(minutes=1)).strftime('%Y%m%d')}",
                "start": left,
                "end": right,
            }
        )
        left = right
        idx += 1
    return windows


def rolling_windows(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for days in (30, 60, 90):
        left = start_ts
        idx = 1
        while left + pd.Timedelta(days=days) <= end_ts:
            right = left + pd.Timedelta(days=days)
            windows.append(
                {
                    "window": f"rolling_{days}d_{idx:03d}_{left.strftime('%Y%m%d')}_{(right - pd.Timedelta(minutes=1)).strftime('%Y%m%d')}",
                    "days": days,
                    "start": left,
                    "end": right,
                }
            )
            left += pd.Timedelta(days=30)
            idx += 1
    return windows


def slice_rows_for_variant(
    *,
    variant: VariantSpec,
    raw_trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in validation_windows(start_ts, end_ts):
        metrics = evaluate_slice(
            config=variant.config,
            raw_trades=raw_trades,
            start_ts=item["start"],
            end_ts=item["end"],
        )
        rows.append(
            {
                "label": variant.label,
                "family": variant.family,
                "parameter": variant.parameter,
                "value": variant.value,
                "slice": item["slice"],
                **metrics,
            }
        )
    return rows


def window_rows(
    *,
    config: StrategyConfig,
    raw_trades: list[Any],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in windows:
        metrics = evaluate_slice(
            config=config,
            raw_trades=raw_trades,
            start_ts=item["start"],
            end_ts=item["end"],
        )
        row = {
            "window": item["window"],
            "slice_start": str(item["start"]),
            "slice_end": str(item["end"]),
            **metrics,
        }
        if "days" in item:
            row["days"] = item["days"]
        rows.append(row)
    return rows


def selected_reason_counts(raw_trades: list[Any], filter_spec: FilterSpec) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in selected_trades(raw_trades, filter_spec):
        counts[trade.exit_reason] = counts.get(trade.exit_reason, 0) + 1
    return counts


def selection_counts(raw_trades: list[Any], filter_spec: FilterSpec) -> dict[str, int]:
    filter_pass = sum(1 for trade in raw_trades if passes_filter(trade, filter_spec))
    selected_count = len(selected_trades(raw_trades, filter_spec))
    return {
        "raw_trade_events": len(raw_trades),
        "filter_pass_events": filter_pass,
        "selected_trades": selected_count,
    }


def evaluate_variant(
    *,
    variant: VariantSpec,
    raw_trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = evaluate_config(
        config=variant.config,
        raw_trades=raw_trades,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if result is None:
        base: dict[str, Any] = empty_slice_metrics(start_ts, end_ts)
    else:
        base = asdict(result)
    slices = slice_rows_for_variant(
        variant=variant,
        raw_trades=raw_trades,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    key_slices = {row["slice"]: row for row in slices}
    counts = selection_counts(raw_trades, variant.config.filter)
    row = {
        "label": variant.label,
        "family": variant.family,
        "parameter": variant.parameter,
        "value": variant.value,
        "signal_name": variant.config.signal.name,
        "signal_kind": variant.config.signal.kind,
        "exit_name": variant.config.exit.name,
        "exit_kind": variant.config.exit.kind,
        "filter_name": variant.config.filter.name,
        "exposure": variant.config.exposure,
        "reason_counts": json.dumps(
            selected_reason_counts(raw_trades, variant.config.filter),
            ensure_ascii=False,
            sort_keys=True,
        ),
        **counts,
        **base,
    }
    for slice_name in ("first_half", "second_half", "last_90d", "q1", "q2", "q3", "q4", "oos_2026_06_01_to_latest"):
        item = key_slices.get(slice_name)
        if item is None:
            continue
        for field in (
            "trades",
            "annual_return_pct",
            "total_return_pct",
            "max_drawdown_pct",
            "win_rate_pct",
            "trades_per_day",
            "profit_factor",
        ):
            row[f"{slice_name}_{field}"] = item[field]
    row["stability_pass"] = bool(
        row.get("second_half_annual_return_pct", -999.0) > 0
        and row.get("last_90d_annual_return_pct", -999.0) > 0
        and row.get("oos_2026_06_01_to_latest_trades", 0) >= 10
    )
    row["ablation_gate_pass"] = bool(
        row.get("meets_full_preference", False) and row["stability_pass"]
    )
    return row, slices


def table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 变体 | 参数 | 值 | 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 | Δ年化 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | "
            f"`{pct(float(row['annual_return_pct']))}` | `{pct(float(row['max_drawdown_pct']))}` | "
            f"`{pct(float(row['win_rate_pct']))}` | `{int(row['trades'])}` | "
            f"`{num(float(row['trades_per_day']))}` | `{num(float(row['profit_factor']))}` | "
            f"`{pct(float(row.get('second_half_annual_return_pct', 0.0)))}` | "
            f"`{pct(float(row.get('last_90d_annual_return_pct', 0.0)))}` | "
            f"`{pct(float(row['delta_annual_return_pct']))}` |"
        )
    return lines


def slice_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 切片 | 年化 | 总收益 | 回撤 | 胜率 | 笔数 | 笔/日 | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['slice']}` | `{pct(float(row['annual_return_pct']))}` | "
            f"`{pct(float(row['total_return_pct']))}` | `{pct(float(row['max_drawdown_pct']))}` | "
            f"`{pct(float(row['win_rate_pct']))}` | `{int(row['trades'])}` | "
            f"`{num(float(row['trades_per_day']))}` | `{num(float(row['profit_factor']))}` |"
        )
    return lines


def render_markdown(
    *,
    metadata: dict[str, Any],
    data_quality: dict[str, Any],
    summary: pd.DataFrame,
    validation_slices: pd.DataFrame,
    rolling: pd.DataFrame,
    weekly: pd.DataFrame,
    monthly: pd.DataFrame,
) -> str:
    baseline = summary.loc[summary["label"].eq("baseline")].iloc[0]
    variants = summary.loc[~summary["label"].eq("baseline")].copy()
    harmful = variants.sort_values(["delta_annual_return_pct", "delta_profit_factor"]).head(15)
    helpful = variants.sort_values(
        ["ablation_gate_pass", "stability_pass", "delta_annual_return_pct"],
        ascending=False,
    ).head(15)
    best_by_parameter = (
        variants.sort_values(
            ["ablation_gate_pass", "stability_pass", "annual_return_pct", "profit_factor"],
            ascending=False,
        )
        .groupby("parameter", sort=False)
        .head(1)
    )
    baseline_slices = validation_slices.loc[validation_slices["label"].eq("baseline")]
    worst_month = monthly.sort_values("annual_return_pct").iloc[0]
    best_month = monthly.sort_values("annual_return_pct", ascending=False).iloc[0]
    worst_rolling90 = rolling.loc[rolling["days"].eq(90)].sort_values("annual_return_pct").head(1)
    positive_months = int((monthly["total_return_pct"] > 0).sum())
    target_pass_count = int(summary["meets_core_target"].sum())
    stable_pass_count = int(summary["stability_pass"].sum())
    ablation_gate_pass_count = int(summary["ablation_gate_pass"].sum())

    lines = [
        "# HYPE-15M-MII 全参数消融与时间切片回测 2026-06-26",
        "",
        "Family id：`HYPE-15M-MII`",
        "",
        "## 结论",
        "",
        "本轮锁定 `2026-06-25` 搜索报告中的最佳综合候选做复现、不同时间片回测和单因子全参数消融。结果仍是负面诊断：基线没有达到 `>=2000%` 年化目标，且最近时间片继续退化；消融里没有任何变体同时满足 core target、频率偏好和最近稳定性。",
        "",
        f"- core target 通过数：`{target_pass_count}/{len(summary)}`。",
        f"- 稳定性通过数：`{stable_pass_count}/{len(summary)}`，定义为后半段年化、Last90 年化为正且 `2026-06-01` 后至少 `10` 笔。",
        f"- 完整消融 gate 通过数：`{ablation_gate_pass_count}/{len(summary)}`。",
        "",
        "因此本策略仍不能提升为 live、paper-live、handoff 或 candidate；本报告只作为 negative diagnostic 和后续是否重构研究方向的证据。",
        "",
        "## 数据与执行口径",
        "",
        f"- 数据：Binance USD-M futures `HYPEUSDT` `15m` cache，`{data_quality['first_ts']}` 到 `{data_quality['last_ts']}`，共 `{data_quality['rows']}` 根。",
        f"- cache：`{data_quality['cache_path']}`；标准 data lake `15m` HYPE 目录存在：`{data_quality['standard_data_lake_found']}`。",
        f"- 数据质量检查：缺口 `{data_quality['gap_count']}`，重复 timestamp `{data_quality['duplicated_ts']}`，关键空值 `{data_quality['critical_nulls']}`，非法 OHLC 行 `{data_quality['invalid_ohlc_rows']}`。",
        "- 限制：该 cache 只有 `ts/open/high/low/close/volume`，没有 `quote_volume/trade_count/vwap/source/is_closed` 字段；本轮是历史 cache 复现口径，不等同于已迁入标准数据湖后的正式数据集。",
        f"- 成本：每边手续费 `{COMMISSION_PER_SIDE:.4%}`，每边滑点 `{SLIPPAGE_PER_SIDE:.4%}`，round-trip `{ROUND_TRIP_COST:.4%}`。",
        "- 执行：闭合 `15m` bar 产生信号，下一根 open 入场；固定 TP/SL 用 intrabar high/low 检查；同根同时触发时 stop first；单仓不重叠。",
        "",
        "## 基线",
        "",
        "- 信号：`RSI(7)` 反转，low `30`，high `60`。",
        "- 过滤：`MACD histogram` 同方向 `>= 0`，`ATR96 pct` 在 `0.60%-2.80%`。",
        "- 出场：`TP=0.90%`，`SL=2.80%`，最长 `16` 根 `15m` bar。",
        "- 暴露：`1.5x`。",
        "",
        "| 年化 | 总收益 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{pct(float(baseline['annual_return_pct']))}` | `{pct(float(baseline['total_return_pct']))}` | `{pct(float(baseline['max_drawdown_pct']))}` | `{pct(float(baseline['win_rate_pct']))}` | `{int(baseline['trades'])}` | `{num(float(baseline['trades_per_day']))}` | `{num(float(baseline['profit_factor']))}` | `{pct(float(baseline['second_half_annual_return_pct']))}` | `{pct(float(baseline['last_90d_annual_return_pct']))}` |",
        "",
        "## 基线时间切片",
        "",
        *slice_table(baseline_slices),
        "",
        "## 伤害最大的消融",
        "",
        *table(harmful),
        "",
        "## 表面改善最大的消融",
        "",
        *table(helpful),
        "",
        "说明：上表按完整 gate、稳定性和年化改善排序；排名靠前不代表可提升，只说明在这个样本内相对基线更好。",
        "",
        "## 每个参数的最佳单因子结果",
        "",
        *table(best_by_parameter),
        "",
        "## 周/月/滚动摘要",
        "",
        f"- 月数：`{len(monthly)}`，盈利月 `{positive_months}/{len(monthly)}`，中位月总收益 `{pct(float(monthly['total_return_pct'].median()))}`。",
        f"- 最差月：`{worst_month['window']}`，年化 `{pct(float(worst_month['annual_return_pct']))}`，总收益 `{pct(float(worst_month['total_return_pct']))}`；最好月：`{best_month['window']}`，年化 `{pct(float(best_month['annual_return_pct']))}`，总收益 `{pct(float(best_month['total_return_pct']))}`。",
    ]
    if not worst_rolling90.empty:
        row = worst_rolling90.iloc[0]
        lines.append(
            f"- 最差滚动 `90d`：`{row['window']}`，年化 `{pct(float(row['annual_return_pct']))}`，总收益 `{pct(float(row['total_return_pct']))}`，回撤 `{pct(float(row['max_drawdown_pct']))}`。"
        )
    lines.extend(
        [
            f"- 周数：`{len(weekly)}`，盈利周 `{int((weekly['total_return_pct'] > 0).sum())}/{len(weekly)}`，中位周总收益 `{pct(float(weekly['total_return_pct'].median()))}`。",
            "",
            "## 参数结论",
            "",
            "- 基线依赖 `MACD >= 0 + ATR band`，但这组过滤没有带来最近稳定性；删除或放宽过滤会改变交易数和年化，但不能修复 Last90 退化。",
            "- `TP=0.90%/SL=2.80%/hold16` 不是 live promotion 级别的稳健结构。部分 TP/hold 或 exposure 改动可能抬高样本内年化，但通常伴随回撤越界、频率偏离或最近窗口转弱。",
            "- RSI 参数邻域没有证明 `RSI(7,30,60)` 是可迁移结构；这更像一个在早期强趋势上捕捉到收益、后期衰减的搜索结果。",
            "- 由于 cache 缺少完整数据湖字段，本轮即使数据连续也只应视为 reproduction diagnostic；若未来继续，需要先迁入/校验标准数据湖，再做 train/test 或 walk-forward，而不是继续扩大盲搜。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- JSON：`{SUMMARY_JSON_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- 验证切片 CSV：`{VALIDATION_SLICES_CSV_PATH}`",
            f"- 滚动切片 CSV：`{ROLLING_CSV_PATH}`",
            f"- 周切片 CSV：`{WEEKLY_CSV_PATH}`",
            f"- 月切片 CSV：`{MONTHLY_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ABLATIONS_DIR.mkdir(parents=True, exist_ok=True)

    raw, metadata = load_data(CACHE_PATH, refresh=False)
    quality = data_quality_report(raw)
    start_ts = pd.Timestamp(raw["ts"].min())
    end_ts = pd.Timestamp(raw["ts"].max())

    variants = build_variants()
    signals = {variant.config.signal.name: variant.config.signal for variant in variants}
    spans = sorted(
        {
            value
            for signal in signals.values()
            for value in (signal.fast, signal.slow)
            if value
        }
        | {fast for fast, _slow in ema_pairs()}
        | {slow for _fast, slow in ema_pairs()}
    )
    features = add_features(raw, spans)
    market = build_market_arrays(features)
    states = {
        signal.name: signal_state(features, signal)
        for signal in signals.values()
    }
    raw_trade_cache: dict[tuple[str, str], list[Any]] = {}

    summary_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    baseline_raw_trades: list[Any] | None = None

    print(
        f"data {start_ts} -> {end_ts} rows={len(raw)} variants={len(variants)}",
        flush=True,
    )
    for idx, variant in enumerate(variants, start=1):
        raw_trades = calculate_raw_trades(
            states=states,
            market=market,
            config=variant.config,
            raw_trade_cache=raw_trade_cache,
        )
        if variant.label == "baseline":
            baseline_raw_trades = raw_trades
        row, slices = evaluate_variant(
            variant=variant,
            raw_trades=raw_trades,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        summary_rows.append(row)
        validation_rows.extend(slices)
        if idx % 10 == 0 or idx == len(variants):
            print(f"variant {idx}/{len(variants)}", flush=True)

    if baseline_raw_trades is None:
        raise RuntimeError("baseline raw trades were not captured")

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"].eq("baseline")].iloc[0]
    for column in (
        "annual_return_pct",
        "total_return_pct",
        "annual_equity_multiple",
        "max_drawdown_pct",
        "win_rate_pct",
        "trades_per_day",
        "profit_factor",
    ):
        summary[f"delta_{column}"] = summary[column] - baseline[column]
    summary = summary.sort_values(
        ["ablation_gate_pass", "stability_pass", "annual_return_pct", "profit_factor"],
        ascending=False,
    ).reset_index(drop=True)

    validation_slices = pd.DataFrame(validation_rows)
    rolling = pd.DataFrame(
        window_rows(
            config=BASELINE,
            raw_trades=baseline_raw_trades,
            windows=rolling_windows(start_ts, end_ts),
        )
    )
    weekly = pd.DataFrame(
        window_rows(
            config=BASELINE,
            raw_trades=baseline_raw_trades,
            windows=weekly_windows(start_ts, end_ts),
        )
    )
    monthly = pd.DataFrame(
        window_rows(
            config=BASELINE,
            raw_trades=baseline_raw_trades,
            windows=calendar_month_windows(start_ts, end_ts),
        )
    )

    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    validation_slices.to_csv(VALIDATION_SLICES_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    weekly.to_csv(WEEKLY_CSV_PATH, index=False)
    monthly.to_csv(MONTHLY_CSV_PATH, index=False)

    MARKDOWN_PATH.write_text(
        render_markdown(
            metadata=metadata,
            data_quality=quality,
            summary=summary,
            validation_slices=validation_slices,
            rolling=rolling,
            weekly=weekly,
            monthly=monthly,
        ),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": "HYPE-15M-MII",
                "baseline": {
                    "signal": asdict(BASELINE.signal),
                    "exit": asdict(BASELINE.exit),
                    "filter": asdict(BASELINE.filter),
                    "exposure": BASELINE.exposure,
                },
                "metadata": metadata,
                "data_quality": quality,
                "cost_model": {
                    "commission_per_side": COMMISSION_PER_SIDE,
                    "slippage_per_side": SLIPPAGE_PER_SIDE,
                    "round_trip_cost": ROUND_TRIP_COST,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary_csv": str(SUMMARY_CSV_PATH),
                    "validation_slices_csv": str(VALIDATION_SLICES_CSV_PATH),
                    "rolling_csv": str(ROLLING_CSV_PATH),
                    "weekly_csv": str(WEEKLY_CSV_PATH),
                    "monthly_csv": str(MONTHLY_CSV_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(
        summary.head(15)[
            [
                "label",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
                "trades_per_day",
                "profit_factor",
                "second_half_annual_return_pct",
                "last_90d_annual_return_pct",
                "ablation_gate_pass",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
