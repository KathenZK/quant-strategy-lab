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
PARENTS = {
    "BTC": {"bias": "weekly_monthly_consensus", "layers": 3, "half_reduce": False},
    "ETH": {"bias": "none", "layers": 0, "half_reduce": False},
    "HYPE": {"bias": "none", "layers": 0, "half_reduce": False},
}
STYLES = {
    "market": None,
    "limit25_1h": (0.25, 1),
    "limit50_1h": (0.50, 1),
    "limit25_4h": (0.25, 4),
    "limit50_4h": (0.50, 4),
}


def transform_attempts(attempts: pd.DataFrame, bars15: pd.DataFrame, style: str) -> pd.DataFrame:
    result = attempts.copy()
    if result.empty:
        return result
    result["entry_style"] = "market" if style == "market" else "limit"
    result["fill_intrabar"] = False
    result["style_id"] = style
    if style == "market":
        return result
    fraction, valid_hours = STYLES[style] or (0.0, 0)
    for index, row in result.loc[result["entry_ts"].notna()].iterrows():
        market_ts = pd.Timestamp(row["entry_ts"])
        restart_ts = market_ts - pd.Timedelta(minutes=15)
        if restart_ts not in bars15.index:
            result.loc[index, ["entry_ts", "raw_entry", "fill_intrabar", "status"]] = [pd.NaT, math.nan, False, "limit_missing_restart_bar"]
            result.loc[index, "resolved_ts"] = min(market_ts + pd.Timedelta(hours=valid_hours), pd.Timestamp(row["candidate_ts"]) + pd.Timedelta(hours=24))
            continue
        side = int(row["side"])
        restart_close = float(bars15.loc[restart_ts, "close"])
        stop = float(row["stop"])
        limit = restart_close - side * fraction * abs(restart_close - stop)
        expiry = min(market_ts + pd.Timedelta(hours=valid_hours), pd.Timestamp(row["candidate_ts"]) + pd.Timedelta(hours=24))
        window = bars15.loc[(bars15.index >= market_ts) & (bars15.index < expiry)]
        fill_ts: pd.Timestamp | None = None
        raw_fill = math.nan
        intrabar = False
        for ts, bar in window.iterrows():
            marketable = float(bar["open"]) <= limit if side > 0 else float(bar["open"]) >= limit
            touched = float(bar["low"]) <= limit if side > 0 else float(bar["high"]) >= limit
            if marketable:
                fill_ts = ts
                raw_fill = float(bar["open"])
                break
            if touched:
                fill_ts = ts
                raw_fill = limit
                intrabar = True
                break
        if fill_ts is None:
            result.loc[index, ["entry_ts", "raw_entry", "fill_intrabar", "status"]] = [pd.NaT, math.nan, False, "limit_unfilled"]
            result.loc[index, "resolved_ts"] = expiry
        else:
            result.loc[index, ["entry_ts", "raw_entry", "fill_intrabar", "status"]] = [fill_ts, raw_fill, intrabar, "entered_limit"]
            result.loc[index, "resolved_ts"] = fill_ts
    return result


def aggregate(asset: str, style: str, fold_metrics: pd.DataFrame, campaigns: pd.DataFrame) -> dict[str, Any]:
    part = fold_metrics.loc[(fold_metrics["asset"] == asset) & (fold_metrics["style"] == style)]
    camp = campaigns.loc[(campaigns["asset"] == asset) & (campaigns["style"] == style) & campaigns["closed"]] if len(campaigns) else pd.DataFrame()
    compound = float((np.prod(1.0 + part["total_return_pct"].to_numpy(float) / 100.0) - 1.0) * 100.0)
    gains = float(camp.loc[camp["net_pnl"].gt(0), "net_pnl"].sum()) if len(camp) else 0.0
    losses = float(-camp.loc[camp["net_pnl"].lt(0), "net_pnl"].sum()) if len(camp) else 0.0
    positive = camp.loc[camp["net_pnl"].gt(0), "net_pnl"].sort_values(ascending=False) if len(camp) else pd.Series(dtype=float)
    return {
        "asset": asset,
        "style": style,
        "compound_return_pct": compound,
        "positive_folds": int(part["total_return_pct"].gt(0).sum()),
        "worst_fold_return_pct": float(part["total_return_pct"].min()),
        "median_fold_return_pct": float(part["total_return_pct"].median()),
        "campaigns": int(len(camp)),
        "profit_factor": gains / losses if losses > 1e-12 else math.inf,
        "worst_drawdown_pct": float(part["max_drawdown_pct"].min()),
        "worst_intrabar_drawdown_pct": float(part["intrabar_max_drawdown_pct"].min()),
        "top1_gross_profit_concentration": float(positive.head(1).sum() / positive.sum()) if positive.sum() > 0 else math.nan,
        "top3_gross_profit_concentration": float(positive.head(3).sum() / positive.sum()) if positive.sum() > 0 else math.nan,
        "risk_violations": int(part["risk_violations"].sum()),
    }


def main() -> None:
    v1 = __import__("importlib").util.spec_from_file_location("bin_mtf_ptc_limit_v1", V1_PATH)
    if v1 is None or v1.loader is None:
        raise RuntimeError(f"cannot load {V1_PATH}")
    v1_module = __import__("importlib").util.module_from_spec(v1)
    __import__("sys").modules[v1.name] = v1_module
    v1.loader.exec_module(v1_module)
    engine = v1_module.load_module(ENGINE_PATH, "bin_mtf_ptc_limit_engine")
    entry = engine.load_path(engine.ENTRY_PATH, "bin_mtf_ptc_limit_entry")
    meter = entry.load_path(entry.METER_PATH, "bin_mtf_ptc_limit_meter")
    data_module = entry.load_path(entry.DATA_PATH, "bin_mtf_ptc_limit_data")
    hourly_frames, _ = meter.load_module().load_assets()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))

    fold_metrics_rows: list[dict[str, Any]] = []
    campaign_parts: list[pd.DataFrame] = []
    cache: dict[tuple[str, str], tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, float, pd.Timestamp, pd.Timestamp]] = {}
    for asset, symbol in engine.SYMBOLS.items():
        bars15, funding, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        parent = PARENTS[asset]
        for fold_name, train_end, eval_start, eval_end in v1_module.FOLDS[asset]:
            hourly_visible = hourly.loc[hourly.index <= eval_end]
            bars_visible = bars15.loc[bars15.index <= eval_end]
            scores, threshold = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED[asset], train_end, eval_start, eval_end)
            scores = v1_module.apply_bias(scores, hourly_visible, str(parent["bias"]))
            all_scores, _ = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED[asset], train_end, eval_start, eval_end)
            attempts = engine.build_attempts(entry, all_scores, hourly_visible, bars_visible, engine.SELECTED[asset])
            attempts = attempts.loc[attempts["candidate_ts"].isin(set(scores.index))].copy() if len(attempts) else attempts
            cache[(asset, fold_name)] = (scores, attempts, bars_visible, funding, threshold, eval_start, eval_end)
            for style in STYLES:
                styled = transform_attempts(attempts, bars_visible, style)
                config = engine.Config(name=f"base_{style}", allow_adds=int(parent["layers"]) > 0, allow_half_reduce=bool(parent["half_reduce"]), max_layers=int(parent["layers"]))
                result = engine.run_engine(asset, bars_visible, funding, scores, styled, threshold, eval_start, eval_end, config)
                fold_metrics_rows.append({"fold": fold_name, "style": style, **result.metrics})
                if len(result.campaigns):
                    frame = result.campaigns.copy()
                    frame.insert(1, "fold", fold_name)
                    frame.insert(2, "style", style)
                    campaign_parts.append(frame)

    fold_metrics = pd.DataFrame(fold_metrics_rows)
    campaigns = pd.concat(campaign_parts, ignore_index=True) if campaign_parts else pd.DataFrame()
    aggregate_rows = [aggregate(asset, style, fold_metrics, campaigns) for asset in engine.SYMBOLS for style in STYLES]
    aggregate_frame = pd.DataFrame(aggregate_rows)
    aggregate_frame["eligible"] = False
    for asset in engine.SYMBOLS:
        mask = aggregate_frame["asset"].eq(asset)
        required_positive = 2 if asset in {"BTC", "ETH"} else 1
        minimum_campaigns = 30 if asset in {"BTC", "ETH"} else 8
        eligible = aggregate_frame["positive_folds"].ge(required_positive) & aggregate_frame["campaigns"].ge(minimum_campaigns) & aggregate_frame["profit_factor"].gt(1.0) & aggregate_frame["worst_drawdown_pct"].ge(-20.0) & aggregate_frame["worst_intrabar_drawdown_pct"].ge(-20.0) & aggregate_frame["risk_violations"].eq(0)
        aggregate_frame.loc[mask, "eligible"] = eligible.loc[mask]

    selected_rows: list[dict[str, Any]] = []
    selected_campaign_parts: list[pd.DataFrame] = []
    selected_action_parts: list[pd.DataFrame] = []
    selected_equity_parts: list[pd.DataFrame] = []
    for asset, symbol in engine.SYMBOLS.items():
        choices = aggregate_frame.loc[(aggregate_frame["asset"] == asset) & aggregate_frame["eligible"]]
        if choices.empty:
            choices = aggregate_frame.loc[aggregate_frame["asset"] == asset]
        selected = choices.sort_values(["compound_return_pct", "worst_fold_return_pct", "profit_factor", "style"], ascending=[False, False, False, True]).iloc[0]
        style = str(selected["style"])
        parent = PARENTS[asset]
        stress_metrics: list[dict[str, Any]] = []
        for fold_name, *_ in v1_module.FOLDS[asset]:
            scores, attempts, bars_visible, funding, threshold, eval_start, eval_end = cache[(asset, fold_name)]
            styled = transform_attempts(attempts, bars_visible, style)
            config = engine.Config(name=f"stress_{style}", slippage=0.0008, allow_adds=int(parent["layers"]) > 0, allow_half_reduce=bool(parent["half_reduce"]), max_layers=int(parent["layers"]))
            result = engine.run_engine(asset, bars_visible, funding, scores, styled, threshold, eval_start, eval_end, config)
            stress_metrics.append(result.metrics)
        stress_compound = float((np.prod(1.0 + pd.DataFrame(stress_metrics)["total_return_pct"].to_numpy(float) / 100.0) - 1.0) * 100.0)

        bars15, funding, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        dev_end, val_start, val_end = meter.SPLITS[asset]
        hourly_visible = hourly.loc[hourly.index <= val_end]
        bars_visible = bars15.loc[bars15.index <= val_end]
        scores_all, threshold = engine.fit_score_frame(meter, hourly_visible, engine.SELECTED[asset], dev_end, val_start, val_end)
        scores = v1_module.apply_bias(scores_all, hourly_visible, str(parent["bias"]))
        attempts = engine.build_attempts(entry, scores_all, hourly_visible, bars_visible, engine.SELECTED[asset])
        attempts = attempts.loc[attempts["candidate_ts"].isin(set(scores.index))].copy() if len(attempts) else attempts
        styled = transform_attempts(attempts, bars_visible, style)
        for stress in (False, True):
            config = engine.Config(name=("stress_" if stress else "base_") + style, slippage=0.0008 if stress else 0.0004, allow_adds=int(parent["layers"]) > 0, allow_half_reduce=bool(parent["half_reduce"]), max_layers=int(parent["layers"]))
            result = engine.run_engine(asset, bars_visible, funding, scores, styled, threshold, val_start, val_end, config)
            selected_rows.append({"asset": asset, "style": style, "selected_inner_compound_return_pct": float(selected["compound_return_pct"]), "selected_inner_stress_compound_return_pct": stress_compound, "selection_eligible": bool(selected["eligible"]), "history_status": "exploratory_single_fold" if asset == "HYPE" else "expanding_development_folds", "evaluation": "revealed_diagnostic_validation_stress" if stress else "revealed_diagnostic_validation_base", **result.metrics})
            if len(result.campaigns):
                frame = result.campaigns.copy()
                frame.insert(1, "style", style)
                frame.insert(2, "evaluation", "stress" if stress else "base")
                selected_campaign_parts.append(frame)
            if not stress and len(result.actions):
                frame = result.actions.copy()
                frame.insert(1, "style", style)
                selected_action_parts.append(frame)
            if not stress and len(result.equity):
                frame = result.equity.copy()
                frame.insert(2, "style", style)
                selected_equity_parts.append(frame)

    selected_frame = pd.DataFrame(selected_rows)
    selected_campaigns = pd.concat(selected_campaign_parts, ignore_index=True) if selected_campaign_parts else pd.DataFrame()
    selected_actions = pd.concat(selected_action_parts, ignore_index=True) if selected_action_parts else pd.DataFrame()
    selected_equity = pd.concat(selected_equity_parts, ignore_index=True) if selected_equity_parts else pd.DataFrame()
    fold_metrics.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_inner_fold_metrics_2026-08-03.csv", index=False)
    aggregate_frame.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_inner_aggregate_2026-08-03.csv", index=False)
    selected_frame.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_selected_diagnostic_2026-08-03.csv", index=False)
    selected_campaigns.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_selected_campaigns_2026-08-03.csv", index=False)
    selected_actions.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_selected_actions_2026-08-03.csv", index=False)
    selected_equity.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_selected_equity_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_limit_retest_v2_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "styles": list(STYLES), "parents": PARENTS, "selected": selected_frame.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("INNER")
    print(aggregate_frame.sort_values(["asset", "compound_return_pct"], ascending=[True, False]).to_string(index=False))
    print("\nSELECTED DIAGNOSTIC")
    print(selected_frame.to_string(index=False))


if __name__ == "__main__":
    main()
