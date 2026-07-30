"""精确回放 7/13 与 7/17 空头 giveaway：V35 全进全出 vs V35.3 分批路径。

目标交易：
- 2026-07-13 14:45 UTC short：实盘接近 TP 后打满 SL（-1321 USDT）
- 2026-07-17 02:00 UTC short：实盘 manual_exit；研究路径可到 TP

本脚本在完整 V35.3 引擎上抽取这两笔，并输出逐根 mark-to-market
与分批/最终成交的逐笔 PnL 表。不修改冻结版、不修改 runner。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
FILLS_PATH = ARTIFACT_DIR / f"{OUT_STEM}_fills.csv"
BARS_PATH = ARTIFACT_DIR / f"{OUT_STEM}_bars.csv"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"

TARGET_ENTRIES = (
    {
        "trade_id": "2026-07-13_short_giveaway",
        "entry_ts": "2026-07-13 14:45:00+00:00",
        "live": {
            "entry_price": 64.146,
            "allocation": 3.0,
            "entry_atr": 0.3422410714,
            "net_pnl_usdt": -1321.47,
            "trade_return_pct": -11.3559,
            "exit_reason": "stop_loss",
            "note": "MFE~4.83ATR then full SL7; V35.1 era live",
        },
    },
    {
        "trade_id": "2026-07-17_short_manual",
        "entry_ts": "2026-07-17 02:00:00+00:00",
        "live": {
            "trade_return_pct": -4.1278,
            "exit_reason": "manual_exit",
            "research_expected_return_pct_v35": 6.1765,
            "note": "manual exit misclassified; research V35 expected TP",
        },
    },
)


def v35_3_spec() -> stop_engine.StopPartialSpec:
    return stop_engine.StopPartialSpec(
        name="v35_3",
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
        directional_stop_replaces_hard_stop=True,
    )


def find_trade(trades: pd.DataFrame, entry_ts: str) -> dict[str, Any] | None:
    if trades.empty:
        return None
    target = pd.Timestamp(entry_ts)
    matched = trades[pd.to_datetime(trades["entry_ts"]) == target]
    if matched.empty:
        return None
    return matched.iloc[0].to_dict()


def replay_bars_for_trade(
    *,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    trade: dict[str, Any],
    config: base.V35Config,
    hard_stop_atr: float,
    profit_partial: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Isolated walk from known entry to exit under one exit rule set.

    Uses the trade's research entry fields; ignores portfolio path dependence
    so fill economics are comparable across variants for the same episode.
    """
    entry_bar = int(trade["entry_bar"])
    direction = int(trade["direction"])
    entry_price = float(trade["entry_price"])
    entry_atr = float(trade["entry_atr"])
    allocation0 = float(trade["allocation"])
    equity = 1.0
    cost = config.trade_cost_rate * allocation0
    equity *= 1.0 - cost
    allocation = allocation0
    previous_price = entry_price
    mfe_atr = 0.0
    partial_taken = False
    bars: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = [
        {
            "event": "entry",
            "ts": str(trade["entry_ts"]),
            "price": entry_price,
            "allocation_closed": 0.0,
            "allocation_remaining": allocation,
            "fill_cost": cost,
            "equity_after": equity,
            "mfe_atr": 0.0,
            "note": "entry market",
        }
    ]

    take_price = entry_price + direction * config.take_profit_atr * entry_atr
    hard_stop_price = entry_price - direction * hard_stop_atr * entry_atr
    profit_partial_price = (
        entry_price + direction * stop_engine.PROFIT_TRIGGER_ATR * entry_atr
        if profit_partial and direction == -1
        else None
    )

    for i in range(entry_bar, len(frame)):
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])

        funding_pnl = -direction * allocation * float(funding.iloc[i])
        equity *= 1.0 + funding_pnl

        if direction == 1:
            mfe_atr = max(mfe_atr, (high - entry_price) / entry_atr)
            hard_stop_hit = low <= hard_stop_price
            take_hit = high >= take_price
            profit_hit = False
        else:
            mfe_atr = max(mfe_atr, (entry_price - low) / entry_atr)
            hard_stop_hit = high >= hard_stop_price
            take_hit = low <= take_price
            profit_hit = (
                profit_partial_price is not None
                and not partial_taken
                and low <= profit_partial_price
            )

        event = "hold"
        fill_price = None
        closed = 0.0
        exit_now = False
        reason = None

        if hard_stop_hit:
            fill_price = hard_stop_price
            closed = allocation
            exit_now = True
            reason = "stop_loss"
            event = "final_stop"
        elif profit_hit:
            fill_price = float(profit_partial_price)
            closed = allocation0 * stop_engine.PROFIT_FRACTION
            pnl = direction * allocation * (fill_price / previous_price - 1.0)
            fill_cost = config.trade_cost_rate * closed
            equity *= 1.0 + pnl - fill_cost
            allocation -= closed
            previous_price = fill_price
            partial_taken = True
            fills.append(
                {
                    "event": "profit_partial_75pct",
                    "ts": str(ts),
                    "price": fill_price,
                    "allocation_closed": closed,
                    "allocation_remaining": allocation,
                    "fill_cost": fill_cost,
                    "equity_after": equity,
                    "mfe_atr": mfe_atr,
                    "note": (
                        f"4.4ATR reduce; remaining keeps TP5/SL{hard_stop_atr:g}"
                    ),
                }
            )
            # same-bar remainder may still hit TP after partial
            if take_hit:
                fill_price = take_price
                closed = allocation
                exit_now = True
                reason = "take_profit"
                event = "final_tp_after_partial"
            else:
                event = "partial_only"
        elif take_hit:
            fill_price = take_price
            closed = allocation
            exit_now = True
            reason = "take_profit"
            event = "final_tp"

        if exit_now:
            assert fill_price is not None
            pnl = direction * allocation * (fill_price / previous_price - 1.0)
            fill_cost = config.trade_cost_rate * closed
            equity *= 1.0 + pnl - fill_cost
            allocation = 0.0
            fills.append(
                {
                    "event": event,
                    "ts": str(ts),
                    "price": fill_price,
                    "allocation_closed": closed,
                    "allocation_remaining": 0.0,
                    "fill_cost": fill_cost,
                    "equity_after": equity,
                    "mfe_atr": mfe_atr,
                    "note": reason,
                }
            )
            bars.append(
                {
                    "ts": str(ts),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "allocation": 0.0,
                    "mfe_atr": mfe_atr,
                    "mark_equity": equity,
                    "event": event,
                    "favorable_atr": (
                        (entry_price - low) / entry_atr
                        if direction == -1
                        else (high - entry_price) / entry_atr
                    ),
                    "adverse_atr": (
                        (high - entry_price) / entry_atr
                        if direction == -1
                        else (entry_price - low) / entry_atr
                    ),
                }
            )
            break

        # mark to close
        pnl = direction * allocation * (close / previous_price - 1.0)
        equity *= 1.0 + pnl
        previous_price = close
        weak = float(features["adx"].iloc[i]) < config.adx_exit
        bars.append(
            {
                "ts": str(ts),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "allocation": allocation,
                "mfe_atr": mfe_atr,
                "mark_equity": equity,
                "event": event,
                "adx": float(features["adx"].iloc[i]),
                "adx_weak": weak,
                "favorable_atr": (
                    (entry_price - low) / entry_atr
                    if direction == -1
                    else (high - entry_price) / entry_atr
                ),
                "adverse_atr": (
                    (high - entry_price) / entry_atr
                    if direction == -1
                    else (entry_price - low) / entry_atr
                ),
            }
        )
        if i - entry_bar >= config.max_hold_bars:
            fills.append(
                {
                    "event": "timeout_open_next",
                    "ts": str(ts),
                    "price": close,
                    "allocation_closed": 0.0,
                    "allocation_remaining": allocation,
                    "fill_cost": 0.0,
                    "equity_after": equity,
                    "mfe_atr": mfe_atr,
                    "note": "timeout pending; isolated replay stops at signal bar",
                }
            )
            break
    else:
        fills.append(
            {
                "event": "still_open_at_data_end",
                "ts": str(frame.index[-1]),
                "price": float(frame["close"].iloc[-1]),
                "allocation_closed": 0.0,
                "allocation_remaining": allocation,
                "fill_cost": 0.0,
                "equity_after": equity,
                "mfe_atr": mfe_atr,
                "note": "data ended before exit",
            }
        )

    return fills, bars


def peak_giveaway_stats(bars: list[dict[str, Any]]) -> dict[str, Any]:
    if not bars:
        return {}
    frame = pd.DataFrame(bars)
    peak_i = int(frame["mfe_atr"].idxmax())
    peak = frame.loc[peak_i]
    final = frame.iloc[-1]
    return {
        "peak_mfe_atr": float(peak["mfe_atr"]),
        "peak_ts": peak["ts"],
        "equity_at_peak_mark": float(peak["mark_equity"]),
        "return_at_peak_mark_pct": round(
            (float(peak["mark_equity"]) - 1.0) * 100.0, 4
        ),
        "final_equity": float(final["mark_equity"]),
        "final_return_pct": round((float(final["mark_equity"]) - 1.0) * 100.0, 4),
        "giveaway_from_peak_pp": round(
            (float(peak["mark_equity"]) - float(final["mark_equity"])) * 100.0,
            4,
        ),
        "bars": int(len(frame)),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )

    # Full-path engines for trade extraction / portfolio metrics.
    v35_1, _ = partial.run_backtest(
        spec=partial.PartialSpec("v35_1", None, 0.0),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        cooldown_bars=0,
    )
    v35_3, v35_3_audit = stop_engine.run_backtest(
        spec=v35_3_spec(),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )

    fill_rows: list[dict[str, Any]] = []
    bar_rows: list[dict[str, Any]] = []
    episode_summaries: list[dict[str, Any]] = []

    for target in TARGET_ENTRIES:
        entry_ts = target["entry_ts"]
        trade_v35_1 = find_trade(v35_1.trades, entry_ts)
        trade_v35_3 = find_trade(v35_3.trades, entry_ts)
        if trade_v35_3 is None:
            episode_summaries.append(
                {
                    "trade_id": target["trade_id"],
                    "entry_ts": entry_ts,
                    "error": "trade not found under V35.3 full path",
                    "live": target["live"],
                }
            )
            continue

        # Isolated replays for clean fill economics.
        fills_full, bars_full = replay_bars_for_trade(
            frame=frame,
            funding=funding,
            features=features,
            trade=trade_v35_3,
            config=config,
            hard_stop_atr=7.0,
            profit_partial=False,
        )
        fills_partial, bars_partial = replay_bars_for_trade(
            frame=frame,
            funding=funding,
            features=features,
            trade=trade_v35_3,
            config=config,
            hard_stop_atr=5.70,
            profit_partial=True,
        )

        for row in fills_full:
            fill_rows.append(
                {
                    "trade_id": target["trade_id"],
                    "variant": "isolated_v35_full_inout_sl7",
                    **row,
                }
            )
        for row in fills_partial:
            fill_rows.append(
                {
                    "trade_id": target["trade_id"],
                    "variant": "isolated_v35_3_partial_sl57",
                    **row,
                }
            )
        for row in bars_partial:
            bar_rows.append(
                {
                    "trade_id": target["trade_id"],
                    "variant": "isolated_v35_3_partial_sl57",
                    **row,
                }
            )

        signal_i = int(trade_v35_3["entry_bar"]) - config.entry_delay_bars
        episode_summaries.append(
            {
                "trade_id": target["trade_id"],
                "entry_ts": entry_ts,
                "live": target["live"],
                "signal_features": {
                    "signal_ts": str(frame.index[signal_i]),
                    "ema_spread": float(features["ema_spread"].iloc[signal_i]),
                    "adx28": float(features["adx"].iloc[signal_i]),
                    "volume_surge": float(
                        features["volume_surge"].iloc[signal_i]
                    ),
                },
                "full_path_v35_1": None
                if trade_v35_1 is None
                else {
                    k: trade_v35_1[k]
                    for k in (
                        "entry_price",
                        "exit_ts",
                        "exit_price",
                        "entry_atr",
                        "allocation",
                        "mfe_atr",
                        "exit_reason",
                        "trade_return",
                        "partial_taken",
                        "partial_ts",
                        "partial_price",
                    )
                    if k in trade_v35_1
                },
                "full_path_v35_3": {
                    k: trade_v35_3[k]
                    for k in (
                        "entry_price",
                        "exit_ts",
                        "exit_price",
                        "entry_atr",
                        "allocation",
                        "remaining_allocation_at_exit",
                        "mfe_atr",
                        "exit_reason",
                        "trade_return",
                        "profit_partial_taken",
                        "profit_partial_ts",
                        "profit_partial_price",
                        "profit_partial_allocation",
                    )
                    if k in trade_v35_3
                },
                "isolated_v35_full_inout_sl7": {
                    "fills": fills_full,
                    "peak_stats": peak_giveaway_stats(bars_full),
                    "final_return_pct": round(
                        (fills_full[-1]["equity_after"] - 1.0) * 100.0, 4
                    ),
                },
                "isolated_v35_3_partial_sl57": {
                    "fills": fills_partial,
                    "peak_stats": peak_giveaway_stats(bars_partial),
                    "final_return_pct": round(
                        (fills_partial[-1]["equity_after"] - 1.0) * 100.0, 4
                    ),
                },
                "delta_partial_minus_full_pp": round(
                    (fills_partial[-1]["equity_after"] - fills_full[-1]["equity_after"])
                    * 100.0,
                    4,
                ),
            }
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 giveaway short partial precise replay",
        "run_date": "2026-07-29",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "targets": [t["trade_id"] for t in TARGET_ENTRIES],
            "isolated_replay": (
                "Uses research entry price/ATR/allocation from the V35.3 "
                "full-path trade; ignores prior portfolio path so fill PnL "
                "is comparable across exit variants for the same episode."
            ),
            "v35_3_rules": (
                "Short MFE4.4ATR reduce 75% once; remaining 25% keeps TP5 and "
                "directional hard stop 5.70ATR; stop-first; costs 0.00085/fill; "
                "funding on remaining allocation."
            ),
            "full_inout_rules": (
                "No profit partial; hard stop 7.0ATR; TP5; same costs/funding."
            ),
            "live_numbers": "Anchored from runner-tracking reports; not re-fetched.",
        },
        "portfolio_context": {
            "v35_1": v35_1.metrics,
            "v35_3": v35_3.metrics,
            "v35_3_audit": {
                "profit_partial_events": v35_3_audit.get(
                    "profit_partial_events"
                ),
                "stop_partial_events": v35_3_audit.get("stop_partial_events"),
            },
            "standard_slices_v35_3": v35_3.slices,
        },
        "episodes": episode_summaries,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(fill_rows).to_csv(FILLS_PATH, index=False)
    pd.DataFrame(bar_rows).to_csv(BARS_PATH, index=False)
    pd.concat(
        [
            v35_1.trades.assign(variant="v35_1_full_path"),
            v35_3.trades.assign(variant="v35_3_full_path"),
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']}"
    )
    for ep in episode_summaries:
        if "error" in ep:
            print(f"{ep['trade_id']}: ERROR {ep['error']}")
            continue
        full_r = ep["isolated_v35_full_inout_sl7"]["final_return_pct"]
        part_r = ep["isolated_v35_3_partial_sl57"]["final_return_pct"]
        peak = ep["isolated_v35_3_partial_sl57"]["peak_stats"]
        print(
            f"{ep['trade_id']}: full {full_r:+.2f}% -> partial {part_r:+.2f}% "
            f"(Δ {ep['delta_partial_minus_full_pp']:+.2f}pp) "
            f"peak_mfe={peak.get('peak_mfe_atr', float('nan')):.3f} "
            f"v35_3_path={ep['full_path_v35_3'].get('exit_reason')} "
            f"{float(ep['full_path_v35_3'].get('trade_return', 0)) * 100:+.2f}%"
        )
    print(f"summary -> {SUMMARY_PATH}")
    print(f"fills   -> {FILLS_PATH}")
    print(f"bars    -> {BARS_PATH}")


if __name__ == "__main__":
    main()
