from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

import pandas as pd

import _btc_15m_v40_common as common


DATA_END_EXCLUSIVE = pd.Timestamp("2026-07-17T14:45:00Z")
TRAIN_START = pd.Timestamp("2024-07-17T14:45:00Z")
VALIDATION_START = pd.Timestamp("2025-07-17T14:45:00Z")
HOLDOUT_START = pd.Timestamp("2026-01-17T14:45:00Z")
HOLDOUT_END = pd.Timestamp("2026-07-17T14:45:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze BTC-15M-EMA-TB V40 development and holdout splits."
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Validate constants and kernel SHA without reading or writing artifacts.",
    )
    return parser.parse_args()


def build_payload() -> dict[str, object]:
    common.load_kernel()
    audit_bytes = common.AUDIT_PATH.read_bytes()
    audit = json.loads(audit_bytes)
    cutoff = pd.Timestamp(audit["closed_bar_cutoff_exclusive"])
    last_ts = pd.Timestamp(audit["ohlcv_quality"]["last_ts"])
    expected_last = DATA_END_EXCLUSIVE - common.BAR
    if cutoff != DATA_END_EXCLUSIVE:
        raise RuntimeError(
            "latest data audit endpoint does not match frozen endpoint: "
            f"expected {DATA_END_EXCLUSIVE.isoformat()}, got {cutoff.isoformat()}"
        )
    if last_ts != expected_last:
        raise RuntimeError(
            "latest audited candle does not match frozen endpoint: "
            f"expected {expected_last.isoformat()}, got {last_ts.isoformat()}"
        )
    if int(audit.get("total_blocker_count", -1)) != 0:
        raise RuntimeError("latest data audit contains blockers")
    if audit.get("fatal_errors"):
        raise RuntimeError("latest data audit contains fatal errors")
    if not audit.get("writes", {}).get("performed"):
        raise RuntimeError("latest data audit did not refresh the standard data lake")

    payload: dict[str, object] = {
        "schema_version": 1,
        "family": "BTC-15M-EMA-Trend-Breakout",
        "research_identity": "BTC-15M-EMA-TB-V40-transfer-search",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_end_exclusive": DATA_END_EXCLUSIVE.isoformat(),
        "train_start": TRAIN_START.isoformat(),
        "validation_start": VALIDATION_START.isoformat(),
        "holdout_start": HOLDOUT_START.isoformat(),
        "holdout_end": HOLDOUT_END.isoformat(),
        "holdout_status": "sealed_unread",
        "kernel_path": str(common.KERNEL_PATH.relative_to(common.ROOT)),
        "kernel_sha256": common.KERNEL_SHA256,
        "data_quality_artifact": str(common.AUDIT_PATH.relative_to(common.ROOT)),
        "data_quality_sha256": common.sha256_bytes(audit_bytes),
        "data_quality_closed_bar_cutoff_exclusive": cutoff.isoformat(),
        "data_quality_last_ts": last_ts.isoformat(),
        "data_quality_blocker_count": 0,
    }
    payload["payload_sha256"] = common.payload_sha256(payload)
    return payload


def main() -> None:
    args = parse_args()
    if args.smoke:
        common.load_kernel()
        if not (
            TRAIN_START
            < VALIDATION_START
            < HOLDOUT_START
            < HOLDOUT_END
            == DATA_END_EXCLUSIVE
        ):
            raise RuntimeError("split constants are not strictly ordered")
        print("smoke PASS: split constants and kernel SHA", flush=True)
        return

    payload = build_payload()
    if common.SPLITS_PATH.exists():
        existing = common.read_verified_payload(common.SPLITS_PATH, "frozen splits")
        immutable_fields = [
            "data_end_exclusive",
            "train_start",
            "validation_start",
            "holdout_start",
            "holdout_end",
            "kernel_sha256",
            "data_quality_sha256",
        ]
        if any(existing.get(key) != payload.get(key) for key in immutable_fields):
            raise RuntimeError(
                "refusing to overwrite a different frozen split artifact"
            )
        print(
            f"frozen splits already match: {common.SPLITS_PATH}",
            flush=True,
        )
        return
    common.atomic_write_json(common.SPLITS_PATH, payload)
    print(f"wrote {common.SPLITS_PATH}", flush=True)
    print(f"payload_sha256={payload['payload_sha256']}", flush=True)


if __name__ == "__main__":
    main()
