"""K-family candle-morphology supplement on the 4h local+trend selector.

Implements specs/bin-4h-emax-k-candle-supplement-contract-2026-07-29.md.
Reuses the local+trend feature block from research_local_trend_selector and
the 18 K features from the 15m family's research_feature_ablation_k.
Family stays archived; diagnostic only.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

import research_local_trend_selector as port

# port already put the 15m scripts dir on sys.path
import research_feature_ablation_k as kmod  # noqa: E402
import research_feature_label_ablation as base  # noqa: E402
import emax_common as ec  # noqa: E402
import run_baseline as rb  # noqa: E402

OUT_DIR = rb.ARTIFACT_DIR / "k_candle_supplement"
REFERENCE_LOCAL_TREND = {"top_decile_net_atr": 0.3673, "top_decile_gross_atr": 0.4674}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = pd.read_parquet(rb.ARTIFACT_DIR / f"events_dev_{port.TIMEFRAME}.parquet")
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)

    bar_floor = events["entry_ts"].dt.floor(port.CLUSTER_FLOOR)
    cluster_n = events.groupby([bar_floor, events["side"]])["sym_key"].transform("size").astype(float)
    coin_n = events.groupby(["sym_key", "side"])["sym_key"].transform("size")
    raw_weight = 1.0 / (coin_n * cluster_n)
    events["weight"] = raw_weight * len(events) / raw_weight.sum()

    pool = events.loc[events["in_trading_pool"]].reset_index(drop=True)
    blocks = []
    symbols = sorted(pool["sym_key"].unique())
    started = time.monotonic()
    for count, sym in enumerate(symbols, start=1):
        rows = pool.loc[pool["sym_key"] == sym]
        block = port.symbol_features(sym, rows)
        frame = ec.compute_indicators(rb.load_symbol_frame(sym))
        kblock = kmod.k_candle_features(frame, rows)
        blocks.append(pd.concat([block, kblock.set_index(block.index)], axis=1))
        if count % 100 == 0 or count == len(symbols):
            print(f"features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)
    pool = pd.concat(blocks, ignore_index=True)
    nan_share = {c: round(float(pool[c].isna().mean()), 4) for c in kmod.K_FEATURES}
    print("K nan share:", nan_share)

    features = base.LOCAL_FEATURES + port.TREND_FEATURES + kmod.K_FEATURES
    missing = [c for c in features if c not in pool.columns]
    if missing:
        raise RuntimeError(f"missing feature columns: {missing}")

    base.PURGE = pd.Timedelta(days=port.PURGE_DAYS)
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
    result["top_decile_cost_atr"] = round(float(top["cost_atr"].mean()), 4)

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-4h-emax-k-candle-supplement-contract-2026-07-29.md",
        "variant": "local_trend_k",
        "timeframe": port.TIMEFRAME,
        "pool_events": int(len(pool)),
        "n_features": len(features),
        "k_nan_share": nan_share,
        "result": result,
        "reference_local_trend": REFERENCE_LOCAL_TREND,
    }
    out = OUT_DIR / "k_supplement_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "gate_a_ranking", "gate_b_monetizable", "passes_both")},
        ensure_ascii=False))
    print("4h K verdict passes_both:", result["passes_both"], "| report ->", out)


if __name__ == "__main__":
    main()
