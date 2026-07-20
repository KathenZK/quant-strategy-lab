from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
ENGINE_PATH = ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v1/engine.py"
ENGINE_SHA256 = "0420ea44854201e17d4bf5b9142fb8335d143e78772656473a1dcf4594a5f04c"
DATA_PATH = ARTIFACT_DIR / "bnb_binance_1h_closed_klines_2y.parquet"
QUALITY_PATH = ARTIFACT_DIR / "bnb_binance_1h_data_quality_2y.json"
FUNDING_PATH = ARTIFACT_DIR / "bnb_binance_funding_history_2y.csv"
DATE_TAG = "2026-07-03"
FREEZE_JSON = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_frozen_primary_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_search_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_prefit_{DATE_TAG}.csv"
RANKING_CSV = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_locked_result_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"bnb_1h_adaptive_regime_primary_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"bnb-1h-adaptive-regime-search-{DATE_TAG}.md"

TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.50
TARGET_MAX_DD = -0.20
MIN_PREFIT_TRADES = 50
MIN_VALIDATION_TRADES = 15
MIN_OOS_TRADES = 12
WARMUP_DAYS = 45
LOCKED_OOS_MONTHS = 3

MUTATION_GROUPS = (
    ("style", "indicator_window", "threshold_low", "threshold_high", "band_k", "pullback_atr"),
    ("side_mode",),
    ("ema_fast", "ema_slow", "ema_htf"),
    ("roc_window", "roc_threshold_bps", "min_dir_roc_bps"),
    ("macd_fast", "macd_slow", "macd_signal", "require_macd_turn"),
    ("min_adx", "max_adx"),
    ("min_rvol",),
    ("min_atr_bps", "max_atr_bps"),
    ("max_dist_ema_bps",),
    ("htf_mode",),
    ("require_body_dir",),
    ("max_aligned_funding_bps",),
    ("exit_kind", "tp_atr", "sl_atr", "trail_activation_atr", "trail_atr"),
    ("max_hold_bars", "cooldown_bars"),
    ("sizing_kind", "fixed_leverage", "risk_fraction", "max_leverage"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Broad prefit-only BNBUSDT 1h search followed by one locked-OOS "
            "evaluation of a predeclared primary."
        )
    )
    parser.add_argument("--random-configs", type=int, default=500_000)
    parser.add_argument("--neighbors", type=int, default=250_000)
    parser.add_argument("--seed", type=int, default=2026070303)
    parser.add_argument("--prefit-keep", type=int, default=1_200)
    parser.add_argument("--seed-pool", type=int, default=180)
    parser.add_argument("--progress-every", type=int, default=10_000)
    parser.add_argument("--no-ensembles", action="store_true")
    parser.add_argument(
        "--prefit-only",
        action="store_true",
        help="Stop before ensemble construction, primary freeze, or OOS unlock.",
    )
    return parser.parse_args()


def load_engine() -> Any:
    actual_hash = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if actual_hash != ENGINE_SHA256:
        raise RuntimeError(
            f"Search engine drift: expected {ENGINE_SHA256}, got {actual_hash}"
        )
    spec = importlib.util.spec_from_file_location("bnb_1h_search_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load search engine: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.TARGET_ANNUAL_MULTIPLE = TARGET_ANNUAL_MULTIPLE
    module.TARGET_WIN_RATE = TARGET_WIN_RATE
    module.TARGET_MAX_DD = TARGET_MAX_DD
    module.MIN_PREFIT_TRADES = MIN_PREFIT_TRADES
    module.MIN_VALIDATION_TRADES = MIN_VALIDATION_TRADES
    module.MIN_HOLDOUT_TRADES = MIN_OOS_TRADES
    return module


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not DATA_PATH.exists() or not QUALITY_PATH.exists() or not FUNDING_PATH.exists():
        raise FileNotFoundError("Run scripts/fetch_bnb_binance_1h.py first")
    frame = pd.read_parquet(DATA_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    duplicate = int(frame.duplicated("ts").sum())
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="1h")
    missing = expected.difference(pd.DatetimeIndex(frame["ts"]))
    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    nulls = {column: int(frame[column].isna().sum()) for column in required}
    violations = {
        "high_lt_open_close": int(
            (frame["high"] < frame[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_open_close": int(
            (frame["low"] > frame[["open", "close"]].min(axis=1)).sum()
        ),
        "nonpositive_ohlc": int(
            ((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
        "negative_volume": int((frame["volume"] < 0).sum()),
        "negative_quote_volume": int((frame["quote_volume"] < 0).sum()),
    }
    metadata = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    fetch_quality = metadata["data_quality"]
    blockers = (
        duplicate
        + len(missing)
        + sum(nulls.values())
        + sum(violations.values())
        + int(set(frame["is_closed"].unique()) != {True})
        + int(fetch_quality.get("blocker_count", 1))
    )
    if blockers:
        raise RuntimeError(
            f"BNBUSDT exact frame failed quality gate: missing={len(missing)} "
            f"duplicate={duplicate} nulls={nulls} violations={violations}"
        )
    funding = pd.read_csv(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True, format="mixed")
    funding = funding.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    if funding.empty or funding["funding_rate"].isna().any():
        raise RuntimeError("BNB funding history is empty or contains null rates")
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "missing_bars": int(len(missing)),
        "duplicate_bars": duplicate,
        "critical_nulls": nulls,
        "ohlcv_violations": violations,
        "raw_normalized_mismatch": fetch_quality["raw_normalized_mismatch"],
        "funding_rows": int(len(funding)),
        "funding_first_ts": funding["ts"].iloc[0].isoformat(),
        "funding_last_ts": funding["ts"].iloc[-1].isoformat(),
        "source_counts": {
            str(key): int(value) for key, value in frame["source"].value_counts().items()
        },
    }
    return frame, funding, quality


def strict_metrics(
    engine: Any,
    trades: list[Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    purged = [
        trade
        for trade in trades
        if start <= trade.entry_ts < end and trade.exit_ts < end
    ]
    return engine.metrics(purged, start, end)


def candidate_from_trades(
    engine: Any,
    cfg: Any,
    trades: list[Any],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    prefit_end: pd.Timestamp,
) -> Any | None:
    train = strict_metrics(engine, trades, train_start, train_end)
    validation = strict_metrics(engine, trades, train_end, prefit_end)
    prefit = strict_metrics(engine, trades, train_start, prefit_end)
    score = engine.prefit_score(train, validation, prefit)
    if score <= -1e8:
        return None
    return engine.Candidate(
        name=cfg.name,
        kind="single",
        styles=cfg.style,
        config_names=cfg.name,
        prefit_score=score,
        prefit_pass=engine.prefit_gate(train, validation, prefit),
        train=train,
        validation=validation,
        prefit=prefit,
    )


def selection_key(candidate: Any) -> tuple[int, float, float, float, float]:
    train = candidate.train
    validation = candidate.validation
    floor_ann = min(train["annual_multiple"], validation["annual_multiple"])
    worst_dd = min(train["max_dd"], validation["max_dd"])
    floor_win = min(train["win_rate"], validation["win_rate"])
    return (
        int(candidate.prefit_pass),
        candidate.prefit_score,
        floor_ann,
        worst_dd,
        floor_win,
    )


def retain(
    retained: list[tuple[Any, Any, list[Any]]],
    item: tuple[Any, Any, list[Any]],
    keep: int,
) -> list[tuple[Any, Any, list[Any]]]:
    retained.append(item)
    if len(retained) > keep * 3:
        retained = sorted(retained, key=lambda row: selection_key(row[0]), reverse=True)[:keep]
    return retained


def bnb_name(name: str) -> str:
    return name.replace("HYPE_1H_AR", "BNB_1H_AR")


def mutate_config(engine: Any, seed: Any, rng: random.Random, index: int) -> Any:
    donor = engine.random_config(rng, index)
    updates: dict[str, Any] = {"name": f"BNB_1H_AR_N{index:07d}"}
    for group in rng.sample(MUTATION_GROUPS, k=rng.choice((1, 2, 2, 3, 3, 4, 5))):
        for field in group:
            updates[field] = getattr(donor, field)
    cfg = replace(seed, **updates, entry_delay_bars=1)
    if cfg.ema_slow <= cfg.ema_fast * 1.35:
        cfg = replace(cfg, ema_fast=donor.ema_fast, ema_slow=donor.ema_slow)
    if cfg.max_adx <= cfg.min_adx:
        cfg = replace(cfg, max_adx=100.0)
    if cfg.max_atr_bps <= cfg.min_atr_bps:
        cfg = replace(cfg, max_atr_bps=10_000.0)
    return cfg


def candidate_row(candidate: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": candidate.name,
        "kind": candidate.kind,
        "styles": candidate.styles,
        "config_names": candidate.config_names,
        "prefit_score": candidate.prefit_score,
        "prefit_pass": candidate.prefit_pass,
        "target_pass": candidate.target_pass,
    }
    for prefix, values in (
        ("train", candidate.train),
        ("validation", candidate.validation),
        ("prefit", candidate.prefit),
        ("holdout", candidate.holdout or {}),
        ("full", candidate.full or {}),
    ):
        for key, value in values.items():
            row[f"{prefix}_{key}"] = value
    return row


def simulate_masked(
    engine: Any,
    frame: pd.DataFrame,
    cfg: Any,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    start: pd.Timestamp | None = None,
) -> list[Any]:
    signal = engine.build_signal(frame, cfg)
    if start is not None:
        allowed = frame["ts"] + pd.Timedelta(hours=cfg.entry_delay_bars) >= start
        signal = signal.copy()
        signal[~allowed.to_numpy()] = 0
    return engine.simulate_trades(
        frame, signal, cfg, funding_times, funding_cumulative
    )


def metric_gate(metric: dict[str, float], min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= TARGET_WIN_RATE
        and metric["max_dd"] > TARGET_MAX_DD
    )


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2f}x"


def main() -> None:
    args = parse_args()
    engine = load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    raw_frame, funding, quality = load_data()
    raw_start = pd.Timestamp(raw_frame["ts"].iloc[0])
    full_end = pd.Timestamp(raw_frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    oos_start = full_end - pd.DateOffset(months=LOCKED_OOS_MONTHS)
    train_start = raw_start + pd.Timedelta(days=WARMUP_DAYS)
    prefit_span = oos_start - train_start
    train_end = (train_start + prefit_span * 0.70).floor("h")
    split = {
        "raw_start": raw_start.isoformat(),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "validation_end": oos_start.isoformat(),
        "oos_start": oos_start.isoformat(),
        "full_end": full_end.isoformat(),
    }
    print(f"data rows={len(raw_frame)} split={split}", flush=True)

    # Structural lock: no OOS candle is present in the feature/search frame.
    prefit_raw = raw_frame.loc[raw_frame["ts"] < oos_start].copy().reset_index(drop=True)
    prefit_funding = funding.loc[funding["ts"] < oos_start].copy().reset_index(drop=True)
    prefit_frame = engine.add_features(prefit_raw, prefit_funding)
    prefit_funding_times, prefit_funding_cumulative = engine.funding_prefix(prefit_funding)

    rng = random.Random(args.seed)
    curated = [
        replace(cfg, name=bnb_name(cfg.name), entry_delay_bars=1)
        for cfg in engine.curated_configs()
    ]
    configs = curated + [
        replace(
            engine.random_config(rng, index + len(curated)),
            name=f"BNB_1H_AR_R{index + len(curated):07d}",
            entry_delay_bars=1,
        )
        for index in range(args.random_configs)
    ]
    retained: list[tuple[Any, Any, list[Any]]] = []
    counts = {
        "curated_configs": len(curated),
        "random_configs": args.random_configs,
        "first_pass_evaluated": 0,
        "first_pass_eligible": 0,
        "first_pass_prefit_pass": 0,
        "neighbors_requested": args.neighbors,
        "neighbors_evaluated": 0,
        "neighbors_eligible": 0,
        "neighbors_prefit_pass": 0,
    }
    for index, cfg in enumerate(configs, start=1):
        signal = engine.build_signal(prefit_frame, cfg)
        if int(np.count_nonzero(signal)) < 8:
            continue
        trades = engine.simulate_trades(
            prefit_frame,
            signal,
            cfg,
            prefit_funding_times,
            prefit_funding_cumulative,
        )
        candidate = candidate_from_trades(
            engine, cfg, trades, train_start, train_end, oos_start
        )
        counts["first_pass_evaluated"] += 1
        if candidate is None:
            continue
        counts["first_pass_eligible"] += 1
        counts["first_pass_prefit_pass"] += int(candidate.prefit_pass)
        retained = retain(retained, (candidate, cfg, trades), args.prefit_keep)
        if index % args.progress_every == 0 and retained:
            best = max(retained, key=lambda row: selection_key(row[0]))[0]
            print(
                f"first {index}/{len(configs)} eligible={counts['first_pass_eligible']} "
                f"passes={counts['first_pass_prefit_pass']} best={best.name} "
                f"score={best.prefit_score:.3f} ann={best.prefit['annual_multiple']:.3f} "
                f"dd={best.prefit['max_dd']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda row: selection_key(row[0]), reverse=True)[
        : args.prefit_keep
    ]
    if not retained:
        raise RuntimeError("No first-pass config survived the minimum-trade gate")

    seed_pool = [row[1] for row in retained[: args.seed_pool]]
    seen = {
        tuple((key, value) for key, value in asdict(cfg).items() if key != "name")
        for cfg in seed_pool
    }
    for index in range(args.neighbors):
        cfg = mutate_config(
            engine,
            seed_pool[index % len(seed_pool)],
            rng,
            args.random_configs + len(curated) + index,
        )
        key = tuple((name, value) for name, value in asdict(cfg).items() if name != "name")
        if key in seen:
            continue
        seen.add(key)
        signal = engine.build_signal(prefit_frame, cfg)
        if int(np.count_nonzero(signal)) < 8:
            continue
        trades = engine.simulate_trades(
            prefit_frame,
            signal,
            cfg,
            prefit_funding_times,
            prefit_funding_cumulative,
        )
        candidate = candidate_from_trades(
            engine, cfg, trades, train_start, train_end, oos_start
        )
        counts["neighbors_evaluated"] += 1
        if candidate is None:
            continue
        counts["neighbors_eligible"] += 1
        counts["neighbors_prefit_pass"] += int(candidate.prefit_pass)
        retained = retain(retained, (candidate, cfg, trades), args.prefit_keep)
        if (index + 1) % args.progress_every == 0 and retained:
            best = max(retained, key=lambda row: selection_key(row[0]))[0]
            print(
                f"neighbor {index + 1}/{args.neighbors} "
                f"eligible={counts['neighbors_eligible']} "
                f"passes={counts['neighbors_prefit_pass']} best={best.name} "
                f"score={best.prefit_score:.3f} ann={best.prefit['annual_multiple']:.3f} "
                f"dd={best.prefit['max_dd']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda row: selection_key(row[0]), reverse=True)[
        : args.prefit_keep
    ]

    if args.prefit_only:
        print(
            json.dumps(
                json_safe(
                    {
                        "status": "prefit_only_oos_not_unlocked",
                        "search_counts": counts,
                        "retained": len(retained),
                        "best": candidate_row(retained[0][0]),
                    }
                ),
                indent=2,
                ensure_ascii=False,
            ),
            flush=True,
        )
        return

    ensemble_rows: list[tuple[Any, tuple[Any, Any], list[Any]]] = []
    if not args.no_ensembles:
        ensemble_source = [(candidate, cfg) for candidate, cfg, _trades in retained]
        raw_ensembles = engine.make_ensembles(
            ensemble_source,
            prefit_frame,
            prefit_funding_times,
            prefit_funding_cumulative,
            train_start,
            train_end,
            oos_start,
        )
        for candidate, pair, trades in raw_ensembles:
            train = strict_metrics(engine, trades, train_start, train_end)
            validation = strict_metrics(engine, trades, train_end, oos_start)
            prefit = strict_metrics(engine, trades, train_start, oos_start)
            score = engine.prefit_score(train, validation, prefit)
            if score <= -1e8:
                continue
            candidate.train = train
            candidate.validation = validation
            candidate.prefit = prefit
            candidate.prefit_score = score
            candidate.prefit_pass = engine.prefit_gate(train, validation, prefit)
            ensemble_rows.append((candidate, pair, trades))
        ensemble_rows.sort(key=lambda row: selection_key(row[0]), reverse=True)
    counts["retained_singles"] = len(retained)
    counts["retained_ensembles"] = len(ensemble_rows)

    prefit_rows: list[dict[str, Any]] = []
    for candidate, cfg, _trades in retained:
        row = candidate_row(candidate)
        row.update({f"cfg_{key}": value for key, value in asdict(cfg).items()})
        prefit_rows.append(row)
    for candidate, pair, _trades in ensemble_rows:
        row = candidate_row(candidate)
        row["left_config"] = json.dumps(asdict(pair[0]), sort_keys=True)
        row["right_config"] = json.dumps(asdict(pair[1]), sort_keys=True)
        prefit_rows.append(row)
    prefit_rows.sort(
        key=lambda row: (
            bool(row["prefit_pass"]),
            float(row["prefit_score"]),
        ),
        reverse=True,
    )
    pd.DataFrame(prefit_rows).to_csv(PREFIT_CSV, index=False)

    primary_kind: str
    primary_candidate: Any
    primary_configs: tuple[Any, ...]
    primary_priorities: tuple[float, ...]
    best_single = retained[0]
    best_ensemble = ensemble_rows[0] if ensemble_rows else None
    if best_ensemble is not None and selection_key(best_ensemble[0]) > selection_key(best_single[0]):
        primary_candidate = best_ensemble[0]
        primary_configs = best_ensemble[1]
        primary_priorities = tuple(
            next(
                candidate.prefit_score
                for candidate, cfg, _trades in retained
                if cfg.name == member.name
            )
            for member in primary_configs
        )
        primary_kind = "ensemble"
    else:
        primary_candidate = best_single[0]
        primary_configs = (best_single[1],)
        primary_priorities = (primary_candidate.prefit_score,)
        primary_kind = "single"

    freeze_payload = {
        "frozen_before_oos_unlock": True,
        "family": "BNB-1H-Adaptive-Regime",
        "primary_name": primary_candidate.name,
        "primary_kind": primary_kind,
        "selection_rule": "prefit_pass_then_prefit_score_then_train_validation_floor",
        "split": split,
        "prefit_metrics": candidate_row(primary_candidate),
        "configs": [asdict(cfg) for cfg in primary_configs],
        "ensemble_priorities": list(primary_priorities),
        "locked_oos_read_count_planned": 1,
    }
    FREEZE_JSON.write_text(
        json.dumps(json_safe(freeze_payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"PRIMARY FROZEN kind={primary_kind} name={primary_candidate.name}; unlocking OOS once",
        flush=True,
    )

    # OOS is loaded into the feature engine only after the primary is frozen above.
    full_frame = engine.add_features(raw_frame, funding)
    full_funding_times, full_funding_cumulative = engine.funding_prefix(funding)

    def strategy_trades(start: pd.Timestamp | None) -> list[Any]:
        component_trades = [
            simulate_masked(
                engine,
                full_frame,
                cfg,
                full_funding_times,
                full_funding_cumulative,
                start,
            )
            for cfg in primary_configs
        ]
        if len(component_trades) == 1:
            return component_trades[0]
        return engine.merge_trade_sets(
            component_trades[0],
            component_trades[1],
            primary_priorities[0],
            primary_priorities[1],
        )

    full_trades = strategy_trades(None)
    oos_trades = strategy_trades(oos_start)
    full_metrics = strict_metrics(engine, full_trades, train_start, full_end)
    oos_metrics = strict_metrics(engine, oos_trades, oos_start, full_end)
    primary_candidate.full = full_metrics
    primary_candidate.holdout = oos_metrics
    primary_candidate.target_pass = bool(
        metric_gate(full_metrics, MIN_PREFIT_TRADES)
        and metric_gate(oos_metrics, MIN_OOS_TRADES)
    )

    windows = [
        ("train", train_start, train_end, full_trades),
        ("validation", train_end, oos_start, full_trades),
        ("locked_oos", oos_start, full_end, oos_trades),
        ("full", train_start, full_end, full_trades),
    ]
    cursor = train_start
    block = 1
    while cursor < full_end:
        right = min(full_end, cursor + pd.Timedelta(days=90))
        source = oos_trades if cursor >= oos_start else full_trades
        windows.append((f"block_90d_{block:02d}", cursor, right, source))
        cursor = right
        block += 1
    slices = [
        {"window": name, "start": left, "end": right, **strict_metrics(engine, trades, left, right)}
        for name, left, right, trades in windows
    ]
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame([asdict(trade) for trade in full_trades]).to_csv(TRADES_CSV, index=False)
    locked_row = candidate_row(primary_candidate)
    pd.DataFrame([locked_row]).to_csv(RANKING_CSV, index=False)

    status = (
        "hard_gate_hit_pending_robustness_and_live_audit_not_promoted"
        if primary_candidate.target_pass
        else "no_go_locked_oos_hard_gate_failed_not_promoted"
    )
    payload = {
        "family": "BNB-1H-Adaptive-Regime",
        "family_id": "BNB-1H-AR",
        "status": status,
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "annual_return": TARGET_ANNUAL_MULTIPLE - 1.0,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
            "minimum_full_trades": MIN_PREFIT_TRADES,
            "minimum_locked_oos_trades": MIN_OOS_TRADES,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "data_quality": quality,
        "split": split,
        "search_counts": counts,
        "primary": locked_row,
        "primary_configs": [asdict(cfg) for cfg in primary_configs],
        "primary_ensemble_priorities": list(primary_priorities),
        "slices": slices,
        "oos_protocol": {
            "structural_prefit_frame_end": prefit_raw["ts"].iloc[-1],
            "primary_frozen_before_oos_features_built": True,
            "number_of_locked_primaries_evaluated": 1,
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# BNB-1H-Adaptive-Regime 广泛搜索 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "预先冻结的唯一 primary 同时通过全样本与最近三个月 locked OOS 硬门槛；当前只允许进入稳健性和 live-executable 审计，不代表已可实盘。"
            if primary_candidate.target_pass
            else "预先冻结的唯一 primary 未能同时通过全样本与最近三个月 locked OOS 硬门槛，当前为 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        f"- primary：`{primary_candidate.name}`；kind/styles：`{primary_kind}` / `{primary_candidate.styles}`。",
        f"- full：annual `{mult(full_metrics['annual_multiple'])}`，return `{pct(full_metrics['total_return'])}`，DD `{pct(full_metrics['max_dd'])}`，win `{pct(full_metrics['win_rate'])}`，trades `{int(full_metrics['trades'])}`，PF `{full_metrics['profit_factor']:.3f}`。",
        f"- locked OOS：annual `{mult(oos_metrics['annual_multiple'])}`，return `{pct(oos_metrics['total_return'])}`，DD `{pct(oos_metrics['max_dd'])}`，win `{pct(oos_metrics['win_rate'])}`，trades `{int(oos_metrics['trades'])}`，PF `{oos_metrics['profit_factor']:.3f}`。",
        f"- hard gate：`{primary_candidate.target_pass}`。",
        "",
        "## 数据与防泄漏",
        "",
        f"- Binance USD-M Futures `BNBUSDT` perpetual `1h`：`{quality['rows']}` 根闭合 K；UTC `{quality['first_ts']}` 至 `{quality['last_ts']}`。",
        f"- missing=`{quality['missing_bars']}`，duplicate=`{quality['duplicate_bars']}`，funding rows=`{quality['funding_rows']}`。",
        f"- train：`{split['train_start']}` 至 `{split['train_end']}`；validation 至 `{split['validation_end']}`。",
        f"- locked OOS：`{split['oos_start']}` 至 `{split['full_end']}`。搜索阶段的 feature frame 不含任何 OOS K；primary JSON 落盘后才构建 OOS features。",
        "- 只解锁一个预声明 primary；未根据 OOS 从多个候选中择优。",
        "",
        "## 搜索覆盖",
        "",
    ]
    lines.extend(f"- {key}：`{value}`。" for key, value in counts.items())
    lines.extend(
        [
            "- 指标/机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d 闭合 regime、funding filter、fixed/risk sizing、fixed/trailing exit。",
            "",
            "## 执行与成本",
            "",
            "- 闭合 K 产生信号，下一根 open 市价入场；单仓、不加仓。",
            "- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。",
            "- trailing 只在完整 K 结束后更新，新 stop 从下一根 K 生效。",
            f"- fee `{engine.FEE_PER_FILL:.4%}/fill`，slippage `{engine.SLIPPAGE_PER_FILL:.4%}/fill`，另计真实 Binance funding。",
            "",
            "## Promotion 边界",
            "",
            (
                "即使 locked hard gate 命中，也必须继续通过逐 K 净值回撤、参数邻域、成本/延迟、清算、数量精度、保护单、重启恢复、缺 K 和 kill switch 审计；完成前禁止标记 candidate/paper-live/live。"
                if primary_candidate.target_pass
                else "locked hard gate 未通过，禁止标记 candidate、paper-live、dry-run、handoff 或 live。"
            ),
            "",
            "## 产物",
            "",
            f"- `{FREEZE_JSON.relative_to(ROOT)}`",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{PREFIT_CSV.relative_to(ROOT)}`",
            f"- `{SLICES_CSV.relative_to(ROOT)}`",
            f"- `{TRADES_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            json_safe({"status": status, "search_counts": counts, "primary": locked_row}),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
