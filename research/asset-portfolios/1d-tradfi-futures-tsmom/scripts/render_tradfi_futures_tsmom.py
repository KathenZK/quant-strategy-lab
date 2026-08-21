#!/usr/bin/env python3
"""Render the retained TF-1D-FUT-TSMOM P0 paths as self-contained HTML."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-tradfi-futures-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"


def ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def payload(run_date: str) -> dict[str, Any]:
    stem = ARTIFACT_DIR / f"tf-1d-fut-tsmom-p0-{run_date}"
    paths = pd.read_csv(f"{stem}-portfolio-paths.csv", parse_dates=["ts"])
    metrics = pd.read_csv(f"{stem}-metrics.csv")
    yearly = pd.read_csv(f"{stem}-yearly-returns.csv")
    class_year = pd.read_csv(f"{stem}-class-year-contributions.csv")
    labels = {
        "tsmom_1m": "1M",
        "tsmom_3m": "3M",
        "tsmom_12m": "12M",
        "composite": "Composite",
        "long_only": "Long-only RP",
    }
    pivot = paths.pivot(index="ts", columns="strategy", values="net_equity_2bps")
    if pivot.isna().any().any() or not pivot.index.is_monotonic_increasing:
        raise RuntimeError("portfolio paths are incomplete or unordered")
    daily = [
        [ms(ts), *[round(float(row[strategy]), 8) for strategy in labels]]
        for ts, row in pivot.iterrows()
    ]
    primary = metrics.loc[metrics["cost_bps_one_way"].eq(2.0)].set_index("strategy")
    headline = {
        labels[strategy]: {
            "cagr": round(float(primary.loc[strategy, "cagr"]), 8),
            "sharpe": round(float(primary.loc[strategy, "sharpe"]), 8),
            "mdd": round(float(primary.loc[strategy, "max_drawdown"]), 8),
            "net": round(float(primary.loc[strategy, "net_total_return"]), 8),
        }
        for strategy in labels
    }
    yearly = yearly.loc[
        yearly["cost_bps_one_way"].eq(2.0)
        & yearly["strategy"].isin(["composite", "long_only"])
    ]
    annual_pivot = yearly.pivot(index="year", columns="strategy", values="net_return")
    annual = [
        [int(year), round(float(row["composite"]), 8), round(float(row["long_only"]), 8)]
        for year, row in annual_pivot.iterrows()
    ]
    class_data = class_year.loc[class_year["strategy"].eq("composite")]
    classes = sorted(class_data["asset_class"].unique())
    class_pivot = class_data.pivot(
        index="year", columns="asset_class", values="net_contribution_2bps"
    ).fillna(0.0)
    class_annual = [
        [int(year), *[round(float(row[name]), 8) for name in classes]]
        for year, row in class_pivot.iterrows()
    ]
    return {
        "labels": list(labels.values()),
        "daily": daily,
        "metrics": headline,
        "annual": annual,
        "classes": classes,
        "classAnnual": class_annual,
        "window": [daily[0][0], daily[-1][0]],
        "markets": 24,
        "status": "explore / diagnostic-only / not promoted / not live-ready",
    }


def html_document(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>多资产期货 TSMOM P0</title><style>
:root{color-scheme:dark;--bg:#0b0e12;--panel:#111820;--grid:#2a3440;--text:#eef2f6;--muted:#93a1b1}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:20px 22px 14px;border-bottom:1px solid var(--grid);display:flex;gap:22px;justify-content:space-between;flex-wrap:wrap}h1{font-size:21px;margin:0 0 5px}.sub,.hint{color:var(--muted)}.metrics{display:flex;gap:18px;flex-wrap:wrap}.metric b{display:block;font-size:16px}.metric span{font-size:11px;color:var(--muted)}.toolbar{position:sticky;top:0;z-index:4;padding:9px 18px;border-bottom:1px solid var(--grid);background:rgba(11,14,18,.96);display:flex;gap:10px;flex-wrap:wrap}.toolbar button{background:transparent;color:var(--text);border:1px solid var(--grid);padding:6px 10px;cursor:pointer}.toolbar button[aria-pressed="false"]{opacity:.4}.wrap{position:relative;padding:10px 12px 2px}canvas{display:block;width:100%;height:520px;background:var(--panel);border:1px solid var(--grid)}#annual{height:300px}#tip{display:none;position:absolute;pointer-events:none;background:#091019;border:1px solid #526174;padding:8px 10px;z-index:5;white-space:nowrap}.hint{padding:5px 18px 14px}@media(max-width:720px){canvas{height:430px}.wrap{padding:6px}}
</style></head><body><header><div><h1>24市场传统期货 · TSMOM P0</h1><div class="sub">股票指数 / 债券 / 外汇 / 商品各25% · 月末调仓 · 10%组合目标波动 · 2 bps/边</div></div><div class="metrics" id="metrics"></div></header><div class="toolbar" id="toolbar"><button id="reset">重置全窗</button></div><div class="wrap"><canvas id="equity"></canvas><div id="tip"></div></div><div class="hint">五条含成本净值；滚轮缩放、拖动平移、双击重置。短周期与12M的分化可以直接比较。</div><div class="wrap"><canvas id="annual"></canvas></div><div class="hint">上半：Composite与Long-only RP分年收益；下半：Composite四资产类别年度净贡献。</div><script>
const D=__DATA__,COL={"1M":"#60a5fa","3M":"#c084fc","12M":"#fb923c","Composite":"#34d399","Long-only RP":"#e5e7eb",bond:"#60a5fa",commodity:"#f59e0b",equity_index:"#34d399",fx:"#c084fc"};const visible=Object.fromEntries(D.labels.map(x=>[x,true]));let view={start:D.window[0],end:D.window[1]},drag=null,hover=null,raf=0;const eq=document.getElementById('equity'),ctx=eq.getContext('2d'),an=document.getElementById('annual'),actx=an.getContext('2d'),tip=document.getElementById('tip'),pct=x=>(x*100).toFixed(2)+'%',date=x=>new Date(x).toISOString().slice(0,10),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
document.getElementById('metrics').innerHTML=['12M','Composite','Long-only RP'].map(k=>`<div class="metric"><b>${pct(D.metrics[k].cagr)} / ${D.metrics[k].sharpe.toFixed(2)}</b><span>${k} CAGR / Sharpe · MDD ${pct(D.metrics[k].mdd)}</span></div>`).join('');const tb=document.getElementById('toolbar');D.labels.forEach(k=>{const b=document.createElement('button');b.textContent=k;b.dataset.label=k;b.setAttribute('aria-pressed','true');b.onclick=()=>{visible[k]=!visible[k];b.setAttribute('aria-pressed',visible[k]);schedule()};tb.appendChild(b)});
function fit(c,h){const d=devicePixelRatio||1,r=c.getBoundingClientRect();c.width=Math.round(r.width*d);c.height=Math.round(h*d);return d}function xm(t,l,r){return l+(t-view.start)/(view.end-view.start)*(r-l)}function ym(v,a,b,t,z){return z-(v-a)/(b-a||1)*(z-t)}function line(c,pts,color,w){if(pts.length<2)return;c.beginPath();pts.forEach((p,i)=>(i?c.lineTo(...p):c.moveTo(...p)));c.strokeStyle=color;c.lineWidth=w;c.stroke()}
function draw(){raf=0;const d=fit(eq,520),W=eq.width,H=eq.height,l=58*d,r=W-14*d,t=18*d,b=H-35*d;ctx.clearRect(0,0,W,H);ctx.strokeStyle='#2a3440';ctx.strokeRect(l,t,r-l,b-t);const rows=D.daily.filter(x=>x[0]>=view.start&&x[0]<=view.end),vals=rows.flatMap(x=>x.slice(1)),lo=Math.min(...vals),hi=Math.max(...vals);D.labels.forEach((k,j)=>{if(visible[k])line(ctx,rows.map(x=>[xm(x[0],l,r),ym(x[1+j],lo,hi,t,b)]),COL[k],(k==='12M'||k==='Composite'?2:1.2)*d)});ctx.fillStyle='#93a1b1';ctx.font=`${10*d}px sans-serif`;ctx.fillText(`${lo.toFixed(2)}x`,8*d,b);ctx.fillText(`${hi.toFixed(2)}x`,8*d,t+10*d);ctx.fillText(date(view.start),l,b+18*d);ctx.fillText(date(view.end),r-72*d,b+18*d);if(hover!==null){const x=xm(hover,l,r);ctx.strokeStyle='#d1d5db';ctx.beginPath();ctx.moveTo(x,t);ctx.lineTo(x,b);ctx.stroke();const row=rows.reduce((a,z)=>Math.abs(z[0]-hover)<Math.abs(a[0]-hover)?z:a,rows[0]);tip.innerHTML=date(row[0])+'<br>'+D.labels.map((k,j)=>`${k} ${row[1+j].toFixed(3)}x`).join(' · ');tip.style.display='block'}else tip.style.display='none';drawAnnual(d)}
function drawAnnual(d){fit(an,300);const W=an.width,H=an.height,l=48*d,r=W-12*d,t=12*d,b=H-30*d,mid=145*d;actx.clearRect(0,0,W,H);actx.strokeStyle='#2a3440';actx.strokeRect(l,t,r-l,mid-t);actx.strokeRect(l,mid+12*d,r-l,b-mid-12*d);const av=D.annual.flatMap(x=>x.slice(1)),am=Math.max(.01,...av.map(Math.abs)),zero=ym(0,-am,am,t,mid),g=(r-l)/D.annual.length;D.annual.forEach((row,i)=>row.slice(1).forEach((v,j)=>{const x=l+i*g+g*(.2+j*.3),y=ym(v,-am,am,t,mid);actx.fillStyle=j?'#e5e7eb':'#34d399';actx.fillRect(x,Math.min(y,zero),g*.24,Math.abs(zero-y))}));actx.strokeStyle='#64748b';actx.beginPath();actx.moveTo(l,zero);actx.lineTo(r,zero);actx.stroke();const cv=D.classAnnual.flatMap(x=>x.slice(1)),cm=Math.max(.01,...cv.map(Math.abs)),cz=ym(0,-cm,cm,mid+12*d,b);D.classAnnual.forEach((row,i)=>row.slice(1).forEach((v,j)=>{const bw=g*.75/D.classes.length,x=l+i*g+g*.12+j*bw,y=ym(v,-cm,cm,mid+12*d,b);actx.fillStyle=COL[D.classes[j]];actx.fillRect(x,Math.min(y,cz),bw*.86,Math.abs(cz-y))}));actx.strokeStyle='#64748b';actx.beginPath();actx.moveTo(l,cz);actx.lineTo(r,cz);actx.stroke();actx.fillStyle='#93a1b1';actx.font=`${10*d}px sans-serif`;D.annual.forEach((row,i)=>actx.fillText(row[0],l+i*g,b+16*d))}
function schedule(){if(!raf)raf=requestAnimationFrame(draw)}document.getElementById('reset').onclick=()=>{view={start:D.window[0],end:D.window[1]};schedule()};eq.ondblclick=document.getElementById('reset').onclick;eq.onwheel=e=>{e.preventDefault();const rect=eq.getBoundingClientRect(),u=(e.clientX-rect.left)/rect.width,span=view.end-view.start,n=clamp(span*(e.deltaY>0?1.25:.8),86400000*60,D.window[1]-D.window[0]),anchor=view.start+u*span;view.start=clamp(anchor-u*n,D.window[0],D.window[1]-n);view.end=view.start+n;schedule()};eq.onmousedown=e=>drag={x:e.clientX,start:view.start,end:view.end};window.onmouseup=()=>drag=null;window.onmousemove=e=>{if(drag){const span=drag.end-drag.start,dx=(e.clientX-drag.x)/eq.getBoundingClientRect().width*span;view.start=clamp(drag.start-dx,D.window[0],D.window[1]-span);view.end=view.start+span;schedule()}else{const r=eq.getBoundingClientRect();if(e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom){hover=view.start+(e.clientX-r.left)/r.width*(view.end-view.start);tip.style.left=e.clientX-r.left+18+'px';tip.style.top=e.clientY-r.top+18+'px';schedule()}}};eq.onmouseleave=()=>{hover=null;schedule()};window.onresize=schedule;schedule();
</script></body></html>'''.replace("__DATA__", encoded)


def checksums(stem: Path, output: Path) -> None:
    rows = []
    for path in sorted(stem.parent.glob(f"{stem.name}-*")):
        if path == output:
            continue
        rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default="2026-08-18")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    stem = ARTIFACT_DIR / f"tf-1d-fut-tsmom-p0-{args.run_date}"
    output = Path(f"{stem}-interactive.html")
    if output.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {output}; pass --force")
    data = payload(args.run_date)
    output.write_text(html_document(data), encoding="utf-8")
    checksums(stem, Path(f"{stem}-checksums.sha256"))
    print(
        json.dumps(
            {"output": str(output.relative_to(ROOT)), "bytes": output.stat().st_size, "rows": len(data["daily"])},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
