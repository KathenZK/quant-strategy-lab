"""Port of the 15m local+trend LightGBM selector to 4h events.

Implements specs/bin-4h-emax-local-trend-selector-contract-2026-07-29.md.
Reuses the frozen events_dev_4h.parquet and the 15m feature modules
(bar-count windows unchanged; multi-day trend windows rescaled to 4h bars).
Family stays archived; diagnostic only.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector/scripts"))

import emax_features as ef  # noqa: E402
import research_feature_label_ablation as base  # noqa: E402
import run_baseline as rb  # noqa: E402  (this family's loaders)

TIMEFRAME = "4h"
BARS_7D = 42
BARS_30D = 180
PURGE_DAYS = 17
CLUSTER_FLOOR = "1D"
OUT_DIR = rb.ARTIFACT_DIR / "local_trend_selector"

TREND_ALIGNED = ["ret_7d", "ret_30d", "d1_gap_atr", "d1_price_to_slow"]
TREND_RAW = ["donchian_pos_30d", "dist_high_30d", "dist_low_30d"]
TREND_FEATURES = TREND_ALIGNED + TREND_RAW
REFERENCE_15M_A2 = {"top_decile_net_atr": -0.1338, "top_decile_gross_atr": 0.1668}


def trend_columns(frame: pd.DataFrame) -> pd.DataFrame:
    close, atr = frame["close"], frame["atr"]
    atr_frac = (atr / close).replace(0.0, np.nan)
    feats = pd.DataFrame(index=frame.index)
    feats["ret_7d"] = (close / close.shift(BARS_7D) - 1.0) / atr_frac
    feats["ret_30d"] = (close / close.shift(BARS_30D) - 1.0) / atr_frac
    high30 = frame["high"].rolling(BARS_30D, min_periods=BARS_30D // 2).max()
    low30 = frame["low"].rolling(BARS_30D, min_periods=BARS_30D // 2).min()
    feats["donchian_pos_30d"] = (close - low30) / (high30 - low30).replace(0.0, np.nan)
    feats["dist_high_30d"] = (high30 - close) / atr
    feats["dist_low_30d"] = (close - low30) / atr
    return feats


def daily_state(frame: pd.DataFrame) -> pd.DataFrame:
    daily = (
        frame.set_index("ts").resample("1D")
        .agg({"high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    prev_close = daily["close"].shift(1)
    tr = pd.concat(
        [daily["high"] - daily["low"], (daily["high"] - prev_close).abs(),
         (daily["low"] - prev_close).abs()], axis=1,
    ).max(axis=1)
    d_atr = tr.rolling(14, min_periods=14).mean()
    ema21 = daily["close"].ewm(span=21, adjust=False).mean()
    ema96 = daily["close"].ewm(span=96, adjust=False).mean()
    converged = pd.Series(np.arange(len(daily)) >= 96, index=daily.index)
    return pd.DataFrame(
        {
            "d1_gap_atr": ((ema21 - ema96) / d_atr).where(converged),
            "d1_price_to_slow": ((daily["close"] - ema96) / d_atr).where(converged),
        }
    ).shift(1)


def symbol_features(sym: str, rows: pd.DataFrame) -> pd.DataFrame:
    frame = ef.symbol_indicator_frame(rb.load_symbol_frame(sym))
    signal_idx = rows["signal_idx"].to_numpy()
    side = rows["side"].to_numpy()
    block = rows.reset_index(drop=True)

    for name, aligned in ef.SYMBOL_FEATURES.items():
        values = frame[name].to_numpy()[signal_idx]
        block[name] = values * side if aligned else values

    gap = frame["gap_atr"].to_numpy()
    block["gap_pre_atr"] = gap[np.maximum(signal_idx - 1, 0)] * side
    ec = sys.modules["emax_common"]
    all_cross = np.sort(np.concatenate(ec.detect_cross_indices(frame)))
    pos = np.searchsorted(all_cross, signal_idx, side="left")
    prev_cross = np.where(pos > 0, all_cross[np.maximum(pos - 1, 0)], -1)
    block["bars_since_prev_cross"] = np.where(prev_cross >= 0, signal_idx - prev_cross, np.nan)
    lo384 = np.searchsorted(all_cross, signal_idx - 384, side="left")
    block["crosses_384"] = (pos - lo384).astype(float)

    trend = trend_columns(frame)
    for col in TREND_ALIGNED[:2] + TREND_RAW:
        values = trend[col].to_numpy()[signal_idx]
        block[col] = values * side if col in TREND_ALIGNED else values

    d1 = daily_state(frame)
    days = pd.DatetimeIndex(frame["ts"].iloc[signal_idx]).normalize()
    for col in ("d1_gap_atr", "d1_price_to_slow"):
        block[col] = d1[col].reindex(days).to_numpy() * side
    return block


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = pd.read_parquet(rb.ARTIFACT_DIR / f"events_dev_{TIMEFRAME}.parquet")
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)

    bar_floor = events["entry_ts"].dt.floor(CLUSTER_FLOOR)
    cluster_n = events.groupby([bar_floor, events["side"]])["sym_key"].transform("size").astype(float)
    coin_n = events.groupby(["sym_key", "side"])["sym_key"].transform("size")
    raw_weight = 1.0 / (coin_n * cluster_n)
    events["weight"] = raw_weight * len(events) / raw_weight.sum()

    pool = events.loc[events["in_trading_pool"]].reset_index(drop=True)
    print(f"pool events: {len(pool)}, cost_atr mean: {pool['cost_atr'].mean():.4f}", flush=True)

    blocks = []
    symbols = sorted(pool["sym_key"].unique())
    started = time.monotonic()
    for count, sym in enumerate(symbols, start=1):
        blocks.append(symbol_features(sym, pool.loc[pool["sym_key"] == sym]))
        if count % 100 == 0 or count == len(symbols):
            print(f"features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)
    pool = pd.concat(blocks, ignore_index=True)

    features = base.LOCAL_FEATURES + TREND_FEATURES
    missing = [c for c in features if c not in pool.columns]
    if missing:
        raise RuntimeError(f"missing feature columns: {missing}")

    base.PURGE = pd.Timedelta(days=PURGE_DAYS)
    scores, top_imp = base.run_variant(pool, features, "abs")
    result = base.evaluate(pool, scores)
    result["top_feature_importance_gain"] = top_imp

    oof = pool.loc[scores.notna()].assign(score=scores.dropna())
    oof["year"] = oof["entry_ts"].dt.year
    oof["decile"] = (
        oof.groupby("year")["score"].rank(pct=True, method="first")
        .mul(10).apply(np.ceil).clip(1, 10).astype(int)
    )
    top = oof.loc[oof["decile"] == 10]
    result["top_decile_gross_atr"] = round(float(top["b4_2_gross_atr"].mean()), 4)
    result["top_decile_gross_by_year"] = {
        int(y): round(float(v), 4) for y, v in top.groupby("year")["b4_2_gross_atr"].mean().items()
    }
    result["top_decile_cost_atr"] = round(float(top["cost_atr"].mean()), 4)

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": f"specs/bin-{TIMEFRAME}-emax-local-trend-selector-contract-2026-07-29.md",
        "timeframe": TIMEFRAME,
        "pool_events": int(len(pool)),
        "cost_atr_mean": round(float(pool["cost_atr"].mean()), 4),
        "purge_days": PURGE_DAYS,
        "result": result,
        "reference_15m_a2": REFERENCE_15M_A2,
    }
    score_out = pool[["sym_key", "entry_ts", "side", base.LABEL_COL]].copy()
    score_out["score_local_trend"] = scores
    score_out.to_parquet(OUT_DIR / "oof_scores_local_trend.parquet", index=False)
    out = OUT_DIR / "local_trend_selector_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "top_decile_cost_atr",
        "gate_a_ranking", "gate_b_monetizable", "passes_both")}, ensure_ascii=False))
    print(f"{TIMEFRAME} verdict passes_both:", result["passes_both"], "| report ->", out)


if __name__ == "__main__":
    main()
