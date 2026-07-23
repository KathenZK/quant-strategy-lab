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

import pandas as pd

import mmtf_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1h-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

ADX_VALUES = (0.0, 10.0, 14.0, 18.0, 22.0, 26.0, 30.0, 35.0, 40.0)
RVOL_VALUES = (0.0, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
BREAKOUT_VALUES = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5)
EXPANSION_VALUES = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
SL_VALUES = (0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)
TP_VALUES = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
TRAIL_ACTIVATION_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
TRAIL_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
BREAKEVEN_VALUES = (0.0, 0.5, 0.75, 1.0, 1.5, 2.0)
MAX_HOLD_VALUES = (6, 9, 12, 18, 24, 36, 48, 72, 96, 120, 168)
COOLDOWN_VALUES = (0, 1, 3, 6, 12, 24, 48)
LEVERAGE_VALUES = (1.5, 2.0, 2.5, 3.0)

_WORKER_BOOK: engine.FeatureBook | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search the independent HYPE 1h MMTF V1 baseline.")
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--stage1", type=int, default=30_000)
    parser.add_argument("--stage2", type=int, default=18_000)
    parser.add_argument("--parents", type=int, default=30)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    return parser.parse_args()


def _random_config(rng: random.Random) -> engine.Config:
    fast = rng.choice(engine.EMA_SPANS[:-1])
    slow_choices = [value for value in engine.EMA_SPANS if value > fast]
    return engine.Config(
        mechanism=rng.randrange(len(engine.MECHANISMS)),
        direction=rng.choices((0, 1, 2), weights=(5, 2, 3), k=1)[0],
        entry_window=rng.choice(engine.ENTRY_WINDOWS),
        exit_window=rng.choice(engine.EXIT_WINDOWS),
        ema_fast=fast,
        ema_slow=rng.choice(slow_choices),
        atr_window=rng.choice(engine.ATR_WINDOWS),
        adx_min=rng.choice(ADX_VALUES),
        rvol_min=rng.choice(RVOL_VALUES),
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
        trend_exit=rng.choice((True, False)),
    )


def _neighbor(values: tuple[Any, ...], current: Any, rng: random.Random) -> Any:
    index = values.index(current)
    candidates = [index]
    if index > 0:
        candidates.append(index - 1)
    if index + 1 < len(values):
        candidates.append(index + 1)
    return values[rng.choice(candidates)]


def _neighbor_config(parent: engine.Config, rng: random.Random) -> engine.Config:
    fast = _neighbor(engine.EMA_SPANS[:-1], parent.ema_fast, rng)
    slow_values = tuple(value for value in engine.EMA_SPANS if value > fast)
    slow = parent.ema_slow if parent.ema_slow in slow_values else slow_values[0]
    slow = _neighbor(slow_values, slow, rng)
    return engine.Config(
        mechanism=parent.mechanism,
        direction=parent.direction if rng.random() < 0.85 else rng.randrange(3),
        entry_window=_neighbor(engine.ENTRY_WINDOWS, parent.entry_window, rng),
        exit_window=_neighbor(engine.EXIT_WINDOWS, parent.exit_window, rng),
        ema_fast=fast,
        ema_slow=slow,
        atr_window=_neighbor(engine.ATR_WINDOWS, parent.atr_window, rng),
        adx_min=_neighbor(ADX_VALUES, parent.adx_min, rng),
        rvol_min=_neighbor(RVOL_VALUES, parent.rvol_min, rng),
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
        trend_exit=parent.trend_exit if rng.random() < 0.8 else not parent.trend_exit,
    )


def _unique_configs(generator: Iterable[engine.Config], limit: int) -> list[engine.Config]:
    seen: set[tuple[Any, ...]] = set()
    output: list[engine.Config] = []
    for config in generator:
        if config.key in seen:
            continue
        seen.add(config.key)
        output.append(config)
        if len(output) >= limit:
            break
    return output


def _init_worker() -> None:
    global _WORKER_BOOK
    _WORKER_BOOK = engine.build_book(include_locked_oos=False)


def _prefix_metrics(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ending_equity", "total_return", "annual_factor", "max_drawdown",
        "win_rate", "trades", "profit_factor", "average_trade", "fee_return",
        "slippage_return", "funding_return", "liquidated",
    )
    return {f"{prefix}_{key}": metrics[key] for key in keys}


def _evaluate_batch(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _WORKER_BOOK is None:
        raise RuntimeError("worker book not initialized")
    book = _WORKER_BOOK
    validation_start = book.terminal_ts - pd.Timedelta(days=90)
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        config = engine.config_from_dict(payload)
        full = engine.run_backtest(book, config)
        validation = engine.run_backtest(book, config, start_ts=validation_start)
        row = asdict(config)
        row.update(_prefix_metrics("prefit", full.metrics))
        row.update(_prefix_metrics("validation", validation.metrics))
        rows.append(row)
    return rows


def _batches(items: list[engine.Config], size: int) -> list[list[dict[str, Any]]]:
    payloads = [asdict(item) for item in items]
    return [payloads[index : index + size] for index in range(0, len(payloads), size)]


def evaluate(configs: list[engine.Config], *, workers: int, batch_size: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    batches = _batches(configs, batch_size)
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as executor:
        futures = [executor.submit(_evaluate_batch, batch) for batch in batches]
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.extend(future.result())
            if completed % max(1, len(futures) // 20) == 0:
                print(f"evaluated {min(completed * batch_size, len(configs))}/{len(configs)}", flush=True)
    return pd.DataFrame(rows)


def _safe_log(value: float) -> float:
    return math.log(max(1e-12, min(float(value), 1e100)))


def add_selection_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["prefit_target_pass"] = (
        (result["prefit_annual_factor"] >= 20.0)
        & (result["prefit_win_rate"] >= 0.80)
        & (result["prefit_max_drawdown"] < 0.20)
        & (result["prefit_trades"] >= 45)
        & (~result["prefit_liquidated"])
    )
    result["validation_proxy_pass"] = (
        (result["validation_annual_factor"] >= 20.0)
        & (result["validation_win_rate"] >= 0.80)
        & (result["validation_max_drawdown"] < 0.20)
        & (result["validation_trades"] >= 10)
        & (~result["validation_liquidated"])
    )
    result["joint_selection_pass"] = result["prefit_target_pass"] & result["validation_proxy_pass"]
    prefit_gap = (
        (20.0 / result["prefit_annual_factor"].clip(lower=1e-12)).clip(lower=1.0).map(math.log)
        + 10.0 * (0.80 - result["prefit_win_rate"]).clip(lower=0.0)
        + 10.0 * (result["prefit_max_drawdown"] - 0.20).clip(lower=0.0)
        + (45 - result["prefit_trades"]).clip(lower=0) / 20.0
    )
    validation_gap = (
        (20.0 / result["validation_annual_factor"].clip(lower=1e-12)).clip(lower=1.0).map(math.log)
        + 10.0 * (0.80 - result["validation_win_rate"]).clip(lower=0.0)
        + 10.0 * (result["validation_max_drawdown"] - 0.20).clip(lower=0.0)
        + (10 - result["validation_trades"]).clip(lower=0) / 5.0
    )
    result["target_gap"] = prefit_gap + 0.75 * validation_gap
    result["balanced_score"] = (
        result["prefit_annual_factor"].map(_safe_log)
        + 0.75 * result["validation_annual_factor"].map(_safe_log)
        + 4.0 * result["prefit_win_rate"]
        + 3.0 * result["validation_win_rate"]
        - 8.0 * result["prefit_max_drawdown"]
        - 6.0 * result["validation_max_drawdown"]
        + 0.05 * result["prefit_trades"].clip(upper=120)
    )
    return result


def shortlist(frame: pd.DataFrame, per_view: int = 120) -> pd.DataFrame:
    eligible = frame.loc[
        (~frame["prefit_liquidated"])
        & (~frame["validation_liquidated"])
        & (frame["prefit_trades"] >= 35)
        & (frame["validation_trades"] >= 7)
        & (frame["prefit_max_drawdown"] < 0.60)
    ].copy()
    selected: set[int] = set()
    views = [
        ("target_gap", True),
        ("balanced_score", False),
        ("prefit_annual_factor", False),
        ("prefit_win_rate", False),
        ("prefit_max_drawdown", True),
        ("validation_annual_factor", False),
        ("validation_win_rate", False),
    ]
    for mechanism in sorted(eligible["mechanism"].unique()):
        group = eligible.loc[eligible["mechanism"] == mechanism]
        for column, ascending in views:
            selected.update(group.sort_values(column, ascending=ascending).head(per_view).index)
    return frame.loc[sorted(selected)].sort_values(
        ["joint_selection_pass", "target_gap", "balanced_score"],
        ascending=[False, True, False],
    )


def select_v1(frame: pd.DataFrame) -> pd.Series:
    joint = frame.loc[frame["joint_selection_pass"]]
    if not joint.empty:
        return joint.sort_values(
            ["target_gap", "validation_max_drawdown", "balanced_score"],
            ascending=[True, True, False],
        ).iloc[0]
    prefit_pass = frame.loc[frame["prefit_target_pass"]]
    if not prefit_pass.empty:
        return prefit_pass.sort_values(
            ["target_gap", "balanced_score"], ascending=[True, False]
        ).iloc[0]
    eligible = frame.loc[
        (frame["prefit_trades"] >= 45)
        & (frame["validation_trades"] >= 10)
        & (frame["prefit_max_drawdown"] < 0.35)
        & (~frame["prefit_liquidated"])
        & (~frame["validation_liquidated"])
    ]
    pool = eligible if not eligible.empty else frame
    return pool.sort_values(["target_gap", "balanced_score"], ascending=[True, False]).iloc[0]


def _row_to_config(row: pd.Series) -> engine.Config:
    return engine.config_from_dict(row.to_dict())


def _generate_neighborhood(
    parents: list[engine.Config], *, count: int, seed: int, exclude: set[tuple[Any, ...]]
) -> list[engine.Config]:
    rng = random.Random(seed)

    def stream() -> Iterable[engine.Config]:
        attempts = 0
        while attempts < count * 100:
            attempts += 1
            candidate = _neighbor_config(rng.choice(parents), rng)
            if candidate.key not in exclude:
                yield candidate

    return _unique_configs(stream(), count)


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    stage1 = _unique_configs((_random_config(rng) for _ in range(args.stage1 * 3)), args.stage1)
    print(f"stage1 unique configs: {len(stage1)}", flush=True)
    stage1_frame = add_selection_columns(
        evaluate(stage1, workers=args.workers, batch_size=args.batch_size)
    )
    stage1_short = shortlist(stage1_frame)
    if stage1_short.empty:
        stage1_short = stage1_frame.sort_values(
            ["target_gap", "balanced_score"], ascending=[True, False]
        ).head(max(args.parents, 20))
    parent_rows = stage1_short.head(args.parents)
    parents = [_row_to_config(row) for _, row in parent_rows.iterrows()]
    exclude = {config.key for config in stage1}
    stage2 = _generate_neighborhood(
        parents, count=args.stage2, seed=args.seed + 1, exclude=exclude
    )
    print(f"stage2 unique configs: {len(stage2)}", flush=True)
    stage2_frame = add_selection_columns(
        evaluate(stage2, workers=args.workers, batch_size=args.batch_size)
    )
    combined = pd.concat([stage1_frame, stage2_frame], ignore_index=True)
    frontier = shortlist(combined, per_view=160).reset_index(drop=True)
    v1_row = select_v1(combined)
    v1_config = _row_to_config(v1_row)

    book = engine.build_book(include_locked_oos=False)
    validation_start = book.terminal_ts - pd.Timedelta(days=90)
    v1_prefit = engine.run_backtest(book, v1_config, detailed=True)
    v1_validation = engine.run_backtest(
        book, v1_config, start_ts=validation_start, detailed=True
    )
    engine_hash = hashlib.sha256((Path(__file__).parent / "mmtf_engine.py").read_bytes()).hexdigest()
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    selected = {
        "family": "HYPE-1H-Multi-Mechanism-Trend-Following",
        "version_role": "V1 original baseline selection freeze",
        "selected_at_utc": datetime.now(UTC).isoformat(),
        "selection_data_end_exclusive": book.terminal_ts.isoformat(),
        "locked_oos_accessed": False,
        "config": engine.config_dict(v1_config),
        "config_sha256": engine.config_sha256(v1_config),
        "engine_sha256": engine_hash,
        "search_script_sha256": script_hash,
        "selection_metrics": {
            "prefit": v1_prefit.metrics,
            "internal_validation_90d": v1_validation.metrics,
        },
        "selection_flags": {
            "prefit_target_pass": bool(v1_row["prefit_target_pass"]),
            "validation_proxy_pass": bool(v1_row["validation_proxy_pass"]),
            "joint_selection_pass": bool(v1_row["joint_selection_pass"]),
        },
        "search_counts": {
            "stage1": int(len(stage1_frame)),
            "stage2": int(len(stage2_frame)),
            "total": int(len(combined)),
            "prefit_target_pass": int(combined["prefit_target_pass"].sum()),
            "validation_proxy_pass": int(combined["validation_proxy_pass"].sum()),
            "joint_selection_pass": int(combined["joint_selection_pass"].sum()),
            "frontier_rows": int(len(frontier)),
        },
    }
    prefix = f"hype_1h_mmtf_v1_search_{args.run_date}"
    frontier.to_csv(ARTIFACT_DIR / f"{prefix}_frontier.csv", index=False)
    pd.DataFrame(v1_prefit.trades).to_csv(
        ARTIFACT_DIR / f"{prefix}_prefit_trades.csv", index=False
    )
    pd.DataFrame(v1_prefit.equity_path).to_csv(
        ARTIFACT_DIR / f"{prefix}_prefit_equity.csv", index=False
    )
    (ARTIFACT_DIR / f"{prefix}.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(selected, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
