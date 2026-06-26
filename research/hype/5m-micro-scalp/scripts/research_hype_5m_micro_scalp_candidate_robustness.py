from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_micro_scalp_relaxed_rounds import row_to_config
from research_hype_5m_micro_scalp_search import (
    ARTIFACT_ROOT,
    DIAGNOSTIC_ROOT,
    EXIT_SLIPPAGE_RATE,
    ENTRY_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    ScalpConfig,
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


CANDIDATES_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_relaxed_rounds_candidates_2026-06-26.csv"
REPORT_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_candidate_robustness_2026-06-26.json"
SUMMARY_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_candidate_robustness_summary_2026-06-26.csv"
MONTHLY_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_candidate_robustness_monthly_2026-06-26.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / "hype-5m-micro-scalp-candidate-robustness-2026-06-26.md"

BASE_NAMES = (
    "R2_relax_winrate_payoff_R04600",
    "R1_relax_frequency_R03831",
    "R3_live_candidate_gate_R03979",
    "R1_relax_frequency_R01242",
)


def num(value: float, digits: int = 3) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def bps(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 10000:.{digits}f} bps"


def local_values(value: float, *, minimum: float = 0.0) -> tuple[float, ...]:
    return tuple(sorted({max(minimum, round(value * mult, 6)) for mult in (0.75, 0.9, 1.0, 1.1, 1.25, 1.5)}))


def local_int_values(value: int, options: tuple[int, ...]) -> tuple[int, ...]:
    nearest = sorted(options, key=lambda item: abs(item - value))[:5]
    return tuple(sorted(set([value, *nearest])))


def build_local_configs(base: ScalpConfig, base_name: str) -> list[ScalpConfig]:
    configs: list[ScalpConfig] = []
    seen: set[tuple[Any, ...]] = set()

    def add(cfg: ScalpConfig, tag: str) -> None:
        named = replace(cfg, name=f"{base_name}__{tag}_{len(configs):04d}")
        data = asdict(named)
        data.pop("name", None)
        key = tuple(data.items())
        if key not in seen:
            seen.add(key)
            configs.append(named)

    add(base, "base")

    ema_fast_values = local_int_values(base.ema_fast, (5, 8, 9, 12, 21, 34))
    ema_slow_values = local_int_values(base.ema_slow, (21, 34, 55, 96, 144, 192))
    ema_htf_values = local_int_values(base.ema_htf, (96, 144, 192, 288, 384))
    donchian_values = local_int_values(base.donchian, (12, 24, 48, 96))
    hold_values = local_int_values(base.max_hold_bars, (6, 9, 12, 18, 24, 36, 48, 72, 96, 144))
    cooldown_values = local_int_values(base.cooldown_bars, (0, 6, 12, 18, 24, 36, 48, 72, 96, 144, 192))

    for tp in local_values(base.tp_bps, minimum=20.0):
        for sl in local_values(base.sl_bps, minimum=30.0):
            add(replace(base, tp_bps=tp, sl_bps=sl), "tp_sl")

    for hold in hold_values:
        for cooldown in cooldown_values:
            add(replace(base, max_hold_bars=hold, cooldown_bars=cooldown), "hold_cd")

    for fast in ema_fast_values:
        for slow in ema_slow_values:
            if fast < slow:
                add(replace(base, ema_fast=fast, ema_slow=slow), "ema")
    for htf in ema_htf_values:
        for donchian in donchian_values:
            add(replace(base, ema_htf=htf, donchian=donchian), "context")

    for vwap in local_values(base.vwap_dev_bps, minimum=10.0):
        for dist in local_values(base.max_dist_ema_bps, minimum=20.0):
            add(replace(base, vwap_dev_bps=vwap, max_dist_ema_bps=dist), "dist")

    for bb in tuple(sorted({max(0.5, base.bb_z + delta) for delta in (-0.5, -0.25, 0.0, 0.25, 0.5)})):
        for close_pos in tuple(sorted({min(0.9, max(0.45, base.close_pos + delta)) for delta in (-0.12, -0.06, 0.0, 0.06, 0.12)})):
            add(replace(base, bb_z=bb, close_pos=close_pos), "trigger")

    for min_adx in tuple(sorted({max(0.0, base.min_adx + delta) for delta in (-10.0, -5.0, 0.0, 5.0, 10.0)})):
        for max_chop in tuple(sorted({min(100.0, max(35.0, base.max_chop + delta)) for delta in (-20.0, -10.0, 0.0, 10.0, 20.0)})):
            add(replace(base, min_adx=min_adx, max_chop=max_chop), "regime")

    for require_trend in (base.require_trend, not base.require_trend):
        for require_htf in (base.require_htf, not base.require_htf):
            for require_macd_turn in (base.require_macd_turn, not base.require_macd_turn):
                add(
                    replace(
                        base,
                        require_trend=require_trend,
                        require_htf=require_htf,
                        require_macd_turn=require_macd_turn,
                    ),
                    "bool",
                )
    return configs


def robust_gate(row: dict[str, Any]) -> bool:
    return bool(
        int(row["full_trades"]) >= 80
        and float(row["full_annualized_multiple"]) >= 1.05
        and float(row["full_profit_factor"]) >= 1.10
        and float(row["full_max_dd"]) >= -0.20
        and float(row["val_2026_03_01_to_2026_06_01_profit_factor"]) >= 1.0
        and float(row["fwd_2026_06_01_to_latest_profit_factor"]) >= 1.0
        and int(row["fwd_2026_06_01_to_latest_trades"]) >= 5
        and float(row["recent_30d_total_return"]) >= -0.02
    )


def monthly_for(summary: pd.DataFrame, configs: dict[str, ScalpConfig], frame: pd.DataFrame) -> pd.DataFrame:
    names = summary.loc[summary["robust_gate"].eq(True), "name"].drop_duplicates().tolist()
    names.extend(summary.sort_values("robust_score", ascending=False).head(40)["name"].tolist())
    names = list(dict.fromkeys(names))
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name in names:
        cfg = configs[name]
        trades, _ = simulate_trades(frame, build_signal(frame, cfg), cfg)
        for item in months:
            rows.append(
                {
                    "name": name,
                    "base_candidate": summary.loc[summary["name"].eq(name), "base_candidate"].iloc[0],
                    "month": item["name"],
                    "month_start": item["start"],
                    "month_end": item["end"],
                    **metric_from_trades(trades, start=item["start"], end=item["end"]),
                }
            )
    return pd.DataFrame(rows)


def add_monthly_gate(summary: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        summary["robust_monthly_pass"] = False
        return summary
    agg = (
        monthly.assign(negative_month=lambda frame: frame["total_return"] < 0)
        .groupby("name")
        .agg(
            months=("month", "count"),
            negative_months=("negative_month", "sum"),
            worst_month_return=("total_return", "min"),
            median_month_return=("total_return", "median"),
        )
        .reset_index()
    )
    result = summary.merge(agg, on="name", how="left")
    result["robust_monthly_pass"] = (
        result["robust_gate"].eq(True)
        & result["negative_months"].le(6)
        & result["worst_month_return"].ge(-0.12)
    )
    return result


def robust_score(row: dict[str, Any]) -> float:
    ann = float(row["full_annualized_multiple"])
    pf = float(row["full_profit_factor"])
    val_pf = float(row["val_2026_03_01_to_2026_06_01_profit_factor"])
    fwd_pf = float(row["fwd_2026_06_01_to_latest_profit_factor"])
    return float(
        min(80.0, np.log(max(ann, 1e-9)) * 35.0)
        + 55.0 * min(pf if np.isfinite(pf) else 4.0, 4.0)
        + 40.0 * min(val_pf if np.isfinite(val_pf) else 4.0, 4.0)
        + 40.0 * min(fwd_pf if np.isfinite(fwd_pf) else 4.0, 4.0)
        + 30.0 * max(float(row["full_max_dd"]), -1.0)
        + 15.0 * float(row["full_win_rate"])
        + 5.0 * max(float(row["recent_30d_total_return"]), -0.2)
    )


def table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    output = [
        "| base | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{item['base_candidate']}` | `{item['name']}` | `{item['cfg_entry_style']}` | `{item['cfg_side_mode']}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{pct(float(item['full_win_rate']))}` | "
            f"`{num(float(item['full_profit_factor']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | "
            f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | "
            f"`{pct(float(item['recent_30d_total_return']))}` | "
            f"`{int(item['negative_months']) if pd.notna(item.get('negative_months')) else '-'}` |"
        )
    return output


def render_markdown(summary: pd.DataFrame, quality: dict[str, Any]) -> str:
    robust = summary.loc[summary["robust_gate"].eq(True)].sort_values("robust_score", ascending=False)
    monthly = summary.loc[summary["robust_monthly_pass"].eq(True)].sort_values("robust_score", ascending=False)
    lines = [
        "# HYPE 5m Micro-Scalp candidate robustness 2026-06-26",
        "",
        "Family id: `HYPE-5M-Micro-Scalp`",
        "",
        "目标：围绕 relaxed-rounds 里交易数相对足够的候选做参数邻域复核，判断是否只是单点碰巧。",
        "",
        "## 固定执行口径",
        "",
        "- 闭合 K 信号；下一根 open 入场。",
        "- 入场即固定 TP/SL bracket；同 K 同时触及按止损先成交。",
        "- stop/target open 穿越按 open 市价成交；timeout 下一根 open 退出。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## 数据",
        "",
        f"- `{quality['start_ts']}` 到 `{quality['end_ts']}`，missing `{quality['missing_bars']}`，OHLC/VWAP/volume hard violations `{quality['ohlcv_violations']}`。",
        "",
        "## 邻域结果",
        "",
        f"- 测试邻域配置：`{len(summary)}`。",
        f"- robust gate 通过：`{len(robust)}`。",
        f"- robust + monthly gate 通过：`{len(monthly)}`。",
        "",
    ]
    for base_name, group in summary.groupby("base_candidate"):
        lines.append(f"### {base_name}")
        lines.append("")
        lines.append(
            f"- configs `{len(group)}`；robust gate `{int(group['robust_gate'].sum())}`；"
            f"monthly pass `{int(group['robust_monthly_pass'].sum())}`。"
        )
        lines.append("")
        best = group.sort_values("robust_score", ascending=False)
        lines.extend(table(best, limit=6))
        lines.append("")
    lines.extend(["## Robust Monthly Pass Top", ""])
    if monthly.empty:
        lines.append("没有候选同时通过 robust gate 和月度 gate。")
    else:
        lines.extend(table(monthly, limit=16))
    lines.extend(
        [
            "",
            "## 结论",
            "",
        ]
    )
    if monthly.empty:
        lines.append("邻域复核没有留下可推进候选。")
    else:
        lines.append("邻域复核留下多个可推进候选；下一步应针对最稳的 1-2 个生成逐笔路径图、paper audit runner 和 live spec 草案。")
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_PATH}`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw, quality = load_hype_5m()
    frame = add_features(raw)
    candidates = pd.read_csv(CANDIDATES_PATH)
    bases = candidates.loc[candidates["name"].isin(BASE_NAMES)].copy()
    if len(bases) != len(BASE_NAMES):
        missing = sorted(set(BASE_NAMES) - set(bases["name"]))
        raise RuntimeError(f"missing base candidates: {missing}")

    configs: dict[str, ScalpConfig] = {}
    all_rows: list[dict[str, Any]] = []
    slices = validation_slices(frame)
    for _, base_row in bases.iterrows():
        base_name = str(base_row["name"])
        base_cfg = row_to_config(base_row, base_name)
        local_configs = build_local_configs(base_cfg, base_name)
        print(f"base={base_name} local_configs={len(local_configs)}")
        for idx, cfg in enumerate(local_configs, start=1):
            row, _, _ = row_for_config(frame, cfg, slices)
            row["base_candidate"] = base_name
            row["robust_gate"] = robust_gate(row)
            row["robust_score"] = robust_score(row)
            all_rows.append(row)
            configs[str(row["name"])] = cfg
            if idx % 300 == 0:
                best = max((item for item in all_rows if item["base_candidate"] == base_name), key=lambda item: item["robust_score"])
                print(
                    f"{base_name} progress={idx}/{len(local_configs)} "
                    f"best={best['name']} ann={best['full_annualized_multiple']:.3f} "
                    f"pf={best['full_profit_factor']:.3f} tpd={best['full_trades_per_day']:.3f}"
                )

    summary = pd.DataFrame(all_rows).sort_values("robust_score", ascending=False)
    monthly = monthly_for(summary, configs, frame)
    summary = add_monthly_gate(summary, monthly).sort_values("robust_score", ascending=False)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, quality), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "base_candidates": BASE_NAMES,
                "data_quality": quality,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "configs": int(len(summary)),
                "robust_gate_count": int(summary["robust_gate"].sum()),
                "robust_monthly_pass_count": int(summary["robust_monthly_pass"].sum()),
                "top": summary.head(50).to_dict(orient="records"),
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
    print(f"robust_gate={int(summary['robust_gate'].sum())} robust_monthly={int(summary['robust_monthly_pass'].sum())}")
    print(summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
