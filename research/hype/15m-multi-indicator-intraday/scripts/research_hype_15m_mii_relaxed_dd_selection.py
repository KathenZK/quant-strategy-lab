from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import asdict, replace
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
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_relaxed_dd_selection.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SOURCE_RANKING_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_ranking_2026-06-29.csv"
LADDER_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_relaxed_dd_exposure_ladder_2026-06-30.csv"
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_relaxed_dd_selection_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md"

EXPOSURES = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0)


def base_configs() -> dict[str, evolution.CleanConfig]:
    return {
        "dd25_top": evolution.CleanConfig(
            rsi_window=7,
            rsi_low=40.0,
            rsi_high=60.0,
            min_atr_pct96=0.0075,
            min_rvol96=0.75,
            take_profit_pct=0.012,
            stop_pct=0.045,
            max_hold_bars=16,
            exposure=1.0,
        ),
        "score_top": evolution.CleanConfig(
            rsi_window=7,
            rsi_low=40.0,
            rsi_high=55.0,
            min_atr_pct96=0.0075,
            min_rvol96=1.0,
            take_profit_pct=0.012,
            stop_pct=0.045,
            max_hold_bars=16,
            exposure=1.0,
        ),
        "dd30_high_win": evolution.CleanConfig(
            rsi_window=7,
            rsi_low=40.0,
            rsi_high=60.0,
            min_atr_pct96=0.0075,
            min_rvol96=0.5,
            take_profit_pct=0.012,
            stop_pct=0.045,
            max_hold_bars=48,
            exposure=1.0,
        ),
        "delay_high_win": evolution.CleanConfig(
            rsi_window=9,
            rsi_low=40.0,
            rsi_high=60.0,
            min_atr_pct96=0.0075,
            min_rvol96=0.75,
            take_profit_pct=0.009,
            stop_pct=0.045,
            max_hold_bars=32,
            exposure=1.0,
        ),
        "delay_balanced": evolution.CleanConfig(
            rsi_window=7,
            rsi_low=40.0,
            rsi_high=60.0,
            min_atr_pct96=0.009,
            min_rvol96=0.0,
            take_profit_pct=0.012,
            stop_pct=0.045,
            max_hold_bars=32,
            exposure=1.0,
        ),
    }


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


def metrics_for(
    context: evolution.EvalContext,
    config: evolution.CleanConfig,
    trades: list[Any],
) -> dict[str, Any]:
    return evolution.evaluate_window(
        context,
        config,
        trades,
        context.start_ts,
        context.end_ts,
        purge_end=False,
    )


def evaluate_exposure_ladder(context: evolution.EvalContext) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, base_config in base_configs().items():
        state = signal_state(context.features, base_config.signal)
        k1_trades = v1.simulate_trades_live(
            context.market,
            state,
            base_config.exit,
            entry_delay_bars=1,
        )
        k2_trades = v1.simulate_trades_live(
            context.market,
            state,
            base_config.exit,
            entry_delay_bars=2,
        )
        for exposure in EXPOSURES:
            config = replace(base_config, exposure=exposure)
            k1 = metrics_for(context, config, k1_trades)
            k2 = metrics_for(context, config, k2_trades)
            last90 = evolution.evaluate_window(
                context,
                config,
                k1_trades,
                max(context.start_ts, context.end_ts - pd.Timedelta(days=90)),
                context.end_ts,
                purge_end=False,
            )
            rows.append(
                {
                    "family": label,
                    "name": config.name,
                    **asdict(config),
                    "k1_annual_return_pct": k1["annual_return_pct"],
                    "k1_max_drawdown_pct": k1["max_drawdown_pct"],
                    "k1_win_rate_pct": k1["win_rate_pct"],
                    "k1_trades_per_day": k1["trades_per_day"],
                    "k1_profit_factor": k1["profit_factor"],
                    "k1_last90_annual_return_pct": last90["annual_return_pct"],
                    "k2_annual_return_pct": k2["annual_return_pct"],
                    "k2_max_drawdown_pct": k2["max_drawdown_pct"],
                    "k2_win_rate_pct": k2["win_rate_pct"],
                    "k2_trades_per_day": k2["trades_per_day"],
                    "k2_profit_factor": k2["profit_factor"],
                }
            )
    return pd.DataFrame(rows)


def historical_tier(ranking: pd.DataFrame, max_dd: float, limit: int = 10) -> pd.DataFrame:
    return (
        ranking.loc[
            ranking["max_drawdown_pct"].ge(-max_dd)
            & ranking["win_rate_pct"].ge(75.0)
            & ranking["second_half_annual_return_pct"].gt(0)
            & ranking["last90_annual_return_pct"].gt(0)
        ]
        .sort_values("annual_return_pct", ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def ladder_tier(ladder: pd.DataFrame, max_dd: float, limit: int = 10) -> pd.DataFrame:
    return (
        ladder.loc[
            ladder["k1_max_drawdown_pct"].ge(-max_dd)
            & ladder["k1_win_rate_pct"].ge(75.0)
            & ladder["k1_last90_annual_return_pct"].gt(0)
        ]
        .sort_values("k1_annual_return_pct", ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def delay_tier(ladder: pd.DataFrame, max_dd: float, limit: int = 10) -> pd.DataFrame:
    frame = ladder.loc[
        ladder["k1_max_drawdown_pct"].ge(-max_dd)
        & ladder["k2_max_drawdown_pct"].ge(-max_dd)
        & ladder["k1_win_rate_pct"].ge(75.0)
        & ladder["k2_win_rate_pct"].ge(75.0)
        & ladder["k2_annual_return_pct"].gt(50.0)
        & ladder["k1_last90_annual_return_pct"].gt(0)
    ].copy()
    frame["min_k1_k2_annual_return_pct"] = frame[
        ["k1_annual_return_pct", "k2_annual_return_pct"]
    ].min(axis=1)
    return (
        frame.sort_values(
            ["min_k1_k2_annual_return_pct", "k1_win_rate_pct"],
            ascending=False,
        )
        .head(limit)
        .reset_index(drop=True)
    )


def table(rows: pd.DataFrame, columns: list[tuple[str, str]], limit: int = 10) -> list[str]:
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        values: list[str] = []
        for _, column in columns:
            value = row[column]
            if isinstance(value, (float, np.floating)):
                if column.endswith("_pct") or "return" in column or "drawdown" in column:
                    values.append(f"`{value:.2f}%`")
                else:
                    values.append(f"`{value:.3f}`")
            else:
                values.append(f"`{value}`")
        lines.append("| " + " | ".join(values) + " |")
    return lines


def render_markdown(
    ranking: pd.DataFrame,
    ladder: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    dd25 = historical_tier(ranking, 25.0)
    dd30 = historical_tier(ranking, 30.0)
    ladder35 = ladder_tier(ladder, 35.0)
    delay30 = delay_tier(ladder, 30.0)
    delay35 = delay_tier(ladder, 35.0)
    best_dd25 = dd25.iloc[0]
    best_dd30 = dd30.iloc[0]
    best_ladder35 = ladder35.iloc[0]
    best_delay = delay30.iloc[0] if not delay30.empty else delay35.iloc[0]

    hist_cols = [
        ("名称", "name"),
        ("年化", "annual_return_pct"),
        ("回撤", "max_drawdown_pct"),
        ("胜率", "win_rate_pct"),
        ("笔/日", "trades_per_day"),
        ("PF", "profit_factor"),
        ("Last90", "last90_annual_return_pct"),
    ]
    ladder_cols = [
        ("组", "family"),
        ("名称", "name"),
        ("K+1 年化", "k1_annual_return_pct"),
        ("K+1 回撤", "k1_max_drawdown_pct"),
        ("K+1 胜率", "k1_win_rate_pct"),
        ("K+2 年化", "k2_annual_return_pct"),
        ("K+2 回撤", "k2_max_drawdown_pct"),
        ("K+2 胜率", "k2_win_rate_pct"),
    ]

    lines = [
        f"# HYPE-15M-MII 放宽回撤高收益选择 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "## 结论",
        "",
        (
            "有，但只能记录为 diagnostic。按新成本 `0.1000% fee/fill + "
            "0.0400% slippage/fill`、round-trip `0.2800%`，放宽回撤后可以找到 "
            "`300%+` 年化和 `80%+` 胜率的 K+1 版本；但这些高收益版本对 K+2 "
            "延迟非常敏感，不能作为实盘候选。"
        ),
        "",
        (
            f"- `DD<=25%` 历史排名首位：`{best_dd25['name']}`，年化 "
            f"`{best_dd25['annual_return_pct']:.2f}%`，回撤 "
            f"`{best_dd25['max_drawdown_pct']:.2f}%`，胜率 "
            f"`{best_dd25['win_rate_pct']:.2f}%`。"
        ),
        (
            f"- `DD<=30%` 历史排名首位：`{best_dd30['name']}`，年化 "
            f"`{best_dd30['annual_return_pct']:.2f}%`，回撤 "
            f"`{best_dd30['max_drawdown_pct']:.2f}%`，胜率 "
            f"`{best_dd30['win_rate_pct']:.2f}%`；但 Last90 只有 "
            f"`{best_dd30['last90_annual_return_pct']:.2f}%`，近期稳定性很薄。"
        ),
        (
            f"- 暴露阶梯 `DD<=35%` 最高：`{best_ladder35['name']}`，K+1 年化 "
            f"`{best_ladder35['k1_annual_return_pct']:.2f}%`，回撤 "
            f"`{best_ladder35['k1_max_drawdown_pct']:.2f}%`，胜率 "
            f"`{best_ladder35['k1_win_rate_pct']:.2f}%`；但 K+2 回撤 "
            f"`{best_ladder35['k2_max_drawdown_pct']:.2f}%`，应视为过度激进。"
        ),
        (
            f"- K+1/K+2 都在放宽回撤内的高胜率代表：`{best_delay['name']}`，"
            f"K+1 年化 `{best_delay['k1_annual_return_pct']:.2f}%` / 回撤 "
            f"`{best_delay['k1_max_drawdown_pct']:.2f}%` / 胜率 "
            f"`{best_delay['k1_win_rate_pct']:.2f}%`；K+2 年化 "
            f"`{best_delay['k2_annual_return_pct']:.2f}%` / 回撤 "
            f"`{best_delay['k2_max_drawdown_pct']:.2f}%` / 胜率 "
            f"`{best_delay['k2_win_rate_pct']:.2f}%`。"
        ),
        "",
        "## 数据与口径",
        "",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        f"- 成本：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        "- 执行：闭合 K 信号、K+1 open 入场、单仓不重叠、stop-first、timeout-open；K+2 只作为成交延迟压力。",
        "",
        "## `DD<=25%` Top",
        "",
        *table(dd25, hist_cols, limit=10),
        "",
        "## `DD<=30%` Top",
        "",
        *table(dd30, hist_cols, limit=10),
        "",
        "## 暴露阶梯 `DD<=35%` Top",
        "",
        *table(ladder35, ladder_cols, limit=12),
        "",
        "## K+1/K+2 同时放宽回撤 Top",
        "",
        *table(delay35, ladder_cols, limit=12),
        "",
        "## 状态判断",
        "",
        "- 若只追求样本内 K+1，`DD<=25%` 首位最值得继续追踪；若接受 `DD<=30%`，高胜率首位收益更高但 Last90 太薄。",
        "- 若要求 K+2 延迟也能站住，应牺牲收益，优先看 K+1/K+2 同时放宽回撤表。",
        "- 这些结果都不是 untouched OOS；没有资金费、盘口级 stop-market、真实成交滑点、runner、重启恢复、对账和 kill switch，因此不能标记为 candidate、paper-live、dry-run、handoff 或 live。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 暴露阶梯 CSV：`{LADDER_CSV_PATH}`",
        f"- JSON：`{SUMMARY_JSON_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return str(value)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    ranking = pd.read_csv(SOURCE_RANKING_PATH)
    context, metadata, quality = build_context()
    ladder = evaluate_exposure_ladder(context)

    dd25 = historical_tier(ranking, 25.0)
    dd30 = historical_tier(ranking, 30.0)
    ladder35 = ladder_tier(ladder, 35.0)
    delay30 = delay_tier(ladder, 30.0)
    delay35 = delay_tier(ladder, 35.0)

    ladder.to_csv(LADDER_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(ranking, ladder, quality), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "run_date": RUN_DATE,
                "status": "relaxed_drawdown_diagnostic_selection_not_promoted",
                "metadata": metadata,
                "data_quality": quality,
                "costs": {
                    "commission_per_fill": COMMISSION_PER_SIDE,
                    "slippage_per_fill": SLIPPAGE_PER_SIDE,
                    "round_trip": ROUND_TRIP_COST,
                },
                "best_dd25": dd25.iloc[0].to_dict(),
                "best_dd30": dd30.iloc[0].to_dict(),
                "best_ladder_dd35": ladder35.iloc[0].to_dict(),
                "best_delay_dd30": (
                    delay30.iloc[0].to_dict() if not delay30.empty else None
                ),
                "best_delay_dd35": delay35.iloc[0].to_dict(),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "ladder_csv": str(LADDER_CSV_PATH),
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
        dd25.head(5)[
            [
                "name",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades_per_day",
                "last90_annual_return_pct",
            ]
        ].to_string(index=False)
    )
    print(
        delay35.head(5)[
            [
                "family",
                "name",
                "k1_annual_return_pct",
                "k1_max_drawdown_pct",
                "k1_win_rate_pct",
                "k2_annual_return_pct",
                "k2_max_drawdown_pct",
                "k2_win_rate_pct",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
