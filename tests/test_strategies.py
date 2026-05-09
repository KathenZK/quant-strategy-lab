import pandas as pd
import pytest

from strategy_lab.data import MarketType
from strategy_lab.strategies import (
    CrowdingReversalConfig,
    CrowdingReversalStrategy,
    DonchianBreakoutConfig,
    DonchianBreakoutStrategy,
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
    MomentumRotationConfig,
    MomentumRotationStrategy,
    SmallCapMomentumBreakoutConfig,
    SmallCapMomentumBreakoutStrategy,
    SpotCtaTrendConfig,
    SpotCtaTrendStrategy,
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


def test_moving_average_crossover_strategy_applies_take_profit_and_stop_loss() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    price_frame = pd.DataFrame({"BTC": [100.0, 112.0, 110.0, 121.0]}, index=index)
    factors = {
        "ma_distance_30": pd.DataFrame({"BTC": [0.01, 0.01, 0.04, 0.04]}, index=index),
        "ma_distance_120": pd.DataFrame({"BTC": [0.03, 0.03, 0.02, 0.02]}, index=index),
    }
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(
            long_allocation=1.0,
            short_allocation=1.0,
            take_profit_pct=0.10,
            stop_loss_pct=0.08,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert weights.loc[index[0], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[2], "BTC"] == pytest.approx(-1.0)
    assert weights.loc[index[3], "BTC"] == pytest.approx(0.0)


def test_moving_average_crossover_strategy_filters_choppy_entries() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 102.0]}, index=index)
    factors = {
        "ma_distance_30": pd.DataFrame({"BTC": [0.010, 0.011, 0.012]}, index=index),
        "ma_distance_120": pd.DataFrame({"BTC": [0.020, 0.021, 0.022]}, index=index),
    }
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(
            long_allocation=1.0,
            short_allocation=1.0,
            min_ma_gap_ratio=0.03,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert signal.loc[index[0], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.0)


def test_donchian_breakout_strategy_holds_position_between_breakouts() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    factors = {
        "donchian_breakout_14": pd.DataFrame(
            {"BTC": [float("nan"), 1.0, float("nan"), -1.0, float("nan")]},
            index=index,
        )
    }
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(long_allocation=1.0, short_allocation=1.0)
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal)

    assert pd.isna(signal.loc[index[0], "BTC"])
    assert signal.loc[index[1], "BTC"] == pytest.approx(1.0)
    assert pd.isna(signal.loc[index[2], "BTC"])
    assert signal.loc[index[3], "BTC"] == pytest.approx(-1.0)
    assert pd.isna(signal.loc[index[4], "BTC"])

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[2], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[3], "BTC"] == pytest.approx(-1.0)
    assert weights.loc[index[4], "BTC"] == pytest.approx(-1.0)


def test_donchian_breakout_strategy_requires_configured_factor() -> None:
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(breakout_factor="donchian_breakout_10")
    )
    index = pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC")
    factors = {
        "donchian_breakout_14": pd.DataFrame({"BTC": [1.0, float("nan")]}, index=index),
    }
    with pytest.raises(ValueError):
        strategy.build_signal_frame(factors)


def test_donchian_breakout_strategy_filters_countertrend_breakouts() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    factors = {
        "donchian_breakout_14": pd.DataFrame(
            {"BTC": [1.0, 1.0, -1.0, -1.0]},
            index=index,
        ),
        "ma_distance_120": pd.DataFrame(
            {"BTC": [-0.02, 0.03, 0.02, -0.04]},
            index=index,
        ),
    }
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(
            breakout_factor="donchian_breakout_14",
            trend_factor="ma_distance_120",
        )
    )

    signal = strategy.build_signal_frame(factors)

    assert pd.isna(signal.loc[index[0], "BTC"])
    assert signal.loc[index[1], "BTC"] == pytest.approx(1.0)
    assert pd.isna(signal.loc[index[2], "BTC"])
    assert signal.loc[index[3], "BTC"] == pytest.approx(-1.0)


def test_donchian_breakout_strategy_exits_when_trend_reverses() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    factors = {
        "donchian_breakout_14": pd.DataFrame(
            {"BTC": [float("nan"), 1.0, float("nan"), float("nan")]},
            index=index,
        ),
        "ma_distance_120": pd.DataFrame(
            {"BTC": [0.02, 0.03, -0.01, -0.02]},
            index=index,
        ),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 102.0, 101.0, 100.0]}, index=index)
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(
            trend_factor="ma_distance_120",
            exit_on_trend_reversal=True,
            long_allocation=1.0,
            short_allocation=1.0,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(1.0)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[3], "BTC"] == pytest.approx(0.0)


def test_donchian_breakout_strategy_supports_risk_budget_pyramids_and_trailing_stop() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    factors = {
        "donchian_breakout_14": pd.DataFrame(
            {"BTC": [float("nan"), 1.0, float("nan"), float("nan"), float("nan")]},
            index=index,
        )
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 100.0, 110.0, 121.0, 114.0]}, index=index)
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(
            long_allocation=1.0,
            short_allocation=1.0,
            stop_loss_pct=0.10,
            trailing_stop_pct=0.05,
            risk_budget_pct=0.02,
            max_pyramids=2,
            pyramid_step_pct=0.10,
            pyramid_unit_scale=0.5,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.2)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.3)
    assert weights.loc[index[3], "BTC"] == pytest.approx(0.4)
    assert weights.loc[index[4], "BTC"] == pytest.approx(0.0)


def test_donchian_breakout_strategy_requires_price_frame_for_stop_or_pyramiding_rules() -> None:
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(
            stop_loss_pct=0.08,
            risk_budget_pct=0.01,
            max_pyramids=1,
        )
    )
    index = pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0, float("nan")]}, index=index)

    with pytest.raises(ValueError):
        strategy.build_weights(signal)


def test_donchian_breakout_strategy_requires_factor_frames_for_trend_filter() -> None:
    strategy = DonchianBreakoutStrategy(
        DonchianBreakoutConfig(
            trend_factor="ma_distance_120",
            long_allocation=1.0,
            short_allocation=1.0,
        )
    )
    index = pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0, float("nan")]}, index=index)
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0]}, index=index)

    with pytest.raises(ValueError):
        strategy.build_weights(signal, price_frame=price_frame)


def test_momentum_rotation_strategy_builds_signal_and_weights() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    factors = {
        "ret_24": pd.DataFrame({"BTC": [0.08], "ETH": [-0.06], "SOL": [0.02]}, index=index),
        "ret_4": pd.DataFrame({"BTC": [0.03], "ETH": [-0.04], "SOL": [0.01]}, index=index),
        "breakout_20": pd.DataFrame({"BTC": [0.02], "ETH": [-0.03], "SOL": [0.00]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [68.0], "ETH": [32.0], "SOL": [48.0]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [0.4], "ETH": [0.3], "SOL": [-0.8]}, index=index),
    }
    strategy = MomentumRotationStrategy(
        MomentumRotationConfig(
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


def test_momentum_rotation_strategy_applies_liquidation_overlay() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="D", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0], "ETH": [-1.0], "SOL": [0.5]}, index=index)
    strategy = MomentumRotationStrategy(
        MomentumRotationConfig(
            max_long_positions=2,
            max_short_positions=1,
            long_allocation=0.5,
            short_allocation=0.5,
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


def test_momentum_rotation_strategy_version_changes_with_config() -> None:
    baseline = MomentumRotationStrategy(MomentumRotationConfig()).version()
    updated = MomentumRotationStrategy(MomentumRotationConfig(min_momentum=0.01)).version()
    assert baseline != updated


def test_small_cap_momentum_breakout_strategy_enters_and_times_out() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_10": pd.DataFrame(
            {"DOGE": [float("nan"), 1.0, float("nan"), float("nan")], "PEPE": [float("nan")] * 4},
            index=index,
        ),
        "ret_1": pd.DataFrame({"DOGE": [0.0, 0.03, 0.00, 0.00], "PEPE": [0.0, 0.03, 0.00, 0.00]}, index=index),
        "ret_4": pd.DataFrame({"DOGE": [0.0, 0.02, 0.00, 0.00], "PEPE": [0.0, 0.02, 0.00, 0.00]}, index=index),
        "volume_surge_20": pd.DataFrame(
            {"DOGE": [0.0, 3.0, 0.0, 0.0], "PEPE": [0.0, 3.0, 0.0, 0.0]},
            index=index,
        ),
        "rsi_14": pd.DataFrame(
            {"DOGE": [50.0, 68.0, 60.0, 55.0], "PEPE": [50.0, 68.0, 60.0, 55.0]},
            index=index,
        ),
        "amihud_illiquidity": pd.DataFrame(
            {"DOGE": [0.0, 0.000001, 0.0, 0.0], "PEPE": [0.0, 0.000001, 0.0, 0.0]},
            index=index,
        ),
    }
    price_frame = pd.DataFrame({"DOGE": [100.0, 104.0, 106.0, 107.0], "PEPE": [100.0] * 4}, index=index)
    strategy = SmallCapMomentumBreakoutStrategy(
        SmallCapMomentumBreakoutConfig(
            max_positions=1,
            long_allocation=0.3,
            stop_loss_pct=None,
            trailing_stop_pct=None,
            max_hold_bars=2,
            cooldown_bars=1,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert signal.loc[index[1], "DOGE"] > 0.0
    assert pd.isna(signal.loc[index[1], "PEPE"])
    assert weights.loc[index[0], "DOGE"] == pytest.approx(0.0)
    assert weights.loc[index[1], "DOGE"] == pytest.approx(0.3)
    assert weights.loc[index[2], "DOGE"] == pytest.approx(0.3)
    assert weights.loc[index[3], "DOGE"] == pytest.approx(0.0)


def test_small_cap_momentum_breakout_requires_price_frame_for_stops() -> None:
    strategy = SmallCapMomentumBreakoutStrategy(SmallCapMomentumBreakoutConfig(stop_loss_pct=0.06))
    index = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    signal = pd.DataFrame({"DOGE": [1.0]}, index=index)

    with pytest.raises(ValueError):
        strategy.build_weights(signal)


def test_spot_cta_trend_strategy_builds_long_only_trend_weights() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="4h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0], "ETH": [1.0], "SOL": [0.0]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02], "ETH": [0.02], "SOL": [0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame({"BTC": [20_000_000.0], "ETH": [15_000_000.0], "SOL": [30_000_000.0]}, index=index),
        "ma_distance_120": pd.DataFrame({"BTC": [0.05], "ETH": [0.03], "SOL": [-0.02]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [0.2], "ETH": [0.2], "SOL": [0.2]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [65.0], "ETH": [70.0], "SOL": [48.0]}, index=index),
        "amihud_illiquidity": pd.DataFrame({"BTC": [0.000001], "ETH": [0.000002], "SOL": [0.000001]}, index=index),
        "atr_pct_14": pd.DataFrame({"BTC": [0.04], "ETH": [0.05], "SOL": [0.03]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0], "ETH": [300.0], "SOL": [300.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0], "ETH": [50.0], "SOL": [25.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert signal.loc[index[0], "BTC"] > 0.0
    assert signal.loc[index[0], "ETH"] > 0.0
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[0], "ETH"] == pytest.approx(0.0)
    assert weights.loc[index[0], "SOL"] == pytest.approx(0.0)


def test_spot_cta_trend_treats_missing_donchian_breakout_as_neutral() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="4h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [float("nan")]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame({"BTC": [20_000_000.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0]}, index=index),
    }
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)

    assert signal.loc[index[0], "BTC"] == pytest.approx(0.0)


@pytest.mark.skip(reason="obsolete: simplified spot CTA now requires Donchian breakout only")
def test_spot_cta_trend_can_enter_pump_without_fresh_breakout() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [float("nan")], "ETH": [float("nan")]}, index=index),
        "ret_12": pd.DataFrame({"BTC": [0.11], "ETH": [0.03]}, index=index),
        "ret_4": pd.DataFrame({"BTC": [0.04], "ETH": [0.01]}, index=index),
        "ret_1": pd.DataFrame({"BTC": [0.01], "ETH": [-0.01]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [1.2], "ETH": [0.2]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [91.0], "ETH": [64.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0], "ETH": [300.0]}, index=index),
    }
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            acceleration_momentum_factor="ret_1",
            benchmark_momentum_factor=None,
            liquidity_rank_factor=None,
            require_breakout=False,
            acceleration_momentum_weight=0.8,
            max_positions=1,
            long_allocation=0.60,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)

    assert signal.loc[index[0], "BTC"] > 0.0
    assert signal.loc[index[0], "ETH"] == pytest.approx(0.0)


@pytest.mark.skip(reason="obsolete: simplified spot CTA removed donchian-only mode")
def test_spot_cta_trend_donchian_only_uses_breakout_factor_only() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    breakout = pd.DataFrame(
        {"BTC": [1.0, float("nan"), -1.0], "ETH": [float("nan"), 1.0, float("nan")]},
        index=index,
    )
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            donchian_only=True,
            breakout_factor="donchian_breakout_20",
        )
    )

    signal = strategy.build_signal_frame({"donchian_breakout_20": breakout})

    pd.testing.assert_frame_equal(signal, breakout)


@pytest.mark.skip(reason="obsolete: simplified spot CTA removed separate Donchian exit")
def test_spot_cta_trend_donchian_only_can_use_separate_exit_factor() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    entry = pd.DataFrame({"BTC": [1.0, float("nan"), float("nan")]}, index=index)
    exit_breakout = pd.DataFrame({"BTC": [float("nan"), float("nan"), -1.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            donchian_only=True,
            breakout_factor="donchian_breakout_20",
            donchian_exit_factor="donchian_breakout_10",
        )
    )

    signal = strategy.build_signal_frame(
        {
            "donchian_breakout_20": entry,
            "donchian_breakout_10": exit_breakout,
        }
    )

    assert signal.loc[index[0], "BTC"] == pytest.approx(1.0)
    assert pd.isna(signal.loc[index[1], "BTC"])
    assert signal.loc[index[2], "BTC"] == pytest.approx(-1.0)


@pytest.mark.skip(reason="obsolete: simplified spot CTA exits only on fixed stop")
def test_spot_cta_trend_donchian_only_exits_on_negative_breakout_only() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0, float("nan"), -1.0, float("nan")]}, index=index)
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 99.0, 98.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            donchian_only=True,
            max_positions=1,
            long_allocation=0.60,
            stop_loss_pct=None,
            cooldown_bars=0,
            exit_on_signal_loss=False,
            exit_on_negative_signal=True,
            entry_confirmation_bars=0,
        )
    )

    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.60)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.60)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[3], "BTC"] == pytest.approx(0.0)


def test_spot_cta_trend_exits_on_fixed_stop_loss() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0, float("nan"), float("nan"), float("nan")]}, index=index)
    price_frame = pd.DataFrame({"BTC": [100.0, 89.0, 92.0, 94.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.60,
            stop_loss_pct=0.10,
        )
    )

    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.60)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[3], "BTC"] == pytest.approx(0.0)


def test_spot_cta_trend_does_not_exit_on_profit_pullback_without_stop_loss() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0, float("nan"), float("nan"), float("nan")]}, index=index)
    price_frame = pd.DataFrame({"BTC": [100.0, 125.0, 106.0, 130.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.60,
            stop_loss_pct=None,
        )
    )

    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.60)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.60)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.60)
    assert weights.loc[index[3], "BTC"] == pytest.approx(0.60)


@pytest.mark.skip(reason="obsolete: simplified spot CTA no longer exits on signal loss")
def test_spot_cta_trend_strategy_exits_when_signal_is_lost() -> None:
    index = pd.date_range("2024-01-01", periods=8, freq="4h", tz="UTC")
    signal = pd.DataFrame({"BTC": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]}, index=index)
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
            cooldown_bars=0,
            entry_confirmation_bars=0,
        )
    )

    weights = strategy.build_weights(signal, price_frame=price_frame)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[5], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[6], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[7], "BTC"] == pytest.approx(0.70)


def test_spot_cta_trend_holds_after_breakout_without_momentum_exit() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0, float("nan"), float("nan")]}, index=index),
        "ret_72": pd.DataFrame({"BTC": [0.10, 0.08, -0.01]}, index=index),
        "ret_24": pd.DataFrame({"BTC": [0.04, 0.03, 0.00]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02, 0.02, 0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame({"BTC": [20_000_000.0, 20_000_000.0, 20_000_000.0]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [0.2, 0.1, 0.1]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [65.0, 62.0, 48.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0, 302.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 102.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert signal.loc[index[0], "BTC"] > 0.0
    assert signal.loc[index[1], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.70)


def test_spot_cta_trend_enters_breakout_immediately() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0, float("nan"), float("nan"), float("nan")]}, index=index),
        "ret_72": pd.DataFrame({"BTC": [0.10, 0.09, 0.08, 0.07]}, index=index),
        "ret_24": pd.DataFrame({"BTC": [0.04, 0.04, 0.03, 0.03]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02, 0.02, 0.02, 0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame(
            {"BTC": [20_000_000.0, 20_000_000.0, 20_000_000.0, 20_000_000.0]},
            index=index,
        ),
        "volume_surge_20": pd.DataFrame({"BTC": [0.2, 0.2, 0.2, 0.2]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [65.0, 64.0, 63.0, 62.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0, 302.0, 303.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 102.0, 103.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.70)


@pytest.mark.skip(reason="obsolete: simplified spot CTA buys at breakout bar close")
def test_spot_cta_trend_waits_one_bar_by_default() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0, float("nan"), float("nan")]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02, 0.02, 0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame({"BTC": [20_000_000.0, 20_000_000.0, 20_000_000.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0, 302.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 102.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
            cooldown_bars=0,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert signal.loc[index[0], "BTC"] > 0.0
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.70)


def test_spot_cta_trend_keeps_immediate_entry_after_pullback() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0, float("nan"), float("nan"), float("nan")]}, index=index),
        "ret_72": pd.DataFrame({"BTC": [0.10, 0.09, 0.08, 0.07]}, index=index),
        "ret_24": pd.DataFrame({"BTC": [0.04, 0.04, 0.03, 0.03]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02, 0.02, 0.02, 0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame(
            {"BTC": [20_000_000.0, 20_000_000.0, 20_000_000.0, 20_000_000.0]},
            index=index,
        ),
        "volume_surge_20": pd.DataFrame({"BTC": [0.2, 0.2, 0.2, 0.2]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [65.0, 64.0, 63.0, 62.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0, 302.0, 303.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 99.0, 96.0, 103.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert weights.loc[index[0], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[1], "BTC"] == pytest.approx(0.70)
    assert weights.loc[index[2], "BTC"] == pytest.approx(0.70)


@pytest.mark.skip(reason="obsolete: simplified spot CTA ranks only by 24h dollar volume")
def test_spot_cta_trend_prioritizes_strongest_entries() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame(
            {"BTC": [1.0, float("nan"), float("nan")], "ETH": [1.0, float("nan"), float("nan")]},
            index=index,
        ),
        "ret_72": pd.DataFrame({"BTC": [0.15, 0.14, 0.13], "ETH": [0.05, 0.05, 0.04]}, index=index),
        "ret_24": pd.DataFrame({"BTC": [0.08, 0.07, 0.06], "ETH": [0.02, 0.02, 0.01]}, index=index),
        "ret_1": pd.DataFrame({"BTC": [0.03, 0.03, 0.03], "ETH": [0.00, 0.00, 0.00]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02, 0.02, 0.02], "ETH": [0.02, 0.02, 0.02]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [0.8, 0.7, 0.6], "ETH": [0.0, 0.0, 0.0]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [65.0, 64.0, 63.0], "ETH": [62.0, 61.0, 60.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0, 302.0], "ETH": [300.0, 301.0, 302.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0, 102.0], "ETH": [50.0, 51.0, 52.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=2,
            long_allocation=0.70,
            stop_loss_pct=None,
            cooldown_bars=0,
            acceleration_momentum_factor="ret_1",
            liquidity_rank_factor=None,
            acceleration_momentum_weight=1.0,
            entry_confirmation_bars=0,
            entry_rank_limit=1,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert signal.loc[index[0], "BTC"] > signal.loc[index[0], "ETH"]
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.35)
    assert weights.loc[index[0], "ETH"] == pytest.approx(0.0)


def test_spot_cta_trend_prioritizes_higher_dollar_volume_entries_in_liquidity_band() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0, float("nan")], "ETH": [1.0, float("nan")]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02, 0.02], "ETH": [0.02, 0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame(
            {"BTC": [12_000_000.0, 12_000_000.0], "ETH": [50_000_000.0, 50_000_000.0]},
            index=index,
        ),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0], "ETH": [300.0, 301.0]}, index=index),
    }
    price_frame = pd.DataFrame({"BTC": [100.0, 101.0], "ETH": [50.0, 51.0]}, index=index)
    strategy = SpotCtaTrendStrategy(
        SpotCtaTrendConfig(
            max_positions=1,
            long_allocation=0.70,
            stop_loss_pct=None,
        )
    )

    signal = strategy.build_signal_frame(factors)
    weights = strategy.build_weights(signal, price_frame=price_frame, factors=factors)

    assert signal.loc[index[0], "ETH"] > signal.loc[index[0], "BTC"]
    assert weights.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert weights.loc[index[0], "ETH"] == pytest.approx(0.70)


def test_spot_cta_trend_blocks_entries_above_liquidity_band() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0], "ETH": [1.0]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [0.02], "ETH": [0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame({"BTC": [150_000_000.0], "ETH": [50_000_000.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0], "ETH": [300.0]}, index=index),
    }
    strategy = SpotCtaTrendStrategy(SpotCtaTrendConfig())

    signal = strategy.build_signal_frame(factors)

    assert signal.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert signal.loc[index[0], "ETH"] > 0.0


def test_spot_cta_trend_blocks_weak_benchmark_regime() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    factors = {
        "donchian_breakout_20": pd.DataFrame({"BTC": [1.0, 1.0]}, index=index),
        "ret_72": pd.DataFrame({"BTC": [0.10, 0.10]}, index=index),
        "ret_24": pd.DataFrame({"BTC": [0.04, 0.04]}, index=index),
        "benchmark_ret_24": pd.DataFrame({"BTC": [-0.04, -0.02]}, index=index),
        "dollar_volume_24": pd.DataFrame({"BTC": [20_000_000.0, 20_000_000.0]}, index=index),
        "volume_surge_20": pd.DataFrame({"BTC": [0.2, 0.2]}, index=index),
        "rsi_14": pd.DataFrame({"BTC": [65.0, 65.0]}, index=index),
        "age_bars": pd.DataFrame({"BTC": [300.0, 301.0]}, index=index),
    }
    strategy = SpotCtaTrendStrategy(SpotCtaTrendConfig())

    signal = strategy.build_signal_frame(factors)

    assert signal.loc[index[0], "BTC"] == pytest.approx(0.0)
    assert signal.loc[index[1], "BTC"] > 0.0


def test_strategy_registry_lists_builtin_strategies() -> None:
    names = list_registered_strategies()
    assert "trend_confirmation" in names
    assert "crowding_reversal" in names
    assert "ma_crossover" in names
    assert "donchian_breakout" in names
    assert "momentum_rotation" in names
    assert "small_cap_momentum_breakout" in names
    assert "spot_cta_trend" in names


def test_create_strategy_uses_registry() -> None:
    trend = create_strategy("trend_confirmation", {"max_long_positions": 1})
    crowding = create_strategy("crowding_reversal", {"max_short_positions": 1})
    crossover = create_strategy("ma_crossover", {"long_allocation": 0.75})
    donchian = create_strategy("donchian_breakout", {"long_allocation": 0.75})
    momentum = create_strategy("momentum_rotation", {"long_allocation": 0.75})
    small_cap = create_strategy("small_cap_momentum_breakout", {"long_allocation": 0.25})
    spot_cta = create_strategy("spot_cta_trend", {"long_allocation": 0.70})
    assert isinstance(trend, TrendConfirmationStrategy)
    assert isinstance(crowding, CrowdingReversalStrategy)
    assert isinstance(crossover, MovingAverageCrossoverStrategy)
    assert isinstance(donchian, DonchianBreakoutStrategy)
    assert isinstance(momentum, MomentumRotationStrategy)
    assert isinstance(small_cap, SmallCapMomentumBreakoutStrategy)
    assert isinstance(spot_cta, SpotCtaTrendStrategy)


def test_strategy_universe_can_be_configured_inside_strategy_options() -> None:
    strategy = create_strategy("ma_crossover", {"symbols": ["eth/usdt"]})
    assert strategy.default_symbols(exchange="binance", market_type=MarketType.SPOT) == ["ETH/USDT"]


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
