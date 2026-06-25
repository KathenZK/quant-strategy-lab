from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
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
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_v13_late_reentry import LateReentrySpec, run_late_reentry
from research_hype_v14_main_backfill import v14_spec


REPORT_PATH = Path("research/hype/ema-crossover/artifacts/hype_v17_trend_state_search.json")
RANKING_PATH = Path("research/hype/ema-crossover/artifacts/hype_v17_trend_state_search_ranking.csv")
CONSTRAINT_PATH = Path("research/hype/ema-crossover/artifacts/hype_v17_trend_state_search_constraints.csv")
TRADES_PATH = Path("research/hype/ema-crossover/artifacts/hype_v17_trend_state_search_top_trades.csv")

TARGET_RETURN = 50.0
TARGET_DD = -0.20
TARGET_WIN_RATE = 0.80


@dataclass(frozen=True, slots=True)
class SignalPlan:
    name: str
    base_filter: str
    add_signal: str = "none"
    add_min_age: int = 129
    add_max_age: int = 384
    add_dist: float = 0.065
    add_scale: float = 0.55


@dataclass(frozen=True, slots=True)
class EnginePlan:
    name: str
    late_max_age: int
    late_dist: float
    cooldown: int
    min_prev_pnl: float
    min_prev_mfe_atr: float
    stop_atr: float
    warning_source: str = "volume"
    osc_min_score: int = 3
    segment_exit_mode: str = "none"
    segment_min_mfe_atr: float = 0.0
    segment_exit_min_capture: float = 0.0
    segment_adx: float = 0.0
    allocation_scale: float = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Broad HYPE EMA-X trend-state search.")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--max-runs", type=int, default=0, help="Optional cap for quick probes.")
    return parser.parse_args()


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - mean) / std.replace(0.0, np.nan)


def add_v17_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result.close
    high = result.high
    low = result.low
    volume = result.volume
    typical = (high + low + close) / 3

    low9 = low.rolling(9, min_periods=9).min()
    high9 = high.rolling(9, min_periods=9).max()
    rsv = 100 * (close - low9) / (high9 - low9).replace(0.0, np.nan)
    result["kdj_k"] = rsv.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    result["kdj_d"] = result.kdj_k.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    result["kdj_j"] = 3 * result.kdj_k - 2 * result.kdj_d
    result["kdj_j_slope3"] = result.kdj_j.diff(3)

    tp_mean = typical.rolling(20, min_periods=20).mean()
    tp_mad = (typical - tp_mean).abs().rolling(20, min_periods=20).mean()
    result["cci20"] = (typical - tp_mean) / (0.015 * tp_mad.replace(0.0, np.nan))
    result["willr14"] = -100 * (high.rolling(14, min_periods=14).max() - close) / (
        high.rolling(14, min_periods=14).max() - low.rolling(14, min_periods=14).min()
    ).replace(0.0, np.nan)

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    result["macd_hist"] = ema12 - ema26 - (ema12 - ema26).ewm(span=9, adjust=False, min_periods=9).mean()
    result["macd_hist_slope3"] = result.macd_hist.diff(3)

    result["aroon_up14"] = high.rolling(14, min_periods=14).apply(lambda x: 100 * (1 + np.argmax(x)) / 14, raw=True)
    result["aroon_down14"] = low.rolling(14, min_periods=14).apply(lambda x: 100 * (1 + np.argmin(x)) / 14, raw=True)
    result["roc24"] = close.pct_change(24)
    result["roc96"] = close.pct_change(96)

    mfv = ((close - low) - (high - close)) / (high - low).replace(0.0, np.nan) * volume
    result["cmf20"] = mfv.rolling(20, min_periods=20).sum() / volume.rolling(20, min_periods=20).sum().replace(0.0, np.nan)
    obv_step = np.sign(close.diff()).fillna(0.0) * volume
    result["obv"] = obv_step.cumsum()
    result["obv_slope48"] = result.obv.diff(48) / volume.rolling(96, min_periods=96).sum().replace(0.0, np.nan)

    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    result["bb_pos20"] = (close - (mid - 2 * std)) / (4 * std).replace(0.0, np.nan)
    result["bb_width20"] = (4 * std) / mid.replace(0.0, np.nan)
    result["bb_width_z192"] = rolling_zscore(result.bb_width20, 192)
    result["keltner_width20"] = 4 * result.atr_pct96
    result["squeeze_on"] = result.bb_width20 < result.keltner_width20

    high_max = high.rolling(14, min_periods=14).max()
    low_min = low.rolling(14, min_periods=14).min()
    tr_sum = (high - low).rolling(14, min_periods=14).sum()
    result["chop14"] = 100 * np.log10(tr_sum / (high_max - low_min).replace(0.0, np.nan)) / np.log10(14)
    result["eff96_local"] = close.pct_change(96).abs() / close.pct_change().abs().rolling(96, min_periods=96).sum().replace(0.0, np.nan)

    vm_plus = (high - low.shift(1)).abs().rolling(14, min_periods=14).sum()
    vm_minus = (low - high.shift(1)).abs().rolling(14, min_periods=14).sum()
    tr = pd.concat([(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    tr14 = tr.rolling(14, min_periods=14).sum()
    result["vortex_plus14"] = vm_plus / tr14.replace(0.0, np.nan)
    result["vortex_minus14"] = vm_minus / tr14.replace(0.0, np.nan)

    result["dir"] = np.where(result.ema_spread > 0, 1, np.where(result.ema_spread < 0, -1, 0)).astype(np.int8)
    direction = result.dir.to_numpy("int8")
    result["dir_dist_ema96"] = direction * (close / result.ema96 - 1.0)
    result["dir_donchian96"] = np.where(direction > 0, result.donchian_pos96, 1 - result.donchian_pos96)
    result["dir_roc24"] = direction * result.roc24
    result["dir_roc96"] = direction * result.roc96
    result["dir_macd_hist"] = direction * result.macd_hist
    result["dir_macd_hist_slope3"] = direction * result.macd_hist_slope3
    result["dir_aroon"] = np.where(direction > 0, result.aroon_up14 - result.aroon_down14, result.aroon_down14 - result.aroon_up14)
    result["dir_cmf20"] = direction * result.cmf20
    result["dir_obv_slope48"] = direction * result.obv_slope48
    result["dir_vortex"] = np.where(direction > 0, result.vortex_plus14 - result.vortex_minus14, result.vortex_minus14 - result.vortex_plus14)
    result["dir_kdj_reset"] = np.where(direction > 0, result.kdj_j >= 45, result.kdj_j <= 55)
    result["dir_rsi"] = np.where(direction > 0, result.rsi14, 100 - result.rsi14)
    result["dir_willr"] = np.where(direction > 0, result.willr14, -100 - result.willr14)
    result["dir_cci20"] = direction * result.cci20
    result["trend_score"] = (
        (result.adx28 >= 28).astype(int)
        + (result.dir_macd_hist > 0).astype(int)
        + (result.dir_aroon > 0).astype(int)
        + (result.dir_vortex > 0).astype(int)
        + (result.dir_obv_slope48 > 0).astype(int)
        + (result.dir_cmf20 > -0.05).astype(int)
        + (result.chop14 <= 55).astype(int)
        + (result.eff96_local >= 0.18).astype(int)
        + (result.atr_ratio96_672 <= 1.8).astype(int)
        + (result.dir_dist_ema96 <= 0.08).astype(int)
    )
    return result


def base_filter_mask(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name == "none":
        return np.ones(len(frame), dtype=bool)
    if name == "low_dd_dist04":
        return (frame.dir_dist_ema96 <= 0.04).fillna(False).to_numpy(bool)
    if name == "atr18":
        return (frame.atr_ratio96_672 <= 1.8).fillna(False).to_numpy(bool)
    if name == "trend_score7":
        return (frame.trend_score >= 7).fillna(False).to_numpy(bool)
    if name == "trend_score8":
        return (frame.trend_score >= 8).fillna(False).to_numpy(bool)
    if name == "not_hot_edge":
        hot = (frame.dir_donchian96 >= 0.96) & (frame.dir_dist_ema96 > 0.04) & (frame.vol_surge192 < 1.0)
        return (~hot).fillna(False).to_numpy(bool)
    if name == "atr18_trend7":
        return ((frame.atr_ratio96_672 <= 1.8) & (frame.trend_score >= 7)).fillna(False).to_numpy(bool)
    if name == "dist06_trend7":
        return ((frame.dir_dist_ema96 <= 0.06) & (frame.trend_score >= 7)).fillna(False).to_numpy(bool)
    if name == "quality_combo":
        hot = (frame.dir_donchian96 >= 0.96) & (frame.dir_dist_ema96 > 0.04) & (frame.vol_surge192 < 1.0)
        return ((frame.atr_ratio96_672 <= 1.8) & (frame.trend_score >= 6) & ~hot).fillna(False).to_numpy(bool)
    raise ValueError(name)


def add_signal_mask(frame: pd.DataFrame, name: str, min_age: int, max_age: int, max_dist: float) -> np.ndarray:
    direction = frame.dir.to_numpy("int8")
    base = (
        (direction != 0)
        & frame.regime_age.between(min_age, max_age).fillna(False).to_numpy(bool)
        & (frame.dir_dist_ema96 <= max_dist).fillna(False).to_numpy(bool)
        & (frame.h1_ema_spread.to_numpy("float64") * direction > 0)
        & (frame.trend_score >= 6).fillna(False).to_numpy(bool)
    )
    if name == "none":
        return np.zeros(len(frame), dtype=bool)
    if name == "late_breakout":
        mask = base & (frame.dir_donchian96 >= 0.72).fillna(False).to_numpy(bool) & (frame.dir_roc24 >= 0).fillna(False).to_numpy(bool)
    elif name == "late_pullback":
        touched = np.where(direction > 0, frame.low.rolling(32, min_periods=1).min() / frame.ema96 - 1, 1 - frame.high.rolling(32, min_periods=1).max() / frame.ema96)
        mask = base & (touched <= 0.018) & (frame.dir_rsi >= 50).fillna(False).to_numpy(bool)
    elif name == "late_kdj_reset":
        reset = np.where(
            direction > 0,
            (frame.kdj_j.rolling(32, min_periods=1).min() <= 25) & (frame.kdj_j >= 45) & (frame.kdj_j_slope3 > 0),
            (frame.kdj_j.rolling(32, min_periods=1).max() >= 75) & (frame.kdj_j <= 55) & (frame.kdj_j_slope3 < 0),
        )
        mask = base & reset
    elif name == "late_squeeze_release":
        mask = base & frame.squeeze_on.shift(1).rolling(24, min_periods=1).max().fillna(False).astype(bool).to_numpy(bool) & (frame.bb_width_z192 > -0.2).fillna(False).to_numpy(bool)
    elif name == "late_aroon_vortex":
        mask = base & (frame.dir_aroon > 20).fillna(False).to_numpy(bool) & (frame.dir_vortex > 0).fillna(False).to_numpy(bool)
    elif name == "late_mfi_cmf":
        mask = base & (frame.dir_cmf20 > 0).fillna(False).to_numpy(bool) & (frame.mfi14.between(35, 75)).fillna(False).to_numpy(bool)
    else:
        raise ValueError(name)
    previous = np.r_[False, mask[:-1]]
    same_previous = np.r_[0, direction[:-1]] == direction
    return mask & ~(previous & same_previous)


def build_signal(frame: pd.DataFrame, plan: SignalPlan) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    base = entry_signal(frame, v6_variant())
    mask = base_filter_mask(frame, plan.base_filter)
    signal = base.copy()
    signal[~mask] = 0
    kind = np.array([""] * len(frame), dtype=object)
    kind[signal != 0] = "base"

    add_mask = add_signal_mask(frame, plan.add_signal, plan.add_min_age, plan.add_max_age, plan.add_dist)
    direction = frame.dir.to_numpy("int8")
    overwrite = add_mask & (signal == 0)
    signal[overwrite] = direction[overwrite]
    kind[overwrite] = plan.add_signal
    return signal, kind, {
        "base_bars": int(np.count_nonzero(base)),
        "filtered_base_bars": int(np.count_nonzero(signal[kind == "base"])),
        "add_bars": int(np.count_nonzero(add_mask)),
        "total_bars": int(np.count_nonzero(signal)),
    }


def signal_plans() -> list[SignalPlan]:
    plans: list[SignalPlan] = []
    for base_filter in (
        "none",
        "low_dd_dist04",
        "atr18",
        "not_hot_edge",
        "trend_score7",
        "trend_score8",
        "atr18_trend7",
        "dist06_trend7",
        "quality_combo",
    ):
        plans.append(SignalPlan(f"{base_filter}_base", base_filter))
    for base_filter in ("none", "atr18", "not_hot_edge", "quality_combo", "low_dd_dist04"):
        for add_signal in (
            "late_breakout",
            "late_pullback",
            "late_kdj_reset",
            "late_squeeze_release",
            "late_aroon_vortex",
            "late_mfi_cmf",
        ):
            plans.append(SignalPlan(f"{base_filter}_{add_signal}", base_filter, add_signal=add_signal))
    return plans


def engine_plans() -> list[EnginePlan]:
    plans: list[EnginePlan] = []
    for late_max_age, late_dist, cooldown, min_prev_pnl, min_mfe, late_name in (
        (256, 0.06, 16, 0.0, 4.0, "v14"),
        (256, 0.06, 16, -0.03, 4.0, "pnlm03"),
        (384, 0.06, 16, -0.03, 4.0, "age384_pnlm03"),
        (384, 0.075, 12, -0.03, 3.0, "age384_d075_pnlm03"),
    ):
        for stop in (9.0, 8.0, 7.0):
            for allocation_scale in (1.0, 0.9, 0.8, 0.75):
                plans.append(
                    EnginePlan(
                        f"{late_name}_stop{stop:g}_scale{allocation_scale:g}",
                        late_max_age,
                        late_dist,
                        cooldown,
                        min_prev_pnl,
                        min_mfe,
                        stop,
                        allocation_scale=allocation_scale,
                    )
                )
        for warning_source, osc_min_score in (("either", 2),):
            plans.append(
                EnginePlan(
                    f"{late_name}_either2_stop8",
                    late_max_age,
                    late_dist,
                    cooldown,
                    min_prev_pnl,
                    min_mfe,
                    8.0,
                    warning_source=warning_source,
                    osc_min_score=osc_min_score,
                )
            )
        plans.append(
            EnginePlan(
                f"{late_name}_segment_ema55_stop8",
                late_max_age,
                late_dist,
                cooldown,
                min_prev_pnl,
                min_mfe,
                8.0,
                segment_exit_mode="ema55",
                segment_min_mfe_atr=4.0,
                segment_exit_min_capture=0.35,
            )
        )
    return plans


def make_strategy(name: str, plan: EnginePlan) -> LateReentrySpec:
    base = focused_spec(
        name,
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=128,
        entry_max_dist_ema96=0.08,
        segment_exit_mode=plan.segment_exit_mode,
        segment_min_mfe_atr=plan.segment_min_mfe_atr,
        segment_exit_min_capture=plan.segment_exit_min_capture,
        segment_adx=plan.segment_adx,
        segment_bars=1,
    )
    v12 = replace(base, stop_atr=plan.stop_atr, warning_source=plan.warning_source, osc_min_score=plan.osc_min_score)
    return LateReentrySpec(
        name,
        v12,
        late_max_age=plan.late_max_age,
        late_dist_ema96=plan.late_dist,
        cooldown_bars=plan.cooldown,
        min_prev_pnl=plan.min_prev_pnl,
        min_prev_mfe_atr=plan.min_prev_mfe_atr,
    )


def row_from_result(result: dict[str, Any], signal_counts: dict[str, int], signal_plan: SignalPlan, engine_plan: EnginePlan) -> dict[str, Any]:
    max_dd = float(result["max_dd"])
    win_rate = float(result["win_rate"])
    ret = float(result["return"])
    target_pass = win_rate >= TARGET_WIN_RATE and max_dd >= TARGET_DD and ret >= TARGET_RETURN
    constraint_gap = max(0.0, TARGET_WIN_RATE - win_rate) + max(0.0, TARGET_DD - max_dd) * 3 + max(0.0, TARGET_RETURN - ret) / TARGET_RETURN
    return {
        "name": result["name"],
        "return": ret,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "target_pass": target_pass,
        "constraint_gap": constraint_gap,
        "target_score": ret + max_dd * 25 + (win_rate - 0.5) * 10,
        "sharpe": result["sharpe"],
        "trades": result["trades"],
        "late_trades": result["late_trades"],
        "avg_trade_pct": result["avg_trade_pct"],
        "median_trade_pct": result["median_trade_pct"],
        "worst_trade_pct": result["worst_trade_pct"],
        "exit_reasons": result["exit_reasons"],
        "signal_plan": signal_plan.name,
        "base_filter": signal_plan.base_filter,
        "add_signal": signal_plan.add_signal,
        "engine_plan": engine_plan.name,
        "allocation_scale": engine_plan.allocation_scale,
        **signal_counts,
    }


def target_gap(ret: float, max_dd: float, win_rate: float) -> float:
    return max(0.0, TARGET_WIN_RATE - win_rate) + max(0.0, TARGET_DD - max_dd) * 3 + max(0.0, TARGET_RETURN - ret) / TARGET_RETURN


def target_score(ret: float, max_dd: float, win_rate: float) -> float:
    return ret + max_dd * 25 + (win_rate - 0.5) * 10


def main() -> None:
    args = parse_args()
    raw = load_hype_data_lake()
    frame = add_v17_indicators(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    baseline = run_late_reentry(frame, v14_spec(), start_ts=start_ts, collect_trades=True)
    baseline["name"] = "V14_fixed"

    signals = [(plan, *build_signal(frame, plan)) for plan in signal_plans()]
    engines = engine_plans()
    rows: list[dict[str, Any]] = [
        {
            "name": "V14_fixed",
            "return": baseline["return"],
            "max_dd": baseline["max_dd"],
            "win_rate": baseline["win_rate"],
            "target_pass": baseline["win_rate"] >= TARGET_WIN_RATE and baseline["max_dd"] >= TARGET_DD and baseline["return"] >= TARGET_RETURN,
            "constraint_gap": target_gap(baseline["return"], baseline["max_dd"], baseline["win_rate"]),
            "target_score": target_score(baseline["return"], baseline["max_dd"], baseline["win_rate"]),
            "sharpe": baseline["sharpe"],
            "trades": baseline["trades"],
            "late_trades": baseline["late_trades"],
            "avg_trade_pct": baseline["avg_trade_pct"],
            "median_trade_pct": baseline["median_trade_pct"],
            "worst_trade_pct": baseline["worst_trade_pct"],
            "exit_reasons": baseline["exit_reasons"],
            "signal_plan": "V14",
            "base_filter": "V14",
            "add_signal": "none",
            "engine_plan": "V14",
            "allocation_scale": 1.0,
        }
    ]
    all_results = [baseline]
    run_count = 0
    for signal_plan, signal, kind, counts in signals:
        for engine_plan in engines:
            run_count += 1
            if args.max_runs and run_count > args.max_runs:
                break
            name = f"V17_{signal_plan.name}_{engine_plan.name}"
            strategy = make_strategy(name, engine_plan)
            scale = {"base": engine_plan.allocation_scale}
            if signal_plan.add_signal != "none":
                scale[signal_plan.add_signal] = signal_plan.add_scale * engine_plan.allocation_scale
            result = run_late_reentry(
                frame,
                strategy,
                start_ts=start_ts,
                collect_trades=True,
                signal_override=signal,
                signal_kind_override=kind,
                entry_allocation_scale=scale,
            )
            all_results.append(result)
            rows.append(row_from_result(result, counts, signal_plan, engine_plan))
        if args.max_runs and run_count > args.max_runs:
            break

    ranking = pd.DataFrame(rows).sort_values(["target_pass", "constraint_gap", "target_score"], ascending=[False, True, False])
    constraint_hits = ranking[(ranking.win_rate >= TARGET_WIN_RATE) & (ranking.max_dd >= TARGET_DD)].sort_values("return", ascending=False)
    top_names = set(ranking.head(args.top)["name"]) | set(constraint_hits.head(args.top)["name"])
    trades = pd.concat(
        [
            pd.DataFrame(result["trades_detail"]).assign(spec=result["name"])
            for result in all_results
            if result["name"] in top_names and result.get("trades_detail")
        ],
        ignore_index=True,
        sort=False,
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    constraint_hits.to_csv(CONSTRAINT_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "start": str(start_ts),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                    "bars": int(len(frame)),
                },
                "targets": {
                    "return": TARGET_RETURN,
                    "max_dd": TARGET_DD,
                    "win_rate": TARGET_WIN_RATE,
                },
                "baseline": rows[0],
                "signal_plans": [asdict(plan) for plan in signal_plans()],
                "engine_plans": [asdict(plan) for plan in engine_plans()],
                "ranking": ranking.head(args.top).to_dict(orient="records"),
                "constraint_hits": constraint_hits.head(args.top).to_dict(orient="records"),
                "notes": [
                    "V17 broadens trend-state search across momentum, volatility, volume, structure, and oscillator indicators.",
                    "Ranking prioritizes the user's hard constraints first, then return-adjusted target score.",
                    "Constraint hits require win_rate >= 80% and max_dd >= -20%; full target also requires return >= 50x.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"constraints={CONSTRAINT_PATH}")
    print(ranking.head(args.top).to_string(index=False))
    print("\\nconstraint hits")
    print(constraint_hits.head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
