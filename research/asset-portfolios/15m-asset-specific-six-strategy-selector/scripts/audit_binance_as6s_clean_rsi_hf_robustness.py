from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SEARCH_DIR = FAMILY_DIR / "artifacts/per_asset_clean_rsi_hf"
OUTPUT_DIR = FAMILY_DIR / "artifacts/per_asset_clean_rsi_hf_robustness"
MII_SCRIPTS = ROOT / "research/hype/15m-multi-indicator-intraday/scripts"
AS6S_SCRIPTS = FAMILY_DIR / "scripts"
sys.path.insert(0, str(MII_SCRIPTS))
sys.path.insert(0, str(AS6S_SCRIPTS))

import research_hype_15m_mii_clean_evolution as evolution  # noqa: E402
import research_hype_15m_mii_search as mii  # noqa: E402
from as6s_engine import (  # noqa: E402
    FEE_PER_FILL,
    REUSED_END,
    STARTS,
    adverse_fill,
    funding_arrays,
    funding_return,
    load_funding,
    load_symbol_frame,
)
from research_binance_as6s_clean_rsi_hf_search import Config  # noqa: E402
from research_binance_as6s_per_asset_hf_discovery import (  # noqa: E402
    HISTORICAL_OOS_END,
    PREFIT_END,
)
from research_binance_as6s_per_asset_hf_filter_tune import finite_pf  # noqa: E402


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    slippage: float
    entry_delay_bars: int


SCENARIOS = (
    Scenario("base_4bps_k1", 0.0004, 1),
    Scenario("stress_8bps_k1", 0.0008, 1),
    Scenario("base_4bps_k2", 0.0004, 2),
    Scenario("stress_8bps_k2", 0.0008, 2),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Funding-aware, fill-aware robustness audit for clean-RSI candidates."
    )
    parser.add_argument("--symbol", choices=tuple(STARTS), required=True)
    parser.add_argument("--candidates", type=int, default=300)
    parser.add_argument("--top", type=int, default=100)
    return parser.parse_args()


def robust_trades(
    market: mii.MarketArrays,
    state: mii.SignalState,
    exit_spec: mii.ExitSpec,
    funding_times: np.ndarray,
    funding_prefix: np.ndarray,
    *,
    slippage: float,
    entry_delay_bars: int,
) -> list[mii.EventTrade]:
    trades: list[mii.EventTrade] = []
    n = len(market.open)
    open_exit_reasons = {"max_hold", "stop_gap", "take_profit_gap"}
    for signal_idx, direction_value in zip(
        state.signal_i, state.directions, strict=False
    ):
        entry_i = int(signal_idx + entry_delay_bars)
        if entry_i >= n - 1:
            continue
        forced_exit_i = min(entry_i + exit_spec.max_hold_bars, n - 1)
        if forced_exit_i <= entry_i:
            continue

        direction = int(direction_value)
        entry_fill = adverse_fill(
            float(market.open[entry_i]), direction, entry=True, slippage=slippage
        )
        stop_price = entry_fill * (1.0 - direction * exit_spec.stop_pct)
        take_profit_price = entry_fill * (
            1.0 + direction * float(exit_spec.take_profit_pct)
        )
        exit_i = forced_exit_i
        exit_base = float(market.open[forced_exit_i])
        exit_reason = "max_hold"
        min_path_price = 0.0
        max_path_price = 0.0

        # Timeout is filled at the opening event before that bar's range is known.
        for index in range(entry_i, forced_exit_i):
            bar_open = float(market.open[index])
            high = float(market.high[index])
            low = float(market.low[index])
            if direction > 0:
                min_path_price = min(min_path_price, low / entry_fill - 1.0)
                max_path_price = max(max_path_price, high / entry_fill - 1.0)
                if bar_open <= stop_price:
                    exit_i, exit_base, exit_reason = index, bar_open, "stop_gap"
                    break
                if bar_open >= take_profit_price:
                    exit_i, exit_base, exit_reason = (
                        index,
                        take_profit_price,
                        "take_profit_gap",
                    )
                    break
                if low <= stop_price:
                    exit_i, exit_base, exit_reason = index, stop_price, "stop_loss"
                    break
                if high >= take_profit_price:
                    exit_i, exit_base, exit_reason = (
                        index,
                        take_profit_price,
                        "take_profit",
                    )
                    break
            else:
                min_path_price = min(min_path_price, 1.0 - high / entry_fill)
                max_path_price = max(max_path_price, 1.0 - low / entry_fill)
                if bar_open >= stop_price:
                    exit_i, exit_base, exit_reason = index, bar_open, "stop_gap"
                    break
                if bar_open <= take_profit_price:
                    exit_i, exit_base, exit_reason = (
                        index,
                        take_profit_price,
                        "take_profit_gap",
                    )
                    break
                if high >= stop_price:
                    exit_i, exit_base, exit_reason = index, stop_price, "stop_loss"
                    break
                if low <= take_profit_price:
                    exit_i, exit_base, exit_reason = (
                        index,
                        take_profit_price,
                        "take_profit",
                    )
                    break

        exit_fill = adverse_fill(
            exit_base, direction, entry=False, slippage=slippage
        )
        price_return = direction * (exit_fill / entry_fill - 1.0)
        entry_ts = pd.Timestamp(market.ts[entry_i])
        exit_ts = pd.Timestamp(market.ts[exit_i])
        funding_ret = funding_return(
            direction,
            entry_ts,
            exit_ts,
            funding_times,
            funding_prefix,
        )
        fee_ret = -FEE_PER_FILL * (1.0 + exit_fill / entry_fill)
        net_return = float(price_return + funding_ret + fee_ret)
        conservative_mae = min(
            float(min_path_price - 2.0 * FEE_PER_FILL), net_return
        )
        signal_i = int(signal_idx)
        trades.append(
            mii.EventTrade(
                signal_i=signal_i,
                entry_i=entry_i,
                exit_i=int(exit_i),
                direction=direction,
                entry_ts=entry_ts,
                exit_ts=exit_ts,
                entry_price=entry_fill,
                exit_price=float(exit_fill),
                raw_return=net_return,
                min_path_return=conservative_mae,
                max_path_return=float(max_path_price),
                bars_held=int(max(exit_i - entry_i, 0)),
                exit_reason=exit_reason,
                signal_name=state.spec.name,
                signal_kind=state.spec.kind,
                adx14=mii.finite(market.adx14[signal_i], default=0.0),
                rvol96=mii.finite(market.rvol96[signal_i], default=0.0),
                h1_dir_spread=(
                    mii.finite(market.h1_spread[signal_i], default=0.0) * direction
                ),
                h4_dir_spread=(
                    mii.finite(market.h4_spread[signal_i], default=0.0) * direction
                ),
                dir_ret16=mii.finite(market.ret16[signal_i], default=0.0)
                * direction,
                dir_ret48=mii.finite(market.ret48[signal_i], default=0.0)
                * direction,
                dir_ret96=mii.finite(market.ret96[signal_i], default=0.0)
                * direction,
                dir_macd=mii.finite(market.macd_hist[signal_i], default=0.0)
                * direction,
                dir_rsi14=(
                    mii.finite(market.rsi14[signal_i], default=50.0)
                    if direction > 0
                    else 100.0
                    - mii.finite(market.rsi14[signal_i], default=50.0)
                ),
                atr_pct96=mii.finite(market.atr_pct96[signal_i], default=0.0),
                atr_ratio96_672=mii.finite(
                    market.atr_ratio96_672[signal_i], default=99.0
                ),
                previous_signal_age=mii.finite(
                    state.previous_signal_age[signal_i], default=0.0
                ),
                churn192=mii.finite(state.churn192[signal_i], default=999.0),
            )
        )
    # Keep the variable explicit: these exits release the sleeve at the bar open.
    if not open_exit_reasons:
        raise AssertionError("unreachable")
    return trades


def select_nonoverlap(
    trades: Iterable[mii.EventTrade], filter_spec: mii.FilterSpec
) -> list[mii.EventTrade]:
    selected: list[mii.EventTrade] = []
    available_i = -1
    open_exit_reasons = {"max_hold", "stop_gap", "take_profit_gap"}
    for trade in trades:
        if trade.entry_i < available_i or not mii.passes_filter(trade, filter_spec):
            continue
        selected.append(trade)
        intrabar_delay = 0 if trade.exit_reason in open_exit_reasons else 1
        available_i = trade.exit_i + filter_spec.cooldown_bars + intrabar_delay
    return selected


def metrics(
    trades: Iterable[mii.EventTrade], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, Any]:
    chosen = sorted(
        (
            trade
            for trade in trades
            if start <= trade.entry_ts and trade.exit_ts < end
        ),
        key=lambda trade: trade.exit_ts,
    )
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    returns: list[float] = []
    for trade in chosen:
        trough = equity * max(1e-9, 1.0 + trade.min_path_return)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(1e-9, 1.0 + trade.raw_return)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        returns.append(trade.raw_return)
    wins = [value for value in returns if value > 0.0]
    losses = [value for value in returns if value < 0.0]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    return {
        "trades": len(chosen),
        "wins": len(wins),
        "win_rate": len(wins) / len(chosen) if chosen else 0.0,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (365.25 / days) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else math.inf,
        "avg_trade": float(np.mean(returns)) if returns else 0.0,
        "trades_per_day": len(chosen) / days,
        "long_trades": sum(trade.direction > 0 for trade in chosen),
        "short_trades": sum(trade.direction < 0 for trade in chosen),
    }


def row_score(row: dict[str, Any]) -> float:
    evidence = [
        row[scenario.name][window]
        for scenario in SCENARIOS
        for window in ("prefit", "historical_oos", "current_3m")
    ]
    if min(metric["trades"] for metric in evidence) < 6:
        return -1e9
    min_win = min(metric["win_rate"] for metric in evidence)
    worst_dd = min(metric["max_dd"] for metric in evidence)
    min_pf = min(finite_pf(metric["profit_factor"]) for metric in evidence)
    positives = sum(metric["total_return"] > 0.0 for metric in evidence)
    base = row["base_4bps_k1"]
    log_annual = sum(
        weight * math.log(max(base[window]["annual_multiple"], 1e-9))
        for window, weight in (
            ("prefit", 1.0),
            ("historical_oos", 1.2),
            ("current_3m", 0.9),
        )
    )
    return float(
        log_annual
        + 4.0 * min_win
        + 0.5 * math.log(min_pf)
        + 2.0 * worst_dd
        + 0.5 * positives
        + 12.0 * min(0.0, min_win - 0.70)
        + 14.0 * min(0.0, worst_dd + 0.20)
    )


def all_windows_pass(
    row: dict[str, Any], *, min_win_rate: float, min_trades: int
) -> bool:
    return all(
        metric["trades"] >= min_trades
        and metric["win_rate"] >= min_win_rate
        and metric["total_return"] > 0.0
        and metric["max_dd"] > -0.20
        for scenario in SCENARIOS
        for metric in (
            row[scenario.name]["prefit"],
            row[scenario.name]["historical_oos"],
            row[scenario.name]["current_3m"],
        )
    )


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_path = (
        SEARCH_DIR / f"{args.symbol.lower()}_clean_rsi_hf_2026-07-14.json"
    )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    candidates = source["ranking"][: args.candidates]
    if not candidates:
        raise RuntimeError(f"{args.symbol} has no discovery candidates")

    raw = load_symbol_frame(args.symbol, end=REUSED_END)[
        ["ts", "open", "high", "low", "close", "volume"]
    ].copy()
    features = evolution.add_rsi_features(evolution.add_features(raw, []))
    market = mii.build_market_arrays(features)
    funding_times, funding_prefix = funding_arrays(
        load_funding(args.symbol, end=REUSED_END)
    )
    configs = [Config(**row["config"]) for row in candidates]
    states: dict[str, mii.SignalState] = {}
    cache: dict[tuple[str, str, str], list[mii.EventTrade]] = {}
    ranking: list[dict[str, Any]] = []

    for index, config in enumerate(configs, start=1):
        state = states.setdefault(
            config.signal.name, mii.signal_state(features, config.signal)
        )
        row: dict[str, Any] = {
            "config": asdict(config),
            "signal_name": config.signal.name,
            "exit_name": config.exit.name,
            "filter_name": config.filter.name,
        }
        for scenario in SCENARIOS:
            key = (config.signal.name, config.exit.name, scenario.name)
            raw_trades = cache.get(key)
            if raw_trades is None:
                raw_trades = robust_trades(
                    market,
                    state,
                    config.exit,
                    funding_times,
                    funding_prefix,
                    slippage=scenario.slippage,
                    entry_delay_bars=scenario.entry_delay_bars,
                )
                cache[key] = raw_trades
            selected = select_nonoverlap(raw_trades, config.filter)
            row[scenario.name] = {
                "prefit": metrics(selected, STARTS[args.symbol], PREFIT_END),
                "historical_oos": metrics(
                    selected, PREFIT_END, HISTORICAL_OOS_END
                ),
                "current_3m": metrics(
                    selected, HISTORICAL_OOS_END, REUSED_END
                ),
                "through_current": metrics(
                    selected, STARTS[args.symbol], REUSED_END
                ),
            }
        row["score"] = row_score(row)
        row["hard80"] = all_windows_pass(
            row, min_win_rate=0.80, min_trades=8
        )
        row["portfolio_eligible"] = all_windows_pass(
            row, min_win_rate=0.70, min_trades=6
        )
        ranking.append(row)
        if index % 25 == 0:
            print(
                f"{args.symbol} robust={index}/{len(configs)} cache={len(cache)}",
                flush=True,
            )

    ranking.sort(key=lambda value: value["score"], reverse=True)
    hard80 = [row for row in ranking if row["hard80"]]
    portfolio_eligible = [row for row in ranking if row["portfolio_eligible"]]
    output = OUTPUT_DIR / (
        f"{args.symbol.lower()}_clean_rsi_hf_robustness_2026-07-14.json"
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "asset_first_clean_rsi_robustness_diagnostic_not_live_ready",
        "symbol": args.symbol,
        "source": str(source_path.relative_to(ROOT)),
        "execution": (
            "closed 15m signal; next-open K+1/K+2; fill-aware 4/8bps; "
            "actual Binance funding; open-gap safe; same-bar stop-first; "
            "timeout open before intrabar; one sleeve position"
        ),
        "audited_candidates": len(candidates),
        "hard80_count": len(hard80),
        "portfolio_eligible_70_count": len(portfolio_eligible),
        "disclosure": (
            "Current 3m participates in this diagnostic ranking. Final locked future "
            "OOS is [2026-07-14T09:00Z, 2026-10-14T09:00Z)."
        ),
        "ranking": ranking[: args.top],
        "hard80": hard80[: args.top],
        "portfolio_eligible": portfolio_eligible[: args.top],
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "hard80": len(hard80),
                "portfolio_eligible": len(portfolio_eligible),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
