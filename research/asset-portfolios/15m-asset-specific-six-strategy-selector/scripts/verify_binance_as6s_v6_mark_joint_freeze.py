from __future__ import annotations

import hashlib
import json
from pathlib import Path

from as6s_engine import REUSED_END, load_funding, load_symbol_frame
import freeze_binance_as6s_v6_mark_joint_future_oos as freeze
import replay_binance_as6s_v6_mark_price_account as mark_replay


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json"
)


def main() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    if payload.get("version") != "BIN-15M-AS6S-V6":
        failures.append("version:drift")
    if payload["future_oos"]["start_inclusive"] != REUSED_END.isoformat():
        failures.append("future_oos:start_drift")
    arbitration = payload.get("arbitration", {})
    if not arbitration.get("entry_time_fields_only"):
        failures.append("arbitration:not_entry_time_only")
    if "exit_ts" not in arbitration.get("forbidden_fields", []):
        failures.append("arbitration:exit_ts_not_forbidden")
    if arbitration.get("account_position_owner") != "global joint account only":
        failures.append("state:position_owner_not_global")

    for relative, expected in payload["frozen_files"].items():
        path = ROOT / relative
        if not path.exists():
            failures.append(f"missing:{relative}")
            continue
        actual = freeze.v5_freeze.v4_freeze.v3_freeze.sha256_file(path)
        if actual != expected:
            failures.append(f"file_hash:{relative}:{expected}:{actual}")

    for symbol, expected in payload[
        "trade_and_funding_snapshot_through_selection_end"
    ].items():
        ohlcv = load_symbol_frame(symbol, end=REUSED_END)
        funding = load_funding(symbol, end=REUSED_END)
        actual = {
            "ohlcv_rows": len(ohlcv),
            "ohlcv_logical_sha256": freeze.v5_freeze.v4_freeze.v3_freeze.logical_frame_digest(
                ohlcv, freeze.v5_freeze.v4_freeze.v3_freeze.OHLCV_COLUMNS
            ),
            "funding_rows": len(funding),
            "funding_logical_sha256": freeze.v5_freeze.v4_freeze.v3_freeze.logical_frame_digest(
                funding, freeze.v5_freeze.v4_freeze.v3_freeze.FUNDING_COLUMNS
            ),
        }
        for field, value in actual.items():
            if value != expected[field]:
                failures.append(f"data:{symbol}:{field}:{expected[field]}:{value}")

    for symbol, expected in payload["mark_price_snapshot_through_selection_end"].items():
        mark = mark_replay.load_mark(symbol)
        actual = {
            "rows": len(mark),
            "first_ts": mark["ts"].iloc[0].isoformat(),
            "last_ts": mark["ts"].iloc[-1].isoformat(),
            "logical_sha256": freeze.v5_freeze.v4_freeze.v3_freeze.logical_frame_digest(
                mark, freeze.MARK_COLUMNS
            ),
        }
        for field, value in actual.items():
            if value != expected[field]:
                failures.append(f"mark:{symbol}:{field}:{expected[field]}:{value}")

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
                    payload["trade_and_funding_snapshot_through_selection_end"]
                ),
                "mark_symbols_verified": len(
                    payload["mark_price_snapshot_through_selection_end"]
                ),
                "entry_time_fields_only": True,
                "joint_state_owner": arbitration["account_position_owner"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
