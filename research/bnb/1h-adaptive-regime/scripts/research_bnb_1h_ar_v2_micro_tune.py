"""BNB-1H-Adaptive-Regime-V2 ablation-guided micro tune.

Selection discipline: legs and ensembles are scored on train/validation/
prefit only. A single preferred ensemble is chosen on prefit criteria and
only then evaluated once on the reused locked OOS window as an observation.
Nothing in this script selects on OOS results.
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
NOTES_DIR = FAMILY_DIR / "research-notes"
DATE_TAG = "2026-07-07"
LEGS_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v2_micro_tune_legs_{DATE_TAG}.csv"
ENSEMBLES_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v2_micro_tune_ensembles_{DATE_TAG}.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_ar_v2_micro_tune_{DATE_TAG}.json"
PREFERRED_TRADES_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v2_micro_tune_preferred_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"bnb-1h-ar-v2-micro-tune-{DATE_TAG}.md"

SEED = 2026070701
LEG_SAMPLES = {"ema_pullback": 2000, "wick_reject": 1600}
TOP_LEGS = 40

# Baseline prefit reference (V2): annual 2.2025x, dd -18.66%, win 87.04%.
BASE_PREFIT_ANNUAL = 2.2025453037631735
BASE_PREFIT_DD = -0.1865920870214116
BASE_PREFIT_WIN = 0.8703703703703703

EMA_GRID: dict[str, tuple[Any, ...]] = {
    "ema_fast": (34, 55),
    "ema_slow": (89, 144, 233),
    "pullback_atr": (-0.5, -0.25, 0.0),
    "max_dist_ema_bps": (200.0, 300.0, 500.0),
    "min_rvol": (0.8, 1.0, 1.25),
    "min_atr_bps": (25.0, 50.0, 75.0),
    "max_hold_bars": (120, 168, 240),
    "cooldown_bars": (0, 6, 12),
    "fixed_leverage": (1.5, 2.0, 2.5),
    "exit_variant": (
        ("fixed", 2.5, 3.0, None, None),
        ("fixed", 2.5, 4.0, None, None),
        ("fixed", 3.0, 4.0, None, None),
        ("fixed", 3.0, 5.0, None, None),
        ("fixed", 3.5, 5.0, None, None),
        ("fixed", 4.0, 5.0, None, None),
        ("trailing", 3.0, 4.0, 1.5, 1.0),
        ("trailing", 3.0, 4.0, 2.0, 1.5),
        ("trailing", 3.0, 5.0, 2.0, 1.5),
        ("trailing", 3.0, 5.0, 3.0, 1.5),
    ),
}

WICK_GRID: dict[str, tuple[Any, ...]] = {
    "threshold_low": (0.30, 0.35, 0.40),
    "threshold_high": (0.75, 0.80, 0.85),
    "band_k": (0.5, 0.75, 1.0),
    "min_adx": (16.0, 20.0, 24.0, 28.0),
    "min_rvol": (1.5, 2.0, 2.5),
    "htf_mode": ("h12", "h4"),
    "max_hold_bars": (48, 72),
    "cooldown_bars": (12, 24),
    "fixed_leverage": (0.75, 1.0),
    "exit_variant": (
        ("fixed", 0.75, 4.0, None, None),
        ("fixed", 1.0, 4.0, None, None),
        ("fixed", 1.0, 5.0, None, None),
        ("fixed", 1.5, 5.0, None, None),
        ("fixed", 1.0, 3.0, None, None),
        ("fixed", 1.5, 4.0, None, None),
    ),
}


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
    total = 1
    for key in keys:
        total *= len(grid[key])
    combos: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    if total <= count:
        for values in product(*(grid[key] for key in keys)):
            combos.append(dict(zip(keys, values)))
        return combos
    while len(combos) < count:
        values = tuple(rng.choice(grid[key]) for key in keys)
        if values in seen:
            continue
        seen.add(values)
        combos.append(dict(zip(keys, values)))
    return combos


def leg_metrics(engine: Any, trades: list[Any], split: dict[str, pd.Timestamp]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, split["train_start"], split["train_end"]),
        "validation": engine.metrics(trades, split["train_end"], split["oos_start"]),
        "prefit": engine.metrics(trades, split["train_start"], split["oos_start"]),
    }


def leg_score(bundle: dict[str, dict[str, float]]) -> float:
    train, validation, prefit = bundle["train"], bundle["validation"], bundle["prefit"]
    if train["total_return"] <= 0 or validation["total_return"] <= 0:
        return -1e9
    if prefit["trades"] < 30 or validation["trades"] < 8:
        return -1e9
    annuals = [max(train["annual_multiple"], 1e-9), max(validation["annual_multiple"], 1e-9), max(prefit["annual_multiple"], 1e-9)]
    log_ann = [math.log(min(a, 1e6)) for a in annuals]
    win_floor = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    return float(
        0.6 * log_ann[2]
        + 0.8 * min(log_ann[0], log_ann[1])
        + 1.5 * win_floor
        - 18.0 * max(0.0, -0.185 - worst_dd)
    )


def ensemble_gate(bundle: dict[str, dict[str, float]]) -> bool:
    train, validation, prefit = bundle["train"], bundle["validation"], bundle["prefit"]
    return bool(
        train["total_return"] > 0
        and validation["total_return"] > 0
        and prefit["total_return"] > 0
        and prefit["trades"] >= 70
        and validation["trades"] >= 15
        and train["max_dd"] > BASE_PREFIT_DD
        and validation["max_dd"] > BASE_PREFIT_DD
        and prefit["max_dd"] > BASE_PREFIT_DD
        and prefit["win_rate"] >= BASE_PREFIT_WIN
        and validation["win_rate"] >= 0.85
        and prefit["annual_multiple"] > BASE_PREFIT_ANNUAL
    )


def ensemble_score(bundle: dict[str, dict[str, float]]) -> float:
    prefit = bundle["prefit"]
    train, validation = bundle["train"], bundle["validation"]
    if prefit["trades"] < 70:
        return -1e9
    annuals = [max(train["annual_multiple"], 1e-9), max(validation["annual_multiple"], 1e-9), max(prefit["annual_multiple"], 1e-9)]
    log_ann = [math.log(min(a, 1e6)) for a in annuals]
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    win_floor = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    return float(
        0.8 * log_ann[2]
        + 0.7 * min(log_ann[0], log_ann[1])
        + 2.0 * win_floor
        + 3.0 * (worst_dd - BASE_PREFIT_DD)
    )


def flat(bundle: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, metrics in bundle.items()
        for key, value in metrics.items()
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

    base_ema, base_wick = v2.v2_configs(engine)
    legs: dict[str, list[tuple[Any, dict[str, dict[str, float]], float, list[Any]]]] = {}
    leg_rows: list[dict[str, Any]] = []
    for leg_name, base_cfg, grid in (
        ("ema_pullback", base_ema, EMA_GRID),
        ("wick_reject", base_wick, WICK_GRID),
    ):
        combos = sample_combos(grid, LEG_SAMPLES[leg_name], rng)
        combos.insert(0, {})  # baseline leg itself
        evaluated: list[tuple[Any, dict[str, dict[str, float]], float, list[Any]]] = []
        for index, combo in enumerate(combos):
            cfg = apply_variant(base_cfg, f"{base_cfg.name}_T{index:05d}", combo) if combo else base_cfg
            trades = v2.simulate_component(engine, frame, funding_times, funding_cumulative, cfg)
            bundle = leg_metrics(engine, trades, split)
            score = leg_score(bundle)
            if score <= -1e8:
                continue
            evaluated.append((cfg, bundle, score, trades))
            row = {"leg": leg_name, "name": cfg.name, "score": score, **flat(bundle)}
            row["config"] = json.dumps(v2.json_safe(asdict(cfg)), sort_keys=True)
            leg_rows.append(row)
        evaluated.sort(key=lambda item: item[2], reverse=True)
        legs[leg_name] = evaluated[:TOP_LEGS]
        print(
            f"{leg_name}: evaluated={len(evaluated)} kept_top={len(legs[leg_name])} "
            f"best_score={evaluated[0][2]:.3f}" if evaluated else f"{leg_name}: none",
            flush=True,
        )

    pd.DataFrame(leg_rows).sort_values("score", ascending=False).head(400).to_csv(LEGS_CSV, index=False)

    ensemble_rows: list[dict[str, Any]] = []
    candidates: list[tuple[float, bool, Any, Any, tuple[float, float], dict[str, dict[str, float]]]] = []
    for ema_cfg, ema_bundle, ema_sc, ema_trades in legs["ema_pullback"]:
        for wick_cfg, wick_bundle, wick_sc, wick_trades in legs["wick_reject"]:
            merged = engine.merge_trade_sets(ema_trades, wick_trades, ema_sc, wick_sc)
            bundle = leg_metrics(engine, merged, split)
            passed = ensemble_gate(bundle)
            score = ensemble_score(bundle)
            candidates.append((score, passed, ema_cfg, wick_cfg, (ema_sc, wick_sc), bundle))
            ensemble_rows.append(
                {
                    "ema_name": ema_cfg.name,
                    "wick_name": wick_cfg.name,
                    "gate_pass": passed,
                    "score": score,
                    **flat(bundle),
                }
            )
    ensembles_frame = pd.DataFrame(ensemble_rows).sort_values(
        ["gate_pass", "score"], ascending=False
    )
    ensembles_frame.to_csv(ENSEMBLES_CSV, index=False)

    passed = [item for item in candidates if item[1]]
    passed.sort(key=lambda item: item[0], reverse=True)
    print(f"ensembles={len(candidates)} gate_pass={len(passed)}", flush=True)

    result: dict[str, Any] = {
        "family": "BNB-1H-Adaptive-Regime",
        "base_version": "BNB-1H-Adaptive-Regime-V2",
        "date": DATE_TAG,
        "selection": "prefit_only_gate_then_score",
        "seed": SEED,
        "leg_samples": LEG_SAMPLES,
        "ensembles_evaluated": len(candidates),
        "ensembles_gate_pass": len(passed),
    }

    preferred_note_lines: list[str] = []
    if passed:
        score, _, ema_cfg, wick_cfg, priorities, bundle = passed[0]
        # Single reused-OOS unlock for the one preferred config only.
        configs = (ema_cfg, wick_cfg)
        full_trades = v2.simulate_strategy(
            engine, frame, funding_times, funding_cumulative, configs, priorities
        )
        oos_trades = v2.simulate_strategy(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            configs,
            priorities,
            start=split["oos_start"],
        )
        full_bundle = v2.metric_bundle(engine, full_trades, oos_trades, split)
        windows = v2.multiwindow_rows(engine, full_trades, oos_trades, split)
        pd.DataFrame([asdict(t) for t in full_trades]).to_csv(PREFERRED_TRADES_CSV, index=False)
        result.update(
            {
                "preferred": {
                    "name": f"V2_tune__{ema_cfg.name}__{wick_cfg.name}",
                    "score": score,
                    "priorities": priorities,
                    "configs": [asdict(ema_cfg), asdict(wick_cfg)],
                    "metrics": full_bundle,
                    "multiwindow": windows,
                },
                "status": "tuned_observation_found_reused_oos_not_promoted",
            }
        )
        preferred_note_lines = [
            f"- 首选：`{ema_cfg.name}` + `{wick_cfg.name}`（prefit-only gate + score 选出，唯一一次 reused OOS 揭盲）。",
            f"- train：{fmt(full_bundle['train'])}。",
            f"- validation：{fmt(full_bundle['validation'])}。",
            f"- prefit：{fmt(full_bundle['prefit'])}。",
            f"- reused locked OOS（观察值）：{fmt(full_bundle['holdout'])}。",
            f"- full：{fmt(full_bundle['full'])}。",
        ]
    else:
        result["status"] = "no_tuned_config_beat_v2_on_prefit_gate"
        top = ensembles_frame.head(5)
        preferred_note_lines = ["- 无组合通过 prefit gate；最接近的 5 个组合（仅 prefit 指标）："]
        for _, row in top.iterrows():
            preferred_note_lines.append(
                f"- `{row['ema_name']}`+`{row['wick_name']}`：prefit "
                f"`{row['prefit_annual_multiple']:.2f}x / {row['prefit_max_dd'] * 100:.2f}% / "
                f"{row['prefit_win_rate'] * 100:.2f}%`。"
            )

    SUMMARY_JSON.write_text(
        json.dumps(v2.json_safe(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# BNB-1H-Adaptive-Regime-V2 消融引导微调 - 2026-07-07",
        "",
        "## 结论",
        "",
        "在 V2 clean 参数上做消融引导微调。选参只使用 train/validation/prefit；locked OOS 已在 V1 搜索时揭盲，本轮对唯一首选组合复用该窗口，结果只作为观察值，不支持 promotion。",
        "",
        f"- Leg 采样：`ema_pullback` `{LEG_SAMPLES['ema_pullback']}`、`wick_reject` `{LEG_SAMPLES['wick_reject']}`；每侧取 top `{TOP_LEGS}` 组成 `{len(candidates)}` 个 ensemble。",
        f"- prefit gate（收益更高、回撤更小、胜率更高，均相对 V2 prefit `2.20x / -18.66% / 87.04%`）通过：`{len(passed)}`。",
        "",
        "## 首选结果",
        "",
    ]
    lines.extend(preferred_note_lines)
    lines.extend(
        [
            "",
            "## 口径",
            "",
            "- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`；数据与 V1/V2 冻结一致（UTC 至 `2026-07-03`），未刷新。",
            "- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 funding；杠杆硬上限 `<=3x`。",
            "- Gate：train/validation/prefit 回撤均需优于 V2 prefit DD，prefit 胜率 `>= 87.04%`，prefit 年化 `> 2.2025x`，validation trades `>= 15`。",
            "",
            "## Promotion 边界",
            "",
            "reused OOS 属于二次读取，任何微调结果都不能凭此标记 candidate/paper-live/live；如需推进，必须等新的 forward 数据形成真正未读 OOS 或走完整重新冻结流程。",
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{LEGS_CSV.relative_to(ROOT)}`",
            f"- `{ENSEMBLES_CSV.relative_to(ROOT)}`",
        ]
    )
    if passed:
        lines.append(f"- `{PREFERRED_TRADES_CSV.relative_to(ROOT)}`")
    lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(v2.json_safe({k: v for k, v in result.items() if k != "preferred"}), indent=2, ensure_ascii=False), flush=True)
    if passed:
        print(json.dumps(v2.json_safe(result["preferred"]["metrics"]), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
