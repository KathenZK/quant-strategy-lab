from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

from search_prefit_portfolios import (
    add_cross_sectional_score_state,
    build_policy,
    evaluate_policy,
)
from train_prefit_walk_forward import FOLDS, clean_features


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PANEL_ROOT = ARTIFACT_DIR / "cross_sectional_factor_dataset/panel"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "prefit_model_matrix_manifest.json"
MODEL_ROOT = ARTIFACT_DIR / "prefit_walk_forward"
OUTPUT_ROOT = ARTIFACT_DIR / "prefit_broad_universe_transfer"
HORIZON = 24
FEATURE_SET = "full_coverage"
SEEDS = (7, 17, 29, 42)
TOP_N = 7
EXPOSURE = 0.45
PREFIT_END = pd.Timestamp("2026-03-31T00:00:00Z")


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit transfer to the broad historical Top150/5m universe."
    )
    parser.add_argument("--train-window-days", type=int)
    return parser.parse_args()


def prefit_panel_files() -> list[Path]:
    files = []
    for directory in sorted(PANEL_ROOT.glob("year_month=*")):
        if directory.name.removeprefix("year_month=") >= "2026-04":
            continue
        files.extend(sorted(directory.glob("*.parquet")))
    if not files:
        raise RuntimeError("no pre-OOS panel files")
    return files


def source_file_list() -> str:
    return "[" + ",".join(
        f"'{sql_path(path)}'" for path in prefit_panel_files()
    ) + "]"


def feature_names() -> list[str]:
    manifest = json.loads(MATRIX_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not manifest.get("physical_oos_isolation"):
        raise RuntimeError("prefit matrix did not prove OOS isolation")
    return list(manifest["feature_sets"][FEATURE_SET])


def label_columns() -> list[str]:
    return [
        f"label_funding_sum_{HORIZON}h",
        f"label_long_net_{HORIZON}h",
        f"label_short_net_{HORIZON}h",
        f"label_gross_return_{HORIZON}h",
        f"label_long_relative_{HORIZON}h",
        f"label_short_relative_{HORIZON}h",
    ]


def load_fold(
    connection: duckdb.DuckDBPyConnection,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    features: list[str],
) -> pd.DataFrame:
    feature_sql = ", ".join(f'"{name}"' for name in features)
    labels_sql = ", ".join(label_columns())
    frame = connection.execute(
        f"""
        SELECT
            epoch_ms(ts)::BIGINT AS ts_ms,
            symbol,
            liquidity_rank,
            avg_daily_quote_volume_7d,
            universe_main,
            {feature_sql},
            {labels_sql}
        FROM read_parquet(
            {source_file_list()},
            hive_partitioning = false,
            union_by_name = true
        )
        WHERE ts >= TIMESTAMPTZ '{start.isoformat()}'
          AND ts < TIMESTAMPTZ '{end.isoformat()}'
        ORDER BY ts, symbol
        """
    ).fetch_df()
    frame["ts"] = pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True)
    return frame


def model_path(
    fold_id: str, seed: int, train_window_days: int | None
) -> Path:
    window_suffix = (
        f"_tw{train_window_days}d" if train_window_days is not None else ""
    )
    identity = (
        f"regression_{FEATURE_SET}_{HORIZON}h_{fold_id}{window_suffix}_s{seed}"
    )
    path = MODEL_ROOT / identity / "model.txt"
    if not path.exists():
        raise RuntimeError(f"model is missing: {path}")
    return path


def build_predictions(
    prediction_path: Path, train_window_days: int | None
) -> pd.DataFrame:
    if prediction_path.exists():
        frame = pd.read_parquet(prediction_path)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    features = feature_names()
    connection = duckdb.connect()
    connection.execute("SET threads = 8")
    frames = []
    for fold_id, start_text, end_text in FOLDS:
        start = pd.Timestamp(start_text)
        end = pd.Timestamp(end_text)
        if end > PREFIT_END:
            raise RuntimeError("fold crossed OOS boundary")
        frame = load_fold(connection, start=start, end=end, features=features)
        x = clean_features(frame, features)
        scores = []
        for seed in SEEDS:
            booster = lgb.Booster(
                model_file=str(model_path(fold_id, seed, train_window_days))
            )
            scores.append(booster.predict(x).astype("float32"))
        keep = [
            "ts",
            "symbol",
            "liquidity_rank",
            "avg_daily_quote_volume_7d",
            "universe_main",
            *label_columns(),
        ]
        output = frame[keep].copy()
        output["score"] = np.mean(np.stack(scores), axis=0).astype("float32")
        output["fold_id"] = fold_id
        frames.append(output)
        print(f"predicted {fold_id} rows={len(output)}", flush=True)
    result = pd.concat(frames, ignore_index=True)
    if result["ts"].max() >= PREFIT_END:
        raise RuntimeError("broad transfer predictions crossed OOS boundary")
    result.to_parquet(prediction_path, index=False, compression="zstd")
    return result


def audit_variant(frame: pd.DataFrame, name: str) -> list[dict[str, Any]]:
    scored = add_cross_sectional_score_state(frame)
    decisions, legs = build_policy(
        scored,
        horizon=HORIZON,
        account_mode="long_short",
        top_n=TOP_N,
    )
    return [
        {
            "universe_variant": name,
            "offset_utc_hours": offset,
            "rows": len(frame),
            "symbols": int(frame["symbol"].nunique()),
            **evaluate_policy(
                decisions,
                legs,
                horizon=HORIZON,
                threshold=0.0,
                exposure=EXPOSURE,
                offset_utc_hours=offset,
            ),
        }
        for offset in range(HORIZON)
    ]


def main() -> None:
    args = parse_args()
    output_root = OUTPUT_ROOT
    if args.train_window_days is not None:
        output_root = OUTPUT_ROOT / f"tw{args.train_window_days}d"
    output_root.mkdir(parents=True, exist_ok=True)
    prediction_path = output_root / "broad_transfer_predictions.parquet"
    predictions = build_predictions(prediction_path, args.train_window_days)
    variants = {
        "broad_top150_5m": predictions,
        "main_top100_10m": predictions.loc[predictions["universe_main"]].copy(),
        "top50": predictions.loc[predictions["liquidity_rank"] <= 50].copy(),
        "avg_daily_quote_volume_20m": predictions.loc[
            predictions["avg_daily_quote_volume_7d"] >= 20_000_000.0
        ].copy(),
    }
    rows = [
        row
        for name, frame in variants.items()
        for row in audit_variant(frame, name)
    ]
    results = pd.DataFrame(rows)
    results_path = output_root / "broad_universe_timing_audit.csv"
    results.to_csv(results_path, index=False)
    summary = results.groupby("universe_variant").agg(
        hard_gate_pass_offsets=("hard_gate_pass", "sum"),
        worst_annualized_return=("annualized_return", "min"),
        worst_max_drawdown=("max_drawdown", "min"),
        worst_stress_max_drawdown=("stress_max_drawdown", "min"),
        minimum_win_rate=("win_rate", "min"),
        minimum_sharpe=("sharpe", "min"),
        minimum_profit_factor=("profit_factor", "min"),
        minimum_positive_month_share=("positive_month_share", "min"),
        minimum_positive_fold_count=("positive_fold_count", "min"),
    ).reset_index()
    summary_path = output_root / "broad_universe_summary.csv"
    summary.to_csv(summary_path, index=False)
    report = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "oos_revealed": False,
        "model": "four-seed full-coverage regression ensemble",
        "train_window_days": args.train_window_days,
        "candidate": {
            "horizon_hours": HORIZON,
            "account_mode": "long_short",
            "top_n": TOP_N,
            "exposure": EXPOSURE,
        },
        "summary": summary.to_dict(orient="records"),
        "predictions": str(prediction_path),
        "results_csv": str(results_path),
    }
    report_path = output_root / "broad_universe_transfer_audit.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
