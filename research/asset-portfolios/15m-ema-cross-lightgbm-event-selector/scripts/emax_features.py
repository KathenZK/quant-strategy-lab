"""Feature computation for BIN-15M-EMAX-LGBM (V1 feature list, ~50 features).

All features are relative (ATR / z-score / range-position), use only data known
at the signal bar close, and never encode symbol identity. Direction-sensitive
features are aligned by side (positive = supportive of the trade direction) so
the two per-side models share one feature codebase.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import emax_common as ec


BARS_4H = 16
BARS_24H = 96
BARS_30D = 2880
RET_WINDOWS = (1, 4, 8, 16, 32, 96)


def rolling_range_position(series: pd.Series, window: int) -> pd.Series:
    """Position of the current value inside its trailing rolling range [0, 1]."""
    low = series.rolling(window, min_periods=window // 2).min()
    high = series.rolling(window, min_periods=window // 2).max()
    span = (high - low).replace(0.0, np.nan)
    return (series - low) / span


def wilder_adx(frame: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = frame["high"], frame["low"], frame["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    alpha = 1.0 / length
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=alpha, adjust=False).mean()


def symbol_indicator_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Extend the kline frame with everything symbol-local features need."""
    out = ec.compute_indicators(frame)
    close = out["close"]
    atr = out["atr"]
    atr_frac = atr / close

    out["atr_frac"] = atr_frac
    out["gap_atr"] = (out["ema_fast"] - out["ema_slow"]) / atr
    out["fast_slope_4"] = out["ema_fast"].diff(4) / atr
    out["fast_slope_16"] = out["ema_fast"].diff(BARS_4H) / atr
    out["slow_slope_16"] = out["ema_slow"].diff(BARS_4H) / atr
    out["slow_slope_96"] = out["ema_slow"].diff(BARS_24H) / atr
    out["slope_diff_16"] = out["fast_slope_16"] - out["slow_slope_16"]
    out["entangled"] = (out["gap_atr"].abs() < 0.25).astype(float)
    out["entangle_96"] = out["entangled"].rolling(BARS_24H, min_periods=1).sum()
    out["price_to_fast_atr"] = (close - out["ema_fast"]) / atr
    out["price_to_slow_atr"] = (close - out["ema_slow"]) / atr

    log_ret = np.log(close).diff()
    for window in RET_WINDOWS:
        out[f"ret_{window}"] = (close / close.shift(window) - 1.0) / atr_frac
    out["adx_14"] = wilder_adx(out)
    delta_sum = close.diff().abs().rolling(BARS_24H).sum().replace(0.0, np.nan)
    out["efficiency_96"] = (close - close.shift(BARS_24H)).abs() / delta_sum
    high96 = out["high"].rolling(BARS_24H).max()
    low96 = out["low"].rolling(BARS_24H).min()
    out["dist_high_24h"] = (high96 - close) / atr
    out["dist_low_24h"] = (close - low96) / atr
    span96 = (high96 - low96).replace(0.0, np.nan)
    out["donchian_pos_96"] = (close - low96) / span96
    color = np.sign(close - out["open"])
    run = color.groupby((color != color.shift()).cumsum()).cumcount() + 1
    out["color_run"] = (run * color).astype(float)

    out["rv_4h"] = log_ret.rolling(BARS_4H).std()
    out["rv_24h"] = log_ret.rolling(BARS_24H).std()
    out["rv_ratio"] = out["rv_4h"] / out["rv_24h"].replace(0.0, np.nan)
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    out["bb_width_atr"] = 4.0 * std20 / atr
    out["atr_pos_30d"] = rolling_range_position(atr_frac, BARS_30D)
    prev_close = close.shift(1)
    tr = pd.concat(
        [out["high"] - out["low"], (out["high"] - prev_close).abs(), (out["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    out["tr_over_atr"] = tr / atr

    qv = out["quote_volume"]
    qv_mean96 = qv.rolling(BARS_24H).mean()
    qv_std96 = qv.rolling(BARS_24H).std().replace(0.0, np.nan)
    out["vol_z_96"] = (qv - qv_mean96) / qv_std96
    out["vol_ratio_4_24"] = qv.rolling(BARS_4H).mean() / qv_mean96.replace(0.0, np.nan)
    out["qv_rel_30d"] = qv / qv.rolling(BARS_30D, min_periods=BARS_30D // 2).mean()
    taker_ratio = out["taker_buy_volume"] / out["volume"].replace(0.0, np.nan)
    out["taker_bias"] = 2.0 * taker_ratio - 1.0
    tc = out["trade_count"].astype(float)
    tc_std = tc.rolling(BARS_24H).std().replace(0.0, np.nan)
    out["tc_z_96"] = (tc - tc.rolling(BARS_24H).mean()) / tc_std
    impact = log_ret.abs() / qv.replace(0.0, np.nan)
    out["impact_rel_96"] = impact / impact.rolling(BARS_24H).mean().replace(0.0, np.nan)

    out["up_24h"] = (close > close.shift(BARS_24H)).astype(float)
    out["above_slow"] = (close > out["ema_slow"]).astype(float)
    out["ret_24h_raw"] = close / close.shift(BARS_24H) - 1.0
    return out


# feature -> aligned by side (multiplied by +1 long / -1 short)
SYMBOL_FEATURES: dict[str, bool] = {
    "gap_atr": True,
    "fast_slope_4": True,
    "fast_slope_16": True,
    "slow_slope_16": True,
    "slow_slope_96": True,
    "slope_diff_16": True,
    "entangle_96": False,
    "price_to_fast_atr": True,
    "price_to_slow_atr": True,
    "ret_1": True,
    "ret_4": True,
    "ret_8": True,
    "ret_16": True,
    "ret_32": True,
    "ret_96": True,
    "adx_14": False,
    "efficiency_96": False,
    "dist_high_24h": False,
    "dist_low_24h": False,
    "donchian_pos_96": False,
    "color_run": True,
    "atr_frac": False,
    "rv_ratio": False,
    "bb_width_atr": False,
    "atr_pos_30d": False,
    "tr_over_atr": False,
    "vol_z_96": False,
    "vol_ratio_4_24": False,
    "qv_rel_30d": False,
    "taker_bias": True,
    "tc_z_96": False,
    "impact_rel_96": False,
}

# cross-geometry features computed at event assembly time
EVENT_LEVEL_FEATURES = [
    "gap_pre_atr",
    "bars_since_prev_cross",
    "crosses_384",
]

MARKET_FEATURES_ALIGNED = [
    "btc_ret_16",
    "btc_ret_96",
    "btc_gap_atr",
    "breadth_up_bias",
    "breadth_above_slow_bias",
    "rel_strength_24h",
    "funding_last",
    "funding_avg_3d",
    "funding_avg_7d",
    "mkt_funding_mean",
]
MARKET_FEATURES_RAW = [
    "btc_atr_frac",
    "btc_rv_ratio",
    "csd_24h",
    "cross_count_1h_same_side",
    "cross_ratio_24h_same_side",
    "funding_pos_30d",
    "bars_to_next_funding",
    "listing_age_log",
    "adv_rank_pct",
    "vol_rank_pct",
    "hour_sin",
    "hour_cos",
    "day_of_week",
]


@dataclass(slots=True)
class MarketState:
    """Global per-ts cross-sectional aggregates plus BTC state."""

    table: pd.DataFrame  # indexed by ts
    daily_vol_rank: pd.DataFrame  # sym_key, day, vol_rank_pct (as-of previous day)


def build_market_state(
    symbols: list[str],
    eligibility: pd.DataFrame,
    *,
    progress_every: int = 100,
) -> MarketState:
    """One pass over symbols accumulating cross-sectional sums per 15m ts."""
    elig_lookup = {
        sym: set(
            pd.DatetimeIndex(
                group.loc[group["eligible"], "day"]
            ).normalize()
        )
        for sym, group in eligibility.groupby("sym_key", sort=False)
    }

    index: pd.DatetimeIndex | None = None
    sums: dict[str, np.ndarray] = {}
    daily_atr: list[pd.DataFrame] = []
    btc_state: pd.DataFrame | None = None

    def accumulate(name: str, positions: np.ndarray, values: np.ndarray) -> None:
        array = sums.setdefault(name, np.zeros(len(index)))
        np.add.at(array, positions, values)

    for count, sym in enumerate(symbols, start=1):
        frame = ec.load_symbol_frame(sym)
        if len(frame) < BARS_24H + 2:
            continue
        frame = ec.compute_indicators(frame)
        close = frame["close"]
        frame["up_24h"] = (close > close.shift(BARS_24H)).astype(float)
        frame["above_slow"] = (close > frame["ema_slow"]).astype(float)
        frame["ret_24h_raw"] = close / close.shift(BARS_24H) - 1.0
        frame["atr_frac"] = frame["atr"] / close

        days = frame["ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
        eligible_days = elig_lookup.get(sym, set())
        eligible_mask = days.isin(eligible_days).to_numpy()

        if index is None:
            start = pd.Timestamp("2019-12-01", tz="UTC")
            end = pd.Timestamp("2026-07-01", tz="UTC")
            index = pd.date_range(start, end, freq="15min")
        positions = index.get_indexer(frame["ts"])
        ok = (positions >= 0) & eligible_mask & frame["ret_24h_raw"].notna().to_numpy()
        positions_ok = positions[ok]
        accumulate("count", positions_ok, np.ones(ok.sum()))
        accumulate("up_sum", positions_ok, frame["up_24h"].to_numpy()[ok])
        accumulate("above_sum", positions_ok, frame["above_slow"].to_numpy()[ok])
        ret_raw = frame["ret_24h_raw"].to_numpy()[ok]
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
                    "btc_ret_16": (close / close.shift(BARS_4H) - 1.0) / frame["atr_frac"],
                    "btc_ret_96": frame["ret_24h_raw"] / frame["atr_frac"],
                    "btc_gap_atr": (frame["ema_fast"] - frame["ema_slow"]) / frame["atr"],
                    "btc_atr_frac": frame["atr_frac"],
                    "btc_rv_ratio": (
                        log_ret.rolling(BARS_4H).std()
                        / log_ret.rolling(BARS_24H).std().replace(0.0, np.nan)
                    ),
                    "btc_close": close,
                    "btc_log_ret": log_ret,
                }
            )
        if count % progress_every == 0:
            print(f"market state {count}/{len(symbols)}", flush=True)

    if index is None or btc_state is None:
        raise RuntimeError("market state build failed: no data or missing BTC")

    count_arr = sums["count"]
    with np.errstate(invalid="ignore", divide="ignore"):
        breadth_up = sums["up_sum"] / count_arr
        breadth_above = sums["above_sum"] / count_arr
        ret_mean = sums["ret_sum"] / count_arr
        csd = np.sqrt(np.maximum(sums["ret_sumsq"] / count_arr - ret_mean**2, 0.0))
    table = pd.DataFrame(
        {
            "ts": index,
            "universe_count": count_arr,
            "breadth_up": breadth_up,
            "breadth_above_slow": breadth_above,
            "univ_ret_24h_mean": ret_mean,
            "csd_24h": csd,
        }
    )
    table = table.merge(btc_state, on="ts", how="left")
    table = table.set_index("ts")

    daily_vol = pd.concat(daily_atr, ignore_index=True)
    daily_vol["day"] = pd.DatetimeIndex(daily_vol["day"])
    # as-of: rank yesterday's closing atr_frac, applied to today's events
    daily_vol["vol_rank_pct"] = daily_vol.groupby("day")["atr_frac"].rank(pct=True)
    daily_vol["apply_day"] = daily_vol["day"] + pd.Timedelta(days=1)
    daily_vol_rank = daily_vol[["sym_key", "apply_day", "vol_rank_pct"]].rename(
        columns={"apply_day": "day"}
    )
    return MarketState(table=table, daily_vol_rank=daily_vol_rank)
