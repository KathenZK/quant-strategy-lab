"""XA-1D-EWMAC-UT: literature-frozen EWMAC ensemble, universal parameters.

Executes the pre-registered contract in
specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md:

  signal   EWMAC pairs (8,32)/(16,64)/(32,128)/(64,256), Carver scalars
           5.3/3.75/2.65/1.87, cap +-20, equal-weight mean of usable pairs
           (pair usable after slow-span days; >=2 pairs required, else flat)
  sizing   w = (F/10) * (20% / sigma_ann), |w| <= 2.0, EWMA hl=20 vol
  buffer   trade only when |w* - w_held| >= 0.10 * (20% / sigma_ann)
  crypto   Binance USDT perp 1d resampled from audited 15m lake (dedup
           prefers binance_vision_kline_monthly), fee 0.001 + slip 4bps
           per side, daily as-of funding as pure cost, annualizer 365
  tradfi   Yahoo daily ETFs (QQQ/SPY/SOXX/GLD/SLV/SOYB), adjclose-scaled
           OHLC, primary zero cost + 10bps/side sensitivity, annualizer 252

No parameter below was tuned on repository data; all constants are frozen
in the contract before any backtest was run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ewmac-universal-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
YAHOO_RAW_DIR = ARTIFACT_DIR / "yahoo_raw"
K15_ROOT = ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
FUNDING_ROOT = ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"

# --- frozen contract constants ---------------------------------------------
PAIRS: tuple[tuple[int, int], ...] = ((8, 32), (16, 64), (32, 128), (64, 256))
SCALARS = {(8, 32): 5.3, (16, 64): 3.75, (32, 128): 2.65, (64, 256): 1.87}
FORECAST_CAP = 20.0
MIN_PAIRS = 2
VOL_HALFLIFE = 20
TARGET_VOL = 0.20
WEIGHT_CAP = 2.0
BUFFER_FRACTION = 0.10
CRYPTO_COST_PER_SIDE = 0.001 + 0.0004
TRADFI_SENSITIVITY_PER_SIDE = 0.0010
CRYPTO_ANN_DAYS = 365
TRADFI_ANN_DAYS = 252
PERIOD1 = 631152000  # 1990-01-01 UTC
PERIOD2 = 1790000000

CRYPTO_ASSETS = ("BTC", "ETH", "HYPE")
GATED_CRYPTO = ("BTC", "ETH")
TRADFI_ASSETS = {
    "QQQ": "Invesco QQQ (Nasdaq-100)",
    "SPY": "SPDR S&P 500",
    "SOXX": "iShares Semiconductor (PHLX SOX)",
    "GLD": "SPDR Gold Shares",
    "SLV": "iShares Silver Trust",
    "SOYB": "Teucrium Soybean",
}

RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", default="2026-08-05")
    parser.add_argument("--refresh", action="store_true", help="re-fetch Yahoo data")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


# --- crypto data -------------------------------------------------------------


def load_crypto_daily() -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute("SET enable_progress_bar=false")
    symbols = ", ".join(f"'{s}'" for s in CRYPTO_ASSETS)
    frame = con.execute(
        f"""
        WITH rows AS (
            SELECT
                replace(symbol, '/USDT:USDT', '') AS sym,
                ts, open, high, low, close, quote_volume,
                row_number() OVER (
                    PARTITION BY replace(symbol, '/USDT:USDT', ''), ts
                    ORDER BY CASE
                        WHEN source = 'binance_vision_kline_monthly' THEN 0 ELSE 1
                    END
                ) AS rn
            FROM read_parquet('{K15_ROOT}/**/*.parquet', union_by_name=true)
            WHERE replace(symbol, '/USDT:USDT', '') IN ({symbols})
        )
        SELECT
            sym,
            time_bucket(INTERVAL '1 day', ts) AS day,
            arg_min(open, ts) AS open,
            max(high) AS high,
            min(low) AS low,
            arg_max(close, ts) AS close,
            sum(quote_volume) AS quote_volume,
            count(*) AS bars_15m
        FROM rows
        WHERE rn = 1
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    ).fetch_df()
    frame["day"] = pd.to_datetime(frame["day"]).dt.tz_localize(None)

    books: dict[str, pd.DataFrame] = {}
    quality: dict[str, Any] = {}
    for sym in CRYPTO_ASSETS:
        sub = frame.loc[frame["sym"] == sym].set_index("day").sort_index()
        # drop leading/trailing partial days (contract: incomplete boundary days)
        while len(sub) and sub["bars_15m"].iloc[0] < 96:
            sub = sub.iloc[1:]
        while len(sub) and sub["bars_15m"].iloc[-1] < 96:
            sub = sub.iloc[:-1]
        full_range = pd.date_range(sub.index[0], sub.index[-1], freq="D")
        missing_days = int(len(full_range) - len(sub))
        partial_days = int((sub["bars_15m"] < 96).sum())
        ohlc_bad = int(
            (
                (sub["high"] < sub[["open", "close"]].max(axis=1))
                | (sub["low"] > sub[["open", "close"]].min(axis=1))
                | (sub[["open", "high", "low", "close"]] <= 0).any(axis=1)
            ).sum()
        )
        null_rows = int(sub[["open", "high", "low", "close"]].isna().any(axis=1).sum())
        quality[sym] = {
            "rows": int(len(sub)),
            "first_day": str(sub.index[0].date()),
            "last_day": str(sub.index[-1].date()),
            "missing_whole_days": missing_days,
            "interior_partial_days": partial_days,
            "ohlc_invalid_rows": ohlc_bad,
            "null_rows": null_rows,
        }
        if missing_days or ohlc_bad or null_rows:
            raise RuntimeError(f"crypto data quality blocker for {sym}: {quality[sym]}")
        books[sym] = sub
    return books, quality


def load_crypto_funding() -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    symbols = ", ".join(f"'{s}'" for s in CRYPTO_ASSETS)
    frame = con.execute(
        f"""
        WITH rows AS (
            SELECT
                replace(symbol, '/USDT:USDT', '') AS sym,
                ts, funding_rate,
                row_number() OVER (
                    PARTITION BY replace(symbol, '/USDT:USDT', ''), ts
                    ORDER BY CASE
                        WHEN source = 'binance_vision_monthly' THEN 0 ELSE 1
                    END
                ) AS rn
            FROM read_parquet('{FUNDING_ROOT}/**/*.parquet', union_by_name=true)
            WHERE replace(symbol, '/USDT:USDT', '') IN ({symbols})
        )
        SELECT sym, time_bucket(INTERVAL '1 day', ts) AS day,
               sum(funding_rate) AS funding_rate
        FROM rows WHERE rn = 1
        GROUP BY 1, 2
        """
    ).fetch_df()
    frame["day"] = pd.to_datetime(frame["day"]).dt.tz_localize(None)
    return frame.pivot(index="day", columns="sym", values="funding_rate")


# --- tradfi data -------------------------------------------------------------


def yahoo_url(symbol: str) -> str:
    return (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={PERIOD1}&period2={PERIOD2}"
        "&interval=1d&events=div%2Csplits"
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
                    "curl", "--fail", "--location", "--silent", "--show-error",
                    "--max-time", "60", "--user-agent", "Mozilla/5.0", url,
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
    raise RuntimeError(f"yahoo fetch failed for {symbol}: {last_error}")


def parse_yahoo(content: bytes, symbol: str) -> tuple[pd.DataFrame, dict[str, Any]]:
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
    dup = int(frame["day"].duplicated().sum())
    frame = frame.loc[~frame["day"].duplicated(keep="last")].set_index("day").sort_index()
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
        "duplicate_days_dropped": dup,
        "raw_ohlc_inconsistent_rows": ohlc_bad,
        "max_session_gap_days": int(gaps.max()) if len(gaps) else 0,
        "adjustment": "OHLC scaled by adjclose/close (dividends+splits)",
    }
    return adjusted, quality


# --- signal + backtest --------------------------------------------------------


def combined_forecast(close: pd.Series) -> pd.Series:
    price_vol = close.diff().ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std()
    pair_forecasts = []
    for fast, slow in PAIRS:
        ema_fast = close.ewm(span=fast, min_periods=fast).mean()
        ema_slow = close.ewm(span=slow, min_periods=slow).mean()
        raw = (ema_fast - ema_slow) / price_vol
        pair_forecasts.append((raw * SCALARS[(fast, slow)]).clip(-FORECAST_CAP, FORECAST_CAP))
    stacked = pd.concat(pair_forecasts, axis=1)
    available = stacked.notna().sum(axis=1)
    return stacked.mean(axis=1).where(available >= MIN_PAIRS).clip(-FORECAST_CAP, FORECAST_CAP)


def backtest(
    close: pd.Series,
    *,
    ann_days: int,
    cost_per_side: float,
    funding_daily: pd.Series | None = None,
) -> pd.DataFrame:
    ret = close.pct_change()
    sigma_ann = ret.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std() * math.sqrt(
        ann_days
    )
    forecast = combined_forecast(close).shift(1)
    sigma_lag = sigma_ann.shift(1)
    w_full = (TARGET_VOL / sigma_lag).where(sigma_lag > 0)
    w_target = (forecast / 10.0 * w_full).clip(-WEIGHT_CAP, WEIGHT_CAP)
    buffer = BUFFER_FRACTION * w_full

    funding = (
        funding_daily.reindex(close.index).fillna(0.0)
        if funding_daily is not None
        else pd.Series(0.0, index=close.index)
    )

    valid = w_target.notna() & buffer.notna()
    if not valid.any():
        raise RuntimeError("no valid evaluation window")
    start = valid.idxmax()

    idx = close.index[close.index >= start]
    w_held = 0.0
    records = []
    for day in idx:
        target = w_target.loc[day]
        if math.isfinite(target) and abs(target - w_held) >= buffer.loc[day]:
            traded = abs(target - w_held)
            w_held = float(target)
        else:
            traded = 0.0
        day_ret = ret.loc[day]
        day_ret = day_ret if math.isfinite(day_ret) else 0.0
        cost = traded * cost_per_side
        funding_pnl = -w_held * funding.loc[day]
        net = w_held * day_ret - cost + funding_pnl
        records.append(
            {
                "day": day,
                "w_held": w_held,
                "traded": traded,
                "price_pnl": w_held * day_ret,
                "cost": -cost,
                "funding_pnl": funding_pnl,
                "net": net,
                "asset_ret": day_ret,
            }
        )
    return pd.DataFrame(records).set_index("day")


def drawdown(curve: pd.Series) -> float:
    return float((curve / curve.cummax() - 1.0).min())


def metrics(path: pd.DataFrame, *, ann_days: int) -> dict[str, Any]:
    net = path["net"]
    equity = (1.0 + net).cumprod()
    n_years = max((net.index[-1] - net.index[0]).days / 365.25, 1e-9)
    vol = float(net.std() * math.sqrt(ann_days))
    sharpe = float(net.mean() / net.std() * math.sqrt(ann_days)) if net.std() > 0 else math.nan
    total = float(equity.iloc[-1] - 1.0)
    hold = (1.0 + path["asset_ret"]).cumprod()
    hold_ret = path["asset_ret"]
    yearly = equity.groupby(equity.index.year).last()
    yearly_prev = yearly.shift(1)
    yearly_prev.iloc[0] = 1.0
    return {
        "window": [str(net.index[0].date()), str(net.index[-1].date())],
        "years": round(n_years, 2),
        "total_net_return": round(total, 4),
        "cagr": round(float((1.0 + total) ** (1.0 / n_years) - 1.0), 4),
        "realized_ann_vol": round(vol, 4),
        "sharpe_net": round(sharpe, 3),
        "max_drawdown": round(drawdown(equity), 4),
        "yearly_net": {str(y): round(float(v / p - 1.0), 4) for (y, v), p in zip(yearly.items(), yearly_prev)},
        "ann_one_way_turnover": round(float(path["traded"].sum() / n_years), 2),
        "cost_drag_per_year": round(float(-path["cost"].sum() / n_years), 4),
        "funding_drag_per_year": round(float(-path["funding_pnl"].sum() / n_years), 4),
        "avg_abs_weight": round(float(path["w_held"].abs().mean()), 3),
        "max_abs_weight": round(float(path["w_held"].abs().max()), 3),
        "buy_hold": {
            "total_return": round(float(hold.iloc[-1] - 1.0), 4),
            "realized_ann_vol": round(float(hold_ret.std() * math.sqrt(ann_days)), 4),
            "sharpe": round(
                float(hold_ret.mean() / hold_ret.std() * math.sqrt(ann_days))
                if hold_ret.std() > 0
                else math.nan,
                3,
            ),
            "max_drawdown": round(drawdown(hold), 4),
        },
    }


def recent_rows(path: pd.DataFrame, asset: str, variant: str) -> list[dict[str, Any]]:
    equity = (1.0 + path["net"]).cumprod()
    end = equity.index[-1]
    rows = []
    for label, days in RECENT_SLICES.items():
        start = end - pd.Timedelta(days=days)
        base = equity.loc[:start]
        if base.empty:
            continue
        rows.append(
            {
                "asset": asset,
                "variant": variant,
                "slice": label,
                "net_return": round(float(equity.iloc[-1] / base.iloc[-1] - 1.0), 4),
            }
        )
    return rows


# --- self test ----------------------------------------------------------------


def self_test() -> None:
    rng = np.random.default_rng(7)
    n = 1500
    trend = np.cumsum(np.full(n, 0.001) + rng.normal(0, 0.01, n))
    close = pd.Series(
        100.0 * np.exp(trend),
        index=pd.date_range("2020-01-01", periods=n, freq="D"),
    )
    path = backtest(close, ann_days=365, cost_per_side=0.0014)
    assert path["w_held"].iloc[-1] > 0, "uptrend must end long"
    assert (1.0 + path["net"]).prod() > 1.0, "uptrend must be profitable"
    m = metrics(path, ann_days=365)
    assert m["ann_one_way_turnover"] < 40, "buffer must bound turnover"
    fc = combined_forecast(close)
    assert fc.abs().max() <= FORECAST_CAP + 1e-9
    down = pd.Series(
        100.0 * np.exp(-trend),
        index=close.index,
    )
    path_down = backtest(down, ann_days=365, cost_per_side=0.0014)
    assert path_down["w_held"].iloc[-1] < 0, "downtrend must end short"
    print("self-test passed")


# --- main ---------------------------------------------------------------------


def clean_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if not math.isfinite(float(obj)) else float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    return obj


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = args.run_date

    books, crypto_quality = load_crypto_daily()
    funding = load_crypto_funding()

    summary: dict[str, Any] = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md",
        "params": {
            "pairs": [list(p) for p in PAIRS],
            "forecast_scalars": {f"{f}_{s}": SCALARS[(f, s)] for f, s in PAIRS},
            "forecast_cap": FORECAST_CAP,
            "min_pairs": MIN_PAIRS,
            "vol_halflife": VOL_HALFLIFE,
            "target_vol": TARGET_VOL,
            "weight_cap": WEIGHT_CAP,
            "buffer_fraction": BUFFER_FRACTION,
            "crypto_cost_per_side": CRYPTO_COST_PER_SIDE,
            "tradfi_sensitivity_per_side": TRADFI_SENSITIVITY_PER_SIDE,
        },
        "data_quality": {"crypto": crypto_quality, "tradfi": {}},
        "assets": {},
        "gates": {},
    }
    metric_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    equity_frames: dict[str, pd.DataFrame] = {}

    for sym in CRYPTO_ASSETS:
        close = books[sym]["close"]
        fseries = funding[sym] if sym in funding.columns else None
        path = backtest(
            close,
            ann_days=CRYPTO_ANN_DAYS,
            cost_per_side=CRYPTO_COST_PER_SIDE,
            funding_daily=fseries,
        )
        m = metrics(path, ann_days=CRYPTO_ANN_DAYS)
        held_days = int((path["w_held"].abs() > 0).sum())
        covered = (
            int(((path["w_held"].abs() > 0) & fseries.reindex(path.index).notna()).sum())
            if fseries is not None
            else 0
        )
        m["funding_coverage_held_days"] = round(covered / held_days, 4) if held_days else None
        summary["assets"][sym] = {
            "class": "crypto",
            "market": "Binance USDT perp 1d (from audited 15m lake)",
            "cost_model": "fee 0.001 + slip 4bps per side + daily as-of funding",
            "net": m,
        }
        metric_rows.append({"asset": sym, "variant": "net_default_cost", **flatten(m)})
        yearly_rows.extend(
            {"asset": sym, "variant": "net_default_cost", "year": y, "net_return": v}
            for y, v in m["yearly_net"].items()
        )
        recent.extend(recent_rows(path, sym, "net_default_cost"))
        equity_frames[sym] = pd.DataFrame(
            {
                "strategy": (1.0 + path["net"]).cumprod(),
                "buy_hold": (1.0 + path["asset_ret"]).cumprod(),
            }
        )

    yahoo_manifest = {}
    for sym, desc in TRADFI_ASSETS.items():
        content, url = fetch_yahoo(sym, run_date, refresh=args.refresh)
        frame, quality = parse_yahoo(content, sym)
        summary["data_quality"]["tradfi"][sym] = quality
        yahoo_manifest[sym] = {"url": url, "raw_sha256": quality["raw_sha256"]}
        close = frame["close"]
        variants = {
            "net_zero_cost": 0.0,
            "net_10bps_side": TRADFI_SENSITIVITY_PER_SIDE,
        }
        asset_entry: dict[str, Any] = {
            "class": "tradfi_etf",
            "name": desc,
            "market": "Yahoo daily, adjclose-scaled OHLC (diagnostic, not a live venue)",
            "cost_model": "primary zero cost + 10bps/side sensitivity; "
            "no financing/borrow/tax",
        }
        for variant, cost in variants.items():
            path = backtest(close, ann_days=TRADFI_ANN_DAYS, cost_per_side=cost)
            m = metrics(path, ann_days=TRADFI_ANN_DAYS)
            asset_entry[variant] = m
            metric_rows.append({"asset": sym, "variant": variant, **flatten(m)})
            yearly_rows.extend(
                {"asset": sym, "variant": variant, "year": y, "net_return": v}
                for y, v in m["yearly_net"].items()
            )
            recent.extend(recent_rows(path, sym, variant))
            if variant == "net_zero_cost":
                equity_frames[sym] = pd.DataFrame(
                    {
                        "strategy": (1.0 + path["net"]).cumprod(),
                        "buy_hold": (1.0 + path["asset_ret"]).cumprod(),
                    }
                )
        summary["assets"][sym] = asset_entry

    # --- gates -----------------------------------------------------------------
    crypto_gates = {}
    for sym in GATED_CRYPTO:
        m = summary["assets"][sym]["net"]
        crypto_gates[sym] = {
            "G1_total_net_positive": m["total_net_return"] > 0,
            "G2_sharpe_ge_0p5": m["sharpe_net"] >= 0.5,
            "G3_mdd_lt_40pct": m["max_drawdown"] > -0.40,
            "G4_turnover_le_15x": m["ann_one_way_turnover"] <= 15.0,
        }
    tradfi_gates = {}
    for sym in TRADFI_ASSETS:
        zero = summary["assets"][sym]["net_zero_cost"]
        sens = summary["assets"][sym]["net_10bps_side"]
        tradfi_gates[sym] = {
            "V1_positive_at_0_and_10bps": zero["total_net_return"] > 0
            and sens["total_net_return"] > 0,
            "V2_sharpe_ge_0p3": zero["sharpe_net"] >= 0.3,
            "V3_mdd_lt_40pct": zero["max_drawdown"] > -0.40,
        }
    crypto_pass = all(all(g.values()) for g in crypto_gates.values())
    tradfi_pass_count = sum(all(g.values()) for g in tradfi_gates.values())
    summary["gates"] = {
        "crypto_per_asset": crypto_gates,
        "crypto_universal_pass": crypto_pass,
        "tradfi_per_asset": tradfi_gates,
        "tradfi_pass_count": f"{tradfi_pass_count}/{len(TRADFI_ASSETS)}",
        "tradfi_broad_fail": tradfi_pass_count <= len(TRADFI_ASSETS) - 4,
    }
    summary["yahoo_manifest"] = yahoo_manifest

    # --- artifacts ---------------------------------------------------------------
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"xa_1d_ewmac_ut_metrics_{run_date}.csv", index=False
    )
    pd.DataFrame(yearly_rows).to_csv(
        ARTIFACT_DIR / f"xa_1d_ewmac_ut_yearly_{run_date}.csv", index=False
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"xa_1d_ewmac_ut_recent_{run_date}.csv", index=False
    )
    (YAHOO_RAW_DIR / f"manifest_{run_date}.json").write_text(
        json.dumps(yahoo_manifest, indent=2), encoding="utf-8"
    )

    curves = pd.concat(
        {sym: df for sym, df in equity_frames.items()}, axis=1, sort=True
    )
    curves.columns = ["_".join(c) for c in curves.columns]
    curves.reset_index(names="day").to_parquet(
        ARTIFACT_DIR / f"xa_1d_ewmac_ut_equity_{run_date}.parquet", index=False
    )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    assets = list(equity_frames)
    fig, axes = plt.subplots(3, 3, figsize=(15, 10))
    for ax, sym in zip(axes.flat, assets):
        df = equity_frames[sym]
        ax.plot(df.index, df["strategy"], lw=1.2, label="EWMAC net")
        ax.plot(df.index, df["buy_hold"], lw=0.8, alpha=0.6, label="buy&hold")
        ax.set_yscale("log")
        ax.set_title(sym)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    for ax in axes.flat[len(assets):]:
        ax.axis("off")
    fig.suptitle("XA-1D-EWMAC-UT: literature-frozen EWMAC vs buy&hold (log equity)")
    fig.tight_layout()
    fig.savefig(ARTIFACT_DIR / f"xa_1d_ewmac_ut_equity_{run_date}.png", dpi=150)

    out = ARTIFACT_DIR / f"xa_1d_ewmac_ut_summary_{run_date}.json"
    out.write_text(
        json.dumps(clean_json(summary), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(clean_json(summary["gates"]), indent=2, ensure_ascii=False))
    for sym in summary["assets"]:
        key = "net" if "net" in summary["assets"][sym] else "net_zero_cost"
        m = summary["assets"][sym][key]
        print(
            f"{sym:5s} {key:14s} total={m['total_net_return']:+.2%} "
            f"sharpe={m['sharpe_net']:.2f} mdd={m['max_drawdown']:.2%} "
            f"turnover={m['ann_one_way_turnover']:.1f}x "
            f"hold={m['buy_hold']['total_return']:+.2%}"
        )
    print("report ->", out)


def flatten(m: dict[str, Any]) -> dict[str, Any]:
    flat = {k: v for k, v in m.items() if not isinstance(v, dict)}
    flat["window_start"], flat["window_end"] = m["window"]
    del flat["window"]
    for k, v in m["buy_hold"].items():
        flat[f"buy_hold_{k}"] = v
    return flat


if __name__ == "__main__":
    main()
