from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v6 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_full_ablation.py", "hype_pbtr_v6_full_for_v61")

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

HTML_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_trade_paths_{RUN_DATE}.html"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_trades_{RUN_DATE}.csv"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_summary_{RUN_DATE}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v6-1-trade-paths-{RUN_DATE}.md"

V61_LEVERAGE = 3.0


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def equity_metrics(returns: np.ndarray) -> dict[str, float]:
    equity = np.cumprod(1.0 + returns)
    equity_with_start = np.r_[1.0, equity]
    peak = np.maximum.accumulate(equity_with_start)
    dd = equity_with_start / peak - 1.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "trades": float(len(returns)),
        "total_return": float(equity[-1] - 1.0) if len(equity) else 0.0,
        "max_dd": float(dd.min()) if len(dd) else 0.0,
        "avg_trade": float(returns.mean()) if len(returns) else 0.0,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "payoff_ratio": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.inf,
        "worst_trade": float(returns.min()) if len(returns) else 0.0,
        "best_trade": float(returns.max()) if len(returns) else 0.0,
    }


def compute_equity_points(trade_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    equity = 1.0
    peak = 1.0
    points = [{"i": 0, "ts": None, "equity": equity, "drawdown": 0.0}]
    for i, row in enumerate(trade_rows, start=1):
        equity *= 1.0 + float(row["net_ret_3x"])
        peak = max(peak, equity)
        points.append({"i": i, "ts": row["exit_ts"], "equity": equity, "drawdown": equity / peak - 1.0})
    return points


def build_trade_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    cfg = replace(v6.BASELINE, tp_atr=2.5)
    raw = v6.load_closed_frame()
    frame = v6.add_required_features(raw)
    signal, raw_signal_count = v6.build_filtered_signal(frame, cfg)
    trades = v6.simulate_live_orders(frame, signal, v6.signal_spec(cfg), v6.exit_spec(cfg), label="HYPE-5M-PBTR-V6.1")
    ts = pd.to_datetime(frame["ts"], utc=True)
    ts_to_i = {pd.Timestamp(value): i for i, value in enumerate(ts)}

    trade_rows: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    for trade_no, trade in enumerate(trades, start=1):
        signal_i = ts_to_i[pd.Timestamp(trade.signal_ts)]
        entry_i = ts_to_i[pd.Timestamp(trade.entry_ts)]
        exit_i = ts_to_i[pd.Timestamp(trade.exit_ts)]
        start_i = max(0, signal_i - 24)
        end_i = min(len(frame) - 1, exit_i + 24)
        local = frame.iloc[start_i : end_i + 1]
        bars = [
            {
                "i": int(i),
                "ts": str(row.ts),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "ema21": float(row.ema21) if np.isfinite(row.ema21) else None,
                "ema55": float(row.ema55) if np.isfinite(row.ema55) else None,
            }
            for i, row in zip(range(start_i, end_i + 1), local.itertuples(index=False), strict=False)
        ]
        net_ret_3x = float(trade.net_ret_1x * V61_LEVERAGE)
        trade_row = {
            "trade_no": trade_no,
            "signal_ts": trade.signal_ts,
            "entry_ts": trade.entry_ts,
            "exit_ts": trade.exit_ts,
            "side": trade.side,
            "reason": trade.reason,
            "bars_held": trade.bars_held,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "net_ret_1x": trade.net_ret_1x,
            "net_ret_3x": net_ret_3x,
            "mae_1x": trade.mae_1x,
            "mfe_1x": trade.mfe_1x,
            "signal_atr14": float(frame["atr14"].iloc[signal_i]),
            "signal_atr_bps": float(frame["atr14"].iloc[signal_i] / frame["close"].iloc[signal_i] * 10000.0),
            "dir_ret192_bps": float(frame["dir_ret192_bps"].iloc[signal_i]) if "dir_ret192_bps" in frame else np.nan,
        }
        trade_rows.append(trade_row)
        windows.append(
            {
                "trade_no": trade_no,
                "bars": bars,
                "signal_i": signal_i,
                "entry_i": entry_i,
                "exit_i": exit_i,
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "net_ret_3x": net_ret_3x,
                "reason": trade.reason,
            }
        )

    trades_df = pd.DataFrame(trade_rows)
    returns = trades_df["net_ret_3x"].to_numpy("float64")
    summary = {
        "strategy": "HYPE-5M-PBTR-V6.1",
        "base": asdict(cfg),
        "leverage": V61_LEVERAGE,
        "raw_signal_count": raw_signal_count,
        "filtered_signal_count": int(np.count_nonzero(signal)),
        "reason_counts": trades_df["reason"].value_counts().to_dict(),
        **equity_metrics(returns),
    }
    return frame, trades_df, summary, windows


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HYPE-5M-PBTR-V6.1 Trade Paths</title>
  <style>
    :root {{
      --bg: #0b0d10;
      --panel: #15181d;
      --panel2: #1d2229;
      --text: #eee9df;
      --muted: #a9a197;
      --grid: #303641;
      --up: #79d99a;
      --down: #ef7272;
      --accent: #f2c86b;
      --blue: #82aaff;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; letter-spacing: -0.03em; }}
    h2 {{ margin: 0 0 12px; font-size: 17px; }}
    p {{ color: var(--muted); margin: 0 0 16px; }}
    code {{ color: var(--accent); }}
    .cards {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }}
    .card, .panel {{ background: linear-gradient(180deg, var(--panel), var(--panel2)); border: 1px solid #2c323c; border-radius: 14px; padding: 14px; box-shadow: 0 14px 40px rgba(0,0,0,.22); }}
    .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
    .value {{ font-size: 21px; font-weight: 750; margin-top: 5px; }}
    .layout {{ display: grid; grid-template-columns: 1.6fr .9fr; gap: 14px; align-items: start; }}
    canvas {{ width: 100%; height: 560px; display: block; background: #101318; border-radius: 10px; }}
    .toolbar {{ display:flex; gap:8px; align-items:center; margin-bottom:10px; flex-wrap: wrap; }}
    button, select {{ background:#202631; color:var(--text); border:1px solid #394252; border-radius:8px; padding:7px 10px; }}
    button {{ cursor:pointer; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 6px 5px; border-bottom: 1px solid #2b313b; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child {{ text-align: left; }}
    tr {{ cursor: pointer; }}
    tr.active {{ background: rgba(242, 200, 107, .13); }}
    .table-wrap {{ max-height: 560px; overflow: auto; }}
    .good {{ color: var(--up); }}
    .bad {{ color: var(--down); }}
    .small {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 1000px) {{ .cards {{ grid-template-columns: 1fr 1fr; }} .layout {{ grid-template-columns: 1fr; }} main {{ padding: 16px; }} }}
  </style>
</head>
<body>
<main>
  <h1>HYPE-5M-PBTR-V6.1 交易路径图</h1>
  <p>V6.1 = V6 + <code>tp_atr=2.5</code> + fixed <code>3x</code> sizing。每笔交易在局部 5m K 线上展示，入场和出场用黄色线连接。</p>
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
      <p class="small">绿色/红色为 5m K 线，蓝线为 EMA21，灰线为 EMA55，黄线连接同一笔入场与出场。窗口含信号前 24 根和出场后 24 根 K。</p>
    </div>
    <div class="panel">
      <h2>交易列表</h2>
      <div class="table-wrap"><table id="trades"></table></div>
    </div>
  </section>
</main>
<script>
const DATA = {data};
let current = 0;

function pct(x, d=2) {{ return (x * 100).toFixed(d) + '%'; }}
function num(x, d=3) {{ return Number.isFinite(x) ? x.toFixed(d) : '∞'; }}

function setup(canvas) {{
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {{ctx, w: rect.width, h: rect.height}};
}}

function renderCards() {{
  const s = DATA.summary;
  const cards = [
    ['Trades', String(Math.round(s.trades))],
    ['Total Return', pct(s.total_return)],
    ['Max Drawdown', pct(s.max_dd)],
    ['Win / PF', pct(s.win_rate) + ' / ' + num(s.profit_factor)],
    ['Worst / Best', pct(s.worst_trade) + ' / ' + pct(s.best_trade)]
  ];
  document.getElementById('cards').innerHTML = cards.map(c => `<div class="card"><div class="label">${{c[0]}}</div><div class="value">${{c[1]}}</div></div>`).join('');
}}

function renderTradeControls() {{
  const select = document.getElementById('tradeSelect');
  select.innerHTML = DATA.trades.map((t, i) => `<option value="${{i}}">#${{t.trade_no}} ${{t.entry_ts}} ${{pct(t.net_ret_3x)}}</option>`).join('');
  select.onchange = () => {{ current = Number(select.value); draw(); }};
  document.getElementById('prev').onclick = () => {{ current = Math.max(0, current - 1); draw(); }};
  document.getElementById('next').onclick = () => {{ current = Math.min(DATA.trades.length - 1, current + 1); draw(); }};
}}

function renderTradeTable() {{
  const rows = DATA.trades.map((t, i) => {{
    const cls = t.net_ret_3x >= 0 ? 'good' : 'bad';
    return `<tr data-i="${{i}}"><td>#${{t.trade_no}}</td><td>${{t.entry_ts.slice(0,16)}}</td><td>${{t.reason}}</td><td>${{t.bars_held}}</td><td class="${{cls}}">${{pct(t.net_ret_3x)}}</td></tr>`;
  }}).join('');
  document.getElementById('trades').innerHTML = `<tr><th>#</th><th>entry</th><th>exit</th><th>bars</th><th>3x ret</th></tr>${{rows}}`;
  document.querySelectorAll('#trades tr[data-i]').forEach(row => {{
    row.onclick = () => {{ current = Number(row.dataset.i); draw(); }};
  }});
}}

function draw() {{
  document.getElementById('tradeSelect').value = String(current);
  document.querySelectorAll('#trades tr').forEach(r => r.classList.remove('active'));
  const active = document.querySelector(`#trades tr[data-i="${{current}}"]`);
  if (active) active.classList.add('active');
  const t = DATA.trades[current];
  const wdata = DATA.windows[current];
  document.getElementById('tradeMeta').textContent = `#${{t.trade_no}} ${{t.reason}} bars=${{t.bars_held}} 1x=${{pct(t.net_ret_1x)}} 3x=${{pct(t.net_ret_3x)}}`;

  const canvas = document.getElementById('chart');
  const {{ctx, w, h}} = setup(canvas);
  ctx.clearRect(0, 0, w, h);
  const bars = wdata.bars;
  const prices = bars.flatMap(b => [b.high, b.low, b.ema21, b.ema55].filter(v => v !== null && Number.isFinite(v))).concat([wdata.entry_price, wdata.exit_price]);
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  const pad = (maxP - minP) * 0.08 || maxP * 0.01;
  const yMin = minP - pad, yMax = maxP + pad;
  const left = 54, right = w - 18, top = 22, bottom = h - 38;
  const step = (right - left) / Math.max(1, bars.length - 1);
  const candleW = Math.max(2, Math.min(8, step * 0.58));
  function x(idx) {{ return left + idx * step; }}
  function y(price) {{ return bottom - (bottom - top) * (price - yMin) / Math.max(1e-12, yMax - yMin); }}

  ctx.strokeStyle = '#303641';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#a9a197';
  ctx.font = '12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
  for (let i = 0; i <= 5; i++) {{
    const yy = top + (bottom - top) * i / 5;
    ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(right, yy); ctx.stroke();
    const p = yMax - (yMax - yMin) * i / 5;
    ctx.fillText(p.toFixed(3), 5, yy + 4);
  }}

  function lineFor(key, color, width=1.4) {{
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath();
    let started = false;
    bars.forEach((b, i) => {{
      const v = b[key];
      if (v === null || !Number.isFinite(v)) return;
      if (!started) {{ ctx.moveTo(x(i), y(v)); started = true; }} else ctx.lineTo(x(i), y(v));
    }});
    ctx.stroke();
  }}
  lineFor('ema21', '#82aaff', 1.4);
  lineFor('ema55', 'rgba(169,161,151,.65)', 1.2);

  bars.forEach((b, i) => {{
    const xx = x(i);
    const up = b.close >= b.open;
    ctx.strokeStyle = up ? '#79d99a' : '#ef7272';
    ctx.fillStyle = up ? 'rgba(121,217,154,.85)' : 'rgba(239,114,114,.85)';
    ctx.beginPath(); ctx.moveTo(xx, y(b.high)); ctx.lineTo(xx, y(b.low)); ctx.stroke();
    const o = y(b.open), c = y(b.close);
    const topBody = Math.min(o, c), bodyH = Math.max(1, Math.abs(c - o));
    ctx.fillRect(xx - candleW / 2, topBody, candleW, bodyH);
  }});

  const entryIdx = bars.findIndex(b => b.i === wdata.entry_i);
  const exitIdx = bars.findIndex(b => b.i === wdata.exit_i);
  const ex = x(entryIdx), ey = y(wdata.entry_price);
  const xx = x(exitIdx), xy = y(wdata.exit_price);
  ctx.strokeStyle = '#f2c86b'; ctx.lineWidth = 2.4;
  ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(xx, xy); ctx.stroke();
  ctx.fillStyle = '#f2c86b';
  ctx.beginPath(); ctx.arc(ex, ey, 5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = t.net_ret_3x >= 0 ? '#79d99a' : '#ef7272';
  ctx.beginPath(); ctx.arc(xx, xy, 5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#eee9df';
  ctx.fillText(`ENTRY ${{wdata.entry_price.toFixed(3)}}`, ex + 7, ey - 8);
  ctx.fillText(`EXIT ${{wdata.exit_price.toFixed(3)}}`, xx + 7, xy - 8);
}}

renderCards();
renderTradeControls();
renderTradeTable();
draw();
window.addEventListener('resize', draw);
</script>
</body>
</html>
"""


def render_markdown(summary: dict[str, Any], html_path: Path) -> str:
    return "\n".join(
        [
            "# HYPE-5M-PBTR-V6.1 交易路径图 2026-06-27",
            "",
            "Family id：`HYPE-5M-PBTR`",
            "",
            "`HYPE-5M-PBTR-V6.1` 定义为 V6 的 sizing/exit 变体：`tp_atr=2.5`，`sl_atr=7`，`time_exit_bars=36`，不使用 trailing，固定 `3x` 仓位。该版本仍是 paper audit candidate，不是生产 sizing 版本。",
            "",
            "## 结果",
            "",
            "| 交易数 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 单笔最差 | 单笔最好 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| `{int(summary['trades'])}` | `{fmt_pct(float(summary['total_return']))}` | `{fmt_pct(float(summary['win_rate']))}` | `{fmt_num(float(summary['profit_factor']))}` | `{fmt_num(float(summary['payoff_ratio']))}` | `{fmt_pct(float(summary['max_dd']))}` | `{fmt_pct(float(summary['worst_trade']))}` | `{fmt_pct(float(summary['best_trade']))}` |",
            "",
            "## 交易路径图",
            "",
            f"- HTML：`{html_path}`",
            "- HTML 内含每笔交易的局部 5m K 线、EMA21/EMA55、入场点、出场点和入场-出场连线。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- trades CSV：`{TRADES_PATH}`",
            f"- summary CSV：`{SUMMARY_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    ) + "\n"


def main() -> None:
    _frame, trades_df, summary, windows = build_trade_data()
    trade_rows = trades_df.copy()
    trade_rows["signal_ts"] = trade_rows["signal_ts"].astype(str)
    trade_rows["entry_ts"] = trade_rows["entry_ts"].astype(str)
    trade_rows["exit_ts"] = trade_rows["exit_ts"].astype(str)
    equity = compute_equity_points(trade_rows.to_dict(orient="records"))
    payload = {"summary": summary, "trades": trade_rows.to_dict(orient="records"), "windows": windows, "equity": equity}

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(TRADES_PATH, index=False)
    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False)
    HTML_PATH.write_text(render_html(payload), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(summary, HTML_PATH), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.1",
                "definition": {"base": summary["base"], "leverage": V61_LEVERAGE},
                "summary": summary,
                "outputs": {"html": str(HTML_PATH), "markdown": str(MARKDOWN_PATH), "trades": str(TRADES_PATH), "summary": str(SUMMARY_PATH)},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"html={HTML_PATH}")
    print(pd.DataFrame([summary]).to_string(index=False))


if __name__ == "__main__":
    main()
