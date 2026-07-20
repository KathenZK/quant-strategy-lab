from __future__ import annotations

from typing import TypeVar


ReturnArray = TypeVar("ReturnArray")


def long_net_return(
    entry_price: ReturnArray,
    exit_price: ReturnArray,
    *,
    round_trip_cost: float,
    funding_sum: ReturnArray | float,
) -> ReturnArray:
    """Return notional-normalized PnL for a long linear contract position."""
    return exit_price / entry_price - 1.0 - round_trip_cost - funding_sum


def short_net_return(
    entry_price: ReturnArray,
    exit_price: ReturnArray,
    *,
    round_trip_cost: float,
    funding_sum: ReturnArray | float,
) -> ReturnArray:
    """Return notional-normalized PnL for a short linear contract position."""
    return 1.0 - exit_price / entry_price - round_trip_cost + funding_sum
