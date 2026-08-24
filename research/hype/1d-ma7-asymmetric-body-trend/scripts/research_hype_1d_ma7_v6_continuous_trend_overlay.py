"""Diagnostic-only continuous-trend overlay audit on frozen V6 / PEHC_294."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-v6-continuous-trend-overlay-contract-2026-08-10.md"
)
DTEC_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_delayed_episode_engine.py"
TRANSITION_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_transition_repair_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
SELF_PATH = Path(__file__).resolve()

OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_v6_continuous_trend_overlay_2026-08-10.json"
)

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
FORWARD_DAYS = 5
ROUNDTRIP_GUARD = 0.0028
EXPECTED_V6_RETURN = 617.1070876096227
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19


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


def canonical_hash(value: Any) -> str:
    document = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(document.encode()).hexdigest()


def sidecar(path: Path) -> Path:
    return Path(f"{path}.sha256")


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> str:
    if path.exists() and not force:
        raise RuntimeError(f"refusing to overwrite {path}")
    document = json.dumps(sanitize(payload), indent=2, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256((document + "\n").encode()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document + "\n", encoding="utf-8")
    sidecar(path).write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, Any]:
    adapter = load_module(ADAPTER_PATH, "cto_adapter_runtime")
    risk = load_module(RISK_PATH, "cto_risk_runtime")
    dtec = load_module(DTEC_ENGINE_PATH, "cto_dtec_engine_runtime")
    transition = load_module(TRANSITION_ENGINE_PATH, "cto_transition_engine_runtime")
    return dtec, transition, risk, adapter, adapter.load_context()


def start_for(window: tuple[int, int]) -> int:
    left, right = window
    return left if left == 0 or right - left == 1 else left + 1


def annualized_return(equity_multiple: float, days: int) -> float:
    return (equity_multiple ** (365.0 / days) - 1.0) * 100.0


def economic_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "entry_ts",
        "exit_ts",
        "side",
        "entry_price",
        "exit_price",
        "exit_reason",
        "net_return",
        "net_pnl",
        "bars_held",
    )
    return [{field: row.get(field) for field in fields} for row in trades]


def trade_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("entry_ts"),
        row.get("exit_ts"),
        row.get("side"),
        row.get("entry_price"),
        row.get("exit_price"),
        row.get("exit_reason"),
    )


def normalize_metrics(raw: Any, replay: Any, *, days: int) -> dict[str, Any]:
    metrics = raw.metrics
    equity_multiple = float(metrics["equity_multiple"])
    return {
        "equity_multiple": equity_multiple,
        "net_return_pct": float(metrics["net_return_pct"]),
        "annualized_return_pct": annualized_return(equity_multiple, days),
        "chronological_1h_mdd_pct": float(replay.chronological_1h_mdd_pct),
        "daily_extreme_mdd_pct": float(metrics["max_drawdown_pct"]),
        "closed_trades": int(metrics["closed_trades"]),
        "long_trades": int(metrics["long_trades"]),
        "short_trades": int(metrics["short_trades"]),
        "win_rate": float(metrics["win_rate"]),
        "profit_factor": float(metrics["profit_factor"]),
        "turnover_multiple": float(metrics["turnover_multiple"]),
        "cost_pct_initial": float(metrics["cost_pct_initial"]),
        "funding_pct_initial": float(metrics["funding_pct_initial"]),
        "max_marked_leverage": float(replay.max_marked_leverage),
        "bankrupt_intraday": bool(metrics["bankrupt_intraday"]),
        "worst_ts": replay.worst_ts,
        "worst_trade_index": replay.worst_trade_index,
    }


def trend_labels(
    events: list[dict[str, Any]],
    context: Any,
    *,
    confirm_names: tuple[str, ...],
    arm_names: tuple[str, ...],
    start_index: int,
    terminal_index: int,
) -> dict[str, Any]:
    labels: list[dict[str, Any]] = []
    arms = [
        row
        for row in events
        if row.get("event") in arm_names
        and start_index <= int(row.get("signal_index", -1))
        and int(row.get("signal_index", -1)) + FORWARD_DAYS < terminal_index
    ]
    confirms = [
        row
        for row in events
        if row.get("event") in confirm_names
        and start_index <= int(row.get("signal_index", -1))
        and int(row.get("signal_index", -1)) + FORWARD_DAYS < terminal_index
    ]
    for event in confirms:
        index = int(event["signal_index"])
        side_name = str(event["side"])
        side = 1 if side_name == "long" else -1
        close = float(context.book.close[index])
        future = float(context.book.close[index + FORWARD_DAYS])
        direction_return = side * (future / close - 1.0)
        same_side = 0
        worst_adverse = 0.0
        for offset in range(index + 1, index + FORWARD_DAYS + 1):
            offset_close = float(context.book.close[offset])
            offset_ma = float(context.features.ma7[offset])
            if math.isfinite(offset_close) and math.isfinite(offset_ma):
                same_side += int(side * (offset_close - offset_ma) > 0.0)
                path_return = side * (offset_close / close - 1.0)
                worst_adverse = min(worst_adverse, path_return)
        direction_hit = direction_return > ROUNDTRIP_GUARD
        persistence_hit = same_side >= 3
        labels.append(
            {
                "signal_index": index,
                "side": side_name,
                "direction_return_5d": direction_return,
                "same_side_closes_5d": same_side,
                "worst_adverse_close_return_5d": worst_adverse,
                "direction_hit": direction_hit,
                "persistence_hit": persistence_hit,
                "trend_hit": bool(direction_hit and persistence_hit),
            }
        )

    def summary(side: str | None) -> dict[str, Any]:
        rows = labels if side is None else [row for row in labels if row["side"] == side]
        hits = sum(bool(row["trend_hit"]) for row in rows)
        return {
            "evaluable": len(rows),
            "hits": hits,
            "precision": hits / len(rows) if rows else None,
        }

    return {
        "horizon_days": FORWARD_DAYS,
        "roundtrip_guard": ROUNDTRIP_GUARD,
        "evaluable_arms": len(arms),
        "evaluable_confirms": len(labels),
        "capture_rate": len(labels) / len(arms) if arms else None,
        "combined": summary(None),
        "long": summary("long"),
        "short": summary("short"),
        "labels": labels,
    }


def candidate_specs(dtec: ModuleType, transition: ModuleType) -> list[dict[str, Any]]:
    long_params = dtec.EpisodeParams(
        persistence_days=3,
        slope_lookback=2,
        slope_min_atr=0.04,
        max_distance_atr=1.5,
        max_age_days=5,
    )
    short_params = dtec.EpisodeParams(
        persistence_days=2,
        slope_lookback=2,
        slope_min_atr=0.0,
        max_distance_atr=1.0,
        max_age_days=5,
    )
    return [
        {
            "arm_id": "CTO_L189",
            "family": "dtec",
            "config": dtec.DTECConfig("CTO_L189", long=long_params),
            "confirm_names": ("confirm_delayed_episode",),
            "arm_names": ("arm_raw_cross",),
        },
        {
            "arm_id": "CTO_S005",
            "family": "dtec",
            "config": dtec.DTECConfig("CTO_S005", short=short_params),
            "confirm_names": ("confirm_delayed_episode",),
            "arm_names": ("arm_raw_cross",),
        },
        {
            "arm_id": "CTO_L189_S005",
            "family": "dtec",
            "config": dtec.DTECConfig("CTO_L189_S005", long=long_params, short=short_params),
            "confirm_names": ("confirm_delayed_episode",),
            "arm_names": ("arm_raw_cross",),
        },
        {
            "arm_id": "CTO_C001",
            "family": "transition",
            "config": transition.TransitionRepairConfig(
                "CTO_C001",
                cooldown_mode="DIRECTIONAL",
                same_side_cooldown_days=1,
                episode_enabled=True,
                episode_max_age_days=3,
                maturity_mode="BUFFER",
                recross_cancels=True,
                anti_chase_cap_atr=0.75,
                rsi_reobserve_enabled=False,
            ),
            "confirm_names": ("episode_confirm",),
            "arm_names": ("episode_arm_raw_cross",),
        },
    ]


def run_engine(
    *,
    dtec: ModuleType,
    transition: ModuleType,
    risk: ModuleType,
    context: Any,
    spec: dict[str, Any] | None,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    start = start_for(window)
    family = "control" if spec is None else str(spec["family"])
    if spec is None:
        result = dtec.run_v6(
            context,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )
        arm_id = "C000_EXACT_V6"
        events: list[dict[str, Any]] = []
        accuracy = trend_labels(
            events,
            context,
            confirm_names=(),
            arm_names=(),
            start_index=start,
            terminal_index=window[1],
        )
    elif family == "dtec":
        result = dtec.run_variant(
            context,
            spec["config"],
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )
        arm_id = str(spec["arm_id"])
        events = list(result.episode_events)
        accuracy = trend_labels(
            events,
            context,
            confirm_names=spec["confirm_names"],
            arm_names=spec["arm_names"],
            start_index=start,
            terminal_index=window[1],
        )
    elif family == "transition":
        result = transition.run_variant(
            context,
            spec["config"],
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )
        arm_id = str(spec["arm_id"])
        events = list(result.signal_events)
        accuracy = trend_labels(
            events,
            context,
            confirm_names=spec["confirm_names"],
            arm_names=spec["arm_names"],
            start_index=start,
            terminal_index=window[1],
        )
    else:
        raise ValueError(f"unknown candidate family: {family}")

    replay = risk.replay_chronological_1h(
        context,
        result.raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    if not all(replay.parity.values()) or bool(result.raw.metrics["bankrupt_intraday"]):
        raise RuntimeError(f"ledger failure: {arm_id}")
    trades = economic_trades(result.raw.trades)
    days = window[1] - start
    payload = {
        "status": "PASS",
        "arm_id": arm_id,
        "family": family,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "slippage": slippage,
        "include_funding": include_funding,
        "signal_lag": signal_lag,
        "config": spec["config"].canonical() if spec is not None else None,
        "metrics": normalize_metrics(result.raw, replay, days=days),
        "accuracy": accuracy,
        "activation_counts": dict(result.activation_counts),
        "events": events,
        "handoff_events": list(result.handoff_events),
        "trades": trades,
        "trades_sha256": canonical_hash(trades),
        "source_sha256": result.source_sha256,
    }
    if family == "transition":
        payload["cooldown_events"] = list(result.cooldown_events)
    if retain:
        payload["path"] = list(result.raw.path)
        payload["replay"] = replay.canonical()
    return payload


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    cm = candidate["metrics"]
    vm = control["metrics"]
    return_delta = float(cm["net_return_pct"]) - float(vm["net_return_pct"])
    mdd_delta = float(cm["chronological_1h_mdd_pct"]) - float(
        vm["chronological_1h_mdd_pct"]
    )
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "return_higher": return_delta > 0.0,
        "mdd_smaller": mdd_delta > 0.0,
        "dual_improvement": return_delta > 0.0 and mdd_delta > 0.0,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
        "trade_count_delta": int(cm["closed_trades"]) - int(vm["closed_trades"]),
        "economic_path_changed": candidate["trades_sha256"] != control["trades_sha256"],
    }


def aggregate_blocks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in rows]
    equity = math.prod(float(row["equity_multiple"]) for row in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "worst_block_mdd_pct": min(
            float(row["chronological_1h_mdd_pct"]) for row in metrics
        ),
        "closed_trades": sum(int(row["closed_trades"]) for row in metrics),
        "positive_blocks": sum(float(row["net_return_pct"]) > 0.0 for row in metrics),
    }


def opportunity_cost(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    candidate_trades = list(candidate["trades"])
    control_trades = list(control["trades"])
    candidate_counts = Counter(trade_identity(row) for row in candidate_trades)
    control_counts = Counter(trade_identity(row) for row in control_trades)
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for row in candidate_trades:
        identity = trade_identity(row)
        if candidate_counts[identity] > control_counts[identity]:
            added.append(row)
            candidate_counts[identity] -= 1
    candidate_counts = Counter(trade_identity(row) for row in candidate_trades)
    for row in control_trades:
        identity = trade_identity(row)
        if control_counts[identity] > candidate_counts[identity]:
            removed.append(row)
            control_counts[identity] -= 1
    keys = ("long_trail_exit", "short_rsi_exit", "shadow_start", "handoff_accept")
    activation_delta = {
        key: int(candidate["activation_counts"].get(key, 0))
        - int(control["activation_counts"].get(key, 0))
        for key in keys
    }
    return {
        "added_trades": added,
        "removed_v6_trades": removed,
        "added_count": len(added),
        "removed_count": len(removed),
        "activation_delta": activation_delta,
        "core_chain_preserved": all(value >= 0 for value in activation_delta.values()),
    }


def gate(
    *,
    full: dict[str, Any],
    stress: dict[str, Any],
    funding_off: dict[str, Any],
    lag: dict[str, Any],
    blocks: list[dict[str, Any]],
    control_full: dict[str, Any],
    control_stress: dict[str, Any],
    control_funding_off: dict[str, Any],
    control_lag: dict[str, Any],
    control_blocks: list[dict[str, Any]],
    cost: dict[str, Any],
) -> dict[str, Any]:
    full_cmp = compare(full, control_full)
    stress_cmp = compare(stress, control_stress)
    funding_cmp = compare(funding_off, control_funding_off)
    lag_cmp = compare(lag, control_lag)
    block_cmps = [
        compare(row, control)
        for row, control in zip(blocks, control_blocks, strict=True)
    ]
    accuracy = full["accuracy"]["combined"]
    checks = {
        "full_return_higher": full_cmp["return_higher"],
        "full_mdd_smaller": full_cmp["mdd_smaller"],
        "stress_not_double_worse": not stress_cmp["double_worse"],
        "funding_off_not_double_worse": not funding_cmp["double_worse"],
        "lag_not_double_worse": not lag_cmp["double_worse"],
        "blocks_not_double_worse": all(not row["double_worse"] for row in block_cmps),
        "confirmations_ge_2": int(accuracy["evaluable"]) >= 2,
        "precision_ge_055": (
            accuracy["precision"] is not None and float(accuracy["precision"]) >= 0.55
        ),
        "core_chain_preserved": bool(cost["core_chain_preserved"]),
        "nonbankrupt": not bool(full["metrics"]["bankrupt_intraday"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "comparisons": {
            "full": full_cmp,
            "stress_8bps": stress_cmp,
            "funding_off": funding_cmp,
            "signal_lag_plus_1d": lag_cmp,
            "blocks": block_cmps,
        },
    }


def recent_windows(count: int) -> dict[str, tuple[int, int]]:
    return {
        label: (max(0, count - days), count)
        for label, days in (
            ("1d", 1),
            ("7d", 7),
            ("1m", 30),
            ("3m", 90),
            ("6m", 180),
            ("1y", 365),
        )
    }


def run_all(*, force: bool) -> dict[str, Any]:
    dtec, transition, risk, adapter, context = load_runtime()
    specs = candidate_specs(dtec, transition)
    pins = {
        "contract": sha256(CONTRACT_PATH),
        "orchestrator": sha256(SELF_PATH),
        "dtec_engine": sha256(DTEC_ENGINE_PATH),
        "transition_engine": sha256(TRANSITION_ENGINE_PATH),
        "adapter": sha256(ADAPTER_PATH),
        "risk": sha256(RISK_PATH),
    }
    control_full = run_engine(
        dtec=dtec,
        transition=transition,
        risk=risk,
        context=context,
        spec=None,
        window=FULL,
        retain=True,
    )
    metrics = control_full["metrics"]
    if not math.isclose(float(metrics["net_return_pct"]), EXPECTED_V6_RETURN, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("exact V6 return anchor drift")
    if not math.isclose(float(metrics["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("exact V6 MDD anchor drift")
    if int(metrics["closed_trades"]) != EXPECTED_V6_TRADES:
        raise RuntimeError("exact V6 trade-count anchor drift")

    control_stress = run_engine(
        dtec=dtec,
        transition=transition,
        risk=risk,
        context=context,
        spec=None,
        window=FULL,
        slippage=STRESS_SLIPPAGE,
    )
    control_funding_off = run_engine(
        dtec=dtec,
        transition=transition,
        risk=risk,
        context=context,
        spec=None,
        window=FULL,
        include_funding=False,
    )
    control_lag = run_engine(
        dtec=dtec,
        transition=transition,
        risk=risk,
        context=context,
        spec=None,
        window=FULL,
        signal_lag=1,
    )
    control_blocks = [
        run_engine(
            dtec=dtec,
            transition=transition,
            risk=risk,
            context=context,
            spec=None,
            window=window,
        )
        for window in BLOCKS
    ]
    controls = {
        "full": control_full,
        "stress_8bps": control_stress,
        "funding_off": control_funding_off,
        "signal_lag_plus_1d": control_lag,
        "cold_flat_blocks": {
            "windows": [list(row) for row in BLOCKS],
            "runs": control_blocks,
            "summary": aggregate_blocks(control_blocks),
        },
    }

    rows: list[dict[str, Any]] = []
    for spec in specs:
        full = run_engine(
            dtec=dtec,
            transition=transition,
            risk=risk,
            context=context,
            spec=spec,
            window=FULL,
            retain=True,
        )
        stress = run_engine(
            dtec=dtec,
            transition=transition,
            risk=risk,
            context=context,
            spec=spec,
            window=FULL,
            slippage=STRESS_SLIPPAGE,
        )
        funding_off = run_engine(
            dtec=dtec,
            transition=transition,
            risk=risk,
            context=context,
            spec=spec,
            window=FULL,
            include_funding=False,
        )
        lag = run_engine(
            dtec=dtec,
            transition=transition,
            risk=risk,
            context=context,
            spec=spec,
            window=FULL,
            signal_lag=1,
        )
        blocks = [
            run_engine(
                dtec=dtec,
                transition=transition,
                risk=risk,
                context=context,
                spec=spec,
                window=window,
            )
            for window in BLOCKS
        ]
        cost = opportunity_cost(full, control_full)
        row_gate = gate(
            full=full,
            stress=stress,
            funding_off=funding_off,
            lag=lag,
            blocks=blocks,
            control_full=control_full,
            control_stress=control_stress,
            control_funding_off=control_funding_off,
            control_lag=control_lag,
            control_blocks=control_blocks,
            cost=cost,
        )
        recent = {
            label: run_engine(
                dtec=dtec,
                transition=transition,
                risk=risk,
                context=context,
                spec=spec,
                window=window,
            )
            for label, window in recent_windows(FULL[1]).items()
        }
        rows.append(
            {
                "arm_id": spec["arm_id"],
                "family": spec["family"],
                "config": spec["config"].canonical(),
                "full": full,
                "stress_8bps": stress,
                "funding_off": funding_off,
                "signal_lag_plus_1d": lag,
                "cold_flat_blocks": {
                    "windows": [list(row) for row in BLOCKS],
                    "runs": blocks,
                    "summary": aggregate_blocks(blocks),
                },
                "recent_slices_audit_only": recent,
                "opportunity_cost": cost,
                "gate": row_gate,
            }
        )

    passers = [row for row in rows if row["gate"]["status"] == "PASS"]
    payload = {
        "schema": "hype-1d-ma7-v6-continuous-trend-overlay-v1",
        "status": "HARD-GATE-FAILED" if not passers else "PASS_DIAGNOSTIC_ONLY",
        "research_state": "all 432d researcher-exposed / diagnostic-only / not promoted / not live-ready",
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframe": "UTC 1d with real 1h execution/risk audit",
        "windows": {
            "full": list(FULL),
            "cold_flat_blocks": [list(row) for row in BLOCKS],
            "recent_slices": {key: list(value) for key, value in recent_windows(FULL[1]).items()},
        },
        "cost_model": {
            "fee_per_fill": 0.001,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "real Binance funding events, plus funding-off stress",
        },
        "pins": pins,
        "book_quality": context.book.quality,
        "market_audit": context.market.audit,
        "controls": controls,
        "candidate_count": len(rows),
        "passing_count": len(passers),
        "champion": passers[0]["arm_id"] if passers else None,
        "rows": rows,
        "decision": (
            "No continuous-trend overlay passed the economic and opportunity-cost gates; "
            "do not change V6 or register V7."
            if not passers
            else "Diagnostic passer exists, but still requires clean prospective observation."
        ),
    }
    digest = write_json(OUTPUT_PATH, payload, force=force)
    payload["output_sha256"] = digest
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    payload = run_all(force=args.force)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "candidate_count": payload["candidate_count"],
                "passing_count": payload["passing_count"],
                "champion": payload["champion"],
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
