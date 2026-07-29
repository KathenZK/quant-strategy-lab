from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import hto_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
V1_PATH = ARTIFACT_DIR / "hype_d15_hto_v1_search_2026-07-29.json"
RUN_DATE = "2026-07-29"


def metric_row(
    *,
    name: str,
    kind: str,
    result: engine.BacktestResult,
    baseline: engine.BacktestResult,
) -> dict[str, Any]:
    metrics = result.metrics
    base = baseline.metrics
    return {
        "name": name,
        "kind": kind,
        "path_equal": engine.trade_signature(result) == engine.trade_signature(baseline),
        "annual_factor": metrics["annual_factor"],
        "annual_factor_delta": metrics["annual_factor"] - base["annual_factor"],
        "total_return": metrics["total_return"],
        "total_return_delta": metrics["total_return"] - base["total_return"],
        "max_drawdown": metrics["max_drawdown"],
        "max_drawdown_delta": metrics["max_drawdown"] - base["max_drawdown"],
        "win_rate": metrics["win_rate"],
        "win_rate_delta": metrics["win_rate"] - base["win_rate"],
        "trades": metrics["trades"],
        "trade_delta": metrics["trades"] - base["trades"],
        "profit_factor": metrics["profit_factor"],
    }


def alternative_values(config: engine.Config) -> dict[str, Any]:
    return {
        "daily_mode": 0,
        "direction": 1,
        "daily_fast": 20,
        "daily_slow": 60,
        "daily_mom_window": 40,
        "daily_adx_window": 7,
        "daily_adx_min": 20.0,
        "daily_channel_window": 20,
        "daily_atr_window": 10,
        "daily_supertrend_mult": 3.0,
        "daily_vote_min": 3,
        "entry_mode": 3,
        "micro_fast": 144,
        "micro_slow": 384,
        "entry_window": 32,
        "exit_window": 96,
        "atr_window": 48,
        "micro_adx_min": 0.0,
        "rvol_min": 0.0,
        "rsi_window": 6,
        "rsi_trigger": 20.0,
        "rsi_reclaim": 49.0,
        "pullback_atr": 1.0,
        "breakout_atr": 0.5,
        "expansion_min": 4.0,
        "sl_atr": 1.0,
        "tp_atr": 0.0,
        "trail_activation_atr": 6.0,
        "trail_atr": 5.0,
        "breakeven_trigger_atr": 0.0,
        "max_hold_bars": 672,
        "cooldown_bars": 0,
        "leverage": 3.0,
        "exit_mode": 0,
    }


def render_report(
    *,
    summary: dict[str, Any],
    frame: pd.DataFrame,
) -> str:
    baseline = summary["baseline_metrics"]
    dormant = summary["dormant_slots"]
    components = frame.loc[frame["kind"] == "component"]
    lines = [
        "# HYPE-D15-HTO-V1 全参数与组件消融",
        "",
        f"- 生成时间：`{summary['generated_at_utc']}`",
        "- 数据：只使用 locked OOS 之前的 frozen prefit；本报告未读取 OOS 绩效。",
        "- 成本：每次成交手续费 `0.001`，不利滑点 `4 bps/fill`，计实际资金费。",
        "- 时序：前一完整 UTC 日状态、`15m` 闭合信号、下一根开盘成交、stop-first。",
        "",
        "## V1 基线",
        "",
        (
            f"`annual_factor={baseline['annual_factor']:.4f}x`，"
            f"`return={baseline['total_return']:.2%}`，"
            f"`win_rate={baseline['win_rate']:.2%}`，"
            f"`MDD={baseline['max_drawdown']:.2%}`，"
            f"`trades={baseline['trades']}`。"
        ),
        "",
        "## 结论",
        "",
        (
            f"逐槽位替换共 `{summary['slot_variant_count']}` 项，组件关闭共 "
            f"`{summary['component_variant_count']}` 项。成交路径完全不变的 dormant "
            f"槽位为：`{', '.join(dormant) if dormant else '无'}`。"
        ),
        "",
        "组件移除结果：",
        "",
        "| 组件 | 年化倍数 | 收益 | 胜率 | MDD | 交易数 | 路径相同 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for _, row in components.iterrows():
        lines.append(
            f"| `{row['name']}` | {row['annual_factor']:.3f}x | "
            f"{row['total_return']:.2%} | {row['win_rate']:.2%} | "
            f"{row['max_drawdown']:.2%} | {int(row['trades'])} | "
            f"{'是' if row['path_equal'] else '否'} |"
        )
    lines.extend(
        [
            "",
            "V1 的 prefit 年化倍数未达到 `10x`，因此消融只用于识别有效机制与精简参数面，",
            "不构成 promotion 证据。只有 path-equal/dormant 槽位可从 V2 接口删除；",
            "对收益有负贡献但改变成交路径的组件不能仅凭单次消融静默删除，需在 clean 面重新搜索。",
            "",
            "## 证据",
            "",
            "- [逐项 CSV](../artifacts/hype_d15_hto_v1_ablation_2026-07-29.csv)",
            "- [机器摘要 JSON](../artifacts/hype_d15_hto_v1_ablation_2026-07-29.json)",
            "- [V1 冻结配置](../artifacts/hype_d15_hto_v1_search_2026-07-29.json)",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(V1_PATH.read_text(encoding="utf-8"))
    if payload["locked_oos_accessed"]:
        raise RuntimeError("V1 artifact unexpectedly accessed locked OOS")
    config = engine.config_from_dict(payload["config"])
    book = engine.build_book(include_locked_oos=False)
    baseline = engine.run_backtest(book, config, detailed=True)
    rows: list[dict[str, Any]] = []

    for field, value in alternative_values(config).items():
        if getattr(config, field) == value:
            continue
        variant = engine.replace_config(config, **{field: value})
        result = engine.run_backtest(book, variant)
        row = metric_row(
            name=field,
            kind="slot",
            result=result,
            baseline=baseline,
        )
        row["baseline_value"] = getattr(config, field)
        row["variant_value"] = value
        rows.append(row)

    components = (
        "daily_ema",
        "daily_momentum",
        "daily_dmi",
        "daily_breakout",
        "daily_supertrend",
        "daily_adx_filter",
        "primary_entry",
        "micro_trend",
        "micro_adx_filter",
        "rvol_filter",
    )
    for component in components:
        result = engine.run_backtest(
            book, config, disabled_components=frozenset({component})
        )
        row = metric_row(
            name=component,
            kind="component",
            result=result,
            baseline=baseline,
        )
        row["baseline_value"] = "enabled"
        row["variant_value"] = "disabled"
        rows.append(row)

    frame = pd.DataFrame(rows)
    dormant = frame.loc[
        (frame["kind"] == "slot") & frame["path_equal"], "name"
    ].tolist()
    summary = {
        "family": payload["family"],
        "version": payload["version"],
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "locked_oos_accessed": False,
        "baseline_config": asdict(config),
        "baseline_config_sha256": engine.config_sha256(config),
        "baseline_trade_signature": engine.trade_signature(baseline),
        "baseline_metrics": baseline.metrics,
        "slot_variant_count": int((frame.kind == "slot").sum()),
        "component_variant_count": int((frame.kind == "component").sum()),
        "dormant_slots": dormant,
        "path_changing_slots": frame.loc[
            (frame.kind == "slot") & (~frame.path_equal), "name"
        ].tolist(),
        "component_rows": frame.loc[frame.kind == "component"].to_dict("records"),
    }
    csv_path = ARTIFACT_DIR / f"hype_d15_hto_v1_ablation_{RUN_DATE}.csv"
    json_path = ARTIFACT_DIR / f"hype_d15_hto_v1_ablation_{RUN_DATE}.json"
    report_path = ABLATION_DIR / f"hype-d15-hto-v1-full-ablation-{RUN_DATE}.md"
    frame.to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(
        render_report(summary=summary, frame=frame), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
