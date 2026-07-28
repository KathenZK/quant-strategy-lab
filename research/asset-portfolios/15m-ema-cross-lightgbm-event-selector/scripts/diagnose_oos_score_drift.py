"""Post-reveal failure attribution: score distribution drift dev vs locked OOS.

Runs AFTER the one-shot reveal has already produced its verdict. This script
only characterizes why the frozen tau produced ~0 trades in the locked OOS
window (score distribution comparison). It must never be used to select a new
tau or any other parameter on the revealed window.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

import emax_common as ec
from train_event_models import feature_columns, score_events

QUANTILES = [0.50, 0.75, 0.90, 0.95, 0.99]


def stats(frame: pd.DataFrame, tau: float) -> dict:
    out: dict = {"events": int(len(frame))}
    if frame.empty:
        return out
    out["score_quantiles"] = {
        f"q{int(q * 100)}": round(float(frame["score"].quantile(q)), 4) for q in QUANTILES
    }
    out["frac_score_gt_tau"] = round(float((frame["score"] > tau).mean()), 6)
    out["n_score_gt_tau"] = int((frame["score"] > tau).sum())
    for col in ("p_tp", "p_sl", "p_timeout", "cost_atr"):
        out[f"{col}_mean"] = round(float(frame[col].mean()), 4)
    return out


def main() -> None:
    model_dir = ec.ARTIFACT_DIR / "model_v1"
    freeze = json.loads((model_dir / "freeze_manifest.json").read_text(encoding="utf-8"))
    tau = freeze["tau"]
    bracket = freeze["bracket"]
    k_tp, k_sl = ec.BRACKETS[bracket]

    oof = pd.read_parquet(model_dir / "oof_scores.parquet")
    oof = oof.loc[oof["in_trading_pool"]].copy()
    oof["entry_ts"] = pd.to_datetime(oof["entry_ts"], utc=True)
    confirm = oof.loc[oof["fold"] == oof["fold"].max()]
    tail_2025h2 = oof.loc[oof["entry_ts"] >= pd.Timestamp("2025-07-01", tz="UTC")]

    dataset = pd.read_parquet(ec.ARTIFACT_DIR / "event_dataset_oos_reveal.parquet")
    dataset["entry_ts"] = pd.to_datetime(dataset["entry_ts"], utc=True)
    oos = dataset.loc[
        (dataset["entry_ts"] >= ec.LOCKED_OOS_START)
        & (dataset["entry_ts"] < ec.LOCKED_OOS_END)
        & dataset["in_trading_pool"]
    ].copy()

    training = json.loads((model_dir / "training_report.json").read_text(encoding="utf-8"))
    features = feature_columns()
    report: dict = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "tau": tau,
        "bracket": bracket,
        "note": "failure attribution only; revealed window must not be used for tuning",
    }
    for side, name in ((1, "long"), (-1, "short")):
        model = joblib.load(model_dir / f"final_{name}.joblib")
        timeout_mean = training["final_models"][name]["timeout_mean_atr"]
        side_oos = oos.loc[oos["side"] == side].copy()
        scored = score_events(model, side_oos, features, k_tp, k_sl, timeout_mean)
        side_oos = pd.concat([side_oos.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)
        report[name] = {
            "dev_oof_2021_2025": stats(oof.loc[oof["side"] == side], tau),
            "confirm_fold_2025_full_year": stats(confirm.loc[confirm["side"] == side], tau),
            "dev_tail_2025h2": stats(tail_2025h2.loc[tail_2025h2["side"] == side], tau),
            "locked_oos_2026h1": stats(side_oos, tau),
        }

    output = model_dir / "oos_score_drift.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"drift report -> {output}")


if __name__ == "__main__":
    main()
