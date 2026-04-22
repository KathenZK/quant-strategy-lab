import pandas as pd
import pytest

from signal_lab.strategies import (
    CrowdingReversalConfig,
    CrowdingReversalStrategy,
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
    TrendConfirmationConfig,
    TrendConfirmationStrategy,
    create_strategy,
    list_registered_strategies,
    register_strategy,
)


def test_trend_confirmation_strategy_builds_signal_and_weights() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    factors = {
        "ret_24": pd.DataFrame({"BTC": [0.08], "ETH": [-0.06], "SOL": [0.02]}, index=index),
        "breakout_20": pd.DataFrame({"BTC": [0.01], "ETH": [-0.05], "SOL": [0.00]}, index=index),
        "oi_change_4": pd.DataFrame({"BTC": [0.10], "ETH": [0.09], "SOL": [-0.01]}, index=index),
        "basis_change_4": pd.DataFrame({"BTC": [0.07], "ETH": [-0.05], "SOL": [0.01]}, index=index),
        "funding_zscore_72": pd.DataFrame({"BTC": [0.5], "ETH": [0.6], "SOL": [3.5]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [0.4], "ETH": [0.3], "SOL": [0.2]}, index=index),
    }
    strategy = TrendConfirmationStrategy(
        TrendConfirmationConfig(
            max_long_positions=1,
            max_short_positions=1,
            long_allocation=0.5,
            short_allocation=0.5,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal)

    assert signal.loc[index[0], "BTC"] > 0
    assert signal.loc[index[0], "ETH"] < 0
    assert pd.isna(signal.loc[index[0], "SOL"])
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.5)
    assert weights.loc[index[0], "ETH"] == pytest.approx(-0.5)
    assert weights.loc[index[0], "SOL"] == pytest.approx(0.0)


def test_trend_confirmation_strategy_version_changes_with_config() -> None:
    baseline = TrendConfirmationStrategy(TrendConfirmationConfig()).version()
    updated = TrendConfirmationStrategy(TrendConfirmationConfig(max_abs_funding_zscore=1.5)).version()
    assert baseline != updated


def test_trend_confirmation_strategy_applies_liquidation_overlay() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0], "ETH": [-1.0], "SOL": [0.5]}, index=index)
    strategy = TrendConfirmationStrategy(
        TrendConfirmationConfig(
            max_long_positions=2,
            max_short_positions=1,
            long_allocation=0.5,
            short_allocation=0.5,
            max_liquidation_spike_zscore=2.5,
            max_liquidation_notional_ratio=0.03,
            liquidation_weight_scale=0.2,
            stop_on_event_cooldown=True,
        )
    )
    liquidation_features = {
        "liq_spike_zscore": pd.DataFrame({"BTC": [3.0], "ETH": [0.0], "SOL": [0.0]}, index=index),
        "liq_notional_vs_dollar_volume": pd.DataFrame({"BTC": [0.01], "ETH": [0.0], "SOL": [0.05]}, index=index),
        "event_cooldown_flag": pd.DataFrame({"BTC": [0], "ETH": [1], "SOL": [0]}, index=index),
    }

    weights = strategy.build_weights(signal, liquidation_features)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.05)
    assert weights.loc[index[0], "ETH"] == pytest.approx(0.0)
    assert weights.loc[index[0], "SOL"] == pytest.approx(0.05)


def test_crowding_reversal_strategy_builds_signal_and_weights() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    factors = {
        "ret_24": pd.DataFrame({"BTC": [0.08], "ETH": [-0.07], "SOL": [0.01]}, index=index),
        "ret_4": pd.DataFrame({"BTC": [-0.02], "ETH": [0.03], "SOL": [0.00]}, index=index),
        "funding_zscore_72": pd.DataFrame({"BTC": [2.2], "ETH": [-2.4], "SOL": [0.1]}, index=index),
        "basis_zscore_72": pd.DataFrame({"BTC": [1.8], "ETH": [-1.7], "SOL": [0.1]}, index=index),
        "oi_zscore_72": pd.DataFrame({"BTC": [1.6], "ETH": [1.7], "SOL": [0.2]}, index=index),
        "price_oi_regime_4": pd.DataFrame({"BTC": [-2.0], "ETH": [2.0], "SOL": [1.0]}, index=index),
    }
    strategy = CrowdingReversalStrategy(
        CrowdingReversalConfig(
            max_long_positions=1,
            max_short_positions=1,
            long_allocation=0.5,
            short_allocation=0.5,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal)

    assert signal.loc[index[0], "BTC"] < 0
    assert signal.loc[index[0], "ETH"] > 0
    assert pd.isna(signal.loc[index[0], "SOL"])
    assert weights.loc[index[0], "BTC"] == pytest.approx(-0.5)
    assert weights.loc[index[0], "ETH"] == pytest.approx(0.5)
    assert weights.loc[index[0], "SOL"] == pytest.approx(0.0)


def test_crowding_reversal_strategy_applies_liquidation_overlay() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    signal = pd.DataFrame({"BTC": [-1.0], "ETH": [1.0]}, index=index)
    strategy = CrowdingReversalStrategy(
        CrowdingReversalConfig(
            max_long_positions=1,
            max_short_positions=1,
            long_allocation=0.5,
            short_allocation=0.5,
            liquidation_weight_scale=0.1,
        )
    )
    liquidation_features = {
        "liq_spike_zscore": pd.DataFrame({"BTC": [3.0], "ETH": [0.0]}, index=index),
        "liq_notional_vs_dollar_volume": pd.DataFrame({"BTC": [0.0], "ETH": [0.0]}, index=index),
        "event_cooldown_flag": pd.DataFrame({"BTC": [0], "ETH": [1]}, index=index),
    }
    weights = strategy.build_weights(signal, liquidation_features)
    assert weights.loc[index[0], "BTC"] == pytest.approx(-0.05)
    assert weights.loc[index[0], "ETH"] == pytest.approx(0.0)


def test_moving_average_crossover_strategy_tracks_regime_until_next_cross() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    factors = {
        "ma_distance_30": pd.DataFrame({"BTC": [0.04, 0.03, 0.01, 0.02, 0.05]}, index=index),
        "ma_distance_120": pd.DataFrame({"BTC": [0.03, 0.04, 0.05, 0.01, 0.02]}, index=index),
    }
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(
            long_allocation=1.0,
            short_allocation=1.0,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal)

    assert signal.loc[index[0], "BTC"] == pytest.approx(-1.0)
    assert signal.loc[index[1], "BTC"] == pytest.approx(1.0)
    assert pd.isna(signal.loc[index[2], "BTC"])
    assert signal.loc[index[3], "BTC"] == pytest.approx(-1.0)
    assert pd.isna(signal.loc[index[4], "BTC"])
    assert weights.loc[index[0], "BTC"] == pytest.approx(-1.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[2], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[3], "BTC"] == pytest.approx(-1.0)
    assert weights.loc[index[4], "BTC"] == pytest.approx(-1.0)


def test_strategy_registry_lists_builtin_strategies() -> None:
    names = list_registered_strategies()
    assert "trend_confirmation" in names
    assert "crowding_reversal" in names
    assert "ma_crossover" in names


def test_create_strategy_uses_registry() -> None:
    trend = create_strategy("trend_confirmation", {"max_long_positions": 1})
    crowding = create_strategy("crowding_reversal", {"max_short_positions": 1})
    crossover = create_strategy("ma_crossover", {"long_allocation": 0.75})
    assert isinstance(trend, TrendConfirmationStrategy)
    assert isinstance(crowding, CrowdingReversalStrategy)
    assert isinstance(crossover, MovingAverageCrossoverStrategy)


def test_register_strategy_decorator_supports_new_strategy_types() -> None:
    @register_strategy("unit_test_strategy")
    class UnitTestStrategy:
        @classmethod
        def from_options(cls, options: dict[str, object] | None = None):
            instance = cls()
            instance.options = options or {}
            return instance

        @property
        def signal_name(self) -> str:
            return "unit_test_strategy"

    instance = create_strategy("unit_test_strategy", {"foo": "bar"})
    assert instance.signal_name == "unit_test_strategy"
    assert instance.options["foo"] == "bar"
