from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = (
    ROOT
    / "research/_shared-kernels/bollinger-keltner-squeeze-breakout/v1/engine.py"
)


def load_engine() -> object:
    spec = importlib.util.spec_from_file_location("bksb_test_engine", ENGINE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_4h_resample_drops_partial_edge_buckets() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01 00:15", periods=31, freq="15min", tz="UTC")
    close = np.arange(len(index), dtype=float) + 10.0
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
    bars, audit = engine.aggregate_complete_bars(frame, "4h")
    assert list(bars.index) == [pd.Timestamp("2026-01-01 04:00", tz="UTC")]
    assert audit["complete_bars"] == 1
    assert audit["dropped_partial_bars"] == 1


def test_squeeze_release_requires_range_breakout() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01", periods=30, freq="1h", tz="UTC")
    close = np.full(30, 100.0)
    close[24:27] = [100.1, 100.2, 100.3]
    close[27:] = [101.0, 103.0, 104.0]
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )
    features = engine.build_features(frame, engine.StrategyConfig())
    signals = features.loc[features["long_signal"] | features["short_signal"]]
    assert not bool((features["long_signal"] & features["short_signal"]).any())
    assert len(signals) <= int(features["release_event"].sum())
