import pandas as pd

from strategy_lab.allocators import DonchianBreakoutAllocator, PersistentSignalAllocator, RankedCrossSectionalAllocator
from strategy_lab.signals import (
    CrowdingReversalSignalModel,
    DonchianBreakoutSignalModel,
    MovingAverageCrossoverSignalModel,
    MomentumRotationSignalModel,
    TrendConfirmationSignalModel,
)
from strategy_lab.strategies import (
    CrowdingReversalConfig,
    CrowdingReversalStrategy,
    DonchianBreakoutConfig,
    DonchianBreakoutStrategy,
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
    MomentumRotationConfig,
    MomentumRotationStrategy,
    TrendConfirmationConfig,
    TrendConfirmationStrategy,
)


def test_trend_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = TrendConfirmationStrategy(
        TrendConfirmationConfig(
            max_long_positions=1,
            long_allocation=0.75,
        )
    )

    assert isinstance(strategy.signal_model, TrendConfirmationSignalModel)
    assert isinstance(strategy.allocator, RankedCrossSectionalAllocator)
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == strategy.allocator.required_risk_features()


def test_crowding_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = CrowdingReversalStrategy(
        CrowdingReversalConfig(
            max_short_positions=1,
            short_allocation=0.75,
        )
    )

    assert isinstance(strategy.signal_model, CrowdingReversalSignalModel)
    assert isinstance(strategy.allocator, RankedCrossSectionalAllocator)
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == strategy.allocator.required_risk_features()


def test_ma_crossover_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(
            take_profit_pct=0.10,
            min_ma_gap_ratio=0.02,
        )
    )

    assert isinstance(strategy.signal_model, MovingAverageCrossoverSignalModel)
    assert isinstance(strategy.allocator, PersistentSignalAllocator)
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == []


def test_donchian_breakout_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(
            trend_factor="ma_distance_120",
            risk_budget_pct=0.01,
            stop_loss_pct=0.05,
            max_pyramids=2,
        )
    )

    assert isinstance(strategy.signal_model, DonchianBreakoutSignalModel)
    assert isinstance(strategy.allocator, DonchianBreakoutAllocator)
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert set(strategy.required_factors()) == {"donchian_breakout_14", "ma_distance_120"}
    assert strategy.required_liquidation_features() == []


def test_momentum_rotation_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = MomentumRotationStrategy(
        MomentumRotationConfig(
            max_long_positions=1,
            long_allocation=0.75,
        )
    )

    assert isinstance(strategy.signal_model, MomentumRotationSignalModel)
    assert isinstance(strategy.allocator, RankedCrossSectionalAllocator)
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == strategy.allocator.required_risk_features()


def test_strategy_versions_change_when_allocator_configuration_changes() -> None:
    baseline = TrendConfirmationStrategy(TrendConfirmationConfig(long_allocation=0.5)).version()
    updated = TrendConfirmationStrategy(TrendConfirmationConfig(long_allocation=0.8)).version()
    assert baseline != updated


def test_ranked_allocator_retains_existing_trend_behavior() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    strategy = TrendConfirmationStrategy(
        TrendConfirmationConfig(
            max_long_positions=1,
            max_short_positions=1,
            long_allocation=0.5,
            short_allocation=0.5,
        )
    )
    signal = pd.DataFrame({"BTC": [2.0], "ETH": [-1.0], "SOL": [0.5]}, index=index)

    weights = strategy.build_weights(signal)

    assert weights.loc[index[0], "BTC"] == 0.5
    assert weights.loc[index[0], "ETH"] == -0.5
    assert weights.loc[index[0], "SOL"] == 0.0
