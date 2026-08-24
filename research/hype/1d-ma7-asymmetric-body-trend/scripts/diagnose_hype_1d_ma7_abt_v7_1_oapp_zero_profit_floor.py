"""Test a long-OAPP zero-profit floor on exact HYPE MA7 ABT V7.1."""

from __future__ import annotations

import argparse
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
BASE_DIAGNOSTIC_PATH = (
    SCRIPT_DIR / "diagnose_hype_1d_ma7_abt_v7_1_oapp_rebound_reset.py"
)
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v7-1-oapp-zero-profit-floor-diagnostic-contract-2026-08-20.md"
)
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_1_oapp_zero_profit_floor_2026-08-20.json"
)
V7_ABLATION_ARTIFACT = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json"
)


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


class ZeroProfitFloorPolicy:
    """Keep OAPP silent above entry after activation; exit at/below entry."""

    def __init__(self, engine: ModuleType, context: Any) -> None:
        self.engine = engine
        self.context = context
        self.entry_identity: tuple[int, float] | None = None
        self.activated = False
        self.events: list[dict[str, Any]] = []
        self.index_by_values = {
            (float(close), float(atr)): index
            for index, (close, atr) in enumerate(
                zip(context.book.close, context.features.atr7, strict=True)
            )
        }
        if len(self.index_by_values) != context.book.count:
            raise RuntimeError("close/ATR pair is not unique enough for policy audit")

    def __call__(self, **kwargs: Any) -> tuple[str | None, int, int, int]:
        side = int(kwargs["side"])
        if side <= 0:
            return self.engine._BASE.lifecycle_exit_decision(**kwargs)
        entry_price = float(kwargs["entry_price"])
        identity = (side, entry_price)
        if identity != self.entry_identity:
            self.entry_identity = identity
            self.activated = False
        close = float(kwargs["signal_close"])
        atr = float(kwargs["atr"])
        highest_close = float(kwargs["highest_close"])
        index = self.index_by_values[(close, atr)]
        activation_atr = float(kwargs["long_exit"].activation_atr)
        peak_profit_atr = (
            (highest_close - entry_price) / atr
            if math.isfinite(atr) and atr > 0.0
            else math.nan
        )
        if math.isfinite(peak_profit_atr) and peak_profit_atr >= activation_atr:
            self.activated = True
        active = self.activated and close <= entry_price
        long_run = 1 if active else 0
        reason = "long_mfe_fraction_trail_exit" if active else None
        self.events.append(
            {
                "index": index,
                "ts": pd.Timestamp(self.context.book.ts[index]).isoformat(),
                "entry_price": entry_price,
                "close": close,
                "highest_close": highest_close,
                "peak_profit_atr": peak_profit_atr,
                "activated": self.activated,
                "gross_profit_fraction": close / entry_price - 1.0,
                "exit": bool(active),
                "reason": reason,
            }
        )
        return reason, long_run, 0, 0


def run_zpf(
    base: ModuleType,
    v6: ModuleType,
    engine: ModuleType,
    context: Any,
    *,
    window: tuple[int, int],
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> tuple[dict[str, Any], Any, ZeroProfitFloorPolicy]:
    variant = base.fixed_variant(v6, engine, context, "CONTROL")
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
    policy = ZeroProfitFloorPolicy(engine, context)
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
        raise RuntimeError("ZPF became bankrupt")
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
    return metrics, result, policy


def off_variant(v6: ModuleType, engine: ModuleType, context: Any) -> Any:
    return v6.Variant(
        name="OAPP_OFF",
        group="known_comparator",
        change="disable long OAPP",
        long_config=context.long_config,
        short_config=context.short_config,
        oapp_config=v6.oapp_config(
            engine,
            arm_id="V7_1_LONG_OAPP_OFF",
            long_exit=engine._OAPP.TrailExit(),
        ),
        pehc_config=v6.fixed_pehc(engine, arm_id="PEHC_294"),
    )


def run_off(
    v6: ModuleType,
    engine: ModuleType,
    context: Any,
    *,
    window: tuple[int, int],
    retain: bool = False,
) -> tuple[dict[str, Any], Any]:
    return v6.run_variant(
        engine,
        context,
        off_variant(v6, engine, context),
        window=window,
        slippage=0.0004,
        signal_lag=0,
        include_funding=True,
        retain=retain,
    )


def signatures(base: ModuleType, result: Any) -> list[tuple[Any, ...]]:
    return [base.trade_signature(row) for row in result.raw.trades]


def incident_trade(base: ModuleType, result: Any) -> dict[str, Any] | None:
    row = next(
        (
            trade
            for trade in result.raw.trades
            if pd.Timestamp(trade["entry_ts"]) == base.INCIDENT_ENTRY_TS
        ),
        None,
    )
    return base.compact_trade(row) if row is not None else None


def run(force: bool = False) -> dict[str, Any]:
    base = load_module(BASE_DIAGNOSTIC_PATH, "zpf_base_diagnostic")
    v6 = base.load_module(base.V6_ABLATION_PATH, "zpf_v6_ablation")
    engine = base.load_module(base.ENGINE_PATH, "zpf_pehc_engine")
    adapter = base.load_module(base.ADAPTER_PATH, "zpf_v4_adapter")
    canonical_context, context = base.extended_context(adapter)

    control_canonical, control_canonical_result, _ = base.run_arm(
        v6,
        engine,
        canonical_context,
        "CONTROL",
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )
    base.assert_control_anchor(control_canonical, control_canonical_result)
    zpf_canonical, zpf_canonical_result, zpf_canonical_policy = run_zpf(
        base,
        v6,
        engine,
        canonical_context,
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )
    off_canonical, off_canonical_result = run_off(
        v6,
        engine,
        canonical_context,
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )

    control_extended, control_extended_result, _ = base.run_arm(
        v6,
        engine,
        context,
        "CONTROL",
        window=(0, context.book.count),
        retain=True,
    )
    base.assert_incident_trade(control_extended_result.raw.trades[-1])
    zpf_extended, zpf_extended_result, zpf_extended_policy = run_zpf(
        base,
        v6,
        engine,
        context,
        window=(0, context.book.count),
        retain=True,
    )
    off_extended, off_extended_result = run_off(
        v6,
        engine,
        context,
        window=(0, context.book.count),
        retain=True,
    )

    stress: dict[str, Any] = {}
    for label, slippage, lag, funding in (
        ("slippage_8bps", 0.0008, 0, True),
        ("lag_1d", 0.0004, 1, True),
        ("funding_off", 0.0004, 0, False),
    ):
        metrics, _, _ = run_zpf(
            base,
            v6,
            engine,
            context,
            window=(0, context.book.count),
            slippage=slippage,
            signal_lag=lag,
            include_funding=funding,
        )
        stress[label] = metrics

    recent: dict[str, Any] = {}
    for label, days in base.RECENT_SLICES.items():
        metrics, _, _ = run_zpf(
            base,
            v6,
            engine,
            context,
            window=(max(0, context.book.count - days), context.book.count),
        )
        recent[label] = metrics

    zpf_incident = incident_trade(base, zpf_extended_result)
    off_incident = incident_trade(base, off_extended_result)
    zpf_off_canonical_equal = signatures(base, zpf_canonical_result) == signatures(
        base, off_canonical_result
    )
    zpf_off_extended_equal = signatures(base, zpf_extended_result) == signatures(
        base, off_extended_result
    )
    existing_ablation = json.loads(V7_ABLATION_ARTIFACT.read_text(encoding="utf-8"))
    existing_off = existing_ablation["candidates"]["n_oapp_long_mode_off"]["stress"][
        "base_full"
    ]
    if not math.isclose(
        float(off_canonical["net_return_pct"]),
        float(existing_off["net_return_pct"]),
        abs_tol=1e-10,
    ):
        raise RuntimeError("OAPP-off comparator drift")

    zpf_exit_events = [row for row in zpf_extended_policy.events if row["exit"]]
    payload = {
        "schema": "hype-1d-ma7-abt-v7-1-oapp-zero-profit-floor-diagnostic-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-ABT-V7.1",
        "candidate": {
            "id": "ZPF",
            "rule": (
                "after 0.5 ATR peak-profit activation, suppress long OAPP above entry; "
                "exit next UTC open on the first signal close at or below entry"
            ),
        },
        "verdict": {
            "decision": "PENDING_MECHANICAL_EVALUATION",
            "runner_change_authorized": False,
        },
        "data_audit": base.sanitize(context.market.audit),
        "canonical": {
            "CONTROL": control_canonical,
            "ZPF": zpf_canonical,
            "OAPP_OFF": off_canonical,
        },
        "extended": {
            "CONTROL": control_extended,
            "ZPF": zpf_extended,
            "OAPP_OFF": off_extended,
        },
        "stress": stress,
        "recent_slices": recent,
        "incident": {
            "control": incident_trade(base, control_extended_result),
            "zpf": zpf_incident,
            "oapp_off": off_incident,
            "zpf_prevents_2026_08_16_exit": bool(
                zpf_incident
                and pd.Timestamp(zpf_incident["exit_ts"]) != base.INCIDENT_EXIT_TS
            ),
            "zpf_terminal_censored": bool(
                zpf_incident and zpf_incident["exit_reason"] == "terminal_flatten"
            ),
        },
        "path_equivalence": {
            "zpf_equals_oapp_off_canonical": zpf_off_canonical_equal,
            "zpf_equals_oapp_off_extended": zpf_off_extended_equal,
        },
        "changed_long_episodes_vs_control": base.changed_long_episodes(
            list(control_extended_result.raw.trades),
            list(zpf_extended_result.raw.trades),
        ),
        "zpf_exit_events": zpf_exit_events,
        "canonical_zpf_exit_events": [
            row for row in zpf_canonical_policy.events if row["exit"]
        ],
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "base_diagnostic_sha256": sha256(BASE_DIAGNOSTIC_PATH),
            "v7_ablation_artifact_sha256": sha256(V7_ABLATION_ARTIFACT),
        },
        "notes": [
            "ZPF preserves native MA7 and intraday protective exits.",
            "A zero-profit signal is not a break-even fill because execution is next-open and costs/funding remain.",
            "The August event is revealed and terminal-censored.",
        ],
    }
    control = payload["canonical"]["CONTROL"]
    candidate = payload["canonical"]["ZPF"]
    if zpf_off_canonical_equal:
        decision = "NO_GO_ZPF_PATH_EQUIVALENT_TO_OAPP_OFF"
    elif (
        float(candidate["net_return_pct"]) < float(control["net_return_pct"])
        and float(candidate["chronological_1h_mdd_pct"]) < -20.0
    ):
        decision = "NO_GO_ZPF_RETURN_LOWER_MDD_GATE_FAILED"
    else:
        decision = "SHADOW_ZPF_ONLY"
    payload["verdict"] = {
        "decision": decision,
        "production_action": "KEEP_V7_1",
        "runner_change_authorized": False,
    }

    document = (
        json.dumps(
            base.sanitize(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
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
    payload = result["payload"]
    print(
        json.dumps(
            {
                "output": result["output"],
                "sha256": result["sha256"],
                "verdict": payload["verdict"],
                "canonical": payload["canonical"],
                "extended": payload["extended"],
                "incident": payload["incident"],
                "path_equivalence": payload["path_equivalence"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
