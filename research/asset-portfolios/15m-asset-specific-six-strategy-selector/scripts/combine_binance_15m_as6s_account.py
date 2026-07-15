from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
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
OUTPUT = FAMILY_DIR / "artifacts/binance_15m_as6s_account_comparison_2026-07-14.json"
PORTFOLIO_START = max(STARTS.values())


@dataclass(frozen=True, slots=True)
class AccountTrade:
    symbol: str
    mechanism: str
    config_id: str
    side: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    score: float
    net_return_1x: float
    mae_return_1x: float
    exit_reason: str


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_candidates(items: Iterable[Any], min_score: float) -> list[tuple[pd.Timestamp, list[Any]]]:
    eligible = sorted(
        (item for item in items if item.score >= min_score),
        key=lambda item: (item.entry_ts, -item.score, item.symbol, item.mechanism),
    )
    return [
        (timestamp, list(group))
        for timestamp, group in itertools.groupby(eligible, key=lambda item: item.entry_ts)
    ]


def natural_trade(item: Any) -> AccountTrade:
    return AccountTrade(
        symbol=item.symbol,
        mechanism=item.mechanism,
        config_id=item.config_id,
        side=item.side,
        entry_ts=item.entry_ts,
        exit_ts=item.exit_ts,
        score=item.score,
        net_return_1x=item.net_return_1x,
        mae_return_1x=item.mae_return_1x,
        exit_reason=item.exit_reason,
    )


def simulate_nonpreemptive(items: list[Any], *, min_score: float, end: pd.Timestamp) -> list[AccountTrade]:
    trades: list[AccountTrade] = []
    blocked_until = PORTFOLIO_START
    for timestamp, candidates in group_candidates(items, min_score):
        if timestamp < PORTFOLIO_START or timestamp >= end or timestamp < blocked_until:
            continue
        candidates = [item for item in candidates if item.exit_ts < end]
        if not candidates:
            continue
        chosen = max(candidates, key=lambda item: (item.score, -item.exit_ts.value))
        trades.append(natural_trade(chosen))
        blocked_until = chosen.exit_ts
    return trades


def truncated_trade(
    item: Any,
    exit_ts: pd.Timestamp,
    *,
    frame_lookup: dict[str, pd.Series],
    funding_lookup: dict[str, tuple[np.ndarray, np.ndarray]],
    slippage: float,
) -> AccountTrade:
    base = float(frame_lookup[item.symbol].loc[exit_ts])
    exit_fill = adverse_fill(base, item.side, entry=False, slippage=slippage)
    price_return = item.side * (exit_fill / item.entry_fill - 1.0)
    times, prefix = funding_lookup[item.symbol]
    funding_ret = funding_return(item.side, item.entry_ts, exit_ts, times, prefix)
    return AccountTrade(
        symbol=item.symbol,
        mechanism=item.mechanism,
        config_id=item.config_id,
        side=item.side,
        entry_ts=item.entry_ts,
        exit_ts=exit_ts,
        score=item.score,
        net_return_1x=float(price_return + funding_ret - 2.0 * FEE_PER_FILL),
        mae_return_1x=min(
            item.mae_return_1x,
            float(price_return - 2.0 * FEE_PER_FILL),
        ),
        exit_reason="preempted_by_other_symbol_breakout",
    )


def simulate_preemptive(
    items: list[Any],
    *,
    min_score: float,
    preempt_score: float,
    preempt_margin: float,
    min_hold_bars: int,
    end: pd.Timestamp,
    frame_lookup: dict[str, pd.Series],
    funding_lookup: dict[str, tuple[np.ndarray, np.ndarray]],
    slippage: float,
) -> list[AccountTrade]:
    trades: list[AccountTrade] = []
    current: Any | None = None
    minimum_hold = pd.Timedelta(minutes=15 * min_hold_bars)
    for timestamp, candidates in group_candidates(items, min_score):
        if timestamp < PORTFOLIO_START or timestamp >= end:
            continue
        candidates = [item for item in candidates if item.exit_ts < end]
        if not candidates:
            continue
        if current is not None and current.exit_ts <= timestamp:
            trades.append(natural_trade(current))
            current = None
        if current is None:
            current = max(candidates, key=lambda item: (item.score, -item.exit_ts.value))
            continue
        challenger_pool = [
            item
            for item in candidates
            if item.symbol != current.symbol
            and item.mechanism == "breakout"
            and item.score >= preempt_score
            and item.score >= current.score + preempt_margin
            and timestamp >= current.entry_ts + minimum_hold
        ]
        if not challenger_pool:
            continue
        challenger = max(
            challenger_pool, key=lambda item: (item.score, -item.exit_ts.value)
        )
        trades.append(
            truncated_trade(
                current,
                timestamp,
                frame_lookup=frame_lookup,
                funding_lookup=funding_lookup,
                slippage=slippage,
            )
        )
        current = challenger
    if current is not None and current.exit_ts < end:
        trades.append(natural_trade(current))
    return trades


def account_metrics(
    trades: Iterable[AccountTrade], *, start: pd.Timestamp, end: pd.Timestamp, exposure: float
) -> dict[str, Any]:
    chosen = sorted(
        (trade for trade in trades if start <= trade.entry_ts and trade.exit_ts < end),
        key=lambda trade: trade.exit_ts,
    )
    returns = [exposure * trade.net_return_1x for trade in chosen]
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for trade, value in zip(chosen, returns, strict=True):
        trough = equity * max(1e-9, 1.0 + exposure * trade.mae_return_1x)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(1e-9, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    positives = [value for value in returns if value > 0.0]
    negatives = [value for value in returns if value <= 0.0]
    years = max((end - start).total_seconds() / (365.25 * 86400.0), 1.0 / 365.25)
    by_sleeve: dict[str, int] = {}
    for trade in chosen:
        key = f"{trade.symbol}:{trade.mechanism}"
        by_sleeve[key] = by_sleeve.get(key, 0) + 1
    return {
        "trades": len(chosen),
        "wins": len(positives),
        "win_rate": len(positives) / len(chosen) if chosen else 0.0,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (1.0 / years) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": sum(positives) / abs(sum(negatives)) if negatives else 999.0,
        "preemptions": sum(
            trade.exit_reason == "preempted_by_other_symbol_breakout" for trade in chosen
        ),
        "long_trades": sum(trade.side > 0 for trade in chosen),
        "short_trades": sum(trade.side < 0 for trade in chosen),
        "by_sleeve": by_sleeve,
    }


def route_score(result: dict[str, Any]) -> tuple[bool, float, float, int]:
    hard_shape = (
        result["trades"] >= 40
        and result["win_rate"] >= 0.80
        and result["total_return"] > 0.0
        and result["max_dd"] > -0.20
    )
    return hard_shape, result["annual_multiple"], result["win_rate"], result["trades"]


def main() -> None:
    reveal = json.loads(REVEAL_PATH.read_text(encoding="utf-8"))
    if reveal.get("stage") != "reused_holdout_revealed_elimination_only":
        raise RuntimeError("unexpected reveal stage")
    configs = [
        StrategyConfig.from_dict(row["config"])
        for symbol_rows in reveal["results"].values()
        for row in symbol_rows.values()
        if row["diagnostic_classification"]
        in {"strong_survivor", "conditional_survivor"}
    ]
    if not configs:
        raise RuntimeError("no diagnostic survivors")

    frames = {cfg.symbol: load_symbol_frame(cfg.symbol, end=REUSED_END) for cfg in configs}
    funding = {cfg.symbol: load_funding(cfg.symbol, end=REUSED_END) for cfg in configs}
    frame_lookup = {
        symbol: frame.set_index("ts")["open"] for symbol, frame in frames.items()
    }
    funding_lookup = {
        symbol: funding_arrays(funding_frame)
        for symbol, funding_frame in funding.items()
    }

    scenario_items: dict[str, list[Any]] = {}
    for scenario, slippage, delay in (
        ("base", BASE_SLIPPAGE, 1),
        ("stress_8bps", 0.0008, 1),
        ("k_plus_2", BASE_SLIPPAGE, 2),
    ):
        scenario_items[scenario] = [
            item
            for cfg in configs
            for item in simulate_opportunities(
                frames[cfg.symbol],
                funding[cfg.symbol],
                cfg,
                end=REUSED_END,
                slippage=slippage,
                entry_delay_bars=delay,
            )
        ]

    route_grid: list[dict[str, Any]] = []
    for exposure in (1.0, 1.5, 2.0, 2.5, 3.0):
        for min_score in (0.0, 0.35, 0.45, 0.55, 0.65, 0.75):
            nonpreemptive = simulate_nonpreemptive(
                scenario_items["base"], min_score=min_score, end=PREFIT_END
            )
            route_grid.append(
                {
                    "mode": "nonpreemptive",
                    "params": {"exposure": exposure, "min_score": min_score},
                    "prefit": account_metrics(
                        nonpreemptive,
                        start=PORTFOLIO_START,
                        end=PREFIT_END,
                        exposure=exposure,
                    ),
                }
            )
            for preempt_score, margin, hold in itertools.product(
                (0.70, 0.80, 0.90), (0.05, 0.10, 0.20), (4, 8, 16)
            ):
                preemptive = simulate_preemptive(
                    scenario_items["base"],
                    min_score=min_score,
                    preempt_score=preempt_score,
                    preempt_margin=margin,
                    min_hold_bars=hold,
                    end=PREFIT_END,
                    frame_lookup=frame_lookup,
                    funding_lookup=funding_lookup,
                    slippage=BASE_SLIPPAGE,
                )
                route_grid.append(
                    {
                        "mode": "strong_breakout_preemptive",
                        "params": {
                            "exposure": exposure,
                            "min_score": min_score,
                            "preempt_score": preempt_score,
                            "preempt_margin": margin,
                            "min_hold_bars": hold,
                        },
                        "prefit": account_metrics(
                            preemptive,
                            start=PORTFOLIO_START,
                            end=PREFIT_END,
                            exposure=exposure,
                        ),
                    }
                )

    frozen_routes: dict[str, dict[str, Any]] = {}
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        candidates = [row for row in route_grid if row["mode"] == mode]
        frozen_routes[mode] = max(candidates, key=lambda row: route_score(row["prefit"]))

    comparisons: dict[str, Any] = {}
    for mode, route in frozen_routes.items():
        params = route["params"]
        scenario_results: dict[str, Any] = {}
        for scenario, items in scenario_items.items():
            if mode == "nonpreemptive":
                trades = simulate_nonpreemptive(
                    items, min_score=params["min_score"], end=REUSED_END
                )
            else:
                trades = simulate_preemptive(
                    items,
                    min_score=params["min_score"],
                    preempt_score=params["preempt_score"],
                    preempt_margin=params["preempt_margin"],
                    min_hold_bars=params["min_hold_bars"],
                    end=REUSED_END,
                    frame_lookup=frame_lookup,
                    funding_lookup=funding_lookup,
                    slippage=0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE,
                )
            scenario_results[scenario] = {
                "prefit": account_metrics(
                    trades,
                    start=PORTFOLIO_START,
                    end=PREFIT_END,
                    exposure=params["exposure"],
                ),
                "reused": account_metrics(
                    trades,
                    start=PREFIT_END,
                    end=REUSED_END,
                    exposure=params["exposure"],
                ),
                "through_reused": account_metrics(
                    trades,
                    start=PORTFOLIO_START,
                    end=REUSED_END,
                    exposure=params["exposure"],
                ),
            }
        comparisons[mode] = {
            "frozen_params": params,
            "prefit_selection_metrics": route["prefit"],
            "scenarios": scenario_results,
            "trades_base": [asdict(trade) for trade in (
                simulate_nonpreemptive(
                    scenario_items["base"], min_score=params["min_score"], end=REUSED_END
                )
                if mode == "nonpreemptive"
                else simulate_preemptive(
                    scenario_items["base"],
                    min_score=params["min_score"],
                    preempt_score=params["preempt_score"],
                    preempt_margin=params["preempt_margin"],
                    min_hold_bars=params["min_hold_bars"],
                    end=REUSED_END,
                    frame_lookup=frame_lookup,
                    funding_lookup=funding_lookup,
                    slippage=BASE_SLIPPAGE,
                )
            )],
        }

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "stage": "account_baseline_after_reused_elimination_not_frozen_for_future_oos",
        "reveal_artifact": str(REVEAL_PATH.relative_to(ROOT)),
        "reveal_sha256": sha256(REVEAL_PATH),
        "portfolio_start": PORTFOLIO_START.isoformat(),
        "candidate_sleeves": [cfg.to_dict() for cfg in configs],
        "route_selection_role": "survivor universe from reused elimination; all route parameters selected on prefit only",
        "route_grid_size": len(route_grid),
        "comparisons": comparisons,
    }
    OUTPUT.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT), "sha256": sha256(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
