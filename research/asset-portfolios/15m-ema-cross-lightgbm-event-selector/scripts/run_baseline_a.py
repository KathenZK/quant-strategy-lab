"""Phase 1 for BIN-15M-EMAX-LGBM: baseline A, kill tests, bracket pre-registration.

Consumes events_dev.parquet. The bracket selection reads ONLY label
distributions (never returns), per the frozen contract. Performance of all
three candidates is reported for audit transparency after selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import emax_common as ec


SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}
KILL_MIN_EVENTS_PER_SIDE = 50_000
KILL_COST_ATR_LIMIT = 0.8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=ec.ARTIFACT_DIR / "events_dev.parquet")
    parser.add_argument(
        "--output", type=Path, default=ec.ARTIFACT_DIR / "baseline_a_report.json"
    )
    return parser.parse_args()


def label_distribution(events: pd.DataFrame, bracket: str) -> dict:
    counts = events[f"{bracket}_label"].value_counts().reindex([0, 1, 2], fill_value=0)
    total = int(counts.sum())
    shares = (counts / total).round(6)
    return {
        "events": total,
        "sl_first": float(shares[0]),
        "tp_first": float(shares[1]),
        "timeout": float(shares[2]),
        "min_class_share": float(shares.min()),
        "timeout_distance_to_third": float(abs(shares[2] - 1.0 / 3.0)),
    }


def select_bracket(distributions: dict[str, dict]) -> tuple[str, str]:
    """Frozen pre-registration rule: timeout share closest to 1/3 and <= 50%;
    min class share >= 15%; on conflict, timeout-share criterion wins."""
    admissible = {
        name: dist
        for name, dist in distributions.items()
        if dist["timeout"] <= 0.50 and dist["min_class_share"] >= 0.15
    }
    if admissible:
        chosen = min(admissible, key=lambda name: admissible[name]["timeout_distance_to_third"])
        return chosen, "timeout_closest_to_third_with_min_class"
    chosen = min(
        (n for n, d in distributions.items() if d["timeout"] <= 0.50),
        key=lambda name: distributions[name]["timeout_distance_to_third"],
        default=min(distributions, key=lambda name: distributions[name]["timeout"]),
    )
    return chosen, "timeout_criterion_only_min_class_unmet"


def performance(events: pd.DataFrame, bracket: str, *, stress: float = 1.0) -> dict:
    # stress applies to execution costs (fee + slippage) only; funding is a
    # market transfer, not an execution assumption
    net = (
        events[f"{bracket}_gross_atr"]
        - stress * events["cost_atr"]
        - events[f"{bracket}_funding_frac"] / events["atr_frac"]
    )
    return {
        "events": int(len(events)),
        "mean_net_atr": float(net.mean()),
        "median_net_atr": float(net.median()),
        "std_net_atr": float(net.std()),
        "share_positive": float((net > 0).mean()),
        "sum_net_atr": float(net.sum()),
        "mean_net_frac": float((net * events["atr_frac"]).mean()),
    }


def slice_performance(events: pd.DataFrame, bracket: str, anchor: pd.Timestamp) -> dict:
    out = {}
    for name, days in SLICES.items():
        start = anchor - pd.Timedelta(days=days)
        window = events.loc[events["entry_ts"] > start]
        out[name] = performance(window, bracket) if len(window) else {"events": 0}
    return out


def main() -> None:
    args = parse_args()
    events = pd.read_parquet(args.events)
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    anchor = events["entry_ts"].max()

    report: dict = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md",
        "events_file": str(args.events),
        "window": {"start": str(events["entry_ts"].min()), "end": str(anchor)},
        "note": (
            "development window only; recent slices anchored to development end "
            "because 2026-01..2026-06 is the locked OOS; slices are audit-only"
        ),
        "cost_model": "fee 0.001 + slip 4bps per fill, funding as-of actual, Binance USD-M",
    }

    # --- bracket pre-registration (labels only) ---
    distributions = {
        name: label_distribution(events, name) for name in ec.BRACKETS
    }
    per_side = {
        f"{name}_side_{side}": label_distribution(
            events.loc[events["side"] == side], name
        )
        for name in ec.BRACKETS
        for side in (1, -1)
    }
    chosen, rule = select_bracket(distributions)
    report["bracket_selection"] = {
        "rule": "timeout share closest to 1/3 and <=50%; min class >=15%; labels only",
        "distributions": distributions,
        "per_side": per_side,
        "chosen": chosen,
        "chosen_by": rule,
    }

    # --- kill tests ---
    pool = events.loc[events["in_trading_pool"]]
    long_events = int((events["side"] == 1).sum())
    short_events = int((events["side"] == -1).sum())
    cost_share_over_limit = float((pool["cost_atr"] > KILL_COST_ATR_LIMIT).mean())
    dispersion = {
        name: float(events[f"{name}_net_atr"].std()) for name in ec.BRACKETS
    }
    cluster = (
        events.assign(hour=events["entry_ts"].dt.floor("h"))
        .groupby(["hour", "side"])
        .size()
    )
    report["kill_tests"] = {
        "long_events": long_events,
        "short_events": short_events,
        "min_events_per_side_required": KILL_MIN_EVENTS_PER_SIDE,
        "events_gate_pass": min(long_events, short_events) >= KILL_MIN_EVENTS_PER_SIDE,
        "trading_pool_events": int(len(pool)),
        "trading_pool_cost_atr_p50": float(pool["cost_atr"].median()),
        "trading_pool_cost_atr_p90": float(pool["cost_atr"].quantile(0.9)),
        "trading_pool_share_cost_over_0p8_atr": cost_share_over_limit,
        "cost_gate_pass": cost_share_over_limit < 0.5,
        "net_atr_dispersion": dispersion,
        "dispersion_gate_pass": all(value > 0.5 for value in dispersion.values()),
        "cluster_same_hour_same_side_p99": float(cluster.quantile(0.99)),
        "cluster_same_hour_same_side_max": int(cluster.max()),
    }

    # --- baseline A performance (all brackets, all events; audit) ---
    for name in ec.BRACKETS:
        block = {
            "all": performance(events, name),
            "long": performance(events.loc[events["side"] == 1], name),
            "short": performance(events.loc[events["side"] == -1], name),
            "trading_pool": performance(pool, name),
            "trading_pool_stress_1p5x": performance(pool, name, stress=1.5),
            "by_year": {
                str(year): performance(group, name)
                for year, group in events.groupby(events["entry_ts"].dt.year)
            },
            "recent_slices_trading_pool": slice_performance(pool, name, anchor),
        }
        report[f"baseline_{name}"] = block

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report["bracket_selection"]["distributions"], indent=2))
    print("chosen bracket:", chosen, "|", rule)
    print(json.dumps(report["kill_tests"], indent=2, default=str))
    print(f"report -> {args.output}")


if __name__ == "__main__":
    main()
