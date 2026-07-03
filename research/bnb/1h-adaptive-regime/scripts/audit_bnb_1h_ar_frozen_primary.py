from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_bnb_1h_adaptive_regime_search as search  # noqa: E402


DATE_TAG = "2026-07-03"
FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
SOURCE_JSON = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_search_{DATE_TAG}.json"
OUTPUT_JSON = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_robustness_{DATE_TAG}.json"
STRESS_CSV = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_stress_{DATE_TAG}.csv"
NEIGHBOR_CSV = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_neighbors_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"bnb-1h-adaptive-regime-robustness-{DATE_TAG}.md"

FEE_BASE = 0.001
SLIP_BASE = 0.0004
TICK_SIZE = 0.01
QTY_STEP = 0.01
MIN_QTY = 0.01
MIN_NOTIONAL = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the predeclared BNB 1h primary without retuning it."
    )
    parser.add_argument("--skip-neighbors", action="store_true")
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    return search.json_safe(value)


def metric_row(prefix: str, values: dict[str, float]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def hard_gate(metric: dict[str, float], *, min_trades: int, dd: float | None = None) -> bool:
    drawdown = metric["max_dd"] if dd is None else dd
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= search.TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= search.TARGET_WIN_RATE
        and drawdown > search.TARGET_MAX_DD
    )


def conservative_intrabar_dd(
    frame: pd.DataFrame,
    trades: list[Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
    fee_per_fill: float,
) -> float:
    selected = [
        trade
        for trade in trades
        if start <= trade.entry_ts < end and trade.exit_ts < end
    ]
    if not selected:
        return 0.0
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for trade in selected:
        for bar_i in range(trade.entry_i, trade.exit_i + 1):
            favorable = high[bar_i] if trade.side > 0 else low[bar_i]
            adverse = low[bar_i] if trade.side > 0 else high[bar_i]
            favorable_ret = trade.exposure * (
                trade.side * (favorable / trade.entry_price - 1.0) - fee_per_fill
            )
            adverse_ret = trade.exposure * (
                trade.side * (adverse / trade.entry_price - 1.0) - fee_per_fill
            )
            peak = max(peak, equity * max(0.001, 1.0 + favorable_ret))
            trough = equity * max(0.001, 1.0 + adverse_ret)
            max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(0.001, 1.0 + trade.equity_ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    return float(max_dd)


def adjacent(value: Any, choices: tuple[Any, ...]) -> list[Any]:
    ordered = sorted(set(choices))
    index = min(range(len(ordered)), key=lambda i: abs(float(ordered[i]) - float(value)))
    result: list[Any] = []
    if index > 0:
        result.append(ordered[index - 1])
    if index + 1 < len(ordered):
        result.append(ordered[index + 1])
    return [item for item in result if item != value]


def config_neighbors(engine: Any, cfg: Any, component: int) -> list[tuple[str, Any]]:
    fields: dict[str, tuple[Any, ...]] = {
        "band_k": (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0),
        "roc_threshold_bps": (25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0),
        "min_adx": (0.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 40.0),
        "min_rvol": (0.0, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0),
        "min_atr_bps": (0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0),
        "tp_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0),
        "sl_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0),
        "max_hold_bars": (4, 6, 8, 12, 18, 24, 36, 48, 72, 96, 120, 168, 240, 336),
        "cooldown_bars": (0, 3, 6, 12, 18, 24, 36, 48),
        "fixed_leverage": (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0),
        "risk_fraction": (0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03, 0.04),
        "max_leverage": (0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
    }
    neighbors: list[tuple[str, Any]] = []
    for field, values in fields.items():
        for new_value in adjacent(getattr(cfg, field), values):
            candidate = replace(
                cfg,
                name=f"{cfg.name}__C{component}_{field}_{new_value}",
                **{field: new_value},
            )
            if candidate.max_adx <= candidate.min_adx:
                continue
            if candidate.max_atr_bps <= candidate.min_atr_bps:
                continue
            neighbors.append((f"component_{component}:{field}={new_value}", candidate))
    return neighbors


def main() -> None:
    args = parse_args()
    if not SOURCE_JSON.exists():
        raise FileNotFoundError("Run the broad BNB search before this audit")
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    engine = search.load_engine()
    raw_frame, funding, quality = search.load_data()
    frame = engine.add_features(raw_frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    split = {key: pd.Timestamp(value) for key, value in source["split"].items()}
    configs = tuple(engine.StrategyConfig(**row) for row in source["primary_configs"])
    priorities = tuple(float(value) for value in source["primary_ensemble_priorities"])

    def run(
        *,
        fee: float,
        slip: float,
        delay: int,
        members: tuple[Any, ...] = configs,
    ) -> tuple[list[Any], list[Any], dict[str, float], dict[str, float], float, float]:
        engine.FEE_PER_FILL = fee
        engine.SLIPPAGE_PER_FILL = slip
        delayed = tuple(replace(cfg, entry_delay_bars=delay) for cfg in members)

        def build(start: pd.Timestamp | None) -> list[Any]:
            parts = [
                search.simulate_masked(
                    engine,
                    frame,
                    cfg,
                    funding_times,
                    funding_cumulative,
                    start,
                )
                for cfg in delayed
            ]
            if len(parts) == 1:
                return parts[0]
            return engine.merge_trade_sets(parts[0], parts[1], priorities[0], priorities[1])

        full_trades = build(None)
        oos_trades = build(split["oos_start"])
        full = search.strict_metrics(
            engine, full_trades, split["train_start"], split["full_end"]
        )
        oos = search.strict_metrics(
            engine, oos_trades, split["oos_start"], split["full_end"]
        )
        full_dd = conservative_intrabar_dd(
            frame, full_trades, split["train_start"], split["full_end"], fee
        )
        oos_dd = conservative_intrabar_dd(
            frame, oos_trades, split["oos_start"], split["full_end"], fee
        )
        return full_trades, oos_trades, full, oos, full_dd, oos_dd

    stresses = (
        ("baseline_k1", FEE_BASE, SLIP_BASE, 1),
        ("slip_8bps_k1", FEE_BASE, 0.0008, 1),
        ("slip_12bps_k1", FEE_BASE, 0.0012, 1),
        ("fee15_slip8_k1", 0.0015, 0.0008, 1),
        ("baseline_k2", FEE_BASE, SLIP_BASE, 2),
        ("slip_8bps_k2", FEE_BASE, 0.0008, 2),
    )
    stress_rows: list[dict[str, Any]] = []
    baseline_full_trades: list[Any] = []
    for name, fee, slip, delay in stresses:
        full_trades, _oos_trades, full, oos, full_dd, oos_dd = run(
            fee=fee, slip=slip, delay=delay
        )
        if name == "baseline_k1":
            baseline_full_trades = full_trades
        row = {
            "scenario": name,
            "fee_per_fill": fee,
            "slippage_per_fill": slip,
            "entry_delay_bars": delay,
            "full_conservative_intrabar_dd": full_dd,
            "oos_conservative_intrabar_dd": oos_dd,
            **metric_row("full", full),
            **metric_row("oos", oos),
        }
        row["full_hard_gate_conservative"] = hard_gate(
            full, min_trades=search.MIN_PREFIT_TRADES, dd=full_dd
        )
        row["oos_hard_gate_conservative"] = hard_gate(
            oos, min_trades=search.MIN_OOS_TRADES, dd=oos_dd
        )
        row["joint_hard_gate_conservative"] = bool(
            row["full_hard_gate_conservative"] and row["oos_hard_gate_conservative"]
        )
        stress_rows.append(row)
    pd.DataFrame(stress_rows).to_csv(STRESS_CSV, index=False)

    neighbor_rows: list[dict[str, Any]] = []
    if not args.skip_neighbors:
        for component, cfg in enumerate(configs):
            for label, neighbor in config_neighbors(engine, cfg, component):
                members = list(configs)
                members[component] = neighbor
                _full_trades, _oos_trades, full, oos, full_dd, oos_dd = run(
                    fee=FEE_BASE,
                    slip=SLIP_BASE,
                    delay=1,
                    members=tuple(members),
                )
                neighbor_rows.append(
                    {
                        "neighbor": label,
                        "full_conservative_intrabar_dd": full_dd,
                        "oos_conservative_intrabar_dd": oos_dd,
                        **metric_row("full", full),
                        **metric_row("oos", oos),
                        "joint_hard_gate_conservative": bool(
                            hard_gate(
                                full,
                                min_trades=search.MIN_PREFIT_TRADES,
                                dd=full_dd,
                            )
                            and hard_gate(
                                oos,
                                min_trades=search.MIN_OOS_TRADES,
                                dd=oos_dd,
                            )
                        ),
                    }
                )
    pd.DataFrame(neighbor_rows).to_csv(NEIGHBOR_CSV, index=False)

    exposures = [trade.exposure for trade in baseline_full_trades]
    stop_tick_ratios = [
        (trade.signal_atr_bps / 10_000.0 * trade.entry_price * cfg.sl_atr) / TICK_SIZE
        for cfg in configs
        for trade in baseline_full_trades
        if trade.config == cfg.name
    ]
    min_reference_equity = 0.0
    for trade in baseline_full_trades:
        required_notional = max(MIN_NOTIONAL, MIN_QTY * trade.entry_price)
        min_reference_equity = max(
            min_reference_equity,
            required_notional / max(trade.exposure, 1e-9),
        )
    execution_checks = {
        "max_exposure": float(max(exposures, default=0.0)),
        "min_exposure": float(min(exposures, default=0.0)),
        "worst_recorded_equity_mae": float(
            min((trade.equity_mae for trade in baseline_full_trades), default=0.0)
        ),
        "recorded_path_crossed_zero_equity": bool(
            any(trade.equity_mae <= -1.0 for trade in baseline_full_trades)
        ),
        "min_stop_distance_ticks": float(min(stop_tick_ratios, default=0.0)),
        "reference_min_equity_for_min_qty_and_notional": float(min_reference_equity),
        "tick_size": TICK_SIZE,
        "qty_step": QTY_STEP,
        "min_qty": MIN_QTY,
        "min_notional": MIN_NOTIONAL,
    }
    baseline = stress_rows[0]
    neighborhood = {
        "count": len(neighbor_rows),
        "joint_hard_gate_count": int(
            sum(bool(row["joint_hard_gate_conservative"]) for row in neighbor_rows)
        ),
        "joint_hard_gate_rate": float(
            np.mean([row["joint_hard_gate_conservative"] for row in neighbor_rows])
        )
        if neighbor_rows
        else 0.0,
    }
    audit_pass = bool(
        baseline["joint_hard_gate_conservative"]
        and not execution_checks["recorded_path_crossed_zero_equity"]
        and stress_rows[1]["joint_hard_gate_conservative"]
        and stress_rows[4]["joint_hard_gate_conservative"]
        and neighborhood["joint_hard_gate_rate"] >= 0.50
    )
    payload = {
        "family": "BNB-1H-Adaptive-Regime",
        "primary": source["primary"]["name"],
        "source_status": source["status"],
        "audit_pass": audit_pass,
        "stress": stress_rows,
        "neighborhood": neighborhood,
        "execution_checks": execution_checks,
        "quality": quality,
        "promotion_blockers": [
            "未实现并影子运行生产 runner",
            "未用账户实际 notional 获取 Binance maintenance-margin tier",
            "未验证真实 testnet/mainnet conditional order acknowledgement 与重启恢复",
        ],
    }
    OUTPUT_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    def mult(value: float) -> str:
        return f"{value:.2f}x"

    lines = [
        "# BNB-1H-Adaptive-Regime 冻结 primary 稳健性与实盘边界审计 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "冻结 primary 通过本地稳健性门槛，但仍有生产 runner、账户 maintenance margin 和真实订单状态恢复三项 blocker，因此仍不是 live-ready。"
            if audit_pass
            else "冻结 primary 未通过本地稳健性门槛，结论保持 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        f"- baseline full：annual `{mult(baseline['full_annual_multiple'])}`，DD（逐笔）`{pct(baseline['full_max_dd'])}`，保守 intrabar DD `{pct(baseline['full_conservative_intrabar_dd'])}`，win `{pct(baseline['full_win_rate'])}`，trades `{int(baseline['full_trades'])}`。",
        f"- baseline locked OOS：annual `{mult(baseline['oos_annual_multiple'])}`，DD（逐笔）`{pct(baseline['oos_max_dd'])}`，保守 intrabar DD `{pct(baseline['oos_conservative_intrabar_dd'])}`，win `{pct(baseline['oos_win_rate'])}`，trades `{int(baseline['oos_trades'])}`。",
        f"- baseline conservative joint gate：`{baseline['joint_hard_gate_conservative']}`。",
        f"- 一维参数邻域 joint pass：`{neighborhood['joint_hard_gate_count']}/{neighborhood['count']}`。",
        "",
        "## 成本与延迟压力",
        "",
        "| Scenario | Full annual | Full DD* | OOS annual | OOS DD* | OOS win | Joint |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in stress_rows:
        lines.append(
            f"| `{row['scenario']}` | `{mult(row['full_annual_multiple'])}` | `{pct(row['full_conservative_intrabar_dd'])}` | `{mult(row['oos_annual_multiple'])}` | `{pct(row['oos_conservative_intrabar_dd'])}` | `{pct(row['oos_win_rate'])}` | `{row['joint_hard_gate_conservative']}` |"
        )
    lines.extend(
        [
            "",
            "`DD*` 为每根持仓 K 内先计有利极值、再计不利极值的保守上界；它不会把只看逐笔平仓净值的较浅回撤当成实盘事实。",
            "",
            "## 执行边界",
            "",
            f"- 最大 exposure：`{execution_checks['max_exposure']:.3f}x`；最差记录路径 equity MAE：`{pct(execution_checks['worst_recorded_equity_mae'])}`。",
            f"- 最小 stop 距离约 `{execution_checks['min_stop_distance_ticks']:.2f}` ticks。",
            f"- 按当前最小数量/名义价值，本历史路径的参考最低权益约 `{execution_checks['reference_min_equity_for_min_qty_and_notional']:.2f} USDT`；真实部署仍需按账户余额和风险限额重新校验。",
            "- 当前没有生产 runner、账户 maintenance-margin tier、真实 conditional order acknowledgement、断线/重启恢复证据；这些仍是 hard blockers。",
            "",
            "## 保留产物",
            "",
            f"- `{OUTPUT_JSON.relative_to(ROOT)}`",
            f"- `{STRESS_CSV.relative_to(ROOT)}`",
            f"- `{NEIGHBOR_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
