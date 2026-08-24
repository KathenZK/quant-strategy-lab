from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import importlib.util
import itertools
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_PATH = FAMILY_DIR / "scripts/search_binance_1d_be_rcr_p0.py"
ANCHORS = {
    "growth": (40, 40, 28, 0.0, 0.25, 3),
    "risk": (90, 60, 56, 1.0, 0.25, 2),
}
KEEP_STATES = {
    "combined": {1, -1, 2, -2},
    "long_only": {1, 2},
    "short_only": {-1, -2},
    "btc_only": {1, -1},
    "eth_only": {2, -2},
    "btc_long": {1},
    "btc_short": {-1},
    "eth_long": {2},
    "eth_short": {-2},
}


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_side_p0", P0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P0 side/asset attribution.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    daily = p0.build_daily(hourly, funding)
    union = p0.build_hourly_union(hourly, funding)
    horizons = sorted({value for values in ANCHORS.values() for value in values[:2]})
    scores = {
        (horizon, vol_h, symbol): p0.normalized_momentum(
            daily[f"{symbol}_close"], horizon, vol_h
        )
        for horizon, vol_h, symbol in itertools.product(
            horizons, (28, 56), p0.ASSETS
        )
    }
    rows = []
    for anchor, values in ANCHORS.items():
        config = p0.Config(*values)
        original = p0.signal_for_config(config, scores)
        for variant, keep in KEEP_STATES.items():
            states = original.copy()
            states[~np.isin(states, list(keep))] = 0
            result = p0.ordered_hourly_replay(
                union, daily, states, slippage=p0.BASE_SLIPPAGE, retain=True
            )
            rows.append(
                {
                    "anchor": anchor,
                    "variant": variant,
                    **asdict(config),
                    "equity_multiple": result.equity_multiple,
                    "ordered_mdd_pct": result.max_drawdown_pct,
                    "trades": len(result.trades),
                    "long_trades": result.long_trades,
                    "short_trades": result.short_trades,
                    "btc_holding_hours": result.holding_hours["BTCUSDT"],
                    "eth_holding_hours": result.holding_hours["ETHUSDT"],
                }
            )
    frame = pd.DataFrame(rows)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P1 side and asset attribution",
        "evidence_role": "development diagnostic only; no ranking permission",
        "data_quality": quality,
        "rows": frame.to_dict("records"),
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    stem = f"binance_1d_be_rcr_side_attribution_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    frame.to_csv(ARTIFACT_DIR / f"{stem}.csv", index=False)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
