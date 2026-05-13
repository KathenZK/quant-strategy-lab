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
    "AgeBarsFactor": "strategy_lab.data.factors.lifecycle",
    "AmihudIlliquidityFactor": "strategy_lab.data.factors.liquidity",
    "AverageDollarVolumeFactor": "strategy_lab.data.factors.liquidity",
    "ATRPercentFactor": "strategy_lab.data.factors.momentum",
    "BearishCandleCountFactor": "strategy_lab.data.factors.momentum",
    "BasisChangeFactor": "strategy_lab.data.factors.derivatives",
    "BasisFactor": "strategy_lab.data.factors.derivatives",
    "BasisZScoreFactor": "strategy_lab.data.factors.derivatives",
    "BenchmarkReturnFactor": "strategy_lab.data.factors.momentum",
    "BullishCandleCountFactor": "strategy_lab.data.factors.momentum",
    "BollingerDistanceFactor": "strategy_lab.data.factors.mean_reversion",
    "BreakoutFactor": "strategy_lab.data.factors.momentum",
    "DonchianBreakoutFactor": "strategy_lab.data.factors.momentum",
    "DonchianBreakoutStrengthFactor": "strategy_lab.data.factors.momentum",
    "FundingRateFactor": "strategy_lab.data.factors.derivatives",
    "FundingRateZScoreFactor": "strategy_lab.data.factors.derivatives",
    "MovingAverageDistanceFactor": "strategy_lab.data.factors.momentum",
    "OpenInterestChangeFactor": "strategy_lab.data.factors.derivatives",
    "OpenInterestZScoreFactor": "strategy_lab.data.factors.derivatives",
    "PriceOpenInterestRegimeFactor": "strategy_lab.data.factors.derivatives",
    "RelativeStrengthFactor": "strategy_lab.data.factors.cross_sectional",
    "RollingDollarVolumeFactor": "strategy_lab.data.factors.liquidity",
    "RSIFactor": "strategy_lab.data.factors.momentum",
    "TrailingReturnFactor": "strategy_lab.data.factors.momentum",
    "VolumeSurgeFactor": "strategy_lab.data.factors.liquidity",
    "VWAPDistanceFactor": "strategy_lab.data.factors.liquidity",
    "ZScoreFactor": "strategy_lab.data.factors.mean_reversion",
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
    "AgeBarsFactor",
    "AmihudIlliquidityFactor",
    "AverageDollarVolumeFactor",
    "ATRPercentFactor",
    "BearishCandleCountFactor",
    "BasisChangeFactor",
    "BasisFactor",
    "BasisZScoreFactor",
    "BenchmarkReturnFactor",
    "BullishCandleCountFactor",
    "BollingerDistanceFactor",
    "BreakoutFactor",
    "DonchianBreakoutFactor",
    "DonchianBreakoutStrengthFactor",
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
    "RollingDollarVolumeFactor",
    "RSIFactor",
    "TrailingReturnFactor",
    "VolumeSurgeFactor",
    "VWAPDistanceFactor",
    "ZScoreFactor",
    "default_registry",
]
