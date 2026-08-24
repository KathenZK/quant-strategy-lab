"""Continuous-strength hysteresis engine for the CTLS-R2 successor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from itertools import product
import math
from typing import Iterable

import numpy as np
import pandas as pd


class Direction(IntEnum):
    DOWN = -1
    FLAT = 0
    UP = 1


class Phase(str, Enum):
    NEUTRAL = "neutral"
    CHOP = "chop"
    SLOW = "slow"
    ESTABLISHED = "established"
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"


WEIGHT_TEMPLATES = {
    "equal": (1.0, 1.0, 1.0, 1.0),
    "persistence": (0.5, 1.5, 1.5, 1.0),
    "early": (1.5, 0.5, 1.5, 0.5),
    "smooth": (0.5, 1.5, 0.5, 1.5),
}


@dataclass(frozen=True, slots=True)
class StrengthConfig:
    z_scale: float
    slope_scale: float
    drift_scale: float
    weight_template: str
    enter_q: float
    exit_q: float
    enter_confirm_days: int
    exit_confirm_days: int = 2
    reverse_confirm_days: int = 1

    def __post_init__(self) -> None:
        if self.z_scale not in (0.25, 0.50, 1.00):
            raise ValueError("z_scale outside the R2 grid")
        if self.slope_scale not in (0.03, 0.08, 0.15):
            raise ValueError("slope_scale outside the R2 grid")
        if self.drift_scale not in (0.05, 0.10, 0.20):
            raise ValueError("drift_scale outside the R2 grid")
        if self.weight_template not in WEIGHT_TEMPLATES:
            raise ValueError("unknown weight template")
        if self.enter_q not in (0.20, 0.35, 0.50):
            raise ValueError("enter_q outside the R2 grid")
        if self.exit_q not in (-0.05, 0.05, 0.15):
            raise ValueError("exit_q outside the R2 grid")
        for name in ("enter_confirm_days", "exit_confirm_days", "reverse_confirm_days"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class PhaseConfig:
    velocity_source: str = "blend"
    accel_source: str = "blend"
    slow_threshold: float = 0.10
    accel_threshold: float = 0.05
    chop_er_max: float = 0.15
    chop_flips: int = 3

    def __post_init__(self) -> None:
        if self.velocity_source not in ("s3", "d3", "blend"):
            raise ValueError("unknown velocity source")
        if self.accel_source not in ("ma_curvature", "drift_curvature", "blend"):
            raise ValueError("unknown acceleration source")
        if self.slow_threshold not in (0.05, 0.10, 0.20):
            raise ValueError("slow_threshold outside the R2 grid")
        if self.accel_threshold not in (0.02, 0.05, 0.10):
            raise ValueError("accel_threshold outside the R2 grid")
        if not math.isfinite(self.chop_er_max) or self.chop_er_max < 0.0:
            raise ValueError("invalid chop_er_max")
        if not 1 <= self.chop_flips <= 4:
            raise ValueError("chop_flips must be in [1, 4]")


@dataclass(frozen=True, slots=True)
class StrengthFeatures:
    ts: pd.Timestamp
    close: float
    ma7: float
    atr7: float
    z: float
    s1: float
    s3: float
    d1: float
    d3: float
    er7: float
    ma_curvature: float
    drift_curvature: float

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.ts)
        if timestamp.tz is None or str(timestamp.tz) != "UTC" or timestamp.hour != 0:
            raise ValueError("feature timestamp must be a UTC daily boundary")
        values = (
            self.close,
            self.ma7,
            self.atr7,
            self.z,
            self.s1,
            self.s3,
            self.d1,
            self.d3,
            self.er7,
            self.ma_curvature,
            self.drift_curvature,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("R2 features must be finite")
        if self.close <= 0.0 or self.ma7 <= 0.0 or self.atr7 <= 0.0:
            raise ValueError("price and ATR inputs must be positive")


@dataclass(frozen=True, slots=True)
class StrengthSnapshot:
    ts: pd.Timestamp
    previous_direction: Direction
    direction: Direction
    phase: Phase
    q: float
    candidate_direction: Direction
    candidate_run: int
    loss_run: int
    velocity: float
    acceleration: float
    transition: str

    @property
    def label(self) -> str:
        if self.direction == Direction.FLAT:
            return self.phase.value
        prefix = "up" if self.direction == Direction.UP else "down"
        return f"{prefix}_{self.phase.value}"


@dataclass(slots=True)
class _State:
    direction: Direction = Direction.FLAT
    candidate_direction: Direction = Direction.FLAT
    candidate_run: int = 0
    loss_run: int = 0
    last_ts: pd.Timestamp | None = None
    relations: tuple[int, ...] = field(default_factory=tuple)


def direction_grid() -> tuple[StrengthConfig, ...]:
    rows = tuple(
        StrengthConfig(*values)
        for values in product(
            (0.25, 0.50, 1.00),
            (0.03, 0.08, 0.15),
            (0.05, 0.10, 0.20),
            tuple(WEIGHT_TEMPLATES),
            (0.20, 0.35, 0.50),
            (-0.05, 0.05, 0.15),
            (1, 2),
        )
    )
    if len(rows) != 1944 or len(set(rows)) != 1944:
        raise AssertionError("R2 direction grid must contain 1,944 unique configs")
    return rows


def phase_grid() -> tuple[PhaseConfig, ...]:
    rows = tuple(
        PhaseConfig(*values)
        for values in product(
            ("s3", "d3", "blend"),
            ("ma_curvature", "drift_curvature", "blend"),
            (0.05, 0.10, 0.20),
            (0.02, 0.05, 0.10),
        )
    )
    if len(rows) != 81 or len(set(rows)) != 81:
        raise AssertionError("R2 phase grid must contain 81 unique configs")
    return rows


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"close", "ma7", "atr7"}
    if not required.issubset(frame.columns):
        raise ValueError(f"missing columns: {sorted(required - set(frame.columns))}")
    result = frame.loc[:, ["close", "ma7", "atr7"]].astype(float).copy()
    if not isinstance(result.index, pd.DatetimeIndex):
        raise ValueError("R2 frame requires a DatetimeIndex")
    if result.index.tz is None or str(result.index.tz) != "UTC":
        raise ValueError("R2 frame index must be UTC")
    if not result.index.is_monotonic_increasing or result.index.has_duplicates:
        raise ValueError("R2 frame index must be sorted and unique")
    if len(result) > 1 and not result.index.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError("R2 frame must be daily consecutive")
    result["z"] = (result["close"] - result["ma7"]) / result["atr7"]
    result["s1"] = result["ma7"].diff() / result["atr7"]
    result["s3"] = result["ma7"].diff(3) / (3.0 * result["atr7"])
    result["d1"] = result["close"].diff() / result["atr7"]
    result["d3"] = result["close"].diff(3) / (3.0 * result["atr7"])
    change = result["close"].diff()
    denominator = change.abs().rolling(7, min_periods=7).sum()
    numerator = result["close"].diff(7)
    result["er7"] = np.divide(
        numerator,
        denominator,
        out=np.zeros(len(result), dtype=float),
        where=denominator.to_numpy() > 0.0,
    )
    result["ma_curvature"] = result["s1"] - result["s3"]
    result["drift_curvature"] = result["d1"] - result["d3"]
    return result.replace([np.inf, -np.inf], np.nan)


def feature_rows(frame: pd.DataFrame) -> tuple[StrengthFeatures, ...]:
    built = build_features(frame)
    columns = (
        "close",
        "ma7",
        "atr7",
        "z",
        "s1",
        "s3",
        "d1",
        "d3",
        "er7",
        "ma_curvature",
        "drift_curvature",
    )
    return tuple(
        StrengthFeatures(ts=pd.Timestamp(ts), **{name: float(row[name]) for name in columns})
        for ts, row in built.dropna().iterrows()
    )


def strength(features: StrengthFeatures, config: StrengthConfig) -> float:
    components = (
        math.tanh(features.z / config.z_scale),
        math.tanh(features.s3 / config.slope_scale),
        math.tanh(features.d3 / config.drift_scale),
        features.er7,
    )
    weights = WEIGHT_TEMPLATES[config.weight_template]
    return float(sum(weight * value for weight, value in zip(weights, components, strict=True)) / sum(weights))


def _flips(values: Iterable[int]) -> int:
    nonzero = [value for value in values if value]
    return sum(left != right for left, right in zip(nonzero, nonzero[1:], strict=False))


class ContinuousStrengthMachine:
    def __init__(self, strength_config: StrengthConfig, phase_config: PhaseConfig | None = None) -> None:
        self.strength_config = strength_config
        self.phase_config = phase_config or PhaseConfig()
        self.state = _State()

    def observe(self, features: StrengthFeatures) -> StrengthSnapshot:
        if self.state.last_ts is not None and features.ts != self.state.last_ts + pd.Timedelta(days=1):
            self._clear_candidate()
            self.state.loss_run = 0
            raise RuntimeError("R2 observations must be consecutive")
        q = strength(features, self.strength_config)
        raw = Direction.UP if q >= self.strength_config.enter_q else Direction.DOWN if q <= -self.strength_config.enter_q else Direction.FLAT
        previous = self.state.direction
        transition = "hold"
        if previous == Direction.FLAT:
            self.state.loss_run = 0
            self._advance_candidate(raw)
            if raw != Direction.FLAT and self.state.candidate_run >= self.strength_config.enter_confirm_days:
                self.state.direction = raw
                transition = f"enter_{raw.name.lower()}"
                self._clear_candidate()
        else:
            opposite = Direction(-int(previous))
            if raw == opposite:
                self._advance_candidate(opposite)
                if self.state.candidate_run >= self.strength_config.reverse_confirm_days:
                    self.state.direction = opposite
                    self.state.loss_run = 0
                    transition = f"reverse_to_{opposite.name.lower()}"
                    self._clear_candidate()
            else:
                self._clear_candidate()
                self.state.loss_run = self.state.loss_run + 1 if int(previous) * q <= self.strength_config.exit_q else 0
                if self.state.loss_run >= self.strength_config.exit_confirm_days:
                    self.state.direction = Direction.FLAT
                    self.state.loss_run = 0
                    transition = "direction_loss"
        relation = 1 if features.close > features.ma7 else -1 if features.close < features.ma7 else 0
        self.state.relations = (*self.state.relations, relation)[-5:]
        self.state.last_ts = features.ts
        velocity = self._velocity(features)
        acceleration = self._acceleration(features)
        phase = self._phase(features, velocity, acceleration)
        return StrengthSnapshot(
            ts=features.ts,
            previous_direction=previous,
            direction=self.state.direction,
            phase=phase,
            q=q,
            candidate_direction=self.state.candidate_direction,
            candidate_run=self.state.candidate_run,
            loss_run=self.state.loss_run,
            velocity=velocity,
            acceleration=acceleration,
            transition=transition,
        )

    def _advance_candidate(self, direction: Direction) -> None:
        if direction == Direction.FLAT:
            self._clear_candidate()
        elif direction == self.state.candidate_direction:
            self.state.candidate_run += 1
        else:
            self.state.candidate_direction = direction
            self.state.candidate_run = 1

    def _clear_candidate(self) -> None:
        self.state.candidate_direction = Direction.FLAT
        self.state.candidate_run = 0

    def _velocity(self, features: StrengthFeatures) -> float:
        if self.phase_config.velocity_source == "s3":
            return features.s3
        if self.phase_config.velocity_source == "d3":
            return features.d3
        return 0.5 * (features.s3 + features.d3)

    def _acceleration(self, features: StrengthFeatures) -> float:
        if self.phase_config.accel_source == "ma_curvature":
            return features.ma_curvature
        if self.phase_config.accel_source == "drift_curvature":
            return features.drift_curvature
        return 0.5 * (features.ma_curvature + features.drift_curvature)

    def _phase(self, features: StrengthFeatures, velocity: float, acceleration: float) -> Phase:
        side = self.state.direction
        if side == Direction.FLAT:
            if _flips(self.state.relations) >= self.phase_config.chop_flips and abs(features.er7) < self.phase_config.chop_er_max:
                return Phase.CHOP
            return Phase.NEUTRAL
        signed = int(side)
        if signed * velocity < self.phase_config.slow_threshold:
            return Phase.SLOW
        if signed * acceleration > self.phase_config.accel_threshold:
            return Phase.ACCELERATING
        if signed * acceleration < -self.phase_config.accel_threshold:
            return Phase.DECELERATING
        return Phase.ESTABLISHED


def replay(
    features: Iterable[StrengthFeatures],
    strength_config: StrengthConfig,
    phase_config: PhaseConfig | None = None,
) -> tuple[StrengthSnapshot, ...]:
    machine = ContinuousStrengthMachine(strength_config, phase_config)
    return tuple(machine.observe(row) for row in features)
