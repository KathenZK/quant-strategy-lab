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
from research_hype_v14_main_backfill import v14_spec


REPORT_PATH = Path("reports/hype_v14_atr_dynamic_entry.json")
RANKING_PATH = Path("reports/hype_v14_atr_dynamic_entry_ranking.csv")
MISS_PATH = Path("reports/hype_v14_atr_dynamic_entry_missed_regimes.csv")
FAILURE_PATH = Path("reports/hype_v14_atr_dynamic_entry_signal_failures.csv")


@dataclass(frozen=True, slots=True)
class TierThreshold:
    long_adx: float
    long_vol: float
    short_adx: float
    short_vol: float
    h1_long_adx: float = 18.0


@dataclass(frozen=True, slots=True)
class DynamicEntrySpec:
    name: str
    low: TierThreshold
    mid: TierThreshold
    high: TierThreshold
    low_cut: float = 0.85
    high_cut: float = 1.20
    require_h1: bool = True


BASE = TierThreshold(long_adx=28.0, long_vol=0.25, short_adx=36.0, short_vol=0.50)


def build_entry_specs() -> list[DynamicEntrySpec]:
    return [
        DynamicEntrySpec("V14_fixed_v6_entry", BASE, BASE, BASE),
        DynamicEntrySpec(
            "ATR_high_relax_vol",
            low=TierThreshold(30.0, 0.45, 38.0, 0.70),
            mid=BASE,
            high=TierThreshold(28.0, 0.00, 36.0, 0.15),
        ),
        DynamicEntrySpec(
            "ATR_high_relax_adx",
            low=TierThreshold(30.0, 0.35, 38.0, 0.60),
            mid=BASE,
            high=TierThreshold(24.0, 0.25, 30.0, 0.50),
        ),
        DynamicEntrySpec(
            "ATR_high_relax_both",
            low=TierThreshold(32.0, 0.50, 40.0, 0.75),
            mid=BASE,
            high=TierThreshold(24.0, 0.00, 30.0, 0.15),
        ),
        DynamicEntrySpec(
            "ATR_high_relax_both_h1",
            low=TierThreshold(32.0, 0.50, 40.0, 0.75),
            mid=BASE,
            high=TierThreshold(24.0, 0.00, 30.0, 0.15, h1_long_adx=14.0),
        ),
        DynamicEntrySpec(
            "ATR_low_breakout_relax",
            low=TierThreshold(24.0, 0.00, 30.0, 0.15),
            mid=BASE,
            high=BASE,
        ),
        DynamicEntrySpec(
            "ATR_low_and_high_relax",
            low=TierThreshold(24.0, 0.00, 30.0, 0.15),
            mid=BASE,
            high=TierThreshold(24.0, 0.00, 30.0, 0.15),
        ),
        DynamicEntrySpec(
            "ATR_gradual_relax",
            low=TierThreshold(30.0, 0.45, 38.0, 0.70),
            mid=TierThreshold(26.0, 0.15, 34.0, 0.35),
            high=TierThreshold(24.0, 0.00, 30.0, 0.15),
        ),
        DynamicEntrySpec(
            "ATR_high_only_loose_cut",
            low=BASE,
            mid=BASE,
            high=TierThreshold(24.0, 0.00, 30.0, 0.15),
            high_cut=1.05,
        ),
        DynamicEntrySpec(
            "ATR_high_only_strict_cut",
            low=BASE,
            mid=BASE,
            high=TierThreshold(24.0, 0.00, 30.0, 0.15),
            high_cut=1.35,
        ),
    ]


def dynamic_entry_signal(frame: pd.DataFrame, spec: DynamicEntrySpec) -> np.ndarray:
    spread = frame.ema_spread.to_numpy("float64")
    regime_long = spread > 0.0
    regime_short = spread < 0.0
    atr_ratio = frame.atr_ratio96_672.replace([np.inf, -np.inf], np.nan).fillna(1.0).to_numpy("float64")
    low_mask = atr_ratio <= spec.low_cut
    high_mask = atr_ratio >= spec.high_cut
    mid_mask = ~(low_mask | high_mask)

    signal = np.zeros(len(frame), dtype=np.int8)
    adx28 = frame.adx28.to_numpy("float64")
    vol = frame.vol_surge192.to_numpy("float64")
    h1_adx = frame.h1_adx21.to_numpy("float64")
    h1_pdi = frame.h1_pdi21.to_numpy("float64")
    h1_mdi = frame.h1_mdi21.to_numpy("float64")
    h1_spread = frame.h1_ema_spread.to_numpy("float64")

    def apply_tier(mask: np.ndarray, tier: TierThreshold) -> None:
        long_ok = regime_long & mask & (adx28 >= tier.long_adx) & (vol >= tier.long_vol)
        short_ok = regime_short & mask & (adx28 >= tier.short_adx) & (vol >= tier.short_vol)
        if spec.require_h1:
            long_ok &= (h1_adx > tier.h1_long_adx) & (h1_pdi > h1_mdi)
            short_ok &= h1_spread < 0
        signal[long_ok] = 1
        signal[short_ok] = -1

    apply_tier(low_mask, spec.low)
    apply_tier(mid_mask, spec.mid)
    apply_tier(high_mask, spec.high)
    return signal


def add_regime_id(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    sign = np.sign(result.ema_spread.to_numpy("float64"))
    sign[sign == 0] = np.nan
    sign_series = pd.Series(sign).ffill().fillna(0).astype(int).to_numpy()
    cross = np.r_[True, sign_series[1:] != sign_series[:-1]]
    result["regime_id"] = np.cumsum(cross)
    result["regime_direction"] = sign_series
    return result


def summarize_large_regimes(frame: pd.DataFrame, signals: dict[str, np.ndarray], start_ts: pd.Timestamp) -> pd.DataFrame:
    working = frame[pd.to_datetime(frame.ts, utc=True) >= start_ts].copy()
    rows: list[dict[str, Any]] = []
    for regime_id, group in working.groupby("regime_id"):
        direction = int(group.regime_direction.iloc[0])
        if direction == 0 or len(group) < 16:
            continue
        start_close = float(group.close.iloc[0])
        if direction > 0:
            potential = float(group.high.max() / start_close - 1)
        else:
            potential = float(1 - group.low.min() / start_close)
        if potential < 0.15:
            continue
        index = group.index.to_numpy()
        row: dict[str, Any] = {
            "regime_id": int(regime_id),
            "side": "long" if direction > 0 else "short",
            "start_ts": str(pd.Timestamp(group.ts.iloc[0])),
            "end_ts": str(pd.Timestamp(group.ts.iloc[-1])),
            "bars": int(len(group)),
            "potential_move": potential,
            "atr_ratio_median": float(group.atr_ratio96_672.median()),
            "atr_ratio_max": float(group.atr_ratio96_672.max()),
            "vol_surge_median": float(group.vol_surge192.median()),
            "adx28_median": float(group.adx28.median()),
        }
        for name, signal in signals.items():
            row[f"{name}_signal_bars"] = int(np.count_nonzero(signal[index] == direction))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("potential_move", ascending=False)


def signal_failure_summary(frame: pd.DataFrame, start_ts: pd.Timestamp) -> pd.DataFrame:
    working = frame[pd.to_datetime(frame.ts, utc=True) >= start_ts].copy()
    rows = []
    for regime_id, group in working.groupby("regime_id"):
        direction = int(group.regime_direction.iloc[0])
        if direction == 0:
            continue
        start_close = float(group.close.iloc[0])
        potential = float(group.high.max() / start_close - 1) if direction > 0 else float(1 - group.low.min() / start_close)
        if potential < 0.15:
            continue
        if direction > 0:
            adx_ok = group.adx28 >= 28
            vol_ok = group.vol_surge192 >= 0.25
            h1_ok = (group.h1_adx21 > 18) & (group.h1_pdi21 > group.h1_mdi21)
        else:
            adx_ok = group.adx28 >= 36
            vol_ok = group.vol_surge192 >= 0.50
            h1_ok = group.h1_ema_spread < 0
        rows.append(
            {
                "regime_id": int(regime_id),
                "side": "long" if direction > 0 else "short",
                "potential_move": potential,
                "bars": int(len(group)),
                "atr_ratio_median": float(group.atr_ratio96_672.median()),
                "adx_ok_rate": float(adx_ok.mean()),
                "vol_ok_rate": float(vol_ok.mean()),
                "h1_ok_rate": float(h1_ok.mean()),
                "all_ok_rate": float((adx_ok & vol_ok & h1_ok).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("potential_move", ascending=False)


def compact_metric(result: dict[str, Any], signal_count: int, large_regime_covered: int) -> dict[str, Any]:
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
        "large_regime_covered": large_regime_covered,
        "exit_reasons": result["exit_reasons"],
    }


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_regime_id(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    v14 = v14_spec()
    entry_specs = build_entry_specs()
    signals = {"base": entry_signal(frame, v6_variant())}
    for spec in entry_specs[1:]:
        signals[spec.name] = dynamic_entry_signal(frame, spec)

    regime_summary = summarize_large_regimes(frame, signals, start_ts)
    failure_summary = signal_failure_summary(frame, start_ts)

    results = []
    for spec in entry_specs:
        signal = signals["base"] if spec.name == "V14_fixed_v6_entry" else signals[spec.name]
        result = run_late_reentry(
            frame,
            v14,
            start_ts=start_ts,
            collect_trades=False,
            signal_override=signal,
        )
        result["name"] = spec.name
        signal_count = int(np.count_nonzero(signal[pd.to_datetime(frame.ts, utc=True) >= start_ts]))
        signal_col = "base_signal_bars" if spec.name == "V14_fixed_v6_entry" else f"{spec.name}_signal_bars"
        large_regime_covered = int((regime_summary[signal_col] > 0).sum())
        results.append(compact_metric(result, signal_count, large_regime_covered))

    ranking = pd.DataFrame(results).sort_values(["return", "max_dd"], ascending=[False, False])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    regime_summary.to_csv(MISS_PATH, index=False)
    failure_summary.to_csv(FAILURE_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "start": str(start_ts),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                },
                "entry_specs": [asdict(spec) for spec in entry_specs],
                "ranking": ranking.to_dict(orient="records"),
                "large_regime_summary": regime_summary.to_dict(orient="records"),
                "signal_failure_summary": failure_summary.to_dict(orient="records"),
                "notes": [
                    "Dynamic entries only replace the base V6 entry signal. V14 filters and late re-entry rules remain unchanged.",
                    "ATR regime uses atr_ratio96_672: low <= low_cut, high >= high_cut, mid otherwise.",
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
    print("\\nlarge regime signal coverage")
    coverage_cols = ["regime_id", "side", "potential_move", "atr_ratio_median", "vol_surge_median", "adx28_median", "base_signal_bars"]
    print(regime_summary[coverage_cols].head(20).to_string(index=False))
    print("\\nfailure summary")
    print(failure_summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
