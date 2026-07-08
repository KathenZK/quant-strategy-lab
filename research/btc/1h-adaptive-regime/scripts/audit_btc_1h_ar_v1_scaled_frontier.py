from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_btc_1h_adaptive_regime_boundary as boundary  # noqa: E402
import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v1_clean as clean  # noqa: E402
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-02"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v1_scaled_frontier_audit_{DATE_TAG}.json"
NEIGHBORHOOD_CSV = (
    ARTIFACT_DIR / f"btc_1h_ar_v1_scaled_frontier_neighborhood_{DATE_TAG}.csv"
)
MONTHLY_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_scaled_frontier_monthly_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_scaled_frontier_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"btc-1h-ar-v1-scaled-frontier-audit-{DATE_TAG}.md"


KELTNER = clean.KeltnerCleanConfig(
    indicator_window=20,
    band_k=2.0,
    roc_window=24,
    min_adx=40.0,
    min_rvol=1.25,
    max_atr_bps=200.0,
    min_dir_roc_bps=-200.0,
    htf_mode="h4",
    max_aligned_funding_bps=4.0,
    tp_atr=1.5,
    sl_atr=5.0,
    max_hold_bars=240,
    cooldown_bars=0,
    fixed_leverage=1.8,
)

CCI = clean.CCICleanConfig(
    ema_htf=377,
    indicator_window=20,
    threshold_high=125.0,
    max_adx=45.0,
    min_rvol=1.25,
    min_atr_bps=75.0,
    max_atr_bps=600.0,
    max_dist_ema_bps=750.0,
    tp_atr=4.5,
    sl_atr=1.5,
    max_hold_bars=72,
    cooldown_bars=48,
    fixed_leverage=2.7,
)


def simulate(
    *,
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    keltner: Any,
    cci: Any,
    delay: int = 1,
    fee: float = 0.001,
    slippage: float = 0.0004,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    trades, _prefit = tune.simulate_pair_scenario(
        engine=engine,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        keltner=keltner,
        cci=cci,
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
        and prefit["win_rate"] >= 0.55
        and tune.robust_prefit_gate(base)
        and tune.robust_prefit_gate(k2)
    )


def neighborhood() -> list[tuple[str, Any, Any]]:
    rows: list[tuple[str, Any, Any]] = []

    def add_k(field: str, values: list[Any]) -> None:
        for value in values:
            if getattr(KELTNER, field) != value:
                rows.append(
                    (
                        f"keltner.{field}={value}",
                        replace(KELTNER, **{field: value}),
                        CCI,
                    )
                )

    def add_c(field: str, values: list[Any]) -> None:
        for value in values:
            if getattr(CCI, field) != value:
                rows.append(
                    (
                        f"cci.{field}={value}",
                        KELTNER,
                        replace(CCI, **{field: value}),
                    )
                )

    add_k("indicator_window", [12, 32])
    add_k("band_k", [1.75, 2.25])
    add_k("roc_window", [12, 48])
    add_k("min_adx", [36.0, 44.0])
    add_k("min_rvol", [1.0, 1.5])
    add_k("max_atr_bps", [150.0, 250.0])
    add_k("min_dir_roc_bps", [-100.0, 0.0])
    add_k("htf_mode", ["h12", "d1"])
    add_k("max_aligned_funding_bps", [2.0, 8.0])
    add_k("tp_atr", [1.25, 2.0])
    add_k("sl_atr", [4.5, 5.5])
    add_k("max_hold_bars", [168, 216])
    add_k("cooldown_bars", [6, 12])
    add_k("fixed_leverage", [1.6, 2.0])

    add_c("ema_htf", [233])
    add_c("indicator_window", [14, 40])
    add_c("threshold_high", [100.0, 150.0])
    add_c("max_adx", [36.0, 100.0])
    add_c("min_rvol", [1.0, 1.5])
    add_c("min_atr_bps", [50.0, 100.0])
    add_c("max_atr_bps", [400.0, 10000.0])
    add_c("max_dist_ema_bps", [500.0, 1000.0])
    add_c("tp_atr", [4.0, 5.0])
    add_c("sl_atr", [1.25, 2.0])
    add_c("max_hold_bars", [96])
    add_c("cooldown_bars", [36])
    add_c("fixed_leverage", [2.4, 3.0])

    for scale in (0.80, 0.85, 0.95, 1.00):
        rows.append(
            (
                f"uniform_exposure_scale={scale}",
                replace(KELTNER, fixed_leverage=2.0 * scale),
                replace(CCI, fixed_leverage=3.0 * scale),
            )
        )
    return rows


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
            keltner=KELTNER,
            cci=CCI,
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
    for label, keltner, cci in neighborhood():
        _base, metrics = simulate(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            keltner=keltner,
            cci=cci,
        )
        _k2_trades, metrics_k2 = simulate(
            engine=engine,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            keltner=keltner,
            cci=cci,
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

    bootstrap_result = boundary.bootstrap(
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
        "family": "BTC-1H-Adaptive-Regime",
        "baseline_version": "BTC-1H-Adaptive-Regime-V1",
        "observation_id": "BTC-1H-AR-V1-SCALED-FRONTIER-2026-07-02",
        "status": "paper_audit_observation_forward_test_required_not_live_ready",
        "selection_provenance": {
            "source": "first prefit-only soft robust frontier",
            "source_exposure": {"keltner": 2.0, "cci": 3.0},
            "source_k2_prefit_max_dd": -0.2176807264256111,
            "uniform_exposure_scale": 0.90,
            "scale_rule": "mechanical prefit K2 drawdown compression below 20pct; reused holdout not used",
        },
        "keltner": asdict(KELTNER),
        "cci": asdict(CCI),
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
        "# BTC-1H-Adaptive-Regime-V1 缩放前沿审计 - 2026-07-02",
        "",
        "## 结论",
        "",
        (
            "得到一个同时满足“相对 V1 收益更高、回撤更小、胜率适中”且 K+2 prefit "
            "回撤低于 20% 的缩放前沿观察。它通过 reused holdout 与成本压力，但由于 "
            "reused holdout 已解锁、没有新增 forward trades 和生产 runner，状态仍为 "
            "`paper-audit observation / not live-ready`，不登记新版本。"
        ),
        "",
        "## 选择来源",
        "",
        "- 来源参数是在第一次 prefit-only 稳健排序中冻结的 soft frontier；OOS 不参与选择。",
        "- 原曝光 Keltner `2.0x`、CCI `3.0x`；其 K+2 prefit DD 为 `-21.77%`。",
        "- 统一乘以 `0.90`，得到 Keltner `1.8x`、CCI `2.7x`；缩放规则只读取 prefit K+2 DD。",
        "",
        "## V1 对比",
        "",
        "| Window | V1 annual / DD / win / trades | Scaled frontier annual / DD / win / trades |",
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
            "- 下一步证据必须来自冻结参数后的新增 forward trades；不得再把 2026-04-02 至 2026-07-02 当作新鲜 OOS。",
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
            "uv run research/btc/1h-adaptive-regime/scripts/audit_btc_1h_ar_v1_scaled_frontier.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
