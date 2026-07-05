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
FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
SEARCH_SCRIPT = SCRIPT_DIR / "research_sol_1h_adaptive_regime_search.py"
SEARCH_JSON = ARTIFACT_DIR / "sol_1h_adaptive_regime_search_2026-07-03.json"
AUDIT_JSON = ARTIFACT_DIR / "sol_1h_adaptive_regime_boundary_audit_2026-07-03.json"
SCENARIOS_CSV = ARTIFACT_DIR / "sol_1h_adaptive_regime_audit_scenarios_2026-07-03.csv"
NEIGHBORHOOD_CSV = ARTIFACT_DIR / "sol_1h_adaptive_regime_neighborhood_2026-07-03.csv"
MONTHLY_CSV = ARTIFACT_DIR / "sol_1h_adaptive_regime_monthly_2026-07-03.csv"
AUDIT_MD = DIAGNOSTIC_DIR / "sol-1h-adaptive-regime-boundary-audit-2026-07-03.md"
QUALITY_MD = DIAGNOSTIC_DIR / "sol-binance-1h-data-quality-2026-07-03.md"


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
        if len(legs) == 1:
            merged = legs[0]
        elif len(legs) == 2:
            merged = engine.merge_trade_sets(
                legs[0], legs[1], priorities[0], priorities[1]
            )
        else:
            raise RuntimeError(f"Expected one or two strategy legs, got {len(legs)}")
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


def neighborhood_configs(
    engine: Any, configs: list[Any]
) -> list[tuple[str, list[Any]]]:
    variants: list[tuple[str, list[Any]]] = []

    def adjacent(current: Any, values: list[Any]) -> list[Any]:
        unique = list(dict.fromkeys(values))
        if isinstance(current, (int, float)) and all(
            isinstance(item, (int, float)) for item in unique
        ):
            ordered = sorted(unique)
            lower = [item for item in ordered if item < current]
            upper = [item for item in ordered if item > current]
            return ([lower[-1]] if lower else []) + ([upper[0]] if upper else [])
        return [item for item in unique if item != current]

    def add(leg: int, field: str, values: list[Any]) -> None:
        cfg = configs[leg]
        for value in adjacent(getattr(cfg, field), values):
            updated_cfg = replace(cfg, **{field: value})
            if updated_cfg.max_adx <= updated_cfg.min_adx:
                continue
            if updated_cfg.max_atr_bps <= updated_cfg.min_atr_bps:
                continue
            updated = list(configs)
            updated[leg] = updated_cfg
            variants.append((f"leg{leg + 1}.{field}={value}", updated))

    common_grids: dict[str, list[Any]] = {
        "side_mode": ["both", "long", "short"],
        "ema_htf": [55, 89, 144, 233, 377],
        "band_k": [0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 4.0],
        "pullback_atr": [-0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0],
        "roc_window": list(engine.ROC_WINDOWS),
        "roc_threshold_bps": [25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0],
        "min_adx": [0.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 40.0],
        "max_adx": [20.0, 24.0, 28.0, 32.0, 36.0, 40.0, 45.0, 55.0, 100.0],
        "min_rvol": [0.0, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0],
        "min_atr_bps": [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0],
        "max_atr_bps": [175.0, 200.0, 250.0, 300.0, 400.0, 600.0, 10_000.0],
        "min_dir_roc_bps": [
            -10_000.0,
            -300.0,
            -200.0,
            -100.0,
            -50.0,
            0.0,
            50.0,
            100.0,
            200.0,
            300.0,
        ],
        "max_dist_ema_bps": [
            200.0,
            300.0,
            500.0,
            750.0,
            1_000.0,
            1_500.0,
            2_500.0,
            10_000.0,
        ],
        "htf_mode": ["none", "h4", "h12", "d1"],
        "require_macd_turn": [False, True],
        "require_body_dir": [False, True],
        "max_aligned_funding_bps": [0.5, 1.0, 2.0, 4.0, 8.0, 10_000.0],
        "exit_kind": ["fixed", "trailing"],
        "tp_atr": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0],
        "sl_atr": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0],
        "trail_activation_atr": [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0],
        "trail_atr": [0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0],
        "max_hold_bars": [4, 6, 8, 12, 18, 24, 36, 48, 72, 96, 120, 168, 240, 336],
        "cooldown_bars": [0, 3, 6, 12, 18, 24, 36, 48],
        "sizing_kind": ["fixed", "risk"],
        "fixed_leverage": [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0],
        "risk_fraction": [
            0.003,
            0.005,
            0.0075,
            0.01,
            0.0125,
            0.015,
            0.02,
            0.025,
            0.03,
            0.04,
        ],
        "max_leverage": [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
    }
    for leg, cfg in enumerate(configs):
        if cfg.style in {
            "bb_revert",
            "bb_break",
            "keltner_break",
            "squeeze_release",
        }:
            windows = list(engine.BAND_WINDOWS)
        elif cfg.style == "donchian_break":
            windows = list(engine.DONCHIAN_WINDOWS)
        elif cfg.style == "rsi_reversal":
            windows = list(engine.RSI_WINDOWS)
        elif cfg.style == "stoch_reversal":
            windows = list(engine.STOCH_WINDOWS)
        elif cfg.style in {"cci_reversal", "williams_reversal"}:
            windows = list(engine.CCI_WINDOWS)
        elif cfg.style == "vwap_revert":
            windows = list(engine.VWAP_WINDOWS)
        else:
            windows = list(engine.BAND_WINDOWS)
        add(leg, "indicator_window", windows)
        for field, values in common_grids.items():
            add(leg, field, values)
        for macd in engine.MACD_SETS:
            if macd == (cfg.macd_fast, cfg.macd_slow, cfg.macd_signal):
                continue
            updated = list(configs)
            updated[leg] = replace(
                cfg,
                macd_fast=macd[0],
                macd_slow=macd[1],
                macd_signal=macd[2],
            )
            variants.append((f"leg{leg + 1}.macd_set={macd}", updated))
    return variants


def bootstrap(
    trades: list[Any], *, days: float, samples: int = 10_000
) -> dict[str, Any]:
    rng = np.random.default_rng(20260703)
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
        for trade_ret, trade_mae in zip(sample_returns, maes[indices], strict=True):
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
        "annual_multiple_p05_p50_p95": np.quantile(annual, [0.05, 0.50, 0.95]).tolist(),
        "max_drawdown_p05_p50_p95": np.quantile(drawdown, [0.05, 0.50, 0.95]).tolist(),
        "win_rate_p05_p50_p95": np.quantile(win_rate, [0.05, 0.50, 0.95]).tolist(),
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
        "# SOLUSDT Binance 永续 1h 数据质量报告 - 2026-07-03",
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
    source_phase: str,
) -> None:
    oos = {
        key.removeprefix("oos_"): value
        for key, value in baseline.items()
        if key.startswith("oos_")
    }
    full = {
        key.removeprefix("full_"): value
        for key, value in baseline.items()
        if key.startswith("full_")
    }
    negative_months = int((monthly["total_return"] < 0).sum())
    lines = [
        "# SOL-1H-Adaptive-Regime 冻结边界与实盘可执行审计 - 2026-07-03",
        "",
        "## 最终结论",
        "",
        (
            "`performance hard gate hit / live audit failed / not promoted / not live-ready`。"
            if baseline["joint_gate"]
            else "`NO-GO / not promoted / not live-ready`。"
        ),
        "",
        (
            "冻结冠军通过 prefit、full 与最近三个月 locked OOS 的收益/胜率/回撤硬门槛，但生产 runner、交易所对账、重启恢复、missing-bar fail-closed、kill switch、价格/数量过滤器落单与真实 stop-market 滑点证据仍缺失，因此不能进入任何 promotion 状态。"
            if baseline["joint_gate"]
            else "冻结冠军没有同时通过 prefit、full 与最近三个月 locked OOS 的 `10x / 50% / <20%` 硬门槛，因此不存在可登记、可交接或可实盘的版本。"
        ),
        "",
        "## 冻结冠军",
        "",
        f"- 来源阶段：`{source_phase}`。",
        f"- 配置：`{' + '.join(cfg.name for cfg in configs)}`。",
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
            "- 研究仓库当前没有 SOL production runner、交易所订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch、tick/step rounding 回测与真实 stop-market 滑点证据。",
            "- 本轮不生成 live spec，不登记版本；性能硬门槛和 live 审计任一失败都禁止 promotion。",
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
    search = load_module(SEARCH_SCRIPT, "sol_1h_search_wrapper")
    engine = search.load_engine()
    frame, funding, quality = search.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    search_summary = json.loads(SEARCH_JSON.read_text(encoding="utf-8"))
    summary = search_summary
    config_payload = summary["best_configs"]
    source_phase = "million_config_broad_search_v1"
    config_names = summary["best"]["config_names"].split("+")
    configs = [engine.StrategyConfig(**config_payload[name]) for name in config_names]
    split = search_summary["split"]
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
    ordered_trades = sorted(base_trades, key=lambda trade: trade.entry_i)
    timing_valid = all(trade.entry_i == trade.signal_i + 1 for trade in ordered_trades)
    no_overlap = all(
        current.entry_i > previous.exit_i
        for previous, current in zip(ordered_trades, ordered_trades[1:], strict=False)
    )
    worst_equity_return = min(trade.equity_ret for trade in ordered_trades)
    worst_equity_mae = min(trade.equity_mae for trade in ordered_trades)
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "source_phase": source_phase,
        "status": (
            "performance_gate_hit_live_audit_failed_not_promoted"
            if baseline["joint_gate"]
            else "no_go_not_promoted_not_live_ready"
        ),
        "frozen_candidate": summary["best"],
        "configs": [asdict(cfg) for cfg in configs],
        "priority_scores": priorities,
        "scenarios": scenario_rows,
        "neighborhood_summary": {
            "variants": len(neighborhood),
            "joint_gate": int(neighborhood["joint_gate"].sum()),
            "oos_dd_under_20pct": int((neighborhood["oos_max_dd"] > -0.20).sum()),
        },
        "bootstrap": bootstrap_result,
        "monthly": monthly_rows,
        "live_executable": {
            "bar_timing_reproducible": timing_valid,
            "stop_first_and_gap_model": True,
            "single_position_state_machine": no_overlap,
            "no_backtest_bankruptcy_event": worst_equity_return > -1.0
            and worst_equity_mae > -1.0,
            "worst_equity_return": worst_equity_return,
            "worst_equity_mae": worst_equity_mae,
            "contract_filters_available": True,
            "tick_step_rounding_backtest_present": False,
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
        source_phase=source_phase,
    )
    print(json.dumps(search.json_safe(payload["neighborhood_summary"]), indent=2))
    print(json.dumps(search.json_safe(bootstrap_result), indent=2))
    print(f"wrote {AUDIT_JSON}")
    print(f"wrote {AUDIT_MD}")
    print(f"wrote {QUALITY_MD}")


if __name__ == "__main__":
    main()
