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
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
DISCOVERY_DIR = FAMILY_DIR / "artifacts/per_asset_hf_discovery"
OUTPUT_DIR = FAMILY_DIR / "artifacts/per_asset_hf_filter_tune"
MII_SCRIPTS = ROOT / "research/hype/15m-multi-indicator-intraday/scripts"
AS6S_SCRIPTS = FAMILY_DIR / "scripts"
sys.path.insert(0, str(MII_SCRIPTS))
sys.path.insert(0, str(AS6S_SCRIPTS))

import research_hype_15m_mii_search as mii  # noqa: E402
from as6s_engine import REUSED_END, STARTS, load_symbol_frame  # noqa: E402
from research_binance_as6s_per_asset_hf_discovery import (  # noqa: E402
    HISTORICAL_OOS_END,
    PREFIT_END,
    ROUND_TRIP_COST,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune per-asset MII filters after discovery.")
    parser.add_argument("--symbol", choices=tuple(STARTS), required=True)
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--pairs", type=int, default=120)
    return parser.parse_args()


def window_metric(
    picked: list[mii.EventTrade], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, Any]:
    trades = [trade for trade in picked if start <= trade.entry_ts and trade.exit_ts < end]
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    values: list[float] = []
    for trade in trades:
        trough = equity * max(1e-9, 1.0 + trade.min_path_return - ROUND_TRIP_COST)
        max_dd = min(max_dd, trough / peak - 1.0)
        value = trade.raw_return - ROUND_TRIP_COST
        equity *= max(1e-9, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        values.append(value)
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    return {
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (365.25 / days) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else math.inf,
        "avg_trade": float(np.mean(values)) if values else 0.0,
        "trades_per_day": len(trades) / days,
        "long_trades": sum(trade.direction > 0 for trade in trades),
        "short_trades": sum(trade.direction < 0 for trade in trades),
    }


def finite_pf(value: float) -> float:
    return 20.0 if math.isinf(value) else max(float(value), 1e-9)


def score(row: dict[str, Any]) -> float:
    windows = (row["prefit"], row["historical_oos"], row["current_3m"])
    if windows[1]["trades"] < 8 or windows[2]["trades"] < 8:
        return -1e9
    min_win = min(metric["win_rate"] for metric in windows)
    worst_dd = min(metric["max_dd"] for metric in windows)
    min_pf = min(finite_pf(metric["profit_factor"]) for metric in windows)
    positive = sum(metric["total_return"] > 0.0 for metric in windows)
    frequency = sum(metric["trades"] for metric in windows) / max(
        sum(
            (end - start).total_seconds() / 86400.0
            for start, end in (
                (row["asset_start"], PREFIT_END),
                (PREFIT_END, HISTORICAL_OOS_END),
                (HISTORICAL_OOS_END, REUSED_END),
            )
        ),
        1.0,
    )
    return float(
        1.3 * math.log(max(windows[0]["annual_multiple"], 1e-9))
        + 1.2 * math.log(max(windows[1]["annual_multiple"], 1e-9))
        + 0.9 * math.log(max(windows[2]["annual_multiple"], 1e-9))
        + 3.0 * min_win
        + 0.55 * math.log(min_pf)
        + 1.5 * worst_dd
        + 1.2 * positive
        + 0.3 * math.log1p(sum(metric["trades"] for metric in windows))
        + 12.0 * min(0.0, min_win - 0.75)
        + 12.0 * min(0.0, worst_dd + 0.20)
        + 5.0 * min(0.0, frequency - 0.12)
    )


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_path = DISCOVERY_DIR / f"{args.symbol.lower()}_hf_discovery_2026-07-14.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    raw = load_symbol_frame(args.symbol, end=REUSED_END)[
        ["ts", "open", "high", "low", "close", "volume"]
    ].copy()
    signal_specs = mii.signal_specs()
    spans = sorted(
        {value for spec in signal_specs for value in (spec.fast, spec.slow) if value}
    )
    features = mii.add_features(raw, spans)
    market = mii.build_market_arrays(features)
    signal_lookup = {spec.name: spec for spec in signal_specs}

    pair_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in source["ranking"]:
        signal_spec = mii.SignalSpec(**row["signal"])
        exit_spec = mii.ExitSpec(**row["exit"])
        pair_rows.setdefault((signal_spec.name, exit_spec.name), row)
        if len(pair_rows) >= args.pairs:
            break

    states: dict[str, mii.SignalState] = {}
    trade_cache: dict[tuple[str, str], list[mii.EventTrade]] = {}
    filters = mii.filter_specs()
    ranking: list[dict[str, Any]] = []
    evaluated = 0
    for pair_no, ((signal_name, exit_name), seed) in enumerate(pair_rows.items(), start=1):
        signal_spec = signal_lookup[signal_name]
        exit_spec = mii.ExitSpec(**seed["exit"])
        if exit_spec.name != exit_name:
            raise RuntimeError("exit reconstruction mismatch")
        state = states.setdefault(signal_name, mii.signal_state(features, signal_spec))
        raw_trades = mii.simulate_trades(market, state, exit_spec)
        trade_cache[(signal_name, exit_name)] = raw_trades
        for filter_spec in filters:
            evaluated += 1
            picked = mii.selected_trades(raw_trades, filter_spec)
            row = {
                "signal": asdict(signal_spec),
                "exit": asdict(exit_spec),
                "filter": asdict(filter_spec),
                "filter_name": filter_spec.name,
                "asset_start": STARTS[args.symbol],
                "prefit": window_metric(picked, STARTS[args.symbol], PREFIT_END),
                "historical_oos": window_metric(
                    picked, PREFIT_END, HISTORICAL_OOS_END
                ),
                "current_3m": window_metric(picked, HISTORICAL_OOS_END, REUSED_END),
                "through_current": window_metric(
                    picked, STARTS[args.symbol], REUSED_END
                ),
            }
            row["score"] = score(row)
            if row["score"] <= -1e8:
                continue
            ranking.append(row)
        ranking.sort(key=lambda row: row["score"], reverse=True)
        del ranking[max(args.top * 10, 1500) :]
        if pair_no % 10 == 0:
            print(
                f"{args.symbol} pairs={pair_no}/{len(pair_rows)} "
                f"evaluated={evaluated} kept={len(ranking)}",
                flush=True,
            )

    ranking.sort(key=lambda row: row["score"], reverse=True)
    for row in ranking:
        row["asset_start"] = row["asset_start"].isoformat()
    hard80 = [
        row
        for row in ranking
        if all(
            row[name]["trades"] >= 8
            and row[name]["win_rate"] >= 0.80
            and row[name]["total_return"] > 0.0
            and row[name]["max_dd"] > -0.20
            for name in ("prefit", "historical_oos", "current_3m")
        )
    ]
    output = OUTPUT_DIR / f"{args.symbol.lower()}_hf_filter_tune_2026-07-14.json"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "filter_tune_discovery_only_not_live_ready",
        "symbol": args.symbol,
        "source": str(source_path.relative_to(ROOT)),
        "pairs": len(pair_rows),
        "filters": len(filters),
        "evaluated": evaluated,
        "hard80_count_before_robust_replay": len(hard80),
        "disclosure": (
            "Current 3m participates in research ranking. Final future OOS remains locked. "
            "Results still require funding, gap-safe, 8bps and K+2 replay."
        ),
        "ranking": ranking[: args.top],
        "hard80": hard80[: args.top],
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "symbol": args.symbol,
                "output": str(output),
                "pairs": len(pair_rows),
                "evaluated": evaluated,
                "hard80": len(hard80),
                "best": ranking[0] if ranking else None,
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
