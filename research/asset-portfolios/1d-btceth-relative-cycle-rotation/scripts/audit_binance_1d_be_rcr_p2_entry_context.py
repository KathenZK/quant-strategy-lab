from __future__ import annotations

import argparse
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
FEATURES = (
    "FAST_OPPOSE5",
    "FAST_OPPOSE10",
    "MARKET_OPPOSE5",
    "RELATIVE_EXTREME20",
    "VOL_SHOCK7_28",
    "CROSS_DISAGREE5",
)


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p2_p0", P0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def auc(labels: pd.Series, scores: pd.Series) -> float:
    valid = labels.notna() & scores.notna()
    y = labels.loc[valid].astype(int)
    x = scores.loc[valid].astype(float)
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = x.rank(method="average")
    return float(
        (ranks.loc[y.eq(1)].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def tercile_edge(frame: pd.DataFrame, feature: str) -> dict[str, Any]:
    work = frame[[feature, "tail"]].dropna().sort_values(feature)
    if len(work) < 15:
        return {"n": len(work), "edge": None}
    bucket = pd.qcut(work[feature].rank(method="first"), 3, labels=False)
    low = float(work.loc[bucket.eq(0), "tail"].mean())
    high = float(work.loc[bucket.eq(2), "tail"].mean())
    return {"n": len(work), "low_tail_rate": low, "high_tail_rate": high, "edge": high - low}


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P2 entry-context attribution.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    daily = p0.build_daily(hourly, funding)
    union = p0.build_hourly_union(hourly, funding)
    horizons = sorted({5, 10, 20, *(value for values in ANCHORS.values() for value in values[:2])})
    scores = {
        (horizon, vol_h, symbol): p0.normalized_momentum(
            daily[f"{symbol}_close"], horizon, vol_h
        )
        for horizon, vol_h, symbol in itertools.product(horizons, (28, 56), p0.ASSETS)
    }
    log_returns = {
        symbol: np.log(daily[f"{symbol}_close"].astype(float)).diff()
        for symbol in p0.ASSETS
    }
    rv7 = {symbol: log_returns[symbol].rolling(7, min_periods=7).std(ddof=1) for symbol in p0.ASSETS}
    rv28 = {symbol: log_returns[symbol].rolling(28, min_periods=28).std(ddof=1) for symbol in p0.ASSETS}
    day_index = {pd.Timestamp(ts): index for index, ts in enumerate(daily["ts"])}
    rows = []
    parity = {}
    for anchor, values in ANCHORS.items():
        config = p0.Config(*values)
        states = p0.signal_for_config(config, scores)
        replay = p0.ordered_hourly_replay(
            union, daily, states, slippage=p0.BASE_SLIPPAGE, retain=True
        )
        parity[anchor] = {
            "equity_multiple": replay.equity_multiple,
            "ordered_mdd_pct": replay.max_drawdown_pct,
            "trades": len(replay.trades),
        }
        cutoff = float(pd.Series([trade["trade_log_growth"] for trade in replay.trades]).quantile(0.20))
        for trade in replay.trades:
            entry = pd.Timestamp(trade["entry_ts"])
            feature_index = day_index[entry] - 1
            asset = trade["asset"]
            side = int(trade["side"])
            btc5 = scores[(5, 28, "BTCUSDT")][feature_index]
            eth5 = scores[(5, 28, "ETHUSDT")][feature_index]
            selected5 = scores[(5, 28, asset)][feature_index]
            selected10 = scores[(10, 28, asset)][feature_index]
            relative20 = scores[(20, 28, "BTCUSDT")][feature_index] - scores[(20, 28, "ETHUSDT")][feature_index]
            rows.append(
                {
                    "anchor": anchor,
                    "entry_ts": entry,
                    "asset": asset,
                    "side": side,
                    "trade_log_growth": trade["trade_log_growth"],
                    "tail": int(trade["trade_log_growth"] <= cutoff),
                    "FAST_OPPOSE5": -side * selected5,
                    "FAST_OPPOSE10": -side * selected10,
                    "MARKET_OPPOSE5": -side * (btc5 + eth5) / 2.0,
                    "RELATIVE_EXTREME20": abs(relative20),
                    "VOL_SHOCK7_28": float(rv7[asset].iloc[feature_index] / rv28[asset].iloc[feature_index]),
                    "CROSS_DISAGREE5": float(np.sign(btc5) != np.sign(eth5)),
                }
            )
    frame = pd.DataFrame(rows)
    results = []
    for feature in FEATURES:
        anchor_auc = {anchor: auc(group["tail"], group[feature]) for anchor, group in frame.groupby("anchor")}
        asset_auc = {asset: auc(group["tail"], group[feature]) for asset, group in frame.groupby("asset")}
        strata = {
            f"{anchor}|{asset}": tercile_edge(group, feature)
            for (anchor, asset), group in frame.groupby(["anchor", "asset"])
        }
        passed = (
            all(value >= 0.62 for value in anchor_auc.values())
            and all(value >= 0.58 for value in asset_auc.values())
            and len(strata) == 4
            and all(value["n"] >= 15 and value["edge"] is not None and value["edge"] >= 0.08 for value in strata.values())
        )
        results.append({"feature": feature, "anchor_auc": anchor_auc, "asset_auc": asset_auc, "strata": strata, "pass": passed})
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P2 frozen entry-context attribution",
        "status": "signal found; P3 contract required" if any(row["pass"] for row in results) else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development diagnostic only; no threshold search",
        "data_quality": quality,
        "parity": parity,
        "counts": {"trades": len(frame), "features": len(results), "pass": sum(row["pass"] for row in results)},
        "results": results,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    stem = f"binance_1d_be_rcr_p2_entry_context_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    frame.to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    flat = []
    for row in results:
        flat.append(
            {
                "feature": row["feature"],
                **{f"auc_anchor_{key}": value for key, value in row["anchor_auc"].items()},
                **{f"auc_asset_{key}": value for key, value in row["asset_auc"].items()},
                "weakest_stratum_edge": min(value["edge"] for value in row["strata"].values()),
                "pass": row["pass"],
            }
        )
    pd.DataFrame(flat).to_csv(ARTIFACT_DIR / f"{stem}_summary.csv", index=False)
    print(json.dumps(p0.clean_json(payload["counts"]), ensure_ascii=False))
    print(pd.DataFrame(flat).to_string(index=False))


if __name__ == "__main__":
    main()
