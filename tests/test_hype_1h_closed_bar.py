from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py"
)


def load_fetch_module():
    spec = importlib.util.spec_from_file_location("fetch_hype_binance_1h", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_closed_bar_mask_is_unit_safe_for_datetime64_ms() -> None:
    fetch = load_fetch_module()
    close_time = pd.Series(
        pd.to_datetime(
            [
                "2026-07-02T01:59:59.999Z",
                "2026-07-02T02:59:59.999Z",
            ]
        ).as_unit("ms")
    )
    cutoff_ms = int(pd.Timestamp("2026-07-02T02:57:46.044Z").timestamp() * 1000)

    result = fetch.closed_bar_mask(close_time, cutoff_ms)

    assert result.tolist() == [True, False]


def test_audit_rejects_normalized_bar_that_is_not_closed() -> None:
    fetch = load_fetch_module()
    raw = pd.DataFrame(
        {
            "open_time": pd.to_datetime(["2026-07-02T02:00:00Z"]).as_unit("ms"),
            "close_time": pd.to_datetime(["2026-07-02T02:59:59.999Z"]).as_unit(
                "ms"
            ),
            "open": [40.0],
            "high": [41.0],
            "low": [39.0],
            "close": [40.5],
            "volume": [10.0],
            "quote_volume": [405.0],
            "trade_count": [5],
            "taker_buy_volume": [4.0],
            "taker_buy_quote_volume": [162.0],
            "ignore": [0.0],
            "source": ["binance_futures_kline_api"],
            "is_closed": [True],
        }
    )
    normalized = fetch.normalize_klines(raw)
    cutoff_ms = int(pd.Timestamp("2026-07-02T02:57:46.044Z").timestamp() * 1000)

    try:
        fetch.audit_data(raw, normalized, cutoff_ms=cutoff_ms)
    except RuntimeError as exc:
        assert "normalized_bar_not_closed_at_cutoff" in str(exc)
    else:
        raise AssertionError("audit_data accepted an unclosed normalized bar")
