from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PARENT_SCRIPT = (
    ROOT
    / "research/hype/1d-pyramiding-trend/scripts/"
    "research_hype_1d_pyramiding_trend.py"
)
V7_REFERENCE_SCRIPT = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "diagnose_hype_1d_ma7_abt_v7_1_oapp_rebound_reset.py"
)

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
ALIAS = "HYPE-1D-MA7-MLT"
TRAIN_DAYS = 365
FEE = 0.001
SLIPPAGE = 0.0004
COST_PER_FILL = FEE + SLIPPAGE
HORIZONS = (3, 7, 14)
EDGE_THRESHOLDS = (0.0, 0.0028, 0.005, 0.01)
RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0)
LGBM_CONFIGS: dict[str, dict[str, Any]] = {
    "LGBM_A": {
        "num_leaves": 7,
        "max_depth": 3,
        "min_child_samples": 30,
        "learning_rate": 0.03,
        "n_estimators": 120,
    },
    "LGBM_B": {
        "num_leaves": 15,
        "max_depth": 4,
        "min_child_samples": 20,
        "learning_rate": 0.03,
        "n_estimators": 160,
    },
}
RULE_MA_WINDOWS = (5, 7, 10, 14, 20, 30)
RULE_SLOPE_LOOKBACKS = (1, 3, 5, 7)
RULE_MIN_SLOPES = (0.0, 0.02, 0.05, 0.10, 0.20)
RULE_GAPS = (0.0, 0.10, 0.25, 0.50)
RULE_DIRECTIONS = ("both", "long_only", "short_only")
RUN_DATE = "2026-08-27"


@dataclass(slots=True)
class MarketData:
    daily: pd.DataFrame
    open_ts: pd.DatetimeIndex
    opens: np.ndarray
    funding_by_open: np.ndarray
    quality: dict[str, Any]
    funding_quality: dict[str, Any]


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {FAMILY} P0.")
    parser.add_argument("--run-date", default=RUN_DATE)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_market() -> MarketData:
    parent = _load_module(PARENT_SCRIPT, "hype_1d_ma7_mlt_parent")
    engine = parent.load_engine()
    hourly, hourly_quality = engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = engine.load_and_audit_funding(ROOT)
    daily, daily_quality = parent.aggregate_complete_daily(hourly)
    daily["ts"] = pd.to_datetime(daily["ts"], utc=True)
    terminal_ts = pd.Timestamp(daily["ts"].iloc[-1]) + pd.Timedelta(days=1)
    terminal = hourly.loc[pd.to_datetime(hourly["ts"], utc=True).eq(terminal_ts)]
    if len(terminal) != 1:
        raise RuntimeError(f"expected one terminal open at {terminal_ts}, got {len(terminal)}")
    if len(daily) != 446:
        raise RuntimeError(f"frozen P0 expected 446 daily rows, got {len(daily)}")
    expected = {
        "first": pd.Timestamp("2025-05-31", tz="UTC"),
        "train_last": pd.Timestamp("2026-05-30", tz="UTC"),
        "validation_first": pd.Timestamp("2026-05-31", tz="UTC"),
        "last": pd.Timestamp("2026-08-19", tz="UTC"),
        "terminal": pd.Timestamp("2026-08-20", tz="UTC"),
    }
    observed = {
        "first": pd.Timestamp(daily["ts"].iloc[0]),
        "train_last": pd.Timestamp(daily["ts"].iloc[TRAIN_DAYS - 1]),
        "validation_first": pd.Timestamp(daily["ts"].iloc[TRAIN_DAYS]),
        "last": pd.Timestamp(daily["ts"].iloc[-1]),
        "terminal": terminal_ts,
    }
    if observed != expected:
        raise RuntimeError(f"frozen boundary mismatch: {observed}")
    open_ts = pd.DatetimeIndex([*daily["ts"], terminal_ts])
    opens = np.r_[daily["open"].to_numpy("float64"), float(terminal["open"].iloc[0])]
    funding_by_open = parent._funding_by_open(open_ts, funding)
    return MarketData(
        daily=daily,
        open_ts=open_ts,
        opens=opens,
        funding_by_open=funding_by_open,
        quality={"hourly": hourly_quality, "daily": daily_quality},
        funding_quality=funding_quality,
    )


def wilder_atr(frame: pd.DataFrame, window: int) -> pd.Series:
    prior_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prior_close).abs(),
            (frame["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def wilder_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean()
    loss = (-delta.clip(upper=0.0)).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean()
    rs = gain / loss.replace(0.0, np.nan)
    output = 100.0 - 100.0 / (1.0 + rs)
    return output.where(loss.ne(0.0), 100.0)


def efficiency_ratio(close: pd.Series, window: int) -> pd.Series:
    displacement = close.diff(window).abs()
    path = close.diff().abs().rolling(window, min_periods=window).sum()
    return displacement / path.replace(0.0, np.nan)


def build_features(market: MarketData) -> pd.DataFrame:
    frame = market.daily.copy()
    close = frame["close"].astype(float)
    log_close = np.log(close)
    log_return = log_close.diff()
    atr7 = wilder_atr(frame, 7)
    atr14 = wilder_atr(frame, 14)
    features: dict[str, pd.Series] = {}
    for window in (1, 2, 3, 5, 7, 14, 21):
        features[f"log_return_{window}d"] = log_close.diff(window)
    for window in (3, 5, 7, 10, 14, 21, 30):
        ma = close.rolling(window, min_periods=window).mean()
        features[f"sma{window}_gap_atr7"] = (close - ma) / atr7
    ma7 = close.rolling(7, min_periods=7).mean()
    for lookback in (1, 3, 5):
        features[f"sma7_slope_{lookback}d_atr7"] = ma7.diff(lookback) / atr7
    features["rsi6"] = wilder_rsi(close, 6)
    features["rsi14"] = wilder_rsi(close, 14)
    features["atr7_pct"] = atr7 / close
    features["atr14_pct"] = atr14 / close
    for window in (3, 7, 14, 30):
        features[f"realized_vol_{window}d"] = log_return.rolling(
            window, min_periods=window
        ).std(ddof=0)
    features["er7"] = efficiency_ratio(close, 7)
    features["er14"] = efficiency_ratio(close, 14)
    body_high = frame[["open", "close"]].max(axis=1)
    body_low = frame[["open", "close"]].min(axis=1)
    features["body_atr7"] = (frame["close"] - frame["open"]) / atr7
    features["range_atr7"] = (frame["high"] - frame["low"]) / atr7
    features["upper_wick_atr7"] = (frame["high"] - body_high) / atr7
    features["lower_wick_atr7"] = (body_low - frame["low"]) / atr7
    features["close_location"] = (frame["close"] - frame["low"]) / (
        frame["high"] - frame["low"]
    ).replace(0.0, np.nan)
    log_volume = np.log1p(frame["volume"].astype(float))
    features["volume_log_change_1d"] = log_volume.diff()
    for window in (7, 30):
        mean = log_volume.rolling(window, min_periods=window).mean()
        std = log_volume.rolling(window, min_periods=window).std(ddof=0)
        features[f"volume_z_{window}d"] = (log_volume - mean) / std.replace(0.0, np.nan)
    features["funding_prev_utc_day"] = pd.Series(
        market.funding_by_open[1 : len(frame) + 1], index=frame.index
    )
    output = pd.DataFrame(features, index=frame.index)
    output.insert(0, "ts", pd.to_datetime(frame["ts"], utc=True))
    return output


def single_trade_return(
    market: MarketData,
    decision_index: int,
    horizon: int,
    side: int,
) -> float:
    entry = decision_index + 1
    exit_index = entry + horizon
    if exit_index >= len(market.opens):
        return math.nan
    equity = 1.0 - COST_PER_FILL
    for open_index in range(entry + 1, exit_index + 1):
        price_return = market.opens[open_index] / market.opens[open_index - 1] - 1.0
        equity *= 1.0 + side * price_return
        equity -= equity * side * market.funding_by_open[open_index]
    equity *= 1.0 - COST_PER_FILL
    return float(equity - 1.0)


def build_labels(market: MarketData) -> dict[int, pd.DataFrame]:
    labels: dict[int, pd.DataFrame] = {}
    for horizon in HORIZONS:
        rows = []
        for decision_index in range(len(market.daily)):
            rows.append(
                {
                    "long": single_trade_return(market, decision_index, horizon, 1),
                    "short": single_trade_return(market, decision_index, horizon, -1),
                }
            )
        labels[horizon] = pd.DataFrame(rows)
    return labels


def model_factories() -> dict[str, Callable[[], Any]]:
    factories: dict[str, Callable[[], Any]] = {}
    for alpha in RIDGE_ALPHAS:
        name = f"RIDGE_A{alpha:g}"
        factories[name] = lambda alpha=alpha: Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=alpha)),
            ]
        )
    for name, config in LGBM_CONFIGS.items():
        factories[name] = lambda config=config: Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                (
                    "model",
                    lgb.LGBMRegressor(
                        objective="regression_l2",
                        verbosity=-1,
                        random_state=20260827,
                        n_jobs=1,
                        deterministic=True,
                        force_col_wise=True,
                        reg_alpha=0.1,
                        reg_lambda=1.0,
                        **config,
                    ),
                ),
            ]
        )
    return factories


def make_signals(
    decisions: list[int],
    long_prediction: np.ndarray,
    short_prediction: np.ndarray,
    edge: float,
) -> dict[int, int]:
    signals: dict[int, int] = {}
    for index, long_edge, short_edge in zip(
        decisions, long_prediction, short_prediction, strict=True
    ):
        best = max(float(long_edge), float(short_edge))
        if not np.isfinite(best) or best <= edge:
            signals[index] = 0
        else:
            signals[index] = 1 if long_edge > short_edge else -1
    return signals


def _profit_factor(trades: list[dict[str, Any]]) -> float:
    wins = sum(max(0.0, float(trade["net_return"])) for trade in trades)
    losses = -sum(min(0.0, float(trade["net_return"])) for trade in trades)
    if losses <= 0.0:
        return 999.0 if wins > 0.0 else 0.0
    return float(wins / losses)


def backtest_signals(
    market: MarketData,
    signals: dict[int, int],
    *,
    horizon: int,
    start_open_index: int,
    terminal_open_index: int,
    force_terminal_exit: bool,
) -> BacktestResult:
    if not (0 <= start_open_index < terminal_open_index < len(market.opens)):
        raise ValueError("invalid backtest bounds")
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    side = 0
    due_exit = -1
    entry_index = -1
    entry_equity = math.nan
    entry_price = math.nan
    total_cost = 0.0
    total_funding = 0.0
    exposure_days = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    previous_open = float(market.opens[start_open_index])

    for open_index in range(start_open_index, terminal_open_index + 1):
        current_open = float(market.opens[open_index])
        ts = pd.Timestamp(market.open_ts[open_index])
        if open_index > start_open_index and side != 0:
            price_return = current_open / previous_open - 1.0
            equity *= 1.0 + side * price_return
            funding_amount = equity * side * market.funding_by_open[open_index]
            equity -= funding_amount
            total_funding += funding_amount
            exposure_days += 1

        exit_reason: str | None = None
        if side != 0 and open_index >= due_exit:
            exit_reason = "fixed_horizon"
        if side != 0 and open_index == terminal_open_index and force_terminal_exit:
            exit_reason = "terminal_mark" if open_index < due_exit else "fixed_horizon"
        if exit_reason is not None:
            exit_cost = equity * COST_PER_FILL
            equity -= exit_cost
            total_cost += exit_cost
            trades.append(
                {
                    "entry_ts": pd.Timestamp(market.open_ts[entry_index]).isoformat(),
                    "exit_ts": ts.isoformat(),
                    "side": "long" if side > 0 else "short",
                    "side_value": side,
                    "entry_price": entry_price,
                    "exit_price": current_open,
                    "scheduled_horizon": horizon,
                    "bars_held": open_index - entry_index,
                    "exit_reason": exit_reason,
                    "net_return": equity / entry_equity - 1.0,
                }
            )
            side = 0
            due_exit = -1
            entry_index = -1
            entry_equity = math.nan
            entry_price = math.nan

        decision_index = open_index - 1
        signal = int(signals.get(decision_index, 0))
        if side == 0 and signal != 0 and open_index < terminal_open_index:
            entry_equity = equity
            entry_cost = equity * COST_PER_FILL
            equity -= entry_cost
            total_cost += entry_cost
            side = signal
            entry_index = open_index
            entry_price = current_open
            due_exit = open_index + horizon

        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1.0)
        path.append(
            {
                "ts": ts.isoformat(),
                "open": current_open,
                "equity": equity,
                "position": side,
            }
        )
        previous_open = current_open

    returns = np.asarray([trade["net_return"] for trade in trades], dtype=float)
    metrics = {
        "total_return": float(equity - 1.0),
        "max_drawdown": float(mdd),
        "profit_factor": _profit_factor(trades),
        "win_rate": float(np.mean(returns > 0.0)) if len(returns) else 0.0,
        "trade_count": int(len(trades)),
        "long_count": int(sum(trade["side_value"] > 0 for trade in trades)),
        "short_count": int(sum(trade["side_value"] < 0 for trade in trades)),
        "exposure_days": exposure_days,
        "total_cost": float(total_cost),
        "total_funding": float(total_funding),
        "final_equity": float(equity),
    }
    return BacktestResult(metrics=metrics, trades=trades, path=path)


def aggregate_folds(results: list[BacktestResult]) -> dict[str, Any]:
    fold_returns = [result.metrics["total_return"] for result in results]
    trades = [trade for result in results for trade in result.trades]
    compounded = float(np.prod([1.0 + value for value in fold_returns]) - 1.0)
    return {
        "positive_fold_count": int(sum(value > 0.0 for value in fold_returns)),
        "median_fold_return": float(np.median(fold_returns)),
        "fold_returns": fold_returns,
        "total_return": compounded,
        "max_drawdown": float(min(result.metrics["max_drawdown"] for result in results)),
        "profit_factor": _profit_factor(trades),
        "trade_count": len(trades),
        "long_count": sum(trade["side_value"] > 0 for trade in trades),
        "short_count": sum(trade["side_value"] < 0 for trade in trades),
    }


def selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(row["positive_fold_count"]),
        -float(row["median_fold_return"]),
        -float(row["total_return"]),
        -float(row["profit_factor"]),
        abs(float(row["max_drawdown"])),
        str(row["candidate_id"]),
    )


def folds_for_horizon(horizon: int) -> list[tuple[int, int]]:
    return [(150, 199), (200, 249), (250, 299), (300, 363 - horizon)]


def train_ml_candidates(
    market: MarketData,
    features: pd.DataFrame,
    labels: dict[int, pd.DataFrame],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    feature_columns = [column for column in features.columns if column != "ts"]
    factories = model_factories()
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        folds = folds_for_horizon(horizon)
        predictions: dict[str, list[tuple[tuple[int, int], dict[int, int]]]] = {
            f"{model_name}|H{horizon}|E{edge:.4f}": []
            for model_name in factories
            for edge in EDGE_THRESHOLDS
        }
        for fold_number, (eval_start, eval_end) in enumerate(folds, start=1):
            train_max = eval_start - horizon - 1
            train_indices = [
                index
                for index in range(30, train_max + 1)
                if np.isfinite(labels[horizon].loc[index, "long"])
                and np.isfinite(labels[horizon].loc[index, "short"])
            ]
            eval_indices = list(range(eval_start, eval_end + 1))
            x_train = features.loc[train_indices, feature_columns]
            x_eval = features.loc[eval_indices, feature_columns]
            for model_name, factory in factories.items():
                long_model = factory()
                short_model = factory()
                long_model.fit(x_train, labels[horizon].loc[train_indices, "long"])
                short_model.fit(x_train, labels[horizon].loc[train_indices, "short"])
                long_prediction = long_model.predict(x_eval)
                short_prediction = short_model.predict(x_eval)
                for edge in EDGE_THRESHOLDS:
                    key = f"{model_name}|H{horizon}|E{edge:.4f}"
                    predictions[key].append(
                        (
                            (eval_start, eval_end),
                            make_signals(
                                eval_indices, long_prediction, short_prediction, edge
                            ),
                        )
                    )
        for candidate_id, fold_signals in predictions.items():
            model_name = candidate_id.split("|")[0]
            edge = float(candidate_id.rsplit("E", 1)[1])
            fold_results = []
            for (eval_start, eval_end), signals in fold_signals:
                fold_results.append(
                    backtest_signals(
                        market,
                        signals,
                        horizon=horizon,
                        start_open_index=eval_start + 1,
                        terminal_open_index=eval_end + 1 + horizon,
                        force_terminal_exit=False,
                    )
                )
            row = {
                "candidate_id": candidate_id,
                "model": model_name,
                "horizon": horizon,
                "edge": edge,
                **aggregate_folds(fold_results),
            }
            rows.append(row)
    eligible = [row for row in rows if row["trade_count"] >= 8]
    if not eligible:
        raise RuntimeError("no ML candidate reached the frozen 8-trade minimum")
    champion = sorted(eligible, key=selection_key)[0]
    return rows, champion


def rule_signal_series(
    market: MarketData,
    *,
    ma_window: int,
    slope_lookback: int,
    min_slope: float,
    gap: float,
    direction: str,
) -> dict[int, int]:
    close = market.daily["close"].astype(float)
    ma = close.rolling(ma_window, min_periods=ma_window).mean()
    atr = wilder_atr(market.daily, 7)
    signed_slope = ma.diff(slope_lookback) / atr
    signed_gap = (close - ma) / atr
    output: dict[int, int] = {}
    for index in range(len(close)):
        if not np.isfinite(signed_slope.iloc[index]) or not np.isfinite(signed_gap.iloc[index]):
            output[index] = 0
            continue
        long_signal = signed_gap.iloc[index] > gap and signed_slope.iloc[index] > min_slope
        short_signal = signed_gap.iloc[index] < -gap and signed_slope.iloc[index] < -min_slope
        if direction == "long_only":
            short_signal = False
        elif direction == "short_only":
            long_signal = False
        output[index] = 1 if long_signal else (-1 if short_signal else 0)
    return output


def train_rule_candidates(market: MarketData) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ma_window in RULE_MA_WINDOWS:
        for slope_lookback in RULE_SLOPE_LOOKBACKS:
            for min_slope in RULE_MIN_SLOPES:
                for gap in RULE_GAPS:
                    for direction in RULE_DIRECTIONS:
                        all_signals = rule_signal_series(
                            market,
                            ma_window=ma_window,
                            slope_lookback=slope_lookback,
                            min_slope=min_slope,
                            gap=gap,
                            direction=direction,
                        )
                        for horizon in HORIZONS:
                            candidate_id = (
                                f"MA{ma_window}|SL{slope_lookback}|MIN{min_slope:.2f}|"
                                f"GAP{gap:.2f}|H{horizon}|{direction}"
                            )
                            fold_results = []
                            for eval_start, eval_end in folds_for_horizon(horizon):
                                signals = {
                                    index: all_signals[index]
                                    for index in range(eval_start, eval_end + 1)
                                }
                                fold_results.append(
                                    backtest_signals(
                                        market,
                                        signals,
                                        horizon=horizon,
                                        start_open_index=eval_start + 1,
                                        terminal_open_index=eval_end + 1 + horizon,
                                        force_terminal_exit=False,
                                    )
                                )
                            rows.append(
                                {
                                    "candidate_id": candidate_id,
                                    "ma_window": ma_window,
                                    "slope_lookback": slope_lookback,
                                    "min_slope": min_slope,
                                    "gap": gap,
                                    "horizon": horizon,
                                    "direction": direction,
                                    **aggregate_folds(fold_results),
                                }
                            )
    eligible = [row for row in rows if row["trade_count"] >= 8]
    if not eligible:
        raise RuntimeError("no rule candidate reached the frozen 8-trade minimum")
    champion = sorted(eligible, key=selection_key)[0]
    return rows, champion


def fit_final_ml(
    features: pd.DataFrame,
    labels: dict[int, pd.DataFrame],
    champion: dict[str, Any],
) -> tuple[Any, Any, list[str], list[int]]:
    horizon = int(champion["horizon"])
    feature_columns = [column for column in features.columns if column != "ts"]
    last_train_decision = TRAIN_DAYS - 2 - horizon
    train_indices = [
        index
        for index in range(30, last_train_decision + 1)
        if np.isfinite(labels[horizon].loc[index, "long"])
        and np.isfinite(labels[horizon].loc[index, "short"])
    ]
    factory = model_factories()[str(champion["model"])]
    long_model = factory()
    short_model = factory()
    long_model.fit(features.loc[train_indices, feature_columns], labels[horizon].loc[train_indices, "long"])
    short_model.fit(features.loc[train_indices, feature_columns], labels[horizon].loc[train_indices, "short"])
    return long_model, short_model, feature_columns, train_indices


def validation_signals_ml(
    features: pd.DataFrame,
    champion: dict[str, Any],
    long_model: Any,
    short_model: Any,
    feature_columns: list[str],
) -> tuple[dict[int, int], pd.DataFrame]:
    decisions = list(range(TRAIN_DAYS - 1, len(features) - 1))
    x = features.loc[decisions, feature_columns]
    long_prediction = long_model.predict(x)
    short_prediction = short_model.predict(x)
    signals = make_signals(
        decisions,
        long_prediction,
        short_prediction,
        float(champion["edge"]),
    )
    predictions = pd.DataFrame(
        {
            "decision_index": decisions,
            "decision_ts": features.loc[decisions, "ts"].astype(str).to_list(),
            "predicted_long_net_return": long_prediction,
            "predicted_short_net_return": short_prediction,
            "signal": [signals[index] for index in decisions],
        }
    )
    return signals, predictions


def validation_signals_rule(
    market: MarketData, champion: dict[str, Any]
) -> dict[int, int]:
    all_signals = rule_signal_series(
        market,
        ma_window=int(champion["ma_window"]),
        slope_lookback=int(champion["slope_lookback"]),
        min_slope=float(champion["min_slope"]),
        gap=float(champion["gap"]),
        direction=str(champion["direction"]),
    )
    return {
        index: all_signals[index]
        for index in range(TRAIN_DAYS - 1, len(market.daily) - 1)
    }


def buy_and_hold(market: MarketData) -> BacktestResult:
    signals = {TRAIN_DAYS - 1: 1}
    horizon = len(market.daily) - TRAIN_DAYS + 1
    return backtest_signals(
        market,
        signals,
        horizon=horizon,
        start_open_index=TRAIN_DAYS,
        terminal_open_index=len(market.daily),
        force_terminal_exit=True,
    )


def exact_v7_reference() -> dict[str, Any]:
    script_dir = V7_REFERENCE_SCRIPT.parent
    reference = _load_module(V7_REFERENCE_SCRIPT, "hype_1d_ma7_mlt_v7_reference")
    v6 = _load_module(
        script_dir / "audit_hype_1d_ma7_abt_v6_full_parameter_ablation.py",
        "hype_1d_ma7_mlt_v7_v6_helper",
    )
    engine = _load_module(
        script_dir / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py",
        "hype_1d_ma7_mlt_v7_engine",
    )
    adapter = _load_module(
        script_dir / "hype_1d_ma7_v4_fair_adapter.py",
        "hype_1d_ma7_mlt_v7_adapter",
    )
    _, context = reference.extended_context(adapter)
    metrics, result, _ = reference.run_arm(
        v6,
        engine,
        context,
        "CONTROL",
        window=(TRAIN_DAYS - 1, len(context.book.ts)),
        retain=True,
    )
    return {
        "role": "descriptive_post_reveal_reference_not_clean_oos",
        "metrics": metrics,
        "trades": [reference.compact_trade(trade) for trade in result.raw.trades],
        "source": str(V7_REFERENCE_SCRIPT.relative_to(ROOT)),
    }


def path_slices(path: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    frame = pd.DataFrame(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    windows = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}
    output: dict[str, dict[str, float]] = {}
    for name, days in windows.items():
        sub = frame.tail(min(days + 1, len(frame)))
        start_equity = float(sub["equity"].iloc[0])
        end_equity = float(sub["equity"].iloc[-1])
        peak = sub["equity"].cummax()
        output[name] = {
            "available_days": int(len(sub) - 1),
            "return": end_equity / start_equity - 1.0,
            "max_drawdown": float((sub["equity"] / peak - 1.0).min()),
        }
    return output


def render_trade_path_html(
    market: MarketData,
    ml_result: BacktestResult,
    rule_result: BacktestResult,
    output_path: Path,
) -> None:
    validation = market.daily.iloc[TRAIN_DAYS:].copy()
    payload = {
        "candles": {
            key: validation[key].astype(float).tolist()
            for key in ("open", "high", "low", "close")
        },
        "ts": validation["ts"].astype(str).tolist(),
        "ml": {"metrics": ml_result.metrics, "trades": ml_result.trades, "path": ml_result.path},
        "rule": {"metrics": rule_result.metrics, "trades": rule_result.trades, "path": rule_result.path},
    }
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HYPE-1D-MA7-MLT P0</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>:root{color-scheme:dark}body{margin:0;background:#0d131a;color:#e8edf2;font:14px/1.5 Inter,-apple-system,sans-serif}header{padding:16px 22px;border-bottom:1px solid #27313d}h1{font-size:19px;margin:0}p{color:#aab7c4;margin:5px 0 0}#chart{width:100%;height:calc(100vh - 90px);min-height:850px}</style></head><body><header><h1>HYPE-1D-MA7-MLT P0 · locked validation trade paths</h1><p>UTC｜完整验证 K 线、ML 与 train-only 规则净值；每笔 entry/exit 均连线。支持拖动、滚轮缩放、框选与双击复位。</p></header><div id="chart"></div><script>const p=__PAYLOAD__;const traces=[{type:'candlestick',x:p.ts,open:p.candles.open,high:p.candles.high,low:p.candles.low,close:p.candles.close,xaxis:'x',yaxis:'y',name:'HYPEUSDT',showlegend:false},{type:'scatter',mode:'lines',x:p.ml.path.map(q=>q.ts),y:p.ml.path.map(q=>q.equity),xaxis:'x2',yaxis:'y2',name:'ML equity',line:{color:'#69b3ff',width:2.4}},{type:'scatter',mode:'lines',x:p.rule.path.map(q=>q.ts),y:p.rule.path.map(q=>q.equity),xaxis:'x2',yaxis:'y2',name:'Rule-search equity',line:{color:'#f6c85f',width:2}}];for(const [kind,data,dash] of [['ML',p.ml,'solid'],['RULE',p.rule,'dot']]){for(const [i,q] of data.trades.entries()){traces.push({type:'scatter',mode:'lines+markers',x:[q.entry_ts,q.exit_ts],y:[q.entry_price,q.exit_price],xaxis:'x',yaxis:'y',showlegend:false,line:{color:q.side_value>0?'#19a974':'#e45756',width:kind==='ML'?2.5:1.7,dash},marker:{size:7},text:[`${kind} #${i+1} ${q.side.toUpperCase()} entry`,`${kind} #${i+1} ${q.exit_reason} · net ${(q.net_return*100).toFixed(2)}%`],hovertemplate:'%{x}<br>%{y:.4f}<br>%{text}<extra></extra>'});}}const axis={type:'date',gridcolor:'#202a35',rangeslider:{visible:false}};Plotly.newPlot('chart',traces,{dragmode:'pan',paper_bgcolor:'#0d131a',plot_bgcolor:'#0d131a',font:{color:'#dce5ed'},margin:{l:65,r:25,t:25,b:50},hovermode:'closest',xaxis:{...axis,domain:[0,1],anchor:'y'},yaxis:{type:'log',gridcolor:'#202a35',domain:[.38,1],title:'HYPEUSDT'},xaxis2:{...axis,domain:[0,1],anchor:'y2'},yaxis2:{gridcolor:'#202a35',domain:[0,.31],title:'equity multiple'}},{responsive:true,displaylogo:false,scrollZoom:true});</script></body></html>"""
    output_path.write_text(
        html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":"), allow_nan=False)),
        encoding="utf-8",
    )


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def write_outputs(
    *,
    run_date: str,
    market: MarketData,
    features: pd.DataFrame,
    ml_rows: list[dict[str, Any]],
    ml_champion: dict[str, Any],
    rule_rows: list[dict[str, Any]],
    rule_champion: dict[str, Any],
    predictions: pd.DataFrame,
    ml_result: BacktestResult,
    rule_result: BacktestResult,
    hold_result: BacktestResult,
    v7_reference: dict[str, Any],
    train_indices: list[int],
) -> dict[str, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_ma7_mlt_p0_365d_train_validation_{run_date}"
    paths = {
        "summary": ARTIFACT_DIR / f"{stem}_summary.json",
        "ml_candidates": ARTIFACT_DIR / f"{stem}_ml_candidates.csv",
        "rule_candidates": ARTIFACT_DIR / f"{stem}_rule_candidates.csv",
        "predictions": ARTIFACT_DIR / f"{stem}_validation_predictions.csv",
        "trades": ARTIFACT_DIR / f"{stem}_validation_trades.csv",
        "path": ARTIFACT_DIR / f"{stem}_validation_path.csv",
        "html": ARTIFACT_DIR / f"{stem}_trade_paths.html",
        "features": ARTIFACT_DIR / f"{stem}_feature_manifest.json",
        "v7_reference": ARTIFACT_DIR / f"{stem}_v7_1_descriptive_reference.json",
    }
    pd.DataFrame(ml_rows).to_csv(paths["ml_candidates"], index=False)
    pd.DataFrame(rule_rows).to_csv(paths["rule_candidates"], index=False)
    predictions.to_csv(paths["predictions"], index=False)
    trade_frames = []
    path_frames = []
    for strategy, result in (("ML", ml_result), ("RULE_SEARCH", rule_result), ("BUY_HOLD", hold_result)):
        trades = pd.DataFrame(result.trades)
        if not trades.empty:
            trades.insert(0, "strategy", strategy)
            trade_frames.append(trades)
        path = pd.DataFrame(result.path)
        path.insert(0, "strategy", strategy)
        path_frames.append(path)
    pd.concat(trade_frames, ignore_index=True).to_csv(paths["trades"], index=False)
    pd.concat(path_frames, ignore_index=True).to_csv(paths["path"], index=False)
    render_trade_path_html(market, ml_result, rule_result, paths["html"])
    feature_manifest = {
        "family": FAMILY,
        "feature_columns": [column for column in features.columns if column != "ts"],
        "feature_count": len(features.columns) - 1,
        "final_training_decision_indices": [min(train_indices), max(train_indices)],
        "final_training_rows": len(train_indices),
        "validation_features_start": features.loc[TRAIN_DAYS - 1, "ts"],
        "validation_features_end": features.loc[len(features) - 2, "ts"],
    }
    paths["features"].write_text(
        json.dumps(json_ready(feature_manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["v7_reference"].write_text(
        json.dumps(json_ready(v7_reference), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ml_metrics = {**ml_result.metrics, "recent_slices": path_slices(ml_result.path)}
    rule_metrics = {**rule_result.metrics, "recent_slices": path_slices(rule_result.path)}
    hold_metrics = {**hold_result.metrics, "recent_slices": path_slices(hold_result.path)}
    if ml_metrics["total_return"] <= 0.0 or ml_metrics["profit_factor"] < 1.0 or ml_metrics["trade_count"] < 3:
        verdict = "ML_NO_EDGE"
    elif (
        ml_metrics["total_return"] > rule_metrics["total_return"]
        and ml_metrics["max_drawdown"] >= rule_metrics["max_drawdown"] - 0.05
    ):
        verdict = "ML_BEATS_RULE_OOS"
    else:
        verdict = "MIXED"
    summary = {
        "family": FAMILY,
        "alias": ALIAS,
        "run_date": run_date,
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "verdict": verdict,
        "data": {
            "daily_rows": len(market.daily),
            "first_ts": market.daily["ts"].iloc[0],
            "train_rows": TRAIN_DAYS,
            "train_last_ts": market.daily["ts"].iloc[TRAIN_DAYS - 1],
            "validation_rows": len(market.daily) - TRAIN_DAYS,
            "validation_first_ts": market.daily["ts"].iloc[TRAIN_DAYS],
            "validation_last_ts": market.daily["ts"].iloc[-1],
            "terminal_open_ts": market.open_ts[-1],
            "quality": market.quality,
            "funding_quality": market.funding_quality,
        },
        "cost": {"fee_per_fill": FEE, "slippage_per_fill": SLIPPAGE, "round_trip": 2 * COST_PER_FILL},
        "ml_champion_train_oof": ml_champion,
        "rule_champion_train_oof": rule_champion,
        "validation": {
            "ml": ml_metrics,
            "rule_search": rule_metrics,
            "buy_hold": hold_metrics,
            "v7_1_descriptive_reference": v7_reference,
        },
        "artifacts": {key: str(path.relative_to(ROOT)) for key, path in paths.items()},
        "limitations": [
            "single 81-day locked validation",
            "fixed-horizon diagnostic has no intraday stop",
            "HYPE-only sample is small",
            "exact V7.1 is not a clean OOS comparator because its rules saw this history",
        ],
    }
    paths["summary"].write_text(
        json.dumps(json_ready(summary), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for path in paths.values():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(path.suffix + ".sha256").write_text(
            f"{digest}  {path.name}\n", encoding="utf-8"
        )
    return paths


def self_test() -> None:
    dummy_daily = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=40, freq="1D", tz="UTC"),
            "open": np.linspace(10.0, 20.0, 40),
            "high": np.linspace(10.5, 20.5, 40),
            "low": np.linspace(9.5, 19.5, 40),
            "close": np.linspace(10.2, 20.2, 40),
            "volume": np.linspace(100.0, 200.0, 40),
        }
    )
    market = MarketData(
        daily=dummy_daily,
        open_ts=pd.date_range("2025-01-01", periods=41, freq="1D", tz="UTC"),
        opens=np.linspace(10.0, 20.0, 41),
        funding_by_open=np.zeros(41),
        quality={},
        funding_quality={},
    )
    features = build_features(market)
    assert len(features) == 40
    assert "sma7_gap_atr7" in features.columns
    result = backtest_signals(
        market,
        {10: 1, 20: -1},
        horizon=3,
        start_open_index=11,
        terminal_open_index=30,
        force_terminal_exit=True,
    )
    assert result.metrics["trade_count"] == 2
    assert all(trade["exit_ts"] > trade["entry_ts"] for trade in result.trades)
    assert folds_for_horizon(14)[-1] == (300, 349)


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("self-test PASS")
        return
    market = load_market()
    features = build_features(market)
    labels = build_labels(market)
    ml_rows, ml_champion = train_ml_candidates(market, features, labels)
    rule_rows, rule_champion = train_rule_candidates(market)
    long_model, short_model, feature_columns, train_indices = fit_final_ml(
        features, labels, ml_champion
    )
    ml_signals, predictions = validation_signals_ml(
        features, ml_champion, long_model, short_model, feature_columns
    )
    rule_signals = validation_signals_rule(market, rule_champion)
    terminal_open_index = len(market.daily)
    ml_result = backtest_signals(
        market,
        ml_signals,
        horizon=int(ml_champion["horizon"]),
        start_open_index=TRAIN_DAYS,
        terminal_open_index=terminal_open_index,
        force_terminal_exit=True,
    )
    rule_result = backtest_signals(
        market,
        rule_signals,
        horizon=int(rule_champion["horizon"]),
        start_open_index=TRAIN_DAYS,
        terminal_open_index=terminal_open_index,
        force_terminal_exit=True,
    )
    hold_result = buy_and_hold(market)
    v7_reference = exact_v7_reference()
    paths = write_outputs(
        run_date=args.run_date,
        market=market,
        features=features,
        ml_rows=ml_rows,
        ml_champion=ml_champion,
        rule_rows=rule_rows,
        rule_champion=rule_champion,
        predictions=predictions,
        ml_result=ml_result,
        rule_result=rule_result,
        hold_result=hold_result,
        v7_reference=v7_reference,
        train_indices=train_indices,
    )
    print(
        json.dumps(
            {
                "ml_champion": ml_champion,
                "rule_champion": rule_champion,
                "validation": {
                    "ml": ml_result.metrics,
                    "rule": rule_result.metrics,
                    "buy_hold": hold_result.metrics,
                    "v7_1_descriptive_reference": v7_reference["metrics"],
                },
                "summary": str(paths["summary"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
