#!/usr/bin/env python3
"""Runnable Binance OHLCV catalog examples. Commands match docs/data-lake-spec.md."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd

from strategy_lab.data.catalog import (
    BINANCE_PERP_1D_CACHE_FROM_15M,
    BINANCE_PERP_1H_NORMALIZED_LEGACY,
    BINANCE_PERP_4H_FROM_15M_V1,
    DatasetScope,
    inspect_dataset,
    list_registered_datasets,
    load_canonical_binance_perp_1d,
    load_trusted_dataset,
)
from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.settings import default_settings

ROOT = Path(__file__).resolve().parents[4]


def layout() -> DataLakeLayout:
    return DataLakeLayout.from_settings(default_settings())


def dump(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def cmd_list(_args: argparse.Namespace) -> int:
    rows = list_registered_datasets(layout=layout())
    slim = [
        {
            "dataset_id": row["dataset_id"],
            "purpose": row["purpose"],
            "allowed_scopes": row["allowed_scopes"],
            "status": row["status"],
            "timeframe": row["timeframe"],
            "observed_start_utc": row["observed_start_utc"],
            "observed_end_utc": row["observed_end_utc"],
            "cutoff_exclusive_utc": row["cutoff_exclusive_utc"],
            "version": row["version"],
            "quality_status": row["quality_status"],
            "manifest_sha256": row["manifest_sha256"],
            "parquet_inventory_fingerprint": row["parquet_inventory_fingerprint"],
            "input_snapshot_fingerprint": row["input_snapshot_fingerprint"],
            "known_limits": row["known_limits"],
        }
        for row in rows
    ]
    dump({"datasets": slim, "count": len(slim)})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    preview = inspect_dataset(
        args.dataset_id,
        layout=layout(),
        requested_scope=DatasetScope(args.scope) if args.scope else None,
        start=args.start,
        end=args.end,
    )
    dump(
        {
            "trusted": preview.trusted,
            "dataset_id": preview.record.dataset_id,
            "status": preview.record.status.value,
            "coverage": {key: value for key, value in preview.coverage.items() if key != "per_symbol"},
            "union_stats": preview.union_stats,
            "parquet_file_count": preview.parquet_file_count,
            "known_limits": list(preview.known_limits),
            "published_cutoff_exclusive_utc": (
                None if preview.published_manifest is None else preview.published_manifest.get("cutoff_exclusive_utc")
            ),
        }
    )
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    loaded = load_trusted_dataset(
        args.dataset_id,
        layout=layout(),
        requested_scope=DatasetScope(args.scope),
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        require_contiguous=False,
        require_closed=True,
        max_materialize_rows=args.max_materialize_rows,
    )
    dump(
        {
            "dataset_id": loaded.record.dataset_id,
            "materialized": loaded.materialized,
            "quality_status": loaded.audit.get("quality_status"),
            "rows": loaded.audit.get("rows"),
            "source_counts": loaded.source_counts,
            "coverage": {key: value for key, value in loaded.coverage.items() if key != "per_symbol"},
            "verified_file_count": len(loaded.verified_parquet_files),
            "parquet_inventory_fingerprint": loaded.manifest.get("parquet_inventory_fingerprint"),
            "dataset_coverage": loaded.verified_identity.get("dataset_coverage"),
            "frame_rows": int(len(loaded.frame)),
        }
    )
    return 0


def cmd_load_1d(args: argparse.Namespace) -> int:
    loaded = load_canonical_binance_perp_1d(
        layout=layout(),
        requested_scope=DatasetScope(args.scope),
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        require_contiguous=False,
        max_materialize_rows=args.max_materialize_rows,
    )
    dump(
        {
            "dataset_id": loaded.record.dataset_id,
            "materialized": loaded.materialized,
            "quality_status": loaded.audit.get("quality_status"),
            "rows": loaded.audit.get("rows"),
            "coverage": {key: value for key, value in loaded.coverage.items() if key != "per_symbol"},
        }
    )
    return 0


def _expect_raise(fn, match: str) -> dict[str, str]:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - example must show the real refusal
        text = str(exc)
        if match not in text:
            raise RuntimeError(f"expected {match!r} in {text!r}") from exc
        return {"rejected": True, "match": match, "error": text[:500]}
    raise RuntimeError(f"expected refusal matching {match!r}")


def cmd_reject(args: argparse.Namespace) -> int:
    lake = layout()
    if args.case == "legacy-1h-full-market":
        result = _expect_raise(
            lambda: load_trusted_dataset(
                BINANCE_PERP_1H_NORMALIZED_LEGACY,
                layout=lake,
                requested_scope=DatasetScope.FULL_MARKET,
            ),
            "cannot satisfy FULL_MARKET",
        )
    elif args.case == "cache-as-ohlcv":
        result = _expect_raise(
            lambda: load_trusted_dataset(
                BINANCE_PERP_1D_CACHE_FROM_15M,
                layout=lake,
                requested_scope=DatasetScope.PARTIAL,
            ),
            "not standard OHLCV",
        )
    elif args.case == "missing-dataset":
        result = _expect_raise(
            lambda: load_trusted_dataset(
                "binance.perp.ohlcv.does_not_exist.v1",
                layout=lake,
                requested_scope=DatasetScope.PARTIAL,
            ),
            "unknown dataset_id",
        )
    elif args.case == "bad-fingerprint":
        result = _expect_raise(
            lambda: load_trusted_dataset(
                BINANCE_PERP_4H_FROM_15M_V1,
                layout=lake,
                requested_scope=DatasetScope.PARTIAL,
                symbol="BTC/USDT:USDT",
                require_contiguous=False,
                expected_parquet_fingerprint="0" * 64,
            ),
            "fingerprint",
        )
    elif args.case == "missing-manifest":
        tmp = Path(tempfile.mkdtemp(prefix="ohlcv-missing-manifest-"))
        fake = DataLakeLayout(
            root_dir=tmp / "data",
            raw_dir=tmp / "data" / "raw",
            normalized_dir=tmp / "data" / "normalized",
            features_dir=tmp / "data" / "features",
            cache_dir=tmp / "data" / "cache",
            derived_dir=tmp / "data" / "derived",
        )
        fake.ensure_directories()
        root = fake.derived_datasets_dir / "binance_perp_4h_from_15m_v1"
        root.mkdir(parents=True)
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2026-07-01T00:00:00Z")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT:USDT"],
                "market_type": ["perp"],
                "timeframe": ["4h"],
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [1.0],
                "quote_volume": [1.0],
                "trade_count": [1],
                "vwap": [1.0],
                "is_closed": [True],
                "source": ["binance_vision_kline_monthly"],
            }
        ).to_parquet(root / "x.parquet", index=False)
        result = _expect_raise(
            lambda: load_trusted_dataset(
                BINANCE_PERP_4H_FROM_15M_V1,
                layout=fake,
                requested_scope=DatasetScope.PARTIAL,
                require_contiguous=False,
            ),
            "manifest missing",
        )
    else:
        raise SystemExit(f"unknown reject case {args.case}")
    dump({"case": args.case, **result})
    return 0


def cmd_bundle(_args: argparse.Namespace) -> int:
    payload: dict[str, object] = {}

    def capture(name: str, fn) -> None:
        payload[name] = json.loads(_capture_stdout(fn))

    capture("list", lambda: cmd_list(argparse.Namespace()))
    capture(
        "inspect_4h",
        lambda: cmd_inspect(
            argparse.Namespace(
                dataset_id=BINANCE_PERP_4H_FROM_15M_V1,
                scope=DatasetScope.FULL_MARKET.value,
                start=None,
                end=None,
            )
        ),
    )
    capture(
        "load_single_4h",
        lambda: cmd_load(
            argparse.Namespace(
                dataset_id=BINANCE_PERP_4H_FROM_15M_V1,
                scope=DatasetScope.SINGLE_SYMBOL.value,
                symbol="BTC/USDT:USDT",
                start=None,
                end="2026-08-24T08:00:00Z",
                max_materialize_rows=2_000_000,
            )
        ),
    )
    capture(
        "load_full_market_4h_window",
        lambda: cmd_load(
            argparse.Namespace(
                dataset_id=BINANCE_PERP_4H_FROM_15M_V1,
                scope=DatasetScope.FULL_MARKET.value,
                symbol=None,
                start="2026-08-01T00:00:00Z",
                end="2026-08-24T08:00:00Z",
                max_materialize_rows=0,
            )
        ),
    )
    capture(
        "load_1d",
        lambda: cmd_load_1d(
            argparse.Namespace(
                scope=DatasetScope.SINGLE_SYMBOL.value,
                symbol="BTC/USDT:USDT",
                start=None,
                end="2026-08-25T00:00:00Z",
                max_materialize_rows=0,
            )
        ),
    )
    for case in (
        "legacy-1h-full-market",
        "cache-as-ohlcv",
        "missing-dataset",
        "bad-fingerprint",
        "missing-manifest",
    ):
        capture(f"reject_{case.replace('-', '_')}", lambda case=case: cmd_reject(argparse.Namespace(case=case)))
    dump(payload)
    return 0


def _capture_stdout(fn) -> str:
    from io import StringIO
    from contextlib import redirect_stdout

    buffer = StringIO()
    with redirect_stdout(buffer):
        code = fn()
    if code:
        raise RuntimeError(f"command failed with {code}")
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")
    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--dataset-id", required=True)
    inspect_p.add_argument("--scope")
    inspect_p.add_argument("--start")
    inspect_p.add_argument("--end")

    load_p = sub.add_parser("load")
    load_p.add_argument("--dataset-id", required=True)
    load_p.add_argument("--scope", required=True)
    load_p.add_argument("--symbol")
    load_p.add_argument("--start")
    load_p.add_argument("--end")
    load_p.add_argument("--max-materialize-rows", type=int, default=2_000_000)

    load1d = sub.add_parser("load-1d")
    load1d.add_argument("--scope", default="PARTIAL")
    load1d.add_argument("--symbol")
    load1d.add_argument("--start")
    load1d.add_argument("--end")
    load1d.add_argument("--max-materialize-rows", type=int, default=0)

    reject_p = sub.add_parser("reject")
    reject_p.add_argument(
        "--case",
        required=True,
        choices=[
            "legacy-1h-full-market",
            "cache-as-ohlcv",
            "missing-dataset",
            "bad-fingerprint",
            "missing-manifest",
        ],
    )
    sub.add_parser("bundle")

    args = parser.parse_args()
    commands = {
        "list": cmd_list,
        "inspect": cmd_inspect,
        "load": cmd_load,
        "load-1d": cmd_load_1d,
        "reject": cmd_reject,
        "bundle": cmd_bundle,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
