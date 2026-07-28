"""V2 scoring-layer dataset for BIN-4H-EMAX: features for death-cross short events.

Joins the corrected dev events (all eligible shorts, bracket b4_2) with
signal-time features. Feature philosophy follows the 15m family module
(emax_features.py, reused directly for symbol-local features): everything is
relative (ATR / z-score / rank), bar-count windows scale with the timeframe
exactly like the signal (EMA21/96) and label (96-bar timeout) do, no symbol
identity, nothing after the signal bar close. Direction-sensitive features are
flipped so positive = supportive of the short.

Extra 4h-specific market features:
  - btc_dist_ema96_1d: BTC previous completed UTC day close vs daily EMA96
    (continuous version of the A2 gate variable)
  - cross_count_same_ts / cross_count_24h: death-cross clustering (P2 showed
    drawdown is driven by clustered signals)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_15M = ROOT / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector/scripts"
sys.path.insert(0, str(SCRIPTS_15M))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import emax_common as ec  # noqa: E402
import emax_features as ef  # noqa: E402  (frame-level feature functions reused)
import run_baseline as rb  # noqa: E402

ARTIFACT_DIR = rb.ARTIFACT_DIR
BRACKET = "b4_2"
CLUSTER_WINDOW = pd.Timedelta(hours=24)

MARKET_INDEX_START = pd.Timestamp("2019-12-01", tz="UTC")
MARKET_INDEX_END = pd.Timestamp("2026-02-01", tz="UTC")

MARKET_FLIPPED = (
    "breadth_up", "breadth_above_slow", "univ_ret_96_mean",
    "btc_ret_16", "btc_ret_96", "btc_gap_atr",
)


def feature_columns() -> list[str]:
    return (
        [name if name != "atr_frac" else "atr_frac_sig" for name in ef.SYMBOL_FEATURES]
        + ["gap_pre_atr", "bars_since_prev_cross", "crosses_384"]
        + [
            "universe_count", "breadth_up", "breadth_above_slow", "univ_ret_96_mean",
            "csd_96", "btc_ret_16", "btc_ret_96", "btc_gap_atr", "btc_atr_frac",
            "btc_rv_ratio", "btc_dist_ema96_1d",
        ]
        + ["vol_rank_pct", "listing_age_log", "adv_rank_pct"]
        + ["funding_last", "funding_avg_3d", "funding_avg_7d"]
        + ["cross_count_same_ts", "cross_count_24h", "hour_sin", "hour_cos", "day_of_week"]
    )


def load_short_events() -> pd.DataFrame:
    events = pd.read_parquet(ARTIFACT_DIR / "events_dev_4h.parquet")
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    shorts = events.loc[events["side"] == -1].copy()
    shorts["day"] = shorts["entry_ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    return shorts.reset_index(drop=True)


def build_market_table(
    symbols: list[str], eligibility: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cross-sectional per-4h-ts aggregates over ELIGIBLE symbols + BTC state."""
    elig_lookup = {
        sym: set(pd.DatetimeIndex(group.loc[group["eligible"], "day"]).normalize())
        for sym, group in eligibility.groupby("sym_key", sort=False)
    }
    index = pd.date_range(MARKET_INDEX_START, MARKET_INDEX_END, freq="4h", tz="UTC")
    sums: dict[str, np.ndarray] = {}
    daily_atr: list[pd.DataFrame] = []
    btc_state: pd.DataFrame | None = None

    def accumulate(name: str, positions: np.ndarray, values: np.ndarray) -> None:
        array = sums.setdefault(name, np.zeros(len(index)))
        np.add.at(array, positions, values)

    for count, sym in enumerate(symbols, start=1):
        frame = rb.load_symbol_frame(sym)
        if len(frame) < ef.BARS_24H + 2:
            continue
        frame = ec.compute_indicators(frame)
        close = frame["close"]
        frame["up_96"] = (close > close.shift(ef.BARS_24H)).astype(float)
        frame["above_slow"] = (close > frame["ema_slow"]).astype(float)
        frame["ret_96_raw"] = close / close.shift(ef.BARS_24H) - 1.0
        frame["atr_frac"] = frame["atr"] / close

        days = frame["ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
        eligible_mask = days.isin(elig_lookup.get(sym, set())).to_numpy()
        positions = index.get_indexer(frame["ts"])
        ok = (positions >= 0) & eligible_mask & frame["ret_96_raw"].notna().to_numpy()
        positions_ok = positions[ok]
        accumulate("count", positions_ok, np.ones(int(ok.sum())))
        accumulate("up_sum", positions_ok, frame["up_96"].to_numpy()[ok])
        accumulate("above_sum", positions_ok, frame["above_slow"].to_numpy()[ok])
        ret_raw = frame["ret_96_raw"].to_numpy()[ok]
        accumulate("ret_sum", positions_ok, ret_raw)
        accumulate("ret_sumsq", positions_ok, ret_raw**2)

        last_daily = (
            frame.assign(day=days)
            .groupby("day", sort=False)["atr_frac"]
            .last()
            .reset_index()
            .assign(sym_key=sym)
        )
        daily_atr.append(last_daily)

        if sym == "BTC":
            log_ret = np.log(close).diff()
            btc_state = pd.DataFrame(
                {
                    "ts": frame["ts"],
                    "btc_ret_16": (close / close.shift(ef.BARS_4H) - 1.0) / frame["atr_frac"],
                    "btc_ret_96": frame["ret_96_raw"] / frame["atr_frac"],
                    "btc_gap_atr": (frame["ema_fast"] - frame["ema_slow"]) / frame["atr"],
                    "btc_atr_frac": frame["atr_frac"],
                    "btc_rv_ratio": (
                        log_ret.rolling(ef.BARS_4H).std()
                        / log_ret.rolling(ef.BARS_24H).std().replace(0.0, np.nan)
                    ),
                }
            )
        if count % 200 == 0:
            print(f"market pass {count}/{len(symbols)}", flush=True)

    if btc_state is None:
        raise RuntimeError("missing BTC in cache")
    count_arr = sums["count"]
    with np.errstate(invalid="ignore", divide="ignore"):
        table = pd.DataFrame(
            {
                "ts": index,
                "universe_count": count_arr,
                "breadth_up": sums["up_sum"] / count_arr,
                "breadth_above_slow": sums["above_sum"] / count_arr,
                "univ_ret_96_mean": sums["ret_sum"] / count_arr,
                "csd_96": np.sqrt(
                    np.maximum(
                        sums["ret_sumsq"] / count_arr - (sums["ret_sum"] / count_arr) ** 2, 0.0
                    )
                ),
            }
        )
    table = table.merge(btc_state, on="ts", how="left").set_index("ts")

    daily_vol = pd.concat(daily_atr, ignore_index=True)
    daily_vol["day"] = pd.DatetimeIndex(daily_vol["day"])
    daily_vol["vol_rank_pct"] = daily_vol.groupby("day")["atr_frac"].rank(pct=True)
    daily_vol["day"] = daily_vol["day"] + pd.Timedelta(days=1)  # as-of previous day
    vol_rank = daily_vol[["sym_key", "day", "vol_rank_pct"]]
    return table, vol_rank


def btc_daily_dist() -> pd.Series:
    """Fractional distance of BTC's previous completed daily close to its daily EMA96."""
    btc = rb.load_symbol_frame("BTC")
    daily = btc.set_index("ts")["close"].resample("1D").last().dropna()
    ema96 = daily.ewm(span=96, adjust=False).mean()
    dist = daily / ema96 - 1.0
    dist.index = (dist.index + pd.Timedelta(days=1)).tz_convert("UTC").tz_localize(None)
    return dist


def symbol_features(events: pd.DataFrame) -> pd.DataFrame:
    """Signal-bar features per event, reusing the 15m frame-level feature module."""
    rows: list[pd.DataFrame] = []
    for sym, group in events.groupby("sym_key", sort=True):
        frame = rb.load_symbol_frame(sym)
        frame = ef.symbol_indicator_frame(frame)
        golden, death = ec.detect_cross_indices(frame)
        all_cross = np.sort(np.concatenate([golden, death]))
        sig = group["signal_idx"].to_numpy(dtype=int)
        expected = rb.to_ns(frame["ts"])[sig + 1]
        actual = rb.to_ns(group["entry_ts"])
        if not (expected == actual).all():
            raise RuntimeError(f"signal_idx misaligned for {sym}")
        feat = frame.iloc[sig][list(ef.SYMBOL_FEATURES)].reset_index(drop=True)
        for name, aligned in ef.SYMBOL_FEATURES.items():
            if aligned:
                feat[name] = -feat[name]  # short side: flip direction-sensitive features
        feat["gap_pre_atr"] = -frame["gap_atr"].to_numpy()[np.maximum(sig - 1, 0)]
        prev_pos = np.searchsorted(all_cross, sig, side="left") - 1
        feat["bars_since_prev_cross"] = np.where(
            prev_pos >= 0, sig - all_cross[np.maximum(prev_pos, 0)], np.nan
        )
        feat["crosses_384"] = np.searchsorted(all_cross, sig, side="left") - np.searchsorted(
            all_cross, sig - 4 * ef.BARS_24H, side="left"
        )
        feat["sym_key"] = sym
        feat["entry_ts"] = group["entry_ts"].to_numpy()
        # events carry their own atr_frac (atr / entry_price) used for sizing
        feat = feat.rename(columns={"atr_frac": "atr_frac_sig"})
        rows.append(feat)
    return pd.concat(rows, ignore_index=True)


def funding_features(events: pd.DataFrame) -> np.ndarray:
    funding = ec.load_funding()
    lookup: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for sym, group in funding.groupby("sym_key", sort=False):
        lookup[sym] = (
            rb.to_ns(group["ts"]),
            group["funding_rate"].to_numpy(dtype=float),
        )
    out = np.full((len(events), 3), np.nan)
    entry_ns = rb.to_ns(events["entry_ts"])
    sym_arr = events["sym_key"].to_numpy()
    for i in range(len(events)):
        pair = lookup.get(sym_arr[i])
        if pair is None:
            continue
        f_ts, f_rate = pair
        ts = entry_ns[i]
        p = int(np.searchsorted(f_ts, ts, side="right")) - 1
        if p < 0:
            continue
        out[i, 0] = f_rate[p]
        lo3 = int(np.searchsorted(f_ts, ts - np.timedelta64(3, "D"), side="left"))
        lo7 = int(np.searchsorted(f_ts, ts - np.timedelta64(7, "D"), side="left"))
        if p >= lo3:
            out[i, 1] = f_rate[lo3 : p + 1].mean()
        if p >= lo7:
            out[i, 2] = f_rate[lo7 : p + 1].mean()
    # short side: positive funding is received by shorts -> already supportive; keep sign
    return out


def main() -> None:
    events = load_short_events()
    print(f"short events: {len(events)} (pool {int(events['in_trading_pool'].sum())})", flush=True)

    daily = rb.build_daily_stats()
    eligibility = rb.build_universe(daily)
    symbols = rb.list_cached_symbols()
    market, vol_rank = build_market_table(symbols, eligibility)
    dist_1d = btc_daily_dist()

    feat = symbol_features(events)
    dataset = events.merge(feat, on=["sym_key", "entry_ts"], how="left", validate="1:1")

    # market state as-of the signal bar (= entry bar minus one 4h bar)
    signal_ts = dataset["entry_ts"] - pd.Timedelta(hours=4)
    mkt = market.reindex(pd.DatetimeIndex(signal_ts)).reset_index(drop=True)
    for col in mkt.columns:
        dataset[col] = mkt[col].to_numpy()
    for col in MARKET_FLIPPED:
        dataset[col] = -dataset[col]

    # flipped: positive = BTC below its daily EMA96 (short-supportive)
    dataset["btc_dist_ema96_1d"] = -dist_1d.reindex(pd.DatetimeIndex(dataset["day"])).to_numpy()

    dataset = dataset.merge(vol_rank, on=["sym_key", "day"], how="left", validate="m:1")

    first_day = daily.groupby("sym_key")["day"].min()
    first_arr = pd.DatetimeIndex(first_day.reindex(dataset["sym_key"]).to_numpy())
    age_days = (
        (dataset["day"].to_numpy() - first_arr.to_numpy()) / np.timedelta64(1, "D")
    ).astype(float)
    dataset["listing_age_log"] = np.log1p(np.maximum(age_days, 0.0))

    elig_rank = eligibility.loc[eligibility["eligible"]].copy()
    elig_rank["day"] = pd.DatetimeIndex(elig_rank["day"])
    elig_rank["adv_rank_pct"] = elig_rank.groupby("day")["adv_30d"].rank(pct=True)
    dataset = dataset.merge(
        elig_rank[["sym_key", "day", "adv_rank_pct"]],
        on=["sym_key", "day"],
        how="left",
        validate="m:1",
    )

    fund = funding_features(dataset)
    dataset["funding_last"] = fund[:, 0]
    dataset["funding_avg_3d"] = fund[:, 1]
    dataset["funding_avg_7d"] = fund[:, 2]

    per_ts = dataset.groupby("entry_ts").size().rename("cross_count_same_ts")
    dataset = dataset.merge(per_ts, left_on="entry_ts", right_index=True, how="left")
    ts_counts = per_ts.sort_index()
    rolling = ts_counts.rolling(CLUSTER_WINDOW, closed="left").sum()
    dataset["cross_count_24h"] = rolling.reindex(dataset["entry_ts"]).fillna(0.0).to_numpy()

    dataset["hour_sin"] = np.sin(2 * np.pi * dataset["entry_ts"].dt.hour / 24.0)
    dataset["hour_cos"] = np.cos(2 * np.pi * dataset["entry_ts"].dt.hour / 24.0)
    dataset["day_of_week"] = dataset["entry_ts"].dt.dayofweek.astype(float)

    out_path = ARTIFACT_DIR / "v2_dataset_short.parquet"
    dataset.to_parquet(out_path, index=False, compression="zstd")

    cols = feature_columns()
    nan_share = dataset[cols].isna().mean().sort_values(ascending=False)
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "rows": int(len(dataset)),
        "pool_rows": int(dataset["in_trading_pool"].sum()),
        "features": len(cols),
        "worst_nan_share": {k: round(float(v), 4) for k, v in nan_share.head(8).items()},
        "label_dist_b4_2": {
            str(k): float(v)
            for k, v in dataset[f"{BRACKET}_label"].value_counts(normalize=True).round(4).items()
        },
    }
    (ARTIFACT_DIR / "v2_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"dataset -> {out_path}")


if __name__ == "__main__":
    main()
