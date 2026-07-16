from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_post24h_exit_floor_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"


@dataclass(frozen=True, slots=True)
class GuardConfig:
    name: str
    mode: str
    min_hold_bars: int = 96
    activation_mfe_atr: float = 4.5
    mfe_condition: str = "at_least"
    floor_atr: float = 0.0
    next_open_exit_reason: str = "post24h_next_open_exit"
    block_same_direction_until_signal_reset: bool = False


def variants() -> list[GuardConfig]:
    return [
        GuardConfig("v35_base", mode="none"),
        GuardConfig("exit_h12_m45", mode="next_open", min_hold_bars=48),
        GuardConfig("exit_h24_m425", mode="next_open", activation_mfe_atr=4.25),
        GuardConfig("exit_h24_m45", mode="next_open"),
        GuardConfig("exit_h24_m475", mode="next_open", activation_mfe_atr=4.75),
        GuardConfig("exit_h36_m45", mode="next_open", min_hold_bars=144),
        GuardConfig("floor_h24_m45_l35", mode="floor", floor_atr=3.5),
        GuardConfig("floor_h24_m45_l40", mode="floor", floor_atr=4.0),
        GuardConfig("floor_h24_m45_l425", mode="floor", floor_atr=4.25),
    ]


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def mfe_gate_passes(mfe_atr: float, guard: GuardConfig) -> bool:
    if guard.mfe_condition == "at_least":
        return mfe_atr >= guard.activation_mfe_atr
    if guard.mfe_condition == "below":
        return mfe_atr < guard.activation_mfe_atr
    raise ValueError(f"Unsupported MFE condition: {guard.mfe_condition}")


def check_intrabar_exit(
    *,
    position: base.Position,
    open_price: float,
    high: float,
    low: float,
    config: base.V35Config,
    floor_active: bool,
    floor_atr: float,
) -> tuple[str, float] | None:
    take = position.entry_price + position.direction * config.take_profit_atr * position.entry_atr
    hard_stop = position.entry_price - position.direction * config.hard_stop_atr * position.entry_atr
    effective_stop = (
        position.entry_price + position.direction * floor_atr * position.entry_atr
        if floor_active
        else hard_stop
    )
    if position.direction == 1:
        if low <= effective_stop:
            if floor_active:
                return (
                    "post24h_profit_floor",
                    min(open_price, effective_stop) if open_price <= effective_stop else effective_stop,
                )
            return "stop_loss", hard_stop
        if high >= take:
            return "take_profit", take
    else:
        if high >= effective_stop:
            if floor_active:
                return (
                    "post24h_profit_floor",
                    max(open_price, effective_stop) if open_price >= effective_stop else effective_stop,
                )
            return "stop_loss", hard_stop
        if low <= take:
            return "take_profit", take
    return None


def close_position(
    *,
    equity: float,
    position: base.Position,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    config: base.V35Config,
    guard_active: bool,
    activation_ts: pd.Timestamp | None,
    activation_mfe_atr: float | None,
    guard: GuardConfig,
) -> tuple[float, float]:
    result = base.close_position(
        equity=equity,
        position=position,
        exit_price=exit_price,
        exit_ts=exit_ts,
        exit_bar=exit_bar,
        reason=reason,
        trades=trades,
        config=config,
    )
    trades[-1].update(
        {
            "guard_mode": guard.mode,
            "guard_active": guard_active,
            "guard_activation_ts": activation_ts,
            "guard_activation_mfe_atr": activation_mfe_atr,
            "guard_floor_atr": guard.floor_atr if guard.mode == "floor" else None,
        }
    )
    return result


def run_backtest(
    *,
    guard: GuardConfig,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> base.RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    blocked_direction = 0
    guard_active = False
    activation_ts: pd.Timestamp | None = None
    activation_mfe_atr: float | None = None
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    no_floor = base.ProfitFloorConfig(enabled=False)

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            exiting_direction = position.direction
            exit_reason = pending_exit
            equity, cost = close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=exit_reason,
                trades=trades,
                config=config,
                guard_active=guard_active,
                activation_ts=activation_ts,
                activation_mfe_atr=activation_mfe_atr,
                guard=guard,
            )
            trading_costs += cost
            if (
                guard.block_same_direction_until_signal_reset
                and exit_reason == guard.next_open_exit_reason
            ):
                blocked_direction = exiting_direction
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
            long_signal = bool(features["long_signal"].iloc[signal_i])
            short_signal = bool(features["short_signal"].iloc[signal_i])
            if blocked_direction == 1 and not long_signal:
                blocked_direction = 0
            elif blocked_direction == -1 and not short_signal:
                blocked_direction = 0
            direction = 0
            if long_signal and not short_signal:
                direction = 1
            elif short_signal and not long_signal:
                direction = -1
            if direction == blocked_direction:
                direction = 0
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0:
                target = (
                    config.long_target_atr_pct
                    if direction == 1
                    else config.short_target_atr_pct
                )
                allocation = min(config.max_allocation, target / (entry_atr / open_price))
                cost = config.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = base.Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )
                guard_active = False
                activation_ts = None
                activation_mfe_atr = None

        if position is not None:
            intrabar = check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
                floor_active=guard_active and guard.mode == "floor",
                floor_atr=guard.floor_atr,
            )
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
                    guard_active=guard_active,
                    activation_ts=activation_ts,
                    activation_mfe_atr=activation_mfe_atr,
                    guard=guard,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (
                    close / position.previous_price - 1.0
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(position, high, low, config, no_floor)
                if (
                    guard.mode != "none"
                    and not guard_active
                    and i - position.entry_bar >= guard.min_hold_bars
                    and mfe_gate_passes(position.mfe_atr, guard)
                ):
                    guard_active = True
                    activation_ts = ts
                    activation_mfe_atr = position.mfe_atr
                    if guard.mode == "next_open":
                        pending_exit = guard.next_open_exit_reason
                can_indicator_exit = position.mfe_atr < config.disable_after_mfe_atr
                if pending_exit is None:
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
    equity_curve = pd.Series(equity_values, index=index, name=guard.name)
    returns = pd.Series(period_returns, index=index, name=f"{guard.name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{guard.name}_weight")
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
        name=guard.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=None,
    )


def hold_stats(trades: pd.DataFrame) -> dict[str, Any]:
    hold = trades["hold_bars"] * 0.25
    return {
        "mean_hours": round(float(hold.mean()), 2),
        "median_hours": round(float(hold.median()), 2),
        "p90_hours": round(float(hold.quantile(0.90)), 2),
        "max_hours": round(float(hold.max()), 2),
        "over_24h": int((hold > 24.0).sum()),
        "over_48h": int((hold > 48.0).sum()),
    }


def latest_path(trades: pd.DataFrame) -> list[dict[str, Any]]:
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out = out.loc[out["entry_ts"] >= pd.Timestamp("2026-07-03T00:00:00Z")].copy()
    out["hold_hours"] = out["hold_bars"] * 0.25
    out["trade_return_pct"] = out["trade_return"] * 100.0
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "entry_atr",
        "mfe_atr",
        "hold_hours",
        "guard_mode",
        "guard_active",
        "guard_activation_ts",
        "guard_activation_mfe_atr",
        "guard_floor_atr",
        "exit_reason",
        "exit_price",
        "trade_return_pct",
    ]
    return out[columns].to_dict("records")


def summarize(guard: GuardConfig, run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    guard_exits = run.trades["exit_reason"].isin(
        ["post24h_next_open_exit", "post24h_profit_floor"]
    )
    return {
        "guard": asdict(guard),
        "metrics": run.metrics,
        "capital_retention_vs_base_pct": round(
            float(run.equity_curve.iloc[-1] / baseline.equity_curve.iloc[-1] * 100.0),
            2,
        ),
        "activations": int(run.trades["guard_activation_ts"].notna().sum()),
        "guard_exits": int(guard_exits.sum()),
        "hold_stats": hold_stats(run.trades),
        "standard_slices": run.slices,
        "latest_path": latest_path(run.trades),
    }


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    config = base.V35Config()
    features = base.build_features(frame, config)
    guards = variants()
    runs = [
        run_backtest(
            guard=guard,
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        for guard in guards
    ]
    canonical = base.run_backtest(
        "canonical",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    baseline = runs[0]
    expected = canonical.trades.assign(
        guard_mode="none",
        guard_active=False,
        guard_activation_ts=None,
        guard_activation_mfe_atr=None,
        guard_floor_atr=None,
    )
    if baseline.metrics != canonical.metrics or not baseline.trades.equals(expected):
        raise RuntimeError("Custom engine failed canonical V35 parity.")

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 post-24h next-open exit / profit-floor",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "base_config": asdict(config),
        "execution_model": {
            "entry": "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1.",
            "base_bracket": "Fixed entry-ATR 5TP / 7SL; intrabar stop-first.",
            "activation": (
                "After a closed bar, require elapsed bars and historical MFE gates. "
                "The action becomes effective from the next 15m bar."
            ),
            "next_open": "Close at the next 15m open after activation.",
            "floor": (
                "Raise stop to the configured positive entry-ATR offset. If the next open "
                "has crossed the floor, fill at open; otherwise fill at the floor when touched."
            ),
            "cost": (
                "V35 canonical 0.00085 per fill, including fee and 4 bps adverse "
                "slippage; Binance funding included."
            ),
        },
        "selection_disclosure": (
            "The 24h/MFE4.5 rules were proposed after two near-TP live observations and "
            "are post-hoc. Adjacent thresholds and floor levels are sensitivity diagnostics."
        ),
        "engine_parity": "PASS: mode=none equals canonical V35 trades and metrics.",
        "rows": [
            summarize(guard, run, baseline)
            for guard, run in zip(guards, runs, strict=True)
        ],
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"gaps={quality['missing_15m_bars']}"
    )
    for row in payload["rows"]:
        metrics = row["metrics"]
        hold = row["hold_stats"]
        print(
            f"{row['guard']['name']:>22} ret={metrics['return_pct']:>8.2f}% "
            f"dd={metrics['max_drawdown_pct']:>7.2f}% sh={metrics['sharpe']:>4.2f} "
            f"retain={row['capital_retention_vs_base_pct']:>6.2f}% "
            f"acts={row['activations']:>2} exits={row['guard_exits']:>2} "
            f"median={hold['median_hours']:>5.2f}h max={hold['max_hours']:>5.2f}h"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
