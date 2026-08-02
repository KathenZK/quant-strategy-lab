from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/hype/15m-multidimensional-trend-pyramiding/scripts"
    / "research_hype_15m_mdtp.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_15m_mdtp_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MDTP = load_module()


def synthetic_frame(rows: int = 800) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    trend = np.linspace(100.0, 125.0, rows)
    wave = 0.5 * np.sin(np.arange(rows) / 13.0)
    close = trend + wave
    return pd.DataFrame(
        {
            "open": close - 0.03,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000.0 + 25.0 * np.cos(np.arange(rows) / 7.0),
        },
        index=index,
    )


def compact_windows():
    return MDTP.FeatureWindows(
        h1_momentum=(2, 4, 8),
        h4_momentum=(2, 3, 4),
        h1_er=4,
        h4_er=3,
        h1_donchian=8,
        h4_donchian=4,
        h1_volume=4,
        h4_volume=3,
        h1_scale=24,
        h4_scale=12,
        slow_ema_h1=8,
        atr_h1=4,
        vol_target_m15=16,
    )


def test_higher_timeframe_features_use_only_previous_completed_bin() -> None:
    frame = synthetic_frame()
    features = MDTP.build_feature_set(frame, compact_windows())
    h1 = MDTP.resample_ohlcv(frame, "1h")

    aligned_ts = pd.Timestamp("2026-01-01 01:00:00", tz="UTC")
    assert features["h1"].loc[aligned_ts, "_close"] == h1.loc[
        pd.Timestamp("2026-01-01 00:00:00", tz="UTC"),
        "close",
    ]


def test_future_bar_mutation_does_not_change_prior_features() -> None:
    frame = synthetic_frame()
    windows = compact_windows()
    before = MDTP.build_feature_set(frame, windows)

    mutated = frame.copy()
    mutated.iloc[-1, mutated.columns.get_loc("close")] *= 1.8
    mutated.iloc[-1, mutated.columns.get_loc("high")] = mutated.iloc[-1]["close"] + 0.25
    after = MDTP.build_feature_set(mutated, windows)

    cutoff = frame.index[-2]
    columns = [
        "price_volume_score_jump",
        "jump_concentration",
        "slow_ema",
        "atr",
    ]
    pd.testing.assert_frame_equal(
        before["h1"].loc[:cutoff, columns],
        after["h1"].loc[:cutoff, columns],
    )
    pd.testing.assert_frame_equal(
        before["h4"].loc[:cutoff, columns],
        after["h4"].loc[:cutoff, columns],
    )


def test_addition_requires_profitable_campaign() -> None:
    index = pd.date_range("2026-01-01", periods=7, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 99.0, 103.0, 104.0, 104.0],
            "high": [101.0, 101.0, 101.0, 103.0, 105.0, 105.0, 105.0],
            "low": [99.0, 99.0, 99.0, 98.0, 102.0, 103.0, 103.0],
            "close": [100.0, 100.0, 100.0, 102.0, 104.0, 104.0, 104.0],
            "volume": [1000.0] * 7,
        },
        index=index,
    )
    state = pd.DataFrame(
        {
            "direction": [0, 1, 1, 1, 1, 0, 0],
            "target_allocation": [0.0, 0.5, 1.0, 1.0, 1.0, 0.0, 0.0],
            "stage": [0, 1, 2, 3, 3, 0, 0],
            "recovery": [False] * 7,
            "block_add": [False] * 7,
            "donchian_exit_long": [False] * 7,
            "donchian_exit_short": [False] * 7,
            "score_decay": [False] * 7,
            "regime_label": ["range", "strong_up", "strong_up", "strong_up", "strong_up", "range", "range"],
        },
        index=index,
    )
    features = {
        "m15": pd.DataFrame({"atr": [10.0] * 7}, index=index),
    }
    config = MDTP.StrategyConfig(
        warmup_days=0,
        min_rebalance=0.1,
        trail_atr=4.0,
    )
    run = MDTP.simulate(
        name="profitable_add_test",
        frame=frame,
        funding=pd.Series(0.0, index=index),
        state=state,
        features=features,
        config=config,
        variant=MDTP.VARIANTS[2],
        fee_per_fill=0.0,
        slippage_per_fill=0.0,
        include_funding=False,
    )

    adds = run.actions.loc[run.actions["action"].eq("add")]
    assert len(adds) == 1
    assert pd.Timestamp(adds.iloc[0]["ts"]) == index[4]
