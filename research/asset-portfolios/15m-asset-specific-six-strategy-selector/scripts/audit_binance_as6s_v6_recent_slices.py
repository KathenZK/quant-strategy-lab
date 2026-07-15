#!/usr/bin/env python3
"""Audit V6 base-cost recent slices at the locked research cutoff."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


FAMILY_DIR = Path(__file__).resolve().parents[1]
FREEZE = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json"
)
TRADES = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_trades_2026-07-15.csv"
)
EXPECTED_FREEZE_SHA256 = "c29f3f89f1b786e26b3aa58343255ac88eaf12dcbfccac46be9d98196cc93cc9"
END = pd.Timestamp("2026-07-14T09:00:00Z")
MODES = ("nonpreemptive", "strong_breakout_preemptive")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def metrics(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    chosen = frame.loc[
        (frame["entry_ts"] >= start) & (frame["exit_ts"] < end)
    ].sort_values("exit_ts")
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    returns: list[float] = []
    for row in chosen.itertuples():
        leverage = float(row.scale) * float(row.exposure)
        trough = equity * max(1e-9, 1.0 + leverage * float(row.mae_return_1x))
        max_dd = min(max_dd, trough / peak - 1.0)
        value = leverage * float(row.net_return_1x)
        equity *= max(1e-9, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        returns.append(value)
    positives = [value for value in returns if value > 0.0]
    negatives = [value for value in returns if value < 0.0]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    years = max(days / 365.25, 1.0 / 365.25)
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "trades": len(chosen),
        "wins": len(positives),
        "win_rate": len(positives) / len(chosen) if len(chosen) else None,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (1.0 / years) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": (
            sum(positives) / abs(sum(negatives)) if negatives else None
        ),
        "long_trades": int((chosen["side"] > 0).sum()),
        "short_trades": int((chosen["side"] < 0).sum()),
        "preemptions": int(
            (chosen["exit_reason"] == "strong_breakout_preemption").sum()
        ),
        "trades_per_day": len(chosen) / days,
    }


def close(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-10)


def main() -> None:
    freeze_hash = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    require(freeze_hash == EXPECTED_FREEZE_SHA256, "freeze manifest hash drifted")
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
    frame = pd.read_csv(TRADES)
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    require(frame["entry_ts"].max() < END, "recent-slice input crossed OOS start")
    require(frame["exit_ts"].max() < END, "recent-slice exits crossed OOS start")
    require(set(frame["mode"]) == set(MODES), "route set drifted")
    require(set(frame["scale"]) == {0.75}, "account scale drifted")

    starts = {
        "1d": END - pd.Timedelta(days=1),
        "7d": END - pd.Timedelta(days=7),
        "1m": END - pd.DateOffset(months=1),
        "3m": END - pd.DateOffset(months=3),
        "6m": END - pd.DateOffset(months=6),
        "1y": END - pd.DateOffset(years=1),
    }
    output: dict[str, Any] = {}
    parity_fields = (
        "trades",
        "wins",
        "win_rate",
        "total_return",
        "annual_multiple",
        "max_dd",
        "profit_factor",
        "long_trades",
        "short_trades",
        "preemptions",
        "trades_per_day",
    )
    for mode in MODES:
        route_frame = frame.loc[frame["mode"] == mode].copy()
        expected_full = frozen["frozen_development_metrics"][mode]["scenarios"][
            "base"
        ]["full"]
        require(len(route_frame) == expected_full["trades"], f"{mode} trade count drifted")
        slices = {name: metrics(route_frame, start, END) for name, start in starts.items()}
        for current_key, frozen_key in (
            ("1m", "1m"),
            ("3m", "current_3m"),
            ("6m", "6m"),
            ("1y", "1y"),
        ):
            expected = frozen["frozen_development_metrics"][mode]["scenarios"][
                "base"
            ][frozen_key]
            for field in parity_fields:
                require(
                    close(slices[current_key][field], expected[field]),
                    f"{mode}.{current_key}.{field} parity drift",
                )
        output[mode] = slices

    print(
        json.dumps(
            {
                "result": "PASS",
                "version": frozen["version"],
                "market": "Binance USD-M Futures perpetual",
                "symbols": [
                    "BTCUSDT",
                    "ETHUSDT",
                    "SOLUSDT",
                    "BNBUSDT",
                    "TRXUSDT",
                    "HYPEUSDT",
                ],
                "cost_model": {
                    "fee_per_fill": 0.001,
                    "adverse_slippage_per_fill": 0.0004,
                    "funding": "historical Binance funding",
                },
                "slice_anchor_end_exclusive": END.isoformat(),
                "selection_use": "diagnostic only; all slices were already observable at freeze",
                "future_oos_read": False,
                "freeze_sha256": freeze_hash,
                "routes": output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
