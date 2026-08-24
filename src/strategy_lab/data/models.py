from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MarketType(StrEnum):
    SPOT = "spot"
    PERP = "perp"
    FUTURES = "futures"
    EQUITY = "equity"


class DatasetKind(StrEnum):
    OHLCV = "ohlcv"
    FUNDING_RATES = "funding_rates"
    OPEN_INTEREST = "open_interest"
    BASIS = "basis_or_premium"
    LIQUIDATIONS = "liquidations"
    TICKER = "ticker_or_top_of_book"
    ASSET_METADATA = "asset_metadata"
    ONCHAIN = "onchain_metrics"
    SQUARE_POSTS = "square_posts"


@dataclass(frozen=True, slots=True)
class InstrumentId:
    exchange: str
    symbol: str
    market_type: MarketType
    base_asset: str
    quote_asset: str


@dataclass(frozen=True, slots=True)
class OHLCVRecord:
    """One candle keyed by its UTC open timestamp.

    ``is_closed`` is the sole authority for whether the candle may be used as a
    completed bar; timestamp position must never be used to guess closure.
    """

    ts: datetime
    instrument: InstrumentId
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    vwap: float
    is_closed: bool
    source: str


@dataclass(frozen=True, slots=True)
class FundingRateRecord:
    ts: datetime
    instrument: InstrumentId
    funding_rate: float
    next_funding_ts: datetime | None
    source: str


@dataclass(frozen=True, slots=True)
class OpenInterestRecord:
    ts: datetime
    instrument: InstrumentId
    open_interest: float
    open_interest_value: float | None
    source: str


@dataclass(frozen=True, slots=True)
class BasisPremiumRecord:
    ts: datetime
    instrument: InstrumentId
    basis: float | None
    basis_rate: float | None
    annualized_basis: float | None
    futures_price: float | None
    index_price: float | None
    mark_price: float | None
    premium_index: float | None
    source: str


@dataclass(frozen=True, slots=True)
class LiquidationRecord:
    ts: datetime
    instrument: InstrumentId
    side: str
    liquidation_side: str
    price: float
    size: float
    notional: float
    source: str


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    kind: DatasetKind
    required_columns: tuple[str, ...]
    partition_columns: tuple[str, ...]


def dataset_specs() -> dict[DatasetKind, DatasetSpec]:
    return {
        DatasetKind.OHLCV: DatasetSpec(
            kind=DatasetKind.OHLCV,
            required_columns=(
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "timeframe",
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
            ),
            partition_columns=(
                "exchange",
                "market_type",
                "symbol",
                "timeframe",
                "date",
            ),
        ),
        DatasetKind.FUNDING_RATES: DatasetSpec(
            kind=DatasetKind.FUNDING_RATES,
            required_columns=(
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "funding_rate",
                "source",
            ),
            partition_columns=("exchange", "market_type", "symbol", "date"),
        ),
        DatasetKind.OPEN_INTEREST: DatasetSpec(
            kind=DatasetKind.OPEN_INTEREST,
            required_columns=(
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "open_interest",
                "source",
            ),
            partition_columns=(
                "exchange",
                "market_type",
                "symbol",
                "timeframe",
                "date",
            ),
        ),
        DatasetKind.BASIS: DatasetSpec(
            kind=DatasetKind.BASIS,
            required_columns=(
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "basis",
                "source",
            ),
            partition_columns=(
                "exchange",
                "market_type",
                "symbol",
                "timeframe",
                "date",
            ),
        ),
        DatasetKind.LIQUIDATIONS: DatasetSpec(
            kind=DatasetKind.LIQUIDATIONS,
            required_columns=(
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "side",
                "size",
                "price",
                "source",
            ),
            partition_columns=("exchange", "market_type", "symbol", "date"),
        ),
        DatasetKind.TICKER: DatasetSpec(
            kind=DatasetKind.TICKER,
            required_columns=(
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "bid",
                "ask",
                "source",
            ),
            partition_columns=("exchange", "market_type", "symbol", "date"),
        ),
        DatasetKind.ASSET_METADATA: DatasetSpec(
            kind=DatasetKind.ASSET_METADATA,
            required_columns=(
                "exchange",
                "symbol",
                "market_type",
                "base_asset",
                "quote_asset",
                "status",
                "source",
            ),
            partition_columns=("exchange", "market_type"),
        ),
        DatasetKind.ONCHAIN: DatasetSpec(
            kind=DatasetKind.ONCHAIN,
            required_columns=("ts", "chain", "metric_name", "value", "source"),
            partition_columns=("chain", "metric_name", "date"),
        ),
        DatasetKind.SQUARE_POSTS: DatasetSpec(
            kind=DatasetKind.SQUARE_POSTS,
            required_columns=("ts", "post_id", "author_name", "content", "source"),
            partition_columns=("source", "date"),
        ),
    }
