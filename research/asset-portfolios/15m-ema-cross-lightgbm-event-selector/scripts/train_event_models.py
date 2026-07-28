"""Phase 3 for BIN-15M-EMAX-LGBM: per-side LightGBM, walk-forward OOF, diagnostics.

Walk-forward expanding folds over the development window with a 2-day embargo.
Per side: 3-class LightGBM with per-class isotonic calibration fitted on the
chronological tail of the training window. Produces out-of-fold scores for the
portfolio backtest, decile-lift diagnostics, a leave-coin-out battery, and
final full-development models for the later freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import joblib
import lightgbm
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.isotonic import IsotonicRegression

import emax_common as ec
import emax_features as ef


EMBARGO = pd.Timedelta(days=2)
FOLDS = 6
CALIB_TAIL = 0.15
LEAVE_OUT_COINS = ["SOL", "DOGE", "AVAX", "SUI", "HYPE"]

LGBM_PARAMS = dict(
    objective="multiclass",
    num_class=3,
    n_estimators=3000,
    learning_rate=0.02,
    num_leaves=31,
    max_depth=6,
    min_child_samples=300,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.7,
    reg_alpha=1.0,
    reg_lambda=5.0,
    random_state=42,
    n_jobs=-1,
    verbosity=-1,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ec.ARTIFACT_DIR / "event_dataset_dev.parquet"
    )
    parser.add_argument(
        "--baseline", type=Path, default=ec.ARTIFACT_DIR / "baseline_a_report.json"
    )
    parser.add_argument("--output-dir", type=Path, default=ec.ARTIFACT_DIR / "model_v1")
    parser.add_argument("--skip-leave-out", action="store_true")
    return parser.parse_args()


def feature_columns() -> list[str]:
    return (
        list(ef.SYMBOL_FEATURES)
        + ef.EVENT_LEVEL_FEATURES
        + ["beta_btc_30d", "corr_btc_30d"]
        + ef.MARKET_FEATURES_ALIGNED
        + ef.MARKET_FEATURES_RAW
    )


CalibratedModel = ec.CalibratedModel


def fit_side_model(
    train: pd.DataFrame, features: list[str], label_column: str
) -> tuple[CalibratedModel, float]:
    """Fit on the chronological head, early-stop and calibrate on the tail."""
    train = train.sort_values("entry_ts").copy()
    # cap extreme weights from very-low-event coins (winsorize at 50x median)
    cap = 50.0 * float(train["weight"].median())
    train["weight"] = train["weight"].clip(upper=cap)
    cut = int(len(train) * (1.0 - CALIB_TAIL))
    cut_ts = train["entry_ts"].iloc[cut]
    head = train.loc[train["entry_ts"] <= cut_ts - EMBARGO]
    tail = train.loc[train["entry_ts"] > cut_ts]
    model = LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        head[features],
        head[label_column],
        sample_weight=head["weight"],
        eval_set=[(tail[features], tail[label_column])],
        eval_sample_weight=[tail["weight"]],
        callbacks=[lightgbm.early_stopping(100, verbose=False)],
    )
    raw = model.predict_proba(tail[features])
    calibrators: list[IsotonicRegression | None] = []
    for k in range(3):
        target = (tail[label_column] == k).astype(float)
        if target.nunique() < 2:
            calibrators.append(None)
            continue
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(raw[:, k], target, sample_weight=tail["weight"])
        calibrators.append(iso)
    timeout_rows = head.loc[
        (head[label_column] == 2) & head["timeout_gross_atr"].notna()
    ]
    timeout_mean = (
        float(np.average(timeout_rows["timeout_gross_atr"], weights=timeout_rows["weight"]))
        if len(timeout_rows)
        else 0.0
    )
    return CalibratedModel(model, calibrators), timeout_mean


def score_events(
    model: CalibratedModel,
    events: pd.DataFrame,
    features: list[str],
    k_tp: float,
    k_sl: float,
    timeout_mean: float,
) -> pd.DataFrame:
    proba = model.predict_proba(events[features])
    score = (
        proba[:, 1] * k_tp
        - proba[:, 0] * k_sl
        + proba[:, 2] * timeout_mean
        - events["cost_atr"].to_numpy()
    )
    return pd.DataFrame(
        {
            "p_sl": proba[:, 0],
            "p_tp": proba[:, 1],
            "p_timeout": proba[:, 2],
            "score": score,
        },
        index=events.index,
    )


def decile_lift(valid: pd.DataFrame, net_column: str) -> dict:
    deciles = pd.qcut(valid["score"], 10, labels=False, duplicates="drop")
    table = valid.groupby(deciles)[net_column].agg(["mean", "count"])
    top = valid.loc[deciles == deciles.max(), net_column]
    return {
        "all_mean_net_atr": float(valid[net_column].mean()),
        "top_decile_mean_net_atr": float(top.mean()),
        "top_decile_share_positive": float((top > 0).mean()),
        "top_decile_events": int(len(top)),
        "decile_means": {str(int(k)): float(v) for k, v in table["mean"].items()},
        "rank_ic": float(valid["score"].corr(valid[net_column], method="spearman")),
    }


def main() -> None:
    args = parse_args()
    dataset = pd.read_parquet(args.dataset)
    dataset["entry_ts"] = pd.to_datetime(dataset["entry_ts"], utc=True)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    bracket = baseline["bracket_selection"]["chosen"]
    k_tp, k_sl = ec.BRACKETS[bracket]
    label_column = f"{bracket}_label"
    net_column = f"{bracket}_net_atr"
    dataset["timeout_gross_atr"] = np.where(
        dataset[label_column] == 2, dataset[f"{bracket}_gross_atr"], np.nan
    )
    features = feature_columns()
    print(f"bracket={bracket} (TP {k_tp} / SL {k_sl}), rows={len(dataset)}", flush=True)

    edges = pd.date_range(
        dataset["entry_ts"].min().floor("D"),
        dataset["entry_ts"].max().ceil("D"),
        periods=FOLDS + 1,
    )
    report: dict = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "bracket": bracket,
        "folds": [str(edge) for edge in edges],
        "params": {k: str(v) for k, v in LGBM_PARAMS.items()},
        "features": features,
        "per_fold": {},
    }
    oof_parts: list[pd.DataFrame] = []
    started = time.monotonic()
    for fold in range(1, FOLDS):
        fold_start, fold_end = edges[fold], edges[fold + 1]
        for side in (1, -1):
            side_data = dataset.loc[dataset["side"] == side]
            train = side_data.loc[side_data["entry_ts"] < fold_start - EMBARGO]
            valid = side_data.loc[
                (side_data["entry_ts"] >= fold_start) & (side_data["entry_ts"] < fold_end)
            ].copy()
            if len(train) < 5000 or len(valid) < 500:
                continue
            model, timeout_mean = fit_side_model(train, features, label_column)
            scored = score_events(model, valid, features, k_tp, k_sl, timeout_mean)
            valid = pd.concat([valid, scored], axis=1)
            valid["fold"] = fold
            oof_parts.append(
                valid[
                    [
                        "sym_key", "side", "entry_ts", "signal_ts", "fold",
                        "in_trading_pool", "cost_atr", "atr_frac", "adv_30d",
                        "p_sl", "p_tp", "p_timeout", "score",
                        label_column, net_column, f"{bracket}_holding_bars",
                        f"{bracket}_exit_ts", f"{bracket}_gross_atr",
                        f"{bracket}_funding_frac", "weight",
                    ]
                ]
            )
            key = f"fold{fold}_side{side}"
            report["per_fold"][key] = {
                "train_events": int(len(train)),
                "valid_events": int(len(valid)),
                "best_iteration": int(model.model.best_iteration_ or 0),
                "timeout_mean_atr": timeout_mean,
                "lift_all": decile_lift(valid, net_column),
                "lift_trading_pool": decile_lift(
                    valid.loc[valid["in_trading_pool"]], net_column
                ),
            }
            print(
                f"fold {fold} side {side}: train={len(train)} valid={len(valid)} "
                f"top_decile={report['per_fold'][key]['lift_trading_pool']['top_decile_mean_net_atr']:.4f} "
                f"all={report['per_fold'][key]['lift_trading_pool']['all_mean_net_atr']:.4f} "
                f"({time.monotonic() - started:.0f}s)",
                flush=True,
            )

    oof = pd.concat(oof_parts, ignore_index=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    oof_path = args.output_dir / "oof_scores.parquet"
    oof.to_parquet(oof_path, index=False, compression="zstd")

    # leave-coin-out battery (secondary diagnostic, not a gate)
    if not args.skip_leave_out:
        report["leave_coin_out"] = {}
        for coin in LEAVE_OUT_COINS:
            for side in (1, -1):
                side_data = dataset.loc[dataset["side"] == side]
                train = side_data.loc[side_data["sym_key"] != coin]
                test = side_data.loc[side_data["sym_key"] == coin].copy()
                if len(test) < 100:
                    report["leave_coin_out"][f"{coin}_side{side}"] = {
                        "test_events": int(len(test)),
                        "note": "insufficient events",
                    }
                    continue
                model, timeout_mean = fit_side_model(train, features, label_column)
                scored = score_events(model, test, features, k_tp, k_sl, timeout_mean)
                test = pd.concat([test, scored], axis=1)
                quintile = pd.qcut(test["score"], 5, labels=False, duplicates="drop")
                top = test.loc[quintile == quintile.max(), net_column]
                report["leave_coin_out"][f"{coin}_side{side}"] = {
                    "test_events": int(len(test)),
                    "all_mean_net_atr": float(test[net_column].mean()),
                    "top_quintile_mean_net_atr": float(top.mean()),
                    "rank_ic": float(
                        test["score"].corr(test[net_column], method="spearman")
                    ),
                }
                print(f"leave-out {coin} side {side} done", flush=True)

    # final models on the full development window (for freeze/reveal later)
    final_meta = {}
    for side in (1, -1):
        side_data = dataset.loc[dataset["side"] == side]
        model, timeout_mean = fit_side_model(side_data, features, label_column)
        side_name = "long" if side == 1 else "short"
        model_path = args.output_dir / f"final_{side_name}.joblib"
        joblib.dump(model, model_path)
        importance = pd.DataFrame(
            {
                "feature": features,
                "gain": model.model.booster_.feature_importance("gain"),
                "split": model.model.booster_.feature_importance("split"),
            }
        ).sort_values("gain", ascending=False)
        importance.to_csv(args.output_dir / f"feature_importance_{side_name}.csv", index=False)
        final_meta[side_name] = {
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "timeout_mean_atr": timeout_mean,
            "best_iteration": int(model.model.best_iteration_ or 0),
            "train_events": int(len(side_data)),
            "top_features": importance.head(15)["feature"].tolist(),
        }
    report["final_models"] = final_meta

    report_path = args.output_dir / "training_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"oof -> {oof_path}")
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
