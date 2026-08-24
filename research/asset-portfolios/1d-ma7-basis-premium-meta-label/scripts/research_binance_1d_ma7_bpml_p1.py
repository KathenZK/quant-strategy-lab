from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-basis-premium-meta-label"
FEATURE_DIR = ROOT / "data/cache/binance_1d_ma7_bpml_p0_unaccepted"
P0_ARTIFACT_DIR = FAMILY_DIR / "artifacts/p0_data_2026-08-10"
DEFAULT_OUTPUT_DIR = FAMILY_DIR / "artifacts/p1_development_2026-08-10"
EVENT_PATH = ROOT / (
    "research/asset-portfolios/1d-ma7-later-maturity-meta-label/"
    "artifacts/p1_development_2026-08-10/p0_p1_events.parquet"
)
EVENT_IDENTITY = (
    "f224974f99f65a0ee53545e4fca8870a65555c4dafc4a42c12bfb623ebc1a777"
)
ASSETS = ("BTC", "ETH", "BNB", "SOL", "TRX")
ASSET_SLUGS = {asset: f"{asset.lower()}usdt" for asset in ASSETS}
END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")
SEED = 20260810
EMBARGO_DAYS = 5
BOOTSTRAP_SAMPLES = 5_000
PERMUTATION_REPEATS = 20
C_GRID = (0.03, 0.10, 0.30, 1.00)
THRESHOLD_GRID = (0.50, 0.55, 0.60, 0.65, 0.70)
ROUTES = ("combined", "long_only", "short_only")
DATASETS = ("premium_index", "mark_price", "index_price")

PRICE_FEATURES = (
    "is_short",
    "maturity_age_days",
    "aligned_distance_atr",
    "aligned_slope_atr",
    "cross_aligned_distance_atr",
    "cross_aligned_slope_atr",
    "distance_change_atr",
    "slope_change_atr",
    "aligned_return_1_atr",
    "aligned_return_3_atr",
    "aligned_return_5_atr",
    "aligned_return_10_atr",
    "aligned_efficiency_5",
    "aligned_efficiency_7",
    "aligned_efficiency_14",
    "atr7_pct",
    "atr7_atr20",
    "aligned_body_atr",
    "range_atr",
    "rejection_wick_atr",
    "opposition_wick_atr",
    "aligned_close_location",
    "aligned_rsi6",
    "aligned_rsi6_delta_1",
    "directional_rsi_extreme_5",
    "counter_rsi_extreme_5",
    "volume_ratio_20",
    "quote_volume_ratio_20",
    "trade_count_ratio_20",
    "hourly_disp_6_atr",
    "hourly_disp_24_atr",
    "hourly_disp_72_atr",
    "hourly_direction_fraction_24",
    "hourly_direction_fraction_72",
    "hourly_signed_efficiency_24",
    "hourly_signed_efficiency_72",
    "hourly_directional_rv_balance_24",
    "hourly_aligned_close_location_24",
    "hourly_impulse_6_vs_18_atr",
    "aligned_funding_carry_24h",
    "aligned_funding_carry_72h",
    "aligned_market_return_1d",
    "aligned_market_return_3d",
    "market_median_atr_pct",
    "aligned_market_breadth",
    "relative_strength_1d",
    "relative_strength_3d",
)
LOCAL_BASIS_FEATURES = (
    "aligned_premium_close",
    "aligned_premium_mean_6h",
    "aligned_premium_mean_24h",
    "aligned_premium_mean_72h",
    "aligned_premium_change_24h",
    "aligned_premium_z14d",
    "premium_vol_24h",
    "premium_range_24h",
    "premium_crowded_fraction_24h",
    "aligned_mark_index_basis_close",
    "aligned_mark_index_basis_mean_24h",
    "aligned_mark_index_basis_mean_72h",
    "aligned_mark_index_basis_change_24h",
    "aligned_mark_index_basis_z14d",
    "mark_index_basis_vol_24h",
    "aligned_premium_minus_mark_basis_24h",
)
MARKET_BASIS_FEATURES = (
    "market_median_aligned_premium_24h",
    "market_median_aligned_mark_basis_24h",
    "market_premium_crowded_breadth",
    "market_mark_basis_crowded_breadth",
    "local_minus_market_aligned_premium_24h",
    "local_minus_market_aligned_mark_basis_24h",
)
BASIS_FEATURES = (*LOCAL_BASIS_FEATURES, *MARKET_BASIS_FEATURES)
FULL_FEATURES = (*PRICE_FEATURES, *BASIS_FEATURES)
BASIS_ONLY_FEATURES = ("is_short", "maturity_age_days", *BASIS_FEATURES)
ROUTE_FEATURES = {
    "price_plus_basis": FULL_FEATURES,
    "price_control": PRICE_FEATURES,
    "basis_only": BASIS_ONLY_FEATURES,
}


@dataclass(frozen=True)
class BasisCache:
    ts_ns: np.ndarray
    premium_open: np.ndarray
    premium_high: np.ndarray
    premium_low: np.ndarray
    premium_close: np.ndarray
    mark_index_basis: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build causal premium/mark-index basis features on frozen LMML "
            "events and run nested LOAO expanding-time development."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--capacity-only", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--max-workers", type=int, default=5)
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=BOOTSTRAP_SAMPLES,
    )
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def event_identity_sha256(events: pd.DataFrame) -> str:
    ordered = events.sort_values(["signal_ts", "asset", "root_id"]).reset_index(
        drop=True
    )
    digest = hashlib.sha256()
    for column in ("cross_ts", "signal_ts", "entry_ts", "exit_ts"):
        values = (
            pd.to_datetime(ordered[column], utc=True)
            .to_numpy(dtype="datetime64[ns]")
            .astype("int64")
        )
        digest.update(np.ascontiguousarray(values).tobytes())
    for column in (
        "event_id",
        "side",
        "cross_index",
        "maturity_index",
        "maturity_age_days",
        "bars_held",
        "label",
    ):
        digest.update(
            np.ascontiguousarray(
                ordered[column].to_numpy(dtype="int64")
            ).tobytes()
        )
    for column in (
        "z_4bps",
        "z_8bps",
        "z_funding_off",
        "z_lag1",
        *PRICE_FEATURES,
    ):
        digest.update(
            np.ascontiguousarray(
                ordered[column].to_numpy(dtype="float64")
            ).tobytes()
        )
    for column in ("root_id", "asset", "exit_reason"):
        digest.update("\0".join(ordered[column].astype(str)).encode("utf-8"))
    return digest.hexdigest()


def frame_identity_sha256(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values("event_id").reset_index(drop=True)
    digest = hashlib.sha256()
    for column in ("event_id", "side", "market_peer_count"):
        digest.update(
            np.ascontiguousarray(
                ordered[column].to_numpy(dtype="int64")
            ).tobytes()
        )
    for column in BASIS_FEATURES:
        digest.update(
            np.ascontiguousarray(
                ordered[column].to_numpy(dtype="float64")
            ).tobytes()
        )
    digest.update("\0".join(ordered["asset"].astype(str)).encode("utf-8"))
    return digest.hexdigest()


def verify_p0_artifacts() -> dict[str, Any]:
    manifest_path = P0_ARTIFACT_DIR / "manifest.json"
    quality_path = P0_ARTIFACT_DIR / "p0_data_quality.json"
    source_path = P0_ARTIFACT_DIR / "p0_source_manifest.json"
    for path in (manifest_path, quality_path, source_path):
        if not path.exists():
            raise RuntimeError(f"Missing P0 artifact: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if not quality.get("archive_identity_schema_pass"):
        raise RuntimeError("P0 source identity/schema did not pass")
    if source.get("archive_count", 0) <= 0:
        raise RuntimeError("P0 source manifest is empty")
    if any(
        int(payload.get(field, -1)) != 0
        for payload in (quality, source)
        for field in (
            "hype_rows_consumed",
            "hype_files_opened",
            "hype_requests_sent",
        )
        if field in payload
    ):
        raise RuntimeError("HYPE lock violation in P0 artifacts")
    for details in manifest["files"].values():
        relative = str(details["path"])
        path = (
            P0_ARTIFACT_DIR / relative
            if "/" not in relative
            else ROOT / relative
        )
        if not path.exists() or sha256_path(path) != details["sha256"]:
            raise RuntimeError(f"P0 manifest identity failure: {path}")
    return {
        "manifest_sha256": sha256_path(manifest_path),
        "quality_sha256": sha256_path(quality_path),
        "source_sha256": sha256_path(source_path),
        "archive_count": int(source["archive_count"]),
        "source_continuity_pass": bool(
            quality.get("source_continuity_pass")
        ),
        "event_level_admission_required": bool(
            quality.get("event_level_admission_required")
        ),
    }


def load_feature_frame(asset: str, dataset: str) -> pd.DataFrame:
    path = FEATURE_DIR / f"{ASSET_SLUGS[asset]}_{dataset}_1h.parquet"
    if not path.exists():
        raise RuntimeError(f"Missing accepted basis feature: {path}")
    frame = pd.read_parquet(path)
    required = {"ts", "asset", "dataset", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise RuntimeError(f"{path} missing required columns")
    if set(frame["asset"].astype(str)) != {asset}:
        raise RuntimeError(f"{path} asset identity mismatch")
    if set(frame["dataset"].astype(str)) != {dataset}:
        raise RuntimeError(f"{path} dataset identity mismatch")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    timestamps = pd.DatetimeIndex(frame["ts"])
    if (
        timestamps.duplicated().any()
        or not timestamps.is_monotonic_increasing
    ):
        raise RuntimeError(f"{path} timestamps are not unique/ordered")
    for column in ("open", "high", "low", "close"):
        values = frame[column].to_numpy(dtype="float64")
        if not np.isfinite(values).all():
            raise RuntimeError(f"{path} contains non-finite {column}")
    return frame


def load_basis_caches() -> dict[str, BasisCache]:
    caches: dict[str, BasisCache] = {}
    for asset in ASSETS:
        frames = {
            dataset: load_feature_frame(asset, dataset)
            for dataset in DATASETS
        }
        premium = frames["premium_index"][
            ["ts", "open", "high", "low", "close"]
        ].rename(
            columns={
                "open": "premium_open",
                "high": "premium_high",
                "low": "premium_low",
                "close": "premium_close",
            }
        )
        mark = frames["mark_price"][["ts", "close"]].rename(
            columns={"close": "mark_close"}
        )
        index = frames["index_price"][["ts", "close"]].rename(
            columns={"close": "index_close"}
        )
        merged = (
            premium.merge(mark, on="ts", how="inner", validate="one_to_one")
            .merge(index, on="ts", how="inner", validate="one_to_one")
            .sort_values("ts")
            .reset_index(drop=True)
        )
        mark_values = merged["mark_close"].to_numpy(dtype="float64")
        index_values = merged["index_close"].to_numpy(dtype="float64")
        basis = np.log(mark_values / index_values)
        if not np.isfinite(basis).all():
            raise RuntimeError(f"{asset} mark/index basis is non-finite")
        reference = pd.DatetimeIndex(merged["ts"])
        caches[asset] = BasisCache(
            ts_ns=reference.to_numpy(dtype="datetime64[ns]").astype("int64"),
            premium_open=merged["premium_open"].to_numpy(dtype="float64"),
            premium_high=merged["premium_high"].to_numpy(dtype="float64"),
            premium_low=merged["premium_low"].to_numpy(dtype="float64"),
            premium_close=merged["premium_close"].to_numpy(dtype="float64"),
            mark_index_basis=basis,
        )
    return caches


def safe_zscore(value: float, reference: np.ndarray) -> float | None:
    if len(reference) != 336 or not np.isfinite(reference).all():
        return None
    scale = float(np.std(reference, ddof=0))
    if not math.isfinite(scale) or scale <= 0.0:
        return None
    result = (float(value) - float(np.mean(reference))) / scale
    return float(result) if math.isfinite(result) else None


def local_basis_features(
    cache: BasisCache,
    *,
    entry_ts: pd.Timestamp,
    side: int,
) -> dict[str, float] | None:
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    entry = pd.Timestamp(entry_ts)
    if entry.tzinfo is None:
        entry = entry.tz_localize("UTC")
    else:
        entry = entry.tz_convert("UTC")
    end = int(np.searchsorted(cache.ts_ns, entry.value, side="left"))
    if end < 360:
        return None
    start = end - 360
    if (
        end > len(cache.ts_ns)
        or cache.ts_ns[end - 1] != entry.value - 3_600_000_000_000
        or np.any(np.diff(cache.ts_ns[start:end]) != 3_600_000_000_000)
    ):
        return None
    premium = cache.premium_close
    mark_basis = cache.mark_index_basis
    premium_6 = premium[end - 6 : end]
    premium_24 = premium[end - 24 : end]
    premium_previous_24 = premium[end - 48 : end - 24]
    premium_72 = premium[end - 72 : end]
    premium_reference = premium[end - 360 : end - 24]
    basis_24 = mark_basis[end - 24 : end]
    basis_previous_24 = mark_basis[end - 48 : end - 24]
    basis_72 = mark_basis[end - 72 : end]
    basis_reference = mark_basis[end - 360 : end - 24]
    arrays = (
        premium_6,
        premium_24,
        premium_previous_24,
        premium_72,
        premium_reference,
        basis_24,
        basis_previous_24,
        basis_72,
        basis_reference,
    )
    if any(not np.isfinite(values).all() for values in arrays):
        return None
    premium_mean_24 = float(np.mean(premium_24))
    basis_mean_24 = float(np.mean(basis_24))
    premium_z = safe_zscore(premium_mean_24, premium_reference)
    basis_z = safe_zscore(basis_mean_24, basis_reference)
    if premium_z is None or basis_z is None:
        return None
    result = {
        "aligned_premium_close": float(side * premium[end - 1]),
        "aligned_premium_mean_6h": float(side * np.mean(premium_6)),
        "aligned_premium_mean_24h": float(side * premium_mean_24),
        "aligned_premium_mean_72h": float(side * np.mean(premium_72)),
        "aligned_premium_change_24h": float(
            side * (premium_mean_24 - np.mean(premium_previous_24))
        ),
        "aligned_premium_z14d": float(side * premium_z),
        "premium_vol_24h": float(np.std(premium_24, ddof=0)),
        "premium_range_24h": float(
            np.max(cache.premium_high[end - 24 : end])
            - np.min(cache.premium_low[end - 24 : end])
        ),
        "premium_crowded_fraction_24h": float(
            np.mean(side * premium_24 > 0.0)
        ),
        "aligned_mark_index_basis_close": float(
            side * mark_basis[end - 1]
        ),
        "aligned_mark_index_basis_mean_24h": float(side * basis_mean_24),
        "aligned_mark_index_basis_mean_72h": float(
            side * np.mean(basis_72)
        ),
        "aligned_mark_index_basis_change_24h": float(
            side * (basis_mean_24 - np.mean(basis_previous_24))
        ),
        "aligned_mark_index_basis_z14d": float(side * basis_z),
        "mark_index_basis_vol_24h": float(np.std(basis_24, ddof=0)),
        "aligned_premium_minus_mark_basis_24h": float(
            side * (premium_mean_24 - basis_mean_24)
        ),
    }
    if not np.isfinite(np.asarray(list(result.values()), dtype="float64")).all():
        return None
    return result


def build_accepted_panel(
    events: pd.DataFrame,
    caches: dict[str, BasisCache],
) -> tuple[pd.DataFrame, dict[str, int]]:
    feature_cache: dict[tuple[str, int, int], dict[str, float] | None] = {}
    rejected: Counter[str] = Counter()
    records: list[dict[str, Any]] = []

    def cached_features(
        asset: str,
        entry_ts: pd.Timestamp,
        side: int,
    ) -> dict[str, float] | None:
        key = (asset, pd.Timestamp(entry_ts).value, side)
        if key not in feature_cache:
            feature_cache[key] = local_basis_features(
                caches[asset],
                entry_ts=pd.Timestamp(entry_ts),
                side=side,
            )
        return feature_cache[key]

    for row in events.sort_values("event_id").itertuples(index=False):
        asset = str(row.asset)
        side = int(row.side)
        entry_ts = pd.Timestamp(row.entry_ts)
        local = cached_features(asset, entry_ts, side)
        if local is None:
            rejected["local_window"] += 1
            continue
        peers = [
            features
            for peer in ASSETS
            if peer != asset
            if (features := cached_features(peer, entry_ts, side)) is not None
        ]
        if len(peers) < 3:
            rejected["market_peers"] += 1
            continue
        market_premium = float(
            np.median(
                [peer["aligned_premium_mean_24h"] for peer in peers]
            )
        )
        market_basis = float(
            np.median(
                [
                    peer["aligned_mark_index_basis_mean_24h"]
                    for peer in peers
                ]
            )
        )
        basis_features = {
            **local,
            "market_median_aligned_premium_24h": market_premium,
            "market_median_aligned_mark_basis_24h": market_basis,
            "market_premium_crowded_breadth": float(
                np.mean(
                    [
                        peer["aligned_premium_mean_24h"] > 0.0
                        for peer in peers
                    ]
                )
            ),
            "market_mark_basis_crowded_breadth": float(
                np.mean(
                    [
                        peer["aligned_mark_index_basis_mean_24h"] > 0.0
                        for peer in peers
                    ]
                )
            ),
            "local_minus_market_aligned_premium_24h": float(
                local["aligned_premium_mean_24h"] - market_premium
            ),
            "local_minus_market_aligned_mark_basis_24h": float(
                local["aligned_mark_index_basis_mean_24h"] - market_basis
            ),
        }
        record = row._asdict()
        record.update(basis_features)
        record["market_peer_count"] = len(peers)
        records.append(record)
    panel = pd.DataFrame.from_records(records)
    if panel.empty:
        return panel, dict(rejected)
    for column in (*PRICE_FEATURES, *BASIS_FEATURES):
        values = panel[column].to_numpy(dtype="float64")
        if not np.isfinite(values).all():
            raise RuntimeError(f"Accepted panel has non-finite {column}")
    if panel["event_id"].duplicated().any():
        raise RuntimeError("Accepted panel has duplicate event_id")
    return panel.sort_values(["signal_ts", "asset", "root_id"]).reset_index(
        drop=True
    ), dict(rejected)


def capacity_summary(
    events: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    event_identity: str,
    rejection_counts: dict[str, int],
    source_audit: dict[str, Any],
) -> dict[str, Any]:
    per_asset = {
        asset: int(panel["asset"].eq(asset).sum()) for asset in ASSETS
    }
    side_counts = {
        "long": int(panel["side"].gt(0).sum()),
        "short": int(panel["side"].lt(0).sum()),
    }
    checks = {
        "usable_events": len(panel) >= 1_300,
        "per_asset": all(count >= 200 for count in per_asset.values()),
        "side_capacity": min(side_counts.values()) >= 550,
        "usable_rate": len(panel) / len(events) >= 0.90,
        "exact_windows_and_market_peers": bool(
            not panel.empty and panel["market_peer_count"].ge(3).all()
        ),
        "event_identity": event_identity == EVENT_IDENTITY,
        "source_manifest_verified": bool(source_audit),
        "hype_lock": True,
    }
    return {
        "schema_version": "binance-1d-ma7-bpml-p0-v1",
        "generated_at_utc": datetime.now(UTC),
        "input_events": int(len(events)),
        "usable_events": int(len(panel)),
        "usable_rate": float(len(panel) / len(events)),
        "per_asset": per_asset,
        "side_counts": side_counts,
        "rejection_counts": rejection_counts,
        "event_identity_sha256": event_identity,
        "accepted_panel_identity_sha256": (
            frame_identity_sha256(panel) if not panel.empty else None
        ),
        "source_audit": source_audit,
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
        "checks": checks,
        "p0_capacity_pass": bool(all(checks.values())),
    }


def asset_balanced_weights(events: pd.DataFrame) -> np.ndarray:
    counts = events["asset"].value_counts()
    mapping = {
        asset: len(events) / (len(counts) * count)
        for asset, count in counts.items()
    }
    return events["asset"].map(mapping).to_numpy(dtype="float64")


def fit_model(
    events: pd.DataFrame,
    features: tuple[str, ...],
    c_value: float,
) -> Pipeline:
    if events["label"].nunique() < 2:
        raise RuntimeError("Training fold contains one label")
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=c_value,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=SEED,
                ),
            ),
        ]
    )
    model.fit(
        events[list(features)],
        events["label"].astype(int),
        model__sample_weight=asset_balanced_weights(events),
    )
    return model


def predict_probability(
    model: Pipeline,
    events: pd.DataFrame,
    features: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(
        model.predict_proba(events[list(features)])[:, 1],
        dtype="float64",
    )


def route_mask(frame: pd.DataFrame, route: str) -> pd.Series:
    if route == "combined":
        return pd.Series(True, index=frame.index)
    if route == "long_only":
        return frame["side"].gt(0)
    if route == "short_only":
        return frame["side"].lt(0)
    raise ValueError(route)


def return_metrics(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    ordered = (
        frame.loc[frame[column].notna()]
        .sort_values(["entry_ts", "asset", "root_id"])
        .reset_index(drop=True)
    )
    if ordered.empty:
        return {
            "events": 0,
            "mean": 0.0,
            "median": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "compound": 0.0,
            "event_sequence_mdd": 0.0,
        }
    returns = ordered[column].to_numpy(dtype="float64")
    factors = np.cumprod(1.0 + returns)
    running_max = np.maximum.accumulate(
        np.concatenate([[1.0], factors])
    )[1:]
    drawdown = factors / running_max - 1.0
    positive = float(returns[returns > 0.0].sum())
    negative = float(-returns[returns < 0.0].sum())
    return {
        "events": int(len(ordered)),
        "mean": float(np.mean(returns)),
        "median": float(np.median(returns)),
        "profit_factor": (
            float(positive / negative) if negative > 0.0 else math.inf
        ),
        "win_rate": float(np.mean(returns > 0.0)),
        "compound": float(factors[-1] - 1.0),
        "event_sequence_mdd": float(np.min(drawdown)),
    }


def time_blocks(
    events: pd.DataFrame,
    *,
    initial_fraction: float,
    blocks: int,
) -> list[tuple[int, pd.Timestamp, pd.Timestamp]]:
    dates = pd.DatetimeIndex(sorted(events["signal_ts"].drop_duplicates()))
    initial = int(math.floor(len(dates) * initial_fraction))
    if initial < 10 or len(dates) - initial < blocks:
        raise RuntimeError("Insufficient dates for expanding-time folds")
    result: list[tuple[int, pd.Timestamp, pd.Timestamp]] = []
    for fold, block in enumerate(np.array_split(dates[initial:], blocks), start=1):
        if not len(block):
            raise RuntimeError("Empty time block")
        result.append((fold, pd.Timestamp(block[0]), pd.Timestamp(block[-1])))
    return result


def split_for_block(
    events: pd.DataFrame,
    *,
    first_test: pd.Timestamp,
    last_test: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    purge_boundary = first_test - pd.Timedelta(days=EMBARGO_DAYS)
    train = events.loc[
        events["signal_ts"].lt(first_test)
        & events["exit_ts"].lt(purge_boundary)
    ].copy()
    test = events.loc[
        events["signal_ts"].ge(first_test)
        & events["signal_ts"].le(last_test)
    ].copy()
    return train, test


def select_inner(
    events: pd.DataFrame,
    features: tuple[str, ...],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    folds = time_blocks(events, initial_fraction=0.50, blocks=3)
    predictions_by_c: dict[float, pd.DataFrame] = {}
    for c_value in C_GRID:
        frames: list[pd.DataFrame] = []
        for fold, first_test, last_test in folds:
            train, test = split_for_block(
                events,
                first_test=first_test,
                last_test=last_test,
            )
            if train.empty or test.empty or train["label"].nunique() < 2:
                frames = []
                break
            model = fit_model(train, features, c_value)
            prediction = test.copy()
            prediction["inner_fold"] = fold
            prediction["probability"] = predict_probability(
                model,
                test,
                features,
            )
            frames.append(prediction)
        if frames:
            predictions_by_c[c_value] = pd.concat(frames, ignore_index=True)
    scores: list[dict[str, Any]] = []
    for c_value, predictions in predictions_by_c.items():
        for route in ROUTES:
            routed = predictions.loc[route_mask(predictions, route)].copy()
            for threshold in THRESHOLD_GRID:
                selected = routed.loc[
                    routed["probability"].ge(threshold)
                ].copy()
                fold_counts = {
                    fold: int(selected["inner_fold"].eq(fold).sum())
                    for fold in range(1, 4)
                }
                fold_metrics = {
                    fold: return_metrics(
                        selected.loc[selected["inner_fold"].eq(fold)],
                        "z_8bps",
                    )
                    for fold in range(1, 4)
                }
                overall = return_metrics(selected, "z_8bps")
                side_counts = {
                    "long": int(selected["side"].gt(0).sum()),
                    "short": int(selected["side"].lt(0).sum()),
                }
                direction_eligible = (
                    min(side_counts.values()) >= 15
                    if route == "combined"
                    else True
                )
                eligible = bool(
                    len(selected) >= 40
                    and all(count >= 8 for count in fold_counts.values())
                    and all(
                        float(metric["mean"]) > 0.0
                        for metric in fold_metrics.values()
                    )
                    and float(overall["profit_factor"]) >= 1.05
                    and direction_eligible
                )
                scores.append(
                    {
                        "C": c_value,
                        "threshold": threshold,
                        "route": route,
                        "eligible": eligible,
                        "selected_events": int(len(selected)),
                        "side_counts": side_counts,
                        "fold_counts": fold_counts,
                        "worst_fold_mean": (
                            min(
                                float(metric["mean"])
                                for metric in fold_metrics.values()
                            )
                            if eligible
                            else None
                        ),
                        "overall": overall,
                        "fold_metrics": fold_metrics,
                    }
                )
    eligible_scores = [score for score in scores if score["eligible"]]
    if not eligible_scores:
        return None, scores
    route_rank = {"combined": 2, "long_only": 1, "short_only": 0}
    choice = max(
        eligible_scores,
        key=lambda score: (
            float(score["worst_fold_mean"]),
            float(score["overall"]["mean"]),
            float(score["overall"]["profit_factor"]),
            float(score["threshold"]),
            -float(score["C"]),
            route_rank[str(score["route"])],
        ),
    )
    return {
        "C": float(choice["C"]),
        "threshold": float(choice["threshold"]),
        "route": str(choice["route"]),
    }, scores


def permutation_importance(
    *,
    model: Pipeline,
    test: pd.DataFrame,
    features: tuple[str, ...],
    choice: dict[str, Any],
    held_asset: str,
    outer_fold: int,
) -> dict[str, float]:
    if not set(BASIS_FEATURES).issubset(features):
        return {}
    route = str(choice["route"])
    threshold = float(choice["threshold"])
    base_probabilities = predict_probability(model, test, features)
    eligible = route_mask(test, route).to_numpy(dtype=bool)
    base_selected = eligible & (base_probabilities >= threshold)
    outcomes = test["z_8bps"].to_numpy(dtype="float64")
    base_utility = float(np.mean(np.where(base_selected, outcomes, 0.0)))
    importance: dict[str, float] = {}
    for feature_index, feature in enumerate(BASIS_FEATURES):
        seed_text = f"{SEED}:{held_asset}:{outer_fold}:{feature_index}"
        feature_seed = int(
            hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16],
            16,
        )
        rng = np.random.default_rng(feature_seed)
        utilities = np.empty(PERMUTATION_REPEATS, dtype="float64")
        original = test[feature].to_numpy(copy=True)
        for repeat in range(PERMUTATION_REPEATS):
            permuted = test.copy()
            permuted[feature] = original[rng.permutation(len(original))]
            probabilities = predict_probability(model, permuted, features)
            selected = eligible & (probabilities >= threshold)
            utilities[repeat] = np.mean(
                np.where(selected, outcomes, 0.0)
            )
        importance[feature] = float(base_utility - np.mean(utilities))
    return importance


def evaluate_outer_fold(
    *,
    events: pd.DataFrame,
    features: tuple[str, ...],
    route_name: str,
    held_asset: str,
    outer_fold: int,
    first_test: pd.Timestamp,
    last_test: pd.Timestamp,
    with_permutation: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    base_train, base_test = split_for_block(
        events,
        first_test=first_test,
        last_test=last_test,
    )
    train = base_train.loc[base_train["asset"].ne(held_asset)].copy()
    test = base_test.loc[base_test["asset"].eq(held_asset)].copy()
    if train.empty or test.empty or train["label"].nunique() < 2:
        raise RuntimeError(
            f"Invalid outer fold route={route_name} "
            f"asset={held_asset} fold={outer_fold}"
        )
    choice, inner_scores = select_inner(train, features)
    prediction = test.copy()
    prediction["held_asset"] = held_asset
    prediction["outer_fold"] = outer_fold
    prediction["model_route"] = route_name
    permutation: dict[str, float] = {}
    if choice is None:
        prediction["probability"] = np.nan
        prediction["selected_C"] = np.nan
        prediction["selected_threshold"] = np.nan
        prediction["selected_route"] = "NO_SELECTION"
        prediction["route_eligible"] = False
        prediction["selected"] = False
    else:
        model = fit_model(train, features, float(choice["C"]))
        prediction["probability"] = predict_probability(
            model,
            test,
            features,
        )
        prediction["selected_C"] = float(choice["C"])
        prediction["selected_threshold"] = float(choice["threshold"])
        prediction["selected_route"] = str(choice["route"])
        prediction["route_eligible"] = route_mask(
            prediction,
            str(choice["route"]),
        )
        prediction["selected"] = (
            prediction["route_eligible"]
            & prediction["probability"].ge(float(choice["threshold"]))
        )
        if with_permutation:
            permutation = permutation_importance(
                model=model,
                test=test,
                features=features,
                choice=choice,
                held_asset=held_asset,
                outer_fold=outer_fold,
            )
    report = {
        "model_route": route_name,
        "held_asset": held_asset,
        "outer_fold": outer_fold,
        "train_rows": int(len(train)),
        "train_assets": train["asset"].value_counts().to_dict(),
        "train_start": train["signal_ts"].min(),
        "train_end": train["signal_ts"].max(),
        "test_rows": int(len(test)),
        "test_start": test["signal_ts"].min(),
        "test_end": test["signal_ts"].max(),
        "choice": choice,
        "selected_rows": int(prediction["selected"].sum()),
        "permutation_importance": permutation,
        "inner_scores": inner_scores,
    }
    print(
        "OUTER_FOLD_COMPLETE "
        f"route={route_name} asset={held_asset} fold={outer_fold} "
        f"selected={report['selected_rows']} "
        f"choice={choice if choice is not None else 'NO_SELECTION'}"
    )
    return prediction, report


def run_outer_oof(
    events: pd.DataFrame,
    *,
    route_name: str,
    features: tuple[str, ...],
    max_workers: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    blocks = time_blocks(events, initial_fraction=0.40, blocks=4)
    tasks = [
        (asset, fold, first_test, last_test)
        for asset in ASSETS
        for fold, first_test, last_test in blocks
    ]
    results: list[tuple[pd.DataFrame, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                evaluate_outer_fold,
                events=events,
                features=features,
                route_name=route_name,
                held_asset=asset,
                outer_fold=fold,
                first_test=first_test,
                last_test=last_test,
                with_permutation=route_name == "price_plus_basis",
            )
            for asset, fold, first_test, last_test in tasks
        ]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(
        key=lambda item: (
            ASSETS.index(str(item[1]["held_asset"])),
            int(item[1]["outer_fold"]),
        )
    )
    oof = pd.concat([prediction for prediction, _ in results], ignore_index=True)
    reports = [report for _, report in results]
    if oof["event_id"].duplicated().any():
        raise RuntimeError(f"{route_name} OOF has duplicate event_id")
    return oof, reports


def cluster_bootstrap(
    selected: pd.DataFrame,
    *,
    samples: int,
    column: str = "z_8bps",
) -> dict[str, Any]:
    selected = selected.loc[selected[column].notna()].copy()
    if selected.empty:
        return {
            "samples": samples,
            "positive_probability": 0.0,
            "quantiles": {"2.5%": 0.0, "50%": 0.0, "97.5%": 0.0},
        }
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    selected["block_90d"] = (
        (pd.to_datetime(selected["entry_ts"], utc=True) - epoch)
        // pd.Timedelta(days=90)
    ).astype("int64")
    clusters = [
        group[column].to_numpy(dtype="float64")
        for _, group in selected.groupby(["asset", "block_90d"], sort=True)
    ]
    rng = np.random.default_rng(SEED)
    outcomes = np.empty(samples, dtype="float64")
    for index in range(samples):
        sampled = rng.integers(0, len(clusters), size=len(clusters))
        values = np.concatenate([clusters[item] for item in sampled])
        outcomes[index] = float(np.mean(values))
    return {
        "samples": samples,
        "clusters": len(clusters),
        "positive_probability": float(np.mean(outcomes > 0.0)),
        "quantiles": {
            "2.5%": float(np.quantile(outcomes, 0.025)),
            "50%": float(np.quantile(outcomes, 0.50)),
            "97.5%": float(np.quantile(outcomes, 0.975)),
        },
    }


def delta_bootstrap(
    full_oof: pd.DataFrame,
    control_oof: pd.DataFrame,
    *,
    samples: int,
) -> dict[str, Any]:
    full = full_oof[
        ["event_id", "asset", "entry_ts", "z_8bps", "selected"]
    ].copy()
    control = control_oof[["event_id", "selected"]].copy()
    merged = full.merge(
        control,
        on="event_id",
        how="inner",
        suffixes=("_full", "_control"),
        validate="one_to_one",
    )
    if len(merged) != len(full_oof) or len(merged) != len(control_oof):
        raise RuntimeError("Full/control OOF event universes differ")
    merged["full_utility"] = np.where(
        merged["selected_full"],
        merged["z_8bps"],
        0.0,
    )
    merged["control_utility"] = np.where(
        merged["selected_control"],
        merged["z_8bps"],
        0.0,
    )
    merged["delta"] = merged["full_utility"] - merged["control_utility"]
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    merged["block_90d"] = (
        (pd.to_datetime(merged["entry_ts"], utc=True) - epoch)
        // pd.Timedelta(days=90)
    ).astype("int64")
    clusters = [
        group["delta"].to_numpy(dtype="float64")
        for _, group in merged.groupby(["asset", "block_90d"], sort=True)
    ]
    rng = np.random.default_rng(SEED + 1)
    outcomes = np.empty(samples, dtype="float64")
    for index in range(samples):
        sampled = rng.integers(0, len(clusters), size=len(clusters))
        outcomes[index] = float(
            np.mean(np.concatenate([clusters[item] for item in sampled]))
        )
    return {
        "samples": samples,
        "events": int(len(merged)),
        "clusters": len(clusters),
        "mean_delta": float(merged["delta"].mean()),
        "full_mean_utility": float(merged["full_utility"].mean()),
        "control_mean_utility": float(merged["control_utility"].mean()),
        "positive_probability": float(np.mean(outcomes > 0.0)),
        "quantiles": {
            "2.5%": float(np.quantile(outcomes, 0.025)),
            "50%": float(np.quantile(outcomes, 0.50)),
            "97.5%": float(np.quantile(outcomes, 0.975)),
        },
    }


def importance_summary(
    reports: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for feature in BASIS_FEATURES:
        values = [
            float(report["permutation_importance"][feature])
            for report in reports
            if feature in report["permutation_importance"]
        ]
        result[feature] = {
            "folds": len(values),
            "median": float(np.median(values)) if values else None,
            "mean": float(np.mean(values)) if values else None,
            "positive_folds": int(np.sum(np.asarray(values) > 0.0)),
        }
    return result


def choice_frequency(reports: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for report in reports:
        choice = report["choice"]
        if choice is None:
            counts["NO_SELECTION"] += 1
        else:
            key = (
                f"C={float(choice['C']):.2f}|"
                f"threshold={float(choice['threshold']):.2f}|"
                f"route={choice['route']}"
            )
            counts[key] += 1
    return dict(sorted(counts.items()))


def threshold_sensitivity(oof: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    finite = oof["probability"].notna() & oof["route_eligible"]
    for delta in (-0.05, 0.0, 0.05):
        selected = oof.loc[
            finite
            & oof["probability"].ge(
                (oof["selected_threshold"] + delta).clip(0.0, 1.0)
            )
        ]
        result[f"{delta:+.2f}"] = return_metrics(selected, "z_8bps")
    return result


def recent_slices(oof: pd.DataFrame) -> dict[str, Any]:
    end = pd.to_datetime(oof["exit_ts"], utc=True).max()
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    selected = oof.loc[oof["selected"]].copy()
    return {
        name: return_metrics(
            selected.loc[
                pd.to_datetime(selected["entry_ts"], utc=True).ge(
                    end - window
                )
            ],
            "z_8bps",
        )
        for name, window in windows.items()
    }


def summarize_route(
    oof: pd.DataFrame,
    reports: list[dict[str, Any]],
    *,
    samples: int,
) -> dict[str, Any]:
    selected = oof.loc[oof["selected"]].copy()
    route_candidates = oof.loc[
        oof["probability"].notna() & oof["route_eligible"]
    ].copy()
    main = return_metrics(selected, "z_8bps")
    variants = {
        column: return_metrics(selected, column)
        for column in ("z_4bps", "z_funding_off", "z_lag1")
    }
    lag_executable_rate = (
        float(selected["z_lag1"].notna().mean()) if len(selected) else 0.0
    )
    per_asset: dict[str, Any] = {}
    positive_assets = 0
    positive_ranking_assets = 0
    dual_improved_assets = 0
    for asset in ASSETS:
        asset_oof = oof.loc[oof["asset"].eq(asset)]
        asset_selected = selected.loc[selected["asset"].eq(asset)]
        asset_candidates = route_candidates.loc[
            route_candidates["asset"].eq(asset)
        ]
        selected_metrics = return_metrics(asset_selected, "z_8bps")
        baseline_metrics = return_metrics(asset_oof, "z_8bps")
        spearman = float(
            asset_candidates["probability"].corr(
                asset_candidates["z_8bps"],
                method="spearman",
            )
        )
        if float(selected_metrics["mean"]) > 0.0:
            positive_assets += 1
        if math.isfinite(spearman) and spearman > 0.0:
            positive_ranking_assets += 1
        dual = bool(
            int(selected_metrics["events"]) >= 15
            and float(selected_metrics["compound"])
            > float(baseline_metrics["compound"])
            and float(selected_metrics["event_sequence_mdd"])
            > float(baseline_metrics["event_sequence_mdd"])
        )
        if dual:
            dual_improved_assets += 1
        per_asset[asset] = {
            "selected": selected_metrics,
            "all_matured_oof": baseline_metrics,
            "ranking_spearman": spearman,
            "dual_improvement": dual,
        }
    per_fold: dict[str, Any] = {}
    positive_folds = 0
    for held_asset in ASSETS:
        for fold in range(1, 5):
            key = f"{held_asset}-{fold}"
            metrics = return_metrics(
                selected.loc[
                    selected["held_asset"].eq(held_asset)
                    & selected["outer_fold"].eq(fold)
                ],
                "z_8bps",
            )
            if float(metrics["mean"]) > 0.0:
                positive_folds += 1
            per_fold[key] = metrics
    overall_spearman = float(
        route_candidates["probability"].corr(
            route_candidates["z_8bps"],
            method="spearman",
        )
    )
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    selected_blocks = (
        pd.DataFrame(
            {
                "asset": selected["asset"],
                "block": (
                    (
                        pd.to_datetime(selected["entry_ts"], utc=True) - epoch
                    )
                    // pd.Timedelta(days=90)
                ).astype("int64"),
            }
        )
        if len(selected)
        else pd.DataFrame(columns=["asset", "block"])
    )
    return {
        "selected_events": int(len(selected)),
        "side_counts": {
            "long": int(selected["side"].gt(0).sum()),
            "short": int(selected["side"].lt(0).sum()),
        },
        "selected_90d_blocks": int(len(selected_blocks.drop_duplicates())),
        "main": main,
        "variants": variants,
        "lag_executable_rate": lag_executable_rate,
        "per_asset": per_asset,
        "per_fold": per_fold,
        "positive_asset_count": positive_assets,
        "positive_ranking_asset_count": positive_ranking_assets,
        "positive_outer_fold_count": positive_folds,
        "dual_improved_asset_count": dual_improved_assets,
        "ranking_spearman": overall_spearman,
        "cluster_bootstrap": cluster_bootstrap(
            selected,
            samples=samples,
        ),
        "choice_frequency": choice_frequency(reports),
        "threshold_sensitivity": threshold_sensitivity(oof),
        "recent_slices": recent_slices(oof),
    }


def apply_development_gate(
    *,
    capacity: dict[str, Any],
    full_summary: dict[str, Any],
    delta: dict[str, Any],
    importance: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    side_counts = full_summary["side_counts"]
    combined_chosen = any(
        "route=combined" in key and count > 0
        for key, count in full_summary["choice_frequency"].items()
    )
    direction_coverage = (
        min(side_counts.values()) >= 30
        if combined_chosen
        else max(side_counts.values()) >= 30
    )
    positive_importance = [
        feature
        for feature, values in importance.items()
        if int(values["folds"]) >= 15
        and values["median"] is not None
        and float(values["median"]) > 0.0
    ]
    variants = full_summary["variants"]
    checks = {
        "p0_capacity": bool(capacity["p0_capacity_pass"]),
        "accepted_total_and_per_asset": bool(
            int(full_summary["selected_events"]) >= 100
            and all(
                int(full_summary["per_asset"][asset]["selected"]["events"])
                >= 15
                for asset in ASSETS
            )
        ),
        "direction_coverage": bool(direction_coverage),
        "time_block_coverage": bool(
            int(full_summary["selected_90d_blocks"]) >= 15
        ),
        "main_economics": bool(
            float(full_summary["main"]["mean"]) > 0.0
            and float(full_summary["main"]["profit_factor"]) >= 1.15
        ),
        "positive_assets": bool(
            int(full_summary["positive_asset_count"]) >= 4
        ),
        "positive_outer_folds": bool(
            int(full_summary["positive_outer_fold_count"]) >= 15
        ),
        "ranking": bool(
            math.isfinite(float(full_summary["ranking_spearman"]))
            and float(full_summary["ranking_spearman"]) > 0.03
            and int(full_summary["positive_ranking_asset_count"]) >= 4
        ),
        "cluster_bootstrap": bool(
            float(
                full_summary["cluster_bootstrap"]["positive_probability"]
            )
            >= 0.90
        ),
        "full_over_price_control": bool(
            float(delta["positive_probability"]) >= 0.90
        ),
        "basis_permutation_importance": len(positive_importance) >= 2,
        "stress_variants": bool(
            all(
                float(variants[column]["mean"]) > 0.0
                and float(variants[column]["profit_factor"]) >= 1.05
                for column in ("z_4bps", "z_funding_off", "z_lag1")
            )
            and float(full_summary["lag_executable_rate"]) >= 0.75
        ),
        "per_asset_dual_improvement": bool(
            int(full_summary["dual_improved_asset_count"]) >= 3
        ),
        "hype_lock": True,
    }
    return {
        "checks": checks,
        "positive_basis_importance_features": positive_importance,
        "development_gate_pass": bool(all(checks.values())),
    }


def final_choice(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    choices = [
        report["choice"] for report in reports if report["choice"] is not None
    ]
    if not choices:
        return None
    counts: Counter[tuple[float, float, str]] = Counter(
        (
            float(choice["C"]),
            float(choice["threshold"]),
            str(choice["route"]),
        )
        for choice in choices
    )
    route_rank = {"combined": 2, "long_only": 1, "short_only": 0}
    choice_tuple = max(
        counts,
        key=lambda item: (
            counts[item],
            item[1],
            -item[0],
            route_rank[item[2]],
        ),
    )
    return {
        "C": choice_tuple[0],
        "threshold": choice_tuple[1],
        "route": choice_tuple[2],
        "outer_fold_votes": counts[choice_tuple],
    }


def frozen_model_state(
    panel: pd.DataFrame,
    reports: list[dict[str, Any]],
    *,
    panel_identity: str,
) -> dict[str, Any]:
    choice = final_choice(reports)
    if choice is None:
        raise RuntimeError("Cannot freeze without an outer-fold choice")
    model = fit_model(panel, FULL_FEATURES, float(choice["C"]))
    scaler: StandardScaler = model.named_steps["scale"]
    estimator: LogisticRegression = model.named_steps["model"]
    return {
        "schema_version": "binance-1d-ma7-bpml-model-v1",
        "created_at_utc": datetime.now(UTC),
        "development_end_exclusive": END_EXCLUSIVE,
        "assets": list(ASSETS),
        "event_identity_sha256": EVENT_IDENTITY,
        "accepted_panel_identity_sha256": panel_identity,
        "features": list(FULL_FEATURES),
        "choice": choice,
        "train_rows": int(len(panel)),
        "positive_rate": float(panel["label"].mean()),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficient": estimator.coef_[0].tolist(),
        "intercept": float(estimator.intercept_[0]),
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }


def write_outputs(
    output_dir: Path,
    *,
    panel: pd.DataFrame,
    capacity: dict[str, Any],
    oof_by_route: dict[str, pd.DataFrame],
    report: dict[str, Any],
    summary: dict[str, Any],
    frozen: dict[str, Any] | None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "accepted_events": output_dir / "p0_accepted_events.parquet",
        "capacity": output_dir / "p0_capacity.json",
        "full_oof": output_dir / "p1_price_plus_basis_oof.parquet",
        "control_oof": output_dir / "p1_price_control_oof.parquet",
        "basis_oof": output_dir / "p1_basis_only_oof.parquet",
        "summary": output_dir / "p1_summary.json",
        "report": output_dir / "p1_report.json",
    }
    panel.to_parquet(paths["accepted_events"], index=False)
    oof_by_route["price_plus_basis"].to_parquet(
        paths["full_oof"],
        index=False,
    )
    oof_by_route["price_control"].to_parquet(
        paths["control_oof"],
        index=False,
    )
    oof_by_route["basis_only"].to_parquet(
        paths["basis_oof"],
        index=False,
    )
    write_json(paths["capacity"], capacity)
    write_json(paths["summary"], summary)
    write_json(paths["report"], report)
    if frozen is not None:
        paths["frozen_model"] = output_dir / "p1_frozen_model.json"
        write_json(paths["frozen_model"], frozen)
    files = {
        name: {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
        for name, path in paths.items()
    }
    manifest = {
        "schema_version": "binance-1d-ma7-bpml-p1-manifest-v1",
        "created_at_utc": datetime.now(UTC),
        "files": files,
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    checksum_path = output_dir / "manifest.sha256"
    checksum_path.write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    return {
        **{name: details["sha256"] for name, details in files.items()},
        "manifest": sha256_path(manifest_path),
    }


def run_self_test() -> None:
    events = pd.read_parquet(EVENT_PATH)
    identity = event_identity_sha256(events)
    if identity != EVENT_IDENTITY:
        raise AssertionError(f"Event identity changed: {identity}")
    timestamps = pd.date_range(
        "2023-01-01T00:00:00Z",
        periods=800,
        freq="1h",
    )
    phase = np.arange(800, dtype="float64")
    premium = 0.0001 * np.sin(phase / 24.0) + phase * 1e-8
    basis = 0.0002 * np.cos(phase / 48.0) + phase * 2e-8
    cache = BasisCache(
        ts_ns=timestamps.to_numpy(dtype="datetime64[ns]").astype("int64"),
        premium_open=premium.copy(),
        premium_high=premium + 0.00002,
        premium_low=premium - 0.00002,
        premium_close=premium.copy(),
        mark_index_basis=basis.copy(),
    )
    entry = timestamps[760]
    before = local_basis_features(cache, entry_ts=entry, side=1)
    if before is None or set(before) != set(LOCAL_BASIS_FEATURES):
        raise AssertionError("Synthetic causal feature build failed")
    changed = BasisCache(
        ts_ns=cache.ts_ns,
        premium_open=cache.premium_open,
        premium_high=cache.premium_high,
        premium_low=cache.premium_low,
        premium_close=np.where(
            np.arange(800) >= 760,
            cache.premium_close + 10.0,
            cache.premium_close,
        ),
        mark_index_basis=np.where(
            np.arange(800) >= 760,
            cache.mark_index_basis + 10.0,
            cache.mark_index_basis,
        ),
    )
    after = local_basis_features(changed, entry_ts=entry, side=1)
    if before != after:
        raise AssertionError("Feature builder consumed post-entry rows")
    if (
        len(PRICE_FEATURES) != 47
        or len(BASIS_FEATURES) != 22
        or len(FULL_FEATURES) != 69
    ):
        raise AssertionError("Frozen feature contract changed")
    if "HYPE" in ASSETS or any("HYPE" in slug.upper() for slug in ASSET_SLUGS.values()):
        raise AssertionError("HYPE lock changed")
    print("SELF_TEST_OK")


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    if args.max_workers < 1 or args.max_workers > 20:
        raise ValueError("--max-workers must be in [1, 20]")
    if args.bootstrap_samples < 100:
        raise ValueError("--bootstrap-samples must be >=100")
    source_audit = verify_p0_artifacts()
    events = pd.read_parquet(EVENT_PATH)
    for column in ("cross_ts", "signal_ts", "entry_ts", "exit_ts"):
        events[column] = pd.to_datetime(events[column], utc=True)
    if len(events) != 1_448:
        raise RuntimeError(f"Frozen event count changed: {len(events)}")
    if set(events["asset"].astype(str)) != set(ASSETS):
        raise RuntimeError("Frozen event universe changed")
    if events["signal_ts"].ge(END_EXCLUSIVE).any():
        raise RuntimeError("Frozen event cutoff changed")
    event_identity = event_identity_sha256(events)
    if event_identity != EVENT_IDENTITY:
        raise RuntimeError(f"Frozen event identity changed: {event_identity}")
    caches = load_basis_caches()
    panel, rejection_counts = build_accepted_panel(events, caches)
    capacity = capacity_summary(
        events,
        panel,
        event_identity=event_identity,
        rejection_counts=rejection_counts,
        source_audit=source_audit,
    )
    if not args.no_write:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        panel.to_parquet(
            args.output_dir / "p0_accepted_events.parquet",
            index=False,
        )
        write_json(args.output_dir / "p0_capacity.json", capacity)
    print(
        "P0_CAPACITY "
        + json.dumps(json_ready(capacity), ensure_ascii=False)
    )
    if args.capacity_only:
        return
    if not capacity["p0_capacity_pass"]:
        raise RuntimeError("P0 capacity failed; P1 is forbidden")
    oof_by_route: dict[str, pd.DataFrame] = {}
    reports_by_route: dict[str, list[dict[str, Any]]] = {}
    summaries_by_route: dict[str, dict[str, Any]] = {}
    for route_name, features in ROUTE_FEATURES.items():
        oof, reports = run_outer_oof(
            panel,
            route_name=route_name,
            features=features,
            max_workers=args.max_workers,
        )
        oof_by_route[route_name] = oof
        reports_by_route[route_name] = reports
        summaries_by_route[route_name] = summarize_route(
            oof,
            reports,
            samples=args.bootstrap_samples,
        )
    delta = delta_bootstrap(
        oof_by_route["price_plus_basis"],
        oof_by_route["price_control"],
        samples=args.bootstrap_samples,
    )
    importance = importance_summary(
        reports_by_route["price_plus_basis"]
    )
    gate = apply_development_gate(
        capacity=capacity,
        full_summary=summaries_by_route["price_plus_basis"],
        delta=delta,
        importance=importance,
    )
    summary = {
        "schema_version": "binance-1d-ma7-bpml-p1-summary-v1",
        "created_at_utc": datetime.now(UTC),
        "status": (
            "DEVELOPMENT_GATE_PASSED"
            if gate["development_gate_pass"]
            else "DEVELOPMENT_HARD_GATE_FAILED"
        ),
        "capacity": capacity,
        "routes": summaries_by_route,
        "full_vs_price_control": delta,
        "basis_permutation_importance": importance,
        "development_gate": gate,
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    report = {
        **summary,
        "contract": {
            "assets": list(ASSETS),
            "event_identity_sha256": EVENT_IDENTITY,
            "development_end_exclusive": END_EXCLUSIVE,
            "price_features": list(PRICE_FEATURES),
            "basis_features": list(BASIS_FEATURES),
            "full_features": list(FULL_FEATURES),
            "model_grid": {
                "C": list(C_GRID),
                "thresholds": list(THRESHOLD_GRID),
                "routes": list(ROUTES),
            },
            "permutation_repeats": PERMUTATION_REPEATS,
            "bootstrap_samples": args.bootstrap_samples,
        },
        "outer_fold_reports": reports_by_route,
    }
    frozen = (
        frozen_model_state(
            panel,
            reports_by_route["price_plus_basis"],
            panel_identity=str(
                capacity["accepted_panel_identity_sha256"]
            ),
        )
        if gate["development_gate_pass"]
        else None
    )
    hashes: dict[str, str] = {}
    if not args.no_write:
        hashes = write_outputs(
            args.output_dir,
            panel=panel,
            capacity=capacity,
            oof_by_route=oof_by_route,
            report=report,
            summary=summary,
            frozen=frozen,
        )
    print(
        json.dumps(
            json_ready(
                {
                    "status": summary["status"],
                    "development_gate": gate,
                    "artifact_sha256": hashes,
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
