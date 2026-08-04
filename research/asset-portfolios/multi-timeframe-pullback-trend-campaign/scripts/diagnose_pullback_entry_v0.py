from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/multi-timeframe-pullback-trend-campaign"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
METER_PATH = FAMILY_DIR / "scripts/research_continuation_meter_v0.py"
DATA_PATH = ROOT / "research/hype/15m-multidimensional-trend-pyramiding/scripts/research_hype_15m_mdtp.py"
SYMBOLS = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "HYPE": "HYPE/USDT:USDT"}
SLIPPAGE = 0.0004


def load_path(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def hourly_atr(hourly: pd.DataFrame) -> pd.Series:
    previous = hourly["close"].shift(1)
    tr = pd.concat([(hourly["high"] - hourly["low"]), (hourly["high"] - previous).abs(), (hourly["low"] - previous).abs()], axis=1).max(axis=1)
    return tr.rolling(24, min_periods=24).mean()


def adverse_fill(price: float, side: int) -> float:
    return price * (1.0 + side * SLIPPAGE)


def find_pullback_entry(
    ts: pd.Timestamp,
    side: int,
    hourly: pd.DataFrame,
    bars15: pd.DataFrame,
    atr: pd.Series,
    onset_hours: int = 24,
    min_atr: float = 0.5,
    max_retrace: float = 0.5,
    wait_hours: int = 24,
    no_new_required: int = 2,
    restart_lookback: int = 4,
    stop_buffer_atr: float = 0.25,
) -> tuple[pd.Timestamp | None, float | None, float | None, str]:
    if ts not in hourly.index or ts - pd.Timedelta(hours=onset_hours) not in hourly.index:
        return None, None, None, "missing_origin"
    origin = float(hourly.loc[ts - pd.Timedelta(hours=onset_hours), "close"])
    candidate_close = float(hourly.loc[ts, "close"])
    atr_value = float(atr.loc[ts])
    if not np.isfinite(atr_value) or atr_value <= 0:
        return None, None, None, "missing_atr"
    expiry = ts + pd.Timedelta(hours=wait_hours)
    future_hourly = hourly.loc[(hourly.index > ts) & (hourly.index <= expiry)]
    running_extreme = candidate_close
    pullback_extreme = candidate_close
    armed_at: pd.Timestamp | None = None
    for hour_ts, row in future_hourly.iterrows():
        if side > 0 and float(row["close"]) <= origin:
            return None, None, None, "origin_invalidated"
        if side < 0 and float(row["close"]) >= origin:
            return None, None, None, "origin_invalidated"
        new_extreme = float(row["high"]) > running_extreme if side > 0 else float(row["low"]) < running_extreme
        if new_extreme:
            running_extreme = float(row["high"] if side > 0 else row["low"])
            pullback_extreme = float(row["close"])
            continue
        pullback_extreme = min(pullback_extreme, float(row["low"])) if side > 0 else max(pullback_extreme, float(row["high"]))
        depth = side * (running_extreme - pullback_extreme)
        leg = side * (running_extreme - origin)
        if leg <= 0:
            return None, None, None, "invalid_leg"
        if depth > max_retrace * leg:
            return None, None, None, "too_deep"
        if depth >= min_atr * atr_value:
            armed_at = hour_ts
            break
    if armed_at is None:
        return None, None, None, "no_valid_pullback"
    window = bars15.loc[(bars15.index >= armed_at) & (bars15.index < expiry)].copy()
    if len(window) < 6:
        return None, None, None, "no_restart_window"
    extreme = pullback_extreme
    no_new_count = 0
    previous: list[pd.Series] = []
    for bar_ts, row in window.iterrows():
        new_pullback_extreme = float(row["low"]) < extreme if side > 0 else float(row["high"]) > extreme
        if new_pullback_extreme:
            extreme = float(row["low"] if side > 0 else row["high"])
            no_new_count = 0
        else:
            no_new_count += 1
        leg = side * (running_extreme - origin)
        depth = side * (running_extreme - extreme)
        if leg <= 0 or depth > max_retrace * leg:
            return None, None, None, "too_deep_after_arm"
        if len(previous) >= restart_lookback and no_new_count >= no_new_required:
            reference = max(float(item["high"]) for item in previous[-restart_lookback:]) if side > 0 else min(float(item["low"]) for item in previous[-restart_lookback:])
            broken = float(row["close"]) > reference if side > 0 else float(row["close"]) < reference
            midpoint = 0.5 * (float(row["high"]) + float(row["low"]))
            half_ok = float(row["close"]) >= midpoint if side > 0 else float(row["close"]) <= midpoint
            if broken and half_ok:
                entry_ts = bar_ts + pd.Timedelta(minutes=15)
                if entry_ts in bars15.index:
                    fill = adverse_fill(float(bars15.loc[entry_ts, "open"]), side)
                    stop = extreme - side * stop_buffer_atr * atr_value
                    if side * (fill - stop) <= 0:
                        return None, None, None, "invalid_structure_stop"
                    return entry_ts, fill, stop, "entered"
        previous.append(row)
    return None, None, None, "no_restart"


def path_metrics(entry_ts: pd.Timestamp, fill: float, side: int, r_log: float, bars15: pd.DataFrame, hours: int = 72, stop: float | None = None) -> dict[str, Any]:
    path = bars15.loc[(bars15.index >= entry_ts) & (bars15.index < entry_ts + pd.Timedelta(hours=hours))]
    if len(path) < hours * 4:
        return {"complete": False}
    r_price = abs(fill - stop) if stop is not None else abs(fill - fill * math.exp(-side * r_log))
    favorable_barrier = fill + side * r_price
    adverse_barrier = fill - side * 0.5 * r_price
    outcome = math.nan
    for _, row in path.iterrows():
        success = float(row["high"]) >= favorable_barrier if side > 0 else float(row["low"]) <= favorable_barrier
        failure = float(row["low"]) <= adverse_barrier if side > 0 else float(row["high"]) >= adverse_barrier
        if failure:
            outcome = 0.0
            break
        if success:
            outcome = 1.0
            break
    favorable = (path["high"].max() - fill) if side > 0 else (fill - path["low"].min())
    adverse = (fill - path["low"].min()) if side > 0 else (path["high"].max() - fill)
    terminal = side * (float(path.iloc[-1]["close"]) - fill) / r_price
    return {"complete": True, "success_before_failure": outcome, "mfe_r": float(max(0.0, favorable) / r_price), "mae_r": float(max(0.0, adverse) / r_price), "terminal_r": float(terminal)}


def main() -> None:
    meter = load_path(METER_PATH, "bin_mtf_ptc_pullback_meter")
    data_module = load_path(DATA_PATH, "bin_mtf_ptc_pullback_data")
    hourly_frames, _ = meter.load_module().load_assets()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    rows: list[dict[str, Any]] = []
    for asset, symbol in SYMBOLS.items():
        bars15, _, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        events = meter.build_events(hourly, 24)
        events["label"] = meter.label_events(events, hourly, 72)
        dev_end, val_start, val_end = meter.SPLITS[asset]
        dev = events.loc[(events.index <= dev_end - pd.Timedelta(days=14)) & events["label"].notna()].copy()
        val = events.loc[(events.index >= val_start) & (events.index <= val_end - pd.Timedelta(hours=96))].copy()
        model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
        model.fit(dev[list(meter.FEATURES)], dev["label"].astype(int))
        dev_probability = model.predict_proba(dev[list(meter.FEATURES)])[:, 1]
        threshold = float(np.quantile(dev_probability, 0.80))
        val["probability"] = model.predict_proba(val[list(meter.FEATURES)])[:, 1]
        candidates = val.loc[val["probability"].ge(threshold)].copy()
        atr = hourly_atr(hourly)
        for ts, event in candidates.iterrows():
            side = int(event["direction"])
            immediate_ts = ts
            if immediate_ts not in bars15.index:
                continue
            immediate_fill = adverse_fill(float(bars15.loc[immediate_ts, "open"]), side)
            pullback_ts, pullback_fill, pullback_stop, reason = find_pullback_entry(ts, side, hourly, bars15, atr)
            immediate = path_metrics(immediate_ts, immediate_fill, side, float(event["r_log"]), bars15)
            pullback = path_metrics(pullback_ts, float(pullback_fill), side, float(event["r_log"]), bars15, stop=float(pullback_stop)) if pullback_ts is not None and pullback_fill is not None and pullback_stop is not None else {"complete": False}
            row = {"asset": asset, "candidate_ts": ts, "side": side, "probability": float(event["probability"]), "threshold": threshold, "pullback_status": reason, "immediate_ts": immediate_ts, "immediate_fill": immediate_fill, "pullback_ts": pullback_ts, "pullback_fill": pullback_fill, "pullback_stop": pullback_stop}
            for prefix, values in (("immediate", immediate), ("pullback", pullback)):
                for key, value in values.items():
                    row[f"{prefix}_{key}"] = value
            if pullback_fill is not None:
                row["entry_improvement_pct"] = side * (immediate_fill - pullback_fill) / immediate_fill * 100.0
                row["structure_stop_distance_pct"] = abs(float(pullback_fill) - float(pullback_stop)) / float(pullback_fill) * 100.0
            rows.append(row)
    ledger = pd.DataFrame(rows)
    summaries: list[dict[str, Any]] = []
    for asset, part in ledger.groupby("asset"):
        paired = part.loc[part["pullback_complete"].fillna(False)].copy()
        summaries.append({
            "asset": asset,
            "strong_candidates": int(len(part)),
            "pullback_entries": int(len(paired)),
            "entry_rate_pct": float(len(paired) / len(part) * 100.0) if len(part) else 0.0,
            "median_entry_improvement_pct": float(paired["entry_improvement_pct"].median()) if len(paired) else math.nan,
            "median_structure_stop_distance_pct": float(paired["structure_stop_distance_pct"].median()) if len(paired) else math.nan,
            "immediate_success_rate_paired": float(paired["immediate_success_before_failure"].mean()) if len(paired) else math.nan,
            "pullback_success_rate": float(paired["pullback_success_before_failure"].mean()) if len(paired) else math.nan,
            "immediate_median_mae_r_paired": float(paired["immediate_mae_r"].median()) if len(paired) else math.nan,
            "pullback_median_mae_r": float(paired["pullback_mae_r"].median()) if len(paired) else math.nan,
            "immediate_median_mfe_r_paired": float(paired["immediate_mfe_r"].median()) if len(paired) else math.nan,
            "pullback_median_mfe_r": float(paired["pullback_mfe_r"].median()) if len(paired) else math.nan,
            "immediate_median_terminal_r_paired": float(paired["immediate_terminal_r"].median()) if len(paired) else math.nan,
            "pullback_median_terminal_r": float(paired["pullback_terminal_r"].median()) if len(paired) else math.nan,
        })
    summary = pd.DataFrame(summaries)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_pullback_entry_v0_ledger_2026-08-03.csv", index=False)
    summary.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_pullback_entry_v0_summary_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_pullback_entry_v0_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "summary": summary.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(summary.to_string(index=False))
    print("\nSTATUS COUNTS")
    print(ledger.groupby(["asset", "pullback_status"]).size().to_string())


if __name__ == "__main__":
    main()
