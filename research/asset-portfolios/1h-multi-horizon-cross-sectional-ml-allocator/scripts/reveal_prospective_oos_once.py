from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
SCRIPT_DIR = FAMILY_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import search_development_allocator as allocator  # noqa: E402
from frozen_r4_inference import sha256  # noqa: E402


OOS_START = pd.Timestamp("2026-07-19T00:00:00Z")
OOS_END = pd.Timestamp("2026-10-19T00:00:00Z")
REVEAL_NOT_BEFORE = pd.Timestamp("2026-10-20T21:05:00Z")
ROUND_TRIP_COST = 0.0028
STRESS_EXTRA_COST = 0.0014
EXPECTED_DECISIONS = 552
FREEZE_DIR = FAMILY_DIR / "artifacts/freeze"
MASTER_FREEZE = FREEZE_DIR / "bin-1h-mhcsml-v1-freeze-r4.json"
BLIND_DIR = FAMILY_DIR / "artifacts/prospective_oos/blind"
CHAIN_DIR = BLIND_DIR / "chain"
REVEAL_DIR = FAMILY_DIR / "artifacts/prospective_oos/reveal"
RECEIPT = REVEAL_DIR / "reveal_started.json"
REPORT = REVEAL_DIR / "one_time_oos_report.json"
LEGS_OUTPUT = REVEAL_DIR / "revealed_legs.parquet"
DECISIONS_OUTPUT = REVEAL_DIR / "revealed_decisions.parquet"
OHLCV_GLOB = ROOT / (
    "data/normalized/ohlcv/exchange=binance/market_type=perp/"
    "timeframe=1h/**/*.parquet"
)
FUNDING_GLOB = ROOT / (
    "data/normalized/funding_rates/exchange=binance/market_type=perp/**/*.parquet"
)
BASELINES = ("ridge_compact", "rule_carry_momentum")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reveal the frozen R4 prospective OOS exactly once after maturity."
    )
    parser.add_argument("--now", help="UTC override, only with --validate-only")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def assert_reveal_time(now: pd.Timestamp) -> None:
    if now < REVEAL_NOT_BEFORE:
        raise RuntimeError(
            "prospective OOS outcomes remain sealed until "
            f"{REVEAL_NOT_BEFORE.isoformat()}"
        )


def atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def verify_and_load_chain(master_sha: str) -> list[dict[str, Any]]:
    paths = sorted(CHAIN_DIR.glob("*.json"))
    if len(paths) != EXPECTED_DECISIONS:
        raise RuntimeError(
            f"blind chain is incomplete: {len(paths)} != {EXPECTED_DECISIONS}"
        )
    previous = "0" * 64
    nodes: list[dict[str, Any]] = []
    expected = list(pd.date_range(OOS_START, OOS_END - pd.Timedelta(hours=4), freq="4h"))
    for path, expected_ts in zip(paths, expected, strict=True):
        node = json.loads(path.read_text(encoding="utf-8"))
        if node["previous_node_sha256"] != previous:
            raise RuntimeError(f"blind chain mismatch: {path}")
        if node["master_freeze_sha256"] != master_sha:
            raise RuntimeError(f"master freeze mismatch: {path}")
        if pd.Timestamp(node["decision_ts"]) != expected_ts:
            raise RuntimeError(f"blind decision sequence mismatch: {path}")
        if node["status"] not in {"FROZEN_ON_TIME", "MISSED"}:
            raise RuntimeError(f"unexpected blind node status: {path}")
        previous = sha256(path)
        nodes.append(node)
    return nodes


def verified_parquet(spec: dict[str, Any]) -> pd.DataFrame:
    path = ROOT / spec["path"]
    if sha256(path) != spec["sha256"]:
        raise RuntimeError(f"blind snapshot SHA mismatch: {path}")
    frame = pd.read_parquet(path)
    for column in ("ts", "entry_time", "planned_exit_time"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def load_blind_signals(nodes: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    decision_rows: list[pd.DataFrame] = []
    leg_rows: list[pd.DataFrame] = []
    for node in nodes:
        ts = pd.Timestamp(node["decision_ts"])
        if node["status"] == "MISSED":
            for strategy in ("r4", *BASELINES):
                decision_rows.append(
                    pd.DataFrame(
                        [{
                            "ts": ts,
                            "strategy": strategy,
                            "active": False,
                            "position_count": 0,
                            "collection_status": "MISSED",
                        }]
                    )
                )
            continue
        outputs = node["outputs"]
        decision = verified_parquet(outputs["decision"])
        decision["strategy"] = "r4"
        decision["collection_status"] = "FROZEN_ON_TIME"
        decision_rows.append(decision)
        legs = verified_parquet(outputs["selected_legs"])
        legs["strategy"] = "r4"
        leg_rows.append(legs)
        baseline_decisions = verified_parquet(outputs["baseline_decisions"])
        baseline_decisions = baseline_decisions.rename(columns={"baseline": "strategy"})
        baseline_decisions["collection_status"] = "FROZEN_ON_TIME"
        decision_rows.append(baseline_decisions)
        baseline_legs = verified_parquet(outputs["baseline_selected_legs"])
        baseline_legs = baseline_legs.rename(columns={"baseline": "strategy"})
        leg_rows.append(baseline_legs)
    decisions = pd.concat(decision_rows, ignore_index=True)
    legs = pd.concat(leg_rows, ignore_index=True) if leg_rows else pd.DataFrame()
    if decisions.duplicated(["ts", "strategy"]).any():
        raise RuntimeError("duplicate revealed decision keys")
    expected_rows = EXPECTED_DECISIONS * (1 + len(BASELINES))
    if len(decisions) != expected_rows:
        raise RuntimeError(f"revealed decision count mismatch: {len(decisions)}")
    return decisions, legs


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def load_market_prices(legs: pd.DataFrame) -> pd.DataFrame:
    requests = pd.concat(
        [
            legs[["symbol", "entry_time"]].rename(columns={"entry_time": "price_ts"}),
            legs[["symbol", "planned_exit_time"]].rename(
                columns={"planned_exit_time": "price_ts"}
            ),
        ],
        ignore_index=True,
    ).drop_duplicates()
    connection = duckdb.connect()
    connection.register("requested_prices", requests)
    prices = connection.execute(
        f"""
        WITH market AS (
            SELECT * EXCLUDE (_rn) FROM (
                SELECT ts, symbol, open,
                    row_number() OVER (
                        PARTITION BY ts, symbol
                        ORDER BY CASE
                            WHEN source LIKE '%prospective_oos%' THEN 0
                            WHEN source LIKE '%freeze_gap%' THEN 1
                            ELSE 2
                        END
                    ) AS _rn
                FROM read_parquet(
                    '{sql_path(OHLCV_GLOB)}',
                    hive_partitioning=false, union_by_name=true
                )
                WHERE ts >= TIMESTAMPTZ '{OOS_START.isoformat()}'
                  AND ts <= TIMESTAMPTZ '2026-10-20T21:00:00Z'
            ) WHERE _rn = 1
        )
        SELECT r.symbol, r.price_ts, m.open
        FROM requested_prices AS r
        LEFT JOIN market AS m
          ON r.symbol = m.symbol AND r.price_ts = m.ts
        """
    ).fetch_df()
    connection.close()
    prices["price_ts"] = pd.to_datetime(prices["price_ts"], utc=True)
    if prices["open"].isna().any():
        missing = prices.loc[prices["open"].isna(), ["symbol", "price_ts"]]
        raise RuntimeError(f"missing reveal prices: {missing.head(20).to_dict('records')}")
    return prices


def load_funding_events(symbols: list[str]) -> pd.DataFrame:
    connection = duckdb.connect()
    connection.register("requested_symbols", pd.DataFrame({"symbol": symbols}))
    funding = connection.execute(
        f"""
        SELECT * EXCLUDE (_rn) FROM (
            SELECT f.ts, f.symbol, f.funding_rate,
                row_number() OVER (
                    PARTITION BY f.ts, f.symbol
                    ORDER BY CASE
                        WHEN f.source LIKE '%prospective_oos%' THEN 0
                        WHEN f.source LIKE '%freeze_gap%' THEN 1
                        ELSE 2
                    END
                ) AS _rn
            FROM read_parquet(
                '{sql_path(FUNDING_GLOB)}',
                hive_partitioning=false, union_by_name=true
            ) AS f
            INNER JOIN requested_symbols AS r USING (symbol)
            WHERE f.ts > TIMESTAMPTZ '{OOS_START.isoformat()}'
              AND f.ts <= TIMESTAMPTZ '2026-10-20T21:00:00Z'
        ) WHERE _rn = 1
        ORDER BY symbol, ts
        """
    ).fetch_df()
    connection.close()
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    return funding


def reveal_leg_returns(legs: pd.DataFrame) -> pd.DataFrame:
    prices = load_market_prices(legs)
    entry = prices.rename(columns={"price_ts": "entry_time", "open": "entry_open"})
    exit_prices = prices.rename(
        columns={"price_ts": "planned_exit_time", "open": "exit_open"}
    )
    result = legs.merge(entry, on=["symbol", "entry_time"], validate="many_to_one")
    result = result.merge(
        exit_prices, on=["symbol", "planned_exit_time"], validate="many_to_one"
    )
    funding = load_funding_events(sorted(result["symbol"].unique()))
    by_symbol = {symbol: group for symbol, group in funding.groupby("symbol")}
    funding_sums: list[float] = []
    funding_counts: list[int] = []
    for row in result.itertuples(index=False):
        events = by_symbol.get(row.symbol)
        if events is None:
            funding_sums.append(0.0)
            funding_counts.append(0)
            continue
        mask = events["ts"].gt(row.entry_time) & events["ts"].le(
            row.planned_exit_time
        )
        funding_sums.append(float(events.loc[mask, "funding_rate"].sum()))
        funding_counts.append(int(mask.sum()))
    result["funding_sum"] = funding_sums
    result["funding_event_count"] = funding_counts
    if result["funding_event_count"].eq(0).any():
        missing = result.loc[
            result["funding_event_count"].eq(0),
            ["symbol", "entry_time", "planned_exit_time"],
        ]
        raise RuntimeError(
            f"funding coverage missing for revealed legs: {missing.head(20).to_dict('records')}"
        )
    gross = result["exit_open"] / result["entry_open"] - 1.0
    result["trade_return"] = -gross - ROUND_TRIP_COST + result["funding_sum"]
    result["stress_trade_return"] = result["trade_return"] - STRESS_EXTRA_COST
    return result


def fixed_month_cohort_returns(decisions: pd.DataFrame) -> list[float]:
    boundaries = [
        OOS_START,
        pd.Timestamp("2026-08-19T00:00:00Z"),
        pd.Timestamp("2026-09-19T00:00:00Z"),
        OOS_END,
    ]
    returns: list[float] = []
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
        values = decisions.loc[
            decisions["ts"].ge(start) & decisions["ts"].lt(end),
            "portfolio_return",
        ]
        returns.append(float((values * 0.03125).sum()))
    return returns


def evaluate_strategy(
    strategy: str, decisions: pd.DataFrame, legs: pd.DataFrame
) -> tuple[dict[str, Any], pd.DataFrame]:
    strategy_decisions = decisions.loc[decisions["strategy"].eq(strategy)].copy()
    strategy_legs = legs.loc[legs["strategy"].eq(strategy)].copy()
    returns = strategy_legs.groupby("ts").agg(
        portfolio_return=("trade_return", "mean"),
        portfolio_stress_return=("stress_trade_return", "mean"),
    )
    strategy_decisions = strategy_decisions.drop(
        columns=["portfolio_return", "portfolio_stress_return"], errors="ignore"
    ).merge(returns, on="ts", how="left", validate="one_to_one")
    strategy_decisions["portfolio_return"] = strategy_decisions[
        "portfolio_return"
    ].fillna(0.0)
    strategy_decisions["portfolio_stress_return"] = strategy_decisions[
        "portfolio_stress_return"
    ].fillna(0.0)
    strategy_decisions["fold_id"] = "prospective_oos"
    strategy_decisions["active"] = strategy_decisions["position_count"].gt(0)
    strategy_legs["fold_id"] = "prospective_oos"
    metrics = allocator.evaluate_policy(
        strategy_decisions,
        strategy_legs,
        horizon=48,
        decision_frequency=4,
        gross_exposure=0.375,
    )
    cohort_returns = fixed_month_cohort_returns(strategy_decisions)
    metrics["fixed_month_cohort_returns"] = cohort_returns
    metrics["positive_fixed_month_cohorts"] = int(
        sum(value > 0.0 for value in cohort_returns)
    )
    metrics["missed_decisions"] = int(
        strategy_decisions["collection_status"].eq("MISSED").sum()
    )
    return metrics, strategy_decisions


def hard_gates(
    r4: dict[str, Any], baseline_metrics: dict[str, dict[str, Any]]
) -> dict[str, bool]:
    return {
        "three_month_return_gte_18_92pct": r4["total_return"] >= 0.1892,
        "annualized_return_gte_100pct": r4["annualized_return"] >= 1.0,
        "max_drawdown_lte_20pct": r4["max_drawdown"] >= -0.20,
        "decision_win_rate_gte_55pct": r4["win_rate"] >= 0.55,
        "sharpe_gte_1_5": r4["sharpe"] >= 1.50,
        "profit_factor_gte_1_30": r4["profit_factor"] >= 1.30,
        "active_decisions_gte_45": r4["decision_count"] >= 45,
        "completed_legs_gte_300": r4["trade_count"] >= 300,
        "positive_month_cohorts_gte_2": r4["positive_fixed_month_cohorts"] >= 2,
        "stress_return_positive": r4["stress_total_return"] > 0.0,
        "stress_drawdown_lte_25pct": r4["stress_max_drawdown"] >= -0.25,
        "symbol_concentration_lte_25pct": (
            r4["symbol_positive_profit_concentration"] <= 0.25
        ),
        "month_concentration_lte_35pct": (
            r4["month_positive_profit_concentration"] <= 0.35
        ),
        "lgbm_beats_ridge_baseline": (
            r4["total_return"] > baseline_metrics["ridge_compact"]["total_return"]
        ),
        "lgbm_beats_rule_baseline": (
            r4["total_return"]
            > baseline_metrics["rule_carry_momentum"]["total_return"]
        ),
    }


def main() -> None:
    args = parse_args()
    if args.now and not args.validate_only:
        raise RuntimeError("--now is forbidden outside --validate-only")
    now = pd.Timestamp(args.now) if args.now else pd.Timestamp.now("UTC")
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    assert_reveal_time(now)
    if args.validate_only:
        print(json.dumps({"status": "PASS", "reveal_time_guard": "OPEN"}, indent=2))
        return
    if REPORT.exists():
        print(REPORT.read_text(encoding="utf-8"))
        return
    master = json.loads(MASTER_FREEZE.read_text(encoding="utf-8"))
    master_sha = sha256(MASTER_FREEZE)
    nodes = verify_and_load_chain(master_sha)
    REVEAL_DIR.mkdir(parents=True, exist_ok=True)
    if not RECEIPT.exists():
        atomic_json(
            {
                "started_at": now.isoformat(),
                "master_freeze_sha256": master_sha,
                "chain_tail_sha256": sha256(sorted(CHAIN_DIR.glob("*.json"))[-1]),
                "status": "REVEAL_STARTED",
            },
            RECEIPT,
        )
    decisions, blind_legs = load_blind_signals(nodes)
    revealed_legs = reveal_leg_returns(blind_legs)
    metrics: dict[str, dict[str, Any]] = {}
    revealed_decisions: list[pd.DataFrame] = []
    for strategy in ("r4", *BASELINES):
        strategy_metrics, strategy_decisions = evaluate_strategy(
            strategy, decisions, revealed_legs
        )
        metrics[strategy] = strategy_metrics
        revealed_decisions.append(strategy_decisions)
    gates = hard_gates(metrics["r4"], {name: metrics[name] for name in BASELINES})
    revealed_legs.to_parquet(LEGS_OUTPUT, index=False, compression="zstd")
    pd.concat(revealed_decisions, ignore_index=True).to_parquet(
        DECISIONS_OUTPUT, index=False, compression="zstd"
    )
    payload = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "freeze_revision": "r4",
        "revealed_at": now.isoformat(),
        "status": "PASS" if all(gates.values()) else "HARD-GATE-FAILED",
        "promotion_status": "not promoted",
        "live_ready": False,
        "master_freeze_sha256": master_sha,
        "metrics": metrics,
        "hard_gates": gates,
        "failed_hard_gates": [name for name, passed in gates.items() if not passed],
        "pending_non_oos_gates": [
            "historical_majority_fold_profit verification",
            "factor-group ablation stability verification",
            "tail IC direction verification",
        ],
        "outputs": {
            "legs": {"path": str(LEGS_OUTPUT.relative_to(ROOT)), "sha256": sha256(LEGS_OUTPUT)},
            "decisions": {"path": str(DECISIONS_OUTPUT.relative_to(ROOT)), "sha256": sha256(DECISIONS_OUTPUT)},
        },
        "note": (
            "OOS performance gates alone never authorize promotion; non-OOS "
            "ablation and live-executable gates must also be PASS."
        ),
    }
    atomic_json(payload, REPORT)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
