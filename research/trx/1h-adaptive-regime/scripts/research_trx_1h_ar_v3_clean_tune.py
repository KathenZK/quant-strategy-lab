from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_trx_1h_ar_v1_clean_strict_ablation_slices as strict_audit  # noqa: E402
import research_trx_1h_adaptive_regime_search as search  # noqa: E402
import trx_1h_ar_v1 as v1  # noqa: E402
import trx_1h_ar_v2 as v2  # noqa: E402
import trx_1h_ar_v3 as v3  # noqa: E402
import trx_1h_ar_v3_clean as v3c  # noqa: E402


DATE_TAG = "2026-07-07"
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v3_clean_tune_{DATE_TAG}.json"
CANDIDATES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_clean_tune_candidates_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_clean_tune_trades_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_clean_tune_slices_{DATE_TAG}.csv"
AUDIT_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_clean_tune_execution_audit_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"trx-1h-ar-v3-clean-tune-{DATE_TAG}.md"

SEED = 20260707
N_CANDIDATES = 6000
DD_FLOOR = -0.20

# Tunable domains restricted to the V3 clean surface (dormant fields excluded).
MACD_TUNE_DOMAINS: dict[str, tuple[Any, ...]] = {
    "roc_window": (3, 6, 12, 24),
    "macd_set": ((8, 21, 5), (12, 26, 9), (21, 55, 9), (34, 89, 13)),
    "min_adx": (12.0, 16.0, 18.0, 20.0, 22.0),
    "max_adx": (24.0, 26.0, 28.0, 30.0),
    "min_rvol": (0.0, 0.6, 0.8, 1.0),
    "min_dir_roc_bps": (-300.0, -200.0, -100.0, -50.0, 0.0),
    "max_dist_ema_bps": (1500.0, 2500.0, 10_000.0),
    "htf_mode": ("none", "h4", "h12", "d1"),
    "tp_atr": (1.5, 2.0, 2.5, 3.0),
    "sl_atr": (3.0, 4.0, 5.0, 6.0),
    "cooldown_bars": (0, 3, 6, 12),
    "entry_delay_bars": (1, 2),
    "fixed_leverage": (3.0, 3.5, 4.0, 4.5, 5.0),
}
STOCH_TUNE_DOMAINS: dict[str, tuple[Any, ...]] = {
    "side_mode": ("long", "both"),
    "indicator_window": (7, 14, 21, 28),
    "threshold_low": (15.0, 20.0, 25.0, 30.0, 35.0),
    "threshold_high": (75.0, 80.0, 85.0, 90.0),
    "roc_window": (3, 6, 12),
    "max_adx": (20.0, 24.0, 28.0, 30.0),
    "min_rvol": (0.6, 0.8, 1.0, 1.25),
    "min_dir_roc_bps": (-10_000.0, -300.0, -200.0, -100.0),
    "require_body_dir": (False, True),
    "sl_atr": (4.0, 5.0, 6.0),
    "trail_activation_atr": (2.0, 3.0, 4.0),
    "trail_atr": (1.25, 1.5, 2.0, 2.5),
    "max_hold_bars": (72, 96, 120, 168),
    "cooldown_bars": (0, 3, 6, 12, 24),
    "entry_delay_bars": (1, 2, 3),
    "fixed_leverage": (2.5, 3.0, 3.5, 4.0),
}
MACD_SET_FIELDS = ("macd_fast", "macd_slow", "macd_signal")


def macd_field_names() -> list[str]:
    names = [
        field.name
        for field in fields(v3c.MACDV3CleanConfig)
        if field.name not in MACD_SET_FIELDS
    ]
    names.append("macd_set")
    return names


def stoch_field_names() -> list[str]:
    return [field.name for field in fields(v3c.StochV3CleanConfig)]


def apply_change(
    macd: v3c.MACDV3CleanConfig,
    stoch: v3c.StochV3CleanConfig,
    component: str,
    field_name: str,
    value: Any,
) -> tuple[v3c.MACDV3CleanConfig, v3c.StochV3CleanConfig]:
    if component == "macd_flip":
        if field_name == "macd_set":
            macd = replace(
                macd,
                macd_fast=value[0],
                macd_slow=value[1],
                macd_signal=value[2],
            )
        else:
            macd = replace(macd, **{field_name: value})
    else:
        stoch = replace(stoch, **{field_name: value})
    return macd, stoch


def random_candidate(
    rng: random.Random,
    base_macd: v3c.MACDV3CleanConfig,
    base_stoch: v3c.StochV3CleanConfig,
) -> tuple[v3c.MACDV3CleanConfig, v3c.StochV3CleanConfig, list[str]]:
    macd = base_macd
    stoch = base_stoch
    n_changes = rng.choice((1, 2, 2, 3, 3, 4, 5))
    all_slots = [("macd_flip", name) for name in macd_field_names()] + [
        ("stoch_reversal", name) for name in stoch_field_names()
    ]
    changed: list[str] = []
    for component, field_name in rng.sample(all_slots, k=n_changes):
        domains = MACD_TUNE_DOMAINS if component == "macd_flip" else STOCH_TUNE_DOMAINS
        value = rng.choice(domains[field_name])
        macd, stoch = apply_change(macd, stoch, component, field_name, value)
        changed.append(f"{component}.{field_name}={value}")
    if macd.min_adx > macd.max_adx or stoch.threshold_high <= stoch.threshold_low:
        return base_macd, base_stoch, []
    return macd, stoch, changed


def dominates_v3(metrics: dict[str, dict[str, float]], base: dict[str, dict[str, float]]) -> bool:
    prefit = metrics["prefit"]
    base_prefit = base["prefit"]
    return bool(
        prefit["annual_multiple"] > base_prefit["annual_multiple"]
        and prefit["win_rate"] > base_prefit["win_rate"]
        and prefit["max_dd"] > base_prefit["max_dd"]
        and metrics["train"]["total_return"] > 0.0
        and metrics["validation"]["total_return"] > 0.0
        and metrics["train"]["max_dd"] > DD_FLOOR
        and metrics["validation"]["max_dd"] > DD_FLOOR
        and metrics["train"]["win_rate"] >= base["train"]["win_rate"] - 0.02
        and metrics["validation"]["win_rate"] >= 0.80
    )


def flatten(prefix: str, values: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v3.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    base_macd = v3c.MACDV3CleanConfig()
    base_stoch = v3c.StochV3CleanConfig()
    base_trades, *_ = v3c.simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    base_metrics = v1.metrics(engine, base_trades)
    base_slices = v1.standard_slices(engine, base_trades)

    rng = random.Random(SEED)
    seen: set[tuple[Any, ...]] = set()
    prefit_rows: list[dict[str, Any]] = []
    dominating: list[dict[str, Any]] = []
    for index in range(N_CANDIDATES):
        macd, stoch, changed = random_candidate(rng, base_macd, base_stoch)
        if not changed:
            continue
        key = tuple(sorted(asdict(macd).items())) + tuple(sorted(asdict(stoch).items()))
        if key in seen:
            continue
        seen.add(key)
        trades, *_ = v3c.simulate_clean(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            macd=macd,
            stoch=stoch,
        )
        if len(trades) < 30:
            continue
        metrics = v1.metrics(engine, trades)
        row: dict[str, Any] = {
            "candidate": index,
            "changes": "; ".join(changed),
            "n_changes": len(changed),
            "dominates_v3_prefit": dominates_v3(metrics, base_metrics),
            **flatten("train", metrics["train"]),
            **flatten("validation", metrics["validation"]),
            **flatten("prefit", metrics["prefit"]),
            **{f"m_{k}": v for k, v in asdict(macd).items()},
            **{f"s_{k}": v for k, v in asdict(stoch).items()},
        }
        prefit_rows.append(row)
        if row["dominates_v3_prefit"]:
            dominating.append(row)

    pool = pd.DataFrame(prefit_rows)
    pool.to_csv(CANDIDATES_CSV, index=False)

    selected_row: dict[str, Any] | None = None
    selected_metrics: dict[str, dict[str, float]] | None = None
    selected_slices: dict[str, dict[str, float]] | None = None
    selected_macd: v3c.MACDV3CleanConfig | None = None
    selected_stoch: v3c.StochV3CleanConfig | None = None
    selected_trades: list[Any] | None = None
    execution_audit: dict[str, Any] | None = None

    if dominating:
        ranked = sorted(
            dominating,
            key=lambda row: (
                row["prefit_annual_multiple"],
                row["prefit_win_rate"],
                row["prefit_max_dd"],
            ),
            reverse=True,
        )
        selected_row = ranked[0]
        selected_macd = v3c.MACDV3CleanConfig(
            **{k[2:]: selected_row[f"m_{k[2:]}"] for k in [f"m_{f.name}" for f in fields(v3c.MACDV3CleanConfig)]}
        )
        selected_stoch = v3c.StochV3CleanConfig(
            **{f.name: selected_row[f"s_{f.name}"] for f in fields(v3c.StochV3CleanConfig)}
        )
        selected_trades, macd_trades, stoch_trades, _ = v3c.simulate_clean(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            macd=selected_macd,
            stoch=selected_stoch,
        )
        selected_metrics = v1.metrics(engine, selected_trades)
        selected_slices = v1.standard_slices(engine, selected_trades)
        pd.DataFrame(engine.trade_rows(selected_trades)).to_csv(TRADES_CSV, index=False)
        pd.DataFrame(
            [{"window": name, **metric} for name, metric in selected_slices.items()]
        ).to_csv(SLICES_CSV, index=False)

        base_configs = [
            v2.macd_to_base(engine, v3.macd_to_v2(v3c.macd_to_v3(selected_macd))),
            v2.stoch_to_base(engine, v3.stoch_to_v2(v3c.stoch_to_v3(selected_stoch))),
        ]
        audit_rows = strict_audit.trade_audit_rows(
            frame=frame,
            merged_trades=selected_trades,
            component_trades={
                base_configs[0].name: macd_trades,
                base_configs[1].name: stoch_trades,
            },
            configs=base_configs,
        )
        audit_frame = pd.DataFrame(audit_rows)
        audit_frame.to_csv(AUDIT_CSV, index=False)
        execution_audit = {
            "audited_rows": int(len(audit_frame)),
            "merged_trades": int(len(selected_trades)),
            "violation_count": int(audit_frame["violation_count"].sum()),
            "merged_violation_count": int(
                audit_frame.loc[audit_frame["scope"] == "merged", "violation_count"].sum()
            ),
            "stop_gap_filled_at_open": int(audit_frame["stop_gap_filled_at_open"].sum()),
            "target_gap_modeled_at_target": int(
                audit_frame["target_gap_modeled_at_target"].sum()
            ),
            "causal_entry_delay_all_ge_1": all(
                cfg.entry_delay_bars >= 1 for cfg in base_configs
            ),
        }

    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "baseline_version": "TRX-1H-Adaptive-Regime-V3",
        "date": DATE_TAG,
        "seed": SEED,
        "selection_policy": {
            "surface": "V3 clean tunable surface (31 slots; 5 dormant fields fixed)",
            "search": f"random neighborhood, 1-5 field changes, {N_CANDIDATES} draws",
            "search_uses": "train_validation_prefit_only",
            "hard_gate": (
                "prefit annual/win/DD all strictly better than V3; "
                "train/validation positive, DD > -20%, validation win >= 80%, "
                "train win >= V3 train win - 2pp"
            ),
            "reused_holdout": "read_only_after_freeze_not_used_for_selection",
            "recent_slices": "read_only_after_freeze_not_used_for_selection",
        },
        "search_counts": {
            "evaluated_unique": int(len(pool)),
            "dominating_v3_prefit": int(len(dominating)),
        },
        "v3_baseline": {"metrics": base_metrics, "standard_slices": base_slices},
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "data_quality": quality,
    }
    if selected_row is not None and selected_metrics is not None:
        assert selected_macd is not None and selected_stoch is not None
        payload["selected"] = {
            "observation_id": f"TRX-1H-AR-V3-CLEAN-TUNE-{DATE_TAG}",
            "changes": selected_row["changes"],
            "macd_flip": asdict(selected_macd),
            "stoch_reversal": asdict(selected_stoch),
            "metrics": selected_metrics,
            "standard_slices": selected_slices,
            "reused_holdout_gate_pass_after_freeze": bool(
                selected_metrics["reused_holdout"]["win_rate"] >= 0.80
                and selected_metrics["reused_holdout"]["max_dd"] > DD_FLOOR
                and selected_metrics["reused_holdout"]["total_return"] > 0.0
            ),
        }
        payload["execution_audit"] = execution_audit
    else:
        payload["selected"] = None
        payload["conclusion"] = (
            "no candidate on the V3 clean surface strictly dominated V3 on "
            "prefit annual + win rate + drawdown under the hard gates"
        )
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# TRX-1H-Adaptive-Regime-V3 clean 参数面微调 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "本轮在 V3 clean 参数面（31 个可调槽，5 个 dormant 字段固定为 V3 值）上做随机邻域微调；"
            "选择过程只使用 train/validation/prefit，不读取 reused holdout 或近期分片。"
            "硬约束要求 prefit 年化、胜率、回撤同时严格优于 V3。"
        ),
        "",
        f"- 唯一候选评估数：`{len(pool)}`（seed `{SEED}`，最多 `{N_CANDIDATES}` 次抽样）。",
        f"- prefit 三指标同时严格优于 V3 的候选：`{len(dominating)}`。",
    ]
    if selected_row is None:
        lines.extend(
            [
                "",
                (
                    "在该 clean 参数面与本轮搜索域内，没有候选能在 prefit 上同时做到"
                    "收益更高、胜率更高、回撤更小。结合 V3 全参数消融中 prefit 严格改善行为 `0`，"
                    "V3 在此参数面上已是局部最优；本轮为 no-hit 诊断结论，V3 参数保持不变。"
                ),
            ]
        )
    else:
        assert selected_metrics is not None and selected_slices is not None
        lines.extend(
            [
                f"- 选中观察值：`TRX-1H-AR-V3-CLEAN-TUNE-{DATE_TAG}`。",
                f"- 变更字段：`{selected_row['changes']}`。",
                "",
                "## V3 vs 微调观察",
                "",
                "| Window | V3 annual / return / DD / win / trades | Tune annual / return / DD / win / trades |",
                "| --- | --- | --- |",
            ]
        )
        for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
            lines.append(
                f"| `{window}` | {metric_line(base_metrics[window])} | "
                f"{metric_line(selected_metrics[window])} |"
            )
        lines.extend(
            [
                "",
                "## 标准近期分片",
                "",
                "| Slice | Annual / Return / DD / Win / Trades |",
                "| --- | --- |",
            ]
        )
        for name, metric in selected_slices.items():
            lines.append(f"| `{name}` | {metric_line(metric)} |")
        if execution_audit is not None:
            lines.extend(
                [
                    "",
                    "## 执行可行性复核",
                    "",
                    f"- 逐笔重放违规：`{execution_audit['violation_count']}`；merged 违规：`{execution_audit['merged_violation_count']}`。",
                    f"- stop gap/open 按 open 成交：`{execution_audit['stop_gap_filled_at_open']}` 次。",
                    f"- target gap 以 target 价保守记账：`{execution_audit['target_gap_modeled_at_target']}` 次。",
                    f"- 所有组件 `entry_delay_bars>=1`：`{execution_audit['causal_entry_delay_all_ge_1']}`。",
                ]
            )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 本轮为微调观察，不自动登记新版本；任何登记需用户明确指令。",
            "- reused holdout 已揭盲，只能做冻结后审计，不能作为 fresh OOS。",
            "- V3 家族当前仍为 `NO-GO / not promoted / not live-ready`。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{CANDIDATES_CSV.name}`",
        ]
    )
    if selected_row is not None:
        lines.extend(
            [
                f"- `artifacts/{TRADES_CSV.name}`",
                f"- `artifacts/{SLICES_CSV.name}`",
                f"- `artifacts/{AUDIT_CSV.name}`",
            ]
        )
    lines.extend(
        [
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v3_clean_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            search.json_safe(
                {
                    "evaluated_unique": len(pool),
                    "dominating_v3_prefit": len(dominating),
                    "selected": payload["selected"] is not None,
                    "selected_changes": selected_row["changes"] if selected_row else None,
                    "selected_prefit": selected_metrics["prefit"] if selected_metrics else None,
                    "selected_reused_holdout": selected_metrics["reused_holdout"]
                    if selected_metrics
                    else None,
                    "selected_current_full": selected_metrics["current_full"]
                    if selected_metrics
                    else None,
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
