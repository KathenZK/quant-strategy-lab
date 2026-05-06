import pandas as pd
import pytest

from strategy_lab.data.factors import (
    AmihudIlliquidityFactor,
    ATRPercentFactor,
    BasisChangeFactor,
    BasisZScoreFactor,
    DonchianBreakoutFactor,
    FundingRateZScoreFactor,
    OpenInterestZScoreFactor,
    RelativeStrengthFactor,
    OpenInterestChangeFactor,
    PriceOpenInterestRegimeFactor,
    RSIFactor,
    TrailingReturnFactor,
    compute_factor_bundle,
    default_registry,
    list_registered_factor_providers,
)


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
    assert "ret_6" in names
    assert "ret_12" in names
    assert "ret_72" in names
    assert "ret_168" in names
    assert "ma_distance_48" in names
    assert "atr_pct_14" in names


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


def test_rsi_factor_handles_one_way_and_flat_markets() -> None:
    up = RSIFactor(window=2).compute(pd.DataFrame({"close": [100.0, 101.0, 102.0]}))
    flat = RSIFactor(window=2).compute(pd.DataFrame({"close": [100.0, 100.0, 100.0]}))

    assert up.iloc[-1] == pytest.approx(100.0)
    assert flat.iloc[-1] == pytest.approx(50.0)


def test_amihud_illiquidity_factor_is_positive() -> None:
    frame = pd.DataFrame({"close": [100.0, 110.0, 121.0], "volume": [10_000.0, 15_000.0, 20_000.0]})
    result = AmihudIlliquidityFactor().compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] > 0
    assert result.iloc[2] > 0


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
