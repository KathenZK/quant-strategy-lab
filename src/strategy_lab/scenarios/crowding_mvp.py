from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe


@dataclass(frozen=True, slots=True)
class CrowdingMvpScenarioConfig:
    exchange: str = "binance"
    market_type: MarketType = MarketType.PERP
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
    start: str = "2024-02-01T00:00:00Z"
    periods: int = 240
    frequency: str = "1h"


def _split_perp_symbol(symbol: str) -> tuple[str, str]:
    base, quote = symbol.split("/", maxsplit=1)
    quote = quote.split(":", maxsplit=1)[0]
    return base.upper(), quote.upper()


def _scenario_close_series(symbol: str, periods: int) -> np.ndarray:
    if symbol.startswith("BTC/"):
        up_leg = np.linspace(30_000, 34_600, periods - 16)
        reversal_leg = np.linspace(up_leg[-1] - 80, up_leg[-1] - 1_000, 16)
        return np.concatenate([up_leg, reversal_leg])
    if symbol.startswith("ETH/"):
        down_leg = np.linspace(2_600, 2_050, periods - 16)
        reversal_leg = np.linspace(down_leg[-1] + 15, down_leg[-1] + 190, 16)
        return np.concatenate([down_leg, reversal_leg])
    base = np.linspace(95, 97, periods)
    noise = 1.8 * np.sin(np.arange(periods) / 4.0)
    return base + noise


def _ohlcv_frame(config: CrowdingMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    close = _scenario_close_series(symbol, config.periods)
    open_ = np.roll(close, 1)
    open_[0] = close[0] * 0.999
    high = np.maximum(open_, close) * 1.0025
    low = np.minimum(open_, close) * 0.9975

    if symbol.startswith("BTC/"):
        volume = 4_000_000 + np.linspace(0, 700_000, config.periods)
    elif symbol.startswith("ETH/"):
        volume = 3_300_000 + np.linspace(0, 500_000, config.periods)
    else:
        volume = 1_600_000 + 100_000 * np.sin(np.arange(config.periods) / 5.0)

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


def _funding_frame(config: CrowdingMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    if symbol.startswith("BTC/"):
        funding = 0.0003 + 0.000012 * x
    elif symbol.startswith("ETH/"):
        funding = -0.0003 - 0.000012 * x
    else:
        funding = 0.00002 * np.sin(x / 3.0)
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


def _open_interest_frame(config: CrowdingMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    if symbol.startswith("BTC/"):
        values = 18_000 + 160 * x
    elif symbol.startswith("ETH/"):
        values = 16_000 + 150 * x
    else:
        values = 10_000 + 5 * np.sin(x / 4.0)
    base_asset, quote_asset = _split_perp_symbol(symbol)
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": [config.exchange] * config.periods,
            "symbol": [symbol] * config.periods,
            "market_type": [config.market_type.value] * config.periods,
            "base_asset": [base_asset] * config.periods,
            "quote_asset": [quote_asset] * config.periods,
            "open_interest": values,
            "open_interest_value": values,
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _basis_frame(config: CrowdingMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    if symbol.startswith("BTC/"):
        basis = 6.0 + 0.16 * x
    elif symbol.startswith("ETH/"):
        basis = -6.0 - 0.16 * x
    else:
        basis = 0.15 * np.sin(x / 4.0)
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
            "annualized_basis": basis / 18.0,
            "futures_price": futures_price,
            "index_price": index_price,
            "mark_price": futures_price - basis * 0.1,
            "premium_index": basis / np.maximum(index_price, 1.0),
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _liquidation_frame(config: CrowdingMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    base_asset, quote_asset = _split_perp_symbol(symbol)
    if symbol.startswith("BTC/"):
        timestamps = pd.to_datetime(["2024-02-09T18:10:00Z", "2024-02-09T18:25:00Z"])
        side = ["sell", "sell"]
        notional = [180_000.0, 220_000.0]
    elif symbol.startswith("ETH/"):
        timestamps = pd.to_datetime(["2024-02-09T19:10:00Z", "2024-02-09T19:40:00Z"])
        side = ["buy", "buy"]
        notional = [120_000.0, 150_000.0]
    else:
        timestamps = pd.to_datetime(["2024-02-06T04:20:00Z"])
        side = ["sell"]
        notional = [1_500.0]

    prices = [float(_scenario_close_series(symbol, config.periods)[min(i * 12 + 120, config.periods - 1)]) for i in range(len(timestamps))]
    size = [n / p for n, p in zip(notional, prices, strict=True)]
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
            "price": prices,
            "size": size,
            "notional": notional,
            "source": ["scenario_seed"] * len(timestamps),
            "date": [item.date().isoformat() for item in timestamps],
        }
    )


def seed_crowding_mvp_data(
    layout: DataLakeLayout,
    *,
    scenario_config: CrowdingMvpScenarioConfig | None = None,
) -> dict[str, dict[str, str]]:
    config = scenario_config or CrowdingMvpScenarioConfig()
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
