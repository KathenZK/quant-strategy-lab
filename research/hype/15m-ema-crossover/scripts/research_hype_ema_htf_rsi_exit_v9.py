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
)
from research_hype_ema_regime_hold_v5 import (
    dynamic_allocation,
    load_hype_data_lake,
    run_variant_dynamic_3x,
)
from research_hype_ema_volume_exhaustion_v7 import V7Spec, add_volume_features, exhaustion_masks
from research_hype_ema_volume_overlay_v8 import V8Spec, run_v8, v6_variant


REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_htf_rsi_exit_v9.json")
RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_htf_rsi_exit_v9_ranking.csv")
TOP_TRADES_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_htf_rsi_exit_v9_top_trades.csv")


@dataclass(frozen=True, slots=True)
class V9Spec:
    name: str
    base_mode: str
    rsi_tf: str
    long_arm: float
    long_exit: float
    short_arm: float
    short_exit: float
    rsi_min_mfe_atr: float
    exit_rvol: float = 2.0
    min_mfe_atr: float = 4.0
    fail_bars: int = 1
    wick_min: float = 0.55
    stop_atr: float = 9.0
    adx_exit: float = 22.0
    adx_exit_bars: int = 3


def build_v9_specs() -> list[V9Spec]:
    rsi_pairs = [
        (70, 60, 30, 40),
        (70, 65, 30, 35),
        (72, 65, 28, 35),
        (75, 68, 25, 32),
    ]
    specs: list[V9Spec] = []
    for base_mode in ("v6_rsi", "v8_rsi", "v8_clean_rsi"):
        for rsi_tf in ("h1", "h4"):
            for long_arm, long_exit, short_arm, short_exit in rsi_pairs:
                for rsi_min_mfe_atr in (0.0, 2.0, 4.0):
                    wick_min = 0.55 if base_mode == "v8_clean_rsi" else 0.35
                    name = (
                        f"V9_{base_mode}_{rsi_tf}_L{long_arm}_{long_exit}"
                        f"_S{short_arm}_{short_exit}_mfe{rsi_min_mfe_atr:g}"
                    )
                    specs.append(
                        V9Spec(
                            name=name,
                            base_mode=base_mode,
                            rsi_tf=rsi_tf,
                            long_arm=long_arm,
                            long_exit=long_exit,
                            short_arm=short_arm,
                            short_exit=short_exit,
                            rsi_min_mfe_atr=rsi_min_mfe_atr,
                            wick_min=wick_min,
                        )
                    )
    return specs


def v8_baseline_spec() -> V8Spec:
    return V8Spec(
        name="V8_full_exit_xrv2_mfe4_fb1_cd0",
        action="full_exit",
        exit_rvol=2.0,
        min_mfe_atr=4.0,
        fail_bars=1,
        cooldown_bars=0,
        wick_min=0.35,
    )


def v8_clean_spec() -> V8Spec:
    return V8Spec(
        name="V8_clean_wick055",
        action="full_exit",
        exit_rvol=2.0,
        min_mfe_atr=4.0,
        fail_bars=1,
        cooldown_bars=0,
        wick_min=0.55,
    )


def metric_result(
    spec: V9Spec,
    equity_curve: pd.Series,
    trades: list[dict[str, object]],
    *,
    collect_trades: bool,
) -> dict[str, object]:
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype=float)
    hold_values = np.array([int(trade["hold_bars"]) for trade in closed], dtype=float)
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
        "exit_reasons": exit_reasons,
        "fitness": float((equity_curve.iloc[-1] - 1.0) + drawdown.min() * 1.5),
    }
    if collect_trades:
        result["trades_detail"] = closed
    return result


def run_v9(
    frame: pd.DataFrame,
    spec: V9Spec,
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
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")
    rsi = frame[f"{spec.rsi_tf}_rsi14"].to_numpy("float64")
    signal = entry_signal(frame, v6_variant())
    use_volume_exit = spec.base_mode in {"v8_rsi", "v8_clean_rsi"}
    exhaust_long, exhaust_short = exhaustion_masks(
        frame,
        V7Spec(
            name=spec.name,
            entry_window=0,
            entry_rvol=0.0,
            entry_mode="price",
            exit_rvol=spec.exit_rvol,
            wick_min=spec.wick_min,
            fail_bars=spec.fail_bars,
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
    trades: list[dict[str, object]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark
        nonlocal hold_bars, bad_bars, fail_bars, mfe_atr, rsi_armed
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
                "rsi_exit_tf": spec.rsi_tf,
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

            if np.isfinite(rsi[i]) and mfe_atr >= spec.rsi_min_mfe_atr:
                if pos > 0 and rsi[i] >= spec.long_arm:
                    rsi_armed = True
                elif pos < 0 and rsi[i] <= spec.short_arm:
                    rsi_armed = True
            rsi_exit = (
                rsi_armed
                and np.isfinite(rsi[i])
                and ((pos > 0 and rsi[i] <= spec.long_exit) or (pos < 0 and rsi[i] >= spec.short_exit))
            )
            if rsi_exit:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "htf_rsi_reversal")
                curve.append(float(equity))
                continue

            if use_volume_exit:
                exhausted = (pos > 0 and exhaust_long[i]) or (pos < 0 and exhaust_short[i])
                exhausted = exhausted and mfe_atr >= spec.min_mfe_atr and hold_bars >= 4
                fail_bars = fail_bars + 1 if exhausted else 0
                if fail_bars >= spec.fail_bars:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, "volume_exhaustion")
                    curve.append(float(equity))
                    continue

            opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (
                pos < 0 and spread[i] > 0 >= previous_spread[i]
            )
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
                "rsi_exit_tf": spec.rsi_tf,
                "exit_reason": "open_at_end",
                "equity_after": float(equity),
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    return metric_result(spec, equity_curve, trades, collect_trades=collect_trades)


def summarize_windows(frame: pd.DataFrame, spec: V9Spec) -> list[dict[str, object]]:
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    windows = {
        "1w": end_ts - pd.Timedelta(days=7),
        "1m": end_ts - pd.Timedelta(days=30),
        "3m": end_ts - pd.Timedelta(days=90),
        "6m": end_ts - pd.Timedelta(days=180),
        "1y": end_ts - pd.Timedelta(days=365),
        "full": None,
    }
    return [
        {
            "window": label,
            **{
                key: row[key]
                for key in ("return", "max_dd", "sharpe", "trades", "win_rate", "avg_trade_pct", "exit_reasons")
            },
        }
        for label, start_ts in windows.items()
        for row in [run_v9(frame, spec, start_ts=start_ts)]
    ]


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_volume_features(build_features(raw))
    specs = build_v9_specs()
    rankings = [run_v9(frame, spec) for spec in specs]
    ranking_frame = pd.DataFrame(rankings).sort_values(
        ["fitness", "return", "sharpe"],
        ascending=False,
    )
    top_name = str(ranking_frame.iloc[0]["name"])
    top_spec = next(spec for spec in specs if spec.name == top_name)
    top_result = run_v9(frame, top_spec, collect_trades=True)
    top_trades = pd.DataFrame(top_result.pop("trades_detail"))

    v6 = run_variant_dynamic_3x(frame, v6_variant())
    v8 = run_v8(frame, v8_baseline_spec())
    v8_clean = run_v8(frame, v8_clean_spec())
    report = {
        "data": {
            "start": str(pd.Timestamp(frame.ts.iloc[0])),
            "end": str(pd.Timestamp(frame.ts.iloc[-1])),
            "bars": int(len(frame)),
        },
        "v6_baseline": v6,
        "v8_baseline": v8,
        "v8_clean_wick055": v8_clean,
        "top_v9": top_result,
        "top_v9_windows": summarize_windows(frame, top_spec),
        "ranking_top20": ranking_frame.head(20).to_dict(orient="records"),
        "notes": [
            "V9 keeps 15m V6 entries and adds higher-timeframe RSI armed-then-reversal exits.",
            "base_mode v6_rsi disables volume exhaustion; v8_rsi and v8_clean_rsi keep V8 volume exhaustion overlay.",
            "h1/h4 RSI features are shifted one high-timeframe bar before aligning to 15m.",
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
