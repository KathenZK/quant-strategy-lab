from .base import FactorMetadata, FactorRegistry, PandasFactor
from .cross_sectional import RelativeStrengthFactor
from .derivatives import (
    BasisChangeFactor,
    BasisFactor,
    BasisZScoreFactor,
    FundingRateFactor,
    FundingRateZScoreFactor,
    OpenInterestChangeFactor,
    OpenInterestZScoreFactor,
    PriceOpenInterestRegimeFactor,
)
from .engine import compute_factor_bundle, compute_factor_frame
from .liquidity import AmihudIlliquidityFactor, VWAPDistanceFactor, VolumeSurgeFactor
from .mean_reversion import BollingerDistanceFactor, ZScoreFactor
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
        ZScoreFactor(window=20),
        BollingerDistanceFactor(window=20),
        VolumeSurgeFactor(window=20),
        AmihudIlliquidityFactor(),
        VWAPDistanceFactor(),
        FundingRateFactor(),
        FundingRateZScoreFactor(window=72),
        OpenInterestChangeFactor(periods=4),
        OpenInterestZScoreFactor(window=72),
        BasisFactor(),
        BasisChangeFactor(periods=4),
        BasisZScoreFactor(window=72),
        PriceOpenInterestRegimeFactor(periods=4),
        RelativeStrengthFactor(periods=24),
    ):
        registry.register(factor)
    return registry


__all__ = [
    "AmihudIlliquidityFactor",
    "BasisChangeFactor",
    "BasisFactor",
    "BasisZScoreFactor",
    "BollingerDistanceFactor",
    "BreakoutFactor",
    "compute_factor_bundle",
    "compute_factor_frame",
    "FactorMetadata",
    "FactorRegistry",
    "FundingRateFactor",
    "FundingRateZScoreFactor",
    "MovingAverageDistanceFactor",
    "OpenInterestChangeFactor",
    "OpenInterestZScoreFactor",
    "PandasFactor",
    "PriceOpenInterestRegimeFactor",
    "RelativeStrengthFactor",
    "RSIFactor",
    "TrailingReturnFactor",
    "VolumeSurgeFactor",
    "VWAPDistanceFactor",
    "ZScoreFactor",
    "default_registry",
]
