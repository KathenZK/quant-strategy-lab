from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import sds_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_sds_baseline_summary.json"
TRADES_PATH = ARTIFACT_DIR / "hype_15m_sds_baseline_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_15m_sds_baseline_equity.csv"
STATES_PATH = ARTIFACT_DIR / "hype_15m_sds_baseline_states.parquet"


def _recent_slices(result: engine.BacktestResult, terminal: pd.Timestamp) -> dict[str, object]:
    offsets = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.DateOffset(months=1),
        "3m": pd.DateOffset(months=3),
        "6m": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
    }
    return {
        label: engine.slice_metrics(
            result,
            start=terminal - offset,
            end=terminal,
        )
        for label, offset in offsets.items()
    }


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    config = engine.BASELINE_CONFIG
    if engine.config_sha256(config) != manifest["hashes"]["baseline_config_sha256"]:
        raise RuntimeError("baseline config differs from frozen manifest")

    prefit_book = engine.build_book(include_locked_oos=False)
    prefit_result = engine.run_backtest(prefit_book, config)

    full_book = engine.build_book(include_locked_oos=True)
    full_result = engine.run_backtest(full_book, config)
    oos_start = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    oos = engine.slice_metrics(
        full_result,
        start=oos_start,
        end=full_book.terminal_ts,
    )
    benchmark_return = float(full_book.close[-1] / full_book.close[0] - 1.0)
    summary = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "status": "explore / not promoted / not live-ready",
        "one_time_reveal": True,
        "no_post_reveal_tuning_authorized": True,
        "config": engine.config_payload(config),
        "config_sha256": engine.config_sha256(config),
        "data_terminal_exclusive": full_book.terminal_ts.isoformat(),
        "locked_oos_start_inclusive": oos_start.isoformat(),
        "oos_provenance": manifest["freeze_contract"]["oos_provenance"],
        "prefit": prefit_result.metrics,
        "locked_oos": oos,
        "full": full_result.metrics,
        "full_buy_hold_return": benchmark_return,
        "full_excess_return_vs_buy_hold": (
            full_result.metrics["total_return"] - benchmark_return
        ),
        "recent_slices": _recent_slices(full_result, full_book.terminal_ts),
        "transition_counts": (
            pd.Series(full_result.states.transition_reason)
            .value_counts()
            .sort_index()
            .to_dict()
        ),
        "decision_rule": {
            "research_bar": "baseline must have positive prefit and locked OOS return, positive excess return, locked OOS MDD below 25%, and at least 30 locked OOS trades before it is worth ablation",
            "promotion": "not evaluated; all repository validation gates remain required",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(full_result.trades).to_csv(TRADES_PATH, index=False)
    pd.DataFrame(full_result.equity_path).to_csv(EQUITY_PATH, index=False)
    engine.states_frame(full_book, full_result.states).to_parquet(
        STATES_PATH,
        index=False,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
