from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ml6as_engine import (
    BASE_SLIPPAGE,
    FULL_END,
    OOS_START,
    RESEARCH_START,
    SYMBOLS,
    RouteConfig,
    StrategyConfig,
    load_funding,
    load_symbol_frame,
    portfolio_metrics,
    replay_portfolio,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-multi-leg-six-asset-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PREFIT_PATH = ARTIFACT_DIR / "binance_1h_ml6as_prefit_search_2026-07-14.json"


def selected_row(
    payload: dict[str, Any], cfg: StrategyConfig
) -> dict[str, Any]:
    rows = payload["cell_search_results"][cfg.symbol][cfg.arm]
    matches = [row for row in rows if row["config"]["config_id"] == cfg.config_id]
    if len(matches) != 1:
        raise RuntimeError(f"cannot resolve frozen cell result for {cfg.config_id}")
    return matches[0]


def quality_weight(row: dict[str, Any]) -> float:
    prefit = row["prefit"]
    validation = row["validation"]
    profitable = (
        prefit["total_return"] > 0.0
        and validation["total_return"] > 0.0
        and prefit["profit_factor"] > 1.0
    )
    if not profitable:
        return 0.25
    return min(
        1.0,
        0.30
        + 0.35 * prefit["win_rate"]
        + 0.20 * validation["win_rate"]
        + 0.15 * min(prefit["profit_factor"] / 2.0, 1.0),
    )


def build_opportunities(
    payload: dict[str, Any],
    *,
    frames: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
    slippage: float,
) -> tuple[list[Any], dict[str, float]]:
    opportunities: list[Any] = []
    weights: dict[str, float] = {}
    for config_payload in payload["selected_configs"]:
        cfg = StrategyConfig.from_dict(config_payload)
        weight = quality_weight(selected_row(payload, cfg))
        weights[cfg.config_id] = weight
        raw = simulate_opportunities(
            frames[cfg.symbol],
            fundings[cfg.symbol],
            cfg,
            end=FULL_END,
            slippage=slippage,
        )
        opportunities.extend(
            replace(
                opportunity,
                score=min(1.0, 0.65 * opportunity.score + 0.35 * weight),
            )
            for opportunity in raw
        )
    return opportunities, weights


def hard_gate(full: dict[str, float], oos: dict[str, float]) -> dict[str, bool]:
    checks = {
        "full_trades_ge_200": full["trades"] >= 200,
        "oos_trades_ge_30": oos["trades"] >= 30,
        "full_win_rate_ge_80pct": full["win_rate"] >= 0.80,
        "oos_win_rate_ge_80pct": oos["win_rate"] >= 0.80,
        "full_max_dd_lt_20pct": full["max_dd"] > -0.20,
        "oos_max_dd_lt_20pct": oos["max_dd"] > -0.20,
        "full_total_return_positive": full["total_return"] > 0.0,
        "oos_total_return_positive": oos["total_return"] > 0.0,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def recent_slices(trades: list[Any]) -> dict[str, dict[str, float]]:
    starts = {
        "last_1d": FULL_END - pd.Timedelta(days=1),
        "last_7d": FULL_END - pd.Timedelta(days=7),
        "last_1m": FULL_END - pd.DateOffset(months=1),
        "last_3m": FULL_END - pd.DateOffset(months=3),
        "last_6m": FULL_END - pd.DateOffset(months=6),
        "last_1y": FULL_END - pd.DateOffset(years=1),
    }
    return {
        name: portfolio_metrics(trades, start=max(start, RESEARCH_START), end=FULL_END)
        for name, start in starts.items()
    }


def contribution(trades: list[Any]) -> dict[str, Any]:
    by_symbol: dict[str, list[float]] = defaultdict(list)
    by_arm: dict[str, list[float]] = defaultdict(list)
    exits: Counter[str] = Counter()
    for trade in trades:
        by_symbol[trade.symbol].append(trade.net_return)
        by_arm[trade.arm].append(trade.net_return)
        exits[trade.exit_reason] += 1

    def summarize(groups: dict[str, list[float]]) -> dict[str, Any]:
        return {
            key: {
                "trades": len(values),
                "wins": sum(value > 0.0 for value in values),
                "win_rate": sum(value > 0.0 for value in values) / len(values),
                "arithmetic_return_sum": sum(values),
                "avg_return": sum(values) / len(values),
                "worst_trade": min(values),
            }
            for key, values in sorted(groups.items())
        }

    return {
        "by_symbol": summarize(by_symbol),
        "by_arm": summarize(by_arm),
        "exit_reasons": dict(sorted(exits.items())),
    }


def trade_rows(variant: str, scope: str, trades: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "variant": variant,
            "scope": scope,
            "symbol": trade.symbol,
            "arm": trade.arm,
            "config_id": trade.config_id,
            "side": trade.side,
            "entry_ts": trade.entry_ts.isoformat(),
            "exit_ts": trade.exit_ts.isoformat(),
            "route_score": trade.route_score,
            "exposure": trade.exposure,
            "net_return": trade.net_return,
            "exit_reason": trade.exit_reason,
            "preempted": trade.preempted,
        }
        for trade in trades
    ]


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Reveal the frozen BIN-1H-ML6AS routes on the locked OOS window "
            "and write the immutable audit artifacts."
        )
    ).parse_args()
    prefit_bytes = PREFIT_PATH.read_bytes()
    prefit_sha256 = hashlib.sha256(prefit_bytes).hexdigest()
    payload = json.loads(prefit_bytes)
    if payload.get("stage") != "prefit_only_oos_unread":
        raise RuntimeError("prefit artifact does not carry the OOS-unread freeze marker")
    if payload["windows"]["oos_start_locked"] != OOS_START.isoformat():
        raise RuntimeError("prefit OOS boundary drift")
    frames = {symbol: load_symbol_frame(symbol, end=FULL_END) for symbol in SYMBOLS}
    fundings = {symbol: load_funding(symbol, end=FULL_END) for symbol in SYMBOLS}
    base_opportunities, weights = build_opportunities(
        payload,
        frames=frames,
        fundings=fundings,
        slippage=BASE_SLIPPAGE,
    )
    stress_opportunities, _ = build_opportunities(
        payload,
        frames=frames,
        fundings=fundings,
        slippage=0.0008,
    )
    variants: dict[str, Any] = {}
    exported_trades: list[dict[str, Any]] = []
    for name, frozen in payload["portfolio_variants"].items():
        route_cfg = RouteConfig.from_dict(frozen["route_config"])
        full_trades = replay_portfolio(
            base_opportunities,
            route_cfg,
            frames=frames,
            fundings=fundings,
            start=RESEARCH_START,
            end=FULL_END,
        )
        oos_flat_trades = replay_portfolio(
            base_opportunities,
            route_cfg,
            frames=frames,
            fundings=fundings,
            start=OOS_START,
            end=FULL_END,
        )
        stress_trades = replay_portfolio(
            stress_opportunities,
            route_cfg,
            frames=frames,
            fundings=fundings,
            start=RESEARCH_START,
            end=FULL_END,
            slippage=0.0008,
        )
        stress_oos_flat = replay_portfolio(
            stress_opportunities,
            route_cfg,
            frames=frames,
            fundings=fundings,
            start=OOS_START,
            end=FULL_END,
            slippage=0.0008,
        )
        full = portfolio_metrics(full_trades, start=RESEARCH_START, end=FULL_END)
        oos_continuation = portfolio_metrics(
            full_trades, start=OOS_START, end=FULL_END
        )
        oos_flat = portfolio_metrics(
            oos_flat_trades, start=OOS_START, end=FULL_END
        )
        stress_full = portfolio_metrics(
            stress_trades, start=RESEARCH_START, end=FULL_END
        )
        stress_oos = portfolio_metrics(
            stress_oos_flat, start=OOS_START, end=FULL_END
        )
        variants[name] = {
            "route_config": route_cfg.to_dict(),
            "prefit_frozen": frozen,
            "full": full,
            "oos_continuation": oos_continuation,
            "oos_flat_start": oos_flat,
            "hard_gate": hard_gate(full, oos_flat),
            "stress_8bps_per_fill": {
                "full": stress_full,
                "oos_flat_start": stress_oos,
                "hard_gate": hard_gate(stress_full, stress_oos),
            },
            "recent_slices": recent_slices(full_trades),
            "contribution_full": contribution(full_trades),
            "contribution_oos_flat_start": contribution(oos_flat_trades),
        }
        exported_trades.extend(trade_rows(name, "full", full_trades))
        exported_trades.extend(trade_rows(name, "oos_flat_start", oos_flat_trades))
        print(
            f"{name}: full={full} oos_flat={oos_flat} "
            f"pass={variants[name]['hard_gate']['all_pass']}",
            flush=True,
        )
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-1H-Multi-Leg-Six-Asset-Selector",
        "prefit_artifact": str(PREFIT_PATH.relative_to(ROOT)),
        "prefit_sha256_before_reveal": prefit_sha256,
        "windows": {
            "full_start": RESEARCH_START.isoformat(),
            "oos_start_locked": OOS_START.isoformat(),
            "end_exclusive": FULL_END.isoformat(),
        },
        "hard_gate_contract": {
            "full_trades_min": 200,
            "oos_trades_min": 30,
            "full_and_oos_win_rate_min": 0.80,
            "full_and_oos_max_dd_strictly_above": -0.20,
            "full_and_oos_return_positive": True,
        },
        "quality_weights_prefit_only": weights,
        "variants": variants,
    }
    output = ARTIFACT_DIR / "binance_1h_ml6as_oos_reveal_2026-07-14.json"
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    trades_path = ARTIFACT_DIR / "binance_1h_ml6as_revealed_trades_2026-07-14.csv"
    pd.DataFrame(exported_trades).to_csv(trades_path, index=False)
    print(f"wrote {output}", flush=True)
    print(f"wrote {trades_path}", flush=True)


if __name__ == "__main__":
    main()
