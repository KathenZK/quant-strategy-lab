from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_cooldown_scan_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
RESULTS_PATH = ARTIFACT_DIR / f"{OUT_STEM}.csv"
SEARCH_BARS = range(0, 97)
STANDARD_WINDOWS = ("1d", "7d", "1m", "3m", "6m", "1y", "full")


def flatten_run(
    run: base.RunResult,
    baseline: base.RunResult,
    cooldown_bars: int,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "cooldown_bars": cooldown_bars,
        "cooldown_hours": cooldown_bars * 0.25,
        "earliest_reentry_bar": cooldown_bars + 1,
        "return_pct": run.metrics["return_pct"],
        "max_drawdown_pct": run.metrics["max_drawdown_pct"],
        "sharpe": run.metrics["sharpe"],
        "trades": run.metrics["trades"],
        "wins": run.metrics["wins"],
        "win_rate_pct": run.metrics["win_rate_pct"],
        "final_equity_retained_pct": (
            100.0
            if cooldown_bars == 0
            else cooldown.comparison(run, baseline)["final_equity_retained_pct"]
        ),
    }
    slices = {item["window"]: item for item in run.slices}
    for window in STANDARD_WINDOWS:
        item = slices[window]
        row[f"{window}_return_pct"] = item["return_pct"]
        row[f"{window}_max_drawdown_pct"] = item["max_drawdown_pct"]
        row[f"{window}_closed_trades"] = item["closed_trades"]
    return row


def ranked_records(
    results: pd.DataFrame,
    column: str,
    ascending: bool,
    limit: int = 10,
) -> list[dict[str, Any]]:
    columns = [
        "cooldown_bars",
        "cooldown_hours",
        "return_pct",
        "max_drawdown_pct",
        "sharpe",
        "trades",
        "win_rate_pct",
        "final_equity_retained_pct",
        "1m_return_pct",
        "3m_return_pct",
    ]
    return (
        results.sort_values(
            [column, "cooldown_bars"],
            ascending=[ascending, True],
        )
        .head(limit)[columns]
        .to_dict(orient="records")
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    features = base.build_features(frame, config)

    runs: list[base.RunResult] = []
    for cooldown_bars in SEARCH_BARS:
        spec = cooldown.RunSpec(
            name=f"v35_cooldown_{cooldown_bars}",
            cooldown_bars=cooldown_bars,
            use_rsi10_90=False,
        )
        runs.append(
            cooldown.run_backtest(
                spec=spec,
                frame=frame,
                funding=funding,
                features=features,
                config=config,
            )
        )

    baseline = runs[0]
    canonical = base.run_backtest(
        "canonical_parity",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_max_equity_diff = float(
        (baseline.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_max_equity_diff > 1e-12:
        raise ValueError(
            f"baseline parity failed: max equity diff={parity_max_equity_diff}"
        )

    results = pd.DataFrame(
        [
            flatten_run(run, baseline, cooldown_bars)
            for cooldown_bars, run in zip(SEARCH_BARS, runs, strict=True)
        ]
    )
    results.to_csv(RESULTS_PATH, index=False)

    baseline_row = results.loc[results["cooldown_bars"] == 0].iloc[0]
    risk_improvers = results.loc[
        (results["cooldown_bars"] > 0)
        & (
            results["max_drawdown_pct"]
            > float(baseline_row["max_drawdown_pct"])
        )
        & (results["final_equity_retained_pct"] >= 80.0)
    ].copy()
    strict_dominators = results.loc[
        (results["cooldown_bars"] > 0)
        & (results["return_pct"] >= float(baseline_row["return_pct"]))
        & (
            results["max_drawdown_pct"]
            >= float(baseline_row["max_drawdown_pct"])
        )
        & (results["sharpe"] >= float(baseline_row["sharpe"]))
    ].copy()

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V35",
        "audit_id": "post-exit cooldown exhaustive scan",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_not_registered",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "baseline_vs_canonical_max_equity_diff": parity_max_equity_diff,
        },
        "search_contract": {
            "cooldown_bars": [min(SEARCH_BARS), max(SEARCH_BARS)],
            "timeframe": "15m",
            "definition": (
                "For cooldown N after an exit on bar E, block E+1 through E+N; "
                "the earliest permitted new entry is E+N+1 open."
            ),
            "selection_warning": (
                "This is an in-sample diagnostic scan. Recent slices are audit "
                "views and do not make the selected cooldown independently OOS."
            ),
            "unchanged": (
                "V35 signals, K0/K1/K2 timing, sizing, 5ATR TP, 7ATR SL, "
                "ADX22 delayed3, 384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "base_config": asdict(config),
        "baseline": baseline_row.to_dict(),
        "rankings": {
            "full_return": ranked_records(
                results, "return_pct", ascending=False
            ),
            "max_drawdown": ranked_records(
                results, "max_drawdown_pct", ascending=False
            ),
            "sharpe": ranked_records(results, "sharpe", ascending=False),
            "recent_1m_return": ranked_records(
                results, "1m_return_pct", ascending=False
            ),
            "recent_3m_return": ranked_records(
                results, "3m_return_pct", ascending=False
            ),
        },
        "risk_improvers_retaining_at_least_80pct_equity": (
            risk_improvers.to_dict(orient="records")
        ),
        "strict_dominators": strict_dominators.to_dict(orient="records"),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={gate['passed']}"
    )
    print(f"baseline parity max equity diff: {parity_max_equity_diff:.2e}")
    print("top full return:")
    print(
        results.sort_values(
            ["return_pct", "cooldown_bars"], ascending=[False, True]
        )[
            [
                "cooldown_bars",
                "return_pct",
                "max_drawdown_pct",
                "sharpe",
                "trades",
                "win_rate_pct",
                "final_equity_retained_pct",
                "1m_return_pct",
                "3m_return_pct",
            ]
        ]
        .head(15)
        .to_string(index=False)
    )
    print(
        "risk improvers retaining >=80% final equity: "
        f"{len(risk_improvers)}"
    )
    print(f"strict dominators: {len(strict_dominators)}")
    print(f"summary -> {SUMMARY_PATH}")
    print(f"results -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
