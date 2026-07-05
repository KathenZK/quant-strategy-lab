from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import random
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trx_1h_ar_v1 as v1  # noqa: E402
import trx_1h_ar_v1_clean as clean  # noqa: E402


FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
DATE_TAG = "2026-07-05"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v1_clean_tune_{DATE_TAG}.json"
MACD_POOL_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_tune_macd_pool_{DATE_TAG}.csv"
STOCH_POOL_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_tune_stoch_pool_{DATE_TAG}.csv"
PAIR_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_tune_pairs_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_tune_selected_trades_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_tune_selected_slices_{DATE_TAG}.csv"
NEIGHBOR_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_tune_neighborhood_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"trx-1h-ar-v1-clean-parameter-tune-{DATE_TAG}.md"


@dataclass(slots=True)
class LegCandidate:
    clean_config: Any
    metrics: dict[str, dict[str, float]]
    score: float
    priority_score: float
    trades: list[Any] | None = None


@dataclass(slots=True)
class PairCandidate:
    macd: clean.MACDCleanConfig
    stoch: clean.StochCleanConfig
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    priorities: tuple[float, float]
    score: float
    strict_improvement: bool
    delay_metrics: dict[str, dict[str, float]] | None = None
    slip8_metrics: dict[str, dict[str, float]] | None = None
    combined_metrics: dict[str, dict[str, float]] | None = None
    robust_score: float = -1e9


_WORK_ENGINE: Any | None = None
_WORK_FRAME: pd.DataFrame | None = None
_WORK_FUNDING_TIMES: Any = None
_WORK_FUNDING_CUMULATIVE: Any = None


MACD_DOMAINS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (55, 89, 144, 233, 377),
    "roc_window": (3, 6, 12, 24, 48, 72, 168),
    "macd_set": ((8, 21, 5), (12, 26, 9), (21, 55, 9), (34, 89, 13)),
    "min_adx": (0.0, 8.0, 12.0, 16.0, 20.0, 24.0),
    "max_adx": (24.0, 28.0, 30.0, 32.0, 36.0, 45.0, 100.0),
    "min_rvol": (0.0, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0),
    "max_atr_bps": (150.0, 175.0, 200.0, 250.0, 300.0, 400.0, 600.0, 10_000.0),
    "min_dir_roc_bps": (-10_000.0, -300.0, -200.0, -100.0, -50.0, 0.0, 50.0, 100.0),
    "max_dist_ema_bps": (300.0, 500.0, 750.0, 1000.0, 1500.0, 2500.0, 10_000.0),
    "htf_mode": ("none", "h4", "h12", "d1"),
    "require_macd_turn": (False, True),
    "tp_atr": (0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0),
    "sl_atr": (2.0, 3.0, 4.0, 5.0, 6.0),
    "max_hold_bars": (48, 72, 96, 120, 168, 240, 336),
    "cooldown_bars": (0, 3, 6, 12, 24),
    "entry_delay_bars": (1, 1, 1, 2),
    "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0),
}

STOCH_DOMAINS: dict[str, tuple[Any, ...]] = {
    "side_mode": ("long", "long", "both"),
    "ema_htf": (55, 89, 144, 233, 377),
    "indicator_window": (7, 14, 21, 28),
    "threshold_low": (10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0),
    "threshold_high": (60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0),
    "roc_window": (3, 6, 12, 24, 48, 72, 168),
    "max_adx": (20.0, 24.0, 28.0, 30.0, 32.0, 36.0, 45.0, 100.0),
    "min_rvol": (0.0, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0),
    "min_dir_roc_bps": (-10_000.0, -300.0, -200.0, -100.0, -50.0, 0.0, 50.0, 100.0),
    "require_body_dir": (False, True),
    "sl_atr": (2.5, 3.0, 4.0, 5.0, 6.0),
    "trail_activation_atr": (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0),
    "trail_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0),
    "max_hold_bars": (48, 72, 96, 120, 168, 240, 336),
    "cooldown_bars": (0, 6, 12, 18, 24, 36, 48),
    "entry_delay_bars": (1, 2, 2, 3),
    "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prefit-only clean-surface tune for TRX-1H-Adaptive-Regime-V1."
    )
    parser.add_argument("--leg-samples", type=int, default=200_000)
    parser.add_argument("--leg-keep", type=int, default=450)
    parser.add_argument("--pair-keep", type=int, default=3_000)
    parser.add_argument("--robust-keep", type=int, default=800)
    parser.add_argument("--seed", type=int, default=2026070501)
    parser.add_argument("--progress-every", type=int, default=10_000)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def prefit_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, v1.TRAIN_START, v1.TRAIN_END),
        "validation": engine.metrics(trades, v1.TRAIN_END, v1.PREFIT_END),
        "prefit": engine.metrics(trades, v1.TRAIN_START, v1.PREFIT_END),
    }


def flatten(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def leg_score(metrics: dict[str, dict[str, float]]) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if prefit["trades"] < 24 or validation["trades"] < 6:
        return -1e9
    annuals = [
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    ]
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    score = (
        0.8 * math.log(min(annuals[2], 1e6))
        + 0.9 * math.log(max(min(annuals[0], annuals[1]), 1e-9))
        + 0.25 * min(prefit["profit_factor"], 5.0)
        + 0.4 * min_win
        - max(0.0, -0.22 - worst_dd) * 20.0
        - max(0.0, 0.50 - min_win) * 10.0
    )
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        score -= 8.0
    return float(score)


def moderate_win_bonus(win_rate: float) -> float:
    if 0.65 <= win_rate <= 0.85:
        return 0.5
    if 0.55 <= win_rate <= 0.90:
        return 0.2
    return -abs(win_rate - 0.75)


def pair_strict_improvement(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> bool:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    ref = reference["prefit"]
    return bool(
        prefit["annual_multiple"] > ref["annual_multiple"]
        and prefit["max_dd"] > ref["max_dd"]
        and prefit["win_rate"] >= 0.55
        and train["total_return"] > 0
        and validation["total_return"] > 0
        and train["max_dd"] > -0.20
        and validation["max_dd"] > -0.20
        and train["win_rate"] >= 0.50
        and validation["win_rate"] >= 0.50
    )


def pair_score(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if prefit["trades"] < 70 or validation["trades"] < 18:
        return -1e9
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    score = (
        1.1 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.2
        * math.log(
            max(min(train["annual_multiple"], validation["annual_multiple"]), 1e-9)
        )
        + 0.35 * min(prefit["profit_factor"], 5.0)
        + 2.0 * max(0.0, prefit["max_dd"] + 0.20)
        + moderate_win_bonus(prefit["win_rate"])
        - max(0.0, -0.20 - worst_dd) * 35.0
        - max(0.0, 0.50 - min_win) * 12.0
    )
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        score -= 10.0
    if pair_strict_improvement(metrics, reference):
        score += 12.0
    return float(score)


def random_macd(rng: random.Random) -> clean.MACDCleanConfig:
    macd_fast, macd_slow, macd_signal = rng.choice(MACD_DOMAINS["macd_set"])
    minimum = rng.choice(MACD_DOMAINS["min_adx"])
    maximum = rng.choice(MACD_DOMAINS["max_adx"])
    if maximum <= minimum:
        maximum = 100.0
    return clean.MACDCleanConfig(
        ema_htf=rng.choice(MACD_DOMAINS["ema_htf"]),
        roc_window=rng.choice(MACD_DOMAINS["roc_window"]),
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        min_adx=minimum,
        max_adx=maximum,
        min_rvol=rng.choice(MACD_DOMAINS["min_rvol"]),
        max_atr_bps=rng.choice(MACD_DOMAINS["max_atr_bps"]),
        min_dir_roc_bps=rng.choice(MACD_DOMAINS["min_dir_roc_bps"]),
        max_dist_ema_bps=rng.choice(MACD_DOMAINS["max_dist_ema_bps"]),
        htf_mode=rng.choice(MACD_DOMAINS["htf_mode"]),
        require_macd_turn=rng.choice(MACD_DOMAINS["require_macd_turn"]),
        tp_atr=rng.choice(MACD_DOMAINS["tp_atr"]),
        sl_atr=rng.choice(MACD_DOMAINS["sl_atr"]),
        max_hold_bars=rng.choice(MACD_DOMAINS["max_hold_bars"]),
        cooldown_bars=rng.choice(MACD_DOMAINS["cooldown_bars"]),
        entry_delay_bars=rng.choice(MACD_DOMAINS["entry_delay_bars"]),
        fixed_leverage=rng.choice(MACD_DOMAINS["fixed_leverage"]),
    )


def random_stoch(rng: random.Random) -> clean.StochCleanConfig:
    low = rng.choice(STOCH_DOMAINS["threshold_low"])
    high = rng.choice(STOCH_DOMAINS["threshold_high"])
    if high <= low + 20.0:
        high = max(75.0, low + 25.0)
    return clean.StochCleanConfig(
        side_mode=rng.choice(STOCH_DOMAINS["side_mode"]),
        ema_htf=rng.choice(STOCH_DOMAINS["ema_htf"]),
        indicator_window=rng.choice(STOCH_DOMAINS["indicator_window"]),
        threshold_low=low,
        threshold_high=high,
        roc_window=rng.choice(STOCH_DOMAINS["roc_window"]),
        max_adx=rng.choice(STOCH_DOMAINS["max_adx"]),
        min_rvol=rng.choice(STOCH_DOMAINS["min_rvol"]),
        min_dir_roc_bps=rng.choice(STOCH_DOMAINS["min_dir_roc_bps"]),
        require_body_dir=rng.choice(STOCH_DOMAINS["require_body_dir"]),
        sl_atr=rng.choice(STOCH_DOMAINS["sl_atr"]),
        trail_activation_atr=rng.choice(STOCH_DOMAINS["trail_activation_atr"]),
        trail_atr=rng.choice(STOCH_DOMAINS["trail_atr"]),
        max_hold_bars=rng.choice(STOCH_DOMAINS["max_hold_bars"]),
        cooldown_bars=rng.choice(STOCH_DOMAINS["cooldown_bars"]),
        entry_delay_bars=rng.choice(STOCH_DOMAINS["entry_delay_bars"]),
        fixed_leverage=rng.choice(STOCH_DOMAINS["fixed_leverage"]),
    )


def config_key(cfg: Any) -> tuple[Any, ...]:
    return tuple(asdict(cfg).values())


def generate_unique_configs(
    *, component: str, rng: random.Random, samples: int
) -> list[Any]:
    baseline = (
        clean.MACDCleanConfig()
        if component == "macd"
        else clean.StochCleanConfig()
    )
    configs = [baseline]
    if component == "stoch":
        configs.extend(
            [
                replace(baseline, entry_delay_bars=2),
                replace(baseline, sl_atr=4.0),
                replace(baseline, cooldown_bars=12),
                replace(baseline, side_mode="both"),
            ]
        )
    seen = {config_key(cfg) for cfg in configs}
    attempts = 0
    while len(configs) < samples + 1 and attempts < samples * 3:
        attempts += 1
        cfg = random_macd(rng) if component == "macd" else random_stoch(rng)
        key = config_key(cfg)
        if key in seen:
            continue
        seen.add(key)
        configs.append(cfg)
    return configs


def evaluate_leg(
    item: tuple[str, Any],
) -> tuple[Any, dict[str, dict[str, float]], float, float]:
    component, cfg = item
    if (
        _WORK_ENGINE is None
        or _WORK_FRAME is None
        or _WORK_FUNDING_TIMES is None
        or _WORK_FUNDING_CUMULATIVE is None
    ):
        raise RuntimeError("Tune worker state was not initialized")
    base_cfg = (
        clean.macd_to_base(_WORK_ENGINE, cfg)
        if component == "macd"
        else clean.stoch_to_base(_WORK_ENGINE, cfg)
    )
    trades = v1.simulate_component(
        _WORK_ENGINE,
        _WORK_FRAME,
        _WORK_FUNDING_TIMES,
        _WORK_FUNDING_CUMULATIVE,
        base_cfg,
    )
    metrics = prefit_metrics(_WORK_ENGINE, trades)
    return cfg, metrics, leg_score(metrics), v1.component_score(_WORK_ENGINE, trades)


def build_leg_pool(
    *,
    component: str,
    configs: list[Any],
    keep: int,
    progress_every: int,
    workers: int,
) -> tuple[list[LegCandidate], dict[str, int]]:
    retained: list[LegCandidate] = []
    eligible = 0
    context = mp.get_context("fork")
    pool = context.Pool(processes=max(1, workers)) if workers > 1 else None
    results = (
        pool.imap(evaluate_leg, ((component, cfg) for cfg in configs), chunksize=64)
        if pool is not None
        else map(evaluate_leg, ((component, cfg) for cfg in configs))
    )
    try:
        for index, (cfg, metrics, score, priority) in enumerate(results, start=1):
            if score > -1e8:
                eligible += 1
                retained.append(
                    LegCandidate(
                        clean_config=cfg,
                        metrics=metrics,
                        score=score,
                        priority_score=priority,
                    )
                )
                if len(retained) > keep * 3:
                    retained = sorted(
                        retained, key=lambda candidate: candidate.score, reverse=True
                    )[:keep]
            if index % progress_every == 0 and retained:
                best = max(retained, key=lambda candidate: candidate.score)
                print(
                    f"{component} {index}/{len(configs)} eligible={eligible} "
                    f"best_ann={best.metrics['prefit']['annual_multiple']:.3f} "
                    f"best_dd={best.metrics['prefit']['max_dd']:.3f}",
                    flush=True,
                )
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    retained = sorted(retained, key=lambda candidate: candidate.score, reverse=True)[:keep]
    return retained, {
        "generated_unique": len(configs),
        "eligible": eligible,
        "retained": len(retained),
    }


def attach_trades(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    pool: list[LegCandidate],
    component: str,
) -> None:
    for candidate in pool:
        base_cfg = (
            clean.macd_to_base(engine, candidate.clean_config)
            if component == "macd"
            else clean.stoch_to_base(engine, candidate.clean_config)
        )
        candidate.trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, base_cfg
        )


def retain_pairs(
    retained: list[PairCandidate], candidate: PairCandidate, keep: int
) -> list[PairCandidate]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained


def simulate_pair_scenario(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    macd: clean.MACDCleanConfig,
    stoch: clean.StochCleanConfig,
    fee: float,
    slippage: float,
    add_delay: int,
    frozen_priorities: tuple[float, float],
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    original_fee = engine.FEE_PER_FILL
    original_slippage = engine.SLIPPAGE_PER_FILL
    engine.FEE_PER_FILL = fee
    engine.SLIPPAGE_PER_FILL = slippage
    try:
        stressed_macd = replace(
            macd, entry_delay_bars=macd.entry_delay_bars + add_delay
        )
        stressed_stoch = replace(
            stoch, entry_delay_bars=stoch.entry_delay_bars + add_delay
        )
        merged, *_ = clean.simulate_clean(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            macd=stressed_macd,
            stoch=stressed_stoch,
            frozen_priorities=frozen_priorities,
        )
        return merged, prefit_metrics(engine, merged)
    finally:
        engine.FEE_PER_FILL = original_fee
        engine.SLIPPAGE_PER_FILL = original_slippage


def robust_prefit_gate(metrics: dict[str, dict[str, float]]) -> bool:
    return all(
        item["total_return"] > 0
        and item["max_dd"] > -0.20
        and item["win_rate"] >= 0.50
        for item in (metrics["train"], metrics["validation"], metrics["prefit"])
    )


def robust_score(candidate: PairCandidate) -> float:
    assert candidate.delay_metrics is not None
    assert candidate.slip8_metrics is not None
    assert candidate.combined_metrics is not None
    stressed = [
        candidate.metrics["prefit"],
        candidate.delay_metrics["prefit"],
        candidate.slip8_metrics["prefit"],
        candidate.combined_metrics["prefit"],
    ]
    min_annual = min(item["annual_multiple"] for item in stressed)
    worst_dd = min(item["max_dd"] for item in stressed)
    min_win = min(item["win_rate"] for item in stressed)
    return float(
        candidate.score
        + 1.5 * math.log(max(min_annual, 1e-9))
        + 1.5 * max(0.0, worst_dd + 0.20)
        + moderate_win_bonus(min_win)
        - max(0.0, -0.20 - worst_dd) * 40.0
        - max(0.0, 0.50 - min_win) * 15.0
    )


def pair_row(candidate: PairCandidate) -> dict[str, Any]:
    row = {
        "score": candidate.score,
        "robust_score": candidate.robust_score,
        "strict_improvement": candidate.strict_improvement,
        **{f"m_{key}": value for key, value in asdict(candidate.macd).items()},
        **{f"s_{key}": value for key, value in asdict(candidate.stoch).items()},
        **flatten(candidate.metrics),
    }
    for prefix, metrics in (
        ("delay", candidate.delay_metrics),
        ("slip8", candidate.slip8_metrics),
        ("combined", candidate.combined_metrics),
    ):
        if metrics is not None:
            row.update({f"{prefix}_{key}": value for key, value in flatten(metrics).items()})
    return row


def leg_rows(pool: list[LegCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "score": candidate.score,
            "priority_score": candidate.priority_score,
            **asdict(candidate.clean_config),
            **flatten(candidate.metrics),
        }
        for candidate in pool
    ]


def scenario_all_metrics(
    engine: Any,
    trades: list[Any],
) -> dict[str, dict[str, float]]:
    return {
        **v1.metrics(engine, trades),
        **v1.standard_slices(engine, trades),
    }


def neighbor_variants(selected: PairCandidate) -> list[tuple[str, Any, Any]]:
    variants: list[tuple[str, Any, Any]] = []
    for field in fields(clean.MACDCleanConfig):
        domain_name = "macd_set" if field.name.startswith("macd_") else field.name
        domain = MACD_DOMAINS.get(domain_name, ())
        values: tuple[Any, ...]
        if domain_name == "macd_set":
            values = tuple(domain)
        else:
            values = tuple(dict.fromkeys(domain))
        for value in values:
            if domain_name == "macd_set":
                replacement = replace(
                    selected.macd,
                    macd_fast=value[0],
                    macd_slow=value[1],
                    macd_signal=value[2],
                )
                label = f"macd_set={value}"
            else:
                if value == getattr(selected.macd, field.name):
                    continue
                replacement = replace(selected.macd, **{field.name: value})
                label = f"macd.{field.name}={value}"
            variants.append((label, replacement, selected.stoch))
    for field in fields(clean.StochCleanConfig):
        domain = tuple(dict.fromkeys(STOCH_DOMAINS[field.name]))
        for value in domain:
            if value == getattr(selected.stoch, field.name):
                continue
            replacement = replace(selected.stoch, **{field.name: value})
            variants.append((f"stoch.{field.name}={value}", selected.macd, replacement))
    return variants


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    reference_trades, *_ = clean.simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    reference_prefit = prefit_metrics(engine, reference_trades)
    reference_all = v1.metrics(engine, reference_trades)

    global _WORK_ENGINE
    global _WORK_FRAME
    global _WORK_FUNDING_TIMES
    global _WORK_FUNDING_CUMULATIVE
    _WORK_ENGINE = engine
    _WORK_FRAME = frame
    _WORK_FUNDING_TIMES = funding_times
    _WORK_FUNDING_CUMULATIVE = funding_cumulative

    rng = random.Random(args.seed)
    macd_configs = generate_unique_configs(
        component="macd", rng=rng, samples=args.leg_samples
    )
    stoch_configs = generate_unique_configs(
        component="stoch", rng=rng, samples=args.leg_samples
    )
    print(
        f"generated macd={len(macd_configs)} stoch={len(stoch_configs)}",
        flush=True,
    )
    macd_pool, macd_counts = build_leg_pool(
        component="macd",
        configs=macd_configs,
        keep=args.leg_keep,
        progress_every=args.progress_every,
        workers=args.workers,
    )
    stoch_pool, stoch_counts = build_leg_pool(
        component="stoch",
        configs=stoch_configs,
        keep=args.leg_keep,
        progress_every=args.progress_every,
        workers=args.workers,
    )
    attach_trades(
        engine, frame, funding_times, funding_cumulative, macd_pool, "macd"
    )
    attach_trades(
        engine, frame, funding_times, funding_cumulative, stoch_pool, "stoch"
    )
    pd.DataFrame(leg_rows(macd_pool)).to_csv(MACD_POOL_CSV, index=False)
    pd.DataFrame(leg_rows(stoch_pool)).to_csv(STOCH_POOL_CSV, index=False)

    pairs: list[PairCandidate] = []
    strict_count = 0
    eligible_pairs = 0
    evaluated_pairs = 0
    for macd_candidate in macd_pool:
        assert macd_candidate.trades is not None
        for stoch_candidate in stoch_pool:
            assert stoch_candidate.trades is not None
            priorities = (
                macd_candidate.priority_score,
                stoch_candidate.priority_score,
            )
            merged = engine.merge_trade_sets(
                macd_candidate.trades,
                stoch_candidate.trades,
                priorities[0],
                priorities[1],
            )
            metrics = prefit_metrics(engine, merged)
            score = pair_score(metrics, reference_prefit)
            evaluated_pairs += 1
            if score <= -1e8:
                continue
            eligible_pairs += 1
            strict = pair_strict_improvement(metrics, reference_prefit)
            strict_count += int(strict)
            pairs = retain_pairs(
                pairs,
                PairCandidate(
                    macd=macd_candidate.clean_config,
                    stoch=stoch_candidate.clean_config,
                    trades=merged,
                    metrics=metrics,
                    priorities=priorities,
                    score=score,
                    strict_improvement=strict,
                ),
                args.pair_keep,
            )
    pairs = sorted(pairs, key=lambda candidate: candidate.score, reverse=True)[
        : args.pair_keep
    ]
    print(
        f"pairs evaluated={evaluated_pairs} eligible={eligible_pairs} "
        f"strict={strict_count} retained={len(pairs)}",
        flush=True,
    )

    for index, candidate in enumerate(pairs[: args.robust_keep], start=1):
        _delay_trades, candidate.delay_metrics = simulate_pair_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            macd=candidate.macd,
            stoch=candidate.stoch,
            fee=0.001,
            slippage=0.0004,
            add_delay=1,
            frozen_priorities=candidate.priorities,
        )
        _slip8_trades, candidate.slip8_metrics = simulate_pair_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            macd=candidate.macd,
            stoch=candidate.stoch,
            fee=0.001,
            slippage=0.0008,
            add_delay=0,
            frozen_priorities=candidate.priorities,
        )
        _combined_trades, candidate.combined_metrics = simulate_pair_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            macd=candidate.macd,
            stoch=candidate.stoch,
            fee=0.001,
            slippage=0.0008,
            add_delay=1,
            frozen_priorities=candidate.priorities,
        )
        candidate.robust_score = robust_score(candidate)
        if index % 100 == 0:
            print(
                f"robust {index}/{min(len(pairs), args.robust_keep)}", flush=True
            )
    robust = sorted(
        pairs[: args.robust_keep],
        key=lambda candidate: candidate.robust_score,
        reverse=True,
    )
    strict_robust = [candidate for candidate in robust if candidate.strict_improvement]
    fully_robust = [
        candidate
        for candidate in strict_robust
        if candidate.delay_metrics is not None
        and candidate.slip8_metrics is not None
        and candidate.combined_metrics is not None
        and robust_prefit_gate(candidate.delay_metrics)
        and robust_prefit_gate(candidate.slip8_metrics)
        and robust_prefit_gate(candidate.combined_metrics)
    ]
    selected = (
        fully_robust[0]
        if fully_robust
        else strict_robust[0]
        if strict_robust
        else robust[0]
    )
    selection_reason = (
        "strict_prefit_improvement_plus_delay_slip8_combined_all_window_gate"
        if fully_robust
        else "strict_prefit_improvement_then_robust_score"
        if strict_robust
        else "no_strict_improvement_robust_frontier"
    )

    selected_all = v1.metrics(engine, selected.trades)
    selected_slices = v1.standard_slices(engine, selected.trades)
    scenario_specs = (
        ("base", 0, 0.001, 0.0004),
        ("one_extra_bar", 1, 0.001, 0.0004),
        ("slippage_8bps", 0, 0.001, 0.0008),
        ("one_extra_bar_slippage_8bps", 1, 0.001, 0.0008),
        ("fee15_slippage8", 0, 0.0015, 0.0008),
    )
    scenarios: list[dict[str, Any]] = []
    for name, add_delay, fee, slippage in scenario_specs:
        if name == "base":
            trades = selected.trades
        else:
            trades, _prefit = simulate_pair_scenario(
                engine=engine,
                frame=frame,
                funding_times=funding_times,
                funding_cumulative=funding_cumulative,
                macd=selected.macd,
                stoch=selected.stoch,
                fee=fee,
                slippage=slippage,
                add_delay=add_delay,
                frozen_priorities=selected.priorities,
            )
        scenarios.append(
            {
                "scenario": name,
                "add_delay_bars": add_delay,
                "fee_per_fill": fee,
                "slippage_per_fill": slippage,
                "metrics": scenario_all_metrics(engine, trades),
            }
        )

    neighbor_rows: list[dict[str, Any]] = []
    for label, macd_cfg, stoch_cfg in neighbor_variants(selected):
        merged, *_ = clean.simulate_clean(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            macd=macd_cfg,
            stoch=stoch_cfg,
        )
        metrics = prefit_metrics(engine, merged)
        neighbor_rows.append(
            {
                "label": label,
                **flatten(metrics),
                "positive_all_windows": all(
                    metrics[window]["total_return"] > 0
                    for window in ("train", "validation", "prefit")
                ),
                "dd_under_20_all_windows": all(
                    metrics[window]["max_dd"] > -0.20
                    for window in ("train", "validation", "prefit")
                ),
                "win_50_all_windows": all(
                    metrics[window]["win_rate"] >= 0.50
                    for window in ("train", "validation", "prefit")
                ),
            }
        )
    pd.DataFrame(neighbor_rows).to_csv(NEIGHBOR_CSV, index=False)
    neighborhood_pass = sum(
        row["positive_all_windows"]
        and row["dd_under_20_all_windows"]
        and row["win_50_all_windows"]
        for row in neighbor_rows
    )

    pd.DataFrame([pair_row(candidate) for candidate in robust[:500]]).to_csv(
        PAIR_CSV, index=False
    )
    pd.DataFrame(
        [
            {
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "bars_held": trade.bars_held,
                "exposure": trade.exposure,
                "equity_ret": trade.equity_ret,
                "equity_mae": trade.equity_mae,
            }
            for trade in selected.trades
        ]
    ).to_csv(TRADES_CSV, index=False)
    pd.DataFrame(
        [
            {"window": window, **metrics}
            for window, metrics in selected_slices.items()
        ]
    ).to_csv(SLICES_CSV, index=False)

    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "baseline_version": "TRX-1H-Adaptive-Regime-V1",
        "observation_id": "TRX-1H-AR-V1-CLEAN-TUNE-2026-07-05",
        "status": "tuned_observation_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "reused_holdout": "read_only_after_freeze_not_used_for_selection",
            "moderate_win_preference": "prefer 65%-85%; hard floor 55% for strict improvement",
            "reason": selection_reason,
        },
        "search_counts": {
            "requested_leg_samples_each": args.leg_samples,
            "macd": macd_counts,
            "stoch": stoch_counts,
            "evaluated_pairs": evaluated_pairs,
            "eligible_pairs": eligible_pairs,
            "strict_improvement_pair_observations": strict_count,
            "retained_pairs": len(pairs),
            "robust_evaluated": min(len(pairs), args.robust_keep),
            "strict_robust": len(strict_robust),
            "fully_robust": len(fully_robust),
            "neighborhood_variants": len(neighbor_rows),
            "neighborhood_all_window_gate": neighborhood_pass,
        },
        "reference_v1": {
            "metrics": reference_all,
            "standard_slices": v1.standard_slices(engine, reference_trades),
        },
        "selected": {
            "macd": asdict(selected.macd),
            "stoch": asdict(selected.stoch),
            "priorities": selected.priorities,
            "base_metrics": selected_all,
            "standard_slices": selected_slices,
            "prefit_score": selected.score,
            "robust_score": selected.robust_score,
            "strict_improvement": selected.strict_improvement,
        },
        "scenarios": scenarios,
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        "# TRX-1H-Adaptive-Regime-V1 Clean 参数联合微调 - 2026-07-05",
        "",
        "## 结论",
        "",
        (
            "本轮只使用 train/validation/prefit 在 V1 全消融后的 clean 参数面选参；"
            "reused holdout 和近期分片均在候选冻结后读取，不参与排序。"
        ),
        "",
        f"- 选择规则：`{selection_reason}`。",
        f"- MACD/Stoch unique configs：`{macd_counts['generated_unique']}` / `{stoch_counts['generated_unique']}`；组合评估 `{evaluated_pairs}`。",
        f"- prefit 同时收益更高、回撤更小、胜率>=55%的 pair observations：`{strict_count}`。",
        f"- 完成额外一根延迟、8 bps、延迟+8 bps 三重 prefit 审计：`{min(len(pairs), args.robust_keep)}`；全窗口通过：`{len(fully_robust)}`。",
        f"- 冻结邻域：`{len(neighbor_rows)}` 个 one-field variants，正收益/DD<20%/win>=50% 全窗口通过 `{neighborhood_pass}`。",
        "",
        "## V1 与冻结微调观察",
        "",
        "| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        reference = reference_all[window]
        tuned = selected_all[window]
        lines.append(
            f"| `{window}` | `{reference['annual_multiple']:.4f}x` | `{reference['max_dd']:.2%}` | `{reference['win_rate']:.2%}` | "
            f"`{tuned['annual_multiple']:.4f}x` | `{tuned['max_dd']:.2%}` | `{tuned['win_rate']:.2%}` | `{int(tuned['trades'])}` |"
        )
    lines.extend(["", "## 冻结参数", "", "### MACD clean", ""])
    lines.extend(
        f"- `{key}` = `{value}`" for key, value in asdict(selected.macd).items()
    )
    lines.extend(["", "### Stochastic clean", ""])
    lines.extend(
        f"- `{key}` = `{value}`" for key, value in asdict(selected.stoch).items()
    )
    lines.extend(
        [
            "",
            "## 延迟、成本与 reused holdout",
            "",
            "| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout return | Reused holdout DD | Full annual | Full DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for scenario in scenarios:
        metrics = scenario["metrics"]
        prefit = metrics["prefit"]
        holdout = metrics["reused_holdout"]
        full = metrics["current_full"]
        lines.append(
            f"| `{scenario['scenario']}` | `{prefit['annual_multiple']:.4f}x` | `{prefit['max_dd']:.2%}` | `{prefit['win_rate']:.2%}` | "
            f"`{holdout['total_return']:.2%}` | `{holdout['max_dd']:.2%}` | `{full['annual_multiple']:.4f}x` | `{full['max_dd']:.2%}` |"
        )
    lines.extend(
        [
            "",
            "## 标准近期分片",
            "",
            "| Slice | Annual | Return | DD | Win | Trades |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for window, metrics in selected_slices.items():
        lines.append(
            f"| `{window}` | `{metrics['annual_multiple']:.4f}x` | `{metrics['total_return']:.2%}` | `{metrics['max_dd']:.2%}` | `{metrics['win_rate']:.2%}` | `{int(metrics['trades'])}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 该结果是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。",
            "- reused holdout 已在 V1 初始研究中揭盲，只能做冻结后失败审计，不能作为 fresh OOS。",
            "- 只有在新增 forward trades 和生产 runner 证据存在后，才允许讨论 candidate/paper-live/live。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{MACD_POOL_CSV.name}`",
            f"- `artifacts/{STOCH_POOL_CSV.name}`",
            f"- `artifacts/{PAIR_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{NEIGHBOR_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v1_clean_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
