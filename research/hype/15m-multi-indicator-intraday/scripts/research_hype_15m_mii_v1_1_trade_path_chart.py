from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_clean_evolution as evolution  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    build_market_arrays,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.1"
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_1_trade_path_chart.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
HTML_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_1_trade_paths_2026-06-30.html"
TRADES_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_1_trades_2026-06-30.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_1_trade_paths_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-1-trade-paths-2026-06-30.md"

BASE_CONFIG = evolution.CleanConfig(
    rsi_window=7,
    rsi_low=40.0,
    rsi_high=60.0,
    min_atr_pct96=0.0075,
    min_rvol96=1.0,
    h1_confirm=False,
    rsi14_band=False,
    take_profit_pct=0.012,
    stop_pct=0.036,
    max_hold_bars=16,
    exposure=2.0,
)
ENTRY_DELAY_BARS = 1
CONTEXT_BEFORE_BARS = 48
CONTEXT_AFTER_BARS = 32


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def build_context() -> tuple[evolution.EvalContext, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    frame, metadata, quality = v1.load_data_lake()
    features = evolution.add_rsi_features(evolution.add_features(frame, []))
    context = evolution.EvalContext(
        features=features,
        market=build_market_arrays(features),
        start_ts=pd.Timestamp(features["ts"].min()),
        end_ts=pd.Timestamp(features["ts"].max()) + pd.Timedelta(minutes=15),
        signal_cache={},
        trade_cache=OrderedDict(),
    )
    v1.engine.simulate_trades = v1.simulate_trades_live
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live
    return context, features, metadata, quality


def equity_curve(trade_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    equity = 1.0
    peak = 1.0
    rows = [{"trade_no": 0, "ts": None, "equity": equity, "drawdown": 0.0}]
    for row in trade_rows:
        equity *= 1.0 + float(row["net_return"])
        peak = max(peak, equity)
        rows.append(
            {
                "trade_no": row["trade_no"],
                "ts": row["exit_ts"],
                "equity": equity,
                "drawdown": equity / peak - 1.0,
            }
        )
    return rows


def build_trade_payload() -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    context, features, metadata, quality = build_context()
    state = signal_state(features, BASE_CONFIG.signal)
    raw_trades = v1.simulate_trades_live(
        context.market,
        state,
        BASE_CONFIG.exit,
        entry_delay_bars=ENTRY_DELAY_BARS,
    )
    selected = v1.selected_trades_live(raw_trades, BASE_CONFIG.filter)
    metrics = evolution.evaluate_window(
        context,
        BASE_CONFIG,
        raw_trades,
        context.start_ts,
        context.end_ts,
        purge_end=False,
    )

    trade_rows: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    for trade_no, trade in enumerate(selected, start=1):
        signal_ts = features["ts"].iloc[trade.signal_i]
        net_return = float(BASE_CONFIG.exposure * (trade.raw_return - ROUND_TRIP_COST))
        trade_row = {
            "trade_no": trade_no,
            "signal_ts": str(signal_ts),
            "entry_ts": str(trade.entry_ts),
            "exit_ts": str(trade.exit_ts),
            "side": "long" if trade.direction == 1 else "short",
            "direction": int(trade.direction),
            "exit_reason": str(trade.exit_reason),
            "bars_held": int(trade.bars_held),
            "entry_price": float(trade.entry_price),
            "exit_price": float(trade.exit_price),
            "raw_return": float(trade.raw_return),
            "net_return": net_return,
            "mae_2x": float(BASE_CONFIG.exposure * trade.min_path_return),
            "mfe_2x": float(BASE_CONFIG.exposure * trade.max_path_return),
            "signal_rsi7": finite(features["rsi7"].iloc[trade.signal_i]),
            "signal_macd_hist": finite(features["macd_12_26_9_hist"].iloc[trade.signal_i]),
            "signal_atr_pct96": finite(features["atr_pct96"].iloc[trade.signal_i]),
            "signal_rvol96": finite(features["rvol96"].iloc[trade.signal_i]),
        }
        trade_rows.append(trade_row)

        start_i = max(0, int(trade.signal_i) - CONTEXT_BEFORE_BARS)
        end_i = min(len(features) - 1, int(trade.exit_i) + CONTEXT_AFTER_BARS)
        local = features.iloc[start_i : end_i + 1]
        bars = []
        for i, row in zip(range(start_i, end_i + 1), local.itertuples(index=False), strict=False):
            bars.append(
                {
                    "i": int(i),
                    "ts": str(row.ts),
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "rsi7": finite(getattr(row, "rsi7")),
                    "macd": finite(getattr(row, "macd_12_26_9")),
                    "macd_signal": finite(getattr(row, "macd_12_26_9_signal")),
                    "macd_hist": finite(getattr(row, "macd_12_26_9_hist")),
                }
            )
        windows.append(
            {
                "trade_no": trade_no,
                "bars": bars,
                "signal_i": int(trade.signal_i),
                "entry_i": int(trade.entry_i),
                "exit_i": int(trade.exit_i),
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "net_return": net_return,
                "exit_reason": str(trade.exit_reason),
            }
        )

    returns = np.array([row["net_return"] for row in trade_rows], dtype="float64")
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    summary = {
        "family": FAMILY,
        "alias": ALIAS,
        "version": VERSION,
        "engine_name": BASE_CONFIG.name,
        "entry_timing": "K+1 open",
        "start_ts": context.start_ts.isoformat(),
        "end_ts": context.end_ts.isoformat(),
        "trades": int(metrics["trades"]),
        "annual_return_pct": float(metrics["annual_return_pct"]),
        "total_return_pct": float(metrics["total_return_pct"]),
        "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
        "win_rate_pct": float(metrics["win_rate_pct"]),
        "profit_factor": float(metrics["profit_factor"]),
        "avg_trade_pct": float(returns.mean() * 100.0) if len(returns) else 0.0,
        "worst_trade_pct": float(returns.min() * 100.0) if len(returns) else 0.0,
        "best_trade_pct": float(returns.max() * 100.0) if len(returns) else 0.0,
        "computed_profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
        "parameters": {
            "signal": "RSI(7) cross 40/60 reversal",
            "macd_periods": evolution.FIXED_MACD_PERIODS,
            "min_dir_macd": 0.0,
            "min_atr_pct96": BASE_CONFIG.min_atr_pct96,
            "max_atr_pct96": evolution.MAX_ATR_PCT_GUARDRAIL,
            "min_rvol96": BASE_CONFIG.min_rvol96,
            "take_profit_pct": BASE_CONFIG.take_profit_pct,
            "stop_pct": BASE_CONFIG.stop_pct,
            "max_hold_bars": BASE_CONFIG.max_hold_bars,
            "exposure": BASE_CONFIG.exposure,
            "commission_per_fill": COMMISSION_PER_SIDE,
            "slippage_per_fill": SLIPPAGE_PER_SIDE,
            "round_trip_cost": ROUND_TRIP_COST,
        },
    }
    payload = {
        "summary": summary,
        "data_quality": quality,
        "metadata": metadata,
        "trades": trade_rows,
        "windows": windows,
        "equity": equity_curve(trade_rows),
    }
    return payload, pd.DataFrame(trade_rows), quality


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HYPE-15M-MII-V1.1 Trade Paths</title>
  <style>
    :root {
      --bg: #0b0d10;
      --panel: #151a20;
      --panel2: #1f252d;
      --text: #efe9dc;
      --muted: #a9a197;
      --grid: #303744;
      --up: #78d99b;
      --down: #ef7676;
      --accent: #f2c86b;
      --blue: #83aaff;
      --purple: #c792ea;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 1600px; margin: 0 auto; padding: 28px; }
    h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: -0.03em; }
    h2 { margin: 0 0 10px; font-size: 17px; }
    p { color: var(--muted); margin: 0 0 16px; }
    code { color: var(--accent); }
    .cards { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }
    .card, .panel { background: linear-gradient(180deg, var(--panel), var(--panel2)); border: 1px solid #2c3440; border-radius: 14px; padding: 14px; box-shadow: 0 14px 40px rgba(0,0,0,.22); }
    .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
    .value { font-size: 20px; font-weight: 760; margin-top: 5px; }
    .layout { display: grid; grid-template-columns: 1.65fr .9fr; gap: 14px; align-items: start; }
    canvas { width: 100%; height: 740px; display: block; background: #10141a; border-radius: 10px; }
    .toolbar { display:flex; gap:8px; align-items:center; margin-bottom:10px; flex-wrap: wrap; }
    button, select { background:#202733; color:var(--text); border:1px solid #3b4657; border-radius:8px; padding:7px 10px; }
    button { cursor:pointer; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 6px 5px; border-bottom: 1px solid #2b333f; text-align: right; white-space: nowrap; }
    th:first-child, td:first-child { text-align: left; }
    tr { cursor: pointer; }
    tr.active { background: rgba(242, 200, 107, .13); }
    .table-wrap { max-height: 740px; overflow: auto; }
    .good { color: var(--up); }
    .bad { color: var(--down); }
    .small { font-size: 12px; color: var(--muted); }
    @media (max-width: 1100px) { .cards { grid-template-columns: 1fr 1fr; } .layout { grid-template-columns: 1fr; } main { padding: 16px; } }
  </style>
</head>
<body>
<main>
  <h1>HYPE-15M-MII-V1.1 交易路径图</h1>
  <p><code>RSI(7)</code> 反转 + <code>MACD(12,26,9)</code> 方向确认 + <code>ATR/RVOL</code> 过滤。每笔交易展示局部 15m K 线、入场/出场连线、RSI 与 MACD。</p>
  <section class="cards" id="cards"></section>
  <section class="layout">
    <div class="panel">
      <div class="toolbar">
        <button id="prev">上一笔</button>
        <select id="tradeSelect"></select>
        <button id="next">下一笔</button>
        <span class="small" id="tradeMeta"></span>
      </div>
      <canvas id="chart"></canvas>
      <p class="small">上：15m K 线与入场/出场；中：RSI(7)，虚线为 40/60；下：MACD 线、signal 线与 histogram。窗口含信号前 48 根和出场后 32 根 K。</p>
    </div>
    <div class="panel">
      <h2>交易列表</h2>
      <div class="table-wrap"><table id="trades"></table></div>
    </div>
  </section>
</main>
<script>
const DATA = __DATA__;
let current = 0;

function pct(x, d=2) { return (x * 100).toFixed(d) + '%'; }
function pctValue(x, d=2) { return Number(x).toFixed(d) + '%'; }
function fmt(x, d=3) { return Number.isFinite(x) ? x.toFixed(d) : 'n/a'; }
function valOr(arr, fallback=0) { return arr.filter(v => v !== null && Number.isFinite(v)); }

function setup(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {ctx, w: rect.width, h: rect.height};
}

function renderCards() {
  const s = DATA.summary;
  const cards = [
    ['Trades', String(s.trades)],
    ['Annual / Total', pctValue(s.annual_return_pct) + ' / ' + pctValue(s.total_return_pct)],
    ['Max DD', pctValue(s.max_drawdown_pct)],
    ['Win / PF', pctValue(s.win_rate_pct) + ' / ' + fmt(s.profit_factor)],
    ['Avg / Worst', pctValue(s.avg_trade_pct) + ' / ' + pctValue(s.worst_trade_pct)],
    ['Cost', '0.28% round-trip']
  ];
  document.getElementById('cards').innerHTML = cards.map(c => `<div class="card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div></div>`).join('');
}

function renderTradeControls() {
  const select = document.getElementById('tradeSelect');
  select.innerHTML = DATA.trades.map((t, i) => `<option value="${i}">#${t.trade_no} ${t.entry_ts.slice(0,16)} ${t.side} ${pct(t.net_return)}</option>`).join('');
  select.onchange = () => { current = Number(select.value); draw(); };
  document.getElementById('prev').onclick = () => { current = Math.max(0, current - 1); draw(); };
  document.getElementById('next').onclick = () => { current = Math.min(DATA.trades.length - 1, current + 1); draw(); };
}

function renderTradeTable() {
  const rows = DATA.trades.map((t, i) => {
    const cls = t.net_return >= 0 ? 'good' : 'bad';
    return `<tr data-i="${i}"><td>#${t.trade_no}</td><td>${t.entry_ts.slice(0,16)}</td><td>${t.side}</td><td>${t.exit_reason}</td><td>${t.bars_held}</td><td class="${cls}">${pct(t.net_return)}</td><td>${fmt(t.signal_rsi7, 1)}</td><td>${fmt(t.signal_macd_hist, 5)}</td></tr>`;
  }).join('');
  document.getElementById('trades').innerHTML = `<tr><th>#</th><th>entry</th><th>side</th><th>exit</th><th>bars</th><th>ret</th><th>RSI</th><th>hist</th></tr>${rows}`;
  document.querySelectorAll('#trades tr[data-i]').forEach(row => {
    row.onclick = () => { current = Number(row.dataset.i); draw(); };
  });
}

function drawAxes(ctx, area, minV, maxV, ticks, formatter) {
  ctx.strokeStyle = '#303744';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#a9a197';
  ctx.font = '12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
  for (let i = 0; i <= ticks; i++) {
    const y = area.top + (area.bottom - area.top) * i / ticks;
    ctx.beginPath(); ctx.moveTo(area.left, y); ctx.lineTo(area.right, y); ctx.stroke();
    const v = maxV - (maxV - minV) * i / ticks;
    ctx.fillText(formatter(v), 5, y + 4);
  }
}

function drawLine(ctx, bars, area, yFn, xFn, key, color, width=1.4) {
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath();
  let started = false;
  bars.forEach((b, i) => {
    const v = b[key];
    if (v === null || !Number.isFinite(v)) return;
    if (!started) { ctx.moveTo(xFn(i), yFn(v)); started = true; } else ctx.lineTo(xFn(i), yFn(v));
  });
  if (started) ctx.stroke();
}

function draw() {
  document.getElementById('tradeSelect').value = String(current);
  document.querySelectorAll('#trades tr').forEach(r => r.classList.remove('active'));
  const active = document.querySelector(`#trades tr[data-i="${current}"]`);
  if (active) active.classList.add('active');

  const t = DATA.trades[current];
  const wdata = DATA.windows[current];
  const bars = wdata.bars;
  document.getElementById('tradeMeta').textContent = `#${t.trade_no} ${t.side} ${t.exit_reason} bars=${t.bars_held} ret=${pct(t.net_return)} RSI=${fmt(t.signal_rsi7,1)} hist=${fmt(t.signal_macd_hist,5)}`;

  const canvas = document.getElementById('chart');
  const {ctx, w, h} = setup(canvas);
  ctx.clearRect(0, 0, w, h);

  const left = 58, right = w - 18;
  const price = {left, right, top: 22, bottom: h * 0.53};
  const rsi = {left, right, top: h * 0.58, bottom: h * 0.74};
  const macd = {left, right, top: h * 0.79, bottom: h - 34};
  const step = (right - left) / Math.max(1, bars.length - 1);
  const candleW = Math.max(2, Math.min(8, step * 0.58));
  const x = i => left + i * step;

  const prices = bars.flatMap(b => [b.high, b.low]).concat([wdata.entry_price, wdata.exit_price]);
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  const pPad = (maxP - minP) * 0.08 || maxP * 0.01;
  const pMin = minP - pPad, pMax = maxP + pPad;
  const yP = value => price.bottom - (price.bottom - price.top) * (value - pMin) / Math.max(1e-12, pMax - pMin);
  drawAxes(ctx, price, pMin, pMax, 5, v => v.toFixed(3));

  bars.forEach((b, i) => {
    const xx = x(i);
    const up = b.close >= b.open;
    ctx.strokeStyle = up ? '#78d99b' : '#ef7676';
    ctx.fillStyle = up ? 'rgba(120,217,155,.88)' : 'rgba(239,118,118,.88)';
    ctx.beginPath(); ctx.moveTo(xx, yP(b.high)); ctx.lineTo(xx, yP(b.low)); ctx.stroke();
    const o = yP(b.open), c = yP(b.close);
    ctx.fillRect(xx - candleW / 2, Math.min(o, c), candleW, Math.max(1, Math.abs(c - o)));
  });

  const entryIdx = bars.findIndex(b => b.i === wdata.entry_i);
  const exitIdx = bars.findIndex(b => b.i === wdata.exit_i);
  const ex = x(entryIdx), ey = yP(wdata.entry_price);
  const xx = x(exitIdx), xy = yP(wdata.exit_price);
  ctx.strokeStyle = '#f2c86b'; ctx.lineWidth = 2.4;
  ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(xx, xy); ctx.stroke();
  ctx.fillStyle = '#f2c86b'; ctx.beginPath(); ctx.arc(ex, ey, 5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = t.net_return >= 0 ? '#78d99b' : '#ef7676'; ctx.beginPath(); ctx.arc(xx, xy, 5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#efe9dc'; ctx.fillText(`ENTRY ${wdata.entry_price.toFixed(3)}`, ex + 7, ey - 8);
  ctx.fillText(`EXIT ${wdata.exit_price.toFixed(3)}`, xx + 7, xy - 8);

  const rsiValues = valOr(bars.map(b => b.rsi7));
  const rMin = Math.max(0, Math.min(30, ...rsiValues) - 4);
  const rMax = Math.min(100, Math.max(70, ...rsiValues) + 4);
  const yR = value => rsi.bottom - (rsi.bottom - rsi.top) * (value - rMin) / Math.max(1e-12, rMax - rMin);
  drawAxes(ctx, rsi, rMin, rMax, 3, v => v.toFixed(0));
  [40, 60].forEach(level => {
    ctx.setLineDash([5, 5]); ctx.strokeStyle = '#f2c86b'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(left, yR(level)); ctx.lineTo(right, yR(level)); ctx.stroke(); ctx.setLineDash([]);
  });
  drawLine(ctx, bars, rsi, yR, x, 'rsi7', '#f2c86b', 1.8);
  ctx.fillStyle = '#efe9dc'; ctx.fillText('RSI(7)', left + 4, rsi.top + 14);

  const macdValues = valOr(bars.flatMap(b => [b.macd, b.macd_signal, b.macd_hist]));
  const mAbs = Math.max(1e-9, ...macdValues.map(v => Math.abs(v))) * 1.15;
  const yM = value => macd.bottom - (macd.bottom - macd.top) * (value + mAbs) / (2 * mAbs);
  drawAxes(ctx, macd, -mAbs, mAbs, 4, v => v.toFixed(4));
  ctx.strokeStyle = '#a9a197'; ctx.beginPath(); ctx.moveTo(left, yM(0)); ctx.lineTo(right, yM(0)); ctx.stroke();
  bars.forEach((b, i) => {
    if (b.macd_hist === null || !Number.isFinite(b.macd_hist)) return;
    ctx.fillStyle = b.macd_hist >= 0 ? 'rgba(120,217,155,.65)' : 'rgba(239,118,118,.65)';
    const zero = yM(0), yy = yM(b.macd_hist);
    ctx.fillRect(x(i) - candleW / 2, Math.min(zero, yy), candleW, Math.max(1, Math.abs(zero - yy)));
  });
  drawLine(ctx, bars, macd, yM, x, 'macd', '#83aaff', 1.6);
  drawLine(ctx, bars, macd, yM, x, 'macd_signal', '#c792ea', 1.4);
  ctx.fillStyle = '#efe9dc'; ctx.fillText('MACD(12,26,9)', left + 4, macd.top + 14);
}

renderCards();
renderTradeControls();
renderTradeTable();
draw();
window.addEventListener('resize', draw);
</script>
</body>
</html>
"""
    return template.replace("__DATA__", data)


def render_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# HYPE-15M-MII V1.1 交易路径图 {RUN_DATE}",
            "",
            f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
            "",
            "`HYPE-15M-MII-V1.1` 是 `V1base` 的干净参数登记版；本图用于逐笔检查价格路径、RSI(7) 触发位置和 MACD(12,26,9) 方向过滤是否符合预期。",
            "",
            "## 汇总",
            "",
            "| 交易数 | 年化 | 总收益 | 最大回撤 | 胜率 | PF | 平均单笔 | 最差单笔 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| `{summary['trades']}` | `{summary['annual_return_pct']:.2f}%` | `{summary['total_return_pct']:.2f}%` | `{summary['max_drawdown_pct']:.2f}%` | `{summary['win_rate_pct']:.2f}%` | `{summary['profit_factor']:.3f}` | `{summary['avg_trade_pct']:.3f}%` | `{summary['worst_trade_pct']:.3f}%` |",
            "",
            "## HTML 图",
            "",
            f"- HTML：`{HTML_PATH}`",
            "- 内容：每笔交易的局部 15m K 线、入场/出场连线、RSI(7) 与 40/60 阈值、MACD(12,26,9) 线/signal/histogram。",
            "",
            "## 状态",
            "",
            "本图只用于 `V1.1` diagnostic inspection，不改变 `NO-GO` 状态。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- trades CSV：`{TRADES_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    ) + "\n"


def main() -> None:
    payload, trades_df, _quality = build_trade_payload()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(TRADES_PATH, index=False)
    HTML_PATH.write_text(render_html(payload), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "alias": ALIAS,
                "version": VERSION,
                "run_date": RUN_DATE,
                "status": "v1_1_trade_paths_diagnostic_not_promoted",
                "summary": payload["summary"],
                "data_quality": payload["data_quality"],
                "outputs": {
                    "html": str(HTML_PATH),
                    "trades": str(TRADES_PATH),
                    "markdown": str(MARKDOWN_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(payload["summary"]), encoding="utf-8")
    print(f"html={HTML_PATH}")
    print(f"trades={TRADES_PATH}")
    print(f"markdown={MARKDOWN_PATH}")
    print(pd.DataFrame([payload["summary"]]).to_string(index=False))


if __name__ == "__main__":
    main()
