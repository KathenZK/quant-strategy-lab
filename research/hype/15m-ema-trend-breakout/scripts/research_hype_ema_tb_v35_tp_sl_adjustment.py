from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"
LATEST_CASE_ENTRY = pd.Timestamp("2026-07-13T14:45:00Z")


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def high_mfe_losses(trades: pd.DataFrame) -> dict[str, dict[str, int]]:
    return {
        str(threshold): {
            "reached": int((trades["mfe_atr"] >= threshold).sum()),
            "losses": int(
                ((trades["mfe_atr"] >= threshold) & (trades["trade_return"] <= 0.0)).sum()
            ),
        }
        for threshold in (1.5, 2.0, 3.0, 4.0, 4.5, 4.75)
    }


def latest_path(trades: pd.DataFrame) -> list[dict[str, Any]]:
    selected = trades.loc[
        pd.to_datetime(trades["entry_ts"], utc=True) >= LATEST_CASE_ENTRY
    ].copy()
    if selected.empty:
        return []
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "mfe_atr",
        "exit_reason",
        "trade_return",
    ]
    selected = selected[columns]
    selected["trade_return_pct"] = selected["trade_return"] * 100.0
    return selected.drop(columns="trade_return").to_dict("records")


def summarize(run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "capital_retention_vs_base_pct": round(
            float(run.equity_curve.iloc[-1] / baseline.equity_curve.iloc[-1] * 100.0),
            2,
        ),
        "high_mfe": high_mfe_losses(run.trades),
        "standard_slices": run.slices,
        "latest_path": latest_path(run.trades),
    }


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    baseline_config = base.V35Config()
    features = base.build_features(frame, baseline_config)
    no_floor = base.ProfitFloorConfig(enabled=False)
    variants = [
        ("v35_tp5_sl7", baseline_config),
        ("v35_tp475_sl7", replace(baseline_config, take_profit_atr=4.75)),
        ("v35_tp5_sl6", replace(baseline_config, hard_stop_atr=6.0)),
        (
            "v35_tp475_sl6",
            replace(
                baseline_config,
                take_profit_atr=4.75,
                hard_stop_atr=6.0,
            ),
        ),
    ]
    runs = [
        base.run_backtest(name, frame, funding, features, config, no_floor)
        for name, config in variants
    ]
    baseline = runs[0]
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 TP4.75/SL6 diagnostic 2026-07-15",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "selection_disclosure": (
            "TP4.75/SL6 was requested after observing the latest near-TP reversal; "
            "results are post-hoc in-sample diagnostics. Standard slices are audit only."
        ),
        "cost_model": (
            "V35 canonical override: 0.00085 per fill, including fee and 4 bps "
            "adverse slippage; Binance funding included."
        ),
        "execution_model": (
            "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1; "
            "fixed entry-ATR TP/SL; 15m intrabar stop-first."
        ),
        "baseline_config": asdict(baseline_config),
        "rows": [summarize(run, baseline) for run in runs],
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"gaps={quality['missing_15m_bars']}"
    )
    for run in runs:
        metrics = run.metrics
        print(
            f"{run.name:>16} ret={metrics['return_pct']:>8.2f}% "
            f"dd={metrics['max_drawdown_pct']:>7.2f}% "
            f"sharpe={metrics['sharpe']:>4.2f} "
            f"win={metrics['win_rate_pct']:>5.2f}% trades={metrics['trades']}"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
