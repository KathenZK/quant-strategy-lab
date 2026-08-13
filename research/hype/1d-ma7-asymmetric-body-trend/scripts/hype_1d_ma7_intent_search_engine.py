"""Independent close-to-next-open engine for MA7 intent-search experiments.

The frozen original-trend engine is deliberately not imported here.  This
module makes the research intent explicit: raw MA7 crosses create directional
intent, an enabled slope gate is always a strict directional threshold, and every decision
records how its pending arm must be treated at execution.

RSI6 is an external, already-computed Wilder feature.  The state machine only
consumes the value supplied in :class:`CloseObservation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from math import isfinite
from typing import Iterable

import pandas as pd


class Side(IntEnum):
    SHORT = -1
    FLAT = 0
    LONG = 1


class FlatEntryMode(str, Enum):
    """How a flat machine is allowed to discover an entry."""

    FRESH_CROSS = "fresh_cross"
    PERSISTENT_REGIME = "persistent_regime"


class OverboughtMode(str, Enum):
    """Optional fresh-short qualification; it never bypasses a held band."""

    DISABLED = "disabled"
    EARLY_REVERSAL = "early_reversal"


class ArmEffect(str, Enum):
    """Explicit arm mutation applied when a decision fills."""

    CLEAR = "clear"
    PRESERVE = "preserve"


class ArmOrigin(str, Enum):
    """The confirmation rule depends on why an intent was armed."""

    FLAT_CROSS = "flat_cross"
    HELD_CROSS = "held_cross"


@dataclass(frozen=True)
class StrategyConfig:
    """All path-changing switches used by the structural intent search.

    ``arm_expiry_days`` counts *subsequent completed closes* after the signal
    close.  Therefore 0 permits only same-close confirmation, 1 permits the
    next close, 2 permits the next two closes, and ``None`` leaves held-position
    arms alive until a recross.  A failed flat fresh-cross is armed only for the
    deliberately searched finite choices 1 and 2.

    ``slope_lookback`` is configuration metadata: ``slope_atr`` is constructed
    causally by the outer feature layer and supplied in each observation.
    """

    prior_side_days: int = 1
    session_open_hour: int = 0
    tolerance_atr: float = 0.75
    slope_min_atr: float = 0.0
    slope_lookback: int = 1
    entry_slope_required: bool = True
    slope_loss_confirm_days: int = 1
    arm_expiry_days: int | None = None
    max_chase_atr: float = 0.75
    flat_entry_mode: FlatEntryMode = FlatEntryMode.FRESH_CROSS
    direct_reversal_enabled: bool = True
    hold_slope_exit_enabled: bool = True
    short_rsi_exit_enabled: bool = False
    short_rsi_exit_threshold: float = 30.0
    short_rsi_exit_days: int = 3
    roundtrip_cost_rate: float = 0.0028
    overbought_mode: OverboughtMode = OverboughtMode.DISABLED
    overbought_threshold: float = 70.0
    overbought_days: int = 3
    strict_previous_side: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "flat_entry_mode", FlatEntryMode(self.flat_entry_mode))
        object.__setattr__(self, "overbought_mode", OverboughtMode(self.overbought_mode))
        if self.prior_side_days < 1:
            raise ValueError("prior_side_days must be >= 1")
        if not 0 <= self.session_open_hour <= 23:
            raise ValueError("session_open_hour must be in [0, 23]")
        if not isfinite(self.tolerance_atr) or self.tolerance_atr < 0.0:
            raise ValueError("tolerance_atr must be finite and >= 0")
        if not isfinite(self.slope_min_atr) or self.slope_min_atr < 0.0:
            raise ValueError("slope_min_atr must be finite and >= 0")
        if self.slope_lookback not in (1, 2, 3):
            raise ValueError("slope_lookback must be 1, 2 or 3")
        if self.slope_loss_confirm_days not in (1, 2):
            raise ValueError("slope_loss_confirm_days must be 1 or 2")
        if self.arm_expiry_days not in (None, 0, 1, 2):
            raise ValueError("arm_expiry_days must be None, 0, 1 or 2")
        if not isfinite(self.max_chase_atr) or self.max_chase_atr < 0.0:
            raise ValueError("max_chase_atr must be finite and >= 0")
        if not 0.0 < self.short_rsi_exit_threshold < 100.0:
            raise ValueError("short_rsi_exit_threshold must be in (0, 100)")
        if self.short_rsi_exit_days < 1:
            raise ValueError("short_rsi_exit_days must be >= 1")
        if not isfinite(self.roundtrip_cost_rate) or not 0.0 <= self.roundtrip_cost_rate < 1.0:
            raise ValueError("roundtrip_cost_rate must be finite and in [0, 1)")
        if not 0.0 < self.overbought_threshold < 100.0:
            raise ValueError("overbought_threshold must be in (0, 100)")
        if self.overbought_days < 1:
            raise ValueError("overbought_days must be >= 1")
        if self.strict_previous_side:
            raise ValueError("intent search freezes inclusive prior-side equality")


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
        if not all(isfinite(value) for value in values):
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
    arm_effect: ArmEffect = ArmEffect.CLEAR

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
    armed_signal_ts: pd.Timestamp | None = None
    armed_origin: ArmOrigin | None = None
    armed_overbought_qualified: bool = False
    relations: list[int] = field(default_factory=list)
    rsi_values: list[float] = field(default_factory=list)
    slope_loss_run: int = 0
    short_rsi_run: int = 0
    pending: Decision | None = None
    last_close_ts: pd.Timestamp | None = None


def _relation(close: float, ma7: float) -> int:
    if close > ma7:
        return 1
    if close < ma7:
        return -1
    return 0


def fresh_cross(
    relations: Iterable[int],
    current_relation: int,
    target_side: Side,
    config: StrategyConfig,
) -> bool:
    """Return a strict signal-day cross after N inclusive opposite-side closes."""

    if target_side not in (Side.LONG, Side.SHORT):
        raise ValueError("target_side must be LONG or SHORT")
    if current_relation != int(target_side):
        return False
    history = list(relations)
    if len(history) < config.prior_side_days:
        return False
    # Long accepts prior close<=MA (relation -1/0); short accepts prior
    # close>=MA (relation +1/0).  The signal close itself remains strict.
    return all(
        value * int(target_side) <= 0
        for value in history[-config.prior_side_days :]
    )


def _slope_pass(side: Side, slope_atr: float, threshold: float) -> bool:
    if side not in (Side.LONG, Side.SHORT):
        raise ValueError("slope side must be directional")
    return int(side) * slope_atr > threshold


def _strict_streak(values: Iterable[float], days: int, threshold: float, *, above: bool) -> bool:
    history = list(values)
    if len(history) < days:
        return False
    if above:
        return all(value > threshold for value in history[-days:])
    return all(value < threshold for value in history[-days:])


class OriginalTrendMachine:
    """Causal state machine with an API compatible with the frozen harness.

    The class name is retained solely so a search harness can swap the engine
    module.  Its implementation and state contract are independent.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.state = MachineState()

    def seed_position(self, side: Side, entry_price: float) -> None:
        if self.state.pending is not None or self.state.relations:
            raise RuntimeError("seed_position is only allowed before observations")
        if side == Side.FLAT or not isfinite(entry_price) or entry_price <= 0.0:
            raise ValueError("seed position must be directional with a positive price")
        self.state.side = Side(side)
        self.state.entry_price = float(entry_price)
        self._reset_hold_counters()

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
            self._trim_history()
            self.state.last_close_ts = history[-1].ts

    def force_flat(self) -> None:
        self.external_exit(cancel_pending=False, arm_effect=ArmEffect.CLEAR)

    def external_exit(
        self,
        *,
        cancel_pending: bool,
        arm_effect: ArmEffect = ArmEffect.CLEAR,
    ) -> Decision | None:
        """Apply an external flatten and explicitly clear or preserve its arm.

        ``cancel_pending=True`` is required when an unfilled engine decision is
        being superseded.  The cancelled decision is returned for audit use.
        """

        effect = ArmEffect(arm_effect)
        cancelled = self.state.pending
        if cancelled is not None and not cancel_pending:
            raise RuntimeError("cannot externally exit with a pending decision")
        if cancel_pending:
            self.state.pending = None
        self.state.side = Side.FLAT
        self.state.entry_price = None
        self._reset_hold_counters()
        if effect == ArmEffect.CLEAR:
            self._cancel_arm()
        return cancelled

    def _arm(
        self,
        side: Side,
        signal_ts: pd.Timestamp,
        origin: ArmOrigin,
        *,
        overbought_qualified: bool = False,
    ) -> None:
        self.state.armed_side = side
        self.state.armed_age = 0
        self.state.armed_signal_ts = signal_ts
        self.state.armed_origin = origin
        self.state.armed_overbought_qualified = overbought_qualified

    def _cancel_arm(self) -> None:
        self.state.armed_side = Side.FLAT
        self.state.armed_age = 0
        self.state.armed_signal_ts = None
        self.state.armed_origin = None
        self.state.armed_overbought_qualified = False

    def _prepare_existing_arm(self, obs: CloseObservation) -> None:
        if self.state.armed_side == Side.FLAT:
            return
        signal_ts = self.state.armed_signal_ts
        if signal_ts is None:
            raise RuntimeError("armed state is missing armed_signal_ts")
        elapsed = (obs.ts - signal_ts) / pd.Timedelta(days=1)
        if elapsed < 0 or int(elapsed) != elapsed:
            raise RuntimeError("armed intent age must be a non-negative whole day")
        self.state.armed_age = int(elapsed)
        expiry = self.config.arm_expiry_days
        if expiry is not None and self.state.armed_age > expiry:
            self._cancel_arm()
            return
        # An armed intent is valid only while the close remains strictly on its
        # target side.  A touch of MA7 therefore cancels just like a recross.
        if _relation(obs.close, obs.ma7) != int(self.state.armed_side):
            self._cancel_arm()

    def _cancel_same_close_zero_expiry_arm(self, signal_ts: pd.Timestamp) -> None:
        if (
            self.config.arm_expiry_days == 0
            and self.state.armed_signal_ts == signal_ts
        ):
            self._cancel_arm()

    def _band_crossed(self, side: Side, obs: CloseObservation) -> bool:
        distance = int(side) * (obs.close - obs.ma7)
        return distance > self.config.tolerance_atr * obs.atr7

    def _held_band_confirms(self, side: Side, obs: CloseObservation) -> bool:
        if not self._band_crossed(side, obs):
            return False
        if _slope_pass(side, obs.slope_atr, self.config.slope_min_atr):
            return True
        return side == Side.SHORT and self.state.armed_overbought_qualified

    def _flat_arm_confirms(self, side: Side, obs: CloseObservation) -> bool:
        if _relation(obs.close, obs.ma7) != int(side):
            return False
        distance_atr = int(side) * (obs.close - obs.ma7) / obs.atr7
        slope_qualified = not self.config.entry_slope_required or _slope_pass(
            side, obs.slope_atr, self.config.slope_min_atr
        )
        return distance_atr <= self.config.max_chase_atr and slope_qualified

    def _prior_overbought(self) -> bool:
        return _strict_streak(
            self.state.rsi_values,
            self.config.overbought_days,
            self.config.overbought_threshold,
            above=True,
        )

    def _validate_next_close(self, obs: CloseObservation) -> None:
        if obs.ts.hour != self.config.session_open_hour:
            raise ValueError("observation timestamp does not match session_open_hour")
        if (
            self.state.last_close_ts is not None
            and obs.ts != self.state.last_close_ts + pd.Timedelta(days=1)
        ):
            raise RuntimeError("daily observations must be consecutive UTC sessions")

    def _trim_history(self) -> None:
        limit = max(self.config.prior_side_days, self.config.overbought_days, 1)
        self.state.relations = self.state.relations[-limit:]
        self.state.rsi_values = self.state.rsi_values[-limit:]

    def _record_observation(self, obs: CloseObservation) -> None:
        self.state.relations.append(_relation(obs.close, obs.ma7))
        self.state.rsi_values.append(obs.rsi6)
        self._trim_history()
        self.state.last_close_ts = obs.ts

    def _reset_hold_counters(self) -> None:
        self.state.slope_loss_run = 0
        self.state.short_rsi_run = 0

    def _update_hold_counters(self, obs: CloseObservation) -> None:
        side = self.state.side
        if side == Side.FLAT:
            self._reset_hold_counters()
            return
        if _slope_pass(side, obs.slope_atr, self.config.slope_min_atr):
            self.state.slope_loss_run = 0
        else:
            # The loss contract is directional slope <= theta.
            self.state.slope_loss_run += 1
        if side == Side.SHORT and self.config.short_rsi_exit_enabled:
            if obs.rsi6 < self.config.short_rsi_exit_threshold:
                self.state.short_rsi_run += 1
            else:
                self.state.short_rsi_run = 0
        else:
            self.state.short_rsi_run = 0

    def _short_rsi_take_profit(self, obs: CloseObservation) -> bool:
        if (
            not self.config.short_rsi_exit_enabled
            or self.state.short_rsi_run < self.config.short_rsi_exit_days
            or self.state.entry_price is None
        ):
            return False
        gross_short_profit = (self.state.entry_price - obs.close) / self.state.entry_price
        return gross_short_profit > self.config.roundtrip_cost_rate

    def _flat_decision(self, obs: CloseObservation, fresh_up: bool, fresh_down: bool) -> Decision | None:
        if self.state.armed_side in (Side.LONG, Side.SHORT):
            target = self.state.armed_side
            if self.state.armed_origin == ArmOrigin.FLAT_CROSS:
                confirmed = self._flat_arm_confirms(target, obs)
                reason = f"flat_armed_slope_confirm_{target.name.lower()}"
            elif self.state.armed_origin == ArmOrigin.HELD_CROSS:
                confirmed = self._held_band_confirms(target, obs)
                reason = f"held_arm_band_confirm_{target.name.lower()}"
            else:
                raise RuntimeError("armed state is missing armed_origin")
            if confirmed:
                return Decision(obs.ts, Side.FLAT, target, reason, ArmEffect.CLEAR)

        relation = _relation(obs.close, obs.ma7)
        if self.config.flat_entry_mode == FlatEntryMode.PERSISTENT_REGIME:
            if relation in (-1, 1):
                target = Side(relation)
                if not self.config.entry_slope_required or _slope_pass(
                    target, obs.slope_atr, self.config.slope_min_atr
                ):
                    return Decision(
                        obs.ts,
                        Side.FLAT,
                        target,
                        f"persistent_regime_{target.name.lower()}",
                        ArmEffect.CLEAR,
                    )
            return None

        for target, crossed in ((Side.LONG, fresh_up), (Side.SHORT, fresh_down)):
            if not crossed:
                continue
            slope_qualified = _slope_pass(
                target, obs.slope_atr, self.config.slope_min_atr
            )
            overbought_qualified = (
                target == Side.SHORT
                and self.config.overbought_mode == OverboughtMode.EARLY_REVERSAL
                and self._prior_overbought()
            )
            entry_qualified = (
                not self.config.entry_slope_required
                or slope_qualified
                or overbought_qualified
            )
            if entry_qualified:
                reason = f"fresh_cross_{target.name.lower()}"
                if overbought_qualified and not slope_qualified:
                    reason = "fresh_cross_short_overbought"
                return Decision(
                    obs.ts,
                    Side.FLAT,
                    target,
                    reason,
                    ArmEffect.CLEAR,
                )
            if self.config.arm_expiry_days in (1, 2):
                self._arm(
                    target,
                    obs.ts,
                    ArmOrigin.FLAT_CROSS,
                    overbought_qualified=overbought_qualified,
                )
            return None
        return None

    def _reversal_decision(self, obs: CloseObservation, target: Side, reason: str) -> Decision:
        if self.config.direct_reversal_enabled:
            return Decision(obs.ts, self.state.side, target, reason, ArmEffect.CLEAR)
        return Decision(
            obs.ts,
            self.state.side,
            Side.FLAT,
            f"{reason}_flat",
            ArmEffect.PRESERVE,
        )

    def _held_decision(self, obs: CloseObservation, fresh_up: bool, fresh_down: bool) -> Decision | None:
        side = self.state.side
        target = Side(-int(side))
        reverse_cross = fresh_down if side == Side.LONG else fresh_up
        if reverse_cross:
            frozen_overbought = (
                target == Side.SHORT
                and self.config.overbought_mode == OverboughtMode.EARLY_REVERSAL
                and self._prior_overbought()
            )
            self._arm(
                target,
                obs.ts,
                ArmOrigin.HELD_CROSS,
                overbought_qualified=frozen_overbought,
            )

        # Priority 1: an armed adverse band with frozen direction qualification.
        if self.state.armed_side == target and self._held_band_confirms(target, obs):
            suffix = ""
            if (
                target == Side.SHORT
                and self.state.armed_overbought_qualified
                and not _slope_pass(target, obs.slope_atr, self.config.slope_min_atr)
            ):
                suffix = "_overbought"
            return self._reversal_decision(
                obs,
                target,
                f"held_arm_band_confirm_{target.name.lower()}{suffix}",
            )

        # Expiry zero means the newly-created intent cannot wait for any later
        # close.  Cancel it before lower-priority flat exits preserve state.
        self._cancel_same_close_zero_expiry_arm(obs.ts)

        # Priority 2: short RSI take profit after actual held-short closes only.
        if side == Side.SHORT and self._short_rsi_take_profit(obs):
            return Decision(
                obs.ts,
                Side.SHORT,
                Side.FLAT,
                "short_rsi_take_profit",
                ArmEffect.CLEAR,
            )

        # Priority 3: C consecutive held closes at directional slope <= theta.
        if (
            self.config.hold_slope_exit_enabled
            and self.state.slope_loss_run >= self.config.slope_loss_confirm_days
        ):
            return Decision(
                obs.ts,
                side,
                Side.FLAT,
                f"{side.name.lower()}_slope_loss",
                ArmEffect.CLEAR,
            )
        return None

    def on_close(self, obs: CloseObservation) -> Decision | None:
        if self.state.pending is not None:
            raise RuntimeError("pending close decision must execute at the next open")
        self._validate_next_close(obs)
        self._prepare_existing_arm(obs)

        relation = _relation(obs.close, obs.ma7)
        fresh_up = fresh_cross(self.state.relations, relation, Side.LONG, self.config)
        fresh_down = fresh_cross(self.state.relations, relation, Side.SHORT, self.config)
        self._update_hold_counters(obs)

        if self.state.side == Side.FLAT:
            decision = self._flat_decision(obs, fresh_up, fresh_down)
        else:
            decision = self._held_decision(obs, fresh_up, fresh_down)

        self._record_observation(obs)
        self.state.pending = decision
        return decision

    def observe_pending_close(self, obs: CloseObservation) -> None:
        """Advance observable state while an execution-delay decision is frozen."""

        if self.state.pending is None:
            raise RuntimeError("pending-close observation requires a decision")
        self._validate_next_close(obs)
        self._prepare_existing_arm(obs)
        self._update_hold_counters(obs)
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
        if not isfinite(fill_price) or fill_price <= 0.0:
            raise ValueError("fill_price must be positive and finite")

        self.state.side = decision.target_side
        self.state.entry_price = (
            None if decision.target_side == Side.FLAT else float(fill_price)
        )
        self._reset_hold_counters()
        if decision.arm_effect == ArmEffect.CLEAR:
            self._cancel_arm()
        self.state.pending = None
        return decision
