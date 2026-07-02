from __future__ import annotations

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

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v1_full_ablation as v1_ablation  # noqa: E402


DATE_TAG = "2026-07-02"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTE_DIR = FAMILY_DIR / "research-notes"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v2_clean_tune_{DATE_TAG}.json"
DI_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_di_coordinate_{DATE_TAG}.csv"
STOCH_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_stoch_coordinate_{DATE_TAG}.csv"
PAIR_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_pair_ranking_{DATE_TAG}.csv"
STRESS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_stress_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_trades_{DATE_TAG}.csv"
REPORT_MD = NOTE_DIR / f"hype-1h-ar-v2-active-parameter-tune-{DATE_TAG}.md"

TRAIN_START = v1_ablation.TRAIN_START
TRAIN_END = v1_ablation.TRAIN_END
PREFIT_END = v1_ablation.PREFIT_END


@dataclass(frozen=True, slots=True)
class DICleanConfig:
    ema_htf: int = 89
    min_adx: float = 12.0
    max_adx: float = 36.0
    min_rvol: float = 2.0
    max_atr_bps: float = 250.0
    roc_window: int = 24
    min_dir_roc_bps: float = -200.0
    max_dist_ema_bps: float = 750.0
    htf_mode: str = "h12"
    require_body_dir: bool = True
    max_aligned_funding_bps: float = 8.0
    tp_atr: float = 1.5
    sl_atr: float = 4.0
    max_hold_bars: int = 18
    fixed_leverage: float = 3.0


@dataclass(frozen=True, slots=True)
class StochCleanConfig:
    indicator_window: int = 21
    threshold_low: float = 25.0
    threshold_high: float = 60.0
    ema_htf: int = 55
    min_adx: float = 12.0
    min_rvol: float = 1.0
    min_atr_bps: float = 200.0
    max_atr_bps: float = 400.0
    max_dist_ema_bps: float = 2500.0
    macd_fast: int = 8
    macd_slow: int = 21
    macd_signal: int = 5
    require_macd_turn: bool = True
    sl_atr: float = 4.0
    trail_activation_atr: float = 1.0
    trail_atr: float = 1.0
    max_hold_bars: int = 8
    cooldown_bars: int = 24
    fixed_leverage: float = 2.0


@dataclass(slots=True)
class ScoredConfig:
    config_id: str
    component: str
    clean_config: DICleanConfig | StochCleanConfig
    trades: list[base.Trade]
    metrics: dict[str, Any]


def di_to_base(cfg: DICleanConfig, name: str = "HYPE_1H_AR_V2_DI") -> base.StrategyConfig:
    return base.StrategyConfig(
        name=name,
        style="di_cross",
        side_mode="both",
        ema_fast=8,
        ema_slow=55,
        ema_htf=cfg.ema_htf,
        indicator_window=20,
        threshold_low=20.0,
        threshold_high=80.0,
        band_k=0.5,
        pullback_atr=0.0,
        roc_window=cfg.roc_window,
        roc_threshold_bps=25.0,
        macd_fast=8,
        macd_slow=21,
        macd_signal=5,
        min_adx=cfg.min_adx,
        max_adx=cfg.max_adx,
        min_rvol=cfg.min_rvol,
        min_atr_bps=0.0,
        max_atr_bps=cfg.max_atr_bps,
        min_dir_roc_bps=cfg.min_dir_roc_bps,
        max_dist_ema_bps=cfg.max_dist_ema_bps,
        htf_mode=cfg.htf_mode,
        require_macd_turn=False,
        require_body_dir=cfg.require_body_dir,
        max_aligned_funding_bps=cfg.max_aligned_funding_bps,
        exit_kind="fixed",
        tp_atr=cfg.tp_atr,
        sl_atr=cfg.sl_atr,
        trail_activation_atr=1.0,
        trail_atr=1.0,
        max_hold_bars=cfg.max_hold_bars,
        cooldown_bars=0,
        entry_delay_bars=1,
        sizing_kind="fixed",
        fixed_leverage=cfg.fixed_leverage,
        risk_fraction=0.01,
        max_leverage=1.0,
    )


def stoch_to_base(
    cfg: StochCleanConfig, name: str = "HYPE_1H_AR_V2_STOCH"
) -> base.StrategyConfig:
    return base.StrategyConfig(
        name=name,
        style="stoch_reversal",
        side_mode="both",
        ema_fast=8,
        ema_slow=55,
        ema_htf=cfg.ema_htf,
        indicator_window=cfg.indicator_window,
        threshold_low=cfg.threshold_low,
        threshold_high=cfg.threshold_high,
        band_k=0.5,
        pullback_atr=0.0,
        roc_window=12,
        roc_threshold_bps=25.0,
        macd_fast=cfg.macd_fast,
        macd_slow=cfg.macd_slow,
        macd_signal=cfg.macd_signal,
        min_adx=cfg.min_adx,
        max_adx=100.0,
        min_rvol=cfg.min_rvol,
        min_atr_bps=cfg.min_atr_bps,
        max_atr_bps=cfg.max_atr_bps,
        min_dir_roc_bps=-10_000.0,
        max_dist_ema_bps=cfg.max_dist_ema_bps,
        htf_mode="none",
        require_macd_turn=cfg.require_macd_turn,
        require_body_dir=False,
        max_aligned_funding_bps=10_000.0,
        exit_kind="trailing",
        tp_atr=1.0,
        sl_atr=cfg.sl_atr,
        trail_activation_atr=cfg.trail_activation_atr,
        trail_atr=cfg.trail_atr,
        max_hold_bars=cfg.max_hold_bars,
        cooldown_bars=cfg.cooldown_bars,
        entry_delay_bars=1,
        sizing_kind="fixed",
        fixed_leverage=cfg.fixed_leverage,
        risk_fraction=0.01,
        max_leverage=1.0,
    )


def equal_signature(left: list[base.Trade], right: list[base.Trade]) -> bool:
    return v1_ablation.signature(left) == v1_ablation.signature(right)


def walk_folds() -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    duration = (PREFIT_END - TRAIN_START) / 4
    return [
        (
            f"prefit_q{index + 1}",
            TRAIN_START + duration * index,
            TRAIN_START + duration * (index + 1),
        )
        for index in range(4)
    ]


def selection_metrics(trades: list[base.Trade]) -> dict[str, Any]:
    train = base.metrics(trades, TRAIN_START, TRAIN_END)
    validation = base.metrics(trades, TRAIN_END, PREFIT_END)
    prefit = base.metrics(trades, TRAIN_START, PREFIT_END)
    result: dict[str, Any] = {}
    for prefix, values in (("train", train), ("validation", validation), ("prefit", prefit)):
        result.update({f"{prefix}_{key}": value for key, value in values.items()})
    positive_folds = 0
    eligible_folds = 0
    worst_fold_return = math.inf
    worst_fold_dd = 0.0
    for name, start, end in walk_folds():
        values = base.metrics(trades, start, end)
        result.update({f"{name}_{key}": value for key, value in values.items()})
        if values["trades"] >= 5:
            eligible_folds += 1
            positive_folds += int(values["total_return"] > 0.0)
            worst_fold_return = min(worst_fold_return, values["total_return"])
            worst_fold_dd = min(worst_fold_dd, values["max_dd"])
    result["eligible_folds"] = eligible_folds
    result["positive_folds"] = positive_folds
    result["worst_fold_return"] = (
        worst_fold_return if math.isfinite(worst_fold_return) else -1.0
    )
    result["worst_fold_dd"] = worst_fold_dd
    return result


def score_metrics(values: dict[str, Any], baseline: dict[str, Any]) -> float:
    if values["prefit_trades"] < 35 or values["validation_trades"] < 8:
        return -1e9
    if values["prefit_annual_multiple"] <= 0 or values["validation_annual_multiple"] <= 0:
        return -1e9
    drawdown_penalty = max(0.0, -0.20 - values["prefit_max_dd"]) * 20.0
    validation_penalty = max(0.0, -0.20 - values["validation_max_dd"]) * 20.0
    win_penalty = max(0.0, 0.50 - values["prefit_win_rate"]) * 8.0
    fold_penalty = max(0, 3 - values["positive_folds"]) * 1.5
    score = (
        math.log(values["prefit_annual_multiple"])
        + 0.35 * math.log(max(values["validation_annual_multiple"], 1e-9))
        + 1.5 * values["prefit_win_rate"]
        + 3.0 * values["prefit_max_dd"]
        + 0.4 * values["worst_fold_return"]
        - drawdown_penalty
        - validation_penalty
        - win_penalty
        - fold_penalty
    )
    strict_dominance = (
        values["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and values["prefit_max_dd"] > baseline["prefit_max_dd"]
        and values["prefit_win_rate"] >= 0.50
    )
    robust = (
        values["validation_total_return"] > 0.0
        and values["validation_win_rate"] >= 0.50
        and values["validation_max_dd"] > -0.20
        and values["eligible_folds"] >= 3
        and values["positive_folds"] >= 3
        and values["worst_fold_dd"] > -0.20
    )
    values["prefit_strict_dominance"] = strict_dominance
    values["prefit_robust_pass"] = robust
    if strict_dominance:
        score += 6.0
    if robust:
        score += 4.0
    return score


def mutate_di(seed: DICleanConfig, rng: random.Random) -> DICleanConfig:
    choices: dict[str, tuple[Any, ...]] = {
        "ema_htf": (55, 89, 144, 233),
        "min_adx": (8.0, 10.0, 12.0, 14.0, 16.0, 20.0),
        "max_adx": (30.0, 32.0, 36.0, 40.0, 45.0, 55.0, 100.0),
        "min_rvol": (1.25, 1.5, 1.75, 2.0, 2.25, 2.5),
        "max_atr_bps": (200.0, 225.0, 250.0, 275.0, 300.0, 350.0, 400.0),
        "roc_window": (12, 24, 48, 72),
        "min_dir_roc_bps": (-10_000.0, -400.0, -300.0, -200.0, -100.0, 0.0, 100.0),
        "max_dist_ema_bps": (300.0, 500.0, 750.0, 1000.0, 1500.0, 2500.0),
        "htf_mode": ("none", "h4", "h12", "d1"),
        "require_body_dir": (False, True),
        "max_aligned_funding_bps": (1.0, 2.0, 4.0, 8.0, 10_000.0),
        "tp_atr": (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0),
        "sl_atr": (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0),
        "max_hold_bars": (8, 12, 15, 18, 24, 36, 48),
        "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.25, 3.5, 4.0),
    }
    updates = {
        field: rng.choice(choices[field])
        for field in rng.sample(list(choices), k=rng.choice((1, 2, 2, 3, 3, 4, 5)))
    }
    cfg = replace(seed, **updates)
    if cfg.max_adx <= cfg.min_adx:
        cfg = replace(cfg, max_adx=100.0)
    return cfg


def mutate_stoch(seed: StochCleanConfig, rng: random.Random) -> StochCleanConfig:
    macd_sets = base.MACD_SETS
    choices: dict[str, tuple[Any, ...]] = {
        "indicator_window": (7, 14, 21, 28),
        "threshold_low": (15.0, 20.0, 25.0, 30.0, 35.0, 40.0),
        "threshold_high": (50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0),
        "ema_htf": (34, 55, 89, 144, 233),
        "min_adx": (0.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0),
        "min_rvol": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
        "min_atr_bps": (100.0, 125.0, 150.0, 175.0, 200.0, 225.0, 250.0),
        "max_atr_bps": (300.0, 350.0, 400.0, 450.0, 500.0, 600.0, 10_000.0),
        "max_dist_ema_bps": (500.0, 1000.0, 1500.0, 2000.0, 2500.0, 4000.0, 10_000.0),
        "require_macd_turn": (False, True),
        "sl_atr": (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0),
        "trail_activation_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0),
        "trail_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0),
        "max_hold_bars": (4, 6, 8, 10, 12, 18, 24),
        "cooldown_bars": (0, 6, 12, 18, 24, 36, 48),
        "fixed_leverage": (1.0, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 3.5),
    }
    fields = list(choices) + ["macd_set"]
    updates: dict[str, Any] = {}
    for field in rng.sample(fields, k=rng.choice((1, 2, 2, 3, 3, 4, 5))):
        if field == "macd_set":
            fast, slow, signal = rng.choice(macd_sets)
            updates.update(macd_fast=fast, macd_slow=slow, macd_signal=signal)
        else:
            updates[field] = rng.choice(choices[field])
    cfg = replace(seed, **updates)
    if cfg.max_atr_bps <= cfg.min_atr_bps:
        cfg = replace(cfg, max_atr_bps=10_000.0)
    return cfg


def unique_mutations(
    seed: DICleanConfig | StochCleanConfig,
    *,
    count: int,
    rng: random.Random,
    component: str,
) -> list[DICleanConfig | StochCleanConfig]:
    output: list[DICleanConfig | StochCleanConfig] = [seed]
    seen = {seed}
    # Curated ablation directions are inserted before random local mutations.
    if component == "di_cross":
        assert isinstance(seed, DICleanConfig)
        curated = [
            replace(seed, min_dir_roc_bps=-10_000.0),
            replace(seed, roc_window=12),
            replace(seed, roc_window=48),
            replace(seed, fixed_leverage=3.5),
        ]
    else:
        assert isinstance(seed, StochCleanConfig)
        curated = [
            replace(seed, threshold_high=55.0),
            replace(seed, min_adx=0.0),
            replace(seed, trail_activation_atr=0.75),
            replace(seed, max_atr_bps=450.0),
        ]
    for item in curated:
        if item not in seen:
            seen.add(item)
            output.append(item)
    while len(output) < count:
        base_seed = rng.choice(output[: min(len(output), 64)]) if rng.random() < 0.35 else seed
        item = (
            mutate_di(base_seed, rng)
            if component == "di_cross"
            else mutate_stoch(base_seed, rng)
        )
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def score_component_variants(
    *,
    component: str,
    configs: list[DICleanConfig | StochCleanConfig],
    other_trades: list[base.Trade],
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    baseline_metrics: dict[str, Any],
) -> list[ScoredConfig]:
    scored: list[ScoredConfig] = []
    for index, clean in enumerate(configs):
        config_id = f"{component}_{index:06d}"
        cfg = (
            di_to_base(clean, config_id)
            if isinstance(clean, DICleanConfig)
            else stoch_to_base(clean, config_id)
        )
        component_trades = boundary.component_trades(
            frame, funding_times, funding_cumulative, cfg
        )
        if component == "di_cross":
            merged = base.merge_trade_sets(component_trades, other_trades, 1.0, 0.0)
        else:
            merged = base.merge_trade_sets(other_trades, component_trades, 1.0, 0.0)
        values = selection_metrics(merged)
        values["selection_score"] = score_metrics(values, baseline_metrics)
        scored.append(
            ScoredConfig(
                config_id=config_id,
                component=component,
                clean_config=clean,
                trades=component_trades,
                metrics=values,
            )
        )
        if (index + 1) % 5_000 == 0:
            best = max(scored, key=lambda item: item.metrics["selection_score"])
            print(
                f"{component} {index + 1}/{len(configs)} best={best.config_id} "
                f"score={best.metrics['selection_score']:.3f} "
                f"ann={best.metrics['prefit_annual_multiple']:.3f} "
                f"dd={best.metrics['prefit_max_dd']:.3f}",
                flush=True,
            )
    return scored


def scored_row(item: ScoredConfig) -> dict[str, Any]:
    return {
        "config_id": item.config_id,
        "component": item.component,
        **{f"cfg_{key}": value for key, value in asdict(item.clean_config).items()},
        **item.metrics,
    }


def retain_diverse(scored: list[ScoredConfig], keep: int) -> list[ScoredConfig]:
    eligible = [item for item in scored if item.metrics["selection_score"] > -1e8]
    ranked = sorted(
        eligible,
        key=lambda item: (
            int(item.metrics.get("prefit_strict_dominance", False)),
            int(item.metrics.get("prefit_robust_pass", False)),
            item.metrics["selection_score"],
        ),
        reverse=True,
    )
    annual = sorted(
        eligible,
        key=lambda item: (
            item.metrics["prefit_max_dd"] > -0.20,
            item.metrics["prefit_annual_multiple"],
        ),
        reverse=True,
    )
    output: list[ScoredConfig] = []
    seen: set[str] = set()
    for item in ranked[:keep] + annual[: keep // 3]:
        if item.config_id in seen:
            continue
        seen.add(item.config_id)
        output.append(item)
        if len(output) >= keep:
            break
    return output


def pair_search(
    di_items: list[ScoredConfig],
    stoch_items: list[ScoredConfig],
    baseline_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for di_item in di_items:
        for stoch_item in stoch_items:
            trades = base.merge_trade_sets(
                di_item.trades, stoch_item.trades, 1.0, 0.0
            )
            values = selection_metrics(trades)
            values["selection_score"] = score_metrics(values, baseline_metrics)
            rows.append(
                {
                    "di_id": di_item.config_id,
                    "stoch_id": stoch_item.config_id,
                    **values,
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("prefit_strict_dominance", False)),
            int(row.get("prefit_robust_pass", False)),
            row["selection_score"],
        ),
        reverse=True,
    )


def current_metrics(trades: list[base.Trade], full_end: pd.Timestamp) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, start, end in (
        ("reused_holdout", PREFIT_END, full_end),
        ("current_full", TRAIN_START, full_end),
        ("last_30d", max(TRAIN_START, full_end - pd.Timedelta(days=30)), full_end),
        ("last_60d", max(TRAIN_START, full_end - pd.Timedelta(days=60)), full_end),
        ("last_90d", max(TRAIN_START, full_end - pd.Timedelta(days=90)), full_end),
    ):
        values = base.metrics(trades, start, end)
        output.update({f"{name}_{key}": value for key, value in values.items()})
    return output


def stress_rows(
    *,
    di_cfg: DICleanConfig,
    stoch_cfg: StochCleanConfig,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    full_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    original_fee = base.FEE_PER_FILL
    original_slippage = base.SLIPPAGE_PER_FILL
    rows: list[dict[str, Any]] = []
    scenarios = [
        ("base_k1", 0.0010, 0.0004, 1),
        ("delay_k2", 0.0010, 0.0004, 2),
        ("delay_k3", 0.0010, 0.0004, 3),
        ("slip_8bps", 0.0010, 0.0008, 1),
        ("slip_10bps", 0.0010, 0.0010, 1),
        ("fee12_slip8", 0.0012, 0.0008, 1),
        ("double_cost", 0.0020, 0.0008, 1),
    ]
    try:
        for label, fee, slippage, delay in scenarios:
            base.FEE_PER_FILL = fee
            base.SLIPPAGE_PER_FILL = slippage
            di_base = replace(di_to_base(di_cfg, f"{label}_DI"), entry_delay_bars=delay)
            stoch_base = replace(
                stoch_to_base(stoch_cfg, f"{label}_STOCH"), entry_delay_bars=delay
            )
            di_trades = boundary.component_trades(
                frame, funding_times, funding_cumulative, di_base
            )
            stoch_trades = boundary.component_trades(
                frame, funding_times, funding_cumulative, stoch_base
            )
            merged = base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)
            rows.append(
                {
                    "scenario": label,
                    "fee_per_fill": fee,
                    "slippage_per_fill": slippage,
                    "entry_delay_bars": delay,
                    **selection_metrics(merged),
                    **current_metrics(merged, full_end),
                }
            )
    finally:
        base.FEE_PER_FILL = original_fee
        base.SLIPPAGE_PER_FILL = original_slippage
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)

    source_left, source_right, _left_priority, _right_priority, _payload = (
        boundary.load_boundary()
    )
    source_left_trades = boundary.component_trades(
        frame, funding_times, funding_cumulative, source_left
    )
    source_right_trades = boundary.component_trades(
        frame, funding_times, funding_cumulative, source_right
    )
    source_merged = base.merge_trade_sets(
        source_left_trades, source_right_trades, 1.0, 0.0
    )

    v2_di = DICleanConfig()
    v2_stoch = StochCleanConfig()
    v2_di_trades = boundary.component_trades(
        frame, funding_times, funding_cumulative, di_to_base(v2_di)
    )
    v2_stoch_trades = boundary.component_trades(
        frame, funding_times, funding_cumulative, stoch_to_base(v2_stoch)
    )
    v2_merged = base.merge_trade_sets(v2_di_trades, v2_stoch_trades, 1.0, 0.0)
    equality = {
        "di_component_path_equal": equal_signature(source_left_trades, v2_di_trades),
        "stoch_component_path_equal": equal_signature(
            source_right_trades, v2_stoch_trades
        ),
        "merged_path_equal": equal_signature(source_merged, v2_merged),
    }
    if not all(equality.values()):
        raise RuntimeError(f"V2 clean baseline does not reproduce V1 exactly: {equality}")
    baseline_selection = selection_metrics(v2_merged)
    baseline_selection["selection_score"] = score_metrics(
        baseline_selection, baseline_selection
    )
    baseline_current = current_metrics(v2_merged, full_end)

    rng = random.Random(2026070201)
    di_configs = unique_mutations(
        v2_di, count=30_000, rng=rng, component="di_cross"
    )
    stoch_configs = unique_mutations(
        v2_stoch, count=30_000, rng=rng, component="stoch_reversal"
    )
    print(
        f"V2 exact reproduction PASS; di_configs={len(di_configs)} "
        f"stoch_configs={len(stoch_configs)}",
        flush=True,
    )
    di_scored = score_component_variants(
        component="di_cross",
        configs=di_configs,
        other_trades=v2_stoch_trades,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        baseline_metrics=baseline_selection,
    )
    stoch_scored = score_component_variants(
        component="stoch_reversal",
        configs=stoch_configs,
        other_trades=v2_di_trades,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        baseline_metrics=baseline_selection,
    )
    pd.DataFrame(scored_row(item) for item in di_scored).to_csv(DI_CSV, index=False)
    pd.DataFrame(scored_row(item) for item in stoch_scored).to_csv(
        STOCH_CSV, index=False
    )
    di_keep = retain_diverse(di_scored, 140)
    stoch_keep = retain_diverse(stoch_scored, 140)
    pairs = pair_search(di_keep, stoch_keep, baseline_selection)
    di_map = {item.config_id: item for item in di_keep}
    stoch_map = {item.config_id: item for item in stoch_keep}

    # Freeze selection using prefit/walk-forward fields only.
    selected_row = next(
        (
            row
            for row in pairs
            if row.get("prefit_strict_dominance", False)
            and row.get("prefit_robust_pass", False)
        ),
        pairs[0],
    )
    selected_di = di_map[selected_row["di_id"]]
    selected_stoch = stoch_map[selected_row["stoch_id"]]
    selected_trades = base.merge_trade_sets(
        selected_di.trades, selected_stoch.trades, 1.0, 0.0
    )
    selected_current = current_metrics(selected_trades, full_end)
    for row in pairs[:500]:
        di_item = di_map[row["di_id"]]
        stoch_item = stoch_map[row["stoch_id"]]
        merged = base.merge_trade_sets(di_item.trades, stoch_item.trades, 1.0, 0.0)
        row.update(current_metrics(merged, full_end))
    pd.DataFrame(pairs[:500]).to_csv(PAIR_CSV, index=False)

    stress = stress_rows(
        di_cfg=selected_di.clean_config,
        stoch_cfg=selected_stoch.clean_config,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        full_end=full_end,
    )
    pd.DataFrame(stress).to_csv(STRESS_CSV, index=False)
    pd.DataFrame(boundary.trade_rows(selected_trades) if hasattr(boundary, "trade_rows") else base.trade_rows(selected_trades)).to_csv(
        TRADES_CSV, index=False
    )

    current_strict_improvement = (
        selected_current["current_full_annual_multiple"]
        > baseline_current["current_full_annual_multiple"]
        and selected_current["current_full_max_dd"]
        > baseline_current["current_full_max_dd"]
        and selected_current["current_full_win_rate"] >= 0.50
    )
    k2 = next(row for row in stress if row["scenario"] == "delay_k2")
    slip8 = next(row for row in stress if row["scenario"] == "slip_8bps")
    live_stress_pass = (
        k2["reused_holdout_total_return"] > 0.0
        and k2["reused_holdout_max_dd"] > -0.20
        and slip8["reused_holdout_total_return"] > 0.0
        and slip8["reused_holdout_max_dd"] > -0.20
    )
    tune_status = (
        "strict_improvement_observation_not_live_ready"
        if current_strict_improvement
        else "prefit_improvement_only_not_live_ready"
    )
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "v1_source": "HYPE-1H-Adaptive-Regime-V1",
        "v2_version": "HYPE-1H-Adaptive-Regime-V2",
        "v2_status": "clean_equivalent_diagnostic_baseline_not_live_ready",
        "tune_id": f"HYPE-1H-Adaptive-Regime-V2-TUNE__{selected_row['di_id']}__{selected_row['stoch_id']}",
        "tune_status": tune_status,
        "data_quality": quality,
        "data_end": full_end,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "v2_clean_configs": {
            "di_cross": asdict(v2_di),
            "stoch_reversal": asdict(v2_stoch),
            "fixed_state_machine": {
                "side": "both",
                "entry_delay_bars": 1,
                "di_exit": "fixed_atr_bracket",
                "stoch_exit": "closed_bar_atr_trailing",
                "sizing": "fixed_equity_notional",
                "conflict_priority": "di_cross_first",
            },
        },
        "v2_equivalence": equality,
        "v2_baseline": {**baseline_selection, **baseline_current},
        "search": {
            "selection_used_reused_holdout": False,
            "di_configs": len(di_configs),
            "stoch_configs": len(stoch_configs),
            "di_retained": len(di_keep),
            "stoch_retained": len(stoch_keep),
            "pair_evaluations": len(pairs),
            "walk_folds": [
                {"name": name, "start": start, "end": end}
                for name, start, end in walk_folds()
            ],
        },
        "selected": {
            "selection_row": selected_row,
            "di_config": asdict(selected_di.clean_config),
            "stoch_config": asdict(selected_stoch.clean_config),
            "current_diagnostics": selected_current,
            "current_strict_improvement_vs_v2": current_strict_improvement,
            "live_stress_pass": live_stress_pass,
        },
        "stress": stress,
        "promotion_blockers": [
            "reused holdout is no longer untouched OOS",
            "selection has not accumulated new forward trades",
            "no production runner/restart recovery/exchange reconciliation",
            "no real stop-market slippage evidence",
        ]
        + ([] if live_stress_pass else ["K+2 or 8 bps slippage stress failed"]),
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report_lines = [
        "# HYPE-1H-Adaptive-Regime-V2 active 参数微调 - 2026-07-02",
        "",
        "## 结论",
        "",
        f"V2 clean baseline 已与 V1 做逐笔等价校验：DI component=`{equality['di_component_path_equal']}`、Stoch component=`{equality['stoch_component_path_equal']}`、merged=`{equality['merged_path_equal']}`。V2 不是换回测口径，而是删除 dormant 字段后的同一状态机。",
        "",
        f"微调只使用 prefit 与其内部 `{len(walk_folds())}` 个时间块排序：DI `{len(di_configs)}` 组、Stoch `{len(stoch_configs)}` 组、组合 `{len(pairs)}` 组；reused holdout 在参数冻结后才作诊断，未参与 selection score。",
        "",
        f"冻结微调观察：`{payload['tune_id']}`；状态 `{tune_status}`。",
        "",
        "## V2 与冻结微调观察对比",
        "",
        "| Metric | V2 baseline prefit | Tune prefit | V2 current full | Tune current full |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Annual multiple | `{base.mult(baseline_selection['prefit_annual_multiple'])}` | `{base.mult(selected_row['prefit_annual_multiple'])}` | `{base.mult(baseline_current['current_full_annual_multiple'])}` | `{base.mult(selected_current['current_full_annual_multiple'])}` |",
        f"| Max DD | `{base.pct(baseline_selection['prefit_max_dd'])}` | `{base.pct(selected_row['prefit_max_dd'])}` | `{base.pct(baseline_current['current_full_max_dd'])}` | `{base.pct(selected_current['current_full_max_dd'])}` |",
        f"| Win rate | `{base.pct(baseline_selection['prefit_win_rate'])}` | `{base.pct(selected_row['prefit_win_rate'])}` | `{base.pct(baseline_current['current_full_win_rate'])}` | `{base.pct(selected_current['current_full_win_rate'])}` |",
        f"| Trades | `{int(baseline_selection['prefit_trades'])}` | `{int(selected_row['prefit_trades'])}` | `{int(baseline_current['current_full_trades'])}` | `{int(selected_current['current_full_trades'])}` |",
        "",
        "## 冻结微调参数",
        "",
        "### DI-cross",
        "",
    ]
    for key, value in asdict(selected_di.clean_config).items():
        report_lines.append(f"- `{key} = {value}`")
    report_lines.extend(["", "### Stoch-reversal", ""])
    for key, value in asdict(selected_stoch.clean_config).items():
        report_lines.append(f"- `{key} = {value}`")
    report_lines.extend(
        [
            "",
            "## 实盘压力",
            "",
            "| Scenario | Current full ann | Full DD | Reused holdout ann | Holdout DD | Holdout win |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in stress:
        report_lines.append(
            f"| `{row['scenario']}` | `{base.mult(row['current_full_annual_multiple'])}` | `{base.pct(row['current_full_max_dd'])}` | `{base.mult(row['reused_holdout_annual_multiple'])}` | `{base.pct(row['reused_holdout_max_dd'])}` | `{base.pct(row['reused_holdout_win_rate'])}` |"
        )
    report_lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            f"- Current full 严格实现更高收益、更低回撤且胜率 `>=50%`：`{current_strict_improvement}`。",
            f"- K+2 与 8 bps slippage reused-holdout 联合压力通过：`{live_stress_pass}`。",
            "- 即使数值改善，reused holdout 已不是 untouched OOS；在新增 forward trades、生产 runner、restart recovery、exchange reconciliation、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据完成前，不提升为 candidate、paper-live、dry-run、handoff 或 live。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
