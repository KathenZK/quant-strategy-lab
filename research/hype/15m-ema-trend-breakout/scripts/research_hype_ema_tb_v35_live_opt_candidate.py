"""V35 实盘优化建议合成候选回测。

对照 AI 建议包：
1) 降低单笔风险（target / cap）
2) MFE>=4ATR 后固定锁 +2.5/~3.0ATR（profit floor，非 1-1.5 trailing）
3) 同方向信号重置后再入场（或 cooldown1 对照）
保留原始 5ATR TP。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39_ab


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_live_opt_candidate_2026-07-20"


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    name: str
    config: base.V35Config
    floor: base.ProfitFloorConfig
    cooldown_bars: int = 0
    require_signal_reset: bool = False
    note: str = ""


def candidates() -> list[CandidateSpec]:
    v35 = base.V35Config()
    no_floor = base.ProfitFloorConfig(enabled=False)
    floor25 = base.ProfitFloorConfig(enabled=True, tiers=((4.0, 2.5),))
    floor30 = base.ProfitFloorConfig(enabled=True, tiers=((4.0, 3.0),))
    return [
        CandidateSpec("v35_base", v35, no_floor, note="live baseline"),
        CandidateSpec(
            "risk_target012",
            replace(v35, long_target_atr_pct=0.012, short_target_atr_pct=0.012),
            no_floor,
            note="target 1.2% both sides; SL risk ≈ 8.4% when uncapped",
        ),
        CandidateSpec(
            "risk_target010",
            replace(v35, long_target_atr_pct=0.010, short_target_atr_pct=0.010),
            no_floor,
            note="target 1.0% both sides; SL risk ≈ 7.0% when uncapped",
        ),
        CandidateSpec(
            "risk_cap25",
            replace(v35, max_allocation=2.5),
            no_floor,
            note="cap 3.0 -> 2.5",
        ),
        CandidateSpec(
            "risk_cap20",
            replace(v35, max_allocation=2.0),
            no_floor,
            note="cap 3.0 -> 2.0",
        ),
        CandidateSpec(
            "floor_40_lock25",
            v35,
            floor25,
            note="MFE>=4 lock +2.5ATR; keep TP5",
        ),
        CandidateSpec(
            "floor_40_lock30",
            v35,
            floor30,
            note="MFE>=4 lock +3.0ATR; keep TP5",
        ),
        CandidateSpec(
            "reentry_cooldown1",
            v35,
            no_floor,
            cooldown_bars=1,
            note="flat cooldown 1 bar after any exit",
        ),
        CandidateSpec(
            "reentry_signal_reset",
            v35,
            no_floor,
            require_signal_reset=True,
            note="same-direction signal must go off then on before re-entry",
        ),
        CandidateSpec(
            "pkg_t012_f25_reset",
            replace(v35, long_target_atr_pct=0.012, short_target_atr_pct=0.012),
            floor25,
            require_signal_reset=True,
            note="AI-like package: risk~8% + floor4/2.5 + signal reset",
        ),
        CandidateSpec(
            "pkg_t012_f30_reset",
            replace(v35, long_target_atr_pct=0.012, short_target_atr_pct=0.012),
            floor30,
            require_signal_reset=True,
            note="AI-like package: risk~8% + floor4/3.0 + signal reset",
        ),
        CandidateSpec(
            "pkg_cap25_f25_cd1",
            replace(v35, max_allocation=2.5),
            floor25,
            cooldown_bars=1,
            note="cap2.5 + floor4/2.5 + cooldown1",
        ),
        CandidateSpec(
            "pkg_t012_f25_cd1",
            replace(v35, long_target_atr_pct=0.012, short_target_atr_pct=0.012),
            floor25,
            cooldown_bars=1,
            note="target1.2% + floor4/2.5 + cooldown1",
        ),
    ]


def run_candidate(
    spec: CandidateSpec,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
) -> base.RunResult:
    config = spec.config
    floor_cfg = spec.floor
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    # same-direction signal reset state
    waiting_reset = {1: False, -1: False}
    seen_off = {1: True, -1: True}

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            exit_dir = position.direction
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
            if spec.require_signal_reset:
                waiting_reset[exit_dir] = True
                seen_off[exit_dir] = False

        if position is not None:
            funding_pnl = -position.direction * position.allocation * float(funding.iloc[i])
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        signal_i = i - config.entry_delay_bars
        long_sig = bool(features["long_signal"].iloc[signal_i])
        short_sig = bool(features["short_signal"].iloc[signal_i])
        if spec.require_signal_reset and position is None:
            if waiting_reset[1] and not long_sig:
                seen_off[1] = True
            if waiting_reset[-1] and not short_sig:
                seen_off[-1] = True

        cooldown_ok = i > last_exit_bar + spec.cooldown_bars
        if position is None and not exited_this_bar and cooldown_ok:
            direction = 0
            if long_sig and not short_sig:
                direction = 1
            elif short_sig and not long_sig:
                direction = -1
            if (
                direction != 0
                and spec.require_signal_reset
                and waiting_reset[direction]
                and not seen_off[direction]
            ):
                direction = 0
            entry_atr = float(features["atr"].iloc[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                target = (
                    config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
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
                if spec.require_signal_reset:
                    waiting_reset[direction] = False
                    seen_off[direction] = True

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
                exit_dir = position.direction
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
                if spec.require_signal_reset:
                    waiting_reset[exit_dir] = True
                    seen_off[exit_dir] = False
            else:
                pnl = position.direction * position.allocation * (
                    close / position.previous_price - 1.0
                )
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
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
    returns = pd.Series(period_returns, index=index, name=f"{spec.name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{spec.name}_weight")
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
        open_position=base.open_position_summary(position, frame.index[-1])
        if position is not None
        else None,
    )


def risk_stats(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"n": 0}
    atr_pct = trades["entry_atr"] / trades["entry_price"]
    sl_risk = trades["allocation"] * 7.0 * atr_pct
    tp_gain = trades["allocation"] * 5.0 * atr_pct
    return {
        "n": int(len(trades)),
        "alloc_median": float(trades["allocation"].median()),
        "alloc_p90": float(trades["allocation"].quantile(0.9)),
        "alloc_max": float(trades["allocation"].max()),
        "alloc_ge_3_share": float((trades["allocation"] >= 2.999).mean()),
        "sl_risk_pct_median": float(sl_risk.median() * 100.0),
        "sl_risk_pct_p90": float(sl_risk.quantile(0.9) * 100.0),
        "sl_risk_pct_max": float(sl_risk.max() * 100.0),
        "tp_gain_pct_median": float(tp_gain.median() * 100.0),
        "sl_over_tp_median": float((sl_risk / tp_gain).median()),
    }


def summarize(spec: CandidateSpec, run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    base_final = 1.0 + float(baseline.metrics["return_pct"]) / 100.0
    final = 1.0 + float(run.metrics["return_pct"]) / 100.0
    return {
        "name": run.name,
        "note": spec.note,
        "config": asdict(spec.config),
        "floor": asdict(spec.floor),
        "cooldown_bars": spec.cooldown_bars,
        "require_signal_reset": spec.require_signal_reset,
        "metrics": run.metrics,
        "slices": run.slices,
        "d90": ab.window_stats(run, 90),
        "risk": risk_stats(run.trades),
        "vs_v35": {
            "return_delta_pp": round(
                float(run.metrics["return_pct"]) - float(baseline.metrics["return_pct"]), 2
            ),
            "maxdd_delta_pp": round(
                float(run.metrics["max_drawdown_pct"])
                - float(baseline.metrics["max_drawdown_pct"]),
                2,
            ),
            "sharpe_delta": round(
                float(run.metrics["sharpe"]) - float(baseline.metrics["sharpe"]), 4
            ),
            "final_equity_retained_pct": round(final / base_final * 100.0, 2),
            "trade_delta": int(run.metrics["trades"] - baseline.metrics["trades"]),
        },
        "open_position": run.open_position,
    }


def print_row(row: dict[str, Any]) -> None:
    m = row["metrics"]
    r = row["risk"]
    print(
        f"{row['name']:>22} | full {m['return_pct']:>9.2f}% dd {m['max_drawdown_pct']:>7.2f}% "
        f"sh {m['sharpe']:>5.2f} n {m['trades']:>3} win {m['win_rate_pct']:>6.2f}% "
        f"| SL risk med/p90 {r.get('sl_risk_pct_median', 0):>5.2f}/{r.get('sl_risk_pct_p90', 0):>5.2f}% "
        f"| exits {m['exit_counts']}"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)

    rows: list[dict[str, Any]] = []
    runs: list[base.RunResult] = []
    baseline: base.RunResult | None = None

    # V35-family candidates share V35 signal flags.
    for spec in candidates():
        features = ab.build_signals(
            base.build_features(frame, spec.config), spec.config, ab.SignalFlags()
        )
        run = run_candidate(spec, frame, funding, features)
        runs.append(run)
        if baseline is None:
            baseline = run
        row = summarize(spec, run, baseline)
        rows.append(row)
        print_row(row)

    # V39 reference on same window.
    v39_cfg = v39_ab.v39_config()
    v39_features = ab.build_signals(
        base.build_features(frame, v39_cfg), v39_cfg, v39_ab.v39_flags()
    )
    v39_spec = CandidateSpec(
        "v39_ref",
        v39_cfg,
        base.ProfitFloorConfig(enabled=False),
        note="V39 reference same window",
    )
    v39_run = run_candidate(v39_spec, frame, funding, v39_features)
    runs.append(v39_run)
    assert baseline is not None
    v39_row = summarize(v39_spec, v39_run, baseline)
    rows.append(v39_row)
    print_row(v39_row)

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V35 live-opt candidate package diagnostic",
        "baseline": "HYPE-EMA-TB-V35",
        "data_quality": quality,
        "cost_model": (
            "Binance USD-M perp, 0.00085 per fill (fee + 4bps slippage combined), funding included."
        ),
        "hypothesis": {
            "ai_package": (
                "V35 entry unchanged + single-trade risk ~8% + MFE>=4 lock 2.5-3ATR "
                "+ same-direction signal reset before re-entry; keep TP5."
            ),
            "already_rejected": [
                "trail pullback 1-1.5ATR from peak",
                "cooldown 2-4 bars as fixed rule",
                "wide staged profit floor",
            ],
        },
        "rows": rows,
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)
    print(f"\nsummary -> {summary_path}")


if __name__ == "__main__":
    main()
