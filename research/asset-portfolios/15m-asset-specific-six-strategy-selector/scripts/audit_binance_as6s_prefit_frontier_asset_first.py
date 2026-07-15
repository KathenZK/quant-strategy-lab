from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import (
    BASE_SLIPPAGE,
    MECHANISMS,
    REUSED_END,
    STARTS,
    SYMBOLS,
    StrategyConfig,
    load_funding,
    load_symbol_frame,
    metrics,
    prefit_windows,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = FAMILY_DIR / "artifacts/binance_15m_as6s_prefit_search_2026-07-14.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_prefit_frontier_asset_first_2026-07-14.json"
CURRENT_3M_START = pd.Timestamp("2026-04-14T09:00:00Z")


def finite_pf(value: float) -> float:
    return min(float(value), 20.0)


def score(row: dict[str, Any]) -> float:
    base = row["scenarios"]["base"]
    stress = row["scenarios"]["stress_8bps"]
    delayed = row["scenarios"]["k_plus_2"]
    evidence = [
        scenario[window]
        for scenario in (base, stress, delayed)
        for window in ("validation_1", "validation_2", "current_3m")
    ]
    if min(metric["trades"] for metric in evidence) < 3:
        return -1e9
    min_win = min(metric["win_rate"] for metric in evidence)
    worst_dd = min(
        scenario["through_current"]["max_dd"]
        for scenario in (base, stress, delayed)
    )
    min_pf = min(
        finite_pf(scenario["through_current"]["profit_factor"])
        for scenario in (base, stress, delayed)
    )
    positive_windows = sum(metric["total_return"] > 0.0 for metric in evidence)
    return float(
        1.2 * math.log(max(base["prefit"]["annual_multiple"], 1e-9))
        + 1.0 * math.log(max(base["current_3m"]["annual_multiple"], 1e-9))
        + 0.6 * math.log(max(stress["through_current"]["annual_multiple"], 1e-9))
        + 4.0 * min_win
        + 0.7 * math.log(max(min_pf, 1e-9))
        + 2.0 * worst_dd
        + 0.5 * positive_windows
        + 12.0 * min(0.0, min_win - 0.65)
        + 14.0 * min(0.0, worst_dd + 0.20)
    )


def window_metrics(opportunities: list[Any], symbol: str) -> dict[str, Any]:
    windows = prefit_windows(symbol)
    return {
        **{
            name: metrics(opportunities, start=start, end=end)
            for name, (start, end) in windows.items()
        },
        "current_3m": metrics(
            opportunities, start=CURRENT_3M_START, end=REUSED_END
        ),
        "through_current": metrics(
            opportunities, start=STARTS[symbol], end=REUSED_END
        ),
    }


def is_portfolio_eligible(row: dict[str, Any]) -> bool:
    scenarios = row["scenarios"]
    return all(
        scenario["through_current"]["total_return"] > 0.0
        and scenario["through_current"]["max_dd"] > -0.20
        and scenario["prefit"]["total_return"] > 0.0
        and scenario["current_3m"]["total_return"] > 0.0
        and scenario["current_3m"]["trades"] >= 3
        for scenario in scenarios.values()
    )


def is_hard80(row: dict[str, Any]) -> bool:
    return is_portfolio_eligible(row) and all(
        scenario[window]["win_rate"] >= 0.80
        for scenario in row["scenarios"].values()
        for window in ("prefit", "current_3m", "through_current")
    )


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "asset_first_frontier_audit_not_live_ready",
        "source": str(SOURCE.relative_to(ROOT)),
        "selection_disclosure": (
            "Configs were generated and selected before 2026-04-14; current 3m is "
            "used here for elimination and diagnostics. Future final OOS remains locked."
        ),
        "symbols": {},
    }
    for symbol in SYMBOLS:
        frame = load_symbol_frame(symbol, end=REUSED_END)
        funding = load_funding(symbol, end=REUSED_END)
        rows: list[dict[str, Any]] = []
        for mechanism in MECHANISMS:
            candidates = source["cells"][symbol][mechanism]["top"]
            for source_rank, candidate in enumerate(candidates, start=1):
                config = StrategyConfig.from_dict(candidate["config"])
                scenarios: dict[str, Any] = {}
                for name, slippage, delay in (
                    ("base", BASE_SLIPPAGE, 1),
                    ("stress_8bps", 0.0008, 1),
                    ("k_plus_2", BASE_SLIPPAGE, 2),
                ):
                    opportunities = simulate_opportunities(
                        frame,
                        funding,
                        config,
                        end=REUSED_END,
                        slippage=slippage,
                        entry_delay_bars=delay,
                    )
                    scenarios[name] = window_metrics(opportunities, symbol)
                row = {
                    "mechanism": mechanism,
                    "source_rank": source_rank,
                    "source_score": candidate["score"],
                    "config": config.to_dict(),
                    "scenarios": scenarios,
                }
                row["score"] = score(row)
                row["portfolio_eligible"] = is_portfolio_eligible(row)
                row["hard80"] = is_hard80(row)
                rows.append(row)
        rows.sort(key=lambda value: value["score"], reverse=True)
        eligible = [row for row in rows if row["portfolio_eligible"]]
        hard80 = [row for row in rows if row["hard80"]]
        payload["symbols"][symbol] = {
            "audited": len(rows),
            "portfolio_eligible": len(eligible),
            "hard80": len(hard80),
            "ranking": rows,
            "eligible_ranking": eligible,
            "hard80_ranking": hard80,
        }
        print(
            f"{symbol}: audited={len(rows)} eligible={len(eligible)} hard80={len(hard80)}",
            flush=True,
        )
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
