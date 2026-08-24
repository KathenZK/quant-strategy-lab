"""Render a locked TPR candidate against exact V4 with every trade connected."""

from __future__ import annotations

import argparse
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
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
PREFIX = ARTIFACT_DIR / "hype_1d_ma7_trend_phase_risk_2026-08-09"
TRIALS_PATH = Path(f"{PREFIX}_development_trials.json")
DEVELOPMENT_PATH = Path(f"{PREFIX}_development.json")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def verify_locked(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(".sha256")
    if not path.is_file() or not sidecar.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    fields = sidecar.read_text(encoding="utf-8").strip().split()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(fields) != 2 or fields[0] != digest or fields[1] != path.name:
        raise RuntimeError(f"invalid locked artifact: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def finite(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def validate_run(run: dict[str, Any], candle_ts: set[str]) -> None:
    trades = run.get("trades")
    path = run.get("path")
    if not isinstance(trades, list) or not isinstance(path, list):
        raise RuntimeError("retained trades/path required")
    if len(trades) != int(run["metrics"]["closed_trades"]):
        raise RuntimeError("trade count mismatch")
    previous_exit: str | None = None
    for trade in trades:
        entry = str(trade["entry_ts"])
        exit_ = str(trade["exit_ts"])
        if entry > exit_ or (previous_exit is not None and entry < previous_exit):
            raise RuntimeError("invalid trade ordering")
        if entry[:10] not in candle_ts or exit_[:10] not in candle_ts:
            raise RuntimeError("trade outside visualized market window")
        previous_exit = exit_


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "armId": run["arm_id"],
        "metrics": run["metrics"],
        "trades": [
            {
                "side": trade["side"],
                "entryTs": trade["entry_ts"],
                "exitTs": trade["exit_ts"],
                "entry": trade["entry_price"],
                "exit": trade["exit_price"],
                "reason": trade["exit_reason"],
                "returnPct": float(trade["net_return"]) * 100.0,
                "entryLeverage": float(trade.get("entry_leverage", 1.0)),
            }
            for trade in run["trades"]
        ],
        "equity": [
            {
                "ts": row["ts"],
                "equity": row["close_equity"],
                "position": row["position"],
                "action": row["action"],
            }
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
    candle_days = {str(row["ts"])[:10] for row in candles}
    validate_run(candidate, candle_days)
    validate_run(control, candle_days)
    payload = {
        "schema": "hype-tpr-trade-path-v1",
        "title": title,
        "candles": candles,
        "candidate": compact_run(candidate),
        "control": compact_run(control),
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#0b0d10;--panel:#11151a;--text:#e8edf2;--muted:#84909d;--green:#47d7a1;--red:#ff6b74;--gold:#e9b949;--blue:#5aa9ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
main{{max-width:1480px;margin:auto;padding:24px}}h1{{font:600 24px system-ui;margin:0 0 8px}}p{{color:var(--muted);margin:0 0 18px}}
.toolbar{{display:flex;gap:8px;margin-bottom:12px}}button{{background:#20262d;color:var(--text);border:1px solid #303944;padding:8px 12px;border-radius:6px;cursor:pointer}}button.active{{border-color:var(--gold);color:var(--gold)}}
.card{{background:var(--panel);border:1px solid #222a33;border-radius:10px;padding:12px;overflow:auto}}canvas{{display:block;width:1400px;height:820px}}
.metrics{{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:8px;margin:12px 0}}.metric{{background:var(--panel);border:1px solid #222a33;padding:10px;border-radius:8px}}.metric b{{display:block;font-size:18px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:8px;border-bottom:1px solid #252c34;text-align:left}}th{{color:var(--muted)}}
</style></head><body><main><h1>{title}</h1><p>完整 D-window K线 / MA7 / 逐笔入场—出场连线 / 收盘权益；按钮切换候选与 exact V4。</p>
<div class="toolbar"><button id="candidate" class="active">Candidate</button><button id="control">Exact V4</button></div><div id="metrics" class="metrics"></div>
<div class="card"><canvas id="chart" width="1400" height="820"></canvas></div><div class="card"><table><thead><tr><th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>Reason</th><th>Net</th><th>Leverage</th></tr></thead><tbody id="trades"></tbody></table></div>
<script>window.TPR_DATA={data};
const D=window.TPR_DATA,C=document.getElementById('chart'),X=C.getContext('2d');let mode='candidate';
const day=s=>s.slice(0,10),idx=new Map(D.candles.map((r,i)=>[day(r.ts),i]));
function y(v,lo,hi,top,height){{return top+(hi-v)/(hi-lo)*height}}function x(i){{return 42+i*(1318/Math.max(1,D.candles.length-1))}}
function render(){{const R=D[mode],P=D.candles;X.clearRect(0,0,C.width,C.height);X.fillStyle='#0f1318';X.fillRect(0,0,C.width,C.height);
const lo=Math.min(...P.map(r=>r.low)),hi=Math.max(...P.map(r=>r.high));const top=26,H=520;X.strokeStyle='#202832';for(let k=0;k<6;k++){{let yy=top+k*H/5;X.beginPath();X.moveTo(40,yy);X.lineTo(1360,yy);X.stroke()}}
P.forEach((r,i)=>{{const xx=x(i),yo=y(r.open,lo,hi,top,H),yc=y(r.close,lo,hi,top,H);X.strokeStyle=r.close>=r.open?'#47d7a1':'#ff6b74';X.beginPath();X.moveTo(xx,y(r.high,lo,hi,top,H));X.lineTo(xx,y(r.low,lo,hi,top,H));X.stroke();X.fillStyle=X.strokeStyle;X.fillRect(xx-1,Math.min(yo,yc),3,Math.max(1,Math.abs(yc-yo)))}});
X.strokeStyle='#e9b949';X.beginPath();let started=false;P.forEach((r,i)=>{{if(r.ma7==null)return;let xx=x(i),yy=y(r.ma7,lo,hi,top,H);if(!started){{X.moveTo(xx,yy);started=true}}else X.lineTo(xx,yy)}});X.stroke();
R.trades.forEach(t=>{{let i1=idx.get(day(t.entryTs)),i2=idx.get(day(t.exitTs));X.strokeStyle=t.side==='long'?'#5aa9ff':'#ff7ab6';X.lineWidth=2;X.beginPath();X.moveTo(x(i1),y(t.entry,lo,hi,top,H));X.lineTo(x(i2),y(t.exit,lo,hi,top,H));X.stroke();X.fillStyle=X.strokeStyle;X.beginPath();X.arc(x(i1),y(t.entry,lo,hi,top,H),4,0,7);X.fill();X.beginPath();X.arc(x(i2),y(t.exit,lo,hi,top,H),4,0,7);X.fill()}});X.lineWidth=1;
const eq=R.equity,elo=Math.min(...eq.map(r=>r.equity)),ehi=Math.max(...eq.map(r=>r.equity));X.strokeStyle='#aab4be';X.beginPath();eq.forEach((r,i)=>{{let xx=42+i*(1318/Math.max(1,eq.length-1)),yy=y(r.equity,elo,ehi,590,190);if(i)X.lineTo(xx,yy);else X.moveTo(xx,yy)}});X.stroke();
const m=R.metrics;document.getElementById('metrics').innerHTML=[['Arm',R.armId],['Net return',m.net_return_pct.toFixed(2)+'%'],['Chronological MDD',m.chronological_1h_mdd_pct.toFixed(2)+'%'],['Daily stress MDD',m.daily_extreme_mdd_pct.toFixed(2)+'%'],['Trades',m.closed_trades]].map(v=>`<div class="metric">${{v[0]}}<b>${{v[1]}}</b></div>`).join('');document.getElementById('trades').innerHTML=R.trades.map((t,i)=>`<tr><td>${{i+1}}</td><td>${{t.side}}</td><td>${{t.entryTs}}</td><td>${{t.exitTs}}</td><td>${{t.reason}}</td><td>${{t.returnPct.toFixed(2)}}%</td><td>${{t.entryLeverage.toFixed(2)}}x</td></tr>`).join('')}}
for(const id of ['candidate','control'])document.getElementById(id).onclick=()=>{{mode=id;document.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.id===id));render()}};render();</script></main></body></html>"""
    encoded = html.encode("utf-8")
    audit = {
        "schema": payload["schema"],
        "sha256": sha256_bytes(encoded),
        "bytes": len(encoded),
        "candidate_trades": len(candidate["trades"]),
        "control_trades": len(control["trades"]),
        "all_trades_connected": True,
        "external_dependencies": 0,
    }
    return encoded, audit


def write_locked(path: Path, document: bytes) -> dict[str, Any]:
    sidecar = path.with_suffix(".sha256")
    if path.exists() or sidecar.exists():
        raise RuntimeError(f"locked HTML already exists: {path.name}")
    digest = sha256_bytes(document)
    with path.open("xb") as handle:
        handle.write(document)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return {"path": str(path), "sha256": digest, "bytes": len(document)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-id")
    args = parser.parse_args()
    development = verify_locked(DEVELOPMENT_PATH)
    trials = verify_locked(TRIALS_PATH)["trials"]
    by_id = {row["arm_id"]: row for row in trials}
    arm_id = args.arm_id or development.get("champion_arm_id") or "QOFF_EOFF_T25X2"
    if arm_id not in by_id or arm_id == "C000_EXACT_V4":
        raise RuntimeError(f"invalid candidate arm: {arm_id}")
    adapter = load_module(ADAPTER_PATH, "hype_tpr_renderer_adapter")
    context = adapter.load_context()
    candles = [
        {
            "ts": context.book.ts[index].isoformat(),
            "open": float(context.book.open[index]),
            "high": float(context.book.high[index]),
            "low": float(context.book.low[index]),
            "close": float(context.book.close[index]),
            "ma7": finite(context.features.ma7[index]),
        }
        for index in range(259)
    ]
    document, audit = build_document(
        title=f"HYPE 1D MA7 TPR · {arm_id} vs exact V4 · Development",
        candles=candles,
        candidate=by_id[arm_id]["base_full"],
        control=by_id["C000_EXACT_V4"]["base_full"],
    )
    output = Path(f"{PREFIX}_development_{arm_id}_trade_path.html")
    audit.update(write_locked(output, document))
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
