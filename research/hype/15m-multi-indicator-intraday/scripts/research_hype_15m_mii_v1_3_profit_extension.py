from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    EventTrade,
    ExitSpec,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.3"
RUN_DATE = "2026-07-02"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_profit_extension.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_profit_extension_2026-07-02.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_profit_extension_windows_2026-07-02.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_profit_extension_2026-07-02.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-profit-extension-2026-07-02.md"

BASE_EXIT = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)
BASE_EXPOSURE = 2.5
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("最近1年", pd.Timedelta(days=365)),
    ("全样本", None),
)


@dataclass(frozen=True, slots=True)
class ExitVariant:
    label: str
    family: str
    description: str
    exposure: float = BASE_EXPOSURE
    filter_spec: Any = None
    tp_atr_mult: float = 1.25
    sl_atr_mult: float = 5.0
    max_hold_bars: int = 24
    split_first_tp_mult: float | None = None
    split_first_weight: float = 0.5
    split_second_tp_mult: float | None = None
    dynamic_rule: str | None = None


def base_filter() -> Any:
    return v12.BASE_CONFIG.filter


def variants() -> list[ExitVariant]:
    base = base_filter()
    rvol125 = replace(base, min_rvol96=1.25)
    rvol150 = replace(base, min_rvol96=1.50)
    return [
        ExitVariant(
            label="v13_baseline_tp1p25_sl5_x2p5",
            family="baseline",
            description="V1.3 baseline：TP=1.25*ATR96%，SL=5*ATR96%，2.5x",
            filter_spec=base,
        ),
        ExitVariant(
            label="fixed_tp1p5_sl5_x2p5",
            family="higher_tp",
            description="单纯提高 TP 到 1.5*ATR96%",
            filter_spec=base,
            tp_atr_mult=1.5,
        ),
        ExitVariant(
            label="fixed_tp1p75_sl5_x2p5",
            family="higher_tp",
            description="单纯提高 TP 到 1.75*ATR96%",
            filter_spec=base,
            tp_atr_mult=1.75,
        ),
        ExitVariant(
            label="fixed_tp2_sl5_x2p5",
            family="higher_tp",
            description="单纯提高 TP 到 2.0*ATR96%",
            filter_spec=base,
            tp_atr_mult=2.0,
        ),
        ExitVariant(
            label="rvol125_tp1p75_sl5_x2p5",
            family="higher_tp_stronger_filter",
            description="RVOL96>=1.25 后提高 TP 到 1.75*ATR96%",
            filter_spec=rvol125,
            tp_atr_mult=1.75,
        ),
        ExitVariant(
            label="rvol125_tp2_sl5_x2p5",
            family="higher_tp_stronger_filter",
            description="RVOL96>=1.25 后提高 TP 到 2.0*ATR96%",
            filter_spec=rvol125,
            tp_atr_mult=2.0,
        ),
        ExitVariant(
            label="rvol150_tp2_sl5_x2p5",
            family="higher_tp_stronger_filter",
            description="RVOL96>=1.50 后提高 TP 到 2.0*ATR96%",
            filter_spec=rvol150,
            tp_atr_mult=2.0,
        ),
        ExitVariant(
            label="split_50_tp1p25_tp2_sl5_x2p5",
            family="split_take_profit",
            description="50% 在 1.25*ATR96% 止盈，50% 在 2.0*ATR96% 止盈或 timeout",
            filter_spec=base,
            split_first_tp_mult=1.25,
            split_second_tp_mult=2.0,
        ),
        ExitVariant(
            label="split_50_tp1p25_tp2p5_sl5_x2p5",
            family="split_take_profit",
            description="50% 在 1.25*ATR96% 止盈，50% 在 2.5*ATR96% 止盈或 timeout",
            filter_spec=base,
            split_first_tp_mult=1.25,
            split_second_tp_mult=2.5,
        ),
        ExitVariant(
            label="dynamic_rvol125_tp2_else1p25_x2p5",
            family="dynamic_tp",
            description="RVOL96>=1.25 时 TP=2.0*ATR96%，否则 TP=1.25*ATR96%",
            filter_spec=base,
            dynamic_rule="rvol125_tp2_else1p25",
        ),
        ExitVariant(
            label="dynamic_rvol150_tp2p5_else1p25_x2p5",
            family="dynamic_tp",
            description="RVOL96>=1.50 时 TP=2.5*ATR96%，否则 TP=1.25*ATR96%",
            filter_spec=base,
            dynamic_rule="rvol150_tp2p5_else1p25",
        ),
        ExitVariant(
            label="dynamic_atr_mid_rvol125_tp2_else1p25_x2p5",
            family="dynamic_tp",
            description="RVOL96>=1.25 且 ATR96%<=1.8% 时 TP=2.0*ATR96%，否则 TP=1.25*ATR96%",
            filter_spec=base,
            dynamic_rule="atr_mid_rvol125_tp2_else1p25",
        ),
        ExitVariant(
            label="v13_baseline_tp1p25_sl5_x2p75",
            family="sizing",
            description="策略不变，只把固定暴露从 2.5x 提到 2.75x",
            filter_spec=base,
            exposure=2.75,
        ),
    ]


def build_context() -> tuple[v12.evolution.EvalContext, dict[str, Any], dict[str, Any]]:
    context, metadata, quality = v12.build_context()
    v1.engine.simulate_trades = v1.simulate_trades_live
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live
    return context, metadata, quality


def finite(value: float, default: float) -> float:
    return float(value) if np.isfinite(value) else default


def target_mult_for_variant(
    variant: ExitVariant,
    *,
    atr_pct96: float,
    rvol96: float,
) -> float:
    if variant.dynamic_rule == "rvol125_tp2_else1p25":
        return 2.0 if rvol96 >= 1.25 else 1.25
    if variant.dynamic_rule == "rvol150_tp2p5_else1p25":
        return 2.5 if rvol96 >= 1.50 else 1.25
    if variant.dynamic_rule == "atr_mid_rvol125_tp2_else1p25":
        return 2.0 if rvol96 >= 1.25 and atr_pct96 <= 0.018 else 1.25
    return variant.tp_atr_mult


def adverse_return(direction: int, entry_price: float, high: float, low: float) -> float:
    if direction == 1:
        return low / entry_price - 1.0
    return entry_price / high - 1.0


def favorable_return(direction: int, entry_price: float, high: float, low: float) -> float:
    if direction == 1:
        return high / entry_price - 1.0
    return entry_price / low - 1.0


def gross_return(direction: int, entry_price: float, exit_price: float) -> float:
    return direction * (exit_price / entry_price - 1.0)


def simulate_single_exit(
    *,
    market: Any,
    state: Any,
    signal_i: int,
    entry_i: int,
    direction: int,
    variant: ExitVariant,
    atr_pct96: float,
    rvol96: float,
) -> tuple[int, float, float, float, str, int]:
    tp_mult = target_mult_for_variant(variant, atr_pct96=atr_pct96, rvol96=rvol96)
    take_profit_pct = atr_pct96 * tp_mult
    stop_pct = atr_pct96 * variant.sl_atr_mult
    forced_exit_i = min(entry_i + variant.max_hold_bars, len(market.open) - 1)
    entry_price = float(market.open[entry_i])
    stop_price = entry_price * (1.0 - direction * stop_pct)
    take_profit_price = entry_price * (1.0 + direction * take_profit_pct)
    exit_i = forced_exit_i
    exit_price = float(market.open[forced_exit_i])
    exit_reason = "max_hold"
    min_path = 0.0
    max_path = 0.0

    for i in range(entry_i, forced_exit_i):
        open_price = float(market.open[i])
        high = float(market.high[i])
        low = float(market.low[i])
        min_path = min(min_path, adverse_return(direction, entry_price, high, low))
        max_path = max(max_path, favorable_return(direction, entry_price, high, low))
        if direction == 1:
            if open_price <= stop_price:
                return i, open_price, min_path, max_path, "stop_gap", 0
            if open_price >= take_profit_price:
                return i, take_profit_price, min_path, max_path, "take_profit_gap", 0
            if low <= stop_price:
                return i, stop_price, min_path, max_path, "stop_loss", 0
            if high >= take_profit_price:
                return i, take_profit_price, min_path, max_path, "take_profit", 0
        else:
            if open_price >= stop_price:
                return i, open_price, min_path, max_path, "stop_gap", 0
            if open_price <= take_profit_price:
                return i, take_profit_price, min_path, max_path, "take_profit_gap", 0
            if high >= stop_price:
                return i, stop_price, min_path, max_path, "stop_loss", 0
            if low <= take_profit_price:
                return i, take_profit_price, min_path, max_path, "take_profit", 0

    timeout_return = gross_return(direction, entry_price, exit_price)
    min_path = min(min_path, timeout_return)
    max_path = max(max_path, timeout_return)
    return exit_i, exit_price, min_path, max_path, exit_reason, 0


def simulate_split_exit(
    *,
    market: Any,
    signal_i: int,
    entry_i: int,
    direction: int,
    variant: ExitVariant,
    atr_pct96: float,
) -> tuple[int, float, float, float, str, float]:
    if variant.split_first_tp_mult is None or variant.split_second_tp_mult is None:
        raise ValueError("split variant missing target multipliers")

    first_weight = variant.split_first_weight
    second_weight = 1.0 - first_weight
    entry_price = float(market.open[entry_i])
    first_tp_price = entry_price * (1.0 + direction * atr_pct96 * variant.split_first_tp_mult)
    second_tp_price = entry_price * (1.0 + direction * atr_pct96 * variant.split_second_tp_mult)
    stop_price = entry_price * (1.0 - direction * atr_pct96 * variant.sl_atr_mult)
    forced_exit_i = min(entry_i + variant.max_hold_bars, len(market.open) - 1)
    first_filled = False
    first_return = 0.0
    min_path = 0.0
    max_path = 0.0
    exit_i = forced_exit_i
    second_exit_price = float(market.open[forced_exit_i])
    exit_reason = "max_hold"

    for i in range(entry_i, forced_exit_i):
        open_price = float(market.open[i])
        high = float(market.high[i])
        low = float(market.low[i])
        adverse = adverse_return(direction, entry_price, high, low)
        favorable = favorable_return(direction, entry_price, high, low)
        if first_filled:
            min_path = min(min_path, first_weight * first_return + second_weight * adverse)
            max_path = max(max_path, first_weight * first_return + second_weight * favorable)
        else:
            min_path = min(min_path, adverse)
            max_path = max(max_path, favorable)

        if direction == 1:
            stop_hit_open = open_price <= stop_price
            first_hit_open = open_price >= first_tp_price
            second_hit_open = open_price >= second_tp_price
            stop_hit = low <= stop_price
            first_hit = high >= first_tp_price
            second_hit = high >= second_tp_price
        else:
            stop_hit_open = open_price >= stop_price
            first_hit_open = open_price <= first_tp_price
            second_hit_open = open_price <= second_tp_price
            stop_hit = high >= stop_price
            first_hit = low <= first_tp_price
            second_hit = low <= second_tp_price

        if stop_hit_open:
            exit_i = i
            second_exit_price = open_price
            exit_reason = "partial_then_stop_gap" if first_filled else "stop_gap"
            break
        if second_hit_open:
            if not first_filled:
                first_filled = True
                first_return = gross_return(direction, entry_price, first_tp_price)
            exit_i = i
            second_exit_price = second_tp_price
            exit_reason = "split_take_profit_gap"
            break
        if first_hit_open and not first_filled:
            first_filled = True
            first_return = gross_return(direction, entry_price, first_tp_price)

        if stop_hit:
            exit_i = i
            second_exit_price = stop_price
            exit_reason = "partial_then_stop_loss" if first_filled else "stop_loss"
            break
        if second_hit:
            if not first_filled:
                first_filled = True
                first_return = gross_return(direction, entry_price, first_tp_price)
            exit_i = i
            second_exit_price = second_tp_price
            exit_reason = "split_take_profit"
            break
        if first_hit and not first_filled:
            first_filled = True
            first_return = gross_return(direction, entry_price, first_tp_price)

    second_return = gross_return(direction, entry_price, second_exit_price)
    if not first_filled:
        raw_return = second_return
        partial_realized_pct = 0.0
    else:
        raw_return = first_weight * first_return + second_weight * second_return
        partial_realized_pct = first_weight * first_return
    if exit_reason == "max_hold":
        if first_filled:
            min_path = min(min_path, raw_return)
            max_path = max(max_path, raw_return)
        else:
            min_path = min(min_path, second_return)
            max_path = max(max_path, second_return)
    return exit_i, raw_return, min_path, max_path, exit_reason, partial_realized_pct


def make_event_trade(
    *,
    market: Any,
    state: Any,
    signal_i: int,
    entry_i: int,
    exit_i: int,
    direction: int,
    entry_price: float,
    exit_price: float,
    raw_return: float,
    min_path: float,
    max_path: float,
    exit_reason: str,
    partial_realized_pct: float,
) -> EventTrade:
    return EventTrade(
        signal_i=signal_i,
        entry_i=entry_i,
        exit_i=int(exit_i),
        direction=direction,
        entry_ts=pd.Timestamp(market.ts[entry_i]),
        exit_ts=pd.Timestamp(market.ts[exit_i]),
        entry_price=entry_price,
        exit_price=float(exit_price),
        raw_return=float(raw_return),
        min_path_return=float(min_path),
        max_path_return=float(max_path),
        bars_held=int(max(exit_i - entry_i, 0)),
        exit_reason=exit_reason,
        signal_name=state.spec.name,
        signal_kind=state.spec.kind,
        adx14=finite(market.adx14[signal_i], 0.0),
        rvol96=finite(market.rvol96[signal_i], 0.0),
        h1_dir_spread=finite(market.h1_spread[signal_i], 0.0) * direction,
        h4_dir_spread=finite(market.h4_spread[signal_i], 0.0) * direction,
        dir_ret16=finite(market.ret16[signal_i], 0.0) * direction,
        dir_ret48=finite(market.ret48[signal_i], 0.0) * direction,
        dir_ret96=finite(market.ret96[signal_i], 0.0) * direction,
        dir_macd=finite(market.macd_hist[signal_i], 0.0) * direction,
        dir_rsi14=(
            finite(market.rsi14[signal_i], 50.0)
            if direction == 1
            else 100.0 - finite(market.rsi14[signal_i], 50.0)
        ),
        atr_pct96=finite(market.atr_pct96[signal_i], 0.0),
        atr_ratio96_672=finite(market.atr_ratio96_672[signal_i], 99.0),
        previous_signal_age=finite(state.previous_signal_age[signal_i], 0.0),
        churn192=finite(state.churn192[signal_i], 999.0),
    )


def simulate_variant_trades(
    context: v12.evolution.EvalContext,
    variant: ExitVariant,
    entry_delay_bars: int,
) -> list[EventTrade]:
    market = context.market
    state = signal_state(context.features, v12.BASE_CONFIG.signal)
    atr_pct96 = context.features["atr_pct96"].to_numpy("float64")
    trades: list[EventTrade] = []
    n = len(market.open)
    for signal_idx, direction_value in zip(state.signal_i, state.directions, strict=False):
        signal_i = int(signal_idx)
        entry_i = signal_i + entry_delay_bars
        if entry_i >= n - 1:
            continue
        direction = int(direction_value)
        entry_price = float(market.open[entry_i])
        atr_value = float(atr_pct96[signal_i])
        rvol_value = finite(market.rvol96[signal_i], 0.0)
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue
        if variant.family == "split_take_profit":
            exit_i, raw_return, min_path, max_path, exit_reason, partial_realized_pct = simulate_split_exit(
                market=market,
                signal_i=signal_i,
                entry_i=entry_i,
                direction=direction,
                variant=variant,
                atr_pct96=atr_value,
            )
            exit_price = float(market.open[exit_i])
        else:
            exit_i, exit_price, min_path, max_path, exit_reason, partial_realized_pct = simulate_single_exit(
                market=market,
                state=state,
                signal_i=signal_i,
                entry_i=entry_i,
                direction=direction,
                variant=variant,
                atr_pct96=atr_value,
                rvol96=rvol_value,
            )
            raw_return = gross_return(direction, entry_price, exit_price)
        trades.append(
            make_event_trade(
                market=market,
                state=state,
                signal_i=signal_i,
                entry_i=entry_i,
                exit_i=exit_i,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                raw_return=raw_return,
                min_path=min_path,
                max_path=max_path,
                exit_reason=exit_reason,
                partial_realized_pct=partial_realized_pct,
            )
        )
    return trades


def window_bounds(
    context: v12.evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = context.end_ts
    start_ts = context.start_ts if duration is None else max(context.start_ts, end_ts - duration)
    return start_ts, end_ts


def window_trades(
    trades: list[EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[EventTrade]:
    return [trade for trade in trades if start_ts <= trade.entry_ts < end_ts]


def selected_trades(
    trades: list[EventTrade],
    variant: ExitVariant,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[EventTrade]:
    return v1.selected_trades_live(window_trades(trades, start_ts, end_ts), variant.filter_spec)


def equity_metrics(
    trades: list[EventTrade],
    variant: ExitVariant,
    period_days: float,
) -> dict[str, Any]:
    if not trades:
        return {
            "annual_return_pct": 0.0,
            "annual_equity_multiple": 1.0,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "trades": 0,
            "trades_per_day": 0.0,
            "profit_factor": 0.0,
            "trade_sharpe": 0.0,
            "trade_sortino": 0.0,
            "calmar": 0.0,
            "avg_trade_pct": 0.0,
            "median_trade_pct": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "avg_bars_held": 0.0,
        }
    returns = np.array(
        [variant.exposure * (trade.raw_return - ROUND_TRIP_COST) for trade in trades],
        dtype="float64",
    )
    min_mark_returns = np.array(
        [variant.exposure * (trade.min_path_return - ROUND_TRIP_COST) for trade in trades],
        dtype="float64",
    )
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for net_return, min_mark_return in zip(returns, min_mark_returns, strict=False):
        mark_equity = equity * max(0.0, 1.0 + float(min_mark_return))
        if peak > 0:
            max_drawdown = min(max_drawdown, mark_equity / peak - 1.0)
        equity *= max(0.0, 1.0 + float(net_return))
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
    total_return = float(equity - 1.0)
    annual_return = float((1.0 + total_return) ** (365.25 / max(period_days, 1.0)) - 1.0)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    trades_per_year = len(returns) / max(period_days, 1.0) * 365.25
    sharpe = (
        float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(trades_per_year))
        if len(returns) >= 2 and np.std(returns, ddof=1) > 0
        else 0.0
    )
    sortino = (
        float(np.mean(returns) / np.std(losses, ddof=1) * np.sqrt(trades_per_year))
        if len(losses) >= 2 and np.std(losses, ddof=1) > 0
        else 0.0
    )
    return {
        "annual_return_pct": annual_return * 100.0,
        "annual_equity_multiple": 1.0 + annual_return,
        "total_return_pct": total_return * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "win_rate_pct": float(len(wins) / len(returns) * 100.0),
        "trades": int(len(returns)),
        "trades_per_day": float(len(returns) / max(period_days, 1.0)),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "trade_sharpe": sharpe,
        "trade_sortino": sortino,
        "calmar": float(annual_return / abs(max_drawdown)) if max_drawdown < 0 else 0.0,
        "avg_trade_pct": float(np.mean(returns) * 100.0),
        "median_trade_pct": float(np.median(returns) * 100.0),
        "best_trade_pct": float(np.max(returns) * 100.0),
        "worst_trade_pct": float(np.min(returns) * 100.0),
        "avg_bars_held": float(np.mean([trade.bars_held for trade in trades])),
    }


def exit_counts(trades: list[EventTrade]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.exit_reason] = counts.get(trade.exit_reason, 0) + 1
    return counts


def evaluate_row(
    *,
    context: v12.evolution.EvalContext,
    trades: list[EventTrade],
    variant: ExitVariant,
    entry_timing: str,
    entry_delay_bars: int,
    window_name: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    picked = selected_trades(trades, variant, start_ts, end_ts)
    period_days = max((end_ts - start_ts).total_seconds() / 86_400.0, 1.0)
    counts = exit_counts(picked)
    return {
        "version": VERSION,
        "variant": variant.label,
        "family": variant.family,
        "description": variant.description,
        "entry_timing": entry_timing,
        "entry_delay_bars": entry_delay_bars,
        "window": window_name,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": period_days,
        "exposure": variant.exposure,
        "tp_atr_mult": variant.tp_atr_mult,
        "sl_atr_mult": variant.sl_atr_mult,
        "split_first_tp_mult": variant.split_first_tp_mult,
        "split_second_tp_mult": variant.split_second_tp_mult,
        "dynamic_rule": variant.dynamic_rule,
        "min_rvol96": variant.filter_spec.min_rvol96,
        "min_atr_pct96": variant.filter_spec.min_atr_pct96,
        "max_atr_pct96": variant.filter_spec.max_atr_pct96,
        **equity_metrics(picked, variant, period_days),
        "take_profit_exits": counts.get("take_profit", 0)
        + counts.get("take_profit_gap", 0)
        + counts.get("split_take_profit", 0)
        + counts.get("split_take_profit_gap", 0),
        "stop_exits": counts.get("stop_loss", 0)
        + counts.get("stop_gap", 0)
        + counts.get("partial_then_stop_loss", 0)
        + counts.get("partial_then_stop_gap", 0),
        "timeout_exits": counts.get("max_hold", 0),
    }


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    context, metadata, quality = build_context()
    summary_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for variant in variants():
        for entry_delay_bars, entry_timing in ENTRY_DELAYS:
            trades = simulate_variant_trades(context, variant, entry_delay_bars)
            for window_name, duration in WINDOWS:
                start_ts, end_ts = window_bounds(context, duration)
                row = evaluate_row(
                    context=context,
                    trades=trades,
                    variant=variant,
                    entry_timing=entry_timing,
                    entry_delay_bars=entry_delay_bars,
                    window_name=window_name,
                    start_ts=start_ts,
                    end_ts=end_ts,
                )
                window_rows.append(row)
                if window_name == "全样本":
                    summary_rows.append(row)
            print(f"evaluated {variant.label} {entry_timing}", flush=True)
    summary = pd.DataFrame(summary_rows)
    windows = pd.DataFrame(window_rows)
    baseline = summary.loc[
        summary["variant"].eq("v13_baseline_tp1p25_sl5_x2p5")
        & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    score_rows = []
    for label in summary["variant"].unique():
        k1 = summary.loc[summary["variant"].eq(label) & summary["entry_timing"].eq("K+1")].iloc[0]
        k2 = summary.loc[summary["variant"].eq(label) & summary["entry_timing"].eq("K+2")].iloc[0]
        score = (
            np.log1p(max(float(k1["annual_return_pct"]), -90.0) / 100.0) * 0.30
            + np.log1p(max(float(k2["annual_return_pct"]), -90.0) / 100.0) * 0.25
            + ((min(float(k1["max_drawdown_pct"]), float(k2["max_drawdown_pct"])) + 60.0) / 60.0)
            * 0.20
            + ((min(float(k1["win_rate_pct"]), float(k2["win_rate_pct"])) - 65.0) / 30.0)
            * 0.15
            + min(float(k1["avg_trade_pct"]) / 2.0, 1.0) * 0.10
        )
        score_rows.append(
            {
                "variant": label,
                "score": score,
                "beats_baseline_k1_return": float(k1["annual_return_pct"])
                > float(baseline["annual_return_pct"]),
                "beats_baseline_k1_avg_trade": float(k1["avg_trade_pct"])
                > float(baseline["avg_trade_pct"]),
            }
        )
    score_df = pd.DataFrame(score_rows)
    summary = summary.merge(score_df, on="variant", how="left")
    summary = summary.sort_values(
        ["entry_timing", "score", "annual_return_pct"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    return summary, windows, metadata, quality


def pct(value: float) -> str:
    return f"{value:.2f}%"


def full_sample_table(summary: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = summary.loc[summary["entry_timing"].eq(entry_timing)].copy()
    lines = [
        f"### {entry_timing} 全样本",
        "",
        "| 方案 | 交易数 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | 平均单笔 | 最差单笔 | 止盈/止损/超时 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{int(row['trades'])}` | "
            f"`{pct(row['total_return_pct'])}` | `{pct(row['annual_return_pct'])}` | "
            f"`{pct(row['max_drawdown_pct'])}` | `{pct(row['win_rate_pct'])}` | "
            f"`{row['profit_factor']:.3f}` | `{pct(row['avg_trade_pct'])}` | "
            f"`{pct(row['worst_trade_pct'])}` | "
            f"`{int(row['take_profit_exits'])}/{int(row['stop_exits'])}/{int(row['timeout_exits'])}` |"
        )
    return lines


def window_table(windows: pd.DataFrame, variants_to_show: list[str], entry_timing: str) -> list[str]:
    subset = windows.loc[
        windows["entry_timing"].eq(entry_timing)
        & windows["variant"].isin(variants_to_show)
        & windows["window"].isin(["最近1月", "最近3月", "最近6月", "全样本"])
    ].copy()
    order = {variant: index for index, variant in enumerate(variants_to_show)}
    window_order = {"最近1月": 0, "最近3月": 1, "最近6月": 2, "全样本": 3}
    subset["variant_order"] = subset["variant"].map(order)
    subset["window_order"] = subset["window"].map(window_order)
    subset = subset.sort_values(["variant_order", "window_order"])
    lines = [
        f"### {entry_timing} 重点窗口",
        "",
        "| 方案 | 窗口 | 交易数 | 总收益 | 年化 | 最大回撤 | 胜率 | 平均单笔 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{row['window']}` | `{int(row['trades'])}` | "
            f"`{pct(row['total_return_pct'])}` | `{pct(row['annual_return_pct'])}` | "
            f"`{pct(row['max_drawdown_pct'])}` | `{pct(row['win_rate_pct'])}` | "
            f"`{pct(row['avg_trade_pct'])}` |"
        )
    return lines


def render_markdown(
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    k1 = summary.loc[summary["entry_timing"].eq("K+1")].copy()
    k2 = summary.loc[summary["entry_timing"].eq("K+2")].copy()
    baseline_k1 = k1.loc[k1["variant"].eq("v13_baseline_tp1p25_sl5_x2p5")].iloc[0]
    best_k1_return = k1.sort_values("annual_return_pct", ascending=False).iloc[0]
    best_k1_avg = k1.sort_values("avg_trade_pct", ascending=False).iloc[0]
    best_score = k1.sort_values("score", ascending=False).iloc[0]
    sizing_k1 = k1.loc[k1["variant"].eq("v13_baseline_tp1p25_sl5_x2p75")].iloc[0]
    sizing_k2 = k2.loc[k2["variant"].eq("v13_baseline_tp1p25_sl5_x2p75")].iloc[0]
    rvol125_k1 = k1.loc[k1["variant"].eq("rvol125_tp1p75_sl5_x2p5")].iloc[0]
    rvol125_k2 = k2.loc[k2["variant"].eq("rvol125_tp1p75_sl5_x2p5")].iloc[0]
    dynamic_k1 = k1.loc[k1["variant"].eq("dynamic_rvol150_tp2p5_else1p25_x2p5")].iloc[0]
    dynamic_k2 = k2.loc[k2["variant"].eq("dynamic_rvol150_tp2p5_else1p25_x2p5")].iloc[0]
    rvol125_recent_k1 = windows.loc[
        windows["variant"].eq("rvol125_tp1p75_sl5_x2p5")
        & windows["entry_timing"].eq("K+1")
        & windows["window"].eq("最近3月")
    ].iloc[0]
    dynamic_recent_k1 = windows.loc[
        windows["variant"].eq("dynamic_rvol150_tp2p5_else1p25_x2p5")
        & windows["entry_timing"].eq("K+1")
        & windows["window"].eq("最近3月")
    ].iloc[0]
    variants_to_show = list(
        dict.fromkeys(
            [
                "v13_baseline_tp1p25_sl5_x2p5",
                str(best_k1_return["variant"]),
                str(best_k1_avg["variant"]),
                str(best_score["variant"]),
                "v13_baseline_tp1p25_sl5_x2p75",
            ]
        )
    )
    lines = [
        f"# HYPE-15M-MII V1.3 多赚一点方案回测 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        "本次测试保持 `V1.3` 的 RSI/MACD/ATR/RVOL 入场过滤不变，比较四类“多赚一点”方案：提高 TP、提高 TP 并加强 RVOL 过滤、分层止盈、动态 TP，以及单纯提高 sizing 到 `2.75x`。",
        "",
        (
            f"- 原 `V1.3` baseline K+1：总收益 `{baseline_k1['total_return_pct']:.2f}%`、"
            f"年化 `{baseline_k1['annual_return_pct']:.2f}%`、回撤 `{baseline_k1['max_drawdown_pct']:.2f}%`、"
            f"胜率 `{baseline_k1['win_rate_pct']:.2f}%`、平均单笔 `{baseline_k1['avg_trade_pct']:.2f}%`。"
        ),
        (
            f"- K+1 年化最高：`{best_k1_return['variant']}`，年化 `{best_k1_return['annual_return_pct']:.2f}%`、"
            f"回撤 `{best_k1_return['max_drawdown_pct']:.2f}%`、胜率 `{best_k1_return['win_rate_pct']:.2f}%`、"
            f"平均单笔 `{best_k1_return['avg_trade_pct']:.2f}%`。"
        ),
        (
            f"- 平均单笔最高：`{best_k1_avg['variant']}`，平均单笔 `{best_k1_avg['avg_trade_pct']:.2f}%`、"
            f"年化 `{best_k1_avg['annual_return_pct']:.2f}%`、回撤 `{best_k1_avg['max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- 综合排序第一：`{best_score['variant']}`，但该排序仍是样本内诊断，不是 promotion。"
        ),
        (
            f"- 单纯把 sizing 从 `2.5x` 提到 `2.75x`，K+1 总收益从 "
            f"`{baseline_k1['total_return_pct']:.2f}%` 提到 `{sizing_k1['total_return_pct']:.2f}%`，"
            f"回撤从 `{baseline_k1['max_drawdown_pct']:.2f}%` 扩到 `{sizing_k1['max_drawdown_pct']:.2f}%`；"
            f"K+2 回撤从 `-41.89%` 扩到 `{sizing_k2['max_drawdown_pct']:.2f}%`。这是风险放大，不是 edge 改善。"
        ),
        (
            f"- `rvol125_tp1p75_sl5_x2p5` 是 K+2 形状最值得注意的出场改法：K+2 总收益 "
            f"`{rvol125_k2['total_return_pct']:.2f}%`、回撤 `{rvol125_k2['max_drawdown_pct']:.2f}%`、"
            f"平均单笔 `{rvol125_k2['avg_trade_pct']:.2f}%`；但它 K+1 最近 3 月总收益 "
            f"`{rvol125_recent_k1['total_return_pct']:.2f}%`，近期明显弱于 baseline。"
        ),
        (
            f"- `dynamic_rvol150_tp2p5_else1p25_x2p5` 全样本 K+1/K+2 收益都更高"
            f"（K+1 `{dynamic_k1['total_return_pct']:.2f}%`，K+2 `{dynamic_k2['total_return_pct']:.2f}%`），"
            f"但 K+1 最近 3 月只有 `{dynamic_recent_k1['total_return_pct']:.2f}%`，且全样本回撤更深。"
        ),
        "",
        "初步判断：如果目标只是“单笔多赚点”，提高 TP 或分层止盈确实能抬高平均单笔；但目前没有一个方案同时满足全样本更高、K+2 更稳、近期窗口不退化。最保守的实用结论仍是保留 `V1.3 baseline`，把 `rvol125_tp1p75` 和 `dynamic_rvol150` 作为后续 OOS/实盘模拟观察，而不是直接替换。",
        "",
        "## 全样本对比",
        "",
        *full_sample_table(summary, "K+1"),
        "",
        *full_sample_table(summary, "K+2"),
        "",
        "## 重点窗口",
        "",
        *window_table(windows, variants_to_show, "K+1"),
        "",
        *window_table(windows, variants_to_show, "K+2"),
        "",
        "## 方案说明",
        "",
        "- `higher_tp`：只把 `TP` 从 `1.25*ATR96%` 提高到 `1.5/1.75/2.0*ATR96%`，`SL=5*ATR96%`、`hold=24` 不变。",
        "- `higher_tp_stronger_filter`：先要求 `RVOL96>=1.25` 或 `1.50`，再提高 TP。",
        "- `split_take_profit`：50% 在 `1.25*ATR96%` 先止盈，剩余 50% 等 `2.0/2.5*ATR96%`、止损或 timeout。",
        "- `dynamic_tp`：只在 RVOL 或 ATR/RVOL 条件更强时放大 TP，否则保持 baseline TP。",
        "- `sizing`：交易和出场不变，把固定暴露从 `2.5x` 提到 `2.75x`。",
        "",
        "## 状态",
        "",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        f"- 成本：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        "- 这些方案均为同样本出场/sizing 诊断；没有补齐资金费、盘口级滑点、runner 对拍、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch，不改变 `NO-GO`。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 全样本 CSV：`{SUMMARY_CSV_PATH}`",
        f"- 窗口 CSV：`{WINDOW_CSV_PATH}`",
        f"- JSON：`{JSON_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [json_safe(child) for child in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    summary, windows, metadata, quality = evaluate()
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, windows, quality), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "profit_extension_diagnostic_not_promoted",
                    "metadata": metadata,
                    "data_quality": quality,
                    "base_exit": asdict(BASE_EXIT),
                    "base_exposure": BASE_EXPOSURE,
                    "costs": {
                        "commission_per_fill": COMMISSION_PER_SIDE,
                        "slippage_per_fill": SLIPPAGE_PER_SIDE,
                        "round_trip": ROUND_TRIP_COST,
                    },
                    "summary": summary.to_dict(orient="records"),
                    "outputs": {
                        "markdown": str(MARKDOWN_PATH),
                        "summary_csv": str(SUMMARY_CSV_PATH),
                        "window_csv": str(WINDOW_CSV_PATH),
                    },
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(
        summary.loc[summary["entry_timing"].eq("K+1")][
            [
                "variant",
                "family",
                "trades",
                "total_return_pct",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "profit_factor",
                "avg_trade_pct",
                "worst_trade_pct",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
