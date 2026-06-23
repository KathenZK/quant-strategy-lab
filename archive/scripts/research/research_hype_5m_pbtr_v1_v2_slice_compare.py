from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from ablate_hype_5m_r05732 import BASE_CONFIG as V1_BASE_CONFIG, simulate_trades_actual_path_mae
from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal
from research_hype_5m_positive_payoff_search import load_all_hype_5m
from research_hype_5m_pbtr_v2_ablation_slices import (
    LEVERAGE,
    V2_BASE_CONFIG,
    apply_final_filter,
    metric_with_sides,
    rolling_windows,
    weekly_slices,
)

V1_FINAL_THRESHOLD = 0.688442

V1_CONFIG = replace(V1_BASE_CONFIG, name="HYPE-5M-PBTR-V1")

REPORT_PATH = Path("reports/hype_5m_pbtr_v1_v2_slice_compare.json")
V1_WEEKLY_PATH = Path("reports/hype_5m_pbtr_v1_weekly_slices.csv")
V1_ROLLING_PATH = Path("reports/hype_5m_pbtr_v1_rolling_windows.csv")
V2_WEEKLY_PATH = Path("reports/hype_5m_pbtr_v2_weekly_slices.csv")
V2_ROLLING_PATH = Path("reports/hype_5m_pbtr_v2_rolling_windows.csv")
COMPARE_ROLLING_PATH = Path("reports/hype_5m_pbtr_v1_v2_rolling_compare.csv")
COMPARE_WEEKLY_PATH = Path("reports/hype_5m_pbtr_v1_v2_weekly_compare.csv")


def run_trades(frame: pd.DataFrame, cfg: SearchConfig, *, threshold: float) -> list[Trade]:
    signal = build_signal(frame, cfg)
    filtered = apply_final_filter(frame, cfg, signal, enabled=True, threshold=threshold)
    return simulate_trades_actual_path_mae(frame, filtered, cfg)


def build_slice_rows(frame: pd.DataFrame, trades: list[Trade], slices: list[dict[str, Any]], *, version: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        rows.append(
            {
                "version": version,
                "window": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:+.{digits}f}%" if value >= 0 else f"{value * 100:.{digits}f}%"


def ratio_text(value: float) -> str:
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}"


def main() -> None:
    frame = add_features(load_all_hype_5m())
    v1_trades = run_trades(frame, V1_CONFIG, threshold=V1_FINAL_THRESHOLD)
    v2_trades = run_trades(frame, V2_BASE_CONFIG, threshold=0.5)

    weekly = weekly_slices(frame)
    rolling = rolling_windows(frame)

    v1_weekly = build_slice_rows(frame, v1_trades, weekly, version="V1")
    v2_weekly = build_slice_rows(frame, v2_trades, weekly, version="V2")
    v1_rolling = build_slice_rows(frame, v1_trades, rolling, version="V1")
    v2_rolling = build_slice_rows(frame, v2_trades, rolling, version="V2")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    v1_weekly.to_csv(V1_WEEKLY_PATH, index=False)
    v1_rolling.to_csv(V1_ROLLING_PATH, index=False)

    compare_rolling = pd.concat([v1_rolling, v2_rolling], ignore_index=True)
    compare_weekly = pd.merge(
        v1_weekly.add_suffix("_v1"),
        v2_weekly.add_suffix("_v2"),
        left_on="window_v1",
        right_on="window_v2",
        how="inner",
    )
    compare_rolling.to_csv(COMPARE_ROLLING_PATH, index=False)
    compare_weekly.to_csv(COMPARE_WEEKLY_PATH, index=False)

    REPORT_PATH.write_text(
        json.dumps(
            {
                "v1": {
                    "config": "HYPE-5M-PBTR-V1",
                    "final_filter_threshold": V1_FINAL_THRESHOLD,
                    "weekly_csv": str(V1_WEEKLY_PATH),
                    "rolling_csv": str(V1_ROLLING_PATH),
                    "rolling_windows": v1_rolling.to_dict(orient="records"),
                },
                "v2": {
                    "config": "HYPE-5M-PBTR-V2",
                    "final_filter_threshold": 0.5,
                    "weekly_csv": str(V2_WEEKLY_PATH),
                    "rolling_csv": str(V2_ROLLING_PATH),
                    "rolling_windows": v2_rolling.to_dict(orient="records"),
                },
                "compare_rolling_csv": str(COMPARE_ROLLING_PATH),
                "compare_weekly_csv": str(COMPARE_WEEKLY_PATH),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print(f"wrote={REPORT_PATH}")
    print(f"v1_weekly={V1_WEEKLY_PATH}")
    print(f"v1_rolling={V1_ROLLING_PATH}")
    print(f"compare_rolling={COMPARE_ROLLING_PATH}")
    print("\nRolling compare:")
    show_cols = [
        "version",
        "window",
        "trades",
        "long_trades",
        "short_trades",
        "long_short_ratio",
        "total_return",
        "win_rate",
        "payoff_ratio",
        "max_dd",
    ]
    print(compare_rolling[show_cols].to_string(index=False))


if __name__ == "__main__":
    main()
