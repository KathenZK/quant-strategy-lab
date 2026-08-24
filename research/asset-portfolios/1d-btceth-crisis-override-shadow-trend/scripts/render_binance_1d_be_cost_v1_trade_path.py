from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-crisis-override-shadow-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATA_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
START = pd.Timestamp("2019-12-24T00:00:00Z")
END = pd.Timestamp("2025-08-07T00:00:00Z")


def daily_market(slug: str) -> list[list[float | int | None]]:
    hourly = pd.read_parquet(
        DATA_DIR / f"{slug}_perp_1h.parquet",
        columns=["ts", "open", "high", "low", "close"],
    )
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    hourly = hourly.loc[hourly["ts"].ge(START) & hourly["ts"].lt(END)].copy()
    hourly["day"] = hourly["ts"].dt.floor("1D")
    daily = hourly.groupby("day", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        hours=("ts", "size"),
    )
    expected_days = pd.date_range(START, END, inclusive="left", freq="1D")
    if not daily.index.equals(expected_days):
        missing = expected_days.difference(daily.index).tolist()
        extra = daily.index.difference(expected_days).tolist()
        raise RuntimeError(
            f"daily candle index mismatch: missing={missing[:5]}, extra={extra[:5]}"
        )
    if not daily["hours"].eq(24).all():
        bad = daily.index[~daily["hours"].eq(24)].tolist()
        raise RuntimeError(f"incomplete daily candles: {bad[:5]}")
    daily["ema50"] = daily["close"].ewm(
        span=50, adjust=False, min_periods=50
    ).mean()
    output: list[list[float | int | None]] = []
    for timestamp, row in daily.iterrows():
        ema = None if pd.isna(row["ema50"]) else round(float(row["ema50"]), 8)
        output.append(
            [
                int(timestamp.timestamp() * 1000),
                round(float(row["open"]), 8),
                round(float(row["high"]), 8),
                round(float(row["low"]), 8),
                round(float(row["close"]), 8),
                ema,
            ]
        )
    return output


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def build_payload(source_date: str) -> dict[str, Any]:
    stem = ARTIFACT_DIR / f"binance_1d_be_cost_p0_{source_date}"
    path = pd.read_csv(f"{stem}_paths.csv", parse_dates=["ts"])
    trades = pd.read_csv(
        f"{stem}_trades.csv", parse_dates=["entry_ts", "exit_ts"]
    )
    legs = pd.read_csv(
        f"{stem}_crisis_legs.csv", parse_dates=["entry_ts", "exit_ts"]
    )
    machine = json.loads(Path(f"{stem}.json").read_text(encoding="utf-8"))
    path = path.loc[path["frontier"].eq("growth_frontier")].copy()
    trades = trades.loc[trades["frontier"].eq("growth_frontier")].copy()
    legs = legs.loc[legs["frontier"].eq("growth_frontier")].copy()
    trades = trades.sort_values(["entry_ts", "exit_ts", "mode"]).reset_index(drop=True)

    account_trades: list[dict[str, Any]] = []
    line_paths: list[dict[str, Any]] = []
    for index, trade in trades.iterrows():
        trade_id = f"T{index + 1:03d}"
        entry_ms = timestamp_ms(trade["entry_ts"])
        exit_ms = timestamp_ms(trade["exit_ts"])
        if entry_ms > exit_ms:
            raise RuntimeError(f"invalid trade interval: {trade_id}")
        account = {
            "id": trade_id,
            "mode": str(trade["mode"]),
            "asset": str(trade["asset"]),
            "side": int(trade["side"]),
            "entry": entry_ms,
            "exit": exit_ms,
            "reason": str(trade["exit_reason"]),
            "logGrowth": round(float(trade["trade_log_growth"]), 8),
        }
        account_trades.append(account)
        if trade["mode"] == "base":
            line_paths.append(
                {
                    "tradeId": trade_id,
                    "mode": "base",
                    "asset": str(trade["asset"]),
                    "side": int(trade["side"]),
                    "entry": entry_ms,
                    "exit": exit_ms,
                    "entryPrice": round(float(trade["entry_price"]), 8),
                    "exitPrice": round(float(trade["exit_price"]), 8),
                    "reason": str(trade["exit_reason"]),
                }
            )
        else:
            matched = legs.loc[
                legs["entry_ts"].eq(trade["entry_ts"])
                & legs["exit_ts"].eq(trade["exit_ts"])
            ].sort_values("asset")
            if len(matched) != 2 or set(matched["asset"]) != {
                "BTCUSDT",
                "ETHUSDT",
            }:
                raise RuntimeError(f"crisis legs missing for {trade_id}")
            for _, leg in matched.iterrows():
                line_paths.append(
                    {
                        "tradeId": trade_id,
                        "mode": "crisis",
                        "asset": str(leg["asset"]),
                        "side": -1,
                        "entry": entry_ms,
                        "exit": exit_ms,
                        "entryPrice": round(float(leg["entry_price"]), 8),
                        "exitPrice": round(float(leg["exit_price"]), 8),
                        "reason": "crisis_state_exit",
                    }
                )

    if len(account_trades) != int(machine["best_growth"]["trades"]):
        raise RuntimeError("account trade count does not match frozen metrics")
    if len({row["id"] for row in account_trades}) != len(account_trades):
        raise RuntimeError("duplicate trade ids")
    if len(line_paths) != 30:
        raise RuntimeError(f"unexpected routed leg count: {len(line_paths)}")
    if {row["tradeId"] for row in line_paths} != {
        row["id"] for row in account_trades
    }:
        raise RuntimeError("not every account trade enters the line-rendering path")

    equity = [
        [timestamp_ms(row.ts), round(float(row.equity), 10)]
        for row in path.itertuples(index=False)
    ]
    crisis_periods = [
        {
            "tradeId": trade["id"],
            "start": trade["entry"],
            "end": trade["exit"],
        }
        for trade in account_trades
        if trade["mode"] == "crisis"
    ]
    if len(crisis_periods) != int(machine["best_growth"]["crisis_episodes"]):
        raise RuntimeError("crisis episode count does not match frozen metrics")
    return {
        "version": "BIN-1D-BE-COST-V1",
        "status": "registered / not promoted / not live-ready",
        "window": [timestamp_ms(START), timestamp_ms(END)],
        "metrics": {
            "equityMultiple": round(
                float(machine["best_growth"]["equity_multiple"]), 6
            ),
            "orderedMddPct": round(
                float(machine["best_growth"]["ordered_mdd_pct"]), 4
            ),
            "accountTrades": len(account_trades),
            "routedLegs": len(line_paths),
            "crisisEpisodes": int(machine["best_growth"]["crisis_episodes"]),
        },
        "parameters": {
            "cbct": "entry20 / exit10 / EMA50 / trail5ATR / confirm2 / cooldown7 / maxhold120",
            "profitProtection": "activation1ATR / giveback35% / confirm2d",
            "crisis": "EMA200 / slope60d / confirm3d / BTC50%+ETH50% short",
        },
        "btc": daily_market("btcusdt"),
        "eth": daily_market("ethusdt"),
        "equity": equity,
        "trades": account_trades,
        "lines": line_paths,
        "crisisPeriods": crisis_periods,
    }


def html_document(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BIN-1D-BE-COST-V1 完整交易路径</title>
<style>
:root{color-scheme:dark;--bg:#0b0f14;--panel:#111821;--line:#273341;--text:#e9eef4;--muted:#91a0af;--up:#2fca8c;--down:#ff6670;--ema:#f4bd50;--crisis:#ff9b42;--equity:#62a9ff;--focus:#f6e27f}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:18px 22px 14px;border-bottom:1px solid var(--line);display:flex;gap:24px;align-items:flex-end;justify-content:space-between;flex-wrap:wrap}h1{font-size:20px;margin:0 0 5px}.sub{color:var(--muted)}.metrics{display:flex;gap:18px;flex-wrap:wrap}.metric b{display:block;font-size:17px}.metric span{color:var(--muted);font-size:11px}.toolbar{padding:9px 18px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:center;flex-wrap:wrap;position:sticky;top:0;background:rgba(11,15,20,.96);z-index:5}.toolbar button{background:transparent;color:var(--text);border:1px solid var(--line);padding:6px 10px;cursor:pointer}.toolbar button[aria-pressed="false"]{color:var(--muted)}.legend{display:flex;gap:14px;color:var(--muted);flex-wrap:wrap}.sw{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:5px}.chart-wrap{position:relative;padding:10px 12px 0}#chart{display:block;width:100%;height:860px;background:var(--panel);border:1px solid var(--line)}#tooltip{position:absolute;display:none;pointer-events:none;background:#0b1118;border:1px solid #435063;padding:8px 10px;white-space:nowrap;z-index:4;color:var(--text);font-variant-numeric:tabular-nums}.hint{padding:5px 18px 12px;color:var(--muted)}.table-wrap{padding:0 18px 28px;overflow:auto}table{width:100%;border-collapse:collapse;min-width:970px;font-variant-numeric:tabular-nums}caption{text-align:left;font-weight:700;font-size:15px;padding:12px 0}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}th{color:var(--muted);font-weight:600}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#18222d}.long{color:var(--up)}.short{color:var(--down)}.crisis{color:var(--crisis)}@media(max-width:720px){header{padding:14px}.metrics{gap:10px}.chart-wrap{padding:6px}#chart{height:760px}.toolbar{padding:8px}.table-wrap{padding:0 8px 20px}}
</style>
</head>
<body>
<header><div><h1>BIN-1D-BE-COST-V1 · 完整交易路径</h1><div class="sub">BTCUSDT / ETHUSDT 日K、各自 EMA50、账户权益、全部入场—出场连线与危机双空区间｜UTC</div></div><div class="metrics" id="metrics"></div></header>
<div class="toolbar"><button id="reset" type="button">重置全窗</button><button id="ema-toggle" type="button" aria-pressed="true">EMA50</button><button id="trade-toggle" type="button" aria-pressed="true">交易连线</button><button id="crisis-toggle" type="button" aria-pressed="true">危机区间</button><div class="legend"><span><i class="sw" style="background:var(--up)"></i>Long</span><span><i class="sw" style="background:var(--down)"></i>Short</span><span><i class="sw" style="background:var(--ema)"></i>EMA50</span><span><i class="sw" style="background:var(--crisis)"></i>Crisis short</span></div></div>
<div class="chart-wrap"><canvas id="chart" aria-label="COST V1 BTC ETH candle, EMA50 and equity charts"></canvas><div id="tooltip" role="tooltip"></div></div>
<div class="hint">滚轮缩放；拖动平移；双击恢复全窗；点击交易表聚焦对应持仓区间。虚线为危机双空腿，实线为正常CBCT交易。</div>
<div class="table-wrap"><table><caption id="trade-caption"></caption><thead><tr><th>ID</th><th>模式</th><th>资产</th><th>方向</th><th>入场 UTC</th><th>出场 UTC</th><th>退出原因</th><th>log growth</th></tr></thead><tbody id="trade-body"></tbody></table></div>
<script>
const DATA=__PAYLOAD__;
const canvas=document.getElementById('chart'),ctx=canvas.getContext('2d'),tip=document.getElementById('tooltip');
const full={start:DATA.window[0],end:DATA.window[1]},view={start:full.start,end:full.end};
const visible={ema:true,trades:true,crisis:true};let drag=null,hoverX=null,raf=0;
document.getElementById('metrics').innerHTML=[['净值倍数',DATA.metrics.equityMultiple.toFixed(3)+'x'],['Ordered MDD',DATA.metrics.orderedMddPct.toFixed(2)+'%'],['账户交易',DATA.metrics.accountTrades],['危机阶段',DATA.metrics.crisisEpisodes]].map(x=>`<div class="metric"><b>${x[1]}</b><span>${x[0]}</span></div>`).join('');
document.getElementById('trade-caption').textContent=`账户交易 ${DATA.metrics.accountTrades} 笔｜绘制 ${DATA.metrics.routedLegs} 条资产腿路径`;
const fmtTs=ms=>new Date(ms).toISOString().replace('.000Z','Z');
document.getElementById('trade-body').innerHTML=DATA.trades.map(t=>`<tr data-id="${t.id}"><td>${t.id}</td><td class="${t.mode==='crisis'?'crisis':''}">${t.mode}</td><td>${t.asset}</td><td class="${t.side>0?'long':'short'}">${t.side>0?'LONG':'SHORT'}</td><td>${fmtTs(t.entry)}</td><td>${fmtTs(t.exit)}</td><td>${t.reason}</td><td>${t.logGrowth.toFixed(4)}</td></tr>`).join('');
const panels=[{key:'btc',title:'BTCUSDT · 1D candles + EMA50',top:.035,bottom:.325},{key:'eth',title:'ETHUSDT · 1D candles + EMA50',top:.355,bottom:.645},{key:'equity',title:'Account equity · hourly retained path',top:.69,bottom:.955}];
function css(name){return getComputedStyle(document.documentElement).getPropertyValue(name).trim()}
function resize(){const dpr=Math.max(1,window.devicePixelRatio||1),r=canvas.getBoundingClientRect();canvas.width=Math.round(r.width*dpr);canvas.height=Math.round(r.height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);schedule()}
function xMap(t,w,l,r){return l+(t-view.start)/(view.end-view.start)*(w-l-r)}
function bisect(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const m=(lo+hi)>>1;if(rows[m][0]<t)lo=m+1;else hi=m}if(lo>0&&Math.abs(rows[lo-1][0]-t)<Math.abs(rows[lo][0]-t))lo--;return lo}
function clipRows(rows){const a=Math.max(0,bisect(rows,view.start)-1),b=Math.min(rows.length,bisect(rows,view.end)+2);return rows.slice(a,b)}
function logMap(v,min,max,y0,y1){const a=Math.log(Math.max(v,1e-12)),lo=Math.log(min),hi=Math.log(max);return y1-(a-lo)/(hi-lo)*(y1-y0)}
function rangeFor(rows,kind){let lo=Infinity,hi=-Infinity;if(kind==='price'){for(const r of rows){lo=Math.min(lo,r[3]);hi=Math.max(hi,r[2]);if(visible.ema&&r[5]!=null){lo=Math.min(lo,r[5]);hi=Math.max(hi,r[5])}}}else{for(const r of rows){lo=Math.min(lo,r[1]);hi=Math.max(hi,r[1])}}if(!isFinite(lo)||lo<=0){lo=.9;hi=1.1}const pad=Math.max(.025,(Math.log(hi)-Math.log(lo))*.07);return[Math.exp(Math.log(lo)-pad),Math.exp(Math.log(hi)+pad)]}
function grid(panel,w,h,left,right,domain){const y0=h*panel.top,y1=h*panel.bottom;ctx.strokeStyle=css('--line');ctx.fillStyle=css('--muted');ctx.font='11px sans-serif';ctx.lineWidth=1;for(let i=0;i<=4;i++){const y=y0+(y1-y0)*i;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right,y);ctx.stroke();const v=Math.exp(Math.log(domain[1])-(Math.log(domain[1])-Math.log(domain[0]))*i/4);ctx.fillText(v>=1000?v.toLocaleString(undefined,{maximumFractionDigits:0}):v.toFixed(v<10?2:1),5,y+4)}ctx.fillStyle=css('--text');ctx.font='600 12px sans-serif';ctx.fillText(panel.title,left+5,y0+15);return[y0,y1]}
function drawPrice(rows,panel,asset,w,h,left,right){const visibleRows=clipRows(rows),domain=rangeFor(visibleRows,'price'),[y0,y1]=grid(panel,w,h,left,right,domain),plotW=w-left-right,cw=Math.max(1,Math.min(8,plotW/Math.max(1,visibleRows.length)*.72));ctx.save();ctx.beginPath();ctx.rect(left,y0,w-left-right,y1-y0);ctx.clip();for(const r of visibleRows){const x=xMap(r[0],w,left,right),yo=logMap(r[1],...domain,y0,y1),yh=logMap(r[2],...domain,y0,y1),yl=logMap(r[3],...domain,y0,y1),yc=logMap(r[4],...domain,y0,y1),up=r[4]>=r[1];ctx.strokeStyle=up?css('--up'):css('--down');ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x,yh);ctx.lineTo(x,yl);ctx.stroke();ctx.fillRect(x-cw/2,Math.min(yo,yc),cw,Math.max(1,Math.abs(yc-yo)))}if(visible.ema){ctx.strokeStyle=css('--ema');ctx.lineWidth=1.5;ctx.beginPath();let begun=false;for(const r of visibleRows){if(r[5]==null)continue;const x=xMap(r[0],w,left,right),y=logMap(r[5],...domain,y0,y1);if(!begun){ctx.moveTo(x,y);begun=true}else ctx.lineTo(x,y)}ctx.stroke()}if(visible.trades){for(const q of DATA.lines){if(q.asset!==asset||q.exit<view.start||q.entry>view.end)continue;const x1=xMap(q.entry,w,left,right),x2=xMap(q.exit,w,left,right),a=logMap(q.entryPrice,...domain,y0,y1),b=logMap(q.exitPrice,...domain,y0,y1);ctx.strokeStyle=q.mode==='crisis'?css('--crisis'):(q.side>0?css('--up'):css('--down'));ctx.lineWidth=q.mode==='crisis'?2.2:1.7;ctx.setLineDash(q.mode==='crisis'?[6,4]:[]);ctx.beginPath();ctx.moveTo(x1,a);ctx.lineTo(x2,b);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x1,a-5);ctx.lineTo(x1-5,a+4);ctx.lineTo(x1+5,a+4);ctx.closePath();ctx.fill();ctx.fillRect(x2-4,b-4,8,8)}}ctx.restore()}
function drawEquity(rows,panel,w,h,left,right){const visibleRows=clipRows(rows),domain=rangeFor(visibleRows,'equity'),[y0,y1]=grid(panel,w,h,left,right,domain);ctx.save();ctx.beginPath();ctx.rect(left,y0,w-left-right,y1-y0);ctx.clip();ctx.strokeStyle=css('--equity');ctx.lineWidth=1.8;ctx.beginPath();const step=Math.max(1,Math.floor(visibleRows.length/Math.max(1,(w-left-right)*2)));let begun=false;for(let i=0;i<visibleRows.length;i+=step){const r=visibleRows[i],x=xMap(r[0],w,left,right),y=logMap(r[1],...domain,y0,y1);if(!begun){ctx.moveTo(x,y);begun=true}else ctx.lineTo(x,y)}ctx.stroke();ctx.restore()}
function drawCrisis(w,h,left,right){if(!visible.crisis)return;ctx.fillStyle='rgba(255,155,66,.09)';for(const p of DATA.crisisPeriods){if(p.end<view.start||p.start>view.end)continue;const a=xMap(Math.max(p.start,view.start),w,left,right),b=xMap(Math.min(p.end,view.end),w,left,right);ctx.fillRect(a,h*.035,Math.max(1,b-a),h*(.955-.035))}}
function xAxis(w,h,left,right){ctx.strokeStyle=css('--line');ctx.fillStyle=css('--muted');ctx.font='11px sans-serif';for(let i=0;i<=6;i++){const t=view.start+(view.end-view.start)*i/6,x=xMap(t,w,left,right);ctx.beginPath();ctx.moveTo(x,h*.955);ctx.lineTo(x,h*.955+5);ctx.stroke();const label=new Date(t).toISOString().slice(0,10);ctx.fillText(label,Math.max(left,Math.min(x-32,w-right-66)),h*.955+19)}}
function draw(){raf=0;const r=canvas.getBoundingClientRect(),w=r.width,h=r.height,left=68,right=18;ctx.clearRect(0,0,w,h);ctx.fillStyle=css('--panel');ctx.fillRect(0,0,w,h);drawCrisis(w,h,left,right);drawPrice(DATA.btc,panels[0],'BTCUSDT',w,h,left,right);drawPrice(DATA.eth,panels[1],'ETHUSDT',w,h,left,right);drawEquity(DATA.equity,panels[2],w,h,left,right);xAxis(w,h,left,right);if(hoverX!=null){ctx.strokeStyle='rgba(230,238,246,.45)';ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(hoverX,h*.035);ctx.lineTo(hoverX,h*.955);ctx.stroke();ctx.setLineDash([])}}
function schedule(){if(!raf)raf=requestAnimationFrame(draw)}
function clamp(){const span=view.end-view.start,fullSpan=full.end-full.start;if(span>=fullSpan){view.start=full.start;view.end=full.end;return}if(view.start<full.start){view.start=full.start;view.end=full.start+span}if(view.end>full.end){view.end=full.end;view.start=full.end-span}}
function reset(){view.start=full.start;view.end=full.end;document.querySelectorAll('tbody tr').forEach(r=>r.classList.remove('active'));schedule()}
document.getElementById('reset').onclick=reset;canvas.ondblclick=reset;
for(const [id,key] of [['ema-toggle','ema'],['trade-toggle','trades'],['crisis-toggle','crisis']])document.getElementById(id).onclick=e=>{visible[key]=!visible[key];e.currentTarget.setAttribute('aria-pressed',String(visible[key]));schedule()};
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left-68)/(r.width-86),center=view.start+Math.max(0,Math.min(1,x))*(view.end-view.start),factor=e.deltaY>0?1.25:.8,newSpan=Math.max(7*864e5,Math.min(full.end-full.start,(view.end-view.start)*factor));view.start=center-newSpan*Math.max(0,Math.min(1,x));view.end=view.start+newSpan;clamp();schedule()},{passive:false});
canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,start:view.start,end:view.end};canvas.setPointerCapture(e.pointerId)});canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);
canvas.addEventListener('pointermove',e=>{const r=canvas.getBoundingClientRect();hoverX=Math.max(68,Math.min(r.width-18,e.clientX-r.left));if(drag){const dx=e.clientX-drag.x,dt=-dx/(r.width-86)*(drag.end-drag.start);view.start=drag.start+dt;view.end=drag.end+dt;clamp();tip.style.display='none';schedule();return}const t=view.start+(hoverX-68)/(r.width-86)*(view.end-view.start),bi=bisect(DATA.btc,t),ei=bisect(DATA.eth,t),qi=bisect(DATA.equity,t),b=DATA.btc[bi],n=DATA.eth[ei],q=DATA.equity[qi];tip.innerHTML=`<b>${fmtTs(b[0]).slice(0,10)}</b><br>BTC O/H/L/C ${b.slice(1,5).map(v=>v.toLocaleString()).join(' / ')}<br>BTC EMA50 ${b[5]==null?'warmup':b[5].toLocaleString()}<br>ETH O/H/L/C ${n.slice(1,5).map(v=>v.toLocaleString()).join(' / ')}<br>ETH EMA50 ${n[5]==null?'warmup':n[5].toLocaleString()}<br>Equity ${q[1].toFixed(4)}x`;tip.style.display='block';tip.style.left=Math.min(r.width-285,Math.max(8,hoverX+18))+'px';tip.style.top='16px';schedule()});canvas.addEventListener('pointerleave',()=>{hoverX=null;tip.style.display='none';schedule()});
document.getElementById('trade-body').addEventListener('click',e=>{const row=e.target.closest('tr');if(!row)return;const t=DATA.trades.find(x=>x.id===row.dataset.id),duration=Math.max(30*864e5,t.exit-t.entry),pad=duration*.35;view.start=t.entry-pad;view.end=t.exit+pad;clamp();document.querySelectorAll('tbody tr').forEach(r=>r.classList.toggle('active',r===row));canvas.scrollIntoView({behavior:'smooth',block:'start'});schedule()});
new ResizeObserver(resize).observe(canvas);resize();
</script>
</body>
</html>
""".replace("__PAYLOAD__", payload_json)


def render(source_date: str, output_date: str) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload(source_date)
    output = ARTIFACT_DIR / f"binance_1d_be_cost_v1_trade_path_{output_date}.html"
    output.write_text(html_document(payload), encoding="utf-8")
    if "__PAYLOAD__" in output.read_text(encoding="utf-8"):
        raise RuntimeError("template placeholder remains")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = ARTIFACT_DIR / f"binance_1d_be_cost_v1_trade_path_{output_date}.sha256"
    manifest.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output, manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render self-contained COST V1 trade path with BTC/ETH EMA50."
    )
    parser.add_argument("--source-date", default="2026-08-12")
    parser.add_argument("--output-date", default="2026-08-14")
    args = parser.parse_args()
    for path in render(args.source_date, args.output_date):
        print(path)


if __name__ == "__main__":
    main()
