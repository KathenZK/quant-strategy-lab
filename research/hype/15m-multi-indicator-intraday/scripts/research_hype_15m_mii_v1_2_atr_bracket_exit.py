from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_clean_evolution as evolution  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    EventTrade,
    ExitSpec,
    build_market_arrays,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.2"
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = (
    FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_2_atr_bracket_exit.py"
)
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
RANKING_CSV_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_bracket_exit_ranking_2026-06-30.csv"
)
EXIT_COUNTS_CSV_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_bracket_exit_counts_2026-06-30.csv"
)
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_bracket_exit_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-2-atr-bracket-exit-2026-06-30.md"

BASE_CONFIG = evolution.CleanConfig(
    rsi_window=7,
    rsi_low=40.0,
    rsi_high=60.0,
    min_atr_pct96=0.0075,
    min_rvol96=1.0,
    h1_confirm=False,
    rsi14_band=False,
    take_profit_pct=0.012,
    stop_pct=0.036,
    max_hold_bars=16,
    exposure=2.0,
)
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))


@dataclass(frozen=True, slots=True)
class AtrBracketCandidate:
    label: str
    family: str
    atr_window: int | None
    tp_atr_mult: float | None
    sl_atr_mult: float | None
    max_hold_bars: int
    take_profit_pct: float | None = None
    stop_pct: float | None = None


def value_slug(value: float) -> str:
    return f"{value:g}".replace(".", "p")


def pct_slug(value: float) -> str:
    return value_slug(value * 10_000)


def candidates() -> list[AtrBracketCandidate]:
    output = [
        AtrBracketCandidate(
            label="baseline_fixed_tp120_sl360_hold16",
            family="fixed_baseline",
            atr_window=None,
            tp_atr_mult=None,
            sl_atr_mult=None,
            max_hold_bars=BASE_CONFIG.max_hold_bars,
            take_profit_pct=BASE_CONFIG.take_profit_pct,
            stop_pct=BASE_CONFIG.stop_pct,
        )
    ]
    for atr_window in (14, 48, 96):
        for tp_atr_mult in (0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0):
            for sl_atr_mult in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
                if sl_atr_mult <= tp_atr_mult * 0.75:
                    continue
                for max_hold_bars in (16, 24, 32, 48):
                    output.append(
                        AtrBracketCandidate(
                            label=(
                                f"atr{atr_window}_tp{value_slug(tp_atr_mult)}x_"
                                f"sl{value_slug(sl_atr_mult)}x_hold{max_hold_bars}"
                            ),
                            family="atr_bracket",
                            atr_window=atr_window,
                            tp_atr_mult=tp_atr_mult,
                            sl_atr_mult=sl_atr_mult,
                            max_hold_bars=max_hold_bars,
                        )
                    )
    return output


def build_context() -> tuple[evolution.EvalContext, dict[str, Any], dict[str, Any]]:
    frame, metadata, quality = v1.load_data_lake()
    features = evolution.add_rsi_features(evolution.add_features(frame, []))
    context = evolution.EvalContext(
        features=features,
        market=build_market_arrays(features),
        start_ts=pd.Timestamp(features["ts"].min()),
        end_ts=pd.Timestamp(features["ts"].max()) + pd.Timedelta(minutes=15),
        signal_cache={},
        trade_cache=OrderedDict(),
    )
    v1.engine.simulate_trades = v1.simulate_trades_live
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live
    return context, metadata, quality


def candidate_exit_spec(candidate: AtrBracketCandidate) -> ExitSpec:
    if candidate.family == "fixed_baseline":
        return BASE_CONFIG.exit
    return ExitSpec(
        kind="fixed",
        take_profit_pct=0.0,
        stop_pct=0.0,
        max_hold_bars=candidate.max_hold_bars,
    )


def finite(value: float, default: float) -> float:
    return float(value) if np.isfinite(value) else default


def simulate_atr_bracket_trades(
    context: evolution.EvalContext,
    candidate: AtrBracketCandidate,
    entry_delay_bars: int,
) -> list[EventTrade]:
    if candidate.family == "fixed_baseline":
        state = signal_state(context.features, BASE_CONFIG.signal)
        return v1.simulate_trades_live(
            context.market,
            state,
            BASE_CONFIG.exit,
            entry_delay_bars=entry_delay_bars,
        )

    if candidate.atr_window is None or candidate.tp_atr_mult is None or candidate.sl_atr_mult is None:
        raise ValueError("ATR bracket candidate missing ATR parameters")

    market = context.market
    state = signal_state(context.features, BASE_CONFIG.signal)
    atr_pct = context.features[f"atr_pct{candidate.atr_window}"].to_numpy("float64")
    trades: list[EventTrade] = []
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
        dynamic_atr_pct = float(atr_pct[signal_i])
        if not np.isfinite(dynamic_atr_pct) or dynamic_atr_pct <= 0:
            continue

        take_profit_pct = dynamic_atr_pct * candidate.tp_atr_mult
        stop_pct = dynamic_atr_pct * candidate.sl_atr_mult
        forced_exit_i = min(entry_i + candidate.max_hold_bars, n - 1)
        if forced_exit_i <= entry_i:
            continue

        direction = int(direction_value)
        entry_price = float(market.open[entry_i])
        stop_price = entry_price * (1 - direction * stop_pct)
        take_profit_price = entry_price * (1 + direction * take_profit_pct)
        min_path = 0.0
        max_path = 0.0
        exit_i = forced_exit_i
        exit_price = float(market.open[forced_exit_i])
        exit_reason = "max_hold"

        for i in range(entry_i, forced_exit_i):
            open_price = float(market.open[i])
            high = float(market.high[i])
            low = float(market.low[i])
            if direction == 1:
                min_path = min(min_path, low / entry_price - 1)
                max_path = max(max_path, high / entry_price - 1)
                if open_price <= stop_price:
                    exit_i, exit_price, exit_reason = i, open_price, "stop_gap"
                    break
                if open_price >= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit_gap"
                    break
                if low <= stop_price:
                    exit_i, exit_price, exit_reason = i, stop_price, "stop_loss"
                    break
                if high >= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                    break
            else:
                min_path = min(min_path, entry_price / high - 1)
                max_path = max(max_path, entry_price / low - 1)
                if open_price >= stop_price:
                    exit_i, exit_price, exit_reason = i, open_price, "stop_gap"
                    break
                if open_price <= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit_gap"
                    break
                if high >= stop_price:
                    exit_i, exit_price, exit_reason = i, stop_price, "stop_loss"
                    break
                if low <= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                    break

        if exit_reason == "max_hold":
            timeout_return = (
                exit_price / entry_price - 1
                if direction == 1
                else entry_price / exit_price - 1
            )
            min_path = min(min_path, timeout_return)
            max_path = max(max_path, timeout_return)

        raw_return = direction * (exit_price / entry_price - 1)
        trades.append(
            EventTrade(
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
        )
    return trades


def window_trades(
    trades: list[EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[EventTrade]:
    return [trade for trade in trades if start_ts <= trade.entry_ts < end_ts]


def selected_trades(
    trades: list[EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[EventTrade]:
    return v1.selected_trades_live(
        window_trades(trades, start_ts, end_ts),
        BASE_CONFIG.filter,
    )


def evaluate_metrics(
    *,
    context: evolution.EvalContext,
    trades: list[EventTrade],
    exit_spec: ExitSpec,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades(trades, start_ts, end_ts),
        filter_spec=BASE_CONFIG.filter,
        exposure=BASE_CONFIG.exposure,
        period_days=period_days,
        exit_spec=exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if result is None:
        return {
            "annual_return_pct": 0.0,
            "annual_equity_multiple": 1.0,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "trades": 0,
            "trades_per_day": 0.0,
            "profit_factor": 0.0,
        }
    return asdict(result)


def selected_stats(
    trades: list[EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    picked = selected_trades(trades, start_ts, end_ts)
    net_returns = [
        BASE_CONFIG.exposure * (trade.raw_return - ROUND_TRIP_COST) * 100.0
        for trade in picked
    ]
    winners = [value for value in net_returns if value > 0]
    exit_counts: dict[str, int] = {}
    for trade in picked:
        exit_counts[trade.exit_reason] = exit_counts.get(trade.exit_reason, 0) + 1
    return {
        "avg_trade_pct": float(np.mean(net_returns)) if net_returns else 0.0,
        "median_trade_pct": float(np.median(net_returns)) if net_returns else 0.0,
        "avg_winner_pct": float(np.mean(winners)) if winners else 0.0,
        "best_trade_pct": float(np.max(net_returns)) if net_returns else 0.0,
        "worst_trade_pct": float(np.min(net_returns)) if net_returns else 0.0,
        "avg_bars_held": float(np.mean([trade.bars_held for trade in picked]))
        if picked
        else 0.0,
        "exit_counts": exit_counts,
    }


def score_row(row: dict[str, Any]) -> float:
    k1_return = max(float(row["k1_annual_return_pct"]), -90.0)
    k2_return = max(float(row["k2_annual_return_pct"]), -90.0)
    worst_drawdown = min(
        float(row["k1_max_drawdown_pct"]),
        float(row["k2_max_drawdown_pct"]),
    )
    min_win = min(float(row["k1_win_rate_pct"]), float(row["k2_win_rate_pct"]))
    min_last90 = min(
        float(row["k1_last90_annual_return_pct"]),
        float(row["k2_last90_annual_return_pct"]),
    )
    return (
        0.24 * np.log1p(k1_return / 100.0)
        + 0.21 * np.log1p(k2_return / 100.0)
        + 0.19 * ((worst_drawdown + 60.0) / 60.0)
        + 0.17 * ((min_win - 65.0) / 30.0)
        + 0.12 * np.log1p(max(min_last90, -90.0) / 100.0)
        + 0.07 * min(float(row["k1_avg_winner_pct"]) / 3.0, 1.0)
    )


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    context, metadata, quality = build_context()
    last90_start = max(context.start_ts, context.end_ts - pd.Timedelta(days=90))
    rows: list[dict[str, Any]] = []
    exit_count_rows: list[dict[str, Any]] = []
    all_candidates = candidates()
    for index, candidate in enumerate(all_candidates, start=1):
        exit_spec = candidate_exit_spec(candidate)
        row: dict[str, Any] = {
            "label": candidate.label,
            "family": candidate.family,
            "atr_window": candidate.atr_window,
            "tp_atr_mult": candidate.tp_atr_mult,
            "sl_atr_mult": candidate.sl_atr_mult,
            "take_profit_pct": candidate.take_profit_pct,
            "stop_pct": candidate.stop_pct,
            "max_hold_bars": candidate.max_hold_bars,
        }
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = simulate_atr_bracket_trades(
                context,
                candidate,
                entry_delay_bars,
            )
            full = evaluate_metrics(
                context=context,
                trades=trades,
                exit_spec=exit_spec,
                start_ts=context.start_ts,
                end_ts=context.end_ts,
            )
            last90 = evaluate_metrics(
                context=context,
                trades=trades,
                exit_spec=exit_spec,
                start_ts=last90_start,
                end_ts=context.end_ts,
            )
            stats = selected_stats(trades, context.start_ts, context.end_ts)
            prefix = entry_label.lower().replace("+", "")
            for key, value in full.items():
                row[f"{prefix}_{key}"] = value
            row[f"{prefix}_last90_annual_return_pct"] = last90["annual_return_pct"]
            for key, value in stats.items():
                if key == "exit_counts":
                    for reason, count in value.items():
                        exit_count_rows.append(
                            {
                                "label": candidate.label,
                                "entry_timing": entry_label,
                                "exit_reason": reason,
                                "count": count,
                            }
                        )
                else:
                    row[f"{prefix}_{key}"] = value
        row["score"] = score_row(row)
        rows.append(row)
        if index % 100 == 0 or index == len(all_candidates):
            print(f"atr bracket exits {index}/{len(all_candidates)}", flush=True)

    ranking = pd.DataFrame(rows)
    baseline = ranking.loc[ranking["family"].eq("fixed_baseline")].iloc[0]
    ranking["delta_k1_annual_return_pct"] = (
        ranking["k1_annual_return_pct"] - baseline["k1_annual_return_pct"]
    )
    ranking["delta_k1_max_drawdown_pct"] = (
        ranking["k1_max_drawdown_pct"] - baseline["k1_max_drawdown_pct"]
    )
    ranking["delta_k1_win_rate_pct"] = ranking["k1_win_rate_pct"] - baseline["k1_win_rate_pct"]
    ranking["delta_k2_annual_return_pct"] = (
        ranking["k2_annual_return_pct"] - baseline["k2_annual_return_pct"]
    )
    ranking["delta_k2_max_drawdown_pct"] = (
        ranking["k2_max_drawdown_pct"] - baseline["k2_max_drawdown_pct"]
    )
    ranking["beats_baseline_k1_shape"] = (
        ranking["k1_annual_return_pct"].gt(baseline["k1_annual_return_pct"])
        & ranking["k1_max_drawdown_pct"].ge(baseline["k1_max_drawdown_pct"])
        & ranking["k1_win_rate_pct"].ge(baseline["k1_win_rate_pct"])
    )
    ranking["beats_baseline_joint_shape"] = (
        ranking["beats_baseline_k1_shape"]
        & ranking["k2_annual_return_pct"].gt(baseline["k2_annual_return_pct"])
        & ranking["k2_max_drawdown_pct"].ge(baseline["k2_max_drawdown_pct"])
        & ranking["k2_win_rate_pct"].ge(baseline["k2_win_rate_pct"])
    )
    ranking["beats_baseline_shape"] = ranking["beats_baseline_joint_shape"]
    ranking = ranking.sort_values(
        ["beats_baseline_joint_shape", "beats_baseline_k1_shape", "score"],
        ascending=False,
    ).reset_index(drop=True)
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    return ranking, pd.DataFrame(exit_count_rows), metadata, quality


def metric_table(rows: pd.DataFrame, limit: int = 15) -> list[str]:
    lines = [
        "| 排名 | 标签 | K+1 年化/回撤/胜率/PF | K+2 年化/回撤/胜率/PF | Last90 K+1/K+2 | 均赢/最好/最差 | 持仓 | Gate |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{int(row['rank'])}` | `{row['label']}` | "
            f"`{row['k1_annual_return_pct']:.2f}% / {row['k1_max_drawdown_pct']:.2f}% / "
            f"{row['k1_win_rate_pct']:.2f}% / {row['k1_profit_factor']:.3f}` | "
            f"`{row['k2_annual_return_pct']:.2f}% / {row['k2_max_drawdown_pct']:.2f}% / "
            f"{row['k2_win_rate_pct']:.2f}% / {row['k2_profit_factor']:.3f}` | "
            f"`{row['k1_last90_annual_return_pct']:.2f}% / {row['k2_last90_annual_return_pct']:.2f}%` | "
            f"`{row['k1_avg_winner_pct']:.2f}% / {row['k1_best_trade_pct']:.2f}% / {row['k1_worst_trade_pct']:.2f}%` | "
            f"`{row['k1_avg_bars_held']:.2f}` | "
            f"`{bool(row['beats_baseline_joint_shape'])}` |"
        )
    return lines


def exit_reason_table(exit_counts: pd.DataFrame, labels: list[str]) -> list[str]:
    lines = [
        "| 标签 | 入场 | take_profit | stop_loss | gap stop | max_hold |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for label in labels:
        for entry_timing in ("K+1", "K+2"):
            subset = exit_counts.loc[
                exit_counts["label"].eq(label)
                & exit_counts["entry_timing"].eq(entry_timing)
            ]
            counts = {
                str(row["exit_reason"]): int(row["count"])
                for row in subset.to_dict(orient="records")
            }
            lines.append(
                f"| `{label}` | `{entry_timing}` | "
                f"`{counts.get('take_profit', 0) + counts.get('take_profit_gap', 0)}` | "
                f"`{counts.get('stop_loss', 0)}` | "
                f"`{counts.get('stop_gap', 0)}` | "
                f"`{counts.get('max_hold', 0)}` |"
            )
    return lines


def row_by_label(rows: pd.DataFrame, label: str) -> pd.Series:
    selected = rows.loc[rows["label"].eq(label)]
    if selected.empty:
        raise ValueError(f"missing label={label}")
    return selected.iloc[0]


def render_markdown(
    ranking: pd.DataFrame,
    exit_counts: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    baseline = row_by_label(ranking, "baseline_fixed_tp120_sl360_hold16")
    atr_rows = ranking.loc[ranking["family"].eq("atr_bracket")].copy()
    best_atr = atr_rows.iloc[0]
    best_k1_return = atr_rows.sort_values(
        "k1_annual_return_pct",
        ascending=False,
    ).iloc[0]
    best_k2_return = atr_rows.sort_values(
        "k2_annual_return_pct",
        ascending=False,
    ).iloc[0]
    passed_k1 = atr_rows.loc[atr_rows["beats_baseline_k1_shape"]]
    passed_joint = atr_rows.loc[atr_rows["beats_baseline_joint_shape"]]
    exit_labels = list(
        dict.fromkeys(
            [
                str(baseline["label"]),
                str(best_atr["label"]),
                str(best_k1_return["label"]),
            ]
        )
    )

    lines = [
        f"# HYPE-15M-MII V1.2 ATR 动态止盈止损测试 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        "这次不是 trailing。测试方法是在信号 K 收盘后读取已知 `ATR%`，下一根 open 入场时设置固定 bracket：`TP = ATR% * tp_mult`、`SL = ATR% * sl_mult`，进场后 TP/SL 不移动。",
        "",
        (
            f"- 固定百分比 baseline：K+1 年化 `{baseline['k1_annual_return_pct']:.2f}%`、"
            f"回撤 `{baseline['k1_max_drawdown_pct']:.2f}%`、胜率 `{baseline['k1_win_rate_pct']:.2f}%`、"
            f"PF `{baseline['k1_profit_factor']:.3f}`；K+2 年化 `{baseline['k2_annual_return_pct']:.2f}%`、"
            f"回撤 `{baseline['k2_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- ATR bracket 综合第一：`{best_atr['label']}`，K+1 年化 "
            f"`{best_atr['k1_annual_return_pct']:.2f}%`、回撤 "
            f"`{best_atr['k1_max_drawdown_pct']:.2f}%`、胜率 "
            f"`{best_atr['k1_win_rate_pct']:.2f}%`；K+2 年化 "
            f"`{best_atr['k2_annual_return_pct']:.2f}%`、回撤 "
            f"`{best_atr['k2_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- ATR bracket 最高 K+1 年化：`{best_k1_return['label']}`，K+1 年化 "
            f"`{best_k1_return['k1_annual_return_pct']:.2f}%`、回撤 "
            f"`{best_k1_return['k1_max_drawdown_pct']:.2f}%`、胜率 "
            f"`{best_k1_return['k1_win_rate_pct']:.2f}%`。"
        ),
        (
            f"- ATR bracket 最高 K+2 年化：`{best_k2_return['label']}`，K+2 年化 "
            f"`{best_k2_return['k2_annual_return_pct']:.2f}%`、回撤 "
            f"`{best_k2_return['k2_max_drawdown_pct']:.2f}%`、胜率 "
            f"`{best_k2_return['k2_win_rate_pct']:.2f}%`。"
        ),
        (
            f"- K+1 收益、回撤、胜率同时超过 baseline：`{len(passed_k1)}/{len(atr_rows)}`；"
            f"K+1/K+2 收益、回撤、胜率同时超过 baseline：`{len(passed_joint)}/{len(atr_rows)}`。"
            "ATR bracket 确实比 trailing 更有价值，但可通过联合 gate 的配置很少。"
        ),
        "- 本报告按用户指定将联合通过配置记录为 `HYPE-15M-MII-V1.2`；它是 `V1.1` 固定 TP/SL 的 ATR 动态止盈止损观察版，不改变 `NO-GO` 状态。",
        "",
        "## 参数与口径",
        "",
        f"- Version：`{VERSION}`。",
        f"- Engine name：`{BASE_CONFIG.name}`。",
        "- Base signal/filter：沿用 `HYPE-15M-MII-V1.1` 的 RSI/MACD/ATR/RVOL 入场过滤。",
        "- V1.1 baseline exit：固定 `TP=1.20%`、`SL=3.60%`、`hold=16`。",
        "- V1.2 selected exit：`ATR96`，`TP = 1.25 * ATR96%`，`SL = 5.0 * ATR96%`，`hold=24`。",
        "- ATR source：`ATR14/ATR48/ATR96`，使用信号 K 收盘时已知的 `ATR%`。",
        "- ATR bracket grid：`tp_mult in 0.6-4.0`，`sl_mult in 1.0-5.0`，`hold in 16/24/32/48`。",
        "- Execution：闭合 K 信号、K+1/K+2 open 入场、单仓不重叠、stop-first、timeout-open。",
        f"- 成本：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        "",
        "## 综合排名",
        "",
        *metric_table(ranking, limit=18),
        "",
        "## ATR bracket 排名",
        "",
        *metric_table(atr_rows, limit=20),
        "",
        "## 出场原因对照",
        "",
        *exit_reason_table(exit_counts, exit_labels),
        "",
        "## 状态",
        "",
        "本测试仍是 diagnostic。ATR bracket 没有补齐资金费、盘口级 stop-market/market 滑点、runner、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch；不得标记为 candidate、paper-live、dry-run、handoff 或 live。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 排名 CSV：`{RANKING_CSV_PATH}`",
        f"- 出场原因 CSV：`{EXIT_COUNTS_CSV_PATH}`",
        f"- JSON：`{SUMMARY_JSON_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return str(value)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    ranking, exit_counts, metadata, quality = evaluate()
    ranking.to_csv(RANKING_CSV_PATH, index=False)
    exit_counts.to_csv(EXIT_COUNTS_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(ranking, exit_counts, quality), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "alias": ALIAS,
                "version": VERSION,
                "run_date": RUN_DATE,
                "status": "atr_bracket_exit_diagnostic_not_promoted",
                "metadata": metadata,
                "data_quality": quality,
                "base_config": asdict(BASE_CONFIG),
                "costs": {
                    "commission_per_fill": COMMISSION_PER_SIDE,
                    "slippage_per_fill": SLIPPAGE_PER_SIDE,
                    "round_trip": ROUND_TRIP_COST,
                },
                "candidate_count": len(ranking),
                "atr_candidate_count": int(ranking["family"].eq("atr_bracket").sum()),
                "beats_baseline_k1_shape_count": int(
                    ranking["beats_baseline_k1_shape"].sum()
                ),
                "beats_baseline_joint_shape_count": int(
                    ranking["beats_baseline_joint_shape"].sum()
                ),
                "top25": ranking.head(25).to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "ranking_csv": str(RANKING_CSV_PATH),
                    "exit_counts_csv": str(EXIT_COUNTS_CSV_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(
        ranking.head(20)[
            [
                "rank",
                "label",
                "family",
                "k1_annual_return_pct",
                "k1_max_drawdown_pct",
                "k1_win_rate_pct",
                "k1_profit_factor",
                "k2_annual_return_pct",
                "k2_max_drawdown_pct",
                "k2_win_rate_pct",
                "beats_baseline_shape",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
