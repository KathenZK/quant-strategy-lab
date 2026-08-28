"""Render P1 strict-cross ML validation as a self-contained interactive HTML."""

from __future__ import annotations

import argparse
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
P1_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p1_cross_event.py"
STEM = "hype_1d_ma7_mlt_p1_cross_event_dynamic_exit_2026-08-27"
SUMMARY_PATH = ARTIFACT_DIR / f"{STEM}_summary.json"
EVENTS_PATH = ARTIFACT_DIR / f"{STEM}_events.csv"
TRADES_PATH = ARTIFACT_DIR / f"{STEM}_validation_trades.csv"
PATH_PATH = ARTIFACT_DIR / f"{STEM}_validation_path.csv"
OUTPUT_PATH = ARTIFACT_DIR / f"{STEM}_trade_paths.html"
MANIFEST_PATH = ARTIFACT_DIR / f"{STEM}_trade_paths_manifest.json"

STRATEGIES = {
    "ML_ENTRY_DYNAMIC_EXIT": {"label": "ML 入场 + 动态退出", "code": "ML", "equity": "#5cc8ff"},
    "ALL_CROSS_DYNAMIC_EXIT": {"label": "全部穿越 + 动态退出", "code": "DYN", "equity": "#bd8cff"},
    "ALL_CROSS_MA7_EXIT": {"label": "全部穿越 + MA7反穿退出", "code": "MA", "equity": "#ffb35c"},
    "ALL_CROSS_H7": {"label": "全部穿越 + 固定7日", "code": "H7", "equity": "#8fdd73"},
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


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1_000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    for path in (SUMMARY_PATH, EVENTS_PATH, TRADES_PATH, PATH_PATH):
        if not path.exists():
            raise RuntimeError(f"missing retained P1 artifact: {path}")
    p1 = load_module(P1_SCRIPT, "hype_1d_ma7_mlt_p1_chart")
    p0, market = p1.load_dependencies()
    state = p1.build_state_frame(p0, market)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    events = pd.read_csv(EVENTS_PATH)
    trades_frame = pd.read_csv(TRADES_PATH)
    paths_frame = pd.read_csv(PATH_PATH)

    validation_state = state.iloc[p1.TRAIN_DAYS :].copy()
    candles: list[dict[str, Any]] = []
    for index, row in validation_state.iterrows():
        candles.append(
            {
                "t": timestamp_ms(row["ts"]),
                "o": float(row["open"]),
                "h": float(row["high"]),
                "l": float(row["low"]),
                "c": float(row["close"]),
                "ma7": finite_or_none(row["ma7"]),
                "slopeAtr": finite_or_none(row["slope1_atr"]),
                "index": int(index),
            }
        )

    validation_events = events.loc[events["split"].eq("validation")].copy()
    signals: list[dict[str, Any]] = []
    for row in validation_events.to_dict("records"):
        decision_index = int(row["decision_index"])
        state_row = state.iloc[decision_index]
        probability = finite_or_none(row["entry_probability"])
        signals.append(
            {
                "id": str(row["event_id"]),
                "t": timestamp_ms(row["decision_ts"]),
                "ts": str(row["decision_ts"]),
                "side": str(row["side"]),
                "close": float(state_row["close"]),
                "ma7": float(state_row["ma7"]),
                "slopeAtr": float(state_row["slope1_atr"]),
                "probability": probability,
                "accepted": bool(probability is not None and probability >= p1.ENTRY_THRESHOLD),
            }
        )

    trades: list[dict[str, Any]] = []
    trade_ids: set[str] = set()
    counters = {key: 0 for key in STRATEGIES}
    for row in trades_frame.to_dict("records"):
        strategy = str(row["strategy"])
        counters[strategy] += 1
        trade_id = f"{STRATEGIES[strategy]['code']}-{counters[strategy]:02d}"
        if trade_id in trade_ids:
            raise RuntimeError(f"duplicate trade id: {trade_id}")
        trade_ids.add(trade_id)
        entry_t = timestamp_ms(row["entry_ts"])
        exit_t = timestamp_ms(row["exit_ts"])
        trades.append(
            {
                "id": trade_id,
                "strategy": strategy,
                "strategyLabel": STRATEGIES[strategy]["label"],
                "eventId": str(row["event_id"]),
                "side": str(row["side"]),
                "signalT": timestamp_ms(row["entry_signal_ts"]),
                "entryT": entry_t,
                "entry": float(row["entry_price"]),
                "exitT": exit_t,
                "exit": float(row["exit_price"]),
                "days": int(row["bars_held"]),
                "netReturnPct": float(row["net_return"]) * 100.0,
                "entryProbability": finite_or_none(row["entry_probability"]),
                "exitProbability": finite_or_none(row["exit_continue_probability"]),
                "exitReason": str(row["exit_reason"]),
            }
        )

    equity: dict[str, list[dict[str, Any]]] = {}
    for strategy, config in STRATEGIES.items():
        frame = paths_frame.loc[paths_frame["strategy"].eq(strategy)]
        equity[strategy] = [
            {
                "t": timestamp_ms(row["ts"]),
                "v": float(row["equity"]),
                "side": int(row["position"]),
            }
            for row in frame.to_dict("records")
        ]
        if len(equity[strategy]) != 82:
            raise RuntimeError(f"{strategy}: expected 82 validation path rows")

    metrics = {
        key: {
            "label": STRATEGIES[key]["label"],
            "color": STRATEGIES[key]["equity"],
            "returnPct": float(summary["validation"][key]["total_return"]) * 100.0,
            "mddPct": float(summary["validation"][key]["max_drawdown"]) * 100.0,
            "trades": int(summary["validation"][key]["trade_count"]),
            "winRatePct": float(summary["validation"][key]["win_rate"]) * 100.0,
        }
        for key in STRATEGIES
    }
    payload = {
        "title": "HYPE 1D MA7-MLT P1：严格穿越事件与动态退出",
        "subtitle": "UTC 日线 · fresh SMA7 cross · |SMA7 slope| ≥ 0.02 ATR7 · 信号后下一日开盘成交",
        "status": "reused holdout diagnostic · not promoted · not live-ready",
        "generatedAt": datetime.now(UTC).isoformat(),
        "window": {
            "start": str(market.daily["ts"].iloc[p1.TRAIN_DAYS]),
            "end": str(market.open_ts[-1]),
        },
        "strategies": STRATEGIES,
        "metrics": metrics,
        "candles": candles,
        "signals": signals,
        "equity": equity,
        "trades": trades,
    }
    manifest = {
        "schema": "hype-1d-ma7-mlt-p1-trade-path-manifest-v1",
        "generated_at": payload["generatedAt"],
        "sources": {
            path.name: sha256(path)
            for path in (SUMMARY_PATH, EVENTS_PATH, TRADES_PATH, PATH_PATH)
        },
        "renderer": Path(__file__).name,
        "window": payload["window"],
        "candles": len(candles),
        "signals": len(signals),
        "accepted_ml_signals": sum(row["accepted"] for row in signals),
        "equity_points": {key: len(value) for key, value in equity.items()},
        "closed_trades": len(trades),
        "trades_by_strategy": counters,
        "unique_trade_ids": len(trade_ids) == len(trades),
        "entry_lte_exit": all(row["entryT"] <= row["exitT"] for row in trades),
        "complete_endpoints": all(row["entry"] > 0 and row["exit"] > 0 for row in trades),
        "line_render_count": len(trades),
        "ma7_points": sum(row["ma7"] is not None for row in candles),
        "external_dependencies": 0,
    }
    return payload, manifest


HTML_TEMPLATE = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HYPE 1D MA7-MLT P1 交易路径</title><style>
:root{color-scheme:dark;--bg:#080b0f;--panel:#0e141a;--panel2:#111a22;--line:#26323d;--grid:#1b2630;--text:#edf2f5;--muted:#8d9ba7;--up:#27d3a2;--down:#f06478;--ma:#f4ca58;--long:#31d19a;--short:#ff7b68}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}.shell{max-width:1900px;margin:auto;padding:22px}header{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:end;margin-bottom:14px}h1{margin:0 0 6px;font:650 23px/1.2 system-ui,sans-serif}.subtitle,.status,.hint{color:var(--muted);font-size:12px}.status{margin-top:4px}.metrics{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}.metric{min-width:150px;padding:8px 10px;border:1px solid var(--line);background:var(--panel)}.metric b{display:block;margin-top:2px;font-size:14px}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding:9px 11px;border:1px solid var(--line);border-bottom:0;background:var(--panel2)}button{color:var(--text);border:1px solid #344653;background:#15202a;padding:6px 10px;cursor:pointer;font:inherit}label{color:var(--muted);user-select:none}input{vertical-align:-2px}.ma-key{color:var(--ma)}.long{color:var(--long)}.short{color:var(--short)}.chart{border:1px solid var(--line);background:var(--panel);overflow:hidden}canvas{width:100%;display:block}#priceChart{height:600px;cursor:crosshair}#slopeChart{height:145px;border-top:1px solid var(--line)}#equityChart{height:230px;border-top:1px solid var(--line)}.hint{padding:8px 11px;border:1px solid var(--line);border-top:0}.table-wrap{margin-top:18px;overflow:auto;max-height:560px;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;min-width:1250px}th,td{padding:8px 9px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}th{color:var(--muted);background:var(--panel2);position:sticky;top:0;z-index:1}th:nth-child(-n+5),td:nth-child(-n+5),th:nth-child(10),td:nth-child(10){text-align:left}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#17232d}.positive{color:var(--up)}.negative{color:var(--down)}#tooltip{position:fixed;z-index:10;display:none;pointer-events:none;max-width:490px;padding:9px 11px;border:1px solid #465966;background:rgba(7,11,15,.97);box-shadow:0 8px 28px rgba(0,0,0,.45);white-space:pre-line;font-size:12px}@media(max-width:900px){.shell{padding:10px}header{grid-template-columns:1fr}.metrics{justify-content:flex-start}#priceChart{height:480px}}
</style></head><body><div class="shell"><header><div><h1 id="title"></h1><div id="subtitle" class="subtitle"></div><div id="status" class="status"></div></div><div id="metrics" class="metrics"></div></header>
<div class="toolbar"><button id="reset">完整范围</button><button id="zoomIn">放大</button><button id="zoomOut">缩小</button><label><input id="showMa" type="checkbox" checked><span class="ma-key">SMA7</span></label><label><input id="showSignals" type="checkbox" checked>穿越事件</label><label><input id="showLabels" type="checkbox">交易编号</label><label><input class="strategy-toggle" data-strategy="ML_ENTRY_DYNAMIC_EXIT" type="checkbox" checked>ML</label><label><input class="strategy-toggle" data-strategy="ALL_CROSS_DYNAMIC_EXIT" type="checkbox">全部+动态</label><label><input class="strategy-toggle" data-strategy="ALL_CROSS_MA7_EXIT" type="checkbox">MA7反穿</label><label><input class="strategy-toggle" data-strategy="ALL_CROSS_H7" type="checkbox">固定7日</label><span class="long">绿色=做多</span><span class="short">红色=做空</span></div>
<div class="chart"><canvas id="priceChart"></canvas><canvas id="slopeChart"></canvas><canvas id="equityChart"></canvas></div><div class="hint">金黄线为 SMA7；实线=ML，点线=全部穿越动态退出，长虚线=MA7反穿退出，点划线=固定7日。滚轮缩放 · 拖拽平移 · 双击复位 · 悬停查看 · 点击逐笔聚焦。</div>
<div class="table-wrap"><table><thead><tr><th>编号</th><th>策略</th><th>事件</th><th>方向</th><th>信号日</th><th>入场</th><th>出场</th><th>入场价</th><th>出场价</th><th>净收益</th><th>持有日</th><th>入场概率</th><th>退出继续概率</th><th>退出原因</th></tr></thead><tbody id="tradeRows"></tbody></table></div></div><div id="tooltip"></div><script>
const DATA=__PAYLOAD__,DAY=86400000,C={bg:'#0e141a',bg2:'#0a1015',grid:'#1b2630',muted:'#8d9ba7',up:'#27d3a2',down:'#f06478',ma:'#f4ca58',long:'#31d19a',short:'#ff7b68',slope:'#bd8cff',threshold:'#667887'};
const $=id=>document.getElementById(id),candles=DATA.candles,trades=DATA.trades,signals=DATA.signals,equity=DATA.equity,priceCanvas=$('priceChart'),slopeCanvas=$('slopeChart'),equityCanvas=$('equityChart'),tooltip=$('tooltip'),rows=$('tradeRows');
const domainMin=candles[0].t,domainMax=Math.max(candles.at(-1).t+DAY,...Object.values(equity).map(v=>v.at(-1).t));let viewStart=domainMin,viewEnd=domainMax,hoverT=null,activeTrade=null,dragging=false,dragX=0,dragStart=0;
function activeStrategies(){return new Set([...document.querySelectorAll('.strategy-toggle:checked')].map(x=>x.dataset.strategy))}function signed(v,d=2){return(v>=0?'+':'')+Number(v).toFixed(d)}function fmt(v,d=3){return v==null?'—':Number(v).toFixed(d)}function day(t){return new Date(t).toISOString().slice(0,10)}function clamp(v,a,b){return Math.max(a,Math.min(b,v))}function setup(c){const r=c.getBoundingClientRect(),d=devicePixelRatio||1;c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);return{ctx:x,w:r.width,h:r.height}}function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}function vc(){return candles.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}function vt(){const a=activeStrategies();return trades.filter(p=>a.has(p.strategy)&&p.exitT>=viewStart&&p.entryT<=viewEnd)}
function ticks(lo,hi,n){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,s=(q<1.5?1:q<3?2:q<7?5:10)*p,o=[];for(let v=Math.ceil(lo/s)*s;v<=hi+s*.1;v+=s)o.push(v);return o}function axes(ctx,m,pw,ph,lo,hi,y,time=true){ctx.font='11px ui-monospace';for(const v of ticks(lo,hi,5)){const yy=y(v);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign='right';ctx.fillText(v.toFixed(Math.abs(v)<10?2:1),m.l-8,yy+4)}if(time)for(let i=0;i<=8;i++){const z=viewStart+(viewEnd-viewStart)*i/8,x=xs(z,m.l,pw);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign=i===0?'left':i===8?'right':'center';ctx.fillText(day(z),x,m.t+ph+18)}}function line(ctx,vals,key,color,y,l,w,dash=[]){ctx.strokeStyle=color;ctx.lineWidth=1.7;ctx.setLineDash(dash);ctx.beginPath();let on=false;for(const p of vals){if(p[key]==null){on=false;continue}const x=xs(p.t+DAY/2,l,w),yy=y(p[key]);on?ctx.lineTo(x,yy):(ctx.moveTo(x,yy),on=true)}ctx.stroke();ctx.setLineDash([])}function dashFor(s){return s==='ML_ENTRY_DYNAMIC_EXIT'?[]:s==='ALL_CROSS_DYNAMIC_EXIT'?[2,4]:s==='ALL_CROSS_MA7_EXIT'?[9,4]:[10,3,2,3]}function marker(ctx,x,y,side,entry,color,size=6){ctx.fillStyle=color;ctx.strokeStyle=C.bg2;ctx.lineWidth=1.3;ctx.beginPath();if(entry){if(side==='long'){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}function cross(ctx,m,pw,ph){if(hoverT==null)return;const x=xs(hoverT,m.l,pw);ctx.strokeStyle=C.muted;ctx.globalAlpha=.6;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}
function drawPrice(){const{ctx,w,h}=setup(priceCanvas),m={l:68,r:22,t:22,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=vc();ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.l)),hi=Math.max(...vis.map(p=>p.h));for(const t of vt()){lo=Math.min(lo,t.entry,t.exit);hi=Math.max(hi,t.entry,t.exit)}const pad=(hi-lo)*.07||1;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,true);const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const p of vis){const x=xs(p.t+DAY/2,m.l,pw),col=p.c>=p.o?C.up:C.down;ctx.strokeStyle=col;ctx.beginPath();ctx.moveTo(x,y(p.h));ctx.lineTo(x,y(p.l));ctx.stroke();ctx.fillStyle=col;ctx.fillRect(x-bw/2,y(Math.max(p.o,p.c)),bw,Math.max(1,y(Math.min(p.o,p.c))-y(Math.max(p.o,p.c))))}if($('showMa').checked)line(ctx,vis,'ma7',C.ma,y,m.l,pw);if($('showSignals').checked)for(const s of signals.filter(s=>s.t>=viewStart&&s.t<=viewEnd)){const x=xs(s.t+DAY/2,m.l,pw),yy=y(s.close),col=s.side==='long'?C.long:C.short;ctx.save();ctx.translate(x,yy);ctx.rotate(Math.PI/4);ctx.fillStyle=s.accepted?col:C.bg2;ctx.strokeStyle=col;ctx.lineWidth=2;ctx.fillRect(-4,-4,8,8);ctx.strokeRect(-4,-4,8,8);ctx.restore()}for(const t of vt()){const hot=t.id===activeTrade,col=t.side==='long'?C.long:C.short,x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=col;ctx.globalAlpha=hot?1:t.strategy==='ML_ENTRY_DYNAMIC_EXIT'?.82:.48;ctx.lineWidth=hot?3:t.strategy==='ML_ENTRY_DYNAMIC_EXIT'?2.4:1.35;ctx.setLineDash(dashFor(t.strategy));ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,col,hot?8:6);marker(ctx,x2,y2,t.side,false,col,hot?8:6);if($('showLabels').checked||hot){ctx.fillStyle=col;ctx.textAlign='center';ctx.font='10px ui-monospace';ctx.fillText(t.id,x1,y1+(t.side==='long'?18:-12))}}cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.font='11px ui-monospace';ctx.fillText('PRICE · HYPEUSDT · SMA7（金黄）',m.l,14)}
function drawSlope(){const{ctx,w,h}=setup(slopeCanvas),m={l:68,r:22,t:18,b:28},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=vc();ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(-.04,...vis.map(p=>p.slopeAtr??0)),hi=Math.max(.04,...vis.map(p=>p.slopeAtr??0)),pad=(hi-lo)*.08;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,false);for(const v of[-.02,.02]){ctx.strokeStyle=C.threshold;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(m.l,y(v));ctx.lineTo(m.l+pw,y(v));ctx.stroke()}ctx.setLineDash([]);line(ctx,vis,'slopeAtr',C.slope,y,m.l,pw);cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('SMA7 1D SLOPE / ATR7 · 门槛 ±0.02',m.l,12)}
function drawEquity(){const{ctx,w,h}=setup(equityCanvas),m={l:68,r:22,t:18,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,a=activeStrategies(),series=[...a].map(k=>({k,v:equity[k].filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)})).filter(x=>x.v.length);ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!series.length)return;let lo=Math.min(...series.flatMap(x=>x.v.map(p=>p.v))),hi=Math.max(...series.flatMap(x=>x.v.map(p=>p.v))),pad=(hi-lo)*.08||.03;lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,true);for(const s of series){ctx.strokeStyle=DATA.strategies[s.k].equity;ctx.lineWidth=s.k==='ML_ENTRY_DYNAMIC_EXIT'?2.5:1.5;ctx.setLineDash(dashFor(s.k));ctx.beginPath();s.v.forEach((p,i)=>{const x=xs(p.t,m.l,pw);i?ctx.lineTo(x,y(p.v)):ctx.moveTo(x,y(p.v))});ctx.stroke();ctx.setLineDash([])}cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('OPEN-TO-OPEN EQUITY · 勾选策略可切换',m.l,12)}function draw(){drawPrice();drawSlope();drawEquity();for(const r of rows.querySelectorAll('tr'))r.classList.toggle('active',r.dataset.id===activeTrade)}
function reset(){viewStart=domainMin;viewEnd=domainMax;activeTrade=null;draw()}function zoom(f,a=(viewStart+viewEnd)/2){const cur=viewEnd-viewStart,next=clamp(cur*f,10*DAY,domainMax-domainMin),q=(a-viewStart)/cur;viewStart=a-next*q;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}function renderMetrics(){$('metrics').innerHTML=Object.entries(DATA.metrics).map(([k,m])=>`<div class="metric" style="border-top:2px solid ${m.color}">${m.label}<b>${signed(m.returnPct)}% · MDD ${signed(m.mddPct)}% · ${m.trades}笔</b></div>`).join('')}function renderTable(){rows.innerHTML=trades.map(t=>`<tr data-id="${t.id}" data-strategy="${t.strategy}"><td>${t.id}</td><td>${t.strategyLabel}</td><td>${t.eventId}</td><td class="${t.side}">${t.side==='long'?'做多':'做空'}</td><td>${day(t.signalT)}</td><td>${day(t.entryT)}</td><td>${day(t.exitT)}</td><td>${fmt(t.entry)}</td><td>${fmt(t.exit)}</td><td class="${t.netReturnPct>=0?'positive':'negative'}">${signed(t.netReturnPct)}%</td><td>${t.days}</td><td>${t.entryProbability==null?'—':fmt(t.entryProbability,3)}</td><td>${t.exitProbability==null?'—':fmt(t.exitProbability,3)}</td><td>${t.exitReason}</td></tr>`).join('');for(const r of rows.querySelectorAll('tr')){r.onmouseenter=()=>{activeTrade=r.dataset.id;draw()};r.onmouseleave=()=>{activeTrade=null;draw()};r.onclick=()=>{const t=trades.find(x=>x.id===r.dataset.id),box=document.querySelector(`.strategy-toggle[data-strategy="${t.strategy}"]`);box.checked=true;const span=Math.max(16*DAY,(t.exitT-t.entryT)*3),mid=(t.entryT+t.exitT)/2;viewStart=clamp(mid-span/2,domainMin,Math.max(domainMin,domainMax-span));viewEnd=Math.min(domainMax,viewStart+span);activeTrade=t.id;draw();priceCanvas.scrollIntoView({behavior:'smooth',block:'center'})}}}
$('title').textContent=DATA.title;$('subtitle').textContent=DATA.subtitle;$('status').textContent=`${DATA.status} · ${DATA.window.start.slice(0,10)} → ${DATA.window.end.slice(0,10)}`;$('reset').onclick=reset;$('zoomIn').onclick=()=>zoom(.65);$('zoomOut').onclick=()=>zoom(1.55);$('showMa').onchange=draw;$('showSignals').onchange=draw;$('showLabels').onchange=draw;for(const x of document.querySelectorAll('.strategy-toggle'))x.onchange=draw;priceCanvas.onwheel=e=>{e.preventDefault();const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-68)/Math.max(1,r.width-90),0,1);zoom(e.deltaY>0?1.2:.82,viewStart+q*(viewEnd-viewStart))};priceCanvas.onpointerdown=e=>{dragging=true;dragX=e.clientX;dragStart=viewStart;priceCanvas.setPointerCapture(e.pointerId)};priceCanvas.onpointerup=e=>{dragging=false;if(priceCanvas.hasPointerCapture(e.pointerId))priceCanvas.releasePointerCapture(e.pointerId)};priceCanvas.onpointermove=e=>{if(dragging){const r=priceCanvas.getBoundingClientRect(),shift=-(e.clientX-dragX)/Math.max(1,r.width-90)*(viewEnd-viewStart),span=viewEnd-viewStart;viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw();return}const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-68)/Math.max(1,r.width-90),0,1);hoverT=viewStart+q*(viewEnd-viewStart);const c=candles.reduce((a,b)=>Math.abs(b.t+DAY/2-hoverT)<Math.abs(a.t+DAY/2-hoverT)?b:a,candles[0]),near=trades.filter(t=>activeStrategies().has(t.strategy)&&Math.min(Math.abs(t.entryT-hoverT),Math.abs(t.exitT-hoverT))<DAY*.65),sg=signals.filter(s=>Math.abs(s.t+DAY/2-hoverT)<DAY*.55);let s=`${day(c.t)} UTC\nO ${fmt(c.o)} H ${fmt(c.h)} L ${fmt(c.l)} C ${fmt(c.c)}\nSMA7 ${fmt(c.ma7)} · slope/ATR ${signed(c.slopeAtr,4)}`;for(const z of sg)s+=`\n${z.id} ${z.side==='long'?'多':'空'} · ML概率 ${fmt(z.probability,3)} · ${z.accepted?'接受':'拒绝'}`;for(const t of near)s+=`\n${t.id} ${t.strategyLabel} · ${signed(t.netReturnPct)}%`;for(const k of activeStrategies()){const ep=equity[k].reduce((a,b)=>Math.abs(b.t-hoverT)<Math.abs(a.t-hoverT)?b:a,equity[k][0]);s+=`\n${DATA.strategies[k].code} equity ${fmt(ep.v,4)}`}tooltip.textContent=s;tooltip.style.display='block';tooltip.style.left=Math.min(innerWidth-505,e.clientX+15)+'px';tooltip.style.top=Math.min(innerHeight-210,e.clientY+15)+'px';draw()};priceCanvas.onpointerleave=()=>{if(!dragging){hoverT=null;tooltip.style.display='none';draw()}};priceCanvas.ondblclick=reset;window.onresize=draw;renderMetrics();renderTable();draw();
</script></body></html>'''


def main() -> None:
    args = parse_args()
    outputs = (OUTPUT_PATH, MANIFEST_PATH, Path(f"{OUTPUT_PATH}.sha256"))
    if any(path.exists() for path in outputs) and not args.force:
        raise RuntimeError(f"trade-path artifact exists: {OUTPUT_PATH.name}; use --force")
    payload, manifest = build_payload()
    html = HTML_TEMPLATE.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
    )
    if "__PAYLOAD__" in html:
        raise RuntimeError("template placeholder remains")
    if html.count("ctx.lineTo(x2,y2)") != 1:
        raise RuntimeError("trade line-rendering path missing or duplicated")
    if "'ma7',C.ma" not in html or "setPointerCapture" not in html:
        raise RuntimeError("SMA7 rendering or pointer pan missing")
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    manifest["html"] = OUTPUT_PATH.name
    manifest["html_sha256"] = sha256(OUTPUT_PATH)
    manifest["html_bytes"] = OUTPUT_PATH.stat().st_size
    manifest["renderer_sha256"] = sha256(Path(__file__).resolve())
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    for path in (OUTPUT_PATH, MANIFEST_PATH):
        Path(f"{path}.sha256").write_text(
            f"{sha256(path)}  {path.name}\n", encoding="utf-8"
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
