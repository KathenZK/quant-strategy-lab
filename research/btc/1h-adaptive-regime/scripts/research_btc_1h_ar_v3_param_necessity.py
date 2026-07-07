from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v3 as v3  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
DATE_TAG = "2026-07-07"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v3_param_necessity_{DATE_TAG}.json"
REPORT_MD = NOTES_DIR / f"btc-1h-ar-v3-param-necessity-{DATE_TAG}.md"


# 每项候选：(component, field, V3 值, 中和值, 说明)。中和值等价于把该过滤/上限从策略中移除。
REMOVAL_CANDIDATES: list[tuple[str, str, Any, Any, str]] = [
    (
        "keltner",
        "max_atr_bps",
        200.0,
        10000.0,
        "波动率上限；消融显示放宽到 250/300/10000 路径不变，从不拒绝信号",
    ),
    (
        "keltner",
        "min_dir_roc_bps",
        -200.0,
        -10000.0,
        "方向 ROC 下限；放宽到 -10000 路径不变，过滤器从不生效",
    ),
    (
        "keltner",
        "max_aligned_funding_bps",
        4.0,
        10000.0,
        "顺方向资金费上限；收紧到 2.0 或放宽到 10000 路径均不变",
    ),
    (
        "keltner",
        "max_hold_bars",
        240,
        100000,
        "最长持仓；168/216 路径不变，没有交易持仓到 240 根上限",
    ),
    (
        "keltner",
        "cooldown_bars",
        0,
        0,
        "冷却期；V3 冻结值即 0（关闭状态），槽位本身无效",
    ),
    (
        "cci",
        "max_atr_bps",
        600.0,
        10000.0,
        "波动率上限；收紧到 300 路径都不变，从不拒绝信号",
    ),
    (
        "cci",
        "cooldown_bars",
        0,
        0,
        "冷却期；V3 冻结值即 0（关闭状态），槽位本身无效",
    ),
]

# roc_window 依附于 min_dir_roc_bps：过滤器移除后该窗口参数完全失效，用单独验证确认。
ROC_WINDOW_PROBE_VALUE = 12


def minimal_configs(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
) -> tuple[Any, Any, list[dict[str, Any]], str]:
    """贪心累积移除非必要参数，保证每一步后与 V3 逐笔路径等价。

    返回 (最小 Keltner clean 配置, 最小 CCI clean 配置, 审计明细, 基线签名)。
    """
    baseline_trades, *_ = v3.simulate_v3(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_signature = v1.trade_signature(baseline_trades)

    keltner = v3.KELTNER
    cci = v3.CCI
    audit: list[dict[str, Any]] = []
    for component, field, v3_value, neutral_value, note in REMOVAL_CANDIDATES:
        if component == "keltner":
            trial_keltner = replace(keltner, **{field: neutral_value})
            trial_cci = cci
        else:
            trial_keltner = keltner
            trial_cci = replace(cci, **{field: neutral_value})
        trial_trades, *_ = v3.simulate_v3(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            keltner=replace(
                v3.clean.keltner_to_base(engine, trial_keltner),
                name="BTC_1H_AR_V3_MIN_KELTNER",
            ),
            cci=replace(
                v3.clean.cci_to_base(engine, trial_cci),
                name="BTC_1H_AR_V3_MIN_CCI",
            ),
        )
        path_equal = v1.trade_signature(trial_trades) == baseline_signature
        audit.append(
            {
                "component": component,
                "field": field,
                "v3_value": v3_value,
                "neutral_value": neutral_value,
                "cumulative_path_equal": path_equal,
                "removed": path_equal,
                "note": note,
            }
        )
        if path_equal:
            keltner = trial_keltner
            cci = trial_cci
    return keltner, cci, audit, baseline_signature


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    min_keltner, min_cci, audit, baseline_signature = minimal_configs(
        engine, frame, funding_times, funding_cumulative
    )

    def simulate_clean(keltner: Any, cci: Any) -> list[Any]:
        trades, *_ = v3.simulate_v3(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            keltner=replace(
                v3.clean.keltner_to_base(engine, keltner),
                name="BTC_1H_AR_V3_MIN_KELTNER",
            ),
            cci=replace(
                v3.clean.cci_to_base(engine, cci), name="BTC_1H_AR_V3_MIN_CCI"
            ),
        )
        return trades

    min_trades = simulate_clean(min_keltner, min_cci)
    min_signature = v1.trade_signature(min_trades)
    if min_signature != baseline_signature:
        raise RuntimeError("Minimal V3 surface is not trade-path equivalent to V3")

    # 验证 roc_window 在方向 ROC 过滤移除后完全失效。
    roc_probe_trades = simulate_clean(
        replace(min_keltner, roc_window=ROC_WINDOW_PROBE_VALUE), min_cci
    )
    roc_window_inert = v1.trade_signature(roc_probe_trades) == baseline_signature

    removed = [row for row in audit if row["removed"]]
    kept_keltner = [
        "indicator_window",
        "band_k",
        "min_adx",
        "min_rvol",
        "htf_mode",
        "tp_atr",
        "sl_atr",
        "fixed_leverage",
    ]
    kept_cci = [
        "ema_htf",
        "indicator_window",
        "threshold_high",
        "max_adx",
        "min_rvol",
        "min_atr_bps",
        "max_dist_ema_bps",
        "tp_atr",
        "sl_atr",
        "max_hold_bars",
        "fixed_leverage",
    ]
    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V3",
        "identity": "v3_minimal_equivalent_surface",
        "status": "diagnostic_param_necessity_audit_not_live_ready",
        "date": DATE_TAG,
        "trade_path_equal": True,
        "roc_window_inert_after_removal": roc_window_inert,
        "clean_slots_before": 27,
        "removed_slots": len(removed) + (1 if roc_window_inert else 0),
        "necessary_slots": {
            "keltner": kept_keltner,
            "cci": kept_cci,
            "total": len(kept_keltner) + len(kept_cci),
        },
        "removal_audit": audit,
        "minimal_keltner": asdict(min_keltner),
        "minimal_cci": asdict(min_cci),
        "metrics": v1.metrics(engine, min_trades),
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        f"# BTC-1H-Adaptive-Regime-V3 参数必要性审计 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "基于 2026-07-06 V3 全参数消融的路径等价证据，对 V3 clean surface 的 `27` 个"
            " active 槽位逐项做中和验证：把候选参数替换为“移除等价”的中性值，并要求替换后"
            "与 V3 逐笔交易签名完全一致（贪心累积验证）。"
        ),
        "",
        (
            f"结果：`{len(removed)}` 个槽位在 V3 冻结值下从不生效，可以安全移除；"
            f"`roc_window` 在方向 ROC 过滤移除后完全失效（probe 验证 `{roc_window_inert}`），"
            "一并从最小表面剔除。最小等价表面共 "
            f"`{len(kept_keltner) + len(kept_cci)}` 个必要参数"
            f"（Keltner `{len(kept_keltner)}` 个、CCI `{len(kept_cci)}` 个），"
            "逐笔路径与 V3 完全等价，指标不变。"
        ),
        "",
        "## 移除明细",
        "",
        "| Leg | Parameter | V3 value | 中和值 | 累积路径等价 | 决定 | 原因 |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in audit:
        decision = "移除" if row["removed"] else "保留"
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['v3_value']}` | "
            f"`{row['neutral_value']}` | `{row['cumulative_path_equal']}` | "
            f"{decision} | {row['note']} |"
        )
    lines.append(
        f"| `keltner` | `roc_window` | `24` | 依附移除 | `{roc_window_inert}` | 移除 | "
        "方向 ROC 过滤（min_dir_roc_bps）移除后该窗口不再被读取 |"
    )
    lines.extend(
        [
            "",
            "## 必要参数（最小等价表面）",
            "",
            "### Keltner breakout leg（8 个）",
            "",
            "| Parameter | V3 value |",
            "| --- | ---: |",
            *[
                f"| `{key}` | `{getattr(min_keltner, key)}` |"
                for key in kept_keltner
            ],
            "",
            "### CCI reversal leg（11 个）",
            "",
            "| Parameter | V3 value |",
            "| --- | ---: |",
            *[f"| `{key}` | `{getattr(min_cci, key)}` |" for key in kept_cci],
            "",
            "## 边界",
            "",
            "- “非必要”只针对 V3 当前冻结值：这些过滤器在历史两年数据上从不触发，不代表它们在其他参数组合下也永远无效。",
            "- 移除验证使用逐笔交易签名完全一致，指标与 V3 逐字节相同，不构成新版本。",
            "- 该审计不改变 `diagnostic observation / not live-ready`。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v3_param_necessity.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
