from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
SCRIPT_DIR = FAMILY_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_prefit_portfolios import (  # noqa: E402
    add_cross_sectional_score_state,
    build_policy,
    evaluate_policy,
    return_metrics,
    selection_frames,
)


OOS_ROOT = FAMILY_DIR / "artifacts/v1_oos_2026q2"
PREDICTION_PATH = OOS_ROOT / "oos_predictions.parquet"
OUTPUT_ROOT = OOS_ROOT / "linear_return_correction"
HORIZON = 24
TOP_N = 7
EXPOSURE = 0.45
ROUND_TRIP_COST = 2.0 * (0.001 + 4.0 / 10_000.0)
COMPLETED_ENTRY_END = pd.Timestamp("2026-06-30T00:00:00Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profit_factor(values: pd.Series) -> float:
    positive = float(values.clip(lower=0.0).sum())
    negative = float(-values.clip(upper=0.0).sum())
    return positive / negative if negative > 0.0 else float("inf")


def side_metrics(values: pd.Series) -> dict[str, float | int]:
    metrics = return_metrics(values, HORIZON)
    return {
        **metrics,
        "decision_count": int(len(values)),
        "win_rate": float(values.gt(0.0).mean()),
        "profit_factor": profit_factor(values),
        "worst_decision_return": float(values.min()),
    }


def corrected_frame() -> tuple[pd.DataFrame, dict[str, Any]]:
    columns = [
        "ts",
        "symbol",
        "score",
        "liquidity_rank",
        "avg_daily_quote_volume_7d",
        "fold_id",
        "label_funding_sum_24h",
        "label_long_net_24h",
        "label_short_net_24h",
        "label_gross_return_24h",
        "label_long_relative_24h",
    ]
    frame = pd.read_parquet(PREDICTION_PATH, columns=columns)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    gross = frame["label_gross_return_24h"]
    funding = frame["label_funding_sum_24h"]
    corrected_short = -gross - ROUND_TRIP_COST + funding
    reconstructed_bug = (
        1.0 / (1.0 + gross) - 1.0 - ROUND_TRIP_COST + funding
    )
    finite = np.isfinite(frame["label_short_net_24h"]) & np.isfinite(
        reconstructed_bug
    )
    max_saved_bug_delta = float(
        np.max(
            np.abs(
                frame.loc[finite, "label_short_net_24h"]
                - reconstructed_bug.loc[finite]
            )
        )
    )
    if max_saved_bug_delta > 1e-10:
        raise RuntimeError(
            "saved OOS labels do not match the documented reciprocal short-return bug"
        )
    frame["label_short_net_24h"] = corrected_short
    return frame, {
        "saved_label_matches_reciprocal_bug": True,
        "max_saved_bug_reconstruction_delta": max_saved_bug_delta,
        "correct_formula": "1 - exit_open / entry_open - round_trip_cost + funding_sum",
        "incorrect_formula": "entry_open / exit_open - 1 - round_trip_cost + funding_sum",
    }


def decile_diagnostic(frame: pd.DataFrame) -> list[dict[str, float | int]]:
    complete = frame.loc[frame["ts"] < COMPLETED_ENTRY_END].copy()
    complete["score_decile"] = complete.groupby("ts")["score"].transform(
        lambda values: pd.qcut(values.rank(method="first"), 10, labels=False)
    )
    grouped = complete.groupby("score_decile", sort=True).agg(
        rows=("symbol", "size"),
        mean_long_relative=("label_long_relative_24h", "mean"),
        mean_long_net=("label_long_net_24h", "mean"),
        mean_short_net=("label_short_net_24h", "mean"),
    )
    return grouped.reset_index().to_dict(orient="records")


def main() -> None:
    frame, formula_audit = corrected_frame()
    scored = add_cross_sectional_score_state(frame)
    complete = scored.loc[scored["ts"] < COMPLETED_ENTRY_END].copy()
    decisions, legs = build_policy(
        complete,
        horizon=HORIZON,
        account_mode="long_short",
        top_n=TOP_N,
    )
    corrected_metrics = evaluate_policy(
        decisions,
        legs,
        horizon=HORIZON,
        threshold=0.0,
        exposure=EXPOSURE,
        offset_utc_hours=0,
    )
    corrected_metrics.pop("missing_exit_trade_count", None)
    corrected_metrics["leg_return_le_minus_100_count"] = int(
        legs["trade_return"].le(-1.0).sum()
    )

    top, bottom = selection_frames(complete, HORIZON, TOP_N)
    top = top.loc[top["ts"].dt.hour == 0].copy()
    bottom = bottom.loc[bottom["ts"].dt.hour == 0].copy()
    side_exposure = EXPOSURE / 2.0
    long_returns = top.groupby("ts")["trade_return"].mean() * side_exposure
    short_returns = bottom.groupby("ts")["trade_return"].mean() * side_exposure
    combined = long_returns.add(short_returns, fill_value=0.0)
    expected = decisions.loc[decisions["ts"].dt.hour == 0].set_index("ts")[
        "portfolio_return"
    ] * EXPOSURE
    np.testing.assert_allclose(combined.loc[expected.index], expected, rtol=0.0, atol=1e-12)

    top["side"] = "long"
    bottom["side"] = "short"
    selected = pd.concat([top, bottom], ignore_index=True)
    selected["capital_weight"] = EXPOSURE / (2.0 * TOP_N)
    selected["weighted_return"] = (
        selected["trade_return"] * selected["capital_weight"]
    )
    selected_columns = [
        "ts",
        "symbol",
        "side",
        "score",
        "liquidity_rank",
        "avg_daily_quote_volume_7d",
        "trade_return",
        "capital_weight",
        "weighted_return",
    ]
    corrected_decisions = combined.rename("portfolio_return").reset_index()
    corrected_decisions["equity"] = (
        1.0 + corrected_decisions["portfolio_return"]
    ).cumprod()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    trade_path = OUTPUT_ROOT / "corrected_completed_trades.csv"
    decision_path = OUTPUT_ROOT / "corrected_portfolio_decisions.csv"
    report_path = OUTPUT_ROOT / "correction_audit.json"
    selected[selected_columns].sort_values(["ts", "side", "score"]).to_csv(
        trade_path, index=False
    )
    corrected_decisions.to_csv(decision_path, index=False)

    result = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "version": "BIN-1H-CSLGBM-V1",
        "audit_type": "post_reveal_linear_usdm_short_return_correction",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "source_prediction_path": str(PREDICTION_PATH),
        "source_prediction_sha256": sha256(PREDICTION_PATH),
        "selection_unchanged": True,
        "model_scores_unchanged": True,
        "formula_audit": formula_audit,
        "corrected_metrics": corrected_metrics,
        "side_metrics": {
            "long_0_225x": side_metrics(long_returns),
            "short_0_225x": side_metrics(short_returns),
        },
        "score_deciles": decile_diagnostic(frame),
        "artifacts": {
            "corrected_trades": str(trade_path),
            "corrected_decisions": str(decision_path),
        },
        "conclusion": (
            "The originally revealed V1 performance is invalid because its short "
            "labels used inverse price returns instead of linear USD-M PnL."
        ),
    }
    report_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
