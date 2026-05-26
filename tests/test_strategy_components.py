import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies import (
    CandleCountShortConfig,
    CandleCountShortStrategy,
    CrowdingReversalConfig,
    CrowdingReversalStrategy,
    DonchianBreakoutConfig,
    DonchianBreakoutStrategy,
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
    MomentumRotationConfig,
    MomentumRotationStrategy,
    SpotTrendConfig,
    SpotTrendStrategy,
)
from strategy_lab.workflow.config import strategy_workflow_from_code


def test_crowding_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = CrowdingReversalStrategy(
        CrowdingReversalConfig(
            max_short_positions=1,
            short_allocation=0.75,
        )
    )

    assert type(strategy.signal_model).__module__.startswith(
        "strategy_lab.strategies.crowding_reversal"
    )
    assert type(strategy.allocator).__module__.startswith(
        "strategy_lab.strategies.crowding_reversal"
    )
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert (
        strategy.required_liquidation_features()
        == strategy.allocator.required_risk_features()
    )


def test_ma_crossover_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(
            take_profit_pct=0.10,
            min_ma_gap_ratio=0.02,
        )
    )

    assert type(strategy.signal_model).__module__.startswith(
        "strategy_lab.strategies.ma_crossover"
    )
    assert type(strategy.allocator).__module__.startswith(
        "strategy_lab.strategies.ma_crossover"
    )
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

    assert type(strategy.signal_model).__module__.startswith(
        "strategy_lab.strategies.donchian_breakout"
    )
    assert type(strategy.allocator).__module__.startswith(
        "strategy_lab.strategies.donchian_breakout"
    )
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert set(strategy.required_factors()) == {
        "donchian_breakout_14",
        "ma_distance_120",
    }
    assert strategy.required_liquidation_features() == []


def test_momentum_rotation_strategy_exposes_signal_and_allocator_components() -> None:
    strategy = MomentumRotationStrategy(
        MomentumRotationConfig(
            max_long_positions=1,
            long_allocation=0.75,
        )
    )

    assert type(strategy.signal_model).__module__.startswith(
        "strategy_lab.strategies.momentum_rotation"
    )
    assert type(strategy.allocator).__module__.startswith(
        "strategy_lab.strategies.momentum_rotation"
    )
    assert strategy.required_factors() == strategy.signal_model.required_factors()
    assert (
        strategy.required_liquidation_features()
        == strategy.allocator.required_risk_features()
    )


def test_spot_cta_strategy_keeps_signal_and_position_logic_inside_strategy() -> None:
    strategy = SpotTrendStrategy(
        SpotTrendConfig(
            max_positions=5,
            long_allocation=0.5,
        )
    )

    assert not hasattr(strategy, "signal_model")
    assert not hasattr(strategy, "allocator")
    assert strategy.required_factors() == [
        "donchian_breakout_strength_20",
        "dollar_volume_1",
        "atr_pct_14",
    ]
    assert strategy.required_liquidation_features() == []


def test_candle_count_short_strategy_keeps_signal_and_position_logic_inside_strategy() -> (
    None
):
    strategy = CandleCountShortStrategy(CandleCountShortConfig())

    assert not hasattr(strategy, "signal_model")
    assert not hasattr(strategy, "allocator")
    assert strategy.required_factors() == [
        "bullish_candle_count_10",
        "bearish_candle_count_10",
        "atr_pct_288",
        "ret_96",
    ]
    assert strategy.required_liquidation_features() == []


def test_candle_count_short_code_workflow_uses_embedded_hype_defaults() -> None:
    workflow = strategy_workflow_from_code(
        "candle_count_short",
        market_type=MarketType.PERP,
        timeframe="15m",
    )

    assert workflow.strategy.symbols == ["HYPE/USDT:USDT"]
    assert workflow.strategy.benchmark_symbol is None
    assert workflow.refresh.enabled is True
    assert workflow.refresh.include_derivatives is False
    assert workflow.refresh.timeframe == "15m"
    assert workflow.execution.fee_bps == 4.5
    assert workflow.execution.slippage_bps == 4.0
    assert workflow.risk.max_abs_weight == 3.0
    assert workflow.risk.max_gross_leverage == 3.0
    assert workflow.risk.max_net_exposure == 3.0


def test_strategy_versions_change_when_allocator_configuration_changes() -> None:
    baseline = MomentumRotationStrategy(
        MomentumRotationConfig(long_allocation=0.5)
    ).version()
    updated = MomentumRotationStrategy(
        MomentumRotationConfig(long_allocation=0.8)
    ).version()
    assert baseline != updated


def test_ranked_allocator_retains_existing_momentum_behavior() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    strategy = MomentumRotationStrategy(
        MomentumRotationConfig(
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
