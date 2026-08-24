from __future__ import annotations

from datetime import UTC, datetime
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FETCHER_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "audit_hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer.py"
)
RUN_DATE = "2026-08-12"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if math.isfinite(number):
        return number
    return None


def date_to_ms(value: str) -> int:
    # Input artifacts use UTC ISO timestamps; date-only strings are UTC starts.
    text = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(text)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return int(timestamp.timestamp() * 1000)


def sma(values: list[float], length: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= length:
            total -= values[index - length]
        if index >= length - 1:
            output[index] = total / length
    return output


def build_payload(symbol: str, stem: str, fetcher: Any) -> dict[str, Any]:
    summary_path = ARTIFACT_DIR / f"{stem}_{RUN_DATE}.json"
    trades_path = ARTIFACT_DIR / f"{stem}_{RUN_DATE}_trades.csv"
    path_path = ARTIFACT_DIR / f"{stem}_{RUN_DATE}_path.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    trades = read_csv_rows(trades_path)
    equity_path = read_csv_rows(path_path)

    start_ms = date_to_ms(summary["data_quality"]["daily"]["start_ts"])
    end_ms = date_to_ms(summary["data_quality"]["daily"]["end_ts"])
    dataset = fetcher.fetch_symbol_dataset(
        symbol,
        "perp_usdt",
        int(summary["data_source"]["history_days_requested"]),
        fetcher.utc_ms_now(),
    )
    candles = [
        row for row in dataset["daily"] if start_ms <= row.ts <= end_ms
    ]
    closes = [row.close for row in candles]
    ma7 = sma(closes, 7)
    candle_payload = [
        {
            "ts": row.ts,
            "iso": fetcher.iso(row.ts),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "ma7": ma7[index],
        }
        for index, row in enumerate(candles)
    ]
    trade_payload: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(trades, start=1):
        entry_ms = date_to_ms(row["entry_ts"])
        exit_ms = date_to_ms(row["exit_ts"])
        if entry_ms > exit_ms:
            raise RuntimeError(f"{symbol} trade {index} has entry after exit")
        trade_id = f"{symbol}-{index:03d}"
        if trade_id in seen_ids:
            raise RuntimeError(f"duplicate trade id {trade_id}")
        seen_ids.add(trade_id)
        trade_payload.append(
            {
                "id": trade_id,
                "entry_ts": row["entry_ts"],
                "exit_ts": row["exit_ts"],
                "entry_ms": entry_ms,
                "exit_ms": exit_ms,
                "side": row["side"],
                "entry_price": float(row["entry_price"]),
                "exit_price": float(row["exit_price"]),
                "bars_held": int(float(row["bars_held"])),
                "exit_reason": row["exit_reason"],
                "net_return_pct": float(row["net_return"]) * 100.0,
                "net_pnl": float(row["net_pnl"]),
            }
        )
    equity_payload = [
        {
            "ts": row["ts"],
            "ms": date_to_ms(row["ts"]),
            "close_equity": float(row["close_equity"]),
            "post_action_equity": float(row["post_action_equity"]),
            "position": int(float(row["position"])),
            "action": row["action"],
        }
        for row in equity_path
    ]

    closed_trades = int(summary["results"]["combined"]["base"]["closed_trades"])
    if closed_trades != len(trade_payload):
        raise RuntimeError(
            f"{symbol} trade count mismatch: metrics={closed_trades} csv={len(trade_payload)}"
        )
    if len(candle_payload) != int(summary["data_quality"]["daily"]["bars"]):
        raise RuntimeError(f"{symbol} candle count mismatch")

    return {
        "symbol": symbol,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "window": {
            "start_ts": summary["results"]["combined"]["base"]["start_ts"],
            "end_ts": summary["results"]["combined"]["base"]["end_ts"],
            "daily_bars": len(candle_payload),
        },
        "metrics": summary["results"]["combined"]["base"],
        "candles": candle_payload,
        "trades": trade_payload,
        "equity": equity_payload,
        "source": {
            "summary": str(summary_path.relative_to(ROOT)),
            "trades": str(trades_path.relative_to(ROOT)),
            "path": str(path_path.relative_to(ROOT)),
            "fetcher": str(FETCHER_PATH.relative_to(ROOT)),
            "fetcher_sha256": hashlib.sha256(FETCHER_PATH.read_bytes()).hexdigest(),
        },
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { color-scheme: dark; --bg:#101318; --panel:#171b22; --grid:#2a313d; --text:#e6edf3; --muted:#9aa7b2; --long:#40c463; --short:#ff6b6b; --ma:#ffd166; --eq:#58a6ff; }
body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
header { padding:22px 28px 12px; border-bottom:1px solid #242b35; }
h1 { margin:0 0 8px; font-size:22px; letter-spacing:.2px; }
.summary { display:flex; gap:18px; flex-wrap:wrap; color:var(--muted); }
.summary b { color:var(--text); }
main { padding:18px 24px 28px; }
.panel { background:var(--panel); border:1px solid #252d38; border-radius:12px; padding:14px; margin-bottom:16px; }
.controls { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:10px; color:var(--muted); }
button { background:#212936; border:1px solid #344052; color:var(--text); border-radius:8px; padding:6px 10px; cursor:pointer; }
button:hover { border-color:#60708a; }
input[type=range] { width:220px; }
svg { width:100%; height:520px; display:block; background:#11151b; border-radius:8px; cursor:grab; touch-action:none; }
svg.dragging { cursor:grabbing; }
.axis text { fill:var(--muted); font-size:11px; }
.axis line,.grid line { stroke:var(--grid); stroke-width:1; }
.wick { stroke-width:1.2; }
.candle.up { fill:#2ea043; stroke:#2ea043; }
.candle.down { fill:#f85149; stroke:#f85149; }
.ma { fill:none; stroke:var(--ma); stroke-width:1.6; }
.equity { fill:none; stroke:var(--eq); stroke-width:1.8; }
.trade-line.long { stroke:var(--long); }
.trade-line.short { stroke:var(--short); }
.trade-line { stroke-width:2.1; opacity:.9; }
.marker.long { fill:var(--long); }
.marker.short { fill:var(--short); }
.selected { filter: drop-shadow(0 0 6px white); stroke-width:3.5 !important; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th,td { padding:7px 8px; border-bottom:1px solid #27303b; text-align:right; white-space:nowrap; }
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3) { text-align:left; }
tr:hover { background:#202733; cursor:pointer; }
.pos { color:var(--long); } .neg { color:var(--short); }
.note { color:var(--muted); font-size:12px; margin-top:8px; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="summary" id="summary"></div>
</header>
<main>
  <section class="panel">
    <div class="controls">
      <button id="fullBtn">Full window</button>
      <button id="last180Btn">Last 180d</button>
      <label>Start <input id="startRange" type="range" min="0" max="100" value="0"></label>
      <label>End <input id="endRange" type="range" min="0" max="100" value="100"></label>
      <span id="rangeLabel"></span>
    </div>
    <svg id="chart" role="img" aria-label="Candlesticks, MA7, trades and equity"></svg>
    <div class="note">Mouse wheel zooms around the cursor; drag the chart to pan; double-click resets. Click a trade row to zoom around its entry/exit. Green trades are long; red trades are short.</div>
  </section>
  <section class="panel">
    <table id="tradeTable">
      <thead><tr><th>ID</th><th>Side</th><th>Entry</th><th>Exit</th><th>Entry Px</th><th>Exit Px</th><th>Net</th><th>Bars</th><th>Reason</th></tr></thead>
      <tbody></tbody>
    </table>
  </section>
</main>
<script>
const DATA = __DATA__;
const svg = document.getElementById('chart');
const startRange = document.getElementById('startRange');
const endRange = document.getElementById('endRange');
const rangeLabel = document.getElementById('rangeLabel');
const candles = DATA.candles;
const trades = DATA.trades;
const equity = DATA.equity;
let selectedId = null;
let startIdx = 0, endIdx = candles.length - 1;
let isDragging = false;
let dragStartX = 0;
let dragWindowStart = 0;
let dragWindowEnd = 0;

function fmtPct(v){ return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'; }
function fmtPx(v){ return v.toLocaleString(undefined,{maximumFractionDigits:2}); }
function setSummary(){
  const m = DATA.metrics;
  document.getElementById('summary').innerHTML =
    `<span>Window <b>${DATA.window.start_ts.slice(0,10)} to ${DATA.window.end_ts.slice(0,10)}</b></span>`+
    `<span>Net <b class="${m.net_return_pct>=0?'pos':'neg'}">${fmtPct(m.net_return_pct)}</b></span>`+
    `<span>MDD <b class="neg">${fmtPct(m.max_drawdown_pct)}</b></span>`+
    `<span>Trades <b>${m.closed_trades}</b></span>`+
    `<span>PF <b>${m.profit_factor.toFixed(2)}</b></span>`;
}
function xScale(ms, w){ const a=candles[startIdx].ts, b=candles[endIdx].ts; return 64 + (ms-a)/(b-a || 1)*(w-108); }
function yScale(v, min, max, top, h){ return top + (max-v)/(max-min || 1)*h; }
function make(tag, attrs){ const el=document.createElementNS('http://www.w3.org/2000/svg', tag); Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v)); return el; }
function title(el, text){ const t=make('title',{}); t.textContent=text; el.appendChild(t); return el; }
function setWindow(start, end){
  let span = Math.max(1, end - start);
  if (span >= candles.length - 1) { startIdx = 0; endIdx = candles.length - 1; render(); return; }
  start = Math.round(start); end = Math.round(end);
  if (start < 0) { end -= start; start = 0; }
  if (end > candles.length - 1) { start -= end - (candles.length - 1); end = candles.length - 1; }
  startIdx = Math.max(0, start);
  endIdx = Math.min(candles.length - 1, Math.max(startIdx + 1, end));
  render();
}
function render(){
  const rect = svg.getBoundingClientRect(); const w=Math.max(900, rect.width); const h=520; svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.innerHTML='';
  if (startIdx >= endIdx) startIdx = Math.max(0, endIdx - 1);
  const visible = candles.slice(startIdx, endIdx+1);
  const startMs = candles[startIdx].ts, endMs = candles[endIdx].ts + 86400000;
  const visibleTrades = trades.filter(t => t.exit_ms >= startMs && t.entry_ms <= endMs);
  const priceVals = visible.flatMap(c=>[c.low,c.high]).concat(visibleTrades.flatMap(t=>[t.entry_price,t.exit_price]));
  const pMin = Math.min(...priceVals)*0.985, pMax = Math.max(...priceVals)*1.015;
  const eVis = equity.filter(e => e.ms >= startMs && e.ms <= endMs);
  const eVals = eVis.map(e=>e.close_equity);
  const eMin = Math.min(...eVals)*0.985, eMax = Math.max(...eVals)*1.015;
  const priceTop=24, priceH=310, eqTop=370, eqH=110;
  for(let i=0;i<6;i++){ const y=priceTop+i*priceH/5; svg.appendChild(make('line',{x1:54,y1:y,x2:w-38,y2:y,class:'grid'})); }
  const candleW = Math.max(2, Math.min(9, (w-120)/visible.length*0.55));
  visible.forEach(c => {
    const x=xScale(c.ts,w), yo=yScale(c.open,pMin,pMax,priceTop,priceH), yc=yScale(c.close,pMin,pMax,priceTop,priceH);
    const yh=yScale(c.high,pMin,pMax,priceTop,priceH), yl=yScale(c.low,pMin,pMax,priceTop,priceH);
    const up=c.close>=c.open;
    svg.appendChild(title(make('line',{x1:x,y1:yh,x2:x,y2:yl,class:'wick',stroke:up?'#2ea043':'#f85149'}), `${c.iso}\nO ${fmtPx(c.open)} H ${fmtPx(c.high)} L ${fmtPx(c.low)} C ${fmtPx(c.close)}`));
    svg.appendChild(make('rect',{x:x-candleW/2,y:Math.min(yo,yc),width:candleW,height:Math.max(1,Math.abs(yc-yo)),class:`candle ${up?'up':'down'}`}));
  });
  const maPts = visible.filter(c=>c.ma7!==null).map(c=>`${xScale(c.ts,w)},${yScale(c.ma7,pMin,pMax,priceTop,priceH)}`).join(' ');
  svg.appendChild(title(make('polyline',{points:maPts,class:'ma'}),'SMA7'));
  visibleTrades.forEach(t => {
    const cls=t.side==='long'?'long':'short';
    const line=make('line',{x1:xScale(t.entry_ms,w),y1:yScale(t.entry_price,pMin,pMax,priceTop,priceH),x2:xScale(t.exit_ms,w),y2:yScale(t.exit_price,pMin,pMax,priceTop,priceH),class:`trade-line ${cls} ${selectedId===t.id?'selected':''}`});
    svg.appendChild(title(line, `${t.id} ${t.side}\n${t.entry_ts} -> ${t.exit_ts}\nNet ${fmtPct(t.net_return_pct)}\n${t.exit_reason}`));
    svg.appendChild(title(make('circle',{cx:xScale(t.entry_ms,w),cy:yScale(t.entry_price,pMin,pMax,priceTop,priceH),r:4,class:`marker ${cls}`}), `${t.id} entry ${fmtPx(t.entry_price)}`));
    svg.appendChild(title(make('rect',{x:xScale(t.exit_ms,w)-4,y:yScale(t.exit_price,pMin,pMax,priceTop,priceH)-4,width:8,height:8,class:`marker ${cls}`}), `${t.id} exit ${fmtPx(t.exit_price)}`));
  });
  const eqPts = eVis.map(e=>`${xScale(e.ms,w)},${yScale(e.close_equity,eMin,eMax,eqTop,eqH)}`).join(' ');
  svg.appendChild(title(make('polyline',{points:eqPts,class:'equity'}),'Equity curve'));
  svg.appendChild(make('text',{x:56,y:18,fill:'#9aa7b2'})).textContent = `Price / SMA7 / trades (${visible.length} daily bars shown)`;
  svg.appendChild(make('text',{x:56,y:eqTop-10,fill:'#9aa7b2'})).textContent = 'Equity';
  rangeLabel.textContent = `${candles[startIdx].iso.slice(0,10)} -> ${candles[endIdx].iso.slice(0,10)}`;
  startRange.value = startIdx; endRange.value = endIdx;
}
function renderTable(){
  const body = document.querySelector('#tradeTable tbody'); body.innerHTML='';
  trades.forEach(t => {
    const tr=document.createElement('tr'); tr.dataset.id=t.id;
    tr.innerHTML = `<td>${t.id}</td><td class="${t.side}">${t.side}</td><td>${t.entry_ts.slice(0,10)}</td><td>${t.exit_ts.slice(0,10)}</td><td>${fmtPx(t.entry_price)}</td><td>${fmtPx(t.exit_price)}</td><td class="${t.net_return_pct>=0?'pos':'neg'}">${fmtPct(t.net_return_pct)}</td><td>${t.bars_held}</td><td>${t.exit_reason}</td>`;
    tr.onclick = () => { selectedId=t.id; const si=Math.max(0,candles.findIndex(c=>c.ts>=t.entry_ms)-20); const ei=Math.min(candles.length-1,candles.findIndex(c=>c.ts>=t.exit_ms)+20); startIdx=si; endIdx=ei; render(); };
    body.appendChild(tr);
  });
}
startRange.max = candles.length - 1; endRange.max = candles.length - 1;
startRange.oninput = () => { startIdx = Number(startRange.value); render(); };
endRange.oninput = () => { endIdx = Number(endRange.value); render(); };
document.getElementById('fullBtn').onclick = () => { selectedId=null; startIdx=0; endIdx=candles.length-1; render(); };
document.getElementById('last180Btn').onclick = () => { selectedId=null; endIdx=candles.length-1; startIdx=Math.max(0,endIdx-180); render(); };
svg.addEventListener('wheel', (event) => {
  event.preventDefault();
  selectedId = null;
  const rect = svg.getBoundingClientRect();
  const plotLeft = 64;
  const plotRight = Math.max(plotLeft + 1, rect.width - 38);
  const frac = Math.min(1, Math.max(0, (event.clientX - rect.left - plotLeft) / (plotRight - plotLeft)));
  const span = Math.max(2, endIdx - startIdx);
  const factor = event.deltaY < 0 ? 0.78 : 1.28;
  const newSpan = Math.max(10, Math.min(candles.length - 1, Math.round(span * factor)));
  const anchor = startIdx + span * frac;
  setWindow(anchor - newSpan * frac, anchor + newSpan * (1 - frac));
}, { passive:false });
svg.addEventListener('pointerdown', (event) => {
  isDragging = true;
  dragStartX = event.clientX;
  dragWindowStart = startIdx;
  dragWindowEnd = endIdx;
  svg.classList.add('dragging');
  svg.setPointerCapture(event.pointerId);
});
svg.addEventListener('pointermove', (event) => {
  if (!isDragging) return;
  const rect = svg.getBoundingClientRect();
  const plotWidth = Math.max(1, rect.width - 102);
  const span = Math.max(1, dragWindowEnd - dragWindowStart);
  const deltaIndex = Math.round(-(event.clientX - dragStartX) / plotWidth * span);
  setWindow(dragWindowStart + deltaIndex, dragWindowEnd + deltaIndex);
});
function stopDrag(event){
  if (!isDragging) return;
  isDragging = false;
  svg.classList.remove('dragging');
  if (event.pointerId !== undefined) {
    try { svg.releasePointerCapture(event.pointerId); } catch (_) {}
  }
}
svg.addEventListener('pointerup', stopDrag);
svg.addEventListener('pointercancel', stopDrag);
svg.addEventListener('mouseleave', stopDrag);
svg.addEventListener('dblclick', () => { selectedId=null; setWindow(0, candles.length - 1); });
window.addEventListener('resize', render);
setSummary(); renderTable(); render();
</script>
</body>
</html>
"""


def render_html(payload: dict[str, Any], output_path: Path) -> None:
    html = HTML_TEMPLATE.replace("__TITLE__", f"{payload['symbol']} Shared MA7 V1 Trade Path").replace(
        "__DATA__",
        json.dumps(payload, ensure_ascii=False, allow_nan=False),
    )
    output_path.write_text(html, encoding="utf-8")


def main() -> None:
    fetcher = load_module(FETCHER_PATH, "shared_ma7_v1_fetcher")
    configs = [
        ("BTCUSDT", "binance_ma7_shared_params_on_btc_hype_aligned", "binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html"),
        ("ETHUSDT", "binance_ma7_shared_params_on_eth_hype_aligned", "binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html"),
    ]
    for symbol, stem, html_name in configs:
        payload = build_payload(symbol, stem, fetcher)
        output_path = ARTIFACT_DIR / html_name
        render_html(payload, output_path)
        print(output_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
