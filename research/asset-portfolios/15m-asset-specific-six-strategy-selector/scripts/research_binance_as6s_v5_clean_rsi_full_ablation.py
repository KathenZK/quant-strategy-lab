from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import audit_binance_as6s_clean_rsi_hf_robustness as clean
from as6s_engine import (
    PREFIT_END,
    REUSED_END,
    STARTS,
    funding_arrays,
    load_funding,
    load_symbol_frame,
)
from as6s_live_safe_router import nonpreemptive
from combine_hybrid_asset_specific_account import UnifiedTrade, strict_metrics


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v5_clean_rsi_full_ablation_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v5-clean-rsi-full-ablation-2026-07-15.md"
SCENARIOS = {
    "base_4bps_k1": (0.0004, 1),
    "stress_8bps_k1": (0.0008, 1),
    "base_4bps_k2": (0.0004, 2),
}


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    config_changes: dict[str, Any]
    filter_changes: dict[str, Any]
    live_promotable: bool = True


VARIANTS = (
    Variant("baseline", {}, {}),
    Variant("remove_min_atr", {}, {"min_atr_pct96": 0.0}),
    Variant("remove_max_atr", {}, {"max_atr_pct96": 99.0}),
    Variant("remove_macd_direction", {}, {"min_dir_macd": -99.0}),
    Variant("remove_rvol_min", {"min_rvol96": 0.0}, {}),
    Variant("remove_h1", {"h1_confirm": False}, {}),
    Variant("remove_rsi14_band", {"rsi14_band": False}, {}),
    Variant("remove_tp", {"take_profit_pct": 99.0}, {}),
    Variant("remove_stop_diagnostic", {"stop_pct": 99.0}, {}, False),
    Variant("remove_max_hold_diagnostic", {"max_hold_bars": 100_000}, {}, False),
)


def metrics_by_window(trades: list[UnifiedTrade], symbol: str) -> dict[str, Any]:
    selected = nonpreemptive(trades, start=STARTS[symbol], end=REUSED_END)
    return {
        "prefit": strict_metrics(selected, STARTS[symbol], PREFIT_END),
        "reused_diagnostic": strict_metrics(selected, PREFIT_END, REUSED_END),
        "through_cutoff": strict_metrics(selected, STARTS[symbol], REUSED_END),
    }


def path_key(rows: list[UnifiedTrade]) -> list[tuple[Any, ...]]:
    return [
        (
            row.side,
            row.entry_ts,
            row.exit_ts,
            round(row.net_return_1x, 12),
            round(row.mae_return_1x, 12),
            row.exit_reason,
        )
        for row in rows
    ]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sleeve = next(
        name
        for name in manifest["selected_sleeves"]
        if manifest["sleeve_configs"][name]["source"]
        == "asset_specific_clean_rsi_hf"
    )
    audit = manifest["sleeve_configs"][sleeve]
    symbol = audit["symbol"]
    baseline_config = clean.Config(**audit["config"])
    frame = load_symbol_frame(symbol, end=REUSED_END)
    funding = load_funding(symbol, end=REUSED_END)
    if frame["ts"].max() >= REUSED_END or funding["ts"].max() >= REUSED_END:
        raise RuntimeError("clean RSI ablation crossed research cutoff")
    raw = frame[["ts", "open", "high", "low", "close", "volume"]]
    features = clean.evolution.add_rsi_features(clean.evolution.add_features(raw, []))
    market = clean.mii.build_market_arrays(features)
    times, prefix = funding_arrays(funding)
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    results: dict[str, Any] = {}
    baseline_paths: dict[str, list[tuple[Any, ...]]] = {}

    for variant in VARIANTS:
        config = replace(baseline_config, **variant.config_changes)
        state = clean.mii.signal_state(features, config.signal)
        filter_spec = replace(config.filter, **variant.filter_changes)
        scenario_rows: dict[str, Any] = {}
        for scenario, (slippage, delay) in SCENARIOS.items():
            generated = clean.robust_trades(
                market,
                state,
                config.exit,
                times,
                prefix,
                slippage=slippage,
                entry_delay_bars=delay,
            )
            selected_raw = clean.select_nonoverlap(generated, filter_spec)
            trades = [
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=symbol,
                    mechanism="clean_rsi_reversal",
                    source_timeframe="15m",
                    side=trade.direction,
                    entry_ts=trade.entry_ts,
                    exit_ts=trade.exit_ts,
                    entry_price=trade.entry_price,
                    net_return_1x=trade.raw_return,
                    mae_return_1x=trade.min_path_return,
                    raw_strength=0.0,
                    strength=0.75 * quality,
                    exposure=exposure,
                    exit_reason=trade.exit_reason,
                )
                for trade in selected_raw
                if trade.exit_ts < REUSED_END
            ]
            account_path = nonpreemptive(
                trades,
                start=STARTS[symbol],
                end=REUSED_END,
            )
            key = path_key(account_path)
            if variant.name == "baseline":
                baseline_paths[scenario] = key
            scenario_rows[scenario] = {
                "generated_signals": len(generated),
                "filtered_trades": len(trades),
                "selected_trades": len(account_path),
                "exact_path_equal_to_baseline": key == baseline_paths.get(scenario, []),
                "metrics": metrics_by_window(trades, symbol),
            }
        results[variant.name] = {
            "config_changes": variant.config_changes,
            "filter_changes": variant.filter_changes,
            "live_promotable": variant.live_promotable,
            "scenarios": scenario_rows,
        }

    exact_noops = [
        name
        for name, row in results.items()
        if name != "baseline"
        and all(
            scenario["exact_path_equal_to_baseline"]
            for scenario in row["scenarios"].values()
        )
    ]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v5_clean_rsi_exact_full_component_ablation",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "sleeve": sleeve,
        "symbol": symbol,
        "baseline_config": asdict(baseline_config),
        "implicit_fixed_conditions_tested": [
            "min_dir_macd=0",
            "max_atr_pct96=0.028",
        ],
        "structural_not_removed": ["RSI crossing event", "RSI window and thresholds"],
        "scenarios": SCENARIOS,
        "variant_evaluations": len(results),
        "exact_noop_variants": exact_noops,
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V5 HYPE clean-RSI全组件消融（2026-07-15）",
        "",
        "严格使用 `ts < 2026-07-14T09:00Z`；未读取未来OOS，未修改V5。",
        "",
        f"- 变体（含基线）：`{len(results)}`",
        f"- 三场景精确无变化：`{len(exact_noops)}`，即 `{', '.join(exact_noops) or '无'}`。",
        "- 除10个显式Config字段外，已补测固定MACD方向和固定ATR96上限。",
        "- `remove_stop_diagnostic` 与 `remove_max_hold_diagnostic` 不可promotion。",
        "- RSI crossing及其窗口/阈值是机制本体，进入clean-surface微调，不用零交易伪消融代替。",
        "",
        f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "variant_evaluations": len(results),
                "exact_noop_variants": exact_noops,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
