from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_conditional_tp48_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"


@dataclass(frozen=True, slots=True)
class ConditionalTPConfig:
    name: str
    enabled: bool
    min_hold_bars: int = 96
    activation_mfe_atr: float = 4.5
    reduced_tp_atr: float = 4.8


def variants() -> list[ConditionalTPConfig]:
    return [
        ConditionalTPConfig("v35_base", enabled=False),
        ConditionalTPConfig("ctp_h12_m45_t48", enabled=True, min_hold_bars=48),
        ConditionalTPConfig("ctp_h24_m425_t48", enabled=True, activation_mfe_atr=4.25),
        ConditionalTPConfig("ctp_h24_m45_t48", enabled=True),
        ConditionalTPConfig("ctp_h24_m475_t48", enabled=True, activation_mfe_atr=4.75),
        ConditionalTPConfig("ctp_h36_m45_t48", enabled=True, min_hold_bars=144),
    ]


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def check_intrabar_exit(
    *,
    position: base.Position,
    open_price: float,
    high: float,
    low: float,
    config: base.V35Config,
    conditional_active: bool,
    reduced_tp_atr: float,
) -> tuple[str, float] | None:
    take_atr = reduced_tp_atr if conditional_active else config.take_profit_atr
    take = position.entry_price + position.direction * take_atr * position.entry_atr
    hard_stop = position.entry_price - position.direction * config.hard_stop_atr * position.entry_atr
    if position.direction == 1:
        if low <= hard_stop:
            return "stop_loss", hard_stop
        if open_price >= take:
            reason = "conditional_take_profit" if conditional_active else "take_profit"
            return reason, open_price
        if high >= take:
            reason = "conditional_take_profit" if conditional_active else "take_profit"
            return reason, take
    else:
        if high >= hard_stop:
            return "stop_loss", hard_stop
        if open_price <= take:
            reason = "conditional_take_profit" if conditional_active else "take_profit"
            return reason, open_price
        if low <= take:
            reason = "conditional_take_profit" if conditional_active else "take_profit"
            return reason, take
    return None


def close_position(
    *,
    equity: float,
    position: base.Position,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    config: base.V35Config,
    conditional_active: bool,
    activation_ts: pd.Timestamp | None,
    activation_mfe_atr: float | None,
    reduced_tp_atr: float,
) -> tuple[float, float]:
    result = base.close_position(
        equity=equity,
        position=position,
        exit_price=exit_price,
        exit_ts=exit_ts,
        exit_bar=exit_bar,
        reason=reason,
        trades=trades,
        config=config,
    )
    trades[-1].update(
        {
            "conditional_tp_active": conditional_active,
            "conditional_tp_activation_ts": activation_ts,
            "conditional_tp_activation_mfe_atr": activation_mfe_atr,
            "effective_take_profit_atr": reduced_tp_atr
            if conditional_active
            else config.take_profit_atr,
        }
    )
    return result


def run_backtest(
    *,
    variant: ConditionalTPConfig,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> base.RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    conditional_active = False
    activation_ts: pd.Timestamp | None = None
    activation_mfe_atr: float | None = None
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    no_floor = base.ProfitFloorConfig(enabled=False)

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, cost = close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
                conditional_active=conditional_active,
                activation_ts=activation_ts,
                activation_mfe_atr=activation_mfe_atr,
                reduced_tp_atr=variant.reduced_tp_atr,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_pnl = -position.direction * position.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        if position is None and not exited_this_bar and i > last_exit_bar:
            signal_i = i - config.entry_delay_bars
            direction = 0
            if bool(features["long_signal"].iloc[signal_i]) and not bool(
                features["short_signal"].iloc[signal_i]
            ):
                direction = 1
            elif bool(features["short_signal"].iloc[signal_i]) and not bool(
                features["long_signal"].iloc[signal_i]
            ):
                direction = -1
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0:
                target = (
                    config.long_target_atr_pct
                    if direction == 1
                    else config.short_target_atr_pct
                )
                allocation = min(config.max_allocation, target / (entry_atr / open_price))
                cost = config.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = base.Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )
                conditional_active = False
                activation_ts = None
                activation_mfe_atr = None

        if position is not None:
            intrabar = check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
                conditional_active=conditional_active,
                reduced_tp_atr=variant.reduced_tp_atr,
            )
            if intrabar is not None:
                reason, exit_price = intrabar
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                    conditional_active=conditional_active,
                    activation_ts=activation_ts,
                    activation_mfe_atr=activation_mfe_atr,
                    reduced_tp_atr=variant.reduced_tp_atr,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (
                    close / position.previous_price - 1.0
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(position, high, low, config, no_floor)
                if (
                    variant.enabled
                    and not conditional_active
                    and i - position.entry_bar >= variant.min_hold_bars
                    and position.mfe_atr >= variant.activation_mfe_atr
                ):
                    conditional_active = True
                    activation_ts = ts
                    activation_mfe_atr = position.mfe_atr
                can_indicator_exit = position.mfe_atr < config.disable_after_mfe_atr
                if can_indicator_exit and float(features["adx"].iloc[i]) < config.adx_exit:
                    position.weak_bars += 1
                else:
                    position.weak_bars = 0
                if can_indicator_exit and position.weak_bars >= config.delayed_bars:
                    pending_exit = "indicator_exit"
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
    return base.RunResult(
        name=variant.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=None,
    )


def hold_stats(trades: pd.DataFrame) -> dict[str, Any]:
    hold = trades["hold_bars"] * 0.25
    tp = trades.loc[
        trades["exit_reason"].isin(["take_profit", "conditional_take_profit"]),
        "hold_bars",
    ] * 0.25
    return {
        "mean_hours": round(float(hold.mean()), 2),
        "median_hours": round(float(hold.median()), 2),
        "p90_hours": round(float(hold.quantile(0.90)), 2),
        "max_hours": round(float(hold.max()), 2),
        "over_24h": int((hold > 24.0).sum()),
        "over_48h": int((hold > 48.0).sum()),
        "tp_mean_hours": round(float(tp.mean()), 2),
        "tp_median_hours": round(float(tp.median()), 2),
        "tp_p90_hours": round(float(tp.quantile(0.90)), 2),
        "tp_max_hours": round(float(tp.max()), 2),
    }


def latest_path(trades: pd.DataFrame) -> list[dict[str, Any]]:
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out = out.loc[out["entry_ts"] >= pd.Timestamp("2026-07-03T00:00:00Z")].copy()
    out["hold_hours"] = out["hold_bars"] * 0.25
    out["trade_return_pct"] = out["trade_return"] * 100.0
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "entry_atr",
        "mfe_atr",
        "hold_hours",
        "conditional_tp_active",
        "conditional_tp_activation_ts",
        "conditional_tp_activation_mfe_atr",
        "effective_take_profit_atr",
        "exit_reason",
        "trade_return_pct",
    ]
    return out[columns].to_dict("records")


def summarize(
    variant: ConditionalTPConfig,
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    return {
        "variant": asdict(variant),
        "metrics": run.metrics,
        "capital_retention_vs_base_pct": round(
            float(run.equity_curve.iloc[-1] / baseline.equity_curve.iloc[-1] * 100.0),
            2,
        ),
        "conditional_activations": int(
            run.trades["conditional_tp_activation_ts"].notna().sum()
        ),
        "conditional_tp_exits": int(
            run.trades["exit_reason"].eq("conditional_take_profit").sum()
        ),
        "hold_stats": hold_stats(run.trades),
        "standard_slices": run.slices,
        "latest_path": latest_path(run.trades),
    }


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    config = base.V35Config()
    features = base.build_features(frame, config)
    configs = variants()
    runs = [
        run_backtest(
            variant=variant,
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        for variant in configs
    ]
    canonical_base = base.run_backtest(
        "canonical_base",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    baseline = runs[0]
    if baseline.metrics != canonical_base.metrics or not baseline.trades.equals(
        canonical_base.trades.assign(
            conditional_tp_active=False,
            conditional_tp_activation_ts=None,
            conditional_tp_activation_mfe_atr=None,
            effective_take_profit_atr=config.take_profit_atr,
        )
    ):
        raise RuntimeError("Custom engine failed canonical V35 parity.")

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 conditional TP4.8 after 24h/MFE4.5",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "base_config": asdict(config),
        "execution_model": {
            "entry": "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1.",
            "base_bracket": "Fixed entry-ATR 5TP / 7SL; intrabar stop-first.",
            "conditional_tp": (
                "After a closed bar, if elapsed bars and MFE gates both pass, amend TP "
                "from 5ATR to 4.8ATR. The amended TP is active from the next 15m bar."
            ),
            "cost": (
                "V35 canonical 0.00085 per fill, including fee and 4 bps adverse "
                "slippage; Binance funding included."
            ),
        },
        "selection_disclosure": (
            "The exact 24h/MFE4.5/TP4.8 rule was proposed after observing two near-TP "
            "live trades and is post-hoc. Sensitivity variants are diagnostic only."
        ),
        "engine_parity": "PASS: disabled conditional engine equals canonical V35 trades and metrics.",
        "rows": [
            summarize(variant, run, baseline)
            for variant, run in zip(configs, runs, strict=True)
        ],
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
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"gaps={quality['missing_15m_bars']}"
    )
    for row in payload["rows"]:
        metrics = row["metrics"]
        hold = row["hold_stats"]
        print(
            f"{row['variant']['name']:>20} ret={metrics['return_pct']:>8.2f}% "
            f"dd={metrics['max_drawdown_pct']:>7.2f}% sh={metrics['sharpe']:>4.2f} "
            f"acts={row['conditional_activations']:>2} exits={row['conditional_tp_exits']:>2} "
            f"median={hold['median_hours']:>5.2f}h max={hold['max_hours']:>5.2f}h"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
