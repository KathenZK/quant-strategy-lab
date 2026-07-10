from __future__ import annotations

import importlib.util
import json
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
REDESIGN_PATH = SCRIPT_DIR / "research_sol_1h_ar_v2_mechanism_redesign.py"
V2_JSON = ARTIFACT_DIR / "sol_1h_ar_high_win_search_2026-07-07.json"
REDESIGN_JSON = ARTIFACT_DIR / "sol_1h_ar_v2_mechanism_redesign_2026-07-10.json"

DATE_TAG = "2026-07-10"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v2_staged_exit_{DATE_TAG}.json"
CANDIDATES_CSV = ARTIFACT_DIR / f"sol_1h_ar_v2_staged_exit_candidates_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"sol_1h_ar_v2_staged_exit_selected_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"sol-1h-ar-v2-staged-exit-{DATE_TAG}.md"


@dataclass(frozen=True, slots=True)
class StagedPolicy:
    name: str
    stage1_atr: float
    stage1_fraction: float
    final_target_atr: float
    stop_atr: float
    max_hold_bars: int
    leverage: float
    move_stop_to_entry: bool
    failure_exit: str


@dataclass(slots=True)
class LegResult:
    name: str
    mechanism: str
    source: str
    policy: StagedPolicy
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]


@dataclass(slots=True)
class StrategyResult:
    name: str
    mechanism: str
    left: LegResult | None
    right: LegResult | None
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


def failure_condition(
    frame: pd.DataFrame, bar_i: int, side: int, mode: str
) -> bool:
    if mode == "none":
        return False
    directional = {
        "roc6": side * float(frame["roc6_bps"].iloc[bar_i]) < 0.0,
        "macd": side * float(frame["macd_hist_8_21_5"].iloc[bar_i]) < 0.0,
        "di": side
        * float(frame["pdi14"].iloc[bar_i] - frame["mdi14"].iloc[bar_i])
        < 0.0,
    }
    if mode == "roc6_macd":
        return directional["roc6"] and directional["macd"]
    if mode == "roc6_di":
        return directional["roc6"] and directional["di"]
    if mode == "fast_consensus":
        return sum(directional.values()) >= 2
    raise ValueError(f"Unknown failure exit: {mode}")


def simulate_staged(
    engine: Any,
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    policy: StagedPolicy,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
) -> list[Any]:
    ts_ns = (
        frame["ts"]
        .astype("datetime64[ns, UTC]")
        .astype("int64")
        .to_numpy()
    )
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Any] = []
    blocked_until = -1
    n = len(frame)

    for signal_i in np.flatnonzero(signal):
        side = int(signal[signal_i])
        entry_i = int(signal_i + cfg.entry_delay_bars)
        if side == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[signal_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0.0:
            continue
        raw_entry = float(open_[entry_i])
        entry_price = raw_entry * (1.0 + side * engine.SLIPPAGE_PER_FILL)
        initial_stop = entry_price - side * policy.stop_atr * signal_atr
        stage1_target = entry_price + side * policy.stage1_atr * signal_atr
        final_target = (
            entry_price + side * policy.final_target_atr * signal_atr
        )
        stop_price = initial_stop
        pending_stop: float | None = None
        stage1_done = False
        failure_due = False
        remaining = 1.0
        fills: list[tuple[float, float, int, str]] = []
        timeout_i = min(n - 1, entry_i + policy.max_hold_bars)

        for bar_i in range(entry_i, timeout_i + 1):
            if pending_stop is not None:
                stop_price = (
                    max(stop_price, pending_stop)
                    if side > 0
                    else min(stop_price, pending_stop)
                )
                pending_stop = None
            bar_open = float(open_[bar_i])
            if bar_i == timeout_i:
                fills.append((remaining, bar_open, bar_i, "timeout_open"))
                remaining = 0.0
                break
            if failure_due:
                fills.append((remaining, bar_open, bar_i, "failure_exit_open"))
                remaining = 0.0
                break
            if engine.crossed_stop(bar_open, stop_price, side):
                fills.append((remaining, bar_open, bar_i, "stop_gap_open"))
                remaining = 0.0
                break

            if not stage1_done and engine.crossed_target(
                bar_open, stage1_target, side
            ):
                fraction = min(policy.stage1_fraction, remaining)
                fills.append(
                    (fraction, stage1_target, bar_i, "stage1_gap_or_open")
                )
                remaining -= fraction
                stage1_done = True
                if policy.move_stop_to_entry:
                    pending_stop = entry_price
            if remaining <= 1e-12:
                break
            if engine.crossed_target(bar_open, final_target, side):
                fills.append(
                    (remaining, final_target, bar_i, "final_gap_or_open")
                )
                remaining = 0.0
                break

            stop_hit = engine.touched_stop(
                float(high[bar_i]), float(low[bar_i]), stop_price, side
            )
            stage1_hit = (
                not stage1_done
                and engine.touched_target(
                    float(high[bar_i]),
                    float(low[bar_i]),
                    stage1_target,
                    side,
                )
            )
            final_hit = engine.touched_target(
                float(high[bar_i]),
                float(low[bar_i]),
                final_target,
                side,
            )
            # Conservative intrabar order: any stop/target ambiguity resolves
            # stop-first for the entire remaining position.
            if stop_hit:
                fills.append((remaining, stop_price, bar_i, "stop_market"))
                remaining = 0.0
                break
            if stage1_hit:
                fraction = min(policy.stage1_fraction, remaining)
                fills.append((fraction, stage1_target, bar_i, "stage1_take"))
                remaining -= fraction
                stage1_done = True
                if policy.move_stop_to_entry:
                    pending_stop = entry_price
            if remaining <= 1e-12:
                break
            if final_hit:
                fills.append(
                    (remaining, final_target, bar_i, "final_take_profit")
                )
                remaining = 0.0
                break
            failure_due = failure_condition(
                frame, bar_i, side, policy.failure_exit
            )

        if remaining > 1e-12:
            raise RuntimeError("Staged simulator left an open position")
        exit_i = max(fill[2] for fill in fills)
        price_ret = 0.0
        exit_fee = 0.0
        funding_ret = 0.0
        for fraction, raw_exit, fill_i, _reason in fills:
            exit_price = raw_exit * (
                1.0 - side * engine.SLIPPAGE_PER_FILL
            )
            price_ret += fraction * side * (exit_price / entry_price - 1.0)
            exit_fee += (
                fraction
                * engine.FEE_PER_FILL
                * exit_price
                / entry_price
            )
            funding_ret += fraction * engine.trade_funding(
                int(ts_ns[entry_i]),
                int(ts_ns[fill_i]),
                side,
                funding_times,
                funding_cumulative,
            )
        fee_ret = engine.FEE_PER_FILL + exit_fee
        net_ret_1x = price_ret - fee_ret + funding_ret
        if side > 0:
            mae = float(
                np.nanmin(low[entry_i : exit_i + 1] / entry_price - 1.0)
            )
            mfe = float(
                np.nanmax(high[entry_i : exit_i + 1] / entry_price - 1.0)
            )
        else:
            mae = float(
                np.nanmin(1.0 - high[entry_i : exit_i + 1] / entry_price)
            )
            mfe = float(
                np.nanmax(1.0 - low[entry_i : exit_i + 1] / entry_price)
            )
        mae -= 2 * engine.FEE_PER_FILL
        reasons = "+".join(dict.fromkeys(fill[3] for fill in fills))
        weighted_exit = sum(
            fraction * raw_exit for fraction, raw_exit, _fill_i, _reason in fills
        )
        trades.append(
            engine.Trade(
                config=policy.name,
                style=cfg.style,
                signal_i=int(signal_i),
                entry_i=entry_i,
                exit_i=exit_i,
                signal_ts=pd.Timestamp(ts_ns[signal_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=weighted_exit,
                exit_reason=reasons,
                bars_held=int(exit_i - entry_i),
                exposure=policy.leverage,
                net_ret_1x=float(net_ret_1x),
                equity_ret=float(policy.leverage * net_ret_1x),
                mae_1x=float(mae),
                equity_mae=float(policy.leverage * mae),
                mfe_1x=float(mfe),
                funding_ret_1x=float(funding_ret),
                signal_atr_bps=float(
                    signal_atr / frame["close"].iloc[signal_i] * 10_000.0
                ),
            )
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades


def make_leg_results(
    engine: Any,
    redesign: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    cfg: Any,
    source: str,
    policies: list[StagedPolicy],
) -> list[LegResult]:
    signal = engine.build_signal(frame, cfg)
    results: list[LegResult] = []
    for policy in policies:
        trades = simulate_staged(
            engine,
            frame,
            signal,
            cfg,
            policy,
            funding_times,
            funding_cumulative,
        )
        score, metrics = redesign.robust_prefit_score(engine, trades)
        if score <= -1e8:
            continue
        results.append(
            LegResult(
                policy.name,
                (
                    "staged_partial_take+next_bar_breakeven"
                    if policy.move_stop_to_entry
                    else "staged_partial_take"
                )
                + (
                    f"+{policy.failure_exit}_failure_exit"
                    if policy.failure_exit != "none"
                    else ""
                ),
                source,
                policy,
                trades,
                score,
                metrics,
            )
        )
    return sorted(results, key=lambda item: item.score, reverse=True)


def donchian_policies() -> list[StagedPolicy]:
    policies: list[StagedPolicy] = []
    for stage1 in (0.75, 1.0):
        for fraction in (0.33, 0.5, 0.67):
            for final in (1.5, 2.0, 3.0, 4.0):
                if final <= stage1:
                    continue
                for stop in (2.0, 3.0, 4.0):
                    for hold in (48, 72, 120):
                        for leverage in (2.0, 2.5, 3.0):
                            for breakeven in (False, True):
                                name = (
                                    f"DON_STAGE_S1{stage1:g}_F{fraction:g}_"
                                    f"T{final:g}_SL{stop:g}_H{hold}_"
                                    f"L{leverage:g}_BE{int(breakeven)}"
                                )
                                policies.append(
                                    StagedPolicy(
                                        name,
                                        stage1,
                                        fraction,
                                        final,
                                        stop,
                                        hold,
                                        leverage,
                                        breakeven,
                                        "none",
                                    )
                                )
    return policies


def vwap_policies() -> list[StagedPolicy]:
    policies: list[StagedPolicy] = []
    for stage1 in (0.75, 1.0):
        for fraction in (0.5, 0.67, 0.75):
            for final in (1.5, 2.0, 2.5):
                if final <= stage1:
                    continue
                for stop in (1.5, 2.0, 2.5, 3.0):
                    for hold in (12, 18):
                        for leverage in (1.0, 1.5):
                            for breakeven in (False, True):
                                for failure in (
                                    "none",
                                    "roc6_macd",
                                    "roc6_di",
                                    "fast_consensus",
                                ):
                                    name = (
                                        f"VWAP_STAGE_S1{stage1:g}_"
                                        f"F{fraction:g}_T{final:g}_"
                                        f"SL{stop:g}_H{hold}_L{leverage:g}_"
                                        f"BE{int(breakeven)}_{failure}"
                                    )
                                    policies.append(
                                        StagedPolicy(
                                            name,
                                            stage1,
                                            fraction,
                                            final,
                                            stop,
                                            hold,
                                            leverage,
                                            breakeven,
                                            failure,
                                        )
                                    )
    return policies


def build_strategies(
    engine: Any,
    redesign: Any,
    donchian: list[LegResult],
    vwap: list[LegResult],
    keep_per_leg: int = 40,
) -> list[StrategyResult]:
    results: list[StrategyResult] = []
    for leg in donchian[:keep_per_leg]:
        results.append(
            StrategyResult(
                f"donchian_only__{leg.name}",
                f"donchian_only:{leg.mechanism}",
                leg,
                None,
                leg.trades,
                leg.score,
                leg.metrics,
            )
        )
    for leg in vwap[:keep_per_leg]:
        results.append(
            StrategyResult(
                f"vwap_only__{leg.name}",
                f"vwap_only:{leg.mechanism}",
                None,
                leg,
                leg.trades,
                leg.score,
                leg.metrics,
            )
        )
    for left in donchian[:keep_per_leg]:
        for right in vwap[:keep_per_leg]:
            trades = engine.merge_trade_sets(
                left.trades, right.trades, left.score, right.score
            )
            score, metrics = redesign.robust_prefit_score(engine, trades)
            if score <= -1e8:
                continue
            results.append(
                StrategyResult(
                    f"ENS__{left.name}__{right.name}",
                    f"ensemble:{left.mechanism}+{right.mechanism}",
                    left,
                    right,
                    trades,
                    score,
                    metrics,
                )
            )
    return sorted(results, key=lambda item: item.score, reverse=True)


def result_row(redesign: Any, result: StrategyResult) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": result.name,
        "mechanism": result.mechanism,
        "prefit_score": result.score,
        "left_name": result.left.name if result.left else "",
        "right_name": result.right.name if result.right else "",
        "right_failure_exit": (
            result.right.policy.failure_exit if result.right else ""
        ),
        "right_breakeven": (
            result.right.policy.move_stop_to_entry if result.right else ""
        ),
    }
    for window, metric in result.metrics.items():
        row.update({f"{window}_{key}": value for key, value in metric.items()})
    for window, start, end in (
        ("prefit_tail", redesign.TRAIN_START, redesign.PREFIT_END),
        ("holdout_tail", redesign.PREFIT_END, redesign.FULL_END),
        ("full_tail", redesign.TRAIN_START, redesign.FULL_END),
    ):
        row.update(
            {
                f"{window}_{key}": value
                for key, value in redesign.tail_metrics(
                    result.trades, start, end
                ).items()
            }
        )
    return row


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2%}"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.4f}x"


def table_row(label: str, metrics: dict[str, dict[str, float]]) -> str:
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
    base = load_module(BASE_SEARCH_PATH, "sol_v2_staged_base")
    redesign = load_module(REDESIGN_PATH, "sol_v2_staged_redesign")
    engine = base.load_engine()
    frame, funding, quality = base.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    v2_source = json.loads(V2_JSON.read_text(encoding="utf-8"))
    configs = [
        engine.StrategyConfig(**config)
        for config in v2_source["best_configs"].values()
    ]
    don_cfg = next(cfg for cfg in configs if cfg.style == "donchian_break")
    vwap_cfg = next(cfg for cfg in configs if cfg.style == "vwap_revert")

    previous = json.loads(REDESIGN_JSON.read_text(encoding="utf-8"))
    previous_selected = previous["selected"]

    don_results = make_leg_results(
        engine,
        redesign,
        frame,
        funding_times,
        funding_cumulative,
        don_cfg,
        "V2 donchian signal source",
        donchian_policies(),
    )
    vwap_results = make_leg_results(
        engine,
        redesign,
        frame,
        funding_times,
        funding_cumulative,
        vwap_cfg,
        "V2 vwap signal source",
        vwap_policies(),
    )
    candidates = build_strategies(engine, redesign, don_results, vwap_results)
    if not candidates:
        raise RuntimeError("No staged-exit candidates survived prefit gates")
    selected = candidates[0]
    frozen = candidates[:100]

    rows = [result_row(redesign, item) for item in frozen]
    pd.DataFrame(rows).to_csv(CANDIDATES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected.trades)).to_csv(TRADES_CSV, index=False)

    standard_slices = [
        {
            "window": name,
            **engine.metrics(
                selected.trades, redesign.FULL_END - delta, redesign.FULL_END
            ),
        }
        for name, delta in redesign.STANDARD_SLICES
    ]
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "baseline_version": "SOL-1H-Adaptive-Regime-V2",
        "observation_id": "SOL-1H-AR-V2-STAGED-EXIT-2026-07-10",
        "status": "diagnostic_only_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_identity_freeze_not_used_for_selection",
            "fresh_oos": False,
            "intrabar_ambiguity": "stop_first",
            "breakeven_update": "effective_next_bar",
            "partial_exit_mae": "conservative_full_exposure_mae",
        },
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_tranche",
        },
        "counts": {
            "donchian_staged_survived": len(don_results),
            "vwap_staged_survived": len(vwap_results),
            "strategy_candidates_survived": len(candidates),
            "frozen_holdout_audit_set": len(frozen),
        },
        "previous_selected": previous_selected,
        "selected": {
            **result_row(redesign, selected),
            "left_policy": (
                asdict(selected.left.policy) if selected.left else None
            ),
            "right_policy": (
                asdict(selected.right.policy) if selected.right else None
            ),
        },
        "standard_slices": standard_slices,
        "top_20": [result_row(redesign, item) for item in candidates[:20]],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    selected_tail = redesign.tail_metrics(
        selected.trades, redesign.TRAIN_START, redesign.FULL_END
    )
    previous_metrics = {
        window: {
            key.removeprefix(f"{window}_"): value
            for key, value in previous_selected.items()
            if key.startswith(f"{window}_")
        }
        for window in (
            "train",
            "validation",
            "prefit",
            "reused_holdout",
            "current_full",
        )
    }
    lines = [
        "# SOL-1H-Adaptive-Regime-V2 分段止盈与失效退出诊断 - 2026-07-10",
        "",
        "## 结论",
        "",
        "本轮验证第一目标部分止盈、剩余仓位延伸目标、次 K 生效保本 stop，以及持仓后快速动量失效次根 open 退出。所有选择只使用 train/validation/prefit；reused holdout 不参与排序。",
        "",
        f"- Donchian staged variants 通过门槛：`{len(don_results)}`。",
        f"- VWAP staged variants 通过门槛：`{len(vwap_results)}`。",
        f"- 组合后通过门槛：`{len(candidates)}`；冻结审计集：`{len(frozen)}`。",
        f"- prefit-only 选中观察：`{selected.name}`。",
        "",
        "## 对照",
        "",
        "| Strategy | Prefit ann | Prefit DD | Prefit win | Reused holdout ann | Holdout DD | Holdout win | Full ann | Full DD | Full win | Full trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        table_row("first redesign", previous_metrics),
        table_row("staged-exit selected", selected.metrics),
        "",
        "## 选中机制",
        "",
        f"- mechanism：`{selected.mechanism}`。",
        f"- Donchian policy：`{selected.left.name if selected.left else 'disabled'}`。",
        f"- VWAP policy：`{selected.right.name if selected.right else 'disabled'}`。",
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
            "## 执行假设",
            "",
            "- 每个 exit tranche 单独计 fee、slippage 和 funding。",
            "- 同 K stop 与任一 target 同时触发时，对剩余仓位按 stop-first。",
            "- 第一目标命中后，保本 stop 从下一根 K 才生效，不使用同 K 内不可知顺序。",
            "- failure exit 只在完整 K 闭合确认，下一根 open 市价退出。",
            "- partial exit 后 MAE 仍按完整 exposure 计入，属于保守回撤估计。",
            "",
            "## 研究边界",
            "",
            "- 本轮沿用已揭盲 reused holdout，只能形成 diagnostic observation，不能登记版本或 promotion。",
            "- 若结构改善，应冻结参数并等待新增 fresh forward trades；不得继续用 reused holdout 倒选 policy。",
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
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_staged_exit.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))
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
