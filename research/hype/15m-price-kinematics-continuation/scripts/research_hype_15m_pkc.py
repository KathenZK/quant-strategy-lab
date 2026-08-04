from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("research/hype/15m-price-kinematics-continuation")
ARTIFACT_DIR = ROOT / "artifacts"
ENGINE_SCRIPT = Path(
    "research/hype/1h-price-kinematics-continuation/scripts/research_hype_1h_pkc.py"
)
RUN_DATE = "2026-08-02"
PAST_WINDOWS = (4, 12, 24)
FUTURE_HORIZONS = (4, 12, 24, 48)
BAR_MINUTES = 15
DIRECTION_WINDOW = 12
ACCELERATION_PAIRS = ((4, 12), (12, 24))
SENSITIVITY_HORIZON = 24
BLOCK_HOURS = 12


def load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("hype_15m_pkc_engine", ENGINE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load price-kinematics engine: {ENGINE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.ARTIFACT_DIR = ARTIFACT_DIR
    module.PAST_WINDOWS = PAST_WINDOWS
    module.FUTURE_HORIZONS = FUTURE_HORIZONS
    module.BAR_MINUTES = BAR_MINUTES
    module.DIRECTION_WINDOW = DIRECTION_WINDOW
    module.ACCELERATION_PAIRS = ACCELERATION_PAIRS
    module.SENSITIVITY_HORIZON = SENSITIVITY_HORIZON
    module.BLOCK_HOURS = BLOCK_HOURS
    module.BASELINE_FEATURES = tuple(
        f"dir_velocity_{window}" for window in PAST_WINDOWS
    )
    module.FULL_FEATURES = (
        *module.BASELINE_FEATURES,
        *(f"path_speed_{window}" for window in PAST_WINDOWS),
        *(f"coherence_{window}" for window in PAST_WINDOWS),
        *(f"burst_{window}" for window in PAST_WINDOWS),
        *(f"noise_{window}" for window in PAST_WINDOWS),
        *(f"roughness_{window}" for window in PAST_WINDOWS),
        *(f"dir_acceleration_{short}_{long}" for short, long in ACCELERATION_PAIRS),
        "scale_alignment",
    )
    module.EXPECTED_POSITIVE = (
        *(f"coherence_{window}" for window in PAST_WINDOWS),
        *(f"dir_acceleration_{short}_{long}" for short, long in ACCELERATION_PAIRS),
        "scale_alignment",
    )
    module.EXPECTED_NEGATIVE = (
        *(f"burst_{window}" for window in PAST_WINDOWS),
        *(f"roughness_{window}" for window in PAST_WINDOWS),
    )
    return module


def prepare_visible_15m(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    visible = frame[["open", "high", "low", "close"]].copy()
    visible.index = visible.index + pd.Timedelta(minutes=15)
    expected = pd.date_range(
        visible.index.min(), visible.index.max(), freq="15min", tz="UTC"
    )
    missing = expected.difference(visible.index)
    invalid = visible["high"].lt(
        visible[["open", "close", "low"]].max(axis=1)
    ) | visible["low"].gt(visible[["open", "close", "high"]].min(axis=1))
    quality = {
        "rows": int(len(visible)),
        "start": visible.index.min().isoformat(),
        "end": visible.index.max().isoformat(),
        "missing_visible_bars": int(len(missing)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "accepted": bool(len(missing) == 0 and int(invalid.sum()) == 0),
        "availability_semantics": "source open timestamp plus 15 minutes",
    }
    if not quality["accepted"]:
        raise RuntimeError(f"visible 15m data quality blocker: {quality}")
    return visible, quality


def add_time_units(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "horizon_hours" in out.columns:
        out = out.rename(columns={"horizon_hours": "horizon_bars"})
        location = out.columns.get_loc("horizon_bars") + 1
        out.insert(location, "horizon_hours", out["horizon_bars"] * BAR_MINUTES / 60)
    return out


def build_gate(
    model_metrics: pd.DataFrame,
    effects: pd.DataFrame,
    phase_sensitivity: pd.DataFrame,
    direction: str,
) -> dict[str, Any]:
    validation = model_metrics.loc[
        model_metrics["period"].eq("validation")
        & model_metrics["direction"].eq(direction)
    ]
    full = validation.loc[validation["feature_set"].eq("full")].set_index(
        "horizon_hours"
    )
    baseline = validation.loc[validation["feature_set"].eq("baseline")].set_index(
        "horizon_hours"
    )
    positive_ic = int(full["ridge_ic"].gt(0.0).sum())
    useful_logit = int(
        (full["logit_auc"].gt(0.5) & full["logit_brier"].le(full["constant_brier"]))
        .fillna(False)
        .sum()
    )
    expected = effects.loc[
        effects["direction"].eq(direction)
        & effects["expected_direction"].isin(("positive", "negative"))
    ]
    feature_hits = expected.groupby("feature")["expected_sign_ci_excludes_zero"].sum()
    robust_features = [str(name) for name, count in feature_hits.items() if count >= 3]
    train_full = model_metrics.loc[
        model_metrics["direction"].eq(direction)
        & model_metrics["period"].eq("train_expanding_oof")
        & model_metrics["feature_set"].eq("full")
    ].set_index("horizon_hours")
    common = train_full.index.intersection(full.index)
    train_validation_same_sign = int(
        (
            np.sign(train_full.loc[common, "ridge_ic"].to_numpy(float))
            == np.sign(full.loc[common, "ridge_ic"].to_numpy(float))
        ).sum()
    )
    trim_same_sign = int(
        (
            np.sign(full["ridge_ic"].to_numpy(float))
            == np.sign(full["trimmed_1pct_ridge_ic"].to_numpy(float))
        ).sum()
    )
    phase = phase_sensitivity.loc[phase_sensitivity["direction"].eq(direction)]
    primary = float(phase.loc[phase["phase"].eq(0), "ridge_ic"].iloc[0])
    phase_same_sign = int((np.sign(phase["ridge_ic"]) == np.sign(primary)).sum())
    min_blocks = int(expected["independent_blocks"].min())
    gate = {
        "positive_full_ridge_ic_at_least_3_of_4": positive_ic >= 3,
        "median_full_ic_not_worse_than_baseline": bool(
            full["ridge_ic"].median() >= baseline["ridge_ic"].median()
        ),
        "useful_full_logit_at_least_3_of_4": useful_logit >= 3,
        "at_least_two_structural_features_with_three_robust_horizons": len(
            robust_features
        )
        >= 2,
        "train_validation_full_ic_same_sign_at_least_3_of_4": (
            train_validation_same_sign >= 3
        ),
        "trimmed_1pct_ic_sign_preserved_at_least_3_of_4": trim_same_sign >= 3,
        "three_of_four_minute_phases_same_6h_ic_sign": phase_same_sign >= 3,
        "at_least_30_independent_12h_blocks": min_blocks >= 30,
        "details": {
            "positive_ic_horizons": positive_ic,
            "useful_logit_horizons": useful_logit,
            "robust_structural_features": robust_features,
            "train_validation_same_sign_horizons": train_validation_same_sign,
            "trimmed_sign_preserved_horizons": trim_same_sign,
            "same_sign_minute_phases": phase_same_sign,
            "minimum_independent_blocks": min_blocks,
        },
    }
    gate["short_horizon_kinematic_evidence_supported"] = all(
        value for key, value in gate.items() if key != "details"
    )
    return gate


def main() -> None:
    engine = load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    raw_frame, source_quality = engine.load_price_data()
    frame, visible_quality = prepare_visible_15m(raw_frame)
    state = engine.build_kinematic_state(frame)
    labelled = engine.add_future_labels(state)
    univariate_bins, univariate_effects = engine.run_univariate(labelled)
    model_metrics, _ = engine.run_models(labelled)
    phase_space = engine.run_phase_space(labelled)
    phase_sensitivity = engine.run_phase_sensitivity(labelled)
    label_summary = engine.run_label_summary(labelled)
    model_coefficients = engine.run_model_coefficients(labelled)
    gates = {
        direction: build_gate(
            model_metrics, univariate_effects, phase_sensitivity, direction
        )
        for direction in ("long", "short")
    }
    observation_counts: dict[str, Any] = {}
    for direction, side in (("long", 1), ("short", -1)):
        observation_counts[direction] = {}
        for horizon in FUTURE_HORIZONS:
            observation_counts[direction][str(horizon)] = {
                period: int(
                    len(
                        engine.phase_subset(
                            labelled,
                            phase=0,
                            side=side,
                            horizon=horizon,
                            period=period,
                        )
                    )
                )
                for period in ("train", "validation")
            }
    payload = {
        "family": "HYPE-15M-Price-Kinematics-Continuation",
        "research_role": "unregistered indicator-free short-horizon diagnostic",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_quality": {
            "source_15m": source_quality,
            "visible_closed_15m": visible_quality,
        },
        "contract": {
            "bar_minutes": BAR_MINUTES,
            "past_windows_bars": PAST_WINDOWS,
            "past_windows_hours": [value * BAR_MINUTES / 60 for value in PAST_WINDOWS],
            "direction_window_bars": DIRECTION_WINDOW,
            "future_horizons_bars": FUTURE_HORIZONS,
            "future_horizons_hours": [
                value * BAR_MINUTES / 60 for value in FUTURE_HORIZONS
            ],
            "primary_minute_phase": 0,
            "minute_phases": engine.ANCHOR_PHASES,
            "train": [engine.TRAIN_START.isoformat(), engine.TRAIN_END.isoformat()],
            "validation": [
                engine.VALIDATION_START.isoformat(),
                engine.VALIDATION_END.isoformat(),
            ],
            "prospective_oos_locked_not_revealed": [
                engine.PROSPECTIVE_START.isoformat(),
                engine.PROSPECTIVE_END.isoformat(),
            ],
            "ridge_alpha": engine.RIDGE_ALPHA,
            "logit_c": engine.LOGIT_C,
            "bootstrap_samples": engine.BOOTSTRAP_SAMPLES,
            "block_hours": BLOCK_HOURS,
        },
        "observation_counts_by_horizon_bars": observation_counts,
        "model_metrics": engine.rounded_records(add_time_units(model_metrics)),
        "univariate_effects": engine.rounded_records(
            add_time_units(univariate_effects)
        ),
        "phase_sensitivity": engine.rounded_records(phase_sensitivity),
        "direction_gates": gates,
        "prospective_oos_touched": False,
        "strategy_backtest_performed": False,
    }
    outputs = {
        "univariate_bins": add_time_units(univariate_bins),
        "univariate_effects": add_time_units(univariate_effects),
        "model_metrics": add_time_units(model_metrics),
        "model_coefficients": add_time_units(model_coefficients),
        "phase_space": add_time_units(phase_space),
        "phase_sensitivity": phase_sensitivity,
        "label_summary": add_time_units(label_summary),
    }
    for name, output in outputs.items():
        output.to_csv(ARTIFACT_DIR / f"hype_15m_pkc_{name}_{RUN_DATE}.csv", index=False)
    labelled.loc[
        labelled.index < engine.PROSPECTIVE_START,
        [
            "direction",
            "anchor_phase",
            *engine.FULL_FEATURES,
            *(f"future_z_{horizon}" for horizon in FUTURE_HORIZONS),
            *(f"continuation_{horizon}" for horizon in FUTURE_HORIZONS),
        ],
    ].to_parquet(
        ARTIFACT_DIR / f"hype_15m_pkc_labelled_observations_{RUN_DATE}.parquet"
    )
    result_path = ARTIFACT_DIR / f"hype_15m_pkc_research_{RUN_DATE}.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
