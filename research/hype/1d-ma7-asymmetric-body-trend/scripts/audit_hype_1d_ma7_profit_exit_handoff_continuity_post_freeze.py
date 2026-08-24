"""Post-freeze PEHC controls and per-episode causal ablations.

This audit cannot alter the frozen shadow candidate or its ordering.  It only
materializes preregistered long-only/RSI-only controls and leave-one-event-out
evidence that is cumbersome to repeat in the primary Stage C artifact.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ORCHESTRATOR_PATH = SCRIPT_DIR / "research_hype_1d_ma7_profit_exit_handoff_continuity.py"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_post_freeze_ablation.json"


def load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    research = load(ORCHESTRATOR_PATH, "hype_pehc_post_freeze_research")
    manifest = research.assert_manifest()
    shadow, shadow_sha = research.read_locked(research.SHADOW_PATH)
    stage_c, stage_c_sha = research.read_locked(research.STAGE_C_PATH)
    if shadow.get("status") != "SHADOW_FROZEN":
        raise RuntimeError("PEHC shadow candidate is not frozen")
    arm_id = str(shadow["config"]["arm_id"])
    row = next(item for item in stage_c["rows"] if item["arm_id"] == arm_id)
    engine, risk, _, context = research.load_runtime()
    config = research._config_by_id(engine)[arm_id]

    oapp_engine, oapp_risk, adapter, _, oapp_context = research._OAPP_RESEARCH.load_runtime()
    long_only_config = oapp_engine.WTLConfig(
        "CONTROL_LONG_ONLY",
        long_exit=oapp_engine.TrailExit("fraction", 0.5, 0.10, 2),
    )
    rsi_only_config = oapp_engine.WTLConfig(
        "CONTROL_RSI_ONLY",
        short_rsi=oapp_engine.ShortRSIExit(20.0, 2),
    )
    controls = {
        "exact_v4": stage_c["controls"]["v4_full"],
        "fixed_oapp": stage_c["controls"]["oapp_full"],
        "long_only": research._OAPP_RESEARCH.run_one(
            engine=oapp_engine,
            risk=oapp_risk,
            adapter=adapter,
            context=oapp_context,
            window=research.FULL,
            config=long_only_config,
        ),
        "rsi_only": research._OAPP_RESEARCH.run_one(
            engine=oapp_engine,
            risk=oapp_risk,
            adapter=adapter,
            context=oapp_context,
            window=research.FULL,
            config=rsi_only_config,
        ),
        "shadow_without_entry": row["shadow_only"],
        "handoff_without_rsi": row["no_rsi"],
    }
    full = row["full"]
    oapp = stage_c["controls"]["oapp_full"]
    leave_one: list[dict[str, Any]] = []
    for origin in row["accepted_origins"]:
        ablated = research.run_candidate(
            engine=engine,
            risk=risk,
            context=context,
            config=research.replace(
                config,
                arm_id=f"{arm_id}_LEAVE_{origin}",
                blocked_origin_indices=(int(origin),),
            ),
            window=research.FULL,
        )
        leave_one.append(
            {
                "origin_index": int(origin),
                "run": ablated,
                "vs_frozen_candidate": research.comparison(full, ablated),
                "remaining_vs_oapp": research.comparison(ablated, oapp),
            }
        )
    keep_one = [
        {
            "origin_index": int(origin),
            "run": run,
            "vs_oapp": research.comparison(run, oapp),
        }
        for origin, run in zip(row["accepted_origins"], row["keep_one"], strict=True)
    ]
    payload = {
        "schema": "hype-pehc-post-freeze-ablation-v1",
        "status": "PASS",
        "selection_effect": "NONE_POST_FREEZE_AUDIT_ONLY",
        "shadow_sha256": shadow_sha,
        "stage_c_sha256": stage_c_sha,
        "manifest_pins": manifest["pins"],
        "arm_id": arm_id,
        "config": config.canonical(),
        "controls": controls,
        "frozen_candidate": full,
        "keep_one_event": keep_one,
        "leave_one_event_out": leave_one,
        "max_winner_origin": row["max_winner_origin"],
        "max_winner_removed": row["max_winner_removed"],
        "max_winner_removed_vs_oapp": row["max_winner_removed_vs_oapp"],
        "all_leave_one_solvent": all(item["run"].get("status") == "PASS" for item in leave_one),
    }
    research.assert_pins(manifest["pins"])
    research.write_locked(OUTPUT_PATH, payload)
    print(f"PEHC post-freeze ablation PASS: {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
