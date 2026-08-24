from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-log-ratio-mean-reversion"
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


def records(frame: pd.DataFrame, columns: list[str]) -> dict[str, list[object]]:
    output: dict[str, list[object]] = {}
    for column in columns:
        output[column] = [pd.Timestamp(value).isoformat() for value in frame[column]] if column == "ts" else [float(value) for value in frame[column]]
    return output


def render(frontier: str, run_date: str) -> Path:
    stem = ARTIFACT_DIR / f"binance_1d_be_lrmr_p0_frontiers_{run_date}"
    trades = pd.read_csv(f"{stem}_trades.csv", parse_dates=["entry_ts", "exit_ts"])
    path = pd.read_csv(f"{stem}_path.csv", parse_dates=["ts"])
    trades = trades.loc[trades["frontier"].eq(frontier)].copy()
    path = path.loc[path["frontier"].eq(frontier)].copy()
    start, end = pd.Timestamp("2019-12-24", tz="UTC"), pd.Timestamp("2025-08-07", tz="UTC")
    btc = daily_bars("btcusdt").loc[lambda data: data["ts"].between(start, end, inclusive="left")]
    eth = daily_bars("ethusdt").loc[lambda data: data["ts"].between(start, end, inclusive="left")]
    pair_payload = []
    for number, trade in trades.reset_index(drop=True).iterrows():
        pair_payload.append({
            "number": number + 1, "state": int(trade["state"]),
            "entry_ts": pd.Timestamp(trade["entry_ts"]).isoformat(), "exit_ts": pd.Timestamp(trade["exit_ts"]).isoformat(),
            "BTCUSDT_entry": float(trade["BTCUSDT_entry_price"]), "BTCUSDT_exit": float(trade["BTCUSDT_exit_price"]),
            "ETHUSDT_entry": float(trade["ETHUSDT_entry_price"]), "ETHUSDT_exit": float(trade["ETHUSDT_exit_price"]),
            "pair_log_growth": float(trade["pair_log_growth"]),
        })
    payload = {"frontier": frontier, "pair_count": len(trades), "btc": records(btc, ["ts", "open", "high", "low", "close"]), "eth": records(eth, ["ts", "open", "high", "low", "close"]), "equity": records(path, ["ts", "equity"]), "pairs": pair_payload}
    output = ARTIFACT_DIR / f"binance_1d_be_lrmr_p0_{frontier}_trade_path_{run_date}.html"
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BIN-1D-BE-LRMR trade path</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>:root{color-scheme:dark}body{margin:0;background:#0d131a;color:#e8edf2;font:14px/1.5 Inter,-apple-system,sans-serif}header{padding:16px 22px;border-bottom:1px solid #27313d}h1{font-size:19px;margin:0}p{color:#aab7c4;margin:5px 0 0}#chart{width:100%;height:calc(100vh - 85px);min-height:900px}</style></head><body><header><h1 id="title"></h1><p>UTC｜每个 pair 在 BTC 与 ETH 面板分别连接 entry/exit；绿色为该腿 long，红色为该腿 short。第三面板为组合净值。</p></header><div id="chart"></div><script>const p=__PAYLOAD__;document.getElementById('title').textContent=`BIN-1D-BE-LRMR · ${p.frontier.replaceAll('_',' ')} · ${p.pair_count} complete pairs`;const candle=(d,n,x,y)=>({type:'candlestick',x:d.ts,open:d.open,high:d.high,low:d.low,close:d.close,name:n,xaxis:x,yaxis:y,showlegend:false});const t=[candle(p.btc,'BTCUSDT','x','y'),candle(p.eth,'ETHUSDT','x2','y2'),{type:'scatter',mode:'lines',x:p.equity.ts,y:p.equity.equity,xaxis:'x3',yaxis:'y3',name:'Equity',line:{color:'#f6c85f',width:2}}];for(const q of p.pairs){for(const [asset,x,y] of [['BTCUSDT','x','y'],['ETHUSDT','x2','y2']]){const side=asset==='BTCUSDT'?q.state:-q.state;t.push({type:'scatter',mode:'lines+markers',x:[q.entry_ts,q.exit_ts],y:[q[asset+'_entry'],q[asset+'_exit']],xaxis:x,yaxis:y,showlegend:false,line:{color:side>0?'#19a974':'#e45756',width:2},marker:{size:6},text:[`#${q.number} ${asset} entry ${side>0?'LONG':'SHORT'}`,`#${q.number} exit · pair log growth ${q.pair_log_growth.toFixed(3)}`],hovertemplate:'%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>'});}}const xa={type:'date',gridcolor:'#202a35',rangeslider:{visible:false}},ya={type:'log',gridcolor:'#202a35'};Plotly.newPlot('chart',t,{paper_bgcolor:'#0d131a',plot_bgcolor:'#0d131a',font:{color:'#dce5ed'},margin:{l:65,r:25,t:25,b:50},xaxis:{...xa,domain:[0,1],anchor:'y'},yaxis:{...ya,domain:[.68,1],title:'BTCUSDT'},xaxis2:{...xa,domain:[0,1],anchor:'y2'},yaxis2:{...ya,domain:[.34,.65],title:'ETHUSDT'},xaxis3:{...xa,domain:[0,1],anchor:'y3'},yaxis3:{...ya,domain:[0,.30],title:'equity multiple'}},{responsive:true,displaylogo:false});</script></body></html>"""
    output.write_text(html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":"))), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render LRMR complete pair paths.")
    parser.add_argument("--run-date", default="2026-08-12")
    args = parser.parse_args()
    for frontier in ("growth_frontier", "risk_frontier"):
        print(render(frontier, args.run_date))


if __name__ == "__main__":
    main()
