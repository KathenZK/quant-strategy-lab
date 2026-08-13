"""Render the frozen primary RSI6-memory cross arm against exact V6."""

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

RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_v6_rsi6_memory_cross.py"
BASE_RENDERER_PATH = (
    SCRIPT_DIR / "render_hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2.py"
)
RESULT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_v6_rsi6_memory_cross_2026-08-10_v2.json"
)
HTML_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_v6_rsi6_memory_cross_2026-08-10_"
    "primary_trade_path.html"
)
MANIFEST_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_v6_rsi6_memory_cross_2026-08-10_"
    "trade_path_manifest.json"
)
SELF_PATH = Path(__file__).resolve()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar(path: Path) -> Path:
    return path.with_suffix(".sha256")


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
    result_sidecar = Path(f"{path}.sha256")
    fields = result_sidecar.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields != [digest, path.name]:
        raise RuntimeError(f"invalid locked artifact: {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), digest


def write_locked(path: Path, payload: bytes) -> dict[str, Any]:
    hash_path = sidecar(path)
    if path.exists() or hash_path.exists():
        raise RuntimeError(f"locked artifact exists: {path.name}")
    digest = hashlib.sha256(payload).hexdigest()
    with path.open("xb") as handle:
        handle.write(payload)
    with hash_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return {"path": str(path), "sha256": digest, "bytes": len(payload)}


def normalized_run(result: Any, risk: ModuleType, context: Any) -> dict[str, Any]:
    replay = risk.replay_chronological_1h(context, result.raw, slippage=0.0004)
    if not all(replay.parity.values()):
        raise RuntimeError("chronological replay parity failed")
    metrics = dict(result.raw.metrics)
    metrics["chronological_1h_mdd_pct"] = replay.chronological_1h_mdd_pct
    metrics["daily_extreme_mdd_pct"] = metrics["max_drawdown_pct"]
    return {
        "arm_id": result.config.arm_id,
        "metrics": metrics,
        "trades": result.raw.trades,
        "path": result.raw.path,
    }


def assert_metric_parity(run: dict[str, Any], frozen: dict[str, Any]) -> None:
    pairs = (
        ("net_return_pct", "net_return_pct"),
        ("chronological_1h_mdd_pct", "chronological_1h_mdd_pct"),
        ("daily_extreme_mdd_pct", "daily_extreme_mdd_pct"),
        ("closed_trades", "closed_trades"),
    )
    for run_key, frozen_key in pairs:
        if not math.isclose(
            float(run["metrics"][run_key]),
            float(frozen[frozen_key]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise RuntimeError(f"frozen metric drift: {run_key}")


def parameters() -> list[dict[str, Any]]:
    return [
        {
            "title": "RSI6 记忆 cross 新增入口",
            "rows": [
                ["窗口", "PRIOR5", "只看 cross 当日前5个完整UTC日，不含cross日。"],
                ["计数", "3 / 5", "达到至少3日才获得替代入场资格。"],
                ["Long", "RSI6 < 30 + cross above MA7", "次日open做多。"],
                ["Short", "RSI6 > 70 + cross below MA7", "次日open做空。"],
                ["组合", "OR exact V6 native entry", "不删除V6原生入场。"],
            ],
        },
        {
            "title": "完整继承 exact V6",
            "rows": [
                ["趋势容错", "0.75 ATR7", "多空持仓继续使用V6的MA7迟滞退出。"],
                ["Long OAPP", "0.5ATR / 10% / 2d", "固定V5多头MFE利润保护。"],
                ["Short RSI TP", "RSI6 20 x 2", "只在盈利空头上触发。"],
                ["PEHC", "PEHC_294 / 8d", "保留V6 forced-short handoff。"],
                ["Cooldown", "long 2d / short 5d", "本轮不改V6 cooldown。"],
                ["杠杆", "1x", "固定目标仓位，不加仓。"],
            ],
        },
        {
            "title": "成交与证据角色",
            "rows": [
                ["日线时序", "close -> next open", "信号仅使用已闭合日线。"],
                ["手续费", "0.10% / fill", "每个实际成交腿收费。"],
                ["滑点", "4 bps / fill", "base不利滑点。"],
                ["Funding", "历史实际值", "只对真实持仓结算。"],
                ["研究状态", "FAIL / diagnostic-only", "全432日均已暴露，不登记V7。"],
            ],
        },
    ]


def main() -> None:
    frozen, frozen_sha = read_locked(RESULT_PATH)
    research = load_module(RESEARCH_PATH, "rsi_memory_render_research")
    renderer = load_module(BASE_RENDERER_PATH, "rsi_memory_base_renderer")
    engine, risk, context = research.load_runtime()
    config = next(
        item
        for item in research.configs(engine)
        if item.arm_id == frozen["primary_arm"]
    )
    candidate_result = engine.run_variant(
        context,
        config,
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
    candidate = normalized_run(candidate_result, risk, context)
    control = normalized_run(control_result, risk, context)
    primary_frozen = next(
        row for row in frozen["arms"] if row["arm_id"] == frozen["primary_arm"]
    )
    assert_metric_parity(candidate, primary_frozen["full"]["metrics"])
    assert_metric_parity(control, frozen["control"]["full"]["metrics"])
    events = [
        {
            **row,
            "ts": context.book.ts[int(row["signal_index"])].isoformat(),
        }
        for row in candidate_result.memory_events
        if row["event"] == "rsi_memory_cross_pass"
    ]
    document, audit = renderer.build_document(
        title="V6 + RSI6 3-of-5 记忆 Cross — Primary FAIL",
        evidence_role="Exposed full history / diagnostic-only / not V7",
        candles=renderer.candles_from_context(context),
        candidate=candidate,
        candidate_label="A1 PRIOR5 BOTH 1x",
        control=control,
        events=events,
        parameter_groups_payload=parameters(),
    )
    document = document.replace(b"Exact V4", b"Exact V6")
    audit["sha256"] = hashlib.sha256(document).hexdigest()
    audit["bytes"] = len(document)
    audit["control_identity"] = "exact V6 PEHC_294 1x"
    audit["memory_pass_events"] = len(events)
    html_record = write_locked(HTML_PATH, document)
    if html_record["sha256"] != audit["sha256"]:
        raise RuntimeError("HTML write/hash mismatch")
    manifest = {
        "schema": "hype-v6-rsi6-memory-cross-trade-path-v1",
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
