"""V35 分阶段提前入场候选：小仓试仓、主腿确认移交与利润保护。

本脚本不修改 V35。它比较：
- V35 原版；
- V38 窄利润保护主腿；
- 三种 early-long 信号；
- 独立卫星叠加；
- 主腿持仓时禁止新试仓、主腿入场时同价移交的分阶段结构。

分阶段结构保证主腿与试仓不同时持仓，因此组合最大名义 allocation 不超过
V35 的 3.0 上限。所有信号均在 K0 收盘确认，按 K2 open 执行。
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_source
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v37_v38_floor as v37


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_staged_early_entry_2026-07-17.json"
TRADES_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_staged_early_entry_trades_2026-07-17.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_staged_early_entry_equity_2026-07-17.csv"
NO_FLOOR = base.ProfitFloorConfig(enabled=False)
NARROW_FLOOR = base.ProfitFloorConfig(enabled=True, tiers=((4.75, 4.25),))


def add_candidate_features(features: pd.DataFrame) -> pd.DataFrame:
    out = v37.add_satellite_features(features)
    out["ret16"] = out["close"].div(out["close"].shift(16)).sub(1.0)
    out["di_gap14"] = out["plus_di14"].sub(out["minus_di14"])
    out["adx14_delta3"] = out["adx14"].sub(out["adx14"].shift(3))
    common = out["satellite_long_signal"]
    out["early_canonical"] = common
    out["early_di25"] = common & out["di_gap14"].ge(25.0)
    out["early_balanced"] = (
        common
        & out["di_gap14"].ge(22.0)
        & out["adx14_delta3"].ge(2.0)
        & out["ret16"].le(0.05)
    )
    out["early_balanced_di20"] = (
        common
        & out["di_gap14"].ge(20.0)
        & out["adx14_delta3"].ge(2.0)
        & out["ret16"].le(0.05)
    )
    out["early_balanced_di24"] = (
        common
        & out["di_gap14"].ge(24.0)
        & out["adx14_delta3"].ge(2.0)
        & out["ret16"].le(0.05)
    )
    out["early_balanced_delta1"] = (
        common
        & out["di_gap14"].ge(22.0)
        & out["adx14_delta3"].ge(1.0)
        & out["ret16"].le(0.05)
    )
    out["early_balanced_delta3"] = (
        common
        & out["di_gap14"].ge(22.0)
        & out["adx14_delta3"].ge(3.0)
        & out["ret16"].le(0.05)
    )
    out["early_balanced_ret04"] = (
        common
        & out["di_gap14"].ge(22.0)
        & out["adx14_delta3"].ge(2.0)
        & out["ret16"].le(0.04)
    )
    out["early_balanced_ret06"] = (
        common
        & out["di_gap14"].ge(22.0)
        & out["adx14_delta3"].ge(2.0)
        & out["ret16"].le(0.06)
    )
    return out


def main_position_state(
    index: pd.DatetimeIndex,
    trades: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    active = pd.Series(False, index=index)
    entries = pd.Series(False, index=index)
    for trade in trades.itertuples():
        entry_ts = pd.Timestamp(trade.entry_ts)
        exit_ts = pd.Timestamp(trade.exit_ts)
        active.loc[entry_ts:exit_ts] = True
        entries.loc[entry_ts] = True
    return active, entries


def run_staged_satellite(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    main_cfg: base.V35Config,
    sat_cfg: v37.SatelliteConfig,
    main_active: pd.Series,
    main_entries: pd.Series,
) -> v37.LegResult:
    """运行与主腿互斥、在主腿入场 open 同价移交的 early-long 试仓。"""

    start = max(main_cfg.warmup_bars, sat_cfg.entry_delay_bars + 1)
    equity = 1.0
    pos: v37.SatPosition | None = None
    last_exit_bar = -1
    period_returns: list[float] = []
    equity_values: list[float] = []
    weights: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if pos is not None and pos.pending_exit is not None:
            equity, cost = v37.close_satellite(
                equity=equity,
                pos=pos,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pos.pending_exit,
                trades=trades,
                cfg=sat_cfg,
            )
            trading_costs += cost
            pos = None
            last_exit_bar = i
            exited_this_bar = True

        if pos is not None and bool(main_entries.iloc[i]):
            equity, cost = v37.close_satellite(
                equity=equity,
                pos=pos,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason="main_confirmation",
                trades=trades,
                cfg=sat_cfg,
            )
            trading_costs += cost
            pos = None
            last_exit_bar = i
            exited_this_bar = True

        if pos is not None:
            funding_pnl = -pos.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        if (
            pos is None
            and not exited_this_bar
            and i > last_exit_bar
            and not bool(main_active.iloc[i])
        ):
            sig_i = i - sat_cfg.entry_delay_bars
            entry_atr = float(features["atr"].iloc[i - 1])
            if (
                bool(features["satellite_long_signal"].iloc[sig_i])
                and np.isfinite(entry_atr)
                and entry_atr > 0.0
                and open_price > 0.0
            ):
                allocation = min(
                    sat_cfg.max_allocation,
                    sat_cfg.target_atr_pct / (entry_atr / open_price),
                )
                cost = sat_cfg.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                pos = v37.SatPosition(
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )

        if pos is not None:
            stop = pos.entry_price - sat_cfg.hard_stop_atr * pos.entry_atr
            take = pos.entry_price + sat_cfg.take_profit_atr * pos.entry_atr
            if low <= stop:
                equity, cost = v37.close_satellite(
                    equity=equity,
                    pos=pos,
                    exit_price=stop,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="stop_loss",
                    trades=trades,
                    cfg=sat_cfg,
                )
                trading_costs += cost
                pos = None
                last_exit_bar = i
            elif high >= take:
                equity, cost = v37.close_satellite(
                    equity=equity,
                    pos=pos,
                    exit_price=take,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="take_profit",
                    trades=trades,
                    cfg=sat_cfg,
                )
                trading_costs += cost
                pos = None
                last_exit_bar = i
            else:
                pnl = pos.allocation * (close / pos.previous_price - 1.0)
                equity *= 1.0 + pnl
                pos.previous_price = close
                pos.mfe_atr = max(pos.mfe_atr, (high - pos.entry_price) / pos.entry_atr)
                if float(features["adx14"].iloc[i]) < sat_cfg.weak_adx14_exit:
                    pos.pending_exit = "weak_exit"

        period_returns.append(equity / start_equity - 1.0)
        equity_values.append(equity)
        weights.append(0.0 if pos is None else pos.allocation)

    index = frame.index[start:]
    returns = pd.Series(period_returns, index=index, name=f"{name}_return")
    equity_curve = pd.Series(equity_values, index=index, name=name)
    weight_series = pd.Series(weights, index=index, name=f"{name}_weight")
    trades_frame = pd.DataFrame(trades)
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weight_series,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    return v37.LegResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
    )


def make_satellite_run(
    *,
    name: str,
    signal_column: str,
    target_atr_pct: float,
    max_allocation: float,
    entry_delay_bars: int,
    staged: bool,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    main_cfg: base.V35Config,
    main: v37.LegResult,
) -> v37.LegResult:
    candidate_features = features.copy()
    candidate_features["satellite_long_signal"] = candidate_features[signal_column]
    sat_cfg = replace(
        v37.SatelliteConfig(),
        target_atr_pct=target_atr_pct,
        max_allocation=max_allocation,
        entry_delay_bars=entry_delay_bars,
    )
    if not staged:
        return v37.run_satellite(
            name,
            frame,
            funding,
            candidate_features,
            main_cfg,
            sat_cfg,
        )
    main_active, main_entries = main_position_state(frame.index, main.trades)
    return run_staged_satellite(
        name,
        frame,
        funding,
        candidate_features,
        main_cfg,
        sat_cfg,
        main_active,
        main_entries,
    )


def allocation_envelope(index: pd.DatetimeIndex, trades: pd.DataFrame) -> pd.Series:
    weights = pd.Series(0.0, index=index)
    for trade in trades.itertuples():
        mask = (index >= pd.Timestamp(trade.entry_ts)) & (index <= pd.Timestamp(trade.exit_ts))
        weights.loc[mask] = np.maximum(weights.loc[mask], abs(float(trade.allocation)))
    return weights


def combine_staged_legs(
    name: str,
    main_leg: v37.LegResult,
    satellite: v37.LegResult,
) -> v37.LegResult:
    """组合互斥腿；同一移交 bar 按先平试仓、后开主腿顺序复利。"""

    main_returns, satellite_returns = main_leg.period_returns.align(
        satellite.period_returns,
        join="outer",
        fill_value=0.0,
    )
    returns = ((1.0 + main_returns) * (1.0 + satellite_returns) - 1.0).rename(
        f"{name}_return"
    )
    equity_curve = (1.0 + returns).cumprod().rename(name)
    trades = pd.concat(
        [
            main_leg.trades.assign(leg="main"),
            satellite.trades.assign(leg="early"),
        ],
        ignore_index=True,
    )
    main_weights = allocation_envelope(returns.index, main_leg.trades)
    satellite_weights = allocation_envelope(returns.index, satellite.trades)
    weights = pd.concat([main_weights, satellite_weights], axis=1).max(axis=1)
    trading_costs = (
        float(main_leg.metrics["trading_costs_pct"])
        + float(satellite.metrics["trading_costs_pct"])
    ) / 100.0
    funding_pnl = (
        float(main_leg.metrics["funding_pnl_pct"])
        + float(satellite.metrics["funding_pnl_pct"])
    ) / 100.0
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl,
    )
    return v37.LegResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades),
        trades=trades,
        equity_curve=equity_curve,
        period_returns=returns,
    )


def fixed_period_metrics(run: v37.LegResult, start: str, end: str) -> dict[str, Any]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    curve = run.equity_curve.loc[start_ts:end_ts]
    if curve.empty:
        return {"start": start, "end": end, "available": False}
    rebased = curve.div(float(curve.iloc[0]))
    drawdown = rebased.div(rebased.cummax()).sub(1.0)
    trades = run.trades
    closed = 0
    if not trades.empty:
        exit_ts = pd.to_datetime(trades["exit_ts"], utc=True)
        closed = int(exit_ts.between(start_ts, end_ts, inclusive="both").sum())
    return {
        "start": curve.index[0].isoformat(),
        "end": curve.index[-1].isoformat(),
        "return_pct": base.pct(float(rebased.iloc[-1] - 1.0)),
        "max_drawdown_pct": base.pct(float(drawdown.min())),
        "closed_trades": closed,
    }


def staged_path_audit(
    main_leg: v37.LegResult,
    satellite: v37.LegResult,
) -> dict[str, Any]:
    overlaps: list[dict[str, str]] = []
    for sat_trade in satellite.trades.itertuples():
        sat_entry = pd.Timestamp(sat_trade.entry_ts)
        sat_exit = pd.Timestamp(sat_trade.exit_ts)
        for main_trade in main_leg.trades.itertuples():
            main_entry = pd.Timestamp(main_trade.entry_ts)
            main_exit = pd.Timestamp(main_trade.exit_ts)
            if max(sat_entry, main_entry) < min(sat_exit, main_exit):
                overlaps.append(
                    {
                        "satellite_entry": sat_entry.isoformat(),
                        "satellite_exit": sat_exit.isoformat(),
                        "main_entry": main_entry.isoformat(),
                        "main_exit": main_exit.isoformat(),
                    }
                )
    handoffs = satellite.trades[satellite.trades["exit_reason"].eq("main_confirmation")]
    lead_bars = handoffs["hold_bars"] if not handoffs.empty else pd.Series(dtype=float)
    anchors = satellite.trades[
        [
            "entry_ts",
            "exit_ts",
            "entry_price",
            "exit_price",
            "exit_reason",
            "allocation",
            "hold_bars",
            "trade_return",
        ]
    ]
    return {
        "overlapping_position_intervals": len(overlaps),
        "overlap_examples": overlaps[:3],
        "handoffs": int(len(handoffs)),
        "handoff_lead_bars_median": (
            round(float(lead_bars.median()), 2) if not lead_bars.empty else None
        ),
        "handoff_lead_bars_min": int(lead_bars.min()) if not lead_bars.empty else None,
        "handoff_lead_bars_max": int(lead_bars.max()) if not lead_bars.empty else None,
        "main_max_allocation": main_leg.metrics["max_abs_allocation"],
        "satellite_max_allocation": satellite.metrics["max_abs_allocation"],
        "portfolio_max_allocation_bound": max(
            main_leg.metrics["max_abs_allocation"],
            satellite.metrics["max_abs_allocation"],
        ),
        "first_satellite_trades": anchors.head(3).to_dict("records"),
        "last_satellite_trades": anchors.tail(3).to_dict("records"),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = data_source.load_data(warehouse)
    config = base.V35Config()
    features = add_candidate_features(base.build_features(frame, config))

    v35 = v37.wrap_main_result(base.run_backtest("v35_base", frame, funding, features, config, NO_FLOOR))
    v38 = v37.wrap_main_result(base.run_backtest("v38_narrow_floor", frame, funding, features, config, NARROW_FLOOR))
    runs: list[v37.LegResult] = [v35, v38]
    search_rows: list[dict[str, Any]] = []
    run_lookup: dict[tuple[str, str, float, float, str], tuple[v37.LegResult, v37.LegResult]] = {}

    signal_columns = ("early_canonical", "early_di25", "early_balanced")
    sizes = ((0.004, 0.50), (0.006, 0.75), (0.008, 1.00))
    for main_leg in (v35, v38):
        for signal_column in signal_columns:
            for target, cap in sizes:
                for staged in (False, True):
                    structure = "staged" if staged else "independent"
                    sat_name = (
                        f"{main_leg.name}_{signal_column}_t{target:.3f}_c{cap:.2f}_{structure}_sat"
                    )
                    sat = make_satellite_run(
                        name=sat_name,
                        signal_column=signal_column,
                        target_atr_pct=target,
                        max_allocation=cap,
                        entry_delay_bars=2,
                        staged=staged,
                        frame=frame,
                        funding=funding,
                        features=features,
                        main_cfg=config,
                        main=main_leg,
                    )
                    if staged:
                        combo = combine_staged_legs(f"{sat_name}_combo", main_leg, sat)
                    else:
                        combo = v37.combine_legs(f"{sat_name}_combo", main_leg, sat)
                    runs.extend((sat, combo))
                    run_lookup[
                        (main_leg.name, signal_column, target, cap, structure)
                    ] = (sat, combo)
                    search_rows.append(
                        {
                            "main": main_leg.name,
                            "signal": signal_column,
                            "target_atr_pct": target,
                            "satellite_cap": cap,
                            "structure": structure,
                            "risk_comparable_to_v35": staged,
                            "portfolio_max_allocation_bound": (
                                max(
                                    main_leg.metrics["max_abs_allocation"],
                                    sat.metrics["max_abs_allocation"],
                                )
                                if staged
                                else main_leg.metrics["max_abs_allocation"]
                                + sat.metrics["max_abs_allocation"]
                            ),
                            "satellite_metrics": sat.metrics,
                            "combo_metrics": combo.metrics,
                            "combo_slices": combo.slices,
                            "strictly_dominates_v35": (
                                combo.metrics["return_pct"] > v35.metrics["return_pct"]
                                and combo.metrics["max_drawdown_pct"]
                                > v35.metrics["max_drawdown_pct"]
                            ),
                        }
                    )

    candidate_key = (
        "v38_narrow_floor",
        "early_balanced",
        0.008,
        1.00,
        "staged",
    )
    candidate_sat, candidate = run_lookup[candidate_key]
    sensitivity_rows: list[dict[str, Any]] = []
    for delay in (1, 2, 3):
        if delay == 2:
            sat, combo = candidate_sat, candidate
        else:
            sat = make_satellite_run(
                name=f"candidate_phase_k{delay}_sat",
                signal_column="early_balanced",
                target_atr_pct=0.008,
                max_allocation=1.0,
                entry_delay_bars=delay,
                staged=True,
                frame=frame,
                funding=funding,
                features=features,
                main_cfg=config,
                main=v38,
            )
            combo = combine_staged_legs(f"candidate_phase_k{delay}", v38, sat)
            runs.extend((sat, combo))
        sensitivity_rows.append(
            {
                "kind": "entry_delay",
                "variant": f"K{delay}_open",
                "metrics": combo.metrics,
                "slices": combo.slices,
                "strictly_dominates_v35": (
                    combo.metrics["return_pct"] > v35.metrics["return_pct"]
                    and combo.metrics["max_drawdown_pct"]
                    > v35.metrics["max_drawdown_pct"]
                ),
            }
        )

    threshold_columns = (
        "early_balanced_di20",
        "early_balanced_di24",
        "early_balanced_delta1",
        "early_balanced_delta3",
        "early_balanced_ret04",
        "early_balanced_ret06",
    )
    for signal_column in threshold_columns:
        sat = make_satellite_run(
            name=f"candidate_sensitivity_{signal_column}_sat",
            signal_column=signal_column,
            target_atr_pct=0.008,
            max_allocation=1.0,
            entry_delay_bars=2,
            staged=True,
            frame=frame,
            funding=funding,
            features=features,
            main_cfg=config,
            main=v38,
        )
        combo = combine_staged_legs(f"candidate_sensitivity_{signal_column}", v38, sat)
        runs.extend((sat, combo))
        sensitivity_rows.append(
            {
                "kind": "one_at_a_time_threshold",
                "variant": signal_column,
                "metrics": combo.metrics,
                "slices": combo.slices,
                "strictly_dominates_v35": (
                    combo.metrics["return_pct"] > v35.metrics["return_pct"]
                    and combo.metrics["max_drawdown_pct"]
                    > v35.metrics["max_drawdown_pct"]
                ),
            }
        )

    fixed_periods = {
        "early_half": ("2025-06-16T02:30:00+00:00", "2025-12-31T23:45:00+00:00"),
        "late_half": ("2026-01-01T00:00:00+00:00", "2026-07-16T15:30:00+00:00"),
    }
    period_comparison = {
        name: {
            "v35": fixed_period_metrics(v35, start, end),
            "candidate": fixed_period_metrics(candidate, start, end),
        }
        for name, (start, end) in fixed_periods.items()
    }

    ranked = sorted(
        search_rows,
        key=lambda row: (
            bool(row["risk_comparable_to_v35"]),
            bool(row["strictly_dominates_v35"]),
            float(row["combo_metrics"]["sharpe"]),
            float(row["combo_metrics"]["return_pct"]),
        ),
        reverse=True,
    )
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "V35 staged early-entry limited search",
        "status": "diagnostic_only_not_registered",
        "source": "data_lake",
        "data_quality": quality,
        "main_config": asdict(config),
        "narrow_floor": asdict(NARROW_FLOOR),
        "signal_definitions": {
            "early_canonical": "V37 canonical early-long signal",
            "early_di25": "canonical + DI14 gap >= 25",
            "early_balanced": "canonical + DI14 gap >= 22 + ADX14 three-bar rise >= 2 + 4h return <= 5%",
        },
        "execution_contract": {
            "signal_and_entry": "K0 closed-bar signal; entry at K2 open.",
            "staged": "No new early leg while main is active; early leg exits at the same K2 open where a main entry occurs.",
            "same_bar_conflict": "Hard stop before take profit; weak exit executes next open.",
            "cost": "0.00085 per fill including adverse execution allowance; Binance funding aligned to 15m bars.",
            "risk": "Staged structure never overlaps main and early positions; maximum nominal allocation remains 3.0.",
        },
        "baseline": v35.metrics,
        "candidate": {
            "identity": {
                "main": "V35 + V38 narrow profit floor",
                "early_signal": "early_balanced",
                "target_atr_pct": 0.008,
                "satellite_cap": 1.0,
                "entry_delay_bars": 2,
                "structure": "staged same-open handoff",
            },
            "metrics": candidate.metrics,
            "slices": candidate.slices,
            "satellite_metrics": candidate_sat.metrics,
            "path_audit": staged_path_audit(v38, candidate_sat),
            "fixed_period_comparison": period_comparison,
        },
        "sensitivity": sensitivity_rows,
        "search": search_rows,
        "ranking": ranked,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.concat([run.equity_curve.rename(run.name) for run in runs], axis=1).to_csv(
        EQUITY_PATH,
        index_label="ts",
    )
    pd.concat(
        [run.trades.assign(variant=run.name) for run in runs if not run.trades.empty],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)

    print("baseline", v35.metrics)
    for row in ranked[:12]:
        print(
            row["main"],
            row["signal"],
            row["target_atr_pct"],
            row["satellite_cap"],
            row["structure"],
            row["combo_metrics"],
            "dominates_v35=",
            row["strictly_dominates_v35"],
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
