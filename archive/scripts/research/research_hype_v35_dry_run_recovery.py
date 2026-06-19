from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from strategy_lab.strategies.candle_count_short.intrabar_backtest import (
    BarsPerYear,
    CandleCountIntrabarBacktestConfig,
    _atr_pct,
    _dynamic_pct,
    _entry_allocation,
    _entry_allowed,
    _intrabar_exit,
    _metrics,
    _normalize_frame,
    _trade_bounds,
    _trend_filter_allows,
    _trend_return,
    build_candle_count_signal,
)


REPORT_DIR = Path("reports")
SUMMARY_PATH = REPORT_DIR / "hype_v35_dry_run_recovery_summary.json"
TRADES_PATH = REPORT_DIR / "hype_v35_dry_run_recovery_trades.csv"
EQUITY_PATH = REPORT_DIR / "hype_v35_dry_run_recovery_equity.csv"
SCAN_PATH = REPORT_DIR / "hype_v35_dry_run_recovery_scan.csv"
FIXED_SKIP_SCAN_PATH = REPORT_DIR / "hype_v35_fixed_skip_reset_scan.csv"


@dataclass(frozen=True, slots=True)
class V35Run:
    equity_curve: pd.Series
    period_returns: pd.Series
    weights: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, float]


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    name: str
    trigger: Literal["losing_trade", "losing_streak", "below_initial"]
    resume: Literal[
        "dry_profitable_trade",
        "dry_segment_breakeven",
        "shadow_above_initial",
    ]
    loss_threshold: int = 1


def main() -> None:
    frame = load_hype_frame_from_lake()
    config = hype_v35_config()
    run = run_v35(frame, config)

    policies = [
        RecoveryPolicy(
            name="loss_trade_pause_until_dry_breakeven",
            trigger="losing_trade",
            resume="dry_segment_breakeven",
        ),
        RecoveryPolicy(
            name="underwater_pause_until_shadow_above_initial",
            trigger="below_initial",
            resume="shadow_above_initial",
        ),
    ]
    policies.extend(
        RecoveryPolicy(
            name=f"loss_streak_{loss_threshold}_pause_until_dry_win",
            trigger="losing_streak",
            resume="dry_profitable_trade",
            loss_threshold=loss_threshold,
        )
        for loss_threshold in range(1, 7)
    )
    policies.extend(
        RecoveryPolicy(
            name=f"loss_streak_{loss_threshold}_pause_until_dry_breakeven",
            trigger="losing_streak",
            resume="dry_segment_breakeven",
            loss_threshold=loss_threshold,
        )
        for loss_threshold in range(2, 7)
    )
    overlays = [apply_recovery_policy(run, policy) for policy in policies]
    fixed_skip_overlays = [
        apply_fixed_skip_reset_policy(run, loss_threshold=2, skip_trades=skip_trades)
        for skip_trades in (1, 2, 3, 4, 5, 6, 8, 10)
    ]
    overlays.extend(fixed_skip_overlays)
    windows = build_window_rows(run, overlays)
    scan = build_scan_rows(overlays)
    fixed_skip_scan = [overlay["summary"] for overlay in fixed_skip_overlays]

    summary = {
        "data": {
            "rows": int(len(frame)),
            "start": run.equity_curve.index[0].isoformat(),
            "end": run.equity_curve.index[-1].isoformat(),
            "source": "data/normalized Binance HYPE 15m trade + mark + funding",
        },
        "baseline": compact_metrics("V35 baseline", run.metrics),
        "policies": [overlay["summary"] for overlay in overlays],
        "scan": scan,
        "fixed_skip_reset_scan": fixed_skip_scan,
        "windows": windows,
        "assumptions": {
            "baseline": "HYPE candle-count V35: 10/8 signal, target_atr_pct=0.006, ATR672, 3/3 early exit, bidirectional 12/9 counter.",
            "loss_trade_pause_until_dry_breakeven": "A losing real closed trade disables real entries. The strategy continues as a dry-run from the next signal. Real entries resume only after skipped dry-run closed trades compound back to >= 1.0 for that pause episode.",
            "loss_streak_scan": "For N=1..6, real entries pause after N consecutive losing real closed trades. The dry-win variant resumes after the first profitable skipped trade; the dry-breakeven variant resumes after skipped trades compound back to >= 1.0.",
            "fixed_skip_reset_scan": "After 2 consecutive losing real closed trades, skip a fixed number of shadow trades, then resume real entries directly. The real account stop-loss risk multiplier is reset to 1.0 before the next real entry.",
            "underwater_pause_until_shadow_above_initial": "Real entries are disabled while the full shadow V35 equity is below initial capital; real resumes after shadow equity is back to >= 1.0.",
            "resume_timing": "If dry-run recovers during a virtual trade, the next real entry is allowed only after that virtual trade closes.",
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    trade_frames = []
    baseline_trades = run.trades.copy()
    baseline_trades.insert(0, "policy", "V35 baseline")
    trade_frames.append(baseline_trades)
    equity_frames = [
        run.equity_curve.rename("V35 baseline").to_frame(),
    ]
    for overlay in overlays:
        trades = overlay["trades"].copy()
        trades.insert(0, "policy", overlay["summary"]["name"])
        trade_frames.append(trades)
        equity_frames.append(overlay["equity_curve"].rename(overlay["summary"]["name"]).to_frame())

    pd.concat(trade_frames, ignore_index=True).to_csv(TRADES_PATH, index=False)
    pd.concat(equity_frames, axis=1).to_csv(EQUITY_PATH, index_label="ts")
    pd.DataFrame(scan).to_csv(SCAN_PATH, index=False)
    pd.DataFrame(fixed_skip_scan).to_csv(FIXED_SKIP_SCAN_PATH, index=False)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {SUMMARY_PATH}")
    print(f"Wrote {TRADES_PATH}")
    print(f"Wrote {EQUITY_PATH}")
    print(f"Wrote {SCAN_PATH}")
    print(f"Wrote {FIXED_SKIP_SCAN_PATH}")


def hype_v35_config() -> CandleCountIntrabarBacktestConfig:
    return CandleCountIntrabarBacktestConfig(
        min_count=8,
        lookback=10,
        allocation=3.0,
        allocation_atr_window=672,
        target_atr_pct=0.006,
        stop_loss_pct=0.03,
        stop_loss_atr_window=672,
        stop_loss_atr_multiplier=5.0,
        min_stop_loss_pct=0.025,
        max_stop_loss_pct=0.035,
        take_profit_pct=0.03,
        take_profit_atr_window=672,
        take_profit_atr_multiplier=5.5,
        min_take_profit_pct=0.020,
        max_take_profit_pct=0.035,
        trend_window_bars=96,
        trend_block_pct=0.05,
        cooldown_bars=8,
        opposite_signal_gap_bars=8,
        entry_mode="signal_start",
        stop_loss_risk_multiplier=0.5,
        min_risk_multiplier=0.0625,
        fee_rate=0.00045,
        slippage_rate=0.0004,
        annualization_bars=BarsPerYear,
    )


def load_hype_frame_from_lake() -> pd.DataFrame:
    lake_root = Path("data/normalized")
    ohlcv_files = sorted(
        (
            lake_root
            / "ohlcv/exchange=binance/market_type=perp/timeframe=15m"
        ).glob("date=*/symbol=hype_usdt_usdt.parquet")
    )
    mark_files = sorted(
        (
            lake_root
            / "mark_price_klines/exchange=binance/market_type=perp/timeframe=15m"
        ).glob("date=*/symbol=hype_usdt_usdt.parquet")
    )
    funding_files = sorted(
        (
            lake_root
            / "funding_rates/exchange=binance/market_type=perp"
        ).glob("date=*/symbol=hype_usdt_usdt.parquet")
    )
    if not ohlcv_files:
        raise FileNotFoundError("missing local HYPE 15m OHLCV data lake files")
    if not mark_files:
        raise FileNotFoundError("missing local HYPE 15m mark-price data lake files")

    trade = pd.concat((pd.read_parquet(path) for path in ohlcv_files), ignore_index=True)
    mark = pd.concat((pd.read_parquet(path) for path in mark_files), ignore_index=True)
    if "is_closed" in trade.columns:
        trade = trade.loc[trade["is_closed"].fillna(True)]

    trade["ts"] = pd.to_datetime(trade["ts"], utc=True)
    mark["ts"] = pd.to_datetime(mark["ts"], utc=True)
    trade = (
        trade.sort_values("ts")
        .drop_duplicates(subset=["ts"], keep="last")
        .set_index("ts")
    )
    mark = (
        mark.sort_values("ts")
        .drop_duplicates(subset=["ts"], keep="last")
        .set_index("ts")
    )

    frame = trade[["open", "high", "low", "close", "volume"]].join(
        mark[["high", "low"]].rename(columns={"high": "mark_high", "low": "mark_low"}),
        how="inner",
    )
    if funding_files:
        funding = pd.concat((pd.read_parquet(path) for path in funding_files), ignore_index=True)
        funding["ts"] = pd.to_datetime(funding["ts"], utc=True).dt.floor("15min")
        funding_rate = (
            funding.sort_values("ts")
            .drop_duplicates(subset=["ts"], keep="last")
            .set_index("ts")["funding_rate"]
        )
        frame["funding_rate"] = funding_rate.reindex(frame.index).fillna(0.0)
    else:
        frame["funding_rate"] = 0.0
    return frame.sort_index()


def run_v35(
    frame: pd.DataFrame,
    config: CandleCountIntrabarBacktestConfig,
    *,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
) -> V35Run:
    frame = _normalize_frame(frame)
    signal = build_candle_count_signal(frame, config)
    funding_rate = (
        frame.get("funding_rate", pd.Series(0.0, index=frame.index))
        .fillna(0.0)
        .astype("float64")
    )
    open_price = frame["open"].astype("float64")
    close = frame["close"].astype("float64")
    mark_high = frame["mark_high"].astype("float64")
    mark_low = frame["mark_low"].astype("float64")
    allocation_atr = _atr_pct(frame, config.allocation_atr_window)
    stop_loss_atr = _atr_pct(frame, config.stop_loss_atr_window)
    take_profit_atr = _atr_pct(frame, config.take_profit_atr_window)
    trend_return = _trend_return(close, config.trend_window_bars)
    start_position, end_position = _trade_bounds(
        frame,
        trade_start=trade_start,
        trade_end=trade_end,
    )

    cost_rate = config.fee_rate + config.slippage_rate
    equity = 1.0
    previous_price = float(close.iloc[start_position])
    current_direction = 0
    entry_position: int | None = None
    entry_ts: pd.Timestamp | None = None
    entry_price = np.nan
    entry_equity = np.nan
    current_allocation = 0.0
    current_base_allocation = 0.0
    current_risk_multiplier_at_entry = 1.0
    current_stop_loss_pct = config.stop_loss_pct
    current_take_profit_pct = config.take_profit_pct
    risk_multiplier = 1.0
    cooldown_remaining = 0
    scheduled_early_exit_position: int | None = None
    scheduled_early_exit_reason: str | None = None

    equity_values: list[float] = []
    period_returns: list[float] = []
    weights: list[float] = []
    trades: list[dict[str, object]] = []
    trading_costs = 0.0
    funding_pnl = 0.0
    stops = 0
    takes = 0
    early_main = 0
    early_counter_opposite = 0
    early_counter_favorable = 0
    entries = 0
    exits = 0
    long_entries = 0
    short_entries = 0

    for position in range(start_position, end_position + 1):
        ts = pd.Timestamp(frame.index[position])
        close_price = float(close.iloc[position])
        bar_return = 0.0
        exited_this_bar = False
        cooldown_at_start = cooldown_remaining

        if position > start_position and current_direction != 0:
            if scheduled_early_exit_position == position:
                exit_price = float(open_price.iloc[position])
                exit_reason = scheduled_early_exit_reason
            else:
                exit_price, exit_reason = _intrabar_exit(
                    direction=current_direction,
                    entry_price=float(entry_price),
                    mark_high=float(mark_high.iloc[position]),
                    mark_low=float(mark_low.iloc[position]),
                    stop_loss_pct=current_stop_loss_pct,
                    take_profit_pct=current_take_profit_pct,
                )

            if exit_price is None:
                pnl = current_direction * current_allocation * (close_price / previous_price - 1.0)
                equity *= 1.0 + pnl
                bar_return += pnl
                previous_price = close_price
            else:
                pnl = current_direction * current_allocation * (float(exit_price) / previous_price - 1.0)
                cost = current_allocation * cost_rate
                equity *= 1.0 + pnl - cost
                bar_return += pnl - cost
                previous_price = close_price
                trading_costs += cost
                exits += 1
                if exit_reason == "stop":
                    stops += 1
                    risk_multiplier = max(
                        config.min_risk_multiplier,
                        risk_multiplier * config.stop_loss_risk_multiplier,
                    )
                elif exit_reason == "take":
                    takes += 1
                    risk_multiplier = 1.0
                elif exit_reason == "early_main":
                    early_main += 1
                elif exit_reason == "early_counter_opposite":
                    early_counter_opposite += 1
                elif exit_reason == "early_counter_favorable":
                    early_counter_favorable += 1
                trades.append(
                    {
                        "entry_ts": entry_ts,
                        "exit_ts": ts,
                        "direction": current_direction,
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "allocation": current_allocation,
                        "base_allocation": current_base_allocation,
                        "risk_multiplier_at_entry": current_risk_multiplier_at_entry,
                        "exit_reason": exit_reason,
                        "entry_equity": float(entry_equity),
                        "exit_equity": equity,
                        "trade_return": equity / float(entry_equity) - 1.0,
                        "period_start": int(entry_position),
                        "period_end": position,
                    }
                )
                current_direction = 0
                entry_position = None
                entry_ts = None
                entry_price = np.nan
                entry_equity = np.nan
                current_allocation = 0.0
                current_base_allocation = 0.0
                current_risk_multiplier_at_entry = 1.0
                scheduled_early_exit_position = None
                scheduled_early_exit_reason = None
                exited_this_bar = True
                cooldown_remaining = max(cooldown_remaining, config.cooldown_bars)
        elif position > start_position:
            previous_price = close_price

        if (
            current_direction != 0
            and entry_position is not None
            and scheduled_early_exit_position is None
            and position + 1 <= end_position
        ):
            early_reason = _v35_early_exit_reason(
                frame=frame,
                entry_position=entry_position,
                current_position=position,
                direction=current_direction,
            )
            if early_reason is not None:
                scheduled_early_exit_position = position + 1
                scheduled_early_exit_reason = early_reason

        if current_direction != 0:
            funding = -current_direction * current_allocation * float(funding_rate.iloc[position])
            equity *= 1.0 + funding
            bar_return += funding
            funding_pnl += funding

        if current_direction == 0 and cooldown_remaining == 0 and not exited_this_bar:
            desired_direction = int(signal.iloc[position])
            if (
                desired_direction != 0
                and _entry_allowed(signal, position, desired_direction, config)
                and _trend_filter_allows(trend_return, position, desired_direction, config)
            ):
                base_allocation = _entry_allocation(allocation_atr, position, config)
                allocation = base_allocation * risk_multiplier
                stop_loss_pct = _dynamic_pct(
                    stop_loss_atr,
                    position,
                    fallback=config.stop_loss_pct,
                    multiplier=config.stop_loss_atr_multiplier,
                    lower=config.min_stop_loss_pct,
                    upper=config.max_stop_loss_pct,
                )
                take_profit_pct = _dynamic_pct(
                    take_profit_atr,
                    position,
                    fallback=config.take_profit_pct,
                    multiplier=config.take_profit_atr_multiplier,
                    lower=config.min_take_profit_pct,
                    upper=config.max_take_profit_pct,
                )
                if allocation > 0.0 and stop_loss_pct > 0.0 and take_profit_pct > 0.0:
                    current_direction = desired_direction
                    entry_position = position
                    entry_ts = ts
                    entry_price = close_price
                    previous_price = close_price
                    entry_equity = equity
                    current_allocation = allocation
                    current_base_allocation = base_allocation
                    current_risk_multiplier_at_entry = risk_multiplier
                    current_stop_loss_pct = stop_loss_pct
                    current_take_profit_pct = take_profit_pct
                    scheduled_early_exit_position = None
                    scheduled_early_exit_reason = None
                    cost = current_allocation * cost_rate
                    equity *= 1.0 - cost
                    bar_return -= cost
                    trading_costs += cost
                    entries += 1
                    if current_direction > 0:
                        long_entries += 1
                    else:
                        short_entries += 1

        equity_values.append(equity)
        period_returns.append(bar_return)
        weights.append(current_direction * current_allocation)
        if cooldown_at_start > 0:
            cooldown_remaining -= 1

    trade_index = frame.index[start_position : end_position + 1]
    equity_curve = pd.Series(equity_values, index=trade_index, name="equity")
    period_return_series = pd.Series(period_returns, index=trade_index, name="period_return")
    weight_series = pd.Series(weights, index=trade_index, name="weight")
    metrics = _metrics(
        equity_curve=equity_curve,
        period_returns=period_return_series,
        entries=entries,
        exits=exits,
        stops=stops,
        takes=takes,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl,
        annualization_bars=config.annualization_bars,
    )
    metrics.update(
        {
            "early_main": float(early_main),
            "early_counter_opposite": float(early_counter_opposite),
            "early_counter_favorable": float(early_counter_favorable),
            "early_exits": float(early_main + early_counter_opposite + early_counter_favorable),
            "long_entries": float(long_entries),
            "short_entries": float(short_entries),
            "avg_abs_allocation": float(weight_series.abs().mean()),
            "max_abs_allocation": float(weight_series.abs().max()),
        }
    )
    return V35Run(
        equity_curve=equity_curve,
        period_returns=period_return_series,
        weights=weight_series,
        trades=pd.DataFrame(trades),
        metrics=metrics,
    )


def _v35_early_exit_reason(
    *,
    frame: pd.DataFrame,
    entry_position: int,
    current_position: int,
    direction: int,
) -> str | None:
    bars_after_entry = current_position - entry_position
    if bars_after_entry == 3:
        last_three = frame.iloc[entry_position + 1 : current_position + 1]
        if _opposite_count(last_three, direction) == 3:
            return "early_main"
    if bars_after_entry == 12:
        last_twelve = frame.iloc[entry_position + 1 : current_position + 1]
        if _opposite_count(last_twelve, direction) >= 9:
            return "early_counter_opposite"
        if _favorable_count(last_twelve, direction) >= 9:
            return "early_counter_favorable"
    return None


def _opposite_count(window: pd.DataFrame, direction: int) -> int:
    if direction > 0:
        return int(window["close"].lt(window["open"]).sum())
    return int(window["close"].gt(window["open"]).sum())


def _favorable_count(window: pd.DataFrame, direction: int) -> int:
    if direction > 0:
        return int(window["close"].gt(window["open"]).sum())
    return int(window["close"].lt(window["open"]).sum())


def apply_recovery_policy(run: V35Run, policy: RecoveryPolicy) -> dict[str, object]:
    trade_actions = run.trades.copy()
    real_period_returns = pd.Series(0.0, index=run.period_returns.index, name=policy.name)
    real_trade_rows: list[dict[str, object]] = []

    active = True
    dry_segment_equity = 1.0
    losing_streak = 0
    active_trades = 0
    skipped_trades = 0
    pause_episodes = 0
    pause_start_ts: pd.Timestamp | None = None
    first_pause_ts: pd.Timestamp | None = None
    first_resume_ts: pd.Timestamp | None = None
    pause_lengths: list[pd.Timedelta] = []
    skipped_would_be_multipliers: list[float] = []

    baseline_equity = run.equity_curve
    real_equity_so_far = 1.0

    for trade in trade_actions.to_dict("records"):
        start = int(trade["period_start"])
        end = int(trade["period_end"])
        trade_period_returns = run.period_returns.iloc[start : end + 1]
        trade_multiplier = float((1.0 + trade_period_returns).prod())
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        action = "real" if active else "dry"

        if active:
            real_period_returns.iloc[start : end + 1] = trade_period_returns.to_numpy()
            real_equity_before = real_equity_so_far
            real_equity_so_far *= trade_multiplier
            active_trades += 1
            should_pause = False
            if trade_multiplier < 1.0:
                losing_streak += 1
            else:
                losing_streak = 0
            if policy.trigger == "losing_trade":
                should_pause = trade_multiplier < 1.0
            elif policy.trigger == "losing_streak":
                should_pause = losing_streak >= policy.loss_threshold
            elif policy.trigger == "below_initial":
                should_pause = real_equity_so_far < 1.0
            if should_pause:
                active = False
                dry_segment_equity = 1.0
                losing_streak = 0
                pause_episodes += 1
                pause_start_ts = exit_ts
                if first_pause_ts is None:
                    first_pause_ts = exit_ts
            real_trade_rows.append(
                {
                    **trade,
                    "action": action,
                    "real_equity_before": real_equity_before,
                    "real_equity_after": real_equity_so_far,
                    "dry_segment_equity_after": np.nan,
                }
            )
            continue

        skipped_trades += 1
        dry_segment_equity *= trade_multiplier
        skipped_would_be_multipliers.append(trade_multiplier)
        resume = False
        if policy.resume == "dry_profitable_trade":
            resume = trade_multiplier > 1.0
        elif policy.resume == "dry_segment_breakeven":
            resume = dry_segment_equity >= 1.0
        elif policy.resume == "shadow_above_initial":
            resume = float(baseline_equity.loc[exit_ts]) >= 1.0
        if resume:
            active = True
            if pause_start_ts is not None:
                pause_lengths.append(exit_ts - pause_start_ts)
            if first_resume_ts is None:
                first_resume_ts = exit_ts
            pause_start_ts = None
            dry_segment_equity = 1.0
            losing_streak = 0
        real_trade_rows.append(
            {
                **trade,
                "action": action,
                "real_equity_before": real_equity_so_far,
                "real_equity_after": real_equity_so_far,
                "dry_segment_equity_after": dry_segment_equity if not active else 1.0,
            }
        )

    real_equity_curve = (1.0 + real_period_returns).cumprod()
    drawdown = real_equity_curve / real_equity_curve.cummax() - 1.0
    volatility = float(real_period_returns.std(ddof=0) * np.sqrt(BarsPerYear))
    sharpe = 0.0
    if real_period_returns.std(ddof=0) > 0.0:
        sharpe = float(real_period_returns.mean() / real_period_returns.std(ddof=0) * np.sqrt(BarsPerYear))
    trades = pd.DataFrame(real_trade_rows)
    real_trades = trades.loc[trades["action"].eq("real")] if not trades.empty else pd.DataFrame()
    dry_trades = trades.loc[trades["action"].eq("dry")] if not trades.empty else pd.DataFrame()
    dry_return = float(np.prod(skipped_would_be_multipliers) - 1.0) if skipped_would_be_multipliers else 0.0
    longest_pause_days = max((item.total_seconds() / 86400 for item in pause_lengths), default=0.0)

    summary = {
        "name": policy.name,
        "trigger": policy.trigger,
        "resume": policy.resume,
        "loss_threshold": int(policy.loss_threshold),
        "return_pct": pct(real_equity_curve.iloc[-1] - 1.0),
        "max_dd_pct": pct(drawdown.min()),
        "sharpe": round(sharpe, 2),
        "annualized_volatility_pct": pct(volatility),
        "active_trades": int(active_trades),
        "skipped_trades": int(skipped_trades),
        "pause_episodes": int(pause_episodes),
        "completed_pause_episodes": int(len(pause_lengths)),
        "longest_completed_pause_days": round(longest_pause_days, 2),
        "first_pause": first_pause_ts.isoformat() if first_pause_ts is not None else None,
        "first_resume": first_resume_ts.isoformat() if first_resume_ts is not None else None,
        "dry_skipped_return_pct": pct(dry_return),
        "real_stop_take_early": exit_breakdown(real_trades),
        "dry_stop_take_early": exit_breakdown(dry_trades),
    }
    return {
        "summary": summary,
        "period_returns": real_period_returns,
        "equity_curve": real_equity_curve,
        "trades": trades,
    }


def apply_fixed_skip_reset_policy(
    run: V35Run,
    *,
    loss_threshold: int,
    skip_trades: int,
) -> dict[str, object]:
    policy_name = f"loss_streak_{loss_threshold}_skip_{skip_trades}_reset_risk"
    real_period_returns = pd.Series(0.0, index=run.period_returns.index, name=policy_name)
    real_trade_rows: list[dict[str, object]] = []
    real_risk_multiplier = 1.0
    losing_streak = 0
    pause_remaining = 0
    active_trades = 0
    skipped_trades = 0
    pause_episodes = 0
    completed_pause_episodes = 0
    pause_start_ts: pd.Timestamp | None = None
    first_pause_ts: pd.Timestamp | None = None
    first_resume_ts: pd.Timestamp | None = None
    pause_lengths: list[pd.Timedelta] = []
    real_equity_so_far = 1.0

    for trade in run.trades.to_dict("records"):
        start = int(trade["period_start"])
        end = int(trade["period_end"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        shadow_period_returns = run.period_returns.iloc[start : end + 1]
        shadow_allocation = float(trade["allocation"])
        base_allocation = float(trade.get("base_allocation", shadow_allocation))

        if pause_remaining > 0:
            skipped_trades += 1
            pause_remaining -= 1
            if pause_remaining == 0:
                completed_pause_episodes += 1
                real_risk_multiplier = 1.0
                if pause_start_ts is not None:
                    pause_lengths.append(exit_ts - pause_start_ts)
                if first_resume_ts is None:
                    first_resume_ts = exit_ts
                pause_start_ts = None
            real_trade_rows.append(
                {
                    **trade,
                    "action": "dry",
                    "real_allocation": 0.0,
                    "real_risk_multiplier_at_entry": np.nan,
                    "real_equity_before": real_equity_so_far,
                    "real_equity_after": real_equity_so_far,
                }
            )
            continue

        real_equity_before = real_equity_so_far
        real_allocation = base_allocation * real_risk_multiplier
        scale = real_allocation / shadow_allocation if shadow_allocation > 0.0 else 0.0
        trade_period_returns = shadow_period_returns * scale
        real_period_returns.iloc[start : end + 1] = trade_period_returns.to_numpy()
        trade_multiplier = float((1.0 + trade_period_returns).prod())
        real_equity_so_far *= trade_multiplier
        active_trades += 1

        if trade_multiplier < 1.0:
            losing_streak += 1
        else:
            losing_streak = 0

        exit_reason = str(trade["exit_reason"])
        if exit_reason == "stop":
            real_risk_multiplier = max(0.0625, real_risk_multiplier * 0.5)
        elif exit_reason == "take":
            real_risk_multiplier = 1.0

        if losing_streak >= loss_threshold:
            pause_episodes += 1
            pause_remaining = skip_trades
            losing_streak = 0
            real_risk_multiplier = 1.0
            pause_start_ts = exit_ts
            if first_pause_ts is None:
                first_pause_ts = exit_ts
            if skip_trades == 0:
                completed_pause_episodes += 1
                pause_lengths.append(pd.Timedelta(0))
                if first_resume_ts is None:
                    first_resume_ts = exit_ts
                pause_start_ts = None

        real_trade_rows.append(
            {
                **trade,
                "action": "real",
                "real_allocation": real_allocation,
                "real_risk_multiplier_at_entry": real_allocation / base_allocation
                if base_allocation > 0.0
                else np.nan,
                "real_equity_before": real_equity_before,
                "real_equity_after": real_equity_so_far,
                "real_trade_return": trade_multiplier - 1.0,
            }
        )

    real_equity_curve = (1.0 + real_period_returns).cumprod()
    drawdown = real_equity_curve / real_equity_curve.cummax() - 1.0
    volatility = float(real_period_returns.std(ddof=0) * np.sqrt(BarsPerYear))
    sharpe = 0.0
    if real_period_returns.std(ddof=0) > 0.0:
        sharpe = float(
            real_period_returns.mean()
            / real_period_returns.std(ddof=0)
            * np.sqrt(BarsPerYear)
        )
    trades = pd.DataFrame(real_trade_rows)
    real_trades = trades.loc[trades["action"].eq("real")] if not trades.empty else pd.DataFrame()
    dry_trades = trades.loc[trades["action"].eq("dry")] if not trades.empty else pd.DataFrame()
    longest_pause_days = max((item.total_seconds() / 86400 for item in pause_lengths), default=0.0)
    summary = {
        "name": policy_name,
        "trigger": "fixed_skip_after_losing_streak",
        "resume": "fixed_skip_then_real",
        "loss_threshold": int(loss_threshold),
        "skip_trades": int(skip_trades),
        "reset_risk_multiplier_on_resume": True,
        "return_pct": pct(real_equity_curve.iloc[-1] - 1.0),
        "max_dd_pct": pct(drawdown.min()),
        "sharpe": round(sharpe, 2),
        "annualized_volatility_pct": pct(volatility),
        "active_trades": int(active_trades),
        "skipped_trades": int(skipped_trades),
        "pause_episodes": int(pause_episodes),
        "completed_pause_episodes": int(completed_pause_episodes),
        "longest_completed_pause_days": round(longest_pause_days, 2),
        "first_pause": first_pause_ts.isoformat() if first_pause_ts is not None else None,
        "first_resume": first_resume_ts.isoformat() if first_resume_ts is not None else None,
        "real_stop_take_early": exit_breakdown(real_trades),
        "dry_stop_take_early": exit_breakdown(dry_trades),
    }
    return {
        "summary": summary,
        "period_returns": real_period_returns,
        "equity_curve": real_equity_curve,
        "trades": trades,
    }


def build_scan_rows(overlays: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for overlay in overlays:
        summary = overlay["summary"]
        if summary["trigger"] != "losing_streak":
            continue
        rows.append(
            {
                "policy": summary["name"],
                "loss_threshold": summary["loss_threshold"],
                "resume": summary["resume"],
                "return_pct": summary["return_pct"],
                "max_dd_pct": summary["max_dd_pct"],
                "sharpe": summary["sharpe"],
                "active_trades": summary["active_trades"],
                "skipped_trades": summary["skipped_trades"],
                "pause_episodes": summary["pause_episodes"],
                "completed_pause_episodes": summary["completed_pause_episodes"],
                "longest_completed_pause_days": summary["longest_completed_pause_days"],
                "dry_skipped_return_pct": summary["dry_skipped_return_pct"],
            }
        )
    return rows


def build_window_rows(run: V35Run, overlays: list[dict[str, object]]) -> list[dict[str, object]]:
    end_ts = run.equity_curve.index[-1]
    windows = {
        "7d": end_ts - pd.Timedelta(days=7),
        "30d": end_ts - pd.Timedelta(days=30),
        "90d": end_ts - pd.Timedelta(days=90),
        "all": run.equity_curve.index[0],
    }
    rows: list[dict[str, object]] = []
    series_by_name = {"V35 baseline": run.equity_curve}
    for overlay in overlays:
        series_by_name[overlay["summary"]["name"]] = overlay["equity_curve"]
    for window, start_ts in windows.items():
        for name, equity in series_by_name.items():
            sliced = equity.loc[equity.index >= start_ts]
            if sliced.empty:
                continue
            normalized = sliced / float(sliced.iloc[0])
            drawdown = normalized / normalized.cummax() - 1.0
            rows.append(
                {
                    "window": window,
                    "policy": name,
                    "return_pct": pct(normalized.iloc[-1] - 1.0),
                    "max_dd_pct": pct(drawdown.min()),
                }
            )
    return rows


def compact_metrics(name: str, metrics: dict[str, float]) -> dict[str, object]:
    return {
        "name": name,
        "return_pct": pct(metrics["cumulative_return"]),
        "max_dd_pct": pct(metrics["max_drawdown"]),
        "sharpe": round(float(metrics["sharpe"]), 2),
        "entries": int(metrics["entries"]),
        "exits": int(metrics["exits"]),
        "stops": int(metrics["stops"]),
        "takes": int(metrics["takes"]),
        "early_main": int(metrics["early_main"]),
        "early_counter_opposite": int(metrics["early_counter_opposite"]),
        "early_counter_favorable": int(metrics["early_counter_favorable"]),
        "avg_abs_allocation": round(float(metrics["avg_abs_allocation"]), 3),
        "max_abs_allocation": round(float(metrics["max_abs_allocation"]), 3),
        "trading_costs": round(float(metrics["trading_costs"]), 6),
        "funding_pnl": round(float(metrics["funding_pnl"]), 6),
    }


def exit_breakdown(trades: pd.DataFrame) -> dict[str, int]:
    if trades.empty:
        return {}
    counts = trades["exit_reason"].value_counts().to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def pct(value: float) -> float:
    return round(float(value) * 100.0, 2)


if __name__ == "__main__":
    main()
