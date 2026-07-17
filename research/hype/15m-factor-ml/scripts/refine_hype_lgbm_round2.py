from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json

import numpy as np
import pandas as pd

from audit_hype_15m_factors import TRAIN_END_EXCLUSIVE, VALIDATION_END_EXCLUSIVE
from backtest_hype_lgbm import run_prediction_backtest
from hype_ml_common import ARTIFACTS_DIR, TripleBarrierConfig, write_json
from search_hype_lgbm_round2 import (
    base_backtest_config,
    feature_sets,
    gate_pass,
    prepare_label_frame,
    risk_configs,
    score_metrics,
    train_and_predict,
)


REGIME_COLUMNS = [
    "atr_percentile_672",
    "efficiency_ratio_48",
    "trend_strength_21_55",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refine HYPE LightGBM validation Pareto anchors without loading OOS."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument(
        "--factor-audit",
        type=Path,
        default=ARTIFACTS_DIR / "factor_audit_round2/factor_audit_summary.json",
    )
    parser.add_argument(
        "--single-factor-audit",
        type=Path,
        default=ARTIFACTS_DIR / "factor_audit_round2/single_factor_train_audit.csv",
    )
    parser.add_argument(
        "--detailed-trials",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_search/detailed_validation_trials.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_refinement",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def row_identity(row: pd.Series | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row["label_id"]),
        str(row["feature_set_id"]),
        str(row["model_spec.id"]),
    )


def choose_anchors(frame: pd.DataFrame, limit: int = 6) -> pd.DataFrame:
    enough = frame.loc[frame["metrics.trade_count"] >= 30].copy()
    high_pf = enough.loc[
        (enough["metrics.profit_factor"] >= 1.30)
        & (enough["metrics.max_drawdown"] <= 0.20)
    ].sort_values(["metrics.total_return", "metrics.win_rate"], ascending=False)
    high_win = enough.loc[
        (enough["metrics.win_rate"] >= 0.55)
        & (enough["metrics.max_drawdown"] <= 0.20)
    ].sort_values(["metrics.profit_factor", "metrics.total_return"], ascending=False)
    joint = enough.copy()
    joint["joint_deficit"] = (
        (0.55 - joint["metrics.win_rate"]).clip(lower=0.0) * 4.0
        + (1.30 - joint["metrics.profit_factor"]).clip(lower=0.0)
        + (joint["metrics.max_drawdown"] - 0.20).clip(lower=0.0) * 3.0
        + (-joint["metrics.total_return"]).clip(lower=0.0) * 2.0
    )
    joint = joint.sort_values(["joint_deficit", "selection_score"], ascending=[True, False])
    pool = pd.concat(
        [
            frame.sort_values("selection_score", ascending=False).head(20),
            high_pf.head(20),
            high_win.head(20),
            joint.head(20),
        ],
        ignore_index=True,
    )
    pool["identity"] = pool.apply(row_identity, axis=1)
    return pool.drop_duplicates("identity").head(limit).drop(columns="identity")


def config_from_row(row: pd.Series) -> tuple[TripleBarrierConfig, dict[str, object]]:
    label = TripleBarrierConfig(
        horizon_bars=int(row["label_config.horizon_bars"]),
        take_profit_atr=float(row["label_config.take_profit_atr"]),
        stop_loss_atr=float(row["label_config.stop_loss_atr"]),
        fee_rate_per_fill=float(row["label_config.fee_rate_per_fill"]),
        slippage_bps_per_fill=float(row["label_config.slippage_bps_per_fill"]),
        min_net_edge_bps=float(row["label_config.min_net_edge_bps"]),
    )
    spec: dict[str, object] = {
        "id": str(row["model_spec.id"]),
        "model_type": str(row["model_spec.model_type"]),
        "num_leaves": int(row["model_spec.num_leaves"]),
        "max_depth": int(row["model_spec.max_depth"]),
        "min_child_samples": int(row["model_spec.min_child_samples"]),
        "learning_rate": float(row["model_spec.learning_rate"]),
        "colsample_bytree": float(row["model_spec.colsample_bytree"]),
        "reg_alpha": float(row["model_spec.reg_alpha"]),
        "reg_lambda": float(row["model_spec.reg_lambda"]),
    }
    return label, spec


def regime_thresholds(train: pd.DataFrame) -> dict[str, float]:
    return {
        "atr_percentile_672_median": float(train["atr_percentile_672"].median()),
        "efficiency_ratio_48_median": float(train["efficiency_ratio_48"].median()),
    }


def apply_regime(
    predictions: pd.DataFrame,
    *,
    model_type: str,
    regime: str,
    thresholds: dict[str, float],
    horizon_bars: int,
) -> pd.DataFrame:
    working = predictions.copy()
    if model_type.startswith("dual_regression"):
        long_column, short_column, blocked = "pred_long_bps", "pred_short_bps", -1e9
    else:
        long_column, short_column, blocked = "p_long", "p_short", 0.0
    if regime == "none":
        pass
    elif regime == "low_vol":
        allowed = working["atr_percentile_672"] <= thresholds["atr_percentile_672_median"]
        working.loc[~allowed, [long_column, short_column]] = blocked
    elif regime == "high_efficiency":
        allowed = working["efficiency_ratio_48"] >= thresholds["efficiency_ratio_48_median"]
        working.loc[~allowed, [long_column, short_column]] = blocked
    elif regime == "trend_follow":
        working.loc[working["trend_strength_21_55"] <= 0.0, long_column] = blocked
        working.loc[working["trend_strength_21_55"] >= 0.0, short_column] = blocked
    elif regime == "trend_contrarian":
        working.loc[working["trend_strength_21_55"] >= 0.0, long_column] = blocked
        working.loc[working["trend_strength_21_55"] <= 0.0, short_column] = blocked
    elif regime == "low_vol_trend_follow":
        allowed = working["atr_percentile_672"] <= thresholds["atr_percentile_672_median"]
        working.loc[~allowed, [long_column, short_column]] = blocked
        working.loc[working["trend_strength_21_55"] <= 0.0, long_column] = blocked
        working.loc[working["trend_strength_21_55"] >= 0.0, short_column] = blocked
    else:
        raise ValueError(f"unsupported regime: {regime}")
    working.loc[working.index[-horizon_bars:], [long_column, short_column]] = np.nan
    return working


def asymmetric_thresholds(model_type: str) -> list[dict[str, float]]:
    if model_type.startswith("dual_regression"):
        edges = [-20.0, 0.0, 10.0, 20.0, 30.0, 40.0, 60.0, 80.0]
        return [
            {
                "long_edge_threshold_bps": long_edge,
                "short_edge_threshold_bps": short_edge,
                "edge_margin_bps": margin,
            }
            for long_edge in edges
            for short_edge in edges
            for margin in (0.0, 10.0, 30.0)
        ]
    probabilities = [0.45, 0.50, 0.525, 0.55, 0.575, 0.60, 0.65, 0.70, 0.75]
    return [
        {
            "long_threshold": long_threshold,
            "short_threshold": short_threshold,
            "probability_margin": margin,
        }
        for long_threshold in probabilities
        for short_threshold in probabilities
        for margin in (0.0, 0.03, 0.08)
    ]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    full = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    full["ts"] = pd.to_datetime(full["ts"], utc=True)
    pre_oos = full.loc[full["ts"] < VALIDATION_END_EXCLUSIVE].copy().reset_index(drop=True)
    if len(full) - len(pre_oos) <= 0:
        raise RuntimeError("locked OOS rows are not present in the source dataset")
    del full

    audit = json.loads(args.factor_audit.read_text(encoding="utf-8"))
    stats = pd.read_csv(args.single_factor_audit)
    sets = feature_sets(audit, stats)
    trials = pd.read_csv(args.detailed_trials)
    anchors = choose_anchors(trials)
    anchors.to_csv(args.output_dir / "refinement_anchors.csv", index=False)
    validation_full = pre_oos.loc[
        (pre_oos["ts"] >= TRAIN_END_EXCLUSIVE)
        & (pre_oos["ts"] < VALIDATION_END_EXCLUSIVE)
    ].copy()

    prediction_cache: dict[str, dict[str, object]] = {}
    threshold_rows: list[dict[str, object]] = []
    regimes = [
        "none",
        "low_vol",
        "high_efficiency",
        "trend_follow",
        "trend_contrarian",
        "low_vol_trend_follow",
    ]
    for anchor_number, (_, row) in enumerate(anchors.iterrows(), start=1):
        label, spec = config_from_row(row)
        feature_set_id = str(row["feature_set_id"])
        features = sets[feature_set_id]
        train, validation_labeled, _ = prepare_label_frame(pre_oos, label)
        validation_model = validation_full.merge(
            validation_labeled[
                ["ts", "direction_label", "long_outcome_bps", "short_outcome_bps"]
            ],
            on="ts",
            how="inner",
            validate="one_to_one",
        )
        predictions, predictive_metrics = train_and_predict(
            train,
            validation_model,
            features=features,
            spec=spec,
            horizon_bars=label.horizon_bars,
            seed=args.seed,
        )
        predictions = predictions.merge(
            validation_full[["ts", *REGIME_COLUMNS]],
            on="ts",
            how="left",
            validate="one_to_one",
        )
        thresholds = regime_thresholds(train)
        anchor_id = f"anchor_{anchor_number}"
        prediction_cache[anchor_id] = {
            "predictions": predictions,
            "label": label,
            "spec": spec,
            "features": features,
            "feature_set_id": feature_set_id,
            "regime_thresholds": thresholds,
            "predictive_metrics": predictive_metrics,
        }
        for regime in regimes:
            working = apply_regime(
                predictions,
                model_type=str(spec["model_type"]),
                regime=regime,
                thresholds=thresholds,
                horizon_bars=label.horizon_bars,
            )
            for threshold in asymmetric_thresholds(str(spec["model_type"])):
                config = base_backtest_config(
                    label, str(spec["model_type"]), threshold, {"max_leverage": 1.0}
                )
                _, metrics = run_prediction_backtest(working, config)
                threshold_rows.append(
                    {
                        "anchor_id": anchor_id,
                        "label_id": str(row["label_id"]),
                        "label_config": asdict(label),
                        "feature_set_id": feature_set_id,
                        "features": features,
                        "model_spec": spec,
                        "predictive_metrics": predictive_metrics,
                        "regime": regime,
                        "regime_thresholds": thresholds,
                        "threshold": threshold,
                        "metrics": metrics,
                        "selection_score": score_metrics(metrics),
                        "gate_pass": gate_pass(metrics),
                    }
                )
        print(f"asymmetric threshold complete {anchor_number}/{len(anchors)}", flush=True)

    threshold_frame = pd.json_normalize(threshold_rows)
    threshold_frame.to_csv(args.output_dir / "asymmetric_threshold_trials.csv", index=False)
    frontier = sorted(
        threshold_rows,
        key=lambda item: (bool(item["gate_pass"]), float(item["selection_score"])),
        reverse=True,
    )[:100]

    risk_rows: list[dict[str, object]] = []
    for item in frontier:
        cached = prediction_cache[str(item["anchor_id"])]
        label = cached["label"]
        spec = cached["spec"]
        working = apply_regime(
            cached["predictions"],
            model_type=str(spec["model_type"]),
            regime=str(item["regime"]),
            thresholds=cached["regime_thresholds"],
            horizon_bars=label.horizon_bars,
        )
        for risk in risk_configs():
            config = base_backtest_config(
                label,
                str(spec["model_type"]),
                item["threshold"],
                risk,
            )
            trades, metrics = run_prediction_backtest(working, config)
            risk_rows.append(
                {
                    **{key: value for key, value in item.items() if key != "metrics"},
                    "risk": risk,
                    "metrics": metrics,
                    "selection_score": score_metrics(metrics),
                    "gate_pass": gate_pass(metrics),
                    "trade_fingerprint": (
                        f"{len(trades)}:{trades['signal_ts'].min() if len(trades) else 'none'}:"
                        f"{trades['signal_ts'].max() if len(trades) else 'none'}"
                    ),
                }
            )

    risk_frame = pd.json_normalize(risk_rows)
    risk_frame.to_csv(args.output_dir / "refined_risk_trials.csv", index=False)
    best = max(
        risk_rows,
        key=lambda item: (bool(item["gate_pass"]), float(item["selection_score"])),
    )
    summary = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "selection_scope": "train + validation only",
        "anchor_count": len(anchors),
        "asymmetric_threshold_trial_count": len(threshold_rows),
        "risk_trial_count": len(risk_rows),
        "validation_gate_pass_count": sum(bool(item["gate_pass"]) for item in risk_rows),
        "best_validation": best,
        "oos_rows_loaded_into_selection_frame": 0,
        "status": "refined prefit candidate; OOS not revealed",
        "next_gate": "walk-forward, seed, cost, and parameter-neighborhood audit",
    }
    write_json(args.output_dir / "refinement_summary.json", summary)
    write_json(
        args.output_dir / "prefit_candidate_refined.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "candidate": best,
            "validation_gate_pass": bool(best["gate_pass"]),
            "oos_revealed": False,
        },
    )
    print(
        json.dumps(
            {
                "anchors": len(anchors),
                "threshold_trials": len(threshold_rows),
                "risk_trials": len(risk_rows),
                "validation_gate_pass_count": summary["validation_gate_pass_count"],
                "best": {
                    "label_id": best["label_id"],
                    "model": best["model_spec"]["id"],
                    "feature_set": best["feature_set_id"],
                    "regime": best["regime"],
                    "threshold": best["threshold"],
                    "risk": best["risk"],
                    "metrics": best["metrics"],
                },
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
