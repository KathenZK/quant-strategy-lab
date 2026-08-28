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
P1_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p1_cross_event.py"
P1_SUMMARY = ARTIFACT_DIR / "hype_1d_ma7_mlt_p1_cross_event_dynamic_exit_2026-08-27_summary.json"

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
EXPERIMENT = "P2_EPISODE_POLICY_LEARNING"
RUN_DATE = "2026-08-27"
TRAIN_DAYS = 365
FEE = 0.001
SLIPPAGE = 0.0004
COST_PER_FILL = FEE + SLIPPAGE
MODEL_C = 0.05
ENTRY_THRESHOLD = 0.55
EXIT_THRESHOLD = 0.45
REVERSAL_MARGIN = 0.10
EPISODE_MAX_AGE = 6
ENTRY_LABEL_HORIZON = 21
ENTRY_TARGET_ATR = 2.0
ENTRY_STOP_ATR = 1.5
SURVIVAL_HORIZON = 14
SURVIVAL_TARGET_ATR = 1.0
SURVIVAL_STOP_ATR = 1.0
MAX_HOLD_DAYS = 30
RANDOM_STATE = 20260827

ENTRY_FEATURES = [
    "episode_age_fraction",
    "aligned_ma_gap_atr",
    "initial_cross_gap_atr",
    "aligned_slope1_atr",
    "aligned_slope3_atr_per_day",
    "aligned_slope_acceleration",
    "aligned_return_1d",
    "aligned_return_3d",
    "aligned_body_atr",
    "aligned_close_location",
    "range_atr",
    "aligned_rsi6",
    "er7",
    "volume_z7",
    "atr7_pct",
    "raw_cross_count7",
]

SURVIVAL_FEATURES = [
    "aligned_ma_gap_atr",
    "aligned_slope1_atr",
    "aligned_slope3_atr_per_day",
    "aligned_slope_acceleration",
    "aligned_return_1d",
    "aligned_return_3d",
    "aligned_rsi6",
    "er7",
    "atr7_pct",
    "hold_age_fraction",
    "unrealized_atr",
    "mfe_atr",
    "mae_atr",
    "giveback_atr",
    "crossed_back_ma7",
    "raw_cross_count7",
]


@dataclass(slots=True)
class ModelBundle:
    model: Any
    features: list[str]
    row_count: int
    positive_rate: float


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]
    decisions: list[dict[str, Any]]


class ConstantProbabilityModel:
    def __init__(self, probability: float):
        self.probability = float(probability)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        p = np.full(len(frame), self.probability, dtype=float)
        return np.column_stack([1.0 - p, p])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {EXPERIMENT}.")
    parser.add_argument("--run-date", default=RUN_DATE)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_context() -> tuple[Any, Any, Any, pd.DataFrame]:
    p1 = load_module(P1_SCRIPT, "hype_1d_ma7_mlt_p2_p1")
    p0, market = p1.load_dependencies()
    state = p1.build_state_frame(p0, market)
    raw_cross = np.zeros(len(state), dtype=int)
    for index in range(1, len(state)):
        prior = state.iloc[index - 1]
        current = state.iloc[index]
        if prior["close"] <= prior["ma7"] and current["close"] > current["ma7"]:
            raw_cross[index] = 1
        elif prior["close"] >= prior["ma7"] and current["close"] < current["ma7"]:
            raw_cross[index] = -1
    state["raw_cross"] = raw_cross
    state["raw_cross_count7"] = (
        pd.Series(np.abs(raw_cross), index=state.index).rolling(7, min_periods=1).sum()
    )
    state["slope_acceleration"] = state["slope1_atr"].diff()
    return p1, p0, market, state


def _finite(row: dict[str, Any], features: list[str]) -> bool:
    return all(np.isfinite(float(row[name])) for name in features)


def entry_feature_row(
    state: pd.DataFrame,
    cross_index: int,
    decision_index: int,
    side: int,
) -> dict[str, Any]:
    current = state.iloc[decision_index]
    cross = state.iloc[cross_index]
    atr = float(current["atr7"])
    cross_atr = float(cross["atr7"])
    return {
        "episode_age_fraction": (decision_index - cross_index) / max(1, EPISODE_MAX_AGE),
        "aligned_ma_gap_atr": side * (float(current["close"]) - float(current["ma7"])) / atr,
        "initial_cross_gap_atr": side * (float(cross["close"]) - float(cross["ma7"])) / cross_atr,
        "aligned_slope1_atr": side * float(current["slope1_atr"]),
        "aligned_slope3_atr_per_day": side * float(current["slope3_atr_per_day"]),
        "aligned_slope_acceleration": side * float(current["slope_acceleration"]),
        "aligned_return_1d": side * float(current["return_1d"]),
        "aligned_return_3d": side * float(current["return_3d"]),
        "aligned_body_atr": side * (float(current["close"]) - float(current["open"])) / atr,
        "aligned_close_location": (
            float(current["close_location"])
            if side > 0
            else 1.0 - float(current["close_location"])
        ),
        "range_atr": (float(current["high"]) - float(current["low"])) / atr,
        "aligned_rsi6": side * (float(current["rsi6"]) - 50.0) / 50.0,
        "er7": float(current["er7"]),
        "volume_z7": float(current["volume_z7"]),
        "atr7_pct": float(current["atr7_pct"]),
        "raw_cross_count7": float(current["raw_cross_count7"]),
    }


def build_episode_candidates(state: pd.DataFrame, market: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    episode_number = 0
    for cross_index in np.flatnonzero(state["raw_cross"].to_numpy()):
        side = int(state.iloc[cross_index]["raw_cross"])
        episode_number += 1
        episode_id = f"X{episode_number:03d}"
        for age in range(EPISODE_MAX_AGE + 1):
            decision_index = int(cross_index + age)
            if decision_index >= len(state) - 1:
                break
            current = state.iloc[decision_index]
            if side * (float(current["close"]) - float(current["ma7"])) <= 0.0:
                break
            features = entry_feature_row(state, int(cross_index), decision_index, side)
            if not _finite(features, ENTRY_FEATURES):
                continue
            rows.append(
                {
                    "episode_id": episode_id,
                    "cross_decision_index": int(cross_index),
                    "cross_ts": pd.Timestamp(state.iloc[cross_index]["ts"]).isoformat(),
                    "decision_index": decision_index,
                    "decision_ts": pd.Timestamp(current["ts"]).isoformat(),
                    "entry_open_index": decision_index + 1,
                    "entry_ts": pd.Timestamp(market.open_ts[decision_index + 1]).isoformat(),
                    "episode_age": age,
                    "side_value": side,
                    "side": "long" if side > 0 else "short",
                    "entry_atr": float(current["atr7"]),
                    **features,
                }
            )
    return pd.DataFrame(rows)


def first_hit_label(
    market: Any,
    *,
    base_open_index: int,
    side: int,
    atr: float,
    horizon: int,
    target_atr: float,
    stop_atr: float,
    max_open_index: int,
) -> tuple[int, float, float]:
    base = float(market.opens[base_open_index])
    mfe = 0.0
    mae = 0.0
    for open_index in range(base_open_index + 1, base_open_index + horizon + 1):
        if open_index > max_open_index:
            raise ValueError("label horizon exceeds boundary")
        excursion = side * (float(market.opens[open_index]) - base) / atr
        mfe = max(mfe, excursion)
        mae = min(mae, excursion)
        if excursion >= target_atr:
            return 1, mfe, mae
        if excursion <= -stop_atr:
            return 0, mfe, mae
    return 0, mfe, mae


def add_entry_labels(candidates: pd.DataFrame, market: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    terminal = len(market.opens) - 1
    for row in candidates.to_dict("records"):
        entry = int(row["entry_open_index"])
        complete = entry + ENTRY_LABEL_HORIZON <= terminal
        if complete:
            label, mfe, mae = first_hit_label(
                market,
                base_open_index=entry,
                side=int(row["side_value"]),
                atr=float(row["entry_atr"]),
                horizon=ENTRY_LABEL_HORIZON,
                target_atr=ENTRY_TARGET_ATR,
                stop_atr=ENTRY_STOP_ATR,
                max_open_index=terminal,
            )
        else:
            label, mfe, mae = None, math.nan, math.nan
        rows.append(
            {
                **row,
                "entry_label_complete": complete,
                "trend_success": label,
                "entry_mfe_21_atr": mfe,
                "entry_mae_21_atr": mae,
            }
        )
    return pd.DataFrame(rows)


def survival_feature_row(
    state: pd.DataFrame,
    market: Any,
    *,
    entry_open_index: int,
    decision_index: int,
    side: int,
    entry_atr: float,
) -> dict[str, Any]:
    current = state.iloc[decision_index]
    entry_price = float(market.opens[entry_open_index])
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
    return {
        "aligned_ma_gap_atr": side * (float(current["close"]) - float(current["ma7"])) / float(current["atr7"]),
        "aligned_slope1_atr": side * float(current["slope1_atr"]),
        "aligned_slope3_atr_per_day": side * float(current["slope3_atr_per_day"]),
        "aligned_slope_acceleration": side * float(current["slope_acceleration"]),
        "aligned_return_1d": side * float(current["return_1d"]),
        "aligned_return_3d": side * float(current["return_3d"]),
        "aligned_rsi6": side * (float(current["rsi6"]) - 50.0) / 50.0,
        "er7": float(current["er7"]),
        "atr7_pct": float(current["atr7_pct"]),
        "hold_age_fraction": (decision_index - entry_open_index + 1) / MAX_HOLD_DAYS,
        "unrealized_atr": unrealized,
        "mfe_atr": mfe,
        "mae_atr": mae,
        "giveback_atr": max(0.0, mfe - unrealized),
        "crossed_back_ma7": float(side * (float(current["close"]) - float(current["ma7"])) <= 0.0),
        "raw_cross_count7": float(current["raw_cross_count7"]),
    }


def build_survival_rows(
    train_candidates: pd.DataFrame,
    state: pd.DataFrame,
    market: Any,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    max_known_open = TRAIN_DAYS - 1
    for candidate in train_candidates.to_dict("records"):
        entry = int(candidate["entry_open_index"])
        for decision_index in range(entry, entry + MAX_HOLD_DAYS):
            base_open = decision_index + 1
            if decision_index >= len(state) or base_open + SURVIVAL_HORIZON > max_known_open:
                break
            features = survival_feature_row(
                state,
                market,
                entry_open_index=entry,
                decision_index=decision_index,
                side=int(candidate["side_value"]),
                entry_atr=float(candidate["entry_atr"]),
            )
            if not _finite(features, SURVIVAL_FEATURES):
                continue
            label, future_mfe, future_mae = first_hit_label(
                market,
                base_open_index=base_open,
                side=int(candidate["side_value"]),
                atr=float(state.iloc[decision_index]["atr7"]),
                horizon=SURVIVAL_HORIZON,
                target_atr=SURVIVAL_TARGET_ATR,
                stop_atr=SURVIVAL_STOP_ATR,
                max_open_index=max_known_open,
            )
            rows.append(
                {
                    "episode_id": candidate["episode_id"],
                    "cross_decision_index": int(candidate["cross_decision_index"]),
                    "candidate_decision_index": int(candidate["decision_index"]),
                    "entry_open_index": entry,
                    "decision_index": decision_index,
                    "decision_ts": pd.Timestamp(state.iloc[decision_index]["ts"]).isoformat(),
                    "side_value": int(candidate["side_value"]),
                    "survival_label": label,
                    "future_mfe_14_atr": future_mfe,
                    "future_mae_14_atr": future_mae,
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
    return ModelBundle(model=model, features=features, row_count=len(frame), positive_rate=positive_rate)


def probability(bundle: ModelBundle, row: dict[str, Any]) -> float:
    frame = pd.DataFrame([{name: float(row[name]) for name in bundle.features}])
    return float(bundle.model.predict_proba(frame)[0, 1])


def expanding_group_oof(
    frame: pd.DataFrame,
    features: list[str],
    target: str,
) -> dict[str, Any]:
    groups = (
        frame[["cross_decision_index"]]
        .drop_duplicates()
        .sort_values("cross_decision_index")["cross_decision_index"]
        .tolist()
    )
    minimum = max(12, int(math.ceil(len(groups) * 0.40)))
    remaining = groups[minimum:]
    folds = [part.tolist() for part in np.array_split(np.asarray(remaining), min(4, len(remaining))) if len(part)]
    actual: list[int] = []
    predicted: list[float] = []
    fold_rows: list[dict[str, Any]] = []
    for test_groups in folds:
        first = min(test_groups)
        train = frame.loc[frame["cross_decision_index"] < first]
        test = frame.loc[frame["cross_decision_index"].isin(test_groups)]
        if train.empty or test.empty or train[target].nunique() < 2:
            continue
        bundle = fit_model(train, features, target)
        values = bundle.model.predict_proba(test[features])[:, 1]
        actual.extend(test[target].astype(int).tolist())
        predicted.extend(values.tolist())
        fold_rows.append(
            {
                "train_groups": int(train["cross_decision_index"].nunique()),
                "train_rows": len(train),
                "test_groups": len(test_groups),
                "test_rows": len(test),
                "first_test_group": int(first),
                "last_test_group": int(max(test_groups)),
            }
        )
    if not predicted:
        return {"available": False, "reason": "no_valid_fold"}
    y = np.asarray(actual, dtype=int)
    p = np.asarray(predicted, dtype=float)
    return {
        "available": True,
        "groups": int(sum(row["test_groups"] for row in fold_rows)),
        "rows": len(y),
        "positive_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        "brier": float(brier_score_loss(y, p)),
        "accuracy_at_0_5": float(accuracy_score(y, p >= 0.5)),
        "predicted_positive_rate": float(np.mean(p >= 0.5)),
        "folds": fold_rows,
    }


def _profit_factor(trades: list[dict[str, Any]]) -> float:
    wins = sum(max(0.0, float(row["net_return"])) for row in trades)
    losses = -sum(min(0.0, float(row["net_return"])) for row in trades)
    if losses <= 0.0:
        return 999.0 if wins > 0.0 else 0.0
    return float(wins / losses)


def trade_path_stats(
    state: pd.DataFrame,
    market: Any,
    *,
    entry_open_index: int,
    exit_open_index: int,
    side: int,
    entry_atr: float,
) -> dict[str, float]:
    entry = float(market.opens[entry_open_index])
    exit_price = float(market.opens[exit_open_index])
    held = state.iloc[entry_open_index : min(exit_open_index, len(state))]
    if held.empty:
        mfe_atr = mae_atr = 0.0
    elif side > 0:
        mfe_atr = max(0.0, (float(held["high"].max()) - entry) / entry_atr)
        mae_atr = min(0.0, (float(held["low"].min()) - entry) / entry_atr)
    else:
        mfe_atr = max(0.0, (entry - float(held["low"].min())) / entry_atr)
        mae_atr = min(0.0, (entry - float(held["high"].max())) / entry_atr)
    favorable_return = side * (exit_price / entry - 1.0)
    mfe_return = mfe_atr * entry_atr / entry
    capture = favorable_return / mfe_return if favorable_return > 0.0 and mfe_return > 0.0 else 0.0
    future_end = min(exit_open_index + SURVIVAL_HORIZON, len(market.opens) - 1)
    remaining = [
        side * (float(market.opens[index]) - exit_price) / entry_atr
        for index in range(exit_open_index + 1, future_end + 1)
    ]
    return {
        "mfe_atr": float(mfe_atr),
        "mae_atr": float(mae_atr),
        "gross_favorable_return": float(favorable_return),
        "capture_ratio": float(capture),
        "remaining_mfe_14_atr": float(max([0.0, *remaining])),
    }


def backtest_policy(
    state: pd.DataFrame,
    market: Any,
    candidates: pd.DataFrame,
    entry_model: ModelBundle,
    survival_model: ModelBundle,
    *,
    strategy: str,
) -> BacktestResult:
    start_open = TRAIN_DAYS
    terminal_open = len(market.daily)
    candidate_map = {
        int(index): group.to_dict("records")
        for index, group in candidates.groupby("decision_index", sort=False)
    }
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    side = 0
    entry_index = -1
    entry_equity = math.nan
    entry_price = math.nan
    entry_atr = math.nan
    entry_candidate: dict[str, Any] | None = None
    entry_probability: float | None = None
    pending: dict[str, Any] | None = None
    used_episodes: set[str] = set()
    total_cost = 0.0
    total_funding = 0.0
    exposure_days = 0
    reversal_count = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    previous_open = float(market.opens[start_open])

    def close_trade(open_index: int, reason: str, info: dict[str, Any]) -> None:
        nonlocal equity, side, entry_index, entry_equity, entry_price, entry_atr
        nonlocal entry_candidate, entry_probability, total_cost
        exit_cost = equity * COST_PER_FILL
        equity -= exit_cost
        total_cost += exit_cost
        stats = trade_path_stats(
            state,
            market,
            entry_open_index=entry_index,
            exit_open_index=open_index,
            side=side,
            entry_atr=entry_atr,
        )
        reverse_cross = info.get("opposite_cross_index")
        trades.append(
            {
                "strategy": strategy,
                "episode_id": entry_candidate["episode_id"] if entry_candidate else None,
                "entry_signal_ts": entry_candidate["decision_ts"] if entry_candidate else None,
                "entry_ts": pd.Timestamp(market.open_ts[entry_index]).isoformat(),
                "exit_ts": pd.Timestamp(market.open_ts[open_index]).isoformat(),
                "side": "long" if side > 0 else "short",
                "side_value": side,
                "entry_price": entry_price,
                "exit_price": float(market.opens[open_index]),
                "entry_probability": entry_probability,
                "exit_survival_probability": info.get("survival_probability"),
                "opposite_entry_probability": info.get("opposite_probability"),
                "bars_held": open_index - entry_index,
                "exit_reason": reason,
                "net_return": equity / entry_equity - 1.0,
                "reversal_delay_days": (
                    open_index - (int(reverse_cross) + 1)
                    if reverse_cross is not None
                    else None
                ),
                **stats,
            }
        )
        side = 0
        entry_index = -1
        entry_equity = math.nan
        entry_price = math.nan
        entry_atr = math.nan
        entry_candidate = None
        entry_probability = None

    def open_trade(open_index: int, candidate: dict[str, Any], p_entry: float | None) -> None:
        nonlocal equity, side, entry_index, entry_equity, entry_price, entry_atr
        nonlocal entry_candidate, entry_probability, total_cost
        entry_equity = equity
        cost = equity * COST_PER_FILL
        equity -= cost
        total_cost += cost
        side = int(candidate["side_value"])
        entry_index = open_index
        entry_price = float(market.opens[open_index])
        entry_atr = float(candidate["entry_atr"])
        entry_candidate = candidate
        entry_probability = p_entry
        used_episodes.add(str(candidate["episode_id"]))

    for open_index in range(start_open, terminal_open + 1):
        current_open = float(market.opens[open_index])
        current_ts = pd.Timestamp(market.open_ts[open_index])
        if open_index > start_open and side != 0:
            price_return = current_open / previous_open - 1.0
            equity *= 1.0 + side * price_return
            funding_amount = equity * side * float(market.funding_by_open[open_index])
            equity -= funding_amount
            total_funding += funding_amount
            exposure_days += 1

        action = pending
        pending = None
        suppress_episode: str | None = None
        if side != 0 and open_index == terminal_open:
            action = action or {"target": 0, "reason": "terminal_mark"}
        if side != 0 and action is not None:
            old_side = side
            target = int(action["target"])
            close_trade(open_index, str(action["reason"]), action)
            if target != 0 and open_index < terminal_open:
                candidate = action["candidate"]
                open_trade(open_index, candidate, float(action["opposite_probability"]))
                reversal_count += int(target == -old_side)
            else:
                suppress_episode = action.get("suppress_episode")

        decision_index = open_index - 1
        today_candidates = candidate_map.get(decision_index, [])
        if side == 0 and open_index < terminal_open:
            available = [
                row
                for row in today_candidates
                if str(row["episode_id"]) not in used_episodes
                and str(row["episode_id"]) != suppress_episode
                and (strategy != "RAW_CROSS_H7" or int(row["episode_age"]) == 0)
            ]
            if available:
                candidate = available[0]
                p_entry = None if strategy == "RAW_CROSS_H7" else probability(entry_model, candidate)
                accepted = p_entry is None or p_entry >= ENTRY_THRESHOLD
                decisions.append(
                    {
                        "strategy": strategy,
                        "kind": "entry",
                        "decision_ts": candidate["decision_ts"],
                        "action_ts": current_ts.isoformat(),
                        "episode_id": candidate["episode_id"],
                        "episode_age": candidate["episode_age"],
                        "side": candidate["side"],
                        "probability": p_entry,
                        "accepted": accepted,
                    }
                )
                if accepted:
                    open_trade(open_index, candidate, p_entry)

        if side != 0 and open_index < len(state) and entry_candidate is not None:
            hold_days = open_index - entry_index + 1
            if strategy == "RAW_CROSS_H7":
                if hold_days >= 7:
                    pending = {"target": 0, "reason": "fixed_7d"}
            else:
                survival_features = survival_feature_row(
                    state,
                    market,
                    entry_open_index=entry_index,
                    decision_index=open_index,
                    side=side,
                    entry_atr=entry_atr,
                )
                p_survival = probability(survival_model, survival_features)
                opposite = next(
                    (
                        row
                        for row in candidate_map.get(open_index, [])
                        if int(row["side_value"]) == -side
                        and str(row["episode_id"]) not in used_episodes
                    ),
                    None,
                )
                p_opposite = probability(entry_model, opposite) if opposite is not None else None
                reversal_ready = bool(
                    opposite is not None
                    and p_opposite is not None
                    and p_opposite >= ENTRY_THRESHOLD
                    and p_opposite >= p_survival + REVERSAL_MARGIN
                )
                reason: str | None = None
                target = side
                if hold_days >= MAX_HOLD_DAYS:
                    reason, target = "max_hold_30d", 0
                elif reversal_ready and strategy == "P2_FULL_POLICY":
                    reason, target = "direct_reversal", -side
                elif reversal_ready and strategy == "P2_NO_REVERSAL":
                    reason, target = "opposite_episode_exit", 0
                elif p_survival < EXIT_THRESHOLD:
                    reason, target = "survival_exit", 0
                decisions.append(
                    {
                        "strategy": strategy,
                        "kind": "hold",
                        "decision_ts": pd.Timestamp(state.iloc[open_index]["ts"]).isoformat(),
                        "action_ts": pd.Timestamp(market.open_ts[open_index + 1]).isoformat(),
                        "episode_id": entry_candidate["episode_id"],
                        "episode_age": hold_days,
                        "side": "long" if side > 0 else "short",
                        "survival_probability": p_survival,
                        "opposite_episode_id": opposite["episode_id"] if opposite else None,
                        "opposite_probability": p_opposite,
                        "action": reason or "hold",
                    }
                )
                if reason is not None:
                    pending = {
                        "target": target,
                        "reason": reason,
                        "survival_probability": p_survival,
                        "opposite_probability": p_opposite,
                        "opposite_cross_index": (
                            int(opposite["cross_decision_index"]) if opposite else None
                        ),
                        "candidate": opposite,
                        "suppress_episode": (
                            opposite["episode_id"]
                            if opposite is not None and strategy == "P2_NO_REVERSAL"
                            else None
                        ),
                    }

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

    trade_returns = np.asarray([row["net_return"] for row in trades], dtype=float)
    capture_values = [row["capture_ratio"] for row in trades if row["gross_favorable_return"] > 0]
    metrics = {
        "total_return": float(equity - 1.0),
        "max_drawdown": float(mdd),
        "profit_factor": _profit_factor(trades),
        "win_rate": float(np.mean(trade_returns > 0.0)) if len(trade_returns) else 0.0,
        "trade_count": len(trades),
        "long_count": sum(int(row["side_value"]) > 0 for row in trades),
        "short_count": sum(int(row["side_value"]) < 0 for row in trades),
        "reversal_count": reversal_count,
        "exposure_days": exposure_days,
        "total_cost": float(total_cost),
        "total_funding": float(total_funding),
        "mean_capture_ratio_profitable": float(np.mean(capture_values)) if capture_values else 0.0,
        "mean_remaining_mfe_14_atr": float(np.mean([row["remaining_mfe_14_atr"] for row in trades])) if trades else 0.0,
        "final_equity": float(equity),
    }
    return BacktestResult(metrics=metrics, trades=trades, path=path, decisions=decisions)


def recent_slices(path: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(path)
    output: dict[str, Any] = {}
    for name, days in {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}.items():
        part = frame.tail(min(days + 1, len(frame)))
        start = float(part["equity"].iloc[0])
        peak = part["equity"].cummax()
        output[name] = {
            "available_days": len(part) - 1,
            "return": float(part["equity"].iloc[-1] / start - 1.0),
            "max_drawdown": float((part["equity"] / peak - 1.0).min()),
        }
    return output


def coefficients(bundle: ModelBundle) -> list[dict[str, Any]]:
    if not isinstance(bundle.model, Pipeline):
        return [{"feature": "constant", "coefficient": 0.0}]
    values = bundle.model.named_steps["model"].coef_[0]
    return sorted(
        [
            {"feature": name, "coefficient": float(value)}
            for name, value in zip(bundle.features, values, strict=True)
        ],
        key=lambda row: abs(row["coefficient"]),
        reverse=True,
    )


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


def verdict(results: dict[str, BacktestResult], p1_summary: dict[str, Any]) -> str:
    full = results["P2_FULL_POLICY"].metrics
    no_reverse = results["P2_NO_REVERSAL"].metrics
    p1 = p1_summary["validation"]["ML_ENTRY_DYNAMIC_EXIT"]
    if full["total_return"] > float(p1["total_return"]) and full["reversal_count"] > 0:
        return "EDUCATIONAL_IMPROVEMENT"
    if full["total_return"] > no_reverse["total_return"] or full["reversal_count"] > 0:
        return "EDUCATIONAL_MIXED"
    return "EDUCATIONAL_FAILURE"


def write_outputs(
    run_date: str,
    market: Any,
    candidates: pd.DataFrame,
    train_candidates: pd.DataFrame,
    validation_candidates: pd.DataFrame,
    survival_rows: pd.DataFrame,
    entry_model: ModelBundle,
    survival_model: ModelBundle,
    entry_oof: dict[str, Any],
    survival_oof: dict[str, Any],
    results: dict[str, BacktestResult],
    p1_summary: dict[str, Any],
) -> dict[str, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_ma7_mlt_p2_episode_policy_{run_date}"
    paths = {
        "summary": ARTIFACT_DIR / f"{stem}_summary.json",
        "episode_candidates": ARTIFACT_DIR / f"{stem}_episode_candidates.csv",
        "survival_training_rows": ARTIFACT_DIR / f"{stem}_survival_training_rows.csv",
        "validation_trades": ARTIFACT_DIR / f"{stem}_validation_trades.csv",
        "validation_path": ARTIFACT_DIR / f"{stem}_validation_path.csv",
        "validation_decisions": ARTIFACT_DIR / f"{stem}_validation_decisions.csv",
        "model_manifest": ARTIFACT_DIR / f"{stem}_model_manifest.json",
    }
    output_candidates = candidates.copy()
    output_candidates["split"] = np.where(
        output_candidates["decision_index"] < TRAIN_DAYS - 1,
        "train",
        "validation",
    )
    output_candidates["entry_probability"] = [
        probability(entry_model, row)
        if int(row["decision_index"]) >= TRAIN_DAYS - 1
        else math.nan
        for row in output_candidates.to_dict("records")
    ]
    output_candidates.to_csv(paths["episode_candidates"], index=False)
    survival_rows.to_csv(paths["survival_training_rows"], index=False)
    trades = pd.concat([pd.DataFrame(result.trades) for result in results.values()], ignore_index=True)
    trades.to_csv(paths["validation_trades"], index=False)
    path_frames = []
    decision_frames = []
    for strategy, result in results.items():
        frame = pd.DataFrame(result.path)
        frame.insert(0, "strategy", strategy)
        path_frames.append(frame)
        decision_frames.append(pd.DataFrame(result.decisions))
    pd.concat(path_frames, ignore_index=True).to_csv(paths["validation_path"], index=False)
    pd.concat(decision_frames, ignore_index=True).to_csv(paths["validation_decisions"], index=False)
    manifest = {
        "entry_model": {
            "C": MODEL_C,
            "threshold": ENTRY_THRESHOLD,
            "features": ENTRY_FEATURES,
            "training_rows": entry_model.row_count,
            "training_episodes": int(train_candidates["cross_decision_index"].nunique()),
            "positive_rate": entry_model.positive_rate,
            "coefficients": coefficients(entry_model),
            "expanding_group_oof": entry_oof,
        },
        "survival_model": {
            "C": MODEL_C,
            "exit_threshold": EXIT_THRESHOLD,
            "features": SURVIVAL_FEATURES,
            "training_rows": survival_model.row_count,
            "training_episodes": int(survival_rows["cross_decision_index"].nunique()),
            "positive_rate": survival_model.positive_rate,
            "coefficients": coefficients(survival_model),
            "expanding_group_oof": survival_oof,
        },
    }
    paths["model_manifest"].write_text(
        json.dumps(json_ready(manifest), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": run_date,
        "status": "post-reveal educational replay / diagnostic-only / not promoted / not live-ready",
        "verdict": verdict(results, p1_summary),
        "research_conclusion": "BEHAVIOR_IMPROVED_BUT_MODEL_GENERALIZATION_FAILED",
        "contract": str((FAMILY_DIR / "specs/hype-1d-ma7-mlt-p2-episode-policy-learning-contract-2026-08-27.md").relative_to(ROOT)),
        "data": {
            "daily_rows": len(market.daily),
            "train_rows": TRAIN_DAYS,
            "validation_rows": len(market.daily) - TRAIN_DAYS,
            "validation_first_ts": market.daily["ts"].iloc[TRAIN_DAYS],
            "validation_last_ts": market.daily["ts"].iloc[-1],
            "terminal_open_ts": market.open_ts[-1],
        },
        "episode": {
            "max_age": EPISODE_MAX_AGE,
            "all_raw_crosses": int(candidates["cross_decision_index"].nunique()),
            "all_candidate_rows": len(candidates),
            "train_complete_episodes": int(train_candidates["cross_decision_index"].nunique()),
            "train_complete_candidate_rows": len(train_candidates),
            "validation_episodes": int(validation_candidates["cross_decision_index"].nunique()),
            "validation_candidate_rows": len(validation_candidates),
        },
        "models": manifest,
        "validation": {
            strategy: {**result.metrics, "recent_slices": recent_slices(result.path)}
            for strategy, result in results.items()
        },
        "references": {
            "p1_ml": p1_summary["validation"]["ML_ENTRY_DYNAMIC_EXIT"],
            "v7_1_descriptive": p1_summary["v7_1_descriptive_reference"],
        },
        "limitations": [
            "explicit post-reveal educational replay",
            "episode-day and survival rows are correlated within a small number of raw-cross episodes",
            "daily-close decisions have no intraday protective stop",
            "no P2 setting may be retuned on this replay result",
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
    assert EPISODE_MAX_AGE == 6
    assert len(ENTRY_FEATURES) == 16
    assert len(SURVIVAL_FEATURES) == 16
    frame = pd.DataFrame({"x": [-2.0, -1.0, 1.0, 2.0], "y": [0, 0, 1, 1]})
    bundle = fit_model(frame, ["x"], "y")
    assert probability(bundle, {"x": 2.0}) > probability(bundle, {"x": -2.0})


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("self-test PASS")
        return
    _, _, market, state = load_context()
    candidates = add_entry_labels(build_episode_candidates(state, market), market)
    train_candidates = candidates.loc[
        (candidates["entry_open_index"] + ENTRY_LABEL_HORIZON <= TRAIN_DAYS - 1)
        & candidates["entry_label_complete"]
    ].copy()
    validation_candidates = candidates.loc[
        (candidates["decision_index"] >= TRAIN_DAYS - 1)
        & (candidates["decision_index"] < len(market.daily) - 1)
    ].copy()
    if train_candidates["trend_success"].nunique() < 2:
        raise RuntimeError("entry labels lack both classes")
    survival_rows = build_survival_rows(train_candidates, state, market)
    if survival_rows["survival_label"].nunique() < 2:
        raise RuntimeError("survival labels lack both classes")
    entry_model = fit_model(train_candidates, ENTRY_FEATURES, "trend_success")
    survival_model = fit_model(survival_rows, SURVIVAL_FEATURES, "survival_label")
    entry_oof = expanding_group_oof(train_candidates, ENTRY_FEATURES, "trend_success")
    survival_oof = expanding_group_oof(survival_rows, SURVIVAL_FEATURES, "survival_label")
    results = {
        strategy: backtest_policy(
            state,
            market,
            validation_candidates,
            entry_model,
            survival_model,
            strategy=strategy,
        )
        for strategy in ("P2_FULL_POLICY", "P2_NO_REVERSAL", "RAW_CROSS_H7")
    }
    p1_summary = json.loads(P1_SUMMARY.read_text(encoding="utf-8"))
    paths = write_outputs(
        args.run_date,
        market,
        candidates,
        train_candidates,
        validation_candidates,
        survival_rows,
        entry_model,
        survival_model,
        entry_oof,
        survival_oof,
        results,
        p1_summary,
    )
    print(
        json.dumps(
            json_ready(
                {
                    "episodes": {
                        "train": int(train_candidates["cross_decision_index"].nunique()),
                        "train_rows": len(train_candidates),
                        "validation": int(validation_candidates["cross_decision_index"].nunique()),
                        "validation_rows": len(validation_candidates),
                    },
                    "survival_rows": len(survival_rows),
                    "entry_oof": entry_oof,
                    "survival_oof": survival_oof,
                    "validation": {key: result.metrics for key, result in results.items()},
                    "verdict": verdict(results, p1_summary),
                    "summary": str(paths["summary"]),
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
