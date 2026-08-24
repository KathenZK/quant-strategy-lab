from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = FAMILY_DIR / "scripts/search_binance_1d_be_cbct_p0.py"
CONTROL = {
    "entry_n": 20,
    "exit_n": 10,
    "breadth_ema": 50,
    "trail_atr": 5.0,
    "confirm_days": 2,
    "cooldown_days": 7,
    "max_hold_days": 120,
}


def load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_cbct_p1_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def protections(engine: Any) -> list[Any]:
    return [
        engine.ProfitProtection(activation, giveback, confirm)
        for activation in (1.0, 2.0, 3.0)
        for giveback in (0.20, 0.35, 0.50)
        for confirm in (1, 2)
    ]


def row(engine: Any, protection: Any | None, result: Any, control: Any) -> dict[str, Any]:
    log_retention = (
        math.log(result.equity_multiple) / math.log(control.equity_multiple)
        if result.equity_multiple > 0 and control.equity_multiple > 1
        else -math.inf
    )
    mdd_improvement = result.max_drawdown_pct - control.max_drawdown_pct
    concentration = engine.concentration(result.trades)
    capacity = result.counts["trades"] >= 20 and all(
        result.counts[key] >= 5 for key in ("long", "short", "BTCUSDT", "ETHUSDT")
    )
    soft_base = (
        result.equity_multiple >= 10.0
        and log_retention >= 0.85
        and result.max_drawdown_pct >= -35.0
        and mdd_improvement >= 10.0
        and capacity
        and concentration <= 0.35
    )
    return {
        "variant": "control" if protection is None else "profit_protection",
        "activation_atr": None if protection is None else protection.activation_atr,
        "giveback": None if protection is None else protection.giveback,
        "profit_confirm_days": None if protection is None else protection.confirm_days,
        "equity_multiple": result.equity_multiple,
        "ordered_mdd_pct": result.max_drawdown_pct,
        "log_growth_retention": log_retention,
        "mdd_improvement_pp": mdd_improvement,
        **result.counts,
        "complete_year_positive_ratio": engine.complete_year_ratio(result.path),
        "rolling_365d_positive_ratio": engine.rolling_ratio(result.path),
        "max_trade_positive_log_share": concentration,
        "capacity_pass": capacity,
        "soft_base_pass": soft_base,
        "stress_equity_multiple": None,
        "stress_ordered_mdd_pct": None,
        "delay_equity_multiple": None,
        "delay_ordered_mdd_pct": None,
        "stress_delay_pass": False,
        "soft_continue_pass": False,
        "hard_target_pass": result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0,
        "trade_path_sha256": result.trade_path_sha256,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frozen CBCT P1 profit-protection OAT.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = load_engine()
    grid = protections(engine)
    if args.self_test:
        assert len(grid) == 18 and len(set(grid)) == 18
        print("self-test: PASS")
        return
    data = engine.load_data_helper()
    hourly_source, funding, quality = data.load_frozen_data()
    daily, hourly, daily_frame = engine.prepare_markets(data, hourly_source, funding)
    config = engine.Config(**CONTROL)
    book = engine.build_entry_book(daily_frame, daily, config.entry_n, config.breadth_ema, config.confirm_days)
    channels = engine.exit_channels(daily_frame, config.exit_n)
    control = engine.simulate(
        data, daily, hourly, book, channels, config, slippage=engine.BASE_SLIPPAGE, retain=True
    )
    expected_equity, expected_mdd = 13.240379390327405, -48.002184752378
    if not math.isclose(control.equity_multiple, expected_equity, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"control equity drift: {control.equity_multiple}")
    if not math.isclose(control.max_drawdown_pct, expected_mdd, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"control MDD drift: {control.max_drawdown_pct}")
    results = [(None, control)]
    for protection in grid:
        result = engine.simulate(
            data,
            daily,
            hourly,
            book,
            channels,
            config,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
            profit_protection=protection,
        )
        results.append((protection, result))
    rows = [row(engine, protection, result, control) for protection, result in results]
    by_hash: dict[str, int] = {}
    for index, item in enumerate(rows):
        prior = by_hash.get(item["trade_path_sha256"])
        if prior is None or item["equity_multiple"] > rows[prior]["equity_multiple"]:
            by_hash[item["trade_path_sha256"]] = index
    for index in by_hash.values():
        item = rows[index]
        if item["variant"] != "profit_protection" or not item["soft_base_pass"]:
            continue
        protection, _ = results[index]
        stress = engine.simulate(
            data,
            daily,
            hourly,
            book,
            channels,
            config,
            slippage=engine.STRESS_SLIPPAGE,
            profit_protection=protection,
        )
        delayed = engine.simulate(
            data,
            daily,
            hourly,
            book,
            channels,
            config,
            slippage=engine.BASE_SLIPPAGE,
            delay_days=1,
            profit_protection=protection,
        )
        item.update(
            {
                "stress_equity_multiple": stress.equity_multiple,
                "stress_ordered_mdd_pct": stress.max_drawdown_pct,
                "delay_equity_multiple": delayed.equity_multiple,
                "delay_ordered_mdd_pct": delayed.max_drawdown_pct,
                "stress_delay_pass": stress.equity_multiple > 1.0 and delayed.equity_multiple > 1.0,
            }
        )
        item["soft_continue_pass"] = item["soft_base_pass"] and item["stress_delay_pass"]
    frame = pd.DataFrame(rows)
    protected = frame.loc[frame["variant"].eq("profit_protection")]
    best_growth = protected.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = protected.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    passing = protected.loc[protected["soft_continue_pass"]].sort_values(
        ["ordered_mdd_pct", "equity_multiple", "activation_atr", "giveback", "profit_confirm_days"],
        ascending=[False, False, True, True, True],
    )
    selected = passing.iloc[0].to_dict() if not passing.empty else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Cross-Breadth-Channel-Trend",
        "campaign": "P1 frozen profit-protection OAT",
        "status": "P1 soft-continue" if selected else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development diagnostic only; audit/prospective sealed",
        "data_quality": quality,
        "control": rows[0],
        "counts": {
            "evaluated_paths": len(frame),
            "profit_protection_configs": len(protected),
            "unique_paths": int(protected["trade_path_sha256"].nunique()),
            "soft_base_pass": int(protected["soft_base_pass"].sum()),
            "soft_continue_pass": int(protected["soft_continue_pass"].sum()),
            "hard_target_pass": int(protected["hard_target_pass"].sum()),
        },
        "best_growth": best_growth,
        "best_risk": best_risk,
        "selected": selected,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_cbct_p1_profit_protection_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(engine.clean(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    frame.to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    path_rows, trade_rows = [], []
    frontier_indices = {
        "control": 0,
        "growth_frontier": int(protected["equity_multiple"].idxmax()),
        "risk_frontier": int(protected["ordered_mdd_pct"].idxmax()),
    }
    if selected is not None:
        frontier_indices["soft_selected"] = int(passing.index[0])
    for frontier, index in frontier_indices.items():
        _, result = results[index]
        path_rows.extend({"frontier": frontier, **item} for item in result.path)
        trade_rows.extend({"frontier": frontier, **item} for item in result.trades)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_path.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    print(json.dumps(engine.clean(payload["counts"]), ensure_ascii=False))
    print(json.dumps(engine.clean(best_growth), ensure_ascii=False))
    print(json.dumps(engine.clean(best_risk), ensure_ascii=False))
    print(json.dumps(engine.clean(selected), ensure_ascii=False))


if __name__ == "__main__":
    main()
