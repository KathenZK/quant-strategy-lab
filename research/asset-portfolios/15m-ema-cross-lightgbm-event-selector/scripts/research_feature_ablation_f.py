"""F-family supplement: volume-profile / 90d-momentum / VWAP features.

Implements the F half of specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md.
Adds 5 new expressions of existing 15m kline data to the local+trend set and
reruns the scoring variant. Persists the augmented pool for the later A run.
Family stays archived; 2026H1 untouched.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

import research_feature_ablation_a2 as a2
import research_feature_label_ablation as base

ec = __import__("emax_common")

OUT_DIR = ec.ARTIFACT_DIR / "af_supplement"
POOL_PATH = OUT_DIR / "pool_local_trend_f.parquet"

BARS_30D = 2880
BARS_90D = 8640

F_ALIGNED = ["ret_8640", "vwap_dist_30d", "vp_hvn_dist_30d"]
F_RAW = ["donchian_pos_90d", "vp_pos_30d"]
F_FEATURES = F_ALIGNED + F_RAW


def symbol_f_features(sym: str, rows: pd.DataFrame) -> pd.DataFrame:
    frame = ec.compute_indicators(ec.load_symbol_frame(sym))
    close, atr = frame["close"], frame["atr"]
    atr_frac = (atr / close).replace(0.0, np.nan)
    typ = (frame["high"] + frame["low"] + close) / 3.0
    vol = frame["volume"].astype(float)

    feats = pd.DataFrame(index=frame.index)
    feats["ret_8640"] = (close / close.shift(BARS_90D) - 1.0) / atr_frac
    high90 = frame["high"].rolling(BARS_90D, min_periods=BARS_90D // 2).max()
    low90 = frame["low"].rolling(BARS_90D, min_periods=BARS_90D // 2).min()
    feats["donchian_pos_90d"] = (close - low90) / (high90 - low90).replace(0.0, np.nan)
    pv = (typ * vol).rolling(BARS_30D, min_periods=BARS_30D // 2).sum()
    vv = vol.rolling(BARS_30D, min_periods=BARS_30D // 2).sum().replace(0.0, np.nan)
    feats["vwap_dist_30d"] = (close - pv / vv) / atr

    signal_idx = rows["signal_idx"].to_numpy()
    block = feats.iloc[signal_idx].reset_index(drop=True)

    # volume-profile position and HVN distance, event bars only
    typ_arr, vol_arr, close_arr, atr_arr = (
        typ.to_numpy(), vol.to_numpy(), close.to_numpy(), atr.to_numpy()
    )
    vp_pos = np.full(len(signal_idx), np.nan)
    hvn_dist = np.full(len(signal_idx), np.nan)
    for k, i in enumerate(signal_idx):
        lo = max(0, i - BARS_30D + 1)
        if i - lo + 1 < BARS_30D // 2:
            continue
        w, p = vol_arr[lo : i + 1], typ_arr[lo : i + 1]
        total = w.sum()
        if not np.isfinite(total) or total <= 0:
            continue
        vp_pos[k] = w[p <= close_arr[i]].sum() / total
        hist, edges = np.histogram(p, bins=50, weights=w)
        centre = 0.5 * (edges[hist.argmax()] + edges[hist.argmax() + 1])
        hvn_dist[k] = (close_arr[i] - centre) / atr_arr[i]
    block["vp_pos_30d"] = vp_pos
    block["vp_hvn_dist_30d"] = hvn_dist
    return block


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds = pd.read_parquet(ec.ARTIFACT_DIR / "event_dataset_dev.parquet")
    for col in ("entry_ts", "signal_ts"):
        ds[col] = pd.to_datetime(ds[col], utc=True)
    pool = ds.loc[ds["in_trading_pool"]].reset_index(drop=True)

    symbols = sorted(pool["sym_key"].unique())
    trend_blocks, f_blocks, order = [], [], []
    started = time.monotonic()
    for count, sym in enumerate(symbols, start=1):
        idx = pool.index[pool["sym_key"] == sym]
        rows = pool.loc[idx]
        trend_blocks.append(a2.symbol_trend_features(sym, rows["signal_ts"]))
        f_blocks.append(symbol_f_features(sym, rows).set_index(idx))
        order.append(pd.Series(idx))
        if count % 100 == 0 or count == len(symbols):
            print(f"features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)

    trend = pd.concat(trend_blocks).sort_index()
    ffeat = pd.concat(f_blocks).sort_index()
    for col in a2.NEW_ALIGNED:
        trend[col] = trend[col] * pool["side"]
    for col in F_ALIGNED:
        ffeat[col] = ffeat[col] * pool["side"]
    pool = pd.concat([pool, trend, ffeat], axis=1)
    nan_share = {c: round(float(pool[c].isna().mean()), 4) for c in F_FEATURES}
    print("F nan share:", nan_share)
    pool.to_parquet(POOL_PATH, index=False, compression="zstd")

    features = base.LOCAL_FEATURES + a2.NEW_FEATURES + F_FEATURES
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

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md",
        "variant": "local_trend_f",
        "n_features": len(features),
        "f_nan_share": nan_share,
        "result": result,
        "reference_a2": {"top_decile_net_atr": -0.1338, "top_decile_gross_atr": 0.1668},
    }
    out = OUT_DIR / "f_supplement_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "gate_a_ranking", "gate_b_monetizable", "passes_both")},
        ensure_ascii=False))
    print("F verdict passes_both:", result["passes_both"], "| report ->", out)


if __name__ == "__main__":
    main()
