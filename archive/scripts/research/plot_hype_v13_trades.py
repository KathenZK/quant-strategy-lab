from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import add_structure_features, run_v12
from research_hype_v13_main_backfill import v13_spec


CHART_PATH = Path("archive/reports/legacy/hype_v13_trade_chart.html")
TRADES_PATH = Path("archive/reports/legacy/hype_v13_trades.csv")
SUMMARY_PATH = Path("archive/reports/legacy/hype_v13_trade_chart_summary.json")


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def build_chart_html(frame: pd.DataFrame, trades: pd.DataFrame, result: dict[str, Any]) -> str:
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
        entry_kind = str(getattr(trade, "entry_kind", "") or "")
        if "_" in entry_kind:
            kind_label = f" {entry_kind.replace('_', ' ')}"
        elif entry_kind:
            kind_label = f" {entry_kind}"
        else:
            kind_label = ""
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
                "text": f"{exit_label} #{index} {pct(trade.pnl_pct)} {trade.exit_reason}",
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
            "trades": int(result["trades"]),
            "return": pct(float(result["return"])),
            "max_drawdown": pct(float(result["max_dd"])),
            "win_rate": pct(float(result["win_rate"])),
            "avg_allocation": f"{float(trades.allocation.mean()):.2f}x",
            "max_allocation": f"{float(trades.allocation.max()):.2f}x",
            "exit_reasons": dict(result["exit_reasons"]),
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>HYPE V13 Trade Chart</title>
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
    <h1>HYPE V13 Trade Path</h1>
    <div class="meta">Binance HYPEUSDT perp 15m · V13 = V12.4 age128 + entry_max_dist_ema96 &lt;= 8% · data lake through 2026-06-01 03:00 UTC</div>
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
    window.__hypeV13Data = data;
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
    window.__hypeV13Chart = chart;
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
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    result = run_v12(frame, v13_spec(), start_ts=start_ts, collect_trades=True)
    trades = pd.DataFrame(result["trades_detail"])

    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "return": result["return"],
                "max_dd": result["max_dd"],
                "sharpe": result["sharpe"],
                "trades": result["trades"],
                "win_rate": result["win_rate"],
                "exit_reasons": result["exit_reasons"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    CHART_PATH.write_text(build_chart_html(frame, trades, result))
    print(f"wrote={CHART_PATH}")
    print(f"trades={len(trades)} return={result['return']:.6f} max_dd={result['max_dd']:.6f}")
    print(f"trades_csv={TRADES_PATH}")
    print(f"summary={SUMMARY_PATH}")


if __name__ == "__main__":
    main()
