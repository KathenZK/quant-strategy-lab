from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from ablate_hype_5m_r05732 import BASE_CONFIG as V1_BASE_CONFIG, simulate_trades_actual_path_mae
from research_hype_5m_filter_refinement import feature_values
from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal
from research_hype_5m_positive_payoff_search import load_all_hype_5m, metric_from_trades, validation_slices


REPORT_PATH = Path("reports/hype_5m_pbtr_v2_ablation_slices.json")
ABLATION_SUMMARY_PATH = Path("reports/hype_5m_pbtr_v2_ablation_summary.csv")
ABLATION_SLICE_PATH = Path("reports/hype_5m_pbtr_v2_ablation_validation_slices.csv")
WEEKLY_SLICE_PATH = Path("reports/hype_5m_pbtr_v2_weekly_slices.csv")
ROLLING_WINDOW_PATH = Path("reports/hype_5m_pbtr_v2_rolling_windows.csv")

LEVERAGE = 1.0
FINAL_FILTER_THRESHOLD = 0.5

V2_BASE_CONFIG = replace(
    V1_BASE_CONFIG,
    name="HYPE-5M-PBTR-V2",
    pullback_buffer=0.01,
    roc_window=96,
    min_efficiency=0.0,
    stop_atr=0.5,
    tp_atr=99.0,
    trail_atr=0.75,
)


def apply_final_filter(
    frame: pd.DataFrame,
    cfg: SearchConfig,
    signal: np.ndarray,
    *,
    enabled: bool,
    threshold: float = FINAL_FILTER_THRESHOLD,
) -> np.ndarray:
    if not enabled:
        return signal.copy()
    sig_idx = np.flatnonzero(signal)
    if len(sig_idx) == 0:
        return signal.copy()
    values = feature_values(frame, cfg, signal, sig_idx)
    keep = values["dir_htf"] >= threshold
    filtered = np.zeros_like(signal)
    filtered[sig_idx[keep]] = signal[sig_idx[keep]]
    previous_same = np.r_[False, (filtered[1:] != 0) & (filtered[1:] == filtered[:-1])]
    filtered[previous_same] = 0
    return filtered


def metric_with_sides(trades: list[Trade], leverage: float, *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    base = metric_from_trades(trades, leverage, start=start, end=end)
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    longs = [trade for trade in selected if trade.side > 0]
    shorts = [trade for trade in selected if trade.side < 0]
    long_count = len(longs)
    short_count = len(shorts)
    long_rets = np.array([trade.net_ret_1x for trade in longs], dtype=float)
    short_rets = np.array([trade.net_ret_1x for trade in shorts], dtype=float)

    def side_stats(rets: np.ndarray) -> tuple[float, float]:
        if len(rets) == 0:
            return 0.0, 0.0
        wins = rets[rets > 0]
        losses = rets[rets <= 0]
        win_rate = float((rets > 0).mean())
        avg_win = float(wins.mean()) if len(wins) else 0.0
        avg_loss_abs = float(abs(losses.mean())) if len(losses) else 0.0
        payoff = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
        return win_rate, payoff

    long_win_rate, long_payoff = side_stats(long_rets)
    short_win_rate, short_payoff = side_stats(short_rets)
    if long_count == 0 and short_count == 0:
        long_short_ratio = 0.0
        long_share = 0.0
        short_share = 0.0
    elif short_count == 0:
        long_short_ratio = float("inf")
        long_share = 1.0
        short_share = 0.0
    elif long_count == 0:
        long_short_ratio = 0.0
        long_share = 0.0
        short_share = 1.0
    else:
        long_short_ratio = float(long_count / short_count)
        total = long_count + short_count
        long_share = float(long_count / total)
        short_share = float(short_count / total)

    return {
        **base,
        "long_trades": int(long_count),
        "short_trades": int(short_count),
        "long_short_ratio": long_short_ratio,
        "long_share": long_share,
        "short_share": short_share,
        "long_win_rate": long_win_rate,
        "short_win_rate": short_win_rate,
        "long_payoff_ratio": long_payoff,
        "short_payoff_ratio": short_payoff,
    }


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
    final_threshold: float = FINAL_FILTER_THRESHOLD,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signal = build_signal(frame, cfg)
    filtered_signal = apply_final_filter(
        frame,
        cfg,
        signal,
        enabled=final_filter,
        threshold=final_threshold,
    )
    trades = simulate_trades_actual_path_mae(frame, filtered_signal, cfg)
    summary: dict[str, Any] = {
        "label": label,
        "family": family,
        "parameter": parameter,
        "value": value,
        "final_filter_enabled": final_filter,
        "final_filter_threshold": final_threshold if final_filter else None,
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
    return summary, slice_rows


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {
            "label": "baseline",
            "family": "baseline",
            "parameter": "baseline",
            "value": "HYPE-5M-PBTR-V2",
            "cfg": V2_BASE_CONFIG,
            "final_filter": True,
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
        {
            "label": "remove_final_filter_dir_htf",
            "family": "filter_ablation",
            "parameter": "final_filter",
            "value": "disabled",
            "cfg": V2_BASE_CONFIG,
            "final_filter": False,
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
    ]

    def add(label: str, family: str, parameter: str, value: Any, **changes: Any) -> None:
        variants.append(
            {
                "label": label,
                "family": family,
                "parameter": parameter,
                "value": value,
                "cfg": replace(V2_BASE_CONFIG, **changes),
                "final_filter": True,
                "final_threshold": FINAL_FILTER_THRESHOLD,
            }
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

    for window in (24, 48, 192):
        add(f"roc_window_{window}", "trend_filter", "roc_window", window, roc_window=window)

    add("remove_min_regime_age", "trend_filter", "min_regime_age", 0, min_regime_age=0)
    add("remove_max_regime_age", "trend_filter", "max_regime_age", 100000, max_regime_age=100000)
    add("strict_pullback_touch", "entry_logic", "pullback_buffer", 0.0, pullback_buffer=0.0)
    add("baseline_pullback_0p0025", "entry_logic", "pullback_buffer", 0.0025, pullback_buffer=0.0025)
    add("remove_max_dist_ema", "trend_filter", "max_dist_ema", 99.0, max_dist_ema=99.0)
    add("remove_min_dir_roc", "trend_filter", "min_dir_roc", -99.0, min_dir_roc=-99.0)
    add("remove_min_dir_rsi", "oscillator_filter", "min_dir_rsi", 0.0, min_dir_rsi=0.0)
    add("remove_max_dir_rsi", "oscillator_filter", "max_dir_rsi", 100.0, max_dir_rsi=100.0)
    add("remove_max_chop", "regime_filter", "max_chop", 100.0, max_chop=100.0)
    add("remove_min_dir_cmf", "flow_filter", "min_dir_cmf", -99.0, min_dir_cmf=-99.0)
    add("restore_min_efficiency_0p025", "regime_filter", "min_efficiency", 0.025, min_efficiency=0.025)
    add("enable_min_adx_14", "inactive_filter_probe", "min_adx", 14.0, min_adx=14.0)
    add("tighten_max_atr_ratio_2", "inactive_filter_probe", "max_atr_ratio", 2.0, max_atr_ratio=2.0)
    add("enable_min_rvol_1", "inactive_filter_probe", "min_rvol", 1.0, min_rvol=1.0)
    add("enable_require_macd", "inactive_filter_probe", "require_macd", True, require_macd=True)
    add("enable_require_obv", "inactive_filter_probe", "require_obv", True, require_obv=True)
    add("enable_require_htf", "inactive_filter_probe", "require_htf", True, require_htf=True)
    add("remove_initial_stop", "exit_risk", "stop_atr", 99.0, stop_atr=99.0)
    add("looser_stop_0p75", "exit_risk", "stop_atr", 0.75, stop_atr=0.75)
    add("looser_stop_1p5", "exit_risk", "stop_atr", 1.5, stop_atr=1.5)
    add("restore_take_profit_1p875", "exit_risk", "tp_atr", 1.875, tp_atr=1.875)
    add("lower_take_profit_1p25", "exit_risk", "tp_atr", 1.25, tp_atr=1.25)
    add("remove_trailing_stop", "exit_risk", "trail_atr", 0.0, trail_atr=0.0)
    add("looser_trailing_stop_1p5", "exit_risk", "trail_atr", 1.5, trail_atr=1.5)
    add("remove_max_hold", "exit_risk", "max_hold_bars", 100000, max_hold_bars=100000)
    add("shorter_max_hold_96", "exit_risk", "max_hold_bars", 96, max_hold_bars=96)
    add("remove_min_hold", "exit_risk", "min_hold_bars", 0, min_hold_bars=0)
    add("enable_exit_ema_21", "inactive_exit_probe", "exit_ema", 21, exit_ema=21)
    add("enable_cooldown_6", "inactive_exit_probe", "cooldown_bars", 6, cooldown_bars=6)
    variants.append(
        {
            "label": "dir_htf_threshold_0p688442",
            "family": "filter_ablation",
            "parameter": "final_filter_threshold",
            "value": 0.688442,
            "cfg": V2_BASE_CONFIG,
            "final_filter": True,
            "final_threshold": 0.688442,
        }
    )
    return variants


def weekly_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0]).floor("D")
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    rows: list[dict[str, Any]] = []
    cursor = start
    week_idx = 1
    while cursor < end:
        week_end = min(cursor + pd.Timedelta(days=7), end)
        rows.append(
            {
                "name": f"week_{week_idx:03d}_{cursor.strftime('%Y%m%d')}_{(week_end - pd.Timedelta(minutes=5)).strftime('%Y%m%d')}",
                "start": cursor,
                "end": week_end,
            }
        )
        cursor = week_end
        week_idx += 1
    return rows


def rolling_windows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    start = pd.Timestamp(frame["ts"].iloc[0])
    return [
        {"name": "recent_1w", "start": end - pd.Timedelta(days=7), "end": end},
        {"name": "recent_1m", "start": end - pd.Timedelta(days=30), "end": end},
        {"name": "recent_3m", "start": end - pd.Timedelta(days=90), "end": end},
        {"name": "recent_6m", "start": end - pd.Timedelta(days=180), "end": end},
        {"name": "full", "start": start, "end": end},
    ]


def run_baseline_time_slices(frame: pd.DataFrame, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        weekly_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})

    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        rolling_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
    return pd.DataFrame(weekly_rows), pd.DataFrame(rolling_rows)


def main() -> None:
    frame = add_features(load_all_hype_5m())
    args = SimpleNamespace(min_full_trades=80, min_slice_trades=12, min_forward_trades=5)
    validation = validation_slices(frame, args)

    summary_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    baseline_trades: list[Trade] | None = None

    for variant in build_variants():
        final_threshold = float(variant.get("final_threshold", FINAL_FILTER_THRESHOLD))
        summary, slices_for_variant = evaluate_variant(
            frame,
            validation,
            label=variant["label"],
            family=variant["family"],
            parameter=variant["parameter"],
            value=variant["value"],
            cfg=variant["cfg"],
            final_filter=variant["final_filter"],
            final_threshold=final_threshold,
        )
        summary_rows.append(summary)
        validation_rows.extend(slices_for_variant)
        if variant["label"] == "baseline":
            signal = build_signal(frame, variant["cfg"])
            filtered_signal = apply_final_filter(frame, variant["cfg"], signal, enabled=True)
            baseline_trades = simulate_trades_actual_path_mae(frame, filtered_signal, variant["cfg"])

    if baseline_trades is None:
        raise RuntimeError("baseline trades missing")

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"] == "baseline"].iloc[0]
    summary["delta_full_annualized_multiple"] = summary["full_annualized_multiple"] - float(baseline["full_annualized_multiple"])
    summary["delta_full_win_rate"] = summary["full_win_rate"] - float(baseline["full_win_rate"])
    summary["delta_full_payoff_ratio"] = summary["full_payoff_ratio"] - float(baseline["full_payoff_ratio"])
    summary["delta_full_max_dd"] = summary["full_max_dd"] - float(baseline["full_max_dd"])
    summary["delta_full_trades"] = summary["full_trades"] - int(baseline["full_trades"])
    summary["delta_min_slice_annualized_multiple"] = summary["min_slice_annualized_multiple"] - float(
        baseline["min_slice_annualized_multiple"]
    )
    summary["delta_min_slice_win_rate"] = summary["min_slice_win_rate"] - float(baseline["min_slice_win_rate"])
    summary["delta_min_slice_payoff_ratio"] = summary["min_slice_payoff_ratio"] - float(baseline["min_slice_payoff_ratio"])
    summary["delta_worst_slice_max_dd"] = summary["worst_slice_max_dd"] - float(baseline["worst_slice_max_dd"])

    weekly_df, rolling_df = run_baseline_time_slices(frame, baseline_trades)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(ABLATION_SUMMARY_PATH, index=False)
    pd.DataFrame(validation_rows).to_csv(ABLATION_SLICE_PATH, index=False)
    weekly_df.to_csv(WEEKLY_SLICE_PATH, index=False)
    rolling_df.to_csv(ROLLING_WINDOW_PATH, index=False)

    top_negative = summary.sort_values("delta_full_annualized_multiple").head(12)
    top_positive = summary.sort_values("delta_full_annualized_multiple", ascending=False).head(12)

    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V2",
                "leverage": LEVERAGE,
                "final_filter_threshold": FINAL_FILTER_THRESHOLD,
                "base_config": asdict(V2_BASE_CONFIG),
                "outputs": {
                    "ablation_summary_csv": str(ABLATION_SUMMARY_PATH),
                    "ablation_validation_slices_csv": str(ABLATION_SLICE_PATH),
                    "weekly_slices_csv": str(WEEKLY_SLICE_PATH),
                    "rolling_windows_csv": str(ROLLING_WINDOW_PATH),
                },
                "baseline": baseline.to_dict(),
                "rolling_windows": rolling_df.to_dict(orient="records"),
                "weekly_slice_count": int(len(weekly_df)),
                "top_negative_full_annualized_deltas": top_negative.to_dict(orient="records"),
                "top_positive_full_annualized_deltas": top_positive.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print(f"wrote={REPORT_PATH}")
    print(f"summary={ABLATION_SUMMARY_PATH}")
    print(f"weekly={WEEKLY_SLICE_PATH}")
    print(f"rolling={ROLLING_WINDOW_PATH}")
    print("\nRolling windows:")
    print(
        rolling_df[
            [
                "window",
                "slice_start",
                "slice_end",
                "trades",
                "long_trades",
                "short_trades",
                "long_short_ratio",
                "long_share",
                "short_share",
                "total_return",
                "win_rate",
                "payoff_ratio",
                "long_win_rate",
                "short_win_rate",
                "max_dd",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
