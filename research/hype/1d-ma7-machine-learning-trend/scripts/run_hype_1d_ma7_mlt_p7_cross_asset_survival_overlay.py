from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-mlt-p7-cross-asset-survival-overlay-contract-2026-08-28.md"
)
P4_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py"
P5_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p5_opportunity_repair_lifecycle.py"
P6_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p6_v7_anchor_three_head_lifecycle.py"

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
EXPERIMENT = "P7_CROSS_ASSET_SURVIVAL_OVERLAY"
RUN_DATE = "2026-08-28"
PREFIX = "hype_1d_ma7_mlt_p7_cross_asset_survival_overlay_2026-08-28"
TRAIN_DAYS = 365
TOTAL_DAYS = 446
DEVELOPMENT_DAYS = 285
PURGE_DAYS = 3
HOLDOUT_DAYS = 81
TRAIN_TERMINAL = pd.Timestamp("2026-05-31T00:00:00Z")
DEVELOPMENT_BOUNDARY = pd.Timestamp("2026-03-12T00:00:00Z")
HOLDOUT_TERMINAL = pd.Timestamp("2026-08-20T00:00:00Z")
OOF_WINDOWS = (
    (pd.Timestamp("2025-10-03T00:00:00Z"), pd.Timestamp("2025-11-12T00:00:00Z")),
    (pd.Timestamp("2025-11-12T00:00:00Z"), pd.Timestamp("2025-12-22T00:00:00Z")),
    (pd.Timestamp("2025-12-22T00:00:00Z"), pd.Timestamp("2026-01-31T00:00:00Z")),
    (pd.Timestamp("2026-01-31T00:00:00Z"), pd.Timestamp("2026-03-12T00:00:00Z")),
)
RANDOM_STATE = 20260828
EXTEND_START_THRESHOLD = 0.60
SURVIVAL_EXIT_THRESHOLD = 0.35
LOW_SURVIVAL_CONFIRMATIONS = 2
SLIPPAGE = 0.0004
TARGET = "survival_3d"
COMPLETE = "survival_label_complete"

DONOR_ASSETS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")
DONOR_SPECS = {
    "BTCUSDT": {
        "klines": ROOT
        / "research/btc/1h-adaptive-regime/artifacts/btc_binance_1h_closed_klines_2y.parquet",
        "funding": ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp/symbol=btc_usdt_usdt/funding.parquet",
    },
    "ETHUSDT": {
        "klines": ROOT
        / "research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_closed_klines_2y.parquet",
        "funding": ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp/symbol=eth_usdt_usdt/funding.parquet",
    },
    "BNBUSDT": {
        "klines": ROOT
        / "research/bnb/1h-adaptive-regime/artifacts/bnb_binance_1h_closed_klines_2y.parquet",
        "funding": ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp/symbol=bnb_usdt_usdt/funding.parquet",
    },
    "SOLUSDT": {
        "klines": ROOT
        / "research/sol/1h-adaptive-regime/artifacts/sol_binance_1h_closed_klines_2y.parquet",
        "funding": ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp/symbol=sol_usdt_usdt/funding.parquet",
    },
}

MANIFEST_PATH = ARTIFACT_DIR / f"{PREFIX}_development_manifest.json"


class ConstantProbabilityModel:
    def __init__(self, probability: float):
        self.probability = float(probability)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        p = np.full(len(frame), self.probability, dtype=float)
        return np.column_stack([1.0 - p, p])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {EXPERIMENT}.")
    parser.add_argument("--stage", choices=("develop", "validate"), default="develop")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.ndarray):
        return [sanitize(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: Any) -> None:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def write_sidecar(path: Path) -> None:
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{sha256(path)}  {path.name}\n", encoding="utf-8"
    )


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def survival_features(p5: Any, p6: Any) -> list[str]:
    names = list(p5.ROOT_FEATURES) + list(p6.ENTRY_ADDITIONS) + list(p6.SURVIVAL_ADDITIONS)
    if len(names) != 36:
        raise RuntimeError(f"P7 survival features must stay at 36, got {len(names)}")
    return names


def timestamp_series(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["ts"], utc=True)


def complete_rows_by_ts(
    frame: pd.DataFrame,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    ts = timestamp_series(frame)
    mask = frame[COMPLETE].astype(bool) & frame[TARGET].notna()
    if start is not None:
        mask &= ts >= start
    if end is not None:
        mask &= ts < end
    return frame.loc[mask].copy()


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=600,
                    max_depth=5,
                    min_samples_leaf=6,
                    max_features=0.75,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def fit_model(frame: pd.DataFrame, features: list[str]) -> Any:
    y = frame[TARGET].astype(int)
    if y.empty:
        raise RuntimeError("empty survival training rows")
    if y.nunique() < 2:
        return ConstantProbabilityModel(float(y.mean()))
    model = make_model()
    model.fit(frame[features], y)
    return model


def probability(model: Any, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    if frame.empty:
        return np.asarray([], dtype=float)
    return np.asarray(model.predict_proba(frame[features])[:, 1], dtype=float)


def classification_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    y = np.asarray(actual, dtype=int)
    p = np.asarray(predicted, dtype=float)
    binary = p >= 0.5
    return {
        "rows": len(y),
        "positive_rate": float(y.mean()) if len(y) else math.nan,
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else math.nan,
        "brier": float(brier_score_loss(y, p)) if len(y) else math.nan,
        "accuracy_at_0_5": float(accuracy_score(y, binary)) if len(y) else math.nan,
        "balanced_accuracy_at_0_5": (
            float(balanced_accuracy_score(y, binary)) if len(np.unique(y)) == 2 else math.nan
        ),
        "precision_at_0_5": float(precision_score(y, binary, zero_division=0)),
        "recall_at_0_5": float(recall_score(y, binary, zero_division=0)),
        "f1_at_0_5": float(f1_score(y, binary, zero_division=0)),
    }


def calendar_oof(frame: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    outputs: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    for fold, (start, end) in enumerate(OOF_WINDOWS, start=1):
        train_end = start - pd.Timedelta(days=PURGE_DAYS)
        train = complete_rows_by_ts(frame, end=train_end)
        test = complete_rows_by_ts(frame, start=start, end=end)
        if test.empty:
            continue
        model = fit_model(train, features)
        part = test[["asset", "index", "ts", TARGET]].copy()
        part["fold"] = fold
        part["probability"] = probability(model, test, features)
        outputs.append(part)
        audits.append(
            {
                "fold": fold,
                "train_end_exclusive": train_end.isoformat(),
                "train_rows": len(train),
                "train_positive_rate": float(train[TARGET].mean()),
                "test_start": start.isoformat(),
                "test_end_exclusive": end.isoformat(),
                "test_rows": len(test),
                "assets": sorted(test["asset"].astype(str).unique()),
            }
        )
    if not outputs:
        return pd.DataFrame(), {"rows": 0, "auc": math.nan, "folds": audits, "by_asset": {}}
    output = pd.concat(outputs, ignore_index=True)
    metrics = classification_metrics(output[TARGET].astype(int), output["probability"].astype(float))
    metrics["folds"] = audits
    metrics["by_asset"] = {
        asset: classification_metrics(
            part[TARGET].astype(int), part["probability"].astype(float)
        )
        for asset, part in output.groupby("asset", sort=True)
    }
    return output, metrics


def load_cut_frame(path: Path, cutoff: pd.Timestamp, time_column: str) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame[time_column] = pd.to_datetime(frame[time_column], utc=True)
    if "is_closed" in frame.columns:
        frame = frame.loc[frame["is_closed"].astype(bool)]
    frame = frame.loc[frame[time_column].le(cutoff)].sort_values(time_column).reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"{path} is empty after cutoff {cutoff}")
    return frame


def load_donor_context(
    original: Any,
    orig_engine: Any,
    base: Any,
    search: Any,
    parent: Any,
    asset: str,
    spec: dict[str, Path],
    cutoff: pd.Timestamp,
) -> Any:
    hourly = load_cut_frame(spec["klines"], cutoff, "ts")
    if hourly["ts"].duplicated().any():
        raise RuntimeError(f"{asset} hourly contains duplicate timestamps")
    if not hourly["ts"].diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise RuntimeError(f"{asset} hourly is not continuous after cutoff")
    funding = load_cut_frame(spec["funding"], cutoff, "ts")[["ts", "funding_rate"]].copy()
    hourly_quality = {
        "symbol": asset,
        "rows": int(len(hourly)),
        "first_ts": hourly["ts"].iloc[0].isoformat(),
        "last_ts": hourly["ts"].iloc[-1].isoformat(),
        "missing_hourly_bars": 0,
        "blocker_count": 0,
    }
    funding_quality = {
        "symbol": asset,
        "rows": int(len(funding)),
        "first_ts": funding["ts"].iloc[0].isoformat(),
        "last_ts": funding["ts"].iloc[-1].isoformat(),
        "blocker_count": 0,
    }
    book = base.build_book(
        parent,
        hourly,
        hourly_quality,
        funding,
        funding_quality,
        phase_hours=0,
    )
    if pd.Timestamp(book.terminal_ts) != cutoff:
        raise RuntimeError(
            f"{asset} terminal drifted: {book.terminal_ts} != {cutoff}"
        )
    features = search.build_features(book, hourly, funding)
    daily = pd.DataFrame(
        {
            "open": book.open,
            "high": book.high,
            "low": book.low,
            "close": book.close,
        },
        index=pd.DatetimeIndex(book.ts),
    )
    daily = orig_engine.add_daily_indicators(
        daily,
        ma_period=7,
        atr_period=7,
        rsi_period=6,
        slope_lookback=1,
        expected_phase_hour=0,
    )
    audit = {
        "symbol": asset,
        "hourly_start": hourly["ts"].iloc[0].isoformat(),
        "hourly_end": hourly["ts"].iloc[-1].isoformat(),
        "hourly_rows": int(len(hourly)),
        "funding_start": funding["ts"].iloc[0].isoformat(),
        "funding_end": funding["ts"].iloc[-1].isoformat(),
        "funding_rows": int(len(funding)),
        "daily_start": pd.Timestamp(book.ts[0]).isoformat(),
        "daily_end": pd.Timestamp(book.ts[-1]).isoformat(),
        "daily_rows": int(book.count),
        "terminal_open": pd.Timestamp(book.terminal_ts).isoformat(),
        "klines": str(spec["klines"].relative_to(ROOT)),
        "klines_sha256": sha256(spec["klines"]),
        "funding": str(spec["funding"].relative_to(ROOT)),
        "funding_sha256": sha256(spec["funding"]),
    }
    market = original.MarketData(book, features, daily, hourly, funding, audit)
    return SimpleNamespace(book=book, features=features, market=market)


def assert_donor_pool(frame: pd.DataFrame) -> None:
    assets = tuple(sorted(frame["asset"].astype(str).unique()))
    expected = tuple(sorted(DONOR_ASSETS))
    if assets != expected:
        raise RuntimeError(f"donor pool drifted: {assets} != {expected}")
    if any("HYPE" in asset.upper() for asset in assets):
        raise RuntimeError("HYPE leaked into the donor training pool")


def build_donor_survival_pool(
    p4: Any,
    p5: Any,
    p6: Any,
    original: Any,
    engine: Any,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Path]]:
    orig_engine, base, search = original.modules()
    parent = base.load_parent()
    parts: list[pd.DataFrame] = []
    coverage: dict[str, Any] = {}
    label_paths: dict[str, Path] | None = None
    for asset, spec in DONOR_SPECS.items():
        log(f"P7 building {asset} survival rows")
        context = load_donor_context(
            original, orig_engine, base, search, parent, asset, spec, TRAIN_TERMINAL
        )
        frame, _, label_paths = p6.build_frame(p5, p4, engine, context)
        rows = p6.build_survival_rows(frame, 0, int(context.book.count))
        rows.insert(0, "asset", asset)
        parts.append(rows)
        complete = rows.loc[rows[COMPLETE].astype(bool) & rows[TARGET].notna()]
        coverage[asset] = {
            "daily_rows": int(context.book.count),
            "daily_start": pd.Timestamp(context.book.ts[0]).isoformat(),
            "daily_end": pd.Timestamp(context.book.ts[-1]).isoformat(),
            "terminal": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "hourly_end": context.market.audit["hourly_end"],
            "funding_end": context.market.audit["funding_end"],
            "survival_rows": int(len(rows)),
            "complete_rows": int(len(complete)),
            "positive_rate": float(complete[TARGET].mean()) if len(complete) else math.nan,
            "klines": context.market.audit["klines"],
            "klines_sha256": context.market.audit["klines_sha256"],
        }
    if label_paths is None:
        raise RuntimeError("donor label engines were not loaded")
    pool = pd.concat(parts, ignore_index=True)
    assert_donor_pool(pool)
    return pool, coverage, label_paths


def load_hype_context(p4: Any, *, train_only: bool) -> tuple[Any, Any, Any, Any, Any]:
    if train_only:
        diag, v6, engine, adapter, context = p4.load_dependencies(train_only=True)
        if context.book.count != TRAIN_DAYS:
            raise RuntimeError("P7 HYPE development context is not 365 days")
        if pd.Timestamp(context.book.terminal_ts) != TRAIN_TERMINAL:
            raise RuntimeError("P7 HYPE development terminal drift")
        return diag, v6, engine, adapter, context
    diag = p4.load_module(p4.DIAGNOSTIC, "hype_p7_v7_1_diag")
    v6 = diag.load_module(diag.V6_ABLATION_PATH, "hype_p7_v7_1_v6")
    engine = diag.load_module(diag.ENGINE_PATH, "hype_p7_v7_1_engine")
    adapter = diag.load_module(diag.ADAPTER_PATH, "hype_p7_v7_1_adapter")
    frozen = adapter.load_context()
    original = frozen.original_harness
    original.HOURLY_CUTOFF = HOLDOUT_TERMINAL
    original.FUNDING_CUTOFF = HOLDOUT_TERMINAL
    from dataclasses import replace

    market = original.load_market(0)
    context = replace(
        frozen,
        market=market,
        short_config=replace(frozen.short_config, cooldown_days=3),
    )
    if context.book.count != TOTAL_DAYS:
        raise RuntimeError(
            f"P7 frozen holdout expected {TOTAL_DAYS} days, got {context.book.count}"
        )
    if pd.Timestamp(context.book.terminal_ts) != HOLDOUT_TERMINAL:
        raise RuntimeError("P7 reused holdout terminal drifted past 2026-08-20")
    return diag, v6, engine, adapter, context


def rewrite_p7_exit_reasons(
    trades: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> None:
    for trade in trades:
        reason = str(trade.get("exit_reason", ""))
        if "_p6_dynamic_survival" in reason:
            trade["exit_reason"] = reason.replace("_p6_dynamic_survival", "_p7_dynamic_survival")
    for decision in decisions:
        for key in ("p6_exit_reason", "exit_reason"):
            value = decision.get(key)
            if isinstance(value, str) and "_p6_dynamic_survival" in value:
                decision[key] = value.replace("_p6_dynamic_survival", "_p7_dynamic_survival")
        if "p6_exit_ts" in decision:
            decision["p7_exit_ts"] = decision["p6_exit_ts"]


def apply_survival_overlay(
    p4: Any,
    p6: Any,
    context: Any,
    frame: pd.DataFrame,
    teacher_trades: list[dict[str, Any]],
    survival_scores: pd.DataFrame,
    right: int,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    survival_map = p6.probability_map(survival_scores)
    core, decisions = p6.extend_core_trades(
        p4, context, frame, teacher_trades, survival_map, right
    )
    if len(core) != len(teacher_trades):
        raise RuntimeError("survival-only overlay changed the V7.1 trade count")
    rewrite_p7_exit_reasons(core, decisions)
    if any(str(trade.get("source", "")).endswith("supplemental") for trade in core):
        raise RuntimeError("P7 overlay inserted a supplemental trade")
    return core, pd.DataFrame(decisions)


def model_metrics(scored: pd.DataFrame) -> dict[str, Any]:
    known = scored.loc[scored[COMPLETE].astype(bool) & scored[TARGET].notna()]
    if known.empty:
        return {"rows": 0, "auc": math.nan}
    return classification_metrics(known[TARGET].astype(int), known["probability"].astype(float))


def recent_slices(
    p4: Any,
    p6: Any,
    diag: Any,
    v6: Any,
    engine: Any,
    context: Any,
    model: Any,
    features: list[str],
    frame: pd.DataFrame,
    left: int,
    right: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for label, days in {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}.items():
        slice_left = max(left, right - days)
        teacher = p4.run_teacher(diag, v6, engine, context, slice_left, right)
        teacher_trades = list(teacher.result.raw.trades)
        survival = p6.build_survival_rows(frame, slice_left, right)
        scores = p6.score_rows(model, survival, features, slice_left, right)
        trades, _ = apply_survival_overlay(
            p4, p6, context, frame, teacher_trades, scores, right
        )
        output[label] = {
            "available_days": right - slice_left,
            "p7": p4.replay_metrics(v6, context, trades),
            "v7_1": p4.replay_metrics(v6, context, teacher_trades),
        }
    return output


def attach_replay_returns(
    trades: list[dict[str, Any]], metrics: dict[str, Any]
) -> list[dict[str, Any]]:
    enriched = copy.deepcopy(trades)
    returns = list(metrics["per_trade_returns"])
    if len(enriched) != len(returns):
        raise RuntimeError("trade count and replay return count disagree")
    for trade, net_return in zip(enriched, returns):
        trade["net_return"] = float(net_return)
    return enriched


def source_manifest(
    p4: Any, diag: Any, label_paths: dict[str, Path], donor_coverage: dict[str, Any]
) -> dict[str, Any]:
    paths = {
        "contract": CONTRACT,
        "script": Path(__file__),
        "p4_runtime": P4_SCRIPT,
        "p5_feature_runtime": P5_SCRIPT,
        "p6_runtime": P6_SCRIPT,
        "v7_1_diagnostic": Path(p4.DIAGNOSTIC),
        "v7_1_engine": Path(diag.ENGINE_PATH),
        "v7_1_adapter": Path(diag.ADAPTER_PATH),
        "v6_replay": Path(diag.V6_ABLATION_PATH),
        **label_paths,
    }
    sources = {
        name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
        for name, path in paths.items()
    }
    for asset, spec in DONOR_SPECS.items():
        sources[f"{asset.lower()}_klines"] = {
            "path": str(spec["klines"].relative_to(ROOT)),
            "sha256": sha256(spec["klines"]),
        }
        sources[f"{asset.lower()}_funding"] = {
            "path": str(spec["funding"].relative_to(ROOT)),
            "sha256": sha256(spec["funding"]),
        }
    sources["donor_coverage"] = donor_coverage
    return sources


def verify_manifest(manifest: dict[str, Any]) -> None:
    sidecar = MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".sha256")
    if not sidecar.exists() or sidecar.read_text(encoding="utf-8").split()[0] != sha256(MANIFEST_PATH):
        raise RuntimeError("development manifest hash mismatch")
    for name, source in manifest["sources"].items():
        if name == "donor_coverage" or not isinstance(source, dict) or "path" not in source:
            continue
        path = ROOT / source["path"]
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"frozen source drift: {path}")


def overlay_bundle(
    p4: Any,
    p5: Any,
    p6: Any,
    v6: Any,
    context: Any,
    frame: pd.DataFrame,
    episodes: list[dict[str, Any]],
    teacher_trades: list[dict[str, Any]],
    model: Any,
    features: list[str],
    left: int,
    right: int,
) -> dict[str, Any]:
    survival = p6.build_survival_rows(frame, left, right)
    scores = p6.score_rows(model, survival, features, left, right)
    trades, decisions = apply_survival_overlay(
        p4, p6, context, frame, teacher_trades, scores, right
    )
    metrics = p4.replay_metrics(v6, context, trades)
    teacher_metrics = p4.replay_metrics(v6, context, teacher_trades)
    trades = attach_replay_returns(trades, metrics)
    teacher_out = attach_replay_returns(copy.deepcopy(teacher_trades), teacher_metrics)
    capture, capture_rows = p5.episode_capture(context, episodes, trades, left, right)
    teacher_capture, teacher_capture_rows = p5.episode_capture(
        context, episodes, teacher_out, left, right
    )
    return {
        "survival": survival,
        "scores": scores,
        "trades": trades,
        "teacher_trades": teacher_out,
        "decisions": decisions,
        "metrics": metrics,
        "teacher_metrics": teacher_metrics,
        "capture": capture,
        "capture_rows": capture_rows,
        "teacher_capture": teacher_capture,
        "teacher_capture_rows": teacher_capture_rows,
        "head_metrics": model_metrics(scores),
        "extended_trades": int(sum(bool(row.get("extended")) for row in decisions.to_dict("records"))),
    }


def develop() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    p4 = load_module(P4_SCRIPT, "hype_p7_p4_develop")
    p5 = load_module(P5_SCRIPT, "hype_p7_p5_develop")
    p6 = load_module(P6_SCRIPT, "hype_p7_p6_develop")
    features = survival_features(p5, p6)
    diag, v6, engine, adapter, hype = load_hype_context(p4, train_only=True)
    if pd.Timestamp(hype.market.audit["hourly_end"]) > TRAIN_TERMINAL:
        raise RuntimeError("P7 development read HYPE holdout hourly bars")
    if pd.Timestamp(hype.market.audit["funding_end"]) > TRAIN_TERMINAL:
        raise RuntimeError("P7 development read HYPE holdout funding")

    donor_pool, donor_coverage, label_paths = build_donor_survival_pool(
        p4, p5, p6, hype.original_harness, engine
    )
    confirmation_fit = complete_rows_by_ts(
        donor_pool, end=DEVELOPMENT_BOUNDARY - pd.Timedelta(days=PURGE_DAYS)
    )
    full_fit = complete_rows_by_ts(donor_pool)
    oof_frame, oof_metrics = calendar_oof(donor_pool, features)
    confirmation_model = fit_model(confirmation_fit, features)
    full_model = fit_model(full_fit, features)

    log("P7 scoring HYPE confirmation and 365-day transfer overlays")
    hype_frame, hype_episodes, _ = p6.build_frame(p5, p4, engine, hype)
    teacher_full = p4.run_teacher(diag, v6, engine, hype, 0, TRAIN_DAYS)
    teacher_confirmation = p4.run_teacher(diag, v6, engine, hype, DEVELOPMENT_DAYS, TRAIN_DAYS)
    confirmation = overlay_bundle(
        p4,
        p5,
        p6,
        v6,
        hype,
        hype_frame,
        hype_episodes,
        list(teacher_confirmation.result.raw.trades),
        confirmation_model,
        features,
        DEVELOPMENT_DAYS,
        TRAIN_DAYS,
    )
    transfer = overlay_bundle(
        p4,
        p5,
        p6,
        v6,
        hype,
        hype_frame,
        hype_episodes,
        list(teacher_full.result.raw.trades),
        full_model,
        features,
        0,
        TRAIN_DAYS,
    )
    slices = recent_slices(
        p4,
        p6,
        diag,
        v6,
        engine,
        hype,
        full_model,
        features,
        hype_frame,
        0,
        TRAIN_DAYS,
    )
    gate_requirements = {
        "donor_oof_auc_gte_0_60": float(oof_metrics["auc"]) >= 0.60,
        "confirmation_return_gt_v7_1": float(confirmation["metrics"]["net_return_pct"])
        > float(confirmation["teacher_metrics"]["net_return_pct"]),
        "confirmation_capture_gte_v7_1": float(confirmation["capture"]["duration_weighted_capture"])
        >= float(confirmation["teacher_capture"]["duration_weighted_capture"]),
        "confirmation_mdd_within_2pp": float(confirmation["metrics"]["chronological_1h_mdd_pct"])
        >= float(confirmation["teacher_metrics"]["chronological_1h_mdd_pct"]) - 2.0,
        "confirmation_trades_eq_v7_1": int(confirmation["metrics"]["trades"])
        == int(confirmation["teacher_metrics"]["trades"]),
    }
    development_gate = all(gate_requirements.values())
    status = (
        "DEVELOPMENT_PASS_READY_FOR_REUSED_HOLDOUT"
        if development_gate
        else "DEVELOPMENT_FAILED_HOLDOUT_LOCKED"
    )

    paths = {
        "donor_survival_rows": ARTIFACT_DIR / f"{PREFIX}_donor_survival_rows.csv",
        "donor_oof": ARTIFACT_DIR / f"{PREFIX}_donor_oof_predictions.csv",
        "hype_feature_frame": ARTIFACT_DIR / f"{PREFIX}_hype_training_feature_frame.csv",
        "hype_survival_rows": ARTIFACT_DIR / f"{PREFIX}_hype_training_survival_rows.csv",
        "confirmation_scores": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_scores.csv",
        "confirmation_decisions": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_decisions.csv",
        "confirmation_trades": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_trades.csv",
        "full_scores": ARTIFACT_DIR / f"{PREFIX}_training_scores.csv",
        "full_decisions": ARTIFACT_DIR / f"{PREFIX}_training_decisions.csv",
        "full_trades": ARTIFACT_DIR / f"{PREFIX}_training_trades.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_training_v7_1_trades.csv",
        "episode_capture": ARTIFACT_DIR / f"{PREFIX}_training_episode_capture.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_development_summary.json",
    }
    write_csv(paths["donor_survival_rows"], donor_pool)
    write_csv(paths["donor_oof"], oof_frame)
    write_csv(paths["hype_feature_frame"], hype_frame)
    write_csv(paths["hype_survival_rows"], transfer["survival"])
    write_csv(paths["confirmation_scores"], confirmation["scores"])
    write_csv(paths["confirmation_decisions"], confirmation["decisions"])
    write_csv(paths["confirmation_trades"], confirmation["trades"])
    write_csv(paths["full_scores"], transfer["scores"])
    write_csv(paths["full_decisions"], transfer["decisions"])
    write_csv(paths["full_trades"], transfer["trades"])
    write_csv(paths["teacher_trades"], transfer["teacher_trades"])
    write_csv(
        paths["episode_capture"],
        pd.concat(
            [
                transfer["capture_rows"].assign(strategy="P7_TRANSFER"),
                transfer["teacher_capture_rows"].assign(strategy="V7.1"),
                confirmation["capture_rows"].assign(strategy="P7_INTERNAL_CONFIRMATION"),
                confirmation["teacher_capture_rows"].assign(strategy="V7.1_INTERNAL_CONFIRMATION"),
            ],
            ignore_index=True,
        ),
    )
    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "stage": "develop",
        "status": status,
        "research_status": ["diagnostic-only", "reused-holdout", "not promoted", "not live-ready"],
        "data_boundary": {
            "train_days": TRAIN_DAYS,
            "train_start": pd.Timestamp(hype.book.ts[0]),
            "train_last_feature_day": pd.Timestamp(hype.book.ts[-1]),
            "train_terminal": pd.Timestamp(hype.book.terminal_ts),
            "development_boundary": DEVELOPMENT_BOUNDARY,
            "holdout_days": HOLDOUT_DAYS,
            "holdout_terminal": HOLDOUT_TERMINAL,
            "holdout_read": False,
            "hourly_end": hype.market.audit["hourly_end"],
            "funding_end": hype.market.audit["funding_end"],
            "donor_assets": list(DONOR_ASSETS),
            "hype_in_training_pool": False,
        },
        "features": features,
        "labels": {
            "target": TARGET,
            "donor_complete_rows": len(full_fit),
            "donor_positive_rate": float(full_fit[TARGET].mean()),
            "confirmation_fit_rows": len(confirmation_fit),
            "confirmation_fit_end_exclusive": (
                DEVELOPMENT_BOUNDARY - pd.Timedelta(days=PURGE_DAYS)
            ).isoformat(),
        },
        "donor_coverage": donor_coverage,
        "oof": oof_metrics,
        "policy": {
            "heads": ["survival"],
            "entry_overlay": False,
            "reversal_overlay": False,
            "extend_start_threshold": EXTEND_START_THRESHOLD,
            "survival_exit_threshold": SURVIVAL_EXIT_THRESHOLD,
            "low_survival_confirmations": LOW_SURVIVAL_CONFIRMATIONS,
            "eligible_core_exits": sorted(p6.ELIGIBLE_CORE_EXITS),
        },
        "development_gate": {
            "passed": development_gate,
            "requirements": gate_requirements,
            "internal_confirmation": {
                "head_metrics": confirmation["head_metrics"],
                "p7": confirmation["metrics"],
                "v7_1": confirmation["teacher_metrics"],
                "p7_episode_capture": confirmation["capture"],
                "v7_1_episode_capture": confirmation["teacher_capture"],
                "extended_trades": confirmation["extended_trades"],
            },
        },
        "hype_365_transfer_not_a_gate": {
            "head_metrics": transfer["head_metrics"],
            "p7": transfer["metrics"],
            "v7_1": transfer["teacher_metrics"],
            "p7_episode_capture": transfer["capture"],
            "v7_1_episode_capture": transfer["teacher_capture"],
            "extended_trades": transfer["extended_trades"],
            "recent_slices_flat_start": slices,
        },
    }
    write_json(paths["summary"], summary)
    for path in paths.values():
        write_sidecar(path)
    manifest = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "status": status,
        "train_days": TRAIN_DAYS,
        "total_days": TOTAL_DAYS,
        "development_days": DEVELOPMENT_DAYS,
        "purge_days": PURGE_DAYS,
        "holdout_terminal": HOLDOUT_TERMINAL.isoformat(),
        "donor_assets": list(DONOR_ASSETS),
        "hype_in_training_pool": False,
        "features": features,
        "target": TARGET,
        "model": {
            "n_estimators": 600,
            "max_depth": 5,
            "min_samples_leaf": 6,
            "max_features": 0.75,
            "class_weight": "balanced",
            "random_state": RANDOM_STATE,
        },
        "policy": summary["policy"],
        "development_gate": development_gate,
        "holdout_permitted": development_gate,
        "sources": source_manifest(p4, diag, label_paths, donor_coverage),
        "development_artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in paths.items()
        },
    }
    write_json(MANIFEST_PATH, manifest)
    write_sidecar(MANIFEST_PATH)
    return summary


def validate() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError("run --stage develop first")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_manifest(manifest)
    if not manifest.get("holdout_permitted"):
        raise RuntimeError("development gates failed; contract forbids holdout read")

    p4 = load_module(P4_SCRIPT, "hype_p7_p4_validate")
    p5 = load_module(P5_SCRIPT, "hype_p7_p5_validate")
    p6 = load_module(P6_SCRIPT, "hype_p7_p6_validate")
    features = list(manifest["features"])
    donor_path = ROOT / manifest["development_artifacts"]["donor_survival_rows"]["path"]
    donor_pool = pd.read_csv(donor_path)
    assert_donor_pool(donor_pool)
    model = fit_model(complete_rows_by_ts(donor_pool), features)

    diag, v6, engine, _, context = load_hype_context(p4, train_only=False)
    frame, episodes, _ = p6.build_frame(p5, p4, engine, context)
    teacher = p4.run_teacher(diag, v6, engine, context, TRAIN_DAYS, TOTAL_DAYS)
    bundle = overlay_bundle(
        p4,
        p5,
        p6,
        v6,
        context,
        frame,
        episodes,
        list(teacher.result.raw.trades),
        model,
        features,
        TRAIN_DAYS,
        TOTAL_DAYS,
    )
    slices = recent_slices(
        p4,
        p6,
        diag,
        v6,
        engine,
        context,
        model,
        features,
        frame,
        TRAIN_DAYS,
        TOTAL_DAYS,
    )
    won = bool(
        float(bundle["metrics"]["net_return_pct"])
        > float(bundle["teacher_metrics"]["net_return_pct"])
        and float(bundle["capture"]["duration_weighted_capture"])
        > float(bundle["teacher_capture"]["duration_weighted_capture"])
        and float(bundle["metrics"]["chronological_1h_mdd_pct"])
        >= float(bundle["teacher_metrics"]["chronological_1h_mdd_pct"]) - 2.0
        and int(bundle["metrics"]["trades"]) == int(bundle["teacher_metrics"]["trades"])
    )
    status = "EDUCATIONAL_REUSED_HOLDOUT_WIN" if won else "V7_1_NOT_BEATEN"
    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "stage": "validate",
        "status": status,
        "research_status": ["diagnostic-only", "reused-holdout", "not promoted", "not live-ready"],
        "boundary": {
            "start": pd.Timestamp(context.book.ts[TRAIN_DAYS]),
            "last_feature_day": pd.Timestamp(context.book.ts[-1]),
            "terminal": pd.Timestamp(context.book.terminal_ts),
            "days": TOTAL_DAYS - TRAIN_DAYS,
            "holdout_classification": "reused_holdout_not_clean_oos",
            "holdout_read": True,
        },
        "head_metrics": bundle["head_metrics"],
        "p7": bundle["metrics"],
        "v7_1": bundle["teacher_metrics"],
        "p7_episode_capture": bundle["capture"],
        "v7_1_episode_capture": bundle["teacher_capture"],
        "v7_1_beaten": won,
        "recent_slices_flat_start": slices,
    }
    paths = {
        "scores": ARTIFACT_DIR / f"{PREFIX}_validation_scores.csv",
        "decisions": ARTIFACT_DIR / f"{PREFIX}_validation_decisions.csv",
        "trades": ARTIFACT_DIR / f"{PREFIX}_validation_trades.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_validation_v7_1_trades.csv",
        "episode_capture": ARTIFACT_DIR / f"{PREFIX}_validation_episode_capture.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_validation_summary.json",
    }
    write_csv(paths["scores"], bundle["scores"])
    write_csv(paths["decisions"], bundle["decisions"])
    write_csv(paths["trades"], bundle["trades"])
    write_csv(paths["teacher_trades"], bundle["teacher_trades"])
    write_csv(
        paths["episode_capture"],
        pd.concat(
            [
                bundle["capture_rows"].assign(strategy="P7"),
                bundle["teacher_capture_rows"].assign(strategy="V7.1"),
            ],
            ignore_index=True,
        ),
    )
    write_json(paths["summary"], summary)
    for path in paths.values():
        write_sidecar(path)
    return summary


def self_test() -> dict[str, Any]:
    p5 = load_module(P5_SCRIPT, "hype_p7_self_p5")
    p6 = load_module(P6_SCRIPT, "hype_p7_self_p6")
    features = survival_features(p5, p6)
    assert "HYPEUSDT" not in DONOR_ASSETS
    assert set(DONOR_SPECS) == set(DONOR_ASSETS)
    assert EXTEND_START_THRESHOLD == p6.EXTEND_START_THRESHOLD == 0.60
    assert SURVIVAL_EXIT_THRESHOLD == p6.SURVIVAL_EXIT_THRESHOLD == 0.35
    assert LOW_SURVIVAL_CONFIRMATIONS == 2
    assert set(p6.ELIGIBLE_CORE_EXITS).isdisjoint(
        {"long_protective_stop", "short_protective_stop"}
    )
    synthetic = pd.DataFrame(
        {
            "asset": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "ETHUSDT"],
            "index": [0, 0, 1, 1],
            "ts": [
                "2025-10-01T00:00:00+00:00",
                "2025-10-01T00:00:00+00:00",
                "2025-11-12T00:00:00+00:00",
                "2025-11-12T00:00:00+00:00",
            ],
            COMPLETE: [True, True, True, True],
            TARGET: [1, 0, 1, 0],
        }
    )
    train = complete_rows_by_ts(
        synthetic, end=pd.Timestamp("2025-11-12T00:00:00Z") - pd.Timedelta(days=PURGE_DAYS)
    )
    test = complete_rows_by_ts(
        synthetic,
        start=pd.Timestamp("2025-11-12T00:00:00Z"),
        end=pd.Timestamp("2025-12-22T00:00:00Z"),
    )
    assert train["ts"].tolist() == [
        "2025-10-01T00:00:00+00:00",
        "2025-10-01T00:00:00+00:00",
    ]
    assert test["index"].tolist() == [1, 1]
    return {
        "status": "PASS",
        "heads": ["survival"],
        "feature_count": len(features),
        "donor_assets": list(DONOR_ASSETS),
        "hype_in_training_pool": False,
        "protective_stops_delegated": True,
        "calendar_oof_ignores_local_index": True,
    }


def main() -> int:
    args = parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    result = develop() if args.stage == "develop" else validate()
    print(json.dumps(sanitize(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
