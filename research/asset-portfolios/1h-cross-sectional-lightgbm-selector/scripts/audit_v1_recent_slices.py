from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from search_prefit_portfolios import (
    add_cross_sectional_score_state,
    build_policy,
    load_regression_ensemble,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
OOS_ROOT = ARTIFACT_DIR / "v1_oos_2026q2"
OOS_PREDICTION_PATH = OOS_ROOT / "oos_predictions.parquet"
OUTPUT_PATH = OOS_ROOT / "v1_recent_slice_audit.json"
CSV_PATH = OOS_ROOT / "v1_recent_slice_audit.csv"
HORIZON = 24
TOP_N = 7
EXPOSURE = 0.45
SEEDS = [7, 17, 29, 42]
LAST_COMPLETED_DECISION = pd.Timestamp("2026-06-29T00:00:00Z")


def compound(values: pd.Series) -> float:
    return float(np.prod(1.0 + values.to_numpy(dtype="float64")) - 1.0)


def metrics(frame: pd.DataFrame) -> dict[str, Any]:
    returns = frame["portfolio_return"].astype("float64")
    equity = np.cumprod(1.0 + returns.to_numpy())
    total = float(equity[-1] - 1.0) if len(equity) else 0.0
    curve = np.concatenate([[1.0], equity])
    peak = np.maximum.accumulate(curve)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    positive = float(returns.clip(lower=0.0).sum())
    negative = float(-returns.clip(upper=0.0).sum())
    return {
        "decision_count": len(frame),
        "completed_trade_legs": len(frame) * 2 * TOP_N,
        "total_return": total,
        "max_drawdown": float(np.min(curve / peak - 1.0)),
        "portfolio_win_rate": float(returns.gt(0.0).mean()),
        "portfolio_profit_factor": (
            positive / negative if negative > 0.0 else float("inf")
        ),
        "sharpe": (
            float(returns.mean() / std * np.sqrt(365.0)) if std > 0.0 else 0.0
        ),
    }


def main() -> None:
    prefit = add_cross_sectional_score_state(
        load_regression_ensemble("full_coverage", HORIZON, SEEDS, 730)
    )
    oos = pd.read_parquet(OOS_PREDICTION_PATH)
    oos["ts"] = pd.to_datetime(oos["ts"], utc=True)
    oos = oos.loc[oos["ts"].le(LAST_COMPLETED_DECISION)].copy()
    needed = [
        "ts",
        "symbol",
        "liquidity_rank",
        "avg_daily_quote_volume_7d",
        "label_long_net_24h",
        "label_short_net_24h",
        "label_gross_return_24h",
        "label_funding_sum_24h",
        "score",
        "fold_id",
    ]
    scored = pd.concat([prefit[needed], oos[needed]], ignore_index=True)
    scored = add_cross_sectional_score_state(scored.drop(columns="score_z", errors="ignore"))
    decisions, _ = build_policy(
        scored,
        horizon=HORIZON,
        account_mode="long_short",
        top_n=TOP_N,
    )
    decisions = decisions.loc[decisions["ts"].dt.hour == 0].copy()
    decisions["portfolio_return"] *= EXPOSURE
    end = decisions["ts"].max()
    windows = {
        "1d": end - pd.Timedelta(days=1),
        "7d": end - pd.Timedelta(days=7),
        "1m": end - pd.DateOffset(months=1),
        "3m": end - pd.DateOffset(months=3),
        "6m": end - pd.DateOffset(months=6),
        "1y": end - pd.DateOffset(years=1),
    }
    rows = []
    for name, start_exclusive in windows.items():
        sliced = decisions.loc[
            decisions["ts"].gt(start_exclusive) & decisions["ts"].le(end)
        ].copy()
        rows.append({
            "slice": name,
            "start_exclusive": start_exclusive.isoformat(),
            "end_inclusive": end.isoformat(),
            **metrics(sliced),
        })
    result = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "version": "BIN-1H-CSLGBM-V1",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "dataset_end": end.isoformat(),
        "selection_use": (
            "Audit only. The 2026Q2 OOS was revealed after V1 was frozen and none "
            "of these slices may be used to alter V1."
        ),
        "metric_semantics": {
            "win_rate": "portfolio holding-period win rate",
            "trade_count": "completed individual long/short legs",
            "slice_boundary": "start exclusive, dataset end inclusive",
        },
        "slices": rows,
    }
    pd.DataFrame(rows).to_csv(CSV_PATH, index=False)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
