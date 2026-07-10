from __future__ import annotations

import json
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v4 as v4  # noqa: E402
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATE_TAG = "2026-07-10"
RANKING_CSV = ARTIFACT_DIR / "btc_1h_adaptive_regime_ranking_2026-07-02.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v4_new_leg_increment_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v4_new_leg_increment_rows_{DATE_TAG}.csv"

CANDIDATE_STYLES = (
    "ema_pullback",
    "macd_flip",
    "wick_reject",
    "squeeze_release",
    "di_cross",
    "vwap_revert",
)

INT_FIELDS = {
    "ema_fast",
    "ema_slow",
    "ema_htf",
    "indicator_window",
    "roc_window",
    "macd_fast",
    "macd_slow",
    "macd_signal",
    "max_hold_bars",
    "cooldown_bars",
    "entry_delay_bars",
}
BOOL_FIELDS = {"require_macd_turn", "require_body_dir"}


def config_from_row(engine: Any, row: pd.Series, suffix: str) -> Any:
    values: dict[str, Any] = {}
    for field in fields(engine.StrategyConfig):
        value = row[f"cfg_{field.name}"]
        if field.name == "name":
            value = f"{row['name']}__{suffix}"
        elif field.name in INT_FIELDS:
            value = int(value)
        elif field.name in BOOL_FIELDS:
            value = bool(value)
        values[field.name] = value
    return engine.StrategyConfig(**values)


def window_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, v1.TRAIN_START, v1.TRAIN_END),
        "validation": engine.metrics(trades, v1.TRAIN_END, v1.PREFIT_END),
        "prefit": engine.metrics(trades, v1.TRAIN_START, v1.PREFIT_END),
        "reused_holdout": engine.metrics(trades, v1.PREFIT_END, v1.FULL_END),
        "current_full": engine.metrics(trades, v1.TRAIN_START, v1.FULL_END),
    }


def flatten(prefix: str, metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{prefix}_{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def entry_overlap(candidate: list[Any], reference: list[Any], tolerance: int) -> float:
    if not candidate:
        return 0.0
    reference_entries = [trade.entry_i for trade in reference]
    overlaps = sum(
        any(abs(trade.entry_i - entry_i) <= tolerance for entry_i in reference_entries)
        for trade in candidate
    )
    return overlaps / len(candidate)


def blocked_by(reference: list[Any], candidate: list[Any]) -> int:
    return sum(
        any(
            ref.entry_i <= trade.entry_i <= ref.exit_i
            for ref in reference
        )
        for trade in candidate
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    v4_trades, v4_keltner, v4_cci, _priorities = v4.simulate_v4(
        engine, frame, funding_times, funding_cumulative
    )
    v4_metrics = window_metrics(engine, v4_trades)

    ranking = pd.read_csv(RANKING_CSV)
    singles = ranking.loc[
        (ranking["kind"] == "single")
        & ranking["styles"].isin(CANDIDATE_STYLES)
    ].copy()
    selected_rows = (
        singles.sort_values(
            ["styles", "prefit_score", "prefit_annual_multiple"],
            ascending=[True, False, False],
        )
        .groupby("styles", as_index=False)
        .head(1)
    )

    rows: list[dict[str, Any]] = []
    for _, source_row in selected_rows.iterrows():
        original_cfg = config_from_row(engine, source_row, "ORIGINAL")
        normalized_cfg = replace(
            original_cfg,
            name=f"{source_row['name']}__FIXED_1X",
            sizing_kind="fixed",
            fixed_leverage=1.0,
        )
        for variant, cfg in (("original", original_cfg), ("fixed_1x", normalized_cfg)):
            candidate_trades = v1.simulate_component(
                engine, frame, funding_times, funding_cumulative, cfg
            )
            candidate_score = tune.leg_score(
                tune.prefit_metrics(engine, candidate_trades)
            )
            merged = engine.merge_trade_sets(
                v4_trades,
                candidate_trades,
                left_priority=1e9,
                right_priority=candidate_score,
            )
            added = len(merged) - len(v4_trades)
            blocked = blocked_by(v4_trades, candidate_trades)
            candidate_metrics = window_metrics(engine, candidate_trades)
            merged_metrics = window_metrics(engine, merged)
            rows.append(
                {
                    "style": cfg.style,
                    "source_config": source_row["name"],
                    "variant": variant,
                    "candidate_score": candidate_score,
                    "candidate_total_trades": len(candidate_trades),
                    "candidate_prefit_trades": int(
                        candidate_metrics["prefit"]["trades"]
                    ),
                    "candidate_reused_holdout_trades": int(
                        candidate_metrics["reused_holdout"]["trades"]
                    ),
                    "exact_entry_overlap_v4": entry_overlap(
                        candidate_trades, v4_trades, 0
                    ),
                    "entry_overlap_v4_pm3h": entry_overlap(
                        candidate_trades, v4_trades, 3
                    ),
                    "entry_overlap_keltner_pm3h": entry_overlap(
                        candidate_trades, v4_keltner, 3
                    ),
                    "entry_overlap_cci_pm3h": entry_overlap(
                        candidate_trades, v4_cci, 3
                    ),
                    "blocked_by_v4": blocked,
                    "blocked_by_v4_rate": (
                        blocked / len(candidate_trades) if candidate_trades else 0.0
                    ),
                    "added_prefit_trades_after_v4": int(
                        merged_metrics["prefit"]["trades"]
                        - v4_metrics["prefit"]["trades"]
                    ),
                    "added_full_trades_after_v4": added,
                    "prefit_delta_return": (
                        merged_metrics["prefit"]["total_return"]
                        - v4_metrics["prefit"]["total_return"]
                    ),
                    "prefit_delta_annual_multiple": (
                        merged_metrics["prefit"]["annual_multiple"]
                        - v4_metrics["prefit"]["annual_multiple"]
                    ),
                    "prefit_delta_max_dd": (
                        merged_metrics["prefit"]["max_dd"]
                        - v4_metrics["prefit"]["max_dd"]
                    ),
                    "validation_delta_return": (
                        merged_metrics["validation"]["total_return"]
                        - v4_metrics["validation"]["total_return"]
                    ),
                    "reused_holdout_delta_return": (
                        merged_metrics["reused_holdout"]["total_return"]
                        - v4_metrics["reused_holdout"]["total_return"]
                    ),
                    **flatten("candidate", candidate_metrics),
                    **flatten("merged", merged_metrics),
                }
            )

    rows_frame = pd.DataFrame(rows).sort_values(
        ["variant", "prefit_delta_return"],
        ascending=[True, False],
    )
    rows_frame.to_csv(ROWS_CSV, index=False)
    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "base_version": "BTC-1H-Adaptive-Regime-V4",
        "status": "diagnostic_incremental_leg_audit_not_live_ready",
        "date": DATE_TAG,
        "selection": (
            "top retained single per candidate style by original prefit score; "
            "reused holdout not used"
        ),
        "merge_contract": (
            "V4 frozen trades have priority; candidate fills only unoccupied slots"
        ),
        "candidate_styles": list(CANDIDATE_STYLES),
        "v4_metrics": v4_metrics,
        "rows": rows_frame.to_dict(orient="records"),
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        rows_frame[
            [
                "style",
                "variant",
                "candidate_prefit_trades",
                "entry_overlap_v4_pm3h",
                "blocked_by_v4_rate",
                "added_prefit_trades_after_v4",
                "prefit_delta_return",
                "validation_delta_return",
                "reused_holdout_delta_return",
                "prefit_delta_max_dd",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
