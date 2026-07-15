from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from as6s_engine import REUSED_END, STARTS, load_funding, load_symbol_frame
import combine_binance_as6s_v6_microtuned_account as account
import replay_binance_as6s_v6_mark_price_account as mark_replay
import research_binance_as6s_v5_legacy_exact_full_ablation as legacy_full


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
SOURCE = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json"
MARK_RESULT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_price_account_2026-07-15.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_account_ablation_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v6-mark-account-ablation-2026-07-15.md"


def compact(result: dict[str, Any]) -> dict[str, Any]:
    minimum_dd = min(
        result["scenarios"][scenario][window]["max_dd"]
        for scenario in account.SCENARIOS
        for window in ("full", "current_3m")
    )
    return {
        "scale": result["scale"],
        "hard_pass": result["hard_pass"],
        "minimum_gate_dd": minimum_dd,
        "robust_dd_buffer_pass": minimum_dd > account.ROBUST_DD_BUFFER,
        "failed_checks": [
            name for name, passed in result["checks"].items() if not passed
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


def delta(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, float]:
    base = baseline["scenarios"]["base"]
    other = variant["scenarios"]["base"]
    return {
        "score": variant["score"] - baseline["score"],
        "full_trades": other["full"]["trades"] - base["full"]["trades"],
        "full_win_rate": other["full"]["win_rate"] - base["full"]["win_rate"],
        "full_annual_multiple": (
            other["full"]["annual_multiple"] - base["full"]["annual_multiple"]
        ),
        "full_max_dd": other["full"]["max_dd"] - base["full"]["max_dd"],
        "current_trades": (
            other["current_3m"]["trades"] - base["current_3m"]["trades"]
        ),
        "current_total_return": (
            other["current_3m"]["total_return"]
            - base["current_3m"]["total_return"]
        ),
        "current_win_rate": (
            other["current_3m"]["win_rate"] - base["current_3m"]["win_rate"]
        ),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    mark_result = json.loads(MARK_RESULT.read_text(encoding="utf-8"))
    frames = {
        symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in STARTS
    }
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in STARTS}
    marks = {symbol: mark_replay.load_mark(symbol) for symbol in STARTS}
    contexts, captured, featured, prefixes = legacy_full.prepare()
    results: dict[str, Any] = {}
    for mode, mode_source in source["results"].items():
        options: dict[str, list[dict[str, Any]]] = {}
        active: list[str] = []
        for sleeve, selection in mode_source["selection"].items():
            if selection["option"] == "dropped":
                continue
            audit = manifest["sleeve_configs"][sleeve]
            config = selection["config"]
            symbol = audit["symbol"]
            if audit["source"] == "prefit_frontier_asset_first":
                universe = mark_replay.frontier_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "asset_specific_clean_rsi_hf":
                universe = mark_replay.clean_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "legacy_asset_specific_1h":
                asset = symbol.removesuffix("USDT")
                baseline_config = next(
                    cfg
                    for name, cfg in captured.items()
                    if name.startswith(asset) and cfg.style == audit["mechanism"]
                )
                universe = mark_replay.legacy_universe(
                    sleeve,
                    audit,
                    config,
                    contexts[asset]["engine"],
                    baseline_config,
                    featured[asset],
                    frames[symbol],
                    marks[symbol],
                    prefixes[asset],
                )
            else:
                raise RuntimeError(f"unknown source {audit['source']}")
            active.append(sleeve)
            options[sleeve] = [
                {"option_id": selection["option"], "config": config, "universe": universe}
            ]
        sleeves = tuple(active)
        selection = tuple(0 for _ in sleeves)
        routed = account.route_scenarios(
            selection,
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        scale = float(
            mark_result["results"][mode]["best_mark_price_scale_result"]["scale"]
        )
        baseline = account.scale_result(routed, scale)
        drops: dict[str, Any] = {}
        for sleeve_index, sleeve in enumerate(sleeves):
            proposal = list(selection)
            proposal[sleeve_index] = -1
            candidate_routed = account.route_scenarios(
                tuple(proposal),
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
            result = account.scale_result(candidate_routed, scale)
            minimum_dd = min(
                result["scenarios"][scenario][window]["max_dd"]
                for scenario in account.SCENARIOS
                for window in ("full", "current_3m")
            )
            drops[sleeve] = {
                "result": compact(result),
                "delta": delta(baseline, result),
                "dispensable": (
                    result["hard_pass"]
                    and minimum_dd > account.ROBUST_DD_BUFFER
                    and result["score"] >= baseline["score"]
                ),
            }
        results[mode] = {
            "scale": scale,
            "baseline": compact(baseline),
            "drop_ablation": drops,
            "dispensable_sleeves": [
                sleeve for sleeve, row in drops.items() if row["dispensable"]
            ],
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_account_leg_ablation_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "method": (
            "Remove one complete sleeve from the full mark-price opportunity pool, "
            "rerun the joint account, and require all hard gates plus the -18.5% "
            "drawdown buffer at the selected mark scale."
        ),
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 mark账户逐腿消融（2026-07-15）",
        "",
        "每次删除一条完整策略腿，重新运行mark触发和联合账户仲裁；可删除判定同时要求全部硬门槛与-18.5%回撤缓冲。",
        "",
    ]
    for mode, row in results.items():
        base = row["baseline"]["scenarios"]["base"]
        lines.extend(
            [
                f"## `{mode}`",
                "",
                (
                    f"scale {row['scale']:.2f}，full {base['full']['trades']}笔，"
                    f"胜率 {base['full']['win_rate']:.2%}，年化倍数 "
                    f"{base['full']['annual_multiple']:.3f}x，回撤 "
                    f"{base['full']['max_dd']:.2%}。"
                ),
                "",
                "| 删除腿 | hard pass | 缓冲通过 | 分数变化 | full年化变化 | 当前3m收益变化 | 失败门槛 |",
                "|---|---|---|---:|---:|---:|---|",
            ]
        )
        ordered = sorted(
            row["drop_ablation"].items(),
            key=lambda item: item[1]["delta"]["score"],
            reverse=True,
        )
        for sleeve, item in ordered:
            result = item["result"]
            change = item["delta"]
            failures = ", ".join(result["failed_checks"]) or "无"
            lines.append(
                f"| `{sleeve}` | `{result['hard_pass']}` | "
                f"`{result['robust_dd_buffer_pass']}` | {change['score']:+.3f} | "
                f"{change['full_annual_multiple']:+.3f}x | "
                f"{change['current_total_return']:+.2%} | {failures} |"
            )
        lines.extend(
            [
                "",
                f"可删除腿：`{row['dispensable_sleeves'] or '无'}`。",
                "",
            ]
        )
    lines.extend(
        [
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
                        "baseline_hard_pass": row["baseline"]["hard_pass"],
                        "dispensable_sleeves": row["dispensable_sleeves"],
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
