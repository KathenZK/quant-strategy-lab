from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signal_lab.data import MarketType
from signal_lab.features import FeatureBuilder


@dataclass(frozen=True, slots=True)
class UniversePanels:
    factor: pd.DataFrame
    price: pd.DataFrame
    dollar_volume: pd.DataFrame | None = None
    funding_rate: pd.DataFrame | None = None


def load_universe_panels(
    *,
    builder: FeatureBuilder,
    exchange: str,
    symbols: list[str],
    market_type: MarketType,
    factor_name: str,
    benchmark_symbol: str | None,
) -> UniversePanels:
    factor_series: dict[str, pd.Series] = {}
    price_series: dict[str, pd.Series] = {}
    dollar_volume_series: dict[str, pd.Series] = {}
    funding_series: dict[str, pd.Series] = {}

    for symbol in symbols:
        market = builder.load_symbol_frame(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            benchmark_symbol=benchmark_symbol,
        )
        if market.empty:
            raise ValueError(f"no normalized market data found for {symbol} on {exchange}/{market_type.value}")

        bundle = builder.build_symbol_features(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            benchmark_symbol=benchmark_symbol,
            factor_names=[factor_name],
        )
        if bundle.empty or factor_name not in bundle.columns:
            raise ValueError(f"factor {factor_name} could not be computed for {symbol}")

        index = pd.to_datetime(market["ts"], utc=True)
        price_series[symbol] = pd.Series(market["close"].to_numpy(), index=index)
        dollar_volume_series[symbol] = pd.Series((market["close"] * market["volume"]).to_numpy(), index=index)
        if "funding_rate" in market.columns:
            funding_series[symbol] = pd.Series(market["funding_rate"].to_numpy(), index=index)

        factor_index = pd.to_datetime(bundle["ts"], utc=True)
        factor_series[symbol] = pd.Series(bundle[factor_name].to_numpy(), index=factor_index)

    factor_panel = pd.DataFrame(factor_series).sort_index()
    price_panel = pd.DataFrame(price_series).sort_index()
    dollar_volume_panel = pd.DataFrame(dollar_volume_series).sort_index() if dollar_volume_series else None
    funding_panel = pd.DataFrame(funding_series).sort_index() if funding_series else None

    aligned_index = factor_panel.index.intersection(price_panel.index)
    if dollar_volume_panel is not None:
        aligned_index = aligned_index.intersection(dollar_volume_panel.index)
    if funding_panel is not None:
        aligned_index = aligned_index.intersection(funding_panel.index)

    factor_panel = factor_panel.loc[aligned_index]
    price_panel = price_panel.loc[aligned_index]
    if dollar_volume_panel is not None:
        dollar_volume_panel = dollar_volume_panel.loc[aligned_index]
    if funding_panel is not None:
        funding_panel = funding_panel.loc[aligned_index]

    return UniversePanels(
        factor=factor_panel,
        price=price_panel,
        dollar_volume=dollar_volume_panel,
        funding_rate=funding_panel,
    )
