from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("research/hype/1d-price-kinematics-continuation")
ARTIFACT_DIR = ROOT / "artifacts"
ENGINE_SCRIPT = Path(
    "research/hype/1h-price-kinematics-continuation/scripts/research_hype_1h_pkc.py"
)
RUN_DATE = "2026-08-03"
PAST_WINDOWS = (3, 7, 14)
FUTURE_HORIZONS = (3, 7, 14)
BAR_MINUTES = 24 * 60
DIRECTION_WINDOW = 7
ACCELERATION_PAIRS = ((3, 7), (7, 14))
SENSITIVITY_HORIZON = 7
BLOCK_HOURS = 14 * 24
TRAIN_START = pd.Timestamp("2025-06-15 00:00:00+00:00")
TRAIN_END = pd.Timestamp("2026-02-01 00:00:00+00:00")
VALIDATION_START = pd.Timestamp("2026-02-15 00:00:00+00:00")
VALIDATION_END = pd.Timestamp("2026-08-03 00:00:00+00:00")
PROSPECTIVE_START = pd.Timestamp("2026-08-03 00:00:00+00:00")
PROSPECTIVE_END = pd.Timestamp("2026-11-03 00:00:00+00:00")
WEEKLY_STRIDE_PHASES = tuple(range(7))


def load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("hype_1d_pkc_engine", ENGINE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load price-kinematics engine: {ENGINE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.ARTIFACT_DIR = ARTIFACT_DIR
    module.RUN_DATE = RUN_DATE
    module.PAST_WINDOWS = PAST_WINDOWS
    module.FUTURE_HORIZONS = FUTURE_HORIZONS
    module.BAR_MINUTES = BAR_MINUTES
    module.DIRECTION_WINDOW = DIRECTION_WINDOW
    module.ACCELERATION_PAIRS = ACCELERATION_PAIRS
    module.SENSITIVITY_HORIZON = SENSITIVITY_HORIZON
    module.BLOCK_HOURS = BLOCK_HOURS
    module.TRAIN_START = TRAIN_START
    module.TRAIN_END = TRAIN_END
    module.VALIDATION_START = VALIDATION_START
    module.VALIDATION_END = VALIDATION_END
    module.PROSPECTIVE_START = PROSPECTIVE_START
    module.PROSPECTIVE_END = PROSPECTIVE_END
    module.ANCHOR_PHASES = WEEKLY_STRIDE_PHASES
    module.PRIMARY_PHASE = None
    module.ANCHOR_PHASE_MODE = "daily_stride"
    module.OOF_MIN_ROWS = 70
    module.OOF_MIN_TRAIN_ROWS = 25
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


def build_complete_daily(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    grouped = frame.resample("1D", label="left", closed="left")
    daily = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_bars=("close", "count"),
    )
    incomplete = daily.loc[daily["source_bars"].ne(96)].copy()
    daily = daily.loc[daily["source_bars"].eq(96)].copy()
    daily.index = daily.index + pd.Timedelta(days=1)
    expected = pd.date_range(daily.index.min(), daily.index.max(), freq="1D", tz="UTC")
    missing = expected.difference(daily.index)
    invalid = daily["high"].lt(
        daily[["open", "close", "low"]].max(axis=1)
    ) | daily["low"].gt(daily[["open", "close", "high"]].min(axis=1))
    quality = {
        "rows": int(len(daily)),
        "start": daily.index.min().isoformat(),
        "end": daily.index.max().isoformat(),
        "incomplete_source_days": int(len(incomplete)),
        "incomplete_source_day_starts": [
            value.isoformat() for value in incomplete.index[:10]
        ],
        "missing_complete_days": int(len(missing)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "accepted": bool(len(missing) == 0 and int(invalid.sum()) == 0),
        "availability_semantics": (
            "index is the first UTC midnight when the completed prior day is known"
        ),
    }
    if not quality["accepted"]:
        raise RuntimeError(f"daily data quality blocker: {quality}")
    return daily, quality


def add_day_units(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "horizon_hours" in out.columns:
        out = out.rename(columns={"horizon_hours": "horizon_days"})
    return out


def run_weekly_stride_sensitivity(
    engine: Any, labelled: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    horizon = SENSITIVITY_HORIZON
    target = f"future_z_{horizon}"
    for side, direction in ((1, "long"), (-1, "short")):
        train = engine.phase_subset(
            labelled,
            phase=None,
            side=side,
            horizon=horizon,
            period="train",
        )
        for phase in WEEKLY_STRIDE_PHASES:
            validation = engine.phase_subset(
                labelled,
                phase=phase,
                side=side,
                horizon=horizon,
                period="validation",
            )
            if len(validation) < 5 or validation[f"continuation_{horizon}"].nunique() < 2:
                rows.append(
                    {
                        "direction": direction,
                        "phase": phase,
                        "samples": int(len(validation)),
                        "ridge_ic": math.nan,
                        "mean_actual_z": float(validation[target].mean()),
                    }
                )
                continue
            evaluation = engine.fit_and_evaluate(
                train,
                validation,
                features=engine.FULL_FEATURES,
                horizon=horizon,
            )
            rows.append(
                {
                    "direction": direction,
                    "phase": phase,
                    "samples": int(len(validation)),
                    "ridge_ic": evaluation.ridge_ic,
                    "mean_actual_z": float(validation[target].mean()),
                }
            )
    return pd.DataFrame(rows)


def repair_discrete_scale_alignment_effects(
    engine: Any,
    labelled: pd.DataFrame,
    effects: pd.DataFrame,
) -> pd.DataFrame:
    repaired = effects.copy()
    for side, direction in ((1, "long"), (-1, "short")):
        for horizon in FUTURE_HORIZONS:
            train = engine.phase_subset(
                labelled,
                phase=None,
                side=side,
                horizon=horizon,
                period="train",
            )
            validation = engine.phase_subset(
                labelled,
                phase=None,
                side=side,
                horizon=horizon,
                period="validation",
            )
            low = float(train["scale_alignment"].min())
            high = float(train["scale_alignment"].max())
            mapped = np.where(
                validation["scale_alignment"].eq(low),
                1.0,
                np.where(validation["scale_alignment"].eq(high), 5.0, np.nan),
            )
            work = validation.assign(feature_bin=mapped)
            observed, ci_low, ci_high, blocks = engine._block_effect_ci(
                work,
                bin_column="feature_bin",
                target=f"future_z_{horizon}",
                samples=engine.BOOTSTRAP_SAMPLES,
                seed=20260803 + side * 1_000 + horizon,
            )
            mask = (
                repaired["direction"].eq(direction)
                & repaired["horizon_hours"].eq(horizon)
                & repaired["feature"].eq("scale_alignment")
            )
            repaired.loc[
                mask,
                [
                    "q5_minus_q1_mean_z",
                    "bootstrap_ci_low",
                    "bootstrap_ci_high",
                    "independent_blocks",
                ],
            ] = [observed, ci_low, ci_high, blocks]
            repaired.loc[mask, "expected_sign_ci_excludes_zero"] = bool(ci_low > 0.0)
    return repaired


def build_gate(
    model_metrics: pd.DataFrame,
    effects: pd.DataFrame,
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
    train_full = model_metrics.loc[
        model_metrics["direction"].eq(direction)
        & model_metrics["period"].eq("train_expanding_oof")
        & model_metrics["feature_set"].eq("full")
    ].set_index("horizon_hours")
    common = train_full.index.intersection(full.index)
    same_sign = int(
        (
            np.sign(train_full.loc[common, "ridge_ic"].to_numpy(float))
            == np.sign(full.loc[common, "ridge_ic"].to_numpy(float))
        ).sum()
    )
    expected = effects.loc[
        effects["direction"].eq(direction)
        & effects["expected_direction"].isin(("positive", "negative"))
    ]
    feature_hits = expected.groupby("feature")["expected_sign_ci_excludes_zero"].sum()
    robust_features = [str(name) for name, count in feature_hits.items() if count >= 2]
    positive_ic = int(full["ridge_ic"].gt(0.0).sum())
    useful_logit = int(
        (full["logit_auc"].gt(0.5) & full["logit_brier"].le(full["constant_brier"]))
        .fillna(False)
        .sum()
    )
    trim_same_sign = int(
        (
            np.sign(full["ridge_ic"].to_numpy(float))
            == np.sign(full["trimmed_1pct_ridge_ic"].to_numpy(float))
        ).sum()
    )
    min_blocks = int(expected["independent_blocks"].min())
    min_validation_samples = int(full["samples"].min())
    gate = {
        "positive_full_ridge_ic_at_least_2_of_3": positive_ic >= 2,
        "median_full_ic_not_worse_than_baseline": bool(
            full["ridge_ic"].median() >= baseline["ridge_ic"].median()
        ),
        "useful_full_logit_at_least_2_of_3": useful_logit >= 2,
        "at_least_two_structural_features_with_two_robust_horizons": (
            len(robust_features) >= 2
        ),
        "train_validation_full_ic_same_sign_at_least_2_of_3": same_sign >= 2,
        "trimmed_1pct_ic_sign_preserved_at_least_2_of_3": trim_same_sign >= 2,
        "at_least_20_independent_14d_blocks": min_blocks >= 20,
        "at_least_50_validation_observations_each_horizon": (
            min_validation_samples >= 50
        ),
        "details": {
            "positive_ic_horizons": positive_ic,
            "useful_logit_horizons": useful_logit,
            "robust_structural_features": robust_features,
            "train_validation_same_sign_horizons": same_sign,
            "trimmed_sign_preserved_horizons": trim_same_sign,
            "minimum_independent_blocks": min_blocks,
            "minimum_validation_observations": min_validation_samples,
        },
    }
    gate["daily_kinematic_evidence_supported"] = all(
        value for key, value in gate.items() if key != "details"
    )
    return gate


def main() -> None:
    engine = load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    raw_frame, source_quality = engine.load_price_data()
    daily, daily_quality = build_complete_daily(raw_frame)
    state = engine.build_kinematic_state(daily)
    labelled = engine.add_future_labels(state)
    univariate_bins, univariate_effects = engine.run_univariate(labelled)
    univariate_effects = repair_discrete_scale_alignment_effects(
        engine, labelled, univariate_effects
    )
    model_metrics, _ = engine.run_models(labelled)
    phase_space = engine.run_phase_space(labelled)
    stride_sensitivity = run_weekly_stride_sensitivity(engine, labelled)
    label_summary = engine.run_label_summary(labelled)
    model_coefficients = engine.run_model_coefficients(labelled)
    gates = {
        direction: build_gate(model_metrics, univariate_effects, direction)
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
                            phase=None,
                            side=side,
                            horizon=horizon,
                            period=period,
                        )
                    )
                )
                for period in ("train", "validation")
            }
    payload = {
        "family": "HYPE-1D-Price-Kinematics-Continuation",
        "research_role": "unregistered indicator-free daily diagnostic",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_quality": {
            "source_15m": source_quality,
            "derived_complete_1d": daily_quality,
        },
        "contract": {
            "bar_minutes": BAR_MINUTES,
            "past_windows_days": PAST_WINDOWS,
            "direction_window_days": DIRECTION_WINDOW,
            "future_horizons_days": FUTURE_HORIZONS,
            "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
            "validation": [VALIDATION_START.isoformat(), VALIDATION_END.isoformat()],
            "prospective_oos_locked_not_revealed": [
                PROSPECTIVE_START.isoformat(),
                PROSPECTIVE_END.isoformat(),
            ],
            "ridge_alpha": engine.RIDGE_ALPHA,
            "logit_c": engine.LOGIT_C,
            "bootstrap_samples": engine.BOOTSTRAP_SAMPLES,
            "block_hours": BLOCK_HOURS,
        },
        "observation_counts": observation_counts,
        "model_metrics": engine.rounded_records(add_day_units(model_metrics)),
        "univariate_effects": engine.rounded_records(
            add_day_units(univariate_effects)
        ),
        "weekly_stride_sensitivity": engine.rounded_records(stride_sensitivity),
        "direction_gates": gates,
        "prospective_oos_touched": False,
        "strategy_backtest_performed": False,
    }
    outputs = {
        "univariate_bins": add_day_units(univariate_bins),
        "univariate_effects": add_day_units(univariate_effects),
        "model_metrics": add_day_units(model_metrics),
        "model_coefficients": add_day_units(model_coefficients),
        "phase_space": add_day_units(phase_space),
        "weekly_stride_sensitivity": stride_sensitivity,
        "label_summary": add_day_units(label_summary),
    }
    for name, output in outputs.items():
        output.to_csv(ARTIFACT_DIR / f"hype_1d_pkc_{name}_{RUN_DATE}.csv", index=False)
    labelled.loc[
        labelled.index < PROSPECTIVE_START,
        [
            "direction",
            "anchor_phase",
            *engine.FULL_FEATURES,
            *(f"future_z_{horizon}" for horizon in FUTURE_HORIZONS),
            *(f"continuation_{horizon}" for horizon in FUTURE_HORIZONS),
        ],
    ].to_parquet(
        ARTIFACT_DIR / f"hype_1d_pkc_labelled_observations_{RUN_DATE}.parquet"
    )
    result_path = ARTIFACT_DIR / f"hype_1d_pkc_research_{RUN_DATE}.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
