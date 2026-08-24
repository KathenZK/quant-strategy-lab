"""Audit registered HYPE-1D-MA7-ABT-V6 with fixed 3x entry leverage."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from statistics import median
import subprocess
import sys
from types import ModuleType
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v6-3x-leverage-contract-2026-08-10.md"
)
PEHC_RESEARCH_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_profit_exit_handoff_continuity.py"
)
PEHC_ENGINE_PATH = (
    SCRIPT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
)
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v6_3x_leverage_2026-08-10.json"
)

TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_engine.py",
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_engine.py",
    ROOT / "tests/test_hype_1d_ma7_trend_phase_risk.py",
)

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TARGET_LEVERAGE = 3.0
EXPECTED_V6_CONFIG_SHA256 = (
    "b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00"
)
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19
TOLERANCE = 1e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        sanitize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def write_locked(payload: dict[str, Any]) -> None:
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if OUTPUT_PATH.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    encoded = (
        json.dumps(
            sanitize(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")


def preflight() -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    if completed.returncode != 0:
        raise RuntimeError(output)
    return {
        "status": "PASS",
        "command": command,
        "output": output,
        "tests": {str(path.relative_to(ROOT)): sha256(path) for path in TEST_PATHS},
    }


def fixed_v6_config(engine: ModuleType) -> Any:
    matches = [row for row in engine.grid_configs() if row.arm_id == "PEHC_294"]
    if len(matches) != 1:
        raise RuntimeError("PEHC_294 identity drift")
    config = matches[0]
    actual = engine.config_sha256(config)
    if actual != EXPECTED_V6_CONFIG_SHA256:
        raise RuntimeError(
            f"PEHC_294 config drift: expected {EXPECTED_V6_CONFIG_SHA256}, got {actual}"
        )
    return config


def activation_counts(raw: Any, events: list[dict[str, Any]]) -> dict[str, int]:
    exits = [str(trade.get("exit_reason", "")) for trade in raw.trades]
    return {
        "shadow_start": sum(row["event"] == "shadow_start" for row in events),
        "shadow_hold": sum(row["event"] == "shadow_hold" for row in events),
        "shadow_expire": sum(row["event"] == "shadow_expire" for row in events),
        "shadow_native_cancel": sum(
            row["event"] == "shadow_cancel_native_exit" for row in events
        ),
        "handoff_opportunity": sum(
            row["event"] == "handoff_opportunity" for row in events
        ),
        "handoff_accept": sum(row["event"] == "handoff_accept" for row in events),
        "handoff_filter_reject": sum(
            row["event"] == "handoff_reject_filter" for row in events
        ),
        "handoff_nonflat_reject": sum(
            row["event"] == "handoff_reject_actual_nonflat" for row in events
        ),
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
    }


def run_raw_v6(
    *,
    engine: ModuleType,
    context: Any,
    config: Any,
    start_index: int,
    terminal_index: int,
    target_leverage: float,
    slippage: float,
    include_funding: bool,
    signal_lag: int,
    retain: bool,
) -> dict[str, Any]:
    oapp_config = engine.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    entry_signal = engine._BASE.EntryQualitySignal(
        context.engine,
        oapp_config.entry,
    )
    leverage_spec = (
        None
        if math.isclose(target_leverage, 1.0, abs_tol=TOLERANCE)
        else engine._BASE.LeverageSpec(
            f"FIXED_{target_leverage:.2f}X",
            "fixed",
            target_leverage,
        )
    )
    leverage_policy = engine._BASE.LeveragePolicy(context, leverage_spec)
    recorder = engine.HandoffRecorder()
    function, source_hash = engine.build_variant_function(
        context,
        config,
        oapp_config=oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        recorder=recorder,
    )
    raw = function(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=context.short_config,
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    handoff_events = list(recorder.events)
    return {
        "raw": raw,
        "source_sha256": source_hash,
        "entry_events": list(entry_signal.events),
        "leverage_events": list(leverage_policy.events),
        "handoff_events": handoff_events,
        "activation_counts": activation_counts(raw, handoff_events),
    }


def annualized_return(equity_multiple: float, days: int) -> float:
    if equity_multiple <= 0.0 or days <= 0:
        return math.nan
    return (equity_multiple ** (365.0 / days) - 1.0) * 100.0


def exposure_pct(raw: Any, window_hours: float) -> float:
    if window_hours <= 0.0:
        raise ValueError("exposure window must be positive")
    held_hours = sum(
        max(
            0.0,
            (
                datetime.fromisoformat(str(row["exit_ts"]))
                - datetime.fromisoformat(str(row["entry_ts"]))
            ).total_seconds()
            / 3_600.0,
        )
        for row in raw.trades
    )
    return held_hours / window_hours * 100.0


def behavior_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "entry_ts",
        "exit_ts",
        "side",
        "entry_price",
        "exit_price",
        "entry_reason",
        "exit_reason",
        "bars_held",
    )
    return [{field: row.get(field) for field in fields} for row in trades]


def scenario(
    *,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    target_leverage: float,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    start = (
        window[0]
        if window[1] - window[0] == 1
        else research.engine_start(window)
    )
    result = run_raw_v6(
        engine=engine,
        context=context,
        config=config,
        start_index=start,
        terminal_index=window[1],
        target_leverage=target_leverage,
        slippage=slippage,
        include_funding=include_funding,
        signal_lag=signal_lag,
        retain=retain,
    )
    raw = result["raw"]
    if bool(raw.metrics.get("bankrupt_intraday")):
        return {
            "status": "BANKRUPT_INTRADAY",
            "target_leverage": target_leverage,
            "requested_window": list(window),
            "engine_window": [start, window[1]],
            "raw_metrics": dict(raw.metrics),
        }
    replay = risk.replay_chronological_1h(
        context,
        raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    if not all(replay.parity.values()):
        raise RuntimeError("chronological replay parity failed")
    raw_metrics = raw.metrics
    long_pnl = sum(
        float(row["net_pnl"]) for row in raw.trades if str(row["side"]) == "long"
    )
    short_pnl = sum(
        float(row["net_pnl"]) for row in raw.trades if str(row["side"]) == "short"
    )
    marked_leverage = float(replay.max_marked_leverage)
    metrics = {
        "equity_multiple": float(replay.terminal_equity),
        "net_return_pct": (float(replay.terminal_equity) - 1.0) * 100.0,
        "annualized_return_pct": annualized_return(
            float(replay.terminal_equity),
            window[1] - start,
        ),
        "chronological_1h_mdd_pct": float(replay.chronological_1h_mdd_pct),
        "daily_extreme_mdd_pct": float(raw_metrics["max_drawdown_pct"]),
        "sharpe": float(raw_metrics["sharpe"]),
        "profit_factor": float(raw_metrics["profit_factor"]),
        "win_rate": float(raw_metrics["win_rate"]),
        "closed_trades": int(raw_metrics["closed_trades"]),
        "long_trades": int(raw_metrics["long_trades"]),
        "short_trades": int(raw_metrics["short_trades"]),
        "long_net_pnl_pct_initial": long_pnl * 100.0,
        "short_net_pnl_pct_initial": short_pnl * 100.0,
        "exposure_pct": exposure_pct(raw, (window[1] - start) * 24.0),
        "turnover_multiple": float(replay.turnover_multiple),
        "cost_pct_initial": float(raw_metrics["cost_pct_initial"]),
        "funding_pct_initial": float(raw_metrics["funding_pct_initial"]),
        "max_intraday_leverage": float(raw_metrics["max_intraday_leverage"]),
        "max_marked_leverage": marked_leverage,
        "minimum_marked_margin_ratio": (
            1.0 / marked_leverage if marked_leverage > 0.0 else math.inf
        ),
        "bankrupt_intraday": False,
        "worst_ts": replay.worst_ts,
        "worst_trade_index": replay.worst_trade_index,
    }
    trades = list(raw.trades)
    payload: dict[str, Any] = {
        "status": "PASS",
        "arm_id": (
            "V6_FIXED_3X"
            if math.isclose(target_leverage, TARGET_LEVERAGE, abs_tol=TOLERANCE)
            else "V6_EXACT_1X"
        ),
        "target_leverage": target_leverage,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "slippage": slippage,
        "include_funding": include_funding,
        "signal_lag": signal_lag,
        "metrics": metrics,
        "replay_parity": dict(replay.parity),
        "source_sha256": result["source_sha256"],
        "activation_counts": result["activation_counts"],
        "handoff_events": result["handoff_events"],
        "leverage_events": result["leverage_events"],
        "trades_sha256": canonical_hash(research.economic_trades(trades)),
        "behavior_sha256": canonical_hash(behavior_trades(trades)),
    }
    if retain:
        payload["trades"] = trades
        payload["path"] = list(raw.path)
        payload["replay"] = replay.canonical()
    return payload


def safe(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - every scenario must retain failure
        return {
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def comparison(three_x: dict[str, Any], one_x: dict[str, Any]) -> dict[str, Any]:
    if three_x.get("status") != "PASS" or one_x.get("status") != "PASS":
        return {"status": "ERROR"}
    candidate = three_x["metrics"]
    control = one_x["metrics"]
    return {
        "status": "PASS",
        "return_delta_pp": float(candidate["net_return_pct"])
        - float(control["net_return_pct"]),
        "annualized_return_delta_pp": float(candidate["annualized_return_pct"])
        - float(control["annualized_return_pct"]),
        "mdd_delta_pp": float(candidate["chronological_1h_mdd_pct"])
        - float(control["chronological_1h_mdd_pct"]),
        "max_marked_leverage_delta": float(candidate["max_marked_leverage"])
        - float(control["max_marked_leverage"]),
        "same_trade_behavior": three_x["behavior_sha256"]
        == one_x["behavior_sha256"],
        "same_handoff_events": canonical_hash(three_x["handoff_events"])
        == canonical_hash(one_x["handoff_events"]),
    }


def pair(
    *,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    one_x = safe(
        lambda: scenario(
            research=research,
            engine=engine,
            risk=risk,
            context=context,
            config=config,
            target_leverage=1.0,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=retain,
        )
    )
    three_x = safe(
        lambda: scenario(
            research=research,
            engine=engine,
            risk=risk,
            context=context,
            config=config,
            target_leverage=TARGET_LEVERAGE,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=retain,
        )
    )
    return {
        "one_x": one_x,
        "three_x": three_x,
        "comparison": comparison(three_x, one_x),
    }


def summarize_windows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [
        row
        for row in rows
        if row["one_x"].get("status") == row["three_x"].get("status") == "PASS"
    ]
    if not valid:
        return {"valid": 0, "total": len(rows)}
    one_equity = math.prod(
        float(row["one_x"]["metrics"]["equity_multiple"]) for row in valid
    )
    three_equity = math.prod(
        float(row["three_x"]["metrics"]["equity_multiple"]) for row in valid
    )
    return {
        "valid": len(valid),
        "total": len(rows),
        "one_x_compound_return_pct": (one_equity - 1.0) * 100.0,
        "three_x_compound_return_pct": (three_equity - 1.0) * 100.0,
        "one_x_worst_mdd_pct": min(
            float(row["one_x"]["metrics"]["chronological_1h_mdd_pct"])
            for row in valid
        ),
        "three_x_worst_mdd_pct": min(
            float(row["three_x"]["metrics"]["chronological_1h_mdd_pct"])
            for row in valid
        ),
        "one_x_positive_windows": sum(
            float(row["one_x"]["metrics"]["net_return_pct"]) > 0.0 for row in valid
        ),
        "three_x_positive_windows": sum(
            float(row["three_x"]["metrics"]["net_return_pct"]) > 0.0 for row in valid
        ),
        "three_x_bankrupt_windows": sum(
            row["three_x"].get("status") == "BANKRUPT_INTRADAY" for row in rows
        ),
    }


def rolling_windows() -> tuple[tuple[int, int], ...]:
    windows = [(left, left + 90) for left in range(0, FULL[1] - 89, 30)]
    anchored = (FULL[1] - 90, FULL[1])
    if anchored not in windows:
        windows.append(anchored)
    return tuple(windows)


def phase_audit(
    *,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for phase in range(24):
        try:
            market = context.original_harness.load_market(phase)
            phase_context = replace(context, market=market)
            result = pair(
                research=research,
                engine=engine,
                risk=risk,
                context=phase_context,
                config=config,
                window=(0, phase_context.book.count),
            )
            rows.append(
                {
                    "phase_hours": phase,
                    "market_audit": market.audit,
                    **result,
                }
            )
        except Exception as exc:  # noqa: BLE001 - invalid phases stay explicit
            rows.append(
                {
                    "phase_hours": phase,
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    valid = [
        row
        for row in rows
        if row.get("one_x", {}).get("status")
        == row.get("three_x", {}).get("status")
        == "PASS"
    ]
    summary: dict[str, Any] = {
        "valid_phases": len(valid),
        "invalid_phases": 24 - len(valid),
    }
    if valid:
        three_metrics = [row["three_x"]["metrics"] for row in valid]
        summary.update(
            {
                "three_x_positive_phases": sum(
                    float(row["net_return_pct"]) > 0.0 for row in three_metrics
                ),
                "three_x_worst_return_pct": min(
                    float(row["net_return_pct"]) for row in three_metrics
                ),
                "three_x_median_return_pct": median(
                    float(row["net_return_pct"]) for row in three_metrics
                ),
                "three_x_worst_mdd_pct": min(
                    float(row["chronological_1h_mdd_pct"]) for row in three_metrics
                ),
                "three_x_max_marked_leverage": max(
                    float(row["max_marked_leverage"]) for row in three_metrics
                ),
            }
        )
    return {"rows": rows, "summary": summary}


def risk_screen(full_three_x: dict[str, Any], phases: dict[str, Any]) -> dict[str, Any]:
    if full_three_x.get("status") != "PASS":
        return {
            "status": "FAILED_TO_EVALUATE",
            "adoption_eligible": False,
        }
    metrics = full_three_x["metrics"]
    minimum_ratio = float(metrics["minimum_marked_margin_ratio"])
    maintenance = {
        f"{ratio * 100:g}%": {
            "assumed_maintenance_margin_ratio": ratio,
            "breached_on_hourly_mark_screen": minimum_ratio <= ratio,
        }
        for ratio in (0.005, 0.01, 0.025, 0.05)
    }
    mdd = abs(float(metrics["chronological_1h_mdd_pct"]))
    budgets = {
        str(budget): mdd <= budget for budget in (20, 25, 30, 35, 40, 50)
    }
    high_tail_risk = (
        mdd > 50.0
        or float(metrics["max_marked_leverage"]) > 4.0
        or any(row["breached_on_hourly_mark_screen"] for row in maintenance.values())
        or int(phases["summary"].get("three_x_positive_phases", 0))
        < int(phases["summary"].get("valid_phases", 0)) / 2
    )
    return {
        "status": "HIGH_TAIL_RISK" if high_tail_risk else "HISTORICAL_SCREEN_ONLY",
        "hourly_open_and_funding_bankruptcy": False,
        "raw_intraday_bankruptcy": bool(metrics["bankrupt_intraday"]),
        "minimum_marked_margin_ratio": minimum_ratio,
        "maintenance_sensitivity": maintenance,
        "mdd_budget_pass": budgets,
        "exact_binance_tiers_modeled": False,
        "liquidation_fee_modeled": False,
        "intrahour_liquidation_path_modeled": False,
        "adoption_eligible": False,
        "reason": (
            "V6 remains shadow-only and 1x prospective has not passed; "
            "this run is an explicitly authorized exposed-history diagnostic."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")

    tests = preflight()
    research = load_module(PEHC_RESEARCH_PATH, "v6_3x_pehc_research")
    engine, risk, _, context = research.load_runtime()
    config = fixed_v6_config(engine)

    full = pair(
        research=research,
        engine=engine,
        risk=risk,
        context=context,
        config=config,
        window=FULL,
        retain=True,
    )
    one_metrics = full["one_x"].get("metrics", {})
    if not (
        full["one_x"].get("status") == "PASS"
        and math.isclose(
            float(one_metrics["net_return_pct"]),
            EXPECTED_V6_RETURN,
            abs_tol=TOLERANCE,
        )
        and math.isclose(
            float(one_metrics["chronological_1h_mdd_pct"]),
            EXPECTED_V6_MDD,
            abs_tol=TOLERANCE,
        )
        and int(one_metrics["closed_trades"]) == EXPECTED_V6_TRADES
    ):
        raise RuntimeError("exact V6 1x anchor drift")
    if full["three_x"].get("status") != "PASS":
        raise RuntimeError(f"V6 3x full run failed: {full['three_x']}")
    if not full["comparison"]["same_trade_behavior"]:
        raise RuntimeError("3x changed V6 trade behavior")
    if not full["comparison"]["same_handoff_events"]:
        raise RuntimeError("3x changed V6 handoff behavior")
    three_x_trades = full["three_x"]["trades"]
    if not all(
        math.isclose(
            float(row.get("entry_leverage", math.nan)),
            TARGET_LEVERAGE,
            abs_tol=TOLERANCE,
        )
        for row in three_x_trades
    ):
        raise RuntimeError("not every V6 3x trade has fixed 3x entry leverage")
    leverage_events = full["three_x"]["leverage_events"]
    if len(leverage_events) != len(three_x_trades) or not all(
        math.isclose(
            float(row["target_leverage"]),
            TARGET_LEVERAGE,
            abs_tol=TOLERANCE,
        )
        for row in leverage_events
    ):
        raise RuntimeError("entry leverage event/trade mismatch")

    stress = pair(
        research=research,
        engine=engine,
        risk=risk,
        context=context,
        config=config,
        window=FULL,
        slippage=STRESS_SLIPPAGE,
    )
    funding_off = pair(
        research=research,
        engine=engine,
        risk=risk,
        context=context,
        config=config,
        window=FULL,
        include_funding=False,
    )
    delayed = pair(
        research=research,
        engine=engine,
        risk=risk,
        context=context,
        config=config,
        window=FULL,
        signal_lag=1,
    )

    recent: dict[str, Any] = {}
    for label, days in (
        ("1d", 1),
        ("7d", 7),
        ("1m", 30),
        ("3m", 90),
        ("6m", 180),
        ("1y", 365),
    ):
        window = (max(0, FULL[1] - days), FULL[1])
        recent[label] = {
            "window": list(window),
            "selection_use": False,
            **pair(
                research=research,
                engine=engine,
                risk=risk,
                context=context,
                config=config,
                window=window,
            ),
        }

    block_rows = [
        {
            "window": list(window),
            **pair(
                research=research,
                engine=engine,
                risk=risk,
                context=context,
                config=config,
                window=window,
            ),
        }
        for window in BLOCKS
    ]
    rolling_rows = [
        {
            "window": list(window),
            **pair(
                research=research,
                engine=engine,
                risk=risk,
                context=context,
                config=config,
                window=window,
            ),
        }
        for window in rolling_windows()
    ]
    phases = phase_audit(
        research=research,
        engine=engine,
        risk=risk,
        context=context,
        config=config,
    )
    risk = risk_screen(full["three_x"], phases)

    payload = {
        "schema": "hype-1d-ma7-abt-v6-fixed-3x-diagnostic-v1",
        "status": "COMPLETED_DIAGNOSTIC",
        "conclusion": risk["status"],
        "research_state": (
            "registered V6 unchanged / shadow-only / diagnostic-only / "
            "not promoted / not live-ready"
        ),
        "governance_deviation": {
            "original_rule": "no leverage before V6 1x clean prospective PASS",
            "authorization": (
                "user explicitly requested V6 fixed 3x diagnostic on 2026-08-10"
            ),
            "scope": "researcher-exposed history only; cannot unlock or select leverage",
        },
        "preflight": tests,
        "identity": {
            "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
            "version": "V6",
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "one_x_anchor": {
                "net_return_pct": EXPECTED_V6_RETURN,
                "chronological_1h_mdd_pct": EXPECTED_V6_MDD,
                "closed_trades": EXPECTED_V6_TRADES,
            },
        },
        "leverage_contract": {
            "control": "target 1x post-cost equity at every actual entry",
            "candidate": "target 3x post-cost equity at every actual entry",
            "quantity": "fixed until exit or reversal; no periodic rebalance",
            "shadow": "capital-free until accepted handoff becomes an actual short",
            "marked_leverage_may_exceed_target": True,
        },
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "costs": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate",
        },
        "windows": {
            "full": list(FULL),
            "cold_flat_blocks": [list(row) for row in BLOCKS],
            "rolling_90d_30d": [list(row) for row in rolling_windows()],
        },
        "full": full,
        "stress_8bps": stress,
        "funding_off": funding_off,
        "signal_lag_plus_1d": delayed,
        "recent_slices_audit_only": recent,
        "cold_flat_blocks": {
            "rows": block_rows,
            "summary": summarize_windows(block_rows),
        },
        "rolling_90d_30d": {
            "rows": rolling_rows,
            "summary": summarize_windows(rolling_rows),
        },
        "phases_0h_to_23h": phases,
        "risk_screen": risk,
        "pins": {
            "contract": sha256(CONTRACT_PATH),
            "audit": sha256(SELF_PATH),
            "pehc_research": sha256(PEHC_RESEARCH_PATH),
            "pehc_engine": sha256(PEHC_ENGINE_PATH),
            "risk_metrics": sha256(RISK_PATH),
            "adapter": sha256(ADAPTER_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v6_changed": False,
        "leverage_unlocked": False,
        "clean_oos_claim": False,
    }
    write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "conclusion": payload["conclusion"],
                "one_x": full["one_x"]["metrics"],
                "three_x": full["three_x"]["metrics"],
                "phase_summary": phases["summary"],
                "artifact": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
