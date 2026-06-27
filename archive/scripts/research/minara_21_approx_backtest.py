from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import duckdb
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OHLCV_ROOT = (
    PROJECT_ROOT
    / "data"
    / "normalized"
    / "ohlcv"
    / "exchange=binance"
    / "market_type=perp"
)
REPORT_PREFIX = PROJECT_ROOT / "reports" / "minara_21_approx_btc_hype"
FEE_RATE = 0.00045


@dataclass(frozen=True, slots=True)
class StrategySpec:
    rank: int
    name: str
    original_asset: str
    original_timeframe: str
    public_rule_quality: str
    logic_name: str
    notes: str
    window_days: int
    allocation: float = 1.0


@dataclass(frozen=True, slots=True)
class RuleOutput:
    signal: pd.Series
    stop_pct: pd.Series | float | None = None
    take_pct: pd.Series | float | None = None
    exit_on_zero: bool = False
    flip: bool = True


def _symbol_stem(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_").lower()


def load_ohlcv(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    root = OHLCV_ROOT / f"timeframe={timeframe}"
    files = sorted(root.glob(f"date=*/symbol={_symbol_stem(symbol)}.parquet"))
    if not files:
        raise FileNotFoundError(f"no {timeframe} parquet files found for {symbol}")
    query = """
        SELECT ts, open, high, low, close, volume, quote_volume, is_closed
        FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
        ORDER BY ts
    """
    with duckdb.connect() as connection:
        frame = connection.execute(query, [[str(path) for path in files]]).fetch_df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates(subset=["ts"], keep="last").sort_values("ts")
    frame = frame[frame["is_closed"].fillna(True).astype(bool)].copy()
    frame = frame.set_index("ts")
    for column in ("open", "high", "low", "close", "volume", "quote_volume"):
        frame[column] = frame[column].astype("float64")
    return frame[["open", "high", "low", "close", "volume", "quote_volume"]]


def resample_ohlcv(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe == "15m":
        return frame.copy()
    rule = {"5m": "5min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1D"}[timeframe]
    resampled = frame.resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "quote_volume": "sum",
        }
    )
    return resampled.dropna(subset=["open", "high", "low", "close"])


def load_symbol_for_timeframe(symbol: str, timeframe: str) -> tuple[pd.DataFrame, str]:
    if symbol == "HYPE/USDT:USDT" and timeframe == "5m":
        return load_ohlcv(symbol, "5m"), "native_5m"
    base = load_ohlcv(symbol, "15m")
    if timeframe == "5m":
        return base, "15m_proxy_for_5m"
    return resample_ohlcv(base, timeframe), "native_15m" if timeframe == "15m" else f"resampled_15m_to_{timeframe}"


def rsi_wilder(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    relative_strength = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + relative_strength)
    rsi = rsi.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)
    return rsi


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    return true_range(frame).rolling(window, min_periods=window).mean()


def bollinger(frame: pd.DataFrame, window: int = 20, mult: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    basis = frame["close"].rolling(window, min_periods=window).mean()
    dev = frame["close"].rolling(window, min_periods=window).std(ddof=0) * mult
    return basis, basis + dev, basis - dev


def keltner(frame: pd.DataFrame, window: int = 20, mult: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    basis = frame["close"].ewm(span=window, adjust=False, min_periods=window).mean()
    width = atr(frame, window) * mult
    return basis, basis + width, basis - width


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = close.ewm(span=12, adjust=False, min_periods=26).mean() - close.ewm(
        span=26, adjust=False, min_periods=26
    ).mean()
    signal = line.ewm(span=9, adjust=False, min_periods=9).mean()
    return line, signal, line - signal


def adx(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = true_range(frame)
    plus_di = 100.0 * plus_dm.rolling(window, min_periods=window).sum() / tr.rolling(window, min_periods=window).sum()
    minus_di = 100.0 * minus_dm.rolling(window, min_periods=window).sum() / tr.rolling(window, min_periods=window).sum()
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.rolling(window, min_periods=window).mean()


def supertrend_direction(frame: pd.DataFrame, window: int = 10, factor: float = 3.0) -> pd.Series:
    atr_value = atr(frame, window)
    hl2 = (frame["high"] + frame["low"]) / 2.0
    upper = hl2 + factor * atr_value
    lower = hl2 - factor * atr_value
    direction = pd.Series(0, index=frame.index, dtype="int64")
    trend = 1
    final_upper = np.nan
    final_lower = np.nan
    previous_close = np.nan
    for ts in frame.index:
        close = float(frame.loc[ts, "close"])
        upper_value = upper.loc[ts]
        lower_value = lower.loc[ts]
        if pd.isna(upper_value) or pd.isna(lower_value):
            direction.loc[ts] = 0
            previous_close = close
            continue
        if pd.isna(final_upper) or upper_value < final_upper or previous_close > final_upper:
            final_upper = float(upper_value)
        if pd.isna(final_lower) or lower_value > final_lower or previous_close < final_lower:
            final_lower = float(lower_value)
        if trend < 0 and close > final_upper:
            trend = 1
        elif trend > 0 and close < final_lower:
            trend = -1
        direction.loc[ts] = trend
        previous_close = close
    return direction


def cross_above(left: pd.Series, right: pd.Series | float) -> pd.Series:
    rhs = right if isinstance(right, pd.Series) else pd.Series(float(right), index=left.index)
    return left.gt(rhs) & left.shift(1).le(rhs.shift(1))


def cross_below(left: pd.Series, right: pd.Series | float) -> pd.Series:
    rhs = right if isinstance(right, pd.Series) else pd.Series(float(right), index=left.index)
    return left.lt(rhs) & left.shift(1).ge(rhs.shift(1))


def signal_from_conditions(index: pd.Index, long: pd.Series | bool = False, short: pd.Series | bool = False) -> pd.Series:
    signal = pd.Series(0, index=index, dtype="int64")
    if isinstance(long, pd.Series):
        signal.loc[long.fillna(False)] = 1
    elif long:
        signal.loc[:] = 1
    if isinstance(short, pd.Series):
        signal.loc[short.fillna(False)] = -1
    elif short:
        signal.loc[:] = -1
    return signal


def rule_rsi_2065(frame: pd.DataFrame) -> RuleOutput:
    rsi = rsi_wilder(frame["close"], 14)
    low_min = frame["low"].rolling(14, min_periods=14).min()
    high_max = frame["high"].rolling(14, min_periods=14).max()
    stoch = 100.0 * (frame["close"] - low_min) / (high_max - low_min).replace(0.0, np.nan)
    ema200 = frame["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    signal = signal_from_conditions(
        frame.index,
        long=rsi.lt(20) & stoch.lt(25) & frame["close"].gt(ema200),
        short=rsi.gt(65) & stoch.gt(75) & frame["close"].lt(ema200),
    )
    return RuleOutput(signal=signal, stop_pct=0.04, take_pct=0.06)


def rule_vol_breakout(frame: pd.DataFrame) -> RuleOutput:
    _, upper, lower = keltner(frame, 20, 2.0)
    ema200 = frame["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    adx_value = adx(frame, 14)
    vol_ma = frame["volume"].rolling(20, min_periods=20).mean()
    atr_pct = (atr(frame, 14) * 2.0 / frame["close"]).clip(0.01, 0.10)
    signal = signal_from_conditions(
        frame.index,
        long=frame["close"].gt(upper) & frame["close"].gt(ema200) & adx_value.gt(20) & frame["volume"].gt(vol_ma),
        short=frame["close"].lt(lower) & frame["close"].lt(ema200) & adx_value.gt(20) & frame["volume"].gt(vol_ma),
    )
    return RuleOutput(signal=signal, stop_pct=atr_pct, take_pct=atr_pct * 2.0)


def rule_supertrend_ai(frame: pd.DataFrame) -> RuleOutput:
    direction = supertrend_direction(frame, 10, 3.0)
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[(direction == 1) & (direction.shift(1) != 1)] = 1
    signal.loc[(direction == -1) & (direction.shift(1) != -1)] = -1
    return RuleOutput(signal=signal)


def rule_bb_upper_short(frame: pd.DataFrame) -> RuleOutput:
    _, upper, _ = bollinger(frame, 20, 2.0)
    return RuleOutput(
        signal=signal_from_conditions(frame.index, short=frame["close"].gt(upper * 1.02)),
        stop_pct=0.08,
        take_pct=0.02,
    )


def rule_supertrend_long_only(frame: pd.DataFrame) -> RuleOutput:
    direction = supertrend_direction(frame, 10, 8.5)
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[(direction == 1) & (direction.shift(1) != 1)] = 1
    signal.loc[(direction == -1) & (direction.shift(1) == 1)] = 0
    return RuleOutput(signal=signal, exit_on_zero=True, flip=False)


def rule_penguin(frame: pd.DataFrame) -> RuleOutput:
    bb_basis, bb_upper, _ = bollinger(frame, 20, 2.0)
    _, kc_upper, _ = keltner(frame, 20, 2.0)
    diff = (bb_upper - kc_upper) / bb_basis
    fast = frame["close"].ewm(span=12, adjust=False, min_periods=12).mean()
    slow = frame["close"].ewm(span=26, adjust=False, min_periods=26).mean()
    thrust = frame["close"].ewm(span=2, adjust=False, min_periods=2).mean()
    signal = signal_from_conditions(
        frame.index,
        long=diff.gt(0) & fast.gt(slow) & thrust.gt(fast),
        short=diff.gt(0) & fast.lt(slow) & thrust.lt(fast),
    )
    return RuleOutput(signal=signal)


def rule_macd_zero(frame: pd.DataFrame) -> RuleOutput:
    _, signal_line, _ = macd(frame["close"])
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[cross_above(signal_line, 0.0)] = 1
    signal.loc[cross_below(signal_line, 0.0)] = 0
    return RuleOutput(signal=signal, exit_on_zero=True, flip=False)


def rule_cdc_macd(frame: pd.DataFrame) -> RuleOutput:
    ema12 = frame["close"].ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = frame["close"].ewm(span=26, adjust=False, min_periods=26).mean()
    return RuleOutput(signal=signal_from_conditions(frame.index, long=cross_above(ema12, ema26), short=cross_below(ema12, ema26)))


def rule_hash_momentum(frame: pd.DataFrame) -> RuleOutput:
    momentum = frame["close"] - frame["close"].shift(10)
    threshold = atr(frame, 14) * 1.5
    ema = frame["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    signal = signal_from_conditions(
        frame.index,
        long=momentum.gt(threshold) & momentum.diff().gt(0) & frame["close"].gt(ema),
        short=momentum.lt(-threshold) & momentum.diff().lt(0) & frame["close"].lt(ema),
    )
    return RuleOutput(signal=signal, stop_pct=0.022, take_pct=0.055)


def rule_moon(frame: pd.DataFrame) -> RuleOutput:
    reference = pd.Timestamp("2000-01-06 18:14:00", tz="UTC")
    age = ((frame.index - reference).total_seconds() / 86400.0) % 29.530588853
    age_series = pd.Series(age, index=frame.index)
    full = age_series.between(14.0, 15.5) & ~age_series.shift(1).between(14.0, 15.5).fillna(False)
    new = ((age_series <= 1.0) | (age_series >= 28.5)) & ~(
        (age_series.shift(1) <= 1.0) | (age_series.shift(1) >= 28.5)
    ).fillna(False)
    return RuleOutput(signal=signal_from_conditions(frame.index, long=full, short=new), stop_pct=0.08, take_pct=0.12)


def rule_ema_7_19(frame: pd.DataFrame) -> RuleOutput:
    ema7 = frame["close"].ewm(span=7, adjust=False, min_periods=7).mean()
    ema19 = frame["close"].ewm(span=19, adjust=False, min_periods=19).mean()
    return RuleOutput(signal=signal_from_conditions(frame.index, long=cross_above(ema7, ema19), short=cross_below(ema7, ema19)))


def rule_rsi_70_buy(frame: pd.DataFrame) -> RuleOutput:
    rsi = rsi_wilder(frame["close"], 14)
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[cross_above(rsi, 70.0)] = 1
    signal.loc[cross_below(rsi, 70.0)] = 0
    return RuleOutput(signal=signal, exit_on_zero=True, flip=False)


def rule_sma_rsi(frame: pd.DataFrame) -> RuleOutput:
    sma50 = frame["close"].rolling(50, min_periods=50).mean()
    sma200 = frame["close"].rolling(200, min_periods=200).mean()
    rsi_avg = rsi_wilder(frame["close"], 21).rolling(9, min_periods=9).mean()
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[frame["close"].gt(sma50) & frame["close"].gt(sma200) & rsi_avg.gt(57)] = 1
    signal.loc[frame["close"].lt(sma50) & rsi_avg.lt(57)] = 0
    return RuleOutput(signal=signal, exit_on_zero=True, flip=False)


def rule_pivot_supertrend(frame: pd.DataFrame) -> RuleOutput:
    direction = supertrend_direction(frame, 10, 3.0)
    ma = frame["close"].rolling(100, min_periods=100).mean()
    return RuleOutput(
        signal=signal_from_conditions(frame.index, long=(direction == 1) & frame["close"].gt(ma), short=(direction == -1) & frame["close"].lt(ma)),
        stop_pct=0.05,
    )


def rule_keltner_eth(frame: pd.DataFrame) -> RuleOutput:
    middle, upper, lower = keltner(frame, 20, 1.5)
    ema200 = frame["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[cross_above(frame["close"], upper) & frame["close"].gt(ema200)] = 1
    signal.loc[cross_below(frame["close"], middle)] = 0
    signal.loc[cross_below(frame["close"], lower) & frame["close"].lt(ema200)] = -1
    signal.loc[cross_above(frame["close"], middle)] = signal.loc[cross_above(frame["close"], middle)].where(
        signal.loc[cross_above(frame["close"], middle)] == 1, 0
    )
    return RuleOutput(signal=signal, exit_on_zero=True)


def rule_hash_supertrend(frame: pd.DataFrame) -> RuleOutput:
    direction = supertrend_direction(frame, 14, 3.0)
    return RuleOutput(signal=signal_from_conditions(frame.index, long=(direction == 1) & (direction.shift(1) != 1), short=(direction == -1) & (direction.shift(1) != -1)))


def rule_crypto_long_py(frame: pd.DataFrame) -> RuleOutput:
    _, upper, lower = bollinger(frame, 20, 2.0)
    rsi = rsi_wilder(frame["close"], 14)
    ema = frame["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    signal = pd.Series(0, index=frame.index, dtype="int64")
    signal.loc[frame["close"].lt(lower) & rsi.lt(35) & frame["close"].gt(ema)] = 1
    signal.loc[frame["close"].gt(upper) | rsi.gt(65)] = 0
    return RuleOutput(signal=signal, stop_pct=0.03, take_pct=0.05, exit_on_zero=True, flip=False)


def tsi(close: pd.Series, long: int = 25, short: int = 13) -> pd.Series:
    diff = close.diff()
    double_smoothed = diff.ewm(span=long, adjust=False, min_periods=long).mean().ewm(span=short, adjust=False, min_periods=short).mean()
    abs_double_smoothed = diff.abs().ewm(span=long, adjust=False, min_periods=long).mean().ewm(span=short, adjust=False, min_periods=short).mean()
    return 100.0 * double_smoothed / abs_double_smoothed.replace(0.0, np.nan)


def rule_oleg(frame: pd.DataFrame) -> RuleOutput:
    _, upper, lower = bollinger(frame, 20, 2.0)
    rsi = rsi_wilder(frame["close"], 14)
    tsi_line = tsi(frame["close"])
    tsi_signal = tsi_line.ewm(span=7, adjust=False, min_periods=7).mean()
    return RuleOutput(
        signal=signal_from_conditions(
            frame.index,
            long=frame["close"].lt(lower) & rsi.lt(35) & cross_above(tsi_line, tsi_signal),
            short=frame["close"].gt(upper) & rsi.gt(65) & cross_below(tsi_line, tsi_signal),
        ),
        stop_pct=0.04,
        take_pct=0.06,
    )


def rule_daily_time(frame: pd.DataFrame) -> RuleOutput:
    signal = pd.Series(0, index=frame.index, dtype="int64")
    for ts in frame.index:
        if ts.hour == 8 and ts.minute == 30:
            signal.loc[ts] = 1
        elif ts.hour == 8 and ts.minute == 0:
            signal.loc[ts] = 0
    return RuleOutput(signal=signal, exit_on_zero=True, flip=False)


def rule_qullamagi(frame: pd.DataFrame) -> RuleOutput:
    close = frame["close"]
    ma5 = close.ewm(span=5, adjust=False, min_periods=5).mean()
    ma15 = close.ewm(span=15, adjust=False, min_periods=15).mean()
    sma67 = close.rolling(67, min_periods=67).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    sma350 = close.rolling(350, min_periods=350).mean()
    high_box = frame["high"].rolling(20, min_periods=20).max().shift(1)
    low_box = frame["low"].rolling(20, min_periods=20).min().shift(1)
    vol_spike = frame["volume"].gt(frame["volume"].rolling(20, min_periods=20).mean() * 1.2)
    long_stack = (close > ma5) & (ma5 > ma15) & (ma15 > sma67) & (sma67 > sma200) & (sma200 > sma350)
    short_stack = (close < ma5) & (ma5 < ma15) & (ma15 < sma67) & (sma67 < sma200) & (sma200 < sma350)
    signal = signal_from_conditions(
        frame.index,
        long=long_stack & close.gt(high_box) & vol_spike,
        short=short_stack & close.lt(low_box) & vol_spike,
    )
    return RuleOutput(signal=signal, stop_pct=0.04, take_pct=0.08)


def rule_kalman(frame: pd.DataFrame) -> RuleOutput:
    close = frame["close"]
    estimate = pd.Series(index=frame.index, dtype="float64")
    gain = 0.18
    previous = np.nan
    for ts, value in close.items():
        previous = float(value) if pd.isna(previous) else previous + gain * (float(value) - previous)
        estimate.loc[ts] = previous
    mae = (close - estimate).abs().rolling(200, min_periods=200).mean()
    upper = estimate + mae * 2.0
    lower = estimate - mae * 2.0
    return RuleOutput(signal=signal_from_conditions(frame.index, long=cross_above(close, upper), short=cross_below(close, lower)))


RULES: dict[str, Callable[[pd.DataFrame], RuleOutput]] = {
    "rsi_2065": rule_rsi_2065,
    "vol_breakout": rule_vol_breakout,
    "supertrend_ai": rule_supertrend_ai,
    "bb_upper_short": rule_bb_upper_short,
    "supertrend_long_only": rule_supertrend_long_only,
    "penguin": rule_penguin,
    "macd_zero": rule_macd_zero,
    "cdc_macd": rule_cdc_macd,
    "hash_momentum": rule_hash_momentum,
    "moon": rule_moon,
    "ema_7_19": rule_ema_7_19,
    "rsi_70_buy": rule_rsi_70_buy,
    "sma_rsi": rule_sma_rsi,
    "pivot_supertrend": rule_pivot_supertrend,
    "keltner_eth": rule_keltner_eth,
    "hash_supertrend": rule_hash_supertrend,
    "crypto_long_py": rule_crypto_long_py,
    "oleg": rule_oleg,
    "daily_time": rule_daily_time,
    "qullamagi": rule_qullamagi,
    "kalman": rule_kalman,
}


SPECS = [
    StrategySpec(1, "Optimized BTC Mean Reversion (RSI 20/65)", "BTC", "15m", "medium", "rsi_2065", "公开说明较完整；已单独跑过一次。", 90),
    StrategySpec(2, "Volatility Breakout System [Fixed Risk]", "ETH", "1h", "medium", "vol_breakout", "公开说明完整但具体 ATR/TP/BE 参数未披露。", 730),
    StrategySpec(3, "SuperTrend AI Adaptive - Strategy [BTC]", "BTC", "4h", "low", "supertrend_ai", "页面只给自适应框架，近似为 ATR10 x3 SuperTrend。", 1460),
    StrategySpec(4, "BB Upper breakout Short +2% (dr Ziuber)", "SOL", "1h", "medium", "bb_upper_short", "只在搜索页拿到规则：超上轨 2% 做空，盈利 2% 平仓。", 730),
    StrategySpec(5, "SuperTrend STRATEGY", "BTC", "1d", "high", "supertrend_long_only", "公开说明清楚：Long-only SuperTrend，原文提 ATR10 x8.5。", 1460),
    StrategySpec(6, "Penguin Volatility State Strategy", "BTC", "1d", "medium", "penguin", "BB/KC 波动状态 + EMA 趋势动量，参数按说明默认化。", 1460),
    StrategySpec(7, "MACD Zero-Line Strategy (Long Only)", "BTC", "1d", "high", "macd_zero", "MACD signal 上穿 0 开多，下穿 0 平仓。", 1460),
    StrategySpec(8, "CDC BACKTEST (MACD) FIX AMOUNT $200k per trade", "BTC", "1d", "high", "cdc_macd", "EMA12/26 交叉；原 200k/400k 仓位等效 0.5x。", 1460, allocation=0.5),
    StrategySpec(9, "Hash Momentum Strategy", "BTC", "4h", "medium", "hash_momentum", "Momentum acceleration + ATR threshold + EMA filter，RR 约 2.5。", 1460),
    StrategySpec(10, "Moon Phases Long/Short Strategy", "BTC", "1h", "low", "moon", "月相逻辑按公开描述近似，非严格天文/源码复现。", 730),
    StrategySpec(11, "7/19 EMA Crypto strategy", "ETH", "30m", "high", "ema_7_19", "EMA7/19 交叉。", 365),
    StrategySpec(12, "RSI > 70 Buy / Exit on Cross Below 70", "BTC", "4h", "high", "rsi_70_buy", "RSI 上穿 70 买，跌破 70 平。", 1460),
    StrategySpec(13, "50 & 200 SMA + RSI Average Strategy", "ETH", "1d", "medium", "sma_rsi", "按原文：价在 SMA50/200 上且 RSI 平均 >57 开多。", 1460),
    StrategySpec(14, "Kadunagra-Pivot Point SuperTrend-trades analysis", "BTC", "4h", "low", "pivot_supertrend", "Pivot SuperTrend 近似为 SuperTrend + MA filter。", 1460),
    StrategySpec(15, "ETHUSDT 4H - Keltner Breakout", "ETH", "4h", "medium", "keltner_eth", "Keltner 突破 + EMA200。", 1460),
    StrategySpec(16, "Hash Supertrend [Hash Capital Research]", "SOL", "4h", "medium", "hash_supertrend", "ATR SuperTrend regime flip，参数默认化。", 1460),
    StrategySpec(17, "Crypto LONG PY", "SOL", "5m", "low", "crypto_long_py", "BB+RSI+EMA+Fib/NY session 描述不完整，近似只做 BB+RSI+EMA。", 60),
    StrategySpec(18, "Oleg_Aryukov_Strategy", "BTC", "15m", "medium", "oleg", "BB+RSI+TSI reversal。", 90),
    StrategySpec(19, "Options test Daily Long 08:30 Exit next day 08:00 UTC", "ETH", "5m", "high", "daily_time", "按 UTC 时间入场/退出；BTC 用 15m 代理无法精确 5m。", 60),
    StrategySpec(20, "Qullamagi EMA Breakout Autotrade", "ETH", "1h", "medium", "qullamagi", "MA stack + box breakout + volume spike。", 730),
    StrategySpec(21, "Kinetic Kalman Breakout", "ETH", "15m", "medium", "kalman", "Kalman filter + MAE bands 近似实现。", 90),
]


def _series_value(value: pd.Series | float | None, ts: pd.Timestamp, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, pd.Series):
        item = value.loc[ts]
        if pd.isna(item):
            return default
        return float(item)
    return float(value)


def backtest(frame: pd.DataFrame, rule: RuleOutput, allocation: float) -> tuple[pd.Series, pd.DataFrame]:
    equity = 1.0
    position = 0
    entry_price = np.nan
    entry_equity = np.nan
    entry_ts: pd.Timestamp | None = None
    equity_points: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict[str, object]] = []

    for ts, row in frame.iterrows():
        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        raw_signal = rule.signal.loc[ts]
        desired = 0 if pd.isna(raw_signal) else int(raw_signal)
        exited = False

        if position != 0 and entry_ts is not None and ts > entry_ts:
            stop_pct = _series_value(rule.stop_pct, ts)
            take_pct = _series_value(rule.take_pct, ts)
            exit_reason = None
            exit_price = np.nan
            if stop_pct is not None:
                stop_price = entry_price * (1.0 - stop_pct) if position > 0 else entry_price * (1.0 + stop_pct)
                if (position > 0 and low <= stop_price) or (position < 0 and high >= stop_price):
                    exit_reason = "stop"
                    exit_price = stop_price
            if exit_reason is None and take_pct is not None:
                take_price = entry_price * (1.0 + take_pct) if position > 0 else entry_price * (1.0 - take_pct)
                if (position > 0 and high >= take_price) or (position < 0 and low <= take_price):
                    exit_reason = "take"
                    exit_price = take_price
            if exit_reason is None and (
                (rule.exit_on_zero and desired == 0)
                or (rule.flip and desired != 0 and desired != position)
            ):
                exit_reason = "signal"
                exit_price = close

            if exit_reason is not None:
                gross_return = position * allocation * (exit_price / entry_price - 1.0)
                equity = entry_equity * (1.0 + gross_return) * (1.0 - FEE_RATE * allocation)
                net_return = (1.0 + gross_return) * (1.0 - FEE_RATE * allocation) ** 2 - 1.0
                trades.append(
                    {
                        "entry_ts": entry_ts.isoformat(),
                        "exit_ts": ts.isoformat(),
                        "direction": position,
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "exit_reason": exit_reason,
                        "net_return": float(net_return),
                    }
                )
                position = 0
                entry_price = np.nan
                entry_equity = np.nan
                entry_ts = None
                exited = True

        if position == 0 and not exited and desired != 0:
            position = desired
            entry_price = close
            equity *= 1.0 - FEE_RATE * allocation
            entry_equity = equity
            entry_ts = ts

        if position != 0:
            mark_return = position * allocation * (close / entry_price - 1.0)
            equity_points.append((ts, float(entry_equity * (1.0 + mark_return))))
        else:
            equity_points.append((ts, float(equity)))

    if position != 0 and entry_ts is not None:
        ts = frame.index[-1]
        close = float(frame["close"].iloc[-1])
        gross_return = position * allocation * (close / entry_price - 1.0)
        equity = entry_equity * (1.0 + gross_return) * (1.0 - FEE_RATE * allocation)
        trades.append(
            {
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "direction": position,
                "entry_price": float(entry_price),
                "exit_price": close,
                "exit_reason": "end",
                "net_return": float((1.0 + gross_return) * (1.0 - FEE_RATE * allocation) ** 2 - 1.0),
            }
        )
        equity_points[-1] = (ts, float(equity))

    equity_curve = pd.Series([value for _, value in equity_points], index=[ts for ts, _ in equity_points], name="equity")
    return equity_curve, pd.DataFrame(trades)


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min()) if not equity.empty else 0.0


def periods_per_year(index: pd.Index) -> float:
    if len(index) < 2:
        return 365.0
    seconds = pd.Series(index).diff().dropna().dt.total_seconds().median()
    return float(365 * 24 * 60 * 60 / seconds) if seconds and seconds > 0 else 365.0


def summarize(spec: StrategySpec, symbol: str, frame: pd.DataFrame, source: str, equity: pd.Series, trades: pd.DataFrame) -> dict[str, object]:
    returns = equity.pct_change().fillna(0.0)
    ppy = periods_per_year(equity.index)
    cumulative = float(equity.iloc[-1] - 1.0) if not equity.empty else 0.0
    years = len(equity) / ppy if ppy else 0.0
    annualized = float(equity.iloc[-1] ** (1 / years) - 1.0) if years > 0 and not equity.empty else 0.0
    volatility = float(returns.std(ddof=0) * np.sqrt(ppy))
    sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(ppy)) if returns.std(ddof=0) > 0 else 0.0
    wins = int(trades["net_return"].gt(0).sum()) if not trades.empty else 0
    gross_profit = float(trades.loc[trades["net_return"] > 0, "net_return"].sum()) if wins else 0.0
    gross_loss = float(-trades.loc[trades["net_return"] < 0, "net_return"].sum()) if not trades.empty else 0.0
    return {
        "rank": spec.rank,
        "strategy": spec.name,
        "logic_name": spec.logic_name,
        "rule_quality": spec.public_rule_quality,
        "symbol": symbol,
        "original_asset": spec.original_asset,
        "timeframe": spec.original_timeframe,
        "data_source": source,
        "start": equity.index[0].isoformat() if not equity.empty else None,
        "end": equity.index[-1].isoformat() if not equity.empty else None,
        "bars": int(len(frame)),
        "cumulative_return": cumulative,
        "annualized_return": annualized,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(equity),
        "trades": int(len(trades)),
        "long_trades": int(trades["direction"].eq(1).sum()) if not trades.empty else 0,
        "short_trades": int(trades["direction"].eq(-1).sum()) if not trades.empty else 0,
        "win_rate": float(wins / len(trades)) if len(trades) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else None,
        "notes": spec.notes,
    }


def main() -> None:
    symbols = ["BTC/USDT:USDT", "HYPE/USDT:USDT"]
    summaries: list[dict[str, object]] = []
    all_trades: list[pd.DataFrame] = []
    equity_columns: list[pd.Series] = []

    for spec in SPECS:
        for symbol in symbols:
            frame, source = load_symbol_for_timeframe(symbol, spec.original_timeframe)
            end = frame.index.max()
            start = end - pd.Timedelta(days=spec.window_days)
            sliced = frame[frame.index >= start].copy()
            rule = RULES[spec.logic_name](sliced)
            equity, trades = backtest(sliced, rule, allocation=spec.allocation)
            summaries.append(summarize(spec, symbol, sliced, source, equity, trades))
            if not trades.empty:
                tagged = trades.copy()
                tagged.insert(0, "symbol", symbol)
                tagged.insert(0, "strategy", spec.name)
                tagged.insert(0, "rank", spec.rank)
                all_trades.append(tagged)
            equity_columns.append(equity.rename(f"{spec.rank:02d}_{symbol.split('/')[0]}"))

    summary_frame = pd.DataFrame(summaries)
    trades_frame = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    equity_frame = pd.concat(equity_columns, axis=1, sort=False)
    payload = {
        "title": "Minara 21 TradingView strategies approximate BTC/HYPE backtest",
        "disclaimer": "Approximate reconstructions from public TradingView descriptions, not strict PineScript source-code replication.",
        "fee_rate_per_side": FEE_RATE,
        "symbols": symbols,
        "strategy_specs": [asdict(spec) for spec in SPECS],
        "summary": summaries,
    }
    REPORT_PREFIX.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_frame.to_csv(f"{REPORT_PREFIX}_summary.csv", index=False)
    trades_frame.to_csv(f"{REPORT_PREFIX}_trades.csv", index=False)
    equity_frame.to_csv(f"{REPORT_PREFIX}_equity.csv")
    print(summary_frame[["rank", "strategy", "symbol", "timeframe", "cumulative_return", "max_drawdown", "trades", "win_rate", "rule_quality"]].to_string(index=False))
    print(f"wrote {REPORT_PREFIX}.json")


if __name__ == "__main__":
    main()
