from __future__ import annotations

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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-local-temporal-audit"
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_alta_p0"
DATA_MANIFEST = FAMILY_DIR / (
    "artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json"
)
OUTPUT_DIR = FAMILY_DIR / "artifacts/p0_events_2026-08-10"
BASE_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-later-maturity-meta-label/"
    "scripts/research_binance_1d_ma7_lmml_p1.py"
)
T0 = pd.Timestamp("2025-05-31T00:00:00Z")
T1 = pd.Timestamp("2026-08-01T00:00:00Z")
TRAIN_PURGE_END = T0 - pd.Timedelta(days=5)
ASSETS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
    "XRP": "xrpusdt",
    "DOGE": "dogeusdt",
    "ADA": "adausdt",
    "LINK": "linkusdt",
    "LTC": "ltcusdt",
    "DOT": "dotusdt",
    "AVAX": "avaxusdt",
    "UNI": "uniusdt",
    "BCH": "bchusdt",
    "ETC": "etcusdt",
    "XLM": "xlmusdt",
    "ATOM": "atomusdt",
    "VET": "vetusdt",
    "NEAR": "nearusdt",
    "AAVE": "aaveusdt",
    "FIL": "filusdt",
}


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location(
        "binance_1d_ma7_alta_event_base", BASE_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if "HYPE" in ASSETS:
        raise RuntimeError("HYPE data is forbidden")
    source = json.loads(DATA_MANIFEST.read_text(encoding="utf-8"))
    if (
        source.get("family") != "BIN-1D-MA7-ALTA"
        or int(source.get("blocker_count", -1)) != 0
        or set(source.get("symbols", []))
        != {f"{asset}USDT" for asset in ASSETS}
    ):
        raise RuntimeError("ALTA P0 source manifest failed admission")

    base = load_base()
    base.ASSETS = ASSETS
    base.DEVELOPMENT_END_EXCLUSIVE = T1
    dailies: dict[str, pd.DataFrame] = {}
    hourlies: dict[str, pd.DataFrame] = {}
    fundings: dict[str, pd.DataFrame] = {}
    input_quality: dict[str, Any] = {}
    for asset, slug in ASSETS.items():
        daily, hourly, funding, quality = base.shared.load_asset_inputs(
            FEATURE_DIR,
            asset=asset,
            slug=slug,
            end_exclusive=T1,
        )
        dailies[asset] = daily
        hourlies[asset] = hourly
        fundings[asset] = funding
        input_quality[asset] = quality

    events, root_summary = base.build_events(dailies, hourlies, fundings)
    train = events.loc[events["exit_ts"].lt(TRAIN_PURGE_END)].copy()
    test = events.loc[
        events["signal_ts"].ge(T0) & events["signal_ts"].lt(T1)
    ].copy()
    per_asset = {
        asset: int(test["asset"].eq(asset).sum()) for asset in ASSETS
    }
    side_counts = {
        "long": int(test["side"].gt(0).sum()),
        "short": int(test["side"].lt(0).sum()),
    }
    checks = {
        "source_quality": int(source["blocker_count"]) == 0,
        "test_total": len(test) >= 200,
        "test_per_asset": all(count >= 8 for count in per_asset.values()),
        "test_directions": min(side_counts.values()) >= 75,
        "train_per_asset": all(
            int(train["asset"].eq(asset).sum()) >= 100 for asset in ASSETS
        ),
        "feature_contract": len(base.FEATURES) == 47
        and len(set(base.FEATURES)) == 47,
        "feature_completeness": not events[list(base.FEATURES)].isna().any().any(),
        "hype_lock": True,
    }
    capacity = {
        "schema_version": "binance-1d-ma7-alta-p0-events-v1",
        "generated_at_utc": datetime.now(UTC),
        "contract": "specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md",
        "t0": T0,
        "train_purge_end_exclusive": TRAIN_PURGE_END,
        "t1_exclusive": T1,
        "assets": list(ASSETS),
        "all_event_rows": int(len(events)),
        "train_event_rows": int(len(train)),
        "test_event_rows": int(len(test)),
        "test_per_asset": per_asset,
        "test_side_counts": side_counts,
        "event_identity_sha256": base.event_identity_sha256(events),
        "train_identity_sha256": base.event_identity_sha256(
            train.reset_index(drop=True)
        ),
        "test_identity_sha256": base.event_identity_sha256(
            test.reset_index(drop=True)
        ),
        "source_manifest_sha256": sha256_path(DATA_MANIFEST),
        "per_asset_root_summary": root_summary,
        "input_quality": input_quality,
        "checks": checks,
        "p0_capacity_pass": bool(all(checks.values())),
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "events": OUTPUT_DIR / "p0_events.parquet",
        "capacity": OUTPUT_DIR / "p0_capacity.json",
    }
    events.to_parquet(paths["events"], index=False)
    write_json(paths["capacity"], capacity)
    manifest = {
        "schema_version": "binance-1d-ma7-alta-p0-event-manifest-v1",
        "created_at_utc": datetime.now(UTC),
        "files": {
            key: {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
            }
            for key, path in paths.items()
        },
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    (OUTPUT_DIR / "manifest.sha256").write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            json_ready(
                {
                    "p0_capacity_pass": capacity["p0_capacity_pass"],
                    "train_event_rows": capacity["train_event_rows"],
                    "test_event_rows": capacity["test_event_rows"],
                    "test_per_asset": capacity["test_per_asset"],
                    "test_side_counts": capacity["test_side_counts"],
                    "checks": checks,
                    "event_identity_sha256": capacity[
                        "event_identity_sha256"
                    ],
                    "hype_rows": 0,
                    "hype_files": 0,
                    "hype_requests": 0,
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
