"""HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble 组合回测。

把 `HYPE-EMA-Trend-Breakout` 趋势腿（`--trend v35` 或 `--trend v39`）与
`HYPE-15M-Multi-Indicator-Intraday-V1.3`（RSI 短促反转 + ATR bracket）组合成一个新策略，比较：

1. 独立双子账户组合（50/50、70/30、30/70，逐 K 再平衡；以及 50/50 固定拆分不再平衡）。
2. 单账户冲突仲裁：趋势腿优先。V1.3 只在趋势腿空仓时开单；趋势信号到来时
   要么强制平掉 V1.3（preempt 变体），要么放弃该笔趋势单（no-preempt 变体）。

两条腿各自保持家族 canonical 成本口径：
- 趋势腿：`0.00085`/fill（taker fee + 4 bps 解释），计入 Binance funding；K+2 open 入场。
- V1.3 腿：fee `0.001`/fill + slippage `4 bps`/fill（round-trip `0.28%`），funding 未计；
  K+1 open 入场为主口径，K+2 为延迟压力。

门禁校验：数据质量 gate、趋势腿与 canonical 引擎逐 K 权益零差、
V1.3 腿与 MII 引擎单仓选择链及终值精确对照。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "research/hype/15m-ema-trend-breakout/scripts"))
sys.path.insert(0, str(REPO_ROOT / "research/hype/15m-multi-indicator-intraday/scripts"))

import research_hype_ema_tb_v35_profit_floor as tb  # noqa: E402  V35/V39 canonical engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as tbab  # noqa: E402  SignalFlags/build_signals
import research_hype_15m_mii_v1_2_atr_bracket_exit as mii12  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as mii1  # noqa: E402

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse  # noqa: E402
from strategy_lab.data.settings import load_settings  # noqa: E402


FAMILY = "HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble"
ALIAS = "HYPE-15M-TB-MII-ENS"
FAMILY_DIR = REPO_ROOT / "research/hype/15m-trend-breakout-multi-indicator-ensemble"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"


def trend_setup(trend: str) -> tuple[tb.V35Config, tbab.SignalFlags]:
    """按主账定义构造趋势腿配置。V39 = V35 + long_vol_min 0.35 + short_target 0.022 - 空头 1h EMA 确认。"""
    if trend == "v35":
        return tb.V35Config(), tbab.SignalFlags()
    if trend == "v39":
        return (
            replace(tb.V35Config(), long_vol_min=0.35, short_target_atr_pct=0.022),
            tbab.SignalFlags(short_use_h1_ema=False),
        )
    raise ValueError(f"unsupported trend leg: {trend}")

MII_EXPOSURE = 2.5
MII_ROUND_TRIP = mii12.ROUND_TRIP_COST  # 0.0028
MII_OPEN_EXIT_REASONS = {"max_hold", "stop_gap", "take_profit_gap"}
M15_PER_YEAR = tb.M15_PER_YEAR

V13_CANDIDATE = mii12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)


def mii_setup(mii: str) -> Any:
    """按 MII 主账定义构造反转腿过滤器。V1.4 = V1.3 + min_rvol96 1.0 -> 0.85。"""
    if mii == "v13":
        return mii12.BASE_CONFIG.filter
    if mii == "v14":
        return replace(mii12.BASE_CONFIG.filter, min_rvol96=0.85)
    raise ValueError(f"unsupported mii leg: {mii}")


def mii_candidates_by_entry(
    context: Any, entry_delay_bars: int, filter_spec: Any
) -> dict[int, Any]:
    """通过入场过滤后的 MII 候选交易，按 entry_i 索引（单仓选择在组合循环里完成）。"""
    raw = mii12.simulate_atr_bracket_trades(context, V13_CANDIDATE, entry_delay_bars=entry_delay_bars)
    by_entry: dict[int, Any] = {}
    for trade in raw:
        if mii1.passes_filter(trade, filter_spec):
            by_entry.setdefault(int(trade.entry_i), trade)
    return by_entry


def close_mii_record(
    trade: Any,
    entry_equity: float,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    leg_label: str = "mii_v13",
) -> tuple[float, dict[str, Any]]:
    raw_return = trade.direction * (exit_price / trade.entry_price - 1.0)
    exit_equity = entry_equity * max(0.0, 1.0 + MII_EXPOSURE * (raw_return - MII_ROUND_TRIP))
    record = {
        "leg": leg_label,
        "entry_ts": pd.Timestamp(trade.entry_ts),
        "exit_ts": exit_ts,
        "direction": int(trade.direction),
        "entry_price": float(trade.entry_price),
        "exit_price": float(exit_price),
        "exit_reason": reason,
        "entry_bar": int(trade.entry_i),
        "exit_bar": exit_bar,
        "hold_bars": exit_bar - int(trade.entry_i),
        "trade_return": exit_equity / entry_equity - 1.0,
    }
    return exit_equity, record


def run_account(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: tb.V35Config,
    mii_by_entry: dict[int, Any] | None,
    *,
    enable_v35: bool,
    enable_mii: bool,
    preempt: bool = True,
    trend_label: str = "v35",
    mii_label: str = "mii_v13",
) -> dict[str, Any]:
    """单账户逐 K 状态机。任一时刻最多持有一条腿的仓位。

    V35 腿完全复刻 canonical 引擎（含 funding、intrabar TP/SL、ADX delayed3、timeout）。
    V1.3 腿使用预生成的独立交易路径：持仓期间按 close 逐 K mark（扣除全额 round-trip
    成本，收敛到出场时刻的 engine-exact 值），availability 链沿用上游单仓规则。
    """
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    opens = frame["open"].to_numpy("float64")
    highs = frame["high"].to_numpy("float64")
    lows = frame["low"].to_numpy("float64")
    closes = frame["close"].to_numpy("float64")
    fund = funding.to_numpy("float64")
    adx = features["adx"].to_numpy("float64")
    atr = features["atr"].to_numpy("float64")
    long_sig = features["long_signal"].to_numpy(bool)
    short_sig = features["short_signal"].to_numpy(bool)
    no_floor = tb.ProfitFloorConfig(enabled=False)

    equity = 1.0
    v35_pos: tb.Position | None = None
    v35_pending: str | None = None
    v35_last_exit = -1
    mii_trade: Any | None = None
    mii_entry_equity = 0.0
    mii_available_i = -1
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    period_returns: list[float] = []

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price, high, low, close = opens[i], highs[i], lows[i], closes[i]
        v35_exited_this_bar = False

        # 1. V35 pending exit（indicator/timeout）按本根 open 成交
        if v35_pos is not None and v35_pending is not None:
            equity, _cost = tb.close_position(
                equity=equity,
                position=v35_pos,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=v35_pending,
                trades=trades,
                config=config,
            )
            trades[-1]["leg"] = trend_label
            v35_pos = None
            v35_pending = None
            v35_last_exit = i
            v35_exited_this_bar = True

        # 2. V1.3 open 型出场（max_hold / gap）按本根 open 成交
        if (
            mii_trade is not None
            and int(mii_trade.exit_i) == i
            and mii_trade.exit_reason in MII_OPEN_EXIT_REASONS
        ):
            equity, record = close_mii_record(
                mii_trade, mii_entry_equity, float(mii_trade.exit_price), ts, i, mii_trade.exit_reason,
                leg_label=mii_label,
            )
            trades.append(record)
            mii_available_i = i  # open 型出场允许同根 open 再入（沿用上游口径）
            mii_trade = None

        # 3. V35 持仓 funding
        if v35_pos is not None:
            funding_pnl = -v35_pos.direction * v35_pos.allocation * fund[i]
            equity *= 1.0 + funding_pnl

        # 4. V35 入场（信号 K-2 收盘，K open 成交）
        v35_entered_this_bar = False
        if enable_v35 and v35_pos is None and not v35_exited_this_bar and i > v35_last_exit:
            signal_i = i - config.entry_delay_bars
            direction = 0
            if long_sig[signal_i] and not short_sig[signal_i]:
                direction = 1
            elif short_sig[signal_i] and not long_sig[signal_i]:
                direction = -1
            entry_atr = float(atr[i - 1])
            if direction != 0 and np.isfinite(entry_atr) and entry_atr > 0.0 and open_price > 0.0:
                if mii_trade is not None:
                    if preempt:
                        equity, record = close_mii_record(
                            mii_trade, mii_entry_equity, open_price, ts, i, f"preempted_by_{trend_label}",
                            leg_label=mii_label,
                        )
                        trades.append(record)
                        mii_available_i = i
                        mii_trade = None
                    else:
                        direction = 0
                if direction != 0:
                    target = (
                        config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
                    )
                    allocation = min(config.max_allocation, target / (entry_atr / open_price))
                    equity *= 1.0 - config.trade_cost_rate * allocation
                    v35_pos = tb.Position(
                        direction=direction,
                        entry_bar=i,
                        entry_ts=ts,
                        entry_price=open_price,
                        entry_atr=entry_atr,
                        allocation=allocation,
                        entry_equity=equity,
                        previous_price=open_price,
                    )
                    v35_entered_this_bar = True

        # 5. V35 持仓处理：intrabar TP/SL、mark、指标退出与 timeout
        if v35_pos is not None:
            intrabar = tb.check_intrabar_exit(
                position=v35_pos, open_price=open_price, high=high, low=low, config=config
            )
            if intrabar is not None:
                reason, exit_price = intrabar
                equity, _cost = tb.close_position(
                    equity=equity,
                    position=v35_pos,
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                )
                trades[-1]["leg"] = trend_label
                v35_pos = None
                v35_pending = None
                v35_last_exit = i
            else:
                pnl = v35_pos.direction * v35_pos.allocation * (close / v35_pos.previous_price - 1.0)
                equity *= 1.0 + pnl
                v35_pos.previous_price = close
                tb.update_position_on_close(v35_pos, high, low, config, no_floor)
                can_indicator_exit = v35_pos.mfe_atr < config.disable_after_mfe_atr
                if can_indicator_exit and adx[i] < config.adx_exit:
                    v35_pos.weak_bars += 1
                else:
                    v35_pos.weak_bars = 0
                if can_indicator_exit and v35_pos.weak_bars >= config.delayed_bars:
                    v35_pending = "indicator_exit"
                if v35_pending is None and i - v35_pos.entry_bar >= config.max_hold_bars:
                    v35_pending = "timeout"

        # 6. V1.3 入场：仅在账户空仓、当根无 V35 成交、且通过 availability 链
        if (
            enable_mii
            and mii_by_entry is not None
            and mii_trade is None
            and v35_pos is None
            and not v35_entered_this_bar
            and i > v35_last_exit
            and i >= mii_available_i
        ):
            candidate = mii_by_entry.get(i)
            if candidate is not None:
                mii_trade = candidate
                mii_entry_equity = equity

        # 7. V1.3 出场（含入场同根触发）或逐 K mark
        if mii_trade is not None:
            if int(mii_trade.exit_i) == i:
                is_open_exit = mii_trade.exit_reason in MII_OPEN_EXIT_REASONS
                equity, record = close_mii_record(
                    mii_trade, mii_entry_equity, float(mii_trade.exit_price), ts, i, mii_trade.exit_reason,
                    leg_label=mii_label,
                )
                trades.append(record)
                mii_available_i = i if is_open_exit else i + 1  # intrabar 出场：下一根才可再入
                mii_trade = None
            else:
                mark_return = MII_EXPOSURE * (
                    mii_trade.direction * (close / mii_trade.entry_price - 1.0) - MII_ROUND_TRIP
                )
                equity = mii_entry_equity * max(0.0, 1.0 + mark_return)

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=name)
    returns = pd.Series(period_returns, index=index, name=f"{name}_return")
    trades_frame = pd.DataFrame(trades)
    if not trades_frame.empty and "leg" not in trades_frame.columns:
        trades_frame["leg"] = trend_label
    return {
        "name": name,
        "equity_curve": equity_curve,
        "returns": returns,
        "trades": trades_frame,
        "open_position": {
            "trend": tb.open_position_summary(v35_pos, frame.index[-1]) if v35_pos is not None else None,
            "mii": {
                "entry_ts": pd.Timestamp(mii_trade.entry_ts).isoformat(),
                "direction": int(mii_trade.direction),
                "scheduled_exit_reason": mii_trade.exit_reason,
            }
            if mii_trade is not None
            else None,
        },
    }


def portfolio_from_returns(
    name: str,
    weight_v35: float,
    v35_run: dict[str, Any],
    mii_run: dict[str, Any],
    *,
    rebalanced: bool,
) -> dict[str, Any]:
    if rebalanced:
        combined_returns = weight_v35 * v35_run["returns"] + (1.0 - weight_v35) * mii_run["returns"]
        equity_curve = (1.0 + combined_returns).cumprod().rename(name)
    else:
        equity_curve = (
            weight_v35 * v35_run["equity_curve"] + (1.0 - weight_v35) * mii_run["equity_curve"]
        ).rename(name)
        combined_returns = equity_curve.pct_change().fillna(equity_curve.iloc[0] - 1.0)
    trades = pd.concat([v35_run["trades"], mii_run["trades"]], ignore_index=True)
    trades = trades.sort_values("exit_ts").reset_index(drop=True)
    return {
        "name": name,
        "equity_curve": equity_curve,
        "returns": combined_returns.rename(f"{name}_return"),
        "trades": trades,
        "open_position": None,
    }


def run_metrics(run: dict[str, Any]) -> dict[str, Any]:
    equity_curve = run["equity_curve"]
    returns = run["returns"]
    trades = run["trades"]
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    volatility = float(returns.std(ddof=0))
    period_days = (equity_curve.index.max() - equity_curve.index.min()).total_seconds() / 86_400.0
    final = float(equity_curve.iloc[-1])
    annual = (final ** (365.0 / period_days) - 1.0) if (period_days > 0 and final > 0) else -1.0
    wins = int(trades["trade_return"].gt(0.0).sum()) if not trades.empty else 0
    exit_counts = trades["exit_reason"].value_counts().to_dict() if not trades.empty else {}
    leg_counts = trades["leg"].value_counts().to_dict() if not trades.empty else {}
    return {
        "start": equity_curve.index.min().isoformat(),
        "end": equity_curve.index.max().isoformat(),
        "total_return_pct": tb.pct(final - 1.0),
        "annual_return_pct": tb.pct(annual),
        "max_drawdown_pct": tb.pct(float(drawdown.min())),
        "sharpe": round(
            float(0.0 if volatility == 0.0 else returns.mean() / volatility * np.sqrt(M15_PER_YEAR)), 2
        ),
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": tb.pct(wins / len(trades)) if len(trades) else 0.0,
        "leg_trades": {str(k): int(v) for k, v in leg_counts.items()},
        "exit_counts": {str(k): int(v) for k, v in exit_counts.items()},
    }


LEDGER_EXPECTATIONS: dict[tuple[str, str], dict[str, float]] = {
    # 主账登记值，用于门禁校验（窗口必须一致才启用）
    ("v39", "2026-07-08T05:30:00+00:00"): {
        "total_return_pct": 9969.45,
        "max_drawdown_pct": -23.46,
        "trades": 107,
        "win_rate_pct": 79.44,
    },
}

MII_LEDGER_EXPECTATIONS: dict[tuple[str, str], dict[str, dict[str, float]]] = {
    # MII 主账登记值（engine 全样本口径），窗口一致时启用门禁
    ("v13", "2026-07-08T05:30:00+00:00"): {
        "K+1": {"total_return_pct": 483.23, "max_drawdown_pct": -22.01, "trades": 185, "win_rate_pct": 84.32},
        "K+2": {"total_return_pct": 204.85, "max_drawdown_pct": -41.89},
    },
    ("v14", "2026-07-08T05:30:00+00:00"): {
        "K+1": {"total_return_pct": 978.36, "max_drawdown_pct": -24.70, "trades": 232, "win_rate_pct": 84.91},
        "K+2": {"total_return_pct": 535.54, "max_drawdown_pct": -38.30},
    },
}


def data_quality_gate(tb_quality: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "missing_15m_bars": int(tb_quality["missing_15m_bars"]),
        "duplicate_ts_before_dedup": int(tb_quality["duplicate_ts_before_dedup"]),
        "invalid_ohlc_rows": int(tb_quality["invalid_ohlc_rows"]),
        "critical_nulls_total": int(sum(tb_quality["critical_nulls"].values())),
        "is_utc_index": bool(tb_quality["is_utc_index"]),
        "raw_vs_normalized_mismatch_rows": int(
            sum(tb_quality["raw_vs_normalized"].get("mismatch_rows", {}).values())
        )
        if tb_quality["raw_vs_normalized"].get("available")
        else -1,
    }
    passed = (
        checks["missing_15m_bars"] == 0
        and checks["duplicate_ts_before_dedup"] == 0
        and checks["invalid_ohlc_rows"] == 0
        and checks["critical_nulls_total"] == 0
        and checks["is_utc_index"]
        and checks["raw_vs_normalized_mismatch_rows"] == 0
    )
    if not passed:
        raise ValueError(f"data-quality gate failed: {json.dumps(checks)}")
    return {"passed": True, **checks}


def mii_chain_gate(
    mii_run: dict[str, Any],
    raw_trades: list[Any],
    start_bar: int,
    filter_spec: Any,
) -> dict[str, Any]:
    """MII 腿门禁：组合循环里的单仓选择链与 MII canonical 引擎逐笔一致，且终值 engine-exact。"""
    eligible = [t for t in raw_trades if int(t.entry_i) >= start_bar]
    chain = mii1.selected_trades_live(eligible, filter_spec)
    expected = [(int(t.entry_i), int(t.exit_i), str(t.exit_reason)) for t in chain]
    got = [
        (int(row["entry_bar"]), int(row["exit_bar"]), str(row["exit_reason"]))
        for row in mii_run["trades"].to_dict("records")
    ]
    if expected != got:
        raise ValueError(
            f"MII chain gate failed: engine chain {len(expected)} trades vs loop {len(got)} trades; "
            f"first diff at index {next((k for k in range(min(len(expected), len(got))) if expected[k] != got[k]), None)}"
        )
    engine_equity = 1.0
    for trade in chain:
        engine_equity *= max(0.0, 1.0 + MII_EXPOSURE * (float(trade.raw_return) - MII_ROUND_TRIP))
    loop_equity = float(mii_run["equity_curve"].iloc[-1])
    diff = abs(engine_equity - loop_equity)
    if diff > 1e-9:
        raise ValueError(f"MII equity gate failed: engine {engine_equity} vs loop {loop_equity}")
    return {"passed": True, "chain_trades": len(expected), "final_equity_abs_diff": diff}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trend", choices=["v35", "v39"], default="v39")
    parser.add_argument("--mii", choices=["v13", "v14"], default="v14")
    parser.add_argument("--run-date", default="2026-07-09")
    args = parser.parse_args()
    trend = args.trend
    mii = args.mii
    mii_label = f"mii_{mii}"
    run_date = args.run_date
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, funding, tb_quality = tb.load_data(warehouse)
    quality_gate = data_quality_gate(tb_quality)
    config, flags = trend_setup(trend)
    features = tbab.build_signals(tb.build_features(frame, config), config, flags)
    mii_filter = mii_setup(mii)

    mii_context, mii_metadata, mii_quality = mii12.build_context()  # 内部含 MII 数据质量 gate
    if len(mii_context.features) != len(frame):
        raise ValueError("趋势腿与 MII 数据湖行数不一致，先排查数据口径")
    mii_ts = pd.to_datetime(mii_context.features["ts"], utc=True).to_numpy()
    if not (mii_ts == frame.index.to_numpy()).all():
        raise ValueError("趋势腿与 MII 时间索引不一致，先排查数据口径")

    mii_k1 = mii_candidates_by_entry(mii_context, 1, mii_filter)
    mii_k2 = mii_candidates_by_entry(mii_context, 2, mii_filter)
    mii_raw_k1 = mii12.simulate_atr_bracket_trades(mii_context, V13_CANDIDATE, entry_delay_bars=1)
    mii_raw_k2 = mii12.simulate_atr_bracket_trades(mii_context, V13_CANDIDATE, entry_delay_bars=2)

    # MII 腿 engine-exact 全样本复核（与家族主账对照；窗口为当前数据湖全量）
    period_days = (mii_context.end_ts - mii_context.start_ts).total_seconds() / 86_400.0
    mii_ledger_check = {}
    for raw, label in ((mii_raw_k1, "K+1"), (mii_raw_k2, "K+2")):
        result = mii1.engine.evaluate_trades(
            trades=raw,
            filter_spec=mii_filter,
            exposure=MII_EXPOSURE,
            period_days=period_days,
            exit_spec=mii12.candidate_exit_spec(V13_CANDIDATE),
            start_ts=mii_context.start_ts,
            end_ts=mii_context.end_ts,
        )
        mii_ledger_check[label] = {
            "total_return_pct": round(float(result.total_return_pct), 2),
            "annual_return_pct": round(float(result.annual_return_pct), 2),
            "max_drawdown_pct": round(float(result.max_drawdown_pct), 2),
            "win_rate_pct": round(float(result.win_rate_pct), 2),
            "trades": int(result.trades),
        }

    # 门禁：MII 腿 engine 全样本结果与 MII 主账登记值对照（窗口一致时启用）
    data_end_iso = frame.index.max().isoformat()
    mii_ledger_key = (mii, data_end_iso)
    mii_ledger_gate: dict[str, Any]
    if mii_ledger_key in MII_LEDGER_EXPECTATIONS:
        mismatches: dict[str, Any] = {}
        for label, expected in MII_LEDGER_EXPECTATIONS[mii_ledger_key].items():
            for key, value in expected.items():
                got_value = mii_ledger_check[label][key]
                if abs(float(got_value) - float(value)) > 0.01:
                    mismatches[f"{label}.{key}"] = {"expected": value, "got": got_value}
        if mismatches:
            raise ValueError(f"MII 腿主账对照失败: {json.dumps(mismatches)}")
        mii_ledger_gate = {"passed": True, "checked_against": MII_LEDGER_EXPECTATIONS[mii_ledger_key]}
    else:
        mii_ledger_gate = {"passed": None, "reason": f"no ledger expectation for {mii_ledger_key}"}

    def account(name: str, mii_by_entry: dict[int, Any] | None, **kwargs: Any) -> dict[str, Any]:
        return run_account(
            name, frame, funding, features, config, mii_by_entry,
            trend_label=trend, mii_label=mii_label, **kwargs
        )

    leg_trend = account(f"leg_{trend}_only", None, enable_v35=True, enable_mii=False)
    leg_mii_k1 = account(f"leg_{mii_label}_k1", mii_k1, enable_v35=False, enable_mii=True)
    leg_mii_k2 = account(f"leg_{mii_label}_k2", mii_k2, enable_v35=False, enable_mii=True)

    # 门禁：组合循环的趋势腿与 canonical 引擎逐 K 对照，防止实现漂移
    canonical_trend = tb.run_backtest(
        f"{trend}_canonical", frame, funding, features, config, tb.ProfitFloorConfig(enabled=False)
    )
    trend_max_diff = float(
        (leg_trend["equity_curve"] - canonical_trend.equity_curve).abs().max()
    )
    if trend_max_diff > 1e-9:
        raise ValueError(f"组合循环的趋势腿与 canonical 引擎不一致，max diff={trend_max_diff}")

    # 门禁：趋势腿 canonical 结果与主账登记值对照（窗口一致时启用）
    ledger_key = (trend, data_end_iso)
    trend_ledger_gate: dict[str, Any]
    if ledger_key in LEDGER_EXPECTATIONS:
        expected = LEDGER_EXPECTATIONS[ledger_key]
        got = canonical_trend.metrics
        metric_map = {
            "total_return_pct": got["return_pct"],
            "max_drawdown_pct": got["max_drawdown_pct"],
            "trades": got["trades"],
            "win_rate_pct": got["win_rate_pct"],
        }
        mismatches = {
            key: {"expected": value, "got": metric_map[key]}
            for key, value in expected.items()
            if abs(float(metric_map[key]) - float(value)) > 0.01
        }
        if mismatches:
            raise ValueError(f"趋势腿主账对照失败: {json.dumps(mismatches)}")
        trend_ledger_gate = {"passed": True, "checked_against": expected}
    else:
        trend_ledger_gate = {"passed": None, "reason": f"no ledger expectation for {ledger_key}"}

    # 门禁：MII 腿单仓选择链 + 终值 engine-exact 对照
    start_bar = max(config.warmup_bars, config.entry_delay_bars + 1)
    mii_gate_k1 = mii_chain_gate(leg_mii_k1, mii_raw_k1, start_bar, mii_filter)
    mii_gate_k2 = mii_chain_gate(leg_mii_k2, mii_raw_k2, start_bar, mii_filter)

    runs = [
        leg_trend,
        leg_mii_k1,
        leg_mii_k2,
        portfolio_from_returns("portfolio_5050_rebal_k1", 0.5, leg_trend, leg_mii_k1, rebalanced=True),
        portfolio_from_returns("portfolio_5050_rebal_k2", 0.5, leg_trend, leg_mii_k2, rebalanced=True),
        portfolio_from_returns("portfolio_7030_rebal_k1", 0.7, leg_trend, leg_mii_k1, rebalanced=True),
        portfolio_from_returns("portfolio_3070_rebal_k1", 0.3, leg_trend, leg_mii_k1, rebalanced=True),
        portfolio_from_returns("portfolio_5050_fixed_k1", 0.5, leg_trend, leg_mii_k1, rebalanced=False),
        account(f"single_{trend}_priority_k1", mii_k1, enable_v35=True, enable_mii=True, preempt=True),
        account(f"single_{trend}_priority_k2", mii_k2, enable_v35=True, enable_mii=True, preempt=True),
        account("single_no_preempt_k1", mii_k1, enable_v35=True, enable_mii=True, preempt=False),
        account("single_no_preempt_k2", mii_k2, enable_v35=True, enable_mii=True, preempt=False),
    ]

    daily_trend = leg_trend["returns"].resample("1D").sum()
    daily_mii = leg_mii_k1["returns"].resample("1D").sum()
    leg_daily_corr = round(float(daily_trend.corr(daily_mii)), 4)

    results = []
    for run in runs:
        metrics = run_metrics(run)
        slices = tb.slice_metrics(run["equity_curve"], run["trades"])
        results.append(
            {
                "name": run["name"],
                "metrics": metrics,
                "slices": slices,
                "open_position": run["open_position"],
            }
        )

    summary = {
        "strategy_family": FAMILY,
        "alias": ALIAS,
        "run_date": run_date,
        "trend_leg": trend,
        "mii_leg": mii,
        "status": "combination_diagnostic_not_promoted",
        "components": {
            "trend_leg": f"HYPE-EMA-Trend-Breakout-{trend.upper()} (canonical engine, funding included, cost 0.00085/fill, K+2 open entry)",
            "reversal_leg": (
                f"HYPE-15M-Multi-Indicator-Intraday-{'V1.4' if mii == 'v14' else 'V1.3'} "
                "(fee 0.001/fill + slippage 4bps/fill, funding excluded, 2.5x, K+1 open entry; K+2 stress)"
            ),
        },
        "data": {
            "exchange": "binance",
            "market_type": "perp",
            "symbol": "HYPE/USDT:USDT",
            "timeframe": "15m",
            "tb_quality": tb_quality,
            "mii_quality": mii_quality,
            "mii_metadata": mii_metadata,
            "evaluation_window_note": "组合曲线从趋势腿 warmup(1600 根 15m) 结束后开始；V1.3 单腿在该窗口内重新锚定单仓 availability 链。",
        },
        "gates": {
            "data_quality": quality_gate,
            "trend_leg_vs_canonical_max_equity_diff": trend_max_diff,
            "trend_ledger_check": trend_ledger_gate,
            "mii_ledger_check": mii_ledger_gate,
            "mii_chain_k1": mii_gate_k1,
            "mii_chain_k2": mii_gate_k2,
        },
        "mii_full_sample_engine_check": mii_ledger_check,
        "leg_daily_return_corr_k1": leg_daily_corr,
        "trend_config": asdict(config),
        "trend_flags": asdict(flags),
        "mii_filter": asdict(mii_filter),
        "results": results,
    }
    stem = f"hype_15m_tb_mii_ensemble_backtest_{trend}_{mii}_{run_date}"
    json_path = ARTIFACTS_DIR / f"{stem}.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    equity_frame = pd.concat(
        [run["equity_curve"].rename(run["name"]) for run in runs], axis=1
    )
    equity_frame.to_csv(ARTIFACTS_DIR / f"{stem}_equity.csv", index_label="ts")
    trade_frames = []
    for run in runs:
        trades = run["trades"].copy()
        if trades.empty:
            continue
        trades.insert(0, "variant", run["name"])
        trade_frames.append(trades)
    pd.concat(trade_frames, ignore_index=True).to_csv(
        ARTIFACTS_DIR / f"{stem}_trades.csv", index=False
    )

    print(f"trend leg: {trend}  mii leg: {mii}")
    print(f"leg daily corr (K+1): {leg_daily_corr}")
    print(f"gate: data quality passed = {quality_gate['passed']}")
    print(f"gate: trend leg vs canonical max equity diff = {trend_max_diff:.2e}")
    print(f"gate: trend ledger check = {json.dumps(trend_ledger_gate, ensure_ascii=False)}")
    print(f"gate: mii ledger check = {json.dumps(mii_ledger_gate, ensure_ascii=False)}")
    print(f"gate: mii chain k1 = {json.dumps(mii_gate_k1)}  k2 = {json.dumps(mii_gate_k2)}")
    print("mii full-sample engine check:", json.dumps(mii_ledger_check, ensure_ascii=False))
    print()
    header = f"{'variant':>26}  {'total%':>10}  {'annual%':>10}  {'maxDD%':>8}  {'sharpe':>6}  {'trades':>6}  {'win%':>6}"
    print(header)
    for item in results:
        m = item["metrics"]
        print(
            f"{item['name']:>26}  {m['total_return_pct']:>10.2f}  {m['annual_return_pct']:>10.2f}  "
            f"{m['max_drawdown_pct']:>8.2f}  {m['sharpe']:>6.2f}  {m['trades']:>6}  {m['win_rate_pct']:>6.2f}"
        )
    print()
    print("slice total returns (%):")
    windows = [s["window"] for s in results[0]["slices"]]
    print(f"{'variant':>26}  " + "  ".join(f"{w:>9}" for w in windows))
    for item in results:
        by_window = {s["window"]: s["return_pct"] for s in item["slices"]}
        print(
            f"{item['name']:>26}  "
            + "  ".join(f"{by_window.get(w, float('nan')):>9.2f}" for w in windows)
        )
    print()
    print("slice max drawdowns (%):")
    print(f"{'variant':>26}  " + "  ".join(f"{w:>9}" for w in windows))
    for item in results:
        by_window = {s["window"]: s["max_drawdown_pct"] for s in item["slices"]}
        print(
            f"{item['name']:>26}  "
            + "  ".join(f"{by_window.get(w, float('nan')):>9.2f}" for w in windows)
        )
    print()
    print(f"summary -> {json_path}")


if __name__ == "__main__":
    main()
