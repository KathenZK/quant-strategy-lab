from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_SCRIPT = (
    FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
)
RUN_DATE = "2026-08-04"
TRADES_PATH = (
    ARTIFACT_DIR
    / f"hype_1d_ma7_separated_primary_trades_{RUN_DATE}.csv"
)
PATH_PATH = (
    ARTIFACT_DIR
    / f"hype_1d_ma7_separated_primary_path_{RUN_DATE}.csv"
)
SUMMARY_PATH = (
    ARTIFACT_DIR / f"hype_1d_ma7_separated_summary_{RUN_DATE}.json"
)
OUTPUT_PATH = (
    ARTIFACT_DIR
    / f"hype_1d_ma7_separated_trade_path_{RUN_DATE}.html"
)


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hype_1d_ma7_abt_chart_base",
        BASE_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def build_payload() -> dict[str, Any]:
    base = load_base()
    book = base.load_books()[0]
    ma7 = (
        pd.Series(book.close, dtype=float)
        .rolling(7, min_periods=7)
        .mean()
    )
    candles = [
        {
            "t": timestamp_ms(ts),
            "o": float(book.open[index]),
            "h": float(book.high[index]),
            "l": float(book.low[index]),
            "c": float(book.close[index]),
            "ma": finite_or_none(ma7.iloc[index]),
        }
        for index, ts in enumerate(book.ts)
    ]

    trades_frame = pd.read_csv(TRADES_PATH)
    trades = []
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        trades.append(
            {
                "id": f"{'L' if side == 'long' else 'S'}{index + 1:02d}",
                "side": side,
                "entryT": timestamp_ms(row["entry_ts"]),
                "exitT": timestamp_ms(row["exit_ts"]),
                "entryTs": str(row["entry_ts"]),
                "exitTs": str(row["exit_ts"]),
                "entry": float(row["entry_price"]),
                "exit": float(row["exit_price"]),
                "bars": int(row["bars_held"]),
                "reason": str(row["exit_reason"]),
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
            }
        )

    path_frame = pd.read_csv(PATH_PATH)
    equity = [
        {
            "t": timestamp_ms(row.ts),
            "v": float(row.close_equity),
            "position": int(row.position),
            "action": str(row.action),
        }
        for row in path_frame.itertuples(index=False)
    ]
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    full = summary["audited_candidates"][0]["windows"]["full"]["base"]
    return {
        "title": "HYPE 日线 MA7 多空分离趋势：完整交易路径",
        "subtitle": (
            "UTC 日 K · post-reveal historical observation · "
            "explore / not promoted / not live-ready"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "candles": candles,
        "trades": trades,
        "equity": equity,
        "metrics": {
            "returnPct": full["net_return_pct"],
            "mddPct": full["max_drawdown_pct"],
            "sharpe": full["sharpe"],
            "profitFactor": full["profit_factor"],
            "trades": full["closed_trades"],
            "longTrades": full["long_trades"],
            "shortTrades": full["short_trades"],
        },
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HYPE MA7 完整交易路径</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #080b0f;
    --panel: #0d1218;
    --panel-2: #111820;
    --grid: #202932;
    --text: #e9eef3;
    --muted: #8a99a8;
    --up: #2dd4a7;
    --down: #f05c70;
    --ma: #f6c85f;
    --long: #36c7ff;
    --short: #ffad5a;
    --equity: #a4e65e;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 14px/1.45 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .shell { max-width: 1900px; margin: 0 auto; padding: 24px; }
  header {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 20px;
    align-items: end;
    margin-bottom: 18px;
  }
  h1 { margin: 0 0 6px; font: 700 24px/1.2 Inter, system-ui, sans-serif; }
  .subtitle { color: var(--muted); font-size: 12px; }
  .metrics { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
  .metric {
    min-width: 112px;
    padding: 9px 11px;
    border: 1px solid #26313c;
    background: var(--panel);
  }
  .metric b { display: block; margin-top: 2px; font-size: 16px; color: #fff; }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
    align-items: center;
    padding: 10px 12px;
    border: 1px solid #26313c;
    border-bottom: 0;
    background: var(--panel-2);
  }
  button {
    color: var(--text);
    border: 1px solid #34414e;
    background: #151d26;
    padding: 6px 10px;
    cursor: pointer;
    font: inherit;
  }
  button:hover { border-color: #6d7e8e; }
  label { color: var(--muted); user-select: none; }
  input { vertical-align: -2px; }
  .swatch { display: inline-block; width: 16px; height: 2px; margin: 0 5px 3px 0; }
  .chart {
    position: relative;
    border: 1px solid #26313c;
    background: var(--panel);
    overflow: hidden;
  }
  #priceChart { width: 100%; height: 650px; display: block; cursor: crosshair; }
  #equityChart { width: 100%; height: 180px; display: block; border-top: 1px solid #26313c; }
  #tooltip {
    position: fixed;
    z-index: 10;
    display: none;
    pointer-events: none;
    max-width: 360px;
    padding: 9px 11px;
    border: 1px solid #465767;
    background: rgba(8, 12, 17, .96);
    box-shadow: 0 8px 30px rgba(0, 0, 0, .35);
    white-space: pre-line;
    font-size: 12px;
  }
  .hint {
    padding: 8px 12px;
    color: var(--muted);
    border: 1px solid #26313c;
    border-top: 0;
    font-size: 12px;
  }
  .trade-table-wrap { margin-top: 20px; overflow-x: auto; border: 1px solid #26313c; }
  table { width: 100%; border-collapse: collapse; min-width: 1120px; }
  th, td { padding: 8px 10px; border-bottom: 1px solid #202932; text-align: right; }
  th { color: var(--muted); background: #111820; position: sticky; top: 0; }
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2),
  th:nth-child(3), td:nth-child(3), th:nth-child(4), td:nth-child(4),
  th:nth-child(9), td:nth-child(9) { text-align: left; }
  tbody tr { cursor: pointer; }
  tbody tr:hover, tbody tr.active { background: #17212b; }
  .positive { color: var(--up); }
  .negative { color: var(--down); }
  .long { color: var(--long); }
  .short { color: var(--short); }
  @media (max-width: 900px) {
    .shell { padding: 12px; }
    header { grid-template-columns: 1fr; }
    .metrics { justify-content: flex-start; }
    #priceChart { height: 520px; }
  }
</style>
</head>
<body>
<div class="shell">
  <header>
    <div>
      <h1 id="title"></h1>
      <div class="subtitle" id="subtitle"></div>
    </div>
    <div class="metrics" id="metrics"></div>
  </header>

  <div class="toolbar">
    <button id="reset">完整范围</button>
    <button id="zoomIn">放大</button>
    <button id="zoomOut">缩小</button>
    <label><input id="showMa" type="checkbox" checked> <span class="swatch" style="background:var(--ma)"></span>MA7</label>
    <label><input id="showTrades" type="checkbox" checked> 交易连线</label>
    <label><input id="showLabels" type="checkbox" checked> 交易编号</label>
    <span class="long">▲ 多头入场</span>
    <span class="short">▼ 空头入场</span>
    <span style="color:var(--muted)">● 出场</span>
  </div>
  <div class="chart">
    <canvas id="priceChart"></canvas>
    <canvas id="equityChart"></canvas>
  </div>
  <div class="hint">滚轮缩放 · 按住拖拽平移 · 双击恢复完整范围 · 悬停查看 K 线和交易 · 点击下方交易定位</div>
  <div class="trade-table-wrap">
    <table>
      <thead>
        <tr>
          <th>编号</th><th>方向</th><th>入场时间 UTC</th><th>出场时间 UTC</th>
          <th>入场价</th><th>出场价</th><th>持有日</th><th>净收益</th><th>退出原因</th><th>金额 PnL</th>
        </tr>
      </thead>
      <tbody id="tradeRows"></tbody>
    </table>
  </div>
</div>
<div id="tooltip"></div>

<script>
const DATA = __PAYLOAD__;
const DAY = 86400000;
const COLORS = {
  bg: "#0d1218", grid: "#202932", text: "#e9eef3", muted: "#8a99a8",
  up: "#2dd4a7", down: "#f05c70", ma: "#f6c85f",
  long: "#36c7ff", short: "#ffad5a", equity: "#a4e65e"
};
const priceCanvas = document.getElementById("priceChart");
const equityCanvas = document.getElementById("equityChart");
const tooltip = document.getElementById("tooltip");
const candles = DATA.candles;
const trades = DATA.trades;
const equity = DATA.equity;
const domainMin = candles[0].t;
const domainMax = Math.max(candles[candles.length - 1].t + DAY, equity[equity.length - 1].t);
let viewStart = domainMin;
let viewEnd = domainMax;
let hoverT = null;
let activeTrade = null;
let dragging = false;
let dragX = 0;
let dragStart = 0;

document.getElementById("title").textContent = DATA.title;
document.getElementById("subtitle").textContent = DATA.subtitle;
const m = DATA.metrics;
document.getElementById("metrics").innerHTML = [
  ["全期净收益", signed(m.returnPct) + "%"],
  ["保守 MDD", m.mddPct.toFixed(2) + "%"],
  ["Sharpe", m.sharpe.toFixed(2)],
  ["金额 PF", m.profitFactor.toFixed(2)],
  ["交易", `${m.trades}（${m.longTrades}L / ${m.shortTrades}S）`]
].map(([k,v]) => `<div class="metric">${k}<b>${v}</b></div>`).join("");

function signed(v) { return (v >= 0 ? "+" : "") + v.toFixed(2); }
function dateOnly(t) { return new Date(t).toISOString().slice(0, 10); }
function dateTime(t) { return new Date(t).toISOString().replace(".000Z", "Z").replace("T", " "); }
function fmt(v, digits=3) { return Number(v).toFixed(digits); }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {ctx, w: rect.width, h: rect.height};
}

function visibleCandles() {
  return candles.filter(c => c.t >= viewStart - DAY && c.t <= viewEnd + DAY);
}

function xScale(t, left, width) {
  return left + (t - viewStart) / (viewEnd - viewStart) * width;
}

function niceTicks(min, max, count) {
  const span = Math.max(1e-9, max - min);
  const raw = span / count;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / p;
  const step = (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p;
  const first = Math.ceil(min / step) * step;
  const out = [];
  for (let v = first; v <= max + step * .1; v += step) out.push(v);
  return out;
}

function drawAxes(ctx, left, top, width, height, yMin, yMax, yFn) {
  ctx.font = "11px ui-monospace, monospace";
  ctx.lineWidth = 1;
  for (const value of niceTicks(yMin, yMax, 6)) {
    const y = yFn(value);
    ctx.strokeStyle = COLORS.grid;
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + width, y); ctx.stroke();
    ctx.fillStyle = COLORS.muted;
    ctx.textAlign = "right";
    ctx.fillText(value.toFixed(value < 10 ? 2 : 1), left - 8, y + 4);
  }
  const timeTicks = 8;
  for (let i = 0; i <= timeTicks; i++) {
    const t = viewStart + (viewEnd - viewStart) * i / timeTicks;
    const x = xScale(t, left, width);
    ctx.strokeStyle = COLORS.grid;
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
    ctx.fillStyle = COLORS.muted;
    ctx.textAlign = i === 0 ? "left" : i === timeTicks ? "right" : "center";
    ctx.fillText(dateOnly(t), x, top + height + 18);
  }
}

function drawMarker(ctx, x, y, side, entry, color, size=6) {
  ctx.fillStyle = color;
  ctx.strokeStyle = "#071016";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  if (entry) {
    if (side === "long") {
      ctx.moveTo(x, y - size); ctx.lineTo(x - size, y + size); ctx.lineTo(x + size, y + size);
    } else {
      ctx.moveTo(x, y + size); ctx.lineTo(x - size, y - size); ctx.lineTo(x + size, y - size);
    }
    ctx.closePath();
  } else {
    ctx.arc(x, y, size - 1, 0, Math.PI * 2);
  }
  ctx.fill(); ctx.stroke();
}

function drawPrice() {
  const {ctx, w, h} = setupCanvas(priceCanvas);
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, w, h);
  const margin = {left: 68, right: 22, top: 22, bottom: 34};
  const pw = w - margin.left - margin.right;
  const ph = h - margin.top - margin.bottom;
  const vis = visibleCandles();
  if (!vis.length) return;
  let yMin = Math.min(...vis.map(c => c.l));
  let yMax = Math.max(...vis.map(c => c.h));
  const visibleTrades = trades.filter(t => t.exitT >= viewStart && t.entryT <= viewEnd);
  for (const t of visibleTrades) {
    yMin = Math.min(yMin, t.entry, t.exit);
    yMax = Math.max(yMax, t.entry, t.exit);
  }
  const pad = (yMax - yMin) * .07 || 1;
  yMin -= pad; yMax += pad;
  const y = v => margin.top + (yMax - v) / (yMax - yMin) * ph;
  drawAxes(ctx, margin.left, margin.top, pw, ph, yMin, yMax, y);

  const visibleDays = Math.max(1, (viewEnd - viewStart) / DAY);
  const bodyW = clamp(pw / visibleDays * .62, 1, 13);
  for (const c of vis) {
    const x = xScale(c.t + DAY / 2, margin.left, pw);
    if (x < margin.left - 10 || x > margin.left + pw + 10) continue;
    const color = c.c >= c.o ? COLORS.up : COLORS.down;
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, y(c.h)); ctx.lineTo(x, y(c.l)); ctx.stroke();
    const top = y(Math.max(c.o, c.c));
    const bottom = y(Math.min(c.o, c.c));
    ctx.fillStyle = color;
    ctx.fillRect(x - bodyW / 2, top, bodyW, Math.max(1, bottom - top));
  }

  if (document.getElementById("showMa").checked) {
    ctx.strokeStyle = COLORS.ma; ctx.lineWidth = 1.6; ctx.beginPath();
    let started = false;
    for (const c of vis) {
      if (c.ma == null) { started = false; continue; }
      const x = xScale(c.t + DAY / 2, margin.left, pw);
      if (!started) { ctx.moveTo(x, y(c.ma)); started = true; }
      else ctx.lineTo(x, y(c.ma));
    }
    ctx.stroke();
  }

  if (document.getElementById("showTrades").checked) {
    for (const t of visibleTrades) {
      const isActive = activeTrade === t.id;
      const color = t.side === "long" ? COLORS.long : COLORS.short;
      const x1 = xScale(t.entryT, margin.left, pw);
      const x2 = xScale(t.exitT, margin.left, pw);
      const y1 = y(t.entry), y2 = y(t.exit);
      ctx.strokeStyle = color;
      ctx.globalAlpha = isActive ? 1 : .72;
      ctx.lineWidth = isActive ? 3 : 1.5;
      ctx.setLineDash(t.returnPct >= 0 ? [] : [5, 4]);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      ctx.setLineDash([]); ctx.globalAlpha = 1;
      drawMarker(ctx, x1, y1, t.side, true, color, isActive ? 8 : 6);
      drawMarker(ctx, x2, y2, t.side, false, color, isActive ? 8 : 6);
      if (document.getElementById("showLabels").checked || isActive) {
        ctx.font = isActive ? "bold 12px ui-monospace" : "10px ui-monospace";
        ctx.fillStyle = color;
        ctx.textAlign = "center";
        ctx.fillText(t.id, x1, y1 + (t.side === "long" ? 18 : -12));
        ctx.fillText(t.id, x2, y2 - 10);
      }
    }
  }

  if (hoverT != null) {
    const hx = xScale(hoverT, margin.left, pw);
    ctx.strokeStyle = "#758697"; ctx.globalAlpha = .65; ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(hx, margin.top); ctx.lineTo(hx, margin.top + ph); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha = 1;
  }
  ctx.fillStyle = COLORS.muted; ctx.textAlign = "left"; ctx.font = "11px ui-monospace";
  ctx.fillText("PRICE · HYPEUSDT", margin.left, 14);
}

function drawEquity() {
  const {ctx, w, h} = setupCanvas(equityCanvas);
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0a0f14"; ctx.fillRect(0, 0, w, h);
  const margin = {left: 68, right: 22, top: 18, bottom: 34};
  const pw = w - margin.left - margin.right;
  const ph = h - margin.top - margin.bottom;
  const vis = equity.filter(p => p.t >= viewStart - DAY && p.t <= viewEnd + DAY);
  if (!vis.length) return;
  let yMin = Math.min(...vis.map(p => p.v));
  let yMax = Math.max(...vis.map(p => p.v));
  const pad = (yMax - yMin) * .08 || .1;
  yMin = Math.max(0, yMin - pad); yMax += pad;
  const y = v => margin.top + (yMax - v) / (yMax - yMin) * ph;
  drawAxes(ctx, margin.left, margin.top, pw, ph, yMin, yMax, y);
  ctx.strokeStyle = COLORS.equity; ctx.lineWidth = 2; ctx.beginPath();
  vis.forEach((p, i) => {
    const x = xScale(p.t, margin.left, pw);
    if (i === 0) ctx.moveTo(x, y(p.v)); else ctx.lineTo(x, y(p.v));
  });
  ctx.stroke();
  for (const t of trades.filter(t => t.exitT >= viewStart && t.exitT <= viewEnd)) {
    const point = equity.reduce((best, p) => Math.abs(p.t - t.exitT) < Math.abs(best.t - t.exitT) ? p : best, equity[0]);
    ctx.fillStyle = t.returnPct >= 0 ? COLORS.up : COLORS.down;
    ctx.beginPath(); ctx.arc(xScale(t.exitT, margin.left, pw), y(point.v), 3.5, 0, Math.PI * 2); ctx.fill();
  }
  if (hoverT != null) {
    const hx = xScale(hoverT, margin.left, pw);
    ctx.strokeStyle = "#758697"; ctx.globalAlpha = .65; ctx.setLineDash([3,3]);
    ctx.beginPath(); ctx.moveTo(hx, margin.top); ctx.lineTo(hx, margin.top + ph); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha = 1;
  }
  ctx.fillStyle = COLORS.muted; ctx.textAlign = "left"; ctx.font = "11px ui-monospace";
  ctx.fillText("EQUITY MULTIPLE", margin.left, 12);
}

function draw() { drawPrice(); drawEquity(); updateRows(); }

function zoom(factor, anchorT=(viewStart + viewEnd) / 2) {
  const current = viewEnd - viewStart;
  const next = clamp(current * factor, 14 * DAY, domainMax - domainMin);
  const ratio = (anchorT - viewStart) / current;
  viewStart = anchorT - next * ratio;
  viewEnd = viewStart + next;
  if (viewStart < domainMin) { viewEnd += domainMin - viewStart; viewStart = domainMin; }
  if (viewEnd > domainMax) { viewStart -= viewEnd - domainMax; viewEnd = domainMax; }
  draw();
}

function reset() { viewStart = domainMin; viewEnd = domainMax; activeTrade = null; draw(); }
document.getElementById("reset").onclick = reset;
document.getElementById("zoomIn").onclick = () => zoom(.65);
document.getElementById("zoomOut").onclick = () => zoom(1.55);
document.getElementById("showMa").onchange = draw;
document.getElementById("showTrades").onchange = draw;
document.getElementById("showLabels").onchange = draw;

priceCanvas.addEventListener("wheel", e => {
  e.preventDefault();
  const rect = priceCanvas.getBoundingClientRect();
  const ratio = clamp((e.clientX - rect.left - 68) / Math.max(1, rect.width - 90), 0, 1);
  const anchor = viewStart + ratio * (viewEnd - viewStart);
  zoom(e.deltaY > 0 ? 1.2 : .82, anchor);
}, {passive: false});
priceCanvas.addEventListener("mousedown", e => {
  dragging = true; dragX = e.clientX; dragStart = viewStart;
});
window.addEventListener("mouseup", () => dragging = false);
window.addEventListener("mousemove", e => {
  if (!dragging) return;
  const rect = priceCanvas.getBoundingClientRect();
  const shift = -(e.clientX - dragX) / Math.max(1, rect.width - 90) * (viewEnd - viewStart);
  const span = viewEnd - viewStart;
  viewStart = clamp(dragStart + shift, domainMin, domainMax - span);
  viewEnd = viewStart + span;
  draw();
});
priceCanvas.addEventListener("dblclick", reset);

priceCanvas.addEventListener("mousemove", e => {
  if (dragging) return;
  const rect = priceCanvas.getBoundingClientRect();
  const ratio = clamp((e.clientX - rect.left - 68) / Math.max(1, rect.width - 90), 0, 1);
  hoverT = viewStart + ratio * (viewEnd - viewStart);
  const candle = candles.reduce((best, c) => Math.abs(c.t + DAY/2 - hoverT) < Math.abs(best.t + DAY/2 - hoverT) ? c : best, candles[0]);
  const eq = equity.reduce((best, p) => Math.abs(p.t - hoverT) < Math.abs(best.t - hoverT) ? p : best, equity[0]);
  const nearby = trades.filter(t => Math.min(Math.abs(t.entryT - hoverT), Math.abs(t.exitT - hoverT)) < DAY * .65);
  let text = `${dateOnly(candle.t)} UTC\nO ${fmt(candle.o)}  H ${fmt(candle.h)}  L ${fmt(candle.l)}  C ${fmt(candle.c)}\nMA7 ${candle.ma == null ? "—" : fmt(candle.ma)}  Equity ${fmt(eq.v, 4)}`;
  for (const t of nearby) {
    text += `\n${t.id} ${t.side === "long" ? "多" : "空"} ${signed(t.returnPct)}% · ${t.reason}`;
  }
  tooltip.textContent = text;
  tooltip.style.display = "block";
  tooltip.style.left = Math.min(window.innerWidth - 380, e.clientX + 16) + "px";
  tooltip.style.top = Math.min(window.innerHeight - 120, e.clientY + 16) + "px";
  draw();
});
priceCanvas.addEventListener("mouseleave", () => {
  hoverT = null; tooltip.style.display = "none"; draw();
});

const rows = document.getElementById("tradeRows");
rows.innerHTML = trades.map(t => `
  <tr data-id="${t.id}">
    <td class="${t.side}">${t.id}</td>
    <td class="${t.side}">${t.side === "long" ? "做多" : "做空"}</td>
    <td>${dateTime(t.entryT)}</td><td>${dateTime(t.exitT)}</td>
    <td>${fmt(t.entry)}</td><td>${fmt(t.exit)}</td><td>${t.bars}</td>
    <td class="${t.returnPct >= 0 ? "positive" : "negative"}">${signed(t.returnPct)}%</td>
    <td>${t.reason}</td><td class="${t.netPnl >= 0 ? "positive" : "negative"}">${signed(t.netPnl)}</td>
  </tr>`).join("");

for (const row of rows.querySelectorAll("tr")) {
  row.addEventListener("mouseenter", () => { activeTrade = row.dataset.id; draw(); });
  row.addEventListener("mouseleave", () => { activeTrade = null; draw(); });
  row.addEventListener("click", () => {
    const t = trades.find(x => x.id === row.dataset.id);
    const span = Math.max(30 * DAY, (t.exitT - t.entryT) * 2.1);
    const mid = (t.entryT + t.exitT) / 2;
    viewStart = clamp(mid - span / 2, domainMin, domainMax - span);
    viewEnd = Math.min(domainMax, viewStart + span);
    activeTrade = t.id;
    draw();
    priceCanvas.scrollIntoView({behavior: "smooth", block: "center"});
  });
}

function updateRows() {
  for (const row of rows.querySelectorAll("tr")) {
    row.classList.toggle("active", row.dataset.id === activeTrade);
  }
}

window.addEventListener("resize", draw);
draw();
</script>
</body>
</html>
"""


def main() -> None:
    payload = build_payload()
    html = HTML_TEMPLATE.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "equity_points": len(payload["equity"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
