from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = (
    ROOT / "research/asset-portfolios/1d-ma7-quantile-utility-meta-label"
)
BASE_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-taker-flow-meta-label/"
    "scripts/research_binance_1d_ma7_tfml_p1.py"
)
EVENT_DIR = FAMILY_DIR / "artifacts/p0_events_2026-08-10"
EVENT_PATH = EVENT_DIR / "p0_events.parquet"
EVENT_CAPACITY_PATH = EVENT_DIR / "p0_capacity.json"
PRICE_QUALITY_PATH = FAMILY_DIR / (
    "artifacts/p0_price_data_2026-08-10/p0_data_quality_manifest.json"
)
OUTPUT_DIR = FAMILY_DIR / "artifacts/p1_development_2026-08-10"
LEGACY_ASSETS = (
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "TRX",
    "XRP",
    "DOGE",
    "ADA",
    "LINK",
    "LTC",
    "DOT",
    "AVAX",
    "UNI",
)
FRESH_ASSETS = ("BCH", "ETC", "XLM", "ATOM", "VET", "NEAR", "AAVE", "FIL")
ALL_ASSETS = (*LEGACY_ASSETS, *FRESH_ASSETS)
QUANTILE_GRID = (0.80, 0.90, 0.95)
END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")


def load_base_module():
    spec = importlib.util.spec_from_file_location(
        "binance_1d_ma7_quml_p1_base",
        BASE_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise ImportError(BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--bootstrap-samples", type=int, default=5_000)
    parser.add_argument("--capacity-only", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def verify_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    event_manifest_path = EVENT_DIR / "manifest.json"
    manifest = json.loads(event_manifest_path.read_text(encoding="utf-8"))
    for details in manifest["files"].values():
        path = EVENT_DIR / details["path"]
        if sha256_path(path) != details["sha256"]:
            raise RuntimeError(f"Event manifest mismatch: {path}")
    capacity = json.loads(EVENT_CAPACITY_PATH.read_text(encoding="utf-8"))
    quality = json.loads(PRICE_QUALITY_PATH.read_text(encoding="utf-8"))
    if quality.get("family") != "BIN-1D-MA7-QUML":
        raise RuntimeError("QUML price source family mismatch")
    if int(quality.get("blocker_count", -1)) != 0:
        raise RuntimeError("QUML price source blockers remain")
    if set(quality.get("symbols", [])) != {
        f"{asset}USDT" for asset in FRESH_ASSETS
    }:
        raise RuntimeError("QUML fresh source universe mismatch")
    return capacity, {
        "event_manifest_sha256": sha256_path(event_manifest_path),
        "price_quality_sha256": sha256_path(PRICE_QUALITY_PATH),
    }


def train_quantile_threshold(
    base,
    model,
    train: pd.DataFrame,
    *,
    quantile: float,
    route: str,
) -> float | None:
    predicted = base.predict_utility(model, train, base.PRICE_FEATURES)
    eligible = base.route_mask(train, route).to_numpy(dtype=bool)
    values = predicted[eligible]
    if not len(values) or not np.isfinite(values).all():
        return None
    return float(np.quantile(values, quantile))


def select_inner_quantile(
    base,
    events: pd.DataFrame,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    folds = base.time_blocks(events, initial_fraction=0.50, blocks=3)
    predictions: dict[float, list[dict[str, Any]]] = {}
    for alpha in base.ALPHA_GRID:
        payloads: list[dict[str, Any]] = []
        for fold, first_test, last_test in folds:
            train, test = base.split_for_block(
                events,
                first_test=first_test,
                last_test=last_test,
            )
            if train.empty or test.empty:
                payloads = []
                break
            model = base.fit_model(train, base.PRICE_FEATURES, alpha)
            payloads.append(
                {
                    "fold": fold,
                    "train": train,
                    "train_prediction": base.predict_utility(
                        model, train, base.PRICE_FEATURES
                    ),
                    "test": test,
                    "test_prediction": base.predict_utility(
                        model, test, base.PRICE_FEATURES
                    ),
                }
            )
        if payloads:
            predictions[alpha] = payloads

    scores: list[dict[str, Any]] = []
    for alpha, payloads in predictions.items():
        for route in base.ROUTES:
            for quantile in QUANTILE_GRID:
                selected_frames: list[pd.DataFrame] = []
                thresholds: list[float] = []
                fold_counts: dict[int, int] = {}
                fold_metrics: dict[int, dict[str, Any]] = {}
                valid = True
                for payload in payloads:
                    train = payload["train"]
                    train_prediction = payload["train_prediction"]
                    train_eligible = base.route_mask(
                        train, route
                    ).to_numpy(dtype=bool)
                    train_values = train_prediction[train_eligible]
                    if not len(train_values):
                        valid = False
                        break
                    threshold = float(np.quantile(train_values, quantile))
                    test = payload["test"].copy()
                    test["predicted_utility"] = payload["test_prediction"]
                    selected = test.loc[
                        base.route_mask(test, route)
                        & test["predicted_utility"].ge(threshold)
                    ].copy()
                    fold = int(payload["fold"])
                    selected["inner_fold"] = fold
                    thresholds.append(threshold)
                    fold_counts[fold] = int(len(selected))
                    fold_metrics[fold] = base.return_metrics(selected, "z_8bps")
                    selected_frames.append(selected)
                if not valid:
                    continue
                selected_all = pd.concat(selected_frames, ignore_index=True)
                overall = base.return_metrics(selected_all, "z_8bps")
                sides = {
                    "long": int(selected_all["side"].gt(0).sum()),
                    "short": int(selected_all["side"].lt(0).sum()),
                }
                direction_eligible = (
                    min(sides.values()) >= 15
                    if route == "combined"
                    else True
                )
                eligible = bool(
                    len(selected_all) >= 40
                    and all(fold_counts.get(fold, 0) >= 8 for fold in range(1, 4))
                    and all(
                        float(fold_metrics[fold]["mean"]) > 0.0
                        for fold in range(1, 4)
                    )
                    and float(overall["profit_factor"]) >= 1.05
                    and direction_eligible
                )
                scores.append(
                    {
                        "alpha": alpha,
                        "quantile": quantile,
                        "route": route,
                        "eligible": eligible,
                        "selected_events": int(len(selected_all)),
                        "side_counts": sides,
                        "fold_counts": fold_counts,
                        "train_thresholds": thresholds,
                        "worst_fold_mean": (
                            min(
                                float(metric["mean"])
                                for metric in fold_metrics.values()
                            )
                            if eligible
                            else None
                        ),
                        "overall": overall,
                        "fold_metrics": fold_metrics,
                    }
                )
    eligible_scores = [score for score in scores if score["eligible"]]
    if not eligible_scores:
        return None, scores
    route_rank = {"combined": 2, "long_only": 1, "short_only": 0}
    choice = max(
        eligible_scores,
        key=lambda score: (
            float(score["worst_fold_mean"]),
            float(score["overall"]["mean"]),
            float(score["overall"]["profit_factor"]),
            float(score["quantile"]),
            float(score["alpha"]),
            route_rank[str(score["route"])],
        ),
    )
    return {
        "alpha": float(choice["alpha"]),
        "quantile": float(choice["quantile"]),
        "route": str(choice["route"]),
    }, scores


def evaluate_quantile_fold(
    base,
    *,
    events: pd.DataFrame,
    held_asset: str,
    outer_fold: int,
    first_test: pd.Timestamp,
    last_test: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    base_train, base_test = base.split_for_block(
        events,
        first_test=first_test,
        last_test=last_test,
    )
    train = base_train.loc[base_train["asset"].ne(held_asset)].copy()
    test = base_test.loc[base_test["asset"].eq(held_asset)].copy()
    if train.empty or test.empty:
        raise RuntimeError(f"Invalid QUML outer fold {held_asset}-{outer_fold}")
    choice, inner_scores = select_inner_quantile(base, train)
    prediction = test.copy()
    prediction["held_asset"] = held_asset
    prediction["outer_fold"] = outer_fold
    prediction["model_route"] = "quantile_utility"
    prediction["selected_quantile"] = np.nan
    prediction["selected_q_minus_005"] = False
    prediction["selected_q_plus_005"] = False
    if choice is None:
        prediction["predicted_utility"] = np.nan
        prediction["selected_alpha"] = np.nan
        prediction["selected_threshold"] = np.nan
        prediction["selected_route"] = "NO_SELECTION"
        prediction["route_eligible"] = False
        prediction["selected"] = False
        report_choice = None
    else:
        model = base.fit_model(
            train,
            base.PRICE_FEATURES,
            float(choice["alpha"]),
        )
        route = str(choice["route"])
        quantile = float(choice["quantile"])
        train_prediction = base.predict_utility(
            model, train, base.PRICE_FEATURES
        )
        train_eligible = base.route_mask(train, route).to_numpy(dtype=bool)
        train_values = train_prediction[train_eligible]
        thresholds = {
            "q_minus_005": float(
                np.quantile(train_values, max(0.0, quantile - 0.05))
            ),
            "frozen": float(np.quantile(train_values, quantile)),
            "q_plus_005": float(
                np.quantile(train_values, min(1.0, quantile + 0.05))
            ),
        }
        prediction["predicted_utility"] = base.predict_utility(
            model, test, base.PRICE_FEATURES
        )
        prediction["selected_alpha"] = float(choice["alpha"])
        prediction["selected_quantile"] = quantile
        prediction["selected_threshold"] = thresholds["frozen"]
        prediction["selected_route"] = route
        prediction["route_eligible"] = base.route_mask(prediction, route)
        prediction["selected"] = (
            prediction["route_eligible"]
            & prediction["predicted_utility"].ge(thresholds["frozen"])
        )
        prediction["selected_q_minus_005"] = (
            prediction["route_eligible"]
            & prediction["predicted_utility"].ge(thresholds["q_minus_005"])
        )
        prediction["selected_q_plus_005"] = (
            prediction["route_eligible"]
            & prediction["predicted_utility"].ge(thresholds["q_plus_005"])
        )
        report_choice = {
            **choice,
            "threshold": thresholds["frozen"],
            "thresholds": thresholds,
        }
    report = {
        "model_route": "quantile_utility",
        "held_asset": held_asset,
        "outer_fold": outer_fold,
        "train_rows": int(len(train)),
        "train_assets": train["asset"].value_counts().to_dict(),
        "train_start": train["signal_ts"].min(),
        "train_end": train["signal_ts"].max(),
        "test_rows": int(len(test)),
        "test_start": test["signal_ts"].min(),
        "test_end": test["signal_ts"].max(),
        "choice": report_choice,
        "selected_rows": int(prediction["selected"].sum()),
        "inner_scores": inner_scores,
        "permutation_importance": {},
    }
    print(
        "OUTER_FOLD_COMPLETE "
        f"route=quantile_utility asset={held_asset} fold={outer_fold} "
        f"selected={report['selected_rows']} "
        f"choice={choice if choice is not None else 'NO_SELECTION'}"
    )
    return prediction, report


def run_quantile_oof(
    base,
    events: pd.DataFrame,
    *,
    max_workers: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    blocks = base.time_blocks(events, initial_fraction=0.40, blocks=4)
    tasks = [
        (asset, fold, first_test, last_test)
        for asset in FRESH_ASSETS
        for fold, first_test, last_test in blocks
    ]
    results: list[tuple[pd.DataFrame, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                evaluate_quantile_fold,
                base,
                events=events,
                held_asset=asset,
                outer_fold=fold,
                first_test=first_test,
                last_test=last_test,
            )
            for asset, fold, first_test, last_test in tasks
        ]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(
        key=lambda item: (
            FRESH_ASSETS.index(str(item[1]["held_asset"])),
            int(item[1]["outer_fold"]),
        )
    )
    oof = pd.concat([frame for frame, _ in results], ignore_index=True)
    if oof["event_id"].duplicated().any():
        raise RuntimeError("QUML OOF contains duplicate events")
    return oof, [report for _, report in results]


def quantile_choice_frequency(reports: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for report in reports:
        choice = report["choice"]
        if choice is None:
            counts["NO_SELECTION"] += 1
            continue
        counts[
            f"alpha={float(choice['alpha']):.0f}|"
            f"quantile={float(choice['quantile']):.2f}|"
            f"route={choice['route']}"
        ] += 1
    return dict(sorted(counts.items()))


def quantile_sensitivity(base, oof: pd.DataFrame) -> dict[str, Any]:
    return {
        "-0.05": base.return_metrics(
            oof.loc[oof["selected_q_minus_005"]], "z_8bps"
        ),
        "frozen": base.return_metrics(oof.loc[oof["selected"]], "z_8bps"),
        "+0.05": base.return_metrics(
            oof.loc[oof["selected_q_plus_005"]], "z_8bps"
        ),
    }


def apply_gate(
    *,
    capacity: dict[str, Any],
    quantile: dict[str, Any],
    delta: dict[str, Any],
) -> dict[str, Any]:
    sides = quantile["side_counts"]
    combined_chosen = any(
        "route=combined" in key and count > 0
        for key, count in quantile["choice_frequency"].items()
    )
    direction_coverage = (
        min(sides.values()) >= 50
        if combined_chosen
        else max(sides.values()) >= 50
    )
    variants = quantile["variants"]
    checks = {
        "p0_capacity": bool(capacity["p0_capacity_pass"]),
        "accepted_total_and_per_asset": bool(
            int(quantile["selected_events"]) >= 160
            and all(
                int(quantile["per_asset"][asset]["selected"]["events"]) >= 15
                for asset in FRESH_ASSETS
            )
        ),
        "direction_coverage": bool(direction_coverage),
        "time_block_coverage": int(quantile["selected_90d_blocks"]) >= 24,
        "main_economics": bool(
            float(quantile["main"]["mean"]) > 0.0
            and float(quantile["main"]["profit_factor"]) >= 1.15
        ),
        "positive_assets": int(quantile["positive_asset_count"]) >= 6,
        "positive_outer_folds": int(quantile["positive_outer_fold_count"]) >= 24,
        "ranking": bool(
            math.isfinite(float(quantile["ranking_spearman"]))
            and float(quantile["ranking_spearman"]) > 0.05
            and int(quantile["positive_ranking_asset_count"]) >= 6
        ),
        "cluster_bootstrap": float(
            quantile["cluster_bootstrap"]["positive_probability"]
        )
        >= 0.90,
        "quantile_over_absolute_control": float(delta["positive_probability"])
        >= 0.90,
        "stress_variants": bool(
            all(
                float(variants[column]["mean"]) > 0.0
                and float(variants[column]["profit_factor"]) >= 1.05
                for column in ("z_4bps", "z_funding_off", "z_lag1")
            )
            and float(quantile["lag_executable_rate"]) >= 0.75
        ),
        "per_asset_dual_improvement": int(
            quantile["dual_improved_asset_count"]
        )
        >= 5,
        "hype_lock": True,
    }
    return {"checks": checks, "development_gate_pass": bool(all(checks.values()))}


def final_quantile_choice(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    choices = [
        report["choice"] for report in reports if report["choice"] is not None
    ]
    if not choices:
        return None
    counts: Counter[tuple[float, float, str]] = Counter(
        (
            float(choice["alpha"]),
            float(choice["quantile"]),
            str(choice["route"]),
        )
        for choice in choices
    )
    route_rank = {"combined": 2, "long_only": 1, "short_only": 0}
    selected = max(
        counts,
        key=lambda item: (
            counts[item],
            item[1],
            item[0],
            route_rank[item[2]],
        ),
    )
    return {
        "alpha": selected[0],
        "quantile": selected[1],
        "route": selected[2],
        "outer_fold_votes": counts[selected],
    }


def frozen_model_state(
    base,
    events: pd.DataFrame,
    reports: list[dict[str, Any]],
    *,
    event_identity: str,
) -> dict[str, Any]:
    choice = final_quantile_choice(reports)
    if choice is None:
        raise RuntimeError("Cannot freeze QUML without an outer choice")
    model = base.fit_model(
        events,
        base.PRICE_FEATURES,
        float(choice["alpha"]),
    )
    threshold = train_quantile_threshold(
        base,
        model,
        events,
        quantile=float(choice["quantile"]),
        route=str(choice["route"]),
    )
    if threshold is None:
        raise RuntimeError("Cannot freeze QUML threshold")
    scaler = model.named_steps["scale"]
    estimator = model.named_steps["model"]
    return {
        "schema_version": "binance-1d-ma7-quml-model-v1",
        "created_at_utc": datetime.now(UTC),
        "development_end_exclusive": END_EXCLUSIVE,
        "assets": list(ALL_ASSETS),
        "fresh_outer_assets": list(FRESH_ASSETS),
        "event_identity_sha256": event_identity,
        "features": list(base.PRICE_FEATURES),
        "target": "z_8bps",
        "choice": choice | {"threshold": threshold},
        "train_rows": int(len(events)),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficient": estimator.coef_.tolist(),
        "intercept": float(estimator.intercept_),
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }


def write_outputs(
    *,
    events: pd.DataFrame,
    capacity: dict[str, Any],
    quantile_oof: pd.DataFrame,
    control_oof: pd.DataFrame,
    summary: dict[str, Any],
    report: dict[str, Any],
    frozen: dict[str, Any] | None,
) -> dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "events": OUTPUT_DIR / "p0_events.parquet",
        "capacity": OUTPUT_DIR / "p0_capacity.json",
        "quantile_oof": OUTPUT_DIR / "p1_quantile_oof.parquet",
        "absolute_control_oof": OUTPUT_DIR / "p1_absolute_control_oof.parquet",
        "summary": OUTPUT_DIR / "p1_summary.json",
        "report": OUTPUT_DIR / "p1_report.json",
    }
    events.to_parquet(paths["events"], index=False)
    quantile_oof.to_parquet(paths["quantile_oof"], index=False)
    control_oof.to_parquet(paths["absolute_control_oof"], index=False)
    write_json(paths["capacity"], capacity)
    write_json(paths["summary"], summary)
    write_json(paths["report"], report)
    if frozen is not None:
        paths["frozen_model"] = OUTPUT_DIR / "p1_frozen_model.json"
        write_json(paths["frozen_model"], frozen)
    files = {
        name: {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
        for name, path in paths.items()
    }
    manifest = {
        "schema_version": "binance-1d-ma7-quml-p1-manifest-v1",
        "created_at_utc": datetime.now(UTC),
        "files": files,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    (OUTPUT_DIR / "manifest.sha256").write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    return {
        **{name: details["sha256"] for name, details in files.items()},
        "manifest": sha256_path(manifest_path),
    }


def enforce_fold_local_aggregate_pipeline() -> None:
    raise RuntimeError(
        "QUML P1 is fail-closed: the historical 21-asset event panel computed "
        "leave-target-out market features before outer and inner held-asset "
        "exclusion. That violates the frozen full-history holdout rule, so the "
        "exposed P1 result is invalidated. A future evaluation needs a new "
        "holdout and fold-local aggregate reconstruction."
    )


def main() -> None:
    args = parse_args()
    if args.max_workers < 1 or args.max_workers > 20:
        raise ValueError("--max-workers must be in [1, 20]")
    if args.bootstrap_samples < 100:
        raise ValueError("--bootstrap-samples must be >=100")
    if "HYPE" in ALL_ASSETS:
        raise RuntimeError("HYPE data is forbidden")
    event_capacity, source_audit = verify_inputs()
    base = load_base_module()
    base.ASSETS = FRESH_ASSETS
    events = pd.read_parquet(EVENT_PATH)
    for column in ("cross_ts", "signal_ts", "entry_ts", "exit_ts"):
        events[column] = pd.to_datetime(events[column], utc=True)
    if set(events["asset"].astype(str)) != set(ALL_ASSETS):
        raise RuntimeError("QUML event universe changed")
    if events["signal_ts"].ge(END_EXCLUSIVE).any():
        raise RuntimeError("Post-cutoff event entered QUML")
    event_identity = base.event_identity_sha256(events)
    if event_identity != event_capacity["event_identity_sha256"]:
        raise RuntimeError("QUML event identity changed")
    fresh = events.loc[events["asset"].isin(FRESH_ASSETS)]
    per_asset = {
        asset: int(fresh["asset"].eq(asset).sum()) for asset in FRESH_ASSETS
    }
    sides = {
        "long": int(fresh["side"].gt(0).sum()),
        "short": int(fresh["side"].lt(0).sum()),
    }
    checks = {
        "event_builder_capacity": bool(event_capacity["p0_capacity_pass"]),
        "fresh_total": len(fresh) >= 1_600,
        "fresh_per_asset": all(count >= 180 for count in per_asset.values()),
        "fresh_directions": min(sides.values()) >= 650,
        "feature_contract": (
            len(base.PRICE_FEATURES) == 47
            and events[list(base.PRICE_FEATURES)].notna().all().all()
            and np.isfinite(
                events[list(base.PRICE_FEATURES)].to_numpy(dtype="float64")
            ).all()
        ),
        "source_identity": bool(source_audit),
        "hype_lock": True,
    }
    capacity = {
        "schema_version": "binance-1d-ma7-quml-p0-v1",
        "created_at_utc": datetime.now(UTC),
        "events_all": int(len(events)),
        "events_fresh": int(len(fresh)),
        "fresh_per_asset": per_asset,
        "fresh_side_counts": sides,
        "event_identity_sha256": event_identity,
        "source_audit": source_audit,
        "checks": checks,
        "p0_capacity_pass": bool(all(checks.values())),
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    if not args.no_write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        events.to_parquet(OUTPUT_DIR / "p0_events.parquet", index=False)
        write_json(OUTPUT_DIR / "p0_capacity.json", capacity)
    print("P0_CAPACITY " + json.dumps(json_ready(capacity), ensure_ascii=False))
    if args.capacity_only:
        return
    if not capacity["p0_capacity_pass"]:
        raise RuntimeError("QUML P0 failed; P1 is forbidden")
    enforce_fold_local_aggregate_pipeline()

    quantile_oof, quantile_reports = run_quantile_oof(
        base,
        events,
        max_workers=args.max_workers,
    )
    absolute_oof, absolute_reports = base.run_outer_oof(
        events,
        model_route="absolute_price_control",
        features=base.PRICE_FEATURES,
        max_workers=args.max_workers,
    )
    quantile_summary = base.summarize_model_route(
        quantile_oof,
        quantile_reports,
        samples=args.bootstrap_samples,
    )
    quantile_summary["choice_frequency"] = quantile_choice_frequency(
        quantile_reports
    )
    quantile_summary["quantile_sensitivity"] = quantile_sensitivity(
        base, quantile_oof
    )
    absolute_summary = base.summarize_model_route(
        absolute_oof,
        absolute_reports,
        samples=args.bootstrap_samples,
    )
    delta = base.delta_bootstrap(
        quantile_oof,
        absolute_oof,
        samples=args.bootstrap_samples,
    )
    gate = apply_gate(
        capacity=capacity,
        quantile=quantile_summary,
        delta=delta,
    )
    status = (
        "DEVELOPMENT_GATE_PASSED"
        if gate["development_gate_pass"]
        else "DEVELOPMENT_HARD_GATE_FAILED"
    )
    summary = {
        "schema_version": "binance-1d-ma7-quml-p1-summary-v1",
        "created_at_utc": datetime.now(UTC),
        "status": status,
        "capacity": capacity,
        "quantile_utility": quantile_summary,
        "absolute_control": absolute_summary,
        "quantile_vs_absolute_control": delta,
        "development_gate": gate,
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    report = {
        **summary,
        "contract": {
            "legacy_training_assets": list(LEGACY_ASSETS),
            "fresh_outer_assets": list(FRESH_ASSETS),
            "all_assets": list(ALL_ASSETS),
            "development_end_exclusive": END_EXCLUSIVE,
            "event_identity_sha256": event_identity,
            "features": list(base.PRICE_FEATURES),
            "target": "z_8bps",
            "alpha": list(base.ALPHA_GRID),
            "quantile": list(QUANTILE_GRID),
            "absolute_threshold": list(base.THRESHOLD_GRID),
            "routes": list(base.ROUTES),
            "bootstrap_samples": args.bootstrap_samples,
        },
        "quantile_outer_reports": quantile_reports,
        "absolute_outer_reports": absolute_reports,
    }
    frozen = (
        frozen_model_state(
            base,
            events,
            quantile_reports,
            event_identity=event_identity,
        )
        if gate["development_gate_pass"]
        else None
    )
    hashes: dict[str, str] = {}
    if not args.no_write:
        hashes = write_outputs(
            events=events,
            capacity=capacity,
            quantile_oof=quantile_oof,
            control_oof=absolute_oof,
            summary=summary,
            report=report,
            frozen=frozen,
        )
    print(
        json.dumps(
            json_ready(
                {
                    "status": status,
                    "development_gate": gate,
                    "artifact_sha256": hashes,
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
