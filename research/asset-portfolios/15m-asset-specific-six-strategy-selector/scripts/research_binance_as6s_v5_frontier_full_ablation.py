from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from as6s_engine import (
    FEE_PER_FILL,
    PREFIT_END,
    REUSED_END,
    STARTS,
    StrategyConfig,
    adverse_fill,
    funding_arrays,
    funding_return,
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
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v5_frontier_full_ablation_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v5-frontier-full-ablation-2026-07-15.md"
SCENARIOS = {
    "base_4bps_k1": (0.0004, 1),
    "stress_8bps_k1": (0.0008, 1),
    "base_4bps_k2": (0.0004, 2),
}


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    changes: dict[str, Any]
    disabled: frozenset[str] = frozenset()
    live_promotable: bool = True


def build_signal(
    frame: pd.DataFrame,
    cfg: StrategyConfig,
    disabled: frozenset[str],
) -> tuple[np.ndarray, np.ndarray]:
    close = frame["close"]
    open_ = frame["open"]
    atr = frame["atr14"]
    adx = frame[f"adx_{cfg.adx_window}"]
    plus = frame[f"pdi_{cfg.adx_window}"]
    minus = frame[f"mdi_{cfg.adx_window}"]
    rvol = frame[f"rvol_{cfg.rvol_window}"]
    common = atr.notna()
    if "min_atr" not in disabled:
        common &= frame["atr_pct"] >= cfg.min_atr_pct
    if "max_atr" not in disabled:
        common &= frame["atr_pct"] <= cfg.max_atr_pct
    if "atr_ratio" not in disabled:
        common &= frame["atr_ratio"] <= cfg.max_atr_ratio
    if "adx_min" not in disabled and "adx_family" not in disabled:
        common &= adx >= cfg.adx_min
    if "rvol_min" not in disabled and "rvol_family" not in disabled:
        common &= rvol >= cfg.rvol_min

    if cfg.mechanism == "trend_state":
        fast = frame[f"ema_{cfg.ema_fast}"]
        slow = frame[f"ema_{cfg.ema_slow}"]
        distance = (close - fast) / atr.replace(0.0, np.nan)
        long_gate = pd.Series(True, index=frame.index)
        short_gate = pd.Series(True, index=frame.index)
        if "ema_order" not in disabled:
            long_gate &= fast > slow
            short_gate &= fast < slow
        if "di_direction" not in disabled and "adx_family" not in disabled:
            long_gate &= plus > minus
            short_gate &= minus > plus
        if "max_distance" not in disabled:
            long_gate &= distance.abs() <= cfg.max_dist_atr
            short_gate &= distance.abs() <= cfg.max_dist_atr
        if cfg.threshold_long >= 0.5 and "pullback" not in disabled:
            long_gate &= (frame["low"] <= fast) & (close > fast)
            short_gate &= (frame["high"] >= fast) & (close < fast)
        if cfg.threshold_long >= 1.0 and "momentum" not in disabled:
            long_gate &= close > close.shift(1)
            short_gate &= close < close.shift(1)
        if "edge_trigger" in disabled:
            long, short = long_gate, short_gate
        else:
            long = long_gate & ~long_gate.shift(1, fill_value=False)
            short = short_gate & ~short_gate.shift(1, fill_value=False)
        score = (
            0.35
            * ((fast - slow).abs() / atr.replace(0.0, np.nan) / 6.0).clip(0.0, 1.0)
            + (0.0 if "adx_family" in disabled else 0.30 * (adx / 45.0).clip(0.0, 1.0))
            + (0.0 if "rvol_family" in disabled else 0.20 * (rvol / 2.0).clip(0.0, 1.0))
            + (
                0.0
                if "max_distance" in disabled
                else 0.15
                * (
                    1.0
                    - (distance.abs() / max(cfg.max_dist_atr, 1.0)).clip(0.0, 1.0)
                )
            )
        )
    elif cfg.mechanism == "breakout":
        fast = frame[f"ema_{cfg.ema_fast}"]
        slow = frame[f"ema_{cfg.ema_slow}"]
        high = frame[f"don_high_{cfg.indicator_window}"]
        low = frame[f"don_low_{cfg.indicator_window}"]
        long = (close > high) & (close.shift(1) <= high.shift(1))
        short = (close < low) & (close.shift(1) >= low.shift(1))
        if "ema_order" not in disabled:
            long &= fast > slow
            short &= fast < slow
        if "di_direction" not in disabled and "adx_family" not in disabled:
            long &= plus > minus
            short &= minus > plus
        range_atr = (high - low) / atr.replace(0.0, np.nan)
        score = (
            (0.0 if "adx_family" in disabled else 0.35 * (adx / 45.0).clip(0.0, 1.0))
            + (0.0 if "rvol_family" in disabled else 0.30 * (rvol / 2.0).clip(0.0, 1.0))
            + 0.20 * (frame["body_atr"] / 1.5).clip(0.0, 1.0)
            + 0.15 * (range_atr / 12.0).clip(0.0, 1.0)
        )
    else:
        rsi = frame[f"rsi_{cfg.indicator_window}"]
        macd = frame[f"macd_{cfg.aux_fast}_{cfg.aux_slow}"]
        long = (rsi > cfg.threshold_long) & (rsi.shift(1) <= cfg.threshold_long)
        short = (rsi < cfg.threshold_short) & (rsi.shift(1) >= cfg.threshold_short)
        if "macd_direction" not in disabled:
            long &= macd > 0.0
            short &= macd < 0.0
        score = (
            0.40 * ((rsi - 50.0).abs() / 30.0).clip(0.0, 1.0)
            + 0.25 * (macd.abs() / atr.replace(0.0, np.nan) / 2.0).clip(0.0, 1.0)
            + (0.0 if "rvol_family" in disabled else 0.20 * (rvol / 2.0).clip(0.0, 1.0))
            + (0.0 if "adx_family" in disabled else 0.15 * (1.0 - (adx / 45.0).clip(0.0, 1.0)))
        )

    if cfg.require_h1 and "h1" not in disabled:
        h1_long = (frame["h1_ema_24"] > frame["h1_ema_96"]) & (
            frame["h1_pdi_21"] > frame["h1_mdi_21"]
        )
        h1_short = (frame["h1_ema_24"] < frame["h1_ema_96"]) & (
            frame["h1_mdi_21"] > frame["h1_pdi_21"]
        )
        if cfg.mechanism == "reversal":
            long &= ~((~h1_long) & (frame["h1_adx_21"] > 30.0))
            short &= ~((~h1_short) & (frame["h1_adx_21"] > 30.0))
        else:
            long &= h1_long
            short &= h1_short
    if cfg.require_body and "body" not in disabled:
        long &= close > open_
        short &= close < open_
    long &= common
    short &= common
    if cfg.side_mode == "long" and "side_mode" not in disabled:
        short &= False
    elif cfg.side_mode == "short" and "side_mode" not in disabled:
        long &= False
    conflict = long & short
    side = np.where(long & ~conflict, 1, np.where(short & ~conflict, -1, 0)).astype(
        np.int8
    )
    return side, np.asarray(score.fillna(0.0).clip(0.0, 1.0), dtype=np.float64)


def simulate(
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: StrategyConfig,
    disabled: frozenset[str],
    *,
    slippage: float,
    delay: int,
) -> list[dict[str, Any]]:
    sides, scores = build_signal(frame, cfg, disabled)
    funding_times, funding_prefix = funding_arrays(funding)
    open_ = frame["open"].to_numpy(dtype=np.float64)
    high = frame["high"].to_numpy(dtype=np.float64)
    low = frame["low"].to_numpy(dtype=np.float64)
    close = frame["close"].to_numpy(dtype=np.float64)
    atr = frame["atr14"].to_numpy(dtype=np.float64)
    slow = (
        frame[f"ema_{cfg.ema_slow}"].to_numpy(dtype=np.float64)
        if cfg.ema_slow
        else np.full(len(frame), np.nan)
    )
    ts = frame["ts"].tolist()
    output: list[dict[str, Any]] = []
    for signal_i in np.flatnonzero(sides):
        entry_i = int(signal_i + delay)
        if entry_i >= len(frame) or ts[entry_i] >= REUSED_END or not np.isfinite(atr[signal_i]):
            continue
        side = int(sides[signal_i])
        entry_fill = adverse_fill(open_[entry_i], side, entry=True, slippage=slippage)
        stop = entry_fill - side * cfg.sl_atr * atr[signal_i]
        target = (
            entry_fill + side * cfg.tp_atr * atr[signal_i]
            if cfg.tp_atr > 0.0
            else math.nan
        )
        exit_i = min(entry_i + cfg.max_hold_bars, len(frame) - 1)
        exit_base = open_[exit_i]
        reason = "time_open"
        high_water = entry_fill
        low_water = entry_fill
        trail_stop = math.nan
        for index in range(entry_i, min(entry_i + cfg.max_hold_bars, len(frame))):
            if side > 0:
                if open_[index] <= stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_stop"
                    break
                if np.isfinite(target) and open_[index] >= target:
                    exit_i, exit_base, reason = index, open_[index], "gap_target"
                    break
                if np.isfinite(trail_stop) and open_[index] <= trail_stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_trail"
                    break
                if low[index] <= stop:
                    exit_i, exit_base, reason = index, stop, "stop"
                    break
                if np.isfinite(trail_stop) and low[index] <= trail_stop:
                    exit_i, exit_base, reason = index, trail_stop, "trail"
                    break
                if np.isfinite(target) and high[index] >= target:
                    exit_i, exit_base, reason = index, target, "target"
                    break
            else:
                if open_[index] >= stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_stop"
                    break
                if np.isfinite(target) and open_[index] <= target:
                    exit_i, exit_base, reason = index, open_[index], "gap_target"
                    break
                if np.isfinite(trail_stop) and open_[index] >= trail_stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_trail"
                    break
                if high[index] >= stop:
                    exit_i, exit_base, reason = index, stop, "stop"
                    break
                if np.isfinite(trail_stop) and high[index] >= trail_stop:
                    exit_i, exit_base, reason = index, trail_stop, "trail"
                    break
                if np.isfinite(target) and low[index] <= target:
                    exit_i, exit_base, reason = index, target, "target"
                    break
            if (
                cfg.mechanism == "trend_state"
                and "trend_break" not in disabled
                and index > entry_i
            ):
                if (side > 0 and close[index - 1] < slow[index - 1]) or (
                    side < 0 and close[index - 1] > slow[index - 1]
                ):
                    exit_i, exit_base, reason = index, open_[index], "trend_break_open"
                    break
            high_water = max(high_water, high[index])
            low_water = min(low_water, low[index])
            if (
                cfg.mechanism == "trend_state"
                and cfg.trail_activate_atr > 0.0
                and "trail" not in disabled
            ):
                mfe = (
                    side
                    * ((high_water if side > 0 else low_water) - entry_fill)
                    / atr[signal_i]
                )
                if mfe >= cfg.trail_activate_atr:
                    candidate = (
                        high_water - cfg.trail_atr * atr[signal_i]
                        if side > 0
                        else low_water + cfg.trail_atr * atr[signal_i]
                    )
                    if not np.isfinite(trail_stop):
                        trail_stop = candidate
                    elif side > 0:
                        trail_stop = max(trail_stop, candidate)
                    else:
                        trail_stop = min(trail_stop, candidate)
        if exit_i >= len(frame) or ts[exit_i] >= REUSED_END:
            continue
        exit_fill = adverse_fill(exit_base, side, entry=False, slippage=slippage)
        price_return = float(side * (exit_fill / entry_fill - 1.0))
        funding_ret = funding_return(
            side,
            ts[entry_i],
            ts[exit_i],
            funding_times,
            funding_prefix,
        )
        fee_ret = -FEE_PER_FILL * (1.0 + exit_fill / entry_fill)
        if side > 0:
            mae_price = float(np.nanmin(low[entry_i : exit_i + 1] / entry_fill - 1.0))
        else:
            mae_price = float(np.nanmin(1.0 - high[entry_i : exit_i + 1] / entry_fill))
        output.append(
            {
                "side": side,
                "entry_ts": ts[entry_i],
                "exit_ts": ts[exit_i],
                "entry_fill": entry_fill,
                "score": float(scores[signal_i]),
                "net_return_1x": price_return + funding_ret + fee_ret,
                "mae_return_1x": min(mae_price + fee_ret, price_return + funding_ret + fee_ret),
                "exit_reason": reason,
            }
        )
    return output


def variants(cfg: StrategyConfig) -> list[Variant]:
    rows = [
        Variant("baseline", {}),
        Variant("remove_min_atr", {}, frozenset({"min_atr"})),
        Variant("remove_max_atr", {}, frozenset({"max_atr"})),
        Variant("remove_atr_ratio", {}, frozenset({"atr_ratio"})),
        Variant("remove_adx_min", {}, frozenset({"adx_min"})),
        Variant("remove_rvol_min", {}, frozenset({"rvol_min"})),
        Variant("remove_adx_family", {}, frozenset({"adx_family"})),
        Variant("remove_rvol_family", {}, frozenset({"rvol_family"})),
        Variant("remove_h1", {}, frozenset({"h1"})),
        Variant("remove_body", {}, frozenset({"body"})),
        Variant("remove_side_restriction", {}, frozenset({"side_mode"})),
        Variant("remove_tp", {"tp_atr": 0.0}),
        Variant("remove_stop_diagnostic", {"sl_atr": 1_000_000.0}, live_promotable=False),
        Variant(
            "remove_max_hold_diagnostic",
            {"max_hold_bars": 100_000},
            live_promotable=False,
        ),
    ]
    if cfg.mechanism in {"trend_state", "breakout"}:
        rows.extend(
            [
                Variant("remove_ema_order", {}, frozenset({"ema_order"})),
                Variant("remove_di_direction", {}, frozenset({"di_direction"})),
            ]
        )
    if cfg.mechanism == "trend_state":
        rows.extend(
            [
                Variant("remove_max_distance", {}, frozenset({"max_distance"})),
                Variant("remove_pullback", {}, frozenset({"pullback"})),
                Variant("remove_momentum", {}, frozenset({"momentum"})),
                Variant("remove_edge_trigger", {}, frozenset({"edge_trigger"})),
                Variant("remove_trend_break", {}, frozenset({"trend_break"})),
                Variant("remove_trail", {}, frozenset({"trail"})),
            ]
        )
    elif cfg.mechanism == "reversal":
        rows.append(Variant("remove_macd_direction", {}, frozenset({"macd_direction"})))
    return rows


def unified(
    sleeve: str,
    audit: dict[str, Any],
    mechanism: str,
    rows: list[dict[str, Any]],
) -> list[UnifiedTrade]:
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    return [
        UnifiedTrade(
            sleeve=sleeve,
            symbol=audit["symbol"],
            mechanism=mechanism,
            source_timeframe="15m",
            side=row["side"],
            entry_ts=row["entry_ts"],
            exit_ts=row["exit_ts"],
            entry_price=row["entry_fill"],
            net_return_1x=row["net_return_1x"],
            mae_return_1x=row["mae_return_1x"],
            raw_strength=row["score"],
            strength=float(0.75 * quality + 0.25 * np.clip(row["score"], 0.0, 1.0)),
            exposure=exposure,
            exit_reason=row["exit_reason"],
        )
        for row in rows
    ]


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
            round(row.raw_strength, 12),
            row.exit_reason,
        )
        for row in rows
    ]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    frames: dict[str, pd.DataFrame] = {}
    funding: dict[str, pd.DataFrame] = {}
    for sleeve in manifest["selected_sleeves"]:
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] != "prefit_frontier_asset_first":
            continue
        symbol = audit["symbol"]
        if symbol not in frames:
            frames[symbol] = load_symbol_frame(symbol, end=REUSED_END)
            funding[symbol] = load_funding(symbol, end=REUSED_END)
            if frames[symbol]["ts"].max() >= REUSED_END:
                raise RuntimeError(f"{symbol} bars crossed cutoff")
            if funding[symbol]["ts"].max() >= REUSED_END:
                raise RuntimeError(f"{symbol} funding crossed cutoff")
        baseline_cfg = StrategyConfig.from_dict(audit["config"])
        sleeve_rows: dict[str, Any] = {}
        baseline_paths: dict[str, list[tuple[Any, ...]]] = {}
        for variant in variants(baseline_cfg):
            cfg = replace(baseline_cfg, **variant.changes)
            scenario_rows: dict[str, Any] = {}
            for scenario, (slippage, delay) in SCENARIOS.items():
                raw = simulate(
                    frames[symbol],
                    funding[symbol],
                    cfg,
                    variant.disabled,
                    slippage=slippage,
                    delay=delay,
                )
                trades = unified(sleeve, audit, cfg.mechanism, raw)
                selected = nonpreemptive(
                    trades,
                    start=STARTS[symbol],
                    end=REUSED_END,
                )
                key = path_key(selected)
                if variant.name == "baseline":
                    baseline_paths[scenario] = key
                scenario_rows[scenario] = {
                    "generated_opportunities": len(trades),
                    "selected_trades": len(selected),
                    "exact_path_equal_to_baseline": key == baseline_paths.get(scenario, []),
                    "metrics": metrics_by_window(trades, symbol),
                }
            sleeve_rows[variant.name] = {
                "changes": variant.changes,
                "disabled_components": sorted(variant.disabled),
                "live_promotable": variant.live_promotable,
                "scenarios": scenario_rows,
            }
        results[sleeve] = {
            "symbol": symbol,
            "mechanism": baseline_cfg.mechanism,
            "baseline_config": asdict(baseline_cfg),
            "structural_not_removed": {
                "signal_event": (
                    "Donchian crossing"
                    if baseline_cfg.mechanism == "breakout"
                    else "RSI crossing"
                    if baseline_cfg.mechanism == "reversal"
                    else "trend-state event"
                ),
                "window_parameters": (
                    "窗口删除会使机制不存在；放入clean-surface微调，不伪装成有意义的零交易消融"
                ),
            },
            "variants": sleeve_rows,
        }

    exact_noops = [
        (sleeve, variant)
        for sleeve, row in results.items()
        for variant, values in row["variants"].items()
        if variant != "baseline"
        and all(
            scenario["exact_path_equal_to_baseline"]
            for scenario in values["scenarios"].values()
        )
    ]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v5_frontier_eight_sleeve_full_component_ablation",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "scenarios": SCENARIOS,
        "sleeves": len(results),
        "variant_evaluations": sum(len(row["variants"]) for row in results.values()),
        "exact_noop_variants": [
            {"sleeve": sleeve, "variant": variant} for sleeve, variant in exact_noops
        ],
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V5 八条frontier腿全组件消融（2026-07-15）",
        "",
        "严格使用 `ts < 2026-07-14T09:00Z`；未读取未来OOS，未修改V5。每个变体均计算4bps/K+1、8bps/K+1、4bps/K+2及prefit/reused diagnostic/through-cutoff。",
        "",
        f"- 腿：`{len(results)}`",
        f"- 含基线的变体评估：`{payload['variant_evaluations']}`",
        f"- 三场景精确无变化的有效条件移除：`{len(exact_noops)}`",
        "- `remove_stop_diagnostic` 与 `remove_max_hold_diagnostic` 只用于解释参数作用，明确不可promotion。",
        "",
        "## 逐腿变体数",
        "",
        "| 腿 | 机制 | 变体数 | 精确无变化变体数 |",
        "|---|---|---:|---:|",
    ]
    for sleeve, row in results.items():
        noops = sum(
            name != "baseline"
            and all(
                scenario["exact_path_equal_to_baseline"]
                for scenario in values["scenarios"].values()
            )
            for name, values in row["variants"].items()
        )
        lines.append(
            f"| `{sleeve}` | `{row['mechanism']}` | {len(row['variants'])} | {noops} |"
        )
    lines.extend(
        [
            "",
            "本文件先保留完整事实，不在消融运行脚本里按单一标量自动删参数；clean接口决策还要结合账户替换边际，避免单腿看似改善却抢走更优交易。",
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
                "variant_evaluations": payload["variant_evaluations"],
                "exact_noop_variants": len(exact_noops),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
