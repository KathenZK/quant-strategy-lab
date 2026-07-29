from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pandas as pd

import sma_xs_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PREFIT_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_prefit_selection.json"
PREFIT_RANKING_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_prefit_ranking.csv"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_one_time_reveal.json"
OOS_RANKING_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_locked_oos_audit.csv"
TRADES_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_selected_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_selected_equity.csv"
STATES_PATH = ARTIFACT_DIR / "hype_15m_sma_xs_selected_states.parquet"


def _label(config: engine.Config) -> str:
    if config.exit_mode == "cross_only":
        return "cross_only"
    return (
        f"{config.exit_mode}"
        f"__k{config.slope_window}"
        f"__confirm{config.exit_confirm_bars}"
    )


def _calmar_like(metrics: dict[str, Any]) -> float:
    return float(metrics["return"]) / max(abs(float(metrics["max_drawdown"])), 0.05)


def _recent_slices(
    result: engine.BacktestResult,
    terminal: pd.Timestamp,
) -> dict[str, object]:
    offsets = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.DateOffset(months=1),
        "3m": pd.DateOffset(months=3),
        "6m": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
    }
    return {
        label: engine.slice_metrics(result, start=terminal - offset, end=terminal)
        for label, offset in offsets.items()
    }


def _frozen_configs(manifest: dict[str, Any]) -> list[engine.Config]:
    configs = [engine.Config(**payload) for payload in manifest["candidate_grid"]]
    if len({_label(config) for config in configs}) != len(configs):
        raise RuntimeError("candidate labels are not unique")
    return configs


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    configs = _frozen_configs(manifest)
    oos_start = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    validation_start = pd.Timestamp(
        manifest["freeze_contract"]["prefit_validation_start_inclusive"]
    )

    prefit_book = engine.build_book(include_locked_oos=False)
    prefit_rows: list[dict[str, Any]] = []
    for config in configs:
        result = engine.run_backtest(prefit_book, config)
        train = engine.slice_metrics(
            result,
            start=prefit_book.source_start,
            end=validation_start,
        )
        validation = engine.slice_metrics(
            result,
            start=validation_start,
            end=oos_start,
        )
        eligible = (
            train["return"] > 0.0
            and validation["return"] > 0.0
            and train["trades"] >= 8
            and validation["trades"] >= 3
        )
        score = min(_calmar_like(train), _calmar_like(validation))
        prefit_rows.append(
            {
                "label": _label(config),
                "exit_mode": config.exit_mode,
                "slope_window": config.slope_window,
                "exit_confirm_bars": config.exit_confirm_bars,
                "eligible": eligible,
                "selection_score": score,
                "train_return": train["return"],
                "train_max_drawdown": train["max_drawdown"],
                "train_trades": train["trades"],
                "train_win_rate": train["win_rate"],
                "validation_return": validation["return"],
                "validation_max_drawdown": validation["max_drawdown"],
                "validation_trades": validation["trades"],
                "validation_win_rate": validation["win_rate"],
                "prefit_return": result.metrics["total_return"],
                "prefit_max_drawdown": result.metrics["max_drawdown"],
                "prefit_trades": result.metrics["trades"],
                "prefit_win_rate": result.metrics["win_rate"],
            }
        )
    prefit_frame = pd.DataFrame(prefit_rows).sort_values(
        ["eligible", "selection_score", "validation_return"],
        ascending=[False, False, False],
    )
    eligible = prefit_frame.loc[prefit_frame["eligible"]]
    selected_row = (
        eligible.iloc[0]
        if not eligible.empty
        else prefit_frame.sort_values(
            ["selection_score", "validation_return"],
            ascending=[False, False],
        ).iloc[0]
    )
    reference = next(
        config for config in configs if _label(config) == selected_row["label"]
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    prefit_frame.to_csv(PREFIT_RANKING_PATH, index=False)
    prefit_payload = {
        "family": "HYPE-15M-SMA-Crossover-Slope",
        "selection_completed_before_locked_oos_reveal": True,
        "selection_rule": (
            "eligible requires positive train and validation returns, at least "
            "8 train and 3 validation trades; maximize the weaker train/validation "
            "return-to-drawdown ratio"
        ),
        "viable_candidate_exists": bool(not eligible.empty),
        "reference_only": bool(eligible.empty),
        "reference_label": _label(reference),
        "reference_config": engine.config_payload(reference),
        "reference_config_sha256": engine.config_sha256(reference),
        "reference_prefit_row": selected_row.to_dict(),
        "eligible_candidates": int(len(eligible)),
        "candidate_count": int(len(prefit_frame)),
    }
    PREFIT_PATH.write_text(
        json.dumps(prefit_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    full_book = engine.build_book(include_locked_oos=True)
    oos_rows: list[dict[str, Any]] = []
    selected_result: engine.BacktestResult | None = None
    baseline_result: engine.BacktestResult | None = None
    for config in configs:
        result = engine.run_backtest(full_book, config)
        oos = engine.slice_metrics(
            result,
            start=oos_start,
            end=full_book.terminal_ts,
        )
        oos_rows.append(
            {
                "label": _label(config),
                "prefit_reference": _label(config) == _label(reference),
                "locked_oos_return": oos["return"],
                "locked_oos_max_drawdown": oos["max_drawdown"],
                "locked_oos_trades": oos["trades"],
                "locked_oos_win_rate": oos["win_rate"],
                "full_return": result.metrics["total_return"],
                "full_max_drawdown": result.metrics["max_drawdown"],
                "full_trades": result.metrics["trades"],
                "full_win_rate": result.metrics["win_rate"],
            }
        )
        if _label(config) == _label(reference):
            selected_result = result
        if config.exit_mode == "cross_only":
            baseline_result = result
    if selected_result is None or baseline_result is None:
        raise RuntimeError("selected or baseline result missing")
    pd.DataFrame(oos_rows).sort_values(
        "locked_oos_return",
        ascending=False,
    ).to_csv(OOS_RANKING_PATH, index=False)

    selected_oos = engine.slice_metrics(
        selected_result,
        start=oos_start,
        end=full_book.terminal_ts,
    )
    baseline_oos = engine.slice_metrics(
        baseline_result,
        start=oos_start,
        end=full_book.terminal_ts,
    )
    screenshot_start = pd.Timestamp("2026-07-14T00:00:00Z")
    screenshot_end = full_book.terminal_ts
    zero_cost = engine.run_backtest(
        full_book,
        replace(reference, fee_per_fill=0.0, slippage_per_fill=0.0),
    )
    double_cost = engine.run_backtest(
        full_book,
        replace(
            reference,
            fee_per_fill=2.0 * engine.BASE_FEE,
            slippage_per_fill=2.0 * engine.BASE_SLIPPAGE,
        ),
    )
    visible_trades = [
        trade
        for trade in selected_result.trades
        if screenshot_start <= pd.Timestamp(trade["entry_ts"]) < screenshot_end
    ]
    summary = {
        "family": "HYPE-15M-SMA-Crossover-Slope",
        "status": "explore / not promoted / not live-ready",
        "one_time_reveal": True,
        "no_post_reveal_tuning_authorized": True,
        "prefit_selection": prefit_payload,
        "data_terminal_exclusive": full_book.terminal_ts.isoformat(),
        "locked_oos_start_inclusive": oos_start.isoformat(),
        "oos_provenance": manifest["freeze_contract"]["oos_provenance"],
        "least_bad_prefit_reference": {
            "locked_oos": selected_oos,
            "full": selected_result.metrics,
            "recent_slices": _recent_slices(selected_result, full_book.terminal_ts),
            "screenshot_window": engine.slice_metrics(
                selected_result,
                start=screenshot_start,
                end=screenshot_end,
            ),
            "screenshot_window_trades": visible_trades,
            "exit_reason_counts": (
                pd.Series([trade["exit_reason"] for trade in selected_result.trades])
                .value_counts()
                .sort_index()
                .to_dict()
            ),
        },
        "cross_only_baseline": {
            "locked_oos": baseline_oos,
            "full": baseline_result.metrics,
            "recent_slices": _recent_slices(baseline_result, full_book.terminal_ts),
            "screenshot_window": engine.slice_metrics(
                baseline_result,
                start=screenshot_start,
                end=screenshot_end,
            ),
        },
        "cost_stress_reference_full": {
            "zero_cost": zero_cost.metrics,
            "base_cost": selected_result.metrics,
            "double_cost": double_cost.metrics,
        },
        "decision_rule": {
            "research_bar": (
                "a viable candidate must remain positive on prefit train, "
                "prefit validation and locked OOS after "
                "fee, slippage and actual funding; slope exit must improve a "
                "meaningful risk or return dimension over cross-only"
            ),
            "promotion": "not evaluated; all repository gates and fresh prospective OOS remain required",
        },
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(selected_result.trades).to_csv(TRADES_PATH, index=False)
    pd.DataFrame(selected_result.equity_path).to_csv(EQUITY_PATH, index=False)
    engine.states_frame(full_book, selected_result.states).to_parquet(
        STATES_PATH,
        index=False,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
