from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v1_clean as clean  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-02"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v1_clean_tune_{DATE_TAG}.json"
KELTNER_POOL_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_tune_keltner_pool_{DATE_TAG}.csv"
CCI_POOL_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_tune_cci_pool_{DATE_TAG}.csv"
PAIR_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_tune_pairs_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_tune_selected_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"btc-1h-ar-v1-clean-parameter-tune-{DATE_TAG}.md"


@dataclass(slots=True)
class LegCandidate:
    clean_config: Any
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    score: float


@dataclass(slots=True)
class PairCandidate:
    keltner: Any
    cci: Any
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    score: float
    strict_improvement: bool
    k2_metrics: dict[str, dict[str, float]] | None = None
    slip8_metrics: dict[str, dict[str, float]] | None = None
    robust_score: float = -1e9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prefit-only clean-surface tune for BTC-1H-Adaptive-Regime-V1."
    )
    parser.add_argument("--leg-samples", type=int, default=150_000)
    parser.add_argument("--leg-keep", type=int, default=350)
    parser.add_argument("--pair-keep", type=int, default=2_000)
    parser.add_argument("--robust-keep", type=int, default=500)
    parser.add_argument("--seed", type=int, default=2026070202)
    parser.add_argument("--progress-every", type=int, default=10_000)
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
    if prefit["trades"] < 20 or validation["trades"] < 5:
        return -1e9
    annuals = [
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    ]
    dd_penalty = sum(
        max(0.0, -0.25 - item["max_dd"]) * 15.0
        for item in (train, validation, prefit)
    )
    win_penalty = sum(
        max(0.0, 0.45 - item["win_rate"]) * 8.0
        for item in (train, validation, prefit)
    )
    negative_penalty = 5.0 * sum(
        item["total_return"] <= 0 for item in (train, validation)
    )
    return float(
        0.8 * math.log(min(annuals[2], 1e6))
        + 0.9 * math.log(min(annuals[0], annuals[1]))
        + 0.25 * min(prefit["profit_factor"], 5.0)
        + 0.5 * prefit["win_rate"]
        - dd_penalty
        - win_penalty
        - negative_penalty
    )


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
    if prefit["trades"] < 60 or validation["trades"] < 18:
        return -1e9
    annuals = [
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    ]
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    score = (
        1.0 * math.log(min(prefit["annual_multiple"], 1e6))
        + 1.1 * math.log(min(annuals[0], annuals[1]))
        + 0.35 * min(prefit["profit_factor"], 5.0)
        + 0.5 * min_win
        - max(0.0, -0.20 - worst_dd) * 25.0
        - max(0.0, 0.50 - min_win) * 10.0
    )
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        score -= 8.0
    if pair_strict_improvement(metrics, reference):
        score += 10.0
    return float(score)


def random_keltner(rng: random.Random) -> clean.KeltnerCleanConfig:
    return clean.KeltnerCleanConfig(
        indicator_window=rng.choice((12, 20, 32, 48, 72, 96)),
        band_k=rng.choice((1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0)),
        roc_window=rng.choice((6, 12, 24, 48, 72, 168)),
        min_adx=rng.choice((20.0, 24.0, 28.0, 32.0, 36.0, 40.0)),
        min_rvol=rng.choice((0.0, 0.6, 0.8, 1.0, 1.25, 1.5)),
        max_atr_bps=rng.choice((150.0, 200.0, 250.0, 300.0, 400.0, 600.0)),
        min_dir_roc_bps=rng.choice((-200.0, -100.0, 0.0, 50.0, 100.0, 200.0)),
        htf_mode=rng.choice(("none", "h4", "h12", "d1")),
        max_aligned_funding_bps=rng.choice((1.0, 2.0, 4.0, 8.0, 10000.0)),
        tp_atr=rng.choice((1.0, 1.25, 1.5, 2.0, 2.5, 3.0)),
        sl_atr=rng.choice((2.5, 3.0, 3.5, 4.0, 4.5, 5.0)),
        max_hold_bars=rng.choice((48, 72, 96, 120, 168, 240)),
        cooldown_bars=rng.choice((0, 3, 6, 12, 24)),
        fixed_leverage=rng.choice((1.5, 2.0, 2.5, 3.0, 3.5, 4.0)),
    )


def random_cci(rng: random.Random) -> clean.CCICleanConfig:
    return clean.CCICleanConfig(
        ema_htf=rng.choice((55, 89, 144, 233, 377)),
        indicator_window=rng.choice((14, 20, 40, 72)),
        threshold_high=rng.choice((75.0, 100.0, 125.0, 150.0, 200.0)),
        max_adx=rng.choice((24.0, 30.0, 36.0, 45.0, 100.0)),
        min_rvol=rng.choice((0.0, 0.8, 1.0, 1.25, 1.5, 2.0)),
        min_atr_bps=rng.choice((0.0, 50.0, 75.0, 100.0, 150.0)),
        max_atr_bps=rng.choice((200.0, 250.0, 300.0, 400.0, 600.0, 10000.0)),
        max_dist_ema_bps=rng.choice((500.0, 750.0, 1000.0, 1500.0, 2500.0, 10000.0)),
        tp_atr=rng.choice((2.0, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0)),
        sl_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5)),
        max_hold_bars=rng.choice((48, 72, 96, 120, 168)),
        cooldown_bars=rng.choice((0, 12, 24, 36, 48)),
        fixed_leverage=rng.choice((1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5)),
    )


def retain_legs(
    retained: list[LegCandidate], candidate: LegCandidate, keep: int
) -> list[LegCandidate]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained


def retain_pairs(
    retained: list[PairCandidate], candidate: PairCandidate, keep: int
) -> list[PairCandidate]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained


def config_key(cfg: Any) -> tuple[Any, ...]:
    return tuple(asdict(cfg).values())


def build_leg_pool(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    rng: random.Random,
    component: str,
    samples: int,
    keep: int,
    progress_every: int,
) -> tuple[list[LegCandidate], dict[str, int]]:
    retained: list[LegCandidate] = []
    seen: set[tuple[Any, ...]] = set()
    evaluated = 0
    eligible = 0
    baseline_cfg: Any = (
        clean.KeltnerCleanConfig()
        if component == "keltner"
        else clean.CCICleanConfig()
    )
    candidates = [baseline_cfg]
    for _ in range(samples):
        candidates.append(
            random_keltner(rng) if component == "keltner" else random_cci(rng)
        )
    for index, cfg in enumerate(candidates, start=1):
        key = config_key(cfg)
        if key in seen:
            continue
        seen.add(key)
        base_cfg = (
            clean.keltner_to_base(engine, cfg)
            if component == "keltner"
            else clean.cci_to_base(engine, cfg)
        )
        trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, base_cfg
        )
        metrics = prefit_metrics(engine, trades)
        score = leg_score(metrics)
        evaluated += 1
        if score <= -1e8:
            continue
        eligible += 1
        retained = retain_legs(
            retained,
            LegCandidate(
                clean_config=cfg,
                trades=trades,
                metrics=metrics,
                score=score,
            ),
            keep,
        )
        if index % progress_every == 0 and retained:
            best = max(retained, key=lambda item: item.score)
            print(
                f"{component} {index}/{len(candidates)} evaluated={evaluated} "
                f"eligible={eligible} retained={len(retained)} "
                f"best_score={best.score:.3f} "
                f"ann={best.metrics['prefit']['annual_multiple']:.3f} "
                f"dd={best.metrics['prefit']['max_dd']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained, {
        "generated": len(candidates),
        "unique_evaluated": evaluated,
        "eligible": eligible,
        "retained": len(retained),
    }


def simulate_pair_scenario(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    keltner: Any,
    cci: Any,
    delay: int,
    fee: float,
    slippage: float,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    original_fee = engine.FEE_PER_FILL
    original_slippage = engine.SLIPPAGE_PER_FILL
    engine.FEE_PER_FILL = fee
    engine.SLIPPAGE_PER_FILL = slippage
    try:
        k_cfg = replace(
            clean.keltner_to_base(engine, keltner), entry_delay_bars=delay
        )
        c_cfg = replace(clean.cci_to_base(engine, cci), entry_delay_bars=delay)
        k_trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, k_cfg
        )
        c_trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, c_cfg
        )
        k_score = leg_score(prefit_metrics(engine, k_trades))
        c_score = leg_score(prefit_metrics(engine, c_trades))
        merged = engine.merge_trade_sets(k_trades, c_trades, k_score, c_score)
        return merged, prefit_metrics(engine, merged)
    finally:
        engine.FEE_PER_FILL = original_fee
        engine.SLIPPAGE_PER_FILL = original_slippage


def robust_score(candidate: PairCandidate) -> float:
    assert candidate.k2_metrics is not None
    assert candidate.slip8_metrics is not None
    metrics_set = [
        candidate.metrics["prefit"],
        candidate.k2_metrics["prefit"],
        candidate.slip8_metrics["prefit"],
    ]
    min_annual = min(item["annual_multiple"] for item in metrics_set)
    worst_dd = min(item["max_dd"] for item in metrics_set)
    min_win = min(item["win_rate"] for item in metrics_set)
    score = (
        candidate.score
        + 1.5 * math.log(max(min_annual, 1e-9))
        - max(0.0, -0.25 - worst_dd) * 30.0
        - max(0.0, 0.45 - min_win) * 10.0
    )
    if candidate.strict_improvement:
        score += 5.0
    if (
        min_annual > 1.0
        and worst_dd > -0.30
        and min_win >= 0.45
    ):
        score += 4.0
    return float(score)


def robust_prefit_gate(metrics: dict[str, dict[str, float]]) -> bool:
    return all(
        item["total_return"] > 0
        and item["max_dd"] > -0.20
        and item["win_rate"] >= 0.50
        for item in (
            metrics["train"],
            metrics["validation"],
            metrics["prefit"],
        )
    )


def all_window_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.metrics(engine, trades)


def pair_row(candidate: PairCandidate) -> dict[str, Any]:
    row = {
        "score": candidate.score,
        "robust_score": candidate.robust_score,
        "strict_improvement": candidate.strict_improvement,
        **{f"k_{key}": value for key, value in asdict(candidate.keltner).items()},
        **{f"c_{key}": value for key, value in asdict(candidate.cci).items()},
        **flatten(candidate.metrics),
    }
    if candidate.k2_metrics is not None:
        row.update(
            {
                f"k2_{key}": value
                for key, value in flatten(candidate.k2_metrics).items()
            }
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
        {
            "score": item.score,
            **asdict(item.clean_config),
            **flatten(item.metrics),
        }
        for item in pool
    ]


def fmt_metric(metric: dict[str, float]) -> str:
    return (
        f"annual `{metric['annual_multiple']:.4f}x`，"
        f"return `{metric['total_return']:.2%}`，"
        f"DD `{metric['max_dd']:.2%}`，"
        f"win `{metric['win_rate']:.2%}`，"
        f"trades `{int(metric['trades'])}`，PF `{metric['profit_factor']:.3f}`"
    )


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
    reference_all = all_window_metrics(engine, reference_trades)

    rng = random.Random(args.seed)
    keltner_pool, k_counts = build_leg_pool(
        engine=engine,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        rng=rng,
        component="keltner",
        samples=args.leg_samples,
        keep=args.leg_keep,
        progress_every=args.progress_every,
    )
    cci_pool, c_counts = build_leg_pool(
        engine=engine,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        rng=rng,
        component="cci",
        samples=args.leg_samples,
        keep=args.leg_keep,
        progress_every=args.progress_every,
    )
    pd.DataFrame(leg_rows(keltner_pool)).to_csv(KELTNER_POOL_CSV, index=False)
    pd.DataFrame(leg_rows(cci_pool)).to_csv(CCI_POOL_CSV, index=False)

    pairs: list[PairCandidate] = []
    strict_count = 0
    evaluated_pairs = 0
    eligible_pairs = 0
    for keltner_item in keltner_pool:
        for cci_item in cci_pool:
            merged = engine.merge_trade_sets(
                keltner_item.trades,
                cci_item.trades,
                keltner_item.score,
                cci_item.score,
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
                    keltner=keltner_item.clean_config,
                    cci=cci_item.clean_config,
                    trades=merged,
                    metrics=metrics,
                    score=score,
                    strict_improvement=strict,
                ),
                args.pair_keep,
            )
    pairs = sorted(pairs, key=lambda item: item.score, reverse=True)[: args.pair_keep]
    print(
        f"pairs evaluated={evaluated_pairs} eligible={eligible_pairs} "
        f"strict={strict_count} retained={len(pairs)}",
        flush=True,
    )

    for index, candidate in enumerate(pairs[: args.robust_keep], start=1):
        _k2_trades, candidate.k2_metrics = simulate_pair_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            keltner=candidate.keltner,
            cci=candidate.cci,
            delay=2,
            fee=0.001,
            slippage=0.0004,
        )
        _slip_trades, candidate.slip8_metrics = simulate_pair_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            keltner=candidate.keltner,
            cci=candidate.cci,
            delay=1,
            fee=0.001,
            slippage=0.0008,
        )
        candidate.robust_score = robust_score(candidate)
        if index % 50 == 0:
            print(f"robust {index}/{min(len(pairs), args.robust_keep)}", flush=True)
    robust = sorted(
        pairs[: args.robust_keep],
        key=lambda item: item.robust_score,
        reverse=True,
    )
    strict_robust = [item for item in robust if item.strict_improvement]
    live_robust = [
        item
        for item in strict_robust
        if item.k2_metrics is not None
        and item.slip8_metrics is not None
        and robust_prefit_gate(item.k2_metrics)
        and robust_prefit_gate(item.slip8_metrics)
    ]
    selected = live_robust[0] if live_robust else (
        strict_robust[0] if strict_robust else robust[0]
    )
    selection_reason = (
        "prefit_strict_improvement_k2_slip8_all_windows_gate_then_robust_score"
        if live_robust
        else "prefit_strict_improvement_then_robust_score"
        if strict_robust
        else "no_strict_improvement_robust_frontier"
    )

    selected_all = all_window_metrics(engine, selected.trades)
    scenario_specs = [
        ("base_k1", 1, 0.001, 0.0004),
        ("delay_k2", 2, 0.001, 0.0004),
        ("delay_k3", 3, 0.001, 0.0004),
        ("slip_8bps", 1, 0.001, 0.0008),
        ("slip_12bps", 1, 0.001, 0.0012),
        ("fee12_slip8", 1, 0.0012, 0.0008),
        ("double_cost", 1, 0.002, 0.0008),
    ]
    scenarios: list[dict[str, Any]] = []
    for name, delay, fee, slippage in scenario_specs:
        if name == "base_k1":
            trades = selected.trades
        else:
            trades, _prefit = simulate_pair_scenario(
                engine=engine,
                frame=frame,
                funding_times=funding_times,
                funding_cumulative=funding_cumulative,
                keltner=selected.keltner,
                cci=selected.cci,
                delay=delay,
                fee=fee,
                slippage=slippage,
            )
        metrics = all_window_metrics(engine, trades)
        scenarios.append(
            {
                "scenario": name,
                "delay": delay,
                "fee_per_fill": fee,
                "slippage_per_fill": slippage,
                "metrics": metrics,
            }
        )

    pd.DataFrame(
        [pair_row(item) for item in robust[: min(500, len(robust))]]
    ).to_csv(PAIR_CSV, index=False)
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

    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "baseline_version": "BTC-1H-Adaptive-Regime-V1",
        "observation_id": "BTC-1H-AR-V1-CLEAN-TUNE-2026-07-02",
        "status": "tuned_observation_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "reused_holdout": "evaluated_once_after_candidate_freeze_not_used_for_selection",
            "reason": selection_reason,
        },
        "search_counts": {
            "leg_samples_each": args.leg_samples,
            "keltner": k_counts,
            "cci": c_counts,
            "evaluated_pairs": evaluated_pairs,
            "eligible_pairs": eligible_pairs,
            "strict_improvement_pair_observations": strict_count,
            "retained_pairs": len(pairs),
            "robust_evaluated": min(len(pairs), args.robust_keep),
            "strict_robust_candidates": len(strict_robust),
            "k2_slip8_all_windows_gate_candidates": len(live_robust),
        },
        "reference_v1": reference_all,
        "selected": {
            "keltner": asdict(selected.keltner),
            "cci": asdict(selected.cci),
            "base_metrics": selected_all,
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
        "# BTC-1H-Adaptive-Regime-V1 Clean 参数微调 - 2026-07-02",
        "",
        "## 结论",
        "",
        (
            "本轮在全参数消融后的 27 个 active clean 参数上做 prefit-only 搜索。"
            f"冻结候选选择规则为 `{selection_reason}`；reused holdout 在冻结后才读取，不参与排序。"
        ),
        "",
        f"- 每腿随机样本：`{args.leg_samples}`；保留 Keltner/CCI：`{len(keltner_pool)}` / `{len(cci_pool)}`。",
        f"- 组合评估：`{evaluated_pairs}`；可评分：`{eligible_pairs}`；prefit 严格改善观察：`{strict_count}`。",
        f"- 完成 K+2 + 8 bps 预拟合稳健审计：`{min(len(pairs), args.robust_keep)}` 个；其中严格改善候选：`{len(strict_robust)}`。",
        f"- 严格改善且 K+2/8 bps 在 train、validation、prefit 全部正收益、胜率 >=50%、DD<20%：`{len(live_robust)}` 个。",
        "",
        "## V1 与冻结微调观察",
        "",
        "| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        ref = reference_all[window]
        tune = selected_all[window]
        lines.append(
            f"| `{window}` | `{ref['annual_multiple']:.4f}x` | `{ref['max_dd']:.2%}` | "
            f"`{ref['win_rate']:.2%}` | `{tune['annual_multiple']:.4f}x` | "
            f"`{tune['max_dd']:.2%}` | `{tune['win_rate']:.2%}` | `{int(tune['trades'])}` |"
        )
    lines.extend(
        [
            "",
            "## 冻结参数",
            "",
            "### Keltner clean",
            "",
        ]
    )
    lines.extend(
        f"- `{key}` = `{value}`" for key, value in asdict(selected.keltner).items()
    )
    lines.extend(["", "### CCI clean", ""])
    lines.extend(
        f"- `{key}` = `{value}`" for key, value in asdict(selected.cci).items()
    )
    lines.extend(
        [
            "",
            "## 延迟与成本审计",
            "",
            "| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout annual | Reused holdout DD | Current full annual | Current full DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for scenario in scenarios:
        metrics = scenario["metrics"]
        prefit = metrics["prefit"]
        holdout = metrics["reused_holdout"]
        current = metrics["current_full"]
        lines.append(
            f"| `{scenario['scenario']}` | `{prefit['annual_multiple']:.4f}x` | "
            f"`{prefit['max_dd']:.2%}` | `{prefit['win_rate']:.2%}` | "
            f"`{holdout['annual_multiple']:.4f}x` | `{holdout['max_dd']:.2%}` | "
            f"`{current['annual_multiple']:.4f}x` | `{current['max_dd']:.2%}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 此结果是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。",
            "- reused holdout 已在 V1 研究中解锁，只能用于失败审计，不能作为新鲜 OOS。",
            "- 只有在收益更高、回撤更小、胜率适中之外，同时通过 K+2、成本压力、参数邻域和新增 forward trades，才允许讨论 promotion。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{KELTNER_POOL_CSV.name}`",
            f"- `artifacts/{CCI_POOL_CSV.name}`",
            f"- `artifacts/{PAIR_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v1_clean_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
