from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"


def daily_bars(slug: str) -> pd.DataFrame:
    frame = pd.read_parquet(P0_DIR / f"{slug}_perp_1h.parquet")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return (
        frame.set_index("ts")
        .resample("1D", label="left", closed="left")
        .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), hours=("close", "count"))
        .loc[lambda data: data["hours"].eq(24)]
        .reset_index()
    )


def render(frontier: str, run_date: str) -> Path:
    stem = ARTIFACT_DIR / f"binance_1d_be_rcr_p0_frontiers_{run_date}"
    trades = pd.read_csv(f"{stem}_trades.csv", parse_dates=["entry_ts", "exit_ts"])
    path = pd.read_csv(f"{stem}_path.csv", parse_dates=["ts"])
    trades = trades.loc[trades["frontier"].eq(frontier)].copy()
    path = path.loc[path["frontier"].eq(frontier)].copy()
    btc = daily_bars("btcusdt")
    eth = daily_bars("ethusdt")
    start = pd.Timestamp("2019-12-24", tz="UTC")
    end = pd.Timestamp("2025-08-07", tz="UTC")
    btc = btc.loc[btc["ts"].between(start, end, inclusive="left")]
    eth = eth.loc[eth["ts"].between(start, end, inclusive="left")]
    def records(frame: pd.DataFrame, columns: list[str]) -> dict[str, list[object]]:
        result: dict[str, list[object]] = {}
        for column in columns:
            if column == "ts":
                result[column] = [pd.Timestamp(value).isoformat() for value in frame[column]]
            else:
                result[column] = [float(value) for value in frame[column]]
        return result

    trade_payload = []
    for trade_number, trade in trades.reset_index(drop=True).iterrows():
        trade_payload.append(
            {
                "number": trade_number + 1,
                "asset": trade["asset"],
                "side": int(trade["side"]),
                "entry_ts": pd.Timestamp(trade["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(trade["exit_ts"]).isoformat(),
                "entry_price": float(trade["entry_price"]),
                "exit_price": float(trade["exit_price"]),
                "trade_log_growth": float(trade["trade_log_growth"]),
            }
        )
    payload = {
        "frontier": frontier,
        "trade_count": len(trades),
        "btc": records(btc, ["ts", "open", "high", "low", "close"]),
        "eth": records(eth, ["ts", "open", "high", "low", "close"]),
        "equity": records(path, ["ts", "equity"]),
        "trades": trade_payload,
    }
    output = ARTIFACT_DIR / f"binance_1d_be_rcr_p0_{frontier}_trade_path_{run_date}.html"
    html = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BIN-1D-BE-RCR complete trade path</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>:root{color-scheme:dark}body{margin:0;background:#0d131a;color:#e8edf2;font:14px/1.5 Inter,-apple-system,sans-serif}header{padding:16px 22px;border-bottom:1px solid #27313d}h1{font-size:19px;margin:0}p{color:#aab7c4;margin:5px 0 0}#chart{width:100%;height:calc(100vh - 85px);min-height:900px}</style></head>
<body><header><h1 id="title"></h1><p>UTC｜BTC/ETH 日 K + 组合净值。每笔入场与对应出场完整连线；绿色为 long，红色为 short。可拖拽、缩放、双击复位。</p></header><div id="chart"></div>
<script>const payload=__PAYLOAD__;
document.getElementById('title').textContent=`BIN-1D-BE-RCR · ${payload.frontier.replaceAll('_',' ')} · ${payload.trade_count} complete trades`;
const candle=(p,name,axes)=>({type:'candlestick',x:p.ts,open:p.open,high:p.high,low:p.low,close:p.close,name,xaxis:axes[0],yaxis:axes[1],showlegend:false});
const traces=[candle(payload.btc,'BTCUSDT',['x','y']),candle(payload.eth,'ETHUSDT',['x2','y2']),{type:'scatter',mode:'lines',x:payload.equity.ts,y:payload.equity.equity,xaxis:'x3',yaxis:'y3',name:'Equity',line:{color:'#f6c85f',width:2}}];
for(const t of payload.trades){const isBtc=t.asset==='BTCUSDT',isLong=t.side>0;traces.push({type:'scatter',mode:'lines+markers',x:[t.entry_ts,t.exit_ts],y:[t.entry_price,t.exit_price],xaxis:isBtc?'x':'x2',yaxis:isBtc?'y':'y2',showlegend:false,line:{color:isLong?'#19a974':'#e45756',width:2},marker:{size:6},text:[`#${t.number} entry ${isLong?'LONG':'SHORT'}`,`#${t.number} exit · log growth ${t.trade_log_growth.toFixed(3)}`],hovertemplate:'%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>'});}
const axis={type:'date',showgrid:true,gridcolor:'#202a35',rangeslider:{visible:false}};const yaxis={type:'log',showgrid:true,gridcolor:'#202a35'};
Plotly.newPlot('chart',traces,{paper_bgcolor:'#0d131a',plot_bgcolor:'#0d131a',font:{color:'#dce5ed'},margin:{l:65,r:25,t:25,b:50},hovermode:'closest',xaxis:{...axis,domain:[0,1],anchor:'y'},yaxis:{...yaxis,domain:[0.68,1],title:'BTCUSDT'},xaxis2:{...axis,domain:[0,1],anchor:'y2'},yaxis2:{...yaxis,domain:[0.34,0.65],title:'ETHUSDT'},xaxis3:{...axis,domain:[0,1],anchor:'y3'},yaxis3:{...yaxis,domain:[0,0.30],title:'equity multiple'}},{responsive:true,displaylogo:false});</script></body></html>"""
    output.write_text(html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":"))), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render complete P0 frontier trade paths.")
    parser.add_argument("--run-date", default="2026-08-12")
    args = parser.parse_args()
    for frontier in ("growth_frontier", "risk_frontier"):
        print(render(frontier, args.run_date))


if __name__ == "__main__":
    main()
