from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/finalize_hype_1d_ma7_oapp_reporting.py"


def load_recovery():
    spec = importlib.util.spec_from_file_location("test_hype_oapp_reporting_recovery", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_append_terminal_open_is_display_only_and_future_blind() -> None:
    recovery = load_recovery()

    class Book:
        terminal_ts = pd.Timestamp("2026-08-06T00:00:00Z")

    class Market:
        hourly = pd.DataFrame([{"ts": Book.terminal_ts, "open": 56.953, "high": 99.0, "low": 1.0, "close": 80.0}])

    class Features:
        ma7 = [54.172285714]

    class Context:
        book = Book()
        market = Market()
        features = Features()

    candles = [{"ts": "2026-08-05T00:00:00+00:00", "open": 55.0, "high": 57.0, "low": 54.0, "close": 56.953, "ma7": 54.0}]
    rows = recovery.append_terminal_open_candle(candles, Context())
    assert len(rows) == 2
    terminal = rows[-1]
    assert terminal["display_only_terminal_open"] is True
    assert terminal["open"] == terminal["high"] == terminal["low"] == terminal["close"] == 56.953

