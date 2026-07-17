from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from search_prefit_portfolios import (
    add_cross_sectional_score_state,
    build_policy,
    evaluate_policy,
    load_predictions,
    load_regression_ensemble,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MATRIX_ROOT = ARTIFACT_DIR / "prefit_model_matrix"
OUTPUT_ROOT = ARTIFACT_DIR / "prefit_candidate_robustness"
HORIZON = 24
DEFAULT_FEATURE_SET = "compact"
SEEDS = (7, 17, 29, 42)
TOP_NS = (3, 5, 7, 10)
EXPOSURES = (0.25, 0.33, 0.40, 0.45)
THRESHOLD = 0.0
CANDIDATE_TOP_N = 7
CANDIDATE_EXPOSURE = 0.45


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the pre-OOS regression-ensemble candidate."
    )
    parser.add_argument(
        "--feature-set", choices=("compact", "full_coverage"), default=DEFAULT_FEATURE_SET
    )
    parser.add_argument("--train-window-days", type=int)
    return parser.parse_args()


def scored_ensemble(
    feature_set: str, train_window_days: int | None = None
) -> pd.DataFrame:
    return add_cross_sectional_score_state(
        load_regression_ensemble(
            feature_set, HORIZON, list(SEEDS), train_window_days
        )
    )


def audit_offsets(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for top_n in TOP_NS:
        decisions, legs = build_policy(
            scored, horizon=HORIZON, account_mode="long_short", top_n=top_n
        )
        for exposure in EXPOSURES:
            for offset in range(HORIZON):
                rows.append({
                    "top_n": top_n,
                    "exposure": exposure,
                    "offset_utc_hours": offset,
                    **evaluate_policy(
                        decisions,
                        legs,
                        horizon=HORIZON,
                        threshold=THRESHOLD,
                        exposure=exposure,
                        offset_utc_hours=offset,
                    ),
                })
    return pd.DataFrame(rows)


def summarize_offsets(rows: pd.DataFrame) -> pd.DataFrame:
    summaries = []
    for (top_n, exposure), group in rows.groupby(["top_n", "exposure"]):
        summaries.append({
            "top_n": int(top_n),
            "exposure": float(exposure),
            "hard_gate_pass_offsets": int(group["hard_gate_pass"].sum()),
            "offset_count": len(group),
            "worst_annualized_return": float(group["annualized_return"].min()),
            "worst_max_drawdown": float(group["max_drawdown"].min()),
            "worst_stress_max_drawdown": float(
                group["stress_max_drawdown"].min()
            ),
            "minimum_win_rate": float(group["win_rate"].min()),
            "minimum_sharpe": float(group["sharpe"].min()),
            "minimum_profit_factor": float(group["profit_factor"].min()),
            "minimum_positive_month_share": float(
                group["positive_month_share"].min()
            ),
            "minimum_positive_fold_count": int(
                group["positive_fold_count"].min()
            ),
        })
    return pd.DataFrame(summaries).sort_values(
        ["hard_gate_pass_offsets", "worst_annualized_return"],
        ascending=[False, False],
    )


def audit_seeds(
    feature_set: str, train_window_days: int | None = None
) -> pd.DataFrame:
    rows = []
    for seed in SEEDS:
        scored = add_cross_sectional_score_state(
            load_predictions(
                "regression", feature_set, HORIZON, seed, train_window_days
            )
        )
        decisions, legs = build_policy(
            scored,
            horizon=HORIZON,
            account_mode="long_short",
            top_n=CANDIDATE_TOP_N,
        )
        rows.append({
            "seed": seed,
            **evaluate_policy(
                decisions,
                legs,
                horizon=HORIZON,
                threshold=THRESHOLD,
                exposure=CANDIDATE_EXPOSURE,
                offset_utc_hours=0,
            ),
        })
    return pd.DataFrame(rows)


def audit_liquidity(scored: pd.DataFrame) -> pd.DataFrame:
    variants = {
        "main_top100_10m": scored,
        "top50": scored.loc[scored["liquidity_rank"] <= 50].copy(),
        "avg_daily_quote_volume_20m": scored.loc[
            scored["avg_daily_quote_volume_7d"] >= 20_000_000.0
        ].copy(),
    }
    rows = []
    for name, frame in variants.items():
        normalized = add_cross_sectional_score_state(frame.drop(columns="score_z"))
        decisions, legs = build_policy(
            normalized,
            horizon=HORIZON,
            account_mode="long_short",
            top_n=CANDIDATE_TOP_N,
        )
        for offset in range(HORIZON):
            rows.append({
                "liquidity_variant": name,
                "offset_utc_hours": offset,
                "symbols": int(frame["symbol"].nunique()),
                **evaluate_policy(
                    decisions,
                    legs,
                    horizon=HORIZON,
                    threshold=THRESHOLD,
                    exposure=CANDIDATE_EXPOSURE,
                    offset_utc_hours=offset,
                ),
            })
    return pd.DataFrame(rows)


def load_market_context() -> pd.DataFrame:
    matrix_glob = MATRIX_ROOT / "**/*.parquet"
    connection = duckdb.connect()
    return connection.execute(
        f"""
        SELECT
            epoch_ms(ts)::BIGINT AS ts_ms,
            avg(market_breadth_ret24_positive) AS market_breadth_ret24_positive,
            avg(market_breadth_trend_positive) AS market_breadth_trend_positive,
            avg(market_median_realized_vol_24) AS market_median_realized_vol_24
        FROM read_parquet(
            '{sql_path(matrix_glob)}',
            hive_partitioning = false,
            union_by_name = true
        )
        WHERE ts >= TIMESTAMPTZ '2024-01-01T00:00:00Z'
          AND ts < TIMESTAMPTZ '2026-03-31T00:00:00Z'
        GROUP BY ts
        ORDER BY ts
        """
    ).fetch_df().assign(
        ts=lambda frame: pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True)
    )


def compound(values: pd.Series) -> float:
    return float(np.prod(1.0 + values.to_numpy(dtype="float64")) - 1.0)


def regime_rows(scored: pd.DataFrame) -> pd.DataFrame:
    decisions, _ = build_policy(
        scored,
        horizon=HORIZON,
        account_mode="long_short",
        top_n=CANDIDATE_TOP_N,
    )
    scheduled = decisions.loc[decisions["ts"].dt.hour == 0].copy()
    scheduled["return"] = scheduled["portfolio_return"] * CANDIDATE_EXPOSURE
    scheduled = scheduled.merge(load_market_context(), on="ts", validate="one_to_one")
    volatility = scheduled["market_median_realized_vol_24"]
    low, high = volatility.quantile([0.33, 0.67])
    scheduled["volatility_regime"] = np.select(
        [volatility <= low, volatility >= high],
        ["low", "high"],
        default="middle",
    )
    breadth = scheduled["market_breadth_ret24_positive"]
    scheduled["breadth_regime"] = np.select(
        [breadth <= 0.40, breadth >= 0.60],
        ["risk_off", "risk_on"],
        default="neutral",
    )
    rows = []
    for dimension in ("volatility_regime", "breadth_regime"):
        for regime, group in scheduled.groupby(dimension):
            returns = group["return"]
            positive = float(returns[returns > 0.0].sum())
            negative = float(-returns[returns < 0.0].sum())
            rows.append({
                "dimension": dimension,
                "regime": regime,
                "decisions": len(group),
                "total_return": compound(returns),
                "win_rate": float(returns.gt(0.0).mean()),
                "profit_factor": positive / negative if negative else float("inf"),
                "mean_return": float(returns.mean()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    output_name = args.feature_set
    if args.train_window_days is not None:
        output_name += f"_tw{args.train_window_days}d"
    output_root = OUTPUT_ROOT / output_name
    output_root.mkdir(parents=True, exist_ok=True)
    ensemble = scored_ensemble(args.feature_set, args.train_window_days)
    offsets = audit_offsets(ensemble)
    offset_summary = summarize_offsets(offsets)
    seeds = audit_seeds(args.feature_set, args.train_window_days)
    liquidity = audit_liquidity(ensemble)
    regimes = regime_rows(ensemble)
    offsets.to_csv(output_root / "timing_offsets.csv", index=False)
    offset_summary.to_csv(output_root / "timing_offset_summary.csv", index=False)
    seeds.to_csv(output_root / "seed_robustness.csv", index=False)
    liquidity.to_csv(output_root / "liquidity_robustness.csv", index=False)
    regimes.to_csv(output_root / "regime_robustness.csv", index=False)
    liquidity_summary = liquidity.groupby("liquidity_variant").agg(
        hard_gate_pass_offsets=("hard_gate_pass", "sum"),
        worst_annualized_return=("annualized_return", "min"),
        worst_max_drawdown=("max_drawdown", "min"),
        worst_stress_max_drawdown=("stress_max_drawdown", "min"),
        minimum_win_rate=("win_rate", "min"),
        minimum_positive_fold_count=("positive_fold_count", "min"),
    ).reset_index()
    liquidity_summary.to_csv(
        output_root / "liquidity_robustness_summary.csv", index=False
    )
    report = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "oos_revealed": False,
        "candidate_under_audit": {
            "model": "four-seed mean LightGBM regression ensemble",
            "seeds": list(SEEDS),
            "feature_set": args.feature_set,
            "train_window_days": args.train_window_days,
            "horizon_hours": HORIZON,
            "account_mode": "long_short",
            "top_n": CANDIDATE_TOP_N,
            "confidence_threshold": THRESHOLD,
            "exposure": CANDIDATE_EXPOSURE,
        },
        "timing_offset_summary": offset_summary.to_dict(orient="records"),
        "seed_hard_gate_pass_count": int(seeds["hard_gate_pass"].sum()),
        "seed_count": len(seeds),
        "liquidity_summary": liquidity_summary.to_dict(orient="records"),
        "regimes": regimes.to_dict(orient="records"),
    }
    report_path = output_root / "prefit_candidate_robustness.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
