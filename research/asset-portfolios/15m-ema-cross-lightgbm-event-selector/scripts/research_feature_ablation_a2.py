"""Ablation addendum a2: LOCAL features + own multi-day trend context.

Implements specs/bin-15m-emax-feature-ablation-a2-addendum-2026-07-29.md.
Adds 7 pre-registered multi-day price-trend features (7d/30d momentum, 30d
range position, previous-day daily EMA21/96 state) to the LOCAL set and
reruns the local-only absolute-label variant under the identical protocol.
Family stays archived; 2026H1 untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import research_feature_label_ablation as base

ec = __import__("emax_common")

OUT_DIR = base.OUT_DIR
BARS_7D = 672
BARS_30D = 2880

NEW_ALIGNED = ["ret_672", "ret_2880", "d1_gap_atr", "d1_price_to_slow"]
NEW_RAW = ["donchian_pos_30d", "dist_high_30d", "dist_low_30d"]
NEW_FEATURES = NEW_ALIGNED + NEW_RAW


def symbol_trend_features(sym: str, signal_ts: pd.Series) -> pd.DataFrame:
    frame = ec.load_symbol_frame(sym)
    frame = ec.compute_indicators(frame)
    frame = frame.set_index("ts")
    close, atr = frame["close"], frame["atr"]
    atr_frac = (atr / close).replace(0.0, np.nan)

    feats = pd.DataFrame(index=frame.index)
    feats["ret_672"] = (close / close.shift(BARS_7D) - 1.0) / atr_frac
    feats["ret_2880"] = (close / close.shift(BARS_30D) - 1.0) / atr_frac
    high30 = frame["high"].rolling(BARS_30D, min_periods=BARS_30D // 2).max()
    low30 = frame["low"].rolling(BARS_30D, min_periods=BARS_30D // 2).min()
    span = (high30 - low30).replace(0.0, np.nan)
    feats["donchian_pos_30d"] = (close - low30) / span
    feats["dist_high_30d"] = (high30 - close) / atr
    feats["dist_low_30d"] = (close - low30) / atr

    # previous completed UTC day's daily EMA21/96 state (resampled from 15m)
    daily = frame.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    prev_close = daily["close"].shift(1)
    tr = pd.concat(
        [daily["high"] - daily["low"], (daily["high"] - prev_close).abs(),
         (daily["low"] - prev_close).abs()], axis=1,
    ).max(axis=1)
    d_atr = tr.rolling(14, min_periods=14).mean()
    ema21 = daily["close"].ewm(span=21, adjust=False).mean()
    ema96 = daily["close"].ewm(span=96, adjust=False).mean()
    converged = pd.Series(np.arange(len(daily)) >= 96, index=daily.index)
    d1 = pd.DataFrame(
        {
            "d1_gap_atr": ((ema21 - ema96) / d_atr).where(converged),
            "d1_price_to_slow": ((daily["close"] - ema96) / d_atr).where(converged),
        }
    ).shift(1)  # as-of previous completed day

    at_signal = feats.reindex(signal_ts)
    days = pd.DatetimeIndex(signal_ts).normalize()
    for col in d1.columns:
        at_signal[col] = d1[col].reindex(days).to_numpy()
    at_signal.index = signal_ts.index
    return at_signal


def main() -> None:
    ds = pd.read_parquet(base.ARTIFACT_DIR / "event_dataset_dev.parquet")
    ds["entry_ts"] = pd.to_datetime(ds["entry_ts"], utc=True)
    ds["signal_ts"] = pd.to_datetime(ds["signal_ts"], utc=True)
    pool = ds.loc[ds["in_trading_pool"]].reset_index(drop=True)

    blocks = []
    symbols = sorted(pool["sym_key"].unique())
    for count, sym in enumerate(symbols, start=1):
        idx = pool.index[pool["sym_key"] == sym]
        blocks.append(symbol_trend_features(sym, pool.loc[idx, "signal_ts"]))
        if count % 100 == 0:
            print(f"trend features {count}/{len(symbols)}", flush=True)
    trend = pd.concat(blocks).sort_index()
    assert len(trend) == len(pool)
    for col in NEW_ALIGNED:
        trend[col] = trend[col] * pool["side"]
    pool = pd.concat([pool, trend], axis=1)
    nan_share = {c: round(float(pool[c].isna().mean()), 4) for c in NEW_FEATURES}
    print("nan share:", nan_share)

    features = base.LOCAL_FEATURES + NEW_FEATURES
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

    prior = json.loads((OUT_DIR / "feature_ablation_report.json").read_text(encoding="utf-8"))
    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-feature-ablation-a2-addendum-2026-07-29.md",
        "variant": "a2_local_trend",
        "n_features": len(features),
        "new_feature_nan_share": nan_share,
        "result": result,
        "reference": {
            "a_local_abs": prior["variants"]["a_local_abs"]["top_decile_mean_net_atr"],
            "ref_full": prior["variants"]["ref"]["top_decile_mean_net_atr"],
        },
        "hypothesis_partially_confirmed": bool(result["passes_both"]),
    }
    score_out = pool[["sym_key", "entry_ts", "side", base.LABEL_COL]].copy()
    score_out["score_a2_local_trend"] = scores
    score_out.to_parquet(OUT_DIR / "oof_scores_a2.parquet", index=False)
    out = OUT_DIR / "feature_ablation_a2_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "gate_a_ranking", "gate_b_monetizable", "passes_both")},
        ensure_ascii=False))
    print("hypothesis_partially_confirmed:", report["hypothesis_partially_confirmed"],
          "| report ->", out)


if __name__ == "__main__":
    main()
