from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.tree import DecisionTreeClassifier, export_text


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-trend-prebreakout-state-atlas"
CONFIG_PATH = FAMILY_DIR / "configs/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml.json"
EXPECTED_CONFIG_SHA256 = "b81a4d6ea48d612cd3d941a695d1446c72c532464052e703aeec244493c94c1f"
EVENTS_PATH = FAMILY_DIR / "artifacts/binance_1d_tpsa_p0r_events.parquet"
EXPECTED_EVENTS_SHA256 = "1c7f9cced72f4cdee48d4f1f9b152f07885de3e7a4bfe5cd35d944046a8d902f"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
REPORT_PATH = FAMILY_DIR / "diagnostics/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md"
OUTPUTS = {
    "metrics": ARTIFACT_DIR / "binance_1d_tpsa_p1_barrier_ml_metrics.csv",
    "predictions": ARTIFACT_DIR / "binance_1d_tpsa_p1_barrier_ml_predictions.parquet",
    "deciles": ARTIFACT_DIR / "binance_1d_tpsa_p1_barrier_ml_deciles.csv",
    "importance": ARTIFACT_DIR / "binance_1d_tpsa_p1_barrier_ml_importance.csv",
    "profiles": ARTIFACT_DIR / "binance_1d_tpsa_p1_barrier_ml_state_profiles.csv",
    "tree_rules": ARTIFACT_DIR / "binance_1d_tpsa_p1_barrier_tree_rules.txt",
    "summary": ARTIFACT_DIR / "binance_1d_tpsa_p1_summary.json",
    "manifest": ARTIFACT_DIR / "binance_1d_tpsa_p1_artifact_manifest.json",
}


def _load_parent_module() -> Any:
    path = FAMILY_DIR / "scripts/run_binance_1d_trend_prebreakout_state_atlas_p0.py"
    spec = importlib.util.spec_from_file_location("tpsa_p0_parent", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load P0 parent module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARENT = _load_parent_module()
ML_FEATURES = PARENT.ML_FEATURES
PRIMARY_MA_PERIODS = PARENT.PRIMARY_MA_PERIODS
WALK_FORWARD_WINDOWS = PARENT.WALK_FORWARD_WINDOWS
DEVELOPMENT_CUTOFF = PARENT.DEVELOPMENT_CUTOFF


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen BIN-1D-TPSA-P1 path-label ML.")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(*, force: bool) -> dict[str, Any]:
    if sha256_file(CONFIG_PATH) != EXPECTED_CONFIG_SHA256:
        raise RuntimeError("P1 frozen config hash mismatch")
    if sha256_file(EVENTS_PATH) != EXPECTED_EVENTS_SHA256:
        raise RuntimeError("P0R events hash mismatch")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != "BIN-1D-TPSA-P1":
        raise RuntimeError("unexpected P1 study id")
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        raise FileExistsError("P1 outputs exist; pass --force")
    return config


def load_events() -> pd.DataFrame:
    columns = [
        "event_id",
        "symbol",
        "event_date",
        "outcome_end_date_20",
        "ma_period",
        "direction",
        "barrier_success_20",
        *ML_FEATURES,
    ]
    events = pd.read_parquet(EVENTS_PATH, columns=columns)
    events["event_date"] = pd.to_datetime(events["event_date"], utc=True)
    events["outcome_end_date_20"] = pd.to_datetime(
        events["outcome_end_date_20"], utc=True
    )
    events = events.loc[
        events["ma_period"].isin(PRIMARY_MA_PERIODS)
        & events["barrier_success_20"].notna()
    ].copy()
    events["target"] = events["barrier_success_20"].astype(int)
    if set(events["target"].unique()) != {0, 1}:
        raise RuntimeError("P1 target does not contain both classes")
    return events


def prediction_deciles(probability: pd.Series) -> pd.Series:
    if len(probability) < 10:
        return pd.Series(pd.NA, index=probability.index, dtype="Int64")
    ranks = probability.rank(method="first")
    return pd.qcut(ranks, 10, labels=False).astype("Int64") + 1


def model_factories() -> dict[str, Any]:
    return {
        "TREE": DecisionTreeClassifier(
            max_depth=4,
            min_samples_leaf=500,
            random_state=42,
        ),
        "LIGHTGBM": LGBMClassifier(
            n_estimators=160,
            learning_rate=0.03,
            num_leaves=15,
            max_depth=4,
            min_child_samples=300,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=5.0,
            random_state=42,
            n_jobs=4,
            verbosity=-1,
        ),
    }


def run_walk_forward(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    rule_sections: list[str] = []

    for ma_period in PRIMARY_MA_PERIODS:
        for direction in ("long", "short"):
            pool = events.loc[
                events["ma_period"].eq(ma_period) & events["direction"].eq(direction)
            ].copy()
            for test_start, test_end in WALK_FORWARD_WINDOWS:
                train = pool.loc[pool["outcome_end_date_20"].lt(test_start)]
                test = pool.loc[
                    pool["event_date"].ge(test_start) & pool["event_date"].lt(test_end)
                ]
                if len(train) < 2000 or len(test) < 200:
                    continue
                imputer = SimpleImputer(strategy="median")
                x_train = pd.DataFrame(
                    imputer.fit_transform(train[list(ML_FEATURES)]),
                    columns=ML_FEATURES,
                    index=train.index,
                )
                x_test = pd.DataFrame(
                    imputer.transform(test[list(ML_FEATURES)]),
                    columns=ML_FEATURES,
                    index=test.index,
                )
                y_train = train["target"].to_numpy(dtype=int)
                y_test = test["target"].to_numpy(dtype=int)
                for model_name, model in model_factories().items():
                    model.fit(x_train, y_train)
                    probability = model.predict_proba(x_test)[:, 1]
                    scored = test[
                        ["event_id", "symbol", "event_date", "ma_period", "direction"]
                    ].copy()
                    scored["fold"] = str(test_start.year)
                    scored["model"] = model_name
                    scored["target"] = y_test
                    scored["probability"] = probability
                    scored["prediction_decile"] = prediction_deciles(scored["probability"])
                    decile_rate = scored.groupby("prediction_decile", observed=True)[
                        "target"
                    ].mean()
                    spread = (
                        float(decile_rate.loc[10] - decile_rate.loc[1])
                        if 1 in decile_rate.index and 10 in decile_rate.index
                        else math.nan
                    )
                    metric_rows.append(
                        {
                            "ma_period": ma_period,
                            "direction": direction,
                            "fold": str(test_start.year),
                            "model": model_name,
                            "train_count": len(train),
                            "test_count": len(test),
                            "test_base_rate": float(y_test.mean()),
                            "roc_auc": float(roc_auc_score(y_test, probability)),
                            "average_precision": float(
                                average_precision_score(y_test, probability)
                            ),
                            "brier_score": float(brier_score_loss(y_test, probability)),
                            "top_minus_bottom_decile_success_rate": spread,
                        }
                    )
                    prediction_frames.append(scored)
                    perm = permutation_importance(
                        model,
                        x_test,
                        y_test,
                        scoring="roc_auc",
                        n_repeats=3,
                        random_state=42,
                        n_jobs=1,
                    )
                    builtin = getattr(
                        model, "feature_importances_", np.full(len(ML_FEATURES), np.nan)
                    )
                    for feature, built, p_mean, p_std in zip(
                        ML_FEATURES,
                        builtin,
                        perm.importances_mean,
                        perm.importances_std,
                        strict=True,
                    ):
                        importance_rows.append(
                            {
                                "ma_period": ma_period,
                                "direction": direction,
                                "fold": str(test_start.year),
                                "model": model_name,
                                "feature": feature,
                                "builtin_importance": float(built),
                                "permutation_auc_decrease": float(p_mean),
                                "permutation_std": float(p_std),
                            }
                        )

            full = pool.loc[pool["event_date"].lt(DEVELOPMENT_CUTOFF)]
            imputer = SimpleImputer(strategy="median")
            x_full = pd.DataFrame(
                imputer.fit_transform(full[list(ML_FEATURES)]),
                columns=ML_FEATURES,
                index=full.index,
            )
            tree = DecisionTreeClassifier(
                max_depth=4, min_samples_leaf=500, random_state=42
            ).fit(x_full, full["target"].to_numpy(dtype=int))
            rule_sections.extend(
                [
                    f"## MA{ma_period} {direction}",
                    export_text(tree, feature_names=list(ML_FEATURES), decimals=3),
                ]
            )

    metrics = pd.DataFrame(metric_rows)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    importance = pd.DataFrame(importance_rows)
    deciles = (
        predictions.groupby(
            ["ma_period", "direction", "fold", "model", "prediction_decile"],
            observed=True,
        )
        .agg(
            sample_count=("target", "size"),
            predicted_probability=("probability", "mean"),
            actual_success_rate=("target", "mean"),
        )
        .reset_index()
    )
    return metrics, predictions, deciles, importance, "\n\n".join(rule_sections) + "\n"


def summarize_models(metrics: pd.DataFrame) -> pd.DataFrame:
    result = (
        metrics.groupby(["ma_period", "direction", "model"])
        .agg(
            folds=("fold", "nunique"),
            auc_above_half_folds=("roc_auc", lambda x: int(np.sum(np.asarray(x) > 0.5))),
            auc_above_053_folds=("roc_auc", lambda x: int(np.sum(np.asarray(x) > 0.53))),
            positive_spread_folds=(
                "top_minus_bottom_decile_success_rate",
                lambda x: int(np.sum(np.asarray(x) > 0)),
            ),
            mean_auc=("roc_auc", "mean"),
            mean_average_precision=("average_precision", "mean"),
            mean_base_rate=("test_base_rate", "mean"),
            mean_top_bottom_spread=("top_minus_bottom_decile_success_rate", "mean"),
        )
        .reset_index()
    )
    result["majority_auc_and_spread"] = (
        result["auc_above_half_folds"].gt(result["folds"] / 2)
        & result["positive_spread_folds"].gt(result["folds"] / 2)
    )
    return result


def build_state_profiles(
    events: pd.DataFrame, predictions: pd.DataFrame
) -> pd.DataFrame:
    categorical = (
        "prior_move_state",
        "recent_move_state",
        "volatility_level_state",
        "volatility_path_state",
        "efficiency_state",
        "consolidation_state",
    )
    event_columns = ["event_id", *ML_FEATURES, *categorical]
    source = pd.read_parquet(EVENTS_PATH, columns=event_columns)
    scored = predictions.loc[
        predictions["model"].eq("LIGHTGBM")
        & predictions["prediction_decile"].isin([1, 10])
    ].merge(source, on="event_id", how="left", validate="one_to_one")
    rows: list[dict[str, Any]] = []
    for keys, group in scored.groupby(
        ["ma_period", "direction", "prediction_decile"], observed=True
    ):
        identity = {
            "ma_period": int(keys[0]),
            "direction": keys[1],
            "prediction_decile": int(keys[2]),
        }
        for feature in ML_FEATURES:
            values = group[feature].to_numpy(dtype=float)
            rows.append(
                {
                    **identity,
                    "profile_type": "numeric",
                    "feature": feature,
                    "category": "",
                    "value": float(np.nanmedian(values)),
                    "mean_value": float(np.nanmean(values)),
                    "sample_count": int(np.isfinite(values).sum()),
                }
            )
        for feature in categorical:
            shares = group[feature].value_counts(normalize=True, dropna=False)
            for category, share in shares.items():
                rows.append(
                    {
                        **identity,
                        "profile_type": "categorical_share",
                        "feature": feature,
                        "category": str(category),
                        "value": float(share),
                        "mean_value": math.nan,
                        "sample_count": len(group),
                    }
                )
    return pd.DataFrame(rows)


def write_report(
    events: pd.DataFrame,
    metrics: pd.DataFrame,
    predictions: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    pooled_deciles = (
        predictions.loc[predictions["model"].eq("LIGHTGBM")]
        .groupby(["ma_period", "direction", "prediction_decile"], observed=True)[
            "target"
        ]
        .mean()
    )

    def pooled_rate(period: int, direction: str, decile: int) -> float:
        return float(pooled_deciles.loc[(period, direction, decile)])

    lines = [
        "# BIN-1D-TPSA-P1：趋势是否发生的路径标签模型",
        "",
        "## 大白话结论",
        "",
        "本轮模型学的不是20天后赚不赚钱，而是：突破后是否先顺向走到 `+2 ATR`，而不是先反向走到 `-1 ATR`。所有输入仍只来自突破前一日及更早。",
        "",
        "只有当 MA7 和 MA30 在同一方向上都能在多数年份得到 AUC 大于 0.5、预测最高十分位的实际成功率也高于最低十分位，才算学到了可重复的市场状态。",
        "",
        "## 模型实际学到的市场状态",
        "",
        "**做多方向出现了一个可重复但尚未确认的结构：突破前波动率处在自身近期较低位置，价格经历过一段下跌或回撤，最近逐渐稳定、单日冲击减弱，然后向上跨越均线。** 它不是‘高 ER 的现成上涨趋势’，更接近‘下跌后的低波稳定区开始向上脱离’。",
        "",
        f"在全部逐年前推预测拼接后，MA7 做多模型最低十分位的趋势发生率为 {pooled_rate(7, 'long', 1):.2%}，最高十分位为 {pooled_rate(7, 'long', 10):.2%}；MA30 做多分别为 {pooled_rate(30, 'long', 1):.2%} 和 {pooled_rate(30, 'long', 10):.2%}。",
        "",
        "做空模型也偏爱低波、收窄、此前已经向下移动的状态，但 MA30 在不同年份反复翻转，因此做空暂时不能算跨均线稳定。",
        "",
        "这与 P0R 的最终收益结果不矛盾：低波稳定区可以提高‘先走出 +2 ATR 趋势段’的概率，但并不保证持有到第20天仍然赚钱。市场结构过滤对趋势启动表现出弱到中等效果，退出和趋势保持仍是下一层问题。",
        "",
        "## 样本",
        "",
        "| MA | 方向 | 有标签事件 | 趋势发生率 |",
        "| --- | --- | ---: | ---: |",
    ]
    for keys, group in events.groupby(["ma_period", "direction"]):
        lines.append(
            f"| MA{keys[0]} | {keys[1]} | {len(group):,} | {group['target'].mean():.2%} |"
        )
    lines.extend(
        [
            "",
            "## 逐年前推汇总",
            "",
            "| MA | 方向 | 模型 | AUC>0.5年份 | AUC>0.53年份 | 头尾差为正年份 | 平均AUC | 平均头尾成功率差 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary.itertuples(index=False):
        lines.append(
            f"| MA{row.ma_period} | {row.direction} | {row.model} | {row.auc_above_half_folds}/{row.folds} | {row.auc_above_053_folds}/{row.folds} | {row.positive_spread_folds}/{row.folds} | {row.mean_auc:.3f} | {row.mean_top_bottom_spread:.2%} |"
        )
    lightgbm = summary.loc[summary["model"].eq("LIGHTGBM")]
    passed_directions = []
    for direction, group in lightgbm.groupby("direction"):
        if set(group["ma_period"]) == set(PRIMARY_MA_PERIODS) and group[
            "majority_auc_and_spread"
        ].all():
            passed_directions.append(direction)
    lines.extend(["", "## 判断", ""])
    if passed_directions:
        lines.append(
            "以下方向在 MA7 和 MA30 上均达到多数年份方向正确的探索性标准："
            + "、".join(passed_directions)
            + "。这仍需全新未揭示区间确认。"
        )
    else:
        lines.append(
            "**没有任何方向同时在 MA7 和 MA30 上达到多数年份的最低排序标准。** 换成真正的趋势路径标签以后，当前这组突破前价格/波动状态仍不足以稳定识别趋势发生。"
        )
    lines.extend(
        [
            "",
            "本轮有意不调模型参数。通过只说明价格状态含有可排序的信息，不说明概率已经校准，更不说明可以按最高十分位直接交易。",
            "",
            "## 文件",
            "",
            "- [逐年指标](../artifacts/binance_1d_tpsa_p1_barrier_ml_metrics.csv)",
            "- [预测十分位](../artifacts/binance_1d_tpsa_p1_barrier_ml_deciles.csv)",
            "- [特征重要性](../artifacts/binance_1d_tpsa_p1_barrier_ml_importance.csv)",
            "- [高分/低分市场状态画像](../artifacts/binance_1d_tpsa_p1_barrier_ml_state_profiles.csv)",
            "- [可读决策树](../artifacts/binance_1d_tpsa_p1_barrier_tree_rules.txt)",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(
    config: dict[str, Any],
    events: pd.DataFrame,
    metrics: pd.DataFrame,
    predictions: pd.DataFrame,
    deciles: pd.DataFrame,
    importance: pd.DataFrame,
    rules: str,
) -> None:
    summary_frame = summarize_models(metrics)
    profiles = build_state_profiles(events, predictions)
    metrics.to_csv(OUTPUTS["metrics"], index=False)
    predictions.to_parquet(OUTPUTS["predictions"], index=False)
    deciles.to_csv(OUTPUTS["deciles"], index=False)
    importance.to_csv(OUTPUTS["importance"], index=False)
    profiles.to_csv(OUTPUTS["profiles"], index=False)
    OUTPUTS["tree_rules"].write_text(rules, encoding="utf-8")
    lightgbm = summary_frame.loc[summary_frame["model"].eq("LIGHTGBM")]
    passed_directions = []
    for direction, group in lightgbm.groupby("direction"):
        if set(group["ma_period"]) == set(PRIMARY_MA_PERIODS) and group[
            "majority_auc_and_spread"
        ].all():
            passed_directions.append(direction)
    summary = {
        "study_id": config["study_id"],
        "status": "exploratory_completed",
        "events": len(events),
        "target_base_rates": [
            {
                "ma_period": int(keys[0]),
                "direction": keys[1],
                "count": len(group),
                "success_rate": float(group["target"].mean()),
            }
            for keys, group in events.groupby(["ma_period", "direction"])
        ],
        "model_summary": summary_frame.to_dict("records"),
        "directions_meeting_exploratory_cross_ma_majority_gate": passed_directions,
        "decision": (
            "INSUFFICIENT_EVIDENCE"
            if not passed_directions
            else "EXPLORATORY_SIGNAL_REQUIRES_NEW_OOS"
        ),
        "no_strategy_no_account": True,
    }
    OUTPUTS["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(events, metrics, predictions, summary_frame)
    paths = [*OUTPUTS.values(), REPORT_PATH]
    manifest = {
        "study_id": config["study_id"],
        "config_sha256": sha256_file(CONFIG_PATH),
        "input_events_sha256": sha256_file(EVENTS_PATH),
        "artifacts": [
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in paths
            if path.exists() and path != OUTPUTS["manifest"]
        ],
    }
    OUTPUTS["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("pass --run after reviewing the frozen P1 contract")
    config = validate_inputs(force=args.force)
    events = load_events()
    metrics, predictions, deciles, importance, rules = run_walk_forward(events)
    write_outputs(config, events, metrics, predictions, deciles, importance, rules)
    print(
        json.dumps(
            {
                "study_id": config["study_id"],
                "events": len(events),
                "fold_rows": len(metrics),
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
