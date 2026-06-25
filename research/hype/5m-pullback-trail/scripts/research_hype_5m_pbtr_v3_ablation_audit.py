from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal
from research_hype_5m_pbtr_v2_ablation_slices import FINAL_FILTER_THRESHOLD, LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v21_live_cost_variants import V21_CLEAN_CONFIG
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
    simulate_trades_live_cost,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m, validation_slices


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_ablation_audit.json")
ABLATION_SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_ablation_summary.csv")
ABLATION_SLICES_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_ablation_validation_slices.csv")
WEEKLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_weekly_slices.csv")
MONTHLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_monthly_slices.csv")
ROLLING_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_rolling_windows.csv")
AUDIT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v3_audit_metrics.json")
MARKDOWN_PATH = Path("research/hype/families/5m-pullback-trail/diagnostics/hype-5m-pbtr-v3-ablation-audit-2026-06-24.md")


V3_CONFIG = replace(
    V21_CLEAN_CONFIG,
    name="HYPE-5M-PBTR-V3",
    min_dir_rsi=0.0,
    max_dir_rsi=100.0,
)


def filtered_signal(frame: pd.DataFrame, cfg: SearchConfig, *, final_filter: bool, threshold: float | None = None) -> np.ndarray:
    signal = build_signal(frame, cfg)
    if not final_filter:
        return signal.copy()
    sig_idx = np.flatnonzero(signal)
    if len(sig_idx) == 0:
        return signal.copy()
    threshold = FINAL_FILTER_THRESHOLD if threshold is None else threshold
    side = signal[sig_idx].astype(float)
    dir_htf = side * frame["htf_spread"].to_numpy("float64")[sig_idx]
    keep = dir_htf >= threshold
    filtered = np.zeros_like(signal)
    filtered[sig_idx[keep]] = signal[sig_idx[keep]]
    previous_same = np.r_[False, (filtered[1:] != 0) & (filtered[1:] == filtered[:-1])]
    filtered[previous_same] = 0
    return filtered


def evaluate_variant(
    frame: pd.DataFrame,
    slices: list[dict[str, Any]],
    *,
    label: str,
    family: str,
    parameter: str,
    value: Any,
    cfg: SearchConfig,
    final_filter: bool,
    final_threshold: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade]]:
    signal = filtered_signal(frame, cfg, final_filter=final_filter, threshold=final_threshold)
    trades = simulate_trades_live_cost(frame, signal, cfg)
    summary: dict[str, Any] = {
        "label": label,
        "family": family,
        "parameter": parameter,
        "value": value,
        "final_filter_enabled": final_filter,
        "final_filter_threshold": final_threshold if final_filter else None,
        "signal_count": int(np.count_nonzero(signal)),
        "trade_count": int(len(trades)),
        **{f"cfg_{key}": item for key, item in asdict(cfg).items()},
    }
    slice_rows: list[dict[str, Any]] = []
    min_win = 1.0
    min_payoff = float("inf")
    min_ann = float("inf")
    worst_dd = 0.0
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        row = {
            "label": label,
            "family": family,
            "parameter": parameter,
            "value": value,
            "slice": item["name"],
            "slice_start": item["start"],
            "slice_end": item["end"],
            **metrics,
        }
        slice_rows.append(row)
        min_win = min(min_win, float(metrics["win_rate"]))
        min_payoff = min(min_payoff, float(metrics["payoff_ratio"]))
        min_ann = min(min_ann, float(metrics["annualized_multiple"]))
        worst_dd = min(worst_dd, float(metrics["max_dd"]))
        for key, metric_value in metrics.items():
            summary[f"{item['name']}_{key}"] = metric_value
    summary["min_slice_win_rate"] = min_win
    summary["min_slice_payoff_ratio"] = min_payoff
    summary["min_slice_annualized_multiple"] = min_ann
    summary["worst_slice_max_dd"] = worst_dd
    return summary, slice_rows, trades


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {
            "label": "baseline_v3",
            "family": "baseline",
            "parameter": "baseline",
            "value": "V3_final_htf_disabled",
            "cfg": V3_CONFIG,
            "final_filter": False,
            "final_threshold": None,
        }
    ]

    def add(
        label: str,
        family: str,
        parameter: str,
        value: Any,
        *,
        final_filter: bool = False,
        final_threshold: float | None = None,
        **changes: Any,
    ) -> None:
        variants.append(
            {
                "label": label,
                "family": family,
                "parameter": parameter,
                "value": value,
                "cfg": replace(V3_CONFIG, **changes),
                "final_filter": final_filter,
                "final_threshold": final_threshold,
            }
        )

    for threshold in (-0.5, 0.0, 0.25, 0.5, 0.688442, 1.0):
        add(
            f"final_htf_ge_{str(threshold).replace('.', 'p').replace('-', 'neg')}",
            "final_htf",
            "final_filter_threshold",
            threshold,
            final_filter=True,
            final_threshold=threshold,
        )

    add("side_long_only", "direction", "side_mode", "long", side_mode="long")
    add("side_short_only", "direction", "side_mode", "short", side_mode="short")

    for fast, slow in ((9, 55), (12, 96), (34, 144), (55, 192), (96, 384)):
        add(f"ema_pair_{fast}_{slow}", "trend_definition", "ema_pair", f"{fast}/{slow}", ema_fast=fast, ema_slow=slow)

    for style in (
        "breakout",
        "momentum",
        "squeeze_breakout",
        "channel_reclaim",
        "trend_rsi_rebound",
        "bb_reversion",
        "ema_deviation_revert",
    ):
        add(f"entry_style_{style}", "entry_logic", "entry_style", style, entry_style=style)

    for value in (0.0, 0.0025, 0.005, 0.02, 99.0):
        label = str(value).replace(".", "p")
        add(f"pullback_buffer_{label}", "entry_logic", "pullback_buffer", value, pullback_buffer=value)

    for window in (24, 48, 192):
        add(f"roc_window_{window}", "trend_filter", "roc_window", window, roc_window=window)

    add("remove_min_regime_age", "trend_filter", "min_regime_age", 0, min_regime_age=0)
    add("restore_max_regime_age_2000", "trend_filter", "max_regime_age", 2000, max_regime_age=2000)
    add("restore_max_dist_ema_0p06", "trend_filter", "max_dist_ema", 0.06, max_dist_ema=0.06)
    add("restore_min_dir_rsi_55", "oscillator_filter", "min_dir_rsi", 55.0, min_dir_rsi=55.0)
    add("restore_max_dir_rsi_72", "oscillator_filter", "max_dir_rsi", 72.0, max_dir_rsi=72.0)
    add("restore_rsi_55_72", "oscillator_filter", "minmax_dir_rsi", "55/72", min_dir_rsi=55.0, max_dir_rsi=72.0)
    add("remove_min_dir_roc", "trend_filter", "min_dir_roc", -99.0, min_dir_roc=-99.0)
    add("remove_max_chop", "regime_filter", "max_chop", 100.0, max_chop=100.0)
    add("restore_min_efficiency_0p025", "regime_filter", "min_efficiency", 0.025, min_efficiency=0.025)
    add("restore_min_dir_cmf_neg0p30", "flow_filter", "min_dir_cmf", -0.30, min_dir_cmf=-0.30)
    add("enable_min_adx_14", "inactive_filter_probe", "min_adx", 14.0, min_adx=14.0)
    add("tighten_max_atr_ratio_2", "inactive_filter_probe", "max_atr_ratio", 2.0, max_atr_ratio=2.0)
    add("enable_min_rvol_1", "inactive_filter_probe", "min_rvol", 1.0, min_rvol=1.0)
    add("enable_require_macd", "inactive_filter_probe", "require_macd", True, require_macd=True)
    add("enable_require_obv", "inactive_filter_probe", "require_obv", True, require_obv=True)
    add("enable_require_htf", "inactive_filter_probe", "require_htf", True, require_htf=True)

    for stop_atr in (0.75, 1.5, 99.0):
        label = str(stop_atr).replace(".", "p")
        add(f"stop_atr_{label}", "exit_risk", "stop_atr", stop_atr, stop_atr=stop_atr)
    for tp_atr in (1.25, 1.875, 3.0):
        label = str(tp_atr).replace(".", "p")
        add(f"tp_atr_{label}", "exit_risk", "tp_atr", tp_atr, tp_atr=tp_atr)
    add("remove_trailing_stop", "exit_risk", "trail_atr", 0.0, trail_atr=0.0)
    add("looser_trailing_stop_1p5", "exit_risk", "trail_atr", 1.5, trail_atr=1.5)
    add("remove_min_hold", "exit_risk", "min_hold_bars", 0, min_hold_bars=0)
    add("min_hold_3", "exit_risk", "min_hold_bars", 3, min_hold_bars=3)
    add("min_hold_9", "exit_risk", "min_hold_bars", 9, min_hold_bars=9)
    add("max_hold_48", "exit_risk", "max_hold_bars", 48, max_hold_bars=48)
    add("max_hold_576", "exit_risk", "max_hold_bars", 576, max_hold_bars=576)
    add("enable_exit_ema_21", "inactive_exit_probe", "exit_ema", 21, exit_ema=21)
    add("enable_cooldown_6", "inactive_exit_probe", "cooldown_bars", 6, cooldown_bars=6)

    return variants


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0]).floor("D")
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        month_end = min(cursor + pd.offsets.MonthBegin(1), end)
        rows.append(
            {
                "name": cursor.strftime("%Y-%m"),
                "start": cursor,
                "end": month_end,
            }
        )
        cursor = month_end
    return rows


def custom_time_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    boundaries = [
        start,
        pd.Timestamp("2025-07-01T00:00:00Z"),
        pd.Timestamp("2025-09-01T00:00:00Z"),
        pd.Timestamp("2025-11-01T00:00:00Z"),
        pd.Timestamp("2026-01-01T00:00:00Z"),
        pd.Timestamp("2026-03-01T00:00:00Z"),
        pd.Timestamp("2026-05-01T00:00:00Z"),
        end,
    ]
    rows: list[dict[str, Any]] = []
    for idx, (left, right) in enumerate(zip(boundaries, boundaries[1:], strict=False), start=1):
        left = max(left, start)
        right = min(right, end)
        if left < right:
            rows.append({"name": f"custom_{idx:02d}_{left:%Y%m%d}_{(right - pd.Timedelta(minutes=5)):%Y%m%d}", "start": left, "end": right})
    return rows


def trades_to_frame(frame: pd.DataFrame, trades: list[Trade]) -> pd.DataFrame:
    idx_by_ts = {pd.Timestamp(ts).value: i for i, ts in enumerate(frame["ts"])}
    close = frame["close"].to_numpy("float64")
    htf = frame["htf_spread"].to_numpy("float64")
    rows: list[dict[str, Any]] = []
    for trade in trades:
        sig_i = idx_by_ts[pd.Timestamp(trade.signal_ts).value]
        side = int(trade.side)
        dir_htf = float(side * htf[sig_i])
        rows.append(
            {
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": side,
                "net_ret_1x": float(trade.net_ret_1x),
                "mae_1x": float(trade.mae_1x),
                "mfe_1x": float(trade.mfe_1x),
                "bars_held": int(trade.bars_held),
                "dir_htf_abs": dir_htf,
                "dir_htf_pct": float(dir_htf / close[sig_i]),
                "close": float(close[sig_i]),
                "month": pd.Timestamp(trade.entry_ts).strftime("%Y-%m"),
                "date": pd.Timestamp(trade.entry_ts).date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def equity_curve(rets: np.ndarray) -> np.ndarray:
    if len(rets) == 0:
        return np.array([1.0])
    return np.cumprod(np.maximum(0.001, 1.0 + rets))


def sequence_metrics(trades: list[Trade], frame: pd.DataFrame) -> dict[str, Any]:
    trade_df = trades_to_frame(frame, trades)
    rets = trade_df["net_ret_1x"].to_numpy("float64")
    eq = equity_curve(rets)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    top_sorted = np.sort(rets)[::-1]
    outlier_rows: list[dict[str, Any]] = []
    for count in (1, 3, 5, 10, 25, 50, 100):
        if count >= len(rets):
            continue
        keep = np.ones(len(rets), dtype=bool)
        keep[np.argsort(rets)[::-1][:count]] = False
        kept = rets[keep]
        outlier_rows.append(
            {
                "method": f"exclude_top_{count}",
                "equity_multiple": float(equity_curve(kept)[-1]),
                "total_return": float(equity_curve(kept)[-1] - 1.0),
                "win_rate": float((kept > 0).mean()),
                "avg_trade": float(kept.mean()),
            }
        )
    for cap in (0.005, 0.01, 0.015, 0.02, 0.03):
        clipped = np.minimum(rets, cap)
        outlier_rows.append(
            {
                "method": f"cap_win_{cap}",
                "equity_multiple": float(equity_curve(clipped)[-1]),
                "total_return": float(equity_curve(clipped)[-1] - 1.0),
                "win_rate": float((clipped > 0).mean()),
                "avg_trade": float(clipped.mean()),
            }
        )

    daily = trade_df.groupby("date", sort=True)["net_ret_1x"].apply(lambda values: float(np.prod(1.0 + values) - 1.0))
    monthly = trade_df.groupby("month", sort=True)["net_ret_1x"].apply(lambda values: float(np.prod(1.0 + values) - 1.0))
    by_month = trade_df.groupby("month", sort=True).agg(
        trades=("net_ret_1x", "size"),
        win_rate=("net_ret_1x", lambda values: float((values > 0).mean())),
        avg_trade=("net_ret_1x", "mean"),
    )
    by_month["compound_return"] = monthly

    arithmetic_sum = float(rets.sum())
    avg_trade = float(rets.mean())
    median_trade = float(np.median(rets))
    days = max((pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5) - pd.Timestamp(frame["ts"].iloc[0])).total_seconds() / 86400.0, 1.0)
    daily_turnover_trades = len(rets) / days
    avg_daily_compound = float(eq[-1] ** (1.0 / days) - 1.0)
    avg_monthly_compound = float(eq[-1] ** (30.4375 / days) - 1.0)
    top10_sum = float(top_sorted[:10].sum())
    top100_sum = float(top_sorted[:100].sum())
    return {
        "trade_distribution": {
            "trades": int(len(rets)),
            "equity_multiple": float(eq[-1]),
            "arithmetic_sum_return": arithmetic_sum,
            "avg_trade": avg_trade,
            "median_trade": median_trade,
            "win_rate": float((rets > 0).mean()),
            "avg_win": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss_abs": float(abs(losses.mean())) if len(losses) else 0.0,
            "best_trade": float(rets.max()),
            "worst_trade": float(rets.min()),
            "p01": float(np.quantile(rets, 0.01)),
            "p05": float(np.quantile(rets, 0.05)),
            "p50": float(np.quantile(rets, 0.50)),
            "p95": float(np.quantile(rets, 0.95)),
            "p99": float(np.quantile(rets, 0.99)),
            "top10_return_sum": top10_sum,
            "top100_return_sum": top100_sum,
            "trades_per_day": float(daily_turnover_trades),
            "avg_daily_compound_return": avg_daily_compound,
            "avg_monthly_compound_return": avg_monthly_compound,
        },
        "outlier_sensitivity": outlier_rows,
        "daily_return_summary": {
            "days": int(len(daily)),
            "positive_days": int((daily > 0).sum()),
            "positive_day_share": float((daily > 0).mean()),
            "median_daily_return": float(daily.median()),
            "worst_daily_return": float(daily.min()),
            "best_daily_return": float(daily.max()),
            "avg_daily_return": float(daily.mean()),
        },
        "monthly_return_summary": {
            "months": int(len(monthly)),
            "positive_months": int((monthly > 0).sum()),
            "positive_month_share": float((monthly > 0).mean()),
            "median_monthly_return": float(monthly.median()),
            "worst_monthly_return": float(monthly.min()),
            "best_monthly_return": float(monthly.max()),
            "avg_monthly_return": float(monthly.mean()),
            "by_month": by_month.reset_index().to_dict(orient="records"),
        },
        "top_trades": trade_df.sort_values("net_ret_1x", ascending=False).head(20).to_dict(orient="records"),
        "bottom_trades": trade_df.sort_values("net_ret_1x").head(20).to_dict(orient="records"),
    }


def cost_stress_metrics(frame: pd.DataFrame, base_signal: np.ndarray, cfg: SearchConfig) -> list[dict[str, Any]]:
    # Reimplement a compact cost stress simulator so we can stress entry slippage directly.
    from research_hype_5m_indicator_search import first_event_offset

    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    n = len(frame)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    rows: list[dict[str, Any]] = []

    for entry_mult in (0.5, 1.0, 1.5, 2.0, 3.0):
        for extra_fee_bps in (0.0, 2.0, 5.0):
            trades: list[Trade] = []
            blocked_until = -1
            entry_slip = ENTRY_SLIPPAGE_RATE * entry_mult
            fee_rate = FEE_RATE_PER_FILL + extra_fee_bps / 10000.0
            for sig_i in np.flatnonzero(base_signal):
                direction = int(base_signal[sig_i])
                entry_i = sig_i + 1
                if entry_i >= n or entry_i <= blocked_until or direction == 0:
                    continue
                atr_value = float(atr[sig_i])
                if not np.isfinite(atr_value) or atr_value <= 0:
                    continue
                entry_price = float(open_[entry_i] * (1.0 + direction * entry_slip))
                stop_price = entry_price - direction * cfg.stop_atr * atr_value
                target_price = entry_price + direction * cfg.tp_atr * atr_value
                end_i = min(n - 1, entry_i + cfg.max_hold_bars)
                sl = slice(entry_i, end_i + 1)
                high_seg = high[sl]
                low_seg = low[sl]
                close_seg = close[sl]
                atr_seg = atr[sl]
                if direction > 0:
                    prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
                    stop_levels = np.maximum(np.full(len(high_seg), stop_price), prev_peak - cfg.trail_atr * atr_seg)
                    stop_hit = low_seg <= stop_levels
                    target_hit = high_seg >= target_price
                else:
                    prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
                    stop_levels = np.minimum(np.full(len(low_seg), stop_price), prev_trough + cfg.trail_atr * atr_seg)
                    stop_hit = high_seg >= stop_levels
                    target_hit = low_seg <= target_price
                if cfg.min_hold_bars > 0:
                    stop_hit[: cfg.min_hold_bars] = False
                    target_hit[: cfg.min_hold_bars] = False
                event_mask = stop_hit | target_hit
                offset = first_event_offset(event_mask)
                if offset is None:
                    offset = len(close_seg) - 1
                    raw_exit_price = float(close_seg[offset])
                elif stop_hit[offset]:
                    raw_exit_price = float(stop_levels[offset])
                else:
                    raw_exit_price = float(target_price)
                path_high = high_seg[: offset + 1]
                path_low = low_seg[: offset + 1]
                if direction > 0:
                    mae = float(np.nanmin(path_low / entry_price - 1.0))
                    mfe = float(np.nanmax(path_high / entry_price - 1.0))
                else:
                    mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
                    mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))
                exit_i = entry_i + offset
                exit_price = float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))
                gross = direction * (exit_price / entry_price - 1.0)
                fee_cost = fee_rate * (1.0 + exit_price / entry_price)
                net = gross - fee_cost
                trades.append(
                    Trade(
                        config=cfg.name,
                        signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                        entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                        exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                        side=direction,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        reason="stress",
                        bars_held=int(exit_i - entry_i + 1),
                        net_ret_1x=float(net),
                        mae_1x=float(mae - fee_rate),
                        mfe_1x=float(mfe),
                    )
                )
                blocked_until = exit_i + cfg.cooldown_bars
            metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
            rows.append(
                {
                    "entry_slippage_multiplier": entry_mult,
                    "extra_fee_bps_per_fill": extra_fee_bps,
                    **metrics,
                }
            )
    return rows


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def render_markdown(summary: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame, rolling: pd.DataFrame, audit: dict[str, Any]) -> str:
    base = summary.loc[summary["label"] == "baseline_v3"].iloc[0]
    top_negative = summary.sort_values("delta_full_total_return").head(12)
    top_positive = summary.sort_values("delta_full_total_return", ascending=False).head(12)
    weekly_v3 = weekly.copy()
    monthly_v3 = monthly.copy()
    worst_week = weekly_v3.sort_values("total_return").iloc[0]
    best_week = weekly_v3.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly_v3.sort_values("total_return").iloc[0]
    best_month = monthly_v3.sort_values("total_return", ascending=False).iloc[0]
    dist = audit["sequence_metrics"]["trade_distribution"]
    daily = audit["sequence_metrics"]["daily_return_summary"]
    monthly_summary = audit["sequence_metrics"]["monthly_return_summary"]
    cost_stress = pd.DataFrame(audit["cost_stress"])

    lines: list[str] = [
        "# HYPE-5M-PBTR-V3 全参数消融与量化审计 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "Canonical name：`HYPE-5M-PBTR-V3`",
        "",
        "V3 定义：从原 `HYPE-5M-PBTR-HF1` 正式提升而来，即 `V2.1A` 移除 final `dir_htf` 过滤。核心机制仍是 `5m pullback_resume + min_hold_bars=6 + trail_atr=0.75`。",
        "",
        "## 成本与数据",
        "",
        "- 成本口径：线上实盘统计成本。",
        f"- 手续费：`{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`。",
        f"- 开仓滑点：`{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 平仓滑点：`{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 净滑点：`{NET_SLIPPAGE_RATE_ON_TURNOVER * 10000:+.4f} bps/总成交额`。",
        "- 数据：Binance HYPEUSDT 永续 `5m`，`2025-05-30 10:30 UTC` 到 `2026-06-23 04:20 UTC`。",
        "- 杠杆：`1x`；单策略单仓，不叠仓。",
        "",
        "## V3 基线",
        "",
        "| 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 | 多/空 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{int(base['full_trades'])}` | `{mult(float(base['full_annualized_multiple']))}` | `{pct(float(base['full_total_return']))}` | `{pct(float(base['full_win_rate']))}` | `{num(float(base['full_payoff_ratio']))}` | `{num(float(base['full_profit_factor']))}` | `{pct(float(base['full_max_dd']))}` | `{int(base['full_long_trades'])}/{int(base['full_short_trades'])}` |",
        "",
        "## 全参数消融",
        "",
        "### 伤害最大的模块",
        "",
        "| 变体 | 参数 | 交易数 | 年化 | 胜率 | payoff | 最大回撤 | Δ累计收益 | 解读 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    interpretation = {
        "remove_min_hold": "删除最小持仓后策略失效，说明 V3 不是入场后立刻兑现 alpha，而是需要给趋势恢复时间。",
        "remove_trailing_stop": "删除 ATR trailing 后胜率崩塌，说明收益主要来自延迟后用紧 trailing 收割路径。",
        "looser_trailing_stop_1p5": "移动止损放宽后保护不足，收益大幅下降。",
        "enable_cooldown_6": "冷却会错过大量有效连续机会，高频收益被削弱。",
        "final_htf_ge_0p5": "恢复 V2.1A final HTF 会显著降频，胜率提高但收益下降。",
    }
    for row in top_negative.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['label']}` | `{row['parameter']}` | "
            f"{int(row['full_trades'])} | {mult(float(row['full_annualized_multiple']))} | "
            f"{pct(float(row['full_win_rate']))} | {num(float(row['full_payoff_ratio']))} | "
            f"{pct(float(row['full_max_dd']))} | {pct(float(row['delta_full_total_return']))} | "
            f"{interpretation.get(row['label'], '')} |"
        )

    lines.extend(
        [
            "",
            "### 正向或中性变化",
            "",
            "| 变体 | 参数 | 交易数 | 年化 | 胜率 | payoff | 最大回撤 | Δ累计收益 | 解读 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in top_positive.to_dict(orient="records"):
        note = ""
        if row["label"] == "baseline_v3":
            note = "V3 基线。"
        elif row["label"] == "remove_max_chop":
            note = "CHOP 上限不是核心约束，删除后收益上升但胜率下降。"
        elif row["label"] == "pullback_buffer_99p0":
            note = "说明严格回踩 EMA21 不是唯一收益来源，需防止过度泛化成趋势恢复模板。"
        elif str(row["label"]).startswith("final_htf"):
            note = "final HTF 阈值越宽，频率和复利越高；它更像频率调节器。"
        lines.append(
            "| "
            f"`{row['label']}` | `{row['parameter']}` | "
            f"{int(row['full_trades'])} | {mult(float(row['full_annualized_multiple']))} | "
            f"{pct(float(row['full_win_rate']))} | {num(float(row['full_payoff_ratio']))} | "
            f"{pct(float(row['full_max_dd']))} | {pct(float(row['delta_full_total_return']))} | "
            f"{note} |"
        )

    lines.extend(
        [
            "",
            "## 时间稳定性",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['window']}` | {int(row['trades'])} | {pct(float(row['total_return']))} | "
            f"{mult(float(row['annualized_multiple']))} | {pct(float(row['win_rate']))} | "
            f"{num(float(row['payoff_ratio']))} | {pct(float(row['max_dd']))} |"
        )

    lines.extend(
        [
            "",
            "周切片摘要：",
            "",
            f"- 周数：`{len(weekly_v3)}`。",
            f"- 平均交易数/周：`{weekly_v3['trades'].mean():.1f}`。",
            f"- 中位周收益：`{pct(float(weekly_v3['total_return'].median()))}`。",
            f"- 盈利周：`{int((weekly_v3['total_return'] > 0).sum())}/{len(weekly_v3)}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`。",
            f"- 最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            "",
            "月切片摘要：",
            "",
            f"- 月数：`{len(monthly_v3)}`。",
            f"- 盈利月：`{int((monthly_v3['total_return'] > 0).sum())}/{len(monthly_v3)}`。",
            f"- 中位月收益：`{pct(float(monthly_v3['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`。",
            f"- 最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 年化为什么这么夸张",
            "",
            "从资深量化审计视角看，V3 的年化不应被解读为可兑现收益承诺。它主要由以下机制共同造成：",
            "",
            f"1. **高交易密度复利**：全样本 `{int(dist['trades'])}` 笔，约 `{dist['trades_per_day']:.2f}` 笔/天。平均每笔只有 `{pct(float(dist['avg_trade']), 4)}`，但连续复利后权益倍数达到 `{mult(float(dist['equity_multiple']))}`。",
            f"2. **正偏 payoff 结构**：胜率只有 `{pct(float(dist['win_rate']))}`，但平均盈利 `{pct(float(dist['avg_win']), 3)}`，平均亏损 `{pct(float(dist['avg_loss_abs']), 3)}`，payoff 接近 `{float(base['full_payoff_ratio']):.2f}`。",
            f"3. **中位数为负但右尾很厚**：中位单笔收益 `{pct(float(dist['median_trade']), 4)}`，最优单笔 `{pct(float(dist['best_trade']))}`，最差单笔 `{pct(float(dist['worst_trade']))}`。这说明策略体验不是高胜率，而是靠少数更大的顺风路径覆盖大量小亏/小赢。",
            f"4. **时间切片有持续正收益**：盈利周 `{int((weekly_v3['total_return'] > 0).sum())}/{len(weekly_v3)}`、盈利月 `{int((monthly_v3['total_return'] > 0).sum())}/{len(monthly_v3)}`，高频填平了低样本周。",
            f"5. **年化公式放大短周期复利**：平均日复利收益约 `{pct(float(dist['avg_daily_compound_return']))}`，这个数看似不大，但年化会变成百万倍级。",
            "",
            "## 审计判断",
            "",
            "我不认为 V3 的回测结果可以按字面作为实盘收益预期。更合理的解释是：HYPE 在这段样本里存在强烈的 5m 趋势恢复微结构，V3 用极高频率和紧 trailing 把它系统性采出来；但该结构高度依赖标的、波动、成交质量和回测成交假设。",
            "",
            "需要重点警惕：",
            "",
            "- **执行容量**：每周约 160 笔，实盘如果用市价/追价，开仓冲击可能远高于当前 `10.73 bps` 均值。",
            "- **止损成交假设**：回测按 bar 内 stop level 成交，再套平仓滑点；极端快跌/快涨时真实 stop-market 可能滑穿。",
            "- **样本选择**：HYPE 是新币，样本约一年，正好覆盖高波动阶段；不能证明该微结构长期存在。",
            "- **复利展示误导**：权益倍数百万级是数学复利结果，实际资金容量、仓位缩放、保证金限制和交易所风控会显著压低。",
            "- **参数挖掘风险**：V3 来自多轮搜索、消融和筛选，必须用 forward dry-run 验证，不能只相信样本内表现。",
            "",
            "## 成本压力",
            "",
            "| 开仓滑点倍数 | 额外手续费/成交 | 交易数 | 权益倍数 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    stress_rows = cost_stress[
        cost_stress["entry_slippage_multiplier"].isin([1.0, 2.0, 3.0])
        & cost_stress["extra_fee_bps_per_fill"].isin([0.0, 5.0])
    ].sort_values(["entry_slippage_multiplier", "extra_fee_bps_per_fill"])
    for row in stress_rows.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['entry_slippage_multiplier']:.1f}x` | `{row['extra_fee_bps_per_fill']:.1f} bps` | "
            f"{int(row['trades'])} | {mult(float(row['equity_multiple']))} | {mult(float(row['annualized_multiple']))} | "
            f"{pct(float(row['win_rate']))} | {num(float(row['payoff_ratio']))} | {num(float(row['profit_factor']))} | "
            f"{pct(float(row['max_dd']))} |"
        )
    lines.extend(
        [
            "",
            "成本压力测试说明：这里只改变开仓滑点和额外手续费，未模拟限价错过、订单失败、盘口冲击随资金规模非线性扩大等问题。因此这不是悲观上限，而是最基础的执行敏感性检查。V3 的样本内优势很大，但收益对成交质量高度敏感。",
            "",
            "## 结论",
            "",
            "V3 可以记入主账，但定位应是高频研究候选，而不是生产批准版本。它真正值得验证的不是百万倍年化，而是 `300-500` 笔 dry-run 后是否还能保持：PF `>=1.8`、payoff `>=2.2`、净胜率不长期低于 `47%`，并且真实开仓滑点没有超过当前假设的 `2x`。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3_ablation_audit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 审计 JSON：`{AUDIT_PATH}`",
            f"- 消融汇总：`{ABLATION_SUMMARY_PATH}`",
            f"- 消融切片：`{ABLATION_SLICES_PATH}`",
            f"- 周切片：`{WEEKLY_PATH}`",
            f"- 月切片：`{MONTHLY_PATH}`",
            f"- 滚动窗口：`{ROLLING_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = add_features(load_all_hype_5m())
    frame = frame.loc[frame["ts"] <= END_TS].reset_index(drop=True)
    args = SimpleNamespace(min_full_trades=80, min_slice_trades=12, min_forward_trades=5)
    validation = validation_slices(frame, args)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    baseline_trades: list[Trade] | None = None
    baseline_signal: np.ndarray | None = None
    for variant in build_variants():
        summary, slices_for_variant, trades = evaluate_variant(frame, validation, **variant)
        summary_rows.append(summary)
        slice_rows.extend(slices_for_variant)
        if variant["label"] == "baseline_v3":
            baseline_trades = trades
            baseline_signal = filtered_signal(frame, variant["cfg"], final_filter=False)

    if baseline_trades is None or baseline_signal is None:
        raise RuntimeError("baseline V3 missing")

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"] == "baseline_v3"].iloc[0]
    summary["delta_full_annualized_multiple"] = summary["full_annualized_multiple"] - float(baseline["full_annualized_multiple"])
    summary["delta_full_total_return"] = summary["full_total_return"] - float(baseline["full_total_return"])
    summary["delta_full_win_rate"] = summary["full_win_rate"] - float(baseline["full_win_rate"])
    summary["delta_full_payoff_ratio"] = summary["full_payoff_ratio"] - float(baseline["full_payoff_ratio"])
    summary["delta_full_max_dd"] = summary["full_max_dd"] - float(baseline["full_max_dd"])
    summary["delta_full_trades"] = summary["full_trades"] - int(baseline["full_trades"])

    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        weekly_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(baseline_trades, LEVERAGE, start=item["start"], end=item["end"])})
    weekly = pd.DataFrame(weekly_rows)

    monthly_rows: list[dict[str, Any]] = []
    for item in month_slices(frame):
        monthly_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(baseline_trades, LEVERAGE, start=item["start"], end=item["end"])})
    monthly = pd.DataFrame(monthly_rows)

    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame) + custom_time_slices(frame):
        rolling_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(baseline_trades, LEVERAGE, start=item["start"], end=item["end"])})
    rolling = pd.DataFrame(rolling_rows)

    audit = {
        "sequence_metrics": sequence_metrics(baseline_trades, frame),
        "cost_stress": cost_stress_metrics(frame, baseline_signal, V3_CONFIG),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(ABLATION_SUMMARY_PATH, index=False)
    pd.DataFrame(slice_rows).to_csv(ABLATION_SLICES_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(summary, weekly, monthly, rolling, audit), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3",
                "data_range": {
                    "start": str(pd.Timestamp(frame["ts"].iloc[0])),
                    "end_exclusive": str(pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)),
                    "bars": int(len(frame)),
                },
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "base_config": asdict(V3_CONFIG),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "ablation_summary": str(ABLATION_SUMMARY_PATH),
                    "ablation_slices": str(ABLATION_SLICES_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "audit": str(AUDIT_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    columns = [
        "label",
        "family",
        "parameter",
        "value",
        "full_trades",
        "full_annualized_multiple",
        "full_total_return",
        "full_win_rate",
        "full_payoff_ratio",
        "full_profit_factor",
        "full_max_dd",
        "delta_full_total_return",
    ]
    print(f"wrote={REPORT_PATH}")
    print(f"markdown={MARKDOWN_PATH}")
    print(summary[columns].sort_values("delta_full_total_return").to_string(index=False))


if __name__ == "__main__":
    main()
