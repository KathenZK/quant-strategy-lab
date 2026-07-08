from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.2"
RUN_DATE = "2026-07-01"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_2_atr_dynamic_leverage.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_dynamic_leverage_2026-07-01.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_dynamic_leverage_windows_2026-07-01.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_dynamic_leverage_2026-07-01.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-2-atr-dynamic-leverage-2026-07-01.md"

V12_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1周", pd.Timedelta(days=7)),
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("最近1年", pd.Timedelta(days=365)),
    ("全样本", None),
)
MIN_LEVERAGE = 2.0
MAX_LEVERAGE = 3.0
MIN_ATR_PCT96 = v12.BASE_CONFIG.filter.min_atr_pct96
MAX_ATR_PCT96 = v12.BASE_CONFIG.filter.max_atr_pct96


def dynamic_leverage(atr_pct96: float) -> float:
    if not np.isfinite(atr_pct96):
        return MIN_LEVERAGE
    if MAX_ATR_PCT96 <= MIN_ATR_PCT96:
        return MIN_LEVERAGE
    normalized = (float(atr_pct96) - MIN_ATR_PCT96) / (MAX_ATR_PCT96 - MIN_ATR_PCT96)
    leverage = MAX_LEVERAGE - normalized * (MAX_LEVERAGE - MIN_LEVERAGE)
    return float(np.clip(leverage, MIN_LEVERAGE, MAX_LEVERAGE))


def leverage_for_variant(variant: str, trade: v12.EventTrade) -> float:
    if variant == "fixed_2x":
        return 2.0
    if variant == "fixed_2p5x":
        return 2.5
    if variant == "fixed_3x":
        return 3.0
    if variant == "atr_dynamic_2x_3x":
        return dynamic_leverage(float(trade.atr_pct96))
    raise ValueError(f"unknown leverage variant: {variant}")


def window_bounds(
    context: v12.evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = context.end_ts
    start_ts = context.start_ts if duration is None else max(context.start_ts, end_ts - duration)
    return start_ts, end_ts


def window_trades(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return [trade for trade in trades if start_ts <= trade.entry_ts < end_ts]


def selected_trades(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return v1.selected_trades_live(
        window_trades(trades, start_ts, end_ts),
        v12.BASE_CONFIG.filter,
    )


def net_returns(
    trades: list[v12.EventTrade],
    variant: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> tuple[list[float], list[float], list[float]]:
    picked = selected_trades(trades, start_ts, end_ts)
    returns: list[float] = []
    min_mark_returns: list[float] = []
    leverages: list[float] = []
    for trade in picked:
        leverage = leverage_for_variant(variant, trade)
        leverages.append(leverage)
        returns.append(float(leverage * (trade.raw_return - v12.ROUND_TRIP_COST)))
        min_mark_returns.append(float(leverage * (trade.min_path_return - v12.ROUND_TRIP_COST)))
    return returns, min_mark_returns, leverages


def equity_metrics(
    returns: list[float],
    min_mark_returns: list[float],
    period_days: float,
) -> dict[str, float | int]:
    if not returns:
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
        }
    array = np.array(returns, dtype="float64")
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for net_return, min_mark_return in zip(array, min_mark_returns, strict=False):
        mark_equity = equity * max(0.0, 1.0 + float(min_mark_return))
        if peak > 0:
            max_drawdown = min(max_drawdown, mark_equity / peak - 1.0)
        equity *= max(0.0, 1.0 + float(net_return))
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
    total_return = float(equity - 1.0)
    annual_return = float((1.0 + total_return) ** (365.25 / max(period_days, 1.0)) - 1.0)
    wins = array[array > 0]
    losses = array[array < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    trades_per_year = len(array) / max(period_days, 1.0) * 365.25
    if len(array) >= 2 and np.std(array, ddof=1) > 0:
        sharpe = float(np.mean(array) / np.std(array, ddof=1) * np.sqrt(trades_per_year))
    else:
        sharpe = 0.0
    if len(losses) >= 2 and np.std(losses, ddof=1) > 0:
        sortino = float(np.mean(array) / np.std(losses, ddof=1) * np.sqrt(trades_per_year))
    else:
        sortino = 0.0
    return {
        "annual_return_pct": annual_return * 100.0,
        "annual_equity_multiple": 1.0 + annual_return,
        "total_return_pct": total_return * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "win_rate_pct": float(len(wins) / len(array) * 100.0),
        "trades": int(len(array)),
        "trades_per_day": float(len(array) / max(period_days, 1.0)),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "trade_sharpe": sharpe,
        "trade_sortino": sortino,
        "calmar": float(annual_return / abs(max_drawdown)) if max_drawdown < 0 else 0.0,
        "avg_trade_pct": float(np.mean(array) * 100.0),
        "median_trade_pct": float(np.median(array) * 100.0),
        "best_trade_pct": float(np.max(array) * 100.0),
        "worst_trade_pct": float(np.min(array) * 100.0),
    }


def leverage_stats(leverages: list[float]) -> dict[str, float]:
    if not leverages:
        return {
            "avg_leverage": 0.0,
            "median_leverage": 0.0,
            "min_leverage": 0.0,
            "max_leverage": 0.0,
        }
    array = np.array(leverages, dtype="float64")
    return {
        "avg_leverage": float(np.mean(array)),
        "median_leverage": float(np.median(array)),
        "min_leverage": float(np.min(array)),
        "max_leverage": float(np.max(array)),
    }


def evaluate_row(
    *,
    trades: list[v12.EventTrade],
    variant: str,
    description: str,
    entry_label: str,
    entry_delay_bars: int,
    window_name: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400.0, 0.0)
    returns, min_mark_returns, leverages = net_returns(trades, variant, start_ts, end_ts)
    metrics = equity_metrics(returns, min_mark_returns, period_days)
    return {
        "version": VERSION,
        "exit_label": V12_CANDIDATE.label,
        "variant": variant,
        "description": description,
        "entry_timing": entry_label,
        "entry_delay_bars": entry_delay_bars,
        "window": window_name,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": period_days,
        "min_atr_pct96": MIN_ATR_PCT96,
        "max_atr_pct96": MAX_ATR_PCT96,
        "min_leverage_rule": MIN_LEVERAGE,
        "max_leverage_rule": MAX_LEVERAGE,
        **metrics,
        **leverage_stats(leverages),
    }


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def summary_table(rows: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = rows.loc[rows["entry_timing"].eq(entry_timing)].copy()
    order = {"fixed_2x": 0, "fixed_2p5x": 1, "fixed_3x": 2, "atr_dynamic_2x_3x": 3}
    subset["order"] = subset["variant"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {entry_timing} 全样本",
        "",
        "| 变体 | 交易数 | 平均杠杆 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | Sharpe | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{int(row['trades'])}` | `{fmt(row['avg_leverage'], 3)}x` | "
            f"`{fmt(row['total_return_pct'])}%` | `{fmt(row['annual_return_pct'])}%` | "
            f"`{fmt(row['max_drawdown_pct'])}%` | `{fmt(row['win_rate_pct'])}%` | "
            f"`{fmt(row['profit_factor'], 3)}` | `{fmt(row['trade_sharpe'])}` | "
            f"`{fmt(row['avg_trade_pct'], 3)}%` | `{fmt(row['worst_trade_pct'], 3)}%` |"
        )
    return lines


def windows_table(rows: pd.DataFrame, variant: str, entry_timing: str) -> list[str]:
    subset = rows.loc[
        rows["variant"].eq(variant) & rows["entry_timing"].eq(entry_timing)
    ].copy()
    order = {name: index for index, (name, _duration) in enumerate(WINDOWS)}
    subset["order"] = subset["window"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {variant} / {entry_timing}",
        "",
        "| 窗口 | 交易数 | 平均杠杆 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | Sharpe |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{fmt(row['avg_leverage'], 3)}x` | "
            f"`{fmt(row['total_return_pct'])}%` | `{fmt(row['annual_return_pct'])}%` | "
            f"`{fmt(row['max_drawdown_pct'])}%` | `{fmt(row['win_rate_pct'])}%` | "
            f"`{fmt(row['profit_factor'], 3)}` | `{fmt(row['trade_sharpe'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, windows: pd.DataFrame, quality: dict[str, Any]) -> str:
    base_k1 = summary.loc[
        summary["variant"].eq("fixed_2x") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    fixed25_k1 = summary.loc[
        summary["variant"].eq("fixed_2p5x") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    fixed3_k1 = summary.loc[
        summary["variant"].eq("fixed_3x") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    dyn_k1 = summary.loc[
        summary["variant"].eq("atr_dynamic_2x_3x") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    base_k2 = summary.loc[
        summary["variant"].eq("fixed_2x") & summary["entry_timing"].eq("K+2")
    ].iloc[0]
    fixed25_k2 = summary.loc[
        summary["variant"].eq("fixed_2p5x") & summary["entry_timing"].eq("K+2")
    ].iloc[0]
    fixed3_k2 = summary.loc[
        summary["variant"].eq("fixed_3x") & summary["entry_timing"].eq("K+2")
    ].iloc[0]
    dyn_k2 = summary.loc[
        summary["variant"].eq("atr_dynamic_2x_3x") & summary["entry_timing"].eq("K+2")
    ].iloc[0]
    lines = [
        f"# HYPE-15M-MII V1.2 ATR 动态杠杆回测 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        (
            "`ATR dynamic leverage` 只改变权益暴露，不改变 `V1.2` 的 RSI/MACD/ATR/RVOL 入场过滤、"
            "ATR bracket 出场、成本、单仓状态机或 K+1/K+2 时序。"
        ),
        "",
        (
            f"- 动态杠杆规则：`ATR96 <= {MIN_ATR_PCT96:.2%}` 取 `{MAX_LEVERAGE:.1f}x`，"
            f"`ATR96 >= {MAX_ATR_PCT96:.2%}` 取 `{MIN_LEVERAGE:.1f}x`，中间线性插值并 clip 到 "
            f"`[{MIN_LEVERAGE:.1f}x, {MAX_LEVERAGE:.1f}x]`。"
        ),
        (
            f"- K+1：固定 `2x` 总收益 `{fmt(base_k1['total_return_pct'])}%`、回撤 "
            f"`{fmt(base_k1['max_drawdown_pct'])}%`；固定 `2.5x` 总收益 "
            f"`{fmt(fixed25_k1['total_return_pct'])}%`、回撤 `{fmt(fixed25_k1['max_drawdown_pct'])}%`；"
            f"固定 `3x` 总收益 "
            f"`{fmt(fixed3_k1['total_return_pct'])}%`、回撤 `{fmt(fixed3_k1['max_drawdown_pct'])}%`；"
            f"动态杠杆平均 `{fmt(dyn_k1['avg_leverage'], 3)}x`，总收益 "
            f"`{fmt(dyn_k1['total_return_pct'])}%`、回撤 `{fmt(dyn_k1['max_drawdown_pct'])}%`。"
        ),
        (
            f"- K+2：固定 `2x` 总收益 `{fmt(base_k2['total_return_pct'])}%`、回撤 "
            f"`{fmt(base_k2['max_drawdown_pct'])}%`；固定 `2.5x` 总收益 "
            f"`{fmt(fixed25_k2['total_return_pct'])}%`、回撤 `{fmt(fixed25_k2['max_drawdown_pct'])}%`；"
            f"固定 `3x` 总收益 "
            f"`{fmt(fixed3_k2['total_return_pct'])}%`、回撤 `{fmt(fixed3_k2['max_drawdown_pct'])}%`；"
            f"动态杠杆平均 `{fmt(dyn_k2['avg_leverage'], 3)}x`，总收益 "
            f"`{fmt(dyn_k2['total_return_pct'])}%`、回撤 `{fmt(dyn_k2['max_drawdown_pct'])}%`。"
        ),
        "",
        "相对固定 `3x`，ATR 动态杠杆确实降低了回撤，但也降低了收益；因为样本内通过过滤的交易大多 ATR 接近下限，动态杠杆平均仍接近 `2.89x`。",
        "",
        "状态：这是杠杆层诊断，不改变 `HYPE-15M-MII-V1.2` 的 `NO-GO / not live-ready` 状态。",
        "",
        "## 数据质量",
        "",
        f"- 覆盖：`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`，quality gate `{quality['quality_gate_pass']}`。",
        "",
        "## 全样本对比",
        "",
    ]
    lines.extend(summary_table(summary, "K+1"))
    lines.append("")
    lines.extend(summary_table(summary, "K+2"))
    lines.extend(["", "## 固定窗口明细", ""])
    for variant in ("fixed_2x", "fixed_2p5x", "fixed_3x", "atr_dynamic_2x_3x"):
        lines.extend(windows_table(windows, variant, "K+1"))
        lines.append("")
        lines.extend(windows_table(windows, variant, "K+2"))
        lines.append("")
    lines.extend(
        [
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- 窗口 CSV：`{WINDOW_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
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
    context, metadata, quality = v12.build_context()
    variants = [
        ("fixed_2x", "原 V1.2 固定 2x 权益暴露"),
        ("fixed_2p5x", "固定 2.5x 权益暴露对照"),
        ("fixed_3x", "固定 3x 权益暴露对照"),
        ("atr_dynamic_2x_3x", "ATR96 越低杠杆越高，2x-3x 线性动态权益暴露"),
    ]
    summary_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for entry_delay_bars, entry_label in ENTRY_DELAYS:
        trades = v12.simulate_atr_bracket_trades(context, V12_CANDIDATE, entry_delay_bars)
        for variant, description in variants:
            summary_rows.append(
                evaluate_row(
                    trades=trades,
                    variant=variant,
                    description=description,
                    entry_label=entry_label,
                    entry_delay_bars=entry_delay_bars,
                    window_name="全样本",
                    start_ts=context.start_ts,
                    end_ts=context.end_ts,
                )
            )
            for window_name, duration in WINDOWS:
                start_ts, end_ts = window_bounds(context, duration)
                window_rows.append(
                    evaluate_row(
                        trades=trades,
                        variant=variant,
                        description=description,
                        entry_label=entry_label,
                        entry_delay_bars=entry_delay_bars,
                        window_name=window_name,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )

    summary = pd.DataFrame(summary_rows)
    windows = pd.DataFrame(window_rows)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    payload = {
        "family": FAMILY,
        "alias": ALIAS,
        "version": VERSION,
        "run_date": RUN_DATE,
        "status": "atr_dynamic_leverage_diagnostic_not_promoted",
        "metadata": metadata,
        "data_quality": quality,
        "base_config": asdict(v12.BASE_CONFIG),
        "v12_exit": asdict(V12_CANDIDATE),
        "leverage_rule": {
            "type": "inverse_linear_by_signal_atr_pct96",
            "min_atr_pct96": MIN_ATR_PCT96,
            "max_atr_pct96": MAX_ATR_PCT96,
            "min_leverage": MIN_LEVERAGE,
            "max_leverage": MAX_LEVERAGE,
            "formula": (
                "leverage = clip(max_leverage - (atr_pct96 - min_atr_pct96) "
                "/ (max_atr_pct96 - min_atr_pct96) * (max_leverage - min_leverage), "
                "min_leverage, max_leverage)"
            ),
        },
        "summary": summary.to_dict(orient="records"),
        "outputs": {
            "script": str(SCRIPT_PATH),
            "summary_csv": str(SUMMARY_CSV_PATH),
            "window_csv": str(WINDOW_CSV_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    JSON_PATH.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(summary, windows, quality), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote {SUMMARY_CSV_PATH}")
    print(f"Wrote {WINDOW_CSV_PATH}")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
