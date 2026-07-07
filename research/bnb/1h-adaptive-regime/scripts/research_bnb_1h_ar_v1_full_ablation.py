from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_bnb_1h_adaptive_regime_search.py"
FREEZE_JSON = ARTIFACT_DIR / "bnb_1h_ar_cap3_highwin_frozen_primary_2026-07-06-cap3-highwin.json"
DATE_TAG = "2026-07-06"

SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_ar_v1_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v1_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v1_full_ablation_fields_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"bnb-1h-ar-v1-full-parameter-ablation-{DATE_TAG}.md"

MAX_LEVERAGE = 3.0
TARGET_ANNUAL_MULTIPLE = 2.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("bnb_1h_base_search", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load base search script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2f}x"


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{mult(metric['annual_multiple'])}` / `{pct(metric['total_return'])}` / "
        f"`{pct(metric['max_dd'])}` / `{pct(metric['win_rate'])}` / "
        f"`{int(metric['trades'])}`"
    )


def load_context() -> tuple[Any, Any, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    base = load_base()
    engine = base.load_engine()
    raw_frame, funding, quality = base.load_data()
    frame = engine.add_features(raw_frame, funding)
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    return base, engine, frame, funding, quality, freeze


def config_from_dict(engine: Any, cfg_dict: dict[str, Any]) -> Any:
    cfg = engine.StrategyConfig(**cfg_dict)
    return replace(
        cfg,
        fixed_leverage=min(float(cfg.fixed_leverage), MAX_LEVERAGE),
        max_leverage=min(float(cfg.max_leverage), MAX_LEVERAGE),
        entry_delay_bars=1,
    )


def simulate_component(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    cfg: Any,
    *,
    start: pd.Timestamp | None = None,
) -> list[Any]:
    signal = engine.build_signal(frame, cfg)
    if start is not None:
        allowed = frame["ts"] + pd.Timedelta(hours=cfg.entry_delay_bars) >= start
        signal = signal.copy()
        signal[~allowed.to_numpy()] = 0
    return engine.simulate_trades(frame, signal, cfg, funding_times, funding_cumulative)


def merge_trades(engine: Any, parts: list[list[Any]], priorities: tuple[float, ...]) -> list[Any]:
    if len(parts) == 1:
        return parts[0]
    return engine.merge_trade_sets(parts[0], parts[1], priorities[0], priorities[1])


def simulate_strategy(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    configs: tuple[Any, ...],
    priorities: tuple[float, ...],
    *,
    removed_component: str | None = None,
    start: pd.Timestamp | None = None,
) -> tuple[list[Any], dict[str, list[Any]]]:
    component_trades: dict[str, list[Any]] = {}
    parts: list[list[Any]] = []
    active_priorities: list[float] = []
    for index, cfg in enumerate(configs):
        if cfg.name == removed_component:
            continue
        trades = simulate_component(
            engine, frame, funding_times, funding_cumulative, cfg, start=start
        )
        component_trades[cfg.name] = trades
        parts.append(trades)
        active_priorities.append(priorities[index])
    if not parts:
        return [], component_trades
    return merge_trades(engine, parts, tuple(active_priorities)), component_trades


def metric_bundle(
    engine: Any,
    trades: list[Any],
    split: dict[str, pd.Timestamp],
    oos_trades: list[Any],
) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, split["train_start"], split["train_end"]),
        "validation": engine.metrics(trades, split["train_end"], split["oos_start"]),
        "prefit": engine.metrics(trades, split["train_start"], split["oos_start"]),
        "holdout": engine.metrics(oos_trades, split["oos_start"], split["full_end"]),
        "full": engine.metrics(trades, split["train_start"], split["full_end"]),
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
            trade.style,
            trade.signal_i,
            trade.entry_i,
            trade.exit_i,
            trade.side,
            trade.exit_reason,
            round(float(trade.entry_price), 8),
            round(float(trade.exit_price), 8),
            round(float(trade.exposure), 8),
            round(float(trade.equity_ret), 12),
        )
        for trade in trades
    )


def neutral_value(component: str, field_name: str, current: Any) -> Any:
    common: dict[str, Any] = {
        "side_mode": "both",
        "ema_fast": 21,
        "ema_slow": 144,
        "ema_htf": 55,
        "indicator_window": 14,
        "threshold_low": 0.0,
        "threshold_high": 100.0,
        "band_k": 0.0,
        "pullback_atr": 10.0,
        "roc_window": 12,
        "roc_threshold_bps": 0.0,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "min_adx": 0.0,
        "max_adx": 100.0,
        "min_rvol": 0.0,
        "min_atr_bps": 0.0,
        "max_atr_bps": 10_000.0,
        "min_dir_roc_bps": -10_000.0,
        "max_dist_ema_bps": 100_000.0,
        "htf_mode": "none",
        "require_macd_turn": False,
        "require_body_dir": False,
        "max_aligned_funding_bps": 10_000.0,
        "exit_kind": "fixed",
        "tp_atr": 100_000.0,
        "sl_atr": 100_000.0,
        "trail_activation_atr": 100_000.0,
        "trail_atr": 100_000.0,
        "max_hold_bars": 100_000,
        "cooldown_bars": 0,
        "entry_delay_bars": 1,
        "sizing_kind": "fixed",
        "fixed_leverage": 1.0,
        "risk_fraction": 0.01,
        "max_leverage": 1.0,
    }
    if component == "wick_reject":
        common.update(
            {
                "threshold_low": 1.0,
                "threshold_high": 0.0,
                "pullback_atr": 0.0,
            }
        )
    value = common[field_name]
    if value == current:
        alternatives: dict[str, Any] = {
            "ema_fast": 34,
            "ema_slow": 233,
            "ema_htf": 144,
            "indicator_window": 32,
            "threshold_low": 0.5,
            "threshold_high": 0.5,
            "band_k": 1.0,
            "roc_window": 48,
            "macd_fast": 21,
            "macd_slow": 55,
            "macd_signal": 13,
            "max_adx": 45.0,
            "exit_kind": "trailing",
            "fixed_leverage": 2.0,
            "risk_fraction": 0.02,
            "max_leverage": 3.0,
        }
        value = alternatives.get(field_name, value)
    return value


def protected_field(field_name: str) -> bool:
    return field_name in {"name", "style", "entry_delay_bars"}


def row_for_variant(
    *,
    variant_type: str,
    component: str,
    field_name: str,
    baseline_value: Any,
    replacement_value: Any,
    metrics: dict[str, dict[str, float]],
    baseline_flat: dict[str, float],
    same_prefit_signature: bool,
    same_full_signature: bool,
) -> dict[str, Any]:
    flat = flatten_metrics(metrics)
    row = {
        "variant_type": variant_type,
        "component": component,
        "field": field_name,
        "baseline_value": json.dumps(json_safe(baseline_value), ensure_ascii=False),
        "replacement_value": json.dumps(json_safe(replacement_value), ensure_ascii=False),
        "same_prefit_signature": same_prefit_signature,
        "same_full_signature": same_full_signature,
        "safe_remove": same_full_signature and variant_type == "field_neutralized",
    }
    row.update(flat)
    for key, value in flat.items():
        row[f"delta_{key}"] = value - baseline_flat[key]
    return row


def gate(metric: dict[str, float], *, min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= TARGET_WIN_RATE
        and metric["max_dd"] > TARGET_MAX_DD
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    _base, engine, frame, funding, quality, freeze = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    split = {
        key: pd.Timestamp(value)
        for key, value in freeze["split"].items()
        if key in {"train_start", "train_end", "oos_start", "full_end"}
    }
    configs = tuple(config_from_dict(engine, cfg) for cfg in freeze["configs"])
    priorities = tuple(float(value) for value in freeze["priorities"])

    baseline_trades, baseline_components = simulate_strategy(
        engine, frame, funding_times, funding_cumulative, configs, priorities
    )
    baseline_oos_trades, _ = simulate_strategy(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        configs,
        priorities,
        start=split["oos_start"],
    )
    baseline_metrics = metric_bundle(engine, baseline_trades, split, baseline_oos_trades)
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_prefit_sig = trade_signature(
        [
            trade
            for trade in baseline_trades
            if split["train_start"] <= trade.entry_ts < split["oos_start"]
        ]
    )
    baseline_full_sig = trade_signature(baseline_trades)

    rows: list[dict[str, Any]] = []
    for removed in configs:
        variant_trades, _ = simulate_strategy(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            configs,
            priorities,
            removed_component=removed.name,
        )
        variant_oos_trades, _ = simulate_strategy(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            configs,
            priorities,
            removed_component=removed.name,
            start=split["oos_start"],
        )
        metrics = metric_bundle(engine, variant_trades, split, variant_oos_trades)
        rows.append(
            row_for_variant(
                variant_type="component_removed",
                component=removed.style,
                field_name="component",
                baseline_value=removed.name,
                replacement_value="removed",
                metrics=metrics,
                baseline_flat=baseline_flat,
                same_prefit_signature=False,
                same_full_signature=False,
            )
        )

    for target_index, target in enumerate(configs):
        for field_name, current_value in asdict(target).items():
            if protected_field(field_name):
                continue
            replacement_value = neutral_value(target.style, field_name, current_value)
            if replacement_value == current_value:
                continue
            variant_configs = list(configs)
            variant_configs[target_index] = replace(target, **{field_name: replacement_value})
            variant_configs_tuple = tuple(variant_configs)
            variant_trades, _ = simulate_strategy(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                variant_configs_tuple,
                priorities,
            )
            variant_oos_trades, _ = simulate_strategy(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                variant_configs_tuple,
                priorities,
                start=split["oos_start"],
            )
            metrics = metric_bundle(engine, variant_trades, split, variant_oos_trades)
            prefit_sig = trade_signature(
                [
                    trade
                    for trade in variant_trades
                    if split["train_start"] <= trade.entry_ts < split["oos_start"]
                ]
            )
            full_sig = trade_signature(variant_trades)
            rows.append(
                row_for_variant(
                    variant_type="field_neutralized",
                    component=target.style,
                    field_name=field_name,
                    baseline_value=current_value,
                    replacement_value=replacement_value,
                    metrics=metrics,
                    baseline_flat=baseline_flat,
                    same_prefit_signature=prefit_sig == baseline_prefit_sig,
                    same_full_signature=full_sig == baseline_full_sig,
                )
            )

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)

    field_rows: list[dict[str, Any]] = []
    for row in rows:
        if row["variant_type"] != "field_neutralized":
            continue
        classification = "keep_active"
        if row["same_full_signature"]:
            classification = "remove_noop"
        elif row["prefit_annual_multiple"] >= baseline_flat["prefit_annual_multiple"] and row[
            "prefit_max_dd"
        ] >= baseline_flat["prefit_max_dd"]:
            classification = "changed_path_prefit_nonworse_review_only"
        field_rows.append(
            {
                "component": row["component"],
                "field": row["field"],
                "classification": classification,
                "same_full_signature": row["same_full_signature"],
                "prefit_annual_multiple": row["prefit_annual_multiple"],
                "prefit_max_dd": row["prefit_max_dd"],
                "prefit_win_rate": row["prefit_win_rate"],
                "holdout_annual_multiple": row["holdout_annual_multiple"],
                "holdout_max_dd": row["holdout_max_dd"],
                "holdout_win_rate": row["holdout_win_rate"],
                "full_annual_multiple": row["full_annual_multiple"],
                "full_max_dd": row["full_max_dd"],
                "full_win_rate": row["full_win_rate"],
            }
        )
    fields_frame = pd.DataFrame(field_rows).sort_values(
        ["classification", "component", "field"]
    )
    fields_frame.to_csv(FIELDS_CSV, index=False)

    removable = fields_frame.loc[fields_frame["classification"] == "remove_noop"]
    changed_nonworse = fields_frame.loc[
        fields_frame["classification"] == "changed_path_prefit_nonworse_review_only"
    ]
    component_rows = rows_frame.loc[rows_frame["variant_type"] == "component_removed"]

    summary = {
        "family": "BNB-1H-Adaptive-Regime",
        "version": "BNB-1H-Adaptive-Regime-V1",
        "status": "full_ablation_complete_not_promoted",
        "data_quality": quality,
        "baseline": baseline_metrics,
        "baseline_gates": {
            "prefit_cap3_highwin": gate(baseline_metrics["prefit"], min_trades=50),
            "holdout_cap3_highwin": gate(baseline_metrics["holdout"], min_trades=12),
            "full_cap3_highwin": gate(baseline_metrics["full"], min_trades=50),
        },
        "rows": len(rows),
        "remove_noop_count": int(len(removable)),
        "changed_path_prefit_nonworse_review_only_count": int(len(changed_nonworse)),
        "artifacts": {
            "rows_csv": str(ROWS_CSV.relative_to(ROOT)),
            "fields_csv": str(FIELDS_CSV.relative_to(ROOT)),
            "report_md": str(REPORT_MD.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(json_safe(summary), indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# BNB-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-06",
        "",
        "## 结论",
        "",
        "`BNB-1H-Adaptive-Regime-V1` 的全参数消融完成。V1 仍是 `diagnostic observation / not promoted / not live-ready`；本报告只用于识别 no-op 参数和机制敏感参数，不用于 OOS 后验选参。",
        "",
        f"- Baseline prefit：{metric_line(baseline_metrics['prefit'])}。",
        f"- Baseline locked OOS：{metric_line(baseline_metrics['holdout'])}。",
        f"- Baseline full：{metric_line(baseline_metrics['full'])}。",
        f"- Field ablation rows：`{len(rows_frame)}`；可安全删除 no-op 参数：`{len(removable)}`。",
        "",
        "## 可从 clean spec 删除的 no-op 参数",
        "",
    ]
    if removable.empty:
        lines.append("- 未发现交易路径完全不变的可删除字段。")
    else:
        for component, group in removable.groupby("component"):
            fields = "`, `".join(group["field"].tolist())
            lines.append(f"- `{component}`：`{fields}`。")

    lines.extend(
        [
            "",
            "## 改变交易路径但样本内不差的参数",
            "",
            "这些变体不能直接作为 clean 版本采用，因为它们改变了交易路径；若要继续，应作为新搜索/新冻结版本处理，而不是用 OOS 后验选择。",
        ]
    )
    if changed_nonworse.empty:
        lines.append("- 无。")
    else:
        for _, row in changed_nonworse.head(20).iterrows():
            lines.append(
                f"- `{row['component']}.{row['field']}`：prefit `{row['prefit_annual_multiple']:.2f}x / {row['prefit_max_dd']:.2%} / {row['prefit_win_rate']:.2%}`；full `{row['full_annual_multiple']:.2f}x / {row['full_max_dd']:.2%} / {row['full_win_rate']:.2%}`。"
            )

    lines.extend(
        [
            "",
            "## Component removal",
            "",
            "| Removed component | Prefit | Locked OOS | Full |",
            "| --- | --- | --- | --- |",
        ]
    )
    for _, row in component_rows.iterrows():
        lines.append(
            f"| `{row['component']}` | `{row['prefit_annual_multiple']:.2f}x / {row['prefit_max_dd']:.2%} / {row['prefit_win_rate']:.2%}` | `{row['holdout_annual_multiple']:.2f}x / {row['holdout_max_dd']:.2%} / {row['holdout_win_rate']:.2%}` | `{row['full_annual_multiple']:.2f}x / {row['full_max_dd']:.2%} / {row['full_win_rate']:.2%}` |"
        )

    lines.extend(
        [
            "",
            "## Clean spec 边界",
            "",
            "可以删除的只包括交易路径完全不变的 no-op 字段。`entry_delay_bars`、执行成本、next-open 入场、stop-first 和 funding 口径不是可删参数。",
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{ROWS_CSV.relative_to(ROOT)}`",
            f"- `{FIELDS_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(json_safe(summary), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
