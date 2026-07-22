from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_mu_v35_session_aware as legacy  # noqa: E402
from mu_hype_xfer_kernel import build_features  # noqa: E402


ARTIFACT_DIR = ROOT / "research/mu/artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "mu_v14_latest_strict_audit.json"
TRADES_PATH = ARTIFACT_DIR / "mu_v14_latest_strict_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / "mu_v14_latest_strict_equity.csv"
DATA_QUALITY_PATH = ARTIFACT_DIR / "mu_binance_15m_data_quality_latest.json"
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
SYMBOL_FILE = "symbol=mu_usdt_usdt.parquet"
OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)

VERSION = "MU-HYPE-XFER experimental V14"
SELECTION_END = pd.Timestamp("2026-06-17T05:45:00Z")
WARMUP_BARS = 1600
ALLOCATION = 3.0
TAKE_PROFIT_ATR = 10.0
HARD_STOP_ATR = 9.0
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0004
PERIODS_PER_YEAR = 365 * 24 * 4

WINDOWS: dict[str, pd.Timedelta | None] = {
    "1D": pd.Timedelta(days=1),
    "7D": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=183),
    "1Y": pd.Timedelta(days=365),
    "ALL": None,
}


@dataclass(frozen=True, slots=True)
class StrictSpec:
    allocation: float = ALLOCATION
    take_profit_atr: float = TAKE_PROFIT_ATR
    hard_stop_atr: float = HARD_STOP_ATR
    fee_rate: float = FEE_RATE
    slippage_rate: float = SLIPPAGE_RATE


def pct(value: float) -> float:
    return round(100.0 * value, 4)


def load_data_quality() -> dict[str, Any]:
    if not DATA_QUALITY_PATH.exists():
        raise FileNotFoundError(
            f"Run refresh_and_audit_mu_binance_15m.py first: {DATA_QUALITY_PATH}"
        )
    return json.loads(DATA_QUALITY_PATH.read_text(encoding="utf-8"))


def build_research_frame(raw: pd.DataFrame) -> pd.DataFrame:
    return legacy.add_signal_columns(legacy.add_session_features(build_features(raw)))


def load_ohlcv_for_audit() -> tuple[pd.DataFrame, dict[str, Any]]:
    files = sorted(OHLCV_ROOT.rglob(SYMBOL_FILE))
    if not files:
        raise FileNotFoundError(f"No {SYMBOL_FILE} OHLCV files under {OHLCV_ROOT}")
    frames: list[pd.DataFrame] = []
    partition_mismatch_rows = 0
    for path in files:
        frame = pd.read_parquet(
            path,
            columns=[
                "ts",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
                "is_closed",
                "source",
            ],
        )
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        expected_partition = path.parent.name.removeprefix("date=")
        partition_mismatch_rows += int(
            frame["ts"].dt.date.astype(str).ne(expected_partition).sum()
        )
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    duplicate_rows = int(combined.duplicated("ts", keep=False).sum())
    if duplicate_rows or partition_mismatch_rows:
        raise RuntimeError(
            "Refusing ambiguous MU OHLCV consumer view: "
            f"duplicate_rows={duplicate_rows}, "
            f"partition_mismatch_rows={partition_mismatch_rows}"
        )
    combined = combined.sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(
        combined["ts"].iloc[0], combined["ts"].iloc[-1], freq="15min"
    )
    missing = expected.difference(pd.DatetimeIndex(combined["ts"]))
    if len(missing):
        raise RuntimeError(f"MU OHLCV consumer view has {len(missing)} missing bars")
    if not combined["is_closed"].all():
        raise RuntimeError("MU OHLCV consumer view contains unclosed bars")
    for column in ["open", "high", "low", "close", "volume"]:
        combined[column] = combined[column].astype("float64")
    return combined, {
        "files": len(files),
        "rows": int(len(combined)),
        "first_ts": combined["ts"].iloc[0].isoformat(),
        "last_ts": combined["ts"].iloc[-1].isoformat(),
        "duplicate_rows": duplicate_rows,
        "partition_mismatch_rows": partition_mismatch_rows,
        "missing_bars": int(len(missing)),
    }


def load_funding_for_audit() -> tuple[pd.DataFrame, dict[str, Any]]:
    files = sorted(FUNDING_ROOT.rglob(SYMBOL_FILE))
    if not files:
        raise FileNotFoundError(f"No {SYMBOL_FILE} funding files under {FUNDING_ROOT}")
    events = pd.concat(
        [
            pd.read_parquet(path, columns=["ts", "funding_rate"])
            for path in files
        ],
        ignore_index=True,
    )
    events["ts"] = pd.to_datetime(events["ts"], utc=True)
    events["funding_rate"] = events["funding_rate"].astype("float64")
    events = events.drop_duplicates(["ts", "funding_rate"]).sort_values("ts")
    events["bar_ts"] = events["ts"].dt.floor("15min")
    counts = events.groupby("bar_ts").size()
    by_bar = (
        events.groupby("bar_ts", as_index=False)["funding_rate"]
        .sum()
        .rename(columns={"bar_ts": "ts"})
        .sort_values("ts")
        .reset_index(drop=True)
    )
    return by_bar, {
        "event_rows": int(len(events)),
        "funding_bars": int(len(by_bar)),
        "multi_event_bars": int((counts > 1).sum()),
        "max_events_in_one_bar": int(counts.max()),
        "aggregation": "sum all funding events after flooring to their 15m bar",
    }


def causality_audit(raw: pd.DataFrame, full: pd.DataFrame) -> dict[str, Any]:
    columns = [
        "ema96",
        "ema384",
        "atr_pct672",
        "h1_ema_spread",
        "h4_ema_spread",
        "v6_long_trend_state",
        "v6_long_signal",
    ]
    checkpoints = sorted(
        {
            max(WARMUP_BARS + 1, int(len(raw) * fraction))
            for fraction in (0.5, 0.75, 0.9)
            if max(WARMUP_BARS + 1, int(len(raw) * fraction)) < len(raw)
        }
    )
    mismatches: list[dict[str, Any]] = []
    for stop in checkpoints:
        prefix = build_research_frame(raw.iloc[: stop + 1].copy())
        for column in columns:
            expected = full[column].iloc[stop]
            observed = prefix[column].iloc[-1]
            if pd.isna(expected) and pd.isna(observed):
                continue
            if isinstance(expected, (bool, np.bool_)):
                equal = bool(expected) == bool(observed)
            else:
                equal = bool(
                    np.isclose(
                        float(expected),
                        float(observed),
                        rtol=0.0,
                        atol=1e-12,
                        equal_nan=True,
                    )
                )
            if not equal:
                mismatches.append(
                    {
                        "checkpoint": str(pd.Timestamp(raw["ts"].iloc[stop])),
                        "column": column,
                        "full": str(expected),
                        "prefix": str(observed),
                    }
                )
    return {
        "checkpoints": [
            str(pd.Timestamp(raw["ts"].iloc[index])) for index in checkpoints
        ],
        "columns": columns,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "pass": not mismatches,
    }


def strict_backtest(
    frame: pd.DataFrame,
    funding_rates: np.ndarray,
    *,
    start_i: int,
    end_i: int | None = None,
    spec: StrictSpec = StrictSpec(),
) -> dict[str, Any]:
    end_i = len(frame) - 1 if end_i is None else end_i
    if start_i >= end_i:
        raise ValueError(f"Invalid audit interval: start_i={start_i}, end_i={end_i}")

    ts = pd.to_datetime(frame["ts"], utc=True)
    open_ = frame["open"].to_numpy(dtype="float64")
    high = frame["high"].to_numpy(dtype="float64")
    low = frame["low"].to_numpy(dtype="float64")
    close = frame["close"].to_numpy(dtype="float64")
    signal = frame["v6_long_signal"].fillna(False).to_numpy(dtype=bool)
    trend = frame["v6_long_trend_state"].fillna(False).to_numpy(dtype=bool)
    atr = frame["atr_pct672"].to_numpy(dtype="float64")

    equity = 1.0
    position = False
    pending_entry = False
    pending_indicator_exit = False
    entry_i = -1
    entry_price = np.nan
    entry_atr = np.nan
    entry_equity = np.nan
    allocation = 0.0
    last_mark = np.nan
    fee_drag = 0.0
    funding_drag = 0.0
    intrabar_conflicts = 0
    gap_stops = 0
    gap_takes = 0
    trades: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []

    def close_position(i: int, fill_price: float, reason: str) -> None:
        nonlocal equity, position, pending_entry, pending_indicator_exit
        nonlocal entry_i, entry_price, entry_atr, entry_equity
        nonlocal allocation, last_mark, fee_drag

        equity *= 1.0 + allocation * (fill_price / last_mark - 1.0)
        fee_multiplier = 1.0 - spec.fee_rate * allocation
        equity_before_fee = equity
        equity *= fee_multiplier
        fee_drag += equity_before_fee - equity
        trade_return = equity / entry_equity - 1.0
        trades.append(
            {
                "entry_ts": str(pd.Timestamp(ts.iloc[entry_i])),
                "exit_ts": str(pd.Timestamp(ts.iloc[i])),
                "entry_price": float(entry_price),
                "exit_price": float(fill_price),
                "entry_atr_pct": float(entry_atr),
                "allocation": float(allocation),
                "bars_held": int(i - entry_i + 1),
                "exit_reason": reason,
                "trade_return_pct": pct(trade_return),
                "equity_after": float(equity),
            }
        )
        position = False
        pending_entry = False
        pending_indicator_exit = False
        entry_i = -1
        entry_price = np.nan
        entry_atr = np.nan
        entry_equity = np.nan
        allocation = 0.0
        last_mark = np.nan

    for i in range(start_i, end_i + 1):
        exited_this_bar = False
        if position:
            equity *= 1.0 + allocation * (open_[i] / last_mark - 1.0)
            last_mark = open_[i]
            rate = float(funding_rates[i])
            if rate != 0.0:
                funding_multiplier = 1.0 - allocation * rate
                before_funding = equity
                equity *= funding_multiplier
                funding_drag += before_funding - equity

            if pending_indicator_exit:
                close_position(
                    i,
                    open_[i] * (1.0 - spec.slippage_rate),
                    "indicator_exit_next_open",
                )
                exited_this_bar = True

        if pending_entry and not position and not exited_this_bar:
            pending_entry = False
            if np.isfinite(atr[i - 1]) and atr[i - 1] > 0.0:
                position = True
                allocation = spec.allocation
                entry_i = i
                entry_atr = float(atr[i - 1])
                entry_price = float(open_[i] * (1.0 + spec.slippage_rate))
                entry_equity = float(equity)
                last_mark = entry_price
                fee_multiplier = 1.0 - spec.fee_rate * allocation
                before_fee = equity
                equity *= fee_multiplier
                fee_drag += before_fee - equity

        if position:
            stop_price = entry_price * (1.0 - spec.hard_stop_atr * entry_atr)
            take_price = entry_price * (1.0 + spec.take_profit_atr * entry_atr)

            if open_[i] <= stop_price:
                gap_stops += 1
                close_position(
                    i,
                    open_[i] * (1.0 - spec.slippage_rate),
                    "gap_stop_open",
                )
                exited_this_bar = True
            elif open_[i] >= take_price:
                gap_takes += 1
                close_position(
                    i,
                    take_price * (1.0 - spec.slippage_rate),
                    "gap_take_capped_at_target",
                )
                exited_this_bar = True
            else:
                hit_stop = low[i] <= stop_price
                hit_take = high[i] >= take_price
                if hit_stop and hit_take:
                    intrabar_conflicts += 1
                    close_position(
                        i,
                        stop_price * (1.0 - spec.slippage_rate),
                        "same_bar_conflict_stop_first",
                    )
                    exited_this_bar = True
                elif hit_stop:
                    close_position(
                        i,
                        stop_price * (1.0 - spec.slippage_rate),
                        "stop_loss",
                    )
                    exited_this_bar = True
                elif hit_take:
                    close_position(
                        i,
                        take_price * (1.0 - spec.slippage_rate),
                        "take_profit",
                    )
                    exited_this_bar = True

        if position:
            equity *= 1.0 + allocation * (close[i] / last_mark - 1.0)
            last_mark = close[i]
            if not trend[i]:
                pending_indicator_exit = True

        if not position and not exited_this_bar and signal[i]:
            pending_entry = True

        if not np.isfinite(equity) or equity <= 0.0:
            raise RuntimeError(
                "V14 equity became non-positive/non-finite; liquidation is not "
                f"modeled safely at {pd.Timestamp(ts.iloc[i])}"
            )
        curve.append(
            {
                "ts": ts.iloc[i],
                "equity": float(equity),
                "position": int(position),
            }
        )

    equity_frame = pd.DataFrame(curve)
    equity_series = equity_frame.set_index("ts")["equity"]
    returns = equity_series.pct_change().fillna(0.0)
    drawdown = equity_series / equity_series.cummax() - 1.0
    trade_returns = np.array(
        [float(trade["trade_return_pct"]) / 100.0 for trade in trades],
        dtype="float64",
    )
    std = float(returns.std(ddof=0))
    return {
        "start": str(pd.Timestamp(ts.iloc[start_i])),
        "end": str(pd.Timestamp(ts.iloc[end_i])),
        "start_i": int(start_i),
        "end_i": int(end_i),
        "return": float(equity_series.iloc[-1] - 1.0),
        "max_drawdown": float(drawdown.min()),
        "sharpe": (
            0.0
            if std == 0.0
            else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR))
        ),
        "closed_trades": len(trades),
        "win_rate": (
            float((trade_returns > 0.0).mean()) if len(trade_returns) else 0.0
        ),
        "open_position_at_end": bool(position),
        "minimum_equity": float(equity_series.min()),
        "intrabar_conflicts": intrabar_conflicts,
        "gap_stops": gap_stops,
        "gap_takes": gap_takes,
        "fee_drag_equity": float(fee_drag),
        "funding_drag_equity": float(funding_drag),
        "trades": trades,
        "equity_curve": equity_frame,
    }


def buy_hold_metrics(
    frame: pd.DataFrame,
    *,
    start_i: int,
    end_i: int,
) -> dict[str, float]:
    entry = float(frame["open"].iloc[start_i]) * (1.0 + SLIPPAGE_RATE)
    marks = frame["close"].iloc[start_i : end_i + 1].astype("float64") / entry
    equity = marks * (1.0 - FEE_RATE)
    final_exit = float(frame["close"].iloc[end_i]) * (1.0 - SLIPPAGE_RATE)
    final_equity = (
        final_exit / entry * (1.0 - FEE_RATE) * (1.0 - FEE_RATE)
    )
    equity.iloc[-1] = final_equity
    drawdown = equity / equity.cummax() - 1.0
    return {
        "return": float(final_equity - 1.0),
        "max_drawdown": float(drawdown.min()),
    }


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for trade in result["trades"]:
        reason = str(trade["exit_reason"])
        counts[reason] = counts.get(reason, 0) + 1
    return {
        "start": result["start"],
        "end": result["end"],
        "return_pct": pct(result["return"]),
        "max_drawdown_pct": pct(result["max_drawdown"]),
        "sharpe": round(float(result["sharpe"]), 4),
        "closed_trades": int(result["closed_trades"]),
        "win_rate_pct": pct(result["win_rate"]),
        "open_position_at_end": bool(result["open_position_at_end"]),
        "minimum_equity": round(float(result["minimum_equity"]), 8),
        "exit_reasons": counts,
        "intrabar_conflicts": int(result["intrabar_conflicts"]),
        "gap_stops": int(result["gap_stops"]),
        "gap_takes": int(result["gap_takes"]),
        "fee_drag_equity": round(float(result["fee_drag_equity"]), 8),
        "funding_drag_equity": round(float(result["funding_drag_equity"]), 8),
    }


def main() -> None:
    data_quality = load_data_quality()
    if data_quality["ohlcv_quality"]["blocker_count"] != 0:
        raise RuntimeError("Refusing to backtest data with OHLCV quality blockers")
    if data_quality["funding_quality"]["blocker_count"] != 0:
        raise RuntimeError("Refusing to backtest data with funding quality blockers")

    raw, ohlcv_consumer_view = load_ohlcv_for_audit()
    funding, funding_alignment = load_funding_for_audit()
    frame = build_research_frame(raw)
    aligned_funding = legacy.align_funding(frame, funding)
    if len(frame) <= WARMUP_BARS:
        raise RuntimeError(f"Insufficient MU history for {WARMUP_BARS} warmup bars")

    causal = causality_audit(raw, frame)
    if not causal["pass"]:
        raise RuntimeError(f"Feature causality audit failed: {causal}")

    earliest_i = WARMUP_BARS
    end_i = len(frame) - 1
    end_ts = pd.Timestamp(frame["ts"].iloc[end_i])
    window_results: dict[str, Any] = {}
    all_trades: list[dict[str, Any]] = []
    equity_frames: list[pd.DataFrame] = []
    for label, delta in WINDOWS.items():
        requested_start = (
            pd.Timestamp(frame["ts"].iloc[earliest_i])
            if delta is None
            else end_ts - delta
        )
        candidates = np.flatnonzero(
            (pd.to_datetime(frame["ts"], utc=True) >= requested_start).to_numpy()
        )
        start_i = max(earliest_i, int(candidates[0])) if len(candidates) else earliest_i
        result = strict_backtest(
            frame,
            aligned_funding,
            start_i=start_i,
            end_i=end_i,
        )
        benchmark = buy_hold_metrics(frame, start_i=start_i, end_i=end_i)
        coverage_complete = delta is None or pd.Timestamp(
            frame["ts"].iloc[earliest_i]
        ) <= requested_start
        window_results[label] = {
            **compact_result(result),
            "coverage_complete": bool(coverage_complete),
            "requested_start": str(requested_start),
            "buy_hold_return_pct": pct(benchmark["return"]),
            "buy_hold_max_drawdown_pct": pct(benchmark["max_drawdown"]),
            "excess_return_vs_buy_hold_pct": round(
                pct(result["return"]) - pct(benchmark["return"]), 4
            ),
        }
        for trade in result["trades"]:
            all_trades.append({"window": label, **trade})
        equity = result["equity_curve"].copy()
        equity["window"] = label
        equity_frames.append(equity)

    selection_candidates = np.flatnonzero(
        (pd.to_datetime(frame["ts"], utc=True) <= SELECTION_END).to_numpy()
    )
    if not len(selection_candidates):
        raise RuntimeError("Selection-period endpoint is absent from MU data")
    selection_end_i = int(selection_candidates[-1])
    selection_result = strict_backtest(
        frame,
        aligned_funding,
        start_i=earliest_i,
        end_i=selection_end_i,
    )
    forward_start_i = selection_end_i + 1
    forward_result = strict_backtest(
        frame,
        aligned_funding,
        start_i=forward_start_i,
        end_i=end_i,
    )
    selection_benchmark = buy_hold_metrics(
        frame,
        start_i=earliest_i,
        end_i=selection_end_i,
    )
    forward_benchmark = buy_hold_metrics(
        frame,
        start_i=forward_start_i,
        end_i=end_i,
    )

    legacy_v14_spec = legacy.ResearchSpec(
        name="time_v6_long_tp10_sl9_max3",
        signal_column="v6_long_signal",
        atr_column="atr_pct672",
        trend_column="v6_long_trend_state",
        entry_gate_column="always_entry_gate",
        max_allocation=3.0,
    )
    legacy_result = legacy.run_research_spec(
        frame,
        legacy_v14_spec,
        start_i=earliest_i,
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "version": VERSION,
            "status": "explore / not promoted / not live-ready",
            "symbol": "MUUSDT",
            "market": "Binance USD-M TRADIFI_PERPETUAL",
            "timeframe": "15m",
            "direction": "long-only",
            "entry_session": "all Binance 15m bars",
            "allocation": ALLOCATION,
            "take_profit_atr": TAKE_PROFIT_ATR,
            "hard_stop_atr": HARD_STOP_ATR,
            "signal_identity": (
                "historical v6 label; actual entry is v6_variant.entry=v2_regime"
            ),
            "exit_identity": (
                "ema_spread > 0 trend state plus TP10/SL9; v6_variant adx_exit is "
                "not used by the V14 research engine"
            ),
            "sizing_identity": "fixed 3x; not dynamic V6 sizing",
        },
        "data": {
            "rows": int(len(frame)),
            "start": str(pd.Timestamp(frame["ts"].iloc[0])),
            "end": str(pd.Timestamp(frame["ts"].iloc[-1])),
            "warmup_bars": WARMUP_BARS,
            "backtest_start_after_warmup": str(
                pd.Timestamp(frame["ts"].iloc[earliest_i])
            ),
            "selection_end": str(SELECTION_END),
            "data_quality_artifact": str(DATA_QUALITY_PATH.relative_to(ROOT)),
            "ohlcv_consumer_view": ohlcv_consumer_view,
            "funding_alignment": funding_alignment,
        },
        "strict_execution_model": {
            "signal_timing": "closed 15m bar signal; next 15m open entry",
            "higher_timeframe_timing": "1h/4h features shifted by one completed HTF bar",
            "indicator_exit": "decision on close; next 15m open market exit",
            "same_bar_tp_sl": "stop-first",
            "gap_stop": "next observed open with adverse slippage",
            "take_profit": "target price with adverse slippage; gap upside capped at target",
            "fee_per_fill": FEE_RATE,
            "adverse_slippage_per_fill": SLIPPAGE_RATE,
            "funding": "actual Binance funding applied to positions carried into funding bar",
            "insolvency": "fail closed if equity becomes non-positive; liquidation is not approximated",
        },
        "causality_audit": causal,
        "windows": window_results,
        "selection_period_strict": {
            **compact_result(selection_result),
            "buy_hold_return_pct": pct(selection_benchmark["return"]),
            "buy_hold_max_drawdown_pct": pct(selection_benchmark["max_drawdown"]),
        },
        "new_data_forward_extension_strict": {
            **compact_result(forward_result),
            "buy_hold_return_pct": pct(forward_benchmark["return"]),
            "buy_hold_max_drawdown_pct": pct(forward_benchmark["max_drawdown"]),
        },
        "legacy_full_window_for_comparison": {
            "return_pct": pct(legacy_result["return"]),
            "max_drawdown_pct": pct(legacy_result["max_dd"]),
            "closed_trades": int(legacy_result["closed_trades"]),
            "win_rate_pct": pct(legacy_result["win_rate"]),
            "warning": (
                "Legacy model omits funding for V1-V14, checks TP before SL, and "
                "does not gap-adjust stop fills; it is not validity evidence."
            ),
        },
        "limitations": [
            "MUUSDT history starts in April 2026, so complete 6M and 1Y slices are unavailable.",
            "The natural forward extension is only about one month and can contain very few trades.",
            "15m OHLC cannot identify true intrabar TP/SL ordering; this audit uses stop-first.",
            "No order-book depth, realized market impact, borrow, liquidation, or runner parity evidence is available.",
            "This audit is not a promotion review and does not satisfy OOS/CPCV/Monte Carlo/stress/phase gates.",
            "The historical 'V6' label is only an alias: V14 does not reproduce the full dynamic-sizing/ADX-exit V6 state machine.",
        ],
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(all_trades).to_csv(TRADES_PATH, index=False)
    pd.concat(equity_frames, ignore_index=True).to_csv(EQUITY_PATH, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
