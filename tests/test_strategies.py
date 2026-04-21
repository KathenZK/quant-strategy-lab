import pandas as pd
import pytest

from signal_lab.strategies import TrendConfirmationConfig, TrendConfirmationStrategy


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
