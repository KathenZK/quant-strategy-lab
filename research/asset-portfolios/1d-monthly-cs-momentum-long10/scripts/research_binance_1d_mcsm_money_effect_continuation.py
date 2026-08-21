#!/usr/bin/env python3
"""Diagnose Binance money-effect diffusion and Top10 leader continuation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

import research_binance_1d_mcsm_long10 as long10


base = long10.base
ext = long10.ext
ROOT = long10.ROOT
ARTIFACT_DIR = long10.ARTIFACT_DIR
FAMILY_NAME = long10.FAMILY_NAME
FAMILY_ALIAS = long10.FAMILY_ALIAS
SPEC = "specs/binance-1d-mcsm-money-effect-continuation-diagnostic-contract-2026-08-20.md"
EVALUATION_START = pd.Timestamp("2020-08-01")
LAST_ENTRY = pd.Timestamp("2026-05-01")
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0004
ROUND_TRIP_COST = 2.0 * (FEE_RATE + SLIPPAGE_RATE)
STATE_LOOKBACK = 12
BOOTSTRAP_DRAWS = 5_000
BOOTSTRAP_SEED = 20260820
HORIZONS = {"1d": 1, "3d": 3, "7d": 7, "14d": 14}
OHLCV_MONTHLY_GLOB = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/"
    "source=binance_vision_monthly/month=*/*.parquet"
)
OHLCV_DATE_GLOB = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/"
    "date=*/symbol=*.parquet"
)
FUNDING_MONTHLY_GLOB = (
    ROOT
    / "data/normalized/funding_rates/exchange=binance/market_type=perp/"
    "source=binance_vision_monthly/month=*/*.parquet"
)
FUNDING_DATE_GLOB = (
    ROOT
    / "data/normalized/funding_rates/exchange=binance/market_type=perp/"
    "date=*/symbol=*.parquet"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def _load_daily_0015() -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    query = f"""
        SELECT ts, sym_key, open_0015, volume_0015, trade_count_0015, is_closed
        FROM (
            SELECT
                ts,
                replace(symbol, '/USDT:USDT', '') AS sym_key,
                open AS open_0015,
                volume AS volume_0015,
                trade_count AS trade_count_0015,
                is_closed,
                priority
            FROM (
                SELECT ts, symbol, open, volume, trade_count, is_closed, 0 AS priority
                FROM read_parquet('{OHLCV_MONTHLY_GLOB}', union_by_name=true)
                UNION ALL BY NAME
                SELECT ts, symbol, open, volume, trade_count, is_closed, 1 AS priority
                FROM read_parquet('{OHLCV_DATE_GLOB}', union_by_name=true)
            )
            WHERE extract(hour FROM ts) = 0
              AND extract(minute FROM ts) = 15
              AND ts >= TIMESTAMPTZ '2020-08-01 00:15:00+00:00'
              AND ts <= TIMESTAMPTZ '2026-06-01 00:15:00+00:00'
            QUALIFY row_number() OVER (PARTITION BY ts, sym_key ORDER BY priority DESC) = 1
        )
        ORDER BY ts, sym_key
    """
    frame = con.execute(query).fetch_df()
    frame["day"] = pd.to_datetime(frame.pop("ts"), utc=True).dt.tz_localize(None).dt.normalize()
    if frame.duplicated(["day", "sym_key"]).any():
        raise RuntimeError("duplicate 00:15 OHLCV keys")
    frame["valid"] = (
        frame["open_0015"].gt(0)
        & frame["volume_0015"].gt(0)
        & frame["trade_count_0015"].gt(0)
        & frame["is_closed"].fillna(False)
    )
    return frame


def _load_monthly_funding() -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    query = f"""
        WITH deduped AS (
            SELECT ts, sym_key, funding_rate, funding_interval_hours
            FROM (
                SELECT
                    ts,
                    replace(symbol, '/USDT:USDT', '') AS sym_key,
                    funding_rate,
                    funding_interval_hours,
                    priority
                FROM (
                    SELECT ts, symbol, funding_rate, funding_interval_hours, 0 AS priority
                    FROM read_parquet('{FUNDING_MONTHLY_GLOB}', union_by_name=true)
                    UNION ALL BY NAME
                    SELECT ts, symbol, funding_rate, funding_interval_hours, 1 AS priority
                    FROM read_parquet('{FUNDING_DATE_GLOB}', union_by_name=true)
                )
                WHERE ts >= TIMESTAMPTZ '2020-08-01 00:15:00+00:00'
                  AND ts < TIMESTAMPTZ '2026-06-01 00:15:00+00:00'
                QUALIFY row_number() OVER (PARTITION BY ts, sym_key ORDER BY priority DESC) = 1
            )
        )
        SELECT
            date_trunc('month', ts - INTERVAL '15 minutes') AS holding_month,
            sym_key,
            sum(funding_rate) AS funding_sum,
            count(*) AS funding_events,
            median(funding_interval_hours) AS median_interval_hours
        FROM deduped
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    frame = con.execute(query).fetch_df()
    frame["holding_month"] = (
        pd.to_datetime(frame["holding_month"], utc=True).dt.tz_localize(None).dt.normalize()
    )
    if frame.duplicated(["holding_month", "sym_key"]).any():
        raise RuntimeError("duplicate monthly funding keys")
    return frame


def _panels_0015(frame: pd.DataFrame, columns: pd.Index) -> tuple[pd.DataFrame, pd.DataFrame]:
    open_panel = frame.pivot(index="day", columns="sym_key", values="open_0015")
    valid_panel = frame.pivot(index="day", columns="sym_key", values="valid").fillna(False).astype(bool)
    full_index = pd.date_range(frame["day"].min(), frame["day"].max(), freq="D")
    return (
        open_panel.reindex(index=full_index, columns=columns),
        valid_panel.reindex(index=full_index, columns=columns, fill_value=False),
    )


def _window_sum(frame: pd.DataFrame, end: pd.Timestamp, start_offset: int, end_offset: int) -> pd.Series:
    start = end - pd.Timedelta(days=start_offset)
    stop = end - pd.Timedelta(days=end_offset)
    window = frame.loc[start:stop]
    return window.sum(min_count=24)


def _month_signal(
    month_start: pd.Timestamp,
    close: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any] | None:
    one = ext._signal(close, month_start, 1, 0)
    three = ext._signal(close, month_start, 3, 0)
    if one is None or three is None:
        return None
    formation_1m, _, end_month, start_day_1m, signal_end_day = one
    formation_3m, _, _, start_day_3m, signal_end_day_3m = three
    if signal_end_day != signal_end_day_3m:
        raise RuntimeError("1m and 3m signal endpoints differ")
    coverage = base.coverage_in_month(bars, end_month)
    excluded = base.excluded_mask(close.columns, bases)
    adv = quote.rolling(base.ADV_WINDOW, min_periods=base.ADV_WINDOW).mean().loc[signal_end_day]
    endpoint_ok = (
        close.loc[start_day_1m].notna()
        & close.loc[signal_end_day].notna()
        & bars.loc[start_day_1m].ge(base.MIN_ENDPOINT_BARS)
        & bars.loc[signal_end_day].ge(base.MIN_ENDPOINT_BARS)
    )
    eligible = (
        (~excluded)
        & endpoint_ok
        & coverage.ge(base.MIN_COVERAGE)
        & formation_1m.notna()
        & adv.ge(base.MIN_ADV_USDT)
    )
    three_endpoint_ok = (
        close.loc[start_day_3m].notna()
        & bars.loc[start_day_3m].ge(base.MIN_ENDPOINT_BARS)
        & formation_3m.notna()
    )
    return {
        "formation_1m": formation_1m,
        "formation_3m": formation_3m,
        "eligible": eligible,
        "three_valid": eligible & three_endpoint_ok,
        "adv": adv,
        "signal_end_day": signal_end_day,
    }


def _ordered_symbols(signal: pd.Series, adv: pd.Series, mask: pd.Series) -> list[str]:
    pool = signal.loc[mask & signal.notna() & np.isfinite(signal)]
    return (
        pd.DataFrame({"signal": pool, "adv": adv.reindex(pool.index).fillna(-1.0)})
        .sort_values(["signal", "adv"], ascending=[False, False])
        .index.astype(str)
        .tolist()
    )


def _funding_for_top10(
    month_start: pd.Timestamp,
    symbols: list[str],
    funding_indexed: pd.DataFrame,
) -> tuple[float | None, float, int]:
    days = int((month_start + pd.offsets.MonthBegin(1) - month_start).days)
    sums: list[float] = []
    coverages: list[float] = []
    missing = 0
    for symbol in symbols:
        key = (month_start, symbol)
        if key not in funding_indexed.index:
            missing += 1
            coverages.append(0.0)
            continue
        row = funding_indexed.loc[key]
        interval = float(row["median_interval_hours"])
        expected = days * 24.0 / interval if interval > 0 else math.nan
        coverage = float(row["funding_events"] / expected) if expected > 0 else 0.0
        coverages.append(min(coverage, 1.0))
        sums.append(float(row["funding_sum"]))
        if coverage < 0.98:
            missing += 1
    funding_pnl = -float(np.mean(sums)) if missing == 0 and len(sums) == len(symbols) else None
    return funding_pnl, float(np.mean(coverages)) if coverages else 0.0, missing


def _cross_section_return(
    symbols: list[str],
    entry_day: pd.Timestamp,
    end_day: pd.Timestamp,
    open_0015: pd.DataFrame,
    valid_0015: pd.DataFrame,
    require_all: bool,
) -> tuple[float | None, float, int]:
    if entry_day not in open_0015.index or end_day not in open_0015.index:
        return None, 0.0, 0
    entry_valid = valid_0015.loc[entry_day, symbols]
    end_valid = valid_0015.loc[end_day, symbols]
    valid = entry_valid & end_valid
    coverage = float(valid.mean()) if len(valid) else 0.0
    if require_all and not bool(valid.all()):
        return None, coverage, int(valid.sum())
    usable = valid.index[valid]
    if len(usable) == 0:
        return None, coverage, 0
    returns = open_0015.loc[end_day, usable] / open_0015.loc[entry_day, usable] - 1.0
    return float(returns.mean()), coverage, int(len(usable))


def _feature_values(
    signal: dict[str, Any],
    top10: list[str],
    quote: pd.DataFrame,
    close: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, float]:
    eligible = signal["eligible"]
    names = eligible.index[eligible]
    f1 = signal["formation_1m"].loc[names]
    f3 = signal["formation_3m"]
    signal_day = signal["signal_end_day"]
    recent_volume = _window_sum(quote, signal_day, 29, 0).reindex(names)
    prior_volume = _window_sum(quote, signal_day, 59, 30).reindex(names)
    volume_valid = recent_volume.notna() & prior_volume.notna() & prior_volume.gt(0)
    liquidity_participation = float((recent_volume[volume_valid] > prior_volume[volume_valid]).mean())
    three_names = signal["three_valid"].index[signal["three_valid"]]
    rank_3m = f3.loc[three_names].rank(pct=True, method="average")
    leader_3m = rank_3m.reindex(top10)
    aligned = pd.concat(
        [signal["formation_1m"].reindex(three_names), f3.reindex(three_names)], axis=1
    ).dropna()
    rank_alignment = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman"))
    funding_30d = funding.loc[signal_day - pd.Timedelta(days=29) : signal_day].mean()
    daily_returns = close.pct_change(fill_method=None)
    vol_30d = (
        daily_returns.loc[signal_day - pd.Timedelta(days=29) : signal_day].std(ddof=0)
        * math.sqrt(base.ANNUALIZER)
    )
    universe_funding = float(funding_30d.reindex(names).median())
    top_funding = float(funding_30d.reindex(top10).median())
    universe_vol = float(vol_30d.reindex(names).median())
    top_vol = float(vol_30d.reindex(top10).median())
    return {
        "breadth_positive_1m": float(f1.gt(0).mean()),
        "market_median_1m": float(f1.median()),
        "liquidity_participation": liquidity_participation,
        "leader_spread_1m": float(f1.reindex(top10).mean() - f1.median()),
        "leader_3m_rank_pct": float(leader_3m.mean()),
        "leader_3m_coverage": float(leader_3m.notna().mean()),
        "rank_alignment_1m_3m": rank_alignment,
        "top10_funding_minus_market_30d": top_funding - universe_funding,
        "top10_vol_ratio_30d": top_vol / universe_vol if universe_vol > 0 else math.nan,
    }


def _apply_causal_states(monthly: pd.DataFrame) -> pd.DataFrame:
    result = monthly.sort_values("month").reset_index(drop=True).copy()
    threshold_features = [
        "breadth_positive_1m",
        "market_median_1m",
        "liquidity_participation",
        "leader_spread_1m",
        "leader_3m_rank_pct",
        "rank_alignment_1m_3m",
        "top10_funding_minus_market_30d",
        "top10_vol_ratio_30d",
    ]
    for feature in threshold_features:
        result[f"{feature}_threshold"] = (
            result[feature].shift(1).expanding(min_periods=STATE_LOOKBACK).median()
        )
        result[f"{feature}_high"] = result[feature].gt(result[f"{feature}_threshold"])
    money_score = (
        result["breadth_positive_1m_high"].astype(int)
        + result["market_median_1m"].gt(0).astype(int)
        + result["liquidity_participation_high"].astype(int)
    )
    leader_score = (
        result["leader_spread_1m_high"].astype(int)
        + result["leader_3m_rank_pct_high"].astype(int)
        + result["rank_alignment_1m_3m_high"].astype(int)
    )
    warmup = result[
        [
            "breadth_positive_1m_threshold",
            "liquidity_participation_threshold",
            "leader_spread_1m_threshold",
            "leader_3m_rank_pct_threshold",
            "rank_alignment_1m_3m_threshold",
        ]
    ].isna().any(axis=1)
    result["money_effect_score"] = money_score
    result["leader_continuation_score"] = leader_score
    result["state_warmup"] = warmup
    result["money_effect_strong"] = money_score.ge(2) & ~warmup
    result["leader_continuation_strong"] = leader_score.ge(2) & ~warmup
    result["state"] = np.where(
        warmup,
        "warmup",
        np.where(result["money_effect_strong"], "strong", "weak")
        + "/"
        + np.where(result["leader_continuation_strong"], "strong", "weak"),
    )
    result["strong_strong_only_net"] = np.where(
        result["state"].eq("strong/strong"), result["top10_net_return"], 0.0
    )
    return result


def _stats(frame: pd.DataFrame) -> dict[str, Any]:
    valid = frame.dropna(subset=["top10_price_return", "market_price_return", "top10_excess_return"])
    excess = valid["top10_excess_return"]
    top = valid["top10_price_return"]
    market = valid["market_price_return"]
    t_stat = float(excess.mean() / (excess.std(ddof=1) / math.sqrt(len(excess)))) if len(excess) > 1 and excess.std(ddof=1) > 0 else math.nan
    return {
        "months": int(len(valid)),
        "mean_top10_price_return": float(top.mean()) if len(valid) else math.nan,
        "median_top10_price_return": float(top.median()) if len(valid) else math.nan,
        "mean_market_price_return": float(market.mean()) if len(valid) else math.nan,
        "mean_top10_excess_return": float(excess.mean()) if len(valid) else math.nan,
        "median_top10_excess_return": float(excess.median()) if len(valid) else math.nan,
        "top10_positive_rate": float(top.gt(0).mean()) if len(valid) else math.nan,
        "selection_win_rate": float(excess.gt(0).mean()) if len(valid) else math.nan,
        "excess_t_stat": t_stat,
    }


def _feature_conditionals(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    features = [
        "breadth_positive_1m",
        "market_median_1m",
        "liquidity_participation",
        "leader_spread_1m",
        "leader_3m_rank_pct",
        "rank_alignment_1m_3m",
        "top10_funding_minus_market_30d",
        "top10_vol_ratio_30d",
    ]
    usable = monthly.loc[~monthly["state_warmup"]].copy()
    for feature in features:
        for bucket, flag in (("high", True), ("low", False)):
            subset = usable.loc[usable[f"{feature}_high"].eq(flag)]
            rows.append({"feature": feature, "bucket": bucket, **_stats(subset)})
    return pd.DataFrame(rows)


def _state_table(monthly: pd.DataFrame) -> pd.DataFrame:
    usable = monthly.loc[~monthly["state_warmup"]].copy()
    valid_net = usable.dropna(subset=["top10_net_return"])
    positive_total = float(valid_net["top10_net_return"].clip(lower=0).sum())
    tail_cut = valid_net["top10_net_return"].quantile(0.90) if len(valid_net) else math.nan
    tail = valid_net.loc[valid_net["top10_net_return"].ge(tail_cut)]
    tail_total = float(tail["top10_net_return"].clip(lower=0).sum())
    rows: list[dict[str, Any]] = []
    for state in ("strong/strong", "strong/weak", "weak/strong", "weak/weak"):
        subset = usable.loc[usable["state"].eq(state)]
        valid_subset = subset.dropna(subset=["top10_net_return"])
        state_positive = float(valid_subset["top10_net_return"].clip(lower=0).sum())
        state_tail = tail.loc[tail["state"].eq(state)]
        row = {
            "state": state,
            **_stats(subset),
            "net_months": int(len(valid_subset)),
            "compound_net_return": float((1.0 + valid_subset["top10_net_return"]).prod() - 1.0),
            "positive_net_pnl_capture": state_positive / positive_total if positive_total > 0 else math.nan,
            "right_tail_net_pnl_capture": float(state_tail["top10_net_return"].clip(lower=0).sum()) / tail_total if tail_total > 0 else math.nan,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _decay_table(decay: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    merged = decay.merge(monthly[["month", "state", "state_warmup"]], on="month", how="left")
    rows: list[dict[str, Any]] = []
    for state in ("all", "strong/strong", "strong/weak", "weak/strong", "weak/weak"):
        subset = merged.loc[~merged["state_warmup"]]
        if state != "all":
            subset = subset.loc[subset["state"].eq(state)]
        for horizon in ("1d", "3d", "7d", "14d", "1m"):
            part = subset.loc[subset["horizon"].eq(horizon)].dropna(subset=["top10_return", "market_return"])
            excess = part["top10_return"] - part["market_return"]
            rows.append(
                {
                    "state": state,
                    "horizon": horizon,
                    "months": int(len(part)),
                    "mean_top10_return": float(part["top10_return"].mean()),
                    "median_top10_return": float(part["top10_return"].median()),
                    "mean_market_return": float(part["market_return"].mean()),
                    "mean_excess_return": float(excess.mean()),
                    "selection_win_rate": float(excess.gt(0).mean()),
                    "mean_market_coverage": float(part["market_coverage"].mean()),
                }
            )
    return pd.DataFrame(rows)


def _cohorts(monthly: pd.DataFrame) -> pd.DataFrame:
    usable = monthly.loc[~monthly["state_warmup"]].reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for cohort, start in enumerate(range(0, len(usable), 12)):
        part = usable.iloc[start : start + 12]
        complete = len(part) == 12
        candidate_valid = bool(
            complete
            and part.loc[part["state"].eq("strong/strong"), "top10_net_return"].notna().all()
        )
        baseline_valid = bool(complete and part["top10_net_return"].notna().all())
        candidate_returns = np.where(
            part["state"].eq("strong/strong"), part["top10_net_return"], 0.0
        )
        rows.append(
            {
                "cohort": cohort,
                "start": part["month"].min() if len(part) else pd.NaT,
                "end": part["month"].max() if len(part) else pd.NaT,
                "months": int(len(part)),
                "complete_12m": complete,
                "candidate_valid": candidate_valid,
                "baseline_valid": baseline_valid,
                "strong_strong_months": int(part["state"].eq("strong/strong").sum()),
                "candidate_net_return": float(np.prod(1.0 + candidate_returns) - 1.0) if candidate_valid else math.nan,
                "baseline_net_return": float((1.0 + part["top10_net_return"]).prod() - 1.0) if baseline_valid else math.nan,
            }
        )
    return pd.DataFrame(rows)


def _bootstrap(monthly: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows: list[dict[str, Any]] = []
    usable = monthly.loc[~monthly["state_warmup"]].dropna(subset=["top10_excess_return"])
    for state in ("all", "strong/strong", "strong/weak", "weak/strong", "weak/weak"):
        values = usable["top10_excess_return"].to_numpy()
        if state != "all":
            values = usable.loc[usable["state"].eq(state), "top10_excess_return"].to_numpy()
        if len(values) == 0:
            continue
        draws = rng.choice(values, size=(BOOTSTRAP_DRAWS, len(values)), replace=True).mean(axis=1)
        for quantile in (0.05, 0.50, 0.95):
            rows.append(
                {
                    "state": state,
                    "draws": BOOTSTRAP_DRAWS,
                    "sample_months": int(len(values)),
                    "quantile": quantile,
                    "mean_monthly_excess": float(np.quantile(draws, quantile)),
                }
            )
    return pd.DataFrame(rows)


def _monthly_mdd(returns: pd.Series) -> float:
    equity = (1.0 + returns).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def _post_reveal_state_ablation(monthly: pd.DataFrame) -> pd.DataFrame:
    usable = monthly.loc[
        ~monthly["state_warmup"] & monthly["top10_price_net_of_trading_cost"].notna()
    ].copy()
    returns = usable["top10_price_net_of_trading_cost"]
    positive_total = float(returns.clip(lower=0).sum())
    tail_cut = float(returns.quantile(0.90))
    tail = usable.loc[returns.ge(tail_cut)]
    tail_total = float(tail["top10_price_net_of_trading_cost"].sum())
    variants = {
        "baseline_all_months": pd.Series(True, index=usable.index),
        "money_effect_strong": usable["money_effect_strong"],
        "leader_continuation_strong": usable["leader_continuation_strong"],
        "strong_strong": usable["state"].eq("strong/strong"),
    }
    rows: list[dict[str, Any]] = []
    for variant, active in variants.items():
        strategy_returns = returns.where(active, 0.0)
        active_rows = usable.loc[active]
        active_tail = tail.loc[tail.index.intersection(active_rows.index)]
        rows.append(
            {
                "diagnostic_status": "post_reveal_ablation_not_selection",
                "variant": variant,
                "months": int(len(usable)),
                "active_months": int(active.sum()),
                "compound_price_net_of_trading_cost": float((1.0 + strategy_returns).prod() - 1.0),
                "monthly_max_drawdown": _monthly_mdd(strategy_returns),
                "mean_active_price_net_of_trading_cost": float(active_rows["top10_price_net_of_trading_cost"].mean()),
                "mean_active_excess_return": float(active_rows["top10_excess_return"].mean()),
                "active_selection_win_rate": float(active_rows["top10_excess_return"].gt(0).mean()),
                "positive_price_pnl_capture": float(active_rows["top10_price_net_of_trading_cost"].clip(lower=0).sum()) / positive_total,
                "right_tail_price_pnl_capture": float(active_tail["top10_price_net_of_trading_cost"].sum()) / tail_total,
            }
        )
    return pd.DataFrame(rows)


def _post_reveal_feature_rankic(monthly: pd.DataFrame) -> pd.DataFrame:
    features = [
        "breadth_positive_1m",
        "market_median_1m",
        "liquidity_participation",
        "leader_spread_1m",
        "leader_3m_rank_pct",
        "rank_alignment_1m_3m",
        "top10_funding_minus_market_30d",
        "top10_vol_ratio_30d",
    ]
    rows: list[dict[str, Any]] = []
    for feature in features:
        sample = monthly[[feature, "top10_price_return", "top10_excess_return"]].dropna()
        rows.append(
            {
                "diagnostic_status": "post_reveal_rankic_not_selection",
                "feature": feature,
                "months": int(len(sample)),
                "spearman_vs_next_month_top10": float(
                    sample[feature].corr(sample["top10_price_return"], method="spearman")
                ),
                "spearman_vs_next_month_excess": float(
                    sample[feature].corr(sample["top10_excess_return"], method="spearman")
                ),
            }
        )
    return pd.DataFrame(rows)


def _self_test() -> None:
    frame = pd.DataFrame(
        {
            "month": pd.date_range("2020-01-01", periods=14, freq="MS"),
            "breadth_positive_1m": np.arange(14, dtype=float),
            "market_median_1m": np.ones(14),
            "liquidity_participation": np.arange(14, dtype=float),
            "leader_spread_1m": np.arange(14, dtype=float),
            "leader_3m_rank_pct": np.arange(14, dtype=float),
            "rank_alignment_1m_3m": np.arange(14, dtype=float),
            "top10_funding_minus_market_30d": np.zeros(14),
            "top10_vol_ratio_30d": np.ones(14),
            "top10_net_return": np.ones(14) * 0.01,
        }
    )
    result = _apply_causal_states(frame)
    assert result.loc[11, "state_warmup"]
    assert not result.loc[12, "state_warmup"]
    assert result.loc[12, "breadth_positive_1m_threshold"] == np.median(np.arange(12))
    assert result.loc[12, "state"] == "strong/strong"
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return

    close, _, bars, quote, funding_daily, bases, cache_meta, audit = long10.load_inputs()
    bars_0015 = _load_daily_0015()
    open_0015, valid_0015 = _panels_0015(bars_0015, close.columns)
    funding_monthly = _load_monthly_funding()
    funding_indexed = funding_monthly.set_index(["holding_month", "sym_key"])

    monthly_rows: list[dict[str, Any]] = []
    decay_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    blocker_rows: list[dict[str, Any]] = []
    for month_start in pd.date_range(EVALUATION_START, LAST_ENTRY, freq="MS"):
        signal = _month_signal(month_start, close, bars, quote, bases)
        if signal is None or month_start not in valid_0015.index:
            blocker_rows.append({"month": month_start, "stage": "signal", "event": "missing_signal_or_entry_day"})
            continue
        entry_valid = valid_0015.loc[month_start]
        eligible_entry = signal["eligible"] & entry_valid.reindex(close.columns, fill_value=False)
        ordered = _ordered_symbols(signal["formation_1m"], signal["adv"], eligible_entry)
        top10 = ordered[:10]
        if len(top10) < 10:
            blocker_rows.append({"month": month_start, "stage": "entry", "event": "fewer_than_10_entry_valid"})
            continue
        features = _feature_values(signal, top10, quote, close, funding_daily)
        next_start = month_start + pd.offsets.MonthBegin(1)
        top_return, top_exit_coverage, top_exit_count = _cross_section_return(
            top10, month_start, next_start, open_0015, valid_0015, require_all=True
        )
        benchmark_names = eligible_entry.index[eligible_entry].astype(str).tolist()
        market_return, market_exit_coverage, market_exit_count = _cross_section_return(
            benchmark_names, month_start, next_start, open_0015, valid_0015, require_all=False
        )
        funding_pnl, funding_coverage, funding_missing = _funding_for_top10(
            month_start, top10, funding_indexed
        )
        if top_return is None:
            invalid = [symbol for symbol in top10 if not bool(valid_0015.at[next_start, symbol])]
            for symbol in invalid:
                blocker_rows.append(
                    {"month": month_start, "stage": "exit", "event": "invalid_top10_exit", "symbol": symbol}
                )
        if funding_missing:
            blocker_rows.append(
                {
                    "month": month_start,
                    "stage": "funding",
                    "event": "incomplete_top10_funding",
                    "count": funding_missing,
                }
            )
        top_excess = top_return - market_return if top_return is not None and market_return is not None else None
        net_return = (
            top_return + funding_pnl - ROUND_TRIP_COST
            if top_return is not None and funding_pnl is not None
            else None
        )
        monthly_rows.append(
            {
                "month": month_start,
                "signal_end_day": signal["signal_end_day"],
                "eligible_count": int(signal["eligible"].sum()),
                "entry_valid_eligible_count": int(eligible_entry.sum()),
                "top10": ",".join(top10),
                "top10_mean_formation_1m": float(signal["formation_1m"].reindex(top10).mean()),
                **features,
                "top10_price_return": top_return,
                "market_price_return": market_return,
                "top10_excess_return": top_excess,
                "top10_price_net_of_trading_cost": top_return - ROUND_TRIP_COST if top_return is not None else None,
                "top10_funding_pnl": funding_pnl,
                "top10_net_return": net_return,
                "round_trip_cost": ROUND_TRIP_COST,
                "top10_exit_coverage": top_exit_coverage,
                "top10_exit_count": top_exit_count,
                "market_exit_coverage": market_exit_coverage,
                "market_exit_count": market_exit_count,
                "funding_coverage": funding_coverage,
                "funding_missing_symbols": funding_missing,
            }
        )
        for rank, symbol in enumerate(top10, 1):
            holding_rows.append(
                {
                    "month": month_start,
                    "rank": rank,
                    "symbol": symbol,
                    "formation_1m": float(signal["formation_1m"].at[symbol]),
                    "formation_3m": float(signal["formation_3m"].at[symbol]) if pd.notna(signal["formation_3m"].at[symbol]) else None,
                    "adv_30d_usdt": float(signal["adv"].at[symbol]),
                    "entry_open_0015": float(open_0015.at[month_start, symbol]),
                    "exit_open_0015": float(open_0015.at[next_start, symbol]) if bool(valid_0015.at[next_start, symbol]) else None,
                }
            )
        for horizon, days in HORIZONS.items():
            end_day = month_start + pd.Timedelta(days=days)
            top_h, top_cov, _ = _cross_section_return(
                top10, month_start, end_day, open_0015, valid_0015, require_all=True
            )
            market_h, market_cov, _ = _cross_section_return(
                benchmark_names, month_start, end_day, open_0015, valid_0015, require_all=False
            )
            decay_rows.append(
                {
                    "month": month_start,
                    "horizon": horizon,
                    "end_day": end_day,
                    "top10_return": top_h,
                    "market_return": market_h,
                    "top10_coverage": top_cov,
                    "market_coverage": market_cov,
                }
            )
        decay_rows.append(
            {
                "month": month_start,
                "horizon": "1m",
                "end_day": next_start,
                "top10_return": top_return,
                "market_return": market_return,
                "top10_coverage": top_exit_coverage,
                "market_coverage": market_exit_coverage,
            }
        )

    monthly = _apply_causal_states(pd.DataFrame(monthly_rows))
    feature_conditionals = _feature_conditionals(monthly)
    state_2x2 = _state_table(monthly)
    continuation_decay = _decay_table(pd.DataFrame(decay_rows), monthly)
    cohorts = _cohorts(monthly)
    bootstrap = _bootstrap(monthly)
    post_reveal_state_ablation = _post_reveal_state_ablation(monthly)
    post_reveal_feature_rankic = _post_reveal_feature_rankic(monthly)

    usable = monthly.loc[~monthly["state_warmup"]].copy()
    valid_net = usable.dropna(subset=["top10_net_return"])
    strong_strong = state_2x2.loc[state_2x2["state"].eq("strong/strong")].iloc[0]
    overall_stats = _stats(usable)
    complete_cohorts = cohorts.loc[cohorts["complete_12m"] & cohorts["candidate_valid"]]
    cohort_positive_rate = float(complete_cohorts["candidate_net_return"].gt(0).mean()) if len(complete_cohorts) else math.nan
    checks = {
        "strong_strong_excess_gt_all": bool(strong_strong["mean_top10_excess_return"] > overall_stats["mean_top10_excess_return"]),
        "strong_strong_selection_win_rate_gte_55pct": bool(strong_strong["selection_win_rate"] >= 0.55),
        "positive_net_pnl_capture_gte_80pct": bool(strong_strong["positive_net_pnl_capture"] >= 0.80),
        "right_tail_net_pnl_capture_gte_80pct": bool(strong_strong["right_tail_net_pnl_capture"] >= 0.80),
        "complete_12m_candidate_positive_rate_gt_50pct": bool(cohort_positive_rate > 0.50),
        "state_thresholds_causal": True,
    }
    stem = f"binance-1d-mcsm-money-effect-continuation-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "contract": SPEC,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "data": {
            "evaluation_start": str(EVALUATION_START.date()),
            "last_entry": str(LAST_ENTRY.date()),
            "monthly_rows": int(len(monthly)),
            "state_usable_rows": int((~monthly["state_warmup"]).sum()),
            "valid_net_rows": int(len(valid_net)),
            "ohlcv_0015_rows": int(len(bars_0015)),
            "funding_month_rows": int(len(funding_monthly)),
        },
        "overall": overall_stats,
        "state_2x2": state_2x2.to_dict(orient="records"),
        "post_reveal_diagnostics": {
            "status": "diagnostic-only / not eligible for selection",
            "state_ablation": post_reveal_state_ablation.to_dict(orient="records"),
            "feature_rankic": post_reveal_feature_rankic.to_dict(orient="records"),
        },
        "acceptance": {
            "checks": checks,
            "all_reference_lines_pass": bool(all(checks.values())),
            "complete_12m_candidate_positive_rate": cohort_positive_rate,
            "complete_12m_candidate_cohorts": int(len(complete_cohorts)),
        },
        "status": "diagnostic-only / not promoted / not live-ready",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-monthly-state-labels.csv", monthly, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-feature-conditionals.csv", feature_conditionals, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-state-2x2.csv", state_2x2, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-continuation-decay.csv", continuation_decay, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-cohorts-12m.csv", cohorts, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-bootstrap.csv", bootstrap, force=args.force)
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-state-ablation-post-reveal.csv",
        post_reveal_state_ablation,
        force=args.force,
    )
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-feature-rankic-post-reveal.csv",
        post_reveal_feature_rankic,
        force=args.force,
    )
    base.write_csv(ARTIFACT_DIR / f"{stem}-top10-holdings.csv", pd.DataFrame(holding_rows), force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-blockers.csv", pd.DataFrame(blocker_rows), force=args.force)
    print(
        json.dumps(
            {
                "overall": overall_stats,
                "state_2x2": summary["state_2x2"],
                "acceptance": summary["acceptance"],
                "blockers": (
                    pd.DataFrame(blocker_rows)
                    .groupby(["stage", "event"])
                    .size()
                    .rename("count")
                    .reset_index()
                    .to_dict(orient="records")
                    if blocker_rows
                    else []
                ),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
