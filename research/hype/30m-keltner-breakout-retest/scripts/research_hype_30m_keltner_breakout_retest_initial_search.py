from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/30m-keltner-breakout-retest"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_CACHE = (
    ROOT
    / "data/cache/hype_30m_k2_fq_v2_atrvt_off/HYPEUSDT_1m_closed_klines.parquet"
)
FUNDING_CACHE = (
    ROOT / "data/cache/hype_30m_k2_fq_v2_atrvt_off/HYPEUSDT_funding.parquet"
)
RUN_DATE = "2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_initial_search_{RUN_DATE}.json"
SEARCH_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_search_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_candidate_trades_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_oos_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_mc_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_phase_{RUN_DATE}.csv"
ABLATION_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_ablation_{RUN_DATE}.csv"
NEIGHBORHOOD_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_neighborhood_{RUN_DATE}.csv"
SLICES_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_recent_slices_{RUN_DATE}.csv"
STRESS_PATH = ARTIFACT_DIR / f"hype_30m_keltner_breakout_retest_stress_{RUN_DATE}.csv"

FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0004
TRAIN_END = pd.Timestamp("2026-01-31 00:00:00+00:00")
VALIDATION_START = pd.Timestamp("2026-02-14 00:00:00+00:00")
VALIDATION_END = pd.Timestamp("2026-06-30 00:00:00+00:00")
SEED = 20260717
V3_WIN_RATE = 67.94871794871796
V3_MDD = -22.67774230986097


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    keltner_ema: int = 10
    keltner_atr: int = 10
    keltner_mult: float = 2.0
    trend_ema_fast: int = 16
    trend_ema_slow: int = 44
    trend_slope_lag: int = 5
    leverage_atr: int = 84


@dataclass(frozen=True, slots=True)
class RetestConfig:
    max_wait_bars: int
    touch_buffer_atr: float
    mid_tolerance_atr: float
    reclaim_buffer_atr: float
    reclaim_close_location: float
    expansion_lookback: int
    require_directional_candle: bool = True
    atr_cap: float = 0.0125
    side_mode: str = "long"

    @property
    def label(self) -> str:
        return (
            f"wait{self.max_wait_bars}_touch{self.touch_buffer_atr:g}"
            f"_mid{self.mid_tolerance_atr:g}_reclaim{self.reclaim_buffer_atr:g}"
            f"_cl{self.reclaim_close_location:g}_exp{self.expansion_lookback}"
            f"_{self.side_mode}"
        )


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    atr_target_pct: float = 0.027
    max_leverage: float = 3.0
    take_profit_pct: float = 0.10
    stop_loss_pct: float = 0.025
    max_hold_bars: int = 30
    fee_rate: float = FEE_RATE
    slippage_rate: float = SLIPPAGE_RATE
    entry_delay_bars: int = 0


@dataclass(slots=True)
class Result:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series
    slices: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(
        alpha=2 / (window + 1),
        adjust=False,
        min_periods=window,
    ).mean()


def rma(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    m1 = pd.read_parquet(SOURCE_CACHE)
    m1["ts"] = pd.to_datetime(m1["ts"], utc=True)
    m1 = m1.loc[
        (m1["ts"] >= pd.Timestamp("2025-05-30 00:00:00+00:00"))
        & (m1["ts"] < pd.Timestamp("2026-07-13 06:07:00+00:00"))
    ].sort_values("ts")
    timestamps = pd.DatetimeIndex(m1["ts"])
    expected = pd.date_range(timestamps.min(), timestamps.max(), freq="1min")
    quality = {
        "source_path": str(SOURCE_CACHE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE_CACHE.read_bytes()).hexdigest(),
        "source": sorted(m1["source"].dropna().astype(str).unique().tolist()),
        "start": str(timestamps.min()),
        "end": str(timestamps.max()),
        "rows": int(len(m1)),
        "missing_1m_bars": int(len(expected.difference(timestamps))),
        "duplicate_ts_rows": int(timestamps.duplicated().sum()),
        "invalid_ohlc_rows": int(
            (
                m1["high"].lt(m1[["open", "close", "low"]].max(axis=1))
                | m1["low"].gt(m1[["open", "close", "high"]].min(axis=1))
            ).sum()
        ),
        "critical_null_rows": int(
            m1[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum()
        ),
    }
    if any(
        quality[key]
        for key in (
            "missing_1m_bars",
            "duplicate_ts_rows",
            "invalid_ohlc_rows",
            "critical_null_rows",
        )
    ):
        raise RuntimeError(f"data quality blocker: {quality}")
    funding = pd.read_parquet(FUNDING_CACHE)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.loc[
        funding["ts"].between(timestamps.min(), timestamps.max())
    ].sort_values("ts")
    return m1.reset_index(drop=True), funding.reset_index(drop=True), quality


def aggregate(
    m1: pd.DataFrame,
    minutes: int,
    phase_minutes: int,
) -> pd.DataFrame:
    source = m1.set_index("ts").sort_index()
    grouped = source.resample(
        f"{minutes}min",
        origin="epoch",
        offset=pd.Timedelta(minutes=phase_minutes),
        label="left",
        closed="left",
    )
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        minute_count=("open", "count"),
    )
    return bars.loc[bars["minute_count"].eq(minutes)].dropna(
        subset=["open", "high", "low", "close"]
    )


def map_trend(
    signal_bars: pd.DataFrame,
    trend_bars: pd.DataFrame,
    column: str,
    signal_minutes: int = 30,
    trend_minutes: int = 60,
) -> np.ndarray:
    trend_close = (trend_bars.index + pd.Timedelta(minutes=trend_minutes)).to_numpy()
    signal_close = (
        signal_bars.index + pd.Timedelta(minutes=signal_minutes)
    ).to_numpy()
    mapped = np.searchsorted(trend_close, signal_close, side="right") - 1
    output = np.zeros(len(signal_bars), dtype=bool)
    valid = mapped >= 0
    output[valid] = trend_bars[column].fillna(False).to_numpy(bool)[mapped[valid]]
    return output


def build_features(
    signal_bars: pd.DataFrame,
    trend_bars: pd.DataFrame,
    channel: ChannelConfig,
) -> pd.DataFrame:
    frame = signal_bars.copy()
    tr = true_range(frame)
    frame["mid"] = ema(frame["close"], channel.keltner_ema)
    frame["atr10"] = rma(tr, channel.keltner_atr)
    frame["upper"] = frame["mid"] + channel.keltner_mult * frame["atr10"]
    frame["lower"] = frame["mid"] - channel.keltner_mult * frame["atr10"]
    frame["atr84"] = rma(tr, channel.leverage_atr)
    candle_range = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    frame["close_location"] = (frame["close"] - frame["low"]) / candle_range

    trend = trend_bars.copy()
    trend["ema_fast"] = ema(trend["close"], channel.trend_ema_fast)
    trend["ema_slow"] = ema(trend["close"], channel.trend_ema_slow)
    trend["slope"] = trend["ema_slow"] - trend["ema_slow"].shift(
        channel.trend_slope_lag
    )
    trend["long_regime"] = trend["ema_fast"].gt(trend["ema_slow"]) & trend[
        "slope"
    ].gt(0.0)
    trend["short_regime"] = trend["ema_fast"].lt(trend["ema_slow"]) & trend[
        "slope"
    ].lt(0.0)
    frame["long_regime"] = map_trend(frame, trend, "long_regime")
    frame["short_regime"] = map_trend(frame, trend, "short_regime")
    return frame


def direct_breakout_signal(features: pd.DataFrame, side_mode: str) -> np.ndarray:
    long_signal = (
        features["long_regime"]
        & features["close"].gt(features["upper"])
        & features["atr84"].div(features["close"]).le(0.0125)
        & features["close_location"].ge(0.65)
    )
    short_signal = (
        features["short_regime"]
        & features["close"].lt(features["lower"])
        & features["atr84"].div(features["close"]).le(0.0125)
        & features["close_location"].le(0.35)
    )
    signal = np.zeros(len(features), dtype=np.int8)
    if side_mode in {"long", "both"}:
        signal[long_signal.fillna(False).to_numpy()] = 1
    if side_mode in {"short", "both"}:
        signal[short_signal.fillna(False).to_numpy()] = -1
    return signal


def build_retest_signal(features: pd.DataFrame, cfg: RetestConfig) -> tuple[np.ndarray, dict[str, int]]:
    open_ = features["open"].to_numpy("float64")
    high = features["high"].to_numpy("float64")
    low = features["low"].to_numpy("float64")
    close = features["close"].to_numpy("float64")
    mid = features["mid"].to_numpy("float64")
    upper = features["upper"].to_numpy("float64")
    lower = features["lower"].to_numpy("float64")
    atr10 = features["atr10"].to_numpy("float64")
    close_location = features["close_location"].to_numpy("float64")
    long_regime = features["long_regime"].to_numpy(bool)
    short_regime = features["short_regime"].to_numpy(bool)
    signal = np.zeros(len(features), dtype=np.int8)
    setup_side = 0
    setup_i = -1
    touched = False
    diagnostics = {
        "breakout_setups": 0,
        "expired_setups": 0,
        "invalidated_setups": 0,
        "touches": 0,
        "reclaims": 0,
    }

    for i in range(1, len(features)):
        if not np.isfinite(atr10[i]) or atr10[i] <= 0.0:
            continue
        if setup_side:
            age = i - setup_i
            regime_ok = long_regime[i] if setup_side > 0 else short_regime[i]
            invalid = (
                close[i] < mid[i] - cfg.mid_tolerance_atr * atr10[i]
                if setup_side > 0
                else close[i] > mid[i] + cfg.mid_tolerance_atr * atr10[i]
            )
            if not regime_ok or invalid:
                diagnostics["invalidated_setups"] += 1
                setup_side = 0
                touched = False
            elif age > cfg.max_wait_bars:
                diagnostics["expired_setups"] += 1
                setup_side = 0
                touched = False
            else:
                touch_now = (
                    low[i] <= upper[i] + cfg.touch_buffer_atr * atr10[i]
                    and low[i] >= mid[i] - cfg.mid_tolerance_atr * atr10[i]
                    if setup_side > 0
                    else high[i] >= lower[i] - cfg.touch_buffer_atr * atr10[i]
                    and high[i] <= mid[i] + cfg.mid_tolerance_atr * atr10[i]
                )
                if touch_now and not touched:
                    diagnostics["touches"] += 1
                touched |= bool(touch_now)
                expansion_ok = (
                    cfg.expansion_lookback == 0
                    or (
                        i >= cfg.expansion_lookback
                        and np.isfinite(atr10[i - cfg.expansion_lookback])
                        and atr10[i] >= atr10[i - cfg.expansion_lookback]
                    )
                )
                reclaim_level = (
                    upper[i] + cfg.reclaim_buffer_atr * atr10[i]
                    if setup_side > 0
                    else lower[i] - cfg.reclaim_buffer_atr * atr10[i]
                )
                reclaim_price = (
                    close[i] >= reclaim_level
                    if setup_side > 0
                    else close[i] <= reclaim_level
                )
                close_quality = (
                    close_location[i] >= cfg.reclaim_close_location
                    if setup_side > 0
                    else close_location[i] <= 1.0 - cfg.reclaim_close_location
                )
                directional = (
                    close[i] > open_[i] if setup_side > 0 else close[i] < open_[i]
                )
                reclaim = (
                    touched
                    and reclaim_price
                    and close_quality
                    and expansion_ok
                    and (directional or not cfg.require_directional_candle)
                )
                if reclaim:
                    signal[i] = setup_side
                    diagnostics["reclaims"] += 1
                    setup_side = 0
                    touched = False

        if setup_side == 0:
            long_breakout = (
                cfg.side_mode in {"long", "both"}
                and long_regime[i]
                and close[i] > upper[i]
            )
            short_breakout = (
                cfg.side_mode in {"short", "both"}
                and short_regime[i]
                and close[i] < lower[i]
            )
            if long_breakout or short_breakout:
                setup_side = 1 if long_breakout else -1
                setup_i = i
                touched = False
                diagnostics["breakout_setups"] += 1
    return signal, diagnostics


def adverse_fill(price: float, side: int, entry: bool, slippage: float) -> float:
    sign = side if entry else -side
    return float(price * (1.0 + sign * slippage))


def metrics_from_equity(equity: pd.Series, trades: pd.DataFrame) -> dict[str, Any]:
    if equity.empty:
        return {
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "avg_leverage": 0.0,
            "worst_trade_pct": 0.0,
            "exit_counts": {},
        }
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = 0.0
    if not returns.empty and float(returns.std(ddof=1)) > 0.0:
        sharpe = float(
            returns.mean() / returns.std(ddof=1) * np.sqrt(365 * 48)
        )
    drawdown = equity / equity.cummax() - 1.0
    trade_returns = (
        pd.to_numeric(trades["net_account_return_pct"], errors="coerce")
        if not trades.empty
        else pd.Series(dtype="float64")
    )
    wins = trade_returns[trade_returns > 0.0].sum()
    losses = abs(trade_returns[trade_returns < 0.0].sum())
    return {
        "return_pct": float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "sharpe": sharpe,
        "trades": int(len(trades)),
        "win_rate_pct": float(trade_returns.gt(0.0).mean() * 100.0)
        if len(trade_returns)
        else 0.0,
        "profit_factor": float(wins / losses) if losses > 0.0 else float("inf"),
        "avg_leverage": float(trades["leverage"].mean()) if not trades.empty else 0.0,
        "worst_trade_pct": float(trade_returns.min()) if len(trade_returns) else 0.0,
        "exit_counts": {
            str(key): int(value)
            for key, value in trades["exit_reason"].value_counts().sort_index().items()
        }
        if not trades.empty
        else {},
    }


def recent_slices(equity: pd.Series) -> list[dict[str, Any]]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    end = equity.index.max()
    rows = []
    for label, delta in windows.items():
        sliced = equity.loc[equity.index >= end - delta]
        if len(sliced) < 2:
            continue
        drawdown = sliced / sliced.cummax() - 1.0
        rows.append(
            {
                "window": label,
                "start": str(sliced.index.min()),
                "end": str(sliced.index.max()),
                "return_pct": float(
                    (sliced.iloc[-1] / sliced.iloc[0] - 1.0) * 100.0
                ),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
            }
        )
    return rows


def simulate(
    features: pd.DataFrame,
    signal: np.ndarray,
    funding: pd.DataFrame,
    execution: ExecutionConfig,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> Result:
    index = pd.DatetimeIndex(features.index)
    start = pd.Timestamp(start) if start is not None else index.min()
    end = pd.Timestamp(end) if end is not None else index.max() + pd.Timedelta(minutes=30)
    active = np.flatnonzero((index >= start) & (index < end))
    open_ = features["open"].to_numpy("float64")
    high = features["high"].to_numpy("float64")
    low = features["low"].to_numpy("float64")
    close = features["close"].to_numpy("float64")
    atr84 = features["atr84"].to_numpy("float64")
    funding_ns = (
        pd.to_datetime(funding["ts"], utc=True)
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    funding_rate = funding["funding_rate"].to_numpy("float64")
    funding_mark = funding["mark_price"].to_numpy("float64")
    funding_cursor = int(np.searchsorted(funding_ns, start.value, side="left"))
    equity = 1.0
    cash = 1.0
    pending: tuple[int, int] | None = None
    position: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    curve: list[tuple[pd.Timestamp, float]] = []
    rejected_atr = 0
    skipped_position_signals = 0

    for i in active:
        ts = index[i]
        while funding_cursor < len(funding_ns) and funding_ns[funding_cursor] <= ts.value:
            if position is not None and funding_ns[funding_cursor] > position["entry_ts"].value:
                mark = funding_mark[funding_cursor]
                if not np.isfinite(mark) or mark <= 0.0:
                    mark = open_[i]
                payment = (
                    -position["side"]
                    * position["quantity"]
                    * mark
                    * funding_rate[funding_cursor]
                )
                cash += payment
                position["funding_pnl"] += payment
            funding_cursor += 1

        if pending is not None and position is None and i >= pending[1]:
            side = pending[0]
            atr = atr84[i - 1] if i else np.nan
            raw_entry = open_[i]
            if (
                np.isfinite(atr)
                and atr > 0.0
                and atr / raw_entry <= 0.0125
            ):
                entry_fill = adverse_fill(
                    raw_entry,
                    side,
                    True,
                    execution.slippage_rate,
                )
                leverage = min(
                    execution.atr_target_pct / (atr / raw_entry),
                    execution.max_leverage,
                )
                equity_before = equity
                notional = equity_before * leverage
                quantity = notional / entry_fill
                entry_fee = notional * execution.fee_rate
                cash = equity_before - entry_fee
                position = {
                    "side": side,
                    "entry_i": i,
                    "entry_ts": ts,
                    "entry_fill": entry_fill,
                    "raw_entry": raw_entry,
                    "quantity": quantity,
                    "leverage": leverage,
                    "equity_before": equity_before,
                    "entry_fee": entry_fee,
                    "funding_pnl": 0.0,
                    "tp": entry_fill
                    * (1.0 + execution.take_profit_pct * side),
                    "sl": entry_fill
                    * (1.0 - execution.stop_loss_pct * side),
                }
            else:
                rejected_atr += 1
            pending = None

        if position is not None:
            side = int(position["side"])
            stop_open = (
                open_[i] <= position["sl"]
                if side > 0
                else open_[i] >= position["sl"]
            )
            target_open = (
                open_[i] >= position["tp"]
                if side > 0
                else open_[i] <= position["tp"]
            )
            stop_hit = (
                low[i] <= position["sl"]
                if side > 0
                else high[i] >= position["sl"]
            )
            target_hit = (
                high[i] >= position["tp"]
                if side > 0
                else low[i] <= position["tp"]
            )
            exit_reason = None
            raw_exit = None
            if stop_open:
                exit_reason, raw_exit = "stop_gap_open", open_[i]
            elif target_open:
                exit_reason, raw_exit = "target_gap_open", position["tp"]
            elif stop_hit:
                exit_reason, raw_exit = "stop_market", position["sl"]
            elif target_hit:
                exit_reason, raw_exit = "target", position["tp"]
            elif i - position["entry_i"] >= execution.max_hold_bars:
                exit_reason, raw_exit = "time_close", close[i]

            if raw_exit is not None:
                exit_fill = adverse_fill(
                    float(raw_exit),
                    side,
                    False,
                    execution.slippage_rate,
                )
                exit_notional = position["quantity"] * exit_fill
                exit_fee = exit_notional * execution.fee_rate
                gross_pnl = (
                    side
                    * position["quantity"]
                    * (exit_fill - position["entry_fill"])
                )
                equity_after = cash + gross_pnl - exit_fee
                trades.append(
                    {
                        "direction": "long" if side > 0 else "short",
                        "entry_ts": position["entry_ts"],
                        "exit_ts": ts,
                        "entry_fill": position["entry_fill"],
                        "exit_fill": exit_fill,
                        "exit_reason": exit_reason,
                        "hold_bars": i - position["entry_i"],
                        "leverage": position["leverage"],
                        "entry_fee": position["entry_fee"],
                        "exit_fee": exit_fee,
                        "funding_pnl": position["funding_pnl"],
                        "net_account_return_pct": (
                            equity_after / position["equity_before"] - 1.0
                        )
                        * 100.0,
                        "equity_before": position["equity_before"],
                        "equity_after": equity_after,
                    }
                )
                equity = equity_after
                cash = equity_after
                position = None

        marked = (
            equity
            if position is None
            else cash
            + position["side"]
            * position["quantity"]
            * (close[i] - position["entry_fill"])
        )
        curve.append((ts, marked))
        if position is None and signal[i]:
            pending = (
                int(signal[i]),
                i + 1 + execution.entry_delay_bars,
            )
        elif position is not None and signal[i]:
            skipped_position_signals += 1

    if position is not None and len(active):
        i = int(active[-1])
        side = int(position["side"])
        exit_fill = adverse_fill(
            close[i],
            side,
            False,
            execution.slippage_rate,
        )
        exit_notional = position["quantity"] * exit_fill
        exit_fee = exit_notional * execution.fee_rate
        gross_pnl = (
            side * position["quantity"] * (exit_fill - position["entry_fill"])
        )
        equity_after = cash + gross_pnl - exit_fee
        trades.append(
            {
                "direction": "long" if side > 0 else "short",
                "entry_ts": position["entry_ts"],
                "exit_ts": index[i],
                "entry_fill": position["entry_fill"],
                "exit_fill": exit_fill,
                "exit_reason": "window_end",
                "hold_bars": i - position["entry_i"],
                "leverage": position["leverage"],
                "entry_fee": position["entry_fee"],
                "exit_fee": exit_fee,
                "funding_pnl": position["funding_pnl"],
                "net_account_return_pct": (
                    equity_after / position["equity_before"] - 1.0
                )
                * 100.0,
                "equity_before": position["equity_before"],
                "equity_after": equity_after,
            }
        )
        equity = equity_after
        if curve:
            curve[-1] = (curve[-1][0], equity)

    trade_frame = pd.DataFrame(trades)
    equity_curve = pd.Series(dict(curve), dtype="float64").sort_index()
    return Result(
        metrics=metrics_from_equity(equity_curve, trade_frame),
        trades=trade_frame,
        equity=equity_curve,
        slices=recent_slices(equity_curve),
        diagnostics={
            "start": str(start),
            "end": str(end),
            "rejected_atr_entries": rejected_atr,
            "skipped_position_signals": skipped_position_signals,
        },
    )


def trade_period_metrics(
    trades: pd.DataFrame,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
) -> dict[str, float | int]:
    if trades.empty:
        selected = trades
    else:
        entry = pd.to_datetime(trades["entry_ts"], utc=True)
        mask = pd.Series(True, index=trades.index)
        if start is not None:
            mask &= entry >= start
        if end is not None:
            mask &= entry < end
        selected = trades.loc[mask]
    returns = (
        selected["net_account_return_pct"].to_numpy("float64") / 100.0
        if not selected.empty
        else np.array([], dtype="float64")
    )
    if not len(returns):
        return {
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "trades": 0,
        }
    curve = np.r_[1.0, np.cumprod(1.0 + returns)]
    drawdown = curve / np.maximum.accumulate(curve) - 1.0
    wins = returns[returns > 0.0].sum()
    losses = abs(returns[returns < 0.0].sum())
    return {
        "return_pct": float((curve[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "win_rate_pct": float((returns > 0.0).mean() * 100.0),
        "profit_factor": float(wins / losses) if losses else float("inf"),
        "trades": int(len(returns)),
    }


def search_configs() -> list[RetestConfig]:
    return [
        RetestConfig(wait, touch, mid_tol, reclaim, close_location, expansion)
        for wait in (2, 3, 4, 5)
        for touch in (0.0, 0.15, 0.30)
        for mid_tol in (0.0, 0.25)
        for reclaim in (-0.50, -0.25, 0.0, 0.10)
        for close_location in (0.55, 0.65, 0.75)
        for expansion in (0, 3, 6)
    ]


def search(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    execution: ExecutionConfig,
) -> tuple[pd.DataFrame, RetestConfig | None]:
    rows = []
    for config in search_configs():
        signal, diagnostics = build_retest_signal(features, config)
        result = simulate(features, signal, funding, execution)
        train = trade_period_metrics(result.trades, None, TRAIN_END)
        validation = trade_period_metrics(
            result.trades,
            VALIDATION_START,
            VALIDATION_END,
        )
        holdout = trade_period_metrics(
            result.trades,
            VALIDATION_END,
            None,
        )
        meets = (
            result.metrics["trades"] >= 40
            and result.metrics["win_rate_pct"] > 72.0
            and result.metrics["max_drawdown_pct"] >= V3_MDD
            and result.metrics["profit_factor"] >= 2.0
            and train["trades"] >= 20
            and train["win_rate_pct"] > V3_WIN_RATE
            and validation["trades"] >= 8
            and validation["win_rate_pct"] > V3_WIN_RATE
        )
        rows.append(
            {
                "variant": config.label,
                **asdict(config),
                **result.metrics,
                "train_return_pct": train["return_pct"],
                "train_mdd_pct": train["max_drawdown_pct"],
                "train_win_rate_pct": train["win_rate_pct"],
                "train_trades": train["trades"],
                "validation_return_pct": validation["return_pct"],
                "validation_mdd_pct": validation["max_drawdown_pct"],
                "validation_win_rate_pct": validation["win_rate_pct"],
                "validation_trades": validation["trades"],
                "holdout_return_pct": holdout["return_pct"],
                "holdout_win_rate_pct": holdout["win_rate_pct"],
                "holdout_trades": holdout["trades"],
                "meets_goal": meets,
                **diagnostics,
            }
        )
    table = pd.DataFrame(rows)
    table["selection_score"] = (
        np.minimum(
            table["train_win_rate_pct"],
            table["validation_win_rate_pct"],
        )
        + np.log1p(table["profit_factor"].clip(upper=20.0)) * 2.0
        + table["trades"].clip(upper=100) / 100.0
    )
    table = table.sort_values(
        ["meets_goal", "selection_score", "return_pct"],
        ascending=[False, False, False],
    )
    accepted = table.loc[table["meets_goal"]]
    if accepted.empty:
        return table, None
    row = accepted.iloc[0]
    return table, RetestConfig(
        max_wait_bars=int(row["max_wait_bars"]),
        touch_buffer_atr=float(row["touch_buffer_atr"]),
        mid_tolerance_atr=float(row["mid_tolerance_atr"]),
        reclaim_buffer_atr=float(row["reclaim_buffer_atr"]),
        reclaim_close_location=float(row["reclaim_close_location"]),
        expansion_lookback=int(row["expansion_lookback"]),
    )


def row(label: str, result: Result, **extra: Any) -> dict[str, Any]:
    return {"variant": label, **result.metrics, **extra}


def rolling_windows(
    features: pd.DataFrame,
    signal: np.ndarray,
    funding: pd.DataFrame,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    window_start = start + pd.Timedelta(days=70)
    number = 0
    while window_start < end:
        window_end = min(window_start + pd.Timedelta(days=30), end)
        result = simulate(
            features,
            signal,
            funding,
            execution,
            start=window_start,
            end=window_end,
        )
        rows.append(
            row(
                f"oos_{number:02d}",
                result,
                oos_start=str(window_start),
                oos_end=str(window_end),
            )
        )
        number += 1
        window_start += pd.Timedelta(days=30)
    return pd.DataFrame(rows)


def trade_mc(trades: pd.DataFrame, runs: int = 5000) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    returns = trades["net_account_return_pct"].to_numpy("float64") / 100.0
    rows = []
    for number in range(runs):
        sampled = rng.choice(returns, size=len(returns), replace=True)
        curve = np.r_[1.0, np.cumprod(1.0 + sampled)]
        drawdown = curve / np.maximum.accumulate(curve) - 1.0
        rows.append(
            {
                "run": number,
                "return_pct": float((curve[-1] - 1.0) * 100.0),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
                "win_rate_pct": float((sampled > 0.0).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def ablation(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    config: RetestConfig,
    execution: ExecutionConfig,
    full: Result,
) -> pd.DataFrame:
    variants = {
        "full": config,
        "no_expansion": replace(config, expansion_lookback=0),
        "no_mid_protection": replace(config, mid_tolerance_atr=10.0),
        "no_close_location": replace(config, reclaim_close_location=0.50),
        "no_directional_candle": replace(config, require_directional_candle=False),
    }
    rows = []
    for label, variant in variants.items():
        signal, _ = build_retest_signal(features, variant)
        result = full if label == "full" else simulate(
            features,
            signal,
            funding,
            execution,
        )
        rows.append(row(label, result))
    direct = direct_breakout_signal(features, "long")
    rows.append(
        row(
            "direct_breakout_long_parent",
            simulate(features, direct, funding, execution),
        )
    )
    return pd.DataFrame(rows)


def neighborhood(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    config: RetestConfig,
    execution: ExecutionConfig,
) -> pd.DataFrame:
    definitions = {
        "max_wait_bars": sorted({max(1, config.max_wait_bars - 1), config.max_wait_bars, config.max_wait_bars + 1}),
        "touch_buffer_atr": sorted({max(0.0, config.touch_buffer_atr - 0.15), config.touch_buffer_atr, config.touch_buffer_atr + 0.15}),
        "mid_tolerance_atr": sorted({max(0.0, config.mid_tolerance_atr - 0.25), config.mid_tolerance_atr, config.mid_tolerance_atr + 0.25}),
        "reclaim_buffer_atr": sorted({max(0.0, config.reclaim_buffer_atr - 0.10), config.reclaim_buffer_atr, config.reclaim_buffer_atr + 0.10}),
        "reclaim_close_location": sorted({max(0.50, config.reclaim_close_location - 0.10), config.reclaim_close_location, min(0.90, config.reclaim_close_location + 0.10)}),
    }
    rows = []
    for parameter, values in definitions.items():
        for value in values:
            variant = replace(config, **{parameter: value})
            signal, _ = build_retest_signal(features, variant)
            result = simulate(features, signal, funding, execution)
            rows.append(
                row(
                    f"{parameter}_{value}",
                    result,
                    parameter=parameter,
                    value=value,
                    is_frozen=value == getattr(config, parameter),
                )
            )
    return pd.DataFrame(rows)


def phase_scan(
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    channel: ChannelConfig,
    config: RetestConfig,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    starts = [start + pd.Timedelta(days=30 * offset) for offset in range(8)]
    rows = []
    for phase in (0, 10, 20):
        signal_bars = aggregate(m1, 30, phase)
        trend_bars = aggregate(m1, 60, 0)
        features = build_features(signal_bars, trend_bars, channel)
        signal, _ = build_retest_signal(features, config)
        for number, run_start in enumerate(starts):
            result = simulate(
                features,
                signal,
                funding,
                execution,
                start=run_start,
                end=end,
            )
            rows.append(
                row(
                    f"phase_{phase}_start_{number}",
                    result,
                    phase_minutes=phase,
                    start_index=number,
                    start=str(run_start),
                )
            )
    return pd.DataFrame(rows)


def stress(
    features: pd.DataFrame,
    signal: np.ndarray,
    funding: pd.DataFrame,
    execution: ExecutionConfig,
) -> pd.DataFrame:
    variants = {
        "baseline": execution,
        "double_fee_slippage": replace(
            execution,
            fee_rate=execution.fee_rate * 2.0,
            slippage_rate=execution.slippage_rate * 2.0,
        ),
        "one_bar_entry_delay": replace(execution, entry_delay_bars=1),
        "two_bar_entry_delay": replace(execution, entry_delay_bars=2),
        "leverage_cap_2x": replace(execution, max_leverage=2.0),
    }
    return pd.DataFrame(
        [
            row(
                label,
                simulate(features, signal, funding, variant),
            )
            for label, variant in variants.items()
        ]
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    m1, funding, quality = load_data()
    channel = ChannelConfig()
    execution = ExecutionConfig()
    signal_bars = aggregate(m1, 30, 0)
    trend_bars = aggregate(m1, 60, 0)
    features = build_features(signal_bars, trend_bars, channel)
    ready = features[["mid", "atr10", "atr84"]].notna().all(axis=1)
    start = pd.Timestamp(features.index[np.flatnonzero(ready.to_numpy())[0]])
    end = signal_bars.index.max() + pd.Timedelta(minutes=30)

    parent_both = simulate(
        features,
        direct_breakout_signal(features, "both"),
        funding,
        execution,
        start=start,
        end=end,
    )
    parent_long = simulate(
        features,
        direct_breakout_signal(features, "long"),
        funding,
        execution,
        start=start,
        end=end,
    )
    if parent_both.metrics["trades"] != 78 or not np.isclose(
        parent_both.metrics["return_pct"],
        6328.984548925989,
        atol=0.05,
    ):
        raise RuntimeError(f"parent parity failed: {parent_both.metrics}")

    table, selected = search(features, funding, execution)
    target = selected
    decision = "candidate_found"
    if target is None:
        decision = "no_candidate_met_goal"
        best = table.iloc[0]
        target = RetestConfig(
            max_wait_bars=int(best["max_wait_bars"]),
            touch_buffer_atr=float(best["touch_buffer_atr"]),
            mid_tolerance_atr=float(best["mid_tolerance_atr"]),
            reclaim_buffer_atr=float(best["reclaim_buffer_atr"]),
            reclaim_close_location=float(best["reclaim_close_location"]),
            expansion_lookback=int(best["expansion_lookback"]),
        )
    target_signal, target_diagnostics = build_retest_signal(features, target)
    target_result = simulate(
        features,
        target_signal,
        funding,
        execution,
        start=start,
        end=end,
    )
    oos = rolling_windows(
        features,
        target_signal,
        funding,
        execution,
        start,
        end,
    )
    mc = trade_mc(target_result.trades)
    phases = phase_scan(
        m1,
        funding,
        channel,
        target,
        execution,
        start,
        end,
    )
    ablations = ablation(
        features,
        funding,
        target,
        execution,
        target_result,
    )
    neighbors = neighborhood(
        features,
        funding,
        target,
        execution,
    )
    stresses = stress(
        features,
        target_signal,
        funding,
        execution,
    )
    slices = pd.DataFrame(target_result.slices)
    phase_summary = (
        phases.groupby("phase_minutes")
        .agg(
            starts=("variant", "size"),
            median_return_pct=("return_pct", "median"),
            min_return_pct=("return_pct", "min"),
            median_mdd_pct=("max_drawdown_pct", "median"),
            median_trades=("trades", "median"),
        )
        .reset_index()
    )
    mc_summary = {
        "return_p05": float(mc["return_pct"].quantile(0.05)),
        "return_median": float(mc["return_pct"].median()),
        "mdd_p05": float(mc["max_drawdown_pct"].quantile(0.05)),
        "win_rate_p05": float(mc["win_rate_pct"].quantile(0.05)),
    }
    summary = {
        "family": "HYPE-30M-Keltner-Breakout-Retest",
        "status": "explore / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_quality": quality,
        "funding": {
            "source_path": str(FUNDING_CACHE.relative_to(ROOT)),
            "rows": int(len(funding)),
            "start": str(funding["ts"].min()),
            "end": str(funding["ts"].max()),
        },
        "cost": asdict(execution),
        "channel": asdict(channel),
        "search_variants": int(len(table)),
        "meeting_goal": int(table["meets_goal"].sum()),
        "decision": decision,
        "selected": asdict(target),
        "selected_metrics": target_result.metrics,
        "selected_signal_diagnostics": target_diagnostics,
        "parent_v3_both": parent_both.metrics,
        "parent_v3_long": parent_long.metrics,
        "rolling_windows": {
            "windows": int(len(oos)),
            "positive_fraction": float(oos["return_pct"].gt(0.0).mean()),
            "median_return_pct": float(oos["return_pct"].median()),
            "median_trades": float(oos["trades"].median()),
        },
        "mc": mc_summary,
        "phase_summary": phase_summary.to_dict(orient="records"),
        "neighborhood": {
            "variants": int(len(neighbors)),
            "positive_fraction": float(neighbors["return_pct"].gt(0.0).mean()),
            "min_return_pct": float(neighbors["return_pct"].min()),
        },
    }
    table.to_csv(SEARCH_PATH, index=False)
    target_result.trades.to_csv(TRADES_PATH, index=False)
    oos.to_csv(OOS_PATH, index=False)
    mc.to_csv(MC_PATH, index=False)
    phases.to_csv(PHASE_PATH, index=False)
    ablations.to_csv(ABLATION_PATH, index=False)
    neighbors.to_csv(NEIGHBORHOOD_PATH, index=False)
    slices.to_csv(SLICES_PATH, index=False)
    stresses.to_csv(STRESS_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print("parent both", parent_both.metrics)
    print("parent long", parent_long.metrics)
    print("search variants", len(table), "meeting goal", int(table["meets_goal"].sum()))
    print("decision", decision)
    print("selected", target)
    print("selected metrics", target_result.metrics)
    print("\nTop 12")
    print(
        table[
            [
                "variant",
                "return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
                "train_win_rate_pct",
                "validation_win_rate_pct",
                "validation_trades",
                "meets_goal",
            ]
        ]
        .head(12)
        .to_string(index=False)
    )
    print("\nphase")
    print(phase_summary.to_string(index=False))
    print("\nsummary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
