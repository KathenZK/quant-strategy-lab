from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import combine_binance_as6s_v6_microtuned_account as account


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_account_neighborhood_2026-07-15.json"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-account-neighborhood-2026-07-15.md"


def find_index(
    sleeve: str,
    option_id: str,
    options: dict[str, list[dict[str, Any]]],
) -> int:
    if option_id == "dropped":
        return -1
    return next(
        index
        for index, row in enumerate(options[sleeve])
        if row["option_id"] == option_id
    )


def summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "scale": result["scale"],
        "hard_pass": result["hard_pass"],
        "failed_checks": [
            name for name, passed in result["checks"].items() if not passed
        ],
        "score": result["score"],
        "base_full": result["scenarios"]["base"]["full"],
        "base_current_3m": result["scenarios"]["base"]["current_3m"],
        "stress_full": result["scenarios"]["stress_8bps"]["full"],
        "stress_current_3m": result["scenarios"]["stress_8bps"]["current_3m"],
        "k2_full": result["scenarios"]["k_plus_2"]["full"],
        "k2_current_3m": result["scenarios"]["k_plus_2"]["current_3m"],
    }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    _manifest, _reference, frames, funding, sleeves, options = (
        account.prepare_account_inputs()
    )
    results: dict[str, Any] = {}
    for mode, mode_source in source["results"].items():
        selected = tuple(
            find_index(sleeve, mode_source["selection"][sleeve]["option"], options)
            for sleeve in sleeves
        )
        scale = float(mode_source["result"]["scale"])
        routed = account.route_scenarios(
            selected,
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        baseline = account.scale_result(routed, scale)
        option_rows: list[dict[str, Any]] = []
        for sleeve_index, sleeve in enumerate(sleeves):
            if selected[sleeve_index] < 0:
                continue
            for neighbor_index, option in enumerate(options[sleeve]):
                if neighbor_index == selected[sleeve_index]:
                    continue
                variant = list(selected)
                variant[sleeve_index] = neighbor_index
                candidate_routed = account.route_scenarios(
                    tuple(variant),
                    sleeves,
                    options,
                    mode=mode,
                    frames=frames,
                    funding=funding,
                )
                result = account.scale_result(candidate_routed, scale)
                option_rows.append(
                    {
                        "sleeve": sleeve,
                        "from_option": mode_source["selection"][sleeve]["option"],
                        "to_option": option["option_id"],
                        "result": summary(result),
                        "score_delta": result["score"] - baseline["score"],
                    }
                )

        scale_rows = []
        for candidate_scale in sorted(
            {
                round(scale + offset, 4)
                for offset in (-0.06, -0.03, 0.0, 0.03, 0.06)
                if 0.0 < scale + offset <= 1.0
            }
        ):
            scale_rows.append(summary(account.scale_result(routed, candidate_scale)))

        router_rows: list[dict[str, Any]] = []
        if mode == "strong_breakout_preemptive":
            settings = [
                (0.70, 0.05, 1),
                (0.80, 0.05, 1),
                (0.75, 0.00, 1),
                (0.75, 0.10, 1),
                (0.75, 0.05, 0),
                (0.75, 0.05, 2),
                (0.75, 0.05, 4),
            ]
            for threshold, margin, min_hold in settings:
                candidate_routed = account.route_scenarios(
                    selected,
                    sleeves,
                    options,
                    mode=mode,
                    frames=frames,
                    funding=funding,
                    preemption_threshold=threshold,
                    preemption_margin=margin,
                    preemption_min_hold_hours=min_hold,
                )
                result = account.scale_result(candidate_routed, scale)
                router_rows.append(
                    {
                        "threshold": threshold,
                        "margin": margin,
                        "min_hold_hours": min_hold,
                        "result": summary(result),
                        "score_delta": result["score"] - baseline["score"],
                    }
                )
        all_rows = option_rows + router_rows
        results[mode] = {
            "baseline": summary(baseline),
            "option_substitutions": option_rows,
            "option_substitution_pass_rate": (
                sum(row["result"]["hard_pass"] for row in option_rows)
                / len(option_rows)
                if option_rows
                else 1.0
            ),
            "scale_neighborhood": scale_rows,
            "scale_pass_rate": (
                sum(row["hard_pass"] for row in scale_rows) / len(scale_rows)
            ),
            "router_neighborhood": router_rows,
            "router_pass_rate": (
                sum(row["result"]["hard_pass"] for row in router_rows)
                / len(router_rows)
                if router_rows
                else None
            ),
            "joint_neighborhood_pass_rate": (
                sum(row["result"]["hard_pass"] for row in all_rows) / len(all_rows)
                if all_rows
                else 1.0
            ),
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_account_neighborhood_audit_not_registered",
        "research_cutoff_exclusive": account.REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "method": (
            "At the selected account scale, replace one sleeve at a time with every "
            "available robust microtune neighbor; separately perturb account scale and "
            "preemption router controls. Each variant replays the full joint account."
        ),
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BIN-15M-AS6S V6 账户邻域稳定性（2026-07-15）",
        "",
        "每次只替换一条腿为已通过单腿稳健排序的邻近候选；另独立扰动账户scale与抢占参数。所有变体均重放联合单仓账户。",
        "",
        "| 路线 | 腿候选通过率 | scale邻域通过率 | 抢占参数通过率 | 联合邻域通过率 |",
        "|---|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        router = (
            "不适用"
            if row["router_pass_rate"] is None
            else f"{row['router_pass_rate']:.2%}"
        )
        lines.append(
            f"| `{mode}` | {row['option_substitution_pass_rate']:.2%} | "
            f"{row['scale_pass_rate']:.2%} | {router} | "
            f"{row['joint_neighborhood_pass_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "通过率只说明开发样本局部稳定性，不替代未来OOS；任何失败变体及其具体门槛保留在结构化结果中。",
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
                        "option_pass_rate": row["option_substitution_pass_rate"],
                        "scale_pass_rate": row["scale_pass_rate"],
                        "router_pass_rate": row["router_pass_rate"],
                        "joint_pass_rate": row["joint_neighborhood_pass_rate"],
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
