from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True, slots=True)
class ExecutionAssumptions:
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    starting_cash: float = 100_000.0
    max_abs_weight: float = 0.20
    max_gross_leverage: float = 1.0
    max_net_exposure: float = 1.0
    min_dollar_volume: float = 0.0
    max_funding_rate_abs: float | None = None


@dataclass(slots=True)
class BacktestResult:
    equity_curve: pd.Series
    period_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    trading_costs: pd.Series
    funding_costs: pd.Series
    metrics: dict[str, float] = field(default_factory=dict)
