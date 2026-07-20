from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PREDICTION_ROOT = ARTIFACT_DIR / "development_walk_forward"
OUTPUT_ROOT = ARTIFACT_DIR / "development_allocator_search"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "development_model_matrix_manifest.json"
DEVELOPMENT_END = pd.Timestamp("2026-04-01T00:00:00Z")
ROUND_TRIP_COST = 2.0 * (0.001 + 4.0 / 10_000.0)
STRESS_EXTRA_COST = 0.5 * ROUND_TRIP_COST
EXPECTED_FOLDS = 7
HORIZONS = (4, 8, 12, 24, 48)
DECISION_FREQUENCIES = (4, 8, 12, 24)
SIDE_MODES = ("long_only", "short_only", "long_short_dynamic")
SCORE_SOURCES = (
    "lgbm",
    "rule_momentum",
    "rule_reversal",
    "rule_carry_momentum",
)
TAIL_PENALTIES = (
    (0.0, 0.0),
    (0.50, 0.25),
    (1.00, 0.50),
)
UTILITY_THRESHOLDS = (1.0, 1.5, 2.0)
MAX_POSITIONS = (1, 3, 5)
GROSS_EXPOSURES = (0.50, 1.00)
RULE_FEATURES = (
    "cs_rank_ret_24",
    "cs_rank_ret_168",
    "cs_rank_ema_spread_24_96",
    "cs_rank_funding_rate",
    "cs_rank_realized_vol_24",
    "cs_rank_mark_premium",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search abstaining utility/risk allocators on development OOF only."
    )
    parser.add_argument(
        "--score-sources", nargs="+", choices=SCORE_SOURCES, default=list(SCORE_SOURCES)
    )
    parser.add_argument(
        "--horizons", nargs="+", type=int, choices=HORIZONS, default=list(HORIZONS)
    )
    parser.add_argument("--feature-set", default="compact")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--return-model-type", default="regression")
    parser.add_argument("--mae-model-type", default="quantile")
    parser.add_argument("--event-model-type", default="classification")
    return parser.parse_args()


def validate_boundary() -> None:
    manifest = json.loads(MATRIX_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS":
        raise RuntimeError("development model matrix is not PASS")
    if not manifest.get("physical_outcome_isolation"):
        raise RuntimeError("development model matrix is not physically isolated")
    if manifest.get("development_end_exclusive") != DEVELOPMENT_END.isoformat():
        raise RuntimeError("unexpected development boundary")
    if manifest.get("reused_holdout_outcomes_read"):
        raise RuntimeError("reused holdout outcomes were read")
    if manifest.get("prospective_oos_outcomes_read"):
        raise RuntimeError("prospective OOS outcomes were read")


def prediction_paths(
    *,
    task: str,
    model_type: str,
    feature_set: str,
    horizon: int,
    seed: int,
) -> list[Path]:
    pattern = f"{task}_{model_type}_{feature_set}_{horizon}h_wf_*_s{seed}"
    paths = sorted(PREDICTION_ROOT.glob(f"{pattern}/predictions.parquet"))
    if len(paths) != EXPECTED_FOLDS:
        raise RuntimeError(
            f"expected {EXPECTED_FOLDS} OOF files for {pattern}, got {len(paths)}"
        )
    return paths


def load_task_scores(
    *,
    task: str,
    model_type: str,
    feature_set: str,
    horizon: int,
    seed: int,
    include_outcomes: bool,
) -> pd.DataFrame:
    columns = ["ts", "symbol", "score", "fold_id"]
    if include_outcomes:
        columns.extend(RULE_FEATURES)
        columns.extend(
            [
                f"label_path_valid_{horizon}h",
                f"label_long_net_{horizon}h",
                f"label_short_net_{horizon}h",
                f"label_long_mae_{horizon}h",
                f"label_short_mae_{horizon}h",
                f"label_short_squeeze_10pct_{horizon}h",
                f"label_long_crash_10pct_{horizon}h",
            ]
        )
    frames = [
        pd.read_parquet(path, columns=list(dict.fromkeys(columns)))
        for path in prediction_paths(
            task=task,
            model_type=model_type,
            feature_set=feature_set,
            horizon=horizon,
            seed=seed,
        )
    ]
    result = pd.concat(frames, ignore_index=True)
    result["ts"] = pd.to_datetime(result["ts"], utc=True)
    if result["ts"].max() >= DEVELOPMENT_END:
        raise RuntimeError("OOF predictions crossed development boundary")
    if result.duplicated(["ts", "symbol"]).any():
        raise RuntimeError(f"duplicate OOF keys for {task}")
    return result.sort_values(["ts", "symbol"]).reset_index(drop=True)


def load_task_score_ensemble(
    *,
    task: str,
    model_type: str,
    feature_set: str,
    horizon: int,
    seeds: list[int],
    include_outcomes: bool,
) -> pd.DataFrame:
    if len(set(seeds)) < 2:
        raise ValueError("score ensemble requires at least two unique seeds")
    frames = [
        load_task_scores(
            task=task,
            model_type=model_type,
            feature_set=feature_set,
            horizon=horizon,
            seed=seed,
            include_outcomes=include_outcomes and index == 0,
        )
        for index, seed in enumerate(seeds)
    ]
    result = frames[0].rename(columns={"score": f"score_s{seeds[0]}"})
    score_columns = [f"score_s{seeds[0]}"]
    for seed, frame in zip(seeds[1:], frames[1:], strict=True):
        score_column = f"score_s{seed}"
        score_columns.append(score_column)
        result = result.merge(
            frame[["ts", "symbol", "score"]].rename(
                columns={"score": score_column}
            ),
            on=["ts", "symbol"],
            how="inner",
            validate="one_to_one",
        )
    result["score"] = result[score_columns].mean(axis=1)
    return result.drop(columns=score_columns)


def load_prediction_bundle(
    args: argparse.Namespace,
    horizon: int,
    *,
    ensemble_seeds: list[int] | None = None,
) -> pd.DataFrame:
    def load(
        *, task: str, model_type: str, include_outcomes: bool
    ) -> pd.DataFrame:
        if ensemble_seeds is None:
            return load_task_scores(
                task=task,
                model_type=model_type,
                feature_set=args.feature_set,
                horizon=horizon,
                seed=args.seed,
                include_outcomes=include_outcomes,
            )
        return load_task_score_ensemble(
            task=task,
            model_type=model_type,
            feature_set=args.feature_set,
            horizon=horizon,
            seeds=ensemble_seeds,
            include_outcomes=include_outcomes,
        )

    long_return = load(
        task="long_return",
        model_type=args.return_model_type,
        include_outcomes=True,
    ).rename(columns={"score": "long_return_score"})
    merge_columns = ["ts", "symbol"]
    bundles = [
        (
            "short_return_score",
            load(
                task="short_return",
                model_type=args.return_model_type,
                include_outcomes=False,
            ),
        ),
        (
            "long_mae_score",
            load(
                task="long_mae",
                model_type=args.mae_model_type,
                include_outcomes=False,
            ),
        ),
        (
            "short_mae_score",
            load(
                task="short_mae",
                model_type=args.mae_model_type,
                include_outcomes=False,
            ),
        ),
        (
            "long_event_score",
            load(
                task="long_event",
                model_type=args.event_model_type,
                include_outcomes=False,
            ),
        ),
        (
            "short_event_score",
            load(
                task="short_event",
                model_type=args.event_model_type,
                include_outcomes=False,
            ),
        ),
    ]
    result = long_return
    for score_name, frame in bundles:
        result = result.merge(
            frame[merge_columns + ["score"]].rename(columns={"score": score_name}),
            on=merge_columns,
            how="inner",
            validate="one_to_one",
        )
    return result


def within_time_zscore(frame: pd.DataFrame, column: str) -> pd.Series:
    grouped = frame.groupby("ts", sort=False)[column]
    median = grouped.transform("median")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((frame[column] - median) / std).fillna(0.0).clip(-10.0, 10.0)


def rule_scores(frame: pd.DataFrame, source: str) -> tuple[pd.Series, pd.Series]:
    momentum = (
        0.50 * frame["cs_rank_ret_24"]
        + 0.30 * frame["cs_rank_ret_168"]
        + 0.20 * frame["cs_rank_ema_spread_24_96"]
    )
    if source == "rule_momentum":
        long_score = momentum
    elif source == "rule_reversal":
        long_score = 1.0 - momentum
    elif source == "rule_carry_momentum":
        long_score = momentum - 0.20 * frame["cs_rank_funding_rate"]
    else:
        raise ValueError(f"unknown rule score source: {source}")
    return long_score, -long_score


def candidate_sides(
    bundle: pd.DataFrame,
    *,
    score_source: str,
    horizon: int,
) -> pd.DataFrame:
    frame = bundle.copy()
    if score_source == "lgbm":
        long_raw = frame["long_return_score"]
        short_raw = frame["short_return_score"]
    else:
        long_raw, short_raw = rule_scores(frame, score_source)
    frame["_long_raw"] = long_raw
    frame["_short_raw"] = short_raw
    frame["long_return_z"] = within_time_zscore(frame, "_long_raw")
    frame["short_return_z"] = within_time_zscore(frame, "_short_raw")
    for side in ("long", "short"):
        frame[f"{side}_mae_z"] = within_time_zscore(
            frame, f"{side}_mae_score"
        )
        frame[f"{side}_event_z"] = within_time_zscore(
            frame, f"{side}_event_score"
        )
    shared = ["ts", "symbol", "fold_id"]
    long = frame[shared].copy()
    long["side"] = "long"
    long["return_z"] = frame["long_return_z"].to_numpy()
    long["mae_z"] = frame["long_mae_z"].to_numpy()
    long["event_z"] = frame["long_event_z"].to_numpy()
    long["trade_return"] = frame[f"label_long_net_{horizon}h"].to_numpy()
    short = frame[shared].copy()
    short["side"] = "short"
    short["return_z"] = frame["short_return_z"].to_numpy()
    short["mae_z"] = frame["short_mae_z"].to_numpy()
    short["event_z"] = frame["short_event_z"].to_numpy()
    short["trade_return"] = frame[f"label_short_net_{horizon}h"].to_numpy()
    candidates = pd.concat([long, short], ignore_index=True)
    candidates = candidates.loc[candidates["trade_return"].notna()].copy()
    candidates["stress_trade_return"] = (
        candidates["trade_return"] - STRESS_EXTRA_COST
    )
    return candidates


def select_legs(
    candidates: pd.DataFrame,
    *,
    side_mode: str,
    mae_penalty: float,
    event_penalty: float,
    utility_threshold: float,
    max_positions: int,
    mae_z_max: float | None = None,
    event_z_max: float | None = None,
) -> pd.DataFrame:
    frame = candidates
    if side_mode == "long_only":
        frame = frame.loc[frame["side"] == "long"].copy()
    elif side_mode == "short_only":
        frame = frame.loc[frame["side"] == "short"].copy()
    elif side_mode == "long_short_dynamic":
        frame = frame.copy()
    else:
        raise ValueError(f"unknown side mode: {side_mode}")
    frame["utility"] = (
        frame["return_z"]
        - mae_penalty * frame["mae_z"]
        - event_penalty * frame["event_z"]
    )
    if mae_z_max is not None:
        frame = frame.loc[frame["mae_z"] <= mae_z_max]
    if event_z_max is not None:
        frame = frame.loc[frame["event_z"] <= event_z_max]
    frame = frame.loc[frame["utility"] >= utility_threshold]
    if side_mode == "long_short_dynamic":
        frame = (
            frame.sort_values(
                ["ts", "symbol", "utility", "side"],
                ascending=[True, True, False, True],
            )
            .drop_duplicates(["ts", "symbol"], keep="first")
        )
    selected = (
        frame.sort_values(
            ["ts", "utility", "symbol"], ascending=[True, False, True]
        )
        .groupby("ts", sort=False, group_keys=False)
        .head(max_positions)
        .copy()
    )
    return selected


def scheduled_policy(
    candidates: pd.DataFrame,
    selected: pd.DataFrame,
    *,
    decision_frequency: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = (
        candidates[["ts", "fold_id"]]
        .drop_duplicates("ts")
        .sort_values("ts")
    )
    base = base.loc[base["ts"].dt.hour % decision_frequency == 0].copy()
    legs = selected.loc[selected["ts"].isin(base["ts"])].copy()
    aggregated = legs.groupby("ts", sort=False).agg(
        portfolio_return=("trade_return", "mean"),
        portfolio_stress_return=("stress_trade_return", "mean"),
        position_count=("symbol", "size"),
        mean_utility=("utility", "mean"),
    )
    decisions = base.merge(aggregated, on="ts", how="left", validate="one_to_one")
    decisions["active"] = decisions["position_count"].notna()
    decisions["position_count"] = decisions["position_count"].fillna(0).astype(int)
    decisions["portfolio_return"] = decisions["portfolio_return"].fillna(0.0)
    decisions["portfolio_stress_return"] = decisions[
        "portfolio_stress_return"
    ].fillna(0.0)
    return decisions, legs


def simulate_overlapping_sleeves(
    decisions: pd.DataFrame,
    *,
    return_column: str,
    horizon: int,
    sleeve_exposure: float,
) -> tuple[pd.DataFrame, np.ndarray, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    pending: deque[tuple[pd.Timestamp, float, float, str]] = deque()
    records: list[dict[str, Any]] = []
    notionals = np.zeros(len(decisions), dtype="float64")
    max_open_gross = 0.0
    open_notional = 0.0
    ruined = False
    rows = decisions.reset_index(drop=True)
    for index, row in enumerate(rows.itertuples(index=False)):
        entry_time = row.ts + pd.Timedelta(hours=1)
        while pending and pending[0][0] <= entry_time:
            exit_time, pnl, opened_exposure, fold_id = pending.popleft()
            before = equity
            equity = max(0.0, equity + pnl)
            period_return = equity / before - 1.0 if before > 0.0 else 0.0
            peak = max(peak, equity)
            drawdown = equity / peak - 1.0 if peak > 0.0 else -1.0
            max_drawdown = min(max_drawdown, drawdown)
            records.append(
                {
                    "ts": exit_time,
                    "period_return": period_return,
                    "equity": equity,
                    "drawdown": drawdown,
                    "fold_id": fold_id,
                }
            )
            open_notional = max(0.0, open_notional - opened_exposure)
            if equity <= 0.0:
                ruined = True
                pending.clear()
                open_notional = 0.0
                break
        opened_exposure = 0.0
        pnl = 0.0
        if bool(row.active) and equity > 0.0 and not ruined:
            notional = equity * sleeve_exposure
            notionals[index] = notional
            pnl = notional * float(getattr(row, return_column))
            opened_exposure = sleeve_exposure
            open_notional += sleeve_exposure
            max_open_gross = max(max_open_gross, open_notional)
        if not ruined:
            pending.append(
                (
                    entry_time + pd.Timedelta(hours=horizon),
                    pnl,
                    opened_exposure,
                    str(row.fold_id),
                )
            )
    while pending:
        exit_time, pnl, opened_exposure, fold_id = pending.popleft()
        before = equity
        equity = max(0.0, equity + pnl)
        period_return = equity / before - 1.0 if before > 0.0 else 0.0
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0 if peak > 0.0 else -1.0
        max_drawdown = min(max_drawdown, drawdown)
        records.append(
            {
                "ts": exit_time,
                "period_return": period_return,
                "equity": equity,
                "drawdown": drawdown,
                "fold_id": fold_id,
            }
        )
        open_notional = max(0.0, open_notional - opened_exposure)
        if equity <= 0.0:
            pending.clear()
            open_notional = 0.0
            break
    curve = pd.DataFrame(records)
    if curve.empty:
        curve = pd.DataFrame(
            columns=["ts", "period_return", "equity", "drawdown", "fold_id"]
        )
    return curve, notionals, max_open_gross


def profit_factor(values: np.ndarray) -> float:
    positive = float(values[values > 0.0].sum())
    negative = float(-values[values < 0.0].sum())
    return positive / negative if negative > 0.0 else (float("inf") if positive else 0.0)


def evaluate_policy(
    decisions: pd.DataFrame,
    legs: pd.DataFrame,
    *,
    horizon: int,
    decision_frequency: int,
    gross_exposure: float,
) -> dict[str, Any]:
    sleeve_exposure = gross_exposure * min(1.0, decision_frequency / horizon)
    curve, notionals, max_open_gross = simulate_overlapping_sleeves(
        decisions,
        return_column="portfolio_return",
        horizon=horizon,
        sleeve_exposure=sleeve_exposure,
    )
    stress_curve, _, stress_max_open_gross = simulate_overlapping_sleeves(
        decisions,
        return_column="portfolio_stress_return",
        horizon=horizon,
        sleeve_exposure=sleeve_exposure,
    )
    active = decisions["active"].to_numpy()
    active_returns = decisions.loc[decisions["active"], "portfolio_return"].to_numpy(
        dtype="float64"
    )
    total_return = float(curve["equity"].iloc[-1] - 1.0) if not curve.empty else 0.0
    stress_total = (
        float(stress_curve["equity"].iloc[-1] - 1.0)
        if not stress_curve.empty
        else 0.0
    )
    start = decisions["ts"].min()
    end = decisions["ts"].max() + pd.Timedelta(hours=horizon + 1)
    years = max((end - start).total_seconds() / (365.25 * 86_400.0), 1 / 365.25)
    annualized = (
        float((1.0 + total_return) ** (1.0 / years) - 1.0)
        if total_return > -1.0
        else -1.0
    )
    realized = curve["period_return"].to_numpy(dtype="float64")
    expected_periods_per_year = 24.0 * 365.25 / decision_frequency
    standard_deviation = float(np.std(realized, ddof=1)) if len(realized) > 1 else 0.0
    sharpe = (
        float(np.mean(realized) / standard_deviation * np.sqrt(expected_periods_per_year))
        if standard_deviation > 0.0
        else 0.0
    )
    fold_returns = curve.groupby("fold_id", sort=False)["period_return"].apply(
        lambda values: float(np.prod(1.0 + values.to_numpy()) - 1.0)
    )
    monthly = curve.set_index("ts")["period_return"].groupby(
        pd.Grouper(freq="MS")
    ).apply(lambda values: float(np.prod(1.0 + values.to_numpy()) - 1.0))
    notional_by_ts = pd.Series(notionals, index=decisions["ts"])
    weighted_legs = legs.copy()
    weighted_legs["decision_notional"] = weighted_legs["ts"].map(notional_by_ts)
    counts = weighted_legs.groupby("ts")["symbol"].transform("size")
    weighted_legs["positive_pnl"] = (
        weighted_legs["decision_notional"]
        / counts
        * weighted_legs["trade_return"].clip(lower=0.0)
    )
    symbol_positive = weighted_legs.groupby("symbol")["positive_pnl"].sum()
    symbol_concentration = (
        float(symbol_positive.max() / symbol_positive.sum())
        if symbol_positive.sum() > 0.0
        else 1.0
    )
    positive_by_month = weighted_legs.assign(
        month=weighted_legs["ts"].dt.strftime("%Y-%m")
    ).groupby("month")["positive_pnl"].sum()
    month_concentration = (
        float(positive_by_month.max() / positive_by_month.sum())
        if positive_by_month.sum() > 0.0
        else 1.0
    )
    decision_count = int(active.sum())
    trade_count = len(weighted_legs)
    max_drawdown = float(curve["drawdown"].min()) if not curve.empty else 0.0
    stress_drawdown = (
        float(stress_curve["drawdown"].min()) if not stress_curve.empty else 0.0
    )
    result = {
        "total_return": total_return,
        "annualized_return": annualized,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "profit_factor": profit_factor(active_returns),
        "win_rate": float((active_returns > 0.0).mean()) if decision_count else 0.0,
        "decision_count": decision_count,
        "trade_count": trade_count,
        "active_decision_share": float(active.mean()) if len(active) else 0.0,
        "positive_month_share": float(monthly.gt(0.0).mean()) if len(monthly) else 0.0,
        "positive_fold_count": int(fold_returns.gt(0.0).sum()),
        "worst_fold_return": float(fold_returns.min()) if len(fold_returns) else 0.0,
        "stress_total_return": stress_total,
        "stress_max_drawdown": stress_drawdown,
        "symbol_positive_profit_concentration": symbol_concentration,
        "month_positive_profit_concentration": month_concentration,
        "sleeve_exposure": sleeve_exposure,
        "max_scheduled_open_gross": max_open_gross,
        "stress_max_scheduled_open_gross": stress_max_open_gross,
        "bankrupt": bool(total_return <= -1.0 + 1e-12),
        "stress_bankrupt": bool(stress_total <= -1.0 + 1e-12),
    }
    result["historical_gate_pass"] = bool(
        result["annualized_return"] >= 0.50
        and result["max_drawdown"] >= -0.25
        and result["win_rate"] >= 0.52
        and result["sharpe"] >= 1.00
        and result["profit_factor"] >= 1.10
        and result["decision_count"] >= 100
        and result["trade_count"] >= 500
        and result["positive_month_share"] >= 0.55
        and result["positive_fold_count"] >= 4
        and result["stress_total_return"] > 0.0
        and result["stress_max_drawdown"] >= -0.30
        and result["symbol_positive_profit_concentration"] <= 0.25
        and result["month_positive_profit_concentration"] <= 0.35
        and result["max_scheduled_open_gross"] <= gross_exposure + 1e-9
        and not result["bankrupt"]
        and not result["stress_bankrupt"]
    )
    result["selection_score"] = float(
        result["annualized_return"]
        + 0.20 * result["sharpe"]
        + 0.50 * result["win_rate"]
        + 0.05 * result["positive_fold_count"]
        - 3.0 * max(0.0, -result["max_drawdown"] - 0.20)
        - 2.0 * max(0.0, 1.30 - min(result["profit_factor"], 1.30))
        - max(0.0, result["symbol_positive_profit_concentration"] - 0.25)
    )
    return result


def main() -> None:
    args = parse_args()
    validate_boundary()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for horizon in args.horizons:
        bundle = load_prediction_bundle(args, horizon)
        for score_source in args.score_sources:
            candidates = candidate_sides(
                bundle, score_source=score_source, horizon=horizon
            )
            penalties = TAIL_PENALTIES if score_source == "lgbm" else ((0.0, 0.0),)
            for decision_frequency in DECISION_FREQUENCIES:
                scheduled_candidates = candidates.loc[
                    candidates["ts"].dt.hour % decision_frequency == 0
                ].copy()
                print(
                    f"search source={score_source} horizon={horizon}h "
                    f"frequency={decision_frequency}h rows={len(scheduled_candidates)}",
                    flush=True,
                )
                for mae_penalty, event_penalty in penalties:
                    for side_mode in SIDE_MODES:
                        for threshold in UTILITY_THRESHOLDS:
                            for max_positions in MAX_POSITIONS:
                                selected = select_legs(
                                    scheduled_candidates,
                                    side_mode=side_mode,
                                    mae_penalty=mae_penalty,
                                    event_penalty=event_penalty,
                                    utility_threshold=threshold,
                                    max_positions=max_positions,
                                )
                                decisions, legs = scheduled_policy(
                                    scheduled_candidates,
                                    selected,
                                    decision_frequency=decision_frequency,
                                )
                                for gross_exposure in GROSS_EXPOSURES:
                                    metrics = evaluate_policy(
                                        decisions,
                                        legs,
                                        horizon=horizon,
                                        decision_frequency=decision_frequency,
                                        gross_exposure=gross_exposure,
                                    )
                                    rows.append(
                                        {
                                            "score_source": score_source,
                                            "return_model_type": args.return_model_type,
                                            "mae_model_type": args.mae_model_type,
                                            "event_model_type": args.event_model_type,
                                            "feature_set": args.feature_set,
                                            "seed": args.seed,
                                            "horizon_hours": horizon,
                                            "decision_frequency_hours": (
                                                decision_frequency
                                            ),
                                            "side_mode": side_mode,
                                            "mae_penalty": mae_penalty,
                                            "event_penalty": event_penalty,
                                            "utility_threshold": threshold,
                                            "max_positions": max_positions,
                                            "gross_exposure": gross_exposure,
                                            **metrics,
                                        }
                                    )
    results = pd.DataFrame(rows).sort_values(
        ["historical_gate_pass", "selection_score"], ascending=[False, False]
    )
    horizon_text = "-".join(str(horizon) for horizon in args.horizons)
    suffix = (
        f"{args.feature_set}_{args.return_model_type}_h{horizon_text}_s{args.seed}"
    )
    results_path = OUTPUT_ROOT / f"allocator_search_{suffix}.csv"
    frontier_path = OUTPUT_ROOT / f"allocator_frontier_{suffix}.csv"
    summary_path = OUTPUT_ROOT / f"allocator_search_summary_{suffix}.json"
    results.to_csv(results_path, index=False)
    results.head(250).to_csv(frontier_path, index=False)
    summary = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "configuration_count": len(results),
        "historical_gate_pass_count": int(results["historical_gate_pass"].sum()),
        "score_sources": args.score_sources,
        "horizons": args.horizons,
        "feature_set": args.feature_set,
        "return_model_type": args.return_model_type,
        "mae_model_type": args.mae_model_type,
        "event_model_type": args.event_model_type,
        "seed": args.seed,
        "best": results.iloc[0].to_dict(),
        "results_csv": str(results_path.relative_to(ROOT)),
        "frontier_csv": str(frontier_path.relative_to(ROOT)),
        "cost_contract": {
            "baseline_round_trip": ROUND_TRIP_COST,
            "stress_multiplier": 1.5,
            "stress_extra_round_trip": STRESS_EXTRA_COST,
        },
        "overlap_contract": (
            "Each decision is a separate futures sleeve; sleeve exposure is capped "
            "by decision_frequency/horizon and PnL is realized at its own exit."
        ),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "configuration_count": summary["configuration_count"],
                "historical_gate_pass_count": summary[
                    "historical_gate_pass_count"
                ],
                "best": summary["best"],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
