from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import asdict
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
    build_market_arrays,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.1"
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = (
    FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_1_window_backtest.py"
)
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_1_window_backtest_2026-06-30.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_1_window_backtest_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-1-window-backtest-2026-06-30.md"

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

ACTIVE_PARAMETERS: dict[str, Any] = {
    "side": "both",
    "signal": "RSI(7) long cross above 40 / short cross below 60",
    "macd_periods": evolution.FIXED_MACD_PERIODS,
    "min_dir_macd": 0.0,
    "min_atr_pct96": BASE_CONFIG.min_atr_pct96,
    "max_atr_pct96": evolution.MAX_ATR_PCT_GUARDRAIL,
    "min_rvol96": BASE_CONFIG.min_rvol96,
    "exit_kind": "fixed",
    "take_profit_pct": BASE_CONFIG.take_profit_pct,
    "stop_pct": BASE_CONFIG.stop_pct,
    "max_hold_bars": BASE_CONFIG.max_hold_bars,
    "exposure": BASE_CONFIG.exposure,
    "entry_timing": "K+1 open",
    "stress_entry_timing": "K+2 open",
    "conflict_rule": "stop-first",
    "timeout_rule": "timeout-open",
    "commission_per_fill": COMMISSION_PER_SIDE,
    "slippage_per_fill": SLIPPAGE_PER_SIDE,
    "round_trip_cost": ROUND_TRIP_COST,
}

WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1周", pd.Timedelta(days=7)),
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("最近1年", pd.Timedelta(days=365)),
    ("全样本", None),
)
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))


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


def window_bounds(
    context: evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = context.end_ts
    start_ts = context.start_ts if duration is None else max(context.start_ts, end_ts - duration)
    return start_ts, end_ts


def selected_net_returns_pct(
    trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    window_trades = [
        trade for trade in trades if start_ts <= trade.entry_ts < end_ts
    ]
    selected = v1.selected_trades_live(window_trades, BASE_CONFIG.filter)
    return [
        float(BASE_CONFIG.exposure * (trade.raw_return - ROUND_TRIP_COST) * 100.0)
        for trade in selected
    ]


def evaluate() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    context, metadata, quality = build_context()
    state = signal_state(context.features, BASE_CONFIG.signal)

    rows: list[dict[str, Any]] = []
    for entry_delay_bars, entry_label in ENTRY_DELAYS:
        trades = v1.simulate_trades_live(
            context.market,
            state,
            BASE_CONFIG.exit,
            entry_delay_bars=entry_delay_bars,
        )
        for window_name, duration in WINDOWS:
            start_ts, end_ts = window_bounds(context, duration)
            metrics = evolution.evaluate_window(
                context,
                BASE_CONFIG,
                trades,
                start_ts,
                end_ts,
                purge_end=False,
            )
            net_returns = selected_net_returns_pct(trades, start_ts, end_ts)
            if int(metrics["trades"]) == 0:
                metrics = {
                    **metrics,
                    "annual_return_pct": 0.0,
                    "total_return_pct": 0.0,
                    "max_drawdown_pct": 0.0,
                    "win_rate_pct": 0.0,
                    "profit_factor": 0.0,
                }
            period_days = max((end_ts - start_ts).total_seconds() / 86400.0, 0.0)
            rows.append(
                {
                    "version": VERSION,
                    "engine_name": BASE_CONFIG.name,
                    "window": window_name,
                    "entry_timing": entry_label,
                    "entry_delay_bars": entry_delay_bars,
                    "start_ts": start_ts.isoformat(),
                    "end_ts": end_ts.isoformat(),
                    "period_days": period_days,
                    **asdict(BASE_CONFIG),
                    "annual_return_pct": float(metrics["annual_return_pct"]),
                    "total_return_pct": float(metrics["total_return_pct"]),
                    "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
                    "win_rate_pct": float(metrics["win_rate_pct"]),
                    "trades": int(metrics["trades"]),
                    "trades_per_day": float(metrics["trades_per_day"]),
                    "annualized_trades": float(metrics["trades_per_day"]) * 365.25,
                    "profit_factor": float(metrics["profit_factor"]),
                    "avg_trade_pct": float(np.mean(net_returns)) if net_returns else 0.0,
                    "median_trade_pct": float(np.median(net_returns)) if net_returns else 0.0,
                    "worst_trade_pct": float(np.min(net_returns)) if net_returns else 0.0,
                }
            )
    result = pd.DataFrame(rows)
    result["window_order"] = result["window"].map(
        {name: index for index, (name, _duration) in enumerate(WINDOWS)}
    )
    result = result.sort_values(["entry_delay_bars", "window_order"]).drop(
        columns=["window_order"]
    )
    return result.reset_index(drop=True), metadata, quality


def metric_table(rows: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = rows.loc[rows["entry_timing"].eq(entry_timing)]
    lines = [
        f"### {entry_timing}",
        "",
        "| 窗口 | 年化 | 总收益 | 最大回撤 | 胜率 | 交易数 | 笔/天 | PF | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | "
            f"`{row['annual_return_pct']:.2f}%` | "
            f"`{row['total_return_pct']:.2f}%` | "
            f"`{row['max_drawdown_pct']:.2f}%` | "
            f"`{row['win_rate_pct']:.2f}%` | "
            f"`{int(row['trades'])}` | "
            f"`{row['trades_per_day']:.3f}` | "
            f"`{row['profit_factor']:.3f}` | "
            f"`{row['avg_trade_pct']:.3f}%` | "
            f"`{row['worst_trade_pct']:.3f}%` |"
        )
    return lines


def row_lookup(rows: pd.DataFrame, window: str, entry_timing: str) -> pd.Series:
    selected = rows.loc[rows["window"].eq(window) & rows["entry_timing"].eq(entry_timing)]
    if selected.empty:
        raise ValueError(f"missing row window={window} entry={entry_timing}")
    return selected.iloc[0]


def render_markdown(rows: pd.DataFrame, quality: dict[str, Any]) -> str:
    k1_1m = row_lookup(rows, "最近1月", "K+1")
    k1_3m = row_lookup(rows, "最近3月", "K+1")
    k1_all = row_lookup(rows, "全样本", "K+1")
    k2_all = row_lookup(rows, "全样本", "K+2")

    lines = [
        f"# HYPE-15M-MII V1.1 分窗口回测 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        (
            "`HYPE-15M-MII-V1.1` 是 `HYPE-15M-MII-V1base` 的干净参数表达：只保留实际生效的"
            "信号、过滤、出场、执行和成本项，去掉未启用的 `1h confirm`、`RSI14 band`、ADX、H4、"
            "ret、churn、cooldown 等参数。策略行为与 `V1base` 相同。"
        ),
        "",
        (
            f"- K+1 全样本：年化 `{k1_all['annual_return_pct']:.2f}%`、总收益 "
            f"`{k1_all['total_return_pct']:.2f}%`、回撤 `{k1_all['max_drawdown_pct']:.2f}%`、"
            f"胜率 `{k1_all['win_rate_pct']:.2f}%`、交易 `{int(k1_all['trades'])}` 笔。"
        ),
        (
            f"- K+2 全样本：年化 `{k2_all['annual_return_pct']:.2f}%`、总收益 "
            f"`{k2_all['total_return_pct']:.2f}%`、回撤 `{k2_all['max_drawdown_pct']:.2f}%`、"
            f"胜率 `{k2_all['win_rate_pct']:.2f}%`；延迟后收益显著下降，回撤扩大。"
        ),
        (
            f"- 最近 1 周无交易；K+1 最近 1 月总收益 `{k1_1m['total_return_pct']:.2f}%`、"
            f"最近 3 月总收益 `{k1_3m['total_return_pct']:.2f}%`，近期窗口偏强；"
            "但短窗口年化会被样本长度放大。"
        ),
        "",
        "## V1.1 干净策略参数",
        "",
        f"- Version：`{VERSION}`。",
        f"- Engine name：`{BASE_CONFIG.name}`。",
        "- Signal：`RSI(7)` 上穿 `40` 做多，下穿 `60` 做空。",
        "- Filter：`side=both`；`MACD(12,26,9)` 方向过滤，`min_dir_macd=0.0`；`ATR96 pct` 在 `0.75%-2.80%`；`RVOL96 >= 1.0`。",
        "- Exit：固定 `TP=1.20%`、`SL=3.60%`、最长 `16` 根 `15m` K。",
        "- Exposure：`2x` 权益暴露。",
        "- Execution：K+1 open 入场；K+2 作为延迟压力；单仓不重叠；stop-first；timeout-open。",
        f"- Cost：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        "",
        "## 数据与质量",
        "",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`。",
        f"- Quality gate：`{quality['quality_gate_pass']}`；gap `{quality['gap_count']}`，duplicates normalized/raw `{quality['normalized_duplicates']}/{quality['raw_duplicates']}`，critical nulls `{quality['critical_nulls']}`，raw/normalized missing `{quality['raw_normalized_missing_rows']}`。",
        "",
        "## 分窗口结果",
        "",
    ]
    lines.extend(metric_table(rows, "K+1"))
    lines.append("")
    lines.extend(metric_table(rows, "K+2"))
    lines.extend(
        [
            "",
            "## 状态",
            "",
            "本回测仍是 diagnostic。`HYPE-15M-MII-V1.1` 去掉的是未启用参数的表达噪音，不是新的实盘审计结果；家族状态仍为 `NO-GO`。资金费、盘口级 stop-market/market 滑点、runner、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch 仍未补齐。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- CSV：`{CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(rows: pd.DataFrame, metadata: dict[str, Any], quality: dict[str, Any]) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_csv(CSV_PATH, index=False)
    summary = {
        "family": FAMILY,
        "alias": ALIAS,
        "version": VERSION,
        "run_date": RUN_DATE,
        "status": "v1_1_window_backtest_diagnostic_not_promoted",
        "metadata": metadata,
        "data_quality": quality,
        "active_parameters": ACTIVE_PARAMETERS,
        "base_config": asdict(BASE_CONFIG),
        "windows": rows.to_dict(orient="records"),
        "artifacts": {
            "script": str(SCRIPT_PATH),
            "csv": str(CSV_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    JSON_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(rows, quality), encoding="utf-8")


def main() -> None:
    rows, metadata, quality = evaluate()
    write_outputs(rows, metadata, quality)
    print(rows.to_string(index=False))
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
