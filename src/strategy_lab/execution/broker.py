from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from strategy_lab.execution.models import AccountSnapshot, Fill


class Broker(ABC):
    @abstractmethod
    def snapshot(self, ts: object, prices: pd.Series) -> AccountSnapshot:
        raise NotImplementedError

    @abstractmethod
    def rebalance_to_weights(self, ts: object, target_weights: pd.Series, prices: pd.Series) -> list[Fill]:
        raise NotImplementedError

    @abstractmethod
    def settle_funding(self, ts: object, funding_rates: pd.Series, prices: pd.Series) -> float:
        raise NotImplementedError
