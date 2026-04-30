from pathlib import Path

import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe
from strategy_lab.features import FeatureBuilder, FeatureStore
from strategy_lab.orchestration import IncrementalStateStore, StrategyRunner, load_strategy_workflow
from strategy_lab.orchestration.workflow_service import WorkflowService
from strategy_lab.data import DuckDBWarehouse
from strategy_lab.factors import default_registry


def _layout(tmp_path: Path) -> DataLakeLayout:
    return DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )


def _normalized_ohlcv(symbol: str) -> pd.DataFrame:
    closes = {
        "BTC/USDT": [100, 101, 103, 104, 106, 108, 110, 112],
        "ETH/USDT": [50, 51, 50.5, 52, 53, 54, 55, 57],
        "SOL/USDT": [20, 20.2, 20.5, 21, 21.5, 22, 22.8, 23.5],
    }[symbol]
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=len(closes), freq="D", tz="UTC"),
            "exchange": ["binance"] * len(closes),
            "symbol": [symbol] * len(closes),
            "market_type": ["spot"] * len(closes),
            "base_asset": [symbol.split("/")[0]] * len(closes),
            "quote_asset": [symbol.split("/")[1]] * len(closes),
            "open": closes,
            "high": [value * 1.01 for value in closes],
            "low": [value * 0.99 for value in closes],
            "close": closes,
            "volume": [1_000_000.0] * len(closes),
            "source": ["test"] * len(closes),
            "date": [item.date().isoformat() for item in pd.date_range("2024-01-01", periods=len(closes), freq="D", tz="UTC")],
        }
    )
    return frame


def _trend_ohlcv(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=80, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        closes = [100 + i * 0.8 for i in range(len(index))]
    elif symbol == "ETH/USDT":
        closes = [200 - i * 0.7 for i in range(len(index))]
    else:
        closes = [50 + ((-1) ** i) * 0.1 for i in range(len(index))]
    frame = pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "open": closes,
            "high": [value * 1.01 for value in closes],
            "low": [value * 0.99 for value in closes],
            "close": closes,
            "volume": [2_000_000.0] * len(index),
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )
    return frame


def _trend_funding(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=80, freq="h", tz="UTC")
    base_rate = 0.0003 if symbol == "BTC/USDT" else (-0.0002 if symbol == "ETH/USDT" else 0.003)
    values = [base_rate + i * 0.00001 for i in range(len(index))]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "funding_rate": values,
            "next_funding_ts": index + pd.Timedelta(hours=8),
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def _trend_open_interest(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=80, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        values = [10_000 + i * 120 for i in range(len(index))]
    elif symbol == "ETH/USDT":
        values = [12_000 + i * 110 for i in range(len(index))]
    else:
        values = [8_000 - i * 5 for i in range(len(index))]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "open_interest": values,
            "open_interest_value": values,
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def _trend_basis(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=80, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        basis = [10 + i * 0.4 for i in range(len(index))]
    elif symbol == "ETH/USDT":
        basis = [8 - i * 0.3 for i in range(len(index))]
    else:
        basis = [1 + ((-1) ** i) * 0.05 for i in range(len(index))]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "basis": basis,
            "basis_rate": [value / 10_000 for value in basis],
            "annualized_basis": [value / 100 for value in basis],
            "futures_price": [100 + value for value in basis],
            "index_price": [100.0] * len(index),
            "mark_price": [100 + value * 0.9 for value in basis],
            "premium_index": [value / 100_000 for value in basis],
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def _trend_liquidations(symbol: str) -> pd.DataFrame:
    if symbol == "BTC/USDT":
        return pd.DataFrame(
            {
                "ts": pd.to_datetime(["2024-01-04T06:10:00Z", "2024-01-04T07:15:00Z"]),
                "exchange": ["binance", "binance"],
                "symbol": [symbol, symbol],
                "market_type": ["perp", "perp"],
                "base_asset": ["BTC", "BTC"],
                "quote_asset": ["USDT", "USDT"],
                "side": ["sell", "sell"],
                "price": [45000.0, 45200.0],
                "size": [0.40, 0.50],
                "notional": [18000.0, 22600.0],
                "source": ["test", "test"],
            }
        )
    if symbol == "ETH/USDT":
        return pd.DataFrame(
            {
                "ts": pd.to_datetime(["2024-01-04T06:10:00Z"]),
                "exchange": ["binance"],
                "symbol": [symbol],
                "market_type": ["perp"],
                "base_asset": ["ETH"],
                "quote_asset": ["USDT"],
                "side": ["buy"],
                "price": [2500.0],
                "size": [0.10],
                "notional": [250.0],
                "source": ["test"],
            }
        )
    return pd.DataFrame(
        {
            "ts": pd.to_datetime(["2024-01-04T06:10:00Z"]),
            "exchange": ["binance"],
            "symbol": [symbol],
            "market_type": ["perp"],
            "base_asset": ["SOL"],
            "quote_asset": ["USDT"],
            "side": ["sell"],
            "price": [100.0],
            "size": [0.01],
            "notional": [1.0],
            "source": ["test"],
        }
    )


def _crowding_ohlcv(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=96, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        prefix = [100 + i * 0.35 for i in range(92)]
        tail = [prefix[-1] - 0.8, prefix[-1] - 1.6, prefix[-1] - 2.4, prefix[-1] - 3.2]
        close = prefix + tail
    elif symbol == "ETH/USDT":
        prefix = [200 - i * 0.45 for i in range(92)]
        tail = [prefix[-1] + 1.0, prefix[-1] + 2.0, prefix[-1] + 3.0, prefix[-1] + 4.0]
        close = prefix + tail
    else:
        close = [80 + 0.05 * ((-1) ** i) for i in range(96)]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "open": close,
            "high": [value * 1.01 for value in close],
            "low": [value * 0.99 for value in close],
            "close": close,
            "volume": [2_500_000.0] * len(index),
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def _crowding_funding(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=96, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        values = [0.0002 + i * 0.00002 for i in range(96)]
    elif symbol == "ETH/USDT":
        values = [-0.0002 - i * 0.00002 for i in range(96)]
    else:
        values = [0.00001 * ((-1) ** i) for i in range(96)]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "funding_rate": values,
            "next_funding_ts": index + pd.Timedelta(hours=8),
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def _crowding_open_interest(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=96, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        values = [15_000 + i * 150 for i in range(96)]
    elif symbol == "ETH/USDT":
        values = [14_000 + i * 140 for i in range(96)]
    else:
        values = [9_000 + i * 2 for i in range(96)]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "open_interest": values,
            "open_interest_value": values,
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def _crowding_basis(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=96, freq="h", tz="UTC")
    if symbol == "BTC/USDT":
        basis = [5 + i * 0.18 for i in range(96)]
    elif symbol == "ETH/USDT":
        basis = [-5 - i * 0.18 for i in range(96)]
    else:
        basis = [0.2 * ((-1) ** i) for i in range(96)]
    return pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": [symbol] * len(index),
            "market_type": ["perp"] * len(index),
            "base_asset": [symbol.split("/")[0]] * len(index),
            "quote_asset": [symbol.split("/")[1]] * len(index),
            "basis": basis,
            "basis_rate": [value / 10_000 for value in basis],
            "annualized_basis": [value / 100 for value in basis],
            "futures_price": [100 + value for value in basis],
            "index_price": [100.0] * len(index),
            "mark_price": [100 + value * 0.9 for value in basis],
            "premium_index": [value / 100_000 for value in basis],
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
        }
    )


def test_incremental_state_store_tracks_checkpoints(tmp_path: Path) -> None:
    store = IncrementalStateStore(tmp_path)
    checkpoint = store.update_checkpoint(
        dataset=DatasetKind.OHLCV,
        exchange="binance",
        symbol="BTC/USDT",
        market_type=MarketType.SPOT,
        timeframe="1h",
        last_ts="2024-01-10T00:00:00Z",
        rows=100,
        raw_path="raw.parquet",
        normalized_path="normalized.parquet",
    )
    resolved = store.resolve_since(
        dataset=DatasetKind.OHLCV,
        exchange="binance",
        symbol="BTC/USDT",
        market_type=MarketType.SPOT,
        timeframe="1h",
        overlap_bars=2,
    )
    assert checkpoint.rows == 100
    assert resolved is not None
    assert pd.Timestamp(resolved) == pd.Timestamp("2024-01-09T22:00:00Z")


def test_load_strategy_workflow_reads_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        """
strategy:
  name: demo
  factor_name: ret_1
  exchange: binance
  market_type: spot
  symbols: [BTC/USDT, ETH/USDT, SOL/USDT]
  benchmark_symbol: BTC/USDT
execution:
  fee_bps: 3.0
  slippage_bps: 1.0
  starting_cash: 50000
""".strip(),
        encoding="utf-8",
    )
    workflow = load_strategy_workflow(config_path)
    assert workflow.strategy.name == "demo"
    assert workflow.execution.starting_cash == 50000
    assert workflow.refresh.incremental is True
    assert workflow.run_backtest is True


def test_strategy_workflow_can_resolve_strategy_owned_symbols(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy-owned-universe.yaml"
    config_path.write_text(
        """
strategy:
  name: ma_owned_universe
  strategy_type: ma_crossover
  exchange: binance
  market_type: spot
  strategy_params:
    symbols: [eth/usdt]
refresh:
  enabled: false
""".strip(),
        encoding="utf-8",
    )

    workflow = load_strategy_workflow(config_path)
    resolved = WorkflowService(builder=None).with_resolved_symbols(workflow)

    assert workflow.strategy.symbols == []
    assert resolved.strategy.symbols == ["ETH/USDT"]


def test_strategy_runner_creates_reports_and_manifests(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT"):
        frame = _normalized_ohlcv(symbol)
        write_dataframe(
            frame,
            layout=layout,
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.SPOT,
            symbol=symbol,
            partition_date=frame["ts"].max().date(),
        )

    config_path = tmp_path / "workflow.yaml"
    config_path.write_text(
        """
strategy:
  name: demo
  factor_name: ret_1
  exchange: binance
  market_type: spot
  symbols: [BTC/USDT, ETH/USDT, SOL/USDT]
  benchmark_symbol: BTC/USDT
refresh:
  enabled: false
workflow:
  run_factor_report: true
  run_backtest: true
  run_paper_trade: true
""".strip(),
        encoding="utf-8",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    artifacts = StrategyRunner(layout=layout, builder=builder).run(load_strategy_workflow(config_path))
    manifests = builder.store.load_manifests("ret_1")

    assert artifacts.manifest_path is not None
    assert Path(artifacts.manifest_path).exists()
    assert artifacts.factor_report_path is not None and Path(artifacts.factor_report_path).exists()
    assert artifacts.backtest_report_path is not None and Path(artifacts.backtest_report_path).exists()
    assert artifacts.paper_report_path is not None and Path(artifacts.paper_report_path).exists()
    assert len(manifests) >= 3


def test_strategy_runner_supports_trend_confirmation_workflow(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT"):
        for dataset_kind, frame in (
            (DatasetKind.OHLCV, _trend_ohlcv(symbol)),
            (DatasetKind.FUNDING_RATES, _trend_funding(symbol)),
            (DatasetKind.OPEN_INTEREST, _trend_open_interest(symbol)),
            (DatasetKind.BASIS, _trend_basis(symbol)),
            (DatasetKind.LIQUIDATIONS, _trend_liquidations(symbol)),
        ):
            write_dataframe(
                frame,
                layout=layout,
                layer="normalized",
                kind=dataset_kind,
                exchange="binance",
                market_type=MarketType.PERP,
                symbol=symbol,
                partition_date=frame["ts"].max().date(),
            )

    config_path = tmp_path / "trend-workflow.yaml"
    config_path.write_text(
        """
strategy:
  name: trend_demo
  strategy_type: trend_confirmation
  exchange: binance
  market_type: perp
  symbols: [BTC/USDT, ETH/USDT, SOL/USDT]
  strategy_params:
    max_long_positions: 1
    max_short_positions: 1
refresh:
  enabled: false
workflow:
  run_factor_report: true
  run_backtest: true
  run_paper_trade: true
""".strip(),
        encoding="utf-8",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    workflow = load_strategy_workflow(config_path)
    runner = StrategyRunner(layout=layout, builder=builder)
    prepared = runner.workflow_service.prepare(workflow)
    backtest = runner.workflow_service.run_backtest(workflow, prepared)
    artifacts = runner.run(workflow)
    manifest = Path(artifacts.manifest_path).read_text(encoding="utf-8")

    assert prepared.signal_name == "trend_confirmation"
    assert prepared.signal_version
    assert prepared.panels.liquidation_features is not None
    assert prepared.target_weights is not None
    assert prepared.target_weights.abs().sum(axis=1).iloc[-1] > 0.0
    assert backtest.metrics
    assert artifacts.manifest_path is not None and Path(artifacts.manifest_path).exists()
    assert artifacts.factor_report_path is not None and Path(artifacts.factor_report_path).exists()
    assert artifacts.backtest_report_path is not None and Path(artifacts.backtest_report_path).exists()
    assert artifacts.paper_report_path is not None and Path(artifacts.paper_report_path).exists()
    assert "trend_confirmation" in manifest


def test_strategy_runner_supports_crowding_reversal_workflow(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()
    for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT"):
        for dataset_kind, frame in (
            (DatasetKind.OHLCV, _crowding_ohlcv(symbol)),
            (DatasetKind.FUNDING_RATES, _crowding_funding(symbol)),
            (DatasetKind.OPEN_INTEREST, _crowding_open_interest(symbol)),
            (DatasetKind.BASIS, _crowding_basis(symbol)),
            (DatasetKind.LIQUIDATIONS, _trend_liquidations(symbol)),
        ):
            write_dataframe(
                frame,
                layout=layout,
                layer="normalized",
                kind=dataset_kind,
                exchange="binance",
                market_type=MarketType.PERP,
                symbol=symbol,
                partition_date=frame["ts"].max().date(),
            )

    config_path = tmp_path / "crowding-workflow.yaml"
    config_path.write_text(
        """
strategy:
  name: crowding_demo
  strategy_type: crowding_reversal
  exchange: binance
  market_type: perp
  symbols: [BTC/USDT, ETH/USDT, SOL/USDT]
  strategy_params:
    max_long_positions: 1
    max_short_positions: 1
refresh:
  enabled: false
workflow:
  run_factor_report: true
  run_backtest: true
  run_paper_trade: true
""".strip(),
        encoding="utf-8",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    workflow = load_strategy_workflow(config_path)
    runner = StrategyRunner(layout=layout, builder=builder)
    prepared = runner.workflow_service.prepare(workflow)
    backtest = runner.workflow_service.run_backtest(workflow, prepared)
    artifacts = runner.run(workflow)
    manifest = Path(artifacts.manifest_path).read_text(encoding="utf-8")

    assert prepared.signal_name == "crowding_reversal"
    assert prepared.signal_version
    assert prepared.panels.liquidation_features is not None
    assert prepared.target_weights is not None
    assert prepared.target_weights.loc[prepared.target_weights.index[-1], "BTC/USDT"] < 0
    assert prepared.target_weights.loc[prepared.target_weights.index[-1], "ETH/USDT"] > 0
    assert backtest.metrics
    assert artifacts.manifest_path is not None and Path(artifacts.manifest_path).exists()
    assert artifacts.factor_report_path is not None and Path(artifacts.factor_report_path).exists()
    assert artifacts.backtest_report_path is not None and Path(artifacts.backtest_report_path).exists()
    assert artifacts.paper_report_path is not None and Path(artifacts.paper_report_path).exists()
    assert "crowding_reversal" in manifest


def test_strategy_runner_passes_price_and_factors_to_ma_crossover_allocator(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()

    index = pd.date_range("2024-01-01", periods=180, freq="D", tz="UTC")
    close = pd.Series([100.0 + i * 0.8 for i in range(len(index))], index=index)
    frame = pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": ["BTC/USDT"] * len(index),
            "market_type": ["spot"] * len(index),
            "base_asset": ["BTC"] * len(index),
            "quote_asset": ["USDT"] * len(index),
            "open": close.to_numpy(),
            "high": (close * 1.01).to_numpy(),
            "low": (close * 0.99).to_numpy(),
            "close": close.to_numpy(),
            "volume": [1_000_000.0] * len(index),
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
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

    config_path = tmp_path / "ma-workflow.yaml"
    config_path.write_text(
        """
strategy:
  name: ma_demo
  strategy_type: ma_crossover
  exchange: binance
  market_type: spot
  symbols: [BTC/USDT]
  strategy_params:
    long_allocation: 1.0
    short_allocation: 1.0
    take_profit_pct: 0.20
    min_ma_gap_ratio: 0.0001
refresh:
  enabled: false
workflow:
  run_factor_report: false
  run_backtest: true
  run_paper_trade: false
""".strip(),
        encoding="utf-8",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    workflow = load_strategy_workflow(config_path)
    runner = StrategyRunner(layout=layout, builder=builder)

    prepared = runner.workflow_service.prepare(workflow)

    assert prepared.signal_name == "ma_crossover"
    assert prepared.signal_version
    assert not prepared.signal_frame.dropna(how="all").empty
    assert prepared.target_weights is not None
    assert prepared.target_weights.abs().sum().sum() > 0.0
    assert prepared.panels.price is not None


def test_strategy_runner_supports_donchian_breakout_pyramiding_workflow(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()

    index = pd.date_range("2024-01-01", periods=180, freq="D", tz="UTC")
    close = pd.Series([100.0 + i * 0.8 for i in range(len(index))], index=index)
    frame = pd.DataFrame(
        {
            "ts": index,
            "exchange": ["binance"] * len(index),
            "symbol": ["BTC/USDT"] * len(index),
            "market_type": ["spot"] * len(index),
            "base_asset": ["BTC"] * len(index),
            "quote_asset": ["USDT"] * len(index),
            "open": close.to_numpy(),
            "high": (close * 1.01).to_numpy(),
            "low": (close * 0.99).to_numpy(),
            "close": close.to_numpy(),
            "volume": [1_500_000.0] * len(index),
            "source": ["test"] * len(index),
            "date": [item.date().isoformat() for item in index],
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

    config_path = tmp_path / "donchian-workflow.yaml"
    config_path.write_text(
        """
strategy:
  name: donchian_demo
  strategy_type: donchian_breakout
  exchange: binance
  market_type: spot
  symbols: [BTC/USDT]
  strategy_params:
    breakout_factor: donchian_breakout_14
    trend_factor: ma_distance_120
    long_allocation: 1.0
    short_allocation: 1.0
    stop_loss_pct: 0.05
    trailing_stop_pct: 0.05
    exit_on_trend_reversal: true
    risk_budget_pct: 0.02
    max_pyramids: 2
    pyramid_step_pct: 0.05
    pyramid_unit_scale: 0.5
refresh:
  enabled: false
workflow:
  run_factor_report: false
  run_backtest: true
  run_paper_trade: false
""".strip(),
        encoding="utf-8",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    workflow = load_strategy_workflow(config_path)
    runner = StrategyRunner(layout=layout, builder=builder)

    prepared = runner.workflow_service.prepare(workflow)

    assert prepared.signal_name == "donchian_breakout"
    assert prepared.signal_version
    assert not prepared.signal_frame.dropna(how="all").empty
    assert prepared.target_weights is not None
    assert prepared.target_weights.max().max() > 0.4
    assert prepared.panels.price is not None


def test_strategy_runner_supports_spot_cta_trend_backtest(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.ensure_directories()

    index = pd.date_range("2024-01-01", periods=180, freq="4h", tz="UTC")
    close_by_symbol = {
        "BTC/USDT": [100.0 + i * 0.8 for i in range(len(index))],
        "ETH/USDT": [80.0 + i * 0.2 for i in range(len(index))],
        "SOL/USDT": [30.0 + i * 0.5 for i in range(len(index))],
    }
    for symbol, closes in close_by_symbol.items():
        frame = pd.DataFrame(
            {
                "ts": index,
                "exchange": ["binance"] * len(index),
                "symbol": [symbol] * len(index),
                "market_type": ["spot"] * len(index),
                "base_asset": [symbol.split("/")[0]] * len(index),
                "quote_asset": [symbol.split("/")[1]] * len(index),
                "open": closes,
                "high": [value * 1.01 for value in closes],
                "low": [value * 0.99 for value in closes],
                "close": closes,
                "volume": [2_000_000.0] * len(index),
                "source": ["test"] * len(index),
                "date": [item.date().isoformat() for item in index],
            }
        )
        write_dataframe(
            frame,
            layout=layout,
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.SPOT,
            symbol=symbol,
            partition_date=frame["ts"].max().date(),
        )

    config_path = tmp_path / "spot-cta-workflow.yaml"
    config_path.write_text(
        """
strategy:
  name: spot_cta_demo
  strategy_type: spot_cta_trend
  exchange: binance
  market_type: spot
  symbols: [BTC/USDT, ETH/USDT, SOL/USDT]
  strategy_params:
    max_positions: 2
    long_allocation: 0.70
    max_rsi: 100.0
    stop_loss_pct:
    trailing_stop_pct:
    cooldown_bars: 0
    max_rank_hold_positions: 2
execution:
  fee_bps: 10.0
  slippage_bps: 10.0
risk:
  max_abs_weight: 0.35
  max_gross_leverage: 0.70
  max_net_exposure: 0.70
  min_dollar_volume: 1000000.0
refresh:
  enabled: false
workflow:
  run_factor_report: false
  run_backtest: true
  run_paper_trade: false
""".strip(),
        encoding="utf-8",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    workflow = load_strategy_workflow(config_path)
    runner = StrategyRunner(layout=layout, builder=builder)

    prepared = runner.workflow_service.prepare(workflow)
    backtest = runner.workflow_service.run_backtest(workflow, prepared)

    assert prepared.signal_name == "spot_cta_trend"
    assert prepared.target_weights is not None
    assert prepared.target_weights.max().max() > 0.0
    assert backtest.metrics["cumulative_return"] > 0.0
