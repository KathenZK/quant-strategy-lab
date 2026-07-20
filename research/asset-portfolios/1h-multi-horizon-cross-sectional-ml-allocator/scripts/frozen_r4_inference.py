from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import joblib
import numpy as np
import pandas as pd


FORBIDDEN_INPUT_TOKENS = (
    "label_",
    "target_",
    "future_",
    "trade_return",
    "realized_return",
    "pnl",
    "profit",
    "mfe",
)
FORBIDDEN_OUTPUT_TOKENS = FORBIDDEN_INPUT_TOKENS + ("drawdown",)
ALLOWED_MAE_COLUMNS = {"short_mae_score", "mae_z"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def outcome_columns(
    columns: list[str] | pd.Index, *, output: bool = False
) -> list[str]:
    tokens = FORBIDDEN_OUTPUT_TOKENS if output else FORBIDDEN_INPUT_TOKENS
    forbidden: list[str] = []
    for value in columns:
        name = str(value).lower()
        if name in ALLOWED_MAE_COLUMNS:
            continue
        if any(token in name for token in tokens):
            forbidden.append(str(value))
    return sorted(forbidden)


def within_time_zscore(frame: pd.DataFrame, column: str) -> pd.Series:
    grouped = frame.groupby("ts", sort=False)[column]
    median = grouped.transform("median")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((frame[column] - median) / std).fillna(0.0).clip(-10.0, 10.0)


def predict_ensemble(
    frame: pd.DataFrame,
    models: list[dict[str, Any]],
    features: list[str],
    *,
    root: Path,
) -> np.ndarray:
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise RuntimeError(f"frozen features missing: {missing[:20]}")
    x = frame[features].astype("float32").replace([np.inf, -np.inf], np.nan)
    predictions: list[np.ndarray] = []
    for metadata in models:
        path = root / str(metadata["model_path"])
        if sha256(path) != metadata["model_sha256"]:
            raise RuntimeError(f"model SHA mismatch: {path}")
        booster = lgb.Booster(model_file=str(path))
        predictions.append(
            booster.predict(x, num_iteration=int(metadata["best_iteration"]))
        )
    return np.mean(np.vstack(predictions), axis=0)


def load_frozen_contract(
    *, root: Path, model_manifest_path: Path
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, list[str]]]:
    manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("blockers"):
        raise RuntimeError("frozen model manifest is not PASS")
    config = manifest["candidate_config"]
    if config["decision_frequency_hours"] != 4 or config["horizon_hours"] != 48:
        raise RuntimeError("unexpected frozen cadence or horizon")
    model_groups: dict[str, list[dict[str, Any]]] = {}
    for model in manifest["models"]:
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
    if any(len(models) != 4 for models in model_groups.values()):
        raise RuntimeError("every frozen model group must contain four seeds")
    feature_lists = {
        name: json.loads((root / spec["path"]).read_text(encoding="utf-8"))
        for name, spec in manifest["feature_lists"].items()
    }
    return manifest, model_groups, feature_lists


def score_r4_panel(
    panel: pd.DataFrame,
    *,
    root: Path,
    model_manifest_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    forbidden_input = outcome_columns(panel.columns)
    if forbidden_input:
        raise RuntimeError(
            f"feature-only scorer received outcome columns: {forbidden_input}"
        )
    manifest, groups, feature_lists = load_frozen_contract(
        root=root, model_manifest_path=model_manifest_path
    )
    config = manifest["candidate_config"]
    frame = panel.loc[
        panel["universe_main"].astype(bool)
        & (panel["ts"].dt.hour % config["decision_frequency_hours"] == 0)
    ].copy()
    if frame.empty:
        raise RuntimeError("no scheduled rows in feature-only panel")
    frame["short_return_score"] = predict_ensemble(
        frame,
        groups["short_return_regression_stable_full"],
        feature_lists["stable_full"],
        root=root,
    )
    frame["short_mae_score"] = predict_ensemble(
        frame,
        groups["short_mae_quantile_stable_full"],
        feature_lists["stable_full"],
        root=root,
    )
    frame["short_event_score"] = predict_ensemble(
        frame,
        groups["short_event_classification_stable_full"],
        feature_lists["stable_full"],
        root=root,
    )
    frame["confirmation_score"] = predict_ensemble(
        frame,
        groups["short_return_classification_compact"],
        feature_lists["compact"],
        root=root,
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
    selected = (
        frame.loc[frame["confirmation_pass"] & frame["utility_pass"]]
        .sort_values(["ts", "utility", "symbol"], ascending=[True, False, True])
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
    scheduled = pd.DataFrame({"ts": sorted(frame["ts"].drop_duplicates())})
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
    decisions["sleeve_exposure"] = (
        decisions["active"].astype(float) * sleeve_exposure
    )
    score_columns = [
        "ts", "symbol", "short_return_score", "short_mae_score",
        "short_event_score", "confirmation_score", "return_z_raw",
        "confirmation_z", "return_z", "mae_z", "event_z", "raw_utility",
        "utility", "confirmation_pass", "utility_pass",
    ]
    leg_columns = [
        "ts", "symbol", "side", "entry_time", "planned_exit_time",
        "sleeve_exposure", "leg_exposure", "utility", "return_z", "mae_z",
        "event_z", "confirmation_z", "raw_utility",
    ]
    outputs = (frame[score_columns], decisions, selected[leg_columns])
    forbidden_output = outcome_columns(
        list(outputs[0].columns) + list(outputs[1].columns) + list(outputs[2].columns),
        output=True,
    )
    if forbidden_output:
        raise RuntimeError(f"scorer emitted outcome columns: {forbidden_output}")
    metadata = {
        "candidate_config": config,
        "sleeve_exposure": sleeve_exposure,
        "exposure_allocation": "equal_weight_within_each_decision_sleeve",
        "model_manifest_sha256": sha256(model_manifest_path),
    }
    return *outputs, metadata


def score_controlled_baselines(
    panel: pd.DataFrame,
    r4_scores: pd.DataFrame,
    *,
    root: Path,
    baseline_manifest_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    baseline_manifest = json.loads(
        baseline_manifest_path.read_text(encoding="utf-8")
    )
    if baseline_manifest.get("status") != "PASS" or baseline_manifest.get("blockers"):
        raise RuntimeError("controlled baseline manifest is not PASS")
    config = baseline_manifest["controlled_allocator"]
    frame = panel.merge(
        r4_scores[
            [
                "ts", "symbol", "short_mae_score", "short_event_score",
                "confirmation_score", "mae_z", "event_z", "confirmation_z",
            ]
        ],
        on=["ts", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    ridge_spec = baseline_manifest["baselines"]["ridge_compact"]
    ridge_path = root / ridge_spec["model_path"]
    if sha256(ridge_path) != ridge_spec["model_sha256"]:
        raise RuntimeError("frozen Ridge baseline SHA mismatch")
    feature_path = root / ridge_spec["feature_list_path"]
    if sha256(feature_path) != ridge_spec["feature_list_sha256"]:
        raise RuntimeError("frozen Ridge feature-list SHA mismatch")
    features = json.loads(feature_path.read_text(encoding="utf-8"))
    ridge = joblib.load(ridge_path)
    ridge_x = frame[features].astype("float32").replace([np.inf, -np.inf], np.nan)
    raw_scores = {
        "ridge_compact": ridge.predict(ridge_x).astype("float64"),
        "rule_carry_momentum": -(
            0.50 * frame["cs_rank_ret_24"]
            + 0.30 * frame["cs_rank_ret_168"]
            + 0.20 * frame["cs_rank_ema_spread_24_96"]
            - 0.20 * frame["cs_rank_funding_rate"]
        ).to_numpy(dtype="float64"),
    }
    sleeve_exposure = (
        config["gross_exposure"]
        * config["decision_frequency_hours"]
        / config["horizon_hours"]
    )
    all_decisions: list[pd.DataFrame] = []
    all_legs: list[pd.DataFrame] = []
    for name, values in raw_scores.items():
        utility_threshold = baseline_manifest["baselines"][name][
            "utility_z_threshold"
        ]
        candidate = frame[["ts", "symbol", "mae_z", "event_z", "confirmation_z"]].copy()
        candidate["baseline"] = name
        candidate["return_score"] = values
        candidate["return_z_raw"] = within_time_zscore(candidate, "return_score")
        candidate["return_z"] = (
            candidate["return_z_raw"]
            + config["confirmation_weight"] * candidate["confirmation_z"]
        )
        candidate["raw_utility"] = (
            candidate["return_z"]
            - config["mae_penalty"] * candidate["mae_z"]
            - config["event_penalty"] * candidate["event_z"]
        )
        candidate["utility"] = within_time_zscore(candidate, "raw_utility")
        selected = (
            candidate.loc[candidate["utility"] >= utility_threshold]
            .sort_values(["ts", "utility", "symbol"], ascending=[True, False, True])
            .groupby("ts", sort=False, group_keys=False)
            .head(config["max_positions"])
            .copy()
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
        scheduled = pd.DataFrame({"ts": sorted(candidate["ts"].drop_duplicates())})
        chosen = selected.groupby("ts", sort=False).agg(
            selected_symbols=("symbol", lambda items: ",".join(items)),
            position_count=("symbol", "size"),
            max_utility=("utility", "max"),
            mean_utility=("utility", "mean"),
            entry_time=("entry_time", "first"),
            planned_exit_time=("planned_exit_time", "first"),
        ).reset_index()
        decisions = scheduled.merge(chosen, on="ts", how="left", validate="one_to_one")
        decisions["baseline"] = name
        decisions["active"] = decisions["selected_symbols"].notna()
        decisions["position_count"] = decisions["position_count"].fillna(0).astype(int)
        decisions["side"] = decisions["active"].map({True: "short", False: "flat"})
        decisions["sleeve_exposure"] = decisions["active"].astype(float) * sleeve_exposure
        all_decisions.append(decisions)
        all_legs.append(
            selected[
                [
                    "ts", "symbol", "baseline", "side", "entry_time",
                    "planned_exit_time", "sleeve_exposure", "leg_exposure",
                    "return_score", "return_z_raw", "return_z", "mae_z",
                    "event_z", "confirmation_z", "raw_utility", "utility",
                ]
            ]
        )
    decisions = pd.concat(all_decisions, ignore_index=True)
    legs = pd.concat(all_legs, ignore_index=True)
    forbidden = outcome_columns(
        list(decisions.columns) + list(legs.columns), output=True
    )
    if forbidden:
        raise RuntimeError(f"controlled baselines emitted outcome columns: {forbidden}")
    return decisions, legs, {
        "baseline_manifest_sha256": sha256(baseline_manifest_path),
        "baselines": sorted(raw_scores),
        "sleeve_exposure": sleeve_exposure,
    }
