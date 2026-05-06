from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd

from strategy_lab.data import DatasetKind, DuckDBWarehouse, MarketType


STABLECOIN_BASES = (
    "BUSD",
    "DAI",
    "FDUSD",
    "FRAX",
    "GUSD",
    "LUSD",
    "PYUSD",
    "SUSD",
    "TUSD",
    "USDC",
    "USDD",
    "USDE",
    "USDP",
    "USD1",
    "USDJ",
    "USDS",
    "UST",
    "USTC",
)

FIAT_BASES = ("AUD", "BRL", "EUR", "GBP", "TRY", "UAH", "USD", "ZAR")
LEVERAGED_SUFFIXES = ("BULL", "BEAR", "2L", "2S", "3L", "3S", "4L", "4S", "5L", "5S")
LEVERAGED_UP_DOWN_ROOTS = (
    "AAVE",
    "ADA",
    "BCH",
    "BNB",
    "BTC",
    "DOT",
    "EOS",
    "ETH",
    "FIL",
    "LINK",
    "LTC",
    "SUSHI",
    "TRX",
    "UNI",
    "XRP",
    "XTZ",
    "YFI",
)


@dataclass(frozen=True, slots=True)
class BinanceSpotUniverseConfig:
    quote_asset: str = "USDT"
    min_avg_dollar_volume: float = 1_000_000.0
    avg_volume_window: int = 30
    min_history_bars: int = 180
    exclude_stablecoins: bool = True
    exclude_fiat: bool = True
    exclude_leveraged_tokens: bool = True
    require_active: bool = True
    excluded_bases: tuple[str, ...] = field(default_factory=tuple)
    excluded_symbols: tuple[str, ...] = field(default_factory=tuple)


def _normalized_symbol(symbol: str) -> str:
    return symbol.upper().replace("_", "/")


def _base_quote_from_market(symbol: str, market: Mapping[str, Any]) -> tuple[str, str]:
    base = str(market.get("base") or symbol.split("/", maxsplit=1)[0]).upper()
    quote = str(market.get("quote") or symbol.split("/", maxsplit=1)[1].split(":", maxsplit=1)[0]).upper()
    return base, quote


def _is_leveraged_base(base: str) -> bool:
    if base.endswith(LEVERAGED_SUFFIXES):
        return True
    for root in LEVERAGED_UP_DOWN_ROOTS:
        if base in {f"{root}UP", f"{root}DOWN"}:
            return True
    return False


def is_tradeable_binance_spot_market(
    symbol: str,
    market: Mapping[str, Any],
    *,
    config: BinanceSpotUniverseConfig = BinanceSpotUniverseConfig(),
) -> bool:
    normalized = _normalized_symbol(symbol)
    base, quote = _base_quote_from_market(normalized, market)

    if quote != config.quote_asset.upper():
        return False
    if normalized in {_normalized_symbol(item) for item in config.excluded_symbols}:
        return False
    if base in {item.upper() for item in config.excluded_bases}:
        return False
    if config.require_active and market.get("active") is False:
        return False
    if market.get("spot") is False:
        return False
    if str(market.get("type", "spot")).lower() not in {"spot", ""}:
        return False
    if config.exclude_stablecoins and base in STABLECOIN_BASES:
        return False
    if config.exclude_fiat and base in FIAT_BASES:
        return False
    if config.exclude_leveraged_tokens and _is_leveraged_base(base):
        return False
    return True


def candidate_symbols_from_markets(
    markets: Mapping[str, Mapping[str, Any]],
    *,
    config: BinanceSpotUniverseConfig = BinanceSpotUniverseConfig(),
) -> list[str]:
    symbols = [
        _normalized_symbol(symbol)
        for symbol, market in markets.items()
        if is_tradeable_binance_spot_market(symbol, market, config=config)
    ]
    return sorted(set(symbols))


def ticker_quote_volume(ticker: Mapping[str, Any]) -> float:
    quote_volume = ticker.get("quoteVolume")
    if quote_volume is not None:
        return float(quote_volume)
    base_volume = ticker.get("baseVolume")
    last = ticker.get("last") or ticker.get("close")
    if base_volume is None or last is None:
        return 0.0
    return float(base_volume) * float(last)


def rank_symbols_by_quote_volume(
    symbols: list[str],
    tickers: Mapping[str, Mapping[str, Any]],
    *,
    min_quote_volume: float = 0.0,
    max_symbols: int | None = None,
) -> list[str]:
    ranked: list[tuple[str, float]] = []
    for symbol in symbols:
        ticker = tickers.get(symbol)
        if ticker is None:
            continue
        quote_volume = ticker_quote_volume(ticker)
        if quote_volume < min_quote_volume:
            continue
        ranked.append((symbol, quote_volume))

    output = [symbol for symbol, _ in sorted(ranked, key=lambda item: (-item[1], item[0]))]
    if max_symbols is not None and max_symbols > 0:
        return output[:max_symbols]
    return output


def filter_symbols_by_ohlcv(
    ohlcv: pd.DataFrame,
    *,
    config: BinanceSpotUniverseConfig = BinanceSpotUniverseConfig(),
    candidate_symbols: list[str] | None = None,
) -> list[str]:
    if ohlcv.empty:
        return []

    frame = ohlcv.copy()
    frame["symbol"] = frame["symbol"].map(_normalized_symbol)
    if candidate_symbols is not None:
        allowed = {_normalized_symbol(symbol) for symbol in candidate_symbols}
        frame = frame[frame["symbol"].isin(allowed)]
    if frame.empty:
        return []

    selected: list[str] = []
    for symbol, group in frame.sort_values("ts").groupby("symbol", sort=True):
        if len(group) < config.min_history_bars:
            continue
        recent = group.tail(config.avg_volume_window)
        avg_dollar_volume = (recent["close"] * recent["volume"]).mean()
        if pd.isna(avg_dollar_volume) or float(avg_dollar_volume) < config.min_avg_dollar_volume:
            continue
        selected.append(str(symbol))
    return selected


def _symbols_from_local_ohlcv_paths(
    warehouse: DuckDBWarehouse,
    *,
    exchange: str,
    timeframe: str | None,
) -> list[str]:
    root = warehouse.layout.dataset_root("normalized", DatasetKind.OHLCV) / f"exchange={exchange.lower()}" / "market_type=spot"
    if timeframe:
        root = root / f"timeframe={timeframe.lower()}"
    symbols = {
        path.stem.removeprefix("symbol=").upper().replace("_", "/")
        for path in root.glob("**/symbol=*.parquet")
    }
    return sorted(symbols)


def select_binance_spot_universe(
    warehouse: DuckDBWarehouse,
    *,
    exchange: str = "binance",
    config: BinanceSpotUniverseConfig = BinanceSpotUniverseConfig(),
    candidate_symbols: list[str] | None = None,
    timeframe: str | None = None,
) -> list[str]:
    if config.min_avg_dollar_volume <= 0.0 and config.min_history_bars <= 1:
        symbols = _symbols_from_local_ohlcv_paths(warehouse, exchange=exchange, timeframe=timeframe)
        if candidate_symbols is not None:
            allowed = {_normalized_symbol(symbol) for symbol in candidate_symbols}
            symbols = [symbol for symbol in symbols if symbol in allowed]
        if symbols:
            return symbols

    ohlcv = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=exchange,
        market_type=MarketType.SPOT,
        timeframe=timeframe,
        columns=["ts", "symbol", "close", "volume"],
    )
    return filter_symbols_by_ohlcv(ohlcv, config=config, candidate_symbols=candidate_symbols)
