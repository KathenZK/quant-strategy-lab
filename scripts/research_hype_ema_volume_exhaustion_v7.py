from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import Variant
from research_hype_ema_cross_strategy import (
    PERIODS_PER_YEAR,
    SLIPPAGE,
    TRADE_COST,
    build_features,
)
from research_hype_ema_regime_hold_v5 import (
    dynamic_allocation,
    load_hype_data_lake,
    run_variant_dynamic_3x,
)


REPORT_PATH = Path("reports/hype_ema_volume_exhaustion_v7.json")
RANKING_PATH = Path("reports/hype_ema_volume_exhaustion_v7_ranking.csv")
TOP_TRADES_PATH = Path("reports/hype_ema_volume_exhaustion_v7_top_trades.csv")


@dataclass(frozen=True, slots=True)
class V7Spec:
    name: str
    entry_window: int
    entry_rvol: float
    entry_mode: str
    exit_rvol: float
    wick_min: float
    fail_bars: int
    min_mfe_atr: float
    invalid_bars: int
    stop_atr: float = 9.0


def add_volume_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result.close
    high = result.high
    low = result.low
    open_ = result.open
    volume = result.volume
    candle_range = (high - low).replace(0.0, np.nan)
    typical = (high + low + close) / 3
    money_flow = typical * volume
    positive_flow = money_flow.where(typical > typical.shift(1), 0.0)
    negative_flow = money_flow.where(typical < typical.shift(1), 0.0)
    sign = np.sign(close.diff()).fillna(0.0)

    result["rvol96"] = volume / volume.rolling(96, min_periods=96).mean().replace(0.0, np.nan)
    result["rvol192"] = volume / volume.rolling(192, min_periods=192).mean().replace(0.0, np.nan)
    result["candle_pos"] = ((close - low) / candle_range).clip(0.0, 1.0)
    result["upper_wick"] = ((high - np.maximum(open_, close)) / candle_range).clip(0.0, 1.0)
    result["lower_wick"] = ((np.minimum(open_, close) - low) / candle_range).clip(0.0, 1.0)
    result["body_range"] = ((close - open_).abs() / candle_range).clip(0.0, 1.0)
    result["obv"] = (sign * volume).cumsum()
    result["obv_mom48"] = result.obv - result.obv.shift(48)
    result["obv_mom96"] = result.obv - result.obv.shift(96)
    flow_ratio = (
        positive_flow.rolling(14, min_periods=14).sum()
        / negative_flow.rolling(14, min_periods=14).sum().replace(0.0, np.nan)
    )
    result["mfi14"] = 100 - 100 / (1 + flow_ratio)
    mfv = ((2 * close - high - low) / candle_range.replace(0.0, np.nan)) * volume
    result["cmf20"] = (
        mfv.rolling(20, min_periods=20).sum()
        / volume.rolling(20, min_periods=20).sum().replace(0.0, np.nan)
    )
    for window in (48, 96, 192):
        result[f"price_high{window}"] = high.rolling(window, min_periods=window).max()
        result[f"price_low{window}"] = low.rolling(window, min_periods=window).min()
        result[f"mfi_high{window}"] = result.mfi14.rolling(window, min_periods=window).max()
        result[f"mfi_low{window}"] = result.mfi14.rolling(window, min_periods=window).min()
    result["ret3_abs"] = close.pct_change(3).abs()
    return result


def build_v7_specs() -> list[V7Spec]:
    specs: list[V7Spec] = []
    for entry_window in (32, 64, 96):
        for entry_rvol in (1.2, 1.5, 1.8):
            for entry_mode in ("price", "flow_any", "flow_all"):
                for exit_rvol in (1.5, 2.0, 2.5):
                    for min_mfe_atr in (1.5, 2.5):
                        for invalid_bars in (0, 2, 4):
                            name = (
                                f"V7_w{entry_window}_rv{entry_rvol:g}_{entry_mode}"
                                f"_xrv{exit_rvol:g}_mfe{min_mfe_atr:g}_inv{invalid_bars}"
                            )
                            specs.append(
                                V7Spec(
                                    name=name,
                                    entry_window=entry_window,
                                    entry_rvol=entry_rvol,
                                    entry_mode=entry_mode,
                                    exit_rvol=exit_rvol,
                                    wick_min=0.35,
                                    fail_bars=2,
                                    min_mfe_atr=min_mfe_atr,
                                    invalid_bars=invalid_bars,
                                )
                            )
    return specs


def entry_signal(frame: pd.DataFrame, spec: V7Spec) -> np.ndarray:
    spread = frame.ema_spread.to_numpy("float64")
    previous = np.r_[np.nan, spread[:-1]]
    long_cross = (spread > 0) & (previous <= 0)
    short_cross = (spread < 0) & (previous >= 0)
    regime_long = spread > 0
    regime_short = spread < 0
    age = np.full(len(frame), np.inf)
    current_age = np.inf
    for i in range(len(frame)):
        if long_cross[i] or short_cross[i]:
            current_age = 0
        elif np.isfinite(current_age):
            current_age += 1
        age[i] = current_age

    volume_ok = frame.rvol96.to_numpy("float64") >= spec.entry_rvol
    price_long = (frame.candle_pos.to_numpy("float64") >= 0.58) & (
        frame.close.to_numpy("float64") > frame.open.to_numpy("float64")
    )
    price_short = (frame.candle_pos.to_numpy("float64") <= 0.42) & (
        frame.close.to_numpy("float64") < frame.open.to_numpy("float64")
    )
    obv_long = frame.obv_mom48.to_numpy("float64") > 0
    obv_short = frame.obv_mom48.to_numpy("float64") < 0
    mfi_long = frame.mfi14.to_numpy("float64") >= 52
    mfi_short = frame.mfi14.to_numpy("float64") <= 48
    cmf_long = frame.cmf20.to_numpy("float64") > 0
    cmf_short = frame.cmf20.to_numpy("float64") < 0

    if spec.entry_mode == "price":
        flow_long = price_long
        flow_short = price_short
    elif spec.entry_mode == "flow_any":
        flow_long = price_long & (obv_long | mfi_long | cmf_long)
        flow_short = price_short & (obv_short | mfi_short | cmf_short)
    elif spec.entry_mode == "flow_all":
        flow_long = price_long & obv_long & (mfi_long | cmf_long)
        flow_short = price_short & obv_short & (mfi_short | cmf_short)
    else:
        raise ValueError(f"unknown entry mode: {spec.entry_mode}")

    long_ok = regime_long & (age <= spec.entry_window) & volume_ok & flow_long
    short_ok = regime_short & (age <= spec.entry_window) & volume_ok & flow_short
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[long_ok] = 1
    signal[short_ok] = -1
    return signal


def exhaustion_masks(frame: pd.DataFrame, spec: V7Spec) -> tuple[np.ndarray, np.ndarray]:
    rvol = frame.rvol96.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    atr = frame.atr_pct96.to_numpy("float64")
    new_high = high >= frame.price_high96.shift(1).to_numpy("float64")
    new_low = low <= frame.price_low96.shift(1).to_numpy("float64")
    mfi_lower_high = frame.mfi14.to_numpy("float64") <= (
        frame.mfi_high96.shift(1).to_numpy("float64") - 8
    )
    mfi_higher_low = frame.mfi14.to_numpy("float64") >= (
        frame.mfi_low96.shift(1).to_numpy("float64") + 8
    )
    blowoff_long = (
        new_high
        & (rvol >= spec.exit_rvol)
        & (frame.upper_wick.to_numpy("float64") >= spec.wick_min)
        & (frame.candle_pos.to_numpy("float64") <= 0.58)
    )
    blowoff_short = (
        new_low
        & (rvol >= spec.exit_rvol)
        & (frame.lower_wick.to_numpy("float64") >= spec.wick_min)
        & (frame.candle_pos.to_numpy("float64") >= 0.42)
    )
    divergence_long = new_high & (rvol >= 1.0) & mfi_lower_high & (close < high)
    divergence_short = new_low & (rvol >= 1.0) & mfi_higher_low & (close > low)
    effort_fail = (rvol >= spec.exit_rvol) & (frame.ret3_abs.to_numpy("float64") <= 0.45 * atr)
    effort_long = effort_fail & (frame.candle_pos.to_numpy("float64") <= 0.55)
    effort_short = effort_fail & (frame.candle_pos.to_numpy("float64") >= 0.45)
    return blowoff_long | divergence_long | effort_long, blowoff_short | divergence_short | effort_short


def run_v7(
    frame: pd.DataFrame,
    spec: V7Spec,
    *,
    start_ts: pd.Timestamp | None = None,
    collect_trades: bool = False,
) -> dict[str, object]:
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
    atr672 = frame.atr_pct672.to_numpy("float64")
    ema96 = frame.ema96.to_numpy("float64")
    cmf20 = frame.cmf20.to_numpy("float64")
    mfi14 = frame.mfi14.to_numpy("float64")
    obv_mom48 = frame.obv_mom48.to_numpy("float64")
    signal = entry_signal(frame, spec)
    exhaust_long, exhaust_short = exhaustion_masks(frame, spec)

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = 0
    hold_bars = 0
    fail_bars = 0
    invalid_bars = 0
    mfe_atr = 0.0
    trades: list[dict[str, object]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark
        nonlocal hold_bars, fail_bars, invalid_bars, mfe_atr
        equity *= 1 + allocation * pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST * allocation
        raw_pnl = pos * (price / entry_px - 1)
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(allocation * raw_pnl),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "exit_reason": reason,
                "equity_after": float(equity),
            }
        )
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_ts = None
        entry_atr = np.nan
        last_mark = price
        hold_bars = 0
        fail_bars = 0
        invalid_bars = 0
        mfe_atr = 0.0

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
            hold_bars += 1
            if np.isfinite(entry_atr) and entry_atr > 0:
                if pos > 0:
                    mfe_atr = max(mfe_atr, (high[i] / entry_px - 1) / entry_atr)
                else:
                    mfe_atr = max(mfe_atr, (1 - low[i] / entry_px) / entry_atr)
                stop_px = entry_px * (1 - pos * spec.stop_atr * entry_atr)
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

            entry_invalid = False
            if spec.invalid_bars > 0 and mfe_atr < spec.min_mfe_atr and hold_bars >= 8:
                if pos > 0:
                    entry_invalid = close[i] < ema96[i] or (
                        cmf20[i] < 0 and obv_mom48[i] < 0 and mfi14[i] < 50
                    )
                else:
                    entry_invalid = close[i] > ema96[i] or (
                        cmf20[i] > 0 and obv_mom48[i] > 0 and mfi14[i] > 50
                    )
            invalid_bars = invalid_bars + 1 if entry_invalid else 0
            if spec.invalid_bars > 0 and invalid_bars >= spec.invalid_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "entry_invalidated")
                curve.append(float(equity))
                continue

            exhausted = (pos > 0 and exhaust_long[i]) or (pos < 0 and exhaust_short[i])
            exhausted = exhausted and mfe_atr >= spec.min_mfe_atr and hold_bars >= 4
            fail_bars = fail_bars + 1 if exhausted else 0
            if fail_bars >= spec.fail_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "volume_exhaustion")
                curve.append(float(equity))
                continue

        if not pos and signal[i]:
            pending_entry = int(signal[i])

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(close[-1]),
                "allocation": float(allocation),
                "raw_pnl_pct": float(pos * (close[-1] / entry_px - 1)),
                "pnl_pct": float(allocation * pos * (close[-1] / entry_px - 1)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "exit_reason": "open_at_end",
                "equity_after": float(equity),
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype=float)
    hold_values = np.array([int(trade["hold_bars"]) for trade in closed], dtype=float)
    allocation_values = np.array([float(trade["allocation"]) for trade in closed], dtype=float)
    exit_reasons: dict[str, int] = {}
    for trade in closed:
        reason = str(trade["exit_reason"])
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    std = returns.std(ddof=0)
    result: dict[str, object] = {
        **asdict(spec),
        "return": float(equity_curve.iloc[-1] - 1.0),
        "max_dd": float(drawdown.min()),
        "sharpe": 0.0 if std == 0.0 else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR)),
        "trades": len(closed),
        "win_rate": float((pnl_values > 0).mean()) if len(pnl_values) else 0.0,
        "avg_trade_pct": float(pnl_values.mean()) if len(pnl_values) else 0.0,
        "median_trade_pct": float(np.median(pnl_values)) if len(pnl_values) else 0.0,
        "best_trade_pct": float(pnl_values.max()) if len(pnl_values) else 0.0,
        "worst_trade_pct": float(pnl_values.min()) if len(pnl_values) else 0.0,
        "avg_hold_bars": float(hold_values.mean()) if len(hold_values) else 0.0,
        "median_hold_bars": float(np.median(hold_values)) if len(hold_values) else 0.0,
        "avg_allocation": float(allocation_values.mean()) if len(allocation_values) else 0.0,
        "max_allocation": float(allocation_values.max()) if len(allocation_values) else 0.0,
        "exit_reasons": exit_reasons,
        "fitness": float((equity_curve.iloc[-1] - 1.0) + drawdown.min() * 1.5),
    }
    if collect_trades:
        result["trades_detail"] = closed
    return result


def summarize_windows(frame: pd.DataFrame, spec: V7Spec) -> list[dict[str, object]]:
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    windows = {
        "1w": end_ts - pd.Timedelta(days=7),
        "1m": end_ts - pd.Timedelta(days=30),
        "3m": end_ts - pd.Timedelta(days=90),
        "6m": end_ts - pd.Timedelta(days=180),
        "1y": end_ts - pd.Timedelta(days=365),
        "full": None,
    }
    rows = []
    for label, start_ts in windows.items():
        row = run_v7(frame, spec, start_ts=start_ts)
        rows.append(
            {
                "window": label,
                "return": row["return"],
                "max_dd": row["max_dd"],
                "sharpe": row["sharpe"],
                "trades": row["trades"],
                "win_rate": row["win_rate"],
                "avg_trade_pct": row["avg_trade_pct"],
                "exit_reasons": row["exit_reasons"],
            }
        )
    return rows


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_volume_features(build_features(raw))
    specs = build_v7_specs()
    rankings = [run_v7(frame, spec) for spec in specs]
    ranking_frame = pd.DataFrame(rankings).sort_values(
        ["fitness", "return", "sharpe"],
        ascending=False,
    )
    viable = ranking_frame[ranking_frame.trades >= 15]
    top_name = str((viable if len(viable) else ranking_frame).iloc[0]["name"])
    top_spec = next(spec for spec in specs if spec.name == top_name)
    top_result = run_v7(frame, top_spec, collect_trades=True)
    top_trades = pd.DataFrame(top_result.pop("trades_detail"))

    v6_variant = Variant(
        "V6_dynamic_3x",
        "v2_regime",
        "adx_exit",
        stop_atr=9.0,
        adx_exit=22,
        adx_exit_bars=3,
    )
    v6 = run_variant_dynamic_3x(frame, v6_variant)
    report = {
        "data": {
            "start": str(pd.Timestamp(frame.ts.iloc[0])),
            "end": str(pd.Timestamp(frame.ts.iloc[-1])),
            "bars": int(len(frame)),
        },
        "v6_baseline": v6,
        "top_v7": top_result,
        "top_v7_windows": summarize_windows(frame, top_spec),
        "ranking_top20": ranking_frame.head(20).to_dict(orient="records"),
        "notes": [
            "V7 entry: EMA96/384 cross regime window + RVOL + candle/flow confirmation.",
            "V7 exit: no fixed take-profit; closes after MFE threshold when volume exhaustion persists.",
            "Fallback exits are hard stop and opposite EMA cross.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    ranking_frame.to_csv(RANKING_PATH, index=False)
    top_trades.to_csv(TOP_TRADES_PATH, index=False)

    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"top_trades={TOP_TRADES_PATH}")
    print(
        "top="
        f"{top_result['name']} return={top_result['return']:.4f} "
        f"dd={top_result['max_dd']:.4f} trades={top_result['trades']} "
        f"win={top_result['win_rate']:.4f}"
    )
    print(
        "v6="
        f"return={v6['return']:.4f} dd={v6['max_dd']:.4f} "
        f"trades={v6['trades']} win={v6['win_rate']:.4f}"
    )


if __name__ == "__main__":
    main()
