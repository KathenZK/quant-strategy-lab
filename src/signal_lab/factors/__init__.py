from .base import FactorMetadata, FactorRegistry, PandasFactor
from .derivatives import FundingRateFactor, OpenInterestChangeFactor, PriceOpenInterestRegimeFactor
from .momentum import BreakoutFactor, MovingAverageDistanceFactor, RSIFactor, TrailingReturnFactor


def default_registry() -> FactorRegistry:
    registry = FactorRegistry()
    for factor in (
        TrailingReturnFactor(periods=1),
        TrailingReturnFactor(periods=4),
        TrailingReturnFactor(periods=24),
        BreakoutFactor(window=20),
        MovingAverageDistanceFactor(window=20),
        RSIFactor(window=14),
        FundingRateFactor(),
        OpenInterestChangeFactor(periods=4),
        PriceOpenInterestRegimeFactor(periods=4),
    ):
        registry.register(factor)
    return registry


__all__ = [
    "BreakoutFactor",
    "FactorMetadata",
    "FactorRegistry",
    "FundingRateFactor",
    "MovingAverageDistanceFactor",
    "OpenInterestChangeFactor",
    "PandasFactor",
    "PriceOpenInterestRegimeFactor",
    "RSIFactor",
    "TrailingReturnFactor",
    "default_registry",
]
