from __future__ import annotations

import importlib.util
import hashlib
import io
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-taker-flow-meta-label/"
    "scripts/research_binance_1d_ma7_tfml_p1.py"
)
SYNC_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-taker-flow-meta-label/"
    "scripts/sync_binance_vision_tfml_5m.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tfml = load_module(SCRIPT, "tfml_test_module")
sync = load_module(SYNC_SCRIPT, "tfml_sync_test_module")


def synthetic_cache(offset: float = 0.0):
    timestamps = pd.date_range(
        "2023-01-01T00:00:00Z",
        periods=5_000,
        freq="5min",
    )
    phase = np.arange(len(timestamps), dtype="float64")
    open_values = (100.0 + offset) * np.exp(phase * 1e-7)
    close_values = open_values * np.exp(
        0.0001 * np.sin(phase / 17.0 + offset)
    )
    quote = 1_000.0 + 100.0 * np.sin(phase / 13.0 + offset)
    imbalance = 0.1 * np.sin(phase / 19.0 + offset) + 0.01
    return tfml.FlowCache(
        ts_ns=timestamps.to_numpy(dtype="datetime64[ns]").astype("int64"),
        open=open_values,
        close=close_values,
        quote_volume=quote,
        trade_count=np.full(len(timestamps), 100.0 + offset),
        net_quote=quote * imbalance,
        per_bar_imbalance=imbalance,
        active=np.ones(len(timestamps), dtype=bool),
    ), timestamps


def test_flow_features_are_causal_and_require_exact_window() -> None:
    cache, timestamps = synthetic_cache()
    assert (
        tfml.local_flow_features(
            cache,
            entry_ts=timestamps[4_319],
            side=1,
        )
        is None
    )
    features = tfml.local_flow_features(
        cache,
        entry_ts=timestamps[4_500],
        side=-1,
    )
    assert features is not None
    assert set(features) == set(tfml.LOCAL_FLOW_FEATURES)
    changed = tfml.FlowCache(
        ts_ns=cache.ts_ns,
        open=cache.open,
        close=np.where(
            np.arange(len(cache.close)) >= 4_500,
            cache.close * 2.0,
            cache.close,
        ),
        quote_volume=np.where(
            np.arange(len(cache.close)) >= 4_500,
            cache.quote_volume * 3.0,
            cache.quote_volume,
        ),
        trade_count=cache.trade_count,
        net_quote=np.where(
            np.arange(len(cache.close)) >= 4_500,
            cache.net_quote * 3.0,
            cache.net_quote,
        ),
        per_bar_imbalance=cache.per_bar_imbalance,
        active=cache.active,
    )
    assert features == tfml.local_flow_features(
        changed,
        entry_ts=timestamps[4_500],
        side=-1,
    )


def test_aggregate_imbalance_uses_quote_weighting() -> None:
    cache, _ = synthetic_cache()
    start, end = 100, 200
    expected = cache.net_quote[start:end].sum() / cache.quote_volume[
        start:end
    ].sum()
    assert np.isclose(
        tfml.aggregate_imbalance(cache, start, end),
        expected,
    )


def test_market_flow_features_exclude_target() -> None:
    caches = {}
    timestamps = None
    for index, asset in enumerate(tfml.ASSETS):
        cache, timestamps = synthetic_cache(index * 0.1)
        caches[asset] = cache
    assert timestamps is not None
    row = {
        "event_id": 1,
        "root_id": "BTC-ROOT-1",
        "asset": "BTC",
        "side": 1,
        "signal_ts": timestamps[4_450],
        "entry_ts": timestamps[4_500],
        "exit_ts": timestamps[4_800],
        "z_8bps": 0.01,
        "z_4bps": 0.011,
        "z_funding_off": 0.009,
        "z_lag1": 0.008,
    }
    row.update({feature: 0.0 for feature in tfml.PRICE_FEATURES})
    panel, rejected = tfml.build_accepted_panel(
        pd.DataFrame([row]),
        caches,
    )
    assert rejected == {}
    assert len(panel) == 1
    peers = [
        tfml.local_flow_features(
            caches[asset],
            entry_ts=timestamps[4_500],
            side=1,
        )
        for asset in tfml.ASSETS
        if asset != "BTC"
    ]
    assert all(peer is not None for peer in peers)
    expected = np.median(
        [peer["aligned_taker_imbalance_24h"] for peer in peers]
    )
    assert panel.loc[0, "market_peer_count"] == 4
    assert np.isclose(
        panel.loc[0, "market_median_aligned_taker_imbalance_24h"],
        expected,
    )


def test_feature_contract_and_hype_lock() -> None:
    assert len(tfml.PRICE_FEATURES) == 47
    assert len(tfml.FLOW_FEATURES) == 23
    assert len(tfml.FULL_FEATURES) == 70
    assert len(set(tfml.FULL_FEATURES)) == len(tfml.FULL_FEATURES)
    assert "HYPE" not in tfml.ASSETS
    assert all("HYPE" not in slug.upper() for slug in tfml.ASSET_SLUGS.values())


def test_frozen_five_asset_nested_aggregate_is_fail_closed() -> None:
    capacity = tfml.strict_nested_aggregate_capacity()

    assert capacity["outer_fold_peers"] == 3
    assert capacity["outer_feasible"]
    assert capacity["inner_fold_peers"] == 2
    assert not capacity["inner_feasible"]
    with pytest.raises(RuntimeError, match="historical P1 aggregate"):
        tfml.enforce_strict_nested_aggregate_capacity()


def test_epoch_parser_normalizes_milliseconds_and_microseconds() -> None:
    milliseconds = pd.Series([1_700_000_000_000, 1_700_000_300_000])
    microseconds = milliseconds * 1_000
    parsed_ms = sync.parse_epoch(milliseconds)
    parsed_us = sync.parse_epoch(microseconds)
    assert parsed_ms.equals(parsed_us)
    values = parsed_ms.to_numpy(dtype="datetime64[ns]").astype("int64")
    assert values[1] - values[0] == tfml.FIVE_MINUTES_NS


def test_invalid_source_flow_row_is_excluded_without_repair(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(sync, "RAW_ROOT", tmp_path)
    monkeypatch.setattr(sync, "ASSET_SLUGS", {"DOT": "dotusdt"})
    start = pd.Timestamp("2023-11-14T11:15:00Z")
    rows = []
    for index in range(2):
        ts = start + pd.Timedelta(minutes=5 * index)
        open_ms = int(ts.timestamp() * 1_000)
        close_ms = open_ms + 300_000 - 1
        rows.append(
            [
                open_ms,
                5.0,
                5.1,
                4.9,
                5.0,
                10.0,
                close_ms,
                50.0,
                100,
                20.0 if index == 0 else 5.0,
                25.0,
                0,
            ]
        )
    csv_payload = pd.DataFrame(rows).to_csv(index=False, header=False).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("DOTUSDT-5m-2023-11.csv", csv_payload)
    payload = buffer.getvalue()
    archive = sync.Archive(
        asset="DOT",
        symbol="DOTUSDT",
        month="2023-11",
        key=(
            "data/futures/um/monthly/klines/DOTUSDT/5m/"
            "DOTUSDT-5m-2023-11.zip"
        ),
        etag=hashlib.md5(payload).hexdigest(),  # noqa: S324
        size=len(payload),
        last_modified="2023-12-01T00:00:00Z",
    )
    archive.raw_path.parent.mkdir(parents=True)
    archive.raw_path.write_bytes(payload)
    parsed = sync.parse_archive(archive)
    assert len(parsed) == 1
    assert parsed.iloc[0]["ts"] == start + pd.Timedelta(minutes=5)
    assert parsed.attrs["invalid_flow_rows"] == [
        {
            "ts": start,
            "base_exceeds_total": True,
            "quote_exceeds_total": False,
        }
    ]
