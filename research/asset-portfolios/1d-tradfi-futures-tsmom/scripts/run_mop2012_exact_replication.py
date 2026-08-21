#!/usr/bin/env python3
"""Audit published MOP (2012) factors and run the paper formula locally."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-tradfi-futures-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CORE_PATH = Path(__file__).with_name("run_tradfi_futures_tsmom.py")
EWMAC_PATH = (
    ROOT
    / "research/asset-portfolios/1d-classic-ewmac-replication/scripts"
    / "run_classic_ewmac_replication.py"
)
RUN_DATE_DEFAULT = datetime.now(UTC).date().isoformat()
SOURCE_DATE = "2026-08-19"
PREFIX = f"tf-1d-fut-tsmom-paper-exact-p1-{SOURCE_DATE}"
PAPER_TARGET_VOL = 0.40
VOL_COM = 60.0
VOL_MIN_PERIODS = 60
VOL_ANNUALIZER = 261
DAILY_ANNUALIZER = 261
FUTURES_START = pd.Timestamp("2022-01-03", tz="UTC")
PROXY_START = pd.Timestamp("2013-01-02", tz="UTC")
FUTURES_COSTS = (0.0, 2.0)
PROXY_COSTS = (0.0, 2.0, 10.0)
PRIMARY_COST = 2.0
STRATEGIES = ("mop_tsmom", "always_long")
LABELS = {"mop_tsmom": "MOP 12M TSMOM", "always_long": "Always-long control"}
FACTOR_LABELS = {
    "TSMOM": "Diversified",
    "TSMOM^EQ": "Equity indices",
    "TSMOM^FX": "Currencies",
    "TSMOM^FI": "Fixed income",
    "TSMOM^CM": "Commodities",
}
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=0),
    "7d": pd.Timedelta(days=6),
    "1m": pd.DateOffset(months=1),
    "3m": pd.DateOffset(months=3),
    "6m": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_module("mop2012_local_core", CORE_PATH)
EWMAC = load_module("mop2012_proxy_source", EWMAC_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=RUN_DATE_DEFAULT)
    parser.add_argument("--allow-untrusted", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compounded(returns: pd.Series) -> float:
    return float((1.0 + returns).prod() - 1.0)


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def paper_sigma(returns: pd.Series) -> pd.Series:
    """Paper Eq. (1): lag-free estimator used for the next return period."""
    mean = returns.ewm(
        com=VOL_COM, adjust=False, min_periods=VOL_MIN_PERIODS
    ).mean()
    second = returns.pow(2).ewm(
        com=VOL_COM, adjust=False, min_periods=VOL_MIN_PERIODS
    ).mean()
    variance = (second - mean.pow(2)).clip(lower=0.0)
    return (variance * VOL_ANNUALIZER).pow(0.5)


def market_features(
    frame: pd.DataFrame, cutoff: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = frame.loc[frame["ts"].le(cutoff), ["ts", "close"]].copy()
    daily["return"] = daily["close"].pct_change(fill_method=None)
    daily["sigma_ann"] = paper_sigma(daily["return"])
    daily["month"] = daily["ts"].dt.tz_localize(None).dt.to_period("M")
    monthly = daily.groupby("month", sort=True, as_index=False).tail(1).copy()
    monthly["return_12m"] = monthly["close"].pct_change(12, fill_method=None)
    monthly["forecast_12m"] = np.sign(monthly["return_12m"])
    monthly["forecast_always_long"] = 1.0
    return daily, monthly


def build_local_path(
    dates: pd.DatetimeIndex,
    returns: pd.DataFrame,
    monthly: dict[str, pd.DataFrame],
    universe: dict[str, dict[str, str]],
    strategy: str,
    evaluation_start: pd.Timestamp,
    costs: tuple[float, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    forecast_column = (
        "forecast_12m" if strategy == "mop_tsmom" else "forecast_always_long"
    )
    raw_targets = pd.DataFrame(index=dates)
    for symbol, events in monthly.items():
        target = events[forecast_column] * PAPER_TARGET_VOL / events["sigma_ann"]
        announcements = pd.Series(
            target.to_numpy(), index=pd.DatetimeIndex(events["ts"])
        )
        raw_targets[symbol] = announcements.reindex(dates).ffill().shift(1)
    active_count = raw_targets.notna().sum(axis=1).replace(0, np.nan)
    positions = raw_targets.div(active_count, axis=0).fillna(0.0)
    turnover_by_market = positions.diff().fillna(positions.abs()).abs()
    gross_by_market = positions * returns.fillna(0.0)
    start_mask = dates >= evaluation_start
    positions = positions.loc[start_mask]
    turnover_by_market = turnover_by_market.loc[start_mask]
    gross_by_market = gross_by_market.loc[start_mask]
    path = pd.DataFrame(index=dates[start_mask])
    path.index.name = "ts"
    path["gross_leverage"] = positions.abs().sum(axis=1)
    path["gross_return"] = gross_by_market.sum(axis=1)
    path["turnover"] = turnover_by_market.sum(axis=1)
    for cost_bps in costs:
        slug = f"{cost_bps:g}bps"
        path[f"net_return_{slug}"] = path["gross_return"] - path["turnover"] * (
            cost_bps / 10_000.0
        )
        path[f"net_equity_{slug}"] = (1.0 + path[f"net_return_{slug}"]).cumprod()
    details = []
    for symbol in universe:
        detail = pd.DataFrame(
            {
                "ts": positions.index,
                "strategy": strategy,
                "symbol": symbol,
                "asset_class": universe[symbol]["class"],
                "position": positions[symbol].to_numpy(),
                "turnover": turnover_by_market[symbol].to_numpy(),
                "gross_contribution": gross_by_market[symbol].to_numpy(),
            }
        )
        detail["net_contribution_2bps"] = (
            detail["gross_contribution"] - detail["turnover"] * 0.0002
        )
        details.append(detail)
    return path.reset_index(), pd.concat(details, ignore_index=True)


def daily_metrics(
    path: pd.DataFrame, strategy: str, cost_bps: float, surface: str
) -> dict[str, Any]:
    slug = f"{cost_bps:g}bps"
    net = path[f"net_return_{slug}"]
    equity = (1.0 + net).cumprod()
    start = pd.Timestamp(path["ts"].iloc[0])
    end = pd.Timestamp(path["ts"].iloc[-1])
    years = (end - start).total_seconds() / (365.25 * 86400)
    annual_return = float(net.mean() * DAILY_ANNUALIZER)
    annual_vol = float(net.std(ddof=1) * math.sqrt(DAILY_ANNUALIZER))
    downside = np.minimum(net.to_numpy(), 0.0)
    downside_dev = float(
        np.sqrt(np.mean(np.square(downside))) * math.sqrt(DAILY_ANNUALIZER)
    )
    dd = drawdown(equity)
    month = path["ts"].dt.tz_localize(None).dt.to_period("M")
    monthly = net.groupby(month).apply(compounded)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    return {
        "surface": surface,
        "strategy": strategy,
        "label": LABELS[strategy],
        "cost_bps_one_way": cost_bps,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "observations": len(path),
        "years": years,
        "cagr": cagr,
        "annualized_arithmetic_return": annual_return,
        "annualized_volatility": annual_vol,
        "sharpe": annual_return / annual_vol if annual_vol else math.nan,
        "sortino": annual_return / downside_dev if downside_dev else math.nan,
        "max_drawdown": float(dd.min()),
        "calmar": cagr / abs(float(dd.min())) if dd.min() < 0 else math.nan,
        "daily_win_rate": float(net.gt(0).mean()),
        "positive_month_ratio": float(monthly.gt(0).mean()),
        "annualized_turnover": float(path["turnover"].sum() / years),
        "total_turnover": float(path["turnover"].sum()),
        "gross_total_return": compounded(path["gross_return"]),
        "net_total_return": total,
        "average_gross_leverage": float(path["gross_leverage"].mean()),
        "max_gross_leverage": float(path["gross_leverage"].max()),
    }


def local_period_table(
    paths: dict[str, pd.DataFrame], costs: tuple[float, ...], surface: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = {"year": [], "month": []}
    for strategy, path in paths.items():
        keys = {
            "year": path["ts"].dt.year,
            "month": path["ts"].dt.tz_localize(None).dt.to_period("M").astype(str),
        }
        for frequency, values in keys.items():
            for period, group in path.groupby(values, sort=True):
                for cost_bps in costs:
                    slug = f"{cost_bps:g}bps"
                    net = group[f"net_return_{slug}"]
                    equity = (1.0 + net).cumprod()
                    rows[frequency].append(
                        {
                            "surface": surface,
                            frequency: int(period) if frequency == "year" else str(period),
                            "strategy": strategy,
                            "label": LABELS[strategy],
                            "cost_bps_one_way": cost_bps,
                            "net_return": compounded(net),
                            "gross_return": compounded(group["gross_return"]),
                            "max_drawdown": float(drawdown(equity).min()),
                            "turnover": float(group["turnover"].sum()),
                        }
                    )
    return pd.DataFrame(rows["year"]), pd.DataFrame(rows["month"])


def local_recent_table(
    paths: dict[str, pd.DataFrame], costs: tuple[float, ...], surface: str
) -> pd.DataFrame:
    rows = []
    for strategy, path in paths.items():
        end = pd.Timestamp(path["ts"].iloc[-1])
        for window, offset in RECENT_WINDOWS.items():
            sample = path.loc[path["ts"].ge(end - offset)]
            for cost_bps in costs:
                slug = f"{cost_bps:g}bps"
                net = sample[f"net_return_{slug}"]
                equity = (1.0 + net).cumprod()
                vol = (
                    float(net.std(ddof=1) * math.sqrt(DAILY_ANNUALIZER))
                    if len(net) > 1
                    else math.nan
                )
                ann = float(net.mean() * DAILY_ANNUALIZER) if len(net) else math.nan
                rows.append(
                    {
                        "surface": surface,
                        "window": window,
                        "strategy": strategy,
                        "cost_bps_one_way": cost_bps,
                        "observations": len(sample),
                        "net_return": compounded(net),
                        "max_drawdown": float(drawdown(equity).min()),
                        "sharpe": ann / vol if vol and math.isfinite(vol) else math.nan,
                        "turnover": float(sample["turnover"].sum()),
                    }
                )
    return pd.DataFrame(rows)


def contribution_tables(
    detail: pd.DataFrame, surface: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = detail.copy()
    work["year"] = pd.to_datetime(work["ts"], utc=True).dt.year
    market = (
        work.groupby(["strategy", "symbol", "asset_class"], as_index=False)
        .agg(
            gross_contribution=("gross_contribution", "sum"),
            net_contribution_2bps=("net_contribution_2bps", "sum"),
            turnover=("turnover", "sum"),
            average_abs_position=("position", lambda value: value.abs().mean()),
        )
        .assign(surface=surface)
    )
    class_year = (
        work.groupby(["year", "strategy", "asset_class"], as_index=False)
        .agg(
            gross_contribution=("gross_contribution", "sum"),
            net_contribution_2bps=("net_contribution_2bps", "sum"),
            turnover=("turnover", "sum"),
        )
        .assign(surface=surface)
    )
    return market, class_year


def run_local_surface(
    frames: dict[str, pd.DataFrame],
    universe: dict[str, dict[str, str]],
    evaluation_start: pd.Timestamp,
    costs: tuple[float, ...],
    surface: str,
) -> dict[str, pd.DataFrame]:
    cutoff = CORE.last_complete_month(frames)
    daily = {}
    monthly = {}
    signals = []
    for symbol, frame in frames.items():
        daily[symbol], monthly[symbol] = market_features(frame, cutoff)
        signal = monthly[symbol].copy()
        signal["symbol"] = symbol
        signal["asset_class"] = universe[symbol]["class"]
        signal["surface"] = surface
        signals.append(signal)
    dates = pd.DatetimeIndex(
        sorted({value for frame in daily.values() for value in frame["ts"]})
    )
    returns = pd.DataFrame(index=dates)
    for symbol in universe:
        returns[symbol] = daily[symbol].set_index("ts")["return"].reindex(dates)
    paths = {}
    details = []
    for strategy in STRATEGIES:
        paths[strategy], detail = build_local_path(
            dates,
            returns,
            monthly,
            universe,
            strategy,
            evaluation_start,
            costs,
        )
        paths[strategy]["strategy"] = strategy
        paths[strategy]["surface"] = surface
        details.append(detail)
    common_end = min(pd.Timestamp(path["ts"].iloc[-1]) for path in paths.values())
    paths = {
        key: value.loc[value["ts"].le(common_end)].copy()
        for key, value in paths.items()
    }
    detail = pd.concat(details, ignore_index=True)
    detail = detail.loc[pd.to_datetime(detail["ts"], utc=True).le(common_end)]
    metrics = pd.DataFrame(
        [
            daily_metrics(path, strategy, cost, surface)
            for strategy, path in paths.items()
            for cost in costs
        ]
    )
    yearly, monthly_returns = local_period_table(paths, costs, surface)
    recent = local_recent_table(paths, costs, surface)
    market, class_year = contribution_tables(detail, surface)
    portfolio_paths = pd.concat(paths.values(), ignore_index=True)
    signals_frame = pd.concat(signals, ignore_index=True)
    daily_detail = []
    for symbol, frame in daily.items():
        part = frame.copy()
        part["symbol"] = symbol
        part["asset_class"] = universe[symbol]["class"]
        part["surface"] = surface
        daily_detail.append(part)
    return {
        "metrics": metrics,
        "yearly": yearly,
        "monthly": monthly_returns,
        "recent": recent,
        "market": market,
        "class_year": class_year,
        "paths": portfolio_paths,
        "signals": signals_frame,
        "detail": detail,
        "market_daily": pd.concat(daily_detail, ignore_index=True),
    }


def load_published_csv(kind: str) -> pd.DataFrame:
    path = ARTIFACT_DIR / f"{PREFIX}-aqr-{kind}-returns.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"run extract_aqr_tsmom_workbooks.py with bundled Python first: {path}"
        )
    frame = pd.read_csv(path, parse_dates=["DATE"])
    expected = {"DATE", *FACTOR_LABELS}
    if set(frame.columns) != expected:
        raise RuntimeError(f"unexpected published columns: {list(frame.columns)}")
    if frame["DATE"].duplicated().any() or not frame["DATE"].is_monotonic_increasing:
        raise RuntimeError(f"invalid published date order: {kind}")
    return frame


def monthly_metrics(
    returns: pd.Series, source: str, scope: str, factor: str
) -> dict[str, Any]:
    clean = returns.dropna().astype(float)
    equity = (1.0 + clean).cumprod()
    annual_return = float(clean.mean() * 12.0)
    annual_vol = float(clean.std(ddof=1) * math.sqrt(12.0))
    downside = np.minimum(clean.to_numpy(), 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(12.0))
    dd = drawdown(equity)
    years = len(clean) / 12.0
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    return {
        "source": source,
        "scope": scope,
        "factor": factor,
        "label": FACTOR_LABELS[factor],
        "start_month": clean.index[0].strftime("%Y-%m-%d"),
        "end_month": clean.index[-1].strftime("%Y-%m-%d"),
        "observations": len(clean),
        "years": years,
        "cagr": cagr,
        "annualized_arithmetic_return": annual_return,
        "annualized_volatility": annual_vol,
        "sharpe": annual_return / annual_vol if annual_vol else math.nan,
        "sortino": annual_return / downside_dev if downside_dev else math.nan,
        "max_drawdown": float(dd.min()),
        "calmar": cagr / abs(float(dd.min())) if dd.min() < 0 else math.nan,
        "positive_month_ratio": float(clean.gt(0).mean()),
        "total_return": float(equity.iloc[-1] - 1.0),
    }


def published_analysis() -> dict[str, Any]:
    original = load_published_csv("original").set_index("DATE")
    updated = load_published_csv("updated").set_index("DATE")
    paper_end = pd.Timestamp("2009-12-31")
    post_start = pd.Timestamp("2010-01-01")
    scopes = [
        ("original", "original_paper_1985_2009", original),
        (
            "updated",
            "updated_reconstruction_1985_2009",
            updated.loc[updated.index <= paper_end],
        ),
        (
            "updated",
            "updated_post_paper_2010_latest",
            updated.loc[updated.index >= post_start],
        ),
        ("updated", "updated_full_1985_latest", updated),
    ]
    metrics = pd.DataFrame(
        [
            monthly_metrics(frame[factor], source, scope, factor)
            for source, scope, frame in scopes
            for factor in FACTOR_LABELS
        ]
    )
    yearly_rows = []
    for source, scope, frame in scopes:
        for year, group in frame.groupby(frame.index.year):
            for factor in FACTOR_LABELS:
                yearly_rows.append(
                    {
                        "source": source,
                        "scope": scope,
                        "year": int(year),
                        "factor": factor,
                        "label": FACTOR_LABELS[factor],
                        "return": compounded(group[factor]),
                    }
                )
    overlap = original.join(updated, lsuffix="_original", rsuffix="_updated")
    comparisons = []
    for factor in FACTOR_LABELS:
        left = overlap[f"{factor}_original"]
        right = overlap[f"{factor}_updated"]
        difference = right - left
        comparisons.append(
            {
                "factor": factor,
                "label": FACTOR_LABELS[factor],
                "observations": len(overlap),
                "correlation": float(left.corr(right)),
                "mean_difference_monthly": float(difference.mean()),
                "mean_absolute_difference_monthly": float(difference.abs().mean()),
                "max_absolute_difference_monthly": float(difference.abs().max()),
            }
        )
    recent_rows = []
    for months, label in ((1, "1m"), (3, "3m"), (6, "6m"), (12, "1y")):
        sample = updated.tail(months)
        for factor in FACTOR_LABELS:
            recent_rows.append(
                {
                    "window": label,
                    "factor": factor,
                    "label": FACTOR_LABELS[factor],
                    "observations": len(sample),
                    "return": compounded(sample[factor]),
                }
            )
    return {
        "metrics": metrics,
        "yearly": pd.DataFrame(yearly_rows),
        "overlap": pd.DataFrame(comparisons),
        "recent": pd.DataFrame(recent_rows),
    }


def load_futures_surface(allow_untrusted: bool) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, str]]]:
    if not allow_untrusted:
        raise RuntimeError("local futures surface is raw_unaccepted; pass --allow-untrusted")
    frames = {
        symbol: CORE.load_market(symbol, allow_untrusted=True) for symbol in CORE.UNIVERSE
    }
    return frames, CORE.UNIVERSE


def load_proxy_surface() -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, str]]]:
    frames = {}
    universe = {}
    for symbol, identity in EWMAC.CLASSIC_ASSETS.items():
        raw_path = EWMAC.YAHOO_RAW_DIR / f"{symbol}_2026-08-10.json"
        content = raw_path.read_bytes()
        adjusted, _ = EWMAC.parse_yahoo(content, symbol, "2026-08-10")
        frame = adjusted.reset_index().rename(columns={"day": "ts"})
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frames[symbol] = frame[["ts", "close"]]
        universe[symbol] = {
            "class": identity["class"],
            "exchange": "proxy",
            "name": identity["name"],
        }
    return frames, universe


def pct(value: Any) -> str:
    return "n/a" if pd.isna(value) else f"{float(value):.2%}"


def num(value: Any) -> str:
    return "n/a" if pd.isna(value) else f"{float(value):.3f}"


def load_prior_controlled_12m() -> pd.DataFrame:
    sources = {
        "24_yahoo_continuous_futures": (
            ARTIFACT_DIR / "tf-1d-fut-tsmom-p0-2026-08-18-metrics.csv"
        ),
        "30_etf_fx_proxies": (
            ARTIFACT_DIR
            / "tf-1d-fut-tsmom-proxy-validation-2026-08-18-metrics.csv"
        ),
    }
    rows = []
    for surface, path in sources.items():
        metrics = pd.read_csv(path)
        selected = metrics.loc[
            metrics["strategy"].eq("tsmom_12m")
            & metrics["cost_bps_one_way"].eq(PRIMARY_COST)
        ]
        if len(selected) != 1:
            raise RuntimeError(f"cannot resolve prior controlled 12M row: {path}")
        row = selected.iloc[0].to_dict()
        row["surface"] = surface
        row["construction"] = "P0 controlled 12M"
        rows.append(row)
    return pd.DataFrame(rows)


def render_report(
    run_date: str,
    published_metrics: pd.DataFrame,
    local_metrics: pd.DataFrame,
    overlap: pd.DataFrame,
    prior_controlled: pd.DataFrame,
) -> str:
    diversified = published_metrics.loc[published_metrics["factor"].eq("TSMOM")].set_index(
        "scope"
    )
    original = diversified.loc["original_paper_1985_2009"]
    reconstructed = diversified.loc["updated_reconstruction_1985_2009"]
    post = diversified.loc["updated_post_paper_2010_latest"]
    full = diversified.loc["updated_full_1985_latest"]
    primary = local_metrics.loc[
        local_metrics["strategy"].eq("mop_tsmom")
        & local_metrics["cost_bps_one_way"].eq(PRIMARY_COST)
    ].set_index("surface")
    futures = primary.loc["24_yahoo_continuous_futures"]
    proxy = primary.loc["30_etf_fx_proxies"]
    published_rows = []
    for label, row in (
        ("作者原论文文件 1985–2009", original),
        ("AQR 更新口径重建 1985–2009", reconstructed),
        ("AQR 论文后 2010–2026-05", post),
        ("AQR 更新全期 1985–2026-05", full),
    ):
        published_rows.append(
            f"| {label} | {pct(row.cagr)} | {pct(row.annualized_arithmetic_return)} | "
            f"{pct(row.annualized_volatility)} | {num(row.sharpe)} | "
            f"{pct(row.max_drawdown)} | {pct(row.total_return)} |"
        )
    class_rows = []
    for factor, label in FACTOR_LABELS.items():
        if factor == "TSMOM":
            continue
        old = published_metrics.loc[
            published_metrics["scope"].eq("original_paper_1985_2009")
            & published_metrics["factor"].eq(factor)
        ].iloc[0]
        new = published_metrics.loc[
            published_metrics["scope"].eq("updated_post_paper_2010_latest")
            & published_metrics["factor"].eq(factor)
        ].iloc[0]
        class_rows.append(
            f"| {label} | {pct(old.cagr)} | {num(old.sharpe)} | "
            f"{pct(new.cagr)} | {num(new.sharpe)} |"
        )
    local_rows = []
    selected = local_metrics.loc[local_metrics["cost_bps_one_way"].eq(PRIMARY_COST)]
    for row in selected.itertuples(index=False):
        local_rows.append(
            f"| `{row.surface}` | `{row.label}` | {pct(row.cagr)} | "
            f"{pct(row.annualized_volatility)} | {num(row.sharpe)} | "
            f"{pct(row.max_drawdown)} | {pct(row.net_total_return)} | "
            f"{num(row.annualized_turnover)} | {num(row.average_gross_leverage)} | "
            f"{num(row.max_gross_leverage)} |"
        )
    comparison_rows = []
    exact = local_metrics.loc[
        local_metrics["strategy"].eq("mop_tsmom")
        & local_metrics["cost_bps_one_way"].eq(PRIMARY_COST)
    ]
    for surface in ("24_yahoo_continuous_futures", "30_etf_fx_proxies"):
        controlled = prior_controlled.loc[prior_controlled["surface"].eq(surface)].iloc[0]
        paper = exact.loc[exact["surface"].eq(surface)].iloc[0]
        for construction, row in (
            ("P0 受控12M", controlled),
            ("论文原式", paper),
        ):
            comparison_rows.append(
                f"| `{surface}` | {construction} | {pct(row.cagr)} | "
                f"{pct(row.annualized_volatility)} | {num(row.sharpe)} | "
                f"{pct(row.max_drawdown)} | {num(row.average_gross_leverage)} | "
                f"{num(row.max_gross_leverage)} |"
            )
    diversified_overlap = overlap.loc[overlap["factor"].eq("TSMOM")].iloc[0]
    stem = f"tf-1d-fut-tsmom-paper-exact-p1-{run_date}"
    return "\n".join(
        [
            f"# MOP 2012 TSMOM 论文原式复刻（{run_date}）",
            "",
            "- 状态：`explore / diagnostic-only / not promoted / not live-ready`",
            "- 原式：`12M sign × 40% / sigma`，所有有效市场等权，持有下月",
            "- 明确取消：类别25%、组合层10%目标、portfolio scalar、3x gross cap",
            "- 作者序列为 monthly excess returns；本地连续期货和代理不与其拼接",
            "",
            "## 一句话结论",
            "",
            f"作者原论文文件在 1985–2009 的 CAGR 为 `{pct(original.cagr)}`、Sharpe "
            f"`{num(original.sharpe)}`；AQR 更新序列在 2010–2026-05 降至 CAGR "
            f"`{pct(post.cagr)}`、Sharpe `{num(post.sharpe)}`。论文效应仍为正，但论文后"
            "明显衰减。",
            f"同一公式在24个当前期货代码上的2 bps结果为 CAGR `{pct(futures.cagr)}`、"
            f"Sharpe `{num(futures.sharpe)}`；30代理长期表面为 CAGR `{pct(proxy.cagr)}`、"
            f"Sharpe `{num(proxy.sharpe)}`。",
            "",
            "## 作者/AQR diversified factor",
            "",
            "| 序列 | CAGR | 年化算术收益 | 波动 | Sharpe | MDD | 总收益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            *published_rows,
            "",
            "## 四资产类别：原论文窗口 vs 论文后",
            "",
            "| 类别 | 原论文 CAGR | 原论文 Sharpe | 论文后 CAGR | 论文后 Sharpe |",
            "| --- | ---: | ---: | ---: | ---: |",
            *class_rows,
            "",
            "## 本地论文公式（2 bps/边）",
            "",
            "| 表面 | 分支 | CAGR | 波动 | Sharpe | MDD | 净总收益 | 年换手 | 平均gross | 峰值gross |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *local_rows,
            "",
            "## 为什么论文式看起来更赚钱",
            "",
            "| 表面 | 构造 | CAGR | 波动 | Sharpe | MDD | 平均gross | 峰值gross |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            *comparison_rows,
            "",
            "论文原式提高了绝对收益，但同时取消3倍帽并把平均gross推到约4–5倍；两个本地表面"
            "的 Sharpe 都低于对应的P0受控12M，MDD约扩大一倍。因此收益提升主要来自更高风险"
            "预算，不是更强的当代预测能力。",
            "",
            "## 重要审计发现",
            "",
            f"AQR 更新文件会重建全部历史。更新口径与作者原始文件在共同300个月的 diversified "
            f"月收益相关性为 `{num(diversified_overlap.correlation)}`，平均绝对月差为 "
            f"`{pct(diversified_overlap.mean_absolute_difference_monthly)}`。因此论文原始结论以"
            " original workbook 为准，更新文件只用于论文后稳定性。",
            "",
            "本地24市场缺少论文的58市场广度及逐合约/远期 excess-return 构造；Yahoo 连续代码"
            "也没有官方 roll mapping。30代理包含ETF费用、分红与商品基金roll结构。两套本地结果"
            "只能回答公式在可得表面的表现，不能称为相同数据复刻。",
            "",
            "## 证据",
            "",
            f"- [冻结契约](../specs/{stem.replace('-2026-08-19', '')}-contract-2026-08-19.md)",
            f"- [作者/AQR 指标](../artifacts/{stem}-published-factor-metrics.csv)",
            f"- [本地同式指标](../artifacts/{stem}-local-metrics.csv)",
            f"- [配置与审计摘要](../artifacts/{stem}-summary.json)",
            f"- [SHA256 清单](../artifacts/{stem}-checksums.sha256)",
            "",
        ]
    )


def self_test() -> None:
    returns = pd.Series([0.01, -0.02, 0.03] * 100, dtype=float)
    sigma = paper_sigma(returns)
    assert sigma.iloc[:59].isna().all()
    expected_mean = returns.ewm(com=60, adjust=False, min_periods=60).mean()
    expected_second = returns.pow(2).ewm(
        com=60, adjust=False, min_periods=60
    ).mean()
    expected = ((expected_second - expected_mean.pow(2)).clip(lower=0) * 261).pow(0.5)
    np.testing.assert_allclose(sigma, expected, equal_nan=True)
    dates = pd.bdate_range("2019-01-01", periods=800, tz="UTC")
    close = 100 * np.exp(np.arange(len(dates)) * 0.0005)
    daily, monthly = market_features(
        pd.DataFrame({"ts": dates, "close": close}), dates[-1]
    )
    expected_signal = np.sign(monthly["close"].pct_change(12, fill_method=None))
    np.testing.assert_allclose(monthly["forecast_12m"], expected_signal, equal_nan=True)
    assert daily.loc[daily["return"].notna(), "sigma_ann"].iloc[-1] >= 0
    print("self-test passed")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    published = published_analysis()
    prior_controlled = load_prior_controlled_12m()
    futures_frames, futures_universe = load_futures_surface(args.allow_untrusted)
    proxy_frames, proxy_universe = load_proxy_surface()
    futures = run_local_surface(
        futures_frames,
        futures_universe,
        FUTURES_START,
        FUTURES_COSTS,
        "24_yahoo_continuous_futures",
    )
    proxy = run_local_surface(
        proxy_frames,
        proxy_universe,
        PROXY_START,
        PROXY_COSTS,
        "30_etf_fx_proxies",
    )
    local_metrics = pd.concat([futures["metrics"], proxy["metrics"]], ignore_index=True)
    stem = f"tf-1d-fut-tsmom-paper-exact-p1-{args.run_date}"
    config = {
        "observation": "MOP 2012 paper-exact construction audit",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "signal": "sign(past 12-month return)",
        "holding_period": "next month",
        "instrument_target_volatility": PAPER_TARGET_VOL,
        "volatility_center_of_mass_days": VOL_COM,
        "volatility_annualizer": VOL_ANNUALIZER,
        "portfolio_weighting": "equal across all valid instruments",
        "portfolio_volatility_target": None,
        "gross_leverage_cap": None,
        "futures_cost_bps_one_way": list(FUTURES_COSTS),
        "proxy_cost_bps_one_way": list(PROXY_COSTS),
        "futures_start": FUTURES_START.isoformat(),
        "proxy_start": PROXY_START.isoformat(),
        "futures_markets": len(futures_universe),
        "proxy_markets": len(proxy_universe),
    }
    source_audit_path = ARTIFACT_DIR / f"{PREFIX}-aqr-source-audit.json"
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "config": config,
        "published_factor_metrics": published["metrics"].to_dict(orient="records"),
        "local_metrics": local_metrics.to_dict(orient="records"),
        "published_overlap_audit": published["overlap"].to_dict(orient="records"),
        "prior_controlled_12m_metrics": prior_controlled.to_dict(orient="records"),
        "source_audit": source_audit,
        "limitations": [
            "published factors are an outcome audit, not an independent instrument-level reconstruction",
            "local futures use raw_unaccepted Yahoo continuous codes rather than the paper's 58 contracts",
            "ETF/FX proxies are not continuous futures excess returns",
            "explicit roll costs and collateral yield are excluded from local surfaces",
        ],
    }
    frames = {
        "published-factor-metrics.csv": published["metrics"],
        "published-factor-yearly.csv": published["yearly"],
        "published-overlap-audit.csv": published["overlap"],
        "published-recent-slices.csv": published["recent"],
        "local-metrics.csv": local_metrics,
        "local-yearly-returns.csv": pd.concat(
            [futures["yearly"], proxy["yearly"]], ignore_index=True
        ),
        "local-monthly-returns.csv": pd.concat(
            [futures["monthly"], proxy["monthly"]], ignore_index=True
        ),
        "local-recent-slices.csv": pd.concat(
            [futures["recent"], proxy["recent"]], ignore_index=True
        ),
        "local-market-contributions.csv": pd.concat(
            [futures["market"], proxy["market"]], ignore_index=True
        ),
        "local-class-year-contributions.csv": pd.concat(
            [futures["class_year"], proxy["class_year"]], ignore_index=True
        ),
        "local-portfolio-paths.csv": pd.concat(
            [futures["paths"], proxy["paths"]], ignore_index=True
        ),
        "local-month-end-signals.csv": pd.concat(
            [futures["signals"], proxy["signals"]], ignore_index=True
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_paths = []
    for suffix, frame in frames.items():
        path = ARTIFACT_DIR / f"{stem}-{suffix}"
        content = frame.to_csv(index=False)
        if path.exists() and not args.force and path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"artifact exists; pass --force: {path}")
        path.write_text(content, encoding="utf-8")
        artifact_paths.append(path)
    for suffix, payload in (("config.json", config), ("summary.json", summary)):
        path = ARTIFACT_DIR / f"{stem}-{suffix}"
        content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if path.exists() and not args.force and path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"artifact exists; pass --force: {path}")
        path.write_text(content, encoding="utf-8")
        artifact_paths.append(path)
    detail_path = ARTIFACT_DIR / f"{stem}-local-asset-daily.parquet"
    detail = pd.concat([futures["detail"], proxy["detail"]], ignore_index=True)
    if detail_path.exists() and not args.force:
        existing = pd.read_parquet(detail_path)
        if len(existing) != len(detail):
            raise RuntimeError(f"artifact exists; pass --force: {detail_path}")
    else:
        detail.to_parquet(detail_path, index=False)
    artifact_paths.append(detail_path)
    for pattern in (
        f"{PREFIX}-aqr-*.xlsx",
        f"{PREFIX}-aqr-*-returns.csv",
        f"{PREFIX}-aqr-source-audit.json",
    ):
        artifact_paths.extend(ARTIFACT_DIR.glob(pattern))
    unique_paths = sorted(set(artifact_paths))
    checksum_path = ARTIFACT_DIR / f"{stem}-checksums.sha256"
    checksum_path.write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in unique_paths) + "\n",
        encoding="utf-8",
    )
    report_path = FAMILY_DIR / "diagnostics" / f"{stem}.md"
    report_path.write_text(
        render_report(
            args.run_date,
            published["metrics"],
            local_metrics,
            published["overlap"],
            prior_controlled,
        ),
        encoding="utf-8",
    )
    print(
        published["metrics"]
        .loc[published["metrics"]["factor"].eq("TSMOM")]
        .to_json(orient="records", force_ascii=False, indent=2)
    )
    print(
        local_metrics.loc[
            local_metrics["strategy"].eq("mop_tsmom")
            & local_metrics["cost_bps_one_way"].eq(PRIMARY_COST)
        ].to_json(orient="records", force_ascii=False, indent=2)
    )
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
