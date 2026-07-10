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


RUN_DATE = "2026-07-10"
ARTIFACT_DIR = base.ARTIFACT_DIR
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_full_ablation_tune_{RUN_DATE}.json"
ABLATION_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_full_ablation_{RUN_DATE}.csv"
SENSITIVITY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_parameter_sensitivity_{RUN_DATE}.csv"
BEAM_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_beam_{RUN_DATE}.csv"
FINALISTS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_finalists_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_rolling_oos_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_phase_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuned_trades_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_monte_carlo_{RUN_DATE}.csv"
START_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_start_time_{RUN_DATE}.csv"
STRESS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_tuning_stress_{RUN_DATE}.csv"

TRAIN_END = pd.Timestamp("2026-01-31 00:00:00+00:00")
VALIDATION_START = pd.Timestamp("2026-02-14 00:00:00+00:00")
VALIDATION_END = pd.Timestamp("2026-06-30 00:00:00+00:00")
HOLDOUT_START = VALIDATION_END
BEAM_WIDTH = 10
FINAL_RETURN_RETENTION = 0.70

PARAMETER_SWEEPS: dict[str, tuple[Any, ...]] = {
    "keltner_ema": (8, 9, 10, 11, 12),
    "keltner_atr": (8, 9, 10, 11, 12),
    "keltner_mult": (1.8, 1.9, 2.0, 2.1, 2.2),
    "h1_ema_fast": (12, 14, 16, 18, 20),
    "h1_ema_slow": (40, 44, 48, 52, 56),
    "h1_slope_lag": (2, 3, 4, 5, 6),
    "leverage_atr": (72, 84, 96, 108, 120),
    "atr_target_pct": (0.024, 0.027, 0.030, 0.033, 0.036),
    "min_leverage": (0.0, 0.5, 1.0, 1.25),
    "max_leverage": (2.25, 2.5, 2.75, 3.0, 3.25),
    "take_profit_pct": (0.08, 0.09, 0.10, 0.11, 0.12),
    "stop_loss_pct": (0.020, 0.0225, 0.025, 0.0275, 0.030),
    "max_hold_bars": (24, 27, 30, 33, 36),
}

TUNING_GRIDS: dict[str, tuple[Any, ...]] = {
    "keltner_ema": (9, 10, 11),
    "keltner_atr": (9, 10, 11),
    "keltner_mult": (1.9, 2.0, 2.1),
    "h1_ema_fast": (14, 16, 18),
    "h1_ema_slow": (44, 48, 52),
    "h1_slope_lag": (3, 4, 5),
    "leverage_atr": (84, 96, 108),
    "atr_target_pct": (0.027, 0.030, 0.033),
    "max_leverage": (2.5, 2.75, 3.0),
    "take_profit_pct": (0.09, 0.10, 0.11),
    "stop_loss_pct": (0.0225, 0.025, 0.0275),
    "max_hold_bars": (27, 30, 33),
}


def map_htf_boolean(frame: pd.DataFrame, htf: pd.DataFrame, column: str) -> np.ndarray:
    h1_close_times = (htf.index + pd.Timedelta(hours=1)).to_numpy()
    b30_close_times = (frame.index + pd.Timedelta(minutes=30)).to_numpy()
    mapped = np.searchsorted(h1_close_times, b30_close_times, side="right") - 1
    output = np.zeros(len(frame), dtype=bool)
    valid = mapped >= 0
    values = htf[column].fillna(False).to_numpy(bool)
    output[valid] = values[mapped[valid]]
    return output


def build_logic_variant(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    cfg: base.StrategyConfig,
    *,
    regime_mode: str = "full",
    use_opposite_exclusion: bool = True,
) -> pd.DataFrame:
    frame = b30.copy()
    tr30 = base.true_range(frame)
    frame["mid"] = base.ema(frame["close"], cfg.keltner_ema)
    frame["atr10"] = base.rma(tr30, cfg.keltner_atr)
    frame["upper"] = frame["mid"] + cfg.keltner_mult * frame["atr10"]
    frame["lower"] = frame["mid"] - cfg.keltner_mult * frame["atr10"]
    frame["atr96"] = base.rma(tr30, cfg.leverage_atr)
    frame["break_up"] = frame["close"].gt(frame["upper"])
    frame["break_down"] = frame["close"].lt(frame["lower"])

    htf = h1.copy()
    htf["ema_fast"] = base.ema(htf["close"], cfg.h1_ema_fast)
    htf["ema_slow"] = base.ema(htf["close"], cfg.h1_ema_slow)
    htf["slope"] = htf["ema_slow"] - htf["ema_slow"].shift(cfg.h1_slope_lag)
    htf["fast_long"] = htf["ema_fast"].gt(htf["ema_slow"])
    htf["fast_short"] = htf["ema_fast"].lt(htf["ema_slow"])
    htf["close_long"] = htf["close"].gt(htf["ema_slow"])
    htf["close_short"] = htf["close"].lt(htf["ema_slow"])
    htf["slope_long"] = htf["slope"].gt(0.0)
    htf["slope_short"] = htf["slope"].lt(0.0)

    if regime_mode == "full":
        htf["long_regime"] = htf["fast_long"] & htf["close_long"] & htf["slope_long"]
        htf["short_regime"] = htf["fast_short"] & htf["close_short"] & htf["slope_short"]
    elif regime_mode == "no_close":
        htf["long_regime"] = htf["fast_long"] & htf["slope_long"]
        htf["short_regime"] = htf["fast_short"] & htf["slope_short"]
    elif regime_mode == "no_slope":
        htf["long_regime"] = htf["fast_long"] & htf["close_long"]
        htf["short_regime"] = htf["fast_short"] & htf["close_short"]
    elif regime_mode == "no_fast_slow":
        htf["long_regime"] = htf["close_long"] & htf["slope_long"]
        htf["short_regime"] = htf["close_short"] & htf["slope_short"]
    elif regime_mode == "no_regime":
        htf["long_regime"] = True
        htf["short_regime"] = True
    else:
        raise ValueError(f"unknown regime mode: {regime_mode}")

    frame["long_regime_1h"] = map_htf_boolean(frame, htf, "long_regime")
    frame["short_regime_1h"] = map_htf_boolean(frame, htf, "short_regime")
    long_signal = frame["long_regime_1h"] & frame["break_up"]
    short_signal = frame["short_regime_1h"] & frame["break_down"]
    if use_opposite_exclusion:
        long_signal &= ~frame["short_regime_1h"]
        short_signal &= ~frame["long_regime_1h"]
    frame["long_signal"] = long_signal
    frame["short_signal"] = short_signal
    return frame


def trade_signature(trades: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    if trades.empty:
        return []
    return [
        (
            str(row.entry_ts),
            str(row.exit_ts),
            str(row.direction),
            str(row.exit_reason),
        )
        for row in trades.itertuples()
    ]


def metrics_equivalent(left: strict.StrictResult, right: strict.StrictResult) -> bool:
    numeric_keys = [
        "return_pct",
        "max_drawdown_pct",
        "sharpe",
        "trades",
        "win_rate_pct",
        "avg_leverage",
        "worst_trade_pct",
        "profit_factor",
        "avg_trade_pct",
        "funding_pnl_pct",
    ]
    for key in numeric_keys:
        left_value = float(left.metrics[key])
        right_value = float(right.metrics[key])
        if not np.isclose(left_value, right_value, rtol=0.0, atol=1e-12, equal_nan=True):
            return False
    return left.metrics["exit_counts"] == right.metrics["exit_counts"]


def metrics_row(
    label: str,
    result: strict.StrictResult,
    cfg: base.StrategyConfig,
    baseline: strict.StrictResult,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "variant": label,
        **asdict(cfg),
        **result.metrics,
        "return_delta_pct": result.metrics["return_pct"] - baseline.metrics["return_pct"],
        "mdd_delta_pct": result.metrics["max_drawdown_pct"] - baseline.metrics["max_drawdown_pct"],
        "win_rate_delta_pp": result.metrics["win_rate_pct"] - baseline.metrics["win_rate_pct"],
        **extra,
    }


def run_logic_and_risk_ablation(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, strict.StrictResult]]:
    baseline_features = build_logic_variant(b30, h1, cfg)
    baseline = strict.simulate("ablation_full", baseline_features, funding, cfg, execution, start_ts=start, end_ts=end)
    results: dict[str, strict.StrictResult] = {"full": baseline}
    logic_variants = {
        "remove_opposite_regime_exclusion": build_logic_variant(
            b30,
            h1,
            cfg,
            use_opposite_exclusion=False,
        ),
        "remove_close_vs_slow": build_logic_variant(b30, h1, cfg, regime_mode="no_close"),
        "remove_close_and_exclusion": build_logic_variant(
            b30,
            h1,
            cfg,
            regime_mode="no_close",
            use_opposite_exclusion=False,
        ),
        "remove_slope": build_logic_variant(b30, h1, cfg, regime_mode="no_slope"),
        "remove_fast_vs_slow": build_logic_variant(b30, h1, cfg, regime_mode="no_fast_slow"),
        "remove_1h_regime": build_logic_variant(
            b30,
            h1,
            cfg,
            regime_mode="no_regime",
            use_opposite_exclusion=False,
        ),
    }
    for label, features in logic_variants.items():
        results[label] = strict.simulate(
            f"ablation_{label}",
            features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=end,
        )

    regime_only = baseline_features.copy()
    regime_only["long_signal"] = regime_only["long_regime_1h"]
    regime_only["short_signal"] = regime_only["short_regime_1h"]
    results["remove_keltner_breakout"] = strict.simulate(
        "ablation_remove_keltner_breakout",
        regime_only,
        funding,
        cfg,
        execution,
        start_ts=start,
        end_ts=end,
    )

    risk_variants = {
        "remove_dynamic_atr_sizing_fixed_1x": replace(cfg, min_leverage=1.0, max_leverage=1.0),
        "remove_dynamic_atr_sizing_fixed_avg": replace(
            cfg,
            min_leverage=baseline.metrics["avg_leverage"],
            max_leverage=baseline.metrics["avg_leverage"],
        ),
        "remove_min_leverage_floor": replace(cfg, min_leverage=0.0),
        "remove_max_leverage_cap": replace(cfg, max_leverage=100.0),
        "remove_take_profit": replace(cfg, take_profit_pct=10.0),
        "remove_stop_loss": replace(cfg, stop_loss_pct=10.0),
        "remove_time_exit": replace(cfg, max_hold_bars=len(b30) + 1),
    }
    for label, variant_cfg in risk_variants.items():
        features = build_logic_variant(b30, h1, variant_cfg)
        results[label] = strict.simulate(
            f"ablation_{label}",
            features,
            funding,
            variant_cfg,
            execution,
            start_ts=start,
            end_ts=end,
        )

    baseline_signature = trade_signature(baseline.trades)
    rows = []
    for label, result in results.items():
        variant_cfg = risk_variants.get(label, cfg)
        signature = trade_signature(result.trades)
        rows.append(
            metrics_row(
                label,
                result,
                variant_cfg,
                baseline,
                exact_trade_signature=signature == baseline_signature,
                exact_metrics=metrics_equivalent(result, baseline),
                signal_or_trade_changed=signature != baseline_signature,
            )
        )
    return pd.DataFrame(rows), results


def config_key(cfg: base.StrategyConfig) -> tuple[Any, ...]:
    return tuple(asdict(cfg).values())


def feature_key(cfg: base.StrategyConfig) -> tuple[Any, ...]:
    return (
        cfg.keltner_ema,
        cfg.keltner_atr,
        cfg.keltner_mult,
        cfg.h1_ema_fast,
        cfg.h1_ema_slow,
        cfg.h1_slope_lag,
        cfg.leverage_atr,
    )


def run_parameter_sensitivity(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, strict.StrictResult]:
    baseline_features = base.build_features(b30, h1, cfg)
    baseline = strict.simulate("sensitivity_baseline", baseline_features, funding, cfg, execution, start_ts=start, end_ts=end)
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] = {feature_key(cfg): baseline_features}
    rows = [metrics_row("baseline", baseline, cfg, baseline, parameter="baseline", parameter_value="baseline")]
    for field, values in PARAMETER_SWEEPS.items():
        for value in values:
            variant_cfg = replace(cfg, **{field: value})
            key = feature_key(variant_cfg)
            if key not in feature_cache:
                feature_cache[key] = base.build_features(b30, h1, variant_cfg)
            result = strict.simulate(
                f"sensitivity_{field}_{value}",
                feature_cache[key],
                funding,
                variant_cfg,
                execution,
                start_ts=start,
                end_ts=end,
            )
            rows.append(
                metrics_row(
                    f"{field}_{value}",
                    result,
                    variant_cfg,
                    baseline,
                    parameter=field,
                    parameter_value=value,
                )
            )
    return pd.DataFrame(rows), baseline


def split_utility(metrics: dict[str, Any], baseline: dict[str, Any]) -> float:
    if metrics["return_pct"] <= -99.0 or metrics["trades"] < max(5, int(0.5 * baseline["trades"])):
        return -1e9
    candidate_log = np.log(max(1e-12, 1.0 + metrics["return_pct"] / 100.0))
    baseline_log = np.log(max(1e-12, 1.0 + baseline["return_pct"] / 100.0))
    log_retention = candidate_log / baseline_log if baseline_log > 0.0 else 0.0
    win_gain = (metrics["win_rate_pct"] - baseline["win_rate_pct"]) / 5.0
    mdd_gain = (
        abs(baseline["max_drawdown_pct"]) - abs(metrics["max_drawdown_pct"])
    ) / max(1e-12, abs(baseline["max_drawdown_pct"]))
    return float(log_retention + 1.25 * win_gain + 1.5 * mdd_gain)


def evaluate_split_candidate(
    cfg: base.StrategyConfig,
    features: pd.DataFrame,
    funding: pd.DataFrame,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    baseline_train: strict.StrictResult,
    baseline_validation: strict.StrictResult,
) -> dict[str, Any]:
    train = strict.simulate(
        "beam_train",
        features,
        funding,
        cfg,
        execution,
        start_ts=start,
        end_ts=TRAIN_END,
    )
    validation = strict.simulate(
        "beam_validation",
        features,
        funding,
        cfg,
        execution,
        start_ts=VALIDATION_START,
        end_ts=VALIDATION_END,
    )
    utility_train = split_utility(train.metrics, baseline_train.metrics)
    utility_validation = split_utility(validation.metrics, baseline_validation.metrics)
    return {
        "config": cfg,
        "train": train,
        "validation": validation,
        "score": 0.45 * utility_train + 0.55 * utility_validation,
    }


def beam_tune(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, list[dict[str, Any]], strict.StrictResult, strict.StrictResult]:
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] = {}

    def features_for(candidate: base.StrategyConfig) -> pd.DataFrame:
        key = feature_key(candidate)
        if key not in feature_cache:
            feature_cache[key] = base.build_features(b30, h1, candidate)
        return feature_cache[key]

    baseline_features = features_for(cfg)
    baseline_train = strict.simulate(
        "baseline_train",
        baseline_features,
        funding,
        cfg,
        execution,
        start_ts=start,
        end_ts=TRAIN_END,
    )
    baseline_validation = strict.simulate(
        "baseline_validation",
        baseline_features,
        funding,
        cfg,
        execution,
        start_ts=VALIDATION_START,
        end_ts=VALIDATION_END,
    )
    beam = [
        evaluate_split_candidate(
            cfg,
            baseline_features,
            funding,
            execution,
            start,
            baseline_train,
            baseline_validation,
        )
    ]
    history: list[dict[str, Any]] = []
    for step, (field, values) in enumerate(TUNING_GRIDS.items(), start=1):
        candidates: dict[tuple[Any, ...], dict[str, Any]] = {}
        for parent in beam:
            parent_cfg = parent["config"]
            for value in values:
                candidate_cfg = replace(parent_cfg, **{field: value})
                key = config_key(candidate_cfg)
                if key in candidates:
                    continue
                candidates[key] = evaluate_split_candidate(
                    candidate_cfg,
                    features_for(candidate_cfg),
                    funding,
                    execution,
                    start,
                    baseline_train,
                    baseline_validation,
                )
        ranked = sorted(candidates.values(), key=lambda item: item["score"], reverse=True)
        beam = ranked[:BEAM_WIDTH]
        for rank, item in enumerate(beam, start=1):
            history.append(
                {
                    "step": step,
                    "field": field,
                    "rank": rank,
                    "score": item["score"],
                    **asdict(item["config"]),
                    "train_return_pct": item["train"].metrics["return_pct"],
                    "train_mdd_pct": item["train"].metrics["max_drawdown_pct"],
                    "train_win_rate_pct": item["train"].metrics["win_rate_pct"],
                    "train_trades": item["train"].metrics["trades"],
                    "validation_return_pct": item["validation"].metrics["return_pct"],
                    "validation_mdd_pct": item["validation"].metrics["max_drawdown_pct"],
                    "validation_win_rate_pct": item["validation"].metrics["win_rate_pct"],
                    "validation_trades": item["validation"].metrics["trades"],
                }
            )
    return pd.DataFrame(history), beam, baseline_train, baseline_validation


def evaluate_finalists(
    beam: list[dict[str, Any]],
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    baseline_full: strict.StrictResult,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    evaluated = []
    for rank, item in enumerate(beam, start=1):
        cfg = item["config"]
        features = base.build_features(b30, h1, cfg)
        full = strict.simulate(f"finalist_{rank:02d}_full", features, funding, cfg, execution, start_ts=start, end_ts=end)
        holdout = strict.simulate(
            f"finalist_{rank:02d}_holdout",
            features,
            funding,
            cfg,
            execution,
            start_ts=HOLDOUT_START,
            end_ts=end,
        )
        return_retention = full.metrics["return_pct"] / baseline_full.metrics["return_pct"]
        meets_goal = bool(
            full.metrics["win_rate_pct"] > baseline_full.metrics["win_rate_pct"]
            and full.metrics["max_drawdown_pct"] > baseline_full.metrics["max_drawdown_pct"]
            and return_retention >= FINAL_RETURN_RETENTION
            and item["validation"].metrics["return_pct"] > 0.0
        )
        row = {
            "beam_rank": rank,
            "score": item["score"],
            **asdict(cfg),
            "full_return_pct": full.metrics["return_pct"],
            "full_mdd_pct": full.metrics["max_drawdown_pct"],
            "full_win_rate_pct": full.metrics["win_rate_pct"],
            "full_trades": full.metrics["trades"],
            "full_return_retention": return_retention,
            "train_return_pct": item["train"].metrics["return_pct"],
            "train_mdd_pct": item["train"].metrics["max_drawdown_pct"],
            "train_win_rate_pct": item["train"].metrics["win_rate_pct"],
            "validation_return_pct": item["validation"].metrics["return_pct"],
            "validation_mdd_pct": item["validation"].metrics["max_drawdown_pct"],
            "validation_win_rate_pct": item["validation"].metrics["win_rate_pct"],
            "validation_trades": item["validation"].metrics["trades"],
            "holdout_return_pct": holdout.metrics["return_pct"],
            "holdout_mdd_pct": holdout.metrics["max_drawdown_pct"],
            "holdout_win_rate_pct": holdout.metrics["win_rate_pct"],
            "holdout_trades": holdout.metrics["trades"],
            "meets_full_goal": meets_goal,
        }
        rows.append(row)
        evaluated.append({**item, "full": full, "holdout": holdout, "row": row})
    return pd.DataFrame(rows), evaluated


def select_candidate(evaluated: list[dict[str, Any]]) -> dict[str, Any] | None:
    feasible = [item for item in evaluated if item["row"]["meets_full_goal"]]
    if not feasible:
        return None
    high_retention = [
        item
        for item in feasible
        if item["row"]["full_return_retention"] >= 0.90
    ]
    pool = high_retention or feasible
    return max(
        pool,
        key=lambda item: (
            item["row"]["full_mdd_pct"],
            item["row"]["full_return_retention"],
            item["row"]["score"],
        ),
    )


def apply_pruned_candidate(
    selected: dict[str, Any],
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    cfg = replace(selected["config"], min_leverage=0.0)
    features = build_logic_variant(
        b30,
        h1,
        cfg,
        regime_mode="no_close",
        use_opposite_exclusion=False,
    )
    selected = dict(selected)
    selected["config"] = cfg
    selected["full"] = strict.simulate(
        "selected_pruned_full",
        features,
        funding,
        cfg,
        execution,
        start_ts=start,
        end_ts=end,
    )
    selected["train"] = strict.simulate(
        "selected_pruned_train",
        features,
        funding,
        cfg,
        execution,
        start_ts=start,
        end_ts=TRAIN_END,
    )
    selected["validation"] = strict.simulate(
        "selected_pruned_validation",
        features,
        funding,
        cfg,
        execution,
        start_ts=VALIDATION_START,
        end_ts=VALIDATION_END,
    )
    selected["holdout"] = strict.simulate(
        "selected_pruned_holdout",
        features,
        funding,
        cfg,
        execution,
        start_ts=HOLDOUT_START,
        end_ts=end,
    )
    selected["row"] = {
        **selected["row"],
        **asdict(cfg),
        "full_return_pct": selected["full"].metrics["return_pct"],
        "full_mdd_pct": selected["full"].metrics["max_drawdown_pct"],
        "full_win_rate_pct": selected["full"].metrics["win_rate_pct"],
        "full_trades": selected["full"].metrics["trades"],
        "train_return_pct": selected["train"].metrics["return_pct"],
        "train_mdd_pct": selected["train"].metrics["max_drawdown_pct"],
        "train_win_rate_pct": selected["train"].metrics["win_rate_pct"],
        "validation_return_pct": selected["validation"].metrics["return_pct"],
        "validation_mdd_pct": selected["validation"].metrics["max_drawdown_pct"],
        "validation_win_rate_pct": selected["validation"].metrics["win_rate_pct"],
        "holdout_return_pct": selected["holdout"].metrics["return_pct"],
        "holdout_mdd_pct": selected["holdout"].metrics["max_drawdown_pct"],
        "holdout_win_rate_pct": selected["holdout"].metrics["win_rate_pct"],
    }
    return selected


def pruning_audit(
    selected: dict[str, Any],
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    cfg = selected["config"]
    full = selected["full"]
    variants = {
        "original_full_logic": base.build_features(b30, h1, cfg),
        "remove_opposite_regime_exclusion": build_logic_variant(
            b30,
            h1,
            cfg,
            use_opposite_exclusion=False,
        ),
        "remove_close_vs_slow": build_logic_variant(b30, h1, cfg, regime_mode="no_close"),
        "remove_both": build_logic_variant(
            b30,
            h1,
            cfg,
            regime_mode="no_close",
            use_opposite_exclusion=False,
        ),
    }
    signature = trade_signature(full.trades)
    rows = {}
    for label, features in variants.items():
        result = strict.simulate(f"prune_{label}", features, funding, cfg, execution, start_ts=start, end_ts=end)
        rows[label] = {
            "exact_trade_signature": trade_signature(result.trades) == signature,
            "metrics": result.metrics,
        }
    removable = [
        label
        for label, details in rows.items()
        if details["exact_trade_signature"]
        and label not in {"remove_both", "original_full_logic"}
    ]
    return {
        "variants": rows,
        "removable_conditions": removable,
        "removed_min_leverage_floor": cfg.min_leverage == 0.0,
        "note": "close-vs-slow is empirically exact on native history; opposite-regime exclusion is logically impossible under mutually exclusive fast/slow regimes.",
    }


def run_candidate_robustness(
    selected: dict[str, Any],
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    execution: strict.ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cfg = selected["config"]
    b30 = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)[0]
    h1 = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)[0]
    features = build_logic_variant(
        b30,
        h1,
        cfg,
        regime_mode="no_close",
        use_opposite_exclusion=False,
    )
    oos = strict.run_rolling_oos(features, funding, cfg, execution, start, end)
    candidate = strict.simulate(
        "selected_pruned_robustness",
        features,
        funding,
        cfg,
        execution,
        start_ts=start,
        end_ts=end,
    )
    rng = np.random.default_rng(strict.SEED + 20)
    mc1_rows = []
    for run in range(100):
        perturbed = build_logic_variant(
            strict.perturb_bars(b30, rng),
            strict.perturb_bars(h1, rng),
            cfg,
            regime_mode="no_close",
            use_opposite_exclusion=False,
        )
        result = strict.simulate(
            f"selected_mc1_{run:03d}",
            perturbed,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=end,
        )
        mc1_rows.append(
            strict.metric_row(
                f"selected_mc1_{run:03d}",
                result,
                mc_type="mc1_kline",
            )
        )
    mc1 = pd.DataFrame(mc1_rows)
    mc23 = strict.run_trade_mc(candidate.trades, 5000)
    monte_carlo = pd.concat([mc1, mc23], ignore_index=True, sort=False)
    mc2 = mc23.loc[mc23["mc_type"].eq("mc2_shuffle")]
    mc3 = mc23.loc[mc23["mc_type"].eq("mc3_bootstrap")]
    mc2_p05 = float(mc2["max_drawdown_pct"].quantile(0.05))
    mc2_limit = -1.5 * abs(float(candidate.metrics["max_drawdown_pct"]))

    daily = candidate.equity.resample("1D").last().pct_change().dropna()
    significance = strict.probabilistic_sharpe(daily)
    significance["dsr_n1000"] = strict.deflated_sharpe(daily, 1000)
    stress = strict.run_stress(features, funding, cfg, execution, start, end)
    bars30 = {
        phase: base.aggregate_ohlcv(
            m1,
            freq="30min",
            phase_min=phase,
            expected_rows=30,
        )[0]
        for phase in strict.PHASES_30M
    }
    bars1h = {
        phase: base.aggregate_ohlcv(
            m1,
            freq="60min",
            phase_min=phase,
            expected_rows=60,
        )[0]
        for phase in strict.PHASES_1H
    }
    phase30 = {
        phase: build_logic_variant(
            frame,
            bars1h[0],
            cfg,
            regime_mode="no_close",
            use_opposite_exclusion=False,
        )
        for phase, frame in bars30.items()
    }
    phase1h = {
        phase: build_logic_variant(
            bars30[0],
            frame,
            cfg,
            regime_mode="no_close",
            use_opposite_exclusion=False,
        )
        for phase, frame in bars1h.items()
    }
    start_runs = strict.run_start_sensitivity(features, funding, cfg, execution, start, end)
    phase_starts = [pd.Timestamp(value) for value in start_runs["start_ts"].iloc[:20]]
    phases = strict.run_phase_gate(phase30, phase1h, funding, cfg, execution, phase_starts, end)
    cagr_mean = float(start_runs["cagr_pct"].mean())
    start_cv = (
        float(start_runs["cagr_pct"].std(ddof=1) / abs(cagr_mean))
        if cagr_mean != 0.0
        else float("inf")
    )
    start_mdd_ratio = abs(float(start_runs["max_drawdown_pct"].min())) / max(
        1e-12,
        abs(float(start_runs["max_drawdown_pct"].median())),
    )
    phase_summary = {
        "30m": strict.phase_gate_status(phases, "30m"),
        "1h": strict.phase_gate_status(phases, "1h"),
    }
    robustness = {
        "gate_3_monte_carlo": {
            "status": (
                "pass"
                if float(mc1["return_pct"].gt(0.0).mean()) >= 0.80
                and mc2_p05 >= mc2_limit
                and float(mc3["return_pct"].quantile(0.05)) > 0.0
                else "fail"
            ),
            "mc1_positive_fraction": float(mc1["return_pct"].gt(0.0).mean()),
            "mc2_mdd_p05_pct": mc2_p05,
            "mc2_mdd_min_pct": float(mc2["max_drawdown_pct"].min()),
            "mc2_mdd_limit_pct": mc2_limit,
            "mc3_return_p05_pct": float(mc3["return_pct"].quantile(0.05)),
            "mc3_positive_fraction": float(mc3["return_pct"].gt(0.0).mean()),
        },
        "gate_5_significance": {
            "status": "pass" if significance["dsr_n1000"] >= 0.95 else "fail",
            **significance,
        },
        "gate_6_start_time": {
            "status": (
                "pass"
                if float(start_runs["return_pct"].gt(0.0).mean()) >= 0.90
                and start_cv < 0.5
                and start_mdd_ratio <= 1.5
                else "fail"
            ),
            "starts": int(len(start_runs)),
            "positive_fraction": float(start_runs["return_pct"].gt(0.0).mean()),
            "cagr_cv": start_cv,
            "mdd_ratio": start_mdd_ratio,
        },
        "gate_7_phase": {
            "status": (
                "pass"
                if phase_summary["30m"]["status"] == "pass"
                and phase_summary["1h"]["status"] == "pass"
                else "fail"
            ),
            **phase_summary,
        },
    }
    return oos, phases, monte_carlo, start_runs, stress, robustness


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    args = type(
        "Args",
        (),
        {
            "since": "2025-05-30T00:00:00Z",
            "until": "",
            "refresh_cache": False,
            "timeout": 45.0,
        },
    )()
    m1 = base.load_or_fetch_1m(args)
    funding_args = type("FundingArgs", (), {"refresh_data": False, "timeout": 45.0})()
    funding = strict.load_or_fetch_funding(funding_args, m1)
    cfg = base.StrategyConfig()
    execution = strict.ExecutionConfig()
    b30 = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)[0]
    h1 = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)[0]
    start = strict.ready_start(base.build_features(b30, h1, cfg))
    end = b30.index.max() + pd.Timedelta(minutes=30)

    ablation, ablation_results = run_logic_and_risk_ablation(
        b30,
        h1,
        funding,
        cfg,
        execution,
        start,
        end,
    )
    sensitivity, baseline_full = run_parameter_sensitivity(
        b30,
        h1,
        funding,
        cfg,
        execution,
        start,
        end,
    )
    beam_history, beam, baseline_train, baseline_validation = beam_tune(
        b30,
        h1,
        funding,
        cfg,
        execution,
        start,
    )
    finalists, evaluated = evaluate_finalists(
        beam,
        b30,
        h1,
        funding,
        execution,
        start,
        end,
        baseline_full,
    )
    selected = select_candidate(evaluated)
    if selected is not None:
        selected = apply_pruned_candidate(
            selected,
            b30,
            h1,
            funding,
            execution,
            start,
            end,
        )

    pruning: dict[str, Any] | None = None
    oos = pd.DataFrame()
    phases = pd.DataFrame()
    monte_carlo = pd.DataFrame()
    start_runs = pd.DataFrame()
    stress = pd.DataFrame()
    robustness: dict[str, Any] | None = None
    selected_payload: dict[str, Any] | None = None
    if selected is not None:
        pruning = pruning_audit(selected, b30, h1, funding, execution, start, end)
        oos, phases, monte_carlo, start_runs, stress, robustness = run_candidate_robustness(
            selected,
            m1,
            funding,
            execution,
            start,
            end,
        )
        selected["full"].trades.to_csv(TRADES_PATH, index=False)
        selected_payload = {
            "config": asdict(selected["config"]),
            "logic": {
                "long_regime": "ema_fast > ema_slow and ema_slow slope > 0",
                "short_regime": "ema_fast < ema_slow and ema_slow slope < 0",
                "removed": [
                    "close-vs-ema_slow regime clause",
                    "opposite-regime exclusion",
                    "minimum leverage floor",
                ],
            },
            "full_metrics": selected["full"].metrics,
            "full_slices": selected["full"].slices,
            "train_metrics": selected["train"].metrics,
            "validation_metrics": selected["validation"].metrics,
            "holdout_metrics": selected["holdout"].metrics,
            "row": selected["row"],
            "pruning": pruning,
            "rolling_oos": {
                "windows": int(len(oos)),
                "positive_fraction": float(oos["return_pct"].gt(0.0).mean()) if len(oos) else None,
                "median_return_pct": float(oos["return_pct"].median()) if len(oos) else None,
                "zero_trade_windows": int(oos["trades"].eq(0).sum()) if len(oos) else None,
            },
            "robustness_gates": robustness,
        }

    exact_equivalents = ablation.loc[
        ablation["exact_trade_signature"] & ablation["exact_metrics"],
        "variant",
    ].tolist()
    summary = {
        "strategy_family": "HYPE-30M-Keltner-Trend-Breakout",
        "study": "K2-FQ-V2-ATRVT-OFF full ablation and constrained tuning",
        "run_date": RUN_DATE,
        "data_range": {"start": str(pd.to_datetime(m1["ts"], utc=True).min()), "end": str(pd.to_datetime(m1["ts"], utc=True).max())},
        "cost_model": {
            "fee_per_fill": strict.FEE_PER_FILL,
            "slippage_per_fill": strict.SLIPPAGE_PER_FILL,
            "funding": True,
        },
        "selection_protocol": {
            "train": f"{start} -> {TRAIN_END}",
            "gap": f"{TRAIN_END} -> {VALIDATION_START}",
            "validation": f"{VALIDATION_START} -> {VALIDATION_END}",
            "holdout": f"{HOLDOUT_START} -> {end}",
            "beam_width": BEAM_WIDTH,
            "full_return_retention_floor": FINAL_RETURN_RETENTION,
            "warning": "All history participated in prior family research; holdout is only internal anti-overfit hygiene, not true OOS.",
        },
        "baseline": {
            "config": asdict(cfg),
            "full_metrics": baseline_full.metrics,
            "train_metrics": baseline_train.metrics,
            "validation_metrics": baseline_validation.metrics,
        },
        "ablation": {
            "exact_trade_equivalents": exact_equivalents,
            "rows": ablation.to_dict(orient="records"),
        },
        "selected": selected_payload,
        "decision": (
            "selected_pruned_tuned_observation"
            if selected_payload is not None
            else "no_candidate_met_win_mdd_return_constraints"
        ),
    }

    ablation.to_csv(ABLATION_PATH, index=False)
    sensitivity.to_csv(SENSITIVITY_PATH, index=False)
    beam_history.to_csv(BEAM_PATH, index=False)
    finalists.to_csv(FINALISTS_PATH, index=False)
    if len(oos):
        oos.to_csv(OOS_PATH, index=False)
    if len(phases):
        phases.to_csv(PHASE_PATH, index=False)
    if len(monte_carlo):
        monte_carlo.to_csv(MC_PATH, index=False)
    if len(start_runs):
        start_runs.to_csv(START_PATH, index=False)
    if len(stress):
        stress.to_csv(STRESS_PATH, index=False)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("baseline", baseline_full.metrics)
    print("exact equivalents", exact_equivalents)
    print("finalists meeting goal", int(finalists["meets_full_goal"].sum()) if len(finalists) else 0)
    if selected_payload is None:
        print("selected NONE")
    else:
        print("selected config", selected_payload["config"])
        print("selected full", selected_payload["full_metrics"])
        print("selected validation", selected_payload["validation_metrics"])
        print("selected holdout", selected_payload["holdout_metrics"])
        print("selected pruning", selected_payload["pruning"])
        print("selected robustness", selected_payload["robustness_gates"])
    print("summary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
