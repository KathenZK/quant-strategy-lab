from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_trx_1h_adaptive_regime_search as search  # noqa: E402


base = search.load_engine()
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
LIVE_DIR = FAMILY_DIR / "live-specs"
DATE_TAG = "2026-07-03"
SOURCE_JSON = ARTIFACT_DIR / f"trx_1h_adaptive_regime_refine_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_live_feasibility_{DATE_TAG}.json"
REPORT_MD = LIVE_DIR / f"trx-1h-ar-live-feasibility-{DATE_TAG}.md"


def metric_bundle(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> dict[str, dict[str, float]]:
    return {
        "train": base.metrics(trades, train_start, train_end),
        "validation": base.metrics(trades, train_end, oos_start),
        "prefit": base.metrics(trades, train_start, oos_start),
        "holdout": base.metrics(trades, oos_start, full_end),
        "full": base.metrics(trades, train_start, full_end),
    }


def run_scenario(
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    configs: list[Any],
    *,
    entry_delay_bars: int,
    fee_per_fill: float,
    slippage_per_fill: float,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    full_end: pd.Timestamp,
    frozen_priorities: tuple[float, float] | None = None,
) -> dict[str, Any]:
    original_fee = base.FEE_PER_FILL
    original_slippage = base.SLIPPAGE_PER_FILL
    base.FEE_PER_FILL = fee_per_fill
    base.SLIPPAGE_PER_FILL = slippage_per_fill
    try:
        scenario_configs = [
            replace(cfg, entry_delay_bars=entry_delay_bars) for cfg in configs
        ]
        components: list[tuple[float, list[Any]]] = []
        for cfg in scenario_configs:
            trades = base.simulate_trades(
                frame,
                base.build_signal(frame, cfg),
                cfg,
                funding_times,
                funding_cumulative,
            )
            train = base.metrics(trades, train_start, train_end)
            validation = base.metrics(trades, train_end, oos_start)
            prefit = base.metrics(trades, train_start, oos_start)
            priority = base.prefit_score(train, validation, prefit)
            components.append((priority, trades))
        priorities = frozen_priorities or (
            components[0][0],
            components[1][0],
        )
        merged = base.merge_trade_sets(
            components[0][1],
            components[1][1],
            priorities[0],
            priorities[1],
        )
        metrics = metric_bundle(
            merged,
            train_start=train_start,
            train_end=train_end,
            oos_start=oos_start,
            full_end=full_end,
        )
        return {
            "entry_delay_bars": entry_delay_bars,
            "fee_per_fill": fee_per_fill,
            "slippage_per_fill": slippage_per_fill,
            "scenario_component_scores": [item[0] for item in components],
            "frozen_component_priorities": list(priorities),
            "metrics": metrics,
            "target_pass": base.target_gate(metrics["holdout"], metrics["full"]),
        }
    finally:
        base.FEE_PER_FILL = original_fee
        base.SLIPPAGE_PER_FILL = original_slippage


def main() -> None:
    if not SOURCE_JSON.exists():
        raise FileNotFoundError("Run the TRX neighborhood refinement first")
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    frame, funding, quality = search.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=search.WARMUP_DAYS)
    oos_start = full_end - pd.DateOffset(months=search.LOCKED_OOS_MONTHS)
    train_end = train_start + (oos_start - train_start) * 0.65
    config_names = str(source["best"]["config_names"]).split("+")
    configs = [
        base.StrategyConfig(**source["retained_configs"][name])
        for name in config_names
    ]
    scenario_specs = (
        ("baseline_k1", 1, 0.0010, 0.0004),
        ("delay_k2", 2, 0.0010, 0.0004),
        ("slippage_8bps", 1, 0.0010, 0.0008),
        ("delay_k2_slippage_8bps", 2, 0.0010, 0.0008),
        ("fee_15bps_slippage_8bps", 1, 0.0015, 0.0008),
    )
    baseline_name, baseline_delay, baseline_fee, baseline_slippage = scenario_specs[0]
    baseline_scenario = run_scenario(
        frame,
        funding_times,
        funding_cumulative,
        configs,
        entry_delay_bars=baseline_delay,
        fee_per_fill=baseline_fee,
        slippage_per_fill=baseline_slippage,
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
        full_end=full_end,
    )
    frozen_priorities = tuple(baseline_scenario["frozen_component_priorities"])
    scenarios = {baseline_name: baseline_scenario}
    for name, delay, fee, slippage in scenario_specs[1:]:
        scenarios[name] = run_scenario(
            frame,
            funding_times,
            funding_cumulative,
            configs,
            entry_delay_bars=delay,
            fee_per_fill=fee,
            slippage_per_fill=slippage,
            train_start=train_start,
            train_end=train_end,
            oos_start=oos_start,
            full_end=full_end,
            frozen_priorities=frozen_priorities,
        )
    expected = source["best"]
    baseline = scenarios["baseline_k1"]["metrics"]
    for window in ("train", "validation", "prefit", "holdout", "full"):
        for metric in ("trades", "annual_multiple", "max_dd", "win_rate"):
            observed = float(baseline[window][metric])
            recorded = float(expected[f"{window}_{metric}"])
            if abs(observed - recorded) > 1e-12:
                raise RuntimeError(
                    f"Baseline reproduction drift at {window}.{metric}: "
                    f"{observed} != {recorded}"
                )
    last_close = float(frame["close"].iloc[-1])
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "audited_observation": source["best"]["name"],
        "status": "no_go_not_promoted_not_live_ready",
        "reason": "The prefit hard gate and locked OOS hard gate both failed; no production runner exists.",
        "quality": quality,
        "components": {cfg.name: source["retained_configs"][cfg.name] for cfg in configs},
        "scenarios": scenarios,
        "contract_filters": {
            "tick_size": 0.00001,
            "tick_size_bps_at_last_close": 0.00001 / last_close * 10_000.0,
            "quantity_step": 1.0,
            "min_quantity": 1.0,
            "min_notional_usdt": 5.0,
            "market_max_quantity": 5_000_000.0,
        },
        "live_controls": {
            "signal_timing": "closed_1h_bar_then_next_open_market_order",
            "protection": "reduce-only stop-market immediately after entry; fixed TP or close-confirmed trailing update",
            "same_bar_ambiguity": "stop_first",
            "gap_stop": "market at first available open plus adverse slippage",
            "single_position": True,
            "missing_bar_action": "block new entries and alert",
            "restart_recovery": "required: reconcile exchange position and open protection orders before signals",
            "kill_switch": "required but no runner is implemented",
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# TRX-1H-Adaptive-Regime 实盘可行性审计 - 2026-07-03",
        "",
        "## 结论",
        "",
        "`NO-GO / not promoted / not live-ready`。领先观察值的下一根开盘 + 即时保护单状态机在工程上可实现，但策略没有通过 prefit 硬门槛，最近三个月 locked OOS 也亏损；仓库中没有生产 runner，因此不能交付为 live、paper-live、dry-run、handoff 或 candidate。",
        "",
        f"- 审计对象：`{source['best']['name']}`。",
        f"- components：`{'+'.join(config_names)}`。",
        "- baseline 已按 trades / annual / DD / win 四字段逐窗口精确复现第一性结果。",
        "",
        "## 执行压力",
        "",
        "| Scenario | Full annual | Full DD | Full win | OOS annual | OOS DD | OOS win | OOS trades | Pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, scenario in scenarios.items():
        full = scenario["metrics"]["full"]
        holdout = scenario["metrics"]["holdout"]
        lines.append(
            f"| `{name}` | `{full['annual_multiple']:.3f}x` | `{full['max_dd']:.2%}` | `{full['win_rate']:.2%}` | `{holdout['annual_multiple']:.3f}x` | `{holdout['max_dd']:.2%}` | `{holdout['win_rate']:.2%}` | `{int(holdout['trades'])}` | `{scenario['target_pass']}` |"
        )
    lines.extend(
        [
            "",
            "## 订单时序",
            "",
            "- `K` 完整闭合后计算信号，`K+1 open` 发送市价单；不使用 K 内未来信息。",
            "- 成交后立即提交 reduce-only stop-market；fixed TP 使用 reduce-only take-profit-market。trailing 只使用已闭合 K 的 high/low 更新，并从下一根 K 生效。",
            "- 同 K stop/target 双触发按 stop-first；open 跳过 stop 时按首个可成交 open 加不利滑点退出。",
            "- 单仓、不加仓；ensemble 冲突按 prefit score 冻结优先级，不读取 OOS 排序。",
            "",
            "## 合约过滤器与运行控制",
            "",
            f"- `tickSize=0.00001`，按最后 close `{last_close:.5f}` 约 `{0.00001 / last_close * 10_000.0:.3f} bps/tick`；`stepSize=1`，`MIN_NOTIONAL=5 USDT`。价格按方向保守取整，数量向下取整。",
            "- 每次启动必须核对 `TRXUSDT` 状态、过滤器、账户 position mode、杠杆与 margin type；本次只有快照，没有假定它永久不变。",
            "- 缺 K、时钟漂移、资金费/行情陈旧时禁止新开仓；重启先以交易所仓位和保护单为真相源恢复状态。",
            "- 必须有最大账户回撤、单笔风险、连续下单失败、保护单丢失和数据陈旧 kill switch；当前仓库未实现这些生产能力。",
            "",
            "## 最终边界",
            "",
            "工程可执行不等于策略可实盘。由于性能 gate 和 OOS gate 均失败，不生成 canonical live spec。后续主账登记的 `V1base` 与 `V2` 仅为 diagnostic baseline / clean baseline，不改变本审计的 `NO-GO / not live-ready` 结论。",
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(search.json_safe(scenarios), indent=2), flush=True)


if __name__ == "__main__":
    main()
