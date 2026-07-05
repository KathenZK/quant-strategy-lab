from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_sol_1h_ar_v1_full_ablation as ablation  # noqa: E402
import sol_1h_ar_v1 as v1  # noqa: E402
import sol_1h_ar_v1_clean as clean  # noqa: E402


FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
DATE_TAG = "2026-07-03"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v1_clean_tune_{DATE_TAG}.json"
LEG_POOL_CSV = ARTIFACT_DIR / f"sol_1h_ar_v1_tune_leg_pool_{DATE_TAG}.csv"
STRATEGY_CSV = ARTIFACT_DIR / f"sol_1h_ar_v1_tune_strategies_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"sol_1h_ar_v1_tune_selected_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"sol-1h-ar-v1-clean-parameter-tune-{DATE_TAG}.md"


@dataclass(slots=True)
class LegCandidate:
    leg_index: int
    clean_config: Any
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    score: float


@dataclass(slots=True)
class StrategyCandidate:
    clean_configs: tuple[Any, ...]
    trades: list[Any]
    metrics: dict[str, dict[str, float]]
    score: float
    strict_improvement: bool
    k2_metrics: dict[str, dict[str, float]] | None = None
    slip8_metrics: dict[str, dict[str, float]] | None = None
    robust_score: float = -1e9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ablation-driven prefit-only clean tune for SOL-1H-Adaptive-Regime-V1."
        )
    )
    parser.add_argument("--leg-samples", type=int, default=250_000)
    parser.add_argument("--leg-keep", type=int, default=400)
    parser.add_argument("--strategy-keep", type=int, default=3_000)
    parser.add_argument("--robust-keep", type=int, default=600)
    parser.add_argument("--seed", type=int, default=2026070304)
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


def moderate_win_rate(value: float) -> float:
    return min(max(value, 0.0), 0.65)


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
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    return float(
        0.9 * math.log(min(annuals[2], 1e6))
        + 0.9 * math.log(min(annuals[0], annuals[1]))
        + 0.30 * min(prefit["profit_factor"], 5.0)
        + 0.50 * moderate_win_rate(prefit["win_rate"])
        - max(0.0, -0.20 - worst_dd) * 30.0
        - max(0.0, 0.45 - min_win) * 10.0
        - 6.0 * sum(item["total_return"] <= 0.0 for item in (train, validation))
    )


def strict_improvement(
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
        and prefit["win_rate"] >= 0.50
        and train["total_return"] > 0.0
        and validation["total_return"] > 0.0
        and train["max_dd"] > -0.20
        and validation["max_dd"] > -0.20
        and train["win_rate"] >= 0.45
        and validation["win_rate"] >= 0.45
    )


def strategy_score(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if prefit["trades"] < 40 or validation["trades"] < 10:
        return -1e9
    annuals = [
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    ]
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    score = (
        1.1 * math.log(min(prefit["annual_multiple"], 1e6))
        + 1.2 * math.log(min(annuals[0], annuals[1]))
        + 0.35 * min(prefit["profit_factor"], 5.0)
        + 0.50 * moderate_win_rate(prefit["win_rate"])
        - max(0.0, -0.20 - worst_dd) * 35.0
        - max(0.0, 0.45 - min_win) * 12.0
    )
    if train["total_return"] <= 0.0 or validation["total_return"] <= 0.0:
        score -= 10.0
    if strict_improvement(metrics, reference):
        score += 12.0
    return float(score)


def valid_base_config(engine: Any, cfg: Any) -> bool:
    macd_valid = (cfg.style != "macd_flip" and not cfg.require_macd_turn) or (
        cfg.macd_fast,
        cfg.macd_slow,
        cfg.macd_signal,
    ) in engine.MACD_SETS
    return bool(
        cfg.ema_fast < cfg.ema_slow
        and cfg.min_adx <= cfg.max_adx
        and cfg.min_atr_bps <= cfg.max_atr_bps
        and macd_valid
    )


def random_clean_config(
    engine: Any,
    rng: random.Random,
    clean_type: type[Any],
    baseline_clean: Any,
    baseline_base: Any,
) -> Any:
    kwargs: dict[str, Any] = {}
    active_fields = list(asdict(baseline_clean))
    macd = rng.choice(engine.MACD_SETS)
    for field_name in active_fields:
        if field_name == "macd_fast":
            value = macd[0]
        elif field_name == "macd_slow":
            value = macd[1]
        elif field_name == "macd_signal":
            value = macd[2]
        else:
            values = ablation.values_for_field(engine, baseline_base, field_name)
            value = rng.choice(values)
        expected = type(getattr(baseline_clean, field_name))
        kwargs[field_name] = expected(value)
    return clean_type(**kwargs)


def config_key(cfg: Any) -> tuple[Any, ...]:
    return tuple(asdict(cfg).items())


def retain_legs(
    retained: list[LegCandidate], candidate: LegCandidate, keep: int
) -> list[LegCandidate]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained


def retain_strategies(
    retained: list[StrategyCandidate], candidate: StrategyCandidate, keep: int
) -> list[StrategyCandidate]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained


def build_leg_pool(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    rng: random.Random,
    leg_index: int,
    clean_type: type[Any],
    baseline_clean: Any,
    baseline_base: Any,
    samples: int,
    keep: int,
    progress_every: int,
) -> tuple[list[LegCandidate], dict[str, int]]:
    retained: list[LegCandidate] = []
    seen: set[tuple[Any, ...]] = set()
    evaluated = 0
    eligible = 0
    candidates = [baseline_clean]
    candidates.extend(
        random_clean_config(engine, rng, clean_type, baseline_clean, baseline_base)
        for _ in range(samples)
    )
    for index, clean_cfg in enumerate(candidates, start=1):
        key = config_key(clean_cfg)
        if key in seen:
            continue
        seen.add(key)
        base_cfg = replace(baseline_base, **asdict(clean_cfg))
        if not valid_base_config(engine, base_cfg):
            continue
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
                leg_index=leg_index,
                clean_config=clean_cfg,
                trades=trades,
                metrics=metrics,
                score=score,
            ),
            keep,
        )
        if index % progress_every == 0 and retained:
            best = max(retained, key=lambda item: item.score)
            print(
                f"leg{leg_index + 1} {index}/{len(candidates)} "
                f"evaluated={evaluated} eligible={eligible} "
                f"best_ann={best.metrics['prefit']['annual_multiple']:.3f} "
                f"best_dd={best.metrics['prefit']['max_dd']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda item: item.score, reverse=True)[:keep]
    return retained, {
        "generated": len(candidates),
        "unique_evaluated": evaluated,
        "eligible": eligible,
        "retained": len(retained),
    }


def merge_legs(engine: Any, legs: tuple[LegCandidate, ...]) -> list[Any]:
    if len(legs) == 1:
        return legs[0].trades
    if len(legs) == 2:
        return engine.merge_trade_sets(
            legs[0].trades,
            legs[1].trades,
            legs[0].score,
            legs[1].score,
        )
    raise RuntimeError(f"Unsupported V1 leg count: {len(legs)}")


def simulate_scenario(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    clean_configs: tuple[Any, ...],
    delay: int,
    fee: float,
    slippage: float,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    original_fee = engine.FEE_PER_FILL
    original_slippage = engine.SLIPPAGE_PER_FILL
    engine.FEE_PER_FILL = fee
    engine.SLIPPAGE_PER_FILL = slippage
    try:
        configs = tuple(
            replace(cfg, entry_delay_bars=delay)
            for cfg in clean.to_base_configs(engine, clean_configs)
        )
        trades, _legs, _priorities = v1.simulate_v1(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            configs=configs,
        )
        return trades, prefit_metrics(engine, trades)
    finally:
        engine.FEE_PER_FILL = original_fee
        engine.SLIPPAGE_PER_FILL = original_slippage


def robust_prefit_gate(metrics: dict[str, dict[str, float]]) -> bool:
    return all(
        item["total_return"] > 0.0
        and item["max_dd"] > -0.25
        and item["win_rate"] >= 0.45
        for item in (metrics["train"], metrics["validation"], metrics["prefit"])
    )


def robust_score(candidate: StrategyCandidate) -> float:
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
    return float(
        candidate.score
        + 1.5 * math.log(max(min_annual, 1e-9))
        - max(0.0, -0.25 - worst_dd) * 30.0
        - max(0.0, 0.45 - min_win) * 10.0
        + (6.0 if candidate.strict_improvement else 0.0)
    )


def strategy_row(candidate: StrategyCandidate) -> dict[str, Any]:
    row: dict[str, Any] = {
        "score": candidate.score,
        "robust_score": candidate.robust_score,
        "strict_improvement": candidate.strict_improvement,
        **flatten(candidate.metrics),
    }
    for index, cfg in enumerate(candidate.clean_configs, start=1):
        row.update({f"leg{index}_{key}": value for key, value in asdict(cfg).items()})
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


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    reference_trades, _reference_legs, _reference_priorities = clean.simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    reference_prefit = prefit_metrics(engine, reference_trades)
    reference_all = v1.metrics(engine, reference_trades)
    types_defaults = clean.clean_types_and_defaults(engine)
    baseline_base = v1.v1_configs(engine)

    rng = random.Random(args.seed)
    pools: list[list[LegCandidate]] = []
    pool_counts: list[dict[str, int]] = []
    for leg_index, (clean_type, baseline_clean) in enumerate(types_defaults):
        pool, counts = build_leg_pool(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            rng=rng,
            leg_index=leg_index,
            clean_type=clean_type,
            baseline_clean=baseline_clean,
            baseline_base=baseline_base[leg_index],
            samples=args.leg_samples,
            keep=args.leg_keep,
            progress_every=args.progress_every,
        )
        pools.append(pool)
        pool_counts.append(counts)

    pd.DataFrame(
        [
            {
                "leg_index": item.leg_index,
                "score": item.score,
                **asdict(item.clean_config),
                **flatten(item.metrics),
            }
            for pool in pools
            for item in pool
        ]
    ).to_csv(LEG_POOL_CSV, index=False)

    candidates: list[StrategyCandidate] = []
    evaluated = 0
    eligible = 0
    strict_count = 0
    for legs in product(*pools):
        merged = merge_legs(engine, legs)
        metrics = prefit_metrics(engine, merged)
        score = strategy_score(metrics, reference_prefit)
        evaluated += 1
        if score <= -1e8:
            continue
        eligible += 1
        strict = strict_improvement(metrics, reference_prefit)
        strict_count += int(strict)
        candidates = retain_strategies(
            candidates,
            StrategyCandidate(
                clean_configs=tuple(item.clean_config for item in legs),
                trades=merged,
                metrics=metrics,
                score=score,
                strict_improvement=strict,
            ),
            args.strategy_keep,
        )
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[
        : args.strategy_keep
    ]
    if not candidates:
        raise RuntimeError("No clean-tune strategy candidate survived")
    print(
        f"strategies evaluated={evaluated} eligible={eligible} "
        f"strict={strict_count} retained={len(candidates)}",
        flush=True,
    )

    for index, candidate in enumerate(candidates[: args.robust_keep], start=1):
        _k2_trades, candidate.k2_metrics = simulate_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            clean_configs=candidate.clean_configs,
            delay=2,
            fee=0.001,
            slippage=0.0004,
        )
        _slip_trades, candidate.slip8_metrics = simulate_scenario(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            clean_configs=candidate.clean_configs,
            delay=1,
            fee=0.001,
            slippage=0.0008,
        )
        candidate.robust_score = robust_score(candidate)
        if index % 50 == 0:
            print(
                f"robust {index}/{min(len(candidates), args.robust_keep)}",
                flush=True,
            )
    robust = sorted(
        candidates[: args.robust_keep],
        key=lambda item: item.robust_score,
        reverse=True,
    )
    strict_robust = [item for item in robust if item.strict_improvement]
    delay_cost_robust = [
        item
        for item in strict_robust
        if item.k2_metrics is not None
        and item.slip8_metrics is not None
        and robust_prefit_gate(item.k2_metrics)
        and robust_prefit_gate(item.slip8_metrics)
    ]
    selected = (
        delay_cost_robust[0]
        if delay_cost_robust
        else strict_robust[0]
        if strict_robust
        else robust[0]
    )
    selection_reason = (
        "strict_higher_return_lower_dd_moderate_win_k2_slip8_robust"
        if delay_cost_robust
        else "strict_higher_return_lower_dd_moderate_win"
        if strict_robust
        else "no_strict_improvement_robust_frontier"
    )

    selected_all = v1.metrics(engine, selected.trades)
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
            trades, _prefit = simulate_scenario(
                engine=engine,
                frame=frame,
                funding_times=funding_times,
                funding_cumulative=funding_cumulative,
                clean_configs=selected.clean_configs,
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
                "metrics": v1.metrics(engine, trades),
            }
        )

    pd.DataFrame(
        [strategy_row(item) for item in robust[: min(600, len(robust))]]
    ).to_csv(STRATEGY_CSV, index=False)
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
        "family": "SOL-1H-Adaptive-Regime",
        "baseline_version": "SOL-1H-Adaptive-Regime-V1",
        "observation_id": "SOL-1H-AR-V1-CLEAN-TUNE-2026-07-03",
        "status": "tuned_observation_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "reused_holdout": "evaluated_after_candidate_freeze_not_used_for_selection",
            "moderate_win_definition": "prefit_at_least_50pct_score_capped_at_65pct",
            "reason": selection_reason,
        },
        "search_counts": {
            "leg_samples_each": args.leg_samples,
            "leg_pools": pool_counts,
            "evaluated_strategies": evaluated,
            "eligible_strategies": eligible,
            "strict_improvement_observations": strict_count,
            "retained_strategies": len(candidates),
            "robust_evaluated": min(len(candidates), args.robust_keep),
            "strict_robust_candidates": len(strict_robust),
            "k2_slip8_robust_candidates": len(delay_cost_robust),
        },
        "reference_v1": reference_all,
        "selected": {
            "clean_configs": [asdict(cfg) for cfg in selected.clean_configs],
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
        "# SOL-1H-Adaptive-Regime-V1 Clean 参数微调 - 2026-07-03",
        "",
        "## 结论",
        "",
        f"选择规则：`{selection_reason}`。调参只使用 train/validation/prefit；reused holdout 在冻结后读取。",
        "",
        f"- 每腿随机样本：`{args.leg_samples}`；组合评估：`{evaluated}`；严格收益更高且回撤更小观察：`{strict_count}`。",
        f"- 严格改善候选：`{len(strict_robust)}`；同时通过 K+2/8 bps prefit 稳健门槛：`{len(delay_cost_robust)}`。",
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
    lines.extend(["", "## 冻结 clean 参数", ""])
    for index, cfg in enumerate(selected.clean_configs, start=1):
        lines.extend([f"### Leg {index}", ""])
        lines.extend(f"- `{key}` = `{value}`" for key, value in asdict(cfg).items())
        lines.append("")
    lines.extend(
        [
            "## 延迟与成本审计",
            "",
            "| Scenario | Prefit annual | Prefit DD | Prefit win | Reused OOS annual | Reused OOS DD | Full annual | Full DD |",
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
            "- 这是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。",
            "- reused holdout 已在 V1 登记时解锁，不是新鲜 OOS，不能参与选择或删参。",
            "- 只有同时满足收益改善、回撤改善、适中胜率、延迟/成本稳健性与新增 forward trades，才允许讨论 promotion。",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v1_clean_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
