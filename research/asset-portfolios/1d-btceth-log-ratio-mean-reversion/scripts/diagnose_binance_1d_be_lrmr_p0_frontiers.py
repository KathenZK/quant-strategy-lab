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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-log-ratio-mean-reversion"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = FAMILY_DIR / "scripts/search_binance_1d_be_lrmr_p0.py"


def load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_lrmr_frontier_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description="LRMR P0 deterministic frontier diagnostics.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    engine = load_engine()
    grid = pd.read_csv(ARTIFACT_DIR / f"binance_1d_be_lrmr_p0_search_{args.run_date}_grid.csv")
    selected = {
        "growth_frontier": grid.sort_values(["equity_multiple", "daily_close_mdd_pct"], ascending=[False, False]).iloc[0],
        "risk_frontier": grid.sort_values(["daily_close_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0],
    }
    data = engine.load_data_helper()
    hourly, funding, quality = data.load_frozen_data()
    daily = data.build_daily(hourly, funding)
    union = data.build_hourly_union(hourly, funding)
    keys = tuple(asdict(engine.configs()[0]))
    payload = {"generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1D-BTCETH-Log-Ratio-Mean-Reversion", "campaign": "P0 deterministic frontier/arm attribution", "evidence_role": "development diagnostic only; audit/prospective sealed", "data_quality": quality, "frontiers": {}}
    path_rows, trade_rows = [], []
    for frontier, row in selected.items():
        config = engine.Config(**{key: row[key] for key in keys})
        z = engine.ratio_z(daily, config.lookback)
        original = engine.pair_states(z, config)
        variants = {"combined": original, "long_btc_short_eth_only": original.copy(), "short_btc_long_eth_only": original.copy()}
        variants["long_btc_short_eth_only"][variants["long_btc_short_eth_only"] < 0] = 0
        variants["short_btc_long_eth_only"][variants["short_btc_long_eth_only"] > 0] = 0
        payload["frontiers"][frontier] = {"config": asdict(config), "daily_equity_multiple": float(row["equity_multiple"]), "daily_close_mdd_pct": float(row["daily_close_mdd_pct"]), "variants": {}}
        for variant, states in variants.items():
            result = engine.hourly_replay(data, union, daily, states, slippage=engine.BASE_SLIPPAGE, retain=True)
            metrics = {"equity_multiple": result.equity_multiple, "conservative_ordered_mdd_pct": result.max_drawdown_pct, "pairs": len(result.trades), "long_btc_short_eth_pairs": result.positive_pair_count, "short_btc_long_eth_pairs": result.negative_pair_count, "complete_year_positive_ratio": engine.complete_year_ratio(result.path), "rolling_365d_positive_ratio": engine.rolling_ratio(result.path), "max_pair_positive_log_share": engine.concentration(result.trades)}
            payload["frontiers"][frontier]["variants"][variant] = metrics
            if variant == "combined":
                path_rows.extend({"frontier": frontier, **item} for item in result.path)
                trade_rows.extend({"frontier": frontier, **item} for item in result.trades)
    stem = f"binance_1d_be_lrmr_p0_frontiers_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(engine.clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_path.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    print(json.dumps(engine.clean(payload["frontiers"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
