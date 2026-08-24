from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
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
LANDMARK_PATH = ARTIFACT_DIR / "binance_1d_be_rcr_p5_hourly_hazard_2026-08-12_landmarks.csv"
LANDMARK_SHA256 = "1a5e509a7690e7fc6d7953f2a281d508be6c2d33a12dc4980a73011121566891"
FEATURES = ("POSITION_CROWD24", "POSITION_CROWD7Z", "MARKET_CROWD7Z", "RELATIVE_CROWD_ROLE7Z", "FUNDING_ACCEL24", "CROSS_CROWD_ABS7Z")


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p6_p0", P0_PATH)
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


def funding_features(index: pd.DatetimeIndex, funding: pd.DataFrame) -> pd.DataFrame:
    events = funding.copy()
    events["hour"] = events["ts"].dt.floor("1h")
    hourly_rate = events.groupby("hour")["funding_rate"].sum().reindex(index, fill_value=0.0)
    fund24 = hourly_rate.rolling(24, min_periods=24).sum()
    mean168 = fund24.rolling(168, min_periods=168).mean()
    std168 = fund24.rolling(168, min_periods=168).std(ddof=1)
    z24 = (fund24 - mean168) / std168.replace(0.0, np.nan)
    delta24 = fund24 - fund24.shift(24)
    delta_std = delta24.rolling(168, min_periods=168).std(ddof=1)
    accel = delta24 / delta_std.replace(0.0, np.nan)
    return pd.DataFrame({"fund24": fund24, "z24": z24, "accel24": accel}, index=index)


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P6 funding/crowding attribution.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    digest = hashlib.sha256(LANDMARK_PATH.read_bytes()).hexdigest()
    if digest != LANDMARK_SHA256:
        raise RuntimeError(f"P5 landmark drift: {digest}")
    frame = pd.read_csv(LANDMARK_PATH, parse_dates=["landmark_ts"])
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    union = p0.build_hourly_union(hourly, funding)
    index = pd.DatetimeIndex(union["ts"])
    features = {symbol: funding_features(index, funding[symbol]) for symbol in p0.ASSETS}
    rows = []
    for landmark in frame.itertuples(index=False):
        timestamp = pd.Timestamp(landmark.landmark_ts)
        asset, side = landmark.asset, int(landmark.side)
        other = "ETHUSDT" if asset == "BTCUSDT" else "BTCUSDT"
        selected, peer = features[asset].loc[timestamp], features[other].loc[timestamp]
        rows.append({
            **landmark._asdict(),
            "POSITION_CROWD24": side * float(selected.fund24),
            "POSITION_CROWD7Z": side * float(selected.z24),
            "MARKET_CROWD7Z": side * float((selected.z24 + peer.z24) / 2.0),
            "RELATIVE_CROWD_ROLE7Z": side * float(selected.z24 - peer.z24),
            "FUNDING_ACCEL24": side * float(selected.accel24),
            "CROSS_CROWD_ABS7Z": float(max(abs(selected.z24), abs(peer.z24))),
        })
    enriched = pd.DataFrame(rows)
    danger_episodes = enriched.loc[enriched["danger"].eq(1)].groupby("anchor")["episode"].nunique().to_dict()
    results = []
    for feature in FEATURES:
        anchor_auc = {key: auc(group["danger"], group[feature]) for key, group in enriched.groupby("anchor")}
        asset_auc = {key: auc(group["danger"], group[feature]) for key, group in enriched.groupby("asset")}
        strata = {f"{a}|{s}": tercile(group, feature) for (a, s), group in enriched.groupby(["anchor", "asset"])}
        passed = all(value >= 0.60 for value in anchor_auc.values()) and all(value >= 0.58 for value in asset_auc.values()) and len(strata) == 4 and all(value["n"] >= 200 and value["danger"] >= 8 and value["edge"] >= 0.08 for value in strata.values()) and all(danger_episodes.get(anchor, 0) >= 8 for anchor in ("growth", "risk"))
        results.append({"feature": feature, "anchor_auc": anchor_auc, "asset_auc": asset_auc, "strata": strata, "pass": passed})
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation", "campaign": "P6 frozen funding/crowding attribution",
        "status": "signal found; economic contract required" if any(row["pass"] for row in results) else "HARD-GATE-FAILED / research line closed / explore / not promoted / not live-ready",
        "evidence_role": "development attribution only; no threshold search", "source_landmark_sha256": digest, "data_quality": quality,
        "counts": {"landmarks": len(enriched), "danger": int(enriched["danger"].sum()), "danger_episodes": danger_episodes, "features": len(results), "pass": sum(row["pass"] for row in results)},
        "results": results, "audit_revealed": False, "prospective_revealed": False,
    }
    stem = f"binance_1d_be_rcr_p6_funding_crowding_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    enriched.to_csv(ARTIFACT_DIR / f"{stem}_landmarks.csv", index=False)
    summary = [{"feature": row["feature"], **{f"auc_anchor_{k}": v for k, v in row["anchor_auc"].items()}, **{f"auc_asset_{k}": v for k, v in row["asset_auc"].items()}, "weakest_edge": min(v["edge"] for v in row["strata"].values()), "pass": row["pass"]} for row in results]
    pd.DataFrame(summary).to_csv(ARTIFACT_DIR / f"{stem}_summary.csv", index=False)
    print(json.dumps(p0.clean_json(payload["counts"]), ensure_ascii=False))
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
