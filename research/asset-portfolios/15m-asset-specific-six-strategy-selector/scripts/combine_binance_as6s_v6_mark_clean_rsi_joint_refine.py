from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import REUSED_END, STARTS
import combine_binance_as6s_v6_mark_microtuned_account as mark_micro
import combine_binance_as6s_v6_mark_robust_account as robust_account
import combine_binance_as6s_v6_microtuned_account as account
from combine_hybrid_asset_specific_account import UnifiedTrade
import replay_binance_as6s_v6_mark_price_account as mark_replay


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SURFACE = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_account_surface_2026-07-15.json"
)
OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_2026-07-15.json"
)
TRADES_OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_trades_2026-07-15.csv"
)
REPORT = (
    FAMILY_DIR
    / "diagnostics/binance-as6s-v6-mark-clean-rsi-joint-refine-2026-07-15.md"
)
MODES = ("nonpreemptive", "strong_breakout_preemptive")


def config_key(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, default=str)


def prepare_refine_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, pd.DataFrame],
    dict[str, pd.DataFrame],
    tuple[str, ...],
    dict[str, list[dict[str, Any]]],
]:
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    _trade_source, manifest, frames, funding, sleeves, options = (
        mark_micro.prepare_mark_account_inputs()
    )
    clean_sleeve = surface["sleeve"]
    audit = manifest["sleeve_configs"][clean_sleeve]
    symbol = audit["symbol"]
    marks = {asset: mark_replay.load_mark(asset) for asset in STARTS}
    context = mark_replay.prepare_clean_mark_context(
        frames[symbol], marks[symbol], funding[symbol], symbol
    )
    configs: list[dict[str, Any]] = []
    for mode in MODES:
        mode_row = surface["results"][mode]
        configs.extend(row["config"] for row in mode_row["top_robust_rows"])
        configs.append(mode_row["source"]["config"])
        configs.append(mode_row["preferred"]["config"])
        configs.extend(
            row["config"]
            for row in mode_row["source_oat_neighborhood"]["rows"]
            if row["metrics"]["research_buffer_pass"]
        )
    unique_configs = list({config_key(config): config for config in configs}.values())
    rows: list[dict[str, Any]] = []
    for index, config in enumerate(unique_configs, start=1):
        if index == 1 or index % 10 == 0 or index == len(unique_configs):
            print(f"joint clean options {index}/{len(unique_configs)}", flush=True)
        rows.append(
            {
                "option_id": f"mark_clean_joint_{index:03d}",
                "config": config,
                "universe": mark_replay.clean_universe(
                    clean_sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                    prepared_context=context,
                ),
            }
        )
    options[clean_sleeve] = rows
    return surface, manifest, frames, funding, sleeves, options


def seed_selection(
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    selection_payload: dict[str, Any],
    clean_sleeve: str,
) -> tuple[int, ...]:
    output: list[int] = []
    for sleeve in sleeves:
        selected = selection_payload[sleeve]
        if selected["option"] == "dropped":
            output.append(-1)
            continue
        if sleeve == clean_sleeve:
            key = config_key(selected["config"])
            output.append(
                next(
                    index
                    for index, option in enumerate(options[sleeve])
                    if config_key(option["config"]) == key
                )
            )
        else:
            output.append(
                next(
                    index
                    for index, option in enumerate(options[sleeve])
                    if option["option_id"] == selected["option"]
                )
            )
    return tuple(output)


def main() -> None:
    surface, _manifest, frames, funding, sleeves, options = prepare_refine_inputs()
    clean_sleeve = surface["sleeve"]
    results: dict[str, Any] = {}
    routed_by_mode: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for mode in MODES:
        print(f"joint refine {mode}", flush=True)
        source_selection = surface["results"][mode]["preferred"]["selection"]
        seed = seed_selection(sleeves, options, source_selection, clean_sleeve)
        selection, result, routed, evaluated, search = (
            robust_account.robust_coordinate_search(
                seed,
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
        )
        if not robust_account.robust_pass(result):
            raise RuntimeError(f"{mode} joint refine returned non-buffered result")
        results[mode] = {
            "surface_seed_selection": source_selection,
            "selection": account.selection_payload(selection, sleeves, options),
            "evaluated_account_states": evaluated,
            "search": search,
            "research_margin": robust_account.robust_margin(result),
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
        "stage": "v6_mark_clean_rsi_joint_refine_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "execution_model": (
            "trade OHLC signals/entries; 15m mark OHLC protection triggers; "
            "trade-price mapped fills; changed exits reroute the joint account"
        ),
        "selection_research_buffers": {
            "minimum_gate_win": robust_account.MIN_GATE_WIN,
            "minimum_gate_dd_strictly_above": robust_account.MIN_GATE_DD,
            "base_current_and_all_six_frequency_min": (
                robust_account.MIN_FREQUENCY_BUFFER
            ),
        },
        "clean_option_count": len(options[clean_sleeve]),
        "other_option_counts": {
            sleeve: len(rows)
            for sleeve, rows in options.items()
            if sleeve != clean_sleeve
        },
        "results": results,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 HYPE clean-RSI扩面后联合微调（2026-07-15）",
        "",
        "将mark参数面中通过研究缓冲的clean-RSI前沿与OAT邻居放回15条腿联合坐标搜索。未来OOS未读取。",
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
            "本结果仍须重新做账户逐腿删除、scale/路由和扩展clean参数邻域审计。",
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
                "clean_option_count": len(options[clean_sleeve]),
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
