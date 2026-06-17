from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OHLCV_COLUMNS = (
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
)


@dataclass(frozen=True, slots=True)
class CrossQualityConfig:
    exchange: str
    market_type: str = "perp"
    timeframe: str = "15m"
    symbols: tuple[str, ...] | None = None
    benchmark_symbol: str | None = "BTC/USDT:USDT"
    horizon_bars: int = 384
    target_atr: float = 6.0
    stop_atr: float = 3.5
    min_bars: int = 800
    require_full_horizon: bool = True
    max_symbols: int | None = None


def symbol_slug(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_").lower()


def discover_symbol_files(ohlcv_root: Path, config: CrossQualityConfig) -> dict[str, list[Path]]:
    root = (
        ohlcv_root
        / f"exchange={config.exchange.lower()}"
        / f"market_type={config.market_type.lower()}"
        / f"timeframe={config.timeframe.lower()}"
    )
    if not root.exists():
        return {}

    requested = {symbol_slug(symbol) for symbol in config.symbols or ()}
    grouped: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("symbol=*.parquet")):
        slug = path.stem.split("symbol=", 1)[-1]
        if requested and slug not in requested:
            continue
        grouped.setdefault(slug, []).append(path)

    if config.max_symbols is None:
        return grouped
    return dict(list(grouped.items())[: config.max_symbols])


def load_symbol_ohlcv(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    frames = [pd.read_parquet(path) for path in sorted(paths)]
    frame = pd.concat(frames, ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    if "is_closed" in frame.columns:
        frame = frame[frame["is_closed"].fillna(False)]
    frame = frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume", "quote_volume", "vwap"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


def adx_di(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    minus_di = (
        100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    )
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def trend_efficiency(close: pd.Series, window: int) -> pd.Series:
    direct = close.pct_change(window).abs()
    path = close.pct_change().abs().rolling(window, min_periods=window).sum()
    return direct / path.replace(0.0, np.nan)


def rolling_last_percentile(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).rank(pct=True)


def add_cross_quality_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy().sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    close = frame["close"].astype("float64")
    high = frame["high"].astype("float64")
    low = frame["low"].astype("float64")
    open_ = frame["open"].astype("float64")
    volume = frame["volume"].astype("float64")
    quote_volume = frame["quote_volume"].astype("float64") if "quote_volume" in frame else close * volume

    frame["ret1"] = close.pct_change()
    for window in (4, 16, 48, 96, 192, 672):
        frame[f"ret{window}"] = close.pct_change(window)

    frame["ema96"] = close.ewm(span=96, adjust=False, min_periods=96).mean()
    frame["ema384"] = close.ewm(span=384, adjust=False, min_periods=384).mean()
    frame["ema_spread"] = frame["ema96"] / frame["ema384"].replace(0.0, np.nan) - 1
    frame["ema96_slope16"] = frame["ema96"].pct_change(16)
    frame["ema96_slope48"] = frame["ema96"].pct_change(48)
    frame["ema384_slope96"] = frame["ema384"].pct_change(96)
    frame["spread_slope4"] = frame["ema_spread"].diff(4)
    frame["spread_slope16"] = frame["ema_spread"].diff(16)
    frame["spread_slope48"] = frame["ema_spread"].diff(48)
    frame["cross_angle_proxy"] = frame["ema96_slope16"] - frame["ema384_slope96"] / 6.0

    for window in (96, 192, 672):
        mean_volume = volume.rolling(window, min_periods=window).mean()
        mean_quote_volume = quote_volume.rolling(window, min_periods=window).mean()
        frame[f"rvol{window}"] = volume / mean_volume.replace(0.0, np.nan)
        frame[f"quote_rvol{window}"] = quote_volume / mean_quote_volume.replace(0.0, np.nan)

    tr = true_range(high, low, close)
    for window in (96, 336, 672):
        frame[f"atr{window}"] = tr.rolling(window, min_periods=window).mean()
        frame[f"atr_pct{window}"] = frame[f"atr{window}"] / close.replace(0.0, np.nan)
    frame["atr_ratio96_672"] = frame["atr_pct96"] / frame["atr_pct672"].replace(0.0, np.nan)

    frame["realized_vol96"] = frame["ret1"].rolling(96, min_periods=96).std()
    frame["realized_vol672"] = frame["ret1"].rolling(672, min_periods=672).std()
    frame["volatility_ratio96_672"] = frame["realized_vol96"] / frame["realized_vol672"].replace(0.0, np.nan)
    frame["volatility_pctile672"] = rolling_last_percentile(frame["realized_vol96"], 672)

    for window in (14, 28):
        frame[f"adx{window}"], frame[f"pdi{window}"], frame[f"mdi{window}"] = adx_di(high, low, close, window)
    frame["adx28_slope16"] = frame["adx28"] - frame["adx28"].shift(16)
    frame["rsi14"] = rsi(close, 14)

    candle_range = (high - low).replace(0.0, np.nan)
    typical = (high + low + close) / 3.0
    money_flow = typical * volume
    positive_flow = money_flow.where(typical > typical.shift(1), 0.0)
    negative_flow = money_flow.where(typical < typical.shift(1), 0.0)
    flow_ratio = (
        positive_flow.rolling(14, min_periods=14).sum()
        / negative_flow.rolling(14, min_periods=14).sum().replace(0.0, np.nan)
    )
    frame["mfi14"] = 100 - 100 / (1 + flow_ratio)
    mfv = ((2 * close - high - low) / candle_range) * volume
    frame["cmf20"] = mfv.rolling(20, min_periods=20).sum() / volume.rolling(20, min_periods=20).sum().replace(0.0, np.nan)
    sign = np.sign(close.diff()).fillna(0.0)
    frame["obv"] = (sign * volume).cumsum()
    volume_sum96 = volume.rolling(96, min_periods=96).sum().replace(0.0, np.nan)
    frame["obv_mom48_norm"] = frame["obv"].diff(48) / volume_sum96
    frame["obv_mom96_norm"] = frame["obv"].diff(96) / volume_sum96
    frame["candle_pos"] = ((close - low) / candle_range).clip(0.0, 1.0)
    frame["body_range"] = ((close - open_).abs() / candle_range).clip(0.0, 1.0)

    for window in (96, 192):
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        frame[f"donchian_pos{window}"] = (close - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)

    frame["symbol_ret672"] = close.pct_change(672)
    frame["symbol_realized_vol672"] = frame["ret1"].rolling(672, min_periods=672).std()
    frame["symbol_trend_eff672"] = trend_efficiency(close, 672)
    frame["symbol_quote_volume_mean672"] = quote_volume.rolling(672, min_periods=672).mean()
    frame["symbol_quote_volume_ratio96_672"] = (
        quote_volume.rolling(96, min_periods=96).mean()
        / quote_volume.rolling(672, min_periods=672).mean().replace(0.0, np.nan)
    )

    spread_sign = np.sign(frame["ema_spread"].to_numpy("float64"))
    previous_sign = np.r_[np.nan, spread_sign[:-1]]
    cross = ((spread_sign > 0) & (previous_sign <= 0)) | ((spread_sign < 0) & (previous_sign >= 0))
    age = np.full(len(frame), np.nan)
    previous_regime_age = np.full(len(frame), np.nan)
    current_age = np.nan
    for i, is_cross in enumerate(cross):
        if is_cross:
            previous_regime_age[i] = current_age
            current_age = 0.0
        elif np.isfinite(current_age):
            current_age += 1.0
        age[i] = current_age
    frame["regime_age"] = age
    frame["previous_regime_age"] = previous_regime_age
    valid_change = np.isfinite(spread_sign) & np.isfinite(previous_sign) & (spread_sign != 0) & (previous_sign != 0)
    sign_change = pd.Series(valid_change & (spread_sign != previous_sign), index=frame.index)
    frame["cross_churn192"] = sign_change.shift(1).rolling(192, min_periods=1).sum()
    frame["cross_churn672"] = sign_change.shift(1).rolling(672, min_periods=1).sum()

    return frame


def benchmark_state(features: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "ema_spread": "btc_ema_spread",
        "ret96": "btc_ret96",
        "ret672": "btc_ret672",
        "adx28": "btc_adx28",
        "pdi28": "btc_pdi28",
        "mdi28": "btc_mdi28",
        "atr_pct672": "btc_atr_pct672",
        "volatility_pctile672": "btc_volatility_pctile672",
        "realized_vol672": "btc_realized_vol672",
    }
    state = features[["ts", *columns.keys()]].rename(columns=columns).copy()
    state["btc_regime"] = np.sign(state["btc_ema_spread"])
    state["btc_di_spread"] = state["btc_pdi28"] - state["btc_mdi28"]
    return state.sort_values("ts").reset_index(drop=True)


def _label_future_path(
    frame: pd.DataFrame,
    event_i: int,
    *,
    direction: int,
    horizon_bars: int,
    target_atr: float,
    stop_atr: float,
    require_full_horizon: bool,
) -> dict[str, Any] | None:
    final_i = event_i + horizon_bars
    if final_i >= len(frame):
        if require_full_horizon:
            return None
        final_i = len(frame) - 1
    if final_i <= event_i:
        return None

    entry = float(frame["close"].iloc[event_i])
    atr_pct = float(frame["atr_pct672"].iloc[event_i])
    if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr_pct) or atr_pct <= 0:
        return None

    future = frame.iloc[event_i + 1 : final_i + 1]
    if direction > 0:
        favorable = future["high"].to_numpy("float64") / entry - 1.0
        adverse = 1.0 - future["low"].to_numpy("float64") / entry
    else:
        favorable = 1.0 - future["low"].to_numpy("float64") / entry
        adverse = future["high"].to_numpy("float64") / entry - 1.0

    target_return = target_atr * atr_pct
    stop_return = stop_atr * atr_pct
    target_hits = np.flatnonzero(favorable >= target_return)
    stop_hits = np.flatnonzero(adverse >= stop_return)
    first_target_bar = int(target_hits[0] + 1) if len(target_hits) else None
    first_stop_bar = int(stop_hits[0] + 1) if len(stop_hits) else None
    target_before_stop = first_target_bar is not None and (first_stop_bar is None or first_target_bar < first_stop_bar)
    mfe = float(np.nanmax(favorable))
    mae = float(np.nanmax(adverse))
    horizon_return = direction * (float(frame["close"].iloc[final_i]) / entry - 1.0)

    return {
        "horizon_bars": int(final_i - event_i),
        "target_atr": float(target_atr),
        "stop_atr": float(stop_atr),
        "target_return": float(target_return),
        "stop_return": float(stop_return),
        "future_mfe": mfe,
        "future_mae": mae,
        "future_mfe_atr": float(mfe / atr_pct),
        "future_mae_atr": float(mae / atr_pct),
        "future_return": float(horizon_return),
        "future_return_atr": float(horizon_return / atr_pct),
        "first_target_bar": first_target_bar,
        "first_stop_bar": first_stop_bar,
        "target_before_stop": bool(target_before_stop),
        "hit_target": bool(first_target_bar is not None),
        "hit_stop": bool(first_stop_bar is not None),
        "capture_score": float(mfe / atr_pct - mae / atr_pct),
    }


def _event_features(frame: pd.DataFrame, event_i: int, *, direction: int) -> dict[str, Any] | None:
    row = frame.iloc[event_i]
    close = float(row["close"])
    ema96 = float(row["ema96"])
    ema384 = float(row["ema384"])
    if not np.isfinite(close) or close <= 0 or not np.isfinite(ema96) or not np.isfinite(ema384):
        return None

    side = "long" if direction > 0 else "short"
    pdi28 = float(row["pdi28"])
    mdi28 = float(row["mdi28"])
    donchian96 = float(row["donchian_pos96"])
    donchian192 = float(row["donchian_pos192"])
    return {
        "event_i": int(event_i),
        "ts": row["ts"],
        "side": side,
        "direction": int(direction),
        "entry_price": close,
        "ema_spread": float(row["ema_spread"]),
        "ema96_slope16": float(row["ema96_slope16"]),
        "ema96_slope48": float(row["ema96_slope48"]),
        "ema384_slope96": float(row["ema384_slope96"]),
        "spread_slope4": float(row["spread_slope4"]),
        "spread_slope16": float(row["spread_slope16"]),
        "spread_slope48": float(row["spread_slope48"]),
        "cross_angle_proxy": float(row["cross_angle_proxy"]),
        "ema96_slope16_dir": float(direction * row["ema96_slope16"]),
        "ema96_slope48_dir": float(direction * row["ema96_slope48"]),
        "ema384_slope96_dir": float(direction * row["ema384_slope96"]),
        "spread_slope16_dir": float(direction * row["spread_slope16"]),
        "cross_angle_proxy_dir": float(direction * row["cross_angle_proxy"]),
        "regime_age": float(row["regime_age"]),
        "previous_regime_age": float(row["previous_regime_age"]),
        "adx14": float(row["adx14"]),
        "adx28": float(row["adx28"]),
        "adx28_slope16": float(row["adx28_slope16"]),
        "pdi28": pdi28,
        "mdi28": mdi28,
        "di_spread28": pdi28 - mdi28,
        "di_spread28_dir": float(direction * (pdi28 - mdi28)),
        "atr_pct96": float(row["atr_pct96"]),
        "atr_pct336": float(row["atr_pct336"]),
        "atr_pct672": float(row["atr_pct672"]),
        "atr_ratio96_672": float(row["atr_ratio96_672"]),
        "realized_vol96": float(row["realized_vol96"]),
        "realized_vol672": float(row["realized_vol672"]),
        "volatility_ratio96_672": float(row["volatility_ratio96_672"]),
        "volatility_pctile672": float(row["volatility_pctile672"]),
        "rvol96": float(row["rvol96"]),
        "rvol192": float(row["rvol192"]),
        "rvol672": float(row["rvol672"]),
        "quote_rvol96": float(row["quote_rvol96"]),
        "quote_rvol192": float(row["quote_rvol192"]),
        "mfi14": float(row["mfi14"]),
        "mfi14_dir": float(direction * (row["mfi14"] - 50.0)),
        "cmf20": float(row["cmf20"]),
        "cmf20_dir": float(direction * row["cmf20"]),
        "obv_mom48_norm": float(row["obv_mom48_norm"]),
        "obv_mom48_norm_dir": float(direction * row["obv_mom48_norm"]),
        "obv_mom96_norm": float(row["obv_mom96_norm"]),
        "obv_mom96_norm_dir": float(direction * row["obv_mom96_norm"]),
        "candle_pos": float(row["candle_pos"]),
        "body_range": float(row["body_range"]),
        "ret16": float(row["ret16"]),
        "ret48": float(row["ret48"]),
        "ret96": float(row["ret96"]),
        "ret192": float(row["ret192"]),
        "ret16_dir": float(direction * row["ret16"]),
        "ret48_dir": float(direction * row["ret48"]),
        "ret96_dir": float(direction * row["ret96"]),
        "ret192_dir": float(direction * row["ret192"]),
        "donchian_pos96": donchian96,
        "donchian_pos192": donchian192,
        "donchian_pos96_dir": donchian96 if direction > 0 else 1.0 - donchian96,
        "donchian_pos192_dir": donchian192 if direction > 0 else 1.0 - donchian192,
        "dist_ema96": float(direction * (close / ema96 - 1.0)),
        "dist_ema384": float(direction * (close / ema384 - 1.0)),
        "abs_dist_ema96": float(abs(close / ema96 - 1.0)),
        "abs_dist_ema384": float(abs(close / ema384 - 1.0)),
        "cross_churn192": float(row["cross_churn192"]),
        "cross_churn672": float(row["cross_churn672"]),
        "symbol_ret672": float(row["symbol_ret672"]),
        "symbol_realized_vol672": float(row["symbol_realized_vol672"]),
        "symbol_trend_eff672": float(row["symbol_trend_eff672"]),
        "symbol_quote_volume_mean672": float(row["symbol_quote_volume_mean672"]),
        "symbol_quote_volume_ratio96_672": float(row["symbol_quote_volume_ratio96_672"]),
    }


def extract_cross_events(
    features: pd.DataFrame,
    config: CrossQualityConfig,
    *,
    metadata: dict[str, Any] | None = None,
    benchmark: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if len(features) < config.min_bars:
        return pd.DataFrame()

    spread = features["ema_spread"].to_numpy("float64")
    sign = np.sign(spread)
    previous = np.r_[np.nan, sign[:-1]]
    cross_idx = np.flatnonzero(((sign > 0) & (previous <= 0)) | ((sign < 0) & (previous >= 0)))
    rows: list[dict[str, Any]] = []
    for event_i in cross_idx:
        direction = 1 if sign[event_i] > 0 else -1
        event = _event_features(features, int(event_i), direction=direction)
        if event is None:
            continue
        label = _label_future_path(
            features,
            int(event_i),
            direction=direction,
            horizon_bars=config.horizon_bars,
            target_atr=config.target_atr,
            stop_atr=config.stop_atr,
            require_full_horizon=config.require_full_horizon,
        )
        if label is None:
            continue
        rows.append({**(metadata or {}), **event, **label})

    events = pd.DataFrame(rows)
    if events.empty or benchmark is None or benchmark.empty:
        return events

    return pd.merge_asof(
        events.sort_values("ts"),
        benchmark.sort_values("ts"),
        on="ts",
        direction="backward",
    )


def build_cross_quality_dataset(ohlcv_root: Path, config: CrossQualityConfig) -> pd.DataFrame:
    symbol_files = discover_symbol_files(ohlcv_root, config)
    if not symbol_files:
        return pd.DataFrame()

    benchmark = None
    if config.benchmark_symbol:
        benchmark_slug = symbol_slug(config.benchmark_symbol)
        benchmark_paths = symbol_files.get(benchmark_slug)
        if benchmark_paths:
            benchmark = benchmark_state(add_cross_quality_features(load_symbol_ohlcv(benchmark_paths)))

    frames: list[pd.DataFrame] = []
    for paths in symbol_files.values():
        raw = load_symbol_ohlcv(paths)
        if raw.empty:
            continue
        symbol = str(raw["symbol"].iloc[0]) if "symbol" in raw else paths[0].stem.removeprefix("symbol=")
        features = add_cross_quality_features(raw)
        metadata = {
            "exchange": config.exchange.lower(),
            "market_type": config.market_type.lower(),
            "timeframe": config.timeframe.lower(),
            "symbol": symbol,
            "base_asset": str(raw["base_asset"].iloc[0]) if "base_asset" in raw else None,
            "quote_asset": str(raw["quote_asset"].iloc[0]) if "quote_asset" in raw else None,
        }
        events = extract_cross_events(features, config, metadata=metadata, benchmark=benchmark)
        if not events.empty:
            frames.append(events)

    if not frames:
        return pd.DataFrame()
    dataset = pd.concat(frames, ignore_index=True).sort_values(["ts", "symbol", "side"]).reset_index(drop=True)
    dataset["event_date"] = pd.to_datetime(dataset["ts"], utc=True).dt.date.astype(str)
    return dataset
