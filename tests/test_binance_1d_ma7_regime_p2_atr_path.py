from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "research/asset-portfolios/1d-ma7-regime-continuation/scripts"
SCRIPT_PATH = SCRIPT_DIR / "analyze_binance_1d_ma7_regime_p2_atr_path.py"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("binance_1d_ma7_rc_p2", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_p2_frozen_config_hash_and_identity() -> None:
    actual_hash = MODULE.sha256_file(MODULE.CONFIG_PATH)
    config = json.loads(MODULE.CONFIG_PATH.read_text(encoding="utf-8"))
    assert actual_hash == MODULE.EXPECTED_CONFIG_SHA256
    assert config["study_id"] == "BIN-1D-MA7-RC-P2"
    assert config["data"]["primary_indicator_history_observations"] == 60
    assert config["decision_boundary"]["not_a_strategy_backtest"] is True


def test_p2_path_quintiles_are_right_closed() -> None:
    values = pd.Series([0.01, 0.20, 0.21, 0.40, 0.60, 0.80, 0.81, 1.0, np.nan])
    actual = MODULE.assign_quintile(values)
    assert actual.tolist() == [1, 1, 2, 2, 3, 4, 5, 5, pd.NA]


def test_p2_breakout_style_uses_fixed_readable_ratios() -> None:
    values = pd.Series([0.20, 0.799, 0.80, 1.0, 1.20, 1.201, np.nan])
    actual = MODULE.classify_breakout_style(values)
    assert actual.tolist() == [
        "WEAK",
        "WEAK",
        "NORMAL",
        "NORMAL",
        "NORMAL",
        "BURST",
        pd.NA,
    ]


def test_p2_pre_breakout_atr_path_does_not_use_trigger_day_range() -> None:
    dates = pd.date_range("2024-01-01", periods=130, freq="D", tz="UTC")
    close = pd.Series(np.linspace(100.0, 140.0, len(dates)))
    frame = pd.DataFrame(
        {
            "symbol": "TEST/USDT:USDT",
            "base_asset": "TEST",
            "event_date": dates,
            "block_id": 1,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "listing_age_days": np.arange(len(dates)),
            "rv_percentile": 0.5,
        }
    )
    for period in MODULE.MA_PERIODS:
        frame[f"sma{period}"] = frame["close"].rolling(period).mean()
    original = MODULE.enrich_feature_block(frame)
    shocked = frame.copy()
    shocked.loc[129, "high"] += 100.0
    shocked.loc[129, "low"] -= 100.0
    changed = MODULE.enrich_feature_block(shocked)
    assert (
        changed.loc[129, "atr_change_10d_pre"]
        == original.loc[129, "atr_change_10d_pre"]
    )
    assert (
        changed.loc[129, "atr_change_percentile_60"]
        == original.loc[129, "atr_change_percentile_60"]
    )
    assert (
        changed.loc[129, "breakout_range_ratio"]
        > original.loc[129, "breakout_range_ratio"]
    )


def test_p2_filter_masks_encode_symmetric_direct_hypotheses() -> None:
    frame = pd.DataFrame(
        {
            "direction": ["long", "long", "short", "short"],
            "ma_slope_aligned": [True, True, True, True],
            "atr_path_q": pd.Series([1, 5, 5, 1], dtype="Int64"),
            "breakout_style": ["BURST", "BURST", "BURST", "BURST"],
            "persistent_contraction": [True, False, False, True],
            "persistent_expansion": [False, True, True, False],
        }
    )
    masks = MODULE.filter_masks(frame)
    assert masks["HYPOTHESIS_EXTREME_BURST"].tolist() == [
        True,
        False,
        True,
        False,
    ]
    assert masks["HYPOTHESIS_PERSISTENT_BURST"].tolist() == [
        True,
        False,
        True,
        False,
    ]


def test_p2_spearman_is_positional_when_series_indexes_differ() -> None:
    left = pd.Series([1.0, 2.0, 3.0], index=[10, 11, 12])
    right = pd.Series([3.0, 2.0, 1.0], index=[20, 21, 22])
    assert MODULE._spearman(left, right) == -1.0
