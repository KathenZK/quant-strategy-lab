from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_ensemble_combo import END_TS, IS_END_TS, START_TS, choose_one_position, metric_from_rows


LEGS_PATH = Path("reports/hype_5m_ensemble_combo_legs.csv")
TRADES_PATH = Path("reports/hype_5m_filter_refinement_top_trades.csv")
RANKING_PATH = Path("reports/hype_5m_ensemble_combo_ranking.csv")
REPORT_PATH = Path("reports/hype_5m_ensemble_ablation.json")
SUMMARY_OUT = Path("reports/hype_5m_ensemble_ablation_summary.csv")
DROP_LEG_OUT = Path("reports/hype_5m_ensemble_ablation_drop_leg.csv")
LEVERAGE_OUT = Path("reports/hype_5m_ensemble_ablation_leverage.csv")
EXECUTION_OUT = Path("reports/hype_5m_ensemble_ablation_execution.csv")

TARGET_COMBOS: tuple[tuple[int, float], ...] = (
    (8, 4.0),
    (16, 2.5),
    (8, 3.0),
    (12, 2.5),
    (5, 3.0),
    (16, 2.0),
    (8, 2.5),
)
LEVERAGE_ABLATIONS: dict[float, tuple[float, ...]] = {
    4.0: (3.0, 4.0, 5.0),
    3.0: (2.5, 3.0, 4.0),
    2.5: (2.0, 2.5, 3.0),
    2.0: (1.5, 2.0, 2.5),
}


def combo_id(legs: int, leverage: float) -> str:
    leverage_text = f"{leverage:g}".replace(".", "p")
    return f"{legs}legs_{leverage_text}x"


def prefixed_metrics(rows: list[dict[str, Any]], leverage: float, prefix: str) -> dict[str, float | int]:
    metrics = metric_from_rows(rows, leverage, start=START_TS, end=END_TS)
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def combo_metrics(rows: list[dict[str, Any]], leverage: float) -> dict[str, float | int]:
    full = metric_from_rows(rows, leverage, start=START_TS, end=END_TS)
    in_sample = metric_from_rows(rows, leverage, start=START_TS, end=IS_END_TS)
    oos = metric_from_rows(rows, leverage, start=IS_END_TS, end=END_TS)
    return {
        **{f"full_{key}": value for key, value in full.items()},
        **{f"is_{key}": value for key, value in in_sample.items()},
        **{f"oos_{key}": value for key, value in oos.items()},
    }


def choose_all_signals(trades: pd.DataFrame, names: list[str]) -> list[dict[str, Any]]:
    sub = trades.loc[trades["refined_name"].isin(names)].copy()
    sub = sub.sort_values(["entry_ts", "leg_rank"])
    selected: list[dict[str, Any]] = []
    used: set[tuple[pd.Timestamp, int]] = set()
    for _, row in sub.iterrows():
        key = (row["signal_ts"], int(row["side"]))
        if key in used:
            continue
        used.add(key)
        selected.append(row.to_dict())
    return selected


def with_delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "delta_full_annualized_multiple": float(row["full_annualized_multiple"])
        - float(baseline["full_annualized_multiple"]),
        "delta_full_max_dd": float(row["full_max_dd"]) - float(baseline["full_max_dd"]),
        "delta_full_win_rate": float(row["full_win_rate"]) - float(baseline["full_win_rate"]),
        "delta_full_trades": int(row["full_trades"]) - int(baseline["full_trades"]),
    }


def main() -> None:
    if not LEGS_PATH.exists() or not TRADES_PATH.exists() or not RANKING_PATH.exists():
        raise FileNotFoundError("run research_hype_5m_ensemble_combo.py before ablation")

    legs = pd.read_csv(LEGS_PATH)
    legs["leg_rank"] = np.arange(1, len(legs) + 1)
    trades = pd.read_csv(TRADES_PATH, parse_dates=["signal_ts", "entry_ts", "exit_ts"])
    rank_map = dict(zip(legs["refined_name"], legs["leg_rank"], strict=True))
    trades["leg_rank"] = trades["refined_name"].map(rank_map)
    ranking = pd.read_csv(RANKING_PATH)

    summary_rows: list[dict[str, Any]] = []
    drop_rows: list[dict[str, Any]] = []
    leverage_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    report_items: list[dict[str, Any]] = []

    for count, leverage in TARGET_COMBOS:
        cid = combo_id(count, leverage)
        selected_leg_frame = legs.head(count).copy()
        names = selected_leg_frame["refined_name"].tolist()
        baseline_rows = choose_one_position(trades, names)
        baseline_metrics = combo_metrics(baseline_rows, leverage)
        baseline = {
            "combo_id": cid,
            "legs": count,
            "leverage": leverage,
            "variant": "baseline",
            "removed_leg_rank": 0,
            "removed_base_name": "",
            "removed_filter_name": "",
            **baseline_metrics,
        }
        summary_rows.append(baseline)

        source = ranking.query("legs == @count and leverage == @leverage")
        source_target_pass = bool(source.iloc[0]["target_pass"]) if len(source) else False

        for _, leg in selected_leg_frame.iterrows():
            remaining_names = [name for name in names if name != leg["refined_name"]]
            ablated_rows = choose_one_position(trades, remaining_names)
            row = {
                "combo_id": cid,
                "legs": count,
                "leverage": leverage,
                "variant": "drop_leg",
                "removed_leg_rank": int(leg["leg_rank"]),
                "removed_base_name": str(leg["base_name"]),
                "removed_filter_name": str(leg["filter_name"]),
                "removed_refined_name": str(leg["refined_name"]),
                **combo_metrics(ablated_rows, leverage),
            }
            drop_rows.append(with_delta(row, baseline))

        for test_leverage in LEVERAGE_ABLATIONS[leverage]:
            row = {
                "combo_id": cid,
                "legs": count,
                "baseline_leverage": leverage,
                "test_leverage": test_leverage,
                "variant": "leverage",
                **combo_metrics(baseline_rows, test_leverage),
            }
            leverage_rows.append(with_delta(row, baseline))

        overlap_rows = choose_all_signals(trades, names)
        one_position_row = {
            "combo_id": cid,
            "legs": count,
            "leverage": leverage,
            "variant": "one_position_only",
            "execution_model": "flat_before_next_entry",
            **baseline_metrics,
        }
        all_signals_row = {
            "combo_id": cid,
            "legs": count,
            "leverage": leverage,
            "variant": "allow_overlapping_signals",
            "execution_model": "all_deduped_signals_marked_sequentially",
            **combo_metrics(overlap_rows, leverage),
        }
        execution_rows.extend([with_delta(one_position_row, baseline), with_delta(all_signals_row, baseline)])

        report_items.append(
            {
                "combo_id": cid,
                "legs": count,
                "leverage": leverage,
                "source_target_pass": source_target_pass,
                "included_legs": selected_leg_frame.to_dict(orient="records"),
                "baseline": baseline,
                "drop_leg": [row for row in drop_rows if row["combo_id"] == cid],
                "leverage_ablation": [row for row in leverage_rows if row["combo_id"] == cid],
                "execution": [row for row in execution_rows if row["combo_id"] == cid],
            }
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(SUMMARY_OUT, index=False)
    pd.DataFrame(drop_rows).to_csv(DROP_LEG_OUT, index=False)
    pd.DataFrame(leverage_rows).to_csv(LEVERAGE_OUT, index=False)
    pd.DataFrame(execution_rows).to_csv(EXECUTION_OUT, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "source_legs": str(LEGS_PATH),
                    "source_trades": str(TRADES_PATH),
                    "source_ranking": str(RANKING_PATH),
                    "start": START_TS.isoformat(),
                    "end_exclusive": END_TS.isoformat(),
                    "is_end_exclusive": IS_END_TS.isoformat(),
                },
                "method": {
                    "drop_leg": "remove one included refined leg and rebuild the one-position ensemble at the same leverage",
                    "leverage": "keep the same selected trades and test adjacent leverage values",
                    "execution": "compare one-position-only execution with taking all de-duplicated leg signals",
                },
                "combos": report_items,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"summary={SUMMARY_OUT}")
    print(f"drop_leg={DROP_LEG_OUT}")
    print(f"leverage={LEVERAGE_OUT}")
    print(f"execution={EXECUTION_OUT}")
    print(pd.DataFrame(summary_rows).to_string(index=False))


if __name__ == "__main__":
    main()
