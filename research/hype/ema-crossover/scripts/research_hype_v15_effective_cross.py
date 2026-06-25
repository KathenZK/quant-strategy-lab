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
from research_hype_state_machine_v12 import V12Spec, add_structure_features
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_v13_late_reentry import LateReentrySpec, run_late_reentry
from research_hype_v14_atr_dynamic_entry import add_regime_id, summarize_large_regimes
from research_hype_v14_main_backfill import v14_spec


REPORT_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v15_effective_cross.json")
CROSS_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v15_effective_cross_events.csv")
RULE_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v15_effective_cross_rule_stats.csv")
RANKING_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v15_effective_cross_ranking.csv")
REGIME_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v15_effective_cross_regimes.csv")


@dataclass(frozen=True, slots=True)
class CrossGateSpec:
    name: str
    prefilter: str
    confirm: str
    entry_max_age: int
    confirm_window: int = 128
    gate_window: int = 256
    direct_confirm_signal: bool = True


def make_late_spec(name: str, entry_max_age: int) -> LateReentrySpec:
    v12 = focused_spec(
        f"{name}_base",
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=entry_max_age,
        entry_max_dist_ema96=0.08,
    )
    return LateReentrySpec(
        name,
        v12,
        late_max_age=256,
        late_dist_ema96=0.06,
        cooldown_bars=16,
        min_prev_pnl=0.0,
        min_prev_mfe_atr=4.0,
    )


def build_gate_specs() -> list[CrossGateSpec]:
    specs = [CrossGateSpec("V14_fixed", "none", "base", 128)]
    for age in (128, 192, 256):
        specs.extend(
            [
                CrossGateSpec(f"cross_slope_h1_age{age}", "slope_h1", "base", age),
                CrossGateSpec(f"cross_strict_age{age}", "strict", "base", age),
                CrossGateSpec(f"confirm_breakout48_age{age}", "slope_h1", "breakout48", age),
                CrossGateSpec(f"confirm_breakout96_age{age}", "slope_h1", "breakout96", age),
                CrossGateSpec(f"confirm_pullback_age{age}", "slope_h1", "pullback", age),
                CrossGateSpec(f"confirm_either_age{age}", "slope_h1", "either", age),
                CrossGateSpec(f"confirm_either_strict_age{age}", "strict", "either", age),
            ]
        )
    return specs


def cross_events(frame: pd.DataFrame, start_ts: pd.Timestamp, horizon: int = 384) -> pd.DataFrame:
    ts = pd.to_datetime(frame.ts, utc=True)
    spread = frame.ema_spread.to_numpy("float64")
    sign = np.sign(spread)
    prev = np.r_[np.nan, sign[:-1]]
    cross_idx = np.flatnonzero(((sign > 0) & (prev <= 0)) | ((sign < 0) & (prev >= 0)))
    rows = []
    for i in cross_idx:
        if ts.iloc[i] < start_ts or i + 4 >= len(frame):
            continue
        direction = 1 if sign[i] > 0 else -1
        end = min(len(frame), i + horizon)
        entry = float(frame.close.iloc[i])
        atr = float(frame.atr_pct672.iloc[i])
        if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        future = frame.iloc[i:end]
        if direction > 0:
            mfe = float(future.high.max() / entry - 1)
            mae = float(1 - future.low.min() / entry)
        else:
            mfe = float(1 - future.low.min() / entry)
            mae = float(future.high.max() / entry - 1)
        recent_sign = sign[max(0, i - 192) : i + 1]
        churn = int(np.count_nonzero(recent_sign[1:] != recent_sign[:-1]))
        h1_same = (
            (direction > 0 and frame.h1_ema_spread.iloc[i] > 0 and frame.h1_pdi21.iloc[i] > frame.h1_mdi21.iloc[i])
            or (direction < 0 and frame.h1_ema_spread.iloc[i] < 0)
        )
        rows.append(
            {
                "cross_i": int(i),
                "ts": str(ts.iloc[i]),
                "side": "long" if direction > 0 else "short",
                "direction": direction,
                "mfe": mfe,
                "mae": mae,
                "mfe_atr": mfe / atr,
                "mae_atr": mae / atr,
                "effective": bool((mfe / atr >= 6.0) and (mae / atr <= 3.5)),
                "big_trend": bool(mfe >= 0.15),
                "ema96_slope48_same": bool(direction * float(frame.ema96_slope48.iloc[i]) > 0),
                "ema384_slope96_same": bool(direction * float(frame.ema384_slope96.iloc[i]) >= 0),
                "h1_same": bool(h1_same),
                "adx28": float(frame.adx28.iloc[i]),
                "adx_slope16": float(frame.adx28.iloc[i] - frame.adx28.iloc[max(0, i - 16)]),
                "vol_surge192": float(frame.vol_surge192.iloc[i]),
                "atr_ratio96_672": float(frame.atr_ratio96_672.iloc[i]),
                "churn192": churn,
                "dist_ema96": float(direction * (frame.close.iloc[i] / frame.ema96.iloc[i] - 1)),
            }
        )
    return pd.DataFrame(rows)


def rule_mask(crosses: pd.DataFrame, rule: str) -> pd.Series:
    if rule == "none":
        return pd.Series(True, index=crosses.index)
    if rule == "slope_h1":
        return crosses.ema96_slope48_same & crosses.h1_same & (crosses.churn192 <= 4) & (crosses.dist_ema96 <= 0.10)
    if rule == "strict":
        return (
            crosses.ema96_slope48_same
            & crosses.ema384_slope96_same
            & crosses.h1_same
            & (crosses.churn192 <= 3)
            & (crosses.atr_ratio96_672 <= 1.8)
            & (crosses.dist_ema96 <= 0.08)
            & (crosses.adx_slope16 >= -4)
        )
    raise ValueError(f"unknown rule: {rule}")


def rule_stats(crosses: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rule in ("none", "slope_h1", "strict"):
        mask = rule_mask(crosses, rule)
        subset = crosses[mask]
        rows.append(
            {
                "rule": rule,
                "crosses": int(len(subset)),
                "effective_rate": float(subset.effective.mean()) if len(subset) else 0.0,
                "big_trend_rate": float(subset.big_trend.mean()) if len(subset) else 0.0,
                "avg_mfe_atr": float(subset.mfe_atr.mean()) if len(subset) else 0.0,
                "avg_mae_atr": float(subset.mae_atr.mean()) if len(subset) else 0.0,
                "median_churn192": float(subset.churn192.median()) if len(subset) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def gated_signal(frame: pd.DataFrame, crosses: pd.DataFrame, spec: CrossGateSpec, base_signal: np.ndarray) -> np.ndarray:
    if spec.name == "V14_fixed":
        return base_signal.copy()
    signal = np.zeros(len(frame), dtype=np.int8)
    close = frame.close.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    ema96 = frame.ema96.to_numpy("float64")
    allowed_crosses = crosses[rule_mask(crosses, spec.prefilter)]
    for cross in allowed_crosses.itertuples():
        i = int(cross.cross_i)
        direction = int(cross.direction)
        max_i = min(len(frame) - 1, i + spec.gate_window)
        confirmed_i: int | None = i if spec.confirm == "base" else None
        if spec.confirm != "base":
            for j in range(i + 1, min(len(frame), i + spec.confirm_window)):
                high48 = float(frame.high.iloc[max(0, j - 48) : j].max())
                low48 = float(frame.low.iloc[max(0, j - 48) : j].min())
                high96 = float(frame.high.iloc[max(0, j - 96) : j].max())
                low96 = float(frame.low.iloc[max(0, j - 96) : j].min())
                breakout48 = close[j] >= high48 if direction > 0 else close[j] <= low48
                breakout96 = close[j] >= high96 if direction > 0 else close[j] <= low96
                touched = low[max(i, j - 16) : j + 1].min() <= ema96[j] * 1.01 if direction > 0 else high[max(i, j - 16) : j + 1].max() >= ema96[j] * 0.99
                reclaim = close[j] > ema96[j] if direction > 0 else close[j] < ema96[j]
                pullback = bool(touched and reclaim)
                if (
                    (spec.confirm == "breakout48" and breakout48)
                    or (spec.confirm == "breakout96" and breakout96)
                    or (spec.confirm == "pullback" and pullback)
                    or (spec.confirm == "either" and (breakout48 or pullback))
                ):
                    confirmed_i = j
                    break
        if confirmed_i is None:
            continue
        end_i = min(max_i, confirmed_i + spec.gate_window)
        mask = np.arange(confirmed_i, end_i + 1)
        same_dir_base = base_signal[mask] == direction
        signal[mask[same_dir_base]] = direction
        if spec.direct_confirm_signal:
            signal[confirmed_i] = direction
    return signal


def compact_metric(result: dict[str, Any], signal_count: int, covered: int) -> dict[str, Any]:
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
        "large_regime_covered": covered,
        "exit_reasons": result["exit_reasons"],
    }


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_regime_id(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    crosses = cross_events(frame, start_ts)
    stats = rule_stats(crosses)
    base = entry_signal(frame, v6_variant())
    specs = build_gate_specs()
    signals = {spec.name: gated_signal(frame, crosses, spec, base) for spec in specs}
    regime_summary = summarize_large_regimes(frame, signals, start_ts)
    mask_1y = pd.to_datetime(frame.ts, utc=True) >= start_ts
    rows = []
    for spec in specs:
        strategy = v14_spec() if spec.name == "V14_fixed" else make_late_spec(spec.name, spec.entry_max_age)
        result = run_late_reentry(
            frame,
            strategy,
            start_ts=start_ts,
            collect_trades=False,
            signal_override=signals[spec.name],
        )
        result["name"] = spec.name
        signal_col = f"{spec.name}_signal_bars"
        rows.append(
            compact_metric(
                result,
                int(np.count_nonzero(signals[spec.name][mask_1y])),
                int((regime_summary[signal_col] > 0).sum()),
            )
        )
    ranking = pd.DataFrame(rows).sort_values(["return", "max_dd"], ascending=[False, False])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    crosses.to_csv(CROSS_PATH, index=False)
    stats.to_csv(RULE_PATH, index=False)
    ranking.to_csv(RANKING_PATH, index=False)
    regime_summary.to_csv(REGIME_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {"start": str(start_ts), "end": str(pd.Timestamp(frame.ts.iloc[-1]))},
                "gate_specs": [asdict(spec) for spec in specs],
                "cross_rule_stats": stats.to_dict(orient="records"),
                "ranking": ranking.to_dict(orient="records"),
                "large_regime_summary": regime_summary.to_dict(orient="records"),
                "notes": [
                    "Effective cross label: future 384-bar MFE >= 6 ATR and MAE <= 3.5 ATR.",
                    "Backtests use V14 exits and late re-entry rules; only base signal gating changes.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"crosses={CROSS_PATH}")
    print(f"ranking={RANKING_PATH}")
    print("\\ncross rule stats")
    print(stats.to_string(index=False))
    print("\\nranking")
    print(ranking.to_string(index=False))


if __name__ == "__main__":
    main()
