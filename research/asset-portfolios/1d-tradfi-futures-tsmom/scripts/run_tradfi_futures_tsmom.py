#!/usr/bin/env python3
"""Run the frozen 24-market traditional-futures TSMOM P0."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-tradfi-futures-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FETCH_SCRIPT = Path(__file__).with_name("fetch_tradfi_futures_yahoo.py")
EVALUATION_START = pd.Timestamp("2022-01-03", tz="UTC")
TARGET_VOL = 0.10
PORTFOLIO_TARGET_VOL = 0.10
VOL_COM = 60.0
VOL_MIN_PERIODS = 60
ANNUALIZER = 252
PORTFOLIO_SCALAR_CAP = 3.0
GROSS_CAP = 3.0
COSTS = (0.0, 2.0)
PRIMARY_COST = 2.0
CLASS_WEIGHT = 0.25
STRATEGIES = ("tsmom_1m", "tsmom_3m", "tsmom_12m", "composite", "long_only")
LABELS = {
    "tsmom_1m": "1M",
    "tsmom_3m": "3M",
    "tsmom_12m": "12M",
    "composite": "Composite",
    "long_only": "Long-only RP",
}
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=0),
    "7d": pd.Timedelta(days=6),
    "1m": pd.DateOffset(months=1),
    "3m": pd.DateOffset(months=3),
    "6m": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
}


def load_fetch_module():
    spec = importlib.util.spec_from_file_location("tf_tsmom_fetch", FETCH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {FETCH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCH = load_fetch_module()
UNIVERSE = FETCH.UNIVERSE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--allow-untrusted", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def raw_files(symbol: str) -> list[Path]:
    identity = UNIVERSE[symbol]
    return sorted(
        (
            ROOT
            / "data/raw/ohlcv"
            / f"exchange={identity['exchange']}"
            / "market_type=futures/timeframe=1d"
            / f"source={FETCH.SOURCE}"
        ).glob(f"date=*/symbol={FETCH.safe_symbol(symbol)}.parquet")
    )


def load_market(symbol: str, *, allow_untrusted: bool) -> pd.DataFrame:
    files = raw_files(symbol)
    if not files:
        raise FileNotFoundError(f"raw partitions absent for {symbol}")
    pattern = str(files[0].parents[1] / "date=*" / files[0].name)
    frame = duckdb.connect().execute(
        "SELECT * FROM read_parquet(?, hive_partitioning=false)", [pattern]
    ).df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    expected = UNIVERSE[symbol]
    if set(frame["symbol"]) != {symbol} or set(frame["asset_class"]) != {
        expected["class"]
    }:
        raise RuntimeError(f"identity mismatch for {symbol}")
    if set(frame["quality_status"]) != {"raw_unaccepted"}:
        raise RuntimeError(f"unexpected quality status for {symbol}")
    if not allow_untrusted:
        raise RuntimeError("P0 surface is raw_unaccepted; pass --allow-untrusted")
    return frame


def last_complete_month(frames: dict[str, pd.DataFrame]) -> pd.Timestamp:
    final = min(pd.Timestamp(frame["ts"].iloc[-1]) for frame in frames.values())
    naive = final.tz_convert("UTC").tz_localize(None)
    prior_end = naive.to_period("M").start_time - pd.Timedelta(days=1)
    eligible = [
        frame.loc[frame["ts"].dt.tz_localize(None).le(prior_end), "ts"].iloc[-1]
        for frame in frames.values()
    ]
    return min(pd.Timestamp(value) for value in eligible)


def market_features(frame: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = frame.loc[frame["ts"].le(cutoff), ["ts", "close"]].copy()
    daily["return"] = daily["close"].pct_change(fill_method=None)
    daily["sigma_ann"] = (
        daily["return"]
        .shift(1)
        .pow(2)
        .ewm(com=VOL_COM, adjust=False, min_periods=VOL_MIN_PERIODS)
        .mean()
        .mul(ANNUALIZER)
        .pow(0.5)
    )
    daily["month"] = daily["ts"].dt.tz_localize(None).dt.to_period("M")
    month_end = daily.groupby("month", sort=True, as_index=False).tail(1).copy()
    for horizon in (1, 3, 12):
        month_end[f"return_{horizon}m"] = month_end["close"].pct_change(
            horizon, fill_method=None
        )
        month_end[f"forecast_{horizon}m"] = np.sign(
            month_end[f"return_{horizon}m"]
        )
    month_end["forecast_composite"] = month_end[
        ["forecast_1m", "forecast_3m", "forecast_12m"]
    ].mean(axis=1, skipna=False)
    month_end["forecast_long_only"] = 1.0
    return daily, month_end


def forecast_column(strategy: str) -> str:
    return {
        "tsmom_1m": "forecast_1m",
        "tsmom_3m": "forecast_3m",
        "tsmom_12m": "forecast_12m",
        "composite": "forecast_composite",
        "long_only": "forecast_long_only",
    }[strategy]


def expand_unscaled_positions(
    dates: pd.DatetimeIndex,
    monthly: dict[str, pd.DataFrame],
    strategy: str,
) -> pd.DataFrame:
    result = pd.DataFrame(index=dates)
    class_counts = pd.Series(
        {asset_class: sum(v["class"] == asset_class for v in UNIVERSE.values())
         for asset_class in {v["class"] for v in UNIVERSE.values()}}
    )
    for symbol, events in monthly.items():
        class_name = UNIVERSE[symbol]["class"]
        target = (
            events[forecast_column(strategy)]
            * TARGET_VOL
            / events["sigma_ann"]
            * CLASS_WEIGHT
            / class_counts[class_name]
        )
        announcements = pd.Series(target.to_numpy(), index=pd.DatetimeIndex(events["ts"]))
        result[symbol] = announcements.reindex(dates).ffill().shift(1)
    return result


def portfolio_scalar(
    dates: pd.DatetimeIndex,
    raw_return: pd.Series,
) -> pd.Series:
    sigma = (
        raw_return.shift(1)
        .pow(2)
        .ewm(com=VOL_COM, adjust=False, min_periods=VOL_MIN_PERIODS)
        .mean()
        .mul(ANNUALIZER)
        .pow(0.5)
    )
    frame = pd.DataFrame({"ts": dates, "sigma": sigma.to_numpy()})
    frame["month"] = frame["ts"].dt.tz_localize(None).dt.to_period("M")
    events = frame.groupby("month", sort=True, as_index=False).tail(1)
    target = (PORTFOLIO_TARGET_VOL / events["sigma"]).clip(
        upper=PORTFOLIO_SCALAR_CAP
    )
    announcements = pd.Series(target.to_numpy(), index=pd.DatetimeIndex(events["ts"]))
    return announcements.reindex(dates).ffill().shift(1)


def build_strategy_path(
    dates: pd.DatetimeIndex,
    returns: pd.DataFrame,
    monthly: dict[str, pd.DataFrame],
    strategy: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    unscaled = expand_unscaled_positions(dates, monthly, strategy)
    raw_return = (unscaled.fillna(0.0) * returns.fillna(0.0)).sum(axis=1)
    scalar = portfolio_scalar(dates, raw_return)
    target = unscaled.mul(scalar, axis=0)
    gross_before_cap = target.abs().sum(axis=1)
    cap_factor = (GROSS_CAP / gross_before_cap).clip(upper=1.0).fillna(0.0)
    positions = target.mul(cap_factor, axis=0).fillna(0.0)
    turnover_by_market = positions.diff().fillna(positions.abs()).abs()
    gross_by_market = positions * returns.fillna(0.0)
    start_mask = dates >= EVALUATION_START
    positions = positions.loc[start_mask]
    turnover_by_market = turnover_by_market.loc[start_mask]
    gross_by_market = gross_by_market.loc[start_mask]
    scalar = scalar.loc[start_mask]
    path = pd.DataFrame(index=dates[start_mask])
    path.index.name = "ts"
    path["portfolio_scalar"] = scalar
    path["gross_leverage"] = positions.abs().sum(axis=1)
    path["gross_return"] = gross_by_market.sum(axis=1)
    path["turnover"] = turnover_by_market.sum(axis=1)
    for cost_bps in COSTS:
        slug = f"{cost_bps:g}bps"
        path[f"net_return_{slug}"] = path["gross_return"] - path["turnover"] * (
            cost_bps / 10_000.0
        )
        path[f"net_equity_{slug}"] = (1.0 + path[f"net_return_{slug}"]).cumprod()
    detail_rows = []
    for symbol in UNIVERSE:
        detail = pd.DataFrame(
            {
                "ts": positions.index,
                "strategy": strategy,
                "symbol": symbol,
                "asset_class": UNIVERSE[symbol]["class"],
                "position": positions[symbol].to_numpy(),
                "turnover": turnover_by_market[symbol].to_numpy(),
                "gross_contribution": gross_by_market[symbol].to_numpy(),
            }
        )
        detail["net_contribution_2bps"] = (
            detail["gross_contribution"] - detail["turnover"] * 0.0002
        )
        detail_rows.append(detail)
    return path.reset_index(), pd.concat(detail_rows, ignore_index=True)


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def compounded(returns: pd.Series) -> float:
    return float((1.0 + returns).prod() - 1.0)


def metrics(path: pd.DataFrame, strategy: str, cost_bps: float) -> dict[str, Any]:
    slug = f"{cost_bps:g}bps"
    net = path[f"net_return_{slug}"]
    equity = (1.0 + net).cumprod()
    start, end = pd.Timestamp(path["ts"].iloc[0]), pd.Timestamp(path["ts"].iloc[-1])
    years = (end - start).total_seconds() / (365.25 * 86400)
    annual_return = float(net.mean() * ANNUALIZER)
    annual_vol = float(net.std(ddof=1) * math.sqrt(ANNUALIZER))
    downside = np.minimum(net.to_numpy(), 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(ANNUALIZER))
    dd = drawdown(equity)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    month_key = path["ts"].dt.tz_localize(None).dt.to_period("M")
    monthly = net.groupby(month_key).apply(compounded)
    return {
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
        "average_portfolio_scalar": float(path["portfolio_scalar"].mean()),
    }


def period_table(paths: dict[str, pd.DataFrame], frequency: str) -> pd.DataFrame:
    rows = []
    for strategy, path in paths.items():
        if frequency == "year":
            keys = path["ts"].dt.year
            name = "year"
        else:
            keys = path["ts"].dt.tz_localize(None).dt.to_period("M").astype(str)
            name = "month"
        for period, group in path.groupby(keys, sort=True):
            for cost_bps in COSTS:
                slug = f"{cost_bps:g}bps"
                net = group[f"net_return_{slug}"]
                equity = (1.0 + net).cumprod()
                rows.append(
                    {
                        name: int(period) if frequency == "year" else str(period),
                        "strategy": strategy,
                        "label": LABELS[strategy],
                        "cost_bps_one_way": cost_bps,
                        "net_return": compounded(net),
                        "gross_return": compounded(group["gross_return"]),
                        "max_drawdown": float(drawdown(equity).min()),
                        "turnover": float(group["turnover"].sum()),
                    }
                )
    return pd.DataFrame(rows)


def recent_table(paths: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for strategy, path in paths.items():
        end = pd.Timestamp(path["ts"].iloc[-1])
        for label, offset in RECENT_WINDOWS.items():
            start = end - offset
            sample = path.loc[path["ts"].ge(start)]
            for cost_bps in COSTS:
                slug = f"{cost_bps:g}bps"
                net = sample[f"net_return_{slug}"]
                equity = (1.0 + net).cumprod()
                vol = float(net.std(ddof=1) * math.sqrt(ANNUALIZER)) if len(net) > 1 else math.nan
                ann = float(net.mean() * ANNUALIZER) if len(net) else math.nan
                rows.append(
                    {
                        "window": label,
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


def contribution_tables(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail = detail.copy()
    detail["year"] = pd.to_datetime(detail["ts"], utc=True).dt.year
    market = (
        detail.groupby(["strategy", "symbol", "asset_class"], as_index=False)
        .agg(
            gross_contribution=("gross_contribution", "sum"),
            net_contribution_2bps=("net_contribution_2bps", "sum"),
            turnover=("turnover", "sum"),
            average_abs_position=("position", lambda value: value.abs().mean()),
        )
    )
    class_year = (
        detail.groupby(["year", "strategy", "asset_class"], as_index=False)
        .agg(
            gross_contribution=("gross_contribution", "sum"),
            net_contribution_2bps=("net_contribution_2bps", "sum"),
            turnover=("turnover", "sum"),
        )
    )
    return market, class_year


def pct(value: Any) -> str:
    return "n/a" if pd.isna(value) else f"{float(value):.2%}"


def num(value: Any) -> str:
    return "n/a" if pd.isna(value) else f"{float(value):.3f}"


def render_report(
    run_date: str,
    metrics_frame: pd.DataFrame,
    yearly: pd.DataFrame,
    market: pd.DataFrame,
    class_year: pd.DataFrame,
    stem: str,
) -> str:
    primary = metrics_frame.loc[metrics_frame["cost_bps_one_way"].eq(PRIMARY_COST)]
    rows = []
    for row in primary.itertuples(index=False):
        rows.append(
            f"| `{row.label}` | {pct(row.cagr)} | {pct(row.annualized_arithmetic_return)} | "
            f"{pct(row.annualized_volatility)} | {num(row.sharpe)} | {num(row.sortino)} | "
            f"{pct(row.max_drawdown)} | {num(row.calmar)} | {pct(row.positive_month_ratio)} | "
            f"{num(row.annualized_turnover)} | {pct(row.gross_total_return)} | "
            f"{pct(row.net_total_return)} | {num(row.average_gross_leverage)} |"
        )
    comp = primary.set_index("strategy").loc["composite"]
    long_only = primary.set_index("strategy").loc["long_only"]
    comp_market = market.loc[market["strategy"].eq("composite")].sort_values(
        "net_contribution_2bps", ascending=False
    )
    market_rows = [
        f"| `{row.symbol}` | `{row.asset_class}` | {pct(row.net_contribution_2bps)} | {num(row.turnover)} |"
        for row in comp_market.itertuples(index=False)
    ]
    class_total = (
        class_year.loc[class_year["strategy"].eq("composite")]
        .groupby("asset_class", as_index=False)["net_contribution_2bps"]
        .sum()
        .sort_values("net_contribution_2bps", ascending=False)
    )
    class_rows = [
        f"| `{row.asset_class}` | {pct(row.net_contribution_2bps)} |"
        for row in class_total.itertuples(index=False)
    ]
    year_primary = yearly.loc[
        yearly["strategy"].isin(["composite", "long_only"])
        & yearly["cost_bps_one_way"].eq(PRIMARY_COST)
    ]
    pivot = year_primary.pivot(index="year", columns="strategy", values="net_return")
    year_rows = [
        f"| `{year}` | {pct(row.get('composite'))} | {pct(row.get('long_only'))} |"
        for year, row in pivot.iterrows()
    ]
    return "\n".join(
        [
            f"# TF-1D-FUT-TSMOM P0 多资产期货回测（{run_date}）",
            "",
            "- 状态：`explore / diagnostic-only / not promoted / not live-ready`",
            "- 资产池：24 个连续期货，股票指数/债券/外汇/商品四类各 25% raw risk budget",
            f"- 主窗口：`{comp.start_ts}` → `{comp.end_ts}`",
            "- 信号：月末 `sign(1M/3M/12M)`；下一交易日生效；Composite 等权",
            "- 风险：资产与组合两层 60-day COM EWMA；组合目标 10%；gross cap 3x",
            "- 成本：0 bps 对照 + 2 bps 单边目标权重换手；未单列 roll cost",
            "",
            "## 结论",
            "",
            f"Composite 含成本 CAGR `{pct(comp.cagr)}`、Sharpe `{num(comp.sharpe)}`、"
            f"最大回撤 `{pct(comp.max_drawdown)}`、净总收益 `{pct(comp.net_total_return)}`。",
            f"Long-only risk parity 同口径 CAGR `{pct(long_only.cagr)}`、Sharpe "
            f"`{num(long_only.sharpe)}`、最大回撤 `{pct(long_only.max_drawdown)}`。",
            "",
            "## 四分支与基准（2 bps）",
            "",
            "| 分支 | CAGR | 年化收益 | 年化波动 | Sharpe | Sortino | MDD | Calmar | 正收益月 | 年换手 | 毛总收益 | 净总收益 | 平均gross |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## Composite 类别累计净贡献（return points）",
            "",
            "| 类别 | 净贡献 |",
            "| --- | ---: |",
            *class_rows,
            "",
            "## Composite 市场累计净贡献（return points）",
            "",
            "| 市场 | 类别 | 净贡献 | 换手 |",
            "| --- | --- | ---: | ---: |",
            *market_rows,
            "",
            "## Composite vs Long-only 分年",
            "",
            "| 年 | Composite | Long-only RP |",
            "| --- | ---: | ---: |",
            *year_rows,
            "",
            "## 数据与结论边界",
            "",
            "Yahoo 连续代码未披露逐合约 roll mapping；本轮没有官方结算价、合约乘数和显式换月成本。"
            "因此 P0 只能判断 2022–2026 公开连续序列上的组合形态，不能登记版本或声称严格复刻期货总收益。",
            "",
            "## 证据",
            "",
            f"- [数据审计](../artifacts/{stem}-data-audit.json)",
            f"- [固定配置](../artifacts/{stem}-config.json)",
            f"- [完整指标](../artifacts/{stem}-metrics.csv)",
            f"- [组合日路径](../artifacts/{stem}-portfolio-paths.csv)",
            f"- [市场贡献](../artifacts/{stem}-market-contributions.csv)",
            f"- [类别年度贡献](../artifacts/{stem}-class-year-contributions.csv)",
            f"- [交互图](../artifacts/{stem}-interactive.html)",
            "",
        ]
    )


def self_test() -> None:
    dates = pd.bdate_range("2018-01-01", periods=1000, tz="UTC")
    x = pd.Series(np.sin(np.arange(len(dates)) / 30) + np.arange(len(dates)) / 500)
    raw = pd.DataFrame({"ts": dates, "close": 100 * np.exp(x / 10)})
    daily, monthly = market_features(raw, dates[-2])
    expected = np.sign(monthly["close"].pct_change(12, fill_method=None))
    np.testing.assert_allclose(monthly["forecast_12m"], expected, equal_nan=True)
    sigma = (
        daily["return"].shift(1).pow(2).ewm(com=60, adjust=False, min_periods=60).mean()
        * 252
    ).pow(0.5)
    np.testing.assert_allclose(daily["sigma_ann"], sigma, equal_nan=True)
    print("self-test passed")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    frames = {
        symbol: load_market(symbol, allow_untrusted=args.allow_untrusted)
        for symbol in UNIVERSE
    }
    cutoff = last_complete_month(frames)
    daily: dict[str, pd.DataFrame] = {}
    monthly: dict[str, pd.DataFrame] = {}
    for symbol, frame in frames.items():
        daily[symbol], monthly[symbol] = market_features(frame, cutoff)
    dates = pd.DatetimeIndex(
        sorted({value for frame in daily.values() for value in frame["ts"]})
    )
    returns = pd.DataFrame(index=dates)
    signals = []
    for symbol in UNIVERSE:
        returns[symbol] = daily[symbol].set_index("ts")["return"].reindex(dates)
        signal = monthly[symbol].copy()
        signal["symbol"] = symbol
        signal["asset_class"] = UNIVERSE[symbol]["class"]
        signals.append(signal)
    paths: dict[str, pd.DataFrame] = {}
    details = []
    for strategy in STRATEGIES:
        paths[strategy], detail = build_strategy_path(dates, returns, monthly, strategy)
        paths[strategy]["strategy"] = strategy
        details.append(detail)
    common_end = min(pd.Timestamp(path["ts"].iloc[-1]) for path in paths.values())
    paths = {key: value.loc[value["ts"].le(common_end)].copy() for key, value in paths.items()}
    detail = pd.concat(details, ignore_index=True)
    detail = detail.loc[pd.to_datetime(detail["ts"], utc=True).le(common_end)]
    metrics_frame = pd.DataFrame(
        [metrics(path, strategy, cost) for strategy, path in paths.items() for cost in COSTS]
    )
    yearly = period_table(paths, "year")
    monthly_returns = period_table(paths, "month")
    recent = recent_table(paths)
    market_contrib, class_year = contribution_tables(detail)
    portfolio_paths = pd.concat(paths.values(), ignore_index=True)
    signal_frame = pd.concat(signals, ignore_index=True)
    stem = f"tf-1d-fut-tsmom-p0-{args.run_date}"
    config = {
        "family": "TradFi-1D-Multi-Asset-Futures-TSMOM",
        "alias": "TF-1D-FUT-TSMOM",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "universe": UNIVERSE,
        "class_weight": CLASS_WEIGHT,
        "signal_lookbacks_months": [1, 3, 12],
        "target_volatility_asset": TARGET_VOL,
        "target_volatility_portfolio": PORTFOLIO_TARGET_VOL,
        "volatility_center_of_mass_days": VOL_COM,
        "portfolio_scalar_cap": PORTFOLIO_SCALAR_CAP,
        "gross_cap": GROSS_CAP,
        "cost_bps_one_way": list(COSTS),
        "evaluation_start": EVALUATION_START.isoformat(),
        "evaluation_end": common_end.isoformat(),
        "quality_status": "raw_unaccepted",
    }
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "config": config,
        "metrics": metrics_frame.to_dict(orient="records"),
        "limitations": json.loads(
            (ARTIFACT_DIR / f"{stem}-data-audit.json").read_text(encoding="utf-8")
        )["acceptance_blockers"],
    }
    def write(path: Path, data: str) -> None:
        path.write_text(data, encoding="utf-8")

    outputs: list[tuple[Path, bytes]] = []
    outputs.append((ARTIFACT_DIR / f"{stem}-config.json", (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode()))
    outputs.append((ARTIFACT_DIR / f"{stem}-summary.json", (json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()))
    for suffix, frame in (
        ("metrics", metrics_frame),
        ("portfolio-paths", portfolio_paths),
        ("yearly-returns", yearly),
        ("monthly-returns", monthly_returns),
        ("recent-slices", recent),
        ("market-contributions", market_contrib),
        ("class-year-contributions", class_year),
        ("month-end-signals", signal_frame),
    ):
        outputs.append((ARTIFACT_DIR / f"{stem}-{suffix}.csv", frame.to_csv(index=False).encode()))
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in outputs:
        if path.exists() and not args.force and path.read_bytes() != content:
            raise RuntimeError(f"artifact exists; use --force: {path}")
        path.write_bytes(content)
    detail_path = ARTIFACT_DIR / f"{stem}-asset-daily.parquet"
    if detail_path.exists() and not args.force:
        existing = pd.read_parquet(detail_path)
        if len(existing) != len(detail):
            raise RuntimeError(f"artifact exists; use --force: {detail_path}")
    else:
        detail.to_parquet(detail_path, index=False)
    report_text = render_report(
        args.run_date, metrics_frame, yearly, market_contrib, class_year, stem
    )
    report_path = FAMILY_DIR / "diagnostics" / f"tf-1d-fut-tsmom-p0-{args.run_date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write(report_path, report_text)
    print(
        metrics_frame.loc[
            metrics_frame["cost_bps_one_way"].eq(PRIMARY_COST),
            ["label", "cagr", "annualized_volatility", "sharpe", "max_drawdown", "net_total_return"],
        ].to_json(orient="records", force_ascii=False, indent=2)
    )
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
