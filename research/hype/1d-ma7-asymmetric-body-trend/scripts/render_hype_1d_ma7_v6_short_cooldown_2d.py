"""Render exact V6 short cooldown 2d against the frozen 5d control."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_v6_rsi6_memory_cross.py"
BASE_RENDERER_PATH = (
    SCRIPT_DIR / "render_hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2.py"
)
HELPER_PATH = SCRIPT_DIR / "render_hype_1d_ma7_v6_rsi6_memory_cross.py"
RESULT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_short_cooldown_2d_2026-08-10.json"
HTML_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_v6_short_cooldown_2d_2026-08-10_trade_path.html"
)
MANIFEST_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_v6_short_cooldown_2d_2026-08-10_trade_path_manifest.json"
)
SELF_PATH = Path(__file__).resolve()


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


def read_result() -> tuple[dict[str, Any], str]:
    digest = sha256(RESULT_PATH)
    fields = Path(f"{RESULT_PATH}.sha256").read_text().split()
    if fields != [digest, RESULT_PATH.name]:
        raise RuntimeError("invalid result sidecar")
    return json.loads(RESULT_PATH.read_text()), digest


def write_locked(path: Path, payload: bytes) -> dict[str, Any]:
    sidecar = path.with_suffix(".sha256")
    if path.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {path.name}")
    digest = hashlib.sha256(payload).hexdigest()
    with path.open("xb") as handle:
        handle.write(payload)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return {"path": str(path), "sha256": digest, "bytes": len(payload)}


def parameter_groups() -> list[dict[str, Any]]:
    return [
        {
            "title": "唯一变量",
            "rows": [
                ["short cooldown", "5d -> 2d", "short退出后全局自然入场锁定缩短3日。"],
                ["global semantics", "both sides blocked", "现有V6的单一cooldown同时阻止自然long和short。"],
                ["long cooldown", "2d unchanged", "long退出后的冻结参数保持不变。"],
            ],
        },
        {
            "title": "完整继承 exact V6",
            "rows": [
                ["趋势容错", "0.75 ATR7", "多空迟滞退出不变。"],
                ["OAPP", "0.5ATR / 10% / 2d", "固定V5多头利润保护。"],
                ["Short RSI TP", "RSI6 20 x 2", "盈利空头止盈不变。"],
                ["PEHC", "PEHC_294 / 8d", "handoff状态机不变。"],
                ["杠杆", "1x", "单仓、不加仓。"],
            ],
        },
        {
            "title": "成交与证据",
            "rows": [
                ["成交", "close -> next open", "只用已闭合日线。"],
                ["成本", "10bps fee + 4bps slip/fill", "并计历史funding。"],
                ["状态", "FAIL / diagnostic-only", "全432日已暴露，不修改V6。"],
            ],
        },
    ]


def main() -> None:
    frozen, frozen_sha = read_result()
    research = load_module(RESEARCH_PATH, "short_cd2_render_research")
    renderer = load_module(BASE_RENDERER_PATH, "short_cd2_base_renderer")
    helper = load_module(HELPER_PATH, "short_cd2_render_helper")
    engine, risk, context = research.load_runtime()
    context_2d = replace(
        context,
        short_config=replace(context.short_config, cooldown_days=2),
    )
    candidate_result = engine.run_v6(
        context_2d,
        start_index=0,
        terminal_index=432,
        slippage=0.0004,
        retain=True,
    )
    control_result = engine.run_v6(
        context,
        start_index=0,
        terminal_index=432,
        slippage=0.0004,
        retain=True,
    )
    candidate = helper.normalized_run(candidate_result, risk, context_2d)
    control = helper.normalized_run(control_result, risk, context)
    helper.assert_metric_parity(
        candidate, frozen["exact_v6"]["candidate_2d"]["full"]["metrics"]
    )
    helper.assert_metric_parity(
        control, frozen["exact_v6"]["control_5d"]["full"]["metrics"]
    )
    added = frozen["exact_v6"]["comparison"]["trade_diff"]["added"]
    events = [
        {"event": "cd2_added_entry", "ts": row["entry_ts"], "side": row["side"]}
        for row in added
    ]
    document, audit = renderer.build_document(
        title="Exact V6 Short Cooldown 2d — FAIL",
        evidence_role="Exposed full history / diagnostic-only / V6 remains 5d",
        candles=renderer.candles_from_context(context),
        candidate=candidate,
        candidate_label="Exact V6 short cooldown 2d",
        control=control,
        events=events,
        parameter_groups_payload=parameter_groups(),
    )
    document = document.replace(b"Exact V4", b"Exact V6 cooldown 5d")
    audit["sha256"] = hashlib.sha256(document).hexdigest()
    audit["bytes"] = len(document)
    audit["control_identity"] = "exact V6 PEHC_294 short cooldown 5d"
    audit["added_entry_events"] = len(events)
    html_record = write_locked(HTML_PATH, document)
    if html_record["sha256"] != audit["sha256"]:
        raise RuntimeError("HTML write/hash mismatch")
    manifest = {
        "schema": "hype-v6-short-cooldown-2d-trade-path-v1",
        "status": "PASS",
        "research_status": frozen["status"],
        "source_result": {"path": str(RESULT_PATH), "sha256": frozen_sha},
        "implementation": {
            "renderer": {"path": str(SELF_PATH), "sha256": sha256(SELF_PATH)},
            "base_renderer": {
                "path": str(BASE_RENDERER_PATH),
                "sha256": sha256(BASE_RENDERER_PATH),
            },
            "helper": {"path": str(HELPER_PATH), "sha256": sha256(HELPER_PATH)},
        },
        "audit": audit,
        "artifact": html_record,
    }
    encoded = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    write_locked(MANIFEST_PATH, encoded)
    print(json.dumps({"status": "PASS", "html": str(HTML_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
