from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_v39_near_tp_floor_2026-07-14"
PRE_INCIDENT_END = pd.Timestamp("2026-07-13T14:30:00Z")
NO_FLOOR = base.ProfitFloorConfig(enabled=False)
FLOOR_475_425 = base.ProfitFloorConfig(enabled=True, tiers=((4.75, 4.25),))
FLOOR_490_440 = base.ProfitFloorConfig(enabled=True, tiers=((4.90, 4.40),))
FLOOR_475_425_CD16 = base.ProfitFloorConfig(
    enabled=True,
    tiers=((4.75, 4.25),),
    cooldown_bars_after_floor=16,
)


def run_family(
    *,
    family: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    config: base.V35Config,
    features: pd.DataFrame,
) -> list[base.RunResult]:
    variants = [
        (f"{family}_base", config, NO_FLOOR),
        (f"{family}_floor_475_lock425", config, FLOOR_475_425),
        (f"{family}_floor_475_lock425_cd16", config, FLOOR_475_425_CD16),
        (f"{family}_floor_490_lock440", config, FLOOR_490_440),
        (f"{family}_tp_475", replace(config, take_profit_atr=4.75), NO_FLOOR),
    ]
    return [
        base.run_backtest(name, frame, funding, features, variant_config, floor_config)
        for name, variant_config, floor_config in variants
    ]


def summarize_run(run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "delta_vs_baseline": {
            "return_pp": round(run.metrics["return_pct"] - baseline.metrics["return_pct"], 2),
            "max_drawdown_pp": round(
                run.metrics["max_drawdown_pct"] - baseline.metrics["max_drawdown_pct"],
                2,
            ),
            "sharpe": round(run.metrics["sharpe"] - baseline.metrics["sharpe"], 2),
            "win_rate_pp": round(
                run.metrics["win_rate_pct"] - baseline.metrics["win_rate_pct"],
                2,
            ),
            "closed_trades": run.metrics["trades"] - baseline.metrics["trades"],
        },
    }


def path_for_entry(run: base.RunResult, entry_ts: pd.Timestamp, direction: int) -> dict[str, Any]:
    if not run.trades.empty:
        entry_times = pd.to_datetime(run.trades["entry_ts"], utc=True)
        matched = run.trades.loc[
            entry_times.eq(entry_ts) & run.trades["direction"].eq(direction)
        ]
        if not matched.empty:
            row = matched.iloc[0]
            return {
                "state": "closed",
                "entry_ts": pd.Timestamp(row["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(row["exit_ts"]).isoformat(),
                "direction": int(row["direction"]),
                "entry_price": float(row["entry_price"]),
                "exit_price": float(row["exit_price"]),
                "entry_atr": float(row["entry_atr"]),
                "mfe_atr": float(row["mfe_atr"]),
                "floor_offset_atr": float(row["floor_offset_atr"]),
                "exit_reason": str(row["exit_reason"]),
                "hold_bars": int(row["hold_bars"]),
                "trade_return_pct": base.pct(float(row["trade_return"])),
            }
    position = run.open_position
    if position is not None and pd.Timestamp(position["entry_ts"]) == entry_ts:
        return {"state": "open", **position}
    return {"state": "not_present"}


def current_case(runs: list[base.RunResult]) -> dict[str, Any] | None:
    baseline = runs[0]
    position = baseline.open_position
    if position is None or float(position["mfe_atr"]) < 4.5:
        return None
    entry_ts = pd.Timestamp(position["entry_ts"])
    direction = int(position["direction"])
    return {
        "baseline_entry_ts": entry_ts.isoformat(),
        "direction": direction,
        "paths": {
            run.name: path_for_entry(run, entry_ts, direction)
            for run in runs
        },
    }


def near_tp_cases(run: base.RunResult) -> dict[str, Any]:
    if run.trades.empty:
        closed = run.trades
    else:
        closed = run.trades.loc[run.trades["mfe_atr"].ge(4.5)].copy()
    non_tp = closed.loc[closed["exit_reason"].ne("take_profit")] if not closed.empty else closed
    rows = []
    for _, row in non_tp.iterrows():
        rows.append(
            {
                "entry_ts": pd.Timestamp(row["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(row["exit_ts"]).isoformat(),
                "direction": int(row["direction"]),
                "mfe_atr": float(row["mfe_atr"]),
                "exit_reason": str(row["exit_reason"]),
                "trade_return_pct": base.pct(float(row["trade_return"])),
            }
        )
    open_near_tp = (
        run.open_position
        if run.open_position is not None and float(run.open_position["mfe_atr"]) >= 4.5
        else None
    )
    return {
        "closed_mfe_ge_4_5": int(len(closed)),
        "closed_mfe_ge_4_5_non_tp": int(len(non_tp)),
        "non_tp_cases": rows,
        "open_mfe_ge_4_5": open_near_tp,
    }


def validate_quality(quality: dict[str, Any]) -> None:
    blockers = {
        "missing_15m_bars": quality["missing_15m_bars"],
        "duplicate_ts_before_dedup": quality["duplicate_ts_before_dedup"],
        "invalid_ohlc_rows": quality["invalid_ohlc_rows"],
        "critical_nulls": sum(quality["critical_nulls"].values()),
        "raw_normalized_mismatches": sum(
            quality["raw_vs_normalized"].get("mismatch_rows", {}).values()
        ),
    }
    failed = {key: value for key, value in blockers.items() if value != 0}
    if failed or not quality["is_utc_index"]:
        raise RuntimeError(f"Data-quality gate failed: {failed}, UTC={quality['is_utc_index']}")


def print_run(run: base.RunResult, baseline: base.RunResult) -> None:
    metrics = run.metrics
    delta = metrics["return_pct"] - baseline.metrics["return_pct"]
    print(
        f"{run.name:>30}  ret {metrics['return_pct']:>10.2f}% "
        f"delta {delta:>9.2f}pp  dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>4.2f}  n {metrics['trades']:>3} "
        f"win {metrics['win_rate_pct']:>6.2f}%  exits {metrics['exit_counts']}"
    )


def build_family_runs(
    *,
    family: str,
    frame: pd.DataFrame,
    funding: pd.Series,
) -> tuple[base.V35Config, ab.SignalFlags, list[base.RunResult]]:
    if family == "v35":
        config = base.V35Config()
        flags = ab.SignalFlags()
    elif family == "v39":
        config = v39.v39_config()
        flags = v39.v39_flags()
    else:
        raise ValueError(f"Unsupported family: {family}")
    features = ab.build_signals(base.build_features(frame, config), config, flags)
    runs = run_family(
        family=family,
        frame=frame,
        funding=funding,
        config=config,
        features=features,
    )
    return config, flags, runs


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = base.load_data(warehouse)
    validate_quality(quality)

    v35_config, v35_flags, v35_runs = build_family_runs(
        family="v35", frame=frame, funding=funding
    )
    v39_config, v39_flags, v39_runs = build_family_runs(
        family="v39", frame=frame, funding=funding
    )

    pre_incident_frame = frame.loc[frame.index <= PRE_INCIDENT_END].copy()
    pre_incident_funding = funding.reindex(pre_incident_frame.index).fillna(0.0)
    _, _, v35_pre_incident_runs = build_family_runs(
        family="v35",
        frame=pre_incident_frame,
        funding=pre_incident_funding,
    )
    _, _, v39_pre_incident_runs = build_family_runs(
        family="v39",
        frame=pre_incident_frame,
        funding=pre_incident_funding,
    )

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB V35/V39 near-TP profit-floor diagnostic 2026-07-14",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "cost_model": (
            "Canonical family override: 0.00085 per fill, representing fee plus "
            "4 bps adverse slippage; Binance funding included."
        ),
        "execution_model": {
            "entry": "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1.",
            "bracket": "Fixed entry-ATR 5.0 TP / 7.0 SL; intrabar stop-first.",
            "floor": (
                "MFE is updated after a closed 15m bar. Once activated, the raised "
                "stop becomes effective on the next bar. A crossed next open fills "
                "at open; otherwise at the floor stop."
            ),
            "selection_disclosure": (
                "The two floor rules were fixed before this run from prior V35 "
                "diagnostics and the observed 4.84 ATR near-miss. Standard slices "
                "are audit outputs, not an additional parameter search."
            ),
        },
        "variant_definitions": {
            "base": "Canonical 5.0 ATR TP without profit floor.",
            "floor_475_lock425": "Activate at MFE >= 4.75 ATR and lock +4.25 ATR.",
            "floor_475_lock425_cd16": (
                "Same floor plus a post-floor 16-bar (4-hour) re-entry cooldown. "
                "This was added after the first run exposed immediate re-entry in "
                "the latest case, so it is a post-hoc diagnostic."
            ),
            "floor_490_lock440": "Activate at MFE >= 4.90 ATR and lock +4.40 ATR.",
            "tp_475": "Directly reduce fixed take profit from 5.0 to 4.75 ATR.",
        },
        "families": {
            "v35": {
                "config": asdict(v35_config),
                "signal_flags": asdict(v35_flags),
                "pre_incident_cutoff": PRE_INCIDENT_END.isoformat(),
                "pre_incident_runs": [
                    summarize_run(run, v35_pre_incident_runs[0])
                    for run in v35_pre_incident_runs
                ],
                "runs": [
                    summarize_run(run, v35_runs[0])
                    for run in v35_runs
                ],
                "baseline_near_tp_cases": near_tp_cases(v35_runs[0]),
                "latest_open_case": current_case(v35_runs),
            },
            "v39": {
                "config": asdict(v39_config),
                "signal_flags": asdict(v39_flags),
                "pre_incident_cutoff": PRE_INCIDENT_END.isoformat(),
                "pre_incident_runs": [
                    summarize_run(run, v39_pre_incident_runs[0])
                    for run in v39_pre_incident_runs
                ],
                "runs": [
                    summarize_run(run, v39_runs[0])
                    for run in v39_runs
                ],
                "baseline_near_tp_cases": near_tp_cases(v39_runs[0]),
                "latest_open_case": current_case(v39_runs),
            },
        },
    }

    json_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(v35_runs + v39_runs, trades_path=trades_path, equity_path=equity_path)

    print(f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']}")
    for family_runs in (v35_runs, v39_runs):
        print()
        for run in family_runs:
            print_run(run, family_runs[0])
    print(f"\nsummary -> {json_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
