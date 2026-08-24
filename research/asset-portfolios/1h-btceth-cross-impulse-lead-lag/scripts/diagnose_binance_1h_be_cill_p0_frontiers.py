from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-btceth-cross-impulse-lead-lag"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = FAMILY_DIR / "scripts/search_binance_1h_be_cill_p0.py"


def load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1h_be_cill_diag_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def filter_signals(engine: Any, book: Any, mask: np.ndarray) -> Any:
    return engine.SignalBook(
        follower=np.where(mask, book.follower, 0).astype(np.int8),
        side=np.where(mask, book.side, 0).astype(np.int8),
        leader=np.where(mask, book.leader, 0).astype(np.int8),
        leader_return_abs=np.where(mask, book.leader_return_abs, np.nan),
        follower_vol=np.where(mask, book.follower_vol, np.nan),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="CILL P0 deterministic frontier attribution.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    engine = load_engine()
    grid = pd.read_csv(ARTIFACT_DIR / f"binance_1h_be_cill_p0_search_{args.run_date}_grid.csv")
    selected = {
        "growth_frontier": grid.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0],
        "risk_frontier": grid.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0],
    }
    data = engine.load_data_helper()
    hourly, funding, quality = data.load_frozen_data()
    market, full = engine.prepare_market(data, hourly, funding)
    keys = tuple(asdict(engine.configs()[0]))
    payload = {"generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1H-BTCETH-Cross-Impulse-Lead-Lag", "campaign": "P0 frontier/cost/arm attribution", "evidence_role": "development diagnostic only; audit/prospective sealed", "data_quality": quality, "frontiers": {}}
    path_rows, trade_rows = [], []
    for frontier, row in selected.items():
        config = engine.Config(**{key: row[key] for key in keys})
        book = engine.build_signal_book(full, market, config)
        variants = {
            "combined": book,
            "long_only": filter_signals(engine, book, book.side > 0),
            "short_only": filter_signals(engine, book, book.side < 0),
            "btc_follower_only": filter_signals(engine, book, book.follower == 1),
            "eth_follower_only": filter_signals(engine, book, book.follower == 2),
        }
        payload["frontiers"][frontier] = {"config": asdict(config), "variants": {}}
        for variant, signals in variants.items():
            result = engine.simulate(market, signals, config, slippage=engine.BASE_SLIPPAGE, retain=True)
            payload["frontiers"][frontier]["variants"][variant] = {"equity_multiple": result.equity_multiple, "ordered_mdd_pct": result.max_drawdown_pct, **result.counts, "complete_year_positive_ratio": engine.complete_year_ratio(result.path), "rolling_365d_positive_ratio": engine.rolling_ratio(result.path), "max_trade_positive_log_share": engine.concentration(result.trades)}
            if variant == "combined":
                path_rows.extend({"frontier": frontier, **item} for item in result.path)
                trade_rows.extend({"frontier": frontier, **item} for item in result.trades)
        original_fee = engine.FEE
        try:
            engine.FEE = 0.0
            gross_with_funding = engine.simulate(market, book, config, slippage=0.0)
            zero_market = engine.Market(market.ts, market.open, market.high, market.low, market.close, {symbol: np.zeros(len(market.ts)) for symbol in engine.SYMBOLS})
            gross_price_only = engine.simulate(zero_market, book, config, slippage=0.0)
        finally:
            engine.FEE = original_fee
        payload["frontiers"][frontier]["cost_attribution"] = {
            "net_equity": payload["frontiers"][frontier]["variants"]["combined"]["equity_multiple"],
            "gross_with_funding_equity": gross_with_funding.equity_multiple,
            "gross_price_only_equity": gross_price_only.equity_multiple,
        }
    stem = f"binance_1h_be_cill_p0_frontiers_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(engine.clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_path.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    print(json.dumps(engine.clean(payload["frontiers"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
