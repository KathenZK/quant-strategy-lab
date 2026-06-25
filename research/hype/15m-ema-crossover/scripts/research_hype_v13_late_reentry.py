from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import entry_signal
from research_hype_ema_cross_strategy import SLIPPAGE, TRADE_COST, build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import dynamic_allocation, load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_ema_volume_overlay_v8 import v6_variant
from research_hype_state_machine_v12 import (
    V12Spec,
    add_structure_features,
    capture_ok,
    confirm_exit,
    entry_filter_allowed,
    hard_trend_invalidated,
    metric_result,
    oscillator_warning,
    reentry_allowed,
    segment_trend_weak,
    volume_warning_masks,
    warning_capture_ok,
)
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_trade_path_diagnostics_v11 import diagnose_trade, summarize, trade_frame_from_result


REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v13_late_reentry.json")
RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v13_late_reentry_ranking.csv")
TRADES_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v13_late_reentry_trades.csv")
DIAG_SUMMARY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v13_late_reentry_diagnostics_summary.csv")
DIAG_DETAIL_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v13_late_reentry_diagnostics_detail.csv")


@dataclass(frozen=True, slots=True)
class LateReentrySpec:
    name: str
    v12: V12Spec
    late_max_age: int
    late_dist_ema96: float
    cooldown_bars: int
    min_prev_pnl: float
    min_prev_mfe_atr: float
    require_pullback: bool = False
    pullback_buffer: float = 0.0


def base_v13_spec(name: str = "V13") -> V12Spec:
    return focused_spec(
        name,
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=128,
        entry_max_dist_ema96=0.08,
    )


def build_specs() -> list[LateReentrySpec]:
    base = base_v13_spec()
    specs = [
        LateReentrySpec("V13_baseline", base, 128, 0.08, 0, 999.0, 999.0),
    ]
    for max_age in (192, 256, 384, 0):
        for cooldown in (8, 16, 32):
            specs.append(
                LateReentrySpec(
                    f"V13_1_age{max_age or 'none'}_cd{cooldown}",
                    base,
                    late_max_age=max_age,
                    late_dist_ema96=0.08,
                    cooldown_bars=cooldown,
                    min_prev_pnl=0.0,
                    min_prev_mfe_atr=4.0,
                )
            )
    for dist in (0.06, 0.10):
        specs.append(
            LateReentrySpec(
                f"V13_1_age256_dist{int(dist * 100):02d}_cd16",
                base,
                late_max_age=256,
                late_dist_ema96=dist,
                cooldown_bars=16,
                min_prev_pnl=0.0,
                min_prev_mfe_atr=4.0,
            )
        )
    for mfe in (6.0, 8.0, 12.0):
        specs.append(
            LateReentrySpec(
                f"V13_1_age256_cd16_mfe{int(mfe)}",
                base,
                late_max_age=256,
                late_dist_ema96=0.08,
                cooldown_bars=16,
                min_prev_pnl=0.0,
                min_prev_mfe_atr=mfe,
            )
        )
    for cooldown in (16, 32):
        specs.append(
            LateReentrySpec(
                f"V13_1_age256_cd{cooldown}_pullback",
                base,
                late_max_age=256,
                late_dist_ema96=0.08,
                cooldown_bars=cooldown,
                min_prev_pnl=0.0,
                min_prev_mfe_atr=4.0,
                require_pullback=True,
            )
        )
    return specs


def current_regime(spread: np.ndarray, i: int) -> int:
    return 1 if spread[i] > 0 else -1 if spread[i] < 0 else 0


def dist_to_ema96(frame: pd.DataFrame, i: int, direction: int) -> float:
    ema96 = float(frame.ema96.iloc[i])
    if not np.isfinite(ema96) or ema96 <= 0:
        return np.inf
    return float(direction * (float(frame.close.iloc[i]) / ema96 - 1))


def late_reentry_allowed(
    frame: pd.DataFrame,
    i: int,
    direction: int,
    spec: LateReentrySpec,
    *,
    last_exit_direction: int,
    last_exit_regime: int,
    last_exit_i: int,
    last_exit_reason: str,
    last_exit_pnl: float,
    last_exit_mfe_atr: float,
    pullback_seen: bool,
) -> bool:
    age = float(frame.regime_age.iloc[i])
    if not np.isfinite(age) or age <= spec.v12.entry_max_regime_age:
        return False
    if spec.late_max_age > 0 and age > spec.late_max_age:
        return False
    if direction != last_exit_direction:
        return False
    regime = 1 if frame.ema_spread.iloc[i] > 0 else -1 if frame.ema_spread.iloc[i] < 0 else 0
    if regime != last_exit_regime or regime != direction:
        return False
    if last_exit_i < 0 or i - last_exit_i < spec.cooldown_bars:
        return False
    if last_exit_reason == "stop_loss":
        return False
    if last_exit_pnl < spec.min_prev_pnl or last_exit_mfe_atr < spec.min_prev_mfe_atr:
        return False
    if spec.require_pullback and not pullback_seen:
        return False
    return dist_to_ema96(frame, i, direction) <= spec.late_dist_ema96


def run_late_reentry(
    frame: pd.DataFrame,
    spec: LateReentrySpec,
    *,
    start_ts: pd.Timestamp | None = None,
    collect_trades: bool = False,
    signal_override: np.ndarray | None = None,
    signal_kind_override: np.ndarray | None = None,
    entry_allocation_scale: dict[str, float] | None = None,
    max_entry_allocation: float | None = None,
) -> dict[str, Any]:
    ts_series = pd.to_datetime(frame.ts, utc=True)
    if start_ts is None:
        start_i = 0
    else:
        candidates = np.flatnonzero(ts_series >= start_ts)
        start_i = int(candidates[0]) if len(candidates) else len(frame)
    ts = ts_series.to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    spread = frame.ema_spread.to_numpy("float64")
    previous_spread = np.r_[np.nan, spread[:-1]]
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")
    signal = signal_override if signal_override is not None else entry_signal(frame, v6_variant())
    volume_long, volume_short = volume_warning_masks(frame, spec.v12)
    osc_long, osc_short = oscillator_warning(frame, spec.v12)

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    entry_kind = ""
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = 0
    pending_entry_kind = ""
    hold_bars = 0
    bad_bars = 0
    hard_bad_bars = 0
    segment_bad_bars = 0
    mfe_atr = 0.0
    warning_active = False
    warning_reason = ""
    warning_ts: pd.Timestamp | None = None
    high_water = 0.0
    low_water = 0.0
    last_exit_direction = 0
    last_exit_regime = 0
    last_exit_i = -1
    last_exit_reason = ""
    last_exit_pnl = 0.0
    last_exit_mfe_atr = 0.0
    pullback_seen = False
    trades: list[dict[str, Any]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark, entry_kind
        nonlocal hold_bars, bad_bars, mfe_atr, warning_active, warning_reason, warning_ts
        nonlocal hard_bad_bars, segment_bad_bars, high_water, low_water, last_exit_direction, last_exit_regime
        nonlocal last_exit_i, last_exit_reason, last_exit_pnl, last_exit_mfe_atr, pullback_seen
        equity *= 1 + allocation * pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST * allocation
        raw_pnl = pos * (price / entry_px - 1)
        pnl_pct = allocation * raw_pnl
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_kind": entry_kind,
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(pnl_pct),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "warning_reason": warning_reason,
                "warning_ts": str(warning_ts) if warning_ts is not None else "",
                "exit_reason": reason,
                "equity_after": float(equity),
            }
        )
        last_exit_direction = int(pos)
        last_exit_regime = current_regime(spread, i)
        last_exit_i = int(i)
        last_exit_reason = reason
        last_exit_pnl = float(pnl_pct)
        last_exit_mfe_atr = float(mfe_atr)
        pullback_seen = False
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_ts = None
        entry_atr = np.nan
        entry_kind = ""
        last_mark = price
        hold_bars = 0
        bad_bars = 0
        hard_bad_bars = 0
        segment_bad_bars = 0
        mfe_atr = 0.0
        warning_active = False
        warning_reason = ""
        warning_ts = None
        high_water = 0.0
        low_water = 0.0

    for i in range(start_i, len(frame)):
        if i > start_i:
            if pos:
                equity *= 1 + allocation * pos * (open_[i] / last_mark - 1)
            last_mark = open_[i]

        if not pos and last_exit_i >= 0 and current_regime(spread, i) == last_exit_regime:
            ema96 = float(frame.ema96.iloc[i])
            if np.isfinite(ema96):
                if last_exit_direction > 0 and low[i] <= ema96 * (1 + spec.pullback_buffer):
                    pullback_seen = True
                elif last_exit_direction < 0 and high[i] >= ema96 * (1 - spec.pullback_buffer):
                    pullback_seen = True

        if pending_entry and not pos:
            entry_atr = atr672[i - 1] if i > 0 else atr672[i]
            next_allocation = dynamic_allocation(pending_entry, entry_atr)
            if entry_allocation_scale:
                for prefix, scale in entry_allocation_scale.items():
                    if pending_entry_kind.startswith(prefix):
                        next_allocation *= scale
                        break
            if max_entry_allocation is not None:
                next_allocation = min(max_entry_allocation, next_allocation)
            if next_allocation > 0:
                pos = pending_entry
                allocation = next_allocation
                entry_kind = pending_entry_kind
                entry_px = open_[i] * (1 + SLIPPAGE if pos > 0 else 1 - SLIPPAGE)
                entry_ts = pd.Timestamp(ts[i])
                high_water = high[i]
                low_water = low[i]
                equity *= 1 - TRADE_COST * allocation
                last_mark = entry_px
            pending_entry = 0
            pending_entry_kind = ""

        if pos:
            hold_bars += 1
            high_water = max(high_water, high[i])
            low_water = min(low_water, low[i])
            if np.isfinite(entry_atr) and entry_atr > 0:
                if pos > 0:
                    mfe_atr = max(mfe_atr, (high[i] / entry_px - 1) / entry_atr)
                else:
                    mfe_atr = max(mfe_atr, (1 - low[i] / entry_px) / entry_atr)
                stop_px = entry_px * (1 - pos * spec.v12.stop_atr * entry_atr)
                hit_stop = low[i] <= stop_px if pos > 0 else high[i] >= stop_px
                if hit_stop:
                    px = stop_px * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(i, px, "stop_loss")
                    curve.append(float(equity))
                    continue

            equity *= 1 + allocation * pos * (close[i] / last_mark - 1)
            last_mark = close[i]

            opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (
                pos < 0 and spread[i] > 0 >= previous_spread[i]
            )
            if opposite_cross:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "opposite_cross")
                curve.append(float(equity))
                continue

            hard_bad = hard_trend_invalidated(frame, i, pos, spec.v12)
            hard_bad_bars = hard_bad_bars + 1 if hard_bad else 0
            if hard_bad_bars >= spec.v12.hard_exit_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, f"hard_{spec.v12.hard_exit_mode}")
                curve.append(float(equity))
                continue

            volume_warning = (pos > 0 and volume_long[i]) or (pos < 0 and volume_short[i])
            osc_warning = (pos > 0 and osc_long[i]) or (pos < 0 and osc_short[i])
            if mfe_atr >= spec.v12.min_mfe_atr and not warning_active:
                if spec.v12.warning_source == "volume" and volume_warning:
                    warning_active = True
                    warning_reason = "volume"
                    warning_ts = pd.Timestamp(ts[i])
                elif spec.v12.warning_source == "osc" and osc_warning:
                    warning_active = True
                    warning_reason = "osc"
                    warning_ts = pd.Timestamp(ts[i])
                elif spec.v12.warning_source == "either" and (volume_warning or osc_warning):
                    warning_active = True
                    warning_reason = "volume" if volume_warning else "osc"
                    warning_ts = pd.Timestamp(ts[i])

            if (
                warning_active
                and confirm_exit(frame, i, pos, entry_px, entry_atr, high_water, low_water, spec.v12)
                and warning_capture_ok(close[i], pos, entry_px, high_water, low_water, spec.v12)
            ):
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, f"warning_confirm_{warning_reason}")
                curve.append(float(equity))
                continue

            if spec.v12.segment_exit_mode != "none" and mfe_atr >= spec.v12.segment_min_mfe_atr:
                segment_bad = segment_trend_weak(frame, i, pos, spec.v12) and capture_ok(
                    close[i],
                    pos,
                    entry_px,
                    high_water,
                    low_water,
                    spec.v12.segment_exit_min_capture,
                )
                segment_bad_bars = segment_bad_bars + 1 if segment_bad else 0
                if segment_bad_bars >= spec.v12.segment_bars:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, f"segment_{spec.v12.segment_exit_mode}")
                    curve.append(float(equity))
                    continue

            if spec.v12.fallback_adx > 0:
                trend_bad = bool(adx28[i] < spec.v12.fallback_adx)
                bad_bars = bad_bars + 1 if trend_bad else 0
                if bad_bars >= spec.v12.fallback_bars:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, "fallback_trend_break")
                    curve.append(float(equity))
                    continue

        if not pos and signal[i]:
            direction = int(signal[i])
            source_kind = ""
            if signal_kind_override is not None:
                source_kind = str(signal_kind_override[i])
            normal_ok = reentry_allowed(
                frame,
                i,
                direction,
                spec.v12,
                last_exit_direction,
                last_exit_regime,
            ) and entry_filter_allowed(frame, i, direction, spec.v12)
            late_ok = late_reentry_allowed(
                frame,
                i,
                direction,
                spec,
                last_exit_direction=last_exit_direction,
                last_exit_regime=last_exit_regime,
                last_exit_i=last_exit_i,
                last_exit_reason=last_exit_reason,
                last_exit_pnl=last_exit_pnl,
                last_exit_mfe_atr=last_exit_mfe_atr,
                pullback_seen=pullback_seen,
            )
            if normal_ok or late_ok:
                pending_entry = direction
                base_kind = "late" if late_ok and not normal_ok else "normal"
                pending_entry_kind = f"{source_kind}_{base_kind}" if source_kind else base_kind

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_kind": entry_kind,
                "entry_price": float(entry_px),
                "exit_price": float(close[-1]),
                "allocation": float(allocation),
                "raw_pnl_pct": float(pos * (close[-1] / entry_px - 1)),
                "pnl_pct": float(allocation * pos * (close[-1] / entry_px - 1)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "warning_reason": warning_reason,
                "warning_ts": str(warning_ts) if warning_ts is not None else "",
                "exit_reason": "open_at_end",
                "equity_after": float(equity),
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    result = metric_result(spec.v12, equity_curve, trades, collect_trades=collect_trades)
    result.update(
        {
            "name": spec.name,
            "late_max_age": spec.late_max_age,
            "late_dist_ema96": spec.late_dist_ema96,
            "cooldown_bars": spec.cooldown_bars,
            "min_prev_pnl": spec.min_prev_pnl,
            "min_prev_mfe_atr": spec.min_prev_mfe_atr,
            "require_pullback": spec.require_pullback,
            "pullback_buffer": spec.pullback_buffer,
            "late_trades": int(sum(1 for trade in trades if str(trade.get("entry_kind", "")).endswith("late") and trade["exit_reason"] != "open_at_end")),
        }
    )
    return result


def compact_metric(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "name",
        "return",
        "max_dd",
        "sharpe",
        "trades",
        "late_trades",
        "win_rate",
        "avg_trade_pct",
        "median_trade_pct",
        "best_trade_pct",
        "worst_trade_pct",
        "avg_hold_bars",
        "late_max_age",
        "late_dist_ema96",
        "cooldown_bars",
        "min_prev_pnl",
        "min_prev_mfe_atr",
        "require_pullback",
        "exit_reasons",
    ]
    return {key: result[key] for key in keys}


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)
    specs = build_specs()
    results = [run_late_reentry(frame, spec, start_ts=start_ts, collect_trades=True) for spec in specs]
    ranking = pd.DataFrame([compact_metric(result) for result in results]).sort_values(
        ["return", "max_dd"], ascending=[False, False]
    )
    best_name = str(ranking.iloc[0]["name"])
    best = next(result for result in results if result["name"] == best_name)
    trades = pd.DataFrame(best["trades_detail"])

    ts_index = pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))
    detail = pd.DataFrame(
        [
            diagnose_trade(frame, ts_index, trade)
            for _, trade in trade_frame_from_result(best["name"], best["trades_detail"]).iterrows()
        ]
    )
    summary, categories = summarize(detail)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    detail.to_csv(DIAG_DETAIL_PATH, index=False)
    summary.to_csv(DIAG_SUMMARY_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "start": str(start_ts),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                },
                "specs": [
                    {
                        **asdict(spec),
                        "v12": asdict(spec.v12),
                    }
                    for spec in specs
                ],
                "ranking": ranking.to_dict(orient="records"),
                "best": compact_metric(best),
                "best_diagnostics_summary": summary.to_dict(orient="records"),
                "best_diagnostics_categories": categories.to_dict(orient="records"),
                "notes": [
                    "V13.1 keeps normal V13 first-entry filters: age <= 128 and dist_ema96 <= 8%.",
                    "Late re-entry is only allowed after a profitable same-regime trade and never after stop_loss.",
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
    print("\\nbest diagnostics")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
