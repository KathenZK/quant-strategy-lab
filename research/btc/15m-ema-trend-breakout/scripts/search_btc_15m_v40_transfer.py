from __future__ import annotations

import argparse
from concurrent.futures import as_completed, ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import product
import json
import math
from multiprocessing import get_context
import os
from typing import Any

import pandas as pd

import _btc_15m_v40_common as common


CANDIDATE_METRICS_PATH = (
    common.ARTIFACT_DIR / "btc_15m_v40_candidate_metrics_2026-07-17.csv"
)
SEARCH_SUMMARY_PATH = common.ARTIFACT_DIR / "btc_15m_v40_search_summary_2026-07-17.json"
DEFAULT_WORKERS = min(8, os.cpu_count() or 1)

_WORKER_KERNEL: Any | None = None
_WORKER_FRAME: pd.DataFrame | None = None
_WORKER_FUNDING: pd.DataFrame | None = None
_WORKER_FEATURES: pd.DataFrame | None = None
_WORKER_SPLITS: dict[str, pd.Timestamp] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the sealed-holdout BTC-15M-EMA-TB V40 transfer search. "
            "This process never loads timestamps at or after holdout_start."
        )
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Validate kernel and exact universe sizes without loading market data.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            "Candidate-evaluation worker processes. Default: "
            f"min(8, cpu_count)={DEFAULT_WORKERS}; use 1 for serial semantics."
        ),
    )
    parser.add_argument(
        "--parallel-equivalence-test",
        action="store_true",
        help=(
            "Run two development-only specs serially and with two fork workers, "
            "assert exact metric equality, and write no artifacts."
        ),
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return args


def default_flags(kernel: Any, **changes: bool) -> dict[str, bool]:
    values = asdict(kernel.v40_flags())
    values.update(changes)
    return values


def stage1a_specs(kernel: Any) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for index, values in enumerate(
        product(
            common.LONG_ADX_GRID,
            common.LONG_VOL_GRID,
            common.H1_LONG_ADX_GRID,
            common.BRACKET_GRID,
            common.COOLDOWN_GRID,
        ),
        start=1,
    ):
        long_adx, long_vol, h1_adx, bracket, cooldown = values
        candidate_id = f"s1a_{index:03d}"
        specs.append(
            {
                "candidate_id": candidate_id,
                "stage": "stage1a_long_only",
                "seed_id": candidate_id,
                "ablation_id": "long_grid",
                "config_changes": {
                    "long_adx_min": long_adx,
                    "long_vol_min": long_vol,
                    "h1_long_adx_min": h1_adx,
                    "take_profit_atr": bracket[0],
                    "hard_stop_atr": bracket[1],
                    "cooldown_bars": cooldown,
                },
                "flags": default_flags(kernel, allow_short=False),
                "overlay": None,
            }
        )
    if len(specs) != 216:
        raise AssertionError(f"Stage1A must contain 216 variants, got {len(specs)}")
    return specs


def stage1b_specs(
    kernel: Any,
    seeds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for seed_number, seed in enumerate(seeds, start=1):
        for short_adx, short_vol, short_h1 in product(
            common.SHORT_ADX_GRID,
            common.SHORT_VOL_GRID,
            common.SHORT_H1_GRID,
        ):
            candidate_id = (
                f"s1b_seed{seed_number}_adx{short_adx:g}_vol{short_vol:g}_h1{short_h1}"
            )
            changes = dict(seed["selection"]["config_changes"])
            changes.update(
                {
                    "short_adx_min": short_adx,
                    "short_vol_min": short_vol,
                }
            )
            specs.append(
                {
                    "candidate_id": candidate_id,
                    "stage": "stage1b_bidirectional",
                    "seed_id": seed["candidate_id"],
                    "ablation_id": (
                        f"add_short_adx{short_adx:g}_vol{short_vol:g}_h1{short_h1}"
                    ),
                    "config_changes": changes,
                    "flags": default_flags(
                        kernel,
                        allow_short=True,
                        short_use_h1_ema=short_h1 == "ema",
                    ),
                    "overlay": None,
                }
            )
    if len(specs) != 72:
        raise AssertionError(f"Stage1B must contain 72 variants, got {len(specs)}")
    return specs


def _stage2_overlay(
    *,
    volume_quantile: float | None,
    atr_regime: str | None,
) -> dict[str, Any] | None:
    if volume_quantile is None and atr_regime is None:
        return None
    return {
        "volume_quantile": volume_quantile,
        "volume_rolling_days": 60,
        "volume_min_period_days": 45,
        "shift_bars": 1,
        "atr_regime": atr_regime,
        "atr_quantile_rolling_days": 60,
        "atr_quantile_min_period_days": 45,
    }


def stage2_first_wave_specs(
    near_misses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for seed_number, seed in enumerate(near_misses, start=1):
        selected = seed["selection"]
        base = {
            "stage": "stage2_step1_single_component",
            "seed_id": seed["candidate_id"],
            "stage2_step": 1,
            "parent_candidate_id": seed["candidate_id"],
            "flags": dict(selected["flags"]),
        }
        for volume_q in common.STAGE2_VOLUME_QUANTILES:
            ablation_id = f"seed{seed_number}__volume_q{volume_q:.2f}"
            specs.append(
                {
                    **base,
                    "candidate_id": f"s2_step1_{ablation_id}",
                    "ablation_id": ablation_id,
                    "component_type": "volume",
                    "added_component_type": "volume",
                    "neighbor_group": f"{seed['candidate_id']}:step1:volume",
                    "components": {
                        "volume_quantile": volume_q,
                        "atr_regime": None,
                        "exit_profile": None,
                    },
                    "config_changes": dict(selected["config_changes"]),
                    "overlay": _stage2_overlay(
                        volume_quantile=volume_q,
                        atr_regime=None,
                    ),
                }
            )
        for atr_regime in [
            value for value in common.STAGE2_ATR_REGIMES if value != "all"
        ]:
            ablation_id = f"seed{seed_number}__atr_{atr_regime}"
            specs.append(
                {
                    **base,
                    "candidate_id": f"s2_step1_{ablation_id}",
                    "ablation_id": ablation_id,
                    "component_type": "atr",
                    "added_component_type": "atr",
                    "neighbor_group": f"{seed['candidate_id']}:step1:atr",
                    "components": {
                        "volume_quantile": None,
                        "atr_regime": atr_regime,
                        "exit_profile": None,
                    },
                    "config_changes": dict(selected["config_changes"]),
                    "overlay": _stage2_overlay(
                        volume_quantile=None,
                        atr_regime=atr_regime,
                    ),
                }
            )
        for exit_profile in common.STAGE2_EXIT_PROFILES:
            changes = dict(selected["config_changes"])
            changes.update(
                {
                    "take_profit_atr": exit_profile[0],
                    "hard_stop_atr": exit_profile[1],
                }
            )
            ablation_id = (
                f"seed{seed_number}__exit_tp{exit_profile[0]:g}_sl{exit_profile[1]:g}"
            )
            specs.append(
                {
                    **base,
                    "candidate_id": f"s2_step1_{ablation_id}",
                    "ablation_id": ablation_id,
                    "component_type": "exit",
                    "added_component_type": "exit",
                    "neighbor_group": f"{seed['candidate_id']}:step1:exit",
                    "components": {
                        "volume_quantile": None,
                        "atr_regime": None,
                        "exit_profile": exit_profile,
                    },
                    "config_changes": changes,
                    "overlay": None,
                }
            )
    if len(specs) != 9 * len(near_misses):
        raise AssertionError("Stage2 step1 must contain 9 variants per seed")
    return specs


def stage2_second_wave_specs(
    best_parents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for seed_number, parent in enumerate(best_parents, start=1):
        selected = parent["selection"]
        components = dict(selected["components"])
        parent_type = str(selected["component_type"])

        additions: list[tuple[str, Any]] = []
        if parent_type != "volume":
            additions.extend(
                ("volume", value) for value in common.STAGE2_VOLUME_QUANTILES
            )
        if parent_type != "atr":
            additions.extend(
                ("atr", value) for value in common.STAGE2_ATR_REGIMES if value != "all"
            )
        if parent_type != "exit":
            additions.extend(("exit", value) for value in common.STAGE2_EXIT_PROFILES)

        for added_type, value in additions:
            child_components = dict(components)
            changes = dict(selected["config_changes"])
            overlay = dict(selected["overlay"] or {})
            if added_type == "volume":
                child_components["volume_quantile"] = value
                overlay = _stage2_overlay(
                    volume_quantile=float(value),
                    atr_regime=child_components["atr_regime"],
                )
                value_label = f"q{value:.2f}"
            elif added_type == "atr":
                child_components["atr_regime"] = value
                overlay = _stage2_overlay(
                    volume_quantile=child_components["volume_quantile"],
                    atr_regime=str(value),
                )
                value_label = str(value)
            else:
                child_components["exit_profile"] = value
                changes.update(
                    {
                        "take_profit_atr": value[0],
                        "hard_stop_atr": value[1],
                    }
                )
                overlay = selected["overlay"]
                value_label = f"tp{value[0]:g}_sl{value[1]:g}"
            component_types = [
                name
                for name in ["volume", "atr", "exit"]
                if child_components[
                    {
                        "volume": "volume_quantile",
                        "atr": "atr_regime",
                        "exit": "exit_profile",
                    }[name]
                ]
                is not None
            ]
            component_type = "+".join(component_types)
            ablation_id = (
                f"seed{seed_number}__parent_{parent['candidate_id']}"
                f"__add_{added_type}_{value_label}"
            )
            specs.append(
                {
                    "candidate_id": f"s2_step2_{ablation_id}",
                    "stage": "stage2_step2_add_one_component",
                    "seed_id": selected["seed_id"],
                    "stage2_step": 2,
                    "parent_candidate_id": parent["candidate_id"],
                    "ablation_id": ablation_id,
                    "component_type": component_type,
                    "added_component_type": added_type,
                    "neighbor_group": (f"{selected['seed_id']}:step2:{component_type}"),
                    "components": child_components,
                    "config_changes": changes,
                    "flags": dict(selected["flags"]),
                    "overlay": overlay,
                }
            )
    if len(specs) > 7 * len(best_parents):
        raise AssertionError("Stage2 step2 exceeds 7 variants per seed")
    if len(specs) + 9 * len(best_parents) > 144:
        raise AssertionError("Stage2 total exceeds 144 variants")
    return specs


def _evaluate_one(
    kernel: Any,
    *,
    selection: dict[str, Any],
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    splits: dict[str, pd.Timestamp],
) -> dict[str, Any]:
    row = common.evaluate_train_validation(
        kernel,
        candidate_id=selection["candidate_id"],
        frame=frame,
        funding=funding,
        features=features,
        splits=splits,
        selection=selection,
    )
    passed, failures = common.gate_without_neighbors(row)
    row["gate_without_neighbors"] = passed
    row["gate_failures"] = failures
    row["failure_score"] = common.failure_score(row)
    return row


def _install_worker_state(
    *,
    kernel: Any,
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    splits: dict[str, pd.Timestamp],
) -> None:
    global _WORKER_KERNEL
    global _WORKER_FRAME
    global _WORKER_FUNDING
    global _WORKER_FEATURES
    global _WORKER_SPLITS
    _WORKER_KERNEL = kernel
    _WORKER_FRAME = frame
    _WORKER_FUNDING = funding
    _WORKER_FEATURES = features
    _WORKER_SPLITS = splits


def _worker_ready() -> None:
    if any(
        value is None
        for value in [
            _WORKER_KERNEL,
            _WORKER_FRAME,
            _WORKER_FUNDING,
            _WORKER_FEATURES,
            _WORKER_SPLITS,
        ]
    ):
        raise RuntimeError("fork worker did not inherit read-only search state")


def _worker_evaluate(
    index_and_selection: tuple[int, dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
    _worker_ready()
    index, selection = index_and_selection
    row = _evaluate_one(
        _WORKER_KERNEL,
        selection=selection,
        frame=_WORKER_FRAME,
        funding=_WORKER_FUNDING,
        features=_WORKER_FEATURES,
        splits=_WORKER_SPLITS,
    )
    return index, row


def evaluate_specs(
    kernel: Any,
    *,
    specs: list[dict[str, Any]],
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    splits: dict[str, pd.Timestamp],
    label: str,
    workers: int,
) -> list[dict[str, Any]]:
    total = len(specs)
    if workers == 1 or total <= 1:
        rows: list[dict[str, Any]] = []
        for index, selection in enumerate(specs, start=1):
            rows.append(
                _evaluate_one(
                    kernel,
                    selection=selection,
                    frame=frame,
                    funding=funding,
                    features=features,
                    splits=splits,
                )
            )
            if index == 1 or index % 12 == 0 or index == total:
                print(f"{label}: {index}/{total}", flush=True)
        return rows

    _install_worker_state(
        kernel=kernel,
        frame=frame,
        funding=funding,
        features=features,
        splits=splits,
    )
    rows_by_index: dict[int, dict[str, Any]] = {}
    fork_context = get_context("fork")
    with ProcessPoolExecutor(
        max_workers=min(workers, total),
        mp_context=fork_context,
        initializer=_worker_ready,
    ) as executor:
        futures = [
            executor.submit(_worker_evaluate, (index, selection))
            for index, selection in enumerate(specs)
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            index, row = future.result()
            rows_by_index[index] = row
            if completed == 1 or completed % 12 == 0 or completed == total:
                print(
                    f"{label}: {completed}/{total} completed "
                    f"with {min(workers, total)} fork workers",
                    flush=True,
                )
    return [rows_by_index[index] for index in range(total)]


def _grid_distance(
    left: dict[str, Any],
    right: dict[str, Any],
    dimensions: list[tuple[str, list[Any]]],
) -> int | None:
    distance = 0
    for key, values in dimensions:
        left_value = left[key]
        right_value = right[key]
        if left_value == right_value:
            continue
        left_index = values.index(left_value)
        right_index = values.index(right_value)
        difference = abs(left_index - right_index)
        if difference != 1:
            return None
        distance += difference
    return distance


def annotate_neighbors(
    rows: list[dict[str, Any]],
    *,
    dimensions: list[tuple[str, list[Any]]],
    value_getter: Any,
    group_key: str | None,
    train_only: bool,
) -> None:
    for row in rows:
        current = value_getter(row)
        neighbors: list[dict[str, Any]] = []
        for other in rows:
            if other is row:
                continue
            if group_key and (
                row["selection"].get(group_key) != other["selection"].get(group_key)
            ):
                continue
            distance = _grid_distance(
                current,
                value_getter(other),
                dimensions,
            )
            if distance == 1:
                neighbors.append(other)
        pool = [row, *neighbors]
        if train_only:
            positive = [
                item["train"]["return_pct"] > 0.0
                and item["stress_2x_train"]["return_pct"] > 0.0
                for item in pool
            ]
        else:
            positive = [
                item["train"]["return_pct"] > 0.0
                and item["validation"]["return_pct"] > 0.0
                and item["stress_2x_train"]["return_pct"] > 0.0
                and item["stress_2x_validation"]["return_pct"] > 0.0
                for item in pool
            ]
        ratio = float(sum(positive) / len(positive))
        row["neighbor_count_including_self"] = len(pool)
        row["neighbor_positive_ratio"] = ratio
        if ratio < common.NEIGHBOR_POSITIVE_RATIO_MIN:
            row["gate_failures"].append("neighbor_positive_ratio")
        row["gate_pass"] = bool(
            row["gate_without_neighbors"]
            and ratio >= common.NEIGHBOR_POSITIVE_RATIO_MIN
        )


def stage1a_values(row: dict[str, Any]) -> dict[str, Any]:
    changes = row["selection"]["config_changes"]
    return {
        "long_adx_min": changes["long_adx_min"],
        "long_vol_min": changes["long_vol_min"],
        "h1_long_adx_min": changes["h1_long_adx_min"],
        "bracket": (
            changes["take_profit_atr"],
            changes["hard_stop_atr"],
        ),
        "cooldown_bars": changes["cooldown_bars"],
    }


def stage1b_values(row: dict[str, Any]) -> dict[str, Any]:
    changes = row["selection"]["config_changes"]
    return {
        "short_adx_min": changes["short_adx_min"],
        "short_vol_min": changes["short_vol_min"],
        "short_h1": (
            "ema" if row["selection"]["flags"]["short_use_h1_ema"] else "none"
        ),
    }


def stage2_values(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row["selection"]["components"])


def attach_parent_deltas(
    rows: list[dict[str, Any]],
    parents: dict[str, dict[str, Any]],
) -> None:
    def difference(left: Any, right: Any) -> float | None:
        left_value = float(left)
        right_value = float(right)
        if not (math.isfinite(left_value) and math.isfinite(right_value)):
            return None
        return left_value - right_value

    for row in rows:
        parent_id = row["selection"]["parent_candidate_id"]
        parent = parents[parent_id]
        delta = {
            "train_return_pct": difference(
                row["train"]["return_pct"],
                parent["train"]["return_pct"],
            ),
            "validation_return_pct": difference(
                row["validation"]["return_pct"],
                parent["validation"]["return_pct"],
            ),
            "train_profit_factor": difference(
                row["train"]["profit_factor"],
                parent["train"]["profit_factor"],
            ),
            "validation_profit_factor": difference(
                row["validation"]["profit_factor"],
                parent["validation"]["profit_factor"],
            ),
            "stress_2x_train_return_pct": difference(
                row["stress_2x_train"]["return_pct"],
                parent["stress_2x_train"]["return_pct"],
            ),
            "stress_2x_validation_return_pct": difference(
                row["stress_2x_validation"]["return_pct"],
                parent["stress_2x_validation"]["return_pct"],
            ),
            "failure_score_improvement": difference(
                parent["failure_score"],
                row["failure_score"],
            ),
        }
        row["selection"]["parent_delta"] = delta


def best_step1_per_seed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seed_ids = sorted({row["selection"]["seed_id"] for row in rows})
    return [
        max(
            [row for row in rows if row["selection"]["seed_id"] == seed_id],
            key=rank_final,
        )
        for seed_id in seed_ids
    ]


def train_seed_gate(row: dict[str, Any]) -> bool:
    train = row["train"]
    return bool(
        train["return_pct"] > 0.0
        and abs(train["max_drawdown_pct"]) <= 25.0
        and train["trades"] >= 24
        and train["profit_factor"] >= 1.15
        and row["stress_2x_train"]["return_pct"] > 0.0
        and train["top_trade_positive_pnl_share"] <= common.TOP_TRADE_SHARE_MAX
        and train["top3_trade_positive_pnl_share"] <= common.TOP3_TRADE_SHARE_MAX
    )


def select_three_train_seeds(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (
            row["neighbor_positive_ratio"],
            row["train_seed_gate"],
            row["train"]["profit_factor"],
            row["train"]["return_pct"],
            -abs(row["train"]["max_drawdown_pct"]),
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    dimensions = [
        ("long_adx_min", common.LONG_ADX_GRID),
        ("long_vol_min", common.LONG_VOL_GRID),
        ("h1_long_adx_min", common.H1_LONG_ADX_GRID),
        ("bracket", common.BRACKET_GRID),
        ("cooldown_bars", common.COOLDOWN_GRID),
    ]
    for candidate in ranked:
        values = stage1a_values(candidate)
        if all(
            _grid_distance(values, stage1a_values(existing), dimensions) is None
            for existing in selected
        ):
            selected.append(candidate)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        selected = ranked[:3]
    return selected


def rank_final(row: dict[str, Any]) -> tuple[float, ...]:
    return (
        float(row["gate_pass"]),
        row["neighbor_positive_ratio"],
        row["validation"]["profit_factor"],
        row["stress_2x_validation"]["return_pct"],
        row["validation"]["return_pct"],
        row["train"]["profit_factor"],
        -abs(row["validation"]["max_drawdown_pct"]),
    )


def verify_inputs() -> tuple[dict[str, Any], dict[str, pd.Timestamp]]:
    split_payload = common.read_verified_payload(common.SPLITS_PATH, "frozen splits")
    if split_payload["kernel_sha256"] != common.KERNEL_SHA256:
        raise RuntimeError("frozen split kernel SHA does not match this search")
    audit_sha = common.sha256_bytes(common.AUDIT_PATH.read_bytes())
    if split_payload["data_quality_sha256"] != audit_sha:
        raise RuntimeError("data-quality artifact changed after split freeze")
    splits = common.parse_splits(split_payload)
    return split_payload, splits


def run_parallel_equivalence_test(kernel: Any) -> None:
    data_start = pd.Timestamp(
        json.loads(common.AUDIT_PATH.read_bytes())["ohlcv_quality"]["first_ts"]
    )
    test_splits = {
        "train_start": data_start + pd.Timedelta(days=20),
        "validation_start": data_start + pd.Timedelta(days=50),
        "holdout_start": data_start + pd.Timedelta(days=80),
    }
    frame, funding = common.load_market(
        data_start,
        test_splits["holdout_start"],
    )
    features = common.build_feature_base(kernel, frame)
    specs = stage1a_specs(kernel)[:2]
    serial = evaluate_specs(
        kernel,
        specs=specs,
        frame=frame,
        funding=funding,
        features=features,
        splits=test_splits,
        label="parallel equivalence serial",
        workers=1,
    )
    parallel = evaluate_specs(
        kernel,
        specs=specs,
        frame=frame,
        funding=funding,
        features=features,
        splits=test_splits,
        label="parallel equivalence fork",
        workers=2,
    )
    for index, (serial_row, parallel_row) in enumerate(
        zip(serial, parallel, strict=True),
        start=1,
    ):
        serial_bytes = common.canonical_json_bytes(common.finite_json_value(serial_row))
        parallel_bytes = common.canonical_json_bytes(
            common.finite_json_value(parallel_row)
        )
        if serial_bytes != parallel_bytes:
            raise AssertionError(
                f"parallel equivalence failed for spec {index}: "
                f"{specs[index - 1]['candidate_id']}"
            )
    print(
        "parallel equivalence PASS: 2 specs; all metrics exactly equal; "
        "development-only; no artifacts written",
        flush=True,
    )


def selection_already_frozen(split_payload: dict[str, Any]) -> bool:
    if not common.SELECTION_PATH.exists():
        return False
    existing = common.read_verified_payload(
        common.SELECTION_PATH,
        "frozen selection",
    )
    if (
        existing["frozen_splits_payload_sha256"] != split_payload["payload_sha256"]
        or existing["config_universe_sha256"] != common.config_universe_sha256()
    ):
        raise RuntimeError("a frozen selection exists for different search inputs")
    for path, key in [
        (CANDIDATE_METRICS_PATH, "candidate_metrics_sha256"),
        (SEARCH_SUMMARY_PATH, "search_summary_sha256"),
    ]:
        if not path.exists():
            raise RuntimeError(f"frozen selection evidence is missing: {path}")
        actual = common.sha256_bytes(path.read_bytes())
        if actual != existing[key]:
            raise RuntimeError(
                f"frozen selection evidence SHA mismatch for {path}: "
                f"expected {existing[key]}, got {actual}"
            )
    print(
        json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True),
        flush=True,
    )
    print("selection already frozen; search outputs left unchanged", flush=True)
    return True


def persist_selection(
    *,
    selected: dict[str, Any],
    role: str,
    qualified: bool,
    split_payload: dict[str, Any],
    metrics_sha: str,
    summary_sha: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "family": "BTC-15M-EMA-Trend-Breakout",
        "research_identity": "BTC-15M-EMA-TB-V40-transfer-search",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "qualified_candidate": qualified,
        "status": (
            "frozen_candidate_for_single_holdout_reveal"
            if qualified
            else "frozen_diagnostic_near_miss_not_candidate"
        ),
        "selection": common.selection_identity(selected),
        "selection_metrics": {
            "train": selected["train"],
            "validation": selected["validation"],
            "stress_2x_train": selected["stress_2x_train"],
            "stress_2x_validation": selected["stress_2x_validation"],
            "neighbor_positive_ratio": selected["neighbor_positive_ratio"],
            "gate_pass": selected["gate_pass"],
            "gate_failures": selected["gate_failures"],
        },
        "kernel_sha256": common.KERNEL_SHA256,
        "frozen_splits_payload_sha256": split_payload["payload_sha256"],
        "data_quality_sha256": split_payload["data_quality_sha256"],
        "config_universe_sha256": common.config_universe_sha256(),
        "candidate_metrics_sha256": metrics_sha,
        "search_summary_sha256": summary_sha,
        "holdout_status": "sealed_unread",
    }
    payload = common.finite_json_value(payload)
    payload["payload_sha256"] = common.payload_sha256(payload)
    if common.SELECTION_PATH.exists():
        existing = common.read_verified_payload(
            common.SELECTION_PATH,
            "frozen selection",
        )
        immutable = [
            "role",
            "qualified_candidate",
            "selection",
            "kernel_sha256",
            "frozen_splits_payload_sha256",
            "data_quality_sha256",
            "config_universe_sha256",
        ]
        if any(existing.get(key) != payload.get(key) for key in immutable):
            raise RuntimeError("refusing to overwrite a different frozen selection")
        print("frozen selection already matches; leaving it unchanged", flush=True)
        return existing
    common.atomic_write_json(common.SELECTION_PATH, payload)
    return payload


def main() -> None:
    args = parse_args()
    kernel = common.load_kernel()
    universe = common.config_universe()
    if args.smoke:
        assert len(stage1a_specs(kernel)) == 216
        dummy_seeds = [
            {"candidate_id": f"seed_{index}", "selection": spec}
            for index, spec in enumerate(stage1a_specs(kernel)[:3], start=1)
        ]
        assert len(stage1b_specs(kernel, dummy_seeds)) == 72
        dummy_near_misses = [
            {
                "candidate_id": f"near_miss_{index}",
                "selection": {
                    "config_changes": {},
                    "flags": default_flags(kernel),
                },
            }
            for index in range(1, 5)
        ]
        first_wave = stage2_first_wave_specs(dummy_near_misses)
        assert len(first_wave) == 36
        assert all(
            sum(value is not None for value in spec["components"].values()) == 1
            for spec in first_wave
        )
        atr_parents = []
        for index, near_miss in enumerate(dummy_near_misses, start=1):
            selection = next(
                spec
                for spec in first_wave
                if spec["seed_id"] == near_miss["candidate_id"]
                and spec["component_type"] == "atr"
            )
            atr_parents.append(
                {
                    "candidate_id": f"dummy_parent_{index}",
                    "selection": selection,
                }
            )
        second_wave = stage2_second_wave_specs(atr_parents)
        assert len(second_wave) == 28
        assert all(
            sum(value is not None for value in spec["components"].values()) == 2
            and spec["added_component_type"] != "atr"
            and ":step2:" in spec["neighbor_group"]
            for spec in second_wave
        )
        assert len(first_wave) + len(second_wave) == universe["stage2"]["max_count"]
        print(
            "smoke PASS: kernel SHA; Stage1A=216; Stage1B=72; "
            "Stage2 step1<=36 + step2<=28 = total<=64",
            flush=True,
        )
        return

    split_payload, splits = verify_inputs()
    if args.parallel_equivalence_test:
        run_parallel_equivalence_test(kernel)
        return
    if selection_already_frozen(split_payload):
        return
    data_start = pd.Timestamp(
        json.loads(common.AUDIT_PATH.read_bytes())["ohlcv_quality"]["first_ts"]
    )
    print(
        f"loading development data only: [{data_start}, {splits['holdout_start']})",
        flush=True,
    )
    frame, funding = common.load_market(
        data_start,
        splits["holdout_start"],
    )
    if frame.index.max() >= splits["holdout_start"]:
        raise RuntimeError("holdout row entered the development process")
    print(f"loaded {len(frame)} development bars; building features", flush=True)
    features = common.build_feature_base(kernel, frame)

    baseline_selection = {
        "candidate_id": "v40_original_baseline",
        "stage": "baseline",
        "seed_id": None,
        "ablation_id": "v40_original",
        "config_changes": {},
        "flags": default_flags(kernel),
        "overlay": None,
    }
    baseline = evaluate_specs(
        kernel,
        specs=[baseline_selection],
        frame=frame,
        funding=funding,
        features=features,
        splits=splits,
        label="baseline",
        workers=args.workers,
    )[0]
    baseline["neighbor_positive_ratio"] = 1.0
    baseline["gate_pass"] = baseline["gate_without_neighbors"]

    stage1a = evaluate_specs(
        kernel,
        specs=stage1a_specs(kernel),
        frame=frame,
        funding=funding,
        features=features,
        splits=splits,
        label="Stage1A",
        workers=args.workers,
    )
    annotate_neighbors(
        stage1a,
        dimensions=[
            ("long_adx_min", common.LONG_ADX_GRID),
            ("long_vol_min", common.LONG_VOL_GRID),
            ("h1_long_adx_min", common.H1_LONG_ADX_GRID),
            ("bracket", common.BRACKET_GRID),
            ("cooldown_bars", common.COOLDOWN_GRID),
        ],
        value_getter=stage1a_values,
        group_key=None,
        train_only=True,
    )
    for row in stage1a:
        row["train_seed_gate"] = train_seed_gate(row)
    seeds = select_three_train_seeds(stage1a)
    print(
        "train-only plateau seeds: "
        + ", ".join(seed["candidate_id"] for seed in seeds),
        flush=True,
    )

    stage1b = evaluate_specs(
        kernel,
        specs=stage1b_specs(kernel, seeds),
        frame=frame,
        funding=funding,
        features=features,
        splits=splits,
        label="Stage1B",
        workers=args.workers,
    )
    annotate_neighbors(
        stage1b,
        dimensions=[
            ("short_adx_min", common.SHORT_ADX_GRID),
            ("short_vol_min", common.SHORT_VOL_GRID),
            ("short_h1", common.SHORT_H1_GRID),
        ],
        value_getter=stage1b_values,
        group_key="seed_id",
        train_only=False,
    )
    stage1_passes = [row for row in stage1b if row["gate_pass"]]

    stage2_first_wave: list[dict[str, Any]] = []
    stage2_second_wave: list[dict[str, Any]] = []
    if stage1_passes:
        selected = max(stage1_passes, key=rank_final)
        role = "candidate"
        qualified = True
        print(
            f"Stage1 qualified plateau selected: {selected['candidate_id']}",
            flush=True,
        )
    else:
        near_misses = sorted(
            stage1b,
            key=lambda row: (row["failure_score"], tuple(-x for x in rank_final(row))),
        )[:4]
        print(
            "Stage1 has no qualified plateau; Stage2 seeds: "
            + ", ".join(row["candidate_id"] for row in near_misses),
            flush=True,
        )
        stage2_first_wave = evaluate_specs(
            kernel,
            specs=stage2_first_wave_specs(near_misses),
            frame=frame,
            funding=funding,
            features=features,
            splits=splits,
            label="Stage2 step1",
            workers=args.workers,
        )
        attach_parent_deltas(
            stage2_first_wave,
            {row["candidate_id"]: row for row in near_misses},
        )
        annotate_neighbors(
            stage2_first_wave,
            dimensions=[
                ("volume_quantile", [None, *common.STAGE2_VOLUME_QUANTILES]),
                ("atr_regime", [None, *common.STAGE2_ATR_REGIMES[1:]]),
                ("exit_profile", [None, *common.STAGE2_EXIT_PROFILES]),
            ],
            value_getter=stage2_values,
            group_key="neighbor_group",
            train_only=False,
        )
        best_first_wave = best_step1_per_seed(stage2_first_wave)
        print(
            "Stage2 step1 parents: "
            + ", ".join(row["candidate_id"] for row in best_first_wave),
            flush=True,
        )
        stage2_second_wave = evaluate_specs(
            kernel,
            specs=stage2_second_wave_specs(best_first_wave),
            frame=frame,
            funding=funding,
            features=features,
            splits=splits,
            label="Stage2 step2",
            workers=args.workers,
        )
        attach_parent_deltas(
            stage2_second_wave,
            {row["candidate_id"]: row for row in best_first_wave},
        )
        annotate_neighbors(
            stage2_second_wave,
            dimensions=[
                ("volume_quantile", [None, *common.STAGE2_VOLUME_QUANTILES]),
                ("atr_regime", [None, *common.STAGE2_ATR_REGIMES[1:]]),
                ("exit_profile", [None, *common.STAGE2_EXIT_PROFILES]),
            ],
            value_getter=stage2_values,
            group_key="neighbor_group",
            train_only=False,
        )
        stage2 = [*stage2_first_wave, *stage2_second_wave]
        stage2_passes = [row for row in stage2 if row["gate_pass"]]
        if stage2_passes:
            selected = max(stage2_passes, key=rank_final)
            role = "candidate"
            qualified = True
            print(
                f"Stage2 qualified candidate selected: {selected['candidate_id']}",
                flush=True,
            )
        else:
            selected = min(stage2, key=lambda row: row["failure_score"])
            role = "diagnostic_near_miss"
            qualified = False
            print(
                "Stage2 has no qualified item; freezing diagnostic near-miss: "
                f"{selected['candidate_id']}",
                flush=True,
            )

    stage2 = [*stage2_first_wave, *stage2_second_wave]
    all_rows = [baseline, *stage1a, *stage1b, *stage2]
    candidate_frame = pd.DataFrame([common.flatten_candidate(row) for row in all_rows])
    common.atomic_write_csv(CANDIDATE_METRICS_PATH, candidate_frame)
    metrics_sha = common.sha256_bytes(CANDIDATE_METRICS_PATH.read_bytes())

    summary: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "BTC-15M-EMA-Trend-Breakout",
        "holdout_accessed": False,
        "development_end_exclusive": splits["holdout_start"].isoformat(),
        "kernel_sha256": common.KERNEL_SHA256,
        "frozen_splits_payload_sha256": split_payload["payload_sha256"],
        "config_universe": universe,
        "config_universe_sha256": common.config_universe_sha256(),
        "counts": {
            "baseline": 1,
            "stage1a": len(stage1a),
            "stage1b": len(stage1b),
            "stage1b_gate_pass": len(stage1_passes),
            "stage2_step1_single_component": len(stage2_first_wave),
            "stage2_step2_add_one_component": len(stage2_second_wave),
            "stage2_total": len(stage2),
            "stage2_gate_pass": sum(row["gate_pass"] for row in stage2),
            "total_metrics_rows": len(all_rows),
        },
        "train_only_seed_ids": [seed["candidate_id"] for seed in seeds],
        "buyhold": {
            "train": common.buyhold_metrics(
                frame,
                splits["train_start"],
                splits["validation_start"],
            ),
            "validation": common.buyhold_metrics(
                frame,
                splits["validation_start"],
                splits["holdout_start"],
            ),
        },
        "baseline": {
            "candidate_id": baseline["candidate_id"],
            "train": baseline["train"],
            "validation": baseline["validation"],
            "stress_2x_train": baseline["stress_2x_train"],
            "stress_2x_validation": baseline["stress_2x_validation"],
        },
        "frozen_result": {
            "role": role,
            "qualified_candidate": qualified,
            "selection": common.selection_identity(selected),
            "gate_failures": selected["gate_failures"],
        },
        "candidate_metrics_path": str(CANDIDATE_METRICS_PATH.relative_to(common.ROOT)),
        "candidate_metrics_sha256": metrics_sha,
    }
    summary = common.finite_json_value(summary)
    summary["payload_sha256"] = common.payload_sha256(summary)
    common.atomic_write_json(SEARCH_SUMMARY_PATH, summary)
    summary_sha = common.sha256_bytes(SEARCH_SUMMARY_PATH.read_bytes())
    selection_payload = persist_selection(
        selected=selected,
        role=role,
        qualified=qualified,
        split_payload=split_payload,
        metrics_sha=metrics_sha,
        summary_sha=summary_sha,
    )
    print(f"wrote {CANDIDATE_METRICS_PATH}", flush=True)
    print(f"wrote {SEARCH_SUMMARY_PATH}", flush=True)
    print(f"frozen selection: {common.SELECTION_PATH}", flush=True)
    print(
        f"selection payload_sha256={selection_payload['payload_sha256']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
