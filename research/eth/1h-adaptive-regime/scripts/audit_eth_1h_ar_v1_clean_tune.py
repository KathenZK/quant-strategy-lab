from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v1_clean as clean  # noqa: E402
import research_eth_1h_ar_v1_clean_tune as tune  # noqa: E402


FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
DATE_TAG = "2026-07-03"
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v1_clean_tune_audit_{DATE_TAG}.json"
NEIGHBORHOOD_CSV = (
    ARTIFACT_DIR / f"eth_1h_ar_v1_clean_tune_neighborhood_{DATE_TAG}.csv"
)
MONTHLY_CSV = ARTIFACT_DIR / f"eth_1h_ar_v1_clean_tune_monthly_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v1_clean_tune_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"eth-1h-ar-v1-clean-tune-audit-{DATE_TAG}.md"


BB_BREAK = clean.BBBreakCleanConfig(
    ema_htf=89,
    indicator_window=32,
    band_k=2.0,
    roc_window=48,
    min_adx=28.0,
    min_rvol=2.5,
    min_atr_bps=50.0,
    min_dir_roc_bps=-200.0,
    max_dist_ema_bps=10000.0,
    max_aligned_funding_bps=10000.0,
    tp_atr=3.0,
    sl_atr=4.0,
    max_hold_bars=48,
    fixed_leverage=2.0,
)

RSI = clean.RSICleanConfig(
    ema_htf=377,
    indicator_window=14,
    threshold_low=10.0,
    threshold_high=65.0,
    roc_window=6,
    min_adx=16.0,
    max_adx=100.0,
    min_atr_bps=100.0,
    min_dir_roc_bps=-10000.0,
    max_dist_ema_bps=1000.0,
    tp_atr=2.5,
    sl_atr=2.0,
    max_hold_bars=24,
    cooldown_bars=0,
    fixed_leverage=1.5,
)


def simulate(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    bb_break: Any,
    rsi: Any,
    delay: int = 1,
    fee: float = 0.001,
    slippage: float = 0.0004,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    trades, _prefit = tune.simulate_pair_scenario(
        engine=engine,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        bb_break=bb_break,
        rsi=rsi,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )
    return trades, v1.metrics(engine, trades)


def flattened(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def robust_prefit_improvement(
    base: dict[str, dict[str, float]],
    k2: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> bool:
    prefit = base["prefit"]
    ref = reference["prefit"]
    return bool(
        prefit["annual_multiple"] > ref["annual_multiple"]
        and prefit["max_dd"] > ref["max_dd"]
        and 0.55 <= prefit["win_rate"] <= 0.85
        and tune.robust_prefit_gate(base)
        and tune.robust_prefit_gate(k2)
    )


def neighborhood() -> list[tuple[str, Any, Any]]:
    rows: list[tuple[str, Any, Any]] = []

    def add_k(field: str, values: list[Any]) -> None:
        for value in values:
            if getattr(BB_BREAK, field) != value:
                rows.append(
                    (
                        f"bb_break.{field}={value}",
                        replace(BB_BREAK, **{field: value}),
                        RSI,
                    )
                )

    def add_c(field: str, values: list[Any]) -> None:
        for value in values:
            if getattr(RSI, field) != value:
                rows.append(
                    (
                        f"rsi.{field}={value}",
                        BB_BREAK,
                        replace(RSI, **{field: value}),
                    )
                )

    add_k("ema_htf", [55, 144])
    add_k("indicator_window", [20, 48])
    add_k("band_k", [1.75, 2.25])
    add_k("roc_window", [24, 72])
    add_k("min_adx", [24.0, 32.0])
    add_k("min_rvol", [2.0, 3.0])
    add_k("min_atr_bps", [25.0, 75.0])
    add_k("min_dir_roc_bps", [-100.0, 0.0])
    add_k("max_dist_ema_bps", [2500.0, 7500.0])
    add_k("max_aligned_funding_bps", [4.0, 8.0])
    add_k("tp_atr", [2.5, 3.5])
    add_k("sl_atr", [3.5, 4.5])
    add_k("max_hold_bars", [36, 72])
    add_k("fixed_leverage", [1.75, 2.25])

    add_c("ema_htf", [233])
    add_c("indicator_window", [9, 21])
    add_c("threshold_low", [15.0, 20.0])
    add_c("threshold_high", [60.0, 70.0])
    add_c("roc_window", [3, 12])
    add_c("min_adx", [12.0, 20.0])
    add_c("max_adx", [55.0])
    add_c("min_atr_bps", [75.0, 125.0])
    add_c("min_dir_roc_bps", [-200.0, 0.0])
    add_c("max_dist_ema_bps", [750.0, 1500.0])
    add_c("tp_atr", [2.0, 3.0])
    add_c("sl_atr", [1.5, 2.5])
    add_c("max_hold_bars", [18, 36])
    add_c("cooldown_bars", [3, 6])
    add_c("fixed_leverage", [1.25, 1.75])

    for scale in (0.80, 0.90, 1.10):
        rows.append(
            (
                f"uniform_exposure_scale={scale}",
                replace(BB_BREAK, fixed_leverage=2.0 * scale),
                replace(RSI, fixed_leverage=1.5 * scale),
            )
        )
    return rows


def bootstrap(
    trades: list[Any], *, days: float, samples: int = 10_000
) -> dict[str, Any]:
    rng = np.random.default_rng(2026070304)
    returns = np.array([trade.equity_ret for trade in trades], dtype="float64")
    maes = np.array([trade.equity_mae for trade in trades], dtype="float64")
    annual = np.empty(samples)
    drawdown = np.empty(samples)
    win_rate = np.empty(samples)
    shape = np.zeros(samples, dtype=bool)
    for sample_i in range(samples):
        indices = rng.integers(0, len(trades), size=len(trades))
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        sample_returns = returns[indices]
        for trade_ret, trade_mae in zip(
            sample_returns, maes[indices], strict=True
        ):
            trough = equity * max(0.001, 1.0 + trade_mae)
            max_dd = min(max_dd, trough / peak - 1.0)
            equity *= max(0.001, 1.0 + trade_ret)
            peak = max(peak, equity)
            max_dd = min(max_dd, equity / peak - 1.0)
        ann = equity ** (365.25 / days) if equity > 0 else 0.0
        wins = float(np.mean(sample_returns > 0))
        annual[sample_i] = ann
        drawdown[sample_i] = max_dd
        win_rate[sample_i] = wins
        shape[sample_i] = ann >= 10.0 and wins >= 0.50 and max_dd > -0.20
    return {
        "samples": samples,
        "annual_multiple_p05_p50_p95": np.quantile(
            annual, [0.05, 0.50, 0.95]
        ).tolist(),
        "max_drawdown_p05_p50_p95": np.quantile(
            drawdown, [0.05, 0.50, 0.95]
        ).tolist(),
        "win_rate_p05_p50_p95": np.quantile(
            win_rate, [0.05, 0.50, 0.95]
        ).tolist(),
        "hard_shape_hit_rate": float(np.mean(shape)),
    }


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['max_dd']:.2%}` / "
        f"`{metric['win_rate']:.2%}` / `{int(metric['trades'])}`"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    reference_trades, *_ = clean.simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    reference = v1.metrics(engine, reference_trades)

    scenario_specs = [
        ("base_k1", 1, 0.001, 0.0004),
        ("delay_k2", 2, 0.001, 0.0004),
        ("delay_k3", 3, 0.001, 0.0004),
        ("slip_8bps", 1, 0.001, 0.0008),
        ("slip_12bps", 1, 0.001, 0.0012),
        ("fee12_slip8", 1, 0.0012, 0.0008),
        ("double_cost", 1, 0.002, 0.0008),
    ]
    scenarios: list[dict[str, Any]] = []
    base_trades: list[Any] | None = None
    base_metrics: dict[str, dict[str, float]] | None = None
    for name, delay, fee, slippage in scenario_specs:
        trades, metrics = simulate(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            bb_break=BB_BREAK,
            rsi=RSI,
            delay=delay,
            fee=fee,
            slippage=slippage,
        )
        if name == "base_k1":
            base_trades = trades
            base_metrics = metrics
        scenarios.append(
            {
                "scenario": name,
                "delay": delay,
                "fee_per_fill": fee,
                "slippage_per_fill": slippage,
                "metrics": metrics,
            }
        )
    assert base_trades is not None
    assert base_metrics is not None
    k2_metrics = scenarios[1]["metrics"]

    neighborhood_rows: list[dict[str, Any]] = []
    for label, bb_break, rsi in neighborhood():
        _base, metrics = simulate(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            bb_break=bb_break,
            rsi=rsi,
        )
        _k2_trades, metrics_k2 = simulate(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            bb_break=bb_break,
            rsi=rsi,
            delay=2,
        )
        neighborhood_rows.append(
            {
                "variant": label,
                "robust_prefit_improvement": robust_prefit_improvement(
                    metrics, metrics_k2, reference
                ),
                "reused_holdout_positive": (
                    metrics["reused_holdout"]["total_return"] > 0
                    and metrics["reused_holdout"]["max_dd"] > -0.20
                    and metrics["reused_holdout"]["win_rate"] >= 0.50
                ),
                **flattened(metrics),
                **{
                    f"k2_{key}": value
                    for key, value in flattened(metrics_k2).items()
                },
            }
        )
    neighborhood_frame = pd.DataFrame(neighborhood_rows)
    neighborhood_frame.to_csv(NEIGHBORHOOD_CSV, index=False)

    monthly_rows: list[dict[str, Any]] = []
    cursor = v1.TRAIN_START
    block = 1
    while cursor < v1.FULL_END:
        end = min(cursor + pd.DateOffset(months=1), v1.FULL_END)
        monthly_rows.append(
            {
                "block": block,
                "start": cursor.isoformat(),
                "end": end.isoformat(),
                **engine.metrics(base_trades, cursor, end),
            }
        )
        cursor = end
        block += 1
    monthly_frame = pd.DataFrame(monthly_rows)
    monthly_frame.to_csv(MONTHLY_CSV, index=False)

    bootstrap_result = bootstrap(
        base_trades,
        days=(v1.FULL_END - v1.TRAIN_START).total_seconds() / 86_400.0,
    )
    pd.DataFrame(
        [
            {
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "bars_held": trade.bars_held,
                "exposure": trade.exposure,
                "equity_ret": trade.equity_ret,
                "equity_mae": trade.equity_mae,
            }
            for trade in base_trades
        ]
    ).to_csv(TRADES_CSV, index=False)

    contract = quality["fetch_metadata"]["contract_snapshot"]
    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "baseline_version": "ETH-1H-Adaptive-Regime-V1",
        "observation_id": "ETH-1H-AR-V1-CLEAN-TUNE-AUDIT-2026-07-03",
        "status": "diagnostic_tuned_observation_no_go_not_live_ready",
        "selection_provenance": {
            "source": "clean tune strict improvement plus K2 and 8bps robust score",
            "source_observation": "ETH-1H-AR-V1-CLEAN-TUNE-2026-07-03",
            "selection_uses": "train_validation_prefit_only",
            "win_rate_band": "0.55_to_0.85",
            "reused_holdout_used_for_selection": False,
        },
        "bb_break": asdict(BB_BREAK),
        "rsi": asdict(RSI),
        "reference_v1": reference,
        "base_metrics": base_metrics,
        "k2_prefit_gate": tune.robust_prefit_gate(k2_metrics),
        "scenarios": scenarios,
        "neighborhood": {
            "variants": len(neighborhood_frame),
            "robust_prefit_improvement": int(
                neighborhood_frame["robust_prefit_improvement"].sum()
            ),
            "reused_holdout_positive": int(
                neighborhood_frame["reused_holdout_positive"].sum()
            ),
        },
        "monthly": {
            "blocks": len(monthly_frame),
            "negative_blocks": int((monthly_frame["total_return"] < 0).sum()),
        },
        "bootstrap": bootstrap_result,
        "live_executable": {
            "closed_bar_next_open": True,
            "stop_first_and_gap_model": True,
            "single_position_no_pyramiding": True,
            "contract_filters_available": True,
            "production_runner_present": False,
            "restart_recovery_present": False,
            "exchange_reconciliation_present": False,
            "missing_bar_fail_closed_present": False,
            "kill_switch_present": False,
            "new_forward_trades_present": False,
        },
        "contract_snapshot": contract,
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        "# ETH-1H-Adaptive-Regime-V1 Clean 微调审计 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "得到一个在 prefit 同时满足“相对 V1 收益更高、回撤更小、胜率适中”且通过 "
            "K+2/8 bps 选择门槛的 clean tuned observation；但最近三个月 reused holdout "
            "收益仍为负，原始 10x 目标也未达到。因此状态为 "
            "`diagnostic tuned observation / NO-GO / not live-ready`，不登记新版本。"
        ),
        "",
        "## 选择来源",
        "",
        "- 参数来自 33 个 active clean 参数的 prefit-only 搜索；OOS 不参与选择。",
        "- 冻结规则要求 prefit 年化高于 V1、DD 更小、胜率位于 55%-85%，并通过 K+2 与 8 bps 稳健排序。",
        "- 最近三个月已在 V1 阶段解锁，本报告只作 reused holdout 失败审计。",
        "",
        "## V1 对比",
        "",
        "| Window | V1 annual / DD / win / trades | Clean tune annual / DD / win / trades |",
        "| --- | --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(
            f"| `{window}` | {metric_line(reference[window])} | "
            f"{metric_line(base_metrics[window])} |"
        )
    lines.extend(
        [
            "",
            "## 延迟与成本",
            "",
            "| Scenario | Prefit annual / DD / win / trades | Reused holdout annual / DD / win / trades | Current full annual / DD / win / trades |",
            "| --- | --- | --- | --- |",
        ]
    )
    for scenario in scenarios:
        metrics = scenario["metrics"]
        lines.append(
            f"| `{scenario['scenario']}` | {metric_line(metrics['prefit'])} | "
            f"{metric_line(metrics['reused_holdout'])} | "
            f"{metric_line(metrics['current_full'])} |"
        )
    lines.extend(
        [
            "",
            "## 参数邻域与序列稳健性",
            "",
            f"- one-at-a-time / exposure 邻域：`{len(neighborhood_frame)}`。",
            f"- 仍满足相对 V1 严格改善且 K+2 prefit 全窗口 gate：`{int(neighborhood_frame['robust_prefit_improvement'].sum())}`。",
            f"- reused holdout 为正、DD<20%、win>=50%：`{int(neighborhood_frame['reused_holdout_positive'].sum())}`；该数字只作复用审计，不用于选参。",
            f"- 月度块：`{len(monthly_frame)}`；负收益块：`{int((monthly_frame['total_return'] < 0).sum())}`。",
            f"- bootstrap 10,000 次 annual 5/50/95：`{bootstrap_result['annual_multiple_p05_p50_p95']}`；DD 5/50/95：`{bootstrap_result['max_drawdown_p05_p50_p95']}`。",
            "",
            "## 实盘边界",
            "",
            "- 成交状态机可表达：闭合 K、下一根 open、立即保护、stop-first、gap-open、单仓。",
            f"- 合约 tick `{contract['price_filter']['tickSize']}`、market step `{contract['market_lot_size']['stepSize']}`、min notional `{contract['min_notional']['notional']}` USDT。",
            "- 当前没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。",
            "- 最近三个月 reused holdout 收益为负；即使补齐 runner 也不能绕过该失败。",
            "- 下一步证据必须来自冻结参数后的新增 forward trades；不得再把 2026-04-03 至 2026-07-03 当作新鲜 OOS。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{NEIGHBORHOOD_CSV.name}`",
            f"- `artifacts/{MONTHLY_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/eth/1h-adaptive-regime/scripts/audit_eth_1h_ar_v1_clean_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
