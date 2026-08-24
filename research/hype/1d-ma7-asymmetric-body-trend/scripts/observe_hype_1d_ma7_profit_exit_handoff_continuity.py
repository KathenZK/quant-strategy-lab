"""Outcome-locked prospective observer for frozen PEHC_294 versus exact V4."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SPEC_DIR = FAMILY_DIR / "specs"

OBSERVER_PROTOCOL_PATH = SPEC_DIR / (
    "hype-1d-ma7-profit-exit-handoff-continuity-"
    "prospective-observer-v1-2026-08-10.md"
)
OBSERVER_PATH = Path(__file__).resolve()
OBSERVER_TEST_PATH = (
    ROOT
    / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_prospective.py"
)

UPSTREAM_PREFIX = ARTIFACT_DIR / (
    "hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10"
)
PEHC_MANIFEST_PATH = Path(f"{UPSTREAM_PREFIX}_manifest.json")
SHADOW_PATH = Path(f"{UPSTREAM_PREFIX}_shadow_candidate.json")
PROSPECTIVE_PROTOCOL_PATH = Path(f"{UPSTREAM_PREFIX}_prospective_protocol.json")

OBSERVER_PREFIX = ARTIFACT_DIR / (
    "hype_1d_ma7_profit_exit_handoff_continuity_"
    "prospective_observer_v1_2026-08-10"
)
OBSERVER_MANIFEST_PATH = Path(f"{OBSERVER_PREFIX}_manifest.json")
ACCESS_LOCK_PATH = Path(f"{OBSERVER_PREFIX}_access_lock.json")
FINAL_PATH = Path(f"{OBSERVER_PREFIX}_final.json")

PROSPECTIVE_START = pd.Timestamp("2026-08-11T00:00:00Z")
MIN_COMPLETE_DAYS = 90
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_TEST_COUNT = 97


@dataclass(frozen=True, slots=True)
class Runtime:
    research: ModuleType
    engine: ModuleType
    risk: ModuleType
    adapter: ModuleType
    frozen_context: Any
    config: Any
    shadow: dict[str, Any]


def sidecar(path: Path) -> Path:
    return path.with_suffix(".sha256")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> Any:
    if is_dataclass(value):
        return canonical(asdict(value))
    if isinstance(value, dict):
        return {str(key): canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return canonical(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    hash_path = sidecar(path)
    if not path.is_file() or not hash_path.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    fields = hash_path.read_text(encoding="utf-8").strip().split()
    digest = sha256(path)
    if len(fields) != 2 or fields[0] != digest or fields[1] != path.name:
        raise RuntimeError(f"invalid sidecar: {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), digest


def _encoded_json(payload: Any) -> bytes:
    return (
        json.dumps(
            canonical(payload),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def write_locked(path: Path, payload: Any) -> str:
    hash_path = sidecar(path)
    if path.exists() or hash_path.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _encoded_json(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    with path.open("xb") as handle:
        handle.write(encoded)
    with hash_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def write_or_verify_locked(path: Path, payload: Any) -> str:
    if path.exists() or sidecar(path).exists():
        existing, digest = read_locked(path)
        if canonical(existing) != canonical(payload):
            raise RuntimeError(f"existing snapshot differs: {path.name}")
        return digest
    return write_locked(path, payload)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_file_pin(pin: dict[str, Any]) -> Path:
    path = Path(str(pin["path"]))
    expected = str(pin["sha256"])
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(
            f"implementation drift: {path.name}: expected {expected}, got {actual}"
        )
    return path


def observer_implementation_pins() -> dict[str, dict[str, str]]:
    paths = {
        "observer_protocol": OBSERVER_PROTOCOL_PATH,
        "observer": OBSERVER_PATH,
        "observer_test": OBSERVER_TEST_PATH,
    }
    return {
        label: {"path": str(path), "sha256": sha256(path)}
        for label, path in paths.items()
    }


def frozen_artifact_hashes() -> dict[str, str]:
    return {
        "pehc_manifest": read_locked(PEHC_MANIFEST_PATH)[1],
        "shadow_candidate": read_locked(SHADOW_PATH)[1],
        "prospective_protocol": read_locked(PROSPECTIVE_PROTOCOL_PATH)[1],
    }


def assert_frozen_chain() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    pehc_manifest, manifest_sha = read_locked(PEHC_MANIFEST_PATH)
    shadow, shadow_sha = read_locked(SHADOW_PATH)
    protocol, _ = read_locked(PROSPECTIVE_PROTOCOL_PATH)
    if pehc_manifest.get("status") != "PASS":
        raise RuntimeError("invalid PEHC manifest")
    if shadow.get("status") != "SHADOW_FROZEN":
        raise RuntimeError("PEHC shadow candidate is not frozen")
    if shadow.get("config", {}).get("arm_id") != "PEHC_294":
        raise RuntimeError("unexpected PEHC shadow identity")
    if shadow.get("implementation_pins") != pehc_manifest.get("pins"):
        raise RuntimeError("shadow/manifest implementation pins differ")
    if protocol.get("shadow_sha256") != shadow_sha:
        raise RuntimeError("prospective protocol does not pin the shadow candidate")
    if protocol.get("prospective_start") != PROSPECTIVE_START.isoformat():
        raise RuntimeError("prospective start drift")
    if int(protocol.get("minimum_complete_utc_days", -1)) != MIN_COMPLETE_DAYS:
        raise RuntimeError("minimum prospective days drift")
    if pehc_manifest.get("prospective_start") != PROSPECTIVE_START.isoformat():
        raise RuntimeError("PEHC manifest prospective start drift")
    for pin in pehc_manifest["pins"].values():
        _assert_file_pin(pin)
    if manifest_sha != frozen_artifact_hashes()["pehc_manifest"]:
        raise RuntimeError("PEHC manifest hash drift")
    return pehc_manifest, shadow, protocol


def _pinned_test_paths(pehc_manifest: dict[str, Any]) -> tuple[Path, ...]:
    paths = [
        Path(pin["path"])
        for label, pin in sorted(pehc_manifest["pins"].items())
        if "test" in label
    ]
    paths.append(OBSERVER_TEST_PATH)
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return tuple(unique)


def run_preflight(pehc_manifest: dict[str, Any]) -> dict[str, Any]:
    if EXPECTED_TEST_COUNT <= 0:
        raise RuntimeError("EXPECTED_TEST_COUNT must be frozen before manifest")
    test_paths = _pinned_test_paths(pehc_manifest)
    command = [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, test_paths)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else -1
    status = (
        "PASS"
        if completed.returncode == 0 and passed == EXPECTED_TEST_COUNT
        else "FAIL"
    )
    record = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_TEST_COUNT,
        "returncode": completed.returncode,
        "tests": {str(path): sha256(path) for path in test_paths},
        "output_tail": output[-4000:],
    }
    if status != "PASS":
        raise RuntimeError(
            f"observer preflight expected {EXPECTED_TEST_COUNT}, got {passed}"
        )
    return record


def _load_pinned(pin: dict[str, Any], name: str) -> ModuleType:
    return load_module(_assert_file_pin(pin), name)


def load_runtime() -> Runtime:
    pehc_manifest, shadow, _ = assert_frozen_chain()
    pins = pehc_manifest["pins"]
    research = _load_pinned(pins["orchestrator"], "hype_pehc_prospective_research")
    engine = _load_pinned(pins["engine"], "hype_pehc_prospective_engine")
    risk = _load_pinned(pins["metrics"], "hype_pehc_prospective_metrics")
    adapter = _load_pinned(pins["adapter"], "hype_pehc_prospective_adapter")
    frozen_context = adapter.load_context()
    matches = [
        row
        for row in engine.grid_configs()
        if row.arm_id == shadow["config"]["arm_id"]
    ]
    if len(matches) != 1:
        raise RuntimeError("frozen PEHC config is missing from the 490 grid")
    config = matches[0]
    if canonical(config.canonical()) != canonical(shadow["config"]):
        raise RuntimeError("frozen PEHC config payload drift")
    if engine.config_sha256(config) != shadow["config_sha256"]:
        raise RuntimeError("frozen PEHC config hash drift")
    return Runtime(
        research=research,
        engine=engine,
        risk=risk,
        adapter=adapter,
        frozen_context=frozen_context,
        config=config,
        shadow=shadow,
    )


def verify_frozen_anchor(runtime: Runtime) -> dict[str, Any]:
    exact_raw = runtime.adapter.verify_full_baseline(retain=True)
    candidate = runtime.research.run_candidate(
        engine=runtime.engine,
        risk=runtime.risk,
        context=runtime.frozen_context,
        config=runtime.config,
        window=(0, 432),
        retain=True,
    )
    exact = runtime.research.run_exact(
        risk=runtime.risk,
        context=runtime.frozen_context,
        window=(0, 432),
        retain=True,
    )
    if canonical_hash(candidate) != canonical_hash(runtime.shadow["candidate"]):
        raise RuntimeError("frozen PEHC candidate anchor drift")
    if canonical_hash(exact) != canonical_hash(runtime.shadow["exact_v4"]):
        raise RuntimeError("frozen exact V4 anchor drift")
    return {
        "status": "PASS",
        "candidate_payload_sha256": canonical_hash(candidate),
        "exact_v4_payload_sha256": canonical_hash(exact),
        "exact_v4_equity_multiple": float(exact_raw.metrics["equity_multiple"]),
        "exact_v4_closed_trades": int(exact_raw.metrics["closed_trades"]),
    }


def stage_manifest() -> dict[str, Any]:
    if OBSERVER_MANIFEST_PATH.exists() or sidecar(OBSERVER_MANIFEST_PATH).exists():
        raise RuntimeError("observer manifest already exists")
    if ACCESS_LOCK_PATH.exists() or sidecar(ACCESS_LOCK_PATH).exists():
        raise RuntimeError("access lock exists before observer manifest")
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists():
        raise RuntimeError("final exists before observer manifest")
    pehc_manifest, _, _ = assert_frozen_chain()
    preflight = run_preflight(pehc_manifest)
    runtime = load_runtime()
    anchor = verify_frozen_anchor(runtime)
    pins = observer_implementation_pins()
    artifacts = frozen_artifact_hashes()
    payload = {
        "schema": "hype-pehc-prospective-observer-manifest-v1",
        "status": "PASS",
        "prospective_start": PROSPECTIVE_START.isoformat(),
        "minimum_complete_utc_days": MIN_COMPLETE_DAYS,
        "candidate_arm_id": runtime.config.arm_id,
        "candidate_config_sha256": runtime.engine.config_sha256(runtime.config),
        "cold_flat_start": True,
        "first_executable_open_offset_days": 1,
        "terminal_flatten_counts_as_closed_trade": False,
        "earliest_sample_eligible_terminal_is_mandatory": True,
        "interim_performance_disclosure": False,
        "one_shot_final": True,
        "leverage_locked_until_1x_pass": True,
        "observer_pins": pins,
        "frozen_artifacts": artifacts,
        "preflight": preflight,
        "frozen_anchor": anchor,
    }
    if pins != observer_implementation_pins():
        raise RuntimeError("observer implementation drift during manifest")
    if artifacts != frozen_artifact_hashes():
        raise RuntimeError("upstream artifact drift during manifest")
    write_locked(OBSERVER_MANIFEST_PATH, payload)
    return payload


def assert_observer_manifest() -> tuple[dict[str, Any], str]:
    manifest, digest = read_locked(OBSERVER_MANIFEST_PATH)
    if manifest.get("status") != "PASS":
        raise RuntimeError("invalid prospective observer manifest")
    if manifest.get("observer_pins") != observer_implementation_pins():
        raise RuntimeError("prospective observer implementation pin drift")
    if manifest.get("frozen_artifacts") != frozen_artifact_hashes():
        raise RuntimeError("prospective observer upstream artifact drift")
    assert_frozen_chain()
    return manifest, digest


def _latest_complete_terminal(hourly: pd.DataFrame) -> pd.Timestamp:
    if hourly.empty:
        raise RuntimeError("trusted hourly data are empty")
    ts = pd.DatetimeIndex(pd.to_datetime(hourly["ts"], utc=True)).sort_values()
    if ts.has_duplicates:
        raise RuntimeError("trusted hourly timestamps are duplicated")
    if not ts.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise RuntimeError("trusted hourly data are not continuous")
    candidates = ts[(ts.hour == 0) & (ts.minute == 0) & (ts.second == 0)]
    if not len(candidates):
        raise RuntimeError("no UTC terminal open in trusted hourly data")
    terminal = pd.Timestamp(candidates[-1])
    prior = ts[(ts >= terminal - pd.Timedelta(hours=24)) & (ts < terminal)]
    if len(prior) != 24:
        raise RuntimeError("latest UTC terminal does not close a complete prior day")
    return terminal


def build_extended_context(
    runtime: Runtime,
    *,
    terminal_override: pd.Timestamp | None = None,
) -> Any:
    frozen = runtime.frozen_context
    original = frozen.original_harness
    indicator_engine, base, search = original.modules()
    parent = base.load_parent()
    market_engine = parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    hourly = hourly.copy()
    funding = funding.copy()
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    hourly = hourly.sort_values("ts").reset_index(drop=True)
    funding = funding.sort_values("ts").reset_index(drop=True)
    latest = _latest_complete_terminal(hourly)
    terminal = latest if terminal_override is None else pd.Timestamp(terminal_override)
    if terminal.tzinfo is None:
        terminal = terminal.tz_localize("UTC")
    else:
        terminal = terminal.tz_convert("UTC")
    if terminal > latest or terminal.hour != 0 or terminal.minute != 0:
        raise RuntimeError("invalid prospective terminal override")
    if terminal not in set(hourly["ts"]):
        raise RuntimeError("prospective terminal open is unavailable")
    execution_hourly = hourly.loc[hourly["ts"].le(terminal)].copy()
    execution_funding = funding.loc[funding["ts"].lt(terminal)].copy()
    if execution_funding.empty:
        raise RuntimeError("prospective funding input is empty")
    book = base.build_book(
        parent,
        execution_hourly,
        hourly_quality,
        execution_funding,
        funding_quality,
        phase_hours=0,
    )
    features = search.build_features(book, execution_hourly, execution_funding)
    daily = pd.DataFrame(
        {
            "open": book.open,
            "high": book.high,
            "low": book.low,
            "close": book.close,
        },
        index=pd.DatetimeIndex(book.ts),
    )
    daily = indicator_engine.add_daily_indicators(
        daily,
        ma_period=7,
        atr_period=7,
        rsi_period=6,
        slope_lookback=1,
        expected_phase_hour=0,
    )
    audit = {
        "phase_hour": 0,
        "trusted_hourly_audit": hourly_quality,
        "trusted_funding_audit": funding_quality,
        "trusted_hourly_last_ts": hourly["ts"].iloc[-1].isoformat(),
        "trusted_hourly_rows": int(len(hourly)),
        "trusted_funding_last_ts": funding["ts"].iloc[-1].isoformat(),
        "trusted_funding_rows": int(len(funding)),
        "execution_terminal_open": terminal.isoformat(),
        "execution_hourly_rows": int(len(execution_hourly)),
        "execution_funding_rows": int(len(execution_funding)),
        "execution_hourly_sha256": original.canonical_hash(
            execution_hourly,
            ["ts", "open", "high", "low", "close", "volume"],
        ),
        "execution_funding_sha256": original.canonical_hash(
            execution_funding,
            ["ts", "funding_rate"],
        ),
        "daily_start": pd.Timestamp(book.ts[0]).isoformat(),
        "daily_end": pd.Timestamp(book.ts[-1]).isoformat(),
        "daily_rows": int(book.count),
    }
    market = original.MarketData(
        book,
        features,
        daily,
        execution_hourly,
        execution_funding,
        audit,
    )
    return replace(frozen, market=market)


def prospective_window(context: Any) -> dict[str, Any]:
    daily = pd.DatetimeIndex(pd.to_datetime(context.book.ts, utc=True))
    terminal = pd.Timestamp(context.book.terminal_ts)
    if terminal.tzinfo is None:
        terminal = terminal.tz_localize("UTC")
    else:
        terminal = terminal.tz_convert("UTC")
    positions = np.flatnonzero(daily == PROSPECTIVE_START)
    if not len(positions):
        if terminal <= PROSPECTIVE_START:
            return {
                "start_index": None,
                "terminal_index": int(context.book.count),
                "complete_days": 0,
                "terminal_ts": terminal.isoformat(),
                "engine_start_index": None,
            }
        raise RuntimeError("prospective start is missing from complete daily rows")
    start_index = int(positions[0])
    complete_days = int(context.book.count - start_index)
    return {
        "start_index": start_index,
        "terminal_index": int(context.book.count),
        "complete_days": complete_days,
        "terminal_ts": terminal.isoformat(),
        "engine_start_index": start_index + 1,
    }


def _natural_trades(
    trades: Iterable[dict[str, Any]],
    terminal_ts: pd.Timestamp,
) -> list[dict[str, Any]]:
    terminal = pd.Timestamp(terminal_ts)
    return [
        row
        for row in trades
        if str(row.get("exit_reason")) != "terminal_flatten"
        and pd.Timestamp(row["exit_ts"]) < terminal
    ]


def sample_counts(
    *,
    candidate_trades: Iterable[dict[str, Any]],
    control_trades: Iterable[dict[str, Any]],
    handoff_events: Iterable[dict[str, Any]],
    terminal_ts: pd.Timestamp,
) -> dict[str, int]:
    candidate = _natural_trades(candidate_trades, terminal_ts)
    control = _natural_trades(control_trades, terminal_ts)
    events = [
        row
        for row in handoff_events
        if pd.Timestamp(row["ts"]) < pd.Timestamp(terminal_ts)
    ]
    return {
        "candidate_closed_trades": len(candidate),
        "control_closed_trades": len(control),
        "candidate_long_trades": sum(row.get("side") == "long" for row in candidate),
        "candidate_short_trades": sum(row.get("side") == "short" for row in candidate),
        "control_long_trades": sum(row.get("side") == "long" for row in control),
        "control_short_trades": sum(row.get("side") == "short" for row in control),
        "handoff_opportunities": sum(
            row.get("event") == "handoff_opportunity" for row in events
        ),
        "handoff_accepts": sum(row.get("event") == "handoff_accept" for row in events),
    }


def sample_gate(counts: dict[str, int]) -> dict[str, Any]:
    checks = {
        "candidate_closed_trades_gte_5": counts["candidate_closed_trades"] >= 5,
        "control_closed_trades_gte_5": counts["control_closed_trades"] >= 5,
        "candidate_long_trades_gte_2": counts["candidate_long_trades"] >= 2,
        "candidate_short_trades_gte_2": counts["candidate_short_trades"] >= 2,
        "control_long_trades_gte_2": counts["control_long_trades"] >= 2,
        "control_short_trades_gte_2": counts["control_short_trades"] >= 2,
        "handoff_opportunities_gte_2": counts["handoff_opportunities"] >= 2,
        "handoff_accepts_gte_1": counts["handoff_accepts"] >= 1,
    }
    return {"status": "PASS" if all(checks.values()) else "INSUFFICIENT", "checks": checks}


def earliest_sample_eligible_terminal(
    *,
    daily_ts: Iterable[pd.Timestamp],
    book_terminal_ts: pd.Timestamp,
    start_index: int,
    candidate_trades: Iterable[dict[str, Any]],
    control_trades: Iterable[dict[str, Any]],
    handoff_events: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    daily = pd.DatetimeIndex(pd.to_datetime(list(daily_ts), utc=True))
    terminal_values = list(daily) + [pd.Timestamp(book_terminal_ts)]
    for terminal_index in range(start_index + MIN_COMPLETE_DAYS, len(daily) + 1):
        terminal = pd.Timestamp(terminal_values[terminal_index])
        counts = sample_counts(
            candidate_trades=candidate_trades,
            control_trades=control_trades,
            handoff_events=handoff_events,
            terminal_ts=terminal,
        )
        gate = sample_gate(counts)
        if gate["status"] == "PASS":
            return {
                "terminal_index": terminal_index,
                "terminal_ts": terminal.isoformat(),
                "complete_days": terminal_index - start_index,
                "sample_counts": counts,
                "sample_gate": gate,
            }
    return None


def data_prefix_hashes(context: Any) -> dict[str, Any]:
    audit = context.market.audit
    return {
        "terminal_ts": pd.Timestamp(context.book.terminal_ts).isoformat(),
        "execution_hourly_rows": int(audit["execution_hourly_rows"]),
        "execution_hourly_sha256": str(audit["execution_hourly_sha256"]),
        "execution_funding_rows": int(audit["execution_funding_rows"]),
        "execution_funding_sha256": str(audit["execution_funding_sha256"]),
    }


def _snapshot_path(terminal_ts: str) -> Path:
    through = (pd.Timestamp(terminal_ts) - pd.Timedelta(days=1)).date().isoformat()
    return Path(f"{OBSERVER_PREFIX}_observation_through_{through}.json")


def _data_audit_summary(context: Any) -> dict[str, Any]:
    audit = context.market.audit
    return {
        "execution_terminal_open": audit["execution_terminal_open"],
        "execution_hourly_rows": audit["execution_hourly_rows"],
        "execution_funding_rows": audit["execution_funding_rows"],
        "execution_hourly_sha256": audit["execution_hourly_sha256"],
        "execution_funding_sha256": audit["execution_funding_sha256"],
        "trusted_hourly_last_ts": audit["trusted_hourly_last_ts"],
        "trusted_funding_last_ts": audit["trusted_funding_last_ts"],
        "hourly_blocker_count": int(
            audit["trusted_hourly_audit"].get("blocker_count", 0)
        ),
        "funding_blocker_count": int(
            audit["trusted_funding_audit"].get("blocker_count", 0)
        ),
    }


def _run_base_pair(runtime: Runtime, context: Any, window: tuple[int, int]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = runtime.research.run_candidate(
        engine=runtime.engine,
        risk=runtime.risk,
        context=context,
        config=runtime.config,
        window=window,
        retain=True,
    )
    control = runtime.research.run_exact(
        risk=runtime.risk,
        context=context,
        window=window,
        retain=True,
    )
    return candidate, control


def _all_parity(run: dict[str, Any]) -> bool:
    return all(bool(value) for value in run.get("replay_parity", {}).values())


def performance_gate(
    *,
    research: ModuleType,
    candidate: dict[str, Any],
    control: dict[str, Any],
    stress_candidate: dict[str, Any],
    stress_control: dict[str, Any],
    funding_off_candidate: dict[str, Any],
    funding_off_control: dict[str, Any],
    handoff_off: dict[str, Any],
) -> dict[str, Any]:
    base = research.comparison(candidate, control)
    stress = research.comparison(stress_candidate, stress_control)
    checks = {
        "base_return_strictly_higher": bool(base.get("return_higher")),
        "base_real_1h_mdd_strictly_smaller": bool(base.get("mdd_smaller")),
        "base_material": bool(base.get("material")),
        "stress_8bps_not_double_worse": not bool(stress.get("double_worse", True)),
        "funding_off_candidate_solvent": not bool(
            funding_off_candidate["metrics"].get("bankrupt_intraday")
        ),
        "funding_off_control_solvent": not bool(
            funding_off_control["metrics"].get("bankrupt_intraday")
        ),
        "candidate_ledger_parity": _all_parity(candidate),
        "control_ledger_parity": _all_parity(control),
        "handoff_off_ledger_parity": _all_parity(handoff_off),
        "handoff_opportunity_activated": int(
            candidate["activation_counts"].get("handoff_opportunity", 0)
        )
        >= 2,
        "handoff_accept_activated": int(
            candidate["activation_counts"].get("handoff_accept", 0)
        )
        >= 1,
        "handoff_changes_economic_trade_path": (
            candidate["trades_sha256"] != handoff_off["trades_sha256"]
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "base_comparison": base,
        "stress_8bps_comparison": stress,
    }


def _recover_locked_context(runtime: Runtime, lock: dict[str, Any]) -> tuple[Any, tuple[int, int]]:
    terminal = pd.Timestamp(lock["terminal_ts"])
    context = build_extended_context(runtime, terminal_override=terminal)
    if data_prefix_hashes(context) != lock["data_prefix"]:
        raise RuntimeError("locked prospective data prefix drift")
    window_info = prospective_window(context)
    window = (int(window_info["start_index"]), int(window_info["terminal_index"]))
    if list(window) != lock["requested_window"]:
        raise RuntimeError("locked prospective window drift")
    return context, window


def _finalize(runtime: Runtime, observer_manifest_sha: str, lock: dict[str, Any]) -> dict[str, Any]:
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists():
        final, _ = read_locked(FINAL_PATH)
        return final
    context, window = _recover_locked_context(runtime, lock)
    candidate, control = _run_base_pair(runtime, context, window)
    actual_counts = sample_counts(
        candidate_trades=candidate["trades"],
        control_trades=control["trades"],
        handoff_events=candidate["handoff_events"],
        terminal_ts=pd.Timestamp(lock["terminal_ts"]),
    )
    if actual_counts != lock["sample_counts"] or sample_gate(actual_counts)["status"] != "PASS":
        raise RuntimeError("locked sample gate replay drift")
    handoff_off_config = replace(
        runtime.config,
        arm_id=f"{runtime.config.arm_id}_HANDOFF_OFF",
        entry_enabled=False,
    )
    handoff_off = runtime.research.run_candidate(
        engine=runtime.engine,
        risk=runtime.risk,
        context=context,
        config=handoff_off_config,
        window=window,
        retain=True,
    )
    stress_candidate = runtime.research.run_candidate(
        engine=runtime.engine,
        risk=runtime.risk,
        context=context,
        config=runtime.config,
        window=window,
        slippage=STRESS_SLIPPAGE,
        retain=False,
    )
    stress_control = runtime.research.run_exact(
        risk=runtime.risk,
        context=context,
        window=window,
        slippage=STRESS_SLIPPAGE,
        retain=False,
    )
    funding_off_candidate = runtime.research.run_candidate(
        engine=runtime.engine,
        risk=runtime.risk,
        context=context,
        config=runtime.config,
        window=window,
        include_funding=False,
        retain=False,
    )
    funding_off_control = runtime.research.run_exact(
        risk=runtime.risk,
        context=context,
        window=window,
        include_funding=False,
        retain=False,
    )
    gate = performance_gate(
        research=runtime.research,
        candidate=candidate,
        control=control,
        stress_candidate=stress_candidate,
        stress_control=stress_control,
        funding_off_candidate=funding_off_candidate,
        funding_off_control=funding_off_control,
        handoff_off=handoff_off,
    )
    status = gate["status"]
    payload = {
        "schema": "hype-pehc-prospective-final-v1",
        "status": status,
        "observer_manifest_sha256": observer_manifest_sha,
        "access_lock_sha256": sha256(ACCESS_LOCK_PATH),
        "candidate_arm_id": runtime.config.arm_id,
        "prospective_start": PROSPECTIVE_START.isoformat(),
        "terminal_ts": lock["terminal_ts"],
        "complete_days": lock["complete_days"],
        "requested_window": lock["requested_window"],
        "engine_window": [window[0] + 1, window[1]],
        "sample_counts": actual_counts,
        "sample_gate": sample_gate(actual_counts),
        "performance_gate": gate,
        "candidate": candidate,
        "exact_v4": control,
        "handoff_off": handoff_off,
        "stress_8bps": {
            "candidate": stress_candidate,
            "exact_v4": stress_control,
        },
        "funding_off": {
            "candidate": funding_off_candidate,
            "exact_v4": funding_off_control,
        },
        "data_prefix": lock["data_prefix"],
        "leverage_unlocked": status == "PASS",
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "failure_rule": (
            None
            if status == "PASS"
            else "no retuning on this window; materially new mechanism and later start required"
        ),
    }
    assert_observer_manifest()
    write_locked(FINAL_PATH, payload)
    return payload


def _observe() -> dict[str, Any]:
    observer_manifest, observer_manifest_sha = assert_observer_manifest()
    runtime = load_runtime()
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists():
        final, final_sha = read_locked(FINAL_PATH)
        return {
            "schema": "hype-pehc-prospective-observer-status-v1",
            "status": "FINAL_ALREADY_LOCKED",
            "final_status": final["status"],
            "final_sha256": final_sha,
            "terminal_ts": final["terminal_ts"],
        }
    if ACCESS_LOCK_PATH.exists() or sidecar(ACCESS_LOCK_PATH).exists():
        lock, _ = read_locked(ACCESS_LOCK_PATH)
        if lock.get("observer_manifest_sha256") != observer_manifest_sha:
            raise RuntimeError("access lock observer manifest drift")
        return _finalize(runtime, observer_manifest_sha, lock)

    context = build_extended_context(runtime)
    info = prospective_window(context)
    base_snapshot = {
        "schema": "hype-pehc-prospective-observer-status-v1",
        "observer_manifest_sha256": observer_manifest_sha,
        "prospective_start": PROSPECTIVE_START.isoformat(),
        "terminal_ts": info["terminal_ts"],
        "complete_days": info["complete_days"],
        "minimum_complete_days": MIN_COMPLETE_DAYS,
        "requested_window": (
            None
            if info["start_index"] is None
            else [info["start_index"], info["terminal_index"]]
        ),
        "engine_window": (
            None
            if info["engine_start_index"] is None
            else [info["engine_start_index"], info["terminal_index"]]
        ),
        "data_audit": _data_audit_summary(context),
        "performance_disclosed": False,
        "leverage_locked": True,
        "registered": False,
        "promoted": False,
        "live_ready": False,
    }
    if int(info["complete_days"]) < MIN_COMPLETE_DAYS:
        payload = {
            **base_snapshot,
            "status": "INSUFFICIENT_FUTURE_DATA",
            "sample_counts": None,
            "sample_gate": "NOT_EVALUATED_BEFORE_90_DAYS",
        }
        write_or_verify_locked(_snapshot_path(info["terminal_ts"]), payload)
        return payload

    latest_window = (int(info["start_index"]), int(info["terminal_index"]))
    candidate, control = _run_base_pair(runtime, context, latest_window)
    eligible = earliest_sample_eligible_terminal(
        daily_ts=context.book.ts,
        book_terminal_ts=context.book.terminal_ts,
        start_index=latest_window[0],
        candidate_trades=candidate["trades"],
        control_trades=control["trades"],
        handoff_events=candidate["handoff_events"],
    )
    if eligible is None:
        counts = sample_counts(
            candidate_trades=candidate["trades"],
            control_trades=control["trades"],
            handoff_events=candidate["handoff_events"],
            terminal_ts=pd.Timestamp(info["terminal_ts"]),
        )
        payload = {
            **base_snapshot,
            "status": "INSUFFICIENT_EVENT_SAMPLE",
            "sample_counts": counts,
            "sample_gate": sample_gate(counts),
        }
        write_or_verify_locked(_snapshot_path(info["terminal_ts"]), payload)
        return payload

    locked_terminal = pd.Timestamp(eligible["terminal_ts"])
    locked_context = build_extended_context(runtime, terminal_override=locked_terminal)
    locked_info = prospective_window(locked_context)
    lock_payload = {
        "schema": "hype-pehc-prospective-access-lock-v1",
        "status": "LOCKED_FOR_ONE_SHOT_ADJUDICATION",
        "observer_manifest_sha256": observer_manifest_sha,
        "frozen_artifacts": observer_manifest["frozen_artifacts"],
        "candidate_arm_id": runtime.config.arm_id,
        "prospective_start": PROSPECTIVE_START.isoformat(),
        "terminal_ts": eligible["terminal_ts"],
        "complete_days": eligible["complete_days"],
        "requested_window": [
            int(locked_info["start_index"]),
            int(locked_info["terminal_index"]),
        ],
        "engine_window": [
            int(locked_info["engine_start_index"]),
            int(locked_info["terminal_index"]),
        ],
        "sample_counts": eligible["sample_counts"],
        "sample_gate": eligible["sample_gate"],
        "data_prefix": data_prefix_hashes(locked_context),
        "performance_disclosed": False,
        "leverage_locked": True,
    }
    write_locked(ACCESS_LOCK_PATH, lock_payload)
    return _finalize(runtime, observer_manifest_sha, lock_payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("self-test", "manifest", "observe"),
        required=True,
    )
    args = parser.parse_args()
    stages: dict[str, Callable[[], dict[str, Any]]] = {
        "manifest": stage_manifest,
        "observe": _observe,
    }
    if args.stage == "self-test":
        assert PROSPECTIVE_START == pd.Timestamp("2026-08-11T00:00:00Z")
        assert MIN_COMPLETE_DAYS == 90
        assert EXPECTED_TEST_COUNT > 0
        print("PEHC prospective observer self-test PASS")
        return
    result = stages[args.stage]()
    print(
        json.dumps(
            {
                "stage": args.stage,
                "status": result["status"],
                "terminal_ts": result.get("terminal_ts"),
                "complete_days": result.get("complete_days"),
                "performance_disclosed": result.get("performance_disclosed"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
