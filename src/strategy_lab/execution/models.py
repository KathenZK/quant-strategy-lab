from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    order_type: OrderType = OrderType.MARKET
    post_only: bool = False
    reduce_only: bool = False


@dataclass(frozen=True, slots=True)
class OrderIntent:
    symbol: str
    target_weight: float
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)


@dataclass(frozen=True, slots=True)
class Fill:
    ts: object
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    fee: float


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0

    def market_value(self, price: float) -> float:
        return self.quantity * price


@dataclass(slots=True)
class AccountSnapshot:
    ts: object
    cash: float
    equity: float
    positions: dict[str, Position]
