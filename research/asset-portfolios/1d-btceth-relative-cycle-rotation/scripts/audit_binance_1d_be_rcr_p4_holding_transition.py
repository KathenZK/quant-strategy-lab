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
ANCHORS = {"growth": (40, 40, 28, 0.0, 0.25, 3), "risk": (90, 60, 56, 1.0, 0.25, 2)}
FEATURES = ("FAST_OPPOSE5", "MARKET_OPPOSE5", "ROLE_VIOLATION20", "REL_EXTREME_RISE3", "GIVEBACK_ATR14", "ENTRY_LOSS_ATR14")


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p4_p0", P0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rank_auc(labels: pd.Series, scores: pd.Series) -> float:
    valid = labels.notna() & scores.notna()
    y, x = labels.loc[valid].astype(int), scores.loc[valid].astype(float)
    positives, negatives = int(y.sum()), int(len(y) - y.sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = x.rank(method="average")
    return float((ranks.loc[y.eq(1)].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def tercile(frame: pd.DataFrame, feature: str) -> dict[str, Any]:
    work = frame[[feature, "danger"]].dropna().sort_values(feature)
    if len(work) < 3:
        return {"n": len(work), "danger": int(work["danger"].sum()), "edge": None}
    bucket = pd.qcut(work[feature].rank(method="first"), 3, labels=False)
    low = float(work.loc[bucket.eq(0), "danger"].mean())
    high = float(work.loc[bucket.eq(2), "danger"].mean())
    return {"n": len(work), "danger": int(work["danger"].sum()), "low_rate": low, "high_rate": high, "edge": high - low}


def atr14(daily: pd.DataFrame, symbol: str) -> np.ndarray:
    high, low = daily[f"{symbol}_high"], daily[f"{symbol}_low"]
    previous = daily[f"{symbol}_close"].shift(1)
    tr = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=14).mean().to_numpy(float)


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P4 holding-transition attribution.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    daily = p0.build_daily(hourly, funding)
    union = p0.build_hourly_union(hourly, funding)
    horizons = sorted({5, 20, *(value for values in ANCHORS.values() for value in values[:2])})
    scores = {(horizon, vol, symbol): p0.normalized_momentum(daily[f"{symbol}_close"], horizon, vol) for horizon, vol, symbol in itertools.product(horizons, (28, 56), p0.ASSETS)}
    atr = {symbol: atr14(daily, symbol) for symbol in p0.ASSETS}
    start = int(daily["ts"].searchsorted(p0.COMMON_START))
    end = int(daily["ts"].searchsorted(p0.DEVELOPMENT_END))
    rows, parity = [], {}
    for anchor, values in ANCHORS.items():
        config = p0.Config(*values)
        states = p0.signal_for_config(config, scores)
        replay = p0.ordered_hourly_replay(union, daily, states, slippage=p0.BASE_SLIPPAGE, retain=True)
        parity[anchor] = {"equity_multiple": replay.equity_multiple, "ordered_mdd_pct": replay.max_drawdown_pct, "trades": len(replay.trades)}
        entry_index, favorable_close, episode = start, float("nan"), 0
        for index in range(start, end):
            state = int(states[index])
            prior = int(states[index - 1]) if index > start else 0
            if state != prior:
                entry_index, favorable_close = index, float("nan")
                if state:
                    episode += 1
            if not state:
                continue
            asset = p0.STATE_ASSET[state]
            side = 1 if state > 0 else -1
            if state != prior:
                favorable_close = float(daily.iloc[index][f"{asset}_close"])
                continue
            feature_index = index - 1
            close = float(daily.iloc[feature_index][f"{asset}_close"])
            if not np.isfinite(favorable_close):
                favorable_close = close
            else:
                favorable_close = max(favorable_close, close) if side > 0 else min(favorable_close, close)
            future_end = index
            while future_end < min(end, index + 3) and int(states[future_end]) == state:
                future_end += 1
            future = daily.iloc[index:future_end]
            if future.empty:
                continue
            open_price = float(daily.iloc[index][f"{asset}_open"])
            adverse_price = float(future[f"{asset}_{'low' if side > 0 else 'high'}"].min() if side > 0 else future[f"{asset}_high"].max())
            adverse_return = side * (adverse_price / open_price - 1.0)
            other = "ETHUSDT" if asset == "BTCUSDT" else "BTCUSDT"
            selected20, other20 = scores[(20, 28, asset)][feature_index], scores[(20, 28, other)][feature_index]
            btc5, eth5 = scores[(5, 28, "BTCUSDT")][feature_index], scores[(5, 28, "ETHUSDT")][feature_index]
            selected5 = scores[(5, 28, asset)][feature_index]
            relative = scores[(20, 28, "BTCUSDT")] - scores[(20, 28, "ETHUSDT")]
            atr_value = atr[asset][feature_index]
            entry_open = float(daily.iloc[entry_index][f"{asset}_open"])
            rows.append({
                "anchor": anchor, "asset": asset, "side": side, "episode": episode,
                "landmark_ts": daily.iloc[index]["ts"], "holding_age_days": index - entry_index,
                "adverse_3d_return": adverse_return, "danger": int(adverse_return <= -0.08),
                "FAST_OPPOSE5": -side * selected5,
                "MARKET_OPPOSE5": -side * (btc5 + eth5) / 2.0,
                "ROLE_VIOLATION20": -side * (selected20 - other20),
                "REL_EXTREME_RISE3": abs(relative[feature_index]) - abs(relative[feature_index - 3]),
                "GIVEBACK_ATR14": side * (favorable_close - close) / atr_value,
                "ENTRY_LOSS_ATR14": -side * (close - entry_open) / atr_value,
            })
    frame = pd.DataFrame(rows)
    results = []
    danger_episodes = frame.loc[frame["danger"].eq(1)].groupby("anchor")["episode"].nunique().to_dict()
    for feature in FEATURES:
        anchor_auc = {key: rank_auc(group["danger"], group[feature]) for key, group in frame.groupby("anchor")}
        asset_auc = {key: rank_auc(group["danger"], group[feature]) for key, group in frame.groupby("asset")}
        strata = {f"{a}|{s}": tercile(group, feature) for (a, s), group in frame.groupby(["anchor", "asset"])}
        passed = (
            all(value >= 0.60 for value in anchor_auc.values())
            and all(value >= 0.58 for value in asset_auc.values())
            and len(strata) == 4
            and all(value["n"] >= 60 and value["danger"] >= 8 and value["edge"] is not None and value["edge"] >= 0.10 for value in strata.values())
            and all(danger_episodes.get(anchor, 0) >= 8 for anchor in ANCHORS)
        )
        results.append({"feature": feature, "anchor_auc": anchor_auc, "asset_auc": asset_auc, "strata": strata, "pass": passed})
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P4 frozen holding-transition attribution",
        "status": "signal found; P5 contract required" if any(row["pass"] for row in results) else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development attribution only; no threshold search", "data_quality": quality, "parity": parity,
        "counts": {"landmarks": len(frame), "danger": int(frame["danger"].sum()), "danger_episodes": danger_episodes, "features": len(results), "pass": sum(row["pass"] for row in results)},
        "results": results, "audit_revealed": False, "prospective_revealed": False,
    }
    stem = f"binance_1d_be_rcr_p4_holding_transition_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_landmarks.csv", index=False)
    summary = [{"feature": row["feature"], **{f"auc_anchor_{k}": v for k, v in row["anchor_auc"].items()}, **{f"auc_asset_{k}": v for k, v in row["asset_auc"].items()}, "weakest_edge": min(v["edge"] for v in row["strata"].values()), "pass": row["pass"]} for row in results]
    pd.DataFrame(summary).to_csv(ARTIFACT_DIR / f"{stem}_summary.csv", index=False)
    print(json.dumps(p0.clean_json(payload["counts"]), ensure_ascii=False))
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
