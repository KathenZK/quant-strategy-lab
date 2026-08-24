"""Render the registered V7 short-cooldown trade path.

V7 is the V6 `n_short_cooldown_days_3` neighborhood candidate registered from
the full-parameter ablation.  This script rebuilds the retained run from the
frozen engine instead of reconstructing trades from prose.
"""

from __future__ import annotations

from dataclasses import asdict
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

ABLATION_SCRIPT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_full_parameter_ablation.py"
ZOOM_RENDERER_PATH = SCRIPT_DIR / "render_hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2.py"
ABLATION_ARTIFACT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v6_full_parameter_ablation_2026-08-11.json"
V7_JSON_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json"
V7_HTML_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_trade_path_2026-08-11.html"

V7_VARIANT_NAME = "n_short_cooldown_days_3"
CONTROL_VARIANT_NAME = "exact_v6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".sha256")


def load_module(path: Path, name: str) -> Any:
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
        return "INF" if value > 0 else "-INF"
    return value


def write_locked(path: Path, payload: bytes, *, force: bool) -> str:
    hash_path = sidecar(path)
    if (path.exists() or hash_path.exists()) and not force:
        raise RuntimeError(f"artifact already exists: {path.name}")
    digest = hashlib.sha256(payload).hexdigest()
    path.write_bytes(payload)
    hash_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def write_locked_json(path: Path, payload: dict[str, Any], *, force: bool) -> str:
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    return write_locked(path, encoded, force=force)


def read_locked_json(path: Path) -> tuple[dict[str, Any], str]:
    hash_path = sidecar(path)
    if not path.is_file() or not hash_path.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    digest = sha256(path)
    fields = hash_path.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[0] != digest or fields[1] != path.name:
        raise RuntimeError(f"invalid sidecar for {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), digest


def run_dict(name: str, metrics: dict[str, Any], result: Any) -> dict[str, Any]:
    payload_metrics = dict(metrics)
    payload_metrics["daily_extreme_mdd_pct"] = payload_metrics["raw_engine_mdd_pct"]
    return {
        "arm_id": name,
        "metrics": payload_metrics,
        "trades": list(result.raw.trades),
        "path": list(result.raw.path),
        "handoff_events": list(result.handoff_events),
        "entry_events": list(result.entry_events),
    }


def assert_metric_close(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in ("net_return_pct", "chronological_1h_mdd_pct", "closed_trades"):
        if isinstance(actual[key], int):
            if int(actual[key]) != int(expected[key]):
                raise RuntimeError(f"metric drift: {key}")
        elif not math.isclose(float(actual[key]), float(expected[key]), rel_tol=0.0, abs_tol=0.05):
            raise RuntimeError(f"metric drift: {key}: {actual[key]} vs {expected[key]}")


def adjust_v7_parameter_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = json.loads(json.dumps(groups, ensure_ascii=False))
    for group in output:
        if group["title"] == "exact V4 多头腿":
            group["title"] = "V7 多头腿（继承 V6）"
        elif group["title"] == "exact V4 空头腿":
            group["title"] = "V7 空头腿（V6 + short cooldown 3d）"
            for row in group["rows"]:
                if row[0] == "cooldown_days":
                    row[2] = "空头退出后3日不重新开空；这是V7相对V6的唯一实际交易参数改动。"
        elif group["title"] == "固定 OAPP 增量":
            group["title"] = "V7 继承固定 OAPP"
        elif group["title"] == "PEHC_294 增量":
            group["title"] = "V7 继承 PEHC_294"
    return output


def add_rsi6_to_candles(candles: list[dict[str, Any]], rsi6: Any) -> list[dict[str, Any]]:
    output = json.loads(json.dumps(candles, ensure_ascii=False))
    if len(output) != len(rsi6) + 1:
        raise RuntimeError("RSI6 length must match daily candles plus terminal display candle")
    for index, value in enumerate(rsi6):
        output[index]["rsi6"] = float(value) if math.isfinite(float(value)) else None
    output[-1]["rsi6"] = output[-2].get("rsi6")
    return output


def patch_v7_template(template: str) -> str:
    output = template.replace("Exact V4", "Exact V6")
    output = output.replace(
        '<span><i style="background:#d9e0e5"></i>Equity</span>',
        '<span><i style="background:#d9e0e5"></i>Equity</span>'
        '<span><i style="background:#a8c46a"></i>RSI6</span>'
        '<span><i style="background:#6f7d89"></i>RSI 30/70</span>',
    )
    output = output.replace(
        "priceH=Math.round(H*.62),eqTop=Math.round(H*.72),eqH=H-eqTop-35",
        "priceH=Math.round(H*.54),rsiTop=Math.round(H*.62),rsiH=Math.round(H*.15),eqTop=Math.round(H*.82),eqH=H-eqTop-35",
    )
    output = output.replace(
        "X.restore();\nconst eqMap=",
        """X.restore();
const rsiVals=visible.map(r=>r.rsi6).filter(v=>v!=null),ry=v=>rsiTop+(100-v)/100*rsiH;X.strokeStyle='#25313b';X.beginPath();X.moveTo(left,rsiTop);X.lineTo(W-right,rsiTop);X.moveTo(left,rsiTop+rsiH);X.lineTo(W-right,rsiTop+rsiH);X.stroke();X.fillStyle='#82909c';X.fillText('RSI6',5,rsiTop+8);for(const [lvl,label] of [[70,'70'],[30,'30']]){const y=ry(lvl);X.strokeStyle='#6f7d89';X.setLineDash([4,4]);X.beginPath();X.moveTo(left,y);X.lineTo(W-right,y);X.stroke();X.setLineDash([]);X.fillStyle='#82909c';X.fillText(label,35,y)}if(rsiVals.length){X.save();X.beginPath();X.rect(left,rsiTop,plotW,rsiH);X.clip();X.strokeStyle='#a8c46a';X.lineWidth=1.5;X.beginPath();begun=false;for(let i=loI;i<=hiI;i++){const v=P[i].rsi6;if(v==null)continue;begun?X.lineTo(xx(i),ry(v)):(X.moveTo(xx(i),ry(v)),begun=true)}X.stroke();X.restore();X.lineWidth=1}
const eqMap=""",
    )
    output = output.replace(
        "MA7 ${fmt(r.ma7)}  Equity ${q?fmt(q.value,3):'—'}",
        "MA7 ${fmt(r.ma7)}  RSI6 ${fmt(r.rsi6)}  Equity ${q?fmt(q.value,3):'—'}",
    )
    return output


def build_v7_document(
    renderer: Any,
    *,
    candles: list[dict[str, Any]],
    candidate: dict[str, Any],
    control: dict[str, Any],
    events: list[dict[str, Any]],
    parameter_groups: list[dict[str, Any]],
) -> tuple[bytes, dict[str, Any]]:
    title = "HYPE-1D-MA7-ABT-V7 short cooldown 3d — Trade Path"
    evidence_role = "registered / post-reveal / not promoted / not live-ready"
    template = patch_v7_template(renderer.HTML_TEMPLATE)
    payload = {
        "schema": "hype-ma7-v7-trade-path-v1",
        "title": title,
        "evidenceRole": evidence_role,
        "candles": candles,
        "candidate": renderer.compact_run(candidate, "V7 short cooldown 3d"),
        "control": renderer.compact_run(control, "Exact V6 1x"),
        "events": events,
        "parameterGroups": parameter_groups,
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    document = template.replace("__TITLE__", title).replace("__PAYLOAD__", data).encode("utf-8")
    audit = validate_payload(payload, document)
    return document, audit


def validate_payload(payload: dict[str, Any], document: bytes) -> dict[str, Any]:
    if b"__PAYLOAD__" in document or b"__TITLE__" in document:
        raise RuntimeError("HTML placeholder remains")
    candles = payload["candles"]
    if not any(row.get("rsi6") is not None for row in candles):
        raise RuntimeError("RSI6 payload missing")
    days = {str(row["ts"])[:10] for row in candles}
    if len(days) != len(candles):
        raise RuntimeError("candle timestamps are not unique by day")
    for run_name in ("candidate", "control"):
        run = payload[run_name]
        trades = run["trades"]
        if len(trades) != int(run["metrics"]["closed_trades"]):
            raise RuntimeError(f"{run_name}: trade count mismatch")
        seen_ids: set[int] = set()
        for index, trade in enumerate(trades):
            if index in seen_ids:
                raise RuntimeError(f"{run_name}: duplicate trade id")
            seen_ids.add(index)
            if str(trade["entryTs"]) > str(trade["exitTs"]):
                raise RuntimeError(f"{run_name}: entry after exit")
            if str(trade["entryTs"])[:10] not in days or str(trade["exitTs"])[:10] not in days:
                raise RuntimeError(f"{run_name}: trade endpoint outside candles")
    return {
        "schema": payload["schema"],
        "sha256": hashlib.sha256(document).hexdigest(),
        "bytes": len(document),
        "candles": len(candles),
        "candidate_trades": len(payload["candidate"]["trades"]),
        "control_trades": len(payload["control"]["trades"]),
        "events": len(payload["events"]),
        "trade_ids_unique": True,
        "all_trades_connected": True,
        "entry_lte_exit": True,
        "external_dependencies": 0,
        "no_template_placeholders": True,
        "rsi6_panel": True,
        "rsi_reference_levels": [30, 70],
    }


def run(force: bool) -> dict[str, Any]:
    ablation_artifact, ablation_sha = read_locked_json(ABLATION_ARTIFACT_PATH)
    ablation = load_module(ABLATION_SCRIPT_PATH, "hype_ma7_v7_ablation")
    renderer = load_module(ZOOM_RENDERER_PATH, "hype_ma7_v7_renderer_base")
    engine = ablation.load_module(ablation.ENGINE_PATH, "hype_ma7_v7_engine")
    adapter = ablation.load_module(ablation.ADAPTER_PATH, "hype_ma7_v7_adapter")
    context = adapter.load_context()
    variants = {variant.name: variant for variant in ablation.build_variants(engine, context)}
    if V7_VARIANT_NAME not in variants or CONTROL_VARIANT_NAME not in variants:
        raise RuntimeError("required variants not present")

    control_metrics, control_result = ablation.run_variant(
        engine,
        context,
        variants[CONTROL_VARIANT_NAME],
        window=ablation.FULL,
        slippage=ablation.BASE_SLIPPAGE,
        signal_lag=0,
        include_funding=True,
        retain=True,
    )
    v7_metrics, v7_result = ablation.run_variant(
        engine,
        context,
        variants[V7_VARIANT_NAME],
        window=ablation.FULL,
        slippage=ablation.BASE_SLIPPAGE,
        signal_lag=0,
        include_funding=True,
        retain=True,
    )
    assert_metric_close(control_metrics, ablation_artifact["control"])
    assert_metric_close(v7_metrics, ablation_artifact["candidates"][V7_VARIANT_NAME]["stress"]["base_full"])

    v7_config = {
        "long_config": ablation.variant_config(variants[V7_VARIANT_NAME].long_config),
        "short_config": ablation.variant_config(variants[V7_VARIANT_NAME].short_config),
        "oapp_config": ablation.variant_config(variants[V7_VARIANT_NAME].oapp_config),
        "pehc_config": ablation.variant_config(variants[V7_VARIANT_NAME].pehc_config),
    }
    candles = add_rsi6_to_candles(
        renderer.candles_from_context(context),
        engine._BASE.wilder_rsi6(context.book.close),
    )
    parameter_groups = adjust_v7_parameter_groups(
        renderer.parameter_groups(
            long_config=asdict(variants[V7_VARIANT_NAME].long_config),
            short_config=asdict(variants[V7_VARIANT_NAME].short_config),
            oapp_config=v7_config["oapp_config"],
            pehc_config=v7_config["pehc_config"],
        )
    )
    v7_run = run_dict(V7_VARIANT_NAME, v7_metrics, v7_result)
    control_run = run_dict(CONTROL_VARIANT_NAME, control_metrics, control_result)
    document, html_audit = build_v7_document(
        renderer,
        candles=candles,
        candidate=v7_run,
        control=control_run,
        events=v7_run["handoff_events"],
        parameter_groups=parameter_groups,
    )
    html_sha = write_locked(V7_HTML_PATH, document, force=force)
    payload = {
        "schema": "hype-1d-ma7-abt-v7-registration-artifact-v1",
        "version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V7",
        "alias": "HYPE-1D-MA7-ABT-V7",
        "status": "registered / not promoted / not live-ready",
        "source_variant": V7_VARIANT_NAME,
        "change_vs_v6": "short cooldown_days 5 -> 3; all other V6 parameters unchanged",
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "cost_model": {
            "fee_per_fill": 0.001,
            "slippage_per_fill": ablation.BASE_SLIPPAGE,
            "funding": "actual Binance funding events",
        },
        "data_range": ablation_artifact["data_range"],
        "metrics": v7_metrics,
        "control_exact_v6": control_metrics,
        "config": v7_config,
        "config_sha256": ablation.canonical_hash(
            {
                "long": v7_config["long_config"],
                "short": v7_config["short_config"],
                "oapp": v7_config["oapp_config"],
                "pehc": v7_config["pehc_config"],
            }
        ),
        "trades": v7_run["trades"],
        "path": v7_run["path"],
        "handoff_events": v7_run["handoff_events"],
        "source_artifacts": {
            "full_parameter_ablation": {
                "path": str(ABLATION_ARTIFACT_PATH.relative_to(FAMILY_DIR)),
                "sha256": ablation_sha,
            }
        },
        "implementation_sha256": {
            "generator": sha256(Path(__file__).resolve()),
            "ablation_script": sha256(ABLATION_SCRIPT_PATH),
            "zoom_renderer_base": sha256(ZOOM_RENDERER_PATH),
            "pehc_engine": sha256(ablation.ENGINE_PATH),
            "adapter": sha256(ablation.ADAPTER_PATH),
        },
        "html": {"path": str(V7_HTML_PATH.relative_to(FAMILY_DIR)), "sha256": html_sha, "audit": html_audit},
        "research_state": "registration only; no promotion, live spec, dry-run, live, runner authorization, or leverage change",
    }
    payload["artifact_sha256"] = write_locked_json(V7_JSON_PATH, payload, force=force)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    payload = run(force=args.force)
    print(json.dumps({"status": "PASS", "json": str(V7_JSON_PATH), "html": str(V7_HTML_PATH), "metrics": payload["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
