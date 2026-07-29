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
from typing import Any, Iterable

import numpy as np
import pandas as pd

import hto_engine as engine
import hto_v2


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
V1_PATH = ARTIFACT_DIR / "hype_d15_hto_v1_search_2026-07-29.json"
RUN_DATE = "2026-07-29"

MICRO_ADX_VALUES = (0.0, 10.0, 14.0, 18.0, 22.0, 26.0, 30.0, 35.0, 40.0)
RVOL_VALUES = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
BREAKOUT_VALUES = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75)
SL_VALUES = (0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
TP_VALUES = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)
TRAIL_ACTIVATION_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)
TRAIL_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)
BREAKEVEN_VALUES = (0.0, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
COOLDOWN_VALUES = (0, 1, 3, 6, 12, 24, 48, 72, 96, 144)
LEVERAGE_VALUES = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0)

_BOOK: engine.FeatureBook | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tune active HYPE-D15-HTO V2 clean parameters without OOS."
    )
    parser.add_argument("--seed", type=int, default=2026072902)
    parser.add_argument("--risk-round", type=int, default=40_000)
    parser.add_argument("--joint-round", type=int, default=80_000)
    parser.add_argument("--parents", type=int, default=100)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def _unique(
    stream: Iterable[hto_v2.CleanConfig], limit: int
) -> list[hto_v2.CleanConfig]:
    seen: set[tuple[Any, ...]] = set()
    output: list[hto_v2.CleanConfig] = []
    for config in stream:
        if config.key in seen:
            continue
        seen.add(config.key)
        output.append(config)
        if len(output) >= limit:
            break
    return output


def _risk_candidate(
    base: hto_v2.CleanConfig, rng: random.Random
) -> hto_v2.CleanConfig:
    payload = asdict(base)
    payload.update(
        sl_atr=rng.choice(SL_VALUES),
        tp_atr=rng.choice(TP_VALUES),
        trail_activation_atr=rng.choice(TRAIL_ACTIVATION_VALUES),
        trail_atr=rng.choice(TRAIL_VALUES),
        breakeven_trigger_atr=rng.choice(BREAKEVEN_VALUES),
        cooldown_bars=rng.choice(COOLDOWN_VALUES),
        leverage=rng.choice(LEVERAGE_VALUES),
    )
    return hto_v2.CleanConfig(**payload)


def _joint_candidate(
    parent: hto_v2.CleanConfig, rng: random.Random
) -> hto_v2.CleanConfig:
    daily_fast = rng.choice(engine.DAILY_EMA_SPANS[:-1])
    daily_slow = rng.choice(
        tuple(value for value in engine.DAILY_EMA_SPANS if value > daily_fast)
    )
    micro_fast = rng.choice(engine.MICRO_EMA_SPANS[:-1])
    micro_slow = rng.choice(
        tuple(value for value in engine.MICRO_EMA_SPANS if value > micro_fast)
    )
    return hto_v2.CleanConfig(
        direction=rng.choices((0, 1, 2), weights=(7, 2, 1), k=1)[0],
        daily_fast=daily_fast,
        daily_slow=daily_slow,
        daily_mom_window=rng.choice(engine.DAILY_MOM_WINDOWS),
        daily_dmi_window=rng.choice(engine.DAILY_ADX_WINDOWS),
        daily_channel_window=rng.choice(engine.DAILY_CHANNEL_WINDOWS),
        micro_fast=micro_fast,
        micro_slow=micro_slow,
        entry_window=rng.choice(engine.MICRO_WINDOWS),
        exit_window=rng.choice(engine.MICRO_WINDOWS),
        atr_window=rng.choice(engine.MICRO_ATR_WINDOWS),
        micro_adx_min=rng.choice(MICRO_ADX_VALUES),
        rvol_min=rng.choice(RVOL_VALUES),
        breakout_atr=rng.choice(BREAKOUT_VALUES),
        sl_atr=rng.choice((parent.sl_atr, rng.choice(SL_VALUES))),
        tp_atr=rng.choice((parent.tp_atr, rng.choice(TP_VALUES))),
        trail_activation_atr=rng.choice(
            (parent.trail_activation_atr, rng.choice(TRAIL_ACTIVATION_VALUES))
        ),
        trail_atr=rng.choice((parent.trail_atr, rng.choice(TRAIL_VALUES))),
        breakeven_trigger_atr=rng.choice(
            (parent.breakeven_trigger_atr, rng.choice(BREAKEVEN_VALUES))
        ),
        cooldown_bars=rng.choice(
            (parent.cooldown_bars, rng.choice(COOLDOWN_VALUES))
        ),
        leverage=rng.choice((parent.leverage, rng.choice(LEVERAGE_VALUES))),
    )


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
    validation_start = _BOOK.terminal_ts - pd.Timedelta(days=60)
    output: list[dict[str, Any]] = []
    for payload in payloads:
        clean = hto_v2.from_dict(payload)
        config = hto_v2.to_engine(clean)
        development = engine.run_backtest(
            _BOOK, config, end_ts=validation_start
        ).metrics
        validation = engine.run_backtest(
            _BOOK, config, start_ts=validation_start
        ).metrics
        row = asdict(clean)
        row.update(_metric_columns("development", development))
        row.update(_metric_columns("validation", validation))
        output.append(row)
    return output


def evaluate(
    configs: list[hto_v2.CleanConfig], *, workers: int, batch_size: int
) -> pd.DataFrame:
    payloads = [asdict(config) for config in configs]
    batches = [
        payloads[index : index + batch_size]
        for index in range(0, len(payloads), batch_size)
    ]
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as executor:
        futures = [executor.submit(_evaluate_batch, batch) for batch in batches]
        step = max(1, len(futures) // 20)
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.extend(future.result())
            if completed % step == 0 or completed == len(futures):
                print(
                    f"evaluated {min(completed * batch_size, len(configs))}/{len(configs)}",
                    flush=True,
                )
    return pd.DataFrame(rows)


def add_scores(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["development_target_pass"] = (
        (result.development_annual_factor >= 10.0)
        & (result.development_win_rate >= 0.50)
        & (result.development_max_drawdown < 0.20)
        & (result.development_trades >= 30)
        & (~result.development_liquidated)
    )
    result["validation_target_pass"] = (
        (result.validation_annual_factor >= 10.0)
        & (result.validation_win_rate >= 0.50)
        & (result.validation_max_drawdown < 0.20)
        & (result.validation_trades >= 8)
        & (~result.validation_liquidated)
    )
    result["joint_target_pass"] = (
        result.development_target_pass & result.validation_target_pass
    )
    result["target_gap"] = (
        np.log(
            (10.0 / result.development_annual_factor.clip(lower=1e-12)).clip(
                lower=1.0
            )
        )
        + 8 * (0.50 - result.development_win_rate).clip(lower=0)
        + 12 * (result.development_max_drawdown - 0.20).clip(lower=0)
        + (30 - result.development_trades).clip(lower=0) / 20
        + 0.8
        * (
            np.log(
                (10.0 / result.validation_annual_factor.clip(lower=1e-12)).clip(
                    lower=1.0
                )
            )
            + 8 * (0.50 - result.validation_win_rate).clip(lower=0)
            + 12 * (result.validation_max_drawdown - 0.20).clip(lower=0)
            + (8 - result.validation_trades).clip(lower=0) / 5
        )
    )
    result["balanced_score"] = (
        np.log(result.development_annual_factor.clip(lower=1e-12))
        + 0.8 * np.log(result.validation_annual_factor.clip(lower=1e-12))
        + 3 * result.development_win_rate
        + 2.5 * result.validation_win_rate
        - 8 * result.development_max_drawdown
        - 7 * result.validation_max_drawdown
        + 0.02 * result.development_trades.clip(upper=100)
        + 0.04 * result.validation_trades.clip(upper=30)
    )
    return result


def _row_config(row: pd.Series) -> hto_v2.CleanConfig:
    return hto_v2.from_dict(row.to_dict())


def _rolling_audit(
    book: engine.FeatureBook, clean: hto_v2.CleanConfig
) -> dict[str, Any]:
    config = hto_v2.to_engine(clean)
    starts = pd.date_range(
        book.source_start + pd.Timedelta(days=100),
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
    returns = np.asarray([fold["return"] for fold in folds], dtype="float64")
    trades = np.asarray([fold["trades"] for fold in folds], dtype="int64")
    return {
        "folds": folds,
        "positive_fraction": float((returns > 0).mean()) if len(returns) else 0.0,
        "median_return": float(np.median(returns)) if len(returns) else 0.0,
        "worst_return": float(returns.min()) if len(returns) else 0.0,
        "zero_trade_folds": int((trades == 0).sum()),
        "median_trades": float(np.median(trades)) if len(trades) else 0.0,
    }


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    v1_payload = json.loads(V1_PATH.read_text(encoding="utf-8"))
    if v1_payload["locked_oos_accessed"]:
        raise RuntimeError("V1 unexpectedly accessed locked OOS")
    v1_config = engine.config_from_dict(v1_payload["config"])
    v2 = hto_v2.from_v1(v1_config)
    book = engine.build_book(include_locked_oos=False)
    v1_result = engine.run_backtest(book, v1_config)
    v2_result = engine.run_backtest(book, hto_v2.to_engine(v2))
    if engine.trade_signature(v1_result) != engine.trade_signature(v2_result):
        raise RuntimeError("V2 clean baseline is not path-equal to V1")

    risk_pool = _unique(
        [v2]
        + [_risk_candidate(v2, rng) for _ in range(args.risk_round * 4)],
        args.risk_round,
    )
    print(f"risk round unique configs: {len(risk_pool)}", flush=True)
    risk_frame = add_scores(
        evaluate(risk_pool, workers=args.workers, batch_size=args.batch_size)
    )
    parent_rows = risk_frame.loc[
        (risk_frame.development_trades >= 20)
        & (risk_frame.validation_trades >= 4)
        & (~risk_frame.development_liquidated)
        & (~risk_frame.validation_liquidated)
    ].sort_values(
        ["joint_target_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    )
    if parent_rows.empty:
        parent_rows = risk_frame.sort_values(
            ["target_gap", "balanced_score"], ascending=[True, False]
        )
    parents = [
        _row_config(row) for _, row in parent_rows.head(args.parents).iterrows()
    ]
    joint_pool = _unique(
        (
            _joint_candidate(rng.choice(parents), rng)
            for _ in range(args.joint_round * 4)
        ),
        args.joint_round,
    )
    print(f"joint round unique configs: {len(joint_pool)}", flush=True)
    joint_frame = add_scores(
        evaluate(joint_pool, workers=args.workers, batch_size=args.batch_size)
    )
    combined = pd.concat([risk_frame, joint_frame], ignore_index=True)
    eligible = combined.loc[
        (combined.development_trades >= 30)
        & (combined.validation_trades >= 8)
        & (~combined.development_liquidated)
        & (~combined.validation_liquidated)
    ].sort_values(
        ["joint_target_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    )
    if eligible.empty:
        eligible = combined.sort_values(
            ["joint_target_pass", "target_gap", "balanced_score"],
            ascending=[False, True, False],
        )
    audited: list[dict[str, Any]] = []
    for _, row in eligible.head(240).iterrows():
        clean = _row_config(row)
        rolling = _rolling_audit(book, clean)
        record = row.to_dict()
        record.update(
            rolling_positive_fraction=rolling["positive_fraction"],
            rolling_median_return=rolling["median_return"],
            rolling_worst_return=rolling["worst_return"],
            rolling_zero_trade_folds=rolling["zero_trade_folds"],
            rolling_median_trades=rolling["median_trades"],
        )
        audited.append(record)
    audited_frame = pd.DataFrame(audited)
    audited_frame["audit_score"] = (
        audited_frame.target_gap
        + 2 * (0.60 - audited_frame.rolling_positive_fraction).clip(lower=0)
        + 2 * (-audited_frame.rolling_median_return).clip(lower=0)
        + audited_frame.rolling_zero_trade_folds / 10
    )
    final_row = audited_frame.sort_values(
        ["joint_target_pass", "audit_score", "balanced_score"],
        ascending=[False, True, False],
    ).iloc[0]
    final_clean = _row_config(final_row)
    final_config = hto_v2.to_engine(final_clean)
    validation_start = book.terminal_ts - pd.Timedelta(days=60)
    full = engine.run_backtest(book, final_config, detailed=True)
    development = engine.run_backtest(
        book, final_config, end_ts=validation_start, detailed=True
    )
    validation = engine.run_backtest(
        book, final_config, start_ts=validation_start, detailed=True
    )
    rolling = _rolling_audit(book, final_clean)
    summary = {
        "family": v1_payload["family"],
        "version": "HYPE-D15-HTO-V3",
        "role": "V2 clean-equivalent surface tuned without locked OOS",
        "selected_at_utc": datetime.now(UTC).isoformat(),
        "selection_data_end_exclusive": book.terminal_ts.isoformat(),
        "locked_oos_accessed": False,
        "v2_path_equal_to_v1": True,
        "v1_trade_signature": engine.trade_signature(v1_result),
        "v2_trade_signature": engine.trade_signature(v2_result),
        "clean_config": asdict(final_clean),
        "engine_config": engine.config_dict(final_config),
        "config_sha256": engine.config_sha256(final_config),
        "engine_sha256": hashlib.sha256(
            (Path(__file__).parent / "hto_engine.py").read_bytes()
        ).hexdigest(),
        "tune_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "metrics": {
            "prefit_full": full.metrics,
            "development": development.metrics,
            "internal_validation_60d": validation.metrics,
            "rolling_30d": rolling,
        },
        "selection_flags": {
            "development_target_pass": bool(final_row.development_target_pass),
            "validation_target_pass": bool(final_row.validation_target_pass),
            "joint_target_pass": bool(final_row.joint_target_pass),
        },
        "search_counts": {
            "risk_round": int(len(risk_frame)),
            "joint_round": int(len(joint_frame)),
            "total": int(len(combined)),
            "development_target_pass": int(combined.development_target_pass.sum()),
            "validation_target_pass": int(combined.validation_target_pass.sum()),
            "joint_target_pass": int(combined.joint_target_pass.sum()),
        },
    }
    prefix = f"hype_d15_hto_v3_tune_{RUN_DATE}"
    combined.sort_values(
        ["joint_target_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    ).head(8000).to_csv(ARTIFACT_DIR / f"{prefix}_frontier.csv", index=False)
    audited_frame.to_csv(ARTIFACT_DIR / f"{prefix}_rolling_audit.csv", index=False)
    pd.DataFrame(full.trades).to_csv(
        ARTIFACT_DIR / f"{prefix}_prefit_trades.csv", index=False
    )
    pd.DataFrame(full.equity_path).to_csv(
        ARTIFACT_DIR / f"{prefix}_prefit_equity.csv", index=False
    )
    (ARTIFACT_DIR / f"{prefix}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
