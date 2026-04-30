from __future__ import annotations

from collections.abc import Iterable

from strategy_lab.allocators.common import apply_liquidation_risk_overlay as _apply_liquidation_risk_overlay
from strategy_lab.data import MarketType


def normalize_symbols(symbols: Iterable[object] | str | None) -> list[str]:
    if symbols is None:
        return []
    if isinstance(symbols, str):
        raw_symbols = symbols.split(",")
    else:
        raw_symbols = symbols
    return [str(symbol).strip().upper() for symbol in raw_symbols if str(symbol).strip()]


def market_symbols(base_assets: Iterable[str], market_type: MarketType, quote_asset: str = "USDT") -> list[str]:
    suffix = f"/{quote_asset}:USDT" if market_type == MarketType.PERP else f"/{quote_asset}"
    return [f"{base.strip().upper()}{suffix}" for base in base_assets if base.strip()]


def resolve_configured_symbols(
    configured_symbols: Iterable[object] | str | None,
    *,
    market_type: MarketType,
    default_bases: Iterable[str],
) -> list[str]:
    configured = normalize_symbols(configured_symbols)
    if configured:
        return configured
    return market_symbols(default_bases, market_type)


def apply_liquidation_risk_overlay(*args, **kwargs):
    if "liquidation_features" in kwargs:
        kwargs["risk_features"] = kwargs.pop("liquidation_features")
    return _apply_liquidation_risk_overlay(*args, **kwargs)
