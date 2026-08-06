from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-sma-crossover-slope"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FREEZE_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_dataset_freeze.json"
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"

BASE_FEE = 0.001
BASE_SLIPPAGE = 0.0004
HOURS_PER_YEAR = 365.25 * 24.0
EXIT_MODES = {
    "cross_only",
    "fast_slope",
    "gap_slope",
    "hybrid_any",
    "hybrid_both",
}


@dataclass(frozen=True, slots=True)
class Config:
    fast_window: int = 30
    slow_window: int = 120
    atr_window: int = 14
    slope_window: int = 3
    exit_confirm_bars: int = 2
    exit_mode: str = "cross_only"
    leverage: float = 1.0
    fee_per_fill: float = BASE_FEE
    slippage_per_fill: float = BASE_SLIPPAGE

    def validate(self) -> None:
        if min(
            self.fast_window,
            self.slow_window,
            self.atr_window,
            self.slope_window,
            self.exit_confirm_bars,
        ) <= 0:
            raise ValueError("all windows must be positive")
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be below slow_window")
        if self.exit_mode not in EXIT_MODES:
            raise ValueError(f"unknown exit_mode: {self.exit_mode}")
        if not 0.0 < self.leverage <= 3.0:
            raise ValueError("leverage must be in (0, 3]")
        if self.fee_per_fill < 0.0 or self.slippage_per_fill < 0.0:
            raise ValueError("costs must be non-negative")


BASELINE_CONFIG = Config()


@dataclass(slots=True)
class FeatureBook:
    ts: pd.DatetimeIndex
    terminal_ts: pd.Timestamp
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    atr: np.ndarray
    funding_by_bar: np.ndarray
    source_start: pd.Timestamp

    @property
    def rows(self) -> int:
        return len(self.ts)


@dataclass(slots=True)
class StateBook:
    desired_state: np.ndarray
    sma_fast: np.ndarray
    sma_slow: np.ndarray
    fast_slope: np.ndarray
    normalized_gap: np.ndarray
    gap_slope: np.ndarray
    golden_cross: np.ndarray
    dead_cross: np.ndarray
    transition_reason: list[str]


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    equity_path: list[dict[str, Any]]
    states: StateBook


def config_payload(config: Config) -> dict[str, Any]:
    return asdict(config)


def config_sha256(config: Config) -> str:
    raw = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_partitions(root: Path, timestamp_column: str) -> pd.DataFrame:
    paths = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not paths:
        raise RuntimeError(f"no partitions found below {root}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame[timestamp_column] = pd.to_datetime(frame[timestamp_column], utc=True)
    return (
        frame.sort_values(timestamp_column)
        .drop_duplicates(timestamp_column, keep="last")
        .reset_index(drop=True)
    )


def load_market() -> pd.DataFrame:
    warehouse = DuckDBWarehouse(
        DataLakeLayout.from_settings(load_settings(None))
    )
    return warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        timeframe="15m",
    ).reset_index(drop=True)


def load_funding() -> pd.DataFrame:
    frame = _load_partitions(FUNDING_ROOT, "ts")
    if frame["funding_rate"].isna().any():
        raise RuntimeError("funding contains null rates")
    return frame


def _atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    window: int,
) -> np.ndarray:
    previous_close = np.r_[np.nan, close[:-1]]
    true_range = np.maximum(
        high - low,
        np.maximum(np.abs(high - previous_close), np.abs(low - previous_close)),
    )
    return (
        pd.Series(true_range)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )


def _funding_by_bar(
    ts: pd.DatetimeIndex,
    funding: pd.DataFrame,
) -> np.ndarray:
    event_ts = pd.DatetimeIndex(funding["ts"]).as_unit("ns").asi8
    rates = funding["funding_rate"].to_numpy("float64")
    bar_open = ts.as_unit("ns").asi8
    bar_close = (ts + pd.Timedelta(minutes=15)).as_unit("ns").asi8
    output = np.zeros(len(ts), dtype="float64")
    for index, (left_ts, right_ts) in enumerate(zip(bar_open, bar_close, strict=True)):
        left = int(np.searchsorted(event_ts, left_ts, side="left"))
        right = int(np.searchsorted(event_ts, right_ts, side="left"))
        if right > left:
            output[index] = float(rates[left:right].sum())
    return output


def build_book(*, include_locked_oos: bool) -> FeatureBook:
    manifest = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if manifest["quality"]["blocker_count"] != 0:
        raise RuntimeError("frozen dataset has quality blockers")
    frame = load_market()
    terminal = pd.Timestamp(manifest["freeze_contract"]["data_terminal_exclusive"])
    oos_start = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    frame = frame.loc[frame["ts"] < terminal].copy()
    if not include_locked_oos:
        frame = frame.loc[frame["ts"] < oos_start].copy()
        terminal = oos_start
    expected = (
        manifest["rows"]["all"]
        if include_locked_oos
        else manifest["rows"]["prefit"]
    )
    if len(frame) != expected:
        raise RuntimeError(f"frozen row-count mismatch: {len(frame)} != {expected}")

    funding = load_funding()
    funding = funding.loc[funding["ts"] < terminal].copy()
    ts = pd.DatetimeIndex(frame["ts"])
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    return FeatureBook(
        ts=ts,
        terminal_ts=terminal,
        open=frame["open"].to_numpy("float64"),
        high=high,
        low=low,
        close=close,
        volume=frame["volume"].to_numpy("float64"),
        atr=_atr(high, low, close, BASELINE_CONFIG.atr_window),
        funding_by_bar=_funding_by_bar(ts, funding),
        source_start=pd.Timestamp(ts[0]),
    )


def generate_states(
    close: np.ndarray,
    atr: np.ndarray,
    config: Config,
) -> StateBook:
    config.validate()
    close_series = pd.Series(np.asarray(close, dtype="float64"))
    sma_fast = (
        close_series.rolling(config.fast_window, min_periods=config.fast_window)
        .mean()
        .to_numpy("float64")
    )
    sma_slow = (
        close_series.rolling(config.slow_window, min_periods=config.slow_window)
        .mean()
        .to_numpy("float64")
    )
    lag = config.slope_window
    fast_lag = np.r_[np.full(lag, np.nan), sma_fast[:-lag]]
    fast_slope = (sma_fast - fast_lag) / (
        lag * np.where(atr <= 1e-12, np.nan, atr)
    )
    normalized_gap = (sma_fast - sma_slow) / np.where(
        atr <= 1e-12,
        np.nan,
        atr,
    )
    gap_lag = np.r_[np.full(lag, np.nan), normalized_gap[:-lag]]
    gap_slope = (normalized_gap - gap_lag) / lag

    previous_fast = np.r_[np.nan, sma_fast[:-1]]
    previous_slow = np.r_[np.nan, sma_slow[:-1]]
    golden = (
        (sma_fast > sma_slow)
        & (previous_fast <= previous_slow)
        & np.isfinite(previous_fast)
        & np.isfinite(previous_slow)
    )
    dead = (
        (sma_fast < sma_slow)
        & (previous_fast >= previous_slow)
        & np.isfinite(previous_fast)
        & np.isfinite(previous_slow)
    )

    rows = len(close)
    desired = np.zeros(rows, dtype="int8")
    reasons = ["warmup"] * rows
    state = 0
    weak_bars = 0

    for index in range(rows):
        reason = "hold"
        if golden[index]:
            if state != 1:
                reason = "golden_cross" if state == 0 else "dead_to_golden"
            state = 1
            weak_bars = 0
        elif dead[index]:
            if state != -1:
                reason = "dead_cross" if state == 0 else "golden_to_dead"
            state = -1
            weak_bars = 0
        elif state and config.exit_mode != "cross_only":
            fast_weak = (
                np.isfinite(fast_slope[index])
                and (
                    fast_slope[index] <= 0.0
                    if state == 1
                    else fast_slope[index] >= 0.0
                )
            )
            gap_weak = (
                np.isfinite(gap_slope[index])
                and (
                    gap_slope[index] <= 0.0
                    if state == 1
                    else gap_slope[index] >= 0.0
                )
            )
            weak = {
                "fast_slope": fast_weak,
                "gap_slope": gap_weak,
                "hybrid_any": fast_weak or gap_weak,
                "hybrid_both": fast_weak and gap_weak,
            }[config.exit_mode]
            weak_bars = weak_bars + 1 if weak else 0
            if weak_bars >= config.exit_confirm_bars:
                state = 0
                reason = f"{config.exit_mode}_exit"
                weak_bars = 0
        else:
            weak_bars = 0

        desired[index] = state
        reasons[index] = reason

    return StateBook(
        desired_state=desired,
        sma_fast=sma_fast,
        sma_slow=sma_slow,
        fast_slope=fast_slope,
        normalized_gap=normalized_gap,
        gap_slope=gap_slope,
        golden_cross=golden,
        dead_cross=dead,
        transition_reason=reasons,
    )


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peaks = np.maximum.accumulate(equity)
    drawdowns = equity / np.where(peaks <= 0.0, np.nan, peaks) - 1.0
    return float(np.nanmin(drawdowns))


def _annual_factor(final_equity: float, elapsed_hours: float) -> float:
    if final_equity <= 0.0 or elapsed_hours <= 0.0:
        return 0.0
    return float(final_equity ** (HOURS_PER_YEAR / elapsed_hours))


def run_backtest(
    book: FeatureBook,
    config: Config,
    *,
    states: StateBook | None = None,
) -> BacktestResult:
    config.validate()
    states = states or generate_states(book.close, book.atr, config)
    if len(states.desired_state) != book.rows:
        raise ValueError("state and market row counts differ")

    cost = config.fee_per_fill + config.slippage_per_fill
    equity = 1.0
    position = 0
    entry_price = math.nan
    entry_index = -1
    entry_signal_index = -1
    entry_equity_before_cost = math.nan
    position_base_equity = math.nan
    funding_sum = 0.0
    trades: list[dict[str, Any]] = []
    equity_path: list[dict[str, Any]] = []

    def close_position(index: int, price: float, reason: str) -> None:
        nonlocal equity, position, entry_price, entry_index
        nonlocal entry_signal_index, entry_equity_before_cost
        nonlocal position_base_equity, funding_sum

        direction = position
        gross = direction * config.leverage * (price / entry_price - 1.0)
        funding_return = -direction * config.leverage * funding_sum
        factor_before_exit_cost = 1.0 + gross + funding_return
        equity = (
            0.0
            if factor_before_exit_cost <= 0.0
            else position_base_equity
            * factor_before_exit_cost
            * (1.0 - cost * config.leverage)
        )
        net_return = equity / entry_equity_before_cost - 1.0
        trades.append(
            {
                "signal_ts": book.ts[entry_signal_index].isoformat(),
                "entry_ts": book.ts[entry_index].isoformat(),
                "exit_ts": book.ts[index].isoformat(),
                "direction": "long" if direction == 1 else "short",
                "entry_price": float(entry_price),
                "exit_price": float(price),
                "bars_held": int(index - entry_index + 1),
                "exit_reason": reason,
                "gross_return": float(gross),
                "funding_return": float(funding_return),
                "net_return": float(net_return),
                "leverage": float(config.leverage),
                "equity_after": float(equity),
            }
        )
        position = 0
        entry_price = math.nan
        entry_index = -1
        entry_signal_index = -1
        entry_equity_before_cost = math.nan
        position_base_equity = math.nan
        funding_sum = 0.0

    def open_position(index: int, direction: int, signal_index: int) -> None:
        nonlocal equity, position, entry_price, entry_index
        nonlocal entry_signal_index, entry_equity_before_cost
        nonlocal position_base_equity, funding_sum

        entry_equity_before_cost = equity
        equity *= 1.0 - cost * config.leverage
        position_base_equity = equity
        position = direction
        entry_price = float(book.open[index])
        entry_index = index
        entry_signal_index = signal_index
        funding_sum = 0.0

    for index in range(book.rows):
        if index > 0 and equity > 0.0:
            target = int(states.desired_state[index - 1])
            if position != target:
                if position:
                    reason = "cross_reverse" if target else states.transition_reason[index - 1]
                    close_position(index, float(book.open[index]), reason)
                if target and equity > 0.0:
                    open_position(index, target, index - 1)

        if position and equity > 0.0:
            funding_sum += float(book.funding_by_bar[index])

        mark_equity = equity
        if position and equity > 0.0:
            gross = (
                position
                * config.leverage
                * (float(book.close[index]) / entry_price - 1.0)
            )
            funding_return = -position * config.leverage * funding_sum
            mark_equity = position_base_equity * (1.0 + gross + funding_return)
        equity_path.append(
            {
                "ts": book.ts[index].isoformat(),
                "equity": float(max(0.0, mark_equity)),
                "position": int(position),
                "desired_state": int(states.desired_state[index]),
            }
        )
        if equity <= 0.0:
            break

    if position and equity > 0.0:
        close_position(book.rows - 1, float(book.close[-1]), "terminal")
        equity_path[-1]["equity"] = float(equity)
        equity_path[-1]["position"] = 0

    equity_values = np.asarray(
        [row["equity"] for row in equity_path],
        dtype="float64",
    )
    net_returns = np.asarray([trade["net_return"] for trade in trades], dtype="float64")
    elapsed_hours = (
        (book.terminal_ts - book.source_start).total_seconds() / 3600.0
    )
    wins = int((net_returns > 0.0).sum())
    trade_sharpe = (
        float(net_returns.mean() / net_returns.std(ddof=1) * math.sqrt(len(net_returns)))
        if len(net_returns) > 1 and net_returns.std(ddof=1) > 0.0
        else None
    )
    metrics = {
        "final_equity": float(equity),
        "total_return": float(equity - 1.0),
        "annual_factor": _annual_factor(float(equity), elapsed_hours),
        "max_drawdown": _max_drawdown(equity_values),
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate": float(wins / len(trades)) if trades else 0.0,
        "long_trades": int(sum(trade["direction"] == "long" for trade in trades)),
        "short_trades": int(sum(trade["direction"] == "short" for trade in trades)),
        "trade_sharpe": trade_sharpe,
        "average_trade": float(net_returns.mean()) if trades else 0.0,
        "median_bars_held": (
            float(np.median([trade["bars_held"] for trade in trades]))
            if trades
            else 0.0
        ),
        "max_leverage": float(config.leverage),
        "cost_per_fill": float(cost),
    }
    return BacktestResult(
        metrics=metrics,
        trades=trades,
        equity_path=equity_path,
        states=states,
    )


def slice_metrics(
    result: BacktestResult,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    equity = pd.DataFrame(result.equity_path)
    equity["ts"] = pd.to_datetime(equity["ts"], utc=True)
    before = equity.loc[equity["ts"] < start, "equity"]
    start_equity = float(before.iloc[-1]) if len(before) else float(equity["equity"].iloc[0])
    scoped = equity.loc[(equity["ts"] >= start) & (equity["ts"] < end)].copy()
    if scoped.empty:
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "return": 0.0,
            "max_drawdown": 0.0,
            "trades": 0,
            "win_rate": 0.0,
        }
    values = np.r_[start_equity, scoped["equity"].to_numpy("float64")]
    trades = [
        trade
        for trade in result.trades
        if start <= pd.Timestamp(trade["entry_ts"]) < end
    ]
    wins = sum(float(trade["net_return"]) > 0.0 for trade in trades)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "return": float(values[-1] / values[0] - 1.0),
        "max_drawdown": _max_drawdown(values),
        "trades": int(len(trades)),
        "win_rate": float(wins / len(trades)) if trades else 0.0,
    }


def states_frame(book: FeatureBook, states: StateBook) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": book.ts,
            "close": book.close,
            "atr": book.atr,
            "desired_state": states.desired_state,
            "sma_fast": states.sma_fast,
            "sma_slow": states.sma_slow,
            "fast_slope": states.fast_slope,
            "normalized_gap": states.normalized_gap,
            "gap_slope": states.gap_slope,
            "golden_cross": states.golden_cross,
            "dead_cross": states.dead_cross,
            "transition_reason": states.transition_reason,
        }
    )
