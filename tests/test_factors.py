import pandas as pd
import pytest

from signal_lab.factors import (
    AmihudIlliquidityFactor,
    RelativeStrengthFactor,
    OpenInterestChangeFactor,
    PriceOpenInterestRegimeFactor,
    TrailingReturnFactor,
    compute_factor_bundle,
    default_registry,
)


def test_default_registry_contains_expected_factors() -> None:
    registry = default_registry()
    names = registry.names()
    assert len(names) >= 12
    assert "ret_1" in names
    assert "funding_rate" in names
    assert "price_oi_regime_4" in names
    assert "relative_strength_24" in names


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


def test_amihud_illiquidity_factor_is_positive() -> None:
    frame = pd.DataFrame({"close": [100.0, 110.0, 121.0], "volume": [10_000.0, 15_000.0, 20_000.0]})
    result = AmihudIlliquidityFactor().compute(frame)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] > 0
    assert result.iloc[2] > 0


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
