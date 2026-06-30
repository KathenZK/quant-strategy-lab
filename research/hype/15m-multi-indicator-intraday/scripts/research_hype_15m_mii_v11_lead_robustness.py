from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_clean_evolution as evolution  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import build_market_arrays, signal_state  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
VERSION = "HYPE-15M-Multi-Indicator-Intraday-V1.1"
RUN_DATE = "2026-06-29"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v11_lead_robustness.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
ABLATIONS_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v11_lead_robustness_2026-06-29.json"
NEIGHBORHOOD_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v11_lead_neighborhood_2026-06-29.csv"
STRESS_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v11_lead_stress_2026-06-29.csv"
MONTHLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v11_lead_monthly_2026-06-29.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v11_lead_rolling90_2026-06-29.csv"
MARKDOWN_PATH = ABLATIONS_DIR / "hype-15m-mii-v1-1-clean-lead-robustness-2026-06-29.md"

LEAD = evolution.CleanConfig(
    rsi_window=7,
    rsi_low=40.0,
    rsi_high=55.0,
    min_atr_pct96=0.0075,
    min_rvol96=1.0,
    h1_confirm=False,
    rsi14_band=False,
    take_profit_pct=0.012,
    stop_pct=0.045,
    max_hold_bars=16,
    exposure=2.0,
)


@dataclass(frozen=True, slots=True)
class Variant:
    label: str
    parameter: str
    value: Any
    config: evolution.CleanConfig


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "m").replace(" ", "")


def variants() -> list[Variant]:
    output = [Variant("baseline", "baseline", "V1.1", LEAD)]
    grid: dict[str, tuple[Any, ...]] = {
        "rsi_window": (5, 7, 11, 14),
        "rsi_low": (35.0, 37.5, 42.5),
        "rsi_high": (55.0, 57.5, 62.5, 65.0),
        "min_atr_pct96": (0.006, 0.00675, 0.00825, 0.009),
        "min_rvol96": (0.0, 0.5, 1.0),
        "h1_confirm": (True,),
        "rsi14_band": (True,),
        "take_profit_pct": (0.009, 0.0105, 0.0135, 0.015),
        "stop_pct": (0.032, 0.036, 0.04, 0.05, 0.055),
        "max_hold_bars": (24, 32, 40, 64),
        "exposure": (0.75, 1.0, 1.5, 1.75),
    }
    for parameter, values in grid.items():
        for value in values:
            if value == getattr(LEAD, parameter):
                continue
            config = replace(LEAD, **{parameter: value})
            if not evolution.valid_config(config):
                continue
            output.append(
                Variant(
                    label=f"{parameter}_{label_value(value)}",
                    parameter=parameter,
                    value=value,
                    config=config,
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


def evaluate_neighborhood(
    context: evolution.EvalContext,
) -> tuple[pd.DataFrame, dict[str, list[dict[str, Any]]]]:
    rows: list[dict[str, Any]] = []
    slices: dict[str, list[dict[str, Any]]] = {}
    for index, variant in enumerate(variants(), start=1):
        row, variant_slices = evolution.evaluate_config(context, variant.config)
        rows.append(
            {
                "label": variant.label,
                "parameter": variant.parameter,
                "value": variant.value,
                **row,
            }
        )
        slices[variant.label] = variant_slices
        if index % 10 == 0 or index == len(variants()):
            print(f"neighborhood {index}/{len(variants())}", flush=True)
    summary = pd.DataFrame(rows)
    baseline = summary.loc[summary["label"].eq("baseline")].iloc[0]
    for column in (
        "annual_return_pct",
        "max_drawdown_pct",
        "win_rate_pct",
        "trades_per_day",
        "profit_factor",
        "last90_annual_return_pct",
    ):
        summary[f"delta_{column}"] = summary[column] - baseline[column]
    summary["neighborhood_gate"] = (
        summary["annual_return_pct"].ge(100.0)
        & summary["max_drawdown_pct"].ge(-22.0)
        & summary["win_rate_pct"].ge(75.0)
        & summary["trades_per_day"].between(0.5, 2.0)
        & summary["second_half_annual_return_pct"].gt(0)
        & summary["last90_annual_return_pct"].gt(0)
    )
    return summary.sort_values("score", ascending=False).reset_index(drop=True), slices


def evaluate_cost_stress(
    context: evolution.EvalContext,
    trades: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    original_cost = v1.search_engine.ROUND_TRIP_COST
    try:
        stress_values = tuple(
            dict.fromkeys((original_cost, 0.0030, 0.0035, 0.0040))
        )
        for cost in stress_values:
            v1.search_engine.ROUND_TRIP_COST = cost
            full = evolution.evaluate_window(
                context,
                LEAD,
                trades,
                context.start_ts,
                context.end_ts,
                purge_end=False,
            )
            last90_start = max(
                context.start_ts,
                context.end_ts - pd.Timedelta(days=90),
            )
            last90 = evolution.evaluate_window(
                context,
                LEAD,
                trades,
                last90_start,
                context.end_ts,
                purge_end=False,
            )
            rows.append(
                {
                    "stress": "round_trip_cost",
                    "value": cost,
                    **{f"full_{key}": value for key, value in full.items()},
                    **{f"last90_{key}": value for key, value in last90.items()},
                }
            )
    finally:
        v1.search_engine.ROUND_TRIP_COST = original_cost
    return rows


def evaluate_delay_stress(
    context: evolution.EvalContext,
) -> dict[str, Any]:
    state = signal_state(context.features, LEAD.signal)
    trades = v1.simulate_trades_live(
        context.market,
        state,
        LEAD.exit,
        entry_delay_bars=2,
    )
    full = evolution.evaluate_window(
        context,
        LEAD,
        trades,
        context.start_ts,
        context.end_ts,
        purge_end=False,
    )
    last90 = evolution.evaluate_window(
        context,
        LEAD,
        trades,
        max(context.start_ts, context.end_ts - pd.Timedelta(days=90)),
        context.end_ts,
        purge_end=False,
    )
    return {
        "stress": "entry_delay_bars",
        "value": 2,
        **{f"full_{key}": value for key, value in full.items()},
        **{f"last90_{key}": value for key, value in last90.items()},
    }


def evaluate_side(
    context: evolution.EvalContext,
    trades: list[Any],
    side: str,
) -> dict[str, Any]:
    filter_spec = replace(LEAD.filter, side=side)
    period_days = (context.end_ts - context.start_ts).total_seconds() / 86_400
    result = v1.engine.evaluate_trades(
        trades=trades,
        filter_spec=filter_spec,
        exposure=LEAD.exposure,
        period_days=period_days,
        exit_spec=LEAD.exit,
        start_ts=context.start_ts,
        end_ts=context.end_ts,
    )
    metrics = evolution.empty_metrics() if result is None else asdict(result)
    return {"stress": "side", "value": side, **{f"full_{key}": value for key, value in metrics.items()}}


def monthly_windows(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    first_month = start_ts.floor("D").replace(day=1)
    starts = pd.date_range(first_month, end_ts, freq="MS", tz="UTC")
    output: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for month_start in starts:
        left = max(start_ts, pd.Timestamp(month_start))
        right = min(end_ts, pd.Timestamp(month_start + pd.offsets.MonthBegin(1)))
        if right > left:
            output.append((left.strftime("%Y-%m"), left, right))
    return output


def rolling90_windows(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    output: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    left = start_ts
    index = 1
    while left + pd.Timedelta(days=90) <= end_ts:
        right = left + pd.Timedelta(days=90)
        output.append(
            (
                f"rolling90_{index:03d}_{left.strftime('%Y%m%d')}_{right.strftime('%Y%m%d')}",
                left,
                right,
            )
        )
        left += pd.Timedelta(days=30)
        index += 1
    return output


def window_rows(
    context: evolution.EvalContext,
    trades: list[Any],
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, start_ts, end_ts in windows:
        metrics = evolution.evaluate_window(
            context,
            LEAD,
            trades,
            start_ts,
            end_ts,
            purge_end=end_ts < context.end_ts,
        )
        if int(metrics["trades"]) == 0:
            metrics = {
                **metrics,
                "annual_return_pct": 0.0,
                "annual_equity_multiple": 1.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "trades_per_day": 0.0,
                "profit_factor": 0.0,
            }
        rows.append(
            {
                "window": label,
                "start_ts": start_ts.isoformat(),
                "end_ts": end_ts.isoformat(),
                **metrics,
            }
        )
    return rows


def metrics_table(rows: pd.DataFrame, limit: int = 15) -> list[str]:
    lines = [
        "| 变体 | 参数 | 值 | 年化 | 回撤 | 胜率 | 笔/日 | PF | Last90 | Gate |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | "
            f"`{row['annual_return_pct']:.2f}%` | `{row['max_drawdown_pct']:.2f}%` | "
            f"`{row['win_rate_pct']:.2f}%` | `{row['trades_per_day']:.3f}` | "
            f"`{row['profit_factor']:.3f}` | `{row['last90_annual_return_pct']:.2f}%` | "
            f"`{bool(row['neighborhood_gate'])}` |"
        )
    return lines


def stress_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 压力项 | 值 | 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | Last90 年化 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['stress']}` | `{row['value']}` | "
            f"`{float(row['full_annual_return_pct']):.2f}%` | "
            f"`{float(row['full_max_drawdown_pct']):.2f}%` | "
            f"`{float(row['full_win_rate_pct']):.2f}%` | "
            f"`{int(row['full_trades'])}` | `{float(row['full_trades_per_day']):.3f}` | "
            f"`{float(row['full_profit_factor']):.3f}` | "
            f"`{float(row.get('last90_annual_return_pct', np.nan)):.2f}%` |"
        )
    return lines


def render_markdown(
    quality: dict[str, Any],
    neighborhood: pd.DataFrame,
    stresses: pd.DataFrame,
    monthly: pd.DataFrame,
    rolling: pd.DataFrame,
    diagnostic_gate: bool,
) -> str:
    baseline = neighborhood.loc[neighborhood["label"].eq("baseline")].iloc[0]
    variants_only = neighborhood.loc[neighborhood["label"].ne("baseline")]
    gate_count = int(variants_only["neighborhood_gate"].sum())
    grouped = (
        variants_only.groupby("parameter", sort=False)
        .agg(
            variants=("label", "count"),
            gate_pass=("neighborhood_gate", "sum"),
            best_annual=("annual_return_pct", "max"),
            worst_annual=("annual_return_pct", "min"),
            best_dd=("max_drawdown_pct", "max"),
            worst_dd=("max_drawdown_pct", "min"),
        )
        .reset_index()
    )
    worst_month = monthly.sort_values("total_return_pct").iloc[0]
    worst_rolling = rolling.sort_values("total_return_pct").iloc[0]
    cost_rows = stresses.loc[stresses["stress"].eq("round_trip_cost")].copy()
    cost_rows["numeric_value"] = pd.to_numeric(cost_rows["value"], errors="coerce")
    base_cost = cost_rows.loc[
        (cost_rows["numeric_value"] - v1.search_engine.ROUND_TRIP_COST).abs().idxmin()
    ]
    high_cost = cost_rows.sort_values("numeric_value").iloc[-1]
    delay = stresses.loc[stresses["stress"].eq("entry_delay_bars")].iloc[0]

    lines = [
        f"# {VERSION} 干净领先版本稳健性复核 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "状态：`diagnostic evolution lead / not promoted / not live-ready`",
        "",
        "## 结论",
        "",
        f"本轮选择的不是演化年化最高或 exposure 最高版本，而是通过 K+1/K+2 联合筛选的 `{LEAD.exposure:g}x` 低频高质量 Pareto 成员。随后对全部生效参数做细粒度 OAT，并补成本、延迟、方向、月度和滚动窗口压力。",
        "",
        f"- 邻域变体：`{len(variants_only)}`；通过 neighborhood gate：`{gate_count}/{len(variants_only)}`。",
        f"- 月度盈利：`{int((monthly['total_return_pct'] > 0).sum())}/{len(monthly)}`；最差月 `{worst_month['window']}` 总收益 `{worst_month['total_return_pct']:.2f}%`。",
        f"- 最差滚动 90d：`{worst_rolling['window']}`，总收益 `{worst_rolling['total_return_pct']:.2f}%`，回撤 `{worst_rolling['max_drawdown_pct']:.2f}%`。",
        f"- 基础 `{float(base_cost['numeric_value']) * 10000:.0f} bps` round-trip 年化 `{base_cost['full_annual_return_pct']:.2f}%`；"
        f"高压 `{float(high_cost['numeric_value']) * 10000:.0f} bps` round-trip 年化 `{high_cost['full_annual_return_pct']:.2f}%`；"
        f"K+2 延迟年化 `{delay['full_annual_return_pct']:.2f}%`。",
        f"- diagnostic gate：`{diagnostic_gate}`。它只允许记录 V1.1 diagnostic lead，不构成 candidate 或 live promotion。",
        "",
        "## V1.1 Diagnostic Lead",
        "",
        f"- `RSI({LEAD.rsi_window})`：多头上穿 `{LEAD.rsi_low:g}`，空头下穿 `{LEAD.rsi_high:g}`。",
        "- 固定 `MACD(12,26,9)` 同方向过滤。",
        f"- `{LEAD.min_atr_pct96:.2%} <= ATR96 pct <= 2.80%`，`RVOL96 >= {LEAD.min_rvol96:g}`。",
        f"- `TP={LEAD.take_profit_pct:.2%}`，`SL={LEAD.stop_pct:.2%}`，最长 `{LEAD.max_hold_bars}` 根 K，`{LEAD.exposure:g}x` exposure。",
        "- 关闭 1h confirm 与 directional RSI14 band；没有 dormant filter 字段。",
        "",
        "| 年化 | 总收益 | 回撤 | 胜率 | 交易数 | 笔/日 | PF | 后半段年化 | Last90 年化 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{baseline['annual_return_pct']:.2f}%` | `{baseline['total_return_pct']:.2f}%` | `{baseline['max_drawdown_pct']:.2f}%` | `{baseline['win_rate_pct']:.2f}%` | `{int(baseline['trades'])}` | `{baseline['trades_per_day']:.3f}` | `{baseline['profit_factor']:.3f}` | `{baseline['second_half_annual_return_pct']:.2f}%` | `{baseline['last90_annual_return_pct']:.2f}%` |",
        "",
        "## 邻域摘要",
        "",
        "| 参数 | 变体数 | Gate 通过 | 最好年化 | 最差年化 | 最低回撤 | 最坏回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in grouped.to_dict(orient="records"):
        lines.append(
            f"| `{row['parameter']}` | `{int(row['variants'])}` | `{int(row['gate_pass'])}` | "
            f"`{row['best_annual']:.2f}%` | `{row['worst_annual']:.2f}%` | "
            f"`{row['best_dd']:.2f}%` | `{row['worst_dd']:.2f}%` |"
        )
    lines.extend(
        [
            "",
            "## 邻域最好结果",
            "",
            *metrics_table(neighborhood, limit=15),
            "",
            "## 压力测试",
            "",
            *stress_table(stresses),
            "",
            "## 解释",
            "",
            f"- 收益提升主要来自 `RSI {LEAD.rsi_low:g}/{LEAD.rsi_high:g} + ATR 质量门槛 + {LEAD.take_profit_pct:.2%} TP`，不是 dormant 字段或更高 exposure 单独放大。",
            f"- `SL={LEAD.stop_pct:.2%}` 是高胜率结构的重要组成，但也意味着单次止损在 `{LEAD.exposure:g}x` 暴露下约损失 `{LEAD.exposure * (LEAD.stop_pct + v1.search_engine.ROUND_TRIP_COST):.2%}`（含基础 round-trip 成本），实盘必须有独立账户级风险限制。",
            "- 邻域通过率只能说明参数不是孤立单点；由于演化和复核都使用同一历史，仍存在二次选择偏差。",
            "- 资金费、tick/盘口级 stop-market、真实滑点、订单失败、runner、重启恢复、对账和 kill switch 仍未解决。",
            "",
            "## 状态",
            "",
            "若 diagnostic gate 通过，则把本配置记录为 `HYPE-15M-Multi-Indicator-Intraday-V1.1` diagnostic evolution lead；不得标记为 candidate、paper-live、dry-run、handoff 或 live。真正 promotion 需要新增未参与搜索的 forward 数据和完整 live-executable 工程审计。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- JSON：`{SUMMARY_JSON_PATH}`",
            f"- 邻域：`{NEIGHBORHOOD_CSV_PATH}`",
            f"- 压力：`{STRESS_CSV_PATH}`",
            f"- 月度：`{MONTHLY_CSV_PATH}`",
            f"- 滚动 90d：`{ROLLING_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ABLATIONS_DIR.mkdir(parents=True, exist_ok=True)
    context, metadata, quality = build_context()
    neighborhood, slices = evaluate_neighborhood(context)
    baseline = neighborhood.loc[neighborhood["label"].eq("baseline")].iloc[0]
    trades = evolution.raw_trades(context, LEAD)

    stress_rows = evaluate_cost_stress(context, trades)
    stress_rows.append(evaluate_delay_stress(context))
    stress_rows.extend(evaluate_side(context, trades, side) for side in ("long", "short"))
    stresses = pd.DataFrame(stress_rows)
    monthly = pd.DataFrame(
        window_rows(
            context,
            trades,
            monthly_windows(context.start_ts, context.end_ts),
        )
    )
    rolling = pd.DataFrame(
        window_rows(
            context,
            trades,
            rolling90_windows(context.start_ts, context.end_ts),
        )
    )

    cost_rows = stresses.loc[stresses["stress"].eq("round_trip_cost")].copy()
    cost_rows["numeric_value"] = pd.to_numeric(cost_rows["value"], errors="coerce")
    high_cost = cost_rows.sort_values("numeric_value").iloc[-1]
    delay = stresses.loc[stresses["stress"].eq("entry_delay_bars")].iloc[0]
    variants_only = neighborhood.loc[neighborhood["label"].ne("baseline")]
    neighborhood_ratio = float(variants_only["neighborhood_gate"].mean())
    diagnostic_gate = bool(
        baseline["annual_return_pct"] >= 150.0
        and baseline["max_drawdown_pct"] >= -20.0
        and baseline["win_rate_pct"] >= 75.0
        and baseline["trades_per_day"] >= 0.5
        and baseline["profit_factor"] >= 1.5
        and baseline["second_half_annual_return_pct"] > 0
        and baseline["last90_annual_return_pct"] > 0
        and baseline["positive_quarters"] == 4
        and neighborhood_ratio >= 0.40
        and high_cost["full_annual_return_pct"] > 50.0
        and high_cost["full_max_drawdown_pct"] >= -30.0
        and delay["full_annual_return_pct"] > 100.0
        and delay["full_max_drawdown_pct"] >= -25.0
        and rolling["total_return_pct"].min() > -10.0
    )

    neighborhood.to_csv(NEIGHBORHOOD_CSV_PATH, index=False)
    stresses.to_csv(STRESS_CSV_PATH, index=False)
    monthly.to_csv(MONTHLY_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(
            quality,
            neighborhood,
            stresses,
            monthly,
            rolling,
            diagnostic_gate,
        ),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "version": VERSION,
                "status": (
                    "diagnostic_evolution_lead_not_promoted"
                    if diagnostic_gate
                    else "failed_diagnostic_gate"
                ),
                "diagnostic_gate": diagnostic_gate,
                "metadata": metadata,
                "data_quality": quality,
                "lead_config": asdict(LEAD),
                "lead_metrics": baseline.to_dict(),
                "neighborhood_gate_ratio": neighborhood_ratio,
                "neighborhood": neighborhood.to_dict(orient="records"),
                "stresses": stresses.to_dict(orient="records"),
                "monthly": monthly.to_dict(orient="records"),
                "rolling90": rolling.to_dict(orient="records"),
                "lead_slices": slices["baseline"],
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "neighborhood_csv": str(NEIGHBORHOOD_CSV_PATH),
                    "stress_csv": str(STRESS_CSV_PATH),
                    "monthly_csv": str(MONTHLY_CSV_PATH),
                    "rolling90_csv": str(ROLLING_CSV_PATH),
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
        neighborhood.head(15)[
            [
                "label",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades_per_day",
                "profit_factor",
                "last90_annual_return_pct",
                "neighborhood_gate",
            ]
        ].to_string(index=False)
    )
    print(stresses.to_string(index=False))
    print(f"diagnostic_gate={diagnostic_gate}")


if __name__ == "__main__":
    main()
