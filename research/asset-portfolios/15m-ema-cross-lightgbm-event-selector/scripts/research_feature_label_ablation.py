"""Feature/label 2x2 ablation for the archived BIN-15M-EMAX family.

Implements specs/bin-15m-emax-feature-ablation-contract-2026-07-29.md.
Tests whether LOCAL pattern features alone (cross geometry + own price/vol/
volume) support an out-of-fold, cost-inclusive decile spread — the user's
"the features were the problem" hypothesis. Family stays archived; no
promotion path; the revealed 2026H1 window is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
OUT_DIR = ARTIFACT_DIR / "feature_ablation"

LABEL_COL = "b4_2_net_atr"
PURGE = pd.Timedelta(days=2)
OOF_YEARS = (2022, 2023, 2024, 2025)
MIN_GROUP = 8
SEED = 42

LOCAL_FEATURES = [
    "side",
    # cross geometry
    "gap_atr", "fast_slope_4", "fast_slope_16", "slow_slope_16", "slow_slope_96",
    "slope_diff_16", "entangle_96", "gap_pre_atr", "bars_since_prev_cross", "crosses_384",
    # own price / trend
    "price_to_fast_atr", "price_to_slow_atr", "ret_1", "ret_4", "ret_8", "ret_16",
    "ret_32", "ret_96", "adx_14", "efficiency_96", "dist_high_24h", "dist_low_24h",
    "donchian_pos_96", "color_run",
    # own volatility
    "atr_frac", "rv_ratio", "bb_width_atr", "atr_pos_30d", "tr_over_atr",
    # own volume / liquidity
    "vol_z_96", "vol_ratio_4_24", "qv_rel_30d", "taker_bias", "tc_z_96", "impact_rel_96",
    "cost_atr",
]
MARKET_FEATURES = [
    "beta_btc_30d", "corr_btc_30d", "btc_ret_16", "btc_ret_96", "btc_gap_atr",
    "btc_atr_frac", "btc_rv_ratio",
    "csd_24h", "universe_count", "breadth_up_bias", "breadth_above_slow_bias",
    "rel_strength_24h", "mkt_funding_mean",
    "funding_last", "funding_avg_3d", "funding_avg_7d", "funding_pos_30d",
    "bars_to_next_funding",
    "adv_30d", "adv_rank_pct", "listing_age_log", "vol_rank_pct",
    "hour_sin", "hour_cos", "day_of_week",
    "cross_count_1h_same_side", "cross_ratio_24h_same_side",
]
FULL_FEATURES = LOCAL_FEATURES + MARKET_FEATURES

LGB_PARAMS = dict(
    n_estimators=800, learning_rate=0.02, num_leaves=31, max_depth=6,
    min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
    reg_alpha=1.0, reg_lambda=5.0, random_state=SEED, n_jobs=-1, verbosity=-1,
)

VARIANTS = {
    "ref": {"features": FULL_FEATURES, "label": "abs"},
    "a_local_abs": {"features": LOCAL_FEATURES, "label": "abs"},
    "b_full_rel": {"features": FULL_FEATURES, "label": "rel"},
    "c_local_rel": {"features": LOCAL_FEATURES, "label": "rel"},
}


def add_relative_label(pool: pd.DataFrame) -> pd.DataFrame:
    day = pool["entry_ts"].dt.tz_convert("UTC").dt.normalize()
    group = pool.groupby([day, pool["side"]])[LABEL_COL]
    pool = pool.assign(
        rel_label=group.rank(pct=True, method="average"),
        group_size=group.transform("size"),
    )
    return pool


def run_variant(pool: pd.DataFrame, features: list[str], label_kind: str) -> tuple[pd.Series, dict]:
    scores = pd.Series(np.nan, index=pool.index)
    importances: dict[str, float] = {}
    for year in OOF_YEARS:
        cutoff = pd.Timestamp(f"{year}-01-01", tz="UTC")
        train = pool.loc[pool["entry_ts"] < cutoff - PURGE]
        test_idx = pool.index[pool["entry_ts"].dt.year == year]
        if label_kind == "rel":
            train = train.loc[train["group_size"] >= MIN_GROUP]
            y = train["rel_label"]
        else:
            y = train[LABEL_COL]
        model = lgb.LGBMRegressor(**LGB_PARAMS)
        model.fit(train[features], y, sample_weight=train["weight"])
        scores.loc[test_idx] = model.predict(pool.loc[test_idx, features])
        gain = pd.Series(
            model.booster_.feature_importance(importance_type="gain"), index=features
        )
        for name, value in gain.items():
            importances[name] = importances.get(name, 0.0) + float(value)
    top_imp = dict(sorted(importances.items(), key=lambda kv: -kv[1])[:15])
    total = sum(importances.values())
    return scores, {k: round(v / total, 4) for k, v in top_imp.items()}


def evaluate(pool: pd.DataFrame, scores: pd.Series) -> dict:
    oof = pool.loc[scores.notna()].assign(score=scores.dropna())
    oof["year"] = oof["entry_ts"].dt.year
    oof["decile"] = (
        oof.groupby("year")["score"].rank(pct=True, method="first")
        .mul(10).apply(np.ceil).clip(1, 10).astype(int)
    )
    decile_mean = oof.groupby("decile")[LABEL_COL].mean()
    rho = float(spearmanr(decile_mean.index, decile_mean.to_numpy()).statistic)
    top = oof.loc[oof["decile"] == 10]
    top_by_year = top.groupby("year")[LABEL_COL].mean()
    gate_a = bool(rho > 0.8)
    gate_b = bool(top[LABEL_COL].mean() > 0 and (top_by_year > 0).sum() >= 3)
    return {
        "decile_mean_net_atr": {int(k): round(float(v), 4) for k, v in decile_mean.items()},
        "decile_spearman": round(rho, 3),
        "top_decile_mean_net_atr": round(float(top[LABEL_COL].mean()), 4),
        "top_decile_by_year": {int(y): round(float(v), 4) for y, v in top_by_year.items()},
        "top_decile_events": int(len(top)),
        "top_decile_share_long": round(float((top["side"] == 1).mean()), 3),
        "gate_a_ranking": gate_a,
        "gate_b_monetizable": gate_b,
        "passes_both": bool(gate_a and gate_b),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds = pd.read_parquet(ARTIFACT_DIR / "event_dataset_dev.parquet")
    ds["entry_ts"] = pd.to_datetime(ds["entry_ts"], utc=True)
    pool = ds.loc[ds["in_trading_pool"]].reset_index(drop=True)
    pool = add_relative_label(pool)
    missing = [c for c in FULL_FEATURES if c not in pool.columns]
    if missing:
        raise RuntimeError(f"missing feature columns: {missing}")

    report: dict = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-feature-ablation-contract-2026-07-29.md",
        "pool_events": int(len(pool)),
        "n_local_features": len(LOCAL_FEATURES),
        "n_full_features": len(FULL_FEATURES),
        "variants": {},
    }
    score_frame = pool[["sym_key", "entry_ts", "side", LABEL_COL]].copy()
    for name, cfg in VARIANTS.items():
        scores, top_imp = run_variant(pool, cfg["features"], cfg["label"])
        result = evaluate(pool, scores)
        result["top_feature_importance_gain"] = top_imp
        report["variants"][name] = result
        score_frame[f"score_{name}"] = scores
        print(name, json.dumps({k: result[k] for k in (
            "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
            "gate_a_ranking", "gate_b_monetizable", "passes_both")}, ensure_ascii=False))

    hypothesis = bool(
        report["variants"]["a_local_abs"]["passes_both"]
        or report["variants"]["c_local_rel"]["passes_both"]
    )
    report["feature_hypothesis_confirmed"] = hypothesis
    score_frame.to_parquet(OUT_DIR / "oof_scores_ablation.parquet", index=False)
    out = OUT_DIR / "feature_ablation_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("feature_hypothesis_confirmed:", hypothesis, "| report ->", out)


if __name__ == "__main__":
    main()
