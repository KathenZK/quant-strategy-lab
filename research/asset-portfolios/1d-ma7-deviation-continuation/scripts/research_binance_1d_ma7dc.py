from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-deviation-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
LOADER_PATH = (
    ROOT
    / "research/asset-portfolios/1h-four-asset-trend-habitat-audit/scripts/"
    "research_binance_1h_fatha.py"
)
RUN_DATE = "2026-08-04"
ASSETS = ("HYPE", "BTC", "ETH")
HORIZONS = (1, 3, 7, 14)
FEATURES = (
    "ma7_slope_strength_atr",
    "signed_deviation_atr",
    "signed_deviation_velocity_atr",
    "slope_persistence_days",
)
SCOPES = ("all", "long", "short")
STATES = ("expansion", "pullback", "restart", "crossed")
RECENT_SLICES = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=182),
    "1y": pd.Timedelta(days=365),
}
MA_WINDOW = 7
MIN_QUANTILE_HISTORY = 90
BOOTSTRAP_SAMPLES = 1_000
BLOCK_DAYS = 14
FEE_RATE = 0.001
SLIPPAGE = 0.0004
ROUNDTRIP_HURDLE = 2.0 * (FEE_RATE + SLIPPAGE)
EPSILON = 1e-12


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_ma7dc_loader", LOADER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data module: {LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_hourly_assets() -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    module = load_module()
    loaded = module.load_assets()
    frames = {asset: loaded[asset].hourly.copy() for asset in ASSETS}
    quality = {asset: loaded[asset].quality for asset in ASSETS}
    return frames, quality


def build_complete_daily(hourly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = hourly.copy()
    source.index = source.index - pd.Timedelta(hours=1)
    grouped = source.resample("1D", label="left", closed="left")
    daily = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_bars=("close", "count"),
    )
    incomplete = daily.loc[daily["source_bars"].ne(24)].copy()
    daily = daily.loc[daily["source_bars"].eq(24)].copy()
    invalid = daily["high"].lt(
        daily[["open", "close", "low"]].max(axis=1)
    ) | daily["low"].gt(daily[["open", "close", "high"]].min(axis=1))
    expected = pd.date_range(daily.index.min(), daily.index.max(), freq="1D", tz="UTC")
    missing = expected.difference(daily.index)
    daily.index = daily.index + pd.Timedelta(days=1)
    quality = {
        "rows": int(len(daily)),
        "visible_start": daily.index.min().isoformat(),
        "visible_end": daily.index.max().isoformat(),
        "incomplete_source_days_excluded": int(len(incomplete)),
        "incomplete_source_day_starts": [value.isoformat() for value in incomplete.index[:10]],
        "missing_complete_days": int(len(missing)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "accepted": bool(len(missing) == 0 and not invalid.any()),
        "availability": "index is next UTC midnight after the completed source day",
    }
    if not quality["accepted"]:
        raise RuntimeError(f"daily data quality blocker: {quality}")
    return daily, quality


def _direction_persistence(direction: pd.Series) -> pd.Series:
    values = direction.to_numpy(float)
    out = np.zeros(len(values), dtype=float)
    previous = 0.0
    count = 0
    for index, value in enumerate(values):
        if not np.isfinite(value) or value == 0.0:
            previous = 0.0
            count = 0
            out[index] = 0.0
            continue
        count = count + 1 if value == previous else 1
        out[index] = float(count)
        previous = value
    return pd.Series(out, index=direction.index, dtype=float)


def _causal_quintile(values: pd.Series, min_history: int = MIN_QUANTILE_HISTORY) -> pd.Series:
    array = values.to_numpy(float)
    result = np.full(len(array), np.nan)
    for index, value in enumerate(array):
        if not np.isfinite(value):
            continue
        history = array[:index]
        history = history[np.isfinite(history)]
        if len(history) < min_history:
            continue
        cuts = np.quantile(history, [0.2, 0.4, 0.6, 0.8])
        result[index] = float(np.searchsorted(cuts, value, side="right") + 1)
    return pd.Series(result, index=values.index, dtype="Float64")


def build_states(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr7"] = true_range.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    frame["sma7"] = frame["close"].rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    slope = frame["sma7"] - frame["sma7"].shift(1)
    frame["direction"] = np.sign(slope)
    frame["direction_name"] = np.where(
        frame["direction"].gt(0), "long", np.where(frame["direction"].lt(0), "short", "flat")
    )
    frame["ma7_slope_strength_atr"] = slope.abs() / frame["atr7"].replace(0.0, np.nan)
    raw_deviation_atr = (frame["close"] - frame["sma7"]) / frame["atr7"].replace(0.0, np.nan)
    frame["raw_deviation_atr"] = raw_deviation_atr
    frame["signed_deviation_atr"] = frame["direction"] * raw_deviation_atr
    frame["signed_deviation_pct"] = frame["direction"] * (frame["close"] / frame["sma7"] - 1.0)
    frame["signed_deviation_velocity_atr"] = frame["direction"] * raw_deviation_atr.diff()
    frame["prior_signed_deviation_velocity_atr"] = frame["direction"] * raw_deviation_atr.diff().shift(1)
    frame["prior_signed_deviation_atr"] = frame["direction"] * raw_deviation_atr.shift(1)
    frame["slope_persistence_days"] = _direction_persistence(frame["direction"])
    stable = frame["direction"].ne(0.0) & frame["direction"].eq(frame["direction"].shift(1))
    positive_side = frame["signed_deviation_atr"].gt(0.0)
    restart = (
        stable
        & positive_side
        & frame["prior_signed_deviation_atr"].gt(0.0)
        & frame["signed_deviation_velocity_atr"].gt(0.0)
        & frame["prior_signed_deviation_velocity_atr"].lt(0.0)
    )
    frame["state"] = "unstable_direction"
    frame.loc[stable & frame["signed_deviation_atr"].le(0.0), "state"] = "crossed"
    frame.loc[stable & positive_side & frame["signed_deviation_velocity_atr"].lt(0.0), "state"] = "pullback"
    frame.loc[stable & positive_side & frame["signed_deviation_velocity_atr"].ge(0.0), "state"] = "expansion"
    frame.loc[restart, "state"] = "restart"
    frame["deviation_quintile"] = _causal_quintile(frame["signed_deviation_atr"])
    return frame


def _first_passage(
    highs: np.ndarray,
    lows: np.ndarray,
    entry: float,
    atr: float,
    side: int,
) -> float:
    if not np.isfinite(atr) or atr <= EPSILON:
        return math.nan
    favorable = entry + side * atr
    adverse = entry - side * 0.5 * atr
    for high, low in zip(highs, lows, strict=True):
        success = high >= favorable if side > 0 else low <= favorable
        failure = low <= adverse if side > 0 else high >= adverse
        if failure:
            return 0.0
        if success:
            return 1.0
    return math.nan


def add_future_labels(states: pd.DataFrame) -> pd.DataFrame:
    frame = states.copy()
    close = frame["close"].to_numpy(float)
    high = frame["high"].to_numpy(float)
    low = frame["low"].to_numpy(float)
    atr = frame["atr7"].to_numpy(float)
    direction = frame["direction"].to_numpy(float)
    for horizon in HORIZONS:
        raw_return = np.full(len(frame), np.nan)
        signed_return = np.full(len(frame), np.nan)
        mfe_r = np.full(len(frame), np.nan)
        mae_r = np.full(len(frame), np.nan)
        first_passage = np.full(len(frame), np.nan)
        for index in range(len(frame) - horizon):
            if not np.isfinite(direction[index]):
                continue
            side = int(direction[index])
            if side == 0 or not np.isfinite(atr[index]) or atr[index] <= EPSILON:
                continue
            raw_return[index] = math.log(close[index + horizon] / close[index])
            signed_return[index] = side * raw_return[index]
            future_high = high[index + 1 : index + horizon + 1]
            future_low = low[index + 1 : index + horizon + 1]
            if side > 0:
                favorable = max(0.0, float(future_high.max() - close[index]))
                adverse = max(0.0, float(close[index] - future_low.min()))
            else:
                favorable = max(0.0, float(close[index] - future_low.min()))
                adverse = max(0.0, float(future_high.max() - close[index]))
            mfe_r[index] = favorable / atr[index]
            mae_r[index] = adverse / atr[index]
            first_passage[index] = _first_passage(
                future_high, future_low, close[index], atr[index], side
            )
        frame[f"future_log_return_{horizon}d"] = raw_return
        frame[f"future_signed_log_return_{horizon}d"] = signed_return
        frame[f"future_net_log_return_{horizon}d"] = signed_return - ROUNDTRIP_HURDLE
        frame[f"continuation_{horizon}d"] = np.where(
            np.isfinite(signed_return), signed_return > 0.0, np.nan
        )
        frame[f"mfe_r_{horizon}d"] = mfe_r
        frame[f"mae_r_{horizon}d"] = mae_r
        frame[f"first_passage_{horizon}d"] = first_passage
    return frame


def _scope_subset(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "all":
        return frame.loc[frame["direction"].ne(0.0)].copy()
    return frame.loc[frame["direction_name"].eq(scope)].copy()


def _four_blocks(frame: pd.DataFrame) -> pd.Series:
    if len(frame) < 4:
        return pd.Series(np.nan, index=frame.index)
    positions = np.arange(len(frame))
    return pd.Series(np.minimum(3, positions * 4 // len(frame)) + 1, index=frame.index, dtype=int)


def _calendar_block_ids(index: pd.DatetimeIndex) -> np.ndarray:
    origin = index.min().floor("D")
    return ((index.floor("D") - origin).days // BLOCK_DAYS).to_numpy(int)


def block_bootstrap_ic(
    frame: pd.DataFrame,
    feature: str,
    target: str,
    seed: int,
) -> tuple[float, float, int]:
    work = frame[[feature, target]].dropna().copy()
    if len(work) < 20 or work[feature].nunique() < 3 or work[target].nunique() < 3:
        return math.nan, math.nan, 0
    work["block"] = _calendar_block_ids(pd.DatetimeIndex(work.index))
    blocks = [part for _, part in work.groupby("block", sort=True)]
    if len(blocks) < 4:
        return math.nan, math.nan, len(blocks)
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sampled = [blocks[index] for index in rng.integers(0, len(blocks), len(blocks))]
        joined = pd.concat(sampled, ignore_index=True)
        value = spearmanr(joined[feature], joined[target]).statistic
        if np.isfinite(value):
            draws.append(float(value))
    if not draws:
        return math.nan, math.nan, len(blocks)
    low, high = np.quantile(draws, [0.025, 0.975])
    return float(low), float(high), len(blocks)


def feature_metrics(asset: str, labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope_index, scope in enumerate(SCOPES):
        scoped = _scope_subset(labelled, scope)
        for horizon in HORIZONS:
            target = f"future_signed_log_return_{horizon}d"
            for feature_index, feature in enumerate(FEATURES):
                work = scoped[[feature, target]].dropna().copy()
                ic = (
                    float(spearmanr(work[feature], work[target]).statistic)
                    if len(work) >= 10 and work[feature].nunique() >= 3
                    else math.nan
                )
                work["time_block"] = _four_blocks(work)
                block_ics = []
                for _, part in work.groupby("time_block"):
                    value = (
                        spearmanr(part[feature], part[target]).statistic
                        if len(part) >= 8 and part[feature].nunique() >= 3
                        else math.nan
                    )
                    block_ics.append(float(value) if np.isfinite(value) else math.nan)
                ci_low, ci_high, independent_blocks = block_bootstrap_ic(
                    work,
                    feature,
                    target,
                    seed=20260804 + scope_index * 10_000 + horizon * 100 + feature_index,
                )
                rows.append(
                    {
                        "asset": asset,
                        "scope": scope,
                        "horizon_days": horizon,
                        "feature": feature,
                        "samples": int(len(work)),
                        "spearman_ic": ic,
                        "bootstrap_ci_low": ci_low,
                        "bootstrap_ci_high": ci_high,
                        "independent_14d_blocks": independent_blocks,
                        "positive_time_blocks": int(sum(value > 0.0 for value in block_ics if np.isfinite(value))),
                        "valid_time_blocks": int(sum(np.isfinite(value) for value in block_ics)),
                        **{f"time_block_{index + 1}_ic": value for index, value in enumerate(block_ics)},
                    }
                )
    return pd.DataFrame(rows)


def baseline_metrics(asset: str, labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in SCOPES:
        scoped = _scope_subset(labelled, scope)
        for horizon in HORIZONS:
            raw_target = f"future_log_return_{horizon}d"
            signed_target = f"future_signed_log_return_{horizon}d"
            conditional = scoped.loc[scoped[signed_target].notna()].copy()
            if scope == "long":
                fixed_side = 1.0
            elif scope == "short":
                fixed_side = -1.0
            else:
                fixed_side = math.nan
            unconditional = labelled.loc[labelled[raw_target].notna()].copy()
            unconditional_signed = (
                fixed_side * unconditional[raw_target]
                if np.isfinite(fixed_side)
                else pd.Series(np.nan, index=unconditional.index)
            )
            conditional_mean = float(conditional[signed_target].mean()) if len(conditional) else math.nan
            unconditional_mean = (
                float(unconditional_signed.mean()) if unconditional_signed.notna().any() else math.nan
            )
            rows.append(
                {
                    "asset": asset,
                    "scope": scope,
                    "horizon_days": horizon,
                    "conditional_samples": int(len(conditional)),
                    "conditional_mean_signed_log_return": conditional_mean,
                    "unconditional_same_side_samples": int(unconditional_signed.notna().sum()),
                    "unconditional_same_side_mean_log_return": unconditional_mean,
                    "conditional_uplift_vs_unconditional": (
                        conditional_mean - unconditional_mean
                        if np.isfinite(conditional_mean) and np.isfinite(unconditional_mean)
                        else math.nan
                    ),
                }
            )
    return pd.DataFrame(rows)


def _outcome_row(
    asset: str,
    scope: str,
    horizon: int,
    group_name: str,
    group_value: Any,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    target = f"future_signed_log_return_{horizon}d"
    work = frame.loc[frame[target].notna()].copy()
    passage = work[f"first_passage_{horizon}d"].dropna()
    return {
        "asset": asset,
        "scope": scope,
        "horizon_days": horizon,
        group_name: group_value,
        "samples": int(len(work)),
        "mean_signed_log_return": float(work[target].mean()) if len(work) else math.nan,
        "mean_net_log_return": float(work[f"future_net_log_return_{horizon}d"].mean()) if len(work) else math.nan,
        "continuation_rate": float(work[f"continuation_{horizon}d"].mean()) if len(work) else math.nan,
        "cost_positive_rate": float(work[f"future_net_log_return_{horizon}d"].gt(0.0).mean()) if len(work) else math.nan,
        "mean_mfe_r": float(work[f"mfe_r_{horizon}d"].mean()) if len(work) else math.nan,
        "mean_mae_r": float(work[f"mae_r_{horizon}d"].mean()) if len(work) else math.nan,
        "first_passage_success_rate": float(passage.mean()) if len(passage) else math.nan,
        "resolved_first_passage": int(len(passage)),
    }


def grouped_metrics(asset: str, labelled: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    quintile_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    for scope in SCOPES:
        scoped = _scope_subset(labelled, scope)
        for horizon in HORIZONS:
            for quintile in range(1, 6):
                part = scoped.loc[scoped["deviation_quintile"].eq(quintile)]
                quintile_rows.append(
                    _outcome_row(asset, scope, horizon, "deviation_quintile", quintile, part)
                )
            for state in STATES:
                part = scoped.loc[scoped["state"].eq(state)]
                state_rows.append(_outcome_row(asset, scope, horizon, "state", state, part))
    return pd.DataFrame(quintile_rows), pd.DataFrame(state_rows)


def block_metrics(asset: str, labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    horizon = 7
    for scope in SCOPES:
        scoped = _scope_subset(labelled, scope)
        target = f"future_signed_log_return_{horizon}d"
        scoped = scoped.loc[scoped[target].notna()].copy()
        scoped["time_block"] = _four_blocks(scoped)
        for block, block_frame in scoped.groupby("time_block"):
            block_start = block_frame.index.min().isoformat()
            block_end = block_frame.index.max().isoformat()
            baseline_row = _outcome_row(
                asset, scope, horizon, "time_block", int(block), block_frame
            )
            baseline_row.update(
                {
                    "group_kind": "baseline",
                    "state": "",
                    "deviation_quintile": math.nan,
                    "block_start": block_start,
                    "block_end": block_end,
                }
            )
            rows.append(baseline_row)
            for state in STATES:
                part = block_frame.loc[block_frame["state"].eq(state)]
                row = _outcome_row(asset, scope, horizon, "time_block", int(block), part)
                row.update(
                    {
                        "group_kind": "state",
                        "state": state,
                        "deviation_quintile": math.nan,
                        "block_start": block_start,
                        "block_end": block_end,
                    }
                )
                rows.append(row)
            for quintile in range(1, 6):
                part = block_frame.loc[block_frame["deviation_quintile"].eq(quintile)]
                row = _outcome_row(asset, scope, horizon, "time_block", int(block), part)
                row.update(
                    {
                        "group_kind": "deviation_quintile",
                        "state": "",
                        "deviation_quintile": quintile,
                        "block_start": block_start,
                        "block_end": block_end,
                    }
                )
                rows.append(row)
    return pd.DataFrame(rows)


def recent_slice_metrics(asset: str, labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    horizon = 7
    target = f"future_signed_log_return_{horizon}d"
    complete = labelled.loc[labelled[target].notna() & labelled["direction"].ne(0.0)].copy()
    if complete.empty:
        return pd.DataFrame()
    end = complete.index.max()
    for name, duration in RECENT_SLICES.items():
        part = complete.loc[complete.index > end - duration]
        row = _outcome_row(asset, "all", horizon, "slice", name, part)
        row["anchor_end"] = end.isoformat()
        rows.append(row)
    return pd.DataFrame(rows)


def _lookup(
    frame: pd.DataFrame,
    asset: str,
    scope: str,
    horizon: int,
    **filters: Any,
) -> pd.Series | None:
    mask = frame["asset"].eq(asset) & frame["scope"].eq(scope) & frame["horizon_days"].eq(horizon)
    for column, value in filters.items():
        mask &= frame[column].eq(value)
    selected = frame.loc[mask]
    return None if selected.empty else selected.iloc[0]


def build_gates(
    asset: str,
    labelled: pd.DataFrame,
    features: pd.DataFrame,
    baselines: pd.DataFrame,
    quintiles: pd.DataFrame,
    states: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in SCOPES:
        scoped = _scope_subset(labelled, scope)
        block_work = scoped.loc[scoped["future_signed_log_return_7d"].notna()].copy()
        block_work["time_block"] = _four_blocks(block_work)
        positive_blocks = int(
            block_work.groupby("time_block")["future_net_log_return_7d"].mean().gt(0.0).sum()
        )
        mean_7 = float(block_work["future_net_log_return_7d"].mean()) if len(block_work) else math.nan
        valid_14 = scoped["future_net_log_return_14d"].dropna()
        mean_14 = float(valid_14.mean()) if len(valid_14) else math.nan
        baseline_7 = _lookup(baselines, asset, scope, 7)
        baseline_14 = _lookup(baselines, asset, scope, 14)
        uplift_7 = (
            float(baseline_7["conditional_uplift_vs_unconditional"])
            if baseline_7 is not None
            else math.nan
        )
        uplift_14 = (
            float(baseline_14["conditional_uplift_vs_unconditional"])
            if baseline_14 is not None
            else math.nan
        )
        beta_control = scope == "all" or (uplift_7 > 0.0 and uplift_14 > 0.0)
        gate_direction = bool(
            mean_7 > 0.0 and mean_14 > 0.0 and positive_blocks >= 3 and beta_control
        )

        slope_7 = _lookup(features, asset, scope, 7, feature="ma7_slope_strength_atr")
        slope_14 = _lookup(features, asset, scope, 14, feature="ma7_slope_strength_atr")
        gate_slope = bool(
            slope_7 is not None
            and slope_14 is not None
            and float(slope_7["spearman_ic"]) > 0.0
            and float(slope_14["spearman_ic"]) > 0.0
            and (
                float(slope_7["bootstrap_ci_low"]) > 0.0
                or float(slope_14["bootstrap_ci_low"]) > 0.0
            )
        )

        interior_passes = 0
        interior_details: dict[str, Any] = {}
        for horizon in (7, 14):
            part = quintiles.loc[
                quintiles["asset"].eq(asset)
                & quintiles["scope"].eq(scope)
                & quintiles["horizon_days"].eq(horizon)
                & quintiles["samples"].gt(0)
            ].copy()
            if part.empty:
                best_q = math.nan
                best_net = math.nan
            else:
                best = part.loc[part["mean_net_log_return"].idxmax()]
                best_q = int(best["deviation_quintile"])
                best_net = float(best["mean_net_log_return"])
                if best_q in (2, 3, 4) and best_net > 0.0:
                    interior_passes += 1
            interior_details[f"best_deviation_q_{horizon}d"] = best_q
            interior_details[f"best_deviation_net_{horizon}d"] = best_net
        gate_interior = interior_passes == 2

        restart_passes = 0
        restart_details: dict[str, Any] = {}
        for horizon in (7, 14):
            restart = _lookup(states, asset, scope, horizon, state="restart")
            expansion = _lookup(states, asset, scope, horizon, state="expansion")
            restart_samples = int(restart["samples"]) if restart is not None else 0
            restart_net = float(restart["mean_net_log_return"]) if restart is not None else math.nan
            expansion_net = float(expansion["mean_net_log_return"]) if expansion is not None else math.nan
            if restart_samples >= 20 and restart_net > 0.0 and restart_net > expansion_net:
                restart_passes += 1
            restart_details[f"restart_samples_{horizon}d"] = restart_samples
            restart_details[f"restart_net_{horizon}d"] = restart_net
            restart_details[f"expansion_net_{horizon}d"] = expansion_net
        gate_restart = restart_passes == 2

        passed = sum((gate_direction, gate_slope, gate_interior, gate_restart))
        evidence = "supported" if passed >= 3 else "partial" if passed == 2 else "not supported"
        rows.append(
            {
                "asset": asset,
                "scope": scope,
                "directional_continuation": gate_direction,
                "slope_increment": gate_slope,
                "interior_deviation": gate_interior,
                "restart_increment": gate_restart,
                "passed_gates": passed,
                "evidence": evidence,
                "mean_net_7d": mean_7,
                "mean_net_14d": mean_14,
                "uplift_vs_unconditional_7d": uplift_7,
                "uplift_vs_unconditional_14d": uplift_14,
                "positive_7d_time_blocks": positive_blocks,
                **interior_details,
                **restart_details,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    hourly_assets, source_quality = load_hourly_assets()
    quality_payload: dict[str, Any] = {}
    daily_outputs: list[pd.DataFrame] = []
    feature_outputs: list[pd.DataFrame] = []
    baseline_outputs: list[pd.DataFrame] = []
    quintile_outputs: list[pd.DataFrame] = []
    state_outputs: list[pd.DataFrame] = []
    block_outputs: list[pd.DataFrame] = []
    slice_outputs: list[pd.DataFrame] = []
    gate_outputs: list[pd.DataFrame] = []

    for asset in ASSETS:
        daily, daily_quality = build_complete_daily(hourly_assets[asset])
        quality_payload[asset] = {
            "source": source_quality[asset],
            "daily": daily_quality,
        }
        labelled = add_future_labels(build_states(daily))
        labelled.insert(0, "asset", asset)
        features = feature_metrics(asset, labelled)
        baselines = baseline_metrics(asset, labelled)
        quintiles, states = grouped_metrics(asset, labelled)
        blocks = block_metrics(asset, labelled)
        slices = recent_slice_metrics(asset, labelled)
        gates = build_gates(asset, labelled, features, baselines, quintiles, states)
        daily_outputs.append(labelled.reset_index(names="visible_ts"))
        feature_outputs.append(features)
        baseline_outputs.append(baselines)
        quintile_outputs.append(quintiles)
        state_outputs.append(states)
        block_outputs.append(blocks)
        slice_outputs.append(slices)
        gate_outputs.append(gates)

    daily_frame = pd.concat(daily_outputs, ignore_index=True)
    feature_frame = pd.concat(feature_outputs, ignore_index=True)
    baseline_frame = pd.concat(baseline_outputs, ignore_index=True)
    quintile_frame = pd.concat(quintile_outputs, ignore_index=True)
    state_frame = pd.concat(state_outputs, ignore_index=True)
    block_frame = pd.concat(block_outputs, ignore_index=True)
    slice_frame = pd.concat(slice_outputs, ignore_index=True)
    gate_frame = pd.concat(gate_outputs, ignore_index=True)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    quality_path = ARTIFACT_DIR / f"binance_1d_ma7dc_data_quality_{RUN_DATE}.json"
    quality_path.write_text(json.dumps(quality_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    daily_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_daily_states_{RUN_DATE}.csv", index=False)
    feature_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_feature_metrics_{RUN_DATE}.csv", index=False)
    baseline_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_baseline_metrics_{RUN_DATE}.csv", index=False)
    quintile_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_deviation_quintiles_{RUN_DATE}.csv", index=False)
    state_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_state_metrics_{RUN_DATE}.csv", index=False)
    block_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_block_metrics_{RUN_DATE}.csv", index=False)
    slice_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_recent_slices_{RUN_DATE}.csv", index=False)
    gate_frame.to_csv(ARTIFACT_DIR / f"binance_1d_ma7dc_gate_summary_{RUN_DATE}.csv", index=False)
    summary = {
        "run_date": RUN_DATE,
        "family": "Binance-1D-MA7-Deviation-Continuation",
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "assets": ASSETS,
            "ma_type": "SMA",
            "ma_window": MA_WINDOW,
            "horizons_days": HORIZONS,
            "roundtrip_hurdle": ROUNDTRIP_HURDLE,
            "min_causal_quantile_history": MIN_QUANTILE_HISTORY,
            "historical_evidence_role": "diagnostic_only_researcher_exposed",
            "orders_generated": False,
        },
        "data_quality_accepted": bool(
            all(value["daily"]["accepted"] for value in quality_payload.values())
        ),
        "gates": gate_frame.to_dict(orient="records"),
    }
    (ARTIFACT_DIR / f"binance_1d_ma7dc_summary_{RUN_DATE}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(gate_frame.to_string(index=False))


if __name__ == "__main__":
    main()
