from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402


RUN_DATE = "2026-07-10"
FAMILY_DIR = base.FAMILY_DIR
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
FUNDING_CACHE = base.CACHE_DIR / "HYPEUSDT_funding.parquet"
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_validation_gates_{RUN_DATE}.json"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_trades_{RUN_DATE}.csv"
GATES_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_gate_summary_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_rolling_oos_{RUN_DATE}.csv"
ABLATION_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_ablation_{RUN_DATE}.csv"
STRESS_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_stress_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_phase_{RUN_DATE}.csv"
START_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_start_time_{RUN_DATE}.csv"
PARAM_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_parameter_neighborhood_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_k2_strict_monte_carlo_{RUN_DATE}.csv"

FUNDING_API_PATH = "/fapi/v1/fundingRate"
FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
SEED = 20260710
PHASES_30M = (0, 5, 10, 15, 20, 25)
PHASES_1H = (0, 30)


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    fee_rate: float = FEE_PER_FILL
    slippage_rate: float = SLIPPAGE_PER_FILL
    extra_stop_slippage_rate: float = 0.0
    entry_delay_bars: int = 0
    bracket_delay_bars: int = 0
    include_funding: bool = True
    signal_mode: str = "full"
    bracket_atr_column: str = "atr96"
    dynamic_tp_atr_mult: float | None = None
    dynamic_sl_atr_mult: float | None = None
    dynamic_tp_floor_pct: float = 0.0
    dynamic_tp_cap_pct: float = 10.0
    dynamic_sl_floor_pct: float = 0.0
    dynamic_sl_cap_pct: float = 10.0


@dataclass(frozen=True, slots=True)
class StrictResult:
    name: str
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    trades: pd.DataFrame
    equity: pd.Series
    diagnostics: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2025-05-30T00:00:00Z")
    parser.add_argument("--until", default="")
    parser.add_argument("--refresh-data", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--mc-kline-runs", type=int, default=100)
    parser.add_argument("--mc-trade-runs", type=int, default=5000)
    return parser.parse_args()


def fetch_funding(*, since_ms: int, until_ms: int, timeout: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    cursor = since_ms
    while cursor <= until_ms:
        payload = base.request_json(
            FUNDING_API_PATH,
            params={
                "symbol": base.SYMBOL,
                "startTime": cursor,
                "endTime": until_ms,
                "limit": 1000,
            },
            timeout=timeout,
        )
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(payload)
        next_cursor = int(payload[-1]["fundingTime"]) + 1
        if next_cursor <= cursor:
            raise RuntimeError("funding pagination stopped advancing")
        cursor = next_cursor
        if len(payload) < 1000:
            break
        time.sleep(0.05)
    if not rows:
        return pd.DataFrame(columns=["ts", "funding_rate", "mark_price", "source"])
    frame = pd.DataFrame(rows)
    frame["ts"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["fundingRate"], errors="coerce")
    frame["mark_price"] = pd.to_numeric(frame.get("markPrice"), errors="coerce")
    frame["source"] = "binance_futures_funding_rate_api"
    return (
        frame[["ts", "funding_rate", "mark_price", "source"]]
        .sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .reset_index(drop=True)
    )


def load_or_fetch_funding(args: argparse.Namespace, m1: pd.DataFrame) -> pd.DataFrame:
    since_ms = int(pd.to_datetime(m1["ts"], utc=True).min().timestamp() * 1000)
    until_ms = int((pd.to_datetime(m1["ts"], utc=True).max() + pd.Timedelta(minutes=1)).timestamp() * 1000)
    if FUNDING_CACHE.exists() and not args.refresh_data:
        frame = pd.read_parquet(FUNDING_CACHE)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        covered = not frame.empty and frame["ts"].min().timestamp() * 1000 <= since_ms and frame["ts"].max().timestamp() * 1000 >= until_ms - 8 * 60 * 60 * 1000
        if covered:
            since_ts = pd.to_datetime(since_ms, unit="ms", utc=True)
            until_ts = pd.to_datetime(until_ms, unit="ms", utc=True)
            return frame.loc[(frame["ts"] >= since_ts) & (frame["ts"] <= until_ts)].reset_index(drop=True)
    frame = fetch_funding(since_ms=since_ms, until_ms=until_ms, timeout=args.timeout)
    base.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(FUNDING_CACHE, index=False)
    return frame


def load_standard_lake_1m() -> tuple[pd.DataFrame, pd.DataFrame]:
    relative = Path("ohlcv/exchange=binance/market_type=perp/timeframe=1m")
    raw_root = base.ROOT / "data/raw" / relative
    normalized_root = base.ROOT / "data/normalized" / relative

    def load(root: Path) -> pd.DataFrame:
        files = sorted(root.rglob("symbol=hype_usdt_usdt.parquet"))
        if not files:
            return pd.DataFrame()
        return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)

    return load(raw_root), load(normalized_root)


def audit_data_quality(m1: pd.DataFrame, raw_lake: pd.DataFrame, normalized_lake: pd.DataFrame) -> dict[str, Any]:
    quality = base.data_quality(m1)
    key_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
    result: dict[str, Any] = {
        **quality,
        "cache_has_vwap": "vwap" in m1.columns,
        "raw_lake_rows": int(len(raw_lake)),
        "normalized_lake_rows": int(len(normalized_lake)),
        "raw_normalized_exact_match": False,
        "cache_lake_overlap_rows": 0,
        "cache_lake_mismatch_cells": None,
        "full_period_in_standard_lake": False,
    }
    if not raw_lake.empty and not normalized_lake.empty:
        raw = raw_lake.copy()
        normalized = normalized_lake.copy()
        raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
        normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
        common_columns = ["ts", *[column for column in key_columns + ["vwap", "is_closed", "source"] if column in raw.columns and column in normalized.columns]]
        raw_cmp = raw[common_columns].sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
        normalized_cmp = normalized[common_columns].sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
        result["raw_normalized_exact_match"] = bool(raw_cmp.equals(normalized_cmp))

        cache = m1.copy()
        cache["ts"] = pd.to_datetime(cache["ts"], utc=True)
        overlap_columns = [column for column in key_columns if column in cache.columns and column in normalized.columns]
        merged = cache[["ts", *overlap_columns]].merge(
            normalized[["ts", *overlap_columns]],
            on="ts",
            how="inner",
            suffixes=("_cache", "_lake"),
        )
        mismatches = 0
        for column in overlap_columns:
            left = pd.to_numeric(merged[f"{column}_cache"], errors="coerce").to_numpy("float64")
            right = pd.to_numeric(merged[f"{column}_lake"], errors="coerce").to_numpy("float64")
            mismatches += int((~np.isclose(left, right, rtol=0.0, atol=1e-12, equal_nan=True)).sum())
        result["cache_lake_overlap_rows"] = int(len(merged))
        result["cache_lake_mismatch_cells"] = mismatches
        cache_ts = pd.to_datetime(cache["ts"], utc=True)
        lake_ts = pd.to_datetime(normalized["ts"], utc=True)
        result["full_period_in_standard_lake"] = bool(lake_ts.min() <= cache_ts.min() and lake_ts.max() >= cache_ts.max())
        result["standard_lake_start"] = str(lake_ts.min())
        result["standard_lake_end"] = str(lake_ts.max())
    result["gate_pass"] = bool(
        quality["missing_1m_bars"] == 0
        and quality["duplicate_ts_rows"] == 0
        and quality["invalid_ohlc_rows"] == 0
        and quality["critical_null_rows"] == 0
        and result["raw_normalized_exact_match"]
        and result["cache_lake_mismatch_cells"] == 0
        and result["full_period_in_standard_lake"]
        and result["cache_has_vwap"]
    )
    return result


def adverse_fill(raw_price: float, direction: int, *, is_entry: bool, slippage: float) -> float:
    order_side = direction if is_entry else -direction
    return float(raw_price * (1.0 + order_side * slippage))


def select_signals(features: pd.DataFrame, mode: str) -> tuple[np.ndarray, np.ndarray]:
    if mode == "full":
        return features["long_signal"].fillna(False).to_numpy(bool), features["short_signal"].fillna(False).to_numpy(bool)
    if mode == "no_regime":
        return features["break_up"].fillna(False).to_numpy(bool), features["break_down"].fillna(False).to_numpy(bool)
    if mode == "regime_only":
        return features["long_regime_1h"].fillna(False).to_numpy(bool), features["short_regime_1h"].fillna(False).to_numpy(bool)
    raise ValueError(f"unknown signal mode: {mode}")


def metrics_from_equity(equity: pd.Series, trades: pd.DataFrame) -> dict[str, Any]:
    metrics = base.compute_metrics(equity, trades)
    if trades.empty:
        metrics.update({"profit_factor": 0.0, "avg_trade_pct": 0.0, "funding_pnl_pct": 0.0, "gap_stop_count": 0, "both_hit_count": 0})
        return metrics
    returns = pd.to_numeric(trades["net_account_return_pct"], errors="coerce") / 100.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    metrics.update(
        {
            "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
            "avg_trade_pct": float(returns.mean() * 100.0),
            "funding_pnl_pct": float(pd.to_numeric(trades["funding_pnl"], errors="coerce").sum() * 100.0),
            "gap_stop_count": int(trades["exit_reason"].eq("stop_gap_open").sum()),
            "both_hit_count": int(pd.to_numeric(trades["both_hit"], errors="coerce").fillna(0).astype(bool).sum()),
        }
    )
    return metrics


def simulate(
    name: str,
    features: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    *,
    start_ts: pd.Timestamp | None = None,
    end_ts: pd.Timestamp | None = None,
    force_close: bool = True,
) -> StrictResult:
    index = pd.DatetimeIndex(features.index)
    start = index.min() if start_ts is None else pd.Timestamp(start_ts)
    end = index.max() + pd.Timedelta(minutes=30) if end_ts is None else pd.Timestamp(end_ts)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")

    long_signal, short_signal = select_signals(features, execution.signal_mode)
    open_ = features["open"].to_numpy("float64")
    high = features["high"].to_numpy("float64")
    low = features["low"].to_numpy("float64")
    close = features["close"].to_numpy("float64")
    atr96 = features["atr96"].to_numpy("float64")
    if execution.bracket_atr_column not in features.columns:
        raise KeyError(f"missing bracket ATR column: {execution.bracket_atr_column}")
    bracket_atr = features[execution.bracket_atr_column].to_numpy("float64")

    funding_frame = funding.copy()
    if funding_frame.empty:
        funding_ns = np.array([], dtype="int64")
        funding_rate = np.array([], dtype="float64")
        funding_mark = np.array([], dtype="float64")
    else:
        funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True)
        funding_frame = funding_frame.sort_values("ts")
        funding_ns = (
            funding_frame["ts"]
            .dt.tz_convert("UTC")
            .dt.tz_localize(None)
            .to_numpy(dtype="datetime64[ns]")
            .astype("int64")
        )
        funding_rate = pd.to_numeric(funding_frame["funding_rate"], errors="coerce").fillna(0.0).to_numpy("float64")
        funding_mark = pd.to_numeric(funding_frame["mark_price"], errors="coerce").to_numpy("float64")

    equity = 1.0
    cash = 1.0
    position: dict[str, Any] | None = None
    pending: tuple[int, int] | None = None
    funding_cursor = int(np.searchsorted(funding_ns, start.value, side="left")) if len(funding_ns) else 0
    trades: list[dict[str, Any]] = []
    curve: list[tuple[pd.Timestamp, float]] = []
    rejected_warmup = 0
    skipped_signals_in_position = 0
    same_bar_conflicts = 0

    active_indices = np.flatnonzero((index >= start) & (index < end))
    if not len(active_indices):
        empty = pd.Series(dtype="float64", name=name)
        return StrictResult(name, metrics_from_equity(empty, pd.DataFrame()), [], pd.DataFrame(), empty, {"no_active_bars": True})

    for i in active_indices:
        ts = index[i]

        while funding_cursor < len(funding_ns) and funding_ns[funding_cursor] <= ts.value:
            if position is not None and execution.include_funding and funding_ns[funding_cursor] > position["entry_ts"].value:
                mark = funding_mark[funding_cursor]
                if not np.isfinite(mark) or mark <= 0.0:
                    mark = open_[i]
                payment = -position["direction"] * position["quantity"] * mark * funding_rate[funding_cursor]
                cash += payment
                position["funding_pnl"] += payment
            funding_cursor += 1

        if pending is not None and position is None and i >= pending[1]:
            direction = pending[0]
            atr = atr96[i - 1] if i > 0 else np.nan
            raw_entry = open_[i]
            if np.isfinite(atr) and atr > 0.0 and np.isfinite(raw_entry) and raw_entry > 0.0:
                entry_fill = adverse_fill(raw_entry, direction, is_entry=True, slippage=execution.slippage_rate)
                leverage = float(np.clip(strategy.atr_target_pct / (atr / raw_entry), strategy.min_leverage, strategy.max_leverage))
                bracket_atr_value = bracket_atr[i - 1] if i > 0 else np.nan
                bracket_atr_pct = (
                    float(bracket_atr_value / raw_entry)
                    if np.isfinite(bracket_atr_value) and bracket_atr_value > 0.0
                    else float("nan")
                )
                tp_pct = strategy.take_profit_pct
                sl_pct = strategy.stop_loss_pct
                if execution.dynamic_tp_atr_mult is not None:
                    if not np.isfinite(bracket_atr_pct):
                        pending = None
                        rejected_warmup += 1
                        continue
                    tp_pct = float(
                        np.clip(
                            execution.dynamic_tp_atr_mult * bracket_atr_pct,
                            execution.dynamic_tp_floor_pct,
                            execution.dynamic_tp_cap_pct,
                        )
                    )
                if execution.dynamic_sl_atr_mult is not None:
                    if not np.isfinite(bracket_atr_pct):
                        pending = None
                        rejected_warmup += 1
                        continue
                    sl_pct = float(
                        np.clip(
                            execution.dynamic_sl_atr_mult * bracket_atr_pct,
                            execution.dynamic_sl_floor_pct,
                            execution.dynamic_sl_cap_pct,
                        )
                    )
                equity_before = equity
                entry_notional = equity_before * leverage
                quantity = entry_notional / entry_fill
                entry_fee = entry_notional * execution.fee_rate
                cash = equity_before - entry_fee
                if direction == 1:
                    tp = entry_fill * (1.0 + tp_pct)
                    sl = entry_fill * (1.0 - sl_pct)
                else:
                    tp = entry_fill * (1.0 - tp_pct)
                    sl = entry_fill * (1.0 + sl_pct)
                position = {
                    "direction": direction,
                    "entry_i": i,
                    "entry_ts": ts,
                    "raw_entry_price": raw_entry,
                    "entry_fill": entry_fill,
                    "entry_notional": entry_notional,
                    "entry_fee": entry_fee,
                    "quantity": quantity,
                    "leverage": leverage,
                    "equity_before": equity_before,
                    "tp": tp,
                    "sl": sl,
                    "entry_atr_pct": bracket_atr_pct,
                    "tp_pct": tp_pct,
                    "sl_pct": sl_pct,
                    "funding_pnl": 0.0,
                }
            else:
                rejected_warmup += 1
            pending = None

        if position is not None:
            direction = int(position["direction"])
            bracket_active = i - int(position["entry_i"]) >= execution.bracket_delay_bars
            stop_open = bracket_active and ((direction == 1 and open_[i] <= position["sl"]) or (direction == -1 and open_[i] >= position["sl"]))
            target_open = bracket_active and ((direction == 1 and open_[i] >= position["tp"]) or (direction == -1 and open_[i] <= position["tp"]))
            stop_hit = bracket_active and ((direction == 1 and low[i] <= position["sl"]) or (direction == -1 and high[i] >= position["sl"]))
            target_hit = bracket_active and ((direction == 1 and high[i] >= position["tp"]) or (direction == -1 and low[i] <= position["tp"]))
            both_hit = bool(stop_hit and target_hit)
            if both_hit:
                same_bar_conflicts += 1

            exit_reason: str | None = None
            raw_exit: float | None = None
            exit_slippage = execution.slippage_rate
            if stop_open:
                exit_reason = "stop_gap_open"
                raw_exit = open_[i]
                exit_slippage += execution.extra_stop_slippage_rate
            elif target_open:
                exit_reason = "target_gap_open"
                raw_exit = float(position["tp"])
            elif stop_hit:
                exit_reason = "stop_market"
                raw_exit = float(position["sl"])
                exit_slippage += execution.extra_stop_slippage_rate
            elif target_hit:
                exit_reason = "target"
                raw_exit = float(position["tp"])
            elif i - int(position["entry_i"]) >= strategy.max_hold_bars:
                exit_reason = "time_close"
                raw_exit = close[i]

            if exit_reason is not None and raw_exit is not None:
                exit_fill = adverse_fill(raw_exit, direction, is_entry=False, slippage=exit_slippage)
                exit_notional = position["quantity"] * exit_fill
                exit_fee = exit_notional * execution.fee_rate
                gross_pnl = direction * position["quantity"] * (exit_fill - position["entry_fill"])
                equity_after = cash + gross_pnl - exit_fee
                trades.append(
                    {
                        "run": name,
                        "direction": "long" if direction == 1 else "short",
                        "entry_ts": position["entry_ts"],
                        "exit_ts": ts,
                        "raw_entry_price": position["raw_entry_price"],
                        "entry_fill": position["entry_fill"],
                        "raw_exit_price": raw_exit,
                        "exit_fill": exit_fill,
                        "exit_reason": exit_reason,
                        "hold_bars": i - int(position["entry_i"]),
                        "leverage": position["leverage"],
                        "entry_atr_pct": position["entry_atr_pct"],
                        "tp_pct": position["tp_pct"],
                        "sl_pct": position["sl_pct"],
                        "entry_fee": position["entry_fee"],
                        "exit_fee": exit_fee,
                        "funding_pnl": position["funding_pnl"],
                        "both_hit": both_hit,
                        "net_account_return_pct": (equity_after / position["equity_before"] - 1.0) * 100.0,
                        "equity_before": position["equity_before"],
                        "equity_after": equity_after,
                    }
                )
                equity = equity_after
                cash = equity_after
                position = None

        if position is None:
            curve_equity = equity
        else:
            curve_equity = cash + position["direction"] * position["quantity"] * (close[i] - position["entry_fill"])
        curve.append((ts, curve_equity))

        if position is None:
            direction = 1 if long_signal[i] else -1 if short_signal[i] else 0
            if direction:
                pending = (direction, i + 1 + execution.entry_delay_bars)
        elif long_signal[i] or short_signal[i]:
            skipped_signals_in_position += 1

    if position is not None and force_close:
        i = int(active_indices[-1])
        direction = int(position["direction"])
        raw_exit = close[i]
        exit_fill = adverse_fill(raw_exit, direction, is_entry=False, slippage=execution.slippage_rate)
        exit_notional = position["quantity"] * exit_fill
        exit_fee = exit_notional * execution.fee_rate
        gross_pnl = direction * position["quantity"] * (exit_fill - position["entry_fill"])
        equity_after = cash + gross_pnl - exit_fee
        trades.append(
            {
                "run": name,
                "direction": "long" if direction == 1 else "short",
                "entry_ts": position["entry_ts"],
                "exit_ts": index[i],
                "raw_entry_price": position["raw_entry_price"],
                "entry_fill": position["entry_fill"],
                "raw_exit_price": raw_exit,
                "exit_fill": exit_fill,
                "exit_reason": "window_end",
                "hold_bars": i - int(position["entry_i"]),
                "leverage": position["leverage"],
                "entry_atr_pct": position["entry_atr_pct"],
                "tp_pct": position["tp_pct"],
                "sl_pct": position["sl_pct"],
                "entry_fee": position["entry_fee"],
                "exit_fee": exit_fee,
                "funding_pnl": position["funding_pnl"],
                "both_hit": False,
                "net_account_return_pct": (equity_after / position["equity_before"] - 1.0) * 100.0,
                "equity_before": position["equity_before"],
                "equity_after": equity_after,
            }
        )
        equity = equity_after
        if curve:
            curve[-1] = (curve[-1][0], equity_after)

    equity_curve = pd.Series(dict(curve), name=name).sort_index()
    trades_frame = pd.DataFrame(trades)
    return StrictResult(
        name=name,
        metrics=metrics_from_equity(equity_curve, trades_frame),
        slices=base.compute_slices(equity_curve),
        trades=trades_frame,
        equity=equity_curve,
        diagnostics={
            "start": str(start),
            "end": str(end),
            "rejected_warmup_entries": rejected_warmup,
            "skipped_signals_in_position": skipped_signals_in_position,
            "same_bar_conflicts": same_bar_conflicts,
            "force_close": force_close,
            "execution": asdict(execution),
        },
    )


def ready_start(features: pd.DataFrame) -> pd.Timestamp:
    ready = features[["atr96", "upper", "lower"]].notna().all(axis=1)
    ready &= features["long_regime_1h"].notna() & features["short_regime_1h"].notna()
    if not ready.any():
        raise RuntimeError("features never become ready")
    return pd.Timestamp(features.index[ready.argmax()])


def metric_row(label: str, result: StrictResult, **extra: Any) -> dict[str, Any]:
    return {"variant": label, **result.metrics, **extra}


def buy_hold_equity(features: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    frame = features.loc[(features.index >= start) & (features.index < end)]
    if frame.empty:
        return pd.Series(dtype="float64", name="buy_hold")
    entry = float(frame["open"].iloc[0] * (1.0 + SLIPPAGE_PER_FILL))
    quantity = 1.0 / entry
    cash = 1.0 - FEE_PER_FILL
    equity = cash + quantity * (frame["close"] - entry)
    exit_fill = float(frame["close"].iloc[-1] * (1.0 - SLIPPAGE_PER_FILL))
    equity.iloc[-1] = cash + quantity * (exit_fill - entry) - quantity * exit_fill * FEE_PER_FILL
    return equity.rename("buy_hold")


def gate_zero(full: StrictResult, one_x: StrictResult, features: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    hold = buy_hold_equity(features, start, end)
    curves = pd.concat([full.equity.rename("strategy"), one_x.equity.rename("strategy_1x"), hold], axis=1).ffill().dropna()
    daily = curves.resample("1D").last().pct_change().dropna()
    excess = daily["strategy"] - daily["buy_hold"]
    excess_1x = daily["strategy_1x"] - daily["buy_hold"]

    def ir(series: pd.Series) -> float:
        std = float(series.std(ddof=1))
        return float(series.mean() / std * np.sqrt(365)) if std > 0.0 else 0.0

    result = {
        "strategy_return_pct": full.metrics["return_pct"],
        "strategy_1x_return_pct": one_x.metrics["return_pct"],
        "buy_hold_return_pct": float((hold.iloc[-1] / hold.iloc[0] - 1.0) * 100.0),
        "excess_ir": ir(excess),
        "excess_1x_ir": ir(excess_1x),
        "daily_observations": int(len(daily)),
    }
    result["status"] = "pass" if result["excess_ir"] > 0.0 and result["excess_1x_ir"] > 0.0 else "fail"
    return result


def run_ablation(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    variants: list[tuple[str, base.StrategyConfig, ExecutionConfig]] = [
        ("full", strategy, execution),
        ("no_1h_regime", strategy, replace(execution, signal_mode="no_regime")),
        ("regime_only_no_keltner", strategy, replace(execution, signal_mode="regime_only")),
        ("fixed_1x_sizing", replace(strategy, min_leverage=1.0, max_leverage=1.0), execution),
        ("no_take_profit", replace(strategy, take_profit_pct=10.0), execution),
        ("no_stop_loss", replace(strategy, stop_loss_pct=10.0), execution),
        ("no_time_exit", replace(strategy, max_hold_bars=len(features) + 1), execution),
    ]
    rows = []
    for label, cfg, exec_cfg in variants:
        result = simulate(f"ablation_{label}", features, funding, cfg, exec_cfg, start_ts=start, end_ts=end)
        rows.append(metric_row(label, result))
    frame = pd.DataFrame(rows)
    baseline_trades = int(frame.loc[frame["variant"].eq("full"), "trades"].iloc[0])
    frame["trade_count_changed"] = frame["trades"].astype(int).ne(baseline_trades)
    frame.loc[frame["variant"].eq("full"), "trade_count_changed"] = True
    return frame


def run_rolling_oos(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
) -> pd.DataFrame:
    first_oos = data_start + pd.Timedelta(days=70)
    starts = pd.date_range(first_oos, data_end - pd.Timedelta(days=30), freq="7D")
    rows = []
    for idx, start in enumerate(starts):
        end = start + pd.Timedelta(days=30)
        result = simulate(f"oos_{idx:02d}", features, funding, strategy, execution, start_ts=start, end_ts=end)
        rows.append(
            metric_row(
                f"oos_{idx:02d}",
                result,
                is_start=str(start - pd.Timedelta(days=70)),
                gap_start=str(start - pd.Timedelta(days=10)),
                oos_start=str(start),
                oos_end=str(end),
            )
        )
    return pd.DataFrame(rows)


def perturb_bars(frame: pd.DataFrame, rng: np.random.Generator, price_sigma: float = 0.0002) -> pd.DataFrame:
    perturbed = frame.copy()
    scale = np.exp(rng.normal(0.0, price_sigma, len(frame)))
    for column in ["open", "high", "low", "close"]:
        perturbed[column] = frame[column].to_numpy("float64") * scale
    perturbed["high"] = perturbed[["open", "high", "low", "close"]].max(axis=1)
    perturbed["low"] = perturbed[["open", "high", "low", "close"]].min(axis=1)
    return perturbed


def run_mc_kline(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    runs: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for run in range(runs):
        features = base.build_features(perturb_bars(b30, rng), perturb_bars(h1, rng), strategy)
        result = simulate(f"mc1_{run:03d}", features, funding, strategy, execution, start_ts=start, end_ts=end)
        rows.append(metric_row(f"mc1_{run:03d}", result, mc_type="mc1_kline"))
    return pd.DataFrame(rows)


def drawdown_from_returns(returns: np.ndarray) -> float:
    equity = np.r_[1.0, np.cumprod(1.0 + returns)]
    return float((equity / np.maximum.accumulate(equity) - 1.0).min())


def run_trade_mc(trades: pd.DataFrame, runs: int) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 1)
    returns = pd.to_numeric(trades["net_account_return_pct"], errors="coerce").dropna().to_numpy("float64") / 100.0
    rows = []
    for run in range(runs):
        shuffled = rng.permutation(returns)
        rows.append(
            {
                "variant": f"mc2_{run:04d}",
                "mc_type": "mc2_shuffle",
                "return_pct": float((np.prod(1.0 + shuffled) - 1.0) * 100.0),
                "max_drawdown_pct": drawdown_from_returns(shuffled) * 100.0,
            }
        )
        boot = rng.choice(returns, size=len(returns), replace=True)
        rows.append(
            {
                "variant": f"mc3_{run:04d}",
                "mc_type": "mc3_bootstrap",
                "return_pct": float((np.prod(1.0 + boot) - 1.0) * 100.0),
                "max_drawdown_pct": drawdown_from_returns(boot) * 100.0,
                "win_rate_pct": float((boot > 0.0).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def parameter_variants(strategy: base.StrategyConfig) -> list[tuple[str, base.StrategyConfig]]:
    variants = [("baseline", strategy)]
    definitions = {
        "keltner_ema": (8, 12),
        "keltner_atr": (8, 12),
        "keltner_mult": (1.8, 2.2),
        "h1_ema_fast": (14, 18),
        "h1_ema_slow": (42, 54),
        "leverage_atr": (80, 112),
        "atr_target_pct": (0.027, 0.033),
        "take_profit_pct": (0.08, 0.12),
        "stop_loss_pct": (0.02, 0.03),
        "max_hold_bars": (24, 36),
    }
    for field, values in definitions.items():
        for value in values:
            variants.append((f"{field}_{value}", replace(strategy, **{field: value})))
    return variants


def run_parameter_neighborhood(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    for label, cfg in parameter_variants(strategy):
        features = base.build_features(b30, h1, cfg)
        result = simulate(f"mc4_{label}", features, funding, cfg, execution, start_ts=start, end_ts=end)
        rows.append(metric_row(label, result))
    return pd.DataFrame(rows)


def run_stress(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    variants = [
        ("strict_base", execution),
        ("slippage_10bps", replace(execution, slippage_rate=0.0010)),
        ("slippage_20bps", replace(execution, slippage_rate=0.0020)),
        ("stop_extra_10bps", replace(execution, extra_stop_slippage_rate=0.0010)),
        ("stop_extra_20bps", replace(execution, extra_stop_slippage_rate=0.0020)),
        ("entry_delay_1bar", replace(execution, entry_delay_bars=1)),
        ("bracket_delay_1bar", replace(execution, bracket_delay_bars=1)),
        ("no_funding", replace(execution, include_funding=False)),
    ]
    rows = []
    for label, cfg in variants:
        result = simulate(f"stress_{label}", features, funding, strategy, cfg, start_ts=start, end_ts=end)
        rows.append(metric_row(label, result, same_bar_conflicts=result.diagnostics["same_bar_conflicts"]))
    return pd.DataFrame(rows)


def probabilistic_sharpe(daily_returns: pd.Series, benchmark_sharpe: float = 0.0) -> dict[str, float]:
    returns = daily_returns.replace([np.inf, -np.inf], np.nan).dropna()
    n = len(returns)
    if n < 3 or float(returns.std(ddof=1)) <= 0.0:
        return {"observations": float(n), "annualized_sharpe": 0.0, "psr": 0.0, "skew": 0.0, "kurtosis": 0.0, "min_trl_days": float("inf")}
    period_sr = float(returns.mean() / returns.std(ddof=1))
    annualized = period_sr * np.sqrt(365)
    benchmark_period = benchmark_sharpe / np.sqrt(365)
    skew = float(returns.skew())
    kurtosis = float(returns.kurtosis() + 3.0)
    denominator = np.sqrt(max(1e-12, 1.0 - skew * period_sr + ((kurtosis - 1.0) / 4.0) * period_sr**2))
    z = (period_sr - benchmark_period) * np.sqrt(n - 1) / denominator
    psr = NormalDist().cdf(z)
    z95 = NormalDist().inv_cdf(0.95)
    min_trl = 1.0 + (z95 * denominator / max(1e-12, period_sr - benchmark_period)) ** 2
    return {
        "observations": float(n),
        "period_sharpe": period_sr,
        "annualized_sharpe": annualized,
        "psr": psr,
        "skew": skew,
        "kurtosis": kurtosis,
        "min_trl_days": float(min_trl),
    }


def deflated_sharpe(daily_returns: pd.Series, trials: int) -> float:
    returns = daily_returns.replace([np.inf, -np.inf], np.nan).dropna()
    n = len(returns)
    if n < 3 or float(returns.std(ddof=1)) <= 0.0 or trials <= 1:
        return 0.0
    observed = float(returns.mean() / returns.std(ddof=1))
    skew = float(returns.skew())
    kurtosis = float(returns.kurtosis() + 3.0)
    sr_std = np.sqrt(max(1e-12, (1.0 - skew * observed + ((kurtosis - 1.0) / 4.0) * observed**2) / (n - 1)))
    gamma = 0.5772156649015329
    normal = NormalDist()
    expected_max = sr_std * (
        (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / trials)
        + gamma * normal.inv_cdf(1.0 - 1.0 / (trials * np.e))
    )
    denominator = np.sqrt(max(1e-12, 1.0 - skew * observed + ((kurtosis - 1.0) / 4.0) * observed**2))
    z = (observed - expected_max) * np.sqrt(n - 1) / denominator
    return float(normal.cdf(z))


def run_start_sensitivity(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    starts = pd.date_range(start, end - pd.Timedelta(days=90), freq="14D")
    rows = []
    for idx, run_start in enumerate(starts):
        result = simulate(f"start_{idx:02d}", features, funding, strategy, execution, start_ts=run_start, end_ts=end)
        years = max((end - run_start).total_seconds() / (365.0 * 24 * 3600), 1 / 365)
        final_multiple = max(1e-12, 1.0 + result.metrics["return_pct"] / 100.0)
        cagr = final_multiple ** (1.0 / years) - 1.0
        rows.append(metric_row(f"start_{idx:02d}", result, start_ts=str(run_start), cagr_pct=cagr * 100.0))
    return pd.DataFrame(rows)


def phase_features(m1: pd.DataFrame, strategy: base.StrategyConfig) -> tuple[dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
    bars30 = {phase: base.aggregate_ohlcv(m1, freq="30min", phase_min=phase, expected_rows=30)[0] for phase in PHASES_30M}
    bars1h = {phase: base.aggregate_ohlcv(m1, freq="60min", phase_min=phase, expected_rows=60)[0] for phase in PHASES_1H}
    main_h1 = bars1h[0]
    main_30 = bars30[0]
    phase30_features = {phase: base.build_features(frame, main_h1, strategy) for phase, frame in bars30.items()}
    phase1h_features = {phase: base.build_features(main_30, frame, strategy) for phase, frame in bars1h.items()}
    return phase30_features, phase1h_features


def run_phase_gate(
    phase30: dict[int, pd.DataFrame],
    phase1h: dict[int, pd.DataFrame],
    funding: pd.DataFrame,
    strategy: base.StrategyConfig,
    execution: ExecutionConfig,
    starts: list[pd.Timestamp],
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    for dimension, collection in (("30m", phase30), ("1h", phase1h)):
        for phase, features in collection.items():
            for start_idx, run_start in enumerate(starts):
                effective_start = max(run_start, ready_start(features))
                result = simulate(
                    f"phase_{dimension}_{phase}_{start_idx:02d}",
                    features,
                    funding,
                    strategy,
                    execution,
                    start_ts=effective_start,
                    end_ts=end,
                )
                years = max((end - effective_start).total_seconds() / (365.0 * 24 * 3600), 1 / 365)
                final_multiple = max(1e-12, 1.0 + result.metrics["return_pct"] / 100.0)
                cagr = final_multiple ** (1.0 / years) - 1.0
                rows.append(
                    metric_row(
                        f"{dimension}_phase_{phase}_start_{start_idx:02d}",
                        result,
                        dimension=dimension,
                        phase_min=phase,
                        start_ts=str(effective_start),
                        cagr_pct=cagr * 100.0,
                    )
                )
    return pd.DataFrame(rows)


def summarize_distribution(frame: pd.DataFrame, value: str) -> dict[str, float]:
    series = pd.to_numeric(frame[value], errors="coerce").dropna()
    if series.empty:
        return {}
    return {
        "count": float(len(series)),
        "min": float(series.min()),
        "p05": float(series.quantile(0.05)),
        "median": float(series.median()),
        "p95": float(series.quantile(0.95)),
        "max": float(series.max()),
        "positive_fraction": float(series.gt(0.0).mean()),
    }


def phase_gate_status(phase_results: pd.DataFrame, dimension: str) -> dict[str, Any]:
    subset = phase_results.loc[phase_results["dimension"].eq(dimension)].copy()
    by_phase = subset.groupby("phase_min").agg(
        median_cagr_pct=("cagr_pct", "median"),
        median_mdd_pct=("max_drawdown_pct", "median"),
        positive_fraction=("return_pct", lambda values: float((values > 0.0).mean())),
    )
    native = by_phase.loc[0]
    non_native = by_phase.drop(index=0)
    median_non_native_cagr = float(non_native["median_cagr_pct"].median())
    cagr_ratio = median_non_native_cagr / float(native["median_cagr_pct"]) if float(native["median_cagr_pct"]) != 0.0 else float("-inf")
    mdd_ratio = abs(float(non_native["median_mdd_pct"].median())) / max(1e-12, abs(float(native["median_mdd_pct"])))
    cagr_values = by_phase["median_cagr_pct"].to_numpy("float64")
    cv = float(np.std(cagr_values, ddof=1) / abs(np.mean(cagr_values))) if len(cagr_values) > 1 and np.mean(cagr_values) != 0.0 else float("inf")
    status = "pass" if median_non_native_cagr > 0.0 and cagr_ratio >= 0.60 and mdd_ratio <= 1.5 and cv < 0.5 else "fail"
    return {
        "status": status,
        "native_median_cagr_pct": float(native["median_cagr_pct"]),
        "non_native_median_cagr_pct": median_non_native_cagr,
        "non_native_to_native_ratio": cagr_ratio,
        "non_native_mdd_ratio": mdd_ratio,
        "cross_phase_cagr_cv": cv,
        "phase_table": by_phase.reset_index().to_dict(orient="records"),
    }


def gate_rows(gates: dict[str, dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gate": gate,
                "status": details.get("status", "incomplete"),
                "summary": details.get("summary", ""),
            }
            for gate, details in gates.items()
        ]
    )


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    base_args = argparse.Namespace(
        since=args.since,
        until=args.until,
        refresh_cache=args.refresh_data,
        timeout=args.timeout,
    )
    m1 = base.load_or_fetch_1m(base_args)
    funding = load_or_fetch_funding(args, m1)
    raw_lake, normalized_lake = load_standard_lake_1m()
    data_quality = audit_data_quality(m1, raw_lake, normalized_lake)

    strategy = base.StrategyConfig()
    execution = ExecutionConfig()
    b30 = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)[0]
    h1 = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)[0]
    features = base.build_features(b30, h1, strategy)
    start = ready_start(features)
    end = features.index.max() + pd.Timedelta(minutes=30)

    full = simulate("strict_full", features, funding, strategy, execution, start_ts=start, end_ts=end)
    one_x = simulate(
        "strict_1x",
        features,
        funding,
        replace(strategy, min_leverage=1.0, max_leverage=1.0),
        execution,
        start_ts=start,
        end_ts=end,
    )
    gate0 = gate_zero(full, one_x, features, start, end)

    ablation = run_ablation(features, funding, strategy, execution, start, end)
    alpha_variants = ablation.loc[ablation["variant"].isin(["no_1h_regime", "regime_only_no_keltner"])]
    gate1_status = "pass" if bool(alpha_variants["trade_count_changed"].all()) else "fail"

    oos = run_rolling_oos(features, funding, strategy, execution, start, end)
    oos_positive = float(oos["return_pct"].gt(0.0).mean()) if len(oos) else 0.0
    oos_zero_trade = int(oos["trades"].eq(0).sum()) if len(oos) else 0
    gate2_status = "pass" if len(oos) >= 30 and oos_positive >= 0.60 and oos_zero_trade == 0 else "fail"

    mc1 = run_mc_kline(b30, h1, funding, strategy, execution, start, end, args.mc_kline_runs)
    mc23 = run_trade_mc(full.trades, args.mc_trade_runs)
    params = run_parameter_neighborhood(b30, h1, funding, strategy, execution, start, end)
    mc1_positive = float(mc1["return_pct"].gt(0.0).mean())
    mc2 = mc23.loc[mc23["mc_type"].eq("mc2_shuffle")]
    mc2_mdd_p05 = float(mc2["max_drawdown_pct"].quantile(0.05))
    mc2_mdd_limit = 1.5 * abs(float(full.metrics["max_drawdown_pct"]))
    mc3 = mc23.loc[mc23["mc_type"].eq("mc3_bootstrap")]
    mc3_p05 = float(mc3["return_pct"].quantile(0.05))
    param_positive = float(params["return_pct"].gt(0.0).mean())
    gate3_status = (
        "pass"
        if mc1_positive >= 0.80
        and mc2_mdd_p05 >= -mc2_mdd_limit
        and mc3_p05 > 0.0
        and param_positive >= 0.80
        else "fail"
    )
    mc = pd.concat([mc1, mc23], ignore_index=True, sort=False)

    stress = run_stress(features, funding, strategy, execution, start, end)
    quantitative_stress_pass = bool(stress["return_pct"].gt(0.0).all() and stress["max_drawdown_pct"].gt(-50.0).all())
    gate4_status = "incomplete"

    daily_returns = full.equity.resample("1D").last().pct_change().dropna()
    significance = probabilistic_sharpe(daily_returns)
    significance["dsr_n100"] = deflated_sharpe(daily_returns, 100)
    significance["dsr_n500"] = deflated_sharpe(daily_returns, 500)
    significance["dsr_n1000"] = deflated_sharpe(daily_returns, 1000)
    gate5_status = "pass" if significance["psr"] >= 0.95 and significance["dsr_n1000"] >= 0.95 and significance["observations"] >= significance["min_trl_days"] else "fail"

    starts = run_start_sensitivity(features, funding, strategy, execution, start, end)
    start_positive = float(starts["return_pct"].gt(0.0).mean())
    cagr_mean = float(starts["cagr_pct"].mean())
    cagr_cv = float(starts["cagr_pct"].std(ddof=1) / abs(cagr_mean)) if cagr_mean != 0.0 else float("inf")
    start_mdd_ratio = abs(float(starts["max_drawdown_pct"].min())) / max(1e-12, abs(float(starts["max_drawdown_pct"].median())))
    gate6_status = "pass" if start_positive >= 0.90 and cagr_cv < 0.5 and start_mdd_ratio <= 1.5 else "fail"

    phase30, phase1h = phase_features(m1, strategy)
    phase_starts = [pd.Timestamp(value) for value in starts["start_ts"].iloc[:20]]
    phases = run_phase_gate(phase30, phase1h, funding, strategy, execution, phase_starts, end)
    phase30_gate = phase_gate_status(phases, "30m")
    phase1h_gate = phase_gate_status(phases, "1h")
    gate7_status = "pass" if phase30_gate["status"] == "pass" and phase1h_gate["status"] == "pass" else "fail"

    gates = {
        "data_quality_precondition": {
            "status": "pass" if data_quality["gate_pass"] else "fail",
            "summary": "完整样本进入标准 data lake，raw/normalized/cache 对齐且 schema 完整。" if data_quality["gate_pass"] else "完整样本未全部进入标准 data lake 或 schema/对齐证据不完整。",
            "details": data_quality,
        },
        "gate_0_excess_return": {
            "status": gate0["status"],
            "summary": f"策略与 1x 策略相对 buy-and-hold 的日频 IR 分别为 {gate0['excess_ir']:.2f} / {gate0['excess_1x_ir']:.2f}。",
            "details": gate0,
        },
        "gate_1_ablation": {
            "status": gate1_status,
            "summary": "核心入场部件消融均改变成交序列；风险部件结果见完整表。" if gate1_status == "pass" else "至少一个核心部件消融未改变成交序列。",
            "details": ablation.to_dict(orient="records"),
        },
        "gate_2_oos_cpcv": {
            "status": gate2_status,
            "summary": f"滚动 OOS {len(oos)} 组，正收益占比 {oos_positive:.1%}，零交易窗口 {oos_zero_trade}。",
            "details": {
                "windows": int(len(oos)),
                "positive_fraction": oos_positive,
                "zero_trade_windows": oos_zero_trade,
                "return_distribution": summarize_distribution(oos, "return_pct"),
            },
        },
        "gate_3_monte_carlo": {
            "status": gate3_status,
            "summary": f"K 线扰动正收益 {mc1_positive:.1%}；交易重排 MDD p05 {mc2_mdd_p05:.2f}%（上限 -{mc2_mdd_limit:.2f}%）；bootstrap 收益 p05 {mc3_p05:.2f}%；参数邻域正收益 {param_positive:.1%}。",
            "details": {
                "mc1_return": summarize_distribution(mc1, "return_pct"),
                "mc2_mdd": summarize_distribution(mc2, "max_drawdown_pct"),
                "mc2_mdd_p05_limit_pct": -mc2_mdd_limit,
                "mc3_return": summarize_distribution(mc3, "return_pct"),
                "parameter_return": summarize_distribution(params, "return_pct"),
            },
        },
        "gate_4_stress": {
            "status": gate4_status,
            "summary": f"量化压力测试 {'通过' if quantitative_stress_pass else '未通过'}；拒单、断流恢复、保护单失败和仓位恢复需 runner 状态机，研究脚本无法给出通过证据。",
            "details": {
                "quantitative_pass": quantitative_stress_pass,
                "variants": stress.to_dict(orient="records"),
                "operational_blockers": ["order_rejection", "data_disconnect_recovery", "protective_order_failure", "restart_position_reconciliation", "kill_switch"],
            },
        },
        "gate_5_significance": {
            "status": gate5_status,
            "summary": f"PSR {significance['psr']:.4f}，DSR(N=1000) {significance['dsr_n1000']:.4f}，样本 {int(significance['observations'])} 天。",
            "details": significance,
        },
        "gate_6_start_time": {
            "status": gate6_status,
            "summary": f"{len(starts)} 个起跑点，正收益 {start_positive:.1%}，CAGR CV {cagr_cv:.3f}，MDD ratio {start_mdd_ratio:.3f}。",
            "details": {
                "starts": int(len(starts)),
                "positive_fraction": start_positive,
                "cagr_cv": cagr_cv,
                "mdd_ratio": start_mdd_ratio,
                "cagr_distribution": summarize_distribution(starts, "cagr_pct"),
            },
        },
        "gate_7_phase": {
            "status": gate7_status,
            "summary": f"30m phase={phase30_gate['status']}，1h phase={phase1h_gate['status']}。",
            "details": {"30m": phase30_gate, "1h": phase1h_gate},
        },
        "live_executable": {
            "status": "incomplete",
            "summary": "研究回放已覆盖 next-open、gap-stop、同 bar SL 优先和 bracket delay；OCO/reduce-only、拒单、重启恢复、missing-bar fail-closed 尚无 runner 证据。",
            "details": {
                "covered": ["closed_bar_signal", "next_bar_entry", "adverse_entry_exit_slippage", "stop_gap_open", "same_bar_stop_first", "entry_bar_bracket", "funding"],
                "blockers": ["runner_state_machine_parity", "oco_reduce_only", "order_rejection", "restart_recovery", "missing_bar_fail_closed", "kill_switch"],
            },
        },
    }
    overall = "not_promoted_not_live_ready" if any(item["status"] != "pass" for item in gates.values()) else "eligible_for_promotion_review"

    summary = {
        "strategy_family": "HYPE-30M-Keltner-Trend-Breakout",
        "strategy_id": "K2-FQ-V2-ATRVT-OFF external observation",
        "run_date": RUN_DATE,
        "status": "explore / not promoted / not live-ready",
        "overall_decision": overall,
        "data_range": {"start": str(pd.to_datetime(m1["ts"], utc=True).min()), "end": str(pd.to_datetime(m1["ts"], utc=True).max()), "rows": int(len(m1))},
        "cost_model": {"fee_per_fill": FEE_PER_FILL, "slippage_per_fill": SLIPPAGE_PER_FILL, "combined_nominal_per_fill": FEE_PER_FILL + SLIPPAGE_PER_FILL},
        "funding": {
            "included": True,
            "rows": int(len(funding)),
            "start": str(funding["ts"].min()) if len(funding) else None,
            "end": str(funding["ts"].max()) if len(funding) else None,
            "null_rates": int(funding["funding_rate"].isna().sum()) if len(funding) else 0,
        },
        "strict_headline": {"metrics": full.metrics, "slices": full.slices, "diagnostics": full.diagnostics},
        "gates": gates,
    }

    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    full.trades.to_csv(TRADES_PATH, index=False)
    gate_rows(gates).to_csv(GATES_PATH, index=False)
    oos.to_csv(OOS_PATH, index=False)
    ablation.to_csv(ABLATION_PATH, index=False)
    stress.to_csv(STRESS_PATH, index=False)
    phases.to_csv(PHASE_PATH, index=False)
    starts.to_csv(START_PATH, index=False)
    params.to_csv(PARAM_PATH, index=False)
    mc.to_csv(MC_PATH, index=False)

    print("data", summary["data_range"])
    print("funding", summary["funding"])
    print("strict", full.metrics)
    for gate, details in gates.items():
        print(f"{gate:>28}: {details['status']:<10} {details['summary']}")
    print("overall", overall)
    print("summary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
