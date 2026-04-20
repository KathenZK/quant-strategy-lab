from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from signal_lab.execution.models import AccountSnapshot, Fill
from signal_lab.execution.paper import PaperBroker
from signal_lab.portfolio.risk import RiskManager


@dataclass(slots=True)
class PaperTradingResult:
    equity_curve: pd.Series
    snapshots: list[AccountSnapshot]
    fills: list[Fill]
    funding_cashflows: pd.Series


@dataclass(slots=True)
class PaperTradingSession:
    broker: PaperBroker
    risk_manager: RiskManager
    fills: list[Fill] = field(default_factory=list)
    snapshots: list[AccountSnapshot] = field(default_factory=list)

    def run(
        self,
        *,
        target_weights: pd.DataFrame,
        price_frame: pd.DataFrame,
        dollar_volume: pd.DataFrame | None = None,
        funding_rate: pd.DataFrame | None = None,
    ) -> PaperTradingResult:
        funding_events: list[float] = []
        funding_index: list[object] = []
        for ts in target_weights.index:
            constrained = self.risk_manager.apply_weights(
                target_weights.loc[ts],
                dollar_volume_row=None if dollar_volume is None else dollar_volume.loc[ts],
                funding_rate_row=None if funding_rate is None else funding_rate.loc[ts],
            )
            fills = self.broker.rebalance_to_weights(ts, constrained, price_frame.loc[ts])
            self.fills.extend(fills)
            funding_cashflow = 0.0
            if funding_rate is not None:
                funding_cashflow = self.broker.settle_funding(ts, funding_rate.loc[ts], price_frame.loc[ts])
            funding_events.append(funding_cashflow)
            funding_index.append(ts)
            self.snapshots.append(self.broker.snapshot(ts, price_frame.loc[ts]))

        equity_curve = pd.Series(
            [snapshot.equity for snapshot in self.snapshots],
            index=target_weights.index,
            name="equity",
        )
        return PaperTradingResult(
            equity_curve=equity_curve,
            snapshots=self.snapshots,
            fills=self.fills,
            funding_cashflows=pd.Series(funding_events, index=funding_index, name="funding_cashflow"),
        )
