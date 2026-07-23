from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import mmtf_engine as engine
import mmtf_v2


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1h-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TUNE_PATH = ARTIFACT_DIR / "hype_1h_mmtf_v2_clean_tune_2026-07-22.json"
ROBUSTNESS_PATH = ARTIFACT_DIR / "hype_1h_mmtf_v3_prefit_robustness_2026-07-22.json"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1h_mmtf_v3_locked_oos_reveal_2026-07-22.json"

RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=180),
    "1y": pd.Timedelta(days=365),
}


def _current_hashes() -> dict[str, str]:
    scripts = Path(__file__).parent
    return {
        "engine": hashlib.sha256((scripts / "mmtf_engine.py").read_bytes()).hexdigest(),
        "clean_adapter": hashlib.sha256((scripts / "mmtf_v2.py").read_bytes()).hexdigest(),
        "tune_script": hashlib.sha256(
            (scripts / "research_hype_1h_mmtf_v2_clean_tune.py").read_bytes()
        ).hexdigest(),
    }


def _target_pass(metrics: dict[str, Any], *, minimum_trades: int) -> bool:
    return bool(
        metrics["annual_factor"] >= 20.0
        and metrics["win_rate"] >= 0.80
        and metrics["max_drawdown"] < 0.20
        and metrics["trades"] >= minimum_trades
        and not metrics["liquidated"]
    )


def _trade_bootstrap(trades: list[dict[str, Any]], *, seed: int = 2026072204) -> dict[str, Any]:
    returns = np.asarray([trade["net_return"] for trade in trades], dtype="float64")
    if not len(returns):
        return {"draws": 0, "reason": "no trades"}
    rng = np.random.default_rng(seed)
    endings: list[float] = []
    drawdowns: list[float] = []
    for _ in range(20_000):
        sample = rng.choice(returns, size=len(returns), replace=True)
        equity = np.r_[1.0, np.cumprod(1.0 + sample)]
        peak = np.maximum.accumulate(equity)
        endings.append(float(equity[-1]))
        drawdowns.append(float((1.0 - equity / peak).max()))
    return {
        "draws": 20_000,
        "ending_equity_p05_p50_p95": [
            float(np.quantile(endings, quantile)) for quantile in (0.05, 0.50, 0.95)
        ],
        "max_drawdown_p05_p50_p95": [
            float(np.quantile(drawdowns, quantile)) for quantile in (0.05, 0.50, 0.95)
        ],
        "probability_max_drawdown_lt_20pct": float(
            (np.asarray(drawdowns) < 0.20).mean()
        ),
    }


def main() -> None:
    if OUTPUT_PATH.exists():
        raise RuntimeError(
            f"locked OOS was already revealed at {OUTPUT_PATH}; one-time contract forbids rerun"
        )
    tune = json.loads(TUNE_PATH.read_text(encoding="utf-8"))
    robustness = json.loads(ROBUSTNESS_PATH.read_text(encoding="utf-8"))
    current_hashes = _current_hashes()
    if current_hashes != tune["code_hashes"]:
        raise RuntimeError("frozen code changed after V3 selection")
    if robustness["locked_oos_accessed"] or not robustness["freeze_verified"]:
        raise RuntimeError("prefit robustness evidence violates reveal preconditions")

    clean = mmtf_v2.clean_from_dict(tune["v3_tuned_freeze"]["config"])
    config = mmtf_v2.to_engine_config(clean)
    manifest = engine.load_manifest()
    oos_start = pd.Timestamp(manifest["freeze_contract"]["locked_oos_start_inclusive"])
    terminal = pd.Timestamp(manifest["freeze_contract"]["locked_oos_end_exclusive"])
    book = engine.build_book(include_locked_oos=True)

    prefit = engine.run_backtest(book, config, end_ts=oos_start, detailed=True)
    locked_oos = engine.run_backtest(
        book, config, start_ts=oos_start, end_ts=terminal, detailed=True
    )
    full = engine.run_backtest(book, config, end_ts=terminal, detailed=True)

    stress: dict[str, Any] = {}
    for name, delay, slippage in (
        ("base_k1_4bps", 1, engine.BASE_SLIPPAGE),
        ("delay_k2_4bps", 2, engine.BASE_SLIPPAGE),
        ("base_k1_8bps", 1, engine.STRESS_SLIPPAGE),
        ("delay_k2_8bps", 2, engine.STRESS_SLIPPAGE),
    ):
        stress[name] = {
            "locked_oos": engine.run_backtest(
                book,
                config,
                start_ts=oos_start,
                end_ts=terminal,
                entry_delay_bars=delay,
                slippage_per_fill=slippage,
            ).metrics,
            "full": engine.run_backtest(
                book,
                config,
                end_ts=terminal,
                entry_delay_bars=delay,
                slippage_per_fill=slippage,
            ).metrics,
        }

    slices: dict[str, Any] = {}
    for name, duration in RECENT_WINDOWS.items():
        start = max(book.source_start, terminal - duration)
        slices[name] = engine.run_backtest(
            book, config, start_ts=start, end_ts=terminal
        ).metrics

    stress_drawdown_pass = all(
        payload["full"]["max_drawdown"] < 0.20
        and payload["locked_oos"]["max_drawdown"] < 0.20
        and not payload["full"]["liquidated"]
        and not payload["locked_oos"]["liquidated"]
        for payload in stress.values()
    )
    full_pass = _target_pass(full.metrics, minimum_trades=60)
    oos_pass = _target_pass(locked_oos.metrics, minimum_trades=15)
    phase_pass = bool(robustness["phase_audit"]["default_phase_gate_pass"])
    overall = bool(full_pass and oos_pass and stress_drawdown_pass and phase_pass)

    summary = {
        "family": "HYPE-1H-Multi-Mechanism-Trend-Following",
        "version": "HYPE-1H-Multi-Mechanism-Trend-Following-V3",
        "revealed_at_utc": datetime.now(UTC).isoformat(),
        "one_time_reveal": True,
        "no_post_reveal_tuning_authorized": True,
        "freeze_verified": {
            "config": asdict(clean),
            "clean_config_sha256": mmtf_v2.clean_sha256(clean),
            "engine_config_sha256": engine.config_sha256(config),
            "code_hashes": current_hashes,
        },
        "windows": {
            "prefit_end_exclusive": oos_start.isoformat(),
            "locked_oos_start_inclusive": oos_start.isoformat(),
            "locked_oos_end_exclusive": terminal.isoformat(),
        },
        "metrics": {
            "prefit": prefit.metrics,
            "locked_oos_flat_reset": locked_oos.metrics,
            "full": full.metrics,
        },
        "recent_slices": slices,
        "stress": stress,
        "monte_carlo_full_trade_bootstrap": _trade_bootstrap(full.trades),
        "gates": {
            "full_hard_target_pass": full_pass,
            "locked_oos_hard_target_pass": oos_pass,
            "stress_drawdown_pass": stress_drawdown_pass,
            "phase_gate_pass": phase_pass,
            "overall_hard_target_pass": overall,
        },
        "decision": (
            "PASS_FOR_PROMOTION_REVIEW" if overall else "NO-GO / not promoted / not live-ready"
        ),
    }
    pd.DataFrame(locked_oos.trades).to_csv(
        ARTIFACT_DIR / "hype_1h_mmtf_v3_locked_oos_trades_2026-07-22.csv",
        index=False,
    )
    pd.DataFrame(full.trades).to_csv(
        ARTIFACT_DIR / "hype_1h_mmtf_v3_full_trades_2026-07-22.csv",
        index=False,
    )
    pd.DataFrame(full.equity_path).to_csv(
        ARTIFACT_DIR / "hype_1h_mmtf_v3_full_equity_2026-07-22.csv",
        index=False,
    )
    OUTPUT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
