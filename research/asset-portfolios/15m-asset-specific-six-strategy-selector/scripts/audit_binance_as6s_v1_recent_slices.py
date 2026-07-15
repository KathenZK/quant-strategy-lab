from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ACCOUNT_PATH = FAMILY_DIR / "artifacts/binance_hybrid_asset_specific_account_2026-07-14.json"
TRADES_PATH = (
    FAMILY_DIR / "artifacts/binance_hybrid_asset_specific_account_trades_2026-07-14.csv"
)
FREEZE_PATH = FAMILY_DIR / "artifacts/binance_as6s_future_oos_freeze_2026-07-14.json"
OUTPUT_PATH = FAMILY_DIR / "artifacts/binance_15m_as6s_v1_recent_slices_2026-07-14.json"
EXPECTED_FREEZE_SHA256 = "a675d7de8d1a5784b7f6121174497cc31be2313578d50de6fb4a4d3c768394bf"


def slice_metrics(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    chosen = frame.loc[(frame["entry_ts"] >= start) & (frame["exit_ts"] < end)].sort_values(
        "exit_ts"
    )
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    wins = 0
    for row in chosen.itertuples():
        leverage = 0.75 * float(row.exposure)
        trough = equity * max(1e-9, 1.0 + leverage * float(row.mae_return_1x))
        max_dd = min(max_dd, trough / peak - 1.0)
        trade_return = leverage * float(row.net_return_1x)
        wins += int(trade_return > 0.0)
        equity *= max(1e-9, 1.0 + trade_return)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    trades = len(chosen)
    years = max((end - start).total_seconds() / (365.25 * 86400.0), 1 / 365.25)
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "trades": trades,
        "wins": wins,
        "win_rate": wins / trades if trades else None,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (1.0 / years) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
    }


def main() -> None:
    freeze_sha256 = hashlib.sha256(FREEZE_PATH.read_bytes()).hexdigest()
    if freeze_sha256 != EXPECTED_FREEZE_SHA256:
        raise RuntimeError(
            f"freeze manifest hash mismatch: {freeze_sha256} != {EXPECTED_FREEZE_SHA256}"
        )

    account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    account_scale = account["comparisons"]["nonpreemptive"]["frozen_params"][
        "account_scale"
    ]
    if not math.isclose(float(account_scale), 0.75):
        raise RuntimeError(f"unexpected V1 account scale: {account_scale}")

    frame = pd.read_csv(TRADES_PATH)
    frame = frame.loc[
        (frame["mode"] == "nonpreemptive") & (frame["scenario"] == "base")
    ].copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)

    end = pd.Timestamp(account["portfolio_end"])
    starts = {
        "last_1d": end - pd.Timedelta(days=1),
        "last_7d": end - pd.Timedelta(days=7),
        "last_1m": end - pd.DateOffset(months=1),
        "last_3m": end - pd.DateOffset(months=3),
        "last_6m": end - pd.DateOffset(months=6),
        "last_1y": end - pd.DateOffset(years=1),
    }
    boundary_crossings = {
        name: int(
            ((frame["entry_ts"] < start) & (frame["exit_ts"] >= start)).sum()
        )
        for name, start in starts.items()
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "version": "Binance-15M-Asset-Specific-Six-Strategy-Selector-V1",
        "short_id": "BIN-15M-AS6S-V1",
        "route": "nonpreemptive",
        "scenario": "base",
        "account_scale": account_scale,
        "portfolio_end": end.isoformat(),
        "fee_per_fill": 0.001,
        "adverse_slippage_per_fill": 0.0004,
        "funding": "Binance actual historical funding",
        "freeze_manifest_sha256": freeze_sha256,
        "slice_rule": "entry_ts >= window_start and exit_ts < portfolio_end",
        "boundary_crossing_positions": boundary_crossings,
        "windows": {
            name: slice_metrics(frame, start, end) for name, start in starts.items()
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT_PATH), "windows": payload["windows"]}, indent=2))


if __name__ == "__main__":
    main()
