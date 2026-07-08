from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v1_full_ablation as v1_ablation  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402


DATE_TAG = "2026-07-06"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTE_DIR = FAMILY_DIR / "notes"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v2_ablation_combo_retest_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_ablation_combo_retest_rows_{DATE_TAG}.csv"
WINDOWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_ablation_combo_retest_windows_{DATE_TAG}.csv"
REPORT_MD = NOTE_DIR / f"hype-1h-ar-v2-ablation-combo-retest-{DATE_TAG}.md"

TRAIN_START = v1_ablation.TRAIN_START
PREFIT_END = v1_ablation.PREFIT_END

SCENARIOS = (
    ("base_k1", 0.0010, 0.0004, 1),
    ("delay_k2", 0.0010, 0.0004, 2),
    ("slip_8bps", 0.0010, 0.0008, 1),
)


def di_candidates() -> list[tuple[str, v2.DICleanConfig]]:
    baseline = v2.DICleanConfig()
    return [
        ("di_base", baseline),
        ("di_roc_off", replace(baseline, min_dir_roc_bps=-10_000.0)),
        ("di_roc12", replace(baseline, roc_window=12)),
        (
            "di_roc12_off",
            replace(baseline, roc_window=12, min_dir_roc_bps=-10_000.0),
        ),
    ]


def stoch_candidates() -> list[tuple[str, v2.StochCleanConfig]]:
    baseline = v2.StochCleanConfig()
    return [
        ("stoch_base", baseline),
        ("stoch_th55", replace(baseline, threshold_high=55.0)),
        ("stoch_trail05", replace(baseline, trail_atr=0.5)),
        ("stoch_th55_trail05", replace(baseline, threshold_high=55.0, trail_atr=0.5)),
    ]


def simulate_combo(
    *,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    di_cfg: v2.DICleanConfig,
    stoch_cfg: v2.StochCleanConfig,
    combo_id: str,
    fee: float,
    slippage: float,
    delay: int,
) -> list[base.Trade]:
    original_fee = base.FEE_PER_FILL
    original_slippage = base.SLIPPAGE_PER_FILL
    try:
        base.FEE_PER_FILL = fee
        base.SLIPPAGE_PER_FILL = slippage
        di_base = replace(v2.di_to_base(di_cfg, f"{combo_id}_DI"), entry_delay_bars=delay)
        stoch_base = replace(
            v2.stoch_to_base(stoch_cfg, f"{combo_id}_STOCH"), entry_delay_bars=delay
        )
        di_trades = boundary.component_trades(
            frame, funding_times, funding_cumulative, di_base
        )
        stoch_trades = boundary.component_trades(
            frame, funding_times, funding_cumulative, stoch_base
        )
        return base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)
    finally:
        base.FEE_PER_FILL = original_fee
        base.SLIPPAGE_PER_FILL = original_slippage


def prefixed_metrics(
    trades: list[base.Trade], full_end: pd.Timestamp, prefix: str
) -> dict[str, Any]:
    windows = (
        ("prefit", TRAIN_START, PREFIT_END),
        ("reused_holdout", PREFIT_END, full_end),
        ("current_full", TRAIN_START, full_end),
    )
    output: dict[str, Any] = {}
    for name, start, end in windows:
        values = base.metrics(trades, start, end)
        output.update({f"{prefix}_{name}_{key}": value for key, value in values.items()})
    return output


def recent_rows(
    combo_id: str, trades: list[base.Trade], full_end: pd.Timestamp
) -> list[dict[str, Any]]:
    windows = [
        ("last_7d", max(TRAIN_START, full_end - pd.Timedelta(days=7)), full_end),
        ("last_30d", max(TRAIN_START, full_end - pd.Timedelta(days=30)), full_end),
        ("last_90d", max(TRAIN_START, full_end - pd.Timedelta(days=90)), full_end),
        ("last_180d", max(TRAIN_START, full_end - pd.Timedelta(days=180)), full_end),
        ("last_365d", max(TRAIN_START, full_end - pd.Timedelta(days=365)), full_end),
    ]
    return [
        {"combo_id": combo_id, "window": name, "start": start, "end": end, **base.metrics(trades, start, end)}
        for name, start, end in windows
    ]


def gate_from_row(row: dict[str, Any], prefix: str) -> bool:
    holdout = {
        key.removeprefix(f"{prefix}_reused_holdout_"): value
        for key, value in row.items()
        if key.startswith(f"{prefix}_reused_holdout_")
    }
    full = {
        key.removeprefix(f"{prefix}_current_full_"): value
        for key, value in row.items()
        if key.startswith(f"{prefix}_current_full_")
    }
    return base.target_gate(holdout, full)


def pct(value: float) -> str:
    return base.pct(float(value))


def mult(value: float) -> str:
    return base.mult(float(value), digits=4)


def markdown_rows(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Combo | Base annual | Base DD | Base win | Holdout annual | Holdout DD | K+2 full/DD | 8bps full/DD | Gates |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        gates = []
        if row["base_k1_target_pass"]:
            gates.append("base")
        if row["delay_k2_target_pass"]:
            gates.append("K+2")
        if row["slip_8bps_target_pass"]:
            gates.append("8bps")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['combo_id']}`",
                    mult(row["base_k1_current_full_annual_multiple"]),
                    pct(row["base_k1_current_full_max_dd"]),
                    pct(row["base_k1_current_full_win_rate"]),
                    mult(row["base_k1_reused_holdout_annual_multiple"]),
                    pct(row["base_k1_reused_holdout_max_dd"]),
                    f"{mult(row['delay_k2_current_full_annual_multiple'])} / {pct(row['delay_k2_current_full_max_dd'])}",
                    f"{mult(row['slip_8bps_current_full_annual_multiple'])} / {pct(row['slip_8bps_current_full_max_dd'])}",
                    ", ".join(gates) if gates else "-",
                ]
            )
            + " |"
        )
    return lines


def report_markdown(
    *,
    rows: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    quality: dict[str, Any],
    full_end: pd.Timestamp,
) -> str:
    ranked = sorted(
        rows,
        key=lambda row: (
            row["all_scenario_target_pass"],
            row["base_k1_target_pass"],
            row["base_k1_current_full_annual_multiple"],
            row["base_k1_current_full_max_dd"],
        ),
        reverse=True,
    )
    base_row = next(row for row in rows if row["combo_id"] == "di_base__stoch_base")
    best = ranked[0]
    full_pass = sum(row["base_k1_target_pass"] for row in rows)
    all_pass = sum(row["all_scenario_target_pass"] for row in rows)
    lines = [
        "# HYPE-1H-Adaptive-Regime-V2 消融引导组合复测 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            f"本轮只复测 V2 全参数消融提示的少量组合：DI `4` 个候选 × Stoch `4` 个候选，"
            f"共 `{len(rows)}` 个组合；每个组合跑 base K+1、K+2 延迟和 8 bps/fill 滑点。"
        ),
        "",
        (
            f"base K+1 target gate 通过 `{full_pass}/{len(rows)}`；"
            f"K+2 与 8bps 同时通过 `{all_pass}/{len(rows)}`。"
        ),
        "",
        (
            f"最佳 base 排名组合 `{best['combo_id']}`：current full "
            f"`{mult(best['base_k1_current_full_annual_multiple'])}`、"
            f"DD `{pct(best['base_k1_current_full_max_dd'])}`、"
            f"胜率 `{pct(best['base_k1_current_full_win_rate'])}`；"
            f"reused holdout `{mult(best['base_k1_reused_holdout_annual_multiple'])}`、"
            f"DD `{pct(best['base_k1_reused_holdout_max_dd'])}`。"
        ),
        "",
        (
            "结论：如果只看 base K+1，`di_roc12_off` 方向显著优于 V2 baseline；"
            "但 K+2 延迟或 8bps 滑点下仍无法形成完整稳健通过，因此本轮仍不登记 `V2.1/V3`。"
        ),
        "",
        "## 数据与口径",
        "",
        f"- 数据：Binance HYPEUSDT perpetual `1h` closed-only，`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`。",
        f"- 当前评估终点：`{full_end.isoformat()}`。",
        "- 成本：base 为 `0.001` fee/fill + `4 bps` slippage/fill；压力为 K+2 延迟和 `8 bps` slippage/fill。",
        "- 资金费：逐笔计入 Binance 历史 funding。",
        "- Reused holdout 已解锁，只能用于诊断，不能重新包装为 untouched OOS。",
        "",
        "## 组合排名",
        "",
        *markdown_rows(ranked),
        "",
        "## Baseline 对照",
        "",
        (
            f"`di_base__stoch_base`：current full `{mult(base_row['base_k1_current_full_annual_multiple'])}`、"
            f"DD `{pct(base_row['base_k1_current_full_max_dd'])}`、"
            f"胜率 `{pct(base_row['base_k1_current_full_win_rate'])}`；"
            f"reused holdout `{mult(base_row['base_k1_reused_holdout_annual_multiple'])}`。"
        ),
        "",
        "## 最近窗口提示",
        "",
    ]
    best_windows = [row for row in windows if row["combo_id"] == best["combo_id"]]
    lines.extend(
        [
            "| Window | Trades | Win | Return | DD | Annual |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in best_windows:
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(row['win_rate'])}` | "
            f"`{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | `{mult(row['annual_multiple'])}` |"
        )
    lines.extend(
        [
            "",
            "## 机器证据",
            "",
            f"- JSON：`artifacts/{SUMMARY_JSON.name}`",
            f"- 组合 CSV：`artifacts/{ROWS_CSV.name}`",
            f"- 最近窗口 CSV：`artifacts/{WINDOWS_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_ablation_combo_retest.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)

    rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for di_name, di_cfg in di_candidates():
        for stoch_name, stoch_cfg in stoch_candidates():
            combo_id = f"{di_name}__{stoch_name}"
            row: dict[str, Any] = {
                "combo_id": combo_id,
                "di_name": di_name,
                "stoch_name": stoch_name,
                "di_config": asdict(di_cfg),
                "stoch_config": asdict(stoch_cfg),
            }
            for scenario, fee, slippage, delay in SCENARIOS:
                trades = simulate_combo(
                    frame=frame,
                    funding_times=funding_times,
                    funding_cumulative=funding_cumulative,
                    di_cfg=di_cfg,
                    stoch_cfg=stoch_cfg,
                    combo_id=f"{combo_id}__{scenario}",
                    fee=fee,
                    slippage=slippage,
                    delay=delay,
                )
                row.update(prefixed_metrics(trades, full_end, scenario))
                if scenario == "base_k1":
                    window_rows.extend(recent_rows(combo_id, trades, full_end))
            for scenario, *_rest in SCENARIOS:
                row[f"{scenario}_target_pass"] = gate_from_row(row, scenario)
            row["all_scenario_target_pass"] = all(
                row[f"{scenario}_target_pass"] for scenario, *_rest in SCENARIOS
            )
            rows.append(row)

    rows = sorted(
        rows,
        key=lambda row: (
            row["all_scenario_target_pass"],
            row["base_k1_target_pass"],
            row["base_k1_current_full_annual_multiple"],
            row["base_k1_current_full_max_dd"],
        ),
        reverse=True,
    )
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "base_version": "HYPE-1H-Adaptive-Regime-V2",
        "status": "diagnostic_combo_retest_not_live_ready_not_promoted",
        "data_quality": quality,
        "full_end": full_end,
        "scenarios": [
            {"name": name, "fee_per_fill": fee, "slippage_per_fill": slippage, "entry_delay_bars": delay}
            for name, fee, slippage, delay in SCENARIOS
        ],
        "combo_count": len(rows),
        "base_target_pass_count": int(sum(row["base_k1_target_pass"] for row in rows)),
        "all_scenario_target_pass_count": int(
            sum(row["all_scenario_target_pass"] for row in rows)
        ),
        "rows": rows,
        "recent_windows": window_rows,
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    pd.DataFrame(base.json_safe(rows)).to_csv(ROWS_CSV, index=False)
    pd.DataFrame(base.json_safe(window_rows)).to_csv(WINDOWS_CSV, index=False)
    REPORT_MD.write_text(
        report_markdown(rows=rows, windows=window_rows, quality=quality, full_end=full_end),
        encoding="utf-8",
    )
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
