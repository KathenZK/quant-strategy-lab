#!/usr/bin/env python3
"""Accept Polygon MU 15m regular-session bars into canonical normalized OHLCV."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import (
    DataLakeLayout,
    DatasetKind,
    DuckDBWarehouse,
    MarketType,
    OHLCVDerivationPolicy,
    OHLCVSessionPolicy,
    audit_ohlcv_frame,
    audit_raw_normalized_ohlcv,
    expected_ohlcv_session_bars,
    normalize_dataset,
    session_policy_metadata,
    write_normalized_dataframe,
)
from strategy_lab.data.fs import atomic_write_text


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = ROOT / "data"
DEFAULT_AUDIT_OUTPUT = (
    ROOT / "research/mu/artifacts/mu-polygon-15m-acceptance-2026-08-06.json"
)
SOURCE = "polygon_api"
SOURCE_DATASET_ID = "polygon-mu-15m-adjusted-2025-06-17-2026-06-17"
TIMEFRAME = "15m"
IDENTITY = {
    "exchange": "nasdaq",
    "market_type": "equity",
    "symbol": "MU",
    "timeframe": TIMEFRAME,
    "source": SOURCE,
}
RAW_REQUIRED_COLUMNS = {
    "ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "transactions",
    "exchange",
    "symbol",
    "market_type",
    "timeframe",
    "source",
    "source_dataset_id",
    "adjustment",
    "session_scope",
    "quality_status",
}


def data_layout(data_root: Path) -> DataLakeLayout:
    return DataLakeLayout(
        root_dir=data_root,
        raw_dir=data_root / "raw",
        normalized_dir=data_root / "normalized",
        features_dir=data_root / "features",
        cache_dir=data_root / "cache",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(paths: list[Path], *, relative_to: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(relative_to).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def raw_source_root(data_root: Path) -> Path:
    return (
        data_root
        / "raw/ohlcv/exchange=nasdaq/market_type=equity"
        / f"timeframe={TIMEFRAME}/source={SOURCE}"
    )


def normalized_target_root(data_root: Path) -> Path:
    return (
        data_root
        / "normalized/ohlcv/exchange=nasdaq/market_type=equity"
        / f"timeframe={TIMEFRAME}"
    )


def load_raw_polygon(data_root: Path) -> tuple[pd.DataFrame, list[Path]]:
    source_root = raw_source_root(data_root)
    files = sorted(source_root.glob("date=*/symbol=mu.parquet"))
    if not files:
        raise FileNotFoundError(f"no Polygon MU raw partitions under {source_root}")
    raw = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    missing = sorted(RAW_REQUIRED_COLUMNS - set(raw.columns))
    if missing:
        raise ValueError(f"Polygon raw OHLCV is missing required source columns: {missing}")

    raw["ts"] = pd.to_datetime(raw["ts"], utc=True, errors="raise")
    for column, expected in IDENTITY.items():
        actual = raw[column].astype("string")
        matches = (
            actual.str.upper().eq(expected)
            if column == "symbol"
            else actual.str.lower().eq(expected.lower())
        )
        if not matches.all():
            values = sorted(actual.loc[~matches].dropna().unique().tolist())
            raise ValueError(f"raw {column} identity mismatch: {values}")
    if not raw["source_dataset_id"].eq(SOURCE_DATASET_ID).all():
        raise ValueError("raw source_dataset_id does not match the frozen Polygon dataset")
    if not raw["quality_status"].eq("raw_unaccepted").all():
        raise ValueError("Polygon source must remain raw_unaccepted in the raw layer")
    duplicate_rows = int(raw.duplicated("ts", keep=False).sum())
    if duplicate_rows:
        raise ValueError(f"Polygon raw OHLCV contains {duplicate_rows} duplicate rows")
    return raw.sort_values("ts").reset_index(drop=True), files


def _json_string(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def prepare_candidate(
    raw: pd.DataFrame,
    *,
    generated_at: pd.Timestamp,
    code_hash: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    schedule = expected_ohlcv_session_bars(
        start=raw["ts"].min(),
        end=raw["ts"].max(),
        timeframe=TIMEFRAME,
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
    )
    raw_index = pd.DatetimeIndex(raw["ts"])
    expected_index = pd.DatetimeIndex(schedule["ts"])
    missing = expected_index.difference(raw_index)
    if len(missing):
        sample = [timestamp.isoformat() for timestamp in missing[:10]]
        raise ValueError(
            f"Polygon regular session has {len(missing)} missing bars; sample={sample}"
        )

    regular = raw.merge(schedule, on="ts", how="inner", validate="one_to_one")
    if len(regular) != len(schedule):
        raise ValueError(
            f"regular-session row mismatch: {len(regular)} != {len(schedule)}"
        )

    transactions = pd.to_numeric(regular["transactions"], errors="raise")
    if (
        transactions.isna().any()
        or transactions.lt(0).any()
        or not np.equal(transactions, np.floor(transactions)).all()
    ):
        raise ValueError("Polygon transactions cannot map losslessly to trade_count")
    native_vwap = pd.to_numeric(regular["vwap"], errors="raise")
    if native_vwap.isna().any() or not np.isfinite(native_vwap).all():
        raise ValueError("Polygon native vwap contains null or non-finite values")

    calendar_metadata = session_policy_metadata(OHLCVSessionPolicy.XNAS_REGULAR)
    regular["trade_count"] = transactions.astype("int64")
    regular["is_closed"] = regular["bar_close_ts"].le(generated_at)
    if not regular["is_closed"].all():
        open_count = int((~regular["is_closed"]).sum())
        raise ValueError(f"candidate contains {open_count} bars not closed as of audit")
    regular["session_provenance"] = _json_string(
        {
            **calendar_metadata,
            "bar_timestamp_semantics": "UTC bar open",
            "membership_rule": "bar interval is within XNAS regular [open, close)",
            "source_session_scope": sorted(
                raw["session_scope"].astype("string").unique().tolist()
            ),
        }
    )
    regular["closure_provenance"] = _json_string(
        {
            "mode": "calendar_attested",
            "calendar": "XNAS",
            "formula": "is_closed = bar_close_ts <= audit_as_of",
            "audit_as_of": generated_at.isoformat(),
            "calendar_package": calendar_metadata["calendar_package"],
            "calendar_package_version": calendar_metadata[
                "calendar_package_version"
            ],
        }
    )
    regular["quality_status"] = "accepted"
    regular["accepted_for_strategy_evidence"] = True

    derivation_policy = OHLCVDerivationPolicy(
        derive_quote_volume=True,
        derive_vwap=False,
        reason=(
            "Polygon aggregate omitted quote volume; canonical acceptance uses the "
            "explicit close*volume proxy while retaining native Polygon vwap"
        ),
        source_dataset_id=SOURCE_DATASET_ID,
        generated_at=generated_at.isoformat(),
        code_hash=code_hash,
        formula_version="1.0",
        null_policy="error",
    )
    normalized = normalize_dataset(
        DatasetKind.OHLCV,
        regular,
        ohlcv_derivation=derivation_policy,
    )

    raw_projection = regular[
        [
            "ts",
            "exchange",
            "symbol",
            "market_type",
            "timeframe",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trade_count",
            "vwap",
            "is_closed",
            "source",
        ]
    ].copy()
    raw_projection["quote_volume"] = (
        raw_projection["close"] * raw_projection["volume"]
    )
    alignment = audit_raw_normalized_ohlcv(raw_projection, normalized)
    continuity = audit_ohlcv_frame(
        normalized,
        expected_timeframe=TIMEFRAME,
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
        closure_as_of=generated_at,
    )
    if not alignment.trusted:
        raise ValueError(f"raw/normalized alignment failed: {alignment.to_dict()}")
    if not continuity.trusted:
        raise ValueError(f"regular-session continuity failed: {continuity.to_dict()}")

    session_sizes = schedule.groupby("session").size()
    preparation_audit = {
        "raw_rows": len(raw),
        "regular_session_rows": len(normalized),
        "filtered_non_regular_rows": len(raw) - len(normalized),
        "session_count": int(schedule["session"].nunique()),
        "full_session_count": int(session_sizes.eq(26).sum()),
        "early_close_session_count": int(session_sizes.lt(26).sum()),
        "regular_start": normalized["ts"].min().isoformat(),
        "regular_end": normalized["ts"].max().isoformat(),
        "native_vwap_preserved": bool(
            np.array_equal(
                normalized["vwap"].to_numpy(),
                regular.sort_values("ts")["vwap"].to_numpy(),
            )
        ),
        "transactions_mapped_to_trade_count": bool(
            np.array_equal(
                normalized["trade_count"].to_numpy(),
                regular.sort_values("ts")["transactions"].to_numpy(),
            )
        ),
        "continuity": continuity.to_dict(),
        "raw_normalized_alignment": alignment.to_dict(),
    }
    if not preparation_audit["native_vwap_preserved"]:
        raise ValueError("native Polygon vwap changed during normalization")
    if not preparation_audit["transactions_mapped_to_trade_count"]:
        raise ValueError("transactions to trade_count mapping changed during normalization")
    return normalized, raw_projection, preparation_audit


def stage_and_commit(
    normalized: pd.DataFrame,
    raw_projection: pd.DataFrame,
    *,
    data_root: Path,
    generated_at: pd.Timestamp,
) -> dict[str, Any]:
    target_root = normalized_target_root(data_root)
    if target_root.exists():
        raise FileExistsError(
            f"canonical normalized target already exists; refusing overwrite: {target_root}"
        )

    cache_root = data_root / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=".mu-polygon-accept-", dir=cache_root)
    )
    try:
        staging_layout = data_layout(staging_root)
        paths = write_normalized_dataframe(
            normalized,
            layout=staging_layout,
            kind=DatasetKind.OHLCV,
            exchange="nasdaq",
            market_type=MarketType.EQUITY,
            symbol="MU",
            timeframe=TIMEFRAME,
        )
        staged = DuckDBWarehouse(staging_layout).load_trusted_ohlcv(
            exchange="nasdaq",
            market_type=MarketType.EQUITY,
            symbol="MU",
            timeframe=TIMEFRAME,
            session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
            closure_as_of=generated_at,
        )
        staged_alignment = audit_raw_normalized_ohlcv(raw_projection, staged)
        if not staged_alignment.trusted:
            raise ValueError(
                f"staged raw/normalized alignment failed: {staged_alignment.to_dict()}"
            )

        staged_target = normalized_target_root(staging_root)
        staged_files = sorted(staged_target.glob("date=*/symbol=mu.parquet"))
        staged_tree_hash = tree_sha256(staged_files, relative_to=staged_target)
        target_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_target, target_root)
        return {
            "action": "atomic_directory_commit",
            "target": target_root.relative_to(data_root).as_posix(),
            "files": len(paths),
            "rows": len(staged),
            "tree_sha256": staged_tree_hash,
            "round_trip_continuity": staged.attrs["ohlcv_audit"],
            "round_trip_alignment": staged_alignment.to_dict(),
        }
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def build_audit_payload(
    *,
    data_root: Path,
    raw_files: list[Path],
    generated_at: pd.Timestamp,
    code_hash: str,
    preparation: dict[str, Any],
    write_result: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = session_policy_metadata(OHLCVSessionPolicy.XNAS_REGULAR)
    return {
        "schema_version": "1.0",
        "generated_at": generated_at.isoformat(),
        "decision": "accepted" if write_result is not None else "candidate_passed",
        "accepted_for_strategy_evidence": write_result is not None,
        "market_identity": IDENTITY,
        "source_dataset_id": SOURCE_DATASET_ID,
        "data_root": str(data_root),
        "raw": {
            "quality_status": "raw_unaccepted",
            "files": len(raw_files),
            "tree_sha256": tree_sha256(
                raw_files, relative_to=raw_source_root(data_root)
            ),
            "rows": preparation["raw_rows"],
        },
        "session_policy": metadata,
        "transformation": {
            "filter": "XNAS regular session only",
            "vwap": "native Polygon vwap retained",
            "trade_count": "lossless mapping from native transactions",
            "quote_volume": "explicit OHLCVDerivationPolicy close * volume proxy",
            "is_closed": "calendar-attested against bar_close_ts and audit_as_of",
            "code_sha256": code_hash,
        },
        "preparation_audit": preparation,
        "normalized_write": write_result,
        "yahoo_isolation": {
            "quality_status": "raw_unaccepted",
            "normalized": False,
            "trade_count": "missing; not filled with zero or any proxy",
            "schema_policy_relaxed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    audit_output = args.audit_output
    if not audit_output.is_absolute():
        audit_output = ROOT / audit_output
    generated_at = pd.Timestamp(datetime.now(timezone.utc))
    code_hash = f"sha256:{sha256(Path(__file__))}"

    raw, raw_files = load_raw_polygon(data_root)
    normalized, raw_projection, preparation = prepare_candidate(
        raw,
        generated_at=generated_at,
        code_hash=code_hash,
    )
    write_result = (
        stage_and_commit(
            normalized,
            raw_projection,
            data_root=data_root,
            generated_at=generated_at,
        )
        if args.apply
        else None
    )
    payload = build_audit_payload(
        data_root=data_root,
        raw_files=raw_files,
        generated_at=generated_at,
        code_hash=code_hash,
        preparation=preparation,
        write_result=write_result,
    )
    if args.apply:
        atomic_write_text(
            audit_output,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
