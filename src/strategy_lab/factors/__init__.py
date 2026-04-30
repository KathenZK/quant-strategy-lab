from .base import (
    FactorMetadata,
    FactorRegistry,
    PandasFactor,
    build_registered_factors,
    list_registered_factor_providers,
    register_factor_provider,
)
from .engine import compute_factor_bundle, compute_factor_frame


_FACTOR_EXPORTS = {
    "AmihudIlliquidityFactor": "strategy_lab.factors.liquidity",
    "ATRPercentFactor": "strategy_lab.factors.momentum",
    "BasisChangeFactor": "strategy_lab.factors.derivatives",
    "BasisFactor": "strategy_lab.factors.derivatives",
    "BasisZScoreFactor": "strategy_lab.factors.derivatives",
    "BollingerDistanceFactor": "strategy_lab.factors.mean_reversion",
    "BreakoutFactor": "strategy_lab.factors.momentum",
    "DonchianBreakoutFactor": "strategy_lab.factors.momentum",
    "FundingRateFactor": "strategy_lab.factors.derivatives",
    "FundingRateZScoreFactor": "strategy_lab.factors.derivatives",
    "MovingAverageDistanceFactor": "strategy_lab.factors.momentum",
    "OpenInterestChangeFactor": "strategy_lab.factors.derivatives",
    "OpenInterestZScoreFactor": "strategy_lab.factors.derivatives",
    "PriceOpenInterestRegimeFactor": "strategy_lab.factors.derivatives",
    "RelativeStrengthFactor": "strategy_lab.factors.cross_sectional",
    "RSIFactor": "strategy_lab.factors.momentum",
    "TrailingReturnFactor": "strategy_lab.factors.momentum",
    "VolumeSurgeFactor": "strategy_lab.factors.liquidity",
    "VWAPDistanceFactor": "strategy_lab.factors.liquidity",
    "ZScoreFactor": "strategy_lab.factors.mean_reversion",
}


def __getattr__(name: str):
    if name not in _FACTOR_EXPORTS:
        raise AttributeError(name)
    from importlib import import_module

    module = import_module(_FACTOR_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value


def default_registry() -> FactorRegistry:
    registry = FactorRegistry()
    for factor in build_registered_factors():
        registry.register(factor)
    return registry


__all__ = [
    "AmihudIlliquidityFactor",
    "ATRPercentFactor",
    "BasisChangeFactor",
    "BasisFactor",
    "BasisZScoreFactor",
    "BollingerDistanceFactor",
    "BreakoutFactor",
    "DonchianBreakoutFactor",
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
