from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
HISTORY_PATH = FAMILY_DIR / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
STEM = "binance_1d_ma7_as_search_v2"
EXPECTED_DEVELOPMENT = {
    "BTCUSDT": {
        "equity_multiple": 6.3164,
        "max_drawdown_pct": -52.80,
        "closed_trades": 117,
    },
    "ETHUSDT": {
        "equity_multiple": 6.0161,
        "max_drawdown_pct": -56.76,
        "closed_trades": 116,
    },
}
RECENT_SLICES = (
    ("1d", 1),
    ("7d", 7),
    ("1m", 30),
    ("3m", 91),
    ("6m", 182),
    ("1y", 365),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze Binance-1D-MA7-Asset-Specific-Search V2 (P2-C parent) "
            "and render BTC/ETH trade-path HTML from the frozen P0 snapshot."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def v2_configs(history: Any, engine: Any) -> tuple[Any, Any]:
    long_config, short_config = history.v1_configs(engine)
    return replace(long_config, entry_mode="pullback_reclaim"), short_config


def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "start_ts",
        "end_ts",
        "days",
        "equity_multiple",
        "net_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "closed_trades",
        "long_trades",
        "short_trades",
        "win_rate",
        "profit_factor",
        "turnover_multiple",
        "cost_pct_initial",
        "funding_pct_initial",
        "max_intraday_leverage",
        "bankrupt_intraday",
    )
    return {key: metrics[key] for key in keys}


def recent_bounds(
    book: Any,
    *,
    start: int,
    end: int,
) -> dict[str, tuple[int, int]]:
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    end_ts = pd.Timestamp(timestamps[end])
    output: dict[str, tuple[int, int]] = {}
    for name, days in RECENT_SLICES:
        target = end_ts - pd.Timedelta(days=days)
        left = int(timestamps.searchsorted(target, side="left"))
        left = max(start, min(left, end - 1))
        output[name] = (left, end)
    return output


def candles_from_book(
    book: Any,
    features: Any,
    *,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    rows: list[dict[str, Any]] = []
    last_complete = min(end, book.count)
    for index in range(start, last_complete):
        ts = pd.Timestamp(timestamps[index])
        ma7 = float(features.ma7[index])
        rows.append(
            {
                "ts": int(ts.timestamp() * 1000),
                "iso": ts.isoformat(),
                "open": float(book.open[index]),
                "high": float(book.high[index]),
                "low": float(book.low[index]),
                "close": float(book.close[index]),
                "ma7": None if not math.isfinite(ma7) else ma7,
            }
        )
    terminal = pd.Timestamp(timestamps[end])
    terminal_open = float(book.quality["terminal_open"]) if end == book.count else float(
        book.open[end]
    )
    rows.append(
        {
            "ts": int(terminal.timestamp() * 1000),
            "iso": terminal.isoformat(),
            "open": terminal_open,
            "high": terminal_open,
            "low": terminal_open,
            "close": terminal_open,
            "ma7": None,
        }
    )
    return rows


def trade_payload(symbol: str, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, trade in enumerate(trades, start=1):
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        entry_ms = int(entry_ts.timestamp() * 1000)
        exit_ms = int(exit_ts.timestamp() * 1000)
        if entry_ms > exit_ms:
            raise RuntimeError(f"{symbol} trade {index} has entry after exit")
        trade_id = f"{symbol}-{index:03d}"
        if trade_id in seen:
            raise RuntimeError(f"duplicate trade id {trade_id}")
        seen.add(trade_id)
        payload.append(
            {
                "id": trade_id,
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": exit_ts.isoformat(),
                "entry_ms": entry_ms,
                "exit_ms": exit_ms,
                "side": trade["side"],
                "entry_price": float(trade["entry_price"]),
                "exit_price": float(trade["exit_price"]),
                "bars_held": int(trade["bars_held"]),
                "exit_reason": trade["exit_reason"],
                "net_return_pct": float(trade["net_return"]) * 100.0,
                "net_pnl": float(trade["net_pnl"]),
            }
        )
    return payload


def equity_payload(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ts": row["ts"],
            "ms": int(pd.Timestamp(row["ts"]).timestamp() * 1000),
            "close_equity": float(row["close_equity"]),
            "post_action_equity": float(row["post_action_equity"]),
            "position": int(row["position"]),
            "action": row["action"],
        }
        for row in path
    ]


def assert_development(symbol: str, metrics: dict[str, Any]) -> None:
    expected = EXPECTED_DEVELOPMENT[symbol]
    multiple = round(float(metrics["equity_multiple"]), 4)
    drawdown = round(float(metrics["max_drawdown_pct"]), 2)
    trades = int(metrics["closed_trades"])
    if multiple != expected["equity_multiple"]:
        raise RuntimeError(
            f"{symbol} development multiple {multiple} != {expected['equity_multiple']}"
        )
    if drawdown != expected["max_drawdown_pct"]:
        raise RuntimeError(
            f"{symbol} development MDD {drawdown} != {expected['max_drawdown_pct']}"
        )
    if trades != expected["closed_trades"]:
        raise RuntimeError(
            f"{symbol} development trades {trades} != {expected['closed_trades']}"
        )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
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
      <button id="fullBtn">全窗</button>
      <button id="last180Btn">最近 180 日</button>
      <label>Start <input id="startRange" type="range" min="0" max="100" value="0"></label>
      <label>End <input id="endRange" type="range" min="0" max="100" value="100"></label>
      <span id="rangeLabel"></span>
    </div>
    <svg id="chart" role="img" aria-label="Candlesticks, MA7, trades and equity"></svg>
    <div class="note">滚轮缩放，拖动平移，双击恢复全窗。点击交易表聚焦该笔入场—出场。绿色为多，红色为空。K 线、SMA7 与交易来自同一冻结 P0 回测。</div>
  </section>
  <section class="panel">
    <table id="tradeTable">
      <thead><tr><th>ID</th><th>方向</th><th>入场</th><th>出场</th><th>入场价</th><th>出场价</th><th>净收益</th><th>持仓日</th><th>原因</th></tr></thead>
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
    `<span>窗口 <b>${DATA.window.start_ts.slice(0,10)} 至 ${DATA.window.end_ts.slice(0,10)}</b></span>`+
    `<span>净值 <b class="${m.net_return_pct>=0?'pos':'neg'}">${fmtPct(m.net_return_pct)}</b></span>`+
    `<span>MDD <b class="neg">${fmtPct(m.max_drawdown_pct)}</b></span>`+
    `<span>交易 <b>${m.closed_trades}</b></span>`+
    `<span>PF <b>${Number.isFinite(m.profit_factor)?m.profit_factor.toFixed(2):'n/a'}</b></span>`;
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
  svg.appendChild(title(make('polyline',{points:eqPts,class:'equity'}),'权益曲线'));
  svg.appendChild(make('text',{x:56,y:18,fill:'#9aa7b2'})).textContent = `价格 / SMA7 / 交易连线（显示 ${visible.length} 根日K）`;
  svg.appendChild(make('text',{x:56,y:eqTop-10,fill:'#9aa7b2'})).textContent = '权益';
  rangeLabel.textContent = `${candles[startIdx].iso.slice(0,10)} -> ${candles[endIdx].iso.slice(0,10)}`;
  startRange.value = startIdx; endRange.value = endIdx;
}
function renderTable(){
  const body = document.querySelector('#tradeTable tbody'); body.innerHTML='';
  trades.forEach(t => {
    const tr=document.createElement('tr'); tr.dataset.id=t.id;
    tr.innerHTML = `<td>${t.id}</td><td class="${t.side}">${t.side}</td><td>${t.entry_ts.slice(0,10)}</td><td>${t.exit_ts.slice(0,10)}</td><td>${fmtPx(t.entry_price)}</td><td>${fmtPx(t.exit_price)}</td><td class="${t.net_return_pct>=0?'pos':'neg'}">${fmtPct(t.net_return_pct)}</td><td>${t.bars_held}</td><td>${t.exit_reason}</td>`;
    tr.onclick = () => { selectedId=t.id; const si=Math.max(0,candles.findIndex(c=>c.ts>=t.entry_ms)-20); const ei=Math.min(candles.length-1,candles.findIndex(c=>c.ts>=t.exit_ms)+20); startIdx=si; endIdx=Math.max(startIdx+1, ei); render(); };
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
    html = (
        HTML_TEMPLATE.replace(
            "__TITLE__",
            f"{payload['symbol']} MA7-AS-SEARCH V2 交易路径",
        ).replace(
            "__DATA__",
            json.dumps(payload, ensure_ascii=False, allow_nan=False),
        )
    )
    output_path.write_text(html, encoding="utf-8")
    text = output_path.read_text(encoding="utf-8")
    if "__DATA__" in text or "__TITLE__" in text:
        raise RuntimeError(f"template placeholder remains in {output_path.name}")


def verify_chart_payload(payload: dict[str, Any]) -> None:
    trades = payload["trades"]
    closed = int(payload["metrics"]["closed_trades"])
    if closed != len(trades):
        raise RuntimeError(
            f"{payload['symbol']} chart trades {len(trades)} != closed_trades {closed}"
        )
    ids = [row["id"] for row in trades]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"{payload['symbol']} duplicate trade ids")
    if any(row["entry_ms"] > row["exit_ms"] for row in trades):
        raise RuntimeError(f"{payload['symbol']} entry after exit")
    if any("entry_price" not in row or "exit_price" not in row for row in trades):
        raise RuntimeError(f"{payload['symbol']} trade missing endpoints")
    if not payload["candles"]:
        raise RuntimeError(f"{payload['symbol']} empty candles")
    if not payload["equity"]:
        raise RuntimeError(f"{payload['symbol']} empty equity path")


def main() -> None:
    args = parse_args()
    spec = importlib.util.spec_from_file_location(
        "ma7_v1_long_history",
        HISTORY_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {HISTORY_PATH}")
    history = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)

    transfer = history.load_module(
        history.TRANSFER_PATH,
        history.TRANSFER_SHA256,
        "btc_eth_ma7_v2_transfer",
    )
    engine = transfer.load_engine()
    long_config, short_config = v2_configs(history, engine)
    if args.self_test:
        v1_long, v1_short = history.v1_configs(engine)
        assert asdict(long_config)["entry_mode"] == "pullback_reclaim"
        assert asdict(v1_long)["entry_mode"] == "reclaim"
        assert asdict(short_config) == asdict(v1_short)
        assert history.DEVELOPMENT_END > history.COMMON_START
        print("self-test: PASS")
        return

    manifest = json.loads(history.P0_MANIFEST.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "version": "V2",
        "alias": "BIN-1D-MA7-AS-SEARCH-V2",
        "status": "registered / HARD-GATE-FAILED / not promoted / not live-ready",
        "identity": "P2-C parent: V1 shared params with long entry_mode=pullback_reclaim",
        "evidence_role": (
            "development is the frozen selection window; "
            "audit/full_history are researcher-exposed and not clean OOS"
        ),
        "contract": {
            "common_start": history.COMMON_START.isoformat(),
            "development_end_exclusive": history.DEVELOPMENT_END.isoformat(),
            "expected_terminal": history.EXPECTED_TERMINAL.isoformat(),
            "fee_per_fill": engine.FEE,
            "base_slippage_per_fill": engine.BASE_SLIPPAGE,
            "stress_slippage_per_fill": engine.STRESS_SLIPPAGE,
            "execution": "closed UTC day signal, next open; real 1h stop path",
            "positioning": "about 1x after fills, fixed quantity while held",
            "source_manifest": str(history.P0_MANIFEST.relative_to(ROOT)),
        },
        "v2": {
            "long_config": asdict(long_config),
            "short_config": asdict(short_config),
        },
        "assets": {},
    }
    metric_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    chart_files: list[Path] = []
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    for symbol, slug in history.ASSETS.items():
        hourly, funding, quality = history.load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        if pd.Timestamp(book.terminal_ts) != history.EXPECTED_TERMINAL:
            raise RuntimeError(f"{symbol}: terminal drift {book.terminal_ts}")
        features = engine.build_features(book, hourly, funding)
        starts = {
            "development": history.boundary(book, history.COMMON_START),
            "researcher_exposed_audit": history.boundary(
                book, history.DEVELOPMENT_END
            ),
            "full_history": history.boundary(book, history.COMMON_START),
        }
        ends = {
            "development": history.boundary(book, history.DEVELOPMENT_END),
            "researcher_exposed_audit": book.count,
            "full_history": book.count,
        }
        asset_payload: dict[str, Any] = {
            "data_quality": quality,
            "terminal_open": book.quality["terminal_open"],
            "windows": {},
            "recent_slices": {},
        }
        retained = None
        for window in starts:
            asset_payload["windows"][window] = {}
            for variant, long_leg, short_leg in (
                ("combined", long_config, short_config),
                ("long_only", long_config, None),
                ("short_only", None, short_config),
            ):
                stresses = {
                    "base": (engine.BASE_SLIPPAGE, 0),
                    "stress_8bps": (engine.STRESS_SLIPPAGE, 0),
                    "one_day_extra_delay": (engine.BASE_SLIPPAGE, 1),
                }
                asset_payload["windows"][window][variant] = {}
                for stress, (slippage, lag) in stresses.items():
                    retain = (
                        window == "full_history"
                        and variant == "combined"
                        and stress == "base"
                    )
                    result = history.run_window(
                        engine,
                        book,
                        features,
                        long_leg,
                        short_leg,
                        start=starts[window],
                        end=ends[window],
                        slippage=slippage,
                        signal_lag=lag,
                        retain=retain,
                    )
                    metrics = compact_metrics(result.metrics)
                    asset_payload["windows"][window][variant][stress] = metrics
                    metric_rows.append(
                        {
                            "symbol": symbol,
                            "window": window,
                            "variant": variant,
                            "stress": stress,
                            **metrics,
                        }
                    )
                    if retain:
                        retained = result
                        for trade in result.trades:
                            trade_rows.append({"symbol": symbol, **trade})
                        for row in result.path:
                            path_rows.append({"symbol": symbol, **row})
        if retained is None:
            raise RuntimeError(f"{symbol}: missing retained full-history path")
        assert_development(
            symbol,
            asset_payload["windows"]["development"]["combined"]["base"],
        )
        for name, (left, right) in recent_bounds(
            book,
            start=starts["full_history"],
            end=ends["full_history"],
        ).items():
            slice_result = history.run_window(
                engine,
                book,
                features,
                long_config,
                short_config,
                start=left,
                end=right,
                slippage=engine.BASE_SLIPPAGE,
                signal_lag=0,
                retain=False,
            )
            asset_payload["recent_slices"][name] = compact_metrics(
                slice_result.metrics
            )
            metric_rows.append(
                {
                    "symbol": symbol,
                    "window": f"recent_{name}",
                    "variant": "combined",
                    "stress": "base",
                    **compact_metrics(slice_result.metrics),
                }
            )

        chart_trades = trade_payload(symbol, retained.trades)
        chart_equity = equity_payload(retained.path)
        chart_candles = candles_from_book(
            book,
            features,
            start=starts["full_history"],
            end=ends["full_history"],
        )
        chart_payload = {
            "symbol": symbol,
            "version": "BIN-1D-MA7-AS-SEARCH-V2",
            "status": payload["status"],
            "generated_at_utc": payload["generated_at_utc"],
            "window": {
                "start_ts": retained.metrics["start_ts"],
                "end_ts": retained.metrics["end_ts"],
                "daily_bars": len(chart_candles),
            },
            "metrics": compact_metrics(retained.metrics),
            "candles": chart_candles,
            "trades": chart_trades,
            "equity": chart_equity,
        }
        verify_chart_payload(chart_payload)
        slug_name = "btc" if symbol == "BTCUSDT" else "eth"
        html_path = (
            ARTIFACT_DIR
            / f"{STEM}_{slug_name}_trade_path_{args.run_date}.html"
        )
        render_html(chart_payload, html_path)
        chart_files.append(html_path)
        asset_payload["chart"] = {
            "html": str(html_path.relative_to(ROOT)),
            "closed_trades": len(chart_trades),
            "daily_bars": len(chart_candles),
            "equity_rows": len(chart_equity),
        }
        payload["assets"][symbol] = asset_payload

    payload["hard_target"] = {
        symbol: {
            "equity_multiple_gte_20": (
                payload["assets"][symbol]["windows"]["development"]["combined"][
                    "base"
                ]["equity_multiple"]
                >= 20.0
            ),
            "mdd_within_20pct": (
                payload["assets"][symbol]["windows"]["development"]["combined"][
                    "base"
                ]["max_drawdown_pct"]
                >= -20.0
            ),
        }
        for symbol in history.ASSETS
    }
    payload["hard_target"]["all_pass"] = all(
        row["equity_multiple_gte_20"] and row["mdd_within_20pct"]
        for key, row in payload["hard_target"].items()
        if key != "all_pass"
    )

    summary_path = ARTIFACT_DIR / f"{STEM}_{args.run_date}.json"
    metrics_path = ARTIFACT_DIR / f"{STEM}_{args.run_date}_metrics.csv"
    trades_path = ARTIFACT_DIR / f"{STEM}_{args.run_date}_trades.csv"
    path_path = ARTIFACT_DIR / f"{STEM}_{args.run_date}_path.csv"
    summary_path.write_text(
        json.dumps(history.clean_json(payload), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    write_csv(metrics_path, history.clean_json(metric_rows))
    write_csv(trades_path, history.clean_json(trade_rows))
    write_csv(path_path, history.clean_json(path_rows))
    digest_path = ARTIFACT_DIR / f"{STEM}_trade_paths_{args.run_date}.sha256"
    lines = []
    for path in [summary_path, metrics_path, trades_path, path_path, *chart_files]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
        print(path)
    digest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(digest_path)
    if payload["hard_target"]["all_pass"]:
        raise RuntimeError("V2 unexpectedly passed the 20x / MDD<=20% hard target")


if __name__ == "__main__":
    main()
