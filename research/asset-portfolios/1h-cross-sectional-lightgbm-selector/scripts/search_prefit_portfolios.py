from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PREDICTION_ROOT = ARTIFACT_DIR / "prefit_walk_forward"
OUTPUT_ROOT = ARTIFACT_DIR / "prefit_portfolio_search"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "prefit_model_matrix_manifest.json"
PREFIT_END = pd.Timestamp("2026-03-31T00:00:00Z")
ROUND_TRIP_COST = 2.0 * (0.001 + 4.0 / 10_000.0)
STRESS_EXTRA_COST = 0.5 * ROUND_TRIP_COST
MODEL_TYPES = ("regression", "classification", "ranker", "ridge")
ENSEMBLES = ("regression_ensemble",)
BASELINES = (
    "rule_momentum_24",
    "rule_momentum_composite",
    "rule_reversal_24",
    "rule_carry_momentum",
)
HORIZONS = (4, 12, 24)
TOP_NS = (1, 3, 5)
CONFIDENCE_THRESHOLDS = (0.0, 1.5, 2.0, 2.5, 3.0)
EXPOSURES = (0.10, 0.15, 0.20, 0.25, 0.33, 0.50, 0.75, 1.00)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search pre-OOS portfolio policies over frozen OOF predictions."
    )
    parser.add_argument(
        "--score-sources", nargs="+", default=[*MODEL_TYPES, *BASELINES]
    )
    parser.add_argument(
        "--horizons", nargs="+", type=int, choices=HORIZONS, default=list(HORIZONS)
    )
    parser.add_argument("--feature-set", default="compact")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ensemble-seeds", nargs="+", type=int, default=[7, 17, 29, 42])
    parser.add_argument("--train-window-days", type=int)
    return parser.parse_args()


def validate_prefit_boundary() -> None:
    manifest = json.loads(MATRIX_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not manifest.get("physical_oos_isolation"):
        raise RuntimeError("prefit matrix is not physically isolated from OOS")
    if manifest.get("prefit_end_exclusive") != PREFIT_END.isoformat():
        raise RuntimeError("unexpected prefit boundary")


def prediction_paths(
    model_type: str,
    feature_set: str,
    horizon: int,
    seed: int,
    train_window_days: int | None = None,
) -> list[Path]:
    pattern = f"{model_type}_{feature_set}_{horizon}h_wf_*_s{seed}"
    candidates = sorted(PREDICTION_ROOT.glob(f"{pattern}/predictions.parquet"))
    window_marker = (
        f"_tw{train_window_days}d_" if train_window_days is not None else None
    )
    paths = [
        path
        for path in candidates
        if (
            window_marker in path.parent.name
            if window_marker is not None
            else "_tw" not in path.parent.name
        )
    ]
    if len(paths) != 5:
        raise RuntimeError(
            f"expected five walk-forward predictions for {pattern}, got {len(paths)}"
        )
    return paths


def load_predictions(
    model_type: str,
    feature_set: str,
    horizon: int,
    seed: int,
    train_window_days: int | None = None,
) -> pd.DataFrame:
    columns = [
        "ts",
        "symbol",
        "liquidity_rank",
        "avg_daily_quote_volume_7d",
        "cs_rank_ret_24",
        "cs_rank_ret_168",
        "cs_rank_ema_spread_24_96",
        "cs_rank_funding_rate",
        f"label_funding_sum_{horizon}h",
        f"label_long_net_{horizon}h",
        f"label_short_net_{horizon}h",
        f"label_gross_return_{horizon}h",
        "score",
        "fold_id",
    ]
    frames = [
        pd.read_parquet(path, columns=columns)
        for path in prediction_paths(
            model_type, feature_set, horizon, seed, train_window_days
        )
    ]
    result = pd.concat(frames, ignore_index=True)
    result["ts"] = pd.to_datetime(result["ts"], utc=True)
    if result["ts"].max() >= PREFIT_END:
        raise RuntimeError("prediction data crossed the sealed OOS boundary")
    if result.duplicated(["ts", "symbol"]).any():
        raise RuntimeError("duplicate prediction keys")
    return result.sort_values(["ts", "symbol"]).reset_index(drop=True)


def load_regression_ensemble(
    feature_set: str,
    horizon: int,
    seeds: list[int],
    train_window_days: int | None = None,
) -> pd.DataFrame:
    if len(set(seeds)) < 2:
        raise RuntimeError("regression ensemble requires at least two unique seeds")
    frames = [
        load_predictions(
            "regression", feature_set, horizon, seed, train_window_days
        )
        for seed in seeds
    ]
    key_columns = ["ts", "symbol"]
    result = frames[0].copy()
    score_columns = []
    for seed, frame in zip(seeds, frames, strict=True):
        column = f"score_s{seed}"
        score_columns.append(column)
        if seed == seeds[0]:
            result[column] = result.pop("score")
            continue
        result = result.merge(
            frame[key_columns + ["score"]].rename(columns={"score": column}),
            on=key_columns,
            how="inner",
            validate="one_to_one",
        )
    result["score"] = result[score_columns].mean(axis=1)
    return result.drop(columns=score_columns)


def apply_score_source(frame: pd.DataFrame, score_source: str) -> pd.DataFrame:
    result = frame.copy()
    if score_source in MODEL_TYPES or score_source in ENSEMBLES:
        return result
    if score_source == "rule_momentum_24":
        result["score"] = result["cs_rank_ret_24"]
    elif score_source == "rule_momentum_composite":
        result["score"] = (
            0.50 * result["cs_rank_ret_24"]
            + 0.30 * result["cs_rank_ret_168"]
            + 0.20 * result["cs_rank_ema_spread_24_96"]
        )
    elif score_source == "rule_reversal_24":
        result["score"] = 1.0 - result["cs_rank_ret_24"]
    elif score_source == "rule_carry_momentum":
        result["score"] = (
            0.55 * result["cs_rank_ret_24"]
            + 0.30 * result["cs_rank_ret_168"]
            + 0.15 * result["cs_rank_ema_spread_24_96"]
            - 0.20 * result["cs_rank_funding_rate"]
        )
    else:
        raise ValueError(f"unknown score source: {score_source}")
    return result


def add_cross_sectional_score_state(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.loc[np.isfinite(frame["score"])].copy()
    grouped = result.groupby("ts", sort=False)["score"]
    median = grouped.transform("median")
    std = grouped.transform("std").replace(0.0, np.nan)
    result["score_z"] = ((result["score"] - median) / std).fillna(0.0)
    return result.sort_values(["ts", "score", "symbol"]).reset_index(drop=True)


def selection_frames(
    frame: pd.DataFrame, horizon: int, top_n: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    long_label = f"label_long_net_{horizon}h"
    short_label = f"label_short_net_{horizon}h"
    grouped = frame.groupby("ts", sort=False, group_keys=False)
    bottom = grouped.head(top_n).copy()
    top = grouped.tail(top_n).copy()
    top["trade_return"] = top[long_label].fillna(-1.0)
    bottom["trade_return"] = bottom[short_label].fillna(-1.0)
    top["stress_trade_return"] = top["trade_return"] - STRESS_EXTRA_COST
    bottom["stress_trade_return"] = bottom["trade_return"] - STRESS_EXTRA_COST
    return top, bottom


def aggregate_side(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    result = frame.groupby("ts", sort=False).agg(
        fold_id=("fold_id", "first"),
        **{
            f"{prefix}_return": ("trade_return", "mean"),
            f"{prefix}_stress_return": ("stress_trade_return", "mean"),
            f"{prefix}_score_z_max": ("score_z", "max"),
            f"{prefix}_score_z_min": ("score_z", "min"),
        },
    )
    return result.reset_index()


def build_policy(
    frame: pd.DataFrame,
    *,
    horizon: int,
    account_mode: str,
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    top, bottom = selection_frames(frame, horizon, top_n)
    top_agg = aggregate_side(top, "long")
    if account_mode == "long_only":
        decisions = top_agg.rename(
            columns={
                "long_return": "portfolio_return",
                "long_stress_return": "portfolio_stress_return",
                "long_score_z_max": "confidence",
            }
        )[[
            "ts", "fold_id", "portfolio_return", "portfolio_stress_return",
            "confidence",
        ]]
        legs = top[[
            "ts", "symbol", "trade_return", "stress_trade_return"
        ]].copy()
        legs["capital_weight"] = 1.0 / top_n
        return decisions, legs

    bottom_agg = aggregate_side(bottom, "short")
    merged = top_agg.merge(
        bottom_agg.drop(columns="fold_id"), on="ts", validate="one_to_one"
    )
    if account_mode == "long_short":
        decisions = pd.DataFrame({
            "ts": merged["ts"],
            "fold_id": merged["fold_id"],
            "portfolio_return": 0.5 * (
                merged["long_return"] + merged["short_return"]
            ),
            "portfolio_stress_return": 0.5 * (
                merged["long_stress_return"] + merged["short_stress_return"]
            ),
            "confidence": np.minimum(
                merged["long_score_z_max"], -merged["short_score_z_min"]
            ),
        })
        long_legs = top[[
            "ts", "symbol", "trade_return", "stress_trade_return"
        ]].copy()
        short_legs = bottom[[
            "ts", "symbol", "trade_return", "stress_trade_return"
        ]].copy()
        legs = pd.concat([long_legs, short_legs], ignore_index=True)
        legs["capital_weight"] = 0.5 / top_n
        return decisions, legs

    if account_mode != "global_single" or top_n != 1:
        raise ValueError(f"invalid policy: {account_mode} top_n={top_n}")
    choose_long = merged["long_score_z_max"] >= -merged["short_score_z_min"]
    decisions = pd.DataFrame({
        "ts": merged["ts"],
        "fold_id": merged["fold_id"],
        "portfolio_return": np.where(
            choose_long, merged["long_return"], merged["short_return"]
        ),
        "portfolio_stress_return": np.where(
            choose_long,
            merged["long_stress_return"],
            merged["short_stress_return"],
        ),
        "confidence": np.maximum(
            merged["long_score_z_max"], -merged["short_score_z_min"]
        ),
        "choose_long": choose_long.to_numpy(),
    })
    top_single = top.set_index("ts")
    bottom_single = bottom.set_index("ts")
    selected_rows = []
    for ts, is_long in zip(decisions["ts"], choose_long, strict=True):
        source = top_single if is_long else bottom_single
        row = source.loc[ts]
        selected_rows.append({
            "ts": ts,
            "symbol": row["symbol"],
            "trade_return": row["trade_return"],
            "stress_trade_return": row["stress_trade_return"],
            "capital_weight": 1.0,
        })
    return decisions, pd.DataFrame(selected_rows)


def compound_return(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    return float(np.prod(1.0 + values.to_numpy(dtype="float64")) - 1.0)


def return_metrics(returns: pd.Series, horizon: int) -> dict[str, float]:
    values = returns.to_numpy(dtype="float64")
    equity = np.cumprod(1.0 + values)
    total = float(equity[-1] - 1.0) if len(equity) else 0.0
    years = max(len(values) * horizon / (24.0 * 365.0), 1.0 / 365.0)
    annualized = -1.0 if equity[-1] <= 0.0 else float(equity[-1] ** (1.0 / years) - 1.0)
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))
    curve = np.concatenate([[1.0], equity])
    max_drawdown = float(np.min(curve / peak - 1.0))
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    sharpe = (
        float(np.mean(values) / std * np.sqrt(24.0 * 365.0 / horizon))
        if std > 0.0
        else 0.0
    )
    return {
        "total_return": total,
        "annualized_return": annualized,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
    }


def evaluate_policy(
    decisions: pd.DataFrame,
    legs: pd.DataFrame,
    *,
    horizon: int,
    threshold: float,
    exposure: float,
    offset_utc_hours: int = 0,
) -> dict[str, Any]:
    scheduled = decisions.loc[
        (decisions["ts"].dt.hour - offset_utc_hours) % horizon == 0
    ].copy()
    scheduled["active"] = scheduled["confidence"] >= threshold
    scheduled["return"] = np.where(
        scheduled["active"], scheduled["portfolio_return"] * exposure, 0.0
    )
    scheduled["stress_return"] = np.where(
        scheduled["active"], scheduled["portfolio_stress_return"] * exposure, 0.0
    )
    active_ts = scheduled.loc[scheduled["active"], "ts"]
    active_legs = legs.loc[legs["ts"].isin(active_ts)].copy()
    trade_values = active_legs["trade_return"].to_numpy(dtype="float64")
    positive = float(trade_values[trade_values > 0.0].sum())
    negative = float(-trade_values[trade_values < 0.0].sum())
    leg_profit_factor = positive / negative if negative > 0.0 else float("inf")
    active_portfolio_values = scheduled.loc[
        scheduled["active"], "return"
    ].to_numpy(dtype="float64")
    portfolio_positive = float(
        active_portfolio_values[active_portfolio_values > 0.0].sum()
    )
    portfolio_negative = float(
        -active_portfolio_values[active_portfolio_values < 0.0].sum()
    )
    profit_factor = (
        portfolio_positive / portfolio_negative
        if portfolio_negative > 0.0
        else float("inf")
    )
    base = return_metrics(scheduled["return"], horizon)
    stress = return_metrics(scheduled["stress_return"], horizon)
    monthly = scheduled.set_index("ts")["return"].groupby(pd.Grouper(freq="MS")).apply(
        compound_return
    )
    fold_returns = scheduled.groupby("fold_id", sort=False)["return"].apply(
        compound_return
    )
    active_legs["weighted_positive"] = (
        active_legs["trade_return"].clip(lower=0.0) * active_legs["capital_weight"]
    )
    symbol_positive = active_legs.groupby("symbol")["weighted_positive"].sum()
    symbol_concentration = (
        float(symbol_positive.max() / symbol_positive.sum())
        if symbol_positive.sum() > 0.0
        else 1.0
    )
    positive_periods = scheduled["return"].clip(lower=0.0)
    positive_by_month = positive_periods.groupby(
        scheduled["ts"].dt.strftime("%Y-%m")
    ).sum()
    month_concentration = (
        float(positive_by_month.max() / positive_by_month.sum())
        if positive_by_month.sum() > 0.0
        else 1.0
    )
    leg_trade_count = len(active_legs)
    decision_count = int(scheduled["active"].sum())
    result = {
        **base,
        "stress_total_return": stress["total_return"],
        "stress_annualized_return": stress["annualized_return"],
        "stress_max_drawdown": stress["max_drawdown"],
        "decision_count": decision_count,
        "trade_count": leg_trade_count,
        "leg_trade_count": leg_trade_count,
        "win_rate": float(
            scheduled.loc[scheduled["active"], "return"].gt(0.0).mean()
        ) if scheduled["active"].any() else 0.0,
        "leg_win_rate": (
            float((trade_values > 0.0).mean()) if leg_trade_count else 0.0
        ),
        "profit_factor": profit_factor,
        "leg_profit_factor": leg_profit_factor,
        "positive_month_share": float(monthly.gt(0.0).mean()),
        "positive_fold_count": int(fold_returns.gt(0.0).sum()),
        "worst_fold_return": float(fold_returns.min()),
        "symbol_positive_profit_concentration": symbol_concentration,
        "month_positive_profit_concentration": month_concentration,
        "missing_exit_trade_count": int((trade_values <= -1.0).sum()),
    }
    result["hard_gate_pass"] = bool(
        result["annualized_return"] >= 1.00
        and result["max_drawdown"] >= -0.20
        and result["win_rate"] >= 0.55
        and result["sharpe"] >= 1.50
        and result["profit_factor"] >= 1.30
        and result["trade_count"] >= 100
        and result["positive_month_share"] >= 0.60
        and result["stress_total_return"] > 0.0
        and result["stress_max_drawdown"] >= -0.25
        and result["symbol_positive_profit_concentration"] <= 0.25
        and result["month_positive_profit_concentration"] <= 0.35
        and result["positive_fold_count"] >= 4
    )
    result["selection_score"] = float(
        result["annualized_return"]
        + 0.20 * result["sharpe"]
        + 0.50 * result["win_rate"]
        + 0.05 * result["positive_fold_count"]
        - 3.0 * max(0.0, -result["max_drawdown"] - 0.20)
        - 2.0 * max(0.0, 1.30 - min(result["profit_factor"], 1.30))
    )
    return result


def main() -> None:
    args = parse_args()
    validate_prefit_boundary()
    unknown = sorted(
        set(args.score_sources) - set(MODEL_TYPES) - set(ENSEMBLES) - set(BASELINES)
    )
    if unknown:
        raise RuntimeError(f"unknown score sources: {unknown}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for horizon in args.horizons:
        model_cache: dict[str, pd.DataFrame] = {}
        for score_source in args.score_sources:
            if score_source in ENSEMBLES:
                backing_model = score_source
            else:
                backing_model = (
                    score_source if score_source in MODEL_TYPES else "regression"
                )
            if backing_model not in model_cache:
                if backing_model == "regression_ensemble":
                    model_cache[backing_model] = load_regression_ensemble(
                        args.feature_set,
                        horizon,
                        args.ensemble_seeds,
                        args.train_window_days,
                    )
                else:
                    model_cache[backing_model] = load_predictions(
                        backing_model,
                        args.feature_set,
                        horizon,
                        args.seed,
                        args.train_window_days,
                    )
            scored = add_cross_sectional_score_state(
                apply_score_source(model_cache[backing_model], score_source)
            )
            print(
                f"search score={score_source} horizon={horizon} rows={len(scored)}",
                flush=True,
            )
            policies = [("global_single", 1)] + [
                (mode, top_n)
                for mode in ("long_only", "long_short")
                for top_n in TOP_NS
            ]
            for account_mode, top_n in policies:
                decisions, legs = build_policy(
                    scored,
                    horizon=horizon,
                    account_mode=account_mode,
                    top_n=top_n,
                )
                for threshold in CONFIDENCE_THRESHOLDS:
                    for exposure in EXPOSURES:
                        metrics = evaluate_policy(
                            decisions,
                            legs,
                            horizon=horizon,
                            threshold=threshold,
                            exposure=exposure,
                            offset_utc_hours=0,
                        )
                        rows.append({
                            "score_source": score_source,
                            "feature_set": args.feature_set,
                            "seed": args.seed,
                            "horizon": horizon,
                            "account_mode": account_mode,
                            "top_n": top_n,
                            "confidence_threshold": threshold,
                            "exposure": exposure,
                            "rebalance_offset_utc_hours": 0,
                            **metrics,
                        })
    results = pd.DataFrame(rows).sort_values(
        ["hard_gate_pass", "selection_score"], ascending=[False, False]
    )
    suffix_parts: list[str] = []
    if args.feature_set != "compact":
        suffix_parts.append(args.feature_set)
    if args.train_window_days is not None:
        suffix_parts.append(f"tw{args.train_window_days}d")
    if any(source in ENSEMBLES for source in args.score_sources):
        seed_text = "-".join(str(seed) for seed in args.ensemble_seeds)
        suffix_parts.append(f"ensemble_s{seed_text}")
    elif args.seed != 42:
        suffix_parts.append(f"s{args.seed}")
    suffix = "_" + "_".join(suffix_parts) if suffix_parts else ""
    results_path = OUTPUT_ROOT / f"prefit_portfolio_search{suffix}.csv"
    results.to_csv(results_path, index=False)
    frontier = results.head(100).copy()
    frontier_path = OUTPUT_ROOT / f"prefit_frontier{suffix}.csv"
    frontier.to_csv(frontier_path, index=False)
    summary = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "oos_revealed": False,
        "physical_oos_isolation": True,
        "prefit_end_exclusive": PREFIT_END.isoformat(),
        "score_sources": args.score_sources,
        "horizons": args.horizons,
        "feature_set": args.feature_set,
        "seed": args.seed,
        "ensemble_seeds": args.ensemble_seeds,
        "train_window_days": args.train_window_days,
        "configuration_count": len(results),
        "hard_gate_pass_count": int(results["hard_gate_pass"].sum()),
        "best": results.iloc[0].to_dict(),
        "results_csv": str(results_path),
        "frontier_csv": str(frontier_path),
        "missing_exit_policy": "selected missing scheduled exits are forced to -100%",
        "cost_policy": {
            "baseline_round_trip": ROUND_TRIP_COST,
            "stress_multiplier": 1.5,
            "stress_extra_round_trip": STRESS_EXTRA_COST,
        },
    }
    summary_path = OUTPUT_ROOT / f"prefit_portfolio_search_summary{suffix}.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({
        "configuration_count": summary["configuration_count"],
        "hard_gate_pass_count": summary["hard_gate_pass_count"],
        "best": summary["best"],
    }, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
