from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from strategy_lab.data.models import DatasetKind, dataset_specs
from strategy_lab.data.sessions import (
    OHLCVSessionPolicy,
    expected_ohlcv_session_bars,
    session_policy_metadata,
    timeframe_delta,
)


class DuplicatePolicy(StrEnum):
    ERROR = "error"
    KEEP_LAST = "keep_last"


@dataclass(frozen=True, slots=True)
class DuplicateStats:
    policy: DuplicatePolicy
    key_columns: tuple[str, ...]
    duplicate_rows: int
    duplicate_key_groups: int
    dropped_rows: int

    def to_dict(self) -> dict[str, object]:
        return {
            "policy": self.policy.value,
            "key_columns": list(self.key_columns),
            "duplicate_rows": self.duplicate_rows,
            "duplicate_key_groups": self.duplicate_key_groups,
            "dropped_rows": self.dropped_rows,
        }


@dataclass(frozen=True, slots=True)
class OHLCVAuditReport:
    rows: int
    groups: int
    start: str | None
    end: str | None
    duplicate_rows: int
    missing_bars: int
    unexpected_intervals: int
    open_rows: int
    timeframe_mismatches: int
    schema_errors: tuple[str, ...] = ()
    session_policy: str = OHLCVSessionPolicy.CONTINUOUS_24_7.value
    calendar_name: str | None = None
    expected_bars: int = 0
    session_count: int = 0
    out_of_session_rows: int = 0
    closure_mismatches: int = 0
    closure_as_of: str | None = None

    @property
    def trusted(self) -> bool:
        return not any(
            (
                self.duplicate_rows,
                self.missing_bars,
                self.unexpected_intervals,
                self.open_rows,
                self.timeframe_mismatches,
                self.out_of_session_rows,
                self.closure_mismatches,
                len(self.schema_errors),
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rows": self.rows,
            "groups": self.groups,
            "start": self.start,
            "end": self.end,
            "duplicate_rows": self.duplicate_rows,
            "missing_bars": self.missing_bars,
            "unexpected_intervals": self.unexpected_intervals,
            "open_rows": self.open_rows,
            "timeframe_mismatches": self.timeframe_mismatches,
            "schema_errors": list(self.schema_errors),
            "session_policy": self.session_policy,
            "calendar_name": self.calendar_name,
            "expected_bars": self.expected_bars,
            "session_count": self.session_count,
            "out_of_session_rows": self.out_of_session_rows,
            "closure_mismatches": self.closure_mismatches,
            "closure_as_of": self.closure_as_of,
            "trusted": self.trusted,
        }


@dataclass(frozen=True, slots=True)
class RawNormalizedOHLCVAuditReport:
    raw_rows: int
    normalized_rows: int
    missing_in_raw: int
    missing_in_normalized: int
    field_mismatches: dict[str, int]

    @property
    def trusted(self) -> bool:
        return (
            self.missing_in_raw == 0
            and self.missing_in_normalized == 0
            and not any(self.field_mismatches.values())
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "raw_rows": self.raw_rows,
            "normalized_rows": self.normalized_rows,
            "missing_in_raw": self.missing_in_raw,
            "missing_in_normalized": self.missing_in_normalized,
            "field_mismatches": self.field_mismatches,
            "trusted": self.trusted,
        }


@dataclass(frozen=True, slots=True)
class OHLCVDerivationPolicy:
    """Explicit permission to create proxy fields that are absent upstream."""

    derive_quote_volume: bool = False
    derive_vwap: bool = False
    reason: str = ""
    source_dataset_id: str = ""
    generated_at: str = ""
    code_hash: str = ""
    formula_version: str = "1.0"
    null_policy: str = "error"

    def __post_init__(self) -> None:
        if not (self.derive_quote_volume or self.derive_vwap):
            return
        required = {
            "reason": self.reason,
            "source_dataset_id": self.source_dataset_id,
            "generated_at": self.generated_at,
            "code_hash": self.code_hash,
            "formula_version": self.formula_version,
            "null_policy": self.null_policy,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"OHLCV derivation provenance is incomplete: {missing}")


def business_key_columns(kind: DatasetKind, frame: pd.DataFrame) -> tuple[str, ...]:
    if kind == DatasetKind.ASSET_METADATA:
        candidates = ("exchange", "symbol", "market_type")
    elif kind == DatasetKind.LIQUIDATIONS:
        # Several real liquidation orders can share one exchange event timestamp.
        return ()
    else:
        candidates = ("ts", "exchange", "symbol", "market_type", "timeframe")
    return tuple(column for column in candidates if column in frame.columns)


def resolve_duplicates(
    kind: DatasetKind,
    frame: pd.DataFrame,
    *,
    policy: DuplicatePolicy = DuplicatePolicy.ERROR,
    order_columns: Iterable[str] = (),
) -> tuple[pd.DataFrame, DuplicateStats]:
    keys = business_key_columns(kind, frame)
    if not keys:
        return frame.copy(), DuplicateStats(policy, keys, 0, 0, 0)

    duplicate_mask = frame.duplicated(subset=list(keys), keep=False)
    duplicate_rows = int(duplicate_mask.sum())
    duplicate_groups = (
        int(frame.loc[duplicate_mask].groupby(list(keys), dropna=False).ngroups)
        if duplicate_rows
        else 0
    )
    if duplicate_rows and policy == DuplicatePolicy.ERROR:
        raise ValueError(
            f"duplicate business keys for {kind.value}: "
            f"{duplicate_rows} rows across {duplicate_groups} key groups; keys={list(keys)}"
        )

    resolved = frame.copy()
    dropped_rows = 0
    if duplicate_rows:
        stable_order = [*keys, *(column for column in order_columns if column in resolved.columns)]
        resolved = resolved.sort_values(stable_order, kind="stable")
        before = len(resolved)
        resolved = resolved.drop_duplicates(subset=list(keys), keep="last")
        dropped_rows = before - len(resolved)
    return resolved.reset_index(drop=True), DuplicateStats(
        policy=policy,
        key_columns=keys,
        duplicate_rows=duplicate_rows,
        duplicate_key_groups=duplicate_groups,
        dropped_rows=dropped_rows,
    )


def derive_ohlcv_columns(
    frame: pd.DataFrame,
    policy: OHLCVDerivationPolicy | None,
) -> pd.DataFrame:
    derived = frame.copy()
    if policy is None:
        return derived

    provenance: dict[str, dict[str, str]] = {}
    flags: list[str] = []
    if "quote_volume" not in derived.columns and policy.derive_quote_volume:
        if not {"close", "volume"}.issubset(derived.columns):
            raise ValueError("cannot derive quote_volume without close and volume")
        derived["quote_volume"] = derived["close"] * derived["volume"]
        provenance["quote_volume"] = {
            "formula": "close * volume",
            "source_columns": "close,volume",
            "quality": "derived_proxy",
            "reason": policy.reason,
        }
        flags.append("derived_quote_volume_proxy")

    if "vwap" not in derived.columns and policy.derive_vwap:
        if not {"quote_volume", "volume"}.issubset(derived.columns):
            raise ValueError("cannot derive vwap without quote_volume and volume")
        if derived["volume"].eq(0).any():
            raise ValueError("cannot derive vwap where volume is zero")
        derived["vwap"] = derived["quote_volume"] / derived["volume"]
        provenance["vwap"] = {
            "formula": "quote_volume / volume",
            "source_columns": "quote_volume,volume",
            "quality": "derived_proxy",
            "reason": policy.reason,
        }
        flags.append("derived_vwap_proxy")

    if provenance:
        payload = json.dumps(
            {
                "mode": "explicit_opt_in",
                "formula_version": policy.formula_version,
                "source_dataset_id": policy.source_dataset_id,
                "generated_at": policy.generated_at,
                "null_policy": policy.null_policy,
                "code_hash": policy.code_hash,
                "fields": provenance,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        derived["derivation_provenance"] = payload
        new_flags = "|".join(flags)
        if "quality_flags" in derived.columns:
            existing = derived["quality_flags"].fillna("").astype("string")
            derived["quality_flags"] = existing.map(
                lambda value: f"{value}|{new_flags}".strip("|")
            )
        else:
            derived["quality_flags"] = new_flags
    return derived


def validate_frame(kind: DatasetKind, frame: pd.DataFrame) -> None:
    spec = dataset_specs()[kind]
    missing = [column for column in spec.required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns for {kind.value}: {missing}")

    required = list(spec.required_columns)
    null_counts = {
        column: int(frame[column].isna().sum())
        for column in required
        if frame[column].isna().any()
    }
    if null_counts:
        raise ValueError(f"critical nulls for {kind.value}: {null_counts}")

    if "ts" in frame.columns:
        if not isinstance(frame["ts"].dtype, pd.DatetimeTZDtype):
            raise ValueError("ts must be timezone-aware datetime64")
        if str(frame["ts"].dt.tz) != "UTC":
            raise ValueError(f"ts must use UTC timezone, got {frame['ts'].dt.tz}")

    if "source" in frame.columns:
        source = frame["source"].astype("string").str.strip().str.lower()
        invalid_source = source.isin({"", "unknown", "none", "null", "nan", "n/a"})
        if invalid_source.any():
            raise ValueError(f"source contains {int(invalid_source.sum())} unknown/empty values")

    if kind == DatasetKind.OHLCV:
        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
            "vwap",
        ]
        non_numeric = [
            column for column in numeric_columns if not is_numeric_dtype(frame[column])
        ]
        if non_numeric:
            raise ValueError(f"OHLCV columns must be numeric: {non_numeric}")
        non_finite = {
            column: int((~np.isfinite(frame[column].to_numpy(dtype=float))).sum())
            for column in numeric_columns
            if (~np.isfinite(frame[column].to_numpy(dtype=float))).any()
        }
        if non_finite:
            raise ValueError(f"non-finite OHLCV values: {non_finite}")
        invalid_ohlc = (
            (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
            | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
        )
        if invalid_ohlc.any():
            raise ValueError(f"invalid OHLC rows: {int(invalid_ohlc.sum())}")
        if frame["volume"].lt(0).any() or frame["quote_volume"].lt(0).any():
            raise ValueError("volume and quote_volume must be non-negative")
        if frame["vwap"].le(0).any():
            raise ValueError("vwap must be positive")
        trade_count = frame["trade_count"].to_numpy(dtype=float)
        if (trade_count < 0).any() or not np.equal(trade_count, np.floor(trade_count)).all():
            raise ValueError("trade_count must contain non-negative integers")
        if not is_bool_dtype(frame["is_closed"].dtype):
            raise ValueError("is_closed must have boolean dtype; unknown state is not allowed")

    keys = business_key_columns(kind, frame)
    if keys and frame.duplicated(subset=list(keys), keep=False).any():
        raise ValueError(f"duplicate business keys for {kind.value}; keys={list(keys)}")


def audit_ohlcv_frame(
    frame: pd.DataFrame,
    *,
    expected_timeframe: str | None = None,
    require_closed: bool = True,
    session_policy: OHLCVSessionPolicy | str = OHLCVSessionPolicy.CONTINUOUS_24_7,
    closure_as_of: pd.Timestamp | str | None = None,
) -> OHLCVAuditReport:
    resolved_policy = OHLCVSessionPolicy(session_policy)
    policy_metadata = session_policy_metadata(resolved_policy)
    schema_errors: list[str] = []
    try:
        validate_frame(DatasetKind.OHLCV, frame)
    except (TypeError, ValueError) as exc:
        schema_errors.append(str(exc))

    required_for_audit = {
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
    }
    if not required_for_audit.issubset(frame.columns):
        return OHLCVAuditReport(
            rows=len(frame),
            groups=0,
            start=None,
            end=None,
            duplicate_rows=0,
            missing_bars=0,
            unexpected_intervals=0,
            open_rows=0,
            timeframe_mismatches=0,
            schema_errors=tuple(schema_errors),
            session_policy=resolved_policy.value,
            calendar_name=policy_metadata["calendar"],
        )

    identity = ("ts", "exchange", "symbol", "market_type", "timeframe")
    duplicate_rows = int(frame.duplicated(subset=list(identity), keep=False).sum())
    open_rows = (
        int((~frame["is_closed"].fillna(False).astype(bool)).sum())
        if require_closed and "is_closed" in frame.columns
        else 0
    )
    expected = str(expected_timeframe).strip().lower() if expected_timeframe else None
    actual_timeframes = frame["timeframe"].astype("string").str.strip().str.lower()
    timeframe_mismatches = int(actual_timeframes.ne(expected).sum()) if expected else 0

    missing_bars = 0
    unexpected_intervals = 0
    expected_bars = 0
    session_count = 0
    out_of_session_rows = 0
    closure_mismatches = 0
    resolved_closure_as_of: pd.Timestamp | None = None
    if resolved_policy == OHLCVSessionPolicy.XNAS_REGULAR:
        resolved_closure_as_of = (
            pd.Timestamp.now(tz="UTC")
            if closure_as_of is None
            else pd.Timestamp(closure_as_of)
        )
        resolved_closure_as_of = (
            resolved_closure_as_of.tz_localize("UTC")
            if resolved_closure_as_of.tzinfo is None
            else resolved_closure_as_of.tz_convert("UTC")
        )
    group_columns = ["exchange", "symbol", "market_type", "timeframe"]
    groups = 0
    for key, group in frame.groupby(group_columns, dropna=False, sort=False):
        groups += 1
        group_timeframe = expected or str(key[-1]).strip().lower()
        try:
            interval = timeframe_delta(group_timeframe)
        except ValueError as exc:
            schema_errors.append(str(exc))
            continue
        timestamps = (
            pd.to_datetime(group["ts"], utc=True, errors="coerce")
            .dropna()
            .drop_duplicates()
            .sort_values()
        )
        if len(timestamps) < 2:
            if resolved_policy == OHLCVSessionPolicy.CONTINUOUS_24_7:
                continue
        if resolved_policy == OHLCVSessionPolicy.CONTINUOUS_24_7:
            for delta in timestamps.diff().dropna():
                if delta == interval:
                    continue
                if delta > interval and delta % interval == pd.Timedelta(0):
                    missing_bars += int(delta / interval) - 1
                else:
                    unexpected_intervals += 1
            continue

        if timestamps.empty:
            continue
        schedule = expected_ohlcv_session_bars(
            start=timestamps.min(),
            end=timestamps.max(),
            timeframe=group_timeframe,
            session_policy=resolved_policy,
        )
        expected_index = pd.DatetimeIndex(schedule["ts"])
        actual_index = pd.DatetimeIndex(timestamps)
        missing_bars += len(expected_index.difference(actual_index))
        expected_bars += len(expected_index)
        session_count += int(schedule["session"].nunique())

        parsed_group_ts = pd.to_datetime(group["ts"], utc=True, errors="coerce")
        in_session = parsed_group_ts.isin(expected_index)
        out_of_session_rows += int((~in_session).sum())
        if "is_closed" in group.columns and resolved_closure_as_of is not None:
            closure = pd.DataFrame(
                {
                    "ts": parsed_group_ts.loc[in_session],
                    "actual_closed": group.loc[in_session, "is_closed"]
                    .fillna(False)
                    .astype(bool),
                }
            ).merge(schedule[["ts", "bar_close_ts"]], on="ts", how="left")
            expected_closed = closure["bar_close_ts"].le(resolved_closure_as_of)
            closure_mismatches += int(
                closure["actual_closed"].ne(expected_closed).sum()
            )

    timestamps = pd.to_datetime(frame["ts"], utc=True, errors="coerce").dropna()
    return OHLCVAuditReport(
        rows=len(frame),
        groups=groups,
        start=timestamps.min().isoformat() if not timestamps.empty else None,
        end=timestamps.max().isoformat() if not timestamps.empty else None,
        duplicate_rows=duplicate_rows,
        missing_bars=missing_bars,
        unexpected_intervals=unexpected_intervals,
        open_rows=open_rows,
        timeframe_mismatches=timeframe_mismatches,
        schema_errors=tuple(dict.fromkeys(schema_errors)),
        session_policy=resolved_policy.value,
        calendar_name=policy_metadata["calendar"],
        expected_bars=expected_bars,
        session_count=session_count,
        out_of_session_rows=out_of_session_rows,
        closure_mismatches=closure_mismatches,
        closure_as_of=(
            resolved_closure_as_of.isoformat()
            if resolved_closure_as_of is not None
            else None
        ),
    )


def audit_raw_normalized_ohlcv(
    raw: pd.DataFrame,
    normalized: pd.DataFrame,
) -> RawNormalizedOHLCVAuditReport:
    identity = ["ts", "exchange", "symbol", "market_type", "timeframe"]
    compared_fields = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
    ]
    for label, frame in (("raw", raw), ("normalized", normalized)):
        missing = [column for column in [*identity, *compared_fields] if column not in frame]
        if missing:
            raise ValueError(f"{label} OHLCV frame missing comparison columns: {missing}")
        if frame.duplicated(subset=identity, keep=False).any():
            raise ValueError(f"{label} OHLCV frame contains duplicate identity rows")

    merged = raw[[*identity, *compared_fields]].merge(
        normalized[[*identity, *compared_fields]],
        on=identity,
        how="outer",
        suffixes=("_raw", "_normalized"),
        indicator=True,
    )
    both = merged["_merge"].eq("both")
    mismatches: dict[str, int] = {}
    for field in compared_fields:
        left = merged.loc[both, f"{field}_raw"]
        right = merged.loc[both, f"{field}_normalized"]
        if field == "is_closed":
            mismatches[field] = int(left.astype(bool).ne(right.astype(bool)).sum())
        else:
            mismatches[field] = int(
                (~np.isclose(left.astype(float), right.astype(float), rtol=0.0, atol=0.0)).sum()
            )
    return RawNormalizedOHLCVAuditReport(
        raw_rows=len(raw),
        normalized_rows=len(normalized),
        missing_in_raw=int(merged["_merge"].eq("right_only").sum()),
        missing_in_normalized=int(merged["_merge"].eq("left_only").sum()),
        field_mismatches=mismatches,
    )
