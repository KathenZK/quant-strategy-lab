from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BINANCE_ROOT = Path(
    "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
YAHOO_PATH = Path(
    "data/external/us_equities/yahoo/symbol=mu/timeframe=15m/"
    "mu_15m_60d_include_prepost.parquet"
)
SUMMARY_PATH = Path("reports/mu_binance_yahoo_15m_alignment.json")
ALIGNED_PATH = Path("reports/mu_binance_yahoo_15m_aligned.csv")
BUCKET_PATH = Path("reports/mu_binance_yahoo_15m_alignment_by_session.csv")


def pct(value: float) -> float:
    return round(value * 100.0, 4)


def bps(value: float) -> float:
    return round(value * 10000.0, 2)


def load_binance() -> pd.DataFrame:
    files = sorted(BINANCE_ROOT.rglob("symbol=mu_usdt_usdt.parquet"))
    if not files:
        raise FileNotFoundError(f"no Binance MUUSDT parquet under {BINANCE_ROOT}")
    frame = pd.concat(
        [
            pd.read_parquet(
                path,
                columns=["ts", "open", "high", "low", "close", "volume"],
            )
            for path in files
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.floor("15min")
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame


def load_yahoo() -> pd.DataFrame:
    if not YAHOO_PATH.exists():
        raise FileNotFoundError(f"missing Yahoo 15m parquet: {YAHOO_PATH}")
    frame = pd.read_parquet(YAHOO_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.floor("15min")
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame


def ny_session_bucket(ts: pd.Series) -> pd.Series:
    local = pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(
        "America/New_York"
    )
    minutes = local.hour * 60 + local.minute
    bucket = np.full(len(local), "other", dtype=object)
    bucket[(minutes >= 4 * 60) & (minutes < 9 * 60 + 30)] = "premarket"
    bucket[(minutes >= 9 * 60 + 30) & (minutes < 16 * 60)] = "regular"
    bucket[(minutes >= 16 * 60) & (minutes < 20 * 60)] = "afterhours"
    bucket[(minutes >= 20 * 60) | (minutes < 4 * 60)] = "overnight"
    return pd.Series(bucket, index=ts.index)


def summarize_returns(frame: pd.DataFrame) -> dict[str, Any]:
    working = frame.dropna(subset=["binance_ret", "yahoo_ret"]).copy()
    working = working[
        np.isfinite(working.binance_ret.to_numpy("float64"))
        & np.isfinite(working.yahoo_ret.to_numpy("float64"))
    ]
    if working.empty:
        return {
            "bars": 0,
            "return_corr": 0.0,
            "direction_agreement_pct": 0.0,
            "mean_abs_return_diff_bps": 0.0,
            "p95_abs_return_diff_bps": 0.0,
        }
    binance_ret = working.binance_ret.to_numpy("float64")
    yahoo_ret = working.yahoo_ret.to_numpy("float64")
    corr = np.corrcoef(binance_ret, yahoo_ret)[0, 1]
    nonzero = (binance_ret != 0.0) | (yahoo_ret != 0.0)
    direction_agreement = (
        np.sign(binance_ret[nonzero]) == np.sign(yahoo_ret[nonzero])
    ).mean() if nonzero.any() else 0.0
    abs_diff = np.abs(binance_ret - yahoo_ret)
    return {
        "bars": int(len(working)),
        "return_corr": round(float(corr), 4) if np.isfinite(corr) else 0.0,
        "direction_agreement_pct": pct(float(direction_agreement)),
        "mean_abs_return_diff_bps": bps(float(abs_diff.mean())),
        "p95_abs_return_diff_bps": bps(float(np.quantile(abs_diff, 0.95))),
    }


def summarize_prices(frame: pd.DataFrame) -> dict[str, Any]:
    ratio = frame.binance_close / frame.yahoo_close.replace(0.0, np.nan)
    normalized_spread = (
        frame.binance_close / float(frame.binance_close.iloc[0])
    ) / (frame.yahoo_close / float(frame.yahoo_close.iloc[0])) - 1.0
    close_diff_pct = frame.binance_close / frame.yahoo_close.replace(0.0, np.nan) - 1.0
    return {
        "close_ratio_median": round(float(ratio.median()), 6),
        "close_ratio_p05": round(float(ratio.quantile(0.05)), 6),
        "close_ratio_p95": round(float(ratio.quantile(0.95)), 6),
        "mean_abs_close_diff_pct": pct(float(close_diff_pct.abs().mean())),
        "normalized_spread_end_pct": pct(float(normalized_spread.iloc[-1])),
        "normalized_spread_max_abs_pct": pct(float(normalized_spread.abs().max())),
    }


def bucket_summary(aligned: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, subset in aligned.groupby("ny_session", sort=False):
        row = {
            "session": bucket,
            **summarize_prices(subset),
            **summarize_returns(subset),
        }
        rows.append(row)
    order = {"premarket": 0, "regular": 1, "afterhours": 2, "overnight": 3, "other": 4}
    return pd.DataFrame(rows).sort_values(
        "session",
        key=lambda series: series.map(order).fillna(99),
    )


def daily_summary(aligned: pd.DataFrame) -> dict[str, Any]:
    working = aligned.copy()
    local = pd.DatetimeIndex(pd.to_datetime(working.ts, utc=True)).tz_convert(
        "America/New_York"
    )
    working["ny_date"] = local.date.astype(str)
    daily = (
        working.groupby("ny_date", as_index=False)
        .agg(binance_close=("binance_close", "last"), yahoo_close=("yahoo_close", "last"))
        .sort_values("ny_date")
    )
    daily["binance_ret"] = daily.binance_close.pct_change()
    daily["yahoo_ret"] = daily.yahoo_close.pct_change()
    ret = daily.dropna(subset=["binance_ret", "yahoo_ret"])
    corr = (
        np.corrcoef(ret.binance_ret.to_numpy("float64"), ret.yahoo_ret.to_numpy("float64"))[0, 1]
        if len(ret) >= 2
        else np.nan
    )
    return {
        "days": int(len(daily)),
        "daily_return_corr": round(float(corr), 4) if np.isfinite(corr) else 0.0,
        "binance_period_return_pct": pct(float(daily.binance_close.iloc[-1] / daily.binance_close.iloc[0] - 1.0)),
        "yahoo_period_return_pct": pct(float(daily.yahoo_close.iloc[-1] / daily.yahoo_close.iloc[0] - 1.0)),
    }


def main() -> None:
    binance = load_binance()
    yahoo = load_yahoo()
    yahoo_start = pd.Timestamp(yahoo.ts.iloc[0])
    yahoo_end = pd.Timestamp(yahoo.ts.iloc[-1])
    binance_in_yahoo_span = binance[(binance.ts >= yahoo_start) & (binance.ts <= yahoo_end)]

    aligned = binance.merge(
        yahoo,
        on="ts",
        how="inner",
        suffixes=("_binance", "_yahoo"),
    )
    aligned = aligned.rename(
        columns={
            "open_binance": "binance_open",
            "high_binance": "binance_high",
            "low_binance": "binance_low",
            "close_binance": "binance_close",
            "volume_binance": "binance_volume",
            "open_yahoo": "yahoo_open",
            "high_yahoo": "yahoo_high",
            "low_yahoo": "yahoo_low",
            "close_yahoo": "yahoo_close",
            "volume_yahoo": "yahoo_volume",
        }
    )
    aligned["ny_session"] = ny_session_bucket(aligned.ts)
    aligned["binance_ret"] = aligned.binance_close.pct_change()
    aligned["yahoo_ret"] = aligned.yahoo_close.pct_change()
    aligned["close_ratio"] = aligned.binance_close / aligned.yahoo_close.replace(0.0, np.nan)
    aligned["close_diff_pct"] = aligned.close_ratio - 1.0
    aligned["abs_return_diff_bps"] = (aligned.binance_ret - aligned.yahoo_ret).abs() * 10000.0

    bucket = bucket_summary(aligned)
    summary = {
        "symbol": "MU",
        "sources": {
            "binance": str(BINANCE_ROOT / "date=*/symbol=mu_usdt_usdt.parquet"),
            "yahoo": str(YAHOO_PATH),
        },
        "coverage": {
            "binance_rows_total": int(len(binance)),
            "yahoo_rows_total": int(len(yahoo)),
            "binance_rows_in_yahoo_span": int(len(binance_in_yahoo_span)),
            "aligned_rows": int(len(aligned)),
            "aligned_start": str(pd.Timestamp(aligned.ts.iloc[0])),
            "aligned_end": str(pd.Timestamp(aligned.ts.iloc[-1])),
            "yahoo_span_start": str(yahoo_start),
            "yahoo_span_end": str(yahoo_end),
            "aligned_vs_yahoo_rows_pct": pct(len(aligned) / len(yahoo)),
            "aligned_vs_binance_span_pct": pct(len(aligned) / len(binance_in_yahoo_span)),
        },
        "price_alignment": summarize_prices(aligned),
        "return_alignment": summarize_returns(aligned),
        "daily_alignment": daily_summary(aligned),
        "by_session": bucket.to_dict(orient="records"),
        "notes": [
            "Yahoo 15m free data only covers recent intraday history and mostly 04:00-20:00 ET when includePrePost=true.",
            "Exact UTC 15m timestamps are used after flooring Yahoo timestamps to 15-minute boundaries.",
            "Price-level comparison uses close ratio; strategy-relevant comparison should focus more on return correlation and direction agreement.",
        ],
    }

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    aligned.to_csv(ALIGNED_PATH, index=False)
    bucket.to_csv(BUCKET_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
