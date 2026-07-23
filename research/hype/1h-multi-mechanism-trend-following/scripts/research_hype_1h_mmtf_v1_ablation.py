from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import mmtf_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1h-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
V1_PATH = ARTIFACT_DIR / "hype_1h_mmtf_v1_search_2026-07-22.json"


def _metrics(prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_annual_factor": payload["annual_factor"],
        f"{prefix}_total_return": payload["total_return"],
        f"{prefix}_max_drawdown": payload["max_drawdown"],
        f"{prefix}_win_rate": payload["win_rate"],
        f"{prefix}_trades": payload["trades"],
        f"{prefix}_profit_factor": payload["profit_factor"],
    }


def main() -> None:
    freeze = json.loads(V1_PATH.read_text(encoding="utf-8"))
    if freeze["locked_oos_accessed"]:
        raise RuntimeError("V1 freeze unexpectedly accessed locked OOS")
    baseline = engine.config_from_dict(freeze["config"])
    book = engine.build_book(include_locked_oos=False)
    validation_start = book.terminal_ts - pd.Timedelta(days=90)
    baseline_full = engine.run_backtest(book, baseline, detailed=True)
    baseline_validation = engine.run_backtest(
        book, baseline, start_ts=validation_start, detailed=True
    )
    baseline_signature = engine.trade_signature(baseline_full)

    variants: list[tuple[str, engine.Config, frozenset[str], str]] = [
        ("baseline", baseline, frozenset(), "冻结 V1"),
        ("primary_entry_removed", baseline, frozenset({"primary_entry"}), "移除主入场"),
        ("ema_regime_removed", baseline, frozenset({"ema_regime"}), "移除 EMA regime"),
        ("adx_filter_removed", baseline, frozenset({"adx_filter"}), "移除 ADX filter"),
        ("rvol_filter_removed", baseline, frozenset({"rvol_filter"}), "移除 RVOL filter"),
        ("take_profit_removed", engine.replace_config(baseline, tp_atr=0.0), frozenset(), "移除 TP"),
        (
            "hard_stop_diagnostic_removed",
            engine.replace_config(baseline, sl_atr=100.0),
            frozenset(),
            "诊断性移除 hard stop；不可执行 promotion",
        ),
        (
            "trailing_removed",
            engine.replace_config(baseline, trail_activation_atr=1_000_000.0),
            frozenset(),
            "移除 trailing",
        ),
        (
            "breakeven_removed",
            engine.replace_config(baseline, breakeven_trigger_atr=0.0),
            frozenset(),
            "移除 breakeven",
        ),
        (
            "timeout_removed",
            engine.replace_config(baseline, max_hold_bars=1_000_000),
            frozenset(),
            "移除 timeout",
        ),
        (
            "cooldown_removed",
            engine.replace_config(baseline, cooldown_bars=0),
            frozenset(),
            "移除 cooldown",
        ),
        (
            "trend_exit_enabled",
            engine.replace_config(baseline, trend_exit=True),
            frozenset(),
            "启用此前关闭的 trend exit",
        ),
        ("long_only", engine.replace_config(baseline, direction=1), frozenset(), "只保留多头"),
        ("short_only", engine.replace_config(baseline, direction=2), frozenset(), "只保留空头"),
        (
            "inactive_breakout_atr_probe",
            engine.replace_config(baseline, breakout_atr=0.5),
            frozenset(),
            "momentum 机制下探测 breakout_atr 是否 dormant",
        ),
        (
            "inactive_exit_window_probe",
            engine.replace_config(baseline, exit_window=72),
            frozenset(),
            "trend_exit=false 时探测 exit_window 是否 dormant",
        ),
        (
            "lower_leverage_probe",
            engine.replace_config(baseline, leverage=1.5),
            frozenset(),
            "降低风险预算",
        ),
        (
            "higher_leverage_probe",
            engine.replace_config(baseline, leverage=2.5),
            frozenset(),
            "提高风险预算",
        ),
    ]

    rows: list[dict[str, Any]] = []
    for name, config, disabled, rationale in variants:
        full = engine.run_backtest(
            book, config, detailed=True, disabled_components=disabled
        )
        validation = engine.run_backtest(
            book,
            config,
            start_ts=validation_start,
            detailed=True,
            disabled_components=disabled,
        )
        signature = engine.trade_signature(full)
        row = {
            "variant": name,
            "rationale": rationale,
            "disabled_components": ",".join(sorted(disabled)),
            "path_equal_to_baseline": signature == baseline_signature,
            "trade_signature": signature,
            "config": json.dumps(asdict(config), sort_keys=True),
        }
        row.update(_metrics("prefit", full.metrics))
        row.update(_metrics("validation", validation.metrics))
        rows.append(row)

    frame = pd.DataFrame(rows)
    output_csv = ARTIFACT_DIR / "hype_1h_mmtf_v1_ablation_2026-07-22.csv"
    frame.to_csv(output_csv, index=False)
    summary = {
        "family": "HYPE-1H-Multi-Mechanism-Trend-Following",
        "version": "HYPE-1H-Multi-Mechanism-Trend-Following-V1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "locked_oos_accessed": False,
        "baseline_config_sha256": engine.config_sha256(baseline),
        "baseline_trade_signature": baseline_signature,
        "variants": int(len(frame)),
        "path_equal_variants": frame.loc[frame["path_equal_to_baseline"], "variant"].tolist(),
        "path_changing_variants": frame.loc[~frame["path_equal_to_baseline"], "variant"].tolist(),
        "baseline_metrics": {
            "prefit": baseline_full.metrics,
            "validation": baseline_validation.metrics,
        },
        "csv": str(output_csv.relative_to(ROOT)),
    }
    (ARTIFACT_DIR / "hype_1h_mmtf_v1_ablation_2026-07-22.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(frame.drop(columns="config").to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
