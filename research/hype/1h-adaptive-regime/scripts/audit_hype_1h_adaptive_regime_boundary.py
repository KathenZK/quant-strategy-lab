from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_1h_adaptive_regime_search as base  # noqa: E402


DATE_TAG = "2026-07-01"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
REFINE_JSON = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_{DATE_TAG}.json"
REFINE_PREFIT_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_prefit_{DATE_TAG}.csv"
DATA_QUALITY_JSON = ARTIFACT_DIR / "hype_binance_1h_data_quality.json"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_adaptive_regime_boundary_audit_{DATE_TAG}.json"
STRESS_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_boundary_stress_{DATE_TAG}.csv"
ABLATION_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_boundary_ablation_{DATE_TAG}.csv"
MONTHLY_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_boundary_monthly_{DATE_TAG}.csv"
BOOTSTRAP_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_boundary_bootstrap_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"hype-1h-adaptive-regime-boundary-audit-{DATE_TAG}.md"

EXPECTED_BEST = "ENS__HYPE_1H_AR_N026857__HYPE_1H_AR_N090440"
LEFT_NAME = "HYPE_1H_AR_N026857"
RIGHT_NAME = "HYPE_1H_AR_N090440"


def load_boundary() -> tuple[
    base.StrategyConfig,
    base.StrategyConfig,
    float,
    float,
    dict[str, Any],
]:
    payload = json.loads(REFINE_JSON.read_text(encoding="utf-8"))
    if payload["best"]["name"] != EXPECTED_BEST:
        raise RuntimeError(
            f"Boundary best changed: expected {EXPECTED_BEST}, got {payload['best']['name']}"
        )
    configs = payload["retained_configs"]
    left = base.StrategyConfig(**configs[LEFT_NAME])
    right = base.StrategyConfig(**configs[RIGHT_NAME])
    prefit = pd.read_csv(REFINE_PREFIT_CSV).set_index("name")
    return (
        left,
        right,
        float(prefit.loc[LEFT_NAME, "prefit_score"]),
        float(prefit.loc[RIGHT_NAME, "prefit_score"]),
        payload,
    )


def split_times(frame: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=base.WARMUP_DAYS)
    usable = full_end - train_start
    train_end = train_start + usable * 0.55
    validation_end = train_start + usable * 0.775
    return train_start, train_end, validation_end, full_end


def component_trades(
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    cfg: base.StrategyConfig,
) -> list[base.Trade]:
    return base.simulate_trades(
        frame,
        base.build_signal(frame, cfg),
        cfg,
        funding_times,
        funding_cumulative,
    )


def ensemble_trades(
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    left: base.StrategyConfig,
    right: base.StrategyConfig,
    left_priority: float,
    right_priority: float,
) -> tuple[list[base.Trade], list[base.Trade], list[base.Trade]]:
    left_trades = component_trades(frame, funding_times, funding_cumulative, left)
    right_trades = component_trades(frame, funding_times, funding_cumulative, right)
    merged = base.merge_trade_sets(
        left_trades, right_trades, left_priority, right_priority
    )
    return merged, left_trades, right_trades


def metric_row(
    *,
    label: str,
    trades: list[base.Trade],
    train_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    full_end: pd.Timestamp,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    full = base.metrics(trades, train_start, full_end)
    holdout = base.metrics(trades, validation_end, full_end)
    row: dict[str, Any] = {"label": label}
    if extra:
        row.update(extra)
    for prefix, values in (("full", full), ("holdout", holdout)):
        for key, value in values.items():
            row[f"{prefix}_{key}"] = value
    row["full_shape_pass"] = base.shape_gate(full, min_trades=base.MIN_PREFIT_TRADES)
    row["holdout_shape_pass"] = base.shape_gate(
        holdout, min_trades=base.MIN_HOLDOUT_TRADES
    )
    row["target_pass"] = base.target_gate(holdout, full)
    return row


def cost_delay_stress(
    *,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    left: base.StrategyConfig,
    right: base.StrategyConfig,
    left_priority: float,
    right_priority: float,
    train_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    full_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    original_fee = base.FEE_PER_FILL
    original_slippage = base.SLIPPAGE_PER_FILL
    rows: list[dict[str, Any]] = []
    scenarios = [
        ("base_k1", 0.0010, 0.0004, 1, 1.0),
        ("delay_k2", 0.0010, 0.0004, 2, 1.0),
        ("delay_k3", 0.0010, 0.0004, 3, 1.0),
        ("slip_8bps", 0.0010, 0.0008, 1, 1.0),
        ("slip_10bps", 0.0010, 0.0010, 1, 1.0),
        ("fee12_slip8", 0.0012, 0.0008, 1, 1.0),
        ("double_cost", 0.0020, 0.0008, 1, 1.0),
        ("exposure_075x", 0.0010, 0.0004, 1, 0.75),
        ("exposure_050x", 0.0010, 0.0004, 1, 0.50),
        ("exposure_125x", 0.0010, 0.0004, 1, 1.25),
    ]
    try:
        for label, fee, slippage, delay, exposure_scale in scenarios:
            base.FEE_PER_FILL = fee
            base.SLIPPAGE_PER_FILL = slippage
            left_cfg = replace(
                left,
                entry_delay_bars=delay,
                fixed_leverage=left.fixed_leverage * exposure_scale,
            )
            right_cfg = replace(
                right,
                entry_delay_bars=delay,
                fixed_leverage=right.fixed_leverage * exposure_scale,
            )
            merged, _left, _right = ensemble_trades(
                frame,
                funding_times,
                funding_cumulative,
                left_cfg,
                right_cfg,
                left_priority,
                right_priority,
            )
            rows.append(
                metric_row(
                    label=label,
                    trades=merged,
                    train_start=train_start,
                    validation_end=validation_end,
                    full_end=full_end,
                    extra={
                        "fee_per_fill": fee,
                        "slippage_per_fill": slippage,
                        "entry_delay_bars": delay,
                        "exposure_scale": exposure_scale,
                    },
                )
            )
    finally:
        base.FEE_PER_FILL = original_fee
        base.SLIPPAGE_PER_FILL = original_slippage
    return rows


def add_variants(
    cfg: base.StrategyConfig,
    component: str,
    fields: dict[str, list[Any]],
) -> list[tuple[str, str, Any, base.StrategyConfig]]:
    variants: list[tuple[str, str, Any, base.StrategyConfig]] = []
    for field, values in fields.items():
        baseline = getattr(cfg, field)
        for value in values:
            if value == baseline:
                continue
            variant = replace(cfg, **{field: value})
            if variant.max_adx <= variant.min_adx:
                continue
            if variant.max_atr_bps <= variant.min_atr_bps:
                continue
            variants.append((component, field, value, variant))
    return variants


def ablation_variants(
    left: base.StrategyConfig, right: base.StrategyConfig
) -> list[tuple[str, str, Any, base.StrategyConfig]]:
    left_fields: dict[str, list[Any]] = {
        "side_mode": ["long", "short"],
        "min_adx": [0.0, 8.0, 16.0, 20.0, 24.0],
        "max_adx": [28.0, 32.0, 40.0, 45.0, 100.0],
        "min_rvol": [0.0, 1.0, 1.5, 1.75, 2.25],
        "max_atr_bps": [200.0, 225.0, 300.0, 400.0, 10_000.0],
        "min_dir_roc_bps": [-10_000.0, -300.0, -100.0, 0.0, 100.0],
        "roc_window": [12, 48, 72],
        "max_dist_ema_bps": [300.0, 500.0, 1_000.0, 1_500.0, 10_000.0],
        "ema_htf": [55, 144, 233, 377],
        "htf_mode": ["none", "h4", "d1"],
        "require_body_dir": [False],
        "max_aligned_funding_bps": [1.0, 2.0, 4.0, 10_000.0],
        "tp_atr": [0.75, 1.0, 1.25, 1.75, 2.0, 2.5, 3.0],
        "sl_atr": [2.5, 3.0, 3.5, 4.5, 5.0, 6.0],
        "max_hold_bars": [8, 12, 15, 24, 36, 48],
        "cooldown_bars": [3, 6, 12, 24],
        "fixed_leverage": [1.5, 2.0, 2.5, 3.5, 4.0, 5.0],
    }
    right_fields: dict[str, list[Any]] = {
        "side_mode": ["long", "short"],
        "indicator_window": [7, 14, 28],
        "threshold_low": [15.0, 20.0, 30.0, 35.0, 40.0],
        "threshold_high": [55.0, 65.0, 70.0, 75.0, 80.0],
        "min_adx": [0.0, 8.0, 16.0, 20.0, 24.0],
        "min_rvol": [0.0, 0.6, 0.8, 1.25, 1.5, 2.0],
        "min_atr_bps": [0.0, 100.0, 150.0, 175.0, 225.0, 250.0],
        "max_atr_bps": [300.0, 350.0, 450.0, 600.0, 10_000.0],
        "max_dist_ema_bps": [500.0, 1_000.0, 1_500.0, 2_000.0, 10_000.0],
        "ema_htf": [89, 144, 233, 377],
        "require_macd_turn": [False],
        "sl_atr": [2.5, 3.0, 3.5, 4.5, 5.0, 6.0],
        "trail_activation_atr": [0.5, 0.75, 1.25, 1.5, 2.0, 3.0],
        "trail_atr": [0.5, 0.75, 1.25, 1.5, 2.0, 2.5, 3.0],
        "max_hold_bars": [4, 6, 10, 12, 18, 24],
        "cooldown_bars": [0, 6, 12, 18, 36, 48],
        "fixed_leverage": [1.0, 1.5, 1.75, 2.25, 2.5, 3.0, 4.0],
    }
    return add_variants(left, "di_cross", left_fields) + add_variants(
        right, "stoch_reversal", right_fields
    )


def run_ablation(
    *,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    left: base.StrategyConfig,
    right: base.StrategyConfig,
    left_priority: float,
    right_priority: float,
    train_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    full_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    baseline, left_base, right_base = ensemble_trades(
        frame,
        funding_times,
        funding_cumulative,
        left,
        right,
        left_priority,
        right_priority,
    )
    rows.append(
        metric_row(
            label="baseline_ensemble",
            trades=baseline,
            train_start=train_start,
            validation_end=validation_end,
            full_end=full_end,
            extra={"component": "ensemble", "field": "baseline", "value": "baseline"},
        )
    )
    rows.append(
        metric_row(
            label="ablate_stoch_keep_di",
            trades=left_base,
            train_start=train_start,
            validation_end=validation_end,
            full_end=full_end,
            extra={"component": "ensemble", "field": "leg", "value": "di_only"},
        )
    )
    rows.append(
        metric_row(
            label="ablate_di_keep_stoch",
            trades=right_base,
            train_start=train_start,
            validation_end=validation_end,
            full_end=full_end,
            extra={"component": "ensemble", "field": "leg", "value": "stoch_only"},
        )
    )
    for component, field, value, variant in ablation_variants(left, right):
        if component == "di_cross":
            merged, _left, _right = ensemble_trades(
                frame,
                funding_times,
                funding_cumulative,
                variant,
                right,
                left_priority,
                right_priority,
            )
        else:
            merged, _left, _right = ensemble_trades(
                frame,
                funding_times,
                funding_cumulative,
                left,
                variant,
                left_priority,
                right_priority,
            )
        rows.append(
            metric_row(
                label=f"{component}__{field}__{value}",
                trades=merged,
                train_start=train_start,
                validation_end=validation_end,
                full_end=full_end,
                extra={"component": component, "field": field, "value": value},
            )
        )
    return rows


def monthly_rows(
    trades: list[base.Trade], start: pd.Timestamp, end: pd.Timestamp
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start.floor("D").replace(day=1)
    while cursor < end:
        right = cursor + pd.offsets.MonthBegin(1)
        rows.append(
            {
                "month": cursor.strftime("%Y-%m"),
                "start": cursor,
                "end": min(right, end),
                **base.metrics(trades, max(cursor, start), min(right, end)),
            }
        )
        cursor = right
    return rows


def bootstrap_rows(
    trades: list[base.Trade], days: float, *, seed: int = 2026070103
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    returns = [trade.equity_ret for trade in trades]
    maes = [trade.equity_mae for trade in trades]
    rows: list[dict[str, Any]] = []
    for run in range(10_000):
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        wins = 0
        for _ in range(len(returns)):
            index = rng.randrange(len(returns))
            trough = equity * max(0.001, 1.0 + maes[index])
            max_dd = min(max_dd, trough / peak - 1.0)
            value = returns[index]
            wins += value > 0.0
            equity *= max(0.001, 1.0 + value)
            peak = max(peak, equity)
            max_dd = min(max_dd, equity / peak - 1.0)
        annual = equity ** (365.25 / days)
        rows.append(
            {
                "run": run,
                "final_equity": equity,
                "annual_multiple": annual,
                "max_dd": max_dd,
                "win_rate": wins / len(returns),
                "shape_pass": (
                    annual >= base.TARGET_ANNUAL_MULTIPLE
                    and max_dd > base.TARGET_MAX_DD
                    and wins / len(returns) >= base.TARGET_WIN_RATE
                ),
            }
        )
    return rows


def live_risk_audit(
    trades: list[base.Trade], contract: dict[str, Any]
) -> dict[str, Any]:
    atr_bps = np.array([trade.signal_atr_bps for trade in trades], dtype=float)
    stop_distance = np.array(
        [
            trade.signal_atr_bps * (4.0 if trade.config in {LEFT_NAME, RIGHT_NAME} else 4.0)
            for trade in trades
        ],
        dtype=float,
    )
    return {
        "tick_size": contract["price_filter"]["tickSize"],
        "quantity_step": contract["lot_size"]["stepSize"],
        "market_min_qty": contract["market_lot_size"]["minQty"],
        "min_notional": contract["min_notional"]["notional"],
        "max_strategy_exposure": float(max(trade.exposure for trade in trades)),
        "max_signal_atr_bps": float(atr_bps.max()),
        "max_initial_stop_distance_bps": float(stop_distance.max()),
        "initial_stop_over_15pct_count": int((stop_distance > 1_500.0).sum()),
        "gap_stop_model": "crossed stop fills at bar open plus adverse slippage",
        "same_bar_conflict": "stop_first",
        "trailing_update": "closed_bar_update_effective_next_bar",
        "restart_recovery_implemented": False,
        "missing_bar_fail_closed_implemented": False,
        "exchange_reconciliation_implemented": False,
        "kill_switch_implemented": False,
        "production_runner_exists": False,
    }


def markdown_report(
    *,
    baseline: dict[str, Any],
    stress: list[dict[str, Any]],
    ablation: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
    bootstrap_summary: dict[str, Any],
    live_audit: dict[str, Any],
) -> str:
    stress_map = {row["label"]: row for row in stress}
    full = {key.removeprefix("full_"): value for key, value in baseline.items() if key.startswith("full_")}
    holdout = {
        key.removeprefix("holdout_"): value
        for key, value in baseline.items()
        if key.startswith("holdout_")
    }
    pass_ablation = sum(row["target_pass"] for row in ablation)
    negative_months = sum(row["total_return"] < 0.0 for row in monthly)
    lines = [
        "# HYPE-1H-Adaptive-Regime 边界组合严格审计 - 2026-07-01",
        "",
        "## 最终结论",
        "",
        "`NO-GO / not live-ready / not promoted`。",
        "",
        f"边界组合 full 年化倍率 `{base.mult(full['annual_multiple'])}`，低于 `10.0x`；locked holdout 仅 `{base.mult(holdout['annual_multiple'])}`。虽然 full 胜率 `{base.pct(full['win_rate'])}`、回撤 `{base.pct(full['max_dd'])}` 仍在线内，但三项硬门槛没有同时通过。",
        "",
        "更关键的是，这个结果处在回撤边界：基础 holdout DD 已到 "
        f"`{base.pct(holdout['max_dd'])}`，没有给 stop-market 跳空、成本漂移或状态恢复失败留下安全垫。",
        "",
        "## 冻结规则摘要",
        "",
        "- `DI-cross` 腿：`+DI14/-DI14` cross，12h EMA regime、RVOL/ADX/ATR/24h momentum/body/funding 过滤；`TP=1.5 ATR14`、`SL=4 ATR14`、`18h` timeout、固定 `3x`。",
        "- `Stoch-reversal` 腿：Stoch(21) K/D 在 `<=25` / `>=60` 区域反转，MACD(8,21,5) turn、ATR/RVOL/ADX/distance 过滤；`SL=4 ATR14`、activation `1 ATR14`、trail `1 ATR14`、`8h` timeout、`24h` cooldown、固定 `2x`。",
        "- 同时触发/持仓重叠时按 prefit 排名确定优先级；单仓，不加仓。",
        "- 费用 `10 bps/fill`、滑点 `4 bps/fill`，逐笔资金费；closed bar 信号，下一根 open 入场。",
        "",
        "## 延迟与成本压力",
        "",
        "| Scenario | Full ann | Full DD | Full win | Holdout ann | Holdout DD | Pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in (
        "base_k1",
        "delay_k2",
        "delay_k3",
        "slip_8bps",
        "slip_10bps",
        "fee12_slip8",
        "double_cost",
        "exposure_075x",
        "exposure_050x",
        "exposure_125x",
    ):
        row = stress_map[label]
        lines.append(
            f"| `{label}` | `{base.mult(row['full_annual_multiple'])}` | `{base.pct(row['full_max_dd'])}` | `{base.pct(row['full_win_rate'])}` | `{base.mult(row['holdout_annual_multiple'])}` | `{base.pct(row['holdout_max_dd'])}` | `{row['target_pass']}` |"
        )
    lines.extend(
        [
            "",
            "## 消融与邻域",
            "",
            f"- 单腿拆分及所有 active-field one-at-a-time variants 共 `{len(ablation)}` 行；完整 target pass 为 `{pass_ablation}`。",
            "- 这些变体在 holdout 解锁后只作脆弱性诊断，不用于回头挑参数。",
            "",
            "## 月度与 bootstrap",
            "",
            f"- 月度块 `{len(monthly)}` 个，负收益月 `{negative_months}` 个。",
            f"- 交易序列 bootstrap `10,000` 次：annual 5/50/95 分位 `{bootstrap_summary['annual_q05']:.2f}x / {bootstrap_summary['annual_q50']:.2f}x / {bootstrap_summary['annual_q95']:.2f}x`；DD 5% 分位 `{bootstrap_summary['dd_q05']:.2%}`；完整形状命中率 `{bootstrap_summary['shape_pass_rate']:.2%}`。",
            "- bootstrap 只重排/重采样已发生交易，不能替代新的时间外市场，因此不用于 promotion。",
            "",
            "## 实盘可执行审计",
            "",
            f"- 合约 tick `{live_audit['tick_size']}`、qty step `{live_audit['quantity_step']}`、min notional `{live_audit['min_notional']} USDT`；最大名义暴露 `{live_audit['max_strategy_exposure']:.1f}x`。",
            f"- 历史信号最大初始 stop 距离约 `{live_audit['max_initial_stop_distance_bps']:.1f} bps`；超过 `15%` 的次数 `{live_audit['initial_stop_over_15pct_count']}`。",
            "- backtest 已处理 stop gap-open、同 K stop-first、trailing 仅闭合 K 更新；这些是必要条件，不等于生产系统已完成。",
            "- 当前没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。",
            "",
            "因此即使把 full `9.73x` 四舍五入成 `10x`，也不能实盘：精确门槛未过，holdout 未过，风险缓冲不足，生产状态机也不存在。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    left, right, left_priority, right_priority, source_payload = load_boundary()
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    train_start, train_end, validation_end, full_end = split_times(frame)
    merged, left_trades, right_trades = ensemble_trades(
        frame,
        funding_times,
        funding_cumulative,
        left,
        right,
        left_priority,
        right_priority,
    )
    baseline = metric_row(
        label="baseline_ensemble",
        trades=merged,
        train_start=train_start,
        validation_end=validation_end,
        full_end=full_end,
    )
    stress = cost_delay_stress(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        left=left,
        right=right,
        left_priority=left_priority,
        right_priority=right_priority,
        train_start=train_start,
        validation_end=validation_end,
        full_end=full_end,
    )
    ablation = run_ablation(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        left=left,
        right=right,
        left_priority=left_priority,
        right_priority=right_priority,
        train_start=train_start,
        validation_end=validation_end,
        full_end=full_end,
    )
    monthly = monthly_rows(merged, train_start, full_end)
    days = (full_end - train_start).total_seconds() / 86_400.0
    bootstrap = bootstrap_rows(merged, days)
    bootstrap_frame = pd.DataFrame(bootstrap)
    bootstrap_summary = {
        "runs": len(bootstrap),
        "annual_q05": float(bootstrap_frame["annual_multiple"].quantile(0.05)),
        "annual_q50": float(bootstrap_frame["annual_multiple"].quantile(0.50)),
        "annual_q95": float(bootstrap_frame["annual_multiple"].quantile(0.95)),
        "dd_q05": float(bootstrap_frame["max_dd"].quantile(0.05)),
        "dd_q50": float(bootstrap_frame["max_dd"].quantile(0.50)),
        "shape_pass_rate": float(bootstrap_frame["shape_pass"].mean()),
    }
    contract_payload = json.loads(DATA_QUALITY_JSON.read_text(encoding="utf-8"))
    live_audit = live_risk_audit(
        merged, contract_payload["contract_snapshot"]
    )
    stress_frame = pd.DataFrame(stress)
    ablation_frame = pd.DataFrame(ablation)
    monthly_frame = pd.DataFrame(monthly)
    stress_frame.to_csv(STRESS_CSV, index=False)
    ablation_frame.to_csv(ABLATION_CSV, index=False)
    monthly_frame.to_csv(MONTHLY_CSV, index=False)
    bootstrap_frame.to_csv(BOOTSTRAP_CSV, index=False)
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "status": "no_go_not_live_ready_not_promoted",
        "source_boundary": EXPECTED_BEST,
        "source_search_status": source_payload["status"],
        "data_quality": quality,
        "components": {LEFT_NAME: asdict(left), RIGHT_NAME: asdict(right)},
        "component_trade_counts": {
            LEFT_NAME: len(left_trades),
            RIGHT_NAME: len(right_trades),
            "merged": len(merged),
        },
        "baseline": baseline,
        "stress": stress,
        "ablation_summary": {
            "rows": len(ablation),
            "target_pass": int(ablation_frame["target_pass"].sum()),
            "full_shape_pass": int(ablation_frame["full_shape_pass"].sum()),
            "holdout_shape_pass": int(ablation_frame["holdout_shape_pass"].sum()),
        },
        "monthly_summary": {
            "rows": len(monthly),
            "negative_months": int((monthly_frame["total_return"] < 0.0).sum()),
            "worst_month": monthly_frame.sort_values("total_return").iloc[0].to_dict(),
        },
        "bootstrap_summary": bootstrap_summary,
        "live_executable_audit": live_audit,
        "promotion_blockers": [
            "full annual multiple below 10x",
            "locked holdout annual multiple below 10x",
            "holdout drawdown has almost no margin below 20%",
            "no production runner or restart recovery",
            "no exchange reconciliation or kill switch",
            "no real stop-market slippage evidence",
        ],
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        markdown_report(
            baseline=baseline,
            stress=stress,
            ablation=ablation,
            monthly=monthly,
            bootstrap_summary=bootstrap_summary,
            live_audit=live_audit,
        ),
        encoding="utf-8",
    )
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
