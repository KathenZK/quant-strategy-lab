from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
WF_ROOT = ARTIFACT_DIR / "development_walk_forward"
MATRIX_MANIFEST = ARTIFACT_DIR / "development_model_matrix_manifest.json"
OUTPUT_JSON = ARTIFACT_DIR / "historical_factor_group_ablation_2026-07-19.json"
OUTPUT_CSV = ARTIFACT_DIR / "historical_factor_group_ablation_2026-07-19.csv"
MODEL_PATTERN = "short_return_regression_stable_full_48h_wf_*_s42"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def base_feature_name(name: str) -> str:
    return name.removeprefix("cs_rank_")


def feature_group(name: str) -> str:
    value = base_feature_name(name)
    if value.startswith("market_") or value.startswith("relative_to_btc"):
        return "market_regime_cross_asset"
    if any(token in value for token in ("funding",)):
        return "funding_carry"
    if any(token in value for token in ("mark_premium", "basis")):
        return "mark_basis_premium"
    if any(
        token in value
        for token in (
            "volume", "dollar_volume", "trade_count", "taker_imbalance",
            "amihud", "vwap", "liquidity", "coverage",
        )
    ):
        return "liquidity_volume_flow"
    if any(
        token in value
        for token in (
            "atr_", "realized_vol", "downside_vol", "upside_vol",
            "drawdown", "range_max", "extreme_return", "jump_count",
            "kurtosis", "skew",
        )
    ):
        return "volatility_tail"
    if any(
        token in value
        for token in (
            "ema_", "ma_distance", "breakout", "bollinger", "zscore_",
        )
    ):
        return "trend_breakout"
    if any(
        token in value
        for token in (
            "ret_", "rsi_", "candle", "wick", "close_location",
            "bullish", "bearish",
        )
    ):
        return "momentum_reversal_price_action"
    if any(token in value for token in ("age_",)):
        return "lifecycle"
    return "other"


def mean_cross_sectional_ic(
    ts: pd.Series, score: np.ndarray, target_rank: pd.Series
) -> tuple[float, float]:
    work = pd.DataFrame({"ts": ts.to_numpy(), "score": score})
    work["score_rank"] = work.groupby("ts", sort=False)["score"].rank(
        method="average", pct=True, na_option="keep"
    )
    work["target_rank"] = target_rank.to_numpy()
    grouped = work.groupby("ts", sort=False)
    score_centered = work["score_rank"] - grouped["score_rank"].transform("mean")
    target_centered = work["target_rank"] - grouped["target_rank"].transform("mean")
    work["cross"] = score_centered * target_centered
    work["score_sq"] = score_centered**2
    work["target_sq"] = target_centered**2
    sums = work.groupby("ts", sort=False)[["cross", "score_sq", "target_sq"]].sum()
    denominator = np.sqrt(sums["score_sq"] * sums["target_sq"])
    hourly = (sums["cross"] / denominator.replace(0.0, np.nan)).dropna()
    return float(hourly.mean()), float(hourly.gt(0.0).mean())


def permutation_index(ts: pd.Series) -> np.ndarray:
    result = np.arange(len(ts), dtype="int64")
    for indices in ts.groupby(ts, sort=False).indices.values():
        result[indices] = np.roll(indices, 1)
    return result


def load_fold_frame(
    *, start: pd.Timestamp, end: pd.Timestamp, features: list[str]
) -> pd.DataFrame:
    years = range(start.year, (end - pd.Timedelta(seconds=1)).year + 1)
    parts: list[pd.DataFrame] = []
    columns = ["ts", "symbol", *features, "label_short_net_48h"]
    matrix_root = ROOT / json.loads(MATRIX_MANIFEST.read_text(encoding="utf-8"))[
        "matrix_root"
    ]
    for year in years:
        path = matrix_root / f"year={year}/data_0.parquet"
        value = pd.read_parquet(path, columns=columns)
        value["ts"] = pd.to_datetime(value["ts"], utc=True)
        parts.append(value.loc[value["ts"].ge(start) & value["ts"].lt(end)])
    frame = pd.concat(parts, ignore_index=True).sort_values(["ts", "symbol"])
    return frame


def tail_stability() -> dict[str, Any]:
    result: dict[str, Any] = {}
    patterns = {
        "short_mae_quantile": "short_mae_quantile_stable_full_48h_wf_*_s*",
        "short_squeeze_classification": (
            "short_event_classification_stable_full_48h_wf_*_s*"
        ),
    }
    for name, pattern in patterns.items():
        rows: list[dict[str, Any]] = []
        for directory in sorted(WF_ROOT.glob(pattern)):
            diagnostic = json.loads(
                (directory / "diagnostics.json").read_text(encoding="utf-8")
            )
            rows.append(
                {
                    "fold_id": diagnostic["fold_id"],
                    "seed": diagnostic["seed"],
                    "mean_cross_sectional_rank_ic": diagnostic["predictive"][
                        "mean_cross_sectional_rank_ic"
                    ],
                    "positive_ic_share": diagnostic["predictive"][
                        "positive_cross_sectional_rank_ic_share"
                    ],
                }
            )
        frame = pd.DataFrame(rows)
        result[name] = {
            "observations": len(frame),
            "folds": int(frame["fold_id"].nunique()),
            "seeds": int(frame["seed"].nunique()),
            "mean_ic": float(frame["mean_cross_sectional_rank_ic"].mean()),
            "minimum_fold_seed_ic": float(
                frame["mean_cross_sectional_rank_ic"].min()
            ),
            "positive_fold_seed_count": int(
                frame["mean_cross_sectional_rank_ic"].gt(0.0).sum()
            ),
            "mean_positive_ic_share": float(frame["positive_ic_share"].mean()),
        }
    return result


def feature_set_comparison() -> dict[str, Any]:
    files = {
        "compact": "allocator_search_compact_regression_h48_s42.csv",
        "stable_full": "allocator_search_stable_full_regression_h48_s42.csv",
        "tail_stable": "allocator_search_tail_stable_regression_h48_s42.csv",
        "ridge_compact": "allocator_search_compact_ridge_h48_s42.csv",
    }
    root = ARTIFACT_DIR / "development_allocator_search"
    output: dict[str, Any] = {}
    for name, filename in files.items():
        frame = pd.read_csv(root / filename)
        if "score_source" in frame:
            frame = frame.loc[frame["score_source"].eq("lgbm")]
        row = frame.sort_values("selection_score", ascending=False).iloc[0]
        output[name] = {
            key: row[key]
            for key in (
                "annualized_return", "max_drawdown", "win_rate", "sharpe",
                "profit_factor", "decision_count", "trade_count",
                "selection_score",
            )
        }
    return output


def main() -> None:
    if pd.Timestamp.now("UTC") < pd.Timestamp("2026-07-19T00:00:00Z"):
        pass
    diagnostics = sorted(WF_ROOT.glob(MODEL_PATTERN))
    if len(diagnostics) != 7:
        raise RuntimeError(f"expected seven seed-42 return folds, got {len(diagnostics)}")
    first = json.loads((diagnostics[0] / "diagnostics.json").read_text(encoding="utf-8"))
    features = list(first["features"])
    groups: dict[str, list[str]] = {}
    for feature in features:
        groups.setdefault(feature_group(feature), []).append(feature)
    if sum(map(len, groups.values())) != len(features):
        raise RuntimeError("factor-group mapping is incomplete")
    rows: list[dict[str, Any]] = []
    for index, directory in enumerate(diagnostics, start=1):
        diagnostic = json.loads(
            (directory / "diagnostics.json").read_text(encoding="utf-8")
        )
        if diagnostic.get("prospective_oos_outcomes_read"):
            raise RuntimeError("historical fold reports prospective outcome access")
        start = pd.Timestamp(diagnostic["validation_start"])
        end = pd.Timestamp(diagnostic["validation_end_exclusive"])
        frame = load_fold_frame(start=start, end=end, features=features)
        predictions = pd.read_parquet(ROOT / diagnostic["predictions_path"])[
            ["ts", "symbol", "score"]
        ]
        predictions["ts"] = pd.to_datetime(predictions["ts"], utc=True)
        frame = frame.merge(
            predictions, on=["ts", "symbol"], how="inner", validate="one_to_one"
        )
        frame = frame.loc[frame["label_short_net_48h"].notna()].reset_index(drop=True)
        x = (
            frame[features]
            .astype("float32")
            .replace([np.inf, -np.inf], np.nan)
            .to_numpy()
        )
        target_rank = frame.groupby("ts", sort=False)["label_short_net_48h"].rank(
            method="average", pct=True, na_option="keep"
        )
        booster = lgb.Booster(model_file=str(ROOT / diagnostic["model_path"]))
        baseline_score = booster.predict(x, num_iteration=diagnostic["best_iteration"])
        parity = float(np.corrcoef(baseline_score, frame["score"])[0, 1])
        if parity < 0.999999:
            raise RuntimeError(f"stored/model prediction parity failed: {directory}")
        baseline_ic, baseline_positive = mean_cross_sectional_ic(
            frame["ts"], baseline_score, target_rank
        )
        rows.append(
            {
                "fold_id": diagnostic["fold_id"],
                "factor_group": "__baseline__",
                "feature_count": len(features),
                "mean_cross_sectional_rank_ic": baseline_ic,
                "positive_ic_share": baseline_positive,
                "ic_drop_vs_baseline": 0.0,
                "prediction_parity": parity,
            }
        )
        source_index = permutation_index(frame["ts"])
        for group, group_features in sorted(groups.items()):
            columns = np.array([features.index(name) for name in group_features])
            permuted = x.copy()
            permuted[:, columns] = x[source_index][:, columns]
            score = booster.predict(
                permuted, num_iteration=diagnostic["best_iteration"]
            )
            ic, positive_share = mean_cross_sectional_ic(
                frame["ts"], score, target_rank
            )
            rows.append(
                {
                    "fold_id": diagnostic["fold_id"],
                    "factor_group": group,
                    "feature_count": len(group_features),
                    "mean_cross_sectional_rank_ic": ic,
                    "positive_ic_share": positive_share,
                    "ic_drop_vs_baseline": baseline_ic - ic,
                    "prediction_parity": parity,
                }
            )
        print(f"factor ablation folds {index}/{len(diagnostics)}", flush=True)
    detail = pd.DataFrame(rows)
    detail.to_csv(OUTPUT_CSV, index=False)
    baseline = detail.loc[detail["factor_group"].eq("__baseline__")]
    ablation = detail.loc[~detail["factor_group"].eq("__baseline__")]
    aggregate = ablation.groupby("factor_group", sort=False).agg(
        feature_count=("feature_count", "first"),
        mean_ablated_ic=("mean_cross_sectional_rank_ic", "mean"),
        mean_ic_drop=("ic_drop_vs_baseline", "mean"),
        positive_drop_folds=("ic_drop_vs_baseline", lambda values: int(values.gt(0).sum())),
    ).reset_index()
    positive_drops = aggregate["mean_ic_drop"].clip(lower=0.0)
    concentration = (
        float(positive_drops.max() / positive_drops.sum())
        if positive_drops.sum() > 0.0
        else 1.0
    )
    tail = tail_stability()
    gates = {
        "return_ic_positive_all_7_folds": bool(
            baseline["mean_cross_sectional_rank_ic"].gt(0.0).all()
        ),
        "at_least_3_material_positive_groups": bool(
            aggregate["mean_ic_drop"].gt(0.001).sum() >= 3
        ),
        "at_least_3_groups_positive_in_5_of_7_folds": bool(
            aggregate["positive_drop_folds"].ge(5).sum() >= 3
        ),
        "mae_tail_ic_positive_all_fold_seeds": (
            tail["short_mae_quantile"]["positive_fold_seed_count"]
            == tail["short_mae_quantile"]["observations"]
        ),
        "squeeze_tail_ic_positive_all_fold_seeds": (
            tail["short_squeeze_classification"]["positive_fold_seed_count"]
            == tail["short_squeeze_classification"]["observations"]
        ),
    }
    payload = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if all(gates.values()) else "BLOCKED",
        "scope": "historical development OOF only; no prospective OOS access",
        "method": (
            "Seed-42 stable-full 48h short-return OOF models; deterministic "
            "within-timestamp one-symbol rotation for each factor group."
        ),
        "feature_count": len(features),
        "factor_groups": {name: len(values) for name, values in groups.items()},
        "baseline_mean_ic": float(baseline["mean_cross_sectional_rank_ic"].mean()),
        "baseline_positive_folds": int(
            baseline["mean_cross_sectional_rank_ic"].gt(0.0).sum()
        ),
        "group_ablation": aggregate.to_dict("records"),
        "positive_ic_drop_concentration": concentration,
        "known_risk": {
            "dominant_group": aggregate.sort_values(
                "mean_ic_drop", ascending=False
            ).iloc[0]["factor_group"],
            "dominant_positive_ic_drop_share": concentration,
            "note": (
                "This concentration is disclosed as dependency risk, not converted "
                "after the fact into an uncontracted hard threshold."
            ),
        },
        "tail_stability": tail,
        "feature_set_comparison": feature_set_comparison(),
        "gates": gates,
        "blockers": [name for name, passed in gates.items() if not passed],
        "detail_csv": str(OUTPUT_CSV.relative_to(ROOT)),
        "detail_csv_sha256": sha256(OUTPUT_CSV),
        "prospective_oos_outcomes_read": False,
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    if payload["status"] != "PASS":
        raise RuntimeError(f"historical factor-group ablation blocked: {payload['blockers']}")


if __name__ == "__main__":
    main()
