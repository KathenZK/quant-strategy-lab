from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TERMINAL = pd.Timestamp("2025-08-07T00:00:00Z")
HORIZONS = (1, 2, 3, 4)


@dataclass(frozen=True)
class StrategySource:
    strategy: str
    family: str
    path_file: Path
    trades_file: Path
    frontier: str
    full_ordered_mdd_pct: float
    trade_log_column: str
    win_rate_role: str = "account trades"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frozen recent 1y/2y/3y/4y ranking of BTC/ETH strategy paths."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sources() -> list[StrategySource]:
    portfolio = ROOT / "research/asset-portfolios"
    return [
        StrategySource(
            "RCR-growth",
            "BIN-1D-BE-RCR",
            portfolio / "1d-btceth-relative-cycle-rotation/artifacts/binance_1d_be_rcr_p0_frontiers_2026-08-12_path.csv",
            portfolio / "1d-btceth-relative-cycle-rotation/artifacts/binance_1d_be_rcr_p0_frontiers_2026-08-12_trades.csv",
            "growth_frontier",
            -69.6600350089438,
            "trade_log_growth",
        ),
        StrategySource(
            "LRMR-growth",
            "BIN-1D-BE-LRMR",
            portfolio / "1d-btceth-log-ratio-mean-reversion/artifacts/binance_1d_be_lrmr_p0_frontiers_2026-08-12_path.csv",
            portfolio / "1d-btceth-log-ratio-mean-reversion/artifacts/binance_1d_be_lrmr_p0_frontiers_2026-08-12_trades.csv",
            "growth_frontier",
            -44.879751920714575,
            "pair_log_growth",
        ),
        StrategySource(
            "CILL-growth",
            "BIN-1H-BE-CILL",
            portfolio / "1h-btceth-cross-impulse-lead-lag/artifacts/binance_1h_be_cill_p0_frontiers_2026-08-12_path.csv",
            portfolio / "1h-btceth-cross-impulse-lead-lag/artifacts/binance_1h_be_cill_p0_frontiers_2026-08-12_trades.csv",
            "growth_frontier",
            -21.776020019631538,
            "trade_log_growth",
        ),
        StrategySource(
            "CBCT-P1-growth",
            "BIN-1D-BE-CBCT",
            portfolio / "1d-btceth-cross-breadth-channel-trend/artifacts/binance_1d_be_cbct_p1_profit_protection_2026-08-12_path.csv",
            portfolio / "1d-btceth-cross-breadth-channel-trend/artifacts/binance_1d_be_cbct_p1_profit_protection_2026-08-12_trades.csv",
            "growth_frontier",
            -37.19612846945293,
            "trade_log_growth",
        ),
        StrategySource(
            "DHCT-growth",
            "BIN-1D-BE-DHCT",
            portfolio / "1d-btceth-dual-horizon-campaign-trend/artifacts/binance_1d_be_dhct_p0_search_2026-08-12_path.csv",
            portfolio / "1d-btceth-dual-horizon-campaign-trend/artifacts/binance_1d_be_dhct_p0_search_2026-08-12_trades.csv",
            "growth_frontier",
            -35.225014893476924,
            "trade_log_growth",
        ),
        StrategySource(
            "DASE-75CBCT-25RCR",
            "BIN-1D-BE-DASE",
            portfolio / "1d-btceth-dual-alpha-sleeve-ensemble/artifacts/binance_1d_be_dase_p0_2026-08-12_paths.csv",
            portfolio / "1d-btceth-dual-alpha-sleeve-ensemble/artifacts/binance_1d_be_dase_p0_2026-08-12_component_trades.csv",
            "growth_frontier",
            -34.34024086168368,
            "trade_log_growth",
            "component closes",
        ),
        StrategySource(
            "COST-growth",
            "BIN-1D-BE-COST",
            portfolio / "1d-btceth-crisis-override-shadow-trend/artifacts/binance_1d_be_cost_p0_2026-08-12_paths.csv",
            portfolio / "1d-btceth-crisis-override-shadow-trend/artifacts/binance_1d_be_cost_p0_2026-08-12_trades.csv",
            "growth_frontier",
            -35.22258089123961,
            "trade_log_growth",
        ),
        StrategySource(
            "CPPR-25pct-growth",
            "BIN-1D-BE-CPPR",
            portfolio / "1d-btceth-crisis-partial-profit-runner/artifacts/binance_1d_be_cppr_p0_2026-08-12_paths.csv",
            portfolio / "1d-btceth-crisis-partial-profit-runner/artifacts/binance_1d_be_cppr_p0_2026-08-12_trades.csv",
            "growth_frontier",
            -31.866201919832605,
            "trade_log_growth",
        ),
        StrategySource(
            "CPEHC-30d-1d-growth",
            "BIN-1D-BE-CPEHC",
            portfolio / "1d-btceth-crisis-profit-exit-handoff-continuity/artifacts/binance_1d_be_cpehc_p0_2026-08-12_paths.csv",
            portfolio / "1d-btceth-crisis-profit-exit-handoff-continuity/artifacts/binance_1d_be_cpehc_p0_2026-08-12_trades.csv",
            "growth_frontier",
            -31.109815590442636,
            "trade_log_growth",
        ),
    ]


def normalize_path(frame: pd.DataFrame, frontier: str | None = None) -> pd.Series:
    if frontier is not None and "frontier" in frame.columns:
        frame = frame.loc[frame["frontier"].eq(frontier)].copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    equity = frame.set_index("ts")["equity"].astype(float).sort_index()
    equity = equity.loc[~equity.index.duplicated(keep="last")]
    if equity.index[-1] != TERMINAL:
        raise RuntimeError(f"unexpected terminal: {equity.index[-1]}")
    return equity


def daily_close_equity(equity: pd.Series) -> pd.Series:
    daily = equity.resample("1D").last().dropna()
    if daily.index[-1] != TERMINAL:
        daily.loc[TERMINAL] = float(equity.loc[:TERMINAL].iloc[-1])
    return daily.sort_index()


def wilson_lower(wins: int, trades: int, z: float = 1.96) -> float:
    if trades <= 0:
        return 0.0
    p = wins / trades
    denominator = 1.0 + z * z / trades
    center = p + z * z / (2.0 * trades)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * trades)) / trades)
    return (center - margin) / denominator


def slice_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    log_column: str,
) -> dict[str, Any]:
    before = equity.loc[equity.index <= start]
    if before.empty:
        raise RuntimeError(f"no equity baseline at {start}")
    start_equity = float(before.iloc[-1])
    sample = equity.loc[(equity.index > start) & (equity.index <= end)]
    values = pd.concat(
        [pd.Series([start_equity], index=pd.DatetimeIndex([start])), sample]
    )
    values = values.loc[~values.index.duplicated(keep="last")].sort_index()
    end_equity = float(values.iloc[-1])
    normalized = values / start_equity
    max_drawdown = float((normalized / normalized.cummax() - 1.0).min())
    trade_slice = trades.loc[
        trades["exit_ts"].gt(start) & trades["exit_ts"].le(end)
    ]
    logs = pd.to_numeric(trade_slice[log_column], errors="coerce").dropna()
    wins = int(logs.gt(0.0).sum())
    trade_count = int(len(logs))
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "equity_multiple": end_equity / start_equity,
        "return_pct": (end_equity / start_equity - 1.0) * 100.0,
        "daily_close_mdd_pct": max_drawdown * 100.0,
        "closed_trades": trade_count,
        "wins": wins,
        "win_rate": wins / trade_count if trade_count else None,
        "win_rate_wilson_lower": wilson_lower(wins, trade_count),
    }


def ma7_rows() -> list[dict[str, Any]]:
    baseline_path = FAMILY_DIR / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
    baseline = load_module(baseline_path, "recent_rank_ma7_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "recent_rank_ma7_transfer",
    )
    engine = transfer.load_engine()
    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    pair = json.loads(
        (ARTIFACT_DIR / "binance_1d_ma7_p2e_ordered_1h_mdd_2026-08-12.json").read_text(
            encoding="utf-8"
        )
    )["best_pair"]
    long_config = engine.Config(**pair["long_config"])
    short_config = engine.Config(**pair["short_config"])
    output: list[dict[str, Any]] = []
    for symbol, slug in baseline.ASSETS.items():
        hourly, funding, quality = baseline.load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = engine.build_features(book, hourly, funding)
        result = engine.backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=baseline.boundary(book, baseline.COMMON_START),
            terminal_index=baseline.boundary(book, baseline.DEVELOPMENT_END),
            retain=True,
        )
        path = pd.DataFrame(result.path).rename(columns={"close_equity": "equity"})
        equity = daily_close_equity(normalize_path(path))
        trades = pd.DataFrame(result.trades)
        trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        trades["trade_log_growth"] = np.log1p(trades["net_return"].astype(float))
        full_ordered_mdd = float(pair["assets"][symbol]["ordered_1h_mdd_pct"])
        for years in HORIZONS:
            output.append(
                {
                    "strategy": f"MA7-P2-growth-{symbol.removesuffix('USDT')}",
                    "family": "BIN-1D-MA7-AS-SEARCH-P2E",
                    "horizon_years": years,
                    "full_ordered_mdd_pct": full_ordered_mdd,
                    "win_rate_role": "asset trades",
                    **slice_metrics(
                        equity,
                        trades,
                        start=TERMINAL - pd.DateOffset(years=years),
                        end=TERMINAL,
                        log_column="trade_log_growth",
                    ),
                }
            )
    return output


def portfolio_rows() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in sources():
        equity = daily_close_equity(
            normalize_path(pd.read_csv(source.path_file), source.frontier)
        )
        trades = pd.read_csv(source.trades_file)
        if "frontier" in trades.columns:
            trades = trades.loc[trades["frontier"].eq(source.frontier)].copy()
        trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        for years in HORIZONS:
            output.append(
                {
                    "strategy": source.strategy,
                    "family": source.family,
                    "horizon_years": years,
                    "full_ordered_mdd_pct": source.full_ordered_mdd_pct,
                    "win_rate_role": source.win_rate_role,
                    **slice_metrics(
                        equity,
                        trades,
                        start=TERMINAL - pd.DateOffset(years=years),
                        end=TERMINAL,
                        log_column=source.trade_log_column,
                    ),
                }
            )
    return output


def add_ranks(frame: pd.DataFrame) -> pd.DataFrame:
    ranked: list[pd.DataFrame] = []
    for _, group in frame.groupby("horizon_years", sort=True):
        group = group.copy()
        group["return_rank"] = group["return_pct"].rank(
            ascending=False, method="min"
        ).astype(int)
        group["mdd_rank"] = group["daily_close_mdd_pct"].rank(
            ascending=False, method="min"
        ).astype(int)
        group["win_rank"] = group["win_rate_wilson_lower"].rank(
            ascending=False, method="min"
        ).astype(int)
        count = len(group)
        denominator = max(1, count - 1)
        return_score = (count - group["return_rank"]) / denominator
        mdd_score = (count - group["mdd_rank"]) / denominator
        win_score = (count - group["win_rank"]) / denominator
        group["horizon_score"] = (
            0.45 * return_score + 0.35 * mdd_score + 0.20 * win_score
        )
        group.loc[group["closed_trades"].eq(0), "horizon_score"] *= 0.5
        group["composite_rank"] = group["horizon_score"].rank(
            ascending=False, method="min"
        ).astype(int)
        ranked.append(group)
    return pd.concat(ranked, ignore_index=True).sort_values(
        ["horizon_years", "composite_rank", "strategy"]
    )


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    weights = {1: 0.35, 2: 0.30, 3: 0.20, 4: 0.15}
    rows = []
    for strategy, group in frame.groupby("strategy"):
        score = sum(
            float(row.horizon_score) * weights[int(row.horizon_years)]
            for row in group.itertuples()
        )
        positive = int(group["return_pct"].gt(0.0).sum())
        dd_safe = int(group["daily_close_mdd_pct"].ge(-20.0).sum())
        rows.append(
            {
                "strategy": strategy,
                "family": group["family"].iloc[0],
                "recent_weighted_score": score,
                "positive_horizons": positive,
                "dd_le_20_horizons": dd_safe,
                "min_closed_trades": int(group["closed_trades"].min()),
                "full_ordered_mdd_pct": float(group["full_ordered_mdd_pct"].iloc[0]),
            }
        )
    summary = pd.DataFrame(rows).sort_values(
        ["recent_weighted_score", "positive_horizons", "strategy"],
        ascending=[False, False, True],
    )
    summary.insert(0, "overall_rank", range(1, len(summary) + 1))
    return summary


def self_test() -> None:
    equity = pd.Series(
        [1.0, 1.2, 0.9, 1.1],
        index=pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC"),
    )
    trades = pd.DataFrame(
        {
            "exit_ts": pd.to_datetime(["2024-01-03", "2024-01-04"], utc=True),
            "log": [-0.1, 0.2],
        }
    )
    result = slice_metrics(
        equity,
        trades,
        start=pd.Timestamp("2024-01-01", tz="UTC"),
        end=pd.Timestamp("2024-01-04", tz="UTC"),
        log_column="log",
    )
    assert math.isclose(result["return_pct"], 10.0)
    assert math.isclose(result["daily_close_mdd_pct"], -25.0)
    assert result["closed_trades"] == 2 and result["wins"] == 1
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    rows = portfolio_rows() + ma7_rows()
    ranking = add_ranks(pd.DataFrame(rows))
    summary = summarize(ranking)
    stem = f"binance_btceth_recent_horizon_ranking_{args.run_date}"
    ranking.to_csv(ARTIFACT_DIR / f"{stem}.csv", index=False)
    summary.to_csv(ARTIFACT_DIR / f"{stem}_summary.csv", index=False)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "evidence_role": "post-selection diagnostic on already revealed development only",
        "terminal": TERMINAL.isoformat(),
        "horizons_years": list(HORIZONS),
        "return_mdd_sampling": "continuous-account UTC daily-close equity",
        "win_rate": "net-positive closes with exit_ts in (slice_start, terminal]",
        "ranking_weights": {"return": 0.45, "daily_close_mdd": 0.35, "wilson_win_rate": 0.20},
        "overall_horizon_weights": {"1y": 0.35, "2y": 0.30, "3y": 0.20, "4y": 0.15},
        "audit_revealed": False,
        "prospective_revealed": False,
        "summary": summary.to_dict(orient="records"),
    }
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(summary.to_json(orient="records", force_ascii=False))


if __name__ == "__main__":
    main()
