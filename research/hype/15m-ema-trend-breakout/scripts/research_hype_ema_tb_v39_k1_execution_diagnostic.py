from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39_ab


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09"
NO_FLOOR = base.ProfitFloorConfig(enabled=False)


def run_v39_variant(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> base.RunResult:
    return base.run_backtest(name, frame, funding, features, config, NO_FLOOR)


def summarize_run(run: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "slices": run.slices,
        "d90": ab.window_stats(run, 90),
        "d30": ab.window_stats(run, 30),
        "long_side": ab.side_stats(run, 1),
        "short_side": ab.side_stats(run, -1),
        "open_position": run.open_position,
    }


def annotate_trades(run: base.RunResult, frame: pd.DataFrame, entry_delay_bars: int) -> pd.DataFrame:
    trades = run.trades.copy()
    if trades.empty:
        return trades
    trades["variant"] = run.name
    trades["signal_bar"] = trades["entry_bar"] - entry_delay_bars
    trades["signal_ts"] = trades["signal_bar"].map(lambda idx: frame.index[int(idx)].isoformat())
    trades["entry_atr_source_bar"] = trades["entry_bar"] - 1
    trades["entry_atr_source_ts"] = trades["entry_atr_source_bar"].map(lambda idx: frame.index[int(idx)].isoformat())
    return trades


def trade_path_comparison(k2: base.RunResult, k1: base.RunResult, frame: pd.DataFrame) -> dict[str, Any]:
    k2_trades = annotate_trades(k2, frame, 2)
    k1_trades = annotate_trades(k1, frame, 1)
    if k2_trades.empty or k1_trades.empty:
        return {
            "k2_trades": int(len(k2_trades)),
            "k1_trades": int(len(k1_trades)),
            "common_signal_direction": 0,
            "k2_only_signal_direction": int(len(k2_trades)),
            "k1_only_signal_direction": int(len(k1_trades)),
        }
    keys = ["signal_bar", "direction"]
    merged = k2_trades.merge(k1_trades, on=keys, suffixes=("_k2", "_k1"), how="outer", indicator=True)
    common = merged.loc[merged["_merge"] == "both"].copy()
    if not common.empty:
        common["entry_price_delta_pct"] = (common["entry_price_k1"] / common["entry_price_k2"] - 1.0) * 100.0
        common["trade_return_delta_pct"] = (common["trade_return_k1"] - common["trade_return_k2"]) * 100.0
        common["hold_bars_delta"] = common["hold_bars_k1"] - common["hold_bars_k2"]
    return {
        "k2_trades": int(len(k2_trades)),
        "k1_trades": int(len(k1_trades)),
        "common_signal_direction": int((merged["_merge"] == "both").sum()),
        "k2_only_signal_direction": int((merged["_merge"] == "left_only").sum()),
        "k1_only_signal_direction": int((merged["_merge"] == "right_only").sum()),
        "common_entry_price_delta_pct": describe_series(common.get("entry_price_delta_pct")),
        "common_trade_return_delta_pct": describe_series(common.get("trade_return_delta_pct")),
        "common_hold_bars_delta": describe_series(common.get("hold_bars_delta")),
        "exit_reason_pairs": (
            common.groupby(["exit_reason_k2", "exit_reason_k1"]).size().reset_index(name="count").to_dict("records")
            if not common.empty
            else []
        ),
        "k2_only_examples": select_examples(merged.loc[merged["_merge"] == "left_only"], "_k2"),
        "k1_only_examples": select_examples(merged.loc[merged["_merge"] == "right_only"], "_k1"),
    }


def describe_series(series: pd.Series | None) -> dict[str, Any]:
    if series is None or series.empty:
        return {"count": 0}
    return {
        "count": int(series.count()),
        "mean": round(float(series.mean()), 6),
        "median": round(float(series.median()), 6),
        "min": round(float(series.min()), 6),
        "max": round(float(series.max()), 6),
    }


def select_examples(frame: pd.DataFrame, suffix: str, limit: int = 8) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    columns = [
        f"signal_ts{suffix}",
        "direction",
        f"entry_ts{suffix}",
        f"exit_ts{suffix}",
        f"exit_reason{suffix}",
        f"trade_return{suffix}",
    ]
    existing = [column for column in columns if column in frame.columns]
    out = frame[existing].head(limit).copy()
    for column in out.columns:
        if column.startswith("trade_return"):
            out[f"{column}_pct"] = out[column].astype(float).mul(100.0).round(4)
            out = out.drop(columns=[column])
    return out.to_dict("records")


def add_deltas(rows: list[dict[str, Any]]) -> None:
    base_row = next(row for row in rows if row["name"] == "v39_k2_base")
    for row in rows:
        row["delta_vs_k2_base"] = {
            "full_return_pp": round(row["metrics"]["return_pct"] - base_row["metrics"]["return_pct"], 2),
            "full_maxdd_pp": round(row["metrics"]["max_drawdown_pct"] - base_row["metrics"]["max_drawdown_pct"], 2),
            "sharpe": round(row["metrics"]["sharpe"] - base_row["metrics"]["sharpe"], 4),
            "trades": row["metrics"]["trades"] - base_row["metrics"]["trades"],
            "win_rate_pp": round(row["metrics"]["win_rate_pct"] - base_row["metrics"]["win_rate_pct"], 2),
            "d90_return_pp": round(row["d90"]["return_pct"] - base_row["d90"]["return_pct"], 2),
            "d90_maxdd_pp": round(row["d90"]["max_drawdown_pct"] - base_row["d90"]["max_drawdown_pct"], 2),
            "d90_win_rate_pp": round((row["d90"]["win_rate_pct"] or 0.0) - (base_row["d90"]["win_rate_pct"] or 0.0), 2),
        }


def print_row(row: dict[str, Any]) -> None:
    metrics = row["metrics"]
    d90 = row["d90"]
    d30 = row["d30"]
    print(
        f"{row['name']:>16} | full {metrics['return_pct']:>9.2f}% dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>5.2f} n {metrics['trades']:>3} win {metrics['win_rate_pct']:>6.2f}% "
        f"| 90d {d90['return_pct']:>8.2f}% dd {d90['max_drawdown_pct']:>7.2f}% "
        f"win {d90['win_rate_pct'] or 0:>6.2f}% n {d90['trades']:>3} "
        f"| 30d {d30['return_pct']:>7.2f}%"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)

    k2_config = v39_ab.v39_config()
    k1_config = replace(k2_config, entry_delay_bars=1)
    features = ab.build_signals(base.build_features(frame, k2_config), k2_config, v39_ab.v39_flags())

    k2_run = run_v39_variant("v39_k2_base", frame, funding, features, k2_config)
    k1_run = run_v39_variant("v39_k1_entry", frame, funding, features, k1_config)
    runs = [k2_run, k1_run]
    rows = [summarize_run(run) for run in runs]
    add_deltas(rows)
    for row in rows:
        print_row(row)

    comparison = trade_path_comparison(k2_run, k1_run, frame)
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V39 K+1 execution diagnostic",
        "baseline": "HYPE-EMA-TB-V39 K2 open",
        "data_quality": quality,
        "cost_model": "Binance USD-M perp, 0.00085 per fill (fee + 4bps slippage combined), funding included.",
        "execution_assumptions": {
            "k2_base": "K0 close signal, skip completed K1, enter at K2 open, entry_atr from K1 completed ATR672.",
            "k1_variant": "K0 close signal, enter at K1 open, entry_atr from K0 completed ATR672. This is an execution diagnostic, not a V39 replacement.",
            "unchanged": "Signals, sizing formula, TP/SL, indicator exit, timeout, cost and funding assumptions unchanged.",
        },
        "v39_flags": asdict(v39_ab.v39_flags()),
        "k2_config": asdict(k2_config),
        "k1_config": asdict(k1_config),
        "rows": rows,
        "trade_path_comparison": comparison,
    }

    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)

    annotated_trades_path = ARTIFACT_DIR / f"{OUT_STEM}_annotated_trades.csv"
    pd.concat(
        [
            annotate_trades(k2_run, frame, k2_config.entry_delay_bars),
            annotate_trades(k1_run, frame, k1_config.entry_delay_bars),
        ],
        ignore_index=True,
    ).to_csv(annotated_trades_path, index=False)

    print(f"\nsummary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"annotated trades -> {annotated_trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
