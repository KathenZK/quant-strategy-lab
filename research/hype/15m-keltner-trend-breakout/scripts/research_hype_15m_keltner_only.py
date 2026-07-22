"""回测 HYPE 15m 纯 Keltner 通道突破探索线。

只使用 EMA96 ± 2.4 × ATR144 生成多空信号；不使用 EMA 方向、ADX/DI、
成交量或 1h 确认。退出只保留固定 entry-ATR bracket、timeout 与冷却。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-keltner-trend-breakout"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
UPSTREAM_QUALITY_PATH = (
    ROOT
    / "research/hype/15m-ema-trend-breakout/artifacts/hype_binance_15m_data_quality.json"
)
OUT_STEM = "hype_15m_keltner_only_initial_2026-07-20"

EXCHANGE = "binance"
SYMBOL = "HYPE/USDT:USDT"
TIMEFRAME = "15m"
M15_PER_YEAR = 365 * 24 * 4
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=182),
    "1y": pd.Timedelta(days=365),
}


@dataclass(frozen=True, slots=True)
class KeltnerConfig:
    center_ema_window: int = 96
    channel_atr_window: int = 144
    channel_multiplier: float = 2.4
    sizing_atr_window: int = 672
    long_target_atr_pct: float = 0.014
    short_target_atr_pct: float = 0.012
    max_allocation: float = 3.0
    take_profit_atr: float = 4.0
    hard_stop_atr: float = 12.0
    max_hold_bars: int = 192
    cooldown_bars: int = 16
    warmup_bars: int = 1600
    fee_per_fill: float = 0.001
    adverse_slippage_per_fill: float = 0.0004

    def validate(self) -> None:
        windows = (
            self.center_ema_window,
            self.channel_atr_window,
            self.sizing_atr_window,
            self.max_hold_bars,
            self.warmup_bars,
        )
        if any(value <= 0 for value in windows):
            raise ValueError("indicator, hold, and warmup windows must be positive")
        if self.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        positive_values = (
            self.channel_multiplier,
            self.long_target_atr_pct,
            self.short_target_atr_pct,
            self.max_allocation,
            self.take_profit_atr,
            self.hard_stop_atr,
        )
        if any(value <= 0.0 for value in positive_values):
            raise ValueError("channel, sizing, and bracket values must be positive")
        if min(self.fee_per_fill, self.adverse_slippage_per_fill) < 0.0:
            raise ValueError("cost rates must be non-negative")


@dataclass(frozen=True, slots=True)
class RunSpec:
    name: str
    entry_delay_bars: int
    sizing_mode: str
    fixed_allocation: float = 1.0

    def validate(self, config: KeltnerConfig) -> None:
        if self.entry_delay_bars not in {1, 2}:
            raise ValueError("entry_delay_bars must be 1 or 2")
        if self.sizing_mode not in {"atr_risk", "fixed"}:
            raise ValueError("sizing_mode must be atr_risk or fixed")
        if self.fixed_allocation <= 0.0 or self.fixed_allocation > config.max_allocation:
            raise ValueError("fixed_allocation must be within (0, max_allocation]")


@dataclass(slots=True)
class Position:
    direction: int
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    signal_bar: int
    signal_ts: pd.Timestamp


@dataclass(frozen=True, slots=True)
class RunResult:
    spec: RunSpec
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    trades: pd.DataFrame
    equity_curve: pd.Series
    period_returns: pd.Series
    open_position: dict[str, Any] | None


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def build_features(frame: pd.DataFrame, config: KeltnerConfig) -> pd.DataFrame:
    config.validate()
    out = frame.copy()
    tr = true_range(out)
    out["center"] = out["close"].ewm(
        span=config.center_ema_window,
        adjust=False,
        min_periods=config.center_ema_window,
    ).mean()
    out["channel_atr"] = tr.rolling(
        config.channel_atr_window,
        min_periods=config.channel_atr_window,
    ).mean()
    out["sizing_atr"] = tr.rolling(
        config.sizing_atr_window,
        min_periods=config.sizing_atr_window,
    ).mean()
    out["upper"] = out["center"] + config.channel_multiplier * out["channel_atr"]
    out["lower"] = out["center"] - config.channel_multiplier * out["channel_atr"]
    out["long_signal"] = out["close"].gt(out["upper"])
    out["short_signal"] = out["close"].lt(out["lower"])
    if bool((out["long_signal"] & out["short_signal"]).any()):
        raise RuntimeError("Keltner long and short signals conflict")
    return out


def load_data(
    warehouse: DuckDBWarehouse,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    normalized = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        columns=[
            "ts",
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
            "timeframe",
        ],
    )
    if normalized.empty:
        raise RuntimeError("normalized Binance HYPEUSDT 15m dataset is empty")
    normalized_duplicate_stats = normalized.attrs.get("duplicate_stats", {})
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    normalized = normalized.sort_values("ts")
    duplicate_rows = int(normalized.duplicated("ts").sum())
    frame = normalized.drop_duplicates("ts", keep="last").set_index("ts")
    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    expected = pd.date_range(frame.index.min(), frame.index.max(), freq="15min")
    missing = expected.difference(frame.index)
    critical = [
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
        "timeframe",
    ]
    nulls = {column: int(frame[column].isna().sum()) for column in critical}
    invalid_ohlc = int(
        (
            frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
            | frame[["open", "high", "low", "close"]].le(0.0).any(axis=1)
            | frame["volume"].lt(0.0)
        ).sum()
    )
    non_closed = int((~frame["is_closed"].fillna(False).astype(bool)).sum())
    source_values = sorted(str(value) for value in frame["source"].dropna().unique())
    timeframe_values = sorted(str(value) for value in frame["timeframe"].dropna().unique())

    if not UPSTREAM_QUALITY_PATH.exists():
        raise RuntimeError(f"missing upstream raw/normalized audit: {UPSTREAM_QUALITY_PATH}")
    quality_bytes = UPSTREAM_QUALITY_PATH.read_bytes()
    upstream = json.loads(quality_bytes)
    upstream_quality = upstream["data_quality"]
    upstream_last = pd.Timestamp(upstream_quality["last_ts"])
    if upstream_last != frame.index.max():
        raise RuntimeError(
            f"upstream audit ends at {upstream_last}, normalized data ends at {frame.index.max()}"
        )

    blocker_count = (
        duplicate_rows
        + len(missing)
        + sum(nulls.values())
        + invalid_ohlc
        + non_closed
        + int(source_values != ["binance_futures_kline_api"])
        + int(timeframe_values != [TIMEFRAME])
        + int(upstream_quality.get("blocker_count", -1) != 0)
    )
    quality = {
        "market": "Binance USD-M Futures",
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "duplicate_rows": duplicate_rows,
        "missing_bars": int(len(missing)),
        "critical_nulls": nulls,
        "invalid_ohlcv_rows": invalid_ohlc,
        "non_closed_rows": non_closed,
        "source_values": source_values,
        "timeframe_values": timeframe_values,
        "normalized_duplicate_stats": normalized_duplicate_stats,
        "upstream_raw_normalized_audit": {
            "path": str(UPSTREAM_QUALITY_PATH.relative_to(ROOT)),
            "sha256": hashlib.sha256(quality_bytes).hexdigest(),
            "generated_at_utc": upstream["generated_at_utc"],
            "raw_normalized_mismatch": upstream_quality["raw_normalized_mismatch"],
            "blocker_count": upstream_quality["blocker_count"],
        },
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"data-quality blockers found: {quality}")

    funding_frame = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        columns=["ts", "funding_rate", "source"],
    )
    if funding_frame.empty:
        raise RuntimeError("normalized Binance HYPEUSDT funding dataset is empty")
    funding_duplicate_stats = funding_frame.attrs.get("duplicate_stats", {})
    funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True).dt.floor("15min")
    funding_frame["funding_rate"] = pd.to_numeric(
        funding_frame["funding_rate"], errors="coerce"
    )
    if funding_frame["funding_rate"].isna().any():
        raise RuntimeError("funding dataset contains null/non-numeric rates")
    funding_raw = (
        funding_frame.sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .set_index("ts")["funding_rate"]
    )
    funding = funding_raw.reindex(frame.index).fillna(0.0).rename("funding_rate")
    quality["funding"] = {
        "rows": int(len(funding_frame)),
        "start": funding_frame["ts"].min().isoformat(),
        "end": funding_frame["ts"].max().isoformat(),
        "non_zero_aligned_rows": int(funding.ne(0.0).sum()),
        "aligned_sum_rate": float(funding.sum()),
        "duplicate_stats": funding_duplicate_stats,
    }
    return frame[["open", "high", "low", "close", "volume"]], funding, quality


def entry_allocation(
    *,
    direction: int,
    entry_atr: float,
    raw_entry_price: float,
    spec: RunSpec,
    config: KeltnerConfig,
) -> float:
    if spec.sizing_mode == "fixed":
        return float(spec.fixed_allocation)
    target = (
        config.long_target_atr_pct
        if direction == 1
        else config.short_target_atr_pct
    )
    return float(min(config.max_allocation, target / (entry_atr / raw_entry_price)))


def adverse_fill(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    config: KeltnerConfig,
) -> float:
    sign = direction if is_entry else -direction
    return raw_price * (1.0 + sign * config.adverse_slippage_per_fill)


def bracket_exit(
    position: Position,
    *,
    open_price: float,
    high: float,
    low: float,
    config: KeltnerConfig,
) -> tuple[str, float] | None:
    take = (
        position.entry_price
        + position.direction * config.take_profit_atr * position.entry_atr
    )
    stop = (
        position.entry_price
        - position.direction * config.hard_stop_atr * position.entry_atr
    )
    if position.direction == 1:
        if open_price <= stop:
            return "stop_loss_gap", open_price
        if low <= stop:
            return "stop_loss", stop
        if open_price >= take:
            return "take_profit_gap", take
        if high >= take:
            return "take_profit", take
    else:
        if open_price >= stop:
            return "stop_loss_gap", open_price
        if high >= stop:
            return "stop_loss", stop
        if open_price <= take:
            return "take_profit_gap", take
        if low <= take:
            return "take_profit", take
    return None


def close_position(
    *,
    equity: float,
    position: Position,
    raw_exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    config: KeltnerConfig,
    trades: list[dict[str, Any]],
) -> tuple[float, float]:
    exit_price = adverse_fill(
        raw_exit_price,
        position.direction,
        is_entry=False,
        config=config,
    )
    pnl = (
        position.direction
        * position.allocation
        * (exit_price / position.previous_price - 1.0)
    )
    equity *= 1.0 + pnl
    fee = config.fee_per_fill * position.allocation
    equity *= 1.0 - fee
    trades.append(
        {
            "signal_ts": position.signal_ts,
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "exit_reason": reason,
            "raw_price_return": (
                position.direction * (exit_price / position.entry_price - 1.0)
            ),
            "trade_return": equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": equity,
        }
    )
    return equity, fee


def run_backtest(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    spec: RunSpec,
    config: KeltnerConfig,
) -> RunResult:
    spec.validate(config)
    start = max(config.warmup_bars, spec.entry_delay_bars + 1)
    equity = 1.0
    position: Position | None = None
    pending_timeout = False
    last_exit_bar = -10_000
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    period_returns: list[float] = []
    timestamps: list[pd.Timestamp] = []
    trading_cost_rate_total = 0.0
    funding_rate_total = 0.0

    for i in range(start, len(frame)):
        ts = pd.Timestamp(frame.index[i])
        start_equity = equity
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_timeout:
            equity, fee = close_position(
                equity=equity,
                position=position,
                raw_exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason="timeout_next_open",
                config=config,
                trades=trades,
            )
            trading_cost_rate_total += fee
            position = None
            pending_timeout = False
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_effect = (
                -position.direction * position.allocation * float(funding.iloc[i])
            )
            equity *= 1.0 + funding_effect
            funding_rate_total += funding_effect

        cooldown_complete = i > last_exit_bar + config.cooldown_bars
        if position is None and not exited_this_bar and cooldown_complete:
            signal_bar = i - spec.entry_delay_bars
            long_signal = bool(features["long_signal"].iloc[signal_bar])
            short_signal = bool(features["short_signal"].iloc[signal_bar])
            direction = (
                1
                if long_signal and not short_signal
                else -1
                if short_signal and not long_signal
                else 0
            )
            entry_atr = float(features["sizing_atr"].iloc[i - 1])
            if direction and np.isfinite(entry_atr) and entry_atr > 0.0:
                allocation = entry_allocation(
                    direction=direction,
                    entry_atr=entry_atr,
                    raw_entry_price=open_price,
                    spec=spec,
                    config=config,
                )
                entry_price = adverse_fill(
                    open_price,
                    direction,
                    is_entry=True,
                    config=config,
                )
                entry_equity = equity
                fee = config.fee_per_fill * allocation
                equity *= 1.0 - fee
                trading_cost_rate_total += fee
                position = Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=entry_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=entry_equity,
                    previous_price=entry_price,
                    signal_bar=signal_bar,
                    signal_ts=pd.Timestamp(frame.index[signal_bar]),
                )

        if position is not None:
            hit = bracket_exit(
                position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
            )
            if hit is not None:
                reason, raw_exit_price = hit
                equity, fee = close_position(
                    equity=equity,
                    position=position,
                    raw_exit_price=raw_exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    config=config,
                    trades=trades,
                )
                trading_cost_rate_total += fee
                position = None
                last_exit_bar = i
                exited_this_bar = True
            else:
                pnl = (
                    position.direction
                    * position.allocation
                    * (close / position.previous_price - 1.0)
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                if i - position.entry_bar + 1 >= config.max_hold_bars:
                    pending_timeout = True

        timestamps.append(ts)
        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)

    index = pd.DatetimeIndex(timestamps)
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
    returns = pd.Series(period_returns, index=index, name=spec.name)
    trades_frame = pd.DataFrame(trades)
    metrics = metrics_from_series(
        equity_curve,
        returns,
        trades_frame,
        trading_cost_rate_total=trading_cost_rate_total,
        funding_rate_total=funding_rate_total,
    )
    slices = [
        slice_metrics(
            name,
            delta,
            equity_curve,
            returns,
            trades_frame,
        )
        for name, delta in RECENT_WINDOWS.items()
    ]
    open_position = None
    if position is not None:
        open_position = {
            "direction": position.direction,
            "entry_ts": position.entry_ts.isoformat(),
            "entry_price": position.entry_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "hold_bars": int(len(frame) - 1 - position.entry_bar),
            "unrealized_trade_return_pct": round(
                (equity / position.entry_equity - 1.0) * 100.0,
                6,
            ),
        }
    return RunResult(
        spec=spec,
        metrics=metrics,
        slices=slices,
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position,
    )


def max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min() * 100.0)


def sharpe_ratio(returns: pd.Series) -> float:
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty or float(clean.std(ddof=0)) == 0.0:
        return 0.0
    return float(
        clean.mean() / clean.std(ddof=0) * math.sqrt(M15_PER_YEAR)
    )


def metrics_from_series(
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
    *,
    trading_cost_rate_total: float,
    funding_rate_total: float,
) -> dict[str, Any]:
    trade_returns = (
        trades["trade_return"].astype(float)
        if not trades.empty
        else pd.Series(dtype="float64")
    )
    wins = trade_returns[trade_returns > 0.0]
    losses = trade_returns[trade_returns < 0.0]
    profit_factor = (
        float(wins.sum() / abs(losses.sum()))
        if not losses.empty
        else None
    )
    direction_counts = (
        {
            "long": int((trades["direction"] == 1).sum()),
            "short": int((trades["direction"] == -1).sum()),
        }
        if not trades.empty
        else {"long": 0, "short": 0}
    )
    exit_counts = (
        {str(key): int(value) for key, value in trades["exit_reason"].value_counts().items()}
        if not trades.empty
        else {}
    )
    return {
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": max_drawdown_pct(
            pd.concat(
                [
                    pd.Series(
                        [1.0],
                        index=[equity.index[0] - pd.Timedelta(minutes=15)],
                    ),
                    equity,
                ]
            )
        ),
        "sharpe": sharpe_ratio(returns),
        "trades": int(len(trades)),
        "win_rate_pct": float((trade_returns > 0.0).mean() * 100.0)
        if not trade_returns.empty
        else 0.0,
        "profit_factor": profit_factor,
        "direction_counts": direction_counts,
        "exit_counts": exit_counts,
        "average_allocation": float(trades["allocation"].mean())
        if not trades.empty
        else 0.0,
        "max_allocation": float(trades["allocation"].max())
        if not trades.empty
        else 0.0,
        "trading_cost_rate_total": float(trading_cost_rate_total),
        "funding_rate_total": float(funding_rate_total),
    }


def slice_metrics(
    name: str,
    delta: pd.Timedelta,
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
) -> dict[str, Any]:
    cutoff = equity.index[-1] - delta
    mask = equity.index > cutoff
    selected_equity = equity.loc[mask]
    selected_returns = returns.loc[mask]
    if selected_equity.empty:
        return {
            "window": name,
            "start": None,
            "end": equity.index[-1].isoformat(),
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "trades": 0,
            "win_rate_pct": 0.0,
        }
    prior = equity.loc[equity.index <= cutoff]
    base_equity = float(prior.iloc[-1]) if not prior.empty else 1.0
    normalized = pd.concat(
        [
            pd.Series([base_equity], index=[cutoff]),
            selected_equity,
        ]
    )
    slice_trades = (
        trades.loc[pd.to_datetime(trades["exit_ts"], utc=True) > cutoff]
        if not trades.empty
        else trades
    )
    win_rate = (
        float((slice_trades["trade_return"].astype(float) > 0.0).mean() * 100.0)
        if not slice_trades.empty
        else 0.0
    )
    return {
        "window": name,
        "start": cutoff.isoformat(),
        "end": equity.index[-1].isoformat(),
        "return_pct": float((selected_equity.iloc[-1] / base_equity - 1.0) * 100.0),
        "max_drawdown_pct": max_drawdown_pct(normalized),
        "sharpe": sharpe_ratio(selected_returns),
        "trades": int(len(slice_trades)),
        "win_rate_pct": win_rate,
    }


def serialize_result(run: RunResult) -> dict[str, Any]:
    return {
        "spec": asdict(run.spec),
        "metrics": run.metrics,
        "slices": run.slices,
        "open_position": run.open_position,
    }


def write_artifacts(
    runs: list[RunResult],
    payload: dict[str, Any],
) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / f"{OUT_STEM}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    trade_frames = []
    for run in runs:
        frame = run.trades.copy()
        frame.insert(0, "variant", run.spec.name)
        trade_frames.append(frame)
    pd.concat(trade_frames, ignore_index=True).to_csv(
        ARTIFACT_DIR / f"{OUT_STEM}_trades.csv",
        index=False,
    )
    pd.concat(
        [run.equity_curve.rename(run.spec.name) for run in runs],
        axis=1,
    ).to_csv(ARTIFACT_DIR / f"{OUT_STEM}_equity.csv", index_label="ts")


def print_result(run: RunResult) -> None:
    metrics = run.metrics
    print(
        f"{run.spec.name:>30} | "
        f"ret {metrics['return_pct']:>9.2f}% "
        f"dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>5.2f} "
        f"n {metrics['trades']:>4} "
        f"win {metrics['win_rate_pct']:>6.2f}% "
        f"pf {metrics['profit_factor'] or 0.0:>5.2f}"
    )
    for row in run.slices:
        print(
            f"  {row['window']:>2}: "
            f"{row['return_pct']:>8.2f}% / "
            f"{row['max_drawdown_pct']:>7.2f}% / "
            f"n={row['trades']:>3}"
        )


def main() -> None:
    config = KeltnerConfig()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, funding, quality = load_data(warehouse)
    features = build_features(frame, config)
    specs = [
        RunSpec(
            name="keltner_only_atr_k1",
            entry_delay_bars=1,
            sizing_mode="atr_risk",
        ),
        RunSpec(
            name="keltner_only_fixed1x_k1",
            entry_delay_bars=1,
            sizing_mode="fixed",
            fixed_allocation=1.0,
        ),
        RunSpec(
            name="keltner_only_atr_k2",
            entry_delay_bars=2,
            sizing_mode="atr_risk",
        ),
    ]
    runs = [run_backtest(frame, funding, features, spec, config) for spec in specs]
    payload = {
        "strategy_family": "HYPE-15M-Keltner-Trend-Breakout",
        "research_id": "HYPE-15M-KTB pure Keltner initial diagnostic",
        "status": "explore / not promoted / not live-ready",
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "data_quality": quality,
        "selection_policy": (
            "No parameter search. K1 ATR-risk is the predeclared primary; "
            "fixed 1x and K2 are sizing/timing audits only. Recent slices were not used for selection."
        ),
        "signal": {
            "long": "closed K0 close > EMA96(close) + 2.4 * arithmetic-rolling ATR144",
            "short": "closed K0 close < EMA96(close) - 2.4 * arithmetic-rolling ATR144",
            "removed": ["EMA direction", "ADX/DI", "volume", "1h confirmation"],
        },
        "execution": {
            "primary_entry": "K0 closed signal -> K1 open market entry",
            "timing_audit": "K0 closed signal -> skip K1 -> K2 open market entry",
            "entry_atr": "latest completed arithmetic-rolling ATR672 before entry",
            "bracket": "entry-anchored TP4ATR / SL12ATR; stop-first; gap-through stop fills at worse open",
            "exit": "fixed bracket or 192-bar timeout at next open",
            "cooldown": "16 complete 15m bars after exit",
            "position_model": "single position, no pyramiding or same-bar re-entry",
        },
        "cost_model": {
            "fee_per_fill": config.fee_per_fill,
            "adverse_slippage_per_fill": config.adverse_slippage_per_fill,
            "funding": "actual Binance funding included",
        },
        "config": asdict(config),
        "runs": [serialize_result(run) for run in runs],
    }
    write_artifacts(runs, payload)
    print(
        f"data {quality['start']} -> {quality['end']} "
        f"rows={quality['rows']} blockers={quality['blocker_count']}"
    )
    for run in runs:
        print_result(run)
    print(f"artifacts -> {ARTIFACT_DIR / OUT_STEM}")


if __name__ == "__main__":
    main()
