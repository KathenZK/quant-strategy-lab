from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/multi-timeframe-pullback-trend-campaign"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = FAMILY_DIR / "scripts/research_campaign_engine_v0.py"
V1_PATH = FAMILY_DIR / "scripts/search_regime_campaign_v1.py"
SCALES = {
    "1x": (0.0025, 0.009, 0.010),
    "2x": (0.0050, 0.018, 0.020),
    "3x": (0.0075, 0.027, 0.030),
}


def main() -> None:
    v1 = __import__("importlib").util.spec_from_file_location("bin_mtf_ptc_scale_v1", V1_PATH)
    if v1 is None or v1.loader is None:
        raise RuntimeError(f"cannot load {V1_PATH}")
    v1_module = __import__("importlib").util.module_from_spec(v1)
    __import__("sys").modules[v1.name] = v1_module
    v1.loader.exec_module(v1_module)
    engine = v1_module.load_module(ENGINE_PATH, "bin_mtf_ptc_scale_engine")
    entry = engine.load_path(engine.ENTRY_PATH, "bin_mtf_ptc_scale_entry")
    meter = entry.load_path(entry.METER_PATH, "bin_mtf_ptc_scale_meter")
    data_module = entry.load_path(entry.DATA_PATH, "bin_mtf_ptc_scale_data")
    hourly = meter.load_module().load_assets()[0]["BTC"]
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    bars15, funding, _ = data_module.load_symbol_data(warehouse, engine.SYMBOLS["BTC"], require_raw_parity=True)

    rows: list[dict[str, Any]] = []
    campaign_parts: list[pd.DataFrame] = []
    fold_payload: list[tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame, float, pd.Timestamp, pd.Timestamp]] = []
    for fold_name, train_end, eval_start, eval_end in v1_module.FOLDS["BTC"]:
        hourly_visible = hourly.loc[hourly.index <= eval_end]
        bars_visible = bars15.loc[bars15.index <= eval_end]
        scores_all, threshold = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED["BTC"], train_end, eval_start, eval_end)
        scores = v1_module.apply_bias(scores_all, hourly_visible, "weekly_monthly_consensus")
        attempts = engine.build_attempts(entry, scores_all, hourly_visible, bars_visible, engine.SELECTED["BTC"])
        attempts = attempts.loc[attempts["candidate_ts"].isin(set(scores.index))].copy() if len(attempts) else attempts
        fold_payload.append((fold_name, scores, attempts, bars_visible, threshold, eval_start, eval_end))

    for cost_name, slippage in (("base", 0.0004), ("stress", 0.0008)):
        for scale_name, (layer_risk, operational_risk, hard_risk) in SCALES.items():
            for fold_name, scores, attempts, bars_visible, threshold, eval_start, eval_end in fold_payload:
                config = engine.Config(name=f"{cost_name}_{scale_name}", slippage=slippage, allow_adds=True, allow_half_reduce=False, max_layers=3, layer_risk=layer_risk, operational_risk=operational_risk, hard_risk=hard_risk)
                result = engine.run_engine("BTC", bars_visible, funding, scores, attempts, threshold, eval_start, eval_end, config)
                rows.append({"sample": "development_fold", "fold": fold_name, "cost": cost_name, "scale": scale_name, **result.metrics})
                if cost_name == "base" and scale_name in {"1x", "3x"} and len(result.campaigns):
                    frame = result.campaigns.copy()
                    frame.insert(1, "sample", "development_fold")
                    frame.insert(2, "fold", fold_name)
                    frame.insert(3, "scale", scale_name)
                    campaign_parts.append(frame)

    dev_end, val_start, val_end = meter.SPLITS["BTC"]
    hourly_visible = hourly.loc[hourly.index <= val_end]
    bars_visible = bars15.loc[bars15.index <= val_end]
    scores_all, threshold = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED["BTC"], dev_end, val_start, val_end)
    scores = v1_module.apply_bias(scores_all, hourly_visible, "weekly_monthly_consensus")
    attempts = engine.build_attempts(entry, scores_all, hourly_visible, bars_visible, engine.SELECTED["BTC"])
    attempts = attempts.loc[attempts["candidate_ts"].isin(set(scores.index))].copy() if len(attempts) else attempts
    for cost_name, slippage in (("base", 0.0004), ("stress", 0.0008)):
        for scale_name, (layer_risk, operational_risk, hard_risk) in SCALES.items():
            config = engine.Config(name=f"{cost_name}_{scale_name}", slippage=slippage, allow_adds=True, allow_half_reduce=False, max_layers=3, layer_risk=layer_risk, operational_risk=operational_risk, hard_risk=hard_risk)
            result = engine.run_engine("BTC", bars_visible, funding, scores, attempts, threshold, val_start, val_end, config)
            rows.append({"sample": "revealed_diagnostic_validation", "fold": "2024_to_2025H1", "cost": cost_name, "scale": scale_name, **result.metrics})
            if cost_name == "base" and scale_name in {"1x", "3x"} and len(result.campaigns):
                frame = result.campaigns.copy()
                frame.insert(1, "sample", "revealed_diagnostic_validation")
                frame.insert(2, "fold", "2024_to_2025H1")
                frame.insert(3, "scale", scale_name)
                campaign_parts.append(frame)

    metrics = pd.DataFrame(rows)
    campaigns = pd.concat(campaign_parts, ignore_index=True) if campaign_parts else pd.DataFrame()
    aggregate_rows: list[dict[str, Any]] = []
    for cost_name in ("base", "stress"):
        for scale_name in SCALES:
            part = metrics.loc[(metrics["sample"] == "development_fold") & (metrics["cost"] == cost_name) & (metrics["scale"] == scale_name)]
            cumulative = float(np.prod(1.0 + part["total_return_pct"].to_numpy(float) / 100.0))
            annual_multiple = cumulative ** (1.0 / max(len(part), 1))
            validation = metrics.loc[(metrics["sample"] == "revealed_diagnostic_validation") & (metrics["cost"] == cost_name) & (metrics["scale"] == scale_name)].iloc[0]
            aggregate_rows.append({
                "cost": cost_name,
                "scale": scale_name,
                "development_3y_equity_multiple": cumulative,
                "development_annual_equity_multiple": annual_multiple,
                "development_worst_fold_return_pct": float(part["total_return_pct"].min()),
                "development_worst_mdd_pct": float(part["max_drawdown_pct"].min()),
                "development_worst_intrabar_mdd_pct": float(part["intrabar_max_drawdown_pct"].min()),
                "development_max_leverage": float(part["max_effective_leverage"].max()),
                "development_max_stop_risk_pct": float(part["max_projected_stop_risk_pct"].max()),
                "development_risk_violations": int(part["risk_violations"].sum()),
                "diagnostic_validation_annual_equity_multiple": float(validation["annual_equity_multiple"]),
                "diagnostic_validation_return_pct": float(validation["total_return_pct"]),
                "diagnostic_validation_mdd_pct": float(validation["max_drawdown_pct"]),
                "diagnostic_validation_intrabar_mdd_pct": float(validation["intrabar_max_drawdown_pct"]),
                "diagnostic_validation_max_leverage": float(validation["max_effective_leverage"]),
                "diagnostic_validation_max_stop_risk_pct": float(validation["max_projected_stop_risk_pct"]),
                "diagnostic_validation_risk_violations": int(validation["risk_violations"]),
                "log_growth_scale_needed_for_20x_from_validation": math.log(20.0) / math.log(float(validation["annual_equity_multiple"])) if float(validation["annual_equity_multiple"]) > 1.0 else math.inf,
            })
    aggregate = pd.DataFrame(aggregate_rows)
    metrics.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_risk_scaling_v1_metrics_2026-08-03.csv", index=False)
    aggregate.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_risk_scaling_v1_aggregate_2026-08-03.csv", index=False)
    campaigns.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_risk_scaling_v1_campaigns_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_risk_scaling_v1_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "scales": SCALES, "aggregate": aggregate.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
