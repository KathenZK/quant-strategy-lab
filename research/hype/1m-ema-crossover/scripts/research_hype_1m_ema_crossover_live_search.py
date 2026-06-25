from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from itertools import product
from pathlib import Path
from urllib.parse import urlencode
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests


SYMBOL = "HYPEUSDT"
DISPLAY_SYMBOL = "HYPE/USDT:USDT"
INTERVAL = "1m"
INTERVAL_MS = 60_000
ARCHIVE_URL = "https://data.binance.vision/data/futures/um/daily/klines"
FAPI_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
COMMISSION_PER_SIDE = 0.0005
SLIPPAGE_PER_SIDE = 0.00025
ROUND_TRIP_COST = 2 * (COMMISSION_PER_SIDE + SLIPPAGE_PER_SIDE)
TARGET_ANNUALIZED_FACTOR = 20.0
TARGET_MIN_WIN_RATE = 0.50
TARGET_MAX_DRAWDOWN = -0.20
TARGET_MIN_TRADES = 10


@dataclass(frozen=True, slots=True)
class ExitSpec:
    kind: str
    stop_pct: float
    max_hold_bars: int
    take_profit_pct: float | None = None
    activation_pct: float | None = None
    trail_pct: float | None = None

    @property
    def name(self) -> str:
        if self.kind == "fixed":
            return (
                f"fixed_tp{pct_slug(self.take_profit_pct)}"
                f"_sl{pct_slug(self.stop_pct)}_hold{self.max_hold_bars}"
            )
        return (
            f"trail_act{pct_slug(self.activation_pct)}_trail{pct_slug(self.trail_pct)}"
            f"_sl{pct_slug(self.stop_pct)}_hold{self.max_hold_bars}"
        )


@dataclass(frozen=True, slots=True)
class FilterSpec:
    min_adx14: float = 0.0
    min_rvol60: float = 0.0
    min_htf_dir_spread: float = -99.0
    min_dir_ret60: float = -99.0
    max_churn360: float = 999.0
    min_previous_regime_age: float = 0.0
    min_atr_pct60: float = 0.0
    max_atr_pct60: float = 99.0
    cooldown_bars: int = 0

    @property
    def name(self) -> str:
        parts: list[str] = []
        if self.min_adx14:
            parts.append(f"adx{value_slug(self.min_adx14)}")
        if self.min_rvol60:
            parts.append(f"rvol{value_slug(self.min_rvol60)}")
        if self.min_htf_dir_spread > -90:
            parts.append(f"htf{pct_slug(self.min_htf_dir_spread)}")
        if self.min_dir_ret60 > -90:
            parts.append(f"ret60{pct_slug(self.min_dir_ret60)}")
        if self.max_churn360 < 900:
            parts.append(f"churn{value_slug(self.max_churn360)}")
        if self.min_previous_regime_age:
            parts.append(f"age{value_slug(self.min_previous_regime_age)}")
        if self.min_atr_pct60:
            parts.append(f"atrmin{pct_slug(self.min_atr_pct60)}")
        if self.max_atr_pct60 < 90:
            parts.append(f"atrmax{pct_slug(self.max_atr_pct60)}")
        if self.cooldown_bars:
            parts.append(f"cool{self.cooldown_bars}")
        return "base" if not parts else "_".join(parts)


@dataclass(slots=True)
class EventTrade:
    signal_i: int
    entry_i: int
    exit_i: int
    direction: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_price: float
    exit_price: float
    raw_return: float
    min_path_return: float
    max_path_return: float
    bars_held: int
    exit_reason: str
    adx14: float
    rvol60: float
    htf_dir_spread: float
    dir_ret60: float
    churn360: float
    previous_regime_age: float
    atr_pct60: float


@dataclass(slots=True)
class MarketArrays:
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    ts: np.ndarray
    adx14: np.ndarray
    rvol60: np.ndarray
    ret60: np.ndarray
    htf_spread: np.ndarray
    atr_pct60: np.ndarray


@dataclass(slots=True)
class PairState:
    signal_i: np.ndarray
    directions: np.ndarray
    previous_regime_age: np.ndarray
    churn360: np.ndarray


@dataclass(slots=True)
class SearchResult:
    name: str
    fast_ema: int
    slow_ema: int
    exit_name: str
    exit_kind: str
    filter_name: str
    exposure: float
    final_equity: float
    total_return_pct: float
    annualized_factor: float
    max_drawdown_pct: float
    win_rate: float
    trades: int
    profit_factor: float
    avg_trade_pct: float
    median_trade_pct: float
    worst_trade_pct: float
    stop_trades: int
    tp_trades: int
    trail_trades: int
    opposite_cross_trades: int
    max_hold_trades: int
    score: float
    meets_target: bool
    start_ts: str
    end_ts: str


def pct_slug(value: float | None) -> str:
    if value is None:
        return "na"
    return str(round(value * 10_000, 4)).replace(".", "p")


def value_slug(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value).replace(".", "p").replace("-", "m")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search live-executable HYPE-1M-EMA-Crossover Binance futures variants."
    )
    parser.add_argument("--start-date", type=str, required=True)
    parser.add_argument("--end-date", type=str, required=True)
    parser.add_argument("--refresh-data", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hype_1m_ema_crossover_live_search"))
    parser.add_argument("--output-dir", type=Path, default=Path("research/hype/1m-ema-crossover/artifacts"))
    parser.add_argument("--stage1-keep", type=int, default=500)
    parser.add_argument("--stage2-keep", type=int, default=1000)
    parser.add_argument("--top", type=int, default=100)
    return parser.parse_args()


def date_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def download_bytes(url: str, path: Path, *, refresh: bool) -> bytes | None:
    if path.exists() and not refresh:
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    session = requests.Session()
    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=45)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            tmp_path.write_bytes(response.content)
            tmp_path.replace(path)
            return response.content
        except Exception:
            if attempt == 3:
                break
            time.sleep(1.5 * attempt)

    command = [
        "curl",
        "-L",
        "--http1.1",
        "--retry",
        "5",
        "--retry-all-errors",
        "--retry-delay",
        "1",
        "--silent",
        "--show-error",
        "--max-time",
        "120",
        "-o",
        str(tmp_path),
        url,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            payload = tmp_path.read_bytes()
            tmp_path.replace(path)
            return payload
        return None
    payload = tmp_path.read_bytes()
    tmp_path.replace(path)
    return payload


def load_archive_day(day: date, cache_dir: Path, *, refresh: bool) -> pd.DataFrame | None:
    day_text = day.isoformat()
    url = f"{ARCHIVE_URL}/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{day_text}.zip"
    payload = download_bytes(url, cache_dir / "zips" / f"{SYMBOL}-{INTERVAL}-{day_text}.zip", refresh=refresh)
    if payload is None:
        return None
    with ZipFile(BytesIO(payload)) as zipped:
        names = zipped.namelist()
        if not names:
            return None
        with zipped.open(names[0]) as handle:
            frame = pd.read_csv(handle)
    return normalize_kline_frame(frame, source="binance_vision")


def curl_json(url: str) -> object | None:
    command = [
        "curl",
        "-L",
        "--http1.1",
        "--retry",
        "5",
        "--retry-all-errors",
        "--retry-delay",
        "1",
        "--silent",
        "--show-error",
        "--max-time",
        "120",
        url,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    text = completed.stdout.strip()
    if not text.startswith("["):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_rest_day(day: date) -> pd.DataFrame | None:
    start_ms = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = start_ms + 24 * 60 * 60 * 1000 - 1
    params = urlencode(
        {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1500,
        }
    )
    payload = curl_json(f"{FAPI_KLINES_URL}?{params}")
    if not payload:
        return None
    frame = pd.DataFrame(
        payload,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "count",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignore",
        ],
    )
    return normalize_kline_frame(frame, source="fapi_rest")


def normalize_kline_frame(frame: pd.DataFrame, *, source: str) -> pd.DataFrame:
    renamed = frame.rename(columns={"open_time": "ts", "count": "trade_count"}).copy()
    renamed["ts"] = pd.to_datetime(renamed["ts"], unit="ms", utc=True)
    keep = ["ts", "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
    normalized = renamed[keep].copy()
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized["exchange"] = "binance"
    normalized["symbol"] = DISPLAY_SYMBOL
    normalized["market_type"] = "perp"
    normalized["timeframe"] = INTERVAL
    normalized["base_asset"] = "HYPE"
    normalized["quote_asset"] = "USDT"
    normalized["vwap"] = normalized["quote_volume"] / normalized["volume"].replace(0.0, np.nan)
    normalized["vwap"] = normalized["vwap"].fillna(normalized["close"])
    normalized["is_closed"] = True
    normalized["source"] = source
    return normalized[
        [
            "ts",
            "exchange",
            "symbol",
            "market_type",
            "timeframe",
            "base_asset",
            "quote_asset",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
            "vwap",
            "is_closed",
            "source",
        ]
    ]


def fetch_or_load_data(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, object]]:
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    parquet_path = args.cache_dir / f"{SYMBOL}_{INTERVAL}_{start.isoformat()}_{end.isoformat()}.parquet"
    metadata_path = parquet_path.with_suffix(".metadata.json")
    if parquet_path.exists() and metadata_path.exists() and not args.refresh_data:
        frame = pd.read_parquet(parquet_path)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame, json.loads(metadata_path.read_text())

    frames: list[pd.DataFrame] = []
    missing_archive: list[str] = []
    missing_all: list[str] = []
    rest_days: list[str] = []
    archive_days: list[str] = []

    for day in date_range(start, end):
        frame = load_archive_day(day, args.cache_dir, refresh=args.refresh_data)
        if frame is None:
            missing_archive.append(day.isoformat())
            frame = load_rest_day(day)
            if frame is None:
                missing_all.append(day.isoformat())
                continue
            rest_days.append(day.isoformat())
        else:
            archive_days.append(day.isoformat())
        frames.append(frame)

    if not frames:
        raise RuntimeError("No HYPEUSDT 1m rows were downloaded.")

    combined = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    combined["date"] = combined["ts"].dt.date.astype("string")
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(parquet_path, index=False)

    expected_full_days = len(date_range(start, end)) * 1440
    metadata: dict[str, object] = {
        "symbol": SYMBOL,
        "timeframe": INTERVAL,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rows": int(len(combined)),
        "first_ts": str(combined["ts"].min()),
        "last_ts": str(combined["ts"].max()),
        "expected_full_day_rows": expected_full_days,
        "archive_days": archive_days,
        "rest_days": rest_days,
        "missing_archive_days": missing_archive,
        "missing_all_days": missing_all,
        "cache_parquet": str(parquet_path),
        "commission_per_side": COMMISSION_PER_SIDE,
        "slippage_per_side": SLIPPAGE_PER_SIDE,
        "round_trip_cost": ROUND_TRIP_COST,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    return combined, metadata


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


def rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def adx_di(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def add_features(frame: pd.DataFrame, ema_spans: list[int]) -> pd.DataFrame:
    enriched = frame.sort_values("ts").reset_index(drop=True).copy()
    close = enriched["close"].astype("float64")
    high = enriched["high"].astype("float64")
    low = enriched["low"].astype("float64")
    volume = enriched["volume"].astype("float64")

    for span in ema_spans:
        enriched[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()

    enriched["ret60"] = close.pct_change(60)
    enriched["ret240"] = close.pct_change(240)
    for window in (60, 240):
        enriched[f"rvol{window}"] = volume / volume.rolling(window, min_periods=window).mean().replace(0.0, np.nan)
    tr = true_range(high, low, close)
    enriched["atr60"] = tr.rolling(60, min_periods=60).mean()
    enriched["atr_pct60"] = enriched["atr60"] / close.replace(0.0, np.nan)
    enriched["adx14"], enriched["pdi14"], enriched["mdi14"] = adx_di(high, low, close, 14)
    enriched["rsi14"] = rsi(close, 14)

    htf = (
        enriched.set_index("ts")[["open", "high", "low", "close", "volume"]]
        .resample("15min", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    htf_state = pd.DataFrame(index=htf.index)
    htf_state["htf_ema24"] = htf["close"].ewm(span=24, adjust=False, min_periods=24).mean()
    htf_state["htf_ema96"] = htf["close"].ewm(span=96, adjust=False, min_periods=96).mean()
    htf_state["htf_spread"] = htf_state["htf_ema24"] / htf_state["htf_ema96"].replace(0.0, np.nan) - 1
    htf_state = htf_state.shift(1).reindex(pd.DatetimeIndex(enriched["ts"]), method="ffill")
    enriched["htf_spread"] = htf_state["htf_spread"].to_numpy()
    return enriched


def ema_pairs() -> list[tuple[int, int]]:
    fast_spans = [5, 8, 13, 21, 34, 55, 89, 144, 233]
    slow_spans = [21, 34, 55, 89, 144, 233, 377, 610, 987, 1597]
    return [(fast, slow) for fast in fast_spans for slow in slow_spans if slow > fast * 1.6]


def coarse_exit_specs() -> list[ExitSpec]:
    specs: list[ExitSpec] = []
    for take_profit_pct, stop_pct, max_hold_bars in product(
        [0.01, 0.025, 0.05],
        [0.006, 0.012, 0.022],
        [360, 1440],
    ):
        specs.append(
            ExitSpec(
                kind="fixed",
                take_profit_pct=take_profit_pct,
                stop_pct=stop_pct,
                max_hold_bars=max_hold_bars,
            )
        )
    for activation_pct, trail_pct, stop_pct, max_hold_bars in product(
        [0.01, 0.025, 0.05],
        [0.005, 0.012],
        [0.006, 0.016],
        [720, 1440],
    ):
        specs.append(
            ExitSpec(
                kind="trailing",
                activation_pct=activation_pct,
                trail_pct=trail_pct,
                stop_pct=stop_pct,
                max_hold_bars=max_hold_bars,
            )
        )
    return specs


def full_exit_specs() -> list[ExitSpec]:
    specs: list[ExitSpec] = []
    for take_profit_pct, stop_pct, max_hold_bars in product(
        [0.006, 0.01, 0.016, 0.026, 0.045, 0.07],
        [0.004, 0.007, 0.011, 0.018, 0.028],
        [120, 360, 720, 1440, 2880],
    ):
        specs.append(
            ExitSpec(
                kind="fixed",
                take_profit_pct=take_profit_pct,
                stop_pct=stop_pct,
                max_hold_bars=max_hold_bars,
            )
        )
    for activation_pct, trail_pct, stop_pct, max_hold_bars in product(
        [0.008, 0.014, 0.024, 0.04, 0.06],
        [0.004, 0.007, 0.012, 0.018],
        [0.004, 0.008, 0.014, 0.024],
        [360, 720, 1440, 2880],
    ):
        specs.append(
            ExitSpec(
                kind="trailing",
                activation_pct=activation_pct,
                trail_pct=trail_pct,
                stop_pct=stop_pct,
                max_hold_bars=max_hold_bars,
            )
        )
    return specs


def filter_specs() -> list[FilterSpec]:
    specs: list[FilterSpec] = [FilterSpec()]
    for min_adx14, min_rvol60, min_htf_dir_spread, min_dir_ret60, max_churn360, age, atr_band, cooldown in product(
        [0.0, 12.0, 18.0, 24.0, 30.0],
        [0.0, 0.8, 1.0, 1.25],
        [-99.0, 0.0, 0.0015],
        [-99.0, -0.003, 0.0, 0.003],
        [999.0, 6.0, 3.0],
        [0.0, 60.0, 240.0],
        [(0.0, 99.0), (0.00035, 0.010), (0.0006, 0.007)],
        [0, 30],
    ):
        active_filters = sum(
            [
                min_adx14 > 0,
                min_rvol60 > 0,
                min_htf_dir_spread > -90,
                min_dir_ret60 > -90,
                max_churn360 < 900,
                age > 0,
                atr_band != (0.0, 99.0),
                cooldown > 0,
            ]
        )
        if active_filters > 4:
            continue
        specs.append(
            FilterSpec(
                min_adx14=min_adx14,
                min_rvol60=min_rvol60,
                min_htf_dir_spread=min_htf_dir_spread,
                min_dir_ret60=min_dir_ret60,
                max_churn360=max_churn360,
                min_previous_regime_age=age,
                min_atr_pct60=atr_band[0],
                max_atr_pct60=atr_band[1],
                cooldown_bars=cooldown,
            )
        )
    seen: set[str] = set()
    unique: list[FilterSpec] = []
    for spec in specs:
        if spec.name in seen:
            continue
        seen.add(spec.name)
        unique.append(spec)
    return unique


def build_market_arrays(features: pd.DataFrame) -> MarketArrays:
    return MarketArrays(
        open=features["open"].to_numpy("float64"),
        high=features["high"].to_numpy("float64"),
        low=features["low"].to_numpy("float64"),
        ts=features["ts"].array.to_numpy(),
        adx14=features["adx14"].to_numpy("float64"),
        rvol60=features["rvol60"].to_numpy("float64"),
        ret60=features["ret60"].to_numpy("float64"),
        htf_spread=features["htf_spread"].to_numpy("float64"),
        atr_pct60=features["atr_pct60"].to_numpy("float64"),
    )


def pair_signals(features: pd.DataFrame, fast: int, slow: int) -> PairState:
    spread = features[f"ema{fast}"].to_numpy("float64") / features[f"ema{slow}"].to_numpy("float64") - 1
    sign = np.sign(spread)
    previous = np.r_[np.nan, sign[:-1]]
    cross_long = (sign > 0) & (previous <= 0)
    cross_short = (sign < 0) & (previous >= 0)
    cross = (cross_long | cross_short) & np.isfinite(spread)
    signal_i = np.flatnonzero(cross)
    directions = np.where(cross_long[signal_i], 1, -1)

    previous_regime_age = np.full(len(features), np.nan)
    last_cross = None
    for idx in signal_i:
        if last_cross is not None:
            previous_regime_age[idx] = idx - last_cross
        last_cross = idx
    cross_series = pd.Series(cross.astype(float))
    churn360 = cross_series.shift(1).rolling(360, min_periods=1).sum().to_numpy("float64")
    return PairState(
        signal_i=signal_i,
        directions=directions,
        previous_regime_age=previous_regime_age,
        churn360=churn360,
    )


def finite(value: float, default: float = 0.0) -> float:
    return float(value) if np.isfinite(value) else default


def simulate_trades_from_state(
    market: MarketArrays,
    state: PairState,
    exit_spec: ExitSpec,
) -> list[EventTrade]:
    signal_i = state.signal_i
    directions = state.directions
    previous_regime_age = state.previous_regime_age
    churn360 = state.churn360
    if len(signal_i) < 2:
        return []

    open_arr = market.open
    high_arr = market.high
    low_arr = market.low
    ts_arr = market.ts
    adx14 = market.adx14
    rvol60 = market.rvol60
    ret60 = market.ret60
    htf_spread = market.htf_spread
    atr_pct60 = market.atr_pct60
    n = len(open_arr)
    trades: list[EventTrade] = []

    for pos, signal_idx in enumerate(signal_i):
        entry_i = int(signal_idx + 1)
        if entry_i >= n - 1:
            continue
        direction = int(directions[pos])
        next_signal_idx = int(signal_i[pos + 1]) if pos + 1 < len(signal_i) else n - 2
        forced_exit_i = min(entry_i + exit_spec.max_hold_bars, next_signal_idx + 1, n - 1)
        if forced_exit_i <= entry_i:
            continue

        entry_price = float(open_arr[entry_i])
        stop_price = entry_price * (1 - direction * exit_spec.stop_pct)
        take_profit_price = None
        if exit_spec.kind == "fixed":
            take_profit_price = entry_price * (1 + direction * float(exit_spec.take_profit_pct))

        trail_stop: float | None = None
        best_price = entry_price
        min_path = 0.0
        max_path = 0.0
        exit_i = forced_exit_i
        exit_price = float(open_arr[forced_exit_i])
        exit_reason = "opposite_cross" if forced_exit_i == next_signal_idx + 1 else "max_hold"

        for i in range(entry_i, forced_exit_i):
            high = float(high_arr[i])
            low = float(low_arr[i])
            if direction == 1:
                min_path = min(min_path, low / entry_price - 1)
                max_path = max(max_path, high / entry_price - 1)
                if low <= stop_price:
                    exit_i = i
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                    break
                if trail_stop is not None and low <= trail_stop:
                    exit_i = i
                    exit_price = trail_stop
                    exit_reason = "trailing_stop"
                    break
                if take_profit_price is not None and high >= take_profit_price:
                    exit_i = i
                    exit_price = take_profit_price
                    exit_reason = "take_profit"
                    break
                if exit_spec.kind == "trailing":
                    best_price = max(best_price, high)
                    if best_price / entry_price - 1 >= float(exit_spec.activation_pct):
                        candidate = best_price * (1 - float(exit_spec.trail_pct))
                        trail_stop = candidate if trail_stop is None else max(trail_stop, candidate)
            else:
                min_path = min(min_path, entry_price / high - 1)
                max_path = max(max_path, entry_price / low - 1)
                if high >= stop_price:
                    exit_i = i
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                    break
                if trail_stop is not None and high >= trail_stop:
                    exit_i = i
                    exit_price = trail_stop
                    exit_reason = "trailing_stop"
                    break
                if take_profit_price is not None and low <= take_profit_price:
                    exit_i = i
                    exit_price = take_profit_price
                    exit_reason = "take_profit"
                    break
                if exit_spec.kind == "trailing":
                    best_price = min(best_price, low)
                    if entry_price / best_price - 1 >= float(exit_spec.activation_pct):
                        candidate = best_price * (1 + float(exit_spec.trail_pct))
                        trail_stop = candidate if trail_stop is None else min(trail_stop, candidate)

        raw_return = direction * (exit_price / entry_price - 1)
        trades.append(
            EventTrade(
                signal_i=int(signal_idx),
                entry_i=int(entry_i),
                exit_i=int(exit_i),
                direction=direction,
                entry_ts=pd.Timestamp(ts_arr[entry_i]),
                exit_ts=pd.Timestamp(ts_arr[exit_i]),
                entry_price=entry_price,
                exit_price=float(exit_price),
                raw_return=float(raw_return),
                min_path_return=float(min_path),
                max_path_return=float(max_path),
                bars_held=int(max(exit_i - entry_i, 0)),
                exit_reason=exit_reason,
                adx14=finite(adx14[signal_idx]),
                rvol60=finite(rvol60[signal_idx]),
                htf_dir_spread=finite(htf_spread[signal_idx]) * direction,
                dir_ret60=finite(ret60[signal_idx]) * direction,
                churn360=finite(churn360[signal_idx], default=999.0),
                previous_regime_age=finite(previous_regime_age[signal_idx], default=0.0),
                atr_pct60=finite(atr_pct60[signal_idx]),
            )
        )
    return trades


def simulate_trades(
    features: pd.DataFrame,
    fast: int,
    slow: int,
    exit_spec: ExitSpec,
) -> list[EventTrade]:
    return simulate_trades_from_state(
        build_market_arrays(features),
        pair_signals(features, fast, slow),
        exit_spec,
    )


def passes_filter(trade: EventTrade, spec: FilterSpec) -> bool:
    return (
        trade.adx14 >= spec.min_adx14
        and trade.rvol60 >= spec.min_rvol60
        and trade.htf_dir_spread >= spec.min_htf_dir_spread
        and trade.dir_ret60 >= spec.min_dir_ret60
        and trade.churn360 <= spec.max_churn360
        and trade.previous_regime_age >= spec.min_previous_regime_age
        and trade.atr_pct60 >= spec.min_atr_pct60
        and trade.atr_pct60 <= spec.max_atr_pct60
    )


def evaluate_trades(
    *,
    trades: list[EventTrade],
    filter_spec: FilterSpec,
    exposure: float,
    period_days: float,
    fast: int,
    slow: int,
    exit_spec: ExitSpec,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> SearchResult | None:
    selected: list[EventTrade] = []
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    cooldown_until = -1
    net_returns: list[float] = []
    gross_wins = 0.0
    gross_losses = 0.0

    for trade in trades:
        if trade.entry_i < cooldown_until:
            continue
        if not passes_filter(trade, filter_spec):
            continue
        min_mark_return = exposure * (trade.min_path_return - ROUND_TRIP_COST)
        mark_equity = equity * max(0.0, 1 + min_mark_return)
        if peak > 0:
            max_drawdown = min(max_drawdown, mark_equity / peak - 1)

        trade_net_return = exposure * (trade.raw_return - ROUND_TRIP_COST)
        equity *= max(0.0, 1 + trade_net_return)
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1)
        selected.append(trade)
        net_returns.append(trade_net_return)
        if trade_net_return >= 0:
            gross_wins += trade_net_return
        else:
            gross_losses += abs(trade_net_return)
        cooldown_until = trade.exit_i + filter_spec.cooldown_bars

    if not selected:
        return None

    final_equity = float(equity)
    total_return_pct = (final_equity - 1.0) * 100
    annualized_factor = final_equity ** (365.25 / period_days) if period_days > 0 and final_equity > 0 else 0.0
    wins = [value for value in net_returns if value > 0]
    win_rate = len(wins) / len(net_returns)
    max_drawdown_pct = max_drawdown * 100
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else math.inf
    stop_trades = sum(1 for trade in selected if trade.exit_reason == "stop_loss")
    tp_trades = sum(1 for trade in selected if trade.exit_reason == "take_profit")
    trail_trades = sum(1 for trade in selected if trade.exit_reason == "trailing_stop")
    opposite_cross_trades = sum(1 for trade in selected if trade.exit_reason == "opposite_cross")
    max_hold_trades = sum(1 for trade in selected if trade.exit_reason == "max_hold")
    meets_target = (
        annualized_factor >= TARGET_ANNUALIZED_FACTOR
        and win_rate >= TARGET_MIN_WIN_RATE
        and max_drawdown >= TARGET_MAX_DRAWDOWN
        and len(selected) >= TARGET_MIN_TRADES
    )
    drawdown_penalty = max(0.0, abs(max_drawdown) - abs(TARGET_MAX_DRAWDOWN)) * 10
    trade_penalty = max(0, TARGET_MIN_TRADES - len(selected)) * 0.15
    score = math.log(max(annualized_factor, 1e-9)) + win_rate - drawdown_penalty - trade_penalty
    if meets_target:
        score += 10
    name = f"HYPE_1M_EMA_CROSSOVER_FAST{fast}_SLOW{slow}_{exit_spec.name}_{filter_spec.name}_x{value_slug(exposure)}"
    return SearchResult(
        name=name,
        fast_ema=fast,
        slow_ema=slow,
        exit_name=exit_spec.name,
        exit_kind=exit_spec.kind,
        filter_name=filter_spec.name,
        exposure=exposure,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        annualized_factor=annualized_factor,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate * 100,
        trades=len(selected),
        profit_factor=profit_factor,
        avg_trade_pct=float(np.mean(net_returns) * 100),
        median_trade_pct=float(np.median(net_returns) * 100),
        worst_trade_pct=float(np.min(net_returns) * 100),
        stop_trades=stop_trades,
        tp_trades=tp_trades,
        trail_trades=trail_trades,
        opposite_cross_trades=opposite_cross_trades,
        max_hold_trades=max_hold_trades,
        score=score,
        meets_target=meets_target,
        start_ts=str(start_ts),
        end_ts=str(end_ts),
    )


def result_sort_key(result: SearchResult) -> tuple[int, float, float, float, int]:
    return (
        int(result.meets_target),
        result.score,
        result.annualized_factor,
        -abs(result.max_drawdown_pct),
        result.trades,
    )


def top_results(results: list[SearchResult], keep: int) -> list[SearchResult]:
    return sorted(results, key=result_sort_key, reverse=True)[:keep]


def maybe_prune_results(results: list[SearchResult], keep: int) -> list[SearchResult]:
    if len(results) <= keep * 3:
        return results
    return top_results(results, keep)


def trades_to_frame(trades: list[EventTrade], *, result: SearchResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for trade in trades:
        rows.append(
            {
                "strategy": result.name,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "direction": "long" if trade.direction == 1 else "short",
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "raw_return_pct": trade.raw_return * 100,
                "net_return_pct": result.exposure * (trade.raw_return - ROUND_TRIP_COST) * 100,
                "min_path_return_pct": trade.min_path_return * 100,
                "max_path_return_pct": trade.max_path_return * 100,
                "bars_held": trade.bars_held,
                "exit_reason": trade.exit_reason,
                "adx14": trade.adx14,
                "rvol60": trade.rvol60,
                "htf_dir_spread": trade.htf_dir_spread,
                "dir_ret60": trade.dir_ret60,
                "churn360": trade.churn360,
                "previous_regime_age": trade.previous_regime_age,
                "atr_pct60": trade.atr_pct60,
            }
        )
    return pd.DataFrame(rows)


def selected_trades_for_result(
    raw_trades: list[EventTrade],
    filter_spec: FilterSpec,
    exposure: float,
) -> list[EventTrade]:
    selected: list[EventTrade] = []
    cooldown_until = -1
    for trade in raw_trades:
        if trade.entry_i < cooldown_until:
            continue
        if not passes_filter(trade, filter_spec):
            continue
        selected.append(trade)
        cooldown_until = trade.exit_i + filter_spec.cooldown_bars
    return selected


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw, metadata = fetch_or_load_data(args)
    raw = raw.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    start_ts = raw["ts"].min()
    end_ts = raw["ts"].max()
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1)
    print(f"loaded rows={len(raw)} start={start_ts} end={end_ts}", flush=True)

    pairs = ema_pairs()
    spans = sorted({span for pair in pairs for span in pair})
    features = add_features(raw, spans)
    feature_ready = features.dropna(subset=[f"ema{max(spans)}", "adx14", "rvol60", "atr_pct60"]).index.min()
    if pd.isna(feature_ready):
        raise RuntimeError("Not enough 1m data for the slowest EMA and features.")

    market = build_market_arrays(features)
    exposures = [1.0, 1.5, 2.0, 2.5, 3.0]
    base_filters = [FilterSpec(), FilterSpec(min_htf_dir_spread=0.0), FilterSpec(min_adx14=18.0)]
    stage1_results: list[SearchResult] = []
    trade_cache: dict[tuple[int, int, str], list[EventTrade]] = {}
    pair_state_cache: dict[tuple[int, int], PairState] = {}

    for pair_no, (fast, slow) in enumerate(pairs, start=1):
        pair_state = pair_signals(features, fast, slow)
        pair_state_cache[(fast, slow)] = pair_state
        for exit_spec in coarse_exit_specs():
            raw_trades = simulate_trades_from_state(market, pair_state, exit_spec)
            if len(raw_trades) < 3:
                continue
            trade_cache[(fast, slow, exit_spec.name)] = raw_trades
            for filter_spec in base_filters:
                for exposure in exposures:
                    result = evaluate_trades(
                        trades=raw_trades,
                        filter_spec=filter_spec,
                        exposure=exposure,
                        period_days=period_days,
                        fast=fast,
                        slow=slow,
                        exit_spec=exit_spec,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                    if result is not None:
                        stage1_results.append(result)
        print(
            f"stage1 pairs={pair_no}/{len(pairs)} signals={len(pair_state.signal_i)} "
            f"results={len(stage1_results)}",
            flush=True,
        )

    stage1_top = top_results(stage1_results, args.stage1_keep)
    top_pairs = sorted({(result.fast_ema, result.slow_ema) for result in stage1_top})
    print(
        f"stage1 done results={len(stage1_results)} kept={len(stage1_top)} top_pairs={len(top_pairs)}",
        flush=True,
    )
    stage2_base_map: dict[tuple[int, int, str], tuple[SearchResult, ExitSpec, list[EventTrade]]] = {}
    stage2_seed_results: list[SearchResult] = []
    full_exits = full_exit_specs()

    for pair_no, (fast, slow) in enumerate(top_pairs, start=1):
        pair_state = pair_state_cache.get((fast, slow))
        if pair_state is None:
            pair_state = pair_signals(features, fast, slow)
            pair_state_cache[(fast, slow)] = pair_state
        for exit_spec in full_exits:
            raw_trades = simulate_trades_from_state(market, pair_state, exit_spec)
            if len(raw_trades) < 3:
                continue
            for filter_spec in base_filters:
                for exposure in exposures:
                    result = evaluate_trades(
                        trades=raw_trades,
                        filter_spec=filter_spec,
                        exposure=exposure,
                        period_days=period_days,
                        fast=fast,
                        slow=slow,
                        exit_spec=exit_spec,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                    if result is not None:
                        stage2_seed_results.append(result)
                        key = (fast, slow, exit_spec.name)
                        current = stage2_base_map.get(key)
                        if current is None or result_sort_key(result) > result_sort_key(current[0]):
                            stage2_base_map[key] = (result, exit_spec, raw_trades)
        print(
            f"stage2 pairs={pair_no}/{len(top_pairs)} seed_results={len(stage2_seed_results)} "
            f"unique_exits={len(stage2_base_map)}",
            flush=True,
        )

    stage2_base = sorted(stage2_base_map.values(), key=lambda row: result_sort_key(row[0]), reverse=True)[: args.stage2_keep]
    print(f"stage2 done kept={len(stage2_base)}", flush=True)
    filters = filter_specs()
    final_results: list[SearchResult] = []
    final_evaluated = 0
    final_with_trades = 0
    targets_met = 0
    final_keep = max(args.top * 20, 1000)
    for base_no, (seed_result, exit_spec, raw_trades) in enumerate(stage2_base, start=1):
        for filter_spec in filters:
            for exposure in exposures:
                final_evaluated += 1
                result = evaluate_trades(
                    trades=raw_trades,
                    filter_spec=filter_spec,
                    exposure=exposure,
                    period_days=period_days,
                    fast=seed_result.fast_ema,
                    slow=seed_result.slow_ema,
                    exit_spec=exit_spec,
                    start_ts=start_ts,
                    end_ts=end_ts,
                )
                if result is None:
                    continue
                final_with_trades += 1
                targets_met += int(result.meets_target)
                final_results.append(result)
                final_results = maybe_prune_results(final_results, final_keep)
        if base_no % 100 == 0:
            print(
                f"final base={base_no}/{len(stage2_base)} evaluated={final_evaluated} "
                f"with_trades={final_with_trades} targets={targets_met}",
                flush=True,
            )

    final_results = top_results(final_results, final_keep)
    ranking = top_results(final_results, args.top)
    ranking_frame = pd.DataFrame([asdict(result) for result in ranking])
    ranking_path = args.output_dir / "hype_1m_ema_crossover_live_search_ranking.csv"
    ranking_frame.to_csv(ranking_path, index=False)

    best = ranking[0] if ranking else None
    top_trade_path = args.output_dir / "hype_1m_ema_crossover_live_search_top_trades.csv"
    if best is not None:
        best_exit = next(spec for spec in full_exits if spec.name == best.exit_name)
        best_filter = next(spec for spec in filters if spec.name == best.filter_name)
        best_pair_state = pair_state_cache.get((best.fast_ema, best.slow_ema))
        if best_pair_state is None:
            best_pair_state = pair_signals(features, best.fast_ema, best.slow_ema)
        best_raw_trades = simulate_trades_from_state(market, best_pair_state, best_exit)
        selected = selected_trades_for_result(best_raw_trades, best_filter, best.exposure)
        trades_to_frame(selected, result=best).to_csv(top_trade_path, index=False)

    summary = {
        "metadata": metadata,
        "feature_ready_index": int(feature_ready),
        "period_days": period_days,
        "pairs_tested": len(pairs),
        "coarse_exit_specs": len(coarse_exit_specs()),
        "full_exit_specs": len(full_exits),
        "filter_specs": len(filters),
        "stage1_results": len(stage1_results),
        "stage1_kept": len(stage1_top),
        "stage2_seed_results": len(stage2_seed_results),
        "stage2_base_kept": len(stage2_base),
        "final_candidates_evaluated": final_evaluated,
        "final_candidates_with_trades": final_with_trades,
        "final_results_kept": len(final_results),
        "target": {
            "annualized_factor": TARGET_ANNUALIZED_FACTOR,
            "min_win_rate": TARGET_MIN_WIN_RATE,
            "max_drawdown": TARGET_MAX_DRAWDOWN,
            "min_trades": TARGET_MIN_TRADES,
        },
        "cost_assumption": {
            "commission_per_side": COMMISSION_PER_SIDE,
            "slippage_per_side": SLIPPAGE_PER_SIDE,
            "round_trip_cost": ROUND_TRIP_COST,
        },
        "best": asdict(best) if best is not None else None,
        "targets_met": targets_met,
        "ranking_csv": str(ranking_path),
        "top_trades_csv": str(top_trade_path) if best is not None else None,
    }
    summary_path = args.output_dir / "hype_1m_ema_crossover_live_search.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
