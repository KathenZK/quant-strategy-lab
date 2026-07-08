from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import EventTrade, signal_state  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.3"
RUN_DATE = "2026-07-08"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_micro_tune.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
FULL_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_micro_tune_full_2026-07-08.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_micro_tune_windows_2026-07-08.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_micro_tune_rolling_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_micro_tune_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-micro-tune-2026-07-08.md"

V13_EXPOSURE = 2.5
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
FIXED_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("全样本", None),
)

RSI_PAIRS = ((40.0, 60.0), (35.0, 60.0), (40.0, 65.0), (35.0, 65.0), (45.0, 55.0), (45.0, 60.0), (40.0, 55.0))
MIN_ATR_VALUES = (0.0070, 0.0075)
MIN_RVOL_VALUES = (0.75, 0.9, 1.0)
EXIT_VARIANTS = (
    ("tp1p25_sl5_hold24", 1.25, 5.0, 24),
    ("tp1p5_sl5_hold24", 1.5, 5.0, 24),
    ("tp1p25_sl4_hold24", 1.25, 4.0, 24),
)

BASELINE_KEY = ("rsi40_60", 0.0075, 1.0, "tp1p25_sl5_hold24")


def rsi_label(low: float, high: float) -> str:
    return f"rsi{int(low)}_{int(high)}"


def config_label(rsi: str, min_atr: float, min_rvol: float, exit_label: str) -> str:
    return f"{rsi}_atr{int(round(min_atr * 10_000))}_rvol{min_rvol:g}_{exit_label}"


def finite(value: float, default: float) -> float:
    return float(value) if np.isfinite(value) else default


def simulate_atr_bracket_with_state(
    context: Any,
    state: Any,
    *,
    tp_atr_mult: float,
    sl_atr_mult: float,
    max_hold_bars: int,
    entry_delay_bars: int,
) -> list[EventTrade]:
    market = context.market
    atr_pct = context.features["atr_pct96"].to_numpy("float64")
    trades: list[EventTrade] = []
    n = len(market.open)
    for signal_idx, direction_value in zip(state.signal_i, state.directions, strict=False):
        signal_i = int(signal_idx)
        entry_i = signal_i + entry_delay_bars
        if entry_i >= n - 1:
            continue
        dynamic_atr_pct = float(atr_pct[signal_i])
        if not np.isfinite(dynamic_atr_pct) or dynamic_atr_pct <= 0:
            continue

        take_profit_pct = dynamic_atr_pct * tp_atr_mult
        stop_pct = dynamic_atr_pct * sl_atr_mult
        forced_exit_i = min(entry_i + max_hold_bars, n - 1)
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


def evaluate_metrics(
    *,
    trades: list[EventTrade],
    filter_spec: Any,
    exit_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades(trades, start_ts, end_ts),
        filter_spec=filter_spec,
        exposure=V13_EXPOSURE,
        period_days=period_days,
        exit_spec=exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    empty = {
        "annual_return_pct": 0.0,
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": 0.0,
        "trades": 0,
        "trades_per_day": 0.0,
        "profit_factor": 0.0,
    }
    if result is None:
        return empty
    metrics = asdict(result)
    if int(metrics["trades"]) == 0:
        metrics.update(empty)
    return metrics


def net_returns_pct(
    trades: list[EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    picked = v1.selected_trades_live(window_trades(trades, start_ts, end_ts), filter_spec)
    return [
        float(V13_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
        for trade in picked
    ]


def rolling_stats(
    context: Any,
    trades: list[EventTrade],
    filter_spec: Any,
    exit_spec: Any,
    *,
    config_name: str,
    entry_label: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for days in (30, 90):
        duration = pd.Timedelta(days=days)
        step = pd.Timedelta(days=7)
        left = context.start_ts
        returns: list[float] = []
        drawdowns: list[float] = []
        zero_trade = 0
        while left + duration <= context.end_ts:
            metrics = evaluate_metrics(
                trades=trades,
                filter_spec=filter_spec,
                exit_spec=exit_spec,
                start_ts=left,
                end_ts=left + duration,
            )
            returns.append(float(metrics["total_return_pct"]))
            drawdowns.append(float(metrics["max_drawdown_pct"]))
            if int(metrics["trades"]) == 0:
                zero_trade += 1
            left += step
        arr = np.array(returns)
        rows.append(
            {
                "config": config_name,
                "entry": entry_label,
                "days": days,
                "slices": int(len(arr)),
                "positive": int((arr > 0).sum()),
                "median_ret": float(np.median(arr)) if len(arr) else 0.0,
                "worst_ret": float(arr.min()) if len(arr) else 0.0,
                "median_dd": float(np.median(drawdowns)) if drawdowns else 0.0,
                "worst_dd": float(min(drawdowns)) if drawdowns else 0.0,
                "zero_trade": zero_trade,
            }
        )
    return rows


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    context, metadata, quality = v12.build_context()
    exit_spec = v12.candidate_exit_spec(
        v12.AtrBracketCandidate(
            label="atr96_generic",
            family="atr_bracket",
            atr_window=96,
            tp_atr_mult=1.25,
            sl_atr_mult=5.0,
            max_hold_bars=24,
        )
    )

    states: dict[str, Any] = {}
    for low, high in RSI_PAIRS:
        config = replace(v12.BASE_CONFIG, rsi_low=low, rsi_high=high)
        states[rsi_label(low, high)] = signal_state(context.features, config.signal)

    raw_trade_cache: dict[tuple[str, str, str], list[EventTrade]] = {}
    for low, high in RSI_PAIRS:
        rsi = rsi_label(low, high)
        for exit_label, tp_mult, sl_mult, hold in EXIT_VARIANTS:
            for entry_delay_bars, entry_label in ENTRY_DELAYS:
                raw_trade_cache[(rsi, exit_label, entry_label)] = simulate_atr_bracket_with_state(
                    context,
                    states[rsi],
                    tp_atr_mult=tp_mult,
                    sl_atr_mult=sl_mult,
                    max_hold_bars=hold,
                    entry_delay_bars=entry_delay_bars,
                )

    full_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for low, high in RSI_PAIRS:
        rsi = rsi_label(low, high)
        for min_atr in MIN_ATR_VALUES:
            for min_rvol in MIN_RVOL_VALUES:
                filter_spec = replace(
                    v12.BASE_CONFIG.filter,
                    min_atr_pct96=min_atr,
                    min_rvol96=min_rvol,
                )
                for exit_label, _tp, _sl, _hold in EXIT_VARIANTS:
                    label = config_label(rsi, min_atr, min_rvol, exit_label)
                    is_baseline = (rsi, min_atr, min_rvol, exit_label) == BASELINE_KEY
                    for entry_delay_bars, entry_label in ENTRY_DELAYS:
                        trades = raw_trade_cache[(rsi, exit_label, entry_label)]
                        for window_name, duration in FIXED_WINDOWS:
                            end_ts = context.end_ts
                            start_ts = (
                                context.start_ts
                                if duration is None
                                else max(context.start_ts, end_ts - duration)
                            )
                            metrics = evaluate_metrics(
                                trades=trades,
                                filter_spec=filter_spec,
                                exit_spec=exit_spec,
                                start_ts=start_ts,
                                end_ts=end_ts,
                            )
                            returns = net_returns_pct(trades, filter_spec, start_ts, end_ts)
                            row = {
                                "label": label,
                                "is_baseline": is_baseline,
                                "rsi_low": low,
                                "rsi_high": high,
                                "min_atr_bps": int(round(min_atr * 10_000)),
                                "min_rvol96": min_rvol,
                                "exit_variant": exit_label,
                                "entry_timing": entry_label,
                                "window": window_name,
                                "trades": int(metrics["trades"]),
                                "total_return_pct": float(metrics["total_return_pct"]),
                                "annual_return_pct": float(metrics["annual_return_pct"]),
                                "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
                                "win_rate_pct": float(metrics["win_rate_pct"]),
                                "profit_factor": float(metrics["profit_factor"]),
                                "avg_trade_pct": float(np.mean(returns)) if returns else 0.0,
                                "worst_trade_pct": float(np.min(returns)) if returns else 0.0,
                            }
                            if window_name == "全样本":
                                full_rows.append(row)
                            else:
                                window_rows.append(row)

    full = pd.DataFrame(full_rows)
    windows = pd.DataFrame(window_rows)

    k1 = full.loc[full["entry_timing"].eq("K+1")].set_index("label")
    k2 = full.loc[full["entry_timing"].eq("K+2")].set_index("label")
    baseline_label = config_label("rsi40_60", 0.0075, 1.0, "tp1p25_sl5_hold24")
    base_k1 = k1.loc[baseline_label]
    base_k2 = k2.loc[baseline_label]

    merged = k1.join(k2, lsuffix="_k1", rsuffix="_k2")
    merged["pass_strict_gate"] = (
        (merged["trades_k1"] > int(base_k1["trades"]))
        & (merged["win_rate_pct_k1"] >= float(base_k1["win_rate_pct"]))
        & (merged["total_return_pct_k1"] > float(base_k1["total_return_pct"]))
        & (merged["max_drawdown_pct_k1"] >= float(base_k1["max_drawdown_pct"]))
        & (merged["total_return_pct_k2"] >= float(base_k2["total_return_pct"]))
        & (merged["max_drawdown_pct_k2"] >= float(base_k2["max_drawdown_pct"]))
    )
    merged["pass_relaxed_gate"] = (
        (merged["trades_k1"] > int(base_k1["trades"]))
        & (merged["win_rate_pct_k1"] >= float(base_k1["win_rate_pct"]) - 1.0)
        & (merged["total_return_pct_k1"] > float(base_k1["total_return_pct"]))
        & (merged["max_drawdown_pct_k1"] >= float(base_k1["max_drawdown_pct"]) - 3.0)
        & (merged["total_return_pct_k2"] >= float(base_k2["total_return_pct"]) * 0.9)
    )

    strict_count = int(merged["pass_strict_gate"].sum())
    relaxed = merged.loc[merged["pass_relaxed_gate"]].sort_values(
        "total_return_pct_k1", ascending=False
    )

    top_by_return = merged.sort_values("total_return_pct_k1", ascending=False).head(12)

    rolling_rows: list[dict[str, Any]] = []
    rolling_targets = {
        "baseline_rvol1.0": v12.BASE_CONFIG.filter,
        "cand_rvol0.9": replace(v12.BASE_CONFIG.filter, min_rvol96=0.9),
    }
    for entry_delay_bars, entry_label in ENTRY_DELAYS:
        trades = raw_trade_cache[("rsi40_60", "tp1p25_sl5_hold24", entry_label)]
        for config_name, filter_spec in rolling_targets.items():
            rolling_rows.extend(
                rolling_stats(
                    context,
                    trades,
                    filter_spec,
                    exit_spec,
                    config_name=config_name,
                    entry_label=entry_label,
                )
            )
    rolling = pd.DataFrame(rolling_rows)

    full.to_csv(FULL_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)

    def fmt(value: float, digits: int = 2) -> str:
        return f"{value:.{digits}f}"

    def merged_table(frame: pd.DataFrame) -> list[str]:
        lines = [
            "| 配置 | K+1 笔 | K+1 收益 | K+1 回撤 | K+1 胜率 | K+1 PF | K+2 收益 | K+2 回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for label, row in frame.iterrows():
            marker = " (baseline)" if label == baseline_label else ""
            lines.append(
                f"| `{label}`{marker} | `{int(row['trades_k1'])}` | `{fmt(row['total_return_pct_k1'])}%` | "
                f"`{fmt(row['max_drawdown_pct_k1'])}%` | `{fmt(row['win_rate_pct_k1'])}%` | "
                f"`{fmt(row['profit_factor_k1'], 3)}` | `{fmt(row['total_return_pct_k2'])}%` | "
                f"`{fmt(row['max_drawdown_pct_k2'])}%` |"
            )
        return lines

    more_trades = merged.loc[merged["trades_k1"] > int(base_k1["trades"])]
    more_trades_best = more_trades.sort_values("total_return_pct_k1", ascending=False).head(10)

    lines = [
        f"# HYPE-15M-MII V1.3 提频微调网格 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 设定",
        "",
        "保持 `V1.3` 的 MACD 方向过滤、ATR bracket 出场结构、单仓状态机、Binance fee `0.001`/fill、slippage `4 bps`/fill 和 `2.5x` 权益暴露不变，扫描：",
        "",
        f"- RSI 反转阈值：`{', '.join(f'{int(a)}/{int(b)}' for a, b in RSI_PAIRS)}`",
        f"- `min_atr_pct96`：`{', '.join(f'{int(v*10_000)} bps' for v in MIN_ATR_VALUES)}`",
        f"- `min_rvol96`：`{', '.join(f'{v:g}' for v in MIN_RVOL_VALUES)}`",
        f"- 出场：`{', '.join(label for label, *_ in EXIT_VARIANTS)}`（注意：不同 TP/SL 只影响模拟路径，评估统一用 ATR bracket 语义）",
        f"- 共 `{len(RSI_PAIRS) * len(MIN_ATR_VALUES) * len(MIN_RVOL_VALUES) * len(EXIT_VARIANTS)}` 个配置，K+1 主口径 + K+2 延迟压力。",
        "",
        "## 联合 gate 结果",
        "",
        (
            f"严格 gate（K+1 笔数更多、胜率不降、收益更高、回撤不更差，且 K+2 收益/回撤不更差）："
            f"`{strict_count}/{len(merged)}` 通过。"
        ),
        (
            f"放宽 gate（胜率容忍 `-1pp`、回撤容忍 `-3pp`、K+2 收益容忍 `-10%`）："
            f"`{len(relaxed)}/{len(merged)}` 通过。"
        ),
        "",
        "## 基线",
        "",
        *merged_table(merged.loc[[baseline_label]]),
        "",
        "## 放宽 gate 通过配置" if len(relaxed) else "## 放宽 gate 无通过配置",
        "",
    ]
    if len(relaxed):
        lines.extend(merged_table(relaxed.head(10)))
        lines.append("")

    lines.extend(
        [
            "## 候选 `rvol0.9` 滚动窗口对比",
            "",
            "| 配置 | 入场 | 窗口 | 正收益切片 | 中位收益 | 最差收益 | 中位回撤 | 最差回撤 | 零交易切片 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling.to_dict(orient="records"):
        lines.append(
            f"| `{row['config']}` | `{row['entry']}` | `{row['days']}d` | "
            f"`{int(row['positive'])}/{int(row['slices'])}` | `{fmt(row['median_ret'])}%` | "
            f"`{fmt(row['worst_ret'])}%` | `{fmt(row['median_dd'])}%` | "
            f"`{fmt(row['worst_dd'])}%` | `{int(row['zero_trade'])}` |"
        )
    lines.append("")
    lines.extend(
        [
            "## 交易数超过基线的前 10 名（按 K+1 收益）",
            "",
            *merged_table(more_trades_best),
            "",
            "## K+1 收益前 12 名（不限笔数）",
            "",
            *merged_table(top_by_return),
            "",
            "## 数据质量",
            "",
            f"- Standard data lake：`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`，quality gate `{quality['quality_gate_pass']}`。",
            "",
            "## 状态",
            "",
            "本诊断为同样本参数微调，不改变 `V1.3` 的 `NO-GO / not live-ready` 状态。任何被选中的配置都必须先经过 OOS/纸面观察、资金费与滑点审计，才可讨论替换 baseline。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 全样本 CSV：`{FULL_CSV_PATH}`",
            f"- 分窗口 CSV：`{WINDOW_CSV_PATH}`",
            f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    MARKDOWN_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

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

    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "micro_tune_diagnostic_not_promoted",
                    "metadata": metadata,
                    "data_quality": quality,
                    "baseline_label": baseline_label,
                    "strict_gate_pass": strict_count,
                    "relaxed_gate_pass": int(len(relaxed)),
                    "rolling": rolling.to_dict(orient="records"),
                    "grid": {
                        "rsi_pairs": RSI_PAIRS,
                        "min_atr_values": MIN_ATR_VALUES,
                        "min_rvol_values": MIN_RVOL_VALUES,
                        "exit_variants": [label for label, *_ in EXIT_VARIANTS],
                    },
                    "merged": merged.reset_index().to_dict(orient="records"),
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"strict gate pass: {strict_count}/{len(merged)}")
    print(f"relaxed gate pass: {len(relaxed)}/{len(merged)}")
    print("baseline:")
    print(merged.loc[[baseline_label], ["trades_k1", "total_return_pct_k1", "max_drawdown_pct_k1", "win_rate_pct_k1", "total_return_pct_k2", "max_drawdown_pct_k2"]].to_string())
    if len(relaxed):
        print("relaxed gate top:")
        print(relaxed[["trades_k1", "total_return_pct_k1", "max_drawdown_pct_k1", "win_rate_pct_k1", "total_return_pct_k2", "max_drawdown_pct_k2"]].head(10).to_string())
    print("more trades top by K+1 return:")
    print(more_trades_best[["trades_k1", "total_return_pct_k1", "max_drawdown_pct_k1", "win_rate_pct_k1", "profit_factor_k1", "total_return_pct_k2", "max_drawdown_pct_k2"]].to_string())
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
