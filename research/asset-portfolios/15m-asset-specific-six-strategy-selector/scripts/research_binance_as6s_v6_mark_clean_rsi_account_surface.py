from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import audit_binance_as6s_clean_rsi_hf_robustness as clean
from as6s_engine import REUSED_END, STARTS
import combine_binance_as6s_v6_mark_microtuned_account as mark_micro
import combine_binance_as6s_v6_mark_robust_account as robust_account
import combine_binance_as6s_v6_microtuned_account as account
import replay_binance_as6s_v6_mark_price_account as mark_replay
import research_binance_as6s_v6_clean_rsi_microtune as clean_tune


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_robust_account_2026-07-15.json"
)
OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_account_surface_2026-07-15.json"
)
REPORT = (
    FAMILY_DIR
    / "diagnostics/binance-as6s-v6-mark-clean-rsi-account-surface-2026-07-15.md"
)
MODES = ("nonpreemptive", "strong_breakout_preemptive")
TOP_ROWS = 25
OAT_DOMAINS = {
    "rsi_window": (5, 7, 9),
    "rsi_low": (35.0, 40.0, 45.0),
    "rsi_high": (55.0, 60.0, 65.0),
    "min_atr_pct96": (0.0075, 0.00825, 0.009, 0.00975, 0.0105),
    "take_profit_pct": (0.009, 0.0105, 0.012, 0.0135, 0.015),
    "stop_pct": (0.036, 0.045, 0.054),
    "max_hold_bars": (32, 40, 48, 56, 64),
}


def config_key(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, default=str)


def oat_configs(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [config]
    for field, values in OAT_DOMAINS.items():
        for value in values:
            if value == config[field]:
                continue
            rows.append({**config, field: value})
    return rows


def oat_distance(left: dict[str, Any], right: dict[str, Any]) -> int:
    return sum(left[field] != right[field] for field in OAT_DOMAINS)


def compact(result: dict[str, Any]) -> dict[str, Any]:
    base = result["scenarios"]["base"]
    return {
        "hard_pass": result["hard_pass"],
        "research_buffer_pass": robust_account.robust_pass(result),
        "score": result["score"],
        "scale": result["scale"],
        "effective_max_leverage": result["effective_max_leverage"],
        "minimum_gate_win": robust_account.minimum_gate_win(result),
        "minimum_gate_dd": robust_account.minimum_gate_dd(result),
        "full_trades": base["full"]["trades"],
        "full_win_rate": base["full"]["win_rate"],
        "full_annual_multiple": base["full"]["annual_multiple"],
        "full_max_dd": base["full"]["max_dd"],
        "current_trades": base["current_3m"]["trades"],
        "current_frequency": base["current_3m"]["trades_per_day"],
        "current_win_rate": base["current_3m"]["win_rate"],
        "current_total_return": base["current_3m"]["total_return"],
        "all_six_frequency": base["all_six_active"]["trades_per_day"],
    }


def base_selection(
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    source_selection: dict[str, Any],
    clean_sleeve: str,
) -> tuple[int, ...]:
    rows: list[int] = []
    for sleeve in sleeves:
        if sleeve == clean_sleeve:
            rows.append(0)
            continue
        option_id = source_selection[sleeve]["option"]
        rows.append(
            next(
                index
                for index, option in enumerate(options[sleeve])
                if option["option_id"] == option_id
            )
        )
    return tuple(rows)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    _trade_source, manifest, frames, funding, sleeves, options = (
        mark_micro.prepare_mark_account_inputs()
    )
    clean_sleeve = next(
        sleeve
        for sleeve in sleeves
        if manifest["sleeve_configs"][sleeve]["source"]
        == "asset_specific_clean_rsi_hf"
    )
    audit = manifest["sleeve_configs"][clean_sleeve]
    symbol = audit["symbol"]
    marks = {asset: mark_replay.load_mark(asset) for asset in STARTS}
    context = mark_replay.prepare_clean_mark_context(
        frames[symbol], marks[symbol], funding[symbol], symbol
    )

    baseline_config = clean.Config(**audit["config"])
    configs = [asdict(config) for config in clean_tune.candidates(baseline_config)]
    for mode in MODES:
        source_config = source["results"][mode]["selection"][clean_sleeve][
            "config"
        ]
        configs.extend(oat_configs(source_config))
    unique_configs = list({config_key(config): config for config in configs}.values())
    clean_options: list[dict[str, Any]] = []
    for index, config in enumerate(unique_configs, start=1):
        if index == 1 or index % 25 == 0 or index == len(unique_configs):
            print(f"clean mark surface {index}/{len(unique_configs)}", flush=True)
        clean_options.append(
            {
                "option_id": f"mark_clean_surface_{index:04d}",
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
    options[clean_sleeve] = clean_options
    clean_index = sleeves.index(clean_sleeve)

    results: dict[str, Any] = {}
    for mode in MODES:
        print(f"account surface {mode}", flush=True)
        source_selection = source["results"][mode]["selection"]
        source_clean_key = config_key(source_selection[clean_sleeve]["config"])
        seed = base_selection(sleeves, options, source_selection, clean_sleeve)
        rows: list[dict[str, Any]] = []
        preferred_full: dict[str, Any] | None = None
        preferred_selection: tuple[int, ...] | None = None
        preferred_score = float("-inf")
        for option_index, option in enumerate(clean_options):
            proposal = list(seed)
            proposal[clean_index] = option_index
            proposal_tuple = tuple(proposal)
            result, _routed = account.evaluate_selection(
                proposal_tuple,
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
            row = {
                "option_id": option["option_id"],
                "config": option["config"],
                "is_source": config_key(option["config"]) == source_clean_key,
                "metrics": compact(result),
            }
            rows.append(row)
            if robust_account.robust_pass(result) and result["score"] > preferred_score:
                preferred_score = float(result["score"])
                preferred_full = result
                preferred_selection = proposal_tuple
        if preferred_full is None or preferred_selection is None:
            raise RuntimeError(f"{mode} mark clean surface has no buffered candidate")
        rows.sort(
            key=lambda row: (
                row["metrics"]["research_buffer_pass"],
                row["metrics"]["score"],
            ),
            reverse=True,
        )
        preferred_option = options[clean_sleeve][preferred_selection[clean_index]]
        source_row = next(row for row in rows if row["is_source"])
        oat_rows = [
            row
            for row in rows
            if oat_distance(row["config"], source_selection[clean_sleeve]["config"])
            <= 1
        ]
        results[mode] = {
            "tested_configs": len(rows),
            "hard_passes": sum(row["metrics"]["hard_pass"] for row in rows),
            "research_buffer_passes": sum(
                row["metrics"]["research_buffer_pass"] for row in rows
            ),
            "source": source_row,
            "source_oat_neighborhood": {
                "variants_including_source": len(oat_rows),
                "hard_passes": sum(
                    row["metrics"]["hard_pass"] for row in oat_rows
                ),
                "research_buffer_passes": sum(
                    row["metrics"]["research_buffer_pass"] for row in oat_rows
                ),
                "rows": oat_rows,
            },
            "preferred": {
                "option_id": preferred_option["option_id"],
                "config": preferred_option["config"],
                "metrics": compact(preferred_full),
                "full_result": preferred_full,
                "selection": account.selection_payload(
                    preferred_selection, sleeves, options
                ),
            },
            "top_robust_rows": [
                row for row in rows if row["metrics"]["research_buffer_pass"]
            ][:TOP_ROWS],
            "all_rows": rows,
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_clean_rsi_account_surface_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "sleeve": clean_sleeve,
        "candidate_policy": (
            "reuse the fixed 500-config clean-RSI local surface plus current "
            "mark selections; regenerate every exit with mark-price protection; "
            "reroute the full account and retain the user gates plus research buffers"
        ),
        "research_buffers": {
            "minimum_gate_win": robust_account.MIN_GATE_WIN,
            "minimum_gate_dd_strictly_above": robust_account.MIN_GATE_DD,
            "minimum_base_current_and_all_six_frequency": (
                robust_account.MIN_FREQUENCY_BUFFER
            ),
        },
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 HYPE clean-RSI mark账户参数面（2026-07-15）",
        "",
        "把既有500个clean-RSI局部配置全部改用mark-price保护退出，并逐个替换回六币联合账户。未来OOS未读取。",
        "",
        "| 路线 | 配置数 | 硬门槛通过 | 研究缓冲通过 | source OAT硬通过 | source OAT缓冲通过 | source年化 | preferred年化 | source最低胜率 | preferred最低胜率 | preferred当前频率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        source_metrics = row["source"]["metrics"]
        preferred_metrics = row["preferred"]["metrics"]
        oat = row["source_oat_neighborhood"]
        lines.append(
            f"| `{mode}` | {row['tested_configs']} | {row['hard_passes']} | "
            f"{row['research_buffer_passes']} | "
            f"{oat['hard_passes']}/{oat['variants_including_source']} | "
            f"{oat['research_buffer_passes']}/{oat['variants_including_source']} | "
            f"{source_metrics['full_annual_multiple']:.3f}x | "
            f"{preferred_metrics['full_annual_multiple']:.3f}x | "
            f"{source_metrics['minimum_gate_win']:.2%} | "
            f"{preferred_metrics['minimum_gate_win']:.2%} | "
            f"{preferred_metrics['current_frequency']:.3f}/日 |"
        )
    lines.extend(
        [
            "",
            "preferred仍须做OAT邻域和重新联合坐标搜索；本轮不登记版本。",
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
                        "tested": row["tested_configs"],
                        "hard_passes": row["hard_passes"],
                        "buffer_passes": row["research_buffer_passes"],
                        "source": row["source"]["metrics"],
                        "preferred": row["preferred"]["metrics"],
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
