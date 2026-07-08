from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_low_atr_overlays_2026-07-08.json"
TRADES_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_low_atr_overlays_trades_2026-07-08.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_ema_tb_v35_low_atr_overlays_equity_2026-07-08.csv"


@dataclass(frozen=True, slots=True)
class OverlayConfig:
    name: str
    global_max_allocation: float | None = None
    low_atr_threshold: float | None = None
    low_atr_max_allocation: float | None = None
    very_low_atr_threshold: float | None = None
    very_low_atr_max_allocation: float | None = None
    low_adx_threshold: float | None = None
    low_adx_max_allocation: float | None = None
    strict_low_atr_threshold: float | None = None
    strict_long_adx_min: float = 32.0
    strict_short_adx_min: float = 40.0
    strict_long_vol_min: float = 0.35
    strict_short_vol_min: float = 0.60
    strict_h1_long_adx_min: float = 20.0
    use_v38_floor: bool = False


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)
    config = base.V35Config()
    features = base.build_features(frame, config)
    variants = [
        OverlayConfig(name="v35_base"),
        OverlayConfig(name="global_cap25", global_max_allocation=2.5),
        OverlayConfig(name="global_cap2", global_max_allocation=2.0),
        OverlayConfig(name="global_cap15", global_max_allocation=1.5),
        OverlayConfig(name="low_atr_cap2", low_atr_threshold=0.0065, low_atr_max_allocation=2.0),
        OverlayConfig(name="very_low_atr_cap15", very_low_atr_threshold=0.0055, very_low_atr_max_allocation=1.5),
        OverlayConfig(
            name="low_atr_tiered_cap",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.0,
            very_low_atr_threshold=0.0055,
            very_low_atr_max_allocation=1.5,
        ),
        OverlayConfig(name="low_atr_strict_entry", strict_low_atr_threshold=0.0065),
        OverlayConfig(name="all_strict_entry", strict_low_atr_threshold=1.0),
        OverlayConfig(name="low_adx_cap2", low_adx_threshold=35.0, low_adx_max_allocation=2.0),
        OverlayConfig(name="low_adx_cap15", low_adx_threshold=35.0, low_adx_max_allocation=1.5),
        OverlayConfig(name="low_adx35_cap25", low_adx_threshold=35.0, low_adx_max_allocation=2.5),
        OverlayConfig(name="low_adx32_cap2", low_adx_threshold=32.0, low_adx_max_allocation=2.0),
        OverlayConfig(name="low_adx32_cap25", low_adx_threshold=32.0, low_adx_max_allocation=2.5),
        OverlayConfig(
            name="low_atr_or_low_adx_cap25",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.5,
            low_adx_threshold=35.0,
            low_adx_max_allocation=2.5,
        ),
        OverlayConfig(
            name="low_atr_or_adx32_cap2",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.0,
            low_adx_threshold=32.0,
            low_adx_max_allocation=2.0,
        ),
        OverlayConfig(
            name="low_atr_or_low_adx_cap2",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.0,
            low_adx_threshold=35.0,
            low_adx_max_allocation=2.0,
        ),
        OverlayConfig(
            name="low_atr_cap2_strict_entry",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.0,
            strict_low_atr_threshold=0.0065,
        ),
        OverlayConfig(
            name="low_atr_tiered_cap_strict_entry",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.0,
            very_low_atr_threshold=0.0055,
            very_low_atr_max_allocation=1.5,
            strict_low_atr_threshold=0.0065,
        ),
        OverlayConfig(
            name="low_atr_cap2_strict_entry_v38",
            low_atr_threshold=0.0065,
            low_atr_max_allocation=2.0,
            strict_low_atr_threshold=0.0065,
            use_v38_floor=True,
        ),
    ]
    runs = [run_overlay(frame, funding, features, config, overlay) for overlay in variants]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V35 low-ATR overlay backtest",
        "data_quality": quality,
        "base_config": asdict(config),
        "overlay_configs": {overlay.name: asdict(overlay) for overlay in variants},
        "assumptions": {
            "data": "Updated Binance HYPEUSDT 15m data lake through the latest closed bar.",
            "execution": "Same V35 K0 close / K2 open / entry ATR from K1 / intrabar TP-SL model.",
            "overlay_scope": "Only entry-time allocation caps and low-ATR entry gates are changed; V35 exits remain unchanged unless use_v38_floor=True.",
            "cost": "V35 canonical 0.00085 per fill, including fee plus adverse slippage.",
        },
        "runs": [summarize_run(run) for run in runs],
        "comparison": compare_to_base(runs),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_artifacts(runs)
    print_summary(runs)


def run_overlay(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
    overlay: OverlayConfig,
) -> base.RunResult:
    floor_cfg = (
        base.ProfitFloorConfig(enabled=True, tiers=((4.75, 4.25),))
        if overlay.use_v38_floor
        else base.ProfitFloorConfig(enabled=False)
    )
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    entry_blocked_until = -1
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
            equity, cost = base.close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
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

        if position is None and not exited_this_bar and i > last_exit_bar and i > entry_blocked_until:
            signal_i = i - config.entry_delay_bars
            direction = entry_direction(features, signal_i, overlay)
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                entry_atr_pct = entry_atr / open_price
                if passes_entry_overlay(features, signal_i, direction, entry_atr_pct, overlay):
                    target = config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
                    dynamic_cap = allocation_cap(config, overlay, features, signal_i, entry_atr_pct)
                    allocation = min(dynamic_cap, target / entry_atr_pct)
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
                if reason == "profit_floor" and floor_cfg.cooldown_bars_after_floor > 0:
                    entry_blocked_until = i + floor_cfg.cooldown_bars_after_floor
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (close / position.previous_price - 1.0)
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(position, high, low, config, floor_cfg)
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
    equity_curve = pd.Series(equity_values, index=index, name=overlay.name)
    returns = pd.Series(period_returns, index=index, name=f"{overlay.name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{overlay.name}_weight")
    trades_frame = pd.DataFrame(trades)
    if not trades_frame.empty:
        trades_frame["overlay"] = overlay.name
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    return base.RunResult(
        name=overlay.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=base.open_position_summary(position, frame.index[-1]) if position is not None else None,
    )


def entry_direction(features: pd.DataFrame, signal_i: int, overlay: OverlayConfig) -> int:
    long_signal = bool(features["long_signal"].iloc[signal_i])
    short_signal = bool(features["short_signal"].iloc[signal_i])
    if long_signal and not short_signal:
        return 1
    if short_signal and not long_signal:
        return -1
    return 0


def passes_entry_overlay(
    features: pd.DataFrame,
    signal_i: int,
    direction: int,
    entry_atr_pct: float,
    overlay: OverlayConfig,
) -> bool:
    if overlay.strict_low_atr_threshold is None or entry_atr_pct >= overlay.strict_low_atr_threshold:
        return True
    row = features.iloc[signal_i]
    if direction == 1:
        return (
            float(row["adx"]) >= overlay.strict_long_adx_min
            and float(row["volume_surge"]) >= overlay.strict_long_vol_min
            and float(row["h1_adx"]) > overlay.strict_h1_long_adx_min
        )
    return float(row["adx"]) >= overlay.strict_short_adx_min and float(row["volume_surge"]) >= overlay.strict_short_vol_min


def allocation_cap(
    config: base.V35Config,
    overlay: OverlayConfig,
    features: pd.DataFrame,
    signal_i: int,
    entry_atr_pct: float,
) -> float:
    cap = config.max_allocation
    if overlay.global_max_allocation is not None:
        cap = min(cap, overlay.global_max_allocation)
    if overlay.low_atr_threshold is not None and entry_atr_pct < overlay.low_atr_threshold:
        cap = min(cap, overlay.low_atr_max_allocation or cap)
    if overlay.very_low_atr_threshold is not None and entry_atr_pct < overlay.very_low_atr_threshold:
        cap = min(cap, overlay.very_low_atr_max_allocation or cap)
    if overlay.low_adx_threshold is not None and float(features["adx"].iloc[signal_i]) < overlay.low_adx_threshold:
        cap = min(cap, overlay.low_adx_max_allocation or cap)
    return cap


def summarize_run(run: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "slices": run.slices,
        "recent_90d": slice_by_window(run, "3m"),
        "recent_30d": slice_by_window(run, "1m"),
        "open_position": run.open_position,
        "exit_counts": run.metrics.get("exit_counts", {}),
        "last_trades": last_trades(run.trades, 8),
    }


def compare_to_base(runs: list[base.RunResult]) -> list[dict[str, Any]]:
    base_run = runs[0]
    rows = []
    for run in runs[1:]:
        rows.append(
            {
                "name": run.name,
                "full_return_delta_pct": round(run.metrics["return_pct"] - base_run.metrics["return_pct"], 2),
                "full_maxdd_delta_pct": round(run.metrics["max_drawdown_pct"] - base_run.metrics["max_drawdown_pct"], 2),
                "full_sharpe_delta": round(run.metrics["sharpe"] - base_run.metrics["sharpe"], 2),
                "full_trade_delta": int(run.metrics["trades"] - base_run.metrics["trades"]),
                "recent_90d_return_delta_pct": slice_delta(run, base_run, "3m", "return_pct"),
                "recent_90d_maxdd_delta_pct": slice_delta(run, base_run, "3m", "max_drawdown_pct"),
                "recent_30d_return_delta_pct": slice_delta(run, base_run, "1m", "return_pct"),
                "recent_30d_maxdd_delta_pct": slice_delta(run, base_run, "1m", "max_drawdown_pct"),
            }
        )
    return rows


def slice_by_window(run: base.RunResult, window: str) -> dict[str, Any] | None:
    for item in run.slices:
        if item["window"] == window:
            return item
    return None


def slice_delta(run: base.RunResult, base_run: base.RunResult, window: str, key: str) -> float | None:
    item = slice_by_window(run, window)
    base_item = slice_by_window(base_run, window)
    if item is None or base_item is None:
        return None
    return round(float(item[key]) - float(base_item[key]), 2)


def last_trades(trades: pd.DataFrame, count: int) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    cols = [col for col in ["entry_ts", "exit_ts", "direction", "exit_reason", "mfe_atr", "allocation", "trade_return", "hold_bars"] if col in trades.columns]
    out = trades.tail(count)[cols].copy()
    if "trade_return" in out.columns:
        out["trade_return_pct"] = out["trade_return"].map(base.pct)
        out = out.drop(columns=["trade_return"])
    return out.to_dict("records")


def write_artifacts(runs: list[base.RunResult]) -> None:
    pd.concat([run.equity_curve.rename(run.name) for run in runs], axis=1).to_csv(EQUITY_PATH, index_label="ts")
    frames = [run.trades.assign(variant=run.name) for run in runs if not run.trades.empty]
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(TRADES_PATH, index=False)


def print_summary(runs: list[base.RunResult]) -> None:
    print(f"summary -> {SUMMARY_PATH}")
    print(f"{'variant':>32} {'full':>10} {'dd':>8} {'sharpe':>7} {'3m':>10} {'3mdd':>8} {'1m':>10} {'trades':>7} exits")
    for run in runs:
        s3 = slice_by_window(run, "3m") or {}
        s1 = slice_by_window(run, "1m") or {}
        print(
            f"{run.name:>32} {run.metrics['return_pct']:>9.2f}% {run.metrics['max_drawdown_pct']:>7.2f}% "
            f"{run.metrics['sharpe']:>7.2f} {s3.get('return_pct', 0):>9.2f}% {s3.get('max_drawdown_pct', 0):>7.2f}% "
            f"{s1.get('return_pct', 0):>9.2f}% {run.metrics['trades']:>7} {run.metrics['exit_counts']}"
        )


if __name__ == "__main__":
    main()
