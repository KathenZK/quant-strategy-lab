from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-ma7-root-hazard-timing"
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
DEFAULT_OUTPUT_DIR = FAMILY_DIR / "artifacts/p1_development_2026-08-10"
SHARED_KERNEL_PATH = (
    ROOT / "research/_shared-kernels/binance-ma7-root-data/v1/engine.py"
)
EXPECTED_SHARED_KERNEL_SHA256 = (
    "3d7c6d295568b96627a4b6aa4efad0fc7fdc8a53503f9f4fa55922c7069bfa3d"
)
if hashlib.sha256(SHARED_KERNEL_PATH.read_bytes()).hexdigest() != (
    EXPECTED_SHARED_KERNEL_SHA256
):
    raise RuntimeError("Shared Binance MA7 root-data kernel SHA256 mismatch")
SHARED_SPEC = importlib.util.spec_from_file_location(
    "binance_ma7_root_data_v1_rht",
    SHARED_KERNEL_PATH,
)
if SHARED_SPEC is None or SHARED_SPEC.loader is None:
    raise ImportError(f"Cannot load shared kernel: {SHARED_KERNEL_PATH}")
shared = importlib.util.module_from_spec(SHARED_SPEC)
sys.modules[SHARED_SPEC.name] = shared
SHARED_SPEC.loader.exec_module(shared)

ASSETS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
}
EXPECTED_FULL_CROSS_COUNTS = {
    "BTC": 456,
    "ETH": 448,
    "BNB": 378,
    "SOL": 348,
    "TRX": 423,
}
DEVELOPMENT_END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")
ROOT_CUTOFF_EXCLUSIVE = pd.Timestamp("2025-05-20T00:00:00Z")
ROOT_ADMISSION_HOURS = 120
MAX_HOLD_HOURS = 120
OUTER_EMBARGO_HOURS = 120
FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
MAIN_SLIPPAGE = 0.0008
STRESS_SLIPPAGE = 0.0012
LEVERAGE = 0.25
SEED = 20260810
BOOTSTRAP_SAMPLES = 10_000
C_GRID = (0.03, 0.10, 0.30, 1.00)
THRESHOLD_GRID = (0.50, 0.55, 0.60, 0.65)

FULL_FEATURES = (
    "is_short",
    "age_frac",
    "cross_distance_atr",
    "cross_slope_1_atr",
    "cross_slope_2_atr",
    "aligned_root_displacement_atr",
    "aligned_return_1h_atr",
    "aligned_return_6h_atr",
    "aligned_return_24h_atr",
    "signed_efficiency_6h",
    "signed_efficiency_24h",
    "giveback_from_root_mfe_atr",
    "root_mae_atr",
    "realized_vol_24h_atr",
    "aligned_funding_carry_24h",
)
CONTROL_FEATURES = FULL_FEATURES[:5]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build pre-HYPE hourly MA7-root landmarks and run frozen "
            "root-grouped nested LOAO/time first-hit diagnostics."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--capacity-only", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _hourly_open_at(
    hourly: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> float | None:
    timestamps = pd.DatetimeIndex(hourly["ts"])
    index = int(timestamps.searchsorted(timestamp, side="left"))
    if index >= len(hourly) or pd.Timestamp(hourly.at[index, "ts"]) != timestamp:
        return None
    return float(hourly.at[index, "open"])


def first_daily_recross_boundary(
    daily: pd.DataFrame,
    *,
    cross_index: int,
    side: int,
) -> pd.Timestamp | None:
    for index in range(cross_index + 1, len(daily)):
        close = float(daily.at[index, "close"])
        ma = float(daily.at[index, "sma7"])
        if not all(math.isfinite(value) for value in (close, ma)):
            return pd.Timestamp(daily.at[index, "ts"]) + pd.Timedelta(days=1)
        if side * (close - ma) <= 0.0:
            return pd.Timestamp(daily.at[index, "ts"]) + pd.Timedelta(days=1)
    return None


def hourly_trade_outcome(
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    recross_ts: pd.Timestamp | None,
    admission_end: pd.Timestamp,
    side: int,
    slippage: float,
    include_funding: bool,
    lag_hours: int = 0,
) -> dict[str, Any] | None:
    delayed_entry = entry_ts + pd.Timedelta(hours=lag_hours)
    if delayed_entry >= admission_end:
        return None
    if recross_ts is not None and delayed_entry >= recross_ts:
        return None
    timeout = delayed_entry + pd.Timedelta(hours=MAX_HOLD_HOURS)
    exit_ts = min(recross_ts, timeout) if recross_ts is not None else timeout
    if exit_ts >= DEVELOPMENT_END_EXCLUSIVE:
        return None
    entry_reference = _hourly_open_at(hourly, delayed_entry)
    exit_reference = _hourly_open_at(hourly, exit_ts)
    if entry_reference is None or exit_reference is None:
        return None
    entry_fill = entry_reference * (1.0 + side * slippage)
    funding_component = 0.0
    funding_events = 0
    if include_funding:
        funding_component, funding_events = shared.funding_return(
            funding,
            entry_ts=delayed_entry,
            exit_ts=exit_ts,
            side=side,
            entry_fill=entry_fill,
        )
    result = shared.levered_trade_return(
        side=side,
        entry_reference=entry_reference,
        exit_reference=exit_reference,
        slippage=slippage,
        fee_rate=FEE_RATE,
        leverage=LEVERAGE,
        funding_component=funding_component,
    )
    return {
        "entry_ts": delayed_entry,
        "exit_ts": exit_ts,
        "exit_reason": (
            "ma7_recross"
            if recross_ts is not None and recross_ts <= timeout
            else "timeout_120h"
        ),
        "funding_events": funding_events,
        **result,
    }


def _window_displacement_and_efficiency(
    hourly: pd.DataFrame,
    *,
    decision_index: int,
    hours: int,
    side: int,
    atr: float,
) -> tuple[float, float]:
    sample = hourly.iloc[decision_index - hours : decision_index]
    first_open = float(sample.iloc[0]["open"])
    last_close = float(sample.iloc[-1]["close"])
    path = np.concatenate(
        [
            np.asarray([first_open], dtype="float64"),
            sample["close"].to_numpy(dtype="float64"),
        ]
    )
    length = float(np.abs(np.diff(path)).sum())
    displacement = side * (last_close - first_open) / atr
    efficiency = (
        side * (last_close - first_open) / length if length > 0.0 else 0.0
    )
    return float(displacement), float(efficiency)


def landmark_features(
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    decision_ts: pd.Timestamp,
    root_start: pd.Timestamp,
    age_hours: int,
    side: int,
    cross_atr: float,
    cross_distance: float,
    cross_slope_1: float,
    cross_slope_2: float,
) -> dict[str, float] | None:
    timestamps = pd.DatetimeIndex(hourly["ts"])
    decision_index = int(timestamps.searchsorted(decision_ts, side="left"))
    root_index = int(timestamps.searchsorted(root_start, side="left"))
    if (
        decision_index >= len(hourly)
        or pd.Timestamp(hourly.at[decision_index, "ts"]) != decision_ts
        or root_index >= len(hourly)
        or pd.Timestamp(hourly.at[root_index, "ts"]) != root_start
        or decision_index < 24
    ):
        return None
    current_open = float(hourly.at[decision_index, "open"])
    root_open = float(hourly.at[root_index, "open"])
    disp1, _ = _window_displacement_and_efficiency(
        hourly,
        decision_index=decision_index,
        hours=1,
        side=side,
        atr=cross_atr,
    )
    disp6, efficiency6 = _window_displacement_and_efficiency(
        hourly,
        decision_index=decision_index,
        hours=6,
        side=side,
        atr=cross_atr,
    )
    disp24, efficiency24 = _window_displacement_and_efficiency(
        hourly,
        decision_index=decision_index,
        hours=24,
        side=side,
        atr=cross_atr,
    )
    root_window = hourly.iloc[root_index:decision_index]
    if root_window.empty:
        root_mfe = 0.0
        root_mae = 0.0
    elif side > 0:
        root_mfe = max(
            0.0,
            (float(root_window["high"].max()) - root_open) / cross_atr,
        )
        root_mae = max(
            0.0,
            (root_open - float(root_window["low"].min())) / cross_atr,
        )
    else:
        root_mfe = max(
            0.0,
            (root_open - float(root_window["low"].min())) / cross_atr,
        )
        root_mae = max(
            0.0,
            (float(root_window["high"].max()) - root_open) / cross_atr,
        )
    current_displacement = side * (current_open - root_open) / cross_atr
    giveback = max(0.0, root_mfe - current_displacement)
    day = hourly.iloc[decision_index - 24 : decision_index]
    path = np.concatenate(
        [
            np.asarray([float(day.iloc[0]["open"])], dtype="float64"),
            day["close"].to_numpy(dtype="float64"),
        ]
    )
    realized_vol = float(np.sqrt(np.square(np.diff(path) / cross_atr).sum()))
    funding_ts = pd.DatetimeIndex(funding["ts"])
    left = int(
        funding_ts.searchsorted(
            decision_ts - pd.Timedelta(hours=24), side="left"
        )
    )
    right = int(funding_ts.searchsorted(decision_ts, side="left"))
    carry = float(
        -side
        * funding.iloc[left:right]["funding_rate"].to_numpy(dtype="float64").sum()
    )
    values = {
        "is_short": float(side < 0),
        "age_frac": float(age_hours / ROOT_ADMISSION_HOURS),
        "cross_distance_atr": cross_distance,
        "cross_slope_1_atr": cross_slope_1,
        "cross_slope_2_atr": cross_slope_2,
        "aligned_root_displacement_atr": float(current_displacement),
        "aligned_return_1h_atr": disp1,
        "aligned_return_6h_atr": disp6,
        "aligned_return_24h_atr": disp24,
        "signed_efficiency_6h": efficiency6,
        "signed_efficiency_24h": efficiency24,
        "giveback_from_root_mfe_atr": float(giveback),
        "root_mae_atr": float(root_mae),
        "realized_vol_24h_atr": realized_vol,
        "aligned_funding_carry_24h": carry,
    }
    if tuple(values) != FULL_FEATURES:
        raise RuntimeError("Hourly feature contract mismatch")
    if not all(math.isfinite(value) for value in values.values()):
        return None
    return values


def build_roots_and_panel(
    dailies: dict[str, pd.DataFrame],
    hourlies: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    inventory: dict[str, Any] = {}
    for asset in ASSETS:
        daily = dailies[asset]
        hourly = hourlies[asset]
        funding = fundings[asset]
        counts: Counter[str] = Counter()
        full_crosses = [
            index
            for index in range(20, len(daily))
            if shared.raw_cross(daily, index)
        ]
        if len(full_crosses) != EXPECTED_FULL_CROSS_COUNTS[asset]:
            raise RuntimeError(
                f"{asset} raw-cross inventory changed: "
                f"{len(full_crosses)} != {EXPECTED_FULL_CROSS_COUNTS[asset]}"
            )
        counts["full_raw_crosses"] = len(full_crosses)
        for local_number, cross_index in enumerate(full_crosses, start=1):
            cross_ts = pd.Timestamp(daily.at[cross_index, "ts"])
            if cross_ts >= ROOT_CUTOFF_EXCLUSIVE:
                counts["post_root_cutoff"] += 1
                continue
            side = int(shared.raw_cross(daily, cross_index))
            cross_atr = float(daily.at[cross_index, "atr7"])
            ma = float(daily.at[cross_index, "sma7"])
            close = float(daily.at[cross_index, "close"])
            previous_ma_1 = float(daily.at[cross_index - 1, "sma7"])
            previous_ma_2 = float(daily.at[cross_index - 2, "sma7"])
            if not all(
                math.isfinite(value)
                for value in (
                    cross_atr,
                    ma,
                    close,
                    previous_ma_1,
                    previous_ma_2,
                )
            ) or cross_atr <= 0.0:
                counts["invalid_cross_state"] += 1
                continue
            root_start = cross_ts + pd.Timedelta(days=1)
            if root_start < pd.Timestamp(
                funding["funding_nominal_ts"].min()
            ).floor("1h"):
                counts["before_funding_history"] += 1
                continue
            recross_ts = first_daily_recross_boundary(
                daily,
                cross_index=cross_index,
                side=side,
            )
            admission_end = root_start + pd.Timedelta(
                hours=ROOT_ADMISSION_HOURS
            )
            if recross_ts is not None:
                admission_end = min(admission_end, recross_ts)
            candidate_times = pd.date_range(
                root_start,
                admission_end,
                freq="1h",
                inclusive="left",
            )
            root_id = (
                f"{asset}-{cross_ts.strftime('%Y%m%d')}-"
                f"{'L' if side > 0 else 'S'}-{local_number:04d}"
            )
            cross_distance = side * (close - ma) / cross_atr
            cross_slope_1 = side * (ma - previous_ma_1) / cross_atr
            cross_slope_2 = side * (ma - previous_ma_2) / cross_atr
            root_rows: list[dict[str, Any]] = []
            information_end = root_start
            for age_hours, decision_ts in enumerate(candidate_times):
                decision_ts = pd.Timestamp(decision_ts)
                features = landmark_features(
                    hourly,
                    funding,
                    decision_ts=decision_ts,
                    root_start=root_start,
                    age_hours=age_hours,
                    side=side,
                    cross_atr=cross_atr,
                    cross_distance=cross_distance,
                    cross_slope_1=cross_slope_1,
                    cross_slope_2=cross_slope_2,
                )
                if features is None:
                    root_rows = []
                    counts["incomplete_feature_root"] += 1
                    break
                base = hourly_trade_outcome(
                    hourly,
                    funding,
                    entry_ts=decision_ts,
                    recross_ts=recross_ts,
                    admission_end=admission_end,
                    side=side,
                    slippage=BASE_SLIPPAGE,
                    include_funding=True,
                )
                main = hourly_trade_outcome(
                    hourly,
                    funding,
                    entry_ts=decision_ts,
                    recross_ts=recross_ts,
                    admission_end=admission_end,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=True,
                )
                stress = hourly_trade_outcome(
                    hourly,
                    funding,
                    entry_ts=decision_ts,
                    recross_ts=recross_ts,
                    admission_end=admission_end,
                    side=side,
                    slippage=STRESS_SLIPPAGE,
                    include_funding=True,
                )
                funding_off = hourly_trade_outcome(
                    hourly,
                    funding,
                    entry_ts=decision_ts,
                    recross_ts=recross_ts,
                    admission_end=admission_end,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=False,
                )
                lag1 = hourly_trade_outcome(
                    hourly,
                    funding,
                    entry_ts=decision_ts,
                    recross_ts=recross_ts,
                    admission_end=admission_end,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=True,
                    lag_hours=1,
                )
                lag6 = hourly_trade_outcome(
                    hourly,
                    funding,
                    entry_ts=decision_ts,
                    recross_ts=recross_ts,
                    admission_end=admission_end,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=True,
                    lag_hours=6,
                )
                if any(item is None for item in (base, main, stress, funding_off)):
                    root_rows = []
                    counts["incomplete_label_root"] += 1
                    break
                assert base is not None
                assert main is not None
                assert stress is not None
                assert funding_off is not None
                outcome_ends = [
                    pd.Timestamp(item["exit_ts"])
                    for item in (base, main, stress, funding_off, lag1, lag6)
                    if item is not None
                ]
                information_end = max(information_end, *outcome_ends)
                root_rows.append(
                    {
                        "root_id": root_id,
                        "asset": asset,
                        "side": side,
                        "side_name": "long" if side > 0 else "short",
                        "cross_ts": cross_ts,
                        "root_start": root_start,
                        "decision_ts": decision_ts,
                        "age_hours": age_hours,
                        "entry_ts": main["entry_ts"],
                        "exit_ts": main["exit_ts"],
                        "exit_reason": main["exit_reason"],
                        "z_4bps": float(base["direct_net_return"]),
                        "z_8bps": float(main["direct_net_return"]),
                        "z_12bps": float(stress["direct_net_return"]),
                        "z_funding_off": float(
                            funding_off["direct_net_return"]
                        ),
                        "z_lag1h": (
                            float(lag1["direct_net_return"])
                            if lag1 is not None
                            else np.nan
                        ),
                        "z_lag6h": (
                            float(lag6["direct_net_return"])
                            if lag6 is not None
                            else np.nan
                        ),
                        "label": int(float(main["direct_net_return"]) > 0.0),
                        **features,
                    }
                )
            if not root_rows:
                continue
            row_weight = 1.0 / len(root_rows)
            for row in root_rows:
                row["row_weight"] = row_weight
                row["root_information_end"] = information_end
            first = root_rows[0]
            roots.append(
                {
                    "root_id": root_id,
                    "asset": asset,
                    "side": side,
                    "side_name": first["side_name"],
                    "cross_ts": cross_ts,
                    "root_start": root_start,
                    "admission_end": admission_end,
                    "recross_ts": recross_ts,
                    "root_information_end": information_end,
                    "candidate_rows": len(root_rows),
                    "k0_z_4bps": first["z_4bps"],
                    "k0_z_8bps": first["z_8bps"],
                    "k0_z_12bps": first["z_12bps"],
                    "k0_z_funding_off": first["z_funding_off"],
                }
            )
            rows.extend(root_rows)
            counts["eligible_roots"] += 1
            counts["candidate_rows"] += len(root_rows)
            counts["long_roots" if side > 0 else "short_roots"] += 1
        inventory[asset] = dict(sorted(counts.items()))
    root_frame = (
        pd.DataFrame(roots)
        .sort_values(["root_start", "asset", "root_id"])
        .reset_index(drop=True)
    )
    panel = (
        pd.DataFrame(rows)
        .sort_values(["decision_ts", "asset", "root_id"])
        .reset_index(drop=True)
    )
    if root_frame.empty or panel.empty:
        raise RuntimeError("No eligible roots or person-period rows")
    root_frame.insert(0, "root_index", np.arange(len(root_frame), dtype="int64"))
    panel.insert(0, "row_id", np.arange(len(panel), dtype="int64"))
    if root_frame["root_id"].duplicated().any():
        raise RuntimeError("Duplicate root ids")
    if panel[list(FULL_FEATURES)].isna().any().any():
        raise RuntimeError("Person-period features contain missing values")
    weight_sums = panel.groupby("root_id")["row_weight"].sum()
    if not np.allclose(weight_sums.to_numpy(), 1.0, rtol=0.0, atol=1e-12):
        raise RuntimeError("Root row weights do not sum to one")
    return root_frame, panel, inventory


def _hourly_cache(
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, np.ndarray]:
    hourly_ns = (
        pd.to_datetime(hourly["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    funding_ns = (
        pd.to_datetime(funding["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    rates = funding["funding_rate"].to_numpy(dtype="float64")
    rate_mark = rates * funding["mark_price"].to_numpy(dtype="float64")
    return {
        "hourly_ns": hourly_ns,
        "open": hourly["open"].to_numpy(dtype="float64"),
        "high": hourly["high"].to_numpy(dtype="float64"),
        "low": hourly["low"].to_numpy(dtype="float64"),
        "close": hourly["close"].to_numpy(dtype="float64"),
        "funding_ns": funding_ns,
        "funding_rate_prefix": np.concatenate(
            [np.asarray([0.0]), np.cumsum(rates)]
        ),
        "funding_rate_mark_prefix": np.concatenate(
            [np.asarray([0.0]), np.cumsum(rate_mark)]
        ),
    }


def _prefix_sum(
    prefix: np.ndarray,
    *,
    left: int,
    right: int,
) -> float:
    return float(prefix[right] - prefix[left])


def _fast_outcome(
    cache: dict[str, np.ndarray],
    *,
    entry_index: int,
    recross_index: int | None,
    admission_end_index: int,
    side: int,
    slippage: float,
    include_funding: bool,
    lag_hours: int = 0,
) -> dict[str, Any] | None:
    delayed_entry_index = entry_index + lag_hours
    if delayed_entry_index >= admission_end_index:
        return None
    if recross_index is not None and delayed_entry_index >= recross_index:
        return None
    timeout_index = delayed_entry_index + MAX_HOLD_HOURS
    exit_index = (
        min(recross_index, timeout_index)
        if recross_index is not None
        else timeout_index
    )
    hourly_ns = cache["hourly_ns"]
    if exit_index >= len(hourly_ns):
        return None
    entry_reference = float(cache["open"][delayed_entry_index])
    exit_reference = float(cache["open"][exit_index])
    entry_fill = entry_reference * (1.0 + side * slippage)
    funding_component = 0.0
    funding_events = 0
    if include_funding:
        funding_ns = cache["funding_ns"]
        left = int(
            np.searchsorted(
                funding_ns,
                hourly_ns[delayed_entry_index],
                side="right",
            )
        )
        right = int(
            np.searchsorted(funding_ns, hourly_ns[exit_index], side="left")
        )
        numerator = _prefix_sum(
            cache["funding_rate_mark_prefix"],
            left=left,
            right=right,
        )
        funding_component = -side * numerator / entry_fill
        funding_events = right - left
    result = shared.levered_trade_return(
        side=side,
        entry_reference=entry_reference,
        exit_reference=exit_reference,
        slippage=slippage,
        fee_rate=FEE_RATE,
        leverage=LEVERAGE,
        funding_component=funding_component,
    )
    return {
        "entry_index": delayed_entry_index,
        "exit_index": exit_index,
        "entry_ts": pd.Timestamp(hourly_ns[delayed_entry_index], tz="UTC"),
        "exit_ts": pd.Timestamp(hourly_ns[exit_index], tz="UTC"),
        "exit_reason": (
            "ma7_recross"
            if recross_index is not None and recross_index <= timeout_index
            else "timeout_120h"
        ),
        "funding_events": funding_events,
        **result,
    }


def _fast_window_values(
    cache: dict[str, np.ndarray],
    *,
    decision_index: int,
    hours: int,
    side: int,
    atr: float,
) -> tuple[float, float]:
    first = decision_index - hours
    first_open = float(cache["open"][first])
    last_close = float(cache["close"][decision_index - 1])
    closes = cache["close"][first:decision_index]
    length = abs(float(closes[0]) - first_open)
    if len(closes) > 1:
        length += float(np.abs(np.diff(closes)).sum())
    displacement = side * (last_close - first_open) / atr
    efficiency = (
        side * (last_close - first_open) / length if length > 0.0 else 0.0
    )
    return float(displacement), float(efficiency)


def _fast_landmark_features(
    cache: dict[str, np.ndarray],
    *,
    decision_index: int,
    root_start_index: int,
    age_hours: int,
    side: int,
    cross_atr: float,
    cross_distance: float,
    cross_slope_1: float,
    cross_slope_2: float,
    root_mfe: float,
    root_mae: float,
) -> dict[str, float]:
    current_open = float(cache["open"][decision_index])
    root_open = float(cache["open"][root_start_index])
    disp1, _ = _fast_window_values(
        cache,
        decision_index=decision_index,
        hours=1,
        side=side,
        atr=cross_atr,
    )
    disp6, efficiency6 = _fast_window_values(
        cache,
        decision_index=decision_index,
        hours=6,
        side=side,
        atr=cross_atr,
    )
    disp24, efficiency24 = _fast_window_values(
        cache,
        decision_index=decision_index,
        hours=24,
        side=side,
        atr=cross_atr,
    )
    current_displacement = side * (current_open - root_open) / cross_atr
    first = decision_index - 24
    path = np.concatenate(
        [
            np.asarray([float(cache["open"][first])]),
            cache["close"][first:decision_index],
        ]
    )
    realized_vol = float(np.sqrt(np.square(np.diff(path) / cross_atr).sum()))
    decision_ns = int(cache["hourly_ns"][decision_index])
    funding_ns = cache["funding_ns"]
    left = int(
        np.searchsorted(
            funding_ns,
            decision_ns - 24 * 60 * 60 * 1_000_000_000,
            side="left",
        )
    )
    right = int(np.searchsorted(funding_ns, decision_ns, side="left"))
    carry = -side * _prefix_sum(
        cache["funding_rate_prefix"],
        left=left,
        right=right,
    )
    return {
        "is_short": float(side < 0),
        "age_frac": float(age_hours / ROOT_ADMISSION_HOURS),
        "cross_distance_atr": cross_distance,
        "cross_slope_1_atr": cross_slope_1,
        "cross_slope_2_atr": cross_slope_2,
        "aligned_root_displacement_atr": float(current_displacement),
        "aligned_return_1h_atr": disp1,
        "aligned_return_6h_atr": disp6,
        "aligned_return_24h_atr": disp24,
        "signed_efficiency_6h": efficiency6,
        "signed_efficiency_24h": efficiency24,
        "giveback_from_root_mfe_atr": float(
            max(0.0, root_mfe - current_displacement)
        ),
        "root_mae_atr": float(root_mae),
        "realized_vol_24h_atr": realized_vol,
        "aligned_funding_carry_24h": float(carry),
    }


def build_roots_and_panel_fast(
    dailies: dict[str, pd.DataFrame],
    hourlies: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    inventory: dict[str, Any] = {}
    for asset in ASSETS:
        daily = dailies[asset]
        funding = fundings[asset]
        cache = _hourly_cache(hourlies[asset], funding)
        hourly_ns = cache["hourly_ns"]
        counts: Counter[str] = Counter()
        full_crosses = [
            index
            for index in range(20, len(daily))
            if shared.raw_cross(daily, index)
        ]
        if len(full_crosses) != EXPECTED_FULL_CROSS_COUNTS[asset]:
            raise RuntimeError(
                f"{asset} raw-cross inventory changed: "
                f"{len(full_crosses)} != {EXPECTED_FULL_CROSS_COUNTS[asset]}"
            )
        counts["full_raw_crosses"] = len(full_crosses)
        funding_start = pd.Timestamp(
            funding["funding_nominal_ts"].min()
        ).floor("1h")
        for local_number, cross_index in enumerate(full_crosses, start=1):
            cross_ts = pd.Timestamp(daily.at[cross_index, "ts"])
            if cross_ts >= ROOT_CUTOFF_EXCLUSIVE:
                counts["post_root_cutoff"] += 1
                continue
            side = int(shared.raw_cross(daily, cross_index))
            cross_atr = float(daily.at[cross_index, "atr7"])
            ma = float(daily.at[cross_index, "sma7"])
            close = float(daily.at[cross_index, "close"])
            previous_ma_1 = float(daily.at[cross_index - 1, "sma7"])
            previous_ma_2 = float(daily.at[cross_index - 2, "sma7"])
            if not all(
                math.isfinite(value)
                for value in (
                    cross_atr,
                    ma,
                    close,
                    previous_ma_1,
                    previous_ma_2,
                )
            ) or cross_atr <= 0.0:
                counts["invalid_cross_state"] += 1
                continue
            root_start = cross_ts + pd.Timedelta(days=1)
            if root_start < funding_start:
                counts["before_funding_history"] += 1
                continue
            root_start_ns = root_start.value
            root_start_index = int(
                np.searchsorted(hourly_ns, root_start_ns, side="left")
            )
            if (
                root_start_index >= len(hourly_ns)
                or int(hourly_ns[root_start_index]) != root_start_ns
                or root_start_index < 24
            ):
                counts["missing_root_start"] += 1
                continue
            recross_ts = first_daily_recross_boundary(
                daily,
                cross_index=cross_index,
                side=side,
            )
            recross_index: int | None = None
            if recross_ts is not None:
                recross_index = int(
                    np.searchsorted(hourly_ns, recross_ts.value, side="left")
                )
                if (
                    recross_index >= len(hourly_ns)
                    or int(hourly_ns[recross_index]) != recross_ts.value
                ):
                    recross_index = None
            admission_end_index = root_start_index + ROOT_ADMISSION_HOURS
            if recross_index is not None:
                admission_end_index = min(admission_end_index, recross_index)
            if admission_end_index <= root_start_index:
                counts["empty_admission"] += 1
                continue
            root_id = (
                f"{asset}-{cross_ts.strftime('%Y%m%d')}-"
                f"{'L' if side > 0 else 'S'}-{local_number:04d}"
            )
            cross_distance = side * (close - ma) / cross_atr
            cross_slope_1 = side * (ma - previous_ma_1) / cross_atr
            cross_slope_2 = side * (ma - previous_ma_2) / cross_atr
            root_rows: list[dict[str, Any]] = []
            information_end = root_start
            max_high = float("-inf")
            min_low = float("inf")
            root_open = float(cache["open"][root_start_index])
            for decision_index in range(root_start_index, admission_end_index):
                age_hours = decision_index - root_start_index
                if age_hours > 0:
                    completed_index = decision_index - 1
                    max_high = max(
                        max_high, float(cache["high"][completed_index])
                    )
                    min_low = min(
                        min_low, float(cache["low"][completed_index])
                    )
                if age_hours == 0:
                    root_mfe = 0.0
                    root_mae = 0.0
                elif side > 0:
                    root_mfe = max(0.0, (max_high - root_open) / cross_atr)
                    root_mae = max(0.0, (root_open - min_low) / cross_atr)
                else:
                    root_mfe = max(0.0, (root_open - min_low) / cross_atr)
                    root_mae = max(0.0, (max_high - root_open) / cross_atr)
                features = _fast_landmark_features(
                    cache,
                    decision_index=decision_index,
                    root_start_index=root_start_index,
                    age_hours=age_hours,
                    side=side,
                    cross_atr=cross_atr,
                    cross_distance=cross_distance,
                    cross_slope_1=cross_slope_1,
                    cross_slope_2=cross_slope_2,
                    root_mfe=root_mfe,
                    root_mae=root_mae,
                )
                base = _fast_outcome(
                    cache,
                    entry_index=decision_index,
                    recross_index=recross_index,
                    admission_end_index=admission_end_index,
                    side=side,
                    slippage=BASE_SLIPPAGE,
                    include_funding=True,
                )
                main = _fast_outcome(
                    cache,
                    entry_index=decision_index,
                    recross_index=recross_index,
                    admission_end_index=admission_end_index,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=True,
                )
                stress = _fast_outcome(
                    cache,
                    entry_index=decision_index,
                    recross_index=recross_index,
                    admission_end_index=admission_end_index,
                    side=side,
                    slippage=STRESS_SLIPPAGE,
                    include_funding=True,
                )
                funding_off = _fast_outcome(
                    cache,
                    entry_index=decision_index,
                    recross_index=recross_index,
                    admission_end_index=admission_end_index,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=False,
                )
                lag1 = _fast_outcome(
                    cache,
                    entry_index=decision_index,
                    recross_index=recross_index,
                    admission_end_index=admission_end_index,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=True,
                    lag_hours=1,
                )
                lag6 = _fast_outcome(
                    cache,
                    entry_index=decision_index,
                    recross_index=recross_index,
                    admission_end_index=admission_end_index,
                    side=side,
                    slippage=MAIN_SLIPPAGE,
                    include_funding=True,
                    lag_hours=6,
                )
                if any(item is None for item in (base, main, stress, funding_off)):
                    root_rows = []
                    counts["incomplete_label_root"] += 1
                    break
                assert base is not None
                assert main is not None
                assert stress is not None
                assert funding_off is not None
                outcome_ends = [
                    pd.Timestamp(item["exit_ts"])
                    for item in (base, main, stress, funding_off, lag1, lag6)
                    if item is not None
                ]
                information_end = max(information_end, *outcome_ends)
                decision_ts = pd.Timestamp(
                    hourly_ns[decision_index], tz="UTC"
                )
                root_rows.append(
                    {
                        "root_id": root_id,
                        "asset": asset,
                        "side": side,
                        "side_name": "long" if side > 0 else "short",
                        "cross_ts": cross_ts,
                        "root_start": root_start,
                        "decision_ts": decision_ts,
                        "age_hours": age_hours,
                        "entry_ts": main["entry_ts"],
                        "exit_ts": main["exit_ts"],
                        "exit_reason": main["exit_reason"],
                        "z_4bps": float(base["direct_net_return"]),
                        "z_8bps": float(main["direct_net_return"]),
                        "z_12bps": float(stress["direct_net_return"]),
                        "z_funding_off": float(
                            funding_off["direct_net_return"]
                        ),
                        "z_lag1h": (
                            float(lag1["direct_net_return"])
                            if lag1 is not None
                            else np.nan
                        ),
                        "z_lag6h": (
                            float(lag6["direct_net_return"])
                            if lag6 is not None
                            else np.nan
                        ),
                        "label": int(float(main["direct_net_return"]) > 0.0),
                        **features,
                    }
                )
            if not root_rows:
                continue
            row_weight = 1.0 / len(root_rows)
            for row in root_rows:
                row["row_weight"] = row_weight
                row["root_information_end"] = information_end
            first = root_rows[0]
            admission_end = pd.Timestamp(
                hourly_ns[admission_end_index], tz="UTC"
            )
            roots.append(
                {
                    "root_id": root_id,
                    "asset": asset,
                    "side": side,
                    "side_name": first["side_name"],
                    "cross_ts": cross_ts,
                    "root_start": root_start,
                    "admission_end": admission_end,
                    "recross_ts": recross_ts,
                    "root_information_end": information_end,
                    "candidate_rows": len(root_rows),
                    "k0_z_4bps": first["z_4bps"],
                    "k0_z_8bps": first["z_8bps"],
                    "k0_z_12bps": first["z_12bps"],
                    "k0_z_funding_off": first["z_funding_off"],
                }
            )
            rows.extend(root_rows)
            counts["eligible_roots"] += 1
            counts["candidate_rows"] += len(root_rows)
            counts["long_roots" if side > 0 else "short_roots"] += 1
        inventory[asset] = dict(sorted(counts.items()))
    root_frame = (
        pd.DataFrame(roots)
        .sort_values(["root_start", "asset", "root_id"])
        .reset_index(drop=True)
    )
    panel = (
        pd.DataFrame(rows)
        .sort_values(["decision_ts", "asset", "root_id"])
        .reset_index(drop=True)
    )
    if root_frame.empty or panel.empty:
        raise RuntimeError("No eligible roots or person-period rows")
    root_frame.insert(0, "root_index", np.arange(len(root_frame), dtype="int64"))
    panel.insert(0, "row_id", np.arange(len(panel), dtype="int64"))
    weight_sums = panel.groupby("root_id")["row_weight"].sum()
    if not np.allclose(weight_sums.to_numpy(), 1.0, rtol=0.0, atol=1e-12):
        raise RuntimeError("Root row weights do not sum to one")
    if not np.isfinite(panel[list(FULL_FEATURES)].to_numpy()).all():
        raise RuntimeError("Person-period features contain non-finite values")
    return root_frame, panel, inventory


def frame_identity_sha256(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    *,
    sort_columns: tuple[str, ...],
) -> str:
    ordered = frame.sort_values(list(sort_columns)).reset_index(drop=True)
    digest = hashlib.sha256()
    for column in columns:
        series = ordered[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            values = (
                pd.to_datetime(series, utc=True)
                .to_numpy(dtype="datetime64[ns]")
                .astype("int64")
            )
            digest.update(np.ascontiguousarray(values).tobytes())
        elif pd.api.types.is_numeric_dtype(series):
            values = series.to_numpy(dtype="float64")
            digest.update(np.ascontiguousarray(values).tobytes())
        else:
            digest.update("\0".join(series.astype(str)).encode("utf-8"))
    return digest.hexdigest()


def root_time_blocks(
    roots: pd.DataFrame,
    *,
    initial_fraction: float,
    blocks: int,
) -> list[tuple[int, pd.Timestamp, pd.Timestamp]]:
    dates = pd.DatetimeIndex(sorted(roots["root_start"].drop_duplicates()))
    initial = int(math.floor(len(dates) * initial_fraction))
    if initial < 20 or len(dates) - initial < blocks:
        raise RuntimeError("Insufficient root dates for time folds")
    result: list[tuple[int, pd.Timestamp, pd.Timestamp]] = []
    for fold, block in enumerate(np.array_split(dates[initial:], blocks), start=1):
        if not len(block):
            raise RuntimeError("Empty root time block")
        result.append((fold, pd.Timestamp(block[0]), pd.Timestamp(block[-1])))
    return result


def split_roots_for_block(
    roots: pd.DataFrame,
    *,
    first_test: pd.Timestamp,
    last_test: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    purge_boundary = first_test - pd.Timedelta(hours=OUTER_EMBARGO_HOURS)
    train = roots.loc[
        roots["root_start"].lt(first_test)
        & roots["root_information_end"].lt(purge_boundary)
    ].copy()
    test = roots.loc[
        roots["root_start"].ge(first_test)
        & roots["root_start"].le(last_test)
    ].copy()
    return train, test


def rows_for_roots(panel: pd.DataFrame, roots: pd.DataFrame) -> pd.DataFrame:
    return panel.loc[panel["root_id"].isin(set(roots["root_id"]))].copy()


def fit_model(
    rows: pd.DataFrame,
    *,
    features: tuple[str, ...],
    c_value: float,
) -> Pipeline:
    if rows["label"].nunique() < 2:
        raise RuntimeError("Training rows contain one label")
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=c_value,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=SEED,
                ),
            ),
        ]
    )
    weights = rows["row_weight"].to_numpy(dtype="float64")
    model.fit(
        rows[list(features)],
        rows["label"].astype(int),
        scale__sample_weight=weights,
        model__sample_weight=weights,
    )
    return model


def predict_probability(
    model: Pipeline,
    rows: pd.DataFrame,
    *,
    features: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(
        model.predict_proba(rows[list(features)])[:, 1],
        dtype="float64",
    )


def first_hits(
    scored_rows: pd.DataFrame,
    *,
    threshold_column: str = "selected_threshold",
    threshold_delta: float = 0.0,
) -> pd.DataFrame:
    eligible = scored_rows.loc[
        scored_rows["probability"].ge(
            scored_rows[threshold_column] + threshold_delta
        )
    ].copy()
    if eligible.empty:
        return eligible
    return (
        eligible.sort_values(["decision_ts", "root_id"])
        .groupby("root_id", sort=False, as_index=False)
        .first()
    )


def select_inner(
    panel: pd.DataFrame,
    roots: pd.DataFrame,
    *,
    features: tuple[str, ...],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    blocks = root_time_blocks(roots, initial_fraction=0.50, blocks=3)
    predictions_by_c: dict[float, pd.DataFrame] = {}
    for c_value in C_GRID:
        prediction_frames: list[pd.DataFrame] = []
        for fold, first_test, last_test in blocks:
            train_roots, test_roots = split_roots_for_block(
                roots,
                first_test=first_test,
                last_test=last_test,
            )
            train_rows = rows_for_roots(panel, train_roots)
            test_rows = rows_for_roots(panel, test_roots)
            if (
                train_rows.empty
                or test_rows.empty
                or train_rows["label"].nunique() < 2
            ):
                prediction_frames = []
                break
            model = fit_model(
                train_rows,
                features=features,
                c_value=c_value,
            )
            prediction = test_rows.copy()
            prediction["inner_fold"] = fold
            prediction["probability"] = predict_probability(
                model,
                test_rows,
                features=features,
            )
            prediction_frames.append(prediction)
        if prediction_frames:
            predictions_by_c[c_value] = pd.concat(
                prediction_frames, ignore_index=True
            )
    scores: list[dict[str, Any]] = []
    for c_value, predictions in predictions_by_c.items():
        for threshold in THRESHOLD_GRID:
            work = predictions.copy()
            work["selected_threshold"] = threshold
            selected = first_hits(work)
            fold_metrics = {
                fold: shared.return_metrics(
                    selected.loc[selected["inner_fold"].eq(fold)],
                    "z_8bps",
                )
                for fold in range(1, 4)
            }
            side_counts = {
                "long": int(selected["side"].gt(0).sum()),
                "short": int(selected["side"].lt(0).sum()),
            }
            overall = shared.return_metrics(selected, "z_8bps")
            eligible = bool(
                len(selected) >= 60
                and all(
                    int(metric["events"]) >= 15
                    and float(metric["mean"]) > 0.0
                    for metric in fold_metrics.values()
                )
                and side_counts["long"] >= 15
                and side_counts["short"] >= 15
                and float(overall["profit_factor"]) >= 1.05
            )
            scores.append(
                {
                    "C": c_value,
                    "threshold": threshold,
                    "eligible": eligible,
                    "selected_roots": int(len(selected)),
                    "side_counts": side_counts,
                    "worst_fold_mean": (
                        min(
                            float(metric["mean"])
                            for metric in fold_metrics.values()
                        )
                        if eligible
                        else None
                    ),
                    "overall": overall,
                    "fold_metrics": fold_metrics,
                }
            )
    eligible_scores = [score for score in scores if score["eligible"]]
    if not eligible_scores:
        return None, scores
    choice = max(
        eligible_scores,
        key=lambda score: (
            float(score["worst_fold_mean"]),
            float(score["overall"]["mean"]),
            float(score["overall"]["profit_factor"]),
            float(score["threshold"]),
            -float(score["C"]),
        ),
    )
    return {
        "C": float(choice["C"]),
        "threshold": float(choice["threshold"]),
    }, scores


def root_decisions(
    test_roots: pd.DataFrame,
    *,
    held_asset: str,
    outer_fold: int,
    variant_id: str,
    choice: dict[str, Any] | None,
    scored_rows: pd.DataFrame | None,
) -> pd.DataFrame:
    base = test_roots[
        [
            "root_id",
            "asset",
            "side",
            "side_name",
            "cross_ts",
            "root_start",
            "root_information_end",
            "k0_z_4bps",
            "k0_z_8bps",
            "k0_z_12bps",
            "k0_z_funding_off",
        ]
    ].copy()
    base["held_asset"] = held_asset
    base["outer_fold"] = outer_fold
    base["variant_id"] = variant_id
    base["no_selection"] = choice is None
    base["selected"] = False
    for column in (
        "decision_ts",
        "entry_ts",
        "exit_ts",
        "probability",
        "z_4bps",
        "z_8bps",
        "z_12bps",
        "z_funding_off",
        "z_lag1h",
        "z_lag6h",
    ):
        base[column] = np.nan
    if choice is not None and scored_rows is not None:
        selected = first_hits(scored_rows)
        selected_columns = selected[
            [
                "root_id",
                "decision_ts",
                "entry_ts",
                "exit_ts",
                "probability",
                "z_4bps",
                "z_8bps",
                "z_12bps",
                "z_funding_off",
                "z_lag1h",
                "z_lag6h",
            ]
        ].copy()
        base = base.drop(
            columns=[
                "decision_ts",
                "entry_ts",
                "exit_ts",
                "probability",
                "z_4bps",
                "z_8bps",
                "z_12bps",
                "z_funding_off",
                "z_lag1h",
                "z_lag6h",
            ]
        ).merge(selected_columns, on="root_id", how="left", validate="one_to_one")
        base["selected"] = base["decision_ts"].notna()
    base["selected_C"] = np.nan if choice is None else float(choice["C"])
    base["selected_threshold"] = (
        np.nan if choice is None else float(choice["threshold"])
    )
    for outcome in (
        "z_4bps",
        "z_8bps",
        "z_12bps",
        "z_funding_off",
        "z_lag1h",
        "z_lag6h",
    ):
        base[f"utility_{outcome}"] = np.where(
            base["selected"],
            base[outcome].fillna(0.0),
            0.0,
        )
    return base


def run_variant_oof(
    panel: pd.DataFrame,
    roots: pd.DataFrame,
    *,
    features: tuple[str, ...],
    variant_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    blocks = root_time_blocks(roots, initial_fraction=0.40, blocks=4)
    row_scores: list[pd.DataFrame] = []
    decisions: list[pd.DataFrame] = []
    reports: list[dict[str, Any]] = []
    for held_asset in ASSETS:
        for fold, first_test, last_test in blocks:
            base_train, base_test = split_roots_for_block(
                roots,
                first_test=first_test,
                last_test=last_test,
            )
            train_roots = base_train.loc[
                base_train["asset"].ne(held_asset)
            ].copy()
            test_roots = base_test.loc[
                base_test["asset"].eq(held_asset)
            ].copy()
            train_rows = rows_for_roots(panel, train_roots)
            test_rows = rows_for_roots(panel, test_roots)
            if train_rows.empty or test_rows.empty:
                raise RuntimeError(
                    f"Invalid outer fold {variant_id} {held_asset}-{fold}"
                )
            choice, inner_scores = select_inner(
                panel,
                train_roots,
                features=features,
            )
            scored: pd.DataFrame | None = None
            if choice is not None:
                model = fit_model(
                    train_rows,
                    features=features,
                    c_value=float(choice["C"]),
                )
                scored = test_rows.copy()
                scored["variant_id"] = variant_id
                scored["held_asset"] = held_asset
                scored["outer_fold"] = fold
                scored["selected_C"] = float(choice["C"])
                scored["selected_threshold"] = float(choice["threshold"])
                scored["probability"] = predict_probability(
                    model,
                    test_rows,
                    features=features,
                )
                row_scores.append(scored)
            fold_decisions = root_decisions(
                test_roots,
                held_asset=held_asset,
                outer_fold=fold,
                variant_id=variant_id,
                choice=choice,
                scored_rows=scored,
            )
            decisions.append(fold_decisions)
            reports.append(
                {
                    "variant_id": variant_id,
                    "held_asset": held_asset,
                    "outer_fold": fold,
                    "train_roots": int(len(train_roots)),
                    "train_rows": int(len(train_rows)),
                    "test_roots": int(len(test_roots)),
                    "test_rows": int(len(test_rows)),
                    "test_start": test_roots["root_start"].min(),
                    "test_end": test_roots["root_start"].max(),
                    "choice": choice,
                    "no_selection": choice is None,
                    "selected_roots": int(fold_decisions["selected"].sum()),
                    "inner_scores": inner_scores,
                }
            )
    scored_frame = (
        pd.concat(row_scores, ignore_index=True)
        if row_scores
        else pd.DataFrame()
    )
    return scored_frame, pd.concat(decisions, ignore_index=True), reports


def cluster_bootstrap(
    frame: pd.DataFrame,
    *,
    value_column: str,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "samples": samples,
            "clusters": 0,
            "positive_probability": 0.0,
            "quantiles": {"2.5%": 0.0, "50%": 0.0, "97.5%": 0.0},
        }
    work = frame.loc[frame[value_column].notna()].copy()
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    work["block_90d"] = (
        (pd.to_datetime(work["root_start"], utc=True) - epoch)
        // pd.Timedelta(days=90)
    ).astype("int64")
    clusters = [
        group[value_column].to_numpy(dtype="float64")
        for _, group in work.groupby(["asset", "block_90d"], sort=True)
    ]
    rng = np.random.default_rng(SEED)
    outcomes = np.empty(samples, dtype="float64")
    for index in range(samples):
        choices = rng.integers(0, len(clusters), size=len(clusters))
        sample = np.concatenate([clusters[item] for item in choices])
        outcomes[index] = float(np.mean(sample))
    return {
        "samples": samples,
        "seed": SEED,
        "clusters": int(len(clusters)),
        "positive_probability": float(np.mean(outcomes > 0.0)),
        "quantiles": {
            "2.5%": float(np.quantile(outcomes, 0.025)),
            "50%": float(np.quantile(outcomes, 0.50)),
            "97.5%": float(np.quantile(outcomes, 0.975)),
        },
    }


def root_ranking_summary(scored_rows: pd.DataFrame) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if scored_rows.empty:
        return {
            "eligible_roots": 0,
            "median_spearman": None,
            "positive_asset_count": 0,
            "per_asset": {},
        }
    for root_id, group in scored_rows.groupby("root_id", sort=False):
        if (
            len(group) < 12
            or group["probability"].nunique() < 2
            or group["z_8bps"].nunique() < 2
        ):
            continue
        correlation = float(
            group["probability"].corr(group["z_8bps"], method="spearman")
        )
        if math.isfinite(correlation):
            records.append(
                {
                    "root_id": root_id,
                    "asset": str(group.iloc[0]["asset"]),
                    "spearman": correlation,
                }
            )
    ranking = pd.DataFrame(records)
    if ranking.empty:
        return {
            "eligible_roots": 0,
            "median_spearman": None,
            "positive_asset_count": 0,
            "per_asset": {},
        }
    per_asset = {
        asset: {
            "roots": int(len(group)),
            "median_spearman": float(group["spearman"].median()),
        }
        for asset, group in ranking.groupby("asset", sort=True)
    }
    positive_assets = sum(
        float(item["median_spearman"]) > 0.0 for item in per_asset.values()
    )
    return {
        "eligible_roots": int(len(ranking)),
        "median_spearman": float(ranking["spearman"].median()),
        "positive_asset_count": int(positive_assets),
        "per_asset": per_asset,
    }


def choice_mode(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    choices = [
        (float(report["choice"]["C"]), float(report["choice"]["threshold"]))
        for report in reports
        if report["choice"] is not None
    ]
    if not choices:
        return None
    counts = Counter(choices)
    selected = max(
        counts,
        key=lambda choice: (counts[choice], choice[1], -choice[0]),
    )
    return {
        "C": selected[0],
        "threshold": selected[1],
        "count": int(counts[selected]),
        "eligible_outer_folds": int(len(choices)),
        "distribution": [
            {"C": key[0], "threshold": key[1], "count": int(value)}
            for key, value in sorted(
                counts.items(),
                key=lambda item: (-item[1], -item[0][1], item[0][0]),
            )
        ],
    }


def threshold_sensitivity(
    scored_rows: pd.DataFrame,
    *,
    delta: float,
) -> dict[str, Any]:
    selected_frames: list[pd.DataFrame] = []
    for (_, _), group in scored_rows.groupby(
        ["held_asset", "outer_fold"], sort=True
    ):
        hits = first_hits(group, threshold_delta=delta)
        selected_frames.append(hits)
    selected = (
        pd.concat(selected_frames, ignore_index=True)
        if selected_frames
        else pd.DataFrame()
    )
    return {
        "threshold_delta": delta,
        "selected_roots": int(len(selected)),
        "metrics": shared.return_metrics(selected, "z_8bps"),
    }


def recent_slices(selected: pd.DataFrame) -> dict[str, Any]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=182),
        "1y": pd.Timedelta(days=365),
    }
    return {
        name: shared.return_metrics(
            selected.loc[
                pd.to_datetime(selected["entry_ts"], utc=True).ge(
                    DEVELOPMENT_END_EXCLUSIVE - window
                )
            ],
            "z_8bps",
        )
        for name, window in windows.items()
    }


def summarize_development(
    roots: pd.DataFrame,
    main_scores: pd.DataFrame,
    main_decisions: pd.DataFrame,
    control_decisions: pd.DataFrame,
    main_reports: list[dict[str, Any]],
    control_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = main_decisions.loc[main_decisions["selected"]].copy()
    main_metrics = shared.return_metrics(selected, "z_8bps")
    variants = {
        column: shared.return_metrics(selected, column)
        for column in (
            "z_4bps",
            "z_8bps",
            "z_12bps",
            "z_funding_off",
            "z_lag1h",
            "z_lag6h",
        )
    }
    per_asset: dict[str, Any] = {}
    positive_assets = 0
    dual_improved_assets = 0
    for asset in ASSETS:
        asset_selected = selected.loc[selected["asset"].eq(asset)].copy()
        selected_metrics = shared.return_metrics(asset_selected, "z_8bps")
        immediate = asset_selected.copy()
        immediate["entry_ts"] = immediate["root_start"]
        immediate["immediate_z8"] = immediate["k0_z_8bps"]
        immediate_metrics = shared.return_metrics(immediate, "immediate_z8")
        positive = float(selected_metrics["mean"]) > 0.0
        dual = bool(
            float(selected_metrics["compound"])
            > float(immediate_metrics["compound"])
            and float(selected_metrics["event_sequence_mdd"])
            > float(immediate_metrics["event_sequence_mdd"])
        )
        positive_assets += int(positive)
        dual_improved_assets += int(dual)
        per_asset[asset] = {
            "selected": selected_metrics,
            "immediate_k0_same_roots": immediate_metrics,
            "positive_mean": positive,
            "dual_improved": dual,
        }
    fold_metrics: dict[str, Any] = {}
    positive_folds = 0
    for (asset, fold), frame in main_decisions.groupby(
        ["held_asset", "outer_fold"], sort=True
    ):
        metrics = shared.return_metrics(
            frame.loc[frame["selected"]],
            "z_8bps",
        )
        positive = int(metrics["events"]) > 0 and float(metrics["mean"]) > 0.0
        positive_folds += int(positive)
        fold_metrics[f"{asset}-{int(fold)}"] = {
            **metrics,
            "positive_mean": positive,
            "no_selection": bool(frame["no_selection"].all()),
        }
    side_counts = {
        "long": int(selected["side"].gt(0).sum()),
        "short": int(selected["side"].lt(0).sum()),
    }
    per_asset_counts = {
        asset: int(selected["asset"].eq(asset).sum()) for asset in ASSETS
    }
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    block_count = (
        int(
            (
                (pd.to_datetime(selected["root_start"], utc=True) - epoch)
                // pd.Timedelta(days=90)
            ).nunique()
        )
        if not selected.empty
        else 0
    )
    bootstrap = cluster_bootstrap(selected, value_column="z_8bps")
    paired = selected.copy()
    paired["timing_delta_z8"] = paired["z_8bps"] - paired["k0_z_8bps"]
    paired_bootstrap = cluster_bootstrap(
        paired,
        value_column="timing_delta_z8",
    )
    ranking = root_ranking_summary(main_scores)
    control = control_decisions[
        ["root_id", "held_asset", "outer_fold", "utility_z_8bps"]
    ].rename(columns={"utility_z_8bps": "control_utility"})
    utility = main_decisions.merge(
        control,
        on=["root_id", "held_asset", "outer_fold"],
        how="left",
        validate="one_to_one",
    )
    utility["control_utility"] = utility["control_utility"].fillna(0.0)
    utility["full_minus_control"] = (
        utility["utility_z_8bps"] - utility["control_utility"]
    )
    control_bootstrap = cluster_bootstrap(
        utility,
        value_column="full_minus_control",
    )
    lag1_executable = int(selected["z_lag1h"].notna().sum())
    lag1_rate = (
        float(lag1_executable / len(selected)) if len(selected) else 0.0
    )
    root_counts = roots["asset"].value_counts().to_dict()
    capacity_gate = bool(
        len(roots) >= 1_800
        and all(int(root_counts.get(asset, 0)) >= 300 for asset in ASSETS)
    )
    gate_checks = {
        "root_capacity": capacity_gate,
        "oof_trade_coverage": bool(
            len(selected) >= 150
            and all(count >= 20 for count in per_asset_counts.values())
            and side_counts["long"] >= 50
            and side_counts["short"] >= 50
        ),
        "time_block_coverage": bool(block_count >= 12),
        "main_economics": bool(
            float(main_metrics["mean"]) > 0.0
            and float(main_metrics["profit_factor"]) >= 1.15
        ),
        "positive_assets": bool(positive_assets >= 4),
        "positive_outer_folds": bool(positive_folds >= 15),
        "within_root_ranking": bool(
            ranking["median_spearman"] is not None
            and float(ranking["median_spearman"]) > 0.05
            and int(ranking["positive_asset_count"]) >= 4
        ),
        "cluster_bootstrap": bool(
            float(bootstrap["positive_probability"]) >= 0.90
        ),
        "beats_immediate_k0": bool(
            len(paired) > 0
            and float(paired["timing_delta_z8"].mean()) > 0.0
            and float(paired_bootstrap["positive_probability"]) >= 0.90
        ),
        "per_asset_dual_improvement": bool(dual_improved_assets >= 3),
        "beats_static_control": bool(
            float(control_bootstrap["positive_probability"]) >= 0.90
        ),
        "stress_12bps": bool(
            float(variants["z_12bps"]["mean"]) > 0.0
            and float(variants["z_12bps"]["profit_factor"]) >= 1.05
        ),
        "stress_funding_off": bool(
            float(variants["z_funding_off"]["mean"]) > 0.0
            and float(variants["z_funding_off"]["profit_factor"]) >= 1.05
        ),
        "stress_lag1h": bool(
            lag1_rate >= 0.90
            and (
                float(selected["z_lag1h"].fillna(0.0).mean()) > 0.0
                if len(selected)
                else False
            )
            and float(variants["z_lag1h"]["profit_factor"]) >= 1.05
        ),
    }
    return {
        "eligible_roots": int(len(roots)),
        "oof_first_hit_roots": int(len(selected)),
        "side_counts": side_counts,
        "per_asset_selected_counts": per_asset_counts,
        "time_block_count_90d": block_count,
        "main": main_metrics,
        "variants": variants,
        "lag1h_executable_rate": lag1_rate,
        "per_asset": per_asset,
        "positive_asset_count": positive_assets,
        "dual_improved_asset_count": dual_improved_assets,
        "folds": fold_metrics,
        "positive_outer_fold_count": positive_folds,
        "ranking": ranking,
        "bootstrap": bootstrap,
        "paired_immediate": {
            "roots": int(len(paired)),
            "mean_delta_z8": (
                float(paired["timing_delta_z8"].mean())
                if len(paired)
                else 0.0
            ),
            "bootstrap": paired_bootstrap,
        },
        "static_control": {
            "mean_full_utility": float(utility["utility_z_8bps"].mean()),
            "mean_control_utility": float(utility["control_utility"].mean()),
            "mean_delta": float(utility["full_minus_control"].mean()),
            "bootstrap": control_bootstrap,
        },
        "threshold_sensitivity": {
            "minus_0.05": threshold_sensitivity(
                main_scores, delta=-0.05
            ),
            "plus_0.05": threshold_sensitivity(
                main_scores, delta=0.05
            ),
        },
        "recent_slices": recent_slices(selected),
        "main_final_choice": choice_mode(main_reports),
        "control_final_choice": choice_mode(control_reports),
        "gate_checks": gate_checks,
        "development_gate_pass": bool(all(gate_checks.values())),
    }


def frozen_model_state(
    panel: pd.DataFrame,
    choice: dict[str, Any],
    *,
    panel_sha256: str,
    root_sha256: str,
    quality: dict[str, Any],
) -> dict[str, Any]:
    model = fit_model(
        panel,
        features=FULL_FEATURES,
        c_value=float(choice["C"]),
    )
    scaler = model.named_steps["scale"]
    estimator = model.named_steps["model"]
    state: dict[str, Any] = {
        "schema_version": "binance-1h-ma7-rht-model-v1",
        "created_at_utc": datetime.now(UTC),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "root_cutoff_exclusive": ROOT_CUTOFF_EXCLUSIVE,
        "shared_kernel_sha256": EXPECTED_SHARED_KERNEL_SHA256,
        "features": list(FULL_FEATURES),
        "C": float(choice["C"]),
        "threshold": float(choice["threshold"]),
        "train_rows": int(len(panel)),
        "train_roots": int(panel["root_id"].nunique()),
        "panel_sha256": panel_sha256,
        "root_sha256": root_sha256,
        "input_sha256": {
            asset: item["input_sha256"] for asset, item in quality.items()
        },
        "scaler_mean": {
            feature: float(value)
            for feature, value in zip(
                FULL_FEATURES, scaler.mean_, strict=True
            )
        },
        "scaler_scale": {
            feature: float(value)
            for feature, value in zip(
                FULL_FEATURES, scaler.scale_, strict=True
            )
        },
        "coefficients": {
            feature: float(value)
            for feature, value in zip(
                FULL_FEATURES, estimator.coef_[0], strict=True
            )
        },
        "intercept": float(estimator.intercept_[0]),
    }
    canonical = json.dumps(
        json_ready(state), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    state["model_state_sha256"] = hashlib.sha256(canonical).hexdigest()
    return state


def build_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    dailies: dict[str, pd.DataFrame] = {}
    hourlies: dict[str, pd.DataFrame] = {}
    fundings: dict[str, pd.DataFrame] = {}
    quality: dict[str, Any] = {}
    for asset, slug in ASSETS.items():
        paths = shared.feature_paths(FEATURE_DIR, slug)
        if any("hype" in path.name.lower() for path in paths.values()):
            raise RuntimeError("HYPE path rejected before read")
        daily, hourly, funding, asset_quality = shared.load_asset_inputs(
            FEATURE_DIR,
            asset=asset,
            slug=slug,
            end_exclusive=DEVELOPMENT_END_EXCLUSIVE,
        )
        dailies[asset] = daily
        hourlies[asset] = hourly
        fundings[asset] = funding
        quality[asset] = asset_quality
    roots, panel, inventory = build_roots_and_panel_fast(
        dailies, hourlies, fundings
    )
    root_sha = frame_identity_sha256(
        roots,
        (
            "root_id",
            "asset",
            "side",
            "cross_ts",
            "root_start",
            "admission_end",
            "recross_ts",
            "root_information_end",
            "candidate_rows",
            "k0_z_8bps",
        ),
        sort_columns=("root_start", "asset", "root_id"),
    )
    panel_sha = frame_identity_sha256(
        panel,
        (
            "root_id",
            "asset",
            "side",
            "decision_ts",
            "entry_ts",
            "exit_ts",
            "z_4bps",
            "z_8bps",
            "z_12bps",
            "z_funding_off",
            "z_lag1h",
            "z_lag6h",
            "label",
            "row_weight",
            *FULL_FEATURES,
        ),
        sort_columns=("decision_ts", "asset", "root_id"),
    )
    capacity = {
        "schema_version": "binance-1h-ma7-rht-p0-v1",
        "generated_at_utc": datetime.now(UTC),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "root_cutoff_exclusive": ROOT_CUTOFF_EXCLUSIVE,
        "assets": list(ASSETS),
        "hype_rows_consumed": 0,
        "hype_files_opened": 0,
        "full_raw_cross_inventory": EXPECTED_FULL_CROSS_COUNTS,
        "eligible_roots": int(len(roots)),
        "person_period_rows": int(len(panel)),
        "long_roots": int(roots["side"].gt(0).sum()),
        "short_roots": int(roots["side"].lt(0).sum()),
        "positive_landmark_rate_8bps": float(panel["label"].mean()),
        "per_asset_inventory": inventory,
        "root_identity_sha256": root_sha,
        "panel_identity_sha256": panel_sha,
        "shared_kernel": {
            "path": str(SHARED_KERNEL_PATH.relative_to(ROOT)),
            "sha256": EXPECTED_SHARED_KERNEL_SHA256,
        },
        "input_quality": quality,
    }
    return roots, panel, capacity


def build_payload() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    dict[str, Any] | None,
]:
    roots, panel, capacity = build_data()
    main_scores, main_decisions, main_reports = run_variant_oof(
        panel,
        roots,
        features=FULL_FEATURES,
        variant_id="full",
    )
    control_scores, control_decisions, control_reports = run_variant_oof(
        panel,
        roots,
        features=CONTROL_FEATURES,
        variant_id="static_control",
    )
    summary = summarize_development(
        roots,
        main_scores,
        main_decisions,
        control_decisions,
        main_reports,
        control_reports,
    )
    report = {
        "schema_version": "binance-1h-ma7-rht-p1-v1",
        "generated_at_utc": datetime.now(UTC),
        "contract": (
            "specs/binance-1h-ma7-rht-p0-p1-contract-2026-08-10.md"
        ),
        "hype_data_loaded": False,
        "shared_kernel": capacity["shared_kernel"],
        "features": {
            "full": list(FULL_FEATURES),
            "static_control": list(CONTROL_FEATURES),
        },
        "model_grid": {
            "C": list(C_GRID),
            "threshold": list(THRESHOLD_GRID),
        },
        "cost_model": {
            "fee_per_fill": FEE_RATE,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "main_slippage_per_fill": MAIN_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "leverage": LEVERAGE,
            "funding": "actual event timestamp/rate/mark",
        },
        "main_outer_reports": main_reports,
        "control_outer_reports": control_reports,
        "summary": summary,
    }
    all_scores = pd.concat(
        [main_scores, control_scores],
        ignore_index=True,
    )
    all_decisions = pd.concat(
        [main_decisions, control_decisions],
        ignore_index=True,
    )
    frozen: dict[str, Any] | None = None
    final_choice = summary["main_final_choice"]
    if summary["development_gate_pass"] and final_choice is not None:
        frozen = frozen_model_state(
            panel,
            final_choice,
            panel_sha256=capacity["panel_identity_sha256"],
            root_sha256=capacity["root_identity_sha256"],
            quality=capacity["input_quality"],
        )
    return (
        roots,
        panel,
        all_scores,
        all_decisions,
        {"capacity": capacity, "report": report},
        frozen,
    )


def write_capacity_outputs(
    output_dir: Path,
    roots: pd.DataFrame,
    panel: pd.DataFrame,
    capacity: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "roots": output_dir / "p0_roots.parquet",
        "panel": output_dir / "p0_person_period_panel.parquet",
        "capacity": output_dir / "p0_data_capacity.json",
    }
    atomic_write_parquet(paths["roots"], roots)
    atomic_write_parquet(paths["panel"], panel)
    atomic_write_json(paths["capacity"], capacity)
    return paths


def write_outputs(
    output_dir: Path,
    roots: pd.DataFrame,
    panel: pd.DataFrame,
    scores: pd.DataFrame,
    decisions: pd.DataFrame,
    payload: dict[str, Any],
    frozen: dict[str, Any] | None,
) -> dict[str, str]:
    paths = write_capacity_outputs(
        output_dir,
        roots,
        panel,
        payload["capacity"],
    )
    paths.update(
        {
            "oof_row_scores": output_dir / "p1_oof_row_scores.parquet",
            "oof_root_decisions": (
                output_dir / "p1_oof_root_decisions.parquet"
            ),
            "report": output_dir / "p1_report.json",
            "summary": output_dir / "p1_summary.json",
        }
    )
    atomic_write_parquet(paths["oof_row_scores"], scores)
    atomic_write_parquet(paths["oof_root_decisions"], decisions)
    atomic_write_json(paths["report"], payload["report"])
    atomic_write_json(paths["summary"], payload["report"]["summary"])
    if frozen is not None:
        paths["frozen_model"] = output_dir / "p1_frozen_model.json"
        atomic_write_json(paths["frozen_model"], frozen)
    hashes = {name: shared.sha256_path(path) for name, path in paths.items()}
    manifest_path = output_dir / "manifest.json"
    atomic_write_json(
        manifest_path,
        {
            "schema_version": "binance-1h-ma7-rht-manifest-v1",
            "generated_at_utc": datetime.now(UTC),
            "files": {
                name: {"path": path.name, "sha256": hashes[name]}
                for name, path in paths.items()
            },
        },
    )
    manifest_sha = shared.sha256_path(manifest_path)
    (output_dir / "manifest.sha256").write_text(
        f"{manifest_sha}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    hashes["manifest"] = manifest_sha
    return hashes


def run_self_test() -> None:
    daily = pd.DataFrame(
        {
            "close": [9.0, 10.1, 10.0, 9.9],
            "sma7": [10.0, 10.0, 10.0, 10.0],
        }
    )
    if shared.raw_cross(daily, 1) != 1:
        raise AssertionError("Soft long root missing")
    if shared.raw_cross(daily, 3) != -1:
        raise AssertionError("Soft short root missing")
    weights = pd.DataFrame(
        {
            "root_id": ["A", "A", "B", "B", "B"],
            "row_weight": [0.5, 0.5, 1 / 3, 1 / 3, 1 / 3],
        }
    ).groupby("root_id")["row_weight"].sum()
    if not np.allclose(weights.to_numpy(), 1.0):
        raise AssertionError("Synthetic root weights do not sum to one")


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        print("self-test: PASS")
        return
    if args.capacity_only:
        roots, panel, capacity = build_data()
        result: dict[str, Any] = {"capacity": capacity}
        if not args.no_write:
            paths = write_capacity_outputs(
                args.output_dir,
                roots,
                panel,
                capacity,
            )
            result["artifact_sha256"] = {
                name: shared.sha256_path(path) for name, path in paths.items()
            }
        print(json.dumps(json_ready(result), ensure_ascii=False, indent=2))
        return
    roots, panel, scores, decisions, payload, frozen = build_payload()
    result = {
        "eligible_roots": int(len(roots)),
        "person_period_rows": int(len(panel)),
        "development_gate_pass": bool(
            payload["report"]["summary"]["development_gate_pass"]
        ),
        "summary": payload["report"]["summary"],
    }
    if not args.no_write:
        result["artifact_sha256"] = write_outputs(
            args.output_dir,
            roots,
            panel,
            scores,
            decisions,
            payload,
            frozen,
        )
    print(json.dumps(json_ready(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
