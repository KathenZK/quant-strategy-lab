from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import mhef_v2_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CANDIDATE_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_prefit_candidate.json"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_mhef_v2_validation_summary.json"
PATH_OUTPUT = ARTIFACT_DIR / "hype_15m_mhef_v2_candidate_path.parquet"


def _recent_slices(
    path: pd.DataFrame,
    terminal: pd.Timestamp,
) -> dict[str, dict[str, Any]]:
    offsets: dict[str, pd.Timedelta | pd.DateOffset] = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.DateOffset(months=1),
        "3m": pd.DateOffset(months=3),
        "6m": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
    }
    return {
        label: engine.slice_metrics(path, start=terminal - offset, end=terminal)
        for label, offset in offsets.items()
    }


def _daily_block_bootstrap(
    path: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    seed: int = 20260728,
    simulations: int = 5000,
    block_days: int = 7,
) -> dict[str, Any]:
    sliced = path.loc[(path["ts"] >= start) & (path["ts"] < end)].copy()
    sliced["return"] = sliced["equity_net"].pct_change().fillna(0.0)
    daily = (
        sliced.set_index("ts")["return"]
        .resample("1D")
        .apply(lambda values: float(np.prod(1.0 + values.to_numpy()) - 1.0))
        .to_numpy("float64")
    )
    if len(daily) < block_days:
        raise RuntimeError("not enough daily returns for block bootstrap")
    rng = np.random.default_rng(seed)
    sample_returns = np.empty(simulations, dtype="float64")
    max_start = len(daily) - block_days + 1
    blocks_needed = int(np.ceil(len(daily) / block_days))
    for simulation in range(simulations):
        starts = rng.integers(0, max_start, size=blocks_needed)
        sample = np.concatenate(
            [daily[index : index + block_days] for index in starts]
        )[: len(daily)]
        sample_returns[simulation] = float(np.prod(1.0 + sample) - 1.0)
    return {
        "method": "moving block bootstrap of daily net returns",
        "seed": seed,
        "simulations": simulations,
        "block_days": block_days,
        "days": int(len(daily)),
        "probability_positive": float((sample_returns > 0.0).mean()),
        "return_percentiles": {
            "p05": float(np.quantile(sample_returns, 0.05)),
            "p50": float(np.quantile(sample_returns, 0.50)),
            "p95": float(np.quantile(sample_returns, 0.95)),
        },
    }


def _buy_hold_metrics(
    book: engine.MarketBook,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    sliced = book.frame.loc[
        (book.frame["ts"] >= start) & (book.frame["ts"] < end)
    ]
    first = float(sliced["open"].iloc[0])
    last = float(sliced["open"].iloc[-1])
    return {
        "start_ts": pd.Timestamp(sliced["ts"].iloc[0]).isoformat(),
        "end_ts": pd.Timestamp(sliced["ts"].iloc[-1]).isoformat(),
        "open_to_open_return": last / first - 1.0,
    }


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    if not candidate["selection_completed_before_prefit_validation_reveal"]:
        raise RuntimeError("candidate was not frozen before validation")
    if not candidate["prefit_validation_unread"]:
        raise RuntimeError("prefit validation has already been marked as read")

    config = engine.config_from_payload(candidate["candidate_config"])
    if engine.config_sha256(config) != candidate["candidate_config_sha256"]:
        raise RuntimeError("candidate config hash mismatch")
    tune_start = pd.Timestamp(
        manifest["freeze_contract"]["development_tune_start_inclusive"]
    )
    validation_start = pd.Timestamp(
        manifest["freeze_contract"]["prefit_validation_start_inclusive"]
    )
    validation_end = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    book = engine.build_book(terminal_exclusive=validation_end)
    train_start = pd.Timestamp(book.frame["ts"].iloc[0])

    result = engine.run_backtest(book, config)
    train = engine.slice_metrics(
        result.path,
        start=train_start,
        end=tune_start,
    )
    tune = engine.slice_metrics(
        result.path,
        start=tune_start,
        end=validation_start,
    )
    validation = engine.slice_metrics(
        result.path,
        start=validation_start,
        end=validation_end,
    )
    zero_cost = engine.run_backtest(
        book,
        replace(config, fee_per_turnover=0.0, slippage_per_turnover=0.0),
    )
    double_cost = engine.run_backtest(
        book,
        replace(
            config,
            fee_per_turnover=2.0 * engine.BASE_FEE,
            slippage_per_turnover=2.0 * engine.BASE_SLIPPAGE,
        ),
    )
    exact_target = engine.run_backtest(
        book,
        replace(
            config,
            no_trade_buffer=0.0,
            minimum_position_change=0.0,
            max_position_step=2.0,
        ),
    )
    zero_validation = engine.slice_metrics(
        zero_cost.path,
        start=validation_start,
        end=validation_end,
    )
    double_validation = engine.slice_metrics(
        double_cost.path,
        start=validation_start,
        end=validation_end,
    )
    exact_validation = engine.slice_metrics(
        exact_target.path,
        start=validation_start,
        end=validation_end,
    )
    passed = (
        validation["gross_return"] > 0.0
        and validation["net_return"] > 0.0
        and validation["max_drawdown"] > -0.20
        and validation["sign_flips"] >= 4
    )
    bootstrap = _daily_block_bootstrap(
        result.path,
        start=validation_start,
        end=validation_end,
    )
    summary = {
        "family": candidate["family"],
        "research_identity": candidate["research_identity"],
        "status": "explore / not promoted / not live-ready",
        "one_time_prefit_validation_reveal": True,
        "candidate_frozen_before_reveal": True,
        "no_post_reveal_tuning_authorized": True,
        "reused_locked_oos_from_2026_04_28_remains_unread": True,
        "candidate_label": candidate["candidate_label"],
        "candidate_config": candidate["candidate_config"],
        "candidate_config_sha256": candidate["candidate_config_sha256"],
        "development": {
            "train": train,
            "tune": tune,
        },
        "prefit_validation": validation,
        "validation_gate": {
            "rule": (
                "positive gross and net return, max drawdown above -20%, "
                "and at least four sign flips"
            ),
            "passed": bool(passed),
        },
        "validation_diagnostics": {
            "zero_cost": zero_validation,
            "base_cost": validation,
            "double_cost": double_validation,
            "exact_target_without_cost_controls": exact_validation,
            "buy_hold": _buy_hold_metrics(
                book,
                start=validation_start,
                end=validation_end,
            ),
            "daily_block_bootstrap": bootstrap,
        },
        "recent_slices_anchored_to_prefit_validation_end": _recent_slices(
            result.path,
            validation_end,
        ),
        "decision": (
            "PREFIT_VALIDATION_PASS_BUT_NOT_PROMOTED"
            if passed
            else "NO_GO_PREFIT_VALIDATION_FAILED"
        ),
        "next_gate": (
            "fresh outcome-blind prospective OOS is required; the existing "
            "2026-04-28 onward window is already revealed and cannot qualify"
            if passed
            else "do not rescue or retune this candidate on the revealed validation"
        ),
    }
    candidate["prefit_validation_unread"] = False
    candidate["prefit_validation_revealed_at_validation_script"] = True
    CANDIDATE_PATH.write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    result.path.to_parquet(PATH_OUTPUT, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
