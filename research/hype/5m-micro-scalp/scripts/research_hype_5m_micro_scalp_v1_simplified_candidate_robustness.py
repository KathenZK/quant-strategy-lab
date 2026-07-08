from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, replace
from itertools import combinations, product
from pathlib import Path
from typing import Any

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
from research_hype_5m_micro_scalp_v1_simplified_combo_search import (
    FIXED_DORMANT_FIELDS,
    MARKDOWN_PATH as COMBO_MARKDOWN_PATH,
    SIMPLIFIED_ACTIVE_FIELDS,
    SUMMARY_PATH as COMBO_SUMMARY_PATH,
    add_combo_scores,
    config_key,
    num,
)


RUN_ID = "2026-06-30"
FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "notes"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_candidate_robustness_summary_{RUN_ID}.csv"
SEED_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_candidate_robustness_by_seed_{RUN_ID}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_candidate_robustness_monthly_{RUN_ID}.csv"
PREFERRED_TRADES_PATH = (
    ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_candidate_robustness_preferred_trades_{RUN_ID}.csv"
)
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_simplified_candidate_robustness_{RUN_ID}.json"
MARKDOWN_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-simplified-candidate-robustness-{RUN_ID}.md"

DEFAULT_CANDIDATES = [
    "V1S_core_032883",
    "V1S_core_023723",
    "V1S_core_023702",
    "V1S_core_034033",
    "V1S_rand_016782",
]

PAIR_FIELDS = [
    "vwap_dev_bps",
    "max_dist_ema_bps",
    "close_pos",
    "tp_bps",
    "sl_bps",
    "max_hold_bars",
    "cooldown_bars",
    "min_adx",
    "max_atr_pct_bps",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local robustness sweep for simplified HYPE-5M-Micro-Scalp-V1 combo leads.")
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--random-per-candidate", type=int, default=2500)
    parser.add_argument("--progress-every", type=int, default=2500)
    parser.add_argument("--candidates", nargs="*", default=DEFAULT_CANDIDATES)
    return parser.parse_args()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def config_from_row(row: pd.Series, name: str | None = None) -> ScalpConfig:
    kwargs: dict[str, Any] = {"name": name or str(row["name"])}
    for field in ScalpConfig.__dataclass_fields__:
        if field == "name":
            continue
        value = row[f"cfg_{field}"]
        if field in {"ema_fast", "ema_slow", "ema_htf", "donchian", "rsi_window", "max_hold_bars", "cooldown_bars"}:
            value = int(value)
        elif field in {"require_trend", "require_htf", "require_macd_turn", "require_body_dir"}:
            value = parse_bool(value)
        elif field in {"side_mode", "entry_style"}:
            value = str(value)
        else:
            value = float(value)
        kwargs[field] = value
    kwargs.update(FIXED_DORMANT_FIELDS)
    return ScalpConfig(**kwargs)


def unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def clipped_close_pos(value: float) -> float:
    return round(float(min(0.82, max(0.52, value))), 2)


def field_options(cfg: ScalpConfig) -> dict[str, list[Any]]:
    return {
        "side_mode": unique([cfg.side_mode, "both", "long", "short"]),
        "ema_fast": unique([cfg.ema_fast, 12, 21, 34, 8]),
        "ema_slow": unique([cfg.ema_slow, 96, 144, 55, 192]),
        "ema_htf": unique([cfg.ema_htf, 192, 384]),
        "vwap_dev_bps": unique([cfg.vwap_dev_bps, cfg.vwap_dev_bps - 15.0, cfg.vwap_dev_bps + 15.0, 60.0, 75.0, 90.0, 120.0]),
        "min_adx": unique([cfg.min_adx, 0.0, 10.0, 14.0, 18.0, 22.0]),
        "max_chop": unique([cfg.max_chop, 42.0, 48.0, 55.0, 62.0, 100.0]),
        "min_rvol": unique([cfg.min_rvol, 0.0, 0.5, 0.75, 1.0, 1.25]),
        "min_atr_pct_bps": unique([cfg.min_atr_pct_bps, 0.0, 18.0, 25.0, 35.0, 50.0]),
        "max_atr_pct_bps": unique([cfg.max_atr_pct_bps, 140.0, 160.0, 220.0, 350.0, 9999.0]),
        "max_dist_ema_bps": unique([cfg.max_dist_ema_bps, 90.0, 130.0, 180.0, 260.0, 400.0, 9999.0]),
        "close_pos": unique([cfg.close_pos, clipped_close_pos(cfg.close_pos - 0.06), clipped_close_pos(cfg.close_pos + 0.06), 0.58, 0.64, 0.70, 0.76]),
        "require_htf": unique([cfg.require_htf, not cfg.require_htf]),
        "require_macd_turn": unique([cfg.require_macd_turn, not cfg.require_macd_turn]),
        "require_body_dir": unique([cfg.require_body_dir, not cfg.require_body_dir]),
        "tp_bps": unique([cfg.tp_bps, 55.0, 67.5, 75.0, 90.0, 110.0]),
        "sl_bps": unique([cfg.sl_bps, 300.0, 400.0, 500.0, 650.0]),
        "max_hold_bars": unique([cfg.max_hold_bars, 36, 48, 72, 96, 144]),
        "cooldown_bars": unique([cfg.cooldown_bars, 0, 12, 24, 36, 48, 72]),
    }


def small_options(options: dict[str, list[Any]], field: str, current: Any) -> list[Any]:
    values = options[field]
    if field in {"require_htf", "require_macd_turn", "require_body_dir", "side_mode"}:
        return values[:2]
    if current in values:
        return unique([current, *values[1:3]])
    return values[:3]


def with_name(cfg: ScalpConfig, seed_name: str, idx: int) -> ScalpConfig:
    return replace(cfg, name=f"{seed_name}__N{idx:05d}")


def build_neighbors(seed_cfg: ScalpConfig, seed_name: str, rng: random.Random, random_count: int) -> list[ScalpConfig]:
    options = field_options(seed_cfg)
    configs: list[ScalpConfig] = [replace(seed_cfg, name=f"{seed_name}__seed")]
    for field in SIMPLIFIED_ACTIVE_FIELDS:
        for value in options[field]:
            if value == getattr(seed_cfg, field):
                continue
            configs.append(replace(seed_cfg, name=f"{seed_name}__{field}__{value}", **{field: value}))

    idx = 0
    for field_a, field_b in combinations(PAIR_FIELDS, 2):
        vals_a = small_options(options, field_a, getattr(seed_cfg, field_a))
        vals_b = small_options(options, field_b, getattr(seed_cfg, field_b))
        for value_a, value_b in product(vals_a, vals_b):
            if value_a == getattr(seed_cfg, field_a) and value_b == getattr(seed_cfg, field_b):
                continue
            idx += 1
            configs.append(replace(seed_cfg, name=f"{seed_name}__P{idx:04d}", **{field_a: value_a, field_b: value_b}))

    for rand_i in range(random_count):
        kwargs: dict[str, Any] = {}
        for field in SIMPLIFIED_ACTIVE_FIELDS:
            if rng.random() < 0.42:
                kwargs[field] = rng.choice(options[field])
        idx += 1
        configs.append(replace(seed_cfg, name=f"{seed_name}__R{rand_i:05d}", **kwargs))

    deduped: list[ScalpConfig] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for cfg in configs:
        if cfg.ema_fast >= cfg.ema_slow:
            continue
        key = config_key(cfg)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(with_name(cfg, seed_name, len(deduped)))
    return deduped


def add_robust_flags(row: dict[str, Any]) -> dict[str, Any]:
    row["audit_like_gate"] = bool(
        int(row["full_trades"]) >= 120
        and float(row["full_annualized_multiple"]) >= 1.30
        and float(row["full_profit_factor"]) >= 1.50
        and 0.60 <= float(row["full_win_rate"]) <= 0.94
        and float(row["full_max_dd"]) >= -0.10
        and float(row["full_avg_trade"]) > 0
        and float(row["val_2026_03_01_to_2026_06_01_profit_factor"]) >= 1.0
        and float(row["fwd_2026_06_01_to_latest_profit_factor"]) >= 1.0
        and float(row["recent_30d_total_return"]) >= 0.0
    )
    return row


def seed_summary(rows: pd.DataFrame) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for seed_name, group in rows.groupby("seed_candidate"):
        strict = group.loc[group["strict_improve_gate"].eq(True)]
        audit_like = group.loc[group["audit_like_gate"].eq(True)]
        best = group.sort_values("balanced_score", ascending=False).iloc[0]
        items.append(
            {
                "seed_candidate": seed_name,
                "configs": int(len(group)),
                "strict_improve_count": int(len(strict)),
                "strict_improve_rate": float(len(strict) / len(group)),
                "audit_like_count": int(len(audit_like)),
                "audit_like_rate": float(len(audit_like) / len(group)),
                "median_ann": float(group["full_annualized_multiple"].median()),
                "p25_ann": float(group["full_annualized_multiple"].quantile(0.25)),
                "median_pf": float(group["full_profit_factor"].replace(np.inf, np.nan).median()),
                "median_max_dd": float(group["full_max_dd"].median()),
                "p10_max_dd": float(group["full_max_dd"].quantile(0.10)),
                "best_name": str(best["name"]),
                "best_ann": float(best["full_annualized_multiple"]),
                "best_pf": float(best["full_profit_factor"]),
                "best_win": float(best["full_win_rate"]),
                "best_max_dd": float(best["full_max_dd"]),
                "best_recent30": float(best["recent_30d_total_return"]),
            }
        )
    return pd.DataFrame(items).sort_values(["audit_like_rate", "strict_improve_rate", "best_ann"], ascending=False)


def monthly_for_top(frame: pd.DataFrame, cfg_by_name: dict[str, ScalpConfig], names: list[str]) -> pd.DataFrame:
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


def select_preferred(summary: pd.DataFrame) -> pd.Series:
    best_audit = summary.loc[summary["audit_like_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    finite_fwd = best_audit.loc[np.isfinite(best_audit["fwd_2026_06_01_to_latest_profit_factor"])]
    if not finite_fwd.empty:
        return finite_fwd.iloc[0]
    if not best_audit.empty:
        return best_audit.iloc[0]
    return summary.sort_values("balanced_score", ascending=False).iloc[0]


def table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    output = [
        "| name | seed | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 | strict | audit-like |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{item['name']}` | `{item['seed_candidate']}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{num(float(item['full_profit_factor']))}` | "
            f"`{pct(float(item['full_win_rate']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | `{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | `{pct(float(item['recent_30d_total_return']))}` | "
            f"`{bool(item['strict_improve_gate'])}` | `{bool(item['audit_like_gate'])}` |"
        )
    return output


def render_markdown(
    summary: pd.DataFrame,
    by_seed: pd.DataFrame,
    monthly: pd.DataFrame,
    quality: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    best_audit = summary.loc[summary["audit_like_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    best_strict = summary.loc[summary["strict_improve_gate"].eq(True)].sort_values("balanced_score", ascending=False)
    preferred = select_preferred(summary)
    preferred_monthly = monthly.loc[monthly["name"].eq(preferred["name"])]
    neg_months = int((preferred_monthly["total_return"] < 0).sum()) if not preferred_monthly.empty else 0

    lines = [
        "# HYPE-5M-Micro-Scalp-V1 精简候选局部稳健性 2026-06-30",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "本报告围绕精简组合搜索的前排候选做局部邻域测试，目的是确认改善不是单点参数尖峰。它仍是 paper-audit observation，不是 promotion。",
        "",
        "## 输入",
        "",
        f"- 来源组合报告：`{COMBO_MARKDOWN_PATH}`。",
        f"- 来源 summary：`{COMBO_SUMMARY_PATH}`。",
        f"- seed candidates：`{', '.join(args.candidates)}`。",
        f"- 每个候选 random local configs：`{args.random_per_candidate}`。",
        "",
        "## 数据与执行口径",
        "",
        f"- 数据：`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 Binance HYPEUSDT perpetual `5m` K。",
        f"- 缺口 `{quality['missing_bars']}`，OHLC/VWAP/volume 硬违规：`{quality['ohlcv_violations']}`。",
        "- 执行：闭合 K 信号、下一根 open 入场、入场即 TP/SL bracket、同 K stop-first、timeout 下一根 open。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## 稳健性摘要",
        "",
        "| seed | configs | strict improve | strict rate | audit-like | audit-like rate | median ann | p25 ann | median PF | median DD | p10 DD | best ann | best DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in by_seed.to_dict(orient="records"):
        lines.append(
            f"| `{row['seed_candidate']}` | `{int(row['configs'])}` | `{int(row['strict_improve_count'])}` | "
            f"`{float(row['strict_improve_rate']):.1%}` | `{int(row['audit_like_count'])}` | `{float(row['audit_like_rate']):.1%}` | "
            f"`{mult(float(row['median_ann']))}` | `{mult(float(row['p25_ann']))}` | `{num(float(row['median_pf']))}` | "
            f"`{pct(float(row['median_max_dd']))}` | `{pct(float(row['p10_max_dd']))}` | "
            f"`{mult(float(row['best_ann']))}` | `{pct(float(row['best_max_dd']))}` |"
        )
    lines.extend(["", "## Top Audit-Like Neighbors", "", *table(best_audit, 15)])
    lines.extend(["", "## Top Strict Improve Neighbors", "", *table(best_strict, 15)])
    lines.extend(["", "## 主观察结论", ""])
    lines.append(
        f"- 推荐下一步优先审计 `{preferred['name']}`（seed `{preferred['seed_candidate']}`）：ann `{mult(float(preferred['full_annualized_multiple']))}`，PF `{num(float(preferred['full_profit_factor']))}`，win `{pct(float(preferred['full_win_rate']))}`，maxDD `{pct(float(preferred['full_max_dd']))}`，recent30 `{pct(float(preferred['recent_30d_total_return']))}`，负收益月份 `{neg_months}`。"
    )
    lines.extend(["", "## 推荐行参数", "", "| field | value |", "| --- | --- |"])
    for field in SIMPLIFIED_ACTIVE_FIELDS:
        lines.append(f"| `{field}` | `{preferred[f'cfg_{field}']}` |")
    lines.extend(["", "固定机制与 dormant 字段：`entry_style=vwap_revert`，`require_trend=true`；RSI/Bollinger/Donchian/wick/pullback/breakout/momentum-pause 参数不参与当前信号。"])
    lines.append(
        "- 该推荐不是 live-ready：还需要逐笔路径图、同 K TP/SL 与 gap ordering 审计、参数邻域二次收缩、walk-forward 固化、订单维护与 restart-state 审计。"
    )
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_simplified_candidate_robustness.py`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- By-seed CSV：`{SEED_SUMMARY_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
            f"- Preferred trades CSV：`{PREFERRED_TRADES_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    combo = pd.read_csv(COMBO_SUMMARY_PATH)
    baseline_row = combo.loc[combo["name"].eq("HYPE-5M-Micro-Scalp-V1-simplified")].iloc[0].to_dict()
    seed_rows = combo.loc[combo["name"].isin(args.candidates)].copy()
    if len(seed_rows) != len(args.candidates):
        found = set(seed_rows["name"])
        missing = [name for name in args.candidates if name not in found]
        raise RuntimeError(f"missing candidates in combo summary: {missing}")

    frame_raw, quality = load_hype_5m()
    frame = add_features(frame_raw)
    slices = validation_slices(frame)
    rng = random.Random(args.seed)

    configs: list[tuple[str, ScalpConfig]] = []
    for _, row in seed_rows.iterrows():
        seed_name = str(row["name"])
        seed_cfg = config_from_row(row, seed_name)
        for cfg in build_neighbors(seed_cfg, seed_name, rng, args.random_per_candidate):
            configs.append((seed_name, cfg))

    rows: list[dict[str, Any]] = []
    cfg_by_name: dict[str, ScalpConfig] = {}
    for idx, (seed_name, cfg) in enumerate(configs, start=1):
        row, _, _ = row_for_config(frame, cfg, slices)
        row = add_combo_scores(row, baseline_row)
        row = add_robust_flags(row)
        row["seed_candidate"] = seed_name
        rows.append(row)
        cfg_by_name[cfg.name] = cfg
        if args.progress_every and idx % args.progress_every == 0:
            print(
                f"progress={idx}/{len(configs)} seed={seed_name} name={cfg.name} "
                f"ann={row['full_annualized_multiple']:.2f} pf={row['full_profit_factor']:.3f} "
                f"dd={row['full_max_dd']:.3f}",
                flush=True,
            )

    summary = pd.DataFrame(rows).sort_values("balanced_score", ascending=False)
    by_seed = seed_summary(summary)
    top_names = list(
        dict.fromkeys(
            summary.loc[summary["audit_like_gate"].eq(True)].sort_values("balanced_score", ascending=False).head(80)["name"].tolist()
            + summary.loc[summary["strict_improve_gate"].eq(True)].sort_values("balanced_score", ascending=False).head(80)["name"].tolist()
        )
    )
    monthly = monthly_for_top(frame, cfg_by_name, top_names[:120])
    preferred = select_preferred(summary)
    preferred_cfg = cfg_by_name[str(preferred["name"])]
    preferred_trades, _ = simulate_trades(frame, build_signal(frame, preferred_cfg), preferred_cfg)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    by_seed.to_csv(SEED_SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    trades_to_frame(preferred_trades).to_csv(PREFERRED_TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, by_seed, monthly, quality, args), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "run_id": RUN_ID,
                "script": "research_hype_5m_micro_scalp_v1_simplified_candidate_robustness.py",
                "source_summary": str(COMBO_SUMMARY_PATH),
                "seed_candidates": args.candidates,
                "random_per_candidate": args.random_per_candidate,
                "configs_evaluated": int(len(summary)),
                "data_quality": quality,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "by_seed": str(SEED_SUMMARY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "preferred_trades": str(PREFERRED_TRADES_PATH),
                },
                "preferred": preferred.to_dict(),
                "by_seed": by_seed.to_dict(orient="records"),
                "top_audit_like": summary.loc[summary["audit_like_gate"].eq(True)]
                .sort_values("balanced_score", ascending=False)
                .head(30)
                .to_dict(orient="records"),
                "top_strict_improve": summary.loc[summary["strict_improve_gate"].eq(True)]
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
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"by_seed={SEED_SUMMARY_PATH}")
    print(f"monthly={MONTHLY_PATH}")
    print(f"preferred_trades={PREFERRED_TRADES_PATH}")


if __name__ == "__main__":
    main()
