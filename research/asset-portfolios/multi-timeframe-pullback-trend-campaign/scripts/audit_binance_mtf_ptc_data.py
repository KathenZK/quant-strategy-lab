from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/multi-timeframe-pullback-trend-campaign"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
LOADER_PATH = ROOT / "research/asset-portfolios/1h-price-impulse-campaign/scripts/research_binance_1h_pic_v0.py"
ASSETS = ("BTC", "ETH", "HYPE")
SPLITS = {
    "BTC": {"development_end": "2023-12-31T23:59:59Z", "validation_end": "2025-06-30T23:59:59Z", "locked_start": "2025-07-01T00:00:00Z"},
    "ETH": {"development_end": "2023-12-31T23:59:59Z", "validation_end": "2025-06-30T23:59:59Z", "locked_start": "2025-07-01T00:00:00Z"},
    "HYPE": {"development_end": "2025-10-31T23:59:59Z", "validation_end": "2026-02-28T23:59:59Z", "locked_start": "2026-03-01T00:00:00Z"},
}


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("bin_mtf_ptc_data_loader", LOADER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data loader: {LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_module()
    frames, quality = module.load_assets()
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Pullback-Trend-Campaign",
        "history_disclosure": "all existing history is revealed; locked evaluation is not fresh OOS",
        "purge_days": 14,
        "assets": {},
    }
    for asset in ASSETS:
        source = quality[asset]["source"]
        hourly = quality[asset]["hourly"]
        blockers = {
            "source_accepted": not bool(source["accepted"]),
            "hourly_accepted": not bool(hourly["accepted"]),
            "missing_15m": int(source["missing_15m_bars"]),
            "duplicates": int(source["duplicate_ts_before_dedup"]),
            "critical_nulls": int(sum(source["critical_nulls"].values())),
            "invalid_ohlcv": int(source["invalid_ohlcv_rows"]),
            "raw_normalized_parity": not bool(source["raw_vs_normalized"]["accepted"]),
        }
        blocker_count = sum(int(value) for value in blockers.values())
        payload["assets"][asset] = {
            "source": source,
            "hourly": hourly,
            "hourly_rows_loaded": int(len(frames[asset])),
            "splits": SPLITS[asset],
            "blockers": blockers,
            "blocker_count": blocker_count,
        }
        if blocker_count:
            raise RuntimeError(f"{asset} data quality blocker: {blockers}")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "binance_mtf_ptc_data_split_audit_2026-08-03.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({asset: {"blocker_count": row["blocker_count"], "rows": row["source"]["rows"], "start": row["source"]["start"], "end": row["source"]["end"]} for asset, row in payload["assets"].items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
