from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from strategy_lab.data.models import DatasetKind, dataset_specs


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
class OHLCVDerivationPolicy:
    """Explicit permission to create proxy fields that are absent upstream."""

    derive_quote_volume: bool = False
    derive_vwap: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        if (self.derive_quote_volume or self.derive_vwap) and not self.reason.strip():
            raise ValueError("OHLCV derivation requires a non-empty audit reason")


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
            "quality": "derived_proxy",
            "reason": policy.reason,
        }
        flags.append("derived_vwap_proxy")

    if provenance:
        payload = json.dumps(
            {"mode": "explicit_opt_in", "fields": provenance},
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
