"""Post-reveal V6 missed-trend attribution and isolated probe audit.

The hindsight stable-trend labels are used only to describe coverage.  Probe
entries are generated exclusively from causal raw MA7 crosses and the frozen
V6 buffer/slope thresholds.  The exact V6 trade schedule always has priority.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-v6-missed-trend-attribution-contract-2026-08-10.md"
)
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
TRANSITION_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_transition_repair_engine.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
LABEL_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
R3_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r3_walk_forward_identifiability.py"
R4_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r4_stable_segment.py"
SELF_PATH = Path(__file__).resolve()
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v6_missed_trend_attribution.py"
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_v6_missed_trend_attribution_2026-08-10.json"
)
OUTPUT_SHA_PATH = OUTPUT_PATH.with_suffix(".sha256")

EXPECTED_BOOK_COUNT = 432
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_TRADES = 19
EXPECTED_V6_CONFIG_SHA256 = (
    "b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00"
)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
PROBE_LEVERAGE = 0.25
ROOT_MAX_AGE_DAYS = 5
PROBE_MAX_HOLD_DAYS = 5
FORWARD_DAYS = 5
ROUNDTRIP_GUARD = 0.0028
RECENT_WINDOWS = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}

IMPLEMENTATION_PATHS = (
    CONTRACT_PATH,
    ADAPTER_PATH,
    TRANSITION_PATH,
    RISK_PATH,
    LABEL_ENGINE_PATH,
    R3_PATH,
    R4_PATH,
    SELF_PATH,
    TEST_PATH,
)


@dataclass(frozen=True, slots=True)
class Runtime:
    adapter: ModuleType
    transition: ModuleType
    risk: ModuleType
    labels: ModuleType
    r3: ModuleType
    r4: ModuleType
    context: Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit exact V6 missed trends and a state-isolated probe."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the payload without writing locked artifacts.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip pytest preflight; intended only for local debugging.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [sanitize(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        sanitize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_runtime() -> Runtime:
    adapter = _load(ADAPTER_PATH, "v6_missed_attribution_adapter")
    transition = _load(TRANSITION_PATH, "v6_missed_attribution_transition")
    risk = _load(RISK_PATH, "v6_missed_attribution_risk")
    labels = _load(LABEL_ENGINE_PATH, "v6_missed_attribution_labels")
    r3 = _load(R3_PATH, "v6_missed_attribution_r3")
    r4 = _load(R4_PATH, "v6_missed_attribution_r4")
    context = adapter.load_context()
    if context.book.count != EXPECTED_BOOK_COUNT:
        raise RuntimeError("frozen daily book count drift")
    return Runtime(adapter, transition, risk, labels, r3, r4, context)


def implementation_pins() -> dict[str, str]:
    missing = [path for path in IMPLEMENTATION_PATHS if not path.exists()]
    if missing:
        raise RuntimeError(f"missing implementation files: {missing}")
    return {
        str(path.relative_to(ROOT)): sha256(path)
        for path in IMPLEMENTATION_PATHS
    }


def run_preflight() -> dict[str, Any]:
    before = implementation_pins()
    tests = (
        TEST_PATH,
        ROOT / "tests/test_hype_1d_ma7_v6_transition_repair_engine.py",
        ROOT / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_engine.py",
        ROOT / "tests/test_hype_1d_ma7_ctls_r4_stable_segment.py",
    )
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/pytest"), "-q", *(str(path) for path in tests)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(
        value for value in (completed.stdout, completed.stderr) if value
    ).strip()
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    after = implementation_pins()
    result = {
        "status": (
            "PASS"
            if completed.returncode == 0 and passed > 0 and before == after
            else "FAIL"
        ),
        "passed": passed,
        "returncode": completed.returncode,
        "pins_stable": before == after,
        "tests": [str(path.relative_to(ROOT)) for path in tests],
        "output": output,
    }
    if result["status"] != "PASS":
        raise RuntimeError(f"preflight failed: {result}")
    return result


def _ts_at(context: Any, index: int) -> pd.Timestamp:
    if index < context.book.count:
        return pd.Timestamp(context.book.ts[index])
    if index == context.book.count:
        return pd.Timestamp(context.book.terminal_ts)
    raise IndexError(index)


def _open_at(context: Any, index: int) -> float:
    if index < context.book.count:
        return float(context.book.open[index])
    if index == context.book.count:
        return float(context.book.quality["terminal_open"])
    raise IndexError(index)


def _side_value(value: Any) -> int:
    if isinstance(value, str):
        if value == "long":
            return 1
        if value == "short":
            return -1
    integer = int(value)
    if integer not in (-1, 1):
        raise ValueError(f"invalid side: {value}")
    return integer


def _side_name(side: int) -> str:
    return "long" if side > 0 else "short"


def _economic_trade_identity(trades: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "entry_ts",
        "exit_ts",
        "side",
        "entry_price",
        "exit_price",
        "exit_reason",
    )
    return [
        {field: row.get(field) for field in fields}
        for row in trades
    ]


def _entry_source(action: str) -> str:
    if action == "pehc_handoff_enter_short":
        return "PEHC_HANDOFF"
    if action.startswith("reverse_"):
        return "FORCED_REVERSAL"
    if action in ("enter_long", "enter_short"):
        return "NATIVE"
    return "UNKNOWN"


def build_core_schedule(context: Any, raw: Any) -> list[dict[str, Any]]:
    actions = {
        pd.Timestamp(row["ts"]).floor("D"): str(row["action"])
        for row in raw.path
    }
    schedule: list[dict[str, Any]] = []
    for index, trade in enumerate(raw.trades, 1):
        entry_ts = pd.Timestamp(trade["entry_ts"])
        action = actions.get(entry_ts.floor("D"), "unknown")
        schedule.append(
            {
                "trade_id": f"V6T{index:03d}",
                "source": "core",
                "root_id": None,
                "side": _side_value(trade["side"]),
                "entry_ts": entry_ts,
                "exit_ts": pd.Timestamp(trade["exit_ts"]),
                "entry_price": float(trade["entry_price"]),
                "exit_price": float(trade["exit_price"]),
                "leverage": float(trade.get("entry_leverage", 1.0)),
                "exit_reason": str(trade["exit_reason"]),
                "entry_source": _entry_source(action),
                "path_action": action,
            }
        )
    return schedule


def _schedule_identity(schedule: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "source",
        "root_id",
        "side",
        "entry_ts",
        "exit_ts",
        "entry_price",
        "exit_price",
        "leverage",
        "exit_reason",
    )
    return [
        {field: sanitize(row.get(field)) for field in fields}
        for row in schedule
    ]


def replay_schedule(
    runtime: Runtime,
    schedule: Iterable[dict[str, Any]],
    *,
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
) -> dict[str, Any]:
    context = runtime.context
    risk = runtime.risk
    rows = sorted(
        (dict(row) for row in schedule),
        key=lambda row: (pd.Timestamp(row["entry_ts"]), 0 if row["source"] == "probe" else 1),
    )
    previous_exit: pd.Timestamp | None = None
    for row in rows:
        entry_ts = pd.Timestamp(row["entry_ts"])
        exit_ts = pd.Timestamp(row["exit_ts"])
        if entry_ts >= exit_ts:
            raise RuntimeError(f"non-positive trade duration: {row}")
        if previous_exit is not None and entry_ts < previous_exit:
            raise RuntimeError(f"overlapping scheduled trades: {row}")
        previous_exit = exit_ts

    hourly = risk._hourly_marks(context)
    funding = risk._funding_events(context) if include_funding else []
    cost_rate = float(context.engine.FEE) + float(slippage)
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    worst_ts: str | None = None
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    points: list[dict[str, Any]] = []
    replayed: list[dict[str, Any]] = []

    def observe(ts: pd.Timestamp, marked: float, kind: str) -> None:
        nonlocal peak, mdd, worst_ts
        if not math.isfinite(marked) or marked <= 0.0:
            raise RuntimeError(f"non-positive marked equity at {ts}: {marked}")
        peak = max(peak, marked)
        drawdown = marked / peak - 1.0
        if drawdown < mdd:
            mdd = drawdown
            worst_ts = ts.isoformat()
        points.append({"ts": ts, "equity": float(marked), "kind": kind})

    observe(pd.Timestamp(context.book.ts[0]), equity, "start")
    for trade_index, row in enumerate(rows):
        entry_ts = pd.Timestamp(row["entry_ts"])
        exit_ts = pd.Timestamp(row["exit_ts"])
        side = _side_value(row["side"])
        entry_price = float(row["entry_price"])
        exit_price = float(row["exit_price"])
        leverage = float(row["leverage"])
        entry_equity = equity
        qty, equity, turnover = risk.target_quantity(
            equity,
            0.0,
            side,
            entry_price,
            cost_rate,
            leverage,
        )
        total_turnover += turnover
        total_cost += entry_equity - equity
        observe(entry_ts, entry_equity, f"trade_{trade_index}_entry_pre_cost")
        observe(entry_ts, equity, f"trade_{trade_index}_entry_post_cost")
        base_equity = equity
        cumulative_funding = 0.0
        trade_min = equity
        trade_max = equity
        event_rows: list[tuple[pd.Timestamp, int, str, float, Any | None]] = []
        for ts, price in hourly:
            if entry_ts < ts < exit_ts:
                event_rows.append((ts, 0, "hourly_open", float(price), None))
        for event in funding:
            event_ts = pd.Timestamp(event.ts)
            if entry_ts <= event_ts < exit_ts:
                event_rows.append(
                    (event_ts, 1, "funding", float(event.price), event)
                )
        event_rows.sort(key=lambda item: (item[0], item[1]))
        for event_ts, _, kind, price, event in event_rows:
            marked = base_equity + qty * (price - entry_price) - cumulative_funding
            observe(event_ts, marked, f"trade_{trade_index}_{kind}_pre")
            trade_min = min(trade_min, marked)
            trade_max = max(trade_max, marked)
            if kind == "funding":
                if event is None:
                    raise RuntimeError("missing funding payload")
                payment = qty * price * float(event.rate)
                cumulative_funding += payment
                total_funding += payment
                marked -= payment
                observe(event_ts, marked, f"trade_{trade_index}_funding_post")
                trade_min = min(trade_min, marked)
                trade_max = max(trade_max, marked)
        before_exit = (
            base_equity + qty * (exit_price - entry_price) - cumulative_funding
        )
        observe(exit_ts, before_exit, f"trade_{trade_index}_exit_pre_cost")
        trade_min = min(trade_min, before_exit)
        trade_max = max(trade_max, before_exit)
        old_equity = before_exit
        _, equity, turnover = risk.target_quantity(
            before_exit,
            qty,
            0,
            exit_price,
            cost_rate,
            1.0,
        )
        total_turnover += turnover
        total_cost += old_equity - equity
        observe(exit_ts, equity, f"trade_{trade_index}_exit_post_cost")
        trade_min = min(trade_min, equity)
        trade_max = max(trade_max, equity)
        replayed.append(
            {
                **sanitize(row),
                "entry_equity": float(entry_equity),
                "exit_equity": float(equity),
                "net_return": float(equity / entry_equity - 1.0),
                "net_pnl": float(equity - entry_equity),
                "mae_pct_entry_equity": float(
                    (trade_min / entry_equity - 1.0) * 100.0
                ),
                "mfe_pct_entry_equity": float(
                    (trade_max / entry_equity - 1.0) * 100.0
                ),
            }
        )
    terminal_ts = pd.Timestamp(context.book.terminal_ts)
    observe(terminal_ts, equity, "terminal")
    pnl = np.asarray([float(row["net_pnl"]) for row in replayed], dtype=float)
    gross_profit = float(pnl[pnl > 0.0].sum()) if len(pnl) else 0.0
    gross_loss = float(-pnl[pnl < 0.0].sum()) if len(pnl) else 0.0
    metrics = {
        "equity_multiple": float(equity),
        "net_return_pct": float((equity - 1.0) * 100.0),
        "chronological_1h_mdd_pct": float(mdd * 100.0),
        "worst_ts": worst_ts,
        "closed_trades": len(replayed),
        "core_trades": sum(row["source"] == "core" for row in replayed),
        "probe_trades": sum(row["source"] == "probe" for row in replayed),
        "long_trades": sum(int(row["side"]) > 0 for row in replayed),
        "short_trades": sum(int(row["side"]) < 0 for row in replayed),
        "win_rate": (
            float(np.mean(pnl > 0.0)) if len(pnl) else None
        ),
        "profit_factor": (
            float(gross_profit / gross_loss) if gross_loss > 0.0 else None
        ),
        "turnover_multiple": float(total_turnover),
        "cost_pct_initial": float(total_cost * 100.0),
        "funding_pct_initial": float(total_funding * 100.0),
    }
    return {
        "metrics": metrics,
        "trades": replayed,
        "recent_slices": recent_slices(points, terminal_ts, equity),
        "schedule_sha256": canonical_hash(_schedule_identity(rows)),
        "_points": points,
    }


def recent_slices(
    points: list[dict[str, Any]],
    terminal_ts: pd.Timestamp,
    terminal_equity: float,
) -> dict[str, Any]:
    ordered = sorted(
        enumerate(points),
        key=lambda item: (pd.Timestamp(item[1]["ts"]), item[0]),
    )
    rows = [row for _, row in ordered]
    output: dict[str, Any] = {}
    for label, days in RECENT_WINDOWS.items():
        start_ts = terminal_ts - pd.Timedelta(days=days)
        prior = [
            row for row in rows if pd.Timestamp(row["ts"]) <= start_ts
        ]
        start_equity = float(prior[-1]["equity"]) if prior else 1.0
        window_equities = [start_equity]
        window_equities.extend(
            float(row["equity"])
            for row in rows
            if pd.Timestamp(row["ts"]) > start_ts
        )
        peak = start_equity
        mdd = 0.0
        for equity in window_equities:
            peak = max(peak, equity)
            mdd = min(mdd, equity / peak - 1.0)
        output[label] = {
            "start_ts": start_ts.isoformat(),
            "end_ts": terminal_ts.isoformat(),
            "net_return_pct": (terminal_equity / start_equity - 1.0) * 100.0,
            "chronological_1h_mdd_pct": mdd * 100.0,
        }
    return output


def _center_regression_diagnostics(
    daily: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    close = daily["close"].to_numpy(float)
    atr7 = daily["atr7"].to_numpy(float)
    beta_atr = np.full(len(daily), np.nan)
    r_squared = np.full(len(daily), np.nan)
    x = np.arange(-3.0, 4.0)
    x_ss = float(np.dot(x, x))
    for index in range(3, len(daily) - 3):
        if not math.isfinite(atr7[index]) or atr7[index] <= 0.0:
            continue
        values = close[index - 3 : index + 4]
        if not np.isfinite(values).all():
            continue
        centered = values - float(values.mean())
        beta = float(np.dot(x, centered) / x_ss)
        fitted = beta * x
        total = float(np.dot(centered, centered))
        residual = float(np.dot(centered - fitted, centered - fitted))
        beta_atr[index] = beta / atr7[index]
        r_squared[index] = (
            0.0 if total <= 0.0 else max(0.0, 1.0 - residual / total)
        )
    return beta_atr, r_squared


def extract_reference_episodes(
    stable: pd.Series,
    daily: pd.DataFrame,
    raw_labels: pd.Series,
) -> list[dict[str, Any]]:
    beta_atr, r_squared = _center_regression_diagnostics(daily)
    values = stable.to_numpy(float)
    episodes: list[dict[str, Any]] = []
    index = 0
    while index < len(values):
        if not math.isfinite(values[index]) or int(values[index]) == 0:
            index += 1
            continue
        side = int(values[index])
        end = index
        while (
            end + 1 < len(values)
            and math.isfinite(values[end + 1])
            and int(values[end + 1]) == side
        ):
            end += 1
        episode_values = beta_atr[index : end + 1]
        episode_r2 = r_squared[index : end + 1]
        finite_beta = episode_values[np.isfinite(episode_values)]
        finite_r2 = episode_r2[np.isfinite(episode_r2)]
        labels = [
            str(value)
            for value in raw_labels.iloc[index : end + 1]
            if pd.notna(value)
        ]
        episodes.append(
            {
                "episode_id": f"REF{len(episodes) + 1:03d}",
                "direction": _side_name(side),
                "side": side,
                "start_index": index,
                "end_index": end,
                "start_ts": pd.Timestamp(daily.index[index]).isoformat(),
                "end_ts": pd.Timestamp(daily.index[end]).isoformat(),
                "interval_end_ts": (
                    pd.Timestamp(daily.index[end]) + pd.Timedelta(days=1)
                ).isoformat(),
                "duration_days": end - index + 1,
                "median_beta7_atr": (
                    float(np.median(finite_beta)) if len(finite_beta) else None
                ),
                "median_r_squared": (
                    float(np.median(finite_r2)) if len(finite_r2) else None
                ),
                "raw_label_counts": dict(sorted(Counter(labels).items())),
                "hindsight_audit_only": True,
                "root_ids": [],
                "main_root_id": None,
            }
        )
        index = end + 1
    return episodes


def _raw_cross(context: Any, index: int) -> int:
    if index < 1:
        return 0
    values = (
        float(context.book.close[index - 1]),
        float(context.features.ma7[index - 1]),
        float(context.book.close[index]),
        float(context.features.ma7[index]),
    )
    if not all(math.isfinite(value) for value in values):
        return 0
    prior_close, prior_ma7, close, ma7 = values
    if prior_close <= prior_ma7 and close > ma7:
        return 1
    if prior_close >= prior_ma7 and close < ma7:
        return -1
    return 0


def _criteria(context: Any, side: int, index: int) -> dict[str, Any]:
    config = context.long_config if side > 0 else context.short_config
    lookback = int(config.slope_lookback)
    if index < lookback:
        return {"finite": False}
    close = float(context.book.close[index])
    ma7 = float(context.features.ma7[index])
    atr7 = float(context.features.atr7[index])
    previous_ma7 = float(context.features.ma7[index - lookback])
    finite = (
        all(math.isfinite(value) for value in (close, ma7, atr7, previous_ma7))
        and atr7 > 0.0
    )
    if not finite:
        return {"finite": False}
    distance_atr = side * (close - ma7) / atr7
    slope_atr = side * (ma7 - previous_ma7) / atr7
    return {
        "finite": True,
        "distance_atr": float(distance_atr),
        "slope_atr": float(slope_atr),
        "buffer_threshold": float(config.entry_buffer_atr),
        "slope_threshold": float(config.slope_min_atr),
        "buffer_pass": bool(distance_atr > float(config.entry_buffer_atr)),
        "slope_pass": bool(slope_atr >= float(config.slope_min_atr)),
    }


def _failure_code(criteria: dict[str, Any]) -> str:
    if not criteria.get("finite"):
        return "NONFINITE"
    buffer_pass = bool(criteria["buffer_pass"])
    slope_pass = bool(criteria["slope_pass"])
    if buffer_pass and slope_pass:
        return "PASS"
    if buffer_pass:
        return "SLOPE_SAME_DAY_FAIL"
    if slope_pass:
        return "BUFFER_SAME_DAY_FAIL"
    return "BOTH_SAME_DAY_FAIL"


def _forward_label(context: Any, index: int, side: int) -> dict[str, Any]:
    if index + FORWARD_DAYS >= context.book.count:
        return {
            "evaluable": False,
            "direction_return_5d": None,
            "same_side_closes_5d": None,
            "direction_hit": None,
            "persistence_hit": None,
            "trend_hit": None,
        }
    close = float(context.book.close[index])
    future = float(context.book.close[index + FORWARD_DAYS])
    direction_return = side * (future / close - 1.0)
    same_side = sum(
        side
        * (
            float(context.book.close[offset])
            - float(context.features.ma7[offset])
        )
        > 0.0
        for offset in range(index + 1, index + FORWARD_DAYS + 1)
    )
    direction_hit = direction_return > ROUNDTRIP_GUARD
    persistence_hit = same_side >= 3
    return {
        "evaluable": True,
        "direction_return_5d": float(direction_return),
        "same_side_closes_5d": int(same_side),
        "direction_hit": bool(direction_hit),
        "persistence_hit": bool(persistence_hit),
        "trend_hit": bool(direction_hit and persistence_hit),
    }


def _cooldown_blocked(
    cooldown_events: list[dict[str, Any]], entry_index: int
) -> tuple[bool, dict[str, Any] | None]:
    sets = [
        event
        for event in cooldown_events
        if event.get("event") == "cooldown_set"
        and int(event["index"]) <= entry_index
    ]
    if not sets:
        return False, None
    latest = max(sets, key=lambda row: int(row["index"]))
    blocked = entry_index <= int(latest["eligible_after_index"])
    return blocked, sanitize(latest) if blocked else None


def _core_at_preopen(
    core: list[dict[str, Any]], ts: pd.Timestamp
) -> list[dict[str, Any]]:
    return [
        row
        for row in core
        if pd.Timestamp(row["entry_ts"]) < ts <= pd.Timestamp(row["exit_ts"])
    ]


def _core_starts(
    core: list[dict[str, Any]], ts: pd.Timestamp
) -> list[dict[str, Any]]:
    return [
        row for row in core if pd.Timestamp(row["entry_ts"]) == ts
    ]


def _standalone_fixed_5d(
    runtime: Runtime,
    side: int,
    maturity_index: int | None,
) -> dict[str, Any] | None:
    if maturity_index is None:
        return None
    context = runtime.context
    entry_index = maturity_index + 1
    exit_index = entry_index + PROBE_MAX_HOLD_DAYS
    if entry_index >= context.book.count or exit_index > context.book.count:
        return {"evaluable": False}
    schedule = [
        {
            "trade_id": "STANDALONE",
            "source": "standalone",
            "root_id": None,
            "side": side,
            "entry_ts": _ts_at(context, entry_index),
            "exit_ts": _ts_at(context, exit_index),
            "entry_price": _open_at(context, entry_index),
            "exit_price": _open_at(context, exit_index),
            "leverage": 1.0,
            "exit_reason": "fixed_5d",
            "entry_source": "CAUSAL_ROOT",
            "path_action": "standalone",
        }
    ]
    base = replay_schedule(runtime, schedule)
    stress = replay_schedule(runtime, schedule, slippage=STRESS_SLIPPAGE)
    trade = base["trades"][0]
    return {
        "evaluable": True,
        "entry_ts": trade["entry_ts"],
        "exit_ts": trade["exit_ts"],
        "net_return_pct": float(trade["net_return"] * 100.0),
        "stress_8bps_net_return_pct": float(
            stress["trades"][0]["net_return"] * 100.0
        ),
        "mae_pct_entry_equity": float(trade["mae_pct_entry_equity"]),
        "mfe_pct_entry_equity": float(trade["mfe_pct_entry_equity"]),
        "cost_and_funding_included": True,
    }


def build_roots(
    runtime: Runtime,
    core: list[dict[str, Any]],
    cooldown_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    context = runtime.context
    roots: list[dict[str, Any]] = []
    for cross_index in range(1, context.book.count):
        side = _raw_cross(context, cross_index)
        if not side:
            continue
        cross_criteria = _criteria(context, side, cross_index)
        config = context.long_config if side > 0 else context.short_config
        native_at_cross = bool(
            context.engine.close_entry_signal(
                config,
                context.book,
                context.features,
                cross_index,
            )
        )
        maturity_index: int | None = None
        maturity_criteria: dict[str, Any] | None = None
        cancellation = "MAX_AGE"
        window_end = min(
            context.book.count - 1,
            cross_index + ROOT_MAX_AGE_DAYS,
        )
        valid_end = window_end
        for index in range(cross_index, window_end + 1):
            close = float(context.book.close[index])
            ma7 = float(context.features.ma7[index])
            if not all(math.isfinite(value) for value in (close, ma7)):
                cancellation = "NONFINITE"
                valid_end = max(cross_index, index - 1)
                break
            if index > cross_index and side * (close - ma7) <= 0.0:
                cancellation = "RECROSS"
                valid_end = index - 1
                break
            criteria = _criteria(context, side, index)
            if (
                maturity_index is None
                and criteria.get("finite")
                and bool(criteria["buffer_pass"])
                and bool(criteria["slope_pass"])
            ):
                maturity_index = index
                maturity_criteria = criteria
        execution_index = (
            maturity_index + 1 if maturity_index is not None else None
        )
        execution_ts = (
            _ts_at(context, execution_index)
            if execution_index is not None
            and execution_index <= context.book.count
            else None
        )
        execution_blocker: str | None = None
        blocker_detail: Any = None
        same_side_core = False
        if execution_ts is not None and execution_index is not None:
            starts = _core_starts(core, execution_ts)
            preopen = _core_at_preopen(core, execution_ts)
            same_side_core = any(
                int(row["side"]) == side for row in (*starts, *preopen)
            )
            if same_side_core:
                execution_blocker = "CAPTURED_AT_ELIGIBILITY"
                blocker_detail = [
                    row["trade_id"]
                    for row in (*starts, *preopen)
                    if int(row["side"]) == side
                ]
            elif starts:
                execution_blocker = "CORE_PRECEDENCE"
                blocker_detail = [row["trade_id"] for row in starts]
            elif preopen:
                execution_blocker = "POSITION_OCCUPIED"
                blocker_detail = [row["trade_id"] for row in preopen]
            else:
                blocked, cooldown = _cooldown_blocked(
                    cooldown_events, execution_index
                )
                if blocked:
                    execution_blocker = "COOLDOWN_BLOCKED"
                    blocker_detail = cooldown
                elif maturity_index > cross_index:
                    execution_blocker = "FRESHNESS_EXPIRED"
                elif native_at_cross:
                    execution_blocker = "ENGINE_INVARIANT_FAIL"
                else:
                    execution_blocker = "NATIVE_CONDITION_MISMATCH"
        if maturity_index is None:
            execution_blocker = (
                "RECROSS_BEFORE_MATURITY"
                if cancellation == "RECROSS"
                else "NO_LATER_MATURITY"
            )
        root_id = f"ROOT{len(roots) + 1:03d}"
        roots.append(
            {
                "root_id": root_id,
                "direction": _side_name(side),
                "side": side,
                "cross_index": cross_index,
                "cross_ts": _ts_at(context, cross_index).isoformat(),
                "cross_criteria": sanitize(cross_criteria),
                "cross_gate": _failure_code(cross_criteria),
                "native_at_cross": native_at_cross,
                "valid_window_end_index": valid_end,
                "valid_window_end_ts": _ts_at(context, valid_end).isoformat(),
                "cancellation": cancellation,
                "maturity_index": maturity_index,
                "maturity_ts": (
                    _ts_at(context, maturity_index).isoformat()
                    if maturity_index is not None
                    else None
                ),
                "maturity_age_days": (
                    maturity_index - cross_index
                    if maturity_index is not None
                    else None
                ),
                "maturity_criteria": sanitize(maturity_criteria),
                "later_maturity": bool(
                    maturity_index is not None and maturity_index > cross_index
                ),
                "execution_index": execution_index,
                "execution_ts": (
                    execution_ts.isoformat()
                    if execution_ts is not None
                    else None
                ),
                "execution_blocker": execution_blocker,
                "blocker_detail": sanitize(blocker_detail),
                "raw_cross_forward_label": _forward_label(
                    context, cross_index, side
                ),
                "maturity_forward_label": (
                    _forward_label(context, maturity_index, side)
                    if maturity_index is not None
                    else None
                ),
                "standalone_fixed_5d": _standalone_fixed_5d(
                    runtime, side, maturity_index
                ),
                "reference_episode_id": None,
                "hindsight_used_for_probe": False,
            }
        )
    return roots


def _overlap_hours(
    left_start: pd.Timestamp,
    left_end: pd.Timestamp,
    right_start: pd.Timestamp,
    right_end: pd.Timestamp,
) -> float:
    start = max(left_start, right_start)
    end = min(left_end, right_end)
    return max(0.0, (end - start).total_seconds() / 3600.0)


def associate_and_classify_episodes(
    episodes: list[dict[str, Any]],
    roots: list[dict[str, Any]],
    core: list[dict[str, Any]],
) -> None:
    episode_by_id = {row["episode_id"]: row for row in episodes}
    for root in roots:
        matches: list[tuple[int, int, dict[str, Any]]] = []
        for episode in episodes:
            if int(episode["side"]) != int(root["side"]):
                continue
            overlap = max(
                0,
                min(
                    int(root["valid_window_end_index"]),
                    int(episode["end_index"]),
                )
                - max(int(root["cross_index"]), int(episode["start_index"]))
                + 1,
            )
            if overlap > 0:
                matches.append(
                    (overlap, -int(episode["start_index"]), episode)
                )
        if matches:
            selected = max(matches, key=lambda item: (item[0], item[1]))[2]
            root["reference_episode_id"] = selected["episode_id"]
            selected["root_ids"].append(root["root_id"])

    roots_by_id = {row["root_id"]: row for row in roots}
    for episode in episodes:
        episode["root_ids"].sort(
            key=lambda root_id: int(roots_by_id[root_id]["cross_index"])
        )
        episode["main_root_id"] = (
            episode["root_ids"][0] if episode["root_ids"] else None
        )
        start = pd.Timestamp(episode["start_ts"])
        end = pd.Timestamp(episode["interval_end_ts"])
        same_side = []
        opposite = []
        for trade in core:
            hours = _overlap_hours(
                start,
                end,
                pd.Timestamp(trade["entry_ts"]),
                pd.Timestamp(trade["exit_ts"]),
            )
            if hours <= 0.0:
                continue
            target = (
                same_side
                if int(trade["side"]) == int(episode["side"])
                else opposite
            )
            target.append((trade, hours))
        if same_side:
            first_trade, _ = min(
                same_side,
                key=lambda item: max(
                    start, pd.Timestamp(item[0]["entry_ts"])
                ),
            )
            first_exposure = max(start, pd.Timestamp(first_trade["entry_ts"]))
            source = (
                "CARRY"
                if pd.Timestamp(first_trade["entry_ts"]) < start
                else first_trade["entry_source"]
            )
            episode.update(
                {
                    "capture_status": "CAPTURED",
                    "capture_source": source,
                    "first_exposure_ts": first_exposure.isoformat(),
                    "capture_latency_days": (
                        first_exposure - start
                    ).total_seconds()
                    / 86_400.0,
                    "same_direction_exposure_hours": sum(
                        hours for _, hours in same_side
                    ),
                    "capture_ratio": min(
                        1.0,
                        sum(hours for _, hours in same_side)
                        / (float(episode["duration_days"]) * 24.0),
                    ),
                    "same_direction_trade_ids": [
                        trade["trade_id"] for trade, _ in same_side
                    ],
                    "opposite_direction_exposure_hours": sum(
                        hours for _, hours in opposite
                    ),
                    "primary_reason": "CAPTURED",
                    "secondary_tags": [],
                }
            )
            continue
        if not episode["root_ids"]:
            primary_reason = "MISSED_HINDSIGHT_ONLY"
            tags: list[str] = []
        else:
            main = roots_by_id[str(episode["main_root_id"])]
            primary_reason = str(
                main["execution_blocker"] or main["cross_gate"]
            )
            tags = [str(main["cross_gate"])]
            if bool(main["later_maturity"]):
                tags.extend(["LATER_MATURITY", "FRESHNESS_EXPIRED"])
            standalone = main.get("standalone_fixed_5d")
            if (
                standalone
                and standalone.get("evaluable")
                and float(standalone["net_return_pct"]) <= 0.0
            ):
                tags.append("NON_ECONOMIC")
        episode.update(
            {
                "capture_status": "MISSED",
                "capture_source": None,
                "first_exposure_ts": None,
                "capture_latency_days": None,
                "same_direction_exposure_hours": 0.0,
                "capture_ratio": 0.0,
                "same_direction_trade_ids": [],
                "opposite_direction_exposure_hours": sum(
                    hours for _, hours in opposite
                ),
                "primary_reason": primary_reason,
                "secondary_tags": sorted(set(tags)),
            }
        )

    missing = [
        root["reference_episode_id"]
        for root in roots
        if root["reference_episode_id"] is not None
        and root["reference_episode_id"] not in episode_by_id
    ]
    if missing:
        raise RuntimeError(f"root mapped to unknown reference episodes: {missing}")


def _probe_natural_exit(
    context: Any,
    side: int,
    maturity_index: int,
    entry_index: int,
) -> tuple[int, str]:
    max_exit = min(
        context.book.count,
        entry_index + PROBE_MAX_HOLD_DAYS,
    )
    for signal_index in range(entry_index, context.book.count):
        close = float(context.book.close[signal_index])
        ma7 = float(context.features.ma7[signal_index])
        if not all(math.isfinite(value) for value in (close, ma7)):
            return min(context.book.count, signal_index + 1), "nonfinite"
        if side * (close - ma7) <= 0.0:
            return min(context.book.count, signal_index + 1), "ma7_recross"
        if signal_index + 1 >= max_exit:
            break
    return max_exit, "max_5d"


def build_probe_schedule(
    runtime: Runtime,
    roots: list[dict[str, Any]],
    core: list[dict[str, Any]],
    *,
    lag_days: int = 0,
    excluded_root_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    context = runtime.context
    excluded = excluded_root_ids or set()
    candidates = []
    for root in roots:
        maturity_index = root.get("maturity_index")
        if maturity_index is None:
            continue
        entry_index = int(maturity_index) + 1 + int(lag_days)
        candidates.append(
            (
                entry_index,
                int(root["cross_index"]),
                0 if int(root["side"]) > 0 else 1,
                root,
            )
        )
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    accepted: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    active_probe_exit: pd.Timestamp | None = None
    core_entry_rows = sorted(
        core, key=lambda row: pd.Timestamp(row["entry_ts"])
    )

    for entry_index, _, _, root in candidates:
        root_id = str(root["root_id"])
        side = int(root["side"])
        if root_id in excluded:
            decisions.append(
                {
                    "root_id": root_id,
                    "status": "REJECT",
                    "reason": "LEAVE_ONE_OUT_EXCLUDED",
                }
            )
            continue
        if entry_index >= context.book.count:
            decisions.append(
                {
                    "root_id": root_id,
                    "status": "REJECT",
                    "reason": "TERMINAL",
                }
            )
            continue
        prior_index = entry_index - 1
        prior_close = float(context.book.close[prior_index])
        prior_ma7 = float(context.features.ma7[prior_index])
        if (
            not all(math.isfinite(value) for value in (prior_close, prior_ma7))
            or side * (prior_close - prior_ma7) <= 0.0
        ):
            decisions.append(
                {
                    "root_id": root_id,
                    "status": "REJECT",
                    "reason": "STALE_AFTER_LAG",
                    "entry_index": entry_index,
                }
            )
            continue
        entry_ts = _ts_at(context, entry_index)
        starts = _core_starts(core, entry_ts)
        preopen = _core_at_preopen(core, entry_ts)
        if starts:
            decisions.append(
                {
                    "root_id": root_id,
                    "status": "REJECT",
                    "reason": "CORE_PRECEDENCE",
                    "entry_ts": entry_ts.isoformat(),
                    "core_trade_ids": [row["trade_id"] for row in starts],
                }
            )
            continue
        if preopen:
            decisions.append(
                {
                    "root_id": root_id,
                    "status": "REJECT",
                    "reason": "POSITION_OCCUPIED",
                    "entry_ts": entry_ts.isoformat(),
                    "core_trade_ids": [row["trade_id"] for row in preopen],
                }
            )
            continue
        if active_probe_exit is not None and entry_ts < active_probe_exit:
            decisions.append(
                {
                    "root_id": root_id,
                    "status": "REJECT",
                    "reason": "PROBE_ALREADY_ACTIVE",
                    "entry_ts": entry_ts.isoformat(),
                    "active_probe_exit_ts": active_probe_exit.isoformat(),
                }
            )
            continue
        natural_exit_index, natural_reason = _probe_natural_exit(
            context,
            side,
            int(root["maturity_index"]),
            entry_index,
        )
        natural_exit_ts = _ts_at(context, natural_exit_index)
        next_core = next(
            (
                row
                for row in core_entry_rows
                if entry_ts < pd.Timestamp(row["entry_ts"]) <= natural_exit_ts
            ),
            None,
        )
        if next_core is not None:
            exit_ts = pd.Timestamp(next_core["entry_ts"])
            exit_price = float(next_core["entry_price"])
            exit_reason = "core_preempt"
            preempting_trade_id = next_core["trade_id"]
        else:
            exit_ts = natural_exit_ts
            exit_price = _open_at(context, natural_exit_index)
            exit_reason = natural_reason
            preempting_trade_id = None
        if exit_ts <= entry_ts:
            raise RuntimeError("probe exit is not after entry")
        probe_id = f"PROBE{len(accepted) + 1:03d}"
        trade = {
            "trade_id": probe_id,
            "source": "probe",
            "root_id": root_id,
            "side": side,
            "entry_ts": entry_ts,
            "exit_ts": exit_ts,
            "entry_price": _open_at(context, entry_index),
            "exit_price": exit_price,
            "leverage": PROBE_LEVERAGE,
            "exit_reason": exit_reason,
            "entry_source": "RAW_CROSS_MATURITY",
            "path_action": "isolated_probe",
            "entry_index": entry_index,
            "preempting_core_trade_id": preempting_trade_id,
            "reference_episode_id": root.get("reference_episode_id"),
            "trend_hit_not_used": True,
        }
        accepted.append(trade)
        active_probe_exit = exit_ts
        decisions.append(
            {
                "root_id": root_id,
                "probe_id": probe_id,
                "status": "ACCEPT",
                "reason": "ISOLATED_PROBE",
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": exit_ts.isoformat(),
                "exit_reason": exit_reason,
                "preempting_core_trade_id": preempting_trade_id,
            }
        )
    return accepted, decisions


def compare_metrics(
    candidate: dict[str, Any], control: dict[str, Any]
) -> dict[str, Any]:
    candidate_metrics = candidate["metrics"]
    control_metrics = control["metrics"]
    return_delta = float(candidate_metrics["net_return_pct"]) - float(
        control_metrics["net_return_pct"]
    )
    mdd_delta = float(
        candidate_metrics["chronological_1h_mdd_pct"]
    ) - float(control_metrics["chronological_1h_mdd_pct"])
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "return_higher": return_delta > 1e-12,
        "mdd_smaller": mdd_delta > 1e-12,
        "dual_improvement": return_delta > 1e-12 and mdd_delta > 1e-12,
        "double_worse": return_delta < -1e-12 and mdd_delta < -1e-12,
    }


def run_probe_variant(
    runtime: Runtime,
    roots: list[dict[str, Any]],
    core: list[dict[str, Any]],
    *,
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    lag_days: int = 0,
    excluded_root_ids: set[str] | None = None,
) -> dict[str, Any]:
    probes, decisions = build_probe_schedule(
        runtime,
        roots,
        core,
        lag_days=lag_days,
        excluded_root_ids=excluded_root_ids,
    )
    control = replay_schedule(
        runtime,
        core,
        slippage=slippage,
        include_funding=include_funding,
    )
    combined_schedule = [*core, *probes]
    candidate = replay_schedule(
        runtime,
        combined_schedule,
        slippage=slippage,
        include_funding=include_funding,
    )
    return {
        "settings": {
            "slippage": slippage,
            "include_funding": include_funding,
            "probe_signal_lag_days": lag_days,
            "probe_leverage": PROBE_LEVERAGE,
            "excluded_root_ids": sorted(excluded_root_ids or set()),
        },
        "control": {
            "metrics": control["metrics"],
            "recent_slices": control["recent_slices"],
            "schedule_sha256": control["schedule_sha256"],
        },
        "candidate": {
            "metrics": candidate["metrics"],
            "recent_slices": candidate["recent_slices"],
            "schedule_sha256": candidate["schedule_sha256"],
        },
        "comparison": compare_metrics(candidate, control),
        "probe_decisions": decisions,
        "probe_trades": [
            row for row in candidate["trades"] if row["source"] == "probe"
        ],
        "accepted_probe_count": len(probes),
        "_control_full": control,
        "_candidate_full": candidate,
    }


def _strip_private(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_private(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_strip_private(item) for item in value]
    return value


def probe_attribution_summary(
    probe_trades: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
) -> dict[str, Any]:
    missed_ids = {
        str(row["episode_id"])
        for row in episodes
        if row["capture_status"] == "MISSED"
    }
    captured_ids = {
        str(row["episode_id"])
        for row in episodes
        if row["capture_status"] == "CAPTURED"
    }

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "trades": len(rows),
            "wins": sum(float(row["net_pnl"]) > 0.0 for row in rows),
            "win_rate": (
                sum(float(row["net_pnl"]) > 0.0 for row in rows) / len(rows)
                if rows
                else None
            ),
            "net_pnl_equity_units": sum(
                float(row["net_pnl"]) for row in rows
            ),
            "mean_trade_return_pct": (
                sum(float(row["net_return"]) * 100.0 for row in rows)
                / len(rows)
                if rows
                else None
            ),
        }

    return {
        "all": summarize(probe_trades),
        "long": summarize(
            [row for row in probe_trades if int(row["side"]) > 0]
        ),
        "short": summarize(
            [row for row in probe_trades if int(row["side"]) < 0]
        ),
        "mapped_to_missed_reference_episode": summarize(
            [
                row
                for row in probe_trades
                if row.get("reference_episode_id") in missed_ids
            ]
        ),
        "mapped_to_captured_reference_episode": summarize(
            [
                row
                for row in probe_trades
                if row.get("reference_episode_id") in captured_ids
            ]
        ),
        "not_mapped_to_reference_episode": summarize(
            [
                row
                for row in probe_trades
                if row.get("reference_episode_id") is None
            ]
        ),
        "interpretation_constraint": (
            "reference mapping is hindsight-only attribution and was not used "
            "to select probe entries"
        ),
    }


def _conclusion(
    invariants: dict[str, bool],
    episodes: list[dict[str, Any]],
    base: dict[str, Any],
    stress: dict[str, Any],
    funding_off: dict[str, Any],
    lag: dict[str, Any],
    leave_one_out: dict[str, Any],
) -> str:
    if not all(invariants.values()):
        return "AUDIT_INVALID"
    causal_misses = [
        row
        for row in episodes
        if row["capture_status"] == "MISSED" and row["root_ids"]
    ]
    if not causal_misses:
        return "HINDSIGHT_ONLY_MISSES"
    probe_trades = list(base["probe_trades"])
    block_count = int(base.get("accepted_probe_block_count", 0))
    if len(probe_trades) < 4 or block_count < 4:
        return "INSUFFICIENT_INDEPENDENT_EPISODES"
    if not base["comparison"]["return_higher"]:
        return "NON_ECONOMIC_MISSES"
    if not base["comparison"]["mdd_smaller"]:
        return "NO_DUAL_IMPROVEMENT"
    if (
        stress["comparison"]["double_worse"]
        or funding_off["comparison"]["double_worse"]
        or lag["comparison"]["double_worse"]
        or not leave_one_out["comparison"]["return_higher"]
    ):
        return "FRAGILE_EXPOSED_INCREMENT"
    return "EXPOSED_CAUSAL_LEAK_SUPPORTED"


def build_payload() -> dict[str, Any]:
    runtime = load_runtime()
    context = runtime.context
    transition = runtime.transition
    exact = transition.run_v6(
        context,
        start_index=0,
        terminal_index=context.book.count,
        retain=True,
    )
    exact_wrapper = transition.run_variant(
        context,
        transition.TransitionRepairConfig("ATTRIBUTION_EXACT"),
        start_index=0,
        terminal_index=context.book.count,
        retain=True,
    )
    exact_risk = runtime.risk.replay_chronological_1h(
        context,
        exact.raw,
        retain_points=False,
    )
    core = build_core_schedule(context, exact.raw)
    core_replay = replay_schedule(runtime, core)
    daily = context.market.daily
    raw_labels = runtime.labels.hindsight_labels(
        daily.loc[:, ["close", "ma7", "atr7"]]
    )
    raw_direction = runtime.r3.direction_target(raw_labels)
    stable = runtime.r4.stable_direction_target(raw_direction)
    episodes = extract_reference_episodes(stable, daily, raw_labels)
    roots = build_roots(
        runtime,
        core,
        list(exact_wrapper.cooldown_events),
    )
    associate_and_classify_episodes(episodes, roots, core)

    base = run_probe_variant(runtime, roots, core)
    stress = run_probe_variant(
        runtime,
        roots,
        core,
        slippage=STRESS_SLIPPAGE,
    )
    funding_off = run_probe_variant(
        runtime,
        roots,
        core,
        include_funding=False,
    )
    lag = run_probe_variant(
        runtime,
        roots,
        core,
        lag_days=1,
    )

    root_by_id = {row["root_id"]: row for row in roots}
    for variant in (base, stress, funding_off, lag):
        blocks = {
            int(root_by_id[trade["root_id"]]["cross_index"]) // 54
            for trade in variant["probe_trades"]
        }
        variant["accepted_probe_blocks"] = sorted(blocks)
        variant["accepted_probe_block_count"] = len(blocks)

    positive_probes = [
        row for row in base["probe_trades"] if float(row["net_pnl"]) > 0.0
    ]
    largest_probe = (
        max(positive_probes, key=lambda row: float(row["net_pnl"]))
        if positive_probes
        else None
    )
    excluded = (
        {str(largest_probe["root_id"])}
        if largest_probe is not None
        else set()
    )
    leave_one_out = run_probe_variant(
        runtime,
        roots,
        core,
        excluded_root_ids=excluded,
    )
    leave_one_out["removed_probe"] = (
        {
            "trade_id": largest_probe["trade_id"],
            "root_id": largest_probe["root_id"],
            "net_pnl": largest_probe["net_pnl"],
        }
        if largest_probe is not None
        else None
    )
    leave_blocks = {
        int(root_by_id[trade["root_id"]]["cross_index"]) // 54
        for trade in leave_one_out["probe_trades"]
    }
    leave_one_out["accepted_probe_blocks"] = sorted(leave_blocks)
    leave_one_out["accepted_probe_block_count"] = len(leave_blocks)

    engine_invariant_roots = [
        row["root_id"]
        for row in roots
        if row["execution_blocker"] == "ENGINE_INVARIANT_FAIL"
    ]
    replay_terminal_parity = math.isclose(
        float(core_replay["metrics"]["equity_multiple"]),
        float(exact_risk.terminal_equity),
        rel_tol=2e-10,
        abs_tol=2e-10,
    )
    replay_mdd_parity = math.isclose(
        float(core_replay["metrics"]["chronological_1h_mdd_pct"]),
        float(exact_risk.chronological_1h_mdd_pct),
        rel_tol=2e-10,
        abs_tol=2e-10,
    )
    exact_anchor = (
        math.isclose(
            float(exact.raw.metrics["net_return_pct"]),
            EXPECTED_V6_RETURN,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        and int(exact.raw.metrics["closed_trades"]) == EXPECTED_V6_TRADES
        and transition.V6_CONFIG_SHA256 == EXPECTED_V6_CONFIG_SHA256
    )
    wrapper_parity = (
        exact.raw.metrics == exact_wrapper.raw.metrics
        and exact.raw.trades == exact_wrapper.raw.trades
        and exact.raw.path == exact_wrapper.raw.path
    )
    combined_no_overlap = True
    combined_rows = sorted(
        [*core, *build_probe_schedule(runtime, roots, core)[0]],
        key=lambda row: pd.Timestamp(row["entry_ts"]),
    )
    for previous, following in zip(combined_rows, combined_rows[1:]):
        if pd.Timestamp(following["entry_ts"]) < pd.Timestamp(
            previous["exit_ts"]
        ):
            combined_no_overlap = False
            break
    invariants = {
        "exact_v6_anchor": bool(exact_anchor),
        "exact_wrapper_parity": bool(wrapper_parity),
        "exact_risk_replay_parity": bool(all(exact_risk.parity.values())),
        "custom_replay_terminal_parity": bool(replay_terminal_parity),
        "custom_replay_mdd_parity": bool(replay_mdd_parity),
        "engine_invariant_failures_zero": not engine_invariant_roots,
        "combined_schedule_nonoverlap": combined_no_overlap,
        "reference_labels_not_used_for_probe": all(
            bool(row.get("trend_hit_not_used"))
            for row in base["probe_trades"]
        ),
        "terminal_equity_positive": float(
            base["candidate"]["metrics"]["equity_multiple"]
        )
        > 0.0,
    }
    conclusion = _conclusion(
        invariants,
        episodes,
        base,
        stress,
        funding_off,
        lag,
        leave_one_out,
    )

    episode_summary = {
        "total": len(episodes),
        "long": sum(int(row["side"]) > 0 for row in episodes),
        "short": sum(int(row["side"]) < 0 for row in episodes),
        "captured": sum(row["capture_status"] == "CAPTURED" for row in episodes),
        "missed": sum(row["capture_status"] == "MISSED" for row in episodes),
        "missed_hindsight_only": sum(
            row["primary_reason"] == "MISSED_HINDSIGHT_ONLY"
            for row in episodes
        ),
        "missed_with_causal_root": sum(
            row["capture_status"] == "MISSED" and bool(row["root_ids"])
            for row in episodes
        ),
        "primary_reason_counts": dict(
            sorted(Counter(row["primary_reason"] for row in episodes).items())
        ),
        "any_capture_rate": (
            sum(row["capture_status"] == "CAPTURED" for row in episodes)
            / len(episodes)
            if episodes
            else None
        ),
        "weighted_same_direction_exposure_ratio": (
            sum(float(row["same_direction_exposure_hours"]) for row in episodes)
            / sum(float(row["duration_days"]) * 24.0 for row in episodes)
            if episodes
            else None
        ),
    }
    root_summary = {
        "total": len(roots),
        "long": sum(int(row["side"]) > 0 for row in roots),
        "short": sum(int(row["side"]) < 0 for row in roots),
        "same_day_pass": sum(row["cross_gate"] == "PASS" for row in roots),
        "later_maturity": sum(bool(row["later_maturity"]) for row in roots),
        "never_matured": sum(row["maturity_index"] is None for row in roots),
        "trend_hit_evaluable": sum(
            bool((row["maturity_forward_label"] or {}).get("evaluable"))
            for row in roots
        ),
        "trend_hits": sum(
            bool((row["maturity_forward_label"] or {}).get("trend_hit"))
            for row in roots
        ),
        "cross_gate_counts": dict(
            sorted(Counter(row["cross_gate"] for row in roots).items())
        ),
        "execution_blocker_counts": dict(
            sorted(
                Counter(
                    str(row["execution_blocker"])
                    for row in roots
                ).items()
            )
        ),
    }
    payload = {
        "schema_version": "hype-1d-ma7-v6-missed-trend-attribution-v1",
        "contract_id": "HYPE-1D-MA7-ABT-V6-MISSED-TREND-ATTRIBUTION-2026-08-10",
        "research_role": "post-reveal diagnostic-only",
        "outcome_visibility": "all 432 days researcher-exposed",
        "status": conclusion,
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "control_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V6",
        "market": {
            "exchange": "binance",
            "market_type": "perp",
            "symbol": "HYPEUSDT",
            "timeframe": "1d from trusted 1h",
            "start_ts": pd.Timestamp(context.book.ts[0]).isoformat(),
            "end_ts": pd.Timestamp(context.book.ts[-1]).isoformat(),
            "terminal_ts": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "daily_rows": context.book.count,
            "audit": sanitize(context.market.audit),
            "adapter_pins": dict(context.pins),
        },
        "cost_model": {
            "fee_per_fill": float(context.engine.FEE),
            "base_adverse_slippage_per_fill": BASE_SLIPPAGE,
            "stress_adverse_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual event timestamp/rate/price",
        },
        "execution_model": {
            "closed_bar_only": True,
            "entry": "next UTC open",
            "probe_leverage": PROBE_LEVERAGE,
            "probe_max_hold_days": PROBE_MAX_HOLD_DAYS,
            "core_priority": True,
            "probe_state_isolated": True,
        },
        "frozen_thresholds": {
            "reference_label": {
                "center_window_days": 7,
                "abs_beta7_atr_min": 0.08,
                "r_squared_min": 0.35,
                "viterbi_transition_cost": 2.0,
                "minimum_direction_run_days": 3,
                "hindsight_audit_only": True,
            },
            "root": {
                "max_age_days": ROOT_MAX_AGE_DAYS,
                "long_distance_atr_strict_gt": 0.0,
                "long_slope_lookback_days": 1,
                "long_slope_atr_gte": 0.02,
                "short_distance_atr_strict_gt": 0.10,
                "short_slope_lookback_days": 2,
                "short_slope_atr_gte": 0.02,
            },
            "forward_label": {
                "days": FORWARD_DAYS,
                "direction_return_strict_gt": ROUNDTRIP_GUARD,
                "same_side_closes_min": 3,
            },
        },
        "implementation_sha256": implementation_pins(),
        "v6_anchor": {
            "metrics": {
                **{
                    key: sanitize(value)
                    for key, value in exact.raw.metrics.items()
                    if key
                    in {
                        "equity_multiple",
                        "net_return_pct",
                        "closed_trades",
                        "long_trades",
                        "short_trades",
                        "win_rate",
                        "profit_factor",
                        "turnover_multiple",
                        "cost_pct_initial",
                        "funding_pct_initial",
                    }
                },
                "chronological_1h_mdd_pct": exact_risk.chronological_1h_mdd_pct,
                "worst_ts": exact_risk.worst_ts,
            },
            "pehc_config_sha256": transition.V6_CONFIG_SHA256,
            "source_sha256": exact.source_sha256,
            "trades_sha256": canonical_hash(
                _economic_trade_identity(exact.raw.trades)
            ),
            "wrapper_source_sha256": exact_wrapper.source_sha256,
        },
        "episode_summary": episode_summary,
        "root_summary": root_summary,
        "reference_episodes": episodes,
        "root_opportunities": roots,
        "probe_results": {
            "base": _strip_private(base),
            "stress_8bps": _strip_private(stress),
            "funding_off": _strip_private(funding_off),
            "probe_lag_1d": _strip_private(lag),
            "leave_largest_positive_probe_out": _strip_private(
                leave_one_out
            ),
        },
        "probe_attribution_summary": probe_attribution_summary(
            base["probe_trades"], episodes
        ),
        "invariants": invariants,
        "invariant_failures": [
            key for key, value in invariants.items() if not value
        ],
        "engine_invariant_root_ids": engine_invariant_roots,
        "final_conclusion_code": conclusion,
        "governance": {
            "modifies_v6": False,
            "registers_v7": False,
            "promotion_evidence": False,
            "runner_handoff": False,
            "leverage_unlock": False,
            "next_step_requires_clean_prospective": True,
        },
    }
    return sanitize(payload)


def write_locked(path: Path, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        sanitize(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).encode()
    try:
        with path.open("xb") as handle:
            handle.write(encoded + b"\n")
    except FileExistsError as exc:
        raise RuntimeError(f"locked artifact already exists: {path}") from exc
    digest = sha256(path)
    try:
        with OUTPUT_SHA_PATH.open("x", encoding="utf-8") as handle:
            handle.write(f"{digest}  {path.name}\n")
    except FileExistsError as exc:
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"locked checksum already exists: {OUTPUT_SHA_PATH}"
        ) from exc
    return digest


def main() -> None:
    args = parse_args()
    preflight = (
        {"status": "SKIPPED"}
        if args.skip_preflight
        else run_preflight()
    )
    payload = build_payload()
    payload["preflight"] = preflight
    summary = {
        "status": payload["status"],
        "episodes": payload["episode_summary"],
        "roots": payload["root_summary"],
        "base_probe": payload["probe_results"]["base"]["comparison"],
        "base_probe_trades": payload["probe_results"]["base"][
            "accepted_probe_count"
        ],
        "base_probe_blocks": payload["probe_results"]["base"][
            "accepted_probe_block_count"
        ],
        "invariant_failures": payload["invariant_failures"],
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    digest = write_locked(OUTPUT_PATH, payload)
    summary["output"] = str(OUTPUT_PATH.relative_to(ROOT))
    summary["sha256"] = digest
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
