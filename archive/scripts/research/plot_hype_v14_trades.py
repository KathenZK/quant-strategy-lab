from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from plot_hype_v13_trades import build_chart_html
from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import add_structure_features
from research_hype_v13_late_reentry import run_late_reentry
from research_hype_v14_main_backfill import v14_spec


CHART_PATH = Path("archive/reports/legacy/hype_v14_trade_chart.html")
TRADES_PATH = Path("archive/reports/legacy/hype_v14_trades.csv")
SUMMARY_PATH = Path("archive/reports/legacy/hype_v14_trade_chart_summary.json")


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    result = run_late_reentry(frame, v14_spec(), start_ts=start_ts, collect_trades=True)
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
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    html = build_chart_html(frame, trades, result)
    html = html.replace("HYPE V13 Trade Chart", "HYPE V14 Trade Chart")
    html = html.replace("HYPE V13 Trade Path", "HYPE V14 Trade Path")
    html = html.replace(
        "Binance HYPEUSDT perp 15m · V13 = V12.4 age128 + entry_max_dist_ema96 &lt;= 8% · data lake through 2026-06-01 03:00 UTC",
        "Binance HYPEUSDT perp 15m · V14 = V13 + profitable same-regime late re-entry · data lake through 2026-06-01 03:00 UTC",
    )
    html = html.replace("__hypeV13Data", "__hypeV14Data")
    html = html.replace("__hypeV13Chart", "__hypeV14Chart")
    CHART_PATH.write_text(html)
    print(f"wrote={CHART_PATH}")
    print(f"trades={len(trades)} late={int((trades.entry_kind == 'late').sum())} return={result['return']:.6f} max_dd={result['max_dd']:.6f}")
    print(f"trades_csv={TRADES_PATH}")
    print(f"summary={SUMMARY_PATH}")


if __name__ == "__main__":
    main()
