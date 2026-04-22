from .base import (
    FactorMetadata,
    FactorRegistry,
    PandasFactor,
    build_registered_factors,
    list_registered_factor_providers,
    register_factor_provider,
)
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
    for factor in build_registered_factors():
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
    "list_registered_factor_providers",
    "MovingAverageDistanceFactor",
    "OpenInterestChangeFactor",
    "OpenInterestZScoreFactor",
    "PandasFactor",
    "PriceOpenInterestRegimeFactor",
    "register_factor_provider",
    "RelativeStrengthFactor",
    "RSIFactor",
    "TrailingReturnFactor",
    "VolumeSurgeFactor",
    "VWAPDistanceFactor",
    "ZScoreFactor",
    "default_registry",
]
