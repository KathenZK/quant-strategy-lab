"""A-family supplement: OI / long-short positioning features -> 15m final verdict.

Implements the A half of specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md.
Joins Binance Vision USDM metrics (explore-grade lake ingestion) onto the
persisted local+trend+F pool and reruns the scoring variant with all four
feature families. Family stays archived; 2026H1 untouched.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

import research_feature_ablation_a2 as a2
import research_feature_ablation_f as fmod
import research_feature_label_ablation as base

ec = __import__("emax_common")

OUT_DIR = ec.ARTIFACT_DIR / "af_supplement"
LAKE_ROOT = (
    ec.ROOT
    / "data/normalized/derivatives_metrics/exchange=binance/market_type=perp"
    / "timeframe=5m/source=binance_vision_daily"
)
STALE = pd.Timedelta(hours=6)
LAGS = {"oi_chg_24h": pd.Timedelta(hours=24), "oi_chg_3d": pd.Timedelta(days=3),
        "oi_chg_7d": pd.Timedelta(days=7)}
A_FEATURES = [
    "oi_chg_24h", "oi_chg_3d", "oi_chg_7d", "oi_value_to_adv",
    "ls_top_pos", "ls_top_acct", "ls_global_acct", "taker_ls_vol",
]


def load_metrics(symbol: str) -> pd.DataFrame | None:
    files = sorted(LAKE_ROOT.glob(f"month=*/{symbol}.parquet"))
    if not files:
        return None
    frame = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    return frame.sort_values("ts").reset_index(drop=True)


def asof_values(mts: np.ndarray, values: np.ndarray, at: np.ndarray) -> np.ndarray:
    idx = np.searchsorted(mts, at, side="right") - 1
    ok = idx >= 0
    out = np.full(len(at), np.nan)
    take = np.maximum(idx, 0)
    fresh = ok & ((at - mts[take]) <= STALE.to_timedelta64())
    out[fresh] = values[take[fresh]]
    return out


def symbol_a_features(sym: str, rows: pd.DataFrame) -> pd.DataFrame:
    block = pd.DataFrame(index=rows.index, columns=A_FEATURES, dtype=float)
    metrics = load_metrics(sym + "USDT")
    if metrics is None or metrics.empty:
        return block
    mts = metrics["ts"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
    at = rows["signal_ts"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")

    oi = metrics["sum_open_interest"].to_numpy(dtype=float)
    oi_now = asof_values(mts, oi, at)
    for name, lag in LAGS.items():
        oi_lag = asof_values(mts, oi, at - lag.to_timedelta64())
        with np.errstate(divide="ignore", invalid="ignore"):
            block[name] = np.where(oi_lag > 0, oi_now / oi_lag - 1.0, np.nan)
    oi_value = asof_values(mts, metrics["sum_open_interest_value"].to_numpy(dtype=float), at)
    adv = rows["adv_30d"].to_numpy(dtype=float)
    block["oi_value_to_adv"] = np.where(adv > 0, oi_value / adv, np.nan)
    for feature, column in (
        ("ls_top_pos", "sum_toptrader_long_short_ratio"),
        ("ls_top_acct", "count_toptrader_long_short_ratio"),
        ("ls_global_acct", "count_long_short_ratio"),
        ("taker_ls_vol", "sum_taker_long_short_vol_ratio"),
    ):
        block[feature] = asof_values(mts, metrics[column].to_numpy(dtype=float), at)
    return block


def main() -> None:
    pool = pd.read_parquet(fmod.POOL_PATH)
    for col in ("entry_ts", "signal_ts"):
        pool[col] = pd.to_datetime(pool[col], utc=True)

    blocks = []
    symbols = sorted(pool["sym_key"].unique())
    started = time.monotonic()
    for count, sym in enumerate(symbols, start=1):
        idx = pool.index[pool["sym_key"] == sym]
        blocks.append(symbol_a_features(sym, pool.loc[idx]))
        if count % 100 == 0 or count == len(symbols):
            print(f"A features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)
    a_block = pd.concat(blocks).sort_index()
    pool = pd.concat([pool, a_block], axis=1)

    nan_share = {c: round(float(pool[c].isna().mean()), 4) for c in A_FEATURES}
    year = pool["entry_ts"].dt.year
    coverage_by_year = {
        int(y): round(float(v), 4)
        for y, v in pool["oi_chg_24h"].notna().groupby(year).mean().items()
    }
    print("A nan share:", nan_share)
    print("oi coverage by year:", coverage_by_year)

    features = base.LOCAL_FEATURES + a2.NEW_FEATURES + fmod.F_FEATURES + A_FEATURES
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
        "variant": "local_trend_f_a",
        "n_features": len(features),
        "a_nan_share": nan_share,
        "oi_coverage_by_year": coverage_by_year,
        "result": result,
        "reference": {
            "a2_local_trend": {"net": -0.1338, "gross": 0.1668},
            "local_trend_f": {"net": -0.1443, "gross": 0.158},
        },
    }
    out = OUT_DIR / "a_supplement_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    score_out = pool[["sym_key", "entry_ts", "side", base.LABEL_COL]].copy()
    score_out["score_local_trend_f_a"] = scores
    score_out.to_parquet(OUT_DIR / "oof_scores_a.parquet", index=False)
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "gate_a_ranking", "gate_b_monetizable", "passes_both")},
        ensure_ascii=False))
    print("15m FINAL verdict passes_both:", result["passes_both"], "| report ->", out)


if __name__ == "__main__":
    main()
