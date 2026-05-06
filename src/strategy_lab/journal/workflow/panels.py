from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.data.features import FeatureBuilder


@dataclass(frozen=True, slots=True)
class UniversePanels:
    factor: pd.DataFrame
    price: pd.DataFrame
    dollar_volume: pd.DataFrame | None = None
    funding_rate: pd.DataFrame | None = None
    liquidation_features: dict[str, pd.DataFrame] | None = None


@dataclass(frozen=True, slots=True)
class MultiFactorUniversePanels:
    factors: dict[str, pd.DataFrame]
    price: pd.DataFrame
    dollar_volume: pd.DataFrame | None = None
    funding_rate: pd.DataFrame | None = None
    liquidation_features: dict[str, pd.DataFrame] | None = None


def load_multi_factor_panels(
    *,
    builder: FeatureBuilder,
    exchange: str,
    symbols: list[str],
    market_type: MarketType,
    factor_names: list[str],
    benchmark_symbol: str | None,
    timeframe: str | None = None,
    liquidation_feature_names: list[str] | None = None,
) -> MultiFactorUniversePanels:
    factor_series: dict[str, dict[str, pd.Series]] = {name: {} for name in factor_names}
    price_series: dict[str, pd.Series] = {}
    dollar_volume_series: dict[str, pd.Series] = {}
    funding_series: dict[str, pd.Series] = {}
    liquidation_series: dict[str, dict[str, pd.Series]] = {
        "liq_spike_zscore": {},
        "liq_notional_vs_dollar_volume": {},
        "post_liq_oi_drop": {},
        "event_cooldown_flag": {},
    }

    for symbol in symbols:
        market = builder.load_symbol_frame(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            timeframe=timeframe,
            benchmark_symbol=benchmark_symbol,
        )
        if market.empty:
            raise ValueError(f"no normalized market data found for {symbol} on {exchange}/{market_type.value}")

        bundle = builder.build_symbol_features(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            timeframe=timeframe,
            benchmark_symbol=benchmark_symbol,
            factor_names=factor_names,
            market_frame=market,
        )
        missing = [name for name in factor_names if bundle.empty or name not in bundle.columns]
        if missing:
            raise ValueError(f"factors {missing} could not be computed for {symbol}")

        index = pd.to_datetime(market["ts"], utc=True)
        price_series[symbol] = pd.Series(market["close"].to_numpy(), index=index)
        dollar_volume_series[symbol] = pd.Series((market["close"] * market["volume"]).to_numpy(), index=index)
        if "funding_rate" in market.columns:
            funding_series[symbol] = pd.Series(market["funding_rate"].to_numpy(), index=index)

        if liquidation_feature_names:
            liquidation = builder.warehouse.load_liquidation_features(
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                timeframe=timeframe,
            )
            if not liquidation.empty:
                liq_index = pd.to_datetime(liquidation["ts"], utc=True)
                for feature_name in liquidation_feature_names:
                    if feature_name in liquidation.columns:
                        liquidation_series.setdefault(feature_name, {})
                        liquidation_series[feature_name][symbol] = pd.Series(liquidation[feature_name].to_numpy(), index=liq_index)

        factor_index = pd.to_datetime(bundle["ts"], utc=True)
        for name in factor_names:
            factor_series[name][symbol] = pd.Series(bundle[name].to_numpy(), index=factor_index)

    factor_panels = {name: pd.DataFrame(series).sort_index() for name, series in factor_series.items()}
    price_panel = pd.DataFrame(price_series).sort_index()
    dollar_volume_panel = pd.DataFrame(dollar_volume_series).sort_index() if dollar_volume_series else None
    funding_panel = pd.DataFrame(funding_series).sort_index() if funding_series else None
    liquidation_panels = {
        name: pd.DataFrame(series).sort_index()
        for name, series in liquidation_series.items()
        if series
    }

    aligned_index = price_panel.index
    for panel in factor_panels.values():
        aligned_index = aligned_index.intersection(panel.index)
    if dollar_volume_panel is not None:
        aligned_index = aligned_index.intersection(dollar_volume_panel.index)
    if funding_panel is not None:
        aligned_index = aligned_index.intersection(funding_panel.index)
    for panel in liquidation_panels.values():
        aligned_index = aligned_index.intersection(panel.index)

    factor_panels = {name: panel.loc[aligned_index] for name, panel in factor_panels.items()}
    price_panel = price_panel.loc[aligned_index]
    if dollar_volume_panel is not None:
        dollar_volume_panel = dollar_volume_panel.loc[aligned_index]
    if funding_panel is not None:
        funding_panel = funding_panel.loc[aligned_index]
    liquidation_panels = {name: panel.loc[aligned_index] for name, panel in liquidation_panels.items()}

    return MultiFactorUniversePanels(
        factors=factor_panels,
        price=price_panel,
        dollar_volume=dollar_volume_panel,
        funding_rate=funding_panel,
        liquidation_features=liquidation_panels or None,
    )


def load_universe_panels(
    *,
    builder: FeatureBuilder,
    exchange: str,
    symbols: list[str],
    market_type: MarketType,
    factor_name: str,
    benchmark_symbol: str | None,
    timeframe: str | None = None,
    liquidation_feature_names: list[str] | None = None,
) -> UniversePanels:
    multi = load_multi_factor_panels(
        builder=builder,
        exchange=exchange,
        symbols=symbols,
        market_type=market_type,
        timeframe=timeframe,
        factor_names=[factor_name],
        benchmark_symbol=benchmark_symbol,
        liquidation_feature_names=liquidation_feature_names,
    )
    return UniversePanels(
        factor=multi.factors[factor_name],
        price=multi.price,
        dollar_volume=multi.dollar_volume,
        funding_rate=multi.funding_rate,
        liquidation_features=multi.liquidation_features,
    )
