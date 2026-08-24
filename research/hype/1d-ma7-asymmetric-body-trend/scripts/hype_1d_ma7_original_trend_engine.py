"""Pure close-to-next-open state engine for the MA7 original-trend study.

This module intentionally performs no data loading and exposes no frozen default
configuration.  The remaining semantic choices are explicit in ``StrategyConfig``
and must be fixed in a research contract before any historical result is run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Iterable

import numpy as np
import pandas as pd


class Side(IntEnum):
    SHORT = -1
    FLAT = 0
    LONG = 1


class SlopeLossAction(str, Enum):
    HOLD = "hold"
    FLAT = "flat"


class OverboughtMode(str, Enum):
    DISABLED = "disabled"
    SHORT_FILTER = "short_filter"
    EARLY_REVERSAL = "early_reversal"


@dataclass(frozen=True)
class StrategyConfig:
    """Every field that can change the trade path is explicit.

    ``arm_expiry_days=None`` means that a fresh cross remains armed until price
    closes back on the originating side of MA7.  A non-negative integer limits
    confirmation to that many *subsequent* completed days after the cross.
    """

    prior_side_days: int
    session_open_hour: int
    tolerance_atr: float
    slope_min_atr: float
    entry_requires_slope: bool
    band_requires_slope: bool
    slope_loss_action: SlopeLossAction
    arm_cross_while_held: bool
    arm_expiry_days: int | None
    flat_cross_waits_for_confirmation: bool
    short_rsi_exit_enabled: bool
    short_rsi_exit_threshold: float
    short_rsi_exit_days: int
    short_rsi_exit_requires_profit: bool
    overbought_mode: OverboughtMode
    overbought_threshold: float
    overbought_days: int
    overbought_requires_short_slope: bool
    strict_previous_side: bool = True

    def __post_init__(self) -> None:
        if self.prior_side_days < 1:
            raise ValueError("prior_side_days must be >= 1")
        if not 0 <= self.session_open_hour <= 23:
            raise ValueError("session_open_hour must be in [0, 23]")
        if self.tolerance_atr < 0.0:
            raise ValueError("tolerance_atr must be >= 0")
        if self.slope_min_atr < 0.0:
            raise ValueError("slope_min_atr must be >= 0")
        if self.arm_expiry_days is not None and self.arm_expiry_days < 0:
            raise ValueError("arm_expiry_days must be >= 0 or None")
        if not 0.0 < self.short_rsi_exit_threshold < 100.0:
            raise ValueError("short RSI exit threshold must be in (0, 100)")
        if self.short_rsi_exit_days < 1:
            raise ValueError("short_rsi_exit_days must be >= 1")
        if not 0.0 < self.overbought_threshold < 100.0:
            raise ValueError("overbought threshold must be in (0, 100)")
        if self.overbought_days < 1:
            raise ValueError("overbought_days must be >= 1")


@dataclass(frozen=True)
class CloseObservation:
    ts: pd.Timestamp
    close: float
    ma7: float
    atr7: float
    slope_atr: float
    rsi6: float

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("observation timestamp must be timezone-aware")
        if (
            str(self.ts.tz) != "UTC"
            or self.ts.minute != 0
            or self.ts.second != 0
            or self.ts.microsecond != 0
        ):
            raise ValueError("observation timestamp must be an hourly UTC session open")
        values = (self.close, self.ma7, self.atr7, self.slope_atr, self.rsi6)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("observation values must be finite")
        if self.close <= 0.0 or self.ma7 <= 0.0 or self.atr7 <= 0.0:
            raise ValueError("close, ma7 and atr7 must be positive")
        if not 0.0 <= self.rsi6 <= 100.0:
            raise ValueError("rsi6 must be in [0, 100]")


@dataclass(frozen=True)
class Decision:
    signal_ts: pd.Timestamp
    from_side: Side
    target_side: Side
    reason: str

    @property
    def next_open_ts(self) -> pd.Timestamp:
        return self.signal_ts + pd.Timedelta(days=1)

    @property
    def fills(self) -> int:
        if self.from_side == self.target_side:
            return 0
        if self.from_side != Side.FLAT and self.target_side != Side.FLAT:
            return 2
        return 1


@dataclass
class MachineState:
    side: Side = Side.FLAT
    entry_price: float | None = None
    armed_side: Side = Side.FLAT
    armed_age: int = 0
    relations: list[int] = field(default_factory=list)
    rsi_values: list[float] = field(default_factory=list)
    pending: Decision | None = None
    last_close_ts: pd.Timestamp | None = None


def _relation(close: float, ma7: float) -> int:
    if close > ma7:
        return 1
    if close < ma7:
        return -1
    return 0


def _all_prior_side(
    relations: Iterable[int],
    *,
    side: Side,
    days: int,
    strict: bool,
) -> bool:
    history = list(relations)
    if len(history) < days:
        return False
    required = history[-days:]
    if strict:
        return all(value == int(side) for value in required)
    if side == Side.LONG:
        return all(value >= 0 for value in required)
    return all(value <= 0 for value in required)


def fresh_cross(
    relations: Iterable[int],
    current_relation: int,
    target_side: Side,
    config: StrategyConfig,
) -> bool:
    if target_side not in (Side.LONG, Side.SHORT):
        raise ValueError("target_side must be LONG or SHORT")
    if current_relation != int(target_side):
        return False
    return _all_prior_side(
        relations,
        side=Side(-int(target_side)),
        days=config.prior_side_days,
        strict=config.strict_previous_side,
    )


def _slope_pass(side: Side, slope_atr: float, minimum: float) -> bool:
    if side == Side.LONG:
        return slope_atr > minimum
    if side == Side.SHORT:
        return slope_atr < -minimum
    raise ValueError("slope side must be directional")


def _streak(values: Iterable[float], days: int, predicate) -> bool:
    history = list(values)
    return len(history) >= days and all(predicate(value) for value in history[-days:])


class OriginalTrendMachine:
    """Causal state machine: closed-bar decisions apply only at next open."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.state = MachineState()

    def seed_position(self, side: Side, entry_price: float) -> None:
        if self.state.pending is not None or self.state.relations:
            raise RuntimeError("seed_position is only allowed before observations")
        if side == Side.FLAT or not np.isfinite(entry_price) or entry_price <= 0.0:
            raise ValueError("seed position must be directional with a positive price")
        self.state.side = side
        self.state.entry_price = float(entry_price)

    def prime_history(self, observations: Iterable[CloseObservation]) -> None:
        if (
            self.state.side != Side.FLAT
            or self.state.pending is not None
            or self.state.last_close_ts is not None
        ):
            raise RuntimeError("history priming requires a fresh flat machine")
        history = list(observations)
        for index, obs in enumerate(history):
            if obs.ts.hour != self.config.session_open_hour:
                raise ValueError("history timestamp does not match session_open_hour")
            if index and obs.ts != history[index - 1].ts + pd.Timedelta(days=1):
                raise RuntimeError("priming observations must be consecutive")
            self.state.relations.append(_relation(obs.close, obs.ma7))
            self.state.rsi_values.append(obs.rsi6)
        if history:
            limit = max(
                self.config.prior_side_days,
                self.config.short_rsi_exit_days,
                self.config.overbought_days,
            )
            self.state.relations = self.state.relations[-limit:]
            self.state.rsi_values = self.state.rsi_values[-limit:]
            self.state.last_close_ts = history[-1].ts

    def force_flat(self) -> None:
        if self.state.pending is not None:
            raise RuntimeError("cannot force flat with a pending daily decision")
        self.state.side = Side.FLAT
        self.state.entry_price = None
        self._cancel_arm()

    def _arm(self, side: Side) -> None:
        self.state.armed_side = side
        self.state.armed_age = 0

    def _cancel_arm(self) -> None:
        self.state.armed_side = Side.FLAT
        self.state.armed_age = 0

    def _age_or_expire_arm(self) -> None:
        if self.state.armed_side == Side.FLAT:
            return
        self.state.armed_age += 1
        expiry = self.config.arm_expiry_days
        if expiry is not None and self.state.armed_age > expiry:
            self._cancel_arm()

    def _band_confirms(self, side: Side, obs: CloseObservation) -> bool:
        if self.config.band_requires_slope and not _slope_pass(
            side, obs.slope_atr, self.config.slope_min_atr
        ):
            return False
        if side == Side.LONG:
            return obs.close >= obs.ma7 + self.config.tolerance_atr * obs.atr7
        return obs.close <= obs.ma7 - self.config.tolerance_atr * obs.atr7

    def _entry_slope_passes(self, side: Side, obs: CloseObservation) -> bool:
        return not self.config.entry_requires_slope or _slope_pass(
            side, obs.slope_atr, self.config.slope_min_atr
        )

    def _prior_overbought(self) -> bool:
        return _streak(
            self.state.rsi_values,
            self.config.overbought_days,
            lambda value: value > self.config.overbought_threshold,
        )

    def _short_rsi_exit(self, obs: CloseObservation) -> bool:
        if not self.config.short_rsi_exit_enabled:
            return False
        values = [*self.state.rsi_values, obs.rsi6]
        if not _streak(
            values,
            self.config.short_rsi_exit_days,
            lambda value: value < self.config.short_rsi_exit_threshold,
        ):
            return False
        if not self.config.short_rsi_exit_requires_profit:
            return True
        return self.state.entry_price is not None and obs.close < self.state.entry_price

    def _validate_next_close(self, obs: CloseObservation) -> None:
        if obs.ts.hour != self.config.session_open_hour:
            raise ValueError("observation timestamp does not match session_open_hour")
        if (
            self.state.last_close_ts is not None
            and obs.ts != self.state.last_close_ts + pd.Timedelta(days=1)
        ):
            raise RuntimeError("daily observations must be consecutive UTC sessions")

    def _record_observation(self, obs: CloseObservation) -> None:
        self.state.relations.append(_relation(obs.close, obs.ma7))
        self.state.rsi_values.append(obs.rsi6)
        history_limit = max(
            self.config.prior_side_days,
            self.config.short_rsi_exit_days,
            self.config.overbought_days,
        )
        self.state.relations = self.state.relations[-history_limit:]
        self.state.rsi_values = self.state.rsi_values[-history_limit:]
        self.state.last_close_ts = obs.ts

    def _decide_flat(
        self,
        obs: CloseObservation,
        fresh_up: bool,
        fresh_down: bool,
    ) -> Decision | None:
        for side, crossed in ((Side.LONG, fresh_up), (Side.SHORT, fresh_down)):
            if not crossed:
                continue
            if (
                side == Side.SHORT
                and self.config.overbought_mode == OverboughtMode.SHORT_FILTER
                and not self._prior_overbought()
            ):
                continue
            if self.config.flat_cross_waits_for_confirmation:
                self._arm(side)
                if not self._band_confirms(side, obs):
                    return None
            elif not self._entry_slope_passes(side, obs):
                return None
            return Decision(obs.ts, Side.FLAT, side, f"fresh_cross_{side.name.lower()}")

        if self.state.armed_side in (Side.LONG, Side.SHORT):
            target = self.state.armed_side
            relation = _relation(obs.close, obs.ma7)
            if relation == -int(target):
                self._cancel_arm()
            elif self._band_confirms(target, obs):
                return Decision(
                    obs.ts,
                    Side.FLAT,
                    target,
                    f"armed_band_confirm_{target.name.lower()}",
                )
        return None

    def _decide_long(
        self,
        obs: CloseObservation,
        fresh_down: bool,
    ) -> Decision | None:
        if fresh_down and self.config.arm_cross_while_held:
            self._arm(Side.SHORT)
        elif _relation(obs.close, obs.ma7) > 0 and self.state.armed_side == Side.SHORT:
            self._cancel_arm()

        if (
            fresh_down
            and self.config.overbought_mode == OverboughtMode.EARLY_REVERSAL
            and self._prior_overbought()
            and (
                not self.config.overbought_requires_short_slope
                or _slope_pass(
                    Side.SHORT,
                    obs.slope_atr,
                    self.config.slope_min_atr,
                )
            )
        ):
            return Decision(obs.ts, Side.LONG, Side.SHORT, "overbought_fresh_down")

        if self.state.armed_side == Side.SHORT and self._band_confirms(Side.SHORT, obs):
            return Decision(obs.ts, Side.LONG, Side.SHORT, "armed_short_band_confirm")

        if self.config.slope_loss_action == SlopeLossAction.FLAT and not _slope_pass(
            Side.LONG, obs.slope_atr, self.config.slope_min_atr
        ):
            return Decision(obs.ts, Side.LONG, Side.FLAT, "long_slope_lost")
        return None

    def _decide_short(
        self,
        obs: CloseObservation,
        fresh_up: bool,
    ) -> Decision | None:
        if fresh_up and self.config.arm_cross_while_held:
            self._arm(Side.LONG)
        elif _relation(obs.close, obs.ma7) < 0 and self.state.armed_side == Side.LONG:
            self._cancel_arm()

        if self.state.armed_side == Side.LONG and self._band_confirms(Side.LONG, obs):
            return Decision(obs.ts, Side.SHORT, Side.LONG, "armed_long_band_confirm")

        if self._short_rsi_exit(obs):
            return Decision(obs.ts, Side.SHORT, Side.FLAT, "short_rsi_take_profit")

        if self.config.slope_loss_action == SlopeLossAction.FLAT and not _slope_pass(
            Side.SHORT, obs.slope_atr, self.config.slope_min_atr
        ):
            return Decision(obs.ts, Side.SHORT, Side.FLAT, "short_slope_lost")
        return None

    def on_close(self, obs: CloseObservation) -> Decision | None:
        if self.state.pending is not None:
            raise RuntimeError("pending close decision must execute at the next open")
        self._validate_next_close(obs)

        current_relation = _relation(obs.close, obs.ma7)
        fresh_up = fresh_cross(
            self.state.relations,
            current_relation,
            Side.LONG,
            self.config,
        )
        fresh_down = fresh_cross(
            self.state.relations,
            current_relation,
            Side.SHORT,
            self.config,
        )

        if self.state.armed_side != Side.FLAT and not (fresh_up or fresh_down):
            self._age_or_expire_arm()

        if self.state.side == Side.FLAT:
            decision = self._decide_flat(obs, fresh_up, fresh_down)
        elif self.state.side == Side.LONG:
            decision = self._decide_long(obs, fresh_down)
        else:
            decision = self._decide_short(obs, fresh_up)

        self._record_observation(obs)
        self.state.pending = decision
        return decision

    def observe_pending_close(self, obs: CloseObservation) -> None:
        """Advance causal history while a delayed decision remains frozen.

        No replacement decision may be created during an execution-delay stress.
        An armed cross can still age or be cancelled by a recross because those
        are observable state updates rather than fills.
        """

        if self.state.pending is None:
            raise RuntimeError("pending-close observation requires a decision")
        self._validate_next_close(obs)
        relation = _relation(obs.close, obs.ma7)
        if self.state.armed_side != Side.FLAT:
            if relation == -int(self.state.armed_side):
                self._cancel_arm()
            else:
                self._age_or_expire_arm()
        self._record_observation(obs)

    def on_next_open(
        self,
        fill_ts: pd.Timestamp,
        fill_price: float,
        *,
        extra_delay_days: int = 0,
    ) -> Decision:
        decision = self.state.pending
        if decision is None:
            raise RuntimeError("no pending decision for this open")
        if extra_delay_days < 0:
            raise ValueError("extra_delay_days must be >= 0")
        expected = decision.next_open_ts + pd.Timedelta(days=extra_delay_days)
        if fill_ts != expected:
            raise RuntimeError(f"decision must fill at {expected.isoformat()}")
        if not np.isfinite(fill_price) or fill_price <= 0.0:
            raise ValueError("fill_price must be positive and finite")
        self.state.side = decision.target_side
        self.state.entry_price = (
            None if decision.target_side == Side.FLAT else float(fill_price)
        )
        preserve_opposite_arm = (
            decision.target_side == Side.FLAT
            and decision.reason
            in {
                "long_slope_lost",
                "short_slope_lost",
                "short_rsi_take_profit",
            }
            and self.state.armed_side != Side.FLAT
        )
        if not preserve_opposite_arm:
            self._cancel_arm()
        self.state.pending = None
        return decision


def wilder_rsi(close: pd.Series, period: int = 6) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    values = pd.to_numeric(close, errors="raise").astype(float)
    delta = values.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    result = pd.Series(np.nan, index=values.index, dtype=float)
    if len(values) <= period:
        return result

    avg_gain = float(gain.iloc[1 : period + 1].mean())
    avg_loss = float(loss.iloc[1 : period + 1].mean())

    def rsi_value(up: float, down: float) -> float:
        if down == 0.0 and up == 0.0:
            return 50.0
        if down == 0.0:
            return 100.0
        if up == 0.0:
            return 0.0
        rs = up / down
        return 100.0 - 100.0 / (1.0 + rs)

    result.iloc[period] = rsi_value(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + float(gain.iloc[index])) / period
        avg_loss = (avg_loss * (period - 1) + float(loss.iloc[index])) / period
        result.iloc[index] = rsi_value(avg_gain, avg_loss)
    return result


def add_daily_indicators(
    daily: pd.DataFrame,
    *,
    ma_period: int = 7,
    atr_period: int = 7,
    rsi_period: int = 6,
    slope_lookback: int = 1,
    expected_phase_hour: int = 0,
) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = sorted(required - set(daily.columns))
    if missing:
        raise ValueError(f"missing daily columns: {missing}")
    if not isinstance(daily.index, pd.DatetimeIndex) or daily.index.tz is None:
        raise ValueError("daily index must be a timezone-aware DatetimeIndex")
    if not 0 <= expected_phase_hour <= 23:
        raise ValueError("expected_phase_hour must be in [0, 23]")
    if str(daily.index.tz) != "UTC" or not all(
        timestamp.minute == 0
        and timestamp.second == 0
        and timestamp.microsecond == 0
        and timestamp.hour == expected_phase_hour
        for timestamp in daily.index
    ):
        raise ValueError("daily index must use the expected UTC session opens")
    if not daily.index.is_monotonic_increasing or not daily.index.is_unique:
        raise ValueError("daily index must be sorted and unique")
    if (
        len(daily.index) > 1
        and not (daily.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all()
    ):
        raise ValueError("daily index must be consecutive for a 24/7 market")
    if min(ma_period, atr_period, rsi_period, slope_lookback) < 1:
        raise ValueError("indicator periods must be >= 1")

    output = daily.copy()
    for column in required:
        output[column] = pd.to_numeric(output[column], errors="raise").astype(float)
    if (
        not np.isfinite(output[["open", "high", "low", "close"]]).all().all()
        or (output[["open", "high", "low", "close"]] <= 0.0).any().any()
        or (output["high"] < output[["open", "close", "low"]].max(axis=1)).any()
        or (output["low"] > output[["open", "close", "high"]].min(axis=1)).any()
    ):
        raise ValueError("invalid OHLC values")

    previous_close = output["close"].shift(1)
    true_range = pd.concat(
        (
            output["high"] - output["low"],
            (output["high"] - previous_close).abs(),
            (output["low"] - previous_close).abs(),
        ),
        axis=1,
    ).max(axis=1)
    output["ma7"] = output["close"].rolling(ma_period, min_periods=ma_period).mean()
    output["atr7"] = true_range.rolling(atr_period, min_periods=atr_period).mean()
    output["rsi6"] = wilder_rsi(output["close"], rsi_period)
    output["slope_atr"] = (
        output["ma7"] - output["ma7"].shift(slope_lookback)
    ) / output["atr7"]
    return output
