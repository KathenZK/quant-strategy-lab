from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.research.ema_cross_quality import (
    CrossQualityConfig,
    discover_symbol_files,
    extract_cross_events,
)


def _manual_feature_frame(*, same_bar_target_and_stop: bool = False) -> pd.DataFrame:
    periods = 20
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=periods, freq="15min", tz="UTC"),
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.0,
            "ema96": 100.0,
            "ema384": 100.0,
            "ema_spread": [-0.02] * 10 + [0.02] * 10,
            "ema96_slope16": 0.01,
            "ema96_slope48": 0.02,
            "ema384_slope96": 0.003,
            "spread_slope4": 0.01,
            "spread_slope16": 0.02,
            "spread_slope48": 0.03,
            "cross_angle_proxy": 0.0095,
            "regime_age": np.nan,
            "previous_regime_age": np.nan,
            "adx14": 25.0,
            "adx28": 28.0,
            "adx28_slope16": 2.0,
            "pdi28": 35.0,
            "mdi28": 20.0,
            "atr_pct96": 0.01,
            "atr_pct336": 0.01,
            "atr_pct672": 0.01,
            "atr_ratio96_672": 1.0,
            "realized_vol96": 0.01,
            "realized_vol672": 0.01,
            "volatility_ratio96_672": 1.0,
            "volatility_pctile672": 0.5,
            "rvol96": 1.2,
            "rvol192": 1.1,
            "rvol672": 1.0,
            "quote_rvol96": 1.2,
            "quote_rvol192": 1.1,
            "mfi14": 60.0,
            "cmf20": 0.1,
            "obv_mom48_norm": 0.2,
            "obv_mom96_norm": 0.3,
            "candle_pos": 0.7,
            "body_range": 0.4,
            "ret16": 0.01,
            "ret48": 0.02,
            "ret96": 0.03,
            "ret192": 0.04,
            "donchian_pos96": 0.8,
            "donchian_pos192": 0.75,
            "cross_churn192": 1.0,
            "cross_churn672": 2.0,
            "symbol_ret672": 0.2,
            "symbol_realized_vol672": 0.03,
            "symbol_trend_eff672": 0.4,
            "symbol_quote_volume_mean672": 1_000_000.0,
            "symbol_quote_volume_ratio96_672": 1.3,
        }
    )
    if same_bar_target_and_stop:
        frame.loc[11, "high"] = 103.0
        frame.loc[11, "low"] = 98.5
    else:
        frame.loc[12, "high"] = 103.0
    return frame


def test_extract_cross_events_labels_target_before_stop() -> None:
    config = CrossQualityConfig(
        exchange="binance",
        horizon_bars=4,
        target_atr=2.0,
        stop_atr=1.0,
        min_bars=0,
    )

    events = extract_cross_events(_manual_feature_frame(), config)

    assert len(events) == 1
    event = events.iloc[0]
    assert event["side"] == "long"
    assert bool(event["target_before_stop"])
    assert event["first_target_bar"] == 2
    assert pd.isna(event["first_stop_bar"])
    assert event["future_mfe_atr"] >= 2.0


def test_extract_cross_events_treats_same_bar_target_and_stop_as_not_clean() -> None:
    config = CrossQualityConfig(
        exchange="binance",
        horizon_bars=4,
        target_atr=2.0,
        stop_atr=1.0,
        min_bars=0,
    )

    events = extract_cross_events(_manual_feature_frame(same_bar_target_and_stop=True), config)

    assert len(events) == 1
    event = events.iloc[0]
    assert not bool(event["target_before_stop"])
    assert event["first_target_bar"] == 1
    assert event["first_stop_bar"] == 1


def test_discover_symbol_files_filters_requested_symbols(tmp_path) -> None:
    root = tmp_path / "ohlcv"
    hype = (
        root
        / "exchange=binance"
        / "market_type=perp"
        / "timeframe=15m"
        / "date=2026-01-01"
        / "symbol=hype_usdt_usdt.parquet"
    )
    eth = hype.with_name("symbol=eth_usdt_usdt.parquet")
    hype.parent.mkdir(parents=True)
    hype.touch()
    eth.touch()

    files = discover_symbol_files(
        root,
        CrossQualityConfig(
            exchange="binance",
            symbols=("HYPE/USDT:USDT",),
        ),
    )

    assert list(files) == ["hype_usdt_usdt"]
    assert files["hype_usdt_usdt"] == [hype]
