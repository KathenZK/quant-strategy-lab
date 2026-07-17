"""Expandable HYPE 15m research factor library.

The registry is intentionally separate from ``default_registry`` so this
research family cannot silently alter another asset's feature surface.  Every
factor is causal at the close of the current bar.  Forward-looking labels are
implemented only in the family research scripts.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, FactorRegistry, PandasFactor


FrameFn = Callable[[pd.DataFrame], pd.Series]


class FunctionalFactor(PandasFactor):
    def __init__(
        self,
        *,
        name: str,
        category: str,
        frequency: str,
        lookback: int,
        inputs: tuple[str, ...],
        description: str,
        formula: str,
        direction: str,
        fn: FrameFn,
        parameters: dict[str, object] | None = None,
    ) -> None:
        self.name = name
        self._parameters = parameters or {}
        self.metadata = FactorMetadata(
            name=name,
            category=category,
            frequency=frequency,
            lookback=lookback,
            inputs=inputs,
            market_types=("perp",),
            description=description,
            formula=formula,
            direction=direction,
        )
        self._fn = fn

    def parameters(self) -> dict[str, object]:
        return dict(self._parameters)

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        values = self._fn(frame)
        return pd.Series(values, index=frame.index, dtype="float64")


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0.0, np.nan)


def _ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def _rolling_std(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).std(ddof=0)


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    return _safe_div(series - mean, _rolling_std(series, window))


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).rolling(window, min_periods=window).mean()
    loss = (-delta.clip(upper=0.0)).rolling(window, min_periods=window).mean()
    result = 100.0 - 100.0 / (1.0 + _safe_div(gain, loss))
    result = result.where(loss.ne(0.0), 100.0)
    result = result.where(gain.ne(0.0), 0.0)
    return result.where(~(gain.eq(0.0) & loss.eq(0.0)), 50.0)


def _atr_percent(frame: pd.DataFrame, window: int) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return _safe_div(
        true_range.rolling(window, min_periods=window).mean(), frame["close"]
    )


def _donchian_position(frame: pd.DataFrame, window: int) -> pd.Series:
    prior_high = frame["high"].rolling(window, min_periods=window).max().shift(1)
    prior_low = frame["low"].rolling(window, min_periods=window).min().shift(1)
    return _safe_div(frame["close"] - prior_low, prior_high - prior_low)


def _efficiency_ratio(close: pd.Series, window: int) -> pd.Series:
    displacement = close.diff(window).abs()
    path = close.diff().abs().rolling(window, min_periods=window).sum()
    return _safe_div(displacement, path)


def _return_autocorrelation(close: pd.Series, window: int) -> pd.Series:
    returns = close.pct_change()
    return returns.rolling(window, min_periods=window).corr(returns.shift(1))


def _volume_return_correlation(frame: pd.DataFrame, window: int) -> pd.Series:
    returns = frame["close"].pct_change()
    volume_change = np.log1p(frame["quote_volume"]).diff()
    return returns.rolling(window, min_periods=window).corr(volume_change)


def _amihud(frame: pd.DataFrame, window: int) -> pd.Series:
    daily_scale = 1_000_000_000.0
    impact = _safe_div(frame["close"].pct_change().abs(), frame["quote_volume"])
    return impact.rolling(window, min_periods=window).mean() * daily_scale


def _trend_strength(frame: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    spread = _safe_div(_ema(frame["close"], fast) - _ema(frame["close"], slow), frame["close"])
    return _safe_div(spread, _atr_percent(frame, 14))


def _adx(frame: pd.DataFrame, window: int) -> pd.Series:
    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0),
        index=frame.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0),
        index=frame.index,
    )
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    smoothed_tr = true_range.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    plus_di = 100.0 * _safe_div(
        plus_dm.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean(),
        smoothed_tr,
    )
    minus_di = 100.0 * _safe_div(
        minus_dm.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean(),
        smoothed_tr,
    )
    dx = 100.0 * _safe_div((plus_di - minus_di).abs(), plus_di + minus_di)
    return dx.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def _stochastic(frame: pd.DataFrame, window: int) -> pd.Series:
    rolling_low = frame["low"].rolling(window, min_periods=window).min()
    rolling_high = frame["high"].rolling(window, min_periods=window).max()
    return 100.0 * _safe_div(frame["close"] - rolling_low, rolling_high - rolling_low)


def _cci(frame: pd.DataFrame, window: int) -> pd.Series:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    mean = typical.rolling(window, min_periods=window).mean()
    deviation = typical.rolling(window, min_periods=window).apply(
        lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True
    )
    return _safe_div(typical - mean, 0.015 * deviation)


def _obv_flow(frame: pd.DataFrame, window: int) -> pd.Series:
    signed_volume = np.sign(frame["close"].diff()).fillna(0.0) * frame["volume"]
    return _safe_div(
        signed_volume.rolling(window, min_periods=window).sum(),
        frame["volume"].rolling(window, min_periods=window).sum(),
    )


def _chaikin_money_flow(frame: pd.DataFrame, window: int) -> pd.Series:
    multiplier = _safe_div(
        2.0 * frame["close"] - frame["high"] - frame["low"],
        frame["high"] - frame["low"],
    ).fillna(0.0)
    return _safe_div(
        (multiplier * frame["volume"]).rolling(window, min_periods=window).sum(),
        frame["volume"].rolling(window, min_periods=window).sum(),
    )


def _make(
    *,
    name: str,
    category: str,
    lookback: int,
    inputs: tuple[str, ...],
    description: str,
    formula: str,
    direction: str,
    fn: FrameFn,
    parameters: dict[str, object],
) -> FunctionalFactor:
    return FunctionalFactor(
        name=name,
        category=category,
        frequency="15m",
        lookback=lookback,
        inputs=inputs,
        description=description,
        formula=formula,
        direction=direction,
        fn=fn,
        parameters=parameters,
    )


def build_hype_15m_factors() -> list[PandasFactor]:
    factors: list[PandasFactor] = []

    for window in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 192):
        factors.append(
            _make(
                name=f"ret_{window}",
                category="momentum",
                lookback=window + 1,
                inputs=("close",),
                description=f"Close-to-close return over {window} bars.",
                formula=f"close / close.shift({window}) - 1",
                direction="positive_bullish",
                fn=lambda frame, w=window: frame["close"].pct_change(w),
                parameters={"window": window},
            )
        )

    for period in (5, 8, 13, 21, 34, 55, 96, 144, 192, 384):
        factors.append(
            _make(
                name=f"ema_distance_{period}",
                category="trend",
                lookback=period,
                inputs=("close",),
                description=f"Close distance from EMA({period}).",
                formula=f"close / EMA(close, {period}) - 1",
                direction="positive_bullish",
                fn=lambda frame, p=period: _safe_div(
                    frame["close"], _ema(frame["close"], p)
                )
                - 1.0,
                parameters={"period": period},
            )
        )

    for period in (8, 21, 55, 96, 192, 384):
        for lag in (1, 4, 12):
            factors.append(
                _make(
                    name=f"ema_slope_{period}_{lag}",
                    category="trend",
                    lookback=period + lag,
                    inputs=("close",),
                    description=f"Per-bar slope of EMA({period}) over {lag} bars.",
                    formula=f"EMA(close, {period}).pct_change({lag}) / {lag}",
                    direction="positive_bullish",
                    fn=lambda frame, p=period, lag_bars=lag: _ema(
                        frame["close"], p
                    ).pct_change(lag_bars)
                    / lag_bars,
                    parameters={"period": period, "slope_lag": lag},
                )
            )

    for fast, slow in (
        (5, 13),
        (8, 21),
        (13, 34),
        (21, 55),
        (34, 96),
        (55, 96),
        (96, 192),
        (192, 384),
    ):
        factors.append(
            _make(
                name=f"ema_spread_{fast}_{slow}",
                category="trend",
                lookback=slow,
                inputs=("close",),
                description=f"Normalized EMA({fast}) minus EMA({slow}).",
                formula=f"(EMA(close, {fast}) - EMA(close, {slow})) / EMA(close, {slow})",
                direction="positive_bullish",
                fn=lambda frame, f=fast, s=slow: _safe_div(
                    _ema(frame["close"], f) - _ema(frame["close"], s),
                    _ema(frame["close"], s),
                ),
                parameters={"fast": fast, "slow": slow},
            )
        )

    for window in (7, 14, 28, 56):
        factors.append(
            _make(
                name=f"rsi_{window}",
                category="momentum",
                lookback=window + 1,
                inputs=("close",),
                description=f"Simple rolling RSI({window}) scaled from 0 to 100.",
                formula=f"100 - 100 / (1 + mean(gain,{window}) / mean(loss,{window}))",
                direction="context_dependent",
                fn=lambda frame, w=window: _rsi(frame["close"], w),
                parameters={"window": window},
            )
        )

    for window in (7, 14, 28, 56, 96):
        factors.append(
            _make(
                name=f"atr_pct_{window}",
                category="volatility",
                lookback=window + 1,
                inputs=("high", "low", "close"),
                description=f"Mean true range divided by close over {window} bars.",
                formula=f"SMA(true_range, {window}) / close",
                direction="non_directional_regime",
                fn=lambda frame, w=window: _atr_percent(frame, w),
                parameters={"window": window},
            )
        )

    for window in (7, 14, 28, 56, 96, 192):
        factors.append(
            _make(
                name=f"realized_vol_{window}",
                category="volatility",
                lookback=window + 1,
                inputs=("close",),
                description=f"Standard deviation of close returns over {window} bars.",
                formula=f"std(close.pct_change(), {window})",
                direction="non_directional_regime",
                fn=lambda frame, w=window: _rolling_std(frame["close"].pct_change(), w),
                parameters={"window": window},
            )
        )

    for window in (20, 50, 96):
        factors.extend(
            [
                _make(
                    name=f"bollinger_distance_{window}",
                    category="mean_reversion",
                    lookback=window,
                    inputs=("close",),
                    description=f"Close z-distance from its {window}-bar mean.",
                    formula=f"(close - SMA(close,{window})) / STD(close,{window})",
                    direction="context_dependent",
                    fn=lambda frame, w=window: _rolling_zscore(frame["close"], w),
                    parameters={"window": window},
                ),
                _make(
                    name=f"bollinger_width_{window}",
                    category="volatility",
                    lookback=window,
                    inputs=("close",),
                    description=f"Four-standard-deviation band width over {window} bars.",
                    formula=f"4 * STD(close,{window}) / SMA(close,{window})",
                    direction="non_directional_regime",
                    fn=lambda frame, w=window: _safe_div(
                        4.0 * _rolling_std(frame["close"], w),
                        frame["close"].rolling(w, min_periods=w).mean(),
                    ),
                    parameters={"window": window},
                ),
            ]
        )

    for window in (20, 48, 96, 192):
        factors.append(
            _make(
                name=f"donchian_position_{window}",
                category="trend",
                lookback=window + 1,
                inputs=("high", "low", "close"),
                description=f"Close position inside the prior {window}-bar channel.",
                formula=f"(close - prior_low_{window}) / (prior_high_{window} - prior_low_{window})",
                direction="positive_bullish",
                fn=lambda frame, w=window: _donchian_position(frame, w),
                parameters={"window": window, "uses_prior_channel": True},
            )
        )

    for field, prefix, inputs in (
        ("volume", "volume_ratio", ("volume",)),
        ("quote_volume", "quote_volume_ratio", ("quote_volume",)),
        ("trade_count", "trade_count_ratio", ("trade_count",)),
    ):
        for window in (5, 20, 48, 96, 192):
            factors.append(
                _make(
                    name=f"{prefix}_{window}",
                    category="liquidity",
                    lookback=window,
                    inputs=inputs,
                    description=f"Current {field} divided by its {window}-bar mean.",
                    formula=f"{field} / SMA({field},{window})",
                    direction="non_directional_regime",
                    fn=lambda frame, w=window, column=field: _safe_div(
                        frame[column], frame[column].rolling(w, min_periods=w).mean()
                    ),
                    parameters={"field": field, "window": window},
                )
            )

    direct_specs: list[tuple[str, str, int, tuple[str, ...], str, str, str, FrameFn]] = [
        (
            "vwap_distance",
            "liquidity",
            1,
            ("close", "vwap"),
            "Close distance from current-bar VWAP.",
            "(close - vwap) / vwap",
            "positive_bullish",
            lambda f: _safe_div(f["close"] - f["vwap"], f["vwap"]),
        ),
        (
            "candle_body_strength",
            "price_action",
            1,
            ("open", "high", "low", "close"),
            "Signed candle body divided by candle range.",
            "(close - open) / (high - low)",
            "positive_bullish",
            lambda f: _safe_div(f["close"] - f["open"], f["high"] - f["low"]),
        ),
        (
            "close_location",
            "price_action",
            1,
            ("high", "low", "close"),
            "Centered close location inside the current candle.",
            "2 * (close - low) / (high - low) - 1",
            "positive_bullish",
            lambda f: 2.0 * _safe_div(f["close"] - f["low"], f["high"] - f["low"])
            - 1.0,
        ),
        (
            "upper_wick_ratio",
            "price_action",
            1,
            ("open", "high", "low", "close"),
            "Upper wick divided by candle range.",
            "(high - max(open,close)) / (high - low)",
            "negative_bullish",
            lambda f: _safe_div(
                f["high"] - f[["open", "close"]].max(axis=1), f["high"] - f["low"]
            ),
        ),
        (
            "lower_wick_ratio",
            "price_action",
            1,
            ("open", "high", "low", "close"),
            "Lower wick divided by candle range.",
            "(min(open,close) - low) / (high - low)",
            "positive_bullish",
            lambda f: _safe_div(
                f[["open", "close"]].min(axis=1) - f["low"], f["high"] - f["low"]
            ),
        ),
        (
            "range_pct",
            "volatility",
            1,
            ("high", "low", "close"),
            "Current high-low range divided by close.",
            "(high - low) / close",
            "non_directional_regime",
            lambda f: _safe_div(f["high"] - f["low"], f["close"]),
        ),
        (
            "mark_distance",
            "derivatives",
            1,
            ("close", "mark_price"),
            "Trade close distance from mark price.",
            "(close - mark_price) / mark_price",
            "context_dependent",
            lambda f: _safe_div(f["close"] - f["mark_price"], f["mark_price"]),
        ),
        (
            "mark_return_1",
            "derivatives",
            2,
            ("mark_price",),
            "One-bar mark-price return.",
            "mark_price.pct_change(1)",
            "positive_bullish",
            lambda f: f["mark_price"].pct_change(),
        ),
        (
            "funding_rate",
            "derivatives",
            1,
            ("funding_rate",),
            "Most recently published funding rate as of the closed bar.",
            "asof(funding_rate, bar_close)",
            "context_dependent",
            lambda f: f["funding_rate"],
        ),
        (
            "funding_change",
            "derivatives",
            2,
            ("funding_rate",),
            "Change in the as-of funding rate.",
            "funding_rate.diff(1)",
            "context_dependent",
            lambda f: f["funding_rate"].diff(),
        ),
        (
            "funding_age_scaled",
            "derivatives",
            1,
            ("funding_age_hours",),
            "Hours since the last funding event divided by eight.",
            "funding_age_hours / 8",
            "non_directional_regime",
            lambda f: f["funding_age_hours"] / 8.0,
        ),
    ]
    for name, category, lookback, inputs, description, formula, direction, fn in direct_specs:
        factors.append(
            _make(
                name=name,
                category=category,
                lookback=lookback,
                inputs=inputs,
                description=description,
                formula=formula,
                direction=direction,
                fn=fn,
                parameters={"formula_id": name},
            )
        )

    for window in (20, 96, 288):
        factors.append(
            _make(
                name=f"mark_distance_zscore_{window}",
                category="derivatives",
                lookback=window,
                inputs=("close", "mark_price"),
                description=f"Z-score of trade-to-mark distance over {window} bars.",
                formula=f"zscore((close-mark_price)/mark_price,{window})",
                direction="context_dependent",
                fn=lambda frame, w=window: _rolling_zscore(
                    _safe_div(frame["close"] - frame["mark_price"], frame["mark_price"]), w
                ),
                parameters={"window": window},
            )
        )

    for window in (96, 288):
        factors.append(
            _make(
                name=f"funding_zscore_{window}",
                category="derivatives",
                lookback=window,
                inputs=("funding_rate",),
                description=f"Bar-aligned funding-rate z-score over {window} bars.",
                formula=f"zscore(asof_funding_rate,{window})",
                direction="context_dependent",
                fn=lambda frame, w=window: _rolling_zscore(frame["funding_rate"], w),
                parameters={"window_bars": window},
            )
        )

    for window in (20, 48, 96):
        factors.extend(
            [
                _make(
                    name=f"efficiency_ratio_{window}",
                    category="regime",
                    lookback=window + 1,
                    inputs=("close",),
                    description=f"Kaufman path efficiency over {window} bars.",
                    formula=f"abs(close-close.shift({window})) / sum(abs(diff(close)),{window})",
                    direction="non_directional_trend_strength",
                    fn=lambda frame, w=window: _efficiency_ratio(frame["close"], w),
                    parameters={"window": window},
                ),
                _make(
                    name=f"return_autocorr_{window}",
                    category="regime",
                    lookback=window + 2,
                    inputs=("close",),
                    description=f"Lag-one return autocorrelation over {window} bars.",
                    formula=f"rolling_corr(ret_1,ret_1.shift(1),{window})",
                    direction="non_directional_regime",
                    fn=lambda frame, w=window: _return_autocorrelation(frame["close"], w),
                    parameters={"window": window, "lag": 1},
                ),
                _make(
                    name=f"volume_return_corr_{window}",
                    category="liquidity",
                    lookback=window + 2,
                    inputs=("close", "quote_volume"),
                    description=f"Return/quote-volume-change correlation over {window} bars.",
                    formula=f"rolling_corr(ret_1,diff(log1p(quote_volume)),{window})",
                    direction="context_dependent",
                    fn=lambda frame, w=window: _volume_return_correlation(frame, w),
                    parameters={"window": window},
                ),
                _make(
                    name=f"amihud_{window}",
                    category="liquidity",
                    lookback=window + 1,
                    inputs=("close", "quote_volume"),
                    description=f"Scaled Amihud price-impact estimate over {window} bars.",
                    formula=f"1e9 * SMA(abs(ret_1)/quote_volume,{window})",
                    direction="negative_liquidity",
                    fn=lambda frame, w=window: _amihud(frame, w),
                    parameters={"window": window, "scale": 1_000_000_000.0},
                ),
            ]
        )

    for fast, slow in ((21, 55), (55, 96), (96, 192)):
        factors.append(
            _make(
                name=f"trend_strength_{fast}_{slow}",
                category="regime",
                lookback=max(slow, 15),
                inputs=("high", "low", "close"),
                description=f"EMA({fast},{slow}) spread normalized by ATR(14).",
                formula=f"((EMA{fast}-EMA{slow})/close) / ATR_PCT_14",
                direction="positive_bullish",
                fn=lambda frame, f=fast, s=slow: _trend_strength(frame, f, s),
                parameters={"fast": fast, "slow": slow, "atr_window": 14},
            )
        )

    for window in (192, 672):
        factors.append(
            _make(
                name=f"atr_percentile_{window}",
                category="regime",
                lookback=window + 14,
                inputs=("high", "low", "close"),
                description=f"Current ATR(14) percentile inside {window} bars.",
                formula=f"rolling_percentile(ATR_PCT_14,{window})",
                direction="non_directional_regime",
                fn=lambda frame, w=window: _atr_percent(frame, 14).rolling(
                    w, min_periods=w
                ).rank(pct=True),
                parameters={"window": window, "atr_window": 14},
            )
        )

    for window in (48, 96):
        factors.append(
            _make(
                name=f"return_skew_{window}",
                category="momentum",
                lookback=window + 1,
                inputs=("close",),
                description=f"Skewness of one-bar returns over {window} bars.",
                formula=f"skew(ret_1,{window})",
                direction="positive_upside_asymmetry",
                fn=lambda frame, w=window: frame["close"].pct_change().rolling(
                    w, min_periods=w
                ).skew(),
                parameters={"window": window},
            )
        )

    taker_imbalance = lambda frame: 2.0 * _safe_div(  # noqa: E731
        frame["taker_buy_volume"], frame["volume"]
    ) - 1.0
    for name, inputs, formula, fn in (
        (
            "taker_buy_volume_ratio",
            ("taker_buy_volume", "volume"),
            "taker_buy_volume / volume",
            lambda f: _safe_div(f["taker_buy_volume"], f["volume"]),
        ),
        (
            "taker_buy_quote_ratio",
            ("taker_buy_quote_volume", "quote_volume"),
            "taker_buy_quote_volume / quote_volume",
            lambda f: _safe_div(f["taker_buy_quote_volume"], f["quote_volume"]),
        ),
        (
            "taker_imbalance",
            ("taker_buy_volume", "volume"),
            "2 * taker_buy_volume / volume - 1",
            taker_imbalance,
        ),
    ):
        factors.append(
            _make(
                name=name,
                category="order_flow",
                lookback=1,
                inputs=inputs,
                description="Bar-level aggressive-buy share or signed imbalance.",
                formula=formula,
                direction="positive_bullish",
                fn=fn,
                parameters={"formula_id": name},
            )
        )

    for window in (5, 20, 48, 96, 192):
        factors.append(
            _make(
                name=f"taker_imbalance_mean_{window}",
                category="order_flow",
                lookback=window,
                inputs=("taker_buy_volume", "volume"),
                description=f"Mean taker imbalance over {window} bars.",
                formula=f"SMA(2*taker_buy_volume/volume-1,{window})",
                direction="positive_bullish",
                fn=lambda frame, w=window: taker_imbalance(frame).rolling(
                    w, min_periods=w
                ).mean(),
                parameters={"window": window},
            )
        )

    for window in (20, 96):
        factors.append(
            _make(
                name=f"taker_imbalance_zscore_{window}",
                category="order_flow",
                lookback=window,
                inputs=("taker_buy_volume", "volume"),
                description=f"Taker imbalance z-score over {window} bars.",
                formula=f"zscore(2*taker_buy_volume/volume-1,{window})",
                direction="positive_bullish",
                fn=lambda frame, w=window: _rolling_zscore(taker_imbalance(frame), w),
                parameters={"window": window},
            )
        )

    factors.append(
        _make(
            name="average_trade_size_quote",
            category="liquidity",
            lookback=1,
            inputs=("quote_volume", "trade_count"),
            description="Average quote notional per trade in the current bar.",
            formula="quote_volume / trade_count",
            direction="non_directional_regime",
            fn=lambda frame: _safe_div(frame["quote_volume"], frame["trade_count"]),
            parameters={"formula_id": "average_trade_size_quote"},
        )
    )
    for window in (20, 96):
        factors.append(
            _make(
                name=f"average_trade_size_ratio_{window}",
                category="liquidity",
                lookback=window,
                inputs=("quote_volume", "trade_count"),
                description=f"Average trade size divided by its {window}-bar mean.",
                formula=f"avg_trade_size / SMA(avg_trade_size,{window})",
                direction="non_directional_regime",
                fn=lambda frame, w=window: (
                    lambda size: _safe_div(size, size.rolling(w, min_periods=w).mean())
                )(_safe_div(frame["quote_volume"], frame["trade_count"])),
                parameters={"window": window},
            )
        )

    mark_specs: list[tuple[str, str, str, FrameFn]] = [
        (
            "mark_range_pct",
            "(mark_high - mark_low) / mark_price",
            "non_directional_regime",
            lambda f: _safe_div(f["mark_high"] - f["mark_low"], f["mark_price"]),
        ),
        (
            "mark_body_strength",
            "(mark_price - mark_open) / (mark_high - mark_low)",
            "positive_bullish",
            lambda f: _safe_div(
                f["mark_price"] - f["mark_open"], f["mark_high"] - f["mark_low"]
            ),
        ),
        (
            "mark_close_location",
            "2 * (mark_price - mark_low) / (mark_high - mark_low) - 1",
            "positive_bullish",
            lambda f: 2.0
            * _safe_div(f["mark_price"] - f["mark_low"], f["mark_high"] - f["mark_low"])
            - 1.0,
        ),
        (
            "mark_distance_change",
            "diff((close - mark_price) / mark_price)",
            "context_dependent",
            lambda f: _safe_div(
                f["close"] - f["mark_price"], f["mark_price"]
            ).diff(),
        ),
    ]
    for name, formula, direction, fn in mark_specs:
        inputs = (
            ("close", "mark_price")
            if name == "mark_distance_change"
            else ("mark_open", "mark_high", "mark_low", "mark_price")
        )
        factors.append(
            _make(
                name=name,
                category="derivatives",
                lookback=2 if name == "mark_distance_change" else 1,
                inputs=inputs,
                description="Mark-price candle structure or trade/mark dislocation change.",
                formula=formula,
                direction=direction,
                fn=fn,
                parameters={"formula_id": name},
            )
        )

    for window in (14, 28):
        factors.extend(
            [
                _make(
                    name=f"adx_{window}",
                    category="regime",
                    lookback=2 * window,
                    inputs=("high", "low", "close"),
                    description=f"Wilder ADX({window}) trend-strength estimate.",
                    formula=f"Wilder_ADX(high,low,close,{window})",
                    direction="non_directional_trend_strength",
                    fn=lambda frame, w=window: _adx(frame, w),
                    parameters={"window": window},
                ),
                _make(
                    name=f"stochastic_{window}",
                    category="momentum",
                    lookback=window,
                    inputs=("high", "low", "close"),
                    description=f"Stochastic close location over {window} bars.",
                    formula=f"100*(close-lowest(low,{window}))/(highest(high,{window})-lowest(low,{window}))",
                    direction="context_dependent",
                    fn=lambda frame, w=window: _stochastic(frame, w),
                    parameters={"window": window},
                ),
            ]
        )

    for window in (20, 50):
        factors.append(
            _make(
                name=f"cci_{window}",
                category="momentum",
                lookback=window,
                inputs=("high", "low", "close"),
                description=f"Commodity Channel Index over {window} bars.",
                formula=f"CCI(typical_price,{window})",
                direction="context_dependent",
                fn=lambda frame, w=window: _cci(frame, w),
                parameters={"window": window},
            )
        )

    for window in (20, 96):
        factors.extend(
            [
                _make(
                    name=f"obv_flow_{window}",
                    category="order_flow",
                    lookback=window + 1,
                    inputs=("close", "volume"),
                    description=f"Signed volume flow normalized over {window} bars.",
                    formula=f"sum(sign(diff(close))*volume,{window})/sum(volume,{window})",
                    direction="positive_bullish",
                    fn=lambda frame, w=window: _obv_flow(frame, w),
                    parameters={"window": window},
                ),
                _make(
                    name=f"chaikin_money_flow_{window}",
                    category="order_flow",
                    lookback=window,
                    inputs=("high", "low", "close", "volume"),
                    description=f"Chaikin money flow over {window} bars.",
                    formula=f"sum(CLV*volume,{window})/sum(volume,{window})",
                    direction="positive_bullish",
                    fn=lambda frame, w=window: _chaikin_money_flow(frame, w),
                    parameters={"window": window},
                ),
            ]
        )

    time_specs: list[tuple[str, str, FrameFn]] = [
        (
            "hour_sin",
            "sin(2*pi*UTC_hour/24)",
            lambda f: np.sin(2.0 * np.pi * pd.to_datetime(f["ts"], utc=True).dt.hour / 24.0),
        ),
        (
            "hour_cos",
            "cos(2*pi*UTC_hour/24)",
            lambda f: np.cos(2.0 * np.pi * pd.to_datetime(f["ts"], utc=True).dt.hour / 24.0),
        ),
        (
            "weekday_sin",
            "sin(2*pi*UTC_weekday/7)",
            lambda f: np.sin(2.0 * np.pi * pd.to_datetime(f["ts"], utc=True).dt.dayofweek / 7.0),
        ),
        (
            "weekday_cos",
            "cos(2*pi*UTC_weekday/7)",
            lambda f: np.cos(2.0 * np.pi * pd.to_datetime(f["ts"], utc=True).dt.dayofweek / 7.0),
        ),
        (
            "is_weekend",
            "1[UTC_weekday>=5]",
            lambda f: (pd.to_datetime(f["ts"], utc=True).dt.dayofweek >= 5).astype(float),
        ),
    ]
    for name, formula, fn in time_specs:
        factors.append(
            _make(
                name=name,
                category="seasonality",
                lookback=1,
                inputs=("ts",),
                description="Deterministic UTC calendar seasonality feature.",
                formula=formula,
                direction="context_dependent",
                fn=fn,
                parameters={"timezone": "UTC"},
            )
        )

    return factors


def hype_15m_registry() -> FactorRegistry:
    registry = FactorRegistry()
    for factor in build_hype_15m_factors():
        registry.register(factor)
    return registry


__all__ = ["FunctionalFactor", "build_hype_15m_factors", "hype_15m_registry"]
