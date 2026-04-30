from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import pytest

from strategy_lab.data import CCXTDataClient, DataIngestionService, DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType, normalize_dataset, write_dataframe
from strategy_lab.data.pipeline import drop_incomplete_ohlcv
from strategy_lab.features import FeatureBuilder, FeatureStore
from strategy_lab.factors import default_registry


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


def test_warehouse_keeps_ohlcv_timeframes_separate(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    index = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    base = pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * 2,
            "symbol": ["BTC/USDT"] * 2,
            "market_type": ["spot"] * 2,
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [100.0, 100.0],
            "source": ["test"] * 2,
        }
    )
    daily = base.assign(close=[10.0, 20.0])
    write_dataframe(
        base,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        partition_date=base["ts"].max().date(),
        timeframe="1h",
    )
    write_dataframe(
        daily,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        partition_date=daily["ts"].max().date(),
        timeframe="1d",
    )

    hourly_loaded = DuckDBWarehouse(layout).load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
    )
    daily_loaded = DuckDBWarehouse(layout).load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1d",
    )

    assert hourly_loaded["close"].tolist() == [1.0, 2.0]
    assert daily_loaded["close"].tolist() == [10.0, 20.0]
    assert "timeframe=1h" in str(layout.dataset_path(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
        partition_date=base["ts"].max().date(),
    ))


def test_feature_store_paths_include_data_identity(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    store = FeatureStore(layout)
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
            "exchange": ["binance"] * 2,
            "symbol": ["BTC/USDT"] * 2,
            "market_type": ["spot"] * 2,
            "timeframe": ["1h"] * 2,
            "ret_1": [0.0, 0.01],
        }
    )

    path = store.write_factor_frame(
        "ret_1",
        frame,
        exchange="binance",
        market_type="spot",
        symbol="BTC/USDT",
        timeframe="1h",
        factor_version="v1",
    )

    assert "version=v1" in str(path)
    assert "exchange=binance" in str(path)
    assert "symbol=btc_usdt" in str(path)
    assert "timeframe=1h" in str(path)


def test_drop_incomplete_ohlcv_removes_current_open_bar() -> None:
    frame = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"], utc=True),
            "close": [100.0, 101.0],
        }
    )

    closed = drop_incomplete_ohlcv(
        frame,
        timeframe="1h",
        now=pd.Timestamp("2024-01-01T01:30:00Z"),
    )

    assert closed["ts"].tolist() == [pd.Timestamp("2024-01-01T00:00:00Z")]


def test_fetch_ohlcv_paginates_from_since() -> None:
    start_ms = 1_704_067_200_000
    hour_ms = 60 * 60 * 1000

    class FakeExchange:
        def __init__(self) -> None:
            self.calls = []
            self.rows = [[start_ms + hour_ms * i, 1.0, 1.1, 0.9, 1.0 + i, 100.0] for i in range(5)]

        def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=1000):
            self.calls.append((symbol, timeframe, since, limit))
            rows = [row for row in self.rows if since is None or row[0] >= since]
            return rows[: min(limit, 2)]

    fake_exchange = FakeExchange()

    class FakeClient(CCXTDataClient):
        def _build_exchange(self):
            return fake_exchange

    frame = FakeClient(exchange_name="binance", market_type=MarketType.SPOT).fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="1h",
        since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        limit=5,
    )

    assert len(frame) == 5
    assert frame["close"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [call[2] for call in fake_exchange.calls] == [start_ms, start_ms + 2 * hour_ms, start_ms + 4 * hour_ms]


def test_fetch_basis_or_premium_merges_basis_and_premium_rows() -> None:
    class FakeExchange:
        def fapiDataGetBasis(self, params):
            assert params["pair"] == "BTCUSDT"
            return [
                {
                    "timestamp": 1704067200000,
                    "basis": "10.5",
                    "basisRate": "0.0012",
                    "annualizedBasisRate": "0.145",
                    "futuresPrice": "43100.5",
                    "indexPrice": "43090.0",
                }
            ]

        def fetch_premium_index_ohlcv(self, symbol, timeframe="1h", since=None, limit=1000):
            assert symbol == "BTC/USDT:USDT"
            return [[1704067200000, 0.0004, 0.0005, 0.0003, 0.00045, 0]]

    class FakeClient(CCXTDataClient):
        def _build_exchange(self):
            return FakeExchange()

    frame = FakeClient(exchange_name="binance", market_type=MarketType.PERP).fetch_basis_or_premium(
        symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=10,
    )
    assert len(frame) == 1
    assert frame["basis"].iloc[0] == 10.5
    assert frame["premium_index"].iloc[0] == 0.00045
    assert frame["quote_asset"].iloc[0] == "USDT"


def test_fetch_historical_liquidations_from_gate_contract_stats() -> None:
    class FakeExchange:
        markets = {
            "BTC/USDT:USDT": {
                "id": "BTC_USDT",
                "settleId": "usdt",
            }
        }

        def market(self, symbol):
            return self.markets[symbol]

        def publicFuturesGetSettleContractStats(self, params):
            assert params["contract"] == "BTC_USDT"
            return [
                {
                    "time": "1704067200",
                    "mark_price": "43000",
                    "long_liq_usd_new": "12000",
                    "short_liq_usd_new": "5000",
                }
            ]

    class FakeClient(CCXTDataClient):
        def _build_exchange(self):
            return FakeExchange()

    frame = FakeClient(exchange_name="gateio", market_type=MarketType.PERP).fetch_historical_liquidations(
        symbol="BTC/USDT:USDT",
        timeframe="4h",
        limit=100,
    )
    assert len(frame) == 2
    assert set(frame["side"]) == {"buy", "sell"}
    assert frame["notional"].sum() == pytest.approx(17000.0)


def test_refresh_basis_or_premium_writes_raw_and_normalized(tmp_path: Path, monkeypatch) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()

    def fake_fetch(self, *, symbol: str, timeframe: str = "1h", since=None, limit: int = 1000):
        return pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
                "exchange": ["binance", "binance"],
                "symbol": [symbol.upper(), symbol.upper()],
                "market_type": ["perp", "perp"],
                "base_asset": ["BTC", "BTC"],
                "quote_asset": ["USDT", "USDT"],
                "basis": [10.0, 11.0],
                "basis_rate": [0.001, 0.0011],
                "annualized_basis": [0.12, 0.13],
                "futures_price": [43000.0, 43100.0],
                "index_price": [42990.0, 43090.0],
                "mark_price": [43001.0, 43101.0],
                "premium_index": [0.0004, 0.0005],
                "source": ["binance_api", "binance_api"],
            }
        )

    monkeypatch.setattr(CCXTDataClient, "fetch_basis_or_premium", fake_fetch)
    result = DataIngestionService(layout).refresh_basis_or_premium(
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=2,
    )
    assert Path(result["raw"]).exists()
    assert Path(result["normalized"]).exists()


def test_warehouse_merged_market_frame_includes_basis_data(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    ohlcv = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
            "exchange": ["binance", "binance"],
            "symbol": ["BTC/USDT:USDT", "BTC/USDT:USDT"],
            "market_type": ["perp", "perp"],
            "base_asset": ["BTC", "BTC"],
            "quote_asset": ["USDT", "USDT"],
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [100.0, 100.0],
            "source": ["test", "test"],
        }
    )
    basis = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
            "exchange": ["binance", "binance"],
            "symbol": ["BTC/USDT:USDT", "BTC/USDT:USDT"],
            "market_type": ["perp", "perp"],
            "base_asset": ["BTC", "BTC"],
            "quote_asset": ["USDT", "USDT"],
            "basis": [10.0, 11.0],
            "basis_rate": [0.001, 0.0011],
            "annualized_basis": [0.12, 0.13],
            "futures_price": [43000.0, 43100.0],
            "index_price": [42990.0, 43090.0],
            "mark_price": [43001.0, 43101.0],
            "premium_index": [0.0004, 0.0005],
            "source": ["test", "test"],
        }
    )
    write_dataframe(
        ohlcv,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="BTC/USDT:USDT",
        partition_date=ohlcv["ts"].max().date(),
    )
    write_dataframe(
        basis,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.BASIS,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="BTC/USDT:USDT",
        partition_date=basis["ts"].max().date(),
    )
    merged = DuckDBWarehouse(layout).merged_market_frame(
        exchange="binance",
        symbol="BTC/USDT:USDT",
        market_type=MarketType.PERP,
    )
    assert "basis" in merged.columns
    assert "premium_index" in merged.columns
    assert merged["basis"].iloc[-1] == 11.0


def test_feature_builder_forward_fills_perp_fields(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    ohlcv = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
            "exchange": ["binance"] * 4,
            "symbol": ["BTC/USDT:USDT"] * 4,
            "market_type": ["perp"] * 4,
            "base_asset": ["BTC"] * 4,
            "quote_asset": ["USDT"] * 4,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.0, 101.0, 102.0, 103.0],
            "volume": [1_000.0] * 4,
            "source": ["test"] * 4,
        }
    )
    funding = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T02:00:00Z"]),
            "exchange": ["binance", "binance"],
            "symbol": ["BTC/USDT:USDT", "BTC/USDT:USDT"],
            "market_type": ["perp", "perp"],
            "base_asset": ["BTC", "BTC"],
            "quote_asset": ["USDT", "USDT"],
            "funding_rate": [0.001, 0.002],
            "next_funding_ts": pd.to_datetime(["2024-01-01T08:00:00Z", "2024-01-01T16:00:00Z"]),
            "source": ["test", "test"],
        }
    )
    write_dataframe(
        ohlcv,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="BTC/USDT:USDT",
        partition_date=ohlcv["ts"].max().date(),
    )
    write_dataframe(
        funding,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="BTC/USDT:USDT",
        partition_date=funding["ts"].max().date(),
    )
    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    frame = builder.load_symbol_frame(
        exchange="binance",
        symbol="BTC/USDT:USDT",
        market_type=MarketType.PERP,
    )
    assert frame["funding_rate"].tolist() == [0.001, 0.001, 0.002, 0.002]


def test_warehouse_load_liquidation_features(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    ohlcv = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"),
            "exchange": ["binance"] * 3,
            "symbol": ["BTC/USDT:USDT"] * 3,
            "market_type": ["perp"] * 3,
            "base_asset": ["BTC"] * 3,
            "quote_asset": ["USDT"] * 3,
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 101.0, 102.0],
            "volume": [1_000_000.0] * 3,
            "source": ["test"] * 3,
        }
    )
    liqs = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2024-01-01T00:10:00Z",
                    "2024-01-01T01:15:00Z",
                ]
            ),
            "exchange": ["binance", "binance"],
            "symbol": ["BTC/USDT:USDT", "BTC/USDT:USDT"],
            "market_type": ["perp", "perp"],
            "base_asset": ["BTC", "BTC"],
            "quote_asset": ["USDT", "USDT"],
            "side": ["sell", "buy"],
            "price": [43000.0, 43200.0],
            "size": [0.01, 0.02],
            "notional": [430.0, 864.0],
            "source": ["test", "test"],
        }
    )
    write_dataframe(
        ohlcv,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="BTC/USDT:USDT",
        partition_date=ohlcv["ts"].max().date(),
    )
    write_dataframe(
        liqs,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.LIQUIDATIONS,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="BTC/USDT:USDT",
        partition_date=pd.Timestamp("2024-01-01T01:15:00Z").date(),
    )
    features = DuckDBWarehouse(layout).load_liquidation_features(
        exchange="binance",
        symbol="BTC/USDT:USDT",
        market_type=MarketType.PERP,
        spike_window=2,
        cooldown_bars=2,
        spike_threshold=0.1,
        notional_ratio_threshold=0.0001,
    )
    assert len(features) == 3
    assert "event_cooldown_flag" in features.columns
    assert features["liquidation_total_notional"].sum() == pytest.approx(1294.0)
