from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import REUSED_END
import combine_binance_as6s_v6_mark_microtuned_account as mark_micro
import combine_binance_as6s_v6_microtuned_account as account
from combine_hybrid_asset_specific_account import UnifiedTrade


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_microtuned_account_2026-07-15.json"
)
OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_robust_account_2026-07-15.json"
)
TRADES_OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_robust_account_trades_2026-07-15.csv"
)
REPORT = (
    FAMILY_DIR
    / "diagnostics/binance-as6s-v6-mark-robust-account-2026-07-15.md"
)
MODES = ("nonpreemptive", "strong_breakout_preemptive")
MIN_GATE_WIN = 0.81
MIN_GATE_DD = -0.185
MIN_FREQUENCY_BUFFER = 1.01
MAX_ITERATIONS = 8


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


def robust_pass(result: dict[str, Any]) -> bool:
    base = result["scenarios"]["base"]
    return bool(
        result["hard_pass"]
        and minimum_gate_win(result) >= MIN_GATE_WIN
        and minimum_gate_dd(result) > MIN_GATE_DD
        and base["current_3m"]["trades_per_day"] >= MIN_FREQUENCY_BUFFER
        and base["all_six_active"]["trades_per_day"] >= MIN_FREQUENCY_BUFFER
    )


def robust_margin(result: dict[str, Any]) -> dict[str, float | bool]:
    base = result["scenarios"]["base"]
    return {
        "pass": robust_pass(result),
        "minimum_gate_win": minimum_gate_win(result),
        "minimum_gate_dd": minimum_gate_dd(result),
        "current_frequency": base["current_3m"]["trades_per_day"],
        "all_six_frequency": base["all_six_active"]["trades_per_day"],
    }


def neighbors(
    selection: tuple[int, ...],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
) -> list[tuple[int, ...]]:
    rows: list[tuple[int, ...]] = []
    for sleeve_index, sleeve in enumerate(sleeves):
        for option_index in range(-1, len(options[sleeve])):
            if option_index == selection[sleeve_index]:
                continue
            proposal = list(selection)
            proposal[sleeve_index] = option_index
            rows.append(tuple(proposal))
    return rows


def robust_coordinate_search(
    seed: tuple[int, ...],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> tuple[
    tuple[int, ...],
    dict[str, Any],
    dict[str, list[UnifiedTrade]],
    int,
    dict[str, Any],
]:
    cache: dict[
        tuple[int, ...], tuple[dict[str, Any], dict[str, list[UnifiedTrade]]]
    ] = {}

    def evaluate(
        selection: tuple[int, ...],
    ) -> tuple[dict[str, Any], dict[str, list[UnifiedTrade]]]:
        if selection not in cache:
            cache[selection] = account.evaluate_selection(
                selection,
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
        return cache[selection]

    seed_result, _seed_routed = evaluate(seed)
    current = seed
    current_result = seed_result
    current_routed = _seed_routed
    bootstrap: dict[str, Any] = {
        "seed_robust_pass": robust_pass(seed_result),
        "one_step_candidates": 0,
        "one_step_robust_passes": 0,
    }
    if not robust_pass(current_result):
        candidates: list[
            tuple[
                float,
                tuple[int, ...],
                dict[str, Any],
                dict[str, list[UnifiedTrade]],
            ]
        ] = []
        for proposal in neighbors(seed, sleeves, options):
            result, routed = evaluate(proposal)
            bootstrap["one_step_candidates"] += 1
            if robust_pass(result):
                bootstrap["one_step_robust_passes"] += 1
                candidates.append((result["score"], proposal, result, routed))
        if not candidates:
            raise RuntimeError(f"{mode} has no one-step research-buffer seed")
        _score, current, current_result, current_routed = max(
            candidates, key=lambda row: row[0]
        )

    accepted_steps: list[dict[str, Any]] = []
    for iteration in range(MAX_ITERATIONS):
        candidates = []
        for proposal in neighbors(current, sleeves, options):
            result, routed = evaluate(proposal)
            if robust_pass(result):
                candidates.append((result["score"], proposal, result, routed))
        if not candidates:
            break
        _score, proposal, result, routed = max(
            candidates, key=lambda row: row[0]
        )
        if result["score"] <= current_result["score"] + 1e-12:
            break
        changed = next(
            index
            for index, (left, right) in enumerate(zip(current, proposal, strict=True))
            if left != right
        )
        accepted_steps.append(
            {
                "iteration": iteration + 1,
                "sleeve": sleeves[changed],
                "from": (
                    "dropped"
                    if current[changed] < 0
                    else options[sleeves[changed]][current[changed]]["option_id"]
                ),
                "to": (
                    "dropped"
                    if proposal[changed] < 0
                    else options[sleeves[changed]][proposal[changed]]["option_id"]
                ),
                "score_before": current_result["score"],
                "score_after": result["score"],
            }
        )
        current, current_result, current_routed = (
            proposal,
            result,
            routed,
        )
    return (
        current,
        current_result,
        current_routed,
        len(cache),
        {**bootstrap, "accepted_steps": accepted_steps},
    )


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    _trade_source, _manifest, frames, funding, sleeves, options = (
        mark_micro.prepare_mark_account_inputs()
    )
    results: dict[str, Any] = {}
    routed_by_mode: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for mode in MODES:
        print(f"robust search {mode}", flush=True)
        seed = mark_micro.seed_selection(
            sleeves,
            options,
            source["results"][mode]["selection"],
        )
        selection, result, routed, evaluated, search = robust_coordinate_search(
            seed,
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        if not robust_pass(result):
            raise RuntimeError(f"{mode} robust search returned non-passing result")
        results[mode] = {
            "source_selection": source["results"][mode]["selection"],
            "selection": account.selection_payload(selection, sleeves, options),
            "evaluated_account_states": evaluated,
            "search": search,
            "research_margin": robust_margin(result),
            "result": result,
        }
        routed_by_mode[mode] = routed

    trade_rows: list[dict[str, Any]] = []
    for mode, routed in routed_by_mode.items():
        scale = float(results[mode]["result"]["scale"])
        for trade in routed["base"]:
            trade_rows.append({"mode": mode, "scale": scale, **asdict(trade)})
    pd.DataFrame(trade_rows).to_csv(TRADES_OUTPUT, index=False)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_robust_account_coordinate_search_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "execution_model": (
            "trade OHLC signals/entries; 15m mark OHLC protection triggers; "
            "trade-price mapped fills; changed exits reroute the joint account"
        ),
        "user_hard_gate": (
            "unchanged: base/stress/K+2 full and current win>=80%, DD<20%, "
            "return>0; base current/all-six frequency 1-2/day; leverage<=3x"
        ),
        "selection_research_buffers": {
            "minimum_gate_win": MIN_GATE_WIN,
            "minimum_gate_dd_strictly_above": MIN_GATE_DD,
            "base_current_and_all_six_frequency_min": MIN_FREQUENCY_BUFFER,
            "note": (
                "adds at least one current-3m trade above the 1/day boundary; "
                "these are selection margins, not changes to the user hard gate"
            ),
        },
        "results": results,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BIN-15M-AS6S V6 mark稳健缓冲联合微调（2026-07-15）",
        "",
        "在用户硬门槛之外，选择阶段额外要求：所有门禁窗口最低胜率>=81%、最低回撤>-18.5%、当前3m和六币全活跃期频率>=1.01单/日。未来OOS未读取。",
        "",
        "| 路线 | hard pass | buffer pass | scale | 杠杆 | 年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前胜率 | 当前频率 | 最低压力胜率 | 最低压力回撤 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        result = row["result"]
        margin = row["research_margin"]
        base = result["scenarios"]["base"]
        lines.append(
            f"| `{mode}` | `{result['hard_pass']}` | `{margin['pass']}` | "
            f"{result['scale']:.2f} | {result['effective_max_leverage']:.2f}x | "
            f"{base['full']['annual_multiple']:.3f}x | "
            f"{base['full']['win_rate']:.2%} | {base['full']['max_dd']:.2%} | "
            f"{base['current_3m']['total_return']:+.2%} | "
            f"{base['current_3m']['win_rate']:.2%} | "
            f"{base['current_3m']['trades_per_day']:.3f}/日 | "
            f"{margin['minimum_gate_win']:.2%} | "
            f"{margin['minimum_gate_dd']:.2%} |"
        )
    lines.extend(
        [
            "",
            "本结果仍为开发样本观察，下一步必须对新选择重新做逐腿删除和完整邻域审计。",
            "",
            f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})；交易路径：[`{TRADES_OUTPUT.name}`](../artifacts/{TRADES_OUTPUT.name})。",
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
                        "hard_pass": row["result"]["hard_pass"],
                        "research_buffer_pass": row["research_margin"]["pass"],
                        "scale": row["result"]["scale"],
                        "score": row["result"]["score"],
                        "annual_multiple": row["result"]["scenarios"]["base"][
                            "full"
                        ]["annual_multiple"],
                        "minimum_gate_win": row["research_margin"][
                            "minimum_gate_win"
                        ],
                        "minimum_gate_dd": row["research_margin"][
                            "minimum_gate_dd"
                        ],
                        "current_frequency": row["research_margin"][
                            "current_frequency"
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
