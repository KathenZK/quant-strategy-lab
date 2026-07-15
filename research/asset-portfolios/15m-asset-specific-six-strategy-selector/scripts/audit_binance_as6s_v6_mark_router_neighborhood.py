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
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_router_neighborhood_2026-07-15.json"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-router-neighborhood-2026-07-15.md"
MODE = "strong_breakout_preemptive"


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
        "base_full": result["scenarios"]["base"]["full"],
        "base_current_3m": result["scenarios"]["base"]["current_3m"],
        "stress_full": result["scenarios"]["stress_8bps"]["full"],
        "stress_current_3m": result["scenarios"]["stress_8bps"]["current_3m"],
        "k2_full": result["scenarios"]["k_plus_2"]["full"],
        "k2_current_3m": result["scenarios"]["k_plus_2"]["current_3m"],
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
    options: dict[str, list[dict[str, Any]]] = {}
    active: list[str] = []
    mode_source = source["results"][MODE]
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
    selected_scale = float(
        mark_result["results"][MODE]["best_mark_price_scale_result"]["scale"]
    )
    baseline_routed = account.route_scenarios(
        selection,
        sleeves,
        options,
        mode=MODE,
        frames=frames,
        funding=funding,
    )
    baseline = account.scale_result(baseline_routed, selected_scale)
    scale_rows = [
        compact(account.scale_result(baseline_routed, scale))
        for scale in (0.54, 0.57, 0.60, 0.63, 0.66, 0.69, 0.72)
    ]
    settings = [
        (0.70, 0.05, 1),
        (0.80, 0.05, 1),
        (0.75, 0.00, 1),
        (0.75, 0.10, 1),
        (0.75, 0.05, 0),
        (0.75, 0.05, 2),
        (0.75, 0.05, 4),
    ]
    router_rows: list[dict[str, Any]] = []
    for threshold, margin, min_hold in settings:
        routed = account.route_scenarios(
            selection,
            sleeves,
            options,
            mode=MODE,
            frames=frames,
            funding=funding,
            preemption_threshold=threshold,
            preemption_margin=margin,
            preemption_min_hold_hours=min_hold,
        )
        result = account.scale_result(routed, selected_scale)
        router_rows.append(
            {
                "threshold": threshold,
                "margin": margin,
                "min_hold_hours": min_hold,
                "result": compact(result),
                "score_delta": result["score"] - baseline["score"],
            }
        )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_router_neighborhood_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "mode": MODE,
        "selected_scale": selected_scale,
        "baseline": compact(baseline),
        "scale_neighborhood": scale_rows,
        "scale_hard_pass_rate": sum(row["hard_pass"] for row in scale_rows)
        / len(scale_rows),
        "scale_buffer_pass_rate": sum(
            row["hard_pass"] and row["robust_dd_buffer_pass"] for row in scale_rows
        )
        / len(scale_rows),
        "router_neighborhood": router_rows,
        "router_hard_pass_rate": sum(
            row["result"]["hard_pass"] for row in router_rows
        )
        / len(router_rows),
        "router_buffer_pass_rate": sum(
            row["result"]["hard_pass"]
            and row["result"]["robust_dd_buffer_pass"]
            for row in router_rows
        )
        / len(router_rows),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 mark抢占路由邻域（2026-07-15）",
        "",
        "对完整mark账户重放独立扰动scale、抢占阈值、强度差和最短持仓。",
        "",
        f"- scale硬门槛通过率：{payload['scale_hard_pass_rate']:.2%}。",
        f"- scale含-18.5%缓冲通过率：{payload['scale_buffer_pass_rate']:.2%}。",
        f"- 路由参数硬门槛通过率：{payload['router_hard_pass_rate']:.2%}。",
        f"- 路由参数含缓冲通过率：{payload['router_buffer_pass_rate']:.2%}。",
        "",
        "| threshold | margin | min hold | hard pass | 缓冲通过 | 分数变化 |",
        "|---:|---:|---:|---|---|---:|",
    ]
    for row in router_rows:
        result = row["result"]
        lines.append(
            f"| {row['threshold']:.2f} | {row['margin']:.2f} | "
            f"{row['min_hold_hours']}h | `{result['hard_pass']}` | "
            f"`{result['robust_dd_buffer_pass']}` | {row['score_delta']:+.3f} |"
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
                "scale_hard_pass_rate": payload["scale_hard_pass_rate"],
                "scale_buffer_pass_rate": payload["scale_buffer_pass_rate"],
                "router_hard_pass_rate": payload["router_hard_pass_rate"],
                "router_buffer_pass_rate": payload["router_buffer_pass_rate"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
