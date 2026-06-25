from __future__ import annotations

import itertools
import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from ablate_hype_5m_r05732 import BASE_CONFIG, simulate_trades_actual_path_mae
from research_hype_5m_filter_refinement import feature_values
from research_hype_5m_indicator_search import SearchConfig, add_features, build_signal
from research_hype_5m_positive_payoff_search import load_all_hype_5m, metric_from_trades, validation_slices


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_r05732_v2_combo_test.json")
RANKING_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_r05732_v2_combo_test_ranking.csv")
SLICE_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_r05732_v2_combo_test_slices.csv")

LEVERAGE = 1.0


EMA_PAIRS = ((21, 96), (12, 96))
PULLBACK_BUFFERS = (0.0025, 0.005, 0.01, 0.015, 99.0)
TP_ATRS = (1.875, 2.5, 3.0, 99.0)
STOP_ATRS = (0.5, 0.75)
MAX_CHOPS = (62.0, 100.0)
MIN_EFFICIENCIES = (0.0, 0.025)
MIN_DIR_RSIS = (50.0, 55.0)
ROC_WINDOWS = (24, 48, 96, 192)
DIR_HTF_THRESHOLDS = (0.5, 0.688442, 0.946715, None)

MIN_SLICE_WIN = 0.56
MIN_SLICE_PAYOFF = 1.8
MAX_WORST_DD = -0.12
MIN_FULL_TRADES = 500
MIN_FORWARD_TRADES = 20


def apply_dir_htf_filter(
    frame: pd.DataFrame,
    cfg: SearchConfig,
    signal: np.ndarray,
    threshold: float | None,
) -> np.ndarray:
    if threshold is None:
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


def evaluate_variant(
    frame: pd.DataFrame,
    slices: list[dict[str, Any]],
    cfg: SearchConfig,
    *,
    dir_htf_threshold: float | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signal = build_signal(frame, cfg)
    filtered_signal = apply_dir_htf_filter(frame, cfg, signal, dir_htf_threshold)
    trades = simulate_trades_actual_path_mae(frame, filtered_signal, cfg)
    label = (
        f"ema{cfg.ema_fast}_{cfg.ema_slow}"
        f"_pb{cfg.pullback_buffer:g}"
        f"_tp{cfg.tp_atr:g}"
        f"_sl{cfg.stop_atr:g}"
        f"_chop{cfg.max_chop:g}"
        f"_eff{cfg.min_efficiency:g}"
        f"_rsi{cfg.min_dir_rsi:g}"
        f"_roc{cfg.roc_window:g}"
        f"_htf{'none' if dir_htf_threshold is None else f'{dir_htf_threshold:g}'}"
    )
    summary: dict[str, Any] = {
        "label": label,
        "dir_htf_threshold": dir_htf_threshold if dir_htf_threshold is not None else "disabled",
        "final_filter_enabled": dir_htf_threshold is not None,
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
            "slice": item["name"],
            **metrics,
        }
        slice_rows.append(row)
        min_win = min(min_win, float(metrics["win_rate"]))
        min_payoff = min(min_payoff, float(metrics["payoff_ratio"]))
        min_ann = min(min_ann, float(metrics["annualized_multiple"]))
        worst_dd = min(worst_dd, float(metrics["max_dd"]))
        for key, value in metrics.items():
            summary[f"{item['name']}_{key}"] = value
    summary["min_slice_win_rate"] = min_win
    summary["min_slice_payoff_ratio"] = min_payoff
    summary["min_slice_annualized_multiple"] = min_ann
    summary["worst_slice_max_dd"] = worst_dd
    summary["passes_v2_gate"] = (
        int(summary["full_trades"]) >= MIN_FULL_TRADES
        and int(summary["forward_2026_06_01_latest_trades"]) >= MIN_FORWARD_TRADES
        and min_win >= MIN_SLICE_WIN
        and min_payoff >= MIN_SLICE_PAYOFF
        and worst_dd >= MAX_WORST_DD
    )
    summary["score"] = (
        min(float(summary["full_annualized_multiple"]), 200.0)
        + 4.0 * min(float(summary["min_slice_annualized_multiple"]), 80.0)
        + 100.0 * min_win
        + 20.0 * min(min_payoff, 3.0)
        + 50.0 * worst_dd
        - 0.003 * max(0, int(summary["full_trades"]) - 2500)
    )
    return summary, slice_rows


def config_grid() -> list[tuple[SearchConfig, float | None]]:
    rows: list[tuple[SearchConfig, float | None]] = []
    for (
        (ema_fast, ema_slow),
        pullback_buffer,
        tp_atr,
        stop_atr,
        max_chop,
        min_efficiency,
        min_dir_rsi,
        roc_window,
        dir_htf_threshold,
    ) in itertools.product(
        EMA_PAIRS,
        PULLBACK_BUFFERS,
        TP_ATRS,
        STOP_ATRS,
        MAX_CHOPS,
        MIN_EFFICIENCIES,
        MIN_DIR_RSIS,
        ROC_WINDOWS,
        DIR_HTF_THRESHOLDS,
    ):
        cfg = replace(
            BASE_CONFIG,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            pullback_buffer=pullback_buffer,
            tp_atr=tp_atr,
            stop_atr=stop_atr,
            max_chop=max_chop,
            min_efficiency=min_efficiency,
            min_dir_rsi=min_dir_rsi,
            roc_window=roc_window,
        )
        rows.append((cfg, dir_htf_threshold))
    return rows


def main() -> None:
    frame = add_features(load_all_hype_5m())
    args = SimpleNamespace(min_full_trades=80, min_slice_trades=12, min_forward_trades=5)
    slices = validation_slices(frame, args)
    rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    grid = config_grid()
    for idx, (cfg, dir_htf_threshold) in enumerate(grid, start=1):
        if idx % 250 == 0:
            print(f"tested={idx}/{len(grid)} rows={len(rows)}", flush=True)
        summary, variant_slices = evaluate_variant(frame, slices, cfg, dir_htf_threshold=dir_htf_threshold)
        rows.append(summary)
        slice_rows.extend(variant_slices)

    ranking = pd.DataFrame(rows).sort_values(
        ["passes_v2_gate", "score", "min_slice_annualized_multiple", "full_annualized_multiple"],
        ascending=[False, False, False, False],
    )
    slices_frame = pd.DataFrame(slice_rows)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    slices_frame.to_csv(SLICE_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_line": "HYPE-5M-PBTR R05732",
                "source": "synchronous tweaks from R05732 full-parameter ablation",
                "constraints": {
                    "min_slice_win_rate": MIN_SLICE_WIN,
                    "min_slice_payoff_ratio": MIN_SLICE_PAYOFF,
                    "worst_slice_max_dd_at_least": MAX_WORST_DD,
                    "min_full_trades": MIN_FULL_TRADES,
                    "min_forward_trades": MIN_FORWARD_TRADES,
                    "mae_mfe_definition": "actual entry-to-exit path",
                },
                "grid": {
                    "ema_pairs": EMA_PAIRS,
                    "pullback_buffers": PULLBACK_BUFFERS,
                    "tp_atrs": TP_ATRS,
                    "stop_atrs": STOP_ATRS,
                    "max_chops": MAX_CHOPS,
                    "min_efficiencies": MIN_EFFICIENCIES,
                    "min_dir_rsis": MIN_DIR_RSIS,
                    "roc_windows": ROC_WINDOWS,
                    "dir_htf_thresholds": DIR_HTF_THRESHOLDS,
                    "total": len(grid),
                },
                "top_rows": ranking.head(80).to_dict(orient="records"),
                "outputs": {
                    "ranking_csv": str(RANKING_PATH),
                    "slice_csv": str(SLICE_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"slices={SLICE_PATH}")
    columns = [
        "label",
        "passes_v2_gate",
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
        "cfg_ema_fast",
        "cfg_ema_slow",
        "cfg_pullback_buffer",
        "cfg_tp_atr",
        "cfg_stop_atr",
        "cfg_max_chop",
        "cfg_min_efficiency",
        "cfg_min_dir_rsi",
        "cfg_roc_window",
        "dir_htf_threshold",
    ]
    print(ranking[columns].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
