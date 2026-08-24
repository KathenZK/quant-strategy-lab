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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-taker-flow-meta-label"
BASE_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-later-maturity-meta-label/"
    "scripts/research_binance_1d_ma7_lmml_p1.py"
)
LEGACY_FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
FRESH_FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_tfml_p0e"
OUTPUT_DIR = FAMILY_DIR / "artifacts/p0e_events_2026-08-10"
END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")
LEGACY_ASSETS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
}
FRESH_ASSETS = {
    "XRP": "xrpusdt",
    "DOGE": "dogeusdt",
    "ADA": "adausdt",
    "LINK": "linkusdt",
    "LTC": "ltcusdt",
    "DOT": "dotusdt",
    "AVAX": "avaxusdt",
    "UNI": "uniusdt",
}
ALL_ASSETS = {**LEGACY_ASSETS, **FRESH_ASSETS}


def load_base_module():
    spec = importlib.util.spec_from_file_location(
        "binance_1d_ma7_tfml_p0e_event_base",
        BASE_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise ImportError(BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    if "HYPE" in ALL_ASSETS:
        raise RuntimeError("HYPE data is forbidden")
    base = load_base_module()
    base.ASSETS = ALL_ASSETS
    base.DEVELOPMENT_END_EXCLUSIVE = END_EXCLUSIVE
    dailies: dict[str, pd.DataFrame] = {}
    hourlies: dict[str, pd.DataFrame] = {}
    fundings: dict[str, pd.DataFrame] = {}
    quality: dict[str, Any] = {}
    for asset, slug in ALL_ASSETS.items():
        feature_dir = (
            LEGACY_FEATURE_DIR
            if asset in LEGACY_ASSETS
            else FRESH_FEATURE_DIR
        )
        daily, hourly, funding, asset_quality = base.shared.load_asset_inputs(
            feature_dir,
            asset=asset,
            slug=slug,
            end_exclusive=END_EXCLUSIVE,
        )
        dailies[asset] = daily
        hourlies[asset] = hourly
        fundings[asset] = funding
        quality[asset] = asset_quality
    events, root_summary = base.build_events(dailies, hourlies, fundings)
    identity = base.event_identity_sha256(events)
    fresh = events.loc[events["asset"].isin(FRESH_ASSETS)]
    fresh_counts = {
        asset: int(fresh["asset"].eq(asset).sum()) for asset in FRESH_ASSETS
    }
    checks = {
        "fresh_event_total": len(fresh) >= 1_600,
        "fresh_per_asset": all(count >= 180 for count in fresh_counts.values()),
        "fresh_direction_capacity": min(
            int(fresh["side"].gt(0).sum()),
            int(fresh["side"].lt(0).sum()),
        )
        >= 650,
        "all_feature_inputs_validated": len(quality) == len(ALL_ASSETS),
        "hype_lock": True,
    }
    capacity = {
        "schema_version": "binance-1d-ma7-tfml-p0e-events-v1",
        "generated_at_utc": datetime.now(UTC),
        "contract": (
            "specs/binance-1d-ma7-tfml-p0e-p1e-"
            "universe-expansion-contract-2026-08-10.md"
        ),
        "development_end_exclusive": END_EXCLUSIVE,
        "legacy_assets": list(LEGACY_ASSETS),
        "fresh_assets": list(FRESH_ASSETS),
        "all_assets": list(ALL_ASSETS),
        "event_rows": int(len(events)),
        "fresh_event_rows": int(len(fresh)),
        "fresh_per_asset": fresh_counts,
        "fresh_long_events": int(fresh["side"].gt(0).sum()),
        "fresh_short_events": int(fresh["side"].lt(0).sum()),
        "event_identity_sha256": identity,
        "per_asset_root_summary": root_summary,
        "input_quality": quality,
        "checks": checks,
        "p0e_event_capacity_pass": bool(all(checks.values())),
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    event_path = OUTPUT_DIR / "p0e_events.parquet"
    capacity_path = OUTPUT_DIR / "p0e_event_capacity.json"
    events.to_parquet(event_path, index=False)
    write_json(capacity_path, capacity)
    files = {
        "events": {
            "path": event_path.name,
            "bytes": event_path.stat().st_size,
            "sha256": sha256_path(event_path),
        },
        "capacity": {
            "path": capacity_path.name,
            "bytes": capacity_path.stat().st_size,
            "sha256": sha256_path(capacity_path),
        },
    }
    manifest = {
        "schema_version": "binance-1d-ma7-tfml-p0e-event-manifest-v1",
        "created_at_utc": datetime.now(UTC),
        "files": files,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    (OUTPUT_DIR / "manifest.sha256").write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    print(json.dumps(json_ready(capacity), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
