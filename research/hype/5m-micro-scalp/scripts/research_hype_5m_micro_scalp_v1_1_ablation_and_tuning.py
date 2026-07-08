from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from research_hype_5m_micro_scalp_search import (
    ARTIFACT_ROOT,
    EXIT_SLIPPAGE_RATE,
    ENTRY_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    ScalpConfig,
    add_features,
    bps,
    build_signal,
    load_hype_5m,
    metric_from_trades,
    month_slices,
    mult,
    pct,
    row_for_config,
    simulate_trades,
    validation_slices,
)
from research_hype_5m_micro_scalp_v1_simplified_combo_search import verify_raw_normalized_parity


RUN_ID = "2026-06-30"
FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
ABLATION_ROOT = FAMILY_ROOT / "ablations"
CANONICAL_ROOT = FAMILY_ROOT / "specs"
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "research-notes"

BASELINE_CONFIG_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_baseline_config_{RUN_ID}.json"
ABLATION_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_full_ablation_summary_{RUN_ID}.csv"
ABLATION_MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_full_ablation_monthly_{RUN_ID}.csv"
ABLATION_REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_full_ablation_{RUN_ID}.json"
ABLATION_MARKDOWN_PATH = ABLATION_ROOT / f"hype-5m-micro-scalp-v1-1-full-parameter-ablation-{RUN_ID}.md"

TUNE_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_micro_tune_summary_{RUN_ID}.csv"
TUNE_MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_micro_tune_monthly_{RUN_ID}.csv"
TUNE_PREFERRED_TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_micro_tune_preferred_trades_{RUN_ID}.csv"
TUNE_REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_1_micro_tune_{RUN_ID}.json"
TUNE_MARKDOWN_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-1-micro-tune-{RUN_ID}.md"

SPEC_MARKDOWN_PATH = CANONICAL_ROOT / "hype-5m-micro-scalp-v1-1-baseline-spec.md"

ACTIVE_EFFECTIVE_FIELDS = [
    "side_mode",
    "ema_fast",
    "ema_slow",
    "ema_htf",
    "vwap_dev_bps",
    "min_adx",
    "max_chop",
    "min_rvol",
    "min_atr_pct_bps",
    "max_atr_pct_bps",
    "max_dist_ema_bps",
    "close_pos",
    "require_htf",
    "require_macd_turn",
    "require_body_dir",
    "tp_bps",
    "sl_bps",
    "max_hold_bars",
    "cooldown_bars",
]

DORMANT_UNDER_VWAP_REVERT = [
    "donchian",
    "rsi_window",
    "rsi_low",
    "rsi_high",
    "bb_z",
    "pullback_bps",
    "breakout_bps",
    "min_dir_roc_bps",
    "max_counter_roc_bps",
    "wick_atr",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HYPE-5M-Micro-Scalp-V1.1 full ablation and micro tuning.")
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--max-grid-configs", type=int, default=22000)
    parser.add_argument("--max-random-configs", type=int, default=22000)
    parser.add_argument("--top-keep", type=int, default=160)
    parser.add_argument("--progress-every", type=int, default=5000)
    parser.add_argument("--skip-raw-parity", action="store_true")
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--skip-tuning", action="store_true")
    return parser.parse_args()


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def v1_1_config(name: str = "HYPE-5M-Micro-Scalp-V1.1") -> ScalpConfig:
    return ScalpConfig(
        name=name,
        side_mode="both",
        entry_style="vwap_revert",
        ema_fast=21,
        ema_slow=192,
        ema_htf=384,
        donchian=96,
        rsi_window=7,
        rsi_low=40.0,
        rsi_high=76.0,
        bb_z=1.75,
        vwap_dev_bps=65.0,
        pullback_bps=100.0,
        breakout_bps=10.0,
        min_dir_roc_bps=70.0,
        max_counter_roc_bps=260.0,
        min_adx=10.0,
        max_chop=62.0,
        min_rvol=1.0,
        min_atr_pct_bps=35.0,
        max_atr_pct_bps=350.0,
        max_dist_ema_bps=130.0,
        wick_atr=1.4,
        close_pos=0.76,
        require_trend=True,
        require_htf=True,
        require_macd_turn=True,
        require_body_dir=True,
        tp_bps=90.0,
        sl_bps=500.0,
        max_hold_bars=96,
        cooldown_bars=48,
    )


def config_key(cfg: ScalpConfig) -> tuple[tuple[str, Any], ...]:
    data = asdict(cfg)
    data.pop("name", None)
    return tuple(data.items())


def ablation_values(base: ScalpConfig) -> dict[str, list[Any]]:
    return {
        "side_mode": ["both", "long", "short"],
        "entry_style": [
            "vwap_revert",
            "bb_revert",
            "trend_rsi_snapback",
            "wick_reject",
            "micro_breakout",
            "macd_flip",
            "ema_reclaim",
            "momentum_pause",
        ],
        "ema_fast": [8, 12, 21, 34],
        "ema_slow": [96, 144, 192, 288],
        "ema_htf": [192, 288, 384],
        "donchian": [24, 48, 96],
        "rsi_window": [7, 14, 28],
        "rsi_low": [32.0, 36.0, 40.0, 44.0],
        "rsi_high": [64.0, 68.0, 72.0, 76.0],
        "bb_z": [1.25, 1.5, 1.75, 2.0, 2.5],
        "vwap_dev_bps": [50.0, 60.0, 65.0, 75.0, 90.0, 120.0, 140.0],
        "pullback_bps": [0.0, 50.0, 100.0, 140.0],
        "breakout_bps": [0.0, 5.0, 10.0, 20.0, 35.0],
        "min_dir_roc_bps": [0.0, 40.0, 70.0, 100.0, 150.0],
        "max_counter_roc_bps": [120.0, 180.0, 260.0, 360.0],
        "min_adx": [0.0, 10.0, 14.0, 18.0, 22.0],
        "max_chop": [42.0, 48.0, 55.0, 62.0, 70.0, 100.0],
        "min_rvol": [0.5, 0.75, 1.0, 1.25, 1.5],
        "min_atr_pct_bps": [0.0, 18.0, 25.0, 35.0, 50.0],
        "max_atr_pct_bps": [140.0, 220.0, 350.0, 9999.0],
        "max_dist_ema_bps": [90.0, 130.0, 180.0, 260.0, 400.0, 9999.0],
        "wick_atr": [0.75, 1.0, 1.4],
        "close_pos": [0.58, 0.64, 0.70, 0.76, 0.82],
        "require_trend": [False, True],
        "require_htf": [False, True],
        "require_macd_turn": [False, True],
        "require_body_dir": [False, True],
        "tp_bps": [67.5, 75.0, 90.0, 110.0, 130.0],
        "sl_bps": [300.0, 400.0, 500.0, 650.0],
        "max_hold_bars": [48, 72, 96, 144, 192],
        "cooldown_bars": [0, 24, 36, 48, 72, 96],
    }


def ablation_matrix(base: ScalpConfig) -> list[ScalpConfig]:
    configs = [base]
    seen = {config_key(base)}
    for param, values in ablation_values(base).items():
        base_value = getattr(base, param)
        for value in values:
            if value == base_value:
                continue
            cfg = replace(base, name=f"V1.1__{param}__{value}", **{param: value})
            if cfg.ema_fast >= cfg.ema_slow:
                continue
            key = config_key(cfg)
            if key in seen:
                continue
            seen.add(key)
            configs.append(cfg)
    return configs


def add_changed_columns(row: dict[str, Any], cfg: ScalpConfig, base: ScalpConfig) -> dict[str, Any]:
    if cfg.name == base.name:
        row["changed_param"] = "BASELINE"
        row["changed_value"] = ""
        row["is_baseline"] = True
        return row
    for key, value in asdict(cfg).items():
        if key == "name":
            continue
        if value != getattr(base, key):
            row["changed_param"] = key
            row["changed_value"] = str(value)
            row["is_baseline"] = False
            return row
    raise RuntimeError(f"could not identify changed param for {cfg.name}")


def add_metric_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary.loc[summary["is_baseline"].eq(True)].iloc[0]
    result = summary.copy()
    for metric in (
        "signals",
        "full_trades",
        "full_trades_per_day",
        "full_annualized_multiple",
        "full_profit_factor",
        "full_win_rate",
        "full_avg_trade",
        "full_max_dd",
        "recent_30d_total_return",
        "val_2026_03_01_to_2026_06_01_profit_factor",
        "fwd_2026_06_01_to_latest_profit_factor",
    ):
        result[f"delta_{metric}"] = result[metric] - base[metric]
    numeric_checks = [
        "signals",
        "full_trades",
        "full_annualized_multiple",
        "full_profit_factor",
        "full_win_rate",
        "full_avg_trade",
        "full_max_dd",
        "recent_30d_total_return",
    ]
    delta_frame = result[[f"delta_{metric}" for metric in numeric_checks]].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    result["identical_to_baseline"] = delta_frame.abs().max(axis=1) <= 1e-12
    return result


def add_search_flags(row: dict[str, Any], baseline_row: dict[str, Any]) -> dict[str, Any]:
    full_ann = float(row["full_annualized_multiple"])
    full_pf = float(row["full_profit_factor"])
    full_win = float(row["full_win_rate"])
    full_dd = float(row["full_max_dd"])
    full_trades = int(row["full_trades"])
    val_pf = float(row["val_2026_03_01_to_2026_06_01_profit_factor"])
    fwd_pf = float(row["fwd_2026_06_01_to_latest_profit_factor"])
    recent30 = float(row["recent_30d_total_return"])
    avg_trade = float(row["full_avg_trade"])
    base_ann = float(baseline_row["full_annualized_multiple"])
    base_dd = float(baseline_row["full_max_dd"])
    base_pf = float(baseline_row["full_profit_factor"])
    base_win = float(baseline_row["full_win_rate"])
    row["delta_vs_v1_1_ann"] = full_ann - base_ann
    row["delta_vs_v1_1_max_dd"] = full_dd - base_dd
    row["delta_vs_v1_1_pf"] = full_pf - base_pf
    row["delta_vs_v1_1_win"] = full_win - base_win
    row["sample_ok"] = bool(full_trades >= 120 and int(row["val_2026_03_01_to_2026_06_01_trades"]) >= 12 and int(row["fwd_2026_06_01_to_latest_trades"]) >= 5)
    row["split_ok"] = bool(val_pf >= 1.0 and fwd_pf >= 1.0 and recent30 >= 0.0)
    row["win_suitable"] = bool(0.65 <= full_win <= 0.92)
    row["strict_improve_gate"] = bool(
        row["sample_ok"]
        and row["split_ok"]
        and row["win_suitable"]
        and full_ann > base_ann
        and full_dd > base_dd
        and full_pf >= max(1.50, base_pf * 0.85)
        and avg_trade > 0.0
    )
    row["balanced_gate"] = bool(
        row["sample_ok"]
        and row["split_ok"]
        and row["win_suitable"]
        and full_ann >= 1.50
        and full_pf >= 1.50
        and full_dd >= -0.10
        and avg_trade > 0.0
    )
    safe_pf = min(full_pf if np.isfinite(full_pf) else 5.0, 5.0)
    row["balanced_score"] = float(
        90.0 * math.log(max(full_ann, 1e-9))
        + 30.0 * safe_pf
        + 45.0 * full_win
        + 260.0 * max(full_dd, -0.5)
        + 18.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 18.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        + 160.0 * recent30
        + min(full_trades, 260) / 10.0
        - (0.0 if row["sample_ok"] else 28.0)
        - (0.0 if row["win_suitable"] else 18.0)
    )
    row["return_score"] = float(
        140.0 * math.log(max(full_ann, 1e-9))
        + 22.0 * safe_pf
        + 180.0 * max(full_dd, -0.5)
        + 14.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 14.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        + 130.0 * recent30
        - (0.0 if full_trades >= 120 else 35.0)
    )
    row["low_dd_score"] = float(
        520.0 * full_dd
        + 35.0 * safe_pf
        + 60.0 * math.log(max(full_ann, 1e-9))
        + 12.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 12.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        + min(full_trades, 260) / 12.0
    )
    return row


def monthly_for_configs(frame: pd.DataFrame, cfg_by_name: dict[str, ScalpConfig], names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name in names:
        cfg = cfg_by_name[name]
        trades, _ = simulate_trades(frame, build_signal(frame, cfg), cfg)
        for item in months:
            rows.append(
                {
                    "name": name,
                    "month": item["name"],
                    "month_start": item["start"],
                    "month_end": item["end"],
                    **metric_from_trades(trades, start=item["start"], end=item["end"]),
                }
            )
    return pd.DataFrame(rows)


def trades_to_frame(trades: list[Any]) -> pd.DataFrame:
    return pd.DataFrame([{**asdict(trade), "side_label": "long" if trade.side > 0 else "short"} for trade in trades])


def tune_grid_configs(base: ScalpConfig, max_grid: int, rng: random.Random) -> Iterable[ScalpConfig]:
    grid = list(
        product(
            [(21, 192, 384), (21, 144, 384), (34, 192, 384), (21, 192, 192)],
            [55.0, 65.0, 75.0, 90.0],
            [0.70, 0.76, 0.82],
            [90.0, 130.0, 180.0],
            [75.0, 90.0, 110.0, 130.0],
            [400.0, 500.0, 650.0],
            [72, 96, 144],
            [24, 48, 72],
            [0.75, 1.0, 1.25],
            [0.0, 10.0, 18.0],
            [55.0, 62.0, 70.0],
            [220.0, 350.0, 9999.0],
        )
    )
    rng.shuffle(grid)
    for idx, (
        ema_tuple,
        vwap_dev_bps,
        close_pos,
        max_dist_ema_bps,
        tp_bps,
        sl_bps,
        max_hold_bars,
        cooldown_bars,
        min_rvol,
        min_adx,
        max_chop,
        max_atr_pct_bps,
    ) in enumerate(grid[:max_grid], start=1):
        ema_fast, ema_slow, ema_htf = ema_tuple
        yield replace(
            base,
            name=f"V1.1_tune_grid_{idx:06d}",
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            ema_htf=ema_htf,
            vwap_dev_bps=vwap_dev_bps,
            close_pos=close_pos,
            max_dist_ema_bps=max_dist_ema_bps,
            tp_bps=tp_bps,
            sl_bps=sl_bps,
            max_hold_bars=max_hold_bars,
            cooldown_bars=cooldown_bars,
            min_rvol=min_rvol,
            min_adx=min_adx,
            max_chop=max_chop,
            max_atr_pct_bps=max_atr_pct_bps,
        )


def tune_random_config(base: ScalpConfig, rng: random.Random, idx: int) -> ScalpConfig:
    ema_fast, ema_slow, ema_htf = rng.choice(
        [
            (21, 192, 384),
            (21, 144, 384),
            (34, 192, 384),
            (21, 192, 192),
            (12, 192, 384),
            (34, 288, 384),
        ]
    )
    return replace(
        base,
        name=f"V1.1_tune_rand_{idx:06d}",
        side_mode=rng.choice(["both", "both", "both", "long", "short"]),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        ema_htf=ema_htf,
        vwap_dev_bps=rng.choice([45.0, 55.0, 60.0, 65.0, 75.0, 85.0, 100.0]),
        min_adx=rng.choice([0.0, 10.0, 14.0, 18.0, 22.0]),
        max_chop=rng.choice([48.0, 55.0, 62.0, 70.0, 100.0]),
        min_rvol=rng.choice([0.5, 0.75, 1.0, 1.25, 1.5]),
        min_atr_pct_bps=rng.choice([18.0, 25.0, 35.0, 50.0]),
        max_atr_pct_bps=rng.choice([140.0, 220.0, 350.0, 9999.0]),
        max_dist_ema_bps=rng.choice([90.0, 130.0, 180.0, 260.0, 400.0]),
        close_pos=rng.choice([0.64, 0.70, 0.76, 0.82]),
        require_htf=rng.choice([False, True, True]),
        require_macd_turn=rng.choice([False, True, True]),
        require_body_dir=rng.choice([False, True, True]),
        tp_bps=rng.choice([67.5, 75.0, 90.0, 110.0, 130.0, 150.0]),
        sl_bps=rng.choice([300.0, 400.0, 500.0, 650.0, 800.0]),
        max_hold_bars=rng.choice([48, 72, 96, 144, 192]),
        cooldown_bars=rng.choice([0, 24, 36, 48, 72, 96]),
    )


def build_tune_configs(base: ScalpConfig, max_grid: int, max_random: int, seed: int) -> list[ScalpConfig]:
    rng = random.Random(seed)
    configs = [base]
    configs.extend(tune_grid_configs(base, max_grid, rng))
    for idx in range(max_random):
        configs.append(tune_random_config(base, rng, idx))
    deduped: list[ScalpConfig] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for cfg in configs:
        if cfg.ema_fast >= cfg.ema_slow:
            continue
        key = config_key(cfg)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cfg)
    return deduped


def strict_table(rows: pd.DataFrame, baseline: pd.Series, limit: int = 12) -> list[str]:
    output = [
        "| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        changed = []
        if item.get("changed_param") not in (None, "BASELINE"):
            changed.append(f"{item.get('changed_param')}={item.get('changed_value')}")
        for field in ACTIVE_EFFECTIVE_FIELDS:
            key = f"cfg_{field}"
            if str(item.get(key)) != str(baseline.get(key)):
                label = f"{field}={item.get(key)}"
                if label not in changed:
                    changed.append(label)
        output.append(
            f"| `{item['name']}` | `{'; '.join(changed) if changed else 'same as V1.1'}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{num(float(item['full_profit_factor']))}` | "
            f"`{pct(float(item['full_win_rate']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | `{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | `{pct(float(item['recent_30d_total_return']))}` |"
        )
    return output


def render_ablation_markdown(summary: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any], raw_parity: dict[str, Any] | None) -> str:
    base = summary.loc[summary["is_baseline"].eq(True)].iloc[0]
    variants = summary.loc[summary["is_baseline"].eq(False)].copy()
    grouped = (
        variants.groupby("changed_param")
        .agg(
            variants=("name", "count"),
            identical=("identical_to_baseline", "sum"),
            best_ann=("full_annualized_multiple", "max"),
            best_pf=("full_profit_factor", "max"),
            best_dd=("full_max_dd", "max"),
            worst_ann=("full_annualized_multiple", "min"),
        )
        .reset_index()
        .sort_values(["identical", "best_ann"], ascending=[False, False])
    )
    ineffective = grouped.loc[grouped["identical"].eq(grouped["variants"]), "changed_param"].tolist()
    active_top = variants.loc[~variants["identical_to_baseline"].eq(True)].sort_values("full_annualized_multiple", ascending=False).head(15)
    fragile = variants.loc[~variants["identical_to_baseline"].eq(True)].sort_values("full_annualized_multiple", ascending=True).head(12)

    lines = [
        "# HYPE-5M-Micro-Scalp-V1.1 全参数消融 2026-06-30",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "本报告将 `V1S_rand_016782__N00596` 正式记录为 `HYPE-5M-Micro-Scalp-V1.1` 后，对 `ScalpConfig` 的全部字段做 one-at-a-time 消融。状态仍为 `paper-audit observation / not live-ready`。",
        "",
        "## 数据与执行",
        "",
        f"- 数据：Binance HYPEUSDT perpetual `5m`，`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        f"- 缺口 `{quality['missing_bars']}`；OHLC/VWAP/volume 硬违规：`{quality['ohlcv_violations']}`。",
        f"- raw/normalized 对齐：`{raw_parity if raw_parity is not None else 'skipped'}`。",
        "- 信号闭合 K，下一根 open 入场；入场即固定 TP/SL bracket；同 K 同时触及按 stop-first；timeout 下一根 open。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## V1.1 基线",
        "",
        f"- trades `{int(base['full_trades'])}`，trades/day `{float(base['full_trades_per_day']):.2f}`，ann `{mult(float(base['full_annualized_multiple']))}`。",
        f"- win `{pct(float(base['full_win_rate']))}`，PF `{num(float(base['full_profit_factor']))}`，avg `{bps(float(base['full_avg_trade']))}`，maxDD `{pct(float(base['full_max_dd']))}`。",
        f"- VAL PF `{num(float(base['val_2026_03_01_to_2026_06_01_profit_factor']))}`，FWD PF `{num(float(base['fwd_2026_06_01_to_latest_profit_factor']))}`，recent30 `{pct(float(base['recent_30d_total_return']))}`。",
        "",
        "## 无效或 dormant 参数",
        "",
        f"- 完全无影响参数组：`{', '.join(ineffective) if ineffective else 'none'}`。",
        "- 解释：V1.1 固定 `entry_style=vwap_revert`，所以上述 RSI/Bollinger/Donchian/wick/pullback/breakout/momentum-pause 相关字段不参与当前信号；它们只有切换入场风格后才有效。",
        "",
        "## 参数组摘要",
        "",
        "| parameter | variants | identical | best ann | best PF | best DD | worst ann |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in grouped.to_dict(orient="records"):
        lines.append(
            f"| `{row['changed_param']}` | `{int(row['variants'])}` | `{int(row['identical'])}` | "
            f"`{mult(float(row['best_ann']))}` | `{num(float(row['best_pf']))}` | `{pct(float(row['best_dd']))}` | `{mult(float(row['worst_ann']))}` |"
        )
    lines.extend(["", "## Top One-At-A-Time Variants", "", *strict_table(active_top, base, 15)])
    lines.extend(["", "## Fragile One-At-A-Time Variants", "", *strict_table(fragile, base, 12)])
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- V1.1 的有效核心是 `vwap_revert + require_trend=true + EMA21/192/384 + HTF/MACD/body filters + 65 bps VWAP deviation + TP/SL 90/500 bps`。",
            "- 当前消融可直接确认一批 dormant 字段；后续调参应集中在 EMA slow/HTF、VWAP 偏离、ADX/chop/rvol/ATR、EMA 距离、close position、HTF/MACD/body、TP/SL、hold/cooldown。",
            "- 本报告只说明参数敏感性，不构成 live-ready 证明。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_1_ablation_and_tuning.py`",
            f"- Summary CSV：`{ABLATION_SUMMARY_PATH}`",
            f"- Monthly CSV：`{ABLATION_MONTHLY_PATH}`",
            f"- JSON：`{ABLATION_REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_tune_markdown(summary: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any], preferred: pd.Series) -> str:
    base = summary.loc[summary["name"].eq("HYPE-5M-Micro-Scalp-V1.1")].iloc[0]
    candidates = summary.loc[~summary["name"].eq("HYPE-5M-Micro-Scalp-V1.1")].copy()
    strict = candidates.loc[candidates["strict_improve_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    balanced = candidates.loc[candidates["balanced_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    top_return = candidates.loc[candidates["sample_ok"].eq(True)].sort_values("return_score", ascending=False).head(15)
    top_low_dd = candidates.loc[
        (candidates["sample_ok"].eq(True))
        & (candidates["full_annualized_multiple"] >= 1.30)
        & (candidates["full_profit_factor"] >= 1.30)
    ].sort_values("low_dd_score", ascending=False).head(15)
    preferred_monthly = monthly.loc[monthly["name"].eq(preferred["name"])]
    neg_months = int((preferred_monthly["total_return"] < 0).sum()) if not preferred_monthly.empty else 0
    worst_month = preferred_monthly.sort_values("total_return").head(1).to_dict(orient="records") if not preferred_monthly.empty else []
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.1 微调搜索 2026-06-30",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "本报告基于 V1.1 全参数消融暴露出的有效字段做组合微调，目标是寻找更高收益、更低回撤、胜率不过度极端的后续观察版本。",
        "",
        "## 搜索规模",
        "",
        f"- configs evaluated：`{len(summary)}`。",
        "- 微调只围绕有效参数：EMA、VWAP deviation、ADX/chop/rvol/ATR、EMA distance、close position、HTF/MACD/body、TP/SL、hold/cooldown。",
        "",
        "## V1.1 基线",
        "",
        f"- trades `{int(base['full_trades'])}`，trades/day `{float(base['full_trades_per_day']):.2f}`，ann `{mult(float(base['full_annualized_multiple']))}`。",
        f"- win `{pct(float(base['full_win_rate']))}`，PF `{num(float(base['full_profit_factor']))}`，avg `{bps(float(base['full_avg_trade']))}`，maxDD `{pct(float(base['full_max_dd']))}`。",
        f"- VAL PF `{num(float(base['val_2026_03_01_to_2026_06_01_profit_factor']))}`，FWD PF `{num(float(base['fwd_2026_06_01_to_latest_profit_factor']))}`，recent30 `{pct(float(base['recent_30d_total_return']))}`。",
        "",
        "## 微调结果",
        "",
        f"- strict improve gate：`{int(candidates['strict_improve_gate'].sum())}` / `{len(candidates)}`。",
        f"- balanced gate：`{int(candidates['balanced_gate'].sum())}` / `{len(candidates)}`。",
        "",
        "### 严格优于 V1.1 的候选",
        "",
    ]
    lines.extend(strict_table(strict, base, 15) if not strict.empty else ["没有配置同时超过 V1.1 年化与回撤。"])
    lines.extend(["", "### 均衡候选", ""])
    lines.extend(strict_table(balanced, base, 15) if not balanced.empty else ["没有配置通过 balanced gate。"])
    lines.extend(["", "### 高收益排序", "", *strict_table(top_return, base, 15)])
    lines.extend(["", "### 低回撤排序", "", *strict_table(top_low_dd, base, 15)])
    lines.extend(["", "## 推荐观察行", ""])
    lines.append(
        f"- `{preferred['name']}`：ann `{mult(float(preferred['full_annualized_multiple']))}`，PF `{num(float(preferred['full_profit_factor']))}`，win `{pct(float(preferred['full_win_rate']))}`，avg `{bps(float(preferred['full_avg_trade']))}`，maxDD `{pct(float(preferred['full_max_dd']))}`，VAL PF `{num(float(preferred['val_2026_03_01_to_2026_06_01_profit_factor']))}`，FWD PF `{num(float(preferred['fwd_2026_06_01_to_latest_profit_factor']))}`，recent30 `{pct(float(preferred['recent_30d_total_return']))}`，负收益月份 `{neg_months}`。"
    )
    if worst_month:
        item = worst_month[0]
        lines.append(
            f"- 最差月份 `{item['month']}`：return `{pct(float(item['total_return']))}`，PF `{num(float(item['profit_factor']))}`，trades `{int(item['trades'])}`。"
        )
    lines.extend(["", "推荐行参数：", "", "| field | value |", "| --- | --- |"])
    for field in ACTIVE_EFFECTIVE_FIELDS:
        lines.append(f"| `{field}` | `{preferred[f'cfg_{field}']}` |")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 微调阶段可以找到更激进的收益版本，但如果回撤、分段样本或胜率范围不过关，不应替代 V1.1。",
            "- 推荐观察行仍然只是 paper-audit observation；进入 live/paper-live/handoff 前必须补逐笔路径、订单维护、重启恢复和 paper/live reconciliation。",
            "",
            "## 产物",
            "",
            f"- Summary CSV：`{TUNE_SUMMARY_PATH}`",
            f"- Monthly CSV：`{TUNE_MONTHLY_PATH}`",
            f"- Preferred trades CSV：`{TUNE_PREFERRED_TRADES_PATH}`",
            f"- JSON：`{TUNE_REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run_ablation(frame: pd.DataFrame, quality: dict[str, Any], raw_parity: dict[str, Any] | None) -> pd.DataFrame:
    base = v1_1_config()
    configs = ablation_matrix(base)
    slices = validation_slices(frame)
    rows: list[dict[str, Any]] = []
    config_by_name: dict[str, ScalpConfig] = {}
    for cfg in configs:
        row, _, _ = row_for_config(frame, cfg, slices)
        rows.append(add_changed_columns(row, cfg, base))
        config_by_name[cfg.name] = cfg
        print(f"ablation done {cfg.name}", flush=True)
    summary = add_metric_deltas(pd.DataFrame(rows)).sort_values(["is_baseline", "full_annualized_multiple"], ascending=[False, False])
    monthly = monthly_for_configs(frame, config_by_name, list(config_by_name))
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(ABLATION_SUMMARY_PATH, index=False)
    monthly.to_csv(ABLATION_MONTHLY_PATH, index=False)
    ABLATION_MARKDOWN_PATH.write_text(render_ablation_markdown(summary, monthly, quality, raw_parity), encoding="utf-8")
    ABLATION_REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1.1",
                "source_candidate": "V1S_rand_016782__N00596",
                "data_quality": quality,
                "raw_normalized_parity": raw_parity,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "configs": int(len(summary)),
                "baseline": summary.loc[summary["is_baseline"].eq(True)].to_dict(orient="records"),
                "identical_parameter_groups": summary.loc[summary["identical_to_baseline"].eq(True), "changed_param"].drop_duplicates().tolist(),
                "top": summary.loc[~summary["is_baseline"].eq(True)]
                .sort_values("full_annualized_multiple", ascending=False)
                .head(30)
                .to_dict(orient="records"),
                "outputs": {
                    "markdown": str(ABLATION_MARKDOWN_PATH),
                    "summary": str(ABLATION_SUMMARY_PATH),
                    "monthly": str(ABLATION_MONTHLY_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return summary


def select_preferred_tune(summary: pd.DataFrame) -> pd.Series:
    candidates = summary.loc[~summary["name"].eq("HYPE-5M-Micro-Scalp-V1.1")].copy()
    strict = candidates.loc[candidates["strict_improve_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    if not strict.empty:
        return strict.iloc[0]
    balanced = candidates.loc[candidates["balanced_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    if not balanced.empty:
        return balanced.iloc[0]
    return candidates.sort_values("balanced_score", ascending=False).iloc[0]


def run_tuning(frame: pd.DataFrame, quality: dict[str, Any], args: argparse.Namespace) -> pd.DataFrame:
    base = v1_1_config()
    slices = validation_slices(frame)
    configs = build_tune_configs(base, args.max_grid_configs, args.max_random_configs, args.seed)
    cfg_by_name = {cfg.name: cfg for cfg in configs}
    baseline_row, _, _ = row_for_config(frame, base, slices)
    rows: list[dict[str, Any]] = []
    for idx, cfg in enumerate(configs, start=1):
        row, _, _ = row_for_config(frame, cfg, slices)
        row = add_search_flags(row, baseline_row)
        rows.append(row)
        if args.progress_every and idx % args.progress_every == 0:
            print(
                f"tune progress={idx}/{len(configs)} ann={row['full_annualized_multiple']:.2f} "
                f"pf={row['full_profit_factor']:.3f} dd={row['full_max_dd']:.3f}",
                flush=True,
            )
    summary = pd.DataFrame(rows).sort_values("balanced_score", ascending=False)
    preferred = select_preferred_tune(summary)
    top_names = list(
        dict.fromkeys(
            summary.loc[summary["strict_improve_gate"].eq(True)].sort_values("balanced_score", ascending=False).head(args.top_keep)["name"].tolist()
            + summary.loc[summary["balanced_gate"].eq(True)].sort_values("balanced_score", ascending=False).head(args.top_keep)["name"].tolist()
            + [str(preferred["name"]), "HYPE-5M-Micro-Scalp-V1.1"]
        )
    )
    monthly = monthly_for_configs(frame, cfg_by_name, top_names[: args.top_keep + 5])
    preferred_cfg = cfg_by_name[str(preferred["name"])]
    preferred_trades, _ = simulate_trades(frame, build_signal(frame, preferred_cfg), preferred_cfg)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(TUNE_SUMMARY_PATH, index=False)
    monthly.to_csv(TUNE_MONTHLY_PATH, index=False)
    trades_to_frame(preferred_trades).to_csv(TUNE_PREFERRED_TRADES_PATH, index=False)
    TUNE_MARKDOWN_PATH.write_text(render_tune_markdown(summary, monthly, quality, preferred), encoding="utf-8")
    TUNE_REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1.1",
                "script": "research_hype_5m_micro_scalp_v1_1_ablation_and_tuning.py",
                "seed": args.seed,
                "configs": int(len(summary)),
                "preferred": preferred.to_dict(),
                "strict_improve_count": int(summary["strict_improve_gate"].sum()),
                "balanced_gate_count": int(summary["balanced_gate"].sum()),
                "outputs": {
                    "markdown": str(TUNE_MARKDOWN_PATH),
                    "summary": str(TUNE_SUMMARY_PATH),
                    "monthly": str(TUNE_MONTHLY_PATH),
                    "preferred_trades": str(TUNE_PREFERRED_TRADES_PATH),
                },
                "top_strict": summary.loc[summary["strict_improve_gate"].eq(True)]
                .sort_values("balanced_score", ascending=False)
                .head(30)
                .to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return summary


def write_baseline_config() -> None:
    base = v1_1_config()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    BASELINE_CONFIG_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1.1",
                "source_candidate": "V1S_rand_016782__N00596",
                "status": "paper-audit observation / not live-ready",
                "baseline_config": asdict(base),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    write_baseline_config()
    frame_raw, quality = load_hype_5m()
    raw_parity = None if args.skip_raw_parity else verify_raw_normalized_parity(frame_raw)
    frame = add_features(frame_raw)
    if not args.skip_ablation:
        run_ablation(frame, quality, raw_parity)
    if not args.skip_tuning:
        run_tuning(frame, quality, args)
    print(f"baseline_config={BASELINE_CONFIG_PATH}")
    if not args.skip_ablation:
        print(f"ablation_markdown={ABLATION_MARKDOWN_PATH}")
        print(f"ablation_summary={ABLATION_SUMMARY_PATH}")
    if not args.skip_tuning:
        print(f"tune_markdown={TUNE_MARKDOWN_PATH}")
        print(f"tune_summary={TUNE_SUMMARY_PATH}")
        print(f"tune_preferred_trades={TUNE_PREFERRED_TRADES_PATH}")


if __name__ == "__main__":
    main()
