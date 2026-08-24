from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-volatility-impulse-pullback-reclaim"
)
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p1_development_2026-08-10"
SHARED_KERNEL_PATH = (
    ROOT / "research/_shared-kernels/binance-ma7-root-data/v1/engine.py"
)
SHARED_KERNEL_SHA256 = (
    "3d7c6d295568b96627a4b6aa4efad0fc7fdc8a53503f9f4fa55922c7069bfa3d"
)

ASSET_SLUGS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
}
ASSETS = tuple(ASSET_SLUGS)
INPUT_END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")
DEVELOPMENT_ROOT_END = pd.Timestamp("2024-05-25T00:00:00Z")
DEVELOPMENT_DATA_END = pd.Timestamp("2024-06-01T00:00:00Z")
HOLDOUT_ROOT_START = pd.Timestamp("2024-06-01T00:00:00Z")
HOLDOUT_ROOT_END = pd.Timestamp("2025-05-20T00:00:00Z")

ATR_PERIOD = 24
IMPULSE_HOURS = 6
ROOT_RANGE_CAP_ATR = 3.0
CLOSE_LOCATION_MIN = 0.70
PENDING_HOURS = 48
INVALIDATION_ATR = 0.5
STOP_ATR = 1.0
TARGET_ATR = 2.0
TIMEOUT_HOURS = 120
LEVERAGE = 0.25
FEE_RATE = 0.001
MAIN_SLIPPAGE = 0.0004
STRESS_8BPS = 0.0008
STRESS_12BPS = 0.0012
BOOTSTRAP_SAMPLES = 10_000
RANDOM_SEED = 20260810


@dataclass(frozen=True, order=True)
class Config:
    breakout_lookback: int
    impulse_atr: float
    pullback_atr: float

    @property
    def config_id(self) -> str:
        impulse = str(self.impulse_atr).replace(".", "p")
        pullback = str(self.pullback_atr).replace(".", "p")
        return f"N{self.breakout_lookback}_I{impulse}_P{pullback}"


CONFIGS = tuple(
    Config(lookback, impulse, pullback)
    for lookback in (24, 72)
    for impulse in (1.0, 1.5)
    for pullback in (0.5, 1.0)
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_shared_kernel() -> Any:
    actual = sha256_path(SHARED_KERNEL_PATH)
    if actual != SHARED_KERNEL_SHA256:
        raise RuntimeError(
            f"Shared kernel SHA mismatch: expected {SHARED_KERNEL_SHA256}, got {actual}"
        )
    name = "binance_ma7_root_data_v1_vipr"
    spec = importlib.util.spec_from_file_location(name, SHARED_KERNEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load shared kernel")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


shared = load_shared_kernel()


def validate_input_paths() -> None:
    allowed = set(ASSET_SLUGS.values())
    for asset, slug in ASSET_SLUGS.items():
        if asset == "HYPE" or slug not in allowed or "hype" in slug.lower():
            raise RuntimeError("HYPE or non-whitelisted asset reached input validation")
        paths = shared.feature_paths(FEATURE_DIR, slug)
        for path in paths.values():
            if "hype" in path.name.lower():
                raise RuntimeError(f"Forbidden HYPE path: {path}")


def prefix_sum(values: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(values, dtype="float64")])


def cache_inputs(
    hourly: pd.DataFrame, funding: pd.DataFrame
) -> dict[str, np.ndarray]:
    ts_ns = (
        pd.to_datetime(hourly["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    expected = 3_600_000_000_000
    if len(ts_ns) < 2 or np.any(np.diff(ts_ns) != expected):
        raise RuntimeError("Hourly input is not a complete 1h UTC grid")
    if hourly["ts"].duplicated().any() or not bool(hourly["is_closed"].all()):
        raise RuntimeError("Hourly input has duplicate or non-closed bars")
    open_values = hourly["open"].to_numpy(dtype="float64")
    high_values = hourly["high"].to_numpy(dtype="float64")
    low_values = hourly["low"].to_numpy(dtype="float64")
    close_values = hourly["close"].to_numpy(dtype="float64")
    if not np.isfinite(
        np.column_stack([open_values, high_values, low_values, close_values])
    ).all():
        raise RuntimeError("Hourly OHLC contains non-finite values")
    if (
        np.any(open_values <= 0.0)
        or np.any(low_values <= 0.0)
        or np.any(high_values < np.maximum(open_values, close_values))
        or np.any(low_values > np.minimum(open_values, close_values))
    ):
        raise RuntimeError("Hourly OHLC is invalid")

    previous_close = np.concatenate([[close_values[0]], close_values[:-1]])
    true_range = np.maximum.reduce(
        [
            high_values - low_values,
            np.abs(high_values - previous_close),
            np.abs(low_values - previous_close),
        ]
    )
    tr_prefix = prefix_sum(true_range)
    atr_prior = np.full(len(hourly), np.nan, dtype="float64")
    indices = np.arange(ATR_PERIOD, len(hourly))
    atr_prior[indices] = (
        tr_prefix[indices] - tr_prefix[indices - ATR_PERIOD]
    ) / ATR_PERIOD

    funding_ts_ns = (
        pd.to_datetime(funding["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    if np.any(np.diff(funding_ts_ns) <= 0):
        raise RuntimeError("Funding timestamps are not strictly increasing")
    funding_rate = funding["funding_rate"].to_numpy(dtype="float64")
    funding_mark = funding["mark_price"].to_numpy(dtype="float64")
    if not np.isfinite(funding_rate).all() or not np.isfinite(funding_mark).all():
        raise RuntimeError("Funding input contains non-finite values")
    return {
        "ts_ns": ts_ns,
        "open": open_values,
        "high": high_values,
        "low": low_values,
        "close": close_values,
        "true_range": true_range,
        "atr_prior": atr_prior,
        "funding_ts_ns": funding_ts_ns,
        "funding_mark_rate_prefix": prefix_sum(funding_rate * funding_mark),
    }


def prior_breakout_levels(
    high: np.ndarray, low: np.ndarray, lookback: int
) -> tuple[np.ndarray, np.ndarray]:
    prior_high = (
        pd.Series(high).rolling(lookback, min_periods=lookback).max().shift(1)
    )
    prior_low = (
        pd.Series(low).rolling(lookback, min_periods=lookback).min().shift(1)
    )
    return (
        prior_high.to_numpy(dtype="float64"),
        prior_low.to_numpy(dtype="float64"),
    )


def root_signals(
    cache: dict[str, np.ndarray], config: Config
) -> tuple[np.ndarray, np.ndarray]:
    high = cache["high"]
    low = cache["low"]
    close = cache["close"]
    atr = cache["atr_prior"]
    tr = cache["true_range"]
    prior_high, prior_low = prior_breakout_levels(
        high, low, config.breakout_lookback
    )
    side = np.zeros(len(close), dtype="int8")
    level = np.full(len(close), np.nan, dtype="float64")
    start = max(config.breakout_lookback, ATR_PERIOD, IMPULSE_HOURS)
    for index in range(start, len(close)):
        values = (
            atr[index],
            prior_high[index],
            prior_low[index],
            high[index],
            low[index],
            close[index],
            close[index - IMPULSE_HOURS],
            tr[index],
        )
        if not all(math.isfinite(float(value)) for value in values):
            continue
        if atr[index] <= 0.0 or high[index] <= low[index]:
            continue
        if tr[index] / atr[index] > ROOT_RANGE_CAP_ATR:
            continue
        displacement = (close[index] - close[index - IMPULSE_HOURS]) / atr[index]
        close_location = (close[index] - low[index]) / (
            high[index] - low[index]
        )
        if (
            close[index] > prior_high[index]
            and displacement >= config.impulse_atr
            and close_location >= CLOSE_LOCATION_MIN
        ):
            side[index] = 1
            level[index] = prior_high[index]
        elif (
            close[index] < prior_low[index]
            and -displacement >= config.impulse_atr
            and close_location <= 1.0 - CLOSE_LOCATION_MIN
        ):
            side[index] = -1
            level[index] = prior_low[index]
    return side, level


def timestamp_from_ns(value: int | np.integer[Any]) -> pd.Timestamp:
    return pd.Timestamp(int(value), tz="UTC")


def funding_mark_sum(
    cache: dict[str, np.ndarray], entry_index: int, exit_index: int
) -> tuple[float, int]:
    entry_ns = int(cache["ts_ns"][entry_index])
    exit_ns = int(cache["ts_ns"][exit_index])
    funding_ts = cache["funding_ts_ns"]
    left = int(np.searchsorted(funding_ts, entry_ns, side="right"))
    right = int(np.searchsorted(funding_ts, exit_ns, side="left"))
    prefix = cache["funding_mark_rate_prefix"]
    return float(prefix[right] - prefix[left]), int(right - left)


def bracket_exit(
    cache: dict[str, np.ndarray],
    *,
    entry_index: int,
    side: int,
    root_atr: float,
    data_end_exclusive: pd.Timestamp,
) -> dict[str, Any] | None:
    ts_ns = cache["ts_ns"]
    end_index = int(
        np.searchsorted(
            ts_ns,
            int(data_end_exclusive.value),
            side="left",
        )
    )
    timeout_index = entry_index + TIMEOUT_HOURS
    if entry_index >= len(ts_ns) or timeout_index >= end_index:
        return None
    entry_reference = float(cache["open"][entry_index])
    stop = entry_reference - side * STOP_ATR * root_atr
    target = entry_reference + side * TARGET_ATR * root_atr
    for index in range(entry_index, timeout_index):
        open_value = float(cache["open"][index])
        high_value = float(cache["high"][index])
        low_value = float(cache["low"][index])
        if side == 1:
            if open_value <= stop:
                return {
                    "exit_index": index,
                    "exit_reference": open_value,
                    "exit_reason": "STOP_GAP",
                }
            if open_value >= target:
                return {
                    "exit_index": index,
                    "exit_reference": target,
                    "exit_reason": "TARGET_GAP",
                }
            stop_hit = low_value <= stop
            target_hit = high_value >= target
        else:
            if open_value >= stop:
                return {
                    "exit_index": index,
                    "exit_reference": open_value,
                    "exit_reason": "STOP_GAP",
                }
            if open_value <= target:
                return {
                    "exit_index": index,
                    "exit_reference": target,
                    "exit_reason": "TARGET_GAP",
                }
            stop_hit = high_value >= stop
            target_hit = low_value <= target
        if stop_hit:
            return {
                "exit_index": index,
                "exit_reference": stop,
                "exit_reason": "STOP_BOTH" if target_hit else "STOP",
            }
        if target_hit:
            return {
                "exit_index": index,
                "exit_reference": target,
                "exit_reason": "TARGET",
            }
    return {
        "exit_index": timeout_index,
        "exit_reference": float(cache["open"][timeout_index]),
        "exit_reason": "TIMEOUT",
    }


def add_return_variants(
    row: dict[str, Any],
    cache: dict[str, np.ndarray],
    *,
    prefix: str = "",
    include_lag: bool = False,
    data_end_exclusive: pd.Timestamp,
) -> None:
    side = int(row["side"])
    entry_index = int(row[f"{prefix}entry_index"])
    exit_index = int(row[f"{prefix}exit_index"])
    entry_reference = float(row[f"{prefix}entry_reference"])
    exit_reference = float(row[f"{prefix}exit_reference"])
    mark_sum, funding_count = funding_mark_sum(cache, entry_index, exit_index)
    row[f"{prefix}funding_count"] = funding_count
    for name, slippage, funding_on in (
        ("z_4bps", MAIN_SLIPPAGE, True),
        ("z_8bps", STRESS_8BPS, True),
        ("z_12bps", STRESS_12BPS, True),
        ("z_funding_off", MAIN_SLIPPAGE, False),
    ):
        entry_fill = entry_reference * (1.0 + side * slippage)
        funding_component = (
            -side * mark_sum / entry_fill if funding_on else 0.0
        )
        outcome = shared.levered_trade_return(
            side=side,
            entry_reference=entry_reference,
            exit_reference=exit_reference,
            slippage=slippage,
            fee_rate=FEE_RATE,
            leverage=LEVERAGE,
            funding_component=funding_component,
        )
        row[f"{prefix}{name}"] = outcome["direct_net_return"]
    if not include_lag:
        return
    lag_entry_index = entry_index + 1
    lag = bracket_exit(
        cache,
        entry_index=lag_entry_index,
        side=side,
        root_atr=float(row["root_atr"]),
        data_end_exclusive=data_end_exclusive,
    )
    if lag is None:
        row["z_lag1h"] = math.nan
        row["lag1h_entry_ts"] = None
        row["lag1h_exit_ts"] = None
        return
    lag_entry_reference = float(cache["open"][lag_entry_index])
    lag_exit_index = int(lag["exit_index"])
    lag_exit_reference = float(lag["exit_reference"])
    lag_mark_sum, _ = funding_mark_sum(cache, lag_entry_index, lag_exit_index)
    lag_entry_fill = lag_entry_reference * (1.0 + side * MAIN_SLIPPAGE)
    lag_outcome = shared.levered_trade_return(
        side=side,
        entry_reference=lag_entry_reference,
        exit_reference=lag_exit_reference,
        slippage=MAIN_SLIPPAGE,
        fee_rate=FEE_RATE,
        leverage=LEVERAGE,
        funding_component=-side * lag_mark_sum / lag_entry_fill,
    )
    row["z_lag1h"] = lag_outcome["direct_net_return"]
    row["lag1h_entry_ts"] = timestamp_from_ns(cache["ts_ns"][lag_entry_index])
    row["lag1h_exit_ts"] = timestamp_from_ns(cache["ts_ns"][lag_exit_index])


def root_record(
    *,
    asset: str,
    config: Config,
    index: int,
    cache: dict[str, np.ndarray],
    side: int,
    level: float,
    accepted: bool,
    disposition: str,
) -> dict[str, Any]:
    signal_ts = timestamp_from_ns(cache["ts_ns"][index]) + pd.Timedelta(hours=1)
    return {
        "asset": asset,
        "config_id": config.config_id,
        "root_id": (
            f"{asset}-{config.config_id}-"
            f"{signal_ts.strftime('%Y%m%dT%H%M%SZ')}-{side:+d}"
        ),
        "root_bar_index": index,
        "root_bar_ts": timestamp_from_ns(cache["ts_ns"][index]),
        "root_signal_ts": signal_ts,
        "side": side,
        "breakout_level": level,
        "root_atr": float(cache["atr_prior"][index]),
        "accepted": accepted,
        "disposition": disposition,
    }


def simulate_config_asset(
    *,
    asset: str,
    cache: dict[str, np.ndarray],
    config: Config,
    root_start: pd.Timestamp | None,
    root_end_exclusive: pd.Timestamp,
    data_end_exclusive: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sides, levels = root_signals(cache, config)
    ts_ns = cache["ts_ns"]
    warmup_index = max(config.breakout_lookback, ATR_PERIOD, IMPULSE_HOURS)
    start_index = warmup_index
    if root_start is not None:
        start_index = max(
            warmup_index,
            int(
                np.searchsorted(
                    ts_ns,
                    int((root_start - pd.Timedelta(hours=1)).value),
                    side="left",
                )
            ),
        )
    data_end_index = int(
        np.searchsorted(ts_ns, int(data_end_exclusive.value), side="left")
    )
    roots: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    busy_exit_index: int | None = None

    for index in range(start_index, data_end_index):
        signal_ns = int(ts_ns[index]) + 3_600_000_000_000
        root_allowed = signal_ns < int(root_end_exclusive.value) and (
            root_start is None or signal_ns >= int(root_start.value)
        )
        signal_side = int(sides[index]) if root_allowed else 0
        if busy_exit_index is not None:
            if index < busy_exit_index:
                if signal_side != 0:
                    roots.append(
                        root_record(
                            asset=asset,
                            config=config,
                            index=index,
                            cache=cache,
                            side=signal_side,
                            level=float(levels[index]),
                            accepted=False,
                            disposition="POSITION_OCCUPIED",
                        )
                    )
                continue
            busy_exit_index = None

        scheduled = False
        if pending is not None:
            age = index - int(pending["root_bar_index"])
            invalid = (
                int(pending["side"])
                * (float(cache["close"][index]) - float(pending["breakout_level"]))
                < -INVALIDATION_ATR * float(pending["root_atr"])
            )
            if age > PENDING_HOURS:
                pending["disposition"] = "EXPIRED"
                pending = None
            elif invalid:
                pending["disposition"] = "INVALIDATED"
                pending = None
            else:
                side = int(pending["side"])
                if pending["armed_index"] is None:
                    pullback = (
                        float(pending["prior_extreme"])
                        - float(cache["low"][index])
                        if side == 1
                        else float(cache["high"][index])
                        - float(pending["prior_extreme"])
                    )
                    if pullback >= config.pullback_atr * float(
                        pending["root_atr"]
                    ):
                        pending["armed_index"] = index
                elif index > int(pending["armed_index"]):
                    reclaim = side * (
                        float(cache["close"][index])
                        - float(pending["breakout_level"])
                    ) >= 0.0 and side * (
                        float(cache["close"][index])
                        - float(cache["close"][index - 1])
                    ) > 0.0
                    if reclaim:
                        entry_index = index + 1
                        outcome = bracket_exit(
                            cache,
                            entry_index=entry_index,
                            side=side,
                            root_atr=float(pending["root_atr"]),
                            data_end_exclusive=data_end_exclusive,
                        )
                        if outcome is not None:
                            row = {
                                key: pending[key]
                                for key in (
                                    "asset",
                                    "config_id",
                                    "root_id",
                                    "root_bar_index",
                                    "root_bar_ts",
                                    "root_signal_ts",
                                    "side",
                                    "breakout_level",
                                    "root_atr",
                                )
                            }
                            row.update(
                                {
                                    "armed_bar_ts": timestamp_from_ns(
                                        ts_ns[int(pending["armed_index"])]
                                    ),
                                    "reclaim_bar_ts": timestamp_from_ns(
                                        ts_ns[index]
                                    ),
                                    "entry_index": entry_index,
                                    "entry_ts": timestamp_from_ns(
                                        ts_ns[entry_index]
                                    ),
                                    "entry_reference": float(
                                        cache["open"][entry_index]
                                    ),
                                    "exit_index": int(outcome["exit_index"]),
                                    "exit_ts": timestamp_from_ns(
                                        ts_ns[int(outcome["exit_index"])]
                                    ),
                                    "exit_reference": float(
                                        outcome["exit_reference"]
                                    ),
                                    "exit_reason": str(outcome["exit_reason"]),
                                }
                            )
                            add_return_variants(
                                row,
                                cache,
                                include_lag=True,
                                data_end_exclusive=data_end_exclusive,
                            )
                            immediate_entry = int(pending["root_bar_index"]) + 1
                            immediate = bracket_exit(
                                cache,
                                entry_index=immediate_entry,
                                side=side,
                                root_atr=float(pending["root_atr"]),
                                data_end_exclusive=data_end_exclusive,
                            )
                            if immediate is None:
                                raise RuntimeError(
                                    "Executed root lacks immediate baseline"
                                )
                            row.update(
                                {
                                    "immediate_entry_index": immediate_entry,
                                    "immediate_entry_ts": timestamp_from_ns(
                                        ts_ns[immediate_entry]
                                    ),
                                    "immediate_entry_reference": float(
                                        cache["open"][immediate_entry]
                                    ),
                                    "immediate_exit_index": int(
                                        immediate["exit_index"]
                                    ),
                                    "immediate_exit_ts": timestamp_from_ns(
                                        ts_ns[int(immediate["exit_index"])]
                                    ),
                                    "immediate_exit_reference": float(
                                        immediate["exit_reference"]
                                    ),
                                    "immediate_exit_reason": str(
                                        immediate["exit_reason"]
                                    ),
                                }
                            )
                            add_return_variants(
                                row,
                                cache,
                                prefix="immediate_",
                                data_end_exclusive=data_end_exclusive,
                            )
                            trades.append(row)
                            busy_exit_index = int(outcome["exit_index"])
                            scheduled = True
                        pending["disposition"] = (
                            "TRADED" if scheduled else "INCOMPLETE_OUTCOME"
                        )
                        pending = None
                if pending is not None:
                    if side == 1:
                        pending["prior_extreme"] = max(
                            float(pending["prior_extreme"]),
                            float(cache["high"][index]),
                        )
                    else:
                        pending["prior_extreme"] = min(
                            float(pending["prior_extreme"]),
                            float(cache["low"][index]),
                        )

        if scheduled:
            if signal_side != 0:
                roots.append(
                    root_record(
                        asset=asset,
                        config=config,
                        index=index,
                        cache=cache,
                        side=signal_side,
                        level=float(levels[index]),
                        accepted=False,
                        disposition="ENTRY_SCHEDULED",
                    )
                )
            continue
        if signal_side == 0:
            continue
        if pending is not None and signal_side == int(pending["side"]):
            roots.append(
                root_record(
                    asset=asset,
                    config=config,
                    index=index,
                    cache=cache,
                    side=signal_side,
                    level=float(levels[index]),
                    accepted=False,
                    disposition="SAME_SIDE_PENDING",
                )
            )
            continue
        if pending is not None:
            pending["disposition"] = "REPLACED_BY_OPPOSITE"
        accepted = root_record(
            asset=asset,
            config=config,
            index=index,
            cache=cache,
            side=signal_side,
            level=float(levels[index]),
            accepted=True,
            disposition="PENDING",
        )
        roots.append(accepted)
        pending = dict(accepted)
        pending["armed_index"] = None
        pending["prior_extreme"] = (
            float(cache["high"][index])
            if signal_side == 1
            else float(cache["low"][index])
        )

    return pd.DataFrame(roots), pd.DataFrame(trades)


def block_labels(series: pd.Series, days: int) -> pd.Series:
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    return ((series - epoch) // pd.Timedelta(days=days)).astype("int64")


def cluster_bootstrap(
    frame: pd.DataFrame,
    *,
    column: str,
    block_days: int,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    usable = frame.loc[frame[column].notna()].copy()
    if usable.empty:
        return {
            "samples": BOOTSTRAP_SAMPLES,
            "seed": seed,
            "clusters": 0,
            "positive_probability": 0.0,
            "quantiles": {"2.5%": 0.0, "50%": 0.0, "97.5%": 0.0},
        }
    usable["block"] = block_labels(usable["entry_ts"], block_days)
    clusters = [
        group[column].to_numpy(dtype="float64")
        for _, group in usable.groupby(["asset", "block"], sort=True)
    ]
    rng = np.random.default_rng(seed)
    means = np.empty(BOOTSTRAP_SAMPLES, dtype="float64")
    for index in range(BOOTSTRAP_SAMPLES):
        selected = rng.integers(0, len(clusters), size=len(clusters))
        sample = np.concatenate([clusters[item] for item in selected])
        means[index] = float(np.mean(sample))
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": seed,
        "clusters": len(clusters),
        "positive_probability": float(np.mean(means > 0.0)),
        "quantiles": {
            "2.5%": float(np.quantile(means, 0.025)),
            "50%": float(np.quantile(means, 0.5)),
            "97.5%": float(np.quantile(means, 0.975)),
        },
    }


def summarize_trades(
    frame: pd.DataFrame,
    *,
    block_days: int,
    include_holdout_audits: bool,
) -> dict[str, Any]:
    main = shared.return_metrics(frame, "z_4bps")
    per_asset: dict[str, Any] = {}
    for asset in ASSETS:
        asset_frame = frame.loc[frame["asset"] == asset]
        per_asset[asset] = shared.return_metrics(asset_frame, "z_4bps")
    per_side = {
        "long": shared.return_metrics(frame.loc[frame["side"] == 1], "z_4bps"),
        "short": shared.return_metrics(frame.loc[frame["side"] == -1], "z_4bps"),
    }
    block_frame = frame.copy()
    block_frame["block"] = block_labels(block_frame["entry_ts"], block_days)
    blocks = {
        str(int(block)): shared.return_metrics(group, "z_4bps")
        for block, group in block_frame.groupby("block", sort=True)
    }
    positive_blocks = sum(metrics["mean"] > 0.0 for metrics in blocks.values())
    summary: dict[str, Any] = {
        "main": main,
        "per_asset": per_asset,
        "per_side": per_side,
        "positive_asset_count": sum(
            metrics["mean"] > 0.0 for metrics in per_asset.values()
        ),
        "blocks": blocks,
        "positive_block_count": positive_blocks,
        "block_count": len(blocks),
        "positive_block_rate": (
            positive_blocks / len(blocks) if blocks else 0.0
        ),
        "bootstrap": cluster_bootstrap(
            frame, column="z_4bps", block_days=block_days
        ),
    }
    if not include_holdout_audits:
        return summary

    variants = {
        column: shared.return_metrics(frame, column)
        for column in ("z_8bps", "z_12bps", "z_funding_off", "z_lag1h")
    }
    immediate = shared.return_metrics(frame, "immediate_z_4bps")
    paired = frame.copy()
    paired["paired_delta"] = paired["z_4bps"] - paired["immediate_z_4bps"]
    paired_bootstrap = cluster_bootstrap(
        paired, column="paired_delta", block_days=block_days
    )
    dual_by_asset: dict[str, Any] = {}
    for asset in ASSETS:
        asset_frame = frame.loc[frame["asset"] == asset]
        selected_metrics = shared.return_metrics(asset_frame, "z_4bps")
        immediate_metrics = shared.return_metrics(
            asset_frame, "immediate_z_4bps"
        )
        dual_by_asset[asset] = {
            "reclaim": selected_metrics,
            "immediate": immediate_metrics,
            "dual_improved": (
                selected_metrics["compound"] > immediate_metrics["compound"]
                and selected_metrics["event_sequence_mdd"]
                > immediate_metrics["event_sequence_mdd"]
            ),
        }
    lag_executable_rate = (
        float(frame["z_lag1h"].notna().mean()) if not frame.empty else 0.0
    )
    summary.update(
        {
            "variants": variants,
            "immediate_same_roots": immediate,
            "paired_immediate": {
                "roots": int(len(paired)),
                "mean_delta": (
                    float(paired["paired_delta"].mean())
                    if not paired.empty
                    else 0.0
                ),
                "bootstrap": paired_bootstrap,
            },
            "dual_by_asset": dual_by_asset,
            "dual_improved_asset_count": sum(
                item["dual_improved"] for item in dual_by_asset.values()
            ),
            "lag1h_executable_rate": lag_executable_rate,
        }
    )
    return summary


def development_gate(summary: dict[str, Any]) -> dict[str, bool]:
    return {
        "trade_capacity": (
            summary["main"]["events"] >= 120
            and all(
                summary["per_asset"][asset]["events"] >= 10 for asset in ASSETS
            )
            and summary["per_side"]["long"]["events"] >= 30
            and summary["per_side"]["short"]["events"] >= 30
        ),
        "main_economics": (
            summary["main"]["mean"] > 0.0
            and summary["main"]["profit_factor"] >= 1.05
        ),
        "positive_assets": summary["positive_asset_count"] >= 4,
        "positive_blocks": summary["positive_block_rate"] >= 0.60,
        "cluster_bootstrap": (
            summary["bootstrap"]["positive_probability"] >= 0.80
        ),
    }


def select_development(
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    eligible = [
        item for item in candidates if all(item["gate_checks"].values())
    ]
    if not eligible:
        return None

    def rank(item: dict[str, Any]) -> tuple[float, ...]:
        summary = item["summary"]
        config = item["config"]
        minimum_asset_mean = min(
            summary["per_asset"][asset]["mean"] for asset in ASSETS
        )
        return (
            minimum_asset_mean,
            summary["positive_block_rate"],
            summary["main"]["mean"],
            summary["main"]["profit_factor"],
            float(config["breakout_lookback"]),
            float(config["impulse_atr"]),
            float(config["pullback_atr"]),
        )

    return max(eligible, key=rank)


def holdout_gate(summary: dict[str, Any]) -> dict[str, bool]:
    variants = summary["variants"]
    return {
        "trade_capacity": (
            summary["main"]["events"] >= 40
            and all(
                summary["per_asset"][asset]["events"] >= 5 for asset in ASSETS
            )
            and summary["per_side"]["long"]["events"] >= 10
            and summary["per_side"]["short"]["events"] >= 10
        ),
        "main_economics": (
            summary["main"]["mean"] > 0.0
            and summary["main"]["profit_factor"] >= 1.15
        ),
        "positive_assets": summary["positive_asset_count"] >= 4,
        "positive_blocks": (
            summary["block_count"] >= 4
            and summary["positive_block_count"] >= 3
        ),
        "cluster_bootstrap": (
            summary["bootstrap"]["positive_probability"] >= 0.90
        ),
        "beats_immediate": (
            summary["paired_immediate"]["mean_delta"] > 0.0
            and summary["paired_immediate"]["bootstrap"][
                "positive_probability"
            ]
            >= 0.80
        ),
        "per_asset_dual_improvement": (
            summary["dual_improved_asset_count"] >= 3
        ),
        "stress_8bps": (
            variants["z_8bps"]["mean"] > 0.0
            and variants["z_8bps"]["profit_factor"] >= 1.05
        ),
        "stress_lag1h": (
            summary["lag1h_executable_rate"] >= 0.90
            and variants["z_lag1h"]["mean"] > 0.0
            and variants["z_lag1h"]["profit_factor"] >= 1.05
        ),
    }


def recent_slices(frame: pd.DataFrame, end: pd.Timestamp) -> dict[str, Any]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    return {
        name: shared.return_metrics(
            frame.loc[
                (frame["entry_ts"] >= end - window)
                & (frame["entry_ts"] < end)
            ],
            "z_4bps",
        )
        for name, window in windows.items()
    }


def load_data() -> tuple[
    dict[str, dict[str, np.ndarray]], dict[str, Any]
]:
    validate_input_paths()
    caches: dict[str, dict[str, np.ndarray]] = {}
    quality: dict[str, Any] = {}
    for asset, slug in ASSET_SLUGS.items():
        _, hourly, funding, asset_quality = shared.load_asset_inputs(
            FEATURE_DIR,
            asset=asset,
            slug=slug,
            end_exclusive=INPUT_END_EXCLUSIVE,
        )
        caches[asset] = cache_inputs(hourly, funding)
        quality[asset] = asset_quality
    return caches, quality


def run_configuration(
    caches: dict[str, dict[str, np.ndarray]],
    config: Config,
    *,
    root_start: pd.Timestamp | None,
    root_end_exclusive: pd.Timestamp,
    data_end_exclusive: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    roots: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    for asset in ASSETS:
        asset_roots, asset_trades = simulate_config_asset(
            asset=asset,
            cache=caches[asset],
            config=config,
            root_start=root_start,
            root_end_exclusive=root_end_exclusive,
            data_end_exclusive=data_end_exclusive,
        )
        roots.append(asset_roots)
        trades.append(asset_trades)
    root_frame = pd.concat(roots, ignore_index=True) if roots else pd.DataFrame()
    trade_frame = (
        pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    )
    required_columns: dict[str, str] = {
        "asset": "object",
        "side": "int64",
        "entry_ts": "datetime64[ns, UTC]",
        "root_id": "object",
        "z_4bps": "float64",
        "z_8bps": "float64",
        "z_12bps": "float64",
        "z_funding_off": "float64",
        "z_lag1h": "float64",
        "immediate_z_4bps": "float64",
    }
    for column, dtype in required_columns.items():
        if column not in trade_frame:
            trade_frame[column] = pd.Series(dtype=dtype)
    if not trade_frame.empty:
        trade_frame = trade_frame.sort_values(
            ["entry_ts", "asset", "root_id"]
        ).reset_index(drop=True)
    return root_frame, trade_frame


def build_payload() -> dict[str, Any]:
    caches, quality = load_data()
    development_candidates: list[dict[str, Any]] = []
    development_roots: list[pd.DataFrame] = []
    development_trades: list[pd.DataFrame] = []
    for config in CONFIGS:
        roots, trades = run_configuration(
            caches,
            config,
            root_start=None,
            root_end_exclusive=DEVELOPMENT_ROOT_END,
            data_end_exclusive=DEVELOPMENT_DATA_END,
        )
        summary = summarize_trades(
            trades, block_days=180, include_holdout_audits=False
        )
        checks = development_gate(summary)
        development_candidates.append(
            {
                "config": asdict(config) | {"config_id": config.config_id},
                "root_inventory": {
                    "all_qualifying": int(len(roots)),
                    "accepted": (
                        int(roots["accepted"].sum()) if not roots.empty else 0
                    ),
                },
                "summary": summary,
                "gate_checks": checks,
                "development_gate_pass": all(checks.values()),
            }
        )
        development_roots.append(roots)
        development_trades.append(trades)
    selected = select_development(development_candidates)
    holdout_revealed = selected is not None
    holdout_roots = pd.DataFrame()
    holdout_trades = pd.DataFrame()
    holdout_summary: dict[str, Any] | None = None
    holdout_checks: dict[str, bool] | None = None
    holdout_pass = False
    if selected is not None:
        config_values = selected["config"]
        selected_config = Config(
            int(config_values["breakout_lookback"]),
            float(config_values["impulse_atr"]),
            float(config_values["pullback_atr"]),
        )
        holdout_roots, holdout_trades = run_configuration(
            caches,
            selected_config,
            root_start=HOLDOUT_ROOT_START,
            root_end_exclusive=HOLDOUT_ROOT_END,
            data_end_exclusive=INPUT_END_EXCLUSIVE,
        )
        holdout_summary = summarize_trades(
            holdout_trades, block_days=90, include_holdout_audits=True
        )
        holdout_summary["recent_slices"] = recent_slices(
            holdout_trades, INPUT_END_EXCLUSIVE
        )
        holdout_checks = holdout_gate(holdout_summary)
        holdout_pass = all(holdout_checks.values())

    dev_root_frame = pd.concat(development_roots, ignore_index=True)
    dev_trade_frame = pd.concat(development_trades, ignore_index=True)
    capacity = {
        "schema_version": "binance-1h-vipr-p0-v1",
        "input_end_exclusive": INPUT_END_EXCLUSIVE,
        "development_root_end": DEVELOPMENT_ROOT_END,
        "development_data_end": DEVELOPMENT_DATA_END,
        "holdout_root_start": HOLDOUT_ROOT_START,
        "holdout_root_end": HOLDOUT_ROOT_END,
        "assets": list(ASSETS),
        "config_count": len(CONFIGS),
        "hype_rows_consumed": 0,
        "hype_files_opened": 0,
        "input_quality": quality,
        "shared_kernel": {
            "path": str(SHARED_KERNEL_PATH.relative_to(ROOT)),
            "sha256": SHARED_KERNEL_SHA256,
        },
    }
    report = {
        "schema_version": "binance-1h-vipr-p1-v1",
        "generated_at_utc": pd.Timestamp.now(tz="UTC"),
        "capacity": capacity,
        "development_candidates": development_candidates,
        "selected_development": selected,
        "holdout_revealed": holdout_revealed,
        "holdout_summary": holdout_summary,
        "holdout_gate_checks": holdout_checks,
        "holdout_gate_pass": holdout_pass,
        "decision": (
            "HOLDOUT_PASS"
            if holdout_pass
            else (
                "HOLDOUT_HARD_GATE_FAILED"
                if holdout_revealed
                else "DEVELOPMENT_HARD_GATE_FAILED_HOLDOUT_UNREVEALED"
            )
        ),
    }
    summary = {
        "decision": report["decision"],
        "development_eligible_config_count": sum(
            item["development_gate_pass"] for item in development_candidates
        ),
        "selected_config": selected["config"] if selected else None,
        "holdout_revealed": holdout_revealed,
        "holdout_gate_pass": holdout_pass,
        "development_candidates": [
            {
                "config": item["config"],
                "main": item["summary"]["main"],
                "positive_asset_count": item["summary"][
                    "positive_asset_count"
                ],
                "positive_block_rate": item["summary"]["positive_block_rate"],
                "bootstrap_positive_probability": item["summary"]["bootstrap"][
                    "positive_probability"
                ],
                "gate_checks": item["gate_checks"],
            }
            for item in development_candidates
        ],
        "holdout_summary": holdout_summary,
        "holdout_gate_checks": holdout_checks,
    }
    return {
        "capacity": capacity,
        "report": report,
        "summary": summary,
        "development_roots": dev_root_frame,
        "development_trades": dev_trade_frame,
        "holdout_roots": holdout_roots,
        "holdout_trades": holdout_trades,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_outputs(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "capacity": ARTIFACT_DIR / "p0_data_quality.json",
        "development_roots": ARTIFACT_DIR / "p1_development_roots.parquet",
        "development_trades": ARTIFACT_DIR / "p1_development_trades.parquet",
        "report": ARTIFACT_DIR / "p1_report.json",
        "summary": ARTIFACT_DIR / "p1_summary.json",
    }
    write_json(paths["capacity"], payload["capacity"])
    payload["development_roots"].to_parquet(
        paths["development_roots"], index=False
    )
    payload["development_trades"].to_parquet(
        paths["development_trades"], index=False
    )
    if payload["report"]["holdout_revealed"]:
        paths["holdout_roots"] = ARTIFACT_DIR / "p1_holdout_roots.parquet"
        paths["holdout_trades"] = ARTIFACT_DIR / "p1_holdout_trades.parquet"
        payload["holdout_roots"].to_parquet(paths["holdout_roots"], index=False)
        payload["holdout_trades"].to_parquet(
            paths["holdout_trades"], index=False
        )
    write_json(paths["report"], payload["report"])
    write_json(paths["summary"], payload["summary"])
    manifest = {
        "schema_version": "binance-1h-vipr-manifest-v1",
        "generated_at_utc": pd.Timestamp.now(tz="UTC"),
        "files": {
            name: {
                "path": str(path.relative_to(ARTIFACT_DIR)),
                "sha256": sha256_path(path),
            }
            for name, path in paths.items()
        },
    }
    manifest_path = ARTIFACT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    manifest_sha = ARTIFACT_DIR / "manifest.sha256"
    manifest_sha.write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    return {
        name: details["sha256"] for name, details in manifest["files"].items()
    } | {"manifest": sha256_path(manifest_path)}


def run_self_test() -> None:
    assert len(CONFIGS) == 8
    assert len({config.config_id for config in CONFIGS}) == 8
    assert DEVELOPMENT_ROOT_END < HOLDOUT_ROOT_START < HOLDOUT_ROOT_END
    assert HOLDOUT_ROOT_END < INPUT_END_EXCLUSIVE
    assert "HYPE" not in ASSETS
    assert all("hype" not in slug.lower() for slug in ASSET_SLUGS.values())
    print("self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return
    payload = build_payload()
    output = dict(payload["summary"])
    if not args.no_write:
        output["artifact_sha256"] = write_outputs(payload)
    print(json.dumps(json_ready(output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
