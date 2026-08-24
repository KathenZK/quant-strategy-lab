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
FEATURES = ("ASSET_OPPOSE6", "ASSET_OPPOSE24", "MARKET_OPPOSE6", "ROLE_VIOLATION24", "VOL_SHOCK6_72", "REL_EXTREME_RISE6")


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p5_p0", P0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def auc(labels: pd.Series, scores: pd.Series) -> float:
    valid = labels.notna() & scores.notna()
    y, x = labels.loc[valid].astype(int), scores.loc[valid].astype(float)
    positives, negatives = int(y.sum()), int(len(y) - y.sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = x.rank(method="average")
    return float((ranks.loc[y.eq(1)].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def tercile(frame: pd.DataFrame, feature: str) -> dict[str, Any]:
    work = frame[[feature, "danger"]].dropna().sort_values(feature)
    bucket = pd.qcut(work[feature].rank(method="first"), 3, labels=False)
    low, high = float(work.loc[bucket.eq(0), "danger"].mean()), float(work.loc[bucket.eq(2), "danger"].mean())
    return {"n": len(work), "danger": int(work["danger"].sum()), "low_rate": low, "high_rate": high, "edge": high - low}


def z_momentum(close: pd.Series, horizon: int, vol: pd.Series) -> np.ndarray:
    log_close = np.log(close.astype(float))
    return ((log_close - log_close.shift(horizon)) / (vol * np.sqrt(horizon))).to_numpy(float)


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P5 hourly-hazard attribution.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    daily = p0.build_daily(hourly, funding)
    union = p0.build_hourly_union(hourly, funding)
    daily_horizons = sorted({value for values in ANCHORS.values() for value in values[:2]})
    daily_scores = {(h, v, s): p0.normalized_momentum(daily[f"{s}_close"], h, v) for h, v, s in itertools.product(daily_horizons, (28, 56), p0.ASSETS)}
    close = {symbol: union[f"{symbol}_close"].astype(float) for symbol in p0.ASSETS}
    log_returns = {symbol: np.log(close[symbol]).diff() for symbol in p0.ASSETS}
    rv72 = {symbol: log_returns[symbol].rolling(72, min_periods=72).std(ddof=1) for symbol in p0.ASSETS}
    rv6 = {symbol: log_returns[symbol].rolling(6, min_periods=6).std(ddof=1) for symbol in p0.ASSETS}
    z6 = {symbol: z_momentum(close[symbol], 6, rv72[symbol]) for symbol in p0.ASSETS}
    z24 = {symbol: z_momentum(close[symbol], 24, rv72[symbol]) for symbol in p0.ASSETS}
    day_index = {pd.Timestamp(ts): index for index, ts in enumerate(daily["ts"])}
    rows, parity = [], {}
    for anchor, values in ANCHORS.items():
        config = p0.Config(*values)
        daily_states = p0.signal_for_config(config, daily_scores)
        replay = p0.ordered_hourly_replay(union, daily, daily_states, slippage=p0.BASE_SLIPPAGE, retain=True)
        parity[anchor] = {"equity_multiple": replay.equity_multiple, "ordered_mdd_pct": replay.max_drawdown_pct, "trades": len(replay.trades)}
        states = np.array([daily_states[day_index[pd.Timestamp(ts).floor("1D")]] for ts in union["ts"]], dtype=np.int8)
        episode, age = 0, 0
        for index in range(1, len(union) - 24):
            state, prior = int(states[index]), int(states[index - 1])
            if state != prior:
                age = 0
                if state:
                    episode += 1
            elif state:
                age += 1
            if not state or age < 6 or pd.Timestamp(union.iloc[index]["ts"]).hour not in (6, 12, 18):
                continue
            feature_index = index - 1
            asset, side = p0.STATE_ASSET[state], 1 if state > 0 else -1
            other = "ETHUSDT" if asset == "BTCUSDT" else "BTCUSDT"
            future_end = index
            while future_end < min(len(union), index + 24) and int(states[future_end]) == state:
                future_end += 1
            future = union.iloc[index:future_end]
            open_price = float(union.iloc[index][f"{asset}_open"])
            adverse_price = float(future[f"{asset}_low"].min() if side > 0 else future[f"{asset}_high"].max())
            adverse = side * (adverse_price / open_price - 1.0)
            relative = z24["BTCUSDT"] - z24["ETHUSDT"]
            rows.append({
                "anchor": anchor, "asset": asset, "side": side, "episode": episode,
                "landmark_ts": union.iloc[index]["ts"], "holding_age_hours": age,
                "adverse_24h_return": adverse, "danger": int(adverse <= -0.08),
                "ASSET_OPPOSE6": -side * z6[asset][feature_index],
                "ASSET_OPPOSE24": -side * z24[asset][feature_index],
                "MARKET_OPPOSE6": -side * (z6["BTCUSDT"][feature_index] + z6["ETHUSDT"][feature_index]) / 2.0,
                "ROLE_VIOLATION24": -side * (z24[asset][feature_index] - z24[other][feature_index]),
                "VOL_SHOCK6_72": float(rv6[asset].iloc[feature_index] / rv72[asset].iloc[feature_index]),
                "REL_EXTREME_RISE6": abs(relative[feature_index]) - abs(relative[feature_index - 6]),
            })
    frame = pd.DataFrame(rows)
    danger_episodes = frame.loc[frame["danger"].eq(1)].groupby("anchor")["episode"].nunique().to_dict()
    results = []
    for feature in FEATURES:
        anchor_auc = {key: auc(group["danger"], group[feature]) for key, group in frame.groupby("anchor")}
        asset_auc = {key: auc(group["danger"], group[feature]) for key, group in frame.groupby("asset")}
        strata = {f"{a}|{s}": tercile(group, feature) for (a, s), group in frame.groupby(["anchor", "asset"])}
        passed = all(value >= 0.60 for value in anchor_auc.values()) and all(value >= 0.58 for value in asset_auc.values()) and len(strata) == 4 and all(value["n"] >= 200 and value["danger"] >= 8 and value["edge"] >= 0.08 for value in strata.values()) and all(danger_episodes.get(anchor, 0) >= 8 for anchor in ANCHORS)
        results.append({"feature": feature, "anchor_auc": anchor_auc, "asset_auc": asset_auc, "strata": strata, "pass": passed})
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation", "campaign": "P5 frozen hourly-hazard attribution",
        "status": "signal found; P6 contract required" if any(row["pass"] for row in results) else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development attribution only; no threshold search", "data_quality": quality, "parity": parity,
        "counts": {"landmarks": len(frame), "danger": int(frame["danger"].sum()), "danger_episodes": danger_episodes, "features": len(results), "pass": sum(row["pass"] for row in results)},
        "results": results, "audit_revealed": False, "prospective_revealed": False,
    }
    stem = f"binance_1d_be_rcr_p5_hourly_hazard_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_landmarks.csv", index=False)
    summary = [{"feature": row["feature"], **{f"auc_anchor_{k}": v for k, v in row["anchor_auc"].items()}, **{f"auc_asset_{k}": v for k, v in row["asset_auc"].items()}, "weakest_edge": min(v["edge"] for v in row["strata"].values()), "pass": row["pass"]} for row in results]
    pd.DataFrame(summary).to_csv(ARTIFACT_DIR / f"{stem}_summary.csv", index=False)
    print(json.dumps(p0.clean_json(payload["counts"]), ensure_ascii=False))
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
