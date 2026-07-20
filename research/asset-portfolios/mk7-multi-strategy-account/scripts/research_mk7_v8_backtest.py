"""Independent mk7-v8 backtest against the external frozen spec.

Assumptions / documented deviations:
- Binance USDM single venue for CVD/flow (user-confirmed).
- top_lsr_pos only available from public API ~2026-06-13; earlier points fail-open
  per spec §3.2 (series is non-empty, so not a hard-fail).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY = ROOT / "research/asset-portfolios/mk7-multi-strategy-account"
CACHE = ROOT / "data/cache/mk7_v8_binance"
ART = FAMILY / "artifacts"
NOTES = FAMILY / "notes"
DATE_TAG = "2026-07-13"

FULL_START = pd.Timestamp("2024-08-17T06:00:00Z")
FULL_END = pd.Timestamp("2026-07-02T03:00:00Z")
MAIN_START = pd.Timestamp("2025-05-30T00:00:00Z")
MAIN_END = pd.Timestamp("2026-07-01T00:00:00Z")
HYPE_AR_START = pd.Timestamp("2025-07-14T10:00:00Z")
K2FQ_EXEC_AFTER = pd.Timestamp("2025-05-30T00:00:00Z")

TARGET_RAW = {"TRX": 44, "SOL": 79, "HYPE": 74, "ETH": 89, "BTC": 54, "BNB": 62}
TARGET_K2FQ_RAW = 68
TARGET_MII_RAW = 375
TARGET_SELECTED_FULL = 743
TARGET_SELECTED_MAIN = 601
RECENT_WINDOWS: tuple[tuple[str, pd.Timedelta | pd.DateOffset], ...] = (
    ("1d", pd.Timedelta(days=1)),
    ("7d", pd.Timedelta(days=7)),
    ("1m", pd.DateOffset(months=1)),
    ("3m", pd.DateOffset(months=3)),
    ("6m", pd.DateOffset(months=6)),
    ("1y", pd.DateOffset(years=1)),
)


def load_engine() -> Any:
    path = ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v1/engine.py"
    spec = importlib.util.spec_from_file_location("mk7_ar_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load engine: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ENGINE = load_engine()


@dataclass(slots=True)
class Cand:
    family: str
    asset: str
    leg: str
    side: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_price: float
    exit_price: float
    exposure_native: float
    stop_pct: float
    net_ret_1x: float
    funding_ret_1x: float
    entry_fee: float
    funding_scale: float
    component: str  # six / k2fq / mii


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def enrich_1h(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"].astype("float64")
    high = out["high"].astype("float64")
    low = out["low"].astype("float64")
    rh = high.rolling(24, min_periods=24).max()
    rl = low.rolling(24, min_periods=24).min()
    k = 100.0 * (close - rl) / (rh - rl).replace(0.0, np.nan)
    out["stoch_k24"] = k
    out["stoch_d24"] = k.rolling(3, min_periods=3).mean()
    line = close.ewm(span=8, adjust=False, min_periods=8).mean() - close.ewm(
        span=55, adjust=False, min_periods=55
    ).mean()
    signal = line.ewm(span=5, adjust=False, min_periods=5).mean()
    out["macd_hist_8_55_5"] = line - signal
    tc = out["trade_count"].astype("float64")
    out["trade_rvol48"] = tc / tc.rolling(48, min_periods=48).mean().replace(0.0, np.nan)
    return out


DEFAULTS = dict(
    side_mode="both",
    indicator_window=20,
    ema_fast=55,
    ema_slow=144,
    ema_htf=55,
    threshold_low=25.0,
    threshold_high=75.0,
    band_k=0.5,
    pullback_atr=0.0,
    roc_window=24,
    roc_threshold_bps=0.0,
    macd_fast=12,
    macd_slow=26,
    macd_signal=9,
    min_adx=0.0,
    max_adx=100.0,
    min_rvol=0.0,
    min_atr_bps=0.0,
    max_atr_bps=10000.0,
    min_dir_roc_bps=-10000.0,
    max_dist_ema_bps=100000.0,
    htf_mode="none",
    require_macd_turn=False,
    require_body_dir=False,
    max_aligned_funding_bps=10000.0,
    exit_kind="fixed",
    tp_atr=1.0,
    sl_atr=5.0,
    trail_activation_atr=1.0,
    trail_atr=1.0,
    max_hold_bars=100000,
    cooldown_bars=0,
    entry_delay_bars=1,
    sizing_kind="fixed",
    fixed_leverage=1.0,
    risk_fraction=0.01,
    max_leverage=100.0,
)

LEGS: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    "TRX": [
        (
            "macd",
            "macd_flip",
            dict(
                ema_htf=89,
                roc_window=6,
                macd_fast=34,
                macd_slow=89,
                macd_signal=13,
                min_adx=20.0,
                max_adx=24.0,
                min_rvol=0.75,
                max_atr_bps=150.0,
                min_dir_roc_bps=100.0,
                max_dist_ema_bps=10000.0,
                htf_mode="h12",
                tp_atr=2.0,
                sl_atr=5.0,
                max_hold_bars=120,
                cooldown_bars=3,
                fixed_leverage=12.5,
            ),
        ),
        (
            "stoch",
            "stoch_reversal",
            dict(
                side_mode="long",
                ema_htf=233,
                indicator_window=24,
                threshold_low=20.0,
                threshold_high=75.0,
                roc_window=3,
                max_adx=24.0,
                min_rvol=1.0,
                min_dir_roc_bps=-500.0,
                require_body_dir=True,
                exit_kind="trailing",
                sl_atr=6.0,
                trail_activation_atr=3.0,
                trail_atr=2.0,
                max_hold_bars=120,
                cooldown_bars=6,
                entry_delay_bars=2,
                fixed_leverage=8.75,
            ),
        ),
    ],
    "SOL": [
        (
            "donchian",
            "donchian_break",
            dict(
                side_mode="short",
                ema_fast=144,
                ema_slow=233,
                ema_htf=377,
                indicator_window=12,
                roc_window=24,
                min_adx=36.0,
                min_rvol=0.5,
                min_atr_bps=100.0,
                min_dir_roc_bps=0.0,
                max_dist_ema_bps=750.0,
                max_aligned_funding_bps=4.0,
                tp_atr=0.75,
                sl_atr=4.0,
                max_hold_bars=120,
                fixed_leverage=6.0,
            ),
        ),
        (
            "vwap",
            "vwap_revert",
            dict(
                side_mode="short",
                ema_fast=34,
                ema_slow=55,
                ema_htf=89,
                indicator_window=48,
                band_k=1.25,
                roc_window=72,
                max_adx=60.0,
                min_rvol=0.75,
                min_atr_bps=125.0,
                max_dist_ema_bps=1000.0,
                htf_mode="h12",
                max_aligned_funding_bps=1.0,
                tp_atr=0.75,
                sl_atr=3.0,
                max_hold_bars=18,
                cooldown_bars=3,
                fixed_leverage=1.5,
            ),
        ),
    ],
    "HYPE": [
        (
            "di",
            "di_cross",
            dict(
                ema_fast=8,
                ema_slow=55,
                ema_htf=89,
                min_adx=10.0,
                min_rvol=2.0,
                max_atr_bps=250.0,
                htf_mode="h12",
                tp_atr=1.5,
                sl_atr=4.5,
                max_hold_bars=18,
                fixed_leverage=3.0,
            ),
        ),
        (
            "stoch",
            "stoch_reversal",
            dict(
                ema_fast=8,
                ema_slow=55,
                ema_htf=55,
                indicator_window=21,
                threshold_low=25.0,
                threshold_high=55.0,
                roc_window=12,
                macd_fast=8,
                macd_slow=55,
                macd_signal=5,
                min_rvol=1.0,
                min_atr_bps=200.0,
                max_atr_bps=500.0,
                require_macd_turn=True,
                exit_kind="trailing",
                sl_atr=4.0,
                trail_activation_atr=1.0,
                trail_atr=1.0,
                max_hold_bars=8,
                cooldown_bars=36,
                fixed_leverage=2.0,
            ),
        ),
    ],
    "ETH": [
        (
            "bb",
            "bb_break",
            dict(
                ema_htf=55,
                indicator_window=72,
                band_k=2.5,
                roc_window=24,
                min_adx=16.0,
                min_rvol=3.5,
                min_atr_bps=75.0,
                min_dir_roc_bps=100.0,
                max_dist_ema_bps=750.0,
                max_aligned_funding_bps=8.0,
                tp_atr=2.5,
                sl_atr=5.0,
                max_hold_bars=60,
                fixed_leverage=1.5,
            ),
        ),
        (
            "rsi",
            "rsi_reversal",
            dict(
                side_mode="short",
                ema_htf=233,
                indicator_window=7,
                threshold_low=5.0,
                threshold_high=75.0,
                roc_window=6,
                min_adx=15.0,
                max_adx=55.0,
                min_atr_bps=125.0,
                min_dir_roc_bps=-300.0,
                max_dist_ema_bps=750.0,
                tp_atr=2.5,
                sl_atr=3.0,
                max_hold_bars=36,
                cooldown_bars=24,
                fixed_leverage=2.5,
            ),
        ),
    ],
    "BTC": [
        (
            "keltner",
            "keltner_break",
            dict(
                side_mode="short",
                ema_fast=55,
                ema_slow=144,
                ema_htf=55,
                indicator_window=20,
                band_k=2.0,
                min_adx=40.0,
                min_rvol=0.75,
                htf_mode="h4",
                tp_atr=1.5,
                sl_atr=5.0,
                fixed_leverage=4.8,
            ),
        ),
        (
            "cci",
            "cci_reversal",
            dict(
                side_mode="long",
                ema_fast=89,
                ema_slow=233,
                ema_htf=377,
                indicator_window=20,
                threshold_high=125.0,
                max_adx=30.0,
                min_rvol=1.25,
                min_atr_bps=75.0,
                max_dist_ema_bps=750.0,
                tp_atr=5.5,
                sl_atr=1.5,
                max_hold_bars=72,
                fixed_leverage=3.5,
            ),
        ),
    ],
    "BNB": [
        (
            "ema_pullback",
            "ema_pullback",
            dict(
                ema_fast=89,
                ema_slow=144,
                ema_htf=377,
                pullback_atr=0.25,
                roc_window=12,
                max_adx=40.0,
                min_rvol=1.25,
                min_atr_bps=75.0,
                min_dir_roc_bps=-300.0,
                max_dist_ema_bps=300.0,
                exit_kind="trailing",
                sl_atr=5.0,
                trail_activation_atr=2.0,
                trail_atr=1.5,
                max_hold_bars=240,
                cooldown_bars=12,
                fixed_leverage=3.75,
            ),
        ),
        (
            "wick",
            "wick_reject",
            dict(
                ema_fast=21,
                ema_slow=144,
                ema_htf=55,
                threshold_low=0.4,
                threshold_high=0.75,
                band_k=0.5,
                min_adx=28.0,
                min_rvol=2.0,
                htf_mode="h12",
                tp_atr=1.0,
                sl_atr=5.0,
                max_hold_bars=48,
                cooldown_bars=24,
                fixed_leverage=3.5,
            ),
        ),
    ],
}

PRIORITY = {
    "TRX": {"macd": 2.0, "stoch": 1.0},
    "SOL": {"donchian": 2.0, "vwap": 1.0},
    "HYPE": {"di": 1.0, "stoch": 0.0},
    "ETH": {"bb": 2.0, "rsi": 1.0},
    "BTC": {"keltner": 2.0, "cci": 1.0},
    "BNB": {"ema_pullback": 2.445774012147314, "wick": 1.6307399812929821},
}

ARTIFACT_1H = {
    "TRX": ROOT
    / "research/trx/1h-adaptive-regime/artifacts/trx_binance_1h_closed_klines_2y.parquet",
    "SOL": ROOT
    / "research/sol/1h-adaptive-regime/artifacts/sol_binance_1h_closed_klines_2y.parquet",
    "HYPE": ROOT
    / "research/hype/1h-adaptive-regime/artifacts/hype_binance_1h_closed_klines.parquet",
    "ETH": ROOT
    / "research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_closed_klines_2y.parquet",
    "BTC": ROOT
    / "research/btc/1h-adaptive-regime/artifacts/btc_binance_1h_closed_klines_2y.parquet",
    "BNB": ROOT
    / "research/bnb/1h-adaptive-regime/artifacts/bnb_binance_1h_closed_klines_2y.parquet",
}


def load_1h(asset: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    raw = pd.read_parquet(ARTIFACT_1H[asset])
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    funding = pd.read_parquet(
        ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp"
        / f"symbol={asset.lower()}_usdt_usdt/funding.parquet"
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    frame = enrich_1h(ENGINE.add_features(raw, funding))
    ft, fc = ENGINE.funding_prefix(funding)
    return frame, ft, fc


def six_coin_candidates() -> tuple[list[Cand], dict[str, int], dict[str, pd.DataFrame]]:
    cands: list[Cand] = []
    counts: dict[str, int] = {}
    frames: dict[str, pd.DataFrame] = {}
    for asset, legs in LEGS.items():
        frame, ft, fc = load_1h(asset)
        frames[asset] = frame
        per_leg: list[list[Any]] = []
        for leg, style, ov in legs:
            cfg_dict = DEFAULTS | ov | {"name": f"{asset}_{leg}", "style": style}
            cfg_dict["max_leverage"] = float(cfg_dict["fixed_leverage"])
            cfg = ENGINE.StrategyConfig(**cfg_dict)
            sig = ENGINE.build_signal(frame, cfg)
            if asset == "BNB" and leg == "wick":
                tr = frame["trade_rvol48"].to_numpy("float64")
                keep = np.isfinite(tr) & (tr >= 2.25)
                sig = np.where(keep, sig, 0).astype(np.int8)
            n = len(frame)
            sig2 = sig.copy()
            for i in np.flatnonzero(sig):
                entry_i = int(i + cfg.entry_delay_bars)
                if entry_i >= n:
                    sig2[i] = 0
                    continue
                ets = frame["ts"].iloc[entry_i]
                cut = max(FULL_START, HYPE_AR_START) if asset == "HYPE" else FULL_START
                if not (cut <= ets < FULL_END):
                    sig2[i] = 0
            trades = ENGINE.simulate_trades(frame, sig2, cfg, ft, fc)
            per_leg.append(trades)
        merged = ENGINE.merge_trade_sets(
            per_leg[0],
            per_leg[1],
            PRIORITY[asset][legs[0][0]],
            PRIORITY[asset][legs[1][0]],
        )
        counts[asset] = len(merged)
        ov_by_leg = {leg: ov for leg, _style, ov in legs}
        for trade in merged:
            leg_name = trade.config.split("_", 1)[-1]
            ov = ov_by_leg[leg_name]
            stop_pct = (float(trade.signal_atr_bps) / 10000.0) * float(
                ov.get("sl_atr", DEFAULTS["sl_atr"])
            )
            cands.append(
                Cand(
                    family=asset,
                    asset=asset,
                    leg=leg_name,
                    side=int(trade.side),
                    entry_ts=pd.Timestamp(trade.entry_ts),
                    exit_ts=pd.Timestamp(trade.exit_ts),
                    entry_price=float(trade.entry_price),
                    exit_price=float(trade.exit_price),
                    exposure_native=float(trade.exposure),
                    stop_pct=float(stop_pct),
                    net_ret_1x=float(trade.net_ret_1x),
                    funding_ret_1x=float(trade.funding_ret_1x),
                    entry_fee=0.001,
                    funding_scale=1.0,
                    component="six",
                )
            )
        print(f"[six] {asset} merged={counts[asset]} target={TARGET_RAW[asset]}", flush=True)
    return cands, counts, frames


def last_value_strictly_before(series: pd.Series, ts: pd.Timestamp) -> float:
    """Last observation with index < ts; NaN if none (fail-open caller)."""
    idx = series.index
    pos = int(idx.searchsorted(pd.Timestamp(ts), side="left")) - 1
    if pos < 0:
        return float("nan")
    return float(series.iloc[pos])


def last_value_at_or_before(series: pd.Series, ts: pd.Timestamp) -> float:
    """Last observation with index <= ts; NaN if none (fail-open caller)."""
    idx = series.index
    pos = int(idx.searchsorted(pd.Timestamp(ts), side="right")) - 1
    if pos < 0:
        return float("nan")
    return float(series.iloc[pos])


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def rma(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev).abs(),
            (frame["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)


def aggregate_from_15m(src: pd.DataFrame, rule: str, expected: int) -> pd.DataFrame:
    s = src.sort_values("ts").set_index("ts")
    g = s.resample(rule, label="left", closed="left")
    out = g.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        trade_count=("trade_count", "sum"),
        minute_count=("open", "count"),
    )
    return out.loc[out["minute_count"].eq(expected)].dropna(subset=["open", "high", "low", "close"])


def k2fq_candidates(funding: pd.DataFrame) -> list[Cand]:
    h15 = pd.read_parquet(CACHE / "klines/hypeusdt_15m_with_taker.parquet")
    h15["ts"] = pd.to_datetime(h15["ts"], utc=True)
    prem = pd.read_parquet(CACHE / "premium/hype_usdt_premium_index_15m.parquet")
    prem["ts"] = pd.to_datetime(prem["ts"], utc=True)
    lsr = pd.read_parquet(CACHE / "top_lsr/hype_usdt_top_lsr_pos_5m.parquet")
    lsr["ts"] = pd.to_datetime(lsr["ts"], utc=True)

    b30 = aggregate_from_15m(h15, "30min", 2)
    h1 = aggregate_from_15m(h15, "60min", 4)
    tr = true_range(b30)
    mid = ema(b30["close"], 10)
    atr10 = rma(tr, 10)
    upper = mid + 2.05 * atr10
    lower = mid - 2.05 * atr10
    atr96 = rma(tr, 96)
    h1 = h1.copy()
    h1["ema16"] = ema(h1["close"], 16)
    h1["ema48"] = ema(h1["close"], 48)
    h1["trend"] = np.sign(h1["ema16"] - h1["ema48"])

    # map closed 1h trend onto 30m open (only already-closed 1h)
    h1_close_ts = h1.index + pd.Timedelta(hours=1)
    b30_open = b30.index.to_numpy()
    mapped = np.searchsorted(h1_close_ts.to_numpy(), b30_open, side="right") - 1
    trend = np.full(len(b30), np.nan)
    valid = mapped >= 0
    trend_vals = h1["trend"].to_numpy("float64")
    trend[valid] = trend_vals[mapped[valid]]

    prev_close = b30["close"].shift(1)
    prev_upper = upper.shift(1)
    prev_lower = lower.shift(1)
    was_inside = (prev_close >= prev_lower) & (prev_close <= prev_upper)
    long_raw = was_inside & (b30["close"] > upper)
    short_raw = was_inside & (b30["close"] < lower)

    prem_s = (
        prem.set_index("ts")["close"]
        .astype("float64")
        .sort_index()
    )
    prem_s.index = pd.to_datetime(prem_s.index, utc=True)
    lsr_s = (
        lsr.set_index("ts")["top_lsr_pos"]
        .astype("float64")
        .sort_index()
    )
    lsr_s.index = pd.to_datetime(lsr_s.index, utc=True)

    funding = funding.sort_values("ts")
    f_times = pd.to_datetime(funding["ts"], utc=True).astype("int64").to_numpy()
    f_rates = funding["funding_rate"].to_numpy("float64")
    f_cum = np.r_[0.0, np.cumsum(f_rates)]

    cands: list[Cand] = []
    blocked_until = pd.Timestamp.min.tz_localize("UTC")
    idx = list(b30.index)
    for i, ts in enumerate(idx):
        side = 0
        if bool(long_raw.iloc[i]) and trend[i] > 0:
            side = 1
        elif bool(short_raw.iloc[i]) and trend[i] < 0:
            side = -1
        if side == 0:
            continue
        entry_ts = ts + pd.Timedelta(minutes=30)
        if not (entry_ts > K2FQ_EXEC_AFTER and entry_ts < FULL_END):
            continue
        if entry_ts <= blocked_until:
            continue
        # premium at signal bar open: last value strictly before open
        prem_val = last_value_strictly_before(prem_s, ts)
        if np.isfinite(prem_val) and prem_val * side > 0.001:
            continue
        # top_lsr query point is signal-bar end; "取此前最后值" is strict-before.
        # Isolated missing points remain fail-open through the prior observation.
        bar_end = ts + pd.Timedelta(minutes=30)
        lsr_val = last_value_strictly_before(lsr_s, bar_end)
        if side < 0 and np.isfinite(lsr_val) and lsr_val > 1.5:
            continue

        entry_price = float(b30["close"].iloc[i])
        atr = float(atr96.iloc[i])
        if not np.isfinite(atr) or atr <= 0 or entry_price <= 0:
            continue
        atr_pct = atr / entry_price
        native = float(np.clip(0.0224 / atr_pct, 1.6, 4.0))
        tp = entry_price * (1 + side * 0.05)
        sl = entry_price * (1 - side * 0.025)

        # walk 15m sub-bars from entry bar onward, max 30 * 30m = 60 * 15m
        sub = h15.loc[(h15["ts"] >= entry_ts) & (h15["ts"] < entry_ts + pd.Timedelta(minutes=30 * 30))]
        if sub.empty:
            continue
        exit_ts = None
        exit_price = None
        reason = "timeout"
        hold_30 = 0
        last_30_close_ts = entry_ts
        for _, row in sub.iterrows():
            # count completed 30m bars by open alignment
            if int((row["ts"] - entry_ts).total_seconds()) % 1800 == 0 and row["ts"] > entry_ts:
                hold_30 = int((row["ts"] - entry_ts) / pd.Timedelta(minutes=30))
            hi = float(row["high"])
            lo = float(row["low"])
            cl = float(row["close"])
            last_30_close_ts = row["ts"] + pd.Timedelta(minutes=15)
            if side > 0:
                if lo <= sl:
                    exit_ts = row["ts"] + pd.Timedelta(minutes=15)
                    exit_price = sl * (1 - side * 0.001)  # SL +10bp adverse already via side
                    # Spec: SL fill adds 10bp adverse slippage; entry fill is close (no slip stated beyond cost)
                    exit_price = sl * (1 - 0.001) if side > 0 else sl * (1 + 0.001)
                    reason = "sl"
                    break
                if hi >= tp:
                    exit_ts = row["ts"] + pd.Timedelta(minutes=15)
                    exit_price = tp
                    reason = "tp"
                    break
            else:
                if hi >= sl:
                    exit_ts = row["ts"] + pd.Timedelta(minutes=15)
                    exit_price = sl * (1 + 0.001)
                    reason = "sl"
                    break
                if lo <= tp:
                    exit_ts = row["ts"] + pd.Timedelta(minutes=15)
                    exit_price = tp
                    reason = "tp"
                    break
            if hold_30 >= 30:
                exit_ts = last_30_close_ts
                exit_price = cl
                reason = "timeout"
                break
        if exit_ts is None:
            exit_ts = pd.Timestamp(sub["ts"].iloc[-1]) + pd.Timedelta(minutes=15)
            exit_price = float(sub["close"].iloc[-1])
            reason = "timeout"

        # costs: 6bp/side on fills; entry at close, exit as above
        # net_ret_1x = side*(exit/entry-1) - fee + funding; fee approx 6bp each side on notional
        fee = 0.0006 * (1.0 + float(exit_price) / entry_price)
        # funding (entry, exit]
        left = int(np.searchsorted(f_times, int(entry_ts.value), side="right"))
        right = int(np.searchsorted(f_times, int(exit_ts.value), side="right"))
        funding_ret = float(-side * (f_cum[right] - f_cum[left]))
        net = side * (float(exit_price) / entry_price - 1.0) - fee + funding_ret
        cands.append(
            Cand(
                family="K2FQ",
                asset="HYPE",
                leg="k2fq",
                side=side,
                entry_ts=entry_ts,
                exit_ts=pd.Timestamp(exit_ts),
                entry_price=entry_price,
                exit_price=float(exit_price),
                exposure_native=native,
                stop_pct=0.025,
                net_ret_1x=float(net),
                funding_ret_1x=float(funding_ret),
                entry_fee=0.0006,
                funding_scale=1.0,
                component="k2fq",
            )
        )
        blocked_until = pd.Timestamp(exit_ts)
        _ = reason
    print(f"[k2fq] raw={len(cands)} target={TARGET_K2FQ_RAW}", flush=True)
    return cands


def wilder_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def mii_candidates() -> list[Cand]:
    h15 = pd.read_parquet(CACHE / "klines/hypeusdt_15m_with_taker.parquet")
    h15["ts"] = pd.to_datetime(h15["ts"], utc=True)
    h1m = pd.read_parquet(CACHE / "klines/hypeusdt_1m_with_taker.parquet")
    h1m["ts"] = pd.to_datetime(h1m["ts"], utc=True)
    btc = pd.read_parquet(CACHE / "klines/btcusdt_15m_with_taker.parquet")
    btc["ts"] = pd.to_datetime(btc["ts"], utc=True)
    flow = pd.read_parquet(CACHE / "features/hype_usdt_15m_cvd_flow_single_venue.parquet")
    flow["ts"] = pd.to_datetime(flow["ts"], utc=True)

    f = h15.sort_values("ts").reset_index(drop=True)
    close = f["close"].astype("float64")
    high = f["high"].astype("float64")
    low = f["low"].astype("float64")
    open_ = f["open"].astype("float64")
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    atr96 = tr.rolling(96, min_periods=96).mean()
    atr_pct = atr96 / close
    rsi7 = wilder_rsi(close, 7)
    macd_line = close.ewm(span=12, adjust=False, min_periods=12).mean() - close.ewm(
        span=26, adjust=False, min_periods=26
    ).mean()
    macd_hist = macd_line - macd_line.ewm(span=9, adjust=False, min_periods=9).mean()
    # ER96
    abs_move = (close - close.shift(96)).abs()
    path = close.diff().abs().rolling(96, min_periods=96).sum()
    er96 = abs_move / path.replace(0.0, np.nan)

    flow = flow.set_index("ts").sort_index()
    mid_imb = flow["mid_imb"].reindex(f["ts"]).to_numpy("float64")
    big_imb = flow["big_imb"].reindex(f["ts"]).to_numpy("float64")
    net = flow["net_flow"].reindex(f["ts"]).fillna(0.0)
    tot = flow["total_flow"].reindex(f["ts"]).fillna(0.0)
    flow_ratio = (
        net.rolling(96, min_periods=96).sum()
        / tot.rolling(96, min_periods=96).sum().replace(0.0, np.nan)
    ).to_numpy("float64")

    btc = btc.set_index("ts").sort_index()
    btc_close = btc["close"].reindex(f["ts"]).ffill()
    # tide at bar j = log(btc[j]/btc[j-96]); advisors read entry_i-1 = signal_i
    tide = np.log(btc_close / btc_close.shift(96)).to_numpy("float64")

    h1m = h1m.set_index("ts").sort_index()

    signals: list[tuple[int, int]] = []
    for i in range(1, len(f) - 2):
        side = 0
        if (
            rsi7.iloc[i - 1] <= 40
            and rsi7.iloc[i] > 40
            and macd_hist.iloc[i] >= 0
        ):
            side = 1
        elif (
            rsi7.iloc[i - 1] >= 60
            and rsi7.iloc[i] < 60
            and macd_hist.iloc[i] <= 0
        ):
            side = -1
        if side == 0:
            continue
        ap = float(atr_pct.iloc[i])
        if not np.isfinite(ap):
            continue
        if ap < 0.0060 or ap > 0.0280:
            continue
        if 0.0060 <= ap < 0.0075:
            er = float(er96.iloc[i])
            if np.isfinite(er) and er < 0.20:
                continue
            # ER missing => fail-open
        # RVOL off
        signals.append((i, side))

    mid_buy_a = flow["mid_buy"].reindex(f["ts"]).fillna(0.0).to_numpy("float64")
    mid_sell_a = flow["mid_sell"].reindex(f["ts"]).fillna(0.0).to_numpy("float64")
    big_buy_a = flow["big_buy"].reindex(f["ts"]).fillna(0.0).to_numpy("float64")
    big_sell_a = flow["big_sell"].reindex(f["ts"]).fillna(0.0).to_numpy("float64")

    trades: list[Cand] = []
    blocked_until = -1
    for signal_i, side in signals:
        entry_i = signal_i + 1
        if entry_i <= blocked_until or entry_i >= len(f) - 1:
            continue
        entry_ts = pd.Timestamp(f["ts"].iloc[entry_i])
        if not (MAIN_START <= entry_ts < FULL_END):
            # MII only meaningful after HYPE 15m start; keep full curve filter
            if entry_ts < FULL_START or entry_ts >= FULL_END:
                continue
        # CVD short mid gate: last-10-bar aggregate mid imbalance; missing fail-open
        lo = max(0, signal_i - 9)
        hi = signal_i + 1
        mid_den = float(mid_buy_a[lo:hi].sum() + mid_sell_a[lo:hi].sum())
        if side < 0 and mid_den > 0:
            mid_agg = float(mid_buy_a[lo:hi].sum() - mid_sell_a[lo:hi].sum()) / mid_den
            if mid_agg > 0.02:
                continue

        ap = float(atr_pct.iloc[signal_i])
        sl_distance = 5.0 * ap
        native = min(2.5, 0.175 / max(sl_distance, 1e-12))
        # big credit from 10-bar aggregate big imbalance
        big_den = float(big_buy_a[lo:hi].sum() + big_sell_a[lo:hi].sum())
        if big_den > 0:
            big_agg = float(big_buy_a[lo:hi].sum() - big_sell_a[lo:hi].sum()) / big_den
            if big_agg >= 0:
                native *= 1.3
        # 1m blowoff short only
        if side < 0:
            end_1m = entry_ts
            start_1m = entry_ts - pd.Timedelta(minutes=150)
            win = h1m.loc[(h1m.index >= start_1m) & (h1m.index < end_1m)]
            if len(win) >= int(0.8 * 150):
                peak_i = win["volume"].idxmax()
                row = win.loc[peak_i]
                rng = float(row["high"] - row["low"])
                upper_wick = float(row["high"] - max(row["open"], row["close"]))
                med = float(win["volume"].median())
                if rng > 0 and upper_wick / rng >= 0.20 and (med == 0 or float(row["volume"]) / med >= 0):
                    # risk-capped 1.3
                    if native * sl_distance <= 0.175 + 1e-12:
                        native = min(native * 1.3, 0.175 / max(sl_distance, 1e-12))
                    else:
                        native *= 1.3  # already over budget: do not cut
        # advisors on entry bar i-1 (= signal bar)
        votes_against = 0
        alloc = native
        fr = flow_ratio[signal_i] if signal_i >= 0 else np.nan
        if np.isfinite(fr):
            if side < 0 and fr > 0.0:
                alloc *= 0.8
                votes_against += 1
            elif side > 0 and fr < -0.01:
                alloc *= 0.8
                votes_against += 1
        td = tide[signal_i] if signal_i >= 0 else np.nan
        if np.isfinite(td):
            if side < 0 and td > 0:
                alloc *= 0.75
                votes_against += 1
            elif side > 0 and td < 0:
                alloc *= 0.75
                votes_against += 1
        if votes_against == 0:
            # unanimous 1.25 with risk cap
            if alloc * sl_distance <= 0.175 + 1e-12:
                alloc = min(alloc * 1.25, 0.175 / max(sl_distance, 1e-12))
            else:
                alloc *= 1.25

        entry_price = float(open_.iloc[entry_i])  # next bar open; costs in net
        # apply round-trip 28bp as 14bp/side in net later
        tp_pct = 1.25 * ap
        sl_pct = 5.0 * ap
        tp = entry_price * (1 + side * tp_pct)
        sl = entry_price * (1 - side * sl_pct)
        max_i = min(len(f) - 1, entry_i + 96)
        giveup_arm_i = entry_i + 72
        exit_i = max_i
        exit_price = float(open_.iloc[max_i])
        reason = "timeout_open"
        for bar_i in range(entry_i, max_i + 1):
            o = float(open_.iloc[bar_i])
            h = float(high.iloc[bar_i])
            l = float(low.iloc[bar_i])
            if bar_i == max_i:
                exit_i = bar_i
                exit_price = o
                reason = "timeout_open"
                break
            # gap opens
            if side > 0:
                if o <= sl:
                    exit_i, exit_price, reason = bar_i, o, "sl_gap"
                    break
                if o >= tp:
                    exit_i, exit_price, reason = bar_i, tp, "tp_gap"
                    break
            else:
                if o >= sl:
                    exit_i, exit_price, reason = bar_i, o, "sl_gap"
                    break
                if o <= tp:
                    exit_i, exit_price, reason = bar_i, tp, "tp_gap"
                    break
            # intrabar: SL, giveup, TP
            stop_hit = (l <= sl) if side > 0 else (h >= sl)
            tp_hit = (h >= tp) if side > 0 else (l <= tp)
            if stop_hit:
                exit_i, exit_price, reason = bar_i, sl, "sl"
                break
            if bar_i >= giveup_arm_i:
                # giveup when loss recovers to <=1.75%
                mark = o
                loss = side * (mark / entry_price - 1.0)
                if loss >= -0.0175:
                    exit_i, exit_price, reason = bar_i, mark, "giveup"
                    break
            if tp_hit:
                exit_i, exit_price, reason = bar_i, tp, "tp"
                break

        # 14bp/side costs
        fee = 0.0014 * (1.0 + float(exit_price) / entry_price)
        net = side * (float(exit_price) / entry_price - 1.0) - fee
        trades.append(
            Cand(
                family="MII",
                asset="HYPE",
                leg="mii",
                side=side,
                entry_ts=entry_ts,
                exit_ts=pd.Timestamp(f["ts"].iloc[exit_i]),
                entry_price=entry_price,
                exit_price=float(exit_price),
                exposure_native=float(alloc),
                stop_pct=float(sl_pct),
                net_ret_1x=float(net),
                funding_ret_1x=0.0,
                entry_fee=0.0014,
                funding_scale=0.0,
                component="mii",
            )
        )
        blocked_until = exit_i
        _ = reason
    print(f"[mii] filtered={len(trades)} target={TARGET_MII_RAW}", flush=True)
    return trades


def causal_score(family: str, now: pd.Timestamp, history: list[Cand]) -> float:
    prior = [t for t in history if t.family == family and t.exit_ts < now]
    if len(prior) < 8:
        return 0.0
    r = np.array([t.net_ret_1x for t in prior[-40:]], dtype="float64")
    w = np.exp(np.linspace(-2.0, 0.0, len(r)))
    mean = float(np.average(r, weights=w))
    downside = float(np.sqrt(np.average(np.minimum(r, 0.0) ** 2, weights=w)))
    return mean / max(downside, 0.002)


def scale_exposure(c: Cand) -> float:
    if c.component == "six":
        scaled = c.exposure_native * 1.5
        return float(min(scaled, 0.175 * 2.0 / max(c.stop_pct, 1e-12)))
    if c.component == "k2fq":
        return float(c.exposure_native * 1.2)
    return float(c.exposure_native * 1.3)


def select_dual_slot(cands: list[Cand]) -> list[tuple[Cand, float]]:
    ordered = sorted(cands, key=lambda t: (t.entry_ts, t.exit_ts, t.family))
    by_ts: dict[pd.Timestamp, list[Cand]] = {}
    for c in ordered:
        by_ts.setdefault(c.entry_ts, []).append(c)
    active: list[tuple[Cand, float]] = []
    selected: list[tuple[Cand, float]] = []
    history: list[Cand] = []
    for t in sorted(by_ts):
        # release exits at t
        still = []
        for c, exp in active:
            if c.exit_ts > t:
                still.append((c, exp))
            else:
                history.append(c)
        active = still
        free = 2 - len(active)
        if free <= 0:
            continue
        active_assets = {c.asset for c, _ in active}
        choices = [c for c in by_ts[t] if c.asset not in active_assets]
        ranked = []
        for c in choices:
            score = causal_score(c.family, t, history + [a for a, _ in active])
            if c.component == "k2fq":
                score += 1000.0
            ranked.append(((-score, c.stop_pct, c.family), c))
        ranked.sort(key=lambda x: x[0])
        seen_asset = set()
        for _key, c in ranked:
            if free <= 0:
                break
            if c.asset in seen_asset or c.asset in active_assets:
                continue
            exp = scale_exposure(c)
            selected.append((c, exp))
            active.append((c, exp))
            active_assets.add(c.asset)
            seen_asset.add(c.asset)
            free -= 1
    return selected


def load_account_funding() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for asset in ("TRX", "SOL", "HYPE", "ETH", "BTC", "BNB"):
        frame = pd.read_parquet(
            ROOT
            / "data/normalized/funding/exchange=binance/market_type=perp"
            / f"symbol={asset.lower()}_usdt_usdt/funding.parquet"
        )
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame = frame.drop_duplicates("ts", keep="last").sort_values("ts")
        times = frame["ts"].astype("int64").to_numpy()
        cumulative = np.r_[0.0, np.cumsum(frame["funding_rate"].to_numpy("float64"))]
        out[asset] = (times, cumulative)
    return out


def build_mark_series(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """Closed-bar marks indexed by availability time."""
    marks: dict[str, pd.Series] = {}
    h15 = pd.read_parquet(CACHE / "klines/hypeusdt_15m_with_taker.parquet")
    h15["ts"] = pd.to_datetime(h15["ts"], utc=True)
    marks["HYPE"] = pd.Series(
        h15["close"].to_numpy("float64"),
        index=pd.DatetimeIndex(h15["ts"] + pd.Timedelta(minutes=15)),
    ).sort_index()
    for asset, frame in frames.items():
        if asset == "HYPE":
            continue
        marks[asset] = pd.Series(
            frame["close"].to_numpy("float64"),
            index=pd.DatetimeIndex(frame["ts"] + pd.Timedelta(hours=1)),
        ).sort_index()
    return marks


def build_full_equity_curve(
    selected: list[tuple[Cand, float]], frames: dict[str, pd.DataFrame]
) -> pd.Series:
    """15m MTM NAV; old exits first, same-ts entries share one marked base.

    Trades whose entry_ts equals exit_ts enter first and settle after all entries
    at that timestamp. This preserves the trade's intrabar entry-before-exit
    order while retaining the account-level old-exits-before-new-entries rule.
    """
    marks = build_mark_series(frames)
    funding = load_account_funding()
    entries: dict[pd.Timestamp, list[int]] = {}
    exits: dict[pd.Timestamp, list[int]] = {}
    for i, (c, _exp) in enumerate(selected):
        entries.setdefault(c.entry_ts, []).append(i)
        exits.setdefault(c.exit_ts, []).append(i)

    def mark_at(c: Cand, ts: pd.Timestamp) -> float:
        series = marks[c.asset]
        pos = int(series.index.searchsorted(ts, side="right")) - 1
        if pos < 0:
            raise RuntimeError(f"no closed mark for {c.asset} at {ts}")
        return float(series.iloc[pos])

    def accrued_funding(c: Cand, ts: pd.Timestamp) -> float:
        if c.funding_scale == 0.0:
            return 0.0
        times, cumulative = funding[c.asset]
        if c.component == "k2fq":
            left = int(np.searchsorted(times, c.entry_ts.value, side="right"))
            right = int(np.searchsorted(times, ts.value, side="right"))
        else:
            left = int(np.searchsorted(times, c.entry_ts.value, side="left"))
            right = int(np.searchsorted(times, ts.value, side="left"))
        return float(-c.side * (cumulative[right] - cumulative[left]))

    active: set[int] = set()
    bases: dict[int, float] = {}
    realized = 0.0
    points: list[tuple[pd.Timestamp, float]] = []

    def unrealized(i: int, ts: pd.Timestamp) -> float:
        c, exp = selected[i]
        one_x = (
            c.side * (mark_at(c, ts) / c.entry_price - 1.0)
            - c.entry_fee
            + accrued_funding(c, ts) * c.funding_scale
        )
        return float(bases[i] * 0.5 * exp * one_x)

    timeline = pd.date_range(FULL_START, FULL_END, freq="15min", inclusive="left")
    for ts in timeline:
        # Settle positions opened before ts. A same-ts intrabar trade has not
        # entered yet and is settled after the shared entry base is frozen.
        for i in exits.get(ts, []):
            if i not in active:
                continue
            c, exp = selected[i]
            realized += bases[i] * 0.5 * exp * c.net_ret_1x
            active.remove(i)
            bases.pop(i)

        nav_before_entries = 1.0 + realized + sum(unrealized(i, ts) for i in active)
        new_entries = entries.get(ts, [])
        for i in new_entries:
            bases[i] = float(nav_before_entries)
            active.add(i)

        for i in new_entries:
            c, exp = selected[i]
            if c.exit_ts != ts:
                continue
            realized += bases[i] * 0.5 * exp * c.net_ret_1x
            active.remove(i)
            bases.pop(i)

        nav = 1.0 + realized + sum(unrealized(i, ts) for i in active)
        points.append((ts, float(nav)))

    return pd.Series(
        [value for _ts, value in points],
        index=pd.DatetimeIndex([ts for ts, _value in points]),
        name="nav",
        dtype="float64",
    )


def equity_metrics(
    selected: list[tuple[Cand, float]],
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    full_curve: pd.Series | None = None,
    main_annual: bool = False,
) -> dict[str, Any]:
    """Metrics on a window. If full_curve given, multiple = NAV(end)/NAV(start) on that curve."""
    trades = [(c, exp) for c, exp in selected if start <= c.entry_ts < end]
    if full_curve is None:
        raise ValueError("full_curve is required for specification MTM metrics")

    before = int(full_curve.index.searchsorted(start, side="left")) - 1
    nav0 = float(full_curve.iloc[before]) if before >= 0 else 1.0
    after = int(full_curve.index.searchsorted(end, side="left")) - 1
    nav1 = float(full_curve.iloc[after]) if after >= 0 else nav0
    multiple = float(nav1 / nav0) if nav0 > 0 else float("inf")

    path = full_curve[(full_curve.index >= start) & (full_curve.index < end)]
    if path.empty:
        path = pd.Series([nav0, nav1], index=pd.DatetimeIndex([start, end - pd.Timedelta(seconds=1)]))
    else:
        path = pd.concat([pd.Series([nav0], index=pd.DatetimeIndex([start])), path]).sort_index()
    norm = path / nav0
    peak = norm.cummax()
    mdd = float((norm / peak - 1.0).min()) if len(norm) else 0.0

    rets = np.array([0.5 * exp * c.net_ret_1x for c, exp in trades], dtype="float64")
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    win_rate = float((rets > 0).mean()) if len(rets) else 0.0
    pf = (
        float(wins.sum() / abs(losses.sum()))
        if len(losses) and losses.sum() != 0
        else float("inf")
    )
    daily = norm.resample("1D").last().dropna()
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max(), freq="D")).ffill()
    dr = daily.pct_change().dropna()
    if len(dr) >= 2 and float(dr.std(ddof=1)) > 0:
        sharpe = float(dr.mean() / dr.std(ddof=1) * np.sqrt(365.25))
    else:
        sharpe = 0.0
    if main_annual:
        annual_multiple = multiple ** (365.0 / 397.0) if multiple > 0 else 0.0
    else:
        days = max((end - start).total_seconds() / 86400.0, 1.0)
        annual_multiple = multiple ** (365.25 / days) if multiple > 0 else 0.0
    mar = (annual_multiple - 1.0) / abs(mdd) if mdd < 0 else float("inf")
    return {
        "multiple": multiple,
        "mdd": float(mdd),
        "win_rate": win_rate,
        "pf": pf,
        "trades": int(len(trades)),
        "sharpe": sharpe,
        "mar": float(mar),
        "k2fq_trades": int(sum(1 for c, _ in trades if c.component == "k2fq")),
        "mii_trades": int(sum(1 for c, _ in trades if c.component == "mii")),
    }


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)

    six, six_counts, frames = six_coin_candidates()
    funding = pd.read_parquet(
        ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp/symbol=hype_usdt_usdt/funding.parquet"
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    k2 = k2fq_candidates(funding)
    mii = mii_candidates()
    all_cands = six + k2 + mii
    selected = select_dual_slot(all_cands)

    curve = build_full_equity_curve(selected, frames)
    full = equity_metrics(selected, FULL_START, FULL_END, full_curve=curve)
    main_m = equity_metrics(
        selected, MAIN_START, MAIN_END, full_curve=curve, main_annual=True
    )
    recent_slices: dict[str, dict[str, Any]] = {}
    for label, offset in RECENT_WINDOWS:
        slice_start = max(FULL_START, FULL_END - offset)
        metric = equity_metrics(
            selected, slice_start, FULL_END, full_curve=curve
        )
        recent_slices[label] = {
            "start": slice_start,
            "end": FULL_END,
            "total_return": metric["multiple"] - 1.0,
            **metric,
        }

    summary = {
        "version": "mk7-v8",
        "status": "independent_reproduction_attempt",
        "deviations": [
            "top_lsr_pos uses Binance Vision 5m sum_toptrader_long_short_ratio from 2025-05-30",
            "CVD/flow uses Binance USDM single-venue aggTrades",
            "SOL merged candidates may differ from frozen 79",
            "K2FQ/MII raw counts not byte-matched to frozen 68/375; see notes",
        ],
        "raw_counts": {
            "six": six_counts,
            "six_total": int(sum(six_counts.values())),
            "k2fq": len(k2),
            "mii": len(mii),
            "targets": {
                "six": TARGET_RAW,
                "k2fq": TARGET_K2FQ_RAW,
                "mii": TARGET_MII_RAW,
            },
        },
        "selected": {
            "full": len(selected),
            "main_window": int(sum(1 for c, _ in selected if MAIN_START <= c.entry_ts < MAIN_END)),
            "targets": {"full": TARGET_SELECTED_FULL, "main": TARGET_SELECTED_MAIN},
        },
        "metrics_full": full,
        "metrics_main": main_m,
        "recent_slices": recent_slices,
        "spec_main_targets": {
            "multiple": 37662.136815,
            "mdd": -0.16858990,
            "win_rate": 0.87687188,
            "pf": 4.823429,
            "trades": 601,
            "k2fq": 66,
            "sharpe": 9.870348,
        },
        "spec_full_targets": {
            "multiple": 9328938.861620,
            "mdd": -0.18898046,
            "win_rate": 0.88963661,
            "pf": 6.065153,
            "trades": 743,
            "sharpe": 9.014511,
        },
    }

    trades_rows = []
    for c, exp in selected:
        trades_rows.append(
            {
                "family": c.family,
                "asset": c.asset,
                "leg": c.leg,
                "component": c.component,
                "side": c.side,
                "entry_ts": c.entry_ts.isoformat(),
                "exit_ts": c.exit_ts.isoformat(),
                "exposure": exp,
                "exposure_native": c.exposure_native,
                "stop_pct": c.stop_pct,
                "net_ret_1x": c.net_ret_1x,
                "equity_ret": 0.5 * exp * c.net_ret_1x,
            }
        )
    trades_df = pd.DataFrame(trades_rows)
    trades_path = ART / f"mk7_v8_selected_trades_{DATE_TAG}.csv"
    summary_path = ART / f"mk7_v8_backtest_summary_{DATE_TAG}.json"
    slices_path = ART / f"mk7_v8_recent_slices_{DATE_TAG}.json"
    trades_df.to_csv(trades_path, index=False)
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    slices_path.write_text(
        json.dumps(json_safe(recent_slices), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    counts_path = ART / f"mk7_v8_raw_candidate_counts_{DATE_TAG}.json"
    counts_path.write_text(
        json.dumps(
            json_safe(
                {
                    "raw": {
                        **six_counts,
                        "K2FQ": len(k2),
                        "MII": len(mii),
                    },
                    "expected": {**TARGET_RAW, "K2FQ": TARGET_K2FQ_RAW, "MII": TARGET_MII_RAW},
                    "selected_full": len(selected),
                    "selected_main": int(
                        sum(1 for c, _ in selected if MAIN_START <= c.entry_ts < MAIN_END)
                    ),
                }
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # quick sha of selected identity fields
    payload = trades_df[
        ["asset", "leg", "side", "entry_ts", "exit_ts", "exposure", "equity_ret"]
    ].to_csv(index=False).encode()
    summary["selected_trade_sha256_local"] = hashlib.sha256(payload).hexdigest()
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")

    md = NOTES / f"mk7-v8-backtest-{DATE_TAG}.md"
    md.write_text(
        "\n".join(
            [
                f"# mk7-v8 独立回测 {DATE_TAG}",
                "",
                "状态：`explore / not promoted / not live-ready`",
                "",
                "## 数据口径",
                "",
                "- 币安 USDM 单所；CVD/flow 来自 aggTrades 聚合。",
                "- `top_lsr_pos` 来自 Binance Vision USD-M `daily/metrics` 的 "
                "`sum_toptrader_long_short_ratio`，覆盖 2025-05-30 起完整研究窗。",
                "- Vision 归档与 REST API 近窗重叠值仅有四位小数舍入差；归档 16 个孤立 "
                "5m 缺点按规格取此前最后值。",
                "",
                "## 原始候选",
                "",
                f"- 六币：`{six_counts}`（目标 `{TARGET_RAW}`）",
                f"- K2FQ：`{len(k2)}`（目标 `{TARGET_K2FQ_RAW}`）",
                f"- MII：`{len(mii)}`（目标 `{TARGET_MII_RAW}`）",
                "",
                "## 入选与指标",
                "",
                f"- 完整入选：`{len(selected)}`（目标 `{TARGET_SELECTED_FULL}`）",
                f"- 主窗入选：`{summary['selected']['main_window']}`（目标 `{TARGET_SELECTED_MAIN}`）",
                f"- 主窗：`{json.dumps(json_safe(main_m), ensure_ascii=False)}`",
                f"- 完整：`{json.dumps(json_safe(full), ensure_ascii=False)}`",
                "",
                "## 入选计数分解",
                "",
                (
                    f"- 完整：六币 `{full['trades'] - full['k2fq_trades'] - full['mii_trades']}` / "
                    f"K2FQ `{full['k2fq_trades']}` / MII `{full['mii_trades']}`；"
                    "规格为 `375 / 66 / 302`。"
                ),
                (
                    f"- 主窗：六币 `{main_m['trades'] - main_m['k2fq_trades'] - main_m['mii_trades']}` / "
                    f"K2FQ `{main_m['k2fq_trades']}` / MII `{main_m['mii_trades']}`；"
                    "规格为 `233 / 66 / 302`。"
                ),
                "- 主窗仅剩 K2FQ `+1`；完整窗另有前段 SOL `+3`。",
                "",
                "## 最近窗口（锚定数据末端）",
                "",
                "| 窗口 | UTC 起点 | 收益 | 胜率 | 交易数 |",
                "| --- | --- | ---: | ---: | ---: |",
                *[
                    (
                        f"| `{label}` | `{json_safe(item['start'])}` | "
                        f"`{item['total_return'] * 100:.2f}%` | "
                        f"`{item['win_rate'] * 100:.2f}%` | `{item['trades']}` |"
                    )
                    for label, item in recent_slices.items()
                ],
                "",
                f"所有窗口锚定数据末端 `{FULL_END.isoformat()}`；收益按完整 15m MTM "
                "权益曲线在窗口起止点重定基，交易数/胜率按窗口内入场交易统计。",
                "",
                "## 产物",
                "",
                f"- [`{summary_path.relative_to(FAMILY)}`](../{summary_path.relative_to(FAMILY)})",
                f"- [`{trades_path.relative_to(FAMILY)}`](../{trades_path.relative_to(FAMILY)})",
                f"- [`{counts_path.relative_to(FAMILY)}`](../{counts_path.relative_to(FAMILY)})",
                f"- [`{slices_path.relative_to(FAMILY)}`](../{slices_path.relative_to(FAMILY)})",
                "- [数据完整性报告](../../../../data/cache/mk7_v8_binance/logs/integrity_report.json)",
                "",
                "## 与规格差异",
                "",
                "- 完整 LSR 已消除原先最大的 K2FQ 数据缺口；残余计数偏差需要逐笔冻结清单定位。",
                "- 六币 SOL 合并候选仍高于冻结 79；K2FQ/MII 原始计数尚未完全对齐 68/375。",
                "- 权益使用规格要求的 15m mark-to-market、同刻旧仓先平、同刻开平交易入后结算。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(json_safe(summary), indent=2, ensure_ascii=False))
    print("wrote", summary_path)
    print("wrote", trades_path)
    print("wrote", counts_path)
    print("wrote", slices_path)
    print("wrote", md)


if __name__ == "__main__":
    main()
