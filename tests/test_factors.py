import pandas as pd
import pytest

from strategy_lab.data.factors import (
    AmihudIlliquidityFactor,
    AverageDollarVolumeFactor,
    ATRPercentFactor,
    BearishCandleCountFactor,
    BasisChangeFactor,
    BasisZScoreFactor,
    BenchmarkReturnFactor,
    BullishCandleCountFactor,
    DonchianBreakoutFactor,
    DonchianBreakoutStrengthFactor,
    FundingRateZScoreFactor,
    OpenInterestZScoreFactor,
    RelativeStrengthFactor,
    OpenInterestChangeFactor,
    PriceOpenInterestRegimeFactor,
    RollingDollarVolumeFactor,
    RSIFactor,
    TrailingReturnFactor,
    compute_factor_bundle,
    default_registry,
    list_registered_factor_providers,
)
from strategy_lab.data.factors.hype_15m import build_hype_15m_factors, hype_15m_registry


def test_default_registry_contains_expected_factors() -> None:
    registry = default_registry()
    names = registry.names()
    assert len(names) >= 18
    assert "ret_1" in names
    assert "funding_rate" in names
    assert "funding_zscore_72" in names
    assert "oi_zscore_72" in names
    assert "basis_change_4" in names
    assert "basis_zscore_72" in names
    assert "ma_distance_30" in names
    assert "ma_distance_90" in names
    assert "ma_distance_120" in names
    assert "price_oi_regime_4" in names
    assert "relative_strength_24" in names
    assert "donchian_breakout_10" in names
    assert "donchian_breakout_12" in names
    assert "donchian_breakout_14" in names
    assert "donchian_breakout_20" in names
    assert "donchian_breakout_55" in names
    assert "donchian_breakout_strength_20" in names
    assert "ret_6" in names
    assert "ret_12" in names
    assert "ret_72" in names
    assert "ret_168" in names
    assert "benchmark_ret_24" in names
    assert "benchmark_ret_72" in names
    assert "bullish_candle_count_10" in names
    assert "bearish_candle_count_10" in names
    assert "ma_distance_48" in names
    assert "atr_pct_14" in names
    assert "avg_dollar_volume_20" in names
    assert "dollar_volume_1" in names
    assert "dollar_volume_24" in names


def test_builtin_factor_providers_are_discovered() -> None:
    providers = list_registered_factor_providers()
    assert "builtin_cross_sectional_factors" in providers
    assert "builtin_derivatives_factors" in providers
    assert "builtin_liquidity_factors" in providers
    assert "builtin_mean_reversion_factors" in providers
    assert "builtin_momentum_factors" in providers


def test_trailing_return_factor_uses_pct_change() -> None:
    frame = pd.DataFrame({"close": [100.0, 110.0, 121.0]})
    result = TrailingReturnFactor(periods=1).compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.10)
    assert result.iloc[2] == pytest.approx(0.10)


def test_benchmark_return_factor_uses_benchmark_close() -> None:
    frame = pd.DataFrame({"close": [50.0, 55.0, 60.5], "benchmark_close": [100.0, 110.0, 121.0]})
    result = BenchmarkReturnFactor(periods=1).compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.10)
    assert result.iloc[2] == pytest.approx(0.10)


def test_factor_version_changes_when_compute_logic_changes() -> None:
    factor = TrailingReturnFactor(periods=24)
    baseline_version = factor.version()
    baseline_spec = factor.spec()
    assert "source_hash" in baseline_spec
    assert baseline_spec["source_hash"]

    original_compute = TrailingReturnFactor.compute

    def patched_compute(self, frame):
        return frame[self.price_column].pct_change(self.periods).fillna(0.0)

    try:
        TrailingReturnFactor.compute = patched_compute
        mutated_version = TrailingReturnFactor(periods=24).version()
    finally:
        TrailingReturnFactor.compute = original_compute

    assert mutated_version != baseline_version, (
        "Factor.version() must change when compute() implementation changes, "
        "otherwise feature caches silently keep the stale values."
    )


def test_open_interest_change_factor() -> None:
    frame = pd.DataFrame({"open_interest": [100.0, 100.0, 120.0, 144.0]})
    result = OpenInterestChangeFactor(periods=2).compute(frame)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.20)
    assert result.iloc[3] == pytest.approx(0.44)


def test_open_interest_zscore_factor() -> None:
    frame = pd.DataFrame({"open_interest": [100.0, 110.0, 120.0, 130.0]})
    result = OpenInterestZScoreFactor(window=3).compute(frame)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(1.0)
    assert result.iloc[3] == pytest.approx(1.0)


def test_price_open_interest_regime_factor() -> None:
    frame = pd.DataFrame(
        {
            "close": [100.0, 110.0, 90.0, 80.0],
            "open_interest": [100.0, 110.0, 120.0, 100.0],
        }
    )
    factor = PriceOpenInterestRegimeFactor(periods=1)
    result = factor.compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == 2.0
    assert result.iloc[2] == -2.0
    assert result.iloc[3] == -1.0


def test_basis_change_factor_uses_pct_change() -> None:
    frame = pd.DataFrame({"basis": [10.0, 12.0, 15.0]})
    result = BasisChangeFactor(periods=1).compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.20)
    assert result.iloc[2] == pytest.approx(0.25)


def test_basis_zscore_factor_uses_rolling_window() -> None:
    frame = pd.DataFrame({"basis": [10.0, 11.0, 12.0, 13.0]})
    result = BasisZScoreFactor(window=3).compute(frame)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(1.0)
    assert result.iloc[3] == pytest.approx(1.0)


def test_funding_rate_zscore_factor_uses_rolling_window() -> None:
    frame = pd.DataFrame({"funding_rate": [0.001, 0.002, 0.003, 0.004]})
    result = FundingRateZScoreFactor(window=3).compute(frame)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(1.0)
    assert result.iloc[3] == pytest.approx(1.0)


def test_relative_strength_factor_uses_benchmark() -> None:
    frame = pd.DataFrame(
        {
            "close": [100.0, 110.0, 121.0],
            "benchmark_close": [100.0, 105.0, 110.25],
        }
    )
    result = RelativeStrengthFactor(periods=1).compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx((110.0 / 100.0 - 1.0) - (105.0 / 100.0 - 1.0))


def test_donchian_breakout_factor_signals_on_new_extremes() -> None:
    closes = [100.0, 101.0, 99.0, 102.0, 98.0, 105.0, 96.0]
    frame = pd.DataFrame({"close": closes})
    result = DonchianBreakoutFactor(window=3).compute(frame)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert pd.isna(result.iloc[2])
    assert result.iloc[3] == pytest.approx(1.0)
    assert result.iloc[4] == pytest.approx(-1.0)
    assert result.iloc[5] == pytest.approx(1.0)
    assert result.iloc[6] == pytest.approx(-1.0)


def test_donchian_breakout_factor_holds_when_inside_range() -> None:
    frame = pd.DataFrame({"close": [100.0, 101.0, 99.0, 100.5]})
    result = DonchianBreakoutFactor(window=3).compute(frame)
    assert pd.isna(result.iloc[3])


def test_donchian_breakout_factor_uses_intrabar_high_for_new_high() -> None:
    frame = pd.DataFrame(
        {
            "close": [100.0, 101.0, 99.0, 100.5],
            "high": [100.5, 101.5, 99.5, 102.0],
            "low": [99.5, 100.5, 98.5, 100.0],
        }
    )
    result = DonchianBreakoutFactor(window=3).compute(frame)

    assert result.iloc[3] == pytest.approx(1.0)


def test_candle_count_factors_count_recent_bullish_and_bearish_candles() -> None:
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 12.0, 11.0, 10.0, 9.0, 8.0, 8.0, 7.0, 7.0],
            "close": [11.0, 11.0, 11.0, 12.0, 11.0, 10.0, 7.0, 9.0, 8.0, 6.0],
        }
    )

    bullish = BullishCandleCountFactor(window=10).compute(frame)
    bearish = BearishCandleCountFactor(window=10).compute(frame)

    assert pd.isna(bullish.iloc[8])
    assert bullish.iloc[9] == pytest.approx(7.0)
    assert bearish.iloc[9] == pytest.approx(3.0)


def test_rsi_factor_handles_one_way_and_flat_markets() -> None:
    up = RSIFactor(window=2).compute(pd.DataFrame({"close": [100.0, 101.0, 102.0]}))
    flat = RSIFactor(window=2).compute(pd.DataFrame({"close": [100.0, 100.0, 100.0]}))

    assert up.iloc[-1] == pytest.approx(100.0)
    assert flat.iloc[-1] == pytest.approx(50.0)


def test_hype_15m_library_has_versioned_metadata_and_unique_names() -> None:
    factors = build_hype_15m_factors()
    names = [factor.metadata.name for factor in factors]

    assert len(factors) >= 100
    assert len(names) == len(set(names))
    assert all(factor.metadata.frequency == "15m" for factor in factors)
    assert all(factor.metadata.formula for factor in factors)
    assert all(factor.metadata.direction for factor in factors)
    assert all(factor.version() for factor in factors)


def test_hype_15m_donchian_factor_uses_prior_channel() -> None:
    factor = hype_15m_registry().get("donchian_position_20")
    frame = pd.DataFrame(
        {
            "high": [10.0] * 20 + [20.0],
            "low": [8.0] * 20 + [19.0],
            "close": [9.0] * 20 + [19.5],
        }
    )

    result = factor.compute(frame)

    assert pd.isna(result.iloc[19])
    assert result.iloc[20] == pytest.approx((19.5 - 8.0) / (10.0 - 8.0))


def test_amihud_illiquidity_factor_is_positive() -> None:
    frame = pd.DataFrame({"close": [100.0, 110.0, 121.0], "volume": [10_000.0, 15_000.0, 20_000.0]})
    result = AmihudIlliquidityFactor().compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] > 0
    assert result.iloc[2] > 0


def test_average_dollar_volume_factor_uses_close_times_volume() -> None:
    frame = pd.DataFrame({"close": [10.0, 11.0, 12.0], "volume": [100.0, 200.0, 300.0]})
    result = AverageDollarVolumeFactor(window=2).compute(frame)

    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx((1000.0 + 2200.0) / 2.0)
    assert result.iloc[2] == pytest.approx((2200.0 + 3600.0) / 2.0)


def test_rolling_dollar_volume_factor_uses_close_times_volume_sum() -> None:
    frame = pd.DataFrame({"close": [10.0, 11.0, 12.0], "volume": [100.0, 200.0, 300.0]})
    result = RollingDollarVolumeFactor(window=2).compute(frame)

    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(1000.0 + 2200.0)
    assert result.iloc[2] == pytest.approx(2200.0 + 3600.0)


def test_atr_percent_factor_normalizes_true_range_by_close() -> None:
    frame = pd.DataFrame(
        {
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.0, 11.0, 12.0],
        }
    )
    result = ATRPercentFactor(window=2).compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(2.0 / 11.0)


def test_donchian_breakout_strength_requires_close_confirmed_new_high() -> None:
    frame = pd.DataFrame(
        {
            "high": [10.0, 11.0, 12.0, 13.0, 15.0],
            "low": [9.0, 9.5, 10.0, 11.0, 13.0],
            "close": [9.5, 10.5, 11.0, 12.0, 14.0],
        }
    )
    result = DonchianBreakoutStrengthFactor(window=3, atr_window=2).compute(frame)

    assert pd.isna(result.iloc[3])
    prior_high = 13.0
    breakout_pct = 14.0 / prior_high - 1.0
    atr = (2.0 + 3.0) / 2.0
    atr_pct = atr / 14.0
    assert result.iloc[4] == pytest.approx(breakout_pct / atr_pct)


def test_compute_factor_bundle_adds_expected_columns() -> None:
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC").tolist() * 2,
            "symbol": ["BTC/USDT"] * 5 + ["ETH/USDT"] * 5,
            "exchange": ["binance"] * 10,
            "market_type": ["spot"] * 10,
            "close": [100, 101, 102, 103, 104, 50, 51, 52, 53, 54],
            "volume": [1000] * 10,
            "vwap": [100, 101, 102, 103, 104, 50, 51, 52, 53, 54],
            "benchmark_close": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
        }
    )
    bundle = compute_factor_bundle(frame, default_registry(), factor_names=["ret_1", "vwap_distance"])
    assert "ret_1" in bundle.columns
    assert "vwap_distance" in bundle.columns
    assert len(bundle) == len(frame)
