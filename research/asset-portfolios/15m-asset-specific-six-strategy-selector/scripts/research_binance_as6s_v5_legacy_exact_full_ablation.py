from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

import pandas as pd

import audit_legacy_asset_specific_1h_sleeves as legacy
from as6s_engine import PREFIT_END, REUSED_END, STARTS, SYMBOLS, load_funding
from as6s_live_safe_router import nonpreemptive
from combine_hybrid_asset_specific_account import UnifiedTrade, strict_metrics


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v5-legacy-exact-full-ablation-2026-07-15.md"
SCENARIOS = {
    "base_4bps_k1": (0.0004, 1),
    "stress_8bps_k1": (0.0008, 1),
    "base_4bps_k2": (0.0004, 2),
}
CONTRACT_FIELDS = {"name", "style", "entry_delay_bars"}


def distinct(values: list[Any], baseline: Any, limit: int = 2) -> list[Any]:
    return [value for value in values if value != baseline][:limit]


def replacement_groups(cfg: Any, frame: pd.DataFrame) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []

    def integer_suffixes(pattern: str) -> list[int]:
        regex = re.compile(pattern)
        return sorted(
            {
                int(match.group(1))
                for column in frame.columns
                if (match := regex.fullmatch(column)) is not None
            }
        )

    ema_windows = integer_suffixes(r"ema(\d+)")
    roc_windows = integer_suffixes(r"roc(\d+)_bps")
    indicator_patterns = {
        "donchian_break": r"don_high(\d+)",
        "bb_revert": r"bb_z(\d+)",
        "bb_break": r"bb_z(\d+)",
        "rsi_reversal": r"rsi(\d+)",
        "stoch_reversal": r"stoch_k(\d+)",
        "cci_reversal": r"cci(\d+)",
        "williams_reversal": r"willr(\d+)",
        "keltner_break": r"band_mid(\d+)",
        "squeeze_release": r"bb_width_z(\d+)",
        "vwap_revert": r"vwap_dev_atr(\d+)",
    }
    indicator_windows = (
        integer_suffixes(indicator_patterns[cfg.style])
        if cfg.style in indicator_patterns
        else [7, 14, 20, 21, 24, 48, 72, 96]
    )
    macd_regex = re.compile(r"macd_hist_(\d+)_(\d+)_(\d+)")
    available_macd_sets = sorted(
        {
            tuple(int(value) for value in match.groups())
            for column in frame.columns
            if (match := macd_regex.fullmatch(column)) is not None
        }
    )
    available_htf_modes = [
        mode for mode in ("h4", "h12", "d1") if f"{mode}_spread" in frame
    ]

    def single(field: str, values: list[Any]) -> None:
        candidates = distinct(values, getattr(cfg, field))
        groups.append(
            {
                "label": field,
                "fields": [field],
                "updates": [{field: value} for value in candidates],
            }
        )

    single("side_mode", ["both", "long", "short"])
    single("ema_fast", ema_windows)
    single("ema_slow", ema_windows)
    single("ema_htf", ema_windows)
    single("indicator_window", indicator_windows)
    low_values = [10.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    high_values = [55.0, 60.0, 70.0, 75.0, 80.0, 90.0]
    single("threshold_low", [v for v in low_values if v < cfg.threshold_high])
    single("threshold_high", [v for v in high_values if v > cfg.threshold_low])
    single("band_k", [0.5, 0.75, 1.0, 1.5, 2.0, 2.5])
    single("pullback_atr", [-0.5, -0.25, 0.0, 0.25, 0.75])
    single("roc_window", roc_windows)
    single("roc_threshold_bps", [0.0, 25.0, 50.0, 100.0, 300.0])
    baseline_macd = (cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    groups.append(
        {
            "label": "macd_set",
            "fields": ["macd_fast", "macd_slow", "macd_signal"],
            "updates": [
                {"macd_fast": fast, "macd_slow": slow, "macd_signal": signal}
                for fast, slow, signal in distinct(available_macd_sets, baseline_macd)
            ],
        }
    )
    single("min_adx", [0.0, 10.0, 20.0, 28.0, 36.0, 40.0])
    single(
        "max_adx",
        [value for value in [24.0, 36.0, 55.0, 100.0] if value >= cfg.min_adx],
    )
    single("min_rvol", [0.0, 0.75, 1.0, 1.5, 2.0, 3.5])
    single("min_atr_bps", [0.0, 25.0, 50.0, 100.0, 125.0, 200.0])
    single(
        "max_atr_bps",
        [value for value in [150.0, 250.0, 400.0, 600.0, 10_000.0] if value >= cfg.min_atr_bps],
    )
    single("min_dir_roc_bps", [-10_000.0, -300.0, -100.0, 0.0, 100.0])
    single("max_dist_ema_bps", [300.0, 750.0, 1_500.0, 10_000.0])
    single("htf_mode", ["none", *available_htf_modes])
    single("require_macd_turn", [False, True])
    single("require_body_dir", [False, True])
    single("max_aligned_funding_bps", [1.0, 2.0, 8.0, 10_000.0])
    exit_updates: list[dict[str, Any]]
    if cfg.exit_kind == "fixed":
        exit_updates = [
            {
                "exit_kind": "trailing",
                "trail_activation_atr": 1.0,
                "trail_atr": 1.0,
            }
        ]
    else:
        exit_updates = [{"exit_kind": "fixed"}]
    groups.append(
        {
            "label": "exit_kind",
            "fields": ["exit_kind"],
            "updates": exit_updates,
        }
    )
    single("tp_atr", [0.75, 1.0, 1.5, 2.5, 4.0])
    single("sl_atr", [2.0, 3.0, 4.0, 5.0, 6.0])
    single("trail_activation_atr", [0.75, 1.0, 2.0, 3.0])
    single("trail_atr", [0.75, 1.0, 1.5, 2.5])
    single("max_hold_bars", [18, 36, 48, 72, 96, 120, 240])
    single("cooldown_bars", [0, 3, 12, 24, 36])
    single("sizing_kind", ["fixed", "risk"])
    single("fixed_leverage", [1.0, 2.0, 3.0])
    single("risk_fraction", [0.005, 0.01, 0.025])
    single("max_leverage", [1.0, 2.5, 3.0])
    covered = CONTRACT_FIELDS | {
        field for group in groups for field in group["fields"]
    }
    actual = set(asdict(cfg) if is_dataclass(cfg) else vars(cfg))
    if covered != actual:
        raise RuntimeError(
            f"full field coverage drift for {cfg.name}: missing={actual-covered}, extra={covered-actual}"
        )
    return groups


def prepare() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, pd.DataFrame],
    dict[str, tuple[Any, Any]],
]:
    first, contexts = legacy.prepare_legacy()
    raw_frames = {symbol: legacy.aggregate_h1(symbol) for symbol in SYMBOLS}
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS}
    featured: dict[str, pd.DataFrame] = {}
    prefixes: dict[str, tuple[Any, Any]] = {}
    for symbol in SYMBOLS:
        asset = symbol.removesuffix("USDT")
        engine = contexts[asset]["engine"]
        featured[asset] = engine.add_features(raw_frames[symbol], funding[symbol])
        prefixes[asset] = engine.funding_prefix(funding[symbol])
        if featured[asset]["ts"].max() >= REUSED_END:
            raise RuntimeError(f"{asset} legacy frame crossed research cutoff")
        if funding[symbol]["ts"].max() >= REUSED_END:
            raise RuntimeError(f"{asset} legacy funding crossed research cutoff")
    featured["HYPE"] = sys.modules[
        "research_hype_1h_ar_v3_full_ablation"
    ].ensure_extra_macd_features(featured["HYPE"])

    captured: dict[str, Any] = {}
    original = legacy.simulate_stateless

    def capture(
        engine: Any,
        frame: pd.DataFrame,
        cfg: Any,
        funding_times: Any,
        funding_cumulative: Any,
    ) -> list[Any]:
        del engine, frame, funding_times, funding_cumulative
        captured[cfg.name] = cfg
        return []

    legacy.simulate_stateless = capture
    try:
        legacy.simulate_components(
            first,
            contexts,
            raw_frames,
            funding,
            slippage=0.0004,
            delay=1,
        )
    finally:
        legacy.simulate_stateless = original
    return contexts, captured, featured, prefixes


def to_unified(
    sleeve: str,
    audit: dict[str, Any],
    cfg: Any,
    rows: list[Any],
) -> list[UnifiedTrade]:
    exposure = float(audit["exposure"])
    strength = 0.75 * float(audit["quality"])
    return [
        UnifiedTrade(
            sleeve=sleeve,
            symbol=audit["symbol"],
            mechanism=audit["mechanism"],
            source_timeframe="1h",
            side=int(trade.side),
            entry_ts=trade.entry_ts,
            exit_ts=trade.exit_ts,
            entry_price=float(trade.entry_price),
            net_return_1x=float(trade.net_ret_1x),
            mae_return_1x=float(trade.mae_1x),
            raw_strength=0.0,
            cooldown_hours=int(cfg.cooldown_bars),
            strength=strength,
            exposure=exposure,
            exit_reason=str(trade.exit_reason),
        )
        for trade in rows
        if trade.exit_ts < REUSED_END
    ]


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


def metrics_by_window(
    rows: list[UnifiedTrade], start: pd.Timestamp
) -> dict[str, Any]:
    selected = nonpreemptive(rows, start=start, end=REUSED_END)
    return {
        "prefit": strict_metrics(selected, start, PREFIT_END),
        "reused_diagnostic": strict_metrics(selected, PREFIT_END, REUSED_END),
        "through_cutoff": strict_metrics(selected, start, REUSED_END),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contexts, configs, featured, prefixes = prepare()
    results: dict[str, Any] = {}
    for sleeve in manifest["selected_sleeves"]:
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] != "legacy_asset_specific_1h":
            continue
        asset = audit["symbol"].removesuffix("USDT")
        expected_name = next(
            name
            for name, cfg in configs.items()
            if cfg.style == audit["mechanism"] and name.startswith(asset)
        )
        baseline_cfg = configs[expected_name]
        engine = contexts[asset]["engine"]
        start = STARTS[audit["symbol"]]
        groups = replacement_groups(baseline_cfg, featured[asset])
        baseline_paths: dict[str, list[tuple[Any, ...]]] = {}
        baseline_metrics: dict[str, Any] = {}
        for scenario, (slippage, delay) in SCENARIOS.items():
            engine.SLIPPAGE_PER_FILL = slippage
            cfg = replace(baseline_cfg, entry_delay_bars=delay)
            raw = legacy.simulate_stateless(
                engine,
                featured[asset],
                cfg,
                *prefixes[asset],
            )
            unified = to_unified(sleeve, audit, cfg, raw)
            selected = nonpreemptive(unified, start=start, end=REUSED_END)
            baseline_paths[scenario] = path_key(selected)
            baseline_metrics[scenario] = metrics_by_window(unified, start)

        group_results: dict[str, Any] = {}
        for group in groups:
            variants: list[dict[str, Any]] = []
            for updates in group["updates"]:
                scenario_rows: dict[str, Any] = {}
                for scenario, (slippage, delay) in SCENARIOS.items():
                    engine.SLIPPAGE_PER_FILL = slippage
                    cfg = replace(
                        baseline_cfg,
                        **updates,
                        entry_delay_bars=delay,
                    )
                    raw = legacy.simulate_stateless(
                        engine,
                        featured[asset],
                        cfg,
                        *prefixes[asset],
                    )
                    unified = to_unified(sleeve, audit, cfg, raw)
                    selected = nonpreemptive(unified, start=start, end=REUSED_END)
                    key = path_key(selected)
                    scenario_rows[scenario] = {
                        "generated_opportunities": len(unified),
                        "selected_trades": len(selected),
                        "exact_path_equal_to_baseline": key == baseline_paths[scenario],
                        "metrics": metrics_by_window(unified, start),
                    }
                variants.append(
                    {
                        "updates": updates,
                        "all_scenarios_exact": all(
                            row["exact_path_equal_to_baseline"]
                            for row in scenario_rows.values()
                        ),
                        "scenarios": scenario_rows,
                    }
                )
            group_results[group["label"]] = {
                "fields": group["fields"],
                "variants": variants,
                "classification": (
                    "remove_noop"
                    if variants and all(row["all_scenarios_exact"] for row in variants)
                    else "active_tunable"
                ),
            }
        results[sleeve] = {
            "symbol": audit["symbol"],
            "mechanism": audit["mechanism"],
            "start": start.isoformat(),
            "baseline_config": asdict(baseline_cfg),
            "contract_fixed": sorted(CONTRACT_FIELDS),
            "baseline_metrics": baseline_metrics,
            "parameter_groups": group_results,
        }

    noop_groups = [
        {"sleeve": sleeve, "group": group}
        for sleeve, row in results.items()
        for group, values in row["parameter_groups"].items()
        if values["classification"] == "remove_noop"
    ]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v5_six_legacy_sleeves_exact_config_full_parameter_ablation",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "scenarios": SCENARIOS,
        "sleeves": len(results),
        "parameter_groups": sum(
            len(row["parameter_groups"]) for row in results.values()
        ),
        "variant_evaluations": sum(
            len(group["variants"])
            for row in results.values()
            for group in row["parameter_groups"].values()
        ),
        "remove_noop_groups": noop_groups,
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V5 六条旧1h腿精确配置全参数消融（2026-07-15）",
        "",
        "本轮不是直接引用旧家族结论，而是从V5实际运行模块重建六条精确配置，在当前外部暴露与单仓状态语义下重新逐字段扰动。严格使用 `ts < 2026-07-14T09:00Z`。",
        "",
        f"- 腿：`{len(results)}`",
        f"- 参数组：`{payload['parameter_groups']}`",
        f"- 参数变体：`{payload['variant_evaluations']}`，每个均复测三执行场景。",
        f"- 所有扰动均三场景交易路径不变、可移出clean接口的参数组实例：`{len(noop_groups)}`。",
        "- `name/style/entry_delay_bars`为身份、机制和执行契约，不按普通Alpha参数删除；K+2已独立覆盖entry delay。",
        "",
        "## 逐腿摘要",
        "",
        "| 腿 | 参数组 | 可移除无作用组 |",
        "|---|---:|---:|",
    ]
    for sleeve, row in results.items():
        noops = sum(
            group["classification"] == "remove_noop"
            for group in row["parameter_groups"].values()
        )
        lines.append(f"| `{sleeve}` | {len(row['parameter_groups'])} | {noops} |")
    lines.extend(
        [
            "",
            "字段只有在至少两个替代值、三个执行场景下完整交易路径均不变时才标记 `remove_noop`；其余保留为active_tunable，后续仅在clean表面做局部微调。",
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
                "sleeves": len(results),
                "parameter_groups": payload["parameter_groups"],
                "variant_evaluations": payload["variant_evaluations"],
                "remove_noop_groups": len(noop_groups),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
