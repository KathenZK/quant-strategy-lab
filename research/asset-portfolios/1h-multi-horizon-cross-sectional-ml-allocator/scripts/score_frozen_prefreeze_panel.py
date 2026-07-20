from __future__ import annotations

import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
FREEZE_DIR = FAMILY_DIR / "artifacts/freeze"
PANEL_MANIFEST = FREEZE_DIR / "prefreeze_inference_panel_manifest_2026-07-18.json"
MODEL_MANIFEST = FREEZE_DIR / "bin-1h-mhcsml-v1-model-freeze-r4.json"
OUTPUT_DIR = FREEZE_DIR / "prefreeze_dry_inference_r4"
SCORES_PATH = OUTPUT_DIR / "scores.parquet"
DECISIONS_PATH = OUTPUT_DIR / "decisions.parquet"
LEGS_PATH = OUTPUT_DIR / "selected_legs.parquet"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def within_time_zscore(frame: pd.DataFrame, column: str) -> pd.Series:
    grouped = frame.groupby("ts", sort=False)[column]
    median = grouped.transform("median")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((frame[column] - median) / std).fillna(0.0).clip(-10.0, 10.0)


def predict_ensemble(
    frame: pd.DataFrame,
    models: list[dict[str, object]],
    features: list[str],
) -> np.ndarray:
    x = frame[features].astype("float32").replace([np.inf, -np.inf], np.nan)
    predictions: list[np.ndarray] = []
    for metadata in models:
        path = ROOT / str(metadata["model_path"])
        if sha256(path) != metadata["model_sha256"]:
            raise RuntimeError(f"model SHA mismatch: {path}")
        booster = lgb.Booster(model_file=str(path))
        predictions.append(
            booster.predict(x, num_iteration=int(metadata["best_iteration"]))
        )
    return np.mean(np.vstack(predictions), axis=0)


def main() -> None:
    panel_manifest = json.loads(PANEL_MANIFEST.read_text(encoding="utf-8"))
    model_manifest = json.loads(MODEL_MANIFEST.read_text(encoding="utf-8"))
    if panel_manifest.get("status") != "PASS" or panel_manifest.get("blockers"):
        raise RuntimeError("prefreeze inference panel is not PASS")
    if model_manifest.get("status") != "PASS":
        raise RuntimeError("frozen model manifest is not PASS")
    config = model_manifest["candidate_config"]
    if config["decision_frequency_hours"] != 4 or config["horizon_hours"] != 48:
        raise RuntimeError("unexpected frozen cadence or horizon")
    panel_path = ROOT / panel_manifest["panel_path"]
    if sha256(panel_path) != panel_manifest["panel_sha256"]:
        raise RuntimeError("prefreeze panel SHA mismatch")
    panel = pd.read_parquet(panel_path)
    panel["ts"] = pd.to_datetime(panel["ts"], utc=True)
    if panel["ts"].max() >= PROSPECTIVE_START:
        raise RuntimeError("prefreeze scoring input crossed prospective boundary")
    frame = panel.loc[
        panel["universe_main"]
        & (panel["ts"].dt.hour % config["decision_frequency_hours"] == 0)
    ].copy()
    model_groups: dict[str, list[dict[str, object]]] = {}
    for model in model_manifest["models"]:
        identity = str(model["identity"])
        group = identity.rsplit("_s", maxsplit=1)[0]
        model_groups.setdefault(group, []).append(model)
    expected = {
        "short_return_regression_stable_full",
        "short_mae_quantile_stable_full",
        "short_event_classification_stable_full",
        "short_return_classification_compact",
    }
    if set(model_groups) != expected:
        raise RuntimeError(f"unexpected frozen model groups: {sorted(model_groups)}")
    for name, models in model_groups.items():
        if len(models) != 4:
            raise RuntimeError(f"model group is not four-seed: {name}")
    feature_lists = {
        name: json.loads((ROOT / spec["path"]).read_text(encoding="utf-8"))
        for name, spec in model_manifest["feature_lists"].items()
    }
    frame["short_return_score"] = predict_ensemble(
        frame,
        model_groups["short_return_regression_stable_full"],
        feature_lists["stable_full"],
    )
    frame["short_mae_score"] = predict_ensemble(
        frame,
        model_groups["short_mae_quantile_stable_full"],
        feature_lists["stable_full"],
    )
    frame["short_event_score"] = predict_ensemble(
        frame,
        model_groups["short_event_classification_stable_full"],
        feature_lists["stable_full"],
    )
    frame["confirmation_score"] = predict_ensemble(
        frame,
        model_groups["short_return_classification_compact"],
        feature_lists["compact"],
    )
    frame["return_z_raw"] = within_time_zscore(frame, "short_return_score")
    frame["mae_z"] = within_time_zscore(frame, "short_mae_score")
    frame["event_z"] = within_time_zscore(frame, "short_event_score")
    frame["confirmation_z"] = within_time_zscore(frame, "confirmation_score")
    frame["return_z"] = (
        frame["return_z_raw"]
        + config["confirmation_weight"] * frame["confirmation_z"]
    )
    frame["raw_utility"] = (
        frame["return_z"]
        - config["mae_penalty"] * frame["mae_z"]
        - config["event_penalty"] * frame["event_z"]
    )
    frame["utility"] = within_time_zscore(frame, "raw_utility")
    frame["confirmation_pass"] = (
        True
        if config["confirmation_z_min"] is None
        else frame["confirmation_z"] >= config["confirmation_z_min"]
    )
    frame["utility_pass"] = frame["utility"] >= config["utility_z_threshold"]
    eligible = frame.loc[frame["confirmation_pass"] & frame["utility_pass"]]
    selected = (
        eligible.sort_values(
            ["ts", "utility", "symbol"], ascending=[True, False, True]
        )
        .groupby("ts", sort=False, group_keys=False)
        .head(config["max_positions"])
        .copy()
    )
    sleeve_exposure = (
        config["gross_exposure"]
        * config["decision_frequency_hours"]
        / config["horizon_hours"]
    )
    selected["side"] = "short"
    selected["entry_time"] = selected["ts"] + pd.Timedelta(hours=1)
    selected["planned_exit_time"] = selected["entry_time"] + pd.Timedelta(
        hours=config["horizon_hours"]
    )
    selected["sleeve_exposure"] = sleeve_exposure
    selected["leg_exposure"] = sleeve_exposure / selected.groupby("ts")[
        "symbol"
    ].transform("size")
    scheduled = pd.DataFrame(
        {"ts": sorted(frame["ts"].drop_duplicates().tolist())}
    )
    chosen = selected.groupby("ts", sort=False).agg(
        selected_symbols=("symbol", lambda values: ",".join(values)),
        position_count=("symbol", "size"),
        max_utility=("utility", "max"),
        mean_utility=("utility", "mean"),
        entry_time=("entry_time", "first"),
        planned_exit_time=("planned_exit_time", "first"),
    ).reset_index()
    decisions = scheduled.merge(chosen, on="ts", how="left", validate="one_to_one")
    decisions["active"] = decisions["selected_symbols"].notna()
    decisions["position_count"] = decisions["position_count"].fillna(0).astype(int)
    decisions["side"] = decisions["active"].map({True: "short", False: "flat"})
    decisions["sleeve_exposure"] = decisions["active"].astype(float) * sleeve_exposure
    score_columns = [
        "ts",
        "symbol",
        "short_return_score",
        "short_mae_score",
        "short_event_score",
        "confirmation_score",
        "return_z_raw",
        "confirmation_z",
        "return_z",
        "mae_z",
        "event_z",
        "raw_utility",
        "utility",
        "confirmation_pass",
        "utility_pass",
    ]
    leg_columns = [
        "ts",
        "symbol",
        "side",
        "entry_time",
        "planned_exit_time",
        "sleeve_exposure",
        "leg_exposure",
        "utility",
        "return_z",
        "mae_z",
        "event_z",
        "confirmation_z",
        "raw_utility",
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame[score_columns].to_parquet(SCORES_PATH, index=False, compression="zstd")
    decisions.to_parquet(DECISIONS_PATH, index=False, compression="zstd")
    selected[leg_columns].to_parquet(LEGS_PATH, index=False, compression="zstd")
    forbidden_tokens = ("label_", "trade_return", "pnl", "profit", "drawdown")
    output_columns = set(score_columns + leg_columns + decisions.columns.tolist())
    forbidden = sorted(
        name for name in output_columns if any(token in name for token in forbidden_tokens)
    )
    blockers: list[str] = []
    if forbidden:
        blockers.append("outcome_or_performance_columns_present")
    if decisions["ts"].max() >= PROSPECTIVE_START:
        blockers.append("prospective_rows_present")
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "role": "prefreeze feature-only dry inference",
        "candidate_config": config,
        "sleeve_exposure": sleeve_exposure,
        "model_manifest": str(MODEL_MANIFEST.relative_to(ROOT)),
        "model_manifest_sha256": sha256(MODEL_MANIFEST),
        "panel_manifest": str(PANEL_MANIFEST.relative_to(ROOT)),
        "panel_manifest_sha256": sha256(PANEL_MANIFEST),
        "scheduled_decisions": len(decisions),
        "active_decisions": int(decisions["active"].sum()),
        "selected_legs": len(selected),
        "first_ts": decisions["ts"].min().isoformat(),
        "last_ts": decisions["ts"].max().isoformat(),
        "outcome_or_performance_columns": forbidden,
        "freeze_gap_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "outputs": {
            "scores": {"path": str(SCORES_PATH.relative_to(ROOT)), "sha256": sha256(SCORES_PATH)},
            "decisions": {"path": str(DECISIONS_PATH.relative_to(ROOT)), "sha256": sha256(DECISIONS_PATH)},
            "selected_legs": {"path": str(LEGS_PATH.relative_to(ROOT)), "sha256": sha256(LEGS_PATH)},
        },
        "blockers": blockers,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    if blockers:
        raise RuntimeError(f"prefreeze dry inference blocked: {blockers}")


if __name__ == "__main__":
    main()
