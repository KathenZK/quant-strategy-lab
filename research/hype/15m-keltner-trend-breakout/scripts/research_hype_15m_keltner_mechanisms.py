"""测试三条预先冻结的 HYPE 15m Keltner 新机制假设。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_15m_keltner_only as base


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-keltner-trend-breakout"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
OUT_STEM = "hype_15m_keltner_mechanism_hypotheses_2026-07-21"


@dataclass(frozen=True, slots=True)
class HypothesisSpec:
    name: str
    mechanism: str
    description: str
    entry_delay_bars: int = 1

    def validate(self) -> None:
        if self.entry_delay_bars not in {1, 2}:
            raise ValueError("entry_delay_bars must be 1 or 2")


@dataclass(slots=True)
class Position:
    direction: int
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    signal_bar: int
    signal_ts: pd.Timestamp


@dataclass(frozen=True, slots=True)
class RunResult:
    spec: HypothesisSpec
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    time_splits: list[dict[str, Any]]
    trades: pd.DataFrame
    equity_curve: pd.Series
    period_returns: pd.Series
    open_position: dict[str, Any] | None


def build_hypothesis_signals(
    features: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    close = features["close"]
    center = features["center"]
    upper = features["upper"]
    lower = features["lower"]
    width_pct = (upper - lower) / center

    outer_long = close.gt(upper) & close.shift(1).le(upper.shift(1))
    outer_short = close.lt(lower) & close.shift(1).ge(lower.shift(1))

    width_q25 = width_pct.rolling(192, min_periods=192).quantile(0.25)
    compressed = width_pct.le(width_q25)
    recent_compression = (
        compressed.shift(1).rolling(16, min_periods=1).max().fillna(0.0).astype(bool)
    )
    expanding = width_pct.gt(width_pct.shift(1))

    recent_upper_touch = (
        close.gt(upper).shift(1).rolling(32, min_periods=1).max().fillna(0.0).astype(bool)
    )
    recent_lower_touch = (
        close.lt(lower).shift(1).rolling(32, min_periods=1).max().fillna(0.0).astype(bool)
    )
    center_rising = center.gt(center.shift(32))
    center_falling = center.lt(center.shift(32))
    midline_long = (
        recent_upper_touch
        & center_rising
        & close.shift(1).le(center.shift(1))
        & close.gt(center)
        & close.lt(upper)
    )
    midline_short = (
        recent_lower_touch
        & center_falling
        & close.shift(1).ge(center.shift(1))
        & close.lt(center)
        & close.gt(lower)
    )

    definitions = {
        "outer_break_mid_exit": (outer_long, outer_short),
        "compression_expansion_break": (
            outer_long & recent_compression & expanding,
            outer_short & recent_compression & expanding,
        ),
        "trend_pullback_mid_reclaim": (midline_long, midline_short),
    }
    outputs: dict[str, pd.DataFrame] = {}
    for name, (long_signal, short_signal) in definitions.items():
        conflict = long_signal & short_signal
        if bool(conflict.any()):
            raise RuntimeError(f"{name} has conflicting long/short signals")
        out = features.copy()
        out["width_pct"] = width_pct
        out["long_signal"] = long_signal.fillna(False)
        out["short_signal"] = short_signal.fillna(False)
        outputs[name] = out
    return outputs


def stop_exit(
    position: Position,
    *,
    open_price: float,
    high: float,
    low: float,
    config: base.KeltnerConfig,
) -> tuple[str, float] | None:
    stop = (
        position.entry_price
        - position.direction * config.hard_stop_atr * position.entry_atr
    )
    if position.direction == 1:
        if open_price <= stop:
            return "stop_loss_gap", open_price
        if low <= stop:
            return "stop_loss", stop
    else:
        if open_price >= stop:
            return "stop_loss_gap", open_price
        if high >= stop:
            return "stop_loss", stop
    return None


def close_position(
    *,
    equity: float,
    position: Position,
    raw_exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    config: base.KeltnerConfig,
    trades: list[dict[str, Any]],
) -> tuple[float, float]:
    exit_price = base.adverse_fill(
        raw_exit_price,
        position.direction,
        is_entry=False,
        config=config,
    )
    pnl = (
        position.direction
        * position.allocation
        * (exit_price / position.previous_price - 1.0)
    )
    equity *= 1.0 + pnl
    fee = config.fee_per_fill * position.allocation
    equity *= 1.0 - fee
    trades.append(
        {
            "signal_ts": position.signal_ts,
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "exit_reason": reason,
            "raw_price_return": (
                position.direction * (exit_price / position.entry_price - 1.0)
            ),
            "trade_return": equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": equity,
        }
    )
    return equity, fee


def run_backtest(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    spec: HypothesisSpec,
    config: base.KeltnerConfig,
) -> RunResult:
    spec.validate()
    start = max(config.warmup_bars, spec.entry_delay_bars + 1)
    equity = 1.0
    position: Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -10_000
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    period_returns: list[float] = []
    timestamps: list[pd.Timestamp] = []
    trading_cost_rate_total = 0.0
    funding_rate_total = 0.0

    for i in range(start, len(frame)):
        ts = pd.Timestamp(frame.index[i])
        start_equity = equity
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, fee = close_position(
                equity=equity,
                position=position,
                raw_exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                config=config,
                trades=trades,
            )
            trading_cost_rate_total += fee
            position = None
            pending_exit = None
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_effect = (
                -position.direction * position.allocation * float(funding.iloc[i])
            )
            equity *= 1.0 + funding_effect
            funding_rate_total += funding_effect

        cooldown_complete = i > last_exit_bar + config.cooldown_bars
        if position is None and not exited_this_bar and cooldown_complete:
            signal_bar = i - spec.entry_delay_bars
            long_signal = bool(features["long_signal"].iloc[signal_bar])
            short_signal = bool(features["short_signal"].iloc[signal_bar])
            direction = (
                1
                if long_signal and not short_signal
                else -1
                if short_signal and not long_signal
                else 0
            )
            entry_atr = float(features["sizing_atr"].iloc[i - 1])
            if direction and np.isfinite(entry_atr) and entry_atr > 0.0:
                allocation = 1.0
                entry_price = base.adverse_fill(
                    open_price,
                    direction,
                    is_entry=True,
                    config=config,
                )
                entry_equity = equity
                fee = config.fee_per_fill * allocation
                equity *= 1.0 - fee
                trading_cost_rate_total += fee
                position = Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=entry_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=entry_equity,
                    previous_price=entry_price,
                    signal_bar=signal_bar,
                    signal_ts=pd.Timestamp(frame.index[signal_bar]),
                )

        if position is not None:
            hit = stop_exit(
                position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
            )
            if hit is not None:
                reason, raw_exit_price = hit
                equity, fee = close_position(
                    equity=equity,
                    position=position,
                    raw_exit_price=raw_exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    config=config,
                    trades=trades,
                )
                trading_cost_rate_total += fee
                position = None
                last_exit_bar = i
            else:
                pnl = (
                    position.direction
                    * position.allocation
                    * (close / position.previous_price - 1.0)
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                crossed_midline = (
                    position.direction == 1
                    and close < float(features["center"].iloc[i])
                ) or (
                    position.direction == -1
                    and close > float(features["center"].iloc[i])
                )
                if crossed_midline:
                    pending_exit = "midline_exit_next_open"
                elif i - position.entry_bar + 1 >= config.max_hold_bars:
                    pending_exit = "timeout_next_open"

        timestamps.append(ts)
        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)

    index = pd.DatetimeIndex(timestamps)
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
    returns = pd.Series(period_returns, index=index, name=spec.name)
    trades_frame = pd.DataFrame(trades)
    metrics = base.metrics_from_series(
        equity_curve,
        returns,
        trades_frame,
        trading_cost_rate_total=trading_cost_rate_total,
        funding_rate_total=funding_rate_total,
    )
    slices = [
        base.slice_metrics(name, delta, equity_curve, returns, trades_frame)
        for name, delta in base.RECENT_WINDOWS.items()
    ]
    time_splits = chronological_splits(equity_curve, returns, trades_frame)
    open_position = None
    if position is not None:
        open_position = {
            "direction": position.direction,
            "entry_ts": position.entry_ts.isoformat(),
            "entry_price": position.entry_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "hold_bars": int(len(frame) - 1 - position.entry_bar),
            "pending_exit": pending_exit,
            "unrealized_trade_return_pct": round(
                (equity / position.entry_equity - 1.0) * 100.0,
                6,
            ),
        }
    return RunResult(
        spec=spec,
        metrics=metrics,
        slices=slices,
        time_splits=time_splits,
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position,
    )


def chronological_splits(
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
) -> list[dict[str, Any]]:
    n = len(equity)
    boundaries = [0, int(n * 0.50), int(n * 0.75), n]
    names = ["development", "validation", "test"]
    rows = []
    for idx, name in enumerate(names):
        start_pos = boundaries[idx]
        end_pos = boundaries[idx + 1]
        selected_equity = equity.iloc[start_pos:end_pos]
        selected_returns = returns.iloc[start_pos:end_pos]
        start_ts = selected_equity.index[0]
        end_ts = selected_equity.index[-1]
        base_equity = (
            float(equity.iloc[start_pos - 1]) if start_pos > 0 else 1.0
        )
        normalized = pd.concat(
            [
                pd.Series(
                    [base_equity],
                    index=[start_ts - pd.Timedelta(minutes=15)],
                ),
                selected_equity,
            ]
        )
        selected_trades = (
            trades.loc[
                pd.to_datetime(trades["exit_ts"], utc=True).between(
                    start_ts,
                    end_ts,
                    inclusive="both",
                )
            ]
            if not trades.empty
            else trades
        )
        rows.append(
            {
                "split": name,
                "start": start_ts.isoformat(),
                "end": end_ts.isoformat(),
                "return_pct": float(
                    (selected_equity.iloc[-1] / base_equity - 1.0) * 100.0
                ),
                "max_drawdown_pct": base.max_drawdown_pct(normalized),
                "sharpe": base.sharpe_ratio(selected_returns),
                "trades": int(len(selected_trades)),
                "win_rate_pct": (
                    float(
                        (
                            selected_trades["trade_return"].astype(float) > 0.0
                        ).mean()
                        * 100.0
                    )
                    if not selected_trades.empty
                    else 0.0
                ),
            }
        )
    return rows


def viability_gate(run: RunResult) -> dict[str, Any]:
    split_returns = {
        row["split"]: float(row["return_pct"]) for row in run.time_splits
    }
    recent = {row["window"]: row for row in run.slices}
    checks = {
        "full_return_positive": run.metrics["return_pct"] > 0.0,
        "full_maxdd_not_worse_than_35pct": run.metrics["max_drawdown_pct"] >= -35.0,
        "minimum_30_closed_trades": run.metrics["trades"] >= 30,
        "development_positive": split_returns["development"] > 0.0,
        "validation_positive": split_returns["validation"] > 0.0,
        "test_positive": split_returns["test"] > 0.0,
        "recent_3m_positive": recent["3m"]["return_pct"] > 0.0,
        "recent_6m_positive": recent["6m"]["return_pct"] > 0.0,
    }
    return {
        "checks": checks,
        "passed": bool(all(checks.values())),
        "passed_count": int(sum(checks.values())),
        "total_count": int(len(checks)),
    }


def serialize_run(run: RunResult) -> dict[str, Any]:
    return {
        "spec": asdict(run.spec),
        "metrics": run.metrics,
        "slices": run.slices,
        "time_splits": run.time_splits,
        "viability_gate": viability_gate(run),
        "open_position": run.open_position,
    }


def write_artifacts(runs: list[RunResult], payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / f"{OUT_STEM}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    trade_frames = []
    for run in runs:
        frame = run.trades.copy()
        frame.insert(0, "variant", run.spec.name)
        trade_frames.append(frame)
    pd.concat(trade_frames, ignore_index=True).to_csv(
        ARTIFACT_DIR / f"{OUT_STEM}_trades.csv",
        index=False,
    )
    pd.concat(
        [run.equity_curve.rename(run.spec.name) for run in runs],
        axis=1,
    ).to_csv(ARTIFACT_DIR / f"{OUT_STEM}_equity.csv", index_label="ts")


def print_run(run: RunResult) -> None:
    metrics = run.metrics
    gate = viability_gate(run)
    print(
        f"{run.spec.name:>38} | "
        f"ret {metrics['return_pct']:>8.2f}% "
        f"dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>5.2f} "
        f"n {metrics['trades']:>4} "
        f"win {metrics['win_rate_pct']:>6.2f}% "
        f"gate {gate['passed_count']}/{gate['total_count']}"
    )
    split_text = " | ".join(
        f"{row['split']} {row['return_pct']:+.2f}%/{row['max_drawdown_pct']:.2f}%/{row['trades']}"
        for row in run.time_splits
    )
    print(f"  {split_text}")
    recent = {row["window"]: row for row in run.slices}
    print(
        f"  recent 1m {recent['1m']['return_pct']:+.2f}% "
        f"3m {recent['3m']['return_pct']:+.2f}% "
        f"6m {recent['6m']['return_pct']:+.2f}% "
        f"1y {recent['1y']['return_pct']:+.2f}%"
    )


def main() -> None:
    config = base.KeltnerConfig(
        hard_stop_atr=4.0,
        max_hold_bars=192,
        cooldown_bars=4,
    )
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = base.load_data(warehouse)
    features = base.build_features(frame, config)
    signals = build_hypothesis_signals(features)
    descriptions = {
        "outer_break_mid_exit": (
            "外轨首次穿越入场；收盘回到中轨另一侧后下一根 open 退出。"
        ),
        "compression_expansion_break": (
            "过去16根出现通道宽度192根25分位压缩，宽度重新扩张时外轨穿越入场；中轨退出。"
        ),
        "trend_pullback_mid_reclaim": (
            "过去32根触及同向外轨，中轨32根斜率同向；价格回踩中轨后 reclaim 入场；再失守中轨退出。"
        ),
    }
    specs = [
        HypothesisSpec(
            name=f"{mechanism}_k{delay}",
            mechanism=mechanism,
            description=description,
            entry_delay_bars=delay,
        )
        for mechanism, description in descriptions.items()
        for delay in (1, 2)
    ]
    runs = [
        run_backtest(
            frame,
            funding,
            signals[spec.mechanism],
            spec,
            config,
        )
        for spec in specs
    ]
    gross_config = replace(
        config,
        fee_per_fill=0.0,
        adverse_slippage_per_fill=0.0,
    )
    gross_runs = [
        run_backtest(
            frame,
            funding,
            signals[spec.mechanism],
            replace(spec, name=f"{spec.mechanism}_k1_gross_cost_ablation"),
            gross_config,
        )
        for spec in specs
        if spec.entry_delay_bars == 1
    ]
    payload = {
        "strategy_family": "HYPE-15M-Keltner-Trend-Breakout",
        "research_id": "HYPE-15M-KTB frozen mechanism hypotheses",
        "status": "explore / not promoted / not live-ready",
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "data_quality": quality,
        "selection_policy": (
            "Three mechanisms and all parameters were frozen before execution. "
            "K1 is primary and K2 is phase sensitivity only. No grid search; "
            "time splits and recent slices were not used to tune parameters."
        ),
        "shared_execution": {
            "signal": "closed K0 only",
            "entry": "K1 open primary; K2 open phase audit",
            "sizing": "fixed 1x",
            "emergency_stop": "4 x entry ATR672, gap-open worse fill",
            "normal_exit": "closed-bar midline cross, next open",
            "timeout": "192 bars, next open",
            "cooldown": "4 complete 15m bars",
            "cost": "0.001 fee + 0.0004 adverse slippage per fill",
            "funding": "actual Binance funding included",
        },
        "keltner": {
            "center": "EMA96 adjust=False min_periods=96",
            "channel_atr": "arithmetic rolling mean true range, 144 bars",
            "multiplier": 2.4,
            "sizing_atr": "arithmetic rolling mean true range, 672 bars",
        },
        "config": asdict(config),
        "hypotheses": descriptions,
        "viability_gate": (
            "full return > 0; MaxDD >= -35%; >=30 trades; development, "
            "validation, test, recent 3m and recent 6m returns all > 0"
        ),
        "runs": [serialize_run(run) for run in runs],
        "gross_cost_ablation": {
            "purpose": (
                "Diagnostic only: K1 paths with fee and slippage set to zero; "
                "actual funding retained. Not eligible for selection."
            ),
            "runs": [serialize_run(run) for run in gross_runs],
        },
    }
    write_artifacts(runs, payload)
    print(
        f"data {quality['start']} -> {quality['end']} "
        f"rows={quality['rows']} blockers={quality['blocker_count']}"
    )
    for run in runs:
        print_run(run)
    print("gross cost ablation (funding retained):")
    for run in gross_runs:
        print_run(run)
    print(f"artifacts -> {ARTIFACT_DIR / OUT_STEM}")


if __name__ == "__main__":
    main()
