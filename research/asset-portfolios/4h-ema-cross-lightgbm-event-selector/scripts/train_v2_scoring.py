"""V2 scoring layer for BIN-4H-EMAX: expanding-window purged CV LightGBM.

Implements specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md exactly:
three-class (SL/TP/timeout) LightGBM on all eligible death-cross shorts,
validation years 2021..2025, purge = 16 days (96 x 4h label window),
cluster-downweighted samples, score = expected net ATR with train-fold
class-conditional means. All evaluation is out-of-fold, pool events only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_v2_dataset import ARTIFACT_DIR, BRACKET, feature_columns  # noqa: E402

VAL_YEARS = (2021, 2022, 2023, 2024, 2025)
PURGE = pd.Timedelta(days=16)
PARAMS = {
    "objective": "multiclass",
    "num_class": 3,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "max_depth": 6,
    "min_child_samples": 200,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.7,
    "reg_alpha": 1.0,
    "reg_lambda": 5.0,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}
N_ESTIMATORS = 2000
EARLY_STOP = 100


def rank_corr(x: np.ndarray, y: np.ndarray) -> float:
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    return float(np.corrcoef(rx, ry)[0, 1])


def decile_table(frame: pd.DataFrame) -> dict:
    deciles = pd.qcut(frame["score"], 10, labels=False, duplicates="drop")
    grouped = frame.groupby(deciles)["net_atr"].agg(["size", "mean"])
    return {
        f"d{int(d)}": {"events": int(row["size"]), "net_mean_atr": round(float(row["mean"]), 4)}
        for d, row in grouped.iterrows()
    }


def main() -> None:
    dataset = pd.read_parquet(ARTIFACT_DIR / "v2_dataset_short.parquet")
    dataset["entry_ts"] = pd.to_datetime(dataset["entry_ts"], utc=True)
    features = feature_columns()
    label_col = f"{BRACKET}_label"
    net_col = f"{BRACKET}_net_atr"

    weights_all = (1.0 / dataset["cross_count_same_ts"]).clip(0.05, 1.0)

    oof_rows: list[pd.DataFrame] = []
    fold_reports: dict[str, dict] = {}
    importance_acc: dict[str, float] = {}

    for year in VAL_YEARS:
        val_start = pd.Timestamp(f"{year}-01-01", tz="UTC")
        val_end = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
        train_mask = dataset["entry_ts"] <= val_start - PURGE
        val_mask = (dataset["entry_ts"] >= val_start) & (dataset["entry_ts"] < val_end)
        train = dataset.loc[train_mask]
        val = dataset.loc[val_mask]
        if train.empty or val.empty:
            continue

        # chronological tail of train as early-stopping set (never the val year)
        cut = train["entry_ts"].quantile(0.9)
        fit = train.loc[train["entry_ts"] < cut]
        stop = train.loc[train["entry_ts"] >= cut]

        model = lgb.LGBMClassifier(n_estimators=N_ESTIMATORS, **PARAMS)
        model.fit(
            fit[features],
            fit[label_col],
            sample_weight=weights_all.loc[fit.index],
            eval_set=[(stop[features], stop[label_col])],
            eval_sample_weight=[weights_all.loc[stop.index]],
            callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
        )
        best_iter = int(model.best_iteration_ or N_ESTIMATORS)

        m_class = train.groupby(label_col)[net_col].mean()
        proba = model.predict_proba(val[features])
        score = (
            proba[:, 1] * m_class.get(1, 0.0)
            + proba[:, 0] * m_class.get(0, 0.0)
            + proba[:, 2] * m_class.get(2, 0.0)
        )
        oof = val[["sym_key", "entry_ts", "in_trading_pool", label_col, net_col,
                   "atr_frac", f"{BRACKET}_exit_ts", f"{BRACKET}_net_frac"]].copy()
        oof["p_sl"] = proba[:, 0]
        oof["p_tp"] = proba[:, 1]
        oof["p_timeout"] = proba[:, 2]
        oof["score"] = score
        oof["fold_year"] = year
        oof_rows.append(oof)

        for name, gain in zip(features, model.booster_.feature_importance("gain")):
            importance_acc[name] = importance_acc.get(name, 0.0) + float(gain)

        pool_val = oof.loc[oof["in_trading_pool"]].rename(columns={net_col: "net_atr"})
        kept = pool_val.loc[pool_val["score"] > 0]
        fold_reports[str(year)] = {
            "train_events": int(len(train)),
            "val_pool_events": int(len(pool_val)),
            "best_iteration": best_iter,
            "class_means_train": {str(k): round(float(v), 4) for k, v in m_class.items()},
            "rank_corr_score_net": round(
                rank_corr(pool_val["score"].to_numpy(), pool_val["net_atr"].to_numpy()), 4
            ),
            "net_mean_all": round(float(pool_val["net_atr"].mean()), 4),
            "net_mean_score_gt0": round(float(kept["net_atr"].mean()), 4) if len(kept) else None,
            "kept_frac_score_gt0": round(float(len(kept) / len(pool_val)), 4),
            "deciles": decile_table(pool_val),
        }
        print(f"fold {year}: iters={best_iter} "
              f"rank_corr={fold_reports[str(year)]['rank_corr_score_net']} "
              f"all={fold_reports[str(year)]['net_mean_all']} "
              f"kept={fold_reports[str(year)]['net_mean_score_gt0']} "
              f"({fold_reports[str(year)]['kept_frac_score_gt0']})", flush=True)

    oof_all = pd.concat(oof_rows, ignore_index=True)
    oof_all.to_parquet(ARTIFACT_DIR / "v2_oof_scores.parquet", index=False, compression="zstd")

    pool_all = oof_all.loc[oof_all["in_trading_pool"]].rename(columns={net_col: "net_atr"})
    kept_all = pool_all.loc[pool_all["score"] > 0]
    overall = {
        "pool_events": int(len(pool_all)),
        "rank_corr_score_net": round(
            rank_corr(pool_all["score"].to_numpy(), pool_all["net_atr"].to_numpy()), 4
        ),
        "net_mean_all": round(float(pool_all["net_atr"].mean()), 4),
        "net_mean_score_gt0": round(float(kept_all["net_atr"].mean()), 4),
        "kept_frac_score_gt0": round(float(len(kept_all) / len(pool_all)), 4),
        "deciles": decile_table(pool_all),
    }

    top_features = dict(
        sorted(importance_acc.items(), key=lambda kv: kv[1], reverse=True)[:20]
    )
    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md",
        "params": PARAMS | {"n_estimators": N_ESTIMATORS, "early_stopping": EARLY_STOP},
        "overall_oof_pool": overall,
        "folds": fold_reports,
        "top20_feature_gain": {k: round(v, 1) for k, v in top_features.items()},
    }
    out = ARTIFACT_DIR / "v2_training_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(overall, indent=2))
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
