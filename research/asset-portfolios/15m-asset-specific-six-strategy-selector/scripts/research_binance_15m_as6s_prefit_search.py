from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from typing import Any

import numpy as np

from as6s_engine import (
    MECHANISMS,
    PREFIT_END,
    SYMBOLS,
    StrategyConfig,
    evaluate_prefit,
    load_funding,
    load_symbol_frame,
    prefit_score,
    prefit_windows,
    random_config,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
OUTPUT = ARTIFACT_DIR / "binance_15m_as6s_prefit_search_2026-07-14.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run OOS-unread asset-specific six-symbol mechanism search."
    )
    parser.add_argument("--trials-per-mechanism", type=int, default=1500)
    parser.add_argument("--keep-per-cell", type=int, default=12)
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args()


def hard_prefit_shape(result: dict[str, dict[str, float]]) -> bool:
    prefit = result["prefit"]
    val1 = result["validation_1"]
    val2 = result["validation_2"]
    return bool(
        prefit["trades"] >= 18
        and prefit["win_rate"] >= 0.75
        and prefit["max_dd"] > -0.20
        and prefit["total_return"] > 0.0
        and val1["trades"] >= 3
        and val2["trades"] >= 3
        and val1["win_rate"] >= 0.65
        and val2["win_rate"] >= 0.65
        and val1["total_return"] > 0.0
        and val2["total_return"] > 0.0
        and val1["max_dd"] > -0.20
        and val2["max_dd"] > -0.20
    )


def config_signature(cfg: StrategyConfig) -> str:
    payload = cfg.to_dict()
    payload.pop("config_id")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def search_symbol(symbol: str, trials: int, keep: int, seed: int) -> dict[str, Any]:
    frame = load_symbol_frame(symbol, end=PREFIT_END)
    funding = load_funding(symbol, end=PREFIT_END)
    atr_values = frame.loc[frame["ts"] < PREFIT_END, "atr_pct"].dropna().to_numpy(dtype=np.float64)
    symbol_result: dict[str, Any] = {}
    for mechanism_index, mechanism in enumerate(MECHANISMS):
        rng = random.Random(seed + mechanism_index * 1_000_003)
        retained: list[dict[str, Any]] = []
        seen: set[str] = set()
        generated = 0
        attempts = 0
        while generated < trials and attempts < trials * 10:
            attempts += 1
            cfg = random_config(symbol, mechanism, rng, generated, atr_values)
            signature = config_signature(cfg)
            if signature in seen:
                continue
            seen.add(signature)
            generated += 1
            opportunities = simulate_opportunities(frame, funding, cfg, end=PREFIT_END)
            result = evaluate_prefit(opportunities, symbol)
            score = prefit_score(result)
            if score <= -1e8:
                continue
            retained.append(
                {
                    "config": cfg.to_dict(),
                    "score": score,
                    "hard_prefit_shape": hard_prefit_shape(result),
                    **result,
                }
            )
            retained.sort(
                key=lambda row: (
                    row["hard_prefit_shape"],
                    row["score"],
                    row["prefit"]["win_rate"],
                    row["prefit"]["total_return"],
                ),
                reverse=True,
            )
            del retained[max(keep * 4, 48) :]
        retained.sort(
            key=lambda row: (
                row["hard_prefit_shape"],
                row["score"],
                row["prefit"]["win_rate"],
            ),
            reverse=True,
        )
        symbol_result[mechanism] = {
            "trials_requested": trials,
            "unique_evaluated": generated,
            "hard_prefit_hits_retained": sum(row["hard_prefit_shape"] for row in retained),
            "top": retained[:keep],
        }
        best = retained[0] if retained else None
        print(
            f"{symbol} {mechanism}: evaluated={generated} "
            f"best={None if best is None else best['prefit']}",
            flush=True,
        )
    return symbol_result


def main() -> None:
    args = parse_args()
    seeds = {symbol: 2026071400 + index * 100_000 for index, symbol in enumerate(SYMBOLS)}
    cells: dict[str, Any] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                search_symbol,
                symbol,
                args.trials_per_mechanism,
                args.keep_per_cell,
                seeds[symbol],
            ): symbol
            for symbol in SYMBOLS
        }
        for future in as_completed(futures):
            symbol = futures[future]
            cells[symbol] = future.result()
            print(f"completed {symbol}", flush=True)

    selected: list[dict[str, Any]] = []
    mechanism_prefit_ranking: dict[str, list[dict[str, Any]]] = {}
    for symbol in SYMBOLS:
        ranking: list[dict[str, Any]] = []
        for mechanism in MECHANISMS:
            top = cells[symbol][mechanism]["top"]
            if not top:
                continue
            best = top[0]
            selected.append(best["config"])
            ranking.append(
                {
                    "mechanism": mechanism,
                    "config_id": best["config"]["config_id"],
                    "score": best["score"],
                    "hard_prefit_shape": best["hard_prefit_shape"],
                    "prefit": best["prefit"],
                    "validation_1": best["validation_1"],
                    "validation_2": best["validation_2"],
                }
            )
        ranking.sort(
            key=lambda row: (row["hard_prefit_shape"], row["score"]), reverse=True
        )
        mechanism_prefit_ranking[symbol] = ranking

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "stage": "prefit_only_reused_holdout_unread_for_this_family",
        "selection_end_exclusive": PREFIT_END.isoformat(),
        "reused_holdout": {
            "start": PREFIT_END.isoformat(),
            "end": "2026-07-14T09:00:00+00:00",
            "role": "elimination_only_not_selection_not_final_oos",
        },
        "future_oos": {
            "start": "2026-07-14T09:00:00+00:00",
            "end": "2026-10-14T09:00:00+00:00",
            "role": "final_oos_after_freeze",
        },
        "search": {
            "trials_per_symbol_mechanism": args.trials_per_mechanism,
            "keep_per_cell": args.keep_per_cell,
            "workers": args.workers,
            "total_requested_trials": args.trials_per_mechanism * len(SYMBOLS) * len(MECHANISMS),
            "seeds": seeds,
        },
        "prefit_windows": {
            symbol: {
                name: [start.isoformat(), end.isoformat()]
                for name, (start, end) in prefit_windows(symbol).items()
            }
            for symbol in SYMBOLS
        },
        "cells": {symbol: cells[symbol] for symbol in SYMBOLS},
        "selected_best_per_mechanism": selected,
        "mechanism_prefit_ranking": mechanism_prefit_ranking,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(json.dumps({"output": str(OUTPUT), "sha256": digest}, indent=2), flush=True)


if __name__ == "__main__":
    main()
