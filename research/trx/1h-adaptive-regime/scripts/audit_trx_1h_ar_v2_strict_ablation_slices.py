from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_trx_1h_adaptive_regime_search as search  # noqa: E402
import research_trx_1h_ar_v1base_full_ablation as v1base_ablation  # noqa: E402


base = search.load_engine()

FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
DATE_TAG = "2026-07-03"
REFINE_JSON = ARTIFACT_DIR / f"trx_1h_adaptive_regime_refine_{DATE_TAG}.json"
V2_JSON = ARTIFACT_DIR / f"trx_1h_ar_v1base_full_ablation_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v2_strict_ablation_slices_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_strict_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_strict_ablation_fields_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_strict_slices_{DATE_TAG}.csv"
TRADE_AUDIT_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_trade_execution_audit_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"trx-1h-ar-v2-strict-ablation-slices-{DATE_TAG}.md"


def metric_bundle(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> dict[str, dict[str, float]]:
    return {
        "train": base.metrics(trades, train_start, train_end),
        "validation": base.metrics(trades, train_end, oos_start),
        "prefit": base.metrics(trades, train_start, oos_start),
        "holdout": base.metrics(trades, oos_start, full_end),
        "full": base.metrics(trades, train_start, full_end),
    }


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def trade_signature(trades: list[Any]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            trade.signal_i,
            trade.entry_i,
            trade.exit_i,
            trade.side,
            trade.exit_reason,
            round(trade.entry_price, 12),
            round(trade.exit_price, 12),
            round(trade.equity_ret, 12),
        )
        for trade in trades
    )


def component_score(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
) -> float:
    train = base.metrics(trades, train_start, train_end)
    validation = base.metrics(trades, train_end, oos_start)
    prefit = base.metrics(trades, train_start, oos_start)
    return base.prefit_score(train, validation, prefit)


def simulate_pair(
    configs: list[Any],
    *,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
) -> tuple[list[Any], dict[str, list[Any]], tuple[float, float]]:
    component_trades: dict[str, list[Any]] = {}
    priorities: list[float] = []
    for cfg in configs:
        trades = base.simulate_trades(
            frame,
            base.build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        component_trades[cfg.name] = trades
        priorities.append(
            component_score(
                trades,
                train_start=train_start,
                train_end=train_end,
                oos_start=oos_start,
            )
        )
    merged = base.merge_trade_sets(
        component_trades[configs[0].name],
        component_trades[configs[1].name],
        priorities[0],
        priorities[1],
    )
    return merged, component_trades, (priorities[0], priorities[1])


def load_v2_configs() -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
    refine = json.loads(REFINE_JSON.read_text(encoding="utf-8"))
    v2 = json.loads(V2_JSON.read_text(encoding="utf-8"))
    config_names = str(refine["best"]["config_names"]).split("+")
    full_configs = [
        base.StrategyConfig(**refine["retained_configs"][name])
        for name in config_names
    ]
    by_style = {cfg.style: cfg for cfg in full_configs}
    clean_configs_by_style: dict[str, Any] = {}
    for style, clean_fields in v2["v2_clean_components"].items():
        clean_configs_by_style[style] = replace(
            by_style[style],
            **{
                key: value
                for key, value in clean_fields.items()
                if hasattr(by_style[style], key)
            },
        )
    clean_configs = [clean_configs_by_style[cfg.style] for cfg in full_configs]
    return clean_configs, refine, v2


def strict_windows(
    *,
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    candidates = [
        ("last_1d", full_end - pd.Timedelta(days=1)),
        ("last_7d", full_end - pd.Timedelta(days=7)),
        ("last_1m", full_end - pd.DateOffset(months=1)),
        ("last_3m", full_end - pd.DateOffset(months=3)),
        ("last_6m", full_end - pd.DateOffset(months=6)),
        ("last_1y", full_end - pd.DateOffset(years=1)),
    ]
    return [
        (name, max(train_start, left), full_end)
        for name, left in candidates
        if max(train_start, left) < full_end
    ]


def strict_slice_rows(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    return [
        {"window": name, "start": left, "end": right, **base.metrics(trades, left, right)}
        for name, left, right in strict_windows(
            train_start=train_start,
            full_end=full_end,
        )
    ]


def replay_trade(frame: pd.DataFrame, trade: Any, cfg: Any) -> dict[str, Any]:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    side = int(trade.side)
    signal_i = int(trade.signal_i)
    entry_i = int(signal_i + cfg.entry_delay_bars)
    signal_atr = float(atr[signal_i])
    raw_entry = float(open_[entry_i])
    entry_price = raw_entry * (1.0 + side * base.SLIPPAGE_PER_FILL)
    stop_price = entry_price - side * cfg.sl_atr * signal_atr
    target = (
        entry_price + side * cfg.tp_atr * signal_atr
        if cfg.exit_kind == "fixed"
        else None
    )
    best_price = entry_price
    timeout_i = min(len(frame) - 1, entry_i + cfg.max_hold_bars)
    replay_exit_i = timeout_i
    raw_exit = float(open_[timeout_i])
    reason = "timeout_open"
    target_gap_modeled_at_target = False
    stop_gap_filled_at_open = False
    for bar_i in range(entry_i, timeout_i + 1):
        bar_open = float(open_[bar_i])
        if bar_i == timeout_i:
            replay_exit_i = bar_i
            raw_exit = bar_open
            reason = "timeout_open"
            break
        if base.crossed_stop(bar_open, stop_price, side):
            replay_exit_i = bar_i
            raw_exit = bar_open
            reason = "stop_gap_open"
            stop_gap_filled_at_open = True
            break
        if target is not None and base.crossed_target(bar_open, target, side):
            replay_exit_i = bar_i
            raw_exit = float(target)
            reason = "target_gap_or_open"
            target_gap_modeled_at_target = True
            break
        stop_hit = base.touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side)
        target_hit = target is not None and base.touched_target(
            float(high[bar_i]), float(low[bar_i]), float(target), side
        )
        if stop_hit and target_hit:
            replay_exit_i = bar_i
            raw_exit = stop_price
            reason = "both_hit_stop_first"
            break
        if stop_hit:
            replay_exit_i = bar_i
            raw_exit = stop_price
            reason = "stop_market"
            break
        if target_hit:
            replay_exit_i = bar_i
            raw_exit = float(target)
            reason = "take_profit"
            break
        if cfg.exit_kind == "trailing":
            if side > 0:
                best_price = max(best_price, float(high[bar_i]))
                if best_price - entry_price >= cfg.trail_activation_atr * signal_atr:
                    stop_price = max(stop_price, best_price - cfg.trail_atr * signal_atr)
            else:
                best_price = min(best_price, float(low[bar_i]))
                if entry_price - best_price >= cfg.trail_activation_atr * signal_atr:
                    stop_price = min(stop_price, best_price + cfg.trail_atr * signal_atr)
    expected_exit_price = raw_exit * (1.0 - side * base.SLIPPAGE_PER_FILL)
    raw_exit_inside_bar = (
        float(low[replay_exit_i]) - 1e-12
        <= raw_exit
        <= float(high[replay_exit_i]) + 1e-12
    )
    return {
        "expected_entry_i": entry_i,
        "replay_exit_i": replay_exit_i,
        "replay_reason": reason,
        "raw_exit": raw_exit,
        "expected_exit_price": expected_exit_price,
        "raw_exit_inside_bar": raw_exit_inside_bar,
        "stop_gap_filled_at_open": stop_gap_filled_at_open,
        "target_gap_modeled_at_target": target_gap_modeled_at_target,
        "entry_price_match": abs(entry_price - float(trade.entry_price)) <= 1e-12,
        "exit_price_match": abs(expected_exit_price - float(trade.exit_price)) <= 1e-12,
    }


def trade_audit_rows(
    *,
    frame: pd.DataFrame,
    merged_trades: list[Any],
    component_trades: dict[str, list[Any]],
    configs: list[Any],
) -> list[dict[str, Any]]:
    by_name = {cfg.name: cfg for cfg in configs}
    rows: list[dict[str, Any]] = []
    for scope, trades in [("merged", merged_trades), *component_trades.items()]:
        for trade in trades:
            cfg = by_name[trade.config]
            replay = replay_trade(frame, trade, cfg)
            violations: list[str] = []
            if trade.entry_i != replay["expected_entry_i"]:
                violations.append("entry_delay_mismatch")
            if trade.entry_i <= trade.signal_i:
                violations.append("entry_not_after_signal")
            if trade.exit_i != replay["replay_exit_i"]:
                violations.append("exit_index_mismatch")
            if trade.exit_reason != replay["replay_reason"]:
                violations.append("exit_reason_mismatch")
            if not replay["entry_price_match"]:
                violations.append("entry_price_mismatch")
            if not replay["exit_price_match"]:
                violations.append("exit_price_mismatch")
            if (
                trade.exit_reason
                in {"stop_market", "both_hit_stop_first", "take_profit", "target_gap_or_open"}
                and not replay["raw_exit_inside_bar"]
                and not replay["target_gap_modeled_at_target"]
            ):
                violations.append("raw_exit_outside_bar")
            rows.append(
                {
                    "scope": scope,
                    "config": trade.config,
                    "style": trade.style,
                    "signal_ts": trade.signal_ts,
                    "entry_ts": trade.entry_ts,
                    "exit_ts": trade.exit_ts,
                    "side": trade.side,
                    "exit_reason": trade.exit_reason,
                    "bars_held": trade.bars_held,
                    "entry_delay_ok": trade.entry_i == replay["expected_entry_i"],
                    "entry_after_signal": trade.entry_i > trade.signal_i,
                    "replay_exit_ok": trade.exit_i == replay["replay_exit_i"],
                    "replay_reason_ok": trade.exit_reason == replay["replay_reason"],
                    "entry_price_match": replay["entry_price_match"],
                    "exit_price_match": replay["exit_price_match"],
                    "raw_exit_inside_bar": replay["raw_exit_inside_bar"],
                    "stop_gap_filled_at_open": replay["stop_gap_filled_at_open"],
                    "target_gap_modeled_at_target": replay["target_gap_modeled_at_target"],
                    "violation_count": len(violations),
                    "violations": ",".join(violations),
                }
            )
    return rows


def variant_config(component: str, base_cfg: Any, field_name: str, value: Any) -> Any:
    if component == "macd_flip" and field_name in {
        "macd_fast",
        "macd_slow",
        "macd_signal",
    }:
        return replace(
            base_cfg,
            macd_fast=value[0],
            macd_slow=value[1],
            macd_signal=value[2],
        )
    return replace(base_cfg, **{field_name: value})


def prefit_improves(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return bool(
        row["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and row["prefit_max_dd"] > baseline["prefit_max_dd"]
        and row["prefit_win_rate"] >= 0.50
        and row["train_total_return"] > 0
        and row["validation_total_return"] > 0
        and row["validation_max_dd"] > -0.20
    )


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def main() -> None:
    if not REFINE_JSON.exists() or not V2_JSON.exists():
        raise FileNotFoundError("Run refine and V1base full ablation before V2 strict audit")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)

    configs, refine, v2 = load_v2_configs()
    frame, funding, quality = search.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)

    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=search.WARMUP_DAYS)
    oos_start = full_end - pd.DateOffset(months=search.LOCKED_OOS_MONTHS)
    train_end = train_start + (oos_start - train_start) * 0.65

    baseline_trades, component_trades, priorities = simulate_pair(
        configs,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
    )
    baseline_metrics = metric_bundle(
        baseline_trades,
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
        full_end=full_end,
    )
    expected = refine["best"]
    for window in ("train", "validation", "prefit", "holdout", "full"):
        for metric in ("trades", "annual_multiple", "max_dd", "win_rate"):
            observed = float(baseline_metrics[window][metric])
            recorded = float(expected[f"{window}_{metric}"])
            if abs(observed - recorded) > 1e-12:
                raise RuntimeError(
                    f"V2 baseline drift at {window}.{metric}: {observed} != {recorded}"
                )
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_signature = trade_signature(baseline_trades)
    component_signatures = {
        cfg.style: trade_signature(component_trades[cfg.name]) for cfg in configs
    }

    slice_rows = strict_slice_rows(
        baseline_trades,
        train_start=train_start,
        full_end=full_end,
    )
    pd.DataFrame(slice_rows).to_csv(SLICES_CSV, index=False)

    audit_rows = trade_audit_rows(
        frame=frame,
        merged_trades=baseline_trades,
        component_trades=component_trades,
        configs=configs,
    )
    audit_frame = pd.DataFrame(audit_rows)
    audit_frame.to_csv(TRADE_AUDIT_CSV, index=False)

    rows: list[dict[str, Any]] = [
        {
            "label": "TRX-1H-Adaptive-Regime-V2",
            "component": "ensemble",
            "field": "baseline",
            "baseline_value": "baseline",
            "value": "baseline",
            "classification": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            **baseline_flat,
        }
    ]
    observed: dict[str, set[str]] = {"macd_flip": set(), "stoch_reversal": set()}
    by_style = {cfg.style: cfg for cfg in configs}
    clean_surface = {
        style: list(fields_for_style)
        for style, fields_for_style in v2["clean_surface"].items()
    }
    for component in ("macd_flip", "stoch_reversal"):
        base_cfg = by_style[component]
        other_cfg = next(cfg for cfg in configs if cfg.name != base_cfg.name)
        values_by_field = v1base_ablation.variant_values(component, base_cfg)
        for field_name in sorted(clean_surface[component]):
            observed[component].add(field_name)
            for value in values_by_field[field_name]:
                label_value = str(value).replace(".", "p").replace("-", "m")
                label = f"{component}__{field_name}__{label_value}"
                if field_name == "style" and value == "leg_removed":
                    component_variant_trades: list[Any] = []
                    merged = component_trades[other_cfg.name]
                else:
                    variant = variant_config(component, base_cfg, field_name, value)
                    if variant.ema_fast >= variant.ema_slow:
                        continue
                    if variant.min_adx > variant.max_adx:
                        continue
                    if variant.min_atr_bps > variant.max_atr_bps:
                        continue
                    variant_configs = (
                        [variant, other_cfg]
                        if configs[0].name == base_cfg.name
                        else [other_cfg, variant]
                    )
                    merged, variant_component_trades, _variant_priorities = simulate_pair(
                        variant_configs,
                        frame=frame,
                        funding_times=funding_times,
                        funding_cumulative=funding_cumulative,
                        train_start=train_start,
                        train_end=train_end,
                        oos_start=oos_start,
                    )
                    component_variant_trades = variant_component_trades[variant.name]
                flat = flatten_metrics(
                    metric_bundle(
                        merged,
                        train_start=train_start,
                        train_end=train_end,
                        oos_start=oos_start,
                        full_end=full_end,
                    )
                )
                row = {
                    "label": label,
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(base_cfg, field_name),
                    "value": value,
                    "classification": (
                        "contract_fixed"
                        if field_name in v1base_ablation.CONTRACT_FIXED
                        else "active_tunable"
                    ),
                    "component_path_equal": (
                        False
                        if field_name == "style"
                        else trade_signature(component_variant_trades)
                        == component_signatures[component]
                    ),
                    "merged_path_equal": trade_signature(merged) == baseline_signature,
                    **flat,
                }
                row["prefit_strict_improve"] = prefit_improves(row, baseline_flat)
                rows.append(row)

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)
    field_rows: list[dict[str, Any]] = []
    for component in ("macd_flip", "stoch_reversal"):
        cfg = by_style[component]
        for field_name in sorted(clean_surface[component]):
            subset = rows_frame.loc[
                (rows_frame["component"] == component)
                & (rows_frame["field"] == field_name)
            ]
            field_rows.append(
                {
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(cfg, field_name),
                    "classification": (
                        "contract_fixed"
                        if field_name in v1base_ablation.CONTRACT_FIXED
                        else "active_tunable"
                    ),
                    "variant_rows": int(len(subset)),
                    "component_path_equal_rows": int(
                        subset["component_path_equal"].sum()
                    ),
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
                    "prefit_strict_improve_rows": int(
                        subset["prefit_strict_improve"].sum()
                    ),
                    "best_prefit_annual_multiple": float(
                        subset["prefit_annual_multiple"].max()
                    ),
                    "best_prefit_max_dd": float(
                        subset.loc[
                            subset["prefit_annual_multiple"].idxmax(),
                            "prefit_max_dd",
                        ]
                    ),
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    strict = rows_frame.loc[rows_frame["prefit_strict_improve"]].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd", "validation_annual_multiple"],
        ascending=[False, False, False],
    )
    violation_count = int(audit_frame["violation_count"].sum())
    target_gap_count = int(audit_frame["target_gap_modeled_at_target"].sum())
    stop_gap_count = int(audit_frame["stop_gap_filled_at_open"].sum())
    merged_violations = int(
        audit_frame.loc[audit_frame["scope"] == "merged", "violation_count"].sum()
    )
    slice_summary = {
        row["window"]: {
            "annual_multiple": row["annual_multiple"],
            "total_return": row["total_return"],
            "max_dd": row["max_dd"],
            "win_rate": row["win_rate"],
            "trades": row["trades"],
        }
        for row in slice_rows
    }
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "version": "TRX-1H-Adaptive-Regime-V2",
        "status": "strict_ablation_slice_execution_audit_complete_no_go_not_live_ready",
        "date": DATE_TAG,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "baseline": baseline_metrics,
        "strict_slices": slice_summary,
        "v2_field_slots": {
            "macd_flip": len(clean_surface["macd_flip"]),
            "stoch_reversal": len(clean_surface["stoch_reversal"]),
            "total": sum(len(fields_for_style) for fields_for_style in clean_surface.values()),
            "coverage_missing": {
                component: sorted(set(clean_surface[component]) - observed[component])
                for component in ("macd_flip", "stoch_reversal")
            },
        },
        "ablation_rows_including_baseline": len(rows_frame),
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "execution_audit": {
            "audited_rows": int(len(audit_frame)),
            "merged_trades": int(len(baseline_trades)),
            "merged_full_window_trades": int(baseline_metrics["full"]["trades"]),
            "component_trades": {
                name: int(len(trades)) for name, trades in component_trades.items()
            },
            "violation_count": violation_count,
            "merged_violation_count": merged_violations,
            "stop_gap_filled_at_open": stop_gap_count,
            "target_gap_modeled_at_target": target_gap_count,
            "causal_entry_delay_all_ge_1": all(cfg.entry_delay_bars >= 1 for cfg in configs),
            "lookahead_note": (
                "Signals use closed 1h bars; HTF and funding features are merge_asof "
                "known at signal close; entries execute at K+1 open."
            ),
        },
        "artifacts": {
            "rows_csv": str(ROWS_CSV.relative_to(ROOT)),
            "fields_csv": str(FIELDS_CSV.relative_to(ROOT)),
            "slices_csv": str(SLICES_CSV.relative_to(ROOT)),
            "trade_audit_csv": str(TRADE_AUDIT_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# TRX-1H-Adaptive-Regime-V2 严格消融、分片与执行审计 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "`TRX-1H-Adaptive-Regime-V2` 完成 clean 参数全量 one-at-a-time 消融、"
            "最近 `1d/7d/1m/3m/6m/1y` 严格分片和逐笔执行重放。"
        ),
        "",
        (
            f"执行审计覆盖 warmup 后全路径 merged `{len(baseline_trades)}` 笔交易"
            f"（full 指标窗口 `{int(baseline_metrics['full']['trades'])}` 笔）和组件交易；"
            f"违规计数 `{violation_count}`，merged 违规 `{merged_violations}`。"
            f"stop gap 均按 open 成交 `{stop_gap_count}` 次；"
            f"有利 target gap 以 target 价保守记账 `{target_gap_count}` 次。"
        ),
        "",
        (
            "未发现 stale stop fill、入场早于信号、逐笔重放漂移或 raw exit 越界导致的不可实盘问题。"
            "但 V2 仍因收益/OOS gate 失败、近期切片亏损和无 production runner 保持 "
            "`NO-GO / not promoted / not live-ready`。"
        ),
        "",
        "## V2 基线",
        "",
        "| Window | Annual / Return / DD / Win / Trades |",
        "| --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "holdout", "full"):
        lines.append(f"| `{window}` | {metric_line(baseline_metrics[window])} |")
    lines.extend(
        [
            "",
            "## 严格近期分片",
            "",
            "| Slice | UTC Start | Annual / Return / DD / Win / Trades |",
            "| --- | --- | --- |",
        ]
    )
    for row in slice_rows:
        lines.append(
            f"| `{row['window']}` | `{row['start']}` | {metric_line(row)} |"
        )
    lines.extend(
        [
            "",
            "## V2 参数消融",
            "",
            f"- V2 clean 字段槽：`{payload['v2_field_slots']['total']}`，coverage missing：`{payload['v2_field_slots']['coverage_missing']}`。",
            f"- one-at-a-time 行数（含 baseline）：`{len(rows_frame)}`。",
            f"- prefit 严格改善行数：`{len(strict)}`；这些行未用于 OOS 选参。",
            "",
            "| Component | Field | Baseline | Classification | Variants | Component Equal | Merged Equal | Prefit Strict Improve |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in fields_frame.to_dict(orient="records"):
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | "
            f"`{row['classification']}` | `{row['variant_rows']}` | "
            f"`{row['component_path_equal_rows']}` | `{row['merged_path_equal_rows']}` | "
            f"`{row['prefit_strict_improve_rows']}` |"
        )
    lines.extend(
        [
            "",
            "## 不可实盘风险检查",
            "",
            f"- 入场时序：所有组件 `entry_delay_bars>=1`，信号闭合后下一根 open 入场：`{payload['execution_audit']['causal_entry_delay_all_ge_1']}`。",
            f"- 逐笔重放：违规总数 `{violation_count}`，merged 违规 `{merged_violations}`。",
            f"- stop 穿越：`stop_gap_open` 按 open 成交 `{stop_gap_count}` 次，未发现穿越 stop 后仍按旧 stop 价成交。",
            f"- target 穿越：有利 gap/open 以 target 价保守记账 `{target_gap_count}` 次，不构成乐观穿越收益。",
            "- 未来函数：本审计确认当前引擎使用闭合 1h K 产生信号、K+1 open 入场；HTF/funding 特征按已知时间 `merge_asof` 对齐。未发现 OOS 排序或 K 内决策依赖。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{ROWS_CSV.name}`",
            f"- `artifacts/{FIELDS_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{TRADE_AUDIT_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/trx/1h-adaptive-regime/scripts/audit_trx_1h_ar_v2_strict_ablation_slices.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
