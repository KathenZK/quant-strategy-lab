"""Pure causal engine for the CTLS continuous-trend research branch.

The engine owns no market data, performance result, or frozen champion.  It
separates an always-observed trend state from the account position that a
later execution harness may choose to hold.
"""

from __future__ import annotations

from dataclasses import dataclass
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


class StateLabel(str, Enum):
    NEUTRAL = "neutral"
    CHOP = "chop"
    UP_SLOW = "up_slow"
    UP_ESTABLISHED = "up_established"
    UP_ACCELERATING = "up_accelerating"
    UP_DECELERATING = "up_decelerating"
    DOWN_SLOW = "down_slow"
    DOWN_ESTABLISHED = "down_established"
    DOWN_ACCELERATING = "down_accelerating"
    DOWN_DECELERATING = "down_decelerating"


@dataclass(frozen=True, slots=True)
class DetectionConfig:
    distance_min: float
    slow_slope_min: float
    drift_min: float
    er_min: float
    direction_score_min: int
    enter_confirm_days: int
    hold_score_min: int = 1
    exit_confirm_days: int = 2
    reverse_confirm_days: int = 2
    accel_threshold: float = 0.03
    slow_phase_threshold: float = 0.08
    chop_er_max: float = 0.15
    chop_flips: int = 3

    def __post_init__(self) -> None:
        thresholds = (
            self.distance_min,
            self.slow_slope_min,
            self.drift_min,
            self.er_min,
            self.accel_threshold,
            self.slow_phase_threshold,
            self.chop_er_max,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in thresholds):
            raise ValueError("thresholds must be finite and non-negative")
        if self.direction_score_min not in (2, 3):
            raise ValueError("direction_score_min must be 2 or 3")
        if not 1 <= self.hold_score_min <= 4:
            raise ValueError("hold_score_min must be in [1, 4]")
        for name in ("enter_confirm_days", "exit_confirm_days", "reverse_confirm_days"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        if not 1 <= self.chop_flips <= 4:
            raise ValueError("chop_flips must be in [1, 4]")


@dataclass(frozen=True, slots=True)
class CausalFeatures:
    ts: pd.Timestamp
    close: float
    ma7: float
    atr7: float
    z: float
    s1: float
    s3: float
    d3: float
    er7: float
    acceleration: float

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.ts)
        if timestamp.tz is None or str(timestamp.tz) != "UTC":
            raise ValueError("feature timestamp must be timezone-aware UTC")
        if timestamp.hour != 0 or any(
            (timestamp.minute, timestamp.second, timestamp.microsecond)
        ):
            raise ValueError("feature timestamp must be a UTC daily boundary")
        values = (
            self.close,
            self.ma7,
            self.atr7,
            self.z,
            self.s1,
            self.s3,
            self.d3,
            self.er7,
            self.acceleration,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("all feature values must be finite")
        if self.close <= 0.0 or self.ma7 <= 0.0 or self.atr7 <= 0.0:
            raise ValueError("close, ma7, and atr7 must be positive")
        if not -1.0 <= self.er7 <= 1.0:
            raise ValueError("er7 must be in [-1, 1]")


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    ts: pd.Timestamp
    previous_direction: Direction
    direction: Direction
    phase: Phase
    up_score: int
    down_score: int
    candidate_direction: Direction
    candidate_run: int
    loss_run: int
    transition: str

    @property
    def label(self) -> StateLabel:
        if self.direction == Direction.FLAT:
            return StateLabel.CHOP if self.phase == Phase.CHOP else StateLabel.NEUTRAL
        return StateLabel(f"{'up' if self.direction == Direction.UP else 'down'}_{self.phase.value}")


@dataclass(slots=True)
class _MachineState:
    direction: Direction = Direction.FLAT
    candidate_direction: Direction = Direction.FLAT
    candidate_run: int = 0
    loss_run: int = 0
    last_ts: pd.Timestamp | None = None
    relations: tuple[int, ...] = ()


def detection_grid() -> tuple[DetectionConfig, ...]:
    configs = tuple(
        DetectionConfig(*values)
        for values in product(
            (0.0, 0.10, 0.25),
            (0.0, 0.01, 0.02),
            (0.0, 0.05, 0.10),
            (0.10, 0.20, 0.30),
            (2, 3),
            (1, 2),
        )
    )
    if len(configs) != 324 or len(set(configs)) != 324:
        raise AssertionError("frozen CTLS detection grid must contain 324 unique configs")
    return configs


def build_causal_features(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"close", "ma7", "atr7"}
    if not required.issubset(frame.columns):
        raise ValueError(f"missing columns: {sorted(required - set(frame.columns))}")
    result = frame.loc[:, ["close", "ma7", "atr7"]].astype(float).copy()
    if not isinstance(result.index, pd.DatetimeIndex):
        raise ValueError("daily feature frame requires a DatetimeIndex")
    if result.index.tz is None or str(result.index.tz) != "UTC":
        raise ValueError("daily feature index must be timezone-aware UTC")
    if not result.index.is_monotonic_increasing or result.index.has_duplicates:
        raise ValueError("daily feature index must be sorted and unique")
    if len(result) > 1 and not result.index.to_series().diff().dropna().eq(
        pd.Timedelta(days=1)
    ).all():
        raise ValueError("daily feature index must be consecutive")
    result["z"] = (result["close"] - result["ma7"]) / result["atr7"]
    result["s1"] = result["ma7"].diff(1) / result["atr7"]
    result["s3"] = result["ma7"].diff(3) / (3.0 * result["atr7"])
    result["d3"] = result["close"].diff(3) / (3.0 * result["atr7"])
    abs_change = result["close"].diff().abs()
    denominator = abs_change.rolling(7, min_periods=7).sum()
    numerator = result["close"].diff(7)
    result["er7"] = np.divide(
        numerator,
        denominator,
        out=np.zeros(len(result), dtype=float),
        where=denominator.to_numpy() > 0.0,
    )
    result["acceleration"] = result["s1"] - result["s3"]
    result = result.replace([np.inf, -np.inf], np.nan)
    return result


def feature_rows(frame: pd.DataFrame) -> tuple[CausalFeatures, ...]:
    built = build_causal_features(frame)
    rows: list[CausalFeatures] = []
    for ts, row in built.dropna().iterrows():
        rows.append(
            CausalFeatures(
                ts=pd.Timestamp(ts),
                close=float(row["close"]),
                ma7=float(row["ma7"]),
                atr7=float(row["atr7"]),
                z=float(row["z"]),
                s1=float(row["s1"]),
                s3=float(row["s3"]),
                d3=float(row["d3"]),
                er7=float(row["er7"]),
                acceleration=float(row["acceleration"]),
            )
        )
    return tuple(rows)


def _score(features: CausalFeatures, side: Direction, config: DetectionConfig) -> int:
    signed = int(side)
    return sum(
        (
            signed * features.z > config.distance_min,
            signed * features.s3 > config.slow_slope_min,
            signed * features.d3 > config.drift_min,
            signed * features.er7 > config.er_min,
        )
    )


def _relation(features: CausalFeatures) -> int:
    return 1 if features.close > features.ma7 else -1 if features.close < features.ma7 else 0


def _flip_count(relations: Iterable[int]) -> int:
    nonzero = [value for value in relations if value]
    return sum(left != right for left, right in zip(nonzero, nonzero[1:], strict=False))


class ContinuousTrendMachine:
    def __init__(self, config: DetectionConfig) -> None:
        self.config = config
        self.state = _MachineState()

    def observe(self, features: CausalFeatures) -> StateSnapshot:
        if self.state.last_ts is not None and features.ts != self.state.last_ts + pd.Timedelta(
            days=1
        ):
            self.state.candidate_direction = Direction.FLAT
            self.state.candidate_run = 0
            self.state.loss_run = 0
            raise RuntimeError("CTLS observations must be consecutive")
        up_score = _score(features, Direction.UP, self.config)
        down_score = _score(features, Direction.DOWN, self.config)
        raw = Direction.FLAT
        if up_score >= self.config.direction_score_min and up_score > down_score:
            raw = Direction.UP
        elif down_score >= self.config.direction_score_min and down_score > up_score:
            raw = Direction.DOWN

        previous = self.state.direction
        transition = "hold"
        if previous == Direction.FLAT:
            self.state.loss_run = 0
            self._advance_candidate(raw)
            if (
                raw != Direction.FLAT
                and self.state.candidate_run >= self.config.enter_confirm_days
            ):
                self.state.direction = raw
                transition = f"enter_{raw.name.lower()}"
                self._clear_candidate()
        else:
            opposite = Direction(-int(previous))
            if raw == opposite:
                self._advance_candidate(raw)
                if self.state.candidate_run >= self.config.reverse_confirm_days:
                    self.state.direction = opposite
                    self.state.loss_run = 0
                    transition = f"reverse_to_{opposite.name.lower()}"
                    self._clear_candidate()
            else:
                self._clear_candidate()
                active_score = up_score if previous == Direction.UP else down_score
                self.state.loss_run = (
                    self.state.loss_run + 1
                    if active_score < self.config.hold_score_min
                    else 0
                )
                if self.state.loss_run >= self.config.exit_confirm_days:
                    self.state.direction = Direction.FLAT
                    self.state.loss_run = 0
                    transition = "direction_loss"

        relations = (*self.state.relations, _relation(features))[-5:]
        self.state.relations = relations
        self.state.last_ts = features.ts
        phase = self._phase(features, up_score, down_score)
        return StateSnapshot(
            ts=features.ts,
            previous_direction=previous,
            direction=self.state.direction,
            phase=phase,
            up_score=up_score,
            down_score=down_score,
            candidate_direction=self.state.candidate_direction,
            candidate_run=self.state.candidate_run,
            loss_run=self.state.loss_run,
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

    def _phase(
        self,
        features: CausalFeatures,
        up_score: int,
        down_score: int,
    ) -> Phase:
        direction = self.state.direction
        if direction == Direction.FLAT:
            if (
                _flip_count(self.state.relations) >= self.config.chop_flips
                and abs(features.er7) < self.config.chop_er_max
            ):
                return Phase.CHOP
            return Phase.NEUTRAL
        signed = int(direction)
        active_score = up_score if direction == Direction.UP else down_score
        if (
            signed * features.acceleration > self.config.accel_threshold
            and signed * features.s1 > self.config.accel_threshold
        ):
            return Phase.ACCELERATING
        if (
            signed * features.acceleration < -self.config.accel_threshold
            or active_score < self.config.direction_score_min
        ):
            return Phase.DECELERATING
        if signed * features.s3 < self.config.slow_phase_threshold:
            return Phase.SLOW
        return Phase.ESTABLISHED


def hindsight_labels(frame: pd.DataFrame) -> pd.Series:
    built = build_causal_features(frame)
    labels = pd.Series(index=built.index, dtype="object")
    close = built["close"].to_numpy(float)
    ma7 = built["ma7"].to_numpy(float)
    atr7 = built["atr7"].to_numpy(float)
    x = np.arange(-3.0, 4.0)
    x_ss = float(np.dot(x, x))
    for index in range(3, len(built) - 3):
        if not np.isfinite(atr7[index]) or atr7[index] <= 0.0:
            continue
        values = close[index - 3 : index + 4]
        if not np.isfinite(values).all():
            continue
        centered = values - float(values.mean())
        beta = float(np.dot(x, centered) / x_ss)
        fitted = beta * x
        total = float(np.dot(centered, centered))
        residual = float(np.dot(centered - fitted, centered - fitted))
        r_squared = 0.0 if total <= 0.0 else max(0.0, 1.0 - residual / total)
        beta_atr = beta / atr7[index]
        if abs(beta_atr) < 0.08 or r_squared < 0.35:
            ma_window = ma7[index - 3 : index + 4]
            if not np.isfinite(ma_window).all():
                continue
            relations = np.sign(
                values - ma_window
            ).astype(int)
            labels.iloc[index] = (
                StateLabel.CHOP.value
                if _flip_count(relations) >= 3
                else StateLabel.NEUTRAL.value
            )
            continue
        direction = Direction.UP if beta_atr > 0.0 else Direction.DOWN
        past = (close[index] - close[index - 3]) / (3.0 * atr7[index])
        future = (close[index + 3] - close[index]) / (3.0 * atr7[index])
        directional_change = int(direction) * (future - past)
        prefix = "up" if direction == Direction.UP else "down"
        if directional_change > 0.10:
            phase = "accelerating"
        elif directional_change < -0.10:
            phase = "decelerating"
        elif abs(beta_atr) < 0.20:
            phase = "slow"
        else:
            phase = "established"
        labels.iloc[index] = f"{prefix}_{phase}"
    return labels


def replay(
    features: Iterable[CausalFeatures], config: DetectionConfig
) -> tuple[StateSnapshot, ...]:
    machine = ContinuousTrendMachine(config)
    return tuple(machine.observe(row) for row in features)
