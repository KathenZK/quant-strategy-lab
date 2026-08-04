from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/multi-timeframe-pullback-trend-campaign"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
V0_PATH = FAMILY_DIR / "scripts/research_continuation_meter_v0.py"


def load_v0() -> Any:
    spec = importlib.util.spec_from_file_location("bin_mtf_ptc_continuation_v0_audit", V0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load V0: {V0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fit_probability(dev: pd.DataFrame, val: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, Any]:
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    model.fit(dev[features], dev["label"].astype(int))
    return model.predict_proba(val[features])[:, 1], model


def subgroup_metrics(val: pd.DataFrame, probability: np.ndarray, group_name: str, group_values: pd.Series) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    work = val.copy()
    work["probability"] = probability
    work["group"] = group_values.astype(str).to_numpy()
    for group, part in work.groupby("group"):
        if len(part) < 30 or part["label"].nunique() < 2:
            continue
        low = part["probability"].quantile(0.2)
        high = part["probability"].quantile(0.8)
        rows.append({
            "group_type": group_name,
            "group": group,
            "events": int(len(part)),
            "base_rate": float(part["label"].mean()),
            "auc": float(roc_auc_score(part["label"], part["probability"])),
            "top_bottom_spread": float(part.loc[part["probability"].ge(high), "label"].mean() - part.loc[part["probability"].le(low), "label"].mean()),
        })
    return rows


def main() -> None:
    v0 = load_v0()
    loader = v0.load_module()
    frames, _ = loader.load_assets()
    summary: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    ablations: list[dict[str, Any]] = []
    coefficients: list[dict[str, Any]] = []
    for asset in v0.ASSETS:
        hourly = frames[asset]
        events = v0.build_events(hourly, 24)
        for horizon in v0.LABEL_HOURS:
            work = events.copy()
            work["label"] = v0.label_events(work, hourly, horizon)
            dev_end, val_start, val_end = v0.SPLITS[asset]
            dev = work.loc[(work.index <= dev_end - pd.Timedelta(days=14)) & work["label"].notna()].copy()
            val = work.loc[(work.index >= val_start) & (work.index <= val_end - pd.Timedelta(hours=horizon)) & work["label"].notna()].copy()
            features = list(v0.FEATURES)
            probability, model = fit_probability(dev, val, features)
            baseline_probability = np.full(len(val), float(dev["label"].mean()))
            summary.append({
                "asset": asset,
                "onset_hours": 24,
                "label_hours": horizon,
                "events": int(len(val)),
                "auc": float(roc_auc_score(val["label"], probability)),
                "brier": float(brier_score_loss(val["label"], probability)),
                "baseline_brier": float(brier_score_loss(val["label"], baseline_probability)),
                "brier_skill": float(1.0 - brier_score_loss(val["label"], probability) / brier_score_loss(val["label"], baseline_probability)),
            })
            for row in subgroup_metrics(val, probability, "side", val["direction"].map({1.0: "long", -1.0: "short"})):
                groups.append({"asset": asset, "label_hours": horizon, **row})
            for row in subgroup_metrics(val, probability, "year", pd.Series(val.index.year, index=val.index)):
                groups.append({"asset": asset, "label_hours": horizon, **row})
            logistic = model.named_steps["logisticregression"]
            for feature, value in zip(features, logistic.coef_[0], strict=True):
                coefficients.append({"asset": asset, "label_hours": horizon, "feature": feature, "standardized_coefficient": float(value)})
            full_auc = float(roc_auc_score(val["label"], probability))
            for omitted in features:
                subset = [feature for feature in features if feature != omitted]
                ablated_probability, _ = fit_probability(dev, val, subset)
                ablated_auc = float(roc_auc_score(val["label"], ablated_probability))
                ablations.append({"asset": asset, "label_hours": horizon, "omitted_feature": omitted, "full_auc": full_auc, "ablated_auc": ablated_auc, "auc_delta_full_minus_ablated": full_auc - ablated_auc})
    frames_out = {
        "summary": pd.DataFrame(summary),
        "subgroups": pd.DataFrame(groups),
        "ablations": pd.DataFrame(ablations),
        "coefficients": pd.DataFrame(coefficients),
    }
    for name, frame in frames_out.items():
        frame.to_csv(ARTIFACT_DIR / f"binance_mtf_ptc_continuation_meter_v0_{name}_audit_2026-08-03.csv", index=False)
    payload = {name: frame.to_dict(orient="records") for name, frame in frames_out.items()}
    (ARTIFACT_DIR / "binance_mtf_ptc_continuation_meter_v0_audit_2026-08-03.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(frames_out["summary"].to_string(index=False))
    print("\nSUBGROUPS")
    print(frames_out["subgroups"].to_string(index=False))
    print("\nTOP ABLATION DELTAS")
    print(frames_out["ablations"].sort_values("auc_delta_full_minus_ablated", ascending=False).groupby(["asset", "label_hours"]).head(3).to_string(index=False))


if __name__ == "__main__":
    main()
