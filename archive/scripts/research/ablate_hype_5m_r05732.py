from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_filter_refinement import feature_values
from research_hype_5m_indicator_search import (
    FEE_RATE,
    SLIPPAGE_RATE,
    SearchConfig,
    Trade,
    add_features,
    build_signal,
    first_event_offset,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m, metric_from_trades, validation_slices


REPORT_PATH = Path("reports/hype_5m_r05732_ablation.json")
SUMMARY_PATH = Path("reports/hype_5m_r05732_ablation_summary.csv")
SLICE_PATH = Path("reports/hype_5m_r05732_ablation_slices.csv")

LEVERAGE = 1.0
FINAL_FILTER_NAME = "dir_htf_ge_0.688442"
FINAL_FILTER_THRESHOLD = 0.688442


BASE_CONFIG = SearchConfig(
    name="HYPE_PP_R05732",
    side_mode="both",
    ema_fast=21,
    ema_slow=96,
    entry_style="pullback_resume",
    donchian=96,
    roc_window=48,
    min_regime_age=3,
    max_regime_age=2000,
    breakout_buffer=0.002,
    pullback_buffer=0.0025,
    max_dist_ema=0.06,
    min_dir_roc=-0.01,
    min_dir_rsi=55.0,
    max_dir_rsi=72.0,
    min_adx=0.0,
    max_chop=62.0,
    max_atr_ratio=99.0,
    min_rvol=0.0,
    min_dir_cmf=-0.30,
    require_macd=False,
    require_obv=False,
    require_htf=False,
    min_efficiency=0.025,
    stop_atr=0.75,
    tp_atr=1.875,
    trail_atr=0.75,
    max_hold_bars=576,
    min_hold_bars=6,
    exit_ema=0,
    cooldown_bars=0,
)


def apply_final_filter(frame: pd.DataFrame, cfg: SearchConfig, signal: np.ndarray, enabled: bool) -> np.ndarray:
    if not enabled:
        return signal.copy()
    sig_idx = np.flatnonzero(signal)
    if len(sig_idx) == 0:
        return signal.copy()
    values = feature_values(frame, cfg, signal, sig_idx)
    keep = values["dir_htf"] >= FINAL_FILTER_THRESHOLD
    filtered = np.zeros_like(signal)
    filtered[sig_idx[keep]] = signal[sig_idx[keep]]
    previous_same = np.r_[False, (filtered[1:] != 0) & (filtered[1:] == filtered[:-1])]
    filtered[previous_same] = 0
    return filtered


def simulate_trades_actual_path_mae(frame: pd.DataFrame, signal: np.ndarray, cfg: SearchConfig) -> list[Trade]:
    if "_ts_ns" in frame.columns:
        ts_ns = frame["_ts_ns"].to_numpy("int64")
    else:
        ts_ns = frame["ts"].map(lambda value: pd.Timestamp(value).value).to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    exit_ema = frame[f"ema{cfg.exit_ema}"].to_numpy("float64") if cfg.exit_ema else np.full(len(frame), np.nan)
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        atr_value = float(atr[sig_i])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * SLIPPAGE_RATE))
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
            stop_levels = np.full(len(high_seg), stop_price)
            if cfg.trail_atr > 0:
                stop_levels = np.maximum(stop_levels, prev_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
            target_hit = high_seg >= target_price
            ema_exit = close_seg < exit_ema[sl] if cfg.exit_ema else np.zeros(len(high_seg), dtype=bool)
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.full(len(low_seg), stop_price)
            if cfg.trail_atr > 0:
                stop_levels = np.minimum(stop_levels, prev_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels
            target_hit = low_seg <= target_price
            ema_exit = close_seg > exit_ema[sl] if cfg.exit_ema else np.zeros(len(low_seg), dtype=bool)

        if cfg.min_hold_bars > 0:
            stop_hit[: cfg.min_hold_bars] = False
            target_hit[: cfg.min_hold_bars] = False
            ema_exit[: cfg.min_hold_bars] = False
        event_mask = stop_hit | target_hit | ema_exit
        offset = first_event_offset(event_mask)
        reason = "time"
        if offset is None:
            offset = len(close_seg) - 1
            exit_price = float(close_seg[offset])
        elif stop_hit[offset]:
            reason = "stop"
            exit_price = float(stop_levels[offset])
        elif target_hit[offset]:
            reason = "target"
            exit_price = float(target_price)
        else:
            reason = "ema_exit"
            exit_price = float(close_seg[offset])

        path_high = high_seg[: offset + 1]
        path_low = low_seg[: offset + 1]
        if direction > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))

        exit_i = entry_i + offset
        exit_price = float(exit_price * (1.0 - direction * SLIPPAGE_RATE))
        gross = direction * (exit_price / entry_price - 1.0)
        net = gross - 2 * FEE_RATE
        trades.append(
            Trade(
                config=cfg.name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades


def evaluate(
    *,
    frame: pd.DataFrame,
    slices: list[dict[str, Any]],
    label: str,
    family: str,
    parameter: str,
    value: Any,
    cfg: SearchConfig,
    final_filter: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signal = build_signal(frame, cfg)
    filtered_signal = apply_final_filter(frame, cfg, signal, enabled=final_filter)
    trades = simulate_trades_actual_path_mae(frame, filtered_signal, cfg)
    summary: dict[str, Any] = {
        "label": label,
        "family": family,
        "parameter": parameter,
        "value": value,
        "final_filter_enabled": final_filter,
        "signal_count": int(np.count_nonzero(filtered_signal)),
        "trade_count": int(len(trades)),
        **{f"cfg_{key}": item for key, item in asdict(cfg).items()},
    }
    slice_rows: list[dict[str, Any]] = []
    min_win = 1.0
    min_payoff = float("inf")
    min_ann = float("inf")
    worst_dd = 0.0
    for item in slices:
        metrics = metric_from_trades(trades, LEVERAGE, start=item["start"], end=item["end"])
        row = {
            "label": label,
            "family": family,
            "parameter": parameter,
            "value": value,
            "slice": item["name"],
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
    return summary, slice_rows


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {
            "label": "baseline",
            "family": "baseline",
            "parameter": "baseline",
            "value": "as_selected",
            "cfg": BASE_CONFIG,
            "final_filter": True,
        },
        {
            "label": "remove_final_filter_dir_htf",
            "family": "filter_ablation",
            "parameter": "final_filter",
            "value": "disabled",
            "cfg": BASE_CONFIG,
            "final_filter": False,
        },
    ]

    def add(label: str, family: str, parameter: str, value: Any, **changes: Any) -> None:
        variants.append(
            {
                "label": label,
                "family": family,
                "parameter": parameter,
                "value": value,
                "cfg": replace(BASE_CONFIG, **changes),
                "final_filter": True,
            }
        )

    add("side_long_only", "direction", "side_mode", "long", side_mode="long")
    add("side_short_only", "direction", "side_mode", "short", side_mode="short")

    for fast, slow in ((9, 55), (12, 96), (34, 144), (55, 192), (96, 384)):
        add(f"ema_pair_{fast}_{slow}", "trend_definition", "ema_pair", f"{fast}/{slow}", ema_fast=fast, ema_slow=slow)

    for style in ("breakout", "momentum", "squeeze_breakout", "channel_reclaim", "trend_rsi_rebound", "bb_reversion", "ema_deviation_revert"):
        add(f"entry_style_{style}", "entry_logic", "entry_style", style, entry_style=style)

    add("donchian_24_unused_check", "unused_or_style_specific", "donchian", 24, donchian=24)
    add("breakout_buffer_zero_unused_check", "unused_or_style_specific", "breakout_buffer", 0.0, breakout_buffer=0.0)

    for window in (24, 96, 192):
        add(f"roc_window_{window}", "trend_filter", "roc_window", window, roc_window=window)

    add("remove_min_regime_age", "trend_filter", "min_regime_age", 0, min_regime_age=0)
    add("remove_max_regime_age", "trend_filter", "max_regime_age", 100000, max_regime_age=100000)
    add("remove_pullback_touch_requirement", "entry_logic", "pullback_buffer", 99.0, pullback_buffer=99.0)
    add("strict_pullback_touch", "entry_logic", "pullback_buffer", 0.0, pullback_buffer=0.0)
    add("looser_pullback_touch_0p01", "entry_logic", "pullback_buffer", 0.01, pullback_buffer=0.01)
    add("remove_max_dist_ema", "trend_filter", "max_dist_ema", 99.0, max_dist_ema=99.0)
    add("remove_min_dir_roc", "trend_filter", "min_dir_roc", -99.0, min_dir_roc=-99.0)
    add("remove_min_dir_rsi", "oscillator_filter", "min_dir_rsi", 0.0, min_dir_rsi=0.0)
    add("remove_max_dir_rsi", "oscillator_filter", "max_dir_rsi", 100.0, max_dir_rsi=100.0)
    add("remove_max_chop", "regime_filter", "max_chop", 100.0, max_chop=100.0)
    add("remove_min_dir_cmf", "flow_filter", "min_dir_cmf", -99.0, min_dir_cmf=-99.0)
    add("remove_min_efficiency", "regime_filter", "min_efficiency", 0.0, min_efficiency=0.0)

    add("enable_min_adx_14", "inactive_filter_probe", "min_adx", 14.0, min_adx=14.0)
    add("tighten_max_atr_ratio_2", "inactive_filter_probe", "max_atr_ratio", 2.0, max_atr_ratio=2.0)
    add("enable_min_rvol_1", "inactive_filter_probe", "min_rvol", 1.0, min_rvol=1.0)
    add("enable_require_macd", "inactive_filter_probe", "require_macd", True, require_macd=True)
    add("enable_require_obv", "inactive_filter_probe", "require_obv", True, require_obv=True)
    add("enable_require_htf", "inactive_filter_probe", "require_htf", True, require_htf=True)

    add("remove_initial_stop", "exit_risk", "stop_atr", 99.0, stop_atr=99.0)
    add("tighter_stop_0p5", "exit_risk", "stop_atr", 0.5, stop_atr=0.5)
    add("looser_stop_1p5", "exit_risk", "stop_atr", 1.5, stop_atr=1.5)
    add("remove_take_profit", "exit_risk", "tp_atr", 99.0, tp_atr=99.0)
    add("lower_take_profit_1p25", "exit_risk", "tp_atr", 1.25, tp_atr=1.25)
    add("higher_take_profit_3p0", "exit_risk", "tp_atr", 3.0, tp_atr=3.0)
    add("remove_trailing_stop", "exit_risk", "trail_atr", 0.0, trail_atr=0.0)
    add("looser_trailing_stop_1p5", "exit_risk", "trail_atr", 1.5, trail_atr=1.5)
    add("remove_max_hold", "exit_risk", "max_hold_bars", 100000, max_hold_bars=100000)
    add("shorter_max_hold_96", "exit_risk", "max_hold_bars", 96, max_hold_bars=96)
    add("remove_min_hold", "exit_risk", "min_hold_bars", 0, min_hold_bars=0)
    add("enable_exit_ema_21", "inactive_exit_probe", "exit_ema", 21, exit_ema=21)
    add("enable_cooldown_6", "inactive_exit_probe", "cooldown_bars", 6, cooldown_bars=6)
    return variants


def main() -> None:
    frame = add_features(load_all_hype_5m())
    args = SimpleNamespace(min_full_trades=80, min_slice_trades=12, min_forward_trades=5)
    slices = validation_slices(frame, args)
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    for variant in build_variants():
        summary, slices_for_variant = evaluate(frame=frame, slices=slices, **variant)
        summary_rows.append(summary)
        slice_rows.extend(slices_for_variant)

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"] == "baseline"].iloc[0]
    summary["delta_full_annualized_multiple"] = summary["full_annualized_multiple"] - float(
        baseline["full_annualized_multiple"]
    )
    summary["delta_full_win_rate"] = summary["full_win_rate"] - float(baseline["full_win_rate"])
    summary["delta_full_payoff_ratio"] = summary["full_payoff_ratio"] - float(baseline["full_payoff_ratio"])
    summary["delta_full_max_dd"] = summary["full_max_dd"] - float(baseline["full_max_dd"])
    summary["delta_full_trades"] = summary["full_trades"] - int(baseline["full_trades"])
    summary["delta_min_slice_annualized_multiple"] = summary["min_slice_annualized_multiple"] - float(
        baseline["min_slice_annualized_multiple"]
    )
    summary["delta_min_slice_win_rate"] = summary["min_slice_win_rate"] - float(baseline["min_slice_win_rate"])
    summary["delta_min_slice_payoff_ratio"] = summary["min_slice_payoff_ratio"] - float(
        baseline["min_slice_payoff_ratio"]
    )
    summary["delta_worst_slice_max_dd"] = summary["worst_slice_max_dd"] - float(baseline["worst_slice_max_dd"])
    summary["abs_full_ann_delta_rank"] = summary["delta_full_annualized_multiple"].abs().rank(ascending=False)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    pd.DataFrame(slice_rows).to_csv(SLICE_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE_PP_R05732__dir_htf_ge_0.688442",
                "leverage": LEVERAGE,
                "final_filter": FINAL_FILTER_NAME,
                "mae_mfe_definition": "actual entry-to-exit path only",
                "base_config": asdict(BASE_CONFIG),
                "outputs": {
                    "summary_csv": str(SUMMARY_PATH),
                    "slice_csv": str(SLICE_PATH),
                },
                "baseline": baseline.to_dict(),
                "top_negative_full_annualized_deltas": summary.sort_values("delta_full_annualized_multiple")
                .head(12)
                .to_dict(orient="records"),
                "top_positive_full_annualized_deltas": summary.sort_values("delta_full_annualized_multiple", ascending=False)
                .head(12)
                .to_dict(orient="records"),
                "all_rows": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"slices={SLICE_PATH}")
    columns = [
        "label",
        "family",
        "parameter",
        "value",
        "full_trades",
        "full_annualized_multiple",
        "full_win_rate",
        "full_payoff_ratio",
        "full_max_dd",
        "min_slice_annualized_multiple",
        "min_slice_win_rate",
        "min_slice_payoff_ratio",
        "worst_slice_max_dd",
        "forward_2026_06_01_latest_trades",
        "forward_2026_06_01_latest_annualized_multiple",
        "forward_2026_06_01_latest_win_rate",
        "delta_full_annualized_multiple",
        "delta_full_trades",
    ]
    print(summary[columns].sort_values("delta_full_annualized_multiple").to_string(index=False))


if __name__ == "__main__":
    main()
