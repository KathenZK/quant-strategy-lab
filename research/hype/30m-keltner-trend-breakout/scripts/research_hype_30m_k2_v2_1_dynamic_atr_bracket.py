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
import research_hype_30m_k2_v2_full_ablation_and_tune as tune  # noqa: E402


RUN_DATE = "2026-07-10"
ARTIFACT_DIR = base.ARTIFACT_DIR
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_{RUN_DATE}.json"
SEARCH_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_search_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_oos_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_mc_{RUN_DATE}.csv"
START_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_start_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_phase_{RUN_DATE}.csv"
STRESS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_stress_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_dynamic_atr_bracket_trades_{RUN_DATE}.csv"

RETURN_RETENTION_FLOOR = 0.80
ATR_SOURCES = ("atr10", "atr96")
TP_MULTS = (6.0, 7.5, 9.0, 10.5, 12.0)
TP_FLOORS = (0.06, 0.08)
TP_CAPS = (0.10, 0.12, 0.15)
SL_MULTS = (1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0)
SL_FLOORS = (0.015, 0.020)
SL_CAPS = (0.025, 0.030, 0.035)


def v21_config() -> base.StrategyConfig:
    return replace(
        base.StrategyConfig(),
        h1_ema_slow=44,
        h1_slope_lag=5,
        leverage_atr=84,
        atr_target_pct=0.027,
        min_leverage=0.0,
    )


def v21_features(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    cfg: base.StrategyConfig,
) -> pd.DataFrame:
    return tune.build_logic_variant(
        b30,
        h1,
        cfg,
        regime_mode="no_close",
        use_opposite_exclusion=False,
    )


def variant_label(execution: strict.ExecutionConfig) -> str:
    tp = (
        "fixed"
        if execution.dynamic_tp_atr_mult is None
        else f"{execution.dynamic_tp_atr_mult:g}x_{execution.dynamic_tp_floor_pct:g}_{execution.dynamic_tp_cap_pct:g}"
    )
    sl = (
        "fixed"
        if execution.dynamic_sl_atr_mult is None
        else f"{execution.dynamic_sl_atr_mult:g}x_{execution.dynamic_sl_floor_pct:g}_{execution.dynamic_sl_cap_pct:g}"
    )
    return f"{execution.bracket_atr_column}_tp_{tp}_sl_{sl}"


def execution_variants() -> list[strict.ExecutionConfig]:
    baseline = strict.ExecutionConfig()
    variants: dict[str, strict.ExecutionConfig] = {"fixed_baseline": baseline}
    for source in ATR_SOURCES:
        for mult in TP_MULTS:
            for floor in TP_FLOORS:
                for cap in TP_CAPS:
                    if floor > cap:
                        continue
                    execution = replace(
                        baseline,
                        bracket_atr_column=source,
                        dynamic_tp_atr_mult=mult,
                        dynamic_tp_floor_pct=floor,
                        dynamic_tp_cap_pct=cap,
                    )
                    variants[variant_label(execution)] = execution
        for mult in SL_MULTS:
            for floor in SL_FLOORS:
                for cap in SL_CAPS:
                    if floor > cap:
                        continue
                    execution = replace(
                        baseline,
                        bracket_atr_column=source,
                        dynamic_sl_atr_mult=mult,
                        dynamic_sl_floor_pct=floor,
                        dynamic_sl_cap_pct=cap,
                    )
                    variants[variant_label(execution)] = execution

        for tp_mult in (7.5, 9.0, 10.5):
            for tp_floor in TP_FLOORS:
                for tp_cap in (0.10, 0.12):
                    for sl_mult in (1.75, 2.25, 2.75):
                        for sl_floor in SL_FLOORS:
                            for sl_cap in (0.025, 0.030):
                                execution = replace(
                                    baseline,
                                    bracket_atr_column=source,
                                    dynamic_tp_atr_mult=tp_mult,
                                    dynamic_tp_floor_pct=tp_floor,
                                    dynamic_tp_cap_pct=tp_cap,
                                    dynamic_sl_atr_mult=sl_mult,
                                    dynamic_sl_floor_pct=sl_floor,
                                    dynamic_sl_cap_pct=sl_cap,
                                )
                                variants[variant_label(execution)] = execution
    return list(variants.values())


def log_retention(candidate_return: float, baseline_return: float) -> float:
    candidate_log = np.log(max(1e-12, 1.0 + candidate_return / 100.0))
    baseline_log = np.log(max(1e-12, 1.0 + baseline_return / 100.0))
    return float(candidate_log / baseline_log) if baseline_log > 0.0 else 0.0


def split_score(
    candidate: strict.StrictResult,
    baseline: strict.StrictResult,
) -> float:
    metrics = candidate.metrics
    base_metrics = baseline.metrics
    if metrics["return_pct"] <= -99.0 or metrics["trades"] < 0.5 * base_metrics["trades"]:
        return -1e9
    retention = log_retention(metrics["return_pct"], base_metrics["return_pct"])
    win_gain = (metrics["win_rate_pct"] - base_metrics["win_rate_pct"]) / 5.0
    mdd_gain = (
        abs(base_metrics["max_drawdown_pct"]) - abs(metrics["max_drawdown_pct"])
    ) / max(1e-12, abs(base_metrics["max_drawdown_pct"]))
    return float(retention + 1.5 * win_gain + 2.0 * mdd_gain)


def bracket_stats(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {}
    return {
        "entry_atr_pct": {
            "min": float(trades["entry_atr_pct"].min()),
            "median": float(trades["entry_atr_pct"].median()),
            "max": float(trades["entry_atr_pct"].max()),
        },
        "tp_pct": {
            "min": float(trades["tp_pct"].min()),
            "median": float(trades["tp_pct"].median()),
            "max": float(trades["tp_pct"].max()),
            "unique": int(trades["tp_pct"].nunique()),
        },
        "sl_pct": {
            "min": float(trades["sl_pct"].min()),
            "median": float(trades["sl_pct"].median()),
            "max": float(trades["sl_pct"].max()),
            "unique": int(trades["sl_pct"].nunique()),
        },
    }


def run_search(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[
    pd.DataFrame,
    dict[str, Any] | None,
    dict[str, strict.StrictResult],
    dict[str, dict[str, Any]],
]:
    baseline_execution = strict.ExecutionConfig()
    baseline_results = {
        "full": strict.simulate(
            "dynamic_fixed_full",
            features,
            funding,
            cfg,
            baseline_execution,
            start_ts=start,
            end_ts=end,
        ),
        "train": strict.simulate(
            "dynamic_fixed_train",
            features,
            funding,
            cfg,
            baseline_execution,
            start_ts=start,
            end_ts=tune.TRAIN_END,
        ),
        "validation": strict.simulate(
            "dynamic_fixed_validation",
            features,
            funding,
            cfg,
            baseline_execution,
            start_ts=tune.VALIDATION_START,
            end_ts=tune.VALIDATION_END,
        ),
        "holdout": strict.simulate(
            "dynamic_fixed_holdout",
            features,
            funding,
            cfg,
            baseline_execution,
            start_ts=tune.HOLDOUT_START,
            end_ts=end,
        ),
    }
    rows = []
    evaluated: dict[str, Any] = {}
    for execution in execution_variants():
        label = variant_label(execution)
        full = strict.simulate(
            f"{label}_full",
            features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=end,
        )
        train = strict.simulate(
            f"{label}_train",
            features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=tune.TRAIN_END,
        )
        validation = strict.simulate(
            f"{label}_validation",
            features,
            funding,
            cfg,
            execution,
            start_ts=tune.VALIDATION_START,
            end_ts=tune.VALIDATION_END,
        )
        retention = full.metrics["return_pct"] / baseline_results["full"].metrics["return_pct"]
        validation_retention = (
            validation.metrics["return_pct"]
            / baseline_results["validation"].metrics["return_pct"]
        )
        meets_full_goal = bool(
            full.metrics["win_rate_pct"] > baseline_results["full"].metrics["win_rate_pct"]
            and full.metrics["max_drawdown_pct"] > baseline_results["full"].metrics["max_drawdown_pct"]
            and retention >= RETURN_RETENTION_FLOOR
        )
        meets_goal = bool(
            meets_full_goal
            and validation.metrics["win_rate_pct"]
            >= baseline_results["validation"].metrics["win_rate_pct"]
            and validation.metrics["max_drawdown_pct"]
            >= baseline_results["validation"].metrics["max_drawdown_pct"]
            and validation_retention >= 0.70
        )
        score = 0.45 * split_score(train, baseline_results["train"]) + 0.55 * split_score(
            validation,
            baseline_results["validation"],
        )
        row = {
            "variant": label,
            **asdict(execution),
            "score": score,
            "full_return_pct": full.metrics["return_pct"],
            "full_mdd_pct": full.metrics["max_drawdown_pct"],
            "full_win_rate_pct": full.metrics["win_rate_pct"],
            "full_sharpe": full.metrics["sharpe"],
            "full_trades": full.metrics["trades"],
            "return_retention": retention,
            "train_return_pct": train.metrics["return_pct"],
            "train_mdd_pct": train.metrics["max_drawdown_pct"],
            "train_win_rate_pct": train.metrics["win_rate_pct"],
            "validation_return_pct": validation.metrics["return_pct"],
            "validation_mdd_pct": validation.metrics["max_drawdown_pct"],
            "validation_win_rate_pct": validation.metrics["win_rate_pct"],
            "validation_return_retention": validation_retention,
            "meets_full_goal": meets_full_goal,
            "meets_goal": meets_goal,
        }
        rows.append(row)
        evaluated[label] = {
            "execution": execution,
            "full": full,
            "train": train,
            "validation": validation,
            "row": row,
        }
    frame = pd.DataFrame(rows).sort_values(
        ["meets_goal", "score"],
        ascending=[False, False],
    )
    feasible = frame.loc[frame["meets_goal"]]
    if feasible.empty:
        selected = None
    else:
        high_retention = feasible.loc[feasible["return_retention"].ge(0.90)]
        pool = high_retention if not high_retention.empty else feasible
        selected_row = pool.sort_values(
            ["full_mdd_pct", "return_retention", "score"],
            ascending=[False, False, False],
        ).iloc[0]
        selected = evaluated[str(selected_row["variant"])]
    return frame, selected, baseline_results, evaluated


def phase_feature_sets(
    m1: pd.DataFrame,
    cfg: base.StrategyConfig,
) -> tuple[dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
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
        phase: v21_features(frame, bars1h[0], cfg)
        for phase, frame in bars30.items()
    }
    phase1h = {
        phase: v21_features(bars30[0], frame, cfg)
        for phase, frame in bars1h.items()
    }
    return phase30, phase1h


def robustness(
    selected: dict[str, Any],
    features: pd.DataFrame,
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    execution = selected["execution"]
    full = selected["full"]
    holdout = strict.simulate(
        "dynamic_selected_holdout",
        features,
        funding,
        cfg,
        execution,
        start_ts=tune.HOLDOUT_START,
        end_ts=end,
    )
    oos = strict.run_rolling_oos(features, funding, cfg, execution, start, end)
    trade_mc = strict.run_trade_mc(full.trades, 5000)
    mc2 = trade_mc.loc[trade_mc["mc_type"].eq("mc2_shuffle")]
    mc3 = trade_mc.loc[trade_mc["mc_type"].eq("mc3_bootstrap")]
    mc2_p05 = float(mc2["max_drawdown_pct"].quantile(0.05))
    mc2_limit = -1.5 * abs(float(full.metrics["max_drawdown_pct"]))
    daily = full.equity.resample("1D").last().pct_change().dropna()
    significance = strict.probabilistic_sharpe(daily)
    significance["dsr_n1000"] = strict.deflated_sharpe(daily, 1000)
    starts = strict.run_start_sensitivity(
        features,
        funding,
        cfg,
        execution,
        start,
        end,
    )
    cagr_mean = float(starts["cagr_pct"].mean())
    start_cv = float(starts["cagr_pct"].std(ddof=1) / abs(cagr_mean))
    phase30, phase1h = phase_feature_sets(m1, cfg)
    phase_starts = [pd.Timestamp(value) for value in starts["start_ts"].iloc[:20]]
    phases = strict.run_phase_gate(
        phase30,
        phase1h,
        funding,
        cfg,
        execution,
        phase_starts,
        end,
    )
    phase_summary = {
        "30m": strict.phase_gate_status(phases, "30m"),
        "1h": strict.phase_gate_status(phases, "1h"),
    }
    stress = strict.run_stress(features, funding, cfg, execution, start, end)
    summary = {
        "holdout": {"metrics": holdout.metrics, "slices": holdout.slices},
        "rolling_oos": {
            "windows": int(len(oos)),
            "positive_fraction": float(oos["return_pct"].gt(0.0).mean()),
            "median_return_pct": float(oos["return_pct"].median()),
            "zero_trade_windows": int(oos["trades"].eq(0).sum()),
        },
        "monte_carlo": {
            "status": "pass" if mc2_p05 >= mc2_limit else "fail",
            "mc2_mdd_p05_pct": mc2_p05,
            "mc2_mdd_min_pct": float(mc2["max_drawdown_pct"].min()),
            "mc2_mdd_limit_pct": mc2_limit,
            "mc3_return_p05_pct": float(mc3["return_pct"].quantile(0.05)),
        },
        "significance": significance,
        "start_time": {
            "starts": int(len(starts)),
            "positive_fraction": float(starts["return_pct"].gt(0.0).mean()),
            "cagr_cv": start_cv,
        },
        "phase": phase_summary,
    }
    return summary, {
        "oos": oos,
        "mc": trade_mc,
        "starts": starts,
        "phases": phases,
        "stress": stress,
    }


def serializable_result(result: strict.StrictResult) -> dict[str, Any]:
    return {
        "metrics": result.metrics,
        "slices": result.slices,
        "bracket_stats": bracket_stats(result.trades),
    }


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
    funding_args = type("FundingArgs", (), {"refresh_data": False, "timeout": 45.0})()
    m1 = base.load_or_fetch_1m(args)
    funding = strict.load_or_fetch_funding(funding_args, m1)
    cfg = v21_config()
    b30 = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)[0]
    h1 = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)[0]
    features = v21_features(b30, h1, cfg)
    start = strict.ready_start(features)
    end = b30.index.max() + pd.Timedelta(minutes=30)

    search, selected, baseline, evaluated = run_search(
        features,
        funding,
        cfg,
        start,
        end,
    )
    selected_payload: dict[str, Any] | None = None
    near_miss_payload: dict[str, Any] | None = None
    robustness_payload: dict[str, Any] | None = None
    target = selected
    if target is None:
        near_rows = search.loc[search["meets_full_goal"]].sort_values(
            ["score", "return_retention"],
            ascending=[False, False],
        )
        if not near_rows.empty:
            target = evaluated[str(near_rows.iloc[0]["variant"])]
    if target is not None:
        robustness_payload, frames = robustness(
            target,
            features,
            m1,
            funding,
            cfg,
            start,
            end,
        )
        holdout = strict.simulate(
            "dynamic_selected_holdout_export",
            features,
            funding,
            cfg,
            target["execution"],
            start_ts=tune.HOLDOUT_START,
            end_ts=end,
        )
        target["full"].trades.to_csv(TRADES_PATH, index=False)
        frames["oos"].to_csv(OOS_PATH, index=False)
        frames["mc"].to_csv(MC_PATH, index=False)
        frames["starts"].to_csv(START_PATH, index=False)
        frames["phases"].to_csv(PHASE_PATH, index=False)
        frames["stress"].to_csv(STRESS_PATH, index=False)
        payload = {
            "execution": asdict(target["execution"]),
            "full": serializable_result(target["full"]),
            "train": serializable_result(target["train"]),
            "validation": serializable_result(target["validation"]),
            "holdout": serializable_result(holdout),
            "row": target["row"],
        }
        if selected is not None:
            selected_payload = payload
        else:
            near_miss_payload = payload

    summary = {
        "strategy": "HYPE-30M-Keltner-Trend-Breakout-V2.1",
        "study": "dynamic ATR TP/SL bracket",
        "run_date": RUN_DATE,
        "objective": {
            "higher_win_rate": True,
            "lower_mdd": True,
            "full_return_retention_floor": RETURN_RETENTION_FLOOR,
            "validation_return_retention_floor": 0.70,
        },
        "entry_atr_context": {
            "atr84_median_pct": 0.010712,
            "fixed_tp_equivalent_atr": 9.335,
            "fixed_sl_equivalent_atr": 2.334,
        },
        "baseline": {
            split: serializable_result(result)
            for split, result in baseline.items()
        },
        "search": {
            "variants": int(len(search)),
            "meeting_goal": int(search["meets_goal"].sum()),
        },
        "selected": selected_payload,
        "near_miss": near_miss_payload,
        "robustness": robustness_payload,
        "decision": (
            "dynamic_candidate_found"
            if selected_payload is not None
            else "keep_fixed_tp_sl_no_dynamic_candidate_met_constraints"
        ),
        "selection_warning": "History is not true OOS; dynamic candidate must not replace V2.1 without explicit version registration.",
    }
    search.to_csv(SEARCH_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print("baseline", baseline["full"].metrics)
    print("search variants", len(search), "meeting goal", int(search["meets_goal"].sum()))
    if selected_payload is None:
        print("selected NONE; keep fixed TP/SL")
        if near_miss_payload is not None:
            print("near miss execution", near_miss_payload["execution"])
            print("near miss full", near_miss_payload["full"])
            print("near miss validation", near_miss_payload["validation"])
            print("near miss robustness", robustness_payload)
        print(search.head(10).to_string(index=False))
    else:
        print("selected execution", selected_payload["execution"])
        print("selected full", selected_payload["full"])
        print("selected validation", selected_payload["validation"])
        print("selected holdout", selected_payload["holdout"])
        print("robustness", robustness_payload)
    print("summary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
