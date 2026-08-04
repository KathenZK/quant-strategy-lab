from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dstc_data import load_assets


FAMILY_DIR = Path(__file__).resolve().parents[1]
OUTPUT = FAMILY_DIR / "artifacts/binance_mtf_dstc_data_audit_2026-08-04.json"


def main() -> None:
    assets = load_assets()
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Dual-State-Trend-Campaign",
        "status": "data audit; no strategy performance evaluated",
        "boundary": {
            "HYPE": "query/filesystem cutoff 2026-08-01T15:15:00Z; no later partition supplied to DuckDB",
            "BTC_ETH": "query/filesystem cutoff 2026-08-03T11:45:00Z",
        },
        "assets": {asset: data.quality for asset, data in assets.items()},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                asset: {
                    "rows15": len(data.bars15),
                    "rows1h": len(data.bars1h),
                    "rows4h": len(data.bars4h),
                    "rows1d": len(data.bars1d),
                    "start": data.quality["source"]["start"],
                    "end": data.quality["source"]["end"],
                    "accepted": all(section["accepted"] for section in data.quality.values()),
                }
                for asset, data in assets.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
