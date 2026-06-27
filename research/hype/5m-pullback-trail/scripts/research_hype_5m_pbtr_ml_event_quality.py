from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


retry = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v33_retry_arm.py", "hype_pbtr_v33_retry_arm_ml")
v33 = retry.v33
v1strict = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v1_strict_live_audit.py", "hype_pbtr_v1_strict_ml")

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_ml_event_quality_{RUN_DATE}.json"
EVENTS_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_ml_event_quality_events_{RUN_DATE}.csv"
SCORES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_ml_event_quality_scores_{RUN_DATE}.csv"
EXACT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_ml_event_quality_exact_{RUN_DATE}.csv"
V1_EVENTS_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_ml_event_quality_v1_events_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-ml-event-quality-{RUN_DATE}.md"

MIN_TRAIN_EVENTS = 600
MIN_MONTH_EVENTS = 20
L2 = 0.02
ITERATIONS = 180
QUANTILES = (0.05, 0.10, 0.20, 0.30)
FEATURE_COLUMNS = (
    "side",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
    "ema_spread_bps",
    "abs_ema_spread_bps",
    "close_ema21_bps",
    "ema21_slope3_bps",
    "ema21_slope6_bps",
    "ema21_slope12_bps",
    "dir_ret12_bps",
    "dir_ret24_bps",
    "dir_ret48_bps",
    "dir_ret96_bps",
    "dir_ret192_bps",
    "dir_ret384_bps",
    "htf_spread_bps",
    "body_atr",
    "dir_body_atr",
    "range_atr",
    "close_pos",
    "adverse_wick_atr",
    "favorable_wick_atr",
    "pullback_depth_atr",
    "atr_bps",
    "atr_ratio_14_96",
    "vol_ratio_96",
    "quote_vol_ratio_96",
    "trade_count_ratio_96",
    "chop14",
    "adx14",
)


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def add_ml_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"]
    high = result["high"]
    low = result["low"]
    open_ = result["open"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    for span in (9, 13, 21, 55, 96):
        column = f"ema{span}"
        if column not in result.columns:
            result[column] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    if "atr14" not in result.columns:
        result["atr14"] = tr.rolling(14, min_periods=14).mean()

    ema21 = result["ema21"]
    ema96 = result["ema96"]
    result["ema_spread_bps_raw"] = (ema21 - ema96) / close * 10000.0
    result["abs_ema_spread_bps"] = result["ema_spread_bps_raw"].abs()
    result["close_ema21_bps_raw"] = (close / ema21 - 1.0) * 10000.0
    for window in (3, 6, 12):
        result[f"ema21_slope{window}_bps_raw"] = (ema21 / ema21.shift(window) - 1.0) * 10000.0
    for window in (12, 24, 48, 96, 192, 384):
        result[f"ret{window}_bps_raw"] = (close / close.shift(window) - 1.0) * 10000.0

    atr = result["atr14"].replace(0.0, np.nan)
    candle_range = (high - low).replace(0.0, np.nan)
    candle_top = pd.concat([open_, close], axis=1).max(axis=1)
    candle_bottom = pd.concat([open_, close], axis=1).min(axis=1)
    result["body_atr"] = (close - open_).abs() / atr
    result["body_atr_raw"] = (close - open_) / atr
    result["range_atr"] = (high - low) / atr
    result["long_close_pos"] = (close - low) / candle_range
    result["short_close_pos"] = (high - close) / candle_range
    result["upper_wick_atr"] = (high - candle_top) / atr
    result["lower_wick_atr"] = (candle_bottom - low) / atr
    result["long_pullback_depth_atr"] = np.maximum(0.0, (ema21 - low) / atr)
    result["short_pullback_depth_atr"] = np.maximum(0.0, (high - ema21) / atr)
    result["atr_bps"] = result["atr14"] / close * 10000.0
    result["atr_ratio_14_96"] = result["atr14"] / result["atr14"].rolling(96, min_periods=96).mean()
    result["vol_ratio_96"] = result["volume"] / result["volume"].rolling(96, min_periods=96).mean()
    result["quote_vol_ratio_96"] = result["quote_volume"] / result["quote_volume"].rolling(96, min_periods=96).mean()
    result["trade_count_ratio_96"] = result["trade_count"] / result["trade_count"].rolling(96, min_periods=96).mean()

    sum_tr = tr.rolling(14, min_periods=14).sum()
    high_14 = high.rolling(14, min_periods=14).max()
    low_14 = low.rolling(14, min_periods=14).min()
    result["chop14"] = 100.0 * np.log10(sum_tr / (high_14 - low_14).replace(0.0, np.nan)) / np.log10(14)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_di = 100.0 * pd.Series(plus_dm, index=result.index).rolling(14, min_periods=14).sum() / sum_tr
    minus_di = 100.0 * pd.Series(minus_dm, index=result.index).rolling(14, min_periods=14).sum() / sum_tr
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)) * 100.0
    result["adx14"] = dx.rolling(14, min_periods=14).mean()

    htf = result.set_index("ts")[["open", "high", "low", "close"]].resample("1h", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    htf = htf.dropna()
    htf["ema21_1h"] = htf["close"].ewm(span=21, adjust=False, min_periods=21).mean()
    htf["ema96_1h"] = htf["close"].ewm(span=96, adjust=False, min_periods=96).mean()
    htf["htf_spread_bps_raw"] = (htf["ema21_1h"] - htf["ema96_1h"]) / htf["close"] * 10000.0
    result = pd.merge_asof(
        result.sort_values("ts"),
        htf[["htf_spread_bps_raw"]].reset_index().sort_values("ts"),
        on="ts",
        direction="backward",
    )
    return result


def direction_value(signal: np.ndarray, long_values: np.ndarray, short_values: np.ndarray) -> np.ndarray:
    return np.where(signal > 0, long_values, short_values)


def build_event_features(frame: pd.DataFrame, signal: np.ndarray, source: str) -> pd.DataFrame:
    idx = np.flatnonzero(signal)
    side = signal[idx].astype("float64")
    ts = pd.to_datetime(frame["ts"], utc=True)
    hour = ts.dt.hour.to_numpy("float64")[idx]
    day = ts.dt.dayofweek.to_numpy("float64")[idx]
    close = frame["close"].to_numpy("float64")

    data: dict[str, Any] = {
        "source": source,
        "idx": idx,
        "signal_ts": frame["ts"].to_numpy()[idx],
        "entry_ts": frame["ts"].to_numpy()[idx + 1],
        "side": side,
        "hour_sin": np.sin(2.0 * np.pi * hour / 24.0),
        "hour_cos": np.cos(2.0 * np.pi * hour / 24.0),
        "day_sin": np.sin(2.0 * np.pi * day / 7.0),
        "day_cos": np.cos(2.0 * np.pi * day / 7.0),
        "ema_spread_bps": side * frame["ema_spread_bps_raw"].to_numpy("float64")[idx],
        "abs_ema_spread_bps": frame["abs_ema_spread_bps"].to_numpy("float64")[idx],
        "close_ema21_bps": side * frame["close_ema21_bps_raw"].to_numpy("float64")[idx],
        "htf_spread_bps": side * frame["htf_spread_bps_raw"].to_numpy("float64")[idx],
        "body_atr": frame["body_atr"].to_numpy("float64")[idx],
        "dir_body_atr": side * frame["body_atr_raw"].to_numpy("float64")[idx],
        "range_atr": frame["range_atr"].to_numpy("float64")[idx],
        "atr_bps": frame["atr_bps"].to_numpy("float64")[idx],
        "atr_ratio_14_96": frame["atr_ratio_14_96"].to_numpy("float64")[idx],
        "vol_ratio_96": frame["vol_ratio_96"].to_numpy("float64")[idx],
        "quote_vol_ratio_96": frame["quote_vol_ratio_96"].to_numpy("float64")[idx],
        "trade_count_ratio_96": frame["trade_count_ratio_96"].to_numpy("float64")[idx],
        "chop14": frame["chop14"].to_numpy("float64")[idx],
        "adx14": frame["adx14"].to_numpy("float64")[idx],
        "close": close[idx],
    }
    for window in (3, 6, 12):
        data[f"ema21_slope{window}_bps"] = side * frame[f"ema21_slope{window}_bps_raw"].to_numpy("float64")[idx]
    for window in (12, 24, 48, 96, 192, 384):
        data[f"dir_ret{window}_bps"] = side * frame[f"ret{window}_bps_raw"].to_numpy("float64")[idx]
    data["close_pos"] = direction_value(
        signal[idx],
        frame["long_close_pos"].to_numpy("float64")[idx],
        frame["short_close_pos"].to_numpy("float64")[idx],
    )
    data["adverse_wick_atr"] = direction_value(
        signal[idx],
        frame["lower_wick_atr"].to_numpy("float64")[idx],
        frame["upper_wick_atr"].to_numpy("float64")[idx],
    )
    data["favorable_wick_atr"] = direction_value(
        signal[idx],
        frame["upper_wick_atr"].to_numpy("float64")[idx],
        frame["lower_wick_atr"].to_numpy("float64")[idx],
    )
    data["pullback_depth_atr"] = direction_value(
        signal[idx],
        frame["long_pullback_depth_atr"].to_numpy("float64")[idx],
        frame["short_pullback_depth_atr"].to_numpy("float64")[idx],
    )
    return pd.DataFrame(data)


def independent_retry_labels(frame: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    cfg = v33.V33_CONFIG
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    rows: list[dict[str, Any]] = []
    n = len(frame)
    for row in events.itertuples(index=False):
        sig_i = int(row.idx)
        direction = int(row.side)
        entry_i = sig_i + 1
        if entry_i >= n or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        active_stop = initial_stop
        armed = False
        arm_i = -1
        reject_count = 0
        reason = "time"
        exit_i = n - 1
        raw_exit = float(close[-1])

        for j in range(entry_i, n):
            bars_held = j - entry_i + 1
            if armed:
                if not retry.armable(direction, active_stop, float(open_[j])):
                    reason = "gap_market_exit"
                    raw_exit = float(open_[j])
                    exit_i = j
                    break
                if retry.touched(direction, active_stop, float(high[j]), float(low[j])):
                    reason = "stop_market"
                    raw_exit = active_stop
                    exit_i = j
                    break
            if not armed and bars_held > 9:
                reason = "stop_arm_deadline"
                raw_exit = float(close[j])
                exit_i = j
                break
            if bars_held < 7:
                continue
            desired_stop = retry.trailed_stop(
                direction,
                entry_price,
                initial_stop,
                high[entry_i : j + 1],
                low[entry_i : j + 1],
                float(atr[j]),
                active_stop,
            )
            active_stop = desired_stop
            if retry.armable(direction, desired_stop, float(close[j])):
                armed = True
                arm_i = j
            else:
                reject_count += 1

        exit_price = retry.exit_price_with_cost(raw_exit, direction)
        net, mae, mfe = retry.net_mae_mfe(
            direction,
            entry_price,
            exit_price,
            high[entry_i : exit_i + 1],
            low[entry_i : exit_i + 1],
        )
        rows.append(
            {
                "idx": sig_i,
                "entry_price": entry_price,
                "exit_idx": exit_i,
                "exit_price": exit_price,
                "net_ret_1x": net,
                "positive_net": float(net > 0),
                "mae_1x": mae,
                "mfe_1x": mfe,
                "reason": reason,
                "bars_held": exit_i - entry_i + 1,
                "arm_success": float(armed),
                "bad_unlock": float(reason in {"stop_arm_deadline", "gap_market_exit"}),
                "trailing_positive": float(armed and reason == "stop_market" and net > 0),
                "reject_count": reject_count,
                "arm_bars_held": (arm_i - entry_i + 1) if arm_i >= 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def build_v1_executed_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    from research_hype_5m_indicator_search import add_features, build_signal

    _ = frame
    frame_v1 = add_features(v1strict.load_all_hype_5m())
    frame_v1["_ts_ns"] = frame_v1["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    signal = build_signal(frame_v1, v1strict.V1_BASE_CONFIG)
    signal = v1strict.apply_v1_final_filter(frame_v1, signal)
    trades, diag = v1strict.simulate_v1_live_realistic(frame_v1, signal)
    rows: list[dict[str, Any]] = []
    diag = diag.reset_index(drop=True)
    for i, trade in enumerate(trades):
        rows.append(
            {
                "source": "v1_executed",
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "side": trade.side,
                "net_ret_1x": trade.net_ret_1x,
                "positive_net": float(trade.net_ret_1x > 0),
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "reason": trade.reason,
                "bad_unlock": float(str(trade.reason).startswith("unlock")),
                "trailing_positive": float(trade.reason in {"stop_market", "target_limit"} and trade.net_ret_1x > 0),
                "lockout_initial_stop_breached": diag.loc[i, "lockout_initial_stop_breached"] if i < len(diag) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def fit_logistic(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    if len(np.unique(y)) < 2:
        return np.zeros(x.shape[1] + 1)
    x_aug = np.c_[np.ones(len(x)), x]
    weights = np.zeros(x_aug.shape[1])
    pos = max(float(y.sum()), 1.0)
    neg = max(float(len(y) - y.sum()), 1.0)
    sample_weight = np.where(y > 0, len(y) / (2.0 * pos), len(y) / (2.0 * neg))
    lr = 0.08
    for _ in range(ITERATIONS):
        pred = sigmoid(x_aug @ weights)
        grad = (x_aug.T @ ((pred - y) * sample_weight)) / len(y)
        grad[1:] += L2 * weights[1:]
        weights -= lr * grad
    return weights


def predict_logistic(x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return sigmoid(np.c_[np.ones(len(x)), x] @ weights)


def fit_ridge(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x_aug = np.c_[np.ones(len(x)), x]
    reg = np.eye(x_aug.shape[1]) * L2
    reg[0, 0] = 0.0
    return np.linalg.pinv(x_aug.T @ x_aug + reg) @ x_aug.T @ y


def predict_linear(x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return np.c_[np.ones(len(x)), x] @ weights


def standardize(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    train_x = train.loc[:, FEATURE_COLUMNS].to_numpy("float64")
    test_x = test.loc[:, FEATURE_COLUMNS].to_numpy("float64")
    med = np.nanmedian(train_x, axis=0)
    train_x = np.where(np.isfinite(train_x), train_x, med)
    test_x = np.where(np.isfinite(test_x), test_x, med)
    mean = train_x.mean(axis=0)
    std = train_x.std(axis=0)
    std[std < 1e-9] = 1.0
    return (train_x - mean) / std, (test_x - mean) / std


def walk_forward_scores(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    result["signal_ts"] = pd.to_datetime(result["signal_ts"], utc=True)
    result["month"] = result["signal_ts"].dt.strftime("%Y-%m")
    result["score"] = np.nan
    result["pred_positive"] = np.nan
    result["pred_bad_unlock"] = np.nan
    result["pred_trailing_positive"] = np.nan
    result["pred_net_ret"] = np.nan
    result["train_events"] = 0
    result["month_events"] = 0

    for month in sorted(result["month"].unique()):
        test_mask = result["month"].eq(month)
        train_mask = result["signal_ts"] < pd.Timestamp(f"{month}-01", tz="UTC")
        train = result.loc[train_mask].dropna(subset=["net_ret_1x"])
        test = result.loc[test_mask]
        if len(train) < MIN_TRAIN_EVENTS or len(test) < MIN_MONTH_EVENTS:
            continue
        train_x, test_x = standardize(train, test)
        y_pos = train["positive_net"].to_numpy("float64")
        y_bad = train["bad_unlock"].to_numpy("float64")
        y_trail = train["trailing_positive"].to_numpy("float64")
        y_ret = train["net_ret_1x"].clip(-0.05, 0.05).to_numpy("float64")

        w_pos = fit_logistic(train_x, y_pos)
        w_bad = fit_logistic(train_x, y_bad)
        w_trail = fit_logistic(train_x, y_trail)
        w_ret = fit_ridge(train_x, y_ret)

        p_pos = predict_logistic(test_x, w_pos)
        p_bad = predict_logistic(test_x, w_bad)
        p_trail = predict_logistic(test_x, w_trail)
        p_ret = predict_linear(test_x, w_ret)
        score = 0.55 * p_pos + 0.25 * p_trail - 0.45 * p_bad + 35.0 * p_ret

        idx = result.index[test_mask]
        result.loc[idx, "pred_positive"] = p_pos
        result.loc[idx, "pred_bad_unlock"] = p_bad
        result.loc[idx, "pred_trailing_positive"] = p_trail
        result.loc[idx, "pred_net_ret"] = p_ret
        result.loc[idx, "score"] = score
        result.loc[idx, "train_events"] = len(train)
        result.loc[idx, "month_events"] = len(test)
    return result


def selected_signal(signal: np.ndarray, scores: pd.DataFrame, quantile: float) -> tuple[np.ndarray, pd.DataFrame]:
    result = np.zeros_like(signal)
    scored = scores.loc[np.isfinite(scores["score"])].copy()
    scored["selected"] = False
    for month, group in scored.groupby("month"):
        threshold = float(group["score"].quantile(1.0 - quantile))
        selected = group.index[group["score"] >= threshold]
        scored.loc[selected, "selected"] = True
        _ = month
    selected_rows = scored.loc[scored["selected"]]
    idx = selected_rows["idx"].to_numpy("int64")
    result[idx] = signal[idx]
    previous_same = np.r_[False, (result[1:] != 0) & (result[1:] == result[:-1])]
    result[previous_same] = 0
    return result, selected_rows


def baseline_eligible_signal(signal: np.ndarray, scores: pd.DataFrame) -> np.ndarray:
    result = np.zeros_like(signal)
    eligible = scores.loc[np.isfinite(scores["score"])]
    idx = eligible["idx"].to_numpy("int64")
    result[idx] = signal[idx]
    previous_same = np.r_[False, (result[1:] != 0) & (result[1:] == result[:-1])]
    result[previous_same] = 0
    return result


def exact_rows(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    label: str,
    selected: pd.DataFrame,
) -> list[dict[str, Any]]:
    modes: list[retry.Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])
    rows: list[dict[str, Any]] = []
    full_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    scored_start = pd.Timestamp(selected["signal_ts"].min()) if len(selected) else full_start
    scored_end = full_end
    for mode in modes:
        eval_signal = signal.copy()
        start = scored_start
        end = scored_end
        if mode.startswith("1m") and frame_1m is not None:
            one_start = pd.Timestamp(frame_1m["ts"].iloc[0])
            one_end = pd.Timestamp(frame_1m["ts"].iloc[-1])
            ts = pd.to_datetime(frame["ts"], utc=True)
            keep = (ts >= one_start) & (ts <= one_end.floor("5min"))
            eval_signal = np.where(keep.to_numpy(), eval_signal, 0).astype(np.int8)
            start = max(start, one_start.ceil("5min"))
            end = min(end, one_end.floor("5min") + pd.Timedelta(minutes=5))
        trades, diag = retry.simulate_retry_arm(frame, eval_signal, frame_1m, mode)
        metrics = v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)
        diag_in_window = diag.loc[(pd.to_datetime(diag["signal_ts"], utc=True) >= start) & (pd.to_datetime(diag["signal_ts"], utc=True) < end)] if not diag.empty else diag
        rows.append(
            {
                "label": label,
                "mode": mode,
                "selected_events": int(np.count_nonzero(eval_signal)),
                "model_selected_rows": int(len(selected)),
                "start": start,
                "end": end,
                "independent_positive_rate": float(selected["positive_net"].mean()) if len(selected) else np.nan,
                "independent_bad_unlock_rate": float(selected["bad_unlock"].mean()) if len(selected) else np.nan,
                "independent_trailing_positive_rate": float(selected["trailing_positive"].mean()) if len(selected) else np.nan,
                "exact_arm_success_rate": float(diag_in_window["armed"].mean()) if "armed" in diag_in_window else np.nan,
                "exact_deadline_rate": float((diag_in_window["reason"] == "stop_arm_deadline").mean()) if "reason" in diag_in_window else np.nan,
                **metrics,
            }
        )
    return rows


def render_exact_table(rows: pd.DataFrame, limit: int = 80) -> list[str]:
    lines = [
        "| label | mode | events | trades | total | PF | win | payoff | DD | bad_unlock | trail+ | armed | deadline |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['mode']}` | `{int(row['selected_events'])}` | `{int(row['trades'])}` | "
            f"`{pct(float(row['total_return']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{pct(float(row['independent_bad_unlock_rate']))}` | `{pct(float(row['independent_trailing_positive_rate']))}` | "
            f"`{pct(float(row['exact_arm_success_rate']))}` | `{pct(float(row['exact_deadline_rate']))}` |"
        )
    return lines


def render_markdown(events: pd.DataFrame, scores: pd.DataFrame, exact: pd.DataFrame, v1_events: pd.DataFrame) -> str:
    exact_sorted = exact.sort_values(["profit_factor", "total_return"], ascending=[False, False])
    robust = (
        exact.groupby("label")
        .agg(
            modes=("mode", "nunique"),
            min_trades=("trades", "min"),
            min_pf=("profit_factor", "min"),
            min_total=("total_return", "min"),
            worst_dd=("max_dd", "min"),
            min_arm=("exact_arm_success_rate", "min"),
            max_deadline=("exact_deadline_rate", "max"),
        )
        .reset_index()
        .sort_values(["min_pf", "min_total"], ascending=[False, False])
    )
    lines = [
        "# HYPE-5M-PBTR ML event quality rescue 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告把 V3.3.1 原始 pullback 触发器降级为事件源，用 walk-forward 机器学习事件质量模型筛选入场。模型只使用信号 K 收盘时已知特征，训练标签来自严格 retry-arm 独立回放；最终结果仍用单仓 exact replay 复核。",
        "",
        "## 数据集",
        "",
        f"- V3.3.1 事件数：`{len(events)}`；可 walk-forward 打分事件：`{int(np.isfinite(scores['score']).sum())}`。",
        f"- V1 strict executed 对照事件：`{len(v1_events)}`；仅作标签分布参考，不用于筛选 V3.3.1。",
        f"- V3.3.1 独立标签 positive rate：`{pct(float(events['positive_net'].mean()))}`；bad unlock/deadline rate：`{pct(float(events['bad_unlock'].mean()))}`；trailing positive rate：`{pct(float(events['trailing_positive'].mean()))}`。",
        "",
        "## 模型",
        "",
        "- 每个月只用该月之前的事件训练，不随机切分。",
        "- 轻量模型为 `numpy` logistic/ridge：分别预测 `positive_net`、`bad_unlock`、`trailing_positive` 和 clipped `net_ret_1x`。",
        "- 综合分数：`0.55 * P(positive) + 0.25 * P(trailing_positive) - 0.45 * P(bad_unlock) + 35 * E(net_ret)`。",
        "- 逐月选择 top `5%/10%/20%/30%` 事件，再回放单仓 V3.3.1 retry-arm。",
        "",
        "## Robust 聚合",
        "",
        "| label | modes | min trades | min total | min PF | worst DD | min armed | max deadline |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in robust.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['modes'])}` | `{int(row['min_trades'])}` | `{pct(float(row['min_total']))}` | "
            f"`{num(float(row['min_pf']))}` | `{pct(float(row['worst_dd']))}` | `{pct(float(row['min_arm']))}` | `{pct(float(row['max_deadline']))}` |"
        )
    lines.extend(["", "## Exact Replay 明细", ""])
    lines.extend(render_exact_table(exact_sorted))
    best = robust.iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"本轮最强 robust 行为 `{best['label']}`，四口径 min PF `{num(float(best['min_pf']))}`，min total `{pct(float(best['min_total']))}`，最少交易 `{int(best['min_trades'])}`。",
            "",
            "如果 min PF 仍低于 `1`，说明这套轻量 ML 事件质量选择器没有救回 V3.3.1；若 PF 接近或超过 `1` 但交易数太低，则只能作为下一轮 paper-audit 特征线索。无论哪种情况，不能只因为 trailing/armed 比例上升就认为可上线。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- events CSV：`{EVENTS_PATH}`",
            f"- scores CSV：`{SCORES_PATH}`",
            f"- exact CSV：`{EXACT_PATH}`",
            f"- V1 对照 CSV：`{V1_EVENTS_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    frame = add_ml_features(v33.add_minimal_features(raw, v33.V33_CONFIG))
    signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    events = build_event_features(frame, signal, "v3_3_1")
    labels = independent_retry_labels(frame, events)
    events = events.merge(labels, on="idx", how="inner")
    events = events.replace([np.inf, -np.inf], np.nan).dropna(subset=["net_ret_1x"])
    scores = walk_forward_scores(events)

    frame_1m = retry.load_hype_1m()
    exact_rows_out: list[dict[str, Any]] = []
    eligible_signal = baseline_eligible_signal(signal, scores)
    eligible_rows = scores.loc[np.isfinite(scores["score"])].copy()
    exact_rows_out.extend(exact_rows(frame, eligible_signal, frame_1m, "baseline_scored_events", eligible_rows))
    for quantile in QUANTILES:
        selected, selected_rows = selected_signal(signal, scores, quantile)
        exact_rows_out.extend(exact_rows(frame, selected, frame_1m, f"ml_top_{int(quantile * 100)}pct", selected_rows))

    exact = pd.DataFrame(exact_rows_out)
    v1_events = build_v1_executed_dataset(frame)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENTS_PATH, index=False)
    scores.to_csv(SCORES_PATH, index=False)
    exact.to_csv(EXACT_PATH, index=False)
    v1_events.to_csv(V1_EVENTS_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(events, scores, exact, v1_events), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy_line": "HYPE-5M-PBTR-ML-event-quality",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "features": FEATURE_COLUMNS,
                    "quantiles": QUANTILES,
                    "model": "walk_forward_numpy_logistic_ridge",
                    "min_train_events": MIN_TRAIN_EVENTS,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "events": str(EVENTS_PATH),
                    "scores": str(SCORES_PATH),
                    "exact": str(EXACT_PATH),
                    "v1_events": str(V1_EVENTS_PATH),
                },
                "summary": exact.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(exact.sort_values(["profit_factor", "total_return"], ascending=[False, False]).to_string(index=False))


if __name__ == "__main__":
    main()
