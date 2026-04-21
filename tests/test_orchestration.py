from pathlib import Path

import pandas as pd

from signal_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe
from signal_lab.features import FeatureBuilder, FeatureStore
from signal_lab.orchestration import IncrementalStateStore, StrategyRunner, load_strategy_workflow
from signal_lab.data import DuckDBWarehouse
from signal_lab.factors import default_registry


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
  factor: ret_1
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
  factor: ret_1
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
