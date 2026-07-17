from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    horizon_bars: int = 12
    take_profit_atr: float = 1.5
    stop_loss_atr: float = 1.0
    fee_rate_per_fill: float = 0.001
    slippage_bps_per_fill: float = 4.0
    initial_equity: float = 1.0
    long_threshold: float = 0.55
    short_threshold: float = 0.55
    probability_margin: float = 0.05
    signal_mode: str = "probability"
    edge_threshold_bps: float = 0.0
    edge_margin_bps: float = 0.0
    long_edge_threshold_bps: float | None = None
    short_edge_threshold_bps: float | None = None
    risk_per_trade: float | None = None
    max_leverage: float = 1.0
    max_consecutive_losses: int = 0
    loss_cooldown_bars: int = 0
    drawdown_pause_threshold: float = 1.0
    drawdown_cooldown_bars: int = 0


def _fill_price(price: float, direction: int, *, is_entry: bool, slippage_rate: float) -> float:
    if direction == 1:
        return price * (1.0 + slippage_rate) if is_entry else price * (1.0 - slippage_rate)
    return price * (1.0 - slippage_rate) if is_entry else price * (1.0 + slippage_rate)


def _funding_between(frame: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp, direction: int) -> float:
    if "funding_ts" not in frame.columns or "funding_rate" not in frame.columns:
        return 0.0
    events = frame[["funding_ts", "funding_rate"]].dropna().drop_duplicates("funding_ts")
    events = events[(events["funding_ts"] > start_ts) & (events["funding_ts"] <= end_ts)]
    if events.empty:
        return 0.0
    return float((-direction * events["funding_rate"]).sum())


def _simulate_trade(frame: pd.DataFrame, signal_index: int, direction: int, config: BacktestConfig) -> dict[str, Any] | None:
    entry_index = signal_index + 1
    if entry_index >= len(frame):
        return None
    atr_pct = float(frame.iloc[signal_index]["atr_pct_14"])
    if not np.isfinite(atr_pct) or atr_pct <= 0.0:
        return None
    entry_raw = float(frame.iloc[entry_index]["open"])
    if not np.isfinite(entry_raw) or entry_raw <= 0.0:
        return None
    slip = config.slippage_bps_per_fill / 10_000.0
    entry_price = _fill_price(entry_raw, direction, is_entry=True, slippage_rate=slip)
    if direction == 1:
        take_profit = entry_price * (1.0 + config.take_profit_atr * atr_pct)
        stop_loss = entry_price * (1.0 - config.stop_loss_atr * atr_pct)
    else:
        take_profit = entry_price * (1.0 - config.take_profit_atr * atr_pct)
        stop_loss = entry_price * (1.0 + config.stop_loss_atr * atr_pct)

    last_index = min(len(frame) - 1, entry_index + config.horizon_bars - 1)
    exit_index = last_index
    exit_raw = float(frame.iloc[last_index]["close"])
    reason = "timeout"
    for j in range(entry_index, last_index + 1):
        bar = frame.iloc[j]
        bar_open = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        if direction == 1:
            if bar_open <= stop_loss:
                exit_index, exit_raw, reason = j, bar_open, "stop_gap"
                break
            if bar_open >= take_profit:
                exit_index, exit_raw, reason = j, bar_open, "take_profit_gap"
                break
            if low <= stop_loss:
                exit_index, exit_raw, reason = j, stop_loss, "stop"
                break
            if high >= take_profit:
                exit_index, exit_raw, reason = j, take_profit, "take_profit"
                break
        else:
            if bar_open >= stop_loss:
                exit_index, exit_raw, reason = j, bar_open, "stop_gap"
                break
            if bar_open <= take_profit:
                exit_index, exit_raw, reason = j, bar_open, "take_profit_gap"
                break
            if high >= stop_loss:
                exit_index, exit_raw, reason = j, stop_loss, "stop"
                break
            if low <= take_profit:
                exit_index, exit_raw, reason = j, take_profit, "take_profit"
                break

    exit_price = _fill_price(exit_raw, direction, is_entry=False, slippage_rate=slip)
    gross_return = exit_price / entry_price - 1.0 if direction == 1 else entry_price / exit_price - 1.0
    fee_return = 2.0 * config.fee_rate_per_fill
    funding_return = _funding_between(frame, frame.iloc[entry_index]["ts"], frame.iloc[exit_index]["ts"], direction)
    underlying_net_return = gross_return - fee_return + funding_return
    if config.risk_per_trade is None:
        leverage = config.max_leverage
    else:
        stop_budget = (
            config.stop_loss_atr * atr_pct
            + 2.0 * (config.fee_rate_per_fill + slip)
        )
        leverage = min(
            config.max_leverage,
            config.risk_per_trade / max(stop_budget, 1e-9),
        )
    net_return = underlying_net_return * leverage
    return {
        "signal_ts": frame.iloc[signal_index]["ts"],
        "entry_ts": frame.iloc[entry_index]["ts"],
        "exit_ts": frame.iloc[exit_index]["ts"],
        "direction": direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "exit_reason": reason,
        "gross_return": gross_return,
        "fee_return": fee_return,
        "funding_return": funding_return,
        "underlying_net_return": underlying_net_return,
        "leverage": leverage,
        "net_return": net_return,
        "net_bps": net_return * 10_000.0,
        "holding_bars": exit_index - entry_index + 1,
        "_exit_index": exit_index,
    }


def summarize_trades(trades: list[dict[str, Any]], frame: pd.DataFrame, config: BacktestConfig) -> dict[str, Any]:
    if not trades:
        return {
            "config": asdict(config),
            "trade_count": 0,
            "total_return": 0.0,
            "annualized_multiple": 1.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_bps": 0.0,
            "long_trades": 0,
            "short_trades": 0,
        }
    returns = np.array([float(trade["net_return"]) for trade in trades], dtype="float64")
    equity = np.cumprod(1.0 + returns) * config.initial_equity
    equity_with_start = np.concatenate([[config.initial_equity], equity])
    peaks = np.maximum.accumulate(equity_with_start)
    max_drawdown = float(np.max(1.0 - equity_with_start / peaks))
    wins = returns > 0.0
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    days = max((pd.Timestamp(frame["ts"].max()) - pd.Timestamp(frame["ts"].min())).total_seconds() / 86_400.0, 1.0)
    annualized_multiple = float(equity[-1] ** (365.0 / days))
    return {
        "config": asdict(config),
        "trade_count": len(trades),
        "total_return": float(equity[-1] - 1.0),
        "annualized_multiple": annualized_multiple,
        "max_drawdown": max_drawdown,
        "win_rate": float(wins.mean()),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else float("inf"),
        "avg_trade_bps": float(returns.mean() * 10_000.0),
        "long_trades": sum(trade["direction"] == 1 for trade in trades),
        "short_trades": sum(trade["direction"] == -1 for trade in trades),
        "fee_return_total": float(sum(trade["fee_return"] for trade in trades)),
        "funding_return_total": float(sum(trade["funding_return"] for trade in trades)),
        "average_leverage": float(np.mean([trade["leverage"] for trade in trades])),
        "max_leverage_used": float(max(trade["leverage"] for trade in trades)),
    }


def run_prediction_backtest(frame: pd.DataFrame, config: BacktestConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = frame.sort_values("ts").reset_index(drop=True).copy()
    opens = pd.to_numeric(working["open"], errors="coerce").to_numpy(dtype="float64")
    highs = pd.to_numeric(working["high"], errors="coerce").to_numpy(dtype="float64")
    lows = pd.to_numeric(working["low"], errors="coerce").to_numpy(dtype="float64")
    closes = pd.to_numeric(working["close"], errors="coerce").to_numpy(dtype="float64")
    atrs = pd.to_numeric(working["atr_pct_14"], errors="coerce").to_numpy(dtype="float64")
    timestamps = pd.to_datetime(working["ts"], utc=True).to_numpy(dtype="datetime64[ns]")
    timestamp_ns = timestamps.astype("int64")
    if config.signal_mode == "probability":
        long_signals = pd.to_numeric(working.get("p_long"), errors="coerce").to_numpy(dtype="float64")
        short_signals = pd.to_numeric(working.get("p_short"), errors="coerce").to_numpy(dtype="float64")
    elif config.signal_mode == "expected_bps":
        long_signals = pd.to_numeric(working.get("pred_long_bps"), errors="coerce").to_numpy(dtype="float64")
        short_signals = pd.to_numeric(working.get("pred_short_bps"), errors="coerce").to_numpy(dtype="float64")
    else:
        raise ValueError(f"unsupported signal_mode: {config.signal_mode}")

    if "funding_ts" in working.columns and "funding_rate" in working.columns:
        funding_events = (
            working[["funding_ts", "funding_rate"]]
            .dropna()
            .drop_duplicates("funding_ts")
            .sort_values("funding_ts")
        )
        funding_event_ns = pd.to_datetime(
            funding_events["funding_ts"], utc=True
        ).to_numpy(dtype="datetime64[ns]").astype("int64")
        funding_rates = pd.to_numeric(
            funding_events["funding_rate"], errors="coerce"
        ).fillna(0.0).to_numpy(dtype="float64")
        funding_cumulative = np.concatenate([[0.0], np.cumsum(funding_rates)])
    else:
        funding_event_ns = np.array([], dtype="int64")
        funding_cumulative = np.array([0.0], dtype="float64")

    def funding_between(start_index: int, end_index: int, direction: int) -> float:
        left = int(np.searchsorted(funding_event_ns, timestamp_ns[start_index], side="right"))
        right = int(np.searchsorted(funding_event_ns, timestamp_ns[end_index], side="right"))
        return float(-direction * (funding_cumulative[right] - funding_cumulative[left]))

    trades: list[dict[str, Any]] = []
    index = 0
    next_allowed_index = 0
    consecutive_losses = 0
    equity = config.initial_equity
    peak_equity = config.initial_equity
    while index < len(working) - 1:
        if index < next_allowed_index:
            index += 1
            continue
        long_value = float(long_signals[index])
        short_value = float(short_signals[index])
        if not np.isfinite(long_value) or not np.isfinite(short_value):
            index += 1
            continue
        direction = 0
        if config.signal_mode == "probability":
            if (
                long_value >= config.long_threshold
                and long_value - short_value >= config.probability_margin
            ):
                direction = 1
            elif (
                short_value >= config.short_threshold
                and short_value - long_value >= config.probability_margin
            ):
                direction = -1
        else:
            long_edge_threshold = (
                config.edge_threshold_bps
                if config.long_edge_threshold_bps is None
                else config.long_edge_threshold_bps
            )
            short_edge_threshold = (
                config.edge_threshold_bps
                if config.short_edge_threshold_bps is None
                else config.short_edge_threshold_bps
            )
            if (
                long_value >= long_edge_threshold
                and long_value - short_value >= config.edge_margin_bps
            ):
                direction = 1
            elif (
                short_value >= short_edge_threshold
                and short_value - long_value >= config.edge_margin_bps
            ):
                direction = -1
        if direction == 0:
            index += 1
            continue
        entry_index = index + 1
        atr_pct = float(atrs[index])
        entry_raw = float(opens[entry_index])
        if (
            entry_index >= len(working)
            or not np.isfinite(atr_pct)
            or atr_pct <= 0.0
            or not np.isfinite(entry_raw)
            or entry_raw <= 0.0
        ):
            index += 1
            continue
        slip = config.slippage_bps_per_fill / 10_000.0
        entry_price = _fill_price(
            entry_raw, direction, is_entry=True, slippage_rate=slip
        )
        if direction == 1:
            take_profit = entry_price * (1.0 + config.take_profit_atr * atr_pct)
            stop_loss = entry_price * (1.0 - config.stop_loss_atr * atr_pct)
        else:
            take_profit = entry_price * (1.0 - config.take_profit_atr * atr_pct)
            stop_loss = entry_price * (1.0 + config.stop_loss_atr * atr_pct)
        last_index = min(len(working) - 1, entry_index + config.horizon_bars - 1)
        exit_index = last_index
        exit_raw = float(closes[last_index])
        reason = "timeout"
        for cursor in range(entry_index, last_index + 1):
            bar_open = float(opens[cursor])
            high = float(highs[cursor])
            low = float(lows[cursor])
            if direction == 1:
                if bar_open <= stop_loss:
                    exit_index, exit_raw, reason = cursor, bar_open, "stop_gap"
                    break
                if bar_open >= take_profit:
                    exit_index, exit_raw, reason = cursor, bar_open, "take_profit_gap"
                    break
                if low <= stop_loss:
                    exit_index, exit_raw, reason = cursor, stop_loss, "stop"
                    break
                if high >= take_profit:
                    exit_index, exit_raw, reason = cursor, take_profit, "take_profit"
                    break
            else:
                if bar_open >= stop_loss:
                    exit_index, exit_raw, reason = cursor, bar_open, "stop_gap"
                    break
                if bar_open <= take_profit:
                    exit_index, exit_raw, reason = cursor, bar_open, "take_profit_gap"
                    break
                if high >= stop_loss:
                    exit_index, exit_raw, reason = cursor, stop_loss, "stop"
                    break
                if low <= take_profit:
                    exit_index, exit_raw, reason = cursor, take_profit, "take_profit"
                    break
        exit_price = _fill_price(
            exit_raw, direction, is_entry=False, slippage_rate=slip
        )
        gross_return = (
            exit_price / entry_price - 1.0
            if direction == 1
            else entry_price / exit_price - 1.0
        )
        fee_return = 2.0 * config.fee_rate_per_fill
        funding_return = funding_between(entry_index, exit_index, direction)
        underlying_net_return = gross_return - fee_return + funding_return
        if config.risk_per_trade is None:
            leverage = config.max_leverage
        else:
            stop_budget = (
                config.stop_loss_atr * atr_pct
                + 2.0 * (config.fee_rate_per_fill + slip)
            )
            leverage = min(
                config.max_leverage,
                config.risk_per_trade / max(stop_budget, 1e-9),
            )
        net_return = underlying_net_return * leverage
        trade = {
            "signal_ts": pd.Timestamp(timestamps[index], tz="UTC"),
            "entry_ts": pd.Timestamp(timestamps[entry_index], tz="UTC"),
            "exit_ts": pd.Timestamp(timestamps[exit_index], tz="UTC"),
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "exit_reason": reason,
            "gross_return": gross_return,
            "fee_return": fee_return,
            "funding_return": funding_return,
            "underlying_net_return": underlying_net_return,
            "leverage": leverage,
            "net_return": net_return,
            "net_bps": net_return * 10_000.0,
            "holding_bars": exit_index - entry_index + 1,
        }
        equity *= 1.0 + float(trade["net_return"])
        peak_equity = max(peak_equity, equity)
        drawdown = 1.0 - equity / peak_equity
        trade["equity_after"] = equity
        trade["drawdown_after"] = drawdown
        if float(trade["net_return"]) > 0.0:
            consecutive_losses = 0
        else:
            consecutive_losses += 1
        trade["consecutive_losses_after"] = consecutive_losses
        if (
            config.max_consecutive_losses > 0
            and consecutive_losses >= config.max_consecutive_losses
        ):
            next_allowed_index = max(
                next_allowed_index, exit_index + config.loss_cooldown_bars
            )
            consecutive_losses = 0
        if drawdown >= config.drawdown_pause_threshold:
            next_allowed_index = max(
                next_allowed_index, exit_index + config.drawdown_cooldown_bars
            )
        trade["next_allowed_index"] = next_allowed_index
        trades.append(trade)
        index = exit_index
    trades_frame = pd.DataFrame(trades)
    return trades_frame, summarize_trades(trades, working, config)


def threshold_candidates() -> list[tuple[float, float, float]]:
    return [(threshold, threshold, margin) for threshold in (0.34, 0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.50) for margin in (0.00, 0.005, 0.01, 0.02, 0.03)]
