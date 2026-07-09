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
import research_hype_15m_mii_v1_3_signal_drought_diagnostic as drought  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.4"
RUN_DATE = "2026-07-09"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_4_dynamic_stop.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
FULL_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_dynamic_stop_full_2026-07-09.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_dynamic_stop_windows_2026-07-09.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_dynamic_stop_rolling_2026-07-09.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_dynamic_stop_recent_2026-07-09.csv"
EXIT_COUNTS_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_dynamic_stop_exit_counts_2026-07-09.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_dynamic_stop_2026-07-09.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-4-dynamic-stop-2026-07-09.md"

V14_EXPOSURE = 2.5
V14_MIN_RVOL96 = 0.85
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
TP_ATR_MULT = 1.25
BASE_SL_ATR_MULT = 5.0
MAX_HOLD_BARS = 24
ATR_WINDOW = 96
FIXED_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("全样本", None),
    ("最近90d", pd.Timedelta(days=90)),
    ("最近30d", pd.Timedelta(days=30)),
)
RECENT_WINDOWS: tuple[tuple[str, pd.Timedelta], ...] = (
    ("最近24h", pd.Timedelta(hours=24)),
    ("最近72h", pd.Timedelta(hours=72)),
    ("最近7d", pd.Timedelta(days=7)),
    ("最近30d", pd.Timedelta(days=30)),
    ("最近90d", pd.Timedelta(days=90)),
)


@dataclass(frozen=True, slots=True)
class DynamicStopSpec:
    label: str
    family: str
    description: str
    initial_sl_atr_mult: float = BASE_SL_ATR_MULT
    tp_atr_mult: float = TP_ATR_MULT
    break_even_trigger_atr: float | None = None
    break_even_stop_atr: float | None = None
    step_rules: tuple[tuple[float, float], ...] = ()
    trail_activation_atr: float | None = None
    trail_distance_atr: float | None = None
    max_hold_bars: int = MAX_HOLD_BARS

    @property
    def exit_spec(self) -> v12.ExitSpec:
        stop_pct = self.initial_sl_atr_mult * 0.01
        take_profit_pct = self.tp_atr_mult * 0.01
        return v12.ExitSpec(
            kind="fixed",
            take_profit_pct=take_profit_pct,
            stop_pct=stop_pct,
            max_hold_bars=self.max_hold_bars,
        )


def v14_filter() -> Any:
    return replace(v12.BASE_CONFIG.filter, min_rvol96=V14_MIN_RVOL96)


def specs() -> list[DynamicStopSpec]:
    return [
        DynamicStopSpec(
            label="baseline_tp1p25_sl5",
            family="baseline",
            description="V1.4 baseline：TP=1.25*ATR96，SL=5.0*ATR96",
        ),
        DynamicStopSpec(
            label="fixed_tp1p25_sl3",
            family="fixed_sl_reference",
            description="固定窄止损参照：TP=1.25*ATR96，SL=3.0*ATR96",
            initial_sl_atr_mult=3.0,
        ),
        DynamicStopSpec(
            label="be_trig0p75_stop_m2p5",
            family="break_even_like",
            description="浮盈 >=0.75*ATR 后，下一根 K 起把 SL 上移到 -2.5*ATR",
            break_even_trigger_atr=0.75,
            break_even_stop_atr=-2.5,
        ),
        DynamicStopSpec(
            label="be_trig0p75_stop_m1p5",
            family="break_even_like",
            description="浮盈 >=0.75*ATR 后，下一根 K 起把 SL 上移到 -1.5*ATR",
            break_even_trigger_atr=0.75,
            break_even_stop_atr=-1.5,
        ),
        DynamicStopSpec(
            label="be_trig1_stop_0",
            family="break_even_like",
            description="浮盈 >=1.0*ATR 后，下一根 K 起把 SL 上移到入场价",
            break_even_trigger_atr=1.0,
            break_even_stop_atr=0.0,
        ),
        DynamicStopSpec(
            label="step_0p5_m3_1p0_m1",
            family="step_stop",
            description="分档：浮盈 0.5*ATR 后 SL=-3*ATR；浮盈 1.0*ATR 后 SL=-1*ATR",
            step_rules=((0.5, -3.0), (1.0, -1.0)),
        ),
        DynamicStopSpec(
            label="step_0p75_m2p5_1p0_m0p5",
            family="step_stop",
            description="分档：浮盈 0.75*ATR 后 SL=-2.5*ATR；浮盈 1.0*ATR 后 SL=-0.5*ATR",
            step_rules=((0.75, -2.5), (1.0, -0.5)),
        ),
        DynamicStopSpec(
            label="step_0p75_m2p5_1p1_0",
            family="step_stop",
            description="分档：浮盈 0.75*ATR 后 SL=-2.5*ATR；浮盈 1.1*ATR 后 SL=0",
            step_rules=((0.75, -2.5), (1.1, 0.0)),
        ),
        DynamicStopSpec(
            label="trail_act0p75_dist1p0",
            family="activation_trailing",
            description="浮盈 >=0.75*ATR 后，下一根 K 起启用 1.0*ATR 跟踪止损",
            trail_activation_atr=0.75,
            trail_distance_atr=1.0,
        ),
        DynamicStopSpec(
            label="trail_act1p0_dist0p5",
            family="activation_trailing",
            description="浮盈 >=1.0*ATR 后，下一根 K 起启用 0.5*ATR 跟踪止损",
            trail_activation_atr=1.0,
            trail_distance_atr=0.5,
        ),
        DynamicStopSpec(
            label="trail_act1p0_dist0p75",
            family="activation_trailing",
            description="浮盈 >=1.0*ATR 后，下一根 K 起启用 0.75*ATR 跟踪止损",
            trail_activation_atr=1.0,
            trail_distance_atr=0.75,
        ),
        DynamicStopSpec(
            label="step_0p75_m2p5_trail1p0_0p5",
            family="combo",
            description="浮盈 0.75*ATR 后 SL=-2.5*ATR；浮盈 1.0*ATR 后启用 0.5*ATR trailing",
            step_rules=((0.75, -2.5),),
            trail_activation_atr=1.0,
            trail_distance_atr=0.5,
        ),
    ]


def stop_price(entry_price: float, direction: int, stop_return: float) -> float:
    return entry_price * (1.0 + direction * stop_return)


def favorable_return(entry_price: float, direction: int, high: float, low: float) -> float:
    if direction == 1:
        return high / entry_price - 1.0
    return entry_price / low - 1.0


def adverse_return(entry_price: float, direction: int, high: float, low: float) -> float:
    if direction == 1:
        return low / entry_price - 1.0
    return entry_price / high - 1.0


def update_stop_return(
    *,
    current_stop_return: float,
    max_favorable_return: float,
    atr_pct: float,
    spec: DynamicStopSpec,
) -> float:
    next_stop_return = current_stop_return
    if spec.break_even_trigger_atr is not None and spec.break_even_stop_atr is not None:
        if max_favorable_return >= spec.break_even_trigger_atr * atr_pct:
            next_stop_return = max(next_stop_return, spec.break_even_stop_atr * atr_pct)
    for trigger_atr, stop_atr in spec.step_rules:
        if max_favorable_return >= trigger_atr * atr_pct:
            next_stop_return = max(next_stop_return, stop_atr * atr_pct)
    if spec.trail_activation_atr is not None and spec.trail_distance_atr is not None:
        if max_favorable_return >= spec.trail_activation_atr * atr_pct:
            next_stop_return = max(
                next_stop_return,
                max_favorable_return - spec.trail_distance_atr * atr_pct,
            )
    return next_stop_return


def simulate_dynamic_stop_trades(
    context: v12.evolution.EvalContext,
    spec: DynamicStopSpec,
    entry_delay_bars: int,
) -> list[v12.EventTrade]:
    market = context.market
    state = v12.signal_state(context.features, v12.BASE_CONFIG.signal)
    atr_pct_values = context.features[f"atr_pct{ATR_WINDOW}"].to_numpy("float64")
    trades: list[v12.EventTrade] = []
    n = len(market.open)
    for signal_idx, direction_value in zip(
        state.signal_i,
        state.directions,
        strict=False,
    ):
        signal_i = int(signal_idx)
        entry_i = signal_i + entry_delay_bars
        if entry_i >= n - 1:
            continue
        atr_pct = float(atr_pct_values[signal_i])
        if not np.isfinite(atr_pct) or atr_pct <= 0.0:
            continue
        forced_exit_i = min(entry_i + spec.max_hold_bars, n - 1)
        if forced_exit_i <= entry_i:
            continue

        direction = int(direction_value)
        entry_price = float(market.open[entry_i])
        take_profit_return = spec.tp_atr_mult * atr_pct
        take_profit_price = stop_price(entry_price, direction, take_profit_return)
        initial_stop_return = -spec.initial_sl_atr_mult * atr_pct
        active_stop_return = initial_stop_return
        max_favorable = 0.0
        min_path = 0.0
        max_path = 0.0
        exit_i = forced_exit_i
        exit_price = float(market.open[forced_exit_i])
        exit_reason = "max_hold"

        for i in range(entry_i, forced_exit_i):
            open_price = float(market.open[i])
            high = float(market.high[i])
            low = float(market.low[i])
            active_stop_price = stop_price(entry_price, direction, active_stop_return)

            min_path = min(min_path, adverse_return(entry_price, direction, high, low))
            max_path = max(max_path, favorable_return(entry_price, direction, high, low))

            if direction == 1:
                if open_price <= active_stop_price:
                    exit_i = i
                    exit_price = open_price
                    exit_reason = "dynamic_stop_gap" if active_stop_return > initial_stop_return else "stop_gap"
                    break
                if open_price >= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit_gap"
                    break
                if low <= active_stop_price:
                    exit_i = i
                    exit_price = active_stop_price
                    exit_reason = "dynamic_stop" if active_stop_return > initial_stop_return else "stop_loss"
                    break
                if high >= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                    break
            else:
                if open_price >= active_stop_price:
                    exit_i = i
                    exit_price = open_price
                    exit_reason = "dynamic_stop_gap" if active_stop_return > initial_stop_return else "stop_gap"
                    break
                if open_price <= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit_gap"
                    break
                if high >= active_stop_price:
                    exit_i = i
                    exit_price = active_stop_price
                    exit_reason = "dynamic_stop" if active_stop_return > initial_stop_return else "stop_loss"
                    break
                if low <= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                    break

            # Stop updates become active from the next bar only.
            max_favorable = max(max_favorable, favorable_return(entry_price, direction, high, low))
            active_stop_return = update_stop_return(
                current_stop_return=active_stop_return,
                max_favorable_return=max_favorable,
                atr_pct=atr_pct,
                spec=spec,
            )

        if exit_reason == "max_hold":
            timeout_return = (
                exit_price / entry_price - 1.0
                if direction == 1
                else entry_price / exit_price - 1.0
            )
            min_path = min(min_path, timeout_return)
            max_path = max(max_path, timeout_return)

        raw_return = direction * (exit_price / entry_price - 1.0)
        trades.append(
            v12.EventTrade(
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
                adx14=v12.finite(market.adx14[signal_i], 0.0),
                rvol96=v12.finite(market.rvol96[signal_i], 0.0),
                h1_dir_spread=v12.finite(market.h1_spread[signal_i], 0.0) * direction,
                h4_dir_spread=v12.finite(market.h4_spread[signal_i], 0.0) * direction,
                dir_ret16=v12.finite(market.ret16[signal_i], 0.0) * direction,
                dir_ret48=v12.finite(market.ret48[signal_i], 0.0) * direction,
                dir_ret96=v12.finite(market.ret96[signal_i], 0.0) * direction,
                dir_macd=v12.finite(market.macd_hist[signal_i], 0.0) * direction,
                dir_rsi14=(
                    v12.finite(market.rsi14[signal_i], 50.0)
                    if direction == 1
                    else 100.0 - v12.finite(market.rsi14[signal_i], 50.0)
                ),
                atr_pct96=v12.finite(market.atr_pct96[signal_i], 0.0),
                atr_ratio96_672=v12.finite(market.atr_ratio96_672[signal_i], 99.0),
                previous_signal_age=v12.finite(state.previous_signal_age[signal_i], 0.0),
                churn192=v12.finite(state.churn192[signal_i], 999.0),
            )
        )
    return trades


def window_bounds(
    context: v12.evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = pd.Timestamp(context.end_ts)
    if duration is None:
        return pd.Timestamp(context.start_ts), end_ts
    return max(pd.Timestamp(context.start_ts), end_ts - duration), end_ts


def window_trades(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return [trade for trade in trades if start_ts <= pd.Timestamp(trade.entry_ts) < end_ts]


def selected_trades(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return v1.selected_trades_live(window_trades(trades, start_ts, end_ts), filter_spec)


def selected_returns(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    return [
        float(V14_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
        for trade in selected_trades(trades, filter_spec, start_ts, end_ts)
    ]


def exit_counts(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in selected_trades(trades, filter_spec, start_ts, end_ts):
        counts[trade.exit_reason] = counts.get(trade.exit_reason, 0) + 1
    return counts


def evaluate_row(
    *,
    dataset: str,
    spec: DynamicStopSpec,
    trades: list[v12.EventTrade],
    filter_spec: Any,
    entry_label: str,
    window: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400.0, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades(trades, start_ts, end_ts),
        filter_spec=filter_spec,
        exposure=V14_EXPOSURE,
        period_days=period_days,
        exit_spec=spec.exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    metrics = {
        "annual_return_pct": 0.0,
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": 0.0,
        "trades": 0,
        "trades_per_day": 0.0,
        "profit_factor": 0.0,
    }
    if result is not None:
        metrics.update(asdict(result))
    returns = selected_returns(trades, filter_spec, start_ts, end_ts)
    counts = exit_counts(trades, filter_spec, start_ts, end_ts)
    return {
        "dataset": dataset,
        "label": spec.label,
        "family": spec.family,
        "description": spec.description,
        "entry_timing": entry_label,
        "window": window,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": period_days,
        "tp_atr_mult": spec.tp_atr_mult,
        "initial_sl_atr_mult": spec.initial_sl_atr_mult,
        "max_hold_bars": spec.max_hold_bars,
        "trades": int(metrics["trades"]),
        "trades_per_week": float(metrics["trades"]) / period_days * 7.0,
        "total_return_pct": float(metrics["total_return_pct"]),
        "annual_return_pct": float(metrics["annual_return_pct"]),
        "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
        "win_rate_pct": float(metrics["win_rate_pct"]),
        "profit_factor": float(metrics["profit_factor"]),
        "avg_trade_pct": float(np.mean(returns)) if returns else 0.0,
        "median_trade_pct": float(np.median(returns)) if returns else 0.0,
        "worst_trade_pct": float(np.min(returns)) if returns else 0.0,
        "best_trade_pct": float(np.max(returns)) if returns else 0.0,
        "take_profit_exits": counts.get("take_profit", 0) + counts.get("take_profit_gap", 0),
        "stop_exits": counts.get("stop_loss", 0) + counts.get("stop_gap", 0),
        "dynamic_stop_exits": counts.get("dynamic_stop", 0) + counts.get("dynamic_stop_gap", 0),
        "max_hold_exits": counts.get("max_hold", 0),
    }


def evaluate_fixed(
    *,
    dataset: str,
    context: v12.evolution.EvalContext,
    specs_to_run: list[DynamicStopSpec],
    windows: tuple[tuple[str, pd.Timedelta | None], ...],
) -> pd.DataFrame:
    filter_spec = v14_filter()
    rows: list[dict[str, Any]] = []
    for spec in specs_to_run:
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = simulate_dynamic_stop_trades(
                context,
                spec,
                entry_delay_bars=entry_delay_bars,
            )
            for window, duration in windows:
                start_ts, end_ts = window_bounds(context, duration)
                rows.append(
                    evaluate_row(
                        dataset=dataset,
                        spec=spec,
                        trades=trades,
                        filter_spec=filter_spec,
                        entry_label=entry_label,
                        window=window,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )
    return pd.DataFrame(rows)


def full_comparison(full: pd.DataFrame) -> pd.DataFrame:
    k1 = full.loc[full["entry_timing"].eq("K+1")].set_index("label")
    k2 = full.loc[full["entry_timing"].eq("K+2")].set_index("label")
    merged = k1.join(k2, lsuffix="_k1", rsuffix="_k2")
    base = merged.loc["baseline_tp1p25_sl5"]
    merged["delta_total_return_pct_k1"] = merged["total_return_pct_k1"] - base["total_return_pct_k1"]
    merged["delta_max_drawdown_pct_k1"] = merged["max_drawdown_pct_k1"] - base["max_drawdown_pct_k1"]
    merged["delta_win_rate_pct_k1"] = merged["win_rate_pct_k1"] - base["win_rate_pct_k1"]
    merged["delta_total_return_pct_k2"] = merged["total_return_pct_k2"] - base["total_return_pct_k2"]
    merged["delta_max_drawdown_pct_k2"] = merged["max_drawdown_pct_k2"] - base["max_drawdown_pct_k2"]
    merged["pass_strict_gate"] = (
        (merged.index != "baseline_tp1p25_sl5")
        & (
        (merged["total_return_pct_k1"] >= base["total_return_pct_k1"])
        & (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"])
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 1.0)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"] * 0.90)
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"])
        )
    )
    merged["pass_defensive_gate"] = (
        (merged.index != "baseline_tp1p25_sl5")
        & (
        (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"] + 2.0)
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"] + 2.0)
        & (merged["total_return_pct_k1"] >= base["total_return_pct_k1"] * 0.70)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"] * 0.70)
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 3.0)
        )
    )
    merged["score"] = (
        np.log1p(np.maximum(merged["total_return_pct_k1"], -90.0) / 100.0) * 0.28
        + np.log1p(np.maximum(merged["total_return_pct_k2"], -90.0) / 100.0) * 0.22
        + ((merged["max_drawdown_pct_k1"] + 60.0) / 60.0) * 0.18
        + ((merged["max_drawdown_pct_k2"] + 60.0) / 60.0) * 0.16
        + ((merged["win_rate_pct_k1"] - 80.0) / 20.0) * 0.10
        + ((merged["worst_trade_pct_k1"] + 20.0) / 20.0) * 0.06
    )
    return merged.sort_values(
        ["pass_strict_gate", "pass_defensive_gate", "score"],
        ascending=False,
    ).reset_index()


def rolling_summary(
    context: v12.evolution.EvalContext,
    labels: list[str],
    specs_by_label: dict[str, DynamicStopSpec],
) -> pd.DataFrame:
    filter_spec = v14_filter()
    rows: list[dict[str, Any]] = []
    for label in labels:
        spec = specs_by_label[label]
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = simulate_dynamic_stop_trades(
                context,
                spec,
                entry_delay_bars=entry_delay_bars,
            )
            for days in (30, 90):
                duration = pd.Timedelta(days=days)
                step = pd.Timedelta(days=7)
                left = pd.Timestamp(context.start_ts)
                returns: list[float] = []
                drawdowns: list[float] = []
                trade_counts: list[int] = []
                while left + duration <= pd.Timestamp(context.end_ts):
                    row = evaluate_row(
                        dataset="standard_data_lake",
                        spec=spec,
                        trades=trades,
                        filter_spec=filter_spec,
                        entry_label=entry_label,
                        window=f"rolling_{days}d",
                        start_ts=left,
                        end_ts=left + duration,
                    )
                    returns.append(float(row["total_return_pct"]))
                    drawdowns.append(float(row["max_drawdown_pct"]))
                    trade_counts.append(int(row["trades"]))
                    left += step
                arr = np.array(returns)
                dd = np.array(drawdowns)
                counts = np.array(trade_counts)
                rows.append(
                    {
                        "label": label,
                        "family": spec.family,
                        "entry_timing": entry_label,
                        "rolling_days": days,
                        "slices": int(len(arr)),
                        "positive_slices": int((arr > 0).sum()) if len(arr) else 0,
                        "median_total_return_pct": float(np.median(arr)) if len(arr) else 0.0,
                        "worst_total_return_pct": float(arr.min()) if len(arr) else 0.0,
                        "median_max_drawdown_pct": float(np.median(dd)) if len(dd) else 0.0,
                        "worst_max_drawdown_pct": float(dd.min()) if len(dd) else 0.0,
                        "median_trades": float(np.median(counts)) if len(counts) else 0.0,
                        "zero_trade_slices": int((counts == 0).sum()) if len(counts) else 0,
                    }
                )
    return pd.DataFrame(rows)


def exit_count_rows(
    context: v12.evolution.EvalContext,
    labels: list[str],
    specs_by_label: dict[str, DynamicStopSpec],
) -> pd.DataFrame:
    filter_spec = v14_filter()
    rows: list[dict[str, Any]] = []
    start_ts, end_ts = window_bounds(context, None)
    for label in labels:
        spec = specs_by_label[label]
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = simulate_dynamic_stop_trades(
                context,
                spec,
                entry_delay_bars=entry_delay_bars,
            )
            counts = exit_counts(trades, filter_spec, start_ts, end_ts)
            row = {"label": label, "entry_timing": entry_label}
            row.update(counts)
            rows.append(row)
    return pd.DataFrame(rows).fillna(0)


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def comparison_table(frame: pd.DataFrame, limit: int = 14) -> list[str]:
    lines = [
        "| 规则 | family | K+1收益 | K+1回撤 | K+1胜率 | K+1最差 | K+2收益 | K+2回撤 | K+2胜率 | Gate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in frame.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['family_k1']}` | `{fmt(row['total_return_pct_k1'])}%` | "
            f"`{fmt(row['max_drawdown_pct_k1'])}%` | `{fmt(row['win_rate_pct_k1'])}%` | "
            f"`{fmt(row['worst_trade_pct_k1'], 3)}%` | `{fmt(row['total_return_pct_k2'])}%` | "
            f"`{fmt(row['max_drawdown_pct_k2'])}%` | `{fmt(row['win_rate_pct_k2'])}%` | "
            f"`{bool(row['pass_strict_gate'])}/{bool(row['pass_defensive_gate'])}` |"
        )
    return lines


def fixed_table(frame: pd.DataFrame, *, dataset: str, entry: str, window: str, labels: list[str]) -> list[str]:
    subset = frame.loc[
        frame["dataset"].eq(dataset)
        & frame["entry_timing"].eq(entry)
        & frame["window"].eq(window)
        & frame["label"].isin(labels)
    ].copy()
    order = {label: idx for idx, label in enumerate(labels)}
    subset["order"] = subset["label"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {dataset} / {entry} / {window}",
        "",
        "| 规则 | 交易数 | 总收益 | 回撤 | 胜率 | PF | 平均单笔 | 最差单笔 | 动态止损退出 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['max_drawdown_pct'])}%` | `{fmt(row['win_rate_pct'])}%` | "
            f"`{fmt(row['profit_factor'], 3)}` | `{fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{fmt(row['worst_trade_pct'], 3)}%` | `{int(row['dynamic_stop_exits'])}` |"
        )
    return lines


def rolling_table(rolling: pd.DataFrame, *, entry: str, days: int, labels: list[str]) -> list[str]:
    subset = rolling.loc[
        rolling["entry_timing"].eq(entry)
        & rolling["rolling_days"].eq(days)
        & rolling["label"].isin(labels)
    ].copy()
    order = {label: idx for idx, label in enumerate(labels)}
    subset["order"] = subset["label"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {entry} / rolling {days}d",
        "",
        "| 规则 | 正收益切片 | 中位收益 | 最差收益 | 中位回撤 | 最差回撤 | 中位交易数 | 零交易切片 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['positive_slices'])}/{int(row['slices'])}` | "
            f"`{fmt(row['median_total_return_pct'])}%` | `{fmt(row['worst_total_return_pct'])}%` | "
            f"`{fmt(row['median_max_drawdown_pct'])}%` | `{fmt(row['worst_max_drawdown_pct'])}%` | "
            f"`{fmt(row['median_trades'], 1)}` | `{int(row['zero_trade_slices'])}` |"
        )
    return lines


def exit_counts_table(exit_counts_df: pd.DataFrame) -> list[str]:
    columns = list(exit_counts_df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in exit_counts_df.to_dict(orient="records"):
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, (int, np.integer)):
                values.append(f"`{int(value)}`")
            elif isinstance(value, (float, np.floating)) and float(value).is_integer():
                values.append(f"`{int(value)}`")
            else:
                values.append(f"`{value}`")
        lines.append("| " + " | ".join(values) + " |")
    return lines


def render_markdown(
    comparison: pd.DataFrame,
    full: pd.DataFrame,
    windows: pd.DataFrame,
    recent: pd.DataFrame,
    rolling: pd.DataFrame,
    exit_counts_df: pd.DataFrame,
    specs_by_label: dict[str, DynamicStopSpec],
    lake_quality: dict[str, Any],
    recent_quality: dict[str, Any],
) -> str:
    base = comparison.loc[comparison["label"].eq("baseline_tp1p25_sl5")].iloc[0]
    strict = comparison.loc[comparison["pass_strict_gate"]]
    defensive = comparison.loc[comparison["pass_defensive_gate"]]
    best = comparison.iloc[0]
    labels = list(dict.fromkeys(["baseline_tp1p25_sl5", "fixed_tp1p25_sl3", *comparison["label"].head(7).tolist()]))
    lines = [
        f"# HYPE-15M-MII V1.4 动态止损诊断 {RUN_DATE}",
        "",
        "## 结论",
        "",
        "本轮保持 `V1.4` 入场、`min_atr_pct96=75 bps`、`min_rvol96=0.85`、`TP=1.25*ATR96`、`hold=24`、Binance 成本和 `2.5x` 不变，只测试盈利后上移止损。动态 stop 更新只在下一根 K 生效；同一根 K 内仍按已生效 stop/TP 做 stop-first 检查，避免不可执行的同根 high/low lookahead。",
        "",
        (
            f"`V1.4 baseline`：K+1 总收益 `{fmt(base['total_return_pct_k1'])}%`、回撤 "
            f"`{fmt(base['max_drawdown_pct_k1'])}%`、胜率 `{fmt(base['win_rate_pct_k1'])}%`；"
            f"K+2 总收益 `{fmt(base['total_return_pct_k2'])}%`、回撤 `{fmt(base['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"综合排序第一为 `{best['label']}`：K+1 总收益 `{fmt(best['total_return_pct_k1'])}%`、"
            f"回撤 `{fmt(best['max_drawdown_pct_k1'])}%`；K+2 总收益 `{fmt(best['total_return_pct_k2'])}%`、"
            f"回撤 `{fmt(best['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"严格 gate 通过 `{len(strict)}/{len(comparison)}`；防守 gate 通过 "
            f"`{len(defensive)}/{len(comparison)}`。"
        ),
        "",
    ]
    if len(strict):
        label = str(strict.iloc[0]["label"])
        lines.append(f"可继续观察的动态止损候选是 `{label}`：{specs_by_label[label].description}。")
    elif len(defensive):
        label = str(defensive.iloc[0]["label"])
        lines.append(f"只有防守 gate 候选 `{label}`：{specs_by_label[label].description}，但尚未达到收益/回撤联合替换条件。")
    else:
        lines.append("没有动态止损规则同时满足收益保留与 K+1/K+2 回撤改善。")
    lines.extend(
        [
            "",
            "结论口径：动态止损如果只改善最近 30/90 天，但全样本收益、滚动窗口或 K+2 明显退化，就只能记录为近期防守观察，不替换 `V1.4 baseline`。",
            "",
            "## 全样本综合对比",
            "",
            *comparison_table(comparison),
            "",
            "## 固定窗口",
            "",
            *fixed_table(full, dataset="standard_data_lake", entry="K+1", window="全样本", labels=labels),
            "",
            *fixed_table(full, dataset="standard_data_lake", entry="K+2", window="全样本", labels=labels),
            "",
            *fixed_table(windows, dataset="standard_data_lake", entry="K+1", window="最近90d", labels=labels),
            "",
            "## Recent API",
            "",
            *fixed_table(recent, dataset="recent_binance_api", entry="K+1", window="最近90d", labels=labels),
            "",
            *fixed_table(recent, dataset="recent_binance_api", entry="K+1", window="最近30d", labels=labels),
            "",
            "## 滚动窗口",
            "",
            *rolling_table(rolling, entry="K+1", days=30, labels=labels),
            "",
            *rolling_table(rolling, entry="K+2", days=90, labels=labels),
            "",
            "## 出场原因",
            "",
            *exit_counts_table(exit_counts_df),
            "",
            "## 数据质量",
            "",
            f"- Standard data lake：`{lake_quality['first_ts']}` 到 `{lake_quality['last_ts']}`，rows `{lake_quality['rows']}`，quality gate `{lake_quality['quality_gate_pass']}`。",
            f"- Recent Binance API：`{recent_quality['first_ts']}` 到 `{recent_quality['last_ts']}`，rows `{recent_quality['rows']}`，quality gate `{recent_quality['quality_gate_pass']}`。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 全样本 CSV：`{FULL_CSV_PATH}`",
            f"- 固定窗口 CSV：`{WINDOW_CSV_PATH}`",
            f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
            f"- recent API CSV：`{RECENT_CSV_PATH}`",
            f"- 出场原因 CSV：`{EXIT_COUNTS_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    lake_context, lake_metadata, lake_quality = v12.build_context()
    specs_to_run = specs()
    specs_by_label = {spec.label: spec for spec in specs_to_run}
    fixed = evaluate_fixed(
        dataset="standard_data_lake",
        context=lake_context,
        specs_to_run=specs_to_run,
        windows=FIXED_WINDOWS,
    )
    full = fixed.loc[fixed["window"].eq("全样本")].copy()
    windows = fixed.loc[~fixed["window"].eq("全样本")].copy()
    comparison = full_comparison(full)
    rolling_labels = list(dict.fromkeys(["baseline_tp1p25_sl5", "fixed_tp1p25_sl3", *comparison["label"].head(8).tolist()]))
    rolling = rolling_summary(lake_context, rolling_labels, specs_by_label)
    exit_counts_df = exit_count_rows(lake_context, rolling_labels, specs_by_label)

    recent_frame = drought.fetch_recent_fapi_klines()
    recent_quality = drought.data_quality(recent_frame)
    if not recent_quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(recent_quality, ensure_ascii=False)}")
    recent_context = drought.build_context(recent_frame)
    recent = evaluate_fixed(
        dataset="recent_binance_api",
        context=recent_context,
        specs_to_run=specs_to_run,
        windows=tuple((name, duration) for name, duration in RECENT_WINDOWS),
    )

    full.to_csv(FULL_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    recent.to_csv(RECENT_CSV_PATH, index=False)
    exit_counts_df.to_csv(EXIT_COUNTS_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(
            comparison,
            full,
            windows,
            recent,
            rolling,
            exit_counts_df,
            specs_by_label,
            lake_quality,
            recent_quality,
        ),
        encoding="utf-8",
    )
    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "dynamic_stop_diagnostic_not_promoted",
                    "lake_metadata": lake_metadata,
                    "lake_quality": lake_quality,
                    "recent_quality": recent_quality,
                    "specs": [asdict(spec) for spec in specs_to_run],
                    "comparison": comparison.to_dict(orient="records"),
                    "full": full.to_dict(orient="records"),
                    "windows": windows.to_dict(orient="records"),
                    "rolling": rolling.to_dict(orient="records"),
                    "recent": recent.to_dict(orient="records"),
                    "exit_counts": exit_counts_df.to_dict(orient="records"),
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Top comparison")
    print(
        comparison[
            [
                "label",
                "family_k1",
                "trades_k1",
                "total_return_pct_k1",
                "max_drawdown_pct_k1",
                "win_rate_pct_k1",
                "worst_trade_pct_k1",
                "total_return_pct_k2",
                "max_drawdown_pct_k2",
                "win_rate_pct_k2",
                "pass_strict_gate",
                "pass_defensive_gate",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
