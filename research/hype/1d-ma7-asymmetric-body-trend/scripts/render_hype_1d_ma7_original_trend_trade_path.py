from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
LABELS = (
    "A_CORE",
    "B_SHORT_RSI_EXIT",
    "C_OVERBOUGHT_REVERSAL",
    "D_BOTH_RSI",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render original MA7 trade paths.")
    parser.add_argument("--run-date", default="2026-08-09")
    return parser.parse_args()


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1_000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def build_payload(run_date: str) -> dict[str, Any]:
    prefix = ARTIFACT_DIR / f"hype_1d_ma7_original_trend_{run_date}"
    summary_path = Path(f"{prefix}_summary.json")
    path_path = Path(f"{prefix}_path.csv")
    trades_path = Path(f"{prefix}_trades.csv")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    paths = pd.read_csv(path_path)
    trades_frame = pd.read_csv(trades_path)
    if tuple(summary["primary"]) != LABELS:
        raise RuntimeError("summary arm order drift")
    if set(paths["label"]) != set(LABELS) or set(trades_frame["label"]) != set(LABELS):
        raise RuntimeError("retained artifacts do not contain all frozen arms")

    reference = paths.loc[paths["label"].eq(LABELS[0])].copy()
    daily = reference.loc[~reference["terminal"].astype(bool)]
    candles = [
        {
            "t": timestamp_ms(row.ts),
            "o": float(row.open),
            "h": float(row.high),
            "l": float(row.low),
            "c": float(row.close),
            "ma": finite_or_none(row.ma7),
            "upper": finite_or_none(row.upper_band),
            "lower": finite_or_none(row.lower_band),
            "rsi": finite_or_none(row.rsi6),
            "slope": finite_or_none(row.slope_atr),
        }
        for row in daily.itertuples(index=False)
    ]

    arms: dict[str, Any] = {}
    all_trade_ids: set[str] = set()
    for label in LABELS:
        arm_path = paths.loc[paths["label"].eq(label)].copy()
        arm_trades = trades_frame.loc[trades_frame["label"].eq(label)].copy()
        if len(arm_trades) != int(summary["primary"][label]["closed_trades"]):
            raise RuntimeError(f"{label}: trade count does not match summary")
        if not arm_path["terminal"].astype(bool).sum() == 1:
            raise RuntimeError(f"{label}: expected exactly one terminal path point")
        final_equity = float(arm_path.iloc[-1]["equity"])
        expected_equity = float(summary["primary"][label]["equity_multiple"])
        if not math.isclose(final_equity, expected_equity, abs_tol=1e-12):
            raise RuntimeError(f"{label}: path and metric equity differ")

        arm_trade_rows = []
        for row in arm_trades.itertuples(index=False):
            trade_id = str(row.trade_id)
            if trade_id in all_trade_ids:
                raise RuntimeError(f"duplicate trade id: {trade_id}")
            all_trade_ids.add(trade_id)
            entry_ts = pd.Timestamp(row.entry_ts)
            exit_ts = pd.Timestamp(row.exit_ts)
            if entry_ts > exit_ts:
                raise RuntimeError(f"{trade_id}: entry occurs after exit")
            arm_trade_rows.append(
                {
                    "id": trade_id,
                    "side": str(row.side),
                    "entryT": timestamp_ms(entry_ts),
                    "exitT": timestamp_ms(exit_ts),
                    "entryTs": entry_ts.isoformat(),
                    "exitTs": exit_ts.isoformat(),
                    "entry": float(row.entry_price),
                    "exit": float(row.exit_price),
                    "days": (exit_ts - entry_ts).total_seconds() / 86_400.0,
                    "reason": str(row.exit_reason),
                    "returnPct": float(row.net_return) * 100.0,
                    "netPnl": float(row.net_pnl),
                    "mfePct": float(row.mfe_return) * 100.0,
                    "maePct": float(row.mae_return) * 100.0,
                    "givebackPct": float(row.giveback_return) * 100.0,
                }
            )
        metrics = summary["primary"][label]
        arms[label] = {
            "metrics": {
                "returnPct": float(metrics["net_return_pct"]),
                "mddPct": float(metrics["max_drawdown_pct"]),
                "sharpe": finite_or_none(metrics["sharpe"]),
                "profitFactor": finite_or_none(metrics["profit_factor"]),
                "trades": int(metrics["closed_trades"]),
                "longTrades": int(metrics["long_trades"]),
                "shortTrades": int(metrics["short_trades"]),
                "shortGivebackPct": finite_or_none(metrics["short_mean_giveback_pct"]),
            },
            "equity": [
                {
                    "t": timestamp_ms(row.ts),
                    "v": float(row.equity),
                    "side": int(row.side),
                    "armed": int(row.armed_side),
                    "terminal": bool(row.terminal),
                }
                for row in arm_path.itertuples(index=False)
            ],
            "trades": arm_trade_rows,
        }

    return {
        "title": "HYPE 1D MA7 原始趋势状态机：完整交易路径",
        "subtitle": (
            "UTC 日线 · researcher-exposed development · "
            "explore / not promoted / not live-ready"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "candles": candles,
        "arms": arms,
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HYPE 1D MA7 原始趋势状态机交易路径</title>
<style>
  :root { color-scheme: dark; --bg:#080b0f; --panel:#0d1218; --panel2:#111820;
    --grid:#202932; --border:#283440; --text:#e9eef3; --muted:#8a99a8;
    --up:#2dd4a7; --down:#f05c70; --ma:#f6c85f; --band:#77889a;
    --long:#36c7ff; --short:#ffad5a; --equity:#a4e65e; --rsi:#bd93f9; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
    font:14px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; }
  .shell { max-width:1900px; margin:0 auto; padding:24px; }
  header { display:grid; grid-template-columns:1fr auto; gap:20px; align-items:end; margin-bottom:18px; }
  h1 { margin:0 0 6px; font:600 24px/1.2 system-ui,sans-serif; }
  .subtitle,.hint { color:var(--muted); font-size:12px; }
  .metrics { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }
  .metric { min-width:112px; padding:9px 11px; border:1px solid var(--border); background:var(--panel); }
  .metric b { display:block; margin-top:2px; font-size:16px; color:var(--text); }
  .toolbar { display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; padding:10px 12px;
    border:1px solid var(--border); border-bottom:0; background:var(--panel2); }
  button,select { color:var(--text); border:1px solid #34414e; background:#151d26;
    padding:6px 10px; cursor:pointer; font:inherit; }
  button:hover,select:hover { border-color:#6d7e8e; }
  label { color:var(--muted); user-select:none; }
  input { vertical-align:-2px; }
  .chart { position:relative; border:1px solid var(--border); background:var(--panel); overflow:hidden; }
  canvas { width:100%; display:block; }
  #priceChart { height:570px; cursor:crosshair; }
  #rsiChart { height:150px; border-top:1px solid var(--border); }
  #equityChart { height:190px; border-top:1px solid var(--border); }
  #tooltip { position:fixed; z-index:10; display:none; pointer-events:none; max-width:410px;
    padding:9px 11px; border:1px solid #465767; background:rgba(8,12,17,.97);
    box-shadow:0 8px 30px rgba(0,0,0,.35); white-space:pre-line; font-size:12px; }
  .hint { padding:8px 12px; border:1px solid var(--border); border-top:0; }
  .table-wrap { margin-top:20px; overflow-x:auto; border:1px solid var(--border); }
  table { width:100%; border-collapse:collapse; min-width:1340px; }
  th,td { padding:8px 10px; border-bottom:1px solid var(--grid); text-align:right; }
  th { color:var(--muted); background:var(--panel2); position:sticky; top:0; }
  th:nth-child(-n+4),td:nth-child(-n+4),th:nth-child(9),td:nth-child(9) { text-align:left; }
  tbody tr { cursor:pointer; }
  tbody tr:hover,tbody tr.active { background:#17212b; }
  .positive,.long { color:var(--up); } .negative,.short { color:var(--down); }
  @media (max-width:900px) { .shell{padding:12px} header{grid-template-columns:1fr}
    .metrics{justify-content:flex-start} #priceChart{height:480px} }
</style>
</head>
<body>
<div class="shell">
  <header><div><h1 id="title"></h1><div class="subtitle" id="subtitle"></div></div>
    <div class="metrics" id="metrics"></div></header>
  <div class="toolbar">
    <label>实验臂 <select id="armSelect"></select></label>
    <button id="reset">完整范围</button><button id="zoomIn">放大</button><button id="zoomOut">缩小</button>
    <label><input id="showMa" type="checkbox" checked> MA7</label>
    <label><input id="showBand" type="checkbox" checked> ±0.75 ATR7</label>
    <label><input id="showTrades" type="checkbox" checked> 交易连线</label>
    <label><input id="showLabels" type="checkbox"> 交易编号</label>
    <span class="long">▲ 多头</span><span class="short">▼ 空头</span>
  </div>
  <div class="chart"><canvas id="priceChart"></canvas><canvas id="rsiChart"></canvas><canvas id="equityChart"></canvas></div>
  <div class="hint">滚轮缩放 · 拖拽平移 · 双击恢复 · 悬停查 K 线/RSI/仓位 · 点击逐笔记录定位</div>
  <div class="table-wrap"><table><thead><tr>
    <th>编号</th><th>方向</th><th>入场 UTC</th><th>出场 UTC</th><th>入场价</th><th>出场价</th>
    <th>持有日</th><th>净收益</th><th>退出原因</th><th>MFE</th><th>MAE</th><th>回吐</th><th>金额 PnL</th>
  </tr></thead><tbody id="tradeRows"></tbody></table></div>
</div><div id="tooltip"></div>
<script>
const DATA=__PAYLOAD__, DAY=86400000;
const COLORS={bg:"#0d1218",bg2:"#0a0f14",grid:"#202932",muted:"#8a99a8",up:"#2dd4a7",
  down:"#f05c70",ma:"#f6c85f",band:"#77889a",long:"#36c7ff",short:"#ffad5a",
  equity:"#a4e65e",rsi:"#bd93f9"};
const candles=DATA.candles, armNames=Object.keys(DATA.arms), priceCanvas=document.getElementById("priceChart"),
  rsiCanvas=document.getElementById("rsiChart"), equityCanvas=document.getElementById("equityChart"),
  tooltip=document.getElementById("tooltip"), rows=document.getElementById("tradeRows");
const domainMin=candles[0].t, domainMax=Math.max(candles[candles.length-1].t+DAY,
  ...armNames.map(k=>DATA.arms[k].equity.at(-1).t));
let armName=armNames[0],viewStart=domainMin,viewEnd=domainMax,hoverT=null,activeTrade=null,
  dragging=false,dragX=0,dragStart=0;
document.getElementById("title").textContent=DATA.title;
document.getElementById("subtitle").textContent=DATA.subtitle;
document.getElementById("armSelect").innerHTML=armNames.map(k=>`<option value="${k}">${k}</option>`).join("");
function arm(){return DATA.arms[armName]} function trades(){return arm().trades} function equity(){return arm().equity}
function signed(v){return(v>=0?"+":"")+v.toFixed(2)} function dt(t){return new Date(t).toISOString().replace(".000Z","Z").replace("T"," ")}
function day(t){return new Date(t).toISOString().slice(0,10)} function fmt(v,d=3){return Number(v).toFixed(d)}
function clamp(v,lo,hi){return Math.max(lo,Math.min(hi,v))}
function setup(c){const r=c.getBoundingClientRect(),d=window.devicePixelRatio||1;c.width=Math.round(r.width*d);
  c.height=Math.round(r.height*d);const x=c.getContext("2d");x.setTransform(d,0,0,d,0,0);return{ctx:x,w:r.width,h:r.height}}
function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}
function visible(){return candles.filter(c=>c.t>=viewStart-DAY&&c.t<=viewEnd+DAY)}
function ticks(lo,hi,n){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,
  step=(q<1.5?1:q<3?2:q<7?5:10)*p,out=[];for(let v=Math.ceil(lo/step)*step;v<=hi+step*.1;v+=step)out.push(v);return out}
function axes(ctx,l,t,w,h,lo,hi,y,time=true){ctx.font="11px ui-monospace";ctx.lineWidth=1;
  for(const v of ticks(lo,hi,5)){const yy=y(v);ctx.strokeStyle=COLORS.grid;ctx.beginPath();ctx.moveTo(l,yy);ctx.lineTo(l+w,yy);ctx.stroke();
    ctx.fillStyle=COLORS.muted;ctx.textAlign="right";ctx.fillText(v.toFixed(Math.abs(v)<10?2:1),l-8,yy+4)}
  if(time)for(let i=0;i<=8;i++){const z=viewStart+(viewEnd-viewStart)*i/8,x=xs(z,l,w);ctx.strokeStyle=COLORS.grid;
    ctx.beginPath();ctx.moveTo(x,t);ctx.lineTo(x,t+h);ctx.stroke();ctx.fillStyle=COLORS.muted;
    ctx.textAlign=i===0?"left":i===8?"right":"center";ctx.fillText(day(z),x,t+h+18)}}
function line(ctx,values,key,color,y,l,w,dash=[]){ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.setLineDash(dash);ctx.beginPath();let on=false;
  for(const p of values){if(p[key]==null){on=false;continue}const x=xs(p.t+DAY/2,l,w),yy=y(p[key]);if(!on){ctx.moveTo(x,yy);on=true}else ctx.lineTo(x,yy)}ctx.stroke();ctx.setLineDash([])}
function marker(ctx,x,y,side,entry,color,size=6){ctx.fillStyle=color;ctx.strokeStyle=COLORS.bg2;ctx.lineWidth=1.5;ctx.beginPath();
  if(entry){if(side==="long"){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{
    ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}
function drawPrice(){const{ctx,w,h}=setup(priceCanvas);ctx.fillStyle=COLORS.bg;ctx.fillRect(0,0,w,h);const m={l:68,r:22,t:22,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=visible();if(!vis.length)return;
  let lo=Math.min(...vis.map(c=>c.l)),hi=Math.max(...vis.map(c=>c.h));for(const c of vis){if(c.lower!=null)lo=Math.min(lo,c.lower);if(c.upper!=null)hi=Math.max(hi,c.upper)}
  const vt=trades().filter(t=>t.exitT>=viewStart&&t.entryT<=viewEnd);for(const t of vt){lo=Math.min(lo,t.entry,t.exit);hi=Math.max(hi,t.entry,t.exit)}
  const p=(hi-lo)*.07||1;lo-=p;hi+=p;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m.l,m.t,pw,ph,lo,hi,y,true);
  const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const c of vis){const x=xs(c.t+DAY/2,m.l,pw),col=c.c>=c.o?COLORS.up:COLORS.down;
    ctx.strokeStyle=col;ctx.beginPath();ctx.moveTo(x,y(c.h));ctx.lineTo(x,y(c.l));ctx.stroke();ctx.fillStyle=col;
    ctx.fillRect(x-bw/2,y(Math.max(c.o,c.c)),bw,Math.max(1,y(Math.min(c.o,c.c))-y(Math.max(c.o,c.c))))}
  if(document.getElementById("showBand").checked){line(ctx,vis,"upper",COLORS.band,y,m.l,pw,[4,4]);line(ctx,vis,"lower",COLORS.band,y,m.l,pw,[4,4])}
  if(document.getElementById("showMa").checked)line(ctx,vis,"ma",COLORS.ma,y,m.l,pw);
  if(document.getElementById("showTrades").checked)for(const t of vt){const hot=activeTrade===t.id,col=t.side==="long"?COLORS.long:COLORS.short,
    x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=col;ctx.globalAlpha=hot?1:.72;
    ctx.lineWidth=hot?3:1.5;ctx.setLineDash(t.returnPct>=0?[]:[5,4]);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
    ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,col,hot?8:6);marker(ctx,x2,y2,t.side,false,col,hot?8:6);
    if(document.getElementById("showLabels").checked||hot){ctx.fillStyle=col;ctx.textAlign="center";ctx.font="10px ui-monospace";
      ctx.fillText(t.id.split("-").at(-1),x1,y1+(t.side==="long"?18:-12));ctx.fillText(t.id.split("-").at(-1),x2,y2-10)}}
  cross(ctx,m,pw,ph);ctx.fillStyle=COLORS.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText("PRICE · HYPEUSDT",m.l,14)}
function cross(ctx,m,pw,ph){if(hoverT==null)return;const x=xs(hoverT,m.l,pw);ctx.strokeStyle=COLORS.muted;ctx.globalAlpha=.65;ctx.setLineDash([3,3]);
  ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}
function drawRsi(){const{ctx,w,h}=setup(rsiCanvas);ctx.fillStyle=COLORS.bg2;ctx.fillRect(0,0,w,h);const m={l:68,r:22,t:16,b:28},pw=w-m.l-m.r,ph=h-m.t-m.b,y=v=>m.t+(100-v)/100*ph;
  axes(ctx,m.l,m.t,pw,ph,0,100,y,false);for(const v of[30,70]){ctx.strokeStyle=v===30?COLORS.up:COLORS.down;ctx.globalAlpha=.55;ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(m.l,y(v));ctx.lineTo(m.l+pw,y(v));ctx.stroke()}ctx.globalAlpha=1;ctx.setLineDash([]);line(ctx,visible(),"rsi",COLORS.rsi,y,m.l,pw);cross(ctx,m,pw,ph);
  ctx.fillStyle=COLORS.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText("RSI6 · 30 / 70",m.l,12)}
function drawEquity(){const{ctx,w,h}=setup(equityCanvas);ctx.fillStyle=COLORS.bg2;ctx.fillRect(0,0,w,h);const m={l:68,r:22,t:18,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,
  vis=equity().filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.v)),hi=Math.max(...vis.map(p=>p.v)),pad=(hi-lo)*.08||.1;
  lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m.l,m.t,pw,ph,lo,hi,y,true);ctx.strokeStyle=COLORS.equity;ctx.lineWidth=2;ctx.beginPath();
  vis.forEach((p,i)=>{const x=xs(p.t,m.l,pw);i?ctx.lineTo(x,y(p.v)):ctx.moveTo(x,y(p.v))});ctx.stroke();cross(ctx,m,pw,ph);
  ctx.fillStyle=COLORS.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText("EQUITY MULTIPLE",m.l,12)}
function metrics(){const m=arm().metrics;document.getElementById("metrics").innerHTML=[["全期净收益",signed(m.returnPct)+"%"],["MDD",m.mddPct.toFixed(2)+"%"],
  ["Sharpe",m.sharpe==null?"—":m.sharpe.toFixed(2)],["PF",m.profitFactor==null?"—":m.profitFactor.toFixed(2)],
  ["交易",`${m.trades}（${m.longTrades}L/${m.shortTrades}S）`],["空头平均回吐",m.shortGivebackPct.toFixed(2)+"%"]]
  .map(([k,v])=>`<div class="metric">${k}<b>${v}</b></div>`).join("")}
function table(){rows.innerHTML=trades().map(t=>`<tr data-id="${t.id}"><td>${t.id.split("-").at(-1)}</td><td class="${t.side}">${t.side==="long"?"做多":"做空"}</td>
  <td>${dt(t.entryT)}</td><td>${dt(t.exitT)}</td><td>${fmt(t.entry)}</td><td>${fmt(t.exit)}</td><td>${fmt(t.days,1)}</td>
  <td class="${t.returnPct>=0?"positive":"negative"}">${signed(t.returnPct)}%</td><td>${t.reason}</td><td>${signed(t.mfePct)}%</td>
  <td>${signed(t.maePct)}%</td><td>${fmt(t.givebackPct,2)}%</td><td class="${t.netPnl>=0?"positive":"negative"}">${signed(t.netPnl)}</td></tr>`).join("");
  for(const r of rows.querySelectorAll("tr")){r.onmouseenter=()=>{activeTrade=r.dataset.id;draw()};r.onmouseleave=()=>{activeTrade=null;draw()};r.onclick=()=>{
    const t=trades().find(x=>x.id===r.dataset.id),span=Math.max(30*DAY,(t.exitT-t.entryT)*2.1),mid=(t.entryT+t.exitT)/2;viewStart=clamp(mid-span/2,domainMin,domainMax-span);
    viewEnd=Math.min(domainMax,viewStart+span);activeTrade=t.id;draw();priceCanvas.scrollIntoView({behavior:"smooth",block:"center"})}}}
function draw(){metrics();drawPrice();drawRsi();drawEquity();for(const r of rows.querySelectorAll("tr"))r.classList.toggle("active",r.dataset.id===activeTrade)}
function reset(){viewStart=domainMin;viewEnd=domainMax;activeTrade=null;draw()} function zoom(f,a=(viewStart+viewEnd)/2){const cur=viewEnd-viewStart,next=clamp(cur*f,14*DAY,domainMax-domainMin),q=(a-viewStart)/cur;
  viewStart=a-next*q;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}
document.getElementById("armSelect").onchange=e=>{armName=e.target.value;activeTrade=null;table();draw()};document.getElementById("reset").onclick=reset;
document.getElementById("zoomIn").onclick=()=>zoom(.65);document.getElementById("zoomOut").onclick=()=>zoom(1.55);
for(const id of["showMa","showBand","showTrades","showLabels"])document.getElementById(id).onchange=draw;
priceCanvas.onwheel=e=>{e.preventDefault();const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-68)/Math.max(1,r.width-90),0,1);zoom(e.deltaY>0?1.2:.82,viewStart+q*(viewEnd-viewStart))};
priceCanvas.onmousedown=e=>{dragging=true;dragX=e.clientX;dragStart=viewStart};window.onmouseup=()=>dragging=false;window.addEventListener("mousemove",e=>{if(!dragging)return;
  const r=priceCanvas.getBoundingClientRect(),shift=-(e.clientX-dragX)/Math.max(1,r.width-90)*(viewEnd-viewStart),span=viewEnd-viewStart;
  viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw()});priceCanvas.ondblclick=reset;
priceCanvas.addEventListener("mousemove",e=>{if(dragging)return;const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-68)/Math.max(1,r.width-90),0,1);
  hoverT=viewStart+q*(viewEnd-viewStart);const c=candles.reduce((a,b)=>Math.abs(b.t+DAY/2-hoverT)<Math.abs(a.t+DAY/2-hoverT)?b:a,candles[0]),
  ep=equity().reduce((a,b)=>Math.abs(b.t-hoverT)<Math.abs(a.t-hoverT)?b:a,equity()[0]),near=trades().filter(t=>Math.min(Math.abs(t.entryT-hoverT),Math.abs(t.exitT-hoverT))<DAY*.65);
  let s=`${day(c.t)} UTC\nO ${fmt(c.o)} H ${fmt(c.h)} L ${fmt(c.l)} C ${fmt(c.c)}\nMA7 ${c.ma==null?"—":fmt(c.ma)} · RSI6 ${c.rsi==null?"—":fmt(c.rsi,1)}\nEquity ${fmt(ep.v,4)} · side ${ep.side} · armed ${ep.armed}`;
  for(const t of near)s+=`\n${t.id} ${t.side==="long"?"多":"空"} ${signed(t.returnPct)}% · ${t.reason}`;tooltip.textContent=s;tooltip.style.display="block";
  tooltip.style.left=Math.min(window.innerWidth-430,e.clientX+16)+"px";tooltip.style.top=Math.min(window.innerHeight-140,e.clientY+16)+"px";draw()});
priceCanvas.onmouseleave=()=>{hoverT=null;tooltip.style.display="none";draw()};window.onresize=draw;table();draw();
</script></body></html>
"""


def main() -> None:
    args = parse_args()
    payload = build_payload(args.run_date)
    output = (
        ARTIFACT_DIR / f"hype_1d_ma7_original_trend_trade_path_{args.run_date}.html"
    )
    html = HTML_TEMPLATE.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    output.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "arms": len(payload["arms"]),
                "trades": sum(len(arm["trades"]) for arm in payload["arms"].values()),
                "bytes": output.stat().st_size,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
