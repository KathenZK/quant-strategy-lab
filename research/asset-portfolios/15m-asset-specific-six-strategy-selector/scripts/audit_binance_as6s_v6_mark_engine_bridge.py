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
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_engine_bridge_2026-07-15.json"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-engine-bridge-2026-07-15.md"


def metric_delta(source: dict[str, Any], bridge: dict[str, Any]) -> dict[str, float]:
    return {
        "trades": bridge["trades"] - source["trades"],
        "win_rate": bridge["win_rate"] - source["win_rate"],
        "total_return": bridge["total_return"] - source["total_return"],
        "annual_multiple": bridge["annual_multiple"] - source["annual_multiple"],
        "max_dd": bridge["max_dd"] - source["max_dd"],
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    frames = {
        symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in STARTS
    }
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in STARTS}
    trade_trigger = {
        symbol: frame[["ts", "open", "high", "low", "close"]].copy()
        for symbol, frame in frames.items()
    }
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
                    trade_trigger[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "asset_specific_clean_rsi_hf":
                universe = mark_replay.clean_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    trade_trigger[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "legacy_asset_specific_1h":
                asset = symbol.removesuffix("USDT")
                baseline = next(
                    cfg
                    for name, cfg in captured.items()
                    if name.startswith(asset) and cfg.style == audit["mechanism"]
                )
                universe = mark_replay.legacy_universe(
                    sleeve,
                    audit,
                    config,
                    contexts[asset]["engine"],
                    baseline,
                    featured[asset],
                    frames[symbol],
                    trade_trigger[symbol],
                    prefixes[asset],
                )
            else:
                raise RuntimeError(f"unknown source {audit['source']}")
            active.append(sleeve)
            options[sleeve] = [
                {"option_id": selection["option"], "config": config, "universe": universe}
            ]
        sleeves = tuple(active)
        routed = account.route_scenarios(
            tuple(0 for _ in sleeves),
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        scale = float(mode_source["result"]["scale"])
        bridge = account.scale_result(routed, scale)
        comparisons: dict[str, Any] = {}
        for scenario in account.SCENARIOS:
            comparisons[scenario] = {}
            for window in ("full", "current_3m"):
                source_metric = mode_source["result"]["scenarios"][scenario][window]
                bridge_metric = bridge["scenarios"][scenario][window]
                comparisons[scenario][window] = metric_delta(
                    source_metric, bridge_metric
                )
        results[mode] = {
            "scale": scale,
            "source_trade_ohlc_result": mode_source["result"],
            "trade_trigger_live_semantics_result": bridge,
            "delta": comparisons,
            "interpretation": (
                "This isolates the execution-state migration: trigger OHLC equals "
                "trade OHLC, but legacy 1h protection is evaluated on executable 15m "
                "sub-bars and protective gaps fill at trade open."
            ),
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_engine_bridge_audit_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "purpose": (
            "Separate live execution-state resolution changes from mark-vs-trade "
            "price-source changes by feeding trade OHLC into the mark trigger engine."
        ),
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 mark执行引擎桥接审计（2026-07-15）",
        "",
        "本审计把trade OHLC同时作为保护触发源，用于分离“执行状态机分辨率变化”与“mark/trade价格源差异”。",
        "",
        "| 路线 | 原hard pass | 桥接hard pass | full交易变化 | full年化变化 | full回撤变化 | 当前3m收益变化 |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        delta = row["delta"]["base"]["full"]
        current = row["delta"]["base"]["current_3m"]
        lines.append(
            f"| `{mode}` | `{row['source_trade_ohlc_result']['hard_pass']}` | "
            f"`{row['trade_trigger_live_semantics_result']['hard_pass']}` | "
            f"{delta['trades']:+.0f} | {delta['annual_multiple']:+.3f}x | "
            f"{delta['max_dd']:+.2%} | {current['total_return']:+.2%} |"
        )
    lines.extend(
        [
            "",
            "桥接差异属于从研究K线状态机迁移到可执行保护状态机的真实模型变化，不应通过强行逐笔相等来隐藏。",
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
                        "source_hard_pass": row["source_trade_ohlc_result"][
                            "hard_pass"
                        ],
                        "bridge_hard_pass": row[
                            "trade_trigger_live_semantics_result"
                        ]["hard_pass"],
                        "base_full_delta": row["delta"]["base"]["full"],
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
