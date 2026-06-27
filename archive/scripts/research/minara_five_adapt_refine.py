from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import minara_21_approx_backtest as base
import minara_five_adapt_search as coarse


OUT = Path("archive/reports/legacy/minara_five_adapt_btc_hype_refined")


def main() -> None:
    data = coarse._load_data()
    results = []
    for symbol, family, timeframe, params in _refine_grid():
        frame = data[symbol][timeframe]
        rule = coarse._build_rule(family, frame, params)
        equity, trades = base.backtest(frame, rule, allocation=1.0)
        row = asdict(
            coarse._evaluate(
                family=family,
                symbol=symbol,
                timeframe=timeframe,
                params=params,
                equity=equity,
                trades=trades,
            )
        )
        row["return"] = row.pop("return_")
        results.append(row)

    ranked = (
        pd.DataFrame(results)
        .sort_values(["calmar", "return", "sharpe"], ascending=[False, False, False])
        .reset_index(drop=True)
    )
    valid = ranked[ranked["trades"].ge(5)].copy()
    top_by_group = (
        valid.groupby(["symbol", "family"], group_keys=False)
        .head(10)
        .reset_index(drop=True)
    )
    payload = {
        "note": "Refinement grid around the best coarse-search directions. Uses the same fee-adjusted close-entry/intrabar-stop model as the 21-strategy approximation.",
        "top_by_symbol_family_min_5_trades": top_by_group.to_dict("records"),
        "global_top_min_5_trades": valid.head(80).to_dict("records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    ranked.to_csv(f"{OUT}_all.csv", index=False)
    top_by_group.to_csv(f"{OUT}_top_by_group.csv", index=False)
    print(
        top_by_group[
            [
                "symbol",
                "family",
                "timeframe",
                "return",
                "max_drawdown",
                "calmar",
                "trades",
                "robustness",
                "params",
            ]
        ].head(100).to_string(index=False)
    )
    print(f"wrote {OUT}.json")


def _refine_grid() -> list[tuple[str, str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, str, dict[str, Any]]] = []
    rows.extend(_kinetic())
    rows.extend(_macd())
    rows.extend(_supertrend())
    rows.extend(_qullamagi())
    rows.extend(_hash_momentum())
    return rows


def _kinetic() -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = []
    for symbol, tf, gain, lookback, band, mode, stop, take in itertools.product(
        ["BTC/USDT:USDT", "HYPE/USDT:USDT"],
        ["4h"],
        [0.15, 0.20, 0.25],
        [150, 200, 250],
        [2.0, 2.5, 2.8],
        ["both", "long"],
        [None, 0.04, 0.05, 0.06],
        [None, 0.08, 0.10, 0.12],
    ):
        if (stop is None) != (take is None):
            continue
        rows.append((symbol, "kinetic_kalman", tf, {
            "gain": gain,
            "lookback": lookback,
            "band_mult": band,
            "mode": mode,
            "stop_pct": stop,
            "take_pct": take,
        }))
    return rows


def _macd() -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = []
    for symbol, tf, fast, slow, sig, mode, stop, take in itertools.product(
        ["BTC/USDT:USDT", "HYPE/USDT:USDT"],
        ["4h", "1d"],
        [8, 12],
        [26, 35],
        [9],
        ["long", "both"],
        [None, 0.08],
        [None, 0.20],
    ):
        if fast >= slow or (stop is None) != (take is None):
            continue
        rows.append((symbol, "macd_zero", tf, {
            "fast": fast,
            "slow": slow,
            "signal_len": sig,
            "mode": mode,
            "stop_pct": stop,
            "take_pct": take,
        }))
    return rows


def _supertrend() -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = []
    for symbol, tf, window, mult, mode, stop, take in itertools.product(
        ["BTC/USDT:USDT", "HYPE/USDT:USDT"],
        ["4h", "1d"],
        [10, 12, 14],
        [2.5, 3.0, 3.5],
        ["long", "both"],
        [None, 0.10],
        [None, 0.30],
    ):
        if (stop is None) != (take is None):
            continue
        rows.append((symbol, "supertrend", tf, {
            "window": window,
            "mult": mult,
            "mode": mode,
            "stop_pct": stop,
            "take_pct": take,
        }))
    return rows


def _qullamagi() -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = []
    presets = [
        (5, 15, 67, 200, 350),
        (10, 20, 50, 100, 200),
    ]
    for symbol, preset, box, volume, mode, stop, take in itertools.product(
        ["BTC/USDT:USDT", "HYPE/USDT:USDT"],
        presets,
        [20, 36],
        [1.0, 1.5],
        ["long", "both"],
        [0.06, 0.10],
        [0.12, 0.25],
    ):
        if take <= stop * 1.8:
            continue
        rows.append((symbol, "qullamagi", "4h", {
            "preset": preset,
            "box": box,
            "volume_mult": volume,
            "mode": mode,
            "stop_pct": stop,
            "take_pct": take,
        }))
    return rows


def _hash_momentum() -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = []
    for symbol, tf, lookback, threshold, ema, mode, stop, take in itertools.product(
        ["BTC/USDT:USDT", "HYPE/USDT:USDT"],
        ["1h", "4h"],
        [12, 24, 36],
        [2.5, 3.0, 3.5],
        [50, 100],
        ["long", "both"],
        [0.04, 0.08],
        [0.10, 0.20],
    ):
        if take <= stop * 2:
            continue
        rows.append((symbol, "hash_momentum", tf, {
            "lookback": lookback,
            "threshold": threshold,
            "ema": ema,
            "mode": mode,
            "stop_pct": stop,
            "take_pct": take,
        }))
    return rows


if __name__ == "__main__":
    main()
