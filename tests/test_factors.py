import pandas as pd
import pytest

from signal_lab.factors import (
    OpenInterestChangeFactor,
    PriceOpenInterestRegimeFactor,
    TrailingReturnFactor,
    default_registry,
)


def test_default_registry_contains_expected_factors() -> None:
    registry = default_registry()
    names = registry.names()
    assert "ret_1" in names
    assert "funding_rate" in names
    assert "price_oi_regime_4" in names


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
