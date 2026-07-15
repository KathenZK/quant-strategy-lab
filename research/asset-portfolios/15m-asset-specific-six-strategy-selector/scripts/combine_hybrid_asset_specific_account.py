from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from as6s_engine import (
    BASE_SLIPPAGE,
    FEE_PER_FILL,
    PREFIT_END,
    REUSED_END,
    STARTS,
    StrategyConfig,
    adverse_fill,
    funding_arrays,
    funding_return,
    load_funding,
    load_symbol_frame,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
REVEAL_PATH = FAMILY_DIR / "artifacts/binance_15m_as6s_reused_holdout_2026-07-14.json"
LEGACY_PATH = FAMILY_DIR / "artifacts/binance_legacy_asset_specific_1h_sleeves_2026-07-14.json"
LEGACY_TRADES = FAMILY_DIR / "artifacts/binance_legacy_asset_specific_1h_sleeves_trades_2026-07-14.csv"
OUTPUT = FAMILY_DIR / "artifacts/binance_hybrid_asset_specific_account_2026-07-14.json"
TRADES_OUTPUT = FAMILY_DIR / "artifacts/binance_hybrid_asset_specific_account_trades_2026-07-14.csv"


@dataclass(frozen=True, slots=True)
class UnifiedTrade:
    sleeve: str
    symbol: str
    mechanism: str
    source_timeframe: str
    side: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_price: float
    net_return_1x: float
    mae_return_1x: float
    raw_strength: float
    cooldown_hours: int = 0
    strength: float = 0.0
    exposure: float = 1.0
    exit_reason: str = ""


def strict_metrics(
    trades: Iterable[UnifiedTrade], start: pd.Timestamp, end: pd.Timestamp, scale: float = 1.0
) -> dict[str, Any]:
    chosen = sorted(
        (trade for trade in trades if start <= trade.entry_ts and trade.exit_ts < end),
        key=lambda trade: trade.exit_ts,
    )
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    returns: list[float] = []
    for trade in chosen:
        leverage = scale * trade.exposure
        trough = equity * max(1e-9, 1.0 + leverage * trade.mae_return_1x)
        max_dd = min(max_dd, trough / peak - 1.0)
        value = leverage * trade.net_return_1x
        equity *= max(1e-9, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        returns.append(value)
    positives = [value for value in returns if value > 0.0]
    negatives = [value for value in returns if value < 0.0]
    years = max((end - start).total_seconds() / (365.25 * 86400.0), 1 / 365.25)
    by_sleeve: dict[str, int] = {}
    for trade in chosen:
        by_sleeve[trade.sleeve] = by_sleeve.get(trade.sleeve, 0) + 1
    return {
        "trades": len(chosen),
        "wins": len(positives),
        "win_rate": len(positives) / len(chosen) if chosen else 0.0,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (1.0 / years) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": sum(positives) / abs(sum(negatives)) if negatives else math.inf,
        "long_trades": sum(trade.side > 0 for trade in chosen),
        "short_trades": sum(trade.side < 0 for trade in chosen),
        "preemptions": sum(trade.exit_reason == "strong_breakout_preemption" for trade in chosen),
        "by_sleeve": by_sleeve,
    }


def sleeve_quality(metric: dict[str, Any]) -> float:
    annual_term = np.clip(math.log(max(metric["annual_multiple"], 1e-9)) / math.log(5.0), 0.0, 1.0)
    pf_term = np.clip(metric["profit_factor"] / 5.0, 0.0, 1.0)
    return float(0.55 * metric["win_rate"] + 0.25 * annual_term + 0.20 * pf_term)


def single_sleeve_nonoverlap(trades: list[UnifiedTrade]) -> list[UnifiedTrade]:
    selected: list[UnifiedTrade] = []
    blocked_until: pd.Timestamp | None = None
    for trade in sorted(trades, key=lambda value: (value.entry_ts, value.exit_ts)):
        if blocked_until is not None and trade.entry_ts <= blocked_until:
            continue
        selected.append(trade)
        blocked_until = trade.exit_ts + pd.Timedelta(hours=trade.cooldown_hours)
    return selected


def choose_exposure(
    scenarios: dict[str, list[UnifiedTrade]], start: pd.Timestamp
) -> tuple[float, bool, dict[str, Any]]:
    chosen = 0.5
    robust = False
    audit: dict[str, Any] = {}
    for exposure in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
        scenario_metrics = {
            name: strict_metrics(
                (
                    replace(trade, exposure=exposure)
                    for trade in single_sleeve_nonoverlap(trades)
                ),
                start,
                PREFIT_END,
            )
            for name, trades in scenarios.items()
        }
        base = scenario_metrics["base"]
        passed = (
            base["trades"] >= 18
            and base["win_rate"] >= 0.75
            and all(value["total_return"] > 0.0 for value in scenario_metrics.values())
            and all(value["max_dd"] > -0.15 for value in scenario_metrics.values())
        )
        if passed:
            chosen = exposure
            robust = True
            audit = scenario_metrics
    if not audit:
        audit = {
            name: strict_metrics(
                (
                    replace(trade, exposure=chosen)
                    for trade in single_sleeve_nonoverlap(trades)
                ),
                start,
                PREFIT_END,
            )
            for name, trades in scenarios.items()
        }
    return chosen, robust, audit


def classify_reused(
    scenarios: dict[str, list[UnifiedTrade]],
    *,
    start: pd.Timestamp,
    exposure: float,
    prefit_robust: bool,
) -> tuple[str, dict[str, Any]]:
    reused = {
        name: strict_metrics(
            (
                replace(trade, exposure=exposure)
                for trade in single_sleeve_nonoverlap(trades)
            ),
            PREFIT_END,
            REUSED_END,
        )
        for name, trades in scenarios.items()
    }
    through = {
        name: strict_metrics(
            (
                replace(trade, exposure=exposure)
                for trade in single_sleeve_nonoverlap(trades)
            ),
            start,
            REUSED_END,
        )
        for name, trades in scenarios.items()
    }
    base = reused["base"]
    common = (
        all(value["total_return"] > 0.0 for value in reused.values())
        and all(value["max_dd"] > -0.20 for value in reused.values())
    )
    if base["trades"] >= 5 and base["win_rate"] >= 0.80 and common:
        classification = "strong_survivor"
    elif base["trades"] >= 5 and base["win_rate"] >= 0.70 and common:
        classification = "conditional_survivor"
    elif (
        base["trades"] >= 5
        and base["win_rate"] >= 0.80
        and reused["base"]["total_return"] > 0.0
        and reused["stress_8bps"]["total_return"] > 0.0
        and prefit_robust
        and all(value["total_return"] > 0.0 for value in through.values())
        and all(value["max_dd"] > -0.20 for value in through.values())
    ):
        classification = "k_plus_2_warning_survivor"
    elif (
        base["trades"] < 5
        and prefit_robust
        and all(value["total_return"] >= 0.0 for value in reused.values())
        and all(value["total_return"] > 0.0 for value in through.values())
        and all(value["max_dd"] > -0.20 for value in through.values())
    ):
        classification = "insufficient_reused_evidence"
    else:
        classification = "eliminated"
    return classification, {"reused": reused, "through_reused": through}


def current_scenarios(reveal: dict[str, Any]) -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, pd.Timestamp]]:
    configs = [
        StrategyConfig.from_dict(row["config"])
        for rows in reveal["results"].values()
        for row in rows.values()
    ]
    frames = {cfg.symbol: load_symbol_frame(cfg.symbol, end=REUSED_END) for cfg in configs}
    funding = {cfg.symbol: load_funding(cfg.symbol, end=REUSED_END) for cfg in configs}
    output: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for cfg in configs:
        sleeve = f"15m:{cfg.symbol}:{cfg.mechanism}"
        output[sleeve] = {}
        for scenario, slippage, delay in (
            ("base", BASE_SLIPPAGE, 1),
            ("stress_8bps", 0.0008, 1),
            ("k_plus_2", BASE_SLIPPAGE, 2),
        ):
            opportunities = simulate_opportunities(
                frames[cfg.symbol], funding[cfg.symbol], cfg,
                end=REUSED_END, slippage=slippage, entry_delay_bars=delay,
            )
            output[sleeve][scenario] = [
                UnifiedTrade(
                    sleeve=sleeve, symbol=cfg.symbol, mechanism=cfg.mechanism,
                    source_timeframe="15m", side=item.side,
                    entry_ts=item.entry_ts, exit_ts=item.exit_ts,
                    entry_price=item.entry_fill, net_return_1x=item.net_return_1x,
                    mae_return_1x=item.mae_return_1x, raw_strength=item.score,
                    cooldown_hours=0,
                    exit_reason=item.exit_reason,
                )
                for item in opportunities
            ]
    return output, {symbol: STARTS[symbol] for symbol in frames}


def legacy_scenarios(legacy: dict[str, Any]) -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, pd.Timestamp]]:
    frame = pd.read_csv(LEGACY_TRADES)
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    output: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for (asset, style), sleeve_rows in frame.groupby(["asset", "style"]):
        symbol = f"{asset}USDT"
        sleeve = f"1h:{symbol}:{style}"
        output[sleeve] = {}
        for scenario, rows in sleeve_rows.groupby("scenario"):
            output[sleeve][str(scenario)] = [
                UnifiedTrade(
                    sleeve=sleeve, symbol=symbol, mechanism=str(style),
                    source_timeframe="1h", side=int(row.side),
                    entry_ts=row.entry_ts, exit_ts=row.exit_ts,
                    entry_price=float(row.entry_price),
                    net_return_1x=float(row.net_ret_1x),
                    mae_return_1x=float(row.mae_1x), raw_strength=0.0,
                    cooldown_hours=int(row.cooldown_bars),
                    exit_reason=str(row.exit_reason),
                )
                for row in rows.itertuples()
            ]
    starts = {
        f"{asset}USDT": pd.Timestamp(value)
        for asset, value in legacy["windows"]["asset_starts"].items()
    }
    return output, starts


def choose_candidate_universe(
    all_sleeves: dict[str, dict[str, list[UnifiedTrade]]],
    starts: dict[str, pd.Timestamp],
) -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, Any]]:
    selected: dict[str, dict[str, list[UnifiedTrade]]] = {}
    audit: dict[str, Any] = {}
    for sleeve, scenarios in all_sleeves.items():
        symbol = next(iter(scenarios["base"]), None)
        symbol_name = symbol.symbol if symbol is not None else sleeve.split(":")[1]
        exposure, robust, prefit = choose_exposure(scenarios, starts[symbol_name])
        classification, diagnostic = classify_reused(
            scenarios, start=starts[symbol_name], exposure=exposure,
            prefit_robust=robust,
        )
        quality = sleeve_quality(prefit["base"])
        adjusted = {
            name: [
                replace(
                    trade,
                    exposure=exposure,
                    strength=float(0.7 * quality + 0.3 * trade.raw_strength),
                )
                for trade in trades
            ]
            for name, trades in scenarios.items()
        }
        audit[sleeve] = {
            "symbol": symbol_name, "chosen_exposure": exposure,
            "prefit_robust": robust, "prefit": prefit,
            "quality": quality, "classification": classification, **diagnostic,
        }
        if classification != "eliminated":
            selected[sleeve] = adjusted
    return selected, audit


def grouped(items: Iterable[UnifiedTrade]) -> list[tuple[pd.Timestamp, list[UnifiedTrade]]]:
    ordered = sorted(items, key=lambda trade: (trade.entry_ts, -trade.strength, trade.exit_ts))
    return [
        (timestamp, list(rows))
        for timestamp, rows in itertools.groupby(ordered, key=lambda trade: trade.entry_ts)
    ]


def nonpreemptive(items: list[UnifiedTrade], *, start: pd.Timestamp, end: pd.Timestamp) -> list[UnifiedTrade]:
    chosen: list[UnifiedTrade] = []
    blocked_until: pd.Timestamp | None = None
    sleeve_cooldown: dict[str, pd.Timestamp] = {}
    for timestamp, candidates in grouped(items):
        if timestamp < start or timestamp >= end:
            continue
        candidates = [
            trade for trade in candidates
            if trade.exit_ts < end
            and timestamp > sleeve_cooldown.get(trade.sleeve, start - pd.Timedelta(hours=1))
        ]
        if not candidates or (blocked_until is not None and timestamp <= blocked_until):
            continue
        trade = max(candidates, key=lambda value: (value.strength, -value.exit_ts.value))
        chosen.append(trade)
        blocked_until = trade.exit_ts
        sleeve_cooldown[trade.sleeve] = trade.exit_ts + pd.Timedelta(
            hours=trade.cooldown_hours
        )
    return chosen


def partial_close(
    trade: UnifiedTrade,
    exit_ts: pd.Timestamp,
    *,
    bars: dict[str, pd.DataFrame],
    funding: dict[str, tuple[np.ndarray, np.ndarray]],
    slippage: float,
) -> UnifiedTrade:
    frame = bars[trade.symbol]
    exit_open = float(frame.loc[frame["ts"] == exit_ts, "open"].iloc[0])
    exit_fill = adverse_fill(exit_open, trade.side, entry=False, slippage=slippage)
    price_return = trade.side * (exit_fill / trade.entry_price - 1.0)
    times, prefix = funding[trade.symbol]
    funding_ret = funding_return(trade.side, trade.entry_ts, exit_ts, times, prefix)
    segment = frame.loc[(frame["ts"] >= trade.entry_ts) & (frame["ts"] < exit_ts)]
    if trade.side > 0:
        adverse = float(segment["low"].min() / trade.entry_price - 1.0)
    else:
        adverse = float(1.0 - segment["high"].max() / trade.entry_price)
    net = float(price_return + funding_ret - 2.0 * FEE_PER_FILL)
    return replace(
        trade, exit_ts=exit_ts, net_return_1x=net,
        mae_return_1x=min(adverse - 2.0 * FEE_PER_FILL, net),
        exit_reason="strong_breakout_preemption",
    )


def is_breakout(trade: UnifiedTrade) -> bool:
    return trade.mechanism in {"breakout", "donchian_break", "keltner_break", "bb_break"}


def preemptive(
    items: list[UnifiedTrade], *, start: pd.Timestamp, end: pd.Timestamp,
    threshold: float, margin: float, min_hold_hours: int,
    bars: dict[str, pd.DataFrame], funding: dict[str, tuple[np.ndarray, np.ndarray]],
    slippage: float,
) -> list[UnifiedTrade]:
    chosen: list[UnifiedTrade] = []
    current: UnifiedTrade | None = None
    sleeve_cooldown: dict[str, pd.Timestamp] = {}
    min_hold = pd.Timedelta(hours=min_hold_hours)
    for timestamp, candidates in grouped(items):
        if timestamp < start or timestamp >= end:
            continue
        candidates = [
            trade for trade in candidates
            if trade.exit_ts < end
            and timestamp > sleeve_cooldown.get(trade.sleeve, start - pd.Timedelta(hours=1))
        ]
        if not candidates:
            continue
        if current is not None and current.exit_ts <= timestamp:
            ended_on_candidate_bar = current.exit_ts == timestamp
            chosen.append(current)
            sleeve_cooldown[current.sleeve] = current.exit_ts + pd.Timedelta(
                hours=current.cooldown_hours
            )
            current = None
            if ended_on_candidate_bar:
                continue
        if current is None:
            current = max(candidates, key=lambda value: (value.strength, -value.exit_ts.value))
            continue
        challengers = [
            trade for trade in candidates
            if trade.symbol != current.symbol and is_breakout(trade)
            and trade.strength >= threshold
            and trade.strength >= current.strength + margin
            and timestamp >= current.entry_ts + min_hold
        ]
        if not challengers:
            continue
        challenger = max(challengers, key=lambda value: (value.strength, -value.exit_ts.value))
        chosen.append(
            partial_close(
                current, timestamp, bars=bars, funding=funding, slippage=slippage
            )
        )
        sleeve_cooldown[current.sleeve] = timestamp + pd.Timedelta(
            hours=current.cooldown_hours
        )
        current = challenger
    if current is not None and current.exit_ts < end:
        chosen.append(current)
    return chosen


def main() -> None:
    reveal = json.loads(REVEAL_PATH.read_text(encoding="utf-8"))
    legacy = json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    current, current_starts = current_scenarios(reveal)
    old, old_starts = legacy_scenarios(legacy)
    all_sleeves = {**current, **old}
    starts = {**current_starts, **old_starts}
    candidates, sleeve_audit = choose_candidate_universe(all_sleeves, starts)
    if not candidates:
        raise RuntimeError("no candidate sleeves survived")
    active_starts = [
        starts[trade.symbol]
        for rows in candidates.values()
        for trade in rows["base"][:1]
    ]
    portfolio_start = min(active_starts)
    all_six_active_start = max(active_starts)

    bars = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in starts}
    funding_frames = {symbol: load_funding(symbol, end=REUSED_END) for symbol in starts}
    funding = {symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()}
    scenario_items = {
        scenario: [trade for rows in candidates.values() for trade in rows[scenario]]
        for scenario in ("base", "stress_8bps", "k_plus_2")
    }

    scale_grid = []
    for scale in (0.5, 0.75, 1.0):
        scenario_metrics = {
            scenario: strict_metrics(
                nonpreemptive(items, start=portfolio_start, end=PREFIT_END),
                portfolio_start,
                PREFIT_END,
                scale,
            )
            for scenario, items in scenario_items.items()
        }
        scale_grid.append((scale, scenario_metrics))
    valid_scales = [
        row
        for row in scale_grid
        if all(metric["win_rate"] >= 0.80 for metric in row[1].values())
        and all(metric["max_dd"] > -0.20 for metric in row[1].values())
        and all(metric["total_return"] > 0.0 for metric in row[1].values())
    ]
    account_scale = max(
        valid_scales or scale_grid,
        key=lambda row: row[1]["base"]["annual_multiple"],
    )[0]

    preempt_grid: list[dict[str, Any]] = []
    for threshold, margin, hold in itertools.product(
        (0.70, 0.80, 0.90), (0.05, 0.10, 0.20), (2, 4, 8, 16)
    ):
        trades = preemptive(
            scenario_items["base"], start=portfolio_start, end=PREFIT_END,
            threshold=threshold, margin=margin, min_hold_hours=hold,
            bars=bars, funding=funding, slippage=BASE_SLIPPAGE,
        )
        metric = strict_metrics(trades, portfolio_start, PREFIT_END, account_scale)
        preempt_grid.append(
            {"threshold": threshold, "margin": margin, "min_hold_hours": hold, "prefit": metric}
        )
    frozen_preempt = max(
        preempt_grid,
        key=lambda row: (
            row["prefit"]["win_rate"] >= 0.80 and row["prefit"]["max_dd"] > -0.20,
            row["prefit"]["annual_multiple"], row["prefit"]["win_rate"],
        ),
    )
    preempt_scale_grid: list[tuple[float, dict[str, Any]]] = []
    for scale in (0.5, 0.75, 1.0):
        scenario_metrics: dict[str, Any] = {}
        for scenario, items in scenario_items.items():
            trades = preemptive(
                items, start=portfolio_start, end=PREFIT_END,
                threshold=frozen_preempt["threshold"], margin=frozen_preempt["margin"],
                min_hold_hours=frozen_preempt["min_hold_hours"], bars=bars,
                funding=funding,
                slippage=0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE,
            )
            scenario_metrics[scenario] = strict_metrics(
                trades, portfolio_start, PREFIT_END, scale
            )
        preempt_scale_grid.append((scale, scenario_metrics))
    valid_preempt_scales = [
        row
        for row in preempt_scale_grid
        if all(metric["win_rate"] >= 0.80 for metric in row[1].values())
        and all(metric["max_dd"] > -0.20 for metric in row[1].values())
        and all(metric["total_return"] > 0.0 for metric in row[1].values())
    ]
    preempt_account_scale = max(
        valid_preempt_scales or preempt_scale_grid,
        key=lambda row: row[1]["base"]["annual_multiple"],
    )[0]

    comparisons: dict[str, Any] = {}
    output_trades: list[dict[str, Any]] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        comparisons[mode] = {"scenarios": {}}
        mode_scale = (
            account_scale if mode == "nonpreemptive" else preempt_account_scale
        )
        for scenario, items in scenario_items.items():
            if mode == "nonpreemptive":
                trades = nonpreemptive(items, start=portfolio_start, end=REUSED_END)
            else:
                trades = preemptive(
                    items, start=portfolio_start, end=REUSED_END,
                    threshold=frozen_preempt["threshold"], margin=frozen_preempt["margin"],
                    min_hold_hours=frozen_preempt["min_hold_hours"], bars=bars,
                    funding=funding,
                    slippage=0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE,
                )
            comparisons[mode]["scenarios"][scenario] = {
                "prefit": strict_metrics(trades, portfolio_start, PREFIT_END, mode_scale),
                "reused": strict_metrics(trades, PREFIT_END, REUSED_END, mode_scale),
                "all_six_active": strict_metrics(
                    trades, all_six_active_start, REUSED_END, mode_scale
                ),
                "through_reused": strict_metrics(trades, portfolio_start, REUSED_END, mode_scale),
            }
            if scenario == "base":
                output_trades.extend(
                    {"mode": mode, "scenario": scenario, **asdict(trade)} for trade in trades
                )
    comparisons["nonpreemptive"]["frozen_params"] = {"account_scale": account_scale}
    comparisons["strong_breakout_preemptive"]["frozen_params"] = {
        "account_scale": preempt_account_scale,
        "threshold": frozen_preempt["threshold"], "margin": frozen_preempt["margin"],
        "min_hold_hours": frozen_preempt["min_hold_hours"],
    }
    diagnostic_gates: dict[str, Any] = {}
    for mode, comparison in comparisons.items():
        base = comparison["scenarios"]["base"]
        full = base["through_reused"]
        reused = base["reused"]
        robustness = {
            scenario: comparison["scenarios"][scenario]["through_reused"]
            for scenario in ("stress_8bps", "k_plus_2")
        }
        checks = {
            "full_trades_ge_200": full["trades"] >= 200,
            "full_win_rate_ge_80pct": full["win_rate"] >= 0.80,
            "full_max_dd_lt_20pct": full["max_dd"] > -0.20,
            "full_return_positive": full["total_return"] > 0.0,
            "reused_trades_ge_30": reused["trades"] >= 30,
            "reused_win_rate_ge_80pct": reused["win_rate"] >= 0.80,
            "reused_max_dd_lt_20pct": reused["max_dd"] > -0.20,
            "reused_return_positive": reused["total_return"] > 0.0,
            "stress_full_positive_dd_lt_20pct": (
                robustness["stress_8bps"]["total_return"] > 0.0
                and robustness["stress_8bps"]["max_dd"] > -0.20
            ),
            "k_plus_2_full_positive_dd_lt_20pct": (
                robustness["k_plus_2"]["total_return"] > 0.0
                and robustness["k_plus_2"]["max_dd"] > -0.20
            ),
        }
        diagnostic_gates[mode] = {
            "checks": checks,
            "current_reused_diagnostic_pass": all(checks.values()),
            "final_future_oos_pass": None,
            "final_future_oos_reason": "future [2026-07-14T09:00Z, 2026-10-14T09:00Z) data unavailable",
        }
    pd.DataFrame(output_trades).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "stage": "hybrid_mechanism_account_diagnostic_before_future_oos_freeze",
        "portfolio_start": portfolio_start.isoformat(),
        "all_six_active_start": all_six_active_start.isoformat(),
        "portfolio_end": REUSED_END.isoformat(),
        "candidate_sleeves": list(candidates),
        "sleeve_audit": sleeve_audit,
        "route_selection": {
            "role": "reused eliminates sleeves; exposure and account routing selected on prefit only",
            "account_scale_grid": [
                {"scale": scale, "prefit_scenarios": metrics}
                for scale, metrics in scale_grid
            ],
            "preemptive_account_scale_grid": [
                {"scale": scale, "prefit_scenarios": metrics}
                for scale, metrics in preempt_scale_grid
            ],
            "frozen_preemption": frozen_preempt,
        },
        "diagnostic_gates": diagnostic_gates,
        "comparisons": comparisons,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT), "candidate_sleeves": len(candidates)}, indent=2))


if __name__ == "__main__":
    main()
