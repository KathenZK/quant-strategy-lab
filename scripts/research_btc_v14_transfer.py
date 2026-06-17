from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import add_structure_features
from research_hype_v13_late_reentry import run_late_reentry
from research_hype_v14_main_backfill import v14_spec


DATA_LAKE_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m")
SYMBOL_FILE = "symbol=btc_usdt_usdt.parquet"
CSV_PATH = Path("reports/btc_v14_transfer.csv")
JSON_PATH = Path("reports/btc_v14_transfer.json")
TRADES_PATH = Path("reports/btc_v14_transfer_trades.csv")
SENSITIVITY_PATH = Path("reports/btc_v14_transfer_allocation_sensitivity.csv")

WINDOWS = {
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=180),
    "1Y": pd.Timedelta(days=365),
}


def load_symbol_data_lake(symbol_file: str = SYMBOL_FILE) -> pd.DataFrame:
    files = sorted(DATA_LAKE_ROOT.rglob(symbol_file))
    if not files:
        raise FileNotFoundError(f"no {symbol_file} parquet files under {DATA_LAKE_ROOT}")

    frame = pd.concat(
        [
            pd.read_parquet(
                path,
                columns=["ts", "open", "high", "low", "close", "volume"],
            )
            for path in files
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame


def prepare_features(raw: pd.DataFrame) -> pd.DataFrame:
    return add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def buy_hold_metrics(frame: pd.DataFrame, start_ts: pd.Timestamp) -> dict[str, float]:
    working = frame[pd.to_datetime(frame.ts, utc=True) >= start_ts].copy()
    if working.empty:
        return {"return": 0.0, "max_dd": 0.0}
    equity = working.close / float(working.close.iloc[0])
    drawdown = equity / equity.cummax() - 1.0
    return {"return": float(equity.iloc[-1] - 1.0), "max_dd": float(drawdown.min())}


def row_from_result(label: str, result: dict[str, Any], benchmark: dict[str, float]) -> dict[str, Any]:
    exit_reasons = dict(result["exit_reasons"])
    return {
        "window": label,
        "v14_return": result["return"],
        "v14_return_pct": pct(result["return"]),
        "v14_max_dd": result["max_dd"],
        "v14_max_dd_pct": pct(result["max_dd"]),
        "v14_sharpe": result["sharpe"],
        "v14_trades": int(result["trades"]),
        "v14_late_trades": int(result["late_trades"]),
        "v14_win_rate": result["win_rate"],
        "v14_win_rate_pct": pct(result["win_rate"]),
        "v14_avg_trade_pct": result["avg_trade_pct"],
        "v14_median_trade_pct": result["median_trade_pct"],
        "buy_hold_return": benchmark["return"],
        "buy_hold_return_pct": pct(benchmark["return"]),
        "buy_hold_max_dd": benchmark["max_dd"],
        "buy_hold_max_dd_pct": pct(benchmark["max_dd"]),
        "exit_reasons": exit_reasons,
    }


def main() -> None:
    raw = load_symbol_data_lake()
    frame = prepare_features(raw)
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    start_ts = pd.Timestamp(frame.ts.iloc[0])
    spec = v14_spec()

    rows = []
    results: dict[str, dict[str, Any]] = {}
    for label, delta in WINDOWS.items():
        window_start = max(start_ts, end_ts - delta)
        result = run_late_reentry(frame, spec, start_ts=window_start)
        benchmark = buy_hold_metrics(frame, window_start)
        rows.append(row_from_result(label, result, benchmark))
        results[label] = result

    result_1y_trades = run_late_reentry(
        frame,
        spec,
        start_ts=max(start_ts, end_ts - pd.Timedelta(days=365)),
        collect_trades=True,
    )
    trades = pd.DataFrame(result_1y_trades.get("trades_detail", []))
    sensitivity_rows = []
    one_year_start = max(start_ts, end_ts - pd.Timedelta(days=365))
    for scale in (1.0, 0.5, 1 / 3, 0.25):
        kwargs: dict[str, Any] = {}
        if scale != 1.0:
            kwargs["entry_allocation_scale"] = {"": scale}
        scaled = run_late_reentry(frame, spec, start_ts=one_year_start, **kwargs)
        sensitivity_rows.append(
            {
                "allocation_scale": scale,
                "return": scaled["return"],
                "return_pct": pct(scaled["return"]),
                "max_dd": scaled["max_dd"],
                "max_dd_pct": pct(scaled["max_dd"]),
                "trades": int(scaled["trades"]),
                "win_rate": scaled["win_rate"],
                "win_rate_pct": pct(scaled["win_rate"]),
                "avg_trade_pct": scaled["avg_trade_pct"],
                "median_trade_pct": scaled["median_trade_pct"],
            }
        )

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(CSV_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    pd.DataFrame(sensitivity_rows).to_csv(SENSITIVITY_PATH, index=False)
    JSON_PATH.write_text(
        json.dumps(
            {
                "symbol": "BTCUSDT",
                "data": {
                    "start": str(start_ts),
                    "end": str(end_ts),
                    "rows": int(len(frame)),
                    "source": str(DATA_LAKE_ROOT / "date=*/symbol=btc_usdt_usdt.parquet"),
                },
                "strategy": {
                    "name": "V14 transferred from HYPE",
                    "late_reentry": asdict(spec),
                    "note": "No BTC parameter tuning; same V14 rules, fees, slippage and dynamic allocation.",
                },
                "windows": rows,
                "allocation_sensitivity_1y": sensitivity_rows,
                "trades_1y": result_1y_trades,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print(f"wrote={CSV_PATH}")
    print(f"json={JSON_PATH}")
    print(f"trades={TRADES_PATH}")
    print(f"sensitivity={SENSITIVITY_PATH}")
    print(pd.DataFrame(rows).to_string(index=False))
    print(pd.DataFrame(sensitivity_rows).to_string(index=False))


if __name__ == "__main__":
    main()
