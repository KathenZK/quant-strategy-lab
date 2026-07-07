"""Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble single-position variant.

Same six frozen sleeves as the first combination backtest (TRX V3, SOL V2,
HYPE V4, ETH V3, BTC V4, BNB V3), but the whole account holds at most ONE
position at a time across all six symbols:

- All six strategies generate signals in parallel.
- First entry wins the slot ("first come, first served"); while a position
  is open every other signal (any asset, any leg) is ignored.
- Nothing pre-empts an open position: no early close, no swap.
- A new entry is allowed only strictly after the previous trade's exit bar,
  mirroring the per-family `merge_trade_sets` blocking semantics.
- Same-hour entry ties are broken by frozen family current-full annual
  multiple (descending), and the tie count is reported.
- The winning trade runs on FULL account equity at its own frozen exposure,
  so per-trade leverage equals the sleeve's fixed leverage (up to 5x TRX).

Costs per sleeve are unchanged: fee 0.001/fill, slippage 4 bps/fill, actual
Binance funding. All windows are post-freeze audit only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SCRIPT_DIR = Path(__file__).resolve().parent
DATE_TAG = "2026-07-07"
SUMMARY_JSON = ARTIFACT_DIR / f"binance_1h_ar_mae_single_position_{DATE_TAG}.json"
EQUITY_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_single_position_equity_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_single_position_trades_{DATE_TAG}.csv"

# Same-hour entry tie-break: frozen family current-full annual multiple.
TIE_PRIORITY = {
    "HYPE": 22.8128,
    "TRX": 5.686,
    "BTC": 5.27,
    "ETH": 3.3084,
    "BNB": 2.94,
    "SOL": 2.07,
}

SLICES = (
    ("last_1d", pd.Timedelta(days=1)),
    ("last_7d", pd.Timedelta(days=7)),
    ("last_1m", pd.DateOffset(months=1)),
    ("last_3m", pd.DateOffset(months=3)),
    ("last_6m", pd.DateOffset(months=6)),
    ("last_1y", pd.DateOffset(years=1)),
)


def load_first_backtest_module() -> Any:
    name = "research_binance_1h_ar_multi_asset_ensemble_backtest"
    if name in sys.modules:
        return sys.modules[name]
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def select_single_position(
    tagged: list[tuple[str, Any]],
) -> tuple[list[tuple[str, Any]], list[tuple[str, Any]], int]:
    """Greedy first-come single-position selection across all sleeves."""
    ordered = sorted(
        tagged,
        key=lambda item: (
            item[1].entry_ts,
            -TIE_PRIORITY[item[0]],
            item[1].exit_ts,
        ),
    )
    selected: list[tuple[str, Any]] = []
    skipped: list[tuple[str, Any]] = []
    blocked_until: pd.Timestamp | None = None
    ties = 0
    previous_entry: pd.Timestamp | None = None
    for asset, trade in ordered:
        if previous_entry is not None and trade.entry_ts == previous_entry:
            ties += 1
        previous_entry = trade.entry_ts
        if blocked_until is not None and trade.entry_ts <= blocked_until:
            skipped.append((asset, trade))
            continue
        selected.append((asset, trade))
        blocked_until = trade.exit_ts
    return selected, skipped, ties


def portfolio_curve(
    selected: list[tuple[str, Any]],
    frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    """Hourly account equity with intra-trade close-based mark-to-market."""
    timeline = pd.date_range(start, end, freq="1h", tz="UTC")
    values = pd.Series(np.nan, index=timeline, dtype="float64")
    values.iloc[0] = 1.0
    equity = 1.0
    for asset, trade in selected:
        frame = frames[asset]
        entry_i = int(trade.entry_i)
        exit_i = int(trade.exit_i)
        close = frame["close"].to_numpy(dtype="float64")
        close_ts = frame["ts"] + pd.Timedelta(hours=1)
        for i in range(entry_i, exit_i):
            ts = close_ts.iloc[i]
            if ts < start or ts > end:
                continue
            mark = close[i] / float(trade.entry_price) - 1.0
            values.loc[ts] = equity * (
                1.0 + float(trade.exposure) * float(trade.side) * mark
            )
        equity *= 1.0 + float(trade.equity_ret)
        exit_ts_close = close_ts.iloc[exit_i]
        if start <= exit_ts_close <= end:
            values.loc[exit_ts_close] = equity
    return values.ffill().fillna(1.0)


def trade_stats(selected: list[tuple[str, Any]], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
    returns = [
        float(trade.equity_ret)
        for _asset, trade in selected
        if start <= trade.entry_ts < end
    ]
    if not returns:
        return {"trades": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
    positives = [value for value in returns if value > 0]
    negatives = [abs(value) for value in returns if value < 0]
    return {
        "trades": float(len(returns)),
        "win_rate": float(len(positives) / len(returns)),
        "profit_factor": (
            float(sum(positives) / sum(negatives)) if negatives else float("inf")
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    first = load_first_backtest_module()

    sleeves: list[dict[str, Any]] = []
    for loader in (
        first.load_trx,
        first.load_sol,
        first.load_hype,
        first.load_eth,
        first.load_btc,
        first.load_bnb,
    ):
        sleeve = loader()
        metric = first.verify_sleeve(sleeve)
        sleeve["trades"] = [
            trade
            for trade in sleeve["trades"]
            if sleeve["start"] <= trade.entry_ts < sleeve["end"]
        ]
        sleeves.append(sleeve)
        print(
            f"verified {sleeve['asset']} {sleeve['version']}: "
            f"annual={metric['annual_multiple']:.4f}x trades={int(metric['trades'])}",
            flush=True,
        )

    start = max(s["start"] for s in sleeves if s["asset"] != "HYPE")
    hype_start = next(s["start"] for s in sleeves if s["asset"] == "HYPE")
    end = min(s["end"] for s in sleeves)

    tagged = [
        (sleeve["asset"], trade)
        for sleeve in sleeves
        for trade in sleeve["trades"]
        if start <= trade.entry_ts < end
    ]
    selected, skipped, ties = select_single_position(tagged)
    frames = {sleeve["asset"]: sleeve["frame"] for sleeve in sleeves}
    curve = portfolio_curve(selected, frames, start, end)

    windows: list[tuple[str, pd.Timestamp]] = [
        ("full", start),
        ("all_six_active", hype_start),
        ("reused_holdout", pd.Timestamp("2026-04-03T00:00:00Z")),
    ]
    for name, delta in SLICES:
        windows.append((name, max(start, end - delta)))

    results: dict[str, Any] = {}
    for name, window_start in windows:
        results[name] = {
            "start": window_start,
            "end": end,
            "curve": first.curve_metrics(curve, window_start, end),
            "trade_stats": trade_stats(selected, window_start, end),
        }

    candidate_count = len(tagged)
    selected_count = len(selected)
    per_asset_selected = {
        asset: int(sum(1 for a, _t in selected if a == asset))
        for asset in frames
    }
    per_asset_candidates = {
        asset: int(sum(1 for a, _t in tagged if a == asset)) for asset in frames
    }
    exposures = [float(trade.exposure) for _a, trade in selected]
    hold_hours = [
        (trade.exit_ts - trade.entry_ts).total_seconds() / 3600.0
        for _a, trade in selected
    ]
    in_position_hours = float(sum(hold_hours))
    total_hours = float((end - start).total_seconds() / 3600.0)

    trades_rows = [
        {
            "asset": asset,
            "style": trade.style,
            "entry_ts": trade.entry_ts,
            "exit_ts": trade.exit_ts,
            "side": trade.side,
            "exposure": trade.exposure,
            "equity_ret": trade.equity_ret,
            "exit_reason": trade.exit_reason,
        }
        for asset, trade in selected
    ]
    pd.DataFrame(trades_rows).to_csv(TRADES_CSV, index=False)
    curve.rename("portfolio_single_position").to_csv(EQUITY_CSV, index_label="ts")

    payload = {
        "family": "Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble",
        "observation": "single_position_first_come_first_served",
        "status": "combination_diagnostic_not_promoted_not_live_ready",
        "date": DATE_TAG,
        "structure": (
            "one account-wide position slot; first entry wins; open position "
            "blocks all other signals until strictly after its exit bar; full "
            "account equity per trade at the sleeve's frozen exposure"
        ),
        "tie_break": "frozen family current-full annual multiple descending",
        "portfolio_start": start,
        "hype_sleeve_start": hype_start,
        "portfolio_end": end,
        "costs": {
            "fee_per_fill": 0.001,
            "slippage_per_fill": 0.0004,
            "funding": "actual_binance_history_per_trade",
        },
        "selection": {
            "candidate_trades": candidate_count,
            "selected_trades": selected_count,
            "skipped_blocked": len(skipped),
            "same_hour_entry_ties": ties,
            "per_asset_candidates": per_asset_candidates,
            "per_asset_selected": per_asset_selected,
            "avg_exposure": float(np.mean(exposures)) if exposures else 0.0,
            "max_exposure": float(np.max(exposures)) if exposures else 0.0,
            "median_hold_hours": float(np.median(hold_hours)) if hold_hours else 0.0,
            "in_position_hours_pct": in_position_hours / total_hours,
        },
        "portfolio_windows": results,
        "notes": [
            "All windows are post-freeze audit only; nothing was selected "
            "using these results.",
            "Sleeve trade paths are the frozen family versions; blocking only "
            "removes trades, it never alters entry/exit of kept trades.",
            "Skipped-by-blocking counterfactual is approximate for cooldown "
            "state: per-family cooldowns were simulated within each sleeve, "
            "not re-simulated after cross-asset blocking.",
        ],
    }
    SUMMARY_JSON.write_text(
        json.dumps(first.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    brief = {
        "selection": payload["selection"],
        "windows": {
            name: {
                "annual": results[name]["curve"]["annual_multiple"],
                "return": results[name]["curve"]["total_return"],
                "max_dd": results[name]["curve"]["max_dd"],
                "trades": results[name]["trade_stats"]["trades"],
                "win_rate": results[name]["trade_stats"]["win_rate"],
                "profit_factor": results[name]["trade_stats"]["profit_factor"],
            }
            for name, _ in windows
        },
    }
    print(json.dumps(first.json_safe(brief), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
