from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SEARCH_PATH = FAMILY_DIR / "scripts/search_binance_1d_be_rcr_p0.py"


def load_search() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p0_search", SEARCH_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SEARCH_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic P0 frontier replay.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    search = load_search()
    grid_path = ARTIFACT_DIR / f"binance_1d_be_rcr_p0_search_{args.run_date}_grid.csv"
    grid = pd.read_csv(grid_path)
    growth = grid.sort_values(
        ["equity_multiple", "daily_close_mdd_pct"], ascending=[False, False]
    ).iloc[0]
    risk = grid.sort_values(
        ["daily_close_mdd_pct", "equity_multiple"], ascending=[False, False]
    ).iloc[0]
    selected = {"growth_frontier": growth, "risk_frontier": risk}
    hourly, funding, quality = search.load_frozen_data()
    daily = search.build_daily(hourly, funding)
    union = search.build_hourly_union(hourly, funding)
    configs = search.configs()
    horizons = sorted(
        {value for config in configs for value in (config.regime_h, config.relative_h)}
    )
    scores = {}
    for horizon in horizons:
        for vol_h in (14, 28, 56):
            for symbol in search.ASSETS:
                scores[(horizon, vol_h, symbol)] = search.normalized_momentum(
                    daily[f"{symbol}_close"], horizon, vol_h
                )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P0 deterministic frontier attribution",
        "evidence_role": "development diagnostic only; audit/prospective sealed",
        "data_quality": quality,
        "frontiers": {},
    }
    trade_rows = []
    path_rows = []
    keys = tuple(asdict(configs[0]))
    for name, row in selected.items():
        config = search.Config(**{key: row[key] for key in keys})
        states = search.signal_for_config(config, scores)
        replay = search.ordered_hourly_replay(
            union, daily, states, slippage=search.BASE_SLIPPAGE, retain=True
        )
        worst = sorted(replay.trades, key=lambda trade: trade["trade_log_growth"])[:5]
        payload["frontiers"][name] = {
            "config": asdict(config),
            "daily_equity_multiple": float(row["equity_multiple"]),
            "daily_close_mdd_pct": float(row["daily_close_mdd_pct"]),
            "ordered_equity_multiple": replay.equity_multiple,
            "ordered_mdd_pct": replay.max_drawdown_pct,
            "trades": len(replay.trades),
            "holding_hours": replay.holding_hours,
            "long_trades": replay.long_trades,
            "short_trades": replay.short_trades,
            "complete_year_positive_ratio": search.complete_year_positive_ratio(
                replay.path
            ),
            "rolling_365d_positive_ratio": search.rolling_positive_ratio(replay.path),
            "max_trade_positive_log_share": search.trade_concentration(replay.trades),
            "worst_five_trades": worst,
        }
        trade_rows.extend({"frontier": name, **trade} for trade in replay.trades)
        path_rows.extend({"frontier": name, **path} for path in replay.path)
    stem = f"binance_1d_be_rcr_p0_frontiers_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(search.clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_path.csv", index=False)
    print(json.dumps(search.clean_json(payload["frontiers"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
