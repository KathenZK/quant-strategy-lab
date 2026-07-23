from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import random
from typing import Any

import numpy as np
import pandas as pd

import mmtf_engine as engine
import mmtf_v2


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
V1_PATH = ARTIFACT_DIR / "hype_15m_mmtf_v1_search_2026-07-22.json"

FAST_VALUES = (8, 12, 16, 24, 32, 48, 72, 96)
SLOW_VALUES = (144, 192, 288, 384, 672, 960)
ATR_VALUES = (14, 28, 48, 96)
ADX_VALUES = (18.0, 22.0, 26.0, 30.0, 35.0, 40.0)
RVOL_VALUES = (0.75, 1.0, 1.25, 1.5, 2.0)
KELTNER_VALUES = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
SL_VALUES = (2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0)
TP_VALUES = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
MAX_HOLD_VALUES = (12, 18, 24, 36, 48, 72, 96, 144, 192)
LEVERAGE_VALUES = (1.5, 2.0, 2.25, 2.5, 2.75, 3.0)
TREND_EXIT_VALUES: tuple[int | None, ...] = (None, 8, 12, 16, 24, 32, 48, 72, 96)

_BOOK: engine.FeatureBook | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify HYPE 15m MMTF V2 clean equivalence and tune active slots."
    )
    parser.add_argument("--seed", type=int, default=2026072202)
    parser.add_argument("--risk-round", type=int, default=24_000)
    parser.add_argument("--joint-round", type=int, default=36_000)
    parser.add_argument("--parents", type=int, default=60)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--batch-size", type=int, default=80)
    return parser.parse_args()


def _init_worker() -> None:
    global _BOOK
    _BOOK = engine.build_book(include_locked_oos=False)


def _metric_columns(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_{key}": metrics[key]
        for key in (
            "annual_factor",
            "total_return",
            "max_drawdown",
            "win_rate",
            "trades",
            "profit_factor",
            "average_trade",
            "liquidated",
        )
    }


def _evaluate_batch(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _BOOK is None:
        raise RuntimeError("worker book not initialized")
    validation_start = _BOOK.terminal_ts - pd.Timedelta(days=90)
    output: list[dict[str, Any]] = []
    for payload in payloads:
        clean = mmtf_v2.clean_from_dict(payload)
        config = mmtf_v2.to_engine_config(clean)
        full = engine.run_backtest(_BOOK, config)
        validation = engine.run_backtest(_BOOK, config, start_ts=validation_start)
        row = asdict(clean)
        row.update(_metric_columns("prefit", full.metrics))
        row.update(_metric_columns("validation", validation.metrics))
        output.append(row)
    return output


def evaluate(
    configs: list[mmtf_v2.CleanConfig], *, workers: int, batch_size: int
) -> pd.DataFrame:
    payloads = [asdict(config) for config in configs]
    batches = [
        payloads[index : index + batch_size]
        for index in range(0, len(payloads), batch_size)
    ]
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as executor:
        futures = [executor.submit(_evaluate_batch, batch) for batch in batches]
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.extend(future.result())
            if completed % max(1, len(futures) // 20) == 0:
                print(
                    f"evaluated {min(completed * batch_size, len(configs))}/{len(configs)}",
                    flush=True,
                )
    return pd.DataFrame(rows)


def _risk_candidate(rng: random.Random) -> mmtf_v2.CleanConfig:
    base = mmtf_v2.v2_baseline()
    return mmtf_v2.CleanConfig(
        ema_fast=base.ema_fast,
        ema_slow=base.ema_slow,
        atr_window=base.atr_window,
        adx_min=base.adx_min,
        rvol_min=base.rvol_min,
        keltner_atr=base.keltner_atr,
        sl_atr=rng.choice(SL_VALUES),
        tp_atr=rng.choice(TP_VALUES),
        max_hold_bars=rng.choice(MAX_HOLD_VALUES),
        leverage=rng.choice(LEVERAGE_VALUES),
        trend_exit_window=rng.choice(TREND_EXIT_VALUES),
    )


def _joint_candidate(
    parent: mmtf_v2.CleanConfig, rng: random.Random
) -> mmtf_v2.CleanConfig:
    fast = rng.choice(FAST_VALUES)
    slow = rng.choice(tuple(value for value in SLOW_VALUES if value > fast))
    return mmtf_v2.CleanConfig(
        ema_fast=fast,
        ema_slow=slow,
        atr_window=rng.choice(ATR_VALUES),
        adx_min=rng.choice(ADX_VALUES),
        rvol_min=rng.choice(RVOL_VALUES),
        keltner_atr=rng.choice(KELTNER_VALUES),
        sl_atr=rng.choice((parent.sl_atr, rng.choice(SL_VALUES))),
        tp_atr=rng.choice((parent.tp_atr, rng.choice(TP_VALUES))),
        max_hold_bars=rng.choice((parent.max_hold_bars, rng.choice(MAX_HOLD_VALUES))),
        leverage=rng.choice((parent.leverage, rng.choice(LEVERAGE_VALUES))),
        trend_exit_window=rng.choice(
            (parent.trend_exit_window, rng.choice(TREND_EXIT_VALUES))
        ),
    )


def _unique(
    configs: list[mmtf_v2.CleanConfig], limit: int
) -> list[mmtf_v2.CleanConfig]:
    seen: set[tuple[Any, ...]] = set()
    output: list[mmtf_v2.CleanConfig] = []
    for config in configs:
        key = tuple(asdict(config).values())
        if key in seen:
            continue
        seen.add(key)
        output.append(config)
        if len(output) >= limit:
            break
    return output


def _add_scores(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["prefit_target_pass"] = (
        (result.prefit_annual_factor >= 20.0)
        & (result.prefit_win_rate >= 0.80)
        & (result.prefit_max_drawdown < 0.20)
        & (result.prefit_trades >= 100)
        & (~result.prefit_liquidated)
    )
    result["validation_proxy_pass"] = (
        (result.validation_annual_factor >= 20.0)
        & (result.validation_win_rate >= 0.80)
        & (result.validation_max_drawdown < 0.20)
        & (result.validation_trades >= 20)
        & (~result.validation_liquidated)
    )
    result["joint_pass"] = result.prefit_target_pass & result.validation_proxy_pass
    result["target_gap"] = (
        (20.0 / result.prefit_annual_factor.clip(lower=1e-12))
        .clip(lower=1.0)
        .map(np.log)
        + 10.0 * (0.80 - result.prefit_win_rate).clip(lower=0.0)
        + 12.0 * (result.prefit_max_drawdown - 0.20).clip(lower=0.0)
        + (100 - result.prefit_trades).clip(lower=0) / 40.0
        + 0.75
        * (
            (20.0 / result.validation_annual_factor.clip(lower=1e-12))
            .clip(lower=1.0)
            .map(np.log)
            + 10.0 * (0.80 - result.validation_win_rate).clip(lower=0.0)
            + 10.0 * (result.validation_max_drawdown - 0.20).clip(lower=0.0)
            + (20 - result.validation_trades).clip(lower=0) / 10.0
        )
    )
    result["balanced_score"] = (
        result.prefit_annual_factor.clip(lower=1e-12).map(np.log)
        + 0.75 * result.validation_annual_factor.clip(lower=1e-12).map(np.log)
        + 4.0 * result.prefit_win_rate
        + 3.0 * result.validation_win_rate
        - 9.0 * result.prefit_max_drawdown
        - 6.0 * result.validation_max_drawdown
        + 0.04 * result.prefit_trades.clip(upper=150)
    )
    return result


def _row_config(row: pd.Series) -> mmtf_v2.CleanConfig:
    return mmtf_v2.clean_from_dict(row.to_dict())


def _rolling_audit(
    book: engine.FeatureBook, clean: mmtf_v2.CleanConfig
) -> dict[str, Any]:
    config = mmtf_v2.to_engine_config(clean)
    starts = pd.date_range(
        book.source_start + pd.Timedelta(days=90),
        book.terminal_ts - pd.Timedelta(days=30),
        freq="15D",
    )
    folds: list[dict[str, Any]] = []
    for start in starts:
        end = min(start + pd.Timedelta(days=30), book.terminal_ts)
        metrics = engine.run_backtest(book, config, start_ts=start, end_ts=end).metrics
        folds.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "return": metrics["total_return"],
                "annual_factor": metrics["annual_factor"],
                "max_drawdown": metrics["max_drawdown"],
                "win_rate": metrics["win_rate"],
                "trades": metrics["trades"],
            }
        )
    returns = np.asarray([fold["return"] for fold in folds])
    trades = np.asarray([fold["trades"] for fold in folds])
    return {
        "folds": folds,
        "fold_count": len(folds),
        "positive_fraction": float((returns > 0.0).mean()) if len(returns) else 0.0,
        "zero_trade_folds": int((trades == 0).sum()),
        "median_trades": float(np.median(trades)) if len(trades) else 0.0,
        "total_fold_trades": int(trades.sum()),
        "median_return": float(np.median(returns)) if len(returns) else 0.0,
        "worst_return": float(returns.min()) if len(returns) else 0.0,
        "median_drawdown": float(
            np.median([fold["max_drawdown"] for fold in folds])
        ) if folds else 0.0,
    }


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    book = engine.build_book(include_locked_oos=False)
    v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
    if v1["locked_oos_accessed"]:
        raise RuntimeError("V1 freeze unexpectedly accessed locked OOS")
    v1_config = engine.config_from_dict(v1["config"])
    v1_result = engine.run_backtest(book, v1_config, detailed=True)

    v2 = mmtf_v2.v2_baseline()
    v2_engine = mmtf_v2.to_engine_config(v2)
    v2_result = engine.run_backtest(book, v2_engine, detailed=True)
    if engine.trade_signature(v1_result) != engine.trade_signature(v2_result):
        raise RuntimeError("V2 clean baseline is not path-equal to V1")

    risk_pool = _unique(
        [v2] + [_risk_candidate(rng) for _ in range(args.risk_round * 5)],
        args.risk_round,
    )
    print(f"risk round configs: {len(risk_pool)}", flush=True)
    risk_frame = _add_scores(
        evaluate(risk_pool, workers=args.workers, batch_size=args.batch_size)
    )
    parent_rows = risk_frame.sort_values(
        ["joint_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    ).head(args.parents)
    parents = [_row_config(row) for _, row in parent_rows.iterrows()]

    joint_candidates = [
        _joint_candidate(rng.choice(parents), rng)
        for _ in range(args.joint_round * 4)
    ]
    joint_pool = _unique(joint_candidates, args.joint_round)
    print(f"joint round configs: {len(joint_pool)}", flush=True)
    joint_frame = _add_scores(
        evaluate(joint_pool, workers=args.workers, batch_size=args.batch_size)
    )
    combined = pd.concat([risk_frame, joint_frame], ignore_index=True)

    eligible = combined.loc[
        (combined.prefit_trades >= 100)
        & (combined.validation_trades >= 20)
        & (combined.prefit_max_drawdown < 0.35)
        & (~combined.prefit_liquidated)
        & (~combined.validation_liquidated)
    ]
    if eligible.empty:
        eligible = combined
    audit_rows = eligible.sort_values(
        ["joint_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    ).head(240)
    audited: list[dict[str, Any]] = []
    for _, row in audit_rows.iterrows():
        clean = _row_config(row)
        rolling = _rolling_audit(book, clean)
        record = row.to_dict()
        record.update(
            {
                "rolling_positive_fraction": rolling["positive_fraction"],
                "rolling_zero_trade_folds": rolling["zero_trade_folds"],
                "rolling_median_trades": rolling["median_trades"],
                "rolling_median_return": rolling["median_return"],
                "rolling_worst_return": rolling["worst_return"],
                "rolling_median_drawdown": rolling["median_drawdown"],
            }
        )
        audited.append(record)
    audited_frame = pd.DataFrame(audited)
    audited_frame["audit_score"] = (
        audited_frame.target_gap
        + 2.0 * (0.65 - audited_frame.rolling_positive_fraction).clip(lower=0.0)
        + 2.0 * (-audited_frame.rolling_median_return).clip(lower=0.0)
        + audited_frame.rolling_zero_trade_folds / 10.0
    )
    audited_frame["hard_shape_pass"] = (
        (audited_frame.prefit_win_rate >= 0.80)
        & (audited_frame.prefit_max_drawdown < 0.20)
        & (audited_frame.prefit_trades >= 100)
        & (audited_frame.validation_win_rate >= 0.80)
        & (audited_frame.validation_max_drawdown < 0.20)
        & (audited_frame.validation_trades >= 20)
    )
    shape_pool = audited_frame.loc[audited_frame.hard_shape_pass]
    if shape_pool.empty:
        shape_pool = audited_frame
    final_row = shape_pool.sort_values(
        ["joint_pass", "audit_score", "balanced_score"],
        ascending=[False, True, False],
    ).iloc[0]
    final_clean = _row_config(final_row)
    final_config = mmtf_v2.to_engine_config(final_clean)
    final_prefit = engine.run_backtest(book, final_config, detailed=True)
    validation_start = book.terminal_ts - pd.Timedelta(days=90)
    final_validation = engine.run_backtest(
        book, final_config, start_ts=validation_start, detailed=True
    )
    rolling = _rolling_audit(book, final_clean)

    frontier = combined.sort_values(
        ["joint_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    ).head(4_000)
    frontier.to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v2_clean_tune_frontier_2026-07-22.csv",
        index=False,
    )
    audited_frame.to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v2_clean_tune_rolling_2026-07-22.csv",
        index=False,
    )
    pd.DataFrame(final_prefit.trades).to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v3_tuned_prefit_trades_2026-07-22.csv",
        index=False,
    )
    pd.DataFrame(final_prefit.equity_path).to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v3_tuned_prefit_equity_2026-07-22.csv",
        index=False,
    )
    summary = {
        "family": "HYPE-15M-Multi-Mechanism-Trend-Following",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "locked_oos_accessed": False,
        "v2_clean_equivalence": {
            "v1_signature": engine.trade_signature(v1_result),
            "v2_signature": engine.trade_signature(v2_result),
            "exact_equal": True,
            "removed_slots": [
                "mechanism selector",
                "direction selector",
                "entry_window",
                "breakout_atr",
                "trailing activation/distance",
                "breakeven trigger",
                "cooldown",
                "disabled trend-exit window",
            ],
            "clean_config": asdict(v2),
            "clean_config_sha256": mmtf_v2.clean_sha256(v2),
        },
        "search_counts": {
            "risk_round": int(len(risk_frame)),
            "joint_round": int(len(joint_frame)),
            "total": int(len(combined)),
            "prefit_target_pass": int(combined.prefit_target_pass.sum()),
            "validation_proxy_pass": int(combined.validation_proxy_pass.sum()),
            "joint_pass": int(combined.joint_pass.sum()),
            "rolling_audited": int(len(audited_frame)),
        },
        "v3_tuned_freeze": {
            "config": asdict(final_clean),
            "clean_config_sha256": mmtf_v2.clean_sha256(final_clean),
            "engine_config_sha256": engine.config_sha256(final_config),
            "prefit": final_prefit.metrics,
            "validation_90d": final_validation.metrics,
            "rolling_audit": rolling,
        },
        "code_hashes": {
            "engine": hashlib.sha256(
                (Path(__file__).parent / "mmtf_engine.py").read_bytes()
            ).hexdigest(),
            "clean_adapter": hashlib.sha256(
                (Path(__file__).parent / "mmtf_v2.py").read_bytes()
            ).hexdigest(),
            "tune_script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    (
        ARTIFACT_DIR / "hype_15m_mmtf_v2_clean_tune_2026-07-22.json"
    ).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

