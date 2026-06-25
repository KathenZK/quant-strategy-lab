from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


MAIN_RANKING = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_positive_payoff_search_ranking.csv")
TARGETED_RANKING = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_positive_payoff_targeted_r05578.csv")
REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_survival_frontier.json")
FRONTIER_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_survival_frontier_summary.csv")
BEST_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_survival_frontier_best_rows.csv")

SLICE_PREFIXES = [
    "full",
    "slice_2025_05_30_2025_09_01",
    "slice_2025_09_01_2025_12_01",
    "slice_2025_12_01_2026_03_01",
    "slice_2026_03_01_2026_06_01",
    "forward_2026_06_01_latest",
]
TRADE_MINIMUMS = {
    "full": 80,
    "slice_2025_05_30_2025_09_01": 12,
    "slice_2025_09_01_2025_12_01": 12,
    "slice_2025_12_01_2026_03_01": 12,
    "slice_2026_03_01_2026_06_01": 12,
    "forward_2026_06_01_latest": 5,
}
WIN_THRESHOLDS = (0.55, 0.58, 0.60)
DD_LIMITS = (-0.20, -0.25, -0.30)


def load_candidates() -> pd.DataFrame:
    frames = [pd.read_csv(MAIN_RANKING)]
    if TARGETED_RANKING.exists():
        frames.append(pd.read_csv(TARGETED_RANKING))
    frame = pd.concat(frames, ignore_index=True)
    frame = frame.drop_duplicates(
        subset=["name", "filter_name", "leverage", "stage"],
        keep="first",
    ).reset_index(drop=True)
    return frame


def add_survival_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["min_slice_win_rate"] = result[[f"{prefix}_win_rate" for prefix in SLICE_PREFIXES]].min(axis=1)
    result["min_slice_payoff_ratio"] = result[[f"{prefix}_payoff_ratio" for prefix in SLICE_PREFIXES]].min(axis=1)
    result["min_slice_annualized_multiple"] = result[
        [f"{prefix}_annualized_multiple" for prefix in SLICE_PREFIXES]
    ].min(axis=1)
    result["min_slice_trades"] = result[[f"{prefix}_trades" for prefix in SLICE_PREFIXES]].min(axis=1)
    result["worst_slice_max_dd"] = result[[f"{prefix}_max_dd" for prefix in SLICE_PREFIXES]].min(axis=1)
    trade_ok = pd.Series(True, index=result.index)
    for prefix, minimum in TRADE_MINIMUMS.items():
        trade_ok &= result[f"{prefix}_trades"] >= minimum
    result["trade_minimums_ok"] = trade_ok
    return result


def filter_survivors(frame: pd.DataFrame, *, win_threshold: float, dd_limit: float) -> pd.DataFrame:
    return frame.loc[
        (frame["trade_minimums_ok"])
        & (frame["min_slice_win_rate"] >= win_threshold)
        & (frame["min_slice_payoff_ratio"] > 1.0)
        & (frame["worst_slice_max_dd"] >= dd_limit)
    ].copy()


def compact_row(row: pd.Series, *, win_threshold: float, dd_limit: float, rank_name: str) -> dict[str, Any]:
    return {
        "win_threshold": win_threshold,
        "dd_limit": dd_limit,
        "rank_name": rank_name,
        "name": row["name"],
        "stage": row["stage"],
        "leverage": row["leverage"],
        "full_annualized_multiple": row["full_annualized_multiple"],
        "full_win_rate": row["full_win_rate"],
        "full_payoff_ratio": row["full_payoff_ratio"],
        "full_max_dd": row["full_max_dd"],
        "full_trades": row["full_trades"],
        "min_slice_annualized_multiple": row["min_slice_annualized_multiple"],
        "min_slice_win_rate": row["min_slice_win_rate"],
        "min_slice_payoff_ratio": row["min_slice_payoff_ratio"],
        "worst_slice_max_dd": row["worst_slice_max_dd"],
        "forward_annualized_multiple": row["forward_2026_06_01_latest_annualized_multiple"],
        "forward_win_rate": row["forward_2026_06_01_latest_win_rate"],
        "forward_payoff_ratio": row["forward_2026_06_01_latest_payoff_ratio"],
        "forward_max_dd": row["forward_2026_06_01_latest_max_dd"],
        "forward_trades": row["forward_2026_06_01_latest_trades"],
        "entry_style": row["entry_style"],
        "side_mode": row["side_mode"],
        "ema_fast": row["ema_fast"],
        "ema_slow": row["ema_slow"],
        "stop_atr": row["stop_atr"],
        "tp_atr": row["tp_atr"],
        "trail_atr": row["trail_atr"],
        "max_hold_bars": row["max_hold_bars"],
        "filter_name": row["filter_name"],
    }


def main() -> None:
    frame = add_survival_columns(load_candidates())
    frontier_rows: list[dict[str, Any]] = []
    best_rows: list[dict[str, Any]] = []

    for win_threshold in WIN_THRESHOLDS:
        for dd_limit in DD_LIMITS:
            survivors = filter_survivors(frame, win_threshold=win_threshold, dd_limit=dd_limit)
            row: dict[str, Any] = {
                "win_threshold": win_threshold,
                "dd_limit": dd_limit,
                "survivor_rows": int(len(survivors)),
                "best_full_annualized_multiple": 0.0,
                "best_min_slice_annualized_multiple": 0.0,
                "best_forward_annualized_multiple": 0.0,
            }
            if not survivors.empty:
                by_full = survivors.sort_values(
                    ["full_annualized_multiple", "min_slice_annualized_multiple"],
                    ascending=[False, False],
                ).iloc[0]
                by_min = survivors.sort_values(
                    ["min_slice_annualized_multiple", "full_annualized_multiple"],
                    ascending=[False, False],
                ).iloc[0]
                by_forward = survivors.sort_values(
                    ["forward_2026_06_01_latest_annualized_multiple", "full_annualized_multiple"],
                    ascending=[False, False],
                ).iloc[0]
                row.update(
                    {
                        "best_full_annualized_multiple": float(by_full["full_annualized_multiple"]),
                        "best_full_name": by_full["name"],
                        "best_min_slice_annualized_multiple": float(by_min["min_slice_annualized_multiple"]),
                        "best_min_slice_name": by_min["name"],
                        "best_forward_annualized_multiple": float(
                            by_forward["forward_2026_06_01_latest_annualized_multiple"]
                        ),
                        "best_forward_name": by_forward["name"],
                    }
                )
                best_rows.extend(
                    [
                        compact_row(by_full, win_threshold=win_threshold, dd_limit=dd_limit, rank_name="best_full"),
                        compact_row(by_min, win_threshold=win_threshold, dd_limit=dd_limit, rank_name="best_min_slice"),
                        compact_row(by_forward, win_threshold=win_threshold, dd_limit=dd_limit, rank_name="best_forward"),
                    ]
                )
            frontier_rows.append(row)

    frontier = pd.DataFrame(frontier_rows)
    best = pd.DataFrame(best_rows)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frontier.to_csv(FRONTIER_PATH, index=False)
    best.to_csv(BEST_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "source": [str(MAIN_RANKING), str(TARGETED_RANKING)],
                "slices": SLICE_PREFIXES,
                "trade_minimums": TRADE_MINIMUMS,
                "constraints": {
                    "win_thresholds": WIN_THRESHOLDS,
                    "dd_limits": DD_LIMITS,
                    "payoff_ratio": "> 1.0 on every slice",
                },
                "frontier": frontier_rows,
                "best_rows": best_rows,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"frontier={FRONTIER_PATH}")
    print(f"best={BEST_PATH}")
    print(frontier.to_string(index=False))
    if not best.empty:
        print(best.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
