from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MANIFEST_PATH = ARTIFACT_DIR / "hype_d15_hto_dataset_freeze_2026-07-29.json"
SNAPSHOT_PATH = ARTIFACT_DIR / "hype_d15_hto_frozen_15m_2026-07-29.parquet"
FUNDING_PATH = ARTIFACT_DIR / "hype_d15_hto_frozen_funding_2026-07-29.parquet"

BASE_FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
HOURS_PER_YEAR = 365.25 * 24.0

DAILY_MODES = {
    0: "ema_momentum_agreement",
    1: "ema_momentum_dmi_vote",
    2: "donchian_state_plus_ema",
    3: "supertrend_plus_ema",
    4: "five_factor_vote",
    5: "donchian_state_only",
    6: "four_factor_unanimous",
}
ENTRY_MODES = {
    0: "donchian_breakout",
    1: "ema_pullback_reclaim",
    2: "rsi_recovery",
    3: "keltner_breakout",
    4: "normalized_momentum",
    5: "range_expansion_breakout",
}
DIRECTIONS = {0: "both", 1: "long_only", 2: "short_only"}
EXIT_MODES = {
    0: "risk_only",
    1: "micro_ema_flip",
    2: "daily_flip",
    3: "daily_or_micro_flip",
    4: "donchian_exit",
}

DAILY_EMA_SPANS = (3, 5, 8, 10, 15, 20, 30, 40, 60, 90)
DAILY_MOM_WINDOWS = (3, 5, 8, 10, 15, 20, 30, 40, 60)
DAILY_ADX_WINDOWS = (5, 7, 10, 14, 20)
DAILY_CHANNEL_WINDOWS = (3, 5, 7, 10, 15, 20, 30, 40, 60)
DAILY_ATR_WINDOWS = (5, 7, 10, 14, 20)
SUPERTREND_MULTIPLIERS = (1.5, 2.0, 2.5, 3.0, 4.0)

MICRO_EMA_SPANS = (8, 12, 16, 24, 32, 48, 72, 96, 144, 192, 288, 384)
MICRO_WINDOWS = (8, 12, 16, 24, 32, 48, 72, 96, 144, 192)
MICRO_ATR_WINDOWS = (14, 28, 48, 96, 192)
RSI_WINDOWS = (6, 9, 14, 21, 28)


@dataclass(frozen=True, slots=True)
class Config:
    daily_mode: int
    direction: int
    daily_fast: int
    daily_slow: int
    daily_mom_window: int
    daily_adx_window: int
    daily_adx_min: float
    daily_channel_window: int
    daily_atr_window: int
    daily_supertrend_mult: float
    daily_vote_min: int
    entry_mode: int
    micro_fast: int
    micro_slow: int
    entry_window: int
    exit_window: int
    atr_window: int
    micro_adx_min: float
    rvol_min: float
    rsi_window: int
    rsi_trigger: float
    rsi_reclaim: float
    pullback_atr: float
    breakout_atr: float
    expansion_min: float
    sl_atr: float
    tp_atr: float
    trail_activation_atr: float
    trail_atr: float
    breakeven_trigger_atr: float
    max_hold_bars: int
    cooldown_bars: int
    leverage: float
    exit_mode: int

    def validate(self) -> None:
        if self.daily_mode not in DAILY_MODES:
            raise ValueError("unknown daily_mode")
        if self.entry_mode not in ENTRY_MODES:
            raise ValueError("unknown entry_mode")
        if self.direction not in DIRECTIONS:
            raise ValueError("unknown direction")
        if self.exit_mode not in EXIT_MODES:
            raise ValueError("unknown exit_mode")
        if self.daily_fast >= self.daily_slow:
            raise ValueError("daily_fast must be below daily_slow")
        if self.micro_fast >= self.micro_slow:
            raise ValueError("micro_fast must be below micro_slow")
        if not 0.0 < self.leverage <= 3.0:
            raise ValueError("leverage must be in (0, 3]")
        if self.sl_atr <= 0.0 or self.trail_atr <= 0.0:
            raise ValueError("stop distances must be positive")
        if self.rsi_trigger > self.rsi_reclaim:
            raise ValueError("rsi_trigger must be <= rsi_reclaim")

    @property
    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


@dataclass(slots=True)
class FeatureBook:
    ts: pd.DatetimeIndex
    terminal_ts: pd.Timestamp
    source_start: pd.Timestamp
    selection_end: pd.Timestamp
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    ema: dict[int, np.ndarray]
    atr: dict[int, np.ndarray]
    adx: np.ndarray
    rsi: dict[int, np.ndarray]
    rvol: np.ndarray
    prior_high: dict[int, np.ndarray]
    prior_low: dict[int, np.ndarray]
    momentum_atr: dict[tuple[int, int], np.ndarray]
    tr_over_atr: dict[int, np.ndarray]
    funding_by_bar: np.ndarray
    daily_ema: dict[int, np.ndarray]
    daily_momentum: dict[int, np.ndarray]
    daily_adx: dict[int, np.ndarray]
    daily_dmi_diff: dict[int, np.ndarray]
    daily_breakout_state: dict[int, np.ndarray]
    daily_supertrend_state: dict[tuple[int, float], np.ndarray]

    @property
    def rows(self) -> int:
        return len(self.ts)


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    equity_path: list[dict[str, Any]]


def config_from_dict(payload: dict[str, Any]) -> Config:
    fields = set(Config.__dataclass_fields__)
    return Config(**{key: payload[key] for key in fields})


def config_dict(config: Config) -> dict[str, Any]:
    result = asdict(config)
    result["daily_mode_name"] = DAILY_MODES[config.daily_mode]
    result["entry_mode_name"] = ENTRY_MODES[config.entry_mode]
    result["direction_name"] = DIRECTIONS[config.direction]
    result["exit_mode_name"] = EXIT_MODES[config.exit_mode]
    return result


def config_sha256(config: Config) -> str:
    canonical = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def replace_config(config: Config, **changes: Any) -> Config:
    return replace(config, **changes)


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest["quality"]["blocker_count"]:
        raise RuntimeError("frozen dataset contains quality blockers")
    if manifest["freeze_contract"]["locked_oos_performance_accessed"]:
        raise RuntimeError("dataset manifest says locked OOS was already accessed")
    if hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest() != manifest["artifacts"]["snapshot_sha256"]:
        raise RuntimeError("frozen snapshot hash mismatch")
    if hashlib.sha256(FUNDING_PATH.read_bytes()).hexdigest() != manifest["artifacts"]["funding_sha256"]:
        raise RuntimeError("frozen funding hash mismatch")
    return manifest


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    return (
        pd.Series(values)
        .ewm(span=span, adjust=False, min_periods=span)
        .mean()
        .to_numpy("float64")
    )


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
    prior_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prior_close), np.abs(low - prior_close)))
    return (
        pd.Series(tr)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )


def _adx_dmi(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int
) -> tuple[np.ndarray, np.ndarray]:
    up = np.r_[np.nan, np.diff(high)]
    down = np.r_[np.nan, -np.diff(low)]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    atr = _atr(high, low, close, window)
    plus = (
        100
        * pd.Series(plus_dm)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
        / atr
    )
    minus = (
        100
        * pd.Series(minus_dm)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
        / atr
    )
    denominator = plus + minus
    dx = 100 * np.abs(plus - minus) / np.where(denominator == 0, np.nan, denominator)
    adx = (
        pd.Series(dx)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )
    return adx, plus - minus


def _rsi(values: np.ndarray, window: int) -> np.ndarray:
    delta = np.r_[np.nan, np.diff(values)]
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = (
        pd.Series(gain)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )
    avg_loss = (
        pd.Series(loss)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )
    rs = avg_gain / np.where(avg_loss == 0, np.nan, avg_loss)
    result = 100 - 100 / (1 + rs)
    result[(avg_loss == 0) & (avg_gain > 0)] = 100.0
    result[(avg_loss == 0) & (avg_gain == 0)] = 50.0
    return result


def _prior_roll(values: np.ndarray, window: int, kind: str) -> np.ndarray:
    roll = pd.Series(values).shift(1).rolling(window, min_periods=window)
    return (roll.max() if kind == "max" else roll.min()).to_numpy("float64")


def _breakout_state(
    close: np.ndarray, high: np.ndarray, low: np.ndarray, window: int
) -> np.ndarray:
    upper = _prior_roll(high, window, "max")
    lower = _prior_roll(low, window, "min")
    state = np.zeros(len(close), dtype="int8")
    current = 0
    for index in range(len(close)):
        if np.isfinite(upper[index]) and close[index] > upper[index]:
            current = 1
        elif np.isfinite(lower[index]) and close[index] < lower[index]:
            current = -1
        state[index] = current
    return state


def _supertrend_state(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    multiplier: float,
) -> np.ndarray:
    midpoint = (high + low) / 2.0
    upper_basic = midpoint + multiplier * atr
    lower_basic = midpoint - multiplier * atr
    upper = upper_basic.copy()
    lower = lower_basic.copy()
    state = np.zeros(len(close), dtype="int8")
    current = 0
    for index in range(1, len(close)):
        if not np.isfinite(upper_basic[index]):
            continue
        upper[index] = (
            upper_basic[index]
            if upper_basic[index] < upper[index - 1] or close[index - 1] > upper[index - 1]
            else upper[index - 1]
        )
        lower[index] = (
            lower_basic[index]
            if lower_basic[index] > lower[index - 1] or close[index - 1] < lower[index - 1]
            else lower[index - 1]
        )
        if current <= 0 and close[index] > upper[index - 1]:
            current = 1
        elif current >= 0 and close[index] < lower[index - 1]:
            current = -1
        state[index] = current
    return state


def _map_prior_daily(
    values: np.ndarray, daily_index: pd.DatetimeIndex, bar_ts: pd.DatetimeIndex
) -> np.ndarray:
    series = pd.Series(values, index=daily_index)
    prior_days = bar_ts.floor("D") - pd.Timedelta(days=1)
    return series.reindex(prior_days).to_numpy()


def _funding_by_bar(ts: pd.DatetimeIndex, funding: pd.DataFrame) -> np.ndarray:
    event_ts = pd.DatetimeIndex(funding["ts"]).as_unit("ns").asi8
    rates = funding["funding_rate"].to_numpy("float64")
    opens = ts.as_unit("ns").asi8
    closes = (ts + pd.Timedelta(minutes=15)).as_unit("ns").asi8
    output = np.zeros(len(ts), dtype="float64")
    for index, (left_ts, right_ts) in enumerate(zip(opens, closes, strict=True)):
        left = int(np.searchsorted(event_ts, left_ts, side="left"))
        right = int(np.searchsorted(event_ts, right_ts, side="left"))
        if right > left:
            output[index] = float(rates[left:right].sum())
    return output


def build_book(*, include_locked_oos: bool = False) -> FeatureBook:
    manifest = load_manifest()
    frame = pd.read_parquet(SNAPSHOT_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    terminal = pd.Timestamp(manifest["freeze_contract"]["data_terminal_exclusive"])
    oos_start = pd.Timestamp(manifest["freeze_contract"]["locked_oos_start_inclusive"])
    if not include_locked_oos:
        frame = frame.loc[frame["ts"] < oos_start].copy()
        terminal = oos_start
    expected_rows = manifest["rows"]["all" if include_locked_oos else "prefit"]
    if len(frame) != expected_rows:
        raise RuntimeError(f"frozen row mismatch: {len(frame)} != {expected_rows}")
    frame = frame.sort_values("ts").reset_index(drop=True)

    ts = pd.DatetimeIndex(frame["ts"])
    open_values = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    volume = frame["volume"].to_numpy("float64")

    ema = {window: _ema(close, window) for window in MICRO_EMA_SPANS}
    atr = {window: _atr(high, low, close, window) for window in MICRO_ATR_WINDOWS}
    adx = _adx_dmi(high, low, close, 14)[0]
    rsi = {window: _rsi(close, window) for window in RSI_WINDOWS}
    prior_high = {window: _prior_roll(high, window, "max") for window in MICRO_WINDOWS}
    prior_low = {window: _prior_roll(low, window, "min") for window in MICRO_WINDOWS}
    momentum_atr: dict[tuple[int, int], np.ndarray] = {}
    for window in MICRO_WINDOWS:
        delta = close - np.r_[np.full(window, np.nan), close[:-window]]
        for atr_window, atr_values in atr.items():
            momentum_atr[(window, atr_window)] = delta / atr_values
    prior_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prior_close), np.abs(low - prior_close)))
    tr_over_atr = {window: tr / values for window, values in atr.items()}
    rvol = volume / (
        pd.Series(volume).shift(1).rolling(96, min_periods=96).median().to_numpy("float64")
    )

    daily = frame.set_index("ts").resample("1D", label="left", closed="left").agg(
        rows=("close", "size"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    daily = daily.loc[daily["rows"] == 96].copy()
    daily_index = pd.DatetimeIndex(daily.index)
    daily_high = daily["high"].to_numpy("float64")
    daily_low = daily["low"].to_numpy("float64")
    daily_close = daily["close"].to_numpy("float64")
    daily_ema = {
        span: _map_prior_daily(_ema(daily_close, span), daily_index, ts)
        for span in DAILY_EMA_SPANS
    }
    daily_momentum = {
        window: _map_prior_daily(
            daily_close - np.r_[np.full(window, np.nan), daily_close[:-window]],
            daily_index,
            ts,
        )
        for window in DAILY_MOM_WINDOWS
    }
    daily_adx: dict[int, np.ndarray] = {}
    daily_dmi_diff: dict[int, np.ndarray] = {}
    for window in DAILY_ADX_WINDOWS:
        adx_values, dmi_values = _adx_dmi(daily_high, daily_low, daily_close, window)
        daily_adx[window] = _map_prior_daily(adx_values, daily_index, ts)
        daily_dmi_diff[window] = _map_prior_daily(dmi_values, daily_index, ts)
    daily_breakout_state = {
        window: _map_prior_daily(
            _breakout_state(daily_close, daily_high, daily_low, window),
            daily_index,
            ts,
        )
        for window in DAILY_CHANNEL_WINDOWS
    }
    daily_atr_raw = {
        window: _atr(daily_high, daily_low, daily_close, window)
        for window in DAILY_ATR_WINDOWS
    }
    daily_supertrend_state = {
        (window, multiplier): _map_prior_daily(
            _supertrend_state(
                daily_high,
                daily_low,
                daily_close,
                daily_atr_raw[window],
                multiplier,
            ),
            daily_index,
            ts,
        )
        for window in DAILY_ATR_WINDOWS
        for multiplier in SUPERTREND_MULTIPLIERS
    }

    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.loc[funding["ts"] < terminal].sort_values("ts")
    return FeatureBook(
        ts=ts,
        terminal_ts=terminal,
        source_start=pd.Timestamp(ts[0]),
        selection_end=oos_start,
        open=open_values,
        high=high,
        low=low,
        close=close,
        volume=volume,
        ema=ema,
        atr=atr,
        adx=adx,
        rsi=rsi,
        rvol=rvol,
        prior_high=prior_high,
        prior_low=prior_low,
        momentum_atr=momentum_atr,
        tr_over_atr=tr_over_atr,
        funding_by_bar=_funding_by_bar(ts, funding),
        daily_ema=daily_ema,
        daily_momentum=daily_momentum,
        daily_adx=daily_adx,
        daily_dmi_diff=daily_dmi_diff,
        daily_breakout_state=daily_breakout_state,
        daily_supertrend_state=daily_supertrend_state,
    )


def daily_direction(
    book: FeatureBook,
    config: Config,
    *,
    disabled_components: frozenset[str] = frozenset(),
) -> np.ndarray:
    fast = book.daily_ema[config.daily_fast]
    slow = book.daily_ema[config.daily_slow]
    ema_sign = np.sign(fast - slow)
    momentum_sign = np.sign(book.daily_momentum[config.daily_mom_window])
    dmi_sign = np.sign(book.daily_dmi_diff[config.daily_adx_window])
    breakout = book.daily_breakout_state[config.daily_channel_window]
    supertrend = book.daily_supertrend_state[
        (config.daily_atr_window, config.daily_supertrend_mult)
    ]
    if "daily_ema" in disabled_components:
        ema_sign = np.zeros(book.rows)
    if "daily_momentum" in disabled_components:
        momentum_sign = np.zeros(book.rows)
    if "daily_dmi" in disabled_components:
        dmi_sign = np.zeros(book.rows)
    if "daily_breakout" in disabled_components:
        breakout = np.zeros(book.rows)
    if "daily_supertrend" in disabled_components:
        supertrend = np.zeros(book.rows)

    direction = np.zeros(book.rows, dtype="int8")
    if config.daily_mode == 0:
        direction[(ema_sign > 0) & (momentum_sign > 0)] = 1
        direction[(ema_sign < 0) & (momentum_sign < 0)] = -1
    elif config.daily_mode == 1:
        score = ema_sign + momentum_sign + dmi_sign
        direction[score >= config.daily_vote_min] = 1
        direction[score <= -config.daily_vote_min] = -1
    elif config.daily_mode == 2:
        direction[(breakout > 0) & (ema_sign > 0)] = 1
        direction[(breakout < 0) & (ema_sign < 0)] = -1
    elif config.daily_mode == 3:
        direction[(supertrend > 0) & (ema_sign > 0)] = 1
        direction[(supertrend < 0) & (ema_sign < 0)] = -1
    elif config.daily_mode == 4:
        score = ema_sign + momentum_sign + dmi_sign + breakout + supertrend
        direction[score >= config.daily_vote_min] = 1
        direction[score <= -config.daily_vote_min] = -1
    elif config.daily_mode == 5:
        direction = np.nan_to_num(breakout, nan=0.0).astype("int8")
    else:
        score = ema_sign + momentum_sign + dmi_sign + breakout
        direction[score >= 4] = 1
        direction[score <= -4] = -1
    adx_ok = book.daily_adx[config.daily_adx_window] >= config.daily_adx_min
    if "daily_adx_filter" not in disabled_components:
        direction[~adx_ok] = 0
    if config.direction == 1:
        direction[direction < 0] = 0
    elif config.direction == 2:
        direction[direction > 0] = 0
    return direction


def _crossed_above(left: np.ndarray, right: np.ndarray | float) -> np.ndarray:
    current = left > right
    return current & ~np.r_[False, current[:-1]]


def _crossed_below(left: np.ndarray, right: np.ndarray | float) -> np.ndarray:
    current = left < right
    return current & ~np.r_[False, current[:-1]]


def build_signals(
    book: FeatureBook,
    config: Config,
    *,
    disabled_components: frozenset[str] = frozenset(),
) -> tuple[np.ndarray, np.ndarray]:
    config.validate()
    regime = daily_direction(book, config, disabled_components=disabled_components)
    close = book.close
    atr = book.atr[config.atr_window]
    fast = book.ema[config.micro_fast]
    slow = book.ema[config.micro_slow]
    micro_long = fast > slow
    micro_short = fast < slow
    if config.entry_mode == 0:
        long_entry = close > book.prior_high[config.entry_window] + config.breakout_atr * atr
        short_entry = close < book.prior_low[config.entry_window] - config.breakout_atr * atr
    elif config.entry_mode == 1:
        prior_close = np.r_[np.nan, close[:-1]]
        prior_fast = np.r_[np.nan, fast[:-1]]
        long_entry = (
            (book.low <= fast + config.pullback_atr * atr)
            & (close > fast)
            & (prior_close <= prior_fast)
        )
        short_entry = (
            (book.high >= fast - config.pullback_atr * atr)
            & (close < fast)
            & (prior_close >= prior_fast)
        )
    elif config.entry_mode == 2:
        rsi = book.rsi[config.rsi_window]
        prior_rsi = np.r_[np.nan, rsi[:-1]]
        long_entry = (prior_rsi <= config.rsi_trigger) & (rsi >= config.rsi_reclaim)
        short_entry = (
            (prior_rsi >= 100 - config.rsi_trigger)
            & (rsi <= 100 - config.rsi_reclaim)
        )
    elif config.entry_mode == 3:
        long_entry = _crossed_above(close, slow + config.expansion_min * atr)
        short_entry = _crossed_below(close, slow - config.expansion_min * atr)
    elif config.entry_mode == 4:
        momentum = book.momentum_atr[(config.entry_window, config.atr_window)]
        long_entry = _crossed_above(momentum, config.expansion_min)
        short_entry = _crossed_below(momentum, -config.expansion_min)
    else:
        expansion = book.tr_over_atr[config.atr_window] >= config.expansion_min
        long_entry = (
            (close > book.prior_high[config.entry_window] + config.breakout_atr * atr)
            & expansion
        )
        short_entry = (
            (close < book.prior_low[config.entry_window] - config.breakout_atr * atr)
            & expansion
        )
    if "primary_entry" in disabled_components:
        long_entry[:] = False
        short_entry[:] = False
    if "micro_trend" not in disabled_components:
        long_entry &= micro_long
        short_entry &= micro_short
    common = np.isfinite(atr) & np.isfinite(book.adx) & np.isfinite(book.rvol)
    if "micro_adx_filter" not in disabled_components:
        common &= book.adx >= config.micro_adx_min
    if "rvol_filter" not in disabled_components:
        common &= book.rvol >= config.rvol_min
    long_entry &= common & (regime == 1)
    short_entry &= common & (regime == -1)
    signal = np.zeros(book.rows, dtype="int8")
    signal[long_entry] = 1
    signal[short_entry] = -1
    return signal, regime


def _adverse_fill(price: float, side: int, *, entry: bool, slippage: float) -> float:
    signed = side if entry else -side
    return float(price * (1 + signed * slippage))


def _metrics(
    *,
    equity_points: list[float],
    trades: list[dict[str, Any]],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    liquidated: bool,
) -> dict[str, Any]:
    equity = np.asarray(equity_points or [1.0], dtype="float64")
    drawdown = equity / np.maximum.accumulate(equity) - 1
    ending = float(equity[-1])
    hours = max(1.0, (end_ts - start_ts).total_seconds() / 3600)
    annual_log = math.log(ending) * HOURS_PER_YEAR / hours if ending > 0 else -math.inf
    annual_factor = math.exp(min(annual_log, 690)) if np.isfinite(annual_log) else 0.0
    returns = np.asarray([trade["net_return"] for trade in trades], dtype="float64")
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    profit_factor = (
        float(wins.sum() / abs(losses.sum()))
        if len(losses) and losses.sum() < 0
        else (float("inf") if len(wins) else 0.0)
    )
    return {
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "hours": hours,
        "ending_equity": ending,
        "total_return": ending - 1,
        "annual_factor": float(annual_factor),
        "max_drawdown": float(-drawdown.min()),
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "trades": int(len(trades)),
        "profit_factor": profit_factor,
        "average_trade": float(returns.mean()) if len(returns) else 0.0,
        "median_trade": float(np.median(returns)) if len(returns) else 0.0,
        "fee_return": float(sum(trade["fee_return"] for trade in trades)),
        "slippage_return": float(sum(trade["slippage_return"] for trade in trades)),
        "funding_return": float(sum(trade["funding_return"] for trade in trades)),
        "liquidated": liquidated,
    }


def run_backtest(
    book: FeatureBook,
    config: Config,
    *,
    start_ts: pd.Timestamp | None = None,
    end_ts: pd.Timestamp | None = None,
    entry_delay_bars: int = 1,
    slippage_per_fill: float = BASE_SLIPPAGE,
    detailed: bool = False,
    disabled_components: frozenset[str] = frozenset(),
) -> BacktestResult:
    config.validate()
    if entry_delay_bars < 1:
        raise ValueError("entry_delay_bars must be >= 1")
    start_ts = pd.Timestamp(start_ts) if start_ts is not None else book.source_start
    end_ts = pd.Timestamp(end_ts) if end_ts is not None else book.terminal_ts
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    start_index = int(np.searchsorted(book.ts.as_unit("ns").asi8, start_ts.value, side="left"))
    end_index = min(
        book.rows,
        int(np.searchsorted(book.ts.as_unit("ns").asi8, end_ts.value, side="left")),
    )
    signal, regime = build_signals(book, config, disabled_components=disabled_components)
    equity = 1.0
    equity_points = [equity]
    trades: list[dict[str, Any]] = []
    equity_path: list[dict[str, Any]] = []
    cursor = start_index
    next_allowed = start_index
    liquidated = False
    while cursor < end_index - entry_delay_bars:
        offset = max(cursor, next_allowed)
        candidates = np.flatnonzero(signal[offset : end_index - entry_delay_bars])
        if not len(candidates):
            break
        signal_index = offset + int(candidates[0])
        entry_index = signal_index + entry_delay_bars
        side = int(signal[signal_index])
        entry_atr = float(book.atr[config.atr_window][signal_index])
        if not np.isfinite(entry_atr) or entry_atr <= 0:
            cursor = signal_index + 1
            continue
        raw_entry = float(book.open[entry_index])
        entry_fill = _adverse_fill(
            raw_entry, side, entry=True, slippage=slippage_per_fill
        )
        entry_equity = equity
        entry_fee = config.leverage * BASE_FEE
        stop = raw_entry - side * config.sl_atr * entry_atr
        target = (
            raw_entry + side * config.tp_atr * entry_atr
            if config.tp_atr > 0
            else (math.inf if side == 1 else -math.inf)
        )
        trailing_stop = stop
        favorable = raw_entry
        funding_sum = 0.0
        pending_exit: str | None = None
        exit_reason = "terminal"
        exit_index = end_index - 1
        raw_exit_used = float(book.close[exit_index])
        exit_fill = raw_exit_used
        entry_after_fee = entry_equity * (1 - entry_fee)
        equity_points.append(entry_after_fee)
        if detailed:
            equity_path.append(
                {"ts": book.ts[entry_index].isoformat(), "equity": entry_after_fee}
            )
        for bar in range(entry_index, end_index):
            raw_exit: float | None = None
            reason: str | None = None
            if pending_exit is not None:
                raw_exit = float(book.open[bar])
                reason = pending_exit
            else:
                bar_open = float(book.open[bar])
                bar_high = float(book.high[bar])
                bar_low = float(book.low[bar])
                if side == 1:
                    if bar_open <= trailing_stop:
                        raw_exit, reason = bar_open, "stop_gap_open"
                    elif bar_low <= trailing_stop:
                        raw_exit, reason = trailing_stop, "stop"
                    elif config.tp_atr > 0 and bar_open >= target:
                        raw_exit, reason = target, "take_profit_gap"
                    elif config.tp_atr > 0 and bar_high >= target:
                        raw_exit, reason = target, "take_profit"
                else:
                    if bar_open >= trailing_stop:
                        raw_exit, reason = bar_open, "stop_gap_open"
                    elif bar_high >= trailing_stop:
                        raw_exit, reason = trailing_stop, "stop"
                    elif config.tp_atr > 0 and bar_open <= target:
                        raw_exit, reason = target, "take_profit_gap"
                    elif config.tp_atr > 0 and bar_low <= target:
                        raw_exit, reason = target, "take_profit"
            if raw_exit is not None and reason is not None:
                raw_exit_used = raw_exit
                exit_fill = _adverse_fill(
                    raw_exit, side, entry=False, slippage=slippage_per_fill
                )
                exit_index = bar
                exit_reason = reason
                break
            funding_sum += float(book.funding_by_bar[bar])
            adverse_mark = float(book.low[bar] if side == 1 else book.high[bar])
            adverse_factor = (
                1
                + config.leverage * side * (adverse_mark / entry_fill - 1)
                - entry_fee
                - config.leverage * side * funding_sum
            )
            marked_equity = entry_equity * adverse_factor
            equity_points.append(max(0.0, marked_equity))
            if detailed:
                equity_path.append(
                    {"ts": book.ts[bar].isoformat(), "equity": max(0.0, marked_equity)}
                )
            if marked_equity <= 0:
                liquidated = True
                equity = 0.0
                exit_index = bar
                exit_fill = adverse_mark
                exit_reason = "liquidation"
                break
            favorable = (
                max(favorable, float(book.high[bar]))
                if side == 1
                else min(favorable, float(book.low[bar]))
            )
            favorable_atr = side * (favorable - raw_entry) / entry_atr
            if favorable_atr >= config.trail_activation_atr:
                proposed = favorable - side * config.trail_atr * entry_atr
                trailing_stop = (
                    max(trailing_stop, proposed)
                    if side == 1
                    else min(trailing_stop, proposed)
                )
            if (
                config.breakeven_trigger_atr > 0
                and favorable_atr >= config.breakeven_trigger_atr
            ):
                trailing_stop = (
                    max(trailing_stop, raw_entry)
                    if side == 1
                    else min(trailing_stop, raw_entry)
                )
            held = bar - entry_index + 1
            if held >= config.max_hold_bars:
                pending_exit = "timeout"
            elif config.exit_mode in {2, 3} and regime[bar] != side:
                pending_exit = "daily_flip"
            elif config.exit_mode in {1, 3}:
                fast = book.ema[config.micro_fast][bar]
                slow = book.ema[config.micro_slow][bar]
                if (side == 1 and fast < slow) or (side == -1 and fast > slow):
                    pending_exit = "micro_ema_flip"
            elif config.exit_mode == 4:
                boundary = (
                    book.prior_low[config.exit_window][bar]
                    if side == 1
                    else book.prior_high[config.exit_window][bar]
                )
                if (side == 1 and book.close[bar] < boundary) or (
                    side == -1 and book.close[bar] > boundary
                ):
                    pending_exit = "donchian_exit"
        if liquidated:
            break
        if exit_reason == "terminal":
            raw_exit_used = float(book.close[exit_index])
            exit_fill = _adverse_fill(
                raw_exit_used, side, entry=False, slippage=slippage_per_fill
            )
        exit_fee = config.leverage * BASE_FEE
        price_return = side * (exit_fill / entry_fill - 1)
        net_return = (
            config.leverage * (price_return - side * funding_sum)
            - entry_fee
            - exit_fee
        )
        equity = entry_equity * (1 + net_return)
        equity_points.append(max(0.0, equity))
        raw_price_return = side * (raw_exit_used / raw_entry - 1)
        trade = {
            "signal_ts": book.ts[signal_index].isoformat(),
            "entry_ts": book.ts[entry_index].isoformat(),
            "exit_ts": book.ts[exit_index].isoformat(),
            "side": side,
            "entry_price": entry_fill,
            "exit_price": exit_fill,
            "entry_atr": entry_atr,
            "leverage": config.leverage,
            "bars_held": int(exit_index - entry_index + 1),
            "exit_reason": exit_reason,
            "net_return": float(net_return),
            "fee_return": float(-(entry_fee + exit_fee)),
            "slippage_return": float(
                config.leverage * (price_return - raw_price_return)
            ),
            "funding_return": float(-config.leverage * side * funding_sum),
            "entry_equity": float(entry_equity),
            "exit_equity": float(equity),
        }
        trades.append(trade)
        if detailed:
            equity_path.append(
                {"ts": book.ts[exit_index].isoformat(), "equity": float(equity)}
            )
        if equity <= 0:
            liquidated = True
            break
        next_allowed = exit_index + 1 + config.cooldown_bars
        cursor = max(exit_index + 1, next_allowed)
    return BacktestResult(
        metrics=_metrics(
            equity_points=equity_points,
            trades=trades,
            start_ts=start_ts,
            end_ts=end_ts,
            liquidated=liquidated,
        ),
        trades=trades,
        equity_path=equity_path,
    )


def trade_signature(result: BacktestResult) -> str:
    canonical = json.dumps(
        [
            (
                trade["signal_ts"],
                trade["entry_ts"],
                trade["exit_ts"],
                trade["side"],
                trade["exit_reason"],
                round(trade["entry_price"], 12),
                round(trade["exit_price"], 12),
                round(trade["net_return"], 12),
            )
            for trade in result.trades
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
