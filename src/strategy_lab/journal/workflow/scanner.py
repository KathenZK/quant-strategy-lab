from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class ScanDecision:
    symbol: str
    action: str
    target_weight: float
    previous_weight: float
    signal: float | None
    price: float | None


@dataclass(frozen=True, slots=True)
class StrategyScanResult:
    ts: pd.Timestamp
    decisions: list[ScanDecision]
    watchlist: list[ScanDecision]

    def by_action(self, action: str) -> list[ScanDecision]:
        return [item for item in self.decisions if item.action == action]


def _value(row: pd.Series, symbol: str) -> float | None:
    value = row.get(symbol)
    if pd.isna(value):
        return None
    return float(value)


def build_strategy_scan_result(
    *,
    signal_frame: pd.DataFrame,
    target_weights: pd.DataFrame,
    price_frame: pd.DataFrame,
    top_n: int = 20,
) -> StrategyScanResult:
    if signal_frame.empty:
        raise ValueError("signal_frame is empty")
    if target_weights.empty:
        raise ValueError("target_weights is empty")

    ts = pd.to_datetime(target_weights.index[-1], utc=True)
    latest_weights = target_weights.iloc[-1].fillna(0.0)
    previous_weights = (
        target_weights.iloc[-2].fillna(0.0)
        if len(target_weights.index) >= 2
        else pd.Series(0.0, index=target_weights.columns)
    )
    latest_signals = signal_frame.reindex(index=target_weights.index, columns=target_weights.columns).iloc[-1]
    latest_prices = price_frame.reindex(index=target_weights.index, columns=target_weights.columns).iloc[-1]

    decisions: list[ScanDecision] = []
    for symbol in target_weights.columns:
        target = float(latest_weights.get(symbol, 0.0))
        previous = float(previous_weights.get(symbol, 0.0))
        action: str | None = None
        if target > 0.0 and previous <= 0.0:
            action = "buy"
        elif target > 0.0 and previous > 0.0:
            action = "hold"
        elif target <= 0.0 and previous > 0.0:
            action = "sell"

        if action is None:
            continue
        decisions.append(
            ScanDecision(
                symbol=symbol,
                action=action,
                target_weight=target,
                previous_weight=previous,
                signal=_value(latest_signals, symbol),
                price=_value(latest_prices, symbol),
            )
        )

    active_symbols = {item.symbol for item in decisions if item.action in {"buy", "hold"}}
    positive_signals = latest_signals[latest_signals > 0.0].dropna().sort_values(ascending=False)
    watchlist = [
        ScanDecision(
            symbol=symbol,
            action="watch",
            target_weight=float(latest_weights.get(symbol, 0.0)),
            previous_weight=float(previous_weights.get(symbol, 0.0)),
            signal=float(signal),
            price=_value(latest_prices, symbol),
        )
        for symbol, signal in positive_signals.items()
        if symbol not in active_symbols
    ][:top_n]

    action_order = {"sell": 0, "buy": 1, "hold": 2}
    decisions = sorted(
        decisions,
        key=lambda item: (
            action_order[item.action],
            -abs(item.target_weight - item.previous_weight),
            item.symbol,
        ),
    )
    return StrategyScanResult(ts=ts, decisions=decisions, watchlist=watchlist)
