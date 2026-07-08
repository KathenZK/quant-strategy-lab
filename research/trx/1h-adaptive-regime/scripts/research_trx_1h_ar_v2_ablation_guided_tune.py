from __future__ import annotations

import json
import sys
from dataclasses import asdict
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


DATE_TAG = "2026-07-06"
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
PAIR_POOL_CSV = ARTIFACT_DIR / "trx_1h_ar_v1_tune_pairs_2026-07-05.csv"
V2_ABLATION_JSON = ARTIFACT_DIR / f"trx_1h_ar_v2_full_ablation_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v2_ablation_guided_tune_{DATE_TAG}.json"
CANDIDATES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_ablation_guided_tune_candidates_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_ablation_guided_tune_trades_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_ablation_guided_tune_slices_{DATE_TAG}.csv"
AUDIT_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_ablation_guided_tune_execution_audit_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"trx-1h-ar-v2-ablation-guided-tune-{DATE_TAG}.md"

WIN_FLOOR = 0.80
DD_FLOOR = -0.20


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes"}


def macd_from_row(row: Any) -> v2.MACDV2Config:
    return v2.MACDV2Config(
        ema_htf=int(row.m_ema_htf),
        roc_window=int(row.m_roc_window),
        macd_fast=int(row.m_macd_fast),
        macd_slow=int(row.m_macd_slow),
        macd_signal=int(row.m_macd_signal),
        min_adx=float(row.m_min_adx),
        max_adx=float(row.m_max_adx),
        min_rvol=float(row.m_min_rvol),
        max_atr_bps=float(row.m_max_atr_bps),
        min_dir_roc_bps=float(row.m_min_dir_roc_bps),
        max_dist_ema_bps=float(row.m_max_dist_ema_bps),
        htf_mode=str(row.m_htf_mode),
        require_macd_turn=to_bool(row.m_require_macd_turn),
        tp_atr=float(row.m_tp_atr),
        sl_atr=float(row.m_sl_atr),
        max_hold_bars=int(row.m_max_hold_bars),
        cooldown_bars=int(row.m_cooldown_bars),
        entry_delay_bars=int(row.m_entry_delay_bars),
        fixed_leverage=float(row.m_fixed_leverage),
    )


def stoch_from_row(row: Any) -> v2.StochV2Config:
    return v2.StochV2Config(
        side_mode=str(row.s_side_mode),
        ema_htf=int(row.s_ema_htf),
        indicator_window=int(row.s_indicator_window),
        threshold_low=float(row.s_threshold_low),
        threshold_high=float(row.s_threshold_high),
        roc_window=int(row.s_roc_window),
        max_adx=float(row.s_max_adx),
        min_rvol=float(row.s_min_rvol),
        min_dir_roc_bps=float(row.s_min_dir_roc_bps),
        require_body_dir=to_bool(row.s_require_body_dir),
        sl_atr=float(row.s_sl_atr),
        trail_activation_atr=float(row.s_trail_activation_atr),
        trail_atr=float(row.s_trail_atr),
        max_hold_bars=int(row.s_max_hold_bars),
        cooldown_bars=int(row.s_cooldown_bars),
        entry_delay_bars=int(row.s_entry_delay_bars),
        fixed_leverage=float(row.s_fixed_leverage),
    )


def metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.metrics(engine, trades)


def slices(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.standard_slices(engine, trades)


def flatten(prefix: str, values: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def selection_mask(pool: pd.DataFrame, reference_prefit_annual: float) -> pd.Series:
    return (
        (pool["train_win_rate"] >= WIN_FLOOR)
        & (pool["validation_win_rate"] >= WIN_FLOOR)
        & (pool["prefit_win_rate"] >= WIN_FLOOR)
        & (pool["train_max_dd"] > DD_FLOOR)
        & (pool["validation_max_dd"] > DD_FLOOR)
        & (pool["prefit_max_dd"] > DD_FLOOR)
        & (pool["train_total_return"] > 0.0)
        & (pool["validation_total_return"] > 0.0)
        & (pool["prefit_annual_multiple"] > reference_prefit_annual)
    )


def simulate_pair(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    macd: v2.MACDV2Config,
    stoch: v2.StochV2Config,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    return v2.simulate_v2(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        macd=macd,
        stoch=stoch,
    )


def audit_candidate(
    *,
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    source_index: int,
    row: Any,
) -> tuple[dict[str, Any], list[Any], v2.MACDV2Config, v2.StochV2Config]:
    macd = macd_from_row(row)
    stoch = stoch_from_row(row)
    trades, _macd_trades, _stoch_trades, _priorities = simulate_pair(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        macd,
        stoch,
    )
    bundle = metrics(engine, trades)
    recent = slices(engine, trades)
    record: dict[str, Any] = {
        "source_row": source_index,
        "selected_by": "train_validation_prefit_only",
        **flatten("train", bundle["train"]),
        **flatten("validation", bundle["validation"]),
        **flatten("prefit", bundle["prefit"]),
        **flatten("reused_holdout", bundle["reused_holdout"]),
        **flatten("current_full", bundle["current_full"]),
        **flatten("last_1m", recent["last_1m"]),
        **flatten("last_3m", recent["last_3m"]),
        **flatten("last_6m", recent["last_6m"]),
        **flatten("last_1y", recent["last_1y"]),
        **{f"m_{key}": value for key, value in asdict(macd).items()},
        **{f"s_{key}": value for key, value in asdict(stoch).items()},
    }
    return record, trades, macd, stoch


def main() -> None:
    if not PAIR_POOL_CSV.exists():
        raise FileNotFoundError("Run clean tune pair search before V2 ablation-guided tune")
    if not V2_ABLATION_JSON.exists():
        raise FileNotFoundError("Run V2 full ablation before V2 ablation-guided tune")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    engine, frame, funding, quality = v2.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    baseline_trades, *_ = v2.simulate_v2(
        engine,
        frame,
        funding_times,
        funding_cumulative,
    )
    baseline_metrics = metrics(engine, baseline_trades)
    baseline_slices = slices(engine, baseline_trades)
    reference_prefit_annual = baseline_metrics["prefit"]["annual_multiple"]

    pool = pd.read_csv(PAIR_POOL_CSV)
    mask = selection_mask(pool, reference_prefit_annual)
    eligible = pool.loc[mask].copy()
    if eligible.empty:
        raise RuntimeError("No pair candidate satisfied the V2 tune hard gates")
    eligible = eligible.sort_values(
        ["prefit_annual_multiple", "prefit_win_rate", "validation_annual_multiple"],
        ascending=[False, False, False],
    )

    audited_rows: list[dict[str, Any]] = []
    selected_trades: list[Any] | None = None
    selected_macd: v2.MACDV2Config | None = None
    selected_stoch: v2.StochV2Config | None = None
    selected_source_row: int | None = None
    for source_index, row in eligible.iterrows():
        audited, trades, macd, stoch = audit_candidate(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            source_index=int(source_index),
            row=row,
        )
        audited_rows.append(audited)
        if selected_trades is None:
            selected_trades = trades
            selected_macd = macd
            selected_stoch = stoch
            selected_source_row = int(source_index)

    assert selected_trades is not None
    assert selected_macd is not None
    assert selected_stoch is not None
    assert selected_source_row is not None

    candidates = pd.DataFrame(audited_rows)
    candidates.to_csv(CANDIDATES_CSV, index=False)
    selected_metrics = metrics(engine, selected_trades)
    selected_slices = slices(engine, selected_trades)
    slice_rows = [
        {"window": name, **metric}
        for name, metric in selected_slices.items()
    ]
    pd.DataFrame(slice_rows).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected_trades)).to_csv(TRADES_CSV, index=False)

    macd_base = v2.macd_to_base(engine, selected_macd)
    stoch_base = v2.stoch_to_base(engine, selected_stoch)
    _merged, macd_trades, stoch_trades, _priorities = simulate_pair(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        selected_macd,
        selected_stoch,
    )
    component_trades = {
        macd_base.name: macd_trades,
        stoch_base.name: stoch_trades,
    }
    audit_rows = strict_audit.trade_audit_rows(
        frame=frame,
        merged_trades=selected_trades,
        component_trades=component_trades,
        configs=[macd_base, stoch_base],
    )
    audit_frame = pd.DataFrame(audit_rows)
    audit_frame.to_csv(AUDIT_CSV, index=False)
    execution_audit = {
        "audited_rows": int(len(audit_frame)),
        "merged_trades": int(len(selected_trades)),
        "merged_full_window_trades": int(selected_metrics["current_full"]["trades"]),
        "violation_count": int(audit_frame["violation_count"].sum()),
        "merged_violation_count": int(
            audit_frame.loc[audit_frame["scope"] == "merged", "violation_count"].sum()
        ),
        "stop_gap_filled_at_open": int(audit_frame["stop_gap_filled_at_open"].sum()),
        "target_gap_modeled_at_target": int(audit_frame["target_gap_modeled_at_target"].sum()),
        "causal_entry_delay_all_ge_1": all(
            cfg.entry_delay_bars >= 1 for cfg in (macd_base, stoch_base)
        ),
    }
    full_gate_pass = bool(
        selected_metrics["current_full"]["annual_multiple"]
        > baseline_metrics["current_full"]["annual_multiple"]
        and selected_metrics["current_full"]["win_rate"] >= WIN_FLOOR
        and selected_metrics["current_full"]["max_dd"] > DD_FLOOR
    )
    prefit_gate_pass = bool(
        selected_metrics["train"]["win_rate"] >= WIN_FLOOR
        and selected_metrics["validation"]["win_rate"] >= WIN_FLOOR
        and selected_metrics["prefit"]["win_rate"] >= WIN_FLOOR
        and selected_metrics["train"]["max_dd"] > DD_FLOOR
        and selected_metrics["validation"]["max_dd"] > DD_FLOOR
        and selected_metrics["prefit"]["max_dd"] > DD_FLOOR
        and selected_metrics["prefit"]["annual_multiple"] > reference_prefit_annual
    )
    holdout_gate_pass = bool(
        selected_metrics["reused_holdout"]["win_rate"] >= WIN_FLOOR
        and selected_metrics["reused_holdout"]["max_dd"] > DD_FLOOR
        and selected_metrics["reused_holdout"]["total_return"] > 0.0
    )

    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "baseline_version": "TRX-1H-Adaptive-Regime-V2",
        "observation_id": "TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06",
        "registered_version": "TRX-1H-Adaptive-Regime-V3",
        "status": "registered_as_v3_diagnostic_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "candidate_source": "V2 clean-surface pair pool plus V2 full-ablation hard gates",
            "hard_gate": "train/validation/prefit win>=80%, DD<20%, positive train/validation, prefit annual above V2",
            "reused_holdout": "read_only_after_freeze_not_used_for_selection",
            "recent_slices": "read_only_after_freeze_not_used_for_selection",
        },
        "search_counts": {
            "pair_pool_rows": int(len(pool)),
            "eligible_prefit_hard_gate": int(len(eligible)),
            "audited_after_freeze": int(len(audited_rows)),
            "selected_source_row": selected_source_row,
        },
        "baseline": {
            "metrics": baseline_metrics,
            "standard_slices": baseline_slices,
        },
        "selected": {
            "macd_flip": asdict(selected_macd),
            "stoch_reversal": asdict(selected_stoch),
            "metrics": selected_metrics,
            "standard_slices": selected_slices,
            "prefit_gate_pass": prefit_gate_pass,
            "full_gate_pass_after_freeze": full_gate_pass,
            "reused_holdout_gate_pass_after_freeze": holdout_gate_pass,
        },
        "execution_audit": execution_audit,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "artifacts": {
            "candidates_csv": str(CANDIDATES_CSV.relative_to(ROOT)),
            "trades_csv": str(TRADES_CSV.relative_to(ROOT)),
            "slices_csv": str(SLICES_CSV.relative_to(ROOT)),
            "execution_audit_csv": str(AUDIT_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# TRX-1H-Adaptive-Regime-V2 消融引导微调 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            "本轮基于 V2 clean 参数面和 V2 全参数消融后的可调字段做微调；"
            "选择过程只使用 train/validation/prefit，不读取 reused holdout 或近期分片。"
        ),
        "",
        f"- pair pool：`{len(pool)}`；满足 train/validation/prefit `win>=80%`、DD `<20%`、prefit annual 高于 V2 的候选：`{len(eligible)}`。",
        f"- 选中观察值：`TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06`，source row `{selected_source_row}`；后续按用户明确指令正式登记为 `TRX-1H-Adaptive-Regime-V3`。",
        f"- prefit gate pass：`{prefit_gate_pass}`；冻结后 current full gate pass：`{full_gate_pass}`；reused holdout gate pass：`{holdout_gate_pass}`。",
        "",
        "## V2 vs V3",
        "",
        "| Window | V2 annual / return / DD / win / trades | V3 annual / return / DD / win / trades |",
        "| --- | --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(
            f"| `{window}` | {metric_line(baseline_metrics[window])} | "
            f"{metric_line(selected_metrics[window])} |"
        )
    lines.extend(
        [
            "",
            "## 冻结参数",
            "",
            "### MACD V3 登记参数",
            "",
        ]
    )
    lines.extend(f"- `{key}` = `{value}`" for key, value in asdict(selected_macd).items())
    lines.extend(["", "### Stochastic V3 登记参数", ""])
    lines.extend(f"- `{key}` = `{value}`" for key, value in asdict(selected_stoch).items())
    lines.extend(
        [
            "",
            "## 标准近期分片",
            "",
            "| Slice | Annual / Return / DD / Win / Trades |",
            "| --- | --- |",
        ]
    )
    for window in ("last_1d", "last_7d", "last_1m", "last_3m", "last_6m", "last_1y"):
        lines.append(f"| `{window}` | {metric_line(selected_slices[window])} |")
    lines.extend(
        [
            "",
            "## 执行可行性复核",
            "",
            f"- 逐笔重放违规：`{execution_audit['violation_count']}`；merged 违规：`{execution_audit['merged_violation_count']}`。",
            f"- stop gap/open 按 open 成交：`{execution_audit['stop_gap_filled_at_open']}` 次。",
            f"- target gap 以 target 价保守记账：`{execution_audit['target_gap_modeled_at_target']}` 次。",
            f"- 所有组件 `entry_delay_bars>=1`：`{execution_audit['causal_entry_delay_all_ge_1']}`。",
            "",
            "## 研究边界",
            "",
            "- 这是 `TRX-1H-Adaptive-Regime-V2` 的微调观察值，已按后续用户明确指令登记为 `TRX-1H-Adaptive-Regime-V3`；登记不等于 promotion。",
            "- reused holdout 已在初始研究中揭盲，只能做冻结后失败/边界审计，不能作为 fresh OOS。",
            "- 虽然 full 收益、胜率和回撤满足本次目标，但 reused holdout 胜率未达 80%，且没有新增 forward trades 和 TRX production runner，因此 V3 仍不得 promotion。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{CANDIDATES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{AUDIT_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v2_ablation_guided_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
