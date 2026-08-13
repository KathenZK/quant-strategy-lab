"""Audit exact V6 short cooldown 5d -> 2d as one isolated variable."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_v6_rsi6_memory_cross.py"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-v6-short-cooldown-2d-contract-2026-08-10.md"
)
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v6_rsi6_memory_cross_engine.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_short_cooldown_2d_2026-08-10.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_locked(payload: dict[str, Any]) -> None:
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if OUTPUT_PATH.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")


def preflight() -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", str(TEST_PATH)]
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return {"status": "PASS", "command": command, "stdout": result.stdout.strip()}


def evaluate(
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any | None,
) -> dict[str, Any]:
    full = research.run_once(engine, risk, context, config, research.FULL)
    stress = research.run_once(
        engine,
        risk,
        context,
        config,
        research.FULL,
        slippage=research.STRESS_SLIPPAGE,
    )
    blocks = [
        research.run_once(engine, risk, context, config, window)
        for window in research.BLOCKS
    ]
    recent = {
        label: research.run_once(engine, risk, context, config, window)
        for label, window in research.recent_windows(context.book.count).items()
    }
    return {
        "full": full,
        "stress": stress,
        "blocks": blocks,
        "block_summary": research.block_summary(blocks),
        "recent": recent,
    }


def comparison(research: ModuleType, candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    full = research.compare(candidate["full"], control["full"])
    stress = research.compare(candidate["stress"], control["stress"])
    blocks = research.block_compare(
        candidate["block_summary"], control["block_summary"]
    )
    checks = {
        "full_return_higher": full["return_higher"],
        "full_mdd_smaller": full["mdd_smaller"],
        "stress_not_double_worse": not stress["double_worse"],
        "blocks_not_double_worse": not blocks["double_worse"],
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "full": full,
        "stress": stress,
        "blocks": blocks,
        "trade_diff": research.trade_diff(candidate["full"], control["full"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen audit")
    tests = preflight()
    research = load_module(RESEARCH_PATH, "short_cd2_research")
    engine, risk, context = research.load_runtime()
    if context.long_config.cooldown_days != 2 or context.short_config.cooldown_days != 5:
        raise RuntimeError("exact V6 cooldown anchor drift")
    short_2d = replace(context.short_config, cooldown_days=2)
    before = asdict(context.short_config)
    after = asdict(short_2d)
    changed = {key for key in before if before[key] != after[key]}
    if changed != {"cooldown_days"}:
        raise RuntimeError(f"non-isolated short config change: {changed}")
    context_2d = replace(context, short_config=short_2d)
    memory_config = next(
        config
        for config in research.configs(engine)
        if config.arm_id == "A1_PRIOR5_BOTH"
    )
    exact_5d = evaluate(research, engine, risk, context, None)
    exact_2d = evaluate(research, engine, risk, context_2d, None)
    memory_5d = evaluate(research, engine, risk, context, memory_config)
    memory_2d = evaluate(research, engine, risk, context_2d, memory_config)
    exact_compare = comparison(research, exact_2d, exact_5d)
    memory_compare = comparison(research, memory_2d, memory_5d)
    payload = {
        "schema": "hype-v6-short-cooldown-2d-v1",
        "status": exact_compare["status"],
        "research_state": "all 432d exposed / diagnostic-only / not promoted / not live-ready",
        "preflight": tests,
        "variable": {
            "field": "short_config.cooldown_days",
            "control": 5,
            "candidate": 2,
            "changed_fields": sorted(changed),
            "engine_semantics": "global cooldown after short exit blocks both natural long and natural short entries",
        },
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "costs": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": research.BASE_SLIPPAGE,
            "stress_slippage_per_fill": research.STRESS_SLIPPAGE,
            "funding": True,
        },
        "exact_v6": {
            "control_5d": exact_5d,
            "candidate_2d": exact_2d,
            "comparison": exact_compare,
        },
        "rsi_memory_primary": {
            "control_5d": memory_5d,
            "candidate_2d": memory_2d,
            "comparison": memory_compare,
        },
        "pins": {
            "contract": sha256(CONTRACT_PATH),
            "audit": sha256(SELF_PATH),
            "research": sha256(RESEARCH_PATH),
            "engine": sha256(research.ENGINE_PATH),
            "test": sha256(TEST_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v6_changed": False,
    }
    write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "exact_5d": exact_5d["full"]["metrics"],
                "exact_2d": exact_2d["full"]["metrics"],
                "artifact": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
