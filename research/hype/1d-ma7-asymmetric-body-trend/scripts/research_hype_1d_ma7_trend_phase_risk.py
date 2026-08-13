"""Stage-locked HYPE 1D MA7 Trend Phase & Risk research."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-trend-phase-risk-preregistration-2026-08-09.md"
)
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_engine.py"
METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RENDERER_PATH = SCRIPT_DIR / "render_hype_1d_ma7_trend_phase_risk.py"
ORCHESTRATOR_PATH = Path(__file__).resolve()
ENGINE_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_trend_phase_risk.py"
ORCHESTRATOR_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_trend_phase_risk_research.py"
ADAPTER_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v4_fair_adapter.py"
PFT_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v4_pft_engine.py"
HARNESS_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_intent_harness.py"
FAIR_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_intent_fair_metrics.py"
RENDERER_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_trend_phase_risk_trade_path.py"
TEST_PATHS = (
    ENGINE_TEST_PATH,
    ORCHESTRATOR_TEST_PATH,
    ADAPTER_TEST_PATH,
    PFT_TEST_PATH,
    HARNESS_TEST_PATH,
    FAIR_TEST_PATH,
    RENDERER_TEST_PATH,
)
EXPECTED_TEST_COUNT = 56

PREFIX = ARTIFACT_DIR / "hype_1d_ma7_trend_phase_risk_2026-08-09"
MANIFEST_PATH = Path(f"{PREFIX}_manifest.json")
TRIALS_PATH = Path(f"{PREFIX}_development_trials.json")
DEVELOPMENT_PATH = Path(f"{PREFIX}_development.json")
CHAMPION_PATH = Path(f"{PREFIX}_champion.json")
VALIDATION_PATH = Path(f"{PREFIX}_validation.json")
LEVERAGE_PATH = Path(f"{PREFIX}_leverage_development.json")
HOLDOUT_PATH = Path(f"{PREFIX}_holdout.json")
FINAL_PATH = Path(f"{PREFIX}_final.json")

D_FULL = (0, 259)
WFO_FOLDS = ((130, 173), (173, 216), (216, 259))
V_EVAL = (269, 346)
H_EVAL = (356, 432)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MATERIAL_RETURN_PP = 5.0
MATERIAL_MDD_PP = 2.0


def sidecar(path: Path) -> Path:
    return path.with_suffix(".sha256")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> Any:
    if is_dataclass(value):
        return canonical(asdict(value))
    if isinstance(value, dict):
        return {str(key): canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return canonical(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def write_locked(path: Path, payload: Any) -> str:
    hash_path = sidecar(path)
    if path.exists() or hash_path.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            canonical(payload),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with path.open("xb") as handle:
        handle.write(encoded)
    with hash_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    hash_path = sidecar(path)
    if not path.is_file() or not hash_path.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    fields = hash_path.read_text(encoding="utf-8").strip().split()
    actual = sha256(path)
    if len(fields) != 2 or fields[0] != actual or fields[1] != path.name:
        raise RuntimeError(f"invalid sidecar for {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), actual


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def implementation_paths() -> dict[str, Path]:
    return {
        "contract": CONTRACT_PATH,
        "engine": ENGINE_PATH,
        "metrics": METRICS_PATH,
        "adapter": ADAPTER_PATH,
        "renderer": RENDERER_PATH,
        "orchestrator": ORCHESTRATOR_PATH,
        "engine_test": ENGINE_TEST_PATH,
        "orchestrator_test": ORCHESTRATOR_TEST_PATH,
        "adapter_test": ADAPTER_TEST_PATH,
        "pft_test": PFT_TEST_PATH,
        "harness_test": HARNESS_TEST_PATH,
        "fair_test": FAIR_TEST_PATH,
        "renderer_test": RENDERER_TEST_PATH,
    }


def current_pins() -> dict[str, dict[str, str]]:
    return {
        label: {"path": str(path), "sha256": sha256(path)}
        for label, path in implementation_paths().items()
    }


def assert_pins(pins: dict[str, dict[str, str]]) -> None:
    if current_pins() != pins:
        raise RuntimeError("implementation pin drift")


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "hype_tpr_engine_runtime")
    risk = load_module(METRICS_PATH, "hype_tpr_metrics_runtime")
    adapter = load_module(ADAPTER_PATH, "hype_tpr_adapter_runtime")
    return engine, risk, adapter, adapter.load_context()


def run_preflight() -> dict[str, Any]:
    command = [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else -1
    status = (
        "PASS"
        if completed.returncode == 0 and passed == EXPECTED_TEST_COUNT
        else "FAIL"
    )
    record = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_TEST_COUNT,
        "returncode": completed.returncode,
        "tests": {str(path): sha256(path) for path in TEST_PATHS},
        "output_tail": output[-4000:],
    }
    if status != "PASS":
        raise RuntimeError(
            f"preflight expected {EXPECTED_TEST_COUNT} passes, got {passed}"
        )
    return record


def assert_no_early_artifacts() -> None:
    downstream = (DEVELOPMENT_PATH, CHAMPION_PATH, VALIDATION_PATH, LEVERAGE_PATH, HOLDOUT_PATH, FINAL_PATH)
    present = [path.name for path in downstream if path.exists() or sidecar(path).exists()]
    if present:
        raise RuntimeError(f"early TPR artifacts detected: {present}")


def stage_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or sidecar(MANIFEST_PATH).exists():
        raise RuntimeError("manifest already exists")
    assert_no_early_artifacts()
    preflight = run_preflight()
    pins = current_pins()
    engine, risk, adapter, context = load_runtime()
    full = adapter.verify_full_baseline(retain=True)
    replay = risk.replay_chronological_1h(context, full)
    if len(engine.ranked_configs()) != 12 or len(engine.leverage_specs()) != 9:
        raise RuntimeError("frozen grid count drift")
    audit = context.market.audit
    blockers = (
        int(audit["trusted_hourly_audit"]["blocker_count"])
        + int(audit["trusted_funding_audit"]["blocker_count"])
        + int(context.book.quality["daily"]["blocker_count"])
    )
    if blockers:
        raise RuntimeError("market audit blocker")
    payload = {
        "schema": "hype-tpr-manifest-v1",
        "status": "PASS",
        "research_state": "explore / not promoted / not live-ready",
        "pins": pins,
        "preflight": preflight,
        "market_audit": audit,
        "book_quality": context.book.quality,
        "windows": {"D": D_FULL, "WFO": WFO_FOLDS, "V": V_EVAL, "H": H_EVAL},
        "candidate_grid": [config.canonical() for config in engine.ranked_configs()],
        "candidate_hashes": {
            config.arm_id: engine.config_sha256(config)
            for config in engine.ranked_configs()
        },
        "leverage_grid": [asdict(spec) for spec in engine.leverage_specs()],
        "exact_v4_full": {
            "metrics": full.metrics,
            "chronological_replay": replay.canonical(),
            "trades_sha256": canonical_hash(full.trades),
        },
        "candidate_v_h_unrevealed": True,
    }
    assert_pins(pins)
    write_locked(MANIFEST_PATH, payload)
    return payload


def assert_manifest() -> dict[str, Any]:
    manifest, _ = read_locked(MANIFEST_PATH)
    if manifest.get("status") != "PASS":
        raise RuntimeError("manifest is not PASS")
    assert_pins(manifest["pins"])
    return manifest


def engine_start(window: tuple[int, int]) -> int:
    return window[0] if window[0] == 0 else window[0] + 1


def normalize_metrics(raw: Any, replay: Any) -> dict[str, Any]:
    metrics = raw.metrics
    return {
        "start_ts": metrics["start_ts"],
        "end_ts": metrics["end_ts"],
        "days": metrics["days"],
        "equity_multiple": metrics["equity_multiple"],
        "net_return_pct": metrics["net_return_pct"],
        "chronological_1h_mdd_pct": replay.chronological_1h_mdd_pct,
        "chronological_worst_ts": replay.worst_ts,
        "chronological_worst_trade_index": replay.worst_trade_index,
        "daily_extreme_mdd_pct": metrics["max_drawdown_pct"],
        "closed_trades": metrics["closed_trades"],
        "long_trades": metrics["long_trades"],
        "short_trades": metrics["short_trades"],
        "win_rate": metrics["win_rate"],
        "profit_factor": metrics["profit_factor"],
        "turnover_multiple": metrics["turnover_multiple"],
        "cost_pct_initial": metrics["cost_pct_initial"],
        "funding_pct_initial": metrics["funding_pct_initial"],
        "max_intraday_leverage": metrics["max_intraday_leverage"],
        "max_marked_leverage": replay.max_marked_leverage,
        "bankrupt_intraday": metrics["bankrupt_intraday"],
    }


def economic_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "side",
        "entry_ts",
        "exit_ts",
        "entry_price",
        "exit_price",
        "entry_leverage",
        "exit_reason",
        "net_return",
        "net_pnl",
    )
    return [{key: trade.get(key, 1.0 if key == "entry_leverage" else None) for key in fields} for trade in trades]


def economic_path(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "ts",
        "pre_action_equity",
        "post_action_equity",
        "close_equity",
        "position",
        "action",
    )
    return [{key: row.get(key) for key in fields} for row in path]


def run_one(
    *,
    engine: ModuleType,
    risk: ModuleType,
    adapter: ModuleType,
    context: Any,
    window: tuple[int, int],
    config: Any | None,
    slippage: float,
    retain: bool,
    leverage_spec: Any | None = None,
    include_funding: bool = True,
) -> dict[str, Any]:
    start = engine_start(window)
    if config is None:
        if leverage_spec is not None or not include_funding:
            raise ValueError("exact control only supports frozen funding and 1x")
        raw = adapter.run_v4(start, window[1], slippage=slippage, retain=retain)
        source_hash = "exact-v4-adapter"
        events: list[dict[str, Any]] = []
        leverage_events: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        arm_id = "C000_EXACT_V4"
    else:
        result = engine.run_variant(
            context,
            config,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            include_funding=include_funding,
            retain=retain,
            leverage_spec=leverage_spec,
        )
        raw = result.raw
        source_hash = result.source_sha256
        events = result.entry_events
        leverage_events = result.leverage_events
        counts = result.activation_counts
        arm_id = config.arm_id
    replay = risk.replay_chronological_1h(
        context,
        raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    if not all(replay.parity.values()) or bool(raw.metrics["bankrupt_intraday"]):
        raise RuntimeError(f"ledger failure: {arm_id}")
    payload = {
        "arm_id": arm_id,
        "requested_window": window,
        "engine_window": (start, window[1]),
        "slippage": slippage,
        "include_funding": include_funding,
        "leverage_spec": asdict(leverage_spec) if leverage_spec else None,
        "metrics": normalize_metrics(raw, replay),
        "replay_parity": replay.parity,
        "source_sha256": source_hash,
        "activation_counts": counts,
        "entry_events": events,
        "leverage_events": leverage_events,
        "trades_sha256": canonical_hash(economic_trades(raw.trades)),
        "path_sha256": canonical_hash(economic_path(raw.path)),
    }
    if retain:
        payload.update(
            {
                "trades": raw.trades,
                "path": raw.path,
                "chronological_points": [asdict(point) for point in replay.points],
            }
        )
    return payload


def aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [fold["metrics"] for fold in folds]
    equity = math.prod(float(row["equity_multiple"]) for row in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "chronological_1h_mdd_pct": min(
            float(row["chronological_1h_mdd_pct"]) for row in metrics
        ),
        "daily_extreme_mdd_pct": min(
            float(row["daily_extreme_mdd_pct"]) for row in metrics
        ),
        "closed_trades": sum(int(row["closed_trades"]) for row in metrics),
        "long_trades": sum(int(row["long_trades"]) for row in metrics),
        "short_trades": sum(int(row["short_trades"]) for row in metrics),
        "bankrupt_intraday": any(bool(row["bankrupt_intraday"]) for row in metrics),
    }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return_delta = float(candidate["net_return_pct"]) - float(control["net_return_pct"])
    mdd_delta = float(candidate["chronological_1h_mdd_pct"]) - float(
        control["chronological_1h_mdd_pct"]
    )
    daily_delta = float(candidate["daily_extreme_mdd_pct"]) - float(
        control["daily_extreme_mdd_pct"]
    )
    return {
        "return_delta_pp": return_delta,
        "chronological_mdd_delta_pp": mdd_delta,
        "daily_extreme_mdd_delta_pp": daily_delta,
        "return_higher": return_delta > 0.0,
        "chronological_mdd_smaller": mdd_delta > 0.0,
        "material": return_delta >= MATERIAL_RETURN_PP or mdd_delta >= MATERIAL_MDD_PP,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
        "daily_stress_double_worse": return_delta < 0.0 and daily_delta < 0.0,
    }


def numeric_gate(trial: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    full = compare(trial["base_full"]["metrics"], control["base_full"]["metrics"])
    wfo = compare(trial["base_wfo"], control["base_wfo"])
    stress_full = compare(
        trial["stress_full"]["metrics"], control["stress_full"]["metrics"]
    )
    stress_wfo = compare(trial["stress_wfo"], control["stress_wfo"])
    folds = [
        compare(item["metrics"], base["metrics"])
        for item, base in zip(trial["base_folds"], control["base_folds"])
    ]
    checks = {
        "full_dual_dominance": full["return_higher"]
        and full["chronological_mdd_smaller"]
        and full["material"],
        "wfo_dual_dominance": wfo["return_higher"]
        and wfo["chronological_mdd_smaller"]
        and wfo["material"],
        "stress_full_not_double_worse": not stress_full["double_worse"],
        "stress_wfo_not_double_worse": not stress_wfo["double_worse"],
        "folds_not_double_worse": all(not row["double_worse"] for row in folds),
        "daily_stress_full": not full["daily_stress_double_worse"],
        "daily_stress_wfo": not wfo["daily_stress_double_worse"],
        "trade_floor": int(trial["base_full"]["metrics"]["closed_trades"]) >= 8,
        "long_floor": int(trial["base_full"]["metrics"]["long_trades"]) >= 3,
        "short_floor": int(trial["base_full"]["metrics"]["short_trades"]) >= 3,
        "wfo_floor": int(trial["base_wfo"]["closed_trades"]) >= 3,
        "fold_floor": all(int(row["metrics"]["closed_trades"]) >= 1 for row in trial["base_folds"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "full": full,
        "wfo": wfo,
        "stress_full": stress_full,
        "stress_wfo": stress_wfo,
        "folds": folds,
    }


def enabled_modules(config: dict[str, Any]) -> list[str]:
    modules = ["T"]
    if config["q_threshold"] is not None:
        modules.insert(0, "Q")
    if int(config["e_days"]) > 0:
        modules.insert(1 if "Q" in modules else 0, "E")
    return modules


def module_active(module: str, counts: dict[str, int]) -> bool:
    if module == "Q":
        return int(counts.get("q_reject", 0)) > 0
    if module == "E":
        return int(counts.get("e_exit", 0)) > 0
    if module == "T":
        return int(counts.get("t_exit", 0)) > 0
    raise ValueError(module)


def rank_key(trial: dict[str, Any]) -> tuple[Any, ...]:
    gate = trial["gate"]
    return (
        -min(row["return_delta_pp"] for row in gate["folds"]),
        -gate["wfo"]["return_delta_pp"],
        -gate["wfo"]["chronological_mdd_delta_pp"],
        -gate["full"]["return_delta_pp"],
        -gate["full"]["chronological_mdd_delta_pp"],
        len(enabled_modules(trial["config"])),
        trial["arm_id"],
    )


def entry_event_study(
    context: Any,
    control_trades: list[dict[str, Any]],
    *,
    limit_index: int = D_FULL[1],
) -> list[dict[str, Any]]:
    engine = load_module(ENGINE_PATH, "hype_tpr_event_engine")
    timestamps = pd.DatetimeIndex(context.book.ts)
    rows = []
    previous: dict[str, Any] | None = None
    for trade in control_trades:
        entry_ts = pd.Timestamp(trade["entry_ts"])
        entry_day = int(timestamps.searchsorted(entry_ts.floor("1D")))
        signal_index = max(0, entry_day - 1)
        forced = bool(
            previous
            and previous["side"] == "long"
            and previous["exit_ts"] == trade["entry_ts"]
            and trade["side"] == "short"
        )
        side = 1 if trade["side"] == "long" else -1
        signal_close = float(context.book.close[signal_index])
        horizons = {}
        for horizon in (3, 5, 10, 20):
            right = min(limit_index, signal_index + horizon + 1)
            if side > 0:
                mfe = float(np.max(context.book.high[signal_index + 1 : right])) / signal_close - 1.0 if right > signal_index + 1 else None
                mae = float(np.min(context.book.low[signal_index + 1 : right])) / signal_close - 1.0 if right > signal_index + 1 else None
            else:
                mfe = 1.0 - float(np.min(context.book.low[signal_index + 1 : right])) / signal_close if right > signal_index + 1 else None
                mae = 1.0 - float(np.max(context.book.high[signal_index + 1 : right])) / signal_close if right > signal_index + 1 else None
            horizons[str(horizon)] = {"mfe_pct": mfe * 100.0 if mfe is not None else None, "mae_pct": mae * 100.0 if mae is not None else None}
        rows.append(
            {
                "side": trade["side"],
                "entry_ts": trade["entry_ts"],
                "exit_ts": trade["exit_ts"],
                "forced_reversal": forced,
                "signal_index": signal_index,
                "signed_er7": engine.signed_efficiency(context.book.close, signal_index, side, 7),
                "trade_net_return_pct": float(trade["net_return"]) * 100.0,
                "future_horizons": horizons,
            }
        )
        previous = trade
    return rows


def long_decay_event_study(
    context: Any,
    control_trades: list[dict[str, Any]],
    *,
    limit_index: int = D_FULL[1],
) -> list[dict[str, Any]]:
    timestamps = pd.DatetimeIndex(context.book.ts)
    rows: list[dict[str, Any]] = []
    for trade_index, trade in enumerate(control_trades):
        if trade["side"] != "long":
            continue
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        entry_day = int(timestamps.searchsorted(entry_ts.floor("1D")))
        exit_day = min(
            int(timestamps.searchsorted(exit_ts.floor("1D"))),
            limit_index,
        )
        entry_price = float(trade["entry_price"])
        decay_run = 0
        for index in range(entry_day, exit_day):
            ma7 = float(context.features.ma7[index])
            prior_ma7 = float(context.features.ma7[index - 1]) if index > 0 else math.nan
            atr7 = float(context.features.atr7[index])
            slope_atr = (
                (ma7 - prior_ma7) / atr7
                if all(math.isfinite(value) for value in (ma7, prior_ma7, atr7))
                and atr7 > 0.0
                else math.nan
            )
            decay_run = decay_run + 1 if math.isfinite(slope_atr) and slope_atr <= 0.0 else 0
            close_return = float(context.book.close[index]) / entry_price - 1.0
            mfe_return = (
                float(np.max(context.book.high[entry_day : index + 1])) / entry_price
                - 1.0
            )
            next_open = (
                float(context.book.open[index + 1])
                if index + 1 < limit_index
                else None
            )
            hypothetical = {
                str(days): bool(
                    decay_run >= days
                    and close_return > 0.0028
                    and next_open is not None
                )
                for days in (2, 3)
            }
            rows.append(
                {
                    "trade_index": trade_index,
                    "entry_ts": trade["entry_ts"],
                    "actual_exit_ts": trade["exit_ts"],
                    "held_day_index": index,
                    "held_day_ts": pd.Timestamp(context.book.ts[index]).isoformat(),
                    "slope_atr": slope_atr if math.isfinite(slope_atr) else None,
                    "decay_run": decay_run,
                    "close_gross_return_pct": close_return * 100.0,
                    "mfe_return_pct": mfe_return * 100.0,
                    "giveback_from_mfe_pp": (mfe_return - close_return) * 100.0,
                    "hypothetical_trigger": hypothetical,
                    "hypothetical_next_open": next_open,
                }
            )
    return rows


def stage_development() -> dict[str, Any]:
    manifest = assert_manifest()
    for path in (TRIALS_PATH, DEVELOPMENT_PATH, CHAMPION_PATH):
        if path.exists() or sidecar(path).exists():
            raise RuntimeError(f"development artifact exists: {path.name}")
    engine, risk, adapter, context = load_runtime()
    control = {
        "arm_id": "C000_EXACT_V4",
        "config": None,
        "base_full": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=None, slippage=BASE_SLIPPAGE, retain=True),
        "base_folds": [run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=None, slippage=BASE_SLIPPAGE, retain=False) for fold in WFO_FOLDS],
        "stress_full": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=None, slippage=STRESS_SLIPPAGE, retain=False),
        "stress_folds": [run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=None, slippage=STRESS_SLIPPAGE, retain=False) for fold in WFO_FOLDS],
    }
    control["base_wfo"] = aggregate_folds(control["base_folds"])
    control["stress_wfo"] = aggregate_folds(control["stress_folds"])
    trials = [control]
    config_objects: dict[str, Any] = {}
    for config in engine.ranked_configs():
        config_objects[config.arm_id] = config
        trial = {
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "base_full": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config, slippage=BASE_SLIPPAGE, retain=True),
            "base_folds": [run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=config, slippage=BASE_SLIPPAGE, retain=False) for fold in WFO_FOLDS],
            "stress_full": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config, slippage=STRESS_SLIPPAGE, retain=False),
            "stress_folds": [run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=config, slippage=STRESS_SLIPPAGE, retain=False) for fold in WFO_FOLDS],
        }
        trial["base_wfo"] = aggregate_folds(trial["base_folds"])
        trial["stress_wfo"] = aggregate_folds(trial["stress_folds"])
        trial["gate"] = numeric_gate(trial, control)
        trials.append(trial)
    numeric_passers = [trial for trial in trials[1:] if trial["gate"]["status"] == "PASS"]
    for trial in numeric_passers:
        config = config_objects[trial["arm_id"]]
        oat = []
        for module in enabled_modules(trial["config"]):
            disabled = engine.oat_config(config, module)
            disabled_run = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=disabled, slippage=BASE_SLIPPAGE, retain=True)
            changed = trial["base_full"]["trades_sha256"] != disabled_run["trades_sha256"] or trial["base_full"]["path_sha256"] != disabled_run["path_sha256"]
            active = module_active(module, trial["base_full"]["activation_counts"])
            oat.append({"module": module, "disabled_config": disabled.canonical(), "activation_pass": active, "economic_path_changed": changed, "status": "PASS" if active and changed else "FAIL", "disabled_evidence": disabled_run})
        trial["module_oat"] = oat
        trial["gate"]["checks"]["module_wiring"] = all(row["status"] == "PASS" for row in oat)
        trial["gate"]["status"] = "PASS" if all(trial["gate"]["checks"].values()) else "FAIL"
    passers = [trial for trial in trials[1:] if trial["gate"]["status"] == "PASS"]
    ranked = sorted(passers, key=rank_key)
    champion = ranked[0] if ranked else None
    event_study = {
        "natural_entries": entry_event_study(
            context,
            control["base_full"]["trades"],
        ),
        "long_held_days": long_decay_event_study(
            context,
            control["base_full"]["trades"],
        ),
        "right_boundary_exclusive": D_FULL[1],
        "v_h_accessed": False,
    }
    assert_pins(manifest["pins"])
    trials_payload = {"schema": "hype-tpr-development-trials-v1", "manifest_sha256": sha256(MANIFEST_PATH), "trial_count": len(trials), "event_study": event_study, "trials": trials}
    trials_digest = write_locked(TRIALS_PATH, trials_payload)
    development = {
        "schema": "hype-tpr-development-v1",
        "status": "PASS" if champion else "FAIL",
        "hard_gate": "PASS" if champion else "FAIL",
        "research_state": "explore / not promoted / not live-ready",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "trials_sha256": trials_digest,
        "control": {"base_full": control["base_full"]["metrics"], "base_wfo": control["base_wfo"], "stress_full": control["stress_full"]["metrics"], "stress_wfo": control["stress_wfo"]},
        "passers": [trial["arm_id"] for trial in ranked],
        "champion_arm_id": champion["arm_id"] if champion else None,
        "all_arm_summary": [{"arm_id": trial["arm_id"], "config": trial.get("config"), "base_full": trial["base_full"]["metrics"], "base_wfo": trial["base_wfo"], "gate": trial.get("gate", {"status": "CONTROL"})} for trial in trials],
        "v_h_revealed": False,
        "leverage_researched": False,
    }
    development_digest = write_locked(DEVELOPMENT_PATH, development)
    if champion:
        write_locked(CHAMPION_PATH, {"schema": "hype-tpr-champion-v1", "arm_id": champion["arm_id"], "config": champion["config"], "config_sha256": champion["config_sha256"], "gate": champion["gate"], "manifest_sha256": sha256(MANIFEST_PATH), "trials_sha256": trials_digest, "development_sha256": development_digest, "implementation_pins": manifest["pins"]})
    return development


def load_champion() -> tuple[dict[str, Any], dict[str, Any], Any]:
    manifest = assert_manifest()
    development, _ = read_locked(DEVELOPMENT_PATH)
    if development.get("status") != "PASS":
        raise RuntimeError("development did not pass")
    champion, _ = read_locked(CHAMPION_PATH)
    if champion["implementation_pins"] != manifest["pins"]:
        raise RuntimeError("champion implementation drift")
    engine = load_module(ENGINE_PATH, "hype_tpr_champion_engine")
    config = engine.TPRConfig(**champion["config"])
    return manifest, champion, config


def evaluation_gate(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    comparison = compare(candidate["metrics"], control["metrics"])
    checks = {
        "dual_dominance": comparison["return_higher"] and comparison["chronological_mdd_smaller"] and comparison["material"],
        "candidate_trade_floor": int(candidate["metrics"]["closed_trades"]) >= 3,
        "control_trade_floor": int(control["metrics"]["closed_trades"]) >= 3,
        "daily_stress": not comparison["daily_stress_double_worse"],
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "comparison": comparison}


def stage_validation() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    if VALIDATION_PATH.exists() or sidecar(VALIDATION_PATH).exists():
        raise RuntimeError("validation already consumed")
    if LEVERAGE_PATH.exists() or HOLDOUT_PATH.exists() or FINAL_PATH.exists():
        raise RuntimeError("downstream artifact exists")
    engine, risk, adapter, context = load_runtime()
    control = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=V_EVAL, config=None, slippage=BASE_SLIPPAGE, retain=True)
    candidate = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=V_EVAL, config=config, slippage=BASE_SLIPPAGE, retain=True)
    gate = evaluation_gate(candidate, control)
    payload = {"schema": "hype-tpr-validation-v1", "status": gate["status"], "hard_gate": gate["status"], "research_state": "explore / not promoted / not live-ready", "manifest_sha256": sha256(MANIFEST_PATH), "champion_sha256": sha256(CHAMPION_PATH), "arm_id": champion["arm_id"], "window": V_EVAL, "control": control, "candidate": candidate, "gate": gate}
    assert_pins(manifest["pins"])
    write_locked(VALIDATION_PATH, payload)
    return payload


def leverage_eligible(row: dict[str, Any], cap: float) -> bool:
    domains = (row["D"]["base"]["metrics"], row["V"]["base"]["metrics"])
    stress = (row["D"]["stress"]["metrics"], row["V"]["stress"]["metrics"])
    one_x = (row["D"]["one_x_metrics"], row["V"]["one_x_metrics"])
    return bool(
        all(float(domain["net_return_pct"]) > float(base["net_return_pct"]) for domain, base in zip(domains, one_x))
        and all(abs(float(domain["chronological_1h_mdd_pct"])) <= cap for domain in domains)
        and all(not bool(domain["bankrupt_intraday"]) for domain in (*domains, *stress))
    )


def leverage_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    deltas = [float(row[domain]["base"]["metrics"]["net_return_pct"]) - float(row[domain]["one_x_metrics"]["net_return_pct"]) for domain in ("D", "V")]
    compound = math.prod(float(row[domain]["base"]["metrics"]["equity_multiple"]) for domain in ("D", "V"))
    worst_mdd = min(float(row[domain]["base"]["metrics"]["chronological_1h_mdd_pct"]) for domain in ("D", "V"))
    max_lev = max(float(row[domain]["base"]["metrics"]["max_marked_leverage"]) for domain in ("D", "V"))
    return (-min(deltas), -compound, -worst_mdd, max_lev, row["spec"]["id"])


def stage_leverage() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    validation, _ = read_locked(VALIDATION_PATH)
    if validation.get("status") != "PASS":
        raise RuntimeError("validation did not pass")
    if LEVERAGE_PATH.exists() or sidecar(LEVERAGE_PATH).exists():
        raise RuntimeError("leverage stage already consumed")
    if HOLDOUT_PATH.exists() or FINAL_PATH.exists():
        raise RuntimeError("holdout/final exists")
    engine, risk, adapter, context = load_runtime()
    one_x_d = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config, slippage=BASE_SLIPPAGE, retain=False)
    one_x_v = validation["candidate"]
    rows = []
    for spec in engine.leverage_specs():
        row = {"spec": asdict(spec)}
        for label, window, one_x in (("D", D_FULL, one_x_d), ("V", V_EVAL, one_x_v)):
            base = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, slippage=BASE_SLIPPAGE, retain=True, leverage_spec=spec)
            stress = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, slippage=STRESS_SLIPPAGE, retain=False, leverage_spec=spec)
            no_funding = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, slippage=BASE_SLIPPAGE, retain=False, leverage_spec=spec, include_funding=False)
            row[label] = {"one_x_metrics": one_x["metrics"], "base": base, "stress": stress, "funding_off": no_funding}
        row["eligible_35"] = leverage_eligible(row, 35.0)
        row["eligible_50"] = leverage_eligible(row, 50.0)
        rows.append(row)
    primary = sorted([row for row in rows if row["eligible_35"]], key=leverage_rank)
    aggressive = sorted([row for row in rows if row["eligible_50"]], key=leverage_rank)
    payload = {"schema": "hype-tpr-leverage-development-v1", "status": "PASS" if primary else "NO_PRIMARY", "research_state": "explore / not promoted / not live-ready", "manifest_sha256": sha256(MANIFEST_PATH), "champion_sha256": sha256(CHAMPION_PATH), "validation_sha256": sha256(VALIDATION_PATH), "signal_arm_id": champion["arm_id"], "rows": rows, "primary_spec_id": primary[0]["spec"]["id"] if primary else None, "aggressive_spec_id": aggressive[0]["spec"]["id"] if aggressive else None, "holdout_revealed": False}
    assert_pins(manifest["pins"])
    write_locked(LEVERAGE_PATH, payload)
    return payload


def stage_holdout() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    validation, _ = read_locked(VALIDATION_PATH)
    leverage, _ = read_locked(LEVERAGE_PATH)
    if validation.get("status") != "PASS":
        raise RuntimeError("validation did not pass")
    if HOLDOUT_PATH.exists() or sidecar(HOLDOUT_PATH).exists():
        raise RuntimeError("holdout already consumed")
    if FINAL_PATH.exists():
        raise RuntimeError("final exists")
    engine, risk, adapter, context = load_runtime()
    control = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=None, slippage=BASE_SLIPPAGE, retain=True)
    one_x = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, slippage=BASE_SLIPPAGE, retain=True)
    one_x_gate = evaluation_gate(one_x, control)
    leverage_rows = []
    spec_by_id = {spec.id: spec for spec in engine.leverage_specs()}
    for frozen in leverage["rows"]:
        spec = spec_by_id[frozen["spec"]["id"]]
        base = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, slippage=BASE_SLIPPAGE, retain=True, leverage_spec=spec)
        stress = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, slippage=STRESS_SLIPPAGE, retain=False, leverage_spec=spec)
        leverage_rows.append({"spec": frozen["spec"], "D_V_eligible_35": frozen["eligible_35"], "D_V_eligible_50": frozen["eligible_50"], "H_base": base, "H_stress": stress, "H_within_35": abs(float(base["metrics"]["chronological_1h_mdd_pct"])) <= 35.0, "H_within_50": abs(float(base["metrics"]["chronological_1h_mdd_pct"])) <= 50.0})
    status = one_x_gate["status"]
    payload = {"schema": "hype-tpr-holdout-v1", "status": status, "hard_gate": status, "research_state": "explore / not promoted / not live-ready", "manifest_sha256": sha256(MANIFEST_PATH), "champion_sha256": sha256(CHAMPION_PATH), "validation_sha256": sha256(VALIDATION_PATH), "leverage_sha256": sha256(LEVERAGE_PATH), "window": H_EVAL, "control": control, "one_x": one_x, "one_x_gate": one_x_gate, "leverage_rows": leverage_rows}
    assert_pins(manifest["pins"])
    write_locked(HOLDOUT_PATH, payload)
    return payload


def frontier_row(
    identifier: str,
    kind: str,
    run: dict[str, Any],
    *,
    target_leverage: float,
    frozen_eligible_35: bool,
    frozen_eligible_50: bool,
) -> dict[str, Any]:
    metrics = run["metrics"]
    return {
        "id": identifier,
        "kind": kind,
        "target_leverage": target_leverage,
        "max_marked_leverage": metrics["max_marked_leverage"],
        "net_return_pct": metrics["net_return_pct"],
        "chronological_1h_mdd_pct": metrics["chronological_1h_mdd_pct"],
        "daily_extreme_mdd_pct": metrics["daily_extreme_mdd_pct"],
        "closed_trades": metrics["closed_trades"],
        "bankrupt_intraday": metrics["bankrupt_intraday"],
        "frozen_eligible_35": frozen_eligible_35,
        "frozen_eligible_50": frozen_eligible_50,
    }


def stage_finalize() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    holdout, _ = read_locked(HOLDOUT_PATH)
    leverage, _ = read_locked(LEVERAGE_PATH)
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists():
        raise RuntimeError("final artifact already exists")
    engine, risk, adapter, context = load_runtime()
    full_control = run_one(
        engine=engine,
        risk=risk,
        adapter=adapter,
        context=context,
        window=(0, context.book.count),
        config=None,
        slippage=BASE_SLIPPAGE,
        retain=False,
    )
    full_one_x = run_one(
        engine=engine,
        risk=risk,
        adapter=adapter,
        context=context,
        window=(0, context.book.count),
        config=config,
        slippage=BASE_SLIPPAGE,
        retain=False,
    )
    h_rows = [
        frontier_row(
            "EXACT_V4_1X",
            "control",
            holdout["control"],
            target_leverage=1.0,
            frozen_eligible_35=True,
            frozen_eligible_50=True,
        ),
        frontier_row(
            f"{champion['arm_id']}_1X",
            "signal_1x",
            holdout["one_x"],
            target_leverage=1.0,
            frozen_eligible_35=holdout["one_x_gate"]["status"] == "PASS",
            frozen_eligible_50=holdout["one_x_gate"]["status"] == "PASS",
        ),
    ]
    full_rows = [
        frontier_row(
            "EXACT_V4_1X",
            "control",
            full_control,
            target_leverage=1.0,
            frozen_eligible_35=True,
            frozen_eligible_50=True,
        ),
        frontier_row(
            f"{champion['arm_id']}_1X",
            "signal_1x",
            full_one_x,
            target_leverage=1.0,
            frozen_eligible_35=holdout["one_x_gate"]["status"] == "PASS",
            frozen_eligible_50=holdout["one_x_gate"]["status"] == "PASS",
        ),
    ]
    spec_by_id = {spec.id: spec for spec in engine.leverage_specs()}
    leverage_by_id = {row["spec"]["id"]: row for row in leverage["rows"]}
    full_leverage_runs: list[dict[str, Any]] = []
    for h_evidence in holdout["leverage_rows"]:
        spec_id = h_evidence["spec"]["id"]
        spec = spec_by_id[spec_id]
        frozen = leverage_by_id[spec_id]
        h_rows.append(
            frontier_row(
                spec_id,
                spec.kind,
                h_evidence["H_base"],
                target_leverage=spec.value,
                frozen_eligible_35=bool(frozen["eligible_35"]),
                frozen_eligible_50=bool(frozen["eligible_50"]),
            )
        )
        full_run = run_one(
            engine=engine,
            risk=risk,
            adapter=adapter,
            context=context,
            window=(0, context.book.count),
            config=config,
            slippage=BASE_SLIPPAGE,
            retain=False,
            leverage_spec=spec,
        )
        full_leverage_runs.append({"spec": h_evidence["spec"], "run": full_run})
        full_rows.append(
            frontier_row(
                spec_id,
                spec.kind,
                full_run,
                target_leverage=spec.value,
                frozen_eligible_35=bool(frozen["eligible_35"]),
                frozen_eligible_50=bool(frozen["eligible_50"]),
            )
        )
    caps = (20.0, 25.0, 30.0, 35.0, 40.0, 50.0)
    payload = {
        "schema": "hype-tpr-final-v1",
        "status": holdout["status"],
        "hard_gate": holdout["hard_gate"],
        "research_state": "explore / not promoted / not live-ready",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "champion_sha256": sha256(CHAMPION_PATH),
        "validation_sha256": sha256(VALIDATION_PATH),
        "leverage_sha256": sha256(LEVERAGE_PATH),
        "holdout_sha256": sha256(HOLDOUT_PATH),
        "signal_arm_id": champion["arm_id"],
        "h": {
            "rows": h_rows,
            "pareto_all_arms": risk.pareto_frontier(h_rows),
            "best_by_mdd_cap_all_arms": risk.best_by_mdd_caps(h_rows, caps),
        },
        "full_window": {
            "window": (0, context.book.count),
            "rows": full_rows,
            "pareto_all_arms": risk.pareto_frontier(full_rows),
            "best_by_mdd_cap_all_arms": risk.best_by_mdd_caps(full_rows, caps),
            "control": full_control,
            "one_x": full_one_x,
            "leverage_runs": full_leverage_runs,
        },
        "interpretation_guard": (
            "all-arm cap tables are descriptive after one-shot H; only rows with "
            "frozen_eligible_35/50 were eligible before H"
        ),
    }
    assert_pins(manifest["pins"])
    write_locked(FINAL_PATH, payload)
    return payload


def self_test() -> dict[str, Any]:
    engine, risk, _, _ = load_runtime()
    assert len(engine.ranked_configs()) == 12
    assert len(engine.leverage_specs()) == 9
    assert engine_start((0, 10)) == 0 and engine_start((10, 20)) == 11
    rows = [{"id": "a", "net_return_pct": 2.0, "chronological_1h_mdd_pct": -2.0}, {"id": "b", "net_return_pct": 1.0, "chronological_1h_mdd_pct": -3.0}]
    assert [row["id"] for row in risk.pareto_frontier(rows)] == ["a"]
    return {"status": "PASS", "candidate_count": 12, "leverage_count": 9}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=(
            "self-test",
            "manifest",
            "development",
            "validation",
            "leverage",
            "holdout",
            "finalize",
        ),
    )
    args = parser.parse_args()
    if args.stage == "self-test":
        result = self_test()
    elif args.stage == "manifest":
        result = stage_manifest()
    elif args.stage == "development":
        result = stage_development()
    elif args.stage == "validation":
        result = stage_validation()
    elif args.stage == "leverage":
        result = stage_leverage()
    elif args.stage == "holdout":
        result = stage_holdout()
    else:
        result = stage_finalize()
    print(json.dumps(canonical(result), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
