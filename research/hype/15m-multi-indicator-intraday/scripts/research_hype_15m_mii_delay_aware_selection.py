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
import research_hype_15m_mii_v11_lead_robustness as robustness  # noqa: E402
from research_hype_15m_mii_search import build_market_arrays, signal_state  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
RUN_DATE = "2026-06-29"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_delay_aware_selection.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SOURCE_RANKING_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_ranking_2026-06-29.csv"
RANKING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_delay_aware_ranking_2026-06-29.csv"
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_delay_aware_selection_2026-06-29.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-delay-aware-selection-2026-06-29.md"
SELECTED = robustness.LEAD


def bool_value(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes"}


def config_from_row(row: Any) -> evolution.CleanConfig:
    return evolution.CleanConfig(
        rsi_window=int(row.rsi_window),
        rsi_low=float(row.rsi_low),
        rsi_high=float(row.rsi_high),
        min_atr_pct96=float(row.min_atr_pct96),
        min_rvol96=float(row.min_rvol96),
        h1_confirm=bool_value(row.h1_confirm),
        rsi14_band=bool_value(row.rsi14_band),
        take_profit_pct=float(row.take_profit_pct),
        stop_pct=float(row.stop_pct),
        max_hold_bars=int(row.max_hold_bars),
        exposure=float(row.exposure),
    )


def joint_score(row: Any, k2: dict[str, Any]) -> float:
    k1_log = math.log(max(0.01, 1.0 + float(row.annual_return_pct) / 100.0))
    k2_log = math.log(max(0.01, 1.0 + float(k2["annual_return_pct"]) / 100.0))
    return (
        3.0 * min(k1_log, k2_log)
        + 0.04 * min(float(row.win_rate_pct), float(k2["win_rate_pct"]))
        + 0.08 * min(float(row.max_drawdown_pct), float(k2["max_drawdown_pct"]))
        + 0.5
        * math.log(
            max(0.05, min(float(row.profit_factor), float(k2["profit_factor"])))
        )
    )


def evaluate() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    source = pd.read_csv(SOURCE_RANKING_PATH)
    feasible = source.loc[
        source["risk_feasible"].map(bool_value)
    ].copy()
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
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live
    delayed_trade_cache: OrderedDict[tuple[str, str], list[Any]] = OrderedDict()
    rows: list[dict[str, Any]] = []
    for index, source_row in enumerate(feasible.itertuples(index=False), start=1):
        config = config_from_row(source_row)
        key = (config.signal.name, config.exit.name)
        if key not in delayed_trade_cache:
            if config.signal.name not in context.signal_cache:
                context.signal_cache[config.signal.name] = signal_state(
                    features,
                    config.signal,
                )
            delayed_trade_cache[key] = v1.simulate_trades_live(
                context.market,
                context.signal_cache[config.signal.name],
                config.exit,
                entry_delay_bars=2,
            )
            delayed_trade_cache.move_to_end(key)
            while len(delayed_trade_cache) > 256:
                delayed_trade_cache.popitem(last=False)
        trades = delayed_trade_cache[key]
        k2 = evolution.evaluate_window(
            context,
            config,
            trades,
            context.start_ts,
            context.end_ts,
            purge_end=False,
        )
        k2_last90 = evolution.evaluate_window(
            context,
            config,
            trades,
            max(context.start_ts, context.end_ts - pd.Timedelta(days=90)),
            context.end_ts,
            purge_end=False,
        )
        row = {
            "name": config.name,
            **asdict(config),
            "k1_annual_return_pct": float(source_row.annual_return_pct),
            "k1_max_drawdown_pct": float(source_row.max_drawdown_pct),
            "k1_win_rate_pct": float(source_row.win_rate_pct),
            "k1_trades": int(source_row.trades),
            "k1_trades_per_day": float(source_row.trades_per_day),
            "k1_profit_factor": float(source_row.profit_factor),
            "k1_last90_annual_return_pct": float(
                source_row.last90_annual_return_pct
            ),
            "k2_annual_return_pct": float(k2["annual_return_pct"]),
            "k2_max_drawdown_pct": float(k2["max_drawdown_pct"]),
            "k2_win_rate_pct": float(k2["win_rate_pct"]),
            "k2_trades": int(k2["trades"]),
            "k2_trades_per_day": float(k2["trades_per_day"]),
            "k2_profit_factor": float(k2["profit_factor"]),
            "k2_last90_annual_return_pct": float(k2_last90["annual_return_pct"]),
        }
        row["delay_joint_gate"] = bool(
            row["k2_annual_return_pct"] >= 100.0
            and row["k2_max_drawdown_pct"] >= -20.0
            and row["k2_win_rate_pct"] >= 70.0
            and row["k2_trades_per_day"] >= 0.5
            and row["k2_last90_annual_return_pct"] > 0
        )
        row["frequency_preferred"] = bool(
            0.75 <= row["k1_trades_per_day"] <= 2.0
            and 0.75 <= row["k2_trades_per_day"] <= 2.0
        )
        row["joint_score"] = joint_score(source_row, k2)
        rows.append(row)
        if index % 100 == 0 or index == len(feasible):
            print(f"delay-aware {index}/{len(feasible)}", flush=True)
    ranking = pd.DataFrame(rows).sort_values(
        ["delay_joint_gate", "joint_score"],
        ascending=False,
    ).reset_index(drop=True)
    ranking["joint_rank"] = np.arange(1, len(ranking) + 1)
    return ranking, metadata, quality


def table(rows: pd.DataFrame, limit: int = 20) -> list[str]:
    lines = [
        "| 排名 | 名称 | K+1 年化/回撤/胜率/频率 | K+2 年化/回撤/胜率/频率 | K+2 Last90 |",
        "| ---: | --- | --- | --- | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{int(row['joint_rank'])}` | `{row['name']}` | "
            f"`{row['k1_annual_return_pct']:.2f}% / {row['k1_max_drawdown_pct']:.2f}% / "
            f"{row['k1_win_rate_pct']:.2f}% / {row['k1_trades_per_day']:.3f}` | "
            f"`{row['k2_annual_return_pct']:.2f}% / {row['k2_max_drawdown_pct']:.2f}% / "
            f"{row['k2_win_rate_pct']:.2f}% / {row['k2_trades_per_day']:.3f}` | "
            f"`{row['k2_last90_annual_return_pct']:.2f}%` |"
        )
    return lines


def render_markdown(
    ranking: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    passed = ranking.loc[ranking["delay_joint_gate"]]
    frequency = passed.loc[passed["frequency_preferred"]]
    selected = ranking.loc[ranking["name"].eq(SELECTED.name)].iloc[0]
    top_for_display = passed if not passed.empty else ranking
    selection_note = (
        "该版本通过 K+2 联合 gate；仍未满足每天 1-2 笔偏好，且后续仍需要成本、邻域和 live-feasibility 复核。"
        if bool(selected["delay_joint_gate"])
        else "该版本只是 K+1 收益领先的诊断对象，没有通过 K+2 联合 gate；K+2 延迟下回撤和胜率退化明显，不能作为稳健版本。"
    )
    lines = [
        f"# HYPE-15M-MII K+2 延迟联合筛选 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "## 结论",
        "",
        "本轮读取 clean evolution 的全部 risk-feasible 结果，并保持原参数不变，把入场从 K+1 open 推迟到 K+2 open。联合 gate 要求 K+2 年化、回撤、胜率、频率和 Last90 同时合格。",
        "",
        f"- 输入 risk-feasible：`{len(ranking)}`；K+2 联合通过：`{len(passed)}`；其中 K+1/K+2 都达到 `>=0.75` 笔/天：`{len(frequency)}`。",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        f"- 被复核的 K+1 领先诊断对象联合排名：`{int(selected['joint_rank'])}`；该排名不代表通过 K+2 gate。",
        "",
        "## 被复核对象",
        "",
        *table(pd.DataFrame([selected]), limit=1),
        "",
        selection_note,
        "",
        "## 联合排名 Top",
        "",
        *table(top_for_display, limit=20),
        "",
        "## 高频偏好子集 Top",
        "",
        *table(frequency, limit=15),
        "",
        "## 状态",
        "",
        "本轮没有任何配置通过 K+2 联合 gate。K+2 压力只用于排除对单一 next-open 成交点过度敏感的配置；不能据此产生 candidate、paper-live、dry-run、handoff 或 live 状态。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- CSV：`{RANKING_CSV_PATH}`",
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
    ranking, metadata, quality = evaluate()
    selected = ranking.loc[ranking["name"].eq(SELECTED.name)].iloc[0]
    ranking.to_csv(RANKING_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(ranking, quality), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "run_date": RUN_DATE,
                "status": "delay_aware_diagnostic_selection",
                "metadata": metadata,
                "data_quality": quality,
                "input_risk_feasible": len(ranking),
                "delay_joint_pass": int(ranking["delay_joint_gate"].sum()),
                "frequency_preferred_pass": int(
                    (ranking["delay_joint_gate"] & ranking["frequency_preferred"]).sum()
                ),
                "selected": selected.to_dict(),
                "top100": ranking.head(100).to_dict(orient="records"),
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
                "joint_rank",
                "name",
                "k1_annual_return_pct",
                "k1_max_drawdown_pct",
                "k1_win_rate_pct",
                "k1_trades_per_day",
                "k2_annual_return_pct",
                "k2_max_drawdown_pct",
                "k2_win_rate_pct",
                "k2_trades_per_day",
                "k2_last90_annual_return_pct",
                "frequency_preferred",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
