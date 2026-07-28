"""P1 baseline for BIN-1D-EMAX-LGBM: 1d EMA21/96 cross events, raw material check.

Fourth point of the timeframe-gradient scan (15m -> 1h -> 4h -> 1d). There is
no full-market 1d archive in the lake, so 1d bars are DERIVED here by
deterministic resampling of the audited 1h Vision archives (UTC day-boundary
OHLCV aggregation; provenance recorded in the report JSON). Everything else
mirrors the 1h family's P1: same conservative fill rules, Binance cost model,
point-in-time universe (coverage 6 bars/day), three pre-registered brackets.

Development window only: entries whose 96-bar (16-day) label window closes
before 2026-01-01 UTC. 2026H1 is a contaminated holdout for this mechanism.

Reuses pure functions from the frozen 15m engine (emax_common.py, pinned by
SHA256 in the 15m freeze manifest — do not modify it).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(
    0, str(ROOT / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector/scripts")
)
import emax_common as ec  # noqa: E402  (frozen 15m engine, pure functions reused)

FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ema-cross-lightgbm-event-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CACHE_DIR = ROOT / "data/cache/emax_1d_derived"
KLINE_1H_ROOT = ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h"

BARS_PER_DAY = 1
DEV_START = pd.Timestamp("2020-01-01", tz="UTC")
# last entry whose 96-bar (16-day) label window closes strictly before 2026-01-01
DEV_ENTRY_CUTOFF = pd.Timestamp("2026-01-01", tz="UTC") - pd.Timedelta(days=ec.HORIZON_BARS + 1)

PROVENANCE = {
    "derived_field": "1d OHLCV bars",
    "derivation": "UTC day-boundary aggregation of 1h bars: open=first, high=max, "
    "low=min, close=last, volume/quote_volume/trade_count/taker_*=sum; "
    "partial 1d bars kept with bars_1h count recorded",
    "source_dataset": "data/normalized/ohlcv/.../timeframe=1h "
    "(source=binance_vision_monthly + binance_vision_daily_gap_repair; "
    "accepted by BIN-1H-CSLGBM data freeze)",
    "null_policy": "no filling; missing 1h bars simply shrink the 1d aggregate",
}


def kline_globs() -> list[str]:
    # date=* legacy per-day partitions are PRIMARY storage for BTC/ETH/SOL/BNB/TRX/HYPE
    # after each symbol's legacy start (BTC 2023-05-27, ETH/SOL/BNB/TRX 2024-07-03,
    # HYPE 2025-05-30): the monthly sync's remove_legacy_overlap excludes those keys
    # from source=binance_vision_monthly, so omitting date=* silently drops the majors.
    return [
        str(KLINE_1H_ROOT / "source=binance_vision_monthly" / "month=*" / "*.parquet"),
        str(KLINE_1H_ROOT / "source=binance_vision_daily_gap_repair" / "**" / "*.parquet"),
        str(KLINE_1H_ROOT / "date=*" / "*.parquet"),
    ]


def symbol_cache_dir() -> Path:
    return CACHE_DIR / "klines_by_symbol"


def ensure_symbol_partition_cache() -> Path:
    target = symbol_cache_dir()
    marker = target / "_build_complete.json"
    if marker.exists():
        return target
    if target.exists():
        import shutil

        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    con = ec.connect()
    globs = ", ".join(f"'{glob}'" for glob in kline_globs())
    con.execute(
        f"""
        COPY (
            SELECT
                sym_key,
                time_bucket(INTERVAL '1 day', ts) AS ts,
                arg_min(open, ts) AS open,
                max(high) AS high,
                min(low) AS low,
                arg_max(close, ts) AS close,
                sum(volume) AS volume,
                sum(quote_volume) AS quote_volume,
                sum(trade_count) AS trade_count,
                sum(taker_buy_volume) AS taker_buy_volume,
                sum(taker_buy_quote_volume) AS taker_buy_quote_volume,
                count(*) AS bars_1h
            FROM (
                SELECT
                    {ec.sym_key_expr()} AS sym_key, ts, open, high, low, close,
                    volume, quote_volume, trade_count,
                    taker_buy_volume, taker_buy_quote_volume,
                    row_number() OVER (
                        PARTITION BY {ec.sym_key_expr()}, ts
                        ORDER BY CASE WHEN source = 'binance_vision_monthly' THEN 0 ELSE 1 END
                    ) AS rn
                FROM read_parquet([{globs}], union_by_name=true)
                WHERE symbol IS NOT NULL
            )
            WHERE rn = 1
            GROUP BY sym_key, time_bucket(INTERVAL '1 day', ts)
        ) TO '{target}' (FORMAT PARQUET, PARTITION_BY (sym_key), COMPRESSION ZSTD)
        """
    )
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{target}/**/*.parquet')").fetchone()[0]
    marker.write_text(
        json.dumps({"rows": int(rows), "generated_at": pd.Timestamp.now("UTC").isoformat(),
                    "provenance": PROVENANCE}),
        encoding="utf-8",
    )
    return target


def list_cached_symbols() -> list[str]:
    return sorted(
        path.name.removeprefix("sym_key=")
        for path in symbol_cache_dir().glob("sym_key=*")
        if path.is_dir()
    )


def load_symbol_frame(sym_key: str) -> pd.DataFrame:
    con = ec.connect()
    frame = con.execute(
        f"SELECT * FROM read_parquet('{symbol_cache_dir()}/sym_key={sym_key}/*.parquet') ORDER BY ts"
    ).fetch_df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    if frame["ts"].duplicated().any():
        raise RuntimeError(f"duplicate 1d timestamps for {sym_key}")
    return frame


def build_daily_stats() -> pd.DataFrame:
    path = CACHE_DIR / "daily_stats.parquet"
    if path.exists():
        return pd.read_parquet(path)
    con = ec.connect()
    frame = con.execute(
        f"""
        SELECT sym_key, CAST(date_trunc('day', ts) AS DATE) AS day,
               sum(quote_volume) AS quote_volume, count(*) AS bars
        FROM read_parquet('{symbol_cache_dir()}/**/*.parquet', hive_partitioning=true)
        GROUP BY 1, 2 ORDER BY 1, 2
        """
    ).fetch_df()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


def build_universe(daily: pd.DataFrame) -> pd.DataFrame:
    """15m engine's point-in-time universe with 1d coverage (1 bar/day)."""
    excluded = ec.excluded_bases()
    frames = []
    archive_end = pd.Timestamp(daily["day"].max())
    for sym_key, group in daily.groupby("sym_key", sort=True):
        group = group.sort_values("day").set_index(pd.DatetimeIndex(group["day"]))
        full = group.reindex(pd.date_range(group.index.min(), group.index.max(), freq="D"))
        full["quote_volume"] = full["quote_volume"].fillna(0.0)
        full["bars"] = full["bars"].fillna(0)
        adv = full["quote_volume"].rolling(30, min_periods=30).mean().shift(1)
        coverage = full["bars"].rolling(30, min_periods=30).sum().shift(1) / (
            30.0 * BARS_PER_DAY
        )
        listed_days = np.arange(len(full))
        sym_last = full.index.max()
        delist_cut = (
            sym_last - pd.Timedelta(days=ec.DELIST_GUARD_DAYS)
            if sym_last < archive_end - pd.Timedelta(days=2)
            else sym_last
        )
        eligible = (
            (listed_days >= ec.MIN_LISTING_DAYS)
            & (adv.to_numpy() >= ec.MIN_ADV_USDT)
            & (coverage.to_numpy() >= ec.MIN_COVERAGE)
            & (full.index <= delist_cut)
            & (sym_key not in excluded)
        )
        frames.append(
            pd.DataFrame(
                {"sym_key": sym_key, "day": full.index, "eligible": eligible, "adv_30d": adv.to_numpy()}
            )
        )
    eligibility = pd.concat(frames, ignore_index=True)
    eligibility["rank"] = (
        eligibility.loc[eligibility["eligible"]]
        .groupby("day")["adv_30d"]
        .rank(ascending=False, method="first")
    )
    eligibility["in_trading_pool"] = eligibility["eligible"] & (
        eligibility["rank"] <= ec.TRADING_POOL_SIZE
    )
    return eligibility.drop(columns="rank")


def to_ns(values: pd.Series) -> np.ndarray:
    return values.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")


def extract_symbol(
    sym_key: str,
    eligibility: pd.DataFrame,
    funding_lookup: dict[str, tuple[np.ndarray, np.ndarray]],
) -> pd.DataFrame | None:
    frame = load_symbol_frame(sym_key)
    if len(frame) < ec.WARMUP_BARS + ec.HORIZON_BARS + 2:
        return None
    frame = ec.compute_indicators(frame)
    golden, death = ec.detect_cross_indices(frame)

    ts = frame["ts"]
    ts_ns = to_ns(ts)
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    atr_all = frame["atr"].to_numpy(dtype=float)

    elig = eligibility.loc[eligibility["sym_key"] == sym_key]
    elig_map = elig.set_index("day")[["eligible", "in_trading_pool", "adv_30d"]]

    outputs = []
    for side, signal_idx in ((1, golden), (-1, death)):
        signal_idx = signal_idx[signal_idx >= ec.WARMUP_BARS]
        entry_idx = signal_idx + 1
        keep = entry_idx + ec.HORIZON_BARS <= len(frame) - 1
        signal_idx, entry_idx = signal_idx[keep], entry_idx[keep]
        if len(signal_idx) == 0:
            continue
        entry_ts = ts.iloc[entry_idx]
        in_window = (entry_ts >= DEV_START) & (entry_ts <= DEV_ENTRY_CUTOFF)
        signal_idx, entry_idx = signal_idx[in_window.to_numpy()], entry_idx[in_window.to_numpy()]
        if len(signal_idx) == 0:
            continue

        atr = atr_all[signal_idx]
        entry_price = open_[entry_idx]
        valid = (atr > 0) & (entry_price > 0) & np.isfinite(atr)
        signal_idx, entry_idx = signal_idx[valid], entry_idx[valid]
        atr, entry_price = atr[valid], entry_price[valid]
        if len(signal_idx) == 0:
            continue

        entry_days = ts.iloc[entry_idx].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
        joined = elig_map.reindex(entry_days.to_numpy())
        eligible = joined["eligible"].fillna(False).to_numpy(dtype=bool)
        if not eligible.any():
            continue
        pool = joined["in_trading_pool"].fillna(False).to_numpy(dtype=bool)[eligible]
        signal_idx, entry_idx = signal_idx[eligible], entry_idx[eligible]
        atr, entry_price = atr[eligible], entry_price[eligible]

        atr_frac = atr / entry_price
        row = {
            "sym_key": sym_key,
            "side": side,
            "signal_idx": signal_idx,
            "entry_ts": ts.iloc[entry_idx].to_numpy(),
            "entry_price": entry_price,
            "atr": atr,
            "atr_frac": atr_frac,
            "cost_atr": ec.ROUND_TRIP_COST / atr_frac,
            "in_trading_pool": pool,
        }
        entry_ns = ts_ns[entry_idx]
        fund_ts, fund_cum = funding_lookup.get(
            sym_key, (np.array([], dtype="datetime64[ns]"), np.array([0.0]))
        )
        for name, (k_tp, k_sl) in ec.BRACKETS.items():
            outcome = ec.label_bracket(
                open_, high, low, entry_idx, side, entry_price, atr, k_tp, k_sl
            )
            exit_ns = ts_ns[outcome.exit_index]
            funding = ec.funding_cost(fund_ts, fund_cum, entry_ns, exit_ns, side)
            net_frac = outcome.gross_ret - ec.ROUND_TRIP_COST - funding
            row[f"{name}_label"] = outcome.label
            row[f"{name}_exit_ts"] = ts.iloc[outcome.exit_index].to_numpy()
            row[f"{name}_holding_bars"] = outcome.holding_bars
            row[f"{name}_gross_frac"] = outcome.gross_ret
            row[f"{name}_funding_frac"] = funding
            row[f"{name}_net_frac"] = net_frac
            row[f"{name}_net_atr"] = net_frac / atr_frac
            row[f"{name}_gross_atr"] = outcome.gross_ret / atr_frac
        outputs.append(pd.DataFrame(row))
    if not outputs:
        return None
    return pd.concat(outputs, ignore_index=True)


def bracket_stats(frame: pd.DataFrame, name: str) -> dict:
    if frame.empty:
        return {"events": 0}
    labels = frame[f"{name}_label"]
    return {
        "events": int(len(frame)),
        "sl_first": round(float((labels == 0).mean()), 4),
        "tp_first": round(float((labels == 1).mean()), 4),
        "timeout": round(float((labels == 2).mean()), 4),
        "gross_mean_atr": round(float(frame[f"{name}_gross_atr"].mean()), 4),
        "net_mean_atr": round(float(frame[f"{name}_net_atr"].mean()), 4),
        "net_std_atr": round(float(frame[f"{name}_net_atr"].std()), 4),
        "share_net_positive": round(float((frame[f"{name}_net_atr"] > 0).mean()), 4),
        "median_holding_bars": int(frame[f"{name}_holding_bars"].median()),
    }


def main() -> None:
    print("building derived 1d symbol cache (one-off)...", flush=True)
    ensure_symbol_partition_cache()
    daily = build_daily_stats()
    eligibility = build_universe(daily)
    print(
        f"universe: {daily['sym_key'].nunique()} symbols, "
        f"{int(eligibility['eligible'].sum())} eligible symbol-days",
        flush=True,
    )

    funding = ec.load_funding()
    funding_lookup = {
        key: ec.prepare_funding_lookup(group)
        for key, group in funding.groupby("sym_key", sort=False)
    }

    frames: list[pd.DataFrame] = []
    symbols = list_cached_symbols()
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(extract_symbol, key, eligibility, funding_lookup): key
            for key in symbols
        }
        done = 0
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                frames.append(result)
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"extract {done}/{len(futures)} ({time.monotonic() - started:.0f}s)", flush=True)

    events = pd.concat(frames, ignore_index=True).sort_values(["entry_ts", "sym_key"])
    events = events.reset_index(drop=True)
    events_path = ARTIFACT_DIR / "events_dev_1d.parquet"
    events.to_parquet(events_path, index=False, compression="zstd")

    pool = events.loc[events["in_trading_pool"]]
    years = pd.to_datetime(events["entry_ts"], utc=True).dt.year
    pool_years = pd.to_datetime(pool["entry_ts"], utc=True).dt.year
    dev_end = pd.Timestamp(events["entry_ts"].max())
    report: dict = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": "Binance-1D-EMA-Cross-LightGBM-Event-Selector",
        "market": "Binance USD-M USDT perp, 1d (derived from audited 1h), point-in-time universe",
        "derived_data_provenance": PROVENANCE,
        "window": {"entry_floor": str(DEV_START), "entry_cutoff": str(DEV_ENTRY_CUTOFF)},
        "note": "development window only; 2026H1 is a contaminated holdout for this mechanism; recent slices anchored to dev end and audit-only",
        "cost_model": "fee 0.001 + slip 4bps per fill + as-of funding",
        "signal": {"ema_fast": ec.EMA_FAST, "ema_slow": ec.EMA_SLOW, "atr_len": ec.ATR_LEN,
                    "horizon_bars": ec.HORIZON_BARS},
        "events": {
            "rows": int(len(events)),
            "long": int((events["side"] == 1).sum()),
            "short": int((events["side"] == -1).sum()),
            "symbols": int(events["sym_key"].nunique()),
            "trading_pool_rows": int(len(pool)),
        },
        "cost_atr": {
            "pool_p50": round(float(pool["cost_atr"].quantile(0.5)), 4),
            "pool_p90": round(float(pool["cost_atr"].quantile(0.9)), 4),
            "pool_share_over_0p8": round(float((pool["cost_atr"] > 0.8).mean()), 4),
        },
        "brackets": {},
    }
    for name in ec.BRACKETS:
        entry = {
            "all": bracket_stats(events, name),
            "trading_pool": bracket_stats(pool, name),
            "long": bracket_stats(events.loc[events["side"] == 1], name),
            "short": bracket_stats(events.loc[events["side"] == -1], name),
        }
        entry["pool_by_year_side_net_mean_atr"] = {
            f"{year}_side{side}": round(float(group[f"{name}_net_atr"].mean()), 4)
            for (year, side), group in pool.groupby([pool_years, pool["side"]])
        }
        entry["pool_by_year_side_gross_mean_atr"] = {
            f"{year}_side{side}": round(float(group[f"{name}_gross_atr"].mean()), 4)
            for (year, side), group in pool.groupby([pool_years, pool["side"]])
        }
        report["brackets"][name] = entry

    slices = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}
    entry_ts = pd.to_datetime(pool["entry_ts"], utc=True)
    report["recent_slices_pool_b4_2"] = {
        label: {
            "events": int((entry_ts >= dev_end - pd.Timedelta(days=days)).sum()),
            "net_mean_atr": round(
                float(pool.loc[entry_ts >= dev_end - pd.Timedelta(days=days), "b4_2_net_atr"].mean()),
                4,
            ),
        }
        for label, days in slices.items()
    }

    report["events_sha256"] = hashlib.sha256(events_path.read_bytes()).hexdigest()
    output = ARTIFACT_DIR / "baseline_1d_report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["events", "cost_atr"]}, indent=2))
    for name, entry in report["brackets"].items():
        print(name, "all:", json.dumps(entry["all"]))
        print(name, "pool short:", json.dumps(entry["short"]))
    print(f"report -> {output}")


if __name__ == "__main__":
    main()
