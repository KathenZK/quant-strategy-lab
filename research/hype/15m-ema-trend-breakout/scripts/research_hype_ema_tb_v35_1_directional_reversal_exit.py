"""回测 V35.1 的方向性反转退出，不改变入场、仓位或硬止盈止损。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_1_directional_reversal_exit_2026-07-22"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"

LIVE_LOSS_ENTRY_TS = pd.Timestamp("2026-07-21T05:45:00Z")
Source = Literal["none", "di15", "di15_adx_rising", "di1h"]


@dataclass(frozen=True, slots=True)
class DirectionalExitSpec:
    name: str
    source: Source
    confirm_bars: int = 0
    min_adverse_atr: float = 0.0

    @property
    def enabled(self) -> bool:
        return self.source != "none"


def directional_condition(
    *,
    spec: DirectionalExitSpec,
    position: base.Position,
    features: pd.DataFrame,
    i: int,
    close: float,
) -> tuple[bool, float]:
    adverse_atr = (
        -position.direction * (close - position.entry_price) / position.entry_atr
    )
    if adverse_atr <= 0.0 or adverse_atr < spec.min_adverse_atr:
        return False, float(adverse_atr)

    if spec.source in {"di15", "di15_adx_rising"}:
        plus_di = float(features["plus_di"].iloc[i])
        minus_di = float(features["minus_di"].iloc[i])
    elif spec.source == "di1h":
        plus_di = float(features["h1_plus_di"].iloc[i])
        minus_di = float(features["h1_minus_di"].iloc[i])
    else:
        return False, float(adverse_atr)

    opposite_di = (
        minus_di > plus_di if position.direction > 0 else plus_di > minus_di
    )
    if spec.source == "di15_adx_rising":
        adx_rising = float(features["adx"].iloc[i]) > float(
            features["adx"].iloc[i - 1]
        )
        return bool(opposite_di and adx_rising), float(adverse_atr)
    return bool(opposite_di), float(adverse_atr)


def run_variant(
    *,
    spec: DirectionalExitSpec,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> base.RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    pending_meta: dict[str, Any] = {}
    directional_bars = 0
    last_exit_bar = -1
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    no_floor = base.ProfitFloorConfig(enabled=False)

    def record_close(
        *,
        exit_price: float,
        exit_ts: pd.Timestamp,
        exit_bar: int,
        reason: str,
    ) -> None:
        nonlocal equity, trading_costs
        if position is None:
            raise RuntimeError("record_close called without an open position")
        equity, cost = base.close_position(
            equity=equity,
            position=position,
            exit_price=exit_price,
            exit_ts=exit_ts,
            exit_bar=exit_bar,
            reason=reason,
            trades=trades,
            config=config,
        )
        trading_costs += cost
        trades[-1].update(pending_meta)

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            record_close(
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
            )
            position = None
            pending_exit = None
            pending_meta = {}
            directional_bars = 0
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_pnl = (
                -position.direction * position.allocation * float(funding.iloc[i])
            )
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
            if (
                direction != 0
                and np.isfinite(entry_atr)
                and entry_atr > 0.0
                and open_price > 0.0
            ):
                target = (
                    config.long_target_atr_pct
                    if direction > 0
                    else config.short_target_atr_pct
                )
                allocation = min(
                    config.max_allocation,
                    target / (entry_atr / open_price),
                )
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
                directional_bars = 0
                pending_meta = {}

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
                record_close(
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                )
                position = None
                pending_exit = None
                pending_meta = {}
                directional_bars = 0
                last_exit_bar = i
            else:
                pnl = position.direction * position.allocation * (
                    close / position.previous_price - 1.0
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(
                    position,
                    high,
                    low,
                    config,
                    no_floor,
                )

                can_soft_exit = (
                    position.mfe_atr < config.disable_after_mfe_atr
                )
                adx_is_weak = (
                    float(features["adx"].iloc[i]) < config.adx_exit
                )
                position.weak_bars = (
                    position.weak_bars + 1
                    if can_soft_exit and adx_is_weak
                    else 0
                )
                if (
                    can_soft_exit
                    and position.weak_bars >= config.delayed_bars
                ):
                    pending_exit = "indicator_exit"

                if (
                    pending_exit is None
                    and spec.enabled
                    and can_soft_exit
                ):
                    condition, adverse_atr = directional_condition(
                        spec=spec,
                        position=position,
                        features=features,
                        i=i,
                        close=close,
                    )
                    directional_bars = (
                        directional_bars + 1 if condition else 0
                    )
                    if directional_bars >= spec.confirm_bars:
                        pending_exit = f"directional_exit_{spec.source}"
                        pending_meta = {
                            "directional_trigger_ts": ts,
                            "directional_trigger_adverse_atr": adverse_atr,
                            "directional_trigger_confirm_bars": (
                                directional_bars
                            ),
                        }
                else:
                    directional_bars = 0

                if (
                    pending_exit is None
                    and i - position.entry_bar >= config.max_hold_bars
                ):
                    pending_exit = "timeout"

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)
        weight_values.append(
            0.0
            if position is None
            else position.direction * position.allocation
        )

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
    returns = pd.Series(
        period_returns,
        index=index,
        name=f"{spec.name}_return",
    )
    weights = pd.Series(
        weight_values,
        index=index,
        name=f"{spec.name}_weight",
    )
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
        name=spec.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=(
            base.open_position_summary(position, frame.index[-1])
            if position is not None
            else None
        ),
    )


def matched_entry_attribution(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    key_columns = ["entry_ts", "direction"]
    left = baseline.trades.rename(
        columns={
            "exit_reason": "baseline_exit_reason",
            "trade_return": "baseline_trade_return",
            "exit_ts": "baseline_exit_ts",
        }
    )
    right = run.trades.rename(
        columns={
            "exit_reason": "candidate_exit_reason",
            "trade_return": "candidate_trade_return",
            "exit_ts": "candidate_exit_ts",
        }
    )
    matched = left[
        key_columns
        + ["baseline_exit_reason", "baseline_trade_return", "baseline_exit_ts"]
    ].merge(
        right[
            key_columns
            + [
                "candidate_exit_reason",
                "candidate_trade_return",
                "candidate_exit_ts",
            ]
        ],
        on=key_columns,
        how="inner",
    )
    directional = matched[
        matched["candidate_exit_reason"].str.startswith(
            "directional_exit",
            na=False,
        )
    ].copy()
    if directional.empty:
        baseline_reason_counts: dict[str, int] = {}
        delta_sum = 0.0
        improved = 0
        worsened = 0
    else:
        baseline_reason_counts = {
            str(key): int(value)
            for key, value in directional[
                "baseline_exit_reason"
            ].value_counts().items()
        }
        deltas = (
            directional["candidate_trade_return"]
            - directional["baseline_trade_return"]
        )
        delta_sum = float(deltas.sum())
        improved = int(deltas.gt(0.0).sum())
        worsened = int(deltas.lt(0.0).sum())
    return {
        "exact_entry_matches": int(len(matched)),
        "baseline_only_entries": int(len(baseline.trades) - len(matched)),
        "candidate_only_entries": int(len(run.trades) - len(matched)),
        "directional_exit_matches": int(len(directional)),
        "directional_exits_by_baseline_outcome": baseline_reason_counts,
        "improved_matched_trades": improved,
        "worsened_matched_trades": worsened,
        "sum_matched_trade_return_delta_pp": round(delta_sum * 100.0, 4),
    }


def live_loss_counterfactual(run: base.RunResult) -> dict[str, Any] | None:
    if run.trades.empty:
        return None
    entries = pd.to_datetime(run.trades["entry_ts"], utc=True)
    row = run.trades.loc[
        entries.eq(LIVE_LOSS_ENTRY_TS)
        & run.trades["direction"].eq(1)
    ]
    if row.empty:
        return None
    trade = row.iloc[0]
    fields = [
        "entry_ts",
        "exit_ts",
        "entry_price",
        "exit_price",
        "entry_atr",
        "mfe_atr",
        "exit_reason",
        "hold_bars",
        "trade_return",
        "directional_trigger_ts",
        "directional_trigger_adverse_atr",
    ]
    return {
        field: trade[field]
        for field in fields
        if field in trade.index and pd.notna(trade[field])
    }


def comparison(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    baseline_equity = 1.0 + baseline.metrics["return_pct"] / 100.0
    candidate_equity = 1.0 + run.metrics["return_pct"] / 100.0
    return {
        "final_equity_retained_pct": round(
            candidate_equity / baseline_equity * 100.0,
            2,
        ),
        "return_delta_pp": round(
            run.metrics["return_pct"] - baseline.metrics["return_pct"],
            2,
        ),
        "max_drawdown_delta_pp": round(
            run.metrics["max_drawdown_pct"]
            - baseline.metrics["max_drawdown_pct"],
            2,
        ),
        "sharpe_delta": round(
            run.metrics["sharpe"] - baseline.metrics["sharpe"],
            2,
        ),
    }


def pre_live_loss_audit(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    candidate = run.equity_curve.loc[
        run.equity_curve.index < LIVE_LOSS_ENTRY_TS
    ]
    reference = baseline.equity_curve.loc[
        baseline.equity_curve.index < LIVE_LOSS_ENTRY_TS
    ]
    if candidate.empty or reference.empty:
        raise RuntimeError("Pre-live-loss equity window is empty")
    drawdown = candidate / candidate.cummax() - 1.0
    directional_exits = run.trades.loc[
        pd.to_datetime(run.trades["exit_ts"], utc=True).lt(
            LIVE_LOSS_ENTRY_TS
        )
        & run.trades["exit_reason"].str.startswith(
            "directional_exit",
            na=False,
        )
    ]
    return {
        "cutoff_exclusive": LIVE_LOSS_ENTRY_TS.isoformat(),
        "return_pct": round(float(candidate.iloc[-1] - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(float(drawdown.min()) * 100.0, 2),
        "final_equity_retained_vs_v35_1_pct": round(
            float(candidate.iloc[-1] / reference.iloc[-1]) * 100.0,
            2,
        ),
        "directional_exits_before_live_loss": int(
            len(directional_exits)
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    if not quality_gate["passed"]:
        raise RuntimeError(f"Data-quality gate failed: {quality_gate}")

    config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
    specs = [
        DirectionalExitSpec("v35_1_base", "none"),
        DirectionalExitSpec("di15_c1", "di15", confirm_bars=1),
        DirectionalExitSpec("di15_c2", "di15", confirm_bars=2),
        DirectionalExitSpec("di15_c3", "di15", confirm_bars=3),
        DirectionalExitSpec(
            "di15_adxrise_c1",
            "di15_adx_rising",
            confirm_bars=1,
        ),
        DirectionalExitSpec(
            "di15_adxrise_c2",
            "di15_adx_rising",
            confirm_bars=2,
        ),
        DirectionalExitSpec(
            "di15_adxrise_c3",
            "di15_adx_rising",
            confirm_bars=3,
        ),
        DirectionalExitSpec(
            "di15_adxrise_c2_a1",
            "di15_adx_rising",
            confirm_bars=2,
            min_adverse_atr=1.0,
        ),
        DirectionalExitSpec(
            "di15_adxrise_c2_a2",
            "di15_adx_rising",
            confirm_bars=2,
            min_adverse_atr=2.0,
        ),
        DirectionalExitSpec("di1h_c1", "di1h", confirm_bars=1),
        DirectionalExitSpec("di1h_c2", "di1h", confirm_bars=2),
        DirectionalExitSpec(
            "di1h_c1_a1",
            "di1h",
            confirm_bars=1,
            min_adverse_atr=1.0,
        ),
    ]
    runs = [
        run_variant(
            spec=spec,
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        for spec in specs
    ]
    baseline = runs[0]
    canonical = base.run_backtest(
        "canonical_v35_1",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_diff = float(
        (baseline.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35.1 baseline parity failed: {parity_diff}")

    payload_runs: list[dict[str, Any]] = []
    for spec, run in zip(specs, runs, strict=True):
        payload_runs.append(
            {
                "spec": asdict(spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "comparison_to_v35_1": (
                    None if run is baseline else comparison(run, baseline)
                ),
                "matched_entry_attribution": (
                    None
                    if run is baseline
                    else matched_entry_attribution(run, baseline)
                ),
                "pre_live_loss_audit": pre_live_loss_audit(
                    run,
                    baseline,
                ),
                "live_loss_counterfactual": live_loss_counterfactual(run),
            }
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.1",
        "audit_id": "directional reversal exit small grid",
        "run_date": "2026-07-22",
        "status": "diagnostic_only_not_registered_not_promoted",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_v35_1_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "market": "Binance USD-M Futures HYPEUSDT perpetual 15m",
            "execution": (
                "只用最终闭合 K；方向退出在 15m 收盘确认，下一根开盘成交；"
                "同根先执行静态 SL/TP。"
            ),
            "scope": (
                "仅增加 MFE<1.5ATR 且持仓已亏损时的方向反转退出；"
                "入场、仓位、TP5、SL7、原 ADX22 delayed3 和 timeout384 不变。"
            ),
            "costs": (
                "每次成交按 allocation 收取 0.00085，已包含 0.00045 fee "
                "+ 4bps adverse slippage；另计 Binance funding。"
            ),
            "selection": (
                "全样本小网格用于诊断和候选生成；1d/7d/1m/3m/6m/1y "
                "分片仅审计，不是独立 OOS。"
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": payload_runs,
    }
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    pd.concat(
        [
            run.trades.assign(variant=run.name)
            for run in runs
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for run in runs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']} "
        f"parity={parity_diff:.2e}"
    )
    for run in runs:
        metrics = run.metrics
        counterfactual = live_loss_counterfactual(run)
        counterfactual_text = (
            "missing"
            if counterfactual is None
            else (
                f"{counterfactual['exit_reason']} "
                f"{float(counterfactual['trade_return']) * 100:.2f}%"
            )
        )
        print(
            f"{run.name:>22} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"live_loss={counterfactual_text}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
