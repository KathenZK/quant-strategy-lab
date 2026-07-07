from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_ema_tb_v37_v38_floor_2026-07-07.json"
TRADES_PATH = ARTIFACT_DIR / "hype_ema_tb_v37_v38_floor_trades_2026-07-07.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_ema_tb_v37_v38_floor_equity_2026-07-07.csv"


@dataclass(frozen=True, slots=True)
class SatelliteConfig:
    target_atr_pct: float = 0.008
    max_allocation: float = 1.0
    take_profit_atr: float = 4.0
    hard_stop_atr: float = 5.0
    entry_delay_bars: int = 2
    adx14_min: float = 35.0
    weak_adx14_exit: float = 22.0
    trade_cost_rate: float = 0.00085
    weak_exit_next_open: bool = True


@dataclass(slots=True)
class SatPosition:
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    pending_exit: str | None = None
    mfe_atr: float = 0.0


@dataclass(frozen=True, slots=True)
class LegResult:
    name: str
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    trades: pd.DataFrame
    equity_curve: pd.Series
    period_returns: pd.Series


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if args.source == "binance_api":
        frame, funding, quality = base.load_binance_api_data(args.since, args.until)
        base.save_api_inputs(frame, funding)
    else:
        warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
        frame, funding, quality = base.load_data(warehouse)

    config = base.V35Config()
    features = base.build_features(frame, config)
    features = add_satellite_features(features)
    sat_cfg = SatelliteConfig()
    v38_floor = base.ProfitFloorConfig(enabled=True, tiers=((4.75, 4.25),))

    v35 = wrap_main_result(
        base.run_backtest("v35_base", frame, funding, features, config, base.ProfitFloorConfig(enabled=False))
    )
    v38 = wrap_main_result(base.run_backtest("v38_floor_475_425", frame, funding, features, config, v38_floor))
    sat = run_satellite("v37_early_long_satellite", frame, funding, features, config, sat_cfg)
    v37 = combine_legs("v37_v35_plus_satellite", v35, sat)
    v37_v38 = combine_legs("v37_plus_v38_floor", v38, sat)

    runs = [v35, v38, sat, v37, v37_v38]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_ids": {
            "v38": "HYPE-EMA-TB-V38 = V35 + narrow profit floor (mfe>=4.75 locks 4.25ATR)",
            "v37_plus_v38": "HYPE-EMA-TB-V37 satellite overlay with V38 main-leg floor",
        },
        "source": args.source,
        "data_quality": quality,
        "execution_assumptions": {
            "main_leg": "Same V35 live-realistic K2-open replay; V38 only raises an active stop to +4.25ATR after MFE>=4.75ATR, effective next bar.",
            "satellite_leg": "V37 early-long reconstruction: V35 long preconditions except ADX28<28, ADX14>=35 and rising, +DI14>-DI14; K2 open entry; TP4/SL5; weak exit next open when ADX14<22.",
            "portfolio": "Main and satellite can overlap; combined equity uses per-bar main return + satellite return before compounding.",
            "cost": "0.00085 per fill; Binance funding aligned to 15m bars.",
        },
        "main_config": asdict(config),
        "satellite_config": asdict(sat_cfg),
        "v38_floor_config": asdict(v38_floor),
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "slices": run.slices,
                "last_trades": last_trades(run.trades, 8),
            }
            for run in runs
        ],
        "comparison": compare_runs(v35, v37, v38, v37_v38),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_artifacts(runs)
    print_summary(quality, runs)


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--source", choices=["data_lake", "binance_api"], default="binance_api")
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default="")
    return parser.parse_args()


def add_satellite_features(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    adx14, plus_di14, minus_di14 = base.adx_di(out, 14)
    out["adx14"] = adx14
    out["plus_di14"] = plus_di14
    out["minus_di14"] = minus_di14
    out["adx14_rising"] = out["adx14"].gt(out["adx14"].shift(1))
    out["satellite_long_signal"] = (
        out["ema_spread"].gt(0.0)
        & out["volume_surge"].ge(0.25)
        & out["h1_adx"].gt(18.0)
        & out["h1_plus_di"].gt(out["h1_minus_di"])
        & out["adx"].lt(28.0)
        & out["adx14"].ge(35.0)
        & out["adx14_rising"]
        & out["plus_di14"].gt(out["minus_di14"])
    )
    return out


def wrap_main_result(result: base.RunResult) -> LegResult:
    return LegResult(
        name=result.name,
        metrics=result.metrics,
        slices=result.slices,
        trades=result.trades,
        equity_curve=result.equity_curve,
        period_returns=result.period_returns,
    )


def run_satellite(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    main_cfg: base.V35Config,
    sat_cfg: SatelliteConfig,
) -> LegResult:
    start = max(main_cfg.warmup_bars, sat_cfg.entry_delay_bars + 1)
    equity = 1.0
    pos: SatPosition | None = None
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
            equity, cost = close_satellite(
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

        if pos is not None:
            funding_pnl = -pos.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        if pos is None and not exited_this_bar and i > last_exit_bar:
            sig_i = i - sat_cfg.entry_delay_bars
            entry_atr = float(features["atr"].iloc[i - 1])
            if (
                bool(features["satellite_long_signal"].iloc[sig_i])
                and np.isfinite(entry_atr)
                and entry_atr > 0.0
                and open_price > 0.0
            ):
                allocation = min(sat_cfg.max_allocation, sat_cfg.target_atr_pct / (entry_atr / open_price))
                cost = sat_cfg.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                pos = SatPosition(
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
                equity, cost = close_satellite(
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
                equity, cost = close_satellite(
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
                weak = float(features["adx14"].iloc[i]) < sat_cfg.weak_adx14_exit
                if weak:
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
    return LegResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
    )


def close_satellite(
    *,
    equity: float,
    pos: SatPosition,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    cfg: SatelliteConfig,
) -> tuple[float, float]:
    pnl = pos.allocation * (exit_price / pos.previous_price - 1.0)
    cost = cfg.trade_cost_rate * pos.allocation
    exit_equity = equity * (1.0 + pnl - cost)
    trades.append(
        {
            "entry_ts": pos.entry_ts,
            "exit_ts": exit_ts,
            "direction": 1,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "entry_atr": pos.entry_atr,
            "allocation": pos.allocation,
            "mfe_atr": pos.mfe_atr,
            "floor_offset_atr": 0.0,
            "exit_reason": reason,
            "entry_bar": pos.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - pos.entry_bar,
            "raw_price_return": exit_price / pos.entry_price - 1.0,
            "trade_return": exit_equity / pos.entry_equity - 1.0,
            "entry_equity": pos.entry_equity,
            "exit_equity": exit_equity,
        }
    )
    return exit_equity, cost


def combine_legs(name: str, main: LegResult, satellite: LegResult) -> LegResult:
    returns = main.period_returns.add(satellite.period_returns, fill_value=0.0).rename(f"{name}_return")
    equity_curve = (1.0 + returns).cumprod().rename(name)
    trades = pd.concat(
        [
            main.trades.assign(leg="main"),
            satellite.trades.assign(leg="satellite"),
        ],
        ignore_index=True,
    )
    weights = pd.Series(0.0, index=returns.index)
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades,
        trading_costs=0.0,
        funding_pnl=0.0,
    )
    return LegResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades),
        trades=trades,
        equity_curve=equity_curve,
        period_returns=returns,
    )


def compare_runs(v35: LegResult, v37: LegResult, v38: LegResult, v37_v38: LegResult) -> dict[str, Any]:
    return {
        "v38_vs_v35": metric_delta(v38, v35),
        "v37_vs_v35": metric_delta(v37, v35),
        "v37_plus_v38_vs_v37": metric_delta(v37_v38, v37),
        "v37_plus_v38_vs_v35": metric_delta(v37_v38, v35),
    }


def metric_delta(run: LegResult, base_run: LegResult) -> dict[str, Any]:
    return {
        "return_delta_pct": round(run.metrics["return_pct"] - base_run.metrics["return_pct"], 2),
        "max_drawdown_delta_pct": round(run.metrics["max_drawdown_pct"] - base_run.metrics["max_drawdown_pct"], 2),
        "sharpe_delta": round(run.metrics["sharpe"] - base_run.metrics["sharpe"], 2),
        "trade_delta": int(run.metrics["trades"] - base_run.metrics["trades"]),
    }


def last_trades(trades: pd.DataFrame, count: int) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    cols = [col for col in ["leg", "entry_ts", "exit_ts", "direction", "exit_reason", "mfe_atr", "trade_return", "hold_bars"] if col in trades.columns]
    out = trades.tail(count)[cols].copy()
    out["trade_return_pct"] = out["trade_return"].map(base.pct)
    return out.drop(columns=["trade_return"]).to_dict("records")


def write_artifacts(runs: list[LegResult]) -> None:
    equity = pd.concat([run.equity_curve.rename(run.name) for run in runs], axis=1)
    equity.to_csv(EQUITY_PATH, index_label="ts")
    trades = []
    for run in runs:
        if not run.trades.empty:
            trades.append(run.trades.assign(variant=run.name))
    if trades:
        pd.concat(trades, ignore_index=True).to_csv(TRADES_PATH, index=False)


def print_summary(quality: dict[str, Any], runs: list[LegResult]) -> None:
    print(f"data: {quality.get('start')} ~ {quality.get('end')} rows={quality.get('rows')}")
    print(f"summary -> {SUMMARY_PATH}")
    for run in runs:
        m = run.metrics
        print(
            f"{run.name:>26}  ret {m['return_pct']:>10.2f}%  dd {m['max_drawdown_pct']:>7.2f}%  "
            f"sharpe {m['sharpe']:>5.2f}  trades {m['trades']:>4}  win {m['win_rate_pct']:>6.2f}%  exits {m['exit_counts']}"
        )
    print()
    print("slice returns:")
    print("window  " + "  ".join(f"{run.name[:22]:>22}" for run in runs))
    for idx, item in enumerate(runs[0].slices):
        print(f"{item['window']:>6}  " + "  ".join(f"{run.slices[idx]['return_pct']:>22.2f}" for run in runs))


if __name__ == "__main__":
    main()
