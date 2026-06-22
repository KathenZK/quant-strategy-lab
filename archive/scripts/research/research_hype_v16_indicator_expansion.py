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
from research_hype_state_machine_v12 import V12Spec, add_structure_features
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_v13_late_reentry import LateReentrySpec, run_late_reentry
from research_hype_v14_main_backfill import v14_spec


REPORT_PATH = Path("reports/hype_v16_indicator_expansion.json")
RANKING_PATH = Path("reports/hype_v16_indicator_expansion_ranking.csv")
TRADES_PATH = Path("reports/hype_v16_indicator_expansion_trades.csv")
SIGNAL_PATH = Path("reports/hype_v16_indicator_expansion_signal_counts.csv")

DATA_LAKE = Path("data/normalized/ohlcv")


@dataclass(frozen=True, slots=True)
class SignalSpec:
    name: str
    include_base: bool
    early: bool = False
    pullback: bool = False
    breakout: bool = False
    kdj_reset: bool = False
    max_age: int = 384
    dist: float = 0.08
    adx: float = 18.0
    h1_required: bool = True
    min_add_age: int = 0


@dataclass(frozen=True, slots=True)
class ExitSpec:
    name: str
    warning_source: str = "volume"
    osc_min_score: int = 3
    segment_exit_mode: str = "none"
    segment_min_mfe_atr: float = 0.0
    segment_exit_min_capture: float = 0.0
    segment_adx: float = 0.0
    segment_bars: int = 1
    warning_exit_min_capture: float = 0.35


@dataclass(frozen=True, slots=True)
class LateSpec:
    name: str
    max_age: int
    dist: float
    cooldown: int
    min_prev_mfe_atr: float
    min_prev_pnl: float = 0.0
    require_pullback: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explore post-V14 HYPE EMA crossover entry expansion with RSI/KDJ gates."
    )
    parser.add_argument("--exchange", default="binance", choices=["binance", "okx"])
    parser.add_argument("--market-type", default="perp")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--symbol-file", default="symbol=hype_usdt_usdt.parquet")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--top", type=int, default=30)
    return parser.parse_args()


def load_ohlcv(
    *,
    exchange: str,
    market_type: str,
    timeframe: str,
    symbol_file: str,
) -> pd.DataFrame:
    if exchange == "binance" and market_type == "perp" and timeframe == "15m":
        return load_hype_data_lake()

    root = DATA_LAKE / f"exchange={exchange}" / f"market_type={market_type}" / f"timeframe={timeframe}"
    files = sorted(root.rglob(symbol_file))
    if not files:
        raise FileNotFoundError(f"no {symbol_file} files under {root}")
    frame = pd.concat(
        [pd.read_parquet(path, columns=["ts", "open", "high", "low", "close", "volume"]) for path in files],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame


def add_v16_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    low9 = result.low.rolling(9, min_periods=9).min()
    high9 = result.high.rolling(9, min_periods=9).max()
    rsv = 100 * (result.close - low9) / (high9 - low9).replace(0.0, np.nan)
    result["kdj_k"] = rsv.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    result["kdj_d"] = result.kdj_k.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    result["kdj_j"] = 3 * result.kdj_k - 2 * result.kdj_d
    result["kdj_j_slope3"] = result.kdj_j.diff(3)
    result["ema21_slope16"] = result.ema21.pct_change(16)
    result["ema55_slope24"] = result.ema55.pct_change(24)
    result["rsi14_slope8"] = result.rsi14.diff(8)
    result["adx28_slope16"] = result.adx28.diff(16)
    result["low_to_ema96_32"] = result.low.rolling(32, min_periods=1).min() / result.ema96 - 1
    result["high_to_ema96_32"] = result.high.rolling(32, min_periods=1).max() / result.ema96 - 1
    result["kdj_j_low32"] = result.kdj_j.rolling(32, min_periods=1).min()
    result["kdj_j_high32"] = result.kdj_j.rolling(32, min_periods=1).max()
    result["rsi_low32"] = result.rsi14.rolling(32, min_periods=1).min()
    result["rsi_high32"] = result.rsi14.rolling(32, min_periods=1).max()
    result["close_high48_prev"] = result.high.shift(1).rolling(48, min_periods=24).max()
    result["close_low48_prev"] = result.low.shift(1).rolling(48, min_periods=24).min()
    result["close_high96_prev"] = result.high.shift(1).rolling(96, min_periods=48).max()
    result["close_low96_prev"] = result.low.shift(1).rolling(96, min_periods=48).min()
    return result


def _dist_to_ema96(frame: pd.DataFrame, direction: np.ndarray) -> np.ndarray:
    return direction * (frame.close.to_numpy("float64") / frame.ema96.to_numpy("float64") - 1.0)


def _same_h1(frame: pd.DataFrame, direction: np.ndarray) -> np.ndarray:
    h1_spread = frame.h1_ema_spread.to_numpy("float64")
    h1_pdi = frame.h1_pdi21.to_numpy("float64")
    h1_mdi = frame.h1_mdi21.to_numpy("float64")
    return ((direction > 0) & (h1_spread > 0) & (h1_pdi > h1_mdi)) | (
        (direction < 0) & (h1_spread < 0) & (h1_mdi >= h1_pdi)
    )


def _edge_only(mask: np.ndarray, direction: np.ndarray) -> np.ndarray:
    previous = np.r_[False, mask[:-1]]
    same_previous = np.r_[0, direction[:-1]] == direction
    return mask & ~(previous & same_previous)


def build_signal(frame: pd.DataFrame, spec: SignalSpec) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    base = entry_signal(frame, v6_variant())
    signal = base.copy() if spec.include_base else np.zeros(len(frame), dtype=np.int8)
    kinds = np.array([""] * len(frame), dtype=object)
    kinds[base != 0] = "base"

    spread = frame.ema_spread.to_numpy("float64")
    direction = np.where(spread > 0, 1, np.where(spread < 0, -1, 0)).astype(np.int8)
    valid_regime = direction != 0
    age = frame.regime_age.to_numpy("float64")
    dist = _dist_to_ema96(frame, direction)
    same_h1 = _same_h1(frame, direction)
    h1_ok = same_h1 if spec.h1_required else np.ones(len(frame), dtype=bool)
    trend_ok = (
        valid_regime
        & h1_ok
        & np.isfinite(age)
        & (age <= spec.max_age)
        & (age >= spec.min_add_age)
        & (dist <= spec.dist)
        & (frame.adx28.to_numpy("float64") >= spec.adx)
        & (frame.adx28_slope16.to_numpy("float64") >= -6.0)
        & (direction * frame.ema96_slope48.to_numpy("float64") > 0)
    )

    additions: dict[str, np.ndarray] = {}
    close = frame.close.to_numpy("float64")
    rsi = frame.rsi14.to_numpy("float64")
    kdj_j = frame.kdj_j.to_numpy("float64")
    kdj_slope = frame.kdj_j_slope3.to_numpy("float64")
    rsi_slope = frame.rsi14_slope8.to_numpy("float64")

    if spec.early:
        early = (
            trend_ok
            & (age <= min(spec.max_age, 128))
            & (frame.vol_surge192.to_numpy("float64") >= -0.10)
            & (
                ((direction > 0) & (rsi >= 50) & (rsi_slope >= -2) & (kdj_j >= 35) & (kdj_slope >= -8))
                | ((direction < 0) & (rsi <= 50) & (rsi_slope <= 2) & (kdj_j <= 65) & (kdj_slope <= 8))
            )
        )
        additions["early"] = _edge_only(early, direction)

    if spec.pullback:
        touched = ((direction > 0) & (frame.low_to_ema96_32.to_numpy("float64") <= 0.018)) | (
            (direction < 0) & (frame.high_to_ema96_32.to_numpy("float64") >= -0.018)
        )
        reclaim = ((direction > 0) & (close > frame.ema21.to_numpy("float64")) & (rsi >= 50)) | (
            (direction < 0) & (close < frame.ema21.to_numpy("float64")) & (rsi <= 50)
        )
        pullback = trend_ok & touched & reclaim & (frame.vol_surge96.to_numpy("float64") >= -0.25)
        additions["pullback"] = _edge_only(pullback, direction)

    if spec.kdj_reset:
        reset = ((direction > 0) & (frame.kdj_j_low32.to_numpy("float64") <= 25) & (kdj_j >= 45) & (kdj_slope > 0)) | (
            (direction < 0) & (frame.kdj_j_high32.to_numpy("float64") >= 75) & (kdj_j <= 55) & (kdj_slope < 0)
        )
        rsi_reset = ((direction > 0) & (frame.rsi_low32.to_numpy("float64") <= 48) & (rsi >= 52)) | (
            (direction < 0) & (frame.rsi_high32.to_numpy("float64") >= 52) & (rsi <= 48)
        )
        additions["kdj_reset"] = _edge_only(trend_ok & reset & rsi_reset, direction)

    if spec.breakout:
        breakout = ((direction > 0) & (close >= frame.close_high48_prev.to_numpy("float64")) & (rsi >= 52)) | (
            (direction < 0) & (close <= frame.close_low48_prev.to_numpy("float64")) & (rsi <= 48)
        )
        not_stretched = dist <= min(spec.dist, 0.065)
        additions["breakout"] = _edge_only(trend_ok & breakout & not_stretched, direction)

    counts: dict[str, int] = {"base": int(np.count_nonzero(base))}
    for name, mask in additions.items():
        values = direction[mask].astype(np.int8)
        overwrite = mask & (signal == 0)
        signal[overwrite] = direction[overwrite]
        kinds[overwrite] = name
        counts[name] = int(np.count_nonzero(values))

    counts["combined"] = int(np.count_nonzero(signal))
    return signal, kinds, counts


def make_v12(exit_spec: ExitSpec) -> V12Spec:
    base = focused_spec(
        exit_spec.name,
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=exit_spec.warning_exit_min_capture,
        entry_max_regime_age=128,
        entry_max_dist_ema96=0.08,
        segment_exit_mode=exit_spec.segment_exit_mode,
        segment_min_mfe_atr=exit_spec.segment_min_mfe_atr,
        segment_exit_min_capture=exit_spec.segment_exit_min_capture,
        segment_adx=exit_spec.segment_adx,
        segment_bars=exit_spec.segment_bars,
    )
    return replace(
        base,
        warning_source=exit_spec.warning_source,
        osc_min_score=exit_spec.osc_min_score,
    )


def make_late_spec(name: str, late: LateSpec, exit_spec: ExitSpec) -> LateReentrySpec:
    return LateReentrySpec(
        name=name,
        v12=make_v12(exit_spec),
        late_max_age=late.max_age,
        late_dist_ema96=late.dist,
        cooldown_bars=late.cooldown,
        min_prev_pnl=late.min_prev_pnl,
        min_prev_mfe_atr=late.min_prev_mfe_atr,
        require_pullback=late.require_pullback,
    )


def signal_specs() -> list[SignalSpec]:
    return [
        SignalSpec("V14_signal", include_base=True),
        SignalSpec("base_plus_early", include_base=True, early=True, max_age=256, dist=0.08, adx=18),
        SignalSpec("base_plus_pullback", include_base=True, pullback=True, max_age=384, dist=0.075, adx=18),
        SignalSpec("base_plus_kdj_reset", include_base=True, kdj_reset=True, max_age=512, dist=0.075, adx=18),
        SignalSpec("base_plus_breakout", include_base=True, breakout=True, max_age=384, dist=0.065, adx=20),
        SignalSpec(
            "base_plus_late_breakout",
            include_base=True,
            breakout=True,
            max_age=384,
            dist=0.065,
            adx=20,
            min_add_age=129,
        ),
        SignalSpec(
            "base_plus_late_kdj_reset",
            include_base=True,
            kdj_reset=True,
            max_age=512,
            dist=0.075,
            adx=18,
            min_add_age=129,
        ),
        SignalSpec(
            "base_plus_late_pullback",
            include_base=True,
            pullback=True,
            max_age=512,
            dist=0.065,
            adx=18,
            min_add_age=129,
        ),
        SignalSpec(
            "base_plus_late_all",
            include_base=True,
            pullback=True,
            breakout=True,
            kdj_reset=True,
            max_age=512,
            dist=0.065,
            adx=18,
            min_add_age=129,
        ),
        SignalSpec(
            "base_plus_all",
            include_base=True,
            early=True,
            pullback=True,
            breakout=True,
            kdj_reset=True,
            max_age=384,
            dist=0.075,
            adx=18,
        ),
        SignalSpec(
            "indicator_only",
            include_base=False,
            early=True,
            pullback=True,
            breakout=True,
            kdj_reset=True,
            max_age=384,
            dist=0.075,
            adx=18,
        ),
    ]


def exit_specs() -> list[ExitSpec]:
    return [
        ExitSpec("v14_exit"),
        ExitSpec("either_osc2", warning_source="either", osc_min_score=2),
        ExitSpec("segment_ema55_mfe4", segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35),
        ExitSpec(
            "segment_ema55_adx18_mfe4",
            segment_exit_mode="ema55_adx",
            segment_min_mfe_atr=4.0,
            segment_exit_min_capture=0.35,
            segment_adx=18.0,
        ),
        ExitSpec("segment_adx18_mfe4", segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3),
    ]


def late_specs() -> list[LateSpec]:
    return [
        LateSpec("v14_late", max_age=256, dist=0.06, cooldown=16, min_prev_mfe_atr=4.0),
        LateSpec("v14_late_pnl_m03", max_age=256, dist=0.06, cooldown=16, min_prev_mfe_atr=4.0, min_prev_pnl=-0.03),
        LateSpec("late384_pnl_m03", max_age=384, dist=0.06, cooldown=16, min_prev_mfe_atr=4.0, min_prev_pnl=-0.03),
        LateSpec("late384_dist075_pnl_m03", max_age=384, dist=0.075, cooldown=12, min_prev_mfe_atr=3.0, min_prev_pnl=-0.03),
        LateSpec("late384_dist06", max_age=384, dist=0.06, cooldown=16, min_prev_mfe_atr=4.0),
        LateSpec("late384_dist075", max_age=384, dist=0.075, cooldown=12, min_prev_mfe_atr=3.0),
        LateSpec("late512_dist06_pullback", max_age=512, dist=0.06, cooldown=12, min_prev_mfe_atr=3.0, require_pullback=True),
    ]


def compact(result: dict[str, Any], signal_count: dict[str, int]) -> dict[str, Any]:
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
        "best_trade_pct": result["best_trade_pct"],
        "worst_trade_pct": result["worst_trade_pct"],
        "avg_hold_bars": result["avg_hold_bars"],
        "exit_reasons": result["exit_reasons"],
        "signal_total": signal_count["combined"],
        "signal_base": signal_count.get("base", 0),
        "signal_early": signal_count.get("early", 0),
        "signal_pullback": signal_count.get("pullback", 0),
        "signal_kdj_reset": signal_count.get("kdj_reset", 0),
        "signal_breakout": signal_count.get("breakout", 0),
    }


def main() -> None:
    args = parse_args()
    raw = load_ohlcv(
        exchange=args.exchange,
        market_type=args.market_type,
        timeframe=args.timeframe,
        symbol_file=args.symbol_file,
    )
    frame = add_v16_features(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    start_ts = end_ts - pd.Timedelta(days=args.days)

    baseline = run_late_reentry(frame, v14_spec(), start_ts=start_ts, collect_trades=True)
    baseline["name"] = "V14_fixed"

    signal_cache = {spec.name: (*build_signal(frame, spec), spec) for spec in signal_specs()}
    rows: list[dict[str, Any]] = [compact(baseline, {"combined": 0, "base": 0})]
    all_results: list[dict[str, Any]] = [baseline]
    signal_rows: list[dict[str, Any]] = []

    for signal_name, (signal, kinds, counts, signal_spec) in signal_cache.items():
        signal_rows.append({"signal": signal_name, **counts, "spec": asdict(signal_spec)})
        for exit_spec in exit_specs():
            for late_spec in late_specs():
                if signal_name == "V14_signal" and (exit_spec.name != "v14_exit" or late_spec.name != "v14_late"):
                    continue
                name = f"V16_{signal_name}_{exit_spec.name}_{late_spec.name}"
                strategy = make_late_spec(name, late_spec, exit_spec)
                result = run_late_reentry(
                    frame,
                    strategy,
                    start_ts=start_ts,
                    collect_trades=True,
                    signal_override=signal,
                    signal_kind_override=kinds,
                    entry_allocation_scale={
                        "early": 0.55,
                        "pullback": 0.70,
                        "kdj_reset": 0.65,
                        "breakout": 0.60,
                    },
                )
                all_results.append(result)
                row = compact(result, counts)
                row.update(
                    {
                        "signal_spec": signal_name,
                        "exit_spec": exit_spec.name,
                        "late_spec": late_spec.name,
                    }
                )
                rows.append(row)

    ranking = pd.DataFrame(rows).drop_duplicates("name").sort_values(
        ["return", "max_dd", "trades"], ascending=[False, False, False]
    )
    best_names = set(ranking.head(args.top)["name"])
    trades = pd.concat(
        [
            pd.DataFrame(result["trades_detail"]).assign(spec=result["name"])
            for result in all_results
            if result["name"] in best_names and result.get("trades_detail")
        ],
        ignore_index=True,
        sort=False,
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    pd.DataFrame(signal_rows).to_csv(SIGNAL_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "exchange": args.exchange,
                    "market_type": args.market_type,
                    "timeframe": args.timeframe,
                    "start": str(start_ts),
                    "end": str(end_ts),
                    "bars": int(len(frame)),
                },
                "baseline": compact(baseline, {"combined": 0, "base": 0}),
                "signal_specs": [asdict(item) for item in signal_specs()],
                "exit_specs": [asdict(item) for item in exit_specs()],
                "late_specs": [asdict(item) for item in late_specs()],
                "signal_counts": signal_rows,
                "ranking": ranking.head(args.top).to_dict(orient="records"),
                "notes": [
                    "V16 keeps the V14/V13 late-reentry backtester and changes only signal source, exit overlay, and late-entry window.",
                    "Extra entries are event-style RSI/KDJ/EMA pullback or breakout-resume bars, scaled below base entries.",
                    "Primary screen sorts by return, then max drawdown, then trade count; inspect rolling stability before promoting to live.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"trades={TRADES_PATH}")
    print(f"signals={SIGNAL_PATH}")
    print(ranking.head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
