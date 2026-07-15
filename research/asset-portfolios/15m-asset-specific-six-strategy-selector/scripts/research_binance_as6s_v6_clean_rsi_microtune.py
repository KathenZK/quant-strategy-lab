from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import random
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
from as6s_live_safe_router import nonpreemptive
from combine_hybrid_asset_specific_account import UnifiedTrade, strict_metrics


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_clean_rsi_microtune_2026-07-15.json"
REPORT = FAMILY_DIR / "notes/binance-as6s-v6-clean-rsi-microtune-2026-07-15.md"
TRAIN_END = pd.Timestamp("2025-10-14T09:00:00Z")
VALIDATION_1_END = pd.Timestamp("2026-01-14T09:00:00Z")
RANDOM_CANDIDATES = 500
SHORTLIST = 25
SCENARIOS = {
    "base_4bps_k1": (0.0004, 1),
    "stress_8bps_k1": (0.0008, 1),
    "base_4bps_k2": (0.0004, 2),
}


def candidates(base: Any) -> list[Any]:
    domains = (
        (5, 7, 9),
        (35.0, 40.0, 45.0),
        (55.0, 60.0, 65.0),
        (0.0075, 0.00825, 0.009, 0.00975, 0.0105),
        (0.009, 0.0105, 0.012, 0.0135, 0.015),
        (0.036, 0.045, 0.054),
        (32, 40, 48, 56, 64),
    )
    all_values = [
        values
        for values in itertools.product(*domains)
        if values[2] - values[1] >= 15.0
    ]
    rng = random.Random(2026071515)
    rng.shuffle(all_values)
    selected = all_values[: RANDOM_CANDIDATES - 1]
    configs = [base]
    for values in selected:
        configs.append(
            clean.Config(
                rsi_window=values[0],
                rsi_low=values[1],
                rsi_high=values[2],
                min_atr_pct96=values[3],
                min_rvol96=0.0,
                h1_confirm=False,
                rsi14_band=False,
                take_profit_pct=values[4],
                stop_pct=values[5],
                max_hold_bars=values[6],
            )
        )
    unique = {json.dumps(asdict(cfg), sort_keys=True): cfg for cfg in configs}
    return list(unique.values())


def window_metrics(trades: list[UnifiedTrade], symbol: str) -> dict[str, Any]:
    selected = nonpreemptive(trades, start=STARTS[symbol], end=REUSED_END)
    windows = {
        "train": (STARTS[symbol], TRAIN_END),
        "validation_1": (TRAIN_END, VALIDATION_1_END),
        "validation_2": (VALIDATION_1_END, PREFIT_END),
        "prefit": (STARTS[symbol], PREFIT_END),
        "current_diagnostic": (PREFIT_END, REUSED_END),
        "through_cutoff": (STARTS[symbol], REUSED_END),
    }
    return {
        name: strict_metrics(selected, start, end)
        for name, (start, end) in windows.items()
    }


def score(metrics: dict[str, Any]) -> float:
    train = metrics["train"]
    val1 = metrics["validation_1"]
    val2 = metrics["validation_2"]
    prefit = metrics["prefit"]
    current = metrics["current_diagnostic"]
    if prefit["trades"] < 100 or val1["trades"] < 20 or val2["trades"] < 20:
        return -1e12
    return float(
        1.7 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.8 * math.log(max(train["annual_multiple"], 1e-9))
        + 0.9 * math.log(max(val1["annual_multiple"], 1e-9))
        + 1.1 * math.log(max(val2["annual_multiple"], 1e-9))
        + 2.0 * prefit["win_rate"]
        + val1["win_rate"]
        + 1.2 * val2["win_rate"]
        + 4.0 * min(prefit["max_dd"], val1["max_dd"], val2["max_dd"])
        + 0.2 * math.log1p(prefit["trades"])
        + 20.0 * min(0.0, train["total_return"])
        + 24.0 * min(0.0, val1["total_return"])
        + 28.0 * min(0.0, val2["total_return"])
        + 30.0 * min(0.0, current["total_return"])
        + 18.0 * min(0.0, current["win_rate"] - 0.75)
        + 18.0 * min(0.0, current["max_dd"] + 0.20)
    )


def evaluate(
    config: Any,
    *,
    sleeve: str,
    symbol: str,
    quality: float,
    exposure: float,
    features: pd.DataFrame,
    market: Any,
    funding_times: Any,
    funding_prefix: Any,
    scenario: str,
) -> dict[str, Any]:
    slippage, delay = SCENARIOS[scenario]
    state = clean.mii.signal_state(features, config.signal)
    # max_atr_pct96=2.8% was exact-noop in the full ablation, so the clean
    # interface removes it by fixing an unbounded cap here.
    filter_spec = replace(config.filter, max_atr_pct96=99.0)
    generated = clean.robust_trades(
        market,
        state,
        config.exit,
        funding_times,
        funding_prefix,
        slippage=slippage,
        entry_delay_bars=delay,
    )
    raw = clean.select_nonoverlap(generated, filter_spec)
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
        for trade in raw
        if trade.exit_ts < REUSED_END
    ]
    return {
        "generated_signals": len(generated),
        "filtered_trades": len(trades),
        "metrics": window_metrics(trades, symbol),
    }


def robust_score(scenarios: dict[str, Any]) -> float:
    value = score(scenarios["base_4bps_k1"]["metrics"])
    for name in ("stress_8bps_k1", "base_4bps_k2"):
        metrics = scenarios[name]["metrics"]
        prefit = metrics["prefit"]
        current = metrics["current_diagnostic"]
        value += 0.5 * math.log(max(prefit["annual_multiple"], 1e-9))
        value += prefit["win_rate"] + 2.0 * prefit["max_dd"]
        value += 25.0 * min(0.0, current["total_return"])
        value += 14.0 * min(0.0, current["win_rate"] - 0.75)
        value += 15.0 * min(0.0, current["max_dd"] + 0.20)
    return float(value)


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
    base = clean.Config(**audit["config"])
    frame = load_symbol_frame(symbol, end=REUSED_END)
    funding = load_funding(symbol, end=REUSED_END)
    raw = frame[["ts", "open", "high", "low", "close", "volume"]]
    features = clean.evolution.add_rsi_features(clean.evolution.add_features(raw, []))
    market = clean.mii.build_market_arrays(features)
    funding_times, funding_prefix = funding_arrays(funding)
    configs = candidates(base)
    rows: list[dict[str, Any]] = []
    for config in configs:
        metric = evaluate(
            config,
            sleeve=sleeve,
            symbol=symbol,
            quality=float(audit["quality"]),
            exposure=float(audit["exposure"]),
            features=features,
            market=market,
            funding_times=funding_times,
            funding_prefix=funding_prefix,
            scenario="base_4bps_k1",
        )
        rows.append(
            {
                "config": asdict(config),
                "base_4bps_k1": metric,
                "selection_score": score(metric["metrics"]),
                "is_baseline": config == base,
            }
        )
    rows.sort(key=lambda row: row["selection_score"], reverse=True)
    baseline = next(row for row in rows if row["is_baseline"])
    shortlist = rows[:SHORTLIST]
    if baseline not in shortlist:
        shortlist.append(baseline)
    robust_rows: list[dict[str, Any]] = []
    for row in shortlist:
        config = clean.Config(**row["config"])
        scenarios = {"base_4bps_k1": row["base_4bps_k1"]}
        for scenario in ("stress_8bps_k1", "base_4bps_k2"):
            scenarios[scenario] = evaluate(
                config,
                sleeve=sleeve,
                symbol=symbol,
                quality=float(audit["quality"]),
                exposure=float(audit["exposure"]),
                features=features,
                market=market,
                funding_times=funding_times,
                funding_prefix=funding_prefix,
                scenario=scenario,
            )
        robust_rows.append(
            {**row, "scenarios": scenarios, "robust_score": robust_score(scenarios)}
        )
    robust_rows.sort(key=lambda row: row["robust_score"], reverse=True)
    preferred = robust_rows[0]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_clean_rsi_local_microtune_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "selection_policy": (
            "train/validation/prefit ranking; current diagnostic is veto/penalty; "
            "shortlist rerun at 8bps K+1 and 4bps K+2"
        ),
        "sleeve": sleeve,
        "generated_candidates": len(configs),
        "shortlist": len(robust_rows),
        "baseline": baseline,
        "preferred": preferred,
        "robust_ranking": robust_rows,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    scenarios = preferred["scenarios"]
    lines = [
        "# BIN-15M-AS6S V6 HYPE clean-RSI局部微调（2026-07-15）",
        "",
        "对RSI窗口/阈值、最低ATR、TP、SL和最长持仓做500个局部组合；当前三个月只作负收益、胜率和回撤惩罚，前25名复测8 bps及K+2。",
        "",
        f"- preferred是否变化：`{'是' if preferred['config'] != baseline['config'] else '否'}`",
        f"- base prefit：`{scenarios['base_4bps_k1']['metrics']['prefit']['annual_multiple']:.3f}x / {scenarios['base_4bps_k1']['metrics']['prefit']['win_rate']:.2%} / {scenarios['base_4bps_k1']['metrics']['prefit']['max_dd']:.2%}`",
        f"- base当前3m：`{scenarios['base_4bps_k1']['metrics']['current_diagnostic']['total_return']:+.2%} / {scenarios['base_4bps_k1']['metrics']['current_diagnostic']['win_rate']:.2%} / {scenarios['base_4bps_k1']['metrics']['current_diagnostic']['max_dd']:.2%}`",
        f"- 8bps当前3m：`{scenarios['stress_8bps_k1']['metrics']['current_diagnostic']['total_return']:+.2%}`",
        f"- K+2当前3m：`{scenarios['base_4bps_k2']['metrics']['current_diagnostic']['total_return']:+.2%}`",
        "",
        "该preferred仍须替换回联合账户比较资金占用与机会抢占，不单独promotion。",
        "",
        f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "generated_candidates": len(configs),
                "preferred_changed": preferred["config"] != baseline["config"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
