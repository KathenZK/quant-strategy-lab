from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from train_prefit_walk_forward import FOLDS


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MODEL_ROOT = ARTIFACT_DIR / "prefit_walk_forward"
ROBUSTNESS_ROOT = (
    ARTIFACT_DIR / "prefit_candidate_robustness/full_coverage_tw730d"
)
BROAD_ROOT = ARTIFACT_DIR / "prefit_broad_universe_transfer/tw730d"
SEARCH_ROOT = ARTIFACT_DIR / "prefit_portfolio_search"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "prefit_model_matrix_manifest.json"
FACTOR_MANIFEST_PATH = (
    ARTIFACT_DIR / "cross_sectional_factor_dataset/factor_dataset_manifest.json"
)
PANEL_AUDIT_PATH = ARTIFACT_DIR / "cross_sectional_factor_panel_audit_2026-07-17.json"
DATA_AUDIT_PATH = ARTIFACT_DIR / "binance_usdm_data_quality_20260717T051109Z.json"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/binance-1h-cslgbm-research-contract-2026-07-17.md"
)
SEARCH_SUMMARY_PATH = SEARCH_ROOT / (
    "prefit_portfolio_search_summary_"
    "full_coverage_tw730d_ensemble_s7-17-29-42.json"
)
ROBUSTNESS_PATH = ROBUSTNESS_ROOT / "prefit_candidate_robustness.json"
BROAD_PATH = BROAD_ROOT / "broad_universe_transfer_audit.json"
BASELINE_SEARCH_PATH = SEARCH_ROOT / "prefit_portfolio_search.csv"
FROZEN_PATH = ARTIFACT_DIR / "binance_1h_cslgbm_v1_frozen_prefit_candidate.json"
FROZEN_SHA_PATH = FROZEN_PATH.with_suffix(".sha256")
OOS_REVEAL_MARKER = ARTIFACT_DIR / "binance_1h_cslgbm_v1_oos_revealed.json"

SEEDS = (7, 17, 29, 42)
FEATURE_SET = "full_coverage"
TRAIN_WINDOW_DAYS = 730
HORIZON = 24
TOP_N = 7
EXPOSURE = 0.45
OFFSET = 0


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"required artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def model_artifacts() -> list[dict[str, Any]]:
    rows = []
    for fold_id, _, _ in FOLDS:
        for seed in SEEDS:
            identity = (
                f"regression_{FEATURE_SET}_{HORIZON}h_{fold_id}_"
                f"tw{TRAIN_WINDOW_DAYS}d_s{seed}"
            )
            directory = MODEL_ROOT / identity
            model = directory / "model.txt"
            diagnostics = directory / "diagnostics.json"
            predictions = directory / "predictions.parquet"
            for path in (model, diagnostics, predictions):
                if not path.exists():
                    raise RuntimeError(f"candidate artifact is missing: {path}")
            diagnostic = load_json(diagnostics)
            if diagnostic.get("oos_revealed") is not False:
                raise RuntimeError(f"model did not prove sealed OOS: {identity}")
            rows.append({
                "identity": identity,
                "fold_id": fold_id,
                "seed": seed,
                "model_path": str(model),
                "model_sha256": file_sha256(model),
                "diagnostics_path": str(diagnostics),
                "diagnostics_sha256": file_sha256(diagnostics),
                "predictions_path": str(predictions),
                "predictions_sha256": file_sha256(predictions),
                "best_iteration": diagnostic["best_iteration"],
                "mean_hourly_rank_ic": diagnostic["predictive"][
                    "mean_hourly_rank_ic"
                ],
            })
    return rows


def validate_candidate_evidence() -> dict[str, Any]:
    if OOS_REVEAL_MARKER.exists():
        raise RuntimeError("OOS has already been revealed; candidate cannot be re-frozen")
    matrix = load_json(MATRIX_MANIFEST_PATH)
    factor_manifest = load_json(FACTOR_MANIFEST_PATH)
    panel_audit = load_json(PANEL_AUDIT_PATH)
    data_audit = load_json(DATA_AUDIT_PATH)
    search = load_json(SEARCH_SUMMARY_PATH)
    robustness = load_json(ROBUSTNESS_PATH)
    broad = load_json(BROAD_PATH)
    for name, payload in (
        ("search", search),
        ("robustness", robustness),
        ("broad", broad),
    ):
        if payload.get("oos_revealed") is not False:
            raise RuntimeError(f"{name} artifact did not prove sealed OOS")
    if data_audit.get("status") != "PASS" or data_audit.get("blockers"):
        raise RuntimeError("source data audit is not PASS")
    if panel_audit.get("status") != "PASS" or panel_audit.get("blockers"):
        raise RuntimeError("factor panel audit is not PASS")
    if not matrix.get("physical_oos_isolation"):
        raise RuntimeError("model matrix is not physically isolated from OOS")
    candidate = robustness["candidate_under_audit"]
    expected = {
        "feature_set": FEATURE_SET,
        "train_window_days": TRAIN_WINDOW_DAYS,
        "horizon_hours": HORIZON,
        "account_mode": "long_short",
        "top_n": TOP_N,
        "confidence_threshold": 0.0,
        "exposure": EXPOSURE,
    }
    for key, value in expected.items():
        if candidate.get(key) != value:
            raise RuntimeError(
                f"robustness candidate mismatch {key}: {candidate.get(key)} != {value}"
            )
    timing = pd.read_csv(ROBUSTNESS_ROOT / "timing_offsets.csv")
    timing = timing.loc[
        (timing["top_n"] == TOP_N) & (timing["exposure"] == EXPOSURE)
    ].copy()
    if len(timing) != HORIZON or not timing["hard_gate_pass"].all():
        raise RuntimeError("candidate did not pass all 24 timing offsets")
    main = timing.loc[timing["offset_utc_hours"] == OFFSET]
    if len(main) != 1 or not bool(main.iloc[0]["hard_gate_pass"]):
        raise RuntimeError("candidate main offset did not pass")
    seeds = pd.read_csv(ROBUSTNESS_ROOT / "seed_robustness.csv")
    if set(seeds["seed"]) != set(SEEDS) or not seeds["hard_gate_pass"].all():
        raise RuntimeError("candidate did not pass every individual seed")
    liquidity = pd.read_csv(ROBUSTNESS_ROOT / "liquidity_robustness_summary.csv")
    if not liquidity["hard_gate_pass_offsets"].eq(HORIZON).all():
        raise RuntimeError("candidate did not pass every main liquidity timing stress")
    broad_summary = pd.read_csv(BROAD_ROOT / "broad_universe_summary.csv")
    if not broad_summary["hard_gate_pass_offsets"].eq(HORIZON).all():
        raise RuntimeError("candidate did not pass broad Top150/5m transfer")
    regimes = pd.read_csv(ROBUSTNESS_ROOT / "regime_robustness.csv")
    if not regimes["total_return"].gt(0.0).all():
        raise RuntimeError("candidate lost money in a prefit regime slice")
    baselines = pd.read_csv(BASELINE_SEARCH_PATH)
    pass_sources = sorted(baselines.loc[baselines["hard_gate_pass"], "score_source"].unique())
    if pass_sources != ["regression"]:
        raise RuntimeError(f"unexpected hard-gate pass sources: {pass_sources}")
    features = list(matrix["feature_sets"][FEATURE_SET])
    if len(features) != 165:
        raise RuntimeError(f"unexpected frozen feature count: {len(features)}")
    return {
        "matrix": matrix,
        "factor_manifest": factor_manifest,
        "main_metrics": main.iloc[0].to_dict(),
        "timing_summary": {
            "offset_count": len(timing),
            "hard_gate_pass_offsets": int(timing["hard_gate_pass"].sum()),
            "worst_annualized_return": float(timing["annualized_return"].min()),
            "worst_max_drawdown": float(timing["max_drawdown"].min()),
            "worst_stress_max_drawdown": float(
                timing["stress_max_drawdown"].min()
            ),
            "minimum_win_rate": float(timing["win_rate"].min()),
            "minimum_sharpe": float(timing["sharpe"].min()),
            "minimum_profit_factor": float(timing["profit_factor"].min()),
        },
        "seed_metrics": seeds.to_dict(orient="records"),
        "liquidity_summary": liquidity.to_dict(orient="records"),
        "broad_summary": broad_summary.to_dict(orient="records"),
        "regime_summary": regimes.to_dict(orient="records"),
        "pass_sources": pass_sources,
        "features": features,
    }


def main() -> None:
    evidence = validate_candidate_evidence()
    models = model_artifacts()
    source_paths = [
        CONTRACT_PATH,
        DATA_AUDIT_PATH,
        PANEL_AUDIT_PATH,
        FACTOR_MANIFEST_PATH,
        MATRIX_MANIFEST_PATH,
        SEARCH_SUMMARY_PATH,
        ROBUSTNESS_PATH,
        BROAD_PATH,
        BASELINE_SEARCH_PATH,
    ]
    payload = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "version": "BIN-1H-CSLGBM-V1",
        "frozen_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "registered / pre-OOS frozen / not promoted / not live-ready",
        "oos_revealed": False,
        "oos_contract": {
            "start": "2026-04-01T00:00:00Z",
            "end_exclusive": "2026-07-01T00:00:00Z",
            "completed_trade_end_purge_hours": 25,
            "reveal_count_allowed": 1,
        },
        "universe": {
            "market": "Binance USD-M USDT perpetual crypto only",
            "point_in_time_min_age_hours": 720,
            "trailing_30d_coverage": 0.99,
            "trailing_7d_avg_daily_quote_volume_min": 10_000_000.0,
            "liquidity_top_n": 100,
        },
        "model": {
            "type": "LightGBM regression four-seed mean ensemble",
            "target": "24h label_long_relative net of baseline costs and funding",
            "feature_set": FEATURE_SET,
            "feature_count": len(evidence["features"]),
            "features": evidence["features"],
            "seeds": list(SEEDS),
            "train_window_days": TRAIN_WINDOW_DAYS,
            "train_sample_hours": 4,
            "inner_validation_days": 120,
            "purge_hours": 24,
            "refit_after_early_stopping": False,
            "parameters": load_json(Path(models[0]["diagnostics_path"]))[
                "model_parameters"
            ],
        },
        "portfolio": {
            "feature_decision_hour_utc": OFFSET,
            "entry": "K1 open after the 00:00 UTC feature bar",
            "holding_hours": HORIZON,
            "account_mode": "market-neutral long-short",
            "long_count": TOP_N,
            "short_count": TOP_N,
            "ranking": "long highest ensemble scores; short lowest ensemble scores",
            "confidence_threshold": 0.0,
            "gross_exposure": EXPOSURE,
            "long_gross_exposure": EXPOSURE / 2.0,
            "short_gross_exposure": EXPOSURE / 2.0,
            "per_leg_capital_weight": EXPOSURE / (2.0 * TOP_N),
            "rebalance": "every 24h; close then open; full round-trip cost each leg",
        },
        "cost": {
            "fee_per_fill": 0.001,
            "adverse_slippage_bps_per_fill": 4.0,
            "round_trip_before_funding": 0.0028,
            "funding": "actual settlements by direction",
            "stress_multiplier": 1.5,
        },
        "metric_semantics": {
            "win_rate": "portfolio holding-period win rate",
            "profit_factor": "portfolio holding-period profit factor",
            "trade_count": "completed individual long/short legs",
            "decision_count": "completed 14-leg portfolio holding periods",
        },
        "prefit_main_metrics": evidence["main_metrics"],
        "prefit_timing_summary": evidence["timing_summary"],
        "prefit_seed_metrics": evidence["seed_metrics"],
        "prefit_liquidity_summary": evidence["liquidity_summary"],
        "prefit_broad_summary": evidence["broad_summary"],
        "prefit_regime_summary": evidence["regime_summary"],
        "baseline_conclusion": (
            "Only LightGBM regression produced any hard-gate pass; classification, "
            "LGBMRanker, Ridge, momentum, reversal, and carry-momentum produced zero."
        ),
        "model_artifacts": models,
        "source_artifacts": [
            {
                "path": str(path),
                "sha256": file_sha256(path),
            }
            for path in source_paths
        ],
        "next_gate": (
            "One-time sealed 2026Q2 OOS reveal. Registration is not promotion and "
            "does not establish live readiness."
        ),
    }
    FROZEN_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    frozen_sha = file_sha256(FROZEN_PATH)
    FROZEN_SHA_PATH.write_text(f"{frozen_sha}  {FROZEN_PATH.name}\n", encoding="utf-8")
    print(json.dumps({
        "frozen_candidate": str(FROZEN_PATH),
        "sha256": frozen_sha,
        "version": payload["version"],
        "status": payload["status"],
        "oos_revealed": False,
        "prefit_main_metrics": payload["prefit_main_metrics"],
        "timing_summary": payload["prefit_timing_summary"],
    }, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
