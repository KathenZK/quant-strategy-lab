from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
MII_SCRIPTS = ROOT / "research/hype/15m-multi-indicator-intraday/scripts"
AS6S_SCRIPTS = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector/scripts"
sys.path.insert(0, str(MII_SCRIPTS))
sys.path.insert(0, str(AS6S_SCRIPTS))

import research_hype_15m_mii_search as mii  # noqa: E402
from as6s_engine import REUSED_END, STARTS, load_symbol_frame  # noqa: E402


FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/per_asset_hf_discovery"
SYMBOLS = tuple(STARTS)
PREFIT_END = pd.Timestamp("2026-01-14T09:00:00Z")
HISTORICAL_OOS_END = pd.Timestamp("2026-04-14T09:00:00Z")
ROUND_TRIP_COST = 2.0 * (0.001 + 0.0004)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Per-asset high-frequency mechanism discovery for BIN-15M-AS6S."
    )
    parser.add_argument("--symbol", choices=SYMBOLS, required=True)
    parser.add_argument("--top", type=int, default=120)
    parser.add_argument("--max-signals", type=int, default=0)
    parser.add_argument("--max-exits", type=int, default=0)
    return parser.parse_args()


def metrics(
    trades: list[mii.EventTrade],
    filter_spec: mii.FilterSpec,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    picked = [
        trade
        for trade in mii.selected_trades(trades, filter_spec)
        if start <= trade.entry_ts and trade.exit_ts < end
    ]
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    net_returns: list[float] = []
    for trade in picked:
        trough = equity * max(1e-9, 1.0 + trade.min_path_return - ROUND_TRIP_COST)
        max_dd = min(max_dd, trough / peak - 1.0)
        net = trade.raw_return - ROUND_TRIP_COST
        equity *= max(1e-9, 1.0 + net)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        net_returns.append(net)
    positives = [value for value in net_returns if value > 0.0]
    negatives = [value for value in net_returns if value < 0.0]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    years = days / 365.25
    return {
        "trades": len(picked),
        "wins": len(positives),
        "win_rate": len(positives) / len(picked) if picked else 0.0,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (1.0 / years) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": (
            sum(positives) / abs(sum(negatives)) if negatives else math.inf
        ),
        "avg_trade": float(np.mean(net_returns)) if net_returns else 0.0,
        "trades_per_day": len(picked) / days,
        "long_trades": sum(trade.direction > 0 for trade in picked),
        "short_trades": sum(trade.direction < 0 for trade in picked),
    }


def finite_pf(value: float) -> float:
    return 20.0 if math.isinf(value) else max(float(value), 1e-9)


def prefit_score(metric: dict[str, Any]) -> float:
    if metric["trades"] < 12 or metric["total_return"] <= 0.0:
        return -1e9
    win_gap = min(0.0, metric["win_rate"] - 0.80)
    dd_gap = min(0.0, metric["max_dd"] + 0.20)
    low_frequency_gap = min(0.0, metric["trades_per_day"] - 0.12)
    high_frequency_gap = min(0.0, 2.5 - metric["trades_per_day"])
    return float(
        2.2 * math.log(max(metric["annual_multiple"], 1e-9))
        + 2.0 * metric["win_rate"]
        + 0.65 * math.log(finite_pf(metric["profit_factor"]))
        + 1.0 * metric["max_dd"]
        + 0.25 * math.log1p(metric["trades"])
        + 10.0 * win_gap
        + 10.0 * dd_gap
        + 8.0 * low_frequency_gap
        + 3.0 * high_frequency_gap
    )


def multiwindow_score(row: dict[str, Any]) -> float:
    prefit = row["prefit"]
    oos = row["historical_oos"]
    current = row["current_3m"]
    if oos["trades"] < 8 or current["trades"] < 8:
        return -1e9
    windows = (prefit, oos, current)
    positive_windows = sum(metric["total_return"] > 0.0 for metric in windows)
    min_win = min(metric["win_rate"] for metric in windows)
    worst_dd = min(metric["max_dd"] for metric in windows)
    min_pf = min(finite_pf(metric["profit_factor"]) for metric in windows)
    return float(
        1.6 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.2 * math.log(max(oos["annual_multiple"], 1e-9))
        + 0.8 * math.log(max(current["annual_multiple"], 1e-9))
        + 2.0 * min_win
        + 0.5 * math.log(min_pf)
        + 1.5 * worst_dd
        + 0.35 * math.log1p(sum(metric["trades"] for metric in windows))
        + 1.2 * positive_windows
        + 12.0 * min(0.0, min_win - 0.70)
        + 12.0 * min(0.0, worst_dd + 0.20)
    )


def candidate_key(row: dict[str, Any]) -> tuple[float, float, float, int]:
    return (
        float(row["score"]),
        float(row["historical_oos"]["win_rate"]),
        float(row["current_3m"]["win_rate"]),
        int(row["prefit"]["trades"]),
    )


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    symbol = args.symbol
    raw = load_symbol_frame(symbol, end=REUSED_END)[
        ["ts", "open", "high", "low", "close", "volume"]
    ].copy()
    signal_specs = mii.signal_specs()
    if args.max_signals:
        signal_specs = signal_specs[: args.max_signals]
    spans = sorted(
        {value for spec in signal_specs for value in (spec.fast, spec.slow) if value}
    )
    features = mii.add_features(raw, spans)
    full_market = mii.build_market_arrays(features)
    prefit_rows = int((features["ts"] < PREFIT_END).sum())
    prefit_features = features.iloc[:prefit_rows].reset_index(drop=True)
    prefit_market = mii.build_market_arrays(prefit_features)
    filters = mii.base_filter_specs()
    exit_specs = mii.coarse_exit_specs()
    if args.max_exits:
        exit_specs = exit_specs[: args.max_exits]

    prefit_frontier: list[dict[str, Any]] = []
    evaluated = 0
    simulated = 0
    for signal_no, signal_spec in enumerate(signal_specs, start=1):
        state = mii.signal_state(prefit_features, signal_spec)
        if len(state.signal_i) < 12:
            continue
        for exit_spec in exit_specs:
            raw_trades = mii.simulate_trades(prefit_market, state, exit_spec)
            simulated += 1
            if len(raw_trades) < 12:
                continue
            for filter_spec in filters:
                evaluated += 1
                metric = metrics(
                    raw_trades,
                    filter_spec,
                    start=STARTS[symbol],
                    end=PREFIT_END,
                )
                score = prefit_score(metric)
                if score <= -1e8:
                    continue
                prefit_frontier.append(
                    {
                        "signal": asdict(signal_spec),
                        "exit": asdict(exit_spec),
                        "filter": asdict(filter_spec),
                        "prefit": metric,
                        "prefit_score": score,
                    }
                )
        prefit_frontier.sort(key=lambda row: row["prefit_score"], reverse=True)
        del prefit_frontier[max(args.top * 8, 600) :]
        if signal_no % 10 == 0:
            print(
                f"{symbol} signals={signal_no}/{len(signal_specs)} "
                f"simulated={simulated} evaluated={evaluated} kept={len(prefit_frontier)}",
                flush=True,
            )

    unique_specs: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in prefit_frontier:
        key = (
            mii.SignalSpec(**row["signal"]).name,
            mii.ExitSpec(**row["exit"]).name,
            mii.FilterSpec(**row["filter"]).name,
        )
        unique_specs.setdefault(key, row)

    full_state_cache: dict[str, mii.SignalState] = {}
    full_trade_cache: dict[tuple[str, str], list[mii.EventTrade]] = {}
    audited: list[dict[str, Any]] = []
    for row in unique_specs.values():
        signal_spec = mii.SignalSpec(**row["signal"])
        exit_spec = mii.ExitSpec(**row["exit"])
        filter_spec = mii.FilterSpec(**row["filter"])
        state = full_state_cache.setdefault(
            signal_spec.name, mii.signal_state(features, signal_spec)
        )
        trade_key = (signal_spec.name, exit_spec.name)
        raw_trades = full_trade_cache.get(trade_key)
        if raw_trades is None:
            raw_trades = mii.simulate_trades(full_market, state, exit_spec)
            full_trade_cache[trade_key] = raw_trades
        candidate = {
            **row,
            "historical_oos": metrics(
                raw_trades,
                filter_spec,
                start=PREFIT_END,
                end=HISTORICAL_OOS_END,
            ),
            "current_3m": metrics(
                raw_trades,
                filter_spec,
                start=HISTORICAL_OOS_END,
                end=REUSED_END,
            ),
            "through_current": metrics(
                raw_trades,
                filter_spec,
                start=STARTS[symbol],
                end=REUSED_END,
            ),
        }
        candidate["score"] = multiwindow_score(candidate)
        audited.append(candidate)

    audited.sort(key=candidate_key, reverse=True)
    ranking = audited[: args.top]
    output = ARTIFACT_DIR / f"{symbol.lower()}_hf_discovery_2026-07-14.json"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "mechanism_discovery_only_not_live_ready",
        "symbol": symbol,
        "data_window": [STARTS[symbol].isoformat(), REUSED_END.isoformat()],
        "selection_windows": {
            "prefit": [STARTS[symbol].isoformat(), PREFIT_END.isoformat()],
            "historical_oos": [PREFIT_END.isoformat(), HISTORICAL_OOS_END.isoformat()],
            "current_3m_diagnostic": [
                HISTORICAL_OOS_END.isoformat(),
                REUSED_END.isoformat(),
            ],
            "future_final_oos": [
                REUSED_END.isoformat(),
                "2026-10-14T09:00:00+00:00",
            ],
        },
        "disclosure": (
            "Discovery uses HYPE MII signal priors and approximate fixed round-trip costs. "
            "Funding, gap-safe fills, 8bps, K+2 and account arbitration are mandatory in the next replay stage."
        ),
        "search_space": {
            "signals": len(signal_specs),
            "exits": len(exit_specs),
            "filters": len(filters),
            "simulated": simulated,
            "evaluated": evaluated,
            "prefit_retained": len(prefit_frontier),
            "full_replays": len(full_trade_cache),
        },
        "ranking": ranking,
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "symbol": symbol,
                "output": str(output),
                "ranking": len(ranking),
                "best": ranking[0] if ranking else None,
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
