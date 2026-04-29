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


def select_binance_spot_universe(
    warehouse: DuckDBWarehouse,
    *,
    exchange: str = "binance",
    config: BinanceSpotUniverseConfig = BinanceSpotUniverseConfig(),
    candidate_symbols: list[str] | None = None,
) -> list[str]:
    ohlcv = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=exchange,
        market_type=MarketType.SPOT,
        columns=["ts", "symbol", "close", "volume"],
    )
    return filter_symbols_by_ohlcv(ohlcv, config=config, candidate_symbols=candidate_symbols)
