from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import entry_signal
from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_ema_volume_overlay_v8 import v6_variant
from research_hype_state_machine_v12 import add_structure_features
from research_hype_v13_late_reentry import run_late_reentry
from research_hype_v14_atr_dynamic_entry import add_regime_id, summarize_large_regimes
from research_hype_v14_main_backfill import v14_spec


REPORT_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v14_slow_trend_entry.json")
RANKING_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v14_slow_trend_entry_ranking.csv")
REGIME_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v14_slow_trend_entry_regimes.csv")
TRADE_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v14_slow_trend_entry_best_trades.csv")


@dataclass(frozen=True, slots=True)
class SlowTrendSpec:
    name: str
    mode: str
    adx_min: float
    max_dist_ema96: float
    h1_required: bool = True
    adx_rising: bool = True
    ema384_slope_required: bool = False
    vol_floor: float = -1.0
    slow_allocation_scale: float = 1.0


def build_specs() -> list[SlowTrendSpec]:
    return [
        SlowTrendSpec("V14_fixed", "none", 999.0, 0.0),
        SlowTrendSpec("slow_slope_adx16_h1", "slope", 16.0, 0.08),
        SlowTrendSpec("slow_slope_adx14_h1", "slope", 14.0, 0.08),
        SlowTrendSpec("slow_slope_adx14_noh1", "slope", 14.0, 0.08, h1_required=False),
        SlowTrendSpec("slow_slope_adx16_dist06", "slope", 16.0, 0.06),
        SlowTrendSpec("slow_slope_adx16_ema384", "slope", 16.0, 0.08, ema384_slope_required=True),
        SlowTrendSpec("slow_pullback_adx14_h1", "pullback", 14.0, 0.08),
        SlowTrendSpec("slow_pullback_adx16_h1", "pullback", 16.0, 0.08),
        SlowTrendSpec("slow_breakout48_adx14_h1", "breakout48", 14.0, 0.10),
        SlowTrendSpec("slow_breakout96_adx14_h1", "breakout96", 14.0, 0.10),
        SlowTrendSpec("slow_combo_adx16_h1", "combo", 16.0, 0.08),
        SlowTrendSpec("slow_combo_adx18_h1", "combo", 18.0, 0.08),
        SlowTrendSpec("slow_combo_adx16_volfloor", "combo", 16.0, 0.08, vol_floor=-0.25),
        SlowTrendSpec("scout_pullback_adx16_h1_035x", "pullback", 16.0, 0.08, slow_allocation_scale=0.35),
        SlowTrendSpec("scout_breakout96_adx14_h1_035x", "breakout96", 14.0, 0.10, slow_allocation_scale=0.35),
        SlowTrendSpec("scout_combo_adx16_h1_035x", "combo", 16.0, 0.08, slow_allocation_scale=0.35),
        SlowTrendSpec("scout_pullback_adx16_h1_050x", "pullback", 16.0, 0.08, slow_allocation_scale=0.50),
        SlowTrendSpec("scout_combo_adx16_volfloor_035x", "combo", 16.0, 0.08, vol_floor=-0.25, slow_allocation_scale=0.35),
    ]


def dist_to_ema96(frame: pd.DataFrame, direction: np.ndarray) -> np.ndarray:
    ema96 = frame.ema96.replace(0.0, np.nan).to_numpy("float64")
    close = frame.close.to_numpy("float64")
    return direction * (close / ema96 - 1)


def slow_signal(frame: pd.DataFrame, spec: SlowTrendSpec) -> np.ndarray:
    if spec.mode == "none":
        return np.zeros(len(frame), dtype=np.int8)

    spread = frame.ema_spread.to_numpy("float64")
    direction = np.where(spread > 0, 1, np.where(spread < 0, -1, 0)).astype(np.int8)
    dist = dist_to_ema96(frame, direction.astype(float))
    right_side = dist >= -0.01
    near_ema = dist <= spec.max_dist_ema96
    slope48 = direction * frame.ema96_slope48.to_numpy("float64") > 0
    slope384 = direction * frame.ema384_slope96.to_numpy("float64") > 0
    adx = frame.adx28.to_numpy("float64")
    adx_ok = adx >= spec.adx_min
    adx_rising = pd.Series(adx).diff(16).fillna(0.0).to_numpy("float64") >= 0 if spec.adx_rising else np.ones(len(frame), dtype=bool)
    vol_ok = frame.vol_surge192.to_numpy("float64") >= spec.vol_floor
    h1_long = (frame.h1_ema_spread.to_numpy("float64") > 0) & (
        frame.h1_pdi21.to_numpy("float64") > frame.h1_mdi21.to_numpy("float64")
    )
    h1_short = frame.h1_ema_spread.to_numpy("float64") < 0
    h1_ok = np.where(direction > 0, h1_long, h1_short) if spec.h1_required else np.ones(len(frame), dtype=bool)
    base_ok = (
        (direction != 0)
        & right_side
        & near_ema
        & slope48
        & adx_ok
        & adx_rising
        & h1_ok
        & vol_ok
    )
    if spec.ema384_slope_required:
        base_ok &= slope384

    close = frame.close.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    ema96 = frame.ema96.to_numpy("float64")
    touched_ema = np.where(
        direction > 0,
        pd.Series(low <= ema96 * 1.01).rolling(16, min_periods=1).max().to_numpy(dtype=bool),
        pd.Series(high >= ema96 * 0.99).rolling(16, min_periods=1).max().to_numpy(dtype=bool),
    )
    reclaimed = np.where(direction > 0, close > ema96, close < ema96)
    high48 = frame.high.rolling(48, min_periods=48).max().shift(1).to_numpy("float64")
    low48 = frame.low.rolling(48, min_periods=48).min().shift(1).to_numpy("float64")
    high96 = frame.high.rolling(96, min_periods=96).max().shift(1).to_numpy("float64")
    low96 = frame.low.rolling(96, min_periods=96).min().shift(1).to_numpy("float64")
    breakout48 = np.where(direction > 0, close >= high48, close <= low48)
    breakout96 = np.where(direction > 0, close >= high96, close <= low96)
    pullback = touched_ema & reclaimed

    if spec.mode == "slope":
        trigger = base_ok
    elif spec.mode == "pullback":
        trigger = base_ok & pullback
    elif spec.mode == "breakout48":
        trigger = base_ok & breakout48
    elif spec.mode == "breakout96":
        trigger = base_ok & breakout96
    elif spec.mode == "combo":
        trigger = base_ok & (pullback | breakout48)
    else:
        raise ValueError(f"unknown slow mode: {spec.mode}")

    signal = np.zeros(len(frame), dtype=np.int8)
    signal[trigger & (direction > 0)] = 1
    signal[trigger & (direction < 0)] = -1
    return signal


def compact_metric(result: dict[str, Any], signal_count: int, slow_count: int, large_regime_covered: int) -> dict[str, Any]:
    return {
        "name": result["name"],
        "return": result["return"],
        "max_dd": result["max_dd"],
        "sharpe": result["sharpe"],
        "trades": result["trades"],
        "late_trades": result["late_trades"],
        "win_rate": result["win_rate"],
        "avg_trade_pct": result["avg_trade_pct"],
        "median_trade_pct": result["median_trade_pct"],
        "worst_trade_pct": result["worst_trade_pct"],
        "signal_count": signal_count,
        "slow_signal_count": slow_count,
        "large_regime_covered": large_regime_covered,
        "exit_reasons": result["exit_reasons"],
    }


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_regime_id(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    base_signal = entry_signal(frame, v6_variant())
    mask_1y = pd.to_datetime(frame.ts, utc=True) >= start_ts
    v14 = v14_spec()

    specs = build_specs()
    signals: dict[str, np.ndarray] = {"base": base_signal}
    slow_signals: dict[str, np.ndarray] = {}
    for spec in specs[1:]:
        slow = slow_signal(frame, spec)
        slow_signals[spec.name] = slow
        combined = base_signal.copy()
        slow_only = (combined == 0) & (slow != 0)
        combined[slow_only] = slow[slow_only]
        signals[spec.name] = combined

    regime_summary = summarize_large_regimes(frame, signals, start_ts)
    rows = []
    results = []
    for spec in specs:
        signal = base_signal if spec.name == "V14_fixed" else signals[spec.name]
        signal_kind = np.full(len(frame), "", dtype=object)
        if spec.name != "V14_fixed":
            signal_kind[(base_signal == 0) & (slow_signals[spec.name] != 0)] = "slow"
        result = run_late_reentry(
            frame,
            v14,
            start_ts=start_ts,
            collect_trades=True,
            signal_override=signal,
            signal_kind_override=signal_kind,
            entry_allocation_scale={"slow": spec.slow_allocation_scale},
        )
        result["name"] = spec.name
        signal_col = "base_signal_bars" if spec.name == "V14_fixed" else f"{spec.name}_signal_bars"
        slow_count = 0 if spec.name == "V14_fixed" else int(np.count_nonzero(slow_signals[spec.name][mask_1y]))
        rows.append(
            compact_metric(
                result,
                int(np.count_nonzero(signal[mask_1y])),
                slow_count,
                int((regime_summary[signal_col] > 0).sum()),
            )
        )
        results.append(result)

    ranking = pd.DataFrame(rows).sort_values(["return", "max_dd"], ascending=[False, False])
    best_name = str(ranking.iloc[0]["name"])
    best = next(result for result in results if result["name"] == best_name)
    trades = pd.DataFrame(best["trades_detail"])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    regime_summary.to_csv(REGIME_PATH, index=False)
    trades.to_csv(TRADE_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "start": str(start_ts),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                },
                "specs": [asdict(spec) for spec in specs],
                "ranking": ranking.to_dict(orient="records"),
                "best": ranking.iloc[0].to_dict(),
                "large_regime_summary": regime_summary.to_dict(orient="records"),
                "notes": [
                    "Slow trend signals are added to the base V14 signal; V14 entry filters and late re-entry rules remain unchanged.",
                    "Signals target EMA96 slope trends that may have weak volume or ADX absolute values.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(ranking.to_string(index=False))
    print("\\nlarge regime coverage")
    print(regime_summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
