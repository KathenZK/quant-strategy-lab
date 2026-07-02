from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
SEARCH_SCRIPT = SCRIPT_DIR / "research_btc_1h_adaptive_regime_search.py"
SEARCH_JSON = ARTIFACT_DIR / "btc_1h_adaptive_regime_search_2026-07-02.json"
AUDIT_JSON = ARTIFACT_DIR / "btc_1h_adaptive_regime_boundary_audit_2026-07-02.json"
SCENARIOS_CSV = ARTIFACT_DIR / "btc_1h_adaptive_regime_audit_scenarios_2026-07-02.csv"
NEIGHBORHOOD_CSV = ARTIFACT_DIR / "btc_1h_adaptive_regime_neighborhood_2026-07-02.csv"
MONTHLY_CSV = ARTIFACT_DIR / "btc_1h_adaptive_regime_monthly_2026-07-02.csv"
AUDIT_MD = DIAGNOSTIC_DIR / "btc-1h-adaptive-regime-boundary-audit-2026-07-02.md"
QUALITY_MD = DIAGNOSTIC_DIR / "btc-binance-1h-data-quality-2026-07-02.md"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metric_row(prefix: str, metric: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metric.items()}


def hard_gate(metric: dict[str, float], *, min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= 10.0
        and metric["win_rate"] >= 0.50
        and metric["max_dd"] > -0.20
    )


def simulate_ensemble(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    configs: list[Any],
    *,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    delay: int = 1,
    fee: float = 0.001,
    slippage: float = 0.0004,
) -> tuple[list[Any], list[list[Any]], list[float]]:
    original_fee = engine.FEE_PER_FILL
    original_slippage = engine.SLIPPAGE_PER_FILL
    engine.FEE_PER_FILL = fee
    engine.SLIPPAGE_PER_FILL = slippage
    try:
        delayed = [replace(cfg, entry_delay_bars=delay) for cfg in configs]
        legs: list[list[Any]] = []
        priorities: list[float] = []
        for cfg in delayed:
            trades = engine.simulate_trades(
                frame,
                engine.build_signal(frame, cfg),
                cfg,
                funding_times,
                funding_cumulative,
            )
            legs.append(trades)
            train = engine.metrics(trades, train_start, train_end)
            validation = engine.metrics(trades, train_end, oos_start)
            prefit = engine.metrics(trades, train_start, oos_start)
            priorities.append(engine.prefit_score(train, validation, prefit))
        merged = engine.merge_trade_sets(
            legs[0], legs[1], priorities[0], priorities[1]
        )
        return merged, legs, priorities
    finally:
        engine.FEE_PER_FILL = original_fee
        engine.SLIPPAGE_PER_FILL = original_slippage


def scale_trades(trades: list[Any], scale: float) -> list[Any]:
    return [
        replace(
            trade,
            exposure=trade.exposure * scale,
            equity_ret=trade.equity_ret * scale,
            equity_mae=trade.equity_mae * scale,
        )
        for trade in trades
    ]


def evaluate(
    engine: Any,
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    oos_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> dict[str, Any]:
    prefit = engine.metrics(trades, train_start, oos_start)
    oos = engine.metrics(trades, oos_start, full_end)
    full = engine.metrics(trades, train_start, full_end)
    return {
        **metric_row("prefit", prefit),
        **metric_row("oos", oos),
        **metric_row("full", full),
        "prefit_gate": hard_gate(prefit, min_trades=40),
        "oos_gate": hard_gate(oos, min_trades=12),
        "full_gate": hard_gate(full, min_trades=40),
        "joint_gate": hard_gate(prefit, min_trades=40)
        and hard_gate(oos, min_trades=12)
        and hard_gate(full, min_trades=40),
    }


def neighborhood_configs(engine: Any, configs: list[Any]) -> list[tuple[str, list[Any]]]:
    variants: list[tuple[str, list[Any]]] = []

    def add(leg: int, field: str, values: list[Any]) -> None:
        base = configs[leg]
        for value in values:
            if getattr(base, field) == value:
                continue
            updated = list(configs)
            updated[leg] = replace(base, **{field: value})
            variants.append((f"leg{leg + 1}.{field}={value}", updated))

    add(0, "indicator_window", [12, 20, 32])
    add(0, "band_k", [2.0, 2.25, 2.75, 3.0])
    add(0, "min_adx", [28.0, 32.0, 40.0])
    add(0, "min_rvol", [0.6, 1.0, 1.25])
    add(0, "max_atr_bps", [150.0, 250.0, 300.0])
    add(0, "min_dir_roc_bps", [-100.0, -50.0, 50.0, 100.0])
    add(0, "htf_mode", ["none", "h12"])
    add(0, "max_aligned_funding_bps", [1.0, 4.0, 8.0])
    add(0, "tp_atr", [1.0, 1.25, 2.0, 2.5])
    add(0, "sl_atr", [3.0, 3.5, 4.5, 5.0])
    add(0, "max_hold_bars", [72, 96, 168])
    add(0, "cooldown_bars", [0, 3, 12])
    add(0, "fixed_leverage", [2.5, 3.5])

    add(1, "indicator_window", [14, 40])
    add(1, "threshold_high", [100.0, 150.0])
    add(1, "min_rvol", [1.0, 1.25, 2.0])
    add(1, "min_atr_bps", [0.0, 75.0, 100.0])
    add(1, "max_atr_bps", [250.0, 400.0, 600.0])
    add(1, "max_dist_ema_bps", [750.0, 1500.0, 2500.0])
    add(1, "tp_atr", [3.0, 3.5, 4.5, 5.0])
    add(1, "sl_atr", [0.75, 1.0, 1.5, 2.0])
    add(1, "max_hold_bars", [72, 120, 168])
    add(1, "cooldown_bars", [12, 36, 48])
    add(1, "fixed_leverage", [3.0, 3.5, 4.5])
    return variants


def bootstrap(
    trades: list[Any], *, days: float, samples: int = 10_000
) -> dict[str, Any]:
    rng = np.random.default_rng(20260702)
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


def fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def fmt_mult(value: float) -> str:
    return f"{value:.2f}x"


def write_quality_report(quality: dict[str, Any]) -> None:
    fetched = quality["fetch_metadata"]
    data = fetched["data_quality"]
    funding = fetched["funding"]
    checksum = fetched["checksum"]
    lines = [
        "# BTCUSDT Binance 永续 1h 数据质量报告 - 2026-07-02",
        "",
        "## 结论",
        "",
        "`PASS`。本次研究使用的最近两年闭合 K 无缺口、无重复、无关键空值、无 OHLC 约束违规，raw 与 normalized 数值逐列一致。",
        "",
        "## 数据身份",
        "",
        f"- 市场：`{fetched['market']}`。",
        f"- 合约：`{fetched['symbol']}` / `{fetched['display_symbol']}`。",
        f"- 周期：`{fetched['timeframe']}`。",
        f"- UTC：`{data['first_ts']}` 至 `{data['last_ts']}`。",
        f"- 闭合 K：`{data['rows_closed_normalized']}` 根；理论连续行数：`{data['expected_rows_between_endpoints']}`。",
        "",
        "## 硬质量检查",
        "",
        f"- missing bars：`{data['missing_bars']}`。",
        f"- duplicate raw/normalized：`{data['duplicate_raw']}` / `{data['duplicate_normalized']}`。",
        f"- critical nulls：`{json.dumps(data['critical_nulls'], ensure_ascii=False)}`。",
        f"- OHLCV violations：`{json.dumps(data['ohlcv_violations'], ensure_ascii=False)}`。",
        f"- raw/normalized mismatch：`{json.dumps(data['raw_normalized_mismatch'], ensure_ascii=False)}`。",
        f"- blocker count：`{data['blocker_count']}`。",
        "",
        "## 资金费与合约快照",
        "",
        f"- funding：`{funding['rows']}` 行，`{funding['first_ts']}` 至 `{funding['last_ts']}`，null=`{funding['null_rates']}`。",
        f"- 合约状态：`{fetched['contract_snapshot']['status']}`；tickSize=`{fetched['contract_snapshot']['price_filter']['tickSize']}`，market stepSize=`{fetched['contract_snapshot']['market_lot_size']['stepSize']}`，min notional=`{fetched['contract_snapshot']['min_notional']['notional']}` USDT。",
        "",
        "## 校验值",
        "",
        f"- close sum：`{checksum['close_sum']}`。",
        f"- volume sum：`{checksum['volume_sum']}`。",
        f"- quote volume sum：`{checksum['quote_volume_sum']}`。",
        f"- trade count sum：`{checksum['trade_count_sum']}`。",
        "",
    ]
    QUALITY_MD.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_MD.write_text("\n".join(lines), encoding="utf-8")


def write_audit_report(
    *,
    baseline: dict[str, Any],
    scenarios: pd.DataFrame,
    neighborhood: pd.DataFrame,
    monthly: pd.DataFrame,
    bootstrap_result: dict[str, Any],
    configs: list[Any],
    contract: dict[str, Any],
) -> None:
    oos = {key.removeprefix("oos_"): value for key, value in baseline.items() if key.startswith("oos_")}
    full = {key.removeprefix("full_"): value for key, value in baseline.items() if key.startswith("full_")}
    negative_months = int((monthly["total_return"] < 0).sum())
    lines = [
        "# BTC-1H-Adaptive-Regime 冻结边界与实盘可执行审计 - 2026-07-02",
        "",
        "## 最终结论",
        "",
        "`NO-GO / not promoted / not live-ready`。",
        "",
        "30 万组搜索的 prefit 冻结冠军没有达到 `10x` 年化门槛；最近三个月 locked OOS 更出现明显反转：年化倍率低于 `1x`、胜率低于 `50%`、回撤超过 `20%`。因此不存在可登记、可交接或可实盘的版本。",
        "",
        "## 冻结冠军",
        "",
        f"- ensemble：`{configs[0].name}` + `{configs[1].name}`。",
        f"- prefit：annual `{fmt_mult(baseline['prefit_annual_multiple'])}`，DD `{fmt_pct(baseline['prefit_max_dd'])}`，win `{fmt_pct(baseline['prefit_win_rate'])}`，trades `{int(baseline['prefit_trades'])}`。",
        f"- locked OOS：annual `{fmt_mult(oos['annual_multiple'])}`，return `{fmt_pct(oos['total_return'])}`，DD `{fmt_pct(oos['max_dd'])}`，win `{fmt_pct(oos['win_rate'])}`，trades `{int(oos['trades'])}`。",
        f"- full：annual `{fmt_mult(full['annual_multiple'])}`，return `{fmt_pct(full['total_return'])}`，DD `{fmt_pct(full['max_dd'])}`，win `{fmt_pct(full['win_rate'])}`，trades `{int(full['trades'])}`。",
        "",
        "## 延迟、成本与仓位压力",
        "",
        "| Scenario | Full ann | Full DD | Full win | OOS ann | OOS DD | OOS win | Joint gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in scenarios.to_dict("records"):
        lines.append(
            f"| `{row['scenario']}` | `{fmt_mult(row['full_annual_multiple'])}` | `{fmt_pct(row['full_max_dd'])}` | `{fmt_pct(row['full_win_rate'])}` | `{fmt_mult(row['oos_annual_multiple'])}` | `{fmt_pct(row['oos_max_dd'])}` | `{fmt_pct(row['oos_win_rate'])}` | `{row['joint_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## 参数邻域",
            "",
            f"- one-at-a-time 变体：`{len(neighborhood)}`。",
            f"- prefit/full/OOS 联合通过：`{int(neighborhood['joint_gate'].sum())}`。",
            f"- OOS 回撤仍小于 20% 的变体：`{int((neighborhood['oos_max_dd'] > -0.20).sum())}`；这不代表收益门槛通过。",
            "- 邻域只用于脆弱性审计，OOS 已解锁后不得据此回头挑参数。",
            "",
            "## 月度与 bootstrap",
            "",
            f"- 月度块：`{len(monthly)}`，负收益月：`{negative_months}`。",
            f"- bootstrap `{bootstrap_result['samples']}` 次：annual 5/50/95 分位 `{bootstrap_result['annual_multiple_p05_p50_p95']}`；DD 5/50/95 分位 `{bootstrap_result['max_drawdown_p05_p50_p95']}`；三项硬形状命中率 `{bootstrap_result['hard_shape_hit_rate']:.2%}`。",
            "- bootstrap 只能重采样已发生交易，不能修复真实 OOS 失败。",
            "",
            "## 实盘可执行审计",
            "",
            "- 成交模型可在线表达：闭合 K 信号、下一根 open 市价、入场即有 stop/TP、stop-first、gap-open、单仓不加仓。",
            f"- 合约过滤器：tickSize `{contract['price_filter']['tickSize']}`，market stepSize `{contract['market_lot_size']['stepSize']}`，min notional `{contract['min_notional']['notional']}` USDT。",
            "- 研究仓库当前没有 BTC production runner、交易所订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch 与真实 stop-market 滑点证据。",
            "- 即使补齐 runner，也不能绕过策略本身的 locked OOS 失败；因此不生成 live spec，不登记 V1。",
            "",
            "## 证据",
            "",
            f"- `{AUDIT_JSON.relative_to(ROOT)}`",
            f"- `{SCENARIOS_CSV.relative_to(ROOT)}`",
            f"- `{NEIGHBORHOOD_CSV.relative_to(ROOT)}`",
            f"- `{MONTHLY_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    search = load_module(SEARCH_SCRIPT, "btc_1h_search_wrapper")
    engine = search.load_engine()
    frame, funding, quality = search.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    summary = json.loads(SEARCH_JSON.read_text(encoding="utf-8"))
    config_names = summary["best"]["config_names"].split("+")
    configs = [
        engine.StrategyConfig(**summary["best_configs"][name])
        for name in config_names
    ]
    split = summary["split"]
    train_start = pd.Timestamp(split["train_start"])
    train_end = pd.Timestamp(split["train_end"])
    oos_start = pd.Timestamp(split["oos_start"])
    full_end = pd.Timestamp(split["full_end"])

    base_trades, base_legs, priorities = simulate_ensemble(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        configs,
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
    )
    scenario_specs = [
        ("base_k1", 1, 0.001, 0.0004, 1.0),
        ("delay_k2", 2, 0.001, 0.0004, 1.0),
        ("delay_k3", 3, 0.001, 0.0004, 1.0),
        ("slip_8bps", 1, 0.001, 0.0008, 1.0),
        ("slip_12bps", 1, 0.001, 0.0012, 1.0),
        ("fee12_slip8", 1, 0.0012, 0.0008, 1.0),
        ("double_cost", 1, 0.002, 0.0008, 1.0),
        ("exposure_050x", 1, 0.001, 0.0004, 0.5),
        ("exposure_075x", 1, 0.001, 0.0004, 0.75),
        ("exposure_125x", 1, 0.001, 0.0004, 1.25),
    ]
    scenario_rows: list[dict[str, Any]] = []
    for name, delay, fee, slip, scale in scenario_specs:
        if name.startswith("exposure_"):
            trades = scale_trades(base_trades, scale)
        else:
            trades, _legs, _priority = simulate_ensemble(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                configs,
                train_start=train_start,
                train_end=train_end,
                oos_start=oos_start,
                delay=delay,
                fee=fee,
                slippage=slip,
            )
        scenario_rows.append(
            {
                "scenario": name,
                "delay": delay,
                "fee_per_fill": fee,
                "slippage_per_fill": slip,
                "exposure_scale": scale,
                **evaluate(
                    engine,
                    trades,
                    train_start=train_start,
                    oos_start=oos_start,
                    full_end=full_end,
                ),
            }
        )
    for leg_i, leg_trades in enumerate(base_legs, start=1):
        scenario_rows.append(
            {
                "scenario": f"leg_{leg_i}_only",
                "delay": 1,
                "fee_per_fill": 0.001,
                "slippage_per_fill": 0.0004,
                "exposure_scale": 1.0,
                **evaluate(
                    engine,
                    leg_trades,
                    train_start=train_start,
                    oos_start=oos_start,
                    full_end=full_end,
                ),
            }
        )
    scenarios = pd.DataFrame(scenario_rows)
    scenarios.to_csv(SCENARIOS_CSV, index=False)
    baseline = scenario_rows[0]

    neighborhood_rows: list[dict[str, Any]] = []
    for label, variant_configs in neighborhood_configs(engine, configs):
        trades, _legs, _priorities = simulate_ensemble(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            variant_configs,
            train_start=train_start,
            train_end=train_end,
            oos_start=oos_start,
        )
        neighborhood_rows.append(
            {
                "variant": label,
                **evaluate(
                    engine,
                    trades,
                    train_start=train_start,
                    oos_start=oos_start,
                    full_end=full_end,
                ),
            }
        )
    neighborhood = pd.DataFrame(neighborhood_rows)
    neighborhood.to_csv(NEIGHBORHOOD_CSV, index=False)

    monthly_rows: list[dict[str, Any]] = []
    cursor = train_start
    block = 1
    while cursor < full_end:
        end = min(cursor + pd.DateOffset(months=1), full_end)
        metric = engine.metrics(base_trades, cursor, end)
        monthly_rows.append(
            {
                "block": block,
                "start": cursor.isoformat(),
                "end": end.isoformat(),
                **metric,
            }
        )
        cursor = end
        block += 1
    monthly = pd.DataFrame(monthly_rows)
    monthly.to_csv(MONTHLY_CSV, index=False)
    days = (full_end - train_start).total_seconds() / 86_400.0
    bootstrap_result = bootstrap(base_trades, days=days)

    contract = quality["fetch_metadata"]["contract_snapshot"]
    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "status": "no_go_not_promoted_not_live_ready",
        "frozen_candidate": summary["best"],
        "configs": [asdict(cfg) for cfg in configs],
        "priority_scores": priorities,
        "scenarios": scenario_rows,
        "neighborhood_summary": {
            "variants": len(neighborhood),
            "joint_gate": int(neighborhood["joint_gate"].sum()),
            "oos_dd_under_20pct": int(
                (neighborhood["oos_max_dd"] > -0.20).sum()
            ),
        },
        "bootstrap": bootstrap_result,
        "monthly": monthly_rows,
        "live_executable": {
            "bar_timing_reproducible": True,
            "stop_first_and_gap_model": True,
            "single_position_state_machine": True,
            "contract_filters_available": True,
            "production_runner_present": False,
            "restart_recovery_present": False,
            "exchange_reconciliation_present": False,
            "missing_bar_fail_closed_present": False,
            "kill_switch_present": False,
            "real_stop_slippage_evidence_present": False,
        },
        "contract_snapshot": contract,
    }
    AUDIT_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_quality_report(quality)
    write_audit_report(
        baseline=baseline,
        scenarios=scenarios,
        neighborhood=neighborhood,
        monthly=monthly,
        bootstrap_result=bootstrap_result,
        configs=configs,
        contract=contract,
    )
    print(json.dumps(search.json_safe(payload["neighborhood_summary"]), indent=2))
    print(json.dumps(search.json_safe(bootstrap_result), indent=2))
    print(f"wrote {AUDIT_JSON}")
    print(f"wrote {AUDIT_MD}")
    print(f"wrote {QUALITY_MD}")


if __name__ == "__main__":
    main()
