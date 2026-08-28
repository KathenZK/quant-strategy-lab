"""Render frozen P4 versus exact V7.1 validation paths in one HTML."""

from __future__ import annotations

import argparse
import copy
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P4_SCRIPT = (
    FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py"
)
SLICE_SCRIPT = FAMILY_DIR / "scripts/audit_hype_1d_ma7_mlt_p4_recent_slices.py"
STEM = "hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27"
SUMMARY_PATH = ARTIFACT_DIR / f"{STEM}_validation_summary.json"
DEVELOPMENT_SUMMARY_PATH = ARTIFACT_DIR / f"{STEM}_development_summary.json"
TRAINING_DECISIONS_PATH = ARTIFACT_DIR / f"{STEM}_training_residual_decisions.csv"
TEACHER_TRADES_PATH = ARTIFACT_DIR / f"{STEM}_validation_teacher_trades.csv"
OVERLAY_TRADES_PATH = ARTIFACT_DIR / f"{STEM}_validation_overlay_trades.csv"
DECISIONS_PATH = ARTIFACT_DIR / f"{STEM}_validation_residual_decisions.csv"
DEVELOPMENT_MANIFEST_PATH = ARTIFACT_DIR / f"{STEM}_development_manifest.json"
OUTPUT_PATH = ARTIFACT_DIR / f"{STEM}_v7_1_comparison_trade_paths.html"
MANIFEST_PATH = ARTIFACT_DIR / f"{STEM}_v7_1_comparison_trade_paths_manifest.json"

STRATEGIES = {
    "V7_1": {"label": "exact V7.1", "code": "V7", "color": "#54c7ec", "dash": []},
    "P4": {"label": "P4 EXTEND_ONLY", "code": "P4", "color": "#ff9f43", "dash": [9, 5]},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sidecar(path: Path) -> None:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists():
        raise RuntimeError(f"missing sidecar: {sidecar}")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise RuntimeError(f"source artifact hash mismatch: {path}")


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1_000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def load_trades(path: Path) -> list[dict[str, Any]]:
    return pd.read_csv(path).to_dict("records")


def overlay_from_decisions(
    teacher_trades: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rebuild the frozen P4 training overlay without fitting any model."""
    if len(teacher_trades) != len(decisions):
        raise RuntimeError("frozen training decisions are not one-to-one")
    overlay = copy.deepcopy(teacher_trades)
    for order, (trade, decision) in enumerate(zip(overlay, decisions, strict=True)):
        if int(decision["trade_order"]) != order:
            raise RuntimeError("training decision order mismatch")
        if not bool(decision["accepted"]):
            raise RuntimeError("EXTEND_ONLY unexpectedly filtered a training trade")
        if not bool(decision["extended"]):
            continue
        reason = str(trade["exit_reason"])
        trade["exit_ts"] = str(decision["overlay_exit_ts"])
        trade["exit_price"] = float(decision["overlay_exit_price"])
        trade["exit_reason"] = f"{reason}_ml_extend_3d"
    return overlay


def daily_equity(
    slice_audit: Any,
    p4: Any,
    v6: Any,
    context: Any,
    trades: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    observations, _, terminal_equity = slice_audit.equity_observations(
        p4, v6, context, trades
    )
    last_at_timestamp: dict[pd.Timestamp, float] = {}
    for ts, value in observations:
        last_at_timestamp[pd.Timestamp(ts)] = float(value)
    timestamps = [pd.Timestamp(ts) for ts in context.book.ts[start_index:]]
    timestamps.append(pd.Timestamp(context.book.terminal_ts))
    rows: list[dict[str, Any]] = []
    for ts in timestamps:
        if ts not in last_at_timestamp:
            raise RuntimeError(f"missing daily equity timestamp: {ts}")
        rows.append({"t": timestamp_ms(ts), "v": last_at_timestamp[ts]})
    if not math.isclose(rows[-1]["v"], terminal_equity, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("daily equity terminal parity failed")
    return rows


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    source_paths = (
        SUMMARY_PATH,
        DEVELOPMENT_SUMMARY_PATH,
        TRAINING_DECISIONS_PATH,
        TEACHER_TRADES_PATH,
        OVERLAY_TRADES_PATH,
        DECISIONS_PATH,
        DEVELOPMENT_MANIFEST_PATH,
    )
    for path in source_paths:
        verify_sidecar(path)

    p4 = load_module(P4_SCRIPT, "hype_p4_v7_comparison_main")
    slice_audit = load_module(SLICE_SCRIPT, "hype_p4_v7_comparison_slices")
    train_diag, train_v6, train_engine, _, train_context = p4.load_dependencies(
        train_only=True
    )
    training_teacher_run = p4.run_teacher(
        train_diag, train_v6, train_engine, train_context, 0, p4.TRAIN_DAYS
    )
    training_teacher = list(training_teacher_run.result.raw.trades)
    training_decisions = pd.read_csv(TRAINING_DECISIONS_PATH).to_dict("records")
    training_overlay = overlay_from_decisions(training_teacher, training_decisions)

    _, v6, engine, _, context = p4.load_dependencies(train_only=False)
    validation_summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    development_summary = json.loads(
        DEVELOPMENT_SUMMARY_PATH.read_text(encoding="utf-8")
    )
    validation_teacher = load_trades(TEACHER_TRADES_PATH)
    validation_overlay = load_trades(OVERLAY_TRADES_PATH)
    validation_decisions = pd.read_csv(DECISIONS_PATH).to_dict("records")
    if len(validation_teacher) != len(validation_overlay) or len(
        validation_decisions
    ) != len(validation_teacher):
        raise RuntimeError("frozen validation rows are not one-to-one")

    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    candles: list[dict[str, Any]] = []
    for index in range(context.book.count):
        ma7 = float(context.features.ma7[index])
        atr = float(context.features.atr7[index])
        prior_ma = float(context.features.ma7[index - 1]) if index else math.nan
        candles.append(
            {
                "t": timestamp_ms(context.book.ts[index]),
                "o": float(context.book.open[index]),
                "h": float(context.book.high[index]),
                "l": float(context.book.low[index]),
                "c": float(context.book.close[index]),
                "ma7": finite_or_none(ma7),
                "slopeAtr": finite_or_none((ma7 - prior_ma) / atr),
                "rsi6": finite_or_none(rsi6[index]),
            }
        )

    training_equity = {
        "V7_1": daily_equity(
            slice_audit, p4, train_v6, train_context, training_teacher, 0
        ),
        "P4": daily_equity(
            slice_audit, p4, train_v6, train_context, training_overlay, 0
        ),
    }
    validation_equity = {
        "V7_1": daily_equity(
            slice_audit, p4, v6, context, validation_teacher, p4.TRAIN_DAYS
        ),
        "P4": daily_equity(
            slice_audit, p4, v6, context, validation_overlay, p4.TRAIN_DAYS
        ),
    }
    equity: dict[str, list[dict[str, Any]]] = {}
    for strategy in STRATEGIES:
        training_terminal = float(training_equity[strategy][-1]["v"])
        equity[strategy] = training_equity[strategy] + [
            {"t": row["t"], "v": float(row["v"]) * training_terminal}
            for row in validation_equity[strategy][1:]
        ]

    training_replay = {
        "V7_1": p4.replay_metrics(train_v6, train_context, training_teacher),
        "P4": p4.replay_metrics(train_v6, train_context, training_overlay),
    }
    validation_replay = {
        "V7_1": p4.replay_metrics(v6, context, validation_teacher),
        "P4": p4.replay_metrics(v6, context, validation_overlay),
    }
    expected_training = {
        "V7_1": development_summary["teacher_v7_1"],
        "P4": development_summary["residual"]["full_training_overlay"],
    }
    expected_validation = {
        "V7_1": validation_summary["teacher_v7_1"],
        "P4": validation_summary["ml_residual_overlay"],
    }
    for strategy in STRATEGIES:
        for replay, expected in (
            (training_replay[strategy], expected_training[strategy]),
            (validation_replay[strategy], expected_validation[strategy]),
        ):
            for key in ("net_return_pct", "chronological_1h_mdd_pct"):
                if not math.isclose(
                    float(replay[key]),
                    float(expected[key]),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    raise RuntimeError(f"{strategy} {key} replay parity failed")

    trades: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    segments = (
        (
            "training",
            "训练",
            "TR",
            training_teacher,
            training_overlay,
            training_decisions,
            training_replay,
        ),
        (
            "validation",
            "验证",
            "VA",
            validation_teacher,
            validation_overlay,
            validation_decisions,
            validation_replay,
        ),
    )
    global_order = 0
    for (
        segment,
        segment_label,
        segment_code,
        teachers,
        overlays,
        decisions,
        replays,
    ) in segments:
        decision_by_order = {int(row["trade_order"]): row for row in decisions}
        for local_order, (teacher, overlay) in enumerate(
            zip(teachers, overlays, strict=True)
        ):
            global_order += 1
            decision = decision_by_order[local_order]
            pair_id = f"{segment_code}-{local_order + 1:02d}"
            changed = pd.Timestamp(teacher["exit_ts"]) != pd.Timestamp(
                overlay["exit_ts"]
            ) or not math.isclose(
                float(teacher["exit_price"]),
                float(overlay["exit_price"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            pair = {
                "id": pair_id,
                "order": global_order,
                "segment": segment,
                "segmentLabel": segment_label,
                "side": str(teacher["side"]),
                "entryT": timestamp_ms(teacher["entry_ts"]),
                "entry": float(teacher["entry_price"]),
                "teacherExitT": timestamp_ms(teacher["exit_ts"]),
                "teacherExit": float(teacher["exit_price"]),
                "overlayExitT": timestamp_ms(overlay["exit_ts"]),
                "overlayExit": float(overlay["exit_price"]),
                "teacherReason": str(teacher["exit_reason"]),
                "overlayReason": str(overlay["exit_reason"]),
                "teacherReturnPct": float(
                    replays["V7_1"]["per_trade_returns"][local_order]
                )
                * 100.0,
                "overlayReturnPct": float(
                    replays["P4"]["per_trade_returns"][local_order]
                )
                * 100.0,
                "exitProbability": finite_or_none(decision["exit_probability"]),
                "extended": bool(decision["extended"]),
                "changed": changed,
            }
            pair["returnDeltaPct"] = pair["overlayReturnPct"] - pair["teacherReturnPct"]
            pair["extraDays"] = int(
                (
                    pd.Timestamp(overlay["exit_ts"]) - pd.Timestamp(teacher["exit_ts"])
                ).total_seconds()
                / 86_400
            )
            pairs.append(pair)
            for strategy, return_key, exit_t_key, exit_key, reason_key in (
                (
                    "V7_1",
                    "teacherReturnPct",
                    "teacherExitT",
                    "teacherExit",
                    "teacherReason",
                ),
                (
                    "P4",
                    "overlayReturnPct",
                    "overlayExitT",
                    "overlayExit",
                    "overlayReason",
                ),
            ):
                trades.append(
                    {
                        "id": f"{STRATEGIES[strategy]['code']}-{pair_id}",
                        "pairId": pair_id,
                        "strategy": strategy,
                        "strategyLabel": STRATEGIES[strategy]["label"],
                        "segment": segment,
                        "side": pair["side"],
                        "entryT": pair["entryT"],
                        "entry": pair["entry"],
                        "exitT": pair[exit_t_key],
                        "exit": pair[exit_key],
                        "netReturnPct": pair[return_key],
                        "exitReason": pair[reason_key],
                        "changed": changed,
                    }
                )

    metrics = {}
    for strategy in STRATEGIES:
        metrics[strategy] = {
            "label": STRATEGIES[strategy]["label"],
            "color": STRATEGIES[strategy]["color"],
            "trainReturnPct": float(expected_training[strategy]["net_return_pct"]),
            "trainMddPct": float(
                expected_training[strategy]["chronological_1h_mdd_pct"]
            ),
            "validationReturnPct": float(
                expected_validation[strategy]["net_return_pct"]
            ),
            "validationMddPct": float(
                expected_validation[strategy]["chronological_1h_mdd_pct"]
            ),
            "trades": sum(row["strategy"] == strategy for row in trades),
        }

    training_changed = sum(
        pair["changed"] and pair["segment"] == "training" for pair in pairs
    )
    validation_changed = sum(
        pair["changed"] and pair["segment"] == "validation" for pair in pairs
    )
    payload = {
        "title": "HYPE 1D MA7-MLT P4 vs exact V7.1",
        "subtitle": "完整446日 · 训练365日 + 验证81日 · 同一入场/方向/1x · P4 仅修改退出",
        "status": "V7_1_NOT_BEATEN · reused holdout · diagnostic-only · not live-ready",
        "generatedAt": datetime.now(UTC).isoformat(),
        "window": {
            "start": pd.Timestamp(context.book.ts[0]).isoformat(),
            "boundary": pd.Timestamp(context.book.ts[p4.TRAIN_DAYS]).isoformat(),
            "boundaryT": timestamp_ms(context.book.ts[p4.TRAIN_DAYS]),
            "lastDay": pd.Timestamp(context.book.ts[-1]).isoformat(),
            "terminal": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "days": context.book.count,
            "trainDays": p4.TRAIN_DAYS,
            "validationDays": context.book.count - p4.TRAIN_DAYS,
        },
        "strategies": STRATEGIES,
        "metrics": metrics,
        "difference": {
            "changedPairs": training_changed + validation_changed,
            "trainingChangedPairs": training_changed,
            "validationChangedPairs": validation_changed,
            "summary": "20笔入场全部一致；训练期6笔、验证期1笔由 P4 延长退出。",
        },
        "equityNote": "权益线为便于连续观察而拼接：训练终值 × 验证相对权益；验证期原始账户实际独立从1开始。",
        "candles": candles,
        "equity": equity,
        "trades": trades,
        "pairs": pairs,
    }
    manifest = {
        "schema": "hype-1d-ma7-mlt-p4-v7-1-comparison-trade-path-v2",
        "generated_at": payload["generatedAt"],
        "sources": {path.name: sha256(path) for path in source_paths},
        "renderer": Path(__file__).name,
        "window": payload["window"],
        "candles": len(candles),
        "ma7_points": sum(row["ma7"] is not None for row in candles),
        "equity_points": {key: len(value) for key, value in equity.items()},
        "trades_by_strategy": {
            key: sum(row["strategy"] == key for row in trades) for key in STRATEGIES
        },
        "paired_trades": len(pairs),
        "changed_pairs": training_changed + validation_changed,
        "training_changed_pairs": training_changed,
        "validation_changed_pairs": validation_changed,
        "line_render_count": len(trades),
        "entry_parity": all(
            trades[index * 2]["entryT"] == trades[index * 2 + 1]["entryT"]
            and trades[index * 2]["side"] == trades[index * 2 + 1]["side"]
            and trades[index * 2]["entry"] == trades[index * 2 + 1]["entry"]
            for index in range(len(pairs))
        ),
        "external_dependencies": 0,
    }
    return payload, manifest


HTML_TEMPLATE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P4 vs V7.1 交易路径</title><style>
:root{color-scheme:dark;--bg:#080b0f;--panel:#0e141a;--panel2:#111a22;--line:#26323d;--grid:#1b2630;--text:#edf2f5;--muted:#91a0ad;--up:#25d3a0;--down:#f06478;--ma:#f4ca58;--v7:#54c7ec;--p4:#ff9f43;--warn:#ffd166}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}.shell{max-width:1900px;margin:auto;padding:22px}header{display:grid;grid-template-columns:minmax(420px,1fr) auto;gap:18px;align-items:end;margin-bottom:13px}h1{margin:0 0 6px;font:650 24px/1.2 system-ui,sans-serif}.subtitle,.status,.hint{color:var(--muted);font-size:12px}.status{margin-top:4px}.metrics{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}.metric{min-width:300px;padding:9px 11px;border:1px solid var(--line);background:var(--panel)}.metric b{display:block;margin-top:2px;font-size:13px}.difference{margin:0 0 12px;padding:10px 12px;border:1px solid #5e5128;background:#19170e;color:#f6dfa0}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding:9px 11px;border:1px solid var(--line);border-bottom:0;background:var(--panel2)}button{color:var(--text);border:1px solid #344653;background:#15202a;padding:6px 10px;cursor:pointer;font:inherit}label{color:var(--muted);user-select:none}input{vertical-align:-2px}.v7{color:var(--v7)}.p4{color:var(--p4)}.ma{color:var(--ma)}.chart{border:1px solid var(--line);background:var(--panel);overflow:hidden}canvas{width:100%;display:block}#priceChart{height:650px;cursor:crosshair}#equityChart{height:245px;border-top:1px solid var(--line)}.hint{padding:8px 11px;border:1px solid var(--line);border-top:0}.table-wrap{margin-top:18px;max-height:650px;overflow:auto;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;min-width:1380px}th,td{padding:9px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}th{color:var(--muted);background:var(--panel2);position:sticky;top:0;z-index:1}th:nth-child(-n+4),td:nth-child(-n+4),th:nth-child(13),td:nth-child(13),th:nth-child(14),td:nth-child(14){text-align:left}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#17232d}tbody tr.changed{background:#211c0e}.positive{color:var(--up)}.negative{color:var(--down)}.badge{padding:2px 6px;border:1px solid #665926;color:var(--warn)}#tooltip{position:fixed;z-index:10;display:none;pointer-events:none;max-width:530px;padding:10px 12px;border:1px solid #465966;background:rgba(7,11,15,.97);box-shadow:0 8px 28px rgba(0,0,0,.45);white-space:pre-line;font-size:12px}@media(max-width:950px){.shell{padding:10px}header{grid-template-columns:1fr}.metrics{justify-content:flex-start}#priceChart{height:500px}}
</style></head><body><div class="shell"><header><div><h1 id="title"></h1><div id="subtitle" class="subtitle"></div><div id="status" class="status"></div></div><div id="metrics" class="metrics"></div></header><div id="difference" class="difference"></div>
<div class="toolbar"><button id="reset">完整范围</button><button id="focusTrain">训练段</button><button id="focusValidation">验证段</button><button id="focusDiff">下一处差异</button><button id="zoomIn">放大</button><button id="zoomOut">缩小</button><label><input id="showMa" type="checkbox" checked><span class="ma">SMA7</span></label><label><input id="showLabels" type="checkbox" checked>编号</label><label><input class="strategy-toggle" data-strategy="V7_1" type="checkbox" checked><span class="v7">V7.1 实线</span></label><label><input class="strategy-toggle" data-strategy="P4" type="checkbox" checked><span class="p4">P4 虚线</span></label><span>▲/▼=入场　●=退出　黄色区域=延长持有</span></div>
<div class="chart"><canvas id="priceChart"></canvas><canvas id="equityChart"></canvas></div><div class="hint">20笔交易均已画出：训练17笔、验证3笔；7处退出变化用黄色区间标记。青色实线是 exact V7.1，橙色虚线是 P4。竖虚线为训练/验证边界。权益线仅作视觉拼接，验证账户实际独立从1开始。滚轮缩放 · 拖动平移 · 双击复位 · 点击表格聚焦。</div>
<div class="table-wrap"><table><thead><tr><th>阶段</th><th>交易</th><th>方向</th><th>是否变化</th><th>共同入场</th><th>入场价</th><th>V7.1退出</th><th>P4退出</th><th>V7.1收益</th><th>P4收益</th><th>收益差</th><th>延长天数</th><th>模型退出延长概率</th><th>退出原因</th></tr></thead><tbody id="tradeRows"></tbody></table></div></div><div id="tooltip"></div><script>
const DATA=__PAYLOAD__,DAY=86400000,C={bg:'#0e141a',bg2:'#0a1015',grid:'#1b2630',muted:'#91a0ad',up:'#25d3a0',down:'#f06478',ma:'#f4ca58',v7:'#54c7ec',p4:'#ff9f43',warn:'#ffd166'};
const $=id=>document.getElementById(id),candles=DATA.candles,trades=DATA.trades,pairs=DATA.pairs,equity=DATA.equity,priceCanvas=$('priceChart'),equityCanvas=$('equityChart'),tooltip=$('tooltip'),rows=$('tradeRows');
const domainMin=candles[0].t,domainMax=equity.V7_1.at(-1).t;let viewStart=domainMin,viewEnd=domainMax,hoverT=null,activePair=null,dragging=false,dragX=0,dragStart=0,diffIndex=0;
function activeStrategies(){return new Set([...document.querySelectorAll('.strategy-toggle:checked')].map(x=>x.dataset.strategy))}function signed(v,d=2){return(v>=0?'+':'')+Number(v).toFixed(d)}function fmt(v,d=3){return v==null?'—':Number(v).toFixed(d)}function day(t){return new Date(t).toISOString().slice(0,10)}function clamp(v,a,b){return Math.max(a,Math.min(b,v))}function setup(c){const r=c.getBoundingClientRect(),d=devicePixelRatio||1;c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);return{ctx:x,w:r.width,h:r.height}}function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}function visibleCandles(){return candles.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}function visibleTrades(){const a=activeStrategies();return trades.filter(p=>a.has(p.strategy)&&p.exitT>=viewStart&&p.entryT<=viewEnd)}
function ticks(lo,hi,n){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,s=(q<1.5?1:q<3?2:q<7?5:10)*p,o=[];for(let v=Math.ceil(lo/s)*s;v<=hi+s*.1;v+=s)o.push(v);return o}function axes(ctx,m,pw,ph,lo,hi,y){ctx.font='11px ui-monospace';for(const v of ticks(lo,hi,5)){const yy=y(v);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign='right';ctx.fillText(v.toFixed(Math.abs(v)<10?2:1),m.l-8,yy+4)}for(let i=0;i<=8;i++){const z=viewStart+(viewEnd-viewStart)*i/8,x=xs(z,m.l,pw);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign=i===0?'left':i===8?'right':'center';ctx.fillText(day(z),x,m.t+ph+18)}}function line(ctx,vals,key,color,y,l,w,dash=[]){ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.setLineDash(dash);ctx.beginPath();let on=false;for(const p of vals){if(p[key]==null){on=false;continue}const x=xs(p.t+DAY/2,l,w),yy=y(p[key]);on?ctx.lineTo(x,yy):(ctx.moveTo(x,yy),on=true)}ctx.stroke();ctx.setLineDash([])}function marker(ctx,x,y,side,entry,color,size){ctx.fillStyle=color;ctx.strokeStyle=C.bg2;ctx.lineWidth=1.2;ctx.beginPath();if(entry){if(side==='long'){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}function crosshair(ctx,m,pw,ph){if(hoverT==null)return;const x=xs(hoverT,m.l,pw);ctx.strokeStyle=C.muted;ctx.globalAlpha=.55;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}function boundaryLine(ctx,m,pw,ph,label=true){const t=DATA.window.boundaryT;if(t<viewStart||t>viewEnd)return;const x=xs(t,m.l,pw);ctx.strokeStyle='#d6dee5';ctx.globalAlpha=.7;ctx.lineWidth=1.2;ctx.setLineDash([6,5]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;if(label){ctx.fillStyle='#d6dee5';ctx.textAlign='center';ctx.font='11px ui-monospace';ctx.fillText('训练 ← | → 验证',x,m.t+13)}}
function drawPrice(){const{ctx,w,h}=setup(priceCanvas),m={l:70,r:24,t:24,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=visibleCandles(),vtr=visibleTrades();ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.l),...vtr.map(t=>Math.min(t.entry,t.exit))),hi=Math.max(...vis.map(p=>p.h),...vtr.map(t=>Math.max(t.entry,t.exit))),pad=(hi-lo)*.07||1;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y);for(const p of pairs.filter(p=>p.changed&&p.overlayExitT>=viewStart&&p.teacherExitT<=viewEnd)){const x1=xs(p.teacherExitT,m.l,pw),x2=xs(p.overlayExitT,m.l,pw);ctx.fillStyle='rgba(255,209,102,.10)';ctx.fillRect(x1,m.t,x2-x1,ph);ctx.strokeStyle=C.warn;ctx.setLineDash([4,4]);for(const x of[x1,x2]){ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke()}ctx.setLineDash([])}const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const p of vis){const x=xs(p.t+DAY/2,m.l,pw),col=p.c>=p.o?C.up:C.down;ctx.strokeStyle=col;ctx.beginPath();ctx.moveTo(x,y(p.h));ctx.lineTo(x,y(p.l));ctx.stroke();ctx.fillStyle=col;ctx.fillRect(x-bw/2,y(Math.max(p.o,p.c)),bw,Math.max(1,y(Math.min(p.o,p.c))-y(Math.max(p.o,p.c))))}if($('showMa').checked)line(ctx,vis,'ma7',C.ma,y,m.l,pw);for(const t of vtr.sort((a,b)=>a.strategy==='V7_1'?-1:1)){const cfg=DATA.strategies[t.strategy],hot=t.pairId===activePair,x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=cfg.color;ctx.globalAlpha=hot?1:t.strategy==='P4'?.92:.72;ctx.lineWidth=hot?3.6:t.strategy==='V7_1'?3:2.2;ctx.setLineDash(cfg.dash);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,cfg.color,hot?9:7);marker(ctx,x2,y2,t.side,false,cfg.color,hot?9:7);if($('showLabels').checked||hot){ctx.fillStyle=cfg.color;ctx.textAlign='center';ctx.font='10px ui-monospace';ctx.fillText(t.id,x2,y2+(t.strategy==='V7_1'?-11:17))}}boundaryLine(ctx,m,pw,ph,true);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.font='11px ui-monospace';ctx.fillText('PRICE · HYPEUSDT 1D · SMA7（金黄）',m.l,15)}
function drawEquity(){const{ctx,w,h}=setup(equityCanvas),m={l:70,r:24,t:20,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,a=activeStrategies(),series=[...a].map(k=>({k,v:equity[k].filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)})).filter(s=>s.v.length);ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!series.length)return;let lo=Math.min(...series.flatMap(s=>s.v.map(p=>p.v))),hi=Math.max(...series.flatMap(s=>s.v.map(p=>p.v))),pad=(hi-lo)*.08||.02;lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y);for(const s of series){const cfg=DATA.strategies[s.k];ctx.strokeStyle=cfg.color;ctx.lineWidth=s.k==='V7_1'?2.8:2.2;ctx.setLineDash(cfg.dash);ctx.beginPath();s.v.forEach((p,i)=>{const x=xs(p.t,m.l,pw);i?ctx.lineTo(x,y(p.v)):ctx.moveTo(x,y(p.v))});ctx.stroke();ctx.setLineDash([])}boundaryLine(ctx,m,pw,ph,false);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('EQUITY · 训练终值 × 验证相对权益（验证账户原本从1开始）',m.l,13)}function draw(){drawPrice();drawEquity();for(const r of rows.querySelectorAll('tr'))r.classList.toggle('active',r.dataset.pair===activePair)}
function reset(){viewStart=domainMin;viewEnd=domainMax;activePair=null;draw()}function focusRange(a,b){viewStart=Math.max(domainMin,a);viewEnd=Math.min(domainMax,b);activePair=null;draw()}function zoom(f,a=(viewStart+viewEnd)/2){const cur=viewEnd-viewStart,next=clamp(cur*f,8*DAY,domainMax-domainMin),q=(a-viewStart)/cur;viewStart=a-next*q;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}function focusPair(p){const span=Math.max(18*DAY,(Math.max(p.overlayExitT,p.teacherExitT)-p.entryT)*3),mid=(p.entryT+Math.max(p.overlayExitT,p.teacherExitT))/2;viewStart=clamp(mid-span/2,domainMin,Math.max(domainMin,domainMax-span));viewEnd=Math.min(domainMax,viewStart+span);activePair=p.id;draw()}function focusNextDiff(){const changed=pairs.filter(p=>p.changed);if(!changed.length)return;focusPair(changed[diffIndex%changed.length]);diffIndex=(diffIndex+1)%changed.length}
function renderMetrics(){$('metrics').innerHTML=Object.entries(DATA.metrics).map(([k,m])=>`<div class="metric" style="border-top:2px solid ${m.color}">${m.label}<b>训练 ${signed(m.trainReturnPct)}% / MDD ${signed(m.trainMddPct)}%　·　验证 ${signed(m.validationReturnPct)}% / MDD ${signed(m.validationMddPct)}%　·　${m.trades}笔</b></div>`).join('')}function renderTable(){rows.innerHTML=pairs.map(p=>`<tr data-pair="${p.id}" class="${p.changed?'changed':''}"><td>${p.segmentLabel}</td><td>${p.id}</td><td>${p.side==='long'?'做多':'做空'}</td><td>${p.changed?'<span class="badge">退出变化</span>':'相同'}</td><td>${day(p.entryT)}</td><td>${fmt(p.entry)}</td><td class="v7">${day(p.teacherExitT)} · ${fmt(p.teacherExit)}</td><td class="p4">${day(p.overlayExitT)} · ${fmt(p.overlayExit)}</td><td class="${p.teacherReturnPct>=0?'positive':'negative'}">${signed(p.teacherReturnPct)}%</td><td class="${p.overlayReturnPct>=0?'positive':'negative'}">${signed(p.overlayReturnPct)}%</td><td class="${p.returnDeltaPct>=0?'positive':'negative'}">${signed(p.returnDeltaPct)} pct</td><td>${p.extraDays}</td><td>${fmt(p.exitProbability,4)}</td><td>${p.teacherReason}${p.changed?' → '+p.overlayReason:''}</td></tr>`).join('');for(const r of rows.querySelectorAll('tr')){r.onmouseenter=()=>{activePair=r.dataset.pair;draw()};r.onmouseleave=()=>{activePair=null;draw()};r.onclick=()=>{focusPair(pairs.find(p=>p.id===r.dataset.pair));priceCanvas.scrollIntoView({behavior:'smooth',block:'center'})}}}
$('title').textContent=DATA.title;$('subtitle').textContent=DATA.subtitle;$('status').textContent=`${DATA.status} · ${DATA.window.start.slice(0,10)} → ${DATA.window.terminal.slice(0,10)}`;$('difference').textContent=`${DATA.difference.summary} ${DATA.equityNote}`;$('reset').onclick=reset;$('focusTrain').onclick=()=>focusRange(domainMin,DATA.window.boundaryT);$('focusValidation').onclick=()=>focusRange(DATA.window.boundaryT,domainMax);$('focusDiff').onclick=focusNextDiff;$('zoomIn').onclick=()=>zoom(.65);$('zoomOut').onclick=()=>zoom(1.55);$('showMa').onchange=draw;$('showLabels').onchange=draw;for(const x of document.querySelectorAll('.strategy-toggle'))x.onchange=draw;priceCanvas.onwheel=e=>{e.preventDefault();const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-70)/Math.max(1,r.width-94),0,1);zoom(e.deltaY>0?1.2:.82,viewStart+q*(viewEnd-viewStart))};priceCanvas.onpointerdown=e=>{dragging=true;dragX=e.clientX;dragStart=viewStart;priceCanvas.setPointerCapture(e.pointerId)};priceCanvas.onpointerup=e=>{dragging=false;if(priceCanvas.hasPointerCapture(e.pointerId))priceCanvas.releasePointerCapture(e.pointerId)};priceCanvas.onpointermove=e=>{if(dragging){const r=priceCanvas.getBoundingClientRect(),span=viewEnd-viewStart,shift=-(e.clientX-dragX)/Math.max(1,r.width-94)*span;viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw();return}const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-70)/Math.max(1,r.width-94),0,1);hoverT=viewStart+q*(viewEnd-viewStart);const c=candles.reduce((a,b)=>Math.abs(b.t+DAY/2-hoverT)<Math.abs(a.t+DAY/2-hoverT)?b:a,candles[0]),near=trades.filter(t=>activeStrategies().has(t.strategy)&&Math.min(Math.abs(t.entryT-hoverT),Math.abs(t.exitT-hoverT))<DAY*.7);let s=`${day(c.t)} UTC\nO ${fmt(c.o)} H ${fmt(c.h)} L ${fmt(c.l)} C ${fmt(c.c)}\nSMA7 ${fmt(c.ma7)} · slope/ATR ${signed(c.slopeAtr,4)} · RSI6 ${fmt(c.rsi6,1)}`;for(const t of near)s+=`\n${t.id} ${t.strategyLabel} ${t.side==='long'?'多':'空'} · ${signed(t.netReturnPct)}%`;for(const k of activeStrategies()){const ep=equity[k].reduce((a,b)=>Math.abs(b.t-hoverT)<Math.abs(a.t-hoverT)?b:a,equity[k][0]);s+=`\n${DATA.strategies[k].code} equity ${fmt(ep.v,4)}`}tooltip.textContent=s;tooltip.style.display='block';tooltip.style.left=Math.min(innerWidth-545,e.clientX+15)+'px';tooltip.style.top=Math.min(innerHeight-210,e.clientY+15)+'px';draw()};priceCanvas.onpointerleave=()=>{if(!dragging){hoverT=null;tooltip.style.display='none';draw()}};priceCanvas.ondblclick=reset;window.onresize=draw;renderMetrics();renderTable();draw();
</script></body></html>"""


def main() -> None:
    args = parse_args()
    outputs = (
        OUTPUT_PATH,
        MANIFEST_PATH,
        OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".sha256"),
        MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".sha256"),
    )
    if any(path.exists() for path in outputs) and not args.force:
        raise RuntimeError(
            f"comparison artifact exists: {OUTPUT_PATH.name}; use --force"
        )
    payload, manifest = build_payload()
    html = HTML_TEMPLATE.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
    )
    if "__PAYLOAD__" in html:
        raise RuntimeError("template placeholder remains")
    required = (
        "setPointerCapture",
        "ctx.lineTo(x2,y2)",
        "focusNextDiff",
        "focusTrain",
        "focusValidation",
        "DATA.window.boundaryT",
        "黄色区域=延长持有",
        "SMA7",
    )
    for token in required:
        if token not in html:
            raise RuntimeError(f"required comparison interaction missing: {token}")
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    manifest.update(
        {
            "html": OUTPUT_PATH.name,
            "html_sha256": sha256(OUTPUT_PATH),
            "html_bytes": OUTPUT_PATH.stat().st_size,
            "renderer_sha256": sha256(Path(__file__).resolve()),
        }
    )
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for path in (OUTPUT_PATH, MANIFEST_PATH):
        path.with_suffix(path.suffix + ".sha256").write_text(
            f"{sha256(path)}  {path.name}\n", encoding="utf-8"
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
