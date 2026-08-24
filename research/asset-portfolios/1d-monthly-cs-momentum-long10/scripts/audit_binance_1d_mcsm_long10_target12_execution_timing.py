#!/usr/bin/env python3
"""Audit target12 with a live-feasible 00:15 UTC rebalance price."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

import research_binance_1d_mcsm_long10 as long10
import research_binance_1d_mcsm_long10_liveability as live


base = long10.base
ARTIFACT_DIR = long10.ARTIFACT_DIR
DATA_GLOB = (
    long10.ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/"
    "source=binance_vision_monthly/month=*/*.parquet"
)
DATE_GLOB = (
    long10.ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/"
    "date=*/symbol=*.parquet"
)
SPEC = "specs/binance-1d-mcsm-long10-tv12-risk-budget-contract-2026-08-20.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def _price_returns_at_entry(
    weights: pd.DataFrame,
    close: pd.DataFrame,
    entry: pd.DataFrame,
) -> pd.Series:
    prior = weights.shift(1).fillna(0.0)
    changed = (weights - prior).abs().sum(axis=1).gt(1e-14)
    regular = (prior * (close / close.shift(1) - 1.0).fillna(0.0)).sum(axis=1)
    split = (
        prior * (entry / close.shift(1) - 1.0).fillna(0.0)
        + weights * (close / entry - 1.0).fillna(0.0)
    ).sum(axis=1)
    return regular.where(~changed, split)


def _load_0015_open() -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    rows = con.execute(
        f"""
        SELECT ts_ms, sym_key, open, volume, trade_count, is_closed
        FROM (
            SELECT
                epoch_ms(ts) AS ts_ms,
                replace(symbol, '/USDT:USDT', '') AS sym_key,
                open,
                volume,
                trade_count,
                is_closed,
                priority
            FROM (
                SELECT *, 0 AS priority
                FROM read_parquet('{DATA_GLOB}', union_by_name=true)
                UNION ALL BY NAME
                SELECT *, 1 AS priority
                FROM read_parquet('{DATE_GLOB}', union_by_name=true)
            )
            WHERE extract(day FROM ts) = 1
              AND extract(hour FROM ts) = 0
              AND extract(minute FROM ts) = 15
              AND ts >= TIMESTAMPTZ '2020-08-01 00:15:00+00:00'
              AND ts <= TIMESTAMPTZ '2026-06-01 00:15:00+00:00'
            QUALIFY row_number() OVER (PARTITION BY ts_ms, sym_key ORDER BY priority) = 1
        )
        ORDER BY ts_ms, sym_key
        """
    ).fetchall()
    frame = pd.DataFrame(
        rows,
        columns=["ts_ms", "sym_key", "open_0015", "volume_0015", "trade_count_0015", "is_closed"],
    )
    frame["day"] = pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    if frame.duplicated(["day", "sym_key"]).any():
        raise RuntimeError("duplicate 00:15 entry keys")
    if not frame["is_closed"].all():
        raise RuntimeError("00:15 source contains non-closed bars")
    return frame


def _reconstruct_weights(
    holdings: list[dict[str, Any]],
    close: pd.DataFrame,
) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for row in holdings:
        if row.get("status") != "traded":
            continue
        day = pd.Timestamp(row["rebalance"])
        end = min(day + pd.offsets.MonthEnd(0), close.index.max())
        longs = [symbol for symbol in str(row.get("longs", "")).split(",") if symbol]
        scale = float(row.get("portfolio_scale", 1.0))
        weights.loc[day:end, longs] = 0.1 * scale
    return weights.loc[live.EVALUATION_START:]


def _path_blockers(
    stage: str,
    weights: pd.DataFrame,
    close: pd.DataFrame,
    entry_rows: pd.DataFrame,
) -> pd.DataFrame:
    entry = entry_rows.set_index(["day", "sym_key"])
    prior = weights.shift(1).fillna(0.0)
    changed = (weights - prior).abs().gt(1e-14)
    events: list[dict[str, Any]] = []
    for day in weights.index[changed.any(axis=1) & weights.index.to_series().dt.is_month_start.to_numpy()]:
        for symbol in changed.columns[changed.loc[day]]:
            key = (day, symbol)
            row = entry.loc[key] if key in entry.index else None
            valid = bool(
                row is not None
                and pd.notna(row["open_0015"])
                and float(row["open_0015"]) > 0
                and float(row["volume_0015"]) > 0
                and int(row["trade_count_0015"]) > 0
                and bool(row["is_closed"])
            )
            if not valid:
                before = float(prior.at[day, symbol])
                after = float(weights.at[day, symbol])
                events.append(
                    {
                        "stage": stage,
                        "event": "invalid_entry" if after > before else "invalid_exit",
                        "day": day,
                        "symbol": symbol,
                        "weight_before": before,
                        "weight_after": after,
                        "open_0015": float(row["open_0015"]) if row is not None and pd.notna(row["open_0015"]) else None,
                        "volume_0015": float(row["volume_0015"]) if row is not None and pd.notna(row["volume_0015"]) else None,
                        "trade_count_0015": int(row["trade_count_0015"]) if row is not None and pd.notna(row["trade_count_0015"]) else None,
                    }
                )
    held = weights.abs().gt(1e-14)
    missing_close = held & close.reindex_like(weights).isna()
    for row_index, column_index in zip(*np.where(missing_close.to_numpy())):
        events.append(
            {
                "stage": stage,
                "event": "held_missing_close",
                "day": missing_close.index[row_index],
                "symbol": str(missing_close.columns[column_index]),
                "weight_before": float(weights.iat[row_index, column_index]),
                "weight_after": float(weights.iat[row_index, column_index]),
                "open_0015": None,
                "volume_0015": None,
                "trade_count_0015": None,
            }
        )
    return pd.DataFrame(events)


def _entry_open_panel(
    open_: pd.DataFrame,
    entry_rows: pd.DataFrame,
) -> pd.DataFrame:
    valid = (
        entry_rows["open_0015"].gt(0)
        & entry_rows["volume_0015"].gt(0)
        & entry_rows["trade_count_0015"].gt(0)
        & entry_rows["is_closed"]
    )
    pivot = entry_rows.loc[valid].pivot(index="day", columns="sym_key", values="open_0015")
    pivot = pivot.reindex(index=open_.index, columns=open_.columns)
    result = open_.copy()
    for day in pd.date_range(live.EVALUATION_START, open_.index.max().to_period("M").to_timestamp(), freq="MS"):
        if day in result.index:
            result.loc[day] = pivot.loc[day] if day in pivot.index else np.nan
    return result


def _simulate_0015(
    weights: pd.DataFrame,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    funding: pd.DataFrame,
    entry_rows: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    weights = weights.loc[live.EVALUATION_START:].copy()
    close_eval = close.loc[weights.index]
    entry = open_.loc[weights.index].copy()
    entry_0015 = entry_rows.pivot(index="day", columns="sym_key", values="open_0015")
    entry_0015 = entry_0015.reindex(index=entry.index, columns=entry.columns)
    changed = weights.sub(weights.shift(1).fillna(0.0)).abs().gt(1e-14)
    rebalance_days = changed.any(axis=1) & entry.index.to_series().dt.is_month_start.to_numpy()
    required = changed & rebalance_days.to_numpy()[:, None]
    missing = required & entry_0015.isna()
    if missing.to_numpy().any():
        examples = [
            (str(missing.index[row].date()), str(missing.columns[column]))
            for row, column in zip(*np.where(missing.to_numpy()))
        ][:10]
        raise RuntimeError(f"missing required 00:15 entry prices: {examples}")
    for day in entry.index[rebalance_days]:
        use = changed.loc[day]
        entry.loc[day, use] = entry_0015.loc[day, use]
    price = _price_returns_at_entry(weights, close_eval, entry)
    prior = weights.shift(1).fillna(0.0)
    turnover = (weights - prior).abs().sum(axis=1)
    turnover.iloc[-1] += weights.iloc[-1].abs().sum()
    funding_eval = funding.reindex_like(weights)
    funding_pnl = -(weights * funding_eval.fillna(0.0)).sum(axis=1)
    fee = turnover * live.FEE_RATE
    slippage = turnover * live.SLIPPAGE_RATE
    net = price + funding_pnl - fee - slippage
    metrics = base.performance(net)
    equity = (1.0 + net).cumprod()
    metrics.update(
        {
            "variant": "adv_top10_target12_entry_0015",
            "entry_timing": "first available 00:15 UTC bar open after 00:00 close confirmation",
            "rebalance_days": int(rebalance_days.sum()),
            "changed_symbol_prices": int(required.to_numpy().sum()),
            "missing_required_prices": int(missing.to_numpy().sum()),
            "ann_turnover": float(turnover.sum() * base.ANNUALIZER / len(net)),
            "mean_gross_exposure": float(weights.abs().sum(axis=1).mean()),
            "max_gross_exposure": float(weights.abs().sum(axis=1).max()),
            "price_pnl_sum": float(price.sum()),
            "funding_pnl_sum": float(funding_pnl.sum()),
            "fee_pnl_sum": -float(fee.sum()),
            "slippage_pnl_sum": -float(slippage.sum()),
            "arithmetic_total_pnl_sum": float(net.sum()),
            "nonpositive_equity_days": int((equity <= 0).sum()),
        }
    )
    metrics.update(live._path_diagnostics(net))
    daily = pd.DataFrame(
        {
            "variant": metrics["variant"],
            "day": net.index,
            "net_return": net.to_numpy(),
            "price_pnl": price.to_numpy(),
            "funding_pnl": funding_pnl.to_numpy(),
            "fee": fee.to_numpy(),
            "slippage": slippage.to_numpy(),
            "turnover": turnover.to_numpy(),
            "equity": equity.to_numpy(),
        }
    )
    used_rows = []
    for day in entry.index[rebalance_days]:
        for symbol in changed.columns[changed.loc[day]]:
            used_rows.append(
                {
                    "day": day,
                    "symbol": symbol,
                    "weight_before": float(prior.at[day, symbol]),
                    "weight_after": float(weights.at[day, symbol]),
                    "open_0000": float(open_.at[day, symbol]),
                    "open_0015": float(entry.at[day, symbol]),
                    "entry_move": float(entry.at[day, symbol] / open_.at[day, symbol] - 1.0),
                }
            )
    return metrics, daily, pd.DataFrame(used_rows)


def _self_test() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=index)
    close = pd.DataFrame({"A": [110.0, 121.0, 133.1]}, index=index)
    entry = pd.DataFrame({"A": [100.0, 110.0, 121.0]}, index=index)
    result = _price_returns_at_entry(weights, close, entry)
    assert np.allclose(result.to_numpy(), [0.10, 0.10, 0.10])
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return
    close, open_, bars, quote, funding, bases, cache_meta, audit = long10.load_inputs()
    source = live._baseline_payload("adv10m", "top_n", close, open_, bars, quote, funding, bases)
    config = live.OverlayConfig(
        "adv_top10_target12",
        "ADV Top10 target12",
        "timing_source",
        target_vol=0.12,
    )
    source_payload = live._simulate_overlay(config, source, close, open_, quote, funding)
    entry_rows = _load_0015_open()
    original_blockers = _path_blockers(
        "original_target12",
        source_payload["weights"],
        close,
        entry_rows,
    )
    executable_open = _entry_open_panel(open_, entry_rows)
    executable_variant = long10.ext.Variant(
        "adv_top10_target12_entry0015_reselected",
        "ADV Top10 target12 00:15 reselected",
        "execution_audit",
        universe="adv10m",
        n_legs=10,
        long_only=True,
        portfolio_vol_target=0.12,
    )
    original_min = long10.ext.PORTFOLIO_SCALE_MIN
    original_max = long10.ext.PORTFOLIO_SCALE_MAX
    try:
        long10.ext.PORTFOLIO_SCALE_MIN = 0.0
        long10.ext.PORTFOLIO_SCALE_MAX = 1.0
        indicative = long10.ext._simulate(
            executable_variant,
            close,
            executable_open,
            bars,
            quote,
            funding,
            bases,
        )
    finally:
        long10.ext.PORTFOLIO_SCALE_MIN = original_min
        long10.ext.PORTFOLIO_SCALE_MAX = original_max
    indicative_weights = _reconstruct_weights(indicative["holdings"], close)
    indicative_blockers = _path_blockers(
        "entry0015_reselected",
        indicative_weights,
        close,
        entry_rows,
    )
    blockers = pd.concat([original_blockers, indicative_blockers], ignore_index=True)
    baseline = source_payload["metrics"]
    indicative_net = indicative["daily"].set_index("day")["net_return"].loc[live.EVALUATION_START:]
    metrics = base.performance(indicative_net)
    metrics.update(live._path_diagnostics(indicative_net))
    metrics.update(
        {
            "variant": "adv_top10_target12_entry0015_reselected_fair_window",
            "entry_timing": "00:15 UTC open with positive volume and trade_count",
            "performance_valid": False,
        }
    )
    comparison = {
        "indicative_return_difference": metrics["total_return"] - baseline["total_return"],
        "indicative_cagr_difference": metrics["cagr"] - baseline["cagr"],
        "indicative_sharpe_difference": metrics["sharpe"] - baseline["sharpe"],
        "indicative_mdd_difference": metrics["max_drawdown"] - baseline["max_drawdown"],
        "original_blockers": int(len(original_blockers)),
        "reselected_blockers": int(len(indicative_blockers)),
    }
    stem = f"binance-1d-mcsm-long10-target12-execution-timing-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": long10.FAMILY_NAME,
        "contract": SPEC,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data_glob": str(DATA_GLOB.relative_to(long10.ROOT)),
        "date_overlay_glob": str(DATE_GLOB.relative_to(long10.ROOT)),
        "cache": cache_meta,
        "audit": audit,
        "baseline_0000": baseline,
        "entry_0015_reselected_indicative_only": metrics,
        "comparison": comparison,
        "audit_status": "HARD_BLOCKER / PERFORMANCE_INVALIDATED",
        "performance_valid": False,
        "blocker_counts": blockers.groupby(["stage", "event"]).size().rename("count").reset_index().to_dict(orient="records"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-blockers.csv", blockers, force=args.force)
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-reselected-holdings.csv",
        pd.DataFrame(indicative["holdings"]),
        force=args.force,
    )
    print(
        json.dumps(
            {
                "audit_status": summary["audit_status"],
                "baseline_0000": baseline,
                "entry_0015_reselected_indicative_only": metrics,
                "comparison": comparison,
                "blocker_counts": summary["blocker_counts"],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
