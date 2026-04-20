from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from signal_lab.execution.broker import Broker
from signal_lab.execution.models import AccountSnapshot, Fill, OrderSide, Position


@dataclass(slots=True)
class PaperBroker(Broker):
    starting_cash: float = 100_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    cash: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.cash = self.starting_cash

    def snapshot(self, ts: object, prices: pd.Series) -> AccountSnapshot:
        equity = self.cash
        cloned_positions: dict[str, Position] = {}
        for symbol, position in self.positions.items():
            price = float(prices.get(symbol, position.average_price))
            equity += position.market_value(price)
            cloned_positions[symbol] = Position(symbol=symbol, quantity=position.quantity, average_price=position.average_price)
        return AccountSnapshot(ts=ts, cash=self.cash, equity=equity, positions=cloned_positions)

    def rebalance_to_weights(self, ts: object, target_weights: pd.Series, prices: pd.Series) -> list[Fill]:
        snapshot = self.snapshot(ts, prices)
        fills: list[Fill] = []
        for symbol, target_weight in target_weights.fillna(0.0).items():
            price = float(prices.get(symbol, 0.0))
            if price <= 0:
                continue

            current_quantity = self.positions.get(symbol, Position(symbol=symbol)).quantity
            current_notional = current_quantity * price
            target_notional = snapshot.equity * float(target_weight)
            delta_notional = target_notional - current_notional
            if abs(delta_notional) < 1e-9:
                continue

            side = OrderSide.BUY if delta_notional > 0 else OrderSide.SELL
            slip_multiplier = 1.0 + (self.slippage_bps / 10_000.0 if side == OrderSide.BUY else -self.slippage_bps / 10_000.0)
            execution_price = price * slip_multiplier
            quantity = delta_notional / execution_price
            trade_notional = quantity * execution_price
            fee = abs(trade_notional) * self.fee_bps / 10_000.0

            self.cash -= trade_notional + fee
            new_quantity = current_quantity + quantity
            if abs(new_quantity) < 1e-9:
                self.positions.pop(symbol, None)
            else:
                average_price = execution_price if abs(current_quantity) < 1e-9 else self._weighted_average_price(
                    current_quantity,
                    self.positions.get(symbol, Position(symbol=symbol)).average_price,
                    quantity,
                    execution_price,
                )
                self.positions[symbol] = Position(symbol=symbol, quantity=new_quantity, average_price=average_price)

            fills.append(
                Fill(
                    ts=ts,
                    symbol=symbol,
                    side=side,
                    quantity=float(quantity),
                    price=float(execution_price),
                    fee=float(fee),
                )
            )
        return fills

    def settle_funding(self, ts: object, funding_rates: pd.Series, prices: pd.Series) -> float:
        funding_cash_flow = 0.0
        for symbol, position in self.positions.items():
            price = float(prices.get(symbol, position.average_price))
            rate = float(funding_rates.get(symbol, 0.0))
            funding_cash_flow -= position.market_value(price) * rate
        self.cash += funding_cash_flow
        return funding_cash_flow

    @staticmethod
    def _weighted_average_price(current_qty: float, current_price: float, delta_qty: float, delta_price: float) -> float:
        total_qty = current_qty + delta_qty
        if abs(total_qty) < 1e-9:
            return 0.0
        if current_qty == 0:
            return delta_price
        if current_qty * delta_qty > 0:
            return ((current_qty * current_price) + (delta_qty * delta_price)) / total_qty
        if abs(delta_qty) < abs(current_qty):
            return current_price
        return delta_price
