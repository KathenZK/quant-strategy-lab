from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import combine_binance_as6s_v6_microtuned_account as account


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ACCOUNT_RESULT = (
    FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_account_leg_ablation_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v6-account-leg-ablation-2026-07-15.md"


def option_index(
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


def compact(result: dict[str, Any]) -> dict[str, Any]:
    minimum_gate_dd = min(
        result["scenarios"][scenario][window]["max_dd"]
        for scenario in account.SCENARIOS
        for window in ("full", "current_3m")
    )
    return {
        "scale": result["scale"],
        "effective_max_leverage": result["effective_max_leverage"],
        "hard_pass": result["hard_pass"],
        "minimum_gate_dd": minimum_gate_dd,
        "robust_dd_buffer_pass": minimum_gate_dd > account.ROBUST_DD_BUFFER,
        "failed_checks": [
            check for check, passed in result["checks"].items() if not passed
        ],
        "score": result["score"],
        "scenarios": {
            scenario: {
                window: result["scenarios"][scenario][window]
                for window in ("full", "current_3m", "all_six_active")
            }
            for scenario in account.SCENARIOS
        },
    }


def deltas(
    baseline: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, float]:
    base = baseline["scenarios"]["base"]
    other = variant["scenarios"]["base"]
    return {
        "score": variant["score"] - baseline["score"],
        "full_trades": other["full"]["trades"] - base["full"]["trades"],
        "full_win_rate": other["full"]["win_rate"] - base["full"]["win_rate"],
        "full_total_return": (
            other["full"]["total_return"] - base["full"]["total_return"]
        ),
        "full_annual_multiple": (
            other["full"]["annual_multiple"] - base["full"]["annual_multiple"]
        ),
        "full_max_dd": other["full"]["max_dd"] - base["full"]["max_dd"],
        "current_trades": (
            other["current_3m"]["trades"] - base["current_3m"]["trades"]
        ),
        "current_win_rate": (
            other["current_3m"]["win_rate"] - base["current_3m"]["win_rate"]
        ),
        "current_total_return": (
            other["current_3m"]["total_return"]
            - base["current_3m"]["total_return"]
        ),
        "current_max_dd": (
            other["current_3m"]["max_dd"] - base["current_3m"]["max_dd"]
        ),
    }


def preserves_candidate_buffer(result: dict[str, Any]) -> bool:
    minimum_dd = min(
        result["scenarios"][scenario][window]["max_dd"]
        for scenario in account.SCENARIOS
        for window in ("full", "current_3m")
    )
    return result["hard_pass"] and minimum_dd > account.ROBUST_DD_BUFFER


def evaluate(
    selection: tuple[int, ...],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    scale: float,
    frames: dict[str, Any],
    funding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    routed = account.route_scenarios(
        selection,
        sleeves,
        options,
        mode=mode,
        frames=frames,
        funding=funding,
    )
    fixed = account.scale_result(routed, scale)
    rows = [account.scale_result(routed, candidate) for candidate in account.SCALES]
    passing = [row for row in rows if row["hard_pass"]]
    best = max(passing or rows, key=lambda row: row["score"])
    return fixed, best


def main() -> None:
    source = json.loads(ACCOUNT_RESULT.read_text(encoding="utf-8"))
    _manifest, _reference, frames, funding, sleeves, options = (
        account.prepare_account_inputs()
    )
    results: dict[str, Any] = {}
    for mode, mode_source in source["results"].items():
        selected = mode_source["selection"]
        selection = tuple(
            option_index(sleeve, selected[sleeve]["option"], options)
            for sleeve in sleeves
        )
        scale = float(mode_source["result"]["scale"])
        baseline_fixed, baseline_best = evaluate(
            selection,
            sleeves,
            options,
            mode=mode,
            scale=scale,
            frames=frames,
            funding=funding,
        )
        drops: dict[str, Any] = {}
        reverts: dict[str, Any] = {}
        for sleeve_index, sleeve in enumerate(sleeves):
            if selection[sleeve_index] < 0:
                continue
            dropped = list(selection)
            dropped[sleeve_index] = -1
            fixed, best = evaluate(
                tuple(dropped),
                sleeves,
                options,
                mode=mode,
                scale=scale,
                frames=frames,
                funding=funding,
            )
            drops[sleeve] = {
                "fixed_scale": compact(fixed),
                "best_scale": compact(best),
                "fixed_scale_delta": deltas(baseline_fixed, fixed),
                "dispensable_at_fixed_scale": (
                    preserves_candidate_buffer(fixed)
                    and fixed["score"] >= baseline_fixed["score"]
                ),
            }
            if selection[sleeve_index] > 0:
                reverted = list(selection)
                reverted[sleeve_index] = 0
                fixed, best = evaluate(
                    tuple(reverted),
                    sleeves,
                    options,
                    mode=mode,
                    scale=scale,
                    frames=frames,
                    funding=funding,
                )
                reverts[sleeve] = {
                    "selected_option": selected[sleeve]["option"],
                    "fixed_scale": compact(fixed),
                    "best_scale": compact(best),
                    "fixed_scale_delta": deltas(baseline_fixed, fixed),
                    "microtune_useful_at_fixed_scale": (
                        not preserves_candidate_buffer(fixed)
                        or fixed["score"] < baseline_fixed["score"]
                    ),
                }
        results[mode] = {
            "selected_scale": scale,
            "baseline_fixed_scale": compact(baseline_fixed),
            "baseline_best_scale": compact(baseline_best),
            "drop_ablation": drops,
            "microtune_revert_ablation": reverts,
            "dispensable_sleeves": [
                sleeve
                for sleeve, row in drops.items()
                if row["dispensable_at_fixed_scale"]
            ],
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_account_leg_ablation_not_registered",
        "research_cutoff_exclusive": account.REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "method": (
            "For each selected sleeve, remove the full sleeve and replay the joint "
            "single-position account. For every selected microtune, independently "
            "revert it to V5 baseline. Report both frozen selected scale and the best "
            "allowed scale; no variant may read the future OOS."
        ),
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BIN-15M-AS6S V6 账户逐腿消融（2026-07-15）",
        "",
        "每次只删除一条完整策略腿，并按原账户时序重新路由；微调腿另做单腿回退到V5参数。所有结果严格截止 `2026-07-14T09:00Z`。",
        "",
    ]
    for mode, row in results.items():
        base = row["baseline_fixed_scale"]["scenarios"]["base"]
        lines.extend(
            [
                f"## `{mode}`",
                "",
                (
                    f"基线：scale {row['selected_scale']:.2f}，full {base['full']['trades']}笔，"
                    f"胜率 {base['full']['win_rate']:.2%}，年化倍数 {base['full']['annual_multiple']:.3f}x，"
                    f"回撤 {base['full']['max_dd']:.2%}。"
                ),
                "",
                "| 删除腿 | hard pass | 分数变化 | full交易变化 | full年化变化 | 当前3m收益变化 | 失败门槛 |",
                "|---|---|---:|---:|---:|---:|---|",
            ]
        )
        ordered = sorted(
            row["drop_ablation"].items(),
            key=lambda item: item[1]["fixed_scale_delta"]["score"],
            reverse=True,
        )
        for sleeve, result in ordered:
            fixed = result["fixed_scale"]
            delta = result["fixed_scale_delta"]
            failed = ", ".join(fixed["failed_checks"]) or "无"
            lines.append(
                f"| `{sleeve}` | `{fixed['hard_pass']}` | {delta['score']:+.3f} | "
                f"{delta['full_trades']:+.0f} | {delta['full_annual_multiple']:+.3f}x | "
                f"{delta['current_total_return']:+.2%} | {failed} |"
            )
        lines.extend(
            [
                "",
                f"可删除且不降低固定scale分数的腿：`{row['dispensable_sleeves'] or '无'}`。",
                "",
            ]
        )
    lines.extend(
        [
            "本报告只判定历史开发样本中的边际贡献；被保留不等于通过独立未来OOS。",
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
                        "baseline_hard_pass": row["baseline_fixed_scale"][
                            "hard_pass"
                        ],
                        "dispensable_sleeves": row["dispensable_sleeves"],
                        "drop_variants": len(row["drop_ablation"]),
                        "revert_variants": len(row["microtune_revert_ablation"]),
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
