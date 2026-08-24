"""Final CTLS state-identification attempt with intraday and BTC context."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-ctls-r6-intraday-context-preregistration-2026-08-10.md"
R5_DIAGNOSTIC_PATH = FAMILY_DIR / "diagnostics/hype-1d-ma7-ctls-r5-duration-failure-2026-08-10.md"
R3_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r3_walk_forward_identifiability.py"
R4_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r4_stable_segment.py"
R5_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r5_duration_decoder.py"
LABEL_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
BTC_PATH = ROOT / "data/features/btcusdt_1h_stop_path_v1/btcusdt_perp_1h.parquet"
ORCHESTRATOR_PATH = Path(__file__)
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_ctls_r6_intraday_context.py"
IMPLEMENTATION_PATHS = (
    CONTRACT_PATH,
    R5_DIAGNOSTIC_PATH,
    R3_PATH,
    R4_PATH,
    R5_PATH,
    LABEL_ENGINE_PATH,
    ADAPTER_PATH,
    ORCHESTRATOR_PATH,
    TEST_PATH,
)
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r6_2026-08-10_manifest.json"
DIRECTION_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r6_2026-08-10_direction.json"
R5_DIRECTION_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r5_2026-08-10_direction.json"
FOLDS = tuple((start, start + 54) for start in range(54, 324, 54))
EXPECTED_TESTS = 5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _pins() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in IMPLEMENTATION_PATHS}


def _assert_pins(expected: dict[str, str], btc_sha: str) -> None:
    if _pins() != expected or sha256(BTC_PATH) != btc_sha:
        raise RuntimeError("CTLS-R6 implementation or BTC data pin drift")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(
        _safe(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ).encode()
    try:
        with path.open("xb") as handle:
            handle.write(encoded + b"\n")
    except FileExistsError as exc:
        raise RuntimeError(f"locked artifact already exists: {path}") from exc


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing upstream artifact: {path}")
    return json.loads(path.read_text())


def preflight() -> dict[str, Any]:
    before = (_pins(), sha256(BTC_PATH))
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/pytest"), "-q", str(TEST_PATH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    after = (_pins(), sha256(BTC_PATH))
    status = "PASS" if completed.returncode == 0 and passed == EXPECTED_TESTS and before == after else "FAIL"
    result = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_TESTS,
        "pins_stable": before == after,
        "returncode": completed.returncode,
        "output": output.strip(),
    }
    if status != "PASS":
        raise RuntimeError(f"R6 preflight failed: {result}")
    return result


def _day_context(bars: pd.DataFrame, atr: float, prefix: str) -> dict[str, float]:
    if len(bars) != 24:
        raise RuntimeError(f"{prefix} day requires exactly 24 hourly bars")
    required = ("open", "high", "low", "close", "volume")
    values = bars.loc[:, required].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0.0).any() or (values[:, 4] < 0.0).any():
        raise RuntimeError(f"{prefix} hourly OHLCV is invalid")
    open_ = float(bars["open"].iloc[0])
    close = bars["close"].to_numpy(float)
    log_returns = np.diff(np.r_[open_, close])
    log_returns = np.log(np.r_[open_, close][1:] / np.r_[open_, close][:-1])
    x = np.arange(24, dtype=float)
    slope = float(np.dot(x - x.mean(), close - close.mean()) / np.dot(x - x.mean(), x - x.mean()))
    peaks = np.maximum.accumulate(close)
    troughs = np.minimum.accumulate(close)
    volume = bars["volume"].to_numpy(float)
    total_volume = float(volume.sum())
    return {
        f"{prefix}_return": close[-1] / open_ - 1.0,
        f"{prefix}_first6_return": close[5] / open_ - 1.0,
        f"{prefix}_last6_return": close[-1] / float(bars["open"].iloc[18]) - 1.0,
        f"{prefix}_realized_vol": float(np.sqrt(np.square(log_returns).sum())),
        f"{prefix}_up_semivol": float(np.sqrt(np.square(log_returns[log_returns > 0.0]).sum())),
        f"{prefix}_down_semivol": float(np.sqrt(np.square(log_returns[log_returns < 0.0]).sum())),
        f"{prefix}_slope_atr": slope / atr,
        f"{prefix}_range_atr": (float(bars["high"].max()) - float(bars["low"].min())) / atr,
        f"{prefix}_close_location": (close[-1] - float(bars["low"].min()))
        / max(1e-12, float(bars["high"].max()) - float(bars["low"].min())),
        f"{prefix}_positive_hour_share": float(np.mean(log_returns > 0.0)),
        f"{prefix}_early_late_momentum": (close[11] / open_ - 1.0)
        - (close[-1] / float(bars["open"].iloc[12]) - 1.0),
        f"{prefix}_max_drawdown": float(np.min(close / peaks - 1.0)),
        f"{prefix}_max_rebound": float(np.max(close / troughs - 1.0)),
        f"{prefix}_log_volume": math.log1p(total_volume),
        f"{prefix}_volume_concentration": float(volume.max() / total_volume)
        if total_volume > 0.0
        else 0.0,
    }


def build_augmented_features(
    daily: pd.DataFrame,
    hype_hourly: pd.DataFrame,
    funding: pd.DataFrame,
    btc_hourly: pd.DataFrame,
    r3: Any,
) -> pd.DataFrame:
    base = r3.build_features(daily)
    hype = hype_hourly.copy()
    btc = btc_hourly.copy()
    fund = funding.copy()
    for frame in (hype, btc, fund):
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        if frame["ts"].duplicated().any():
            raise RuntimeError("R6 context contains duplicate timestamps")
    if not hype["ts"].is_monotonic_increasing or not btc["ts"].is_monotonic_increasing:
        raise RuntimeError("R6 hourly context must be sorted")
    rows = []
    for ts, daily_row in daily.iterrows():
        day = pd.Timestamp(ts)
        end = day + pd.Timedelta(days=1)
        hype_day = hype.loc[hype["ts"].ge(day) & hype["ts"].lt(end)]
        btc_day = btc.loc[btc["ts"].ge(day) & btc["ts"].lt(end)]
        atr = float(daily_row["atr7"])
        if not math.isfinite(atr) or atr <= 0.0:
            rows.append({"ts": day})
            continue
        row = {"ts": day}
        row.update(_day_context(hype_day, atr, "hype"))
        btc_atr = max(
            1e-12,
            float(btc_day["high"].max()) - float(btc_day["low"].min()),
        )
        row.update(_day_context(btc_day, btc_atr, "btc"))
        events = fund.loc[fund["ts"].ge(day) & fund["ts"].lt(end)]
        rates = events["funding_rate"].to_numpy(float)
        row["funding_sum"] = float(rates.sum()) if len(rates) else 0.0
        row["funding_abs_sum"] = float(np.abs(rates).sum()) if len(rates) else 0.0
        row["funding_last"] = float(rates[-1]) if len(rates) else 0.0
        rows.append(row)
    context = pd.DataFrame(rows).set_index("ts").reindex(daily.index)
    context["hype_volume_change1"] = context["hype_log_volume"].diff()
    context["hype_volume_change3"] = context["hype_log_volume"].diff(3)
    context["btc_volume_change1"] = context["btc_log_volume"].diff()
    context["funding_change1"] = context["funding_last"].diff()
    context["hype_btc_return_spread"] = context["hype_return"] - context["btc_return"]
    context["hype_btc_corr5"] = context["hype_return"].rolling(5, min_periods=5).corr(
        context["btc_return"]
    )
    return pd.concat([base, context], axis=1).replace([np.inf, -np.inf], np.nan)


def _hash_config(model: dict[str, Any], alpha: float, post: Any, duration: Any) -> str:
    payload = {
        "model": model,
        "alpha": alpha,
        "post": asdict(post),
        "duration": asdict(duration),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path_hash(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def stage_manifest() -> dict[str, Any]:
    tests = preflight()
    pins = _pins()
    btc_sha = sha256(BTC_PATH)
    r5 = _read(R5_DIRECTION_PATH)
    if r5.get("status") != "FAIL" or r5.get("passing_gate") != 0:
        raise RuntimeError("R6 requires frozen R5 failure")
    adapter = _load(ADAPTER_PATH, "ctls_r6_manifest_adapter")
    context = adapter.load_context()
    btc = pd.read_parquet(BTC_PATH, columns=["ts"])
    btc["ts"] = pd.to_datetime(btc["ts"], utc=True)
    payload = {
        "schema_version": "ctls-r6-manifest-v1",
        "status": "LOCKED",
        "preflight": tests,
        "pins": pins,
        "btc": {
            "path": str(BTC_PATH.relative_to(ROOT)),
            "sha256": btc_sha,
            "rows": len(btc),
            "start": btc["ts"].min().isoformat(),
            "end": btc["ts"].max().isoformat(),
        },
        "r5_failure": {"path": str(R5_DIRECTION_PATH.relative_to(ROOT)), "sha256": sha256(R5_DIRECTION_PATH)},
        "trials": 4464,
        "folds": FOLDS,
        "LES_accessed": False,
        "market": {
            "book_count": context.book.count,
            "terminal_ts": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "audit": context.market.audit,
            "adapter_pins": dict(context.pins),
        },
    }
    _assert_pins(pins, btc_sha)
    _write_new(MANIFEST_PATH, payload)
    return {"status": "PASS", "path": str(MANIFEST_PATH), "sha256": sha256(MANIFEST_PATH)}


def rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if row["gate"]["status"] == "PASS" else 1,
        -min(fold["balanced_accuracy"] for fold in row["folds"]),
        -row["aggregate"]["balanced_accuracy"],
        -min(row["aggregate"]["recalls"].values()),
        row["aggregate"]["flip_rate"],
        row["complexity"],
        row["config_sha256"],
    )


def stage_direction() -> dict[str, Any]:
    manifest = _read(MANIFEST_PATH)
    _assert_pins(manifest["pins"], manifest["btc"]["sha256"])
    r3 = _load(R3_PATH, "ctls_r6_r3")
    r4 = _load(R4_PATH, "ctls_r6_r4")
    r5 = _load(R5_PATH, "ctls_r6_r5")
    labels = _load(LABEL_ENGINE_PATH, "ctls_r6_labels")
    adapter = _load(ADAPTER_PATH, "ctls_r6_adapter")
    context = adapter.load_context()
    daily = context.market.daily
    btc = pd.read_parquet(BTC_PATH)
    btc["ts"] = pd.to_datetime(btc["ts"], utc=True)
    btc = btc.sort_values("ts")
    features = build_augmented_features(
        daily,
        context.market.hourly,
        context.market.funding,
        btc,
        r3,
    )
    raw = labels.hindsight_labels(daily.loc[:, ["close", "ma7", "atr7"]])
    target = r4.stable_direction_target(r3.direction_target(raw))
    rows = []
    for model_index, model_config in enumerate(r3.model_configs(), 1):
        fold_probabilities = []
        metadata = []
        for fold_index, (eval_start, eval_end) in enumerate(FOLDS, 1):
            train_positions = list(r4.mature_training_positions(eval_start))
            mask = features.iloc[train_positions].notna().all(axis=1) & target.iloc[train_positions].notna()
            train_x = features.iloc[train_positions].loc[mask]
            train_y = target.iloc[train_positions].loc[mask].astype(int).to_numpy()
            eval_x = features.iloc[eval_start:eval_end]
            if not eval_x.notna().all(axis=1).all():
                raise RuntimeError("R6 eval features contain non-finite rows")
            fold_probabilities.append(r3._fit_predict(model_config, train_x, train_y, eval_x))
            metadata.append(
                {
                    "fold": fold_index,
                    "train_samples": len(train_x),
                    "train_last_label_ts": train_x.index[-1].isoformat(),
                    "eval_start_ts": eval_x.index[0].isoformat(),
                    "eval_end_ts": eval_x.index[-1].isoformat(),
                    "train_class_counts": dict(sorted(Counter(map(int, train_y)).items())),
                }
            )
        for alpha_index, alpha in enumerate(r5.EMA_ALPHAS, 1):
            smoothed = [r4.ema_probabilities(value, alpha) for value in fold_probabilities]
            for post_index, post in enumerate(r5.base_post_configs(r3), 1):
                base_states = [r3.apply_hysteresis(value, post) for value in smoothed]
                for duration_index, duration in enumerate(r5.duration_configs(), 1):
                    all_actual = []
                    all_predicted = []
                    fold_metrics = []
                    path_rows = []
                    for fold_index, ((eval_start, eval_end), base) in enumerate(
                        zip(FOLDS, base_states, strict=True), 1
                    ):
                        predicted = r5.duration_decode(base, duration)
                        eval_target = target.iloc[eval_start:eval_end].to_numpy()
                        eligible = np.arange(len(predicted)) < len(predicted) - 4
                        eligible &= np.isfinite(eval_target)
                        actual_values = eval_target[eligible].astype(int)
                        predicted_values = predicted[eligible]
                        metric = r3.direction_metrics(actual_values, predicted_values)
                        fold_metrics.append({**metadata[fold_index - 1], **metric})
                        all_actual.extend(actual_values.tolist())
                        all_predicted.extend(predicted_values.tolist())
                        path_rows.extend(
                            {
                                "fold": fold_index,
                                "ts": daily.index[eval_start + offset].isoformat(),
                                "direction": int(value),
                            }
                            for offset, value in enumerate(predicted)
                        )
                    aggregate = r3.direction_metrics(
                        np.asarray(all_actual), np.asarray(all_predicted)
                    )
                    gate = r3._gate(aggregate, fold_metrics)
                    rows.append(
                        {
                            "arm_id": f"R6D{model_index:02d}_{alpha_index}_{post_index}_{duration_index}",
                            "status": "OK",
                            "model": model_config,
                            "ema_alpha": alpha,
                            "post": asdict(post),
                            "duration": asdict(duration),
                            "config_sha256": _hash_config(
                                model_config, alpha, post, duration
                            ),
                            "complexity": model_index * 1000
                            + alpha_index * 100
                            + post_index * 10
                            + duration_index,
                            "direction_path_sha256": _path_hash(path_rows),
                            "aggregate": aggregate,
                            "folds": fold_metrics,
                            "gate": gate,
                        }
                    )
    passing = [row for row in rows if row["gate"]["status"] == "PASS"]
    best: dict[str, dict[str, Any]] = {}
    for row in passing:
        current = best.get(row["direction_path_sha256"])
        if current is None or rank_key(row) < rank_key(current):
            best[row["direction_path_sha256"]] = row
    selected = sorted(best.values(), key=rank_key)[:16]
    payload = {
        "schema_version": "ctls-r6-direction-v1",
        "status": "PASS" if selected else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "feature_count": features.shape[1],
        "feature_columns": list(features.columns),
        "trials": len(rows),
        "passing_gate": len(passing),
        "unique_paths": len({row["direction_path_sha256"] for row in rows}),
        "selected_arm_ids": [row["arm_id"] for row in selected],
        "selected": selected,
        "rows": rows,
    }
    _assert_pins(manifest["pins"], manifest["btc"]["sha256"])
    _write_new(DIRECTION_PATH, payload)
    return {
        "status": payload["status"],
        "passing_gate": len(passing),
        "selected": payload["selected_arm_ids"],
        "path": str(DIRECTION_PATH),
        "sha256": sha256(DIRECTION_PATH),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("self-test", "manifest", "direction"))
    return parser.parse_args()


def main() -> None:
    stage = parse_args().stage
    if stage == "self-test":
        result = preflight()
    elif stage == "manifest":
        result = stage_manifest()
    else:
        result = stage_direction()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

