from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FIVE_M_SCRIPT_DIR = ROOT / "research/hype/5m-pullback-trail/scripts"
THIS_DIR = ROOT / "research/hype/15m-pullback-trail/scripts"
for path in (FIVE_M_SCRIPT_DIR, THIS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from research_hype_15m_pbtr_v33_migration import (  # noqa: E402
    json_safe,
    resample_15m_from_5m,
    verify_5m_data,
)
from research_hype_5m_indicator_search import Trade  # noqa: E402
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (  # noqa: E402
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m  # noqa: E402


DATE_TAG = "2026-06-30"
FAMILY_DIR = ROOT / "research/hype/15m-pullback-trail"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAG_DIR = FAMILY_DIR / "diagnostics"

REPORT_JSON = ARTIFACT_DIR / f"hype_15m_pbtr_bracket_search_{DATE_TAG}.json"
PRESCREEN_CSV = ARTIFACT_DIR / f"hype_15m_pbtr_bracket_search_prescreen_{DATE_TAG}.csv"
SUMMARY_CSV = ARTIFACT_DIR / f"hype_15m_pbtr_bracket_search_summary_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"hype_15m_pbtr_bracket_search_slices_{DATE_TAG}.csv"
MONTHLY_CSV = ARTIFACT_DIR / f"hype_15m_pbtr_bracket_search_monthly_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_15m_pbtr_bracket_search_best_trades_{DATE_TAG}.csv"
REPORT_MD = DIAG_DIR / f"hype-15m-pullback-trail-bracket-search-{DATE_TAG}.md"

LEVERAGE = 1.0
IS_END = pd.Timestamp("2026-03-01T00:00:00Z")
VAL_END = pd.Timestamp("2026-06-01T00:00:00Z")
MIN_FULL_TRADES = 50
MIN_OOS_TRADES = 5
PRESCREEN_TOP = 60


@dataclass(frozen=True, slots=True)
class SignalSpec:
    ema_fast: int
    ema_slow: int
    pullback_buffer: float
    side_mode: str
    require_candle: bool

    @property
    def label(self) -> str:
        candle = "candle" if self.require_candle else "nocandle"
        return f"ema{self.ema_fast}_{self.ema_slow}_pb{self.pullback_buffer:g}_{self.side_mode}_{candle}"


@dataclass(frozen=True, slots=True)
class FilterSpec:
    ret_window: int | None = None
    min_dir_ret_bps: float | None = None
    min_htf_bps: float | None = None
    min_ema_spread_bps: float | None = None
    max_abs_dist_fast_bps: float | None = None
    min_body_atr: float | None = None
    min_pullback_atr: float | None = None
    min_vol_ratio: float | None = None
    max_atr_bps: float | None = None

    @property
    def label(self) -> str:
        parts: list[str] = []
        if self.ret_window is not None and self.min_dir_ret_bps is not None:
            parts.append(f"ret{self.ret_window}>={self.min_dir_ret_bps:g}")
        if self.min_htf_bps is not None:
            parts.append(f"htf>={self.min_htf_bps:g}")
        if self.min_ema_spread_bps is not None:
            parts.append(f"spread>={self.min_ema_spread_bps:g}")
        if self.max_abs_dist_fast_bps is not None:
            parts.append(f"dist<={self.max_abs_dist_fast_bps:g}")
        if self.min_body_atr is not None:
            parts.append(f"body>={self.min_body_atr:g}")
        if self.min_pullback_atr is not None:
            parts.append(f"pbatr>={self.min_pullback_atr:g}")
        if self.min_vol_ratio is not None:
            parts.append(f"vol>={self.min_vol_ratio:g}")
        if self.max_atr_bps is not None:
            parts.append(f"atrbps<={self.max_atr_bps:g}")
        return "all" if not parts else "__".join(parts)


@dataclass(frozen=True, slots=True)
class ExitSpec:
    tp_atr: float
    sl_atr: float
    timeout_bars: int

    @property
    def label(self) -> str:
        return f"tp{self.tp_atr:g}_sl{self.sl_atr:g}_tx{self.timeout_bars}"


def pct(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    open_ = result["open"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    for span in (7, 14, 21, 32, 34, 55, 64, 96, 144, 192, 384):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    result["atr14"] = tr.rolling(14, min_periods=14).mean()
    result["atr_bps"] = result["atr14"] / close * 10000.0
    result["range_atr"] = (high - low) / result["atr14"]
    result["body_atr"] = (close - open_).abs() / result["atr14"]
    result["body_bps"] = (close / open_ - 1.0) * 10000.0
    result["vol_ratio_96"] = result["volume"] / result["volume"].rolling(96, min_periods=96).mean()
    result["ema96_384_spread_bps"] = (result["ema96"] - result["ema384"]) / close * 10000.0
    for window in (8, 16, 32, 64, 96, 192):
        result[f"ret{window}_bps"] = (close / close.shift(window) - 1.0) * 10000.0
    return result


def build_signal(frame: pd.DataFrame, spec: SignalSpec) -> np.ndarray:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{spec.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{spec.ema_slow}"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    if spec.side_mode == "long":
        direction = np.where(direction > 0, 1, 0).astype(np.int8)
    elif spec.side_mode == "short":
        direction = np.where(direction < 0, -1, 0).astype(np.int8)
    elif spec.side_mode != "both":
        raise ValueError(f"unknown side_mode={spec.side_mode}")
    touched = np.where(
        direction > 0,
        low <= ema_fast * (1.0 + spec.pullback_buffer),
        high >= ema_fast * (1.0 - spec.pullback_buffer),
    )
    reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
    mask = (direction != 0) & touched & reclaimed & np.isfinite(atr)
    if spec.require_candle:
        candle = np.where(direction > 0, close > open_, close < open_)
        mask &= candle
    signal = np.zeros(len(frame), dtype=np.int8)
    valid = np.nan_to_num(mask, nan=False).astype(bool)
    signal[valid] = direction[valid]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def filter_signal(frame: pd.DataFrame, signal: np.ndarray, spec: SignalSpec, filt: FilterSpec) -> np.ndarray:
    idx = np.flatnonzero(signal)
    if len(idx) == 0:
        return signal.copy()
    side = signal[idx].astype("float64")
    close = frame["close"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    ema_fast = frame[f"ema{spec.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{spec.ema_slow}"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    keep = np.ones(len(idx), dtype=bool)
    if filt.ret_window is not None and filt.min_dir_ret_bps is not None:
        values = side * frame[f"ret{filt.ret_window}_bps"].to_numpy("float64")[idx]
        keep &= np.isfinite(values) & (values >= filt.min_dir_ret_bps)
    if filt.min_htf_bps is not None:
        values = side * frame["ema96_384_spread_bps"].to_numpy("float64")[idx]
        keep &= np.isfinite(values) & (values >= filt.min_htf_bps)
    if filt.min_ema_spread_bps is not None:
        values = side * (ema_fast[idx] - ema_slow[idx]) / close[idx] * 10000.0
        keep &= np.isfinite(values) & (values >= filt.min_ema_spread_bps)
    if filt.max_abs_dist_fast_bps is not None:
        values = np.abs(close[idx] / ema_fast[idx] - 1.0) * 10000.0
        keep &= np.isfinite(values) & (values <= filt.max_abs_dist_fast_bps)
    if filt.min_body_atr is not None:
        values = side * (frame["close"].to_numpy("float64")[idx] - frame["open"].to_numpy("float64")[idx]) / atr[idx]
        keep &= np.isfinite(values) & (values >= filt.min_body_atr)
    if filt.min_pullback_atr is not None:
        values = np.where(side > 0, (ema_fast[idx] - low[idx]) / atr[idx], (high[idx] - ema_fast[idx]) / atr[idx])
        keep &= np.isfinite(values) & (values >= filt.min_pullback_atr)
    if filt.min_vol_ratio is not None:
        values = frame["vol_ratio_96"].to_numpy("float64")[idx]
        keep &= np.isfinite(values) & (values >= filt.min_vol_ratio)
    if filt.max_atr_bps is not None:
        values = frame["atr_bps"].to_numpy("float64")[idx]
        keep &= np.isfinite(values) & (values <= filt.max_atr_bps)
    filtered = np.zeros_like(signal)
    filtered[idx[keep]] = signal[idx[keep]]
    return filtered


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return bool(open_price <= stop_price if side > 0 else open_price >= stop_price)


def crossed_target(open_price: float, target_price: float, side: int) -> bool:
    return bool(open_price >= target_price if side > 0 else open_price <= target_price)


def touched_stop(high_price: float, low_price: float, stop_price: float, side: int) -> bool:
    return bool(low_price <= stop_price if side > 0 else high_price >= stop_price)


def touched_target(high_price: float, low_price: float, target_price: float, side: int) -> bool:
    return bool(high_price >= target_price if side > 0 else low_price <= target_price)


def apply_exit_cost(raw_exit_price: float, side: int) -> float:
    return float(raw_exit_price * (1.0 - side * EXIT_SLIPPAGE_RATE))


def simulate_bracket(frame: pd.DataFrame, signal: np.ndarray, exit_spec: ExitSpec, label: str) -> list[Trade]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)
    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if side == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        target_price = entry_price + side * exit_spec.tp_atr * signal_atr
        stop_price = entry_price - side * exit_spec.sl_atr * signal_atr
        exit_i = min(n - 1, entry_i + exit_spec.timeout_bars)
        raw_exit_price = float(open_[exit_i])
        reason = "time_open"
        for bar_i in range(entry_i, min(n, entry_i + exit_spec.timeout_bars + 1)):
            if crossed_stop(float(open_[bar_i]), stop_price, side):
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "stop_gap_open"
                break
            if crossed_target(float(open_[bar_i]), target_price, side):
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target_gap_or_open"
                break
            if bar_i == entry_i + exit_spec.timeout_bars:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "time_open"
                break
            stop_hit = touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side)
            target_hit = touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side)
            if stop_hit and target_hit:
                exit_i = bar_i
                raw_exit_price = float(stop_price)
                reason = "both_hit_stop_first"
                break
            if stop_hit:
                exit_i = bar_i
                raw_exit_price = float(stop_price)
                reason = "stop_market"
                break
            if target_hit:
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target"
                break
        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        if len(path_high) == 0:
            continue
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
        exit_price = apply_exit_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        trades.append(
            Trade(
                config=label,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i
    return trades


def metric_from_trades(trades: list[Trade], *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected:
        return {
            "trades": 0,
            "total_return": 0.0,
            "annualized_multiple": 1.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "payoff_ratio": 0.0,
            "avg_trade": 0.0,
            "max_dd": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "avg_bars_held": 0.0,
        }
    raw_rets = np.array([trade.net_ret_1x for trade in selected], dtype=float)
    rets = raw_rets * LEVERAGE
    maes = np.array([trade.mae_1x * LEVERAGE for trade in selected], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret, mae in zip(rets, maes, strict=True):
        trough = equity * max(0.001, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(0.001, 1.0 + ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    wins = raw_rets[raw_rets > 0]
    losses = raw_rets[raw_rets <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss_abs = float(abs(losses.mean())) if len(losses) else 0.0
    payoff = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    return {
        "trades": int(len(selected)),
        "total_return": float(equity - 1.0),
        "annualized_multiple": float(equity ** (365.25 / days)) if equity > 0 else 0.0,
        "win_rate": float((raw_rets > 0).mean()),
        "profit_factor": pf,
        "payoff_ratio": payoff,
        "avg_trade": float(rets.mean()),
        "max_dd": float(max_dd),
        "long_trades": int(sum(1 for trade in selected if trade.side > 0)),
        "short_trades": int(sum(1 for trade in selected if trade.side < 0)),
        "avg_bars_held": float(np.mean([trade.bars_held for trade in selected])),
    }


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=15)
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "is_2025_05_30_to_2026_03_01", "start": start, "end": IS_END},
        {"name": "val_2026_03_01_to_2026_06_01", "start": IS_END, "end": VAL_END},
        {"name": "oos_2026_06_01_to_latest", "start": VAL_END, "end": end},
        {"name": "slice_2025_05_30_to_2025_09_01", "start": start, "end": pd.Timestamp("2025-09-01T00:00:00Z")},
        {"name": "slice_2025_09_01_to_2025_12_01", "start": pd.Timestamp("2025-09-01T00:00:00Z"), "end": pd.Timestamp("2025-12-01T00:00:00Z")},
        {"name": "slice_2025_12_01_to_2026_03_01", "start": pd.Timestamp("2025-12-01T00:00:00Z"), "end": IS_END},
        {"name": "slice_2026_03_01_to_2026_06_01", "start": IS_END, "end": VAL_END},
    ]


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=15)
    periods = pd.period_range(start.tz_convert(None).to_period("M"), (end - pd.Timedelta(minutes=15)).tz_convert(None).to_period("M"), freq="M")
    rows: list[dict[str, Any]] = []
    for period in periods:
        left = max(start, pd.Timestamp(period.start_time, tz="UTC"))
        right = min(end, pd.Timestamp((period + 1).start_time, tz="UTC"))
        if left < right:
            rows.append({"name": str(period), "start": left, "end": right})
    return rows


def summarize(label: str, signal_count: int, trades: list[Trade], signal_spec: SignalSpec, filter_spec: FilterSpec, exit_spec: ExitSpec, frame: pd.DataFrame, stage: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slices = validation_slices(frame)
    row: dict[str, Any] = {
        "label": label,
        "stage": stage,
        "signal_count": signal_count,
        "signal_spec": signal_spec.label,
        "filter_spec": filter_spec.label,
        "exit_spec": exit_spec.label,
        **{f"signal_{k}": v for k, v in asdict(signal_spec).items()},
        **{f"filter_{k}": v for k, v in asdict(filter_spec).items()},
        **{f"exit_{k}": v for k, v in asdict(exit_spec).items()},
    }
    slice_rows: list[dict[str, Any]] = []
    for item in slices:
        metrics = metric_from_trades(trades, start=item["start"], end=item["end"])
        slice_rows.append({"label": label, "stage": stage, "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
        prefix = item["name"]
        for key, value in metrics.items():
            row[f"{prefix}_{key}"] = value
    reasons: dict[str, int] = {}
    for trade in trades:
        reasons[trade.reason] = reasons.get(trade.reason, 0) + 1
    row["reason_counts"] = json.dumps(reasons, ensure_ascii=False, sort_keys=True)
    row["score"] = balanced_score(row)
    row["balanced_pass"] = balanced_pass(row)
    return row, slice_rows


def balanced_score(row: dict[str, Any]) -> float:
    full_return = float(row.get("full_total_return", 0.0))
    full_pf = float(row.get("full_profit_factor", 0.0))
    full_win = float(row.get("full_win_rate", 0.0))
    full_payoff = float(row.get("full_payoff_ratio", 0.0))
    full_dd = float(row.get("full_max_dd", 0.0))
    is_pf = float(row.get("is_2025_05_30_to_2026_03_01_profit_factor", 0.0))
    val_pf = float(row.get("val_2026_03_01_to_2026_06_01_profit_factor", 0.0))
    oos_pf = float(row.get("oos_2026_06_01_to_latest_profit_factor", 0.0))
    if not np.isfinite(full_pf):
        full_pf = 5.0
    if not np.isfinite(full_payoff):
        full_payoff = 5.0
    for name, value in (("is_pf", is_pf), ("val_pf", val_pf), ("oos_pf", oos_pf)):
        if not np.isfinite(value):
            locals()[name] = 5.0
    slice_pf_floor = min(is_pf if np.isfinite(is_pf) else 5.0, val_pf if np.isfinite(val_pf) else 5.0, oos_pf if np.isfinite(oos_pf) else 5.0)
    dd_penalty = max(0.0, abs(full_dd) - 0.20) * 80.0
    trade_penalty = max(0.0, MIN_FULL_TRADES - float(row.get("full_trades", 0))) / MIN_FULL_TRADES * 20.0
    oos_penalty = max(0.0, MIN_OOS_TRADES - float(row.get("oos_2026_06_01_to_latest_trades", 0))) / MIN_OOS_TRADES * 15.0
    return (
        min(full_return, 2.0) * 35.0
        + min(full_pf, 2.5) * 22.0
        + full_win * 20.0
        + min(full_payoff, 2.5) * 10.0
        + min(slice_pf_floor, 2.0) * 18.0
        + full_dd * 35.0
        - dd_penalty
        - trade_penalty
        - oos_penalty
    )


def balanced_pass(row: dict[str, Any]) -> bool:
    return (
        int(row.get("full_trades", 0)) >= MIN_FULL_TRADES
        and int(row.get("oos_2026_06_01_to_latest_trades", 0)) >= MIN_OOS_TRADES
        and float(row.get("full_total_return", 0.0)) > 0.15
        and float(row.get("full_profit_factor", 0.0)) >= 1.15
        and float(row.get("full_win_rate", 0.0)) >= 0.45
        and float(row.get("full_payoff_ratio", 0.0)) >= 0.80
        and float(row.get("full_max_dd", 0.0)) > -0.30
        and float(row.get("is_2025_05_30_to_2026_03_01_profit_factor", 0.0)) >= 1.05
        and float(row.get("val_2026_03_01_to_2026_06_01_profit_factor", 0.0)) >= 0.95
        and float(row.get("oos_2026_06_01_to_latest_profit_factor", 0.0)) >= 0.85
    )


def signal_specs() -> list[SignalSpec]:
    specs: list[SignalSpec] = []
    for ema_fast, ema_slow in ((7, 32), (21, 96), (34, 144)):
        for pullback_buffer in (0.01, 0.015):
            for side_mode in ("both", "long", "short"):
                for require_candle in (True, False):
                    specs.append(SignalSpec(ema_fast, ema_slow, pullback_buffer, side_mode, require_candle))
    return specs


def filter_specs() -> list[FilterSpec]:
    specs: list[FilterSpec] = [FilterSpec()]
    for window in (32, 64, 96):
        for threshold in (0.0, 300.0, 600.0):
            specs.append(FilterSpec(ret_window=window, min_dir_ret_bps=threshold))
            specs.append(FilterSpec(ret_window=window, min_dir_ret_bps=threshold, min_htf_bps=0.0))
    for threshold in (0.0, 50.0, 100.0):
        specs.append(FilterSpec(min_htf_bps=threshold))
    for window in (32, 64):
        for threshold in (300.0, 600.0):
            specs.append(FilterSpec(ret_window=window, min_dir_ret_bps=threshold, min_htf_bps=0.0, min_body_atr=0.05))
            specs.append(FilterSpec(ret_window=window, min_dir_ret_bps=threshold, min_htf_bps=0.0, min_pullback_atr=0.10))
            specs.append(FilterSpec(ret_window=window, min_dir_ret_bps=threshold, min_htf_bps=0.0, min_vol_ratio=0.8))
    for max_atr in (240.0, 320.0):
        specs.append(FilterSpec(max_atr_bps=max_atr))
    unique: dict[str, FilterSpec] = {}
    for spec in specs:
        unique[spec.label] = spec
    return list(unique.values())


def prescreen_exit_specs() -> list[ExitSpec]:
    return [
        ExitSpec(1.5, 2.0, 8),
        ExitSpec(2.0, 3.0, 8),
        ExitSpec(2.5, 3.0, 12),
        ExitSpec(3.0, 4.0, 16),
        ExitSpec(4.0, 5.0, 24),
        ExitSpec(5.0, 7.0, 24),
    ]


def full_exit_specs() -> list[ExitSpec]:
    specs: list[ExitSpec] = []
    for tp in (1.5, 2.0, 2.5, 3.0, 4.0):
        for sl in (2.0, 3.0, 4.0, 5.0, 7.0):
            for timeout in (8, 12, 16, 24):
                specs.append(ExitSpec(tp, sl, timeout))
    return specs


def trades_to_frame(trades: list[Trade], label: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "label": label,
                "trade_no": index + 1,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "reason": trade.reason,
            }
            for index, trade in enumerate(trades)
        ]
    )


def render_markdown(data_quality: dict[str, Any], prescreen: pd.DataFrame, summary: pd.DataFrame, slices: pd.DataFrame, monthly: pd.DataFrame) -> str:
    final = summary.sort_values(["balanced_pass", "score", "full_total_return"], ascending=False).copy()
    passed = final[final["balanced_pass"]].copy()
    top = final.head(12)
    best = final.iloc[0]
    best_slices = slices[slices["label"] == best["label"]].copy()
    best_monthly = monthly[monthly["label"] == best["label"]].copy()
    positive_months = int((best_monthly["total_return"] > 0).sum()) if len(best_monthly) else 0
    worst_month = best_monthly.sort_values("total_return").iloc[0] if len(best_monthly) else None
    lines = [
        "# HYPE-15M-Pullback-Trail bracket 可执行搜索 2026-06-30",
        "",
        "Family id：`HYPE-15M-Pullback-Trail`",
        "",
        "本报告把 15m 回踩/恢复信号只当作事件源，放弃旧 V3.3 的 delayed trailing，重新搜索入场即可挂出的固定 TP/SL bracket 与 timeout 退出。",
        "",
        "## 数据与执行口径",
        "",
        f"- 数据源：本地标准数据湖 Binance HYPEUSDT USD-M Futures `5m`，补齐后重采样为闭合 `15m`。",
        f"- 5m 范围：`{data_quality['raw_5m']['start']}` -> `{data_quality['raw_5m']['end']}`，行数 `{data_quality['raw_5m']['rows']}`，缺口 `{data_quality['raw_5m']['missing_5m_bars']}`。",
        f"- 15m 范围：`{data_quality['resampled_15m']['start']}` -> `{data_quality['resampled_15m']['end']}`，行数 `{data_quality['resampled_15m']['rows']}`，缺口 `{data_quality['resampled_15m']['missing_15m_bars']}`。",
        f"- 成本：手续费 `{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`，入场滑点 `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，出场滑点 `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "- 信号：已收盘 15m K 确认，下一根 15m open 成交；持仓期间忽略新信号。",
        "- 退出：入场后立即有 reduce-only TP/SL；同根同时触及按 stop first；开盘跳过 TP/SL 按 open/目标价保守处理；timeout 到期按开盘市价退出。",
        "",
        "## 搜索规模",
        "",
        f"- prescreen 行数：`{len(prescreen)}`。",
        f"- full refine 行数：`{len(summary)}`。",
        f"- balanced pass：`{len(passed)}/{len(summary)}`。",
        "",
        "## 前排结果",
        "",
        "| label | pass | 交易数 | 收益 | 年化 | 胜率 | PF | payoff | 回撤 | OOS交易 | OOS PF |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{bool(row['balanced_pass'])}` | `{int(row['full_trades'])}` | `{pct(float(row['full_total_return']))}` | "
            f"`{mult(float(row['full_annualized_multiple']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_profit_factor']))}` | "
            f"`{num(float(row['full_payoff_ratio']))}` | `{pct(float(row['full_max_dd']))}` | "
            f"`{int(row['oos_2026_06_01_to_latest_trades'])}` | `{num(float(row['oos_2026_06_01_to_latest_profit_factor']))}` |"
        )
    lines.extend(
        [
            "",
            "## 最佳候选",
            "",
            f"- label：`{best['label']}`",
            f"- signal：`{best['signal_spec']}`",
            f"- filter：`{best['filter_spec']}`",
            f"- exit：`{best['exit_spec']}`",
            f"- full：`{int(best['full_trades'])}` 笔，收益 `{pct(float(best['full_total_return']))}`，年化 `{mult(float(best['full_annualized_multiple']))}`，胜率 `{pct(float(best['full_win_rate']))}`，PF `{num(float(best['full_profit_factor']))}`，payoff `{num(float(best['full_payoff_ratio']))}`，最大回撤 `{pct(float(best['full_max_dd']))}`。",
            f"- OOS `2026-06-01 -> latest`：`{int(best['oos_2026_06_01_to_latest_trades'])}` 笔，收益 `{pct(float(best['oos_2026_06_01_to_latest_total_return']))}`，PF `{num(float(best['oos_2026_06_01_to_latest_profit_factor']))}`，胜率 `{pct(float(best['oos_2026_06_01_to_latest_win_rate']))}`。",
            f"- 月度：盈利月 `{positive_months}/{len(best_monthly)}`；最差月 `{worst_month['month'] if worst_month is not None else '-'}` 收益 `{pct(float(worst_month['total_return'])) if worst_month is not None else '-'}`。",
            "",
            "### 最佳候选切片",
            "",
            "| slice | 交易数 | 收益 | 胜率 | PF | payoff | 回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in best_slices.to_dict(orient="records"):
        lines.append(
            f"| `{row['slice']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['profit_factor']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` |"
        )
    if len(passed):
        conclusion = "本轮找到了满足宽松 balanced gate 的 bracket 候选，但它仍只能作为 paper-audit 研究候选，原因是 OOS 样本较短，且参数来自同一资产同一历史窗口搜索。"
    else:
        conclusion = "本轮没有找到满足 balanced gate 的 bracket 候选；前排结果只能作为诊断线索，不应提升为 paper/live。"
    lines.extend(
        [
            "",
            "## 结论",
            "",
            conclusion,
            "",
            "后续若推进，应优先做 walk-forward 阈值固化和 paper audit runner，而不是直接写真钱 live spec。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/15m-pullback-trail/scripts/research_hype_15m_pbtr_bracket_search.py`",
            f"- JSON：`{REPORT_JSON.relative_to(ROOT)}`",
            f"- prescreen CSV：`{PRESCREEN_CSV.relative_to(ROOT)}`",
            f"- summary CSV：`{SUMMARY_CSV.relative_to(ROOT)}`",
            f"- slices CSV：`{SLICES_CSV.relative_to(ROOT)}`",
            f"- monthly CSV：`{MONTHLY_CSV.relative_to(ROOT)}`",
            f"- best trades CSV：`{TRADES_CSV.relative_to(ROOT)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw_5m = load_all_hype_5m()
    raw_quality = verify_5m_data(raw_5m)
    data_15m, resample_quality = resample_15m_from_5m(raw_5m)
    frame = add_features(data_15m)
    data_quality = {"raw_5m": raw_quality, "resampled_15m": resample_quality}

    signal_cache: dict[str, np.ndarray] = {}
    filtered_cache: dict[tuple[str, str], np.ndarray] = {}
    signal_objects = signal_specs()
    filter_objects = filter_specs()

    prescreen_rows: list[dict[str, Any]] = []
    prescreen_slice_rows: list[dict[str, Any]] = []
    for signal_spec in signal_objects:
        signal = build_signal(frame, signal_spec)
        signal_cache[signal_spec.label] = signal
        if int(np.count_nonzero(signal)) < MIN_FULL_TRADES:
            continue
        for filter_spec in filter_objects:
            filtered = filter_signal(frame, signal, signal_spec, filter_spec)
            signal_count = int(np.count_nonzero(filtered))
            if signal_count < MIN_FULL_TRADES:
                continue
            filtered_cache[(signal_spec.label, filter_spec.label)] = filtered
            for exit_spec in prescreen_exit_specs():
                label = f"{signal_spec.label}__{filter_spec.label}__{exit_spec.label}"
                trades = simulate_bracket(frame, filtered, exit_spec, label)
                if len(trades) < MIN_FULL_TRADES:
                    continue
                row, rows = summarize(label, signal_count, trades, signal_spec, filter_spec, exit_spec, frame, "prescreen")
                prescreen_rows.append(row)
                prescreen_slice_rows.extend(rows)

    prescreen = pd.DataFrame(prescreen_rows)
    if prescreen.empty:
        raise RuntimeError("prescreen produced no rows")
    prescreen = prescreen.sort_values(["balanced_pass", "score", "full_total_return"], ascending=False).reset_index(drop=True)
    prescreen.to_csv(PRESCREEN_CSV, index=False)

    keys: list[tuple[str, str]] = []
    for row in prescreen.head(PRESCREEN_TOP).to_dict(orient="records"):
        key = (str(row["signal_spec"]), str(row["filter_spec"]))
        if key not in keys:
            keys.append(key)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    best_trades: list[Trade] = []
    best_label = ""
    for signal_label, filter_label in keys:
        signal_spec = next(item for item in signal_objects if item.label == signal_label)
        filter_spec = next(item for item in filter_objects if item.label == filter_label)
        filtered = filtered_cache.get((signal_label, filter_label))
        if filtered is None:
            filtered = filter_signal(frame, signal_cache[signal_label], signal_spec, filter_spec)
            filtered_cache[(signal_label, filter_label)] = filtered
        signal_count = int(np.count_nonzero(filtered))
        for exit_spec in full_exit_specs():
            label = f"{signal_spec.label}__{filter_spec.label}__{exit_spec.label}"
            trades = simulate_bracket(frame, filtered, exit_spec, label)
            if len(trades) < MIN_FULL_TRADES:
                continue
            row, rows = summarize(label, signal_count, trades, signal_spec, filter_spec, exit_spec, frame, "refine")
            summary_rows.append(row)
            slice_rows.extend(rows)
            if not best_trades or row["score"] > max(item["score"] for item in summary_rows[:-1]):
                best_trades = trades
                best_label = label

    summary = pd.DataFrame(summary_rows).sort_values(["balanced_pass", "score", "full_total_return"], ascending=False).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows)
    if summary.empty:
        raise RuntimeError("refine produced no rows")
    best_label = str(summary.iloc[0]["label"])
    if not best_trades or best_trades[0].config != best_label:
        top = summary.iloc[0]
        signal_spec = next(item for item in signal_objects if item.label == str(top["signal_spec"]))
        filter_spec = next(item for item in filter_objects if item.label == str(top["filter_spec"]))
        exit_spec = ExitSpec(float(top["exit_tp_atr"]), float(top["exit_sl_atr"]), int(top["exit_timeout_bars"]))
        filtered = filtered_cache[(signal_spec.label, filter_spec.label)]
        best_trades = simulate_bracket(frame, filtered, exit_spec, best_label)

    monthly_rows: list[dict[str, Any]] = []
    for label in summary.head(20)["label"].tolist():
        top = summary.loc[summary["label"] == label].iloc[0]
        signal_spec = next(item for item in signal_objects if item.label == str(top["signal_spec"]))
        filter_spec = next(item for item in filter_objects if item.label == str(top["filter_spec"]))
        exit_spec = ExitSpec(float(top["exit_tp_atr"]), float(top["exit_sl_atr"]), int(top["exit_timeout_bars"]))
        trades = simulate_bracket(frame, filtered_cache[(signal_spec.label, filter_spec.label)], exit_spec, label)
        for item in month_slices(frame):
            monthly_rows.append({"label": label, "month": item["name"], **metric_from_trades(trades, start=item["start"], end=item["end"])})
    monthly = pd.DataFrame(monthly_rows)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV, index=False)
    slices.to_csv(SLICES_CSV, index=False)
    monthly.to_csv(MONTHLY_CSV, index=False)
    trades_to_frame(best_trades, best_label).to_csv(TRADES_CSV, index=False)
    REPORT_MD.write_text(render_markdown(data_quality, prescreen, summary, slices, monthly), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "family_id": "HYPE-15M-Pullback-Trail",
                "date": DATE_TAG,
                "question": "15m pullback event source with immediately executable bracket / emergency stop / timeout exits",
                "data_quality": data_quality,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "search": {
                    "signal_specs": len(signal_objects),
                    "filter_specs": len(filter_objects),
                    "prescreen_exit_specs": len(prescreen_exit_specs()),
                    "full_exit_specs": len(full_exit_specs()),
                    "prescreen_rows": len(prescreen),
                    "refine_rows": len(summary),
                    "balanced_pass": int(summary["balanced_pass"].sum()),
                    "best_label": best_label,
                },
                "outputs": {
                    "markdown": str(REPORT_MD.relative_to(ROOT)),
                    "prescreen": str(PRESCREEN_CSV.relative_to(ROOT)),
                    "summary": str(SUMMARY_CSV.relative_to(ROOT)),
                    "slices": str(SLICES_CSV.relative_to(ROOT)),
                    "monthly": str(MONTHLY_CSV.relative_to(ROOT)),
                    "best_trades": str(TRADES_CSV.relative_to(ROOT)),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=json_safe,
        ),
        encoding="utf-8",
    )
    print(f"markdown={REPORT_MD.relative_to(ROOT)}")
    print(f"summary={SUMMARY_CSV.relative_to(ROOT)}")
    print(summary.head(12)[["label", "balanced_pass", "score", "full_trades", "full_total_return", "full_win_rate", "full_profit_factor", "full_payoff_ratio", "full_max_dd", "oos_2026_06_01_to_latest_trades", "oos_2026_06_01_to_latest_profit_factor"]].to_string(index=False))


if __name__ == "__main__":
    main()
