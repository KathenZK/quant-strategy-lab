from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import sds_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_contract.json"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_search.json"
RANKING_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_ranking.csv"
ABLATION_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_ablation.csv"
TRADES_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_reference_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_reference_equity.csv"
STATES_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_prefit_reference_states.parquet"


@dataclass(frozen=True, slots=True)
class KCSConfig:
    volatility_span: int = 96
    kalman_process_ratio: float = 0.01
    kalman_measurement_multiplier: float = 2.0
    kalman_slope_vol_entry: float = 0.08
    kalman_slope_z_entry: float = 1.0
    kalman_slope_vol_exit: float = 0.0
    cusum_allowance: float = 0.15
    cusum_entry: float = 4.0
    structure_window: int = 48
    exit_window: int = 16
    efficiency_window: int = 48
    efficiency_min: float = 0.25
    arm_timeout_bars: int = 12
    exit_confirm_bars: int = 3
    require_cusum: bool = True
    require_kalman: bool = True
    require_structure: bool = True
    require_efficiency: bool = True

    def validate(self) -> None:
        if min(
            self.volatility_span,
            self.structure_window,
            self.exit_window,
            self.efficiency_window,
            self.arm_timeout_bars,
            self.exit_confirm_bars,
        ) <= 0:
            raise ValueError("all windows must be positive")
        if self.kalman_process_ratio <= 0.0:
            raise ValueError("kalman_process_ratio must be positive")
        if self.kalman_measurement_multiplier <= 0.0:
            raise ValueError("kalman_measurement_multiplier must be positive")
        if self.kalman_slope_vol_entry <= 0.0:
            raise ValueError("kalman entry threshold must be positive")
        if self.kalman_slope_z_entry < 0.0:
            raise ValueError("kalman z threshold must be non-negative")
        if self.cusum_entry <= 0.0 or self.cusum_allowance < 0.0:
            raise ValueError("invalid CUSUM thresholds")
        if not 0.0 <= self.efficiency_min <= 1.0:
            raise ValueError("efficiency_min must be in [0, 1]")


@dataclass(slots=True)
class KCSFeatures:
    normalized_return: np.ndarray
    kalman_level: np.ndarray
    kalman_slope: np.ndarray
    kalman_slope_vol: np.ndarray
    kalman_slope_z: np.ndarray
    innovation_z: np.ndarray
    efficiency: np.ndarray
    prior_high: np.ndarray
    prior_low: np.ndarray
    exit_high: np.ndarray
    exit_low: np.ndarray


def config_payload(config: KCSConfig) -> dict[str, Any]:
    return asdict(config)


def config_label(config: KCSConfig) -> str:
    return (
        f"q{config.kalman_process_ratio:g}"
        f"__r{config.kalman_measurement_multiplier:g}"
        f"__cs{config.cusum_entry:g}"
        f"__ks{config.kalman_slope_vol_entry:g}"
        f"__sw{config.structure_window}"
        f"__eff{config.efficiency_min:g}"
        f"__arm{config.arm_timeout_bars}"
        f"__exit{config.exit_confirm_bars}"
    )


def _shifted_return_volatility(
    log_price: np.ndarray,
    span: int,
) -> tuple[np.ndarray, np.ndarray]:
    log_return = np.r_[np.nan, np.diff(log_price)]
    volatility = (
        pd.Series(log_return)
        .ewm(span=span, adjust=False, min_periods=span)
        .std(bias=False)
        .shift(1)
        .to_numpy("float64")
    )
    normalized = log_return / np.where(volatility <= 1e-12, np.nan, volatility)
    return volatility, np.clip(normalized, -8.0, 8.0)


def causal_local_linear_kalman(
    log_price: np.ndarray,
    volatility: np.ndarray,
    *,
    process_ratio: float,
    measurement_multiplier: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows = len(log_price)
    level = np.full(rows, np.nan)
    slope = np.full(rows, np.nan)
    slope_z = np.full(rows, np.nan)
    innovation_z = np.full(rows, np.nan)
    state = np.zeros(2, dtype="float64")
    covariance = np.eye(2, dtype="float64")
    transition = np.asarray([[1.0, 1.0], [0.0, 1.0]], dtype="float64")
    identity = np.eye(2, dtype="float64")
    initialized = False

    for index in range(rows):
        sigma = float(volatility[index])
        if not np.isfinite(sigma) or sigma <= 1e-12:
            continue
        variance = sigma * sigma
        if not initialized:
            state[:] = (float(log_price[index]), 0.0)
            covariance = np.diag([10.0 * variance, variance])
            initialized = True
        else:
            process_noise = np.diag(
                [
                    0.10 * process_ratio * variance,
                    process_ratio * variance,
                ]
            )
            predicted_state = transition @ state
            predicted_covariance = (
                transition @ covariance @ transition.T + process_noise
            )
            observation_variance = measurement_multiplier * variance
            innovation = float(log_price[index] - predicted_state[0])
            innovation_variance = float(
                predicted_covariance[0, 0] + observation_variance
            )
            gain = predicted_covariance[:, 0] / innovation_variance
            state = predicted_state + gain * innovation
            covariance = (
                identity - np.outer(gain, np.asarray([1.0, 0.0]))
            ) @ predicted_covariance
            covariance = 0.5 * (covariance + covariance.T)
            innovation_z[index] = innovation / math.sqrt(innovation_variance)

        level[index] = state[0]
        slope[index] = state[1]
        slope_uncertainty = math.sqrt(max(float(covariance[1, 1]), 1e-18))
        slope_z[index] = state[1] / slope_uncertainty

    return level, slope, slope_z, innovation_z


def build_features(
    book: engine.FeatureBook,
    config: KCSConfig,
) -> KCSFeatures:
    config.validate()
    log_price = np.log(book.close)
    volatility, normalized = _shifted_return_volatility(
        log_price,
        config.volatility_span,
    )
    level, slope, slope_z, innovation_z = causal_local_linear_kalman(
        log_price,
        volatility,
        process_ratio=config.kalman_process_ratio,
        measurement_multiplier=config.kalman_measurement_multiplier,
    )
    slope_vol = slope / np.where(volatility <= 1e-12, np.nan, volatility)
    efficiency = engine._efficiency_ratio(
        log_price,
        config.efficiency_window,
    )
    prior_high = (
        pd.Series(book.high)
        .shift(1)
        .rolling(config.structure_window, min_periods=config.structure_window)
        .max()
        .to_numpy("float64")
    )
    prior_low = (
        pd.Series(book.low)
        .shift(1)
        .rolling(config.structure_window, min_periods=config.structure_window)
        .min()
        .to_numpy("float64")
    )
    exit_high = (
        pd.Series(book.high)
        .shift(1)
        .rolling(config.exit_window, min_periods=config.exit_window)
        .max()
        .to_numpy("float64")
    )
    exit_low = (
        pd.Series(book.low)
        .shift(1)
        .rolling(config.exit_window, min_periods=config.exit_window)
        .min()
        .to_numpy("float64")
    )
    return KCSFeatures(
        normalized_return=normalized,
        kalman_level=level,
        kalman_slope=slope,
        kalman_slope_vol=slope_vol,
        kalman_slope_z=slope_z,
        innovation_z=innovation_z,
        efficiency=efficiency,
        prior_high=prior_high,
        prior_low=prior_low,
        exit_high=exit_high,
        exit_low=exit_low,
    )


def generate_kcs_states(
    book: engine.FeatureBook,
    config: KCSConfig,
    *,
    features: KCSFeatures | None = None,
) -> engine.StateBook:
    config.validate()
    features = features or build_features(book, config)
    rows = book.rows
    desired = np.zeros(rows, dtype="int8")
    positive_cusum = np.zeros(rows, dtype="float64")
    negative_cusum = np.zeros(rows, dtype="float64")
    reasons = ["warmup"] * rows
    active_state = 0
    armed_direction = 0
    armed_age = 0
    weak_count = 0
    g_pos = 0.0
    g_neg = 0.0

    for index in range(rows):
        z_value = features.normalized_return[index]
        ready = (
            np.isfinite(z_value)
            and np.isfinite(features.kalman_slope_vol[index])
            and np.isfinite(features.kalman_slope_z[index])
            and np.isfinite(features.efficiency[index])
            and np.isfinite(features.prior_high[index])
            and np.isfinite(features.prior_low[index])
            and np.isfinite(features.exit_high[index])
            and np.isfinite(features.exit_low[index])
        )
        if not ready:
            desired[index] = active_state
            positive_cusum[index] = g_pos
            negative_cusum[index] = g_neg
            continue

        g_pos = max(0.0, g_pos + float(z_value) - config.cusum_allowance)
        g_neg = min(0.0, g_neg + float(z_value) + config.cusum_allowance)
        kalman_long = (
            features.kalman_slope_vol[index]
            >= config.kalman_slope_vol_entry
            and features.kalman_slope_z[index] >= config.kalman_slope_z_entry
        )
        kalman_short = (
            features.kalman_slope_vol[index]
            <= -config.kalman_slope_vol_entry
            and features.kalman_slope_z[index] <= -config.kalman_slope_z_entry
        )
        cusum_long = g_pos >= config.cusum_entry
        cusum_short = g_neg <= -config.cusum_entry
        long_detected = (
            (cusum_long or not config.require_cusum)
            and (kalman_long or not config.require_kalman)
        )
        short_detected = (
            (cusum_short or not config.require_cusum)
            and (kalman_short or not config.require_kalman)
        )
        long_breakout = (
            book.close[index] > features.prior_high[index]
            if config.require_structure
            else True
        )
        short_breakout = (
            book.close[index] < features.prior_low[index]
            if config.require_structure
            else True
        )
        efficient = (
            features.efficiency[index] >= config.efficiency_min
            if config.require_efficiency
            else True
        )
        reason = "hold"

        if active_state == 0:
            if armed_direction:
                armed_age += 1
                kalman_valid = (
                    features.kalman_slope_vol[index] > 0.0
                    if armed_direction == 1
                    else features.kalman_slope_vol[index] < 0.0
                )
                if (
                    (config.require_kalman and not kalman_valid)
                    or armed_age > config.arm_timeout_bars
                ):
                    reason = "arm_cancel"
                    armed_direction = 0
                    armed_age = 0
                    g_pos = 0.0
                    g_neg = 0.0
                elif (
                    armed_direction == 1
                    and long_breakout
                    and efficient
                ):
                    active_state = 1
                    armed_direction = 0
                    armed_age = 0
                    weak_count = 0
                    g_pos = 0.0
                    g_neg = 0.0
                    reason = "long_start"
                elif (
                    armed_direction == -1
                    and short_breakout
                    and efficient
                ):
                    active_state = -1
                    armed_direction = 0
                    armed_age = 0
                    weak_count = 0
                    g_pos = 0.0
                    g_neg = 0.0
                    reason = "short_start"

            if active_state == 0 and armed_direction == 0:
                if long_detected and not short_detected:
                    if long_breakout and efficient:
                        active_state = 1
                        weak_count = 0
                        g_pos = 0.0
                        g_neg = 0.0
                        reason = "long_start"
                    else:
                        armed_direction = 1
                        armed_age = 0
                        reason = "long_arm"
                elif short_detected and not long_detected:
                    if short_breakout and efficient:
                        active_state = -1
                        weak_count = 0
                        g_pos = 0.0
                        g_neg = 0.0
                        reason = "short_start"
                    else:
                        armed_direction = -1
                        armed_age = 0
                        reason = "short_arm"
        elif active_state == 1:
            slope_weak = (
                features.kalman_slope_vol[index]
                <= config.kalman_slope_vol_exit
            )
            weak_count = weak_count + 1 if slope_weak else 0
            structure_broken = book.close[index] < features.exit_low[index]
            opposite_change = (
                g_neg <= -config.cusum_entry
                and features.kalman_slope_vol[index] < 0.0
            )
            if (
                structure_broken
                or opposite_change
                or weak_count >= config.exit_confirm_bars
            ):
                active_state = 0
                weak_count = 0
                g_pos = 0.0
                g_neg = 0.0
                reason = (
                    "long_structure_end"
                    if structure_broken
                    else "long_opposite_end"
                    if opposite_change
                    else "long_slope_end"
                )
        else:
            slope_weak = (
                features.kalman_slope_vol[index]
                >= -config.kalman_slope_vol_exit
            )
            weak_count = weak_count + 1 if slope_weak else 0
            structure_broken = book.close[index] > features.exit_high[index]
            opposite_change = (
                g_pos >= config.cusum_entry
                and features.kalman_slope_vol[index] > 0.0
            )
            if (
                structure_broken
                or opposite_change
                or weak_count >= config.exit_confirm_bars
            ):
                active_state = 0
                weak_count = 0
                g_pos = 0.0
                g_neg = 0.0
                reason = (
                    "short_structure_end"
                    if structure_broken
                    else "short_opposite_end"
                    if opposite_change
                    else "short_slope_end"
                )

        desired[index] = active_state
        positive_cusum[index] = g_pos
        negative_cusum[index] = g_neg
        reasons[index] = reason

    return engine.StateBook(
        desired_state=desired,
        normalized_return=features.normalized_return,
        fast_drift=features.kalman_slope_vol,
        slow_drift=features.kalman_slope_z,
        efficiency_ratio=features.efficiency,
        positive_cusum=positive_cusum,
        negative_cusum=negative_cusum,
        transition_reason=reasons,
    )


def _candidate_grid() -> list[KCSConfig]:
    configs: list[KCSConfig] = []
    for (
        process_ratio,
        measurement_multiplier,
        cusum_entry,
        slope_entry,
        structure_window,
        efficiency_min,
        arm_timeout,
        exit_confirm,
    ) in itertools.product(
        (0.003, 0.01, 0.03),
        (1.0, 4.0),
        (3.0, 5.0),
        (0.05, 0.10),
        (32, 64),
        (0.20, 0.30),
        (8, 16),
        (2, 4),
    ):
        configs.append(
            KCSConfig(
                kalman_process_ratio=process_ratio,
                kalman_measurement_multiplier=measurement_multiplier,
                cusum_entry=cusum_entry,
                kalman_slope_vol_entry=slope_entry,
                structure_window=structure_window,
                efficiency_window=structure_window,
                efficiency_min=efficiency_min,
                arm_timeout_bars=arm_timeout,
                exit_confirm_bars=exit_confirm,
            )
        )
    return configs


def _score(
    train: dict[str, Any],
    validation: dict[str, Any],
    *,
    valid_sample: bool,
) -> float:
    if not valid_sample:
        return -1e9
    return (
        math.log(max(1e-9, 1.0 + float(train["return"])))
        + math.log(max(1e-9, 1.0 + float(validation["return"])))
        + float(train["max_drawdown"])
        + float(validation["max_drawdown"])
    )


def _run_with_cost_multiplier(
    book: engine.FeatureBook,
    backtest_config: engine.Config,
    states: engine.StateBook,
    multiplier: float,
) -> engine.BacktestResult:
    original_fee = engine.BASE_FEE
    original_slippage = engine.BASE_SLIPPAGE
    try:
        engine.BASE_FEE = original_fee * multiplier
        engine.BASE_SLIPPAGE = original_slippage * multiplier
        return engine.run_backtest(book, backtest_config, states=states)
    finally:
        engine.BASE_FEE = original_fee
        engine.BASE_SLIPPAGE = original_slippage


def _states_frame(
    book: engine.FeatureBook,
    states: engine.StateBook,
    features: KCSFeatures,
) -> pd.DataFrame:
    frame = engine.states_frame(book, states)
    frame["kalman_level"] = features.kalman_level
    frame["kalman_slope"] = features.kalman_slope
    frame["kalman_slope_vol"] = features.kalman_slope_vol
    frame["kalman_slope_z"] = features.kalman_slope_z
    frame["innovation_z"] = features.innovation_z
    frame["prior_high"] = features.prior_high
    frame["prior_low"] = features.prior_low
    frame["exit_high"] = features.exit_high
    frame["exit_low"] = features.exit_low
    return frame


def _direction_diagnostic(
    book: engine.FeatureBook,
    backtest_config: engine.Config,
    states: engine.StateBook,
    validation_start: pd.Timestamp,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, desired in {
        "both": states.desired_state,
        "long_only": np.where(states.desired_state == 1, 1, 0),
        "short_only": np.where(states.desired_state == -1, -1, 0),
    }.items():
        scoped_states = engine.StateBook(
            desired_state=np.asarray(desired, dtype="int8"),
            normalized_return=states.normalized_return,
            fast_drift=states.fast_drift,
            slow_drift=states.slow_drift,
            efficiency_ratio=states.efficiency_ratio,
            positive_cusum=states.positive_cusum,
            negative_cusum=states.negative_cusum,
            transition_reason=states.transition_reason,
        )
        result = engine.run_backtest(
            book,
            backtest_config,
            states=scoped_states,
        )
        output[name] = {
            "train": engine.slice_metrics(
                result,
                start=book.source_start,
                end=validation_start,
            ),
            "validation": engine.slice_metrics(
                result,
                start=validation_start,
                end=book.terminal_ts,
            ),
            "prefit": result.metrics,
        }
    return output


def _recent_prefit_slices(
    result: engine.BacktestResult,
    terminal: pd.Timestamp,
) -> dict[str, Any]:
    offsets = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.DateOffset(months=1),
        "3m": pd.DateOffset(months=3),
        "6m": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
    }
    return {
        label: engine.slice_metrics(
            result,
            start=terminal - offset,
            end=terminal,
        )
        for label, offset in offsets.items()
    }


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    book = engine.build_book(include_locked_oos=False)
    expected_terminal = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    if book.terminal_ts != expected_terminal:
        raise RuntimeError("KCS search attempted to read beyond frozen prefit")
    configs = _candidate_grid()
    grid_payload = [config_payload(config) for config in configs]
    grid_raw = json.dumps(grid_payload, sort_keys=True, separators=(",", ":"))
    validation_start = book.terminal_ts - pd.DateOffset(months=3)
    contract = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "mechanism": "causal Kalman local-linear slope + Page CUSUM detector + Donchian structure confirmation + hysteresis state machine",
        "scope": "prefit only; previously revealed reused OOS is prohibited",
        "prefit_terminal_exclusive": book.terminal_ts.isoformat(),
        "validation_start_inclusive": validation_start.isoformat(),
        "candidate_count": len(configs),
        "candidate_grid_sha256": hashlib.sha256(grid_raw.encode("utf-8")).hexdigest(),
        "candidate_grid": grid_payload,
        "selection_rule": "require train>=30 and validation>=10 trades, then require both returns positive and rank by joint log return plus segment drawdown penalties",
        "execution": {
            "signal": "closed 15m bar",
            "fill": "next bar open",
            "cost": "0.001 fee + 4 bps adverse slippage per fill, actual funding",
            "risk": "1x, 4 ATR96 emergency stop, 384 bar max hold",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    backtest_config = engine.Config(
        stop_atr=4.0,
        max_hold_bars=384,
        leverage=1.0,
    )
    feature_cache: dict[tuple[float, float, int], KCSFeatures] = {}
    rows: list[dict[str, Any]] = []
    result_cache: dict[str, tuple[engine.BacktestResult, KCSFeatures]] = {}
    for config in configs:
        feature_key = (
            config.kalman_process_ratio,
            config.kalman_measurement_multiplier,
            config.structure_window,
        )
        features = feature_cache.get(feature_key)
        if features is None:
            features = build_features(book, config)
            feature_cache[feature_key] = features
        states = generate_kcs_states(book, config, features=features)
        result = engine.run_backtest(book, backtest_config, states=states)
        train = engine.slice_metrics(
            result,
            start=book.source_start,
            end=validation_start,
        )
        validation = engine.slice_metrics(
            result,
            start=validation_start,
            end=book.terminal_ts,
        )
        valid_sample = train["trades"] >= 30 and validation["trades"] >= 10
        joint_positive = train["return"] > 0.0 and validation["return"] > 0.0
        label = config_label(config)
        rows.append(
            {
                "label": label,
                **config_payload(config),
                "train_return": train["return"],
                "train_max_drawdown": train["max_drawdown"],
                "train_trades": train["trades"],
                "train_win_rate": train["win_rate"],
                "validation_return": validation["return"],
                "validation_max_drawdown": validation["max_drawdown"],
                "validation_trades": validation["trades"],
                "validation_win_rate": validation["win_rate"],
                "prefit_return": result.metrics["total_return"],
                "prefit_max_drawdown": result.metrics["max_drawdown"],
                "prefit_trades": result.metrics["trades"],
                "prefit_win_rate": result.metrics["win_rate"],
                "valid_sample": valid_sample,
                "joint_positive": joint_positive,
                "score": _score(train, validation, valid_sample=valid_sample),
            }
        )
        result_cache[label] = (result, features)

    ranking = pd.DataFrame(rows)
    ranking["eligible"] = ranking["valid_sample"] & ranking["joint_positive"]
    ranking = ranking.sort_values(
        ["eligible", "valid_sample", "score"],
        ascending=[False, False, False],
    )
    reference_row = ranking.iloc[0].to_dict()
    reference_config = next(
        config
        for config in configs
        if config_label(config) == reference_row["label"]
    )
    reference_result, reference_features = result_cache[reference_row["label"]]

    ablation_configs = {
        "full_combo": reference_config,
        "no_cusum": KCSConfig(
            **{**config_payload(reference_config), "require_cusum": False}
        ),
        "no_kalman": KCSConfig(
            **{**config_payload(reference_config), "require_kalman": False}
        ),
        "no_structure": KCSConfig(
            **{**config_payload(reference_config), "require_structure": False}
        ),
        "no_efficiency": KCSConfig(
            **{**config_payload(reference_config), "require_efficiency": False}
        ),
    }
    ablation_rows: list[dict[str, Any]] = []
    for name, config in ablation_configs.items():
        features = build_features(book, config)
        states = generate_kcs_states(book, config, features=features)
        result = engine.run_backtest(book, backtest_config, states=states)
        train = engine.slice_metrics(
            result,
            start=book.source_start,
            end=validation_start,
        )
        validation = engine.slice_metrics(
            result,
            start=validation_start,
            end=book.terminal_ts,
        )
        ablation_rows.append(
            {
                "ablation": name,
                "train_return": train["return"],
                "train_max_drawdown": train["max_drawdown"],
                "train_trades": train["trades"],
                "validation_return": validation["return"],
                "validation_max_drawdown": validation["max_drawdown"],
                "validation_trades": validation["trades"],
                "prefit_return": result.metrics["total_return"],
                "prefit_max_drawdown": result.metrics["max_drawdown"],
                "prefit_trades": result.metrics["trades"],
                "prefit_win_rate": result.metrics["win_rate"],
            }
        )

    zero_cost = _run_with_cost_multiplier(
        book,
        backtest_config,
        reference_result.states,
        0.0,
    )
    double_cost = _run_with_cost_multiplier(
        book,
        backtest_config,
        reference_result.states,
        2.0,
    )
    exit_counts = (
        pd.Series([trade["exit_reason"] for trade in reference_result.trades])
        .value_counts()
        .sort_index()
        .to_dict()
    )
    summary = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "mechanism": "Kalman + CUSUM + structure confirmation state machine",
        "status": "prefit-only diagnostic / not registered / not promoted / not live-ready",
        "oos_read": False,
        "prefit_terminal_exclusive": book.terminal_ts.isoformat(),
        "validation_start_inclusive": validation_start.isoformat(),
        "candidate_count": len(ranking),
        "valid_sample_count": int(ranking["valid_sample"].sum()),
        "eligible_count": int(ranking["eligible"].sum()),
        "reference_only": not bool(ranking["eligible"].any()),
        "reference": reference_row,
        "reference_recent_prefit_slices": _recent_prefit_slices(
            reference_result,
            book.terminal_ts,
        ),
        "cost_stress_prefit": {
            "zero_cost": zero_cost.metrics,
            "base_cost": reference_result.metrics,
            "double_cost": double_cost.metrics,
        },
        "exit_reason_counts": exit_counts,
        "state_transition_counts": (
            pd.Series(reference_result.states.transition_reason)
            .value_counts()
            .sort_index()
            .to_dict()
        ),
        "direction_diagnostic": _direction_diagnostic(
            book,
            backtest_config,
            reference_result.states,
            validation_start,
        ),
        "ablation": ablation_rows,
        "decision": (
            "freeze for prospective OOS only if eligible_count is positive and "
            "the result is not dependent on a single fragile parameter island; "
            "never inspect the previously revealed reused OOS for this mechanism"
        ),
    }
    ranking.to_csv(RANKING_PATH, index=False)
    pd.DataFrame(ablation_rows).to_csv(ABLATION_PATH, index=False)
    pd.DataFrame(reference_result.trades).to_csv(TRADES_PATH, index=False)
    pd.DataFrame(reference_result.equity_path).to_csv(EQUITY_PATH, index=False)
    _states_frame(
        book,
        reference_result.states,
        reference_features,
    ).to_parquet(STATES_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
