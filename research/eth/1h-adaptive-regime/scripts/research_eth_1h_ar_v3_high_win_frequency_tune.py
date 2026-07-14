from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v2_1 as v21  # noqa: E402
import eth_1h_ar_v2_1_clean as clean21  # noqa: E402
import research_eth_1h_ar_v3_frequency_forward_diagnostic as v3_diag  # noqa: E402


DATE_TAG = "2026-07-13"
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_tune_{DATE_TAG}.json"
BB_POOL_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_bb_pool_{DATE_TAG}.csv"
RSI_POOL_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_rsi_pool_{DATE_TAG}.csv"
CANDIDATES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_candidates_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_trades_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_slices_{DATE_TAG}.csv"
NEIGHBORHOOD_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_neighborhood_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"eth-1h-ar-v3-high-win-frequency-tune-{DATE_TAG}.md"

MIN_PREFIT_TRADES = 60
TARGET_PREFIT_TRADES = 80
MIN_VALIDATION_TRADES = 12
MIN_TRAIN_WIN = 0.85
MIN_VALIDATION_WIN = 0.80
MIN_PREFIT_WIN = 0.85
MIN_ROBUST_PREFIT_WIN = 0.80
DD_FLOOR = -0.20

BB_DOMAINS: dict[str, tuple[Any, ...]] = {
    "indicator_window": (48, 72, 96),
    "band_k": (2.0, 2.25, 2.5, 2.75),
    "roc_window": (12, 24, 48),
    "min_adx": (12.0, 16.0, 20.0, 24.0),
    "min_rvol": (2.0, 2.5, 3.0, 3.5),
    "min_atr_bps": (0.0, 25.0, 50.0, 75.0, 100.0),
    "min_dir_roc_bps": (0.0, 100.0, 200.0),
    "max_dist_ema_bps": (750.0, 1000.0, 1500.0, 2500.0, 10_000.0),
    "tp_atr": (2.5, 3.0, 3.5),
    "sl_atr": (4.0, 5.0, 6.0),
    "max_hold_bars": (48, 72, 96),
    "fixed_leverage": (1.0, 1.5, 2.0),
}

RSI_DOMAINS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (144, 233, 377),
    "indicator_window": (5, 7, 9, 14),
    "threshold_low": (5.0, 10.0, 15.0),
    "threshold_high": (65.0, 70.0, 75.0, 80.0),
    "roc_window": (3, 6, 12),
    "min_adx": (12.0, 16.0, 20.0, 24.0),
    "max_adx": (45.0, 55.0, 100.0),
    "min_atr_bps": (75.0, 90.0, 100.0, 110.0, 125.0),
    "min_dir_roc_bps": (-10_000.0, -500.0, -300.0, -100.0, 0.0),
    "max_dist_ema_bps": (750.0, 1000.0, 1500.0, 2500.0),
    "tp_atr": (1.5, 2.0, 2.5),
    "sl_atr": (2.0, 2.5, 3.0),
    "max_hold_bars": (24, 36, 48),
    "cooldown_bars": (12, 24, 36),
    "fixed_leverage": (1.5, 2.0, 2.5),
}


@dataclass(slots=True)
class LegCandidate:
    config: Any
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    score: float


@dataclass(slots=True)
class PairCandidate:
    bb: clean21.BBBreakV21CleanConfig
    rsi: clean21.RSIV21CleanConfig
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    score: float
    k2_metrics: dict[str, dict[str, float]] | None = None
    slip8_metrics: dict[str, dict[str, float]] | None = None
    robust_score: float = -1e9
    robust_gate: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="High-win frequency tune for ETH-1H-Adaptive-Regime-V3."
    )
    parser.add_argument("--leg-samples", type=int, default=120_000)
    parser.add_argument("--leg-keep", type=int, default=500)
    parser.add_argument("--pair-keep", type=int, default=3_000)
    parser.add_argument("--robust-keep", type=int, default=800)
    parser.add_argument("--seed", type=int, default=2026071301)
    parser.add_argument("--progress-every", type=int, default=20_000)
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


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


def wilson_lower(wins: int, trades: int, z: float = 1.0) -> float:
    if trades <= 0:
        return 0.0
    p = wins / trades
    denominator = 1.0 + z * z / trades
    center = p + z * z / (2.0 * trades)
    margin = z * math.sqrt(p * (1.0 - p) / trades + z * z / (4.0 * trades * trades))
    return float((center - margin) / denominator)


def metric_wilson(metric: dict[str, float]) -> float:
    trades = int(metric["trades"])
    wins = int(round(metric["win_rate"] * trades))
    return wilson_lower(wins, trades)


def leg_score(metrics: dict[str, dict[str, float]]) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if (
        prefit["trades"] < 18
        or validation["trades"] < 5
        or train["total_return"] <= 0.0
        or validation["total_return"] <= 0.0
    ):
        return -1e9
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    if worst_dd <= -0.22:
        return -1e9
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    min_annual = min(
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    )
    return float(
        1.0 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.7 * math.log(min_annual)
        + 1.8 * min_win
        + 1.5 * metric_wilson(prefit)
        + 0.012 * min(prefit["trades"], 100.0)
        + 0.025 * min(validation["trades"], 24.0)
        + 3.0 * worst_dd
    )


def pair_gate(metrics: dict[str, dict[str, float]]) -> bool:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    return bool(
        prefit["trades"] >= MIN_PREFIT_TRADES
        and validation["trades"] >= MIN_VALIDATION_TRADES
        and train["win_rate"] >= MIN_TRAIN_WIN
        and validation["win_rate"] >= MIN_VALIDATION_WIN
        and prefit["win_rate"] >= MIN_PREFIT_WIN
        and train["total_return"] > 0.0
        and validation["total_return"] > 0.0
        and train["max_dd"] > DD_FLOOR
        and validation["max_dd"] > DD_FLOOR
        and prefit["max_dd"] > DD_FLOOR
    )


def pair_score(metrics: dict[str, dict[str, float]]) -> float:
    if not pair_gate(metrics):
        return -1e9
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    min_annual = min(
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    )
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    trade_reward = min(prefit["trades"], TARGET_PREFIT_TRADES) / TARGET_PREFIT_TRADES
    return float(
        1.2 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.9 * math.log(min_annual)
        + 3.0 * min_win
        + 2.2 * metric_wilson(prefit)
        + 1.2 * trade_reward
        + 0.035 * min(validation["trades"], 24.0)
        + 5.0 * worst_dd
    )


def robust_gate(metrics: dict[str, dict[str, float]]) -> bool:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    return bool(
        prefit["trades"] >= MIN_PREFIT_TRADES - 5
        and validation["trades"] >= MIN_VALIDATION_TRADES - 2
        and train["win_rate"] >= MIN_ROBUST_PREFIT_WIN
        and validation["win_rate"] >= MIN_ROBUST_PREFIT_WIN
        and prefit["win_rate"] >= MIN_ROBUST_PREFIT_WIN
        and train["max_dd"] > DD_FLOOR
        and validation["max_dd"] > DD_FLOOR
        and prefit["max_dd"] > DD_FLOOR
    )


def candidate_robust_score(candidate: PairCandidate) -> float:
    assert candidate.k2_metrics is not None
    assert candidate.slip8_metrics is not None
    scenarios = (candidate.metrics, candidate.k2_metrics, candidate.slip8_metrics)
    min_win = min(
        metrics[window]["win_rate"]
        for metrics in scenarios
        for window in ("train", "validation", "prefit")
    )
    min_annual = min(
        max(metrics["prefit"]["annual_multiple"], 1e-9) for metrics in scenarios
    )
    worst_dd = min(
        metrics[window]["max_dd"]
        for metrics in scenarios
        for window in ("train", "validation", "prefit")
    )
    min_wilson = min(metric_wilson(metrics["prefit"]) for metrics in scenarios)
    min_trades = min(metrics["prefit"]["trades"] for metrics in scenarios)
    return float(
        candidate.score
        + 1.0 * math.log(min_annual)
        + 2.8 * min_win
        + 2.0 * min_wilson
        + 0.8 * min(min_trades, TARGET_PREFIT_TRADES) / TARGET_PREFIT_TRADES
        + 4.0 * worst_dd
        + (8.0 if candidate.robust_gate else 0.0)
    )


def random_from_domains(
    rng: random.Random,
    cls: type[Any],
    domains: dict[str, tuple[Any, ...]],
) -> Any:
    return cls(**{key: rng.choice(values) for key, values in domains.items()})


def config_key(config: Any) -> tuple[Any, ...]:
    return tuple(asdict(config).values())


def retain(items: list[Any], item: Any, keep: int, *, key: str) -> list[Any]:
    items.append(item)
    if len(items) > keep * 3:
        items = sorted(items, key=lambda value: getattr(value, key), reverse=True)[:keep]
    return items


def simulate_leg(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    component: str,
    config: Any,
) -> list[Any]:
    base = (
        clean21.bb_to_v1_clean(config)
        if component == "bb_break"
        else clean21.rsi_to_v1_clean(config)
    )
    strategy_config = (
        clean21.v1_clean.bb_break_to_base(engine, base)
        if component == "bb_break"
        else clean21.v1_clean.rsi_to_base(engine, base)
    )
    return v1.simulate_component(
        engine, frame, funding_times, funding_cumulative, strategy_config
    )


def build_leg_pool(
    *,
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    rng: random.Random,
    component: str,
    samples: int,
    keep: int,
    progress_every: int,
) -> tuple[list[LegCandidate], dict[str, int]]:
    cls = (
        clean21.BBBreakV21CleanConfig
        if component == "bb_break"
        else clean21.RSIV21CleanConfig
    )
    domains = BB_DOMAINS if component == "bb_break" else RSI_DOMAINS
    baseline = v3_diag.V3_BB if component == "bb_break" else v3_diag.V3_RSI
    candidates = [baseline]
    candidates.extend(random_from_domains(rng, cls, domains) for _ in range(samples))

    retained: list[LegCandidate] = []
    seen: set[tuple[Any, ...]] = set()
    evaluated = 0
    eligible = 0
    for index, config in enumerate(candidates, start=1):
        key = config_key(config)
        if key in seen:
            continue
        seen.add(key)
        trades = simulate_leg(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            component,
            config,
        )
        metrics = prefit_metrics(engine, trades)
        score = leg_score(metrics)
        evaluated += 1
        if score <= -1e8:
            continue
        eligible += 1
        retained = retain(
            retained,
            LegCandidate(config=config, trades=trades, metrics=metrics, score=score),
            keep,
            key="score",
        )
        if index % progress_every == 0 and retained:
            best = max(retained, key=lambda item: item.score)
            print(
                f"{component} {index}/{len(candidates)} evaluated={evaluated} "
                f"eligible={eligible} retained={len(retained)} "
                f"best={best.score:.3f} prefit_n={int(best.metrics['prefit']['trades'])} "
                f"win={best.metrics['prefit']['win_rate']:.2%}",
                flush=True,
            )
    retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained, {
        "generated": len(candidates),
        "unique_evaluated": evaluated,
        "eligible": eligible,
        "retained": len(retained),
    }


def simulate_scenario_prefit(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    bb: clean21.BBBreakV21CleanConfig,
    rsi: clean21.RSIV21CleanConfig,
    *,
    delay: int,
    fee: float,
    slippage: float,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    trades, *_ = clean21.simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=bb,
        rsi=rsi,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )
    return trades, prefit_metrics(engine, trades)


def full_scenario_metrics(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    bb: clean21.BBBreakV21CleanConfig,
    rsi: clean21.RSIV21CleanConfig,
    *,
    delay: int,
    fee: float,
    slippage: float,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    trades, *_ = clean21.simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=bb,
        rsi=rsi,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )
    return trades, v1.metrics(engine, trades)


def pair_row(candidate: PairCandidate) -> dict[str, Any]:
    row = {
        "score": candidate.score,
        "robust_score": candidate.robust_score,
        "robust_gate": candidate.robust_gate,
        **{f"bb_{key}": value for key, value in asdict(candidate.bb).items()},
        **{f"rsi_{key}": value for key, value in asdict(candidate.rsi).items()},
        **flatten(candidate.metrics),
    }
    if candidate.k2_metrics is not None:
        row.update(
            {f"k2_{key}": value for key, value in flatten(candidate.k2_metrics).items()}
        )
    if candidate.slip8_metrics is not None:
        row.update(
            {
                f"slip8_{key}": value
                for key, value in flatten(candidate.slip8_metrics).items()
            }
        )
    return row


def leg_rows(pool: list[LegCandidate]) -> list[dict[str, Any]]:
    return [
        {"score": item.score, **asdict(item.config), **flatten(item.metrics)}
        for item in pool
    ]


def neighborhood_values(current: Any, domain: tuple[Any, ...]) -> list[Any]:
    ordered = list(domain)
    if current not in ordered:
        return ordered[:2]
    index = ordered.index(current)
    values = []
    if index > 0:
        values.append(ordered[index - 1])
    if index + 1 < len(ordered):
        values.append(ordered[index + 1])
    return values


def neighborhood_audit(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    selected: PairCandidate,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for component, config, domains in (
        ("bb_break", selected.bb, BB_DOMAINS),
        ("rsi_reversal", selected.rsi, RSI_DOMAINS),
    ):
        for field, domain in domains.items():
            for value in neighborhood_values(getattr(config, field), domain):
                bb = selected.bb
                rsi = selected.rsi
                if component == "bb_break":
                    bb = type(config)(**{**asdict(config), field: value})
                else:
                    rsi = type(config)(**{**asdict(config), field: value})
                trades, *_ = clean21.simulate_clean(
                    engine,
                    frame,
                    funding_times,
                    funding_cumulative,
                    bb_break=bb,
                    rsi=rsi,
                )
                metrics = v1.metrics(engine, trades)
                rows.append(
                    {
                        "component": component,
                        "field": field,
                        "baseline_value": getattr(config, field),
                        "variant_value": value,
                        "prefit_gate": pair_gate(
                            {
                                key: metrics[key]
                                for key in ("train", "validation", "prefit")
                            }
                        ),
                        **flatten(metrics),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_prefit(
    selected_trades: list[Any],
    *,
    samples: int = 10_000,
    seed: int = 2026071302,
) -> dict[str, Any]:
    returns = np.array(
        [
            trade.equity_ret
            for trade in selected_trades
            if v1.TRAIN_START <= trade.entry_ts < v1.PREFIT_END
        ],
        dtype="float64",
    )
    if len(returns) == 0:
        return {"samples": samples, "trades": 0}
    rng = np.random.default_rng(seed)
    equities = np.empty(samples, dtype="float64")
    win_rates = np.empty(samples, dtype="float64")
    for index in range(samples):
        draw = rng.choice(returns, size=len(returns), replace=True)
        equities[index] = float(np.prod(np.maximum(0.001, 1.0 + draw)))
        win_rates[index] = float(np.mean(draw > 0.0))
    return {
        "samples": samples,
        "trades": int(len(returns)),
        "final_equity_quantiles": {
            "p05": float(np.quantile(equities, 0.05)),
            "p50": float(np.quantile(equities, 0.50)),
            "p95": float(np.quantile(equities, 0.95)),
        },
        "win_rate_quantiles": {
            "p05": float(np.quantile(win_rates, 0.05)),
            "p50": float(np.quantile(win_rates, 0.50)),
            "p95": float(np.quantile(win_rates, 0.95)),
        },
        "positive_equity_rate": float(np.mean(equities > 1.0)),
        "win_ge_80_rate": float(np.mean(win_rates >= 0.80)),
    }


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    engine, frame, funding, quality = v21.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    v3_trades, *_ = clean21.simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=v3_diag.V3_BB,
        rsi=v3_diag.V3_RSI,
    )
    v3_prefit = prefit_metrics(engine, v3_trades)

    rng = random.Random(args.seed)
    bb_pool, bb_counts = build_leg_pool(
        engine=engine,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        rng=rng,
        component="bb_break",
        samples=args.leg_samples,
        keep=args.leg_keep,
        progress_every=args.progress_every,
    )
    rsi_pool, rsi_counts = build_leg_pool(
        engine=engine,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        rng=rng,
        component="rsi_reversal",
        samples=args.leg_samples,
        keep=args.leg_keep,
        progress_every=args.progress_every,
    )
    pd.DataFrame(leg_rows(bb_pool)).to_csv(BB_POOL_CSV, index=False)
    pd.DataFrame(leg_rows(rsi_pool)).to_csv(RSI_POOL_CSV, index=False)

    pairs: list[PairCandidate] = []
    evaluated_pairs = 0
    gate_pairs = 0
    for bb_item in bb_pool:
        for rsi_item in rsi_pool:
            merged = engine.merge_trade_sets(
                bb_item.trades,
                rsi_item.trades,
                bb_item.score,
                rsi_item.score,
            )
            metrics = prefit_metrics(engine, merged)
            score = pair_score(metrics)
            evaluated_pairs += 1
            if score <= -1e8:
                continue
            gate_pairs += 1
            pairs = retain(
                pairs,
                PairCandidate(
                    bb=bb_item.config,
                    rsi=rsi_item.config,
                    trades=merged,
                    metrics=metrics,
                    score=score,
                ),
                args.pair_keep,
                key="score",
            )
    pairs = sorted(pairs, key=lambda item: item.score, reverse=True)[: args.pair_keep]
    if not pairs:
        raise RuntimeError("No high-win frequency pair survived the prefit-only gate")
    print(
        f"pairs evaluated={evaluated_pairs} gate={gate_pairs} retained={len(pairs)}",
        flush=True,
    )

    for index, candidate in enumerate(pairs[: args.robust_keep], start=1):
        _k2_trades, candidate.k2_metrics = simulate_scenario_prefit(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            candidate.bb,
            candidate.rsi,
            delay=2,
            fee=0.001,
            slippage=0.0004,
        )
        _s8_trades, candidate.slip8_metrics = simulate_scenario_prefit(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            candidate.bb,
            candidate.rsi,
            delay=1,
            fee=0.001,
            slippage=0.0008,
        )
        candidate.robust_gate = bool(
            robust_gate(candidate.k2_metrics) and robust_gate(candidate.slip8_metrics)
        )
        candidate.robust_score = candidate_robust_score(candidate)
        if index % 100 == 0:
            print(
                f"robust {index}/{min(len(pairs), args.robust_keep)}",
                flush=True,
            )

    robust_candidates = sorted(
        pairs[: args.robust_keep],
        key=lambda item: (item.robust_gate, item.robust_score),
        reverse=True,
    )
    robust_pass = [candidate for candidate in robust_candidates if candidate.robust_gate]
    selected = robust_pass[0] if robust_pass else robust_candidates[0]
    finalists = robust_pass[:5] if robust_pass else robust_candidates[:5]

    selected_trades, selected_metrics = full_scenario_metrics(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        selected.bb,
        selected.rsi,
        delay=1,
        fee=0.001,
        slippage=0.0004,
    )
    v3_metrics = v1.metrics(engine, v3_trades)
    selected_slices = v21.standard_slices(engine, selected_trades)

    scenario_specs = (
        ("base_k1", 1, 0.001, 0.0004),
        ("delay_k2", 2, 0.001, 0.0004),
        ("delay_k3", 3, 0.001, 0.0004),
        ("slip_8bps", 1, 0.001, 0.0008),
        ("slip_12bps", 1, 0.001, 0.0012),
        ("fee12_slip8", 1, 0.0012, 0.0008),
        ("double_cost", 1, 0.002, 0.0008),
    )
    scenarios = []
    for name, delay, fee, slippage in scenario_specs:
        if name == "base_k1":
            metrics = selected_metrics
        else:
            _trades, metrics = full_scenario_metrics(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                selected.bb,
                selected.rsi,
                delay=delay,
                fee=fee,
                slippage=slippage,
            )
        scenarios.append(
            {
                "scenario": name,
                "delay": delay,
                "fee_per_fill": fee,
                "slippage_per_fill": slippage,
                "metrics": metrics,
            }
        )

    neighborhood = neighborhood_audit(
        engine, frame, funding_times, funding_cumulative, selected
    )
    bootstrap = bootstrap_prefit(selected_trades)

    pd.DataFrame(
        [pair_row(candidate) for candidate in robust_candidates[: min(800, len(robust_candidates))]]
    ).to_csv(CANDIDATES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected_trades)).to_csv(TRADES_CSV, index=False)
    pd.DataFrame(
        [{"window": name, **metric} for name, metric in selected_slices.items()]
    ).to_csv(SLICES_CSV, index=False)
    neighborhood.to_csv(NEIGHBORHOOD_CSV, index=False)

    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "baseline_version": "ETH-1H-Adaptive-Regime-V3",
        "observation_id": "ETH-1H-AR-V3-HIGH-WIN-FREQUENCY-TUNE-2026-07-13",
        "status": "diagnostic_observation_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "reused_holdout": "read_only_after_candidate_freeze_not_used_for_selection",
            "recent_slices": "read_only_after_candidate_freeze_not_used_for_selection",
            "hard_gate": {
                "prefit_trades_min": MIN_PREFIT_TRADES,
                "validation_trades_min": MIN_VALIDATION_TRADES,
                "train_win_min": MIN_TRAIN_WIN,
                "validation_win_min": MIN_VALIDATION_WIN,
                "prefit_win_min": MIN_PREFIT_WIN,
                "max_dd_floor": DD_FLOOR,
            },
            "robust_gate": {
                "scenarios": ["delay_k2", "slip_8bps"],
                "prefit_win_min": MIN_ROBUST_PREFIT_WIN,
                "max_dd_floor": DD_FLOOR,
            },
        },
        "search_counts": {
            "leg_samples_each": args.leg_samples,
            "bb_break": bb_counts,
            "rsi_reversal": rsi_counts,
            "evaluated_pairs": evaluated_pairs,
            "hard_gate_pairs": gate_pairs,
            "retained_pairs": len(pairs),
            "robust_evaluated": min(len(pairs), args.robust_keep),
            "robust_gate_pairs": len(robust_pass),
        },
        "baseline_v3": {
            "parameters": {
                "bb_break": asdict(v3_diag.V3_BB),
                "rsi_reversal": asdict(v3_diag.V3_RSI),
            },
            "metrics": v3_metrics,
        },
        "selected": {
            "bb_break": asdict(selected.bb),
            "rsi_reversal": asdict(selected.rsi),
            "metrics": selected_metrics,
            "standard_slices": selected_slices,
            "prefit_hard_gate": pair_gate(
                {
                    key: selected_metrics[key]
                    for key in ("train", "validation", "prefit")
                }
            ),
            "robust_gate": selected.robust_gate,
            "score": selected.score,
            "robust_score": selected.robust_score,
        },
        "finalists_prefit_only": [
            {
                "bb_break": asdict(candidate.bb),
                "rsi_reversal": asdict(candidate.rsi),
                "metrics": candidate.metrics,
                "score": candidate.score,
                "robust_score": candidate.robust_score,
            }
            for candidate in finalists
        ],
        "scenarios": scenarios,
        "neighborhood": {
            "rows": int(len(neighborhood)),
            "prefit_gate_pass": int(neighborhood["prefit_gate"].sum()),
        },
        "bootstrap_prefit": bootstrap,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": 0.001,
            "slippage_per_fill": 0.0004,
            "funding": "actual_binance_history_per_trade",
        },
        "artifacts": {
            "bb_pool_csv": str(BB_POOL_CSV.relative_to(ROOT)),
            "rsi_pool_csv": str(RSI_POOL_CSV.relative_to(ROOT)),
            "candidates_csv": str(CANDIDATES_CSV.relative_to(ROOT)),
            "trades_csv": str(TRADES_CSV.relative_to(ROOT)),
            "slices_csv": str(SLICES_CSV.relative_to(ROOT)),
            "neighborhood_csv": str(NEIGHBORHOOD_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# ETH-1H-Adaptive-Regime-V3 高胜率频率优化 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "本轮接受“增加有效交易数，但不能让胜率下降太多”的约束，"
            "在 V3 的 27 参数 clean surface 上重新搜索。选择只使用 train/validation/prefit；"
            "reused holdout 与近期分片在候选冻结后才读取。"
        ),
        "",
        (
            f"- 硬门槛：prefit trades `>= {MIN_PREFIT_TRADES}`、validation trades "
            f"`>= {MIN_VALIDATION_TRADES}`、train/prefit win `>= {MIN_PREFIT_WIN:.0%}`、"
            f"validation win `>= {MIN_VALIDATION_WIN:.0%}`、各窗口 DD `<20%`。"
        ),
        (
            f"- K+2 与 8 bps 压力门槛：train/validation/prefit win `>= "
            f"{MIN_ROBUST_PREFIT_WIN:.0%}` 且 DD `<20%`。"
        ),
        (
            f"- 每腿随机 `{args.leg_samples}` 组；组合评估 `{evaluated_pairs}`，"
            f"硬门槛命中 `{gate_pairs}`，压力门槛命中 `{len(robust_pass)}`。"
        ),
        "",
        "## V3 与选中观察值",
        "",
        "| Window | V3 annual / return / DD / win / trades | High-win frequency observation |",
        "| --- | --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(
            f"| `{window}` | {metric_line(v3_metrics[window])} | "
            f"{metric_line(selected_metrics[window])} |"
        )
    lines.extend(
        [
            "",
            "## 选中参数",
            "",
            "### BB breakout",
            "",
        ]
    )
    lines.extend(f"- `{key}` = `{value}`" for key, value in asdict(selected.bb).items())
    lines.extend(
        [
            "",
            f"- 硬编码：`ema_htf={clean21.BB_EMA_HTF_FIXED}`；"
            f"`max_aligned_funding_bps={clean21.BB_MAX_ALIGNED_FUNDING_BPS_FIXED}`。",
            "",
            "### RSI reversal",
            "",
        ]
    )
    lines.extend(f"- `{key}` = `{value}`" for key, value in asdict(selected.rsi).items())
    lines.extend(
        [
            "",
            "## 标准近期分片",
            "",
            "| Slice | Annual / Return / DD / Win / Trades |",
            "| --- | --- |",
        ]
    )
    for window in ("last_1d", "last_7d", "last_1m", "last_3m", "last_6m", "last_1y"):
        lines.append(f"| `{window}` | {metric_line(selected_slices[window])} |")
    lines.extend(
        [
            "",
            "## 延迟与成本审计",
            "",
            "| Scenario | Prefit annual / DD / win / trades | Holdout annual / DD / win / trades |",
            "| --- | --- | --- |",
        ]
    )
    for scenario in scenarios:
        metrics = scenario["metrics"]
        prefit = metrics["prefit"]
        holdout = metrics["reused_holdout"]
        lines.append(
            f"| `{scenario['scenario']}` | `{prefit['annual_multiple']:.4f}x` / "
            f"`{prefit['max_dd']:.2%}` / `{prefit['win_rate']:.2%}` / "
            f"`{int(prefit['trades'])}` | `{holdout['annual_multiple']:.4f}x` / "
            f"`{holdout['max_dd']:.2%}` / `{holdout['win_rate']:.2%}` / "
            f"`{int(holdout['trades'])}` |"
        )
    lines.extend(
        [
            "",
            "## 稳健性补充",
            "",
            (
                f"- one-at-a-time 邻域 `{len(neighborhood)}` 行，其中继续通过 prefit "
                f"高胜率频率门槛 `{int(neighborhood['prefit_gate'].sum())}` 行。"
            ),
            (
                f"- prefit bootstrap `{bootstrap['samples']}` 次：正权益比例 "
                f"`{bootstrap['positive_equity_rate']:.2%}`，胜率 `>=80%` 比例 "
                f"`{bootstrap['win_ge_80_rate']:.2%}`。"
            ),
            "",
            "## 研究边界",
            "",
            "- 本轮观察值未登记为 V4；需要用户明确要求后才更新主账和 canonical spec。",
            "- reused holdout 已多次揭盲，只能作冻结后失败边界，不能替代 fresh forward。",
            f"- 当前数据截止 `{v1.FULL_END.isoformat()}`；该时间之后的新增数据尚未进入本次回测。",
            "- 即使历史审计改善，仍需至少 `20-30` 笔 fresh forward 或 `2-3` 个月，且通过 live-executable 审计后才能 promotion。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{BB_POOL_CSV.name}`",
            f"- `artifacts/{RSI_POOL_CSV.name}`",
            f"- `artifacts/{CANDIDATES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{NEIGHBORHOOD_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/eth/1h-adaptive-regime/scripts/"
            "research_eth_1h_ar_v3_high_win_frequency_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            json_safe(
                {
                    "observation_id": payload["observation_id"],
                    "search_counts": payload["search_counts"],
                    "selected_metrics": {
                        window: {
                            key: selected_metrics[window][key]
                            for key in (
                                "annual_multiple",
                                "total_return",
                                "max_dd",
                                "win_rate",
                                "trades",
                            )
                        }
                        for window in selected_metrics
                    },
                    "selected_robust_gate": selected.robust_gate,
                    "neighborhood": payload["neighborhood"],
                    "bootstrap_prefit": bootstrap,
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
