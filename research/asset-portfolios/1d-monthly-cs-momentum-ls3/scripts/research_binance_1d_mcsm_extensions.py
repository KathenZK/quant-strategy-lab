#!/usr/bin/env python3
"""Run breadth, formation, sizing, short-filter, benchmark, and attribution diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_binance_1d_mcsm_ls3 as base


ROOT = base.ROOT
FAMILY_DIR = base.FAMILY_DIR
ARTIFACT_DIR = base.ARTIFACT_DIR
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0004
ASSET_VOL_WINDOW = 30
ASSET_VOL_MIN_PERIODS = 20
PORTFOLIO_VOL_WINDOW = 90
PORTFOLIO_VOL_MIN_PERIODS = 60
PORTFOLIO_VOL_TARGET = 0.20
PORTFOLIO_SCALE_MIN = 0.10
PORTFOLIO_SCALE_MAX = 1.50
SHORT_MIN_LISTING_DAYS = 180
SHORT_MAX_ANN_VOL = 1.50
COMMON_COMPARISON_START = pd.Timestamp("2021-03-01")
EVALUATION_START = pd.Timestamp("2020-03-01")


@dataclass(frozen=True)
class Variant:
    id: str
    label: str
    group: str
    universe: str = "all_listed"
    formation_months: int = 1
    skip_months: int = 0
    selection: str = "top_n"
    n_legs: int | None = 3
    quantile: float | None = None
    long_band: tuple[float, float] | None = None
    short_band: tuple[float, float] | None = None
    reverse: bool = False
    long_only: bool = False
    inverse_vol: bool = False
    portfolio_vol_target: float | None = None
    short_filter: str | None = None
    fixed_symbol: str | None = None
    forced_start: str | None = None


def variants() -> list[Variant]:
    items = [
        Variant("all_top3_long_only", "全上市 Top3 long-only", "long_only", long_only=True),
        Variant("adv10m_top3_long_only", "ADV≥1000万 Top3 long-only", "long_only", universe="adv10m", long_only=True),
        Variant("btc_perp_long", "BTC 永续 long-only", "benchmark", selection="fixed", fixed_symbol="BTC", long_only=True, forced_start="2020-03-01"),
        Variant("eth_perp_long", "ETH 永续 long-only", "benchmark", selection="fixed", fixed_symbol="ETH", long_only=True, forced_start="2020-03-01"),
        Variant("all_market_equal_weight", "全上市合资格合约月度等权", "benchmark", selection="all_equal", long_only=True, forced_start="2020-03-01"),
        Variant("all_top3_bottom3", "全上市 Top3/Bottom3 原策略", "attribution"),
        Variant("all_reverse_top3_bottom3", "全上市 Bottom3/Top3 reverse", "attribution", reverse=True),
    ]
    for universe, universe_label in (("all_listed", "全上市"), ("adv10m", "ADV≥1000万")):
        for n_legs in (10, 20):
            items.append(
                Variant(
                    f"{universe}_top{n_legs}_bottom{n_legs}",
                    f"{universe_label} Top{n_legs}/Bottom{n_legs}",
                    "breadth",
                    universe=universe,
                    n_legs=n_legs,
                )
            )
        items.append(
            Variant(
                f"{universe}_top10pct_bottom10pct",
                f"{universe_label} Top10%/Bottom10%",
                "breadth",
                universe=universe,
                selection="quantile",
                quantile=0.10,
                n_legs=None,
            )
        )
        items.append(
            Variant(
                f"{universe}_trimmed_11_30_71_90",
                f"{universe_label} Long 11–30% / Short 71–90%",
                "tail_trim",
                universe=universe,
                selection="bands",
                long_band=(0.10, 0.30),
                short_band=(0.70, 0.90),
                n_legs=None,
            )
        )
        for months in (1, 3, 6, 12):
            items.append(
                Variant(
                    f"{universe}_formation_{months}m_top10_bottom10",
                    f"{universe_label} {months}M Top10/Bottom10",
                    "formation",
                    universe=universe,
                    formation_months=months,
                    n_legs=10,
                )
            )
        items.append(
            Variant(
                f"{universe}_formation_12_1m_top10_bottom10",
                f"{universe_label} 12-1M Top10/Bottom10",
                "formation",
                universe=universe,
                formation_months=11,
                skip_months=1,
                n_legs=10,
            )
        )
    items.extend(
        [
            Variant(
                "adv10m_top10_bottom10_inverse_vol",
                "ADV≥1000万 Top10/Bottom10 inverse-vol",
                "risk_sizing",
                universe="adv10m",
                n_legs=10,
                inverse_vol=True,
            ),
            Variant(
                "adv10m_top10_bottom10_inverse_vol_target20",
                "ADV≥1000万 Top10/Bottom10 inverse-vol + 20%组合目标波动",
                "risk_sizing",
                universe="adv10m",
                n_legs=10,
                inverse_vol=True,
                portfolio_vol_target=PORTFOLIO_VOL_TARGET,
            ),
            Variant(
                "adv10m_top10_bottom10_short_age180",
                "ADV≥1000万 Top10/Bottom10 + short上市≥180天",
                "short_constraint",
                universe="adv10m",
                n_legs=10,
                short_filter="age",
            ),
            Variant(
                "adv10m_top10_bottom10_short_vol150",
                "ADV≥1000万 Top10/Bottom10 + short波动≤150%",
                "short_constraint",
                universe="adv10m",
                n_legs=10,
                short_filter="vol",
            ),
            Variant(
                "adv10m_top10_bottom10_short_constrained",
                "ADV≥1000万 Top10/Bottom10 + short约束",
                "short_constraint",
                universe="adv10m",
                n_legs=10,
                short_filter="combined",
            ),
            Variant(
                "all_listed_top10_bottom10_short_constrained",
                "全上市 Top10 + short上市/ADV/波动约束",
                "short_constraint",
                universe="all_listed",
                n_legs=10,
                short_filter="combined",
            ),
        ]
    )
    seen = set()
    return [item for item in items if not (item.id in seen or seen.add(item.id))]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def _last_day(frame: pd.DataFrame, month: pd.Period) -> pd.Timestamp | None:
    days = frame.index[(frame.index.to_period("M") == month) & frame.notna().any(axis=1)]
    return days.max() if len(days) else None


def _signal(
    close: pd.DataFrame,
    month_start: pd.Timestamp,
    formation_months: int,
    skip_months: int,
) -> tuple[pd.Series, pd.Period, pd.Period, pd.Timestamp, pd.Timestamp] | None:
    trade_month = month_start.to_period("M")
    end_month = trade_month - 1 - skip_months
    start_month = end_month - formation_months
    if start_month < base.ARCHIVE_START or end_month > base.ARCHIVE_END:
        return None
    end_day = _last_day(close, end_month)
    start_day = _last_day(close, start_month)
    if end_day is None or start_day is None:
        return None
    formation = close.loc[end_day] / close.loc[start_day] - 1.0
    return formation, start_month, end_month, start_day, end_day


def _band(ordered: list[str], bounds: tuple[float, float]) -> list[str]:
    n = len(ordered)
    start = int(math.floor(bounds[0] * n))
    stop = int(math.ceil(bounds[1] * n))
    return ordered[start:stop]


def _pick(
    variant: Variant,
    formation: pd.Series,
    long_eligible: pd.Series,
    short_eligible: pd.Series,
    adv: pd.Series,
    has_open: pd.Series,
) -> tuple[list[str], list[str]] | None:
    finite = formation.notna() & np.isfinite(formation)
    long_pool = formation.loc[finite & long_eligible]
    short_pool = formation.loc[finite & short_eligible]
    long_order_all = (
        pd.DataFrame({"signal": long_pool, "adv": adv.reindex(long_pool.index).fillna(-1.0)})
        .sort_values(["signal", "adv"], ascending=[False, False])
        .index.astype(str)
        .tolist()
    )
    short_strength_order = (
        pd.DataFrame({"signal": short_pool, "adv": adv.reindex(short_pool.index).fillna(-1.0)})
        .sort_values(["signal", "adv"], ascending=[False, False])
        .index.astype(str)
        .tolist()
    )
    long_order = [symbol for symbol in long_order_all if bool(has_open.get(symbol, False))]
    # Match the frozen engine exactly: reverse the complete descending order,
    # then skip symbols without a rebalance-day open.
    short_order = [symbol for symbol in reversed(short_strength_order) if bool(has_open.get(symbol, False))]
    if variant.selection == "all_equal":
        return (long_order, []) if long_order else None
    if variant.selection == "top_n":
        n = int(variant.n_legs or 0)
        longs = long_order[:n]
        shorts = [symbol for symbol in short_order if symbol not in longs][:n]
    elif variant.selection == "quantile":
        n_long = max(1, int(math.ceil(float(variant.quantile) * len(long_order))))
        n_short = max(1, int(math.ceil(float(variant.quantile) * len(short_order))))
        longs = long_order[:n_long]
        shorts = [symbol for symbol in short_order if symbol not in longs][:n_short]
    elif variant.selection == "bands":
        longs = _band(long_order, variant.long_band or (0.10, 0.30))
        # short_order is weakest-to-strongest; reverse it so both percentile bands use strength rank.
        strength_short_order = list(reversed(short_order))
        shorts = [symbol for symbol in _band(strength_short_order, variant.short_band or (0.70, 0.90)) if symbol not in longs]
    else:
        raise ValueError(f"unknown selection: {variant.selection}")
    if not longs or (not variant.long_only and not shorts):
        return None
    if variant.n_legs is not None and (len(longs) < variant.n_legs or (not variant.long_only and len(shorts) < variant.n_legs)):
        return None
    if variant.reverse:
        longs, shorts = shorts, longs
    return longs, ([] if variant.long_only else shorts)


def _leg_weights(symbols: list[str], gross: float, vol: pd.Series | None) -> pd.Series:
    if not symbols:
        return pd.Series(dtype="float64")
    if vol is None:
        raw = pd.Series(1.0, index=symbols)
    else:
        clean = vol.reindex(symbols).replace([np.inf, -np.inf, 0.0], np.nan)
        if clean.isna().any():
            return pd.Series(dtype="float64")
        raw = 1.0 / clean
    return gross * raw / raw.sum()


def _performance(net: pd.Series) -> dict[str, Any]:
    result = base.performance(net)
    equity = (1.0 + net.fillna(0.0)).cumprod()
    result["min_daily_return"] = float(net.min())
    result["nonpositive_equity_days"] = int((equity <= 0.0).sum())
    return result


def _simulate(
    variant: Variant,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any]:
    columns = close.columns
    excluded = base.excluded_mask(columns, bases)
    adv = quote.rolling(base.ADV_WINDOW, min_periods=base.ADV_WINDOW).mean()
    daily_asset_vol = close.pct_change(fill_method=None).rolling(
        ASSET_VOL_WINDOW, min_periods=ASSET_VOL_MIN_PERIODS
    ).std(ddof=0) * math.sqrt(base.ANNUALIZER)
    first_valid = {symbol: close[symbol].first_valid_index() for symbol in columns}
    weights = pd.DataFrame(0.0, index=close.index, columns=columns)
    holdings: list[dict[str, Any]] = []
    for month_start in base.month_starts(close.index):
        if month_start not in close.index:
            continue
        if month_start < EVALUATION_START:
            continue
        if variant.forced_start and month_start < pd.Timestamp(variant.forced_start):
            continue
        hold_end = (month_start + pd.offsets.MonthBegin(1)) - pd.Timedelta(days=1)
        hold_index = close.index[(close.index >= month_start) & (close.index <= hold_end)]
        if hold_index.empty:
            continue
        has_open = open_.loc[month_start].notna()
        if variant.selection == "fixed":
            symbol = str(variant.fixed_symbol)
            picked = ([symbol], []) if bool(has_open.get(symbol, False)) else None
            signal_meta = None
            eligible_count = 1 if picked else 0
            formation = pd.Series(np.nan, index=columns)
            signal_end_day = month_start - pd.Timedelta(days=1)
        else:
            signal_meta = _signal(close, month_start, variant.formation_months, variant.skip_months)
            if signal_meta is None:
                continue
            formation, _, end_month, start_day, signal_end_day = signal_meta
            coverage = base.coverage_in_month(bars, end_month)
            endpoint_ok = (
                close.loc[start_day].notna()
                & close.loc[signal_end_day].notna()
                & bars.loc[start_day].ge(base.MIN_ENDPOINT_BARS)
                & bars.loc[signal_end_day].ge(base.MIN_ENDPOINT_BARS)
            )
            eligible = (~excluded) & endpoint_ok & coverage.ge(base.MIN_COVERAGE) & formation.notna()
            if variant.universe == "adv10m":
                eligible &= adv.loc[signal_end_day].ge(base.MIN_ADV_USDT)
            long_eligible = eligible.copy()
            short_eligible = eligible.copy()
            if variant.short_filter:
                ages = pd.Series(
                    {
                        symbol: ((signal_end_day - first_valid[symbol]).days + 1) if first_valid[symbol] is not None else 0
                        for symbol in columns
                    }
                )
                if variant.short_filter in {"age", "combined"}:
                    short_eligible &= ages.reindex(columns).ge(SHORT_MIN_LISTING_DAYS)
                if variant.short_filter == "combined":
                    short_eligible &= adv.loc[signal_end_day].ge(base.MIN_ADV_USDT)
                if variant.short_filter in {"vol", "combined"}:
                    short_eligible &= daily_asset_vol.loc[signal_end_day].le(SHORT_MAX_ANN_VOL)
            eligible_count = int(eligible.sum())
            picked = _pick(variant, formation, long_eligible, short_eligible, adv.loc[signal_end_day], has_open)
        if picked is None:
            holdings.append({"variant": variant.id, "rebalance": str(month_start.date()), "status": "flat", "eligible": eligible_count})
            continue
        longs, shorts = picked
        vol = daily_asset_vol.loc[signal_end_day] if variant.inverse_vol else None
        long_w = _leg_weights(longs, 1.0, vol)
        short_w = _leg_weights(shorts, -1.0, vol)
        if long_w.empty or (shorts and short_w.empty):
            holdings.append({"variant": variant.id, "rebalance": str(month_start.date()), "status": "flat_bad_vol", "eligible": eligible_count})
            continue
        month_weights = pd.Series(0.0, index=columns)
        month_weights.loc[long_w.index] = long_w
        if len(short_w):
            month_weights.loc[short_w.index] = short_w
        weights.loc[hold_index] = month_weights.to_numpy()
        holdings.append(
            {
                "variant": variant.id,
                "rebalance": str(month_start.date()),
                "status": "traded",
                "eligible": eligible_count,
                "n_longs": len(longs),
                "n_shorts": len(shorts),
                "longs": ",".join(longs),
                "shorts": ",".join(shorts),
                "mean_long_formation": float(formation.reindex(longs).mean()) if variant.selection != "fixed" else None,
                "mean_short_formation": float(formation.reindex(shorts).mean()) if shorts else None,
            }
        )

    def price_returns(weight_frame: pd.DataFrame) -> pd.Series:
        w_bod_local = weight_frame.shift(1).fillna(0.0)
        changed = (weight_frame - w_bod_local).abs().sum(axis=1).gt(1e-14)
        regular = (w_bod_local * (close / close.shift(1) - 1.0).fillna(0.0)).sum(axis=1)
        split = (
            w_bod_local * (open_ / close.shift(1) - 1.0).fillna(0.0)
            + weight_frame * (close / open_ - 1.0).fillna(0.0)
        ).sum(axis=1)
        return regular.where(~changed, split)

    if variant.portfolio_vol_target is not None:
        base_price = price_returns(weights)
        realized = base_price.shift(1).rolling(PORTFOLIO_VOL_WINDOW, min_periods=PORTFOLIO_VOL_MIN_PERIODS).std(ddof=0) * math.sqrt(base.ANNUALIZER)
        for month_start in base.month_starts(close.index):
            if month_start not in weights.index:
                continue
            prior_days = realized.index[realized.index < month_start]
            scalar = 1.0
            if len(prior_days):
                observed = realized.loc[prior_days.max()]
                if pd.notna(observed) and observed > 0:
                    scalar = float(np.clip(variant.portfolio_vol_target / observed, PORTFOLIO_SCALE_MIN, PORTFOLIO_SCALE_MAX))
                else:
                    # Cold start: use a conservative perfect-correlation upper bound from
                    # constituent volatilities known before the rebalance.
                    signal_day = prior_days.max()
                    month_weight = weights.loc[month_start]
                    proxy = float((month_weight.abs() * daily_asset_vol.loc[signal_day].fillna(0.0)).sum())
                    if proxy > 0:
                        scalar = float(np.clip(variant.portfolio_vol_target / proxy, PORTFOLIO_SCALE_MIN, PORTFOLIO_SCALE_MAX))
            hold_end = (month_start + pd.offsets.MonthBegin(1)) - pd.Timedelta(days=1)
            hold_index = weights.index[(weights.index >= month_start) & (weights.index <= hold_end)]
            weights.loc[hold_index] *= scalar
            for row in holdings:
                if row["rebalance"] == str(month_start.date()) and row["status"] == "traded":
                    row["portfolio_scale"] = scalar

    w_bod = weights.shift(1).fillna(0.0)
    price = price_returns(weights)
    long_weights = weights.clip(lower=0.0)
    short_weights = weights.clip(upper=0.0)
    long_price = price_returns(long_weights)
    short_price = price_returns(short_weights)
    turnover = (weights - w_bod).abs().sum(axis=1)
    long_turnover = (long_weights - long_weights.shift(1).fillna(0.0)).abs().sum(axis=1)
    short_turnover = (short_weights - short_weights.shift(1).fillna(0.0)).abs().sum(axis=1)
    last_day = close.index.max()
    turnover.loc[last_day] += weights.loc[last_day].abs().sum()
    long_turnover.loc[last_day] += long_weights.loc[last_day].abs().sum()
    short_turnover.loc[last_day] += short_weights.loc[last_day].abs().sum()
    funding_aligned = funding.reindex_like(weights)
    funding_pnl = -(weights * funding_aligned.fillna(0.0)).sum(axis=1)
    long_funding = -(long_weights * funding_aligned.fillna(0.0)).sum(axis=1)
    short_funding = -(short_weights * funding_aligned.fillna(0.0)).sum(axis=1)
    fee = turnover * FEE_RATE
    slippage = turnover * SLIPPAGE_RATE
    long_fee = long_turnover * FEE_RATE
    short_fee = short_turnover * FEE_RATE
    long_slippage = long_turnover * SLIPPAGE_RATE
    short_slippage = short_turnover * SLIPPAGE_RATE
    net = price + funding_pnl - fee - slippage
    long_net = long_price + long_funding - long_fee - long_slippage
    short_net = short_price + short_funding - short_fee - short_slippage
    traded_dates = [pd.Timestamp(row["rebalance"]) for row in holdings if row["status"] == "traded"]
    active_start = min(traded_dates) if traded_dates else close.index.max()
    series = {
        "net": net.loc[active_start:],
        "price": price.loc[active_start:],
        "funding": funding_pnl.loc[active_start:],
        "fee": fee.loc[active_start:],
        "slippage": slippage.loc[active_start:],
        "turnover": turnover.loc[active_start:],
        "long_net": long_net.loc[active_start:],
        "short_net": short_net.loc[active_start:],
        "long_price": long_price.loc[active_start:],
        "short_price": short_price.loc[active_start:],
    }
    held = weights.loc[active_start:].abs().gt(0.0)
    funding_coverage = float((held & funding_aligned.loc[active_start:].notna()).to_numpy().sum() / max(int(held.to_numpy().sum()), 1))
    metrics = _performance(series["net"])
    common_net = series["net"].loc[series["net"].index >= COMMON_COMPARISON_START]
    common = _performance(common_net) if len(common_net) else {}
    long_metrics = _performance(series["long_net"])
    short_metrics = _performance(series["short_net"]) if weights.lt(0.0).any().any() else {}
    metrics.update(
        {
            "variant": variant.id,
            "label": variant.label,
            "group": variant.group,
            "universe": variant.universe,
            "formation_months": variant.formation_months,
            "skip_months": variant.skip_months,
            "n_rebalances": len(traded_dates),
            "funding_coverage": funding_coverage,
            "mean_gross_exposure": float(weights.loc[active_start:].abs().sum(axis=1).mean()),
            "max_gross_exposure": float(weights.loc[active_start:].abs().sum(axis=1).max()),
            "ann_turnover": float(series["turnover"].sum() * base.ANNUALIZER / max(len(series["net"]), 1)),
            "price_pnl_sum": float(series["price"].sum()),
            "funding_pnl_sum": float(series["funding"].sum()),
            "fee_pnl_sum": -float(series["fee"].sum()),
            "slippage_pnl_sum": -float(series["slippage"].sum()),
            "arithmetic_total_pnl_sum": float(series["net"].sum()),
            "long_total_return": long_metrics.get("total_return"),
            "long_cagr": long_metrics.get("cagr"),
            "long_ann_vol": long_metrics.get("ann_vol"),
            "long_sharpe": long_metrics.get("sharpe"),
            "long_max_drawdown": long_metrics.get("max_drawdown"),
            "short_total_return": short_metrics.get("total_return"),
            "short_cagr": short_metrics.get("cagr"),
            "short_ann_vol": short_metrics.get("ann_vol"),
            "short_sharpe": short_metrics.get("sharpe"),
            "short_max_drawdown": short_metrics.get("max_drawdown"),
            "common_start": str(COMMON_COMPARISON_START.date()),
            "common_total_return": common.get("total_return"),
            "common_cagr": common.get("cagr"),
            "common_ann_vol": common.get("ann_vol"),
            "common_sharpe": common.get("sharpe"),
            "common_max_drawdown": common.get("max_drawdown"),
            "common_month_hit_rate": common.get("month_hit_rate"),
        }
    )
    daily = pd.DataFrame(
        {
            "variant": variant.id,
            "day": series["net"].index,
            "net_return": series["net"].to_numpy(),
            "price_pnl": series["price"].to_numpy(),
            "funding_pnl": series["funding"].to_numpy(),
            "fee": series["fee"].to_numpy(),
            "slippage": series["slippage"].to_numpy(),
            "turnover": series["turnover"].to_numpy(),
            "long_net": series["long_net"].to_numpy(),
            "short_net": series["short_net"].to_numpy(),
            "equity": (1.0 + series["net"]).cumprod().to_numpy(),
        }
    )
    return {"metrics": metrics, "daily": daily, "holdings": holdings}


def _self_test() -> None:
    ohlcv, funding_long, bases = base.make_synthetic_panel()
    close = base.pivot(ohlcv, "close")
    open_ = base.pivot(ohlcv, "open")
    bars = base.pivot(ohlcv, "bars_15m")
    quote = base.pivot(ohlcv, "quote_volume")
    funding = funding_long.pivot(index="day", columns="sym_key", values="funding_rate")
    variant = Variant("test", "test", "test", universe="adv10m", n_legs=3)
    result = _simulate(variant, close, open_, bars, quote, funding, bases)
    march = next(row for row in result["holdings"] if row["rebalance"] == "2021-03-01")
    assert set(march["longs"].split(",")) == {"AAA", "BBB", "CCC"}, march
    assert set(march["shorts"].split(",")) == {"XXX", "YYY", "ZZZ"}, march
    assert math.isclose(
        result["metrics"]["arithmetic_total_pnl_sum"],
        result["metrics"]["price_pnl_sum"] + result["metrics"]["funding_pnl_sum"] + result["metrics"]["fee_pnl_sum"] + result["metrics"]["slippage_pnl_sum"],
        abs_tol=1e-12,
    )
    print("self-test ok")


def _price_only_benchmark(symbol: str, close: pd.DataFrame) -> dict[str, Any]:
    px = close.loc[close.index >= pd.Timestamp("2020-03-01"), symbol].dropna()
    net = px.pct_change(fill_method=None).fillna(0.0)
    metrics = _performance(net)
    common = _performance(net.loc[net.index >= COMMON_COMPARISON_START])
    metrics.update(
        {
            "variant": f"{symbol.lower()}_price_buy_hold",
            "label": f"{symbol} 价格 buy-and-hold（无资金费/交易成本）",
            "group": "benchmark",
            "universe": "fixed_symbol",
            "n_rebalances": 1,
            "price_pnl_sum": float(net.sum()),
            "funding_pnl_sum": 0.0,
            "fee_pnl_sum": 0.0,
            "slippage_pnl_sum": 0.0,
            "arithmetic_total_pnl_sum": float(net.sum()),
            "common_start": str(COMMON_COMPARISON_START.date()),
            "common_total_return": common.get("total_return"),
            "common_cagr": common.get("cagr"),
            "common_ann_vol": common.get("ann_vol"),
            "common_sharpe": common.get("sharpe"),
            "common_max_drawdown": common.get("max_drawdown"),
            "common_month_hit_rate": common.get("month_hit_rate"),
        }
    )
    daily = pd.DataFrame(
        {
            "variant": metrics["variant"],
            "day": net.index,
            "net_return": net.to_numpy(),
            "price_pnl": net.to_numpy(),
            "funding_pnl": 0.0,
            "fee": 0.0,
            "slippage": 0.0,
            "turnover": 0.0,
            "long_net": net.to_numpy(),
            "short_net": 0.0,
            "equity": (1.0 + net).cumprod().to_numpy(),
        }
    )
    return {"metrics": metrics, "daily": daily, "holdings": []}


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return
    cache_meta = base.ensure_daily_cache(rebuild=False)
    ohlcv, funding_long, bases = base.load_panel()
    audit = base.audit_panel(ohlcv, bases)
    audit["funding_rows"] = int(len(funding_long))
    close = base.pivot(ohlcv, "close")
    open_ = base.pivot(ohlcv, "open")
    bars = base.pivot(ohlcv, "bars_15m")
    quote = base.pivot(ohlcv, "quote_volume")
    full_index = pd.date_range(close.index.min(), close.index.max(), freq="D")
    close = close.reindex(full_index)
    open_ = open_.reindex(full_index)
    bars = bars.reindex(full_index)
    quote = quote.reindex(full_index)
    funding = funding_long.pivot(index="day", columns="sym_key", values="funding_rate").reindex(index=close.index, columns=close.columns)
    payloads = []
    for variant in variants():
        print(f"running {variant.id}", flush=True)
        payloads.append(_simulate(variant, close, open_, bars, quote, funding, bases))
    payloads.extend([_price_only_benchmark("BTC", close), _price_only_benchmark("ETH", close)])
    metrics = pd.DataFrame([payload["metrics"] for payload in payloads])
    daily = pd.concat([payload["daily"] for payload in payloads], ignore_index=True)
    holdings = pd.DataFrame([row for payload in payloads for row in payload["holdings"]])
    yearly_rows = []
    recent_rows = []
    for payload in payloads:
        variant_id = payload["metrics"]["variant"]
        net = payload["daily"].set_index("day")["net_return"]
        yearly = ((1.0 + net).resample("YE").prod() - 1.0).rename("net_return").reset_index()
        yearly["year"] = yearly["day"].dt.year
        yearly["variant"] = variant_id
        yearly_rows.append(yearly[["variant", "year", "net_return"]])
        recent_rows.extend({"variant": variant_id, **row} for row in base.recent_slices(net))
    yearly = pd.concat(yearly_rows, ignore_index=True)
    recent = pd.DataFrame(recent_rows)
    attribution = metrics.loc[
        metrics["variant"].isin(["all_top3_bottom3", "all_reverse_top3_bottom3"]),
        [
            "variant",
            "label",
            "price_pnl_sum",
            "funding_pnl_sum",
            "fee_pnl_sum",
            "slippage_pnl_sum",
            "arithmetic_total_pnl_sum",
            "total_return",
        ],
    ].copy()
    stem = f"binance-1d-mcsm-extensions-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baseline_script_sha256": hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "constants": {
            "fee_rate_per_side": FEE_RATE,
            "slippage_rate_per_side": SLIPPAGE_RATE,
            "asset_vol_window_days": ASSET_VOL_WINDOW,
            "portfolio_vol_window_days": PORTFOLIO_VOL_WINDOW,
            "portfolio_vol_target": PORTFOLIO_VOL_TARGET,
            "portfolio_scale_bounds": [PORTFOLIO_SCALE_MIN, PORTFOLIO_SCALE_MAX],
            "short_min_listing_days": SHORT_MIN_LISTING_DAYS,
            "short_min_adv_usdt": base.MIN_ADV_USDT,
            "short_max_ann_vol": SHORT_MAX_ANN_VOL,
            "common_comparison_start": str(COMMON_COMPARISON_START.date()),
            "evaluation_start": str(EVALUATION_START.date()),
        },
        "metrics": metrics.to_dict(orient="records"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-metrics.csv", metrics, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-holdings.csv", holdings, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-daily-paths.csv", daily, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-yearly.csv", yearly, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-recent-slices.csv", recent, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-attribution.csv", attribution, force=args.force)
    print(metrics[["variant", "total_return", "cagr", "ann_vol", "sharpe", "max_drawdown", "month_hit_rate"]].to_string(index=False))


if __name__ == "__main__":
    main()
