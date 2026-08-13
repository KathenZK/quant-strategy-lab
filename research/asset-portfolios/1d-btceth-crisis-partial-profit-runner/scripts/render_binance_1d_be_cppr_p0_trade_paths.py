from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-crisis-partial-profit-runner"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"


def hourly_close(slug: str) -> pd.DataFrame:
    frame = pd.read_parquet(P0_DIR / f"{slug}_perp_1h.parquet", columns=["ts", "close"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    start, end = pd.Timestamp("2019-12-24", tz="UTC"), pd.Timestamp("2025-08-07", tz="UTC")
    return frame.loc[frame["ts"].between(start, end, inclusive="left")].sort_values("ts")


def render(frontier: str, run_date: str) -> Path:
    stem = ARTIFACT_DIR / f"binance_1d_be_cppr_p0_{run_date}"
    path = pd.read_csv(f"{stem}_paths.csv", parse_dates=["ts"])
    trades = pd.read_csv(f"{stem}_trades.csv", parse_dates=["entry_ts", "exit_ts"])
    partials = pd.read_csv(f"{stem}_partial_events.csv", parse_dates=["ts"])
    legs = pd.read_csv(f"{stem}_crisis_legs.csv", parse_dates=["entry_ts", "exit_ts"])
    path = path.loc[path["frontier"].eq(frontier)].copy()
    trades = trades.loc[trades["frontier"].eq(frontier)].copy()
    partials = partials.loc[partials["frontier"].eq(frontier)].copy()
    legs = legs.loc[legs["frontier"].eq(frontier)].copy()
    btc, eth = hourly_close("btcusdt"), hourly_close("ethusdt")
    routed = []
    base_by_number = {}
    for _, trade in trades.iterrows():
        if trade["mode"] != "base":
            continue
        number = int(trade["trade_number"])
        base_by_number[number] = trade
        routed.append(
            {
                "number": number,
                "kind": "RUNNER",
                "asset": trade["asset"],
                "side": int(trade["side"]),
                "entry_ts": pd.Timestamp(trade["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(trade["exit_ts"]).isoformat(),
                "entry": float(trade["entry_price"]),
                "exit": float(trade["exit_price"]),
                "reason": trade["exit_reason"],
            }
        )
    offset = max(base_by_number, default=0)
    for index, (_, leg) in enumerate(legs.iterrows(), start=1):
        routed.append(
            {
                "number": offset + index,
                "kind": "CRISIS",
                "asset": leg["asset"],
                "side": -1,
                "entry_ts": pd.Timestamp(leg["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(leg["exit_ts"]).isoformat(),
                "entry": float(leg["entry_price"]),
                "exit": float(leg["exit_price"]),
                "reason": "crisis_state_exit",
            }
        )
    partial_payload = []
    for _, event in partials.iterrows():
        trade = base_by_number[int(event["trade_number"])]
        partial_payload.append(
            {
                "trade_number": int(event["trade_number"]),
                "asset": trade["asset"],
                "side": int(trade["side"]),
                "ts": pd.Timestamp(event["ts"]).isoformat(),
                "fill": float(event["fill"]),
                "fraction": float(event["fraction"]),
                "remaining": float(event["quantity_remaining"]),
            }
        )
    payload = {
        "frontier": frontier,
        "btc": {"ts": [value.isoformat() for value in btc["ts"]], "close": btc["close"].astype(float).tolist()},
        "eth": {"ts": [value.isoformat() for value in eth["ts"]], "close": eth["close"].astype(float).tolist()},
        "equity": {"ts": [value.isoformat() for value in path["ts"]], "value": path["equity"].astype(float).tolist()},
        "trades": routed,
        "partials": partial_payload,
    }
    output = ARTIFACT_DIR / f"binance_1d_be_cppr_p0_{frontier}_trade_path_{run_date}.html"
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BIN-1D-BE-CPPR trade path</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>:root{color-scheme:dark}body{margin:0;background:#0d131a;color:#e8edf2;font:14px/1.5 Inter,-apple-system,sans-serif}header{padding:16px 22px;border-bottom:1px solid #27313d}h1{font-size:19px;margin:0}p{color:#aab7c4;margin:5px 0 0}#chart{width:100%;height:calc(100vh - 85px);min-height:900px}</style></head><body><header><h1 id="title"></h1><p>UTC｜BTC/ETH 1h close、账户净值、全部runner/crisis entry-exit连线及partial-bank菱形标记。</p></header><div id="chart"></div><script>const p=__PAYLOAD__;document.getElementById('title').textContent=`BIN-1D-BE-CPPR · ${p.frontier.replaceAll('_',' ')} · ${p.trades.length} routed legs · ${p.partials.length} partials`;const t=[{type:'scattergl',mode:'lines',x:p.btc.ts,y:p.btc.close,xaxis:'x',yaxis:'y',name:'BTCUSDT',line:{color:'#69b3ff',width:1}},{type:'scattergl',mode:'lines',x:p.eth.ts,y:p.eth.close,xaxis:'x2',yaxis:'y2',name:'ETHUSDT',line:{color:'#a98cff',width:1}},{type:'scattergl',mode:'lines',x:p.equity.ts,y:p.equity.value,xaxis:'x3',yaxis:'y3',name:'Equity',line:{color:'#f6c85f',width:2.4}}];for(const q of p.trades){const btc=q.asset==='BTCUSDT';t.push({type:'scatter',mode:'lines+markers',x:[q.entry_ts,q.exit_ts],y:[q.entry,q.exit],xaxis:btc?'x':'x2',yaxis:btc?'y':'y2',showlegend:false,line:{color:q.kind==='CRISIS'?'#ff9f1c':(q.side>0?'#19a974':'#e45756'),width:q.kind==='CRISIS'?2.4:1.8,dash:q.kind==='CRISIS'?'dot':'solid'},marker:{size:6},text:[`#${q.number} ${q.kind} ${q.asset} entry`,`#${q.number} ${q.reason}`],hovertemplate:'%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>'});}for(const q of p.partials){const btc=q.asset==='BTCUSDT';t.push({type:'scatter',mode:'markers',x:[q.ts],y:[q.fill],xaxis:btc?'x':'x2',yaxis:btc?'y':'y2',name:'Partial bank',showlegend:false,marker:{size:10,symbol:'diamond',color:'#f6c85f',line:{color:'#0d131a',width:1}},text:[`trade #${q.trade_number} partial ${(q.fraction*100).toFixed(0)}% · remaining ${q.remaining.toFixed(6)}`],hovertemplate:'%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>'});}const xa={type:'date',gridcolor:'#202a35',rangeslider:{visible:false}},ya={type:'log',gridcolor:'#202a35'};Plotly.newPlot('chart',t,{paper_bgcolor:'#0d131a',plot_bgcolor:'#0d131a',font:{color:'#dce5ed'},margin:{l:65,r:25,t:25,b:50},xaxis:{...xa,domain:[0,1],anchor:'y'},yaxis:{...ya,domain:[.68,1],title:'BTCUSDT'},xaxis2:{...xa,domain:[0,1],anchor:'y2'},yaxis2:{...ya,domain:[.34,.65],title:'ETHUSDT'},xaxis3:{...xa,domain:[0,1],anchor:'y3'},yaxis3:{...ya,domain:[0,.30],title:'equity multiple'}},{responsive:true,displaylogo:false});</script></body></html>"""
    output.write_text(html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":"))), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render CPPR partial-runner paths.")
    parser.add_argument("--run-date", default="2026-08-12")
    args = parser.parse_args()
    for frontier in ("growth_frontier", "risk_frontier"):
        print(render(frontier, args.run_date))


if __name__ == "__main__":
    main()
