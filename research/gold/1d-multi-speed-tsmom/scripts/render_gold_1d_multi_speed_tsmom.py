from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/gold/1d-multi-speed-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def rounded(value: Any, digits: int = 8) -> float:
    return round(float(value), digits)


def build_payload(run_date: str, artifact_kind: str) -> dict[str, Any]:
    stem = ARTIFACT_DIR / f"gold-1d-ms-tsmom-{artifact_kind}-{run_date}"
    daily = pd.read_csv(f"{stem}-daily-paths.csv", parse_dates=["ts"])
    episodes = pd.read_csv(
        f"{stem}-episodes.csv", parse_dates=["entry_ts", "exit_ts"]
    )
    yearly = pd.read_csv(f"{stem}-yearly-returns.csv")
    metrics = pd.read_csv(f"{stem}-metrics.csv")
    config = json.loads(Path(f"{stem}-config.json").read_text(encoding="utf-8"))

    if daily.empty or not daily["ts"].is_monotonic_increasing:
        raise RuntimeError("daily path is empty or not monotonic")
    if daily["ts"].duplicated().any():
        raise RuntimeError("daily path contains duplicate timestamps")
    if episodes["episode_id"].duplicated().any():
        raise RuntimeError("duplicate episode ids")
    if (episodes["entry_ts"] > episodes["exit_ts"]).any():
        raise RuntimeError("episode has entry after exit")
    path_dates = set(daily["ts"])
    if not set(episodes["entry_ts"]).issubset(path_dates):
        raise RuntimeError("episode entry is absent from retained daily path")
    if not set(episodes["exit_ts"]).issubset(path_dates):
        raise RuntimeError("episode exit is absent from retained daily path")

    series = {
        "1M": "net_equity_tsmom_1m_2bps",
        "3M": "net_equity_tsmom_3m_2bps",
        "12M": "net_equity_tsmom_12m_2bps",
        "Composite": "net_equity_composite_1_3_12m_2bps",
    }
    if "buyhold_equity_2bps" in daily.columns:
        series["Buy&Hold"] = "buyhold_equity_2bps"
    bars = []
    for row in daily.itertuples(index=False):
        bars.append(
            [
                timestamp_ms(row.ts),
                rounded(row.open, 4),
                rounded(row.high, 4),
                rounded(row.low, 4),
                rounded(row.close, 4),
                rounded(row.position_composite_1_3_12m, 6),
                *[rounded(getattr(row, column), 8) for column in series.values()],
            ]
        )

    episode_rows = []
    for row in episodes.itertuples(index=False):
        episode_rows.append(
            {
                "id": f"E{int(row.episode_id):03d}",
                "side": str(row.side),
                "entry": timestamp_ms(row.entry_ts),
                "exit": timestamp_ms(row.exit_ts),
                "entryPrice": rounded(row.entry_close, 4),
                "exitPrice": rounded(row.exit_close, 4),
                "sessions": int(row.sessions),
                "startPosition": rounded(row.start_position, 5),
                "maxAbsPosition": rounded(row.max_abs_position, 5),
                "netReturn": rounded(row.net_return, 8),
                "closed": bool(row.closed_by_reversal),
            }
        )

    annual = []
    yearly = yearly.loc[yearly["cost_bps_one_way"].eq(2.0)].copy()
    for year in sorted(yearly["year"].unique()):
        rows = yearly.loc[yearly["year"].eq(year)].set_index("label")
        year_daily = daily.loc[daily["ts"].dt.year.eq(year)]
        values = []
        for label in series:
            if label in rows.index:
                values.append(rounded(rows.loc[label, "net_return"], 8))
            elif label == "Buy&Hold":
                values.append(
                    rounded((1.0 + year_daily["buyhold_net_return_2bps"]).prod() - 1.0, 8)
                )
            else:
                raise RuntimeError(f"annual return missing for {label} in {year}")
        annual.append(
            [
                int(year),
                *values,
            ]
        )

    headline = {}
    primary = metrics.loc[metrics["cost_bps_one_way"].eq(2.0)].set_index("label")
    for label in series:
        row = primary.loc[label]
        headline[label] = {
            "cagr": rounded(row["cagr"]),
            "sharpe": rounded(row["sharpe"]),
            "mdd": rounded(row["max_drawdown"]),
            "netTotal": rounded(row["net_total_return"]),
        }
    return {
        "version": "GOLD-1D-MS-TSMOM baseline",
        "status": "explore / not promoted / not live-ready",
        "costBps": 2,
        "targetVol": config["target_volatility"],
        "window": [bars[0][0], bars[-1][0]],
        "labels": list(series),
        "bars": bars,
        "annual": annual,
        "episodes": episode_rows,
        "metrics": headline,
    }


def html_document(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>黄金 TSMOM 1M/3M/12M 回测路径</title><style>
:root{color-scheme:dark;--bg:#0b0e12;--panel:#11161d;--grid:#29313c;--text:#eef2f6;--muted:#8f9baa;--up:#3bd19f;--down:#ff6b77;--gold:#f2c14e;--blue:#61a5fa;--violet:#b794f4;--orange:#fb923c}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:20px 22px 14px;border-bottom:1px solid var(--grid);display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}h1{font-size:21px;margin:0 0 5px}.sub,.hint{color:var(--muted)}.metrics{display:flex;gap:20px;flex-wrap:wrap}.metric b{font-size:17px;display:block}.metric span{font-size:11px;color:var(--muted)}.toolbar{position:sticky;top:0;z-index:4;padding:9px 18px;background:rgba(11,14,18,.96);border-bottom:1px solid var(--grid);display:flex;gap:12px;align-items:center;flex-wrap:wrap}.toolbar button{background:transparent;color:var(--text);border:1px solid var(--grid);padding:6px 10px;cursor:pointer}.toolbar button[aria-pressed="false"]{opacity:.4}.legend{display:flex;gap:13px;color:var(--muted);flex-wrap:wrap}.sw{display:inline-block;width:17px;height:3px;margin-right:5px;vertical-align:middle}.wrap{position:relative;padding:10px 12px 4px}canvas{display:block;width:100%;height:820px;background:var(--panel);border:1px solid var(--grid)}#tip{display:none;position:absolute;pointer-events:none;background:#0a1017;border:1px solid #475569;padding:8px 10px;z-index:5;white-space:nowrap;font-variant-numeric:tabular-nums}.hint{padding:5px 18px 14px}.table-wrap{padding:0 18px 28px;overflow:auto}table{width:100%;border-collapse:collapse;min-width:950px;font-variant-numeric:tabular-nums}caption{text-align:left;font-size:15px;font-weight:700;padding:12px 0}th,td{padding:7px 9px;border-bottom:1px solid var(--grid);white-space:nowrap;text-align:left}th{color:var(--muted)}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#19212b}.long{color:var(--up)}.short{color:var(--down)}@media(max-width:720px){canvas{height:720px}.wrap{padding:6px}.table-wrap{padding:0 8px 20px}}
</style></head><body>
<header><div><h1>黄金 · TSMOM 1M / 3M / 12M</h1><div class="sub">GC.F 连续期货｜10% 单资产目标波动｜2 bps 单边换手成本｜UTC</div></div><div class="metrics" id="metrics"></div></header>
<div class="toolbar"><button id="reset">重置全窗</button>__SERIES_CONTROLS__<div class="legend"><span><i class="sw" style="background:var(--gold)"></i>黄金价格</span>__SERIES_LEGEND__</div></div>
<div class="wrap"><canvas id="chart"></canvas><div id="tip"></div></div><div class="hint">上：价格与 Composite 方向区间；中：Composite 实际持仓；下：四分支含成本净值。滚轮缩放，拖动平移，双击重置；点击区间表聚焦。</div>
<div class="wrap"><canvas id="annual" style="height:310px"></canvas></div><div class="hint">分年份净收益；首尾年份是部分年度。</div>
<div class="table-wrap"><table><caption id="caption"></caption><thead><tr><th>ID</th><th>方向</th><th>入场</th><th>出场</th><th>日数</th><th>起始仓位</th><th>最大绝对仓位</th><th>净收益</th><th>结束</th></tr></thead><tbody id="episodes"></tbody></table></div>
<script>const DATA=__PAYLOAD__;
const C={"1M":"#61a5fa","3M":"#b794f4","12M":"#fb923c","Composite":"#3bd19f","Buy&Hold":"#e5e7eb"},visible=Object.fromEntries(DATA.labels.map(x=>[x,true]));
const canvas=document.getElementById('chart'),ctx=canvas.getContext('2d'),annual=document.getElementById('annual'),actx=annual.getContext('2d'),tip=document.getElementById('tip');let view={start:DATA.window[0],end:DATA.window[1]},drag=null,hover=null,raf=0;
const pct=x=>(100*x).toFixed(2)+'%',date=x=>new Date(x).toISOString().slice(0,10),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
document.getElementById('metrics').innerHTML=Object.entries(DATA.metrics).map(([k,v])=>`<div class="metric"><b>${pct(v.cagr)} / ${v.sharpe.toFixed(2)}</b><span>${k} CAGR / Sharpe · MDD ${pct(v.mdd)}</span></div>`).join('');
const body=document.getElementById('episodes');document.getElementById('caption').textContent=`Composite 方向区间 ${DATA.episodes.length} 段（连续目标仓位，不等同离散交易）`;
body.innerHTML=DATA.episodes.map(e=>`<tr data-id="${e.id}"><td>${e.id}</td><td class="${e.side}">${e.side==='long'?'多':'空'}</td><td>${date(e.entry)}</td><td>${date(e.exit)}</td><td>${e.sessions}</td><td>${e.startPosition.toFixed(3)}</td><td>${e.maxAbsPosition.toFixed(3)}</td><td class="${e.netReturn>=0?'long':'short'}">${pct(e.netReturn)}</td><td>${e.closed?'反转':'样本结束'}</td></tr>`).join('');
function fit(c,h){const d=devicePixelRatio||1,r=c.getBoundingClientRect();c.width=Math.max(1,Math.round(r.width*d));c.height=Math.round(h*d);return d}function xmap(t,l,r){return l+(t-view.start)/(view.end-view.start)*(r-l)}function ym(v,min,max,t,b){return b-(v-min)/(max-min||1)*(b-t)}function line(points,color,w=1.5){if(points.length<2)return;ctx.beginPath();points.forEach((p,i)=>(i?ctx.lineTo(...p):ctx.moveTo(...p)));ctx.strokeStyle=color;ctx.lineWidth=w;ctx.stroke()}
function draw(){raf=0;const d=fit(canvas,820),W=canvas.width,H=canvas.height,l=62*d,r=W-15*d;ctx.clearRect(0,0,W,H);ctx.font=`${11*d}px sans-serif`;const rows=DATA.bars.filter(b=>b[0]>=view.start&&b[0]<=view.end);if(!rows.length)return;const panels=[[20,350],[380,500],[535,790]].map(p=>p.map(x=>x*d));ctx.strokeStyle='#29313c';panels.forEach(p=>ctx.strokeRect(l,p[0],r-l,p[1]-p[0]));
const lo=Math.min(...rows.map(b=>b[3])),hi=Math.max(...rows.map(b=>b[2]));DATA.episodes.filter(e=>e.exit>=view.start&&e.entry<=view.end).forEach(e=>{ctx.fillStyle=e.side==='long'?'rgba(59,209,159,.055)':'rgba(255,107,119,.055)';ctx.fillRect(xmap(Math.max(e.entry,view.start),l,r),panels[0][0],xmap(Math.min(e.exit,view.end),l,r)-xmap(Math.max(e.entry,view.start),l,r),panels[0][1]-panels[0][0])});
const step=Math.max(1,Math.floor(rows.length/1500));for(let i=0;i<rows.length;i+=step){const b=rows[i],x=xmap(b[0],l,r),yO=ym(b[1],lo,hi,...panels[0]),yH=ym(b[2],lo,hi,...panels[0]),yL=ym(b[3],lo,hi,...panels[0]),yC=ym(b[4],lo,hi,...panels[0]);ctx.strokeStyle=b[4]>=b[1]?'#3bd19f':'#ff6b77';ctx.beginPath();ctx.moveTo(x,yH);ctx.lineTo(x,yL);ctx.moveTo(x,yO);ctx.lineTo(x,yC);ctx.stroke()}
const ps=rows.map(b=>b[5]),pmin=Math.min(-.1,...ps),pmax=Math.max(.1,...ps);line(rows.map(b=>[xmap(b[0],l,r),ym(b[5],pmin,pmax,...panels[1])]),'#f2c14e',1.4*d);ctx.strokeStyle='#66717f';ctx.beginPath();ctx.moveTo(l,ym(0,pmin,pmax,...panels[1]));ctx.lineTo(r,ym(0,pmin,pmax,...panels[1]));ctx.stroke();
let emin=Infinity,emax=-Infinity;rows.forEach(b=>b.slice(6,6+DATA.labels.length).forEach(v=>{emin=Math.min(emin,v);emax=Math.max(emax,v)}));DATA.labels.forEach((lab,j)=>{if(visible[lab])line(rows.map(b=>[xmap(b[0],l,r),ym(b[6+j],emin,emax,...panels[2])]),C[lab],(lab==='Composite'?2.1:1.2)*d)});
ctx.fillStyle='#8f9baa';ctx.fillText(`价格 ${lo.toFixed(1)}—${hi.toFixed(1)}`,8*d,35*d);ctx.fillText(`仓位 ${pmin.toFixed(2)}—${pmax.toFixed(2)}`,8*d,395*d);ctx.fillText(`净值 ${emin.toFixed(2)}—${emax.toFixed(2)}`,8*d,550*d);ctx.fillText(date(view.start),l,810*d);ctx.fillText(date(view.end),r-72*d,810*d);
if(hover!==null){const x=xmap(hover,l,r);ctx.strokeStyle='#d1d5db';ctx.beginPath();ctx.moveTo(x,panels[0][0]);ctx.lineTo(x,panels[2][1]);ctx.stroke();const b=rows.reduce((a,z)=>Math.abs(z[0]-hover)<Math.abs(a[0]-hover)?z:a,rows[0]);tip.innerHTML=`${date(b[0])}<br>Close ${b[4].toFixed(2)} · Position ${b[5].toFixed(3)}<br>${DATA.labels.map((lab,j)=>`${lab} ${b[6+j].toFixed(3)}x`).join(' · ')}`;tip.style.display='block'}else tip.style.display='none';drawAnnual(d)}
function drawAnnual(d){fit(annual,310);const W=annual.width,H=annual.height,l=50*d,r=W-12*d,t=15*d,b=H-35*d;actx.clearRect(0,0,W,H);actx.strokeStyle='#29313c';actx.strokeRect(l,t,r-l,b-t);const vals=DATA.annual.flatMap(x=>x.slice(1)),m=Math.max(.01,...vals.map(Math.abs)),zero=ym(0,-m,m,t,b),group=(r-l)/DATA.annual.length,bw=Math.max(1,group*.16);DATA.annual.forEach((row,i)=>row.slice(1).forEach((v,j)=>{const x=l+i*group+group*.13+j*bw,y=ym(v,-m,m,t,b);actx.fillStyle=C[DATA.labels[j]];actx.fillRect(x,Math.min(y,zero),bw*.82,Math.abs(zero-y))}));actx.strokeStyle='#66717f';actx.beginPath();actx.moveTo(l,zero);actx.lineTo(r,zero);actx.stroke();actx.fillStyle='#8f9baa';actx.font=`${10*d}px sans-serif`;DATA.annual.forEach((row,i)=>{if(i%3===0)actx.fillText(row[0],l+i*group,b+16*d)})}
function schedule(){if(!raf)raf=requestAnimationFrame(draw)}window.addEventListener('resize',schedule);document.getElementById('reset').onclick=()=>{view={start:DATA.window[0],end:DATA.window[1]};schedule()};canvas.ondblclick=document.getElementById('reset').onclick;
document.querySelectorAll('.toggle').forEach(x=>x.onclick=()=>{const k=x.dataset.label;visible[k]=!visible[k];x.setAttribute('aria-pressed',visible[k]);schedule()});canvas.onwheel=e=>{e.preventDefault();const rect=canvas.getBoundingClientRect(),u=clamp((e.clientX-rect.left)/rect.width,0,1),span=view.end-view.start,f=e.deltaY>0?1.25:.8,n=Math.max(86400000*30,Math.min(DATA.window[1]-DATA.window[0],span*f)),anchor=view.start+u*span;view.start=clamp(anchor-u*n,DATA.window[0],DATA.window[1]-n);view.end=view.start+n;schedule()};canvas.onmousedown=e=>drag={x:e.clientX,start:view.start,end:view.end};window.onmouseup=()=>drag=null;window.onmousemove=e=>{if(drag){const dx=(e.clientX-drag.x)/canvas.getBoundingClientRect().width*(drag.end-drag.start),span=drag.end-drag.start;view.start=clamp(drag.start-dx,DATA.window[0],DATA.window[1]-span);view.end=view.start+span;schedule()}else{const r=canvas.getBoundingClientRect();if(e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom){hover=view.start+(e.clientX-r.left)/r.width*(view.end-view.start);tip.style.left=(e.clientX-r.left+18)+'px';tip.style.top=(e.clientY-r.top+18)+'px';schedule()}}};canvas.onmouseleave=()=>{hover=null;schedule()};body.onclick=e=>{const tr=e.target.closest('tr');if(!tr)return;const ep=DATA.episodes.find(x=>x.id===tr.dataset.id),pad=Math.max(86400000*10,(ep.exit-ep.entry)*.15);view.start=Math.max(DATA.window[0],ep.entry-pad);view.end=Math.min(DATA.window[1],ep.exit+pad);document.querySelectorAll('tbody tr').forEach(x=>x.classList.toggle('active',x===tr));schedule()};schedule();</script></body></html>'''
    controls = "".join(
        f'<button class="toggle" data-label="{label}" aria-pressed="true">{label}</button>'
        for label in payload["labels"]
    )
    colors = {
        "1M": "#61a5fa",
        "3M": "#b794f4",
        "12M": "#fb923c",
        "Composite": "#3bd19f",
        "Buy&Hold": "#e5e7eb",
    }
    legend = "".join(
        f'<span><i class="sw" style="background:{colors[label]}"></i>{label}</span>'
        for label in payload["labels"]
    )
    return (
        template.replace("__PAYLOAD__", payload_json)
        .replace("__SERIES_CONTROLS__", controls)
        .replace("__SERIES_LEGEND__", legend)
    )


def checksum_manifest(stem: Path, output: Path) -> None:
    files = sorted(stem.parent.glob(f"{stem.name}-*"))
    lines = []
    for path in files:
        if path == output:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default="2026-08-18")
    parser.add_argument(
        "--artifact-kind",
        choices=("baseline", "recent-extension"),
        default="baseline",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    stem = ARTIFACT_DIR / f"gold-1d-ms-tsmom-{args.artifact_kind}-{args.run_date}"
    output = Path(f"{stem}-interactive.html")
    manifest = Path(f"{stem}-checksums.sha256")
    if output.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {output}; pass --force")
    payload = build_payload(args.run_date, args.artifact_kind)
    output.write_text(html_document(payload), encoding="utf-8")
    checksum_manifest(stem, manifest)
    if "__PAYLOAD__" in output.read_text(encoding="utf-8"):
        raise RuntimeError("HTML contains an unresolved payload placeholder")
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "bytes": output.stat().st_size,
                "daily_bars": len(payload["bars"]),
                "episodes": len(payload["episodes"]),
                "annual_rows": len(payload["annual"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
