import pandas as pd

from strategy_lab.strategies import (
    CrowdingReversalConfig,
    CrowdingReversalStrategy,
    DonchianBreakoutConfig,
    DonchianBreakoutStrategy,
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
    MomentumRotationConfig,
    MomentumRotationStrategy,
    SpotCtaTrendConfig,
    SpotCtaTrendStrategy,
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

    assert type(strategy.signal_model).__module__.startswith("strategy_lab.strategies.trend_confirmation")
    assert type(strategy.allocator).__module__.startswith("strategy_lab.strategies.trend_confirmation")
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == strategy.allocator.required_risk_features()


def test_crowding_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = CrowdingReversalStrategy(
        CrowdingReversalConfig(
            max_short_positions=1,
            short_allocation=0.75,
        )
    )

    assert type(strategy.signal_model).__module__.startswith("strategy_lab.strategies.crowding_reversal")
    assert type(strategy.allocator).__module__.startswith("strategy_lab.strategies.crowding_reversal")
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == strategy.allocator.required_risk_features()


def test_ma_crossover_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(
            take_profit_pct=0.10,
            min_ma_gap_ratio=0.02,
        )
    )

    assert type(strategy.signal_model).__module__.startswith("strategy_lab.strategies.ma_crossover")
    assert type(strategy.allocator).__module__.startswith("strategy_lab.strategies.ma_crossover")
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

    assert type(strategy.signal_model).__module__.startswith("strategy_lab.strategies.donchian_breakout")
    assert type(strategy.allocator).__module__.startswith("strategy_lab.strategies.donchian_breakout")
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

    assert type(strategy.signal_model).__module__.startswith("strategy_lab.strategies.momentum_rotation")
    assert type(strategy.allocator).__module__.startswith("strategy_lab.strategies.momentum_rotation")
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert strategy.required_liquidation_features() == strategy.allocator.required_risk_features()


def test_spot_cta_strategy_keeps_signal_and_position_logic_inside_strategy() -> None:
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=5,
            long_allocation=0.5,
        )
    )

    assert not hasattr(strategy, "signal_model")
    assert not hasattr(strategy, "allocator")
    assert strategy.required_factors() == [
        "donchian_breakout_20",
        "dollar_volume_24",
        "benchmark_ret_24",
    ]
    assert strategy.required_liquidation_features() == []


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
