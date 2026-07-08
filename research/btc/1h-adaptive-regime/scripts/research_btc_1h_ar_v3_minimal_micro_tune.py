from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v1_clean as clean  # noqa: E402
import btc_1h_ar_v3 as v3  # noqa: E402
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-07"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v3_minimal_micro_tune_{DATE_TAG}.json"
GRID_CSV = ARTIFACT_DIR / f"btc_1h_ar_v3_minimal_micro_tune_grid_{DATE_TAG}.csv"
TRADES_CSV = (
    ARTIFACT_DIR / f"btc_1h_ar_v3_minimal_micro_tune_selected_trades_{DATE_TAG}.csv"
)
REPORT_MD = NOTES_DIR / f"btc-1h-ar-v3-minimal-micro-tune-{DATE_TAG}.md"


# V3 最小等价表面（见 btc-1h-ar-v3-param-necessity-2026-07-07.md）：
# 已移除的槽位固定为中和值，微调只允许触碰必要参数。
MINIMAL_KELTNER = replace(
    v3.KELTNER,
    max_atr_bps=10000.0,
    min_dir_roc_bps=-10000.0,
    max_aligned_funding_bps=10000.0,
    max_hold_bars=100000,
    cooldown_bars=0,
)
MINIMAL_CCI = replace(v3.CCI, max_atr_bps=10000.0, cooldown_bars=0)

# 必要参数搜索空间；杠杆固定为 V3 值，避免用曝光缩放伪装成结构改善。
KELTNER_SPACE: dict[str, list[Any]] = {
    "band_k": [1.9, 2.0, 2.1],
    "min_adx": [38.0, 40.0, 42.0],
    "min_rvol": [1.15, 1.25, 1.4],
    "htf_mode": ["h4", "none"],
    "tp_atr": [1.4, 1.5, 1.75],
    "sl_atr": [4.5, 5.0, 5.5],
}
CCI_SPACE: dict[str, list[Any]] = {
    "ema_htf": [233, 377],
    "threshold_high": [115.0, 125.0, 135.0],
    "max_adx": [38.0, 40.0, 42.0],
    "min_rvol": [1.25, 1.4],
    "min_atr_bps": [75.0, 90.0],
    "max_dist_ema_bps": [700.0, 750.0, 1000.0],
    "tp_atr": [5.5, 6.0],
    "sl_atr": [1.5, 2.0],
    "max_hold_bars": [72, 96],
}

# 腿级预筛选池大小；两腿全组合过大，先按腿 prefit score 截断。
KELTNER_POOL = 96
CCI_POOL = 256


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


EPS = 1e-9


def base_constraints(metrics: dict[str, dict[str, float]]) -> bool:
    train = metrics["train"]
    validation = metrics["validation"]
    return bool(
        train["total_return"] > 0
        and validation["total_return"] > 0
        and train["win_rate"] >= 0.80
        and validation["win_rate"] >= 0.80
        and train["max_dd"] > -0.20
        and validation["max_dd"] > -0.20
    )


def strict_gate(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> bool:
    """prefit 年化、回撤、胜率三项同时严格优于 V3。"""
    prefit = metrics["prefit"]
    ref = reference["prefit"]
    return bool(
        prefit["annual_multiple"] > ref["annual_multiple"] + EPS
        and prefit["max_dd"] > ref["max_dd"] + EPS
        and prefit["win_rate"] > ref["win_rate"] + EPS
        and base_constraints(metrics)
    )


def pareto_gate(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> bool:
    """prefit 年化严格更高，回撤与胜率不劣于 V3。"""
    prefit = metrics["prefit"]
    ref = reference["prefit"]
    return bool(
        prefit["annual_multiple"] > ref["annual_multiple"] + EPS
        and prefit["max_dd"] >= ref["max_dd"] - EPS
        and prefit["win_rate"] >= ref["win_rate"] - EPS
        and base_constraints(metrics)
    )


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    baseline_trades, *_ = v3.simulate_v3(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_signature = v1.trade_signature(baseline_trades)
    baseline_metrics = v1.metrics(engine, baseline_trades)

    # 最小表面必须逐笔等价 V3，否则搜索基线不成立。
    def leg_variants(
        space: dict[str, list[Any]], base: Any, to_base: Any, name: str
    ) -> list[tuple[dict[str, Any], list[Any], float]]:
        variants = []
        for values in product(*space.values()):
            updates = dict(zip(space.keys(), values, strict=True))
            cfg = replace(base, **updates)
            trades = v1.simulate_component(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                replace(to_base(engine, cfg), name=name),
            )
            score = tune.leg_score(tune.prefit_metrics(engine, trades))
            variants.append((updates, trades, score, cfg))
        return variants

    minimal_check, *_ = v3.simulate_v3(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=replace(
            clean.keltner_to_base(engine, MINIMAL_KELTNER),
            name="BTC_1H_AR_V3_MIN_KELTNER",
        ),
        cci=replace(
            clean.cci_to_base(engine, MINIMAL_CCI), name="BTC_1H_AR_V3_MIN_CCI"
        ),
    )
    if v1.trade_signature(minimal_check) != baseline_signature:
        raise RuntimeError("Minimal surface drifted from V3 trade path")

    keltner_variants = leg_variants(
        KELTNER_SPACE, MINIMAL_KELTNER, clean.keltner_to_base, "BTC_1H_AR_V3M_KELTNER"
    )
    cci_variants = leg_variants(
        CCI_SPACE, MINIMAL_CCI, clean.cci_to_base, "BTC_1H_AR_V3M_CCI"
    )
    keltner_leg_total = len(keltner_variants)
    cci_leg_total = len(cci_variants)
    keltner_variants = sorted(
        keltner_variants, key=lambda item: item[2], reverse=True
    )[:KELTNER_POOL]
    cci_variants = sorted(cci_variants, key=lambda item: item[2], reverse=True)[
        :CCI_POOL
    ]

    rows: list[dict[str, Any]] = []
    for k_idx, (k_updates, k_trades, k_score, _k_cfg) in enumerate(keltner_variants):
        for c_idx, (c_updates, c_trades, c_score, _c_cfg) in enumerate(cci_variants):
            merged = engine.merge_trade_sets(k_trades, c_trades, k_score, c_score)
            metrics = v1.metrics(engine, merged)
            rows.append(
                {
                    "label": f"V3M_{k_idx:03d}_{c_idx:03d}",
                    "passes_strict_gate": strict_gate(metrics, baseline_metrics),
                    "passes_pareto_gate": pareto_gate(metrics, baseline_metrics),
                    **{f"keltner_{key}": value for key, value in k_updates.items()},
                    **{f"cci_{key}": value for key, value in c_updates.items()},
                    "keltner_priority": k_score,
                    "cci_priority": c_score,
                    **flatten_metrics(metrics),
                }
            )

    grid = pd.DataFrame(rows)
    strict_passed = grid.loc[grid["passes_strict_gate"]].copy()
    pareto_passed = grid.loc[grid["passes_pareto_gate"]].copy()
    grid.sort_values(
        [
            "passes_strict_gate",
            "passes_pareto_gate",
            "prefit_annual_multiple",
            "prefit_max_dd",
        ],
        ascending=[False, False, False, False],
    ).to_csv(GRID_CSV, index=False)

    if not strict_passed.empty:
        selection_tier = "strict_three_way_improvement"
        pool = strict_passed
    elif not pareto_passed.empty:
        selection_tier = "pareto_annual_up_dd_win_not_worse"
        pool = pareto_passed
    else:
        selection_tier = "no_gate_pass_best_prefit_annual_fallback"
        pool = grid
    selected_row = (
        pool.sort_values(
            [
                "prefit_annual_multiple",
                "prefit_max_dd",
                "prefit_win_rate",
                "validation_annual_multiple",
            ],
            ascending=[False, False, False, False],
        )
        .iloc[0]
        .to_dict()
    )

    selected_keltner = replace(
        MINIMAL_KELTNER,
        **{
            key: selected_row[f"keltner_{key}"]
            for key in KELTNER_SPACE
        },
    )
    selected_cci = replace(
        MINIMAL_CCI,
        **{key: selected_row[f"cci_{key}"] for key in CCI_SPACE},
    )
    selected_trades, _k, _c, selected_priorities = v3.simulate_v3(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=replace(
            clean.keltner_to_base(engine, selected_keltner),
            name="BTC_1H_AR_V3M_KELTNER",
        ),
        cci=replace(
            clean.cci_to_base(engine, selected_cci), name="BTC_1H_AR_V3M_CCI"
        ),
    )
    selected_metrics = v1.metrics(engine, selected_trades)
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
            for trade in selected_trades
        ]
    ).to_csv(TRADES_CSV, index=False)

    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "base_version": "BTC-1H-Adaptive-Regime-V3",
        "observation_id": f"BTC-1H-AR-V3-MINIMAL-MICRO-TUNE-{DATE_TAG}",
        "status": "diagnostic_micro_tune_not_registered_not_live_ready",
        "surface": "v3_minimal_equivalent_19_necessary_params",
        "selection_rule": (
            "tier1: prefit annual/DD/win all strictly better than V3; "
            "tier2 (pareto): prefit annual strictly higher, DD/win not worse; "
            "both with train/validation win >= 80pct, DD < 20pct, positive; "
            "maximize prefit annual within tier; leverage frozen at V3; "
            "reused holdout not used"
        ),
        "selection_tier": selection_tier,
        "leg_variants": {
            "keltner_total": keltner_leg_total,
            "cci_total": cci_leg_total,
            "keltner_pool": len(keltner_variants),
            "cci_pool": len(cci_variants),
        },
        "grid_size": len(grid),
        "strict_gate_passes": int(strict_passed.shape[0]),
        "pareto_gate_passes": int(pareto_passed.shape[0]),
        "baseline": {
            "keltner": asdict(v3.KELTNER),
            "cci": asdict(v3.CCI),
            "metrics": baseline_metrics,
        },
        "selected": {
            "label": selected_row["label"],
            "keltner": asdict(selected_keltner),
            "cci": asdict(selected_cci),
            "metrics": selected_metrics,
            "priorities": selected_priorities,
        },
        "top_30": grid.sort_values(
            [
                "passes_strict_gate",
                "passes_pareto_gate",
                "prefit_annual_multiple",
                "prefit_max_dd",
            ],
            ascending=[False, False, False, False],
        )
        .head(30)
        .to_dict(orient="records"),
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        f"# BTC-1H-Adaptive-Regime-V3 最小表面微调 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "在 V3 参数必要性审计得到的最小等价表面（19 个必要参数，8 个非必要槽位"
            "已固定为中和值）上执行受约束微调。选参只读取 train/validation/prefit；"
            "两腿杠杆冻结为 V3 值，避免用曝光缩放伪装结构改善；reused holdout 不参与选参。"
        ),
        "",
        (
            f"腿级变体 Keltner `{keltner_leg_total}` 组、CCI `{cci_leg_total}` 组，"
            f"按腿 prefit score 截断为 `{len(keltner_variants)}`/`{len(cci_variants)}` 后"
            f"组合网格 `{len(grid)}` 组。同时满足“prefit 年化更高、回撤更小、胜率更高"
            f"（三项均严格优于 V3）且 train/validation 胜率 >=80%、回撤 <20%、同正”"
            f"的组合为 `{int(strict_passed.shape[0])}` 组；"
            f"退化为 Pareto 口径（年化严格更高、回撤与胜率不劣于 V3）的组合为 "
            f"`{int(pareto_passed.shape[0])}` 组。"
        ),
        "",
        (
            f"实际选择层级：`{selection_tier}`。首选观察 "
            f"`BTC-1H-AR-V3-MINIMAL-MICRO-TUNE-{DATE_TAG}`"
            "（未登记新版本，not live-ready）。"
        ),
        "",
        "## V3 基线 vs 最小表面微调",
        "",
        "| Window | V3 annual / return / DD / win / trades | Micro-tune annual / return / DD / win / trades |",
        "| --- | --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(
            f"| `{window}` | {metric_line(baseline_metrics[window])} | "
            f"{metric_line(selected_metrics[window])} |"
        )
    lines.extend(
        [
            "",
            "## 选中参数（最小表面，19 个必要参数）",
            "",
            "### Keltner leg",
            "",
            *[
                f"- `{key}` = `{getattr(selected_keltner, key)}`"
                + (
                    f"（V3：`{getattr(v3.KELTNER, key)}`）"
                    if getattr(selected_keltner, key) != getattr(v3.KELTNER, key)
                    and key in KELTNER_SPACE
                    else ""
                )
                for key in (
                    "indicator_window",
                    "band_k",
                    "min_adx",
                    "min_rvol",
                    "htf_mode",
                    "tp_atr",
                    "sl_atr",
                    "fixed_leverage",
                )
            ],
            "",
            "### CCI leg",
            "",
            *[
                f"- `{key}` = `{getattr(selected_cci, key)}`"
                + (
                    f"（V3：`{getattr(v3.CCI, key)}`）"
                    if getattr(selected_cci, key) != getattr(v3.CCI, key)
                    and key in CCI_SPACE
                    else ""
                )
                for key in (
                    "ema_htf",
                    "indicator_window",
                    "threshold_high",
                    "max_adx",
                    "min_rvol",
                    "min_atr_bps",
                    "max_dist_ema_bps",
                    "tp_atr",
                    "sl_atr",
                    "max_hold_bars",
                    "fixed_leverage",
                )
            ],
            "",
            "## 选择边界",
            "",
            "- 微调发生在最小等价表面上；被移除的 8 个槽位保持中和值，不参与搜索。",
            "- 杠杆冻结为 V3 值（Keltner `2.4x`、CCI `3.5x`），收益差异来自信号/出场结构而非曝光。",
            "- 本轮没有新增 forward trades，也没有 production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 或真实 stop-market 滑点证据。",
            "- 若要登记为新版本，需要另行确认；当前只是 diagnostic micro-tune observation。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{GRID_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v3_minimal_micro_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "grid_size": len(grid),
                "strict_gate_passes": int(strict_passed.shape[0]),
                "pareto_gate_passes": int(pareto_passed.shape[0]),
                "selection_tier": selection_tier,
                "selected_label": selected_row["label"],
                "baseline_prefit": baseline_metrics["prefit"],
                "selected_prefit": selected_metrics["prefit"],
                "selected_reused_holdout": selected_metrics["reused_holdout"],
                "selected_current_full": selected_metrics["current_full"],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
