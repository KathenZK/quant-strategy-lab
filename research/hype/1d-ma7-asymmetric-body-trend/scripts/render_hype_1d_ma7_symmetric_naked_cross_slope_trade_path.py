"""Render the frozen SNC02 backtest as a self-contained interactive trade path."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BACKTEST_PATH = SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
SOURCE_PATH = ARTIFACT_DIR / "hype_1d_ma7_symmetric_naked_cross_slope_2026-08-20.json"
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_symmetric_naked_cross_slope_trade_path_2026-08-20.html"
)
MANIFEST_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_symmetric_naked_cross_slope_trade_path_2026-08-20_manifest.json"
)


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


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1_000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_context(backtest: ModuleType) -> Any:
    adapter = backtest.load_module(backtest.ADAPTER_PATH, "snc02_chart_adapter")
    frozen = adapter.load_context()
    original = frozen.original_harness
    original.HOURLY_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    original.FUNDING_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    market = original.load_market(0)
    return SimpleNamespace(
        market=market,
        book=market.book,
        features=market.features,
        engine=frozen.engine,
    )


def canonical_trade(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "side",
            "entry_ts",
            "entry_price",
            "exit_ts",
            "exit_price",
            "exit_reason",
            "entry_leverage",
            "gross_return_pct",
            "net_return_pct",
            "net_pnl",
            "funding_pnl",
            "bars",
        )
    }


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    backtest = load_module(BACKTEST_PATH, "snc02_chart_backtest")
    risk = load_module(RISK_PATH, "snc02_chart_risk")
    context = load_context(backtest)
    metrics, raw, signals, actions = backtest.run_backtest(
        context,
        risk,
        start=0,
        right=context.book.count,
    )
    rebuilt_trades = [canonical_trade(row) for row in raw.trades]
    if rebuilt_trades != source["trades"]:
        raise RuntimeError("rebuilt trade ledger differs from retained machine artifact")
    for key in (
        "net_return_pct",
        "chronological_1h_mdd_pct",
        "closed_trades",
        "win_rate",
        "profit_factor",
    ):
        if not math.isclose(
            float(metrics[key]),
            float(source["extended"][key]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(f"extended metric parity failed: {key}")

    replay = risk.replay_chronological_1h(
        context,
        raw,
        slippage=backtest.BASE_SLIPPAGE,
        include_funding=True,
        retain_points=True,
    )
    enter_actions = {
        str(row["ts"]): row
        for row in actions
        if str(row["action"]).startswith("enter_")
    }
    candles: list[dict[str, Any]] = []
    for index, ts in enumerate(context.book.ts):
        ma7 = finite_or_none(context.features.ma7[index])
        atr7 = finite_or_none(context.features.atr7[index])
        previous_ma7 = (
            finite_or_none(context.features.ma7[index - 1]) if index else None
        )
        slope_atr = (
            (ma7 - previous_ma7) / atr7
            if ma7 is not None
            and previous_ma7 is not None
            and atr7 is not None
            and atr7 > 0.0
            else None
        )
        candles.append(
            {
                "t": timestamp_ms(ts),
                "o": float(context.book.open[index]),
                "h": float(context.book.high[index]),
                "l": float(context.book.low[index]),
                "c": float(context.book.close[index]),
                "ma7": ma7,
                "atr7": atr7,
                "slopeAtr": slope_atr,
            }
        )

    chart_signals = [
        {
            "t": timestamp_ms(row["signal_ts"]),
            "ts": row["signal_ts"],
            "side": row["target_side"],
            "close": float(row["close"]),
            "ma7": float(row["ma7"]),
            "slopeAtr": float(row["slope_atr"]),
            "scheduled": bool(row["scheduled"]),
        }
        for row in signals
    ]
    trades: list[dict[str, Any]] = []
    trade_ids: set[str] = set()
    prior_exit: int | None = None
    for index, row in enumerate(raw.trades, start=1):
        trade_id = f"SNC02-{index:03d}"
        if trade_id in trade_ids:
            raise RuntimeError(f"duplicate trade id: {trade_id}")
        trade_ids.add(trade_id)
        entry_t = timestamp_ms(row["entry_ts"])
        exit_t = timestamp_ms(row["exit_ts"])
        if entry_t > exit_t:
            raise RuntimeError(f"{trade_id}: entry occurs after exit")
        action = enter_actions.get(str(row["entry_ts"]))
        if action is None:
            raise RuntimeError(f"{trade_id}: missing retained entry action")
        terminal = str(row["exit_reason"]) == "terminal_flatten"
        trades.append(
            {
                "id": trade_id,
                "side": str(row["side"]),
                "signalT": timestamp_ms(action["signal_ts"]),
                "signalTs": str(action["signal_ts"]),
                "entryT": entry_t,
                "entryTs": str(row["entry_ts"]),
                "entry": float(row["entry_price"]),
                "exitT": exit_t,
                "exitTs": str(row["exit_ts"]),
                "exit": float(row["exit_price"]),
                "days": float(row["bars"]),
                "grossReturnPct": float(row["gross_return_pct"]),
                "netReturnPct": float(row["net_return_pct"]),
                "netPnl": float(row["net_pnl"]),
                "fundingPnl": float(row["funding_pnl"]),
                "exitReason": (
                    "数据终点盯市（非策略退出）"
                    if terminal
                    else "镜像合格信号翻仓"
                ),
                "terminalCensored": terminal,
                "forcedReversal": prior_exit == entry_t,
            }
        )
        prior_exit = exit_t

    equity = [
        {
            "t": timestamp_ms(point.ts),
            "v": float(point.equity),
            "kind": point.kind,
            "side": int(point.side),
        }
        for point in replay.points
    ]
    payload = {
        "title": "HYPE 1D MA7 SNC02 裸策略：完整交易路径",
        "subtitle": (
            "UTC日线 · fresh cross + 1日SMA7斜率≥0.02ATR7 · "
            "次日开盘成交 · 仅镜像合格信号翻仓"
        ),
        "status": "独立signal-core诊断 · explore / not promoted / not live-ready",
        "generatedAt": datetime.now(UTC).isoformat(),
        "window": {
            "start": metrics["start_ts"],
            "end": metrics["end_ts"],
        },
        "metrics": {
            "returnPct": float(metrics["net_return_pct"]),
            "mddPct": float(metrics["chronological_1h_mdd_pct"]),
            "winRatePct": float(metrics["win_rate"]) * 100.0,
            "profitFactor": float(metrics["profit_factor"]),
            "trades": int(metrics["closed_trades"]),
            "longTrades": int(metrics["long_trades"]),
            "shortTrades": int(metrics["short_trades"]),
            "exposurePct": float(metrics["exposure_pct"]),
        },
        "candles": candles,
        "signals": chart_signals,
        "equity": equity,
        "trades": trades,
    }
    manifest = {
        "schema": "hype-1d-ma7-snc02-trade-path-manifest-v1",
        "generated_at": payload["generatedAt"],
        "source_artifact": SOURCE_PATH.name,
        "source_artifact_sha256": sha256(SOURCE_PATH),
        "renderer": Path(__file__).name,
        "renderer_sha256": sha256(Path(__file__).resolve()),
        "window": payload["window"],
        "candles": len(candles),
        "signals": len(chart_signals),
        "equity_points": len(equity),
        "closed_trades": len(trades),
        "unique_trade_ids": len(trade_ids) == len(trades),
        "entry_lte_exit": all(row["entryT"] <= row["exitT"] for row in trades),
        "complete_endpoints": all(
            row["entry"] > 0.0 and row["exit"] > 0.0 for row in trades
        ),
        "line_render_count": len(trades),
        "forced_reversals": sum(row["forcedReversal"] for row in trades),
        "terminal_censored": sum(row["terminalCensored"] for row in trades),
        "metric_parity": True,
        "trade_ledger_parity": True,
        "external_dependencies": 0,
    }
    return payload, manifest


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HYPE 1D MA7 SNC02 裸策略交易路径</title>
<style>
:root{color-scheme:dark;--bg:#080b0e;--panel:#0d1217;--panel2:#111820;--line:#27333e;--grid:#1d2730;--text:#e9eef2;--muted:#8998a5;--up:#27d3a2;--down:#f16072;--ma:#f5c95f;--long:#36c7ff;--short:#ffad5a;--equity:#a2e65c;--slope:#b69cff;--threshold:#6f7e8b;--signal:#f3f6f8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}.shell{max-width:1900px;margin:auto;padding:24px}header{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:end;margin-bottom:16px}h1{margin:0 0 6px;font:620 24px/1.2 system-ui,sans-serif}.subtitle,.status,.hint{color:var(--muted);font-size:12px}.status{margin-top:4px}.metrics{display:flex;flex-wrap:wrap;gap:7px;justify-content:flex-end}.metric{min-width:110px;padding:8px 10px;border:1px solid var(--line);background:var(--panel)}.metric b{display:block;margin-top:2px;font-size:15px}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:9px 12px;border:1px solid var(--line);border-bottom:0;background:var(--panel2)}button{color:var(--text);border:1px solid #344450;background:#151e27;padding:6px 10px;cursor:pointer;font:inherit}button:hover{border-color:#708292}label{color:var(--muted);user-select:none}input{vertical-align:-2px}.long{color:var(--long)}.short{color:var(--short)}.chart{border:1px solid var(--line);background:var(--panel);overflow:hidden}canvas{width:100%;display:block}#priceChart{height:570px;cursor:crosshair}#slopeChart{height:145px;border-top:1px solid var(--line)}#equityChart{height:190px;border-top:1px solid var(--line)}.hint{padding:8px 12px;border:1px solid var(--line);border-top:0}.table-wrap{margin-top:20px;overflow:auto;max-height:580px;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;min-width:1350px}th,td{padding:8px 10px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}th{color:var(--muted);background:var(--panel2);position:sticky;top:0;z-index:1}th:nth-child(-n+5),td:nth-child(-n+5),th:nth-child(10),td:nth-child(10){text-align:left}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#17222b}.positive{color:var(--up)}.negative{color:var(--down)}#tooltip{position:fixed;z-index:10;display:none;pointer-events:none;max-width:440px;padding:9px 11px;border:1px solid #465966;background:rgba(8,12,16,.97);box-shadow:0 8px 28px rgba(0,0,0,.4);white-space:pre-line;font-size:12px}@media(max-width:900px){.shell{padding:12px}header{grid-template-columns:1fr}.metrics{justify-content:flex-start}#priceChart{height:470px}}
</style>
</head>
<body><div class="shell">
<header><div><h1 id="title"></h1><div class="subtitle" id="subtitle"></div><div class="status" id="status"></div></div><div class="metrics" id="metrics"></div></header>
<div class="toolbar"><button id="reset">完整范围</button><button id="zoomIn">放大</button><button id="zoomOut">缩小</button><label><input id="showMa" type="checkbox" checked>SMA7</label><label><input id="showSignals" type="checkbox" checked>合格信号</label><label><input id="showTrades" type="checkbox" checked>交易连线</label><label><input id="showLabels" type="checkbox">交易编号</label><span class="long">▲ 多头</span><span class="short">▼ 空头</span></div>
<div class="chart"><canvas id="priceChart"></canvas><canvas id="slopeChart"></canvas><canvas id="equityChart"></canvas></div>
<div class="hint">滚轮缩放 · 拖拽平移 · 双击恢复 · 悬停查看K线/斜率/权益 · 点击逐笔记录聚焦；虚线交易连线代表亏损，最后一笔空心终点为盯市而非策略退出</div>
<div class="table-wrap"><table><thead><tr><th>编号</th><th>方向</th><th>信号日 UTC</th><th>入场 UTC</th><th>出场/终点 UTC</th><th>入场价</th><th>出场/盯市价</th><th>持有日</th><th>净收益</th><th>退出说明</th><th>毛收益</th><th>Funding PnL</th><th>金额 PnL</th></tr></thead><tbody id="tradeRows"></tbody></table></div>
</div><div id="tooltip"></div><script>
const DATA=__PAYLOAD__,DAY=86400000,C={bg:"#0d1217",bg2:"#0a0f14",grid:"#1d2730",muted:"#8998a5",up:"#27d3a2",down:"#f16072",ma:"#f5c95f",long:"#36c7ff",short:"#ffad5a",equity:"#a2e65c",slope:"#b69cff",threshold:"#6f7e8b",signal:"#f3f6f8"};
const candles=DATA.candles,trades=DATA.trades,signals=DATA.signals,equity=DATA.equity,priceCanvas=$("priceChart"),slopeCanvas=$("slopeChart"),equityCanvas=$("equityChart"),tooltip=$("tooltip"),rows=$("tradeRows");
const domainMin=candles[0].t,domainMax=Math.max(candles.at(-1).t+DAY,equity.at(-1).t);let viewStart=domainMin,viewEnd=domainMax,hoverT=null,activeTrade=null,dragging=false,dragX=0,dragStart=0;
function $(id){return document.getElementById(id)}function signed(v,d=2){return(v>=0?"+":"")+Number(v).toFixed(d)}function fmt(v,d=3){return Number(v).toFixed(d)}function dt(t){return new Date(t).toISOString().replace(".000Z","Z").replace("T"," ")}function day(t){return new Date(t).toISOString().slice(0,10)}function clamp(v,lo,hi){return Math.max(lo,Math.min(hi,v))}
function setup(c){const r=c.getBoundingClientRect(),d=window.devicePixelRatio||1;c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);const x=c.getContext("2d");x.setTransform(d,0,0,d,0,0);return{ctx:x,w:r.width,h:r.height}}
function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}function vc(){return candles.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}function ve(){return equity.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}function vt(){return trades.filter(p=>p.exitT>=viewStart&&p.entryT<=viewEnd)}
function ticks(lo,hi,n){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,step=(q<1.5?1:q<3?2:q<7?5:10)*p,out=[];for(let v=Math.ceil(lo/step)*step;v<=hi+step*.1;v+=step)out.push(v);return out}
function axes(ctx,m,pw,ph,lo,hi,y,time=true){ctx.font="11px ui-monospace";ctx.lineWidth=1;for(const v of ticks(lo,hi,5)){const yy=y(v);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign="right";ctx.fillText(v.toFixed(Math.abs(v)<10?2:1),m.l-8,yy+4)}if(time)for(let i=0;i<=8;i++){const z=viewStart+(viewEnd-viewStart)*i/8,x=xs(z,m.l,pw);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign=i===0?"left":i===8?"right":"center";ctx.fillText(day(z),x,m.t+ph+18)}}
function line(ctx,values,key,color,y,l,w,dash=[]){ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.setLineDash(dash);ctx.beginPath();let on=false;for(const p of values){if(p[key]==null){on=false;continue}const x=xs(p.t+DAY/2,l,w),yy=y(p[key]);on?ctx.lineTo(x,yy):(ctx.moveTo(x,yy),on=true)}ctx.stroke();ctx.setLineDash([])}
function marker(ctx,x,y,side,entry,color,size=6,terminal=false){ctx.fillStyle=terminal?C.bg2:color;ctx.strokeStyle=color;ctx.lineWidth=terminal?2.5:1.5;ctx.beginPath();if(entry){if(side==="long"){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}
function cross(ctx,m,pw,ph){if(hoverT==null)return;const x=xs(hoverT,m.l,pw);ctx.strokeStyle=C.muted;ctx.globalAlpha=.6;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}
function drawPrice(){const{ctx,w,h}=setup(priceCanvas),m={l:68,r:22,t:22,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=vc();ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.l)),hi=Math.max(...vis.map(p=>p.h));for(const t of vt()){lo=Math.min(lo,t.entry,t.exit);hi=Math.max(hi,t.entry,t.exit)}const pad=(hi-lo)*.07||1;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,true);const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const p of vis){const x=xs(p.t+DAY/2,m.l,pw),col=p.c>=p.o?C.up:C.down;ctx.strokeStyle=col;ctx.beginPath();ctx.moveTo(x,y(p.h));ctx.lineTo(x,y(p.l));ctx.stroke();ctx.fillStyle=col;ctx.fillRect(x-bw/2,y(Math.max(p.o,p.c)),bw,Math.max(1,y(Math.min(p.o,p.c))-y(Math.max(p.o,p.c))))}if($("showMa").checked)line(ctx,vis,"ma7",C.ma,y,m.l,pw);if($("showSignals").checked)for(const s of signals.filter(s=>s.t>=viewStart&&s.t<=viewEnd)){const x=xs(s.t+DAY/2,m.l,pw),yy=y(s.close),col=s.side==="long"?C.long:C.short;ctx.save();ctx.translate(x,yy);ctx.rotate(Math.PI/4);ctx.fillStyle=C.bg2;ctx.strokeStyle=col;ctx.lineWidth=2;ctx.fillRect(-4,-4,8,8);ctx.strokeRect(-4,-4,8,8);ctx.restore()}if($("showTrades").checked)for(const t of vt()){const hot=t.id===activeTrade,col=t.side==="long"?C.long:C.short,x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=col;ctx.globalAlpha=hot?1:.75;ctx.lineWidth=hot?3:1.6;ctx.setLineDash(t.netReturnPct>=0?[]:[5,4]);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,col,hot?8:6);marker(ctx,x2,y2,t.side,false,col,hot?8:6,t.terminalCensored);if($("showLabels").checked||hot){ctx.fillStyle=col;ctx.textAlign="center";ctx.font="10px ui-monospace";const n=t.id.split("-").at(-1);ctx.fillText(n,x1,y1+(t.side==="long"?19:-12));ctx.fillText(t.terminalCensored?n+" · 盯市":n,x2,y2-10)}}cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText("PRICE · HYPEUSDT · SMA7",m.l,14)}
function drawSlope(){const{ctx,w,h}=setup(slopeCanvas),m={l:68,r:22,t:18,b:28},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=vc();ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(-.04,...vis.map(p=>p.slopeAtr??0)),hi=Math.max(.04,...vis.map(p=>p.slopeAtr??0)),pad=(hi-lo)*.08;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,false);for(const v of[-.02,.02]){ctx.strokeStyle=C.threshold;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(m.l,y(v));ctx.lineTo(m.l+pw,y(v));ctx.stroke()}ctx.setLineDash([]);line(ctx,vis,"slopeAtr",C.slope,y,m.l,pw);cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText("SMA7 1D SLOPE / ATR7 · 阈值 ±0.02",m.l,12)}
function drawEquity(){const{ctx,w,h}=setup(equityCanvas),m={l:68,r:22,t:18,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=ve();ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.v)),hi=Math.max(...vis.map(p=>p.v)),pad=(hi-lo)*.08||.1;lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,true);ctx.strokeStyle=C.equity;ctx.lineWidth=1.7;ctx.beginPath();vis.forEach((p,i)=>{const x=xs(p.t,m.l,pw);i?ctx.lineTo(x,y(p.v)):ctx.moveTo(x,y(p.v))});ctx.stroke();cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText("1H MARK-TO-MARKET EQUITY",m.l,12)}
function draw(){drawPrice();drawSlope();drawEquity();for(const r of rows.querySelectorAll("tr"))r.classList.toggle("active",r.dataset.id===activeTrade)}function reset(){viewStart=domainMin;viewEnd=domainMax;activeTrade=null;draw()}function zoom(f,a=(viewStart+viewEnd)/2){const cur=viewEnd-viewStart,next=clamp(cur*f,14*DAY,domainMax-domainMin),q=(a-viewStart)/cur;viewStart=a-next*q;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}
function renderMetrics(){const m=DATA.metrics;$("metrics").innerHTML=[["全期净收益",signed(m.returnPct)+"%"],["真实1h MDD",signed(m.mddPct)+"%"],["胜率",fmt(m.winRatePct,2)+"%"],["PF",fmt(m.profitFactor,3)],["交易",`${m.trades}（${m.longTrades}L/${m.shortTrades}S）`],["暴露率",fmt(m.exposurePct,2)+"%"]].map(([k,v])=>`<div class="metric">${k}<b>${v}</b></div>`).join("")}
function renderTable(){rows.innerHTML=trades.map(t=>`<tr data-id="${t.id}"><td>${t.id}</td><td class="${t.side}">${t.side==="long"?"做多":"做空"}</td><td>${dt(t.signalT)}</td><td>${dt(t.entryT)}</td><td>${dt(t.exitT)}</td><td>${fmt(t.entry)}</td><td>${fmt(t.exit)}</td><td>${fmt(t.days,1)}</td><td class="${t.netReturnPct>=0?"positive":"negative"}">${signed(t.netReturnPct)}%</td><td>${t.exitReason}</td><td>${signed(t.grossReturnPct)}%</td><td class="${t.fundingPnl>=0?"positive":"negative"}">${signed(t.fundingPnl,4)}</td><td class="${t.netPnl>=0?"positive":"negative"}">${signed(t.netPnl,4)}</td></tr>`).join("");for(const r of rows.querySelectorAll("tr")){r.onmouseenter=()=>{activeTrade=r.dataset.id;draw()};r.onmouseleave=()=>{activeTrade=null;draw()};r.onclick=()=>{const t=trades.find(x=>x.id===r.dataset.id),span=Math.max(24*DAY,(t.exitT-t.entryT)*2.1),mid=(t.entryT+t.exitT)/2;viewStart=clamp(mid-span/2,domainMin,Math.max(domainMin,domainMax-span));viewEnd=Math.min(domainMax,viewStart+span);activeTrade=t.id;draw();priceCanvas.scrollIntoView({behavior:"smooth",block:"center"})}}}
$("title").textContent=DATA.title;$("subtitle").textContent=DATA.subtitle;$("status").textContent=`${DATA.status} · ${DATA.window.start.slice(0,10)} → ${DATA.window.end.slice(0,10)}`;$("reset").onclick=reset;$("zoomIn").onclick=()=>zoom(.65);$("zoomOut").onclick=()=>zoom(1.55);for(const id of["showMa","showSignals","showTrades","showLabels"])$(id).onchange=draw;priceCanvas.onwheel=e=>{e.preventDefault();const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-68)/Math.max(1,r.width-90),0,1);zoom(e.deltaY>0?1.2:.82,viewStart+q*(viewEnd-viewStart))};priceCanvas.onmousedown=e=>{dragging=true;dragX=e.clientX;dragStart=viewStart};window.addEventListener("mouseup",()=>dragging=false);window.addEventListener("mousemove",e=>{if(!dragging)return;const r=priceCanvas.getBoundingClientRect(),shift=-(e.clientX-dragX)/Math.max(1,r.width-90)*(viewEnd-viewStart),span=viewEnd-viewStart;viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw()});priceCanvas.ondblclick=reset;
priceCanvas.addEventListener("mousemove",e=>{if(dragging)return;const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-68)/Math.max(1,r.width-90),0,1);hoverT=viewStart+q*(viewEnd-viewStart);const c=candles.reduce((a,b)=>Math.abs(b.t+DAY/2-hoverT)<Math.abs(a.t+DAY/2-hoverT)?b:a,candles[0]),ep=equity.reduce((a,b)=>Math.abs(b.t-hoverT)<Math.abs(a.t-hoverT)?b:a,equity[0]),near=trades.filter(t=>Math.min(Math.abs(t.entryT-hoverT),Math.abs(t.exitT-hoverT))<DAY*.65),sg=signals.filter(s=>Math.abs(s.t+DAY/2-hoverT)<DAY*.55);let s=`${day(c.t)} UTC\nO ${fmt(c.o)} H ${fmt(c.h)} L ${fmt(c.l)} C ${fmt(c.c)}\nSMA7 ${c.ma7==null?"—":fmt(c.ma7)} · slope/ATR ${c.slopeAtr==null?"—":signed(c.slopeAtr,4)}\nEquity ${fmt(ep.v,4)} · side ${ep.side}`;for(const z of sg)s+=`\n合格${z.side==="long"?"多":"空"}信号 · slope ${signed(z.slopeAtr,4)}`;for(const t of near)s+=`\n${t.id} ${t.side==="long"?"多":"空"} ${signed(t.netReturnPct)}% · ${t.exitReason}`;tooltip.textContent=s;tooltip.style.display="block";tooltip.style.left=Math.min(window.innerWidth-455,e.clientX+16)+"px";tooltip.style.top=Math.min(window.innerHeight-170,e.clientY+16)+"px";draw()});priceCanvas.onmouseleave=()=>{hoverT=null;tooltip.style.display="none";draw()};window.onresize=draw;renderMetrics();renderTable();draw();
</script></body></html>"""


def main() -> None:
    args = parse_args()
    outputs = (OUTPUT_PATH, MANIFEST_PATH, Path(f"{OUTPUT_PATH}.sha256"))
    if any(path.exists() for path in outputs) and not args.force:
        raise RuntimeError(f"locked trade-path artifact exists: {OUTPUT_PATH.name}")
    payload, manifest = build_payload()
    html = HTML_TEMPLATE.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    if "__PAYLOAD__" in html or "__" + "PLACEHOLDER__" in html:
        raise RuntimeError("template placeholder remains")
    if html.count("ctx.lineTo(x2,y2)") != 1:
        raise RuntimeError("trade line-rendering path missing or duplicated")
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    manifest["html"] = OUTPUT_PATH.name
    manifest["html_sha256"] = sha256(OUTPUT_PATH)
    manifest["html_bytes"] = OUTPUT_PATH.stat().st_size
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(f"{OUTPUT_PATH}.sha256").write_text(
        f"{manifest['html_sha256']}  {OUTPUT_PATH.name}\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
