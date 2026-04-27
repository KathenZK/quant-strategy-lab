import pandas as pd
import pytest

from strategy_lab.data import aggregate_liquidation_events, enrich_liquidation_features, normalize_binance_force_order_events


def test_normalize_binance_force_order_events() -> None:
    payload = {
        "e": "forceOrder",
        "E": 1704067200000,
        "o": {
            "s": "BTCUSDT",
            "S": "SELL",
            "o": "LIMIT",
            "f": "IOC",
            "q": "0.010",
            "p": "43000",
            "ap": "43100",
            "z": "0.010",
            "T": 1704067200000,
        },
    }
    frame = normalize_binance_force_order_events(payload)
    assert len(frame) == 1
    assert frame["symbol"].iloc[0] == "BTC/USDT:USDT"
    assert frame["liquidation_side"].iloc[0] == "long"
    assert frame["notional"].iloc[0] == pytest.approx(431.0)


def test_aggregate_and_enrich_liquidation_features() -> None:
    events = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2024-01-01T00:05:00Z",
                    "2024-01-01T00:20:00Z",
                    "2024-01-01T01:05:00Z",
                    "2024-01-01T02:05:00Z",
                ]
            ),
            "exchange": ["binance"] * 4,
            "symbol": ["BTC/USDT:USDT"] * 4,
            "market_type": ["perp"] * 4,
            "base_asset": ["BTC"] * 4,
            "quote_asset": ["USDT"] * 4,
            "side": ["sell", "buy", "sell", "sell"],
            "price": [43000.0, 43100.0, 43200.0, 43300.0],
            "size": [0.01, 0.02, 0.10, 0.50],
            "notional": [430.0, 862.0, 4320.0, 21650.0],
            "source": ["test"] * 4,
        }
    )
    bars = aggregate_liquidation_events(events, frequency="1h")
    assert len(bars) == 3
    assert bars["liquidation_total_notional"].iloc[0] == pytest.approx(1292.0)

    index = pd.to_datetime(bars["ts"], utc=True)
    dollar_volume = pd.Series([100_000.0, 100_000.0, 100_000.0], index=index)
    open_interest = pd.Series([10_000.0, 9_000.0, 8_000.0], index=index)
    features = enrich_liquidation_features(
        bars,
        dollar_volume=dollar_volume,
        open_interest=open_interest,
        spike_window=2,
        cooldown_bars=2,
        spike_threshold=0.5,
        notional_ratio_threshold=0.1,
    )
    assert "liq_spike_zscore" in features.columns
    assert "event_cooldown_flag" in features.columns
    assert features["event_cooldown_flag"].iloc[-1] == 1
