"""Render the best frozen V6 structural diagnostic against exact V6."""

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
RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_v6_structural_sizing.py"
BASE_RENDERER_PATH = (
    SCRIPT_DIR / "render_hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2.py"
)
RESULT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_structural_sizing_2026-08-10_v2.json"
HTML_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_v6_structural_sizing_2026-08-10_v2_best_trade_path.html"
)
MANIFEST_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_v6_structural_sizing_2026-08-10_v2_trade_path_manifest.json"
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


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    digest = sha256(path)
    fields = Path(f"{path}.sha256").read_text(encoding="utf-8").split()
    if fields != [digest, path.name]:
        raise RuntimeError(f"invalid locked artifact: {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), digest


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


def normalized_candidate(result: Any, engine: ModuleType, context: Any) -> dict[str, Any]:
    replay = engine.replay_structural_chronological_1h(context, result)
    metrics = dict(result.raw.metrics)
    metrics["chronological_1h_mdd_pct"] = replay.chronological_1h_mdd_pct
    metrics["daily_extreme_mdd_pct"] = metrics["max_drawdown_pct"]
    return {
        "arm_id": result.config.arm_id,
        "metrics": metrics,
        "trades": result.raw.trades,
        "path": result.raw.path,
    }


def normalized_control(result: Any, risk: ModuleType, context: Any) -> dict[str, Any]:
    replay = risk.replay_chronological_1h(context, result.raw)
    metrics = dict(result.raw.metrics)
    metrics["chronological_1h_mdd_pct"] = replay.chronological_1h_mdd_pct
    metrics["daily_extreme_mdd_pct"] = metrics["max_drawdown_pct"]
    return {
        "arm_id": "CTRL_EXACT_V6",
        "metrics": metrics,
        "trades": result.raw.trades,
        "path": result.raw.path,
    }


def assert_metric_parity(run: dict[str, Any], frozen: dict[str, Any]) -> None:
    for key in (
        "net_return_pct",
        "chronological_1h_mdd_pct",
        "daily_extreme_mdd_pct",
        "closed_trades",
    ):
        if not math.isclose(
            float(run["metrics"][key]),
            float(frozen[key]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise RuntimeError(f"frozen metric drift: {key}")


def parameters() -> list[dict[str, Any]]:
    return [
        {
            "title": "Best diagnostic arm — not promoted",
            "rows": [
                ["memory long", "prior 5d: 3 x RSI6 < 30", "随后 close 从 <=MA7 穿到 >MA7。"],
                ["initial size", "0.50x", "只有 memory-only long 使用试探仓。"],
                ["confirmation", "close>MA7 and MA7 slope/ATR7>0.02", "最多等待2个新完成日。"],
                ["promotion", "next open -> 1.00x", "原V6退出判断优先。"],
                ["expiry", "2d then flat", "本样本没有触发到期退出。"],
            ],
        },
        {
            "title": "Exact V6 inherited",
            "rows": [
                ["MA7 tolerance", "0.75 ATR7", "持仓迟滞退出保持不变。"],
                ["OAPP", "0.5ATR / 10% / 2d", "多头利润保护保持不变。"],
                ["short RSI TP", "RSI6 20 x 2", "盈利空头止盈保持不变。"],
                ["PEHC", "PEHC_294 / 8d", "handoff状态机保持不变。"],
                ["cooldown", "long 2d / short 5d", "该实验臂没有改冷却。"],
            ],
        },
        {
            "title": "Evidence role",
            "rows": [
                ["cost", "10bps fee + 4bps slip/fill", "并计历史funding。"],
                ["risk", "ordered 1h MDD", "加仓、funding和退出全部逐时重放对账。"],
                ["status", "FAIL / diagnostic-only", "收益提高但MDD未改善，且只激活1个episode。"],
            ],
        },
    ]


def main() -> None:
    frozen, frozen_sha = read_locked(RESULT_PATH)
    research = load_module(RESEARCH_PATH, "v6_structural_render_research")
    renderer = load_module(BASE_RENDERER_PATH, "v6_structural_base_renderer")
    engine, risk, context = research.load_runtime()
    arm_id = str(frozen["best_diagnostic_arm"])
    config = next(row for row in engine.frozen_configs() if row.arm_id == arm_id)
    candidate_result = engine.run_variant(
        context,
        config,
        start_index=0,
        terminal_index=context.book.count,
        slippage=0.0004,
        retain=True,
    )
    control_result = engine.run_exact_v6(
        context,
        start_index=0,
        terminal_index=context.book.count,
        slippage=0.0004,
        retain=True,
    )
    candidate = normalized_candidate(candidate_result, engine, context)
    control = normalized_control(control_result, risk, context)
    frozen_arm = next(row for row in frozen["arms"] if row["arm_id"] == arm_id)
    assert_metric_parity(candidate, frozen_arm["full"]["metrics"])
    assert_metric_parity(control, frozen["control"]["full"]["metrics"])
    events = []
    for row in candidate_result.memory_events:
        if row.get("event") == "rsi_memory_cross_pass" and row.get("side") == "long":
            events.append(
                {
                    "event": "memory_long_pass",
                    "ts": context.book.ts[int(row["signal_index"])].isoformat(),
                }
            )
    events.extend(
        {"event": "long_probe_promoted", "ts": row["ts"]}
        for row in candidate_result.structural_events
        if row.get("event") == "long_probe_promoted"
    )
    document, audit = renderer.build_document(
        title="V6 Structural Sizing — best arm still FAIL",
        evidence_role="Exposed full history / diagnostic-only / exact V6 unchanged",
        candles=renderer.candles_from_context(context),
        candidate=candidate,
        candidate_label="A_LONG_P05_C2 (0.5x -> confirmed 1x)",
        control=control,
        events=events,
        parameter_groups_payload=parameters(),
    )
    document = document.replace(b"Exact V4", b"Exact V6")
    audit["sha256"] = hashlib.sha256(document).hexdigest()
    audit["bytes"] = len(document)
    audit["control_identity"] = "exact V6 PEHC_294 1x"
    audit["structural_event_lines"] = len(events)
    html_record = write_locked(HTML_PATH, document)
    if html_record["sha256"] != audit["sha256"]:
        raise RuntimeError("HTML write/hash mismatch")
    manifest = {
        "schema": "hype-v6-structural-sizing-trade-path-v2",
        "status": "PASS",
        "research_status": frozen["status"],
        "source_result": {"path": str(RESULT_PATH), "sha256": frozen_sha},
        "implementation": {
            "renderer": {"path": str(SELF_PATH), "sha256": sha256(SELF_PATH)},
            "base_renderer": {
                "path": str(BASE_RENDERER_PATH),
                "sha256": sha256(BASE_RENDERER_PATH),
            },
            "engine": {"path": str(research.ENGINE_PATH), "sha256": sha256(research.ENGINE_PATH)},
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
