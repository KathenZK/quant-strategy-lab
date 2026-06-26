from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd


RUN_DATE = "2026-06-26"
FAMILY_ROOT = Path("research/hype/5m-ma-pullback-scalp")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"
BASE_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_ma_pullback_scalp_search_summary_{RUN_DATE}.csv"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_ma_pullback_scalp_robustness_summary_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_ma_pullback_scalp_robustness_monthly_{RUN_DATE}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_ma_pullback_scalp_robustness_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-ma-pullback-scalp-robustness-{RUN_DATE}.md"


def load_search_module() -> Any:
    script = Path(__file__).with_name("research_hype_5m_ma_pullback_scalp.py")
    spec = importlib.util.spec_from_file_location("hype_5m_ma_pullback_scalp_search", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def around(value: float, steps: list[float], *, floor: float | None = None, ceil: float | None = None) -> list[float]:
    values = []
    for step in steps:
        candidate = value + step
        if floor is not None:
            candidate = max(floor, candidate)
        if ceil is not None:
            candidate = min(ceil, candidate)
        values.append(float(candidate))
    return sorted(set(values))


def int_around(value: int, steps: list[int], *, floor: int = 1) -> list[int]:
    return sorted({max(floor, int(value + step)) for step in steps})


def base_config_from_row(module: Any, row: pd.Series) -> Any:
    return module.PullbackConfig(
        name=str(row["name"]),
        side_mode=str(row["cfg_side_mode"]),
        trigger_style=str(row["cfg_trigger_style"]),
        fast_ma=int(row["cfg_fast_ma"]),
        slow_ma=int(row["cfg_slow_ma"]),
        structure_window=int(row["cfg_structure_window"]),
        platform_window=int(row["cfg_platform_window"]),
        structure_margin_bps=float(row["cfg_structure_margin_bps"]),
        slope_lookback=int(row["cfg_slope_lookback"]),
        min_slow_slope_bps=float(row["cfg_min_slow_slope_bps"]),
        min_fast_slope_bps=float(row["cfg_min_fast_slope_bps"]),
        pullback_touch_bps=float(row["cfg_pullback_touch_bps"]),
        reclaim_bps=float(row["cfg_reclaim_bps"]),
        min_body_atr=float(row["cfg_min_body_atr"]),
        max_dist_slow_bps=float(row["cfg_max_dist_slow_bps"]),
        min_atr_bps=float(row["cfg_min_atr_bps"]),
        max_atr_bps=float(row["cfg_max_atr_bps"]),
        min_rvol60=float(row["cfg_min_rvol60"]),
        min_adx14=float(row["cfg_min_adx14"]),
        close_pos=float(row["cfg_close_pos"]),
        require_body_dir=bool(row["cfg_require_body_dir"]),
        tp_bps=float(row["cfg_tp_bps"]),
        sl_bps=float(row["cfg_sl_bps"]),
        max_hold_bars=int(row["cfg_max_hold_bars"]),
        cooldown_bars=int(row["cfg_cooldown_bars"]),
    )


def mutate_configs(module: Any, base_cfg: Any, *, max_configs: int, seed: int) -> list[Any]:
    rng = random.Random(seed)
    fast_slow_pairs = sorted(
        {
            (base_cfg.fast_ma, base_cfg.slow_ma),
            (13, 89),
            (21, 144),
            (34, 233),
            (55, 377),
            (89, 610),
        }
    )
    structure_windows = int_around(base_cfg.structure_window, [-20, -10, -5, 0, 5, 10, 20], floor=6)
    platform_windows = int_around(base_cfg.platform_window, [-8, -5, -3, 0, 3, 5, 8], floor=3)
    slope_lookbacks = int_around(base_cfg.slope_lookback, [-20, -10, -5, 0, 5, 10, 20], floor=5)
    slow_slopes = around(base_cfg.min_slow_slope_bps, [-20, -10, -5, 0, 5, 10, 20], floor=-20.0)
    fast_slopes = around(base_cfg.min_fast_slope_bps, [-30, -15, -5, 0, 5, 15, 30], floor=-40.0)
    touch_values = around(base_cfg.pullback_touch_bps, [-30, -15, -5, 0, 5, 15, 30], floor=0.0)
    reclaim_values = around(base_cfg.reclaim_bps, [-15, -5, 0, 5, 15], floor=0.0)
    body_values = around(base_cfg.min_body_atr, [-0.35, -0.15, 0, 0.15, 0.35], floor=0.0, ceil=1.5)
    max_dist_values = around(base_cfg.max_dist_slow_bps, [-250, -120, -60, 0, 60, 120, 250], floor=60.0)
    min_atr_values = around(base_cfg.min_atr_bps, [-30, -15, -5, 0, 5, 15, 30], floor=0.0)
    max_atr_values = around(base_cfg.max_atr_bps, [-250, -120, -60, 0, 60, 120, 250], floor=80.0, ceil=9999.0)
    rvol_values = around(base_cfg.min_rvol60, [-0.5, -0.25, 0, 0.25, 0.5], floor=0.0)
    adx_values = around(base_cfg.min_adx14, [-12, -6, 0, 6, 12], floor=0.0)
    close_pos_values = around(base_cfg.close_pos, [-0.12, -0.06, 0, 0.06, 0.12], floor=0.50, ceil=0.86)
    tp_values = around(base_cfg.tp_bps, [-80, -40, -20, 0, 20, 40, 80], floor=40.0)
    sl_values = around(base_cfg.sl_bps, [-80, -40, -20, 0, 20, 40, 80], floor=40.0)
    hold_values = int_around(base_cfg.max_hold_bars, [-20, -10, -5, 0, 5, 10, 20], floor=3)
    cooldown_values = int_around(base_cfg.cooldown_bars, [-10, -5, -2, 0, 2, 5, 10], floor=0)

    configs: dict[str, Any] = {}
    configs[f"{base_cfg.name}__base"] = base_cfg.__class__(
        **{**module.asdict(base_cfg), "name": f"{base_cfg.name}__base"}
    )

    choices = [
        fast_slow_pairs,
        structure_windows,
        platform_windows,
        slope_lookbacks,
        slow_slopes,
        fast_slopes,
        touch_values,
        reclaim_values,
        body_values,
        max_dist_values,
        min_atr_values,
        max_atr_values,
        rvol_values,
        adx_values,
        close_pos_values,
        tp_values,
        sl_values,
        hold_values,
        cooldown_values,
    ]
    for idx in range(max_configs * 4):
        (
            fast_slow,
            structure_window,
            platform_window,
            slope_lookback,
            slow_slope,
            fast_slope,
            touch,
            reclaim,
            body_atr,
            max_dist,
            min_atr,
            max_atr,
            rvol,
            adx,
            close_pos,
            tp,
            sl,
            hold,
            cooldown,
        ) = [rng.choice(item) for item in choices]
        if min_atr > max_atr:
            min_atr, max_atr = max_atr, min_atr
        name = f"{base_cfg.name}__nb_{idx:04d}"
        cfg = module.PullbackConfig(
            name=name,
            side_mode=base_cfg.side_mode,
            trigger_style=base_cfg.trigger_style,
            fast_ma=fast_slow[0],
            slow_ma=fast_slow[1],
            structure_window=structure_window,
            platform_window=platform_window,
            structure_margin_bps=base_cfg.structure_margin_bps,
            slope_lookback=slope_lookback,
            min_slow_slope_bps=slow_slope,
            min_fast_slope_bps=fast_slope,
            pullback_touch_bps=touch,
            reclaim_bps=reclaim,
            min_body_atr=body_atr,
            max_dist_slow_bps=max_dist,
            min_atr_bps=min_atr,
            max_atr_bps=max_atr,
            min_rvol60=rvol,
            min_adx14=adx,
            close_pos=close_pos,
            require_body_dir=base_cfg.require_body_dir,
            tp_bps=tp,
            sl_bps=sl,
            max_hold_bars=hold,
            cooldown_bars=cooldown,
        )
        key = json.dumps(module.asdict(cfg), sort_keys=True, default=str)
        configs.setdefault(key, cfg)
        if len(configs) >= max_configs:
            break
    return list(configs.values())[:max_configs]


def robust_flags(row: dict[str, Any], monthly_rows: pd.DataFrame) -> tuple[bool, bool]:
    robust = (
        int(row["full_trades"]) >= 45
        and float(row["full_total_return"]) > 0.0
        and float(row["full_profit_factor"]) >= 1.05
        and float(row["full_max_dd"]) >= -0.22
        and float(row["val_next_20pct_profit_factor"]) >= 1.0
        and float(row["fwd_last_20pct_profit_factor"]) >= 1.0
        and float(row["recent_30d_total_return"]) >= -0.03
    )
    if monthly_rows.empty:
        return robust, False
    negative_months = int((monthly_rows["total_return"] < 0).sum())
    worst_month = float(monthly_rows["total_return"].min())
    monthly = robust and negative_months <= 5 and worst_month >= -0.08
    return robust, monthly


def main() -> None:
    module = load_search_module()
    search_summary = pd.read_csv(BASE_SUMMARY_PATH)
    pass_rows = search_summary.loc[search_summary["paper_candidate_pass"].eq(True)].copy()
    if pass_rows.empty:
        raise RuntimeError("no paper candidate pass rows to test")

    base_configs = [base_config_from_row(module, row) for _, row in pass_rows.iterrows()]
    configs: list[Any] = []
    for idx, cfg in enumerate(base_configs):
        configs.extend(mutate_configs(module, cfg, max_configs=420, seed=20260626 + idx))

    spans = sorted({span for cfg in configs for span in (cfg.fast_ma, cfg.slow_ma)})
    structure_windows = sorted({cfg.structure_window for cfg in configs})
    platform_windows = sorted({cfg.platform_window for cfg in configs})
    frame_raw, quality = module.validate_hype_5m()
    frame = module.add_features(frame_raw, spans, structure_windows, platform_windows)
    slices = module.validation_slices(frame)
    months = module.month_slices(frame)

    summary_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    for idx, cfg in enumerate(configs, start=1):
        row, _, trades = module.row_for_config(frame, cfg, slices)
        per_month = []
        for item in months:
            metrics = module.metric_from_trades(trades, start=item["start"], end=item["end"])
            month_row = {"name": cfg.name, "base_name": cfg.name.split("__")[0], "month": item["name"], **metrics}
            per_month.append(month_row)
            monthly_rows.append(month_row)
        month_frame = pd.DataFrame(per_month)
        robust, monthly = robust_flags(row, month_frame)
        row["base_name"] = cfg.name.split("__")[0]
        row["robust_pass"] = robust
        row["monthly_pass"] = monthly
        row["negative_months"] = int((month_frame["total_return"] < 0).sum()) if not month_frame.empty else 0
        row["worst_month_return"] = float(month_frame["total_return"].min()) if not month_frame.empty else 0.0
        summary_rows.append(row)
        if idx % 200 == 0:
            best = max(summary_rows, key=lambda item: float(item["score"]))
            print(
                f"[{idx}/{len(configs)}] robust={sum(bool(item['robust_pass']) for item in summary_rows)} "
                f"monthly={sum(bool(item['monthly_pass']) for item in summary_rows)} "
                f"best={best['name']} ann={float(best['full_annualized_multiple']):.3f} "
                f"pf={float(best['full_profit_factor']):.3f}"
            )

    summary = pd.DataFrame(summary_rows).sort_values("score", ascending=False).reset_index(drop=True)
    monthly = pd.DataFrame(monthly_rows)
    summary.to_csv(SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)

    top = summary.loc[summary["monthly_pass"].eq(True)].sort_values("score", ascending=False)
    if top.empty:
        top = summary.loc[summary["robust_pass"].eq(True)].sort_values("score", ascending=False)
    if top.empty:
        top = summary.head(20)

    report = {
        "family_id": "HYPE-5M-MA-Pullback-Scalp",
        "run_date": RUN_DATE,
        "quality": quality,
        "tested_configs": int(len(summary)),
        "base_candidates": [cfg.name for cfg in base_configs],
        "robust_pass_count": int(summary["robust_pass"].sum()),
        "monthly_pass_count": int(summary["monthly_pass"].sum()),
        "top_rows": top.head(40).to_dict(orient="records"),
        "paths": {"summary": str(SUMMARY_PATH), "monthly": str(MONTHLY_PATH), "markdown": str(MARKDOWN_PATH)},
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=module.json_default))
    MARKDOWN_PATH.write_text(render_markdown(summary, top, report))
    print(f"wrote {MARKDOWN_PATH}")
    print(f"robust_pass_count={report['robust_pass_count']} monthly_pass_count={report['monthly_pass_count']}")


def render_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    output = [
        "| base | name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{row['base_name']}` | `{row['name']}` | `{row['cfg_trigger_style']}` | `{row['cfg_side_mode']}` | "
            f"`{int(row['cfg_fast_ma'])}/{int(row['cfg_slow_ma'])}` | "
            f"`{float(row['cfg_tp_bps']):.0f}/{float(row['cfg_sl_bps']):.0f}/{int(row['cfg_max_hold_bars'])}` | "
            f"`{float(row['full_trades_per_day']):.2f}` | `{int(row['full_trades'])}` | "
            f"`{float(row['full_annualized_multiple']):.2f}x` | `{float(row['full_win_rate']) * 100:.2f}%` | "
            f"`{float(row['full_profit_factor']):.3f}` | `{float(row['full_avg_trade']) * 10000:.2f} bps` | "
            f"`{float(row['full_max_dd']) * 100:.2f}%` | `{float(row['val_next_20pct_profit_factor']):.3f}` | "
            f"`{float(row['fwd_last_20pct_profit_factor']):.3f}` | `{float(row['recent_30d_total_return']) * 100:.2f}%` | "
            f"`{int(row['negative_months'])}` |"
        )
    return output


def render_markdown(summary: pd.DataFrame, top: pd.DataFrame, report: dict[str, Any]) -> str:
    lines = [
        "# HYPE 5m MA Pullback Scalp robustness 2026-06-26",
        "",
        "Family id: `HYPE-5M-MA-Pullback-Scalp`",
        "",
        "目标：围绕第一轮通过 paper candidate gate 的两条配置做本地参数邻域复核，判断它们是否只是单点过拟合。",
        "",
        "## 固定口径",
        "",
        "- 闭合 `5m` K 信号；下一根 open 入场。",
        "- 入场即固定 TP/SL bracket；同 K 同时触及按止损先成交。",
        "- stop/target open 穿越按 open 市价成交；timeout 下一根 open 退出。",
        "- 成本沿用第一轮脚本里的 observed Binance live cost constants。",
        "",
        "## 邻域结果",
        "",
        f"- base candidates: `{report['base_candidates']}`。",
        f"- tested configs: `{report['tested_configs']}`。",
        f"- robust pass: `{report['robust_pass_count']}`。",
        f"- robust + monthly pass: `{report['monthly_pass_count']}`。",
        "",
    ]
    for base_name, group in summary.groupby("base_name", sort=False):
        lines.extend(
            [
                f"### {base_name}",
                "",
                f"- configs `{len(group)}`；robust pass `{int(group['robust_pass'].sum())}`；monthly pass `{int(group['monthly_pass'].sum())}`。",
                "",
                *render_table(group.sort_values("score", ascending=False), limit=8),
                "",
            ]
        )
    lines.extend(["## Top Robust Rows", "", *render_table(top, limit=16), ""])
    if report["monthly_pass_count"]:
        lines.extend(
            [
                "## 结论",
                "",
                "邻域复核保留了若干可推进配置；它们仍然只是 paper-audit 候选，下一步需要逐笔路径图、paper runner 和 live-runner 订单维护/重启审计。",
            ]
        )
    else:
        lines.extend(
            [
                "## 结论",
                "",
                "邻域复核没有留下稳健配置；第一轮通过行不应推进到 paper-live。",
            ]
        )
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


if __name__ == "__main__":
    main()
