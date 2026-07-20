from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
OOS_ROOT = FAMILY_DIR / "artifacts/v1_oos_2026q2"
PREDICTION_PATH = OOS_ROOT / "oos_predictions.parquet"
TRADE_PATH = OOS_ROOT / "oos_completed_trades.csv"
DECISION_PATH = OOS_ROOT / "oos_portfolio_decisions.csv"
OUTPUT_PATH = OOS_ROOT / "oos_execution_stress_audit.json"
SCENARIO_PATH = OOS_ROOT / "oos_execution_stress_scenarios.csv"
HORIZON_HOURS = 24
DETERMINISTIC_REJECTION_RATE = 0.05
DETERMINISTIC_FEED_OUTAGE_RATE = 0.05
ADDITIONAL_ENTRY_GAP_COST = 0.001


def compound(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    return float(np.prod(1.0 + values.to_numpy(dtype="float64")) - 1.0)


def metrics(
    decisions: pd.DataFrame,
    *,
    active_column: str = "active",
) -> dict[str, Any]:
    returns = decisions["portfolio_return"].astype("float64")
    equity = np.cumprod(1.0 + returns.to_numpy())
    total_return = float(equity[-1] - 1.0) if len(equity) else 0.0
    years = max(len(returns) * HORIZON_HOURS / (24.0 * 365.0), 1.0 / 365.0)
    annualized_return = (
        float(equity[-1] ** (1.0 / years) - 1.0)
        if len(equity) and equity[-1] > 0.0
        else -1.0
    )
    curve = np.concatenate([[1.0], equity])
    peak = np.maximum.accumulate(curve)
    max_drawdown = float(np.min(curve / peak - 1.0))
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        float(returns.mean() / std * np.sqrt(365.0)) if std > 0.0 else 0.0
    )
    active = decisions[active_column].astype(bool)
    active_returns = returns.loc[active]
    positive = float(active_returns.clip(lower=0.0).sum())
    negative = float(-active_returns.clip(upper=0.0).sum())
    monthly = (
        decisions.assign(month=decisions["ts"].dt.strftime("%Y-%m"))
        .groupby("month", sort=True)["portfolio_return"]
        .apply(compound)
    )
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "active_decision_count": int(active.sum()),
        "portfolio_win_rate": (
            float(active_returns.gt(0.0).mean()) if len(active_returns) else 0.0
        ),
        "portfolio_profit_factor": (
            positive / negative if negative > 0.0 else float("inf")
        ),
        "positive_month_share": float(monthly.gt(0.0).mean()),
    }


def stable_bucket(*values: object) -> int:
    payload = "|".join(str(value) for value in values).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % 10_000


def aggregate_legs(legs: pd.DataFrame, all_timestamps: pd.Series) -> pd.DataFrame:
    grouped = (
        legs.groupby("ts", sort=True)["scenario_weighted_return"]
        .sum()
        .rename("portfolio_return")
    )
    frame = pd.DataFrame({"ts": pd.to_datetime(all_timestamps, utc=True)})
    frame = frame.merge(grouped, on="ts", how="left", validate="one_to_one")
    frame["portfolio_return"] = frame["portfolio_return"].fillna(0.0)
    frame["active"] = True
    return frame


def main() -> None:
    trades = pd.read_csv(TRADE_PATH)
    trades["ts"] = pd.to_datetime(trades["ts"], utc=True)
    decisions = pd.read_csv(DECISION_PATH)
    decisions["ts"] = pd.to_datetime(decisions["ts"], utc=True)
    predictions = pd.read_parquet(
        PREDICTION_PATH,
        columns=[
            "ts",
            "symbol",
            "label_long_net_24h",
            "label_short_net_24h",
        ],
    )
    predictions["ts"] = pd.to_datetime(predictions["ts"], utc=True)

    base = decisions[["ts", "portfolio_return"]].copy()
    base["active"] = True
    scenarios: dict[str, dict[str, Any]] = {"frozen_base": metrics(base)}

    gap = trades.copy()
    gap["scenario_weighted_return"] = (
        gap["trade_return"] - ADDITIONAL_ENTRY_GAP_COST
    ) * gap["capital_weight"]
    gap_decisions = aggregate_legs(gap, decisions["ts"])
    scenarios["additional_10bps_entry_gap"] = metrics(gap_decisions)

    rejected = trades.copy()
    rejected["rejected"] = rejected.apply(
        lambda row: stable_bucket(row["ts"].isoformat(), row["symbol"], row["side"])
        < int(DETERMINISTIC_REJECTION_RATE * 10_000),
        axis=1,
    )
    rejected["scenario_weighted_return"] = np.where(
        rejected["rejected"],
        0.0,
        rejected["weighted_return"],
    )
    rejected_decisions = aggregate_legs(rejected, decisions["ts"])
    scenarios["deterministic_5pct_order_rejection"] = {
        **metrics(rejected_decisions),
        "rejected_leg_count": int(rejected["rejected"].sum()),
        "rejected_leg_share": float(rejected["rejected"].mean()),
    }

    outage = base.copy()
    outage["feed_outage"] = outage["ts"].apply(
        lambda ts: stable_bucket(ts.isoformat(), "full_portfolio_feed_outage")
        < int(DETERMINISTIC_FEED_OUTAGE_RATE * 10_000)
    )
    outage["portfolio_return"] = np.where(
        outage["feed_outage"], 0.0, outage["portfolio_return"]
    )
    outage["active"] = ~outage["feed_outage"]
    scenarios["deterministic_5pct_missing_decision_bar"] = {
        **metrics(outage),
        "skipped_decision_count": int(outage["feed_outage"].sum()),
        "skipped_decision_share": float(outage["feed_outage"].mean()),
    }

    delayed_outcomes = predictions.rename(columns={"ts": "outcome_ts"})
    delayed = trades.copy()
    delayed["outcome_ts"] = delayed["ts"] + pd.Timedelta(hours=1)
    delayed = delayed.merge(
        delayed_outcomes,
        on=["outcome_ts", "symbol"],
        how="left",
        validate="many_to_one",
    )
    delayed["delayed_trade_return"] = np.where(
        delayed["side"].eq("long"),
        delayed["label_long_net_24h"],
        delayed["label_short_net_24h"],
    )
    missing_delayed = int(delayed["delayed_trade_return"].isna().sum())
    delayed["scenario_weighted_return"] = (
        delayed["delayed_trade_return"].fillna(0.0) * delayed["capital_weight"]
    )
    delayed_decisions = aggregate_legs(delayed, decisions["ts"])
    scenarios["one_hour_entry_delay"] = {
        **metrics(delayed_decisions),
        "missing_delayed_outcome_leg_count": missing_delayed,
    }

    rows = []
    for scenario, values in scenarios.items():
        rows.append({"scenario": scenario, **values})
    pd.DataFrame(rows).to_csv(SCENARIO_PATH, index=False)

    actual_missing_exit_count = int(trades["trade_return"].isna().sum())
    audit = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "version": "BIN-1H-CSLGBM-V1",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "scope": (
            "Post-reveal fixed diagnostics only. These scenarios do not alter or "
            "select model, factors, universe, Top N, exposure, threshold, or timing."
        ),
        "actual_data_integrity": {
            "completed_leg_count": len(trades),
            "missing_exit_leg_count": actual_missing_exit_count,
        },
        "scenario_definitions": {
            "additional_10bps_entry_gap": (
                "Subtract 10 bps from every selected leg in addition to frozen costs."
            ),
            "deterministic_5pct_order_rejection": (
                "Reject a stable SHA256-selected 5% of legs; rejected capital stays cash."
            ),
            "deterministic_5pct_missing_decision_bar": (
                "Skip stable SHA256-selected decision timestamps; all capital stays cash."
            ),
            "one_hour_entry_delay": (
                "Keep the frozen K0 ranks but enter each selected symbol one hour later "
                "and hold it for the same 24h, using the next timestamp's audited label."
            ),
        },
        "scenarios": scenarios,
        "interpretation": (
            "Execution stresses are robustness diagnostics, not permission to tune on "
            "the revealed 2026Q2 OOS. V1 remains hard-gate failed because its frozen "
            "single-month positive-profit contribution exceeds 35%."
        ),
    }
    OUTPUT_PATH.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
