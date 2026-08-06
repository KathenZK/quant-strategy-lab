from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from research_hype_ema_cross_strategy import (
    PERIODS_PER_YEAR,
    SLIPPAGE,
    SYMBOL,
    TRADE_COST,
    build_features,
    load_trusted_klines,
)


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    entry: str
    exit: str
    take_atr: float | None = None
    stop_atr: float | None = None
    adx_exit: float | None = None
    adx_exit_bars: int = 3
    disable_adx_after_mfe_atr: float | None = None
    ema384_break_bars: int = 2
    max_hold_bars: int | None = None


def entry_signal(frame: pd.DataFrame, variant: Variant) -> np.ndarray:
    spread = frame.ema_spread.to_numpy("float64")
    previous = np.r_[np.nan, spread[:-1]]
    cross_long = (spread > 0.0) & (previous <= 0.0)
    cross_short = (spread < 0.0) & (previous >= 0.0)
    regime_long = spread > 0.0
    regime_short = spread < 0.0

    if variant.entry.startswith("v2"):
        long_ok = (
            regime_long
            & (frame.adx28.to_numpy("float64") >= 28)
            & (frame.vol_surge192.to_numpy("float64") >= 0.25)
            & (frame.h1_adx21.to_numpy("float64") > 18)
            & (frame.h1_pdi21.to_numpy("float64") > frame.h1_mdi21.to_numpy("float64"))
        )
        short_ok = (
            regime_short
            & (frame.adx28.to_numpy("float64") >= 36)
            & (frame.vol_surge192.to_numpy("float64") >= 0.50)
            & (frame.h1_ema_spread.to_numpy("float64") < 0)
        )
        signal = np.zeros(len(frame), dtype=np.int8)
        signal[long_ok] = 1
        signal[short_ok] = -1
        return signal

    v4_long_filter = (
        (frame.ema96_slope48.to_numpy("float64") > 0)
        & (frame.pdi14.to_numpy("float64") > frame.mdi14.to_numpy("float64"))
        & (frame.rsi14.to_numpy("float64") >= 52)
        & (frame.h4_ema_spread.to_numpy("float64") > 0)
    )
    v4_short_filter = (
        (frame.ema96_slope48.to_numpy("float64") < 0)
        & (frame.mdi14.to_numpy("float64") > frame.pdi14.to_numpy("float64"))
        & (frame.rsi14.to_numpy("float64") <= 48)
        & (frame.h4_ema_spread.to_numpy("float64") < 0)
    )
    if "window" in variant.entry:
        window_bars = int(variant.entry.rsplit("_", maxsplit=1)[-1])
        regime_age = np.full(len(frame), np.inf)
        age = np.inf
        for i in range(len(frame)):
            if cross_long[i] or cross_short[i]:
                age = 0
            elif np.isfinite(age):
                age += 1
            regime_age[i] = age
        long_base = regime_long & (regime_age <= window_bars)
        short_base = regime_short & (regime_age <= window_bars)
    else:
        long_base = regime_long if "regime" in variant.entry else cross_long
        short_base = regime_short if "regime" in variant.entry else cross_short
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[long_base & v4_long_filter] = 1
    signal[short_base & v4_short_filter] = -1
    return signal


def run_variant(
    frame: pd.DataFrame,
    variant: Variant,
    *,
    start_ts: pd.Timestamp | None = None,
) -> dict[str, object]:
    if start_ts is None:
        start_i = 0
    else:
        ts_series = pd.to_datetime(frame.ts, utc=True)
        candidates = np.flatnonzero(ts_series >= start_ts)
        start_i = int(candidates[0]) if len(candidates) else len(frame)

    ts = pd.to_datetime(frame.ts, utc=True).to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    spread = frame.ema_spread.to_numpy("float64")
    previous_spread = np.r_[np.nan, spread[:-1]]
    ema384 = frame.ema384.to_numpy("float64")
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")
    signal = entry_signal(frame, variant)

    pos = 0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = 0
    hold_bars = 0
    bad_bars = 0
    mfe_atr = 0.0
    trades: list[dict[str, object]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, entry_px, entry_ts, entry_atr, equity, last_mark, hold_bars, bad_bars, mfe_atr
        equity *= 1 + pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST
        trades.append(
            {
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "pnl_pct": float(pos * (price / entry_px - 1)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "exit_reason": reason,
            }
        )
        pos = 0
        entry_px = 0.0
        entry_ts = None
        entry_atr = np.nan
        last_mark = price
        hold_bars = 0
        bad_bars = 0
        mfe_atr = 0.0

    for i in range(start_i, len(frame)):
        if i > start_i:
            if pos:
                equity *= 1 + pos * (open_[i] / last_mark - 1)
            last_mark = open_[i]

        if pending_entry and not pos:
            entry_px = open_[i] * (1 + SLIPPAGE if pending_entry > 0 else 1 - SLIPPAGE)
            pos = pending_entry
            entry_ts = pd.Timestamp(ts[i])
            entry_atr = atr672[i - 1] if i > 0 else atr672[i]
            equity *= 1 - TRADE_COST
            last_mark = entry_px
            pending_entry = 0

        if pos:
            hold_bars += 1
            if np.isfinite(entry_atr) and entry_atr > 0:
                if pos > 0:
                    mfe_atr = max(mfe_atr, (high[i] / entry_px - 1) / entry_atr)
                else:
                    mfe_atr = max(mfe_atr, (1 - low[i] / entry_px) / entry_atr)

            if np.isfinite(entry_atr) and entry_atr > 0:
                if variant.take_atr is not None:
                    take_px = entry_px * (1 + pos * variant.take_atr * entry_atr)
                    hit_take = high[i] >= take_px if pos > 0 else low[i] <= take_px
                    if hit_take:
                        px = take_px * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                        close_position(i, px, "take_profit")
                        curve.append(float(equity))
                        continue
                if variant.stop_atr is not None:
                    stop_px = entry_px * (1 - pos * variant.stop_atr * entry_atr)
                    hit_stop = low[i] <= stop_px if pos > 0 else high[i] >= stop_px
                    if hit_stop:
                        px = stop_px * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                        close_position(i, px, "stop_loss")
                        curve.append(float(equity))
                        continue

            equity *= 1 + pos * (close[i] / last_mark - 1)
            last_mark = close[i]

            opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (
                pos < 0 and spread[i] > 0 >= previous_spread[i]
            )
            if opposite_cross:
                px = open_[min(i + 1, len(frame) - 1)] * (
                    1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE
                )
                close_position(min(i + 1, len(frame) - 1), px, "opposite_cross")
                if signal[i] == -pos:
                    pending_entry = int(signal[i])
                curve.append(float(equity))
                continue

            trend_bad = False
            if variant.exit in {"ema384_break", "v2_plus_ema384"}:
                trend_bad = close[i] < ema384[i] if pos > 0 else close[i] > ema384[i]
            if variant.exit in {"adx_exit", "v2_plus_ema384"} and variant.adx_exit is not None:
                adx_disabled = (
                    variant.disable_adx_after_mfe_atr is not None
                    and mfe_atr >= variant.disable_adx_after_mfe_atr
                )
                if not adx_disabled:
                    trend_bad |= adx28[i] < variant.adx_exit
            bad_bars = bad_bars + 1 if trend_bad else 0
            required_bad_bars = (
                variant.ema384_break_bars
                if variant.exit in {"ema384_break", "v2_plus_ema384"}
                else variant.adx_exit_bars
            )
            if trend_bad and bad_bars >= required_bad_bars:
                px = open_[min(i + 1, len(frame) - 1)] * (
                    1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE
                )
                close_position(min(i + 1, len(frame) - 1), px, "trend_break")
                curve.append(float(equity))
                continue
            if variant.max_hold_bars is not None and hold_bars >= variant.max_hold_bars:
                px = open_[min(i + 1, len(frame) - 1)] * (
                    1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE
                )
                close_position(min(i + 1, len(frame) - 1), px, "timeout")
                curve.append(float(equity))
                continue

        if not pos and signal[i]:
            pending_entry = int(signal[i])

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "pnl_pct": float(pos * (close[-1] / entry_px - 1)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "exit_reason": "open_at_end",
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    wins = [trade for trade in closed if float(trade["pnl_pct"]) > 0]
    std = returns.std(ddof=0)
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype=float)
    reasons: dict[str, int] = {}
    for trade in closed:
        reasons[str(trade["exit_reason"])] = reasons.get(str(trade["exit_reason"]), 0) + 1
    return {
        "name": variant.name,
        "return": float(equity_curve.iloc[-1] - 1.0),
        "max_dd": float(drawdown.min()),
        "sharpe": 0.0 if std == 0.0 else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR)),
        "trades": len(closed),
        "win_rate": float(len(wins) / len(closed)) if closed else 0.0,
        "avg_trade_pct": float(pnl_values.mean()) if len(pnl_values) else 0.0,
        "median_trade_pct": float(np.median(pnl_values)) if len(pnl_values) else 0.0,
        "best_trade_pct": float(pnl_values.max()) if len(pnl_values) else 0.0,
        "worst_trade_pct": float(pnl_values.min()) if len(pnl_values) else 0.0,
        "exit_reasons": reasons,
    }


def main() -> None:
    raw = load_trusted_klines()
    frame = build_features(raw)
    end_ts = pd.to_datetime(frame.ts, utc=True).max()
    variants = [
        Variant(
            "V2_recreated_regime_reentry_atr_tp",
            "v2_regime",
            "adx_exit",
            take_atr=4.3,
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
            max_hold_bars=192,
        ),
        Variant("V4_current_cross_no_take", "v4_cross", "ema384_break"),
        Variant("V4_regime_reentry_no_take", "v4_regime", "ema384_break"),
        Variant(
            "V4_cross_with_atr_tp_sl",
            "v4_cross",
            "ema384_break",
            take_atr=4.3,
            stop_atr=9.0,
        ),
        Variant(
            "V4_regime_reentry_with_atr_tp_sl",
            "v4_regime",
            "ema384_break",
            take_atr=4.3,
            stop_atr=9.0,
        ),
        Variant(
            "V2_entry_no_take_ema384_exit",
            "v2_regime",
            "ema384_break",
            stop_atr=9.0,
        ),
        Variant(
            "V2_entry_no_take_adx_exit",
            "v2_regime",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
            max_hold_bars=192,
        ),
        Variant(
            "V2_entry_no_take_adx_exit_no_timeout",
            "v2_regime",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
        ),
        Variant(
            "V2_entry_no_take_adx_always_no_timeout",
            "v2_regime",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
        ),
        Variant(
            "V2_entry_no_take_no_stop_adx_no_timeout",
            "v2_regime",
            "adx_exit",
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
        ),
        Variant(
            "V2_entry_take_plus_ema384_exit",
            "v2_regime",
            "v2_plus_ema384",
            take_atr=4.3,
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
            ema384_break_bars=2,
            max_hold_bars=192,
        ),
        Variant("V4_window96_no_take_ema384_exit", "v4_window_96", "ema384_break"),
        Variant("V4_window192_no_take_ema384_exit", "v4_window_192", "ema384_break"),
        Variant("V4_window384_no_take_ema384_exit", "v4_window_384", "ema384_break"),
        Variant(
            "V4_window192_no_take_adx_exit",
            "v4_window_192",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
        ),
        Variant(
            "V4_window384_no_take_adx_exit",
            "v4_window_384",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
        ),
        Variant(
            "V4_window192_take_atr_exit",
            "v4_window_192",
            "ema384_break",
            take_atr=4.3,
            stop_atr=9.0,
        ),
    ]
    windows = {
        "1M": pd.Timedelta(days=30),
        "3M": pd.Timedelta(days=90),
        "6M": pd.Timedelta(days=182),
        "1Y": pd.Timedelta(days=365),
    }
    report = {
        "metadata": {
            "symbol": SYMBOL,
            "end": str(end_ts),
            "note": "Same trusted normalized data as V4 search; V2 is recreated from canvas V2 rules.",
        },
        "full": [run_variant(frame, variant) for variant in variants],
        "windows": {
            variant.name: {
                label: run_variant(frame, variant, start_ts=end_ts - delta)
                for label, delta in windows.items()
            }
            for variant in variants
        },
    }
    output = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_v2_v4_compare.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"wrote={output}")


if __name__ == "__main__":
    main()
