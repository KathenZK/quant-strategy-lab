from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_time_to_tp_2026-07-15.json"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"
HORIZONS_HOURS = (1, 2, 4, 6, 8, 12, 24)
MFE_THRESHOLDS = (1.0, 1.5, 2.0)


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def pct(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return round(float(numerator / denominator * 100.0), 2)


def describe_hours(values: pd.Series) -> dict[str, float]:
    quantiles = values.quantile([0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return {
        "min": round(float(values.min()), 2),
        "p10": round(float(quantiles.loc[0.10]), 2),
        "p25": round(float(quantiles.loc[0.25]), 2),
        "median": round(float(quantiles.loc[0.50]), 2),
        "p75": round(float(quantiles.loc[0.75]), 2),
        "p90": round(float(quantiles.loc[0.90]), 2),
        "p95": round(float(quantiles.loc[0.95]), 2),
        "max": round(float(values.max()), 2),
        "mean": round(float(values.mean()), 2),
    }


def tp_timing(trades: pd.DataFrame) -> dict[str, Any]:
    tp = trades.loc[trades["exit_reason"] == "take_profit"].copy()
    tp["hold_hours"] = tp["hold_bars"] * 0.25
    edges = (-np.inf, 1, 2, 4, 6, 8, 12, 24, 48, np.inf)
    labels = (
        "<=1h",
        "1-2h",
        "2-4h",
        "4-6h",
        "6-8h",
        "8-12h",
        "12-24h",
        "24-48h",
        ">48h",
    )
    bins = pd.cut(tp["hold_hours"], bins=edges, labels=labels, right=True)
    bin_counts = bins.value_counts(sort=False)
    cumulative = {
        f"within_{hours}h": {
            "count": int((tp["hold_hours"] <= hours).sum()),
            "share_pct": pct(int((tp["hold_hours"] <= hours).sum()), len(tp)),
        }
        for hours in HORIZONS_HOURS
    }

    by_direction: dict[str, Any] = {}
    for direction, label in ((1, "long"), (-1, "short")):
        subset = tp.loc[tp["direction"] == direction, "hold_hours"]
        by_direction[label] = {
            "count": int(len(subset)),
            "hours": describe_hours(subset),
        }

    return {
        "count": int(len(tp)),
        "hours": describe_hours(tp["hold_hours"]),
        "bins": [
            {
                "window": str(label),
                "count": int(bin_counts.loc[label]),
                "share_pct": pct(int(bin_counts.loc[label]), len(tp)),
            }
            for label in labels
        ],
        "cumulative": cumulative,
        "by_direction": by_direction,
    }


def mfe_at_horizon(
    *,
    frame: pd.DataFrame,
    trade: pd.Series,
    horizon_bars: int,
) -> float:
    entry_bar = int(trade["entry_bar"])
    end_bar = entry_bar + horizon_bars - 1
    path = frame.iloc[entry_bar : end_bar + 1]
    if int(trade["direction"]) == 1:
        excursion = float(path["high"].max()) - float(trade["entry_price"])
    else:
        excursion = float(trade["entry_price"]) - float(path["low"].min())
    return excursion / float(trade["entry_atr"])


def outcome_counts(cohort: pd.DataFrame) -> dict[str, Any]:
    reasons = cohort["exit_reason"].value_counts()
    tp_count = int(reasons.get("take_profit", 0))
    stop_count = int(reasons.get("stop_loss", 0))
    indicator_count = int(reasons.get("indicator_exit", 0))
    return {
        "count": int(len(cohort)),
        "eventual_tp": tp_count,
        "eventual_tp_pct": pct(tp_count, len(cohort)),
        "eventual_stop": stop_count,
        "eventual_stop_pct": pct(stop_count, len(cohort)),
        "eventual_indicator_exit": indicator_count,
        "eventual_indicator_exit_pct": pct(indicator_count, len(cohort)),
        "eventual_win_pct": pct(int((cohort["trade_return"] > 0.0).sum()), len(cohort)),
        "mean_trade_return_pct": round(float(cohort["trade_return"].mean() * 100.0), 2),
    }


def survivor_analysis(frame: pd.DataFrame, trades: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon_hours in HORIZONS_HOURS:
        horizon_bars = horizon_hours * 4
        survivors = trades.loc[trades["hold_bars"] >= horizon_bars].copy()
        survivors["mfe_at_horizon_atr"] = survivors.apply(
            lambda trade: mfe_at_horizon(
                frame=frame,
                trade=trade,
                horizon_bars=horizon_bars,
            ),
            axis=1,
        )
        eventual_tp = survivors.loc[survivors["exit_reason"] == "take_profit"].copy()
        remaining_tp = eventual_tp["hold_bars"] * 0.25 - horizon_hours
        row: dict[str, Any] = {
            "horizon_hours": horizon_hours,
            "survivors": outcome_counts(survivors),
            "survivor_mfe_median_atr": round(
                float(survivors["mfe_at_horizon_atr"].median()),
                3,
            ),
            "eventual_tp_remaining_hours": (
                describe_hours(remaining_tp) if not remaining_tp.empty else None
            ),
            "mfe_cohorts": {},
        }
        for threshold in MFE_THRESHOLDS:
            below = survivors.loc[survivors["mfe_at_horizon_atr"] < threshold]
            above = survivors.loc[survivors["mfe_at_horizon_atr"] >= threshold]
            row["mfe_cohorts"][f"below_{threshold:g}atr"] = outcome_counts(below)
            row["mfe_cohorts"][f"at_least_{threshold:g}atr"] = outcome_counts(above)
        rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    config = base.V35Config()
    features = base.build_features(frame, config)
    run = base.run_backtest(
        "v35_base",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "version": "HYPE-EMA-TB-V35",
        "question": "Time to fixed 5ATR take-profit and slow-trade prognosis.",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "config": asdict(config),
        "metrics": run.metrics,
        "definitions": {
            "time_to_tp": "Entry open to the intrabar touch of fixed entry-ATR TP5.",
            "survivor": "Trade remains open at the stated elapsed-time boundary.",
            "early_mfe": (
                "Maximum favorable high/low excursion from entry through the last fully "
                "elapsed 15m bar, divided by fixed entry ATR."
            ),
            "selection": (
                "Descriptive audit only. Horizons and 1.5ATR are motivated by the user's "
                "question and V35's indicator-exit disable threshold; not used to select V35."
            ),
        },
        "tp_timing": tp_timing(run.trades),
        "survivor_analysis": survivor_analysis(frame, run.trades),
    }
    OUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    timing = payload["tp_timing"]
    print(
        f"data={quality['start']}~{quality['end']} rows={quality['rows']} "
        f"gaps={quality['missing_15m_bars']}"
    )
    print(
        f"TP trades={timing['count']} median={timing['hours']['median']:.2f}h "
        f"p75={timing['hours']['p75']:.2f}h p90={timing['hours']['p90']:.2f}h "
        f"max={timing['hours']['max']:.2f}h"
    )
    for row in payload["survivor_analysis"]:
        slow = row["mfe_cohorts"]["below_1.5atr"]
        print(
            f"h={row['horizon_hours']:>2} survivors={row['survivors']['count']:>3} "
            f"eventual_tp={row['survivors']['eventual_tp_pct']:>6.2f}% "
            f"mfe<1.5 n={slow['count']:>3} eventual_tp={slow['eventual_tp_pct']} "
            f"mean_return={slow['mean_trade_return_pct']:>6.2f}%"
        )
    print(f"summary -> {OUT_PATH}")


if __name__ == "__main__":
    main()
