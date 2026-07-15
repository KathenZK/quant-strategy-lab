from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from as6s_engine import REUSED_END
import combine_binance_as6s_v6_mark_microtuned_account as mark_micro
import combine_binance_as6s_v6_microtuned_account as account


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_microtuned_account_2026-07-15.json"
)
OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_micro_candidate_audit_2026-07-15.json"
)
REPORT = (
    FAMILY_DIR
    / "diagnostics/binance-as6s-v6-mark-micro-candidate-audit-2026-07-15.md"
)
MODES = ("nonpreemptive", "strong_breakout_preemptive")
SCALE_OFFSETS = (-0.12, -0.09, -0.06, -0.03, 0.0, 0.03, 0.06)
ROUTER_SETTINGS = (
    (0.70, 0.05, 1),
    (0.80, 0.05, 1),
    (0.75, 0.00, 1),
    (0.75, 0.10, 1),
    (0.75, 0.05, 0),
    (0.75, 0.05, 2),
    (0.75, 0.05, 4),
)
MIN_FREQUENCY_BUFFER = 1.01


def minimum_gate_win(result: dict[str, Any]) -> float:
    return min(
        result["scenarios"][scenario][window]["win_rate"]
        for scenario in account.SCENARIOS
        for window in ("full", "current_3m")
    )


def minimum_gate_dd(result: dict[str, Any]) -> float:
    return min(
        result["scenarios"][scenario][window]["max_dd"]
        for scenario in account.SCENARIOS
        for window in ("full", "current_3m")
    )


def compact(result: dict[str, Any]) -> dict[str, Any]:
    min_win = minimum_gate_win(result)
    min_dd = minimum_gate_dd(result)
    current_frequency = result["scenarios"]["base"]["current_3m"][
        "trades_per_day"
    ]
    all_six_frequency = result["scenarios"]["base"]["all_six_active"][
        "trades_per_day"
    ]
    return {
        "scale": result["scale"],
        "effective_max_leverage": result["effective_max_leverage"],
        "hard_pass": result["hard_pass"],
        "failed_checks": [
            name for name, passed in result["checks"].items() if not passed
        ],
        "score": result["score"],
        "minimum_gate_win": min_win,
        "minimum_gate_dd": min_dd,
        "robust_dd_buffer_pass": min_dd > account.ROBUST_DD_BUFFER,
        "win_buffer_81pct_pass": min_win >= 0.81,
        "current_frequency": current_frequency,
        "all_six_frequency": all_six_frequency,
        "frequency_buffer_pass": (
            MIN_FREQUENCY_BUFFER <= current_frequency <= 2.0
            and MIN_FREQUENCY_BUFFER <= all_six_frequency <= 2.0
        ),
        "base_full": result["scenarios"]["base"]["full"],
        "base_current_3m": result["scenarios"]["base"]["current_3m"],
        "stress_full": result["scenarios"]["stress_8bps"]["full"],
        "stress_current_3m": result["scenarios"]["stress_8bps"]["current_3m"],
        "k2_full": result["scenarios"]["k_plus_2"]["full"],
        "k2_current_3m": result["scenarios"]["k_plus_2"]["current_3m"],
    }


def result_delta(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, float]:
    base_full = baseline["scenarios"]["base"]["full"]
    base_current = baseline["scenarios"]["base"]["current_3m"]
    other_full = candidate["scenarios"]["base"]["full"]
    other_current = candidate["scenarios"]["base"]["current_3m"]
    return {
        "score": candidate["score"] - baseline["score"],
        "full_trades": other_full["trades"] - base_full["trades"],
        "full_win_rate": other_full["win_rate"] - base_full["win_rate"],
        "full_annual_multiple": (
            other_full["annual_multiple"] - base_full["annual_multiple"]
        ),
        "full_max_dd": other_full["max_dd"] - base_full["max_dd"],
        "current_trades": other_current["trades"] - base_current["trades"],
        "current_win_rate": (
            other_current["win_rate"] - base_current["win_rate"]
        ),
        "current_total_return": (
            other_current["total_return"] - base_current["total_return"]
        ),
        "current_frequency": (
            other_current["trades_per_day"] - base_current["trades_per_day"]
        ),
    }


def parity_check(
    actual: dict[str, Any], expected: dict[str, Any]
) -> dict[str, Any]:
    mismatches: list[str] = []
    if not math.isclose(
        float(actual["score"]),
        float(expected["score"]),
        rel_tol=0.0,
        abs_tol=1e-10,
    ):
        mismatches.append("score")
    for scenario in account.SCENARIOS:
        for window in ("full", "current_3m", "all_six_active"):
            for field in (
                "trades",
                "wins",
                "win_rate",
                "total_return",
                "max_dd",
                "trades_per_day",
            ):
                left = actual["scenarios"][scenario][window][field]
                right = expected["scenarios"][scenario][window][field]
                if not math.isclose(
                    float(left), float(right), rel_tol=0.0, abs_tol=1e-10
                ):
                    mismatches.append(f"{scenario}.{window}.{field}")
    return {"result": "PASS" if not mismatches else "FAIL", "mismatches": mismatches}


def summarize_pass_rate(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    count = len(rows)
    hard = sum(row["result"]["hard_pass"] for row in rows)
    buffered = sum(
        row["result"]["hard_pass"]
        and row["result"]["robust_dd_buffer_pass"]
        for row in rows
    )
    all_buffers = sum(
        row["result"]["hard_pass"]
        and row["result"]["robust_dd_buffer_pass"]
        and row["result"]["win_buffer_81pct_pass"]
        and row["result"]["frequency_buffer_pass"]
        for row in rows
    )
    return {
        "variants": count,
        "hard_passes": hard,
        "hard_pass_rate": hard / count if count else 0.0,
        "dd_buffer_passes": buffered,
        "dd_buffer_pass_rate": buffered / count if count else 0.0,
        "all_research_buffers_passes": all_buffers,
        "all_research_buffers_pass_rate": all_buffers / count if count else 0.0,
    }


def main() -> None:
    _trade_source, _manifest, frames, funding, sleeves, options = (
        mark_micro.prepare_mark_account_inputs()
    )
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    for mode in MODES:
        print(f"audit mode {mode}", flush=True)
        source_row = source["results"][mode]
        selection = mark_micro.seed_selection(
            sleeves, options, source_row["selection"]
        )
        selected_scale = float(source_row["result"]["scale"])
        baseline_routed = account.route_scenarios(
            selection,
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        baseline = account.scale_result(baseline_routed, selected_scale)
        parity = parity_check(baseline, source_row["result"])
        if parity["result"] != "PASS":
            raise RuntimeError(f"{mode} source parity failed: {parity['mismatches']}")

        drop_rows: list[dict[str, Any]] = []
        for sleeve_index, sleeve in enumerate(sleeves):
            if selection[sleeve_index] < 0:
                continue
            proposal = list(selection)
            proposal[sleeve_index] = -1
            routed = account.route_scenarios(
                tuple(proposal),
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
            candidate = account.scale_result(routed, selected_scale)
            row = compact(candidate)
            drop_rows.append(
                {
                    "sleeve": sleeve,
                    "result": row,
                    "delta": result_delta(baseline, candidate),
                    "dispensable": (
                        row["hard_pass"]
                        and row["robust_dd_buffer_pass"]
                        and candidate["score"] >= baseline["score"] - 1e-12
                    ),
                }
            )

        scale_rows: list[dict[str, Any]] = []
        for offset in SCALE_OFFSETS:
            scale = round(selected_scale + offset, 2)
            candidate = account.scale_result(baseline_routed, scale)
            scale_rows.append(
                {
                    "offset": offset,
                    "result": compact(candidate),
                    "score_delta": candidate["score"] - baseline["score"],
                }
            )

        router_rows: list[dict[str, Any]] = []
        if mode == "strong_breakout_preemptive":
            for threshold, margin, min_hold in ROUTER_SETTINGS:
                routed = account.route_scenarios(
                    selection,
                    sleeves,
                    options,
                    mode=mode,
                    frames=frames,
                    funding=funding,
                    preemption_threshold=threshold,
                    preemption_margin=margin,
                    preemption_min_hold_hours=min_hold,
                )
                candidate = account.scale_result(routed, selected_scale)
                router_rows.append(
                    {
                        "threshold": threshold,
                        "margin": margin,
                        "min_hold_hours": min_hold,
                        "result": compact(candidate),
                        "score_delta": candidate["score"] - baseline["score"],
                    }
                )

        option_rows: list[dict[str, Any]] = []
        for sleeve_index, sleeve in enumerate(sleeves):
            selected_option = selection[sleeve_index]
            if selected_option < 0:
                continue
            for option_index, option in enumerate(options[sleeve]):
                if option_index == selected_option:
                    continue
                proposal = list(selection)
                proposal[sleeve_index] = option_index
                routed = account.route_scenarios(
                    tuple(proposal),
                    sleeves,
                    options,
                    mode=mode,
                    frames=frames,
                    funding=funding,
                )
                candidate = account.scale_result(routed, selected_scale)
                option_rows.append(
                    {
                        "sleeve": sleeve,
                        "selected_option": options[sleeve][selected_option][
                            "option_id"
                        ],
                        "replacement_option": option["option_id"],
                        "result": compact(candidate),
                        "delta": result_delta(baseline, candidate),
                    }
                )

        per_sleeve: dict[str, Any] = {}
        for sleeve in sleeves:
            rows = [row for row in option_rows if row["sleeve"] == sleeve]
            if rows:
                per_sleeve[sleeve] = summarize_pass_rate(rows)

        results[mode] = {
            "selection": source_row["selection"],
            "selected_scale": selected_scale,
            "source_parity": parity,
            "baseline": compact(baseline),
            "drop_ablation": drop_rows,
            "dispensable_sleeves": [
                row["sleeve"] for row in drop_rows if row["dispensable"]
            ],
            "scale_neighborhood": scale_rows,
            "scale_summary": summarize_pass_rate(scale_rows),
            "router_neighborhood": router_rows,
            "router_summary": summarize_pass_rate(router_rows),
            "option_substitution_neighborhood": option_rows,
            "option_substitution_summary": summarize_pass_rate(option_rows),
            "option_substitution_by_sleeve": per_sleeve,
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_micro_candidate_final_audit_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "hard_gate": (
            "unchanged: base/stress/K+2 full and current win>=80%, DD<20%, "
            "return>0; base current/all-six frequency 1-2/day; leverage<=3x"
        ),
        "research_buffers": {
            "minimum_gate_win": 0.81,
            "minimum_gate_dd_strictly_above": account.ROBUST_DD_BUFFER,
            "base_current_and_all_six_frequency": [
                MIN_FREQUENCY_BUFFER,
                2.0,
            ],
            "note": "diagnostic margins only; they do not alter the user hard gate",
        },
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BIN-15M-AS6S V6 最新mark候选最终审计（2026-07-15）",
        "",
        "对mark语义联合微调后的最新选择重做逐腿删除、scale邻域、抢占路由邻域和每腿其余稳健配置单替换。未来OOS未读取。",
        "",
        "用户硬门槛保持不变；另外报告81%最低压力胜率、-18.5%回撤和1.01单/日频率研究缓冲。",
        "",
        "| 路线 | 对拍 | 可删除腿 | scale硬通过率 | 路由硬通过率 | 单替换硬通过率 | 单替换全缓冲通过率 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        scale_summary = row["scale_summary"]
        router_summary = row["router_summary"]
        option_summary = row["option_substitution_summary"]
        router_text = (
            f"{router_summary['hard_pass_rate']:.2%}"
            if router_summary["variants"]
            else "不适用"
        )
        lines.append(
            f"| `{mode}` | `{row['source_parity']['result']}` | "
            f"{len(row['dispensable_sleeves'])} | "
            f"{scale_summary['hard_pass_rate']:.2%} | {router_text} | "
            f"{option_summary['hard_pass_rate']:.2%} | "
            f"{option_summary['all_research_buffers_pass_rate']:.2%} |"
        )
    lines.extend(["", "## 逐腿删除结论", ""])
    for mode, row in results.items():
        lines.append(
            f"- `{mode}`：可删除腿 `{row['dispensable_sleeves'] or '无'}`。"
        )
    lines.extend(
        [
            "",
            "## 邻域薄弱点",
            "",
        ]
    )
    for mode, row in results.items():
        weak = sorted(
            row["option_substitution_by_sleeve"].items(),
            key=lambda item: item[1]["all_research_buffers_pass_rate"],
        )[:5]
        lines.append(f"- `{mode}`最低全缓冲通过腿：")
        for sleeve, stats in weak:
            lines.append(
                f"  - `{sleeve}`：硬门槛 {stats['hard_pass_rate']:.2%}，"
                f"全部研究缓冲 {stats['all_research_buffers_pass_rate']:.2%}。"
            )
    lines.extend(
        [
            "",
            f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "results": {
                    mode: {
                        "source_parity": row["source_parity"]["result"],
                        "dispensable_sleeves": row["dispensable_sleeves"],
                        "scale": row["scale_summary"],
                        "router": row["router_summary"],
                        "option_substitution": row[
                            "option_substitution_summary"
                        ],
                    }
                    for mode, row in results.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
