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
V0_PATH = FAMILY_DIR / "scripts/diagnose_pullback_entry_v0.py"
ONSETS = (4, 12)


def load_v0() -> Any:
    spec = importlib.util.spec_from_file_location("bin_mtf_ptc_pullback_v1_shared", V0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load V0: {V0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    v0 = load_v0()
    meter = v0.load_path(v0.METER_PATH, "bin_mtf_ptc_pullback_v1_meter")
    data_module = v0.load_path(v0.DATA_PATH, "bin_mtf_ptc_pullback_v1_data")
    hourly_frames, _ = meter.load_module().load_assets()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    rows: list[dict[str, Any]] = []
    for asset, symbol in v0.SYMBOLS.items():
        bars15, _, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        atr = v0.hourly_atr(hourly)
        for onset in ONSETS:
            events = meter.build_events(hourly, onset)
            events["label"] = meter.label_events(events, hourly, 72)
            dev_end, val_start, val_end = meter.SPLITS[asset]
            dev = events.loc[(events.index <= dev_end - pd.Timedelta(days=14)) & events["label"].notna()].copy()
            val = events.loc[(events.index >= val_start) & (events.index <= val_end - pd.Timedelta(hours=96))].copy()
            model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
            model.fit(dev[list(meter.FEATURES)], dev["label"].astype(int))
            threshold = float(np.quantile(model.predict_proba(dev[list(meter.FEATURES)])[:, 1], 0.80))
            val["probability"] = model.predict_proba(val[list(meter.FEATURES)])[:, 1]
            for ts, event in val.loc[val["probability"].ge(threshold)].iterrows():
                side = int(event["direction"])
                if ts not in bars15.index:
                    continue
                immediate_fill = v0.adverse_fill(float(bars15.loc[ts, "open"]), side)
                pullback_ts, pullback_fill, pullback_stop, reason = v0.find_pullback_entry(ts, side, hourly, bars15, atr, onset_hours=onset)
                immediate = v0.path_metrics(ts, immediate_fill, side, float(event["r_log"]), bars15)
                pullback = v0.path_metrics(pullback_ts, float(pullback_fill), side, float(event["r_log"]), bars15, stop=float(pullback_stop)) if pullback_ts is not None and pullback_fill is not None and pullback_stop is not None else {"complete": False}
                row: dict[str, Any] = {"asset": asset, "onset_hours": onset, "candidate_ts": ts, "side": side, "probability": float(event["probability"]), "pullback_status": reason}
                for prefix, values in (("immediate", immediate), ("pullback", pullback)):
                    for key, value in values.items():
                        row[f"{prefix}_{key}"] = value
                if pullback_fill is not None:
                    row["entry_improvement_pct"] = side * (immediate_fill - float(pullback_fill)) / immediate_fill * 100.0
                    row["structure_stop_distance_pct"] = abs(float(pullback_fill) - float(pullback_stop)) / float(pullback_fill) * 100.0
                rows.append(row)
    ledger = pd.DataFrame(rows)
    summaries: list[dict[str, Any]] = []
    for (asset, onset), part in ledger.groupby(["asset", "onset_hours"]):
        paired = part.loc[part["pullback_complete"].fillna(False)].copy()
        summaries.append({"asset": asset, "onset_hours": onset, "strong_candidates": int(len(part)), "pullback_entries": int(len(paired)), "entry_rate_pct": float(len(paired) / len(part) * 100.0), "median_entry_improvement_pct": float(paired["entry_improvement_pct"].median()) if len(paired) else math.nan, "median_structure_stop_distance_pct": float(paired["structure_stop_distance_pct"].median()) if len(paired) else math.nan, "immediate_success_rate_paired": float(paired["immediate_success_before_failure"].mean()) if len(paired) else math.nan, "pullback_success_rate": float(paired["pullback_success_before_failure"].mean()) if len(paired) else math.nan, "immediate_median_mae_r_paired": float(paired["immediate_mae_r"].median()) if len(paired) else math.nan, "pullback_median_mae_r": float(paired["pullback_mae_r"].median()) if len(paired) else math.nan, "immediate_median_mfe_r_paired": float(paired["immediate_mfe_r"].median()) if len(paired) else math.nan, "pullback_median_mfe_r": float(paired["pullback_mfe_r"].median()) if len(paired) else math.nan, "immediate_median_terminal_r_paired": float(paired["immediate_terminal_r"].median()) if len(paired) else math.nan, "pullback_median_terminal_r": float(paired["pullback_terminal_r"].median()) if len(paired) else math.nan})
    summary = pd.DataFrame(summaries)
    ledger.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_pullback_entry_v1_early_onset_ledger_2026-08-03.csv", index=False)
    summary.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_pullback_entry_v1_early_onset_summary_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_pullback_entry_v1_early_onset_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "summary": summary.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
