from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-multi-horizon-ema-forecast"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FREEZE_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_dataset_freeze.json"
NORMALIZED_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"

BASE_FEE = 0.001
BASE_SLIPPAGE = 0.0004
PERIODS_PER_YEAR = 365.25 * 24.0 * 4.0

MEDIUM_PAIRS = ((16, 64), (32, 128), (64, 256), (128, 512))
BASE_WEIGHTS = (0.15, 0.25, 0.35, 0.25)


@dataclass(frozen=True, slots=True)
class Config:
    ema_pairs: tuple[tuple[int, int], ...] = MEDIUM_PAIRS
    weights: tuple[float, ...] = BASE_WEIGHTS
    volatility_span: int = 96
    calibration_min_bars: int = 512
    target_median_abs_forecast: float = 0.50
    coherence_power: float = 0.50
    dead_zone: float = 0.05
    target_annual_volatility: float = 0.80
    max_abs_position: float = 1.0
    no_trade_buffer: float = 0.15
    minimum_position_change: float = 0.05
    max_position_step: float = 0.25
    fee_per_turnover: float = BASE_FEE
    slippage_per_turnover: float = BASE_SLIPPAGE

    def validate(self) -> None:
        if len(self.ema_pairs) != len(self.weights) or not self.ema_pairs:
            raise ValueError("ema_pairs and weights must be non-empty and equally sized")
        if any(fast <= 0 or slow <= fast for fast, slow in self.ema_pairs):
            raise ValueError("each EMA pair must satisfy 0 < fast < slow")
        if any(weight < 0.0 for weight in self.weights):
            raise ValueError("weights must be non-negative")
        if not math.isclose(sum(self.weights), 1.0, abs_tol=1e-12):
            raise ValueError("weights must sum to one")
        if min(self.volatility_span, self.calibration_min_bars) <= 1:
            raise ValueError("volatility and calibration windows must exceed one")
        if not 0.0 < self.target_median_abs_forecast < 1.0:
            raise ValueError("target_median_abs_forecast must be in (0, 1)")
        if self.coherence_power < 0.0:
            raise ValueError("coherence_power must be non-negative")
        if not 0.0 <= self.dead_zone < 1.0:
            raise ValueError("dead_zone must be in [0, 1)")
        if self.target_annual_volatility <= 0.0:
            raise ValueError("target_annual_volatility must be positive")
        if not 0.0 < self.max_abs_position <= 1.0:
            raise ValueError("max_abs_position must be in (0, 1]")
        if min(self.no_trade_buffer, self.minimum_position_change) < 0.0:
            raise ValueError("no-trade parameters must be non-negative")
        if self.max_position_step <= 0.0:
            raise ValueError("max_position_step must be positive")
        if min(self.fee_per_turnover, self.slippage_per_turnover) < 0.0:
            raise ValueError("costs must be non-negative")


BASELINE_CONFIG = Config()


@dataclass(slots=True)
class MarketBook:
    frame: pd.DataFrame
    funding: pd.DataFrame
    terminal_ts: pd.Timestamp


@dataclass(slots=True)
class BacktestResult:
    config: Config
    path: pd.DataFrame
    metrics: dict[str, Any]


def config_payload(config: Config) -> dict[str, Any]:
    payload = asdict(config)
    payload["ema_pairs"] = [list(pair) for pair in config.ema_pairs]
    payload["weights"] = list(config.weights)
    return payload


def config_from_payload(payload: dict[str, Any]) -> Config:
    values = dict(payload)
    values["ema_pairs"] = tuple(tuple(int(value) for value in pair) for pair in values["ema_pairs"])
    values["weights"] = tuple(float(value) for value in values["weights"])
    return Config(**values)


def config_sha256(config: Config) -> str:
    raw = json.dumps(config_payload(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_partitions(root: Path) -> pd.DataFrame:
    paths = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not paths:
        raise RuntimeError(f"no partitions below {root}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)


def load_market() -> pd.DataFrame:
    return _load_partitions(NORMALIZED_ROOT)


def load_funding() -> pd.DataFrame:
    frame = _load_partitions(FUNDING_ROOT)
    if frame["funding_rate"].isna().any():
        raise RuntimeError("funding contains null rates")
    return frame


def build_book(*, terminal_exclusive: pd.Timestamp) -> MarketBook:
    manifest = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if int(manifest["quality"]["blocker_count"]) != 0:
        raise RuntimeError("frozen dataset has quality blockers")
    terminal = pd.Timestamp(terminal_exclusive)
    frozen_terminal = pd.Timestamp(manifest["freeze_contract"]["data_terminal_exclusive"])
    if terminal > frozen_terminal:
        raise RuntimeError("requested terminal exceeds frozen dataset")

    market = load_market()
    market = market.loc[market["ts"] < terminal].copy().reset_index(drop=True)
    expected = pd.date_range(market["ts"].iloc[0], terminal, freq="15min", inclusive="left")
    if len(market) != len(expected) or not pd.DatetimeIndex(market["ts"]).equals(expected):
        raise RuntimeError("market rows do not match the frozen contiguous interval")
    funding = load_funding()
    funding = funding.loc[funding["ts"] < terminal, ["ts", "funding_rate"]].copy()
    return MarketBook(frame=market, funding=funding, terminal_ts=terminal)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def build_forecasts(book: MarketBook, config: Config) -> pd.DataFrame:
    config.validate()
    frame = book.frame[["ts", "open", "high", "low", "close"]].copy()
    close = frame["close"].astype("float64")
    log_return = np.log(close / close.shift(1))
    bar_volatility = (
        log_return.ewm(
            span=config.volatility_span,
            adjust=False,
            min_periods=config.volatility_span,
        )
        .std(bias=False)
        .shift(1)
    )
    annual_volatility = bar_volatility * math.sqrt(PERIODS_PER_YEAR)
    frame["bar_volatility"] = bar_volatility
    frame["annual_volatility"] = annual_volatility

    component_columns: list[str] = []
    for fast, slow in config.ema_pairs:
        spread = _ema(close, fast) / _ema(close, slow).replace(0.0, np.nan) - 1.0
        raw = spread / bar_volatility.replace(0.0, np.nan)
        calibration = (
            raw.abs()
            .expanding(min_periods=max(config.calibration_min_bars, slow))
            .median()
            .shift(1)
        )
        coefficient = math.atanh(config.target_median_abs_forecast)
        forecast = np.tanh(coefficient * raw / calibration.replace(0.0, np.nan))
        stem = f"{fast}_{slow}"
        frame[f"raw_forecast_{stem}"] = raw
        frame[f"calibration_{stem}"] = calibration
        frame[f"forecast_{stem}"] = forecast
        component_columns.append(f"forecast_{stem}")

    components = frame[component_columns]
    weights = np.asarray(config.weights, dtype="float64")
    base_score = components.mul(weights, axis=1).sum(
        axis=1,
        min_count=len(component_columns),
    )
    weighted_magnitude = components.abs().mul(weights, axis=1).sum(
        axis=1,
        min_count=len(component_columns),
    )
    coherence = (base_score.abs() / weighted_magnitude.replace(0.0, np.nan)).clip(0.0, 1.0)
    trend_score = base_score * coherence.pow(config.coherence_power)
    magnitude = ((trend_score.abs() - config.dead_zone) / (1.0 - config.dead_zone)).clip(
        lower=0.0,
        upper=1.0,
    )
    trend_score = np.sign(trend_score) * magnitude
    volatility_scalar = (
        config.target_annual_volatility / annual_volatility.replace(0.0, np.nan)
    ).clip(lower=0.0, upper=1.0)
    target = (
        trend_score
        * volatility_scalar
        * config.max_abs_position
    ).clip(-config.max_abs_position, config.max_abs_position)

    frame["base_score"] = base_score
    frame["coherence"] = coherence
    frame["trend_score"] = trend_score
    frame["volatility_scalar"] = volatility_scalar
    frame["target_close"] = target
    return frame


def boundary_track(
    desired: pd.Series,
    *,
    buffer: float,
    minimum_change: float,
    max_step: float,
    max_abs_position: float,
) -> pd.Series:
    if min(buffer, minimum_change) < 0.0 or max_step <= 0.0 or max_abs_position <= 0.0:
        raise ValueError("invalid boundary tracking parameters")
    output = np.zeros(len(desired), dtype="float64")
    current = 0.0
    for index, value in enumerate(desired.to_numpy("float64")):
        target = 0.0 if not np.isfinite(value) else float(
            np.clip(value, -max_abs_position, max_abs_position)
        )
        lower = max(-max_abs_position, target - buffer)
        upper = min(max_abs_position, target + buffer)
        if current < lower:
            next_position = lower
        elif current > upper:
            next_position = upper
        else:
            next_position = current
        requested_change = next_position - current
        if abs(requested_change) + 1e-15 < minimum_change:
            requested_change = 0.0
        change = float(np.clip(requested_change, -max_step, max_step))
        current = float(np.clip(current + change, -max_abs_position, max_abs_position))
        output[index] = current
    return pd.Series(output, index=desired.index, name="position")


def _funding_by_open_interval(
    opens: pd.Series,
    funding: pd.DataFrame,
) -> np.ndarray:
    open_ns = pd.to_datetime(opens, utc=True).astype("int64").to_numpy()
    funding_ns = pd.to_datetime(funding["ts"], utc=True).astype("int64").to_numpy()
    rates = funding["funding_rate"].to_numpy("float64")
    output = np.zeros(len(opens), dtype="float64")
    for index in range(1, len(opens)):
        left = int(np.searchsorted(funding_ns, open_ns[index - 1], side="right"))
        right = int(np.searchsorted(funding_ns, open_ns[index], side="right"))
        if right > left:
            output[index] = float(rates[left:right].sum())
    return output


def run_backtest(
    book: MarketBook,
    config: Config,
    *,
    features: pd.DataFrame | None = None,
) -> BacktestResult:
    features = build_forecasts(book, config) if features is None else features.copy()
    if len(features) != len(book.frame):
        raise ValueError("prebuilt feature rows must match the market book")
    desired_open = features["target_close"].shift(1)
    position = boundary_track(
        desired_open,
        buffer=config.no_trade_buffer,
        minimum_change=config.minimum_position_change,
        max_step=config.max_position_step,
        max_abs_position=config.max_abs_position,
    )
    valid = desired_open.notna()
    valid_indices = np.flatnonzero(valid.to_numpy())
    if not len(valid_indices):
        raise RuntimeError("no valid forecast")
    start = int(valid_indices[0])
    features = features.loc[start:].reset_index(drop=True)
    desired_open = desired_open.loc[start:].reset_index(drop=True)
    position = position.loc[start:].reset_index(drop=True)

    timestamps = pd.to_datetime(features["ts"], utc=True)
    open_price = features["open"].to_numpy("float64")
    funding_rate = _funding_by_open_interval(timestamps, book.funding)
    cost_rate = config.fee_per_turnover + config.slippage_per_turnover
    position_values = position.to_numpy("float64")
    prior_position = np.r_[0.0, position_values[:-1]]
    market_return = np.r_[0.0, open_price[1:] / open_price[:-1] - 1.0]
    turnover = np.abs(position_values - prior_position)
    market_factor = 1.0 + prior_position * market_return
    funding_factor = 1.0 - prior_position * funding_rate
    cost_factor = 1.0 - turnover * cost_rate
    if (
        (market_factor <= 0.0).any()
        or (funding_factor <= 0.0).any()
        or (cost_factor <= 0.0).any()
    ):
        raise RuntimeError("non-positive equity factor")
    equity_gross = np.cumprod(market_factor)
    equity_net = np.cumprod(market_factor * funding_factor * cost_factor)
    pre_cost_equity = equity_net / cost_factor
    cost_amount = pre_cost_equity * turnover * cost_rate
    pre_funding_equity = pre_cost_equity / funding_factor
    funding_amount = pre_funding_equity * prior_position * funding_rate
    path = pd.DataFrame(
        {
            "ts": timestamps,
            "open": open_price,
            "desired_position": desired_open.to_numpy("float64"),
            "position": position_values,
            "turnover": turnover,
            "market_return": market_return,
            "funding_rate_interval": funding_rate,
            "funding_amount": funding_amount,
            "cost_amount": cost_amount,
            "equity_gross": equity_gross,
            "equity_net": equity_net,
            "base_score": features["base_score"].to_numpy("float64"),
            "coherence": features["coherence"].to_numpy("float64"),
            "trend_score": features["trend_score"].to_numpy("float64"),
            "volatility_scalar": features["volatility_scalar"].to_numpy("float64"),
        }
    )
    return BacktestResult(
        config=config,
        path=path,
        metrics=slice_metrics(
            path,
            start=pd.Timestamp(path["ts"].iloc[0]),
            end=book.terminal_ts,
        ),
    )


def slice_metrics(
    path: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    sliced = path.loc[(path["ts"] >= start) & (path["ts"] < end)].copy()
    if len(sliced) < 2:
        return {
            "start_ts": pd.Timestamp(start).isoformat(),
            "end_ts_exclusive": pd.Timestamp(end).isoformat(),
            "bars": int(len(sliced)),
            "gross_return": math.nan,
            "net_return": math.nan,
            "max_drawdown": math.nan,
            "sharpe": math.nan,
            "turnover": 0.0,
            "annualized_turnover": 0.0,
            "rebalance_count": 0,
            "sign_flips": 0,
            "average_abs_position": 0.0,
            "cost_amount": 0.0,
            "funding_amount": 0.0,
        }
    gross = sliced["equity_gross"] / float(sliced["equity_gross"].iloc[0])
    net = sliced["equity_net"] / float(sliced["equity_net"].iloc[0])
    returns = net.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    drawdown = net / net.cummax() - 1.0
    standard_deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        float(returns.mean() / standard_deviation * math.sqrt(PERIODS_PER_YEAR))
        if standard_deviation > 0.0
        else 0.0
    )
    position = sliced["position"].to_numpy("float64")
    prior = np.r_[position[0], position[:-1]]
    days = max(
        (pd.Timestamp(sliced["ts"].iloc[-1]) - pd.Timestamp(sliced["ts"].iloc[0])).total_seconds()
        / 86400.0,
        0.25 / 24.0,
    )
    return {
        "start_ts": pd.Timestamp(sliced["ts"].iloc[0]).isoformat(),
        "end_ts_exclusive": pd.Timestamp(end).isoformat(),
        "bars": int(len(sliced)),
        "gross_return": float(gross.iloc[-1] - 1.0),
        "net_return": float(net.iloc[-1] - 1.0),
        "max_drawdown": float(drawdown.min()),
        "sharpe": sharpe,
        "turnover": float(sliced["turnover"].sum()),
        "annualized_turnover": float(sliced["turnover"].sum() * 365.25 / days),
        "rebalance_count": int((sliced["turnover"] > 1e-12).sum()),
        "sign_flips": int(((position * prior) < 0.0).sum()),
        "average_abs_position": float(np.abs(position).mean()),
        "max_abs_position": float(np.abs(position).max()),
        "time_in_market": float((np.abs(position) > 1e-12).mean()),
        "cost_amount": float(sliced["cost_amount"].sum()),
        "funding_amount": float(sliced["funding_amount"].sum()),
    }


def score_split(metrics: dict[str, Any]) -> float:
    net_return = float(metrics["net_return"])
    max_drawdown = abs(float(metrics["max_drawdown"]))
    return net_return / max(max_drawdown, 0.05)
