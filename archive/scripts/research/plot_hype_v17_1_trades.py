from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from plot_hype_v13_trades import build_chart_html
from research_hype_v17_1_full_ablation import base_candidate_v17_1
from research_hype_v17_hybrid_ablation import load_frame, run_candidate
from research_hype_v17_trend_state_search import SignalPlan, build_signal


CHART_PATH = Path("reports/hype_ema_x_v17_1_binance_trade_chart.html")
TRADES_PATH = Path("reports/hype_ema_x_v17_1_trades.csv")
SUMMARY_PATH = Path("reports/hype_ema_x_v17_1_trade_chart_summary.json")


def main() -> None:
    frame = load_frame()
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    base_signal, _kind, _counts = build_signal(frame, SignalPlan("atr18_base", "atr18"))
    result, _counts = run_candidate(
        frame,
        base_candidate_v17_1(),
        start_ts,
        base_signal,
        collect_trades=True,
    )
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
                "late_trades": result["late_trades"],
                "win_rate": result["win_rate"],
                "exit_reasons": result["exit_reasons"],
                "hq_scale": 1.1,
                "lq_scale": 1.0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    html = build_chart_html(frame, trades, result)
    html = html.replace("HYPE V13 Trade Chart", "HYPE EMA-X V17.1 Trade Chart")
    html = html.replace("HYPE V13 Trade Path", "HYPE EMA-X V17.1 Trade Path")
    html = html.replace(
        "Binance HYPEUSDT perp 15m · V13 = V12.4 age128 + entry_max_dist_ema96 &lt;= 8% · data lake through 2026-06-01 03:00 UTC",
        "Binance HYPEUSDT perp 15m · HYPE-EMA-X-V17.1 = V17 signal with HQ scale 1.1 and LQ scale 1.0 · latest 365-day research slice",
    )
    html = html.replace("__hypeV13Data", "__hypeEmaXV171Data")
    html = html.replace("__hypeV13Chart", "__hypeEmaXV171Chart")
    CHART_PATH.write_text(html)

    print(f"wrote={CHART_PATH}")
    late_count = int(trades.entry_kind.astype(str).str.contains("late").sum())
    print(
        "trades={trades} late={late} return={ret:.6f} max_dd={dd:.6f}".format(
            trades=len(trades),
            late=late_count,
            ret=result["return"],
            dd=result["max_dd"],
        )
    )
    print(f"trades_csv={TRADES_PATH}")
    print(f"summary={SUMMARY_PATH}")


if __name__ == "__main__":
    main()
