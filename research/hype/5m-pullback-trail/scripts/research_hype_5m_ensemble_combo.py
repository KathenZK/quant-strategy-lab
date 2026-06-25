from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


RANKING_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_filter_refinement_ranking.csv")
TRADES_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_filter_refinement_top_trades.csv")
REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_ensemble_combo.json")
RANKING_OUT = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_ranking.csv")
LEGS_OUT = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_legs.csv")
TRADES_OUT = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_selected_trades.csv")

START_TS = pd.Timestamp("2025-06-01T00:00:00Z")
END_TS = pd.Timestamp("2026-06-01T00:00:00Z")
IS_END_TS = pd.Timestamp("2026-03-01T00:00:00Z")
TARGET_ANNUALIZED_MULTIPLE = 20.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20
LEVERAGE_GRID = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one-position HYPE 5m ensemble from refined filter legs.")
    parser.add_argument("--max-legs", type=int, default=16)
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--min-leg-win-rate", type=float, default=0.84)
    parser.add_argument("--min-leg-trades", type=int, default=50)
    parser.add_argument("--max-leg-dd", type=float, default=-0.205)
    return parser.parse_args()


def metric_from_rows(rows: list[dict[str, Any]], leverage: float, *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float | int]:
    selected = [row for row in rows if start <= row["entry_ts"] < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected:
        return {
            "trades": 0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "avg_trade": 0.0,
            "worst_trade": 0.0,
        }
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    rets: list[float] = []
    for row in sorted(selected, key=lambda item: item["entry_ts"]):
        ret = float(row["net_ret_1x"]) * leverage
        mae = float(row["mae_1x"]) * leverage
        trough = equity * max(0.001, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= 1.0 + ret
        if equity <= 0:
            equity = 0.001
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        rets.append(ret)
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    ret_array = np.array(rets, dtype=float)
    return {
        "trades": int(len(rets)),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((ret_array > 0).mean()),
        "avg_trade": float(ret_array.mean()),
        "worst_trade": float(ret_array.min()),
    }


def select_legs(rank: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    work = rank.copy()
    work["refined_name"] = work["base_name"] + "__" + work["filter_name"]
    pool = work.query(
        "full_win_rate >= @args.min_leg_win_rate and full_max_dd >= @args.max_leg_dd and full_trades >= @args.min_leg_trades"
    ).copy()
    pool = pool.sort_values(["full_annualized_multiple", "full_win_rate"], ascending=[False, False])
    legs: list[pd.Series] = []
    seen_base: set[str] = set()
    seen_refined: set[str] = set()
    for _, row in pool.iterrows():
        base = str(row["base_name"])
        refined = str(row["refined_name"])
        if base in seen_base or refined in seen_refined:
            continue
        seen_base.add(base)
        seen_refined.add(refined)
        legs.append(row)
        if len(legs) >= args.max_legs:
            break
    if not legs:
        raise RuntimeError("no eligible refined legs found")
    return pd.DataFrame(legs).reset_index(drop=True)


def choose_one_position(trades: pd.DataFrame, names: list[str]) -> list[dict[str, Any]]:
    sub = trades.loc[trades["refined_name"].isin(names)].copy().sort_values("entry_ts")
    selected: list[dict[str, Any]] = []
    last_exit = pd.Timestamp.min.tz_localize("UTC")
    used: set[tuple[pd.Timestamp, int]] = set()
    for _, row in sub.iterrows():
        key = (row["signal_ts"], int(row["side"]))
        if key in used:
            continue
        if row["entry_ts"] <= last_exit:
            continue
        used.add(key)
        selected.append(row.to_dict())
        last_exit = row["exit_ts"]
    return selected


def main() -> None:
    args = parse_args()
    rank = pd.read_csv(RANKING_PATH)
    trades = pd.read_csv(TRADES_PATH, parse_dates=["signal_ts", "entry_ts", "exit_ts"])
    legs = select_legs(rank, args)
    rows: list[dict[str, Any]] = []
    selected_by_n: dict[int, list[dict[str, Any]]] = {}
    leg_counts = [1, 2, 3, 5, 8, 12, min(16, len(legs))]
    leg_counts = sorted(set(count for count in leg_counts if count <= len(legs)))
    for count in leg_counts:
        names = legs.head(count)["refined_name"].tolist()
        selected = choose_one_position(trades, names)
        selected_by_n[count] = selected
        for leverage in LEVERAGE_GRID:
            full = metric_from_rows(selected, leverage, start=START_TS, end=END_TS)
            in_sample = metric_from_rows(selected, leverage, start=START_TS, end=IS_END_TS)
            oos = metric_from_rows(selected, leverage, start=IS_END_TS, end=END_TS)
            hit = (
                full["trades"] >= 20
                and full["annualized_multiple"] >= TARGET_ANNUALIZED_MULTIPLE
                and full["win_rate"] >= TARGET_WIN_RATE
                and full["max_dd"] >= TARGET_MAX_DD
            )
            rows.append(
                {
                    "legs": count,
                    "leverage": leverage,
                    "target_pass": bool(hit),
                    **{f"full_{key}": value for key, value in full.items()},
                    **{f"is_{key}": value for key, value in in_sample.items()},
                    **{f"oos_{key}": value for key, value in oos.items()},
                }
            )
    ranking = pd.DataFrame(rows).sort_values(
        ["target_pass", "full_annualized_multiple", "full_win_rate"],
        ascending=[False, False, False],
    )
    best = ranking.iloc[0]
    best_count = int(best["legs"])
    best_trades = pd.DataFrame(selected_by_n[best_count])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_OUT, index=False)
    legs.to_csv(LEGS_OUT, index=False)
    best_trades.to_csv(TRADES_OUT, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "symbol": "HYPE/USDT:USDT",
                    "exchange": "binance",
                    "market_type": "perp",
                    "timeframe": "5m",
                    "start": START_TS.isoformat(),
                    "end_exclusive": END_TS.isoformat(),
                    "is_end_exclusive": IS_END_TS.isoformat(),
                },
                "assumptions": {
                    "ensemble": "use ranked refined legs, one open position at a time; skip overlapping trades and duplicate signal_ts+side",
                    "source_ranking": str(RANKING_PATH),
                    "source_trades": str(TRADES_PATH),
                    "target_annualized_multiple": TARGET_ANNUALIZED_MULTIPLE,
                    "target_win_rate": TARGET_WIN_RATE,
                    "target_max_drawdown": TARGET_MAX_DD,
                },
                "best": best.to_dict(),
                "eligible_legs": legs.to_dict(orient="records"),
                "ranking": ranking.head(args.top).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_OUT}")
    print(f"legs={LEGS_OUT}")
    print(f"selected_trades={TRADES_OUT}")
    print(ranking.head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
