from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P4_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py"
STEM = "hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27"
TEACHER_TRADES = ARTIFACT_DIR / f"{STEM}_validation_teacher_trades.csv"
OVERLAY_TRADES = ARTIFACT_DIR / f"{STEM}_validation_overlay_trades.csv"
VALIDATION_SUMMARY = ARTIFACT_DIR / f"{STEM}_validation_summary.json"
OUTPUT = ARTIFACT_DIR / f"{STEM}_recent_slices.json"
SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sidecar(path: Path) -> None:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    expected = sidecar.read_text(encoding="utf-8").split()[0]
    if sha256(path) != expected:
        raise RuntimeError(f"artifact hash mismatch: {path}")


def load_trades(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path)
    return frame.to_dict("records")


def equity_observations(
    p4: Any, v6: Any, context: Any, trades: list[dict[str, Any]]
) -> tuple[list[tuple[pd.Timestamp, float]], dict[pd.Timestamp, float], float]:
    cost_rate = float(context.engine.FEE) + p4.SLIPPAGE
    marks: list[tuple[pd.Timestamp, str, Any]] = []
    for index, day in enumerate(context.book.ts):
        day_ts = pd.Timestamp(day)
        for hour in range(24):
            marks.append(
                (
                    day_ts + pd.Timedelta(hours=hour),
                    "mark",
                    float(context.features.hourly_open[index, hour]),
                )
            )
    terminal = pd.Timestamp(context.book.terminal_ts)
    marks.append((terminal, "mark", float(context.book.quality["terminal_open"])))
    for daily in context.features.funding_events:
        for event in daily:
            marks.append((pd.Timestamp(event.ts), "funding", event))
    for trade in trades:
        marks.append((pd.Timestamp(trade["entry_ts"]), "entry", trade))
        marks.append((pd.Timestamp(trade["exit_ts"]), "exit", trade))
    order = {"mark": 0, "funding": 1, "exit": 2, "entry": 3}
    marks.sort(key=lambda row: (row[0], order[row[1]]))

    equity = 1.0
    qty = 0.0
    mark_price: float | None = None
    observations: list[tuple[pd.Timestamp, float]] = []
    mark_equity: dict[pd.Timestamp, float] = {}
    for ts, kind, payload in marks:
        if kind == "mark":
            price = float(payload)
            if qty and mark_price is not None:
                equity += qty * (price - mark_price)
            if math.isfinite(price) and price > 0.0:
                mark_price = price
            mark_equity[ts] = equity
        elif kind == "funding" and qty:
            equity -= qty * float(payload.price) * float(payload.rate)
        elif kind == "entry":
            if qty:
                raise RuntimeError("overlapping entry in frozen trades")
            price = float(payload["entry_price"])
            side = 1 if str(payload["side"]) == "long" else -1
            leverage = float(payload.get("entry_leverage", 1.0))
            qty, equity, _ = v6.target_quantity(
                equity, qty, side, price, cost_rate, leverage
            )
            mark_price = price
        elif kind == "exit":
            price = float(payload["exit_price"])
            if qty and mark_price is not None:
                equity += qty * (price - mark_price)
            mark_price = price
            qty, equity, _ = v6.target_quantity(equity, qty, 0, price, cost_rate, 1.0)
            qty = 0.0
        observations.append((ts, equity))
    return observations, mark_equity, equity


def slice_metrics(
    observations: list[tuple[pd.Timestamp, float]],
    mark_equity: dict[pd.Timestamp, float],
    terminal: pd.Timestamp,
    days: int,
) -> dict[str, Any]:
    requested = terminal - pd.Timedelta(days=days)
    eligible_marks = [ts for ts in mark_equity if ts <= requested]
    if not eligible_marks:
        raise RuntimeError(f"no mark at or before {requested}")
    start_ts = max(eligible_marks)
    start_equity = float(mark_equity[start_ts])
    path = [(ts, value) for ts, value in observations if ts >= start_ts]
    peak = start_equity
    mdd = 0.0
    for _, value in path:
        peak = max(peak, float(value))
        mdd = min(mdd, float(value) / peak - 1.0)
    end_equity = float(path[-1][1])
    return {
        "requested_days": days,
        "start_ts": start_ts.isoformat(),
        "terminal_ts": terminal.isoformat(),
        "start_equity": start_equity,
        "terminal_equity": end_equity,
        "net_return_pct": (end_equity / start_equity - 1.0) * 100.0,
        "mdd_pct": mdd * 100.0,
    }


def main() -> None:
    for path in (TEACHER_TRADES, OVERLAY_TRADES, VALIDATION_SUMMARY):
        verify_sidecar(path)
    p4 = load_module(P4_SCRIPT, "hype_p4_recent_slices_main")
    _, v6, _, _, context = p4.load_dependencies()
    terminal = pd.Timestamp(context.book.terminal_ts)
    validation = json.loads(VALIDATION_SUMMARY.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "family": p4.FAMILY,
        "experiment": p4.EXPERIMENT,
        "audit": "frozen_validation_recent_slices",
        "terminal_ts": terminal.isoformat(),
        "source_artifacts": {
            "teacher_trades": sha256(TEACHER_TRADES),
            "overlay_trades": sha256(OVERLAY_TRADES),
            "validation_summary": sha256(VALIDATION_SUMMARY),
        },
        "arms": {},
    }
    for name, path, expected in (
        ("teacher_v7_1", TEACHER_TRADES, validation["teacher_v7_1"]["terminal_equity"]),
        (
            "ml_residual_overlay",
            OVERLAY_TRADES,
            validation["ml_residual_overlay"]["terminal_equity"],
        ),
    ):
        observations, mark_equity, terminal_equity = equity_observations(
            p4, v6, context, load_trades(path)
        )
        if not math.isclose(terminal_equity, float(expected), rel_tol=0.0, abs_tol=1e-12):
            raise RuntimeError(f"{name} terminal parity failed")
        payload["arms"][name] = {
            label: slice_metrics(observations, mark_equity, terminal, days)
            for label, days in SLICES.items()
        }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    OUTPUT.with_suffix(OUTPUT.suffix + ".sha256").write_text(
        f"{sha256(OUTPUT)}  {OUTPUT.name}\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
