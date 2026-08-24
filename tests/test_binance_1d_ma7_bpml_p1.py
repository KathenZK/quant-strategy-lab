from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-basis-premium-meta-label/"
    "scripts/research_binance_1d_ma7_bpml_p1.py"
)
SYNC_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-basis-premium-meta-label/"
    "scripts/sync_binance_vision_bpml_basis.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bpml = load_module(SCRIPT, "bpml_test_module")
sync = load_module(SYNC_SCRIPT, "bpml_sync_test_module")


def synthetic_cache(offset: float = 0.0):
    timestamps = pd.date_range(
        "2023-01-01T00:00:00Z",
        periods=900,
        freq="1h",
    )
    phase = np.arange(len(timestamps), dtype="float64")
    premium = (
        offset
        + 0.0001 * np.sin(phase / 31.0)
        + phase * 1e-8
    )
    basis = (
        offset / 2.0
        + 0.0002 * np.cos(phase / 43.0)
        + phase * 2e-8
    )
    return bpml.BasisCache(
        ts_ns=timestamps.to_numpy(dtype="datetime64[ns]").astype("int64"),
        premium_open=premium.copy(),
        premium_high=premium + 0.00002,
        premium_low=premium - 0.00002,
        premium_close=premium.copy(),
        mark_index_basis=basis.copy(),
    ), timestamps


def test_basis_features_are_causal_and_require_exact_warmup() -> None:
    cache, timestamps = synthetic_cache()
    assert (
        bpml.local_basis_features(
            cache,
            entry_ts=timestamps[359],
            side=1,
        )
        is None
    )
    features = bpml.local_basis_features(
        cache,
        entry_ts=timestamps[760],
        side=-1,
    )
    assert features is not None
    assert set(features) == set(bpml.LOCAL_BASIS_FEATURES)
    changed = bpml.BasisCache(
        ts_ns=cache.ts_ns,
        premium_open=cache.premium_open,
        premium_high=cache.premium_high,
        premium_low=cache.premium_low,
        premium_close=np.where(
            np.arange(len(cache.premium_close)) >= 760,
            cache.premium_close + 1.0,
            cache.premium_close,
        ),
        mark_index_basis=np.where(
            np.arange(len(cache.mark_index_basis)) >= 760,
            cache.mark_index_basis + 1.0,
            cache.mark_index_basis,
        ),
    )
    assert features == bpml.local_basis_features(
        changed,
        entry_ts=timestamps[760],
        side=-1,
    )


def test_market_features_exclude_target_asset() -> None:
    caches = {}
    timestamps = None
    for index, asset in enumerate(bpml.ASSETS):
        cache, timestamps = synthetic_cache(index * 0.0001)
        caches[asset] = cache
    assert timestamps is not None
    row = {
        "event_id": 1,
        "root_id": "BTC-ROOT-1",
        "asset": "BTC",
        "side": 1,
        "signal_ts": timestamps[736],
        "entry_ts": timestamps[760],
        "exit_ts": timestamps[800],
        "label": 1,
        "z_8bps": 0.01,
        "z_4bps": 0.011,
        "z_funding_off": 0.009,
        "z_lag1": 0.008,
    }
    row.update({feature: 0.0 for feature in bpml.PRICE_FEATURES})
    panel, rejected = bpml.build_accepted_panel(pd.DataFrame([row]), caches)
    assert rejected == {}
    assert len(panel) == 1
    peers = [
        bpml.local_basis_features(
            caches[asset],
            entry_ts=timestamps[760],
            side=1,
        )
        for asset in bpml.ASSETS
        if asset != "BTC"
    ]
    assert all(peer is not None for peer in peers)
    expected = np.median(
        [peer["aligned_premium_mean_24h"] for peer in peers]
    )
    assert panel.loc[0, "market_peer_count"] == 4
    assert np.isclose(
        panel.loc[0, "market_median_aligned_premium_24h"],
        expected,
    )


def test_split_purges_exit_and_respects_test_window() -> None:
    dates = pd.date_range(
        "2024-01-01T00:00:00Z",
        periods=20,
        freq="1D",
    )
    frame = pd.DataFrame(
        {
            "signal_ts": dates,
            "exit_ts": dates + pd.Timedelta(days=2),
        }
    )
    train, test = bpml.split_for_block(
        frame,
        first_test=dates[12],
        last_test=dates[15],
    )
    assert train["exit_ts"].lt(dates[7]).all()
    assert test["signal_ts"].between(dates[12], dates[15]).all()


def test_feature_contract_and_hype_lock() -> None:
    assert len(bpml.PRICE_FEATURES) == 47
    assert len(bpml.BASIS_FEATURES) == 22
    assert len(bpml.FULL_FEATURES) == 69
    assert len(set(bpml.FULL_FEATURES)) == len(bpml.FULL_FEATURES)
    assert "HYPE" not in bpml.ASSETS
    assert all("HYPE" not in slug.upper() for slug in bpml.ASSET_SLUGS.values())


def test_epoch_parser_normalizes_to_utc_without_precision_loss() -> None:
    milliseconds = pd.Series([1_700_000_000_000, 1_700_003_600_000])
    microseconds = milliseconds * 1_000
    parsed_ms = sync.parse_epoch(milliseconds)
    parsed_us = sync.parse_epoch(microseconds)
    assert parsed_ms.equals(parsed_us)
    values = parsed_ms.to_numpy(dtype="datetime64[ns]").astype("int64")
    assert values[1] - values[0] == 3_600_000_000_000
