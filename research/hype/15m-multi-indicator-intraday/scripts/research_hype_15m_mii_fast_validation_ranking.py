from __future__ import annotations

import json
import math
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
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_fast_validation_ranking.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
SOURCE_RANKING_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_ranking_2026-06-29.csv"
RANKING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_fast_validation_ranking_2026-06-30.csv"
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_fast_validation_ranking_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-fast-validation-frequency-ranking-2026-06-30.md"


def bool_value(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes"}


def config_from_row(row: pd.Series) -> evolution.CleanConfig:
    return evolution.CleanConfig(
        rsi_window=int(row["rsi_window"]),
        rsi_low=float(row["rsi_low"]),
        rsi_high=float(row["rsi_high"]),
        min_atr_pct96=float(row["min_atr_pct96"]),
        min_rvol96=float(row["min_rvol96"]),
        h1_confirm=bool_value(row["h1_confirm"]),
        rsi14_band=bool_value(row["rsi14_band"]),
        take_profit_pct=float(row["take_profit_pct"]),
        stop_pct=float(row["stop_pct"]),
        max_hold_bars=int(row["max_hold_bars"]),
        exposure=float(row["exposure"]),
    )


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def return_score(value: float, cap: float = 150.0) -> float:
    if value <= 0:
        return 0.0
    return clamp(math.log1p(value / 100.0) / math.log1p(cap / 100.0))


def frequency_score(value: float) -> float:
    if 1.0 <= value <= 3.0:
        return 1.0
    if 0.85 <= value < 1.0:
        return 0.72 + 0.28 * (value - 0.85) / 0.15
    if 3.0 < value <= 3.5:
        return 1.0 - 0.5 * (value - 3.0) / 0.5
    return 0.0


def drawdown_score(value: float) -> float:
    # value is negative. -15% or better is excellent; -45% or worse is rejected.
    return clamp((value + 45.0) / 30.0)


def win_score(value: float) -> float:
    return clamp((value - 65.0) / 25.0)


def recent_score(value: float) -> float:
    return clamp((value + 30.0) / 130.0)


def k1_pre_score(row: pd.Series) -> float:
    return (
        0.28 * return_score(float(row["annual_return_pct"]))
        + 0.28 * frequency_score(float(row["trades_per_day"]))
        + 0.18 * drawdown_score(float(row["max_drawdown_pct"]))
        + 0.14 * win_score(float(row["win_rate_pct"]))
        + 0.12
        * min(
            recent_score(float(row["last90_annual_return_pct"])),
            recent_score(float(row["second_half_annual_return_pct"])),
        )
    )


def final_score(row: pd.Series) -> float:
    worst_dd = min(
        float(row["k1_max_drawdown_pct"]),
        float(row["k2_max_drawdown_pct"]),
    )
    min_win = min(float(row["k1_win_rate_pct"]), float(row["k2_win_rate_pct"]))
    min_recent = min(
        float(row["k1_last90_annual_return_pct"]),
        float(row["k2_last90_annual_return_pct"]),
    )
    min_return = min(
        float(row["k1_annual_return_pct"]),
        float(row["k2_annual_return_pct"]),
    )
    strict_frequency_bonus = 0.04 if float(row["k1_trades_per_day"]) >= 1.0 else 0.0
    return (
        0.25 * return_score(float(row["k1_annual_return_pct"]), cap=180.0)
        + 0.13 * return_score(min_return, cap=120.0)
        + 0.24 * frequency_score(float(row["k1_trades_per_day"]))
        + 0.16 * drawdown_score(worst_dd)
        + 0.12 * win_score(min_win)
        + 0.10 * recent_score(min_recent)
        + strict_frequency_bonus
    )


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


def evaluate_k2(
    context: evolution.EvalContext,
    config: evolution.CleanConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = signal_state(context.features, config.signal)
    trades = v1.simulate_trades_live(
        context.market,
        state,
        config.exit,
        entry_delay_bars=2,
    )
    full = evolution.evaluate_window(
        context,
        config,
        trades,
        context.start_ts,
        context.end_ts,
        purge_end=False,
    )
    last90 = evolution.evaluate_window(
        context,
        config,
        trades,
        max(context.start_ts, context.end_ts - pd.Timedelta(days=90)),
        context.end_ts,
        purge_end=False,
    )
    return full, last90


def candidate_pool(source: pd.DataFrame) -> pd.DataFrame:
    broad = source.loc[
        source["trades_per_day"].between(0.85, 3.0)
        & source["win_rate_pct"].ge(65.0)
        & source["max_drawdown_pct"].ge(-45.0)
        & source["annual_return_pct"].gt(-25.0)
    ].copy()
    if broad.empty:
        return broad
    broad["pre_score"] = broad.apply(k1_pre_score, axis=1)
    strict = broad.loc[broad["trades_per_day"].between(1.0, 3.0)]
    near = broad.loc[broad["trades_per_day"].between(0.85, 1.0)]
    selected = pd.concat(
        [
            broad.sort_values("pre_score", ascending=False).head(80),
            strict.sort_values("annual_return_pct", ascending=False).head(35),
            strict.sort_values("last90_annual_return_pct", ascending=False).head(35),
            near.sort_values("annual_return_pct", ascending=False).head(35),
            near.sort_values("last90_annual_return_pct", ascending=False).head(35),
        ],
        ignore_index=True,
    )
    return selected.drop_duplicates("name").reset_index(drop=True)


def evaluate() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    source = pd.read_csv(SOURCE_RANKING_PATH)
    context, metadata, quality = build_context()
    pool = candidate_pool(source)
    rows: list[dict[str, Any]] = []
    for index, row in pool.iterrows():
        config = config_from_row(row)
        k2, k2_last90 = evaluate_k2(context, config)
        rows.append(
            {
                "name": row["name"],
                **asdict(config),
                "k1_annual_return_pct": float(row["annual_return_pct"]),
                "k1_max_drawdown_pct": float(row["max_drawdown_pct"]),
                "k1_win_rate_pct": float(row["win_rate_pct"]),
                "k1_trades": int(row["trades"]),
                "k1_trades_per_day": float(row["trades_per_day"]),
                "k1_profit_factor": float(row["profit_factor"]),
                "k1_second_half_annual_return_pct": float(
                    row["second_half_annual_return_pct"]
                ),
                "k1_last90_annual_return_pct": float(
                    row["last90_annual_return_pct"]
                ),
                "k2_annual_return_pct": float(k2["annual_return_pct"]),
                "k2_max_drawdown_pct": float(k2["max_drawdown_pct"]),
                "k2_win_rate_pct": float(k2["win_rate_pct"]),
                "k2_trades": int(k2["trades"]),
                "k2_trades_per_day": float(k2["trades_per_day"]),
                "k2_profit_factor": float(k2["profit_factor"]),
                "k2_last90_annual_return_pct": float(k2_last90["annual_return_pct"]),
            }
        )
        if (index + 1) % 25 == 0 or index + 1 == len(pool):
            print(f"fast-validation k2 {index + 1}/{len(pool)}", flush=True)
    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking, metadata, quality
    ranking["strict_1_to_3_per_day"] = ranking["k1_trades_per_day"].between(1.0, 3.0)
    ranking["near_1_per_day"] = ranking["k1_trades_per_day"].between(0.85, 1.0)
    ranking["fast_validation_gate"] = (
        ranking["k1_annual_return_pct"].gt(30.0)
        & ranking["k2_annual_return_pct"].gt(0.0)
        & ranking["k1_max_drawdown_pct"].ge(-30.0)
        & ranking["k2_max_drawdown_pct"].ge(-35.0)
        & ranking["k1_win_rate_pct"].ge(70.0)
        & ranking["k2_win_rate_pct"].ge(70.0)
        & ranking["k1_trades_per_day"].between(0.85, 3.0)
        & ranking["k1_last90_annual_return_pct"].gt(0.0)
        & ranking["k2_last90_annual_return_pct"].gt(0.0)
    )
    ranking["score"] = ranking.apply(final_score, axis=1)
    ranking = ranking.sort_values(
        ["fast_validation_gate", "score"],
        ascending=False,
    ).reset_index(drop=True)
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    return ranking, metadata, quality


def table(rows: pd.DataFrame, limit: int = 10) -> list[str]:
    lines = [
        "| 排名 | 名称 | 分数 | K+1 年化/回撤/胜率/频率 | K+2 年化/回撤/胜率 | Last90 K+1/K+2 | Gate |",
        "| ---: | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{int(row['rank'])}` | `{row['name']}` | `{row['score']:.3f}` | "
            f"`{row['k1_annual_return_pct']:.2f}% / {row['k1_max_drawdown_pct']:.2f}% / "
            f"{row['k1_win_rate_pct']:.2f}% / {row['k1_trades_per_day']:.3f}` | "
            f"`{row['k2_annual_return_pct']:.2f}% / {row['k2_max_drawdown_pct']:.2f}% / "
            f"{row['k2_win_rate_pct']:.2f}%` | "
            f"`{row['k1_last90_annual_return_pct']:.2f}% / {row['k2_last90_annual_return_pct']:.2f}%` | "
            f"`{bool(row['fast_validation_gate'])}` |"
        )
    return lines


def render_markdown(
    ranking: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    strict = ranking.loc[ranking["strict_1_to_3_per_day"]]
    near = ranking.loc[ranking["near_1_per_day"]]
    passed = ranking.loc[ranking["fast_validation_gate"]]
    best = ranking.iloc[0] if not ranking.empty else None
    strict_best = strict.iloc[0] if not strict.empty else None

    lines = [
        f"# HYPE-15M-MII 快速验证频率综合排名 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "## 结论",
        "",
        "本轮不是寻找最高收益，而是为了小额实盘快速验证，把频率权重提高，同时保留收益、回撤、胜率、Last90 和 K+2 延迟惩罚。",
        "",
        f"- 输入池：`{len(ranking)}`；严格 `1-3` 笔/天：`{len(strict)}`；接近 `0.85-1` 笔/天：`{len(near)}`；快速验证 gate 通过：`{len(passed)}`。",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        f"- 成本：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        "",
    ]
    if best is not None:
        lines.extend(
            [
                (
                    f"- 综合第一：`{best['name']}`，K+1 年化 "
                    f"`{best['k1_annual_return_pct']:.2f}%`、回撤 "
                    f"`{best['k1_max_drawdown_pct']:.2f}%`、胜率 "
                    f"`{best['k1_win_rate_pct']:.2f}%`、频率 "
                    f"`{best['k1_trades_per_day']:.3f}` 笔/天；K+2 年化 "
                    f"`{best['k2_annual_return_pct']:.2f}%`。"
                ),
            ]
        )
    if strict_best is not None:
        lines.extend(
            [
                (
                    f"- 严格 `>=1` 笔/天第一：`{strict_best['name']}`，K+1 年化 "
                    f"`{strict_best['k1_annual_return_pct']:.2f}%`，但 K+2 年化 "
                    f"`{strict_best['k2_annual_return_pct']:.2f}%`、K+1 Last90 "
                    f"`{strict_best['k1_last90_annual_return_pct']:.2f}%`。"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## 综合排名",
            "",
            *table(ranking, limit=15),
            "",
            "## 严格 `1-3` 笔/天子榜",
            "",
            *table(strict, limit=12),
            "",
            "## 接近 `1` 笔/天子榜",
            "",
            *table(near, limit=12),
            "",
            "## 评分口径",
            "",
            "- 收益：K+1 年化和 K+1/K+2 较小年化都计分，避免只靠单一入场点。",
            "- 频率：`1-3` 笔/天满分；`0.85-1` 笔/天按接近程度给分。",
            "- 回撤：使用 K+1/K+2 更差的回撤计分。",
            "- 胜率：使用 K+1/K+2 较低胜率计分。",
            "- 稳定性：使用 K+1/K+2 较低 Last90 计分。",
            "",
            "## 状态",
            "",
            "本排名只用于小额实盘前的快速验证优先级，不是 promotion。所有配置仍缺资金费、盘口级 stop-market、真实成交滑点、runner、重启恢复、对账和 kill switch。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- CSV：`{RANKING_CSV_PATH}`",
            f"- JSON：`{SUMMARY_JSON_PATH}`",
        ]
    )
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
    ranking, metadata, quality = evaluate()
    ranking.to_csv(RANKING_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(ranking, quality), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "run_date": RUN_DATE,
                "status": "fast_validation_frequency_ranking_not_promoted",
                "metadata": metadata,
                "data_quality": quality,
                "costs": {
                    "commission_per_fill": COMMISSION_PER_SIDE,
                    "slippage_per_fill": SLIPPAGE_PER_SIDE,
                    "round_trip": ROUND_TRIP_COST,
                },
                "ranked_count": len(ranking),
                "strict_1_to_3_count": int(ranking["strict_1_to_3_per_day"].sum())
                if not ranking.empty
                else 0,
                "fast_validation_gate_count": int(
                    ranking["fast_validation_gate"].sum()
                )
                if not ranking.empty
                else 0,
                "top25": ranking.head(25).to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "ranking_csv": str(RANKING_CSV_PATH),
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
                "name",
                "score",
                "k1_annual_return_pct",
                "k1_max_drawdown_pct",
                "k1_win_rate_pct",
                "k1_trades_per_day",
                "k2_annual_return_pct",
                "k2_max_drawdown_pct",
                "k2_win_rate_pct",
                "k1_last90_annual_return_pct",
                "k2_last90_annual_return_pct",
                "fast_validation_gate",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
