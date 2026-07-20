from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
SCRIPT_DIR = FAMILY_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_prefreeze_inference_panel as builder  # noqa: E402


OOS_START = pd.Timestamp("2026-07-19T00:00:00Z")
OOS_END = pd.Timestamp("2026-10-19T00:00:00Z")
PROSPECTIVE_DIR = FAMILY_DIR / "artifacts/prospective_oos"
DATA_MANIFEST = PROSPECTIVE_DIR / "data/latest_data_manifest.json"
WORK_ROOT = PROSPECTIVE_DIR / "working"
TAIL_STAGING = WORK_ROOT / "tail_staging"
BY_SYMBOL = WORK_ROOT / "by_symbol"
PANEL_PATH = WORK_ROOT / "current_feature_panel.parquet"
MANIFEST_PATH = WORK_ROOT / "current_feature_panel_manifest.json"
DYNAMIC_CATALOG = WORK_ROOT / "current_crypto_universe.csv"
BASE_CATALOG = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/artifacts/"
    "binance_usdm_crypto_universe_catalog_2026-07-17.csv"
)
MODEL_MANIFEST = FAMILY_DIR / (
    "artifacts/freeze/bin-1h-mhcsml-v1-model-freeze-r4.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build only the latest feature rows for blind R4 inference."
    )
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_dynamic_catalog(exchange_info_path: Path) -> None:
    base = pd.read_csv(BASE_CATALOG, usecols=["symbol", "eligible"])
    info = json.loads(exchange_info_path.read_text(encoding="utf-8"))
    current = pd.DataFrame(
        {
            "symbol": [
                str(row["symbol"]).removesuffix("USDT") + "/USDT:USDT"
                for row in info["symbols"]
                if row.get("contractType") == "PERPETUAL"
                and row.get("quoteAsset") == "USDT"
                and row.get("status") == "TRADING"
            ],
            "eligible": True,
        }
    )
    catalog = (
        pd.concat([base, current], ignore_index=True)
        .sort_values(["symbol", "eligible"], ascending=[True, False])
        .drop_duplicates("symbol", keep="first")
    )
    DYNAMIC_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(DYNAMIC_CATALOG, index=False)


def main() -> None:
    args = parse_args()
    source = json.loads(DATA_MANIFEST.read_text(encoding="utf-8"))
    if source.get("status") != "PASS" or source.get("blockers"):
        raise RuntimeError("prospective feature-input manifest is not PASS")
    if source.get("prospective_oos_outcomes_read"):
        raise RuntimeError("feature-input manifest reports protected outcome access")
    end = pd.Timestamp(source["closed_end_exclusive"])
    if end > OOS_END:
        raise RuntimeError("feature-input sync crossed frozen OOS end")
    exchange_info_path = ROOT / source["exchange_info_path"]
    if sha256(exchange_info_path) != source["exchange_info_sha256"]:
        raise RuntimeError("exchange-info SHA mismatch")
    model_manifest = json.loads(MODEL_MANIFEST.read_text(encoding="utf-8"))
    required_features: set[str] = set()
    for spec in model_manifest["feature_lists"].values():
        required_features.update(
            json.loads((ROOT / spec["path"]).read_text(encoding="utf-8"))
        )
    shutil.rmtree(WORK_ROOT, ignore_errors=True)
    BY_SYMBOL.mkdir(parents=True, exist_ok=True)
    write_dynamic_catalog(exchange_info_path)
    market_root, funding_root = builder.stage_tail(
        end=end, overwrite=True, staging_root=TAIL_STAGING
    )
    slugs = sorted(builder.current_slugs(exchange_info_path))
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                builder.compute_one,
                slug,
                str(market_root),
                str(funding_root),
                end.isoformat(),
                str(BY_SYMBOL),
            )
            for slug in slugs
        ]
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 50 == 0 or index == len(futures):
                print(f"blind_factors {index}/{len(futures)}", flush=True)
    written = [row for row in results if row["status"] == "written"]
    if len(written) < 400:
        raise RuntimeError(f"too few symbols produced factors: {len(written)}")
    builder.build_panel(
        end,
        by_symbol_root=BY_SYMBOL,
        panel_path=PANEL_PATH,
        universe_catalog=DYNAMIC_CATALOG,
    )
    panel = pd.read_parquet(PANEL_PATH)
    panel["ts"] = pd.to_datetime(panel["ts"], utc=True)
    panel = panel.loc[panel["ts"].ge(end - pd.Timedelta(hours=8))].copy()
    panel.to_parquet(PANEL_PATH, index=False, compression="zstd")
    label_columns = sorted(
        name
        for name in panel.columns
        if name.startswith(("label_", "target_", "future_"))
    )
    missing_features = sorted(required_features - set(panel.columns))
    blockers: list[str] = []
    if label_columns:
        blockers.append("outcome_columns_present")
    if missing_features:
        blockers.append("frozen_features_missing")
    if panel.duplicated(["ts", "symbol"]).any():
        blockers.append("duplicate_keys")
    if panel.empty or panel["ts"].max() >= end:
        blockers.append("closed_bar_boundary_invalid")
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "role": "prospective OOS feature-only current inference panel",
        "source_data_manifest": str(DATA_MANIFEST.relative_to(ROOT)),
        "source_data_manifest_sha256": sha256(DATA_MANIFEST),
        "end_exclusive": end.isoformat(),
        "rows": len(panel),
        "symbols": int(panel["symbol"].nunique()),
        "first_ts": panel["ts"].min().isoformat() if len(panel) else None,
        "last_ts": panel["ts"].max().isoformat() if len(panel) else None,
        "label_columns": label_columns,
        "missing_frozen_features": missing_features,
        "panel_path": str(PANEL_PATH.relative_to(ROOT)),
        "panel_sha256": sha256(PANEL_PATH),
        "symbol_job_status_counts": pd.Series(
            [row["status"] for row in results]
        ).value_counts().to_dict(),
        "prospective_oos_outcomes_read": False,
        "blockers": blockers,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    if blockers:
        raise RuntimeError(f"blind prospective panel blocked: {blockers}")


if __name__ == "__main__":
    main()
