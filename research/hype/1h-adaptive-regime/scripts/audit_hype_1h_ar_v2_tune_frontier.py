from __future__ import annotations

import json
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402


DATE_TAG = "2026-07-02"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DI_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_di_coordinate_{DATE_TAG}.csv"
STOCH_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_stoch_coordinate_{DATE_TAG}.csv"
PAIR_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_pair_ranking_{DATE_TAG}.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_frontier_audit_{DATE_TAG}.json"
STRESS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_frontier_stress_{DATE_TAG}.csv"
NEIGHBOR_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_frontier_neighbors_{DATE_TAG}.csv"
MONTHLY_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_frontier_monthly_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_tune_frontier_trades_{DATE_TAG}.csv"
REPORT_MD = (
    FAMILY_DIR
    / "diagnostics"
    / f"hype-1h-ar-v2-tune-frontier-live-audit-{DATE_TAG}.md"
)

SCENARIOS = (
    ("base_k1", 0.0010, 0.0004, 1, 1.00),
    ("delay_k2", 0.0010, 0.0004, 2, 1.00),
    ("delay_k3", 0.0010, 0.0004, 3, 1.00),
    ("slip_8bps", 0.0010, 0.0008, 1, 1.00),
    ("slip_10bps", 0.0010, 0.0010, 1, 1.00),
    ("fee12_slip8", 0.0012, 0.0008, 1, 1.00),
    ("double_cost", 0.0020, 0.0008, 1, 1.00),
    ("exposure_075x", 0.0010, 0.0004, 1, 0.75),
    ("exposure_050x", 0.0010, 0.0004, 1, 0.50),
    ("exposure_125x", 0.0010, 0.0004, 1, 1.25),
)

DI_GRIDS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (55, 89, 144, 233),
    "min_adx": (8.0, 10.0, 12.0, 14.0, 16.0, 20.0),
    "max_adx": (30.0, 32.0, 36.0, 40.0, 45.0, 55.0, 100.0),
    "min_rvol": (1.25, 1.5, 1.75, 2.0, 2.25, 2.5),
    "max_atr_bps": (200.0, 225.0, 250.0, 275.0, 300.0, 350.0, 400.0),
    "roc_window": (12, 24, 48, 72),
    "min_dir_roc_bps": (-10_000.0, -400.0, -300.0, -200.0, -100.0, 0.0, 100.0),
    "max_dist_ema_bps": (300.0, 500.0, 750.0, 1000.0, 1500.0, 2500.0),
    "htf_mode": ("none", "h4", "h12", "d1"),
    "require_body_dir": (False, True),
    "max_aligned_funding_bps": (1.0, 2.0, 4.0, 8.0, 10_000.0),
    "tp_atr": (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0),
    "sl_atr": (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0),
    "max_hold_bars": (8, 12, 15, 18, 24, 36, 48),
    "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.25, 3.5, 4.0),
}

STOCH_GRIDS: dict[str, tuple[Any, ...]] = {
    "indicator_window": (7, 14, 21, 28),
    "threshold_low": (15.0, 20.0, 25.0, 30.0, 35.0, 40.0),
    "threshold_high": (50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0),
    "ema_htf": (34, 55, 89, 144, 233),
    "min_adx": (0.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0),
    "min_rvol": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    "min_atr_bps": (100.0, 125.0, 150.0, 175.0, 200.0, 225.0, 250.0),
    "max_atr_bps": (300.0, 350.0, 400.0, 450.0, 500.0, 600.0, 10_000.0),
    "max_dist_ema_bps": (500.0, 1000.0, 1500.0, 2000.0, 2500.0, 4000.0, 10_000.0),
    "require_macd_turn": (False, True),
    "sl_atr": (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0),
    "trail_activation_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0),
    "trail_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0),
    "max_hold_bars": (4, 6, 8, 10, 12, 18, 24),
    "cooldown_bars": (0, 6, 12, 18, 24, 36, 48),
    "fixed_leverage": (1.0, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 3.5),
}


def value_from_row(value: Any, expected: Any) -> Any:
    if isinstance(expected, bool):
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)
    if isinstance(expected, int):
        return int(value)
    if isinstance(expected, float):
        return float(value)
    return value


def config_from_row(
    row: pd.Series, cls: type[v2.DICleanConfig] | type[v2.StochCleanConfig]
) -> v2.DICleanConfig | v2.StochCleanConfig:
    defaults = cls()
    values = {
        item.name: value_from_row(row[f"cfg_{item.name}"], getattr(defaults, item.name))
        for item in fields(cls)
    }
    return cls(**values)


def metric_fields(
    trades: list[base.Trade], full_end: pd.Timestamp
) -> dict[str, Any]:
    prefit = base.metrics(trades, v2.TRAIN_START, v2.PREFIT_END)
    holdout = base.metrics(trades, v2.PREFIT_END, full_end)
    full = base.metrics(trades, v2.TRAIN_START, full_end)
    output: dict[str, Any] = {}
    for prefix, values in (
        ("prefit", prefit),
        ("reused_holdout", holdout),
        ("current_full", full),
    ):
        output.update({f"{prefix}_{key}": value for key, value in values.items()})
    output["target_pass"] = base.target_gate(holdout, full)
    return output


def eligible_base_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    return pairs.loc[
        (pairs["current_full_trades"] >= base.MIN_PREFIT_TRADES)
        & (pairs["current_full_annual_multiple"] >= base.TARGET_ANNUAL_MULTIPLE)
        & (pairs["current_full_win_rate"] >= base.TARGET_WIN_RATE)
        & (pairs["current_full_max_dd"] > base.TARGET_MAX_DD)
        & (pairs["reused_holdout_trades"] >= base.MIN_HOLDOUT_TRADES)
        & (pairs["reused_holdout_annual_multiple"] >= base.TARGET_ANNUAL_MULTIPLE)
        & (pairs["reused_holdout_win_rate"] >= base.TARGET_WIN_RATE)
        & (pairs["reused_holdout_max_dd"] > base.TARGET_MAX_DD)
    ].copy()


def adjacent_values(value: Any, grid: tuple[Any, ...]) -> list[Any]:
    if value not in grid:
        return []
    index = grid.index(value)
    output: list[Any] = []
    if index > 0:
        output.append(grid[index - 1])
    if index + 1 < len(grid):
        output.append(grid[index + 1])
    return output


def monthly_rows(
    trades: list[base.Trade], start: pd.Timestamp, end: pd.Timestamp
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        month_end = min(cursor + pd.offsets.MonthBegin(1), end)
        values = base.metrics(trades, cursor, month_end)
        rows.append({"start": cursor, "end": month_end, **values})
        cursor = month_end
    return rows


def main() -> None:
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)

    di_frame = pd.read_csv(DI_CSV).set_index("config_id")
    stoch_frame = pd.read_csv(STOCH_CSV).set_index("config_id")
    pairs = pd.read_csv(PAIR_CSV)
    eligible = eligible_base_pairs(pairs)
    if eligible.empty:
        raise RuntimeError("No V2 tune pair passes the base full + reused-holdout gate")

    di_configs = {
        config_id: config_from_row(di_frame.loc[config_id], v2.DICleanConfig)
        for config_id in eligible["di_id"].unique()
    }
    stoch_configs = {
        config_id: config_from_row(stoch_frame.loc[config_id], v2.StochCleanConfig)
        for config_id in eligible["stoch_id"].unique()
    }
    component_cache: dict[tuple[str, str, str], list[base.Trade]] = {}
    stress_rows: list[dict[str, Any]] = []
    original_fee = base.FEE_PER_FILL
    original_slippage = base.SLIPPAGE_PER_FILL
    try:
        for scenario, fee, slippage, delay, exposure_scale in SCENARIOS:
            base.FEE_PER_FILL = fee
            base.SLIPPAGE_PER_FILL = slippage
            for config_id, clean in di_configs.items():
                cfg = replace(
                    v2.di_to_base(clean, config_id),
                    entry_delay_bars=delay,
                    fixed_leverage=clean.fixed_leverage * exposure_scale,
                )
                component_cache[("di", config_id, scenario)] = boundary.component_trades(
                    frame, funding_times, funding_cumulative, cfg
                )
            for config_id, clean in stoch_configs.items():
                cfg = replace(
                    v2.stoch_to_base(clean, config_id),
                    entry_delay_bars=delay,
                    fixed_leverage=clean.fixed_leverage * exposure_scale,
                )
                component_cache[("stoch", config_id, scenario)] = (
                    boundary.component_trades(
                        frame, funding_times, funding_cumulative, cfg
                    )
                )
            for pair in eligible.itertuples(index=False):
                merged = base.merge_trade_sets(
                    component_cache[("di", pair.di_id, scenario)],
                    component_cache[("stoch", pair.stoch_id, scenario)],
                    1.0,
                    0.0,
                )
                stress_rows.append(
                    {
                        "di_id": pair.di_id,
                        "stoch_id": pair.stoch_id,
                        "scenario": scenario,
                        "fee_per_fill": fee,
                        "slippage_per_fill": slippage,
                        "entry_delay_bars": delay,
                        "exposure_scale": exposure_scale,
                        **metric_fields(merged, full_end),
                    }
                )
    finally:
        base.FEE_PER_FILL = original_fee
        base.SLIPPAGE_PER_FILL = original_slippage

    stress_frame = pd.DataFrame(stress_rows)
    required_stress = {"base_k1", "delay_k2", "slip_8bps"}
    pass_counts = (
        stress_frame.loc[stress_frame["scenario"].isin(required_stress)]
        .groupby(["di_id", "stoch_id"])["target_pass"]
        .sum()
    )
    robust_pairs = pass_counts[pass_counts == len(required_stress)].index
    robust = eligible.set_index(["di_id", "stoch_id"]).loc[robust_pairs].reset_index()
    robust = robust.sort_values(
        ["current_full_annual_multiple", "current_full_max_dd"],
        ascending=False,
    )

    selected: pd.Series | None = None
    selected_di: v2.DICleanConfig | None = None
    selected_stoch: v2.StochCleanConfig | None = None
    selected_trades: list[base.Trade] = []
    neighbor_rows: list[dict[str, Any]] = []
    monthly: list[dict[str, Any]] = []
    if not robust.empty:
        selected = robust.iloc[0]
        selected_di = di_configs[str(selected["di_id"])]
        selected_stoch = stoch_configs[str(selected["stoch_id"])]
        selected_trades = base.merge_trade_sets(
            component_cache[("di", str(selected["di_id"]), "base_k1")],
            component_cache[("stoch", str(selected["stoch_id"]), "base_k1")],
            1.0,
            0.0,
        )
        monthly = monthly_rows(selected_trades, v2.TRAIN_START, full_end)

        selected_di_trades = component_cache[
            ("di", str(selected["di_id"]), "base_k1")
        ]
        selected_stoch_trades = component_cache[
            ("stoch", str(selected["stoch_id"]), "base_k1")
        ]
        for component, clean, grids in (
            ("di_cross", selected_di, DI_GRIDS),
            ("stoch_reversal", selected_stoch, STOCH_GRIDS),
        ):
            for field_name, grid in grids.items():
                baseline_value = getattr(clean, field_name)
                for value in adjacent_values(baseline_value, grid):
                    variant = replace(clean, **{field_name: value})
                    cfg = (
                        v2.di_to_base(variant, f"neighbor_{field_name}_{value}")
                        if component == "di_cross"
                        else v2.stoch_to_base(
                            variant, f"neighbor_{field_name}_{value}"
                        )
                    )
                    component_trades = boundary.component_trades(
                        frame, funding_times, funding_cumulative, cfg
                    )
                    merged = (
                        base.merge_trade_sets(
                            component_trades, selected_stoch_trades, 1.0, 0.0
                        )
                        if component == "di_cross"
                        else base.merge_trade_sets(
                            selected_di_trades, component_trades, 1.0, 0.0
                        )
                    )
                    neighbor_rows.append(
                        {
                            "component": component,
                            "field": field_name,
                            "baseline_value": baseline_value,
                            "variant_value": value,
                            **metric_fields(merged, full_end),
                        }
                    )

    neighbor_frame = pd.DataFrame(neighbor_rows)
    monthly_frame = pd.DataFrame(monthly)
    selected_stress = (
        stress_frame.loc[
            (stress_frame["di_id"] == selected["di_id"])
            & (stress_frame["stoch_id"] == selected["stoch_id"])
        ]
        if selected is not None
        else pd.DataFrame()
    )
    neighbor_summary = {
        "rows": len(neighbor_frame),
        "target_pass": int(neighbor_frame["target_pass"].sum())
        if not neighbor_frame.empty
        else 0,
        "target_pass_rate": float(neighbor_frame["target_pass"].mean())
        if not neighbor_frame.empty
        else 0.0,
        "full_dd_pass": int(
            (neighbor_frame["current_full_max_dd"] > base.TARGET_MAX_DD).sum()
        )
        if not neighbor_frame.empty
        else 0,
        "holdout_dd_pass": int(
            (neighbor_frame["reused_holdout_max_dd"] > base.TARGET_MAX_DD).sum()
        )
        if not neighbor_frame.empty
        else 0,
    }
    selected_id = (
        f"HYPE-1H-Adaptive-Regime-V2-TUNE__{selected['di_id']}__{selected['stoch_id']}"
        if selected is not None
        else None
    )
    selected_metrics = (
        metric_fields(selected_trades, full_end) if selected is not None else None
    )
    live_audit = None
    if selected is not None:
        data_payload = json.loads(
            (ARTIFACT_DIR / "hype_binance_1h_data_quality.json").read_text(
                encoding="utf-8"
            )
        )
        live_audit = boundary.live_risk_audit(
            selected_trades, data_payload["contract_snapshot"]
        )
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "audit": "V2 post-hoc tune frontier live-executable audit",
        "status": "diagnostic_observation_not_live_ready_not_promoted",
        "selection_warning": (
            "The reused holdout and current-full fields were inspected to choose this "
            "frontier observation; they are not untouched OOS evidence."
        ),
        "data_quality": quality,
        "base_target_pass_pairs": len(eligible),
        "stress_required": sorted(required_stress),
        "stress_robust_pairs": len(robust),
        "selected_id": selected_id,
        "selected_di_config": asdict(selected_di) if selected_di else None,
        "selected_stoch_config": asdict(selected_stoch) if selected_stoch else None,
        "selected_metrics": selected_metrics,
        "selected_stress": selected_stress.to_dict(orient="records"),
        "neighbor_summary": neighbor_summary,
        "monthly_summary": {
            "rows": len(monthly_frame),
            "negative_months": int((monthly_frame["total_return"] < 0.0).sum())
            if not monthly_frame.empty
            else 0,
            "worst_month": monthly_frame.sort_values("total_return")
            .iloc[0]
            .to_dict()
            if not monthly_frame.empty
            else None,
        },
        "live_executable_audit": live_audit,
        "promotion_blockers": [
            "reused holdout was inspected post-hoc and is not untouched OOS",
            "no new forward trades after parameter freeze",
            "no production runner or restart recovery",
            "no exchange order/position reconciliation or kill switch",
            "no real stop-market slippage evidence",
        ],
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    stress_frame.to_csv(STRESS_CSV, index=False)
    neighbor_frame.to_csv(NEIGHBOR_CSV, index=False)
    monthly_frame.to_csv(MONTHLY_CSV, index=False)
    pd.DataFrame(base.trade_rows(selected_trades)).to_csv(TRADES_CSV, index=False)

    lines = [
        "# HYPE-1H-Adaptive-Regime-V2 微调前沿实盘压力审计 - 2026-07-02",
        "",
        "## 结论",
        "",
        "`diagnostic observation / not live-ready / not promoted`。",
        "",
        f"基础 full + reused-holdout 三项硬门槛命中 `{len(eligible)}` 组；进一步要求 base K+1、K+2 延迟、8 bps/fill 滑点三个场景都同时满足 full 与 reused-holdout 硬门槛后，剩余 `{len(robust)}` 组。",
        "",
        f"压力门槛后的最高 current-full 年化观察为 `{selected_id}`。这一步查看了 reused holdout 与 current full，因此它是 post-hoc frontier observation，不是新的 untouched OOS 结果。",
        "",
    ]
    if selected is not None and selected_metrics is not None:
        lines.extend(
            [
                "## 核心指标",
                "",
                "| Window | Annual multiple | Max DD | Win rate | Trades |",
                "| --- | ---: | ---: | ---: | ---: |",
                f"| Prefit | `{base.mult(selected_metrics['prefit_annual_multiple'])}` | `{base.pct(selected_metrics['prefit_max_dd'])}` | `{base.pct(selected_metrics['prefit_win_rate'])}` | `{int(selected_metrics['prefit_trades'])}` |",
                f"| Reused holdout | `{base.mult(selected_metrics['reused_holdout_annual_multiple'])}` | `{base.pct(selected_metrics['reused_holdout_max_dd'])}` | `{base.pct(selected_metrics['reused_holdout_win_rate'])}` | `{int(selected_metrics['reused_holdout_trades'])}` |",
                f"| Current full | `{base.mult(selected_metrics['current_full_annual_multiple'])}` | `{base.pct(selected_metrics['current_full_max_dd'])}` | `{base.pct(selected_metrics['current_full_win_rate'])}` | `{int(selected_metrics['current_full_trades'])}` |",
                "",
                "## 成本、延迟与仓位压力",
                "",
                "| Scenario | Full ann | Full DD | Holdout ann | Holdout DD | Target pass |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in selected_stress.itertuples(index=False):
            lines.append(
                f"| `{row.scenario}` | `{base.mult(row.current_full_annual_multiple)}` | `{base.pct(row.current_full_max_dd)}` | `{base.mult(row.reused_holdout_annual_multiple)}` | `{base.pct(row.reused_holdout_max_dd)}` | `{row.target_pass}` |"
            )
        lines.extend(
            [
                "",
                "## 相邻参数稳定性",
                "",
                f"对全部 active 参数逐项测试相邻网格，共 `{neighbor_summary['rows']}` 组；full + reused-holdout 完整硬门槛命中 `{neighbor_summary['target_pass']}` 组（`{neighbor_summary['target_pass_rate']:.2%}`）。这是解锁数据后的脆弱性诊断，不用于再次选参。",
                "",
                "## Promotion 边界",
                "",
                "- 回测状态机只使用闭合 1h K；信号后 K+1 open 入场；成交后 stop 立即生效；同 K 双触发 stop-first；跳空 stop 按 open 加不利滑点；trailing 只在闭合 K 更新并从下一根生效。",
                "- 合约过滤器、历史资金费、10 bps/fill 手续费与 4 bps/fill 基础滑点已计入。",
                "- 但 reused holdout 已被查看，且还没有冻结后的新 forward trades、生产 runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 与真实 stop-market 滑点证据。",
                "- 因此该观察不能标为 candidate、paper-live、dry-run、handoff 或 live。",
                "",
            ]
        )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
