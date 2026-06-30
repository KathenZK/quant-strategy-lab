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
    RAW_ROOT,
    SYMBOL_FILE,
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
from research_hype_5m_micro_scalp_v1_full_ablation import baseline_config


RUN_ID = "2026-06-30"
FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "research-notes"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_combo_summary_{RUN_ID}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_combo_monthly_{RUN_ID}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_combo_top_trades_{RUN_ID}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_combo_{RUN_ID}.json"
MARKDOWN_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-simplified-combo-search-{RUN_ID}.md"

TRAIN_END = pd.Timestamp("2026-03-01T00:00:00Z")
VAL_END = pd.Timestamp("2026-06-01T00:00:00Z")

SIMPLIFIED_ACTIVE_FIELDS = [
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

FIXED_DORMANT_FIELDS = {
    "entry_style": "vwap_revert",
    "donchian": 96,
    "rsi_window": 7,
    "rsi_low": 40.0,
    "rsi_high": 76.0,
    "bb_z": 1.75,
    "pullback_bps": 100.0,
    "breakout_bps": 10.0,
    "min_dir_roc_bps": 70.0,
    "max_counter_roc_bps": 260.0,
    "wick_atr": 1.4,
    "require_trend": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simplified combo search around HYPE-5M-Micro-Scalp-V1 effective parameters."
    )
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--max-random-configs", type=int, default=40000)
    parser.add_argument("--max-core-configs", type=int, default=24000)
    parser.add_argument("--top-keep", type=int, default=120)
    parser.add_argument("--progress-every", type=int, default=5000)
    parser.add_argument(
        "--skip-raw-parity",
        action="store_true",
        help="Skip normalized/raw equality check. Use only for quick local debugging.",
    )
    return parser.parse_args()


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def config_key(cfg: ScalpConfig) -> tuple[tuple[str, Any], ...]:
    data = asdict(cfg)
    data.pop("name", None)
    return tuple(data.items())


def simplified_replace(base: ScalpConfig, *, name: str, **kwargs: Any) -> ScalpConfig:
    values = {**FIXED_DORMANT_FIELDS, **kwargs}
    return replace(base, name=name, **values)


def verify_raw_normalized_parity(normalized: pd.DataFrame) -> dict[str, Any]:
    raw_files = sorted(RAW_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not raw_files:
        raise FileNotFoundError(f"no raw HYPE 5m parquet files under {RAW_ROOT}")
    raw = pd.concat([pd.read_parquet(path) for path in raw_files], ignore_index=True)
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    raw = raw.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    norm = normalized.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap", "is_closed"]
    merged = norm[["ts", *columns]].merge(
        raw[["ts", *columns]],
        on="ts",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    if not (merged["_merge"] == "both").all():
        counts = {str(key): int(value) for key, value in merged["_merge"].value_counts().to_dict().items()}
        raise RuntimeError(f"raw/normalized timestamp mismatch: {counts}")
    mismatches: dict[str, int] = {}
    max_abs_diff: dict[str, float] = {}
    for column in columns:
        left = merged[f"{column}_normalized"]
        right = merged[f"{column}_raw"]
        if column == "is_closed":
            neq = left.astype(bool) != right.astype(bool)
            diff = 0.0
        else:
            diff_series = (left.astype(float) - right.astype(float)).abs()
            neq = diff_series > 1e-12
            diff = float(diff_series.max())
        mismatches[column] = int(neq.sum())
        max_abs_diff[column] = diff
    if any(mismatches.values()):
        raise RuntimeError(f"raw/normalized field mismatch: {mismatches}")
    return {
        "raw_files": int(len(raw_files)),
        "normalized_rows": int(len(norm)),
        "raw_rows": int(len(raw)),
        "merged_rows": int(len(merged)),
        "timestamp_mismatch": 0,
        "field_mismatches": mismatches,
        "max_abs_diff": max_abs_diff,
    }


def core_grid_configs(base: ScalpConfig) -> Iterable[ScalpConfig]:
    idx = 0
    for (
        vwap_dev_bps,
        close_pos,
        max_dist_ema_bps,
        tp_bps,
        sl_bps,
        max_hold_bars,
        cooldown_bars,
        min_adx,
        max_atr_pct_bps,
    ) in product(
        [60.0, 75.0, 90.0, 120.0],
        [0.58, 0.64, 0.70, 0.76],
        [130.0, 180.0, 260.0],
        [55.0, 67.5, 75.0, 90.0],
        [220.0, 300.0, 400.0, 500.0],
        [36, 48, 72, 96],
        [0, 24, 36, 48],
        [0.0, 14.0, 18.0],
        [220.0, 9999.0],
    ):
        idx += 1
        yield simplified_replace(
            base,
            name=f"V1S_core_{idx:06d}",
            vwap_dev_bps=vwap_dev_bps,
            close_pos=close_pos,
            max_dist_ema_bps=max_dist_ema_bps,
            tp_bps=tp_bps,
            sl_bps=sl_bps,
            max_hold_bars=max_hold_bars,
            cooldown_bars=cooldown_bars,
            min_adx=min_adx,
            max_atr_pct_bps=max_atr_pct_bps,
        )


def seeded_edge_configs(base: ScalpConfig) -> Iterable[ScalpConfig]:
    seeds: list[dict[str, Any]] = [
        {},
        {"sl_bps": 400.0},
        {"max_dist_ema_bps": 130.0},
        {"max_hold_bars": 36},
        {"max_atr_pct_bps": 220.0},
        {"min_adx": 18.0},
        {"min_adx": 0.0, "max_dist_ema_bps": 130.0},
        {"sl_bps": 400.0, "max_dist_ema_bps": 130.0},
        {"sl_bps": 400.0, "max_hold_bars": 36},
        {"max_dist_ema_bps": 130.0, "max_hold_bars": 36, "max_atr_pct_bps": 220.0},
        {"require_macd_turn": True},
        {"require_htf": True, "ema_htf": 192},
        {"require_body_dir": False},
        {"cooldown_bars": 0},
        {"close_pos": 0.58},
        {"max_chop": 100.0},
        {"max_dist_ema_bps": 9999.0},
    ]
    for idx, params in enumerate(seeds, start=1):
        yield simplified_replace(base, name=f"V1S_seed_{idx:04d}", **params)


def random_combo_config(base: ScalpConfig, rng: random.Random, idx: int) -> ScalpConfig:
    ema_fast, ema_slow, ema_htf = rng.choice(
        [
            (12, 96, 384),
            (21, 96, 384),
            (21, 96, 192),
            (21, 144, 384),
            (34, 144, 384),
            (8, 55, 192),
        ]
    )
    return simplified_replace(
        base,
        name=f"V1S_rand_{idx:06d}",
        side_mode=rng.choice(["both", "both", "both", "long", "short"]),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        ema_htf=ema_htf,
        vwap_dev_bps=rng.choice([50.0, 60.0, 65.0, 75.0, 85.0, 100.0, 120.0, 140.0]),
        min_adx=rng.choice([0.0, 10.0, 14.0, 18.0, 22.0]),
        max_chop=rng.choice([42.0, 48.0, 55.0, 62.0, 70.0, 100.0]),
        min_rvol=rng.choice([0.0, 0.5, 0.75, 1.0, 1.25]),
        min_atr_pct_bps=rng.choice([0.0, 18.0, 25.0, 35.0, 50.0]),
        max_atr_pct_bps=rng.choice([140.0, 160.0, 220.0, 350.0, 9999.0]),
        max_dist_ema_bps=rng.choice([90.0, 130.0, 160.0, 180.0, 220.0, 260.0, 400.0, 9999.0]),
        close_pos=rng.choice([0.55, 0.58, 0.64, 0.70, 0.76]),
        require_htf=rng.choice([False, False, True]),
        require_macd_turn=rng.choice([False, False, True]),
        require_body_dir=rng.choice([False, True, True]),
        tp_bps=rng.choice([45.0, 55.0, 60.0, 67.5, 75.0, 90.0, 110.0, 130.0]),
        sl_bps=rng.choice([160.0, 220.0, 275.0, 300.0, 350.0, 400.0, 500.0, 650.0]),
        max_hold_bars=rng.choice([24, 36, 48, 72, 96, 144, 192]),
        cooldown_bars=rng.choice([0, 12, 24, 36, 48, 72, 96]),
    )


def build_configs(max_random: int, seed: int, max_core: int) -> list[ScalpConfig]:
    base = simplified_replace(baseline_config(), name="HYPE-5M-Micro-Scalp-V1-simplified")
    configs = [base]
    configs.extend(seeded_edge_configs(base))
    rng = random.Random(seed)
    core_configs = list(core_grid_configs(base))
    rng.shuffle(core_configs)
    if max_core >= 0:
        core_configs = core_configs[:max_core]
    configs.extend(core_configs)
    for idx in range(max_random):
        configs.append(random_combo_config(base, rng, idx))
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


def negative_month_count(trades: list[Any], frame: pd.DataFrame) -> tuple[int, str, float]:
    rows = []
    for item in month_slices(frame):
        metrics = metric_from_trades(trades, start=item["start"], end=item["end"])
        rows.append({"month": item["name"], **metrics})
    monthly = pd.DataFrame(rows)
    if monthly.empty:
        return 0, "", 0.0
    negative = int((monthly["total_return"] < 0).sum())
    worst = monthly.sort_values("total_return").iloc[0]
    return negative, str(worst["month"]), float(worst["total_return"])


def add_combo_scores(row: dict[str, Any], baseline_row: dict[str, Any]) -> dict[str, Any]:
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
    base_trades = int(baseline_row["full_trades"])

    row["delta_vs_v1_ann"] = full_ann - base_ann
    row["delta_vs_v1_max_dd"] = full_dd - base_dd
    row["delta_vs_v1_pf"] = full_pf - base_pf
    row["delta_vs_v1_trades"] = full_trades - base_trades
    row["win_moderate"] = bool(0.60 <= full_win <= 0.90)
    row["sample_ok"] = bool(full_trades >= 120 and int(row["val_2026_03_01_to_2026_06_01_trades"]) >= 12 and int(row["fwd_2026_06_01_to_latest_trades"]) >= 5)
    row["split_ok"] = bool(val_pf >= 1.0 and fwd_pf >= 1.0 and recent30 >= -0.03)
    row["improves_ann"] = bool(full_ann > base_ann)
    row["improves_dd"] = bool(full_dd > base_dd)
    row["improves_pf"] = bool(full_pf > base_pf)
    row["balanced_gate"] = bool(
        row["sample_ok"]
        and row["split_ok"]
        and row["win_moderate"]
        and full_ann > 1.05
        and full_pf >= 1.15
        and full_dd >= -0.12
        and avg_trade > 0.0
    )
    row["strict_improve_gate"] = bool(row["balanced_gate"] and full_ann > base_ann and full_dd > base_dd)
    safe_pf = min(full_pf if np.isfinite(full_pf) else 5.0, 5.0)
    row["balanced_score"] = float(
        70.0 * math.log(max(full_ann, 1e-9))
        + 32.0 * safe_pf
        + 55.0 * full_win
        + 260.0 * max(full_dd, -0.5)
        + 18.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 18.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        + 180.0 * recent30
        + min(full_trades, 260) / 8.0
        - (0.0 if row["win_moderate"] else 18.0)
        - (0.0 if row["sample_ok"] else 25.0)
    )
    row["return_score"] = float(
        120.0 * math.log(max(full_ann, 1e-9))
        + 22.0 * safe_pf
        + 200.0 * max(full_dd, -0.5)
        + 12.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 12.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        + 130.0 * recent30
        - (0.0 if full_trades >= 100 else 35.0)
    )
    row["low_dd_score"] = float(
        500.0 * full_dd
        + 35.0 * safe_pf
        + 55.0 * math.log(max(full_ann, 1e-9))
        + 12.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 12.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        + min(full_trades, 260) / 10.0
    )
    return row


def monthly_for_top(frame: pd.DataFrame, cfg_by_name: dict[str, ScalpConfig], top_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name in top_names:
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


def changed_params(row: dict[str, Any], baseline_row: dict[str, Any]) -> str:
    changed = []
    for field in SIMPLIFIED_ACTIVE_FIELDS:
        key = f"cfg_{field}"
        if str(row.get(key)) != str(baseline_row.get(key)):
            changed.append(f"{field}={row.get(key)}")
    return "; ".join(changed) if changed else "same as V1 simplified baseline"


def table(rows: pd.DataFrame, baseline_row: dict[str, Any], limit: int = 12) -> list[str]:
    output = [
        "| name | changed effective params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{item['name']}` | `{changed_params(item, baseline_row)}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{num(float(item['full_profit_factor']))}` | "
            f"`{pct(float(item['full_win_rate']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | "
            f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | "
            f"`{pct(float(item['recent_30d_total_return']))}` |"
        )
    return output


def render_markdown(
    summary: pd.DataFrame,
    monthly: pd.DataFrame,
    quality: dict[str, Any],
    raw_parity: dict[str, Any] | None,
    args: argparse.Namespace,
) -> str:
    baseline = summary.loc[summary["name"].eq("HYPE-5M-Micro-Scalp-V1-simplified")].iloc[0].to_dict()
    candidates = summary.loc[~summary["name"].eq("HYPE-5M-Micro-Scalp-V1-simplified")].copy()
    strict = candidates.loc[candidates["strict_improve_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    balanced = candidates.loc[candidates["balanced_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    best_return = candidates.loc[candidates["sample_ok"].eq(True)].sort_values("return_score", ascending=False).head(15)
    best_low_dd = candidates.loc[
        (candidates["sample_ok"].eq(True))
        & (candidates["full_annualized_multiple"] >= 1.05)
        & (candidates["full_profit_factor"] >= 1.10)
    ].sort_values("low_dd_score", ascending=False).head(15)

    best_name = str(balanced.iloc[0]["name"]) if not balanced.empty else str(summary.iloc[0]["name"])
    best_monthly = monthly.loc[monthly["name"].eq(best_name)].copy()
    neg_months = int((best_monthly["total_return"] < 0).sum()) if not best_monthly.empty else 0
    worst_month = best_monthly.sort_values("total_return").head(1).to_dict(orient="records") if not best_monthly.empty else []

    lines = [
        "# HYPE-5M-Micro-Scalp-V1 精简参数组合搜索 2026-06-30",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "本轮目标是把 V1 中在 `vwap_revert` 下不生效的 dormant 参数固定，只围绕真实影响信号与退出的字段做组合搜索，寻找比 V1 更高收益、更低回撤、胜率适中的后续观察版本。",
        "",
        "## 精简方式",
        "",
        "- 固定入场机制：`entry_style=vwap_revert`，继续保留 `require_trend=true` 和 EMA 趋势门槛；不再搜索 RSI、Bollinger、Donchian、wick、pullback、breakout、momentum-pause 等对当前入场风格不生效的字段。",
        f"- 保留有效字段 `{len(SIMPLIFIED_ACTIVE_FIELDS)}` 个：`{', '.join(SIMPLIFIED_ACTIVE_FIELDS)}`。",
        "- 允许少量 filter-disable 组合，例如 `cooldown_bars=0`、`max_chop=100`、`max_dist_ema_bps=9999`、`require_body_dir=false`，用于确认 V1 的过滤是否真的必要。",
        "",
        "## 数据与执行口径",
        "",
        f"- 数据：Binance HYPEUSDT perpetual `5m`，`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        f"- 连续性：expected `{quality['expected_bars']}`，missing `{quality['missing_bars']}`，duplicate `{quality['duplicate_ts']}`。",
        f"- OHLC/VWAP/volume 硬违规：`{quality['ohlcv_violations']}`。",
        f"- raw/normalized 对齐：`{raw_parity if raw_parity is not None else 'skipped'}`。",
        "- 信号：闭合 K；入场：下一根 open；退出：入场即固定 TP/SL bracket；同 K 同时触及按 stop-first；timeout 下一根 open。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## 搜索规模",
        "",
        f"- configs evaluated：`{len(summary)}`。",
        f"- seed：`{args.seed}`；core configs sampled：`{args.max_core_configs}`；random configs requested：`{args.max_random_configs}`。",
        "- 结构：V1 baseline + 消融优选 seed + 固定 EMA21/96 的核心网格 + 有效字段 random combo。",
        "",
        "## 当前数据上的 V1 精简基线",
        "",
        f"- trades `{int(baseline['full_trades'])}`，trades/day `{float(baseline['full_trades_per_day']):.2f}`，ann `{mult(float(baseline['full_annualized_multiple']))}`。",
        f"- win `{pct(float(baseline['full_win_rate']))}`，PF `{num(float(baseline['full_profit_factor']))}`，avg `{bps(float(baseline['full_avg_trade']))}`，maxDD `{pct(float(baseline['full_max_dd']))}`。",
        f"- VAL PF `{num(float(baseline['val_2026_03_01_to_2026_06_01_profit_factor']))}`，FWD PF `{num(float(baseline['fwd_2026_06_01_to_latest_profit_factor']))}`，recent30 `{pct(float(baseline['recent_30d_total_return']))}`。",
        "",
        "## 组合结果",
        "",
        f"- balanced gate：`{int(candidates['balanced_gate'].sum())}` / `{len(candidates)}`。",
        f"- strict improve gate（收益高于 V1 且回撤低于 V1）：`{int(candidates['strict_improve_gate'].sum())}` / `{len(candidates)}`。",
        "",
    ]
    if strict.empty:
        lines.append("没有配置同时做到“收益高于当前数据 V1 且 maxDD 更浅”。")
    else:
        lines.extend(["### 严格改进候选", "", *table(strict, baseline, 10)])
    lines.extend(["", "### 均衡候选", ""])
    if balanced.empty:
        lines.append("没有配置通过 balanced gate；以下列表按综合分展示最接近形态。")
        lines.extend(table(candidates.sort_values("balanced_score", ascending=False), baseline, 10))
    else:
        lines.extend(table(balanced, baseline, 12))
    lines.extend(["", "### 高收益排序", "", *table(best_return, baseline, 12)])
    lines.extend(["", "### 低回撤排序", "", *table(best_low_dd, baseline, 12)])
    lines.extend(["", "## 月度提示", ""])
    lines.append(f"- 主观察行：`{best_name}`；负收益月份 `{neg_months}`。")
    if worst_month:
        item = worst_month[0]
        lines.append(
            f"- 最差月份 `{item['month']}`：return `{pct(float(item['total_return']))}`，PF `{num(float(item['profit_factor']))}`，trades `{int(item['trades'])}`。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
        ]
    )
    if not strict.empty:
        lead = strict.iloc[0]
        lines.append(
            f"本轮找到严格优于当前数据 V1 的观察候选 `{lead['name']}`，但它仍只是 `paper-audit observation`，不能替代 V1 或进入实盘。下一步必须做逐笔路径、参数邻域、walk-forward 和订单维护审计。"
        )
    elif not balanced.empty:
        lead = balanced.iloc[0]
        lines.append(
            f"本轮找到收益或回撤某一侧更好的均衡观察候选 `{lead['name']}`，但没有同时超过 V1 的收益与回撤。V1 仍是当前基线，组合候选只适合继续 paper audit。"
        )
    else:
        lines.append("本轮没有找到足够稳健的精简组合候选；V1 仍是当前基线。")
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_simplified_combo_search.py`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
            f"- Top trades CSV：`{TRADES_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame_raw, quality = load_hype_5m()
    raw_parity = None if args.skip_raw_parity else verify_raw_normalized_parity(frame_raw)
    frame = add_features(frame_raw)
    slices = validation_slices(frame)
    configs = build_configs(args.max_random_configs, args.seed, args.max_core_configs)
    cfg_by_name = {cfg.name: cfg for cfg in configs}

    baseline = cfg_by_name["HYPE-5M-Micro-Scalp-V1-simplified"]
    baseline_row, _, _ = row_for_config(frame, baseline, slices)

    rows: list[dict[str, Any]] = []
    best_trades: list[Any] = []
    best_name = baseline.name
    best_score = -float("inf")
    for idx, cfg in enumerate(configs, start=1):
        row, _, trades = row_for_config(frame, cfg, slices)
        row = add_combo_scores(row, baseline_row)
        rows.append(row)
        score = float(row["balanced_score"])
        if score > best_score:
            best_score = score
            best_name = cfg.name
            best_trades = trades
        if args.progress_every and idx % args.progress_every == 0:
            print(
                "progress="
                f"{idx}/{len(configs)} best={best_name} score={best_score:.2f} "
                f"tpd={row['full_trades_per_day']:.2f} ann={row['full_annualized_multiple']:.2f} "
                f"win={row['full_win_rate']:.3f} pf={row['full_profit_factor']:.3f} dd={row['full_max_dd']:.3f}"
                ,
                flush=True,
            )

    summary = pd.DataFrame(rows).sort_values("balanced_score", ascending=False)
    top_names = list(dict.fromkeys(summary.head(args.top_keep)["name"].tolist() + [best_name]))
    monthly = monthly_for_top(frame, cfg_by_name, top_names)
    if best_name in cfg_by_name:
        best_trades, _ = simulate_trades(frame, build_signal(frame, cfg_by_name[best_name]), cfg_by_name[best_name])

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    trades_to_frame(best_trades).to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, monthly, quality, raw_parity, args), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "run_id": RUN_ID,
                "script": "research_hype_5m_micro_scalp_v1_simplified_combo_search.py",
                "simplified_active_fields": SIMPLIFIED_ACTIVE_FIELDS,
                "fixed_dormant_fields": FIXED_DORMANT_FIELDS,
                "seed": args.seed,
                "max_random_configs": args.max_random_configs,
                "max_core_configs": args.max_core_configs,
                "configs_evaluated": int(len(summary)),
                "data_quality": quality,
                "raw_normalized_parity": raw_parity,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "top_trades": str(TRADES_PATH),
                },
                "baseline": summary.loc[summary["name"].eq("HYPE-5M-Micro-Scalp-V1-simplified")]
                .head(1)
                .to_dict(orient="records"),
                "strict_improve_count": int(summary["strict_improve_gate"].sum()),
                "balanced_gate_count": int(summary["balanced_gate"].sum()),
                "top_balanced": summary.sort_values("balanced_score", ascending=False).head(30).to_dict(orient="records"),
                "top_return": summary.sort_values("return_score", ascending=False).head(30).to_dict(orient="records"),
                "top_low_dd": summary.sort_values("low_dd_score", ascending=False).head(30).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"monthly={MONTHLY_PATH}")
    print(f"top_trades={TRADES_PATH}")


if __name__ == "__main__":
    main()
