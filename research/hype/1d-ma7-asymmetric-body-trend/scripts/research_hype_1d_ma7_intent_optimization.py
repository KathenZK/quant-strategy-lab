"""Stage-locked HYPE 1D MA7 intent-optimization research orchestrator.

This file is intentionally an orchestration layer.  Candidate behavior belongs
to the separately frozen state engine; exact V4 behavior belongs to the pinned
fair-window adapter.  The stages here prevent V/H results from feeding back
into development selection.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from functools import lru_cache
import hashlib
import importlib.util
import inspect
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-intent-optimization-preregistration-2026-08-09.md"
)
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_intent_search_engine.py"
INDICATOR_PATH = SCRIPT_DIR / "hype_1d_ma7_original_trend_engine.py"
TRACE_PATH = SCRIPT_DIR / "hype_1d_ma7_intent_state_trace.py"
FAIR_METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_intent_fair_metrics.py"
EVIDENCE_PATH = SCRIPT_DIR / "hype_1d_ma7_intent_evidence.py"
HARNESS_PATH = SCRIPT_DIR / "research_hype_1d_ma7_original_trend.py"
V4_ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RENDERER_PATH = (
    SCRIPT_DIR / "render_hype_1d_ma7_intent_optimization_trade_path.py"
)

RUN_DATE = "2026-08-09"
PREFIX = ARTIFACT_DIR / f"hype_1d_ma7_intent_optimization_{RUN_DATE}"
MANIFEST_PATH = Path(f"{PREFIX}_manifest.json")
MANIFEST_SHA_PATH = Path(f"{PREFIX}_manifest.sha256")
TRIALS_PATH = Path(f"{PREFIX}_development_trials.json")
TRIALS_SHA_PATH = Path(f"{PREFIX}_development_trials.sha256")
DEVELOPMENT_PATH = Path(f"{PREFIX}_development.json")
DEVELOPMENT_SHA_PATH = Path(f"{PREFIX}_development.sha256")
CHAMPION_PATH = Path(f"{PREFIX}_champion.json")
CHAMPION_SHA_PATH = Path(f"{PREFIX}_champion.sha256")
DEVELOPMENT_HTML_PATH = Path(f"{PREFIX}_development_trade_path.html")
DEVELOPMENT_HTML_SHA_PATH = Path(f"{PREFIX}_development_trade_path.sha256")
VALIDATION_PATH = Path(f"{PREFIX}_validation.json")
VALIDATION_SHA_PATH = Path(f"{PREFIX}_validation.sha256")
HOLDOUT_PATH = Path(f"{PREFIX}_holdout.json")
HOLDOUT_SHA_PATH = Path(f"{PREFIX}_holdout.sha256")
FINAL_PATH = Path(f"{PREFIX}_final.json")
FINAL_SHA_PATH = Path(f"{PREFIX}_final.sha256")
FINAL_HTML_PATH = Path(f"{PREFIX}_final_trade_path.html")
FINAL_HTML_SHA_PATH = Path(f"{PREFIX}_final_trade_path.sha256")

BOOK_COUNT = 432
D_FULL = (0, 259)
WFO_FOLDS = ((130, 173), (173, 216), (216, 259))
V_EVAL = (269, 346)
H_EVAL = (356, 432)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MATERIAL_RETURN_PP = 5.0
MATERIAL_MDD_PP = 2.0
MIN_EVAL_TRADES = 3
V4_FULL_RETURN = 398.8406741729143
V4_FULL_MDD = -26.813853621046835
MC_SAMPLES = 10_000
MC_SEED = 20260809

N_VALUES = (1, 2, 3)
A_VALUES = (0, 1, 2)
L_VALUES = (1, 2, 3)
THETA_VALUES = (0.0, 0.01, 0.02, 0.04)
H_VALUES = (0.50, 0.75, 1.00)
C_VALUES = (1, 2)
T_VALUES = (25.0, 30.0, 35.0)
M_VALUES = (2, 3, 4)
M_OB_VALUES = (2, 3, 4)
MANIFEST_EXPECTED_TEST_COUNT = 83
MANIFEST_TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_intent_search_engine.py",
    ROOT / "tests/test_hype_1d_ma7_intent_harness.py",
    ROOT / "tests/test_hype_1d_ma7_intent_state_trace.py",
    ROOT / "tests/test_hype_1d_ma7_intent_fair_metrics.py",
    ROOT / "tests/test_hype_1d_ma7_intent_evidence.py",
    ROOT / "tests/test_hype_1d_ma7_v4_fair_adapter.py",
    ROOT / "tests/test_hype_1d_ma7_intent_optimization_trade_path.py",
    ROOT / "tests/test_hype_1d_ma7_intent_optimization.py",
)


@dataclass(slots=True)
class RuntimeContext:
    harness: ModuleType
    engine: ModuleType
    trace: ModuleType
    fair_metrics: ModuleType
    evidence: ModuleType
    adapter: ModuleType
    renderer: ModuleType
    market: Any
    prepared: dict[int, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _canonical(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _canonical(value),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_locked_json(path: Path, sha_path: Path, payload: Any) -> str:
    if path.exists() or sha_path.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _pretty_bytes(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    with path.open("xb") as handle:
        handle.write(encoded)
    with sha_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def _write_locked_bytes(path: Path, sha_path: Path, payload: bytes) -> str:
    if path.exists() or sha_path.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    with path.open("xb") as handle:
        handle.write(payload)
    with sha_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def _read_locked_json(path: Path, sha_path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file() or not sha_path.is_file():
        raise RuntimeError(f"missing locked artifact or hash: {path.name}")
    parts = sha_path.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2 or parts[1] != path.name:
        raise RuntimeError(f"invalid artifact hash sidecar: {sha_path.name}")
    actual = _sha256(path)
    if parts[0] != actual:
        raise RuntimeError(
            f"artifact hash drift for {path.name}: expected {parts[0]}, got {actual}"
        )
    return json.loads(path.read_text(encoding="utf-8")), actual


def _read_locked_bytes(path: Path, sha_path: Path) -> tuple[bytes, str]:
    if not path.is_file() or not sha_path.is_file():
        raise RuntimeError(f"missing locked artifact or hash: {path.name}")
    parts = sha_path.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2 or parts[1] != path.name:
        raise RuntimeError(f"invalid artifact hash sidecar: {sha_path.name}")
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if parts[0] != actual:
        raise RuntimeError(
            f"artifact hash drift for {path.name}: expected {parts[0]}, got {actual}"
        )
    return payload, actual


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_config(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "prior_side_days": 1,
        "session_open_hour": 0,
        "tolerance_atr": 0.75,
        "slope_lookback": 1,
        "slope_min_atr": 0.0,
        "arm_expiry_days": 1,
        "max_chase_atr": 0.75,
        "flat_entry_mode": "fresh_cross",
        "entry_slope_required": True,
        "direct_reversal_enabled": True,
        "hold_slope_exit_enabled": True,
        "slope_loss_confirm_days": 1,
        "short_rsi_exit_enabled": False,
        "short_rsi_exit_threshold": 30.0,
        "short_rsi_exit_days": 3,
        "roundtrip_cost_rate": 0.0028,
        "overbought_mode": "disabled",
        "overbought_threshold": 70.0,
        "overbought_days": 3,
        "strict_previous_side": False,
    }
    values.update(overrides)
    return values


def _oat_entries() -> list[dict[str, Any]]:
    anchor = base_config(
        short_rsi_exit_enabled=True,
        overbought_mode="slope_or_memory",
    )
    variants = (
        ("OAT00_FULL_INTENT", "full_intent_anchor", {}),
        (
            "OAT01_PERSISTENT_REGIME",
            "persistent_regime_negative_control",
            {"flat_entry_mode": "persistent_regime"},
        ),
        ("OAT02_NO_ARMED", "armed_removed", {"arm_expiry_days": 0}),
        (
            "OAT03_NO_ENTRY_SLOPE",
            "entry_slope_gate_removed",
            {"entry_slope_required": False},
        ),
        (
            "OAT04_NO_SLOPE_LOSS",
            "slope_loss_exit_removed",
            {"hold_slope_exit_enabled": False},
        ),
        (
            "OAT05_NO_ADVERSE_BAND",
            "adverse_band_removed",
            {"tolerance_atr": 0.0},
        ),
        (
            "OAT06_NO_RSI_TP",
            "short_rsi_take_profit_removed",
            {"short_rsi_exit_enabled": False},
        ),
        (
            "OAT07_NO_OVERBOUGHT",
            "overbought_memory_removed",
            {"overbought_mode": "disabled"},
        ),
        (
            "OAT08_NO_DIRECT_REVERSAL",
            "direct_reversal_removed",
            {"direct_reversal_enabled": False},
        ),
    )
    return [
        {
            "id": trial_id,
            "parent": "OAT00_FULL_INTENT" if index else None,
            "role": role,
            "config": {**anchor, **patch},
        }
        for index, (trial_id, role, patch) in enumerate(variants)
    ]


def _stage_a_entries() -> list[dict[str, Any]]:
    rows = []
    for index, (n_cross, expiry, lookback, threshold) in enumerate(
        itertools.product(N_VALUES, A_VALUES, L_VALUES, THETA_VALUES),
        start=1,
    ):
        config = base_config(
            prior_side_days=n_cross,
            arm_expiry_days=expiry,
            slope_lookback=lookback,
            slope_min_atr=threshold,
        )
        rows.append(
            {
                "id": f"A{index:03d}",
                "parent": "STAGE_A_PRESET",
                "config": config,
            }
        )
    return rows


def _template_entries(
    stage: str,
    parent_stage: str,
    parent_count: int,
    patches: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    frozen_patches = tuple(patches)
    rows = []
    index = 0
    for parent_rank in range(1, parent_count + 1):
        parent_slot = f"{parent_stage}_RANK_{parent_rank:02d}"
        for patch in frozen_patches:
            index += 1
            rows.append(
                {
                    "id": f"{stage}{index:03d}",
                    "parent": parent_slot,
                    "config": {"inherit": parent_slot, "overrides": patch},
                }
            )
    return rows


def _manifest_test_files() -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256(path),
        }
        for path in MANIFEST_TEST_PATHS
    ]


def _implementation_pins() -> dict[str, str]:
    return {
        "contract_sha256": _sha256(CONTRACT_PATH),
        "orchestrator_sha256": _sha256(Path(__file__)),
        "engine_sha256": _sha256(ENGINE_PATH),
        "indicator_sha256": _sha256(INDICATOR_PATH),
        "trace_sha256": _sha256(TRACE_PATH),
        "fair_metrics_sha256": _sha256(FAIR_METRICS_PATH),
        "evidence_sha256": _sha256(EVIDENCE_PATH),
        "harness_sha256": _sha256(HARNESS_PATH),
        "v4_adapter_sha256": _sha256(V4_ADAPTER_PATH),
        "renderer_sha256": _sha256(RENDERER_PATH),
    }


def _tested_implementation_hashes() -> dict[str, str]:
    return _implementation_pins()


def _assert_implementation_pins(expected: dict[str, str]) -> None:
    actual = _implementation_pins()
    if actual != expected:
        changed = sorted(
            key for key in set(actual) | set(expected) if actual.get(key) != expected.get(key)
        )
        raise RuntimeError(f"implementation pin drift: {changed}")


def _run_manifest_preflight() -> dict[str, Any]:
    local = self_test()
    if local.get("status") != "PASS":
        raise RuntimeError("orchestrator self-test did not pass")
    tests_before = _manifest_test_files()
    implementation_before = _tested_implementation_hashes()
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--color=no",
            "--disable-warnings",
            *(str(path.relative_to(ROOT)) for path in MANIFEST_TEST_PATHS),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env=environment,
    )
    tests_after = _manifest_test_files()
    implementation_after = _tested_implementation_hashes()
    if tests_before != tests_after or implementation_before != implementation_after:
        raise RuntimeError("manifest preflight inputs changed while tests were running")
    output = f"{completed.stdout}\n{completed.stderr}"
    matches = re.findall(r"(?m)^(\d+) passed in [0-9.]+s$", output)
    if completed.returncode != 0 or matches != [str(MANIFEST_EXPECTED_TEST_COUNT)]:
        raise RuntimeError(
            "manifest preflight must report exactly "
            f"{MANIFEST_EXPECTED_TEST_COUNT} passed with exit 0"
        )
    return {
        "self_test_status": "PASS",
        "pytest_status": "PASS",
        "pytest_passed": int(matches[0]),
        "tests": tests_after,
        "tested_implementation": implementation_after,
    }


@lru_cache(maxsize=1)
def _load_manifest_market_evidence() -> dict[str, Any]:
    adapter = _load_module(V4_ADAPTER_PATH, "hype_intent_manifest_v4_adapter")
    context = adapter.load_context()
    audit = _canonical(context.market.audit)
    return {
        "book_count": int(context.book.count),
        "terminal_ts": pd.Timestamp(context.book.terminal_ts).isoformat(),
        "market_audit": audit,
        "market_audit_sha256": canonical_hash(audit),
    }


def build_manifest(
    *,
    preflight: dict[str, Any] | None = None,
    market_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stage_b = _template_entries(
        "B",
        "A",
        5,
        (
            {"tolerance_atr": band, "slope_loss_confirm_days": days}
            for band, days in itertools.product(H_VALUES, C_VALUES)
        ),
    )
    stage_c = _template_entries(
        "C",
        "B",
        3,
        (
            {
                "short_rsi_exit_enabled": True,
                "short_rsi_exit_threshold": threshold,
                "short_rsi_exit_days": days,
            }
            for threshold, days in itertools.product(T_VALUES, M_VALUES)
        ),
    )
    stage_d = _template_entries(
        "D",
        "C",
        3,
        (
            {
                "overbought_mode": "slope_or_memory",
                "overbought_threshold": 70.0,
                "overbought_days": days,
            }
            for days in M_OB_VALUES
        ),
    )
    payload = {
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "branch": "intent-optimization",
        "run_date": RUN_DATE,
        "contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "no_results": True,
        "splits": {
            "development": list(D_FULL),
            "wfo": [list(item) for item in WFO_FOLDS],
            "validation": list(V_EVAL),
            "holdout": list(H_EVAL),
            "full": [0, BOOK_COUNT],
        },
        "pins": _implementation_pins(),
        "structure_oat": _oat_entries(),
        "stages": {
            "A": _stage_a_entries(),
            "B": stage_b,
            "C": stage_c,
            "D": stage_d,
        },
        "expected_counts": {
            "structure_oat": 9,
            "A": 108,
            "B": 30,
            "C": 27,
            "D": 9,
            "numeric_total": 174,
        },
    }
    if preflight is not None:
        payload["preflight"] = preflight
    if market_evidence is not None:
        payload["market_evidence"] = market_evidence
    return payload


def recompute_slope(daily: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Return a causal daily copy with the contract-normalized MA7 slope."""

    if lookback < 1:
        raise ValueError("slope lookback must be >= 1")
    if "ma7" not in daily or "atr7" not in daily:
        raise ValueError("daily frame lacks ma7/atr7")
    output = daily.copy(deep=True)
    output["slope_atr"] = (
        output["ma7"] - output["ma7"].shift(lookback)
    ) / (lookback * output["atr7"])
    return output


def _assert_gate_comparable(
    candidate: dict[str, Any], comparator: dict[str, Any]
) -> None:
    declared = "gate_eligible" in candidate or "gate_eligible" in comparator
    if not declared:
        return
    if candidate.get("gate_eligible") is not True:
        raise RuntimeError("candidate metric is not eligible for a performance gate")
    if comparator.get("gate_eligible") is not True:
        raise RuntimeError("comparator metric is not eligible for a performance gate")
    if candidate.get("gate_mdd_basis") != comparator.get("gate_mdd_basis"):
        raise RuntimeError("candidate and comparator gate-MDD bases differ")
    if candidate.get("bankrupt") or comparator.get("bankrupt"):
        raise RuntimeError("bankrupt result cannot enter a performance gate")


def double_dominance(candidate: dict[str, Any], comparator: dict[str, Any]) -> dict[str, Any]:
    _assert_gate_comparable(candidate, comparator)
    return_delta = float(candidate["net_return_pct"]) - float(
        comparator["net_return_pct"]
    )
    mdd_delta = float(candidate["max_drawdown_pct"]) - float(
        comparator["max_drawdown_pct"]
    )
    strict = return_delta > 0.0 and mdd_delta > 0.0
    material = return_delta >= MATERIAL_RETURN_PP or mdd_delta >= MATERIAL_MDD_PP
    return {
        "pass": strict and material,
        "strict_return": return_delta > 0.0,
        "strict_mdd": mdd_delta > 0.0,
        "material": material,
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
    }


def no_double_worse(candidate: dict[str, Any], comparator: dict[str, Any]) -> bool:
    _assert_gate_comparable(candidate, comparator)
    return not (
        float(candidate["net_return_pct"]) < float(comparator["net_return_pct"])
        and float(candidate["max_drawdown_pct"])
        < float(comparator["max_drawdown_pct"])
    )


def aggregate_wfo(folds: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(folds)
    if len(rows) != 3:
        raise ValueError("D-WFO aggregate requires exactly three folds")
    equity = math.prod(float(row["equity_multiple"]) for row in rows)
    if any("gate_eligible" in row for row in rows):
        if not all(row.get("gate_eligible") is True for row in rows):
            raise RuntimeError("WFO includes an ineligible gate metric")
        bases = {row.get("gate_mdd_basis") for row in rows}
        if bases != {"daily_extreme_favorable_then_adverse"}:
            raise RuntimeError(f"WFO gate-MDD basis drift: {sorted(bases)}")
        gate_fields = {
            "gate_eligible": True,
            "gate_mdd_basis": "daily_extreme_favorable_then_adverse",
            "bankrupt": any(bool(row.get("bankrupt")) for row in rows),
        }
    else:
        gate_fields = {}
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": min(float(row["max_drawdown_pct"]) for row in rows),
        "closed_trades": sum(int(row["closed_trades"]) for row in rows),
        "turnover": sum(float(row.get("turnover", 0.0)) for row in rows),
        **gate_fields,
    }


def active_parameter_count(config: dict[str, Any]) -> int:
    count = 3  # fresh-cross N, slope L and theta
    count += int(config["arm_expiry_days"] > 0)
    count += int(config["tolerance_atr"] > 0.0)
    count += int(config["hold_slope_exit_enabled"])
    count += int(config["direct_reversal_enabled"])
    count += 3 * int(config["short_rsi_exit_enabled"])
    count += int(config["overbought_mode"] != "disabled")
    return count


def ranking_key(trial: dict[str, Any]) -> tuple[Any, ...]:
    ranking = trial["ranking"]
    return (
        -int(ranking["dominance_domains"]),
        -float(ranking["wfo_return_delta_pp"]),
        -float(ranking["worst_fold_return_delta_pp"]),
        -float(ranking["wfo_mdd_delta_pp"]),
        -float(ranking["full_return_delta_pp"]),
        int(ranking["active_parameter_count"]),
        float(ranking["turnover"]),
        str(trial["id"]),
    )


def rank_trials(trials: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [trial for trial in trials if trial.get("status") == "OK"]
    return sorted(valid, key=ranking_key)


def _normalize_metrics(
    result: Any,
    *,
    gate_mdd_pct: float | None = None,
    drawdown_measurement: str = "native",
    gate_eligible: bool = False,
) -> dict[str, Any]:
    source = result.metrics
    native_mdd = float(source["max_drawdown_pct"])
    if "cost" in source:
        cost_equity_units = float(source["cost"])
        cost_pct_initial = cost_equity_units * 100.0
    else:
        cost_pct_initial = float(source.get("cost_pct_initial", 0.0))
        cost_equity_units = cost_pct_initial / 100.0
    if "funding_payment" in source:
        funding_equity_units = float(source["funding_payment"])
        funding_pct_initial = funding_equity_units * 100.0
    else:
        funding_pct_initial = float(source.get("funding_pct_initial", 0.0))
        funding_equity_units = funding_pct_initial / 100.0
    normalized = {
        "requested_start": source.get("requested_start"),
        "engine_start": source.get("engine_start"),
        "start_ts": source.get("start_ts"),
        "end_ts": source.get("end_ts"),
        "days": float(source.get("days", math.nan)),
        "equity_multiple": float(source["equity_multiple"]),
        "net_return_pct": float(source["net_return_pct"]),
        "max_drawdown_pct": (
            native_mdd if gate_mdd_pct is None else float(gate_mdd_pct)
        ),
        "native_max_drawdown_pct": native_mdd,
        "drawdown_measurement": drawdown_measurement,
        "closed_trades": int(source["closed_trades"]),
        "long_trades": int(source.get("long_trades", 0)),
        "short_trades": int(source.get("short_trades", 0)),
        "turnover": float(source.get("turnover", source.get("turnover_multiple", 0.0))),
        "cost_equity_units": cost_equity_units,
        "cost_pct_initial": cost_pct_initial,
        "cost": cost_equity_units,
        "funding_equity_units": funding_equity_units,
        "funding_pct_initial": funding_pct_initial,
        "funding_payment": funding_equity_units,
        "bankrupt": bool(
            source.get("bankrupt", source.get("bankrupt_intraday", False))
        ),
        "raw": _canonical(source),
    }
    normalized["gate_eligible"] = bool(gate_eligible)
    normalized["gate_mdd_basis"] = (
        "daily_extreme_favorable_then_adverse" if gate_eligible else None
    )
    return normalized


def _fair_audit_summary(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": audit["status"],
        "gate_mdd_pct": float(audit["gate_mdd_pct"]),
        "native_hourly_mdd_pct": float(audit["native_hourly_mdd_pct"]),
        "daily_extreme_order": audit["daily_extreme_order"],
        "solvency": audit["solvency"],
        "consistency": audit["consistency"],
        "ledger": audit["ledger"],
        "action_count": int(audit["action_count"]),
        "atomic_reversal_count": int(audit["atomic_reversal_count"]),
        "terminal_flatten_verified": bool(audit["terminal_flatten_verified"]),
        "audit_path_sha256": canonical_hash(audit["audit_path"]),
        "audit_path_rows": len(audit["audit_path"]),
    }


def _candidate_gate_metrics(
    result: Any,
    config: dict[str, Any],
    start_index: int,
    terminal_index: int,
    slippage: float,
    *,
    retain_full_audit: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = load_runtime()
    data = _prepared_market(runtime, int(config["slope_lookback"]))
    audit = runtime.fair_metrics.v4_compatible_daily_extreme_mdd(
        result,
        data,
        runtime.harness,
        start_index,
        terminal_index,
        slippage,
    )
    metrics = _normalize_metrics(
        result,
        gate_mdd_pct=float(audit["gate_mdd_pct"]),
        drawdown_measurement="v4_compatible_daily_extreme",
        gate_eligible=True,
    )
    evidence = _fair_audit_summary(audit)
    if retain_full_audit:
        evidence["audit_path"] = audit["audit_path"]
    return metrics, evidence


def _v4_gate_metrics(result: Any) -> dict[str, Any]:
    metrics = _normalize_metrics(
        result,
        drawdown_measurement="exact_v4_daily_extreme",
        gate_eligible=True,
    )
    if metrics["bankrupt"]:
        raise RuntimeError("exact V4 comparator reported bankruptcy")
    return metrics


def _enum_value(engine: ModuleType, class_name: str, value: str) -> Any:
    enum_class = getattr(engine, class_name, None)
    if enum_class is None:
        return value
    for member in enum_class:
        if str(member.value) == value or member.name.lower() == value.lower():
            return member
    aliases = {
        ("FlatEntryMode", "fresh_cross"): ("FRESH_CROSS", "FRESH"),
        ("FlatEntryMode", "persistent_regime"): ("PERSISTENT_REGIME", "REGIME"),
        ("OverboughtMode", "disabled"): ("DISABLED",),
        ("OverboughtMode", "slope_or_memory"): (
            "SLOPE_OR_MEMORY",
            "SHORT_QUALIFIER",
            "EARLY_REVERSAL",
        ),
    }
    for name in aliases.get((class_name, value), ()):
        if hasattr(enum_class, name):
            return getattr(enum_class, name)
    raise RuntimeError(f"cannot map {class_name} value {value!r}")


def build_engine_config(engine: ModuleType, config: dict[str, Any]) -> Any:
    """Single adaptation point for the preregistered target engine API."""

    signature = inspect.signature(engine.StrategyConfig)
    expected = set(signature.parameters)
    payload = dict(config)
    payload["flat_entry_mode"] = _enum_value(
        engine, "FlatEntryMode", str(payload["flat_entry_mode"])
    )
    payload["overbought_mode"] = _enum_value(
        engine, "OverboughtMode", str(payload["overbought_mode"])
    )
    missing = sorted(expected - set(payload))
    extra = sorted(set(payload) - expected)
    if missing or extra:
        raise RuntimeError(
            f"target engine StrategyConfig drift: missing={missing}, extra={extra}"
        )
    return engine.StrategyConfig(**payload)


@lru_cache(maxsize=1)
def load_runtime() -> RuntimeContext:
    adapter = _load_module(V4_ADAPTER_PATH, "hype_intent_v4_adapter")
    v4_context = adapter.load_context()
    engine = _load_module(ENGINE_PATH, "hype_intent_candidate_engine")
    trace = _load_module(TRACE_PATH, "hype_intent_state_trace")
    fair_metrics = _load_module(FAIR_METRICS_PATH, "hype_intent_fair_metrics")
    evidence = _load_module(EVIDENCE_PATH, "hype_intent_evidence")
    renderer = _load_module(RENDERER_PATH, "hype_intent_trade_path_renderer")
    return RuntimeContext(
        harness=v4_context.original_harness,
        engine=engine,
        trace=trace,
        fair_metrics=fair_metrics,
        evidence=evidence,
        adapter=adapter,
        renderer=renderer,
        market=v4_context.market,
        prepared={},
    )


def _prepared_market(runtime: RuntimeContext, lookback: int) -> Any:
    if lookback not in runtime.prepared:
        runtime.prepared[lookback] = replace(
            runtime.market,
            daily=recompute_slope(runtime.market.daily, lookback),
        )
    return runtime.prepared[lookback]


def _annotate_window(result: Any, requested_start: int, engine_start: int) -> Any:
    result.metrics["requested_start"] = int(requested_start)
    result.metrics["engine_start"] = int(engine_start)
    return result


def run_candidate(
    config: dict[str, Any],
    start_index: int,
    terminal_index: int,
    *,
    slippage: float = BASE_SLIPPAGE,
    extra_delay_days: int = 0,
    hard_stop_atr: float = 0.0,
    retain: bool = False,
    label: str = "INTENT",
) -> Any:
    runtime = load_runtime()
    engine_config = build_engine_config(runtime.engine, config)
    data = _prepared_market(runtime, int(config["slope_lookback"]))
    result = runtime.harness.backtest(
        runtime.engine,
        data,
        engine_config,
        label=label,
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        extra_delay_days=extra_delay_days,
        hard_stop_atr=hard_stop_atr,
        retain=retain,
    )
    return _annotate_window(result, start_index, start_index)


def _replay_candidate_state_trace(
    config: dict[str, Any],
    start_index: int,
    terminal_index: int,
) -> dict[str, Any]:
    """Replay the pinned R0/no-delay machine path without another backtest."""

    runtime = load_runtime()
    engine_config = build_engine_config(runtime.engine, config)
    data = _prepared_market(runtime, int(config["slope_lookback"]))
    return runtime.trace.replay_state_trace(
        runtime.engine,
        runtime.harness,
        data,
        engine_config,
        start_index,
        terminal_index,
    )


def _assert_trace_parity(result: Any, state_trace: dict[str, Any]) -> dict[str, Any]:
    daily_path = [row for row in result.path if not row.get("terminal")]
    trace_rows = state_trace.get("rows", [])
    if len(daily_path) != len(trace_rows):
        raise RuntimeError(
            "candidate harness/state-trace row-count drift: "
            f"{len(daily_path)} != {len(trace_rows)}"
        )
    path_state = [
        {
            "ts": row.get("ts"),
            "side": int(row.get("side", 0)),
            "armed_side": int(row.get("armed_side", 0)),
            "pending_reason": str(row.get("pending_reason") or ""),
        }
        for row in daily_path
    ]
    traced_state = [
        {
            "ts": row.get("ts"),
            "side": int(row.get("side", 0)),
            "armed_side": int(row.get("armed_side", 0)),
            "pending_reason": str(row.get("pending_reason") or ""),
        }
        for row in trace_rows
    ]
    if path_state != traced_state:
        raise RuntimeError("candidate harness/state-trace daily state drift")

    traced_actions: list[dict[str, Any]] = []
    for event in state_trace.get("events", []):
        if event.get("event") == "decision_fill":
            decision = event["decision"]
            traced_actions.append(
                {
                    "ts": event["ts"],
                    "signal_ts": decision["signal_ts"],
                    "from_side": int(decision["from_side"]),
                    "target_side": int(decision["target_side"]),
                    "reason": decision["reason"],
                    "fills": int(decision["fills"]),
                    "price": float(event["price"]),
                }
            )
        elif event.get("event") == "terminal_flatten":
            traced_actions.append(
                {
                    "ts": event["ts"],
                    "signal_ts": None,
                    "from_side": int(event["from_side"]),
                    "target_side": int(event["target_side"]),
                    "reason": "terminal_flatten",
                    "fills": int(event["fills"]),
                    "price": float(event["price"]),
                }
            )
    if canonical_hash(traced_actions) != canonical_hash(result.actions):
        raise RuntimeError("candidate harness/state-trace action schedule drift")
    return {
        "status": "PASS",
        "daily_rows": len(path_state),
        "actions": len(traced_actions),
        "daily_state_sha256": canonical_hash(path_state),
        "actions_sha256": canonical_hash(traced_actions),
    }


def run_v4(
    start_index: int,
    terminal_index: int,
    *,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    retain: bool = False,
) -> Any:
    result = load_runtime().adapter.run_v4(
        start_index,
        terminal_index,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=retain,
    )
    return _annotate_window(result, start_index, start_index)


def run_v4_flat_start(
    start_index: int,
    terminal_index: int,
    *,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    retain: bool = False,
) -> Any:
    """Align segmented V4 with candidate close-to-next-open flat starts."""

    engine_start = start_index if start_index == 0 else start_index + 1
    if not (0 <= start_index < terminal_index) or engine_start >= terminal_index:
        raise ValueError("invalid V4 flat-start window")
    result = run_v4(
        engine_start,
        terminal_index,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=retain,
    )
    return _annotate_window(result, start_index, engine_start)


def _suite_v4() -> dict[str, Any]:
    runtime = load_runtime()
    anchor_result = runtime.adapter.verify_full_baseline()
    anchor = _v4_gate_metrics(_annotate_window(anchor_result, 0, 0))
    suite: dict[str, Any] = {"full_baseline_anchor": anchor}
    for scenario, slippage in (("base", BASE_SLIPPAGE), ("stress", STRESS_SLIPPAGE)):
        full = _v4_gate_metrics(run_v4(*D_FULL, slippage=slippage))
        folds = [
            _v4_gate_metrics(run_v4_flat_start(start, end, slippage=slippage))
            for start, end in WFO_FOLDS
        ]
        suite[scenario] = {
            "full": full,
            "folds": folds,
            "wfo": aggregate_wfo(folds),
        }
    return suite


def _evaluate_trial(
    trial_id: str,
    stage: str,
    parent_id: str | None,
    config: dict[str, Any],
    v4: dict[str, Any],
) -> dict[str, Any]:
    trial: dict[str, Any] = {
        "id": trial_id,
        "stage": stage,
        "parent_id": parent_id,
        "config": config,
        "config_hash": canonical_hash(config),
    }
    try:
        suite: dict[str, Any] = {}
        base_full_result: Any | None = None
        for scenario, slippage in (
            ("base", BASE_SLIPPAGE),
            ("stress", STRESS_SLIPPAGE),
        ):
            full_result = run_candidate(
                config,
                *D_FULL,
                slippage=slippage,
                retain=True,
                label=trial_id,
            )
            full, full_fair = _candidate_gate_metrics(
                full_result,
                config,
                *D_FULL,
                slippage,
            )
            if scenario == "base":
                base_full_result = full_result
            folds = []
            fold_fair = []
            for index, (start, end) in enumerate(WFO_FOLDS, start=1):
                fold_result = run_candidate(
                    config,
                    start,
                    end,
                    slippage=slippage,
                    retain=True,
                    label=f"{trial_id}-F{index}",
                )
                fold_metrics, fold_audit = _candidate_gate_metrics(
                    fold_result,
                    config,
                    start,
                    end,
                    slippage,
                )
                folds.append(fold_metrics)
                fold_fair.append(fold_audit)
            suite[scenario] = {
                "full": full,
                "full_fair_mdd_audit": full_fair,
                "folds": folds,
                "fold_fair_mdd_audits": fold_fair,
                "wfo": aggregate_wfo(folds),
            }
        full_dom = double_dominance(suite["base"]["full"], v4["base"]["full"])
        wfo_dom = double_dominance(suite["base"]["wfo"], v4["base"]["wfo"])
        worst_fold_delta = min(
            candidate["net_return_pct"] - control["net_return_pct"]
            for candidate, control in zip(
                suite["base"]["folds"],
                v4["base"]["folds"],
                strict=True,
            )
        )
        stress_full = no_double_worse(
            suite["stress"]["full"], v4["stress"]["full"]
        )
        stress_wfo = no_double_worse(
            suite["stress"]["wfo"], v4["stress"]["wfo"]
        )
        trial.update(
            {
                "status": "OK",
                "suite": suite,
                "base_full_evidence": {
                    "trades_sha256": canonical_hash(base_full_result.trades),
                    "path_sha256": canonical_hash(base_full_result.path),
                    "actions_sha256": canonical_hash(base_full_result.actions),
                },
                "ranking": {
                    "dominance_domains": int(full_dom["pass"])
                    + int(wfo_dom["pass"]),
                    "wfo_return_delta_pp": wfo_dom["return_delta_pp"],
                    "worst_fold_return_delta_pp": worst_fold_delta,
                    "wfo_mdd_delta_pp": wfo_dom["mdd_delta_pp"],
                    "full_return_delta_pp": full_dom["return_delta_pp"],
                    "active_parameter_count": active_parameter_count(config),
                    "turnover": suite["base"]["full"]["turnover"],
                },
                "gates": {
                    "full_double_dominance": full_dom,
                    "wfo_double_dominance": wfo_dom,
                    "stress_full_no_double_worse": stress_full,
                    "stress_wfo_no_double_worse": stress_wfo,
                    "development_pass": bool(
                        full_dom["pass"] and wfo_dom["pass"] and stress_full and stress_wfo
                    ),
                },
            }
        )
    except Exception as exc:  # keep every failed/exception trial in evidence
        trial.update(
            {
                "status": "ERROR",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    return trial


def _activation_counts(result: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in getattr(result, "actions", []):
        reason = str(row.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _trade_signatures(
    trades: Iterable[dict[str, Any]], *, include_reasons: bool = True
) -> list[dict[str, Any]]:
    fields = ["side", "entry_ts", "entry_price", "exit_ts", "exit_price"]
    if include_reasons:
        fields.extend(
            ("entry_signal_ts", "entry_reason", "entry_source", "exit_reason")
        )
    return [{field: trade.get(field) for field in fields} for trade in trades]


def _behavior_path_signature(path: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ("ts", "side", "armed_side", "pending_reason", "equity", "terminal")
    return [{field: row.get(field) for field in fields} for row in path]


def _oat_behavior_hash(row: dict[str, Any]) -> Any:
    return row.get("behavior_path_hash", row.get("path_hash"))


def _oat_trade_hash(row: dict[str, Any]) -> Any:
    return row.get("trade_signatures_sha256")


def _activation_count_delta(
    anchor: dict[str, Any], variant: dict[str, Any]
) -> dict[str, int]:
    anchor_counts = anchor.get("activation_counts", {})
    variant_counts = variant.get("activation_counts", {})
    keys = sorted(set(anchor_counts) | set(variant_counts))
    return {
        key: int(variant_counts.get(key, 0)) - int(anchor_counts.get(key, 0))
        for key in keys
        if int(variant_counts.get(key, 0)) != int(anchor_counts.get(key, 0))
    }


def _signature_difference(
    values: list[dict[str, Any]], subtract: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    remaining: dict[str, int] = {}
    for signature in subtract:
        key = canonical_bytes(signature).decode("utf-8")
        remaining[key] = remaining.get(key, 0) + 1
    output = []
    for signature in values:
        key = canonical_bytes(signature).decode("utf-8")
        if remaining.get(key, 0):
            remaining[key] -= 1
        else:
            output.append(signature)
    return output


def _attach_oat_differences(
    rows: list[dict[str, Any]], anchor_id: str
) -> list[dict[str, Any]]:
    anchor = next((row for row in rows if row["id"] == anchor_id), None)
    if anchor is None or anchor.get("status") != "OK":
        return rows
    anchor_signatures = _trade_signatures(anchor["trades"])
    for row in rows:
        if row.get("status") != "OK":
            continue
        signatures = _trade_signatures(row["trades"])
        row["trade_signatures"] = signatures
        row["trade_signatures_sha256"] = canonical_hash(signatures)
        row["added_trade_signatures"] = _signature_difference(
            signatures, anchor_signatures
        )
        row["removed_trade_signatures"] = _signature_difference(
            anchor_signatures, signatures
        )
        row["path_changed"] = _oat_behavior_hash(row) != _oat_behavior_hash(anchor)
        row["trade_path_changed"] = (
            row["trade_signatures_sha256"]
            != canonical_hash(anchor_signatures)
        )
        row["activation_count_deltas"] = _activation_count_delta(anchor, row)
        row["activation_counts_changed"] = bool(
            row["activation_count_deltas"]
        )
    return rows


def _evaluate_oat(entry: dict[str, Any]) -> dict[str, Any]:
    row = {**entry, "config_hash": canonical_hash(entry["config"])}
    try:
        result = run_candidate(
            entry["config"],
            *D_FULL,
            retain=True,
            label=entry["id"],
        )
        state_trace = _replay_candidate_state_trace(entry["config"], *D_FULL)
        metrics, fair_audit = _candidate_gate_metrics(
            result,
            entry["config"],
            *D_FULL,
            BASE_SLIPPAGE,
            retain_full_audit=True,
        )
        trace_parity = _assert_trace_parity(result, state_trace)
        row.update(
            {
                "status": "OK",
                "metrics": metrics,
                "fair_mdd_audit": fair_audit,
                "trace_parity": trace_parity,
                "activation_counts": state_trace["activation_counts"],
                "action_activation_counts": _activation_counts(result),
                "state_trace": state_trace,
                "raw_trades_sha256": canonical_hash(result.trades),
                "path_hash": canonical_hash(result.path),
                "behavior_path_hash": canonical_hash(
                    _behavior_path_signature(result.path)
                ),
                "actions_hash": canonical_hash(result.actions),
                "trades": result.trades,
                "path": result.path,
                "actions": result.actions,
            }
        )
    except Exception as exc:
        row.update(
            {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}
        )
    return row


def _oat_wiring_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    anchor = next((row for row in rows if row["id"] == "OAT00_FULL_INTENT"), None)
    errors = [row["id"] for row in rows if row.get("status") != "OK"]
    if anchor is None or anchor.get("status") != "OK":
        return {
            "pass": False,
            "errors": errors,
            "historically_dormant": [],
            "activation_count_deltas": {},
        }
    path_equal = [
        row["id"]
        for row in rows
        if row["id"] != anchor["id"]
        and row.get("status") == "OK"
        and _oat_trade_hash(row) == _oat_trade_hash(anchor)
    ]
    return {
        "pass": not errors,
        "errors": errors,
        "historically_dormant": path_equal,
        "activation_count_deltas": {
            row["id"]: _activation_count_delta(anchor, row)
            for row in rows
            if row["id"] != anchor["id"] and row.get("status") == "OK"
        },
    }


def _evaluate_template_stage(
    templates: list[dict[str, Any]],
    parents: list[dict[str, Any]],
    stage: str,
    v4: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in templates:
        rank = int(str(template["parent"]).rsplit("_", 1)[1])
        if rank > len(parents):
            rows.append(
                _skipped_template_row(
                    template,
                    stage,
                    "UPSTREAM_INSUFFICIENT",
                    (
                        f"{template['parent']} unavailable: only "
                        f"{len(parents)} valid parent rows"
                    ),
                )
            )
            continue
        parent = parents[rank - 1]
        config = {**parent["config"], **template["config"]["overrides"]}
        rows.append(
            _evaluate_trial(template["id"], stage, parent["id"], config, v4)
        )
    return rows


def _skipped_template_row(
    template: dict[str, Any],
    stage: str,
    reason_code: str,
    reason_detail: str,
) -> dict[str, Any]:
    planned = template["config"]
    return {
        "id": template["id"],
        "stage": stage,
        "parent_id": template.get("parent"),
        "planned_config": planned,
        "planned_config_hash": canonical_hash(planned),
        "config": None,
        "config_hash": None,
        "status": "SKIPPED",
        "skip_reason_code": reason_code,
        "skip_reason_detail": reason_detail,
    }


def _skipped_stage(
    templates: list[dict[str, Any]],
    stage: str,
    reason_detail: str,
    *,
    reason_code: str = "UPSTREAM_INSUFFICIENT",
) -> list[dict[str, Any]]:
    return [
        _skipped_template_row(template, stage, reason_code, reason_detail)
        for template in templates
    ]


def _champion_oat(config: dict[str, Any]) -> list[dict[str, Any]]:
    patches = [
        ("CHAMPION_FULL", {}),
        (
            "CHAMPION_PERSISTENT_REGIME",
            {"flat_entry_mode": "persistent_regime"},
        ),
        ("CHAMPION_NO_ENTRY_SLOPE", {"entry_slope_required": False}),
        ("CHAMPION_NO_SLOPE_LOSS", {"hold_slope_exit_enabled": False}),
        ("CHAMPION_NO_BAND", {"tolerance_atr": 0.0}),
        ("CHAMPION_NO_REVERSAL", {"direct_reversal_enabled": False}),
    ]
    if config["arm_expiry_days"] > 0:
        patches.append(("CHAMPION_NO_ARMED", {"arm_expiry_days": 0}))
    if config["short_rsi_exit_enabled"]:
        patches.append(("CHAMPION_NO_RSI_TP", {"short_rsi_exit_enabled": False}))
    if config["overbought_mode"] != "disabled":
        patches.append(("CHAMPION_NO_OVERBOUGHT", {"overbought_mode": "disabled"}))
    rows = [
        _evaluate_oat(
            {
                "id": trial_id,
                "parent": "CHAMPION_FULL" if patch else None,
                "role": "champion_effective_module_oat",
                "config": {**config, **patch},
            }
        )
        for trial_id, patch in patches
    ]
    return _attach_oat_differences(rows, "CHAMPION_FULL")


def _assert_manifest(manifest: dict[str, Any]) -> None:
    expected_preflight = {
        "self_test_status": "PASS",
        "pytest_status": "PASS",
        "pytest_passed": MANIFEST_EXPECTED_TEST_COUNT,
        "tests": _manifest_test_files(),
        "tested_implementation": _tested_implementation_hashes(),
    }
    if manifest.get("preflight") != expected_preflight:
        raise RuntimeError("manifest preflight evidence or test hashes drifted")
    current_market = _load_manifest_market_evidence()
    audit = current_market.get("market_audit", {})
    data_hashes = (
        audit.get("hourly_sha256"),
        audit.get("phase_input_hourly_sha256"),
        audit.get("funding_sha256"),
    )
    if (
        current_market.get("book_count") != BOOK_COUNT
        or canonical_hash(audit) != current_market.get("market_audit_sha256")
        or any(not isinstance(value, str) or len(value) != 64 for value in data_hashes)
    ):
        raise RuntimeError("manifest market evidence is incomplete or invalid")
    if manifest.get("market_evidence") != current_market:
        raise RuntimeError("manifest market audit or data hashes drifted")
    expected = build_manifest(
        preflight=expected_preflight,
        market_evidence=current_market,
    )
    if canonical_hash(manifest) != canonical_hash(expected):
        raise RuntimeError("manifest drift from deterministic preregistration grid")


def stage_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or MANIFEST_SHA_PATH.exists():
        raise RuntimeError("manifest artifact already exists")
    preflight = _run_manifest_preflight()
    market_evidence = _load_manifest_market_evidence()
    if (
        preflight["tests"] != _manifest_test_files()
        or preflight["tested_implementation"] != _tested_implementation_hashes()
    ):
        raise RuntimeError("manifest inputs changed after preflight completed")
    manifest = build_manifest(
        preflight=preflight,
        market_evidence=market_evidence,
    )
    if manifest["preflight"] != preflight:
        raise RuntimeError("manifest preflight evidence changed after tests")
    for field, expected_hash in preflight["tested_implementation"].items():
        if manifest["pins"][field] != expected_hash:
            raise RuntimeError(f"manifest pin was not covered by tests: {field}")
    _assert_implementation_pins(manifest["pins"])
    digest = _write_locked_json(MANIFEST_PATH, MANIFEST_SHA_PATH, manifest)
    return {"stage": "manifest", "sha256": digest, "counts": manifest["expected_counts"]}


def stage_development() -> dict[str, Any]:
    manifest, manifest_sha = _read_locked_json(MANIFEST_PATH, MANIFEST_SHA_PATH)
    _assert_manifest(manifest)
    expected_pins = dict(manifest["pins"])
    _assert_implementation_pins(expected_pins)
    for path in (
        TRIALS_PATH,
        TRIALS_SHA_PATH,
        DEVELOPMENT_PATH,
        DEVELOPMENT_SHA_PATH,
        CHAMPION_PATH,
        CHAMPION_SHA_PATH,
        DEVELOPMENT_HTML_PATH,
        DEVELOPMENT_HTML_SHA_PATH,
    ):
        if path.exists():
            raise RuntimeError(f"development artifact already exists: {path.name}")

    v4 = _suite_v4()
    oat = _attach_oat_differences(
        [_evaluate_oat(entry) for entry in manifest["structure_oat"]],
        "OAT00_FULL_INTENT",
    )
    oat_gate = _oat_wiring_gate(oat)
    if not oat_gate["pass"]:
        stage_trials = {
            stage: _skipped_stage(
                manifest["stages"][stage],
                stage,
                "structure OAT failed before numeric search",
                reason_code="STRUCTURE_OAT_FAILED",
            )
            for stage in "ABCD"
        }
        skipped_trials = [
            row for stage in "ABCD" for row in stage_trials[stage]
        ]
        trials_payload = {
            "manifest_sha256": manifest_sha,
            "exact_v4": v4,
            "structure_oat": oat,
            "structure_oat_gate": oat_gate,
            "numeric_trials": skipped_trials,
            "stage_rankings": {stage: [] for stage in "ABCD"},
            "final_pool": [],
            "champion_oat": [],
            "numeric_errors": [],
            "numeric_skipped": [row["id"] for row in skipped_trials],
        }
        _assert_implementation_pins(expected_pins)
        trials_sha = _write_locked_json(TRIALS_PATH, TRIALS_SHA_PATH, trials_payload)
        development_payload = {
            "status": "BLOCKED",
            "reason": "structure OAT failed before numeric search",
            "manifest_sha256": manifest_sha,
            "trials_sha256": trials_sha,
            "structure_oat_gate": oat_gate,
            "completed_counts": {stage: 0 for stage in "ABCD"},
            "trial_row_counts": {
                stage: len(stage_trials[stage]) for stage in "ABCD"
            },
            "skipped_counts": {
                stage: len(stage_trials[stage]) for stage in "ABCD"
            },
            "numeric_total": 174,
            "evaluated_total": 0,
            "skipped_total": 174,
            "no_fallback_champion": True,
        }
        _assert_implementation_pins(expected_pins)
        development_sha = _write_locked_json(
            DEVELOPMENT_PATH, DEVELOPMENT_SHA_PATH, development_payload
        )
        return {
            "stage": "development",
            "status": "BLOCKED",
            "trials_sha256": trials_sha,
            "development_sha256": development_sha,
            "champion_sha256": None,
        }
    trials: list[dict[str, Any]] = []
    stage_trials: dict[str, list[dict[str, Any]]] = {}

    stage_a = [
        _evaluate_trial(entry["id"], "A", entry["parent"], entry["config"], v4)
        for entry in manifest["stages"]["A"]
    ]
    trials.extend(stage_a)
    stage_trials["A"] = stage_a
    top_a = rank_trials(stage_a)[:5]
    if len(top_a) < 5:
        stage_b = _skipped_stage(
            manifest["stages"]["B"],
            "B",
            f"Stage A supplied {len(top_a)} of 5 required valid parents",
        )
    else:
        stage_b = _evaluate_template_stage(manifest["stages"]["B"], top_a, "B", v4)
    trials.extend(stage_b)
    stage_trials["B"] = stage_b
    top_b = rank_trials(stage_b)[:3]
    if len(top_a) < 5 or len(top_b) < 3:
        stage_c = _skipped_stage(
            manifest["stages"]["C"],
            "C",
            f"Stage B supplied {len(top_b)} of 3 required valid parents",
        )
    else:
        stage_c = _evaluate_template_stage(manifest["stages"]["C"], top_b, "C", v4)
    trials.extend(stage_c)
    stage_trials["C"] = stage_c
    top_c = rank_trials(stage_c)[:3]
    if len(top_a) < 5 or len(top_b) < 3 or len(top_c) < 3:
        stage_d = _skipped_stage(
            manifest["stages"]["D"],
            "D",
            f"Stage C supplied {len(top_c)} of 3 required valid parents",
        )
    else:
        stage_d = _evaluate_template_stage(manifest["stages"]["D"], top_c, "D", v4)
    trials.extend(stage_d)
    stage_trials["D"] = stage_d
    if len(trials) != 174:
        raise RuntimeError(f"numeric trial count drift: expected 174, got {len(trials)}")

    dedup: dict[str, dict[str, Any]] = {}
    for trial in [*stage_d, *top_c, *top_b]:
        if trial["status"] == "OK":
            dedup.setdefault(trial["config_hash"], trial)
    final_pool = rank_trials(dedup.values())
    first = final_pool[0] if final_pool else None
    numeric_errors = [trial["id"] for trial in trials if trial["status"] == "ERROR"]
    numeric_skipped = [
        trial["id"] for trial in trials if trial["status"] == "SKIPPED"
    ]
    numeric_integrity_pass = all(trial["status"] == "OK" for trial in trials)
    champion_oat: list[dict[str, Any]] = []
    champion_activation: dict[str, Any] | None = None
    wiring_pass = False
    if (
        first is not None
        and numeric_integrity_pass
        and first["gates"]["development_pass"]
    ):
        champion_oat = _champion_oat(first["config"])
        full_path = next(row for row in champion_oat if row["id"] == "CHAMPION_FULL")
        if full_path["status"] == "OK":
            champion_activation = load_runtime().evidence.champion_module_activation(
                full_path
            )
        wiring_pass = bool(
            full_path["status"] == "OK"
            and champion_activation is not None
            and champion_activation["all_applicable_module_gates_pass"] is True
            and all(
                row["status"] == "OK" and row.get("trade_path_changed") is True
                for row in champion_oat
                if row["id"] != "CHAMPION_FULL"
            )
        )

    trials_payload = {
        "manifest_sha256": manifest_sha,
        "exact_v4": v4,
        "structure_oat": oat,
        "structure_oat_gate": oat_gate,
        "numeric_trials": trials,
        "stage_rankings": {
            stage: [trial["id"] for trial in rank_trials(values)]
            for stage, values in stage_trials.items()
        },
        "final_pool": [trial["id"] for trial in final_pool],
        "champion_oat": champion_oat,
        "champion_module_activation": champion_activation,
        "numeric_errors": numeric_errors,
        "numeric_skipped": numeric_skipped,
    }
    if not numeric_integrity_pass or first is None:
        development_status = "BLOCKED"
    elif any(row["status"] != "OK" for row in champion_oat):
        development_status = "BLOCKED"
    elif first["gates"]["development_pass"] and wiring_pass:
        development_status = "PASS"
    else:
        development_status = "FAIL"

    champion_material: dict[str, Any] | None = None
    development_html_bytes: bytes | None = None
    development_html_audit: dict[str, Any] | None = None
    if development_status == "PASS":
        assert first is not None
        retained = run_candidate(
            first["config"],
            *D_FULL,
            retain=True,
            label=f"{first['id']}-CHAMPION",
        )
        retained_metrics, retained_fair = _candidate_gate_metrics(
            retained,
            first["config"],
            *D_FULL,
            BASE_SLIPPAGE,
            retain_full_audit=True,
        )
        reference = first["suite"]["base"]["full"]
        for field in ("equity_multiple", "net_return_pct", "max_drawdown_pct"):
            if not math.isclose(
                float(retained_metrics[field]),
                float(reference[field]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise RuntimeError(f"retained D-full champion replay drift: {field}")
        runtime = load_runtime()
        state_trace = _replay_candidate_state_trace(first["config"], *D_FULL)
        trace_parity = _assert_trace_parity(retained, state_trace)
        retained_v4 = run_v4(*D_FULL, retain=True)
        retained_v4_metrics = _v4_gate_metrics(retained_v4)
        development_html_bytes, development_html_audit = (
            runtime.renderer.build_trade_path_html_document(
                candidate_path=retained.path,
                v4_path=retained_v4.path,
                candidate_trades=retained.trades,
                v4_trades=retained_v4.trades,
                candidate_metrics=retained_metrics,
                v4_metrics=retained_v4_metrics,
                state_trace=state_trace,
                title="HYPE 1D MA7 Intent Optimization：Development 完整交易路径",
                meta={
                    "stage": "development",
                    "window": list(D_FULL),
                    "trial_id": first["id"],
                    "config_hash": first["config_hash"],
                    "gate_mdd_basis": retained_metrics["gate_mdd_basis"],
                },
            )
        )
        if development_html_audit["status"] != "PASS":
            raise RuntimeError("development trade-path HTML consistency gate failed")
        champion_material = {
            "development_metrics": first["suite"],
            "champion_oat": champion_oat,
            "champion_module_activation": champion_activation,
            "trade_path_self_check": {
                "metrics": retained_metrics,
                "fair_mdd_audit": retained_fair,
                "trace_parity": trace_parity,
                "trades_sha256": canonical_hash(retained.trades),
                "path_sha256": canonical_hash(retained.path),
                "actions_sha256": canonical_hash(retained.actions),
                "state_trace_sha256": canonical_hash(state_trace),
                "trades": retained.trades,
                "path": retained.path,
                "actions": retained.actions,
                "state_trace": state_trace,
                "exact_v4": {
                    "metrics": retained_v4_metrics,
                    "trades_sha256": canonical_hash(retained_v4.trades),
                    "path_sha256": canonical_hash(retained_v4.path),
                    "trades": retained_v4.trades,
                    "path": retained_v4.path,
                },
                "engine_config": _canonical(
                    build_engine_config(runtime.engine, first["config"])
                ),
            },
        }

    _assert_implementation_pins(expected_pins)
    trials_sha = _write_locked_json(TRIALS_PATH, TRIALS_SHA_PATH, trials_payload)
    development_payload = {
        "status": development_status,
        "manifest_sha256": manifest_sha,
        "trials_sha256": trials_sha,
        "completed_counts": {
            stage: sum(row["status"] != "SKIPPED" for row in values)
            for stage, values in stage_trials.items()
        },
        "trial_row_counts": {
            stage: len(values) for stage, values in stage_trials.items()
        },
        "skipped_counts": {
            stage: sum(row["status"] == "SKIPPED" for row in values)
            for stage, values in stage_trials.items()
        },
        "numeric_total": len(trials),
        "evaluated_total": sum(row["status"] != "SKIPPED" for row in trials),
        "skipped_total": len(numeric_skipped),
        "first_final_pool_id": first["id"] if first is not None else None,
        "first_development_gate": (
            first["gates"]["development_pass"] if first is not None else False
        ),
        "champion_wiring_gate": wiring_pass,
        "champion_module_activation": champion_activation,
        "numeric_integrity_pass": numeric_integrity_pass,
        "numeric_errors": numeric_errors,
        "numeric_skipped": numeric_skipped,
        "no_fallback_champion": True,
    }
    champion_sha = None
    if development_status == "PASS":
        assert first is not None
        assert champion_material is not None
        assert development_html_bytes is not None
        assert development_html_audit is not None
        development_payload["development_html"] = development_html_audit
        predicted_development_sha = hashlib.sha256(
            _pretty_bytes(development_payload)
        ).hexdigest()
        champion_payload = {
            "status": "FROZEN_DEVELOPMENT_CHAMPION",
            "trial_id": first["id"],
            "config": first["config"],
            "config_hash": first["config_hash"],
            "implementation": expected_pins,
            "upstream": {
                "manifest_sha256": manifest_sha,
                "trials_sha256": trials_sha,
                "development_sha256": predicted_development_sha,
                "development_html_sha256": development_html_audit["sha256"],
            },
            **champion_material,
            "development_html": development_html_audit,
            "no_backup_champion": True,
        }
        html_sha = _write_locked_bytes(
            DEVELOPMENT_HTML_PATH,
            DEVELOPMENT_HTML_SHA_PATH,
            development_html_bytes,
        )
        if html_sha != development_html_audit["sha256"]:
            raise RuntimeError("development HTML hash drift while writing")
        champion_sha = _write_locked_json(
            CHAMPION_PATH, CHAMPION_SHA_PATH, champion_payload
        )
        _assert_implementation_pins(expected_pins)
        development_sha = _write_locked_json(
            DEVELOPMENT_PATH, DEVELOPMENT_SHA_PATH, development_payload
        )
        if development_sha != predicted_development_sha:
            raise RuntimeError("predicted development artifact hash drift")
    else:
        _assert_implementation_pins(expected_pins)
        development_sha = _write_locked_json(
            DEVELOPMENT_PATH, DEVELOPMENT_SHA_PATH, development_payload
        )
    return {
        "stage": "development",
        "status": development_payload["status"],
        "trials_sha256": trials_sha,
        "development_sha256": development_sha,
        "champion_sha256": champion_sha,
    }


def _load_champion() -> tuple[dict[str, Any], str]:
    champion, champion_sha = _read_locked_json(CHAMPION_PATH, CHAMPION_SHA_PATH)
    if canonical_hash(champion["config"]) != champion["config_hash"]:
        raise RuntimeError("champion config canonical hash drift")
    upstream = champion["upstream"]
    manifest, manifest_sha = _read_locked_json(MANIFEST_PATH, MANIFEST_SHA_PATH)
    _assert_manifest(manifest)
    _, trials_sha = _read_locked_json(TRIALS_PATH, TRIALS_SHA_PATH)
    development, development_sha = _read_locked_json(
        DEVELOPMENT_PATH, DEVELOPMENT_SHA_PATH
    )
    if development.get("status") != "PASS":
        raise RuntimeError("development artifact did not freeze a PASS champion")
    actual_upstream = {
        "manifest_sha256": manifest_sha,
        "trials_sha256": trials_sha,
        "development_sha256": development_sha,
    }
    for field, actual in actual_upstream.items():
        if upstream.get(field) != actual:
            raise RuntimeError(f"champion upstream artifact drift: {field}")
    implementation = champion["implementation"]
    if implementation != manifest["pins"]:
        raise RuntimeError("champion implementation does not match manifest pins")
    _assert_implementation_pins(implementation)
    _, html_sha = _read_locked_bytes(
        DEVELOPMENT_HTML_PATH, DEVELOPMENT_HTML_SHA_PATH
    )
    if (
        upstream.get("development_html_sha256") != html_sha
        or champion.get("development_html", {}).get("sha256") != html_sha
        or champion.get("development_html", {}).get("status") != "PASS"
    ):
        raise RuntimeError("champion development HTML evidence drift")
    return champion, champion_sha


def _eval_once(config: dict[str, Any], window: tuple[int, int], label: str) -> dict[str, Any]:
    candidate_base_result = run_candidate(
        config,
        *window,
        slippage=BASE_SLIPPAGE,
        retain=True,
        label=label,
    )
    candidate_base, candidate_base_fair = _candidate_gate_metrics(
        candidate_base_result,
        config,
        *window,
        BASE_SLIPPAGE,
        retain_full_audit=True,
    )
    v4_base_result = run_v4_flat_start(
        *window,
        slippage=BASE_SLIPPAGE,
        retain=True,
    )
    v4_base = _v4_gate_metrics(v4_base_result)
    candidate_stress_result = run_candidate(
        config,
        *window,
        slippage=STRESS_SLIPPAGE,
        retain=True,
        label=f"{label}-STRESS",
    )
    candidate_stress, candidate_stress_fair = _candidate_gate_metrics(
        candidate_stress_result,
        config,
        *window,
        STRESS_SLIPPAGE,
        retain_full_audit=True,
    )
    v4_stress_result = run_v4_flat_start(
        *window,
        slippage=STRESS_SLIPPAGE,
        retain=True,
    )
    v4_stress = _v4_gate_metrics(v4_stress_result)
    state_trace = _replay_candidate_state_trace(config, *window)
    trace_parity = _assert_trace_parity(candidate_base_result, state_trace)
    dominance = double_dominance(candidate_base, v4_base)
    stress_pass = no_double_worse(candidate_stress, v4_stress)
    if candidate_base["closed_trades"] < MIN_EVAL_TRADES:
        status = "INSUFFICIENT"
    elif dominance["pass"] and stress_pass:
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "status": status,
        "window": list(window),
        "candidate": {"base": candidate_base, "stress": candidate_stress},
        "exact_v4": {"base": v4_base, "stress": v4_stress},
        "double_dominance": dominance,
        "stress_no_double_worse": stress_pass,
        "minimum_trades": MIN_EVAL_TRADES,
        "fair_mdd_audit": {
            "base": candidate_base_fair,
            "stress": candidate_stress_fair,
        },
        "trace_parity": trace_parity,
        "state_trace": state_trace,
        "retained_evidence": {
            "candidate": {
                "base": {
                    "trades": candidate_base_result.trades,
                    "path": candidate_base_result.path,
                    "actions": candidate_base_result.actions,
                },
                "stress": {
                    "trades": candidate_stress_result.trades,
                    "path": candidate_stress_result.path,
                    "actions": candidate_stress_result.actions,
                },
            },
            "exact_v4": {
                "base": {
                    "trades": v4_base_result.trades,
                    "path": v4_base_result.path,
                },
                "stress": {
                    "trades": v4_stress_result.trades,
                    "path": v4_stress_result.path,
                },
            },
        },
    }


def stage_validation() -> dict[str, Any]:
    if VALIDATION_PATH.exists() or VALIDATION_SHA_PATH.exists():
        raise RuntimeError("validation was already revealed; rerun is forbidden")
    champion_sha = None
    try:
        champion, champion_sha = _load_champion()
        result = _eval_once(champion["config"], V_EVAL, "VALIDATION")
        _assert_implementation_pins(champion["implementation"])
        payload = {
            "stage": "validation",
            "champion_sha256": champion_sha,
            **result,
            "failure_blocks_holdout": result["status"] != "PASS",
        }
    except Exception as exc:
        payload = {
            "stage": "validation",
            "status": "ERROR",
            "champion_sha256": champion_sha,
            "window": list(V_EVAL),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "failure_blocks_holdout": True,
        }
    digest = _write_locked_json(VALIDATION_PATH, VALIDATION_SHA_PATH, payload)
    return {"stage": "validation", "status": payload["status"], "sha256": digest}


def stage_holdout() -> dict[str, Any]:
    if HOLDOUT_PATH.exists() or HOLDOUT_SHA_PATH.exists():
        raise RuntimeError("holdout was already revealed; rerun is forbidden")
    validation, validation_sha = _read_locked_json(
        VALIDATION_PATH, VALIDATION_SHA_PATH
    )
    if validation["status"] != "PASS":
        raise RuntimeError("validation did not pass; holdout remains locked")
    expected_champion_sha = validation["champion_sha256"]
    try:
        champion, champion_sha = _load_champion()
        if expected_champion_sha != champion_sha:
            raise RuntimeError("validation champion hash drift")
        result = _eval_once(champion["config"], H_EVAL, "HOLDOUT")
        _assert_implementation_pins(champion["implementation"])
        payload = {
            "stage": "holdout",
            "champion_sha256": champion_sha,
            "validation_sha256": validation_sha,
            **result,
            "locked_retrospective_oos": True,
        }
    except Exception as exc:
        payload = {
            "stage": "holdout",
            "status": "ERROR",
            "champion_sha256": expected_champion_sha,
            "validation_sha256": validation_sha,
            "window": list(H_EVAL),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "locked_retrospective_oos": True,
        }
    digest = _write_locked_json(HOLDOUT_PATH, HOLDOUT_SHA_PATH, payload)
    return {"stage": "holdout", "status": payload["status"], "sha256": digest}


def _rolling(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for start in range(0, BOOK_COUNT - 90 + 1, 30):
        end = start + 90
        candidate_result = run_candidate(
            config, start, end, retain=True, label="ROLLING"
        )
        candidate, fair_audit = _candidate_gate_metrics(
            candidate_result,
            config,
            start,
            end,
            BASE_SLIPPAGE,
        )
        comparator = _v4_gate_metrics(run_v4_flat_start(start, end))
        rows.append(
            {
                "start_index": start,
                "terminal_index": end,
                "candidate": candidate,
                "exact_v4": comparator,
                "double_dominance": double_dominance(candidate, comparator),
                "fair_mdd_audit": fair_audit,
            }
        )
    return rows


def _cpcv(config: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = np.array_split(np.arange(BOOK_COUNT), 6)
    rows = []
    for combo_id, selected in enumerate(itertools.combinations(range(6), 2), start=1):
        candidate_equity = 1.0
        v4_equity = 1.0
        candidate_trades = 0
        v4_trades = 0
        pieces = []
        for block_id in selected:
            values = blocks[block_id]
            start = int(values[0]) + 10
            end = int(values[-1]) + 1 - 10
            candidate_result = run_candidate(
                config,
                start,
                end,
                retain=True,
                label=f"CPCV-{combo_id}",
            )
            candidate, fair_audit = _candidate_gate_metrics(
                candidate_result,
                config,
                start,
                end,
                BASE_SLIPPAGE,
            )
            comparator = _v4_gate_metrics(run_v4_flat_start(start, end))
            candidate_equity *= candidate["equity_multiple"]
            v4_equity *= comparator["equity_multiple"]
            candidate_trades += candidate["closed_trades"]
            v4_trades += comparator["closed_trades"]
            pieces.append(
                {
                    "block": block_id,
                    "window": [start, end],
                    "candidate": candidate,
                    "exact_v4": comparator,
                    "fair_mdd_audit": fair_audit,
                }
            )
        rows.append(
            {
                "combo_id": combo_id,
                "test_blocks": list(selected),
                "candidate_equity_multiple": candidate_equity,
                "candidate_net_return_pct": (candidate_equity - 1.0) * 100.0,
                "candidate_closed_trades": candidate_trades,
                "v4_equity_multiple": v4_equity,
                "v4_net_return_pct": (v4_equity - 1.0) * 100.0,
                "v4_closed_trades": v4_trades,
                "insufficient_evidence": candidate_trades < 5,
                "pieces": pieces,
            }
        )
    return rows


def _mc3(label: str, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not trades:
        return [{"label": label, "insufficient_evidence": True, "samples": 0}]
    long_returns = np.asarray(
        [row["net_return"] for row in trades if row["side"] == "long"], dtype=float
    )
    short_returns = np.asarray(
        [row["net_return"] for row in trades if row["side"] == "short"], dtype=float
    )
    rng = np.random.default_rng(MC_SEED)
    ending = np.empty(MC_SAMPLES)
    drawdowns = np.empty(MC_SAMPLES)
    for sample in range(MC_SAMPLES):
        parts: list[float] = []
        if len(long_returns):
            parts.extend(rng.choice(long_returns, len(long_returns), replace=True))
        if len(short_returns):
            parts.extend(rng.choice(short_returns, len(short_returns), replace=True))
        sampled = np.asarray(parts)
        rng.shuffle(sampled)
        curve = np.r_[1.0, np.cumprod(1.0 + sampled)]
        peaks = np.maximum.accumulate(curve)
        ending[sample] = curve[-1]
        drawdowns[sample] = np.min(curve / peaks - 1.0)
    return [
        {
            "label": label,
            "quantile": quantile,
            "equity_multiple": float(np.quantile(ending, quantile)),
            "max_drawdown_pct": float(np.quantile(drawdowns, quantile) * 100.0),
            "loss_probability": float(np.mean(ending < 1.0)),
            "samples": MC_SAMPLES,
            "trades_per_sample": len(trades),
            "insufficient_evidence": len(trades) < 20,
        }
        for quantile in (0.05, 0.10, 0.50, 0.90, 0.95)
    ]


def _trade_adverse_audit(trades: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for trade in trades:
        side = str(trade.get("side"))
        if side not in {"long", "short"}:
            raise RuntimeError(f"invalid trade side in adverse audit: {side!r}")
        entry_price = float(trade["entry_price"])
        max_adverse_price = float(
            trade["lowest"] if side == "long" else trade["highest"]
        )
        direction = 1.0 if side == "long" else -1.0
        calculated = direction * (max_adverse_price - entry_price) / entry_price
        reported = float(trade.get("mae_return", calculated))
        if not math.isclose(reported, calculated, rel_tol=1e-10, abs_tol=1e-10):
            raise RuntimeError("trade MAE does not reconcile to retained adverse price")
        rows.append(
            {
                "trade_id": trade.get("trade_id"),
                "side": side,
                "entry_ts": trade.get("entry_ts"),
                "exit_ts": trade.get("exit_ts"),
                "entry_price": entry_price,
                "max_adverse_price": max_adverse_price,
                "max_adverse_return": calculated,
                "exit_reason": trade.get("exit_reason"),
            }
        )
    return {
        "rows": rows,
        "trade_count": len(rows),
        "worst_max_adverse_return": min(
            (float(row["max_adverse_return"]) for row in rows),
            default=None,
        ),
        "all_trade_paths_retained": True,
    }


def _component_paths() -> dict[str, tuple[Path, Path]]:
    names = (
        "risk",
        "delay",
        "rolling",
        "cpcv",
        "mc3",
        "recent",
        "trades",
        "trade_diff",
        "path",
        "actions",
        "state_trace",
    )
    return {
        name: (
            Path(f"{PREFIX}_{name}.json"),
            Path(f"{PREFIX}_{name}.sha256"),
        )
        for name in names
    }


def stage_finalize() -> dict[str, Any]:
    if any(
        path.exists()
        for path in (
            FINAL_PATH,
            FINAL_SHA_PATH,
            FINAL_HTML_PATH,
            FINAL_HTML_SHA_PATH,
        )
    ):
        raise RuntimeError("finalize was already run")
    champion, champion_sha = _load_champion()
    expected_pins = dict(champion["implementation"])
    _assert_implementation_pins(expected_pins)
    validation, validation_sha = _read_locked_json(
        VALIDATION_PATH, VALIDATION_SHA_PATH
    )
    holdout, holdout_sha = _read_locked_json(HOLDOUT_PATH, HOLDOUT_SHA_PATH)
    if validation["status"] != "PASS" or holdout["status"] != "PASS":
        raise RuntimeError("V and H must both pass before finalize")
    if validation["champion_sha256"] != champion_sha or holdout[
        "champion_sha256"
    ] != champion_sha:
        raise RuntimeError("V/H champion hash drift")

    components = _component_paths()
    for path, sha_path in components.values():
        if path.exists() or sha_path.exists():
            raise RuntimeError(f"final component already exists: {path.name}")

    config = champion["config"]
    candidate_full = run_candidate(config, 0, BOOK_COUNT, retain=True, label="FINAL")
    v4_full = run_v4(0, BOOK_COUNT, retain=True)
    candidate_stress = run_candidate(
        config,
        0,
        BOOK_COUNT,
        slippage=STRESS_SLIPPAGE,
        retain=True,
        label="FINAL-STRESS",
    )
    v4_stress = run_v4(
        0, BOOK_COUNT, slippage=STRESS_SLIPPAGE, retain=True
    )
    candidate_metrics, candidate_fair = _candidate_gate_metrics(
        candidate_full,
        config,
        0,
        BOOK_COUNT,
        BASE_SLIPPAGE,
        retain_full_audit=True,
    )
    v4_metrics = _v4_gate_metrics(v4_full)
    stress_candidate_metrics, stress_candidate_fair = _candidate_gate_metrics(
        candidate_stress,
        config,
        0,
        BOOK_COUNT,
        STRESS_SLIPPAGE,
        retain_full_audit=True,
    )
    stress_v4_metrics = _v4_gate_metrics(v4_stress)
    state_trace = _replay_candidate_state_trace(config, 0, BOOK_COUNT)
    trace_parity = _assert_trace_parity(candidate_full, state_trace)
    comparator_anchor_pass = math.isclose(
        v4_metrics["net_return_pct"], V4_FULL_RETURN, rel_tol=1e-12, abs_tol=1e-12
    ) and math.isclose(
        v4_metrics["max_drawdown_pct"], V4_FULL_MDD, rel_tol=1e-12, abs_tol=1e-12
    )
    if not comparator_anchor_pass:
        raise RuntimeError("exact V4 full comparator drift")
    final_gate = bool(
        candidate_metrics["net_return_pct"] > V4_FULL_RETURN
        and candidate_metrics["max_drawdown_pct"] > V4_FULL_MDD
        and no_double_worse(stress_candidate_metrics, stress_v4_metrics)
    )
    runtime = load_runtime()
    risk_r1 = run_candidate(
        config,
        0,
        BOOK_COUNT,
        hard_stop_atr=1.5,
        retain=True,
        label="R1_SYMMETRIC_HARD_1P5",
    )
    r1_audit = runtime.fair_metrics.audit_r1_gap_stops(
        risk_r1,
        _prepared_market(runtime, int(config["slope_lookback"])),
        1.5,
    )
    r0_r1_diff = runtime.evidence.r0_r1_trade_diff(
        candidate_full.trades,
        risk_r1.trades,
        r0_actions=candidate_full.actions,
        r1_actions=risk_r1.actions,
    )
    risk_contract_pass = bool(
        r1_audit["status"] == "PASS"
        and r1_audit["bankrupt"] is False
        and r1_audit["terminal_flat"] is True
        and int(r1_audit["terminal_side"]) == 0
    )
    r0_position_safety = {
        "bankrupt": bool(candidate_metrics["bankrupt"]),
        "terminal_side": int(candidate_fair["ledger"]["final_side"]),
        "terminal_quantity": float(candidate_fair["ledger"]["final_quantity"]),
        "terminal_flat": int(candidate_fair["ledger"]["final_side"]) == 0,
        "orphan_or_terminal_naked_position_detected": (
            int(candidate_fair["ledger"]["final_side"]) != 0
        ),
        "unprotected_open_position_policy": True,
        "protective_stop_policy": "R0_NONE",
        "scope": "retained ledger terminal state plus declared protection policy",
    }
    r1_position_safety = {
        "bankrupt": bool(r1_audit["bankrupt"]),
        "terminal_side": int(r1_audit["terminal_side"]),
        "terminal_flat": bool(r1_audit["terminal_flat"]),
        "orphan_or_terminal_naked_position_detected": (
            int(r1_audit["terminal_side"]) != 0
        ),
        "unprotected_open_position_policy": False,
        "protective_stop_policy": "symmetric_static_1.5_atr_after_entry",
        "scope": "retained action path, stop audit, and terminal state",
    }
    risk = {
        "R0_NONE": {
            "metrics": candidate_metrics,
            "fair_mdd_audit": candidate_fair,
            "trace_parity": trace_parity,
            "trades_sha256": canonical_hash(candidate_full.trades),
            "path_sha256": canonical_hash(candidate_full.path),
            "actions_sha256": canonical_hash(candidate_full.actions),
            "trades": candidate_full.trades,
            "path": candidate_full.path,
            "actions": candidate_full.actions,
            "all_trade_max_adverse_audit": _trade_adverse_audit(
                candidate_full.trades
            ),
            "position_safety": r0_position_safety,
        },
        "R1_SYMMETRIC_HARD_1P5": {
            "metrics": _normalize_metrics(risk_r1),
            "execution_audit": r1_audit,
            "trades_sha256": canonical_hash(risk_r1.trades),
            "path_sha256": canonical_hash(risk_r1.path),
            "actions_sha256": canonical_hash(risk_r1.actions),
            "trades": risk_r1.trades,
            "path": risk_r1.path,
            "actions": risk_r1.actions,
            "all_trade_max_adverse_audit": _trade_adverse_audit(risk_r1.trades),
            "position_safety": r1_position_safety,
        },
        "R0_R1_TRADE_DIFF": r0_r1_diff,
        "risk_contract_pass": risk_contract_pass,
    }
    delayed_candidate_result = run_candidate(
        config,
        0,
        BOOK_COUNT,
        extra_delay_days=1,
        label="EXTRA_DELAY_1D",
    )
    delayed_candidate = _normalize_metrics(delayed_candidate_result)
    try:
        delay_solvency = runtime.fair_metrics.assert_candidate_solvency(
            delayed_candidate_result
        )
        delay_audit = {"status": "PASS", **delay_solvency}
    except Exception as exc:
        delay_audit = {
            "status": "BLOCKED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    delayed_v4 = _normalize_metrics(run_v4(0, BOOK_COUNT, signal_lag=1))
    delay = {
        "candidate": delayed_candidate,
        "candidate_solvency_audit": delay_audit,
        "exact_v4": delayed_v4,
        "drawdown_measurement": "native_audit_only_not_used_for_gate",
    }
    rolling = _rolling(config)
    cpcv = _cpcv(config)
    mc3 = [*_mc3("candidate", candidate_full.trades), *_mc3("exact_v4", v4_full.trades)]
    recent_candidate = runtime.harness.recent_rows(candidate_full)
    recent_v4 = runtime.adapter.load_context().engine.recent_slices(v4_full)
    recent = {"candidate": recent_candidate, "exact_v4": recent_v4}
    trade_diff = {
        "candidate_vs_exact_v4": runtime.evidence.candidate_v4_trade_attribution(
            candidate_full.trades,
            v4_full.trades,
            candidate_actions=candidate_full.actions,
            exact_v4_actions=(),
        ),
        "r0_vs_r1": r0_r1_diff,
    }
    component_payloads = {
        "risk": risk,
        "delay": delay,
        "rolling": rolling,
        "cpcv": cpcv,
        "mc3": mc3,
        "recent": recent,
        "trades": {"candidate": candidate_full.trades, "exact_v4": v4_full.trades},
        "trade_diff": trade_diff,
        "path": {"candidate": candidate_full.path, "exact_v4": v4_full.path},
        "actions": {"candidate": candidate_full.actions, "exact_v4": []},
        "state_trace": {
            "candidate": state_trace,
            "trace_parity": trace_parity,
        },
    }
    final_html_bytes, final_html_audit = (
        runtime.renderer.build_trade_path_html_document(
            candidate_path=candidate_full.path,
            v4_path=v4_full.path,
            candidate_trades=candidate_full.trades,
            v4_trades=v4_full.trades,
            candidate_metrics=candidate_metrics,
            v4_metrics=v4_metrics,
            state_trace=state_trace,
            title="HYPE 1D MA7 Intent Optimization：全样本完整交易路径",
            meta={
                "stage": "finalize",
                "window": [0, BOOK_COUNT],
                "trial_id": champion["trial_id"],
                "config_hash": champion["config_hash"],
                "gate_mdd_basis": candidate_metrics["gate_mdd_basis"],
            },
        )
    )
    if final_html_audit["status"] != "PASS":
        raise RuntimeError("final trade-path HTML consistency gate failed")
    diagnostic_blockers = []
    diagnostic_warnings = []
    if not risk_contract_pass:
        diagnostic_blockers.append("R1_EXECUTION_AUDIT_BLOCKED")
    if delay_audit["status"] != "PASS":
        diagnostic_warnings.append("EXTRA_DELAY_SOLVENCY_WARNING")
    if diagnostic_blockers:
        final_status = "BLOCKED"
    elif final_gate:
        final_status = "PASS"
    else:
        final_status = "FAIL"
    base_payload = {
        "stage": "finalize",
        "status": final_status,
        "champion_sha256": champion_sha,
        "validation_sha256": validation_sha,
        "holdout_sha256": holdout_sha,
        "candidate_full": candidate_metrics,
        "candidate_full_fair_mdd_audit": candidate_fair,
        "exact_v4_full": v4_metrics,
        "candidate_stress": stress_candidate_metrics,
        "candidate_stress_fair_mdd_audit": stress_candidate_fair,
        "exact_v4_stress": stress_v4_metrics,
        "trace_parity": trace_parity,
        "comparator_anchor_pass": comparator_anchor_pass,
        "final_full_gate": final_gate,
        "risk_contract_pass": risk_contract_pass,
        "diagnostic_blockers": diagnostic_blockers,
        "diagnostic_warnings": diagnostic_warnings,
        "final_html": final_html_audit,
    }
    _assert_implementation_pins(expected_pins)
    hashes = {
        name: _write_locked_json(*components[name], payload)
        for name, payload in component_payloads.items()
    }
    final_html_sha = _write_locked_bytes(
        FINAL_HTML_PATH,
        FINAL_HTML_SHA_PATH,
        final_html_bytes,
    )
    if final_html_sha != final_html_audit["sha256"]:
        raise RuntimeError("final HTML hash drift while writing")
    base_payload["component_sha256"] = hashes
    _assert_implementation_pins(expected_pins)
    digest = _write_locked_json(FINAL_PATH, FINAL_SHA_PATH, base_payload)
    return {"stage": "finalize", "status": final_status, "sha256": digest}


def self_test() -> dict[str, Any]:
    manifest = build_manifest()
    counts = manifest["expected_counts"]
    assert len(manifest["structure_oat"]) == counts["structure_oat"] == 9
    assert len(manifest["stages"]["A"]) == counts["A"] == 108
    assert len(manifest["stages"]["B"]) == counts["B"] == 30
    assert len(manifest["stages"]["C"]) == counts["C"] == 27
    assert len(manifest["stages"]["D"]) == counts["D"] == 9
    assert sum(counts[stage] for stage in "ABCD") == counts["numeric_total"] == 174
    assert manifest["splits"]["development"] == [0, 259]
    assert manifest["splits"]["wfo"] == [[130, 173], [173, 216], [216, 259]]
    assert manifest["splits"]["validation"] == [269, 346]
    assert manifest["splits"]["holdout"] == [356, 432]
    comparator = {"net_return_pct": 10.0, "max_drawdown_pct": -20.0}
    assert double_dominance(
        {"net_return_pct": 15.0, "max_drawdown_pct": -19.0}, comparator
    )["pass"]
    assert no_double_worse(
        {"net_return_pct": 9.0, "max_drawdown_pct": -19.0}, comparator
    )
    return {"stage": "self-test", "status": "PASS", "counts": counts}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("self-test", "manifest", "development", "validation", "holdout", "finalize"),
    )
    return parser.parse_args()


def main() -> None:
    stage = parse_args().stage
    functions = {
        "self-test": self_test,
        "manifest": stage_manifest,
        "development": stage_development,
        "validation": stage_validation,
        "holdout": stage_holdout,
        "finalize": stage_finalize,
    }
    print(json.dumps(_canonical(functions[stage]()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
