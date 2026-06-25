from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import entry_signal
from research_hype_ema_cross_strategy import (
    PERIODS_PER_YEAR,
    SLIPPAGE,
    TRADE_COST,
    build_features,
    rsi,
)
from research_hype_ema_regime_hold_v5 import dynamic_allocation, load_hype_data_lake, run_variant_dynamic_3x
from research_hype_ema_volume_exhaustion_v7 import V7Spec, add_volume_features, exhaustion_masks
from research_hype_ema_volume_overlay_v8 import V8Spec, run_v8, v6_variant
from research_hype_ema_htf_rsi_exit_v9 import v8_clean_spec


REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_oscillator_top_exit_v10.json")
RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_oscillator_top_exit_v10_ranking.csv")
TOP_TRADES_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_oscillator_top_exit_v10_top_trades.csv")


@dataclass(frozen=True, slots=True)
class V10Spec:
    name: str
    base_mode: str
    osc_tf: str
    min_score: int
    min_mfe_atr: float
    long_rsi_arm: float
    long_rsi_exit: float
    short_rsi_arm: float
    short_rsi_exit: float
    kdj_j_high: float
    kdj_j_low: float
    kdj_drop: float
    macd_bars: int
    wick_min: float = 0.55
    exit_rvol: float = 2.0
    stop_atr: float = 9.0
    adx_exit: float = 22.0
    adx_exit_bars: int = 3


def add_htf_oscillator_features(frame: pd.DataFrame, rule: str, prefix: str) -> pd.DataFrame:
    ohlcv = (
        frame.set_index("ts")[["open", "high", "low", "close", "volume"]]
        .resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    low9 = ohlcv.low.rolling(9, min_periods=9).min()
    high9 = ohlcv.high.rolling(9, min_periods=9).max()
    rsv = 100 * (ohlcv.close - low9) / (high9 - low9).replace(0.0, np.nan)
    k = rsv.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    d = k.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    macd = ohlcv.close.ewm(span=12, adjust=False, min_periods=12).mean() - ohlcv.close.ewm(
        span=26, adjust=False, min_periods=26
    ).mean()
    macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    hist = macd - macd_signal
    hist_down = (hist.diff() < 0).astype(float)
    hist_up = (hist.diff() > 0).astype(float)
    htf = pd.DataFrame(index=ohlcv.index)
    htf[f"{prefix}_rsi14_osc"] = rsi(ohlcv.close, 14)
    htf[f"{prefix}_kdj_k"] = k
    htf[f"{prefix}_kdj_d"] = d
    htf[f"{prefix}_kdj_j"] = 3 * k - 2 * d
    htf[f"{prefix}_macd_hist"] = hist
    htf[f"{prefix}_macd_down2"] = hist_down.rolling(2, min_periods=2).sum()
    htf[f"{prefix}_macd_down3"] = hist_down.rolling(3, min_periods=3).sum()
    htf[f"{prefix}_macd_up2"] = hist_up.rolling(2, min_periods=2).sum()
    htf[f"{prefix}_macd_up3"] = hist_up.rolling(3, min_periods=3).sum()
    aligned = htf.shift(1).reindex(pd.DatetimeIndex(frame.ts), method="ffill")
    return aligned.reset_index(drop=True)


def add_oscillator_features(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(
        [
            frame,
            add_htf_oscillator_features(frame, "1h", "h1"),
            add_htf_oscillator_features(frame, "4h", "h4"),
        ],
        axis=1,
    )


def build_v10_specs() -> list[V10Spec]:
    rsi_sets = [(70, 60, 30, 40), (72, 65, 28, 35), (75, 68, 25, 32)]
    specs: list[V10Spec] = []
    for base_mode in ("osc_combo_only", "v8_clean_plus_combo"):
        for osc_tf in ("h1", "h4"):
            for min_score in (2, 3):
                for min_mfe_atr in (2.0, 4.0):
                    for long_arm, long_exit, short_arm, short_exit in rsi_sets:
                        for kdj_j_high, kdj_j_low in ((100, 0), (110, -10)):
                            for macd_bars in (2, 3):
                                name = (
                                    f"V10_{base_mode}_{osc_tf}_score{min_score}_mfe{min_mfe_atr:g}"
                                    f"_rsi{long_arm}_{long_exit}_{short_arm}_{short_exit}"
                                    f"_j{kdj_j_high:g}_{kdj_j_low:g}_macd{macd_bars}"
                                )
                                specs.append(
                                    V10Spec(
                                        name=name,
                                        base_mode=base_mode,
                                        osc_tf=osc_tf,
                                        min_score=min_score,
                                        min_mfe_atr=min_mfe_atr,
                                        long_rsi_arm=long_arm,
                                        long_rsi_exit=long_exit,
                                        short_rsi_arm=short_arm,
                                        short_rsi_exit=short_exit,
                                        kdj_j_high=kdj_j_high,
                                        kdj_j_low=kdj_j_low,
                                        kdj_drop=10.0,
                                        macd_bars=macd_bars,
                                    )
                                )
    return specs


def metric_result(spec: V10Spec, equity_curve: pd.Series, trades: list[dict[str, object]], *, collect_trades: bool) -> dict[str, object]:
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype=float)
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
        "exit_reasons": exit_reasons,
        "fitness": float((equity_curve.iloc[-1] - 1.0) + drawdown.min() * 1.5),
    }
    if collect_trades:
        result["trades_detail"] = closed
    return result


def run_v10(frame: pd.DataFrame, spec: V10Spec, *, start_ts: pd.Timestamp | None = None, collect_trades: bool = False) -> dict[str, object]:
    ts_series = pd.to_datetime(frame.ts, utc=True)
    start_i = 0 if start_ts is None else int(np.flatnonzero(ts_series >= start_ts)[0])
    ts = ts_series.to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    spread = frame.ema_spread.to_numpy("float64")
    previous_spread = np.r_[np.nan, spread[:-1]]
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")
    rsi_values = frame[f"{spec.osc_tf}_rsi14_osc"].to_numpy("float64")
    kdj_j = frame[f"{spec.osc_tf}_kdj_j"].to_numpy("float64")
    macd_down = frame[f"{spec.osc_tf}_macd_down{spec.macd_bars}"].to_numpy("float64")
    macd_up = frame[f"{spec.osc_tf}_macd_up{spec.macd_bars}"].to_numpy("float64")
    price_edge_long = high >= frame.price_high96.shift(1).to_numpy("float64")
    price_edge_short = low <= frame.price_low96.shift(1).to_numpy("float64")
    signal = entry_signal(frame, v6_variant())
    exhaust_long, exhaust_short = exhaustion_masks(
        frame,
        V7Spec(
            name=spec.name,
            entry_window=0,
            entry_rvol=0.0,
            entry_mode="price",
            exit_rvol=spec.exit_rvol,
            wick_min=spec.wick_min,
            fail_bars=1,
            min_mfe_atr=spec.min_mfe_atr,
            invalid_bars=0,
        ),
    )

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = 0
    hold_bars = 0
    bad_bars = 0
    fail_bars = 0
    mfe_atr = 0.0
    rsi_armed = False
    kdj_armed = False
    trades: list[dict[str, object]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str, score: int = 0) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark
        nonlocal hold_bars, bad_bars, fail_bars, mfe_atr, rsi_armed, kdj_armed
        equity *= 1 + allocation * pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST * allocation
        raw_pnl = pos * (price / entry_px - 1)
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(allocation * raw_pnl),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "osc_score": int(score),
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
        bad_bars = 0
        fail_bars = 0
        mfe_atr = 0.0
        rsi_armed = False
        kdj_armed = False

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
                mfe_atr = max(
                    mfe_atr,
                    (high[i] / entry_px - 1) / entry_atr if pos > 0 else (1 - low[i] / entry_px) / entry_atr,
                )
                stop_px = entry_px * (1 - pos * spec.stop_atr * entry_atr)
                if (low[i] <= stop_px if pos > 0 else high[i] >= stop_px):
                    px = stop_px * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(i, px, "stop_loss")
                    curve.append(float(equity))
                    continue

            equity *= 1 + allocation * pos * (close[i] / last_mark - 1)
            last_mark = close[i]

            if np.isfinite(rsi_values[i]):
                if pos > 0 and rsi_values[i] >= spec.long_rsi_arm:
                    rsi_armed = True
                if pos < 0 and rsi_values[i] <= spec.short_rsi_arm:
                    rsi_armed = True
            if np.isfinite(kdj_j[i]):
                if pos > 0 and kdj_j[i] >= spec.kdj_j_high:
                    kdj_armed = True
                if pos < 0 and kdj_j[i] <= spec.kdj_j_low:
                    kdj_armed = True

            edge = bool(price_edge_long[i] if pos > 0 else price_edge_short[i])
            if mfe_atr >= spec.min_mfe_atr and edge:
                rsi_signal = bool(
                    rsi_armed
                    and np.isfinite(rsi_values[i])
                    and ((pos > 0 and rsi_values[i] <= spec.long_rsi_exit) or (pos < 0 and rsi_values[i] >= spec.short_rsi_exit))
                )
                previous_j = kdj_j[i - 1] if i > 0 else np.nan
                kdj_signal = bool(
                    kdj_armed
                    and np.isfinite(kdj_j[i])
                    and np.isfinite(previous_j)
                    and ((pos > 0 and previous_j - kdj_j[i] >= spec.kdj_drop) or (pos < 0 and kdj_j[i] - previous_j >= spec.kdj_drop))
                )
                macd_signal = bool((macd_down[i] >= spec.macd_bars) if pos > 0 else (macd_up[i] >= spec.macd_bars))
                volume_signal = bool(exhaust_long[i] if pos > 0 else exhaust_short[i])
                score = int(rsi_signal) + int(kdj_signal) + int(macd_signal) + int(volume_signal)
                if score >= spec.min_score:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, "oscillator_top_bottom", score)
                    curve.append(float(equity))
                    continue

            if spec.base_mode == "v8_clean_plus_combo":
                exhausted = (pos > 0 and exhaust_long[i]) or (pos < 0 and exhaust_short[i])
                fail_bars = fail_bars + 1 if exhausted and mfe_atr >= 4.0 else 0
                if fail_bars >= 1:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, "volume_exhaustion")
                    curve.append(float(equity))
                    continue

            opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (pos < 0 and spread[i] > 0 >= previous_spread[i])
            if opposite_cross:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "opposite_cross")
                curve.append(float(equity))
                continue

            trend_bad = bool(adx28[i] < spec.adx_exit)
            bad_bars = bad_bars + 1 if trend_bad else 0
            if bad_bars >= spec.adx_exit_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "trend_break")
                curve.append(float(equity))
                continue

        if not pos and signal[i]:
            pending_entry = int(signal[i])
        curve.append(float(equity))

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    return metric_result(spec, equity_curve, trades, collect_trades=collect_trades)


def main() -> None:
    frame = add_oscillator_features(add_volume_features(build_features(load_hype_data_lake())))
    specs = build_v10_specs()
    rankings = [run_v10(frame, spec) for spec in specs]
    ranking_frame = pd.DataFrame(rankings).sort_values(["fitness", "return", "sharpe"], ascending=False)
    top_spec = next(spec for spec in specs if spec.name == str(ranking_frame.iloc[0]["name"]))
    top_result = run_v10(frame, top_spec, collect_trades=True)
    top_trades = pd.DataFrame(top_result.pop("trades_detail"))
    v6 = run_variant_dynamic_3x(frame, v6_variant())
    v8_clean = run_v8(frame, v8_clean_spec())
    report = {
        "data": {"start": str(pd.Timestamp(frame.ts.iloc[0])), "end": str(pd.Timestamp(frame.ts.iloc[-1])), "bars": int(len(frame))},
        "v6_baseline": v6,
        "v8_clean_wick055": v8_clean,
        "top_v10": top_result,
        "ranking_top20": ranking_frame.head(20).to_dict(orient="records"),
        "notes": [
            "V10 tests RSI/KDJ/MACD/volume-wick short top/bottom exits.",
            "Exit requires price edge, MFE threshold, and at least min_score oscillator signals.",
            "HTF oscillator features are shifted one completed higher-timeframe bar before 15m alignment.",
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
        "v8_clean="
        f"return={v8_clean['return']:.4f} dd={v8_clean['max_dd']:.4f} "
        f"trades={v8_clean['trades']} win={v8_clean['win_rate']:.4f}"
    )


if __name__ == "__main__":
    main()
