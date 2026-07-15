from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"
LATEST_CASE_ENTRY = pd.Timestamp("2026-07-13T14:45:00Z")


@dataclass(frozen=True, slots=True)
class GuardConfig:
    name: str
    enabled: bool
    activation_mfe_atr: float = 0.0
    lock_atr: float = 0.0
    reset_mode: str = "none"


@dataclass(slots=True)
class ResetState:
    blocked_direction: int = 0
    false_bars: int = 0


FLOOR_PAIRS = (
    (3.0, 0.5),
    (3.0, 1.0),
    (3.0, 1.5),
    (3.0, 1.75),
    (3.0, 2.0),
    (3.0, 2.25),
    (3.0, 2.5),
    (3.0, 2.75),
    (3.0, 3.0),
    (3.5, 1.0),
    (3.5, 1.5),
    (3.5, 2.0),
    (4.0, 1.5),
    (4.0, 2.0),
    (4.0, 2.5),
    (4.0, 3.0),
    (4.5, 2.5),
    (4.5, 3.0),
    (4.5, 3.5),
    (4.5, 4.0),
    (4.75, 3.5),
    (4.75, 4.0),
    (4.75, 4.25),
)
RESET_MODES = ("none", "signal_once", "signal_false4", "adx_cycle", "core_trend")


def fmt(value: float) -> str:
    return str(value).replace(".", "")


def variants() -> list[GuardConfig]:
    result = [GuardConfig("v35_base", enabled=False)]
    for activation, lock in FLOOR_PAIRS:
        for reset_mode in RESET_MODES:
            result.append(
                GuardConfig(
                    name=f"floor_a{fmt(activation)}_l{fmt(lock)}_{reset_mode}",
                    enabled=True,
                    activation_mfe_atr=activation,
                    lock_atr=lock,
                    reset_mode=reset_mode,
                )
            )
    return result


def signal_direction(features: pd.DataFrame, bar: int) -> int:
    is_long = bool(features["long_signal"].iloc[bar])
    is_short = bool(features["short_signal"].iloc[bar])
    if is_long and not is_short:
        return 1
    if is_short and not is_long:
        return -1
    return 0


def core_trend_is_valid(features: pd.DataFrame, bar: int, direction: int) -> bool:
    if direction == 1:
        return bool(
            float(features["ema_spread"].iloc[bar]) > 0.0
            and float(features["h1_plus_di"].iloc[bar])
            > float(features["h1_minus_di"].iloc[bar])
        )
    return bool(
        float(features["ema_spread"].iloc[bar]) < 0.0
        and float(features["h1_ema_spread"].iloc[bar]) < 0.0
    )


def update_reset_state(
    *,
    state: ResetState,
    guard: GuardConfig,
    features: pd.DataFrame,
    signal_bar: int,
    config: base.V35Config,
) -> None:
    if state.blocked_direction == 0:
        return
    direction = state.blocked_direction
    current_signal = signal_direction(features, signal_bar)
    if guard.reset_mode == "signal_once":
        reset_now = current_signal != direction
    elif guard.reset_mode == "signal_false4":
        state.false_bars = state.false_bars + 1 if current_signal != direction else 0
        reset_now = state.false_bars >= 4
    elif guard.reset_mode == "adx_cycle":
        threshold = config.long_adx_min if direction == 1 else config.short_adx_min
        reset_now = float(features["adx"].iloc[signal_bar]) < threshold
    elif guard.reset_mode == "core_trend":
        reset_now = not core_trend_is_valid(features, signal_bar, direction)
    elif guard.reset_mode == "none":
        reset_now = True
    else:
        raise ValueError(f"Unsupported reset mode: {guard.reset_mode}")
    if reset_now:
        state.blocked_direction = 0
        state.false_bars = 0


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
    reset_state = ResetState()
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    floor_config = base.ProfitFloorConfig(
        enabled=guard.enabled,
        tiers=((guard.activation_mfe_atr, guard.lock_atr),) if guard.enabled else (),
    )

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, cost = base.close_position(
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

        signal_bar = i - config.entry_delay_bars
        update_reset_state(
            state=reset_state,
            guard=guard,
            features=features,
            signal_bar=signal_bar,
            config=config,
        )
        current_signal = signal_direction(features, signal_bar)

        if position is None and not exited_this_bar and i > last_exit_bar:
            direction = 0 if current_signal == reset_state.blocked_direction else current_signal
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                target = config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
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

        if position is not None:
            intrabar = base.check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
            )
            if intrabar is not None:
                reason, exit_price = intrabar
                exited_direction = position.direction
                equity, cost = base.close_position(
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
                if reason == "profit_floor" and guard.reset_mode != "none":
                    reset_state.blocked_direction = exited_direction
                    reset_state.false_bars = 0
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (close / position.previous_price - 1.0)
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(
                    position,
                    high,
                    low,
                    config,
                    floor_config,
                )
                can_indicator_exit = position.mfe_atr < config.disable_after_mfe_atr
                adx_is_weak = float(features["adx"].iloc[i]) < config.adx_exit
                position.weak_bars = position.weak_bars + 1 if can_indicator_exit and adx_is_weak else 0
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
    open_position = None
    if position is not None:
        open_position = base.open_position_summary(position, frame.index[-1])
    return base.RunResult(
        name=guard.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position,
    )


def high_mfe_stats(trades: pd.DataFrame, threshold: float) -> dict[str, Any]:
    if trades.empty:
        return {"threshold": threshold, "trades": 0, "losses": 0, "loss_rate_pct": None}
    qualified = trades.loc[trades["mfe_atr"].ge(threshold)]
    losses = qualified.loc[qualified["trade_return"].le(0.0)]
    return {
        "threshold": threshold,
        "trades": int(len(qualified)),
        "losses": int(len(losses)),
        "loss_rate_pct": base.pct(len(losses) / len(qualified)) if len(qualified) else None,
        "loss_cases": [
            {
                "entry_ts": pd.Timestamp(row["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(row["exit_ts"]).isoformat(),
                "direction": int(row["direction"]),
                "mfe_atr": round(float(row["mfe_atr"]), 6),
                "exit_reason": str(row["exit_reason"]),
                "trade_return_pct": base.pct(float(row["trade_return"])),
            }
            for _, row in losses.iterrows()
        ],
    }


def latest_case(run: base.RunResult) -> dict[str, Any]:
    if run.trades.empty:
        return {"state": "not_present"}
    entries = pd.to_datetime(run.trades["entry_ts"], utc=True)
    matched = run.trades.loc[entries.eq(LATEST_CASE_ENTRY)]
    if matched.empty:
        return {"state": "not_present"}
    row = matched.iloc[0]
    return {
        "state": "closed",
        "exit_ts": pd.Timestamp(row["exit_ts"]).isoformat(),
        "exit_price": float(row["exit_price"]),
        "mfe_atr": round(float(row["mfe_atr"]), 6),
        "exit_reason": str(row["exit_reason"]),
        "trade_return_pct": base.pct(float(row["trade_return"])),
    }


def summarize(guard: GuardConfig, run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    base_multiple = float(baseline.equity_curve.iloc[-1])
    run_multiple = float(run.equity_curve.iloc[-1])
    return {
        "name": run.name,
        "guard": asdict(guard),
        "metrics": run.metrics,
        "capital_retention_vs_base_pct": base.pct(run_multiple / base_multiple),
        "high_mfe": {
            str(threshold): high_mfe_stats(run.trades, threshold)
            for threshold in (3.0, 4.0, 4.5, 4.75)
        },
        "latest_case": latest_case(run),
        "standard_slices": run.slices,
    }


def ranking_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["metrics"]
    return (
        -row["high_mfe"]["4.0"]["losses"],
        metrics["max_drawdown_pct"],
        -row["high_mfe"]["3.0"]["losses"],
        metrics["return_pct"],
    )


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--source", choices=["binance_api", "data_lake"], default="binance_api")
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if args.source == "binance_api":
        frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    else:
        warehouse = base.DuckDBWarehouse(
            base.DataLakeLayout.from_settings(base.load_settings(None))
        )
        frame, funding, quality = base.load_data(warehouse)

    config = base.V35Config()
    features = ab.build_signals(base.build_features(frame, config), config, ab.SignalFlags())
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
    baseline = runs[0]
    rows = [summarize(guard, run, baseline) for guard, run in zip(guards, runs, strict=True)]
    ranked = sorted(rows[1:], key=ranking_key, reverse=True)
    shortlisted_names = ["v35_base", *[row["name"] for row in ranked[:8]]]
    shortlisted_runs = [run for run in runs if run.name in shortlisted_names]

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 high-MFE final-loss prevention 2026-07-15",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "cost_model": (
            "V35 canonical override: 0.00085 per fill, representing fee plus "
            "4 bps adverse slippage; Binance funding included."
        ),
        "execution_model": {
            "entry": "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1.",
            "bracket": "Fixed entry-ATR 5.0 TP / 7.0 SL; intrabar stop-first.",
            "floor": (
                "MFE is updated at closed 15m bar. The floor becomes active from the "
                "next bar; crossed next open fills at open, otherwise at stop."
            ),
            "reset_modes": {
                "none": "No post-floor re-entry block.",
                "signal_once": "Block same direction until its full entry signal is false once.",
                "signal_false4": "Block until the same-direction full entry signal is false for four consecutive bars.",
                "adx_cycle": "Block until ADX drops below that direction's entry threshold.",
                "core_trend": "Block until the direction's EMA/1h directional core becomes invalid.",
            },
        },
        "selection_disclosure": (
            "This is an in-sample diagnostic grid selected directly on full return, "
            "drawdown and high-MFE loss counts. Standard slices are audit outputs only; "
            "no candidate is promotion-ready without future OOS."
        ),
        "base_config": asdict(config),
        "objective": {
            "primary": "Minimize closed trades with MFE>=4ATR and net trade_return<=0.",
            "secondary": "Improve max drawdown, then minimize MFE>=3ATR losses.",
            "tertiary": "Maximize retained compounded return.",
        },
        "baseline_high_mfe": {
            str(threshold): high_mfe_stats(baseline.trades, threshold)
            for threshold in (1.5, 2.0, 3.0, 4.0, 4.5, 4.75)
        },
        "rows": rows,
        "ranked_names": [row["name"] for row in ranked],
        "shortlisted_names": shortlisted_names,
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_shortlist_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_shortlist_equity.csv"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(shortlisted_runs, trades_path=trades_path, equity_path=equity_path)

    print(
        f"data: {quality.get('start')} ~ {quality.get('end')} "
        f"rows={quality.get('rows')} gaps={quality.get('missing_15m_bars')}"
    )
    print(
        f"base: ret={baseline.metrics['return_pct']:.2f}% "
        f"dd={baseline.metrics['max_drawdown_pct']:.2f}% "
        f"mfe4_losses={high_mfe_stats(baseline.trades, 4.0)['losses']}"
    )
    print("\nranked top 15:")
    for row in ranked[:15]:
        metrics = row["metrics"]
        print(
            f"{row['name']:>38} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% sh {metrics['sharpe']:>4.2f} "
            f"mfe4loss {row['high_mfe']['4.0']['losses']} "
            f"mfe3loss {row['high_mfe']['3.0']['losses']} "
            f"retain {row['capital_retention_vs_base_pct']:>6.2f}% "
            f"latest {row['latest_case']}"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
