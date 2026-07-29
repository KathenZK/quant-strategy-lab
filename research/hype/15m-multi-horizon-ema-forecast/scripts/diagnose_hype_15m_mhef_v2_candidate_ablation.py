from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import mhef_v2_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CANDIDATE_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_prefit_candidate.json"
OUTPUT_CSV = ARTIFACT_DIR / "hype_15m_mhef_v2_candidate_centered_ablation.csv"
OUTPUT_JSON = ARTIFACT_DIR / "hype_15m_mhef_v2_candidate_centered_ablation_summary.json"

PAIR_SETS = {
    "classic": ((8, 32), (16, 64), (32, 128), (64, 256)),
    "medium": ((16, 64), (32, 128), (64, 256), (128, 512)),
    "slow": ((32, 128), (64, 256), (128, 512), (256, 1024)),
    "ultra": ((64, 256), (128, 512), (256, 1024), (512, 2048)),
}
WEIGHT_SETS = {
    "fast": (0.35, 0.30, 0.25, 0.10),
    "equal": (0.25, 0.25, 0.25, 0.25),
    "base": (0.15, 0.25, 0.35, 0.25),
    "slow": (0.10, 0.20, 0.30, 0.40),
}


def _position_sha256(path: pd.DataFrame) -> str:
    values = np.round(path["position"].to_numpy("float64"), 12)
    return hashlib.sha256(values.tobytes()).hexdigest()


def _metrics(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_gross_return": values["gross_return"],
        f"{prefix}_net_return": values["net_return"],
        f"{prefix}_max_drawdown": values["max_drawdown"],
        f"{prefix}_sharpe": values["sharpe"],
        f"{prefix}_annualized_turnover": values["annualized_turnover"],
        f"{prefix}_rebalance_count": values["rebalance_count"],
        f"{prefix}_sign_flips": values["sign_flips"],
        f"{prefix}_average_abs_position": values["average_abs_position"],
    }


def _variants(reference: engine.Config) -> list[tuple[str, str, engine.Config]]:
    variants: list[tuple[str, str, engine.Config]] = [
        ("reference", "reference", reference),
        (
            "component",
            "zero_cost_diagnostic",
            replace(reference, fee_per_turnover=0.0, slippage_per_turnover=0.0),
        ),
        (
            "component",
            "double_cost_diagnostic",
            replace(
                reference,
                fee_per_turnover=2.0 * engine.BASE_FEE,
                slippage_per_turnover=2.0 * engine.BASE_SLIPPAGE,
            ),
        ),
        ("component", "no_coherence", replace(reference, coherence_power=0.0)),
        ("component", "no_dead_zone", replace(reference, dead_zone=0.0)),
        (
            "component",
            "no_volatility_scaling",
            replace(reference, target_annual_volatility=10.0),
        ),
        ("component", "no_target_band", replace(reference, no_trade_buffer=0.0)),
        (
            "component",
            "no_minimum_change",
            replace(reference, minimum_position_change=0.0),
        ),
        ("component", "no_step_cap", replace(reference, max_position_step=2.0)),
        (
            "component",
            "exact_target",
            replace(
                reference,
                no_trade_buffer=0.0,
                minimum_position_change=0.0,
                max_position_step=2.0,
            ),
        ),
    ]
    for index, pair in enumerate(reference.ema_pairs):
        variants.append(
            (
                "sleeve_single",
                f"single_{pair[0]}_{pair[1]}",
                replace(reference, ema_pairs=(pair,), weights=(1.0,)),
            )
        )
        pairs = tuple(
            value for slot, value in enumerate(reference.ema_pairs) if slot != index
        )
        weights = tuple(
            value for slot, value in enumerate(reference.weights) if slot != index
        )
        total = sum(weights)
        variants.append(
            (
                "sleeve_drop",
                f"drop_{pair[0]}_{pair[1]}",
                replace(
                    reference,
                    ema_pairs=pairs,
                    weights=tuple(value / total for value in weights),
                ),
            )
        )

    parameter_values: dict[str, list[tuple[str, dict[str, Any]]]] = {
        "ema_pairs": [
            (label, {"ema_pairs": value}) for label, value in PAIR_SETS.items()
        ],
        "weights": [
            (label, {"weights": value}) for label, value in WEIGHT_SETS.items()
        ],
        "volatility_span": [
            (str(value), {"volatility_span": value})
            for value in (48, 96, 192, 384)
        ],
        "calibration_min_bars": [
            (str(value), {"calibration_min_bars": value})
            for value in (256, 512, 1024, 2048)
        ],
        "target_median_abs_forecast": [
            (str(value), {"target_median_abs_forecast": value})
            for value in (0.25, 0.35, 0.50, 0.65)
        ],
        "coherence_power": [
            (str(value), {"coherence_power": value})
            for value in (0.0, 0.25, 0.50, 1.0, 2.0)
        ],
        "dead_zone": [
            (str(value), {"dead_zone": value})
            for value in (0.0, 0.05, 0.10, 0.15, 0.20)
        ],
        "target_annual_volatility": [
            (str(value), {"target_annual_volatility": value})
            for value in (0.30, 0.40, 0.60, 0.80, 1.00)
        ],
        "no_trade_buffer": [
            (str(value), {"no_trade_buffer": value})
            for value in (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
        ],
        "minimum_position_change": [
            (str(value), {"minimum_position_change": value})
            for value in (0.0, 0.025, 0.05, 0.10, 0.15, 0.20)
        ],
        "max_position_step": [
            (str(value), {"max_position_step": value})
            for value in (0.10, 0.15, 0.25, 0.50, 2.0)
        ],
    }
    for parameter, values in parameter_values.items():
        for label, changes in values:
            variants.append(
                (parameter, f"{parameter}={label}", replace(reference, **changes))
            )
    unique: dict[tuple[str, str], tuple[str, str, engine.Config]] = {}
    for group, label, config in variants:
        unique[(group, label)] = (group, label, config)
    return list(unique.values())


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    reference = engine.config_from_payload(candidate["candidate_config"])
    if engine.config_sha256(reference) != candidate["candidate_config_sha256"]:
        raise RuntimeError("candidate config hash mismatch")

    tune_start = pd.Timestamp(
        manifest["freeze_contract"]["development_tune_start_inclusive"]
    )
    development_end = pd.Timestamp(
        manifest["freeze_contract"]["prefit_validation_start_inclusive"]
    )
    book = engine.build_book(terminal_exclusive=development_end)
    train_start = pd.Timestamp(book.frame["ts"].iloc[0])
    rows: list[dict[str, Any]] = []
    reference_hash: str | None = None
    reference_train: dict[str, Any] | None = None
    reference_tune: dict[str, Any] | None = None

    for group, label, config in _variants(reference):
        result = engine.run_backtest(book, config)
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
        path_hash = _position_sha256(result.path)
        if label == "reference":
            reference_hash = path_hash
            reference_train = train
            reference_tune = tune
        rows.append(
            {
                "group": group,
                "label": label,
                "config_sha256": engine.config_sha256(config),
                "position_sha256": path_hash,
                "selection_score": min(
                    engine.score_split(train),
                    engine.score_split(tune),
                ),
                "eligible": bool(
                    train["gross_return"] > 0.0
                    and train["net_return"] > 0.0
                    and tune["gross_return"] > 0.0
                    and tune["net_return"] > 0.0
                    and train["sign_flips"] >= 8
                    and tune["sign_flips"] >= 4
                ),
                **_metrics("train", train),
                **_metrics("tune", tune),
            }
        )
    if reference_hash is None or reference_train is None or reference_tune is None:
        raise RuntimeError("reference result missing")
    for row in rows:
        row["path_equal_to_reference"] = row["position_sha256"] == reference_hash
        row["train_net_delta_vs_reference"] = (
            row["train_net_return"] - reference_train["net_return"]
        )
        row["tune_net_delta_vs_reference"] = (
            row["tune_net_return"] - reference_tune["net_return"]
        )
        row["dominates_reference_net"] = bool(
            row["train_net_delta_vs_reference"] >= -1e-12
            and row["tune_net_delta_vs_reference"] >= -1e-12
            and (
                row["train_net_delta_vs_reference"] > 1e-12
                or row["tune_net_delta_vs_reference"] > 1e-12
            )
        )

    frame = pd.DataFrame(rows).sort_values(
        ["eligible", "selection_score", "tune_net_return"],
        ascending=[False, False, False],
    )
    frame.to_csv(OUTPUT_CSV, index=False)
    best_by_group: dict[str, Any] = {}
    for group, values in frame.groupby("group", sort=True):
        best = values.iloc[0]
        best_by_group[group] = {
            "label": best["label"],
            "eligible": bool(best["eligible"]),
            "selection_score": float(best["selection_score"]),
            "train_net_return": float(best["train_net_return"]),
            "tune_net_return": float(best["tune_net_return"]),
            "train_net_delta_vs_reference": float(
                best["train_net_delta_vs_reference"]
            ),
            "tune_net_delta_vs_reference": float(
                best["tune_net_delta_vs_reference"]
            ),
            "path_equal_to_reference": bool(best["path_equal_to_reference"]),
        }
    summary = {
        "family": candidate["family"],
        "status": "diagnostic only / no post-validation candidate selection",
        "data_boundary": {
            "train_start": train_start.isoformat(),
            "tune_start": tune_start.isoformat(),
            "development_end_exclusive": development_end.isoformat(),
            "prefit_validation_and_reused_oos_read": False,
        },
        "reference_label": candidate["candidate_label"],
        "reference_config_sha256": candidate["candidate_config_sha256"],
        "reference": {
            "train": reference_train,
            "tune": reference_tune,
        },
        "variant_count": int(len(frame)),
        "eligible_variants": int(frame["eligible"].sum()),
        "path_equal_variants": int(frame["path_equal_to_reference"].sum()),
        "dominates_reference_net_variants": int(
            frame["dominates_reference_net"].sum()
        ),
        "best_by_group": best_by_group,
        "governance": (
            "This ablation diagnoses development-only parameter roles after the "
            "candidate failed validation. It does not authorize retuning, replace "
            "the frozen candidate, or create a new OOS claim."
        ),
    }
    OUTPUT_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
