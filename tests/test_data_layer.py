from pathlib import Path

import pandas as pd

from signal_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType, normalize_dataset, write_dataframe


def _layout(tmp_path: Path) -> DataLakeLayout:
    return DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )


def test_normalize_dataset_adds_date_and_sorts() -> None:
    frame = pd.DataFrame(
        {
            "ts": ["2024-01-01T01:00:00Z", "2024-01-01T00:00:00Z"],
            "exchange": ["BINANCE", "BINANCE"],
            "symbol": ["btc/usdt", "btc/usdt"],
            "market_type": ["SPOT", "SPOT"],
            "open": [1.0, 1.0],
            "high": [1.1, 1.1],
            "low": [0.9, 0.9],
            "close": [1.0, 1.0],
            "volume": [10.0, 10.0],
            "source": ["CCXT", "CCXT"],
        }
    )
    normalized = normalize_dataset(DatasetKind.OHLCV, frame)
    assert normalized["exchange"].tolist() == ["binance", "binance"]
    assert normalized["symbol"].tolist() == ["BTC/USDT", "BTC/USDT"]
    assert normalized["date"].tolist() == ["2024-01-01", "2024-01-01"]
    assert normalized["ts"].is_monotonic_increasing


def test_warehouse_loads_written_dataset(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"),
            "exchange": ["binance"] * 3,
            "symbol": ["BTC/USDT"] * 3,
            "market_type": ["spot"] * 3,
            "open": [1.0, 2.0, 3.0],
            "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9],
            "close": [1.0, 2.0, 3.0],
            "volume": [100.0, 100.0, 100.0],
            "source": ["test"] * 3,
        }
    )
    write_dataframe(
        frame,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        partition_date=frame["ts"].max().date(),
    )
    loaded = DuckDBWarehouse(layout).load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
    )
    assert len(loaded) == 3
    assert loaded["close"].iloc[-1] == 3.0
