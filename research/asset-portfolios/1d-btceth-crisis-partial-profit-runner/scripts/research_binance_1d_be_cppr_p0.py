from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-crisis-partial-profit-runner"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
COST_PATH = ROOT / "research/asset-portfolios/1d-btceth-crisis-override-shadow-trend/scripts/research_binance_1d_be_cost_p0.py"
FRACTIONS = (0.0, 0.25, 0.50, 0.75)
EXPECTED_CONTROL = (23.13209027523642, -35.22258089123961)


def load_cost() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_cppr_cost", COST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {COST_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shadow_replay(
    cbct: Any,
    data: Any,
    daily: Any,
    hourly: Any,
    daily_frame: pd.DataFrame,
    *,
    fraction: float,
    slippage: float,
    delay_days: int,
) -> Any:
    config = cbct.Config(20, 10, 50, 5.0, 2, 7, 120)
    partial = cbct.PartialProtection(1.0, 0.20, 1, fraction) if fraction > 0 else None
    return cbct.simulate(
        data,
        daily,
        hourly,
        cbct.build_entry_book(daily_frame, daily, 20, 50, 2),
        cbct.exit_channels(daily_frame, 10),
        config,
        slippage=slippage,
        delay_days=delay_days,
        retain=True,
        profit_protection=cbct.ProfitProtection(1.0, 0.35, 2),
        partial_protection=partial,
    )


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P0 research for BIN-1D-BE-CPPR.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        assert FRACTIONS == (0.0, 0.25, 0.50, 0.75)
        print("self-test: PASS")
        return
    cost = load_cost()
    cbct = cost.load_cbct()
    data = cbct.load_data_helper()
    hourly_source, funding, quality = data.load_frozen_data()
    daily, hourly, daily_frame = cbct.prepare_markets(data, hourly_source, funding)
    crisis_config = cost.Config(200, 60, 3)
    modes = {
        "base": (cbct.BASE_SLIPPAGE, 0),
        "stress": (cbct.STRESS_SLIPPAGE, 0),
        "delay": (cbct.BASE_SLIPPAGE, 1),
    }
    results: dict[float, dict[str, Any]] = {}
    shadow_parity = {}
    neutral = np.zeros(len(daily.ts), dtype=np.int8)
    for fraction in FRACTIONS:
        results[fraction] = {}
        for mode, (slippage, delay) in modes.items():
            shadow = shadow_replay(
                cbct,
                data,
                daily,
                hourly,
                daily_frame,
                fraction=fraction,
                slippage=slippage,
                delay_days=delay,
            )
            neutral_result = cost.route_replay(
                cbct,
                data,
                daily,
                hourly,
                daily_frame,
                shadow,
                neutral,
                slippage=slippage,
                retain=False,
            )
            if not math.isclose(neutral_result.equity_multiple, shadow.equity_multiple, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(f"fraction {fraction} {mode}: shadow terminal router drift")
            if not math.isclose(neutral_result.ordered_mdd_pct, shadow.max_drawdown_pct, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(f"fraction {fraction} {mode}: shadow MDD router drift")
            shadow_parity[f"{fraction:.2f}_{mode}"] = {
                "equity_multiple": neutral_result.equity_multiple,
                "ordered_mdd_pct": neutral_result.ordered_mdd_pct,
                "partial_profit_events": neutral_result.counts["partial_profit_events"],
            }
            results[fraction][mode] = cost.route_replay(
                cbct,
                data,
                daily,
                hourly,
                daily_frame,
                shadow,
                cost.crisis_execution(daily_frame, crisis_config, delay),
                slippage=slippage,
                retain=mode == "base",
            )
    control = results[0.0]["base"]
    if not math.isclose(control.equity_multiple, EXPECTED_CONTROL[0], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"COST control terminal drift: {control.equity_multiple}")
    if not math.isclose(control.ordered_mdd_pct, EXPECTED_CONTROL[1], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"COST control MDD drift: {control.ordered_mdd_pct}")
    rows = []
    for fraction in FRACTIONS:
        base, stress, delay = results[fraction]["base"], results[fraction]["stress"], results[fraction]["delay"]
        base_log = math.log(base.equity_multiple) if base.equity_multiple > 0 else -math.inf
        stress_retention = math.log(stress.equity_multiple) / base_log if stress.equity_multiple > 0 and base_log > 0 else -math.inf
        delay_retention = math.log(delay.equity_multiple) / base_log if delay.equity_multiple > 0 and base_log > 0 else -math.inf
        hard_base = base.equity_multiple >= 20.0 and base.ordered_mdd_pct >= -20.0
        is_arm = fraction > 0
        gates = {
            "stress": stress.equity_multiple >= 16.0 and stress.ordered_mdd_pct >= -22.0,
            "delay": delay.equity_multiple >= 8.0 and delay.ordered_mdd_pct >= -25.0 and delay_retention >= 0.70,
            "calendar": cost.calendar_ratio(base.path) >= 0.70,
            "rolling": cost.rolling_ratio(base.path) >= 0.70,
            "capacity": len(base.trades) >= 20 and base.counts["partial_profit_events"] >= 3,
            "concentration": cost.concentration(base.trades) <= 0.30,
        }
        rows.append(
            {
                "partial_fraction": fraction,
                "variant": "partial_runner" if is_arm else "control",
                "equity_multiple": base.equity_multiple,
                "ordered_mdd_pct": base.ordered_mdd_pct,
                **base.counts,
                "trades": len(base.trades),
                "complete_year_positive_ratio": cost.calendar_ratio(base.path),
                "rolling_365d_positive_ratio": cost.rolling_ratio(base.path),
                "max_trade_positive_log_share": cost.concentration(base.trades),
                "hard_base_pass": hard_base,
                "stress_equity_multiple": stress.equity_multiple,
                "stress_ordered_mdd_pct": stress.ordered_mdd_pct,
                "stress_log_growth_retention": stress_retention,
                "delay_equity_multiple": delay.equity_multiple,
                "delay_ordered_mdd_pct": delay.ordered_mdd_pct,
                "delay_log_growth_retention": delay_retention,
                **{f"gate_{key}": value for key, value in gates.items()},
                "all_gates_pass": is_arm and hard_base and all(gates.values()),
            }
        )
    frame = pd.DataFrame(rows)
    arms = frame.loc[frame["variant"].eq("partial_runner")]
    best_growth = arms.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = arms.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    passing = arms.loc[arms["all_gates_pass"]].sort_values(
        ["ordered_mdd_pct", "stress_log_growth_retention", "equity_multiple", "trades", "partial_fraction"],
        ascending=[False, False, False, True, True],
    )
    selected = passing.iloc[0].to_dict() if not passing.empty else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Crisis-Partial-Profit-Runner",
        "campaign": "P0 frozen partial-runner search",
        "status": "development candidate; audit sealed" if selected else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read",
        "data_quality": quality,
        "control_parity": {"equity_multiple": control.equity_multiple, "ordered_mdd_pct": control.ordered_mdd_pct},
        "shadow_router_parity": shadow_parity,
        "counts": {
            "control": 1,
            "partial_fractions": 3,
            "hard_base_pass": int(arms["hard_base_pass"].sum()),
            "all_gates_pass": int(arms["all_gates_pass"].sum()),
        },
        "best_growth": best_growth,
        "best_risk": best_risk,
        "unique_candidate": selected,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_cppr_p0_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    path_rows, trade_rows, partial_rows, leg_rows = [], [], [], []
    for frontier, row in (("growth_frontier", best_growth), ("risk_frontier", best_risk)):
        fraction = float(row["partial_fraction"])
        result = results[fraction]["base"]
        path_rows.extend({"frontier": frontier, **item} for item in result.path.to_dict("records"))
        for trade_number, trade in enumerate(result.trades, start=1):
            flat_trade = {key: value for key, value in trade.items() if key != "partial_events"}
            trade_rows.append({"frontier": frontier, "trade_number": trade_number, **flat_trade})
            for event in trade.get("partial_events", []):
                partial_rows.append({"frontier": frontier, "trade_number": trade_number, **event})
        leg_rows.extend({"frontier": frontier, **item} for item in result.crisis_legs)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_paths.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    pd.DataFrame(partial_rows).to_csv(ARTIFACT_DIR / f"{stem}_partial_events.csv", index=False)
    pd.DataFrame(leg_rows).to_csv(ARTIFACT_DIR / f"{stem}_crisis_legs.csv", index=False)
    print(json.dumps(clean(payload["counts"]), ensure_ascii=False))
    print(json.dumps(clean(best_growth), ensure_ascii=False))
    print(json.dumps(clean(best_risk), ensure_ascii=False))
    print(json.dumps(clean(selected), ensure_ascii=False))


if __name__ == "__main__":
    main()
