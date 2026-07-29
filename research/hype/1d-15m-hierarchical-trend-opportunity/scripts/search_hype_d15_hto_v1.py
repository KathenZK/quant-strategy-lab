from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable

import numpy as np
import pandas as pd

import hto_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RUN_DATE = "2026-07-29"

DAILY_ADX_VALUES = (0.0, 8.0, 12.0, 16.0, 20.0, 25.0, 30.0, 35.0)
DAILY_VOTE_VALUES = (1, 2, 3, 4)
MICRO_ADX_VALUES = (0.0, 10.0, 14.0, 18.0, 22.0, 26.0, 30.0, 35.0, 40.0)
RVOL_VALUES = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
RSI_TRIGGER_VALUES = (20.0, 25.0, 30.0, 35.0, 40.0, 45.0)
RSI_GAP_VALUES = (0.0, 5.0, 10.0, 15.0)
PULLBACK_VALUES = (-0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0)
BREAKOUT_VALUES = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5)
EXPANSION_VALUES = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
SL_VALUES = (0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)
TP_VALUES = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)
TRAIL_ACTIVATION_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)
TRAIL_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
BREAKEVEN_VALUES = (0.0, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
MAX_HOLD_VALUES = (12, 18, 24, 36, 48, 72, 96, 144, 192, 288, 384, 672)
COOLDOWN_VALUES = (0, 1, 3, 6, 12, 24, 48, 96)
LEVERAGE_VALUES = (1.0, 1.5, 2.0, 2.5, 3.0)

_BOOK: engine.FeatureBook | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broad prefit search for HYPE-D15-HTO original V1."
    )
    parser.add_argument("--seed", type=int, default=2026072901)
    parser.add_argument("--stage1", type=int, default=30_000)
    parser.add_argument("--stage2", type=int, default=20_000)
    parser.add_argument("--parents", type=int, default=80)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def _random_config(rng: random.Random) -> engine.Config:
    daily_fast = rng.choice(engine.DAILY_EMA_SPANS[:-1])
    daily_slow = rng.choice(
        tuple(value for value in engine.DAILY_EMA_SPANS if value > daily_fast)
    )
    micro_fast = rng.choice(engine.MICRO_EMA_SPANS[:-1])
    micro_slow = rng.choice(
        tuple(value for value in engine.MICRO_EMA_SPANS if value > micro_fast)
    )
    rsi_trigger = rng.choice(RSI_TRIGGER_VALUES)
    return engine.Config(
        daily_mode=rng.randrange(len(engine.DAILY_MODES)),
        direction=rng.choices((0, 1, 2), weights=(6, 2, 2), k=1)[0],
        daily_fast=daily_fast,
        daily_slow=daily_slow,
        daily_mom_window=rng.choice(engine.DAILY_MOM_WINDOWS),
        daily_adx_window=rng.choice(engine.DAILY_ADX_WINDOWS),
        daily_adx_min=rng.choice(DAILY_ADX_VALUES),
        daily_channel_window=rng.choice(engine.DAILY_CHANNEL_WINDOWS),
        daily_atr_window=rng.choice(engine.DAILY_ATR_WINDOWS),
        daily_supertrend_mult=rng.choice(engine.SUPERTREND_MULTIPLIERS),
        daily_vote_min=rng.choice(DAILY_VOTE_VALUES),
        entry_mode=rng.randrange(len(engine.ENTRY_MODES)),
        micro_fast=micro_fast,
        micro_slow=micro_slow,
        entry_window=rng.choice(engine.MICRO_WINDOWS),
        exit_window=rng.choice(engine.MICRO_WINDOWS),
        atr_window=rng.choice(engine.MICRO_ATR_WINDOWS),
        micro_adx_min=rng.choice(MICRO_ADX_VALUES),
        rvol_min=rng.choice(RVOL_VALUES),
        rsi_window=rng.choice(engine.RSI_WINDOWS),
        rsi_trigger=rsi_trigger,
        rsi_reclaim=min(50.0, rsi_trigger + rng.choice(RSI_GAP_VALUES)),
        pullback_atr=rng.choice(PULLBACK_VALUES),
        breakout_atr=rng.choice(BREAKOUT_VALUES),
        expansion_min=rng.choice(EXPANSION_VALUES),
        sl_atr=rng.choice(SL_VALUES),
        tp_atr=rng.choice(TP_VALUES),
        trail_activation_atr=rng.choice(TRAIL_ACTIVATION_VALUES),
        trail_atr=rng.choice(TRAIL_VALUES),
        breakeven_trigger_atr=rng.choice(BREAKEVEN_VALUES),
        max_hold_bars=rng.choice(MAX_HOLD_VALUES),
        cooldown_bars=rng.choice(COOLDOWN_VALUES),
        leverage=rng.choice(LEVERAGE_VALUES),
        exit_mode=rng.randrange(len(engine.EXIT_MODES)),
    )


def _neighbor(values: tuple[Any, ...], current: Any, rng: random.Random) -> Any:
    index = values.index(current)
    candidates = [index]
    if index:
        candidates.append(index - 1)
    if index + 1 < len(values):
        candidates.append(index + 1)
    return values[rng.choice(candidates)]


def _neighbor_config(parent: engine.Config, rng: random.Random) -> engine.Config:
    daily_fast = _neighbor(engine.DAILY_EMA_SPANS[:-1], parent.daily_fast, rng)
    daily_slow_values = tuple(
        value for value in engine.DAILY_EMA_SPANS if value > daily_fast
    )
    daily_slow = (
        parent.daily_slow
        if parent.daily_slow in daily_slow_values
        else daily_slow_values[0]
    )
    daily_slow = _neighbor(daily_slow_values, daily_slow, rng)
    micro_fast = _neighbor(engine.MICRO_EMA_SPANS[:-1], parent.micro_fast, rng)
    micro_slow_values = tuple(
        value for value in engine.MICRO_EMA_SPANS if value > micro_fast
    )
    micro_slow = (
        parent.micro_slow
        if parent.micro_slow in micro_slow_values
        else micro_slow_values[0]
    )
    micro_slow = _neighbor(micro_slow_values, micro_slow, rng)
    rsi_trigger = _neighbor(RSI_TRIGGER_VALUES, parent.rsi_trigger, rng)
    reclaim_values = tuple(
        sorted(
            {
                min(50.0, rsi_trigger + gap)
                for gap in RSI_GAP_VALUES
                if min(50.0, rsi_trigger + gap) >= rsi_trigger
            }
        )
    )
    current_reclaim = (
        parent.rsi_reclaim
        if parent.rsi_reclaim in reclaim_values
        else reclaim_values[0]
    )
    return engine.Config(
        daily_mode=parent.daily_mode if rng.random() < 0.85 else rng.randrange(6),
        direction=parent.direction if rng.random() < 0.9 else rng.randrange(3),
        daily_fast=daily_fast,
        daily_slow=daily_slow,
        daily_mom_window=_neighbor(
            engine.DAILY_MOM_WINDOWS, parent.daily_mom_window, rng
        ),
        daily_adx_window=_neighbor(
            engine.DAILY_ADX_WINDOWS, parent.daily_adx_window, rng
        ),
        daily_adx_min=_neighbor(DAILY_ADX_VALUES, parent.daily_adx_min, rng),
        daily_channel_window=_neighbor(
            engine.DAILY_CHANNEL_WINDOWS, parent.daily_channel_window, rng
        ),
        daily_atr_window=_neighbor(
            engine.DAILY_ATR_WINDOWS, parent.daily_atr_window, rng
        ),
        daily_supertrend_mult=_neighbor(
            engine.SUPERTREND_MULTIPLIERS, parent.daily_supertrend_mult, rng
        ),
        daily_vote_min=_neighbor(DAILY_VOTE_VALUES, parent.daily_vote_min, rng),
        entry_mode=parent.entry_mode if rng.random() < 0.85 else rng.randrange(6),
        micro_fast=micro_fast,
        micro_slow=micro_slow,
        entry_window=_neighbor(engine.MICRO_WINDOWS, parent.entry_window, rng),
        exit_window=_neighbor(engine.MICRO_WINDOWS, parent.exit_window, rng),
        atr_window=_neighbor(engine.MICRO_ATR_WINDOWS, parent.atr_window, rng),
        micro_adx_min=_neighbor(MICRO_ADX_VALUES, parent.micro_adx_min, rng),
        rvol_min=_neighbor(RVOL_VALUES, parent.rvol_min, rng),
        rsi_window=_neighbor(engine.RSI_WINDOWS, parent.rsi_window, rng),
        rsi_trigger=rsi_trigger,
        rsi_reclaim=_neighbor(reclaim_values, current_reclaim, rng),
        pullback_atr=_neighbor(PULLBACK_VALUES, parent.pullback_atr, rng),
        breakout_atr=_neighbor(BREAKOUT_VALUES, parent.breakout_atr, rng),
        expansion_min=_neighbor(EXPANSION_VALUES, parent.expansion_min, rng),
        sl_atr=_neighbor(SL_VALUES, parent.sl_atr, rng),
        tp_atr=_neighbor(TP_VALUES, parent.tp_atr, rng),
        trail_activation_atr=_neighbor(
            TRAIL_ACTIVATION_VALUES, parent.trail_activation_atr, rng
        ),
        trail_atr=_neighbor(TRAIL_VALUES, parent.trail_atr, rng),
        breakeven_trigger_atr=_neighbor(
            BREAKEVEN_VALUES, parent.breakeven_trigger_atr, rng
        ),
        max_hold_bars=_neighbor(MAX_HOLD_VALUES, parent.max_hold_bars, rng),
        cooldown_bars=_neighbor(COOLDOWN_VALUES, parent.cooldown_bars, rng),
        leverage=_neighbor(LEVERAGE_VALUES, parent.leverage, rng),
        exit_mode=parent.exit_mode if rng.random() < 0.85 else rng.randrange(5),
    )


def _unique(stream: Iterable[engine.Config], limit: int) -> list[engine.Config]:
    seen: set[tuple[Any, ...]] = set()
    output: list[engine.Config] = []
    for config in stream:
        if config.key in seen:
            continue
        seen.add(config.key)
        output.append(config)
        if len(output) >= limit:
            break
    return output


def _init_worker() -> None:
    global _BOOK
    _BOOK = engine.build_book(include_locked_oos=False)


def _metric_columns(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ending_equity",
        "total_return",
        "annual_factor",
        "max_drawdown",
        "win_rate",
        "trades",
        "profit_factor",
        "average_trade",
        "fee_return",
        "slippage_return",
        "funding_return",
        "liquidated",
    )
    return {f"{prefix}_{key}": metrics[key] for key in keys}


def _evaluate_batch(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _BOOK is None:
        raise RuntimeError("worker book not initialized")
    validation_start = _BOOK.terminal_ts - pd.Timedelta(days=60)
    output: list[dict[str, Any]] = []
    for payload in payloads:
        config = engine.config_from_dict(payload)
        development = engine.run_backtest(
            _BOOK, config, end_ts=validation_start
        ).metrics
        validation = engine.run_backtest(
            _BOOK, config, start_ts=validation_start
        ).metrics
        row = asdict(config)
        row.update(_metric_columns("development", development))
        row.update(_metric_columns("validation", validation))
        output.append(row)
    return output


def evaluate(
    configs: list[engine.Config], *, workers: int, batch_size: int
) -> pd.DataFrame:
    payloads = [asdict(config) for config in configs]
    batches = [
        payloads[index : index + batch_size]
        for index in range(0, len(payloads), batch_size)
    ]
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as executor:
        futures = [executor.submit(_evaluate_batch, batch) for batch in batches]
        progress_step = max(1, len(futures) // 20)
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.extend(future.result())
            if completed % progress_step == 0 or completed == len(futures):
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
        + 8.0 * (0.50 - result.development_win_rate).clip(lower=0)
        + 12.0 * (result.development_max_drawdown - 0.20).clip(lower=0)
        + (30 - result.development_trades).clip(lower=0) / 20.0
        + 0.8
        * (
            np.log(
                (10.0 / result.validation_annual_factor.clip(lower=1e-12)).clip(
                    lower=1.0
                )
            )
            + 8.0 * (0.50 - result.validation_win_rate).clip(lower=0)
            + 12.0 * (result.validation_max_drawdown - 0.20).clip(lower=0)
            + (8 - result.validation_trades).clip(lower=0) / 5.0
        )
    )
    result["balanced_score"] = (
        np.log(result.development_annual_factor.clip(lower=1e-12))
        + 0.8 * np.log(result.validation_annual_factor.clip(lower=1e-12))
        + 3.0 * result.development_win_rate
        + 2.5 * result.validation_win_rate
        - 8.0 * result.development_max_drawdown
        - 7.0 * result.validation_max_drawdown
        + 0.02 * result.development_trades.clip(upper=100)
        + 0.04 * result.validation_trades.clip(upper=30)
    )
    return result


def _row_config(row: pd.Series) -> engine.Config:
    return engine.config_from_dict(row.to_dict())


def _parent_rows(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    selected: set[int] = set()
    views = [
        ("target_gap", True),
        ("balanced_score", False),
        ("development_annual_factor", False),
        ("validation_annual_factor", False),
        ("development_max_drawdown", True),
        ("validation_max_drawdown", True),
    ]
    per_view = max(3, math.ceil(count / (len(views) * len(engine.ENTRY_MODES))))
    for entry_mode in engine.ENTRY_MODES:
        group = frame.loc[
            (frame.entry_mode == entry_mode)
            & (frame.development_trades >= 20)
            & (frame.validation_trades >= 4)
            & (~frame.development_liquidated)
            & (~frame.validation_liquidated)
        ]
        for column, ascending in views:
            selected.update(group.sort_values(column, ascending=ascending).head(per_view).index)
    ranked = frame.loc[sorted(selected)].sort_values(
        ["joint_target_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    )
    if len(ranked) < count:
        supplement = frame.sort_values(
            ["joint_target_pass", "target_gap", "balanced_score"],
            ascending=[False, True, False],
        )
        ranked = pd.concat([ranked, supplement]).loc[
            lambda item: ~item.index.duplicated(keep="first")
        ]
    return ranked.head(count)


def _rolling_audit(book: engine.FeatureBook, config: engine.Config) -> dict[str, Any]:
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
        "fold_count": len(folds),
        "positive_fraction": float((returns > 0).mean()) if len(returns) else 0.0,
        "median_return": float(np.median(returns)) if len(returns) else 0.0,
        "worst_return": float(returns.min()) if len(returns) else 0.0,
        "zero_trade_folds": int((trades == 0).sum()),
        "median_trades": float(np.median(trades)) if len(trades) else 0.0,
    }


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    stage1 = _unique(
        (_random_config(rng) for _ in range(args.stage1 * 3)), args.stage1
    )
    print(f"stage1 unique configs: {len(stage1)}", flush=True)
    stage1_frame = add_scores(
        evaluate(stage1, workers=args.workers, batch_size=args.batch_size)
    )
    parent_rows = _parent_rows(stage1_frame, args.parents)
    parents = [_row_config(row) for _, row in parent_rows.iterrows()]
    exclude = {config.key for config in stage1}

    def neighbors() -> Iterable[engine.Config]:
        attempts = 0
        while attempts < args.stage2 * 100:
            attempts += 1
            candidate = _neighbor_config(rng.choice(parents), rng)
            if candidate.key not in exclude:
                yield candidate

    stage2 = _unique(neighbors(), args.stage2)
    print(f"stage2 unique configs: {len(stage2)}", flush=True)
    stage2_frame = add_scores(
        evaluate(stage2, workers=args.workers, batch_size=args.batch_size)
    )
    combined = pd.concat([stage1_frame, stage2_frame], ignore_index=True)
    candidate_rows = combined.loc[
        (combined.development_trades >= 30)
        & (combined.validation_trades >= 8)
        & (~combined.development_liquidated)
        & (~combined.validation_liquidated)
    ].sort_values(
        ["joint_target_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    )
    if candidate_rows.empty:
        candidate_rows = combined.sort_values(
            ["joint_target_pass", "target_gap", "balanced_score"],
            ascending=[False, True, False],
        )

    book = engine.build_book(include_locked_oos=False)
    audited: list[dict[str, Any]] = []
    for _, row in candidate_rows.head(240).iterrows():
        config = _row_config(row)
        rolling = _rolling_audit(book, config)
        record = row.to_dict()
        record.update(
            {
                "rolling_positive_fraction": rolling["positive_fraction"],
                "rolling_median_return": rolling["median_return"],
                "rolling_worst_return": rolling["worst_return"],
                "rolling_zero_trade_folds": rolling["zero_trade_folds"],
                "rolling_median_trades": rolling["median_trades"],
            }
        )
        audited.append(record)
    audited_frame = pd.DataFrame(audited)
    audited_frame["audit_score"] = (
        audited_frame.target_gap
        + 2.0 * (0.60 - audited_frame.rolling_positive_fraction).clip(lower=0)
        + 2.0 * (-audited_frame.rolling_median_return).clip(lower=0)
        + audited_frame.rolling_zero_trade_folds / 10.0
    )
    v1_row = audited_frame.sort_values(
        ["joint_target_pass", "audit_score", "balanced_score"],
        ascending=[False, True, False],
    ).iloc[0]
    v1_config = _row_config(v1_row)
    validation_start = book.terminal_ts - pd.Timedelta(days=60)
    full = engine.run_backtest(book, v1_config, detailed=True)
    development = engine.run_backtest(
        book, v1_config, end_ts=validation_start, detailed=True
    )
    validation = engine.run_backtest(
        book, v1_config, start_ts=validation_start, detailed=True
    )
    rolling = _rolling_audit(book, v1_config)
    engine_hash = hashlib.sha256(
        (Path(__file__).parent / "hto_engine.py").read_bytes()
    ).hexdigest()
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary = {
        "family": "HYPE-1D-15M-Hierarchical-Trend-Opportunity",
        "version": "HYPE-D15-HTO-V1",
        "role": "original frozen baseline before ablation",
        "selected_at_utc": datetime.now(UTC).isoformat(),
        "selection_data_end_exclusive": book.terminal_ts.isoformat(),
        "locked_oos_accessed": False,
        "config": engine.config_dict(v1_config),
        "config_sha256": engine.config_sha256(v1_config),
        "engine_sha256": engine_hash,
        "search_script_sha256": script_hash,
        "metrics": {
            "prefit_full": full.metrics,
            "development": development.metrics,
            "internal_validation_60d": validation.metrics,
            "rolling_30d": rolling,
        },
        "selection_flags": {
            "development_target_pass": bool(v1_row.development_target_pass),
            "validation_target_pass": bool(v1_row.validation_target_pass),
            "joint_target_pass": bool(v1_row.joint_target_pass),
        },
        "search_counts": {
            "stage1": int(len(stage1_frame)),
            "stage2": int(len(stage2_frame)),
            "total": int(len(combined)),
            "development_target_pass": int(combined.development_target_pass.sum()),
            "validation_target_pass": int(combined.validation_target_pass.sum()),
            "joint_target_pass": int(combined.joint_target_pass.sum()),
        },
    }
    prefix = f"hype_d15_hto_v1_search_{RUN_DATE}"
    combined.sort_values(
        ["joint_target_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    ).head(5000).to_csv(ARTIFACT_DIR / f"{prefix}_frontier.csv", index=False)
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
