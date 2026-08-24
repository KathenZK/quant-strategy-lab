"""Post-reveal full-history comparison of exact V6 and DTEC_L189."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_v6_delayed_episode.py"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_delayed_episode_engine.py"
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_delayed_episode_2026-08-10_manifest.json"
STAGE_A_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_a.json"
FINAL_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_delayed_episode_2026-08-10_final.json"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_dtec_l189_full_history_post_reveal_2026-08-10.json"

FULL = (0, 432)
TAIL = (324, 432)
ARM_ID = "DTEC_L189"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar(path: Path) -> Path:
    return Path(f"{path}.sha256")


def read_locked(path: Path) -> dict[str, Any]:
    expected = sidecar(path).read_text(encoding="utf-8").split()[0]
    if sha256(path) != expected:
        raise RuntimeError(f"sidecar mismatch: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_locked(path: Path, payload: dict[str, Any]) -> str:
    document = json.dumps(sanitize(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"
    digest = hashlib.sha256(document.encode()).hexdigest()
    with path.open("x", encoding="utf-8") as handle:
        handle.write(document)
    with sidecar(path).open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def annualized_return(equity_multiple: float, bars: int) -> float:
    return (equity_multiple ** (365.0 / bars) - 1.0) * 100.0


def compact_run(research: ModuleType, run: dict[str, Any], *, bars: int) -> dict[str, Any]:
    metrics = dict(run["metrics"])
    metrics["annualized_return_pct_365_over_bars"] = annualized_return(
        float(metrics["equity_multiple"]), bars
    )
    return {
        "status": run["status"],
        "arm_id": run["arm_id"],
        "requested_window": run["requested_window"],
        "engine_window": run["engine_window"],
        "metrics": metrics,
        "accuracy": run["accuracy"],
        "activation_counts": run["activation_counts"],
        "episode_events": run["episode_events"],
        "handoff_events": run["handoff_events"],
        "trades_sha256": run["trades_sha256"],
        "trades": research.economic_trades(run["trades"]),
    }


def trade_diff(research: ModuleType, control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    control_rows = research.economic_trades(control["trades"])
    candidate_rows = research.economic_trades(candidate["trades"])
    control_keys = {
        json.dumps(sanitize(row), sort_keys=True, separators=(",", ":"), allow_nan=False)
        for row in control_rows
    }
    candidate_keys = {
        json.dumps(sanitize(row), sort_keys=True, separators=(",", ":"), allow_nan=False)
        for row in candidate_rows
    }
    return {
        "exact_common_count": len(control_keys & candidate_keys),
        "control_only": [row for row in control_rows if json.dumps(sanitize(row), sort_keys=True, separators=(",", ":"), allow_nan=False) not in candidate_keys],
        "candidate_only": [row for row in candidate_rows if json.dumps(sanitize(row), sort_keys=True, separators=(",", ":"), allow_nan=False) not in control_keys],
    }


def main() -> None:
    if OUTPUT_PATH.exists() or sidecar(OUTPUT_PATH).exists():
        raise RuntimeError("post-reveal full-history artifact already exists")
    manifest = read_locked(MANIFEST_PATH)
    stage_a = read_locked(STAGE_A_PATH)
    final = read_locked(FINAL_PATH)
    if manifest.get("status") != "PASS" or stage_a.get("status") != "PASS":
        raise RuntimeError("upstream DTEC evidence is not PASS")
    if final.get("status") != "HARD-GATE-FAILED":
        raise RuntimeError("unexpected upstream DTEC final status")

    research = load_module(RESEARCH_PATH, "hype_dtec_full_history_research")
    engine, risk, _, context = research.load_runtime()
    config = research.config_lookup(engine)[ARM_ID]
    selected = stage_a["selected_a2"]["long"]
    if ARM_ID not in selected:
        raise RuntimeError("DTEC_L189 is not a frozen selected long parent")

    full_control = research.run_once(
        engine=engine, risk=risk, context=context, window=FULL, config=None, retain=True
    )
    full_candidate = research.run_once(
        engine=engine, risk=risk, context=context, window=FULL, config=config, retain=True
    )
    tail_control = research.run_once(
        engine=engine, risk=risk, context=context, window=TAIL, config=None, retain=True
    )
    tail_candidate = research.run_once(
        engine=engine, risk=risk, context=context, window=TAIL, config=config, retain=True
    )

    payload = {
        "schema": "hype-v6-dtec-l189-full-history-post-reveal-v1",
        "status": "DIAGNOSTIC_COMPLETE",
        "evidence_role": "post-reveal diagnostic only / not OOS promotion evidence",
        "user_authorized_full_history_access": True,
        "upstream_final_status_unchanged": final["status"],
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "config": config.canonical(),
        "config_sha256": engine.config_sha256(config),
        "source_pins": {
            "audit": sha256(Path(__file__)),
            "research": sha256(RESEARCH_PATH),
            "engine": sha256(ENGINE_PATH),
            "manifest": sha256(MANIFEST_PATH),
            "stage_a": sha256(STAGE_A_PATH),
            "final": sha256(FINAL_PATH),
        },
        "full_history": {
            "bars": 432,
            "control": compact_run(research, full_control, bars=432),
            "candidate": compact_run(research, full_candidate, bars=432),
            "comparison": research.comparison(full_candidate, full_control),
            "trade_diff": trade_diff(research, full_control, full_candidate),
        },
        "previously_unaccessed_tail_cold_flat": {
            "bars": 108,
            "control": compact_run(research, tail_control, bars=108),
            "candidate": compact_run(research, tail_candidate, bars=108),
            "comparison": research.comparison(tail_candidate, tail_control),
            "trade_diff": trade_diff(research, tail_control, tail_candidate),
            "note": "Cold-flat tail starts execution at index 325 and is diagnostic after upstream D gate failure.",
        },
    }
    digest = write_locked(OUTPUT_PATH, payload)
    print(json.dumps({"path": str(OUTPUT_PATH), "sha256": digest, **payload}, indent=2, default=str))


if __name__ == "__main__":
    main()
