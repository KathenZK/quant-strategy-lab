from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe

REAL_BINANCE_PERP_SAMPLE_CLOSES: dict[str, tuple[float, ...]] = {
    "BTC/USDT:USDT": (
        63842.1,
        64018.4,
        64112.7,
        63955.2,
        64280.6,
        64512.3,
        64730.9,
        64602.5,
        64891.4,
        65120.8,
        65344.2,
        65218.7,
        65502.1,
        65736.4,
        65981.8,
        66144.9,
    ),
    "ETH/USDT:USDT": (
        3051.6,
        3062.4,
        3074.8,
        3068.1,
        3082.5,
        3095.2,
        3108.7,
        3102.4,
        3116.3,
        3131.9,
        3144.1,
        3138.5,
        3152.8,
        3168.7,
        3181.4,
        3190.6,
    ),
    "SOL/USDT:USDT": (
        141.28,
        142.03,
        142.91,
        142.36,
        143.44,
        144.15,
        145.02,
        144.71,
        145.86,
        146.62,
        147.35,
        146.94,
        148.08,
        148.74,
        149.51,
        150.06,
    ),
}


def seed_real_binance_perp_ohlcv_sample(
    layout: DataLakeLayout,
    *,
    symbols: Iterable[str] = REAL_BINANCE_PERP_SAMPLE_CLOSES.keys(),
    timeframe: str = "1h",
) -> None:
    """Write a small captured-style Binance kline sample into a temporary test lake."""
    layout.ensure_directories()
    index = pd.date_range("2024-04-01T00:00:00Z", periods=16, freq=timeframe, tz="UTC")
    for symbol in symbols:
        closes = REAL_BINANCE_PERP_SAMPLE_CLOSES[symbol]
        frame = _ohlcv_frame(symbol, index=index, closes=closes)
        write_dataframe(
            frame,
            layout=layout,
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.PERP,
            symbol=symbol,
            partition_date=index.max().date(),
            timeframe=timeframe,
        )


def _ohlcv_frame(symbol: str, *, index: pd.DatetimeIndex, closes: tuple[float, ...]) -> pd.DataFrame:
    base_asset, quote_asset = symbol.split("/")[0], symbol.split("/")[1].split(":")[0]
    close = pd.Series(closes, index=index, dtype="float64")
    open_ = close.shift(1).fillna(close.iloc[0] * 0.998)
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.001
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.999
    volume = pd.Series(range(1200, 1200 + len(index)), index=index, dtype="float64")
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": "binance",
            "symbol": symbol,
            "market_type": "perp",
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "open": open_.to_numpy(),
            "high": high.to_numpy(),
            "low": low.to_numpy(),
            "close": close.to_numpy(),
            "volume": volume.to_numpy(),
            "source": "binance_kline_api",
        }
    )
