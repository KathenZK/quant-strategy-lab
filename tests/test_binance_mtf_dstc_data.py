from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(
    "research/asset-portfolios/multi-timeframe-dual-state-trend-campaign/scripts/"
    "dstc_data.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_binance_mtf_dstc_data_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cutoff_file_scope_excludes_later_partitions(tmp_path: Path) -> None:
    module = load_module()
    symbol = "HYPE/USDT:USDT"
    stem = "symbol=hype_usdt_usdt.parquet"
    for date in ("2026-08-01", "2026-08-02", "2026-08-03"):
        directory = tmp_path / f"date={date}"
        directory.mkdir()
        (directory / stem).touch()
    files = module.cutoff_scoped_files(
        tmp_path,
        symbol,
        pd.Timestamp("2026-08-01 15:15:00", tz="UTC"),
    )
    assert len(files) == 1
    assert "date=2026-08-01" in files[0]


def test_complete_aggregation_is_visible_only_after_source_bar_closes() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=8, freq="15min", tz="UTC")
    close = np.arange(8, dtype=float) + 100.0
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )
    hourly, quality = module.aggregate_complete(frame, "1h", 4)
    assert quality["accepted"] is True
    assert list(hourly.index) == [
        pd.Timestamp("2026-01-01 01:00", tz="UTC"),
        pd.Timestamp("2026-01-01 02:00", tz="UTC"),
    ]
    assert hourly.iloc[0]["close"] == 103.0


def test_incomplete_source_bin_is_excluded() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=7, freq="15min", tz="UTC")
    close = np.arange(7, dtype=float) + 100.0
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )
    hourly, quality = module.aggregate_complete(frame, "1h", 4)
    assert len(hourly) == 1
    assert quality["incomplete_edge_or_gap_bins_excluded"] == 1
