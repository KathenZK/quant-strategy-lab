from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DHCT_ARTIFACT_DIR = ROOT / "research/asset-portfolios/1d-btceth-dual-horizon-campaign-trend/artifacts"
P0_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"


def hourly_close(slug: str) -> pd.DataFrame:
    frame = pd.read_parquet(P0_DIR / f"{slug}_perp_1h.parquet", columns=["ts", "close"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    start, end = pd.Timestamp("2019-12-24", tz="UTC"), pd.Timestamp("2025-08-07", tz="UTC")
    return frame.loc[frame["ts"].between(start, end, inclusive="left")].sort_values("ts")


def render(frontier: str, run_date: str, campaign: str) -> Path:
    if campaign == "p0":
        artifact_dir = ARTIFACT_DIR
        stem_name = f"binance_1d_be_cbct_p0_frontiers_{run_date}"
        family_label = "BIN-1D-BE-CBCT"
    elif campaign == "p1":
        artifact_dir = ARTIFACT_DIR
        stem_name = f"binance_1d_be_cbct_p1_profit_protection_{run_date}"
        family_label = "BIN-1D-BE-CBCT"
    else:
        artifact_dir = DHCT_ARTIFACT_DIR
        stem_name = f"binance_1d_be_dhct_p0_search_{run_date}"
        family_label = "BIN-1D-BE-DHCT"
    stem = artifact_dir / stem_name
    trades = pd.read_csv(f"{stem}_trades.csv", parse_dates=["entry_ts", "exit_ts"])
    path = pd.read_csv(f"{stem}_path.csv", parse_dates=["ts"])
    trades = trades.loc[trades["frontier"].eq(frontier)].copy()
    path = path.loc[path["frontier"].eq(frontier)].copy()
    btc, eth = hourly_close("btcusdt"), hourly_close("ethusdt")
    trade_payload = [
        {
            "number": number + 1,
            "asset": trade["asset"],
            "side": int(trade["side"]),
            "entry_ts": pd.Timestamp(trade["entry_ts"]).isoformat(),
            "exit_ts": pd.Timestamp(trade["exit_ts"]).isoformat(),
            "entry": float(trade["entry_fill"]),
            "exit": float(trade["exit_fill"]),
            "reason": trade["exit_reason"],
            "log_growth": float(trade["trade_log_growth"]),
        }
        for number, trade in trades.reset_index(drop=True).iterrows()
    ]
    payload = {
        "frontier": frontier,
        "trade_count": len(trades),
        "btc": {"ts": [value.isoformat() for value in btc["ts"]], "close": btc["close"].astype(float).tolist()},
        "eth": {"ts": [value.isoformat() for value in eth["ts"]], "close": eth["close"].astype(float).tolist()},
        "equity": {"ts": [value.isoformat() for value in path["ts"]], "value": path["equity"].astype(float).tolist()},
        "trades": trade_payload,
    }
    output = artifact_dir / f"{family_label.lower().replace('-', '_')}_p0_{frontier}_trade_path_{run_date}.html"
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BIN-1D-BE-CBCT trade path</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>:root{color-scheme:dark}body{margin:0;background:#0d131a;color:#e8edf2;font:14px/1.5 Inter,-apple-system,sans-serif}header{padding:16px 22px;border-bottom:1px solid #27313d}h1{font-size:19px;margin:0}p{color:#aab7c4;margin:5px 0 0}#chart{width:100%;height:calc(100vh - 85px);min-height:900px}</style></head><body><header><h1 id="title"></h1><p>UTC｜全量 1h close、组合净值与每笔 entry/exit 连线。绿色 long，红色 short；hover 显示资产与退出原因。</p></header><div id="chart"></div><script>const p=__PAYLOAD__;document.getElementById('title').textContent=`BIN-1D-BE-CBCT · __CAMPAIGN__ · ${p.frontier.replaceAll('_',' ')} · ${p.trade_count} complete trades`;const t=[{type:'scattergl',mode:'lines',x:p.btc.ts,y:p.btc.close,xaxis:'x',yaxis:'y',name:'BTCUSDT',line:{color:'#69b3ff',width:1}},{type:'scattergl',mode:'lines',x:p.eth.ts,y:p.eth.close,xaxis:'x2',yaxis:'y2',name:'ETHUSDT',line:{color:'#a98cff',width:1}},{type:'scattergl',mode:'lines',x:p.equity.ts,y:p.equity.value,xaxis:'x3',yaxis:'y3',name:'Equity',line:{color:'#f6c85f',width:2}}];for(const q of p.trades){const btc=q.asset==='BTCUSDT';t.push({type:'scatter',mode:'lines+markers',x:[q.entry_ts,q.exit_ts],y:[q.entry,q.exit],xaxis:btc?'x':'x2',yaxis:btc?'y':'y2',showlegend:false,line:{color:q.side>0?'#19a974':'#e45756',width:2},marker:{size:6},text:[`#${q.number} ${q.asset} ${q.side>0?'LONG':'SHORT'} entry`,`#${q.number} ${q.reason} exit · log growth ${q.log_growth.toFixed(3)}`],hovertemplate:'%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>'});}const xa={type:'date',gridcolor:'#202a35',rangeslider:{visible:false}},ya={type:'log',gridcolor:'#202a35'};Plotly.newPlot('chart',t,{paper_bgcolor:'#0d131a',plot_bgcolor:'#0d131a',font:{color:'#dce5ed'},margin:{l:65,r:25,t:25,b:50},xaxis:{...xa,domain:[0,1],anchor:'y'},yaxis:{...ya,domain:[.68,1],title:'BTCUSDT'},xaxis2:{...xa,domain:[0,1],anchor:'y2'},yaxis2:{...ya,domain:[.34,.65],title:'ETHUSDT'},xaxis3:{...xa,domain:[0,1],anchor:'y3'},yaxis3:{...ya,domain:[0,.30],title:'equity multiple'}},{responsive:true,displaylogo:false});</script></body></html>"""
    output.write_text(
        html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
        .replace("BIN-1D-BE-CBCT", family_label)
        .replace("__CAMPAIGN__", campaign.upper()),
        encoding="utf-8",
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render CBCT complete trade paths.")
    parser.add_argument("--run-date", default="2026-08-12")
    parser.add_argument("--campaign", choices=("p0", "p1", "dhct"), default="p0")
    args = parser.parse_args()
    for frontier in ("growth_frontier", "risk_frontier"):
        print(render(frontier, args.run_date, args.campaign))


if __name__ == "__main__":
    main()
