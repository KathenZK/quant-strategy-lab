#!/usr/bin/env python3
"""Run the frozen BIN-1D-MCSM-LS3 monthly long-3 / short-3 diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-monthly-cs-momentum-ls3"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CACHE_DIR = ROOT / "data/cache/binance_perp_1d_from_15m"
OHLCV_CACHE = CACHE_DIR / "ohlcv_1d"
FUNDING_CACHE = CACHE_DIR / "funding_1d"
CACHE_MARKER = CACHE_DIR / "_build_complete.json"

KLINE_15M = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
    / "source=binance_vision_monthly"
)
KLINE_15M_DATE = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_15M = (
    ROOT
    / "data/normalized/funding_rates/exchange=binance/market_type=perp"
    / "source=binance_vision_monthly"
)
FUNDING_DATE = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
OHLCV_OVERLAY = OHLCV_CACHE / "overlay_date_partitions.parquet"
FUNDING_OVERLAY = FUNDING_CACHE / "overlay_date_partitions.parquet"

FAMILY_NAME = "Binance-1D-Monthly-Cross-Sectional-Momentum-LS3"
FAMILY_ALIAS = "BIN-1D-MCSM-LS3"
N_LEGS = 3
LEG_WEIGHT = 1.0 / N_LEGS
FEE_SLIP_PER_SIDE = 0.001 + 0.0004
MIN_COVERAGE = 0.80
MIN_ENDPOINT_BARS = 48
MIN_ADV_USDT = 10_000_000.0
ADV_WINDOW = 30
ANNUALIZER = 365.0
BARS_PER_DAY = 96
ARCHIVE_START = pd.Period("2020-01", freq="M")
ARCHIVE_END = pd.Period("2026-06", freq="M")

STABLE_BASES = {
    "USDC",
    "BUSD",
    "TUSD",
    "USDP",
    "FDUSD",
    "DAI",
    "SUSD",
    "EUR",
    "AEUR",
    "GBP",
    "AUD",
    "BRL",
    "USD1",
    "USDE",
    "XUSD",
    "BFUSD",
}
INDEX_BASES = {"BLUEBIRD", "DOTECO", "FOOTBALL"}
EXCLUDED_BASES = STABLE_BASES | INDEX_BASES

VARIANTS = (
    {
        "id": "all_listed_momentum",
        "universe": "all_listed",
        "sign": 1.0,
        "label": "全上市动量 3+3",
    },
    {
        "id": "adv10m_momentum",
        "universe": "adv10m",
        "sign": 1.0,
        "label": "ADV≥1000万动量 3+3",
    },
    {
        "id": "adv10m_reversal",
        "universe": "adv10m",
        "sign": -1.0,
        "label": "ADV≥1000万反转 3+3",
    },
)

RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.DateOffset(months=1),
    "3m": pd.DateOffset(months=3),
    "6m": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
}

PROVENANCE = {
    "derived_field": "1d OHLCV and daily funding from 15m Vision monthly archives",
    "derivation": (
        "UTC day-boundary aggregation: open=first, high=max, low=min, close=last, "
        "quote_volume=sum, bars_15m=count, all_closed=bool_and(is_closed); "
        "funding_rate summed by UTC day. No gap fill."
    ),
    "source_dataset": (
        "data/normalized/ohlcv/.../timeframe=15m/source=binance_vision_monthly "
        "month=2020-01 through month=2026-06 (full point-in-time universe), "
        "plus date=* partitions for majors that monthly archives drop after overlap "
        "(BTC/ETH/SOL/BNB/TRX/HYPE/MU). Same split for funding_rates. "
        "Panel clipped to 2026-06-30 so July+ majors-only days cannot shrink the universe."
    ),
    "null_policy": "no filling; missing 15m bars shrink the 1d aggregate",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime, pd.Period)):
        return str(value)
    if isinstance(value, np.generic):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_bytes(path: Path, content: bytes, *, force: bool) -> None:
    if path.exists() and not force:
        if path.read_bytes() == content:
            return
        raise RuntimeError(f"artifact exists; use --force to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=f"{path.suffix}.tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, payload: Any, *, force: bool) -> None:
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False).encode()
        + b"\n"
    )
    atomic_write_bytes(path, encoded, force=force)


def write_csv(path: Path, frame: pd.DataFrame, *, force: bool) -> None:
    encoded = frame.to_csv(index=False, lineterminator="\n").encode()
    atomic_write_bytes(path, encoded, force=force)


def write_text(path: Path, content: str, *, force: bool) -> None:
    atomic_write_bytes(path, content.encode(), force=force)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute("SET enable_progress_bar=false")
    return con


def archive_months() -> list[str]:
    months = []
    current = ARCHIVE_START
    while current <= ARCHIVE_END:
        months.append(str(current))
        current += 1
    return months


def _write_date_overlay(con: duckdb.DuckDBPyConnection) -> None:
    kline_glob = str(KLINE_15M_DATE / "date=*" / "*.parquet")
    funding_glob = str(FUNDING_DATE / "date=*" / "*.parquet")
    con.execute(
        f"""
        COPY (
            SELECT
                replace(symbol, '/USDT:USDT', '') AS sym_key,
                any_value(base_asset) AS base_asset,
                CAST(date_trunc('day', ts) AS DATE) AS day,
                arg_min(open, ts) AS open,
                max(high) AS high,
                min(low) AS low,
                arg_max(close, ts) AS close,
                sum(quote_volume) AS quote_volume,
                count(*) AS bars_15m,
                bool_and(is_closed) AS all_closed
            FROM read_parquet('{kline_glob}', union_by_name=true)
            WHERE symbol LIKE '%/USDT:USDT'
            GROUP BY 1, 3
        ) TO '{OHLCV_OVERLAY}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.execute(
        f"""
        COPY (
            SELECT
                replace(symbol, '/USDT:USDT', '') AS sym_key,
                CAST(date_trunc('day', ts) AS DATE) AS day,
                sum(funding_rate) AS funding_rate
            FROM read_parquet('{funding_glob}', union_by_name=true)
            WHERE symbol LIKE '%/USDT:USDT' AND funding_rate IS NOT NULL
            GROUP BY 1, 2
        ) TO '{FUNDING_OVERLAY}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )


def ensure_daily_cache(*, rebuild: bool) -> dict[str, Any]:
    months = archive_months()
    monthly_complete = all((OHLCV_CACHE / f"month={month}.parquet").exists() for month in months)
    overlay_complete = OHLCV_OVERLAY.exists() and FUNDING_OVERLAY.exists()
    if CACHE_MARKER.exists() and monthly_complete and overlay_complete and not rebuild:
        return json.loads(CACHE_MARKER.read_text(encoding="utf-8"))
    if rebuild and CACHE_DIR.exists():
        import shutil

        shutil.rmtree(CACHE_DIR)
    OHLCV_CACHE.mkdir(parents=True, exist_ok=True)
    FUNDING_CACHE.mkdir(parents=True, exist_ok=True)
    con = connect()
    if rebuild or not monthly_complete:
        for month in months:
            kline_src = KLINE_15M / f"month={month}" / "*.parquet"
            funding_src = FUNDING_15M / f"month={month}" / "*.parquet"
            kline_files = list((KLINE_15M / f"month={month}").glob("*.parquet"))
            if not kline_files:
                raise FileNotFoundError(f"missing 15m monthly archive: {month}")
            ohlcv_out = OHLCV_CACHE / f"month={month}.parquet"
            con.execute(
                f"""
                COPY (
                    SELECT
                        replace(symbol, '/USDT:USDT', '') AS sym_key,
                        any_value(base_asset) AS base_asset,
                        CAST(date_trunc('day', ts) AS DATE) AS day,
                        arg_min(open, ts) AS open,
                        max(high) AS high,
                        min(low) AS low,
                        arg_max(close, ts) AS close,
                        sum(quote_volume) AS quote_volume,
                        count(*) AS bars_15m,
                        bool_and(is_closed) AS all_closed
                    FROM read_parquet('{kline_src}', union_by_name=true)
                    WHERE symbol IS NOT NULL
                    GROUP BY 1, 3
                ) TO '{ohlcv_out}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
            funding_out = FUNDING_CACHE / f"month={month}.parquet"
            funding_files = list((FUNDING_15M / f"month={month}").glob("*.parquet"))
            if funding_files:
                con.execute(
                    f"""
                    COPY (
                        SELECT
                            replace(symbol, '/USDT:USDT', '') AS sym_key,
                            CAST(date_trunc('day', ts) AS DATE) AS day,
                            sum(funding_rate) AS funding_rate
                        FROM read_parquet('{funding_src}', union_by_name=true)
                        WHERE funding_rate IS NOT NULL
                        GROUP BY 1, 2
                    ) TO '{funding_out}' (FORMAT PARQUET, COMPRESSION ZSTD)
                    """
                )
            print(f"cached {month}", flush=True)
    print("caching date=* majors overlay", flush=True)
    _write_date_overlay(con)
    ohlcv_rows = int(
        con.execute(
            f"SELECT count(*) FROM read_parquet('{OHLCV_CACHE}/month=*.parquet')"
        ).fetchone()[0]
    )
    funding_rows = int(
        con.execute(
            f"SELECT count(*) FROM read_parquet('{FUNDING_CACHE}/month=*.parquet')"
        ).fetchone()[0]
    )
    marker = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "months": months,
        "ohlcv_rows": ohlcv_rows,
        "funding_rows": funding_rows,
        "overlay": {
            "ohlcv": str(OHLCV_OVERLAY.relative_to(ROOT)),
            "funding": str(FUNDING_OVERLAY.relative_to(ROOT)),
        },
        "provenance": PROVENANCE,
    }
    CACHE_MARKER.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return marker


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    con = connect()
    ohlcv = con.execute(
        f"""
        SELECT * EXCLUDE (prio) FROM (
            SELECT *, 0 AS prio
            FROM read_parquet('{OHLCV_CACHE}/month=*.parquet')
            UNION ALL BY NAME
            SELECT *, 1 AS prio
            FROM read_parquet('{OHLCV_OVERLAY}')
        )
        QUALIFY row_number() OVER (PARTITION BY sym_key, day ORDER BY prio) = 1
        ORDER BY day, sym_key
        """
    ).fetch_df()
    funding = con.execute(
        f"""
        SELECT * EXCLUDE (prio) FROM (
            SELECT *, 0 AS prio
            FROM read_parquet('{FUNDING_CACHE}/month=*.parquet')
            UNION ALL BY NAME
            SELECT *, 1 AS prio
            FROM read_parquet('{FUNDING_OVERLAY}')
        )
        QUALIFY row_number() OVER (PARTITION BY sym_key, day ORDER BY prio) = 1
        ORDER BY day, sym_key
        """
    ).fetch_df()
    ohlcv["day"] = pd.to_datetime(ohlcv["day"])
    funding["day"] = pd.to_datetime(funding["day"])
    cutoff = ARCHIVE_END.to_timestamp(how="end").normalize()
    ohlcv = ohlcv.loc[ohlcv["day"].le(cutoff)].copy()
    funding = funding.loc[funding["day"].le(cutoff)].copy()
    dup = int(ohlcv.duplicated(["day", "sym_key"]).sum())
    if dup:
        raise RuntimeError(f"duplicate 1d keys: {dup}")
    bases = (
        ohlcv.groupby("sym_key")["base_asset"]
        .agg(lambda values: str(values.dropna().iloc[-1]) if values.notna().any() else "")
        .to_dict()
    )
    return ohlcv, funding, bases


def pivot(ohlcv: pd.DataFrame, column: str) -> pd.DataFrame:
    frame = ohlcv.pivot(index="day", columns="sym_key", values=column).sort_index()
    frame.index = pd.DatetimeIndex(frame.index)
    return frame


def excluded_mask(columns: pd.Index, bases: dict[str, str]) -> pd.Series:
    return pd.Series(
        [bases.get(str(symbol), str(symbol)) in EXCLUDED_BASES for symbol in columns],
        index=columns,
    )


def month_starts(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    start = index.min().to_period("M").to_timestamp()
    end = index.max().to_period("M").to_timestamp()
    return pd.date_range(start, end, freq="MS")


def last_available_in_month(frame: pd.DataFrame, month: pd.Period) -> pd.Series:
    window = frame.loc[
        (frame.index.to_period("M") == month) & frame.notna().any(axis=1)
    ]
    if window.empty:
        return pd.Series(index=frame.columns, dtype="float64")
    return window.ffill().iloc[-1]


def coverage_in_month(bars: pd.DataFrame, month: pd.Period) -> pd.Series:
    calendar_days = month.days_in_month
    window = bars.loc[bars.index.to_period("M") == month]
    present = window.ge(1).sum(axis=0)
    return present / float(calendar_days)


def pick_legs(
    formation: pd.Series,
    *,
    eligible: pd.Series,
    has_open: pd.Series,
    adv: pd.Series,
    n_legs: int,
    sign: float,
) -> tuple[list[str], list[str]] | None:
    pool = formation.loc[eligible & formation.notna() & np.isfinite(formation)]
    if pool.size < 2 * n_legs:
        return None
    rank_key = pd.DataFrame(
        {
            "formation": pool * sign,
            "adv": adv.reindex(pool.index).fillna(-1.0),
        }
    )
    ordered = rank_key.sort_values(
        ["formation", "adv"],
        ascending=[False, False],
    ).index.tolist()
    longs: list[str] = []
    for symbol in ordered:
        if bool(has_open.get(symbol, False)):
            longs.append(str(symbol))
        if len(longs) == n_legs:
            break
    shorts: list[str] = []
    for symbol in reversed(ordered):
        if symbol in longs:
            continue
        if bool(has_open.get(symbol, False)):
            shorts.append(str(symbol))
        if len(shorts) == n_legs:
            break
    if len(longs) < n_legs or len(shorts) < n_legs:
        return None
    return longs, shorts


def weights_from_legs(columns: pd.Index, longs: list[str], shorts: list[str]) -> pd.Series:
    weights = pd.Series(0.0, index=columns)
    weights.loc[longs] = LEG_WEIGHT
    weights.loc[shorts] = -LEG_WEIGHT
    return weights


def performance(net: pd.Series, *, gross: pd.Series | None = None) -> dict[str, Any]:
    net = net.astype("float64").fillna(0.0)
    equity = (1.0 + net).cumprod()
    n_days = max(int(len(net)), 1)
    span_years = max((net.index[-1] - net.index[0]).days / 365.25, 1.0 / 365.25)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / span_years) - 1.0) if equity.iloc[-1] > 0 else -1.0
    vol = float(net.std(ddof=0) * math.sqrt(ANNUALIZER))
    sharpe = float(net.mean() / net.std(ddof=0) * math.sqrt(ANNUALIZER)) if net.std(ddof=0) > 0 else 0.0
    dd = equity / equity.cummax() - 1.0
    monthly = (1.0 + net).resample("ME").prod() - 1.0
    out = {
        "n_days": n_days,
        "start": str(net.index[0].date()),
        "end": str(net.index[-1].date()),
        "total_return": total,
        "cagr": cagr,
        "ann_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": float(dd.min()) if len(dd) else 0.0,
        "month_hit_rate": float((monthly > 0).mean()) if len(monthly) else None,
        "n_months": int(len(monthly)),
        "final_equity": float(equity.iloc[-1]),
    }
    if gross is not None:
        out["gross_total_return"] = float((1.0 + gross.astype("float64").fillna(0.0)).prod() - 1.0)
    return out


def recent_slices(net: pd.Series) -> list[dict[str, Any]]:
    end = net.index[-1]
    rows = []
    for label, offset in RECENT_WINDOWS.items():
        start = end - offset
        window = net.loc[net.index > start]
        if window.empty:
            rows.append({"slice": label, "n_days": 0, "net_return": None, "max_drawdown": None})
            continue
        equity = (1.0 + window.astype("float64").fillna(0.0)).cumprod()
        dd = equity / equity.cummax() - 1.0
        rows.append(
            {
                "slice": label,
                "n_days": int(len(window)),
                "start": str(window.index[0].date()),
                "end": str(window.index[-1].date()),
                "net_return": float(equity.iloc[-1] - 1.0),
                "max_drawdown": float(dd.min()),
            }
        )
    return rows


def build_variant(
    *,
    variant: dict[str, Any],
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any]:
    excluded = excluded_mask(close.columns, bases)
    adv = quote.rolling(ADV_WINDOW, min_periods=ADV_WINDOW).mean()
    starts = month_starts(close.index)
    weight_eod = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    holdings: list[dict[str, Any]] = []
    for month_start in starts:
        lookback = (month_start - pd.offsets.MonthBegin(1)).to_period("M")
        prior = lookback - 1
        if lookback < ARCHIVE_START or lookback > ARCHIVE_END:
            continue
        p_end = last_available_in_month(close, lookback)
        p_start = last_available_in_month(close, prior)
        formation = p_end / p_start - 1.0
        coverage = coverage_in_month(bars, lookback)
        lookback_days = close.index[close.index.to_period("M") == lookback]
        prior_days = close.index[close.index.to_period("M") == prior]
        if lookback_days.empty or prior_days.empty or month_start not in close.index:
            continue
        last_lookback = lookback_days.max()
        last_prior = prior_days.max()
        endpoint_ok = (
            close.loc[last_lookback].notna()
            & close.loc[last_prior].notna()
            & bars.loc[last_lookback].ge(MIN_ENDPOINT_BARS)
            & bars.loc[last_prior].ge(MIN_ENDPOINT_BARS)
        )
        has_open = open_.loc[month_start].notna() if month_start in open_.index else pd.Series(False, index=close.columns)
        eligible = (
            (~excluded)
            & endpoint_ok
            & coverage.ge(MIN_COVERAGE)
            & formation.notna()
        )
        if variant["universe"] == "adv10m":
            eligible = eligible & adv.loc[last_lookback].ge(MIN_ADV_USDT)
        picked = pick_legs(
            formation,
            eligible=eligible,
            has_open=has_open,
            adv=adv.loc[last_lookback],
            n_legs=N_LEGS,
            sign=float(variant["sign"]),
        )
        hold_end = (month_start + pd.offsets.MonthBegin(1)) - pd.Timedelta(days=1)
        hold_index = close.index[(close.index >= month_start) & (close.index <= hold_end)]
        if picked is None or hold_index.empty:
            holdings.append(
                {
                    "rebalance": str(month_start.date()),
                    "lookback_month": str(lookback),
                    "eligible": int(eligible.sum()),
                    "status": "flat",
                }
            )
            continue
        longs, shorts = picked
        weights = weights_from_legs(close.columns, longs, shorts)
        weight_eod.loc[hold_index] = np.repeat(
            weights.to_numpy()[None, :], len(hold_index), axis=0
        )
        next_month_days = close.index[close.index.to_period("M") == (lookback + 1)]
        hold_end_px = close.loc[hold_index.max()]
        hold_start_px = open_.loc[month_start]
        realized = hold_end_px / hold_start_px - 1.0
        holdings.append(
            {
                "rebalance": str(month_start.date()),
                "lookback_month": str(lookback),
                "eligible": int(eligible.sum()),
                "status": "traded",
                "longs": ",".join(longs),
                "shorts": ",".join(shorts),
                "long_formation": float(formation[longs].mean()),
                "short_formation": float(formation[shorts].mean()),
                "long_hold": float(realized[longs].mean()),
                "short_hold": float(realized[shorts].mean()),
                "spread_hold": float(realized[longs].mean() - realized[shorts].mean()),
                "min_adv": float(adv.loc[last_lookback, longs + shorts].min()),
                "median_adv": float(adv.loc[last_lookback, longs + shorts].median()),
            }
        )

    prev_close = close.shift(1)
    r_cc = close / prev_close - 1.0
    r_co = close / open_ - 1.0
    r_overnight = open_ / prev_close - 1.0
    w_bod = weight_eod.shift(1).fillna(0.0)
    rebalance_days = pd.Index([row["rebalance"] for row in holdings if row.get("status") == "traded"])
    rebalance_mask = pd.Series(close.index.strftime("%Y-%m-%d").isin(set(rebalance_days)), index=close.index)

    price_pnl = (w_bod * r_cc.fillna(0.0)).sum(axis=1)
    overnight = (w_bod * r_overnight.fillna(0.0)).sum(axis=1)
    intraday = (weight_eod * r_co.fillna(0.0)).sum(axis=1)
    price_pnl = price_pnl.where(~rebalance_mask, overnight + intraday)
    long_pnl = (weight_eod.clip(lower=0.0) * r_cc.fillna(0.0)).sum(axis=1)
    short_pnl = (weight_eod.clip(upper=0.0) * r_cc.fillna(0.0)).sum(axis=1)
    long_pnl = long_pnl.where(~rebalance_mask, (weight_eod.clip(lower=0.0) * r_co.fillna(0.0)).sum(axis=1))
    short_pnl = short_pnl.where(~rebalance_mask, (weight_eod.clip(upper=0.0) * r_co.fillna(0.0)).sum(axis=1))

    turnover = (weight_eod - w_bod).abs().sum(axis=1)
    cost = turnover * FEE_SLIP_PER_SIDE
    last_day = close.index.max()
    if last_day in weight_eod.index:
        cost.loc[last_day] += float(weight_eod.loc[last_day].abs().sum()) * FEE_SLIP_PER_SIDE
    held = weight_eod.abs() > 0
    funding_cov = float((held & funding.notna()).to_numpy().sum() / max(int(held.to_numpy().sum()), 1))
    funding_pnl = -(weight_eod * funding.reindex_like(weight_eod).fillna(0.0)).sum(axis=1)
    gross = price_pnl
    net = price_pnl - cost + funding_pnl

    traded = [row for row in holdings if row.get("status") == "traded"]
    active_start = pd.Timestamp(traded[0]["rebalance"]) if traded else close.index.max()
    net = net.loc[net.index >= active_start]
    gross = gross.loc[net.index]
    cost = cost.loc[net.index]
    funding_pnl = funding_pnl.loc[net.index]
    long_pnl = long_pnl.loc[net.index]
    short_pnl = short_pnl.loc[net.index]
    turnover = turnover.loc[net.index]
    metrics = performance(net, gross=gross)
    metrics.update(
        {
            "variant": variant["id"],
            "label": variant["label"],
            "cost_drag": float(cost.sum()),
            "funding_drag": float(funding_pnl.sum()),
            "price_pnl_sum": float(gross.sum()),
            "long_pnl_sum": float(long_pnl.sum()),
            "short_pnl_sum": float(short_pnl.sum()),
            "mean_turnover": float(turnover.mean()),
            "ann_turnover": float(turnover.sum() * ANNUALIZER / max(len(net), 1)),
            "funding_coverage": funding_cov,
            "n_rebalances": int(len(traded)),
            "n_flat_months": int(sum(row.get("status") == "flat" for row in holdings)),
            "mean_long_formation": float(np.nanmean([row["long_formation"] for row in traded])) if traded else None,
            "mean_short_formation": float(np.nanmean([row["short_formation"] for row in traded])) if traded else None,
            "mean_long_hold": float(np.nanmean([row["long_hold"] for row in traded])) if traded else None,
            "mean_short_hold": float(np.nanmean([row["short_hold"] for row in traded])) if traded else None,
            "mean_spread_hold": float(np.nanmean([row["spread_hold"] for row in traded])) if traded else None,
            "continuation_hit_rate": (
                float(np.mean([row["spread_hold"] > 0 for row in traded])) if traded else None
            ),
        }
    )
    yearly = (
        (1.0 + net)
        .resample("YE")
        .prod()
        .sub(1.0)
        .rename("net_return")
        .to_frame()
        .assign(year=lambda frame: frame.index.year)
    )
    daily = pd.DataFrame(
        {
            "day": net.index,
            "net_return": net.to_numpy(),
            "gross_return": gross.to_numpy(),
            "cost": cost.to_numpy(),
            "funding": funding_pnl.to_numpy(),
            "long_return": long_pnl.to_numpy(),
            "short_return": short_pnl.to_numpy(),
            "turnover": turnover.to_numpy(),
            "equity": (1.0 + net).cumprod().to_numpy(),
        }
    )
    return {
        "metrics": metrics,
        "holdings": holdings,
        "yearly": yearly,
        "slices": recent_slices(net),
        "daily": daily,
        "net": net,
    }


def btc_buy_hold(close: pd.DataFrame, index: pd.DatetimeIndex) -> dict[str, Any]:
    if "BTC" not in close.columns:
        return {"total_return": None}
    px = close["BTC"].reindex(index).dropna()
    ret = px.pct_change(fill_method=None).fillna(0.0)
    return performance(ret)


def pct(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def num(value: float | None, digits: int = 3) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def render_report(
    *,
    run_date: str,
    cache_meta: dict[str, Any],
    audit: dict[str, Any],
    results: dict[str, dict[str, Any]],
    btc: dict[str, Any],
    artifact_stem: str,
) -> str:
    primary = results["all_listed_momentum"]["metrics"]
    tradable = results["adv10m_momentum"]["metrics"]
    reversal = results["adv10m_reversal"]["metrics"]
    lines = [
        f"# BIN-1D-MCSM-LS3 月度最强3/最弱3 诊断（{run_date}）",
        "",
        f"- Family：`{FAMILY_NAME}`（`{FAMILY_ALIAS}`）",
        "- 状态：`explore / not promoted / not live-ready`",
        "- 市场：Binance USD-M USDT 永续；日 K 由已闭合 `15m` Vision 月档按 UTC 日边界聚合",
        f"- 窗口：`{primary['start']}` → `{primary['end']}` UTC；宇宙月档 `2020-01`–`2026-06`",
        "- 成本：每边手续费 `0.001` + 滑点 `4 bps`；资金费按日 as-of 计入",
        "- 仓位：多头三腿各 `+1/3`、空头三腿各 `-1/3`，总名义 200%",
        "- 最近切片只作审计，不参与规则选择",
        f"- 契约：[binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md](../specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md)",
        "",
        "## 结论",
        "",
        (
            f"字面规则（全上市、上月涨最多 3 多 / 跌最多 3 空）全期净收益 "
            f"{pct(primary['total_return'])}，CAGR {pct(primary['cagr'])}，Sharpe {num(primary['sharpe'])}，"
            f"最大回撤 {pct(primary['max_drawdown'])}。"
            f"形成期多头月均 {pct(primary['mean_long_formation'])}、空头 {pct(primary['mean_short_formation'])}，"
            f"但持有月多空价差均值 {pct(primary['mean_spread_hold'])}，延续月占比 "
            f"{pct(primary['continuation_hit_rate'])}。"
        ),
        "",
        (
            f"加上 `ADV≥1000万` 可执行过滤后，动量净收益 {pct(tradable['total_return'])}，"
            f"CAGR {pct(tradable['cagr'])}，Sharpe {num(tradable['sharpe'])}，回撤 {pct(tradable['max_drawdown'])}。"
            f"同一宇宙的反转对照净收益 {pct(reversal['total_return'])}，Sharpe {num(reversal['sharpe'])}。"
        ),
        "",
        (
            "这不是可晋升策略：无波动目标、无强平模型，且最强/最弱三名天然集中在高波动山寨。"
            "本轮不登记版本。"
        ),
        "",
        "## 机制为何失效",
        "",
        (
            f"上月最强三名在持有月仍平均上涨 {pct(primary['mean_long_hold'])}，"
            f"但上月最弱三名平均上涨 {pct(primary['mean_short_hold'])}，"
            f"做空最弱腿被反弹吃掉。76 个月里只有 {pct(primary['continuation_hit_rate'])} "
            "的月份出现「强者继续强、弱者继续弱」。"
        ),
        "",
    ]
    worst = min(
        (row for row in results["all_listed_momentum"]["holdings"] if row.get("status") == "traded"),
        key=lambda row: row.get("spread_hold", 0.0),
        default=None,
    )
    if worst is not None:
        lines.extend(
            [
                (
                    f"最差月份 {worst['rebalance']} 做多 `{worst['longs']}`、做空 `{worst['shorts']}`，"
                    f"空头持有月平均 {pct(worst['short_hold'])}，多空价差 {pct(worst['spread_hold'])}。"
                    "单月这种挤空在 200% 总名义、无止损的线性账户里足够造成不可恢复回撤。"
                ),
                "",
            ]
        )
    lines.extend(
        [
            (
                f"年化波动约 {pct(primary['ann_vol'])}，同窗 BTC 买入持有 "
                f"{pct(btc.get('total_return'))} / Sharpe {num(btc.get('sharpe'))}。"
                "把账户压在最极端的六个名字上，波动本身就会把小的月度负价差复利成接近归零。"
            ),
            "",
            (
                f"反转对照（做多最弱、做空最强）价格腿算术和为正，但资金费日和 "
                f"{num(reversal['funding_drag'], 4)} 把优势对冲掉，路径同样接近归零。"
                "所以问题不只是「方向反了」，而是这个持仓结构不可交易。"
            ),
            "",
        "## 数据审计",
        "",
        f"- 派生日 K 行数：`{audit['ohlcv_rows']}`；资金费日行数：`{audit['funding_rows']}`",
        f"- 符号数：`{audit['n_symbols']}`；排除稳定币/指数后：`{audit['n_symbols_included']}`",
        f"- 日 K 区间：`{audit['ohlcv_start']}` → `{audit['ohlcv_end']}`",
        f"- `bars_15m == 96` 占比：{pct(audit['full_bar_share'])}；非全闭合行：`{audit['open_rows']}`",
        f"- 重复业务键：`{audit['duplicate_rows']}`",
        f"- 资金费覆盖（持仓日×腿）：字面 {pct(primary['funding_coverage'])}，ADV 过滤 {pct(tradable['funding_coverage'])}",
        f"- 缓存：`data/cache/binance_perp_1d_from_15m/`，生成于 `{cache_meta.get('generated_at')}`",
        "",
        "## 全区间结果",
        "",
        "| 配置 | 净收益 | CAGR | 年化波动 | Sharpe | 最大回撤 | 月胜率 | 换仓月 | 延续月占比 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    )
    for variant_id in ("all_listed_momentum", "adv10m_momentum", "adv10m_reversal"):
        metrics = results[variant_id]["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    metrics["label"],
                    pct(metrics["total_return"]),
                    pct(metrics["cagr"]),
                    pct(metrics["ann_vol"]),
                    num(metrics["sharpe"]),
                    pct(metrics["max_drawdown"]),
                    pct(metrics["month_hit_rate"]),
                    str(metrics["n_rebalances"]),
                    pct(metrics["continuation_hit_rate"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"BTC 买入持有（同窗）：净收益 {pct(btc.get('total_return'))}，CAGR {pct(btc.get('cagr'))}，"
            f"Sharpe {num(btc.get('sharpe'))}，最大回撤 {pct(btc.get('max_drawdown'))}。",
            "",
            "## 归因",
            "",
            "| 配置 | 价格 PnL 日和 | 成本日和 | 资金费日和 | 多头日和 | 空头日和 | 形成期多头 | 形成期空头 | 持有月多头 | 持有月空头 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for variant_id in ("all_listed_momentum", "adv10m_momentum", "adv10m_reversal"):
        metrics = results[variant_id]["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    metrics["label"],
                    num(metrics["price_pnl_sum"], 4),
                    num(metrics["cost_drag"], 4),
                    num(metrics["funding_drag"], 4),
                    num(metrics["long_pnl_sum"], 4),
                    num(metrics["short_pnl_sum"], 4),
                    pct(metrics["mean_long_formation"]),
                    pct(metrics["mean_short_formation"]),
                    pct(metrics["mean_long_hold"]),
                    pct(metrics["mean_short_hold"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## 分年净收益", "", "| 年 | 全上市动量 | ADV≥1000万动量 | ADV≥1000万反转 |", "| --- | ---: | ---: | ---: |"])
    years = sorted(
        {
            int(year)
            for variant in results.values()
            for year in variant["yearly"]["year"].tolist()
        }
    )
    for year in years:
        cells = [str(year)]
        for variant_id in ("all_listed_momentum", "adv10m_momentum", "adv10m_reversal"):
            yearly = results[variant_id]["yearly"]
            row = yearly.loc[yearly["year"].eq(year), "net_return"]
            cells.append(pct(float(row.iloc[0])) if len(row) else "n/a")
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(["", "## 最近切片（审计）", ""])
    for variant_id in ("all_listed_momentum", "adv10m_momentum"):
        metrics = results[variant_id]["metrics"]
        lines.extend(
            [
                f"### {metrics['label']}",
                "",
                "| 窗口 | 净收益 | 最大回撤 | 天数 |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for row in results[variant_id]["slices"]:
            lines.append(
                f"| `{row['slice']}` | {pct(row['net_return'])} | {pct(row['max_drawdown'])} | {row['n_days']} |"
            )
        lines.append("")
    sample = [row for row in results["all_listed_momentum"]["holdings"] if row.get("status") == "traded"]
    lines.extend(
        [
            "## 字面规则换仓样例（首尾各 3 个月）",
            "",
            "| 换仓日 | 做多 | 做空 | 形成期多头 | 形成期空头 | 持有月价差 | 资格数 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    shown = sample[:3] + sample[-3:] if len(sample) > 6 else sample
    seen: set[str] = set()
    for row in shown:
        key = row["rebalance"]
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"| {row['rebalance']} | `{row['longs']}` | `{row['shorts']}` | "
            f"{pct(row['long_formation'])} | {pct(row['short_formation'])} | "
            f"{pct(row['spread_hold'])} | {row['eligible']} |"
        )
    lines.extend(
        [
            "",
            "## 限制",
            "",
            "- 线性 PnL，不模拟维持保证金与强平；最弱三名的单日反弹可以把账户路径打穿，实盘更差。",
            "- 字面宇宙会选中上月暴涨/暴跌的薄流动性合约，4 bps 滑点仍可能低估冲击。",
            "- `2026-07` 起本地没有全市场 `15m` 月档，不能把最近两个月当成全市场结果。",
            "- 三个配置是预先冻结的诊断对照，不是参数搜索；不得把较好的那一个登记为版本。",
            "",
            "## 证据",
            "",
            f"- 汇总：[{artifact_stem}-summary.json](../artifacts/{artifact_stem}-summary.json)",
            f"- 指标：[{artifact_stem}-metrics.csv](../artifacts/{artifact_stem}-metrics.csv)",
            f"- 换仓：[{artifact_stem}-holdings.csv](../artifacts/{artifact_stem}-holdings.csv)",
            f"- 分年：[{artifact_stem}-yearly.csv](../artifacts/{artifact_stem}-yearly.csv)",
            f"- 切片：[{artifact_stem}-recent-slices.csv](../artifacts/{artifact_stem}-recent-slices.csv)",
            f"- 日路径：[{artifact_stem}-daily-paths.csv](../artifacts/{artifact_stem}-daily-paths.csv)",
            "- 脚本：[research_binance_1d_mcsm_ls3.py](../scripts/research_binance_1d_mcsm_ls3.py)",
            "",
            "```bash",
            f"uv run python research/asset-portfolios/1d-monthly-cs-momentum-ls3/scripts/research_binance_1d_mcsm_ls3.py --run-date {run_date}",
            "```",
            "",
            "## 状态",
            "",
            "`explore / not promoted / not live-ready`。本轮不登记版本。",
            "",
        ]
    )
    return "\n".join(lines)


def make_synthetic_panel() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    days = pd.date_range("2021-01-01", "2021-04-30", freq="D")
    symbols = ["AAA", "BBB", "CCC", "XXX", "YYY", "ZZZ", "PPP", "QQQ"]
    close = pd.DataFrame(index=days, columns=symbols, dtype="float64")
    close.loc["2021-01-01"] = 100.0
    for day in days[1:]:
        prev = close.loc[: day - pd.Timedelta(days=1)].iloc[-1]
        month = day.month
        row = prev.copy()
        if month == 1:
            row[["AAA", "BBB", "CCC"]] *= 1.02
            row[["XXX", "YYY", "ZZZ"]] *= 0.98
        elif month == 2:
            row[["AAA", "BBB", "CCC"]] *= 1.03
            row[["XXX", "YYY", "ZZZ"]] *= 0.97
        elif month == 3:
            row[["AAA", "BBB", "CCC"]] *= 0.97
            row[["XXX", "YYY", "ZZZ"]] *= 1.03
        else:
            row[:] *= 1.0
        close.loc[day] = row
    open_ = close.shift(1)
    open_.iloc[0] = close.iloc[0]
    bars = pd.DataFrame(96.0, index=days, columns=symbols)
    quote = pd.DataFrame(20_000_000.0, index=days, columns=symbols)
    funding = pd.DataFrame(0.0, index=days, columns=symbols)
    ohlcv_rows = []
    for symbol in symbols:
        for day in days:
            ohlcv_rows.append(
                {
                    "sym_key": symbol,
                    "base_asset": symbol,
                    "day": day,
                    "open": float(open_.loc[day, symbol]),
                    "high": float(close.loc[day, symbol]),
                    "low": float(min(open_.loc[day, symbol], close.loc[day, symbol])),
                    "close": float(close.loc[day, symbol]),
                    "quote_volume": 20_000_000.0,
                    "bars_15m": 96,
                    "all_closed": True,
                }
            )
    ohlcv = pd.DataFrame(ohlcv_rows)
    funding_long = funding.stack().rename("funding_rate").reset_index()
    funding_long.columns = ["day", "sym_key", "funding_rate"]
    bases = {symbol: symbol for symbol in symbols}
    return ohlcv, funding_long, bases


def self_test() -> None:
    ohlcv, funding_long, bases = make_synthetic_panel()
    close = pivot(ohlcv, "close")
    open_ = pivot(ohlcv, "open")
    bars = pivot(ohlcv, "bars_15m")
    quote = pivot(ohlcv, "quote_volume")
    funding = funding_long.pivot(index="day", columns="sym_key", values="funding_rate")
    variant = {
        "id": "adv10m_momentum",
        "universe": "adv10m",
        "sign": 1.0,
        "label": "test",
    }
    result = build_variant(
        variant=variant,
        close=close,
        open_=open_,
        bars=bars,
        quote=quote,
        funding=funding,
        bases=bases,
    )
    traded = [row for row in result["holdings"] if row.get("status") == "traded"]
    march = next(row for row in traded if row["rebalance"] == "2021-03-01")
    assert set(march["longs"].split(",")) == {"AAA", "BBB", "CCC"}, march
    assert set(march["shorts"].split(",")) == {"XXX", "YYY", "ZZZ"}, march
    assert march["spread_hold"] < 0, march
    assert result["metrics"]["n_rebalances"] >= 1
    print("self-test ok", json.dumps(sanitize(result["metrics"]), ensure_ascii=False))


def audit_panel(ohlcv: pd.DataFrame, bases: dict[str, str]) -> dict[str, Any]:
    included = [symbol for symbol, base in bases.items() if base not in EXCLUDED_BASES]
    return {
        "ohlcv_rows": int(len(ohlcv)),
        "n_symbols": int(ohlcv["sym_key"].nunique()),
        "n_symbols_included": int(len(included)),
        "ohlcv_start": str(pd.Timestamp(ohlcv["day"].min()).date()),
        "ohlcv_end": str(pd.Timestamp(ohlcv["day"].max()).date()),
        "full_bar_share": float((ohlcv["bars_15m"] == BARS_PER_DAY).mean()),
        "open_rows": int((~ohlcv["all_closed"].fillna(False)).sum()),
        "duplicate_rows": int(ohlcv.duplicated(["day", "sym_key"]).sum()),
        "excluded_bases": sorted(EXCLUDED_BASES),
    }


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    cache_meta = ensure_daily_cache(rebuild=args.rebuild_cache)
    ohlcv, funding_long, bases = load_panel()
    cache_meta["funding_rows"] = int(len(funding_long))
    audit = audit_panel(ohlcv, bases)
    audit["funding_rows"] = int(len(funding_long))
    close = pivot(ohlcv, "close")
    open_ = pivot(ohlcv, "open")
    bars = pivot(ohlcv, "bars_15m")
    quote = pivot(ohlcv, "quote_volume")
    full_index = pd.date_range(close.index.min(), close.index.max(), freq="D")
    close = close.reindex(full_index)
    open_ = open_.reindex(full_index)
    bars = bars.reindex(full_index)
    quote = quote.reindex(full_index)
    funding = funding_long.pivot(index="day", columns="sym_key", values="funding_rate")
    funding = funding.reindex(index=close.index, columns=close.columns)
    results: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        print(f"running {variant['id']}", flush=True)
        results[variant["id"]] = build_variant(
            variant=variant,
            close=close,
            open_=open_,
            bars=bars,
            quote=quote,
            funding=funding,
            bases=bases,
        )
    primary_index = results["all_listed_momentum"]["net"].index
    btc = btc_buy_hold(close, primary_index)
    artifact_stem = f"binance-1d-mcsm-ls3-diagnostic-{args.run_date}"
    metrics_rows = [results[key]["metrics"] for key in results]
    holdings_rows = []
    yearly_rows = []
    slice_rows = []
    daily_frames = []
    for variant_id, payload in results.items():
        for row in payload["holdings"]:
            holdings_rows.append({"variant": variant_id, **row})
        yearly = payload["yearly"].copy()
        yearly["variant"] = variant_id
        yearly_rows.append(yearly.reset_index(drop=True))
        for row in payload["slices"]:
            slice_rows.append({"variant": variant_id, **row})
        daily = payload["daily"].copy()
        daily["variant"] = variant_id
        daily_frames.append(daily)
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "contract": "specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md",
        "cache": cache_meta,
        "audit": audit,
        "metrics": metrics_rows,
        "btc_buy_hold": btc,
        "provenance": PROVENANCE,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ARTIFACT_DIR / f"{artifact_stem}-summary.json", summary, force=args.force)
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-metrics.csv", pd.DataFrame(metrics_rows), force=args.force)
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-holdings.csv", pd.DataFrame(holdings_rows), force=args.force)
    write_csv(
        ARTIFACT_DIR / f"{artifact_stem}-yearly.csv",
        pd.concat(yearly_rows, ignore_index=True),
        force=args.force,
    )
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-recent-slices.csv", pd.DataFrame(slice_rows), force=args.force)
    write_csv(
        ARTIFACT_DIR / f"{artifact_stem}-daily-paths.csv",
        pd.concat(daily_frames, ignore_index=True),
        force=args.force,
    )
    report = render_report(
        run_date=args.run_date,
        cache_meta=cache_meta,
        audit=audit,
        results=results,
        btc=btc,
        artifact_stem=artifact_stem,
    )
    report_path = FAMILY_DIR / "diagnostics" / f"binance-1d-mcsm-ls3-diagnostic-{args.run_date}.md"
    write_text(report_path, report, force=args.force)
    print(json.dumps(sanitize(metrics_rows), ensure_ascii=False, indent=2))
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
