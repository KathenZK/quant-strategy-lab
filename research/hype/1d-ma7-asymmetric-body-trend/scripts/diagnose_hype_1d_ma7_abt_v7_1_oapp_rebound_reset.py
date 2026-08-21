"""Diagnose V7.1 long-OAPP rebound confirmation without changing V7.1."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v7-1-oapp-rebound-reset-diagnostic-contract-2026-08-20.md"
)
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
V6_ABLATION_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_full_parameter_ablation.py"
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_1_oapp_rebound_reset_2026-08-20.json"
)

CANONICAL_RIGHT = 432
EXPECTED_CANONICAL_RETURN = 711.035936775286
EXPECTED_CANONICAL_MDD = -18.395542229660567
EXPECTED_CANONICAL_TRADES = 20
INCIDENT_ENTRY_TS = pd.Timestamp("2026-08-09T00:00:00Z")
INCIDENT_EXIT_TS = pd.Timestamp("2026-08-16T00:00:00Z")
INCIDENT_ENTRY_PRICE = 55.113
INCIDENT_EXIT_PRICE = 56.894
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
ARM_DESCRIPTIONS = {
    "CONTROL": "exact V7.1 OAPP confirmation",
    "RR": "eligible rebound resets confirmation to one",
    "AF05": "original confirmation plus absolute giveback >= 0.5 ATR7",
    "MAG05": "original confirmation plus close <= SMA7 + 0.5 ATR7",
}


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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class OAPPConfirmationPolicy:
    """Drop-in lifecycle exit policy for the three frozen diagnostic arms."""

    def __init__(
        self,
        engine: ModuleType,
        context: Any,
        mode: str,
        *,
        switch_index: int | None = None,
    ) -> None:
        if mode not in ARM_DESCRIPTIONS:
            raise ValueError(f"unknown mode: {mode}")
        self.engine = engine
        self.context = context
        self.mode = mode
        self.switch_index = switch_index
        self.previous_close: float | None = None
        self.entry_identity: tuple[int, float] | None = None
        self.events: list[dict[str, Any]] = []
        self.index_by_values: dict[tuple[float, float], int] = {}
        for index, (close, atr) in enumerate(
            zip(context.book.close, context.features.atr7, strict=True)
        ):
            key = (float(close), float(atr))
            if key in self.index_by_values:
                raise RuntimeError("close/ATR pair is not unique enough for policy audit")
            self.index_by_values[key] = index

    @staticmethod
    def rebound_count(
        *, active: bool, prior_count: int, previous_close: float | None, close: float
    ) -> int:
        if not active:
            return 0
        if prior_count <= 0 or previous_close is None:
            return 1
        return prior_count + 1 if close <= previous_close else 1

    def __call__(self, **kwargs: Any) -> tuple[str | None, int, int, int]:
        side = int(kwargs["side"])
        if side <= 0 or self.mode == "CONTROL":
            return self.engine._BASE.lifecycle_exit_decision(**kwargs)

        close = float(kwargs["signal_close"])
        atr = float(kwargs["atr"])
        index = self.index_by_values[(close, atr)]
        identity = (side, float(kwargs["entry_price"]))
        if identity != self.entry_identity:
            self.entry_identity = identity
            self.previous_close = None

        if self.switch_index is not None and index < self.switch_index:
            result = self.engine._BASE.lifecycle_exit_decision(**kwargs)
            self.previous_close = close
            return result

        long_exit = kwargs["long_exit"]
        active = self.engine._BASE._trail_trigger(
            side=1,
            spec=long_exit,
            peak_close=float(kwargs["highest_close"]),
            signal_close=close,
            entry_price=float(kwargs["entry_price"]),
            atr=atr,
            guard=float(kwargs["roundtrip_guard"]),
        )
        absolute_giveback_atr = (
            (float(kwargs["highest_close"]) - close) / atr
            if math.isfinite(atr) and atr > 0.0
            else math.nan
        )
        ma7 = float(self.context.features.ma7[index])
        ma_distance_atr = (
            (close - ma7) / atr
            if math.isfinite(ma7) and math.isfinite(atr) and atr > 0.0
            else math.nan
        )
        if self.mode == "AF05":
            active = active and absolute_giveback_atr >= 0.5
        elif self.mode == "MAG05":
            active = active and ma_distance_atr <= 0.5

        prior_count = int(kwargs["long_run"])
        if self.mode == "RR":
            long_run = self.rebound_count(
                active=active,
                prior_count=prior_count,
                previous_close=self.previous_close,
                close=close,
            )
        else:
            long_run = prior_count + 1 if active else 0
        reason = (
            f"long_mfe_{long_exit.mode}_trail_exit"
            if long_exit.enabled and long_run >= long_exit.confirm_days
            else None
        )
        self.events.append(
            {
                "index": index,
                "ts": pd.Timestamp(self.context.book.ts[index]).isoformat(),
                "mode": self.mode,
                "close": close,
                "previous_close": self.previous_close,
                "active": bool(active),
                "prior_count": prior_count,
                "new_count": long_run,
                "absolute_giveback_atr": absolute_giveback_atr,
                "ma_distance_atr": ma_distance_atr,
                "reason": reason,
            }
        )
        self.previous_close = close
        return reason, long_run, 0, 0


def extended_context(adapter: ModuleType) -> tuple[Any, Any]:
    frozen = adapter.load_context()
    original = frozen.original_harness
    original.HOURLY_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    original.FUNDING_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    market = original.load_market(0)
    context = replace(
        frozen,
        market=market,
        short_config=replace(frozen.short_config, cooldown_days=3),
    )
    canonical = replace(
        frozen,
        short_config=replace(frozen.short_config, cooldown_days=3),
    )
    return canonical, context


def fixed_variant(v6: ModuleType, engine: ModuleType, context: Any, mode: str) -> Any:
    return v6.Variant(
        name=mode,
        group="oapp_confirmation_diagnostic",
        change=ARM_DESCRIPTIONS[mode],
        long_config=context.long_config,
        short_config=context.short_config,
        oapp_config=v6.oapp_config(engine, arm_id=f"V7_1_{mode}_OAPP"),
        pehc_config=v6.fixed_pehc(engine, arm_id="PEHC_294"),
    )


def run_arm(
    v6: ModuleType,
    engine: ModuleType,
    context: Any,
    mode: str,
    *,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    include_funding: bool = True,
    switch_index: int | None = None,
    retain: bool = False,
) -> tuple[dict[str, Any], Any, OAPPConfirmationPolicy]:
    variant = fixed_variant(v6, engine, context, mode)
    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    entry_signal = engine._BASE.EntryQualitySignal(context.engine, variant.oapp_config.entry)
    leverage_policy = engine._BASE.LeveragePolicy(context, None)
    recorder = engine.HandoffRecorder()
    function, source_hash = engine.build_variant_function(
        context,
        variant.pehc_config,
        oapp_config=variant.oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        recorder=recorder,
    )
    policy = OAPPConfirmationPolicy(
        engine, context, mode, switch_index=switch_index
    )
    function.__globals__["wtl_exit_decision"] = policy
    left, right = window
    raw = function(
        context.book,
        context.features,
        long_config=variant.long_config,
        short_config=variant.short_config,
        start_index=v6.start_for(window),
        terminal_index=right,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{mode} became bankrupt")
    handoff_events = list(recorder.events)
    result = engine.PEHCExecutionResult(
        config=variant.pehc_config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        handoff_events=handoff_events,
        activation_counts={
            "shadow_start": sum(row["event"] == "shadow_start" for row in handoff_events),
            "handoff_accept": sum(row["event"] == "handoff_accept" for row in handoff_events),
            "long_trail_exit": sum(
                str(trade.get("exit_reason", "")).startswith("long_mfe_")
                for trade in raw.trades
            ),
            "short_rsi_exit": sum(
                str(trade.get("exit_reason", "")) == "short_rsi_take_profit"
                for trade in raw.trades
            ),
            "protective_stop": sum(
                str(trade.get("exit_reason", "")) == "protective_stop"
                for trade in raw.trades
            ),
        },
        rsi6=rsi6,
    )
    replay = v6.chronological_replay(
        context, raw, slippage=slippage, include_funding=include_funding
    )
    metrics = v6.normalize(raw, replay, result, days=right - left)
    metrics["source_sha256"] = source_hash
    metrics["policy_sha256"] = canonical_hash(
        {"mode": mode, "switch_index": switch_index, "description": ARM_DESCRIPTIONS[mode]}
    )
    return metrics, result, policy


def trade_signature(trade: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(trade["side"]),
        pd.Timestamp(trade["entry_ts"]).isoformat(),
        float(trade["entry_price"]),
        pd.Timestamp(trade["exit_ts"]).isoformat(),
        float(trade["exit_price"]),
        str(trade["exit_reason"]),
    )


def compact_trade(trade: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "side",
        "entry_ts",
        "entry_price",
        "exit_ts",
        "exit_price",
        "exit_reason",
        "bars",
        "gross_return_pct",
        "net_return_pct",
        "net_pnl",
    )
    return {field: trade.get(field) for field in fields if field in trade}


def changed_trades(control: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    prefix = 0
    for left, right in zip(control, candidate, strict=False):
        if trade_signature(left) != trade_signature(right):
            break
        prefix += 1
    return {
        "common_prefix_trades": prefix,
        "control_tail": [compact_trade(row) for row in control[prefix:]],
        "candidate_tail": [compact_trade(row) for row in candidate[prefix:]],
    }


def changed_long_episodes(
    control: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> dict[str, Any]:
    def by_entry(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            pd.Timestamp(row["entry_ts"]).isoformat(): row
            for row in rows
            if str(row["side"]) == "long"
        }

    control_by_entry = by_entry(control)
    candidate_by_entry = by_entry(candidate)
    changed: list[dict[str, Any]] = []
    for entry_ts in sorted(set(control_by_entry) & set(candidate_by_entry)):
        left = control_by_entry[entry_ts]
        right = candidate_by_entry[entry_ts]
        left_exit = trade_signature(left)[3:]
        right_exit = trade_signature(right)[3:]
        if left_exit != right_exit:
            changed.append(
                {
                    "entry_ts": entry_ts,
                    "entry_price": float(left["entry_price"]),
                    "control_exit": {
                        "ts": pd.Timestamp(left["exit_ts"]).isoformat(),
                        "price": float(left["exit_price"]),
                        "reason": str(left["exit_reason"]),
                    },
                    "candidate_exit": {
                        "ts": pd.Timestamp(right["exit_ts"]).isoformat(),
                        "price": float(right["exit_price"]),
                        "reason": str(right["exit_reason"]),
                    },
                }
            )
    return {
        "changed_shared_long_episodes": changed,
        "control_only_long_entries": sorted(set(control_by_entry) - set(candidate_by_entry)),
        "candidate_only_long_entries": sorted(set(candidate_by_entry) - set(control_by_entry)),
    }


def incident_table(engine: ModuleType, context: Any) -> list[dict[str, Any]]:
    start = next(
        index
        for index, ts in enumerate(context.book.ts)
        if pd.Timestamp(ts) == INCIDENT_ENTRY_TS
    )
    end = next(
        index
        for index, ts in enumerate(context.book.ts)
        if pd.Timestamp(ts) == pd.Timestamp("2026-08-19T00:00:00Z")
    )
    long_exit = engine._OAPP.TrailExit("fraction", 0.5, 0.10, 2)
    highest = INCIDENT_ENTRY_PRICE
    original_count = 0
    rr_count = 0
    previous_close: float | None = None
    rows: list[dict[str, Any]] = []
    for index in range(start, end + 1):
        close = float(context.book.close[index])
        highest = max(highest, close)
        atr = float(context.features.atr7[index])
        ma7 = float(context.features.ma7[index])
        active = engine._BASE._trail_trigger(
            side=1,
            spec=long_exit,
            peak_close=highest,
            signal_close=close,
            entry_price=INCIDENT_ENTRY_PRICE,
            atr=atr,
            guard=0.0028,
        )
        original_count = original_count + 1 if active else 0
        rr_count = OAPPConfirmationPolicy.rebound_count(
            active=active,
            prior_count=rr_count,
            previous_close=previous_close,
            close=close,
        )
        peak_profit = highest - INCIDENT_ENTRY_PRICE
        giveback = highest - close
        rows.append(
            {
                "signal_ts": pd.Timestamp(context.book.ts[index]).isoformat(),
                "next_open_ts": (
                    pd.Timestamp(context.book.ts[index + 1]).isoformat()
                    if index + 1 < context.book.count
                    else pd.Timestamp(context.book.terminal_ts).isoformat()
                ),
                "open": float(context.book.open[index]),
                "high": float(context.book.high[index]),
                "low": float(context.book.low[index]),
                "close": close,
                "sma7": ma7,
                "atr7": atr,
                "highest_close": highest,
                "giveback": giveback,
                "giveback_fraction": giveback / peak_profit if peak_profit > 0.0 else 0.0,
                "giveback_atr": giveback / atr,
                "close_minus_sma7_atr": (close - ma7) / atr,
                "original_eligible": bool(active),
                "original_count": original_count,
                "rr_count": rr_count,
                "rebound_vs_previous_close": (
                    close > previous_close if previous_close is not None else None
                ),
                "original_exit_next_open": bool(active and original_count >= 2),
                "rr_exit_next_open": bool(active and rr_count >= 2),
            }
        )
        previous_close = close
    return rows


def assert_control_anchor(metrics: dict[str, Any], result: Any) -> None:
    if not math.isclose(
        float(metrics["net_return_pct"]), EXPECTED_CANONICAL_RETURN, abs_tol=1e-8
    ):
        raise RuntimeError("canonical V7.1 return anchor drift")
    if not math.isclose(
        float(metrics["chronological_1h_mdd_pct"]), EXPECTED_CANONICAL_MDD, abs_tol=1e-8
    ):
        raise RuntimeError("canonical V7.1 MDD anchor drift")
    if int(metrics["closed_trades"]) != EXPECTED_CANONICAL_TRADES:
        raise RuntimeError("canonical V7.1 trade-count anchor drift")
    if len(result.raw.trades) != EXPECTED_CANONICAL_TRADES:
        raise RuntimeError("canonical retained trade count drift")


def assert_incident_trade(trade: dict[str, Any]) -> None:
    if pd.Timestamp(trade["entry_ts"]) != INCIDENT_ENTRY_TS:
        raise RuntimeError("incident entry timestamp drift")
    if pd.Timestamp(trade["exit_ts"]) != INCIDENT_EXIT_TS:
        raise RuntimeError("incident exit timestamp drift")
    if not math.isclose(float(trade["entry_price"]), INCIDENT_ENTRY_PRICE, abs_tol=1e-12):
        raise RuntimeError("incident entry price drift")
    if not math.isclose(float(trade["exit_price"]), INCIDENT_EXIT_PRICE, abs_tol=1e-12):
        raise RuntimeError("incident exit price drift")
    if str(trade["exit_reason"]) != "long_mfe_fraction_trail_exit":
        raise RuntimeError("incident exit reason drift")


def run(force: bool = False) -> dict[str, Any]:
    v6 = load_module(V6_ABLATION_PATH, "oapp_rr_v6_ablation")
    engine = load_module(ENGINE_PATH, "oapp_rr_pehc_engine")
    adapter = load_module(ADAPTER_PATH, "oapp_rr_v4_adapter")
    canonical_context, context = extended_context(adapter)
    incident_index = next(
        index
        for index, ts in enumerate(context.book.ts)
        if pd.Timestamp(ts) == INCIDENT_ENTRY_TS
    )

    canonical_metrics, canonical_result, _ = run_arm(
        v6,
        engine,
        canonical_context,
        "CONTROL",
        window=(0, CANONICAL_RIGHT),
        retain=True,
    )
    assert_control_anchor(canonical_metrics, canonical_result)

    canonical_path: dict[str, Any] = {"CONTROL": canonical_metrics}
    for mode in ARM_DESCRIPTIONS:
        if mode == "CONTROL":
            continue
        print(f"[canonical] {mode}")
        metrics, _, _ = run_arm(
            v6,
            engine,
            canonical_context,
            mode,
            window=(0, CANONICAL_RIGHT),
        )
        canonical_path[mode] = metrics

    full: dict[str, Any] = {}
    retained: dict[str, Any] = {}
    policy_events: dict[str, Any] = {}
    for mode in ARM_DESCRIPTIONS:
        print(f"[full] {mode}")
        metrics, result, policy = run_arm(
            v6,
            engine,
            context,
            mode,
            window=(0, context.book.count),
            retain=True,
        )
        full[mode] = metrics
        retained[mode] = result
        policy_events[mode] = policy.events

    control_trades = list(retained["CONTROL"].raw.trades)
    if [trade_signature(row) for row in control_trades[:EXPECTED_CANONICAL_TRADES]] != [
        trade_signature(row) for row in canonical_result.raw.trades
    ]:
        raise RuntimeError("extended control changed the canonical first 20 trades")
    if len(control_trades) != EXPECTED_CANONICAL_TRADES + 1:
        raise RuntimeError("extended control did not contain exactly one new trade")
    assert_incident_trade(control_trades[-1])

    stress: dict[str, Any] = {}
    recent: dict[str, Any] = {}
    for mode in ARM_DESCRIPTIONS:
        stress[mode] = {}
        for label, slippage, lag, funding in (
            ("slippage_8bps", STRESS_SLIPPAGE, 0, True),
            ("lag_1d", BASE_SLIPPAGE, 1, True),
            ("funding_off", BASE_SLIPPAGE, 0, False),
        ):
            print(f"[stress:{label}] {mode}")
            metrics, _, _ = run_arm(
                v6,
                engine,
                context,
                mode,
                window=(0, context.book.count),
                slippage=slippage,
                signal_lag=lag,
                include_funding=funding,
            )
            stress[mode][label] = metrics
        recent[mode] = {}
        for label, days in RECENT_SLICES.items():
            left = max(0, context.book.count - days)
            print(f"[recent:{label}] {mode}")
            metrics, _, _ = run_arm(
                v6,
                engine,
                context,
                mode,
                window=(left, context.book.count),
            )
            recent[mode][label] = metrics

    incident_counterfactual: dict[str, Any] = {}
    for mode in ARM_DESCRIPTIONS:
        print(f"[incident-switch] {mode}")
        metrics, result, policy = run_arm(
            v6,
            engine,
            context,
            mode,
            window=(0, context.book.count),
            switch_index=incident_index,
            retain=True,
        )
        trades = list(result.raw.trades)
        incident_trade = next(
            (
                row
                for row in trades
                if pd.Timestamp(row["entry_ts"]) == INCIDENT_ENTRY_TS
            ),
            None,
        )
        incident_counterfactual[mode] = {
            "metrics": metrics,
            "incident_trade": compact_trade(incident_trade) if incident_trade else None,
            "prevented_2026_08_16_exit": bool(
                incident_trade
                and pd.Timestamp(incident_trade["exit_ts"]) != INCIDENT_EXIT_TS
            ),
            "terminal_censored": bool(
                incident_trade
                and str(incident_trade["exit_reason"]) == "terminal_flatten"
            ),
            "policy_events_from_incident": [
                row for row in policy.events if int(row["index"]) >= incident_index
            ],
        }

    differences = {
        mode: changed_trades(
            control_trades,
            list(retained[mode].raw.trades),
        )
        for mode in ARM_DESCRIPTIONS
        if mode != "CONTROL"
    }
    long_episode_differences = {
        mode: changed_long_episodes(
            control_trades,
            list(retained[mode].raw.trades),
        )
        for mode in ARM_DESCRIPTIONS
        if mode != "CONTROL"
    }
    arm_assessment = {
        mode: {
            "canonical_return_delta_pp": (
                float(canonical_path[mode]["net_return_pct"])
                - float(canonical_path["CONTROL"]["net_return_pct"])
            ),
            "canonical_mdd_delta_pp": (
                float(canonical_path[mode]["chronological_1h_mdd_pct"])
                - float(canonical_path["CONTROL"]["chronological_1h_mdd_pct"])
            ),
            "extended_return_delta_pp": (
                float(full[mode]["net_return_pct"])
                - float(full["CONTROL"]["net_return_pct"])
            ),
            "extended_mdd_delta_pp": (
                float(full[mode]["chronological_1h_mdd_pct"])
                - float(full["CONTROL"]["chronological_1h_mdd_pct"])
            ),
            "prevents_incident_exit": bool(
                incident_counterfactual[mode]["prevented_2026_08_16_exit"]
            ),
            "incident_result_mature": not bool(
                incident_counterfactual[mode]["terminal_censored"]
            ),
        }
        for mode in ARM_DESCRIPTIONS
        if mode != "CONTROL"
    }
    payload = {
        "schema": "hype-1d-ma7-abt-v7-1-oapp-rebound-reset-diagnostic-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-ABT-V7.1",
        "verdict": {
            "production_action": "KEEP_V7_1",
            "research_action": "SHADOW_RR",
            "runner_change_authorized": False,
            "reason": (
                "RR fixes the disclosed rebound-confirmation event with the smallest semantic "
                "change, but loses return and worsens MDD on the canonical revealed history. "
                "The favorable August counterfactual remains terminal-censored, so RR is only "
                "a prospective shadow hypothesis."
            ),
        },
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "data_audit": sanitize(context.market.audit),
        "canonical_anchor": canonical_metrics,
        "canonical_path": canonical_path,
        "extended_control_incident_trade": compact_trade(control_trades[-1]),
        "arm_descriptions": ARM_DESCRIPTIONS,
        "full_path": full,
        "stress": stress,
        "recent_slices": recent,
        "incident_counterfactual": incident_counterfactual,
        "incident_daily_path": incident_table(engine, context),
        "changed_trade_episodes": differences,
        "changed_long_oapp_episodes": long_episode_differences,
        "arm_assessment": arm_assessment,
        "full_path_policy_events": policy_events,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "engine_sha256": sha256(ENGINE_PATH),
            "adapter_sha256": sha256(ADAPTER_PATH),
            "v6_ablation_helper_sha256": sha256(V6_ABLATION_PATH),
        },
        "notes": [
            "The 2026-08 incident and all extended data are revealed diagnostics, not clean OOS.",
            "Terminal flattening is mark-to-market censoring, not a mature strategy exit.",
            "No registered V7.1 file or runner implementation is changed by this diagnostic.",
        ],
    }
    document = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if (OUTPUT_PATH.exists() or sidecar.exists()) and not force:
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    digest = hashlib.sha256(document.encode()).hexdigest()
    sidecar.write_text(f"{digest}  {OUTPUT_PATH.name}\n", encoding="utf-8")
    return {"output": str(OUTPUT_PATH), "sha256": digest, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(force=args.force)
    summary = {
        "output": result["output"],
        "sha256": result["sha256"],
        "full_path": result["payload"]["full_path"],
        "incident_counterfactual": result["payload"]["incident_counterfactual"],
    }
    print(json.dumps(sanitize(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
