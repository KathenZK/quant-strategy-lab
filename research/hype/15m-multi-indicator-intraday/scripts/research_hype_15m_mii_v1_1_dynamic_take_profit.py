from __future__ import annotations

import json
import sys
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
    ExitSpec,
    build_market_arrays,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.1"
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = (
    FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_1_dynamic_take_profit.py"
)
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
RANKING_CSV_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_v1_1_dynamic_take_profit_ranking_2026-06-30.csv"
)
EXIT_COUNTS_CSV_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_v1_1_dynamic_take_profit_exit_counts_2026-06-30.csv"
)
SUMMARY_JSON_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_v1_1_dynamic_take_profit_2026-06-30.json"
)
MARKDOWN_PATH = (
    NOTES_DIR / "hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md"
)

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
class ExitCandidate:
    label: str
    family: str
    exit_spec: ExitSpec
    activation_pct: float | None = None
    trail_pct: float | None = None


def build_context() -> tuple[evolution.EvalContext, dict[str, Any], dict[str, Any]]:
    frame, metadata, quality = v1.load_data_lake()
    features = evolution.add_rsi_features(evolution.add_features(frame, []))
    context = evolution.EvalContext(
        features=features,
        market=build_market_arrays(features),
        start_ts=pd.Timestamp(features["ts"].min()),
        end_ts=pd.Timestamp(features["ts"].max()) + pd.Timedelta(minutes=15),
        signal_cache={},
        trade_cache={},
    )
    v1.engine.simulate_trades = v1.simulate_trades_live
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live
    return context, metadata, quality


def pct_slug(value: float) -> str:
    return f"{value * 10_000:g}".replace(".", "p")


def exit_candidates() -> list[ExitCandidate]:
    candidates = [
        ExitCandidate(
            label="baseline_fixed_tp120_sl360_hold16",
            family="fixed_baseline",
            exit_spec=BASE_CONFIG.exit,
        )
    ]
    for take_profit_pct, max_hold_bars in (
        (0.015, 16),
        (0.018, 16),
        (0.024, 24),
        (0.03, 32),
        (0.04, 48),
    ):
        candidates.append(
            ExitCandidate(
                label=(
                    f"fixed_context_tp{pct_slug(take_profit_pct)}_"
                    f"sl360_hold{max_hold_bars}"
                ),
                family="fixed_context",
                exit_spec=ExitSpec(
                    kind="fixed",
                    take_profit_pct=take_profit_pct,
                    stop_pct=BASE_CONFIG.stop_pct,
                    max_hold_bars=max_hold_bars,
                ),
            )
        )
    for activation_pct in (0.006, 0.009, 0.012, 0.015, 0.018, 0.024, 0.03, 0.04):
        for trail_pct in (0.003, 0.0045, 0.006, 0.009, 0.012, 0.018, 0.024):
            if trail_pct >= activation_pct and activation_pct <= 0.012:
                continue
            for max_hold_bars in (16, 24, 32, 48, 64, 96):
                candidates.append(
                    ExitCandidate(
                        label=(
                            f"trail_act{pct_slug(activation_pct)}_"
                            f"trail{pct_slug(trail_pct)}_sl360_hold{max_hold_bars}"
                        ),
                        family="dynamic_trailing",
                        exit_spec=ExitSpec(
                            kind="trailing",
                            activation_pct=activation_pct,
                            trail_pct=trail_pct,
                            stop_pct=BASE_CONFIG.stop_pct,
                            max_hold_bars=max_hold_bars,
                        ),
                        activation_pct=activation_pct,
                        trail_pct=trail_pct,
                    )
                )
    return candidates


def window_trades(
    trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[Any]:
    return [trade for trade in trades if start_ts <= trade.entry_ts < end_ts]


def evaluate_trades(
    *,
    context: evolution.EvalContext,
    trades: list[Any],
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


def selected_trades(
    trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[Any]:
    return v1.selected_trades_live(
        window_trades(trades, start_ts, end_ts),
        BASE_CONFIG.filter,
    )


def selected_stats(
    trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    picked = selected_trades(trades, start_ts, end_ts)
    net_returns = [
        BASE_CONFIG.exposure * (trade.raw_return - ROUND_TRIP_COST) * 100.0
        for trade in picked
    ]
    winners = [value for value in net_returns if value > 0]
    mfe_values = [
        BASE_CONFIG.exposure * max(trade.max_path_return, 0.0) * 100.0
        for trade in picked
    ]
    exit_counts: dict[str, int] = {}
    for trade in picked:
        exit_counts[trade.exit_reason] = exit_counts.get(trade.exit_reason, 0) + 1
    return {
        "avg_trade_pct": float(np.mean(net_returns)) if net_returns else 0.0,
        "median_trade_pct": float(np.median(net_returns)) if net_returns else 0.0,
        "avg_winner_pct": float(np.mean(winners)) if winners else 0.0,
        "best_trade_pct": float(np.max(net_returns)) if net_returns else 0.0,
        "worst_trade_pct": float(np.min(net_returns)) if net_returns else 0.0,
        "avg_mfe_pct": float(np.mean(mfe_values)) if mfe_values else 0.0,
        "avg_bars_held": float(np.mean([trade.bars_held for trade in picked]))
        if picked
        else 0.0,
        "exit_counts": exit_counts,
    }


def score_row(row: dict[str, Any]) -> float:
    k1_return = float(row["k1_annual_return_pct"])
    k2_return = float(row["k2_annual_return_pct"])
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
        0.25 * np.log1p(max(k1_return, -90.0) / 100.0)
        + 0.20 * np.log1p(max(k2_return, -90.0) / 100.0)
        + 0.18 * ((worst_drawdown + 60.0) / 60.0)
        + 0.16 * ((min_win - 65.0) / 30.0)
        + 0.13 * np.log1p(max(min_last90, -90.0) / 100.0)
        + 0.08 * min(float(row["k1_avg_bars_held"]) / 24.0, 1.0)
    )


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    context, metadata, quality = build_context()
    state = signal_state(context.features, BASE_CONFIG.signal)
    last90_start = max(context.start_ts, context.end_ts - pd.Timedelta(days=90))

    rows: list[dict[str, Any]] = []
    exit_count_rows: list[dict[str, Any]] = []
    candidates = exit_candidates()
    for index, candidate in enumerate(candidates, start=1):
        row: dict[str, Any] = {
            "label": candidate.label,
            "family": candidate.family,
            "exit_kind": candidate.exit_spec.kind,
            "take_profit_pct": candidate.exit_spec.take_profit_pct,
            "activation_pct": candidate.activation_pct,
            "trail_pct": candidate.trail_pct,
            "stop_pct": candidate.exit_spec.stop_pct,
            "max_hold_bars": candidate.exit_spec.max_hold_bars,
        }
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = v1.simulate_trades_live(
                context.market,
                state,
                candidate.exit_spec,
                entry_delay_bars=entry_delay_bars,
            )
            full = evaluate_trades(
                context=context,
                trades=trades,
                exit_spec=candidate.exit_spec,
                start_ts=context.start_ts,
                end_ts=context.end_ts,
            )
            last90 = evaluate_trades(
                context=context,
                trades=trades,
                exit_spec=candidate.exit_spec,
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
        row["beats_baseline_shape"] = False
        rows.append(row)
        if index % 50 == 0 or index == len(candidates):
            print(f"dynamic exits {index}/{len(candidates)}", flush=True)

    ranking = pd.DataFrame(rows)
    baseline = ranking.loc[ranking["family"].eq("fixed_baseline")].iloc[0]
    ranking["delta_k1_annual_return_pct"] = (
        ranking["k1_annual_return_pct"] - baseline["k1_annual_return_pct"]
    )
    ranking["delta_k1_max_drawdown_pct"] = (
        ranking["k1_max_drawdown_pct"] - baseline["k1_max_drawdown_pct"]
    )
    ranking["delta_k1_win_rate_pct"] = (
        ranking["k1_win_rate_pct"] - baseline["k1_win_rate_pct"]
    )
    ranking["delta_k2_annual_return_pct"] = (
        ranking["k2_annual_return_pct"] - baseline["k2_annual_return_pct"]
    )
    ranking["delta_k2_max_drawdown_pct"] = (
        ranking["k2_max_drawdown_pct"] - baseline["k2_max_drawdown_pct"]
    )
    ranking["beats_baseline_shape"] = (
        ranking["k1_annual_return_pct"].gt(baseline["k1_annual_return_pct"])
        & ranking["k1_max_drawdown_pct"].ge(baseline["k1_max_drawdown_pct"])
        & ranking["k1_win_rate_pct"].ge(baseline["k1_win_rate_pct"])
        & ranking["k2_annual_return_pct"].gt(0)
    )
    ranking = ranking.sort_values(
        ["beats_baseline_shape", "score"],
        ascending=False,
    ).reset_index(drop=True)
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    exit_counts = pd.DataFrame(exit_count_rows)
    return ranking, exit_counts, metadata, quality


def metric_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    lines = [
        "| 排名 | 标签 | 类型 | K+1 年化/回撤/胜率/PF | K+2 年化/回撤/胜率/PF | Last90 K+1/K+2 | 均持仓 | 最好/最差单笔 | Gate |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{int(row['rank'])}` | `{row['label']}` | `{row['family']}` | "
            f"`{row['k1_annual_return_pct']:.2f}% / {row['k1_max_drawdown_pct']:.2f}% / "
            f"{row['k1_win_rate_pct']:.2f}% / {row['k1_profit_factor']:.3f}` | "
            f"`{row['k2_annual_return_pct']:.2f}% / {row['k2_max_drawdown_pct']:.2f}% / "
            f"{row['k2_win_rate_pct']:.2f}% / {row['k2_profit_factor']:.3f}` | "
            f"`{row['k1_last90_annual_return_pct']:.2f}% / {row['k2_last90_annual_return_pct']:.2f}%` | "
            f"`{row['k1_avg_bars_held']:.2f}` | "
            f"`{row['k1_best_trade_pct']:.2f}% / {row['k1_worst_trade_pct']:.2f}%` | "
            f"`{bool(row['beats_baseline_shape'])}` |"
        )
    return lines


def exit_reason_table(exit_counts: pd.DataFrame, labels: list[str]) -> list[str]:
    lines = [
        "| 标签 | 入场 | take_profit | trailing_stop | stop_loss | gap stop | max_hold |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
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
                f"`{counts.get('trailing_stop', 0) + counts.get('trailing_gap', 0)}` | "
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
    dynamic = ranking.loc[ranking["family"].eq("dynamic_trailing")].copy()
    fixed_context = ranking.loc[ranking["family"].eq("fixed_context")].copy()
    best_dynamic = dynamic.iloc[0]
    best_k1_return = dynamic.sort_values(
        "k1_annual_return_pct",
        ascending=False,
    ).iloc[0]
    passed = dynamic.loc[dynamic["beats_baseline_shape"]]
    exit_labels = [
        str(baseline["label"]),
        str(best_dynamic["label"]),
        str(best_k1_return["label"]),
    ]
    exit_labels = list(dict.fromkeys(exit_labels))

    lines = [
        f"# HYPE-15M-MII V1.1 动态止盈测试 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        "这次只替换出场逻辑，保持 `HYPE-15M-MII-V1.1` 的 RSI/MACD/ATR/RVOL 信号过滤、`SL=3.60%`、`2x` 权益暴露和成本口径不变。动态止盈定义为：取消固定 `TP=1.20%`，达到 activation 浮盈后用 trailing stop 跟随利润。",
        "",
        (
            f"- 固定 TP baseline：K+1 年化 `{baseline['k1_annual_return_pct']:.2f}%`、"
            f"回撤 `{baseline['k1_max_drawdown_pct']:.2f}%`、胜率 `{baseline['k1_win_rate_pct']:.2f}%`、"
            f"PF `{baseline['k1_profit_factor']:.3f}`；K+2 年化 `{baseline['k2_annual_return_pct']:.2f}%`、"
            f"回撤 `{baseline['k2_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- 动态 trailing 综合第一：`{best_dynamic['label']}`，K+1 年化 "
            f"`{best_dynamic['k1_annual_return_pct']:.2f}%`、回撤 "
            f"`{best_dynamic['k1_max_drawdown_pct']:.2f}%`、胜率 "
            f"`{best_dynamic['k1_win_rate_pct']:.2f}%`；K+2 年化 "
            f"`{best_dynamic['k2_annual_return_pct']:.2f}%`、回撤 "
            f"`{best_dynamic['k2_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- 动态 trailing 最高 K+1 年化：`{best_k1_return['label']}`，K+1 年化 "
            f"`{best_k1_return['k1_annual_return_pct']:.2f}%`，但回撤 "
            f"`{best_k1_return['k1_max_drawdown_pct']:.2f}%`、K+2 回撤 "
            f"`{best_k1_return['k2_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- 同时超过 baseline 的动态 trailing 形状：`{len(passed)}/{len(dynamic)}`。"
            "本轮没有找到“更会让利润奔跑且不牺牲 V1.1 核心优势”的动态止盈。"
        ),
        "",
        "直觉上，V1.1 的 alpha 更像短促均值回归/反转窗口，不是趋势延伸窗口；固定 `1.20%` TP 虽然限制了单笔上限，但也正是高胜率和低持仓时长的来源。动态 trailing 让部分盈利单持有更久，可提高最好单笔，但更多交易会从小赢变成回吐或 timeout，K+2 稳健性也没有改善。",
        "",
        "## 参数与口径",
        "",
        f"- Version：`{VERSION}`。",
        f"- Engine name：`{BASE_CONFIG.name}`。",
        "- Baseline exit：固定 `TP=1.20%`、`SL=3.60%`、`hold=16`。",
        "- Dynamic exit grid：`activation_pct in 0.60%-4.00%`，`trail_pct in 0.30%-2.40%`，`hold in 16/24/32/48/64/96`，`SL=3.60%`。",
        "- Fixed context：额外测试更高固定 TP，用来区分“只是 TP 太小”还是“信号本身不适合奔跑”。",
        f"- 成本：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        "",
        "## 综合排名",
        "",
        *metric_table(ranking, limit=15),
        "",
        "## 动态 trailing 排名",
        "",
        *metric_table(dynamic, limit=15),
        "",
        "## 更高固定 TP 对照",
        "",
        *metric_table(fixed_context, limit=8),
        "",
        "## 出场原因对照",
        "",
        *exit_reason_table(exit_counts, exit_labels),
        "",
        "## 状态",
        "",
        "本测试仍是 diagnostic。动态止盈没有改善 `HYPE-15M-MII-V1.1` 的实盘前置缺口：资金费、盘口级 stop-market/market 滑点、runner、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch 仍未补齐；不得标记为 candidate、paper-live、dry-run、handoff 或 live。",
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
                "status": "dynamic_take_profit_diagnostic_not_promoted",
                "metadata": metadata,
                "data_quality": quality,
                "base_config": asdict(BASE_CONFIG),
                "costs": {
                    "commission_per_fill": COMMISSION_PER_SIDE,
                    "slippage_per_fill": SLIPPAGE_PER_SIDE,
                    "round_trip": ROUND_TRIP_COST,
                },
                "candidate_count": len(ranking),
                "dynamic_candidate_count": int(
                    ranking["family"].eq("dynamic_trailing").sum()
                ),
                "beats_baseline_shape_count": int(
                    ranking["beats_baseline_shape"].sum()
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
