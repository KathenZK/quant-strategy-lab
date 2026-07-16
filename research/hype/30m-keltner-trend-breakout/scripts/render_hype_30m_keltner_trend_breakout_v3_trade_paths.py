"""Render the V3 full-sample trade paths as an interactive HTML chart.

The resulting document uses the Plotly CDN for its JavaScript runtime. It
contains every plotted bar and trade locally, but needs browser network access
once to download Plotly itself.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402
import research_hype_30m_k2_v2_1_dynamic_atr_bracket as dynamic  # noqa: E402
import research_hype_30m_k2_v2_1_loss_regime_filters as regime  # noqa: E402


RUN_DATE = "2026-07-13"
TRADES_PATH = base.ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_trades_{RUN_DATE}.csv"
OUTPUT_PATH = base.ARTIFACT_DIR / f"hype_30m_keltner_trend_breakout_v3_trade_paths_{RUN_DATE}.html"
START = pd.Timestamp("2025-05-30 10:30:00+00:00")
END = pd.Timestamp("2026-07-13 06:06:00+00:00")


def iso(values: pd.Index | pd.Series) -> list[str]:
    return [value.isoformat() for value in values]


def floats(values: pd.Series) -> list[float | None]:
    return [None if pd.isna(value) else float(value) for value in values]


def load_v3_features() -> pd.DataFrame:
    m1 = pd.read_parquet(base.CACHE_PATH)
    m1["ts"] = pd.to_datetime(m1["ts"], utc=True)
    m1 = m1.loc[m1["ts"].between(START, END)].copy()
    b30, _ = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)
    h1, _ = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)
    cfg = dynamic.v21_config()
    features = dynamic.v21_features(b30, h1, cfg)
    features = regime.add_features(features)

    # Map the same completed 1h EMA values visible to the 30m signal bar.
    htf = h1.copy()
    htf["ema_fast_1h"] = base.ema(htf["close"], cfg.h1_ema_fast)
    htf["ema_slow_1h"] = base.ema(htf["close"], cfg.h1_ema_slow)
    htf = htf.assign(close_ts=htf.index + pd.Timedelta(hours=1))
    signal_times = pd.DataFrame(
        {"signal_ts": features.index, "signal_close_ts": features.index + pd.Timedelta(minutes=30)}
    )
    mapped = pd.merge_asof(
        signal_times.sort_values("signal_close_ts"),
        htf[["close_ts", "ema_fast_1h", "ema_slow_1h"]].sort_values("close_ts"),
        left_on="signal_close_ts",
        right_on="close_ts",
        direction="backward",
    ).set_index("signal_ts")
    features["ema_fast_1h"] = mapped.reindex(features.index)["ema_fast_1h"]
    features["ema_slow_1h"] = mapped.reindex(features.index)["ema_slow_1h"]
    return features.loc[START:END].copy()


def load_trades() -> list[dict[str, object]]:
    with TRADES_PATH.open(newline="", encoding="utf-8") as handle:
        trades = list(csv.DictReader(handle))
    for trade in trades:
        trade["entry_ts"] = pd.Timestamp(trade["entry_ts"]).isoformat()
        trade["exit_ts"] = pd.Timestamp(trade["exit_ts"]).isoformat()
        for key in (
            "entry_fill",
            "exit_fill",
            "leverage",
            "entry_atr_pct",
            "net_account_return_pct",
        ):
            trade[key] = float(trade[key])
    return trades


def plot_payload(features: pd.DataFrame, trades: list[dict[str, object]]) -> dict[str, object]:
    index = iso(features.index)
    long_entries = [trade for trade in trades if trade["direction"] == "long"]
    short_entries = [trade for trade in trades if trade["direction"] == "short"]

    def trade_text(trade: dict[str, object]) -> str:
        return (
            f"{str(trade['direction']).upper()}<br>"
            f"入场：{str(trade['entry_ts']).replace('+00:00', ' UTC')} @ {float(trade['entry_fill']):.4f}<br>"
            f"出场：{str(trade['exit_ts']).replace('+00:00', ' UTC')} @ {float(trade['exit_fill']):.4f}<br>"
            f"原因：{trade['exit_reason']}；持有：{trade['hold_bars']} 根<br>"
            f"杠杆：{float(trade['leverage']):.2f}x；ATR%：{float(trade['entry_atr_pct']) * 100:.2f}%<br>"
            f"账户净收益：{float(trade['net_account_return_pct']):+.2f}%"
        )

    path_groups: dict[str, dict[str, list[object]]] = {
        "long_win": {"x": [], "y": []},
        "long_loss": {"x": [], "y": []},
        "short_win": {"x": [], "y": []},
        "short_loss": {"x": [], "y": []},
    }
    brackets = {"tp_x": [], "tp_y": [], "sl_x": [], "sl_y": []}
    for trade in trades:
        outcome = "win" if float(trade["net_account_return_pct"]) >= 0 else "loss"
        key = f"{trade['direction']}_{outcome}"
        path_groups[key]["x"].extend([trade["entry_ts"], trade["exit_ts"], None])
        path_groups[key]["y"].extend([trade["entry_fill"], trade["exit_fill"], None])
        tp = float(trade["entry_fill"]) * (1.10 if trade["direction"] == "long" else 0.90)
        sl = float(trade["entry_fill"]) * (0.975 if trade["direction"] == "long" else 1.025)
        brackets["tp_x"].extend([trade["entry_ts"], trade["exit_ts"], None])
        brackets["tp_y"].extend([tp, tp, None])
        brackets["sl_x"].extend([trade["entry_ts"], trade["exit_ts"], None])
        brackets["sl_y"].extend([sl, sl, None])

    return {
        "price": {
            "x": index,
            "open": floats(features["open"]),
            "high": floats(features["high"]),
            "low": floats(features["low"]),
            "close": floats(features["close"]),
        },
        "lines": {
            "x": index,
            "mid": floats(features["mid"]),
            "upper": floats(features["upper"]),
            "lower": floats(features["lower"]),
            "ema_fast": floats(features["ema_fast_1h"]),
            "ema_slow": floats(features["ema_slow_1h"]),
        },
        "atr_pct": floats(features["atr_pct"] * 100),
        "close_location": floats(features["close_location"]),
        "long_entries": {
            "x": [trade["entry_ts"] for trade in long_entries],
            "y": [trade["entry_fill"] for trade in long_entries],
            "text": [trade_text(trade) for trade in long_entries],
        },
        "short_entries": {
            "x": [trade["entry_ts"] for trade in short_entries],
            "y": [trade["entry_fill"] for trade in short_entries],
            "text": [trade_text(trade) for trade in short_entries],
        },
        "exits": {
            "x": [trade["exit_ts"] for trade in trades],
            "y": [trade["exit_fill"] for trade in trades],
            "text": [trade_text(trade) for trade in trades],
        },
        "trade_paths": path_groups,
        "brackets": brackets,
    }


def html_document(payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HYPE-30M-Keltner-Trend-Breakout-V3 全部交易路径</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; background: #10151c; color: #e8edf2; font: 14px/1.5 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding: 16px 22px 10px; border-bottom: 1px solid #2a3440; }}
    h1 {{ margin: 0; font-size: 19px; }} p {{ margin: 5px 0 0; color: #aab7c4; }}
    #chart {{ width: 100%; height: calc(100vh - 93px); min-height: 700px; }}
    code {{ color: #85d3ff; }}
  </style>
</head>
<body>
  <header>
    <h1>HYPE-30M-Keltner-Trend-Breakout-V3：全部 78 笔交易路径</h1>
    <p>UTC｜拖拽平移、滚轮缩放、双击复位。主图 K 线按当前窗口即时渲染：放大时显示原始 30m，缩小时自动聚合，避免全样本 K 线卡顿。叠加 Keltner(10, 10, 2)、映射 1h EMA(16/44)、进出场与 TP/SL。</p>
  </header>
  <div id="chart"></div>
  <script>
    const payload = {data};
    const chart = document.getElementById("chart");
    const MAX_VISIBLE_CANDLES = 1200;
    const lowerBound = (values, target) => {{
      let left = 0, right = values.length;
      while (left < right) {{
        const middle = (left + right) >>> 1;
        if (values[middle] < target) left = middle + 1; else right = middle;
      }}
      return left;
    }};
    function visibleCandles(start, end) {{
      const all = payload.price;
      const first = Math.max(0, lowerBound(all.x, start) - 1);
      const last = Math.min(all.x.length, lowerBound(all.x, end) + 1);
      const count = Math.max(0, last - first);
      const bucketSize = Math.max(1, Math.ceil(count / MAX_VISIBLE_CANDLES));
      const output = {{x: [], open: [], high: [], low: [], close: []}};
      for (let from = first; from < last; from += bucketSize) {{
        const to = Math.min(last, from + bucketSize);
        let high = -Infinity, low = Infinity;
        for (let i = from; i < to; i += 1) {{
          high = Math.max(high, all.high[i]);
          low = Math.min(low, all.low[i]);
        }}
        output.x.push(all.x[from]);
        output.open.push(all.open[from]);
        output.high.push(high);
        output.low.push(low);
        output.close.push(all.close[to - 1]);
      }}
      return output;
    }}
    const initialStart = payload.price.x[Math.max(0, payload.price.x.length - 1440)];
    const initialEnd = payload.price.x[payload.price.x.length - 1];
    const initialCandles = visibleCandles(initialStart, initialEnd);
    const traces = [
      {{
        type:"candlestick", name:"HYPEUSDT 30m K线", x:initialCandles.x,
        open:initialCandles.open, high:initialCandles.high, low:initialCandles.low, close:initialCandles.close,
        increasing:{{line:{{color:"#26a69a",width:1}}}}, decreasing:{{line:{{color:"#ef5350",width:1}}}},
        xaxis:"x", yaxis:"y"
      }},
      {{type:"scattergl", mode:"lines", name:"30m 收盘价（辅助）", x:payload.price.x, y:payload.price.close, line:{{color:"#9daab7",width:1}}, visible:"legendonly", xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"Keltner 上轨", x:payload.lines.x, y:payload.lines.upper, line:{{color:"#f5b14c",width:1}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"Keltner 中轨 EMA10", x:payload.lines.x, y:payload.lines.mid, line:{{color:"#d8dee9",width:1}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"Keltner 下轨", x:payload.lines.x, y:payload.lines.lower, line:{{color:"#f5b14c",width:1}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"1h EMA16", x:payload.lines.x, y:payload.lines.ema_fast, line:{{color:"#5bc0eb",width:1.25}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"1h EMA44", x:payload.lines.x, y:payload.lines.ema_slow, line:{{color:"#b980f0",width:1.25}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"markers", name:"多头入场", x:payload.long_entries.x, y:payload.long_entries.y, text:payload.long_entries.text, hovertemplate:"%{{text}}<extra>多头入场</extra>", marker:{{symbol:"triangle-up",size:10,color:"#18b77e",line:{{color:"#e8fff6",width:1}}}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"markers", name:"空头入场", x:payload.short_entries.x, y:payload.short_entries.y, text:payload.short_entries.text, hovertemplate:"%{{text}}<extra>空头入场</extra>", marker:{{symbol:"triangle-down",size:10,color:"#ff8a80",line:{{color:"#fff0f0",width:1}}}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"markers", name:"出场", x:payload.exits.x, y:payload.exits.y, text:payload.exits.text, hovertemplate:"%{{text}}<extra>出场</extra>", marker:{{symbol:"x",size:9,color:"#f0f4f8"}}, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"ATR84 / 价格", x:payload.lines.x, y:payload.atr_pct, line:{{color:"#ffcc80",width:1}}, xaxis:"x2", yaxis:"y2"}},
      {{type:"scattergl", mode:"lines", name:"收盘位置", x:payload.lines.x, y:payload.close_location, line:{{color:"#80cbc4",width:1}}, xaxis:"x3", yaxis:"y3"}}
    ];

    const pathStyles = {{
      long_win: {{name:"多头盈利路径", color:"#18b77e", dash:"solid"}},
      long_loss: {{name:"多头亏损路径", color:"#ef5350", dash:"solid"}},
      short_win: {{name:"空头盈利路径", color:"#18b77e", dash:"dot"}},
      short_loss: {{name:"空头亏损路径", color:"#ef5350", dash:"dot"}}
    }};
    for (const [key, style] of Object.entries(pathStyles)) {{
      const path = payload.trade_paths[key];
      traces.push({{type:"scattergl", mode:"lines", name:style.name, x:path.x, y:path.y, line:{{color:style.color,width:2,dash:style.dash}}, hoverinfo:"skip", xaxis:"x", yaxis:"y"}});
    }}
    traces.push(
      {{type:"scattergl", mode:"lines", name:"固定 TP", x:payload.brackets.tp_x, y:payload.brackets.tp_y, line:{{color:"#617080",width:0.75,dash:"dot"}}, hoverinfo:"skip", showlegend:false, xaxis:"x", yaxis:"y"}},
      {{type:"scattergl", mode:"lines", name:"固定 SL", x:payload.brackets.sl_x, y:payload.brackets.sl_y, line:{{color:"#617080",width:0.75,dash:"dot"}}, hoverinfo:"skip", showlegend:false, xaxis:"x", yaxis:"y"}}
    );

    const layout = {{
      paper_bgcolor:"#10151c", plot_bgcolor:"#10151c", font:{{color:"#d5dde5"}},
      margin:{{l:65,r:35,t:18,b:35}}, hovermode:"x unified", dragmode:"pan",
      legend:{{orientation:"h", yanchor:"bottom", y:1.01, xanchor:"left", x:0, bgcolor:"rgba(0,0,0,0)"}},
      xaxis:{{domain:[0,1], anchor:"y", range:[initialStart, initialEnd], rangeslider:{{visible:true,thickness:0.06}}, showgrid:true, gridcolor:"#26313c", zeroline:false}},
      yaxis:{{domain:[0.38,1], title:"价格（USDT）", showgrid:true, gridcolor:"#26313c", fixedrange:false}},
      xaxis2:{{domain:[0,1], anchor:"y2", matches:"x", showticklabels:false, showgrid:true, gridcolor:"#26313c"}},
      yaxis2:{{domain:[0.20,0.32], title:"ATR%", ticksuffix:"%", showgrid:true, gridcolor:"#26313c"}},
      xaxis3:{{domain:[0,1], anchor:"y3", matches:"x", showgrid:true, gridcolor:"#26313c"}},
      yaxis3:{{domain:[0.02,0.14], title:"收盘位置", range:[0,1], showgrid:true, gridcolor:"#26313c"}},
      shapes:[
        {{type:"line", xref:"x2", yref:"y2", x0:payload.lines.x[0], x1:payload.lines.x[payload.lines.x.length-1], y0:1.25, y1:1.25, line:{{color:"#ef5350",dash:"dash",width:1}}}},
        {{type:"line", xref:"x3", yref:"y3", x0:payload.lines.x[0], x1:payload.lines.x[payload.lines.x.length-1], y0:0.65, y1:0.65, line:{{color:"#18b77e",dash:"dash",width:1}}}},
        {{type:"line", xref:"x3", yref:"y3", x0:payload.lines.x[0], x1:payload.lines.x[payload.lines.x.length-1], y0:0.35, y1:0.35, line:{{color:"#ef5350",dash:"dash",width:1}}}}
      ],
      annotations:[
        {{xref:"paper", yref:"y2", x:1.005, y:1.25, text:"ATR cap 1.25%", showarrow:false, font:{{size:10,color:"#ef5350"}}, xanchor:"left"}},
        {{xref:"paper", yref:"y3", x:1.005, y:0.65, text:"多 ≥0.65", showarrow:false, font:{{size:10,color:"#18b77e"}}, xanchor:"left"}},
        {{xref:"paper", yref:"y3", x:1.005, y:0.35, text:"空 ≤0.35", showarrow:false, font:{{size:10,color:"#ef5350"}}, xanchor:"left"}}
      ]
    }};
    Plotly.newPlot(chart, traces, layout, {{responsive:true, displaylogo:false, scrollZoom:true}}).then(() => {{
      let updateTimer;
      const redrawCandles = () => {{
        const range = chart.layout.xaxis.range;
        if (!range) return;
        const candles = visibleCandles(String(range[0]), String(range[1]));
        Plotly.restyle(chart, {{
          x:[candles.x], open:[candles.open], high:[candles.high],
          low:[candles.low], close:[candles.close]
        }}, [0]);
      }};
      chart.on("plotly_relayout", (event) => {{
        if (event["xaxis.autorange"]) {{
          Plotly.relayout(chart, {{"xaxis.range":[initialStart, initialEnd]}});
          return;
        }}
        if (!("xaxis.range[0]" in event || "xaxis.range[1]" in event)) return;
        window.clearTimeout(updateTimer);
        updateTimer = window.setTimeout(redrawCandles, 90);
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    features = load_v3_features()
    trades = load_trades()
    OUTPUT_PATH.write_text(html_document(plot_payload(features, trades)), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({len(features)} bars, {len(trades)} trades)")


if __name__ == "__main__":
    main()
