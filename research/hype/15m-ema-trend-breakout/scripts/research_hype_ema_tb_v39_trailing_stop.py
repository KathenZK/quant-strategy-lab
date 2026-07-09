from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39_ab


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_trailing_stop_2026-07-09"


@dataclass(frozen=True, slots=True)
class TrailConfig:
    name: str
    enabled: bool
    activation_mfe_atr: float = 0.0
    trail_distance_atr: float = 0.0
    note: str = ""


@dataclass(slots=True)
class TrailPosition:
    direction: int
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    mfe_atr: float = 0.0
    weak_bars: int = 0
    trailing_offset_atr: float | None = None


def trail_variants() -> list[TrailConfig]:
    variants = [TrailConfig("v39_base", enabled=False, note="V39 baseline without trailing stop")]
    for activation in [0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
        for distance in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
            if activation == 0.0 and distance <= 2.0:
                # 这类等价于把初始止损从 7ATR 直接收紧到 1-2ATR，先不纳入主扫描。
                continue
            variants.append(
                TrailConfig(
                    name=f"trail_a{fmt(activation)}_d{fmt(distance)}",
                    enabled=True,
                    activation_mfe_atr=activation,
                    trail_distance_atr=distance,
                    note=(
                        f"MFE>={activation:g}ATR 后启用，stop = best favorable excursion - {distance:g}ATR；"
                        "收盘更新，下一根生效"
                    ),
                )
            )
    return variants


def fmt(value: float) -> str:
    return str(value).replace(".", "")


def run_backtest_trailing(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
    trail_cfg: TrailConfig,
) -> base.RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: TrailPosition | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, cost = close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_pnl = -position.direction * position.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        if position is None and not exited_this_bar and i > last_exit_bar:
            signal_i = i - config.entry_delay_bars
            direction = 0
            if bool(features["long_signal"].iloc[signal_i]) and not bool(features["short_signal"].iloc[signal_i]):
                direction = 1
            elif bool(features["short_signal"].iloc[signal_i]) and not bool(features["long_signal"].iloc[signal_i]):
                direction = -1
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                target = config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
                allocation = min(config.max_allocation, target / (entry_atr / open_price))
                cost = config.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = TrailPosition(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )

        if position is not None:
            intrabar = check_intrabar_exit(position, open_price, high, low, config)
            if intrabar is not None:
                reason, exit_price = intrabar
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (close / position.previous_price - 1.0)
                equity *= 1.0 + pnl
                position.previous_price = close
                update_position_on_close(position, high, low, trail_cfg)
                can_indicator_exit = position.mfe_atr < config.disable_after_mfe_atr
                if can_indicator_exit and float(features["adx"].iloc[i]) < config.adx_exit:
                    position.weak_bars += 1
                else:
                    position.weak_bars = 0
                if can_indicator_exit and position.weak_bars >= config.delayed_bars:
                    pending_exit = "indicator_exit"
                if pending_exit is None and i - position.entry_bar >= config.max_hold_bars:
                    pending_exit = "timeout"

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)
        weight_values.append(0.0 if position is None else position.direction * position.allocation)

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=name)
    returns = pd.Series(period_returns, index=index, name=f"{name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{name}_weight")
    trades_frame = pd.DataFrame(trades)
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    return base.RunResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position_summary(position, frame.index[-1]) if position is not None else None,
    )


def check_intrabar_exit(
    position: TrailPosition,
    open_price: float,
    high: float,
    low: float,
    config: base.V35Config,
) -> tuple[str, float] | None:
    take = position.entry_price + position.direction * config.take_profit_atr * position.entry_atr
    hard_stop = position.entry_price - position.direction * config.hard_stop_atr * position.entry_atr
    effective_stop = hard_stop
    trailing_active = position.trailing_offset_atr is not None
    if trailing_active:
        trailing_stop = position.entry_price + position.direction * float(position.trailing_offset_atr) * position.entry_atr
        effective_stop = max(hard_stop, trailing_stop) if position.direction == 1 else min(hard_stop, trailing_stop)

    if position.direction == 1:
        if low <= effective_stop:
            if trailing_active and effective_stop > hard_stop:
                return "trailing_stop", min(open_price, effective_stop) if open_price <= effective_stop else effective_stop
            return "stop_loss", hard_stop
        if high >= take:
            return "take_profit", take
    else:
        if high >= effective_stop:
            if trailing_active and effective_stop < hard_stop:
                return "trailing_stop", max(open_price, effective_stop) if open_price >= effective_stop else effective_stop
            return "stop_loss", hard_stop
        if low <= take:
            return "take_profit", take
    return None


def update_position_on_close(position: TrailPosition, high: float, low: float, trail_cfg: TrailConfig) -> None:
    if position.direction == 1:
        excursion = (high - position.entry_price) / position.entry_atr
    else:
        excursion = (position.entry_price - low) / position.entry_atr
    position.mfe_atr = max(position.mfe_atr, float(excursion))
    if not trail_cfg.enabled or position.mfe_atr < trail_cfg.activation_mfe_atr:
        return
    next_offset = position.mfe_atr - trail_cfg.trail_distance_atr
    if position.trailing_offset_atr is None:
        position.trailing_offset_atr = next_offset
    else:
        position.trailing_offset_atr = max(position.trailing_offset_atr, next_offset)


def close_position(
    *,
    equity: float,
    position: TrailPosition,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    config: base.V35Config,
) -> tuple[float, float]:
    pnl = position.direction * position.allocation * (exit_price / position.previous_price - 1.0)
    cost = config.trade_cost_rate * position.allocation
    exit_equity = equity * (1.0 + pnl - cost)
    raw_price_return = position.direction * (exit_price / position.entry_price - 1.0)
    trades.append(
        {
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "mfe_atr": position.mfe_atr,
            "trailing_offset_atr": position.trailing_offset_atr,
            "exit_reason": reason,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "raw_price_return": raw_price_return,
            "trade_return": exit_equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": exit_equity,
        }
    )
    return exit_equity, cost


def open_position_summary(position: TrailPosition, data_end: pd.Timestamp) -> dict[str, Any]:
    return {
        "data_end": pd.Timestamp(data_end).isoformat(),
        "direction": position.direction,
        "entry_ts": position.entry_ts.isoformat(),
        "entry_price": position.entry_price,
        "entry_atr": position.entry_atr,
        "allocation": position.allocation,
        "mfe_atr": position.mfe_atr,
        "weak_bars": position.weak_bars,
        "trailing_offset_atr": position.trailing_offset_atr,
        "trailing_stop_price": (
            position.entry_price + position.direction * position.trailing_offset_atr * position.entry_atr
            if position.trailing_offset_atr is not None
            else None
        ),
    }


def summarize(cfg: TrailConfig, run: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "trail_config": asdict(cfg),
        "metrics": run.metrics,
        "slices": run.slices,
        "d90": ab.window_stats(run, 90),
        "d30": ab.window_stats(run, 30),
        "long_side": ab.side_stats(run, 1),
        "short_side": ab.side_stats(run, -1),
        "open_position": run.open_position,
    }


def add_deltas(rows: list[dict[str, Any]]) -> None:
    base_row = next(row for row in rows if row["name"] == "v39_base")
    for row in rows:
        row["delta_vs_v39"] = {
            "full_return_pp": round(row["metrics"]["return_pct"] - base_row["metrics"]["return_pct"], 2),
            "full_maxdd_pp": round(row["metrics"]["max_drawdown_pct"] - base_row["metrics"]["max_drawdown_pct"], 2),
            "sharpe": round(row["metrics"]["sharpe"] - base_row["metrics"]["sharpe"], 4),
            "trades": row["metrics"]["trades"] - base_row["metrics"]["trades"],
            "win_rate_pp": round(row["metrics"]["win_rate_pct"] - base_row["metrics"]["win_rate_pct"], 2),
            "d90_return_pp": round(row["d90"]["return_pct"] - base_row["d90"]["return_pct"], 2),
            "d90_maxdd_pp": round(row["d90"]["max_drawdown_pct"] - base_row["d90"]["max_drawdown_pct"], 2),
            "d90_win_rate_pp": round((row["d90"]["win_rate_pct"] or 0.0) - (base_row["d90"]["win_rate_pct"] or 0.0), 2),
        }


def print_row(row: dict[str, Any]) -> None:
    metrics = row["metrics"]
    d90 = row["d90"]
    print(
        f"{row['name']:>18} | full {metrics['return_pct']:>9.2f}% dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>5.2f} n {metrics['trades']:>3} win {metrics['win_rate_pct']:>6.2f}% "
        f"| 90d {d90['return_pct']:>8.2f}% dd {d90['max_drawdown_pct']:>7.2f}% "
        f"win {d90['win_rate_pct'] or 0:>6.2f}% "
        f"| exits {metrics['exit_counts']}"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)
    config = v39_ab.v39_config()
    features = ab.build_signals(base.build_features(frame, config), config, v39_ab.v39_flags())

    rows: list[dict[str, Any]] = []
    runs: list[base.RunResult] = []
    variants = trail_variants()
    for trail_cfg in variants:
        run = run_backtest_trailing(trail_cfg.name, frame, funding, features, config, trail_cfg)
        runs.append(run)
        row = summarize(trail_cfg, run)
        rows.append(row)
        print_row(row)

    add_deltas(rows)
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V39 trailing stop diagnostic",
        "baseline": "HYPE-EMA-TB-V39",
        "data_quality": quality,
        "cost_model": "Binance USD-M perp, 0.00085 per fill (fee + 4bps slippage combined), funding included.",
        "execution_assumptions": {
            "entry": "K0 close signal, K2 open entry, entry ATR from K1 completed bar.",
            "tp_sl": "TP/SL/trailing checked intrabar by 15m high/low, stop first when both stop and TP are crossed.",
            "trailing_timing": "MFE and trailing stop level are updated only after a 15m bar closes; the updated trailing stop is active from the next bar.",
            "trailing_gap_fill": "If next bar open has crossed the trailing stop, fill at open; otherwise fill at the trailing stop price.",
        },
        "v39_config": asdict(config),
        "v39_flags": asdict(v39_ab.v39_flags()),
        "rows": rows,
    }

    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)
    print(f"\nsummary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
