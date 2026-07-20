from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402
import research_hype_30m_k2_strict_validation_gates as strict  # noqa: E402
import research_hype_30m_k2_v2_1_dynamic_atr_bracket as dynamic  # noqa: E402


RUN_DATE = "2026-07-17"
ARTIFACT_DIR = base.ARTIFACT_DIR
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_full_ablation_timeframes_{RUN_DATE}.json"
ABLATION_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_component_ablation_{RUN_DATE}.csv"
SENSITIVITY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_parameter_sensitivity_{RUN_DATE}.csv"
TIMEFRAME_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_timeframe_transfer_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_rolling_oos_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_trade_bootstrap_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_phase_starts_{RUN_DATE}.csv"
SLICES_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_recent_slices_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_k2_v3_full_ablation_baseline_trades_{RUN_DATE}.csv"

FROZEN_UNTIL = "2026-07-13T06:07:00Z"
ATR_CAP = 0.0125
CLOSE_LOCATION = 0.65
SEED = 20260717

PARAMETER_SWEEPS: dict[str, tuple[Any, ...]] = {
    "keltner_ema": (8, 9, 10, 11, 12),
    "keltner_atr": (8, 9, 10, 11, 12),
    "keltner_mult": (1.6, 1.8, 2.0, 2.2, 2.4),
    "h1_ema_fast": (12, 14, 16, 18, 20),
    "h1_ema_slow": (36, 40, 44, 48, 52),
    "h1_slope_lag": (3, 4, 5, 6, 7),
    "leverage_atr": (60, 72, 84, 96, 108),
    "atr_target_pct": (0.021, 0.024, 0.027, 0.030, 0.033),
    "min_leverage": (0.0, 0.5, 1.0),
    "max_leverage": (2.0, 2.5, 3.0, 3.5, 4.0),
    "take_profit_pct": (0.08, 0.09, 0.10, 0.11, 0.12),
    "stop_loss_pct": (0.020, 0.0225, 0.025, 0.0275, 0.030),
    "max_hold_bars": (24, 27, 30, 33, 36),
    "entry_atr_cap": (0.0100, 0.01125, 0.0125, 0.01375, 0.0150),
    "close_location": (0.55, 0.60, 0.65, 0.70, 0.75),
}


def map_htf_boolean(
    frame: pd.DataFrame,
    htf: pd.DataFrame,
    column: str,
    *,
    signal_minutes: int,
    trend_minutes: int,
) -> np.ndarray:
    htf_close_times = (htf.index + pd.Timedelta(minutes=trend_minutes)).to_numpy()
    signal_close_times = (frame.index + pd.Timedelta(minutes=signal_minutes)).to_numpy()
    mapped = np.searchsorted(htf_close_times, signal_close_times, side="right") - 1
    output = np.zeros(len(frame), dtype=bool)
    valid = mapped >= 0
    values = htf[column].fillna(False).to_numpy(bool)
    output[valid] = values[mapped[valid]]
    return output


def build_features(
    signal_bars: pd.DataFrame,
    trend_bars: pd.DataFrame,
    cfg: base.StrategyConfig,
    *,
    signal_minutes: int = 30,
    trend_minutes: int = 60,
    use_fast_slow: bool = True,
    use_slope: bool = True,
    use_regime: bool = True,
    use_keltner: bool = True,
    atr_cap: float | None = ATR_CAP,
    close_location_threshold: float | None = CLOSE_LOCATION,
    atr_denominator: str = "signal_close",
    direction: str = "both",
) -> pd.DataFrame:
    frame = signal_bars.copy()
    tr = base.true_range(frame)
    frame["mid"] = base.ema(frame["close"], cfg.keltner_ema)
    frame["atr10"] = base.rma(tr, cfg.keltner_atr)
    frame["upper"] = frame["mid"] + cfg.keltner_mult * frame["atr10"]
    frame["lower"] = frame["mid"] - cfg.keltner_mult * frame["atr10"]
    frame["atr96"] = base.rma(tr, cfg.leverage_atr)
    candle_range = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    frame["close_location"] = (frame["close"] - frame["low"]) / candle_range

    htf = trend_bars.copy()
    htf["ema_fast"] = base.ema(htf["close"], cfg.h1_ema_fast)
    htf["ema_slow"] = base.ema(htf["close"], cfg.h1_ema_slow)
    htf["slope"] = htf["ema_slow"] - htf["ema_slow"].shift(cfg.h1_slope_lag)
    htf["long_regime"] = True
    htf["short_regime"] = True
    if use_fast_slow:
        htf["long_regime"] &= htf["ema_fast"].gt(htf["ema_slow"])
        htf["short_regime"] &= htf["ema_fast"].lt(htf["ema_slow"])
    if use_slope:
        htf["long_regime"] &= htf["slope"].gt(0.0)
        htf["short_regime"] &= htf["slope"].lt(0.0)
    if not use_regime:
        htf["long_regime"] = True
        htf["short_regime"] = True

    frame["long_regime_1h"] = map_htf_boolean(
        frame,
        htf,
        "long_regime",
        signal_minutes=signal_minutes,
        trend_minutes=trend_minutes,
    )
    frame["short_regime_1h"] = map_htf_boolean(
        frame,
        htf,
        "short_regime",
        signal_minutes=signal_minutes,
        trend_minutes=trend_minutes,
    )
    if use_keltner:
        long_signal = frame["long_regime_1h"] & frame["close"].gt(frame["upper"])
        short_signal = frame["short_regime_1h"] & frame["close"].lt(frame["lower"])
    else:
        long_signal = frame["long_regime_1h"].copy()
        short_signal = frame["short_regime_1h"].copy()

    if atr_cap is not None:
        denominator = (
            frame["close"]
            if atr_denominator == "signal_close"
            else frame["open"].shift(-1)
        )
        atr_filter = frame["atr96"].div(denominator).le(atr_cap)
        long_signal &= atr_filter.fillna(False)
        short_signal &= atr_filter.fillna(False)
    if close_location_threshold is not None:
        long_signal &= frame["close_location"].ge(close_location_threshold).fillna(False)
        short_signal &= frame["close_location"].le(1.0 - close_location_threshold).fillna(False)
    if direction == "long":
        short_signal[:] = False
    elif direction == "short":
        long_signal[:] = False
    elif direction != "both":
        raise ValueError(f"unknown direction: {direction}")
    frame["long_signal"] = long_signal
    frame["short_signal"] = short_signal
    return frame


def ready_start(features: pd.DataFrame) -> pd.Timestamp:
    ready = features[["atr96", "upper", "lower"]].notna().all(axis=1)
    if not ready.any():
        raise RuntimeError("features never become ready")
    return pd.Timestamp(features.index[np.flatnonzero(ready.to_numpy())[0]])


def trade_signature(trades: pd.DataFrame) -> tuple[tuple[str, str, str, str], ...]:
    if trades.empty:
        return ()
    return tuple(
        (
            str(row.entry_ts),
            str(row.exit_ts),
            str(row.direction),
            str(row.exit_reason),
        )
        for row in trades.itertuples()
    )


def result_row(
    category: str,
    variant: str,
    result: strict.StrictResult,
    baseline: strict.StrictResult,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "category": category,
        "variant": variant,
        **result.metrics,
        "return_delta_pct": result.metrics["return_pct"] - baseline.metrics["return_pct"],
        "mdd_delta_pct": result.metrics["max_drawdown_pct"] - baseline.metrics["max_drawdown_pct"],
        "win_rate_delta_pp": result.metrics["win_rate_pct"] - baseline.metrics["win_rate_pct"],
        "trade_delta": result.metrics["trades"] - baseline.metrics["trades"],
        "trade_sequence_changed": trade_signature(result.trades) != trade_signature(baseline.trades),
        **extra,
    }


def simulate(
    label: str,
    features: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> strict.StrictResult:
    return strict.simulate(
        label,
        features,
        funding,
        cfg,
        strict.ExecutionConfig(),
        start_ts=start,
        end_ts=end,
    )


def component_ablation(
    signal_bars: pd.DataFrame,
    trend_bars: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    baseline_features: pd.DataFrame,
    baseline: strict.StrictResult,
) -> pd.DataFrame:
    rows = [result_row("full", "full_v3", baseline, baseline)]
    feature_variants = {
        "remove_1h_regime": build_features(
            signal_bars, trend_bars, cfg, use_regime=False
        ),
        "remove_fast_slow_keep_slope": build_features(
            signal_bars, trend_bars, cfg, use_fast_slow=False
        ),
        "remove_slope_keep_fast_slow": build_features(
            signal_bars, trend_bars, cfg, use_slope=False
        ),
        "remove_keltner_breakout": build_features(
            signal_bars, trend_bars, cfg, use_keltner=False
        ),
        "remove_atr_cap": build_features(
            signal_bars, trend_bars, cfg, atr_cap=None
        ),
        "remove_close_location": build_features(
            signal_bars, trend_bars, cfg, close_location_threshold=None
        ),
        "remove_filter_bundle": build_features(
            signal_bars,
            trend_bars,
            cfg,
            atr_cap=None,
            close_location_threshold=None,
        ),
        "spec_atr_denominator_next_open": build_features(
            signal_bars,
            trend_bars,
            cfg,
            atr_denominator="next_open",
        ),
        "long_only": build_features(
            signal_bars, trend_bars, cfg, direction="long"
        ),
        "short_only": build_features(
            signal_bars, trend_bars, cfg, direction="short"
        ),
    }
    for label, features in feature_variants.items():
        result = simulate(label, features, funding, cfg, start, end)
        rows.append(result_row("logic_or_filter", label, result, baseline))

    risk_variants = {
        "fixed_1x": replace(cfg, min_leverage=1.0, max_leverage=1.0),
        "fixed_baseline_average_leverage": replace(
            cfg,
            min_leverage=float(baseline.metrics["avg_leverage"]),
            max_leverage=float(baseline.metrics["avg_leverage"]),
        ),
        "fixed_3x": replace(cfg, min_leverage=3.0, max_leverage=3.0),
        "remove_take_profit": replace(cfg, take_profit_pct=10.0),
        "remove_stop_loss": replace(cfg, stop_loss_pct=10.0),
        "remove_time_exit": replace(cfg, max_hold_bars=len(signal_bars) + 1),
    }
    for label, variant_cfg in risk_variants.items():
        result = simulate(
            label,
            baseline_features,
            funding,
            variant_cfg,
            start,
            end,
        )
        rows.append(result_row("risk_or_exit", label, result, baseline))
    return pd.DataFrame(rows)


def parameter_sensitivity(
    signal_bars: pd.DataFrame,
    trend_bars: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    baseline: strict.StrictResult,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frozen = asdict(cfg) | {
        "entry_atr_cap": ATR_CAP,
        "close_location": CLOSE_LOCATION,
    }
    for parameter, values in PARAMETER_SWEEPS.items():
        for value in values:
            variant_cfg = cfg
            atr_cap = ATR_CAP
            close_location = CLOSE_LOCATION
            if parameter == "entry_atr_cap":
                atr_cap = float(value)
            elif parameter == "close_location":
                close_location = float(value)
            else:
                variant_cfg = replace(cfg, **{parameter: value})
            features = build_features(
                signal_bars,
                trend_bars,
                variant_cfg,
                atr_cap=atr_cap,
                close_location_threshold=close_location,
            )
            result = simulate(
                f"{parameter}_{value}",
                features,
                funding,
                variant_cfg,
                start,
                end,
            )
            rows.append(
                result_row(
                    "parameter",
                    f"{parameter}_{value}",
                    result,
                    baseline,
                    parameter=parameter,
                    value=value,
                    frozen_value=frozen[parameter],
                    is_frozen=value == frozen[parameter],
                )
            )
    return pd.DataFrame(rows)


def scaled_config(cfg: base.StrategyConfig, signal_minutes: int) -> base.StrategyConfig:
    scale = 30.0 / signal_minutes
    volatility_scale = float(np.sqrt(signal_minutes / 30.0))

    def scaled(value: int, minimum: int = 2) -> int:
        return max(minimum, int(np.floor(value * scale + 0.5)))

    return replace(
        cfg,
        keltner_ema=scaled(cfg.keltner_ema),
        keltner_atr=scaled(cfg.keltner_atr),
        h1_ema_fast=scaled(cfg.h1_ema_fast),
        h1_ema_slow=scaled(cfg.h1_ema_slow),
        h1_slope_lag=scaled(cfg.h1_slope_lag, minimum=1),
        leverage_atr=scaled(cfg.leverage_atr),
        atr_target_pct=cfg.atr_target_pct * volatility_scale,
        max_hold_bars=scaled(cfg.max_hold_bars, minimum=1),
    )


def timeframe_transfer(
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    baseline: strict.StrictResult,
    baseline_start: pd.Timestamp,
    fixed_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    for mode in ("native_bar_counts", "clock_normalized"):
        for signal_minutes in (15, 30, 60, 120):
            trend_minutes = signal_minutes * 2
            variant_cfg = cfg if mode == "native_bar_counts" else scaled_config(cfg, signal_minutes)
            atr_cap = (
                ATR_CAP
                if mode == "native_bar_counts"
                else ATR_CAP * float(np.sqrt(signal_minutes / 30.0))
            )
            signal_bars = base.aggregate_ohlcv(
                m1,
                freq=f"{signal_minutes}min",
                phase_min=0,
                expected_rows=signal_minutes,
            )[0]
            trend_bars = base.aggregate_ohlcv(
                m1,
                freq=f"{trend_minutes}min",
                phase_min=0,
                expected_rows=trend_minutes,
            )[0]
            features = build_features(
                signal_bars,
                trend_bars,
                variant_cfg,
                signal_minutes=signal_minutes,
                trend_minutes=trend_minutes,
                atr_cap=atr_cap,
            )
            start = max(baseline_start, ready_start(features))
            end = min(
                fixed_end,
                signal_bars.index.max() + pd.Timedelta(minutes=signal_minutes),
            )
            label = f"{mode}_{signal_minutes}m_{trend_minutes}m"
            result = simulate(label, features, funding, variant_cfg, start, end)
            rows.append(
                result_row(
                    "timeframe",
                    label,
                    result,
                    baseline,
                    mode=mode,
                    signal_minutes=signal_minutes,
                    trend_minutes=trend_minutes,
                    entry_atr_cap=atr_cap,
                    start=str(start),
                    end=str(end),
                    config=json.dumps(asdict(variant_cfg), sort_keys=True),
                )
            )
            for recent in result.slices:
                slice_rows.append(
                    {
                        "variant": label,
                        "signal_minutes": signal_minutes,
                        "mode": mode,
                        **recent,
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(slice_rows)


def rolling_oos(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    oos_start = start + pd.Timedelta(days=70)
    window = 0
    while oos_start < end:
        oos_end = min(oos_start + pd.Timedelta(days=30), end)
        result = simulate(
            f"oos_{window:02d}",
            features,
            funding,
            cfg,
            oos_start,
            oos_end,
        )
        rows.append(
            {
                "window": window,
                "is_start": str(oos_start - pd.Timedelta(days=70)),
                "gap_start": str(oos_start - pd.Timedelta(days=10)),
                "oos_start": str(oos_start),
                "oos_end": str(oos_end),
                **result.metrics,
            }
        )
        window += 1
        oos_start += pd.Timedelta(days=30)
    return pd.DataFrame(rows)


def phase_starts(
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    baseline: strict.StrictResult,
    baseline_start: pd.Timestamp,
    fixed_end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    starts = [
        baseline_start + pd.Timedelta(days=30 * offset)
        for offset in range(8)
        if baseline_start + pd.Timedelta(days=30 * offset) < fixed_end
    ]
    for phase_type, phases in (("signal_30m", (0, 10, 20)), ("trend_1h", (0, 30))):
        for phase in phases:
            signal_phase = phase if phase_type == "signal_30m" else 0
            trend_phase = phase if phase_type == "trend_1h" else 0
            signal_bars = base.aggregate_ohlcv(
                m1,
                freq="30min",
                phase_min=signal_phase,
                expected_rows=30,
            )[0]
            trend_bars = base.aggregate_ohlcv(
                m1,
                freq="60min",
                phase_min=trend_phase,
                expected_rows=60,
            )[0]
            features = build_features(signal_bars, trend_bars, cfg)
            for idx, start in enumerate(starts):
                result = simulate(
                    f"{phase_type}_{phase}_start_{idx}",
                    features,
                    funding,
                    cfg,
                    max(start, ready_start(features)),
                    fixed_end,
                )
                rows.append(
                    result_row(
                        "phase",
                        f"{phase_type}_{phase}_start_{idx}",
                        result,
                        baseline,
                        phase_type=phase_type,
                        phase_minutes=phase,
                        start_index=idx,
                        start=str(start),
                    )
                )
    return pd.DataFrame(rows)


def summarize_sensitivity(frame: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for parameter, group in frame.groupby("parameter", sort=False):
        output[parameter] = {
            "variants": int(len(group)),
            "positive_fraction": float(group["return_pct"].gt(0.0).mean()),
            "return_min": float(group["return_pct"].min()),
            "return_median": float(group["return_pct"].median()),
            "return_max": float(group["return_pct"].max()),
            "mdd_worst": float(group["max_drawdown_pct"].min()),
            "trade_sequence_changed_fraction": float(
                group["trade_sequence_changed"].mean()
            ),
        }
    return output


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    args = type(
        "Args",
        (),
        {
            "since": "2025-05-30T00:00:00Z",
            "until": FROZEN_UNTIL,
            "refresh_cache": False,
            "timeout": 45.0,
        },
    )()
    funding_args = type(
        "FundingArgs",
        (),
        {"refresh_data": False, "timeout": 45.0},
    )()
    m1 = base.load_or_fetch_1m(args)
    quality = base.data_quality(m1)
    blockers = (
        quality["missing_1m_bars"]
        + quality["duplicate_ts_rows"]
        + quality["invalid_ohlc_rows"]
        + quality["critical_null_rows"]
    )
    if blockers:
        raise RuntimeError(f"data quality blocker: {quality}")
    funding = strict.load_or_fetch_funding(funding_args, m1)
    cfg = dynamic.v21_config()
    signal_bars = base.aggregate_ohlcv(
        m1, freq="30min", phase_min=0, expected_rows=30
    )[0]
    trend_bars = base.aggregate_ohlcv(
        m1, freq="60min", phase_min=0, expected_rows=60
    )[0]
    features = build_features(signal_bars, trend_bars, cfg)
    start = ready_start(features)
    end = signal_bars.index.max() + pd.Timedelta(minutes=30)
    baseline = simulate("v3_full", features, funding, cfg, start, end)
    if baseline.metrics["trades"] != 78 or not np.isclose(
        baseline.metrics["return_pct"], 6328.98, atol=0.05
    ):
        raise RuntimeError(
            "V3 baseline parity failed: "
            f"{baseline.metrics['trades']} trades / "
            f"{baseline.metrics['return_pct']:.6f}%"
        )

    ablation = component_ablation(
        signal_bars,
        trend_bars,
        funding,
        cfg,
        start,
        end,
        features,
        baseline,
    )
    sensitivity = parameter_sensitivity(
        signal_bars,
        trend_bars,
        funding,
        cfg,
        start,
        end,
        baseline,
    )
    timeframes, timeframe_slices = timeframe_transfer(
        m1,
        funding,
        cfg,
        baseline,
        start,
        end,
    )
    oos = rolling_oos(features, funding, cfg, start, end)
    mc = strict.run_trade_mc(baseline.trades, runs=5000)
    phases = phase_starts(m1, funding, cfg, baseline, start, end)
    baseline_slices = pd.DataFrame(
        [{"variant": "v3_full_30m_1h", **item} for item in baseline.slices]
    )
    slices = pd.concat([baseline_slices, timeframe_slices], ignore_index=True)

    mc3 = mc.loc[mc["mc_type"].eq("mc3_bootstrap")]
    phase_summary = (
        phases.groupby(["phase_type", "phase_minutes"])
        .agg(
            starts=("variant", "size"),
            median_return_pct=("return_pct", "median"),
            min_return_pct=("return_pct", "min"),
            median_mdd_pct=("max_drawdown_pct", "median"),
            median_trades=("trades", "median"),
        )
        .reset_index()
    )
    summary = {
        "strategy": "HYPE-30M-Keltner-Trend-Breakout-V3",
        "study": "full connected-parameter ablation and timeframe robustness",
        "run_date": RUN_DATE,
        "data_quality": quality,
        "funding": {
            "rows": int(len(funding)),
            "start": str(funding["ts"].min()) if not funding.empty else None,
            "end": str(funding["ts"].max()) if not funding.empty else None,
        },
        "cost": {
            "fee_per_fill": strict.FEE_PER_FILL,
            "adverse_slippage_per_fill": strict.SLIPPAGE_PER_FILL,
            "funding_included": True,
        },
        "baseline": baseline.metrics,
        "baseline_start": str(start),
        "baseline_end": str(end),
        "implementation_note": (
            "Frozen V3 artifact uses ATR84/signal_close for the 1.25% filter; "
            "the spec wording ATR84/next_open is tested as a separate ablation."
        ),
        "component_ablation": ablation.to_dict(orient="records"),
        "parameter_sensitivity": summarize_sensitivity(sensitivity),
        "timeframes": timeframes.to_dict(orient="records"),
        "rolling_oos": {
            "windows": int(len(oos)),
            "positive_fraction": float(oos["return_pct"].gt(0.0).mean()),
            "zero_trade_windows": int(oos["trades"].eq(0).sum()),
            "median_return_pct": float(oos["return_pct"].median()),
            "median_trades": float(oos["trades"].median()),
        },
        "mc3_bootstrap": {
            "runs": int(len(mc3)),
            "return_p05": float(mc3["return_pct"].quantile(0.05)),
            "return_median": float(mc3["return_pct"].median()),
            "mdd_p05": float(mc3["max_drawdown_pct"].quantile(0.05)),
            "win_rate_p05": float(mc3["win_rate_pct"].quantile(0.05)),
        },
        "phase_summary": phase_summary.to_dict(orient="records"),
    }
    ablation.to_csv(ABLATION_PATH, index=False)
    sensitivity.to_csv(SENSITIVITY_PATH, index=False)
    timeframes.to_csv(TIMEFRAME_PATH, index=False)
    oos.to_csv(OOS_PATH, index=False)
    mc.to_csv(MC_PATH, index=False)
    phases.to_csv(PHASE_PATH, index=False)
    slices.to_csv(SLICES_PATH, index=False)
    baseline.trades.to_csv(TRADES_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print("baseline", baseline.metrics)
    print("\ncomponent ablation")
    print(
        ablation[
            [
                "variant",
                "return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
            ]
        ].to_string(index=False)
    )
    print("\ntimeframes")
    print(
        timeframes[
            [
                "variant",
                "return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
            ]
        ].to_string(index=False)
    )
    print("\nrolling OOS", summary["rolling_oos"])
    print("MC3", summary["mc3_bootstrap"])
    print("\nphase")
    print(phase_summary.to_string(index=False))
    print("\nsummary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
