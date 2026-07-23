from __future__ import annotations

from dataclasses import asdict, replace
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
FAMILY_DIR = ROOT / "research/hype/15m-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TUNE_PATH = ARTIFACT_DIR / "hype_15m_mmtf_v2_clean_tune_2026-07-22.json"
ROBUSTNESS_PATH = ARTIFACT_DIR / "hype_15m_mmtf_v3_prefit_robustness_2026-07-22.json"
OUTPUT_PATH = ARTIFACT_DIR / "hype_15m_mmtf_v3_locked_oos_reveal_2026-07-22.json"

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
            (scripts / "research_hype_15m_mmtf_v2_clean_tune.py").read_bytes()
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


def _extended(result: engine.BacktestResult) -> dict[str, Any]:
    metrics = dict(result.metrics)
    returns = np.asarray([trade["net_return"] for trade in result.trades], dtype="float64")
    wins = returns[returns > 0.0]
    losses = returns[returns <= 0.0]
    payoff = (
        float(wins.mean() / abs(losses.mean()))
        if len(wins) and len(losses) and losses.mean() < 0.0
        else (float("inf") if len(wins) else 0.0)
    )
    trades_per_year = (
        len(returns) * engine.HOURS_PER_YEAR / metrics["hours"]
        if metrics["hours"] > 0.0
        else 0.0
    )
    sharpe = (
        float(returns.mean() / returns.std(ddof=1) * np.sqrt(trades_per_year))
        if len(returns) > 1 and returns.std(ddof=1) > 0.0
        else 0.0
    )
    max_loss_streak = 0
    current_streak = 0
    for value in returns:
        current_streak = current_streak + 1 if value <= 0.0 else 0
        max_loss_streak = max(max_loss_streak, current_streak)
    metrics.update(
        {
            "cagr": metrics["annual_factor"] - 1.0,
            "trade_sharpe_annualized": sharpe,
            "average_win_loss_payoff": payoff,
            "max_single_trade_loss": float(losses.min()) if len(losses) else 0.0,
            "max_consecutive_losses": int(max_loss_streak),
            "actual_leverage": float(
                max((trade["leverage"] for trade in result.trades), default=0.0)
            ),
        }
    )
    return metrics


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
        slices[name] = _extended(
            engine.run_backtest(book, config, start_ts=start, end_ts=terminal)
        )

    leverage_ladder: dict[str, Any] = {}
    for leverage in (1.0, 2.0, 3.0):
        ladder_config = mmtf_v2.to_engine_config(replace(clean, leverage=leverage))
        leverage_ladder[f"{leverage:g}x"] = {
            "locked_oos": _extended(
                engine.run_backtest(
                    book, ladder_config, start_ts=oos_start, end_ts=terminal
                )
            ),
            "full": _extended(engine.run_backtest(book, ladder_config, end_ts=terminal)),
        }

    funding_stress: dict[str, Any] = {}
    for multiple in (0.0, 1.0, 2.0):
        stress_book = replace(book, funding_by_bar=book.funding_by_bar * multiple)
        funding_stress[f"{multiple:g}x_actual"] = {
            "locked_oos": _extended(
                engine.run_backtest(
                    stress_book, config, start_ts=oos_start, end_ts=terminal
                )
            ),
            "full": _extended(
                engine.run_backtest(stress_book, config, end_ts=terminal)
            ),
        }

    stress_drawdown_pass = all(
        payload["full"]["max_drawdown"] < 0.20
        and payload["locked_oos"]["max_drawdown"] < 0.20
        and not payload["full"]["liquidated"]
        and not payload["locked_oos"]["liquidated"]
        for payload in stress.values()
    )
    full_pass = _target_pass(full.metrics, minimum_trades=100)
    oos_pass = _target_pass(locked_oos.metrics, minimum_trades=20)
    phase_pass = bool(robustness["phase_audit"]["default_phase_gate_pass"])
    overall = bool(full_pass and oos_pass and stress_drawdown_pass and phase_pass)

    summary = {
        "family": "HYPE-15M-Multi-Mechanism-Trend-Following",
        "version": "HYPE-15M-Multi-Mechanism-Trend-Following-V3",
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
            "prefit": _extended(prefit),
            "locked_oos_flat_reset": _extended(locked_oos),
            "full": _extended(full),
        },
        "recent_slices": slices,
        "stress": stress,
        "leverage_ladder": leverage_ladder,
        "funding_stress": funding_stress,
        "monte_carlo_full_trade_bootstrap": _trade_bootstrap(full.trades),
        "monte_carlo_locked_oos_trade_bootstrap": _trade_bootstrap(
            locked_oos.trades, seed=2026072205
        ),
        "gates": {
            "full_hard_target_pass": full_pass,
            "locked_oos_hard_target_pass": oos_pass,
            "stress_drawdown_pass": stress_drawdown_pass,
            "phase_gate_pass": phase_pass,
            "overall_hard_target_pass": overall,
        },
        "decision": (
            "PASS_FOR_PROMOTION_REVIEW"
            if overall
            else "HARD-GATE-FAILED / registered / not promoted / not live-ready"
        ),
    }
    pd.DataFrame(locked_oos.trades).to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v3_locked_oos_trades_2026-07-22.csv",
        index=False,
    )
    pd.DataFrame(full.trades).to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v3_full_trades_2026-07-22.csv",
        index=False,
    )
    pd.DataFrame(full.equity_path).to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v3_full_equity_2026-07-22.csv",
        index=False,
    )
    OUTPUT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
