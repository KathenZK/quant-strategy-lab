import pandas as pd

from strategy_lab.ingest import (
    BinanceSpotUniverseConfig,
    candidate_symbols_from_markets,
    filter_symbols_by_ohlcv,
)


def test_binance_spot_universe_filters_non_tradeable_markets() -> None:
    markets = {
        "BTC/USDT": {"base": "BTC", "quote": "USDT", "spot": True, "active": True},
        "ETH/BTC": {"base": "ETH", "quote": "BTC", "spot": True, "active": True},
        "USDC/USDT": {"base": "USDC", "quote": "USDT", "spot": True, "active": True},
        "BTCUP/USDT": {"base": "BTCUP", "quote": "USDT", "spot": True, "active": True},
        "JUP/USDT": {"base": "JUP", "quote": "USDT", "spot": True, "active": True},
        "OLD/USDT": {"base": "OLD", "quote": "USDT", "spot": True, "active": False},
        "BTC/USDT:USDT": {"base": "BTC", "quote": "USDT", "spot": False, "active": True, "type": "swap"},
    }

    symbols = candidate_symbols_from_markets(markets)

    assert symbols == ["BTC/USDT", "JUP/USDT"]


def test_binance_spot_universe_filters_local_history_and_liquidity() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    ohlcv = pd.DataFrame(
        {
            "ts": list(index) * 3,
            "symbol": ["BTC/USDT"] * 5 + ["THIN/USDT"] * 5 + ["NEW/USDT"] * 5,
            "close": [100.0] * 5 + [1.0] * 5 + [10.0] * 5,
            "volume": [20_000.0] * 5 + [100.0] * 5 + [100_000.0] * 5,
        }
    )
    config = BinanceSpotUniverseConfig(
        min_avg_dollar_volume=1_000_000.0,
        avg_volume_window=3,
        min_history_bars=5,
    )

    symbols = filter_symbols_by_ohlcv(
        ohlcv.iloc[:-2],
        config=config,
        candidate_symbols=["BTC/USDT", "THIN/USDT", "NEW/USDT"],
    )

    assert symbols == ["BTC/USDT"]
