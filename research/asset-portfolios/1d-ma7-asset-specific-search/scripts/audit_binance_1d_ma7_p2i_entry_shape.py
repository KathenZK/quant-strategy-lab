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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASELINE_PATH = (
    FAMILY_DIR / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
)
P2G_PATH = (
    FAMILY_DIR / "scripts/audit_binance_1d_ma7_p2g_entry_information.py"
)
ENTRY_PATH = (
    ARTIFACT_DIR
    / "binance_1d_ma7_p2g_entry_information_2026-08-12_entries.csv"
)
FEATURES = (
    "BODY_ATR",
    "BODY_SHARE",
    "CLV",
    "ER7",
    "RANGE_ATR",
    "ADVERSE_WICK_ATR",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P2-I entry-shape attribution on frozen MA7 entries."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def daily_context(daily: pd.DataFrame) -> dict[str, Any]:
    work = daily.copy()
    work["ts"] = pd.to_datetime(work["ts"], utc=True)
    work = work.sort_values("ts").drop_duplicates("ts", keep="last")
    close = work["close"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            work["high"].astype(float) - work["low"].astype(float),
            (work["high"].astype(float) - previous_close).abs(),
            (work["low"].astype(float) - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return {
        "frame": work.reset_index(drop=True),
        "timestamps": pd.DatetimeIndex(work["ts"]),
        "atr7": true_range.rolling(7, min_periods=7).mean().to_numpy(),
        "close": close.to_numpy(),
        "diff": close.diff().to_numpy(),
    }


def shape_features(
    entry_ts: pd.Timestamp,
    *,
    side: int,
    context: dict[str, Any],
) -> dict[str, float]:
    known_day = entry_ts.floor("D") - pd.Timedelta(days=1)
    timestamps = context["timestamps"]
    index = int(timestamps.searchsorted(known_day, side="left"))
    if index >= len(timestamps) or timestamps[index] != known_day:
        raise RuntimeError(f"missing last complete day {known_day}")
    row = context["frame"].iloc[index]
    open_price = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    atr = float(context["atr7"][index])
    candle_range = high - low
    if not np.isfinite(atr) or atr <= 0.0:
        body_atr = range_atr = adverse_wick = math.nan
    else:
        body_atr = side * (close - open_price) / atr
        range_atr = candle_range / atr
        adverse_wick = (
            (min(open_price, close) - low) / atr
            if side > 0
            else (high - max(open_price, close)) / atr
        )
    if candle_range > 0.0:
        body_share = side * (close - open_price) / candle_range
        clv = side * (2.0 * (close - low) / candle_range - 1.0)
    else:
        body_share = clv = math.nan
    er7 = math.nan
    if index >= 7:
        moves = context["diff"][index - 6 : index + 1]
        denominator = float(np.abs(moves).sum())
        if np.all(np.isfinite(moves)) and denominator > 0.0:
            er7 = side * (
                context["close"][index] - context["close"][index - 7]
            ) / denominator
    return {
        "BODY_ATR": body_atr,
        "BODY_SHARE": body_share,
        "CLV": clv,
        "ER7": er7,
        "RANGE_ATR": range_atr,
        "ADVERSE_WICK_ATR": adverse_wick,
    }


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    if args.self_test:
        daily = pd.DataFrame(
            {
                "ts": pd.date_range("2026-01-01", periods=10, tz="UTC"),
                "open": np.arange(10.0, 20.0),
                "high": np.arange(12.0, 22.0),
                "low": np.arange(9.0, 19.0),
                "close": np.arange(11.0, 21.0),
            }
        )
        context = daily_context(daily)
        result = shape_features(
            pd.Timestamp("2026-01-11T00:00:00Z"),
            side=1,
            context=context,
        )
        assert math.isclose(result["BODY_SHARE"], 1.0 / 3.0)
        assert math.isclose(result["CLV"], 1.0 / 3.0)
        print("self-test: PASS")
        return

    baseline = load_module(BASELINE_PATH, "binance_ma7_p2i_baseline")
    p2g = load_module(P2G_PATH, "binance_ma7_p2i_p2g")
    p2g.FEATURES = FEATURES
    contexts: dict[str, dict[str, Any]] = {}
    for symbol, slug in baseline.ASSETS.items():
        daily = pd.read_parquet(baseline.P0_DIR / f"{slug}_perp_1d.parquet")
        contexts[symbol] = daily_context(daily)
    entries = pd.read_csv(ENTRY_PATH)
    cache: dict[tuple[str, int, str], dict[str, float]] = {}
    feature_rows: list[dict[str, float]] = []
    for row in entries.itertuples(index=False):
        side = 1 if row.side == "long" else -1
        entry_ts = pd.Timestamp(row.entry_ts)
        key = (str(row.symbol), side, entry_ts.isoformat())
        if key not in cache:
            cache[key] = shape_features(
                entry_ts,
                side=side,
                context=contexts[str(row.symbol)],
            )
        feature_rows.append(cache[key])
    shape_frame = pd.DataFrame(feature_rows)
    augmented = pd.concat(
        [entries.reset_index(drop=True), shape_frame], axis=1
    )
    metrics = p2g.metric_rows(augmented)
    decision = p2g.decide_features(augmented, metrics)
    if "BODY_SHARE" in decision["passing_features_after_dedup"] and "CLV" in decision[
        "passing_features_after_dedup"
    ]:
        weaker = min(
            ("BODY_SHARE", "CLV"),
            key=lambda name: decision["features"][name]["weakest_auc_edge"],
        )
        decision["features"][weaker]["pass"] = False
        decision["features"][weaker]["deduplicated_as_correlated_weaker"] = True
        decision["passing_features_after_dedup"].remove(weaker)
        decision["selected_feature"] = (
            decision["passing_features_after_dedup"][0]
            if decision["passing_features_after_dedup"]
            else None
        )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-I entry-shape attribution",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "raw_entries": len(augmented),
        "unique_feature_keys": len(cache),
        "decision": decision,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2i_entry_shape_{args.run_date}"
    augmented.to_csv(ARTIFACT_DIR / f"{stem}_entries.csv", index=False)
    pd.DataFrame(
        [
            {key: value for key, value in row.items() if key != "quintiles"}
            for row in metrics
        ]
    ).to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    (ARTIFACT_DIR / f"{stem}_metrics.json").write_text(
        json.dumps(clean_json(metrics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
