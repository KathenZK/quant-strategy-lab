from __future__ import annotations

import hashlib
import json
from pathlib import Path

import freeze_binance_as6s_v3_future_oos as freeze
from as6s_engine import load_funding, load_symbol_frame


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = FAMILY_DIR / "artifacts/binance_as6s_v3_future_oos_freeze_2026-07-14.json"


def main() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    for relative, expected in payload["frozen_files"].items():
        path = ROOT / relative
        if not path.exists():
            failures.append(f"missing:{relative}")
            continue
        actual = freeze.sha256_file(path)
        if actual != expected:
            failures.append(f"file_hash:{relative}:{expected}:{actual}")

    for symbol, expected in payload["data_snapshot_through_selection_end"].items():
        ohlcv = load_symbol_frame(symbol, end=freeze.v3.REUSED_END)
        funding = load_funding(symbol, end=freeze.v3.REUSED_END)
        actual = {
            "ohlcv_rows": len(ohlcv),
            "ohlcv_logical_sha256": freeze.logical_frame_digest(
                ohlcv, freeze.OHLCV_COLUMNS
            ),
            "funding_rows": len(funding),
            "funding_logical_sha256": freeze.logical_frame_digest(
                funding, freeze.FUNDING_COLUMNS
            ),
        }
        for key, value in actual.items():
            if value != expected[key]:
                failures.append(
                    f"data:{symbol}:{key}:{expected[key]}:{value}"
                )

    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    if failures:
        raise RuntimeError("freeze verification failed:\n" + "\n".join(failures))
    print(
        json.dumps(
            {
                "result": "PASS",
                "manifest": str(MANIFEST),
                "manifest_sha256": digest,
                "files_verified": len(payload["frozen_files"]),
                "symbols_verified": len(
                    payload["data_snapshot_through_selection_end"]
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
