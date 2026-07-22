from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "btc_15m_lvcb_summary_2026-07-20.json"
TRADES_PATH = ARTIFACT_DIR / "btc_15m_lvcb_selected_trades_2026-07-20.csv"
OUTPUT_PATH = ARTIFACT_DIR / "btc_15m_lvcb_candidate_audit_2026-07-20.json"
SEED = 20260720
SIMULATIONS = 10_000
BLOCK_LENGTH = 5


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return "inf" if number > 0 else "-inf"
    return value


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    complete = finite(payload)
    complete["payload_sha256"] = payload_sha256(complete)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumprod(1.0 + returns)
    values = np.concatenate(([1.0], equity))
    return float((values / np.maximum.accumulate(values) - 1.0).min())


def stationary_block_bootstrap(returns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED)
    count = len(returns)
    terminals = np.empty(SIMULATIONS, dtype=float)
    drawdowns = np.empty(SIMULATIONS, dtype=float)
    block_count = math.ceil(count / BLOCK_LENGTH)
    offsets = np.arange(BLOCK_LENGTH)
    for simulation in range(SIMULATIONS):
        starts = rng.integers(0, count, size=block_count)
        locations = ((starts[:, None] + offsets) % count).ravel()[:count]
        sample = returns[locations]
        terminals[simulation] = float(np.prod(1.0 + sample) - 1.0)
        drawdowns[simulation] = max_drawdown(sample)
    return terminals, drawdowns


def quantiles(values: np.ndarray) -> dict[str, float]:
    return {
        "p01": float(np.quantile(values, 0.01)),
        "p05": float(np.quantile(values, 0.05)),
        "p50": float(np.quantile(values, 0.50)),
        "p95": float(np.quantile(values, 0.95)),
        "p99": float(np.quantile(values, 0.99)),
    }


def longest_loss_streak(values: np.ndarray) -> int:
    longest = 0
    current = 0
    for value in values:
        if value <= 0.0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def current_loss_streak(values: np.ndarray) -> int:
    streak = 0
    for value in values[::-1]:
        if value > 0.0:
            break
        streak += 1
    return streak


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    trades = pd.read_csv(TRADES_PATH)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    if trades.empty:
        raise RuntimeError("selected candidate has no trades")
    returns = pd.to_numeric(trades["trade_return"], errors="raise").to_numpy(float)
    if np.any(returns <= -1.0):
        raise RuntimeError("candidate trade return would bankrupt equity")
    terminals, drawdowns = stationary_block_bootstrap(returns)
    positive = returns[returns > 0.0]
    total_positive = float(positive.sum())
    audit_pass = bool(
        float((terminals > 0.0).mean()) >= 0.90
        and float((drawdowns <= -0.25).mean()) <= 0.25
        and summary["universe"]["full_history_robust_count"] >= 10
    )
    script_path = Path(__file__).resolve()
    output = {
        "family": "BTC-15M-Trend-Continuation",
        "strategy_id": summary["selected"]["strategy_id"],
        "status": (
            "bootstrap pass / prospective OOS still required"
            if audit_pass
            else "bootstrap fail / not a research candidate"
        ),
        "inputs": {
            "summary_path": str(SUMMARY_PATH.relative_to(ROOT)),
            "summary_sha256": sha256_bytes(SUMMARY_PATH.read_bytes()),
            "trades_path": str(TRADES_PATH.relative_to(ROOT)),
            "trades_sha256": sha256_bytes(TRADES_PATH.read_bytes()),
            "trade_count": len(trades),
            "first_entry": trades["entry_ts"].iloc[0].isoformat(),
            "last_entry": trades["entry_ts"].iloc[-1].isoformat(),
        },
        "observed": {
            "compounded_return_pct": float((np.prod(1.0 + returns) - 1.0) * 100.0),
            "trade_sequence_max_drawdown_pct": max_drawdown(returns) * 100.0,
            "win_rate": float((returns > 0.0).mean()),
            "longest_nonpositive_streak": longest_loss_streak(returns),
            "current_nonpositive_streak": current_loss_streak(returns),
            "top_trade_positive_pnl_share": float(
                1.0 if total_positive <= 0.0 else positive.max() / total_positive
            ),
            "top3_trade_positive_pnl_share": float(
                1.0
                if total_positive <= 0.0
                else np.sort(positive)[-3:].sum() / total_positive
            ),
        },
        "block_bootstrap": {
            "seed": SEED,
            "simulations": SIMULATIONS,
            "block_length_trades": BLOCK_LENGTH,
            "terminal_return": quantiles(terminals),
            "max_drawdown": quantiles(drawdowns),
            "probability_positive_terminal": float((terminals > 0.0).mean()),
            "probability_drawdown_below_minus_25pct": float(
                (drawdowns <= -0.25).mean()
            ),
            "limitations": (
                "resamples trade returns rather than bar paths; it preserves local "
                "trade clustering only through fixed five-trade circular blocks and "
                "does not model changing trade frequency"
            ),
        },
        "audit_pass": audit_pass,
        "remaining_blockers": [
            blocker
            for blocker in summary["remaining_blockers"]
            if "CPCV" not in blocker
        ]
        + ["CPCV and live-executable runner audit not completed"],
        "provenance": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "code_path": str(script_path.relative_to(ROOT)),
            "code_sha256": sha256_bytes(script_path.read_bytes()),
        },
    }
    atomic_write_json(OUTPUT_PATH, output)
    print(json.dumps(finite(output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
