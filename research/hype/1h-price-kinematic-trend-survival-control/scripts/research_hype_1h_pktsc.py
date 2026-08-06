from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path("research/hype/1h-price-kinematic-trend-survival-control")
ARTIFACT_DIR = ROOT / "artifacts"
DATA_SCRIPT = Path(
    "research/hype/15m-multidimensional-trend-pyramiding/scripts/"
    "research_hype_15m_mdtp.py"
)
SYMBOL = "HYPE/USDT:USDT"
RUN_DATE = "2026-08-03"
WF_START = pd.Timestamp("2025-09-01 00:00:00+00:00")
PROSPECTIVE_START = pd.Timestamp("2026-08-02 00:00:00+00:00")
PROSPECTIVE_END = pd.Timestamp("2026-11-02 00:00:00+00:00")
PAST_WINDOWS = (6, 24, 72, 168, 336)
FUTURE_HORIZONS = (24, 72, 168, 336)
DIRECTION_WINDOW = 24
ACCELERATION_PAIRS = ((6, 24), (24, 72), (72, 168), (168, 336))
MIN_TRAIN_ROWS = 300
RIDGE_ALPHA = 10.0
LOGIT_C = 0.1
FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
RISK_FRACTION = 0.01
DISASTER_FRACTION = 0.03
MAX_LEVERAGE = 3.0
BOOTSTRAP_SAMPLES = 5_000
BLOCK_HOURS = 14 * 24
EPSILON = 1e-12

BASELINE_FEATURES = tuple(f"dir_velocity_{window}" for window in PAST_WINDOWS)
FULL_FEATURES = (
    *BASELINE_FEATURES,
    *(f"path_speed_{window}" for window in PAST_WINDOWS),
    *(f"coherence_{window}" for window in PAST_WINDOWS),
    *(f"burst_{window}" for window in PAST_WINDOWS),
    *(f"noise_{window}" for window in PAST_WINDOWS),
    *(f"roughness_{window}" for window in PAST_WINDOWS),
    *(f"dir_acceleration_{short}_{long}" for short, long in ACCELERATION_PAIRS),
    "scale_alignment",
    "direction_age_scaled",
    "episode_progress_z",
    "episode_peak_z",
    "episode_giveback_share",
)


@dataclass(frozen=True, slots=True)
class PolicyResult:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    actions: pd.DataFrame
    equity: pd.Series


def load_data_module() -> Any:
    spec = importlib.util.spec_from_file_location("hype_pktsc_data", DATA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data module: {DATA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_data() -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    module = load_data_module()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, funding, quality = module.load_symbol_data(
        warehouse, SYMBOL, require_raw_parity=True
    )
    if frame.index.max() >= PROSPECTIVE_START:
        raise RuntimeError("prospective OOS is present; refuse to compute")
    return frame, funding, quality


def build_complete_hourly(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    grouped = frame.resample("1h", label="left", closed="left")
    hourly = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_bars=("close", "count"),
    )
    incomplete = hourly.loc[hourly["source_bars"].ne(4)]
    hourly = hourly.loc[hourly["source_bars"].eq(4)].copy()
    expected = pd.date_range(
        hourly.index.min(), hourly.index.max(), freq="1h", tz="UTC"
    )
    missing = expected.difference(hourly.index)
    invalid = hourly["high"].lt(
        hourly[["open", "close", "low"]].max(axis=1)
    ) | hourly["low"].gt(hourly[["open", "close", "high"]].min(axis=1))
    quality = {
        "execution_rows": int(len(hourly)),
        "execution_start": hourly.index.min().isoformat(),
        "execution_end": hourly.index.max().isoformat(),
        "incomplete_source_hours": int(len(incomplete)),
        "missing_complete_hours": int(len(missing)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "accepted": bool(len(missing) == 0 and int(invalid.sum()) == 0),
        "availability_semantics": (
            "execution bars keep open timestamps; feature bars shift plus one hour"
        ),
    }
    if not quality["accepted"]:
        raise RuntimeError(f"hourly data blocker: {quality}")
    visible = hourly.copy()
    visible.index = visible.index + pd.Timedelta(hours=1)
    return hourly, visible, quality


def _roughness(values: np.ndarray) -> float:
    if not np.isfinite(values).all() or len(values) < 2:
        return math.nan
    path = float(np.abs(np.diff(values)).sum())
    if path <= EPSILON:
        return 0.0
    line = np.linspace(values[0], values[-1], len(values))
    return float(np.sqrt(np.mean(np.square(values - line))) / path)


def build_price_state(visible: pd.DataFrame) -> pd.DataFrame:
    state = pd.DataFrame(index=visible.index)
    state["log_price"] = np.log(visible["close"].astype(float))
    state["step"] = state["log_price"].diff()
    absolute = state["step"].abs()
    squared = state["step"].pow(2)
    for window in PAST_WINDOWS:
        displacement = state["log_price"] - state["log_price"].shift(window)
        path = absolute.rolling(window, min_periods=window).sum()
        state[f"velocity_{window}"] = displacement / window
        state[f"path_speed_{window}"] = path / window
        state[f"coherence_{window}"] = displacement.abs() / (path + EPSILON)
        state[f"burst_{window}"] = (
            absolute.rolling(window, min_periods=window).max() / (path + EPSILON)
        )
        state[f"noise_{window}"] = np.sqrt(
            squared.rolling(window, min_periods=window).mean()
        )
        state[f"roughness_{window}"] = (
            state["log_price"]
            .rolling(window + 1, min_periods=window + 1)
            .apply(_roughness, raw=True)
        )
    state["direction"] = np.sign(
        state["log_price"] - state["log_price"].shift(DIRECTION_WINDOW)
    )
    for window in PAST_WINDOWS:
        state[f"dir_velocity_{window}"] = (
            state["direction"] * state[f"velocity_{window}"]
        )
    for short, long in ACCELERATION_PAIRS:
        state[f"dir_acceleration_{short}_{long}"] = (
            state["direction"]
            * (state[f"velocity_{short}"] - state[f"velocity_{long}"])
            / (long - short)
        )
    aligned = [
        np.sign(state[f"velocity_{window}"]).eq(state["direction"])
        for window in PAST_WINDOWS
    ]
    state["scale_alignment"] = sum(item.astype(int) for item in aligned)
    slow = [
        np.sign(state[f"velocity_{window}"]).eq(state["direction"])
        for window in (24, 72, 168)
    ]
    state["slow_alignment"] = sum(item.astype(int) for item in slow)
    change = state["direction"].ne(state["direction"].shift())
    episode = change.cumsum()
    age = state.groupby(episode).cumcount() + 1
    start = state["log_price"].groupby(episode).transform("first")
    progress = state["direction"] * (state["log_price"] - start)
    peak = progress.groupby(episode).cummax().clip(lower=0.0)
    scale = state["noise_336"] * np.sqrt(age.clip(upper=336))
    state["direction_age_scaled"] = age.clip(upper=336) / 336.0
    state["episode_progress_z"] = progress / (scale + EPSILON)
    state["episode_peak_z"] = peak / (scale + EPSILON)
    state["episode_giveback_share"] = (peak - progress) / (peak + EPSILON)
    state["stop_distance_log"] = (
        state["noise_168"].mul(math.sqrt(24.0)).clip(lower=0.01)
    )
    state["is_anchor"] = state.index.hour.isin((0, 4, 8, 12, 16, 20))
    return state


def add_future_labels(
    state: pd.DataFrame, horizons: Iterable[int] = FUTURE_HORIZONS
) -> pd.DataFrame:
    labelled = state.copy()
    price = labelled["log_price"].to_numpy(float)
    direction = labelled["direction"].to_numpy(float)
    noise = labelled["noise_336"].to_numpy(float)
    count = len(labelled)
    for horizon in horizons:
        future_z = np.full(count, np.nan)
        continuation = np.full(count, np.nan)
        mfe = np.full(count, np.nan)
        mae = np.full(count, np.nan)
        first_passage = np.full(count, np.nan)
        for index in range(count - horizon):
            side = direction[index]
            scale = noise[index] * math.sqrt(horizon)
            if side == 0.0 or not np.isfinite(scale) or scale <= EPSILON:
                continue
            path = side * (price[index + 1 : index + horizon + 1] - price[index])
            if not np.isfinite(path).all():
                continue
            final = float(path[-1])
            plus = np.flatnonzero(path >= scale)
            minus = np.flatnonzero(path <= -scale)
            passage = 0.0
            if plus.size and (not minus.size or plus[0] < minus[0]):
                passage = 1.0
            elif minus.size and (not plus.size or minus[0] < plus[0]):
                passage = -1.0
            future_z[index] = final / scale
            continuation[index] = float(final > 0.0)
            mfe[index] = max(0.0, float(path.max()))
            mae[index] = max(0.0, float((-path).max()))
            first_passage[index] = passage
        labelled[f"future_z_{horizon}"] = future_z
        labelled[f"continuation_{horizon}"] = continuation
        labelled[f"mfe_{horizon}"] = mfe
        labelled[f"mae_{horizon}"] = mae
        labelled[f"first_passage_{horizon}"] = first_passage
    return labelled


def _fit_models(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Iterable[str],
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    columns = list(features)
    target = f"future_z_{horizon}"
    binary = f"continuation_{horizon}"
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
    logit = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=LOGIT_C, max_iter=2_000, solver="lbfgs"),
    )
    ridge.fit(train[columns], train[target])
    logit.fit(train[columns], train[binary].astype(int))
    return ridge.predict(test[columns]), logit.predict_proba(test[columns])[:, 1]


def build_prequential_predictions(
    labelled: pd.DataFrame, horizons: Iterable[int] = FUTURE_HORIZONS
) -> pd.DataFrame:
    anchors = labelled.loc[labelled["is_anchor"]].copy()
    rows: list[dict[str, Any]] = []
    test_days = pd.date_range(
        WF_START.normalize(),
        PROSPECTIVE_START.normalize(),
        freq="1D",
        inclusive="left",
        tz="UTC",
    )
    for horizon in horizons:
        target = f"future_z_{horizon}"
        binary = f"continuation_{horizon}"
        required = list(dict.fromkeys([*FULL_FEATURES, target, binary]))
        available = anchors.dropna(subset=required)
        for day in test_days:
            test_end = day + pd.Timedelta(days=1)
            cutoff = day - pd.Timedelta(hours=horizon)
            for side, direction_name in ((1, "long"), (-1, "short")):
                train = available.loc[
                    (available.index < cutoff) & available["direction"].eq(side)
                ]
                test = available.loc[
                    (available.index >= day)
                    & (available.index < test_end)
                    & available["direction"].eq(side)
                ]
                if (
                    len(train) < MIN_TRAIN_ROWS
                    or test.empty
                    or train[binary].nunique() < 2
                ):
                    continue
                base_z, base_p = _fit_models(
                    train, test, BASELINE_FEATURES, horizon
                )
                full_z, full_p = _fit_models(train, test, FULL_FEATURES, horizon)
                constant = float(train[binary].mean())
                for position, (timestamp, row) in enumerate(test.iterrows()):
                    rows.append(
                        {
                            "ts": timestamp,
                            "direction": direction_name,
                            "side": side,
                            "horizon_hours": horizon,
                            "actual_z": float(row[target]),
                            "actual_continuation": int(row[binary]),
                            "baseline_z_pred": float(base_z[position]),
                            "baseline_prob": float(base_p[position]),
                            "full_z_pred": float(full_z[position]),
                            "full_prob": float(full_p[position]),
                            "constant_prob": constant,
                            "slow_alignment": int(row["slow_alignment"]),
                            "stop_distance_log": float(row["stop_distance_log"]),
                        }
                    )
    return pd.DataFrame(rows).sort_values(["ts", "horizon_hours", "side"])


def _safe_ic(predicted: pd.Series, actual: pd.Series) -> float:
    if len(actual) < 3 or predicted.std(ddof=0) <= EPSILON:
        return math.nan
    return float(spearmanr(predicted, actual, nan_policy="omit").statistic)


def prediction_metric_row(
    frame: pd.DataFrame,
    *,
    direction: str,
    horizon: int,
    period: str,
    model: str,
) -> dict[str, Any]:
    z_column = f"{model}_z_pred"
    p_column = f"{model}_prob"
    actual_binary = frame["actual_continuation"].astype(int)
    auc = (
        float(roc_auc_score(actual_binary, frame[p_column]))
        if actual_binary.nunique() > 1
        else math.nan
    )
    return {
        "direction": direction,
        "horizon_hours": horizon,
        "period": period,
        "model": model,
        "samples": int(len(frame)),
        "ridge_ic": _safe_ic(frame[z_column], frame["actual_z"]),
        "logit_auc": auc,
        "logit_brier": float(brier_score_loss(actual_binary, frame[p_column])),
        "constant_brier": float(
            brier_score_loss(actual_binary, frame["constant_prob"])
        ),
        "continuation_rate": float(actual_binary.mean()),
    }


def continuation_gap_bootstrap(
    frame: pd.DataFrame, seed: int
) -> dict[str, Any]:
    low_edge, high_edge = frame["full_prob"].quantile([0.2, 0.8])
    selected = frame.loc[
        (frame["full_prob"] <= low_edge) | (frame["full_prob"] >= high_edge)
    ].copy()
    selected["prob_bin"] = np.where(selected["full_prob"] >= high_edge, 1, 0)
    origin = selected["ts"].min().floor("D")
    selected["block"] = (
        (selected["ts"] - origin).dt.total_seconds() // (BLOCK_HOURS * 3600)
    ).astype(int)
    blocks = np.sort(selected["block"].unique())
    observed = float(
        selected.loc[selected["prob_bin"].eq(1), "actual_continuation"].mean()
        - selected.loc[selected["prob_bin"].eq(0), "actual_continuation"].mean()
    )
    aggregates = (
        selected.groupby(["block", "prob_bin"])["actual_continuation"]
        .agg(["sum", "count"])
        .reset_index()
    )
    block_position = {int(block): index for index, block in enumerate(blocks)}
    sums = np.zeros((2, len(blocks)), dtype=float)
    counts = np.zeros((2, len(blocks)), dtype=float)
    for row in aggregates.itertuples(index=False):
        position = block_position[int(row.block)]
        bin_id = int(row.prob_bin)
        sums[bin_id, position] = float(row.sum)
        counts[bin_id, position] = float(row.count)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(blocks), size=(BOOTSTRAP_SAMPLES, len(blocks)))
    high_count = counts[1, sampled].sum(axis=1)
    low_count = counts[0, sampled].sum(axis=1)
    valid = (high_count > 0) & (low_count > 0)
    effects = (
        sums[1, sampled].sum(axis=1)[valid] / high_count[valid]
        - sums[0, sampled].sum(axis=1)[valid] / low_count[valid]
    )
    return {
        "observed_gap": observed,
        "ci_low": float(np.quantile(effects, 0.025)),
        "ci_high": float(np.quantile(effects, 0.975)),
        "independent_blocks": int(len(blocks)),
    }


def evaluate_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    overall_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    gates: dict[str, Any] = {}
    for direction_index, direction in enumerate(("long", "short")):
        direction_frame = predictions.loc[predictions["direction"].eq(direction)]
        for horizon in FUTURE_HORIZONS:
            frame = direction_frame.loc[
                direction_frame["horizon_hours"].eq(horizon)
            ]
            for model in ("baseline", "full"):
                overall_rows.append(
                    prediction_metric_row(
                        frame,
                        direction=direction,
                        horizon=horizon,
                        period="historical_prequential",
                        model=model,
                    )
                )
            if horizon == 24:
                months = frame["ts"].dt.strftime("%Y-%m")
                for month, group in frame.groupby(months):
                    if len(group) < 30:
                        continue
                    monthly_rows.append(
                        prediction_metric_row(
                            group,
                            direction=direction,
                            horizon=horizon,
                            period=str(month),
                            model="full",
                        )
                    )
        overall = pd.DataFrame(overall_rows)
        selected = overall.loc[overall["direction"].eq(direction)]
        full = selected.loc[selected["model"].eq("full")].set_index("horizon_hours")
        baseline = selected.loc[selected["model"].eq("baseline")].set_index(
            "horizon_hours"
        )
        monthly = pd.DataFrame(monthly_rows)
        direction_monthly = monthly.loc[monthly["direction"].eq(direction)]
        gap = continuation_gap_bootstrap(
            direction_frame.loc[direction_frame["horizon_hours"].eq(24)],
            seed=20260803 + direction_index,
        )
        positive_ic = int(full["ridge_ic"].gt(0.0).sum())
        useful_logit = int(
            (
                full["logit_auc"].gt(0.5)
                & full["logit_brier"].le(full["constant_brier"])
            ).sum()
        )
        positive_months = int(direction_monthly["ridge_ic"].gt(0.0).sum())
        valid_months = int(len(direction_monthly))
        min_samples = int(full["samples"].min())
        longest = direction_frame.loc[
            direction_frame["horizon_hours"].eq(max(FUTURE_HORIZONS))
        ]
        independent_long_blocks = int(
            ((longest["ts"].max() - longest["ts"].min()).total_seconds())
            // (BLOCK_HOURS * 3600)
        )
        gate = {
            "positive_full_ic_at_least_3_of_4": positive_ic >= 3,
            "median_full_ic_not_worse_than_baseline": bool(
                full["ridge_ic"].median() >= baseline["ridge_ic"].median()
            ),
            "useful_full_logit_at_least_3_of_4": useful_logit >= 3,
            "positive_24h_ic_in_at_least_60pct_months": bool(
                valid_months >= 6 and positive_months / valid_months >= 0.60
            ),
            "24h_probability_gap_ci_low_positive": gap["ci_low"] > 0.0,
            "at_least_20_independent_14d_blocks": independent_long_blocks >= 20,
            "at_least_100_observations_each_horizon": min_samples >= 100,
            "details": {
                "positive_ic_horizons": positive_ic,
                "useful_logit_horizons": useful_logit,
                "positive_months": positive_months,
                "valid_months": valid_months,
                "minimum_observations": min_samples,
                "independent_long_horizon_blocks": independent_long_blocks,
                "probability_gap": gap,
            },
        }
        gate["continuation_prediction_supported"] = all(
            value for key, value in gate.items() if key != "details"
        )
        gates[direction] = gate
    return pd.DataFrame(overall_rows), pd.DataFrame(monthly_rows), gates


def desired_dynamic_fraction(probability: float, peak_move: float, risk_move: float, profitable: bool) -> float:
    if probability < 0.55:
        return 0.35
    if probability >= 0.62 and peak_move >= 2.0 * risk_move and profitable:
        return 1.00
    if probability >= 0.60 and peak_move >= risk_move and profitable:
        return 0.85
    if probability >= 0.57 and profitable:
        return 0.70
    return 0.35


def build_campaign_schedule(
    hourly: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    side: int,
    use_mfe_floor: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    p24 = predictions.loc[predictions["horizon_hours"].eq(24)].set_index("ts")
    event_map = {timestamp: row for timestamp, row in p24.iterrows()}
    selected = hourly.loc[
        (hourly.index >= WF_START) & (hourly.index < PROSPECTIVE_START)
    ]
    actions: list[dict[str, Any]] = []
    campaigns: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    campaign_id = 0
    exited_at_open = False

    def exit_campaign(
        timestamp: pd.Timestamp, raw_price: float, reason: str, *, gap: bool = False
    ) -> None:
        nonlocal active
        if active is None:
            return
        exit_move = active["side"] * math.log(raw_price / active["entry_price"])
        capture = (
            exit_move / active["peak_move"]
            if active["peak_move"] > EPSILON
            else math.nan
        )
        actions.append(
            {
                "ts": timestamp,
                "campaign_id": active["campaign_id"],
                "action": "exit",
                "raw_price": raw_price,
                "dynamic_fraction": 0.0,
                "active_stop": active["stop"],
                "reason": reason,
            }
        )
        campaigns.append(
            {
                "campaign_id": active["campaign_id"],
                "side": active["side"],
                "entry_ts": active["entry_ts"],
                "exit_ts": timestamp,
                "entry_price": active["entry_price"],
                "exit_raw_price": raw_price,
                "exit_reason": reason,
                "hold_hours": (timestamp - active["entry_ts"]).total_seconds() / 3600,
                "risk_move_log": active["risk_move"],
                "peak_move_log": active["peak_move"],
                "exit_move_log": exit_move,
                "price_capture_ratio": capture,
                "reached_2r": active["peak_move"] >= 2.0 * active["risk_move"],
                "gap_exit": gap,
                "half_mfe_retained": bool(
                    active["peak_move"] < 2.0 * active["risk_move"]
                    or gap
                    or exit_move + 1e-12 >= 0.5 * active["peak_move"]
                ),
            }
        )
        active = None

    for timestamp, bar in selected.iterrows():
        raw_open = float(bar["open"])
        raw_high = float(bar["high"])
        raw_low = float(bar["low"])
        exited_at_open = False
        if active is not None:
            gap_hit = (side > 0 and raw_open <= active["stop"]) or (
                side < 0 and raw_open >= active["stop"]
            )
            if gap_hit:
                exit_campaign(timestamp, raw_open, "protective_gap", gap=True)
                exited_at_open = True
        event = event_map.get(timestamp)
        if active is not None and event is not None:
            if int(event["side"]) != side or float(event["full_prob"]) < 0.50:
                exit_campaign(timestamp, raw_open, "probability_or_direction_exit")
                exited_at_open = True
            else:
                profitable = side * math.log(raw_open / active["entry_price"]) > 0.0
                fraction = desired_dynamic_fraction(
                    float(event["full_prob"]),
                    float(active["peak_move"]),
                    float(active["risk_move"]),
                    profitable,
                )
                if abs(fraction - active["dynamic_fraction"]) > 1e-12:
                    active["dynamic_fraction"] = fraction
                    actions.append(
                        {
                            "ts": timestamp,
                            "campaign_id": active["campaign_id"],
                            "action": "update",
                            "raw_price": raw_open,
                            "dynamic_fraction": fraction,
                            "active_stop": active["stop"],
                            "reason": "probability_layer_update",
                        }
                    )
        if active is None and not exited_at_open and event is not None:
            qualifies = (
                int(event["side"]) == side
                and int(event["slow_alignment"]) == 3
                and float(event["full_prob"]) >= 0.55
                and float(event["full_z_pred"]) > 0.0
            )
            if qualifies:
                campaign_id += 1
                risk_move = float(event["stop_distance_log"])
                stop = raw_open * math.exp(-side * risk_move)
                active = {
                    "campaign_id": campaign_id,
                    "side": side,
                    "entry_ts": timestamp,
                    "entry_price": raw_open,
                    "risk_move": risk_move,
                    "stop": stop,
                    "peak_move": 0.0,
                    "dynamic_fraction": 0.35,
                }
                actions.append(
                    {
                        "ts": timestamp,
                        "campaign_id": campaign_id,
                        "action": "entry",
                        "raw_price": raw_open,
                        "dynamic_fraction": 0.35,
                        "active_stop": stop,
                        "reason": "frozen_price_state_entry",
                    }
                )
        if active is None:
            continue
        stop_hit = (side > 0 and raw_low <= active["stop"]) or (
            side < 0 and raw_high >= active["stop"]
        )
        if stop_hit:
            exit_campaign(timestamp, float(active["stop"]), "protective_stop")
            continue
        favorable = raw_high if side > 0 else raw_low
        favorable_move = side * math.log(favorable / active["entry_price"])
        active["peak_move"] = max(float(active["peak_move"]), favorable_move)
        if use_mfe_floor and active["peak_move"] >= 2.0 * active["risk_move"]:
            floor = active["entry_price"] * math.exp(side * 0.5 * active["peak_move"])
            tightened = (
                max(active["stop"], floor) if side > 0 else min(active["stop"], floor)
            )
            if abs(tightened - active["stop"]) > 1e-12:
                active["stop"] = tightened
                actions.append(
                    {
                        "ts": timestamp + pd.Timedelta(hours=1),
                        "campaign_id": active["campaign_id"],
                        "action": "stop_update",
                        "raw_price": math.nan,
                        "dynamic_fraction": active["dynamic_fraction"],
                        "active_stop": tightened,
                        "reason": "half_mfe_floor_update",
                    }
                )
    if active is not None:
        timestamp = pd.Timestamp(selected.index[-1])
        exit_campaign(timestamp, float(selected["close"].iloc[-1]), "terminal_flatten")
    return pd.DataFrame(actions), pd.DataFrame(campaigns)


def adverse_fill(raw_price: float, delta_quantity: float, slippage: float) -> float:
    return raw_price * (1.0 + math.copysign(slippage, delta_quantity))


def simulate_policy(
    hourly: pd.DataFrame,
    funding: pd.Series,
    schedule: pd.DataFrame,
    campaigns: pd.DataFrame,
    *,
    policy: str,
    fee_rate: float = FEE_RATE,
    slippage: float = BASE_SLIPPAGE,
) -> PolicyResult:
    selected = hourly.loc[
        (hourly.index >= WF_START) & (hourly.index < PROSPECTIVE_START)
    ]
    schedule_map = {
        timestamp: group.to_dict(orient="records")
        for timestamp, group in schedule.groupby("ts", sort=False)
    }
    campaign_map = campaigns.set_index("campaign_id").to_dict(orient="index")
    equity = 1.0
    quantity = 0.0
    mark_price = float(selected["open"].iloc[0])
    active: dict[str, Any] | None = None
    turnover = fees = slip_cost_total = funding_total = 0.0
    max_fill_leverage = max_effective_leverage = max_open_risk = 0.0
    risk_breaches = 0
    action_counts: dict[str, int] = {}
    action_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    curve: list[float] = []
    curve_index: list[pd.Timestamp] = []
    peak_equity = 1.0
    conservative_mdd = 0.0

    def mark_to(price: float) -> None:
        nonlocal equity, mark_price
        equity += quantity * (price - mark_price)
        mark_price = price

    def trade_to(target: float, raw_price: float, action: str, timestamp: pd.Timestamp) -> None:
        nonlocal equity, quantity, turnover, fees, slip_cost_total
        nonlocal max_fill_leverage
        mark_to(raw_price)
        delta = target - quantity
        if abs(delta) <= 1e-14:
            return
        fill = adverse_fill(raw_price, delta, slippage)
        before = max(equity, EPSILON)
        slip_cost = abs(delta) * abs(fill - raw_price)
        fee = fee_rate * abs(delta) * fill
        equity -= slip_cost + fee
        slip_cost_total += slip_cost
        fees += fee
        turnover += abs(delta) * fill / before
        old = quantity
        quantity = target
        leverage = abs(quantity) * raw_price / max(equity, EPSILON)
        max_fill_leverage = max(max_fill_leverage, leverage)
        key = action
        if action == "update":
            key = "add" if abs(quantity) > abs(old) else "reduce"
        action_counts[key] = action_counts.get(key, 0) + 1
        action_rows.append(
            {
                "ts": timestamp,
                "campaign_id": None if active is None else active["campaign_id"],
                "action": key,
                "raw_price": raw_price,
                "fill_price": fill,
                "quantity_before": old,
                "quantity_after": quantity,
                "equity_after": equity,
                "leverage_after": leverage,
            }
        )

    for timestamp, bar in selected.iterrows():
        raw_open = float(bar["open"])
        if quantity != 0.0:
            payment = quantity * raw_open * float(funding.get(timestamp, 0.0))
            equity -= payment
            funding_total += payment
        mark_to(raw_open)
        for event in schedule_map.get(timestamp, []):
            campaign_id = int(event["campaign_id"])
            action = str(event["action"])
            if action == "entry":
                info = campaign_map[campaign_id]
                entry_equity = equity
                r0 = RISK_FRACTION * entry_equity
                stop = float(event["active_stop"])
                entry_fill = adverse_fill(raw_open, int(info["side"]), slippage)
                stop_fill = adverse_fill(stop, -int(info["side"]), slippage)
                loss_per_unit = (
                    abs(entry_fill - raw_open)
                    + fee_rate * entry_fill
                    + abs(stop_fill - raw_open)
                    + fee_rate * stop_fill
                )
                full_abs = min(
                    r0 / max(loss_per_unit, EPSILON),
                    MAX_LEVERAGE * entry_equity / raw_open,
                )
                fraction = 1.0 if policy == "static_full" else 0.35
                active = {
                    "campaign_id": campaign_id,
                    "side": int(info["side"]),
                    "entry_equity": entry_equity,
                    "r0": r0,
                    "full_abs": full_abs,
                    "entry_ts": timestamp,
                    "entry_price": raw_open,
                    "stop": stop,
                }
                trade_to(int(info["side"]) * full_abs * fraction, raw_open, "entry", timestamp)
            elif action == "update" and active is not None and policy == "dynamic":
                target_abs = active["full_abs"] * float(event["dynamic_fraction"])
                target_abs = min(target_abs, MAX_LEVERAGE * equity / raw_open)
                if target_abs > abs(quantity):
                    net_now = equity - active["entry_equity"]
                    if net_now <= 0.0:
                        continue
                    stop = active["stop"]

                    def projected_stop_equity(candidate_abs: float) -> float:
                        target = active["side"] * candidate_abs
                        delta = target - quantity
                        fill = adverse_fill(raw_open, delta, slippage)
                        post = (
                            equity
                            - abs(delta) * abs(fill - raw_open)
                            - fee_rate * abs(delta) * fill
                        )
                        exit_fill = adverse_fill(stop, -target, slippage)
                        return (
                            post
                            + target * (exit_fill - raw_open)
                            - fee_rate * abs(target) * exit_fill
                        )

                    minimum = active["entry_equity"] - active["r0"]
                    if projected_stop_equity(target_abs) < minimum:
                        low = abs(quantity)
                        high = target_abs
                        for _ in range(50):
                            middle = 0.5 * (low + high)
                            if projected_stop_equity(middle) >= minimum:
                                low = middle
                            else:
                                high = middle
                        target_abs = low
                trade_to(active["side"] * target_abs, raw_open, "update", timestamp)
            elif action == "stop_update" and active is not None:
                active["stop"] = float(event["active_stop"])
            elif action == "exit" and active is not None:
                before_exit = equity
                trade_to(0.0, float(event["raw_price"]), "exit", timestamp)
                info = campaign_map[campaign_id]
                net_pnl = equity - active["entry_equity"]
                trade_rows.append(
                    {
                        "campaign_id": campaign_id,
                        "side": active["side"],
                        "entry_ts": active["entry_ts"],
                        "exit_ts": timestamp,
                        "hold_hours": info["hold_hours"],
                        "exit_reason": info["exit_reason"],
                        "net_pnl": net_pnl,
                        "net_return": net_pnl / active["entry_equity"],
                        "equity_before_exit": before_exit,
                        "price_capture_ratio": info["price_capture_ratio"],
                        "reached_2r": info["reached_2r"],
                        "half_mfe_retained": info["half_mfe_retained"],
                    }
                )
                active = None
        raw_close = float(bar["close"])
        if quantity != 0.0 and active is not None:
            stop = float(active["stop"])
            exit_fill = adverse_fill(stop, -quantity, slippage)
            stop_equity = (
                equity
                + quantity * (exit_fill - mark_price)
                - fee_rate * abs(quantity) * exit_fill
            )
            open_risk = max(0.0, active["entry_equity"] - stop_equity)
            max_open_risk = max(max_open_risk, open_risk / active["entry_equity"])
            if open_risk > active["r0"] + 1e-9:
                risk_breaches += 1
            adverse = float(bar["low"] if quantity > 0 else bar["high"])
            adverse_equity = equity + quantity * (adverse - mark_price)
            effective = abs(quantity) * adverse / max(adverse_equity, EPSILON)
            max_effective_leverage = max(max_effective_leverage, effective)
            conservative_mdd = min(
                conservative_mdd, adverse_equity / max(peak_equity, EPSILON) - 1.0
            )
        mark_to(raw_close)
        peak_equity = max(peak_equity, equity)
        conservative_mdd = min(
            conservative_mdd, equity / max(peak_equity, EPSILON) - 1.0
        )
        curve.append(equity)
        curve_index.append(timestamp)
    equity_series = pd.Series(curve, index=curve_index, name="equity")
    trades = pd.DataFrame(trade_rows)
    years = max(
        (equity_series.index[-1] - equity_series.index[0]).total_seconds()
        / (365.0 * 86400.0),
        1.0 / 365.0,
    )
    returns = equity_series.pct_change().fillna(equity_series.iloc[0] - 1.0)
    volatility = float(returns.std(ddof=0))
    sharpe = (
        float(returns.mean() / volatility * math.sqrt(365 * 24))
        if volatility > 0.0
        else 0.0
    )
    pnl = trades["net_pnl"] if not trades.empty else pd.Series(dtype=float)
    losses = pnl.loc[pnl < 0.0]
    wins = pnl.loc[pnl > 0.0]
    profit_factor = float(wins.sum() / abs(losses.sum())) if losses.sum() < 0 else math.inf
    metrics = {
        "policy": policy,
        "start": equity_series.index[0].isoformat(),
        "end": equity_series.index[-1].isoformat(),
        "total_return_pct": float((equity_series.iloc[-1] - 1.0) * 100.0),
        "sharpe": sharpe,
        "max_drawdown_pct": float(conservative_mdd * 100.0),
        "trades": int(len(trades)),
        "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if len(pnl) else 0.0,
        "profit_factor": profit_factor,
        "avg_hold_hours": float(trades["hold_hours"].mean()) if len(trades) else 0.0,
        "worst_trade_return_pct": float(trades["net_return"].min() * 100.0)
        if len(trades)
        else 0.0,
        "turnover_annualized": turnover / years,
        "fee_pct_initial": fees * 100.0,
        "slippage_pct_initial": slip_cost_total * 100.0,
        "funding_pct_initial": funding_total * 100.0,
        "max_fill_leverage": max_fill_leverage,
        "max_effective_leverage": max_effective_leverage,
        "max_open_risk_pct": max_open_risk * 100.0,
        "risk_breaches": risk_breaches,
        "action_counts": action_counts,
        "half_mfe_violations": int(
            (~campaigns.loc[campaigns["reached_2r"], "half_mfe_retained"]).sum()
        ),
    }
    return PolicyResult(metrics, trades, pd.DataFrame(action_rows), equity_series)


def paired_bootstrap(
    dynamic: pd.DataFrame, seed: pd.DataFrame, rng_seed: int
) -> dict[str, Any]:
    paired = dynamic[["campaign_id", "net_return"]].merge(
        seed[["campaign_id", "net_return"]],
        on="campaign_id",
        suffixes=("_dynamic", "_seed"),
        validate="one_to_one",
    )
    differences = (
        paired["net_return_dynamic"] - paired["net_return_seed"]
    ).to_numpy(float)
    if not len(differences):
        return {"campaigns": 0, "mean_difference": 0.0, "ci": [0.0, 0.0]}
    rng = np.random.default_rng(rng_seed)
    samples = rng.choice(
        differences, size=(BOOTSTRAP_SAMPLES, len(differences)), replace=True
    ).mean(axis=1)
    return {
        "campaigns": int(len(differences)),
        "mean_difference": float(differences.mean()),
        "ci": [
            float(np.quantile(samples, 0.025)),
            float(np.quantile(samples, 0.975)),
        ],
    }


def dynamic_gate(
    dynamic: PolicyResult,
    seed: PolicyResult,
    full: PolicyResult,
    stress: PolicyResult,
    bootstrap: dict[str, Any],
) -> dict[str, Any]:
    metrics = dynamic.metrics
    seed_metrics = seed.metrics
    full_metrics = full.metrics
    counts = metrics["action_counts"]
    gate = {
        "net_return_and_sharpe_above_static_seed": bool(
            metrics["total_return_pct"] > seed_metrics["total_return_pct"]
            and metrics["sharpe"] > seed_metrics["sharpe"]
        ),
        "paired_campaign_increment_ci_low_positive": bootstrap["ci"][0] > 0.0,
        "mdd_and_worst_trade_not_worse_than_static_full": bool(
            metrics["max_drawdown_pct"] >= full_metrics["max_drawdown_pct"]
            and metrics["worst_trade_return_pct"]
            >= full_metrics["worst_trade_return_pct"]
        ),
        "base_and_stress_positive": bool(
            metrics["total_return_pct"] > 0.0
            and stress.metrics["total_return_pct"] > 0.0
        ),
        "campaign_count_hold_and_turnover": bool(
            metrics["trades"] >= 20
            and metrics["avg_hold_hours"] >= 24.0
            and metrics["turnover_annualized"] <= 24.0
        ),
        "dynamic_actions_not_dormant": bool(
            counts.get("add", 0) >= 5 and counts.get("reduce", 0) >= 5
        ),
        "risk_and_leverage_clean": bool(
            metrics["risk_breaches"] == 0
            and metrics["max_fill_leverage"] <= MAX_LEVERAGE + 1e-9
            and metrics["max_effective_leverage"] <= MAX_LEVERAGE + 1e-9
            and metrics["worst_trade_return_pct"] >= -DISASTER_FRACTION * 100.0
        ),
        "half_mfe_protection_clean": metrics["half_mfe_violations"] == 0,
        "details": {
            "paired_bootstrap": bootstrap,
            "dynamic_metrics": metrics,
            "static_seed_metrics": seed_metrics,
            "static_full_metrics": full_metrics,
            "stress_metrics": stress.metrics,
        },
    }
    gate["dynamic_control_supported"] = all(
        value for key, value in gate.items() if key != "details"
    )
    return gate


def rounded(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return round(value, 8)
    if isinstance(value, (np.integer, np.floating)):
        return rounded(value.item())
    return value


def generate_prediction_chunk(horizon: int) -> None:
    if horizon not in FUTURE_HORIZONS:
        raise ValueError(f"unsupported horizon: {horizon}")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, _, _ = load_data()
    _, visible, _ = build_complete_hourly(frame)
    state = build_price_state(visible)
    labelled = add_future_labels(state, horizons=(horizon,))
    predictions = build_prequential_predictions(labelled, horizons=(horizon,))
    path = ARTIFACT_DIR / (
        f"hype_1h_pktsc_prequential_h{horizon}_{RUN_DATE}.parquet"
    )
    predictions.to_parquet(path, index=False)
    print(json.dumps({"horizon": horizon, "rows": len(predictions), "path": str(path)}))


def finalize() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, source_quality = load_data()
    hourly, _, hourly_quality = build_complete_hourly(frame)
    chunks = []
    for horizon in FUTURE_HORIZONS:
        path = ARTIFACT_DIR / (
            f"hype_1h_pktsc_prequential_h{horizon}_{RUN_DATE}.parquet"
        )
        if not path.exists():
            raise RuntimeError(f"missing frozen prediction chunk: {path}")
        chunks.append(pd.read_parquet(path))
    predictions = pd.concat(chunks, ignore_index=True).sort_values(
        ["ts", "horizon_hours", "side"]
    )
    prediction_metrics, monthly_metrics, continuation_gates = evaluate_predictions(
        predictions
    )
    direction_results: dict[str, Any] = {}
    for direction_index, (direction, side) in enumerate(
        (("long", 1), ("short", -1))
    ):
        schedule, campaigns = build_campaign_schedule(
            hourly, predictions, side=side, use_mfe_floor=True
        )
        no_floor_schedule, no_floor_campaigns = build_campaign_schedule(
            hourly, predictions, side=side, use_mfe_floor=False
        )
        policies = {
            policy: simulate_policy(
                hourly, funding, schedule, campaigns, policy=policy
            )
            for policy in ("static_seed", "static_full", "dynamic")
        }
        dynamic_stress = simulate_policy(
            hourly,
            funding,
            schedule,
            campaigns,
            policy="dynamic",
            slippage=STRESS_SLIPPAGE,
        )
        dynamic_gross = simulate_policy(
            hourly,
            pd.Series(dtype=float),
            schedule,
            campaigns,
            policy="dynamic",
            fee_rate=0.0,
            slippage=0.0,
        )
        no_floor = simulate_policy(
            hourly,
            funding,
            no_floor_schedule,
            no_floor_campaigns,
            policy="dynamic",
        )
        bootstrap = paired_bootstrap(
            policies["dynamic"].trades,
            policies["static_seed"].trades,
            20260803 + direction_index,
        )
        gate = dynamic_gate(
            policies["dynamic"],
            policies["static_seed"],
            policies["static_full"],
            dynamic_stress,
            bootstrap,
        )
        direction_results[direction] = {
            "campaigns": int(len(campaigns)),
            "schedule_actions": int(len(schedule)),
            "policy_metrics": {
                name: result.metrics for name, result in policies.items()
            },
            "dynamic_stress_metrics": dynamic_stress.metrics,
            "dynamic_gross_metrics": dynamic_gross.metrics,
            "dynamic_no_mfe_floor_metrics": no_floor.metrics,
            "paired_dynamic_minus_seed": bootstrap,
            "dynamic_gate": gate,
        }
        prefix = ARTIFACT_DIR / f"hype_1h_pktsc_{direction}_{RUN_DATE}"
        schedule.to_csv(f"{prefix}_campaign_schedule.csv", index=False)
        campaigns.to_csv(f"{prefix}_campaigns.csv", index=False)
        for name, result in policies.items():
            result.trades.to_csv(f"{prefix}_{name}_trades.csv", index=False)
            result.actions.to_csv(f"{prefix}_{name}_actions.csv", index=False)
            result.equity.to_csv(f"{prefix}_{name}_equity.csv")
    predictions.to_parquet(
        ARTIFACT_DIR / f"hype_1h_pktsc_prequential_predictions_{RUN_DATE}.parquet",
        index=False,
    )
    prediction_metrics.to_csv(
        ARTIFACT_DIR / f"hype_1h_pktsc_prediction_metrics_{RUN_DATE}.csv",
        index=False,
    )
    monthly_metrics.to_csv(
        ARTIFACT_DIR / f"hype_1h_pktsc_monthly_metrics_{RUN_DATE}.csv",
        index=False,
    )
    payload = {
        "family": "HYPE-1H-Price-Kinematic-Trend-Survival-Control",
        "research_role": "unregistered historical causal walk-forward diagnostic",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_quality": {
            "source_15m": source_quality,
            "derived_complete_1h": hourly_quality,
        },
        "contract": {
            "past_windows_hours": PAST_WINDOWS,
            "future_horizons_hours": FUTURE_HORIZONS,
            "direction_window_hours": DIRECTION_WINDOW,
            "minimum_train_rows_per_direction": MIN_TRAIN_ROWS,
            "historical_walk_forward_start": WF_START.isoformat(),
            "prospective_oos_locked_not_revealed": [
                PROSPECTIVE_START.isoformat(),
                PROSPECTIVE_END.isoformat(),
            ],
            "risk_fraction": RISK_FRACTION,
            "disaster_fraction": DISASTER_FRACTION,
            "max_leverage": MAX_LEVERAGE,
            "fee_rate": FEE_RATE,
            "base_slippage": BASE_SLIPPAGE,
            "stress_slippage": STRESS_SLIPPAGE,
        },
        "continuation_prediction_gates": continuation_gates,
        "directions": direction_results,
        "prospective_oos_touched": False,
        "historical_evidence_is_locked_oos": False,
    }
    result_path = ARTIFACT_DIR / f"hype_1h_pktsc_research_{RUN_DATE}.json"
    result_path.write_text(
        json.dumps(rounded(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(rounded(payload), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--horizon", type=int)
    group.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.horizon is not None:
        generate_prediction_chunk(args.horizon)
    else:
        finalize()


if __name__ == "__main__":
    main()
