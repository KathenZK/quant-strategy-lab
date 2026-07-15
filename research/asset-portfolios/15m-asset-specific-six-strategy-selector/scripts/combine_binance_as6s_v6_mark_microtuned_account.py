from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import REUSED_END, STARTS
import combine_binance_as6s_v6_microtuned_account as account
from combine_hybrid_asset_specific_account import UnifiedTrade
import replay_binance_as6s_v6_mark_price_account as mark_replay
import research_binance_as6s_v5_legacy_exact_full_ablation as legacy_full


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_microtuned_account_2026-07-15.json"
TRADES_OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_microtuned_account_trades_2026-07-15.csv"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-microtuned-account-2026-07-15.md"


def seed_selection(
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    source_selection: dict[str, Any],
) -> tuple[int, ...]:
    output: list[int] = []
    for sleeve in sleeves:
        option_id = source_selection[sleeve]["option"]
        if option_id == "dropped":
            output.append(-1)
            continue
        output.append(
            next(
                index
                for index, row in enumerate(options[sleeve])
                if row["option_id"] == option_id
            )
        )
    return tuple(output)


def prepare_mark_account_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, pd.DataFrame],
    dict[str, pd.DataFrame],
    tuple[str, ...],
    dict[str, list[dict[str, Any]]],
]:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    manifest, _reference, frames, funding, sleeves, trade_options = (
        account.prepare_account_inputs()
    )
    marks = {symbol: mark_replay.load_mark(symbol) for symbol in STARTS}
    contexts, captured, featured, prefixes = legacy_full.prepare()
    options: dict[str, list[dict[str, Any]]] = {}
    for sleeve_index, sleeve in enumerate(sleeves, start=1):
        audit = manifest["sleeve_configs"][sleeve]
        symbol = audit["symbol"]
        rows: list[dict[str, Any]] = []
        print(
            f"mark options {sleeve_index}/{len(sleeves)} {sleeve}",
            flush=True,
        )
        for option in trade_options[sleeve]:
            config = option["config"]
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
            rows.append(
                {
                    "option_id": option["option_id"],
                    "config": config,
                    "universe": universe,
                }
            )
        options[sleeve] = rows
    return source, manifest, frames, funding, sleeves, options


def main() -> None:
    source, _manifest, frames, funding, sleeves, options = (
        prepare_mark_account_inputs()
    )

    results: dict[str, Any] = {}
    routed_by_mode: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for mode, mode_source in source["results"].items():
        seed = seed_selection(
            sleeves,
            options,
            mode_source["selection"],
        )
        selection, result, routed, evaluated = account.coordinate_search(
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
            seed=seed,
        )
        selection, result, routed, prune_evaluated = (
            account.prune_dominated_sleeves(
                selection,
                result,
                routed,
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
        )
        results[mode] = {
            "seed_selection": account.selection_payload(seed, sleeves, options),
            "selection": account.selection_payload(selection, sleeves, options),
            "evaluated_account_states": evaluated + prune_evaluated,
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
        "stage": "v6_mark_microtuned_account_coordinate_search_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "execution_model": (
            "trade OHLC signals/entries; 15m mark OHLC protection triggers; "
            "trade-price mapped fills; changed exits reroute the joint account"
        ),
        "search": {
            "option_counts": {
                sleeve: len(rows) for sleeve, rows in options.items()
            },
            "seed": "trade-OHLC V6 selected option per route",
            "coordinate_iterations_max": 8,
            "drop_allowed": True,
            "robust_dd_buffer": account.ROBUST_DD_BUFFER,
            "hard_gate": (
                "base/stress/K+2 full and current win>=80%, DD<20%, return>0; "
                "base current/all-six frequency 1-2/day; leverage<=3x"
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
        "# BIN-15M-AS6S V6 mark语义联合微调（2026-07-15）",
        "",
        "以trade-OHLC V6选项为种子，把每条腿最多8个稳健候选全部换成mark保护退出后重新做联合账户坐标搜索。未来OOS未读取。",
        "",
        "| 路线 | hard pass | scale | 有效最大杠杆 | 活跃腿 | full年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        result = row["result"]
        base = result["scenarios"]["base"]
        active = sum(
            selection["option"] != "dropped"
            for selection in row["selection"].values()
        )
        lines.append(
            f"| `{mode}` | `{result['hard_pass']}` | {result['scale']:.2f} | "
            f"{result['effective_max_leverage']:.2f}x | {active} | "
            f"{base['full']['annual_multiple']:.3f}x | "
            f"{base['full']['win_rate']:.2%} | {base['full']['max_dd']:.2%} | "
            f"{base['current_3m']['total_return']:+.2%} | "
            f"{base['current_3m']['win_rate']:.2%} | "
            f"{base['current_3m']['trades_per_day']:.3f}/日 |"
        )
    lines.extend(
        [
            "",
            "本结果仍是开发样本观察；需继续做mark候选账户消融、邻域复核、冻结清单与Runner逐笔对拍。",
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
                        "scale": row["result"]["scale"],
                        "score": row["result"]["score"],
                        "active_sleeves": sum(
                            selection["option"] != "dropped"
                            for selection in row["selection"].values()
                        ),
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
