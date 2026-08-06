from __future__ import annotations

import importlib.util
import json
import math
import sys
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
FOLDS = {
    "BTC": (
        ("2021", pd.Timestamp("2020-12-31 23:59:59", tz="UTC"), pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2021-12-31 23:59:59", tz="UTC")),
        ("2022", pd.Timestamp("2021-12-31 23:59:59", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2022-12-31 23:59:59", tz="UTC")),
        ("2023", pd.Timestamp("2022-12-31 23:59:59", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-12-31 23:59:59", tz="UTC")),
    ),
    "ETH": (
        ("2021", pd.Timestamp("2020-12-31 23:59:59", tz="UTC"), pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2021-12-31 23:59:59", tz="UTC")),
        ("2022", pd.Timestamp("2021-12-31 23:59:59", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2022-12-31 23:59:59", tz="UTC")),
        ("2023", pd.Timestamp("2022-12-31 23:59:59", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-12-31 23:59:59", tz="UTC")),
    ),
    "HYPE": (
        ("2025-09_10", pd.Timestamp("2025-08-31 23:59:59", tz="UTC"), pd.Timestamp("2025-09-01", tz="UTC"), pd.Timestamp("2025-10-31 23:59:59", tz="UTC")),
    ),
}
BIASES = ("none", "weekly", "monthly", "weekly_monthly_consensus")


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply_bias(scores: pd.DataFrame, hourly: pd.DataFrame, bias: str) -> pd.DataFrame:
    if scores.empty or bias == "none":
        return scores.copy()
    log_close = np.log(hourly["close"].astype(float))
    weekly = (log_close - log_close.shift(168)).reindex(scores.index)
    monthly = (log_close - log_close.shift(672)).reindex(scores.index)
    side = scores["direction"].astype(float)
    weekly_ok = side * weekly > 0.0
    monthly_ok = side * monthly > 0.0
    if bias == "weekly":
        mask = weekly_ok
    elif bias == "monthly":
        mask = monthly_ok
    elif bias == "weekly_monthly_consensus":
        mask = weekly_ok & monthly_ok
    else:
        raise ValueError(f"unknown bias: {bias}")
    return scores.loc[mask.fillna(False)].copy()


def variants(engine: Any) -> list[tuple[str, int, bool]]:
    rows: list[tuple[str, int, bool]] = []
    for bias in BIASES:
        rows.append((bias, 0, False))
        for layers in (1, 3):
            for half_reduce in (True, False):
                rows.append((bias, layers, half_reduce))
    return rows


def config_for(engine: Any, variant_id: str, layers: int, half_reduce: bool, stress: bool = False) -> Any:
    return engine.Config(
        name=("stress_" if stress else "base_") + variant_id,
        slippage=0.0008 if stress else 0.0004,
        allow_adds=layers > 0,
        allow_half_reduce=half_reduce and layers > 0,
        max_layers=layers,
    )


def aggregate_variant(asset: str, variant_id: str, fold_metrics: pd.DataFrame, campaigns: pd.DataFrame) -> dict[str, Any]:
    part = fold_metrics.loc[(fold_metrics["asset"] == asset) & (fold_metrics["variant_id"] == variant_id)].copy()
    camp = campaigns.loc[(campaigns["asset"] == asset) & (campaigns["variant_id"] == variant_id) & campaigns["closed"]].copy() if len(campaigns) else pd.DataFrame()
    compound = float(np.prod(1.0 + part["total_return_pct"].to_numpy(float) / 100.0) - 1.0)
    gains = float(camp.loc[camp["net_pnl"].gt(0), "net_pnl"].sum()) if len(camp) else 0.0
    losses = float(-camp.loc[camp["net_pnl"].lt(0), "net_pnl"].sum()) if len(camp) else 0.0
    positive = camp.loc[camp["net_pnl"].gt(0), "net_pnl"].sort_values(ascending=False) if len(camp) else pd.Series(dtype=float)
    return {
        "asset": asset,
        "variant_id": variant_id,
        "folds": int(len(part)),
        "compound_return_pct": compound * 100.0,
        "positive_folds": int(part["total_return_pct"].gt(0).sum()),
        "worst_fold_return_pct": float(part["total_return_pct"].min()),
        "median_fold_return_pct": float(part["total_return_pct"].median()),
        "worst_max_drawdown_pct": float(part["max_drawdown_pct"].min()),
        "worst_intrabar_drawdown_pct": float(part["intrabar_max_drawdown_pct"].min()),
        "campaigns": int(len(camp)),
        "profit_factor": gains / losses if losses > 1e-12 else math.inf,
        "top1_gross_profit_concentration": float(positive.head(1).sum() / positive.sum()) if positive.sum() > 0 else math.nan,
        "top3_gross_profit_concentration": float(positive.head(3).sum() / positive.sum()) if positive.sum() > 0 else math.nan,
        "max_effective_leverage": float(part["max_effective_leverage"].max()),
        "max_projected_stop_risk_pct": float(part["max_projected_stop_risk_pct"].max()),
        "risk_violations": int(part["risk_violations"].sum()),
    }


def main() -> None:
    engine = load_module(ENGINE_PATH, "bin_mtf_ptc_regime_campaign_engine")
    entry = engine.load_path(engine.ENTRY_PATH, "bin_mtf_ptc_regime_entry")
    meter = entry.load_path(entry.METER_PATH, "bin_mtf_ptc_regime_meter")
    data_module = entry.load_path(entry.DATA_PATH, "bin_mtf_ptc_regime_data")
    hourly_frames, _ = meter.load_module().load_assets()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))

    base_metrics_rows: list[dict[str, Any]] = []
    base_campaign_parts: list[pd.DataFrame] = []
    fold_cache: dict[tuple[str, str], tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, float, pd.Timestamp, pd.Timestamp]] = {}
    for asset, symbol in engine.SYMBOLS.items():
        bars15, funding, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        for fold_name, train_end, eval_start, eval_end in FOLDS[asset]:
            hourly_visible = hourly.loc[hourly.index <= eval_end]
            bars_visible = bars15.loc[bars15.index <= eval_end]
            scores, threshold = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED[asset], train_end, eval_start, eval_end)
            all_attempts = engine.build_attempts(entry, scores, hourly_visible, bars_visible, engine.SELECTED[asset])
            fold_cache[(asset, fold_name)] = (scores, all_attempts, bars_visible, funding, threshold, eval_start, eval_end)
            for bias, layers, half_reduce in variants(engine):
                variant_id = f"{bias}__layers{layers}__half{int(half_reduce)}"
                filtered_scores = apply_bias(scores, hourly_visible, bias)
                kept = set(filtered_scores.index)
                attempts = all_attempts.loc[all_attempts["candidate_ts"].isin(kept)].copy() if len(all_attempts) else all_attempts
                config = config_for(engine, variant_id, layers, half_reduce)
                result = engine.run_engine(asset, bars_visible, funding, filtered_scores, attempts, threshold, eval_start, eval_end, config)
                base_metrics_rows.append({"fold": fold_name, "variant_id": variant_id, "bias": bias, "layers": layers, "half_reduce": half_reduce, **result.metrics})
                if len(result.campaigns):
                    campaign = result.campaigns.copy()
                    campaign.insert(1, "fold", fold_name)
                    campaign.insert(2, "variant_id", variant_id)
                    base_campaign_parts.append(campaign)

    base_metrics = pd.DataFrame(base_metrics_rows)
    base_campaigns = pd.concat(base_campaign_parts, ignore_index=True) if base_campaign_parts else pd.DataFrame()
    aggregate_rows: list[dict[str, Any]] = []
    for asset in engine.SYMBOLS:
        for variant_id in base_metrics.loc[base_metrics["asset"] == asset, "variant_id"].unique():
            aggregate_rows.append(aggregate_variant(asset, variant_id, base_metrics, base_campaigns))
    aggregate = pd.DataFrame(aggregate_rows)
    aggregate["eligible"] = False
    for asset in engine.SYMBOLS:
        mask = aggregate["asset"].eq(asset)
        if asset in {"BTC", "ETH"}:
            eligible = aggregate["positive_folds"].ge(2) & aggregate["campaigns"].ge(30)
        else:
            eligible = aggregate["campaigns"].ge(8)
        eligible &= aggregate["profit_factor"].gt(1.0) & aggregate["worst_max_drawdown_pct"].ge(-20.0) & aggregate["worst_intrabar_drawdown_pct"].ge(-20.0) & aggregate["risk_violations"].eq(0)
        aggregate.loc[mask, "eligible"] = eligible.loc[mask]

    selected_rows: list[dict[str, Any]] = []
    selected_campaign_parts: list[pd.DataFrame] = []
    selected_action_parts: list[pd.DataFrame] = []
    selected_equity_parts: list[pd.DataFrame] = []
    for asset in engine.SYMBOLS:
        candidates = aggregate.loc[(aggregate["asset"] == asset) & aggregate["eligible"]].copy()
        if candidates.empty:
            candidates = aggregate.loc[aggregate["asset"] == asset].copy()
        selected = candidates.sort_values(["compound_return_pct", "worst_fold_return_pct", "profit_factor", "variant_id"], ascending=[False, False, False, True]).iloc[0]
        variant_id = str(selected["variant_id"])
        bias = variant_id.split("__")[0]
        layers = int(variant_id.split("__layers")[1].split("__")[0])
        half_reduce = bool(int(variant_id.rsplit("half", 1)[1]))

        stress_fold_metrics: list[dict[str, Any]] = []
        for fold_name, *_ in FOLDS[asset]:
            scores, all_attempts, bars_visible, funding, threshold, eval_start, eval_end = fold_cache[(asset, fold_name)]
            hourly_visible = hourly_frames[asset].loc[hourly_frames[asset].index <= eval_end]
            filtered_scores = apply_bias(scores, hourly_visible, bias)
            kept = set(filtered_scores.index)
            attempts = all_attempts.loc[all_attempts["candidate_ts"].isin(kept)].copy() if len(all_attempts) else all_attempts
            result = engine.run_engine(asset, bars_visible, funding, filtered_scores, attempts, threshold, eval_start, eval_end, config_for(engine, variant_id, layers, half_reduce, stress=True))
            stress_fold_metrics.append({"fold": fold_name, **result.metrics})
        stress_frame = pd.DataFrame(stress_fold_metrics)
        stress_compound = float((np.prod(1.0 + stress_frame["total_return_pct"].to_numpy(float) / 100.0) - 1.0) * 100.0)

        symbol = engine.SYMBOLS[asset]
        bars15, funding, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        dev_end, val_start, val_end = meter.SPLITS[asset]
        hourly_visible = hourly.loc[hourly.index <= val_end]
        bars_visible = bars15.loc[bars15.index <= val_end]
        scores, threshold = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED[asset], dev_end, val_start, val_end)
        filtered_scores = apply_bias(scores, hourly_visible, bias)
        attempts_all = engine.build_attempts(entry, scores, hourly_visible, bars_visible, engine.SELECTED[asset])
        kept = set(filtered_scores.index)
        attempts = attempts_all.loc[attempts_all["candidate_ts"].isin(kept)].copy() if len(attempts_all) else attempts_all
        for stress in (False, True):
            result = engine.run_engine(asset, bars_visible, funding, filtered_scores, attempts, threshold, val_start, val_end, config_for(engine, variant_id, layers, half_reduce, stress=stress))
            selected_rows.append({"asset": asset, "variant_id": variant_id, "selected_inner_compound_return_pct": float(selected["compound_return_pct"]), "selected_inner_stress_compound_return_pct": stress_compound, "selection_eligible": bool(selected["eligible"]), "history_status": "exploratory_single_fold" if asset == "HYPE" else "expanding_development_folds", "evaluation": "revealed_diagnostic_validation_stress" if stress else "revealed_diagnostic_validation_base", **result.metrics})
            if len(result.campaigns):
                frame = result.campaigns.copy()
                frame.insert(1, "variant_id", variant_id)
                frame.insert(2, "evaluation", "stress" if stress else "base")
                selected_campaign_parts.append(frame)
            if not stress and len(result.actions):
                frame = result.actions.copy()
                frame.insert(1, "variant_id", variant_id)
                selected_action_parts.append(frame)
            if not stress and len(result.equity):
                frame = result.equity.copy()
                frame.insert(2, "variant_id", variant_id)
                selected_equity_parts.append(frame)

    selected_frame = pd.DataFrame(selected_rows)
    selected_campaigns = pd.concat(selected_campaign_parts, ignore_index=True) if selected_campaign_parts else pd.DataFrame()
    selected_actions = pd.concat(selected_action_parts, ignore_index=True) if selected_action_parts else pd.DataFrame()
    selected_equity = pd.concat(selected_equity_parts, ignore_index=True) if selected_equity_parts else pd.DataFrame()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base_metrics.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_inner_fold_metrics_2026-08-03.csv", index=False)
    aggregate.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_inner_aggregate_2026-08-03.csv", index=False)
    selected_frame.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_selected_diagnostic_2026-08-03.csv", index=False)
    selected_campaigns.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_selected_campaigns_2026-08-03.csv", index=False)
    selected_actions.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_selected_actions_2026-08-03.csv", index=False)
    selected_equity.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_selected_equity_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_regime_campaign_v1_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "search_variants_per_asset": len(variants(engine)), "folds": {asset: [row[0] for row in folds] for asset, folds in FOLDS.items()}, "selected": selected_frame.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("TOP INNER")
    print(aggregate.sort_values(["asset", "compound_return_pct"], ascending=[True, False]).groupby("asset").head(5).to_string(index=False))
    print("\nSELECTED DIAGNOSTIC")
    print(selected_frame.to_string(index=False))


if __name__ == "__main__":
    main()
