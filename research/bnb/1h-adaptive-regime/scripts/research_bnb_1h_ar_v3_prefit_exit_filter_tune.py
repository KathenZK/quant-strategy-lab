"""BNB-1H-Adaptive-Regime-V3 prefit-only exit/filter diagnostics.

This script deliberately does not score, report, or persist reused locked-OOS
metrics. It searches around V3's exit/trailing and filter strength only on
train/validation/prefit. Any candidate with a prefit entry whose exit would
cross into the locked OOS window is rejected from selection.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_v2() -> Any:
    spec = importlib.util.spec_from_file_location("bnb_1h_ar_v2", SCRIPT_DIR / "bnb_1h_ar_v2.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load bnb_1h_ar_v2.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v2 = load_v2()

FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-10"

LEGS_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v3_prefit_exit_filter_tune_legs_{DATE_TAG}.csv"
ENSEMBLES_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v3_prefit_exit_filter_tune_ensembles_{DATE_TAG}.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_ar_v3_prefit_exit_filter_tune_{DATE_TAG}.json"
REPORT_MD = NOTES_DIR / f"bnb-1h-ar-v3-prefit-exit-filter-optimization-{DATE_TAG}.md"

SEED = 2026071001
LEG_SAMPLES = {"ema_pullback": 6000, "wick_reject": 6000}
TOP_LEGS = 60
MAX_EXPOSURE = 2.5

# V3 prefit reference.
V3_PREFIT_ANNUAL = 3.3672197013915555
V3_PREFIT_DD = -0.18235391961740977
V3_PREFIT_WIN = 0.8942307692307693
V3_PREFIT_TRADES = 104

EMA_EXIT_VARIANTS: tuple[tuple[Any, ...], ...] = (
    ("fixed", 2.5, 4.0, None, None),
    ("fixed", 3.0, 4.0, None, None),
    ("fixed", 3.0, 5.0, None, None),
    ("fixed", 3.5, 5.0, None, None),
    ("fixed", 4.0, 5.0, None, None),
    ("trailing", 3.0, 4.0, 1.25, 1.0),
    ("trailing", 3.0, 4.0, 1.5, 1.0),
    ("trailing", 3.0, 5.0, 1.5, 1.25),
    ("trailing", 3.0, 5.0, 2.0, 1.25),
    ("trailing", 3.0, 5.0, 2.0, 1.5),
    ("trailing", 3.0, 5.0, 2.5, 1.5),
    ("trailing", 3.0, 5.0, 3.0, 1.5),
    ("trailing", 3.0, 6.0, 2.0, 1.5),
)

WICK_EXIT_VARIANTS: tuple[tuple[Any, ...], ...] = (
    ("fixed", 0.75, 3.0, None, None),
    ("fixed", 0.75, 4.0, None, None),
    ("fixed", 1.0, 3.0, None, None),
    ("fixed", 1.0, 4.0, None, None),
    ("fixed", 1.0, 5.0, None, None),
    ("fixed", 1.25, 4.0, None, None),
    ("fixed", 1.25, 5.0, None, None),
    ("fixed", 1.5, 4.0, None, None),
    ("fixed", 1.5, 5.0, None, None),
    ("fixed", 2.0, 5.0, None, None),
)

EMA_GRID: dict[str, tuple[Any, ...]] = {
    "ema_fast": (34, 55, 89),
    "ema_slow": (89, 144, 233),
    "pullback_atr": (-0.5, -0.25, 0.0),
    "max_dist_ema_bps": (200.0, 300.0, 500.0),
    "min_rvol": (0.8, 1.0, 1.25),
    "min_atr_bps": (25.0, 50.0, 75.0, 100.0),
    "max_hold_bars": (120, 168, 240, 336),
    "cooldown_bars": (0, 6, 12, 24),
    "fixed_leverage": (2.0, 2.5),
    "exit_variant": EMA_EXIT_VARIANTS,
}

WICK_GRID: dict[str, tuple[Any, ...]] = {
    "threshold_low": (0.30, 0.35, 0.40, 0.45),
    "threshold_high": (0.70, 0.75, 0.80, 0.85),
    "band_k": (0.4, 0.5, 0.75, 1.0),
    "min_adx": (20.0, 24.0, 28.0, 32.0, 36.0),
    "min_rvol": (1.5, 2.0, 2.5, 3.0),
    "htf_mode": ("h4", "h12"),
    "max_hold_bars": (24, 48, 72),
    "cooldown_bars": (12, 24, 36),
    "fixed_leverage": (0.75, 1.0, 1.25),
    "exit_variant": WICK_EXIT_VARIANTS,
}


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2f}x"


def fmt(metric: dict[str, float]) -> str:
    return (
        f"`{mult(metric['annual_multiple'])}` / `{pct(metric['total_return'])}` / "
        f"`{pct(metric['max_dd'])}` / `{pct(metric['win_rate'])}` / `{int(metric['trades'])}`"
    )


def apply_variant(base_cfg: Any, name: str, combo: dict[str, Any]) -> Any:
    updates: dict[str, Any] = {"name": name}
    for key, value in combo.items():
        if key == "exit_variant":
            exit_kind, tp, sl, activation, trail = value
            updates["exit_kind"] = exit_kind
            updates["tp_atr"] = tp
            updates["sl_atr"] = sl
            if exit_kind == "trailing":
                updates["trail_activation_atr"] = activation
                updates["trail_atr"] = trail
            else:
                updates["trail_activation_atr"] = 100_000.0
                updates["trail_atr"] = 100_000.0
        else:
            updates[key] = value
    return replace(base_cfg, **updates)


def sample_combos(grid: dict[str, tuple[Any, ...]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    keys = list(grid.keys())
    total = math.prod(len(grid[key]) for key in keys)
    if total <= count:
        return [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]

    combos: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    while len(combos) < count:
        values = tuple(rng.choice(grid[key]) for key in keys)
        if values in seen:
            continue
        seen.add(values)
        combos.append(dict(zip(keys, values)))
    return combos


def prefit_bundle(engine: Any, trades: list[Any], split: dict[str, pd.Timestamp]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, split["train_start"], split["train_end"]),
        "validation": engine.metrics(trades, split["train_end"], split["oos_start"]),
        "prefit": engine.metrics(trades, split["train_start"], split["oos_start"]),
    }


def flat(bundle: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, metrics in bundle.items()
        for key, value in metrics.items()
    }


def boundary_cross_count(trades: list[Any], split: dict[str, pd.Timestamp]) -> int:
    return sum(
        split["train_start"] <= trade.entry_ts < split["oos_start"] <= trade.exit_ts
        for trade in trades
    )


def leg_score(bundle: dict[str, dict[str, float]]) -> float:
    train, validation, prefit = bundle["train"], bundle["validation"], bundle["prefit"]
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        return -1e9
    if prefit["trades"] < 25 or validation["trades"] < 8:
        return -1e9
    if prefit["max_exposure"] > MAX_EXPOSURE:
        return -1e9
    annuals = [max(train["annual_multiple"], 1e-9), max(validation["annual_multiple"], 1e-9), max(prefit["annual_multiple"], 1e-9)]
    log_ann = [math.log(min(item, 1e6)) for item in annuals]
    win_floor = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    dd_penalty = 18.0 * max(0.0, -0.20 - worst_dd)
    trade_bonus = min(prefit["trades"] / 120.0, 1.0) * 0.25
    return float(0.75 * log_ann[2] + 0.85 * min(log_ann[0], log_ann[1]) + 1.6 * win_floor + trade_bonus - dd_penalty)


def ensemble_gate(bundle: dict[str, dict[str, float]]) -> bool:
    train, validation, prefit = bundle["train"], bundle["validation"], bundle["prefit"]
    return bool(
        train["total_return"] > 0
        and validation["total_return"] > 0
        and prefit["total_return"] > 0
        and prefit["trades"] >= 70
        and validation["trades"] >= 15
        and train["max_dd"] > -0.20
        and validation["max_dd"] > -0.20
        and prefit["max_dd"] > -0.20
        and validation["win_rate"] >= 0.80
        and prefit["win_rate"] >= 0.80
        and prefit["max_exposure"] <= MAX_EXPOSURE
    )


def ensemble_score(bundle: dict[str, dict[str, float]]) -> float:
    train, validation, prefit = bundle["train"], bundle["validation"], bundle["prefit"]
    if not ensemble_gate(bundle):
        return -1e9
    annuals = [max(train["annual_multiple"], 1e-9), max(validation["annual_multiple"], 1e-9), max(prefit["annual_multiple"], 1e-9)]
    log_ann = [math.log(min(item, 1e6)) for item in annuals]
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    win_floor = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    trade_bonus = min(prefit["trades"] / 120.0, 1.0) * 0.2
    return float(0.95 * log_ann[2] + 0.9 * min(log_ann[0], log_ann[1]) + 1.5 * win_floor + trade_bonus + 2.0 * (worst_dd + 0.20))


def v3_configs(engine: Any) -> tuple[Any, Any]:
    base_ema, base_wick = v2.v2_configs(engine)
    ema = replace(
        base_ema,
        name="BNB_1H_AR_V3_EMA_PULLBACK",
        ema_slow=144,
        exit_kind="trailing",
        trail_activation_atr=2.0,
        trail_atr=1.5,
        max_hold_bars=240,
        cooldown_bars=12,
        fixed_leverage=2.5,
    )
    wick = replace(
        base_wick,
        name="BNB_1H_AR_V3_WICK_REJECT",
        threshold_low=0.40,
        threshold_high=0.75,
        min_adx=28.0,
        max_hold_bars=48,
        fixed_leverage=1.0,
    )
    return ema, wick


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    ctx = v2.load_context()
    engine = ctx["engine"]
    frame = ctx["frame"]
    funding_times = ctx["funding_times"]
    funding_cumulative = ctx["funding_cumulative"]
    split = ctx["split"]
    rng = random.Random(SEED)

    v3_ema, v3_wick = v3_configs(engine)
    grids = (
        ("ema_pullback", v3_ema, EMA_GRID),
        ("wick_reject", v3_wick, WICK_GRID),
    )

    legs: dict[str, list[tuple[Any, dict[str, dict[str, float]], float, list[Any]]]] = {}
    leg_rows: list[dict[str, Any]] = []
    rejected_cross = {"ema_pullback": 0, "wick_reject": 0, "ensemble": 0}

    for leg_name, base_cfg, grid in grids:
        combos = sample_combos(grid, LEG_SAMPLES[leg_name], rng)
        combos.insert(0, {})
        evaluated: list[tuple[Any, dict[str, dict[str, float]], float, list[Any]]] = []
        for index, combo in enumerate(combos):
            cfg = apply_variant(base_cfg, f"{base_cfg.name}_EF{index:05d}", combo) if combo else base_cfg
            trades = v2.simulate_component(engine, frame, funding_times, funding_cumulative, cfg)
            cross_count = boundary_cross_count(trades, split)
            if cross_count:
                rejected_cross[leg_name] += 1
                continue
            bundle = prefit_bundle(engine, trades, split)
            score = leg_score(bundle)
            if score <= -1e8:
                continue
            evaluated.append((cfg, bundle, score, trades))
            leg_rows.append(
                {
                    "leg": leg_name,
                    "name": cfg.name,
                    "score": score,
                    "boundary_cross_count": cross_count,
                    **flat(bundle),
                    "config": json.dumps(v2.json_safe(asdict(cfg)), ensure_ascii=False, sort_keys=True),
                }
            )
        evaluated.sort(key=lambda item: item[2], reverse=True)
        legs[leg_name] = evaluated[:TOP_LEGS]
        print(
            f"{leg_name}: evaluated={len(evaluated)} kept_top={len(legs[leg_name])} "
            f"rejected_cross={rejected_cross[leg_name]}",
            flush=True,
        )

    pd.DataFrame(leg_rows).sort_values("score", ascending=False).head(600).to_csv(LEGS_CSV, index=False)

    ensemble_rows: list[dict[str, Any]] = []
    candidates: list[tuple[float, Any, Any, tuple[float, float], dict[str, dict[str, float]]]] = []
    for ema_cfg, _ema_bundle, ema_score, ema_trades in legs["ema_pullback"]:
        for wick_cfg, _wick_bundle, wick_score, wick_trades in legs["wick_reject"]:
            merged = engine.merge_trade_sets(ema_trades, wick_trades, ema_score, wick_score)
            cross_count = boundary_cross_count(merged, split)
            if cross_count:
                rejected_cross["ensemble"] += 1
                continue
            bundle = prefit_bundle(engine, merged, split)
            passed = ensemble_gate(bundle)
            score = ensemble_score(bundle)
            ensemble_rows.append(
                {
                    "ema_name": ema_cfg.name,
                    "wick_name": wick_cfg.name,
                    "gate_pass": passed,
                    "score": score,
                    "boundary_cross_count": cross_count,
                    **flat(bundle),
                }
            )
            if passed:
                candidates.append((score, ema_cfg, wick_cfg, (ema_score, wick_score), bundle))

    ensembles = pd.DataFrame(ensemble_rows).sort_values(["gate_pass", "score"], ascending=False)
    ensembles.to_csv(ENSEMBLES_CSV, index=False)
    candidates.sort(key=lambda item: item[0], reverse=True)

    result: dict[str, Any] = {
        "family": "BNB-1H-Adaptive-Regime",
        "base_version": "BNB-1H-Adaptive-Regime-V3",
        "date": DATE_TAG,
        "selection": "prefit_only_exit_filter_surface_no_oos_metrics",
        "seed": SEED,
        "max_exposure": MAX_EXPOSURE,
        "leg_samples": LEG_SAMPLES,
        "top_legs": TOP_LEGS,
        "ensembles_evaluated": int(len(ensemble_rows)),
        "ensembles_gate_pass": int(len(candidates)),
        "rejected_boundary_cross": rejected_cross,
        "v3_reference": {
            "prefit_annual_multiple": V3_PREFIT_ANNUAL,
            "prefit_max_dd": V3_PREFIT_DD,
            "prefit_win_rate": V3_PREFIT_WIN,
            "prefit_trades": V3_PREFIT_TRADES,
        },
    }

    lines = [
        "# BNB-1H-Adaptive-Regime-V3 prefit-only exit/filter 优化诊断 - 2026-07-10",
        "",
        "## 结论",
        "",
        "本次只研究 V3 附近的 exit/trailing 与过滤强度，不读取、不排序、不报告 reused locked OOS 指标；任何 prefit 入场但出场跨入 OOS 的候选都从选择集中剔除。",
        "",
        f"- Leg 采样：`ema_pullback` `{LEG_SAMPLES['ema_pullback']}`、`wick_reject` `{LEG_SAMPLES['wick_reject']}`；每侧 top `{TOP_LEGS}` 组成 ensemble surface。",
        f"- 最大暴露约束：`<= {MAX_EXPOSURE:.1f}x`，避免用简单加杠杆掩盖结构问题。",
        f"- 因 prefit/OOS 边界跨越被剔除：`ema_pullback` `{rejected_cross['ema_pullback']}`，`wick_reject` `{rejected_cross['wick_reject']}`，ensemble `{rejected_cross['ensemble']}`。",
        "",
    ]

    if candidates:
        best_score, best_ema, best_wick, priorities, best_bundle = candidates[0]
        result["preferred_prefit_only"] = {
            "name": f"V3_EF__{best_ema.name}__{best_wick.name}",
            "score": best_score,
            "priorities": priorities,
            "configs": [asdict(best_ema), asdict(best_wick)],
            "metrics": best_bundle,
            "status": "prefit_only_diagnostic_not_version_not_promoted",
        }
        delta_ann = best_bundle["prefit"]["annual_multiple"] - V3_PREFIT_ANNUAL
        delta_dd = best_bundle["prefit"]["max_dd"] - V3_PREFIT_DD
        delta_win = best_bundle["prefit"]["win_rate"] - V3_PREFIT_WIN
        lines.extend(
            [
                "## Prefit-only 首选观察值",
                "",
                f"- 首选：`{best_ema.name}` + `{best_wick.name}`。",
                f"- train：{fmt(best_bundle['train'])}。",
                f"- validation：{fmt(best_bundle['validation'])}。",
                f"- prefit：{fmt(best_bundle['prefit'])}。",
                f"- 相对 V3 prefit：annual `{delta_ann:+.2f}x`，DD `{delta_dd * 100:+.2f} pct`，win `{delta_win * 100:+.2f} pct`，trades `{int(best_bundle['prefit']['trades'] - V3_PREFIT_TRADES):+d}`。",
                "- 该结果只是下一轮 forward/re-freeze 的候选设计，不登记为 V4，不可 promotion。",
                "",
                "## 参数变化",
                "",
                "相对 V3：",
            ]
        )
        base_ema, base_wick = v3_configs(engine)
        for label, base_cfg, tuned_cfg in (
            ("ema_pullback", base_ema, best_ema),
            ("wick_reject", base_wick, best_wick),
        ):
            changes = []
            for key in asdict(base_cfg):
                old = getattr(base_cfg, key)
                new = getattr(tuned_cfg, key)
                if key != "name" and old != new:
                    changes.append(f"`{key}` `{old}` -> `{new}`")
            lines.append(f"- `{label}`：" + ("；".join(changes) if changes else "无变化") + "。")
        lines.append("")
    else:
        result["status"] = "no_prefit_only_candidate_found"
        lines.extend(
            [
                "## Prefit-only 首选观察值",
                "",
                "- 无候选通过 gate；不建议继续在 V3 附近做同类参数搜索。",
                "",
            ]
        )

    lines.extend(
        [
            "## 口径",
            "",
            "- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`。",
            "- 数据：沿用 V1/V2/V3 冻结数据；本诊断的排序窗口只到 `oos_start` 前。",
            "- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 funding。",
            "- Gate：train/validation/prefit 均为正收益；prefit trades `>=70`、validation trades `>=15`；三段 max DD 均需 `>-20%`；validation/prefit win 均需 `>=80%`；max exposure `<=2.5x`。",
            "",
            "## Promotion 边界",
            "",
            "本报告不含 reused locked OOS 指标，因此不能声称优于 V3 的 OOS 表现。若要把某个观察值登记为新版本，必须先决定是否重开冻结流程或等待新的未读 forward 数据。",
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{LEGS_CSV.relative_to(ROOT)}`",
            f"- `{ENSEMBLES_CSV.relative_to(ROOT)}`",
            "",
        ]
    )

    SUMMARY_JSON.write_text(json.dumps(v2.json_safe(result), indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            v2.json_safe(
                {
                    "ensembles_evaluated": len(ensemble_rows),
                    "ensembles_gate_pass": len(candidates),
                    "rejected_boundary_cross": rejected_cross,
                    "preferred_prefit_only": result.get("preferred_prefit_only", {}),
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
