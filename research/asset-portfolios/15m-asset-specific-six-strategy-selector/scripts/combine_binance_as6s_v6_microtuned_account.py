from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

import audit_binance_as6s_clean_rsi_hf_robustness as clean
from as6s_engine import (
    PREFIT_END,
    REUSED_END,
    STARTS,
    funding_arrays,
    load_funding,
    load_symbol_frame,
)
from as6s_live_safe_router import nonpreemptive, preemptive
from combine_hybrid_asset_specific_account import UnifiedTrade, strict_metrics
import research_binance_as6s_v5_legacy_exact_full_ablation as legacy_full
import reveal_binance_as6s_v5_joint_state_future_oos as v5


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
V5_REFERENCE = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json"
)
FRONTIER_TUNE = FAMILY_DIR / "artifacts/binance_as6s_v6_frontier_microtune_2026-07-15.json"
CLEAN_TUNE = FAMILY_DIR / "artifacts/binance_as6s_v6_clean_rsi_microtune_2026-07-15.json"
LEGACY_TUNE = FAMILY_DIR / "artifacts/binance_as6s_v6_legacy_microtune_2026-07-15.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json"
TRADES_OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_trades_2026-07-15.csv"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-microtuned-account-2026-07-15.md"
RESEARCH_START = pd.Timestamp("2024-07-14T00:00:00Z")
CURRENT_START = PREFIT_END
ALL_SIX_ACTIVE_START = max(STARTS.values())
SCENARIOS = {
    "base": (0.0004, 1),
    "stress_8bps": (0.0008, 1),
    "k_plus_2": (0.0004, 2),
}
SCALES = (
    0.25,
    0.30,
    0.33,
    0.36,
    0.40,
    0.44,
    0.48,
    0.50,
    0.54,
    0.55,
    0.57,
    0.60,
    0.63,
    0.66,
    0.69,
    0.72,
    0.75,
    1.0,
)
TOP_OPTIONS = 8
ROBUST_DD_BUFFER = -0.185


def unique_configs(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    output = [baseline]
    seen = {json.dumps(baseline, sort_keys=True, default=str)}
    for row in rows:
        config = row["config"]
        key = json.dumps(config, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        output.append(config)
        if len(output) >= TOP_OPTIONS:
            break
    return output


def clean_candidate_universe(
    sleeve: str,
    audit: dict[str, Any],
    config_dict: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, list[UnifiedTrade]]:
    symbol = audit["symbol"]
    config = clean.Config(**config_dict)
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    raw = frames[symbol][["ts", "open", "high", "low", "close", "volume"]]
    features = clean.evolution.add_rsi_features(clean.evolution.add_features(raw, []))
    market = clean.mii.build_market_arrays(features)
    state = clean.mii.signal_state(features, config.signal)
    filter_spec = replace(config.filter, max_atr_pct96=99.0)
    times, prefix = funding_arrays(funding[symbol])
    output: dict[str, list[UnifiedTrade]] = {}
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
        output[scenario] = [
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
            for trade in generated
            if clean.mii.passes_filter(trade, filter_spec)
            and STARTS[symbol] <= trade.entry_ts < REUSED_END
            and trade.exit_ts < REUSED_END
        ]
    return output


def legacy_candidate_universe(
    sleeve: str,
    audit: dict[str, Any],
    config_dict: dict[str, Any],
    contexts: dict[str, Any],
    captured: dict[str, Any],
    featured: dict[str, pd.DataFrame],
    prefixes: dict[str, tuple[Any, Any]],
) -> dict[str, list[UnifiedTrade]]:
    asset = audit["symbol"].removesuffix("USDT")
    baseline = next(
        cfg
        for name, cfg in captured.items()
        if name.startswith(asset) and cfg.style == audit["mechanism"]
    )
    config = type(baseline)(**config_dict)
    engine = contexts[asset]["engine"]
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in SCENARIOS.items():
        engine.SLIPPAGE_PER_FILL = slippage
        scenario_config = replace(config, entry_delay_bars=delay)
        rows = legacy_full.legacy.simulate_stateless(
            engine,
            featured[asset],
            scenario_config,
            *prefixes[asset],
        )
        output[scenario] = legacy_full.to_unified(
            sleeve, audit, scenario_config, rows
        )
    return output


def metric(trades: list[UnifiedTrade], start: pd.Timestamp, scale: float) -> dict[str, Any]:
    result = strict_metrics(trades, start, REUSED_END, scale)
    days = max((REUSED_END - start).total_seconds() / 86400.0, 1.0)
    return {**result, "trades_per_day": result["trades"] / days}


def route_scenarios(
    selection: tuple[int, ...],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
    preemption_threshold: float = 0.75,
    preemption_margin: float = 0.05,
    preemption_min_hold_hours: int = 1,
) -> dict[str, list[UnifiedTrade]]:
    output: dict[str, list[UnifiedTrade]] = {}
    funding_arrays_by_symbol = {
        symbol: funding_arrays(frame) for symbol, frame in funding.items()
    }
    for scenario, (slippage, _delay) in SCENARIOS.items():
        items = [
            trade
            for sleeve, option_index in zip(sleeves, selection, strict=True)
            if option_index >= 0
            for trade in options[sleeve][option_index]["universe"][scenario]
        ]
        if mode == "nonpreemptive":
            output[scenario] = nonpreemptive(
                items, start=RESEARCH_START, end=REUSED_END
            )
        else:
            output[scenario] = preemptive(
                items,
                start=RESEARCH_START,
                end=REUSED_END,
                threshold=preemption_threshold,
                margin=preemption_margin,
                min_hold_hours=preemption_min_hold_hours,
                bars=frames,
                funding=funding_arrays_by_symbol,
                slippage=slippage,
            )
    return output


def scale_result(
    routed: dict[str, list[UnifiedTrade]],
    scale: float,
) -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    for scenario, trades in routed.items():
        scenarios[scenario] = {
            "full": metric(trades, RESEARCH_START, scale),
            "current_3m": metric(trades, CURRENT_START, scale),
            "all_six_active": metric(trades, ALL_SIX_ACTIVE_START, scale),
            "1m": metric(trades, REUSED_END - pd.DateOffset(months=1), scale),
            "6m": metric(trades, REUSED_END - pd.DateOffset(months=6), scale),
            "1y": metric(trades, REUSED_END - pd.DateOffset(years=1), scale),
        }
    checks: dict[str, bool] = {
        "base_full_trades_ge_200": scenarios["base"]["full"]["trades"] >= 200,
        "base_current_trades_ge_30": scenarios["base"]["current_3m"]["trades"] >= 30,
        "base_current_frequency_1_to_2": 1.0
        <= scenarios["base"]["current_3m"]["trades_per_day"]
        <= 2.0,
        "base_all_six_frequency_1_to_2": 1.0
        <= scenarios["base"]["all_six_active"]["trades_per_day"]
        <= 2.0,
        "effective_leverage_le_3": scale * 3.0 <= 3.0,
    }
    for scenario in SCENARIOS:
        for window in ("full", "current_3m"):
            row = scenarios[scenario][window]
            prefix = f"{scenario}_{window}"
            checks[f"{prefix}_win_ge_80pct"] = row["win_rate"] >= 0.80
            checks[f"{prefix}_dd_lt_20pct"] = row["max_dd"] > -0.20
            checks[f"{prefix}_return_positive"] = row["total_return"] > 0.0
    hard_pass = all(checks.values())
    base = scenarios["base"]
    minimum_gate_win = min(
        scenarios[scenario][window]["win_rate"]
        for scenario in SCENARIOS
        for window in ("full", "current_3m")
    )
    minimum_gate_dd = min(
        scenarios[scenario][window]["max_dd"]
        for scenario in SCENARIOS
        for window in ("full", "current_3m")
    )
    score = float(
        2.2 * math.log(max(1.0 + base["full"]["total_return"], 1e-9))
        + 1.6 * math.log(max(1.0 + base["current_3m"]["total_return"], 1e-9))
        + 0.7 * math.log(max(1.0 + scenarios["stress_8bps"]["full"]["total_return"], 1e-9))
        + 0.7 * math.log(max(1.0 + scenarios["k_plus_2"]["full"]["total_return"], 1e-9))
        + 2.0 * base["full"]["win_rate"]
        + 1.5 * base["current_3m"]["win_rate"]
        + 4.0 * minimum_gate_win
        + 6.0 * minimum_gate_dd
        - 2.5 * abs(base["current_3m"]["trades_per_day"] - 1.25)
        - 1.5 * abs(base["all_six_active"]["trades_per_day"] - 1.25)
        - 12.0 * max(0.0, 1.10 - base["current_3m"]["trades_per_day"])
        - 12.0 * sum(not value for value in checks.values())
    )
    return {
        "scale": scale,
        "effective_max_leverage": scale * 3.0,
        "hard_pass": hard_pass,
        "checks": checks,
        "score": score,
        "scenarios": scenarios,
    }


def evaluate_selection(
    selection: tuple[int, ...],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], dict[str, list[UnifiedTrade]]]:
    routed = route_scenarios(
        selection,
        sleeves,
        options,
        mode=mode,
        frames=frames,
        funding=funding,
    )
    scale_rows = [scale_result(routed, scale) for scale in SCALES]
    passing = [row for row in scale_rows if row["hard_pass"]]
    buffered = [
        row
        for row in passing
        if min(
            row["scenarios"][scenario][window]["max_dd"]
            for scenario in SCENARIOS
            for window in ("full", "current_3m")
        )
        > ROBUST_DD_BUFFER
    ]
    chosen = max(buffered or passing or scale_rows, key=lambda row: row["score"])
    return chosen, routed


def coordinate_search(
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
    seed: tuple[int, ...] | None = None,
) -> tuple[tuple[int, ...], dict[str, Any], dict[str, list[UnifiedTrade]], int]:
    current = seed or tuple(0 for _ in sleeves)
    cache: dict[tuple[int, ...], tuple[dict[str, Any], dict[str, list[UnifiedTrade]]]] = {}

    def evaluate(selection: tuple[int, ...]) -> tuple[dict[str, Any], dict[str, list[UnifiedTrade]]]:
        if selection not in cache:
            cache[selection] = evaluate_selection(
                selection,
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
        return cache[selection]

    current_result, current_routed = evaluate(current)
    for _iteration in range(8):
        candidates: list[tuple[float, tuple[int, ...], dict[str, Any], dict[str, list[UnifiedTrade]]]] = []
        for index, sleeve in enumerate(sleeves):
            for option_index in range(-1, len(options[sleeve])):
                if option_index == current[index]:
                    continue
                proposal = list(current)
                proposal[index] = option_index
                proposal_tuple = tuple(proposal)
                result, routed = evaluate(proposal_tuple)
                candidates.append((result["score"], proposal_tuple, result, routed))
        if not candidates:
            break
        _score, proposal, result, routed = max(candidates, key=lambda row: row[0])
        if result["score"] <= current_result["score"] + 1e-12:
            break
        current, current_result, current_routed = proposal, result, routed
    return current, current_result, current_routed, len(cache)


def prune_dominated_sleeves(
    selection: tuple[int, ...],
    result: dict[str, Any],
    routed: dict[str, list[UnifiedTrade]],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> tuple[tuple[int, ...], dict[str, Any], dict[str, list[UnifiedTrade]], int]:
    evaluated = 0
    current = selection
    current_result = result
    current_routed = routed
    while True:
        candidates: list[
            tuple[float, tuple[int, ...], dict[str, Any], dict[str, list[UnifiedTrade]]]
        ] = []
        for sleeve_index, _sleeve in enumerate(sleeves):
            if current[sleeve_index] < 0:
                continue
            proposal = list(current)
            proposal[sleeve_index] = -1
            proposal_tuple = tuple(proposal)
            proposal_routed = route_scenarios(
                proposal_tuple,
                sleeves,
                options,
                mode=mode,
                frames=frames,
                funding=funding,
            )
            proposal_result = scale_result(
                proposal_routed, float(current_result["scale"])
            )
            evaluated += 1
            proposal_minimum_dd = min(
                proposal_result["scenarios"][scenario][window]["max_dd"]
                for scenario in SCENARIOS
                for window in ("full", "current_3m")
            )
            if (
                proposal_result["hard_pass"]
                and proposal_minimum_dd > ROBUST_DD_BUFFER
                and (
                proposal_result["score"] >= current_result["score"] - 1e-12
                )
            ):
                candidates.append(
                    (
                        proposal_result["score"],
                        proposal_tuple,
                        proposal_result,
                        proposal_routed,
                    )
                )
        if not candidates:
            break
        _score, current, current_result, current_routed = max(
            candidates, key=lambda row: row[0]
        )
    return current, current_result, current_routed, evaluated


def selection_payload(
    selection: tuple[int, ...],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        sleeve: (
            {"option": "dropped"}
            if index < 0
            else {
                "option": options[sleeve][index]["option_id"],
                "config": options[sleeve][index]["config"],
            }
        )
        for sleeve, index in zip(sleeves, selection, strict=True)
    }


def prepare_account_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, pd.DataFrame],
    dict[str, pd.DataFrame],
    tuple[str, ...],
    dict[str, list[dict[str, Any]]],
]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reference = json.loads(V5_REFERENCE.read_text(encoding="utf-8"))
    frontier_tune = json.loads(FRONTIER_TUNE.read_text(encoding="utf-8"))
    clean_tune = json.loads(CLEAN_TUNE.read_text(encoding="utf-8"))
    legacy_tune = json.loads(LEGACY_TUNE.read_text(encoding="utf-8"))
    frames = {
        symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in STARTS
    }
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in STARTS}
    if any(frame["ts"].max() >= REUSED_END for frame in frames.values()):
        raise RuntimeError("account search crossed candle cutoff")
    if any(frame["ts"].max() >= REUSED_END for frame in funding.values()):
        raise RuntimeError("account search crossed funding cutoff")

    v5.OOS_END = REUSED_END
    v5.components.OOS_END = REUSED_END
    baseline_universe = v5.build_universe(manifest, frames, funding)
    contexts, captured, featured, prefixes = legacy_full.prepare()
    sleeves = tuple(manifest["selected_sleeves"])
    options: dict[str, list[dict[str, Any]]] = {}
    for sleeve in sleeves:
        audit = manifest["sleeve_configs"][sleeve]
        source = audit["source"]
        rows: list[dict[str, Any]] = [
            {
                "option_id": "v5_baseline",
                "config": audit.get("config"),
                "universe": baseline_universe[sleeve],
            }
        ]
        if source == "prefit_frontier_asset_first":
            configs = unique_configs(
                frontier_tune["results"][sleeve]["robust_ranking"],
                audit["config"],
            )
            for index, config in enumerate(configs[1:], start=1):
                candidate_audit = {**audit, "config": config}
                rows.append(
                    {
                        "option_id": f"frontier_micro_{index}",
                        "config": config,
                        "universe": v5.convert_frontier_raw(
                            sleeve, candidate_audit, frames, funding
                        ),
                    }
                )
        elif source == "asset_specific_clean_rsi_hf":
            configs = unique_configs(clean_tune["robust_ranking"], audit["config"])
            for index, config in enumerate(configs[1:], start=1):
                rows.append(
                    {
                        "option_id": f"clean_rsi_micro_{index}",
                        "config": config,
                        "universe": clean_candidate_universe(
                            sleeve, audit, config, frames, funding
                        ),
                    }
                )
        elif source == "legacy_asset_specific_1h":
            configs = unique_configs(
                legacy_tune["results"][sleeve]["robust_ranking"],
                legacy_tune["results"][sleeve]["baseline"]["config"],
            )
            rows[0]["config"] = configs[0]
            for index, config in enumerate(configs[1:], start=1):
                rows.append(
                    {
                        "option_id": f"legacy_micro_{index}",
                        "config": config,
                        "universe": legacy_candidate_universe(
                            sleeve,
                            audit,
                            config,
                            contexts,
                            captured,
                            featured,
                            prefixes,
                        ),
                    }
                )
        else:
            raise RuntimeError(f"unknown source {source}")
        options[sleeve] = rows
    return manifest, reference, frames, funding, sleeves, options


def main() -> None:
    manifest, reference, frames, funding, sleeves, options = prepare_account_inputs()

    baseline_selection = tuple(0 for _ in sleeves)
    baseline_result, baseline_routed = evaluate_selection(
        baseline_selection,
        sleeves,
        options,
        mode="nonpreemptive",
        frames=frames,
        funding=funding,
    )
    parity = strict_metrics(
        baseline_routed["base"], RESEARCH_START, REUSED_END, 0.40
    )
    expected = reference["comparisons"]["nonpreemptive"]["scenarios"]["base"][
        "full"
    ]
    for field in ("trades", "wins", "win_rate", "total_return", "max_dd"):
        if not math.isclose(float(parity[field]), float(expected[field]), rel_tol=0.0, abs_tol=1e-10):
            raise RuntimeError(
                f"V5 baseline parity failed for {field}: {parity[field]} != {expected[field]}"
            )

    results: dict[str, Any] = {}
    routed_by_mode: dict[str, dict[str, list[UnifiedTrade]]] = {}
    selection_by_mode: dict[str, tuple[int, ...]] = {}
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        selection, result, routed, evaluated = coordinate_search(
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        selection, result, routed, prune_evaluated = prune_dominated_sleeves(
            selection,
            result,
            routed,
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        selection_by_mode[mode] = selection
        routed_by_mode[mode] = routed
        results[mode] = {
            "selection": selection_payload(selection, sleeves, options),
            "evaluated_account_states": evaluated + prune_evaluated,
            "result": result,
        }

    trade_rows: list[dict[str, Any]] = []
    for mode, routed in routed_by_mode.items():
        scale = float(results[mode]["result"]["scale"])
        for trade in routed["base"]:
            trade_rows.append(
                {
                    "mode": mode,
                    "scale": scale,
                    **asdict(trade),
                }
            )
    pd.DataFrame(trade_rows).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_microtuned_account_coordinate_search_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "v5_baseline_parity": {
            "result": "PASS",
            "scale": 0.40,
            "metrics": parity,
        },
        "option_counts": {sleeve: len(rows) for sleeve, rows in options.items()},
        "search": {
            "options_per_sleeve": "V5 baseline plus up to 7 robust microtune configs plus drop",
            "coordinate_iterations_max": 8,
            "scales": SCALES,
            "robust_scale_dd_buffer": ROBUST_DD_BUFFER,
            "soft_preference": (
                "maximize return with extra margins above 80% win, below 20% DD, "
                "and prefer current frequency near 1.25/day with a 1.10/day buffer"
            ),
            "hard_gate": (
                "all base/stress/K+2 full and current: win>=80%, DD<20%, return>0; "
                "base current and all-six-active frequency 1-2/day; leverage<=3x"
            ),
        },
        "baseline_best_scale_result": baseline_result,
        "results": results,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 微调账户重组（2026-07-15）",
        "",
        "V5历史基线先按联合状态重新生成并与冻结结果对拍，然后每条腿在V5基线、最多7个稳健微调配置和删除之间做坐标搜索；排序额外偏好胜率、回撤与频率缓冲。所有结果严格截止 `2026-07-14T09:00Z`。",
        "",
        "- V5基线对拍：`PASS`（553笔路径口径及核心指标一致）。",
        "- 硬门槛：base/8bps/K+2的full与当前3m均要求胜率>=80%、回撤<20%、收益>0；当前3m和六币全活跃期频率均为1-2单/天；有效杠杆<=3x。",
        "- scale选择：在通过硬门槛的scale中，优先要求所有门禁窗口回撤优于-18.5%，保留约1.5个百分点缓冲。",
        "",
        "| 路线 | hard pass | scale | 有效最大杠杆 | full年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        result = row["result"]
        base = result["scenarios"]["base"]
        lines.append(
            f"| `{mode}` | `{result['hard_pass']}` | {result['scale']:.2f} | {result['effective_max_leverage']:.2f}x | "
            f"{base['full']['annual_multiple']:.3f}x | {base['full']['win_rate']:.2%} | {base['full']['max_dd']:.2%} | "
            f"{base['current_3m']['total_return']:+.2%} | {base['current_3m']['win_rate']:.2%} | {base['current_3m']['trades_per_day']:.3f}/日 |"
        )
    lines.extend(
        [
            "",
            "本轮仍是开发样本观察；即便hard pass，也必须继续做账户级参数消融、邻域稳定性、mark-price执行偏差和独立未来三个月OOS。",
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
                "v5_baseline_parity": "PASS",
                "results": {
                    mode: {
                        "hard_pass": row["result"]["hard_pass"],
                        "scale": row["result"]["scale"],
                        "score": row["result"]["score"],
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
