from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
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
DATE_TAG = "2026-07-13"
RANKING_CSV = ARTIFACT_DIR / "btc_1h_adaptive_regime_ranking_2026-07-02.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v4_structural_trials_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v4_structural_trials_rows_{DATE_TAG}.csv"
ROUTER_CSV = ARTIFACT_DIR / f"btc_1h_ar_v4_structural_router_rows_{DATE_TAG}.csv"

SEED = 2026071301
VWAP_SAMPLES = 2_500
WICK_SAMPLES = 2_500
MACD_SAMPLES = 2_000

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
MACD_SETS = ((8, 21, 5), (12, 26, 9), (21, 55, 9), (34, 89, 13))


def config_from_row(engine: Any, row: pd.Series, suffix: str) -> Any:
    values: dict[str, Any] = {}
    for field in fields(engine.StrategyConfig):
        value = row[f"cfg_{field.name}"]
        if field.name == "name":
            value = f"{row['name']}__{suffix}"
        elif field.name in INT_FIELDS:
            value = int(value)
        elif field.name in BOOL_FIELDS:
            if isinstance(value, str):
                value = value.lower() == "true"
            else:
                value = bool(value)
        values[field.name] = value
    return engine.StrategyConfig(**values)


def research_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, v1.TRAIN_START, v1.TRAIN_END),
        "validation": engine.metrics(trades, v1.TRAIN_END, v1.PREFIT_END),
        "prefit": engine.metrics(trades, v1.TRAIN_START, v1.PREFIT_END),
    }


def all_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        **research_metrics(engine, trades),
        "reused_holdout": engine.metrics(trades, v1.PREFIT_END, v1.FULL_END),
        "current_full": engine.metrics(trades, v1.TRAIN_START, v1.FULL_END),
    }


def flatten_metrics(
    prefix: str, metrics: dict[str, dict[str, float]]
) -> dict[str, float]:
    return {
        f"{prefix}_{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def count_added_prefit(engine: Any, combined: list[Any], baseline: list[Any]) -> int:
    combined_count = engine.metrics(
        combined, v1.TRAIN_START, v1.PREFIT_END
    )["trades"]
    baseline_count = engine.metrics(
        baseline, v1.TRAIN_START, v1.PREFIT_END
    )["trades"]
    return int(combined_count - baseline_count)


def entry_overlap(candidate: list[Any], reference: list[Any], tolerance: int = 3) -> float:
    if not candidate:
        return 0.0
    entries = [trade.entry_i for trade in reference]
    return sum(
        any(abs(trade.entry_i - entry_i) <= tolerance for entry_i in entries)
        for trade in candidate
    ) / len(candidate)


def marginal_score(
    metrics: dict[str, dict[str, float]],
    baseline: dict[str, dict[str, float]],
    *,
    overlap: float,
) -> float:
    validation_log = math.log(
        max(metrics["validation"]["final_equity"], 1e-9)
        / max(baseline["validation"]["final_equity"], 1e-9)
    )
    prefit_log = math.log(
        max(metrics["prefit"]["final_equity"], 1e-9)
        / max(baseline["prefit"]["final_equity"], 1e-9)
    )
    dd_delta = metrics["prefit"]["max_dd"] - baseline["prefit"]["max_dd"]
    win_delta = metrics["prefit"]["win_rate"] - baseline["prefit"]["win_rate"]
    return float(
        validation_log
        + 0.50 * prefit_log
        + 2.0 * dd_delta
        + 0.5 * win_delta
        - 0.25 * overlap
    )


def passes_gate(
    candidate: dict[str, dict[str, float]],
    combined: dict[str, dict[str, float]],
    baseline: dict[str, dict[str, float]],
    *,
    added_prefit: int,
    overlap: float,
    replacement: bool,
) -> bool:
    prefit_delta = (
        combined["prefit"]["total_return"] - baseline["prefit"]["total_return"]
    )
    validation_delta = (
        combined["validation"]["total_return"]
        - baseline["validation"]["total_return"]
    )
    trade_gate = True if replacement else added_prefit >= 8
    return bool(
        candidate["prefit"]["trades"] >= 25
        and candidate["validation"]["trades"] >= 10
        and candidate["train"]["total_return"] > 0
        and candidate["validation"]["total_return"] > 0
        and prefit_delta > 0
        and validation_delta >= 0
        and combined["prefit"]["max_dd"]
        >= baseline["prefit"]["max_dd"] - 0.02
        and combined["prefit"]["win_rate"]
        >= baseline["prefit"]["win_rate"] - 0.03
        and overlap < 0.40
        and trade_gate
    )


def dedup_key(cfg: Any) -> tuple[Any, ...]:
    return tuple(
        value
        for key, value in asdict(cfg).items()
        if key != "name"
    )


def base_templates(
    engine: Any, ranking: pd.DataFrame, style: str
) -> list[Any]:
    rows = ranking.loc[
        (ranking["kind"] == "single") & (ranking["styles"] == style)
    ].sort_values(
        ["prefit_score", "prefit_annual_multiple"],
        ascending=[False, False],
    )
    return [
        config_from_row(engine, row, f"{style.upper()}_TEMPLATE")
        for _, row in rows.iterrows()
    ]


def vwap_candidates(engine: Any, templates: list[Any], rng: random.Random) -> list[Any]:
    seen: set[tuple[Any, ...]] = set()
    candidates: list[Any] = []
    while len(candidates) < VWAP_SAMPLES:
        template = rng.choice(templates)
        cfg = replace(
            template,
            name=f"BTC_1H_AR_V4_VWAP_SHORT_{len(candidates):05d}",
            style="vwap_revert",
            side_mode="short",
            ema_htf=rng.choice((89, 144, 233, 377)),
            indicator_window=rng.choice((24, 48, 96, 168)),
            band_k=rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0)),
            min_adx=0.0,
            max_adx=rng.choice((24.0, 30.0, 36.0, 40.0, 45.0)),
            min_rvol=rng.choice((0.0, 0.6, 0.8, 1.0, 1.25)),
            min_atr_bps=rng.choice((0.0, 50.0, 75.0, 100.0)),
            max_atr_bps=10_000.0,
            min_dir_roc_bps=-10_000.0,
            max_dist_ema_bps=rng.choice((500.0, 750.0, 1000.0, 1500.0, 10_000.0)),
            htf_mode="none",
            require_macd_turn=False,
            require_body_dir=False,
            max_aligned_funding_bps=10_000.0,
            exit_kind="fixed",
            tp_atr=rng.choice((1.0, 1.5, 2.0, 2.5, 3.0, 4.0)),
            sl_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5)),
            max_hold_bars=rng.choice((24, 36, 48, 72, 96, 120)),
            cooldown_bars=0,
            entry_delay_bars=1,
            sizing_kind="fixed",
            fixed_leverage=1.0,
        )
        key = dedup_key(cfg)
        if key not in seen:
            seen.add(key)
            candidates.append(cfg)
    return candidates


def wick_candidates(engine: Any, templates: list[Any], rng: random.Random) -> list[Any]:
    seen: set[tuple[Any, ...]] = set()
    candidates: list[Any] = []
    while len(candidates) < WICK_SAMPLES:
        template = rng.choice(templates)
        min_adx = rng.choice((24.0, 28.0, 30.0, 32.0, 35.0, 36.0, 38.0))
        max_adx = rng.choice((40.0, 42.0, 45.0, 48.0, 50.0))
        if max_adx <= min_adx:
            continue
        cfg = replace(
            template,
            name=f"BTC_1H_AR_V4_WICK_TRANSITION_{len(candidates):05d}",
            style="wick_reject",
            side_mode="both",
            band_k=rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0)),
            threshold_low=rng.choice((0.15, 0.20, 0.25, 0.30, 0.35)),
            threshold_high=rng.choice((0.65, 0.70, 0.75, 0.80, 0.85)),
            min_adx=min_adx,
            max_adx=max_adx,
            min_rvol=rng.choice((0.0, 0.6, 0.8, 1.0, 1.25)),
            min_atr_bps=rng.choice((0.0, 50.0, 75.0, 100.0)),
            max_atr_bps=10_000.0,
            min_dir_roc_bps=-10_000.0,
            max_dist_ema_bps=10_000.0,
            htf_mode="none",
            require_macd_turn=False,
            require_body_dir=False,
            max_aligned_funding_bps=10_000.0,
            exit_kind="fixed",
            tp_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5)),
            sl_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0)),
            max_hold_bars=rng.choice((12, 18, 24, 36, 48, 72)),
            cooldown_bars=0,
            entry_delay_bars=1,
            sizing_kind="fixed",
            fixed_leverage=1.0,
        )
        key = dedup_key(cfg)
        if key not in seen:
            seen.add(key)
            candidates.append(cfg)
    return candidates


def macd_candidates(engine: Any, templates: list[Any], rng: random.Random) -> list[Any]:
    seen: set[tuple[Any, ...]] = set()
    candidates: list[Any] = []
    while len(candidates) < MACD_SAMPLES:
        template = rng.choice(templates)
        macd = rng.choice(MACD_SETS)
        cfg = replace(
            template,
            name=f"BTC_1H_AR_V4_MACD_REPLACE_{len(candidates):05d}",
            style="macd_flip",
            side_mode="both",
            ema_htf=rng.choice((55, 89, 144, 233, 377)),
            macd_fast=macd[0],
            macd_slow=macd[1],
            macd_signal=macd[2],
            min_adx=rng.choice((20.0, 24.0, 28.0, 32.0, 36.0, 40.0)),
            max_adx=rng.choice((45.0, 100.0)),
            min_rvol=rng.choice((0.0, 0.6, 0.8, 1.0, 1.25)),
            min_atr_bps=rng.choice((0.0, 50.0, 75.0, 100.0)),
            max_atr_bps=10_000.0,
            min_dir_roc_bps=-10_000.0,
            max_dist_ema_bps=10_000.0,
            htf_mode=rng.choice(("none", "h4")),
            require_macd_turn=False,
            require_body_dir=False,
            max_aligned_funding_bps=10_000.0,
            exit_kind="fixed",
            tp_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)),
            sl_atr=rng.choice((1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
            max_hold_bars=rng.choice((24, 36, 48, 72, 96, 120, 168)),
            cooldown_bars=0,
            entry_delay_bars=1,
            sizing_kind="fixed",
            fixed_leverage=2.4,
        )
        if cfg.max_adx <= cfg.min_adx:
            continue
        key = dedup_key(cfg)
        if key not in seen:
            seen.add(key)
            candidates.append(cfg)
    return candidates


def evaluate_stage(
    *,
    stage: str,
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    candidates: list[Any],
    v4_trades: list[Any],
    v4_cci: list[Any],
    v4_cci_priority: float,
    baseline_metrics: dict[str, dict[str, float]],
    replacement: bool,
) -> tuple[
    pd.DataFrame,
    Any,
    list[Any],
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
]:
    rows: list[dict[str, Any]] = []
    best_by_name: dict[
        str,
        tuple[
            Any,
            list[Any],
            dict[str, dict[str, float]],
            dict[str, dict[str, float]],
        ],
    ] = {}
    for cfg in candidates:
        candidate_trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, cfg
        )
        candidate_metrics = research_metrics(engine, candidate_trades)
        candidate_priority = tune.leg_score(candidate_metrics)
        if replacement:
            combined = engine.merge_trade_sets(
                candidate_trades,
                v4_cci,
                candidate_priority,
                v4_cci_priority,
            )
        else:
            combined = engine.merge_trade_sets(
                v4_trades,
                candidate_trades,
                1e9,
                candidate_priority,
            )
        combined_metrics = research_metrics(engine, combined)
        overlap = entry_overlap(candidate_trades, v4_trades)
        added_prefit = count_added_prefit(engine, combined, v4_trades)
        gate = passes_gate(
            candidate_metrics,
            combined_metrics,
            baseline_metrics,
            added_prefit=added_prefit,
            overlap=overlap,
            replacement=replacement,
        )
        score = marginal_score(
            combined_metrics,
            baseline_metrics,
            overlap=overlap,
        )
        row = {
            "stage": stage,
            "name": cfg.name,
            "style": cfg.style,
            "replacement": replacement,
            "passes_gate": gate,
            "score": score,
            "entry_overlap_v4_pm3h": overlap,
            "added_prefit_trades": added_prefit,
            "prefit_delta_return": (
                combined_metrics["prefit"]["total_return"]
                - baseline_metrics["prefit"]["total_return"]
            ),
            "validation_delta_return": (
                combined_metrics["validation"]["total_return"]
                - baseline_metrics["validation"]["total_return"]
            ),
            "prefit_delta_max_dd": (
                combined_metrics["prefit"]["max_dd"]
                - baseline_metrics["prefit"]["max_dd"]
            ),
            "prefit_delta_win_rate": (
                combined_metrics["prefit"]["win_rate"]
                - baseline_metrics["prefit"]["win_rate"]
            ),
            **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
            **flatten_metrics("candidate", candidate_metrics),
            **flatten_metrics("combined", combined_metrics),
        }
        rows.append(row)
        best_by_name[cfg.name] = (
            cfg,
            combined,
            candidate_metrics,
            combined_metrics,
        )

    result = pd.DataFrame(rows).sort_values(
        ["passes_gate", "score", "validation_delta_return", "prefit_delta_return"],
        ascending=[False, False, False, False],
    )
    winner_row = result.iloc[0]
    (
        winner_cfg,
        winner_trades,
        winner_candidate_metrics,
        winner_combined_metrics,
    ) = best_by_name[winner_row["name"]]
    return (
        result,
        winner_cfg,
        winner_trades,
        winner_candidate_metrics,
        winner_combined_metrics,
    )


def merge_many(
    trade_sets: list[tuple[list[Any], float]],
) -> list[Any]:
    tagged = [
        (trade, priority)
        for trades, priority in trade_sets
        for trade in trades
    ]
    tagged.sort(key=lambda item: (item[0].entry_i, -item[1], item[0].exit_i))
    selected: list[Any] = []
    blocked_until = -1
    for trade, _priority in tagged:
        if trade.entry_i <= blocked_until:
            continue
        selected.append(trade)
        blocked_until = trade.exit_i
    return selected


def filtered_by_adx(
    trades: list[Any],
    adx: np.ndarray,
    *,
    low: float | None = None,
    high: float | None = None,
) -> list[Any]:
    selected = []
    for trade in trades:
        value = adx[trade.signal_i]
        if not np.isfinite(value):
            continue
        if low is not None and value < low:
            continue
        if high is not None and value > high:
            continue
        selected.append(trade)
    return selected


def router_trials(
    *,
    engine: Any,
    frame: pd.DataFrame,
    baseline_metrics: dict[str, dict[str, float]],
    v4_keltner: list[Any],
    v4_cci: list[Any],
    priorities: tuple[float, float],
    vwap_result: tuple[Any, list[Any]] | None,
    wick_result: tuple[Any, list[Any]] | None,
) -> pd.DataFrame:
    if vwap_result is None and wick_result is None:
        return pd.DataFrame()
    adx = frame["adx14"].to_numpy("float64")
    rows: list[dict[str, Any]] = []
    for range_max in (30.0, 32.0, 35.0, 36.0, 38.0):
        for trend_min in (40.0, 42.0, 44.0, 46.0):
            if range_max >= trend_min:
                continue
            trade_sets: list[tuple[list[Any], float]] = [
                (
                    filtered_by_adx(v4_keltner, adx, low=trend_min),
                    priorities[0],
                ),
                (
                    filtered_by_adx(v4_cci, adx, high=range_max),
                    priorities[1],
                ),
            ]
            if vwap_result is not None:
                cfg, trades = vwap_result
                score = tune.leg_score(research_metrics(engine, trades))
                trade_sets.append(
                    (filtered_by_adx(trades, adx, high=range_max), score)
                )
            if wick_result is not None:
                cfg, trades = wick_result
                score = tune.leg_score(research_metrics(engine, trades))
                trade_sets.append(
                    (
                        filtered_by_adx(
                            trades,
                            adx,
                            low=range_max,
                            high=trend_min,
                        ),
                        score,
                    )
                )
            combined = merge_many(trade_sets)
            metrics = research_metrics(engine, combined)
            score = marginal_score(metrics, baseline_metrics, overlap=0.0)
            passes = bool(
                metrics["validation"]["total_return"]
                >= baseline_metrics["validation"]["total_return"]
                and metrics["prefit"]["total_return"]
                > baseline_metrics["prefit"]["total_return"]
                and metrics["prefit"]["max_dd"]
                >= baseline_metrics["prefit"]["max_dd"] - 0.02
                and metrics["prefit"]["win_rate"]
                >= baseline_metrics["prefit"]["win_rate"] - 0.03
            )
            rows.append(
                {
                    "range_max_adx": range_max,
                    "trend_min_adx": trend_min,
                    "passes_gate": passes,
                    "score": score,
                    "prefit_delta_return": (
                        metrics["prefit"]["total_return"]
                        - baseline_metrics["prefit"]["total_return"]
                    ),
                    "validation_delta_return": (
                        metrics["validation"]["total_return"]
                        - baseline_metrics["validation"]["total_return"]
                    ),
                    "prefit_delta_max_dd": (
                        metrics["prefit"]["max_dd"]
                        - baseline_metrics["prefit"]["max_dd"]
                    ),
                    "prefit_delta_win_rate": (
                        metrics["prefit"]["win_rate"]
                        - baseline_metrics["prefit"]["win_rate"]
                    ),
                    **flatten_metrics("combined", metrics),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["passes_gate", "score"],
        ascending=[False, False],
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    v4_trades, v4_keltner, v4_cci, priorities = v4.simulate_v4(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_research = research_metrics(engine, v4_trades)
    baseline_all = all_metrics(engine, v4_trades)
    ranking = pd.read_csv(RANKING_CSV)

    stages: list[
        tuple[
            str,
            pd.DataFrame,
            Any,
            list[Any],
            dict[str, dict[str, float]],
            dict[str, dict[str, float]],
        ]
    ] = []
    stage_specs = [
        (
            "vwap_short_add",
            vwap_candidates(
                engine, base_templates(engine, ranking, "vwap_revert"), rng
            ),
            False,
        ),
        (
            "wick_transition_add",
            wick_candidates(
                engine, base_templates(engine, ranking, "wick_reject"), rng
            ),
            False,
        ),
        (
            "macd_replace_keltner",
            macd_candidates(
                engine, base_templates(engine, ranking, "macd_flip"), rng
            ),
            True,
        ),
    ]

    for stage, candidates, replacement in stage_specs:
        (
            result,
            winner_cfg,
            winner_trades,
            winner_candidate_research,
            winner_combined_research,
        ) = evaluate_stage(
            stage=stage,
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            candidates=candidates,
            v4_trades=v4_trades,
            v4_cci=v4_cci,
            v4_cci_priority=priorities[1],
            baseline_metrics=baseline_research,
            replacement=replacement,
        )
        stages.append(
            (
                stage,
                result,
                winner_cfg,
                winner_trades,
                winner_candidate_research,
                winner_combined_research,
            )
        )

    rows_frame = pd.concat([item[1] for item in stages], ignore_index=True)
    rows_frame.to_csv(ROWS_CSV, index=False)

    stage_payloads: dict[str, Any] = {}
    passing_add_legs: dict[str, tuple[Any, list[Any]]] = {}
    for (
        stage,
        result,
        winner_cfg,
        winner_trades,
        winner_candidate_research,
        winner_combined_research,
    ) in stages:
        gate_passes = int(result["passes_gate"].sum())
        winner_all = all_metrics(engine, winner_trades)
        stage_payloads[stage] = {
            "evaluated": len(result),
            "gate_passes": gate_passes,
            "winner_passes_gate": bool(result.iloc[0]["passes_gate"]),
            "winner_config": asdict(winner_cfg),
            "winner_candidate_research_metrics": winner_candidate_research,
            "winner_combined_research_metrics": winner_combined_research,
            "winner_all_metrics": winner_all,
            "winner_row": result.iloc[0].to_dict(),
            "top_20": result.head(20).to_dict(orient="records"),
        }
        if (
            stage == "vwap_short_add"
            and bool(result.iloc[0]["passes_gate"])
        ):
            candidate_only = v1.simulate_component(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                winner_cfg,
            )
            passing_add_legs["vwap"] = (winner_cfg, candidate_only)
        if (
            stage == "wick_transition_add"
            and bool(result.iloc[0]["passes_gate"])
        ):
            candidate_only = v1.simulate_component(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                winner_cfg,
            )
            passing_add_legs["wick"] = (winner_cfg, candidate_only)

    router = router_trials(
        engine=engine,
        frame=frame,
        baseline_metrics=baseline_research,
        v4_keltner=v4_keltner,
        v4_cci=v4_cci,
        priorities=priorities,
        vwap_result=passing_add_legs.get("vwap"),
        wick_result=passing_add_legs.get("wick"),
    )
    if not router.empty:
        router.to_csv(ROUTER_CSV, index=False)

    router_payload: dict[str, Any]
    if router.empty:
        router_payload = {
            "status": "skipped_no_passing_add_leg",
            "evaluated": 0,
            "gate_passes": 0,
        }
    else:
        router_payload = {
            "status": "evaluated",
            "evaluated": len(router),
            "gate_passes": int(router["passes_gate"].sum()),
            "winner": router.iloc[0].to_dict(),
            "top_20": router.head(20).to_dict(orient="records"),
        }

    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "base_version": "BTC-1H-Adaptive-Regime-V4",
        "status": "structural_trials_complete_not_live_ready",
        "date": DATE_TAG,
        "selection_protocol": (
            "train/validation/prefit only; reused holdout revealed after stage winner "
            "selection; add legs fixed at 1x; MACD replacement fixed at V4 Keltner 2.4x"
        ),
        "sample_counts": {
            "vwap_short_add": VWAP_SAMPLES,
            "wick_transition_add": WICK_SAMPLES,
            "macd_replace_keltner": MACD_SAMPLES,
        },
        "baseline_metrics": baseline_all,
        "stages": stage_payloads,
        "router": router_payload,
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    summary_rows = []
    for stage, result, _cfg, _trades, _candidate_metrics, _combined_metrics in stages:
        winner = result.iloc[0]
        summary_rows.append(
            {
                "stage": stage,
                "evaluated": len(result),
                "gate_passes": int(result["passes_gate"].sum()),
                "winner_passes": bool(winner["passes_gate"]),
                "score": winner["score"],
                "prefit_delta_return": winner["prefit_delta_return"],
                "validation_delta_return": winner["validation_delta_return"],
                "prefit_delta_max_dd": winner["prefit_delta_max_dd"],
                "prefit_delta_win_rate": winner["prefit_delta_win_rate"],
            }
        )
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print(json.dumps({"router": router_payload}, indent=2, default=str))


if __name__ == "__main__":
    main()
