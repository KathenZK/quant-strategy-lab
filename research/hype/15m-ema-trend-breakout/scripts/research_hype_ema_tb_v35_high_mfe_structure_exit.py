from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14"
DEFAULT_UNTIL = "2026-07-14T12:45:00Z"
LATEST_CASE_ENTRY = pd.Timestamp("2026-07-13T14:45:00Z")
PRE_INCIDENT_END = pd.Timestamp("2026-07-13T14:30:00Z")


@dataclass(frozen=True, slots=True)
class StructureExitConfig:
    name: str
    mode: str
    activation_mfe_atr: float = 4.0
    adx_weakness_mode: str = "below_threshold"
    adx_weak_bars: int = 3
    adx_peak_drop: float = 5.0
    structure_lookback: int = 4
    require_episode_reset: bool = False
    note: str = ""


@dataclass(slots=True)
class StructurePosition:
    direction: int
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    mfe_atr: float = 0.0
    weak_bars: int = 0
    floor_offset_atr: float = 0.0
    late_weak_bars: int = 0
    activation_adx_peak: float = float("-inf")
    previous_adx: float | None = None


def variants() -> list[StructureExitConfig]:
    return [
        StructureExitConfig(
            "v35_base",
            mode="base",
            note="V35：MFE>=1.5ATR 后永久关闭 ADX indicator exit",
        ),
        StructureExitConfig(
            "never_disable_indicator",
            mode="never_disable",
            note="ADX<22 连续 3 根在整笔持仓期间始终有效；无价格结构确认",
        ),
        StructureExitConfig("mfe40_adx3_swing2", mode="structure", structure_lookback=2),
        StructureExitConfig("mfe40_adx3_swing4", mode="structure", structure_lookback=4),
        StructureExitConfig("mfe40_adx3_swing8", mode="structure", structure_lookback=8),
        StructureExitConfig(
            "mfe40_adx3_swing2_reset",
            mode="structure",
            structure_lookback=2,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adx3_swing4_reset",
            mode="structure",
            structure_lookback=4,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adx3_swing8_reset",
            mode="structure",
            structure_lookback=8,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe35_adx3_swing4_reset",
            mode="structure",
            activation_mfe_atr=3.5,
            structure_lookback=4,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe45_adx3_swing4_reset",
            mode="structure",
            activation_mfe_atr=4.5,
            structure_lookback=4,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adx2_swing4_reset",
            mode="structure",
            adx_weak_bars=2,
            structure_lookback=4,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adxfall2_swing2",
            mode="structure",
            adx_weakness_mode="falling",
            adx_weak_bars=2,
            structure_lookback=2,
        ),
        StructureExitConfig(
            "mfe40_adxfall2_swing2_reset",
            mode="structure",
            adx_weakness_mode="falling",
            adx_weak_bars=2,
            structure_lookback=2,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adxfall2_swing4_reset",
            mode="structure",
            adx_weakness_mode="falling",
            adx_weak_bars=2,
            structure_lookback=4,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adxdrop5_swing2_reset",
            mode="structure",
            adx_weakness_mode="peak_drop",
            adx_weak_bars=1,
            adx_peak_drop=5.0,
            structure_lookback=2,
            require_episode_reset=True,
        ),
        StructureExitConfig(
            "mfe40_adxdrop5_swing4_reset",
            mode="structure",
            adx_weakness_mode="peak_drop",
            adx_weak_bars=1,
            adx_peak_drop=5.0,
            structure_lookback=4,
            require_episode_reset=True,
        ),
    ]


def adverse_structure_break(
    *,
    frame: pd.DataFrame,
    bar: int,
    direction: int,
    lookback: int,
) -> bool:
    if bar < lookback:
        return False
    close = float(frame["close"].iloc[bar])
    prior = frame.iloc[bar - lookback : bar]
    if direction == 1:
        return close < float(prior["low"].min())
    return close > float(prior["high"].max())


def signal_direction(features: pd.DataFrame, signal_bar: int) -> int:
    is_long = bool(features["long_signal"].iloc[signal_bar])
    is_short = bool(features["short_signal"].iloc[signal_bar])
    if is_long and not is_short:
        return 1
    if is_short and not is_long:
        return -1
    return 0


def run_backtest(
    *,
    variant: StructureExitConfig,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> base.RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: StructurePosition | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    blocked_direction = 0
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
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

        if position is not None and pending_exit is not None:
            exited_direction = position.direction
            exit_reason = pending_exit
            equity, cost = base.close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=exit_reason,
                trades=trades,
                config=config,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            last_exit_bar = i
            exited_this_bar = True
            if exit_reason == "high_mfe_structure_exit" and variant.require_episode_reset:
                blocked_direction = exited_direction

        if position is not None:
            funding_pnl = -position.direction * position.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        signal_bar = i - config.entry_delay_bars
        current_signal = signal_direction(features, signal_bar)
        if blocked_direction != 0 and current_signal != blocked_direction:
            blocked_direction = 0

        if position is None and not exited_this_bar and i > last_exit_bar:
            direction = current_signal
            if direction == blocked_direction:
                direction = 0
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                target = config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
                allocation = min(config.max_allocation, target / (entry_atr / open_price))
                cost = config.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = StructurePosition(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )

        if position is not None:
            intrabar = base.check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
            )
            if intrabar is not None:
                reason, exit_price = intrabar
                equity, cost = base.close_position(
                    equity=equity,
                    position=position,
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (close / position.previous_price - 1.0)
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(
                    position,
                    high,
                    low,
                    config,
                    base.ProfitFloorConfig(enabled=False),
                )
                current_adx = float(features["adx"].iloc[i])
                adx_is_weak = current_adx < config.adx_exit

                if variant.mode == "never_disable":
                    position.weak_bars = position.weak_bars + 1 if adx_is_weak else 0
                    if position.weak_bars >= config.delayed_bars:
                        pending_exit = "indicator_exit"
                else:
                    can_early_exit = position.mfe_atr < config.disable_after_mfe_atr
                    position.weak_bars = position.weak_bars + 1 if can_early_exit and adx_is_weak else 0
                    if can_early_exit and position.weak_bars >= config.delayed_bars:
                        pending_exit = "indicator_exit"

                if variant.mode == "structure" and position.mfe_atr >= variant.activation_mfe_atr:
                    position.activation_adx_peak = max(position.activation_adx_peak, current_adx)
                    if variant.adx_weakness_mode == "below_threshold":
                        late_adx_is_weak = adx_is_weak
                    elif variant.adx_weakness_mode == "falling":
                        late_adx_is_weak = (
                            position.previous_adx is not None
                            and current_adx < position.previous_adx
                        )
                    elif variant.adx_weakness_mode == "peak_drop":
                        late_adx_is_weak = (
                            current_adx <= position.activation_adx_peak - variant.adx_peak_drop
                        )
                    else:
                        raise ValueError(
                            f"Unsupported ADX weakness mode: {variant.adx_weakness_mode}"
                        )
                    position.late_weak_bars = (
                        position.late_weak_bars + 1 if late_adx_is_weak else 0
                    )
                    position.previous_adx = current_adx
                    structure_broken = adverse_structure_break(
                        frame=frame,
                        bar=i,
                        direction=position.direction,
                        lookback=variant.structure_lookback,
                    )
                    if position.late_weak_bars >= variant.adx_weak_bars and structure_broken:
                        pending_exit = "high_mfe_structure_exit"

                if pending_exit is None and i - position.entry_bar >= config.max_hold_bars:
                    pending_exit = "timeout"

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)
        weight_values.append(0.0 if position is None else position.direction * position.allocation)

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=variant.name)
    returns = pd.Series(period_returns, index=index, name=f"{variant.name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{variant.name}_weight")
    trades_frame = pd.DataFrame(trades)
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    open_position = None
    if position is not None:
        open_position = base.open_position_summary(position, frame.index[-1])
        open_position["late_weak_bars"] = position.late_weak_bars
        open_position["blocked_direction"] = blocked_direction
    return base.RunResult(
        name=variant.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position,
    )


def latest_case(run: base.RunResult) -> dict[str, Any]:
    if not run.trades.empty:
        entry_ts = pd.to_datetime(run.trades["entry_ts"], utc=True)
        matched = run.trades.loc[entry_ts.eq(LATEST_CASE_ENTRY)]
        if not matched.empty:
            row = matched.iloc[0]
            return {
                "state": "closed",
                "entry_ts": pd.Timestamp(row["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(row["exit_ts"]).isoformat(),
                "entry_price": float(row["entry_price"]),
                "exit_price": float(row["exit_price"]),
                "entry_atr": float(row["entry_atr"]),
                "mfe_atr": float(row["mfe_atr"]),
                "exit_reason": str(row["exit_reason"]),
                "hold_bars": int(row["hold_bars"]),
                "trade_return_pct": base.pct(float(row["trade_return"])),
            }
    if run.open_position is not None and pd.Timestamp(run.open_position["entry_ts"]) == LATEST_CASE_ENTRY:
        return {"state": "open", **run.open_position}
    return {"state": "not_present"}


def summarize(run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "latest_case": latest_case(run),
        "delta_vs_base": {
            "return_pp": round(run.metrics["return_pct"] - baseline.metrics["return_pct"], 2),
            "max_drawdown_pp": round(
                run.metrics["max_drawdown_pct"] - baseline.metrics["max_drawdown_pct"],
                2,
            ),
            "sharpe": round(run.metrics["sharpe"] - baseline.metrics["sharpe"], 2),
            "win_rate_pp": round(
                run.metrics["win_rate_pct"] - baseline.metrics["win_rate_pct"],
                2,
            ),
        },
    }


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--source", choices=["binance_api", "data_lake"], default="binance_api")
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if args.source == "binance_api":
        frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    else:
        warehouse = base.DuckDBWarehouse(
            base.DataLakeLayout.from_settings(base.load_settings(None))
        )
        frame, funding, quality = base.load_data(warehouse)

    config = base.V35Config()
    features = ab.build_signals(base.build_features(frame, config), config, ab.SignalFlags())
    variant_configs = variants()
    def run_variants(
        run_frame: pd.DataFrame,
        run_funding: pd.Series,
        run_features: pd.DataFrame,
    ) -> list[base.RunResult]:
        return [
            run_backtest(
                variant=variant,
                frame=run_frame,
                funding=run_funding,
                features=run_features,
                config=config,
            )
            for variant in variant_configs
        ]

    runs = run_variants(frame, funding, features)
    baseline = runs[0]
    pre_frame = frame.loc[frame.index <= PRE_INCIDENT_END].copy()
    pre_funding = funding.reindex(pre_frame.index).fillna(0.0)
    pre_features = features.reindex(pre_frame.index)
    pre_runs = run_variants(pre_frame, pre_funding, pre_features)
    pre_baseline = pre_runs[0]
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 high-MFE ADX + price-structure exit diagnostic 2026-07-14",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "cost_model": (
            "V35 canonical override: 0.00085 per fill, representing fee plus "
            "4 bps adverse slippage; Binance funding included."
        ),
        "execution_model": {
            "entry": "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1.",
            "bracket": "Fixed entry-ATR 5.0 TP / 7.0 SL; intrabar stop-first.",
            "conditional_exit": (
                "After activation MFE, require the variant's ADX weakness definition "
                "(ADX28<22, consecutive decline, or a drop from post-activation peak) "
                "and current close beyond the adverse extreme of the preceding L completed "
                "bars; exit at next bar open."
            ),
            "episode_reset": (
                "For reset variants only, block same-direction re-entry until that direction's "
                "delayed entry signal becomes false at least once; opposite direction remains eligible."
            ),
            "anti_lookahead": (
                "Structure level excludes the current bar. ADX and structure are evaluated at close; "
                "the exit executes at the next open."
            ),
        },
        "selection_disclosure": (
            "Primary hypothesis fixed at MFE=4.0ATR, ADX weak bars=3 and prior 4-bar "
            "swing break. Lookback 2/8, activation 3.5/4.5 and ADX weak bars=2 are "
            "sensitivity diagnostics, not independent promotion candidates."
        ),
        "base_config": asdict(config),
        "variant_configs": [asdict(item) for item in variant_configs],
        "pre_incident_cutoff": PRE_INCIDENT_END.isoformat(),
        "pre_incident_runs": [
            summarize(run, pre_baseline) for run in pre_runs
        ],
        "runs": [summarize(run, baseline) for run in runs],
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)

    print(
        f"data: {quality.get('start')} ~ {quality.get('end')} "
        f"rows={quality.get('rows')} gaps={quality.get('missing_15m_bars')}"
    )
    print(f"\npre-incident cutoff: {PRE_INCIDENT_END.isoformat()}")
    for run in pre_runs:
        metrics = run.metrics
        print(
            f"{run.name:>30} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% sh {metrics['sharpe']:>4.2f} "
            f"n {metrics['trades']:>3} win {metrics['win_rate_pct']:>6.2f}%"
        )
    print("\nfull window including latest case:")
    for run in runs:
        metrics = run.metrics
        print(
            f"{run.name:>30} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% sh {metrics['sharpe']:>4.2f} "
            f"n {metrics['trades']:>3} win {metrics['win_rate_pct']:>6.2f}% "
            f"latest={latest_case(run)}"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
