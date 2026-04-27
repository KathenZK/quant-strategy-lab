from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe


@dataclass(frozen=True, slots=True)
class TrendMvpScenarioConfig:
    exchange: str = "binance"
    market_type: MarketType = MarketType.PERP
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
    start: str = "2024-01-01T00:00:00Z"
    periods: int = 240
    frequency: str = "1h"


def _split_perp_symbol(symbol: str) -> tuple[str, str]:
    base, quote = symbol.split("/", maxsplit=1)
    quote = quote.split(":", maxsplit=1)[0]
    return base.upper(), quote.upper()


def _scenario_close_series(symbol: str, periods: int) -> np.ndarray:
    x = np.arange(periods, dtype=float)
    if symbol.startswith("BTC/"):
        return 30_000 + 22 * x + 120 * np.sin(x / 12.0)
    if symbol.startswith("ETH/"):
        return 2_400 - 3.8 * x + 18 * np.sin(x / 9.0)
    return 95 + 0.15 * x + 4.5 * np.sin(x / 4.0)


def _ohlcv_frame(config: TrendMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    close = _scenario_close_series(symbol, config.periods)
    open_ = np.roll(close, 1)
    open_[0] = close[0] * 0.998
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998

    if symbol.startswith("BTC/"):
        volume = 3_500_000 + np.linspace(0, 600_000, config.periods)
    elif symbol.startswith("ETH/"):
        volume = 2_900_000 + np.linspace(0, 400_000, config.periods)
    else:
        volume = 1_700_000 + 120_000 * np.sin(np.arange(config.periods) / 6.0)

    base_asset, quote_asset = _split_perp_symbol(symbol)
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": [config.exchange] * config.periods,
            "symbol": [symbol] * config.periods,
            "market_type": [config.market_type.value] * config.periods,
            "base_asset": [base_asset] * config.periods,
            "quote_asset": [quote_asset] * config.periods,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _funding_frame(config: TrendMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    if symbol.startswith("BTC/"):
        funding = 0.00015 + 0.0000035 * x
    elif symbol.startswith("ETH/"):
        funding = -0.00012 - 0.0000028 * x
    else:
        funding = 0.00045 + 0.00001 * np.sin(x / 5.0)
    base_asset, quote_asset = _split_perp_symbol(symbol)
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": [config.exchange] * config.periods,
            "symbol": [symbol] * config.periods,
            "market_type": [config.market_type.value] * config.periods,
            "base_asset": [base_asset] * config.periods,
            "quote_asset": [quote_asset] * config.periods,
            "funding_rate": funding,
            "next_funding_ts": index + pd.Timedelta(hours=8),
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _open_interest_frame(config: TrendMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    if symbol.startswith("BTC/"):
        open_interest = 15_000 + 145 * x
    elif symbol.startswith("ETH/"):
        open_interest = 18_000 + 120 * x
    else:
        open_interest = 9_000 - 6 * x + 50 * np.sin(x / 7.0)
    base_asset, quote_asset = _split_perp_symbol(symbol)
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": [config.exchange] * config.periods,
            "symbol": [symbol] * config.periods,
            "market_type": [config.market_type.value] * config.periods,
            "base_asset": [base_asset] * config.periods,
            "quote_asset": [quote_asset] * config.periods,
            "open_interest": open_interest,
            "open_interest_value": open_interest,
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _basis_frame(config: TrendMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    if symbol.startswith("BTC/"):
        basis = 8.0 + 0.12 * x + 0.4 * np.sin(x / 10.0)
    elif symbol.startswith("ETH/"):
        basis = -6.0 - 0.10 * x + 0.35 * np.sin(x / 9.0)
    else:
        basis = 1.0 + 0.05 * np.sin(x / 3.0)
    base_asset, quote_asset = _split_perp_symbol(symbol)
    index_price = _scenario_close_series(symbol, config.periods)
    futures_price = index_price + basis
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": [config.exchange] * config.periods,
            "symbol": [symbol] * config.periods,
            "market_type": [config.market_type.value] * config.periods,
            "base_asset": [base_asset] * config.periods,
            "quote_asset": [quote_asset] * config.periods,
            "basis": basis,
            "basis_rate": basis / np.maximum(index_price, 1.0),
            "annualized_basis": basis / 20.0,
            "futures_price": futures_price,
            "index_price": index_price,
            "mark_price": futures_price - basis * 0.1,
            "premium_index": basis / np.maximum(index_price, 1.0),
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _liquidation_frame(config: TrendMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    base_asset, quote_asset = _split_perp_symbol(symbol)
    if symbol.startswith("BTC/"):
        timestamps = pd.to_datetime(
            [
                "2024-01-05T12:10:00Z",
                "2024-01-05T12:20:00Z",
                "2024-01-07T03:15:00Z",
            ]
        )
        side = ["sell", "sell", "buy"]
        notional = [150_000.0, 190_000.0, 8_000.0]
    elif symbol.startswith("ETH/"):
        timestamps = pd.to_datetime(
            [
                "2024-01-06T08:15:00Z",
                "2024-01-06T08:35:00Z",
                "2024-01-08T11:00:00Z",
            ]
        )
        side = ["buy", "buy", "sell"]
        notional = [90_000.0, 110_000.0, 5_000.0]
    else:
        timestamps = pd.to_datetime(["2024-01-04T04:20:00Z"])
        side = ["sell"]
        notional = [1_200.0]

    price = [float(_scenario_close_series(symbol, config.periods)[min(i * 12, config.periods - 1)]) for i in range(len(timestamps))]
    size = [n / p for n, p in zip(notional, price, strict=True)]
    return pd.DataFrame(
        {
            "ts": timestamps,
            "exchange": [config.exchange] * len(timestamps),
            "symbol": [symbol] * len(timestamps),
            "market_type": [config.market_type.value] * len(timestamps),
            "base_asset": [base_asset] * len(timestamps),
            "quote_asset": [quote_asset] * len(timestamps),
            "side": side,
            "liquidation_side": ["long" if item == "sell" else "short" for item in side],
            "price": price,
            "size": size,
            "notional": notional,
            "source": ["scenario_seed"] * len(timestamps),
            "date": [item.date().isoformat() for item in timestamps],
        }
    )


def seed_trend_mvp_data(
    layout: DataLakeLayout,
    *,
    scenario_config: TrendMvpScenarioConfig | None = None,
) -> dict[str, dict[str, str]]:
    config = scenario_config or TrendMvpScenarioConfig()
    layout.ensure_directories()
    written: dict[str, dict[str, str]] = {}

    for symbol in config.symbols:
        datasets = {
            DatasetKind.OHLCV: _ohlcv_frame(config, symbol),
            DatasetKind.FUNDING_RATES: _funding_frame(config, symbol),
            DatasetKind.OPEN_INTEREST: _open_interest_frame(config, symbol),
            DatasetKind.BASIS: _basis_frame(config, symbol),
            DatasetKind.LIQUIDATIONS: _liquidation_frame(config, symbol),
        }
        symbol_paths: dict[str, str] = {}
        for kind, frame in datasets.items():
            path = write_dataframe(
                frame,
                layout=layout,
                layer="normalized",
                kind=kind,
                exchange=config.exchange,
                market_type=config.market_type,
                symbol=symbol,
                partition_date=pd.to_datetime(frame["ts"], utc=True).max().date(),
            )
            symbol_paths[kind.value] = str(path)
        written[symbol] = symbol_paths
    return written
