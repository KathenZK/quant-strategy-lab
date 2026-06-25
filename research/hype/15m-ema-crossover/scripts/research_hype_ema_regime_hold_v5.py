from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import numpy as np

from compare_hype_ema_v2_v4 import Variant, entry_signal, run_variant
from research_hype_ema_cross_strategy import (
    PERIODS_PER_YEAR,
    SLIPPAGE,
    SYMBOL,
    TRADE_COST,
    build_features,
)


DATA_LAKE_ROOT = Path(
    "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_v5_data_lake_compare.json")
MAX_ALLOCATION = 3.0
LONG_TARGET_ATR_PCT = 0.016
SHORT_TARGET_ATR_PCT = 0.014


def dynamic_allocation(direction: int, atr_pct: float) -> float:
    if not np.isfinite(atr_pct) or atr_pct <= 0:
        return 0.0
    target = LONG_TARGET_ATR_PCT if direction > 0 else SHORT_TARGET_ATR_PCT
    return min(MAX_ALLOCATION, target / atr_pct)


def load_hype_data_lake() -> pd.DataFrame:
    files = sorted(DATA_LAKE_ROOT.rglob("symbol=hype_usdt_usdt.parquet"))
    if not files:
        raise FileNotFoundError(f"no HYPE parquet files under {DATA_LAKE_ROOT}")

    frame = pd.concat(
        [
            pd.read_parquet(
                path,
                columns=["ts", "open", "high", "low", "close", "volume"],
            )
            for path in files
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame


def build_variants() -> list[Variant]:
    return [
        Variant(
            "V2_data_lake_recreated",
            "v2_regime",
            "adx_exit",
            take_atr=4.3,
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
            max_hold_bars=192,
        ),
        Variant("V4_data_lake_current", "v4_cross", "ema384_break"),
        Variant(
            "V5_no_take_adx_always",
            "v2_regime",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
        ),
        Variant(
            "V5_no_take_adx_mfe_disable_no_timeout",
            "v2_regime",
            "adx_exit",
            stop_atr=9.0,
            adx_exit=22,
            adx_exit_bars=3,
            disable_adx_after_mfe_atr=2.0,
        ),
        Variant("V5_no_take_ema384", "v2_regime", "ema384_break", stop_atr=9.0),
        Variant(
            "V5_take_plus_ema384",
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
    ]


def run_variant_dynamic_3x(
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
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")
    signal = entry_signal(frame, variant)

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = 0
    bad_bars = 0
    trades: list[dict[str, object]] = []
    curve: list[float] = []
    allocations: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark, bad_bars
        equity *= 1 + allocation * pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST * allocation
        trades.append(
            {
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "allocation": float(allocation),
                "pnl_pct": float(allocation * pos * (price / entry_px - 1)),
                "raw_pnl_pct": float(pos * (price / entry_px - 1)),
                "exit_reason": reason,
            }
        )
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_ts = None
        entry_atr = np.nan
        last_mark = price
        bad_bars = 0

    for i in range(start_i, len(frame)):
        if i > start_i:
            if pos:
                equity *= 1 + allocation * pos * (open_[i] / last_mark - 1)
            last_mark = open_[i]

        if pending_entry and not pos:
            entry_atr = atr672[i - 1] if i > 0 else atr672[i]
            next_allocation = dynamic_allocation(pending_entry, entry_atr)
            if next_allocation > 0:
                pos = pending_entry
                allocation = next_allocation
                entry_px = open_[i] * (1 + SLIPPAGE if pos > 0 else 1 - SLIPPAGE)
                entry_ts = pd.Timestamp(ts[i])
                equity *= 1 - TRADE_COST * allocation
                last_mark = entry_px
            pending_entry = 0

        if pos:
            if np.isfinite(entry_atr) and entry_atr > 0:
                stop_px = entry_px * (1 - pos * variant.stop_atr * entry_atr)
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

            trend_bad = bool(adx28[i] < variant.adx_exit)
            bad_bars = bad_bars + 1 if trend_bad else 0
            if bad_bars >= variant.adx_exit_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "trend_break")
                curve.append(float(equity))
                continue

        if not pos and signal[i]:
            pending_entry = int(signal[i])

        curve.append(float(equity))
        allocations.append(float(allocation))

    if pos:
        trades.append(
            {
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "allocation": float(allocation),
                "pnl_pct": float(allocation * pos * (close[-1] / entry_px - 1)),
                "raw_pnl_pct": float(pos * (close[-1] / entry_px - 1)),
                "exit_reason": "open_at_end",
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    wins = [trade for trade in closed if float(trade["pnl_pct"]) > 0]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype=float)
    allocation_values = np.array([float(trade["allocation"]) for trade in closed], dtype=float)
    std = returns.std(ddof=0)
    exit_reasons: dict[str, int] = {}
    for trade in closed:
        reason = str(trade["exit_reason"])
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    return {
        "name": "V6_dynamic_3x",
        "return": float(equity_curve.iloc[-1] - 1.0),
        "max_dd": float(drawdown.min()),
        "sharpe": 0.0 if std == 0.0 else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR)),
        "trades": len(closed),
        "win_rate": float(len(wins) / len(closed)) if closed else 0.0,
        "avg_trade_pct": float(pnl_values.mean()) if len(pnl_values) else 0.0,
        "median_trade_pct": float(np.median(pnl_values)) if len(pnl_values) else 0.0,
        "best_trade_pct": float(pnl_values.max()) if len(pnl_values) else 0.0,
        "worst_trade_pct": float(pnl_values.min()) if len(pnl_values) else 0.0,
        "avg_allocation": float(allocation_values.mean()) if len(allocation_values) else 0.0,
        "median_allocation": float(np.median(allocation_values)) if len(allocation_values) else 0.0,
        "max_allocation": float(allocation_values.max()) if len(allocation_values) else 0.0,
        "exit_reasons": exit_reasons,
    }


def main() -> None:
    raw = load_hype_data_lake()
    frame = build_features(raw)
    end_ts = pd.to_datetime(frame.ts, utc=True).max()
    windows = {
        "1W": pd.Timedelta(days=7),
        "1M": pd.Timedelta(days=30),
        "3M": pd.Timedelta(days=90),
        "6M": pd.Timedelta(days=182),
        "1Y": pd.Timedelta(days=365),
    }
    variants = build_variants()
    v5_variant = next(variant for variant in variants if variant.name == "V5_no_take_adx_always")
    report = {
        "metadata": {
            "symbol": SYMBOL,
            "source": "data_lake",
            "data_lake_root": str(DATA_LAKE_ROOT),
            "start": str(raw.ts.min()),
            "end": str(raw.ts.max()),
            "rows": len(raw),
            "dynamic_allocation": {
                "max_allocation": MAX_ALLOCATION,
                "long_target_atr_pct": LONG_TARGET_ATR_PCT,
                "short_target_atr_pct": SHORT_TARGET_ATR_PCT,
            },
        },
        "full": [run_variant(frame, variant) for variant in variants]
        + [run_variant_dynamic_3x(frame, v5_variant)],
        "windows": {
            variant.name: {
                label: run_variant(frame, variant, start_ts=end_ts - delta)
                for label, delta in windows.items()
            }
            for variant in variants
        },
    }
    report["windows"]["V6_dynamic_3x"] = {
        label: run_variant_dynamic_3x(frame, v5_variant, start_ts=end_ts - delta)
        for label, delta in windows.items()
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"metadata": report["metadata"], "full": report["full"]}, ensure_ascii=False, indent=2))
    print(f"wrote={REPORT_PATH}")


if __name__ == "__main__":
    main()
