"""Signal-pair ablation: EMA30/120 vs the frozen EMA21/96 program.

Implements specs/bin-15m-emax-ema-pair-ablation-contract-2026-07-29.md.
Patches the frozen EMA constants to 30/120, re-extracts dev-window events with
the identical bracket/cost/universe machinery, then reruns the local+trend
scoring variant (a2 protocol). Family stays archived; 2026H1 untouched.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

import emax_common as ec

ec.EMA_FAST = 30
ec.EMA_SLOW = 120
ec.WARMUP_BARS = 4 * ec.EMA_SLOW

import emax_features as ef
import extract_cross_events as x
import research_feature_ablation_a2 as a2
import research_feature_label_ablation as base

OUT_DIR = ec.ARTIFACT_DIR / "ema_pair_ablation"
EVENTS_PATH = OUT_DIR / "events_dev_ema30_120.parquet"
BRACKET_NAMES = list(ec.BRACKETS)


def extract_events() -> pd.DataFrame:
    if EVENTS_PATH.exists():
        return pd.read_parquet(EVENTS_PATH)
    ec.ensure_symbol_partition_cache()
    daily = ec.build_daily_stats()
    universe = ec.build_universe(daily)
    funding_lookup = {
        key: ec.prepare_funding_lookup(group)
        for key, group in ec.load_funding().groupby("sym_key", sort=False)
    }
    symbols = ec.list_cached_symbols()
    frames: list[pd.DataFrame] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(
                x.extract_symbol,
                sym,
                universe.eligibility,
                funding_lookup,
                entry_cutoff=ec.DEV_ENTRY_CUTOFF,
                entry_floor=ec.DEV_START,
            ): sym
            for sym in symbols
        }
        for done, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if result is not None:
                frames.append(result)
            if done % 100 == 0 or done == len(futures):
                print(f"extract {done}/{len(futures)} ({time.monotonic() - started:.0f}s)", flush=True)
    events = pd.concat(frames, ignore_index=True).sort_values(["entry_ts", "sym_key"])
    events = events.reset_index(drop=True)
    events.to_parquet(EVENTS_PATH, index=False, compression="zstd")
    return events


def baseline_stats(events: pd.DataFrame) -> dict:
    pool = events.loc[events["in_trading_pool"]]
    year = pool["entry_ts"].dt.year
    out: dict = {
        "pool_events": int(len(pool)),
        "symbols": int(pool["sym_key"].nunique()),
        "cost_atr_mean": round(float(pool["cost_atr"].mean()), 4),
        "b4_2_holding_bars_median": float(pool["b4_2_holding_bars"].median()),
        "b4_2_timeout_share": round(float((pool["b4_2_label"] == 2).mean()), 4),
        "brackets": {},
    }
    for name in BRACKET_NAMES:
        out["brackets"][name] = {
            "gross_atr": round(float(pool[f"{name}_gross_atr"].mean()), 4),
            "net_atr": round(float(pool[f"{name}_net_atr"].mean()), 4),
            "net_atr_long": round(float(pool.loc[pool["side"] == 1, f"{name}_net_atr"].mean()), 4),
            "net_atr_short": round(float(pool.loc[pool["side"] == -1, f"{name}_net_atr"].mean()), 4),
            "net_atr_by_year": {
                int(y): round(float(v), 4)
                for y, v in pool.groupby(year)[f"{name}_net_atr"].mean().items()
            },
        }
    return out


def symbol_features(sym: str, rows: pd.DataFrame) -> pd.DataFrame:
    frame = ef.symbol_indicator_frame(ec.load_symbol_frame(sym))
    signal_idx = rows["signal_idx"].to_numpy()
    side = rows["side"].to_numpy()
    block = rows.reset_index(drop=True)

    for name, aligned in ef.SYMBOL_FEATURES.items():
        values = frame[name].to_numpy()[signal_idx]
        block[name] = values * side if aligned else values

    gap = frame["gap_atr"].to_numpy()
    block["gap_pre_atr"] = gap[np.maximum(signal_idx - 1, 0)] * side
    all_cross = np.sort(np.concatenate(ec.detect_cross_indices(frame)))
    pos = np.searchsorted(all_cross, signal_idx, side="left")
    prev_cross = np.where(pos > 0, all_cross[np.maximum(pos - 1, 0)], -1)
    block["bars_since_prev_cross"] = np.where(prev_cross >= 0, signal_idx - prev_cross, np.nan)
    lo384 = np.searchsorted(all_cross, signal_idx - 384, side="left")
    block["crosses_384"] = (pos - lo384).astype(float)

    # a2 multi-day trend features (daily EMA21/96 definitions unchanged)
    signal_ts = rows["signal_ts"].reset_index(drop=True)
    trend = a2.symbol_trend_features(sym, signal_ts)
    for col in a2.NEW_FEATURES:
        aligned = col in a2.NEW_ALIGNED
        block[col] = trend[col].to_numpy() * side if aligned else trend[col].to_numpy()
    return block


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = extract_events()
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    events["signal_ts"] = pd.to_datetime(events["signal_ts"], utc=True)
    new_base = baseline_stats(events)

    ref_events = pd.read_parquet(ec.ARTIFACT_DIR / "events_dev.parquet")
    ref_events["entry_ts"] = pd.to_datetime(ref_events["entry_ts"], utc=True)
    ref_base = baseline_stats(ref_events)
    print("baseline ema30_120:", json.dumps(new_base["brackets"]["b4_2"], ensure_ascii=False))
    print("baseline ema21_96 :", json.dumps(ref_base["brackets"]["b4_2"], ensure_ascii=False))

    # cluster weights on all eligible events (same algorithm as the dataset build)
    hour = events["entry_ts"].dt.floor("h")
    cluster_n = events.groupby([hour, events["side"]])["sym_key"].transform("size").astype(float)
    coin_n = events.groupby(["sym_key", "side"])["sym_key"].transform("size")
    raw_weight = 1.0 / (coin_n * cluster_n)
    events["weight"] = raw_weight * len(events) / raw_weight.sum()

    pool = events.loc[events["in_trading_pool"]].reset_index(drop=True)
    blocks = []
    symbols = sorted(pool["sym_key"].unique())
    started = time.monotonic()
    for count, sym in enumerate(symbols, start=1):
        blocks.append(symbol_features(sym, pool.loc[pool["sym_key"] == sym]))
        if count % 100 == 0 or count == len(symbols):
            print(f"features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)
    pool = pd.concat(blocks, ignore_index=True)

    features = base.LOCAL_FEATURES + a2.NEW_FEATURES
    missing = [c for c in features if c not in pool.columns]
    if missing:
        raise RuntimeError(f"missing feature columns: {missing}")
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

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-ema-pair-ablation-contract-2026-07-29.md",
        "signal": {"ema_fast": ec.EMA_FAST, "ema_slow": ec.EMA_SLOW, "warmup_bars": ec.WARMUP_BARS},
        "baseline_ema30_120": new_base,
        "baseline_ema21_96": ref_base,
        "scoring_local_trend": result,
        "reference_a2_ema21_96": {"top_decile_net_atr": -0.1338, "top_decile_gross_atr": 0.1668},
        "pair_changes_verdict": bool(result["passes_both"]),
    }
    score_out = pool[["sym_key", "entry_ts", "side", base.LABEL_COL]].copy()
    score_out["score_local_trend"] = scores
    score_out.to_parquet(OUT_DIR / "oof_scores_ema30_120.parquet", index=False)
    out = OUT_DIR / "ema_pair_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "gate_a_ranking", "gate_b_monetizable", "passes_both")},
        ensure_ascii=False))
    print("pair_changes_verdict:", report["pair_changes_verdict"], "| report ->", out)


if __name__ == "__main__":
    main()
