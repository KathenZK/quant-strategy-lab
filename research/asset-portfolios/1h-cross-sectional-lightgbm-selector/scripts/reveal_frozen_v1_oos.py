from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from search_prefit_portfolios import (
    BASELINES,
    add_cross_sectional_score_state,
    apply_score_source,
    build_policy,
    evaluate_policy,
    selection_frames,
)
from train_prefit_walk_forward import fit_predict, load_slice


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PANEL_ROOT = ARTIFACT_DIR / "cross_sectional_factor_dataset/panel"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "prefit_model_matrix_manifest.json"
FROZEN_PATH = ARTIFACT_DIR / "binance_1h_cslgbm_v1_frozen_prefit_candidate.json"
FROZEN_SHA_PATH = FROZEN_PATH.with_suffix(".sha256")
REVEAL_MARKER = ARTIFACT_DIR / "binance_1h_cslgbm_v1_oos_revealed.json"
OUTPUT_ROOT = ARTIFACT_DIR / "v1_oos_2026q2"
MODEL_ROOT = OUTPUT_ROOT / "models"
OOS_START = pd.Timestamp("2026-04-01T00:00:00Z")
OOS_END = pd.Timestamp("2026-07-01T00:00:00Z")
COMPLETED_ENTRY_END = OOS_END - pd.Timedelta(hours=25)
TRAIN_END = pd.Timestamp("2026-03-31T00:00:00Z")
TRAIN_WINDOW_DAYS = 730
HORIZON = 24
TOP_N = 7
EXPOSURE = 0.45
SEEDS = (7, 17, 29, 42)
FEATURE_SET = "full_coverage"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_frozen_candidate() -> tuple[dict[str, Any], str, list[str]]:
    if REVEAL_MARKER.exists():
        raise RuntimeError(
            f"OOS reveal marker already exists; repeated reveal is forbidden: {REVEAL_MARKER}"
        )
    if not FROZEN_PATH.exists() or not FROZEN_SHA_PATH.exists():
        raise RuntimeError("frozen candidate or SHA sidecar is missing")
    expected_sha = FROZEN_SHA_PATH.read_text(encoding="utf-8").split()[0]
    actual_sha = file_sha256(FROZEN_PATH)
    if expected_sha != actual_sha:
        raise RuntimeError("frozen candidate SHA mismatch")
    frozen = load_json(FROZEN_PATH)
    if frozen.get("oos_revealed") is not False:
        raise RuntimeError("frozen artifact does not prove sealed OOS")
    expected = {
        "feature_set": FEATURE_SET,
        "train_window_days": TRAIN_WINDOW_DAYS,
        "seeds": list(SEEDS),
    }
    for key, value in expected.items():
        if frozen["model"].get(key) != value:
            raise RuntimeError(f"frozen model mismatch: {key}")
    if frozen["portfolio"]["long_count"] != TOP_N:
        raise RuntimeError("frozen portfolio Top N mismatch")
    if frozen["portfolio"]["gross_exposure"] != EXPOSURE:
        raise RuntimeError("frozen exposure mismatch")
    matrix = load_json(MATRIX_MANIFEST_PATH)
    features = list(matrix["feature_sets"][FEATURE_SET])
    if features != frozen["model"]["features"]:
        raise RuntimeError("frozen features differ from matrix manifest")
    return frozen, actual_sha, features


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def oos_panel_files() -> list[Path]:
    result = []
    for month in ("2026-04", "2026-05", "2026-06"):
        result.extend(sorted((PANEL_ROOT / f"year_month={month}").glob("*.parquet")))
    if len(result) != 3:
        raise RuntimeError(f"expected three sealed OOS panel files, got {len(result)}")
    return result


def file_list_sql(paths: list[Path]) -> str:
    return "[" + ",".join(f"'{sql_path(path)}'" for path in paths) + "]"


def label_columns() -> list[str]:
    return [
        f"label_funding_sum_{HORIZON}h",
        f"label_long_net_{HORIZON}h",
        f"label_short_net_{HORIZON}h",
        f"label_gross_return_{HORIZON}h",
        f"label_long_relative_{HORIZON}h",
        f"label_short_relative_{HORIZON}h",
    ]


def load_oos(
    connection: duckdb.DuckDBPyConnection, features: list[str]
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
            {feature_sql},
            {labels_sql}
        FROM read_parquet(
            {file_list_sql(oos_panel_files())},
            hive_partitioning = false,
            union_by_name = true
        )
        WHERE universe_main
          AND ts >= TIMESTAMPTZ '{OOS_START.isoformat()}'
          AND ts < TIMESTAMPTZ '{OOS_END.isoformat()}'
        ORDER BY ts, symbol
        """
    ).fetch_df()
    frame["ts"] = pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True)
    frame["fold_id"] = "oos_2026q2"
    if frame.duplicated(["ts", "symbol"]).any():
        raise RuntimeError("duplicate OOS panel keys")
    return frame


def train_final_ensemble(
    connection: duckdb.DuckDBPyConnection,
    *,
    oos: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    train_start = TRAIN_END - pd.Timedelta(days=TRAIN_WINDOW_DAYS)
    train = load_slice(
        connection,
        features=features,
        horizon=HORIZON,
        start=train_start,
        end=TRAIN_END,
        sampled=True,
    )
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    scores = []
    diagnostics = []
    for seed in SEEDS:
        model_path = MODEL_ROOT / f"final_regression_s{seed}.txt"
        score, diagnostic = fit_predict(
            model_type="regression",
            train=train,
            validation=oos,
            features=features,
            horizon=HORIZON,
            seed=seed,
            model_path=model_path,
        )
        score_path = MODEL_ROOT / f"final_regression_s{seed}_diagnostics.json"
        payload = {
            "seed": seed,
            "train_start": train_start.isoformat(),
            "train_end_exclusive": TRAIN_END.isoformat(),
            "oos_start": OOS_START.isoformat(),
            "oos_end_exclusive": OOS_END.isoformat(),
            "model_path": str(model_path),
            "model_sha256": file_sha256(model_path),
            **diagnostic,
        }
        score_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        scores.append(score)
        diagnostics.append(payload)
        print(
            f"final seed={seed} best_iteration={diagnostic['best_iteration']} "
            f"oos_rank_ic={diagnostic['predictive']['mean_hourly_rank_ic']:.6f}",
            flush=True,
        )
    return np.mean(np.stack(scores), axis=0), diagnostics


def portfolio_evidence(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    complete = scored.loc[scored["ts"] < COMPLETED_ENTRY_END].copy()
    top, bottom = selection_frames(complete, HORIZON, TOP_N)
    top = top.loc[top["ts"].dt.hour == 0].copy()
    bottom = bottom.loc[bottom["ts"].dt.hour == 0].copy()
    weight = EXPOSURE / (2.0 * TOP_N)
    long_label = f"label_long_net_{HORIZON}h"
    short_label = f"label_short_net_{HORIZON}h"
    funding_label = f"label_funding_sum_{HORIZON}h"
    top["side"] = "long"
    top["trade_return"] = top[long_label].fillna(-1.0)
    top["funding_sum"] = top[funding_label]
    bottom["side"] = "short"
    bottom["trade_return"] = bottom[short_label].fillna(-1.0)
    bottom["funding_sum"] = bottom[funding_label]
    legs = pd.concat([top, bottom], ignore_index=True)
    legs["capital_weight"] = weight
    legs["weighted_return"] = legs["trade_return"] * weight
    legs["score_rank"] = legs.groupby("ts")["score"].rank(
        method="first", ascending=False
    )
    decision = legs.groupby("ts", sort=True).agg(
        portfolio_return=("weighted_return", "sum"),
        leg_count=("symbol", "size"),
    ).reset_index()
    decision["equity"] = (1.0 + decision["portfolio_return"]).cumprod()
    longs = top.groupby("ts")["symbol"].apply(lambda values: "|".join(values))
    shorts = bottom.groupby("ts")["symbol"].apply(lambda values: "|".join(values))
    decision = decision.merge(longs.rename("long_symbols"), on="ts")
    decision = decision.merge(shorts.rename("short_symbols"), on="ts")
    leg_columns = [
        "ts",
        "symbol",
        "side",
        "score",
        "score_z",
        "score_rank",
        "liquidity_rank",
        "avg_daily_quote_volume_7d",
        "funding_sum",
        "trade_return",
        "capital_weight",
        "weighted_return",
    ]
    return decision, legs[leg_columns].sort_values(["ts", "side", "score"])


def baseline_metrics(oos: pd.DataFrame) -> pd.DataFrame:
    rows = []
    complete = oos.loc[oos["ts"] < COMPLETED_ENTRY_END].copy()
    for source in BASELINES:
        scored = add_cross_sectional_score_state(apply_score_source(complete, source))
        decisions, legs = build_policy(
            scored,
            horizon=HORIZON,
            account_mode="long_short",
            top_n=TOP_N,
        )
        rows.append({
            "score_source": source,
            **evaluate_policy(
                decisions,
                legs,
                horizon=HORIZON,
                threshold=0.0,
                exposure=EXPOSURE,
                offset_utc_hours=0,
            ),
        })
    return pd.DataFrame(rows)


def main() -> None:
    frozen, frozen_sha, features = validate_frozen_candidate()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    oos = load_oos(connection, features)
    score, model_diagnostics = train_final_ensemble(
        connection, oos=oos, features=features
    )
    scored = oos.copy()
    scored["score"] = score.astype("float32")
    scored = add_cross_sectional_score_state(scored)
    predictions_path = OUTPUT_ROOT / "oos_predictions.parquet"
    scored.to_parquet(predictions_path, index=False, compression="zstd")
    complete = scored.loc[scored["ts"] < COMPLETED_ENTRY_END].copy()
    decisions, legs = build_policy(
        complete,
        horizon=HORIZON,
        account_mode="long_short",
        top_n=TOP_N,
    )
    metrics = evaluate_policy(
        decisions,
        legs,
        horizon=HORIZON,
        threshold=0.0,
        exposure=EXPOSURE,
        offset_utc_hours=0,
    )
    decision_evidence, leg_evidence = portfolio_evidence(scored)
    decision_path = OUTPUT_ROOT / "oos_portfolio_decisions.csv"
    trades_path = OUTPUT_ROOT / "oos_completed_trades.csv"
    decision_evidence.to_csv(decision_path, index=False)
    leg_evidence.to_csv(trades_path, index=False)
    baselines = baseline_metrics(oos)
    baseline_path = OUTPUT_ROOT / "oos_rule_baselines.csv"
    baselines.to_csv(baseline_path, index=False)
    result = {
        "family": frozen["family"],
        "version": frozen["version"],
        "revealed_at": pd.Timestamp.now("UTC").isoformat(),
        "frozen_candidate_sha256": frozen_sha,
        "oos_revealed": True,
        "oos_start": OOS_START.isoformat(),
        "oos_end_exclusive": OOS_END.isoformat(),
        "completed_entry_end_exclusive": COMPLETED_ENTRY_END.isoformat(),
        "oos_panel_rows": len(oos),
        "oos_symbols": int(oos["symbol"].nunique()),
        "metrics": metrics,
        "hard_gate_pass": bool(metrics["hard_gate_pass"]),
        "model_diagnostics": model_diagnostics,
        "rule_baselines": baselines.to_dict(orient="records"),
        "artifacts": {
            "predictions": str(predictions_path),
            "portfolio_decisions": str(decision_path),
            "completed_trades": str(trades_path),
            "rule_baselines": str(baseline_path),
        },
        "policy": (
            "This OOS may not be reused for parameter, feature, threshold, universe, "
            "or portfolio selection. Any post-reveal change requires a future OOS."
        ),
    }
    result_path = OUTPUT_ROOT / "oos_result.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    marker = {
        "version": frozen["version"],
        "revealed_at": result["revealed_at"],
        "frozen_candidate_sha256": frozen_sha,
        "result_path": str(result_path),
        "result_sha256": file_sha256(result_path),
        "hard_gate_pass": result["hard_gate_pass"],
    }
    REVEAL_MARKER.write_text(
        json.dumps(marker, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "version": result["version"],
        "frozen_candidate_sha256": frozen_sha,
        "oos_revealed": True,
        "metrics": metrics,
        "hard_gate_pass": result["hard_gate_pass"],
        "rule_baselines": result["rule_baselines"],
        "result_path": str(result_path),
    }, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
