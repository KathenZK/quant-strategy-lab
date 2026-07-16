from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-candle-count-reversal"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
INTRABAR_PATH = (
    ROOT / "archive/code/platform/src/strategy_lab/strategies/candle_count_short/"
    "intrabar_backtest.py"
)
ARCHIVE_REPLAY_PATH = (
    ROOT / "archive/scripts/research/research_hype_v35_dry_run_recovery.py"
)
OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
RAW_OHLCV_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
MARK_ROOT = (
    ROOT / "data/normalized/mark_price_klines/exchange=binance/market_type=perp/"
    "timeframe=15m"
)
RAW_MARK_ROOT = (
    ROOT / "data/raw/mark_price_klines/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp/"
    "symbol=hype_usdt_usdt"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"
SELECTION_END = pd.Timestamp("2026-06-01T03:00:00Z")
HOLDOUT_START = SELECTION_END + pd.Timedelta(minutes=15)
FAST_SPANS = (24, 48, 96, 192)
SLOW_SPANS = (96, 192, 384, 672)
EMA_PAIRS = tuple(
    (fast, slow) for fast in FAST_SPANS for slow in SLOW_SPANS if fast < slow
)
SUMMARY_PATH = ARTIFACT_DIR / "hype_cc_v35_dual_ema_summary_2026-07-14.json"
GRID_PATH = ARTIFACT_DIR / "hype_cc_v35_dual_ema_grid_2026-07-14.csv"
OOS_PATH = ARTIFACT_DIR / "hype_cc_v35_dual_ema_oos_2026-07-14.csv"
RECENT_PATH = ARTIFACT_DIR / "hype_cc_v35_dual_ema_recent_2026-07-14.csv"
TRADES_PATH = ARTIFACT_DIR / "hype_cc_v35_dual_ema_selected_trades_2026-07-14.csv"
CURRENT_BASELINE = {
    "entries": 339,
    "return_pct": 7713.7113,
    "max_drawdown_pct": -33.2839,
    "sharpe": 4.5647,
}


def _load_replay_module():
    spec_b = importlib.util.spec_from_file_location(
        "strategy_lab.strategies.candle_count_short.intrabar_backtest",
        INTRABAR_PATH,
    )
    if spec_b is None or spec_b.loader is None:
        raise RuntimeError(f"cannot load intrabar replay module: {INTRABAR_PATH}")
    intrabar = importlib.util.module_from_spec(spec_b)
    sys.modules.setdefault(
        "strategy_lab.strategies", types.ModuleType("strategy_lab.strategies")
    )
    sys.modules.setdefault(
        "strategy_lab.strategies.candle_count_short",
        types.ModuleType("strategy_lab.strategies.candle_count_short"),
    )
    sys.modules["strategy_lab.strategies.candle_count_short.intrabar_backtest"] = (
        intrabar
    )
    spec_b.loader.exec_module(intrabar)

    spec = importlib.util.spec_from_file_location(
        "hype_cc_v35_replay_for_dual_ema", ARCHIVE_REPLAY_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load V35 replay module: {ARCHIVE_REPLAY_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_cc_v35_replay_for_dual_ema"] = module
    spec.loader.exec_module(module)
    return module


def _read_partitions(root: Path, columns: list[str] | None = None) -> pd.DataFrame:
    files = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not files:
        raise FileNotFoundError(f"no HYPE partitions under {root}")
    return pd.concat(
        (pd.read_parquet(path, columns=columns) for path in files),
        ignore_index=True,
    )


def _compare_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    columns: tuple[str, ...],
) -> dict[str, int]:
    joined = left[["ts", *columns]].merge(
        right[["ts", *columns]],
        on="ts",
        how="outer",
        suffixes=("_left", "_right"),
        indicator=True,
    )
    mismatches = {
        "missing_left": int(joined["_merge"].eq("right_only").sum()),
        "missing_right": int(joined["_merge"].eq("left_only").sum()),
    }
    common = joined.loc[joined["_merge"].eq("both")]
    for column in columns:
        mismatches[column] = int(
            (
                ~np.isclose(
                    pd.to_numeric(common[f"{column}_left"], errors="coerce"),
                    pd.to_numeric(common[f"{column}_right"], errors="coerce"),
                    rtol=0.0,
                    atol=1e-10,
                    equal_nan=False,
                )
            ).sum()
        )
    return mismatches


def _coerce_utc_ts(frame: pd.DataFrame, label: str) -> None:
    if "ts" in frame:
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return
    if "open_time" in frame:
        open_time = pd.to_numeric(frame["open_time"], errors="coerce")
        if open_time.isna().any():
            raise RuntimeError(f"{label} contains invalid open_time values")
        frame["ts"] = pd.to_datetime(open_time, unit="ms", utc=True)
        return
    raise RuntimeError(f"{label} contains neither ts nor open_time")


def load_and_audit_frame() -> tuple[pd.DataFrame, dict[str, Any]]:
    trade = _read_partitions(OHLCV_ROOT)
    raw_trade = _read_partitions(RAW_OHLCV_ROOT)
    mark = _read_partitions(MARK_ROOT)
    raw_mark = _read_partitions(RAW_MARK_ROOT)
    funding = _read_partitions(FUNDING_ROOT)

    for label, source_frame in (
        ("normalized OHLCV", trade),
        ("raw OHLCV", raw_trade),
        ("normalized mark", mark),
        ("raw mark", raw_mark),
        ("normalized funding", funding),
    ):
        _coerce_utc_ts(source_frame, label)

    duplicate_counts = {
        "ohlcv": int(trade.duplicated("ts").sum()),
        "raw_ohlcv": int(raw_trade.duplicated("ts").sum()),
        "mark": int(mark.duplicated("ts").sum()),
        "raw_mark": int(raw_mark.duplicated("ts").sum()),
        "funding": int(funding.duplicated("ts").sum()),
    }
    trade = trade.sort_values("ts").drop_duplicates("ts", keep="last")
    raw_trade = raw_trade.sort_values("ts").drop_duplicates("ts", keep="last")
    mark = mark.sort_values("ts").drop_duplicates("ts", keep="last")
    raw_mark = raw_mark.sort_values("ts").drop_duplicates("ts", keep="last")
    funding = funding.sort_values("ts").drop_duplicates("ts", keep="last")

    if "is_closed" not in trade or set(trade["is_closed"].dropna().unique()) != {True}:
        raise RuntimeError("OHLCV contains missing or non-closed bars")
    expected = pd.date_range(trade["ts"].iloc[0], trade["ts"].iloc[-1], freq="15min")
    missing_trade = expected.difference(pd.DatetimeIndex(trade["ts"]))
    mark_window = mark.loc[mark["ts"].between(expected[0], expected[-1])]
    missing_mark = expected.difference(pd.DatetimeIndex(mark_window["ts"]))
    critical_columns = (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "source",
        "is_closed",
    )
    critical_nulls = {
        column: int(trade[column].isna().sum()) for column in critical_columns
    }
    ohlc_violations = {
        "high_lt_open_or_close": int(
            (trade["high"] < trade[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_open_or_close": int(
            (trade["low"] > trade[["open", "close"]].min(axis=1)).sum()
        ),
        "high_lt_low": int((trade["high"] < trade["low"]).sum()),
        "nonpositive_ohlc": int(
            ((trade[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
    }
    normalized_vs_raw = _compare_frames(
        trade,
        raw_trade,
        ("open", "high", "low", "close", "volume", "quote_volume", "trade_count"),
    )
    mark_vs_raw = _compare_frames(
        mark_window,
        raw_mark.loc[raw_mark["ts"].between(expected[0], expected[-1])],
        ("open", "high", "low", "close"),
    )

    funding["ts"] = funding["ts"].dt.floor("15min")
    funding = funding.sort_values("ts").drop_duplicates("ts", keep="last")
    funding_gaps = funding["ts"].diff().dropna()
    quality = {
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "timeframe": "15m",
        "rows": int(len(trade)),
        "start": trade["ts"].iloc[0].isoformat(),
        "end": trade["ts"].iloc[-1].isoformat(),
        "missing_ohlcv_bars": int(len(missing_trade)),
        "missing_mark_bars": int(len(missing_mark)),
        "duplicate_counts": duplicate_counts,
        "critical_nulls": critical_nulls,
        "ohlc_violations": ohlc_violations,
        "raw_normalized_ohlcv_mismatches": normalized_vs_raw,
        "raw_normalized_mark_mismatches": mark_vs_raw,
        "funding_rows": int(len(funding)),
        "funding_start": funding["ts"].iloc[0].isoformat(),
        "funding_end": funding["ts"].iloc[-1].isoformat(),
        "funding_null_rates": int(funding["funding_rate"].isna().sum()),
        "funding_max_gap_hours": (
            float(funding_gaps.max().total_seconds() / 3600.0)
            if len(funding_gaps)
            else None
        ),
    }
    blocker_count = (
        len(missing_trade)
        + len(missing_mark)
        + sum(duplicate_counts.values())
        + sum(critical_nulls.values())
        + sum(ohlc_violations.values())
        + sum(normalized_vs_raw.values())
        + sum(mark_vs_raw.values())
        + quality["funding_null_rates"]
    )
    quality["blocker_count"] = int(blocker_count)
    if blocker_count:
        raise RuntimeError(f"HYPE data-quality blockers: {quality}")

    trade = trade.set_index("ts")
    mark_window = mark_window.set_index("ts").reindex(trade.index)
    funding_rate = funding.set_index("ts")["funding_rate"].reindex(trade.index)
    frame = trade[["open", "high", "low", "close", "volume"]].copy()
    frame["mark_high"] = mark_window["high"].astype(float)
    frame["mark_low"] = mark_window["low"].astype(float)
    frame["funding_rate"] = funding_rate.fillna(0.0).astype(float)
    if frame.isna().any().any():
        raise RuntimeError(f"joined replay frame contains nulls: {frame.isna().sum()}")
    return frame, quality


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def ema_allows(
    fast: pd.Series,
    slow: pd.Series,
    position: int,
    direction: int,
) -> bool:
    fast_value = float(fast.iloc[position])
    slow_value = float(slow.iloc[position])
    if not np.isfinite(fast_value) or not np.isfinite(slow_value):
        return False
    if direction > 0:
        return fast_value > slow_value
    return fast_value < slow_value


def run_canonical(
    module,
    frame: pd.DataFrame,
    config,
    *,
    fast_span: int | None = None,
    slow_span: int | None = None,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
):
    if fast_span is None or slow_span is None:
        return module.run_v35(
            frame, config, trade_start=trade_start, trade_end=trade_end
        )
    close = frame["close"].astype(float)
    fast = ema(close, fast_span)
    slow = ema(close, slow_span)
    original = module._trend_filter_allows

    def combined_filter(
        trend_return: pd.Series,
        position: int,
        desired_direction: int,
        run_config,
    ) -> bool:
        return original(
            trend_return, position, desired_direction, run_config
        ) and ema_allows(fast, slow, position, desired_direction)

    module._trend_filter_allows = combined_filter
    try:
        return module.run_v35(
            frame, config, trade_start=trade_start, trade_end=trade_end
        )
    finally:
        module._trend_filter_allows = original


def _realistic_early_reason(
    frame: pd.DataFrame,
    *,
    entry_position: int,
    current_position: int,
    direction: int,
) -> str | None:
    bars_held = current_position - entry_position + 1
    if bars_held == 3:
        window = frame.iloc[entry_position : current_position + 1]
        if direction > 0:
            opposite = int(window["close"].lt(window["open"]).sum())
        else:
            opposite = int(window["close"].gt(window["open"]).sum())
        if opposite == 3:
            return "early_main"
    if bars_held == 12:
        window = frame.iloc[entry_position : current_position + 1]
        if direction > 0:
            opposite = int(window["close"].lt(window["open"]).sum())
            favorable = int(window["close"].gt(window["open"]).sum())
        else:
            opposite = int(window["close"].gt(window["open"]).sum())
            favorable = int(window["close"].lt(window["open"]).sum())
        if opposite >= 9:
            return "early_counter_opposite"
        if favorable >= 9:
            return "early_counter_favorable"
    return None


def run_next_open(
    module,
    frame: pd.DataFrame,
    config,
    *,
    fast_span: int | None = None,
    slow_span: int | None = None,
    direction_filter: Callable[[int, int], bool] | None = None,
    apply_original_trend_filter: bool = True,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
):
    frame = module._normalize_frame(frame)
    signal = module.build_candle_count_signal(frame, config)
    close = frame["close"].astype(float)
    open_price = frame["open"].astype(float)
    mark_high = frame["mark_high"].astype(float)
    mark_low = frame["mark_low"].astype(float)
    funding_rate = frame["funding_rate"].fillna(0.0).astype(float)
    allocation_atr = module._atr_pct(frame, config.allocation_atr_window)
    stop_loss_atr = module._atr_pct(frame, config.stop_loss_atr_window)
    take_profit_atr = module._atr_pct(frame, config.take_profit_atr_window)
    trend_return = module._trend_return(close, config.trend_window_bars)
    fast = ema(close, fast_span) if fast_span is not None else None
    slow = ema(close, slow_span) if slow_span is not None else None
    start_position, end_position = module._trade_bounds(
        frame, trade_start=trade_start, trade_end=trade_end
    )

    cost_rate = config.fee_rate + config.slippage_rate
    equity = 1.0
    previous_price = float(close.iloc[start_position])
    current_direction = 0
    entry_position: int | None = None
    entry_ts: pd.Timestamp | None = None
    entry_price = np.nan
    entry_equity = np.nan
    current_allocation = 0.0
    current_base_allocation = 0.0
    current_risk_multiplier_at_entry = 1.0
    current_stop_loss_pct = config.stop_loss_pct
    current_take_profit_pct = config.take_profit_pct
    risk_multiplier = 1.0
    cooldown_remaining = 0
    pending_direction = 0
    pending_signal_position: int | None = None

    equity_values: list[float] = []
    period_returns: list[float] = []
    weights: list[float] = []
    trades: list[dict[str, object]] = []
    trading_costs = 0.0
    funding_pnl = 0.0
    stops = 0
    takes = 0
    early_main = 0
    early_counter_opposite = 0
    early_counter_favorable = 0
    entries = 0
    exits = 0
    long_entries = 0
    short_entries = 0
    blocked_by_ema = 0
    blocked_by_direction_filter = 0

    for position in range(start_position, end_position + 1):
        ts = pd.Timestamp(frame.index[position])
        close_price = float(close.iloc[position])
        bar_return = 0.0
        exited_this_bar = False
        entered_this_bar = False
        cooldown_at_start = cooldown_remaining

        if (
            current_direction == 0
            and pending_direction != 0
            and pending_signal_position is not None
            and cooldown_remaining == 0
        ):
            signal_position = pending_signal_position
            base_allocation = module._entry_allocation(
                allocation_atr, signal_position, config
            )
            allocation = base_allocation * risk_multiplier
            stop_loss_pct = module._dynamic_pct(
                stop_loss_atr,
                signal_position,
                fallback=config.stop_loss_pct,
                multiplier=config.stop_loss_atr_multiplier,
                lower=config.min_stop_loss_pct,
                upper=config.max_stop_loss_pct,
            )
            take_profit_pct = module._dynamic_pct(
                take_profit_atr,
                signal_position,
                fallback=config.take_profit_pct,
                multiplier=config.take_profit_atr_multiplier,
                lower=config.min_take_profit_pct,
                upper=config.max_take_profit_pct,
            )
            if allocation > 0.0 and stop_loss_pct > 0.0 and take_profit_pct > 0.0:
                current_direction = pending_direction
                entry_position = position
                entry_ts = ts
                entry_price = float(open_price.iloc[position])
                previous_price = entry_price
                entry_equity = equity
                current_allocation = allocation
                current_base_allocation = base_allocation
                current_risk_multiplier_at_entry = risk_multiplier
                current_stop_loss_pct = stop_loss_pct
                current_take_profit_pct = take_profit_pct
                cost = current_allocation * cost_rate
                equity *= 1.0 - cost
                bar_return -= cost
                trading_costs += cost
                entries += 1
                entered_this_bar = True
                if current_direction > 0:
                    long_entries += 1
                else:
                    short_entries += 1
        pending_direction = 0
        pending_signal_position = None

        if current_direction != 0 and entry_position is not None:
            exit_price, exit_reason = module._intrabar_exit(
                direction=current_direction,
                entry_price=float(entry_price),
                mark_high=float(mark_high.iloc[position]),
                mark_low=float(mark_low.iloc[position]),
                stop_loss_pct=current_stop_loss_pct,
                take_profit_pct=current_take_profit_pct,
            )
            if exit_price is None:
                early_reason = _realistic_early_reason(
                    frame,
                    entry_position=entry_position,
                    current_position=position,
                    direction=current_direction,
                )
                if early_reason is not None:
                    exit_price = close_price
                    exit_reason = early_reason

            if exit_price is None:
                pnl = (
                    current_direction
                    * current_allocation
                    * (close_price / previous_price - 1.0)
                )
                equity *= 1.0 + pnl
                bar_return += pnl
                previous_price = close_price
            else:
                pnl = (
                    current_direction
                    * current_allocation
                    * (float(exit_price) / previous_price - 1.0)
                )
                cost = current_allocation * cost_rate
                equity *= 1.0 + pnl - cost
                bar_return += pnl - cost
                trading_costs += cost
                previous_price = close_price
                exits += 1
                if exit_reason == "stop":
                    stops += 1
                    risk_multiplier = max(
                        config.min_risk_multiplier,
                        risk_multiplier * config.stop_loss_risk_multiplier,
                    )
                elif exit_reason == "take":
                    takes += 1
                    risk_multiplier = 1.0
                elif exit_reason == "early_main":
                    early_main += 1
                elif exit_reason == "early_counter_opposite":
                    early_counter_opposite += 1
                elif exit_reason == "early_counter_favorable":
                    early_counter_favorable += 1
                trades.append(
                    {
                        "entry_ts": entry_ts,
                        "exit_ts": ts,
                        "direction": current_direction,
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "allocation": current_allocation,
                        "base_allocation": current_base_allocation,
                        "risk_multiplier_at_entry": current_risk_multiplier_at_entry,
                        "stop_loss_pct": current_stop_loss_pct,
                        "take_profit_pct": current_take_profit_pct,
                        "exit_reason": exit_reason,
                        "entry_equity": float(entry_equity),
                        "exit_equity": equity,
                        "trade_return": equity / float(entry_equity) - 1.0,
                        "period_start": int(entry_position),
                        "period_end": position,
                        "entered_next_open": True,
                        "same_bar_exit": entered_this_bar,
                    }
                )
                current_direction = 0
                entry_position = None
                entry_ts = None
                entry_price = np.nan
                entry_equity = np.nan
                current_allocation = 0.0
                current_base_allocation = 0.0
                current_risk_multiplier_at_entry = 1.0
                exited_this_bar = True
                cooldown_remaining = max(cooldown_remaining, config.cooldown_bars)
        elif position > start_position:
            previous_price = close_price

        if current_direction != 0:
            funding = (
                -current_direction
                * current_allocation
                * float(funding_rate.iloc[position])
            )
            equity *= 1.0 + funding
            bar_return += funding
            funding_pnl += funding

        if (
            position < end_position
            and current_direction == 0
            and cooldown_remaining == 0
            and not exited_this_bar
        ):
            desired_direction = int(signal.iloc[position])
            entry_allowed = (
                desired_direction != 0
                and module._entry_allowed(signal, position, desired_direction, config)
                and (
                    not apply_original_trend_filter
                    or module._trend_filter_allows(
                        trend_return, position, desired_direction, config
                    )
                )
            )
            if entry_allowed and fast is not None and slow is not None:
                if not ema_allows(fast, slow, position, desired_direction):
                    blocked_by_ema += 1
                    entry_allowed = False
            if entry_allowed and direction_filter is not None:
                if not direction_filter(position, desired_direction):
                    blocked_by_direction_filter += 1
                    entry_allowed = False
            if entry_allowed:
                pending_direction = desired_direction
                pending_signal_position = position

        equity_values.append(equity)
        period_returns.append(bar_return)
        weights.append(current_direction * current_allocation)
        if cooldown_at_start > 0:
            cooldown_remaining -= 1

    trade_index = frame.index[start_position : end_position + 1]
    equity_curve = pd.Series(equity_values, index=trade_index, name="equity")
    period_return_series = pd.Series(
        period_returns, index=trade_index, name="period_return"
    )
    weight_series = pd.Series(weights, index=trade_index, name="weight")
    metrics = module._metrics(
        equity_curve=equity_curve,
        period_returns=period_return_series,
        entries=entries,
        exits=exits,
        stops=stops,
        takes=takes,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl,
        annualization_bars=config.annualization_bars,
    )
    metrics.update(
        {
            "early_main": float(early_main),
            "early_counter_opposite": float(early_counter_opposite),
            "early_counter_favorable": float(early_counter_favorable),
            "early_exits": float(
                early_main + early_counter_opposite + early_counter_favorable
            ),
            "long_entries": float(long_entries),
            "short_entries": float(short_entries),
            "avg_abs_allocation": float(weight_series.abs().mean()),
            "max_abs_allocation": float(weight_series.abs().max()),
            "blocked_by_ema": float(blocked_by_ema),
            "blocked_by_direction_filter": float(blocked_by_direction_filter),
        }
    )
    return module.V35Run(
        equity_curve=equity_curve,
        period_returns=period_return_series,
        weights=weight_series,
        trades=pd.DataFrame(trades),
        metrics=metrics,
    )


def compact_metrics(run) -> dict[str, float | int]:
    metrics = run.metrics
    return {
        "return_pct": round(float(metrics["cumulative_return"]) * 100.0, 4),
        "max_drawdown_pct": round(float(metrics["max_drawdown"]) * 100.0, 4),
        "sharpe": round(float(metrics["sharpe"]), 4),
        "entries": int(metrics["entries"]),
        "exits": int(metrics["exits"]),
        "stops": int(metrics["stops"]),
        "takes": int(metrics["takes"]),
        "early_exits": int(metrics.get("early_exits", 0)),
        "long_entries": int(metrics.get("long_entries", 0)),
        "short_entries": int(metrics.get("short_entries", 0)),
        "blocked_by_ema": int(metrics.get("blocked_by_ema", 0)),
        "blocked_by_direction_filter": int(
            metrics.get("blocked_by_direction_filter", 0)
        ),
        "avg_allocation": round(float(metrics.get("avg_abs_allocation", 0.0)), 4),
        "trading_costs": round(float(metrics["trading_costs"]), 6),
        "funding_pnl": round(float(metrics["funding_pnl"]), 6),
    }


def build_oos_windows(
    data_start: pd.Timestamp,
    selection_end: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    first_oos = data_start + pd.Timedelta(days=60 + 10)
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    start = first_oos
    index = 1
    while start <= selection_end:
        end = min(
            start + pd.Timedelta(days=30) - pd.Timedelta(minutes=15), selection_end
        )
        if end > start:
            windows.append((f"oos_{index:02d}", start, end))
        start += pd.Timedelta(days=30)
        index += 1
    return windows


def aggregate_oos(rows: pd.DataFrame) -> pd.DataFrame:
    grouped: list[dict[str, object]] = []
    for (fast, slow), group in rows.groupby(["fast_span", "slow_span"], dropna=False):
        grouped.append(
            {
                "fast_span": fast,
                "slow_span": slow,
                "positive_window_rate": float((group["return_pct"] > 0).mean()),
                "median_return_pct": float(group["return_pct"].median()),
                "median_sharpe": float(group["sharpe"].median()),
                "median_max_drawdown_pct": float(group["max_drawdown_pct"].median()),
                "worst_max_drawdown_pct": float(group["max_drawdown_pct"].min()),
                "median_entries": float(group["entries"].median()),
                "total_entries": int(group["entries"].sum()),
                "zero_trade_windows": int((group["entries"] == 0).sum()),
                "window_count": int(len(group)),
            }
        )
    return pd.DataFrame(grouped)


def is_neighbor(
    fast_a: int,
    slow_a: int,
    fast_b: int,
    slow_b: int,
) -> bool:
    fast_index_a = FAST_SPANS.index(fast_a)
    fast_index_b = FAST_SPANS.index(fast_b)
    slow_index_a = SLOW_SPANS.index(slow_a)
    slow_index_b = SLOW_SPANS.index(slow_b)
    return abs(fast_index_a - fast_index_b) + abs(slow_index_a - slow_index_b) == 1


def main() -> None:
    module = _load_replay_module()
    frame, quality = load_and_audit_frame()
    config = module.hype_v35_config()
    selection_frame = frame.loc[frame.index <= SELECTION_END]
    if selection_frame.empty or frame.index[-1] < HOLDOUT_START:
        raise RuntimeError("selection or holdout data is unavailable")

    canonical_baseline = run_canonical(module, selection_frame, config)
    canonical_metrics = compact_metrics(canonical_baseline)
    parity = {
        key: (
            abs(float(canonical_metrics[key]) - float(expected)) < 0.02
            if key != "entries"
            else int(canonical_metrics[key]) == int(expected)
        )
        for key, expected in CURRENT_BASELINE.items()
    }
    if not all(parity.values()):
        raise RuntimeError(
            "current reproducible V35 baseline parity failed: "
            f"actual={canonical_metrics}, expected={CURRENT_BASELINE}, checks={parity}"
        )

    oos_windows = build_oos_windows(frame.index[0], SELECTION_END)
    oos_rows: list[dict[str, object]] = []
    candidates: list[tuple[int | None, int | None]] = [(None, None), *EMA_PAIRS]
    for fast_span, slow_span in candidates:
        for window_name, start, end in oos_windows:
            run = run_next_open(
                module,
                frame,
                config,
                fast_span=fast_span,
                slow_span=slow_span,
                trade_start=start,
                trade_end=end,
            )
            oos_rows.append(
                {
                    "candidate": (
                        "V35 baseline"
                        if fast_span is None
                        else f"EMA{fast_span}/{slow_span}"
                    ),
                    "fast_span": fast_span,
                    "slow_span": slow_span,
                    "window": window_name,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    **compact_metrics(run),
                }
            )
    oos = pd.DataFrame(oos_rows)
    aggregate = aggregate_oos(oos)
    baseline_aggregate = aggregate.loc[
        aggregate["fast_span"].isna() & aggregate["slow_span"].isna()
    ].iloc[0]
    grid = aggregate.loc[aggregate["fast_span"].notna()].copy()
    grid["trade_retention"] = grid["median_entries"] / float(
        baseline_aggregate["median_entries"]
    )
    grid["pre_pass"] = (
        (grid["positive_window_rate"] >= 0.60)
        & (grid["median_sharpe"] > float(baseline_aggregate["median_sharpe"]))
        & (
            grid["median_return_pct"]
            >= 0.80 * float(baseline_aggregate["median_return_pct"])
        )
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline_aggregate["worst_max_drawdown_pct"])
        )
        & (grid["trade_retention"] >= 0.50)
    )
    grid = grid.sort_values(
        ["pre_pass", "median_sharpe", "median_return_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    selected = grid.iloc[0]
    selected_fast = int(selected["fast_span"])
    selected_slow = int(selected["slow_span"])

    robust_neighbors = grid.loc[
        grid.apply(
            lambda row: is_neighbor(
                selected_fast,
                selected_slow,
                int(row["fast_span"]),
                int(row["slow_span"]),
            ),
            axis=1,
        )
        & (grid["positive_window_rate"] >= 0.50)
        & (grid["median_return_pct"] > 0)
    ]
    plateau_pass = len(robust_neighbors) >= 2

    holdout_end = frame.index[-1]
    holdout_baseline = run_next_open(
        module,
        frame,
        config,
        trade_start=HOLDOUT_START,
        trade_end=holdout_end,
    )
    holdout_selected = run_next_open(
        module,
        frame,
        config,
        fast_span=selected_fast,
        slow_span=selected_slow,
        trade_start=HOLDOUT_START,
        trade_end=holdout_end,
    )
    holdout_baseline_metrics = compact_metrics(holdout_baseline)
    holdout_selected_metrics = compact_metrics(holdout_selected)
    holdout_pass = (
        holdout_selected_metrics["return_pct"] > holdout_baseline_metrics["return_pct"]
        and holdout_selected_metrics["max_drawdown_pct"]
        >= holdout_baseline_metrics["max_drawdown_pct"]
        and holdout_selected_metrics["entries"]
        >= 0.50 * holdout_baseline_metrics["entries"]
    )

    recent_windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    recent_rows: list[dict[str, object]] = []
    for window_name, delta in recent_windows.items():
        start = max(frame.index[0], holdout_end - delta)
        for candidate_name, fast_span, slow_span in (
            ("V35 baseline", None, None),
            (
                f"EMA{selected_fast}/{selected_slow}",
                selected_fast,
                selected_slow,
            ),
        ):
            run = run_next_open(
                module,
                frame,
                config,
                fast_span=fast_span,
                slow_span=slow_span,
                trade_start=start,
                trade_end=holdout_end,
            )
            recent_rows.append(
                {
                    "window": window_name,
                    "candidate": candidate_name,
                    "start": start.isoformat(),
                    "end": holdout_end.isoformat(),
                    "fee_rate": config.fee_rate,
                    "slippage_rate": config.slippage_rate,
                    **compact_metrics(run),
                }
            )

    stress_config = replace(config, fee_rate=0.001, slippage_rate=0.0004)
    stress_baseline = run_next_open(module, frame, stress_config)
    stress_selected = run_next_open(
        module,
        frame,
        stress_config,
        fast_span=selected_fast,
        slow_span=selected_slow,
    )
    canonical_selected = run_canonical(
        module,
        frame,
        config,
        fast_span=selected_fast,
        slow_span=selected_slow,
    )
    realistic_baseline_full = run_next_open(module, frame, config)
    realistic_selected_full = run_next_open(
        module,
        frame,
        config,
        fast_span=selected_fast,
        slow_span=selected_slow,
    )
    final_pass = bool(selected["pre_pass"]) and plateau_pass and holdout_pass

    selected_trades = realistic_selected_full.trades.copy()
    if not selected_trades.empty:
        selected_trades.insert(0, "candidate", f"EMA{selected_fast}/{selected_slow}")
    grid["robust_neighbor_of_selected"] = grid.apply(
        lambda row: is_neighbor(
            selected_fast,
            selected_slow,
            int(row["fast_span"]),
            int(row["slow_span"]),
        ),
        axis=1,
    )
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "HYPE-Candle-Count-Reversal-V35 + dual EMA trend gate",
        "status": (
            "candidate passed; eligible for V36 registration"
            if final_pass
            else "candidate failed; do not register V36"
        ),
        "data_quality": quality,
        "ema_contract": {
            "source": "closed 15m close",
            "formula": "pandas ewm(span=N, adjust=False, min_periods=N)",
            "alpha": "2 / (span + 1)",
            "long_allowed": "fast_ema > slow_ema",
            "short_allowed": "fast_ema < slow_ema",
            "equal_or_not_ready": "block entry",
            "existing_96_bar_5pct_trend_filter": "retained",
            "fast_grid": list(FAST_SPANS),
            "slow_grid": list(SLOW_SPANS),
            "pairs": [list(pair) for pair in EMA_PAIRS],
        },
        "execution": {
            "parity_mode": "signal-bar close entry; frozen canonical V35 engine",
            "selection_mode": "signal confirmed on closed bar; next bar open entry",
            "same_entry_bar_stop_take": True,
            "fee_rate_primary": config.fee_rate,
            "slippage_rate_primary": config.slippage_rate,
            "fee_rate_stress": stress_config.fee_rate,
            "slippage_rate_stress": stress_config.slippage_rate,
            "funding": "Binance funding history included",
            "stop_take_trigger": "Binance 15m mark-price high/low; stop first on conflict",
        },
        "baseline_parity": {
            "expected_current_reproduction": CURRENT_BASELINE,
            "actual": canonical_metrics,
            "checks": parity,
            "legacy_published_difference": (
                "The older 340-trade/+8357.56% headline is not reproducible by the "
                "current frozen replay; the ledger already records the 339-trade "
                "local reproduction."
            ),
        },
        "selection": {
            "selection_data_end": SELECTION_END.isoformat(),
            "holdout_start": HOLDOUT_START.isoformat(),
            "holdout_end": holdout_end.isoformat(),
            "oos_contract": "60d history + 10d gap + 30d OOS, stepped by 30d",
            "oos_window_count": len(oos_windows),
            "selected_fast_span": selected_fast,
            "selected_slow_span": selected_slow,
            "selected_pre_holdout": selected.to_dict(),
            "baseline_oos": baseline_aggregate.to_dict(),
            "robust_neighbor_count": int(len(robust_neighbors)),
            "robust_neighbors": robust_neighbors[
                [
                    "fast_span",
                    "slow_span",
                    "positive_window_rate",
                    "median_return_pct",
                    "median_sharpe",
                ]
            ].to_dict("records"),
            "plateau_pass": plateau_pass,
            "holdout_baseline": holdout_baseline_metrics,
            "holdout_selected": holdout_selected_metrics,
            "holdout_pass": holdout_pass,
            "final_pass": final_pass,
        },
        "full_period": {
            "canonical_selected": compact_metrics(canonical_selected),
            "next_open_baseline": compact_metrics(realistic_baseline_full),
            "next_open_selected": compact_metrics(realistic_selected_full),
            "binance_cost_stress_baseline": compact_metrics(stress_baseline),
            "binance_cost_stress_selected": compact_metrics(stress_selected),
        },
        "artifacts": {
            "grid": str(GRID_PATH.relative_to(ROOT)),
            "oos": str(OOS_PATH.relative_to(ROOT)),
            "recent": str(RECENT_PATH.relative_to(ROOT)),
            "selected_trades": str(TRADES_PATH.relative_to(ROOT)),
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    grid.to_csv(GRID_PATH, index=False)
    oos.to_csv(OOS_PATH, index=False)
    pd.DataFrame(recent_rows).to_csv(RECENT_PATH, index=False)
    selected_trades.to_csv(TRADES_PATH, index=False)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
