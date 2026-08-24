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
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-taker-flow-meta-label"
CACHE_DIR = ROOT / "data/cache/binance_1d_ma7_tfml_p0_unaccepted"
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
ALPHA_GRID = (1.0, 10.0, 100.0, 300.0, 1000.0)
THRESHOLD_GRID = (0.0, 0.0005, 0.0010, 0.0015)
ROUTES = ("combined", "long_only", "short_only")
MIN_MARKET_PEERS = 3
FIVE_MINUTES_NS = 300_000_000_000
ROWS_1H = 12
ROWS_6H = 72
ROWS_24H = 288
ROWS_72H = 864
ROWS_15D = 4_320

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
LOCAL_FLOW_FEATURES = (
    "aligned_taker_imbalance_1h",
    "aligned_taker_imbalance_6h",
    "aligned_taker_imbalance_24h",
    "aligned_taker_imbalance_72h",
    "aligned_taker_imbalance_change_6h_24h",
    "aligned_taker_imbalance_change_24h_72h",
    "aligned_taker_imbalance_z14d",
    "aligned_flow_persistence_6h",
    "aligned_flow_persistence_24h",
    "taker_imbalance_std_24h",
    "taker_imbalance_range_24h",
    "max_quote_volume_share_24h",
    "max_trade_count_share_24h",
    "quote_volume_ratio_24h_14d",
    "trade_count_ratio_24h_14d",
    "aligned_flow_return_divergence_24h",
    "flow_price_correlation_24h",
)
MARKET_FLOW_FEATURES = (
    "market_median_aligned_taker_imbalance_6h",
    "market_median_aligned_taker_imbalance_24h",
    "market_median_aligned_taker_imbalance_72h",
    "market_aligned_flow_breadth_24h",
    "local_minus_market_aligned_taker_imbalance_24h",
    "market_median_aligned_flow_return_divergence_24h",
)
FLOW_FEATURES = (*LOCAL_FLOW_FEATURES, *MARKET_FLOW_FEATURES)
FULL_FEATURES = (*PRICE_FEATURES, *FLOW_FEATURES)
FLOW_ONLY_FEATURES = ("is_short", "maturity_age_days", *FLOW_FEATURES)
MODEL_FEATURES = {
    "price_plus_flow": FULL_FEATURES,
    "price_utility_control": PRICE_FEATURES,
    "flow_only": FLOW_ONLY_FEATURES,
}


@dataclass(frozen=True)
class FlowCache:
    ts_ns: np.ndarray
    open: np.ndarray
    close: np.ndarray
    quote_volume: np.ndarray
    trade_count: np.ndarray
    net_quote: np.ndarray
    per_bar_imbalance: np.ndarray
    active: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build native 5m taker-flow features on frozen LMML events and "
            "run continuous expected-utility nested LOAO development."
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
    for column in FLOW_FEATURES:
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
    if int(source.get("archive_count", 0)) != 316:
        raise RuntimeError("P0 archive count changed")
    for payload in (quality, source):
        for field in (
            "hype_rows_consumed",
            "hype_files_opened",
            "hype_requests_sent",
        ):
            if field in payload and int(payload[field]) != 0:
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
        "compressed_bytes": int(source["compressed_bytes"]),
        "source_continuity_pass": bool(
            quality.get("source_continuity_pass")
        ),
        "event_level_admission_required": bool(
            quality.get("event_level_admission_required")
        ),
    }


def load_flow_cache(asset: str) -> FlowCache:
    path = CACHE_DIR / f"{ASSET_SLUGS[asset]}_perp_5m_taker_flow.parquet"
    if not path.exists():
        raise RuntimeError(f"Missing flow cache: {path}")
    columns = (
        "ts",
        "asset",
        "open",
        "close",
        "quote_volume",
        "trade_count",
        "taker_buy_quote_volume",
    )
    frame = pd.read_parquet(path, columns=list(columns))
    if set(frame["asset"].astype(str)) != {asset}:
        raise RuntimeError(f"{path} asset identity mismatch")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    timestamps = pd.DatetimeIndex(frame["ts"])
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise RuntimeError(f"{path} timestamps are not unique/ordered")
    open_values = frame["open"].to_numpy(dtype="float64")
    close_values = frame["close"].to_numpy(dtype="float64")
    quote = frame["quote_volume"].to_numpy(dtype="float64")
    count = frame["trade_count"].to_numpy(dtype="float64")
    buy_quote = frame["taker_buy_quote_volume"].to_numpy(dtype="float64")
    arrays = (open_values, close_values, quote, count, buy_quote)
    if any(not np.isfinite(values).all() for values in arrays):
        raise RuntimeError(f"{path} contains non-finite fields")
    if (
        np.any(open_values <= 0.0)
        or np.any(close_values <= 0.0)
        or np.any(quote < 0.0)
        or np.any(count < 0.0)
        or np.any(buy_quote < 0.0)
        or np.any(buy_quote > quote + np.maximum(1e-8, quote * 1e-10))
    ):
        raise RuntimeError(f"{path} contains invalid fields")
    active = quote > 0.0
    net_quote = 2.0 * buy_quote - quote
    imbalance = np.full(len(frame), np.nan, dtype="float64")
    imbalance[active] = net_quote[active] / quote[active]
    return FlowCache(
        ts_ns=timestamps.to_numpy(dtype="datetime64[ns]").astype("int64"),
        open=open_values,
        close=close_values,
        quote_volume=quote,
        trade_count=count,
        net_quote=net_quote,
        per_bar_imbalance=imbalance,
        active=active,
    )


def aggregate_imbalance(
    cache: FlowCache,
    start: int,
    end: int,
) -> float | None:
    quote = float(np.sum(cache.quote_volume[start:end]))
    if not math.isfinite(quote) or quote <= 0.0:
        return None
    value = float(np.sum(cache.net_quote[start:end]) / quote)
    return value if math.isfinite(value) else None


def population_zscore(value: float, reference: np.ndarray) -> float | None:
    if not np.isfinite(reference).all() or len(reference) != 14:
        return None
    scale = float(np.std(reference, ddof=0))
    if not math.isfinite(scale) or scale <= 0.0:
        return None
    result = (float(value) - float(np.mean(reference))) / scale
    return float(result) if math.isfinite(result) else None


def local_flow_features(
    cache: FlowCache,
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
    if end < ROWS_15D:
        return None
    start = end - ROWS_15D
    if (
        end > len(cache.ts_ns)
        or cache.ts_ns[end - 1] != entry.value - FIVE_MINUTES_NS
        or np.any(np.diff(cache.ts_ns[start:end]) != FIVE_MINUTES_NS)
    ):
        return None
    window_starts = {
        "1h": end - ROWS_1H,
        "6h": end - ROWS_6H,
        "24h": end - ROWS_24H,
        "72h": end - ROWS_72H,
    }
    imbalances = {
        name: aggregate_imbalance(cache, window_start, end)
        for name, window_start in window_starts.items()
    }
    if any(value is None for value in imbalances.values()):
        return None
    daily_flow = np.empty(14, dtype="float64")
    daily_return = np.empty(14, dtype="float64")
    daily_quote = np.empty(14, dtype="float64")
    daily_count = np.empty(14, dtype="float64")
    reference_start = end - ROWS_15D
    for day in range(14):
        day_start = reference_start + day * ROWS_24H
        day_end = day_start + ROWS_24H
        flow = aggregate_imbalance(cache, day_start, day_end)
        if flow is None:
            return None
        daily_flow[day] = flow
        daily_return[day] = math.log(
            cache.close[day_end - 1] / cache.open[day_start]
        )
        daily_quote[day] = float(
            np.sum(cache.quote_volume[day_start:day_end])
        )
        daily_count[day] = float(
            np.sum(cache.trade_count[day_start:day_end])
        )
    flow_24 = float(imbalances["24h"])
    current_return = math.log(
        cache.close[end - 1] / cache.open[end - ROWS_24H]
    )
    flow_z = population_zscore(flow_24, daily_flow)
    return_z = population_zscore(current_return, daily_return)
    if flow_z is None or return_z is None:
        return None
    active_6 = cache.active[end - ROWS_6H : end]
    active_24 = cache.active[end - ROWS_24H : end]
    if (
        int(np.sum(active_6)) < math.ceil(ROWS_6H * 0.90)
        or int(np.sum(active_24)) < math.ceil(ROWS_24H * 0.90)
    ):
        return None
    imbalance_6_active = cache.per_bar_imbalance[
        end - ROWS_6H : end
    ][active_6]
    imbalance_24_active = cache.per_bar_imbalance[
        end - ROWS_24H : end
    ][active_24]
    current_quote = cache.quote_volume[end - ROWS_24H : end]
    current_count = cache.trade_count[end - ROWS_24H : end]
    quote_sum = float(np.sum(current_quote))
    count_sum = float(np.sum(current_count))
    quote_reference = float(np.median(daily_quote))
    count_reference = float(np.median(daily_count))
    if (
        quote_sum <= 0.0
        or count_sum <= 0.0
        or quote_reference <= 0.0
        or count_reference <= 0.0
    ):
        return None
    current_close = cache.close[end - ROWS_24H - 1 : end]
    bar_returns = np.diff(np.log(current_close))
    if len(bar_returns) != ROWS_24H:
        return None
    correlation_mask = active_24 & np.isfinite(bar_returns)
    if int(np.sum(correlation_mask)) < 260:
        return None
    correlation_flow = cache.per_bar_imbalance[
        end - ROWS_24H : end
    ][correlation_mask]
    correlation_return = bar_returns[correlation_mask]
    if (
        float(np.std(correlation_flow, ddof=0)) <= 0.0
        or float(np.std(correlation_return, ddof=0)) <= 0.0
    ):
        return None
    correlation = float(
        np.corrcoef(correlation_flow, correlation_return)[0, 1]
    )
    result = {
        "aligned_taker_imbalance_1h": float(side * imbalances["1h"]),
        "aligned_taker_imbalance_6h": float(side * imbalances["6h"]),
        "aligned_taker_imbalance_24h": float(side * flow_24),
        "aligned_taker_imbalance_72h": float(side * imbalances["72h"]),
        "aligned_taker_imbalance_change_6h_24h": float(
            side * (float(imbalances["6h"]) - flow_24)
        ),
        "aligned_taker_imbalance_change_24h_72h": float(
            side * (flow_24 - float(imbalances["72h"]))
        ),
        "aligned_taker_imbalance_z14d": float(side * flow_z),
        "aligned_flow_persistence_6h": float(
            np.mean(side * imbalance_6_active > 0.0)
        ),
        "aligned_flow_persistence_24h": float(
            np.mean(side * imbalance_24_active > 0.0)
        ),
        "taker_imbalance_std_24h": float(
            np.std(imbalance_24_active, ddof=0)
        ),
        "taker_imbalance_range_24h": float(
            np.max(imbalance_24_active) - np.min(imbalance_24_active)
        ),
        "max_quote_volume_share_24h": float(
            np.max(current_quote) / quote_sum
        ),
        "max_trade_count_share_24h": float(
            np.max(current_count) / count_sum
        ),
        "quote_volume_ratio_24h_14d": float(
            quote_sum / quote_reference
        ),
        "trade_count_ratio_24h_14d": float(
            count_sum / count_reference
        ),
        "aligned_flow_return_divergence_24h": float(
            side * (flow_z - return_z)
        ),
        "flow_price_correlation_24h": correlation,
    }
    if not np.isfinite(np.asarray(list(result.values()), dtype="float64")).all():
        return None
    return result


def build_accepted_panel(
    events: pd.DataFrame,
    caches: dict[str, FlowCache],
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
            feature_cache[key] = local_flow_features(
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
        market_6h = float(
            np.median(
                [
                    peer["aligned_taker_imbalance_6h"]
                    for peer in peers
                ]
            )
        )
        market_24h = float(
            np.median(
                [
                    peer["aligned_taker_imbalance_24h"]
                    for peer in peers
                ]
            )
        )
        market_72h = float(
            np.median(
                [
                    peer["aligned_taker_imbalance_72h"]
                    for peer in peers
                ]
            )
        )
        flow_features = {
            **local,
            "market_median_aligned_taker_imbalance_6h": market_6h,
            "market_median_aligned_taker_imbalance_24h": market_24h,
            "market_median_aligned_taker_imbalance_72h": market_72h,
            "market_aligned_flow_breadth_24h": float(
                np.mean(
                    [
                        peer["aligned_taker_imbalance_24h"] > 0.0
                        for peer in peers
                    ]
                )
            ),
            "local_minus_market_aligned_taker_imbalance_24h": float(
                local["aligned_taker_imbalance_24h"] - market_24h
            ),
            "market_median_aligned_flow_return_divergence_24h": float(
                np.median(
                    [
                        peer["aligned_flow_return_divergence_24h"]
                        for peer in peers
                    ]
                )
            ),
        }
        record = row._asdict()
        record.update(flow_features)
        record["market_peer_count"] = len(peers)
        records.append(record)
    panel = pd.DataFrame.from_records(records)
    if panel.empty:
        return panel, dict(rejected)
    for column in (*PRICE_FEATURES, *FLOW_FEATURES):
        if not np.isfinite(panel[column].to_numpy(dtype="float64")).all():
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
        "schema_version": "binance-1d-ma7-tfml-p0-v1",
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
    alpha: float,
) -> Pipeline:
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=alpha)),
        ]
    )
    model.fit(
        events[list(features)],
        events["z_8bps"].astype(float),
        model__sample_weight=asset_balanced_weights(events),
    )
    return model


def predict_utility(
    model: Pipeline,
    events: pd.DataFrame,
    features: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(
        model.predict(events[list(features)]),
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
    predictions_by_alpha: dict[float, pd.DataFrame] = {}
    for alpha in ALPHA_GRID:
        frames: list[pd.DataFrame] = []
        for fold, first_test, last_test in folds:
            train, test = split_for_block(
                events,
                first_test=first_test,
                last_test=last_test,
            )
            if train.empty or test.empty:
                frames = []
                break
            model = fit_model(train, features, alpha)
            prediction = test.copy()
            prediction["inner_fold"] = fold
            prediction["predicted_utility"] = predict_utility(
                model,
                test,
                features,
            )
            frames.append(prediction)
        if frames:
            predictions_by_alpha[alpha] = pd.concat(
                frames,
                ignore_index=True,
            )
    scores: list[dict[str, Any]] = []
    for alpha, predictions in predictions_by_alpha.items():
        for route in ROUTES:
            routed = predictions.loc[route_mask(predictions, route)].copy()
            for threshold in THRESHOLD_GRID:
                selected = routed.loc[
                    routed["predicted_utility"].ge(threshold)
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
                        "alpha": alpha,
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
            float(score["alpha"]),
            route_rank[str(score["route"])],
        ),
    )
    return {
        "alpha": float(choice["alpha"]),
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
    if not set(FLOW_FEATURES).issubset(features):
        return {}
    route = str(choice["route"])
    threshold = float(choice["threshold"])
    predictions = predict_utility(model, test, features)
    eligible = route_mask(test, route).to_numpy(dtype=bool)
    selected = eligible & (predictions >= threshold)
    outcomes = test["z_8bps"].to_numpy(dtype="float64")
    baseline = float(np.mean(np.where(selected, outcomes, 0.0)))
    importance: dict[str, float] = {}
    for feature_index, feature in enumerate(FLOW_FEATURES):
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
            predicted = predict_utility(model, permuted, features)
            permuted_selected = eligible & (predicted >= threshold)
            utilities[repeat] = float(
                np.mean(np.where(permuted_selected, outcomes, 0.0))
            )
        importance[feature] = float(baseline - np.mean(utilities))
    return importance


def evaluate_outer_fold(
    *,
    events: pd.DataFrame,
    features: tuple[str, ...],
    model_route: str,
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
    if train.empty or test.empty:
        raise RuntimeError(
            f"Invalid outer fold route={model_route} "
            f"asset={held_asset} fold={outer_fold}"
        )
    choice, inner_scores = select_inner(train, features)
    prediction = test.copy()
    prediction["held_asset"] = held_asset
    prediction["outer_fold"] = outer_fold
    prediction["model_route"] = model_route
    importance: dict[str, float] = {}
    if choice is None:
        prediction["predicted_utility"] = np.nan
        prediction["selected_alpha"] = np.nan
        prediction["selected_threshold"] = np.nan
        prediction["selected_route"] = "NO_SELECTION"
        prediction["route_eligible"] = False
        prediction["selected"] = False
    else:
        model = fit_model(train, features, float(choice["alpha"]))
        prediction["predicted_utility"] = predict_utility(
            model,
            test,
            features,
        )
        prediction["selected_alpha"] = float(choice["alpha"])
        prediction["selected_threshold"] = float(choice["threshold"])
        prediction["selected_route"] = str(choice["route"])
        prediction["route_eligible"] = route_mask(
            prediction,
            str(choice["route"]),
        )
        prediction["selected"] = (
            prediction["route_eligible"]
            & prediction["predicted_utility"].ge(
                float(choice["threshold"])
            )
        )
        if with_permutation:
            importance = permutation_importance(
                model=model,
                test=test,
                features=features,
                choice=choice,
                held_asset=held_asset,
                outer_fold=outer_fold,
            )
    report = {
        "model_route": model_route,
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
        "permutation_importance": importance,
        "inner_scores": inner_scores,
    }
    print(
        "OUTER_FOLD_COMPLETE "
        f"route={model_route} asset={held_asset} fold={outer_fold} "
        f"selected={report['selected_rows']} "
        f"choice={choice if choice is not None else 'NO_SELECTION'}"
    )
    return prediction, report


def run_outer_oof(
    events: pd.DataFrame,
    *,
    model_route: str,
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
                model_route=model_route,
                held_asset=asset,
                outer_fold=fold,
                first_test=first_test,
                last_test=last_test,
                with_permutation=model_route == "price_plus_flow",
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
        raise RuntimeError(f"{model_route} OOF has duplicate event_id")
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
        raise RuntimeError("Full/control OOF universes differ")
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
    for feature in FLOW_FEATURES:
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
                f"alpha={float(choice['alpha']):.0f}|"
                f"threshold={float(choice['threshold']):.4f}|"
                f"route={choice['route']}"
            )
            counts[key] += 1
    return dict(sorted(counts.items()))


def threshold_sensitivity(oof: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    finite = oof["predicted_utility"].notna() & oof["route_eligible"]
    for delta in (-0.0005, 0.0, 0.0005):
        selected = oof.loc[
            finite
            & oof["predicted_utility"].ge(
                oof["selected_threshold"] + delta
            )
        ]
        result[f"{delta:+.4f}"] = return_metrics(selected, "z_8bps")
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


def summarize_model_route(
    oof: pd.DataFrame,
    reports: list[dict[str, Any]],
    *,
    samples: int,
) -> dict[str, Any]:
    selected = oof.loc[oof["selected"]].copy()
    candidates = oof.loc[
        oof["predicted_utility"].notna() & oof["route_eligible"]
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
        asset_candidates = candidates.loc[candidates["asset"].eq(asset)]
        selected_metrics = return_metrics(asset_selected, "z_8bps")
        baseline_metrics = return_metrics(asset_oof, "z_8bps")
        spearman = float(
            asset_candidates["predicted_utility"].corr(
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
        candidates["predicted_utility"].corr(
            candidates["z_8bps"],
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
        "flow_permutation_importance": len(positive_importance) >= 2,
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
        "positive_flow_importance_features": positive_importance,
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
            float(choice["alpha"]),
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
            item[0],
            route_rank[item[2]],
        ),
    )
    return {
        "alpha": choice_tuple[0],
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
    model = fit_model(panel, FULL_FEATURES, float(choice["alpha"]))
    scaler: StandardScaler = model.named_steps["scale"]
    estimator: Ridge = model.named_steps["model"]
    return {
        "schema_version": "binance-1d-ma7-tfml-model-v1",
        "created_at_utc": datetime.now(UTC),
        "development_end_exclusive": END_EXCLUSIVE,
        "assets": list(ASSETS),
        "event_identity_sha256": EVENT_IDENTITY,
        "accepted_panel_identity_sha256": panel_identity,
        "features": list(FULL_FEATURES),
        "target": "z_8bps",
        "choice": choice,
        "train_rows": int(len(panel)),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficient": estimator.coef_.tolist(),
        "intercept": float(estimator.intercept_),
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
        "full_oof": output_dir / "p1_price_plus_flow_oof.parquet",
        "control_oof": output_dir / "p1_price_utility_control_oof.parquet",
        "flow_oof": output_dir / "p1_flow_only_oof.parquet",
        "summary": output_dir / "p1_summary.json",
        "report": output_dir / "p1_report.json",
    }
    panel.to_parquet(paths["accepted_events"], index=False)
    oof_by_route["price_plus_flow"].to_parquet(
        paths["full_oof"],
        index=False,
    )
    oof_by_route["price_utility_control"].to_parquet(
        paths["control_oof"],
        index=False,
    )
    oof_by_route["flow_only"].to_parquet(
        paths["flow_oof"],
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
        "schema_version": "binance-1d-ma7-tfml-p1-manifest-v1",
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
        periods=5_000,
        freq="5min",
    )
    phase = np.arange(len(timestamps), dtype="float64")
    open_values = 100.0 * np.exp(phase * 1e-7)
    close_values = open_values * np.exp(0.0001 * np.sin(phase / 17.0))
    quote = 1_000.0 + 100.0 * np.sin(phase / 13.0)
    imbalance = 0.1 * np.sin(phase / 19.0) + 0.01
    net = quote * imbalance
    cache = FlowCache(
        ts_ns=timestamps.to_numpy(dtype="datetime64[ns]").astype("int64"),
        open=open_values,
        close=close_values,
        quote_volume=quote,
        trade_count=np.full(len(timestamps), 100.0),
        net_quote=net,
        per_bar_imbalance=imbalance,
        active=np.ones(len(timestamps), dtype=bool),
    )
    entry = timestamps[4_500]
    before = local_flow_features(cache, entry_ts=entry, side=1)
    if before is None or set(before) != set(LOCAL_FLOW_FEATURES):
        raise AssertionError("Synthetic flow feature build failed")
    changed = FlowCache(
        ts_ns=cache.ts_ns,
        open=cache.open,
        close=np.where(
            np.arange(len(timestamps)) >= 4_500,
            cache.close * 2.0,
            cache.close,
        ),
        quote_volume=np.where(
            np.arange(len(timestamps)) >= 4_500,
            cache.quote_volume * 2.0,
            cache.quote_volume,
        ),
        trade_count=cache.trade_count,
        net_quote=np.where(
            np.arange(len(timestamps)) >= 4_500,
            cache.net_quote * 2.0,
            cache.net_quote,
        ),
        per_bar_imbalance=cache.per_bar_imbalance,
        active=cache.active,
    )
    after = local_flow_features(changed, entry_ts=entry, side=1)
    if before != after:
        raise AssertionError("Flow builder consumed post-entry rows")
    if (
        len(PRICE_FEATURES) != 47
        or len(FLOW_FEATURES) != 23
        or len(FULL_FEATURES) != 70
    ):
        raise AssertionError("Frozen feature contract changed")
    if "HYPE" in ASSETS or any("HYPE" in slug.upper() for slug in ASSET_SLUGS.values()):
        raise AssertionError("HYPE lock changed")
    print("SELF_TEST_OK")


def strict_nested_aggregate_capacity(
    *,
    asset_count: int = len(ASSETS),
    minimum_peers: int = MIN_MARKET_PEERS,
) -> dict[str, int | bool]:
    outer_peers = asset_count - 2
    inner_peers = asset_count - 3
    return {
        "asset_count": asset_count,
        "minimum_peers": minimum_peers,
        "outer_fold_peers": outer_peers,
        "inner_fold_peers": inner_peers,
        "outer_feasible": outer_peers >= minimum_peers,
        "inner_feasible": inner_peers >= minimum_peers,
    }


def enforce_strict_nested_aggregate_capacity() -> None:
    capacity = strict_nested_aggregate_capacity()
    if not bool(capacity["inner_feasible"]):
        raise RuntimeError(
            "TFML P1 strict nested LOAO is infeasible for the frozen five-asset "
            "universe: fold-local market aggregates must exclude the target, "
            "outer-held and inner-held assets, leaving "
            f"{capacity['inner_fold_peers']} peers below the frozen "
            f"minimum {capacity['minimum_peers']}. The historical P1 aggregate "
            "was computed before held-asset exclusion and is invalidated."
        )


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
    caches = {asset: load_flow_cache(asset) for asset in ASSETS}
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
    enforce_strict_nested_aggregate_capacity()
    oof_by_route: dict[str, pd.DataFrame] = {}
    reports_by_route: dict[str, list[dict[str, Any]]] = {}
    summaries_by_route: dict[str, dict[str, Any]] = {}
    for model_route, features in MODEL_FEATURES.items():
        oof, reports = run_outer_oof(
            panel,
            model_route=model_route,
            features=features,
            max_workers=args.max_workers,
        )
        oof_by_route[model_route] = oof
        reports_by_route[model_route] = reports
        summaries_by_route[model_route] = summarize_model_route(
            oof,
            reports,
            samples=args.bootstrap_samples,
        )
    delta = delta_bootstrap(
        oof_by_route["price_plus_flow"],
        oof_by_route["price_utility_control"],
        samples=args.bootstrap_samples,
    )
    importance = importance_summary(
        reports_by_route["price_plus_flow"]
    )
    gate = apply_development_gate(
        capacity=capacity,
        full_summary=summaries_by_route["price_plus_flow"],
        delta=delta,
        importance=importance,
    )
    summary = {
        "schema_version": "binance-1d-ma7-tfml-p1-summary-v1",
        "created_at_utc": datetime.now(UTC),
        "status": (
            "DEVELOPMENT_GATE_PASSED"
            if gate["development_gate_pass"]
            else "DEVELOPMENT_HARD_GATE_FAILED"
        ),
        "capacity": capacity,
        "routes": summaries_by_route,
        "full_vs_price_control": delta,
        "flow_permutation_importance": importance,
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
            "target": "z_8bps",
            "price_features": list(PRICE_FEATURES),
            "flow_features": list(FLOW_FEATURES),
            "full_features": list(FULL_FEATURES),
            "model_grid": {
                "alpha": list(ALPHA_GRID),
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
            reports_by_route["price_plus_flow"],
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
