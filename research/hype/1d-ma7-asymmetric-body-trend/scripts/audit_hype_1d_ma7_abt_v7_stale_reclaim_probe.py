"""Backtest stale-reclaim maturity probes on registered HYPE-1D-MA7-ABT-V7."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-stale-reclaim-probe-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_stale_reclaim_probe_2026-08-11.json"
BASE_ABLATION_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_four_mechanism_ablation.py"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TOP_N_STRESS = 20
EXPECTED_V7_RETURN = 711.035936775286
EXPECTED_V7_1H_MDD = -18.395542229660567
EXPECTED_V7_TRADES = 20


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_locked(payload: dict[str, Any]) -> str:
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if OUTPUT_PATH.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")
    return digest


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    name: str
    side_scope: str
    min_age_days: int
    max_age_days: int
    max_distance_atr: float
    probe_leverage: float
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.side_scope not in ("both", "long_only", "short_only"):
            raise ValueError("unknown side_scope")
        if self.min_age_days not in (1, 2):
            raise ValueError("min_age_days outside frozen set")
        if self.max_age_days not in (3, 4):
            raise ValueError("max_age_days outside frozen set")
        if self.min_age_days > self.max_age_days:
            raise ValueError("invalid age window")
        if self.max_distance_atr not in (1.00, 1.25, 1.50, math.inf):
            raise ValueError("max_distance_atr outside frozen set")
        if self.probe_leverage not in (0.25, 0.50, 1.00):
            raise ValueError("probe_leverage outside frozen set")

    def canonical(self) -> dict[str, Any]:
        row = asdict(self)
        if math.isinf(self.max_distance_atr):
            row["max_distance_atr"] = "INF"
        return row

    def applies_to(self, side: int) -> bool:
        return self.side_scope == "both" or (
            self.side_scope == "long_only" and side > 0
        ) or (self.side_scope == "short_only" and side < 0)


class StaleReclaimSignal:
    """Native V7 entry OR a narrow stale-reclaim maturity episode."""

    def __init__(
        self,
        native_signal: Any,
        long_config: Any,
        short_config: Any,
        config: ProbeConfig,
    ) -> None:
        self.native_signal = native_signal
        self.long_config = long_config
        self.short_config = short_config
        self.config = config
        self.events: list[dict[str, Any]] = []
        self.active_side = 0
        self.armed_at: int | None = None
        self.initial_buffer_pass = False
        self.initial_slope_pass = False
        self.cached_index: int | None = None
        self.cached_decisions = {1: False, -1: False}
        self.cached_sources = {1: None, -1: None}

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    @staticmethod
    def _side_name(side: int) -> str:
        return "long" if side > 0 else "short"

    def _record(self, event: str, index: int, side: int = 0, **extra: Any) -> None:
        row: dict[str, Any] = {"event": event, "signal_index": int(index), **extra}
        if side:
            row["side"] = self._side_name(side)
        self.events.append(row)

    def _clear(self) -> None:
        self.active_side = 0
        self.armed_at = None
        self.initial_buffer_pass = False
        self.initial_slope_pass = False

    def notify_exit(self, side: int, index: int, reason: str) -> None:
        if self.active_side:
            self._record(
                "stale_cancel_external_exit",
                index,
                self.active_side,
                exit_side=self._side_name(side),
                exit_reason=reason,
            )
        self._clear()

    def notify_entry(self, side: int, index: int, source: str) -> None:
        if self.active_side:
            self._record(
                "stale_cancel_external_entry",
                index,
                self.active_side,
                entry_side=self._side_name(side),
                source=source,
            )
        self._clear()

    def decision_source(self, side: int) -> str | None:
        return self.cached_sources[int(side)]

    def _native(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        return {
            1: bool(self.native_signal(self.long_config, book, features, index)),
            -1: bool(self.native_signal(self.short_config, book, features, index)),
        }

    def _raw_cross(self, book: Any, features: Any, index: int) -> int:
        if index < 1:
            return 0
        values = (
            float(book.close[index - 1]),
            float(features.ma7[index - 1]),
            float(book.close[index]),
            float(features.ma7[index]),
        )
        if not self._finite(*values):
            return 0
        prior_close, prior_ma7, close, ma7 = values
        if prior_close <= prior_ma7 and close > ma7:
            return 1
        if prior_close >= prior_ma7 and close < ma7:
            return -1
        return 0

    def _criteria(self, side: int, book: Any, features: Any, index: int) -> dict[str, Any]:
        config = self.long_config if side > 0 else self.short_config
        if config is None or index < int(config.slope_lookback):
            return {"finite": False}
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        atr7 = float(features.atr7[index])
        prior_ma7 = float(features.ma7[index - int(config.slope_lookback)])
        finite = self._finite(close, ma7, atr7, prior_ma7) and atr7 > 0.0
        if not finite:
            return {"finite": False}
        distance_atr = side * (close - ma7) / atr7
        slope_atr = side * (ma7 - prior_ma7) / atr7
        return {
            "finite": True,
            "distance_atr": distance_atr,
            "slope_atr": slope_atr,
            "buffer_pass": bool(distance_atr > float(config.entry_buffer_atr)),
            "slope_pass": bool(slope_atr > float(config.slope_min_atr)),
            "distance_cap_pass": bool(distance_atr <= self.config.max_distance_atr),
        }

    def _update_episode(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        decisions = {1: False, -1: False}
        cross_side = self._raw_cross(book, features, index)
        if cross_side and self.config.enabled and self.config.applies_to(cross_side):
            criteria = self._criteria(cross_side, book, features, index)
            if criteria.get("finite") and bool(criteria["distance_cap_pass"]):
                failed_maturity = not (
                    bool(criteria["buffer_pass"]) and bool(criteria["slope_pass"])
                )
                if failed_maturity:
                    self.active_side = cross_side
                    self.armed_at = int(index)
                    self.initial_buffer_pass = bool(criteria["buffer_pass"])
                    self.initial_slope_pass = bool(criteria["slope_pass"])
                    self._record(
                        "stale_episode_arm",
                        index,
                        cross_side,
                        distance_atr=criteria["distance_atr"],
                        slope_atr=criteria["slope_atr"],
                        buffer_pass=bool(criteria["buffer_pass"]),
                        slope_pass=bool(criteria["slope_pass"]),
                    )
        if not self.active_side or self.armed_at is None:
            return decisions
        side = self.active_side
        age = int(index - self.armed_at)
        if age > self.config.max_age_days:
            self._record("stale_episode_expire", index, side, age=age)
            self._clear()
            return decisions
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        if not self._finite(close, ma7) or side * (close - ma7) <= 0.0:
            self._record("stale_episode_recross", index, side, age=age)
            self._clear()
            return decisions
        if age < self.config.min_age_days:
            return decisions
        criteria = self._criteria(side, book, features, index)
        if not criteria.get("finite"):
            return decisions
        if (
            bool(criteria["buffer_pass"])
            and bool(criteria["slope_pass"])
            and bool(criteria["distance_cap_pass"])
        ):
            decisions[side] = True
            self._record(
                "stale_episode_confirm",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                distance_atr=criteria["distance_atr"],
                slope_atr=criteria["slope_atr"],
            )
            self._clear()
        return decisions

    def _evaluate(self, book: Any, features: Any, index: int) -> None:
        self.cached_index = int(index)
        self.cached_decisions = {1: False, -1: False}
        self.cached_sources = {1: None, -1: None}
        native = self._native(book, features, index)
        if native[1] or native[-1]:
            side = 1 if native[1] else -1
            self._record("native_entry_signal", index, side)
            self.cached_decisions = native
            self.cached_sources[side] = "native"
            self._clear()
            return
        episode = self._update_episode(book, features, index)
        if episode[1] or episode[-1]:
            side = 1 if episode[1] else -1
            self.cached_decisions = episode
            self.cached_sources[side] = "stale_reclaim"

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        if self.cached_index != index:
            self._evaluate(book, features, index)
        return bool(self.cached_decisions[int(config.side)])


class ProbeLeveragePolicy:
    def __init__(self, full_ablation: ModuleType, signal: StaleReclaimSignal, config: ProbeConfig) -> None:
        self.full_ablation = full_ablation
        self.signal = signal
        self.config = config
        self.pending_leverage = 1.0
        self.last_entry_leverage = 1.0
        self.events: list[dict[str, Any]] = []

    def set_entry_context(self, side: int, price: float, signal_index: int) -> None:
        source = self.signal.decision_source(int(side))
        leverage = self.config.probe_leverage if source == "stale_reclaim" else 1.0
        self.pending_leverage = leverage
        self.last_entry_leverage = leverage
        self.events.append(
            {
                "event": "probe_entry_target",
                "side": "long" if side > 0 else "short",
                "source": source or "unknown",
                "signal_index": int(signal_index),
                "price": float(price),
                "target_leverage": float(leverage),
            }
        )

    def __call__(self, equity: float, old_qty: float, target_side: int, price: float, cost_rate: float) -> tuple[float, float, float]:
        leverage = self.pending_leverage if target_side else 1.0
        qty, post_equity, turnover = self.full_ablation.target_quantity(
            equity,
            old_qty,
            target_side,
            price,
            cost_rate,
            leverage,
        )
        if target_side:
            self.pending_leverage = 1.0
        return qty, post_equity, turnover


def candidate_grid() -> list[ProbeConfig]:
    rows: list[ProbeConfig] = []
    for scope in ("both", "long_only", "short_only"):
        for min_age in (1, 2):
            for max_age in (3, 4):
                for max_distance in (1.00, 1.25, 1.50, math.inf):
                    for leverage in (1.00, 0.50, 0.25):
                        dist = "INF" if math.isinf(max_distance) else f"{max_distance:.2f}".replace(".", "p")
                        lev = f"{leverage:.2f}".replace(".", "p")
                        rows.append(
                            ProbeConfig(
                                name=f"S_{scope}_MIN{min_age}_MAX{max_age}_D{dist}_L{lev}",
                                side_scope=scope,
                                min_age_days=min_age,
                                max_age_days=max_age,
                                max_distance_atr=max_distance,
                                probe_leverage=leverage,
                            )
                        )
    if len(rows) != 144:
        raise RuntimeError("stale reclaim grid cardinality drift")
    return rows


def start_for(window: tuple[int, int]) -> int:
    left, right = window
    return left if left == 0 or right - left == 1 else left + 1


def run_raw(
    base: ModuleType,
    transition: ModuleType,
    full_ablation: ModuleType,
    context: Any,
    config: ProbeConfig,
    *,
    window: tuple[int, int],
    slippage: float,
    include_funding: bool,
    signal_lag: int,
    retain: bool,
) -> Any:
    repair_config = transition.TransitionRepairConfig(config.name)
    oapp_config = transition._PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = transition._BASE.wilder_rsi6(context.book.close)
    native_entry_signal = transition._BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    entry_signal = StaleReclaimSignal(
        native_entry_signal,
        context.long_config,
        context.short_config,
        config,
    )
    leverage_policy = ProbeLeveragePolicy(full_ablation, entry_signal, config)
    handoff_recorder = transition._PEHC.HandoffRecorder()
    repair_recorder = transition.RepairRecorder()
    arm = base.Arm(
        name=config.name,
        group="stale_reclaim_probe",
        description="stale reclaim maturity probe",
        transition_config=repair_config,
    )
    function, source_hash = base.build_variant_function(
        transition,
        context,
        arm,
        entry_signal=entry_signal,
        native_entry_signal=native_entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        handoff_recorder=handoff_recorder,
        repair_recorder=repair_recorder,
    )
    raw = function(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=context.short_config,
        start_index=start_for(window),
        terminal_index=window[1],
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    signal_events = list(entry_signal.events)
    cooldown_events = list(repair_recorder.events)
    handoff_events = list(handoff_recorder.events)
    counts = transition._counts(raw, signal_events, cooldown_events, handoff_events)
    for event in (
        "stale_episode_arm",
        "stale_episode_confirm",
        "stale_episode_expire",
        "stale_episode_recross",
    ):
        counts[event] = sum(row.get("event") == event for row in signal_events)
    counts["probe_entries"] = sum(
        row.get("event") == "probe_entry_target"
        and row.get("source") == "stale_reclaim"
        for row in leverage_policy.events
    )
    return SimpleNamespace(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        activation_counts=counts,
        signal_events=signal_events,
        cooldown_events=cooldown_events,
        handoff_events=handoff_events,
        leverage_events=list(leverage_policy.events),
        rsi6=rsi6,
    )


def normalize(
    base: ModuleType,
    full_ablation: ModuleType,
    context: Any,
    result: Any,
    *,
    days: int,
    slippage: float,
    include_funding: bool,
) -> dict[str, Any]:
    replay = full_ablation.chronological_replay(
        context,
        result.raw,
        slippage=slippage,
        include_funding=include_funding,
    )
    row = full_ablation.normalize(result.raw, replay, result, days=days)
    row["activation_counts"] = dict(result.activation_counts)
    row["leverage_events"] = list(result.leverage_events)
    row["source_sha256"] = result.source_sha256
    return row


def run_once(
    base: ModuleType,
    transition: ModuleType,
    full_ablation: ModuleType,
    context: Any,
    config: ProbeConfig,
    *,
    window: tuple[int, int],
    slippage: float,
    include_funding: bool,
    signal_lag: int,
    retain: bool,
) -> dict[str, Any]:
    result = run_raw(
        base,
        transition,
        full_ablation,
        context,
        config,
        window=window,
        slippage=slippage,
        include_funding=include_funding,
        signal_lag=signal_lag,
        retain=retain,
    )
    return normalize(
        base,
        full_ablation,
        context,
        result,
        days=window[1] - window[0],
        slippage=slippage,
        include_funding=include_funding,
    )


def base_verdict(row: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    ret_delta = row["net_return_pct"] - control["net_return_pct"]
    mdd_delta = row["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": row["closed_trades"] - control["closed_trades"],
        "full_dual_better": ret_delta > 0.0 and mdd_delta >= -1e-8,
    }


def stress_verdict(stress: dict[str, dict[str, Any]], control: dict[str, Any]) -> dict[str, Any]:
    base_row = stress["base_full"]
    ret_delta = base_row["net_return_pct"] - control["net_return_pct"]
    mdd_delta = base_row["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    blocks = [row for key, row in stress.items() if key.startswith("block_")]
    block_positive = sum(row["net_return_pct"] > 0.0 for row in blocks)
    passed = (
        ret_delta > 0.0
        and mdd_delta >= -1e-8
        and stress["slippage_8bps"]["net_return_pct"] > 0.0
        and stress["lag_1d"]["net_return_pct"] > 0.0
        and block_positive == len(blocks)
    )
    if passed:
        decision = "POST_REVEAL_CANDIDATE_ONLY"
    elif base_row["closed_trades"] > control["closed_trades"] + 5:
        decision = "FAIL / noise-releasing"
    elif ret_delta > 0.0 and mdd_delta < 0.0:
        decision = "FAIL / higher-return-higher-risk"
    else:
        decision = "FAIL"
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": base_row["closed_trades"] - control["closed_trades"],
        "block_positive_count": block_positive,
        "block_count": len(blocks),
        "decision": decision,
    }


def run_stress(
    base: ModuleType,
    transition: ModuleType,
    full_ablation: ModuleType,
    context: Any,
    config: ProbeConfig,
) -> dict[str, Any]:
    stress: dict[str, dict[str, Any]] = {}
    for key, window, slippage, include_funding, signal_lag in [
        ("base_full", FULL, BASE_SLIPPAGE, True, 0),
        ("slippage_8bps", FULL, STRESS_SLIPPAGE, True, 0),
        ("funding_off", FULL, BASE_SLIPPAGE, False, 0),
        ("lag_1d", FULL, BASE_SLIPPAGE, True, 1),
    ]:
        stress[key] = run_once(
            base,
            transition,
            full_ablation,
            context,
            config,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=False,
        )
    for block_index, window in enumerate(BLOCKS):
        stress[f"block_{block_index:02d}"] = run_once(
            base,
            transition,
            full_ablation,
            context,
            config,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    recent: dict[str, dict[str, Any]] = {}
    for label, days in RECENT_SLICES.items():
        window = (max(0, FULL[1] - days), FULL[1])
        recent[label] = run_once(
            base,
            transition,
            full_ablation,
            context,
            config,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    return {"stress": stress, "recent": recent}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen stale reclaim diagnostic")

    base = load_module(BASE_ABLATION_PATH, "stale_probe_base_ablation")
    v7_audit = load_module(base.V7_AUDIT_PATH, "stale_probe_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "stale_probe_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)
    transition = load_module(base.TRANSITION_PATH, "stale_probe_transition")
    full_ablation = load_module(base.FULL_ABLATION_PATH, "stale_probe_full_ablation")

    control_config = ProbeConfig(
        name="CTRL_EXACT_V7",
        side_scope="both",
        min_age_days=1,
        max_age_days=3,
        max_distance_atr=1.00,
        probe_leverage=1.00,
        enabled=False,
    )
    control = run_once(
        base,
        transition,
        full_ablation,
        context,
        control_config,
        window=FULL,
        slippage=BASE_SLIPPAGE,
        include_funding=True,
        signal_lag=0,
        retain=False,
    )
    if not (
        math.isclose(control["net_return_pct"], EXPECTED_V7_RETURN, abs_tol=0.05)
        and math.isclose(control["chronological_1h_mdd_pct"], EXPECTED_V7_1H_MDD, abs_tol=0.02)
        and int(control["closed_trades"]) == EXPECTED_V7_TRADES
    ):
        raise RuntimeError(f"V7 anchor drift: {control}")

    configs = candidate_grid()
    base_ranking = []
    for index, config in enumerate(configs, 1):
        print(f"[base {index:03d}/{len(configs)}] {config.name}")
        row = run_once(
            base,
            transition,
            full_ablation,
            context,
            config,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
        base_ranking.append(
            {
                "config": config.canonical(),
                "base_full": row,
                "base_verdict": base_verdict(row, control),
            }
        )
    base_ranking.sort(
        key=lambda row: (
            row["base_verdict"]["full_dual_better"],
            row["base_full"]["net_return_pct"],
            row["base_verdict"]["mdd_delta_vs_v7_pp"],
        ),
        reverse=True,
    )
    selected_names: list[str] = []
    for row in base_ranking:
        if row["base_verdict"]["full_dual_better"]:
            selected_names.append(row["config"]["name"])
    for row in base_ranking:
        name = row["config"]["name"]
        if name not in selected_names:
            selected_names.append(name)
        if len(selected_names) >= TOP_N_STRESS:
            break
    config_by_name = {config.name: config for config in configs}
    stressed: dict[str, Any] = {}
    for index, name in enumerate(selected_names, 1):
        print(f"[stress {index:02d}/{len(selected_names)}] {name}")
        row = run_stress(base, transition, full_ablation, context, config_by_name[name])
        row["config"] = config_by_name[name].canonical()
        row["verdict"] = stress_verdict(row["stress"], control)
        stressed[name] = row
    payload = {
        "schema": "hype-1d-ma7-abt-v7-stale-reclaim-probe-v1",
        "status": "COMPLETED_POST_REVEAL_DIAGNOSTIC",
        "research_state": "V7 unchanged / stale reclaim diagnostic only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": {"config": control_config.canonical(), "base_full": control},
        "grid_size": len(configs),
        "stress_evaluated": selected_names,
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "data_range": {
            "start": str(context.book.ts[FULL[0]]),
            "end": str(context.book.ts[FULL[1] - 1]),
            "terminal_ts": str(context.book.terminal_ts),
            "daily_bars": FULL[1] - FULL[0],
        },
        "cost_model": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance funding events when include_funding=true",
        },
        "base_ranking": base_ranking,
        "stressed": stressed,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "base_ablation_script_sha256": sha256(BASE_ABLATION_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v7_changed": False,
        "clean_oos_claim": False,
    }
    digest = write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(OUTPUT_PATH),
                "artifact_sha256": digest,
                "top5_base": [
                    {
                        "name": row["config"]["name"],
                        "ret": row["base_full"]["net_return_pct"],
                        "mdd": row["base_full"]["chronological_1h_mdd_pct"],
                        "trades": row["base_full"]["closed_trades"],
                        "stale_confirms": row["base_full"]["activation_counts"].get("stale_episode_confirm", 0),
                        "dual": row["base_verdict"]["full_dual_better"],
                    }
                    for row in base_ranking[:5]
                ],
                "stress_decisions": {
                    name: row["verdict"]["decision"] for name, row in stressed.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
