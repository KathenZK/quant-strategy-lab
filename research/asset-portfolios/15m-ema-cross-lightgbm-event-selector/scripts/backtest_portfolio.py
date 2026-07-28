"""Phase 4 for BIN-15M-EMAX-LGBM: capital-constrained portfolio backtest on OOF scores.

Trading pool only. Hybrid gating (score threshold + per-window ranking) with
the frozen concurrency rules: one position per symbol, max 10 concurrent, max 3
new entries per hour per side, max 6 same-side positions, equal notional.
Threshold selected on folds 2..5, confirmed untouched on fold 6.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import emax_common as ec


MAX_CONCURRENT = 10
MAX_PER_HOUR_SIDE = 3
MAX_SIDE = 6
NOTIONAL_FRACTION = 0.10  # of initial capital per position
# absolute thresholds on the calibrated expected-net-ATR score
TAU_GRID = [0.0, 0.25, 0.50, 0.75, 1.00]
MIN_SELECT_TRADES = 150


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--oof", type=Path, default=ec.ARTIFACT_DIR / "model_v1" / "oof_scores.parquet"
    )
    parser.add_argument(
        "--baseline", type=Path, default=ec.ARTIFACT_DIR / "baseline_a_report.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ec.ARTIFACT_DIR / "model_v1" / "portfolio_report.json"
    )
    return parser.parse_args()


def simulate(
    events: pd.DataFrame,
    *,
    tau: float | None,
    net_column: str,
    exit_column: str,
    stress: float = 1.0,
) -> dict:
    """Event-driven simulation. tau=None means baseline A (no score gate,
    admission by arrival order); otherwise candidates are ranked by score."""
    frame = events.sort_values("entry_ts").reset_index(drop=True)
    if tau is not None:
        frame = frame.loc[frame["score"] > tau]
    open_positions: list[tuple[pd.Timestamp, str, int]] = []  # exit_ts, sym, side
    hour_counts: dict[tuple[pd.Timestamp, int], int] = {}
    pnl_records = []
    for ts, group in frame.groupby("entry_ts", sort=True):
        open_positions = [p for p in open_positions if p[0] > ts]
        if tau is not None:
            group = group.sort_values("score", ascending=False)
        for row in group.itertuples(index=False):
            if len(open_positions) >= MAX_CONCURRENT:
                break
            side_open = sum(1 for p in open_positions if p[2] == row.side)
            if side_open >= MAX_SIDE:
                continue
            if any(p[1] == row.sym_key for p in open_positions):
                continue
            hour_key = (ts.floor("h"), row.side)
            if hour_counts.get(hour_key, 0) >= MAX_PER_HOUR_SIDE:
                continue
            net_atr = getattr(row, net_column)
            if stress != 1.0:
                net_atr = net_atr - (stress - 1.0) * row.cost_atr
            net_frac = net_atr * row.atr_frac
            exit_ts = getattr(row, exit_column)
            open_positions.append((exit_ts, row.sym_key, row.side))
            hour_counts[hour_key] = hour_counts.get(hour_key, 0) + 1
            pnl_records.append(
                {
                    "entry_ts": ts,
                    "exit_ts": exit_ts,
                    "sym_key": row.sym_key,
                    "side": row.side,
                    "net_frac": net_frac,
                }
            )
    if not pnl_records:
        return {"trades": 0}
    trades = pd.DataFrame(pnl_records)
    trades["pnl"] = trades["net_frac"] * NOTIONAL_FRACTION  # in units of capital
    by_exit = trades.sort_values("exit_ts")
    equity = 1.0 + by_exit["pnl"].cumsum()
    peak = equity.cummax()
    drawdown = ((equity - peak) / peak).min()
    wins = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    losses = -trades.loc[trades["pnl"] < 0, "pnl"].sum()
    monthly = (
        by_exit.assign(month=by_exit["exit_ts"].dt.to_period("M").astype(str))
        .groupby("month")["pnl"]
        .sum()
    )
    return {
        "trades": int(len(trades)),
        "total_return": float(trades["pnl"].sum()),
        "max_drawdown": float(-drawdown),
        "profit_factor": float(wins / losses) if losses > 0 else float("inf"),
        "win_rate": float((trades["pnl"] > 0).mean()),
        "long_trades": int((trades["side"] == 1).sum()),
        "short_trades": int((trades["side"] == -1).sum()),
        "positive_months": int((monthly > 0).sum()),
        "total_months": int(len(monthly)),
        "monthly": {k: float(v) for k, v in monthly.items()},
    }


def main() -> None:
    args = parse_args()
    oof = pd.read_parquet(args.oof)
    oof["entry_ts"] = pd.to_datetime(oof["entry_ts"], utc=True)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    bracket = baseline["bracket_selection"]["chosen"]
    net_column = f"{bracket}_net_atr"
    exit_column = f"{bracket}_exit_ts"
    oof[exit_column] = pd.to_datetime(oof[exit_column], utc=True)

    pool = oof.loc[oof["in_trading_pool"]].copy()
    max_fold = int(pool["fold"].max())
    select = pool.loc[pool["fold"] < max_fold]
    confirm = pool.loc[pool["fold"] == max_fold]
    print(
        f"bracket={bracket} pool_events={len(pool)} "
        f"select_folds<= {max_fold - 1} ({len(select)}), confirm_fold={max_fold} ({len(confirm)})"
    )

    report: dict = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "bracket": bracket,
        "rules": {
            "max_concurrent": MAX_CONCURRENT,
            "max_per_hour_side": MAX_PER_HOUR_SIDE,
            "max_side": MAX_SIDE,
            "notional_fraction": NOTIONAL_FRACTION,
        },
        "selection": {},
    }

    candidates = []
    for tau in TAU_GRID:
        result = simulate(select, tau=tau, net_column=net_column, exit_column=exit_column)
        entry = {"tau": tau, **result}
        report["selection"][f"tau{tau}"] = entry
        if result.get("trades", 0) >= MIN_SELECT_TRADES:
            candidates.append(entry)
        print(f"select tau={tau:.2f} -> {result.get('trades', 0)} trades, "
              f"return={result.get('total_return', 0):.4f}, "
              f"pf={result.get('profit_factor', 0):.3f}, dd={result.get('max_drawdown', 0):.4f}")

    if not candidates:
        report["decision"] = "NO_ADMISSIBLE_THRESHOLD"
    else:
        best = max(candidates, key=lambda item: item["total_return"])
        tau = best["tau"]
        report["chosen"] = {"tau": tau}
        report["baseline_a_select"] = simulate(
            select, tau=None, net_column=net_column, exit_column=exit_column
        )
        report["confirm_fold"] = simulate(
            confirm, tau=tau, net_column=net_column, exit_column=exit_column
        )
        report["confirm_fold_stress_1p5x"] = simulate(
            confirm, tau=tau, net_column=net_column, exit_column=exit_column, stress=1.5
        )
        report["baseline_a_confirm"] = simulate(
            confirm, tau=None, net_column=net_column, exit_column=exit_column
        )
        gate = (
            report["confirm_fold"].get("total_return", 0.0) > 0.0
            and report["confirm_fold_stress_1p5x"].get("total_return", 0.0) > 0.0
            and report["confirm_fold"].get("total_return", 0.0)
            > report["baseline_a_confirm"].get("total_return", 0.0)
        )
        report["decision"] = "P4_GATE_PASS" if gate else "P4_GATE_FAIL"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    for key in ["chosen", "baseline_a_select", "confirm_fold", "confirm_fold_stress_1p5x", "baseline_a_confirm", "decision"]:
        if key in report:
            value = report[key]
            if isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != "monthly"}
            print(key, "->", json.dumps(value, default=str))
    print(f"report -> {args.output}")


if __name__ == "__main__":
    main()
