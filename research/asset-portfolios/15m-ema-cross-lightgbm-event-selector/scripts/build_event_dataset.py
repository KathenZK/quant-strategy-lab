"""Phase 2 for BIN-15M-EMAX-LGBM: event dataset with features, labels, weights.

One row per eligible event. Features follow the frozen V1 feature list; all
values use only information available at the signal bar close. Weights combine
per-coin balancing with same-hour same-side cluster downweighting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import emax_common as ec
import emax_features as ef


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=ec.ARTIFACT_DIR / "events_dev.parquet")
    parser.add_argument(
        "--output", type=Path, default=ec.ARTIFACT_DIR / "event_dataset_dev.parquet"
    )
    return parser.parse_args()


def funding_features(
    funding: pd.DataFrame, sym_key: str, signal_ts: pd.Series, side: np.ndarray
) -> pd.DataFrame:
    group = funding.loc[funding["sym_key"] == sym_key]
    ts = group["ts"].to_numpy(dtype="datetime64[ns]")
    rates = group["funding_rate"].to_numpy()
    signal_ns = signal_ts.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
    out = pd.DataFrame(index=range(len(signal_ns)))
    if len(ts) == 0:
        for column in ["funding_last", "funding_avg_3d", "funding_avg_7d", "funding_pos_30d"]:
            out[column] = np.nan
        return out

    idx = np.searchsorted(ts, signal_ns, side="right") - 1
    last = np.where(idx >= 0, rates[np.maximum(idx, 0)], np.nan)
    cum = np.concatenate([[0.0], np.cumsum(rates)])

    def window_mean(days: int) -> np.ndarray:
        start = signal_ns - np.timedelta64(days, "D")
        lo = np.searchsorted(ts, start, side="right")
        hi = idx + 1
        count = np.maximum(hi - lo, 0)
        total = cum[np.maximum(hi, 0)] - cum[np.minimum(lo, len(rates))]
        return np.where(count > 0, total / np.maximum(count, 1), np.nan)

    pos = np.full(len(signal_ns), np.nan)
    start30 = signal_ns - np.timedelta64(30, "D")
    lo30 = np.searchsorted(ts, start30, side="right")
    for i in range(len(signal_ns)):
        if idx[i] >= 0 and idx[i] + 1 > lo30[i]:
            window = rates[lo30[i] : idx[i] + 1]
            span = window.max() - window.min()
            pos[i] = (last[i] - window.min()) / span if span > 0 else 0.5

    out["funding_last"] = side * last
    out["funding_avg_3d"] = side * window_mean(3)
    out["funding_avg_7d"] = side * window_mean(7)
    out["funding_pos_30d"] = pos
    return out


def cluster_features(events: pd.DataFrame) -> pd.DataFrame:
    """Same-hour same-side event counts and 24h cross-rate ratio."""
    events = events.copy()
    hour = events["entry_ts"].dt.floor("h")
    events["cross_count_1h_same_side"] = (
        events.groupby([hour, "side"])["sym_key"].transform("size").astype(float)
    )
    out = np.full(len(events), np.nan)
    for side in (1, -1):
        mask = (events["side"] == side).to_numpy()
        ts = events.loc[mask, "entry_ts"].to_numpy(dtype="datetime64[ns]")
        order = np.argsort(ts, kind="stable")
        sorted_ts = ts[order]
        lo_24h = np.searchsorted(sorted_ts, sorted_ts - np.timedelta64(1, "D"), side="left")
        lo_30d = np.searchsorted(sorted_ts, sorted_ts - np.timedelta64(30, "D"), side="left")
        pos = np.arange(len(sorted_ts))
        count_24h = pos - lo_24h + 1.0
        daily_mean_30d = (pos - lo_30d + 1.0) / 30.0
        ratio = count_24h / np.maximum(daily_mean_30d, 1e-9)
        unsorted = np.empty(len(sorted_ts))
        unsorted[order] = ratio
        out[mask] = unsorted
    events["cross_ratio_24h_same_side"] = out
    return events


def btc_beta_corr(
    frame: pd.DataFrame, btc_hourly: pd.Series, signal_ts: pd.Series
) -> pd.DataFrame:
    log_ret = np.log(frame["close"]).diff()
    hourly = log_ret.groupby(frame["ts"].dt.floor("h")).sum()
    joined = pd.concat(
        [hourly.rename("sym"), btc_hourly.rename("btc")], axis=1, sort=True
    ).dropna()
    if len(joined) < 400:
        return pd.DataFrame(
            {"beta_btc_30d": np.nan, "corr_btc_30d": np.nan}, index=range(len(signal_ts))
        )
    window = 720
    cov = joined["sym"].rolling(window, min_periods=360).cov(joined["btc"])
    var = joined["btc"].rolling(window, min_periods=360).var()
    corr = joined["sym"].rolling(window, min_periods=360).corr(joined["btc"])
    stats = pd.DataFrame({"beta_btc_30d": cov / var, "corr_btc_30d": corr})
    idx = stats.index.searchsorted(signal_ts.dt.floor("h"), side="right") - 1
    valid = idx >= 0
    out = pd.DataFrame(
        {
            "beta_btc_30d": np.where(valid, stats["beta_btc_30d"].to_numpy()[np.maximum(idx, 0)], np.nan),
            "corr_btc_30d": np.where(valid, stats["corr_btc_30d"].to_numpy()[np.maximum(idx, 0)], np.nan),
        },
        index=range(len(signal_ts)),
    )
    return out


def main() -> None:
    args = parse_args()
    events = pd.read_parquet(args.events)
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    events["signal_ts"] = pd.to_datetime(events["signal_ts"], utc=True)
    print(f"events: {len(events)} rows, {events['sym_key'].nunique()} symbols", flush=True)

    daily = ec.build_daily_stats()
    universe = ec.build_universe(daily)
    eligibility = universe.eligibility
    eligibility["adv_rank_pct"] = (
        eligibility.loc[eligibility["eligible"]]
        .groupby("day")["adv_30d"]
        .rank(pct=True)
    )

    symbols = sorted(events["sym_key"].unique())
    market = ef.build_market_state(ec.list_cached_symbols(), eligibility)
    market_table = market.table
    btc_hourly = (
        market_table["btc_log_ret"].groupby(market_table.index.floor("h")).sum()
    )
    funding = ec.load_funding()

    blocks: list[pd.DataFrame] = []
    started = time.monotonic()
    for count, sym_key in enumerate(symbols, start=1):
        rows = events.loc[events["sym_key"] == sym_key].copy()
        frame = ef.symbol_indicator_frame(ec.load_symbol_frame(sym_key))
        signal_idx = rows["signal_idx"].to_numpy()
        side = rows["side"].to_numpy()

        block = rows.reset_index(drop=True)
        for name, aligned in ef.SYMBOL_FEATURES.items():
            values = frame[name].to_numpy()[signal_idx]
            block[name] = values * side if aligned else values

        gap = frame["gap_atr"].to_numpy()
        block["gap_pre_atr"] = gap[np.maximum(signal_idx - 1, 0)] * side

        all_cross = np.sort(np.concatenate(ec.detect_cross_indices(frame)))
        pos = np.searchsorted(all_cross, signal_idx, side="left")
        prev_cross = np.where(pos > 0, all_cross[np.maximum(pos - 1, 0)], -1)
        block["bars_since_prev_cross"] = np.where(
            prev_cross >= 0, signal_idx - prev_cross, np.nan
        )
        lo384 = np.searchsorted(all_cross, signal_idx - 384, side="left")
        block["crosses_384"] = (pos - lo384).astype(float)

        block = pd.concat(
            [
                block,
                funding_features(funding, sym_key, rows["signal_ts"], side).set_index(block.index),
                btc_beta_corr(frame, btc_hourly, rows["signal_ts"]).set_index(block.index),
            ],
            axis=1,
        )

        market_rows = market_table.reindex(rows["signal_ts"].to_numpy())
        for col in ["btc_ret_16", "btc_ret_96", "btc_gap_atr"]:
            block[col] = market_rows[col].to_numpy() * side
        for col in ["btc_atr_frac", "btc_rv_ratio", "csd_24h", "universe_count"]:
            block[col] = market_rows[col].to_numpy()
        block["breadth_up_bias"] = (2.0 * market_rows["breadth_up"].to_numpy() - 1.0) * side
        block["breadth_above_slow_bias"] = (
            2.0 * market_rows["breadth_above_slow"].to_numpy() - 1.0
        ) * side
        rel = (
            frame["ret_24h_raw"].to_numpy()[signal_idx]
            - market_rows["univ_ret_24h_mean"].to_numpy()
        ) / frame["atr_frac"].to_numpy()[signal_idx]
        block["rel_strength_24h"] = rel * side

        blocks.append(block)
        if count % 50 == 0 or count == len(symbols):
            print(f"features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)

    data = pd.concat(blocks, ignore_index=True)

    # market-level funding mean (eligible universe, as-of previous day)
    fund_daily = funding.copy()
    fund_daily["day"] = fund_daily["ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    daily_mean = fund_daily.groupby("day")["funding_rate"].mean()
    event_day = (
        data["signal_ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
        - pd.Timedelta(days=1)
    )
    data["mkt_funding_mean"] = daily_mean.reindex(event_day.to_numpy()).to_numpy() * data["side"]

    # universe/day structural features
    day_naive = data["entry_ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    elig_idx = eligibility.set_index(["sym_key", "day"])
    keys = pd.MultiIndex.from_arrays([data["sym_key"], day_naive])
    data["adv_rank_pct"] = elig_idx["adv_rank_pct"].reindex(keys).to_numpy()
    first_days = pd.Series(universe.first_day)
    listing_age = (day_naive - first_days.reindex(data["sym_key"]).to_numpy()).dt.days
    data["listing_age_log"] = np.log1p(listing_age.astype(float))
    vol_rank = market.daily_vol_rank.set_index(["sym_key", "day"])["vol_rank_pct"]
    data["vol_rank_pct"] = vol_rank.reindex(keys).to_numpy()

    # time features
    hour_frac = data["entry_ts"].dt.hour + data["entry_ts"].dt.minute / 60.0
    data["hour_sin"] = np.sin(2 * np.pi * hour_frac / 24.0)
    data["hour_cos"] = np.cos(2 * np.pi * hour_frac / 24.0)
    data["day_of_week"] = data["entry_ts"].dt.dayofweek.astype(float)
    next_funding = data["entry_ts"].dt.ceil("8h")
    data["bars_to_next_funding"] = (
        (next_funding - data["entry_ts"]).dt.total_seconds() / 900.0
    )

    data = cluster_features(data)

    # weights: per-coin balancing x same-hour cluster downweight, per side
    cluster_n = data["cross_count_1h_same_side"]
    coin_n = data.groupby(["sym_key", "side"])["sym_key"].transform("size")
    raw_weight = 1.0 / (coin_n * cluster_n)
    data["weight"] = raw_weight * len(data) / raw_weight.sum()

    feature_columns = (
        list(ef.SYMBOL_FEATURES)
        + ef.EVENT_LEVEL_FEATURES
        + ["beta_btc_30d", "corr_btc_30d"]
        + ef.MARKET_FEATURES_ALIGNED
        + ef.MARKET_FEATURES_RAW
    )
    missing = [column for column in feature_columns if column not in data.columns]
    if missing:
        raise RuntimeError(f"missing feature columns: {missing}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output, index=False, compression="zstd")
    sha = hashlib.sha256(args.output.read_bytes()).hexdigest()
    nan_share = {
        column: float(data[column].isna().mean()) for column in feature_columns
    }
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md",
        "events_input": str(args.events),
        "rows": len(data),
        "feature_count": len(feature_columns),
        "features": feature_columns,
        "aligned_features": [name for name, aligned in ef.SYMBOL_FEATURES.items() if aligned]
        + ef.MARKET_FEATURES_ALIGNED
        + ["gap_pre_atr"],
        "nan_share": nan_share,
        "weights": "per-coin balancing x same-hour same-side cluster downweight",
        "output": str(args.output.relative_to(ec.ROOT)),
        "output_sha256": sha,
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    high_nan = {k: v for k, v in nan_share.items() if v > 0.2}
    print("rows:", len(data), "features:", len(feature_columns))
    print("high-NaN features (>20%):", json.dumps(high_nan, indent=2))
    print(f"dataset -> {args.output}")


if __name__ == "__main__":
    main()
