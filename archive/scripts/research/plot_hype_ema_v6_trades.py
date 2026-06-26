from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import Variant, entry_signal
from research_hype_ema_cross_strategy import SLIPPAGE, TRADE_COST, build_features
from research_hype_ema_regime_hold_v5 import (
    dynamic_allocation,
    load_hype_data_lake,
)


CHART_PATH = Path("archive/reports/legacy/hype_ema_v6_binance_trade_chart.html")
TRADES_PATH = Path("archive/reports/legacy/hype_ema_v6_trades.csv")
EQUITY_PATH = Path("archive/reports/legacy/hype_ema_v6_equity.csv")


def run_v6(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    variant = Variant(
        "V6_dynamic_3x",
        "v2_regime",
        "adx_exit",
        stop_atr=9.0,
        adx_exit=22,
        adx_exit_bars=3,
    )
    signal = entry_signal(frame, variant)
    ts = pd.to_datetime(frame.ts, utc=True).to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    spread = frame.ema_spread.to_numpy("float64")
    previous_spread = np.r_[np.nan, spread[:-1]]
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[0]
    pending_entry = 0
    bad_bars = 0
    trades: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark, bad_bars
        equity *= 1 + allocation * pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST * allocation
        raw_pnl = pos * (price / entry_px - 1)
        trades.append(
            {
                "entry_ts": entry_ts,
                "exit_ts": pd.Timestamp(ts[i]),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(allocation * raw_pnl),
                "exit_reason": reason,
                "entry_atr_pct": float(entry_atr),
                "equity_after": float(equity),
            }
        )
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_ts = None
        entry_atr = np.nan
        last_mark = price
        bad_bars = 0

    for i in range(len(frame)):
        if i > 0:
            if pos:
                equity *= 1 + allocation * pos * (open_[i] / last_mark - 1)
            last_mark = open_[i]

        if pending_entry and not pos:
            entry_atr = atr672[i - 1] if i > 0 else atr672[i]
            next_allocation = dynamic_allocation(pending_entry, entry_atr)
            if next_allocation > 0:
                pos = pending_entry
                allocation = next_allocation
                entry_px = open_[i] * (1 + SLIPPAGE if pos > 0 else 1 - SLIPPAGE)
                entry_ts = pd.Timestamp(ts[i])
                equity *= 1 - TRADE_COST * allocation
                last_mark = entry_px
            pending_entry = 0

        if pos:
            if np.isfinite(entry_atr) and entry_atr > 0:
                stop_px = entry_px * (1 - pos * variant.stop_atr * entry_atr)
                hit_stop = low[i] <= stop_px if pos > 0 else high[i] >= stop_px
                if hit_stop:
                    px = stop_px * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(i, px, "stop_loss")
                    equity_rows.append(_equity_row(ts[i], equity, pos, allocation))
                    continue

            equity *= 1 + allocation * pos * (close[i] / last_mark - 1)
            last_mark = close[i]

            opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (
                pos < 0 and spread[i] > 0 >= previous_spread[i]
            )
            if opposite_cross:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "opposite_cross")
                equity_rows.append(_equity_row(ts[i], equity, pos, allocation))
                continue

            trend_bad = bool(adx28[i] < variant.adx_exit)
            bad_bars = bad_bars + 1 if trend_bad else 0
            if bad_bars >= variant.adx_exit_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "trend_break")
                equity_rows.append(_equity_row(ts[i], equity, pos, allocation))
                continue

        if not pos and signal[i]:
            pending_entry = int(signal[i])

        equity_rows.append(_equity_row(ts[i], equity, pos, allocation))

    return pd.DataFrame(trades), pd.DataFrame(equity_rows)


def _equity_row(ts: np.datetime64, equity: float, pos: int, allocation: float) -> dict[str, object]:
    return {
        "ts": pd.Timestamp(ts),
        "equity": float(equity),
        "position": int(pos),
        "allocation": float(allocation),
    }


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def build_chart_html(frame: pd.DataFrame, trades: pd.DataFrame, equity: pd.DataFrame) -> str:
    chart_frame = frame.copy()
    chart_frame["time"] = pd.to_datetime(chart_frame["ts"], utc=True).map(lambda value: int(value.timestamp()))

    def clean(values: pd.Series, digits: int = 5) -> list[float | None]:
        return [None if pd.isna(value) else round(float(value), digits) for value in values]

    def unix_seconds(value: object) -> int:
        return int(pd.Timestamp(value).timestamp())

    candles = [
        {
            "time": int(row.time),
            "open": round(float(row.open), 5),
            "high": round(float(row.high), 5),
            "low": round(float(row.low), 5),
            "close": round(float(row.close), 5),
        }
        for row in chart_frame.itertuples()
    ]
    ema96 = [
        {"time": int(time), "value": value}
        for time, value in zip(chart_frame["time"], clean(chart_frame["ema96"]), strict=True)
        if value is not None
    ]
    ema384 = [
        {"time": int(time), "value": value}
        for time, value in zip(chart_frame["time"], clean(chart_frame["ema384"]), strict=True)
        if value is not None
    ]

    markers = []
    trade_lines = []
    for index, trade in enumerate(trades.itertuples(), start=1):
        is_long = int(trade.direction) > 0
        entry_time = unix_seconds(trade.entry_ts)
        exit_time = unix_seconds(trade.exit_ts)
        entry_label = "开多" if is_long else "开空"
        entry_kind = getattr(trade, "entry_kind", "")
        kind_label = " late" if entry_kind == "late" else ""
        exit_label = "平多" if is_long else "平空"
        entry_color = "#22c55e" if is_long else "#ef4444"
        exit_color = "#86efac" if trade.pnl_pct > 0 else "#fb7185"
        line_color = "rgba(34,197,94,0.95)" if is_long else "rgba(239,68,68,0.95)"

        markers.append(
            {
                "time": entry_time,
                "position": "belowBar" if is_long else "aboveBar",
                "color": entry_color,
                "shape": "arrowUp" if is_long else "arrowDown",
                "text": f"{entry_label}{kind_label} #{index} {trade.allocation:.2f}x",
            }
        )
        markers.append(
            {
                "time": exit_time,
                "position": "aboveBar" if is_long else "belowBar",
                "color": exit_color,
                "shape": "circle",
                "text": f"{exit_label} #{index} {pct(trade.pnl_pct)}",
            }
        )
        trade_lines.append(
            {
                "color": line_color,
                "data": [
                    {"time": entry_time, "value": round(float(trade.entry_price), 5)},
                    {"time": exit_time, "value": round(float(trade.exit_price), 5)},
                ],
            }
        )

    payload = {
        "candles": candles,
        "ema96": ema96,
        "ema384": ema384,
        "markers": markers,
        "trade_lines": trade_lines,
        "summary": {
            "trades": int(len(trades)),
            "return": pct(float(equity.equity.iloc[-1] - 1)),
            "max_drawdown": pct(float((equity.equity / equity.equity.cummax() - 1).min())),
            "win_rate": pct(float((trades.pnl_pct > 0).mean())),
            "avg_allocation": f"{float(trades.allocation.mean()):.2f}x",
            "max_allocation": f"{float(trades.allocation.max()):.2f}x",
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>HYPE EMA V6 Trade Chart</title>
  <script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0b0f14; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ height: 126px; padding: 16px 22px 8px; border-bottom: 1px solid #1f2937; }}
    h1 {{ margin: 0 0 7px; font-size: 22px; font-weight: 720; }}
    .meta {{ color: #9ca3af; font-size: 13px; }}
    .stats {{ display: flex; gap: 9px; flex-wrap: wrap; margin-top: 11px; }}
    .stat {{ min-width: 96px; border: 1px solid #263241; border-radius: 8px; padding: 7px 10px; background: #111827; }}
    .stat b {{ display: block; font-size: 15px; color: #f9fafb; }}
    .stat span {{ font-size: 11px; color: #9ca3af; }}
    .toolbar {{ position: absolute; right: 18px; top: 16px; display: flex; gap: 8px; }}
    button {{ cursor: pointer; border: 1px solid #334155; border-radius: 7px; background: #111827; color: #d1d5db; padding: 6px 10px; }}
    button:hover {{ background: #1f2937; }}
    #chart {{ height: calc(100vh - 126px); min-height: 720px; }}
  </style>
</head>
<body>
  <header>
    <div class="toolbar">
      <button data-bars="2880">近30天</button>
      <button data-bars="8640">近90天</button>
      <button data-bars="all">全部</button>
    </div>
    <h1>HYPE EMA V6 Trade Path</h1>
    <div class="meta">Binance HYPEUSDT perp 15m · EMA regime trend-hold · max 3x ATR dynamic allocation · data lake through 2026-06-01 03:00 UTC</div>
    <div class="stats">
      <div class="stat"><b id="ret"></b><span>Total return</span></div>
      <div class="stat"><b id="dd"></b><span>Max drawdown</span></div>
      <div class="stat"><b id="trades"></b><span>Trades</span></div>
      <div class="stat"><b id="win"></b><span>Win rate</span></div>
      <div class="stat"><b id="avgAlloc"></b><span>Avg allocation</span></div>
      <div class="stat"><b id="maxAlloc"></b><span>Max allocation</span></div>
    </div>
  </header>
  <div id="chart"></div>
  <script>
    const data = {payload_json};
    window.__hypeV6Data = data;
    document.getElementById("ret").textContent = data.summary.return;
    document.getElementById("dd").textContent = data.summary.max_drawdown;
    document.getElementById("trades").textContent = data.summary.trades;
    document.getElementById("win").textContent = data.summary.win_rate;
    document.getElementById("avgAlloc").textContent = data.summary.avg_allocation;
    document.getElementById("maxAlloc").textContent = data.summary.max_allocation;

    const chart = LightweightCharts.createChart(document.getElementById("chart"), {{
      layout: {{ background: {{ color: "#0b0f14" }}, textColor: "#d1d5db" }},
      grid: {{
        vertLines: {{ color: "#1f2937" }},
        horzLines: {{ color: "#1f2937" }}
      }},
      timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: "#263241" }},
      rightPriceScale: {{ borderColor: "#263241" }},
      crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }}
    }});
    window.__hypeV6Chart = chart;
    const candles = chart.addCandlestickSeries({{
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#9ca3af",
      wickDownColor: "#9ca3af"
    }});
    candles.setData(data.candles);
    candles.setMarkers(data.markers);

    const ema96 = chart.addLineSeries({{ color: "#60a5fa", lineWidth: 2, priceLineVisible: false }});
    ema96.setData(data.ema96);
    const ema384 = chart.addLineSeries({{ color: "#fbbf24", lineWidth: 2, priceLineVisible: false }});
    ema384.setData(data.ema384);

    for (const tradeLine of data.trade_lines) {{
      const line = chart.addLineSeries({{
        color: tradeLine.color,
        lineWidth: 3,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false
      }});
      line.setData(tradeLine.data);
    }}

    function showBars(bars) {{
      if (bars === "all") {{
        chart.timeScale().fitContent();
        return;
      }}
      const firstIndex = Math.max(0, data.candles.length - Number(bars));
      chart.timeScale().setVisibleRange({{
        from: data.candles[firstIndex].time,
        to: data.candles[data.candles.length - 1].time
      }});
    }}
    document.querySelectorAll("[data-bars]").forEach((button) => {{
      button.addEventListener("click", () => showBars(button.dataset.bars));
    }});
    showBars(8640);
    window.addEventListener("resize", () => {{
      chart.applyOptions({{ width: document.getElementById("chart").clientWidth }});
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    raw = load_hype_data_lake()
    frame = build_features(raw)
    trades, equity = run_v6(frame)
    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES_PATH, index=False)
    equity.to_csv(EQUITY_PATH, index=False)
    CHART_PATH.write_text(build_chart_html(frame, trades, equity))
    print(f"wrote={CHART_PATH}")
    print(f"trades={len(trades)} equity_final={equity.equity.iloc[-1]:.6f}")
    print(f"trades_csv={TRADES_PATH}")
    print(f"equity_csv={EQUITY_PATH}")


if __name__ == "__main__":
    main()
