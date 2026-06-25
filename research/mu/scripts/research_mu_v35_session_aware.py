from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import entry_signal
from research_hype_ema_cross_strategy import (
    PERIODS_PER_YEAR,
    SLIPPAGE,
    TRADE_COST,
    build_features,
    true_range,
)
from research_hype_ema_volume_overlay_v8 import v6_variant


DATA_LAKE_ROOT = Path(
    "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = Path("data/normalized/funding_rates/exchange=binance/market_type=perp")
SYMBOL_FILE = "symbol=mu_usdt_usdt.parquet"
SUMMARY_PATH = Path("research/mu/artifacts/mu_usdt_v35_session_aware_summary.json")
TRADES_PATH = Path("research/mu/artifacts/mu_usdt_v35_session_aware_trades.csv")
EQUITY_PATH = Path("research/mu/artifacts/mu_usdt_v35_session_aware_equity.csv")
LEDGER_JSON_PATH = Path("research/mu/artifacts/mu_usdt_v35_session_aware_ledger.json")
LEDGER_CSV_PATH = Path("research/mu/artifacts/mu_usdt_v35_session_aware_ledger.csv")
LEDGER_MD_PATH = Path("research/mu/mu-hype-xfer-session-aware-ledger.md")
ORIGINAL_SESSION_PATH = Path("research/mu/artifacts/mu_hype_v35_original_session_filter.json")
ORIGINAL_SESSION_TRADES_PATH = Path(
    "research/mu/artifacts/mu_hype_v35_original_session_filter_trades.csv"
)

BASELINE_SUMMARY_PATH = Path("research/mu/artifacts/mu_usdt_v35_backtest_summary.json")
ADAPTATION_PATH = Path("research/mu/artifacts/mu_usdt_v35_adaptation_targeted.json")

MAX_ALLOCATION = 2.0
TAKE_PROFIT_ATR = 10.0
HARD_STOP_ATR = 9.0
WARMUP_BARS = 1600
WINDOWS = {
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "ALL": None,
}

BASE_SPEC_META = {
    "time_v6_long": {
        "label": "全时段 V6 long-only",
        "entry_session": "all Binance 15m bars",
        "notes": "只去掉空头，保留 HYPE V6/V35 类连续时间信号。",
    },
    "session_gated_v6_long": {
        "label": "美股常规盘",
        "entry_session": "09:30-16:00 ET weekdays",
        "notes": "只在 regular session 开新仓。",
    },
    "premarket_regular_v6_long": {
        "label": "盘前 + 常规盘",
        "entry_session": "04:00-16:00 ET weekdays",
        "notes": "放开盘前，不放开盘后和夜盘。",
    },
    "extended_day_v6_long": {
        "label": "盘前 + 常规盘 + 盘后",
        "entry_session": "04:00-20:00 ET weekdays",
        "notes": "放开美股 extended day，但不放开 20:00 后夜盘。",
    },
    "regular_overnight_v6_long": {
        "label": "常规盘 + 夜盘",
        "entry_session": "regular session + 20:00-04:00 ET tradifi overnight",
        "notes": "当前主候选：放开夜盘，排除盘前和 16:00-20:00 盘后。",
    },
    "premarket_regular_overnight_v6_long": {
        "label": "盘前 + 常规盘 + 夜盘",
        "entry_session": "04:00-16:00 ET weekdays + tradifi overnight",
        "notes": "排除 16:00-20:00 盘后，但放开盘前和夜盘。",
    },
    "tradifi_24h5_v6_long": {
        "label": "TRADIFI 24/5",
        "entry_session": "Sunday 20:00 through Friday 20:00 ET",
        "notes": "近似放开股票永续可交易 24/5 时段。",
    },
}


@dataclass(frozen=True, slots=True)
class ResearchSpec:
    name: str
    signal_column: str
    atr_column: str
    trend_column: str
    entry_gate_column: str
    cooldown_after_tp: int = 0
    max_allocation: float = MAX_ALLOCATION
    take_profit_atr: float = TAKE_PROFIT_ATR
    hard_stop_atr: float = HARD_STOP_ATR


def load_symbol_data_lake(symbol_file: str = SYMBOL_FILE) -> pd.DataFrame:
    files = sorted(DATA_LAKE_ROOT.rglob(symbol_file))
    if not files:
        raise FileNotFoundError(f"no {symbol_file} parquet files under {DATA_LAKE_ROOT}")

    frame = pd.concat(
        [
            pd.read_parquet(
                path,
                columns=["ts", "open", "high", "low", "close", "volume"],
            )
            for path in files
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame


def load_funding_rates(symbol_file: str = SYMBOL_FILE) -> pd.DataFrame:
    files = sorted(FUNDING_ROOT.rglob(symbol_file))
    if not files:
        return pd.DataFrame(columns=["ts", "funding_rate"])
    frame = pd.concat(
        [
            pd.read_parquet(path, columns=["ts", "funding_rate"])
            for path in files
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.floor("15min")
    frame["funding_rate"] = frame["funding_rate"].astype("float64")
    return (
        frame.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )


def align_funding(frame: pd.DataFrame, funding: pd.DataFrame) -> np.ndarray:
    if funding.empty:
        return np.zeros(len(frame), dtype="float64")
    series = funding.set_index("ts")["funding_rate"]
    aligned = series.reindex(pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))).fillna(0.0)
    return aligned.to_numpy(dtype="float64")


def regular_session_mask(ts: pd.Series) -> np.ndarray:
    local = pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(
        "America/New_York"
    )
    minutes = local.hour * 60 + local.minute
    return (local.weekday < 5) & (minutes >= 9 * 60 + 30) & (minutes < 16 * 60)


def premarket_regular_session_mask(ts: pd.Series) -> np.ndarray:
    local = pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(
        "America/New_York"
    )
    minutes = local.hour * 60 + local.minute
    return (local.weekday < 5) & (minutes >= 4 * 60) & (minutes < 16 * 60)


def extended_day_session_mask(ts: pd.Series) -> np.ndarray:
    local = pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(
        "America/New_York"
    )
    minutes = local.hour * 60 + local.minute
    return (local.weekday < 5) & (minutes >= 4 * 60) & (minutes < 20 * 60)


def tradifi_24h5_session_mask(ts: pd.Series) -> np.ndarray:
    local = pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(
        "America/New_York"
    )
    minutes = local.hour * 60 + local.minute
    weekday = local.weekday
    return (
        ((weekday == 6) & (minutes >= 20 * 60))
        | ((weekday >= 0) & (weekday <= 3))
        | ((weekday == 4) & (minutes < 20 * 60))
    )


def tradifi_overnight_session_mask(ts: pd.Series) -> np.ndarray:
    local = pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(
        "America/New_York"
    )
    minutes = local.hour * 60 + local.minute
    return tradifi_24h5_session_mask(ts) & (
        (minutes >= 20 * 60) | (minutes < 4 * 60)
    )


def _ffill_active(values: pd.Series, length: int) -> np.ndarray:
    return (
        values.reindex(pd.RangeIndex(length))
        .ffill()
        .to_numpy(dtype="float64", na_value=np.nan)
    )


def active_ewm(
    values: np.ndarray,
    update_mask: np.ndarray,
    *,
    span: int,
    min_periods: int | None = None,
) -> np.ndarray:
    min_periods = span if min_periods is None else min_periods
    alpha = 2.0 / (span + 1.0)
    output = np.full(len(values), np.nan, dtype="float64")
    state = np.nan
    count = 0

    for i, value in enumerate(values):
        if update_mask[i] and np.isfinite(value):
            state = value if not np.isfinite(state) else alpha * value + (1.0 - alpha) * state
            count += 1
        if count >= min_periods:
            output[i] = state
    return output


def active_rolling(
    values: np.ndarray,
    update_mask: np.ndarray,
    *,
    window: int,
    agg: str,
    min_periods: int | None = None,
    shift: int = 0,
) -> np.ndarray:
    active_idx = np.flatnonzero(update_mask & np.isfinite(values))
    active_values = pd.Series(values[active_idx], index=active_idx)
    if shift:
        active_values = active_values.shift(shift)
    min_periods = window if min_periods is None else min_periods
    if agg == "mean":
        rolled = active_values.rolling(window, min_periods=min_periods).mean()
    elif agg == "max":
        rolled = active_values.rolling(window, min_periods=min_periods).max()
    elif agg == "min":
        rolled = active_values.rolling(window, min_periods=min_periods).min()
    else:
        raise ValueError(f"unknown active rolling agg: {agg}")
    return _ffill_active(rolled, len(values))


def active_pct_change(
    values: np.ndarray,
    update_mask: np.ndarray,
    *,
    periods: int,
) -> np.ndarray:
    active_idx = np.flatnonzero(update_mask & np.isfinite(values))
    active_values = pd.Series(values[active_idx], index=active_idx)
    changed = active_values.pct_change(periods)
    return _ffill_active(changed, len(values))


def add_session_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    regular = regular_session_mask(result.ts)
    result["regular_session"] = regular
    result["premarket_regular_session"] = premarket_regular_session_mask(result.ts)
    result["extended_day_session"] = extended_day_session_mask(result.ts)
    result["tradifi_overnight_session"] = tradifi_overnight_session_mask(result.ts)
    result["regular_overnight_session"] = (
        result["regular_session"] | result["tradifi_overnight_session"]
    )
    result["premarket_regular_overnight_session"] = (
        result["premarket_regular_session"] | result["tradifi_overnight_session"]
    )
    result["tradifi_24h5_session"] = tradifi_24h5_session_mask(result.ts)

    local = pd.DatetimeIndex(pd.to_datetime(result.ts, utc=True)).tz_convert(
        "America/New_York"
    )
    result["ny_session_date"] = local.date.astype(str)

    typical = (result.high + result.low + result.close) / 3.0
    result["_regular_volume"] = result.volume.where(result.regular_session, 0.0)
    result["_regular_pv"] = (typical * result.volume).where(
        result.regular_session,
        0.0,
    )
    grouped = result.groupby("ny_session_date", sort=False)
    cumulative_volume = grouped["_regular_volume"].cumsum()
    cumulative_pv = grouped["_regular_pv"].cumsum()
    result["session_vwap"] = cumulative_pv / cumulative_volume.replace(0.0, np.nan)
    result = result.drop(columns=["_regular_volume", "_regular_pv"])

    tr = true_range(result.high, result.low, result.close)
    result["tr_pct"] = tr / result.close.replace(0.0, np.nan)
    update_mask = regular & result.close.notna().to_numpy()
    close = result.close.to_numpy("float64")
    high = result.high.to_numpy("float64")
    low = result.low.to_numpy("float64")
    volume = result.volume.to_numpy("float64")
    tr_pct = result.tr_pct.to_numpy("float64")

    result["active_ema96"] = active_ewm(close, update_mask, span=96)
    result["active_ema384"] = active_ewm(close, update_mask, span=384)
    result["active_ema_spread"] = (
        result.active_ema96 / result.active_ema384.replace(0.0, np.nan) - 1.0
    )
    result["active_ema96_slope48"] = active_pct_change(
        result.active_ema96.to_numpy("float64"),
        update_mask,
        periods=48,
    )
    result["active_atr96"] = active_rolling(
        tr_pct,
        update_mask,
        window=96,
        agg="mean",
    )
    result["active_atr672"] = active_rolling(
        tr_pct,
        update_mask,
        window=672,
        agg="mean",
    )
    result["active_atr_ratio96_672"] = (
        result.active_atr96 / result.active_atr672.replace(0.0, np.nan)
    )
    result["active_high48"] = active_rolling(
        high,
        update_mask,
        window=48,
        agg="max",
        shift=1,
    )
    result["active_low48"] = active_rolling(
        low,
        update_mask,
        window=48,
        agg="min",
        shift=1,
    )
    result["active_vol_mean96"] = active_rolling(
        volume,
        update_mask,
        window=96,
        agg="mean",
    )
    result["active_rvol96"] = volume / result.active_vol_mean96.replace(0.0, np.nan) - 1.0
    return result


def add_signal_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    v6_signal = entry_signal(result, v6_variant())
    regular = result.regular_session.to_numpy(dtype=bool)
    base_long = v6_signal == 1

    result["v6_long_signal"] = base_long
    result["v6_regular_long_signal"] = base_long & regular
    result["v6_premarket_regular_long_signal"] = (
        base_long & result.premarket_regular_session.to_numpy(dtype=bool)
    )
    result["v6_extended_day_long_signal"] = (
        base_long & result.extended_day_session.to_numpy(dtype=bool)
    )
    result["v6_regular_overnight_long_signal"] = (
        base_long & result.regular_overnight_session.to_numpy(dtype=bool)
    )
    result["v6_premarket_regular_overnight_long_signal"] = (
        base_long & result.premarket_regular_overnight_session.to_numpy(dtype=bool)
    )
    result["v6_tradifi_24h5_long_signal"] = (
        base_long & result.tradifi_24h5_session.to_numpy(dtype=bool)
    )
    result["v6_long_trend_state"] = result.ema_spread.gt(0.0).fillna(False)

    active_trend = (
        regular
        & result.active_ema_spread.gt(0.0).fillna(False).to_numpy()
        & result.active_ema96_slope48.gt(0.0).fillna(False).to_numpy()
        & result.close.gt(result.active_ema96).fillna(False).to_numpy()
        & result.active_atr_ratio96_672.ge(0.75).fillna(False).to_numpy()
    )
    vwap_ok = result.close.ge(result.session_vwap).fillna(False).to_numpy()
    breakout_ok = result.close.ge(result.active_high48).fillna(False).to_numpy()
    participation_ok = result.active_rvol96.ge(0.25).fillna(False).to_numpy()

    result["active_trend_long_signal"] = active_trend & vwap_ok
    result["active_breakout_long_signal"] = active_trend & vwap_ok & (
        breakout_ok | participation_ok
    )
    result["active_long_trend_state"] = (
        result.active_ema_spread.gt(0.0).fillna(False)
        & result.close.gt(result.active_ema96).fillna(False)
    )
    result["regular_entry_gate"] = regular
    result["premarket_regular_entry_gate"] = result.premarket_regular_session
    result["extended_day_entry_gate"] = result.extended_day_session
    result["regular_overnight_entry_gate"] = result.regular_overnight_session
    result["premarket_regular_overnight_entry_gate"] = (
        result.premarket_regular_overnight_session
    )
    result["tradifi_24h5_entry_gate"] = result.tradifi_24h5_session
    result["always_entry_gate"] = True
    return result


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    return float(drawdown.min())


def buy_hold_metrics(frame: pd.DataFrame, start_i: int) -> dict[str, float]:
    working = frame.iloc[start_i:].copy()
    if working.empty:
        return {"return": 0.0, "max_dd": 0.0}
    equity = working.close / float(working.close.iloc[0])
    return {"return": float(equity.iloc[-1] - 1.0), "max_dd": max_drawdown(equity)}


def hype_v35_signal(frame: pd.DataFrame) -> np.ndarray:
    long_signal = (
        frame.ema_spread.gt(0.0)
        & frame.adx28.ge(28.0)
        & frame.vol_surge192.ge(0.25)
        & frame.h1_adx21.gt(18.0)
        & frame.h1_pdi21.gt(frame.h1_mdi21)
    )
    short_signal = (
        frame.ema_spread.lt(0.0)
        & frame.adx28.ge(36.0)
        & frame.vol_surge192.ge(0.50)
        & frame.h1_ema_spread.lt(0.0)
    )
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[long_signal.fillna(False).to_numpy() & ~short_signal.fillna(False).to_numpy()] = 1
    signal[short_signal.fillna(False).to_numpy() & ~long_signal.fillna(False).to_numpy()] = -1
    return signal


def compact_original_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": result["name"],
        "return_pct": pct(result["return"]),
        "max_dd_pct": pct(result["max_dd"]),
        "sharpe": round(float(result["sharpe"]), 2),
        "closed_trades": int(result["closed_trades"]),
        "win_rate_pct": pct(result["win_rate"]),
        "exit_reasons": result["exit_reasons"],
        "side_summary": result["side_summary"],
    }


def run_hype_v35_original(
    frame: pd.DataFrame,
    *,
    funding_rates: np.ndarray,
    start_i: int,
    entry_gate: np.ndarray | None,
    name: str,
) -> dict[str, Any]:
    ts = pd.to_datetime(frame.ts, utc=True).to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    adx28 = frame.adx28.to_numpy("float64")
    tr_abs = true_range(frame.high, frame.low, frame.close)
    atr_abs = tr_abs.rolling(672, min_periods=672).mean().to_numpy("float64")
    signal = hype_v35_signal(frame)
    gate = np.ones(len(frame), dtype=bool) if entry_gate is None else entry_gate

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_i = -1
    entry_atr = np.nan
    entry_ts: pd.Timestamp | None = None
    equity = 1.0
    hold_bars = 0
    mfe_atr = 0.0
    weak_bars = 0
    pending_exit = ""
    trades: list[dict[str, Any]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_i, entry_atr, entry_ts, equity
        nonlocal hold_bars, mfe_atr, weak_bars, pending_exit
        raw_pnl = pos * (price / entry_px - 1.0)
        pnl_pct = allocation * raw_pnl
        equity *= 1.0 + pnl_pct
        equity *= 1.0 - TRADE_COST * allocation
        trades.append(
            {
                "name": name,
                "entry_i": int(entry_i),
                "exit_i": int(i),
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "entry_atr": float(entry_atr),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(pnl_pct),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "exit_reason": reason,
                "equity_after": float(equity),
            }
        )
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_i = -1
        entry_atr = np.nan
        entry_ts = None
        hold_bars = 0
        mfe_atr = 0.0
        weak_bars = 0
        pending_exit = ""

    for i in range(start_i, len(frame)):
        exited_this_bar = False
        if pos and pending_exit:
            close_position(i, open_[i], pending_exit)
            exited_this_bar = True

        if pos and funding_rates[i] != 0.0:
            equity *= 1.0 - pos * allocation * funding_rates[i]

        if not pos and not exited_this_bar and i >= 2 and gate[i]:
            direction = int(signal[i - 2])
            if direction:
                entry_atr = atr_abs[i - 1]
                if np.isfinite(entry_atr) and entry_atr > 0.0 and open_[i] > 0.0:
                    target = 0.020 if direction > 0 else 0.018
                    next_allocation = min(3.0, target / (entry_atr / open_[i]))
                    if next_allocation > 0.0:
                        pos = direction
                        allocation = float(next_allocation)
                        entry_px = float(open_[i])
                        entry_i = i
                        entry_ts = pd.Timestamp(ts[i])
                        equity *= 1.0 - TRADE_COST * allocation

        if pos:
            hold_bars += 1
            if pos > 0:
                mfe_atr = max(mfe_atr, (high[i] - entry_px) / entry_atr)
                stop_px = entry_px - 7.0 * entry_atr
                take_px = entry_px + 5.0 * entry_atr
                hit_stop = low[i] <= stop_px
                hit_take = high[i] >= take_px
            else:
                mfe_atr = max(mfe_atr, (entry_px - low[i]) / entry_atr)
                stop_px = entry_px + 7.0 * entry_atr
                take_px = entry_px - 5.0 * entry_atr
                hit_stop = high[i] >= stop_px
                hit_take = low[i] <= take_px

            if hit_stop:
                close_position(i, stop_px, "stop_loss")
                curve.append(float(equity))
                continue
            if hit_take:
                close_position(i, take_px, "take_profit")
                curve.append(float(equity))
                continue

            if mfe_atr < 1.5 and np.isfinite(adx28[i]) and adx28[i] < 22.0:
                weak_bars += 1
            else:
                weak_bars = 0
            if mfe_atr < 1.5 and weak_bars >= 3:
                pending_exit = "indicator_exit"
            elif hold_bars >= 384:
                pending_exit = "timeout"

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "name": name,
                "entry_i": int(entry_i),
                "exit_i": int(len(frame) - 1),
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(close[-1]),
                "allocation": float(allocation),
                "entry_atr": float(entry_atr),
                "raw_pnl_pct": float(pos * (close[-1] / entry_px - 1.0)),
                "pnl_pct": float(allocation * pos * (close[-1] / entry_px - 1.0)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "exit_reason": "open_at_end",
                "equity_after": float(equity),
            }
        )

    equity_curve = pd.Series(
        curve,
        index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]),
        name=name,
    )
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype="float64")
    exit_reasons: dict[str, int] = {}
    side_summary: dict[str, dict[str, Any]] = {}
    for trade in closed:
        reason = str(trade["exit_reason"])
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    for side in ("long", "short"):
        side_trades = [trade for trade in closed if trade["side"] == side]
        side_pnl = np.array([float(trade["pnl_pct"]) for trade in side_trades], dtype="float64")
        side_summary[side] = {
            "trades": len(side_trades),
            "return_sum_pct": pct(float(side_pnl.sum())) if len(side_pnl) else 0.0,
            "win_rate_pct": pct(float((side_pnl > 0.0).mean())) if len(side_pnl) else 0.0,
        }
    std = float(returns.std(ddof=0))
    return {
        "name": name,
        "return": float(equity_curve.iloc[-1] - 1.0),
        "max_dd": float(drawdown.min()) if len(drawdown) else 0.0,
        "sharpe": 0.0 if std == 0.0 else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR)),
        "closed_trades": len(closed),
        "win_rate": float((pnl_values > 0.0).mean()) if len(pnl_values) else 0.0,
        "exit_reasons": exit_reasons,
        "side_summary": side_summary,
        "trades_detail": closed,
        "equity_curve": equity_curve,
    }


def run_research_spec(
    frame: pd.DataFrame,
    spec: ResearchSpec,
    *,
    start_i: int,
) -> dict[str, Any]:
    ts = pd.to_datetime(frame.ts, utc=True).to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    signal = frame[spec.signal_column].fillna(False).to_numpy(dtype=bool)
    entry_gate = frame[spec.entry_gate_column].fillna(False).to_numpy(dtype=bool)
    trend = frame[spec.trend_column].fillna(False).to_numpy(dtype=bool)
    atr = frame[spec.atr_column].to_numpy("float64")

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_i = -1
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = False
    hold_bars = 0
    high_water = np.nan
    cooldown = 0
    trades: list[dict[str, Any]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_i, entry_ts, entry_atr, equity
        nonlocal last_mark, pending_entry, hold_bars, high_water, cooldown
        equity *= 1.0 + allocation * (price / last_mark - 1.0)
        equity *= 1.0 - TRADE_COST * allocation
        raw_pnl = price / entry_px - 1.0
        pnl_pct = allocation * raw_pnl
        trades.append(
            {
                "spec": spec.name,
                "entry_i": int(entry_i),
                "exit_i": int(i),
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "side": "long",
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "entry_atr": float(entry_atr),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(pnl_pct),
                "hold_bars": int(hold_bars),
                "mfe_atr": float((high_water / entry_px - 1.0) / entry_atr)
                if np.isfinite(entry_atr) and entry_atr > 0
                else 0.0,
                "exit_reason": reason,
                "equity_after": float(equity),
                "entry_regular_session": bool(frame.regular_session.iloc[entry_i]),
            }
        )
        cooldown = spec.cooldown_after_tp if reason == "take_profit" else 0
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_i = -1
        entry_ts = None
        entry_atr = np.nan
        last_mark = price
        pending_entry = False
        hold_bars = 0
        high_water = np.nan

    for i in range(start_i, len(frame)):
        if i > start_i:
            if pos:
                equity *= 1.0 + allocation * (open_[i] / last_mark - 1.0)
            last_mark = open_[i]

        if pending_entry and not pos:
            pending_entry = False
            if entry_gate[i] and np.isfinite(atr[i - 1]) and atr[i - 1] > 0:
                pos = 1
                allocation = spec.max_allocation
                entry_px = open_[i] * (1.0 + SLIPPAGE)
                entry_i = i
                entry_ts = pd.Timestamp(ts[i])
                entry_atr = float(atr[i - 1])
                high_water = high[i]
                hold_bars = 0
                equity *= 1.0 - TRADE_COST * allocation
                last_mark = entry_px

        if pos:
            hold_bars += 1
            high_water = max(high_water, high[i])
            if np.isfinite(entry_atr) and entry_atr > 0:
                take_px = entry_px * (1.0 + spec.take_profit_atr * entry_atr)
                if high[i] >= take_px:
                    close_position(i, take_px * (1.0 - SLIPPAGE), "take_profit")
                    curve.append(float(equity))
                    continue

                stop_px = entry_px * (1.0 - spec.hard_stop_atr * entry_atr)
                if low[i] <= stop_px:
                    close_position(i, stop_px * (1.0 - SLIPPAGE), "stop_loss")
                    curve.append(float(equity))
                    continue

            equity *= 1.0 + allocation * (close[i] / last_mark - 1.0)
            last_mark = close[i]
            if not trend[i]:
                exit_i = min(i + 1, len(frame) - 1)
                close_position(exit_i, open_[exit_i] * (1.0 - SLIPPAGE), "indicator_exit")
                curve.append(float(equity))
                continue

        if not pos:
            if cooldown > 0:
                cooldown -= 1
            elif signal[i]:
                pending_entry = True

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "spec": spec.name,
                "entry_i": int(entry_i),
                "exit_i": int(len(frame) - 1),
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "side": "long",
                "entry_price": float(entry_px),
                "exit_price": float(close[-1]),
                "allocation": float(allocation),
                "entry_atr": float(entry_atr),
                "raw_pnl_pct": float(close[-1] / entry_px - 1.0),
                "pnl_pct": float(allocation * (close[-1] / entry_px - 1.0)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float((high_water / entry_px - 1.0) / entry_atr)
                if np.isfinite(entry_atr) and entry_atr > 0
                else 0.0,
                "exit_reason": "open_at_end",
                "equity_after": float(equity),
                "entry_regular_session": bool(frame.regular_session.iloc[entry_i]),
            }
        )

    equity_curve = pd.Series(
        curve,
        index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]),
        name=spec.name,
    )
    returns = equity_curve.pct_change().fillna(0.0)
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype="float64")
    exit_reasons: dict[str, int] = {}
    for trade in closed:
        reason = str(trade["exit_reason"])
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    std = float(returns.std(ddof=0))
    signal_after_warmup = signal[start_i:]
    non_regular_signal_after_warmup = signal_after_warmup & ~frame.regular_session.iloc[
        start_i:
    ].to_numpy(dtype=bool)
    return {
        "spec": asdict(spec),
        "return": float(equity_curve.iloc[-1] - 1.0),
        "max_dd": max_drawdown(equity_curve),
        "sharpe": 0.0
        if std == 0.0
        else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR)),
        "closed_trades": len(closed),
        "win_rate": float((pnl_values > 0.0).mean()) if len(pnl_values) else 0.0,
        "avg_trade_pct": float(pnl_values.mean()) if len(pnl_values) else 0.0,
        "median_trade_pct": float(np.median(pnl_values)) if len(pnl_values) else 0.0,
        "best_trade_pct": float(pnl_values.max()) if len(pnl_values) else 0.0,
        "worst_trade_pct": float(pnl_values.min()) if len(pnl_values) else 0.0,
        "exit_reasons": exit_reasons,
        "signal_bars_after_warmup": int(signal_after_warmup.sum()),
        "non_regular_signal_bars_after_warmup": int(non_regular_signal_after_warmup.sum()),
        "regular_entry_trades": int(
            sum(bool(trade["entry_regular_session"]) for trade in closed)
        ),
        "trades_detail": closed,
        "equity_curve": equity_curve,
    }


def pct(value: float) -> float:
    return round(value * 100.0, 2)


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": result["spec"]["name"],
        "return_pct": pct(result["return"]),
        "max_dd_pct": pct(result["max_dd"]),
        "sharpe": round(float(result["sharpe"]), 2),
        "closed_trades": int(result["closed_trades"]),
        "win_rate_pct": pct(result["win_rate"]),
        "avg_trade_pct": pct(result["avg_trade_pct"]),
        "median_trade_pct": pct(result["median_trade_pct"]),
        "best_trade_pct": pct(result["best_trade_pct"]),
        "worst_trade_pct": pct(result["worst_trade_pct"]),
        "signal_bars_after_warmup": int(result["signal_bars_after_warmup"]),
        "non_regular_signal_bars_after_warmup": int(
            result["non_regular_signal_bars_after_warmup"]
        ),
        "regular_entry_trades": int(result["regular_entry_trades"]),
        "exit_reasons": result["exit_reasons"],
    }


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def previous_best_adaptation() -> dict[str, Any] | None:
    payload = load_json(ADAPTATION_PATH)
    if not payload:
        return None
    for item in payload:
        if item.get("name") == "tp10_sl9_max2.0":
            return item
    return None


def window_start_index(
    frame: pd.DataFrame,
    *,
    warmup_i: int,
    window: pd.Timedelta | None,
) -> int:
    if window is None:
        return warmup_i
    ts_series = pd.to_datetime(frame.ts, utc=True)
    window_start = pd.Timestamp(ts_series.iloc[-1]) - window
    candidates = np.flatnonzero(ts_series >= window_start)
    if not len(candidates):
        return warmup_i
    return max(warmup_i, int(candidates[0]))


def make_version_catalog(base_specs: list[ResearchSpec]) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    main_count = 0
    for base_spec in base_specs:
        meta = BASE_SPEC_META[base_spec.name]
        for allocation in (2.0, 3.0):
            main_count += 1
            version = f"V{main_count}"
            spec = ResearchSpec(
                **{
                    **asdict(base_spec),
                    "name": f"{base_spec.name}_tp10_sl9_max{allocation:g}",
                    "max_allocation": allocation,
                }
            )
            catalog.append(
                {
                    "version": version,
                    "branch": "main",
                    "name": spec.name,
                    "label": meta["label"],
                    "entry_session": meta["entry_session"],
                    "notes": meta["notes"],
                    "allocation": allocation,
                    "take_profit_atr": spec.take_profit_atr,
                    "hard_stop_atr": spec.hard_stop_atr,
                    "spec": spec,
                }
            )
    return catalog


def ledger_row(
    *,
    version_meta: dict[str, Any],
    window_label: str,
    frame: pd.DataFrame,
    start_i: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    exit_reasons = dict(result["exit_reasons"])
    return {
        "version": version_meta["version"],
        "name": version_meta["name"],
        "label": version_meta["label"],
        "window": window_label,
        "start": str(pd.Timestamp(frame.ts.iloc[start_i])),
        "end": str(pd.Timestamp(frame.ts.iloc[-1])),
        "entry_session": version_meta["entry_session"],
        "allocation": float(version_meta["allocation"]),
        "take_profit_atr": float(version_meta["take_profit_atr"]),
        "hard_stop_atr": float(version_meta["hard_stop_atr"]),
        "return_pct": pct(result["return"]),
        "max_dd_pct": pct(result["max_dd"]),
        "sharpe": round(float(result["sharpe"]), 2),
        "closed_trades": int(result["closed_trades"]),
        "win_rate_pct": pct(result["win_rate"]),
        "avg_trade_pct": pct(result["avg_trade_pct"]),
        "median_trade_pct": pct(result["median_trade_pct"]),
        "best_trade_pct": pct(result["best_trade_pct"]),
        "worst_trade_pct": pct(result["worst_trade_pct"]),
        "take_profit": int(exit_reasons.get("take_profit", 0)),
        "stop_loss": int(exit_reasons.get("stop_loss", 0)),
        "indicator_exit": int(exit_reasons.get("indicator_exit", 0)),
        "signal_bars": int(result["signal_bars_after_warmup"]),
        "non_regular_signal_bars": int(result["non_regular_signal_bars_after_warmup"]),
        "regular_entry_trades": int(result["regular_entry_trades"]),
        "notes": version_meta["notes"],
    }


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def version_sort_key(version: str) -> tuple[int, int]:
    prefix = version[:1]
    order = {"B": 0, "V": 1}.get(prefix, 9)
    return order, int(version[1:])


def write_markdown_ledger(
    *,
    frame: pd.DataFrame,
    version_catalog: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
) -> None:
    catalog_rows = [
        {
            "版本": item["version"],
            "名称": item["label"],
            "仓位": f"{item['allocation']:g}x",
            "入场时段": item["entry_session"],
            "说明": item["notes"],
        }
        for item in version_catalog
    ]
    all_rows = [row for row in ledger_rows if row["window"] == "ALL"]
    all_rows = sorted(all_rows, key=lambda row: version_sort_key(row["version"]))
    window_rows = sorted(
        ledger_rows,
        key=lambda row: (
            version_sort_key(row["version"]),
            {"1W": 0, "1M": 1, "3M": 2, "ALL": 3}[row["window"]],
        ),
    )
    top_all = sorted(all_rows, key=lambda row: row["return_pct"], reverse=True)[:6]
    content = "\n\n".join(
        [
            "# MUUSDT HYPE V35 Transfer Session-Aware 版本台账",
            (
                "本台账记录 MUUSDT 在 Binance TRADIFI_PERPETUAL 上迁移 HYPE V35/V6 "
                "追趋势内核后的候选版本。所有版本均为 long-only、TP10/SL9，"
                "区别在入场时段和 2x/3x 仓位。"
            ),
            (
                f"数据范围：{pd.Timestamp(frame.ts.iloc[0])} → "
                f"{pd.Timestamp(frame.ts.iloc[-1])}；warmup bars：{WARMUP_BARS}。"
            ),
            "## 版本定义",
            markdown_table(catalog_rows, ["版本", "名称", "仓位", "入场时段", "说明"]),
            "## ALL 窗口排名",
            markdown_table(
                top_all,
                [
                    "version",
                    "label",
                    "allocation",
                    "return_pct",
                    "max_dd_pct",
                    "closed_trades",
                    "win_rate_pct",
                    "take_profit",
                    "stop_loss",
                ],
            ),
            "## 分窗口台账",
            markdown_table(
                window_rows,
                [
                    "version",
                    "label",
                    "window",
                    "return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "closed_trades",
                    "win_rate_pct",
                    "take_profit",
                    "stop_loss",
                    "indicator_exit",
                ],
            ),
            "## 当前结论",
            (
                "- 主 shadow 候选：V1 regular+overnight 2x，ALL 为 "
                "+115.81% / -15.84%，1W/1M/3M 也用于持续观察。"
            ),
            (
                "- 激进观察：V2 regular+overnight 3x，ALL 为 "
                "+205.79% / -22.99%，回撤压力明显高于 V1。"
            ),
            (
                "- 盘前或 24/5 全放开会提高收益，但会把 MDD 拉回 -20% 以上；"
                "当前主线先只保留时段过滤版本。"
            ),
        ]
    )
    LEDGER_MD_PATH.write_text(content + "\n", encoding="utf-8")


def main() -> None:
    raw = load_symbol_data_lake()
    funding = load_funding_rates()
    frame = add_signal_columns(add_session_features(build_features(raw)))
    start_i = min(WARMUP_BARS, len(frame))
    aligned_funding = align_funding(frame, funding)

    original_results = [
        run_hype_v35_original(
            frame,
            funding_rates=aligned_funding,
            start_i=start_i,
            entry_gate=None,
            name="B0_recreated_hype_v35_transfer",
        ),
        run_hype_v35_original(
            frame,
            funding_rates=aligned_funding,
            start_i=start_i,
            entry_gate=frame.tradifi_24h5_session.to_numpy(dtype=bool),
            name="B0_weekend_filtered_hype_v35_transfer",
        ),
    ]

    base_specs = [
        ResearchSpec(
            name="regular_overnight_v6_long",
            signal_column="v6_regular_overnight_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="regular_overnight_entry_gate",
        ),
        ResearchSpec(
            name="session_gated_v6_long",
            signal_column="v6_regular_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="regular_entry_gate",
        ),
        ResearchSpec(
            name="premarket_regular_v6_long",
            signal_column="v6_premarket_regular_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="premarket_regular_entry_gate",
        ),
        ResearchSpec(
            name="extended_day_v6_long",
            signal_column="v6_extended_day_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="extended_day_entry_gate",
        ),
        ResearchSpec(
            name="premarket_regular_overnight_v6_long",
            signal_column="v6_premarket_regular_overnight_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="premarket_regular_overnight_entry_gate",
        ),
        ResearchSpec(
            name="tradifi_24h5_v6_long",
            signal_column="v6_tradifi_24h5_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="tradifi_24h5_entry_gate",
        ),
        ResearchSpec(
            name="time_v6_long",
            signal_column="v6_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="always_entry_gate",
        ),
    ]
    version_catalog = make_version_catalog(base_specs)
    specs = [item["spec"] for item in version_catalog]
    all_results = [
        run_research_spec(frame, spec, start_i=start_i)
        for spec in specs
    ]
    equity_frame = pd.concat(
        [result["equity_curve"] for result in all_results],
        axis=1,
    ).reset_index(names="ts")
    trades = pd.DataFrame(
        [
            trade
            for result in all_results
            for trade in result["trades_detail"]
        ]
    )
    compact = [
        {
            "version": version_catalog[i]["version"],
            **compact_result(result),
            "label": version_catalog[i]["label"],
            "entry_session": version_catalog[i]["entry_session"],
        }
        for i, result in enumerate(all_results)
    ]
    ledger_rows: list[dict[str, Any]] = []
    window_results: dict[str, dict[str, Any]] = {}
    for window_label, window_delta in WINDOWS.items():
        current_start_i = window_start_index(
            frame,
            warmup_i=start_i,
            window=window_delta,
        )
        for version_meta in version_catalog:
            result = run_research_spec(
                frame,
                version_meta["spec"],
                start_i=current_start_i,
            )
            row = ledger_row(
                version_meta=version_meta,
                window_label=window_label,
                frame=frame,
                start_i=current_start_i,
                result=result,
            )
            ledger_rows.append(row)
            window_results[f"{version_meta['version']}:{window_label}"] = {
                **row,
                "exit_reasons": result["exit_reasons"],
            }
    benchmark = buy_hold_metrics(frame, start_i)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES_PATH, index=False)
    equity_frame.to_csv(EQUITY_PATH, index=False)
    pd.DataFrame(
        [
            trade
            for result in original_results
            for trade in result["trades_detail"]
        ]
    ).to_csv(ORIGINAL_SESSION_TRADES_PATH, index=False)
    ORIGINAL_SESSION_PATH.write_text(
        json.dumps(
            {
                "symbol": "MU/USDT:USDT",
                "source_strategy": "HYPE trend-breakout V35 transferred to MU",
                "data": {
                    "rows": int(len(frame)),
                    "start": str(pd.Timestamp(frame.ts.iloc[0])),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                    "warmup_bars": int(start_i),
                    "backtest_start_after_warmup": str(pd.Timestamp(frame.ts.iloc[start_i])),
                },
                "assumptions": {
                    "entry_delay": "K0 signal, K2 open entry",
                    "direction": "long and short",
                    "long_target_atr_pct": 0.020,
                    "short_target_atr_pct": 0.018,
                    "max_allocation": 3.0,
                    "take_profit_atr": 5.0,
                    "hard_stop_atr": 7.0,
                    "indicator_exit": "ADX28 < 22 for 3 bars; disabled after MFE >= 1.5 ATR",
                    "weekend_filter": "no new entries outside Sunday 20:00 to Friday 20:00 ET",
                },
                "results": [compact_original_result(result) for result in original_results],
                "notes": [
                    "This is a HYPE V35 transfer diagnostic, not a MU-specialized V-series candidate.",
                    "Weekend filtering only blocks new entries; existing positions keep full-time TP/SL/indicator management.",
                    "B0_recreated may differ slightly from the stored B0 report if the earlier report used a different slippage or funding convention.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    pd.DataFrame(ledger_rows).to_csv(LEDGER_CSV_PATH, index=False)
    LEDGER_JSON_PATH.write_text(
        json.dumps(
            {
                "symbol": "MU/USDT:USDT",
                "versions": [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "spec"
                    }
                    for item in version_catalog
                ],
                "windows": window_results,
                "rows": ledger_rows,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    write_markdown_ledger(
        frame=frame,
        version_catalog=version_catalog,
        ledger_rows=ledger_rows,
    )
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "symbol": "MU/USDT:USDT",
                "data": {
                    "rows": int(len(frame)),
                    "start": str(pd.Timestamp(frame.ts.iloc[0])),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                    "warmup_bars": int(start_i),
                    "backtest_start_after_warmup": str(pd.Timestamp(frame.ts.iloc[start_i])),
                    "regular_session_bars_after_warmup": int(
                        frame.regular_session.iloc[start_i:].sum()
                    ),
                    "premarket_regular_session_bars_after_warmup": int(
                        frame.premarket_regular_session.iloc[start_i:].sum()
                    ),
                    "extended_day_session_bars_after_warmup": int(
                        frame.extended_day_session.iloc[start_i:].sum()
                    ),
                    "regular_overnight_session_bars_after_warmup": int(
                        frame.regular_overnight_session.iloc[start_i:].sum()
                    ),
                    "premarket_regular_overnight_session_bars_after_warmup": int(
                        frame.premarket_regular_overnight_session.iloc[start_i:].sum()
                    ),
                    "tradifi_24h5_session_bars_after_warmup": int(
                        frame.tradifi_24h5_session.iloc[start_i:].sum()
                    ),
                },
                "assumptions": {
                    "session_timezone": "America/New_York",
                    "entry_sessions": {
                        "regular": "weekday 09:30 <= local time < 16:00",
                        "premarket_regular": "weekday 04:00 <= local time < 16:00",
                        "extended_day": "weekday 04:00 <= local time < 20:00",
                        "regular_overnight": "regular session plus tradifi overnight, excluding premarket and 16:00-20:00 afterhours",
                        "premarket_regular_overnight": "premarket plus regular plus tradifi overnight, excluding 16:00-20:00 afterhours",
                        "tradifi_24h5": "Sunday 20:00 through Friday 20:00 New York time",
                    },
                    "position_side": "long-only",
                    "tested_allocations": [2.0, 3.0],
                    "take_profit_atr": TAKE_PROFIT_ATR,
                    "hard_stop_atr": HARD_STOP_ATR,
                    "fees_and_slippage": {
                        "trade_cost": TRADE_COST,
                        "slippage": SLIPPAGE,
                    },
                },
                "buy_hold_after_warmup": {
                    "return_pct": pct(benchmark["return"]),
                    "max_dd_pct": pct(benchmark["max_dd"]),
                },
                "previous_reports": {
                    "original_v35": load_json(BASELINE_SUMMARY_PATH),
                    "tp10_sl9_max2_adaptation": previous_best_adaptation(),
                },
                "original_hype_v35_session_filter": {
                    "json": str(ORIGINAL_SESSION_PATH),
                    "trades": str(ORIGINAL_SESSION_TRADES_PATH),
                    "results": [
                        compact_original_result(result)
                        for result in original_results
                    ],
                },
                "version_catalog": [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "spec"
                    }
                    for item in version_catalog
                ],
                "variants": compact,
                "ledger": {
                    "json": str(LEDGER_JSON_PATH),
                    "csv": str(LEDGER_CSV_PATH),
                    "markdown": str(LEDGER_MD_PATH),
                },
                "notes": [
                    "time_v6_long keeps the HYPE-style continuous-time EMA/ADX/volume signal and only removes shorts.",
                    "session_gated_v6 blocks new entries outside the US regular session but still uses continuous-time indicators.",
                    "active_time variants update EMA/ATR style state only on US regular-session bars, then allow entries only during that session.",
                    "active_breakout adds either a 48 active-bar high breakout or relative-volume confirmation on top of the active trend gate.",
                    "Exits are still monitored on every Binance 15m bar because after-hours gaps can hit TP/SL.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print(f"wrote={SUMMARY_PATH}")
    print(f"original_session={ORIGINAL_SESSION_PATH}")
    print(f"original_session_trades={ORIGINAL_SESSION_TRADES_PATH}")
    print(f"ledger_json={LEDGER_JSON_PATH}")
    print(f"ledger_csv={LEDGER_CSV_PATH}")
    print(f"ledger_md={LEDGER_MD_PATH}")
    print(f"trades={TRADES_PATH}")
    print(f"equity={EQUITY_PATH}")
    print(pd.DataFrame(compact).to_string(index=False))


if __name__ == "__main__":
    main()
