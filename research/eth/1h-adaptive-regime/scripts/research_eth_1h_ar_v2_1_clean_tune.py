from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v2_1 as v21  # noqa: E402
import eth_1h_ar_v2_1_clean as clean21  # noqa: E402
import research_eth_1h_ar_v2_full_ablation as v2_ablation  # noqa: E402


DATE_TAG = "2026-07-07"
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
V2_1_ABLATION_JSON = ARTIFACT_DIR / "eth_1h_ar_v2_1_full_ablation_2026-07-07.json"
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v2_1_clean_tune_{DATE_TAG}.json"
BB_POOL_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_tune_bb_break_pool_{DATE_TAG}.csv"
RSI_POOL_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_tune_rsi_pool_{DATE_TAG}.csv"
CANDIDATES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_clean_tune_candidates_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_clean_tune_trades_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_clean_tune_slices_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"eth-1h-ar-v2-1-clean-tune-{DATE_TAG}.md"

DD_FLOOR = -0.20
json_safe = v2_ablation.json_safe


class LegCandidate:
    def __init__(
        self,
        *,
        clean_config: Any,
        trades: list[Any],
        metrics: dict[str, dict[str, float]],
        score: float,
    ) -> None:
        self.clean_config = clean_config
        self.trades = trades
        self.metrics = metrics
        self.score = score


class PairCandidate:
    def __init__(
        self,
        *,
        bb_break: clean21.BBBreakV21CleanConfig,
        rsi: clean21.RSIV21CleanConfig,
        trades: list[Any],
        metrics: dict[str, dict[str, float]],
        score: float,
        strict_gate: bool,
    ) -> None:
        self.bb_break = bb_break
        self.rsi = rsi
        self.trades = trades
        self.metrics = metrics
        self.score = score
        self.strict_gate = strict_gate
        self.k2_metrics: dict[str, dict[str, float]] | None = None
        self.slip8_metrics: dict[str, dict[str, float]] | None = None
        self.robust_score = -1e9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean-surface strict-improvement tune for ETH-1H-Adaptive-Regime-V2.1 "
            "(27 active params after V2.1 full ablation)."
        )
    )
    parser.add_argument("--leg-samples", type=int, default=100_000)
    parser.add_argument("--leg-keep", type=int, default=400)
    parser.add_argument("--pair-keep", type=int, default=2_500)
    parser.add_argument("--robust-keep", type=int, default=600)
    parser.add_argument("--seed", type=int, default=2026070701)
    parser.add_argument("--progress-every", type=int, default=20_000)
    return parser.parse_args()


def flatten(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def leg_score(metrics: dict[str, dict[str, float]]) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if prefit["trades"] < 12 or validation["trades"] < 4:
        return -1e9
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_annual = min(
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    )
    score = (
        1.1 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.9 * math.log(min_annual)
        + 2.5 * min_win
        + 0.25 * min(prefit["profit_factor"], 8.0)
        - max(0.0, 0.85 - min_win) * 5.0
        - max(0.0, DD_FLOOR - worst_dd) * 25.0
        - max(0.0, -0.15 - worst_dd) * 6.0
    )
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        score -= 8.0
    return float(score)


def pair_strict_gate(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> bool:
    """相对 V2.1 收益更高、胜率更高、回撤更小，且 train/validation 稳健。"""
    prefit = metrics["prefit"]
    ref = reference["prefit"]
    return bool(
        prefit["annual_multiple"] > ref["annual_multiple"]
        and prefit["win_rate"] > ref["win_rate"]
        and prefit["max_dd"] > ref["max_dd"]
        and metrics["train"]["total_return"] > 0.0
        and metrics["validation"]["total_return"] > 0.0
        and metrics["train"]["max_dd"] > DD_FLOOR
        and metrics["validation"]["max_dd"] > DD_FLOOR
        and metrics["train"]["win_rate"] >= 0.80
        and metrics["validation"]["win_rate"] >= 0.80
    )


def pair_score(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if prefit["trades"] < 30 or validation["trades"] < 8:
        return -1e9
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_annual = min(
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    )
    score = (
        1.3 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.0 * math.log(min_annual)
        + 4.0 * min_win
        + 0.4 * min(prefit["profit_factor"], 8.0)
        + 6.0 * worst_dd
        - max(0.0, DD_FLOOR - worst_dd) * 35.0
    )
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        score -= 10.0
    if pair_strict_gate(metrics, reference):
        score += 10.0
    return float(score)


def robust_score(candidate: PairCandidate) -> float:
    assert candidate.k2_metrics is not None
    assert candidate.slip8_metrics is not None
    metrics_set = [
        candidate.metrics["prefit"],
        candidate.k2_metrics["prefit"],
        candidate.slip8_metrics["prefit"],
    ]
    min_win = min(item["win_rate"] for item in metrics_set)
    min_annual = min(item["annual_multiple"] for item in metrics_set)
    worst_dd = min(item["max_dd"] for item in metrics_set)
    score = (
        candidate.score
        + 1.2 * math.log(max(min_annual, 1e-9))
        + 3.0 * min_win
        + 6.0 * worst_dd
        - max(0.0, DD_FLOOR - worst_dd) * 30.0
    )
    if candidate.strict_gate:
        score += 10.0
    return float(score)


def random_bb_break(rng: random.Random) -> clean21.BBBreakV21CleanConfig:
    return clean21.BBBreakV21CleanConfig(
        indicator_window=rng.choice((12, 20, 32, 48, 72, 96)),
        band_k=rng.choice((1.5, 1.75, 2.0, 2.25, 2.5, 3.0)),
        roc_window=rng.choice((6, 12, 24, 48, 72)),
        min_adx=rng.choice((16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 40.0)),
        min_rvol=rng.choice((1.5, 2.0, 2.5, 3.0, 3.5)),
        min_atr_bps=rng.choice((0.0, 50.0, 75.0, 100.0, 125.0)),
        min_dir_roc_bps=rng.choice((-200.0, -100.0, 0.0, 50.0, 100.0, 200.0)),
        max_dist_ema_bps=rng.choice((750.0, 1000.0, 1500.0, 2500.0, 10_000.0)),
        tp_atr=rng.choice((2.0, 2.5, 3.0, 3.5, 4.0)),
        sl_atr=rng.choice((2.5, 3.0, 3.5, 4.0, 5.0)),
        max_hold_bars=rng.choice((18, 24, 36, 48, 72)),
        fixed_leverage=rng.choice((1.5, 2.0, 2.5, 3.0)),
    )


def random_rsi(rng: random.Random) -> clean21.RSIV21CleanConfig:
    low = rng.choice((5.0, 10.0, 15.0, 20.0, 25.0))
    high_choices = tuple(
        item for item in (55.0, 60.0, 65.0, 70.0, 75.0, 80.0) if item > low
    )
    return clean21.RSIV21CleanConfig(
        ema_htf=rng.choice((89, 144, 233, 377)),
        indicator_window=rng.choice((5, 7, 9, 14, 21)),
        threshold_low=low,
        threshold_high=rng.choice(high_choices),
        roc_window=rng.choice((3, 6, 12, 24, 48)),
        min_adx=rng.choice((0.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0)),
        max_adx=rng.choice((30.0, 36.0, 45.0, 55.0, 100.0)),
        min_atr_bps=rng.choice((50.0, 75.0, 100.0, 125.0, 150.0)),
        min_dir_roc_bps=rng.choice((-10_000.0, -300.0, -100.0, 0.0, 50.0, 100.0)),
        max_dist_ema_bps=rng.choice((500.0, 750.0, 1000.0, 1500.0, 2500.0)),
        tp_atr=rng.choice((1.5, 2.0, 2.5, 3.0, 3.5)),
        sl_atr=rng.choice((1.5, 2.0, 2.5, 3.0)),
        max_hold_bars=rng.choice((12, 18, 24, 36, 48)),
        cooldown_bars=rng.choice((0, 6, 12, 24, 36)),
        fixed_leverage=rng.choice((1.0, 1.5, 2.0, 2.5)),
    )


def retain(retained: list[Any], candidate: Any, keep: int) -> list[Any]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained


def config_key(cfg: Any) -> tuple[Any, ...]:
    return tuple(asdict(cfg).values())


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
    retained: list[LegCandidate] = []
    seen: set[tuple[Any, ...]] = set()
    evaluated = 0
    eligible = 0
    baseline_cfg: Any = (
        clean21.BBBreakV21CleanConfig()
        if component == "bb_break"
        else clean21.RSIV21CleanConfig()
    )
    candidates = [baseline_cfg]
    for _ in range(samples):
        candidates.append(
            random_bb_break(rng) if component == "bb_break" else random_rsi(rng)
        )
    for index, cfg in enumerate(candidates, start=1):
        key = config_key(cfg)
        if key in seen:
            continue
        seen.add(key)
        base_cfg = (
            clean21.bb_to_v1_clean(cfg)
            if component == "bb_break"
            else clean21.rsi_to_v1_clean(cfg)
        )
        trades = v1.simulate_component(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            clean21.v1_clean.bb_break_to_base(engine, base_cfg)
            if component == "bb_break"
            else clean21.v1_clean.rsi_to_base(engine, base_cfg),
        )
        metrics = v1.metrics(engine, trades)
        score = leg_score(metrics)
        evaluated += 1
        if score <= -1e8:
            continue
        eligible += 1
        retained = retain(
            retained,
            LegCandidate(clean_config=cfg, trades=trades, metrics=metrics, score=score),
            keep,
        )
        if index % progress_every == 0 and retained:
            best = max(retained, key=lambda item: item.score)
            print(
                f"{component} {index}/{len(candidates)} evaluated={evaluated} "
                f"eligible={eligible} retained={len(retained)} "
                f"best_score={best.score:.3f} "
                f"ann={best.metrics['prefit']['annual_multiple']:.3f} "
                f"win={best.metrics['prefit']['win_rate']:.2%} "
                f"dd={best.metrics['prefit']['max_dd']:.2%}",
                flush=True,
            )
    return sorted(retained, key=lambda item: item.score, reverse=True)[:keep], {
        "generated": len(candidates),
        "unique_evaluated": evaluated,
        "eligible": eligible,
        "retained": min(len(retained), keep),
    }


def leg_rows(pool: list[LegCandidate]) -> list[dict[str, Any]]:
    return [
        {"score": item.score, **asdict(item.clean_config), **flatten(item.metrics)}
        for item in pool
    ]


def pair_row(candidate: PairCandidate) -> dict[str, Any]:
    row = {
        "score": candidate.score,
        "robust_score": candidate.robust_score,
        "strict_gate": candidate.strict_gate,
        **{f"bb_{key}": value for key, value in asdict(candidate.bb_break).items()},
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


def scenario_metrics(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    bb_break: clean21.BBBreakV21CleanConfig,
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
        bb_break=bb_break,
        rsi=rsi,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )
    return trades, v1.metrics(engine, trades)


def main() -> None:
    args = parse_args()
    if not V2_1_ABLATION_JSON.exists():
        raise FileNotFoundError("Run V2.1 full ablation before V2.1 clean tune")
    ablation_summary = json.loads(V2_1_ABLATION_JSON.read_text(encoding="utf-8"))
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    engine, frame, funding, quality = v21.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    baseline_trades, *_ = v21.simulate_v2_1(engine, frame, funding_times, funding_cumulative)
    baseline_metrics = v1.metrics(engine, baseline_trades)
    baseline_slices = v21.standard_slices(engine, baseline_trades)

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
    eligible_pairs = 0
    strict_count = 0
    for bb_item in bb_pool:
        for rsi_item in rsi_pool:
            merged = engine.merge_trade_sets(
                bb_item.trades,
                rsi_item.trades,
                bb_item.score,
                rsi_item.score,
            )
            metrics = v1.metrics(engine, merged)
            score = pair_score(metrics, baseline_metrics)
            evaluated_pairs += 1
            if score <= -1e8:
                continue
            eligible_pairs += 1
            strict = pair_strict_gate(metrics, baseline_metrics)
            strict_count += int(strict)
            pairs = retain(
                pairs,
                PairCandidate(
                    bb_break=bb_item.clean_config,
                    rsi=rsi_item.clean_config,
                    trades=merged,
                    metrics=metrics,
                    score=score,
                    strict_gate=strict,
                ),
                args.pair_keep,
            )
    pairs = sorted(pairs, key=lambda item: item.score, reverse=True)[: args.pair_keep]
    if not pairs:
        raise RuntimeError("No pair candidates survived scoring")
    print(
        f"pairs evaluated={evaluated_pairs} eligible={eligible_pairs} "
        f"strict={strict_count} retained={len(pairs)}",
        flush=True,
    )

    for index, candidate in enumerate(pairs[: args.robust_keep], start=1):
        _k2, candidate.k2_metrics = scenario_metrics(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            candidate.bb_break,
            candidate.rsi,
            delay=2,
            fee=0.001,
            slippage=0.0004,
        )
        _s8, candidate.slip8_metrics = scenario_metrics(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            candidate.bb_break,
            candidate.rsi,
            delay=1,
            fee=0.001,
            slippage=0.0008,
        )
        candidate.robust_score = robust_score(candidate)
        if index % 100 == 0:
            print(f"robust {index}/{min(len(pairs), args.robust_keep)}", flush=True)

    robust = sorted(
        pairs[: args.robust_keep], key=lambda item: item.robust_score, reverse=True
    )
    strict_robust = [item for item in robust if item.strict_gate]
    selected = strict_robust[0] if strict_robust else robust[0]
    selection_reason = (
        "strict_improvement_vs_v2_1_then_robust_score"
        if strict_robust
        else "no_strict_improvement_best_robust_frontier"
    )
    selected_metrics = v1.metrics(engine, selected.trades)
    selected_slices = v21.standard_slices(engine, selected.trades)

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
            metrics = selected_metrics
        else:
            _trades, metrics = scenario_metrics(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                selected.bb_break,
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

    pd.DataFrame([pair_row(item) for item in robust[: min(600, len(robust))]]).to_csv(
        CANDIDATES_CSV, index=False
    )
    pd.DataFrame(engine.trade_rows(selected.trades)).to_csv(TRADES_CSV, index=False)
    pd.DataFrame(
        [{"window": name, **metric} for name, metric in selected_slices.items()]
    ).to_csv(SLICES_CSV, index=False)

    strict_gate_pass = selected.strict_gate
    full_gate_pass = bool(
        selected_metrics["current_full"]["annual_multiple"]
        > baseline_metrics["current_full"]["annual_multiple"]
        and selected_metrics["current_full"]["win_rate"]
        > baseline_metrics["current_full"]["win_rate"]
        and selected_metrics["current_full"]["max_dd"]
        > baseline_metrics["current_full"]["max_dd"]
    )
    holdout_gate_pass = bool(
        selected_metrics["reused_holdout"]["total_return"] > 0.0
        and selected_metrics["reused_holdout"]["win_rate"] >= 0.80
        and selected_metrics["reused_holdout"]["max_dd"] > DD_FLOOR
    )

    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "baseline_version": "ETH-1H-Adaptive-Regime-V2.1",
        "observation_id": "ETH-1H-AR-V2-1-CLEAN-TUNE-2026-07-07",
        "status": "diagnostic_observation_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "candidate_source": (
                "27-param V2.1 clean surface after full ablation "
                "(bb ema_htf / max_aligned_funding_bps hardcoded)"
            ),
            "strict_gate": (
                "prefit annual/win higher and DD smaller than V2.1, "
                "train/validation positive, DD<20%, win>=80%"
            ),
            "reused_holdout": "read_only_after_freeze_not_used_for_selection",
            "recent_slices": "read_only_after_freeze_not_used_for_selection",
            "selection_reason": selection_reason,
        },
        "search_counts": {
            "leg_samples_each": args.leg_samples,
            "bb_break": bb_counts,
            "rsi_reversal": rsi_counts,
            "evaluated_pairs": evaluated_pairs,
            "eligible_pairs": eligible_pairs,
            "strict_gate_pairs": strict_count,
            "retained_pairs": len(pairs),
            "robust_evaluated": min(len(pairs), args.robust_keep),
            "strict_robust_candidates": len(strict_robust),
        },
        "v2_1_ablation": {
            "summary_json": str(V2_1_ABLATION_JSON.relative_to(ROOT)),
            "inert_fields": ablation_summary.get("inert_fields"),
            "active_tunable_counts": ablation_summary.get("active_tunable_counts"),
        },
        "baseline": {
            "metrics": baseline_metrics,
            "standard_slices": baseline_slices,
        },
        "selected": {
            "bb_break": asdict(selected.bb_break),
            "rsi_reversal": asdict(selected.rsi),
            "metrics": selected_metrics,
            "standard_slices": selected_slices,
            "strict_gate_pass": strict_gate_pass,
            "full_gate_pass_after_freeze": full_gate_pass,
            "reused_holdout_gate_pass_after_freeze": holdout_gate_pass,
            "score": selected.score,
            "robust_score": selected.robust_score,
        },
        "scenarios": scenarios,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "artifacts": {
            "bb_pool_csv": str(BB_POOL_CSV.relative_to(ROOT)),
            "rsi_pool_csv": str(RSI_POOL_CSV.relative_to(ROOT)),
            "candidates_csv": str(CANDIDATES_CSV.relative_to(ROOT)),
            "trades_csv": str(TRADES_CSV.relative_to(ROOT)),
            "slices_csv": str(SLICES_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# ETH-1H-Adaptive-Regime-V2.1 Clean 参数微调 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "本轮在 V2.1 全参数消融后的 `27` 个 active clean 参数上做搜索"
            "（`bb_break.ema_htf` 与 `bb_break.max_aligned_funding_bps` 判定为"
            " merged-path inert，已硬编码为 V2.1 冻结值）。"
            "选择只使用 train/validation/prefit；reused holdout 与近期分片只作冻结后审计。"
        ),
        "",
        f"- 每腿随机样本：`{args.leg_samples}`；保留 BB breakout/RSI：`{len(bb_pool)}` / `{len(rsi_pool)}`。",
        (
            f"- 组合评估：`{evaluated_pairs}`；可评分：`{eligible_pairs}`；"
            f"相对 V2.1“收益更高、胜率更高、回撤更小”的严格改善组合：`{strict_count}`。"
        ),
        (
            f"- 选中观察值：`ETH-1H-AR-V2-1-CLEAN-TUNE-2026-07-07`；"
            f"selection reason `{selection_reason}`。"
        ),
        (
            f"- strict gate pass：`{strict_gate_pass}`；"
            f"冻结后 current full 三项同时改善：`{full_gate_pass}`；"
            f"reused holdout gate pass：`{holdout_gate_pass}`。"
        ),
        "",
        "## V2.1 vs 微调观察",
        "",
        "| Window | V2.1 annual / return / DD / win / trades | Tune annual / return / DD / win / trades |",
        "| --- | --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(
            f"| `{window}` | {metric_line(baseline_metrics[window])} | "
            f"{metric_line(selected_metrics[window])} |"
        )
    lines.extend(["", "## 冻结参数", "", "### BB breakout clean（12 参数）", ""])
    lines.extend(
        f"- `{key}` = `{value}`" for key, value in asdict(selected.bb_break).items()
    )
    lines.extend(
        [
            "",
            f"- 硬编码：`ema_htf` = `{clean21.BB_EMA_HTF_FIXED}`；"
            f"`max_aligned_funding_bps` = `{clean21.BB_MAX_ALIGNED_FUNDING_BPS_FIXED}`。",
            "",
            "### RSI clean（15 参数）",
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
            "| Scenario | Prefit annual / DD / win | Holdout annual / DD / win | Full annual / DD / win |",
            "| --- | --- | --- | --- |",
        ]
    )
    for scenario in scenarios:
        metrics = scenario["metrics"]
        prefit = metrics["prefit"]
        holdout = metrics["reused_holdout"]
        full = metrics["current_full"]
        lines.append(
            f"| `{scenario['scenario']}` | `{prefit['annual_multiple']:.4f}x` / "
            f"`{prefit['max_dd']:.2%}` / `{prefit['win_rate']:.2%}` | "
            f"`{holdout['annual_multiple']:.4f}x` / `{holdout['max_dd']:.2%}` / "
            f"`{holdout['win_rate']:.2%}` | `{full['annual_multiple']:.4f}x` / "
            f"`{full['max_dd']:.2%}` / `{full['win_rate']:.2%}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 这是 V2.1 clean 参数面的微调观察值，不自动登记新版本，也不是 promotion。",
            "- reused holdout 已在 V1/V2/V2.1 阶段揭盲，只能做冻结后失败/边界审计，不能作为 fresh OOS。",
            "- 若 reused holdout 或近期分片失败，应视为失败诊断而不是候选策略。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{BB_POOL_CSV.name}`",
            f"- `artifacts/{RSI_POOL_CSV.name}`",
            f"- `artifacts/{CANDIDATES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_1_clean_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            json_safe(
                {
                    "selection_reason": selection_reason,
                    "strict_gate_pairs": strict_count,
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
                    "strict_gate_pass": strict_gate_pass,
                    "full_gate_pass_after_freeze": full_gate_pass,
                    "reused_holdout_gate_pass_after_freeze": holdout_gate_pass,
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
