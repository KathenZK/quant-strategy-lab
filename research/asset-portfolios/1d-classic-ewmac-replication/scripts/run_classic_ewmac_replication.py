"""Classic multi-asset EWMAC replication using public ETF/FX proxies.

This script is a diagnostic replication of the classic trend-following setup:
traditional asset classes only, literature-frozen EWMAC speeds/scalars, continuous
forecasts, equal-risk allocation, and a portfolio-level 10% volatility target.

It is not a strict futures total-return reproduction. The data are Yahoo Finance
adjusted OHLC proxies retained under this family's artifacts directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-classic-ewmac-replication"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
YAHOO_RAW_DIR = ARTIFACT_DIR / "yahoo_raw"

PAIRS: tuple[tuple[int, int], ...] = ((8, 32), (16, 64), (32, 128), (64, 256))
SCALARS = {(8, 32): 5.3, (16, 64): 3.75, (32, 128): 2.65, (64, 256): 1.87}
FORECAST_CAP = 20.0
MIN_PAIRS = 2
VOL_HALFLIFE = 20
SUBSYSTEM_TARGET_VOL = 0.20
PORTFOLIO_TARGET_VOL = 0.10
GROSS_CAP = 3.0
BUFFER_FRACTION = 0.10
FFILL_LIMIT = 5
ANN_DAYS = 252
PERIOD1 = 315532800  # 1980-01-01 UTC; Yahoo clips to symbol availability.
PERIOD2 = 1790000000

LEDGERS = {
    "gross_zero_cost": 0.0,
    "futures_like_2bps_side": 0.0002,
    "etf_stress_10bps_side": 0.0010,
}

CLASSIC_ASSETS: dict[str, dict[str, str]] = {
    # Equity index proxies: AQR paper uses developed equity index futures.
    "SPY": {"class": "equity_index", "name": "US S&P 500"},
    "IWM": {"class": "equity_index", "name": "US Russell 2000"},
    "QQQ": {"class": "equity_index", "name": "US Nasdaq-100"},
    "EFA": {"class": "equity_index", "name": "MSCI EAFE developed ex-US"},
    "EEM": {"class": "equity_index", "name": "MSCI Emerging Markets"},
    "EWJ": {"class": "equity_index", "name": "Japan equity"},
    "EWU": {"class": "equity_index", "name": "UK equity"},
    "EWG": {"class": "equity_index", "name": "Germany equity"},
    "EWC": {"class": "equity_index", "name": "Canada equity"},
    "EWA": {"class": "equity_index", "name": "Australia equity"},
    # Bond proxies: AQR paper uses developed bond futures.
    "SHY": {"class": "bond", "name": "US 1-3Y Treasury"},
    "IEF": {"class": "bond", "name": "US 7-10Y Treasury"},
    "TLT": {"class": "bond", "name": "US 20+Y Treasury"},
    "TIP": {"class": "bond", "name": "US TIPS"},
    # Commodity proxies: liquid ETFs/ETNs stand in for futures markets.
    "GLD": {"class": "commodity", "name": "Gold"},
    "SLV": {"class": "commodity", "name": "Silver"},
    "USO": {"class": "commodity", "name": "WTI crude oil"},
    "UNG": {"class": "commodity", "name": "Natural gas"},
    "DBC": {"class": "commodity", "name": "Broad commodities"},
    "DBA": {"class": "commodity", "name": "Agriculture basket"},
    "CORN": {"class": "commodity", "name": "Corn"},
    "WEAT": {"class": "commodity", "name": "Wheat"},
    "SOYB": {"class": "commodity", "name": "Soybeans"},
    # Currency proxies: AQR paper uses currency forwards.
    "UUP": {"class": "currency", "name": "US dollar index"},
    "FXE": {"class": "currency", "name": "Euro"},
    "FXY": {"class": "currency", "name": "Japanese yen"},
    "FXB": {"class": "currency", "name": "British pound"},
    "FXA": {"class": "currency", "name": "Australian dollar"},
    "FXC": {"class": "currency", "name": "Canadian dollar"},
    "FXF": {"class": "currency", "name": "Swiss franc"},
}

RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}
CRISIS_WINDOWS = {
    "gfc_spy_drawdown": ("2007-10-09", "2009-03-09"),
    "covid_crash": ("2020-02-19", "2020-03-23"),
    "inflation_2022": ("2022-01-03", "2022-10-12"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", default="2026-08-10")
    parser.add_argument("--refresh", action="store_true", help="re-fetch Yahoo data")
    parser.add_argument("--plot", action="store_true", help="also write an optional equity PNG")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def yahoo_url(symbol: str) -> str:
    return (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={PERIOD1}&period2={PERIOD2}&interval=1d&events=div%2Csplits"
    )


def fetch_yahoo(symbol: str, run_date: str, *, refresh: bool) -> tuple[bytes, str]:
    YAHOO_RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = YAHOO_RAW_DIR / f"{symbol}_{run_date}.json"
    url = yahoo_url(symbol)
    if raw_path.exists() and not refresh:
        return raw_path.read_bytes(), url

    last_error: Exception | None = None
    for attempt in range(4):
        if attempt:
            time.sleep(5.0 * attempt)
        try:
            completed = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    "60",
                    "--user-agent",
                    "Mozilla/5.0",
                    url,
                ],
                check=True,
                capture_output=True,
            )
            content = completed.stdout
            payload = json.loads(content)
            if payload.get("chart", {}).get("result"):
                raw_path.write_bytes(content)
                return content, url
            last_error = RuntimeError(f"empty chart result for {symbol}")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            last_error = exc
    raise RuntimeError(f"Yahoo fetch failed for {symbol}: {last_error}")


def parse_yahoo(content: bytes, symbol: str, run_date: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = json.loads(content)
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    if meta.get("symbol") != symbol:
        raise RuntimeError(f"symbol mismatch: expected {symbol}, got {meta.get('symbol')}")

    ts = pd.to_datetime(pd.Series(result["timestamp"]), unit="s", utc=True)
    tz = meta.get("exchangeTimezoneName", "America/New_York")
    days = ts.dt.tz_convert(tz).dt.normalize().dt.tz_localize(None)
    quote = result["indicators"]["quote"][0]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    frame = pd.DataFrame(
        {
            "day": days,
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "adjclose": adj,
        }
    )
    total_rows = len(frame)
    frame = frame.dropna(subset=["open", "high", "low", "close", "adjclose"])
    dropped = total_rows - len(frame)
    duplicates = int(frame["day"].duplicated().sum())
    frame = frame.loc[~frame["day"].duplicated(keep="last")].set_index("day").sort_index()
    run_day = pd.Timestamp(run_date)
    trailing_unclosed = int((frame.index >= run_day).sum())
    if trailing_unclosed:
        frame = frame.loc[frame.index < run_day]
    factor = frame["adjclose"] / frame["close"]
    adjusted = pd.DataFrame(
        {
            "open": frame["open"] * factor,
            "high": frame["high"] * factor,
            "low": frame["low"] * factor,
            "close": frame["adjclose"],
        }
    )
    ohlc_bad = int(
        (
            (frame["high"] < frame[["open", "close"]].max(axis=1) - 1e-9)
            | (frame["low"] > frame[["open", "close"]].min(axis=1) + 1e-9)
            | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        ).sum()
    )
    gaps = adjusted.index.to_series().diff().dt.days
    quality = {
        "source": "Yahoo Finance chart API",
        "url": yahoo_url(symbol),
        "raw_sha256": hashlib.sha256(content).hexdigest(),
        "symbol": meta.get("symbol"),
        "exchange": meta.get("exchangeName"),
        "currency": meta.get("currency"),
        "rows": int(len(adjusted)),
        "first_day": str(adjusted.index[0].date()),
        "last_day": str(adjusted.index[-1].date()),
        "null_rows_dropped": int(dropped),
        "duplicate_days_dropped": duplicates,
        "trailing_unclosed_days_dropped": trailing_unclosed,
        "raw_ohlc_inconsistent_rows": ohlc_bad,
        "max_session_gap_days": int(gaps.max()) if len(gaps) else 0,
        "adjustment": "OHLC scaled by adjclose/close (dividends+splits)",
    }
    if duplicates or ohlc_bad or len(adjusted) < 260:
        raise RuntimeError(f"data-quality blocker for {symbol}: {quality}")
    return adjusted, quality


def combined_forecast(close: pd.Series) -> pd.Series:
    price_vol = close.diff().ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std()
    cols = []
    for fast, slow in PAIRS:
        ema_fast = close.ewm(span=fast, min_periods=fast).mean()
        ema_slow = close.ewm(span=slow, min_periods=slow).mean()
        raw = (ema_fast - ema_slow) / price_vol
        cols.append((raw * SCALARS[(fast, slow)]).clip(-FORECAST_CAP, FORECAST_CAP))
    stacked = pd.concat(cols, axis=1)
    available = stacked.notna().sum(axis=1)
    return stacked.mean(axis=1).where(available >= MIN_PAIRS).clip(-FORECAST_CAP, FORECAST_CAP)


def build_panel(run_date: str, *, refresh: bool) -> tuple[dict[str, dict[str, pd.Series]], dict[str, Any]]:
    panel: dict[str, dict[str, pd.Series]] = {}
    quality: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    for symbol, meta in CLASSIC_ASSETS.items():
        content, url = fetch_yahoo(symbol, run_date, refresh=refresh)
        frame, q = parse_yahoo(content, symbol, run_date)
        quality[symbol] = q | {"class": meta["class"], "name": meta["name"]}
        manifest[symbol] = {"url": url, "raw_sha256": q["raw_sha256"]}
        close = frame["close"]
        ret = close.pct_change()
        sigma = ret.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std() * math.sqrt(
            ANN_DAYS
        )
        panel[symbol] = {"ret": ret, "forecast": combined_forecast(close), "sigma": sigma}
    (YAHOO_RAW_DIR / f"manifest_{run_date}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return panel, quality


def union_frames(panel: dict[str, dict[str, pd.Series]]) -> dict[str, pd.DataFrame]:
    start = min(entry["ret"].index[0] for entry in panel.values())
    end = max(entry["ret"].index[-1] for entry in panel.values())
    idx = pd.date_range(start, end, freq="D")
    ret = pd.DataFrame(index=idx)
    forecast = pd.DataFrame(index=idx)
    sigma = pd.DataFrame(index=idx)
    for symbol, entry in panel.items():
        ret[symbol] = entry["ret"].reindex(idx).fillna(0.0)
        forecast[symbol] = entry["forecast"].reindex(idx).ffill(limit=FFILL_LIMIT)
        sigma[symbol] = entry["sigma"].reindex(idx).ffill(limit=FFILL_LIMIT)
    return {"ret": ret, "forecast": forecast, "sigma": sigma}


def portfolio_targets(frames: dict[str, pd.DataFrame], assets: list[str]) -> dict[str, Any]:
    ret = frames["ret"][assets]
    fc = frames["forecast"][assets].shift(1)
    sig = frames["sigma"][assets].shift(1)
    subsystem = (fc / 10.0) * (SUBSYSTEM_TARGET_VOL / sig)
    active = subsystem.notna()
    n_active = active.sum(axis=1)
    raw = subsystem.div(n_active.where(n_active > 0), axis=0).fillna(0.0)
    unscaled = (raw * ret).sum(axis=1)
    sigma_p = (
        unscaled.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std().shift(1)
        * math.sqrt(ANN_DAYS)
    )
    scale = (PORTFOLIO_TARGET_VOL / sigma_p).where(sigma_p > 0).fillna(0.0)
    gross_raw = raw.abs().sum(axis=1)
    scale = scale.where(gross_raw * scale <= GROSS_CAP, GROSS_CAP / gross_raw).fillna(0.0)
    targets = raw.mul(scale, axis=0)
    full_size = (SUBSYSTEM_TARGET_VOL / sig).div(n_active.where(n_active > 0), axis=0).mul(
        scale, axis=0
    )
    buffers = (BUFFER_FRACTION * full_size).fillna(0.0)
    return {"targets": targets, "buffers": buffers, "active": active, "n_active": n_active}


def run_ledger(
    frames: dict[str, pd.DataFrame],
    assets: list[str],
    *,
    cost_per_side: float,
    start: pd.Timestamp,
) -> pd.DataFrame:
    built = portfolio_targets(frames, assets)
    targets = built["targets"]
    buffers = built["buffers"]
    active = built["active"]
    ret = frames["ret"][assets]
    held = {symbol: 0.0 for symbol in assets}
    rows = []

    for day in targets.index[targets.index >= start]:
        day_cost = 0.0
        turnover = 0.0
        for symbol in assets:
            if not bool(active.at[day, symbol]):
                if held[symbol] != 0.0:
                    turnover += abs(held[symbol])
                    day_cost += abs(held[symbol]) * cost_per_side
                    held[symbol] = 0.0
                continue
            target = float(targets.at[day, symbol])
            if abs(target - held[symbol]) >= float(buffers.at[day, symbol]):
                traded = abs(target - held[symbol])
                turnover += traded
                day_cost += traded * cost_per_side
                held[symbol] = target

        gross = sum(abs(v) for v in held.values())
        if gross > GROSS_CAP:
            shrink = GROSS_CAP / gross
            for symbol in assets:
                delta = abs(held[symbol]) * (1.0 - shrink)
                turnover += delta
                day_cost += delta * cost_per_side
                held[symbol] *= shrink
            gross = GROSS_CAP

        contrib = {symbol: held[symbol] * float(ret.at[day, symbol]) for symbol in assets}
        rows.append(
            {
                "day": day,
                "net": sum(contrib.values()) - day_cost,
                "cost": -day_cost,
                "turnover": turnover,
                "gross": gross,
                **{f"pnl_{symbol}": value for symbol, value in contrib.items()},
            }
        )
    return pd.DataFrame(rows).set_index("day")


def drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def metrics(path: pd.DataFrame) -> dict[str, Any]:
    net = path["net"]
    equity = (1.0 + net).cumprod()
    years = max((net.index[-1] - net.index[0]).days / 365.25, 1e-9)
    vol = float(net.std() * math.sqrt(ANN_DAYS))
    sharpe = float(net.mean() / net.std() * math.sqrt(ANN_DAYS)) if net.std() > 0 else math.nan
    yearly = equity.groupby(equity.index.year).last()
    prev = yearly.shift(1)
    prev.iloc[0] = 1.0
    return {
        "window": [str(net.index[0].date()), str(net.index[-1].date())],
        "years": round(years, 2),
        "total_net_return": round(float(equity.iloc[-1] - 1.0), 4),
        "cagr": round(float(equity.iloc[-1] ** (1.0 / years) - 1.0), 4),
        "realized_ann_vol": round(vol, 4),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(drawdown(equity), 4),
        "ann_one_way_turnover": round(float(path["turnover"].sum() / years), 2),
        "cost_drag_per_year": round(float(-path["cost"].sum() / years), 4),
        "avg_gross_leverage": round(float(path["gross"].mean()), 3),
        "max_gross_leverage": round(float(path["gross"].max()), 3),
        "yearly_net": {
            str(year): round(float(value / prev_value - 1.0), 4)
            for (year, value), prev_value in zip(yearly.items(), prev)
        },
    }


def recent_rows(path: pd.DataFrame, ledger: str) -> list[dict[str, Any]]:
    equity = (1.0 + path["net"]).cumprod()
    end = equity.index[-1]
    rows = []
    for label, days in RECENT_SLICES.items():
        base = equity.loc[: end - pd.Timedelta(days=days)]
        if not base.empty:
            rows.append(
                {
                    "ledger": ledger,
                    "slice": label,
                    "net_return": round(float(equity.iloc[-1] / base.iloc[-1] - 1.0), 4),
                }
            )
    return rows


def benchmark_returns(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    ret = frames["ret"]
    return {
        "SPY": ret["SPY"],
        "IEF": ret["IEF"],
        "daily_60_40_spy_ief": 0.60 * ret["SPY"] + 0.40 * ret["IEF"],
    }


def simple_stats(ret: pd.Series) -> dict[str, float]:
    ret = ret.dropna()
    equity = (1.0 + ret).cumprod()
    years = max((ret.index[-1] - ret.index[0]).days / 365.25, 1e-9)
    return {
        "total_return": round(float(equity.iloc[-1] - 1.0), 4),
        "cagr": round(float(equity.iloc[-1] ** (1.0 / years) - 1.0), 4),
        "sharpe": round(float(ret.mean() / ret.std() * math.sqrt(ANN_DAYS)), 3)
        if ret.std() > 0
        else math.nan,
        "max_drawdown": round(drawdown(equity), 4),
    }


def crisis_rows(path: pd.DataFrame, frames: dict[str, pd.DataFrame], ledger: str) -> list[dict[str, Any]]:
    rows = []
    bench = benchmark_returns(frames)
    for name, (start, end) in CRISIS_WINDOWS.items():
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        sub = path.loc[(path.index >= s) & (path.index <= e)]
        if sub.empty:
            continue
        strat = simple_stats(sub["net"])
        rows.append({"ledger": ledger, "window": name, "series": "strategy", **strat})
        for bname, ret in bench.items():
            bsub = ret.loc[sub.index]
            rows.append({"ledger": ledger, "window": name, "series": bname, **simple_stats(bsub)})
    return rows


def average_pairwise_correlation(path: pd.DataFrame, assets: list[str]) -> float:
    cols = [f"pnl_{symbol}" for symbol in assets]
    frame = path[cols].rename(columns=lambda x: x.replace("pnl_", ""))
    frame = frame.loc[:, frame.std() > 0]
    corr = frame.corr().to_numpy()
    n = corr.shape[0]
    if n < 2:
        return math.nan
    return round(float((corr.sum() - n) / (n * (n - 1))), 3)


def class_contribution(path: pd.DataFrame, assets: list[str]) -> pd.DataFrame:
    contrib = pd.DataFrame({symbol: path[f"pnl_{symbol}"] for symbol in assets})
    classes = pd.Index([CLASSIC_ASSETS[symbol]["class"] for symbol in assets])
    return contrib.T.groupby(classes).sum().T


def self_test() -> None:
    rng = np.random.default_rng(17)
    idx = pd.date_range("2010-01-01", periods=1600, freq="D")
    close = pd.Series(
        100.0 * np.exp(np.cumsum(0.0005 + rng.normal(0.0, 0.01, len(idx)))),
        index=idx,
    )
    forecast = combined_forecast(close)
    assert forecast.abs().max() <= FORECAST_CAP + 1e-12
    assert forecast.dropna().iloc[-1] > 0.0
    print("self-test passed")


def clean_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if not math.isfinite(float(obj)) else float(obj)
    return obj


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    panel, quality = build_panel(args.run_date, refresh=args.refresh)
    assets = list(panel)
    frames = union_frames(panel)
    built = portfolio_targets(frames, assets)
    n_active = built["n_active"]
    main_start = n_active[n_active >= 12].index[0]

    summary: dict[str, Any] = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/xa-1d-classic-ewmac-replication-contract-2026-08-10.md",
        "paper_reference": {
            "aqr": "Hurst, Ooi, Pedersen (2017), A Century of Evidence on Trend-Following Investing",
            "carver": "Robert Carver Systematic Trading EWMAC forecast scalar table",
        },
        "replication_limits": [
            "Uses public ETF/FX adjusted-close proxies, not rolled futures total returns.",
            "Uses daily Carver-style EWMAC continuous forecasts, not the paper's monthly 1/3/12-month sign signals.",
            "No financing, borrow, tax, futures roll yield, or management/performance fee model.",
        ],
        "assets": CLASSIC_ASSETS,
        "params": {
            "pairs": [list(pair) for pair in PAIRS],
            "forecast_scalars": {f"{fast}_{slow}": SCALARS[(fast, slow)] for fast, slow in PAIRS},
            "forecast_cap": FORECAST_CAP,
            "min_pairs": MIN_PAIRS,
            "vol_halflife": VOL_HALFLIFE,
            "subsystem_target_vol": SUBSYSTEM_TARGET_VOL,
            "portfolio_target_vol": PORTFOLIO_TARGET_VOL,
            "gross_cap": GROSS_CAP,
            "buffer_fraction": BUFFER_FRACTION,
            "ffill_limit_days": FFILL_LIMIT,
            "main_start_min_active": 12,
        },
        "data_quality": quality,
        "windows": {"main_start": str(main_start.date()), "data_end": str(frames["ret"].index[-1].date())},
        "ledgers": {},
    }

    benchmark = benchmark_returns(frames)
    recent: list[dict[str, Any]] = []
    crisis: list[dict[str, Any]] = []
    yearly: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    equity_curves: dict[str, pd.Series] = {}
    class_yearly_rows: list[pd.DataFrame] = []

    for ledger, cost in LEDGERS.items():
        path = run_ledger(frames, assets, cost_per_side=cost, start=main_start)
        m = metrics(path)
        m["avg_pairwise_subsystem_corr"] = average_pairwise_correlation(path, assets)
        for bench_name, bench_ret in benchmark.items():
            aligned = bench_ret.loc[path.index]
            m[f"corr_vs_{bench_name}"] = round(float(path["net"].corr(aligned)), 3)
            m[f"combo_80_60_40_20_strategy_{bench_name}"] = simple_stats(
                0.80 * aligned + 0.20 * path["net"]
            )
        summary["ledgers"][ledger] = m
        metrics_rows.append(
            {"ledger": ledger, **{k: v for k, v in m.items() if not isinstance(v, dict)}}
        )
        yearly.extend(
            {"ledger": ledger, "year": year, "net_return": value}
            for year, value in m["yearly_net"].items()
        )
        recent.extend(recent_rows(path, ledger))
        crisis.extend(crisis_rows(path, frames, ledger))
        equity_curves[ledger] = (1.0 + path["net"]).cumprod()
        class_yearly = class_contribution(path, assets).groupby(path.index.year).sum().round(4)
        class_yearly["ledger"] = ledger
        class_yearly["year"] = class_yearly.index
        class_yearly_rows.append(class_yearly.reset_index(drop=True))

    for name, ret in benchmark.items():
        summary.setdefault("benchmarks", {})[name] = simple_stats(ret.loc[main_start:])

    prefix = f"xa_1d_classic_ewmac_replication_{args.run_date}"
    (ARTIFACT_DIR / f"{prefix}_summary.json").write_text(
        json.dumps(clean_json(summary), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pd.DataFrame(metrics_rows).to_csv(ARTIFACT_DIR / f"{prefix}_metrics.csv", index=False)
    pd.DataFrame(yearly).to_csv(ARTIFACT_DIR / f"{prefix}_yearly.csv", index=False)
    pd.DataFrame(recent).to_csv(ARTIFACT_DIR / f"{prefix}_recent.csv", index=False)
    pd.DataFrame(crisis).to_csv(ARTIFACT_DIR / f"{prefix}_crisis.csv", index=False)
    pd.concat(class_yearly_rows, ignore_index=True).to_csv(
        ARTIFACT_DIR / f"{prefix}_class_yearly.csv", index=False
    )
    pd.DataFrame(equity_curves).reset_index(names="day").to_parquet(
        ARTIFACT_DIR / f"{prefix}_equity.parquet", index=False
    )

    if args.plot:
        matplotlib = importlib.import_module("matplotlib")
        matplotlib.use("Agg")
        plt = importlib.import_module("matplotlib.pyplot")

        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        gross = equity_curves["gross_zero_cost"]
        low_cost = equity_curves["futures_like_2bps_side"]
        stress = equity_curves["etf_stress_10bps_side"]
        spy = (1.0 + benchmark["SPY"].loc[gross.index]).cumprod()
        sixty_forty = (1.0 + benchmark["daily_60_40_spy_ief"].loc[gross.index]).cumprod()
        axes[0].plot(gross.index, gross, label="EWMAC gross", lw=1.2)
        axes[0].plot(low_cost.index, low_cost, label="EWMAC 2bps/side", lw=1.0)
        axes[0].plot(stress.index, stress, label="EWMAC 10bps/side", lw=1.0)
        axes[0].plot(spy.index, spy, label="SPY", lw=0.8, alpha=0.6)
        axes[0].plot(sixty_forty.index, sixty_forty, label="60/40 SPY/IEF", lw=0.8, alpha=0.6)
        axes[0].set_yscale("log")
        axes[0].legend()
        axes[0].grid(alpha=0.3)
        axes[1].plot(stress.index, stress / stress.cummax() - 1.0, color="tab:red", lw=0.9)
        axes[1].set_ylabel("10bps drawdown")
        axes[1].grid(alpha=0.3)
        active = built["n_active"].loc[gross.index]
        axes[2].plot(active.index, active, lw=0.8)
        axes[2].set_ylabel("active assets")
        axes[2].grid(alpha=0.3)
        fig.suptitle("Classic EWMAC replication: traditional asset ETF/FX proxies")
        fig.tight_layout()
        fig.savefig(ARTIFACT_DIR / f"{prefix}_equity.png", dpi=150)

    print(json.dumps(clean_json(summary["ledgers"]), indent=2, ensure_ascii=False))
    print("summary ->", ARTIFACT_DIR / f"{prefix}_summary.json")


if __name__ == "__main__":
    main()
