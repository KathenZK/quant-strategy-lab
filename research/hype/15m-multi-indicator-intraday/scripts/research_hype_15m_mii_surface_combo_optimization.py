from __future__ import annotations

import json
import sys
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from research_hype_15m_mii_full_ablation import (  # noqa: E402
    ABLATIONS_DIR,
    ARTIFACTS_DIR,
    BASELINE,
    CACHE_PATH,
    StrategyConfig,
    VariantSpec,
    bb_signal,
    calculate_raw_trades,
    calendar_month_windows,
    config_with,
    data_quality_report,
    evaluate_variant,
    filter_with,
    fixed_exit,
    json_default,
    num,
    pct,
    rolling_windows,
    rsi_signal,
    trailing_exit,
    window_rows,
)
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    SignalSpec,
    add_features,
    build_market_arrays,
    ema_pairs,
    load_data,
    signal_state,
)


SCRIPT_PATH = (
    Path("research/hype/15m-multi-indicator-intraday/scripts")
    / "research_hype_15m_mii_surface_combo_optimization.py"
)
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_surface_combo_optimization_2026-06-26.json"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_surface_combo_optimization_summary_2026-06-26.csv"
VALIDATION_SLICES_CSV_PATH = (
    ARTIFACTS_DIR / "hype_15m_mii_surface_combo_optimization_slices_2026-06-26.csv"
)
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_surface_combo_optimization_rolling_2026-06-26.csv"
MONTHLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_surface_combo_optimization_monthly_2026-06-26.csv"
MARKDOWN_PATH = ABLATIONS_DIR / "hype-15m-mii-surface-combo-optimization-2026-06-26.md"


def filter_label(values: dict[str, Any]) -> str:
    if not values:
        return "baseline_filter"
    parts: list[str] = []
    for key, value in values.items():
        text = str(value).replace(".", "p").replace("-", "m")
        parts.append(f"{key}_{text}")
    return "__".join(parts)


def add_combo(
    variants: list[VariantSpec],
    *,
    label: str,
    family: str,
    value: str,
    config: StrategyConfig,
) -> None:
    variants.append(
        VariantSpec(
            label=label,
            family=family,
            parameter="surface_combo",
            value=value,
            config=config,
        )
    )


def surface_signals() -> list[tuple[str, SignalSpec]]:
    return [
        ("rsi7_30_60", BASELINE.signal),
        ("rsi14_30_60", rsi_signal(14, 30.0, 60.0)),
        ("bb_reversion_w48_k1p5", bb_signal("bb_reversion", 48, 1.5)),
    ]


def surface_exits() -> list[tuple[str, Any]]:
    return [
        ("fixed_tp0p9_sl2p8_hold16", BASELINE.exit),
        ("fixed_tp1p2_sl2p8_hold16", fixed_exit(0.012, 0.028, 16)),
        ("fixed_tp1p8_sl2p8_hold16", fixed_exit(0.018, 0.028, 16)),
        ("fixed_tp1p2_sl1p8_hold16", fixed_exit(0.012, 0.018, 16)),
        ("fixed_tp1p2_sl2p8_hold8", fixed_exit(0.012, 0.028, 8)),
        ("trail_act2p4_trail0p5_sl2p8_hold16", trailing_exit(0.024, 0.005, 0.028, 16)),
    ]


def surface_filters() -> list[tuple[str, Any]]:
    filter_changes: list[dict[str, Any]] = [
        {},
        {"min_rvol96": 0.75},
        {"min_rvol96": 1.0},
        {"min_atr_pct96": 0.009},
        {"min_h1_dir_spread": 0.0},
        {"min_dir_rsi14": 48.0, "max_dir_rsi14": 78.0},
        {"min_rvol96": 0.75, "min_atr_pct96": 0.009},
        {"min_rvol96": 1.0, "min_atr_pct96": 0.009},
        {"min_rvol96": 0.75, "min_h1_dir_spread": 0.0},
        {"min_rvol96": 0.75, "min_dir_rsi14": 48.0, "max_dir_rsi14": 78.0},
        {"min_atr_pct96": 0.009, "min_h1_dir_spread": 0.0},
    ]
    return [(filter_label(changes), filter_with(**changes)) for changes in filter_changes]


def build_combo_variants() -> list[VariantSpec]:
    variants = [
        VariantSpec(
            label="baseline",
            family="baseline",
            parameter="surface_combo",
            value="search_best",
            config=BASELINE,
        )
    ]
    exposures = [1.0, 1.25, 1.5]
    seen: set[str] = {"baseline"}
    for (signal_label, signal), (exit_label, exit_spec), (filter_name, filter_spec), exposure in product(
        surface_signals(),
        surface_exits(),
        surface_filters(),
        exposures,
    ):
        label = f"{signal_label}__{exit_label}__{filter_name}__x{str(exposure).replace('.', 'p')}"
        if label in seen:
            continue
        seen.add(label)
        add_combo(
            variants,
            label=label,
            family="surface_combo_grid",
            value=f"{signal_label}|{exit_label}|{filter_name}|x{exposure}",
            config=config_with(
                signal=signal,
                exit_spec=exit_spec,
                filter_spec=filter_spec,
                exposure=exposure,
            ),
        )
    return variants


def attach_objective_flags(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()
    baseline = result.loc[result["label"].eq("baseline")].iloc[0]
    baseline_annual = float(baseline["annual_return_pct"])
    baseline_dd = float(baseline["max_drawdown_pct"])
    result["higher_return_than_baseline"] = result["annual_return_pct"] > baseline_annual
    result["lower_dd_than_baseline"] = result["max_drawdown_pct"] >= baseline_dd
    result["return_and_dd_pass"] = (
        result["higher_return_than_baseline"] & result["lower_dd_than_baseline"]
    )
    result["trade_shape_pass"] = (
        (result["win_rate_pct"] >= 70.0)
        & (result["trades_per_day"] >= 0.75)
        & (result["trades_per_day"] <= 2.25)
    )
    result["recent_pass"] = (
        (result["last_90d_annual_return_pct"] > 0.0)
        & (result["second_half_annual_return_pct"] > 0.0)
        & (result["oos_2026_06_01_to_latest_trades"] >= 10)
    )
    result["optimization_gate_pass"] = (
        result["return_and_dd_pass"] & result["trade_shape_pass"] & result["recent_pass"]
    )
    result["objective_score"] = (
        result["annual_return_pct"]
        + (result["max_drawdown_pct"] - baseline_dd) * 8.0
        + result["last_90d_annual_return_pct"] * 0.5
    )
    result.loc[~result["return_and_dd_pass"], "objective_score"] -= 500.0
    result.loc[~result["trade_shape_pass"], "objective_score"] -= 100.0
    result.loc[~result["recent_pass"], "objective_score"] -= 100.0
    return result


def result_table(rows: pd.DataFrame, *, max_rows: int = 15) -> list[str]:
    lines = [
        "| 组合 | 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 | OOS 笔数 | 目标通过 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(max_rows).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{pct(float(row['annual_return_pct']))}` | "
            f"`{pct(float(row['max_drawdown_pct']))}` | `{pct(float(row['win_rate_pct']))}` | "
            f"`{int(row['trades'])}` | `{num(float(row['trades_per_day']))}` | "
            f"`{num(float(row['profit_factor']))}` | "
            f"`{pct(float(row['second_half_annual_return_pct']))}` | "
            f"`{pct(float(row['last_90d_annual_return_pct']))}` | "
            f"`{int(row['oos_2026_06_01_to_latest_trades'])}` | "
            f"`{bool(row['optimization_gate_pass'])}` |"
        )
    return lines


def render_markdown(
    *,
    data_quality: dict[str, Any],
    summary: pd.DataFrame,
    monthly: pd.DataFrame,
    rolling: pd.DataFrame,
) -> str:
    baseline = summary.loc[summary["label"].eq("baseline")].iloc[0]
    variants = summary.loc[~summary["label"].eq("baseline")].copy()
    strict = variants.loc[variants["optimization_gate_pass"]].sort_values(
        ["objective_score", "annual_return_pct"],
        ascending=False,
    )
    return_dd = variants.loc[variants["return_and_dd_pass"]].sort_values(
        ["annual_return_pct", "max_drawdown_pct"],
        ascending=False,
    )
    higher_return = variants.loc[variants["higher_return_than_baseline"]].sort_values(
        ["annual_return_pct"],
        ascending=False,
    )
    lower_dd = variants.loc[variants["lower_dd_than_baseline"]].sort_values(
        ["max_drawdown_pct", "annual_return_pct"],
        ascending=False,
    )
    compromise = variants.sort_values(
        ["objective_score", "annual_return_pct"],
        ascending=False,
    )
    best = compromise.iloc[0]
    worst_rolling90 = rolling.loc[rolling["days"].eq(90)].sort_values("annual_return_pct").head(1)
    worst_month = monthly.sort_values("annual_return_pct").iloc[0]

    lines = [
        "# HYPE-15M-MII 表面改善参数组合优化 2026-06-26",
        "",
        "Family id：`HYPE-15M-MII`",
        "",
        "## 结论",
        "",
        "本轮把全参数消融里“表面改善最大”的单因子组合成网格测试，目标是寻找年化收益高于基线且最大回撤不差于基线的优化版本。结果没有找到可同时满足这两个目标、交易形态和最近稳定性的组合。",
        "",
        f"- 测试组合数：`{len(summary)}`（含基线）。",
        f"- 收益高于基线且回撤不差于基线：`{int(variants['return_and_dd_pass'].sum())}/{len(variants)}`。",
        f"- 完整 optimization gate 通过：`{int(variants['optimization_gate_pass'].sum())}/{len(variants)}`。",
        "",
        "因此这次组合优化仍不能把该策略提升为 candidate；更高收益通常来自放大止盈或保留更多波动交易，但回撤同步变差。更低回撤通常来自加过滤，但收益和交易频率明显下降。",
        "",
        "## 数据与口径",
        "",
        f"- 数据：`data/cache/hypeusdt_15m_fapi.csv`，`{data_quality['first_ts']}` 到 `{data_quality['last_ts']}`，`{data_quality['rows']}` 根 `15m` K。",
        f"- 数据质量：缺口 `{data_quality['gap_count']}`，重复 timestamp `{data_quality['duplicated_ts']}`，关键空值 `{data_quality['critical_nulls']}`，非法 OHLC `{data_quality['invalid_ohlc_rows']}`。",
        "- 限制：仍是 cache reproduction，缺少 `quote_volume/trade_count/vwap/source/is_closed`；不得按标准数据湖 promotion 结果使用。",
        f"- 成本：每边手续费 `{COMMISSION_PER_SIDE:.4%}`，每边滑点 `{SLIPPAGE_PER_SIDE:.4%}`，round-trip `{ROUND_TRIP_COST:.4%}`。",
        "- 执行：闭合 K 产生信号，下一根 open 入场；固定 TP/SL intrabar 检查；同根 TP/SL 保守按 stop first；单仓不重叠。",
        "",
        "## 基线",
        "",
        "| 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{pct(float(baseline['annual_return_pct']))}` | `{pct(float(baseline['max_drawdown_pct']))}` | `{pct(float(baseline['win_rate_pct']))}` | `{int(baseline['trades'])}` | `{num(float(baseline['trades_per_day']))}` | `{num(float(baseline['profit_factor']))}` | `{pct(float(baseline['second_half_annual_return_pct']))}` | `{pct(float(baseline['last_90d_annual_return_pct']))}` |",
        "",
        "## 严格通过组合",
        "",
    ]
    if strict.empty:
        lines.append("无。")
    else:
        lines.extend(result_table(strict))
    lines.extend(
        [
            "",
            "## 收益更高且回撤更小的组合",
            "",
        ]
    )
    if return_dd.empty:
        lines.append("无。")
    else:
        lines.extend(result_table(return_dd))
    lines.extend(
        [
            "",
            "## 样本内收益最高的组合",
            "",
            *result_table(higher_return),
            "",
            "## 回撤最低的组合",
            "",
            *result_table(lower_dd),
            "",
            "## 折中排序最高组合",
            "",
            f"- 组合：`{best['label']}`。",
            f"- 年化 `{pct(float(best['annual_return_pct']))}`，最大回撤 `{pct(float(best['max_drawdown_pct']))}`，胜率 `{pct(float(best['win_rate_pct']))}`，交易 `{int(best['trades'])}` 笔，`{num(float(best['trades_per_day']))}` 笔/日。",
            f"- 它没有通过优化目标：`return_and_dd_pass={bool(best['return_and_dd_pass'])}`，`recent_pass={bool(best['recent_pass'])}`，`trade_shape_pass={bool(best['trade_shape_pass'])}`。",
            "",
            "## 时间稳定性摘要",
            "",
            f"- 最差月：`{worst_month['window']}`，年化 `{pct(float(worst_month['annual_return_pct']))}`，总收益 `{pct(float(worst_month['total_return_pct']))}`。",
        ]
    )
    if not worst_rolling90.empty:
        row = worst_rolling90.iloc[0]
        lines.append(
            f"- 基线最差滚动 `90d`：`{row['window']}`，年化 `{pct(float(row['annual_return_pct']))}`，总收益 `{pct(float(row['total_return_pct']))}`，回撤 `{pct(float(row['max_drawdown_pct']))}`。"
        )
    lines.extend(
        [
            "",
            "## 参数结论",
            "",
            "- `TP=1.2%` 是最接近“收益提高”的单因子，但和其他过滤组合后很难同时保持基线回撤与交易频率。",
            "- `rvol`、`min_atr`、`h1`、`RSI band` 可以降低回撤或提高 PF，但本质是减少交易；组合后收益通常低于基线。",
            "- `BB reversion` 和 trailing 出口改善了最近窗口，但全样本回撤或胜率不足，不能作为优化版。",
            "- 更高杠杆不是优化，只是放大收益和回撤；本轮目标是收益更高且回撤更小，因此不把加杠杆当作解决方案。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- JSON：`{SUMMARY_JSON_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- 验证切片 CSV：`{VALIDATION_SLICES_CSV_PATH}`",
            f"- 滚动切片 CSV：`{ROLLING_CSV_PATH}`",
            f"- 月切片 CSV：`{MONTHLY_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ABLATIONS_DIR.mkdir(parents=True, exist_ok=True)

    raw, metadata = load_data(CACHE_PATH, refresh=False)
    quality = data_quality_report(raw)
    start_ts = pd.Timestamp(raw["ts"].min())
    end_ts = pd.Timestamp(raw["ts"].max())

    variants = build_combo_variants()
    signals = {variant.config.signal.name: variant.config.signal for variant in variants}
    spans = sorted(
        {
            value
            for signal in signals.values()
            for value in (signal.fast, signal.slow)
            if value
        }
        | {fast for fast, _slow in ema_pairs()}
        | {slow for _fast, slow in ema_pairs()}
    )
    features = add_features(raw, spans)
    market = build_market_arrays(features)
    states = {signal.name: signal_state(features, signal) for signal in signals.values()}
    raw_trade_cache: dict[tuple[str, str], list[Any]] = {}

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    baseline_raw_trades: list[Any] | None = None

    print(
        f"data {start_ts} -> {end_ts} rows={len(raw)} combos={len(variants)}",
        flush=True,
    )
    for idx, variant in enumerate(variants, start=1):
        raw_trades = calculate_raw_trades(
            states=states,
            market=market,
            config=variant.config,
            raw_trade_cache=raw_trade_cache,
        )
        if variant.label == "baseline":
            baseline_raw_trades = raw_trades
        row, slices = evaluate_variant(
            variant=variant,
            raw_trades=raw_trades,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        row["config_signal"] = variant.config.signal.name
        row["config_exit"] = variant.config.exit.name
        row["config_filter"] = variant.config.filter.name
        row["config_exposure"] = variant.config.exposure
        summary_rows.append(row)
        slice_rows.extend(slices)
        if idx % 50 == 0 or idx == len(variants):
            print(f"combo {idx}/{len(variants)}", flush=True)

    if baseline_raw_trades is None:
        raise RuntimeError("baseline raw trades were not captured")

    summary = attach_objective_flags(pd.DataFrame(summary_rows))
    summary = summary.sort_values(
        ["optimization_gate_pass", "return_and_dd_pass", "objective_score", "annual_return_pct"],
        ascending=False,
    ).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows)
    rolling = pd.DataFrame(
        window_rows(
            config=BASELINE,
            raw_trades=baseline_raw_trades,
            windows=rolling_windows(start_ts, end_ts),
        )
    )
    monthly = pd.DataFrame(
        window_rows(
            config=BASELINE,
            raw_trades=baseline_raw_trades,
            windows=calendar_month_windows(start_ts, end_ts),
        )
    )
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    slices.to_csv(VALIDATION_SLICES_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    monthly.to_csv(MONTHLY_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(
            data_quality=quality,
            summary=summary,
            monthly=monthly,
            rolling=rolling,
        ),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": "HYPE-15M-MII",
                "baseline": {
                    "signal": asdict(BASELINE.signal),
                    "exit": asdict(BASELINE.exit),
                    "filter": asdict(BASELINE.filter),
                    "exposure": BASELINE.exposure,
                },
                "metadata": metadata,
                "data_quality": quality,
                "cost_model": {
                    "commission_per_side": COMMISSION_PER_SIDE,
                    "slippage_per_side": SLIPPAGE_PER_SIDE,
                    "round_trip_cost": ROUND_TRIP_COST,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary_csv": str(SUMMARY_CSV_PATH),
                    "validation_slices_csv": str(VALIDATION_SLICES_CSV_PATH),
                    "rolling_csv": str(ROLLING_CSV_PATH),
                    "monthly_csv": str(MONTHLY_CSV_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(
        summary.head(20)[
            [
                "label",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
                "trades_per_day",
                "profit_factor",
                "last_90d_annual_return_pct",
                "return_and_dd_pass",
                "optimization_gate_pass",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
