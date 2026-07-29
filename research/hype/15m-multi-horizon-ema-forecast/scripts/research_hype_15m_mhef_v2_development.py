from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

import mhef_v2_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_full_ablation.csv"
SENSITIVITY_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_parameter_sensitivity.csv"
SIGNAL_GRID_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_signal_grid.csv"
EXECUTION_GRID_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_execution_grid.csv"
CANDIDATE_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_prefit_candidate.json"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_development_summary.json"

PAIR_SETS = {
    "classic": ((8, 32), (16, 64), (32, 128), (64, 256)),
    "medium": ((16, 64), (32, 128), (64, 256), (128, 512)),
    "slow": ((32, 128), (64, 256), (128, 512), (256, 1024)),
    "ultra": ((64, 256), (128, 512), (256, 1024), (512, 2048)),
}
WEIGHT_SETS = {
    "base": (0.15, 0.25, 0.35, 0.25),
    "equal": (0.25, 0.25, 0.25, 0.25),
    "fast": (0.35, 0.30, 0.25, 0.10),
    "slow": (0.10, 0.20, 0.30, 0.40),
}


def _metrics_columns(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_gross_return": metrics["gross_return"],
        f"{prefix}_net_return": metrics["net_return"],
        f"{prefix}_max_drawdown": metrics["max_drawdown"],
        f"{prefix}_sharpe": metrics["sharpe"],
        f"{prefix}_turnover": metrics["turnover"],
        f"{prefix}_annualized_turnover": metrics["annualized_turnover"],
        f"{prefix}_rebalance_count": metrics["rebalance_count"],
        f"{prefix}_sign_flips": metrics["sign_flips"],
        f"{prefix}_average_abs_position": metrics["average_abs_position"],
        f"{prefix}_cost_amount": metrics["cost_amount"],
        f"{prefix}_funding_amount": metrics["funding_amount"],
    }


def _evaluate(
    *,
    label: str,
    group: str,
    config: engine.Config,
    book: engine.MarketBook,
    train_start: pd.Timestamp,
    tune_start: pd.Timestamp,
    development_end: pd.Timestamp,
    features: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], engine.BacktestResult]:
    result = engine.run_backtest(book, config, features=features)
    train = engine.slice_metrics(
        result.path,
        start=train_start,
        end=tune_start,
    )
    tune = engine.slice_metrics(
        result.path,
        start=tune_start,
        end=development_end,
    )
    development = engine.slice_metrics(
        result.path,
        start=train_start,
        end=development_end,
    )
    eligible = (
        train["gross_return"] > 0.0
        and train["net_return"] > 0.0
        and tune["gross_return"] > 0.0
        and tune["net_return"] > 0.0
        and train["sign_flips"] >= 8
        and tune["sign_flips"] >= 4
        and min(
            train["average_abs_position"],
            tune["average_abs_position"],
        ) >= 0.05
    )
    row = {
        "label": label,
        "group": group,
        "config_sha256": engine.config_sha256(config),
        "eligible": bool(eligible),
        "selection_score": min(
            engine.score_split(train),
            engine.score_split(tune),
        ),
        **_metrics_columns("train", train),
        **_metrics_columns("tune", tune),
        **_metrics_columns("development", development),
    }
    return row, result


def _renormalize_without(
    values: tuple[Any, ...],
    weights: tuple[float, ...],
    index: int,
) -> tuple[tuple[Any, ...], tuple[float, ...]]:
    remaining_values = tuple(value for slot, value in enumerate(values) if slot != index)
    remaining_weights = tuple(weight for slot, weight in enumerate(weights) if slot != index)
    total = sum(remaining_weights)
    return remaining_values, tuple(weight / total for weight in remaining_weights)


def _ablation_configs() -> list[tuple[str, engine.Config]]:
    baseline = engine.BASELINE_CONFIG
    configs: list[tuple[str, engine.Config]] = [("baseline", baseline)]
    configs.extend(
        [
            (
                "diagnostic_zero_cost",
                replace(
                    baseline,
                    fee_per_turnover=0.0,
                    slippage_per_turnover=0.0,
                ),
            ),
            ("no_coherence", replace(baseline, coherence_power=0.0)),
            ("no_dead_zone", replace(baseline, dead_zone=0.0)),
            (
                "no_volatility_scaling",
                replace(baseline, target_annual_volatility=10.0),
            ),
            ("no_target_band", replace(baseline, no_trade_buffer=0.0)),
            (
                "no_minimum_rebalance",
                replace(baseline, minimum_position_change=0.0),
            ),
            ("no_staged_step", replace(baseline, max_position_step=2.0)),
            (
                "exact_continuous_target",
                replace(
                    baseline,
                    no_trade_buffer=0.0,
                    minimum_position_change=0.0,
                    max_position_step=2.0,
                ),
            ),
        ]
    )
    for index, pair in enumerate(baseline.ema_pairs):
        configs.append(
            (
                f"single_sleeve_{pair[0]}_{pair[1]}",
                replace(baseline, ema_pairs=(pair,), weights=(1.0,)),
            )
        )
        pairs, weights = _renormalize_without(
            baseline.ema_pairs,
            baseline.weights,
            index,
        )
        configs.append(
            (
                f"drop_sleeve_{pair[0]}_{pair[1]}",
                replace(baseline, ema_pairs=pairs, weights=weights),
            )
        )
    return configs


def _sensitivity_configs() -> list[tuple[str, str, engine.Config]]:
    baseline = engine.BASELINE_CONFIG
    rows: list[tuple[str, str, engine.Config]] = []
    values: dict[str, list[tuple[str, dict[str, Any]]]] = {
        "ema_pairs": [
            (label, {"ema_pairs": pairs})
            for label, pairs in PAIR_SETS.items()
        ],
        "weights": [
            (label, {"weights": weights})
            for label, weights in WEIGHT_SETS.items()
        ],
        "volatility_span": [
            (str(value), {"volatility_span": value})
            for value in (48, 96, 192)
        ],
        "calibration_min_bars": [
            (str(value), {"calibration_min_bars": value})
            for value in (256, 512, 1024)
        ],
        "target_median_abs_forecast": [
            (str(value), {"target_median_abs_forecast": value})
            for value in (0.35, 0.50, 0.65)
        ],
        "coherence_power": [
            (str(value), {"coherence_power": value})
            for value in (0.0, 0.5, 1.0, 2.0)
        ],
        "dead_zone": [
            (str(value), {"dead_zone": value})
            for value in (0.0, 0.05, 0.10, 0.15)
        ],
        "target_annual_volatility": [
            (str(value), {"target_annual_volatility": value})
            for value in (0.4, 0.6, 0.8, 1.0, 1.5)
        ],
        "no_trade_buffer": [
            (str(value), {"no_trade_buffer": value})
            for value in (0.0, 0.10, 0.15, 0.20, 0.30, 0.40)
        ],
        "minimum_position_change": [
            (str(value), {"minimum_position_change": value})
            for value in (0.0, 0.025, 0.05, 0.10, 0.15)
        ],
        "max_position_step": [
            (str(value), {"max_position_step": value})
            for value in (0.10, 0.25, 0.50, 2.0)
        ],
    }
    for parameter, variants in values.items():
        for label, changes in variants:
            rows.append((parameter, label, replace(baseline, **changes)))
    return rows


def _sort(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
        ["eligible", "selection_score", "tune_net_return", "tune_annualized_turnover"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    engine_digest = hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest()
    if engine_digest != manifest["hashes"]["engine_sha256"]:
        raise RuntimeError("engine changed after dataset/config freeze; rerun freeze first")
    if engine.config_sha256(engine.BASELINE_CONFIG) != manifest["hashes"]["baseline_config_sha256"]:
        raise RuntimeError("baseline config changed after freeze")

    tune_start = pd.Timestamp(
        manifest["freeze_contract"]["development_tune_start_inclusive"]
    )
    validation_start = pd.Timestamp(
        manifest["freeze_contract"]["prefit_validation_start_inclusive"]
    )
    book = engine.build_book(terminal_exclusive=validation_start)
    train_start = pd.Timestamp(book.frame["ts"].iloc[0])
    baseline_features = engine.build_forecasts(book, engine.BASELINE_CONFIG)

    ablation_rows: list[dict[str, Any]] = []
    for label, config in _ablation_configs():
        features = (
            baseline_features
            if config.ema_pairs == engine.BASELINE_CONFIG.ema_pairs
            and config.weights == engine.BASELINE_CONFIG.weights
            and config.volatility_span == engine.BASELINE_CONFIG.volatility_span
            and config.calibration_min_bars == engine.BASELINE_CONFIG.calibration_min_bars
            and config.target_median_abs_forecast
            == engine.BASELINE_CONFIG.target_median_abs_forecast
            and config.coherence_power == engine.BASELINE_CONFIG.coherence_power
            and config.dead_zone == engine.BASELINE_CONFIG.dead_zone
            and config.target_annual_volatility
            == engine.BASELINE_CONFIG.target_annual_volatility
            else None
        )
        row, _ = _evaluate(
            label=label,
            group="component_ablation",
            config=config,
            book=book,
            train_start=train_start,
            tune_start=tune_start,
            development_end=validation_start,
            features=features,
        )
        ablation_rows.append(row)
    ablation_frame = _sort(pd.DataFrame(ablation_rows))
    ablation_frame.to_csv(ABLATION_PATH, index=False)

    sensitivity_rows: list[dict[str, Any]] = []
    for parameter, value_label, config in _sensitivity_configs():
        row, _ = _evaluate(
            label=f"{parameter}={value_label}",
            group=parameter,
            config=config,
            book=book,
            train_start=train_start,
            tune_start=tune_start,
            development_end=validation_start,
        )
        sensitivity_rows.append(row)
    sensitivity_frame = _sort(pd.DataFrame(sensitivity_rows))
    sensitivity_frame.to_csv(SENSITIVITY_PATH, index=False)

    signal_rows: list[dict[str, Any]] = []
    signal_configs: dict[str, engine.Config] = {}
    signal_features: dict[str, pd.DataFrame] = {}
    counter = 0
    total_signal = (
        len(PAIR_SETS) * len(WEIGHT_SETS) * 3 * 3 * 3
    )
    for pair_label, pairs in PAIR_SETS.items():
        for weight_label, weights in WEIGHT_SETS.items():
            for coherence in (0.0, 0.5, 1.0):
                for dead_zone in (0.05, 0.10, 0.15):
                    for target_volatility in (0.6, 0.8, 1.0):
                        counter += 1
                        label = (
                            f"{pair_label}__{weight_label}__coh{coherence}"
                            f"__dead{dead_zone}__vol{target_volatility}"
                        )
                        config = replace(
                            engine.BASELINE_CONFIG,
                            ema_pairs=pairs,
                            weights=weights,
                            coherence_power=coherence,
                            dead_zone=dead_zone,
                            target_annual_volatility=target_volatility,
                        )
                        features = engine.build_forecasts(book, config)
                        row, _ = _evaluate(
                            label=label,
                            group="signal_grid",
                            config=config,
                            book=book,
                            train_start=train_start,
                            tune_start=tune_start,
                            development_end=validation_start,
                            features=features,
                        )
                        signal_rows.append(row)
                        signal_configs[label] = config
                        signal_features[label] = features
                        if counter % 100 == 0:
                            print(f"signal grid {counter}/{total_signal}", flush=True)
    signal_frame = _sort(pd.DataFrame(signal_rows))
    signal_frame.to_csv(SIGNAL_GRID_PATH, index=False)

    eligible_signal = signal_frame.loc[signal_frame["eligible"]]
    shortlist = (eligible_signal if not eligible_signal.empty else signal_frame).head(8)
    execution_rows: list[dict[str, Any]] = []
    execution_configs: dict[str, engine.Config] = {}
    for source_label in shortlist["label"]:
        source = signal_configs[str(source_label)]
        features = signal_features[str(source_label)]
        for buffer in (0.10, 0.15, 0.20, 0.30, 0.40):
            for minimum_change in (0.025, 0.05, 0.10, 0.15):
                for max_step in (0.10, 0.25, 0.50):
                    label = (
                        f"{source_label}__buffer{buffer}"
                        f"__min{minimum_change}__step{max_step}"
                    )
                    config = replace(
                        source,
                        no_trade_buffer=buffer,
                        minimum_position_change=minimum_change,
                        max_position_step=max_step,
                    )
                    row, _ = _evaluate(
                        label=label,
                        group="execution_grid",
                        config=config,
                        book=book,
                        train_start=train_start,
                        tune_start=tune_start,
                        development_end=validation_start,
                        features=features,
                    )
                    row["source_signal_label"] = source_label
                    execution_rows.append(row)
                    execution_configs[label] = config
    execution_frame = _sort(pd.DataFrame(execution_rows))
    execution_frame.to_csv(EXECUTION_GRID_PATH, index=False)

    eligible_execution = execution_frame.loc[execution_frame["eligible"]]
    selected_row = (
        eligible_execution.iloc[0]
        if not eligible_execution.empty
        else execution_frame.iloc[0]
    )
    selected_label = str(selected_row["label"])
    selected_config = execution_configs[selected_label]
    same_signal = execution_frame.loc[
        execution_frame["source_signal_label"]
        == selected_row["source_signal_label"]
    ]
    candidate = {
        "family": "HYPE-15M-Multi-Horizon-EMA-Forecast",
        "research_identity": "MHEF-V2 continuous risk-target prototype; unregistered observation",
        "status": "explore / not promoted / not live-ready",
        "selection_completed_before_prefit_validation_reveal": True,
        "prefit_validation_unread": True,
        "reused_locked_oos_unread": True,
        "viable_development_candidate_exists": bool(not eligible_execution.empty),
        "reference_only": bool(eligible_execution.empty),
        "candidate_label": selected_label,
        "candidate_config": engine.config_payload(selected_config),
        "candidate_config_sha256": engine.config_sha256(selected_config),
        "candidate_development_row": selected_row.to_dict(),
        "selection_rule": (
            "require positive gross and net returns in both train and tune, "
            "minimum directional activity and non-trivial exposure; maximize the "
            "weaker train/tune net-return-to-drawdown ratio"
        ),
        "robustness": {
            "eligible_signal_candidates": int(len(eligible_signal)),
            "signal_candidates": int(len(signal_frame)),
            "eligible_execution_candidates": int(len(eligible_execution)),
            "execution_candidates": int(len(execution_frame)),
            "eligible_same_signal_execution_neighbors": int(
                same_signal["eligible"].sum()
            ),
            "same_signal_execution_neighbors": int(len(same_signal)),
        },
        "boundaries": {
            "train_start": train_start.isoformat(),
            "tune_start": tune_start.isoformat(),
            "development_end_exclusive": validation_start.isoformat(),
            "prefit_validation_start_inclusive": validation_start.isoformat(),
            "prefit_validation_end_exclusive": manifest["freeze_contract"][
                "locked_oos_start_inclusive"
            ],
            "reused_locked_oos_start_inclusive": manifest["freeze_contract"][
                "locked_oos_start_inclusive"
            ],
        },
    }
    CANDIDATE_PATH.write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    baseline_row = next(row for row in ablation_rows if row["label"] == "baseline")
    exact_row = next(
        row for row in ablation_rows if row["label"] == "exact_continuous_target"
    )
    zero_cost_row = next(
        row for row in ablation_rows if row["label"] == "diagnostic_zero_cost"
    )
    summary = {
        "family": candidate["family"],
        "research_identity": candidate["research_identity"],
        "status": candidate["status"],
        "freeze_contract": manifest["freeze_contract"],
        "data_quality_blockers": manifest["quality"]["blocker_count"],
        "baseline": baseline_row,
        "exact_continuous_target_ablation": exact_row,
        "zero_cost_diagnostic": zero_cost_row,
        "candidate": candidate,
        "artifacts": {
            "ablation": ABLATION_PATH.name,
            "sensitivity": SENSITIVITY_PATH.name,
            "signal_grid": SIGNAL_GRID_PATH.name,
            "execution_grid": EXECUTION_GRID_PATH.name,
            "candidate": CANDIDATE_PATH.name,
        },
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(candidate, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
