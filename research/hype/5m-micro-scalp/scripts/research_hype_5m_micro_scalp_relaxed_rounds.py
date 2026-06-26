from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_micro_scalp_search import (
    ARTIFACT_ROOT,
    DIAGNOSTIC_ROOT,
    EXIT_SLIPPAGE_RATE,
    ENTRY_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    ScalpConfig,
    Trade,
    add_features,
    build_signal,
    load_hype_5m,
    metric_from_trades,
    month_slices,
    pct,
    row_for_config,
    simulate_trades,
    validation_slices,
)


SEED = 2026062602
CONFIGS_PER_ROUND = 7000
PREVIOUS_SUMMARY = ARTIFACT_ROOT / "hype_5m_micro_scalp_search_summary_2026-06-26.csv"

REPORT_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_relaxed_rounds_2026-06-26.json"
SUMMARY_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_relaxed_rounds_summary_2026-06-26.csv"
CANDIDATES_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_relaxed_rounds_candidates_2026-06-26.csv"
MONTHLY_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_relaxed_rounds_monthly_2026-06-26.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / "hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md"


@dataclass(frozen=True, slots=True)
class RoundSpec:
    name: str
    description: str
    tpd_min: float
    tpd_max: float
    min_trades: int
    min_win_rate: float
    min_pf: float
    min_ann: float
    min_max_dd: float
    min_val_pf: float
    min_fwd_pf: float
    min_fwd_trades: int
    min_recent_30d_return: float
    styles: tuple[str, ...]
    tp_values: tuple[float, ...]
    sl_values: tuple[float, ...]
    hold_values: tuple[int, ...]
    cooldown_values: tuple[int, ...]


ROUNDS: tuple[RoundSpec, ...] = (
    RoundSpec(
        name="R1_relax_frequency",
        description="只放松交易频率：从每天 3-5 笔降到每天 0.10-1.00 笔，保留正收益、较高胜率、低回撤和 VAL/FWD 要求。",
        tpd_min=0.10,
        tpd_max=1.00,
        min_trades=40,
        min_win_rate=0.55,
        min_pf=1.10,
        min_ann=1.02,
        min_max_dd=-0.18,
        min_val_pf=1.0,
        min_fwd_pf=1.0,
        min_fwd_trades=3,
        min_recent_30d_return=-0.02,
        styles=("vwap_revert", "bb_revert", "trend_rsi_snapback", "wick_reject"),
        tp_values=(50.0, 60.0, 75.0, 90.0, 120.0, 160.0, 220.0),
        sl_values=(75.0, 100.0, 130.0, 160.0, 220.0, 300.0, 400.0),
        hold_values=(12, 18, 24, 36, 48, 72, 96),
        cooldown_values=(24, 36, 48, 72, 96, 144, 192),
    ),
    RoundSpec(
        name="R2_relax_winrate_payoff",
        description="在低频基础上放松胜率，允许 45%+ 胜率，但要求 PF/payoff 更高，尝试更宽 TP 捕捉较大单笔空间。",
        tpd_min=0.10,
        tpd_max=1.50,
        min_trades=50,
        min_win_rate=0.45,
        min_pf=1.18,
        min_ann=1.05,
        min_max_dd=-0.22,
        min_val_pf=1.0,
        min_fwd_pf=1.0,
        min_fwd_trades=3,
        min_recent_30d_return=-0.03,
        styles=("vwap_revert", "bb_revert", "micro_breakout", "momentum_pause", "wick_reject", "macd_flip"),
        tp_values=(75.0, 90.0, 120.0, 160.0, 220.0, 300.0, 400.0, 550.0),
        sl_values=(50.0, 75.0, 100.0, 130.0, 160.0, 220.0, 300.0),
        hold_values=(12, 18, 24, 36, 48, 72, 96, 144),
        cooldown_values=(6, 12, 18, 24, 36, 48, 72, 96, 144),
    ),
    RoundSpec(
        name="R3_live_candidate_gate",
        description="以真实线上可跑为目标：不限高胜率和微利叙事，只要求可执行、正收益、VAL/FWD 不坏、近 30 天不明显失效。",
        tpd_min=0.05,
        tpd_max=1.25,
        min_trades=30,
        min_win_rate=0.40,
        min_pf=1.08,
        min_ann=1.02,
        min_max_dd=-0.18,
        min_val_pf=0.95,
        min_fwd_pf=0.95,
        min_fwd_trades=2,
        min_recent_30d_return=-0.02,
        styles=("vwap_revert", "bb_revert", "trend_rsi_snapback", "wick_reject", "micro_breakout", "macd_flip"),
        tp_values=(40.0, 50.0, 60.0, 75.0, 90.0, 120.0, 160.0, 220.0, 300.0, 400.0),
        sl_values=(50.0, 75.0, 100.0, 130.0, 160.0, 220.0, 300.0, 400.0),
        hold_values=(6, 9, 12, 18, 24, 36, 48, 72, 96, 144),
        cooldown_values=(6, 12, 18, 24, 36, 48, 72, 96, 144, 192),
    ),
)


def num(value: float, digits: int = 3) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def bps(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 10000:.{digits}f} bps"


def row_to_config(row: pd.Series, name: str) -> ScalpConfig:
    values: dict[str, Any] = {}
    int_fields = {"ema_fast", "ema_slow", "ema_htf", "donchian", "rsi_window", "max_hold_bars", "cooldown_bars"}
    bool_fields = {"require_trend", "require_htf", "require_macd_turn", "require_body_dir"}
    float_fields = {
        "rsi_low",
        "rsi_high",
        "bb_z",
        "vwap_dev_bps",
        "pullback_bps",
        "breakout_bps",
        "min_dir_roc_bps",
        "max_counter_roc_bps",
        "min_adx",
        "max_chop",
        "min_rvol",
        "min_atr_pct_bps",
        "max_atr_pct_bps",
        "max_dist_ema_bps",
        "wick_atr",
        "close_pos",
        "tp_bps",
        "sl_bps",
    }
    for item in fields(ScalpConfig):
        raw = row[f"cfg_{item.name}"]
        if item.name in bool_fields:
            values[item.name] = bool(raw) if isinstance(raw, bool | np.bool_) else str(raw).lower() == "true"
        elif item.name in int_fields:
            values[item.name] = int(float(raw))
        elif item.name in float_fields:
            values[item.name] = float(raw)
        else:
            values[item.name] = str(raw)
    values["name"] = name
    return ScalpConfig(**values)


def seed_configs_from_previous() -> list[ScalpConfig]:
    if not PREVIOUS_SUMMARY.exists():
        return []
    summary = pd.read_csv(PREVIOUS_SUMMARY)
    pool = pd.concat(
        [
            summary.loc[(summary["full_annualized_multiple"] > 0.95) & (summary["full_trades"] >= 30)],
            summary.loc[(summary["full_profit_factor"] > 1.0) & (summary["full_trades"] >= 30)],
            summary.loc[(summary["full_trades_per_day"].between(0.05, 1.5)) & (summary["recent_30d_total_return"] >= -0.03)],
        ],
        ignore_index=True,
    )
    if pool.empty:
        return []
    pool = pool.drop_duplicates("name").sort_values(
        ["full_annualized_multiple", "full_profit_factor", "recent_30d_total_return"],
        ascending=[False, False, False],
    )
    return [row_to_config(row, f"SEED_{idx:04d}") for idx, (_, row) in enumerate(pool.head(80).iterrows())]


def random_targeted_config(rng: random.Random, spec: RoundSpec, idx: int) -> ScalpConfig:
    ema_fast, ema_slow, ema_htf = rng.choice(
        [
            (5, 21, 96),
            (8, 34, 144),
            (9, 55, 192),
            (12, 96, 288),
            (21, 96, 384),
            (34, 144, 384),
        ]
    )
    style = rng.choice(spec.styles)
    tp_bps = rng.choice(spec.tp_values)
    sl_bps = rng.choice(spec.sl_values)
    if spec.name == "R2_relax_winrate_payoff" and tp_bps < sl_bps * 0.8:
        tp_bps = rng.choice([sl_bps * 0.9, sl_bps * 1.1, sl_bps * 1.4, sl_bps * 1.8])
    return ScalpConfig(
        name=f"{spec.name}_R{idx:05d}",
        side_mode=rng.choice(("both", "long", "short")),
        entry_style=style,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        ema_htf=ema_htf,
        donchian=rng.choice((12, 24, 48, 96)),
        rsi_window=rng.choice((7, 14, 28)),
        rsi_low=rng.choice((24.0, 28.0, 32.0, 36.0, 40.0, 44.0)),
        rsi_high=rng.choice((56.0, 60.0, 64.0, 68.0, 72.0, 76.0)),
        bb_z=rng.choice((0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5)),
        vwap_dev_bps=rng.choice((35.0, 50.0, 75.0, 100.0, 140.0, 200.0, 280.0, 380.0, 520.0)),
        pullback_bps=rng.choice((0.0, 10.0, 20.0, 35.0, 50.0, 75.0, 100.0, 140.0)),
        breakout_bps=rng.choice((0.0, 5.0, 10.0, 20.0, 35.0, 50.0)),
        min_dir_roc_bps=rng.choice((-40.0, 0.0, 20.0, 40.0, 70.0, 100.0, 150.0, 220.0, 320.0)),
        max_counter_roc_bps=rng.choice((15.0, 30.0, 50.0, 75.0, 120.0, 180.0, 260.0, 360.0)),
        min_adx=rng.choice((0.0, 10.0, 14.0, 18.0, 22.0, 28.0, 35.0)),
        max_chop=rng.choice((42.0, 48.0, 55.0, 62.0, 70.0, 80.0, 100.0)),
        min_rvol=rng.choice((0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)),
        min_atr_pct_bps=rng.choice((0.0, 12.0, 18.0, 25.0, 35.0, 50.0)),
        max_atr_pct_bps=rng.choice((70.0, 90.0, 120.0, 160.0, 220.0, 350.0, 9999.0)),
        max_dist_ema_bps=rng.choice((35.0, 60.0, 90.0, 130.0, 180.0, 260.0, 400.0, 800.0, 1200.0)),
        wick_atr=rng.choice((0.10, 0.18, 0.25, 0.35, 0.50, 0.75, 1.0, 1.4)),
        close_pos=rng.choice((0.50, 0.54, 0.58, 0.64, 0.70, 0.76, 0.82)),
        require_trend=rng.choice((False, False, True)),
        require_htf=rng.choice((False, False, True)),
        require_macd_turn=rng.choice((False, False, True)),
        require_body_dir=rng.choice((False, True)),
        tp_bps=float(tp_bps),
        sl_bps=float(sl_bps),
        max_hold_bars=int(rng.choice(spec.hold_values)),
        cooldown_bars=int(rng.choice(spec.cooldown_values)),
    )


def mutate_seed(rng: random.Random, spec: RoundSpec, seed: ScalpConfig, idx: int) -> ScalpConfig:
    return replace(
        seed,
        name=f"{spec.name}_M{idx:05d}",
        side_mode=rng.choice((seed.side_mode, seed.side_mode, "both", "long", "short")),
        entry_style=rng.choice((seed.entry_style, seed.entry_style, *spec.styles)),
        ema_fast=rng.choice((seed.ema_fast, seed.ema_fast, 5, 8, 9, 12, 21, 34)),
        ema_slow=rng.choice((seed.ema_slow, seed.ema_slow, 21, 34, 55, 96, 144, 192)),
        ema_htf=rng.choice((seed.ema_htf, seed.ema_htf, 96, 144, 192, 288, 384)),
        donchian=rng.choice((seed.donchian, seed.donchian, 12, 24, 48, 96)),
        rsi_window=rng.choice((seed.rsi_window, seed.rsi_window, 7, 14, 28)),
        rsi_low=max(18.0, seed.rsi_low + rng.choice((-8.0, -4.0, 0.0, 4.0, 8.0))),
        rsi_high=min(82.0, seed.rsi_high + rng.choice((-8.0, -4.0, 0.0, 4.0, 8.0))),
        bb_z=max(0.5, seed.bb_z + rng.choice((-0.5, -0.25, 0.0, 0.25, 0.5))),
        vwap_dev_bps=max(10.0, seed.vwap_dev_bps * rng.choice((0.65, 0.8, 1.0, 1.25, 1.6, 2.1))),
        pullback_bps=max(0.0, seed.pullback_bps + rng.choice((-30.0, -15.0, 0.0, 15.0, 30.0, 60.0))),
        breakout_bps=max(0.0, seed.breakout_bps + rng.choice((-15.0, -5.0, 0.0, 5.0, 15.0, 30.0))),
        min_dir_roc_bps=seed.min_dir_roc_bps + rng.choice((-80.0, -40.0, 0.0, 40.0, 80.0, 160.0)),
        max_counter_roc_bps=max(5.0, seed.max_counter_roc_bps + rng.choice((-80.0, -40.0, 0.0, 40.0, 80.0, 160.0))),
        min_adx=max(0.0, seed.min_adx + rng.choice((-8.0, -4.0, 0.0, 4.0, 8.0))),
        max_chop=min(100.0, max(35.0, seed.max_chop + rng.choice((-16.0, -8.0, 0.0, 8.0, 16.0)))),
        min_rvol=max(0.0, seed.min_rvol + rng.choice((-0.5, -0.25, 0.0, 0.25, 0.5))),
        min_atr_pct_bps=max(0.0, seed.min_atr_pct_bps + rng.choice((-18.0, -8.0, 0.0, 8.0, 18.0))),
        max_atr_pct_bps=max(50.0, seed.max_atr_pct_bps * rng.choice((0.7, 0.9, 1.0, 1.3, 1.8))),
        max_dist_ema_bps=max(20.0, seed.max_dist_ema_bps * rng.choice((0.6, 0.8, 1.0, 1.4, 2.0))),
        wick_atr=max(0.0, seed.wick_atr + rng.choice((-0.25, -0.1, 0.0, 0.1, 0.25, 0.5))),
        close_pos=min(0.90, max(0.45, seed.close_pos + rng.choice((-0.12, -0.06, 0.0, 0.06, 0.12)))),
        require_trend=rng.choice((seed.require_trend, seed.require_trend, False, True)),
        require_htf=rng.choice((seed.require_htf, seed.require_htf, False, True)),
        require_macd_turn=rng.choice((seed.require_macd_turn, seed.require_macd_turn, False, True)),
        require_body_dir=rng.choice((seed.require_body_dir, seed.require_body_dir, False, True)),
        tp_bps=float(rng.choice((seed.tp_bps, seed.tp_bps, *spec.tp_values))),
        sl_bps=float(rng.choice((seed.sl_bps, seed.sl_bps, *spec.sl_values))),
        max_hold_bars=int(rng.choice((seed.max_hold_bars, seed.max_hold_bars, *spec.hold_values))),
        cooldown_bars=int(rng.choice((seed.cooldown_bars, seed.cooldown_bars, *spec.cooldown_values))),
    )


def config_key(cfg: ScalpConfig) -> tuple[Any, ...]:
    data = asdict(cfg)
    data.pop("name", None)
    return tuple(data.items())


def build_round_configs(rng: random.Random, spec: RoundSpec, seeds: list[ScalpConfig]) -> list[ScalpConfig]:
    configs: list[ScalpConfig] = []
    seen: set[tuple[Any, ...]] = set()
    idx = 0
    seed_count = min(len(seeds), max(1, CONFIGS_PER_ROUND // 3))
    for seed_idx in range(seed_count):
        cfg = mutate_seed(rng, spec, seeds[seed_idx % len(seeds)], seed_idx) if seeds else random_targeted_config(rng, spec, seed_idx)
        key = config_key(cfg)
        if key not in seen:
            configs.append(cfg)
            seen.add(key)
    while len(configs) < CONFIGS_PER_ROUND:
        idx += 1
        cfg = random_targeted_config(rng, spec, idx)
        key = config_key(cfg)
        if key not in seen:
            configs.append(cfg)
            seen.add(key)
    return configs


def round_gate(row: dict[str, Any], spec: RoundSpec) -> bool:
    full_tpd = float(row["full_trades_per_day"])
    return bool(
        spec.tpd_min <= full_tpd <= spec.tpd_max
        and int(row["full_trades"]) >= spec.min_trades
        and float(row["full_annualized_multiple"]) >= spec.min_ann
        and float(row["full_win_rate"]) >= spec.min_win_rate
        and float(row["full_profit_factor"]) >= spec.min_pf
        and float(row["full_max_dd"]) >= spec.min_max_dd
        and float(row["val_2026_03_01_to_2026_06_01_profit_factor"]) >= spec.min_val_pf
        and float(row["fwd_2026_06_01_to_latest_profit_factor"]) >= spec.min_fwd_pf
        and int(row["fwd_2026_06_01_to_latest_trades"]) >= spec.min_fwd_trades
        and float(row["recent_30d_total_return"]) >= spec.min_recent_30d_return
    )


def round_score(row: dict[str, Any], spec: RoundSpec) -> float:
    full_tpd = float(row["full_trades_per_day"])
    center = (spec.tpd_min + spec.tpd_max) / 2.0
    width = max((spec.tpd_max - spec.tpd_min) / 2.0, 0.05)
    freq_fit = math.exp(-((full_tpd - center) / width) ** 2)
    ann = float(row["full_annualized_multiple"])
    pf = float(row["full_profit_factor"])
    val_pf = float(row["val_2026_03_01_to_2026_06_01_profit_factor"])
    fwd_pf = float(row["fwd_2026_06_01_to_latest_profit_factor"])
    return float(
        min(80.0, math.log(max(ann, 1e-9)) * 30.0)
        + 55.0 * min(pf if np.isfinite(pf) else 4.0, 4.0)
        + 45.0 * min(val_pf if np.isfinite(val_pf) else 4.0, 4.0)
        + 45.0 * min(fwd_pf if np.isfinite(fwd_pf) else 4.0, 4.0)
        + 40.0 * float(row["full_win_rate"])
        + 40.0 * max(float(row["full_max_dd"]), -1.0)
        + 35.0 * freq_fit
        + 10.0 * max(float(row["recent_30d_total_return"]), -0.2)
    )


def evaluate_round(frame: pd.DataFrame, spec: RoundSpec, configs: list[ScalpConfig]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[Trade]]]:
    slices = validation_slices(frame)
    rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trades_by_name: dict[str, list[Trade]] = {}
    best_name = ""
    best_score = -float("inf")
    for idx, cfg in enumerate(configs, start=1):
        row, per_slices, trades = row_for_config(frame, cfg, slices)
        row["round"] = spec.name
        row["round_description"] = spec.description
        row["round_gate"] = round_gate(row, spec)
        row["round_score"] = round_score(row, spec)
        rows.append(row)
        slice_rows.extend({"round": spec.name, **item} for item in per_slices)
        if bool(row["round_gate"]) or float(row["round_score"]) > best_score:
            trades_by_name[str(row["name"])] = trades
        if float(row["round_score"]) > best_score:
            best_score = float(row["round_score"])
            best_name = str(row["name"])
        if idx % 500 == 0:
            print(
                f"{spec.name} progress={idx}/{len(configs)} "
                f"best={best_name} score={best_score:.2f}"
            )
    return rows, slice_rows, trades_by_name


def monthly_for_names(frame: pd.DataFrame, configs: dict[str, ScalpConfig], names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name in names:
        cfg = configs[name]
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


def candidate_table(summary: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    candidates = summary.loc[summary["round_gate"].eq(True)].copy()
    if candidates.empty:
        return candidates
    monthly_agg = (
        monthly.assign(negative_month=lambda frame: frame["total_return"] < 0)
        .groupby("name")
        .agg(
            months=("month", "count"),
            negative_months=("negative_month", "sum"),
            worst_month_return=("total_return", "min"),
            median_month_return=("total_return", "median"),
            worst_month_pf=("profit_factor", "min"),
        )
        .reset_index()
    )
    candidates = candidates.merge(monthly_agg, on="name", how="left")
    candidates["live_candidate_pass"] = (
        candidates["negative_months"].le(7)
        & candidates["worst_month_return"].ge(-0.12)
        & candidates["full_max_dd"].ge(-0.18)
        & candidates["val_2026_03_01_to_2026_06_01_profit_factor"].ge(1.0)
        & candidates["fwd_2026_06_01_to_latest_profit_factor"].ge(1.0)
        & candidates["recent_30d_total_return"].ge(-0.02)
    )
    return candidates.sort_values(["live_candidate_pass", "round_score"], ascending=[False, False])


def table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    output = [
        "| round | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{item['round']}` | `{item['name']}` | `{item['cfg_entry_style']}` | `{item['cfg_side_mode']}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{pct(float(item['full_win_rate']))}` | "
            f"`{num(float(item['full_profit_factor']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | "
            f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | "
            f"`{pct(float(item['recent_30d_total_return']))}` |"
        )
    return output


def render_markdown(summary: pd.DataFrame, candidates: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any]) -> str:
    lines = [
        "# HYPE 5m Micro-Scalp relaxed rounds 2026-06-26",
        "",
        "Family id: `HYPE-5M-Micro-Scalp`",
        "",
        "目标：按用户要求逐步放松单个约束，寻找能够盈利且真实线上可跑的 Binance HYPEUSDT `5m` 策略候选。",
        "",
        "## 固定不放松的部分",
        "",
        "- 数据质量仍使用完整 Binance HYPEUSDT 永续 `5m` normalized OHLCV。",
        "- 信号仍只使用已收盘 K，下一根 open 入场。",
        "- 入场后仍立即有固定 TP/SL bracket。",
        "- 同 K 同时触及 TP/SL 仍按止损先成交。",
        "- stop/target 被 open 穿越仍按 open 市价成交。",
        "- timeout 仍按下一根 open 退出。",
        f"- 成本仍扣 observed live cost：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## 数据质量",
        "",
        f"- 覆盖：`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        f"- 缺口：`{quality['missing_bars']}`；重复：`{quality['duplicate_ts']}`；OHLC/VWAP/volume 硬违规：`{quality['ohlcv_violations']}`。",
        "",
        "## 分轮结果",
        "",
    ]
    for spec in ROUNDS:
        sub = summary.loc[summary["round"].eq(spec.name)].sort_values("round_score", ascending=False)
        passed = sub.loc[sub["round_gate"].eq(True)].sort_values("round_score", ascending=False)
        lines.extend(
            [
                f"### {spec.name}",
                "",
                spec.description,
                "",
                f"- 搜索配置数：`{len(sub)}`。",
                f"- round gate 通过数：`{len(passed)}`。",
                "",
            ]
        )
        if passed.empty:
            lines.append("没有配置通过本轮 gate。最接近的配置：")
            lines.extend(table(sub, limit=8))
        else:
            lines.append("本轮 gate 通过配置：")
            lines.extend(table(passed, limit=12))
        lines.append("")
    lines.extend(["## 候选月度审计", ""])
    if candidates.empty:
        lines.append("没有任何 round-gate 候选，因此没有 live-candidate 晋级项。")
    else:
        live = candidates.loc[candidates["live_candidate_pass"].eq(True)]
        lines.append(f"- round-gate 候选数：`{len(candidates)}`。")
        lines.append(f"- live-candidate 初筛通过数：`{len(live)}`。")
        lines.append("")
        lines.extend(table(candidates, limit=16))
        if not live.empty:
            lines.extend(["", "### Live-Candidate 初筛", ""])
            for row in live.head(8).to_dict(orient="records"):
                lines.append(
                    f"- `{row['name']}`：ann `{mult(float(row['full_annualized_multiple']))}`，"
                    f"PF `{num(float(row['full_profit_factor']))}`，maxDD `{pct(float(row['full_max_dd']))}`，"
                    f"负收益月份 `{int(row['negative_months'])}/{int(row['months'])}`，"
                    f"最差月 `{pct(float(row['worst_month_return']))}`。"
                )
    lines.extend(
        [
            "",
            "## 结论",
            "",
        ]
    )
    if candidates.empty:
        lines.append("本轮三种放松方式仍没有得到可提升候选。")
    else:
        live = candidates.loc[candidates["live_candidate_pass"].eq(True)]
        if live.empty:
            lines.append("有 round-gate 通过项，但月度稳定性或近期表现仍不足，暂不提升 live/paper-live。")
        else:
            lines.append("出现可进入下一步 paper audit / live-spec 草案的初筛候选；仍需参数邻域、逐笔路径图、订单维护与重启恢复审计后才能真实资金运行。")
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_PATH}`",
            f"- 全量 summary：`{SUMMARY_PATH}`",
            f"- 候选表：`{CANDIDATES_PATH}`",
            f"- 月度审计：`{MONTHLY_PATH}`",
        ]
    )
    _ = monthly
    return "\n".join(lines) + "\n"


def main() -> None:
    rng = random.Random(SEED)
    raw, quality = load_hype_5m()
    frame = add_features(raw)
    seeds = seed_configs_from_previous()
    print(f"seed_configs={len(seeds)}")

    all_rows: list[dict[str, Any]] = []
    all_slices: list[dict[str, Any]] = []
    all_configs: dict[str, ScalpConfig] = {}
    for spec in ROUNDS:
        configs = build_round_configs(rng, spec, seeds)
        for cfg in configs:
            all_configs[cfg.name] = cfg
        rows, slice_rows, _ = evaluate_round(frame, spec, configs)
        all_rows.extend(rows)
        all_slices.extend(slice_rows)
        passed = sum(1 for row in rows if row["round_gate"])
        best = max(rows, key=lambda row: float(row["round_score"]))
        print(
            f"{spec.name} done configs={len(rows)} pass={passed} "
            f"best={best['name']} ann={best['full_annualized_multiple']:.3f} "
            f"pf={best['full_profit_factor']:.3f} tpd={best['full_trades_per_day']:.3f}"
        )

    summary = pd.DataFrame(all_rows).sort_values("round_score", ascending=False)
    gate_names = summary.loc[summary["round_gate"].eq(True), "name"].drop_duplicates().tolist()
    top_names = summary.head(80)["name"].drop_duplicates().tolist()
    monthly_names = list(dict.fromkeys([*gate_names, *top_names]))
    monthly = monthly_for_names(frame, all_configs, monthly_names)
    candidates = candidate_table(summary, monthly)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    candidates.to_csv(CANDIDATES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, candidates, monthly, quality), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "seed": SEED,
                "configs_per_round": CONFIGS_PER_ROUND,
                "data_quality": quality,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "rounds": [asdict(item) for item in ROUNDS],
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "candidates": str(CANDIDATES_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "round_gate_count": int(summary["round_gate"].sum()),
                "live_candidate_count": int(candidates["live_candidate_pass"].sum()) if not candidates.empty else 0,
                "top": summary.head(50).to_dict(orient="records"),
                "candidates": candidates.head(50).to_dict(orient="records") if not candidates.empty else [],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"candidates={CANDIDATES_PATH}")
    print(f"monthly={MONTHLY_PATH}")
    print(f"round_gate={int(summary['round_gate'].sum())} live_candidate={int(candidates['live_candidate_pass'].sum()) if not candidates.empty else 0}")
    print(summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
