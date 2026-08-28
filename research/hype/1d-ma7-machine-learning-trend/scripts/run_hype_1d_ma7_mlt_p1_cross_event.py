from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p0.py"

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
ALIAS = "HYPE-1D-MA7-MLT"
EXPERIMENT = "P1_CROSS_EVENT_DYNAMIC_EXIT"
RUN_DATE = "2026-08-27"
TRAIN_DAYS = 365
FEE = 0.001
SLIPPAGE = 0.0004
COST_PER_FILL = FEE + SLIPPAGE
SLOPE_MIN_ATR = 0.02
SUCCESS_TARGET_ATR = 2.0
FAILURE_STOP_ATR = 1.5
LABEL_HORIZON = 21
EXIT_LOOKAHEAD = 5
EXIT_VALUE_BUFFER = COST_PER_FILL
ENTRY_THRESHOLD = 0.50
EXIT_THRESHOLD = 0.50
MODEL_C = 0.10
RANDOM_STATE = 20260827

ENTRY_FEATURES = [
    "aligned_slope1_atr",
    "aligned_slope3_atr_per_day",
    "cross_after_atr",
    "cross_before_atr",
    "aligned_body_atr",
    "aligned_close_location",
    "aligned_rsi6",
    "range_atr",
    "er7",
    "volume_z7",
    "atr7_pct",
]

EXIT_FEATURES = [
    "aligned_ma_gap_atr",
    "aligned_slope1_atr",
    "aligned_slope3_atr_per_day",
    "aligned_return_1d",
    "aligned_return_3d",
    "aligned_rsi6",
    "er7",
    "atr7_pct",
    "age_fraction",
    "unrealized_atr",
    "mfe_atr",
    "mae_atr",
    "giveback_atr",
    "crossed_back_ma7",
]


@dataclass(slots=True)
class ModelBundle:
    model: Any
    features: list[str]
    positive_rate: float
    row_count: int


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]
    decisions: list[dict[str, Any]]


class ConstantProbabilityModel:
    def __init__(self, probability: float):
        self.probability = float(probability)

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        p = np.full(len(x), self.probability, dtype=float)
        return np.column_stack([1.0 - p, p])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {FAMILY} {EXPERIMENT}.")
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


def load_dependencies() -> tuple[Any, Any]:
    p0 = _load_module(P0_SCRIPT, "hype_1d_ma7_mlt_p1_p0")
    return p0, p0.load_market()


def build_state_frame(p0: Any, market: Any) -> pd.DataFrame:
    frame = market.daily.copy()
    close = frame["close"].astype(float)
    log_close = np.log(close)
    log_volume = np.log1p(frame["volume"].astype(float))
    atr7 = p0.wilder_atr(frame, 7)
    ma7 = close.rolling(7, min_periods=7).mean()
    rsi6 = p0.wilder_rsi(close, 6)
    er7 = p0.efficiency_ratio(close, 7)
    volume_mean = log_volume.rolling(7, min_periods=7).mean()
    volume_std = log_volume.rolling(7, min_periods=7).std(ddof=0)
    output = frame.copy()
    output["ma7"] = ma7
    output["atr7"] = atr7
    output["slope1_atr"] = ma7.diff() / atr7
    output["slope3_atr_per_day"] = ma7.diff(3) / (3.0 * atr7)
    output["rsi6"] = rsi6
    output["er7"] = er7
    output["volume_z7"] = (log_volume - volume_mean) / volume_std.replace(0.0, np.nan)
    output["atr7_pct"] = atr7 / close
    output["return_1d"] = log_close.diff()
    output["return_3d"] = log_close.diff(3)
    output["close_location"] = (frame["close"] - frame["low"]) / (
        frame["high"] - frame["low"]
    ).replace(0.0, np.nan)
    return output


def _finite_row(row: dict[str, Any], columns: list[str]) -> bool:
    return all(np.isfinite(float(row[column])) for column in columns)


def build_events(state: pd.DataFrame, market: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for decision_index in range(7, len(state)):
        current = state.iloc[decision_index]
        prior = state.iloc[decision_index - 1]
        side = 0
        if (
            prior["close"] <= prior["ma7"]
            and current["close"] > current["ma7"]
            and current["slope1_atr"] >= SLOPE_MIN_ATR
        ):
            side = 1
        elif (
            prior["close"] >= prior["ma7"]
            and current["close"] < current["ma7"]
            and current["slope1_atr"] <= -SLOPE_MIN_ATR
        ):
            side = -1
        if side == 0:
            continue
        atr = float(current["atr7"])
        prior_atr = float(prior["atr7"])
        row: dict[str, Any] = {
            "event_id": f"E{decision_index:04d}",
            "decision_index": decision_index,
            "decision_ts": pd.Timestamp(current["ts"]).isoformat(),
            "entry_open_index": decision_index + 1,
            "entry_ts": pd.Timestamp(market.open_ts[decision_index + 1]).isoformat(),
            "side_value": side,
            "side": "long" if side > 0 else "short",
            "entry_atr": atr,
            "aligned_slope1_atr": side * float(current["slope1_atr"]),
            "aligned_slope3_atr_per_day": side * float(current["slope3_atr_per_day"]),
            "cross_after_atr": side * (float(current["close"]) - float(current["ma7"])) / atr,
            "cross_before_atr": -side * (float(prior["close"]) - float(prior["ma7"])) / prior_atr,
            "aligned_body_atr": side * (float(current["close"]) - float(current["open"])) / atr,
            "aligned_close_location": (
                float(current["close_location"])
                if side > 0
                else 1.0 - float(current["close_location"])
            ),
            "aligned_rsi6": side * (float(current["rsi6"]) - 50.0) / 50.0,
            "range_atr": (float(current["high"]) - float(current["low"])) / atr,
            "er7": float(current["er7"]),
            "volume_z7": float(current["volume_z7"]),
            "atr7_pct": float(current["atr7_pct"]),
        }
        if _finite_row(row, ENTRY_FEATURES):
            rows.append(row)
    return pd.DataFrame(rows)


def _funded_open_return(market: Any, start_open: int, end_open: int, side: int) -> float:
    equity = 1.0
    for open_index in range(start_open + 1, end_open + 1):
        price_return = float(market.opens[open_index] / market.opens[open_index - 1] - 1.0)
        equity *= 1.0 + side * price_return
        equity -= equity * side * float(market.funding_by_open[open_index])
    return float(equity - 1.0)


def add_event_outcomes(events: pd.DataFrame, market: Any, p0: Any) -> pd.DataFrame:
    output = events.copy()
    records: list[dict[str, Any]] = []
    terminal = len(market.opens) - 1
    for event in output.to_dict("records"):
        entry = int(event["entry_open_index"])
        side = int(event["side_value"])
        atr = float(event["entry_atr"])
        entry_price = float(market.opens[entry])
        full = entry + LABEL_HORIZON <= terminal
        end = min(entry + LABEL_HORIZON, terminal)
        first_target: int | None = None
        first_stop: int | None = None
        excursions: list[float] = []
        for open_index in range(entry + 1, end + 1):
            excursion = side * (float(market.opens[open_index]) - entry_price) / atr
            excursions.append(excursion)
            if first_target is None and excursion >= SUCCESS_TARGET_ATR:
                first_target = open_index
            if first_stop is None and excursion <= -FAILURE_STOP_ATR:
                first_stop = open_index
        success: float | None
        if not full:
            success = None
        else:
            success = float(
                first_target is not None
                and (first_stop is None or first_target < first_stop)
            )
        record: dict[str, Any] = {
            "label_complete": full,
            "trend_success": success,
            "first_target_open_index": first_target,
            "first_stop_open_index": first_stop,
            "mfe_21_atr": max([0.0, *excursions]),
            "mae_21_atr": min([0.0, *excursions]),
        }
        for horizon in (1, 3, 5, 7, 14, 21):
            record[f"net_return_h{horizon}"] = (
                p0.single_trade_return(market, int(event["decision_index"]), horizon, side)
                if entry + horizon <= terminal
                else math.nan
            )
        records.append(record)
    return pd.concat([output.reset_index(drop=True), pd.DataFrame(records)], axis=1)


def exit_feature_row(
    state: pd.DataFrame,
    market: Any,
    event: dict[str, Any],
    decision_index: int,
) -> dict[str, Any]:
    side = int(event["side_value"])
    entry_open_index = int(event["entry_open_index"])
    entry_price = float(market.opens[entry_open_index])
    entry_atr = float(event["entry_atr"])
    current = state.iloc[decision_index]
    held = state.iloc[entry_open_index : decision_index + 1]
    if side > 0:
        mfe = (float(held["high"].max()) - entry_price) / entry_atr
        adverse = (float(held["low"].min()) - entry_price) / entry_atr
    else:
        mfe = (entry_price - float(held["low"].min())) / entry_atr
        adverse = (entry_price - float(held["high"].max())) / entry_atr
    mfe = max(0.0, mfe)
    mae = max(0.0, -adverse)
    unrealized = side * (float(current["close"]) - entry_price) / entry_atr
    row = {
        "aligned_ma_gap_atr": side
        * (float(current["close"]) - float(current["ma7"]))
        / float(current["atr7"]),
        "aligned_slope1_atr": side * float(current["slope1_atr"]),
        "aligned_slope3_atr_per_day": side * float(current["slope3_atr_per_day"]),
        "aligned_return_1d": side * float(current["return_1d"]),
        "aligned_return_3d": side * float(current["return_3d"]),
        "aligned_rsi6": side * (float(current["rsi6"]) - 50.0) / 50.0,
        "er7": float(current["er7"]),
        "atr7_pct": float(current["atr7_pct"]),
        "age_fraction": (decision_index - entry_open_index + 1) / LABEL_HORIZON,
        "unrealized_atr": unrealized,
        "mfe_atr": mfe,
        "mae_atr": mae,
        "giveback_atr": max(0.0, mfe - unrealized),
        "crossed_back_ma7": float(
            (side > 0 and current["close"] <= current["ma7"])
            or (side < 0 and current["close"] >= current["ma7"])
        ),
    }
    return row


def build_exit_rows(
    events: pd.DataFrame,
    state: pd.DataFrame,
    market: Any,
    *,
    train_only: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    max_known_open = TRAIN_DAYS - 1 if train_only else len(market.opens) - 1
    for event in events.to_dict("records"):
        entry = int(event["entry_open_index"])
        for decision_index in range(entry, entry + LABEL_HORIZON - 1):
            exit_now = decision_index + 1
            last_future = decision_index + 1 + EXIT_LOOKAHEAD
            if last_future > max_known_open or decision_index >= len(state):
                break
            features = exit_feature_row(state, market, event, decision_index)
            if not _finite_row(features, EXIT_FEATURES):
                continue
            increments = [
                _funded_open_return(market, exit_now, future, int(event["side_value"]))
                for future in range(exit_now + 1, last_future + 1)
            ]
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_decision_index": int(event["decision_index"]),
                    "decision_index": decision_index,
                    "decision_ts": pd.Timestamp(state.iloc[decision_index]["ts"]).isoformat(),
                    "continue_value": int(max(increments) > EXIT_VALUE_BUFFER),
                    "best_incremental_return": max(increments),
                    **features,
                }
            )
    return pd.DataFrame(rows)


def fit_model(frame: pd.DataFrame, features: list[str], target: str) -> ModelBundle:
    y = frame[target].astype(int)
    positive_rate = float(y.mean())
    if y.nunique() < 2:
        model: Any = ConstantProbabilityModel(positive_rate)
    else:
        model = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        C=MODEL_C,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        max_iter=2000,
                    ),
                ),
            ]
        )
        model.fit(frame[features], y)
    return ModelBundle(model=model, features=features, positive_rate=positive_rate, row_count=len(frame))


def predict_probability(bundle: ModelBundle, row: dict[str, Any] | pd.Series) -> float:
    frame = pd.DataFrame([{feature: float(row[feature]) for feature in bundle.features}])
    return float(bundle.model.predict_proba(frame)[0, 1])


def expanding_oof_metrics(
    frame: pd.DataFrame,
    features: list[str],
    target: str,
    group_column: str,
) -> dict[str, Any]:
    groups = (
        frame[[group_column]]
        .drop_duplicates()
        .sort_values(group_column)[group_column]
        .tolist()
    )
    minimum_train_groups = max(10, int(math.ceil(len(groups) * 0.40)))
    remaining = groups[minimum_train_groups:]
    if not remaining:
        return {"available": False, "reason": "too_few_groups"}
    folds = [part.tolist() for part in np.array_split(np.asarray(remaining), min(4, len(remaining))) if len(part)]
    predictions: list[float] = []
    actuals: list[int] = []
    fold_rows: list[dict[str, Any]] = []
    for test_groups in folds:
        first_test = min(test_groups)
        train = frame.loc[frame[group_column] < first_test]
        test = frame.loc[frame[group_column].isin(test_groups)]
        if train.empty or test.empty or train[target].nunique() < 2:
            continue
        bundle = fit_model(train, features, target)
        probability = bundle.model.predict_proba(test[features])[:, 1]
        predictions.extend(probability.tolist())
        actuals.extend(test[target].astype(int).tolist())
        fold_rows.append(
            {
                "train_rows": len(train),
                "test_rows": len(test),
                "first_test_group": int(first_test),
                "last_test_group": int(max(test_groups)),
            }
        )
    if not predictions:
        return {"available": False, "reason": "no_valid_expanding_fold"}
    y = np.asarray(actuals, dtype=int)
    p = np.asarray(predictions, dtype=float)
    return {
        "available": True,
        "rows": len(y),
        "positive_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        "brier": float(brier_score_loss(y, p)),
        "accuracy_at_0_5": float(accuracy_score(y, p >= 0.5)),
        "predicted_positive_rate": float(np.mean(p >= 0.5)),
        "folds": fold_rows,
    }


def _profit_factor(trades: list[dict[str, Any]]) -> float:
    wins = sum(max(0.0, float(trade["net_return"])) for trade in trades)
    losses = -sum(min(0.0, float(trade["net_return"])) for trade in trades)
    if losses <= 0:
        return 999.0 if wins > 0 else 0.0
    return float(wins / losses)


def backtest(
    market: Any,
    state: pd.DataFrame,
    events: pd.DataFrame,
    *,
    strategy: str,
    entry_model: ModelBundle | None,
    exit_model: ModelBundle | None,
    start_open_index: int,
    terminal_open_index: int,
) -> BacktestResult:
    event_map = {int(row["decision_index"]): row for row in events.to_dict("records")}
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    side = 0
    entry_open_index = -1
    entry_equity = math.nan
    entry_price = math.nan
    entry_atr = math.nan
    entry_event: dict[str, Any] | None = None
    entry_probability: float | None = None
    pending_exit: dict[str, Any] | None = None
    total_cost = 0.0
    total_funding = 0.0
    exposure_days = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    previous_open = float(market.opens[start_open_index])

    for open_index in range(start_open_index, terminal_open_index + 1):
        current_open = float(market.opens[open_index])
        current_ts = pd.Timestamp(market.open_ts[open_index])
        if open_index > start_open_index and side != 0:
            price_return = current_open / previous_open - 1.0
            equity *= 1.0 + side * price_return
            funding_amount = equity * side * float(market.funding_by_open[open_index])
            equity -= funding_amount
            total_funding += funding_amount
            exposure_days += 1

        exit_info = pending_exit
        if side != 0 and open_index == terminal_open_index:
            exit_info = exit_info or {
                "reason": "terminal_mark",
                "decision_ts": None,
                "continue_probability": None,
            }
        if side != 0 and exit_info is not None:
            exit_cost = equity * COST_PER_FILL
            equity -= exit_cost
            total_cost += exit_cost
            trades.append(
                {
                    "strategy": strategy,
                    "event_id": entry_event["event_id"] if entry_event else None,
                    "entry_signal_ts": entry_event["decision_ts"] if entry_event else None,
                    "entry_ts": pd.Timestamp(market.open_ts[entry_open_index]).isoformat(),
                    "exit_ts": current_ts.isoformat(),
                    "side": "long" if side > 0 else "short",
                    "side_value": side,
                    "entry_price": entry_price,
                    "exit_price": current_open,
                    "entry_probability": entry_probability,
                    "exit_continue_probability": exit_info.get("continue_probability"),
                    "bars_held": open_index - entry_open_index,
                    "exit_reason": exit_info["reason"],
                    "exit_decision_ts": exit_info.get("decision_ts"),
                    "net_return": equity / entry_equity - 1.0,
                }
            )
            side = 0
            entry_open_index = -1
            entry_equity = math.nan
            entry_price = math.nan
            entry_atr = math.nan
            entry_event = None
            entry_probability = None
            pending_exit = None

        decision_index = open_index - 1
        event = event_map.get(decision_index)
        if side == 0 and event is not None and open_index < terminal_open_index:
            probability = (
                predict_probability(entry_model, event) if entry_model is not None else None
            )
            accepted = probability is None or probability >= ENTRY_THRESHOLD
            decisions.append(
                {
                    "strategy": strategy,
                    "kind": "entry",
                    "event_id": event["event_id"],
                    "decision_ts": event["decision_ts"],
                    "action_ts": current_ts.isoformat(),
                    "side": event["side"],
                    "probability": probability,
                    "accepted": accepted,
                }
            )
            if accepted:
                entry_equity = equity
                entry_cost = equity * COST_PER_FILL
                equity -= entry_cost
                total_cost += entry_cost
                side = int(event["side_value"])
                entry_open_index = open_index
                entry_price = current_open
                entry_atr = float(event["entry_atr"])
                entry_event = event
                entry_probability = probability

        if side != 0 and open_index < len(state) and entry_event is not None:
            age = open_index - entry_open_index + 1
            probability: float | None = None
            reason: str | None = None
            if age >= LABEL_HORIZON:
                reason = "max_hold_21d"
            elif strategy in {"ML_ENTRY_DYNAMIC_EXIT", "ALL_CROSS_DYNAMIC_EXIT"}:
                features = exit_feature_row(state, market, entry_event, open_index)
                probability = predict_probability(exit_model, features) if exit_model else None
                if probability is not None and probability < EXIT_THRESHOLD:
                    reason = "ml_dynamic_exit"
            elif strategy == "ALL_CROSS_MA7_EXIT":
                current = state.iloc[open_index]
                if side * (float(current["close"]) - float(current["ma7"])) <= 0.0:
                    reason = "ma7_crossback"
            elif strategy == "ALL_CROSS_H7" and age >= 7:
                reason = "fixed_7d"
            if reason is not None:
                pending_exit = {
                    "reason": reason,
                    "decision_ts": pd.Timestamp(state.iloc[open_index]["ts"]).isoformat(),
                    "continue_probability": probability,
                }
            if strategy in {"ML_ENTRY_DYNAMIC_EXIT", "ALL_CROSS_DYNAMIC_EXIT"}:
                decisions.append(
                    {
                        "strategy": strategy,
                        "kind": "exit",
                        "event_id": entry_event["event_id"],
                        "decision_ts": pd.Timestamp(state.iloc[open_index]["ts"]).isoformat(),
                        "action_ts": pd.Timestamp(market.open_ts[open_index + 1]).isoformat(),
                        "side": "long" if side > 0 else "short",
                        "probability": probability,
                        "accepted": reason == "ml_dynamic_exit",
                    }
                )

        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1.0)
        path.append(
            {
                "ts": current_ts.isoformat(),
                "open": current_open,
                "equity": equity,
                "position": side,
            }
        )
        previous_open = current_open

    trade_returns = np.asarray([trade["net_return"] for trade in trades], dtype=float)
    metrics = {
        "total_return": float(equity - 1.0),
        "max_drawdown": float(mdd),
        "profit_factor": _profit_factor(trades),
        "win_rate": float(np.mean(trade_returns > 0.0)) if len(trade_returns) else 0.0,
        "trade_count": len(trades),
        "long_count": sum(int(trade["side_value"]) > 0 for trade in trades),
        "short_count": sum(int(trade["side_value"]) < 0 for trade in trades),
        "exposure_days": exposure_days,
        "total_cost": float(total_cost),
        "total_funding": float(total_funding),
        "final_equity": float(equity),
    }
    return BacktestResult(metrics=metrics, trades=trades, path=path, decisions=decisions)


def event_study(events: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {
        "events": len(events),
        "long": int((events["side_value"] > 0).sum()) if len(events) else 0,
        "short": int((events["side_value"] < 0).sum()) if len(events) else 0,
        "complete_labels": int(events["trend_success"].notna().sum()) if len(events) else 0,
    }
    complete = events.dropna(subset=["trend_success"])
    output["trend_success_rate"] = float(complete["trend_success"].mean()) if len(complete) else None
    for horizon in (1, 3, 5, 7, 14, 21):
        column = f"net_return_h{horizon}"
        values = events[column].dropna()
        output[f"h{horizon}"] = {
            "available": len(values),
            "mean_net_return": float(values.mean()) if len(values) else None,
            "win_rate": float((values > 0.0).mean()) if len(values) else None,
        }
    return output


def recent_slices(path: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(path)
    windows = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}
    output: dict[str, Any] = {}
    for name, days in windows.items():
        sub = frame.tail(min(days + 1, len(frame)))
        start = float(sub["equity"].iloc[0])
        end = float(sub["equity"].iloc[-1])
        output[name] = {
            "available_days": len(sub) - 1,
            "return": end / start - 1.0,
            "max_drawdown": float((sub["equity"] / sub["equity"].cummax() - 1.0).min()),
        }
    return output


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def model_coefficients(bundle: ModelBundle) -> list[dict[str, Any]]:
    if not isinstance(bundle.model, Pipeline):
        return [{"feature": "constant", "coefficient": 0.0}]
    coefficients = bundle.model.named_steps["model"].coef_[0]
    return sorted(
        [
            {"feature": feature, "coefficient": float(coefficient)}
            for feature, coefficient in zip(bundle.features, coefficients, strict=True)
        ],
        key=lambda row: abs(row["coefficient"]),
        reverse=True,
    )


def verdict(results: dict[str, BacktestResult]) -> str:
    ml = results["ML_ENTRY_DYNAMIC_EXIT"].metrics
    if ml["trade_count"] < 3:
        return "INSUFFICIENT_OOS_TRADES"
    if ml["total_return"] <= 0.0 or ml["profit_factor"] < 1.0:
        return "ML_NO_EDGE"
    ma = results["ALL_CROSS_MA7_EXIT"].metrics
    h7 = results["ALL_CROSS_H7"].metrics
    better_mdd = max(ma["max_drawdown"], h7["max_drawdown"])
    if (
        ml["total_return"] > ma["total_return"]
        and ml["total_return"] > h7["total_return"]
        and ml["max_drawdown"] >= better_mdd - 0.05
    ):
        return "ML_BEATS_SIMPLE_CROSS_OOS"
    return "MIXED"


def write_outputs(
    run_date: str,
    market: Any,
    events: pd.DataFrame,
    train_events: pd.DataFrame,
    validation_events: pd.DataFrame,
    exit_rows: pd.DataFrame,
    entry_model: ModelBundle,
    exit_model: ModelBundle,
    entry_oof: dict[str, Any],
    exit_oof: dict[str, Any],
    results: dict[str, BacktestResult],
    v7_reference: dict[str, Any],
) -> dict[str, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_ma7_mlt_p1_cross_event_dynamic_exit_{run_date}"
    paths = {
        "summary": ARTIFACT_DIR / f"{stem}_summary.json",
        "events": ARTIFACT_DIR / f"{stem}_events.csv",
        "exit_training_rows": ARTIFACT_DIR / f"{stem}_exit_training_rows.csv",
        "validation_trades": ARTIFACT_DIR / f"{stem}_validation_trades.csv",
        "validation_path": ARTIFACT_DIR / f"{stem}_validation_path.csv",
        "validation_decisions": ARTIFACT_DIR / f"{stem}_validation_decisions.csv",
        "model_manifest": ARTIFACT_DIR / f"{stem}_model_manifest.json",
    }
    event_output = events.copy()
    event_output["split"] = np.where(
        event_output["decision_index"] < TRAIN_DAYS - 1,
        "train",
        "validation",
    )
    validation_probabilities = []
    for event in event_output.to_dict("records"):
        validation_probabilities.append(
            predict_probability(entry_model, event)
            if int(event["decision_index"]) >= TRAIN_DAYS - 1
            else math.nan
        )
    event_output["entry_probability"] = validation_probabilities
    event_output.to_csv(paths["events"], index=False)
    exit_rows.to_csv(paths["exit_training_rows"], index=False)
    trade_frames = [pd.DataFrame(result.trades) for result in results.values() if result.trades]
    pd.concat(trade_frames, ignore_index=True).to_csv(paths["validation_trades"], index=False)
    path_frames = []
    decision_frames = []
    for strategy, result in results.items():
        path = pd.DataFrame(result.path)
        path.insert(0, "strategy", strategy)
        path_frames.append(path)
        if result.decisions:
            decision_frames.append(pd.DataFrame(result.decisions))
    pd.concat(path_frames, ignore_index=True).to_csv(paths["validation_path"], index=False)
    pd.concat(decision_frames, ignore_index=True).to_csv(paths["validation_decisions"], index=False)
    manifest = {
        "entry_model": {
            "type": "StandardScaler + LogisticRegression",
            "C": MODEL_C,
            "threshold": ENTRY_THRESHOLD,
            "features": ENTRY_FEATURES,
            "training_rows": entry_model.row_count,
            "positive_rate": entry_model.positive_rate,
            "coefficients": model_coefficients(entry_model),
            "expanding_oof": entry_oof,
        },
        "exit_model": {
            "type": "StandardScaler + LogisticRegression",
            "C": MODEL_C,
            "threshold": EXIT_THRESHOLD,
            "features": EXIT_FEATURES,
            "training_rows": exit_model.row_count,
            "positive_rate": exit_model.positive_rate,
            "coefficients": model_coefficients(exit_model),
            "expanding_group_oof": exit_oof,
        },
    }
    paths["model_manifest"].write_text(
        json.dumps(json_ready(manifest), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    validation_metrics = {
        strategy: {**result.metrics, "recent_slices": recent_slices(result.path)}
        for strategy, result in results.items()
    }
    summary = {
        "family": FAMILY,
        "alias": ALIAS,
        "experiment": EXPERIMENT,
        "run_date": run_date,
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "verdict": verdict(results),
        "research_conclusion": "MECHANICAL_HOLDOUT_PASS_BUT_UNPROVEN_LOW_SAMPLE",
        "frozen_contract": str(
            (FAMILY_DIR / "specs/hype-1d-ma7-mlt-p1-cross-event-dynamic-exit-contract-2026-08-27.md").relative_to(ROOT)
        ),
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
        "cost": {
            "fee_per_fill": FEE,
            "slippage_per_fill": SLIPPAGE,
            "round_trip": 2 * COST_PER_FILL,
        },
        "event_definition": {
            "ma": "SMA7",
            "atr": "Wilder ATR7",
            "slope_min_atr": SLOPE_MIN_ATR,
            "entry_timing": "signal close t, fill open t+1",
            "success_target_atr": SUCCESS_TARGET_ATR,
            "failure_stop_atr": FAILURE_STOP_ATR,
            "label_horizon_days": LABEL_HORIZON,
        },
        "event_study": {
            "all": event_study(events),
            "train_label_complete": event_study(train_events),
            "validation": event_study(validation_events),
        },
        "models": manifest,
        "validation": validation_metrics,
        "v7_1_descriptive_reference": v7_reference,
        "limitations": [
            "HYPE-only strict-cross training events are sparse",
            "validation contains very few qualifying events",
            "dynamic exit is daily-close/next-open and has no intraday hard stop",
            "V7.1 saw this historical period and is descriptive rather than clean OOS",
            "the 81-day path was already revealed by P0; P1 was frozen before its own run but this is a reused holdout, not clean prospective OOS",
            "no P1 parameter may be retuned on the revealed 81-day result",
        ],
        "artifacts": {key: str(path.relative_to(ROOT)) for key, path in paths.items()},
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
    assert len(ENTRY_FEATURES) == 11
    assert len(EXIT_FEATURES) == 14
    frame = pd.DataFrame({"x": [-2.0, -1.0, 1.0, 2.0], "y": [0, 0, 1, 1]})
    bundle = fit_model(frame, ["x"], "y")
    assert predict_probability(bundle, {"x": 2.0}) > predict_probability(bundle, {"x": -2.0})
    constant = fit_model(pd.DataFrame({"x": [1.0, 2.0], "y": [1, 1]}), ["x"], "y")
    assert predict_probability(constant, {"x": 0.0}) == 1.0


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("self-test PASS")
        return
    p0, market = load_dependencies()
    state = build_state_frame(p0, market)
    events = add_event_outcomes(build_events(state, market), market, p0)
    train_events = events.loc[
        (events["decision_index"] < TRAIN_DAYS - 1)
        & (events["entry_open_index"] + LABEL_HORIZON <= TRAIN_DAYS - 1)
        & events["label_complete"]
    ].copy()
    validation_events = events.loc[
        (events["decision_index"] >= TRAIN_DAYS - 1)
        & (events["decision_index"] < len(market.daily) - 1)
    ].copy()
    if train_events.empty or train_events["trend_success"].nunique() < 2:
        raise RuntimeError("entry training labels do not contain both classes")
    exit_rows = build_exit_rows(train_events, state, market, train_only=True)
    if exit_rows.empty or exit_rows["continue_value"].nunique() < 2:
        raise RuntimeError("exit training labels do not contain both classes")
    entry_model = fit_model(train_events, ENTRY_FEATURES, "trend_success")
    exit_model = fit_model(exit_rows, EXIT_FEATURES, "continue_value")
    entry_oof = expanding_oof_metrics(
        train_events, ENTRY_FEATURES, "trend_success", "decision_index"
    )
    exit_oof = expanding_oof_metrics(
        exit_rows, EXIT_FEATURES, "continue_value", "event_decision_index"
    )
    results: dict[str, BacktestResult] = {}
    for strategy in (
        "ML_ENTRY_DYNAMIC_EXIT",
        "ALL_CROSS_DYNAMIC_EXIT",
        "ALL_CROSS_MA7_EXIT",
        "ALL_CROSS_H7",
    ):
        results[strategy] = backtest(
            market,
            state,
            validation_events,
            strategy=strategy,
            entry_model=entry_model if strategy == "ML_ENTRY_DYNAMIC_EXIT" else None,
            exit_model=exit_model if "DYNAMIC_EXIT" in strategy else None,
            start_open_index=TRAIN_DAYS,
            terminal_open_index=len(market.daily),
        )
    v7_reference = p0.exact_v7_reference()
    paths = write_outputs(
        args.run_date,
        market,
        events,
        train_events,
        validation_events,
        exit_rows,
        entry_model,
        exit_model,
        entry_oof,
        exit_oof,
        results,
        v7_reference,
    )
    print(
        json.dumps(
            json_ready(
                {
                    "events": {
                        "all": len(events),
                        "train_complete": len(train_events),
                        "validation": len(validation_events),
                    },
                    "entry_positive_rate": entry_model.positive_rate,
                    "exit_positive_rate": exit_model.positive_rate,
                    "entry_oof": entry_oof,
                    "exit_oof": exit_oof,
                    "validation": {key: value.metrics for key, value in results.items()},
                    "verdict": verdict(results),
                    "summary": str(paths["summary"]),
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
