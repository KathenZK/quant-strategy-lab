from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hype_ml_common import ARTIFACTS_DIR, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize one validation-passing Round 2 trial for prefit audit."
    )
    parser.add_argument(
        "--trials",
        type=Path,
        default=(
            ARTIFACTS_DIR
            / "model_round2_expanded_search/detailed_validation_trials.csv"
        ),
    )
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--prefer-most-trades",
        action="store_true",
        help="Select maximum trade count before validation selection score.",
    )
    return parser.parse_args()


def scalar(row: pd.Series, key: str, default: Any = None) -> Any:
    if key not in row or pd.isna(row[key]):
        return default
    value = row[key]
    return value.item() if isinstance(value, np.generic) else value


def prefixed(row: pd.Series, prefix: str) -> dict[str, Any]:
    return {
        key.removeprefix(prefix): scalar(row, key)
        for key in row.index
        if key.startswith(prefix) and not pd.isna(row[key])
    }


def main() -> None:
    args = parse_args()
    trials = pd.read_csv(args.trials)
    eligible = trials.loc[
        trials["gate_pass"].fillna(False).astype(bool)
        & trials["model_spec.id"].eq(args.model_id)
    ].copy()
    if eligible.empty:
        raise RuntimeError(f"no validation-passing row for model {args.model_id}")
    order = (
        ["metrics.trade_count", "selection_score"]
        if args.prefer_most_trades
        else ["selection_score", "metrics.trade_count"]
    )
    row = eligible.sort_values(order, ascending=False).iloc[0]
    model_type = str(row["model_spec.model_type"])
    if model_type.startswith("dual_regression"):
        threshold = {
            "edge_threshold_bps": float(row["threshold.edge_threshold_bps"]),
            "edge_margin_bps": float(row["threshold.edge_margin_bps"]),
        }
    else:
        threshold = {
            "long_threshold": float(row["threshold.long_threshold"]),
            "short_threshold": float(row["threshold.short_threshold"]),
            "probability_margin": float(row["threshold.probability_margin"]),
        }
    risk = {
        "risk_per_trade": scalar(row, "risk.risk_per_trade"),
        "max_leverage": float(scalar(row, "risk.max_leverage", 1.0)),
    }
    label_config = prefixed(row, "label_config.")
    label_config["horizon_bars"] = int(label_config["horizon_bars"])
    for key in (
        "take_profit_atr",
        "stop_loss_atr",
        "fee_rate_per_fill",
        "slippage_bps_per_fill",
        "min_net_edge_bps",
    ):
        label_config[key] = float(label_config[key])
    model_spec = prefixed(row, "model_spec.")
    for key in ("num_leaves", "max_depth", "min_child_samples"):
        model_spec[key] = int(model_spec[key])
    for key in (
        "learning_rate",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
    ):
        model_spec[key] = float(model_spec[key])
    candidate = {
        "label_id": str(row["label_id"]),
        "label_config": label_config,
        "feature_set_id": str(row["feature_set_id"]),
        "features": list(ast.literal_eval(str(row["features"]))),
        "model_spec": model_spec,
        "predictive_metrics": prefixed(row, "predictive_metrics."),
        "regime": "none",
        "regime_thresholds": {},
        "threshold": threshold,
        "risk": risk,
        "metrics": prefixed(row, "metrics."),
        "selection_score": float(row["selection_score"]),
        "gate_pass": bool(row["gate_pass"]),
        "trial_source": str(args.trials),
    }
    write_json(
        args.output,
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "candidate": candidate,
            "validation_gate_pass": True,
            "oos_revealed": False,
        },
    )
    print(
        {
            "output": str(args.output),
            "model": candidate["model_spec"]["id"],
            "trade_count": candidate["metrics"]["trade_count"],
            "selection_score": candidate["selection_score"],
        }
    )


if __name__ == "__main__":
    main()
