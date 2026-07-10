from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
BASE_SEARCH_PATH = SCRIPT_DIR / "research_sol_1h_adaptive_regime_search.py"
V2_JSON = ARTIFACT_DIR / "sol_1h_ar_high_win_search_2026-07-07.json"

DATE_TAG = "2026-07-10"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v2_mechanism_redesign_{DATE_TAG}.json"
CANDIDATES_CSV = (
    ARTIFACT_DIR / f"sol_1h_ar_v2_mechanism_redesign_candidates_{DATE_TAG}.csv"
)
TRADES_CSV = (
    ARTIFACT_DIR / f"sol_1h_ar_v2_mechanism_redesign_selected_trades_{DATE_TAG}.csv"
)
REPORT_MD = (
    DIAGNOSTIC_DIR / f"sol-1h-ar-v2-mechanism-redesign-{DATE_TAG}.md"
)

TRAIN_START = pd.Timestamp("2024-08-17T05:00:00Z")
TRAIN_END = pd.Timestamp("2025-09-07T07:24:00Z")
PREFIT_END = pd.Timestamp("2026-04-03T05:00:00Z")
FULL_END = pd.Timestamp("2026-07-03T05:00:00Z")

STANDARD_SLICES = (
    ("last_1d", pd.Timedelta(days=1)),
    ("last_7d", pd.Timedelta(days=7)),
    ("last_1m", pd.Timedelta(days=30)),
    ("last_3m", pd.Timedelta(days=91)),
    ("last_6m", pd.Timedelta(days=182)),
    ("last_1y", pd.Timedelta(days=365)),
)


@dataclass(slots=True)
class LegVariant:
    name: str
    mechanism: str
    gate: str
    config: Any
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]


@dataclass(slots=True)
class StrategyVariant:
    name: str
    mechanism: str
    left: LegVariant | None
    right: LegVariant | None
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def window_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, TRAIN_START, TRAIN_END),
        "validation": engine.metrics(trades, TRAIN_END, PREFIT_END),
        "prefit": engine.metrics(trades, TRAIN_START, PREFIT_END),
        "reused_holdout": engine.metrics(trades, PREFIT_END, FULL_END),
        "current_full": engine.metrics(trades, TRAIN_START, FULL_END),
    }


def selected_trades(
    trades: list[Any], start: pd.Timestamp, end: pd.Timestamp
) -> list[Any]:
    return [trade for trade in trades if start <= trade.entry_ts < end]


def tail_metrics(
    trades: list[Any], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, float]:
    subset = selected_trades(trades, start, end)
    if not subset:
        return {
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "payoff_ratio": 0.0,
            "max_trade_loss": 0.0,
            "max_trade_mae": 0.0,
            "stop_count": 0.0,
            "timeout_count": 0.0,
        }
    returns = np.array([trade.equity_ret for trade in subset], dtype="float64")
    wins = returns[returns > 0.0]
    losses = returns[returns <= 0.0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    return {
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": (
            float(avg_win / abs(avg_loss)) if avg_loss < 0.0 else math.inf
        ),
        "max_trade_loss": float(returns.min()),
        "max_trade_mae": float(
            min(trade.equity_mae for trade in subset)
        ),
        "stop_count": float(
            sum("stop" in trade.exit_reason for trade in subset)
        ),
        "timeout_count": float(
            sum("timeout" in trade.exit_reason for trade in subset)
        ),
    }


def robust_prefit_score(
    engine: Any, trades: list[Any]
) -> tuple[float, dict[str, dict[str, float]]]:
    metrics = window_metrics(engine, trades)
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if (
        train["trades"] < 12
        or validation["trades"] < 6
        or prefit["trades"] < 25
        or train["total_return"] <= 0.0
        or validation["total_return"] <= 0.0
        or min(train["win_rate"], validation["win_rate"]) < 0.55
        or min(train["max_dd"], validation["max_dd"], prefit["max_dd"]) <= -0.20
    ):
        return -1e9, metrics
    tails = tail_metrics(trades, TRAIN_START, PREFIT_END)
    min_ann = min(train["annual_multiple"], validation["annual_multiple"])
    score = (
        1.15 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.35 * math.log(max(min_ann, 1e-9))
        + 0.18 * min(prefit["profit_factor"], 5.0)
        + 0.30 * min(prefit["win_rate"], 0.85)
        + 0.12 * min(prefit["trades"] / 50.0, 2.0)
        - 8.0 * max(0.0, -0.08 - tails["max_trade_loss"])
    )
    return float(score), metrics


def directional_gate(
    frame: pd.DataFrame, signal: np.ndarray, gate: str
) -> np.ndarray:
    if gate == "none":
        return signal
    idx = np.flatnonzero(signal)
    if len(idx) == 0:
        return signal
    side = signal[idx].astype("float64")
    masks: dict[str, np.ndarray] = {
        "roc6": side * frame["roc6_bps"].to_numpy("float64")[idx] >= 0.0,
        "roc12": side * frame["roc12_bps"].to_numpy("float64")[idx] >= 0.0,
        "macd_state": (
            side * frame["macd_hist_8_21_5"].to_numpy("float64")[idx] >= 0.0
        ),
        "di_state": (
            side
            * (
                frame["pdi14"].to_numpy("float64")[idx]
                - frame["mdi14"].to_numpy("float64")[idx]
            )
            >= 0.0
        ),
        "h4_state": (
            side * frame["h4_spread"].to_numpy("float64")[idx] >= 0.0
        ),
    }
    if gate in masks:
        keep = masks[gate]
    elif gate == "roc6_macd":
        keep = masks["roc6"] & masks["macd_state"]
    elif gate == "roc6_di":
        keep = masks["roc6"] & masks["di_state"]
    elif gate == "fast_consensus":
        keep = masks["roc6"] & masks["macd_state"] & masks["di_state"]
    elif gate == "h4_fast":
        keep = masks["h4_state"] & masks["roc6"]
    else:
        raise ValueError(f"Unknown gate: {gate}")
    gated = np.zeros_like(signal)
    gated[idx[keep]] = signal[idx[keep]]
    return gated


def simulate_variant(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    cfg: Any,
    gate: str,
) -> list[Any]:
    signal = directional_gate(frame, engine.build_signal(frame, cfg), gate)
    return engine.simulate_trades(
        frame, signal, cfg, funding_times, funding_cumulative
    )


def make_donchian_variants(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    baseline: Any,
) -> list[LegVariant]:
    variants: list[LegVariant] = []
    for side_mode in ("both", "long", "short"):
        for leverage in (1.5, 2.0, 2.5, 3.0):
            for tp_atr in (0.75, 1.0, 1.5, 2.0, 3.0):
                for sl_atr in (1.5, 2.0, 3.0, 4.0):
                    for max_hold in (24, 48, 72, 120):
                        cfg = replace(
                            baseline,
                            name=(
                                f"DON_FIXED_{side_mode}_L{leverage:g}_"
                                f"TP{tp_atr:g}_SL{sl_atr:g}_H{max_hold}"
                            ),
                            side_mode=side_mode,
                            exit_kind="fixed",
                            fixed_leverage=leverage,
                            tp_atr=tp_atr,
                            sl_atr=sl_atr,
                            max_hold_bars=max_hold,
                        )
                        trades = simulate_variant(
                            engine,
                            frame,
                            funding_times,
                            funding_cumulative,
                            cfg,
                            "none",
                        )
                        score, metrics = robust_prefit_score(engine, trades)
                        if score > -1e8:
                            variants.append(
                                LegVariant(
                                    cfg.name,
                                    "donchian_fixed_payoff",
                                    "none",
                                    cfg,
                                    trades,
                                    score,
                                    metrics,
                                )
                            )
        for leverage in (1.5, 2.0, 2.5, 3.0):
            for sl_atr in (1.5, 2.0, 3.0, 4.0):
                for activation in (0.75, 1.0, 1.5):
                    for trail_atr in (0.75, 1.0, 1.5, 2.0):
                        for max_hold in (48, 72, 120):
                            cfg = replace(
                                baseline,
                                name=(
                                    f"DON_TRAIL_{side_mode}_L{leverage:g}_"
                                    f"SL{sl_atr:g}_A{activation:g}_"
                                    f"T{trail_atr:g}_H{max_hold}"
                                ),
                                side_mode=side_mode,
                                exit_kind="trailing",
                                fixed_leverage=leverage,
                                sl_atr=sl_atr,
                                trail_activation_atr=activation,
                                trail_atr=trail_atr,
                                max_hold_bars=max_hold,
                            )
                            trades = simulate_variant(
                                engine,
                                frame,
                                funding_times,
                                funding_cumulative,
                                cfg,
                                "none",
                            )
                            score, metrics = robust_prefit_score(engine, trades)
                            if score > -1e8:
                                variants.append(
                                    LegVariant(
                                        cfg.name,
                                        "donchian_trend_capture",
                                        "none",
                                        cfg,
                                        trades,
                                        score,
                                        metrics,
                                    )
                                )
    return sorted(variants, key=lambda item: item.score, reverse=True)


def make_vwap_variants(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    baseline: Any,
) -> list[LegVariant]:
    variants: list[LegVariant] = []
    gates = (
        "none",
        "roc6",
        "roc12",
        "macd_state",
        "di_state",
        "h4_state",
        "roc6_macd",
        "roc6_di",
        "fast_consensus",
        "h4_fast",
    )
    for side_mode in ("short", "both", "long"):
        for gate in gates:
            for leverage in (0.75, 1.0, 1.5):
                for tp_atr in (0.75, 1.0, 1.25, 1.5):
                    for sl_atr in (0.75, 1.0, 1.5, 2.0, 3.0):
                        for max_hold in (6, 12, 18):
                            cfg = replace(
                                baseline,
                                name=(
                                    f"VWAP_FIXED_{side_mode}_{gate}_"
                                    f"L{leverage:g}_TP{tp_atr:g}_"
                                    f"SL{sl_atr:g}_H{max_hold}"
                                ),
                                side_mode=side_mode,
                                exit_kind="fixed",
                                fixed_leverage=leverage,
                                tp_atr=tp_atr,
                                sl_atr=sl_atr,
                                max_hold_bars=max_hold,
                            )
                            trades = simulate_variant(
                                engine,
                                frame,
                                funding_times,
                                funding_cumulative,
                                cfg,
                                gate,
                            )
                            score, metrics = robust_prefit_score(engine, trades)
                            if score > -1e8:
                                variants.append(
                                    LegVariant(
                                        cfg.name,
                                        "vwap_tail_compression",
                                        gate,
                                        cfg,
                                        trades,
                                        score,
                                        metrics,
                                    )
                                )
            for leverage in (0.75, 1.0, 1.5):
                for sl_atr in (0.75, 1.0, 1.5, 2.0):
                    for activation in (0.5, 0.75, 1.0):
                        for trail_atr in (0.5, 0.75, 1.0):
                            for max_hold in (6, 12, 18):
                                cfg = replace(
                                    baseline,
                                    name=(
                                        f"VWAP_TRAIL_{side_mode}_{gate}_"
                                        f"L{leverage:g}_SL{sl_atr:g}_"
                                        f"A{activation:g}_T{trail_atr:g}_"
                                        f"H{max_hold}"
                                    ),
                                    side_mode=side_mode,
                                    exit_kind="trailing",
                                    fixed_leverage=leverage,
                                    sl_atr=sl_atr,
                                    trail_activation_atr=activation,
                                    trail_atr=trail_atr,
                                    max_hold_bars=max_hold,
                                )
                                trades = simulate_variant(
                                    engine,
                                    frame,
                                    funding_times,
                                    funding_cumulative,
                                    cfg,
                                    gate,
                                )
                                score, metrics = robust_prefit_score(
                                    engine, trades
                                )
                                if score > -1e8:
                                    variants.append(
                                        LegVariant(
                                            cfg.name,
                                            "vwap_trailing_failure_exit",
                                            gate,
                                            cfg,
                                            trades,
                                            score,
                                            metrics,
                                        )
                                    )
    return sorted(variants, key=lambda item: item.score, reverse=True)


def strategy_from_leg(
    engine: Any, leg: LegVariant, prefix: str
) -> StrategyVariant:
    score, metrics = robust_prefit_score(engine, leg.trades)
    return StrategyVariant(
        f"{prefix}__{leg.name}",
        f"{prefix}:{leg.mechanism}",
        leg if prefix == "donchian_only" else None,
        leg if prefix == "vwap_only" else None,
        leg.trades,
        score,
        metrics,
    )


def build_strategy_candidates(
    engine: Any,
    donchian: list[LegVariant],
    vwap: list[LegVariant],
    keep_per_leg: int = 50,
) -> list[StrategyVariant]:
    strategies: list[StrategyVariant] = []
    strategies.extend(
        strategy_from_leg(engine, leg, "donchian_only")
        for leg in donchian[:keep_per_leg]
    )
    strategies.extend(
        strategy_from_leg(engine, leg, "vwap_only")
        for leg in vwap[:keep_per_leg]
    )
    for left in donchian[:keep_per_leg]:
        for right in vwap[:keep_per_leg]:
            merged = engine.merge_trade_sets(
                left.trades, right.trades, left.score, right.score
            )
            score, metrics = robust_prefit_score(engine, merged)
            if score <= -1e8:
                continue
            strategies.append(
                StrategyVariant(
                    f"ENS__{left.name}__{right.name}",
                    f"ensemble:{left.mechanism}+{right.mechanism}",
                    left,
                    right,
                    merged,
                    score,
                    metrics,
                )
            )
    return sorted(strategies, key=lambda item: item.score, reverse=True)


def variant_row(item: StrategyVariant) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": item.name,
        "mechanism": item.mechanism,
        "prefit_score": item.score,
        "left_name": item.left.name if item.left else "",
        "left_gate": item.left.gate if item.left else "",
        "right_name": item.right.name if item.right else "",
        "right_gate": item.right.gate if item.right else "",
    }
    for window, metric in item.metrics.items():
        row.update({f"{window}_{key}": value for key, value in metric.items()})
    for window, start, end in (
        ("prefit_tail", TRAIN_START, PREFIT_END),
        ("holdout_tail", PREFIT_END, FULL_END),
        ("full_tail", TRAIN_START, FULL_END),
    ):
        row.update(
            {
                f"{window}_{key}": value
                for key, value in tail_metrics(item.trades, start, end).items()
            }
        )
    return row


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2%}"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.4f}x"


def metric_table_row(label: str, metrics: dict[str, dict[str, float]]) -> str:
    prefit = metrics["prefit"]
    holdout = metrics["reused_holdout"]
    full = metrics["current_full"]
    return (
        f"| `{label}` | `{mult(prefit['annual_multiple'])}` | "
        f"`{pct(prefit['max_dd'])}` | `{pct(prefit['win_rate'])}` | "
        f"`{mult(holdout['annual_multiple'])}` | "
        f"`{pct(holdout['max_dd'])}` | `{pct(holdout['win_rate'])}` | "
        f"`{mult(full['annual_multiple'])}` | `{pct(full['max_dd'])}` | "
        f"`{pct(full['win_rate'])}` | `{int(full['trades'])}` |"
    )


def main() -> None:
    base = load_module(BASE_SEARCH_PATH, "sol_v2_redesign_base")
    engine = base.load_engine()
    frame, funding, quality = base.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    source = json.loads(V2_JSON.read_text(encoding="utf-8"))
    configs = [
        engine.StrategyConfig(**config)
        for config in source["best_configs"].values()
    ]
    don_base = next(cfg for cfg in configs if cfg.style == "donchian_break")
    vwap_base = next(cfg for cfg in configs if cfg.style == "vwap_revert")

    don_trades = simulate_variant(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        don_base,
        "none",
    )
    vwap_trades = simulate_variant(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        vwap_base,
        "none",
    )
    don_score, don_metrics = robust_prefit_score(engine, don_trades)
    vwap_score, vwap_metrics = robust_prefit_score(engine, vwap_trades)
    baseline_trades = engine.merge_trade_sets(
        don_trades, vwap_trades, don_score, vwap_score
    )
    baseline_score, baseline_metrics = robust_prefit_score(
        engine, baseline_trades
    )
    baseline = StrategyVariant(
        "SOL-1H-Adaptive-Regime-V2",
        "baseline:donchian_break+vwap_revert",
        LegVariant(
            don_base.name,
            "baseline_donchian",
            "none",
            don_base,
            don_trades,
            don_score,
            don_metrics,
        ),
        LegVariant(
            vwap_base.name,
            "baseline_vwap",
            "none",
            vwap_base,
            vwap_trades,
            vwap_score,
            vwap_metrics,
        ),
        baseline_trades,
        baseline_score,
        baseline_metrics,
    )

    don_variants = make_donchian_variants(
        engine, frame, funding_times, funding_cumulative, don_base
    )
    vwap_variants = make_vwap_variants(
        engine, frame, funding_times, funding_cumulative, vwap_base
    )
    candidates = build_strategy_candidates(engine, don_variants, vwap_variants)
    if not candidates:
        raise RuntimeError("No mechanism-redesign candidates survived prefit gates")
    selected = candidates[0]

    # Selection above is exclusively train/validation/prefit. The reused
    # holdout is read only after the selected identity is frozen.
    frozen = candidates[:100]
    rows = [variant_row(item) for item in frozen]
    rows.insert(0, variant_row(baseline))
    pd.DataFrame(rows).to_csv(CANDIDATES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected.trades)).to_csv(TRADES_CSV, index=False)

    standard_slices = [
        {
            "window": name,
            **engine.metrics(selected.trades, FULL_END - delta, FULL_END),
        }
        for name, delta in STANDARD_SLICES
    ]
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "baseline_version": "SOL-1H-Adaptive-Regime-V2",
        "observation_id": "SOL-1H-AR-V2-MECHANISM-REDESIGN-2026-07-10",
        "status": "diagnostic_only_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_identity_freeze_not_used_for_selection",
            "fresh_oos": False,
        },
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "counts": {
            "donchian_variants_survived": len(don_variants),
            "vwap_variants_survived": len(vwap_variants),
            "strategy_candidates_survived": len(candidates),
            "frozen_holdout_audit_set": len(frozen),
        },
        "baseline": variant_row(baseline),
        "selected": {
            **variant_row(selected),
            "left_config": asdict(selected.left.config) if selected.left else None,
            "right_config": asdict(selected.right.config) if selected.right else None,
        },
        "standard_slices": standard_slices,
        "top_20": [variant_row(item) for item in candidates[:20]],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    baseline_tail = tail_metrics(baseline.trades, TRAIN_START, FULL_END)
    selected_tail = tail_metrics(selected.trades, TRAIN_START, FULL_END)
    lines = [
        "# SOL-1H-Adaptive-Regime-V2 机制改造诊断 - 2026-07-10",
        "",
        "## 结论",
        "",
        "本实验把 V2 的问题视为收益结构与 regime 失效，而不是继续做原参数邻域微调。所有候选只使用 train/validation/prefit 排序；最近三个月已在 V1 阶段揭盲，本次只作 reused-holdout 审计。",
        "",
        f"- Donchian 机制变体通过 prefit 基础门槛：`{len(don_variants)}`。",
        f"- VWAP 机制变体通过 prefit 基础门槛：`{len(vwap_variants)}`。",
        f"- 组合后通过基础门槛：`{len(candidates)}`；冻结审计集：`{len(frozen)}`。",
        f"- prefit-only 选中观察：`{selected.name}`。",
        "",
        "## V2 收益结构诊断",
        "",
        f"- V2 full 区间最大单笔亏损 `{pct(baseline_tail['max_trade_loss'])}`，平均盈利 `{pct(baseline_tail['avg_win'])}`，平均亏损 `{pct(baseline_tail['avg_loss'])}`，payoff `{baseline_tail['payoff_ratio']:.3f}`。",
        f"- V2 full 区间 stop exits `{int(baseline_tail['stop_count'])}`，timeout exits `{int(baseline_tail['timeout_count'])}`；高胜率由小 TP 累积，少数 stop 构成主要尾部风险。",
        "- 最近三个月两笔亏损均来自 VWAP short；Donchian 腿为 `2/2` 盈利。两笔 VWAP short 在信号时均出现 `roc6 > 0`、短 MACD histogram > 0、`PDI > MDI`，说明慢速 `h12` 空头 regime 尚未翻转时，快速反弹已经发生。",
        "",
        "## 基线与选中观察",
        "",
        "| Strategy | Prefit ann | Prefit DD | Prefit win | Reused holdout ann | Holdout DD | Holdout win | Full ann | Full DD | Full win | Full trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        metric_table_row("V2 baseline", baseline.metrics),
        metric_table_row("prefit-only selected", selected.metrics),
        "",
        "## 选中机制",
        "",
        f"- strategy mechanism：`{selected.mechanism}`。",
        f"- Donchian：`{selected.left.name if selected.left else 'disabled'}`。",
        f"- VWAP：`{selected.right.name if selected.right else 'disabled'}`；gate `{selected.right.gate if selected.right else 'n/a'}`。",
        f"- full 最大单笔亏损 `{pct(selected_tail['max_trade_loss'])}`，平均盈利 `{pct(selected_tail['avg_win'])}`，平均亏损 `{pct(selected_tail['avg_loss'])}`，payoff `{selected_tail['payoff_ratio']:.3f}`。",
        "",
        "## 标准近期分片（锚定数据集末端，仅审计）",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in standard_slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | "
            f"`{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | "
            f"`{pct(row['win_rate'])}` | `{int(row['trades'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- reused holdout 已被用于提出快速反转 veto 假设，因此本实验不能产生 promotion 或新版本。",
            "- 只有 prefit-only 选择在新增 fresh forward trades 上继续成立，并通过延迟、成本、订单状态机和恢复审计，才允许进入下一阶段。",
            "- 本报告不把 reused-holdout 表现最好的候选倒选为结果。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{CANDIDATES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_mechanism_redesign.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload["counts"]), indent=2))
    print(
        f"selected={selected.name} "
        f"prefit_ann={selected.metrics['prefit']['annual_multiple']:.4f} "
        f"prefit_dd={selected.metrics['prefit']['max_dd']:.4f} "
        f"holdout_ann={selected.metrics['reused_holdout']['annual_multiple']:.4f} "
        f"holdout_dd={selected.metrics['reused_holdout']['max_dd']:.4f} "
        f"full_ann={selected.metrics['current_full']['annual_multiple']:.4f} "
        f"full_dd={selected.metrics['current_full']['max_dd']:.4f}",
        flush=True,
    )
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
