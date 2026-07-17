from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.data.factors.multi_asset_1h import multi_asset_1h_registry


def market_frame(rows: int = 900) -> pd.DataFrame:
    index = np.arange(rows, dtype="float64")
    close = 100.0 * np.exp(0.0002 * index + 0.01 * np.sin(index / 17.0))
    open_price = close * (1.0 + 0.001 * np.sin(index / 5.0))
    high = np.maximum(open_price, close) * 1.002
    low = np.minimum(open_price, close) * 0.998
    volume = 1_000.0 + 100.0 * np.cos(index / 11.0)
    quote_volume = volume * (open_price + close) / 2.0
    return pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=rows, freq="1h", tz="UTC"),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "quote_volume": quote_volume,
            "trade_count": 5_000.0 + index,
            "taker_buy_volume": volume * (0.5 + 0.1 * np.sin(index / 9.0)),
            "taker_buy_quote_volume": quote_volume
            * (0.5 + 0.1 * np.sin(index / 9.0)),
            "vwap": quote_volume / volume,
            "mark_price": close * (1.0 + 0.0001 * np.cos(index / 13.0)),
            "funding_rate": 0.0001 * np.sin(index / 8.0),
        }
    )


def test_multi_asset_1h_registry_is_large_and_unique() -> None:
    registry = multi_asset_1h_registry()

    assert len(registry.names()) == 142
    assert len(registry.names()) == len(set(registry.names()))
    assert "taker_imbalance_mean_24" in registry.names()
    assert "mark_premium_zscore_168" in registry.names()
    assert "funding_mean_72" in registry.names()


def test_multi_asset_1h_factors_do_not_read_future_rows() -> None:
    registry = multi_asset_1h_registry()
    original = market_frame()
    perturbed = original.copy()
    future = perturbed.index >= 820
    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
        "vwap",
        "mark_price",
        "funding_rate",
    ]:
        perturbed.loc[future, column] = perturbed.loc[future, column] * 3.0 + 7.0

    for name in registry.names():
        factor = registry.get(name)
        left = factor.compute(original)
        right = factor.compute(perturbed)
        pd.testing.assert_series_equal(
            left.iloc[:820],
            right.iloc[:820],
            check_names=False,
            check_dtype=False,
            obj=name,
        )
