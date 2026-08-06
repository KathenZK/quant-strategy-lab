from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.data import (
    DataAuthenticityAuditor,
    DataLakeLayout,
    DatasetKind,
    DuckDBWarehouse,
    DuplicatePolicy,
    MarketType,
    OHLCVDerivationPolicy,
    OHLCVSessionPolicy,
    audit_ohlcv_frame,
    audit_raw_normalized_ohlcv,
    expected_ohlcv_session_bars,
    normalize_dataset,
    validate_frame,
    write_dataframe,
    write_normalized_dataframe,
)
from strategy_lab.data.features import FeatureBuilder, FeatureStore
from strategy_lab.data.factors import compute_factor_bundle, default_registry


def _layout(tmp_path: Path) -> DataLakeLayout:
    return DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        cache_dir=tmp_path / "cache",
    )


def _complete_ohlcv(frame: pd.DataFrame, *, timeframe: str = "1h") -> pd.DataFrame:
    completed = frame.copy()
    completed["timeframe"] = timeframe
    completed["quote_volume"] = completed["close"] * completed["volume"]
    completed["trade_count"] = 1
    completed["vwap"] = completed["close"]
    completed["is_closed"] = True
    return completed


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
    frame = _complete_ohlcv(frame)
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
    frame = _complete_ohlcv(frame)
    write_dataframe(
        frame,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
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
    base = _complete_ohlcv(base)
    daily = base.assign(
        timeframe="1d",
        open=[10.0, 20.0],
        high=[10.1, 20.1],
        low=[9.9, 19.9],
        close=[10.0, 20.0],
        quote_volume=[1000.0, 2000.0],
        vwap=[10.0, 20.0],
    )
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
    canonical_path = layout.dataset_path(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
        partition_date=base["ts"].max().date(),
    )
    assert "timeframe=1h" in str(canonical_path)
    assert "/symbol=btc_usdt/" not in str(canonical_path)
    assert canonical_path.name == "symbol=btc_usdt.parquet"


def test_equity_ohlcv_source_partitions_are_filterable(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    index = pd.date_range("2026-01-02 14:30:00", periods=2, freq="15min", tz="UTC")
    base = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": index,
                "exchange": ["nasdaq"] * 2,
                "symbol": ["MU"] * 2,
                "market_type": ["equity"] * 2,
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000.0, 1100.0],
                "source": ["polygon_api"] * 2,
            }
        ),
        timeframe="15m",
    )
    path = write_dataframe(
        base,
        layout=layout,
        layer="raw",
        kind=DatasetKind.OHLCV,
        exchange="nasdaq",
        market_type=MarketType.EQUITY,
        symbol="MU",
        timeframe="15m",
        source="polygon_api",
        partition_date=index[0].date(),
    )

    loaded = DuckDBWarehouse(layout).load_dataset(
        layer="raw",
        kind=DatasetKind.OHLCV,
        exchange="nasdaq",
        market_type=MarketType.EQUITY,
        symbol="MU",
        timeframe="15m",
        source="polygon_api",
    )

    assert "market_type=equity" in str(path)
    assert "source=polygon_api" in str(path)
    assert loaded["source"].unique().tolist() == ["polygon_api"]
    assert loaded["close"].tolist() == [100.5, 101.5]


def test_data_authenticity_auditor_quarantines_non_real_sources(tmp_path: Path) -> None:
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
            "source": ["ccxt", "proxy_vendor", "unknown_vendor"],
        }
    )
    frame = _complete_ohlcv(frame)
    write_dataframe(
        frame,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        partition_date=frame["ts"].max().date(),
        timeframe="1h",
    )

    auditor = DataAuthenticityAuditor(layout)
    dry_run = auditor.audit()
    with pytest.raises(ValueError, match="confirm_destructive"):
        auditor.clean(
            dry_run=False,
            quarantine_unverified_features=False,
            quarantine_duckdb=False,
        )
    clean = auditor.clean(
        dry_run=False,
        confirm_destructive=True,
        quarantine_unverified_features=False,
        quarantine_duckdb=False,
    )
    verified = auditor.audit()
    loaded = DuckDBWarehouse(layout).load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
    )
    quarantine_files = list(
        (layout.root_dir / "_quarantine" / "non_real_sources").rglob("*.parquet")
    )

    assert dry_run.blocked_rows == 2
    assert clean.blocked_rows == 2
    assert verified.blocked_rows == 0
    assert loaded["source"].unique().tolist() == ["ccxt"]
    assert len(quarantine_files) == 1


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


def test_feature_store_loads_filtered_factor_from_direct_partition(
    tmp_path: Path,
) -> None:
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
    store.write_factor_frame(
        "ret_1",
        frame,
        exchange="binance",
        market_type="spot",
        symbol="BTC/USDT",
        timeframe="1h",
        factor_version="v1",
    )

    loaded = store.load_factor_frame(
        "ret_1",
        exchange="binance",
        market_type="spot",
        symbol="BTC/USDT",
        timeframe="1h",
        factor_version="v1",
    )

    assert loaded["symbol"].tolist() == ["BTC/USDT", "BTC/USDT"]
    assert loaded["ret_1"].tolist() == [0.0, 0.01]


def test_age_bars_factor_increments_per_symbol() -> None:
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"),
            "exchange": ["binance"] * 3,
            "symbol": ["BTC/USDT"] * 3,
            "market_type": ["spot"] * 3,
            "timeframe": ["1h"] * 3,
        }
    )

    bundle = compute_factor_bundle(frame, default_registry(), factor_names=["age_bars"])

    assert bundle["age_bars"].tolist() == [1.0, 2.0, 3.0]


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
    ohlcv = _complete_ohlcv(ohlcv)
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
        timeframe="1h",
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
    ohlcv = _complete_ohlcv(ohlcv)
    funding = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T02:00:00Z"]),
            "exchange": ["binance", "binance"],
            "symbol": ["BTC/USDT:USDT", "BTC/USDT:USDT"],
            "market_type": ["perp", "perp"],
            "base_asset": ["BTC", "BTC"],
            "quote_asset": ["USDT", "USDT"],
            "funding_rate": [0.001, 0.002],
            "next_funding_ts": pd.to_datetime(
                ["2024-01-01T08:00:00Z", "2024-01-01T16:00:00Z"]
            ),
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
        timeframe="1h",
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
    ohlcv = _complete_ohlcv(ohlcv)
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
        timeframe="1h",
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


def test_ohlcv_missing_quality_fields_are_rejected_by_default() -> None:
    frame = pd.DataFrame(
        {
            "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "exchange": ["binance"],
            "symbol": ["BTC/USDT"],
            "market_type": ["spot"],
            "timeframe": ["1h"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [2.0],
            "source": ["ccxt"],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        normalize_dataset(DatasetKind.OHLCV, frame)


def test_explicit_ohlcv_derivation_persists_provenance() -> None:
    frame = pd.DataFrame(
        {
            "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "exchange": ["binance"],
            "symbol": ["BTC/USDT"],
            "market_type": ["spot"],
            "timeframe": ["1h"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [2.0],
            "trade_count": [7],
            "is_closed": [True],
            "source": ["ccxt"],
        }
    )
    policy = OHLCVDerivationPolicy(
        derive_quote_volume=True,
        derive_vwap=True,
        reason="vendor export omitted quote aggregates",
        source_dataset_id="test-fixture-ohlcv-v1",
        generated_at="2024-01-01T01:00:00Z",
        code_hash="sha256:test",
    )

    normalized = normalize_dataset(
        DatasetKind.OHLCV,
        frame,
        ohlcv_derivation=policy,
    )

    assert normalized.loc[0, "quote_volume"] == 200.0
    assert normalized.loc[0, "vwap"] == 100.0
    assert "close * volume" in normalized.loc[0, "derivation_provenance"]
    assert normalized.loc[0, "quality_flags"] == (
        "derived_quote_volume_proxy|derived_vwap_proxy"
    )


def test_trade_count_and_is_closed_cannot_be_derived() -> None:
    frame = pd.DataFrame(
        {
            "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "exchange": ["binance"],
            "symbol": ["BTC/USDT"],
            "market_type": ["spot"],
            "timeframe": ["1h"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [2.0],
            "quote_volume": [200.0],
            "vwap": [100.0],
            "source": ["ccxt"],
        }
    )

    with pytest.raises(ValueError, match="trade_count.*is_closed"):
        normalize_dataset(
            DatasetKind.OHLCV,
            frame,
            ohlcv_derivation=OHLCVDerivationPolicy(
                derive_quote_volume=True,
                derive_vwap=True,
                reason="explicit proxy test",
                source_dataset_id="test-fixture-ohlcv-v1",
                generated_at="2024-01-01T01:00:00Z",
                code_hash="sha256:test",
            ),
        )


def test_invalid_numeric_value_is_not_silently_coerced() -> None:
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT"],
                "market_type": ["spot"],
                "open": ["not-a-number"],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [2.0],
                "source": ["ccxt"],
            }
        )
    )

    with pytest.raises(ValueError, match="invalid numeric value in column open"):
        normalize_dataset(DatasetKind.OHLCV, frame)


def test_unknown_closed_state_is_rejected() -> None:
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT"],
                "market_type": ["spot"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [2.0],
                "source": ["ccxt"],
            }
        )
    )
    frame["is_closed"] = pd.Series([pd.NA], dtype="boolean")

    with pytest.raises(ValueError, match="critical nulls"):
        normalize_dataset(DatasetKind.OHLCV, frame)


def test_duplicate_business_keys_require_explicit_policy() -> None:
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00Z")] * 2,
                "exchange": ["binance"] * 2,
                "symbol": ["BTC/USDT"] * 2,
                "market_type": ["spot"] * 2,
                "timeframe": ["1h"] * 2,
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.0, 101.0],
                "volume": [2.0, 3.0],
                "source": ["ccxt"] * 2,
            }
        )
    )

    with pytest.raises(ValueError, match="duplicate business keys"):
        normalize_dataset(DatasetKind.OHLCV, frame)

    normalized = normalize_dataset(
        DatasetKind.OHLCV,
        frame,
        duplicate_policy=DuplicatePolicy.KEEP_LAST,
    )
    stats = normalized.attrs["duplicate_stats"]
    assert normalized["close"].tolist() == [101.0]
    assert stats["duplicate_rows"] == 2
    assert stats["duplicate_key_groups"] == 1
    assert stats["dropped_rows"] == 1


def test_warehouse_keep_latest_returns_duplicate_stats(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    first = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT"],
                "market_type": ["spot"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [2.0],
                "source": ["ccxt"],
            }
        )
    )
    latest = _complete_ohlcv(
        first.assign(open=102.0, high=103.0, low=101.0, close=102.0)
    )
    write_dataframe(
        first,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
        partition_date=pd.Timestamp("2024-01-01").date(),
        file_stem="first",
    )
    write_dataframe(
        latest,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
        partition_date=pd.Timestamp("2024-01-01").date(),
        file_stem="latest",
    )
    warehouse = DuckDBWarehouse(layout)

    with pytest.raises(ValueError, match="duplicate business keys"):
        warehouse.load_dataset(
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.SPOT,
            symbol="BTC/USDT",
            timeframe="1h",
        )

    loaded, stats = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
        duplicate_policy=DuplicatePolicy.KEEP_LAST,
        return_duplicate_stats=True,
    )
    assert loaded["close"].tolist() == [102.0]
    assert stats.duplicate_rows == 2
    assert stats.dropped_rows == 1


def test_validate_frame_checks_utc_source_and_ohlc() -> None:
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT"],
                "market_type": ["spot"],
                "open": [100.0],
                "high": [99.0],
                "low": [98.0],
                "close": [100.0],
                "volume": [2.0],
                "source": ["unknown"],
            }
        )
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        validate_frame(DatasetKind.OHLCV, frame)

    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    with pytest.raises(ValueError, match="source contains"):
        validate_frame(DatasetKind.OHLCV, frame)

    frame["source"] = "ccxt"
    with pytest.raises(ValueError, match="invalid OHLC"):
        validate_frame(DatasetKind.OHLCV, frame)


def test_ohlcv_audit_reports_gaps_and_open_rows() -> None:
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T02:00:00Z"]),
                "exchange": ["binance", "binance"],
                "symbol": ["BTC/USDT", "BTC/USDT"],
                "market_type": ["spot", "spot"],
                "open": [100.0, 102.0],
                "high": [101.0, 103.0],
                "low": [99.0, 101.0],
                "close": [100.0, 102.0],
                "volume": [2.0, 2.0],
                "source": ["ccxt", "ccxt"],
            }
        )
    )
    frame.loc[1, "is_closed"] = False

    report = audit_ohlcv_frame(frame, expected_timeframe="1h")

    assert report.missing_bars == 1
    assert report.open_rows == 1
    assert not report.trusted


def test_xnas_regular_session_audit_skips_closures_and_honors_early_close() -> None:
    schedule = expected_ohlcv_session_bars(
        start="2025-07-02T00:00:00Z",
        end="2025-07-07T23:59:59Z",
        timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
    )
    assert schedule.groupby("session").size().to_dict() == {
        "2025-07-02": 26,
        "2025-07-03": 14,
        "2025-07-07": 26,
    }

    rows = len(schedule)
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": schedule["ts"],
                "exchange": ["nasdaq"] * rows,
                "symbol": ["MU"] * rows,
                "market_type": ["equity"] * rows,
                "open": [100.0] * rows,
                "high": [101.0] * rows,
                "low": [99.0] * rows,
                "close": [100.0] * rows,
                "volume": [1_000.0] * rows,
                "source": ["polygon_api"] * rows,
            }
        ),
        timeframe="15m",
    )
    report = audit_ohlcv_frame(
        frame,
        expected_timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
        closure_as_of="2025-07-08T00:00:00Z",
    )

    assert report.trusted
    assert report.expected_bars == 66
    assert report.session_count == 3
    assert report.missing_bars == 0
    assert report.out_of_session_rows == 0
    assert report.closure_mismatches == 0

    broken = frame.drop(index=30).reset_index(drop=True)
    broken.loc[len(broken)] = broken.iloc[-1]
    broken.loc[len(broken) - 1, "ts"] = pd.Timestamp("2025-07-04T14:00:00Z")
    broken_report = audit_ohlcv_frame(
        broken,
        expected_timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
        closure_as_of="2025-07-08T00:00:00Z",
    )
    assert broken_report.missing_bars == 1
    assert broken_report.out_of_session_rows == 1
    assert not broken_report.trusted


def test_xnas_regular_session_audit_detects_premature_closed_flag() -> None:
    schedule = expected_ohlcv_session_bars(
        start="2025-07-02T13:30:00Z",
        end="2025-07-02T13:30:00Z",
        timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
    )
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": schedule["ts"],
                "exchange": ["nasdaq"],
                "symbol": ["MU"],
                "market_type": ["equity"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [1_000.0],
                "source": ["polygon_api"],
            }
        ),
        timeframe="15m",
    )

    report = audit_ohlcv_frame(
        frame,
        expected_timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
        closure_as_of="2025-07-02T13:40:00Z",
    )

    assert report.closure_mismatches == 1
    assert not report.trusted


def test_raw_normalized_ohlcv_audit_detects_value_drift() -> None:
    raw = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT"],
                "market_type": ["spot"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [2.0],
                "source": ["ccxt"],
            }
        )
    )
    normalized = raw.copy()
    normalized["close"] = 100.5

    report = audit_raw_normalized_ohlcv(raw, normalized)

    assert report.field_mismatches["close"] == 1
    assert not report.trusted


def test_trusted_ohlcv_loader_enforces_continuity_and_source(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"),
                "exchange": ["binance"] * 3,
                "symbol": ["BTC/USDT"] * 3,
                "market_type": ["spot"] * 3,
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.0, 101.0, 102.0],
                "volume": [2.0, 2.0, 2.0],
                "source": ["binance_vision_monthly"] * 3,
            }
        )
    )
    write_dataframe(
        frame,
        layout=layout,
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
        partition_date=pd.Timestamp("2024-01-01").date(),
    )
    warehouse = DuckDBWarehouse(layout)

    trusted = warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert trusted.attrs["ohlcv_audit"]["trusted"] is True
    assert (
        trusted.attrs["ohlcv_audit"]["session_policy"]
        == OHLCVSessionPolicy.CONTINUOUS_24_7.value
    )
    with pytest.raises(ValueError, match="not trusted"):
        warehouse.load_trusted_ohlcv(
            exchange="binance",
            market_type=MarketType.SPOT,
            symbol="BTC/USDT",
            timeframe="1h",
            allowed_sources=("ccxt",),
        )


def test_equity_trusted_loader_requires_and_applies_session_policy(
    tmp_path: Path,
) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    schedule = expected_ohlcv_session_bars(
        start="2025-07-03T00:00:00Z",
        end="2025-07-03T23:59:59Z",
        timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
    )
    rows = len(schedule)
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": schedule["ts"],
                "exchange": ["nasdaq"] * rows,
                "symbol": ["MU"] * rows,
                "market_type": ["equity"] * rows,
                "open": [100.0] * rows,
                "high": [101.0] * rows,
                "low": [99.0] * rows,
                "close": [100.0] * rows,
                "volume": [1_000.0] * rows,
                "source": ["polygon_api"] * rows,
            }
        ),
        timeframe="15m",
    )
    write_normalized_dataframe(
        frame,
        layout=layout,
        kind=DatasetKind.OHLCV,
        exchange="nasdaq",
        market_type=MarketType.EQUITY,
        symbol="MU",
        timeframe="15m",
    )
    warehouse = DuckDBWarehouse(layout)

    with pytest.raises(ValueError, match="explicit session_policy"):
        warehouse.load_trusted_ohlcv(
            exchange="nasdaq",
            market_type=MarketType.EQUITY,
            symbol="MU",
            timeframe="15m",
        )

    trusted = warehouse.load_trusted_ohlcv(
        exchange="nasdaq",
        market_type=MarketType.EQUITY,
        symbol="MU",
        timeframe="15m",
        session_policy=OHLCVSessionPolicy.XNAS_REGULAR,
        closure_as_of="2025-07-04T00:00:00Z",
    )
    assert len(trusted) == 14
    assert trusted.attrs["ohlcv_audit"]["calendar_name"] == "XNAS"
    assert trusted.attrs["ohlcv_audit"]["session_count"] == 1


def test_normalized_writer_splits_multiple_utc_dates(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": pd.to_datetime(["2024-01-01T23:00:00Z", "2024-01-02T00:00:00Z"]),
                "exchange": ["binance", "binance"],
                "symbol": ["BTC/USDT", "BTC/USDT"],
                "market_type": ["spot", "spot"],
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.0, 101.0],
                "volume": [2.0, 2.0],
                "source": ["ccxt", "ccxt"],
            }
        )
    )

    paths = write_normalized_dataframe(
        frame,
        layout=layout,
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.SPOT,
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert len(paths) == 2
    assert all(path.is_file() for path in paths)


def test_write_rejects_partition_identity_mismatch(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    frame = _complete_ohlcv(
        pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01T00:00:00Z")],
                "exchange": ["binance"],
                "symbol": ["BTC/USDT"],
                "market_type": ["spot"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [2.0],
                "source": ["ccxt"],
            }
        )
    )

    with pytest.raises(ValueError, match="timeframe values do not match"):
        write_dataframe(
            frame,
            layout=layout,
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.SPOT,
            symbol="BTC/USDT",
            timeframe="15m",
            partition_date=pd.Timestamp("2024-01-01").date(),
        )
