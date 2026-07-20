from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FROZEN_PATH = ARTIFACT_DIR / "binance_1h_cslgbm_v1_frozen_prefit_candidate.json"
REVEAL_MARKER = ARTIFACT_DIR / "binance_1h_cslgbm_v1_oos_revealed.json"
OOS_ROOT = ARTIFACT_DIR / "v1_oos_2026q2"
RESULT_PATH = OOS_ROOT / "oos_result.json"
DECISION_PATH = OOS_ROOT / "oos_portfolio_decisions.csv"
TRADE_PATH = OOS_ROOT / "oos_completed_trades.csv"
BASELINE_PATH = OOS_ROOT / "oos_rule_baselines.csv"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compound(values: pd.Series) -> float:
    return float(np.prod(1.0 + values.to_numpy(dtype="float64")) - 1.0)


def gate_checks(metrics: dict[str, Any], frozen: dict[str, Any]) -> dict[str, bool]:
    return {
        "annualized_return_gte_100pct": metrics["annualized_return"] >= 1.0,
        "max_drawdown_lte_20pct": metrics["max_drawdown"] >= -0.20,
        "portfolio_win_rate_gte_55pct": metrics["win_rate"] >= 0.55,
        "sharpe_gte_1_5": metrics["sharpe"] >= 1.50,
        "profit_factor_gte_1_30": metrics["profit_factor"] >= 1.30,
        "completed_trade_legs_gte_100": metrics["trade_count"] >= 100,
        "positive_month_share_gte_60pct": metrics["positive_month_share"] >= 0.60,
        "stress_1_5x_positive": metrics["stress_total_return"] > 0.0,
        "stress_1_5x_drawdown_lte_25pct": (
            metrics["stress_max_drawdown"] >= -0.25
        ),
        "single_symbol_positive_profit_lte_25pct": (
            metrics["symbol_positive_profit_concentration"] <= 0.25
        ),
        "single_month_positive_profit_lte_35pct": (
            metrics["month_positive_profit_concentration"] <= 0.35
        ),
        "prefit_walk_forward_majority_positive": (
            frozen["prefit_main_metrics"]["positive_fold_count"] >= 3
        ),
        "lightgbm_prefit_beats_simple_baselines": (
            frozen["baseline_conclusion"].startswith("Only LightGBM regression")
        ),
    }


def monthly_evidence(decisions: pd.DataFrame) -> pd.DataFrame:
    frame = decisions.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["month"] = frame["ts"].dt.strftime("%Y-%m")
    rows = []
    total_positive = float(frame["portfolio_return"].clip(lower=0.0).sum())
    for month, group in frame.groupby("month", sort=True):
        positive = float(group["portfolio_return"].clip(lower=0.0).sum())
        rows.append({
            "month": month,
            "decision_count": len(group),
            "compounded_return": compound(group["portfolio_return"]),
            "win_rate": float(group["portfolio_return"].gt(0.0).mean()),
            "positive_period_profit": positive,
            "positive_profit_contribution": (
                positive / total_positive if total_positive > 0.0 else 1.0
            ),
        })
    return pd.DataFrame(rows)


def symbol_evidence(trades: pd.DataFrame) -> pd.DataFrame:
    frame = trades.copy()
    frame["positive_weighted_return"] = frame["weighted_return"].clip(lower=0.0)
    grouped = frame.groupby("symbol", sort=False).agg(
        completed_trades=("symbol", "size"),
        weighted_net_return_sum=("weighted_return", "sum"),
        positive_weighted_return=("positive_weighted_return", "sum"),
    ).reset_index()
    total_positive = float(grouped["positive_weighted_return"].sum())
    grouped["positive_profit_contribution"] = (
        grouped["positive_weighted_return"] / total_positive
        if total_positive > 0.0
        else 1.0
    )
    return grouped.sort_values("positive_profit_contribution", ascending=False)


def baseline_gate_rows(
    baselines: pd.DataFrame, frozen: dict[str, Any]
) -> pd.DataFrame:
    rows = []
    for _, row in baselines.iterrows():
        metrics = row.to_dict()
        checks = gate_checks(metrics, frozen)
        rows.append({
            "score_source": row["score_source"],
            "total_return": row["total_return"],
            "annualized_return": row["annualized_return"],
            "max_drawdown": row["max_drawdown"],
            "win_rate": row["win_rate"],
            "sharpe": row["sharpe"],
            "profit_factor": row["profit_factor"],
            "failed_gate_count": sum(not value for value in checks.values()),
            "all_gates_pass": all(checks.values()),
        })
    return pd.DataFrame(rows).sort_values("total_return", ascending=False)


def main() -> None:
    frozen = load_json(FROZEN_PATH)
    marker = load_json(REVEAL_MARKER)
    result = load_json(RESULT_PATH)
    frozen_sha = file_sha256(FROZEN_PATH)
    if marker["frozen_candidate_sha256"] != frozen_sha:
        raise RuntimeError("reveal marker does not match frozen candidate")
    if marker["result_sha256"] != file_sha256(RESULT_PATH):
        raise RuntimeError("OOS result changed after reveal marker")
    decisions = pd.read_csv(DECISION_PATH)
    trades = pd.read_csv(TRADE_PATH)
    baselines = pd.read_csv(BASELINE_PATH)
    monthly = monthly_evidence(decisions)
    symbols = symbol_evidence(trades)
    baseline_comparison = baseline_gate_rows(baselines, frozen)
    checks = gate_checks(result["metrics"], frozen)
    failures = [name for name, passed in checks.items() if not passed]
    audit = {
        "family": frozen["family"],
        "version": frozen["version"],
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "frozen_candidate_sha256": frozen_sha,
        "oos_revealed": True,
        "formal_status": "registered / not promoted / not live-ready",
        "research_gate_result": "HARD-GATE-FAILED" if failures else "ALL-GATES-PASSED",
        "gate_checks": checks,
        "failed_gates": failures,
        "metrics": result["metrics"],
        "monthly": monthly.to_dict(orient="records"),
        "top_symbol_positive_profit_contributors": symbols.head(20).to_dict(
            orient="records"
        ),
        "baseline_comparison": baseline_comparison.to_dict(orient="records"),
        "interpretation": (
            "The prefit walk-forward condition is evaluated from the frozen 5-fold "
            "evidence, not by demanding four folds inside the single sealed OOS. "
            "No post-reveal parameter or portfolio change is permitted."
        ),
    }
    monthly.to_csv(OOS_ROOT / "oos_monthly_contribution.csv", index=False)
    symbols.to_csv(OOS_ROOT / "oos_symbol_contribution.csv", index=False)
    baseline_comparison.to_csv(OOS_ROOT / "oos_baseline_gate_comparison.csv", index=False)
    audit_path = OOS_ROOT / "oos_gate_audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
