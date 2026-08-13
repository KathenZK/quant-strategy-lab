from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1d-derivatives-structure-trend-opportunity"
)
METRICS_DIR = ROOT / "data/cache/binance_1d_dsto_p0_unaccepted"
PRICE_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p1_oi_funding_development_2026-08-10"
P0_MANIFEST_PATH = (
    FAMILY_DIR / "artifacts/p0_data_2026-08-10/manifest.json"
)
SHARED_KERNEL_PATH = (
    ROOT / "research/_shared-kernels/binance-ma7-root-data/v1/engine.py"
)
SHARED_KERNEL_SHA256 = (
    "3d7c6d295568b96627a4b6aa4efad0fc7fdc8a53503f9f4fa55922c7069bfa3d"
)

ASSET_SLUGS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
}
ASSETS = tuple(ASSET_SLUGS)
METRICS_START = pd.Timestamp("2021-12-01T00:00:00Z")
ANCHOR_START = pd.Timestamp("2021-12-08T00:00:00Z")
ANCHOR_END_EXCLUSIVE = pd.Timestamp("2025-05-25T00:00:00Z")
INPUT_END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")
HORIZON_HOURS = 120
LEVERAGE = 0.25
FEE_RATE = 0.001
MAIN_SLIPPAGE = 0.0004
LABEL_SLIPPAGE = 0.0008
STRESS_SLIPPAGE = 0.0012
LABEL_HURDLE = 0.0025
RANDOM_SEED = 20260810
BOOTSTRAP_SAMPLES = 10_000

PRICE_FEATURES = (
    "return_24h",
    "return_72h",
    "return_168h",
    "realized_vol_24h",
    "realized_vol_168h",
    "efficiency_24h",
    "efficiency_72h",
    "close_location_168h",
)
DERIVATIVE_FEATURES = (
    "oi_log_change_6h",
    "oi_log_change_24h",
    "oi_log_change_72h",
    "oi_log_change_168h",
    "oi_value_log_change_24h",
    "oi_acceleration_24h_72h",
    "price_oi_confirmation_24h",
    "price_oi_confirmation_72h",
    "funding_sum_24h",
    "funding_sum_72h",
    "funding_sum_168h",
    "funding_acceleration_24h_72h",
    "funding_positive_share_168h",
    "oi_funding_crowding_24h",
    "market_median_oi_change_24h",
    "market_median_oi_change_72h",
    "market_median_oi_change_168h",
    "market_positive_oi_breadth_24h",
    "market_median_funding_sum_24h",
    "market_positive_funding_breadth_24h",
    "local_minus_market_oi_change_24h",
    "local_minus_market_funding_sum_24h",
)
LOCAL_DERIVATIVE_FEATURES = DERIVATIVE_FEATURES[:14]
MARKET_DERIVATIVE_FEATURES = DERIVATIVE_FEATURES[14:]
FULL_FEATURES = PRICE_FEATURES + DERIVATIVE_FEATURES
THRESHOLDS = (0.45, 0.55, 0.65)
MIN_MARKET_PEERS = 3


@dataclass(frozen=True)
class ModelChoice:
    kind: str
    parameter: float | int
    threshold: float


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_shared_kernel() -> Any:
    actual = sha256_path(SHARED_KERNEL_PATH)
    if actual != SHARED_KERNEL_SHA256:
        raise RuntimeError(
            f"Shared kernel SHA mismatch: {actual} != {SHARED_KERNEL_SHA256}"
        )
    name = "binance_ma7_root_data_v1_dsto"
    spec = importlib.util.spec_from_file_location(name, SHARED_KERNEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load shared kernel")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


shared = load_shared_kernel()


def feature_paths(asset: str) -> tuple[Path, dict[str, Path]]:
    if asset == "HYPE" or asset not in ASSET_SLUGS:
        raise RuntimeError(f"Forbidden asset: {asset}")
    slug = ASSET_SLUGS[asset]
    metric_path = METRICS_DIR / f"{slug}_metrics_5m.parquet"
    price_paths = shared.feature_paths(PRICE_DIR, slug)
    for path in (metric_path, *price_paths.values()):
        if "hype" in path.name.lower():
            raise RuntimeError(f"Forbidden HYPE path: {path}")
        if not path.exists():
            raise FileNotFoundError(path)
    return metric_path, price_paths


def verify_p0_source_artifacts() -> dict[str, Any]:
    if not P0_MANIFEST_PATH.exists():
        raise FileNotFoundError(P0_MANIFEST_PATH)
    manifest = json.loads(P0_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    for key in ("source_manifest", "data_quality"):
        details = files.get(key)
        if not isinstance(details, dict):
            raise RuntimeError(f"P0 manifest missing {key}")
        path = P0_MANIFEST_PATH.parent / str(details["path"])
        if not path.exists() or sha256_path(path) != details["sha256"]:
            raise RuntimeError(f"P0 artifact identity mismatch: {key}")
    source_path = P0_MANIFEST_PATH.parent / files["source_manifest"]["path"]
    quality_path = P0_MANIFEST_PATH.parent / files["data_quality"]["path"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if (
        source.get("archive_count") != 6_385
        or source.get("hype_requests_sent") != 0
        or source_quality.get("hype_rows_consumed") != 0
        or source_quality.get("hype_files_opened") != 0
        or source_quality.get("hype_requests_sent") != 0
    ):
        raise RuntimeError("P0 source identity or HYPE lock mismatch")
    feature_entries: dict[str, dict[str, Any]] = {}
    for asset in ASSETS:
        key = f"{asset.lower()}_feature"
        details = files.get(key)
        if not isinstance(details, dict):
            raise RuntimeError(f"P0 manifest missing {key}")
        path = ROOT / str(details["path"])
        if not path.exists() or sha256_path(path) != details["sha256"]:
            raise RuntimeError(f"P0 cache identity mismatch: {asset}")
        feature_entries[asset] = {
            "path": str(path),
            "sha256": details["sha256"],
        }
    return {
        "source_manifest_sha256": files["source_manifest"]["sha256"],
        "data_quality_sha256": files["data_quality"]["sha256"],
        "archive_count": source["archive_count"],
        "original_full_field_quality_pass": bool(
            source_quality.get("quality_pass")
        ),
        "feature_entries": feature_entries,
        "hype_rows_consumed": 0,
        "hype_files_opened": 0,
        "hype_requests_sent": 0,
    }


def prefix_sum(values: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(values, dtype="float64")])


def load_metrics(asset: str, path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    required = {
        "ts",
        "asset",
        "source",
        "sum_open_interest",
        "sum_open_interest_value",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"{asset} metrics missing columns: {sorted(missing)}")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    timestamps = pd.DatetimeIndex(frame["ts"])
    if (
        frame.empty
        or timestamps.min() < METRICS_START
        or timestamps.max() >= INPUT_END_EXCLUSIVE
        or not timestamps.is_monotonic_increasing
    ):
        raise RuntimeError(f"{asset} metrics boundary/order mismatch")
    if set(frame["asset"]) != {asset} or set(frame["source"]) != {
        "binance_vision_metrics"
    }:
        raise RuntimeError(f"{asset} metrics identity mismatch")
    for column in ("sum_open_interest", "sum_open_interest_value"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def metric_anchor_features(
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    anchors: pd.DatetimeIndex,
) -> pd.DataFrame:
    unique_metrics = frame.loc[~frame["ts"].duplicated(keep=False)].set_index("ts")
    funding_frame = funding.copy()
    funding_frame["funding_nominal_ts"] = pd.to_datetime(
        funding_frame["funding_nominal_ts"], utc=True
    )
    funding_frame["funding_rate"] = pd.to_numeric(
        funding_frame["funding_rate"], errors="coerce"
    )
    funding_frame = funding_frame.sort_values("funding_nominal_ts")
    rows: list[dict[str, Any]] = []
    for anchor in anchors:
        metric_times = [
            anchor - pd.Timedelta(minutes=5),
            anchor - pd.Timedelta(hours=6),
            anchor - pd.Timedelta(hours=24),
            anchor - pd.Timedelta(hours=72),
            anchor - pd.Timedelta(hours=168),
        ]
        if not all(timestamp in unique_metrics.index for timestamp in metric_times):
            continue
        metric_rows = unique_metrics.loc[
            metric_times, ["sum_open_interest", "sum_open_interest_value"]
        ]
        metric_values = metric_rows.to_numpy(dtype="float64")
        if (
            not np.isfinite(metric_values).all()
            or np.any(metric_values <= 0.0)
        ):
            continue
        funding_168h = funding_frame.loc[
            (
                funding_frame["funding_nominal_ts"]
                >= anchor - pd.Timedelta(hours=168)
            )
            & (funding_frame["funding_nominal_ts"] < anchor)
        ]
        if funding_168h.empty:
            continue
        last_age = anchor - pd.Timestamp(
            funding_168h["funding_nominal_ts"].iloc[-1]
        )
        if (
            last_age < pd.Timedelta(0)
            or last_age > pd.Timedelta(hours=8)
            or len(funding_168h) < 20
            or not np.isfinite(
                funding_168h["funding_rate"].to_numpy(dtype="float64")
            ).all()
        ):
            continue

        funding_windows: dict[int, pd.DataFrame] = {}
        for hours, minimum_rows in ((24, 3), (72, 9), (168, 20)):
            window = funding_168h.loc[
                funding_168h["funding_nominal_ts"]
                >= anchor - pd.Timedelta(hours=hours)
            ]
            if len(window) < minimum_rows:
                break
            funding_windows[hours] = window
        if len(funding_windows) != 3:
            continue

        log_oi = np.log(metric_rows["sum_open_interest"].to_numpy(dtype="float64"))
        log_oi_value = np.log(
            metric_rows["sum_open_interest_value"].to_numpy(dtype="float64")
        )
        oi_change_6h = float(log_oi[0] - log_oi[1])
        oi_change_24h = float(log_oi[0] - log_oi[2])
        oi_change_72h = float(log_oi[0] - log_oi[3])
        oi_change_168h = float(log_oi[0] - log_oi[4])
        funding_sums = {
            hours: float(window["funding_rate"].sum())
            for hours, window in funding_windows.items()
        }
        row = {
            "anchor_ts": anchor,
            "oi_log_change_6h": oi_change_6h,
            "oi_log_change_24h": oi_change_24h,
            "oi_log_change_72h": oi_change_72h,
            "oi_log_change_168h": oi_change_168h,
            "oi_value_log_change_24h": float(log_oi_value[0] - log_oi_value[2]),
            "oi_acceleration_24h_72h": (
                oi_change_24h - oi_change_72h / 3.0
            ),
            "funding_sum_24h": funding_sums[24],
            "funding_sum_72h": funding_sums[72],
            "funding_sum_168h": funding_sums[168],
            "funding_acceleration_24h_72h": (
                funding_sums[24] - funding_sums[72] / 3.0
            ),
            "funding_positive_share_168h": float(
                (funding_windows[168]["funding_rate"] > 0.0).mean()
            ),
            "oi_funding_crowding_24h": oi_change_24h * funding_sums[24],
        }
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=["anchor_ts", *LOCAL_DERIVATIVE_FEATURES])
    if not np.isfinite(
        result.drop(columns=["anchor_ts"]).to_numpy(dtype="float64")
    ).all():
        raise RuntimeError("Metrics anchor features contain non-finite values")
    return result


def price_cache(
    hourly: pd.DataFrame, funding: pd.DataFrame
) -> dict[str, np.ndarray]:
    ts_ns = (
        pd.to_datetime(hourly["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    if np.any(np.diff(ts_ns) != 3_600_000_000_000):
        raise RuntimeError("Hourly price input is not continuous")
    funding_ts_ns = (
        pd.to_datetime(funding["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    funding_mark_rate = (
        funding["funding_rate"].to_numpy(dtype="float64")
        * funding["mark_price"].to_numpy(dtype="float64")
    )
    return {
        "ts_ns": ts_ns,
        "open": hourly["open"].to_numpy(dtype="float64"),
        "high": hourly["high"].to_numpy(dtype="float64"),
        "low": hourly["low"].to_numpy(dtype="float64"),
        "close": hourly["close"].to_numpy(dtype="float64"),
        "funding_ts_ns": funding_ts_ns,
        "funding_mark_rate_prefix": prefix_sum(funding_mark_rate),
    }


def path_feature_values(cache: dict[str, np.ndarray], index: int) -> dict[str, float]:
    close = cache["close"]
    high = cache["high"]
    low = cache["low"]
    if index < 169:
        raise RuntimeError("Insufficient hourly price warmup")
    log_close = np.log(close[index - 169 : index])
    hourly_returns = np.diff(log_close)

    def horizon_values(hours: int) -> tuple[float, float, float]:
        values = hourly_returns[-hours:]
        endpoint = float(values.sum())
        volatility = float(np.sqrt(np.mean(np.square(values))))
        path = float(np.abs(values).sum())
        efficiency = endpoint / path if path > 0.0 else 0.0
        return endpoint, volatility, efficiency

    return_24, vol_24, efficiency_24 = horizon_values(24)
    return_72, _, efficiency_72 = horizon_values(72)
    return_168, vol_168, _ = horizon_values(168)
    range_high = float(np.max(high[index - 168 : index]))
    range_low = float(np.min(low[index - 168 : index]))
    location = (
        (float(close[index - 1]) - range_low) / (range_high - range_low)
        if range_high > range_low
        else 0.5
    )
    return {
        "return_24h": return_24,
        "return_72h": return_72,
        "return_168h": return_168,
        "realized_vol_24h": vol_24,
        "realized_vol_168h": vol_168,
        "efficiency_24h": efficiency_24,
        "efficiency_72h": efficiency_72,
        "close_location_168h": location,
    }


def funding_mark_sum(
    cache: dict[str, np.ndarray], entry_index: int, exit_index: int
) -> float:
    entry_ns = int(cache["ts_ns"][entry_index])
    exit_ns = int(cache["ts_ns"][exit_index])
    funding_ns = cache["funding_ts_ns"]
    left = int(np.searchsorted(funding_ns, entry_ns, side="right"))
    right = int(np.searchsorted(funding_ns, exit_ns, side="left"))
    prefix = cache["funding_mark_rate_prefix"]
    return float(prefix[right] - prefix[left])


def side_outcome(
    cache: dict[str, np.ndarray],
    *,
    entry_index: int,
    exit_index: int,
    side: int,
    slippage: float,
    include_funding: bool,
) -> float:
    entry_reference = float(cache["open"][entry_index])
    exit_reference = float(cache["open"][exit_index])
    entry_fill = entry_reference * (1.0 + side * slippage)
    funding_component = (
        -side * funding_mark_sum(cache, entry_index, exit_index) / entry_fill
        if include_funding
        else 0.0
    )
    return float(
        shared.levered_trade_return(
            side=side,
            entry_reference=entry_reference,
            exit_reference=exit_reference,
            slippage=slippage,
            fee_rate=FEE_RATE,
            leverage=LEVERAGE,
            funding_component=funding_component,
        )["direct_net_return"]
    )


def asset_anchor_panel(
    asset: str,
    metric_features: pd.DataFrame,
    cache: dict[str, np.ndarray],
) -> pd.DataFrame:
    ts_ns = cache["ts_ns"]
    rows: list[dict[str, Any]] = []
    for metric_row in metric_features.itertuples(index=False):
        anchor = pd.Timestamp(metric_row.anchor_ts)
        index = int(np.searchsorted(ts_ns, int(anchor.value), side="left"))
        if (
            index >= len(ts_ns)
            or int(ts_ns[index]) != int(anchor.value)
            or index + HORIZON_HOURS + 1 >= len(ts_ns)
        ):
            raise RuntimeError(f"{asset} missing anchor price at {anchor}")
        price_values = path_feature_values(cache, index)
        row: dict[str, Any] = {
            "anchor_id": f"{asset}-{anchor.strftime('%Y%m%d')}",
            "asset": asset,
            "anchor_ts": anchor,
            "entry_ts": anchor,
            "exit_ts": pd.Timestamp(
                int(ts_ns[index + HORIZON_HOURS]), tz="UTC"
            ),
            **price_values,
        }
        for feature in LOCAL_DERIVATIVE_FEATURES:
            if feature.startswith("price_oi_confirmation_"):
                continue
            if not hasattr(metric_row, feature):
                raise RuntimeError(f"Missing local derivative feature: {feature}")
            row[feature] = float(getattr(metric_row, feature))
        row["price_oi_confirmation_24h"] = (
            row["return_24h"] * row["oi_log_change_24h"]
        )
        row["price_oi_confirmation_72h"] = (
            row["return_72h"] * row["oi_log_change_72h"]
        )
        for side_name, side in (("long", 1), ("short", -1)):
            row[f"{side_name}_z_4bps"] = side_outcome(
                cache,
                entry_index=index,
                exit_index=index + HORIZON_HOURS,
                side=side,
                slippage=MAIN_SLIPPAGE,
                include_funding=True,
            )
            row[f"{side_name}_z_8bps"] = side_outcome(
                cache,
                entry_index=index,
                exit_index=index + HORIZON_HOURS,
                side=side,
                slippage=LABEL_SLIPPAGE,
                include_funding=True,
            )
            row[f"{side_name}_z_12bps"] = side_outcome(
                cache,
                entry_index=index,
                exit_index=index + HORIZON_HOURS,
                side=side,
                slippage=STRESS_SLIPPAGE,
                include_funding=True,
            )
            row[f"{side_name}_z_funding_off"] = side_outcome(
                cache,
                entry_index=index,
                exit_index=index + HORIZON_HOURS,
                side=side,
                slippage=MAIN_SLIPPAGE,
                include_funding=False,
            )
            row[f"{side_name}_z_lag1h"] = side_outcome(
                cache,
                entry_index=index + 1,
                exit_index=index + HORIZON_HOURS + 1,
                side=side,
                slippage=MAIN_SLIPPAGE,
                include_funding=True,
            )
        long_positive = row["long_z_8bps"] >= LABEL_HURDLE
        short_positive = row["short_z_8bps"] >= LABEL_HURDLE
        if long_positive and short_positive:
            raise RuntimeError(f"{row['anchor_id']} has contradictory labels")
        row["label"] = 1 if long_positive else (-1 if short_positive else 0)
        rows.append(row)
    return pd.DataFrame(rows)


def add_market_features(panel: pd.DataFrame) -> pd.DataFrame:
    local_columns = {
        "market_median_oi_change_24h": "oi_log_change_24h",
        "market_median_oi_change_72h": "oi_log_change_72h",
        "market_median_oi_change_168h": "oi_log_change_168h",
        "market_median_funding_sum_24h": "funding_sum_24h",
    }
    by_anchor = {
        pd.Timestamp(anchor): group.set_index("asset")
        for anchor, group in panel.groupby("anchor_ts", sort=True)
    }
    output_rows: list[dict[str, Any]] = []
    for row in panel.to_dict("records"):
        peers = by_anchor[pd.Timestamp(row["anchor_ts"])].drop(
            index=str(row["asset"])
        )
        if len(peers) < 3:
            continue
        row["market_peer_count"] = len(peers)
        for output, source in local_columns.items():
            row[output] = float(peers[source].median())
        row["market_positive_oi_breadth_24h"] = float(
            (peers["oi_log_change_24h"] > 0.0).mean()
        )
        row["market_positive_funding_breadth_24h"] = float(
            (peers["funding_sum_24h"] > 0.0).mean()
        )
        row["local_minus_market_oi_change_24h"] = (
            float(row["oi_log_change_24h"])
            - float(row["market_median_oi_change_24h"])
        )
        row["local_minus_market_funding_sum_24h"] = (
            float(row["funding_sum_24h"])
            - float(row["market_median_funding_sum_24h"])
        )
        output_rows.append(row)
    result = pd.DataFrame(output_rows)
    if not np.isfinite(result[list(FULL_FEATURES)].to_numpy(dtype="float64")).all():
        raise RuntimeError("Anchor feature panel contains non-finite values")
    return result.sort_values(["anchor_ts", "asset"]).reset_index(drop=True)


def load_anchor_panel() -> tuple[pd.DataFrame, dict[str, Any]]:
    source_audit = verify_p0_source_artifacts()
    anchors = pd.date_range(
        ANCHOR_START,
        ANCHOR_END_EXCLUSIVE - pd.Timedelta(days=1),
        freq="1D",
        tz="UTC",
    )
    panels: list[pd.DataFrame] = []
    asset_quality: dict[str, Any] = {}
    for asset, slug in ASSET_SLUGS.items():
        metric_path, _ = feature_paths(asset)
        expected_entry = source_audit["feature_entries"][asset]
        if metric_path != Path(expected_entry["path"]):
            raise RuntimeError(f"{asset} metric path differs from P0 manifest")
        metrics = load_metrics(asset, metric_path)
        _, hourly, funding, input_quality = shared.load_asset_inputs(
            PRICE_DIR,
            asset=asset,
            slug=slug,
            end_exclusive=INPUT_END_EXCLUSIVE,
        )
        metric_features = metric_anchor_features(metrics, funding, anchors)
        cache = price_cache(hourly, funding)
        asset_panel = asset_anchor_panel(asset, metric_features, cache)
        panels.append(asset_panel)
        asset_quality[asset] = {
            "metrics_path": str(metric_path.relative_to(ROOT)),
            "metrics_sha256": sha256_path(metric_path),
            "metrics_rows": len(metrics),
            "local_exact_endpoint_anchors": len(asset_panel),
            "input_quality": input_quality,
        }
    panel = add_market_features(pd.concat(panels, ignore_index=True))
    return panel, {"source_audit": source_audit, "assets": asset_quality}


def capacity_summary(panel: pd.DataFrame, quality: dict[str, Any]) -> dict[str, Any]:
    label_counts = {
        "long": int((panel["label"] == 1).sum()),
        "flat": int((panel["label"] == 0).sum()),
        "short": int((panel["label"] == -1).sum()),
    }
    per_asset = {
        asset: int((panel["asset"] == asset).sum()) for asset in ASSETS
    }
    checks = {
        "usable_anchors": len(panel) >= 6_100,
        "per_asset": all(value >= 1_200 for value in per_asset.values()),
        "exact_endpoint_admission": (
            int(panel["market_peer_count"].min()) >= 3
            and all(
                details["local_exact_endpoint_anchors"] >= 1_200
                for details in quality["assets"].values()
            )
        ),
        "label_capacity": all(value >= 500 for value in label_counts.values()),
        "source_manifest_verified": (
            quality["source_audit"]["archive_count"] == 6_385
            and not quality["source_audit"]["original_full_field_quality_pass"]
        ),
        "hype_lock": (
            quality["source_audit"]["hype_rows_consumed"] == 0
            and quality["source_audit"]["hype_files_opened"] == 0
            and quality["source_audit"]["hype_requests_sent"] == 0
        ),
    }
    return {
        "schema_version": "binance-1d-dsto-p0r-oi-funding-v1",
        "anchor_start": ANCHOR_START,
        "anchor_end_exclusive": ANCHOR_END_EXCLUSIVE,
        "usable_anchors": len(panel),
        "per_asset": per_asset,
        "label_counts": label_counts,
        "feature_count_full": len(FULL_FEATURES),
        "feature_count_control": len(PRICE_FEATURES),
        "quality": quality,
        "hype_rows_consumed": 0,
        "hype_files_opened": 0,
        "hype_requests_sent": 0,
        "gate_checks": checks,
        "p0_capacity_pass": all(checks.values()),
        "panel_identity_sha256": frame_identity_sha256(
            panel, ["anchor_id", "label", "long_z_4bps", "short_z_4bps"]
        ),
    }


def frame_identity_sha256(frame: pd.DataFrame, columns: list[str]) -> str:
    payload = frame[columns].to_csv(index=False, float_format="%.17g")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def model_candidates() -> tuple[tuple[str, float | int], ...]:
    return tuple(
        [("logistic", value) for value in (0.03, 0.10, 0.30, 1.00)]
        + [("lightgbm", leaves) for leaves in (7, 15)]
    )


def asset_balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame["asset"].value_counts()
    assets = len(counts)
    return np.asarray(
        [len(frame) / (assets * counts[asset]) for asset in frame["asset"]],
        dtype="float64",
    )


def encode_labels(series: pd.Series) -> np.ndarray:
    return series.map({-1: 0, 0: 1, 1: 2}).to_numpy(dtype="int64")


def fit_model(
    frame: pd.DataFrame,
    features: tuple[str, ...],
    kind: str,
    parameter: float | int,
) -> dict[str, Any] | None:
    y = encode_labels(frame["label"])
    if len(np.unique(y)) < 3:
        return None
    x_frame = frame[list(features)].astype("float64")
    weights = asset_balanced_weights(frame)
    if kind == "logistic":
        x = x_frame.to_numpy(dtype="float64")
        scaler = StandardScaler()
        scaler.fit(x, sample_weight=weights)
        model = LogisticRegression(
            C=float(parameter),
            solver="lbfgs",
            max_iter=3000,
            random_state=RANDOM_SEED,
        )
        model.fit(scaler.transform(x), y, sample_weight=weights)
        return {"kind": kind, "model": model, "scaler": scaler}
    if kind == "lightgbm":
        model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            num_leaves=int(parameter),
            n_estimators=200,
            learning_rate=0.03,
            max_depth=-1,
            min_child_samples=50,
            reg_lambda=5.0,
            subsample=1.0,
            colsample_bytree=1.0,
            random_state=RANDOM_SEED,
            deterministic=True,
            force_col_wise=True,
            n_jobs=1,
            verbosity=-1,
        )
        model.fit(x_frame, y, sample_weight=weights)
        return {"kind": kind, "model": model, "scaler": None}
    raise ValueError(kind)


def predict_probabilities(
    fitted: dict[str, Any],
    frame: pd.DataFrame,
    features: tuple[str, ...],
) -> np.ndarray:
    x_frame = frame[list(features)].astype("float64")
    scaler = fitted["scaler"]
    if scaler is not None:
        model_input: Any = scaler.transform(
            x_frame.to_numpy(dtype="float64")
        )
    else:
        model_input = x_frame
    probabilities = fitted["model"].predict_proba(model_input)
    classes = fitted["model"].classes_.astype("int64")
    output = np.zeros((len(frame), 3), dtype="float64")
    for source_index, class_value in enumerate(classes):
        output[:, class_value] = probabilities[:, source_index]
    return output


def score_frame(frame: pd.DataFrame, probabilities: np.ndarray) -> pd.DataFrame:
    scored = frame.copy()
    scored["p_short"] = probabilities[:, 0]
    scored["p_flat"] = probabilities[:, 1]
    scored["p_long"] = probabilities[:, 2]
    return scored


def apply_policy(
    scored: pd.DataFrame,
    *,
    threshold_column: str = "selected_threshold",
    threshold_delta: float = 0.0,
) -> pd.DataFrame:
    output = scored.copy()
    output["direction"] = np.where(
        output["p_long"] >= output["p_short"], 1, -1
    )
    output["confidence"] = np.maximum(output["p_long"], output["p_short"])
    effective_threshold = np.clip(
        output[threshold_column].to_numpy(dtype="float64") + threshold_delta,
        0.0,
        1.0,
    )
    output["qualifies"] = (
        output["confidence"].to_numpy(dtype="float64") >= effective_threshold
    ) & (
        output["confidence"].to_numpy(dtype="float64")
        > output["p_flat"].to_numpy(dtype="float64")
    )
    output["executed"] = False
    for _, group in output.groupby("asset", sort=False):
        busy_until = pd.Timestamp.min.tz_localize("UTC")
        for index in group.sort_values("anchor_ts").index:
            anchor = pd.Timestamp(output.at[index, "anchor_ts"])
            if bool(output.at[index, "qualifies"]) and anchor >= busy_until:
                output.at[index, "executed"] = True
                busy_until = pd.Timestamp(output.at[index, "exit_ts"])
    for suffix in ("z_4bps", "z_8bps", "z_12bps", "z_funding_off", "z_lag1h"):
        output[f"selected_{suffix}"] = np.where(
            output["direction"] == 1,
            output[f"long_{suffix}"],
            output[f"short_{suffix}"],
        )
        output[f"utility_{suffix}"] = np.where(
            output["executed"], output[f"selected_{suffix}"], 0.0
        )
    return output


def return_metrics(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    executed = frame.loc[frame["executed"]].copy()
    if executed.empty:
        empty = executed.copy()
        empty["entry_ts"] = pd.Series(dtype="datetime64[ns, UTC]")
        empty["root_id"] = pd.Series(dtype="object")
        empty[column] = pd.Series(dtype="float64")
        return shared.return_metrics(empty, column)
    executed["root_id"] = executed["anchor_id"]
    return shared.return_metrics(executed, column)


def time_blocks(frame: pd.DataFrame, *, initial_fraction: float, blocks: int) -> list[pd.DatetimeIndex]:
    unique = pd.DatetimeIndex(sorted(frame["anchor_ts"].unique()))
    initial = max(1, int(len(unique) * initial_fraction))
    remainder = unique[initial:]
    return [pd.DatetimeIndex(values) for values in np.array_split(remainder, blocks)]


def split_fold(
    frame: pd.DataFrame,
    *,
    held_asset: str,
    first_test: pd.Timestamp,
    last_test: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    embargo_boundary = first_test - pd.Timedelta(hours=HORIZON_HOURS)
    train = frame.loc[
        (frame["asset"] != held_asset)
        & (frame["exit_ts"] < embargo_boundary)
    ].copy()
    test = frame.loc[
        (frame["asset"] == held_asset)
        & (frame["anchor_ts"] >= first_test)
        & (frame["anchor_ts"] <= last_test)
    ].copy()
    return train, test


def inner_scores(
    outer_train: pd.DataFrame,
    features: tuple[str, ...],
    kind: str,
    parameter: float | int,
) -> pd.DataFrame:
    blocks = time_blocks(outer_train, initial_fraction=0.50, blocks=3)
    rows: list[pd.DataFrame] = []
    inner_assets = sorted(outer_train["asset"].unique())
    for block_number, block in enumerate(blocks, start=1):
        if block.empty:
            continue
        first_test = pd.Timestamp(block.min())
        last_test = pd.Timestamp(block.max())
        for held_asset in inner_assets:
            train, test = split_fold(
                outer_train,
                held_asset=held_asset,
                first_test=first_test,
                last_test=last_test,
            )
            if len(train) < 300 or test.empty:
                continue
            fitted = fit_model(train, features, kind, parameter)
            if fitted is None:
                continue
            scored = score_frame(
                test, predict_probabilities(fitted, test, features)
            )
            scored["inner_time_block"] = block_number
            rows.append(scored)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def choose_inner(
    outer_train: pd.DataFrame, features: tuple[str, ...]
) -> tuple[ModelChoice | None, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    for kind, parameter in model_candidates():
        scored = inner_scores(outer_train, features, kind, parameter)
        if scored.empty:
            continue
        for threshold in THRESHOLDS:
            thresholded = scored.copy()
            thresholded["selected_threshold"] = threshold
            decisions = apply_policy(thresholded)
            trades = decisions.loc[decisions["executed"]]
            metrics = return_metrics(decisions, "selected_z_4bps")
            side_counts = trades["direction"].value_counts()
            block_metrics = {
                int(block): return_metrics(group, "selected_z_4bps")
                for block, group in decisions.groupby(
                    "inner_time_block", sort=True
                )
            }
            eligible = (
                metrics["events"] >= 120
                and int(side_counts.get(1, 0)) >= 40
                and int(side_counts.get(-1, 0)) >= 40
                and len(block_metrics) == 3
                and all(item["mean"] > 0.0 for item in block_metrics.values())
                and metrics["profit_factor"] >= 1.05
            )
            candidates.append(
                {
                    "kind": kind,
                    "parameter": parameter,
                    "threshold": threshold,
                    "metrics": metrics,
                    "block_metrics": block_metrics,
                    "eligible": eligible,
                }
            )
    eligible_candidates = [item for item in candidates if item["eligible"]]
    if not eligible_candidates:
        return None, candidates

    def rank(item: dict[str, Any]) -> tuple[float, ...]:
        complexity = (
            -float(item["parameter"])
            if item["kind"] == "logistic"
            else -100.0 - float(item["parameter"])
        )
        return (
            min(value["mean"] for value in item["block_metrics"].values()),
            item["metrics"]["mean"],
            item["metrics"]["profit_factor"],
            item["threshold"],
            complexity,
        )

    selected = max(eligible_candidates, key=rank)
    return (
        ModelChoice(
            str(selected["kind"]),
            selected["parameter"],
            float(selected["threshold"]),
        ),
        candidates,
    )


def permutation_importance(
    fitted: dict[str, Any],
    test: pd.DataFrame,
    features: tuple[str, ...],
    *,
    fold_seed: int,
) -> dict[str, float]:
    if test.empty:
        return {}
    baseline = predict_probabilities(fitted, test, features)
    y = encode_labels(test["label"])
    baseline_loss = float(log_loss(y, baseline, labels=[0, 1, 2]))
    rng = np.random.default_rng(fold_seed)
    importance: dict[str, float] = {}
    for feature in features:
        permuted = test.copy()
        values = permuted[feature].to_numpy(copy=True)
        rng.shuffle(values)
        permuted[feature] = values
        loss = float(
            log_loss(
                y,
                predict_probabilities(fitted, permuted, features),
                labels=[0, 1, 2],
            )
        )
        importance[feature] = loss - baseline_loss
    return importance


def run_outer(
    panel: pd.DataFrame,
    features: tuple[str, ...],
    *,
    route: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    blocks = time_blocks(panel, initial_fraction=0.40, blocks=4)
    specifications = [
        (asset_number, held_asset, block_number, block)
        for asset_number, held_asset in enumerate(ASSETS)
        for block_number, block in enumerate(blocks, start=1)
    ]

    def evaluate_fold(
        specification: tuple[int, str, int, pd.DatetimeIndex],
    ) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any] | None]:
        asset_number, held_asset, block_number, block = specification
        fold_id = f"{held_asset}-{block_number}"
        first_test = pd.Timestamp(block.min())
        last_test = pd.Timestamp(block.max())
        train, test = split_fold(
            panel,
            held_asset=held_asset,
            first_test=first_test,
            last_test=last_test,
        )
        choice, candidates = choose_inner(train, features)
        selection = {
            "route": route,
            "fold_id": fold_id,
            "held_asset": held_asset,
            "time_block": block_number,
            "train_rows": len(train),
            "test_rows": len(test),
            "choice": (
                {
                    "kind": choice.kind,
                    "parameter": choice.parameter,
                    "threshold": choice.threshold,
                }
                if choice is not None
                else None
            ),
            "inner_candidates": candidates,
        }
        importance_row: dict[str, Any] | None = None
        if choice is None:
            scored = test.copy()
            scored["p_short"] = 0.0
            scored["p_flat"] = 1.0
            scored["p_long"] = 0.0
            scored["selected_threshold"] = 1.0
            scored["outer_selection_available"] = False
        else:
            fitted = fit_model(train, features, choice.kind, choice.parameter)
            if fitted is None:
                raise RuntimeError("Selected outer model could not be fitted")
            probabilities = predict_probabilities(fitted, test, features)
            scored = score_frame(test, probabilities)
            scored["selected_threshold"] = choice.threshold
            scored["outer_selection_available"] = True
            importance_row = {
                "fold_id": fold_id,
                **permutation_importance(
                    fitted,
                    test,
                    features,
                    fold_seed=RANDOM_SEED + asset_number * 10 + block_number,
                ),
            }
        scored["route"] = route
        scored["outer_fold"] = fold_id
        scored["outer_time_block"] = block_number
        print(f"OUTER_FOLD_COMPLETE {route} {fold_id}", flush=True)
        return scored, selection, importance_row

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(evaluate_fold, specifications))
    score_rows = [result[0] for result in results]
    selections = [result[1] for result in results]
    importances = [
        result[2] for result in results if result[2] is not None
    ]
    scores = pd.concat(score_rows, ignore_index=True)
    decisions = apply_policy(scores)
    return decisions, selections, importances


def block_labels(series: pd.Series, days: int = 90) -> pd.Series:
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    return ((series - epoch) // pd.Timedelta(days=days)).astype("int64")


def cluster_bootstrap(
    frame: pd.DataFrame,
    *,
    column: str,
    utility: bool,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    usable = frame.loc[frame[column].notna()].copy()
    if not utility:
        usable = usable.loc[usable["executed"]]
    if usable.empty:
        return {
            "samples": BOOTSTRAP_SAMPLES,
            "clusters": 0,
            "positive_probability": 0.0,
            "quantiles": {"2.5%": 0.0, "50%": 0.0, "97.5%": 0.0},
        }
    usable["block"] = block_labels(usable["anchor_ts"])
    clusters = [
        group[column].to_numpy(dtype="float64")
        for _, group in usable.groupby(["asset", "block"], sort=True)
    ]
    rng = np.random.default_rng(seed)
    means = np.empty(BOOTSTRAP_SAMPLES, dtype="float64")
    for index in range(BOOTSTRAP_SAMPLES):
        selected = rng.integers(0, len(clusters), size=len(clusters))
        values = np.concatenate([clusters[item] for item in selected])
        means[index] = float(np.mean(values))
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": seed,
        "clusters": len(clusters),
        "positive_probability": float(np.mean(means > 0.0)),
        "quantiles": {
            "2.5%": float(np.quantile(means, 0.025)),
            "50%": float(np.quantile(means, 0.5)),
            "97.5%": float(np.quantile(means, 0.975)),
        },
    }


def ranking_summary(decisions: pd.DataFrame) -> dict[str, Any]:
    trades = decisions.loc[decisions["executed"]].copy()
    if len(trades) < 3:
        return {
            "spearman": 0.0,
            "positive_asset_count": 0,
            "per_asset": {},
        }
    overall = float(
        spearmanr(
            trades["confidence"],
            trades["selected_z_4bps"],
        ).statistic
    )
    per_asset: dict[str, float] = {}
    for asset in ASSETS:
        subset = trades.loc[trades["asset"] == asset]
        value = (
            float(spearmanr(subset["confidence"], subset["selected_z_4bps"]).statistic)
            if len(subset) >= 3
            else 0.0
        )
        per_asset[asset] = value if math.isfinite(value) else 0.0
    return {
        "spearman": overall if math.isfinite(overall) else 0.0,
        "positive_asset_count": sum(value > 0.0 for value in per_asset.values()),
        "per_asset": per_asset,
    }


def importance_summary(
    importances: list[dict[str, Any]],
) -> dict[str, Any]:
    if not importances:
        return {"per_feature_median": {}, "positive_derivative_count": 0}
    frame = pd.DataFrame(importances)
    medians = {
        feature: float(frame[feature].median())
        for feature in FULL_FEATURES
        if feature in frame
    }
    return {
        "per_feature_median": medians,
        "positive_derivative_count": sum(
            medians.get(feature, 0.0) > 0.0
            for feature in DERIVATIVE_FEATURES
        ),
    }


def summarize_route(decisions: pd.DataFrame) -> dict[str, Any]:
    trades = decisions.loc[decisions["executed"]]
    main = return_metrics(decisions, "selected_z_4bps")
    per_asset = {
        asset: return_metrics(
            decisions.loc[decisions["asset"] == asset], "selected_z_4bps"
        )
        for asset in ASSETS
    }
    per_fold = {
        fold: return_metrics(group, "selected_z_4bps")
        for fold, group in decisions.groupby("outer_fold", sort=True)
    }
    side_counts = trades["direction"].value_counts()
    return {
        "main": main,
        "variants": {
            column: return_metrics(decisions, column)
            for column in (
                "selected_z_8bps",
                "selected_z_12bps",
                "selected_z_funding_off",
                "selected_z_lag1h",
            )
        },
        "per_asset": per_asset,
        "per_fold": per_fold,
        "positive_asset_count": sum(
            metrics["mean"] > 0.0 for metrics in per_asset.values()
        ),
        "positive_outer_fold_count": sum(
            metrics["mean"] > 0.0 for metrics in per_fold.values()
        ),
        "side_counts": {
            "long": int(side_counts.get(1, 0)),
            "short": int(side_counts.get(-1, 0)),
        },
        "ranking": ranking_summary(decisions),
        "bootstrap": cluster_bootstrap(
            decisions, column="selected_z_4bps", utility=False
        ),
        "outer_selection_count": int(
            decisions.groupby("outer_fold")["outer_selection_available"]
            .first()
            .sum()
        ),
    }


def control_delta(
    full: pd.DataFrame, control: pd.DataFrame
) -> dict[str, Any]:
    left = full[
        ["anchor_id", "asset", "anchor_ts", "utility_z_4bps"]
    ].rename(columns={"utility_z_4bps": "full_utility"})
    right = control[["anchor_id", "utility_z_4bps"]].rename(
        columns={"utility_z_4bps": "control_utility"}
    )
    paired = left.merge(right, on="anchor_id", validate="one_to_one")
    paired["utility_delta"] = (
        paired["full_utility"] - paired["control_utility"]
    )
    paired["executed"] = True
    return {
        "anchors": len(paired),
        "full_mean_utility": float(paired["full_utility"].mean()),
        "control_mean_utility": float(paired["control_utility"].mean()),
        "mean_delta": float(paired["utility_delta"].mean()),
        "bootstrap": cluster_bootstrap(
            paired,
            column="utility_delta",
            utility=True,
            seed=RANDOM_SEED + 1,
        ),
    }


def recent_slices(
    decisions: pd.DataFrame, end: pd.Timestamp
) -> dict[str, Any]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    return {
        name: return_metrics(
            decisions.loc[
                (decisions["anchor_ts"] >= end - window)
                & (decisions["anchor_ts"] < end)
            ],
            "selected_z_4bps",
        )
        for name, window in windows.items()
    }


def threshold_sensitivity(decisions: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, delta in (("minus_0.05", -0.05), ("plus_0.05", 0.05)):
        variant = apply_policy(decisions.drop(
            columns=[
                column
                for column in decisions.columns
                if (
                    column.startswith("selected_")
                    and column != "selected_threshold"
                )
                or column.startswith("utility_")
                or column in {"direction", "confidence", "qualifies", "executed"}
            ],
            errors="ignore",
        ), threshold_delta=delta)
        output[name] = return_metrics(variant, "selected_z_4bps")
    return output


def development_gate(
    capacity: dict[str, Any],
    summary: dict[str, Any],
    delta: dict[str, Any],
    importance: dict[str, Any],
) -> dict[str, bool]:
    variants = summary["variants"]
    return {
        "p0_capacity": bool(capacity["p0_capacity_pass"]),
        "oof_coverage": (
            summary["main"]["events"] >= 300
            and all(
                summary["per_asset"][asset]["events"] >= 40 for asset in ASSETS
            )
            and summary["side_counts"]["long"] >= 100
            and summary["side_counts"]["short"] >= 100
        ),
        "main_economics": (
            summary["main"]["mean"] > 0.0
            and summary["main"]["profit_factor"] >= 1.15
        ),
        "positive_assets": summary["positive_asset_count"] >= 4,
        "positive_outer_folds": summary["positive_outer_fold_count"] >= 15,
        "ranking": (
            summary["ranking"]["spearman"] > 0.03
            and summary["ranking"]["positive_asset_count"] >= 4
        ),
        "cluster_bootstrap": (
            summary["bootstrap"]["positive_probability"] >= 0.90
        ),
        "beats_price_control": (
            delta["mean_delta"] > 0.0
            and delta["bootstrap"]["positive_probability"] >= 0.90
        ),
        "derivative_importance": (
            importance["positive_derivative_count"] >= 2
        ),
        "stress_8bps": (
            variants["selected_z_8bps"]["mean"] > 0.0
            and variants["selected_z_8bps"]["profit_factor"] >= 1.05
        ),
        "stress_funding_off": (
            variants["selected_z_funding_off"]["mean"] > 0.0
            and variants["selected_z_funding_off"]["profit_factor"] >= 1.05
        ),
        "stress_lag1h": (
            variants["selected_z_lag1h"]["events"]
            == summary["main"]["events"]
            and variants["selected_z_lag1h"]["mean"] > 0.0
            and variants["selected_z_lag1h"]["profit_factor"] >= 1.05
        ),
    }


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
            "DSTO P1 strict nested LOAO is infeasible for the frozen five-asset "
            "universe: fold-local market aggregates must exclude the target, "
            "outer-held and inner-held assets, leaving "
            f"{capacity['inner_fold_peers']} peers below the frozen "
            f"minimum {capacity['minimum_peers']}. The historical P1 aggregate "
            "was computed before held-asset exclusion and is invalidated; use a "
            "new contract/universe instead of regenerating it."
        )


def build_payload(*, capacity_only: bool) -> dict[str, Any]:
    panel, quality = load_anchor_panel()
    capacity = capacity_summary(panel, quality)
    if capacity_only or not capacity["p0_capacity_pass"]:
        return {
            "capacity": capacity,
            "panel": panel,
            "report": None,
            "summary": {
                "decision": (
                    "P0_CAPACITY_PASS"
                    if capacity["p0_capacity_pass"]
                    else "P0_CAPACITY_FAILED"
                ),
                "capacity": capacity,
            },
        }
    enforce_strict_nested_aggregate_capacity()
    full, full_selections, full_importances = run_outer(
        panel, FULL_FEATURES, route="full"
    )
    control, control_selections, _ = run_outer(
        panel, PRICE_FEATURES, route="price_control"
    )
    full_summary = summarize_route(full)
    control_summary = summarize_route(control)
    delta = control_delta(full, control)
    importance = importance_summary(full_importances)
    gates = development_gate(capacity, full_summary, delta, importance)
    full_summary["recent_slices"] = recent_slices(
        full, ANCHOR_END_EXCLUSIVE
    )
    full_summary["threshold_sensitivity"] = threshold_sensitivity(full)
    report = {
        "schema_version": "binance-1d-dsto-p1-oi-funding-v1",
        "generated_at_utc": pd.Timestamp.now(tz="UTC"),
        "capacity": capacity,
        "full_summary": full_summary,
        "control_summary": control_summary,
        "control_delta": delta,
        "importance": importance,
        "full_selections": full_selections,
        "control_selections": control_selections,
        "full_importances": full_importances,
        "gate_checks": gates,
        "development_gate_pass": all(gates.values()),
        "frozen_model": None,
        "hype_rows_consumed": 0,
        "hype_files_opened": 0,
        "hype_requests_sent": 0,
    }
    summary = {
        "decision": (
            "DEVELOPMENT_PASS"
            if report["development_gate_pass"]
            else "DEVELOPMENT_HARD_GATE_FAILED"
        ),
        "capacity": {
            "usable_anchors": capacity["usable_anchors"],
            "label_counts": capacity["label_counts"],
            "p0_capacity_pass": capacity["p0_capacity_pass"],
        },
        "full": full_summary,
        "control": control_summary,
        "control_delta": delta,
        "importance": importance,
        "gate_checks": gates,
        "development_gate_pass": report["development_gate_pass"],
    }
    return {
        "capacity": capacity,
        "panel": panel,
        "full": full,
        "control": control,
        "report": report,
        "summary": summary,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_outputs(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "capacity": ARTIFACT_DIR / "p0_data_capacity.json",
        "panel": ARTIFACT_DIR / "p0_p1_anchor_panel.parquet",
    }
    write_json(paths["capacity"], payload["capacity"])
    payload["panel"].to_parquet(paths["panel"], index=False)
    if payload["report"] is not None:
        paths.update(
            {
                "full_scores": ARTIFACT_DIR / "p1_full_oof_scores.parquet",
                "control_scores": ARTIFACT_DIR
                / "p1_control_oof_scores.parquet",
                "report": ARTIFACT_DIR / "p1_report.json",
                "summary": ARTIFACT_DIR / "p1_summary.json",
            }
        )
        payload["full"].to_parquet(paths["full_scores"], index=False)
        payload["control"].to_parquet(paths["control_scores"], index=False)
        write_json(paths["report"], payload["report"])
        write_json(paths["summary"], payload["summary"])
    manifest = {
        "schema_version": "binance-1d-dsto-oi-funding-manifest-v1",
        "generated_at_utc": pd.Timestamp.now(tz="UTC"),
        "files": {
            name: {
                "path": path.name,
                "sha256": sha256_path(path),
            }
            for name, path in paths.items()
        },
    }
    manifest_path = ARTIFACT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    checksum = ARTIFACT_DIR / "manifest.sha256"
    checksum.write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    return {
        name: details["sha256"] for name, details in manifest["files"].items()
    } | {"manifest": sha256_path(manifest_path)}


def run_self_test() -> None:
    assert len(PRICE_FEATURES) == 8
    assert len(LOCAL_DERIVATIVE_FEATURES) == 14
    assert len(MARKET_DERIVATIVE_FEATURES) == 8
    assert len(DERIVATIVE_FEATURES) == 22
    assert len(FULL_FEATURES) == 30
    assert set(PRICE_FEATURES).isdisjoint(DERIVATIVE_FEATURES)
    assert "HYPE" not in ASSETS
    assert ANCHOR_START < ANCHOR_END_EXCLUSIVE < INPUT_END_EXCLUSIVE
    print("self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity-only", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return
    payload = build_payload(capacity_only=args.capacity_only)
    output = dict(payload["summary"])
    if not args.no_write:
        output["artifact_sha256"] = write_outputs(payload)
    print(json.dumps(json_ready(output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
