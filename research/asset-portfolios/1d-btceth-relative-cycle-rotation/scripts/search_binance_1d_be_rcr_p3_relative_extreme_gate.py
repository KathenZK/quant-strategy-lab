from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_PATH = FAMILY_DIR / "scripts/search_binance_1d_be_rcr_p0.py"
ANCHORS = {"growth": (40, 40, 28, 0.0, 0.25, 3), "risk": (90, 60, 56, 1.0, 0.25, 2)}
THRESHOLDS = (1.0, 1.5, 2.0, 2.5, 3.0)


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p3_p0", P0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def gated_states(base: np.ndarray, relative_extreme: np.ndarray, threshold: float) -> np.ndarray:
    output = np.zeros(len(base), dtype=np.int8)
    current = 0
    for index, target_value in enumerate(base):
        target = int(target_value)
        if target == current:
            pass
        elif target == 0:
            current = 0
        elif index > 0 and np.isfinite(relative_extreme[index - 1]) and relative_extreme[index - 1] <= threshold:
            current = target
        else:
            current = 0
        output[index] = current
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P3 relative-extreme gate.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        actual = gated_states(np.array([0, 1, 1, 2, 2], dtype=np.int8), np.array([0.0, 0.0, 2.0, 0.5, 0.0]), 1.0)
        assert actual.tolist() == [0, 1, 1, 0, 2]
        print("self-test: PASS")
        return
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    daily = p0.build_daily(hourly, funding)
    union = p0.build_hourly_union(hourly, funding)
    horizons = sorted({20, *(value for values in ANCHORS.values() for value in values[:2])})
    scores = {
        (horizon, vol_h, symbol): p0.normalized_momentum(daily[f"{symbol}_close"], horizon, vol_h)
        for horizon, vol_h, symbol in itertools.product(horizons, (28, 56), p0.ASSETS)
    }
    extreme = np.abs(scores[(20, 28, "BTCUSDT")] - scores[(20, 28, "ETHUSDT")])
    rows = []
    retained: dict[tuple[str, float], Any] = {}
    controls = {}
    for anchor, values in ANCHORS.items():
        config = p0.Config(*values)
        base = p0.signal_for_config(config, scores)
        control = p0.ordered_hourly_replay(union, daily, base, slippage=p0.BASE_SLIPPAGE)
        controls[anchor] = {"equity_multiple": control.equity_multiple, "ordered_mdd_pct": control.max_drawdown_pct}
        for threshold in THRESHOLDS:
            states = gated_states(base, extreme, threshold)
            result = p0.ordered_hourly_replay(union, daily, states, slippage=p0.BASE_SLIPPAGE, retain=True)
            row = {
                "anchor": anchor,
                "threshold": threshold,
                "base_equity_multiple": result.equity_multiple,
                "base_ordered_mdd_pct": result.max_drawdown_pct,
                "trades": len(result.trades),
                "base_screen_pass": result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0,
                "all_gates_pass": False,
            }
            if row["base_screen_pass"]:
                stress = p0.ordered_hourly_replay(union, daily, states, slippage=p0.STRESS_SLIPPAGE)
                delayed_base = p0.signal_for_config(config, scores, extra_delay_days=1)
                delayed_states = gated_states(delayed_base, extreme, threshold)
                delayed = p0.ordered_hourly_replay(union, daily, delayed_states, slippage=p0.BASE_SLIPPAGE)
                base_log = math.log(result.equity_multiple)
                stress_retention = math.log(stress.equity_multiple) / base_log
                delay_retention = math.log(delayed.equity_multiple) / base_log
                total_hours = sum(result.holding_hours.values())
                gates = {
                    "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
                    "delay": delay_retention >= 0.70 and delayed.equity_multiple >= 8.0 and delayed.max_drawdown_pct >= -25.0,
                    "calendar": p0.complete_year_positive_ratio(result.path) >= 0.70,
                    "rolling": p0.rolling_positive_ratio(result.path) >= 0.70,
                    "participation": (
                        total_hours > 0
                        and all(result.holding_hours[symbol] / total_hours >= 0.10 for symbol in p0.ASSETS)
                        and all(sum(1 for trade in result.trades if trade["asset"] == symbol) >= 5 for symbol in p0.ASSETS)
                        and result.long_trades >= 5
                        and result.short_trades >= 5
                    ),
                    "concentration": p0.trade_concentration(result.trades) <= 0.35,
                }
                row.update({
                    "stress_equity_multiple": stress.equity_multiple,
                    "stress_ordered_mdd_pct": stress.max_drawdown_pct,
                    "stress_log_growth_retention": stress_retention,
                    "delay_equity_multiple": delayed.equity_multiple,
                    "delay_ordered_mdd_pct": delayed.max_drawdown_pct,
                    "delay_log_growth_retention": delay_retention,
                    **{f"gate_{key}": value for key, value in gates.items()},
                    "all_gates_pass": all(gates.values()),
                })
                retained[(anchor, threshold)] = result
            rows.append(row)
    frame = pd.DataFrame(rows)
    passing = frame.loc[frame["all_gates_pass"]].copy()
    if not passing.empty:
        passing = passing.sort_values(
            ["base_ordered_mdd_pct", "stress_log_growth_retention", "base_equity_multiple", "trades", "anchor", "threshold"],
            ascending=[False, False, False, True, True, True],
        )
    unique = passing.iloc[0].to_dict() if not passing.empty else None
    best_growth = frame.sort_values(["base_equity_multiple", "base_ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = frame.sort_values(["base_ordered_mdd_pct", "base_equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P3 frozen relative-extreme gate",
        "status": "development candidate; audit remains sealed" if unique else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective sealed",
        "data_quality": quality,
        "controls": controls,
        "counts": {"configs": len(frame), "base_screen_pass": int(frame["base_screen_pass"].sum()), "all_gates_pass": int(frame["all_gates_pass"].sum())},
        "best_growth": best_growth,
        "best_risk": best_risk,
        "unique_candidate": unique,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    stem = f"binance_1d_be_rcr_p3_relative_extreme_gate_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    if unique:
        result = retained[(unique["anchor"], float(unique["threshold"]))]
        pd.DataFrame(result.path).to_csv(ARTIFACT_DIR / f"{stem}_candidate_path.csv", index=False)
        pd.DataFrame(result.trades).to_csv(ARTIFACT_DIR / f"{stem}_candidate_trades.csv", index=False)
    print(json.dumps(p0.clean_json(payload["counts"]), ensure_ascii=False))
    print(json.dumps(p0.clean_json(best_growth), ensure_ascii=False))
    print(json.dumps(p0.clean_json(best_risk), ensure_ascii=False))
    print(json.dumps(p0.clean_json(unique), ensure_ascii=False))


if __name__ == "__main__":
    main()
