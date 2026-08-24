"""Render a self-contained PEHC candidate, shadow lifecycle, and exact-V4 HTML."""

from __future__ import annotations

import hashlib
from html import escape
import json
import math
from pathlib import Path
from typing import Any


def _finite(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def candles_from_context(context: Any) -> list[dict[str, Any]]:
    candles = [
        {
            "ts": context.book.ts[index].isoformat(),
            "open": _finite(context.book.open[index]),
            "high": _finite(context.book.high[index]),
            "low": _finite(context.book.low[index]),
            "close": _finite(context.book.close[index]),
            "ma7": _finite(context.features.ma7[index]),
            "display_only_terminal": False,
        }
        for index in range(context.book.count)
    ]
    terminal = float(context.book.quality["terminal_open"])
    candles.append(
        {
            "ts": context.book.terminal_ts.isoformat(),
            "open": terminal,
            "high": terminal,
            "low": terminal,
            "close": terminal,
            "ma7": None,
            "display_only_terminal": True,
        }
    )
    return candles


def _validate_run(run: dict[str, Any], days: set[str], label: str) -> None:
    trades = run.get("trades")
    path = run.get("path")
    if not isinstance(trades, list) or not isinstance(path, list):
        raise RuntimeError(f"{label}: retained trades/path required")
    if len(trades) != int(run["metrics"]["closed_trades"]):
        raise RuntimeError(f"{label}: trade count mismatch")
    previous_exit: str | None = None
    for trade in trades:
        entry = str(trade["entry_ts"])
        exit_ = str(trade["exit_ts"])
        if entry > exit_ or (previous_exit is not None and entry < previous_exit):
            raise RuntimeError(f"{label}: invalid trade ordering")
        if entry[:10] not in days or exit_[:10] not in days:
            raise RuntimeError(f"{label}: trade outside candle window")
        previous_exit = exit_


def _validate_handoffs(candidate: dict[str, Any], days: set[str]) -> dict[str, int]:
    events = candidate.get("handoff_events")
    if not isinstance(events, list):
        raise RuntimeError("candidate handoff events required")
    opportunities = {
        (int(row["origin_index"]), str(row["ts"]))
        for row in events
        if row.get("event") == "handoff_opportunity"
    }
    opportunity_origins = {origin for origin, _ in opportunities}
    delayed_rechecks = {
        (int(row["origin_index"]), str(row["ts"]))
        for row in events
        if row.get("event") == "handoff_delayed_recheck"
    }
    accepts = [row for row in events if row.get("event") == "handoff_accept"]
    entries = {
        str(trade["entry_ts"])
        for trade in candidate["trades"]
        if str(trade["side"]) == "short"
    }
    for event in events:
        if str(event["ts"])[:10] not in days:
            raise RuntimeError("handoff event outside candle window")
        if any("equity" in str(key).lower() for key in event):
            raise RuntimeError("shadow event must be capital-isolated")
    for row in accepts:
        key = (int(row["origin_index"]), str(row["ts"]))
        linked_decision = key in opportunities or key in delayed_rechecks
        if int(row["origin_index"]) not in opportunity_origins or not linked_decision or str(row["ts"]) not in entries:
            raise RuntimeError("accepted handoff is not linked to opportunity and short fill")
    return {
        "events": len(events),
        "opportunities": len(opportunities),
        "accepts": len(accepts),
        "rejects": sum("reject" in str(row.get("event")) for row in events),
    }


def _compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "armId": run["arm_id"],
        "metrics": run["metrics"],
        "trades": [
            {
                "side": row["side"],
                "entryTs": row["entry_ts"],
                "exitTs": row["exit_ts"],
                "entry": row["entry_price"],
                "exit": row["exit_price"],
                "reason": row["exit_reason"],
                "returnPct": float(row["net_return"]) * 100.0,
            }
            for row in run["trades"]
        ],
        "equity": [
            {"ts": row["ts"], "value": row["close_equity"], "position": row["position"], "action": row["action"]}
            for row in run["path"]
        ],
    }


def build_document(
    *,
    title: str,
    candles: list[dict[str, Any]],
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    if not candles:
        raise RuntimeError("candles required")
    days = {str(row["ts"])[:10] for row in candles}
    _validate_run(candidate, days, "candidate")
    _validate_run(control, days, "control")
    handoff_audit = _validate_handoffs(candidate, days)
    payload = {
        "schema": "hype-pehc-trade-path-v1",
        "title": title,
        "candles": candles,
        "candidate": _compact_run(candidate),
        "control": _compact_run(control),
        "handoffs": candidate["handoff_events"],
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    safe_title = escape(title)
    document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title>
<style>:root{{--bg:#081019;--panel:#101a25;--line:#27384a;--text:#eaf2f8;--muted:#8fa2b3;--long:#54b7ff;--short:#ff78b9;--gold:#f1c453;--red:#ff6b78;--green:#4bddaa}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:13px ui-monospace,SFMono-Regular,Menlo,monospace}}main{{max-width:1500px;margin:auto;padding:24px}}h1{{font:600 25px system-ui;margin:0 0 7px}}p{{color:var(--muted);margin:0 0 18px;line-height:1.6}}button{{background:#152230;color:var(--text);border:1px solid var(--line);padding:8px 12px;border-radius:6px}}button.active{{color:var(--gold);border-color:var(--gold)}}.toolbar{{display:flex;gap:8px;margin-bottom:12px}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:12px 0}}.metric,.card{{background:var(--panel);border:1px solid var(--line);border-radius:8px}}.metric{{padding:10px}}.metric b{{display:block;font-size:17px;margin-top:5px}}.card{{padding:12px;margin-bottom:12px;overflow:auto}}canvas{{display:block;width:1400px;height:850px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:7px;border-bottom:1px solid #22303e;text-align:left}}th{{color:var(--muted)}}.legend span{{margin-right:16px}}</style></head><body><main><h1>{safe_title}</h1><p>全部432个已暴露UTC日与display-only terminal open；实际持仓只有资金曲线和逐笔连线。圆点/竖线是无资金shadow状态，金色为机会、绿色为接受、红色为拒绝。按钮切换唯一shadow候选与exact V4。</p><div class="legend"><span>◆ shadow start/stop</span><span>● handoff opportunity</span><span>● accepted/rejected</span></div><div class="toolbar"><button id="candidate" class="active">PEHC Shadow Candidate</button><button id="control">Exact V4</button></div><div id="metrics" class="metrics"></div><div class="card"><canvas id="chart" width="1400" height="850"></canvas></div><div class="card"><h3>逐笔交易</h3><table><thead><tr><th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>Reason</th><th>Net</th></tr></thead><tbody id="trades"></tbody></table></div><div class="card"><h3>Shadow / handoff事件</h3><table><thead><tr><th>#</th><th>Event</th><th>Time</th><th>Origin</th><th>Price/Stop</th><th>Result</th></tr></thead><tbody id="events"></tbody></table></div>
<script>window.PEHC_DATA={data};const D=window.PEHC_DATA,C=document.getElementById('chart'),X=C.getContext('2d');let mode='candidate';const day=s=>s.slice(0,10),idx=new Map(D.candles.map((r,i)=>[day(r.ts),i]));const xx=i=>42+i*(1318/Math.max(1,D.candles.length-1));const yy=(v,lo,hi,t,h)=>t+(hi-v)/Math.max(1e-12,hi-lo)*h;
function render(){{const R=D[mode],P=D.candles;X.clearRect(0,0,C.width,C.height);X.fillStyle='#0b141d';X.fillRect(0,0,C.width,C.height);const lo=Math.min(...P.map(r=>r.low)),hi=Math.max(...P.map(r=>r.high)),top=24,H=545;X.strokeStyle='#203040';for(let k=0;k<7;k++){{let y=top+k*H/6;X.beginPath();X.moveTo(40,y);X.lineTo(1360,y);X.stroke()}}P.forEach((r,i)=>{{let x=xx(i),a=yy(r.open,lo,hi,top,H),b=yy(r.close,lo,hi,top,H);X.strokeStyle=r.close>=r.open?'#4bddaa':'#ff6b78';X.beginPath();X.moveTo(x,yy(r.high,lo,hi,top,H));X.lineTo(x,yy(r.low,lo,hi,top,H));X.stroke();X.fillStyle=X.strokeStyle;X.fillRect(x-1,Math.min(a,b),3,Math.max(1,Math.abs(a-b)))}});X.strokeStyle='#f1c453';X.beginPath();let on=false;P.forEach((r,i)=>{{if(r.ma7==null)return;let x=xx(i),y=yy(r.ma7,lo,hi,top,H);on?X.lineTo(x,y):(X.moveTo(x,y),on=true)}});X.stroke();R.trades.forEach(t=>{{let a=idx.get(day(t.entryTs)),b=idx.get(day(t.exitTs));X.strokeStyle=t.side==='long'?'#54b7ff':'#ff78b9';X.lineWidth=2;X.beginPath();X.moveTo(xx(a),yy(t.entry,lo,hi,top,H));X.lineTo(xx(b),yy(t.exit,lo,hi,top,H));X.stroke()}});X.lineWidth=1;if(mode==='candidate')D.handoffs.filter(e=>['shadow_start','shadow_protective_stop','handoff_opportunity','handoff_accept'].includes(e.event)||e.event.includes('reject')).forEach(e=>{{let i=idx.get(day(e.ts));if(i==null)return;let color=e.event==='handoff_accept'?'#4bddaa':e.event.includes('reject')?'#ff6b78':e.event==='handoff_opportunity'?'#f1c453':'#9b87f5';X.strokeStyle=color;X.globalAlpha=.55;X.beginPath();X.moveTo(xx(i),top);X.lineTo(xx(i),top+H);X.stroke();X.globalAlpha=1}});const eq=R.equity,elo=Math.min(...eq.map(r=>r.value)),ehi=Math.max(...eq.map(r=>r.value));X.strokeStyle='#d7e3ec';X.beginPath();eq.forEach((r,i)=>{{let x=42+i*1318/Math.max(1,eq.length-1),y=yy(r.value,elo,ehi,625,185);i?X.lineTo(x,y):X.moveTo(x,y)}});X.stroke();let m=R.metrics;document.getElementById('metrics').innerHTML=[['Arm',R.armId],['Net return',m.net_return_pct.toFixed(2)+'%'],['Real 1h MDD',m.chronological_1h_mdd_pct.toFixed(2)+'%'],['Daily-extreme MDD',m.daily_extreme_mdd_pct.toFixed(2)+'%'],['Trades',m.closed_trades]].map(v=>`<div class="metric">${{v[0]}}<b>${{v[1]}}</b></div>`).join('');document.getElementById('trades').innerHTML=R.trades.map((t,i)=>`<tr><td>${{i+1}}</td><td>${{t.side}}</td><td>${{t.entryTs}}</td><td>${{t.exitTs}}</td><td>${{t.reason}}</td><td>${{t.returnPct.toFixed(2)}}%</td></tr>`).join('')}}
document.getElementById('events').innerHTML=D.handoffs.map((e,i)=>`<tr><td>${{i+1}}</td><td>${{e.event}}</td><td>${{e.ts}}</td><td>${{e.origin_index??''}}</td><td>${{e.price??e.stop_price??''}}</td><td>${{e.passed??''}}</td></tr>`).join('');for(const id of ['candidate','control'])document.getElementById(id).onclick=()=>{{mode=id;document.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.id===id));render()}};render();</script></main></body></html>"""
    encoded = document.encode("utf-8")
    audit = {
        "schema": payload["schema"],
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "candidate_trades": len(candidate["trades"]),
        "control_trades": len(control["trades"]),
        "handoff_audit": handoff_audit,
        "all_trades_connected": True,
        "shadow_capital_isolated": True,
        "display_only_terminal_candles": sum(bool(row.get("display_only_terminal")) for row in candles),
        "external_dependencies": 0,
    }
    return encoded, audit


def write_locked(path: Path, document: bytes) -> dict[str, Any]:
    hash_path = path.with_suffix(".sha256")
    if path.exists() or hash_path.exists():
        raise RuntimeError(f"locked HTML already exists: {path.name}")
    digest = hashlib.sha256(document).hexdigest()
    with path.open("xb") as handle:
        handle.write(document)
    with hash_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return {"path": str(path), "sha256": digest, "bytes": len(document)}
