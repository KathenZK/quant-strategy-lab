from __future__ import annotations

import importlib.util
import itertools
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
ENTRY_PATH = FAMILY_DIR / "scripts/diagnose_pullback_entry_v0.py"
FEE = 0.001
RISK_FRACTION = 0.0025
MAX_EFFECTIVE_LEVERAGE = 3.0
INNER = {
    "BTC": (pd.Timestamp("2022-12-31 23:59:59", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-12-31 23:59:59", tz="UTC")),
    "ETH": (pd.Timestamp("2022-12-31 23:59:59", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-12-31 23:59:59", tz="UTC")),
    "HYPE": (pd.Timestamp("2025-08-31 23:59:59", tz="UTC"), pd.Timestamp("2025-09-01", tz="UTC"), pd.Timestamp("2025-10-31 23:59:59", tz="UTC")),
}


def load_entry() -> Any:
    spec = importlib.util.spec_from_file_location("bin_mtf_ptc_probe_search_shared", ENTRY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load entry module: {ENTRY_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fit_candidates(meter: Any, hourly: pd.DataFrame, onset: int, train_end: pd.Timestamp, start: pd.Timestamp, end: pd.Timestamp, quantile: float) -> pd.DataFrame:
    events = meter.build_events(hourly, onset)
    events["label"] = meter.label_events(events, hourly, 72)
    train = events.loc[(events.index <= train_end - pd.Timedelta(days=14)) & events["label"].notna()].copy()
    target = events.loc[(events.index >= start) & (events.index <= end - pd.Timedelta(hours=96))].copy()
    if len(train) < 100 or len(target) < 10:
        return pd.DataFrame()
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    model.fit(train[list(meter.FEATURES)], train["label"].astype(int))
    threshold = float(np.quantile(model.predict_proba(train[list(meter.FEATURES)])[:, 1], quantile))
    target["probability"] = model.predict_proba(target[list(meter.FEATURES)])[:, 1]
    return target.loc[target["probability"].ge(threshold)].copy()


def build_entries(entry: Any, candidates: pd.DataFrame, hourly: pd.DataFrame, bars15: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    atr = entry.hourly_atr(hourly)
    rows: list[dict[str, Any]] = []
    for ts, event in candidates.iterrows():
        side = int(event["direction"])
        entry_ts, fill, stop, reason = entry.find_pullback_entry(ts, side, hourly, bars15, atr, onset_hours=int(params["onset"]), min_atr=float(params["min_atr"]), max_retrace=float(params["max_retrace"]), restart_lookback=int(params["restart"]), stop_buffer_atr=float(params["stop_buffer"]))
        if entry_ts is not None and fill is not None and stop is not None:
            rows.append({"candidate_ts": ts, "entry_ts": entry_ts, "side": side, "fill": fill, "stop": stop, "probability": float(event["probability"]), "reason": reason})
    return pd.DataFrame(rows).sort_values("entry_ts") if rows else pd.DataFrame()


def run_probe(entry_module: Any, entries: pd.DataFrame, bars15: pd.DataFrame, funding: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame]:
    if entries.empty:
        return {"trades": 0, "total_return_pct": 0.0, "max_drawdown_pct": 0.0, "intrabar_max_drawdown_pct": 0.0, "mean_r": math.nan, "win_rate_pct": math.nan, "max_effective_leverage": 0.0, "max_stop_risk_pct": 0.0}, pd.DataFrame()
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    intrabar_max_dd = 0.0
    max_effective_leverage = 0.0
    max_stop_risk = 0.0
    unavailable_until = start - pd.Timedelta(minutes=15)
    rows: list[dict[str, Any]] = []
    funding_aligned = funding.reindex(bars15.index).fillna(0.0)
    for signal in entries.itertuples(index=False):
        if signal.entry_ts <= unavailable_until or signal.entry_ts < start or signal.entry_ts >= end:
            continue
        path_end = min(signal.entry_ts + pd.Timedelta(hours=336), end)
        path = bars15.loc[(bars15.index >= signal.entry_ts) & (bars15.index <= path_end)]
        if path.empty:
            continue
        side = int(signal.side)
        fill = float(signal.fill)
        stop = float(signal.stop)
        stop_fill = entry_module.adverse_fill(stop, -side)
        risk_per_unit = side * (fill - stop_fill) + FEE * (fill + stop_fill)
        if risk_per_unit <= 0:
            continue
        before = equity
        requested_quantity = before * RISK_FRACTION / risk_per_unit
        leverage_quantity = before * MAX_EFFECTIVE_LEVERAGE / fill
        quantity = min(requested_quantity, leverage_quantity)
        if quantity <= 0:
            continue
        effective_leverage = quantity * fill / before
        stop_risk_fraction = quantity * risk_per_unit / before
        max_effective_leverage = max(max_effective_leverage, effective_leverage)
        max_stop_risk = max(max_stop_risk, stop_risk_fraction)
        reached_one_r = False
        exit_ts = path.index[-1]
        exit_raw = float(path.iloc[-1]["close"])
        reason = "data_or_period_end"
        funding_pnl = 0.0
        r_price = abs(fill - stop)
        for bar_ts, bar in path.iterrows():
            elapsed = (bar_ts - signal.entry_ts) / pd.Timedelta(hours=1)
            # A position carried into this timestamp participates in the funding
            # settlement before any exit filled at this bar open. The entry bar
            # is excluded because the next-open entry follows that settlement.
            # Afterwards the
            # conservative event order is gap stop -> intrabar stop -> scheduled
            # validation/timeout. This prevents a scheduled exit from hiding a
            # worse same-bar stop fill.
            if bar_ts > signal.entry_ts:
                funding_pnl += -side * float(bar["open"]) * float(funding_aligned.loc[bar_ts])
            gap = float(bar["open"]) <= stop if side > 0 else float(bar["open"]) >= stop
            if gap:
                exit_ts, exit_raw, reason = bar_ts, float(bar["open"]), "stop_gap"
                break
            hit = float(bar["low"]) <= stop if side > 0 else float(bar["high"]) >= stop
            if hit:
                exit_ts, exit_raw, reason = bar_ts, stop, "stop_intrabar"
                break
            if elapsed >= 24 and not reached_one_r:
                exit_ts, exit_raw, reason = bar_ts, float(bar["open"]), "validation_failed_24h"
                break
            if elapsed >= 336:
                exit_ts, exit_raw, reason = bar_ts, float(bar["open"]), "timeout_336h"
                break
            favorable = float(bar["high"]) - fill if side > 0 else fill - float(bar["low"])
            reached_one_r = reached_one_r or favorable >= r_price
            close_liquidation = entry_module.adverse_fill(float(bar["close"]), -side)
            mark_equity = before + quantity * (side * (close_liquidation - fill) - FEE * (fill + close_liquidation) + funding_pnl)
            adverse_raw = float(bar["low"] if side > 0 else bar["high"])
            adverse_liquidation = entry_module.adverse_fill(adverse_raw, -side)
            adverse_equity = before + quantity * (side * (adverse_liquidation - fill) - FEE * (fill + adverse_liquidation) + funding_pnl)
            intrabar_max_dd = min(intrabar_max_dd, adverse_equity / peak - 1.0)
            peak = max(peak, mark_equity)
            max_dd = min(max_dd, mark_equity / peak - 1.0)
        exit_fill = entry_module.adverse_fill(exit_raw, -side)
        net_per_unit = side * (exit_fill - fill) - FEE * (fill + exit_fill) + funding_pnl
        net_r = net_per_unit / risk_per_unit
        equity = max(1e-9, before + quantity * net_per_unit)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        intrabar_max_dd = min(intrabar_max_dd, equity / peak - 1.0)
        rows.append({"entry_ts": signal.entry_ts, "exit_ts": exit_ts, "side": side, "entry": fill, "stop": stop, "exit": exit_fill, "quantity": quantity, "effective_leverage": effective_leverage, "stop_risk_pct": stop_risk_fraction * 100.0, "funding_pnl": quantity * funding_pnl, "fees": quantity * FEE * (fill + exit_fill), "holding_hours": (exit_ts - signal.entry_ts) / pd.Timedelta(hours=1), "reason": reason, "net_r": net_r, "net_pnl": quantity * net_per_unit, "equity_before": before, "equity_after": equity})
        unavailable_until = exit_ts
    ledger = pd.DataFrame(rows)
    return {"trades": int(len(ledger)), "total_return_pct": float((equity - 1.0) * 100.0), "max_drawdown_pct": float(max_dd * 100.0), "intrabar_max_drawdown_pct": float(intrabar_max_dd * 100.0), "mean_r": float(ledger["net_r"].mean()) if len(ledger) else math.nan, "win_rate_pct": float(ledger["net_r"].gt(0).mean() * 100.0) if len(ledger) else math.nan, "profit_factor_r": float(ledger.loc[ledger.net_r.gt(0), "net_r"].sum() / -ledger.loc[ledger.net_r.lt(0), "net_r"].sum()) if len(ledger) and ledger.loc[ledger.net_r.lt(0), "net_r"].sum() < 0 else math.nan, "max_effective_leverage": float(max_effective_leverage), "max_stop_risk_pct": float(max_stop_risk * 100.0)}, ledger


def parameter_sample() -> list[dict[str, Any]]:
    grid = [dict(zip(("onset", "quantile", "min_atr", "max_retrace", "restart", "stop_buffer"), values, strict=True)) for values in itertools.product((4, 12, 24), (0.60, 0.75, 0.90), (0.25, 0.50, 0.75), (0.40, 0.50, 0.60), (1, 2, 4), (0.25, 0.50, 1.00))]
    anchor = {"onset": 24, "quantile": 0.80, "min_atr": 0.50, "max_retrace": 0.50, "restart": 4, "stop_buffer": 0.25}
    rng = np.random.default_rng(20260803)
    chosen = rng.choice(len(grid), size=59, replace=False)
    return [anchor, *[grid[int(i)] for i in chosen]]


def main() -> None:
    global entry
    entry = load_entry()
    meter = entry.load_path(entry.METER_PATH, "bin_mtf_ptc_probe_search_meter")
    data_module = entry.load_path(entry.DATA_PATH, "bin_mtf_ptc_probe_search_data")
    hourly_frames, _ = meter.load_module().load_assets()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    search_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    validation_ledgers: list[pd.DataFrame] = []
    params_list = parameter_sample()
    for asset, symbol in entry.SYMBOLS.items():
        bars15, funding, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        train_end, inner_start, inner_end = INNER[asset]
        cache: dict[tuple[int, float], pd.DataFrame] = {}
        for params in params_list:
            key = (int(params["onset"]), float(params["quantile"]))
            if key not in cache:
                cache[key] = fit_candidates(meter, hourly, key[0], train_end, inner_start, inner_end, key[1])
            entries = build_entries(entry, cache[key], hourly, bars15, params)
            metrics, _ = run_probe(entry, entries, bars15, funding, inner_start, inner_end)
            search_rows.append({"asset": asset, **params, **metrics})
        asset_search = pd.DataFrame([row for row in search_rows if row["asset"] == asset])
        eligible = asset_search.loc[(asset_search["trades"] >= (8 if asset == "HYPE" else 15)) & asset_search["max_drawdown_pct"].ge(-20.0) & asset_search["intrabar_max_drawdown_pct"].ge(-20.0) & asset_search["max_effective_leverage"].le(MAX_EFFECTIVE_LEVERAGE + 1e-12) & asset_search["max_stop_risk_pct"].le(RISK_FRACTION * 100.0 + 1e-12)].copy()
        selected = eligible.sort_values(["total_return_pct", "mean_r"], ascending=False).iloc[0].to_dict() if not eligible.empty else asset_search.sort_values(["total_return_pct", "mean_r"], ascending=False).iloc[0].to_dict()
        dev_end, val_start, val_end = meter.SPLITS[asset]
        selected_params = {name: selected[name] for name in ("onset", "quantile", "min_atr", "max_retrace", "restart", "stop_buffer")}
        candidates = fit_candidates(meter, hourly, int(selected["onset"]), dev_end, val_start, val_end, float(selected["quantile"]))
        entries = build_entries(entry, candidates, hourly, bars15, selected_params)
        metrics, ledger = run_probe(entry, entries, bars15, funding, val_start, val_end)
        validation_rows.append({"asset": asset, **selected_params, "selection_inner_return_pct": selected["total_return_pct"], **metrics})
        if not ledger.empty:
            ledger.insert(0, "asset", asset)
            validation_ledgers.append(ledger)
    search = pd.DataFrame(search_rows)
    validation = pd.DataFrame(validation_rows)
    ledger = pd.concat(validation_ledgers, ignore_index=True) if validation_ledgers else pd.DataFrame()
    search.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_probe_search_v0_inner_2026-08-03.csv", index=False)
    validation.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_probe_search_v0_validation_2026-08-03.csv", index=False)
    ledger.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_probe_search_v0_validation_ledger_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_probe_search_v0_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "search_count_per_asset": len(params_list), "validation": validation.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("VALIDATION")
    print(validation.to_string(index=False))


if __name__ == "__main__":
    main()
