from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
    simulate_trades_live_cost,
)
from research_hype_5m_pbtr_v3_ablation_audit import V3_CONFIG, filtered_signal, month_slices
from research_hype_5m_positive_payoff_search import load_all_hype_5m
from research_hype_5m_indicator_search import Trade, add_features


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("reports/hype_5m_pbtr_v31_min_hold_9.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v31_min_hold_9_summary.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v31_min_hold_9_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v31_min_hold_9_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v31_min_hold_9_monthly.csv")
TRADES_PATH = Path("reports/hype_5m_pbtr_v31_min_hold_9_trades.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v31-min-hold-9-2026-06-24.md"
)
HTML_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v31-min-hold-9-trade-path-2026-06-24.html"
)

V31_CONFIG = replace(V3_CONFIG, name="HYPE-5M-PBTR-V3.1", min_hold_bars=9)


def evaluate(frame: pd.DataFrame, cfg_name: str, cfg: Any) -> tuple[dict[str, Any], list[Trade], np.ndarray]:
    signal = filtered_signal(frame, cfg, final_filter=False)
    trades = simulate_trades_live_cost(frame, signal, cfg)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    summary = {
        "label": cfg_name,
        "signal_count": int(np.count_nonzero(signal)),
        **metrics,
    }
    return summary, trades, signal


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def trades_frame(frame: pd.DataFrame, label: str, trades: list[Trade]) -> pd.DataFrame:
    idx_by_ts = {pd.Timestamp(ts).value: idx for idx, ts in enumerate(frame["ts"])}
    rows: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades):
        entry_idx = idx_by_ts[pd.Timestamp(trade.entry_ts).value]
        exit_idx = idx_by_ts[pd.Timestamp(trade.exit_ts).value]
        rows.append(
            {
                "label": label,
                "trade_no": idx + 1,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": int(trade.side),
                "entry_idx": int(entry_idx),
                "exit_idx": int(exit_idx),
                "bars_held": int(trade.bars_held),
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "net_ret_1x": float(trade.net_ret_1x),
                "mae_1x": float(trade.mae_1x),
                "mfe_1x": float(trade.mfe_1x),
                "reason": trade.reason,
            }
        )
    return pd.DataFrame(rows)


def equity_points(trades: list[Trade], *, max_points: int = 2400) -> list[dict[str, Any]]:
    points = [{"ts": str(trades[0].entry_ts) if trades else "", "equity": 1.0, "drawdown": 0.0, "trade_no": 0}]
    equity = 1.0
    peak = 1.0
    for idx, trade in enumerate(trades, start=1):
        equity *= max(0.001, 1.0 + float(trade.net_ret_1x))
        peak = max(peak, equity)
        points.append(
            {
                "ts": str(trade.exit_ts),
                "equity": float(equity),
                "drawdown": float(equity / peak - 1.0),
                "trade_no": idx,
            }
        )
    if len(points) <= max_points:
        return points
    keep_idx = np.unique(np.linspace(0, len(points) - 1, max_points).astype(int))
    return [points[int(idx)] for idx in keep_idx]


def time_slice_rows(frame: pd.DataFrame, label: str, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame):
        rolling_rows.append(
            {
                "label": label,
                "window": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"]),
            }
        )
    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        weekly_rows.append(
            {
                "label": label,
                "window": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"]),
            }
        )
    monthly_rows: list[dict[str, Any]] = []
    for item in month_slices(frame):
        monthly_rows.append(
            {
                "label": label,
                "window": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"]),
            }
        )
    return pd.DataFrame(rolling_rows), pd.DataFrame(weekly_rows), pd.DataFrame(monthly_rows)


def trade_path_samples(frame: pd.DataFrame, trade_df: pd.DataFrame, *, max_samples: int = 12) -> list[dict[str, Any]]:
    close = frame["close"].to_numpy("float64")
    ts = frame["ts"].astype(str).to_numpy()
    selected = pd.concat(
        [
            trade_df.sort_values("net_ret_1x", ascending=False).head(4),
            trade_df.sort_values("net_ret_1x").head(4),
            trade_df.iloc[(trade_df["net_ret_1x"].abs()).argsort()[:4]],
        ],
        ignore_index=True,
    ).drop_duplicates(subset=["trade_no"]).head(max_samples)

    samples: list[dict[str, Any]] = []
    for row in selected.to_dict(orient="records"):
        entry_idx = int(row["entry_idx"])
        exit_idx = int(row["exit_idx"])
        side = int(row["side"])
        idx = np.arange(entry_idx, exit_idx + 1)
        if len(idx) == 0:
            continue
        entry_price = float(row["entry_price"])
        norm = side * (close[idx] / entry_price - 1.0)
        samples.append(
            {
                "trade_no": int(row["trade_no"]),
                "side": "long" if side > 0 else "short",
                "entry_ts": str(row["entry_ts"]),
                "exit_ts": str(row["exit_ts"]),
                "bars_held": int(row["bars_held"]),
                "net_ret": float(row["net_ret_1x"]),
                "mae": float(row["mae_1x"]),
                "mfe": float(row["mfe_1x"]),
                "points": [
                    {"x": int(i - entry_idx), "ts": str(ts[i]), "ret": float(ret)}
                    for i, ret in zip(idx, norm, strict=False)
                ],
            }
        )
    return samples


def monthly_bars(monthly: pd.DataFrame, label: str) -> list[dict[str, Any]]:
    sub = monthly.loc[monthly["label"] == label].copy()
    return [
        {
            "window": str(row["window"]),
            "return": float(row["total_return"]),
            "drawdown": float(row["max_dd"]),
            "trades": int(row["trades"]),
            "win_rate": float(row["win_rate"]),
        }
        for row in sub.to_dict(orient="records")
    ]


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HYPE-5M-PBTR-V3.1 交易路径图</title>
  <style>
    :root {{
      --bg: #0c0d0f;
      --panel: #15171b;
      --panel2: #1d2026;
      --text: #ebe7dc;
      --muted: #a8a197;
      --grid: #343842;
      --v3: #7aa2ff;
      --v31: #f3c969;
      --loss: #ef6f6c;
      --good: #78d39d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: -0.03em; }}
    h2 {{ margin: 26px 0 12px; font-size: 18px; }}
    p {{ margin: 0 0 12px; color: var(--muted); }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 22px 0; }}
    .card, .chart {{
      background: linear-gradient(180deg, var(--panel), var(--panel2));
      border: 1px solid #2c3038;
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.24);
    }}
    .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    canvas {{ width: 100%; height: 360px; display: block; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border-bottom: 1px solid #2c3038; padding: 8px 6px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .legend {{ display: flex; gap: 16px; color: var(--muted); margin-bottom: 6px; }}
    .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
    .small {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 900px) {{ .cards, .grid {{ grid-template-columns: 1fr; }} main {{ padding: 18px; }} }}
  </style>
</head>
<body>
<main>
  <h1>HYPE-5M-PBTR-V3.1 交易路径图</h1>
  <p>V3.1 = V3 + <code>min_hold_bars=9</code>。所有结果沿用线上实盘成本：手续费 4.1466 bps/成交额，开仓滑点 +10.73 bps，平仓滑点 -2.64 bps。</p>
  <section class="cards" id="cards"></section>
  <section class="grid">
    <div class="chart">
      <h2>闭合交易权益曲线（log10）</h2>
      <div class="legend"><span><i class="dot" style="background:var(--v3)"></i>V3</span><span><i class="dot" style="background:var(--v31)"></i>V3.1</span></div>
      <canvas id="equity"></canvas>
      <p class="small">按每笔平仓后权益复利绘制，纵轴为 log10(equity)。</p>
    </div>
    <div class="chart">
      <h2>回撤路径</h2>
      <div class="legend"><span><i class="dot" style="background:var(--v3)"></i>V3</span><span><i class="dot" style="background:var(--v31)"></i>V3.1</span></div>
      <canvas id="drawdown"></canvas>
      <p class="small">按闭合交易权益峰值计算回撤。</p>
    </div>
  </section>
  <section class="grid">
    <div class="chart">
      <h2>月度复利收益</h2>
      <canvas id="monthly"></canvas>
    </div>
    <div class="chart">
      <h2>V3.1 代表性交易路径</h2>
      <canvas id="paths"></canvas>
      <p class="small">展示 V3.1 最优、最差和接近零收益交易的持仓内方向化价格路径。</p>
    </div>
  </section>
  <section class="chart">
    <h2>关键指标</h2>
    <table id="summary"></table>
  </section>
</main>
<script>
const DATA = {data};

function pct(x, d=2) {{ return (x * 100).toFixed(d) + '%'; }}
function mult(x, d=2) {{ return Number.isFinite(x) ? x.toFixed(d) + 'x' : '∞'; }}
function fmt(x, d=2) {{ return Number.isFinite(x) ? x.toFixed(d) : '∞'; }}

function setup(canvas) {{
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {{ctx, w: rect.width, h: rect.height}};
}}

function drawAxes(ctx, w, h, yLabel) {{
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#343842';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {{
    const y = 24 + (h - 54) * i / 4;
    ctx.beginPath(); ctx.moveTo(42, y); ctx.lineTo(w - 16, y); ctx.stroke();
  }}
  ctx.fillStyle = '#a8a197';
  ctx.font = '12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
  ctx.fillText(yLabel, 42, 14);
}}

function lineChart(id, series, accessor, opts={{}}) {{
  const canvas = document.getElementById(id);
  const {{ctx, w, h}} = setup(canvas);
  const all = series.flatMap(s => s.points.map(accessor)).filter(Number.isFinite);
  const min = opts.min ?? Math.min(...all);
  const max = opts.max ?? Math.max(...all);
  drawAxes(ctx, w, h, opts.label || '');
  const left = 42, right = w - 16, top = 24, bottom = h - 30;
  function x(i, n) {{ return left + (right - left) * i / Math.max(1, n - 1); }}
  function y(v) {{ return bottom - (bottom - top) * (v - min) / Math.max(1e-12, max - min); }}
  for (const s of series) {{
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    s.points.forEach((p, i) => {{
      const px = x(i, s.points.length);
      const py = y(accessor(p));
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();
  }}
  ctx.fillStyle = '#a8a197';
  ctx.fillText(fmt(min), 4, bottom);
  ctx.fillText(fmt(max), 4, top + 4);
}}

function barChart() {{
  const canvas = document.getElementById('monthly');
  const {{ctx, w, h}} = setup(canvas);
  drawAxes(ctx, w, h, 'return');
  const left = 42, right = w - 16, top = 24, bottom = h - 40;
  const months = DATA.monthly.v31;
  const max = Math.max(...months.map(m => m.return));
  const bw = (right - left) / months.length;
  months.forEach((m, i) => {{
    const x = left + i * bw + 3;
    const y = bottom - (bottom - top) * m.return / max;
    ctx.fillStyle = m.return >= 0 ? '#f3c969' : '#ef6f6c';
    ctx.fillRect(x, y, Math.max(2, bw - 6), bottom - y);
    if (i % 2 === 0) {{
      ctx.save(); ctx.translate(x + 4, bottom + 12); ctx.rotate(-0.45);
      ctx.fillStyle = '#a8a197'; ctx.font = '10px sans-serif'; ctx.fillText(m.window, 0, 0); ctx.restore();
    }}
  }});
}}

function pathChart() {{
  const canvas = document.getElementById('paths');
  const {{ctx, w, h}} = setup(canvas);
  const paths = DATA.pathSamples;
  const vals = paths.flatMap(p => p.points.map(q => q.ret));
  const min = Math.min(...vals), max = Math.max(...vals);
  drawAxes(ctx, w, h, 'directional return');
  const left = 42, right = w - 16, top = 24, bottom = h - 30;
  function x(i, n) {{ return left + (right - left) * i / Math.max(1, n - 1); }}
  function y(v) {{ return bottom - (bottom - top) * (v - min) / Math.max(1e-12, max - min); }}
  paths.forEach((p, idx) => {{
    ctx.strokeStyle = p.net_ret >= 0 ? `rgba(120,211,157,${{0.35 + idx/30}})` : `rgba(239,111,108,${{0.35 + idx/30}})`;
    ctx.lineWidth = p.net_ret >= 0 ? 2 : 1.4;
    ctx.beginPath();
    p.points.forEach((q, i) => {{
      const px = x(i, p.points.length);
      const py = y(q.ret);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();
  }});
  ctx.strokeStyle = '#a8a197'; ctx.setLineDash([4,4]);
  const zy = y(0); ctx.beginPath(); ctx.moveTo(left, zy); ctx.lineTo(right, zy); ctx.stroke(); ctx.setLineDash([]);
}}

function renderCards() {{
  const s = DATA.summary.v31;
  const cards = [
    ['V3.1 交易数', s.trades],
    ['V3.1 年化', mult(s.annualized_multiple)],
    ['V3.1 最大回撤', pct(s.max_dd)],
    ['V3.1 胜率 / PF', pct(s.win_rate) + ' / ' + fmt(s.profit_factor)]
  ];
  document.getElementById('cards').innerHTML = cards.map(c => `<div class="card"><div class="label">${{c[0]}}</div><div class="value">${{c[1]}}</div></div>`).join('');
}}

function renderSummary() {{
  const rows = [DATA.summary.v3, DATA.summary.v31];
  document.getElementById('summary').innerHTML = `
    <tr><th>版本</th><th>交易数</th><th>权益倍数</th><th>年化</th><th>胜率</th><th>payoff</th><th>PF</th><th>最大回撤</th></tr>
    ${{rows.map(r => `<tr><td>${{r.label}}</td><td>${{r.trades}}</td><td>${{mult(r.equity_multiple)}}</td><td>${{mult(r.annualized_multiple)}}</td><td>${{pct(r.win_rate)}}</td><td>${{fmt(r.payoff_ratio)}}</td><td>${{fmt(r.profit_factor)}}</td><td>${{pct(r.max_dd)}}</td></tr>`).join('')}}
  `;
}}

function drawAll() {{
  renderCards();
  renderSummary();
  lineChart('equity', [
    {{points: DATA.equity.v3, color: '#7aa2ff'}},
    {{points: DATA.equity.v31, color: '#f3c969'}}
  ], p => Math.log10(Math.max(1e-9, p.equity)), {{label: 'log10 equity'}});
  lineChart('drawdown', [
    {{points: DATA.equity.v3, color: '#7aa2ff'}},
    {{points: DATA.equity.v31, color: '#f3c969'}}
  ], p => p.drawdown, {{label: 'drawdown', min: Math.min(...DATA.equity.v3.map(p=>p.drawdown), ...DATA.equity.v31.map(p=>p.drawdown)), max: 0}});
  barChart();
  pathChart();
}}
window.addEventListener('resize', drawAll);
drawAll();
</script>
</body>
</html>
"""


def render_markdown(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    weekly: pd.DataFrame,
    monthly: pd.DataFrame,
    html_path: Path,
) -> str:
    v3 = summary.loc[summary["label"] == "HYPE-5M-PBTR-V3"].iloc[0]
    v31 = summary.loc[summary["label"] == "HYPE-5M-PBTR-V3.1"].iloc[0]
    v31_recent = rolling.loc[rolling["label"].eq("HYPE-5M-PBTR-V3.1")].copy()
    weekly_v31 = weekly.loc[weekly["label"].eq("HYPE-5M-PBTR-V3.1")].copy()
    monthly_v31 = monthly.loc[monthly["label"].eq("HYPE-5M-PBTR-V3.1")].copy()
    worst_week = weekly_v31.sort_values("total_return").iloc[0]
    worst_month = monthly_v31.sort_values("total_return").iloc[0]
    best_month = monthly_v31.sort_values("total_return", ascending=False).iloc[0]
    lines = [
        "# HYPE-5M-PBTR-V3.1 Min Hold 9 回测 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "V3.1 定义：在 `HYPE-5M-PBTR-V3` 基础上将 `min_hold_bars` 从 `6` 提高到 `9`，其他参数不变；final HTF 仍关闭。",
        "",
        "## 成本与数据",
        "",
        "- 成本口径：线上实盘统计成本。",
        f"- 手续费：`{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`。",
        f"- 开仓滑点：`{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 平仓滑点：`{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 净滑点：`{NET_SLIPPAGE_RATE_ON_TURNOVER * 10000:+.4f} bps/总成交额`。",
        "- 数据：Binance HYPEUSDT 永续 `5m`，截至 `2026-06-23 04:20 UTC`。",
        "",
        "## V3 vs V3.1",
        "",
        "| 版本 | `min_hold_bars` | 交易数 | 权益倍数 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `HYPE-5M-PBTR-V3` | `6` | `{int(v3['trades'])}` | `{mult(float(v3['equity_multiple']))}` | `{mult(float(v3['annualized_multiple']))}` | `{pct(float(v3['win_rate']))}` | `{num(float(v3['payoff_ratio']))}` | `{num(float(v3['profit_factor']))}` | `{pct(float(v3['max_dd']))}` |",
        f"| `HYPE-5M-PBTR-V3.1` | `9` | `{int(v31['trades'])}` | `{mult(float(v31['equity_multiple']))}` | `{mult(float(v31['annualized_multiple']))}` | `{pct(float(v31['win_rate']))}` | `{num(float(v31['payoff_ratio']))}` | `{num(float(v31['profit_factor']))}` | `{pct(float(v31['max_dd']))}` |",
        "",
        "V3.1 样本内显著优于 V3：交易数减少，但胜率、payoff、PF 和复利权益都明显抬升；代价是最大回撤从约 `-7.95%` 扩到约 `-10.03%`。",
        "",
        "## 时间切片",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in v31_recent.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "周/月摘要：",
            "",
            f"- 周数：`{len(weekly_v31)}`，盈利周 `{int((weekly_v31['total_return'] > 0).sum())}/{len(weekly_v31)}`，中位周收益 `{pct(float(weekly_v31['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`。",
            f"- 月数：`{len(monthly_v31)}`，盈利月 `{int((monthly_v31['total_return'] > 0).sum())}/{len(monthly_v31)}`，中位月收益 `{pct(float(monthly_v31['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 交易路径图",
            "",
            f"- HTML：`{html_path}`",
            "",
            "HTML 图包含 V3/V3.1 闭合交易权益曲线、回撤路径、V3.1 月度复利收益，以及 V3.1 最优/最差/接近零收益的代表性交易持仓路径。",
            "",
            "## 审计结论",
            "",
            "`min_hold_bars=9` 在样本内是强增强项，不只是参数微调。它减少了更早被 trailing stop 震出的交易，让顺风路径有更多时间展开，因此胜率和 payoff 同时提高。但它也推迟风险释放，最大回撤扩大到约 `-10%`。由于该结果来自 V3 的样本内消融发现，不能直接提升为生产版本；更适合记为 `HYPE-5M-PBTR-V3.1` 研究候选，并用小资金/paper 跑 `300-500` 笔验证。",
            "",
            "## 产物",
            "",
            f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v31_min_hold_9.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 滚动切片：`{ROLLING_PATH}`",
            f"- 周切片：`{WEEKLY_PATH}`",
            f"- 月切片：`{MONTHLY_PATH}`",
            f"- 交易明细：`{TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = add_features(load_all_hype_5m())
    frame = frame.loc[frame["ts"] <= END_TS].reset_index(drop=True)

    v3_summary, v3_trades, _ = evaluate(frame, "HYPE-5M-PBTR-V3", V3_CONFIG)
    v31_summary, v31_trades, _ = evaluate(frame, "HYPE-5M-PBTR-V3.1", V31_CONFIG)
    summaries = pd.DataFrame([v3_summary, v31_summary])
    summaries["equity_multiple"] = summaries["equity_multiple"].astype(float)

    rolling_frames: list[pd.DataFrame] = []
    weekly_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    for label, trades in (("HYPE-5M-PBTR-V3", v3_trades), ("HYPE-5M-PBTR-V3.1", v31_trades)):
        rolling, weekly, monthly = time_slice_rows(frame, label, trades)
        rolling_frames.append(rolling)
        weekly_frames.append(weekly)
        monthly_frames.append(monthly)
    rolling = pd.concat(rolling_frames, ignore_index=True)
    weekly = pd.concat(weekly_frames, ignore_index=True)
    monthly = pd.concat(monthly_frames, ignore_index=True)
    v31_trade_df = trades_frame(frame, "HYPE-5M-PBTR-V3.1", v31_trades)

    payload = {
        "summary": {
            "v3": {
                "label": "V3",
                "trades": int(v3_summary["trades"]),
                "equity_multiple": float(v3_summary["equity_multiple"]),
                "annualized_multiple": float(v3_summary["annualized_multiple"]),
                "win_rate": float(v3_summary["win_rate"]),
                "payoff_ratio": float(v3_summary["payoff_ratio"]),
                "profit_factor": float(v3_summary["profit_factor"]),
                "max_dd": float(v3_summary["max_dd"]),
            },
            "v31": {
                "label": "V3.1",
                "trades": int(v31_summary["trades"]),
                "equity_multiple": float(v31_summary["equity_multiple"]),
                "annualized_multiple": float(v31_summary["annualized_multiple"]),
                "win_rate": float(v31_summary["win_rate"]),
                "payoff_ratio": float(v31_summary["payoff_ratio"]),
                "profit_factor": float(v31_summary["profit_factor"]),
                "max_dd": float(v31_summary["max_dd"]),
            },
        },
        "equity": {
            "v3": equity_points(v3_trades),
            "v31": equity_points(v31_trades),
        },
        "monthly": {
            "v3": monthly_bars(monthly, "HYPE-5M-PBTR-V3"),
            "v31": monthly_bars(monthly, "HYPE-5M-PBTR-V3.1"),
        },
        "pathSamples": trade_path_samples(frame, v31_trade_df),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summaries.to_csv(SUMMARY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    v31_trade_df.to_csv(TRADES_PATH, index=False)
    HTML_PATH.write_text(render_html(payload), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(summaries, rolling, weekly, monthly, HTML_PATH), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.1",
                "definition": {
                    "base": "HYPE-5M-PBTR-V3",
                    "change": "min_hold_bars 6 -> 9",
                    "config": asdict(V31_CONFIG),
                },
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "html": str(HTML_PATH),
                    "summary": str(SUMMARY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "trades": str(TRADES_PATH),
                },
                "summary": summaries.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"html={HTML_PATH}")
    print(summaries.to_string(index=False))


if __name__ == "__main__":
    main()
