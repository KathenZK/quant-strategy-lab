from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe


@dataclass(frozen=True, slots=True)
class SharedComparisonMvpScenarioConfig:
    exchange: str = "binance"
    market_type: MarketType = MarketType.PERP
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
    start: str = "2024-03-01T00:00:00Z"
    periods: int = 320
    frequency: str = "1h"


def _split_perp_symbol(symbol: str) -> tuple[str, str]:
    base, quote = symbol.split("/", maxsplit=1)
    quote = quote.split(":", maxsplit=1)[0]
    return base.upper(), quote.upper()


def _shared_close_series(symbol: str, periods: int) -> np.ndarray:
    x = np.arange(periods, dtype=float)
    final_phase = 16
    trend_phase = int(periods * 0.55)
    crowding_phase = periods - trend_phase - final_phase

    if symbol.startswith("BTC/"):
        phase1 = np.linspace(30_000, 35_200, trend_phase)
        phase2 = np.linspace(phase1[-1] + 25, phase1[-1] + 3_100, crowding_phase)
        phase3 = np.linspace(phase2[-1] - 2, phase2[-1] - 35, final_phase)
        noise = 80 * np.sin(x / 9.0)
        return np.concatenate([phase1, phase2, phase3]) + noise

    if symbol.startswith("ETH/"):
        phase1 = np.linspace(2_700, 2_160, trend_phase)
        phase2 = np.linspace(phase1[-1] - 12, phase1[-1] - 430, crowding_phase)
        phase3 = np.linspace(phase2[-1] + 2, phase2[-1] + 35, final_phase)
        noise = 14 * np.sin(x / 8.0)
        return np.concatenate([phase1, phase2, phase3]) + noise

    base = np.linspace(95, 100, periods)
    noise = 2.8 * np.sin(x / 5.0)
    return base + noise


def _ohlcv_frame(config: SharedComparisonMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    close = _shared_close_series(symbol, config.periods)
    open_ = np.roll(close, 1)
    open_[0] = close[0] * 0.999
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998

    if symbol.startswith("BTC/"):
        volume = 4_200_000 + np.linspace(0, 900_000, config.periods)
    elif symbol.startswith("ETH/"):
        volume = 3_400_000 + np.linspace(0, 600_000, config.periods)
    else:
        volume = 1_800_000 + 140_000 * np.sin(np.arange(config.periods) / 7.0)

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


def _funding_frame(config: SharedComparisonMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    x = np.arange(config.periods, dtype=float)
    final_phase = 16
    trend_phase = int(config.periods * 0.55)
    crowding_phase = config.periods - trend_phase - final_phase

    if symbol.startswith("BTC/"):
        phase1 = np.linspace(0.0001, 0.00035, trend_phase)
        phase2 = np.linspace(phase1[-1], 0.0022, crowding_phase)
        phase3 = np.linspace(phase2[-1], 0.0027, final_phase)
        funding = np.concatenate([phase1, phase2, phase3])
    elif symbol.startswith("ETH/"):
        phase1 = np.linspace(-0.0001, -0.00035, trend_phase)
        phase2 = np.linspace(phase1[-1], -0.0021, crowding_phase)
        phase3 = np.linspace(phase2[-1], -0.0026, final_phase)
        funding = np.concatenate([phase1, phase2, phase3])
    else:
        funding = 0.00002 * np.sin(x / 4.0)

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


def _open_interest_frame(config: SharedComparisonMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    final_phase = 16
    trend_phase = int(config.periods * 0.55)
    crowding_phase = config.periods - trend_phase - final_phase

    if symbol.startswith("BTC/"):
        phase1 = np.linspace(15_000, 27_000, trend_phase)
        phase2 = np.linspace(phase1[-1], 41_000, crowding_phase)
        phase3 = np.linspace(phase2[-1], 43_500, final_phase)
        open_interest = np.concatenate([phase1, phase2, phase3])
    elif symbol.startswith("ETH/"):
        phase1 = np.linspace(14_000, 25_000, trend_phase)
        phase2 = np.linspace(phase1[-1], 38_000, crowding_phase)
        phase3 = np.linspace(phase2[-1], 41_500, final_phase)
        open_interest = np.concatenate([phase1, phase2, phase3])
    else:
        open_interest = 10_000 + 100 * np.sin(np.arange(config.periods) / 6.0)

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


def _basis_frame(config: SharedComparisonMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    index = pd.date_range(config.start, periods=config.periods, freq=config.frequency, tz="UTC")
    final_phase = 16
    trend_phase = int(config.periods * 0.55)
    crowding_phase = config.periods - trend_phase - final_phase

    if symbol.startswith("BTC/"):
        phase1 = np.linspace(5.0, 12.0, trend_phase)
        phase2 = np.linspace(phase1[-1], 28.0, crowding_phase)
        phase3 = np.linspace(phase2[-1], 34.0, final_phase)
        basis = np.concatenate([phase1, phase2, phase3])
    elif symbol.startswith("ETH/"):
        phase1 = np.linspace(-5.0, -12.0, trend_phase)
        phase2 = np.linspace(phase1[-1], -26.0, crowding_phase)
        phase3 = np.linspace(phase2[-1], -32.0, final_phase)
        basis = np.concatenate([phase1, phase2, phase3])
    else:
        basis = 0.2 * np.sin(np.arange(config.periods) / 4.0)

    base_asset, quote_asset = _split_perp_symbol(symbol)
    index_price = _shared_close_series(symbol, config.periods)
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
            "annualized_basis": basis / 16.0,
            "futures_price": futures_price,
            "index_price": index_price,
            "mark_price": futures_price - basis * 0.1,
            "premium_index": basis / np.maximum(index_price, 1.0),
            "source": ["scenario_seed"] * config.periods,
            "date": [item.date().isoformat() for item in index],
        }
    )


def _liquidation_frame(config: SharedComparisonMvpScenarioConfig, symbol: str) -> pd.DataFrame:
    base_asset, quote_asset = _split_perp_symbol(symbol)
    if symbol.startswith("BTC/"):
        timestamps = pd.to_datetime(
            [
                "2024-03-11T10:10:00Z",
                "2024-03-11T10:25:00Z",
                "2024-03-12T03:10:00Z",
            ]
        )
        side = ["sell", "sell", "buy"]
        notional = [160_000.0, 210_000.0, 24_000.0]
    elif symbol.startswith("ETH/"):
        timestamps = pd.to_datetime(
            [
                "2024-03-11T14:20:00Z",
                "2024-03-11T14:45:00Z",
                "2024-03-12T02:20:00Z",
            ]
        )
        side = ["buy", "buy", "sell"]
        notional = [130_000.0, 170_000.0, 18_000.0]
    else:
        timestamps = pd.to_datetime(["2024-03-08T05:00:00Z"])
        side = ["sell"]
        notional = [1_800.0]

    prices = [float(_shared_close_series(symbol, config.periods)[min(220 + i * 8, config.periods - 1)]) for i in range(len(timestamps))]
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


def seed_shared_comparison_mvp_data(
    layout: DataLakeLayout,
    *,
    scenario_config: SharedComparisonMvpScenarioConfig | None = None,
) -> dict[str, dict[str, str]]:
    config = scenario_config or SharedComparisonMvpScenarioConfig()
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
