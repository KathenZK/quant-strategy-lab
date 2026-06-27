from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATA_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m")
RAW_ROOT = Path("data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

FAMILY_ROOT = Path("research/hype/1m-ema-crossover")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

RUN_DATE = "2026-06-27"
REPORT_PATH = ARTIFACT_ROOT / f"hype_1m_ema_deviation_take_profit_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_1m_ema_deviation_take_profit_summary_{RUN_DATE}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_1m_ema_deviation_take_profit_slices_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_1m_ema_deviation_take_profit_monthly_{RUN_DATE}.csv"
TOP_TRADES_PATH = ARTIFACT_ROOT / f"hype_1m_ema_deviation_take_profit_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-1m-ema-deviation-take-profit-{RUN_DATE}.md"

# Same conservative taker-heavy round-trip assumption used by the existing 1m EMA search.
FEE_BPS_PER_FILL = 5.0
SLIPPAGE_BPS_PER_FILL = 2.5
PER_FILL_COST = (FEE_BPS_PER_FILL + SLIPPAGE_BPS_PER_FILL) / 10_000.0
ROUND_TRIP_COST = 2 * PER_FILL_COST

MIN_PAPER_TRADES = 30
MIN_PAPER_PROFIT_FACTOR = 1.10
MIN_PAPER_WIN_RATE = 0.48
MAX_PAPER_DRAWDOWN = -0.20


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    name: str
    fast_ema: int
    slow_ema: int
    exit_model: str
    filter_name: str
    stop_atr: float
    arm_dev_atr: float | None
    trail_drawdown_atr: float | None
    partial_dev_atr: float | None
    partial_fraction: float
    use_two_closes_fast_break: bool
    use_weakening_fast_gap: bool
    max_hold_bars: int
    min_adx14: float
    require_slow_slope: bool
    min_slow_slope_atr: float
    min_atr_bps: float
    max_atr_bps: float
    slope_lookback: int = 10


@dataclass(slots=True)
class Trade:
    config: str
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    entry_price: float
    final_exit_price: float
    exit_reason: str
    bars_held: int
    raw_ret_1x: float
    net_ret_1x: float
    mae_1x: float
    mfe_1x: float
    max_dev_atr: float
    max_drawdown_atr_after_arm: float
    armed: bool
    partial_taken: bool
    partial_fraction: float
    partial_ts: pd.Timestamp | None
    adx14: float
    atr_bps: float
    slow_slope_atr: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest HYPE-1M-EMA-Crossover deviation/take-profit state-machine variants."
    )
    parser.add_argument(
        "--ema-pairs",
        type=str,
        default="8:21,13:48,21:55,21:72,21:96,30:120",
        help="Comma-separated fast:slow EMA pairs.",
    )
    parser.add_argument("--exposures", type=str, default="1,2,3")
    parser.add_argument("--top-keep", type=int, default=80)
    parser.add_argument("--progress-every", type=int, default=25)
    return parser.parse_args()


def parse_ema_pairs(text: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        fast_text, slow_text = item.split(":", maxsplit=1)
        fast = int(fast_text)
        slow = int(slow_text)
        if fast <= 0 or slow <= fast:
            raise ValueError(f"invalid EMA pair: {item}")
        pairs.append((fast, slow))
    if not pairs:
        raise ValueError("no EMA pairs were provided")
    return pairs


def parse_float_list(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("empty float list")
    return values


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def bps(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 10_000:.{digits}f} bps"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}x"


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def value_slug(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value).replace(".", "p").replace("-", "m")


def json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def load_partitioned(root: Path) -> tuple[pd.DataFrame, list[Path]]:
    files = sorted(root.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no parquet files under {root}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame, files


def validate_hype_1m() -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized, normalized_files = load_partitioned(DATA_ROOT)
    raw, raw_files = load_partitioned(RAW_ROOT)

    duplicate_ts = int(normalized.duplicated("ts").sum())
    raw_duplicate_ts = int(raw.duplicated("ts").sum())
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    raw = raw.sort_values("ts").reset_index(drop=True)

    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="1min")
    missing = expected.difference(normalized["ts"])
    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    nulls = {column: int(normalized[column].isna().sum()) for column in required if column in normalized.columns}
    violations = {
        "high_lt_max_open_close": int((normalized["high"] < normalized[["open", "close"]].max(axis=1)).sum()),
        "low_gt_min_open_close": int((normalized["low"] > normalized[["open", "close"]].min(axis=1)).sum()),
        "nonpositive_ohlc": int(((normalized[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()),
        "negative_volume": int((normalized["volume"] < 0).sum()),
        "negative_quote_volume": int((normalized["quote_volume"] < 0).sum()),
        "negative_trade_count": int((normalized["trade_count"] < 0).sum()),
        "vwap_outside_hilo_nonzero_vol": int(
            (
                (normalized["volume"] > 0)
                & (
                    (normalized["vwap"] < normalized["low"] * 0.999999)
                    | (normalized["vwap"] > normalized["high"] * 1.000001)
                )
            ).sum()
        ),
    }

    compare_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    merged = normalized[["ts", *compare_columns]].merge(
        raw[["ts", *compare_columns]],
        on="ts",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    alignment: dict[str, Any] = {
        "rows": int(len(merged)),
        "left_only": int((merged["_merge"] == "left_only").sum()),
        "right_only": int((merged["_merge"] == "right_only").sum()),
        "mismatch_counts": {},
        "max_abs_diff": {},
    }
    both = merged.loc[merged["_merge"].eq("both")].copy()
    for column in compare_columns:
        lhs = both[f"{column}_normalized"].astype(float).to_numpy()
        rhs = both[f"{column}_raw"].astype(float).to_numpy()
        diff = np.abs(lhs - rhs)
        tolerance = 1e-9 if column != "trade_count" else 0.0
        mismatch = ~np.isclose(lhs, rhs, rtol=0.0, atol=tolerance, equal_nan=True)
        alignment["mismatch_counts"][column] = int(mismatch.sum())
        alignment["max_abs_diff"][column] = float(np.nanmax(diff)) if len(diff) else 0.0

    source_counts = {
        str(key): int(value) for key, value in normalized["source"].value_counts(dropna=False).to_dict().items()
    }
    closed_counts = {
        str(key): int(value) for key, value in normalized["is_closed"].value_counts(dropna=False).to_dict().items()
    }
    quality = {
        "normalized_file_count": len(normalized_files),
        "raw_ohlcv_file_count": len(raw_files),
        "rows": int(len(normalized)),
        "raw_rows": int(len(raw)),
        "start_ts": str(normalized["ts"].iloc[0]),
        "end_ts": str(normalized["ts"].iloc[-1]),
        "expected_bars": int(len(expected)),
        "missing_bars": int(len(missing)),
        "first_missing": str(missing[0]) if len(missing) else None,
        "duplicate_ts": duplicate_ts,
        "raw_duplicate_ts": raw_duplicate_ts,
        "nulls": nulls,
        "source_counts": source_counts,
        "is_closed_counts": closed_counts,
        "ohlcv_violations": violations,
        "raw_normalized_alignment": alignment,
        "zero_volume_bars": int((normalized["volume"] == 0).sum()),
        "volume_p99": float(normalized["volume"].quantile(0.99)),
        "volume_max": float(normalized["volume"].max()),
    }

    blockers: list[str] = []
    if duplicate_ts:
        blockers.append(f"normalized duplicate ts={duplicate_ts}")
    if raw_duplicate_ts:
        blockers.append(f"raw duplicate ts={raw_duplicate_ts}")
    if len(missing):
        blockers.append(f"missing bars={len(missing)}, first={missing[0]}")
    if sum(nulls.values()):
        blockers.append(f"required nulls={nulls}")
    if any(violations.values()):
        blockers.append(f"OHLCV violations={violations}")
    if set(normalized["is_closed"].dropna().unique()) != {True}:
        blockers.append("non-closed bars are present")
    if alignment["left_only"] or alignment["right_only"]:
        blockers.append(f"raw/normalized ts mismatch={alignment}")
    if any(alignment["mismatch_counts"].values()):
        blockers.append(f"raw/normalized value mismatch={alignment['mismatch_counts']}")
    if blockers:
        raise RuntimeError("data-quality blocker: " + "; ".join(blockers))
    return normalized, quality


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


def adx_di(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def add_features(frame: pd.DataFrame, ema_spans: list[int]) -> pd.DataFrame:
    result = frame.sort_values("ts").reset_index(drop=True).copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"].astype("float64")
    high = result["high"].astype("float64")
    low = result["low"].astype("float64")
    volume = result["volume"].astype("float64")

    for span in sorted(set(ema_spans)):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()

    tr = true_range(high, low, close)
    result["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    result["atr_bps"] = result["atr14"] / close.replace(0.0, np.nan) * 10_000.0
    result["rvol60"] = volume / volume.rolling(60, min_periods=60).mean().replace(0.0, np.nan)
    result["adx14"], result["pdi14"], result["mdi14"] = adx_di(high, low, close, 14)
    return result


def filter_specs() -> list[dict[str, Any]]:
    return [
        {
            "filter_name": "none",
            "min_adx14": 0.0,
            "require_slow_slope": False,
            "min_slow_slope_atr": 0.0,
            "min_atr_bps": 0.0,
            "max_atr_bps": 999.0,
        },
        {
            "filter_name": "slope_adx18",
            "min_adx14": 18.0,
            "require_slow_slope": True,
            "min_slow_slope_atr": 0.0,
            "min_atr_bps": 0.0,
            "max_atr_bps": 999.0,
        },
        {
            "filter_name": "slope_adx20_atr3p5_100",
            "min_adx14": 20.0,
            "require_slow_slope": True,
            "min_slow_slope_atr": 0.0,
            "min_atr_bps": 3.5,
            "max_atr_bps": 100.0,
        },
    ]


def build_configs(ema_pairs: list[tuple[int, int]]) -> list[StrategyConfig]:
    configs: list[StrategyConfig] = []
    exit_specs: list[dict[str, Any]] = [
        {
            "exit_model": "A_cross_only",
            "stop_atr": 0.0,
            "arm_dev_atr": None,
            "trail_drawdown_atr": None,
            "partial_dev_atr": None,
            "partial_fraction": 0.0,
            "use_two_closes_fast_break": False,
            "use_weakening_fast_gap": False,
            "max_hold_bars": 0,
        }
    ]
    for arm in (1.8, 2.0, 2.2):
        for drawdown in (1.2, 1.5, 1.8):
            for stop in (1.5, 2.0):
                exit_specs.append(
                    {
                        "exit_model": f"B_devtrail_arm{value_slug(arm)}_dd{value_slug(drawdown)}_sl{value_slug(stop)}",
                        "stop_atr": stop,
                        "arm_dev_atr": arm,
                        "trail_drawdown_atr": drawdown,
                        "partial_dev_atr": None,
                        "partial_fraction": 0.0,
                        "use_two_closes_fast_break": False,
                        "use_weakening_fast_gap": False,
                        "max_hold_bars": 1440,
                    }
                )
                exit_specs.append(
                    {
                        "exit_model": f"D_exhaust_arm{value_slug(arm)}_dd{value_slug(drawdown)}_sl{value_slug(stop)}",
                        "stop_atr": stop,
                        "arm_dev_atr": arm,
                        "trail_drawdown_atr": drawdown,
                        "partial_dev_atr": None,
                        "partial_fraction": 0.0,
                        "use_two_closes_fast_break": True,
                        "use_weakening_fast_gap": True,
                        "max_hold_bars": 1440,
                    }
                )
    for partial_dev in (2.0, 2.2, 2.5):
        for drawdown in (1.2, 1.5, 1.8):
            for stop in (1.5, 2.0):
                exit_specs.append(
                    {
                        "exit_model": f"C_staged_p{value_slug(partial_dev)}_dd{value_slug(drawdown)}_sl{value_slug(stop)}",
                        "stop_atr": stop,
                        "arm_dev_atr": 2.0,
                        "trail_drawdown_atr": drawdown,
                        "partial_dev_atr": partial_dev,
                        "partial_fraction": 0.5,
                        "use_two_closes_fast_break": False,
                        "use_weakening_fast_gap": False,
                        "max_hold_bars": 1440,
                    }
                )

    for fast, slow in ema_pairs:
        for exit_spec in exit_specs:
            for filter_spec in filter_specs():
                name = (
                    f"HYPE_1M_EMA_DEVIATION_TP_FAST{fast}_SLOW{slow}_"
                    f"{exit_spec['exit_model']}_{filter_spec['filter_name']}"
                )
                configs.append(
                    StrategyConfig(
                        name=name,
                        fast_ema=fast,
                        slow_ema=slow,
                        **exit_spec,
                        **filter_spec,
                    )
                )
    return configs


def cross_signal(frame: pd.DataFrame, cfg: StrategyConfig) -> np.ndarray:
    fast = frame[f"ema{cfg.fast_ema}"].to_numpy("float64")
    slow = frame[f"ema{cfg.slow_ema}"].to_numpy("float64")
    spread = fast - slow
    previous = np.r_[np.nan, spread[:-1]]
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[(spread > 0) & (previous <= 0) & np.isfinite(spread) & np.isfinite(previous)] = 1
    signal[(spread < 0) & (previous >= 0) & np.isfinite(spread) & np.isfinite(previous)] = -1
    return signal


def touched_stop(open_price: float, high: float, low: float, stop_price: float, side: int) -> tuple[bool, float, str]:
    if side > 0:
        if open_price <= stop_price:
            return True, open_price, "gap_hard_stop"
        if low <= stop_price:
            return True, stop_price, "hard_stop"
    else:
        if open_price >= stop_price:
            return True, open_price, "gap_hard_stop"
        if high >= stop_price:
            return True, stop_price, "hard_stop"
    return False, np.nan, ""


def finite(value: float, default: float = 0.0) -> float:
    return float(value) if np.isfinite(value) else default


def passes_entry_filter(frame: pd.DataFrame, cfg: StrategyConfig, signal_i: int, side: int) -> tuple[bool, float]:
    adx14 = finite(float(frame["adx14"].iloc[signal_i]))
    atr_bps_value = finite(float(frame["atr_bps"].iloc[signal_i]), default=999.0)
    if adx14 < cfg.min_adx14:
        return False, 0.0
    if atr_bps_value < cfg.min_atr_bps or atr_bps_value > cfg.max_atr_bps:
        return False, 0.0
    slow_now = float(frame[f"ema{cfg.slow_ema}"].iloc[signal_i])
    atr_now = float(frame["atr14"].iloc[signal_i])
    lookback_i = signal_i - cfg.slope_lookback
    if lookback_i < 0 or not np.isfinite(slow_now) or not np.isfinite(atr_now) or atr_now <= 0:
        return False, 0.0
    slow_prev = float(frame[f"ema{cfg.slow_ema}"].iloc[lookback_i])
    slow_slope_atr = side * (slow_now - slow_prev) / atr_now
    if cfg.require_slow_slope and slow_slope_atr < cfg.min_slow_slope_atr:
        return False, slow_slope_atr
    return True, slow_slope_atr


def leg_raw_return(side: int, entry_price: float, exit_price: float) -> float:
    return side * (exit_price / entry_price - 1.0)


def add_exit_leg(
    legs: list[tuple[float, int, float, str]],
    fraction: float,
    exit_i: int,
    exit_price: float,
    reason: str,
) -> None:
    if fraction <= 0:
        return
    legs.append((fraction, exit_i, exit_price, reason))


def simulate_trades(frame: pd.DataFrame, cfg: StrategyConfig) -> list[Trade]:
    signal = cross_signal(frame, cfg)
    signal_i = np.flatnonzero(signal)
    if len(signal_i) == 0:
        return []

    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    fast = frame[f"ema{cfg.fast_ema}"].to_numpy("float64")
    slow = frame[f"ema{cfg.slow_ema}"].to_numpy("float64")
    adx14 = frame["adx14"].to_numpy("float64")
    atr_bps_arr = frame["atr_bps"].to_numpy("float64")
    n = len(frame)
    trades: list[Trade] = []

    for pos, sig_i in enumerate(signal_i):
        side = int(signal[sig_i])
        entry_i = int(sig_i + 1)
        if side == 0 or entry_i >= n - 1:
            continue
        passed, slow_slope_atr = passes_entry_filter(frame, cfg, int(sig_i), side)
        if not passed:
            continue

        next_signal_i = int(signal_i[pos + 1]) if pos + 1 < len(signal_i) else n - 2
        forced_exit_i = min(next_signal_i + 1, n - 1)
        forced_reason = "opposite_cross" if next_signal_i + 1 <= n - 1 else "data_end"
        if cfg.max_hold_bars > 0 and entry_i + cfg.max_hold_bars < forced_exit_i:
            forced_exit_i = entry_i + cfg.max_hold_bars
            forced_reason = "max_hold"
        if forced_exit_i <= entry_i:
            continue

        entry_price = float(open_[entry_i])
        atr_at_signal = float(atr[sig_i])
        stop_price: float | None = None
        if cfg.stop_atr > 0 and np.isfinite(atr_at_signal) and atr_at_signal > 0:
            stop_price = entry_price - side * cfg.stop_atr * atr_at_signal

        remaining = 1.0
        legs: list[tuple[float, int, float, str]] = []
        armed = False
        partial_taken = False
        partial_i: int | None = None
        highest = entry_price
        lowest = entry_price
        mae = 0.0
        mfe = 0.0
        max_dev = -math.inf
        max_drawdown_after_arm = 0.0
        final_exit_i = forced_exit_i
        final_reason = forced_reason

        for bar_i in range(entry_i, forced_exit_i):
            if stop_price is not None:
                stopped, stop_fill, stop_reason = touched_stop(
                    float(open_[bar_i]), float(high[bar_i]), float(low[bar_i]), stop_price, side
                )
                if stopped:
                    add_exit_leg(legs, remaining, int(bar_i), float(stop_fill), stop_reason)
                    remaining = 0.0
                    final_exit_i = int(bar_i)
                    final_reason = stop_reason
                    break

            if side > 0:
                highest = max(highest, float(high[bar_i]))
                mae = min(mae, float(low[bar_i]) / entry_price - 1.0)
                mfe = max(mfe, float(high[bar_i]) / entry_price - 1.0)
            else:
                lowest = min(lowest, float(low[bar_i]))
                mae = min(mae, entry_price / float(high[bar_i]) - 1.0)
                mfe = max(mfe, entry_price / float(low[bar_i]) - 1.0)

            atr_now = float(atr[bar_i])
            if not np.isfinite(atr_now) or atr_now <= 0 or not np.isfinite(fast[bar_i]):
                continue

            dev_atr = side * (float(close[bar_i]) - float(fast[bar_i])) / atr_now
            max_dev = max(max_dev, dev_atr)
            if cfg.arm_dev_atr is not None and dev_atr >= cfg.arm_dev_atr:
                armed = True

            if side > 0:
                drawdown_atr = (highest - float(close[bar_i])) / atr_now
                two_closes_break = (
                    bar_i > 0
                    and float(close[bar_i]) < float(fast[bar_i])
                    and float(close[bar_i - 1]) < float(fast[bar_i - 1])
                )
            else:
                drawdown_atr = (float(close[bar_i]) - lowest) / atr_now
                two_closes_break = (
                    bar_i > 0
                    and float(close[bar_i]) > float(fast[bar_i])
                    and float(close[bar_i - 1]) > float(fast[bar_i - 1])
                )
            if armed:
                max_drawdown_after_arm = max(max_drawdown_after_arm, drawdown_atr)

            weakening = False
            if bar_i > 0 and np.isfinite(fast[bar_i - 1]) and np.isfinite(slow[bar_i - 1]):
                fast_slope = side * (float(fast[bar_i]) - float(fast[bar_i - 1]))
                gap_now = float(fast[bar_i]) - float(slow[bar_i])
                gap_prev = float(fast[bar_i - 1]) - float(slow[bar_i - 1])
                gap_change = side * (gap_now - gap_prev)
                weakening = fast_slope < 0 and gap_change < 0

            full_exit_reason: str | None = None
            if armed and cfg.trail_drawdown_atr is not None and drawdown_atr >= cfg.trail_drawdown_atr:
                full_exit_reason = "armed_peak_drawdown_next_open"
            elif armed and cfg.use_two_closes_fast_break and two_closes_break:
                full_exit_reason = "armed_two_closes_fast_break_next_open"
            elif armed and cfg.use_weakening_fast_gap and weakening:
                full_exit_reason = "armed_fast_gap_weakening_next_open"

            next_open_i = bar_i + 1
            if full_exit_reason is not None and next_open_i <= forced_exit_i and next_open_i < n:
                add_exit_leg(legs, remaining, int(next_open_i), float(open_[next_open_i]), full_exit_reason)
                remaining = 0.0
                final_exit_i = int(next_open_i)
                final_reason = full_exit_reason
                break

            can_take_partial = (
                cfg.partial_dev_atr is not None
                and not partial_taken
                and dev_atr >= cfg.partial_dev_atr
                and remaining > cfg.partial_fraction
                and next_open_i < forced_exit_i
                and next_open_i < n
            )
            if can_take_partial:
                add_exit_leg(
                    legs,
                    cfg.partial_fraction,
                    int(next_open_i),
                    float(open_[next_open_i]),
                    "extension_partial_next_open",
                )
                remaining -= cfg.partial_fraction
                partial_taken = True
                partial_i = int(next_open_i)

        if remaining > 0:
            add_exit_leg(legs, remaining, int(forced_exit_i), float(open_[forced_exit_i]), forced_reason)
            final_exit_i = int(forced_exit_i)
            final_reason = forced_reason

        raw_ret = 0.0
        net_ret = 0.0
        final_exit_price = float(open_[final_exit_i])
        for fraction, exit_i, exit_price, reason in legs:
            raw_leg = leg_raw_return(side, entry_price, exit_price)
            raw_ret += fraction * raw_leg
            net_ret += fraction * (raw_leg - ROUND_TRIP_COST)
            if exit_i == final_exit_i:
                final_exit_price = exit_price
                final_reason = reason

        trades.append(
            Trade(
                config=cfg.name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[final_exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                final_exit_price=float(final_exit_price),
                exit_reason=final_reason,
                bars_held=max(int(final_exit_i - entry_i), 0),
                raw_ret_1x=float(raw_ret),
                net_ret_1x=float(net_ret),
                mae_1x=float(mae - ROUND_TRIP_COST),
                mfe_1x=float(mfe),
                max_dev_atr=float(max_dev) if np.isfinite(max_dev) else 0.0,
                max_drawdown_atr_after_arm=float(max_drawdown_after_arm),
                armed=armed,
                partial_taken=partial_taken,
                partial_fraction=float(cfg.partial_fraction if partial_taken else 0.0),
                partial_ts=pd.Timestamp(ts_ns[partial_i], unit="ns", tz="UTC") if partial_i is not None else None,
                adx14=finite(float(adx14[sig_i])),
                atr_bps=finite(float(atr_bps_arr[sig_i])),
                slow_slope_atr=float(slow_slope_atr),
            )
        )
    return trades


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=1)
    span = end - start
    train_end = start + span * 0.60
    val_end = start + span * 0.80
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "train_first_60pct", "start": start, "end": train_end},
        {"name": "val_next_20pct", "start": train_end, "end": val_end},
        {"name": "fwd_last_20pct", "start": val_end, "end": end},
        {"name": "recent_30d", "start": max(start, end - pd.Timedelta(days=30)), "end": end},
        {"name": "recent_14d", "start": max(start, end - pd.Timedelta(days=14)), "end": end},
    ]


def trades_in_window(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> list[Trade]:
    return [trade for trade in trades if start <= trade.entry_ts < end]


def metrics_for_trades(
    trades: list[Trade],
    *,
    exposure: float,
    period_days: float,
) -> dict[str, Any]:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    net_returns: list[float] = []
    raw_returns: list[float] = []
    gross_wins = 0.0
    gross_losses = 0.0

    for trade in trades:
        mark_ret = exposure * trade.mae_1x
        mark_equity = equity * max(0.0, 1.0 + mark_ret)
        if peak > 0:
            max_dd = min(max_dd, mark_equity / peak - 1.0)
        net_ret = exposure * trade.net_ret_1x
        equity *= max(0.0, 1.0 + net_ret)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, equity / peak - 1.0)
        net_returns.append(net_ret)
        raw_returns.append(exposure * trade.raw_ret_1x)
        if net_ret >= 0:
            gross_wins += net_ret
        else:
            gross_losses += abs(net_ret)

    if not trades:
        return {
            "trades": 0,
            "total_return": 0.0,
            "final_equity": 1.0,
            "annualized_multiple": 1.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "median_trade": 0.0,
            "worst_trade": 0.0,
            "trades_per_day": 0.0,
            "avg_mfe_capture": 0.0,
            "avg_giveback": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "armed_trades": 0,
            "partial_trades": 0,
        }

    final_equity = float(equity)
    annualized = final_equity ** (365.25 / period_days) if period_days > 0 and final_equity > 0 else 0.0
    wins = [value for value in net_returns if value > 0]
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else math.inf
    capture_values = [
        max(raw, 0.0) / max(exposure * trade.mfe_1x, 1e-12)
        for raw, trade in zip(raw_returns, trades, strict=False)
        if trade.mfe_1x > 0
    ]
    giveback_values = [
        max(exposure * trade.mfe_1x - raw, 0.0)
        for raw, trade in zip(raw_returns, trades, strict=False)
        if trade.mfe_1x > 0
    ]
    return {
        "trades": int(len(trades)),
        "total_return": final_equity - 1.0,
        "final_equity": final_equity,
        "annualized_multiple": float(annualized),
        "max_dd": float(max_dd),
        "win_rate": float(len(wins) / len(net_returns)),
        "profit_factor": float(profit_factor),
        "avg_trade": float(np.mean(net_returns)),
        "median_trade": float(np.median(net_returns)),
        "worst_trade": float(np.min(net_returns)),
        "trades_per_day": float(len(trades) / period_days) if period_days > 0 else 0.0,
        "avg_mfe_capture": float(np.mean(capture_values)) if capture_values else 0.0,
        "avg_giveback": float(np.mean(giveback_values)) if giveback_values else 0.0,
        "long_trades": int(sum(1 for trade in trades if trade.side > 0)),
        "short_trades": int(sum(1 for trade in trades if trade.side < 0)),
        "armed_trades": int(sum(1 for trade in trades if trade.armed)),
        "partial_trades": int(sum(1 for trade in trades if trade.partial_taken)),
    }


def exit_reason_counts(trades: list[Trade]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.exit_reason] = counts.get(trade.exit_reason, 0) + 1
    return counts


def score_row(row: dict[str, Any]) -> float:
    full_ann = max(float(row["full_annualized_multiple"]), 1e-9)
    full_pf = float(row["full_profit_factor"])
    if not np.isfinite(full_pf):
        full_pf = 10.0
    val_ret = float(row.get("val_next_20pct_total_return", 0.0))
    fwd_ret = float(row.get("fwd_last_20pct_total_return", 0.0))
    recent_ret = float(row.get("recent_30d_total_return", 0.0))
    dd_penalty = max(0.0, abs(float(row["full_max_dd"])) - abs(MAX_PAPER_DRAWDOWN)) * 8.0
    low_trade_penalty = max(0, MIN_PAPER_TRADES - int(row["full_trades"])) * 0.08
    return (
        math.log(full_ann)
        + min(full_pf, 5.0) * 0.7
        + float(row["full_win_rate"])
        + val_ret * 2.0
        + fwd_ret * 3.0
        + recent_ret
        - dd_penalty
        - low_trade_penalty
    )


def paper_candidate_pass(row: dict[str, Any]) -> bool:
    return (
        int(row["full_trades"]) >= MIN_PAPER_TRADES
        and float(row["full_total_return"]) > 0
        and float(row["full_profit_factor"]) >= MIN_PAPER_PROFIT_FACTOR
        and float(row["full_win_rate"]) >= MIN_PAPER_WIN_RATE
        and float(row["full_max_dd"]) >= MAX_PAPER_DRAWDOWN
        and int(row["val_next_20pct_trades"]) >= 3
        and int(row["fwd_last_20pct_trades"]) >= 3
        and float(row["val_next_20pct_total_return"]) >= 0
        and float(row["fwd_last_20pct_total_return"]) >= 0
        and float(row["recent_30d_total_return"]) >= 0
    )


def row_for_config(
    frame: pd.DataFrame,
    cfg: StrategyConfig,
    trades: list[Trade],
    slices: list[dict[str, Any]],
    exposure: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row: dict[str, Any] = {
        **asdict(cfg),
        "exposure": exposure,
        "cost_bps_round_trip": ROUND_TRIP_COST * 10_000.0,
    }
    slice_rows: list[dict[str, Any]] = []
    for item in slices:
        name = str(item["name"])
        start = pd.Timestamp(item["start"])
        end = pd.Timestamp(item["end"])
        window_trades = trades_in_window(trades, start, end)
        period_days = max((end - start).total_seconds() / 86_400.0, 1 / 1440.0)
        metrics = metrics_for_trades(window_trades, exposure=exposure, period_days=period_days)
        for key, value in metrics.items():
            row[f"{name}_{key}"] = value
        slice_row = {
            "name": cfg.name,
            "exit_model": cfg.exit_model,
            "filter_name": cfg.filter_name,
            "fast_ema": cfg.fast_ema,
            "slow_ema": cfg.slow_ema,
            "exposure": exposure,
            "slice": name,
            "start": start,
            "end": end,
            **metrics,
        }
        slice_rows.append(slice_row)

    row["exit_reason_counts"] = json.dumps(exit_reason_counts(trades), ensure_ascii=False, sort_keys=True)
    row["score"] = score_row(row)
    row["paper_candidate_pass"] = paper_candidate_pass(row)
    return row, slice_rows


def monthly_rows(trades_by_config: dict[str, list[Trade]], top_rows: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in top_rows.to_dict(orient="records"):
        name = str(item["name"])
        exposure = float(item["exposure"])
        trades = trades_by_config.get(name, [])
        by_month: dict[str, list[Trade]] = {}
        for trade in trades:
            by_month.setdefault(trade.entry_ts.strftime("%Y-%m"), []).append(trade)
        for month, month_trades in sorted(by_month.items()):
            start = min(trade.entry_ts for trade in month_trades)
            end = max(trade.exit_ts for trade in month_trades) + pd.Timedelta(minutes=1)
            period_days = max((end - start).total_seconds() / 86_400.0, 1 / 1440.0)
            rows.append(
                {
                    "name": name,
                    "fast_ema": int(item["fast_ema"]),
                    "slow_ema": int(item["slow_ema"]),
                    "exit_model": str(item["exit_model"]),
                    "filter_name": str(item["filter_name"]),
                    "exposure": exposure,
                    "month": month,
                    **metrics_for_trades(month_trades, exposure=exposure, period_days=period_days),
                }
            )
    return rows


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        rows.append(
            {
                "config": trade.config,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": "long" if trade.side > 0 else "short",
                "entry_price": trade.entry_price,
                "final_exit_price": trade.final_exit_price,
                "exit_reason": trade.exit_reason,
                "bars_held": trade.bars_held,
                "raw_ret_1x": trade.raw_ret_1x,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "max_dev_atr": trade.max_dev_atr,
                "max_drawdown_atr_after_arm": trade.max_drawdown_atr_after_arm,
                "armed": trade.armed,
                "partial_taken": trade.partial_taken,
                "partial_fraction": trade.partial_fraction,
                "partial_ts": trade.partial_ts,
                "adx14": trade.adx14,
                "atr_bps": trade.atr_bps,
                "slow_slope_atr": trade.slow_slope_atr,
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 15) -> list[str]:
    if frame.empty:
        return ["_none_"]
    display = frame.head(limit).copy()
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [header, sep]
    for _, item in display.iterrows():
        values: list[str] = []
        for column in columns:
            value = item[column]
            if isinstance(value, (float, np.floating)):
                if column.endswith("return") or column.endswith("max_dd") or column.endswith("win_rate"):
                    values.append(f"`{pct(float(value))}`")
                elif "annualized" in column:
                    values.append(f"`{mult(float(value))}`")
                elif "profit_factor" in column:
                    values.append(f"`{num(float(value))}`")
                else:
                    values.append(f"`{num(float(value))}`")
            else:
                values.append(f"`{value}`")
        rows.append("| " + " | ".join(values) + " |")
    return rows


def best_by_group(summary: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if summary.empty:
        return summary
    return (
        summary.sort_values(["paper_candidate_pass", "score"], ascending=[False, False])
        .groupby(group_columns, as_index=False)
        .head(1)
        .reset_index(drop=True)
    )


def render_markdown(
    summary: pd.DataFrame,
    monthly: pd.DataFrame,
    quality: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    summary = summary.copy()
    summary["exit_family"] = summary["exit_model"].str.slice(0, 1).map(
        {
            "A": "A_cross_only",
            "B": "B_deviation_trail",
            "C": "C_staged_partial",
            "D": "D_exhaustion_confirm",
        }
    )
    paper = summary.loc[summary["paper_candidate_pass"].eq(True)].sort_values("score", ascending=False)
    top = paper.head(20) if not paper.empty else summary.sort_values("score", ascending=False).head(20)
    pair_surface = best_by_group(summary, ["fast_ema", "slow_ema"]).sort_values("score", ascending=False)
    model_surface = best_by_group(summary, ["exit_family"]).sort_values("score", ascending=False)
    filter_surface = best_by_group(summary, ["filter_name"]).sort_values("score", ascending=False)
    ema_21_96_focus = summary.loc[(summary["fast_ema"] == 21) & (summary["slow_ema"] == 96)].sort_values(
        "full_total_return", ascending=False
    )

    lines = [
        f"# HYPE 1m EMA deviation take-profit diagnostic {RUN_DATE}",
        "",
        "Family id: `HYPE-1M-EMA-Crossover`",
        "",
        "Status: diagnostic only. This is a new exit-mechanics study for the `1m` EMA-cross family, not a live approval.",
        "",
        "## 数据质量",
        "",
        f"- Normalized OHLCV: `{quality['normalized_file_count']}` 个日分区，`{quality['rows']}` 根 K。",
        f"- Raw OHLCV: `{quality['raw_ohlcv_file_count']}` 个日分区，`{quality['raw_rows']}` 根 K。",
        f"- 时间范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 连续性：expected `{quality['expected_bars']}`，missing `{quality['missing_bars']}`，duplicate `{quality['duplicate_ts']}`。",
        f"- `is_closed`：`{quality['is_closed_counts']}`。",
        f"- `source`：`{quality['source_counts']}`。",
        f"- OHLC/VWAP/volume hard violations：`{quality['ohlcv_violations']}`。",
        f"- Raw/normalized alignment：`{quality['raw_normalized_alignment']}`。",
        "",
        "## 策略定义",
        "",
        "- 入场：快 EMA 上穿慢 EMA，下一根 `1m` open 做多；快 EMA 下穿慢 EMA，下一根 open 做空。",
        "- EMA 组合：`8/21`、`13/48`、`21/55`、`21/72`、`21/96`、`30/120`。",
        "- 核心偏离变量：多头 `dev = (close - fast_ema) / ATR14`，空头镜像为 `dev = (fast_ema - close) / ATR14`。",
        "- 核心回撤变量：多头 `drawdown = (highest_since_entry - close) / ATR14`，空头镜像为 `drawdown = (close - lowest_since_entry) / ATR14`。",
        "- B 版：`dev` 达到阈值后 arm；arm 后从持仓极值回撤达到阈值，下一根 open 全平。",
        "- C 版：极端偏离先平 `50%`；剩余仓位继续用 arm 后高低点回撤止盈。",
        "- D 版：B 版基础上加入连续两根收回快线另一侧、快线斜率与 EMA gap 同时转弱的衰竭确认。",
        "",
        "## 执行模型",
        "",
        "- 信号、arm、衰竭确认都只使用已收盘 K；对应动作在下一根 open 执行。",
        "- ATR 硬止损按入场前已知的 `ATR14` 设置；open 穿越 stop 时按 open 市价成交，不按旧 stop 价美化。",
        "- 同一根 K 内，硬止损优先于收盘后的偏离止盈信号。",
        f"- 成本：每次 fill fee `{FEE_BPS_PER_FILL:.2f} bps` + slippage `{SLIPPAGE_BPS_PER_FILL:.2f} bps`；完整进出 round-trip `{ROUND_TRIP_COST * 10_000:.2f} bps`。",
        f"- Exposures evaluated: `{args.exposures}`。",
        "",
        "## 搜索规模",
        "",
        f"- EMA pairs: `{args.ema_pairs}`。",
        f"- Config rows including filters and exposure: `{len(summary)}`。",
        f"- Paper gate: trades >= `{MIN_PAPER_TRADES}`，PF >= `{MIN_PAPER_PROFIT_FACTOR}`，win >= `{MIN_PAPER_WIN_RATE:.0%}`，maxDD >= `{MAX_PAPER_DRAWDOWN:.0%}`，validation/forward/recent slices 不得亏损。",
        f"- 通过 paper gate：`{len(paper)}`。",
        "",
    ]

    if paper.empty:
        lines.append("没有配置通过完整 paper gate；下面列出的是最接近的诊断配置，不能升级为 paper-live 或 live。")
    else:
        lines.append("以下配置通过 paper gate，但仍然只能进入 paper audit；需要 forward window、真实手续费/滑点和 runner 状态机审计后才能继续。")

    table_columns = [
        "name",
        "exposure",
        "full_trades",
        "full_total_return",
        "full_annualized_multiple",
        "full_max_dd",
        "full_win_rate",
        "full_profit_factor",
        "fwd_last_20pct_total_return",
        "recent_30d_total_return",
    ]
    lines.extend(["", "## Top rows", "", *markdown_table(top, table_columns, limit=12), ""])

    surface_columns = [
        "fast_ema",
        "slow_ema",
        "exit_model",
        "filter_name",
        "exposure",
        "full_trades",
        "full_total_return",
        "full_max_dd",
        "full_profit_factor",
        "fwd_last_20pct_total_return",
    ]
    lines.extend(["## EMA pair surface", "", *markdown_table(pair_surface, surface_columns, limit=12), ""])
    lines.extend(["## EMA21/96 focus", "", *markdown_table(ema_21_96_focus, surface_columns, limit=10), ""])

    exit_family_columns = [
        "exit_family",
        "fast_ema",
        "slow_ema",
        "exit_model",
        "filter_name",
        "exposure",
        "full_trades",
        "full_total_return",
        "full_max_dd",
        "full_profit_factor",
        "fwd_last_20pct_total_return",
    ]
    lines.extend(["## Exit family surface", "", *markdown_table(model_surface, exit_family_columns, limit=10), ""])
    lines.extend(["## Filter surface", "", *markdown_table(filter_surface, surface_columns, limit=10), ""])

    if not top.empty and not monthly.empty:
        top_name = str(top.iloc[0]["name"])
        top_monthly = monthly.loc[monthly["name"].eq(top_name)].copy()
        negative_months = int((top_monthly["total_return"] < 0).sum()) if not top_monthly.empty else 0
        lines.extend(["## 月度提示", ""])
        lines.append(f"- top score `{top_name}` 的负收益月份数：`{negative_months}`。")
        if not top_monthly.empty:
            worst = top_monthly.sort_values("total_return").head(1).iloc[0]
            lines.append(
                f"- 最差月份 `{worst['month']}`：return `{pct(float(worst['total_return']))}`，PF `{num(float(worst['profit_factor']))}`，trades `{int(worst['trades'])}`。"
            )

    lines.extend(["", "## 结论", ""])
    if paper.empty:
        lines.append(
            "本轮证明了“先 arm 偏离、再等回撤确认”的出场机制可以被写成 live-executable 状态机，但在当前数据片段中还没有满足稳健 paper gate 的配置。"
        )
    else:
        best = paper.iloc[0]
        lines.append(
            f"本轮最强 paper-audit 诊断行是 `{best['name']}`；它不是 live candidate，只能作为下一轮 forward/audit 的候选。"
        )
    lines.append(
        "重点观察：不要把 `dev >= X ATR` 当成最高点预测；它只应该启动保护状态，真正退出要靠高低点回撤、快线失守或趋势 gap 收窄确认。"
    )

    lines.extend(
        [
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/1m-ema-crossover/scripts/research_hype_1m_ema_deviation_take_profit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Slices CSV：`{SLICES_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
            f"- Top trades CSV：`{TOP_TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)

    ema_pairs = parse_ema_pairs(args.ema_pairs)
    exposures = parse_float_list(args.exposures)
    configs = build_configs(ema_pairs)
    spans = sorted({span for fast, slow in ema_pairs for span in (fast, slow)})

    frame_raw, quality = validate_hype_1m()
    frame = add_features(frame_raw, spans)
    slices = validation_slices(frame)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trades_by_config: dict[str, list[Trade]] = {}

    for idx, cfg in enumerate(configs, start=1):
        trades = simulate_trades(frame, cfg)
        trades_by_config[cfg.name] = trades
        for exposure in exposures:
            row, per_slices = row_for_config(frame, cfg, trades, slices, exposure)
            summary_rows.append(row)
            slice_rows.extend(per_slices)
        if args.progress_every and idx % args.progress_every == 0:
            best_so_far = sorted(summary_rows, key=lambda item: float(item["score"]), reverse=True)[0]
            print(
                f"[{idx}/{len(configs)}] best={best_so_far['name']} "
                f"x={float(best_so_far['exposure']):.1f} "
                f"ret={float(best_so_far['full_total_return']):.3f} "
                f"pf={float(best_so_far['full_profit_factor']):.3f} "
                f"dd={float(best_so_far['full_max_dd']):.3f} "
                f"trades={int(best_so_far['full_trades'])}",
                flush=True,
            )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["paper_candidate_pass", "score"], ascending=[False, False]
    )
    slices_frame = pd.DataFrame(slice_rows)
    monthly = pd.DataFrame(monthly_rows(trades_by_config, summary.head(args.top_keep)))

    summary.to_csv(SUMMARY_PATH, index=False)
    slices_frame.to_csv(SLICES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)

    best_name = str(summary.iloc[0]["name"]) if not summary.empty else ""
    best_trades = trades_by_config.get(best_name, [])
    trades_to_frame(best_trades).to_csv(TOP_TRADES_PATH, index=False)

    payload = {
        "family_id": "HYPE-1M-EMA-Crossover",
        "run_date": RUN_DATE,
        "quality": quality,
        "cost_model": {
            "fee_bps_per_fill": FEE_BPS_PER_FILL,
            "slippage_bps_per_fill": SLIPPAGE_BPS_PER_FILL,
            "round_trip_bps": ROUND_TRIP_COST * 10_000.0,
        },
        "args": vars(args),
        "config_count": int(len(configs)),
        "summary_rows": int(len(summary)),
        "paper_candidate_pass_count": int(summary["paper_candidate_pass"].sum()) if not summary.empty else 0,
        "top_rows": summary.head(40).to_dict(orient="records"),
        "paths": {
            "summary": str(SUMMARY_PATH),
            "slices": str(SLICES_PATH),
            "monthly": str(MONTHLY_PATH),
            "top_trades": str(TOP_TRADES_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=json_default))
    MARKDOWN_PATH.write_text(render_markdown(summary, monthly, quality, args))

    print(f"wrote {MARKDOWN_PATH}")
    print(f"paper_candidate_pass_count={payload['paper_candidate_pass_count']}")
    if not summary.empty:
        top = summary.iloc[0]
        print(
            "top="
            f"{top['name']} x={float(top['exposure']):.1f} "
            f"ann={float(top['full_annualized_multiple']):.3f} "
            f"ret={float(top['full_total_return']):.3f} "
            f"pf={float(top['full_profit_factor']):.3f} "
            f"win={float(top['full_win_rate']):.3f} "
            f"dd={float(top['full_max_dd']):.3f} "
            f"trades={int(top['full_trades'])}"
        )


if __name__ == "__main__":
    main()
