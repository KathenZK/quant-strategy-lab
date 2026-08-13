from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse, MarketType
from strategy_lab.data.fs import atomic_write_path
from strategy_lab.data.settings import load_settings


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1d-ma7-rsi6-lightgbm-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p1_development_2026-08-07"
HOURLY_PATH = ROOT / "data/features/btcusdt_1h_stop_path_v1/btcusdt_perp_1h.parquet"
FUNDING_PATH = (
    ROOT / "data/features/btcusdt_funding_mark_v1/btcusdt_perp_funding_mark.parquet"
)

DISPLAY_SYMBOL = "BTC/USDT:USDT"
DEVELOPMENT_END_EXCLUSIVE = pd.Timestamp("2025-08-07T00:00:00Z")
VALIDATION_END_INCLUSIVE = pd.Timestamp("2026-08-06T00:00:00Z")
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0004
STOP_ATR = 3.0
SEED = 20260807
THRESHOLDS = (0.50, 0.55, 0.60, 0.65)

MA_FEATURES = (
    "side",
    "prev_close_ma_gap_atr",
    "close_ma_gap_atr",
    "cross_span_atr",
    "ma7_slope_1_atr",
    "ma7_slope_3_atr",
    "prior_side_duration",
)
K_FEATURES = (
    "body_atr",
    "range_atr",
    "upper_wick_atr",
    "lower_wick_atr",
    "close_location",
    "return_3_atr",
    "return_5_atr",
)
RSI_FEATURES = (
    "rsi6",
    "rsi6_delta_1",
    "rsi6_min_5",
    "rsi6_max_5",
    "rsi6_low20_last5",
    "rsi6_high80_last5",
)
VOL_FEATURES = (
    "quote_volume_ratio_7",
    "trade_count_ratio_7",
)
CORE_FEATURES = (*MA_FEATURES, *K_FEATURES, *RSI_FEATURES)

LGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "n_estimators": 120,
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 3,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": SEED,
    "n_jobs": 1,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}


@dataclass(frozen=True, slots=True)
class ModelVariant:
    variant_id: str
    model_type: str
    features: tuple[str, ...]


MODEL_VARIANTS = (
    ModelVariant("logistic_core", "logistic", CORE_FEATURES),
    ModelVariant("lgbm_ma", "lightgbm", MA_FEATURES),
    ModelVariant("lgbm_rsi", "lightgbm", RSI_FEATURES),
    ModelVariant("lgbm_ma_k", "lightgbm", (*MA_FEATURES, *K_FEATURES)),
    ModelVariant("lgbm_core", "lightgbm", CORE_FEATURES),
    ModelVariant(
        "lgbm_core_vol",
        "lightgbm",
        (*CORE_FEATURES, *VOL_FEATURES),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen development-only BTC daily MA7/RSI6 LightGBM "
            "event-quality study without reading the sealed validation period."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    cleaned = json_ready(payload)
    atomic_write_path(
        path,
        lambda temp_path: temp_path.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2),
            encoding="utf-8",
        ),
    )


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilder_rsi(close: pd.Series, period: int = 6) -> pd.Series:
    values = close.to_numpy(dtype="float64")
    result = np.full(len(values), np.nan, dtype="float64")
    if len(values) <= period:
        return pd.Series(result, index=close.index)
    deltas = np.diff(values)
    gains = np.maximum(deltas, 0.0)
    losses = np.maximum(-deltas, 0.0)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())

    def rsi_value(gain: float, loss: float) -> float:
        if loss == 0.0 and gain == 0.0:
            return 50.0
        if loss == 0.0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    result[period] = rsi_value(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        delta_index = index - 1
        avg_gain = (avg_gain * (period - 1) + gains[delta_index]) / period
        avg_loss = (avg_loss * (period - 1) + losses[delta_index]) / period
        result[index] = rsi_value(avg_gain, avg_loss)
    return pd.Series(result, index=close.index)


def load_development_daily() -> pd.DataFrame:
    layout = DataLakeLayout.from_settings(load_settings(None))
    frame = DuckDBWarehouse(layout).load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol=DISPLAY_SYMBOL,
        timeframe="1d",
        source="binance_futures_kline_api_direct",
        end=DEVELOPMENT_END_EXCLUSIVE,
    )
    if frame.empty:
        raise RuntimeError("Development daily BTCUSDT dataset is empty")
    frame = frame.sort_values("ts").reset_index(drop=True)
    if frame["ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
        raise RuntimeError("Sealed validation daily rows entered P1 memory")
    return frame


def load_development_hourly() -> pd.DataFrame:
    if not HOURLY_PATH.exists():
        raise FileNotFoundError(HOURLY_PATH)
    frame = pd.read_parquet(
        HOURLY_PATH,
        columns=["ts", "open", "high", "low", "close", "is_closed", "source"],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    if frame.empty or frame["ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
        raise RuntimeError("Invalid development-only hourly stop path")
    expected = pd.date_range(frame["ts"].min(), frame["ts"].max(), freq="1h")
    if len(expected.difference(pd.DatetimeIndex(frame["ts"]))) > 0:
        raise RuntimeError("Development hourly stop path contains gaps")
    if (~frame["is_closed"].astype(bool)).any():
        raise RuntimeError("Development hourly stop path contains open bars")
    return frame


def load_development_funding() -> pd.DataFrame:
    if not FUNDING_PATH.exists():
        raise FileNotFoundError(FUNDING_PATH)
    frame = pd.read_parquet(
        FUNDING_PATH,
        columns=[
            "ts",
            "funding_nominal_ts",
            "funding_rate",
            "mark_price",
            "mark_price_source",
        ],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["funding_nominal_ts"] = pd.to_datetime(frame["funding_nominal_ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    if frame.empty or frame["ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
        raise RuntimeError("Invalid development-only funding dataset")
    if frame["ts"].duplicated().any():
        raise RuntimeError("Development funding contains duplicate timestamps")
    nominal = pd.DatetimeIndex(frame["funding_nominal_ts"])
    expected = pd.date_range(nominal.min(), nominal.max(), freq="8h")
    missing = expected.difference(nominal)
    if len(missing):
        raise RuntimeError(
            f"Resolved development funding contains {len(missing)} nominal gaps"
        )
    return frame


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            result["high"].astype(float) - result["low"].astype(float),
            (result["high"].astype(float) - previous_close).abs(),
            (result["low"].astype(float) - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["sma7"] = close.rolling(7, min_periods=7).mean()
    result["atr7"] = true_range.rolling(7, min_periods=7).mean()
    result["rsi6"] = wilder_rsi(close, 6)
    result["rsi6_delta_1"] = result["rsi6"].diff()
    result["rsi6_min_5"] = result["rsi6"].rolling(5, min_periods=5).min()
    result["rsi6_max_5"] = result["rsi6"].rolling(5, min_periods=5).max()
    result["rsi6_low20_last5"] = result["rsi6"].le(20.0).rolling(5, min_periods=5).max()
    result["rsi6_high80_last5"] = (
        result["rsi6"].ge(80.0).rolling(5, min_periods=5).max()
    )
    result["quote_volume_ratio_7"] = (
        result["quote_volume"]
        / result["quote_volume"].rolling(7, min_periods=7).median()
    )
    result["trade_count_ratio_7"] = (
        result["trade_count"] / result["trade_count"].rolling(7, min_periods=7).median()
    )
    result["cross_up"] = close.shift(1).lt(result["sma7"].shift(1)) & close.gt(
        result["sma7"]
    )
    result["cross_down"] = close.shift(1).gt(result["sma7"].shift(1)) & close.lt(
        result["sma7"]
    )
    return result


def prior_side_duration(frame: pd.DataFrame, index: int, side: int) -> int:
    duration = 0
    old_side = -side
    for cursor in range(index - 1, -1, -1):
        close = float(frame.at[cursor, "close"])
        ma = float(frame.at[cursor, "sma7"])
        if not (math.isfinite(close) and math.isfinite(ma)):
            break
        relation = 1 if close > ma else -1 if close < ma else 0
        if relation != old_side:
            break
        duration += 1
    return duration


def event_features(frame: pd.DataFrame, index: int, side: int) -> dict[str, float]:
    atr = float(frame.at[index, "atr7"])
    ma = float(frame.at[index, "sma7"])
    prior_ma = float(frame.at[index - 1, "sma7"])
    prior_gap = (float(frame.at[index - 1, "close"]) - prior_ma) / atr
    close_gap = (float(frame.at[index, "close"]) - ma) / atr
    open_value = float(frame.at[index, "open"])
    close_value = float(frame.at[index, "close"])
    high = float(frame.at[index, "high"])
    low = float(frame.at[index, "low"])
    candle_range = high - low
    values = {
        "side": float(side),
        "prev_close_ma_gap_atr": prior_gap,
        "close_ma_gap_atr": close_gap,
        "cross_span_atr": side * (close_gap - prior_gap),
        "ma7_slope_1_atr": (ma - prior_ma) / atr,
        "ma7_slope_3_atr": (ma - float(frame.at[index - 3, "sma7"])) / atr,
        "prior_side_duration": float(prior_side_duration(frame, index, side)),
        "body_atr": (close_value - open_value) / atr,
        "range_atr": candle_range / atr,
        "upper_wick_atr": (high - max(open_value, close_value)) / atr,
        "lower_wick_atr": (min(open_value, close_value) - low) / atr,
        "close_location": (
            (close_value - low) / candle_range if candle_range > 0.0 else 0.5
        ),
        "return_3_atr": (close_value - float(frame.at[index - 3, "close"])) / atr,
        "return_5_atr": (close_value - float(frame.at[index - 5, "close"])) / atr,
        "rsi6": float(frame.at[index, "rsi6"]),
        "rsi6_delta_1": float(frame.at[index, "rsi6_delta_1"]),
        "rsi6_min_5": float(frame.at[index, "rsi6_min_5"]),
        "rsi6_max_5": float(frame.at[index, "rsi6_max_5"]),
        "rsi6_low20_last5": float(frame.at[index, "rsi6_low20_last5"]),
        "rsi6_high80_last5": float(frame.at[index, "rsi6_high80_last5"]),
        "quote_volume_ratio_7": float(frame.at[index, "quote_volume_ratio_7"]),
        "trade_count_ratio_7": float(frame.at[index, "trade_count_ratio_7"]),
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("event feature contains non-finite values")
    return values


def find_close_exit(
    daily: pd.DataFrame,
    *,
    signal_index: int,
    side: int,
) -> tuple[pd.Timestamp, float, str] | None:
    entry_index = signal_index + 1
    signal_rsi = float(daily.at[signal_index, "rsi6"])
    armed = signal_rsi >= 80.0 if side > 0 else signal_rsi <= 20.0
    for index in range(entry_index, len(daily) - 1):
        rsi = float(daily.at[index, "rsi6"])
        rsi_exit = armed and (rsi < 80.0 if side > 0 else rsi > 20.0)
        ma_exit = bool(
            daily.at[index, "cross_down"] if side > 0 else daily.at[index, "cross_up"]
        )
        if rsi_exit or ma_exit:
            reason = (
                "rsi_and_ma7"
                if rsi_exit and ma_exit
                else "rsi6_reversal"
                if rsi_exit
                else "opposite_ma7_cross"
            )
            exit_index = index + 1
            exit_ts = pd.Timestamp(daily.at[exit_index, "ts"])
            exit_open = float(daily.at[exit_index, "open"])
            return exit_ts, exit_open, reason
        if not armed:
            armed = rsi >= 80.0 if side > 0 else rsi <= 20.0
    return None


def find_stop_exit(
    hourly: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    stop_search_end: pd.Timestamp,
    side: int,
    stop_price: float,
) -> tuple[pd.Timestamp, float, float, str] | None:
    timestamps = pd.DatetimeIndex(hourly["ts"])
    left = int(timestamps.searchsorted(entry_ts, side="left"))
    right = int(timestamps.searchsorted(stop_search_end, side="left"))
    for row in hourly.iloc[left:right].itertuples(index=False):
        hit = (
            float(row.low) <= stop_price if side > 0 else float(row.high) >= stop_price
        )
        if not hit:
            continue
        gap = (
            float(row.open) <= stop_price if side > 0 else float(row.open) >= stop_price
        )
        reference = float(row.open) if gap else stop_price
        fill = reference * (1.0 - side * SLIPPAGE_RATE)
        return (
            pd.Timestamp(row.ts),
            reference,
            fill,
            "hard_stop_gap" if gap else "hard_stop",
        )
    return None


def funding_return(
    funding: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    side: int,
    entry_fill: float,
) -> tuple[float, int]:
    timestamps = pd.DatetimeIndex(funding["ts"])
    left = int(timestamps.searchsorted(entry_ts, side="right"))
    right = int(timestamps.searchsorted(exit_ts, side="left"))
    window = funding.iloc[left:right]
    cash_return = (
        -side
        * window["funding_rate"].to_numpy(dtype="float64")
        * window["mark_price"].to_numpy(dtype="float64")
        / entry_fill
    )
    return float(cash_return.sum()), int(len(window))


def build_trade_path(
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    entry_fill: float,
    exit_fill: float,
    side: int,
    net_return: float,
) -> pd.DataFrame:
    timestamps = pd.DatetimeIndex(hourly["ts"])
    left = int(timestamps.searchsorted(entry_ts, side="left"))
    right = int(timestamps.searchsorted(exit_ts, side="left"))
    rows: list[dict[str, Any]] = [{"ts": entry_ts, "factor": 1.0 - FEE_RATE}]
    funding_ts = pd.DatetimeIndex(funding["ts"])
    funding_left = int(funding_ts.searchsorted(entry_ts, side="right"))
    for bar in hourly.iloc[left:right].itertuples(index=False):
        mark_time = pd.Timestamp(bar.ts) + pd.Timedelta(hours=1)
        funding_right = int(funding_ts.searchsorted(mark_time, side="right"))
        active = funding.iloc[funding_left:funding_right]
        funding_component = float(
            (
                -side
                * active["funding_rate"].to_numpy(dtype="float64")
                * active["mark_price"].to_numpy(dtype="float64")
                / entry_fill
            ).sum()
        )
        factor = (
            1.0
            - FEE_RATE
            + side * (float(bar.close) - entry_fill) / entry_fill
            + funding_component
        )
        rows.append({"ts": mark_time, "factor": factor})
    rows.append({"ts": exit_ts, "factor": 1.0 + net_return})
    path = pd.DataFrame(rows).sort_values("ts", kind="stable")
    return path.drop_duplicates("ts", keep="last").reset_index(drop=True)


def path_excursions(
    hourly: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    entry_fill: float,
    exit_fill: float,
    side: int,
    atr: float,
) -> tuple[float, float]:
    timestamps = pd.DatetimeIndex(hourly["ts"])
    left = int(timestamps.searchsorted(entry_ts, side="left"))
    right = int(timestamps.searchsorted(exit_ts, side="left"))
    window = hourly.iloc[left:right]
    if side > 0:
        favorable = (
            max(float(window["high"].max()), exit_fill)
            if not window.empty
            else exit_fill
        )
        adverse = (
            min(float(window["low"].min()), exit_fill)
            if not window.empty
            else exit_fill
        )
        mfe = max(0.0, (favorable - entry_fill) / atr)
        mae = max(0.0, (entry_fill - adverse) / atr)
    else:
        favorable = (
            min(float(window["low"].min()), exit_fill)
            if not window.empty
            else exit_fill
        )
        adverse = (
            max(float(window["high"].max()), exit_fill)
            if not window.empty
            else exit_fill
        )
        mfe = max(0.0, (entry_fill - favorable) / atr)
        mae = max(0.0, (adverse - entry_fill) / atr)
    return float(mfe), float(mae)


def simulate_event(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    signal_index: int,
    side: int,
    event_id: int,
) -> tuple[dict[str, Any], pd.DataFrame] | None:
    entry_index = signal_index + 1
    if entry_index >= len(daily):
        return None
    signal_ts = pd.Timestamp(daily.at[signal_index, "ts"])
    entry_ts = pd.Timestamp(daily.at[entry_index, "ts"])
    funding_start_day = pd.Timestamp(funding["funding_nominal_ts"].min()).floor("1D")
    if entry_ts < funding_start_day:
        return None
    atr = float(daily.at[signal_index, "atr7"])
    entry_open = float(daily.at[entry_index, "open"])
    entry_fill = entry_open * (1.0 + side * SLIPPAGE_RATE)
    stop_price = entry_fill - side * STOP_ATR * atr
    close_exit = find_close_exit(daily, signal_index=signal_index, side=side)
    stop_search_end = (
        close_exit[0] if close_exit is not None else DEVELOPMENT_END_EXCLUSIVE
    )
    stop_exit = find_stop_exit(
        hourly,
        entry_ts=entry_ts,
        stop_search_end=stop_search_end,
        side=side,
        stop_price=stop_price,
    )
    if stop_exit is not None:
        exit_ts, exit_reference, exit_fill, exit_reason = stop_exit
    elif close_exit is not None:
        exit_ts, exit_reference, exit_reason = close_exit
        exit_fill = exit_reference * (1.0 - side * SLIPPAGE_RATE)
    else:
        return None
    if exit_ts >= DEVELOPMENT_END_EXCLUSIVE:
        return None
    funding_component, funding_events = funding_return(
        funding,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        side=side,
        entry_fill=entry_fill,
    )
    gross_return = side * (exit_fill - entry_fill) / entry_fill
    entry_fee = FEE_RATE
    exit_fee = FEE_RATE * exit_fill / entry_fill
    net_return = gross_return + funding_component - entry_fee - exit_fee
    mfe_atr, mae_atr = path_excursions(
        hourly,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        entry_fill=entry_fill,
        exit_fill=exit_fill,
        side=side,
        atr=atr,
    )
    features = event_features(daily, signal_index, side)
    bars_held = max(
        1,
        int(math.ceil((exit_ts - entry_ts) / pd.Timedelta(days=1))),
    )
    record: dict[str, Any] = {
        "event_id": event_id,
        "signal_index": signal_index,
        "signal_ts": signal_ts,
        "side": side,
        "side_name": "long" if side > 0 else "short",
        "entry_ts": entry_ts,
        "entry_open": entry_open,
        "entry_fill": entry_fill,
        "signal_atr7": atr,
        "stop_price": stop_price,
        "exit_ts": exit_ts,
        "exit_reference": exit_reference,
        "exit_fill": exit_fill,
        "exit_reason": exit_reason,
        "bars_held": bars_held,
        "gross_return": gross_return,
        "funding_return": funding_component,
        "funding_events": funding_events,
        "entry_fee_return": entry_fee,
        "exit_fee_return": exit_fee,
        "net_return": net_return,
        "net_return_atr": net_return / (atr / entry_fill),
        "mfe_atr": mfe_atr,
        "mae_atr": mae_atr,
        "label": int(net_return > 0.0),
        **features,
    }
    path = build_trade_path(
        hourly,
        funding,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        entry_fill=entry_fill,
        exit_fill=exit_fill,
        side=side,
        net_return=net_return,
    )
    return record, path


def build_events(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    records: list[dict[str, Any]] = []
    paths: dict[int, pd.DataFrame] = {}
    event_id = 0
    for index in range(12, len(daily) - 1):
        if bool(daily.at[index, "cross_up"]):
            side = 1
        elif bool(daily.at[index, "cross_down"]):
            side = -1
        else:
            continue
        try:
            simulated = simulate_event(
                daily,
                hourly,
                funding,
                signal_index=index,
                side=side,
                event_id=event_id,
            )
        except ValueError:
            continue
        if simulated is None:
            continue
        record, path = simulated
        records.append(record)
        paths[event_id] = path
        event_id += 1
    events = pd.DataFrame(records).sort_values("signal_ts").reset_index(drop=True)
    if events.empty:
        raise RuntimeError("No eligible MA7 crossing events were built")
    if events["signal_ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
        raise RuntimeError("Validation event entered P1 event table")
    if events[list((*CORE_FEATURES, *VOL_FEATURES))].isna().any().any():
        raise RuntimeError("Eligible P1 events contain missing frozen features")
    return events, paths


def make_folds(
    events: pd.DataFrame,
    *,
    initial_fraction: float,
    blocks: int,
) -> list[tuple[int, pd.DataFrame, pd.DataFrame]]:
    count = len(events)
    initial = int(math.floor(count * initial_fraction))
    if initial < 2 or count - initial < blocks:
        raise RuntimeError(
            f"Too few events for {blocks} folds with initial fraction {initial_fraction}"
        )
    test_positions = np.array_split(np.arange(initial, count), blocks)
    folds: list[tuple[int, pd.DataFrame, pd.DataFrame]] = []
    for fold_number, positions in enumerate(test_positions, start=1):
        if len(positions) == 0:
            raise RuntimeError("Walk-forward produced an empty test block")
        test = events.iloc[positions].copy()
        first_test_signal = pd.Timestamp(test["signal_ts"].iloc[0])
        train = events.iloc[: int(positions[0])].copy()
        train = train.loc[train["exit_ts"].lt(first_test_signal)].copy()
        if train.empty or train["label"].nunique() < 2:
            raise RuntimeError(
                f"Fold {fold_number} training data lacks two label classes"
            )
        folds.append((fold_number, train, test))
    return folds


class ConstantProbabilityModel:
    def __init__(self, probability: float) -> None:
        self.probability = float(probability)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        positive = np.full(len(frame), self.probability, dtype="float64")
        return np.column_stack([1.0 - positive, positive])


def fit_model(
    events: pd.DataFrame,
    variant: ModelVariant,
) -> Any:
    labels = events["label"].astype(int)
    if labels.nunique() < 2:
        return ConstantProbabilityModel(float(labels.mean()))
    features = events[list(variant.features)]
    if variant.model_type == "logistic":
        model = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        C=1.0,
                        solver="lbfgs",
                        max_iter=2000,
                        class_weight=None,
                        random_state=SEED,
                    ),
                ),
            ]
        )
    else:
        model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(features, labels)
    return model


def predict_probability(
    model: Any,
    events: pd.DataFrame,
    features: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(
        model.predict_proba(events[list(features)])[:, 1],
        dtype="float64",
    )


def predict_contributions(
    model: Any,
    events: pd.DataFrame,
    features: tuple[str, ...],
) -> np.ndarray:
    if not isinstance(model, lgb.LGBMClassifier):
        return np.zeros((len(events), len(features) + 1), dtype="float64")
    return np.asarray(
        model.booster_.predict(
            events[list(features)],
            pred_contrib=True,
        ),
        dtype="float64",
    )


def strategy_metrics(
    events: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
) -> dict[str, Any]:
    selected = events.sort_values("signal_ts").reset_index(drop=True)
    if selected.empty:
        return {
            "closed_trades": 0,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "funding_return_sum": 0.0,
        }
    equity = 1.0
    curve_rows: list[dict[str, Any]] = []
    positive = 0.0
    negative = 0.0
    for row in selected.itertuples(index=False):
        trade_return = float(row.net_return)
        if trade_return > 0.0:
            positive += trade_return
        elif trade_return < 0.0:
            negative += -trade_return
        base_equity = equity
        path = paths[int(row.event_id)]
        for point in path.itertuples(index=False):
            curve_rows.append(
                {
                    "ts": pd.Timestamp(point.ts),
                    "equity": base_equity * float(point.factor),
                }
            )
        equity *= 1.0 + trade_return
    curve = pd.DataFrame(curve_rows).sort_values("ts", kind="stable")
    curve = curve.drop_duplicates("ts", keep="last")
    daily_curve = (
        curve.assign(day=curve["ts"].dt.floor("1D"))
        .groupby("day", as_index=False)["equity"]
        .last()
    )
    running_max = daily_curve["equity"].cummax()
    drawdown = daily_curve["equity"] / running_max - 1.0
    profit_factor = positive / negative if negative > 0.0 else math.inf
    total_return = equity - 1.0
    return {
        "closed_trades": int(len(selected)),
        "total_return": float(total_return),
        "total_return_pct": float(total_return * 100.0),
        "profit_factor": float(profit_factor),
        "win_rate": float(selected["label"].mean()),
        "max_drawdown": float(drawdown.min()),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "long_trades": int(selected["side"].gt(0).sum()),
        "short_trades": int(selected["side"].lt(0).sum()),
        "funding_return_sum": float(selected["funding_return"].sum()),
    }


def route_events(events: pd.DataFrame, route: str) -> pd.DataFrame:
    if route == "combined":
        return events.copy()
    if route == "long_only":
        return events.loc[events["side"].gt(0)].copy()
    if route == "short_only":
        return events.loc[events["side"].lt(0)].copy()
    raise ValueError(f"unknown route: {route}")


def select_threshold_inner(
    events: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
    variant: ModelVariant,
) -> tuple[float, list[dict[str, Any]]]:
    folds = make_folds(events, initial_fraction=0.50, blocks=3)
    predictions: list[dict[str, Any]] = []
    for fold_number, train, test in folds:
        model = fit_model(train, variant)
        probability = predict_probability(model, test, variant.features)
        prediction = test.copy()
        prediction["probability"] = probability
        predictions.append(
            {
                "fold": fold_number,
                "prediction": prediction,
            }
        )
    scored: list[dict[str, Any]] = []
    for threshold in THRESHOLDS:
        fold_metrics: list[dict[str, Any]] = []
        total_trades = 0
        for item in predictions:
            prediction = item["prediction"]
            selected = prediction.loc[prediction["probability"].ge(threshold)].copy()
            metrics = strategy_metrics(selected, paths)
            total_trades += int(metrics["closed_trades"])
            fold_metrics.append(
                {
                    "fold": item["fold"],
                    "metrics": metrics,
                }
            )
        worst_return = min(
            float(item["metrics"]["total_return"]) for item in fold_metrics
        )
        scored.append(
            {
                "threshold": float(threshold),
                "worst_fold_return": worst_return,
                "total_trades": total_trades,
                "fold_metrics": fold_metrics,
            }
        )
    ranked = sorted(
        scored,
        key=lambda item: (
            -float(item["worst_fold_return"]),
            float(item["threshold"]),
            -int(item["total_trades"]),
        ),
    )
    return float(ranked[0]["threshold"]), scored


def predictive_metrics(labels: pd.Series, probability: np.ndarray) -> dict[str, Any]:
    y = labels.astype(int).to_numpy()
    prediction = probability >= 0.50
    return {
        "rows": int(len(y)),
        "positive_rate": float(y.mean()),
        "log_loss": float(log_loss(y, probability, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y, probability)),
        "roc_auc": (
            float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None
        ),
        "balanced_accuracy_at_050": float(balanced_accuracy_score(y, prediction)),
        "probability_mean": float(probability.mean()),
        "probability_min": float(probability.min()),
        "probability_max": float(probability.max()),
    }


def run_variant_walk_forward(
    events: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
    variant: ModelVariant,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    outer_folds = make_folds(events, initial_fraction=0.40, blocks=4)
    prediction_frames: list[pd.DataFrame] = []
    shap_frames: list[pd.DataFrame] = []
    fold_reports: list[dict[str, Any]] = []
    for fold_number, train, test in outer_folds:
        threshold, inner_scores = select_threshold_inner(
            train,
            paths,
            variant,
        )
        model = fit_model(train, variant)
        probability = predict_probability(model, test, variant.features)
        prediction = test.copy()
        prediction["variant_id"] = variant.variant_id
        prediction["fold"] = fold_number
        prediction["probability"] = probability
        prediction["threshold"] = threshold
        prediction["selected"] = probability >= threshold
        prediction_frames.append(prediction)
        if variant.model_type == "lightgbm":
            contributions = predict_contributions(
                model,
                test,
                variant.features,
            )
            shap = test[["event_id", "signal_ts", "side", "label"]].copy()
            shap["variant_id"] = variant.variant_id
            shap["fold"] = fold_number
            for feature_index, feature in enumerate(variant.features):
                shap[f"shap_{feature}"] = contributions[:, feature_index]
            shap["shap_base"] = contributions[:, -1]
            shap_frames.append(shap)
        fold_reports.append(
            {
                "fold": fold_number,
                "train_rows": int(len(train)),
                "train_start": pd.Timestamp(train["signal_ts"].min()),
                "train_end": pd.Timestamp(train["signal_ts"].max()),
                "test_rows": int(len(test)),
                "test_start": pd.Timestamp(test["signal_ts"].min()),
                "test_end": pd.Timestamp(test["signal_ts"].max()),
                "selected_threshold": threshold,
                "predictive": predictive_metrics(test["label"], probability),
                "inner_threshold_scores": inner_scores,
            }
        )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    shap = pd.concat(shap_frames, ignore_index=True) if shap_frames else pd.DataFrame()
    routes: dict[str, Any] = {}
    for route in ("combined", "long_only", "short_only"):
        fold_comparisons: list[dict[str, Any]] = []
        for fold_number in range(1, 5):
            fold = predictions.loc[predictions["fold"].eq(fold_number)].copy()
            fold_route = route_events(fold, route)
            selected = fold_route.loc[fold_route["selected"]].copy()
            model_metrics = strategy_metrics(selected, paths)
            baseline_metrics = strategy_metrics(fold_route, paths)
            fold_comparisons.append(
                {
                    "fold": fold_number,
                    "model": model_metrics,
                    "all_cross_baseline": baseline_metrics,
                    "return_beats_baseline": (
                        float(model_metrics["total_return"])
                        > float(baseline_metrics["total_return"])
                    ),
                }
            )
        route_frame = route_events(predictions, route)
        selected_route = route_frame.loc[route_frame["selected"]].copy()
        model_metrics = strategy_metrics(selected_route, paths)
        baseline_metrics = strategy_metrics(route_frame, paths)
        better_fold_count = sum(
            bool(item["return_beats_baseline"]) for item in fold_comparisons
        )
        gate = bool(
            int(model_metrics["closed_trades"]) >= 30
            and float(model_metrics["total_return"]) > 0.0
            and float(model_metrics["profit_factor"]) >= 1.20
            and float(model_metrics["max_drawdown"])
            >= float(baseline_metrics["max_drawdown"])
            and better_fold_count >= 3
        )
        routes[route] = {
            "model": model_metrics,
            "all_cross_baseline": baseline_metrics,
            "better_fold_count": better_fold_count,
            "folds": fold_comparisons,
            "development_gate_pass": gate,
        }
    report = {
        "variant": asdict(variant),
        "outer_folds": fold_reports,
        "routes": routes,
    }
    return predictions, shap, report


def choose_core_route(core_report: dict[str, Any]) -> str | None:
    routes = core_report["routes"]
    if routes["combined"]["development_gate_pass"]:
        return "combined"
    passing = [
        route
        for route in ("long_only", "short_only")
        if routes[route]["development_gate_pass"]
    ]
    if not passing:
        return None
    if len(passing) == 1:
        return passing[0]
    return sorted(
        passing,
        key=lambda route: (
            min(
                float(fold["model"]["total_return"]) for fold in routes[route]["folds"]
            ),
            int(routes[route]["model"]["closed_trades"]),
        ),
        reverse=True,
    )[0]


def shap_summary(
    events: pd.DataFrame,
    shap: pd.DataFrame,
    features: tuple[str, ...],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in features:
        column = f"shap_{feature}"
        fold_means = shap.groupby("fold")[column].mean()
        nonzero = fold_means.loc[fold_means.ne(0.0)]
        sign_consistency = (
            max(int(nonzero.gt(0.0).sum()), int(nonzero.lt(0.0).sum())) / len(nonzero)
            if len(nonzero)
            else 0.0
        )
        rows.append(
            {
                "feature": feature,
                "mean_abs_shap": float(shap[column].abs().mean()),
                "mean_shap": float(shap[column].mean()),
                "fold_sign_consistency": float(sign_consistency),
            }
        )
    summary = pd.DataFrame(rows).sort_values(
        ["mean_abs_shap", "fold_sign_consistency"],
        ascending=False,
    )
    merged = shap[["event_id", "fold", *[f"shap_{f}" for f in features]]].merge(
        events[["event_id", "label", "net_return", *features]],
        on="event_id",
        how="left",
        validate="one_to_one",
    )
    dependence: dict[str, Any] = {}
    for feature in summary["feature"].head(8):
        try:
            bins = pd.qcut(
                merged[feature],
                q=min(5, merged[feature].nunique()),
                duplicates="drop",
            )
        except ValueError:
            continue
        grouped = merged.assign(bin=bins).groupby(
            "bin",
            observed=True,
            dropna=True,
        )
        dependence[str(feature)] = [
            {
                "bin": str(key),
                "rows": int(len(group)),
                "feature_mean": float(group[feature].mean()),
                "shap_mean": float(group[f"shap_{feature}"].mean()),
                "label_rate": float(group["label"].mean()),
                "net_return_mean": float(group["net_return"].mean()),
            }
            for key, group in grouped
        ]
    return summary, dependence


def extract_split_thresholds(
    model: lgb.LGBMClassifier,
) -> list[dict[str, Any]]:
    dump = model.booster_.dump_model()
    feature_names = model.booster_.feature_name()
    rows: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], tree_index: int) -> None:
        if "split_feature" not in node:
            return
        feature_index = int(node["split_feature"])
        rows.append(
            {
                "tree": tree_index,
                "feature": feature_names[feature_index],
                "threshold": float(node["threshold"]),
                "split_gain": float(node.get("split_gain", 0.0)),
                "internal_count": int(node.get("internal_count", 0)),
            }
        )
        visit(node["left_child"], tree_index)
        visit(node["right_child"], tree_index)

    for tree_index, tree in enumerate(dump["tree_info"]):
        visit(tree["tree_structure"], tree_index)
    return sorted(rows, key=lambda row: row["split_gain"], reverse=True)


def recent_slice_metrics(
    predictions: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
    route: str,
) -> dict[str, Any]:
    end = pd.Timestamp(predictions["signal_ts"].max())
    result: dict[str, Any] = {}
    for label, days in (
        ("1d", 1),
        ("7d", 7),
        ("1m", 30),
        ("3m", 90),
        ("6m", 180),
        ("1y", 365),
    ):
        cutoff = end - pd.Timedelta(days=days)
        frame = predictions.loc[predictions["signal_ts"].ge(cutoff)].copy()
        frame = route_events(frame, route)
        selected = frame.loc[frame["selected"]].copy()
        result[label] = {
            "start": cutoff,
            "end": end,
            "selection_role": "audit_only",
            "model": strategy_metrics(selected, paths),
            "all_cross_baseline": strategy_metrics(frame, paths),
        }
    return result


def typical_events(
    predictions: pd.DataFrame,
    route: str | None,
) -> dict[str, Any]:
    routed = (
        route_events(predictions, route) if route is not None else predictions.copy()
    )
    selected = routed.loc[routed["selected"]].copy()
    columns = [
        "event_id",
        "signal_ts",
        "side_name",
        "probability",
        "threshold",
        "net_return",
        "net_return_atr",
        "exit_reason",
        "rsi6",
        "rsi6_min_5",
        "rsi6_max_5",
        "close_ma_gap_atr",
        "ma7_slope_3_atr",
        "body_atr",
        "upper_wick_atr",
        "lower_wick_atr",
    ]
    return {
        "selected_best": selected.nlargest(5, "net_return")[columns].to_dict("records"),
        "selected_worst": selected.nsmallest(5, "net_return")[columns].to_dict(
            "records"
        ),
        "highest_probability_winners": routed.loc[routed["label"].eq(1)]
        .nlargest(5, "probability")[columns]
        .to_dict("records"),
        "highest_probability_losers": routed.loc[routed["label"].eq(0)]
        .nlargest(5, "probability")[columns]
        .to_dict("records"),
        "best_realized": routed.nlargest(5, "net_return")[columns].to_dict("records"),
        "worst_realized": routed.nsmallest(5, "net_return")[columns].to_dict("records"),
    }


def probability_ranking(predictions: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for variant_id, frame in predictions.groupby("variant_id", sort=True):
        ranked = frame.copy()
        ranked["probability_quintile"] = pd.qcut(
            ranked["probability"],
            q=5,
            labels=False,
            duplicates="drop",
        )
        quintiles = (
            ranked.groupby("probability_quintile", observed=True)
            .agg(
                rows=("event_id", "size"),
                probability_mean=("probability", "mean"),
                label_rate=("label", "mean"),
                net_return_mean=("net_return", "mean"),
            )
            .reset_index()
        )
        result[str(variant_id)] = {
            "spearman_probability_vs_label": float(
                ranked["probability"].corr(ranked["label"], method="spearman")
            ),
            "spearman_probability_vs_net_return": float(
                ranked["probability"].corr(
                    ranked["net_return"],
                    method="spearman",
                )
            ),
            "quintiles": quintiles.to_dict("records"),
        }
    return result


def run_self_tests() -> None:
    rising = pd.Series(np.arange(1.0, 20.0))
    falling = pd.Series(np.arange(20.0, 1.0, -1.0))
    assert math.isclose(float(wilder_rsi(rising, 6).dropna().iloc[-1]), 100.0)
    assert math.isclose(float(wilder_rsi(falling, 6).dropna().iloc[-1]), 0.0)
    sample = pd.DataFrame(
        {
            "signal_ts": pd.date_range("2024-01-01", periods=20, freq="D", tz="UTC"),
            "exit_ts": pd.date_range("2024-01-02", periods=20, freq="D", tz="UTC"),
            "label": [0, 1] * 10,
        }
    )
    folds = make_folds(sample, initial_fraction=0.40, blocks=4)
    assert len(folds) == 4
    assert all(len(train) > 0 and len(test) > 0 for _, train, test in folds)
    long_fill = 100.0 * (1.0 + SLIPPAGE_RATE)
    short_fill = 100.0 * (1.0 - SLIPPAGE_RATE)
    assert long_fill > 100.0 and short_fill < 100.0


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_tests()
        print(json.dumps({"self_test": "PASS"}, indent=2))
        return
    generated_at = datetime.now(UTC)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    daily = add_indicators(load_development_daily())
    hourly = load_development_hourly()
    funding = load_development_funding()
    events, paths = build_events(daily, hourly, funding)

    event_path = args.output_dir / "p1_events.parquet"
    atomic_write_path(
        event_path,
        lambda temp_path: events.to_parquet(temp_path, index=False),
    )

    all_predictions: list[pd.DataFrame] = []
    all_shap: list[pd.DataFrame] = []
    variant_reports: dict[str, Any] = {}
    for variant in MODEL_VARIANTS:
        predictions, shap, report = run_variant_walk_forward(
            events,
            paths,
            variant,
        )
        all_predictions.append(predictions)
        if not shap.empty:
            all_shap.append(shap)
        variant_reports[variant.variant_id] = report

    predictions = pd.concat(all_predictions, ignore_index=True)
    prediction_path = args.output_dir / "p1_outer_predictions.parquet"
    atomic_write_path(
        prediction_path,
        lambda temp_path: predictions.to_parquet(temp_path, index=False),
    )
    shap = pd.concat(all_shap, ignore_index=True)
    shap_path = args.output_dir / "p1_outer_shap.parquet"
    atomic_write_path(
        shap_path,
        lambda temp_path: shap.to_parquet(temp_path, index=False),
    )

    core_report = variant_reports["lgbm_core"]
    selected_route = choose_core_route(core_report)
    core_predictions = predictions.loc[predictions["variant_id"].eq("lgbm_core")].copy()
    core_shap = shap.loc[shap["variant_id"].eq("lgbm_core")].copy()
    shap_table, dependence = shap_summary(
        events,
        core_shap,
        CORE_FEATURES,
    )
    shap_summary_path = args.output_dir / "p1_core_shap_summary.csv"
    atomic_write_path(
        shap_summary_path,
        lambda temp_path: shap_table.to_csv(temp_path, index=False),
    )
    write_json(args.output_dir / "p1_core_feature_dependence.json", dependence)

    final_threshold, final_threshold_scores = select_threshold_inner(
        events,
        paths,
        next(
            variant for variant in MODEL_VARIANTS if variant.variant_id == "lgbm_core"
        ),
    )
    final_model = fit_model(
        events,
        next(
            variant for variant in MODEL_VARIANTS if variant.variant_id == "lgbm_core"
        ),
    )
    if not isinstance(final_model, lgb.LGBMClassifier):
        raise RuntimeError("Final full-development core model is not LightGBM")
    model_path = args.output_dir / "p1_final_core_model.txt"
    final_model.booster_.save_model(str(model_path))
    split_thresholds = extract_split_thresholds(final_model)
    write_json(
        args.output_dir / "p1_final_core_split_thresholds.json",
        split_thresholds[:100],
    )
    manifest = {
        "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
        "stage": "P1 development-only",
        "features": list(CORE_FEATURES),
        "model_params": LGBM_PARAMS,
        "diagnostic_full_development_threshold": final_threshold,
        "selected_route": selected_route,
        "validation_authorized": selected_route is not None,
        "model_path": str(model_path.relative_to(ROOT)),
        "model_sha256": file_sha256(model_path),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "validation_end_inclusive_sealed": VALIDATION_END_INCLUSIVE,
        "validation_revealed": False,
    }
    write_json(args.output_dir / "p1_final_core_model_manifest.json", manifest)

    selected_oos = (
        route_events(core_predictions, selected_route)
        if selected_route is not None
        else core_predictions.iloc[0:0].copy()
    )
    selected_oos = selected_oos.loc[selected_oos["selected"]].copy()
    selected_path = args.output_dir / "p1_selected_oos_trades.parquet"
    atomic_write_path(
        selected_path,
        lambda temp_path: selected_oos.to_parquet(temp_path, index=False),
    )

    summary = {
        "generated_at_utc": generated_at,
        "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
        "stage": "P1 development-only",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "validation_revealed": False,
        "data": {
            "market": "Binance USD-M Futures",
            "symbol": "BTCUSDT perpetual",
            "timeframe": "1d signals + 1h stop path",
            "daily_start": pd.Timestamp(daily["ts"].min()),
            "daily_end": pd.Timestamp(daily["ts"].max()),
            "daily_rows": int(len(daily)),
            "hourly_start": pd.Timestamp(hourly["ts"].min()),
            "hourly_end": pd.Timestamp(hourly["ts"].max()),
            "hourly_rows": int(len(hourly)),
            "funding_start": pd.Timestamp(funding["ts"].min()),
            "funding_end": pd.Timestamp(funding["ts"].max()),
            "funding_rows": int(len(funding)),
        },
        "costs": {
            "fee_per_fill": FEE_RATE,
            "adverse_slippage_per_fill": SLIPPAGE_RATE,
            "funding": "actual rate and official mark/frozen official mark fallback",
            "funding_boundary": "entry_ts < funding_ts < exit_ts",
        },
        "events": {
            "eligible": int(len(events)),
            "positive_labels": int(events["label"].sum()),
            "positive_rate": float(events["label"].mean()),
            "long": int(events["side"].gt(0).sum()),
            "short": int(events["side"].lt(0).sum()),
            "exit_reasons": events["exit_reason"].value_counts().to_dict(),
            "average_positive_return": float(
                events.loc[events["label"].eq(1), "net_return"].mean()
            ),
            "average_nonpositive_return": float(
                events.loc[events["label"].eq(0), "net_return"].mean()
            ),
            "descriptive_break_even_positive_probability": float(
                -events.loc[events["label"].eq(0), "net_return"].mean()
                / (
                    events.loc[events["label"].eq(1), "net_return"].mean()
                    - events.loc[events["label"].eq(0), "net_return"].mean()
                )
            ),
        },
        "variant_reports": variant_reports,
        "oos_probability_ranking": probability_ranking(predictions),
        "core_decision": {
            "selected_route": selected_route,
            "development_gate_pass": selected_route is not None,
            "diagnostic_full_development_threshold": final_threshold,
            "threshold_for_future_validation": (
                final_threshold if selected_route is not None else None
            ),
            "final_threshold_scores": final_threshold_scores,
            "validation_eligible": selected_route is not None,
        },
        "interpretability": {
            "shap_summary": shap_table.to_dict("records"),
            "feature_dependence_path": str(
                (args.output_dir / "p1_core_feature_dependence.json").relative_to(ROOT)
            ),
            "top_split_thresholds": split_thresholds[:30],
            "typical_events": typical_events(core_predictions, selected_route),
        },
        "recent_slices_anchored_to_development_end_audit_only": (
            recent_slice_metrics(core_predictions, paths, selected_route)
            if selected_route is not None
            else {}
        ),
        "artifacts": {
            "events": str(event_path.relative_to(ROOT)),
            "predictions": str(prediction_path.relative_to(ROOT)),
            "outer_shap": str(shap_path.relative_to(ROOT)),
            "shap_summary": str(shap_summary_path.relative_to(ROOT)),
            "selected_oos_trades": str(selected_path.relative_to(ROOT)),
            "model": str(model_path.relative_to(ROOT)),
        },
    }
    summary_path = args.output_dir / "p1_development_summary.json"
    write_json(summary_path, summary)
    print(
        json.dumps(
            {
                "events": summary["events"],
                "core_decision": summary["core_decision"],
                "core_routes": core_report["routes"],
                "summary": str(summary_path),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
