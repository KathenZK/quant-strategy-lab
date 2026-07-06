from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_bnb_1h_adaptive_regime_search.py"
DATE_TAG = "2026-07-06-cap3-highwin"

FREEZE_JSON = ARTIFACT_DIR / f"bnb_1h_ar_cap3_highwin_frozen_primary_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_ar_cap3_highwin_search_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"bnb_1h_ar_cap3_highwin_prefit_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"bnb_1h_ar_cap3_highwin_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"bnb_1h_ar_cap3_highwin_primary_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"bnb-1h-ar-cap3-highwin-search-{DATE_TAG}.md"

MAX_LEVERAGE = 3.0
TARGET_HIGHWIN_ANNUAL_MULTIPLE = 2.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20
MIN_PREFIT_TRADES = 50
MIN_VALIDATION_TRADES = 15
MIN_OOS_TRADES = 12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BNB 1h cap3 high-win trend/reversion diagnostic search."
    )
    parser.add_argument("--random-configs", type=int, default=500_000)
    parser.add_argument("--neighbors", type=int, default=250_000)
    parser.add_argument("--seed", type=int, default=2026070603)
    parser.add_argument("--prefit-keep", type=int, default=1_500)
    parser.add_argument("--seed-pool", type=int, default=220)
    parser.add_argument("--progress-every", type=int, default=25_000)
    parser.add_argument("--no-ensembles", action="store_true")
    parser.add_argument("--prefit-only", action="store_true")
    return parser.parse_args()


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("bnb_1h_base_search", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load base search script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
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


def cap3_config(cfg: Any, *, name: str | None = None) -> Any:
    updates: dict[str, Any] = {
        "fixed_leverage": min(float(cfg.fixed_leverage), MAX_LEVERAGE),
        "max_leverage": min(float(cfg.max_leverage), MAX_LEVERAGE),
        "entry_delay_bars": 1,
    }
    if name is not None:
        updates["name"] = name
    return replace(cfg, **updates)


def shape_ok(metric: dict[str, float], *, min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= TARGET_HIGHWIN_ANNUAL_MULTIPLE
        and metric["win_rate"] >= TARGET_WIN_RATE
        and metric["max_dd"] > TARGET_MAX_DD
    )


def prefit_gate(
    train: dict[str, float], validation: dict[str, float], prefit: dict[str, float]
) -> bool:
    return bool(
        shape_ok(prefit, min_trades=MIN_PREFIT_TRADES)
        and train["total_return"] > 0.0
        and train["max_dd"] > TARGET_MAX_DD
        and train["win_rate"] >= 0.75
        and validation["trades"] >= MIN_VALIDATION_TRADES
        and validation["annual_multiple"] >= 1.5
        and validation["win_rate"] >= 0.75
        and validation["max_dd"] > TARGET_MAX_DD
        and validation["total_return"] > 0.0
    )


def target_gate(locked_oos: dict[str, float], full: dict[str, float]) -> bool:
    return bool(
        shape_ok(full, min_trades=MIN_PREFIT_TRADES)
        and shape_ok(locked_oos, min_trades=MIN_OOS_TRADES)
    )


def highwin_score(
    train: dict[str, float], validation: dict[str, float], prefit: dict[str, float]
) -> float:
    if train["total_return"] <= 0.0 or validation["total_return"] <= 0.0:
        return -1e9
    if validation["trades"] < MIN_VALIDATION_TRADES or prefit["trades"] < MIN_PREFIT_TRADES:
        return -1e9
    annuals = [
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    ]
    log_ann = [math.log(min(value, 1e6)) for value in annuals]
    win_floor = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    dd_penalty = sum(
        max(0.0, TARGET_MAX_DD - item["max_dd"]) * 18.0
        for item in (train, validation, prefit)
    )
    win_penalty = sum(
        max(0.0, TARGET_WIN_RATE - item["win_rate"]) * 5.0
        for item in (train, validation, prefit)
    )
    sparse_penalty = max(0.0, 0.12 - prefit["trades_per_day"]) * 2.0
    score = (
        0.8 * log_ann[2]
        + 0.8 * min(log_ann[0], log_ann[1])
        + 1.2 * win_floor
        + 0.2 * min(prefit["profit_factor"], 8.0)
        - dd_penalty
        - win_penalty
        - sparse_penalty
    )
    if prefit_gate(train, validation, prefit):
        score += 6.0
    return float(score)


def candidate_from_trades(
    engine: Any,
    cfg: Any,
    trades: list[Any],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    prefit_end: pd.Timestamp,
) -> Any | None:
    train = engine.metrics(trades, train_start, train_end)
    validation = engine.metrics(trades, train_end, prefit_end)
    prefit = engine.metrics(trades, train_start, prefit_end)
    score = highwin_score(train, validation, prefit)
    if score <= -1e8:
        return None
    return engine.Candidate(
        name=cfg.name,
        kind="single",
        styles=cfg.style,
        config_names=cfg.name,
        prefit_score=score,
        prefit_pass=prefit_gate(train, validation, prefit),
        train=train,
        validation=validation,
        prefit=prefit,
    )


def candidate_sort_key(candidate: Any) -> tuple[int, float, float, float, float]:
    return (
        int(candidate.prefit_pass),
        candidate.prefit_score,
        min(candidate.train["annual_multiple"], candidate.validation["annual_multiple"]),
        min(candidate.train["max_dd"], candidate.validation["max_dd"]),
        min(candidate.train["win_rate"], candidate.validation["win_rate"]),
    )


def retain(
    rows: list[tuple[Any, Any, list[Any]]],
    item: tuple[Any, Any, list[Any]],
    keep: int,
) -> list[tuple[Any, Any, list[Any]]]:
    rows.append(item)
    if len(rows) > keep * 4:
        rows = sorted(rows, key=lambda row: candidate_sort_key(row[0]), reverse=True)[:keep]
    return rows


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


def simulate(
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
    return engine.simulate_trades(frame, signal, cfg, funding_times, funding_cumulative)


def make_ensembles(
    engine: Any,
    retained: list[tuple[Any, Any, list[Any]]],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    prefit_end: pd.Timestamp,
) -> list[tuple[Any, tuple[Any, Any], list[Any], tuple[float, float]]]:
    trends = [
        row
        for row in sorted(retained, key=lambda row: candidate_sort_key(row[0]), reverse=True)
        if row[1].style in engine.TREND_STYLES
    ][:35]
    reversions = [
        row
        for row in sorted(retained, key=lambda row: candidate_sort_key(row[0]), reverse=True)
        if row[1].style in engine.REVERSION_STYLES
    ][:35]
    ensembles: list[tuple[Any, tuple[Any, Any], list[Any], tuple[float, float]]] = []
    for left, right in product(trends, reversions):
        left_candidate, left_cfg, left_trades = left
        right_candidate, right_cfg, right_trades = right
        merged = engine.merge_trade_sets(
            left_trades,
            right_trades,
            left_candidate.prefit_score,
            right_candidate.prefit_score,
        )
        train = engine.metrics(merged, train_start, train_end)
        validation = engine.metrics(merged, train_end, prefit_end)
        prefit = engine.metrics(merged, train_start, prefit_end)
        score = highwin_score(train, validation, prefit)
        if score <= -1e8:
            continue
        candidate = engine.Candidate(
            name=f"ENS__{left_cfg.name}__{right_cfg.name}",
            kind="ensemble",
            styles=f"{left_cfg.style}+{right_cfg.style}",
            config_names=f"{left_cfg.name}+{right_cfg.name}",
            prefit_score=score,
            prefit_pass=prefit_gate(train, validation, prefit),
            train=train,
            validation=validation,
            prefit=prefit,
        )
        ensembles.append(
            (
                candidate,
                (left_cfg, right_cfg),
                merged,
                (left_candidate.prefit_score, right_candidate.prefit_score),
            )
        )
    return sorted(ensembles, key=lambda row: candidate_sort_key(row[0]), reverse=True)[:300]


def metric_rows(
    engine: Any,
    trades: list[Any],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    validation_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    full_end: pd.Timestamp,
    oos_trades: list[Any],
) -> list[dict[str, Any]]:
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp, list[Any]]] = [
        ("train", train_start, train_end, trades),
        ("validation", train_end, validation_end, trades),
        ("locked_oos", oos_start, full_end, oos_trades),
        ("full", train_start, full_end, trades),
    ]
    recent_windows = [
        ("last_1d", pd.Timedelta(days=1)),
        ("last_7d", pd.Timedelta(days=7)),
        ("last_1m", pd.Timedelta(days=30)),
        ("last_3m", pd.DateOffset(months=3)),
        ("last_6m", pd.DateOffset(months=6)),
        ("last_1y", pd.DateOffset(years=1)),
    ]
    for name, delta in recent_windows:
        start = max(train_start, full_end - delta)
        source = oos_trades if start >= oos_start else trades
        windows.append((name, start, full_end, source))
    return [
        {"window": name, "start": left, "end": right, **engine.metrics(source, left, right)}
        for name, left, right, source in windows
    ]


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2f}x"


def main() -> None:
    args = parse_args()
    base = load_base()
    engine = base.load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    raw_frame, funding, quality = base.load_data()
    raw_start = pd.Timestamp(raw_frame["ts"].iloc[0])
    full_end = pd.Timestamp(raw_frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    oos_start = full_end - pd.DateOffset(months=base.LOCKED_OOS_MONTHS)
    train_start = raw_start + pd.Timedelta(days=base.WARMUP_DAYS)
    train_end = (train_start + (oos_start - train_start) * 0.70).floor("h")
    split = {
        "raw_start": raw_start.isoformat(),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "validation_end": oos_start.isoformat(),
        "oos_start": oos_start.isoformat(),
        "full_end": full_end.isoformat(),
    }
    print(f"data rows={len(raw_frame)} split={split}", flush=True)

    prefit_raw = raw_frame.loc[raw_frame["ts"] < oos_start].copy().reset_index(drop=True)
    prefit_funding = funding.loc[funding["ts"] < oos_start].copy().reset_index(drop=True)
    prefit_frame = engine.add_features(prefit_raw, prefit_funding)
    prefit_funding_times, prefit_funding_cumulative = engine.funding_prefix(prefit_funding)

    rng = random.Random(args.seed)
    curated = [
        cap3_config(cfg, name=base.bnb_name(cfg.name).replace("BNB_1H_AR", "BNB_1H_CAP3_HW"))
        for cfg in engine.curated_configs()
    ]
    random_configs = [
        cap3_config(
            engine.random_config(rng, index + len(curated)),
            name=f"BNB_1H_CAP3_HW_R{index + len(curated):07d}",
        )
        for index in range(args.random_configs)
    ]
    configs = curated + random_configs
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
            prefit_frame, signal, cfg, prefit_funding_times, prefit_funding_cumulative
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
            best = max(retained, key=lambda row: candidate_sort_key(row[0]))[0]
            print(
                f"first {index}/{len(configs)} eligible={counts['first_pass_eligible']} "
                f"passes={counts['first_pass_prefit_pass']} best={best.name} "
                f"ann={best.prefit['annual_multiple']:.3f} dd={best.prefit['max_dd']:.3f} "
                f"win={best.prefit['win_rate']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda row: candidate_sort_key(row[0]), reverse=True)[
        : args.prefit_keep
    ]
    if not retained:
        raise RuntimeError("No cap3 high-win first-pass config survived")

    seeds = [row[1] for row in retained[: args.seed_pool]]
    seen = {tuple((key, value) for key, value in asdict(cfg).items() if key != "name") for cfg in seeds}
    for index in range(args.neighbors):
        cfg = base.mutate_config(
            engine,
            seeds[index % len(seeds)],
            rng,
            args.random_configs + len(curated) + index,
        )
        cfg = cap3_config(cfg, name=f"BNB_1H_CAP3_HW_N{args.random_configs + len(curated) + index:07d}")
        key = tuple((name, value) for name, value in asdict(cfg).items() if name != "name")
        if key in seen:
            continue
        seen.add(key)
        signal = engine.build_signal(prefit_frame, cfg)
        if int(np.count_nonzero(signal)) < 8:
            continue
        trades = engine.simulate_trades(
            prefit_frame, signal, cfg, prefit_funding_times, prefit_funding_cumulative
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
            best = max(retained, key=lambda row: candidate_sort_key(row[0]))[0]
            print(
                f"neighbor {index + 1}/{args.neighbors} eligible={counts['neighbors_eligible']} "
                f"passes={counts['neighbors_prefit_pass']} best={best.name} "
                f"ann={best.prefit['annual_multiple']:.3f} dd={best.prefit['max_dd']:.3f} "
                f"win={best.prefit['win_rate']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda row: candidate_sort_key(row[0]), reverse=True)[
        : args.prefit_keep
    ]

    ensembles: list[tuple[Any, tuple[Any, Any], list[Any], tuple[float, float]]] = []
    if not args.no_ensembles:
        ensembles = make_ensembles(engine, retained, train_start, train_end, oos_start)
    counts["retained_singles"] = len(retained)
    counts["retained_ensembles"] = len(ensembles)

    rows: list[dict[str, Any]] = []
    for candidate, cfg, _trades in retained:
        row = candidate_row(candidate)
        row.update({f"cfg_{key}": value for key, value in asdict(cfg).items()})
        rows.append(row)
    for candidate, pair, _trades, priorities in ensembles:
        row = candidate_row(candidate)
        row["left_config"] = json.dumps(asdict(pair[0]), sort_keys=True)
        row["right_config"] = json.dumps(asdict(pair[1]), sort_keys=True)
        row["priorities"] = json.dumps(priorities)
        rows.append(row)
    rows.sort(key=lambda row: (bool(row["prefit_pass"]), float(row["prefit_score"])), reverse=True)
    pd.DataFrame(rows).to_csv(PREFIT_CSV, index=False)
    if args.prefit_only:
        print(json.dumps(json_safe({"status": "prefit_only", "counts": counts, "best": rows[0]}), indent=2, ensure_ascii=False))
        return

    best_single = retained[0]
    best_ensemble = ensembles[0] if ensembles else None
    if best_ensemble is not None and candidate_sort_key(best_ensemble[0]) > candidate_sort_key(best_single[0]):
        primary_candidate = best_ensemble[0]
        primary_configs = best_ensemble[1]
        primary_prefit_trades = best_ensemble[2]
        primary_priorities = best_ensemble[3]
        primary_kind = "ensemble"
    else:
        primary_candidate = best_single[0]
        primary_configs = (best_single[1],)
        primary_prefit_trades = best_single[2]
        primary_priorities = (best_single[0].prefit_score,)
        primary_kind = "single"

    freeze_payload = {
        "frozen_before_oos_unlock": True,
        "family": "BNB-1H-Adaptive-Regime",
        "search_name": "cap3_highwin_trend_reversion",
        "primary_name": primary_candidate.name,
        "primary_kind": primary_kind,
        "selection_rule": "cap3_prefit_pass_then_highwin_score",
        "targets": {
            "annual_multiple_min": TARGET_HIGHWIN_ANNUAL_MULTIPLE,
            "win_rate_around": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
            "max_leverage": MAX_LEVERAGE,
        },
        "split": split,
        "prefit_metrics": candidate_row(primary_candidate),
        "configs": [asdict(cfg) for cfg in primary_configs],
        "priorities": primary_priorities,
        "locked_oos_read_count_planned": 1,
    }
    FREEZE_JSON.write_text(json.dumps(json_safe(freeze_payload), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PRIMARY FROZEN kind={primary_kind} name={primary_candidate.name}; unlocking OOS once", flush=True)

    full_frame = engine.add_features(raw_frame, funding)
    full_funding_times, full_funding_cumulative = engine.funding_prefix(funding)

    def strategy_trades(start: pd.Timestamp | None) -> list[Any]:
        parts = [
            simulate(engine, full_frame, cfg, full_funding_times, full_funding_cumulative, start)
            for cfg in primary_configs
        ]
        if len(parts) == 1:
            return parts[0]
        return engine.merge_trade_sets(parts[0], parts[1], primary_priorities[0], primary_priorities[1])

    full_trades = strategy_trades(None)
    oos_trades = strategy_trades(oos_start)
    full_metrics = engine.metrics(full_trades, train_start, full_end)
    oos_metrics = engine.metrics(oos_trades, oos_start, full_end)
    primary_candidate.full = full_metrics
    primary_candidate.holdout = oos_metrics
    primary_candidate.target_pass = target_gate(oos_metrics, full_metrics)
    slices = metric_rows(
        engine,
        full_trades,
        train_start,
        train_end,
        oos_start,
        oos_start,
        full_end,
        oos_trades,
    )
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame([asdict(trade) for trade in full_trades]).to_csv(TRADES_CSV, index=False)

    status = (
        "cap3_highwin_hit_pending_robustness_not_promoted"
        if primary_candidate.target_pass
        else "cap3_highwin_no_go_locked_oos_or_full_failed_not_promoted"
    )
    payload = {
        "family": "BNB-1H-Adaptive-Regime",
        "family_id": "BNB-1H-AR",
        "status": status,
        "targets": freeze_payload["targets"],
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "data_quality": quality,
        "split": split,
        "search_counts": counts,
        "primary": candidate_row(primary_candidate),
        "primary_configs": [asdict(cfg) for cfg in primary_configs],
        "primary_priorities": primary_priorities,
        "slices": slices,
        "oos_protocol": {
            "prefit_frame_excludes_oos": True,
            "primary_frozen_before_full_features": True,
            "locked_primaries_evaluated": 1,
        },
    }
    SUMMARY_JSON.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# BNB-1H-Adaptive-Regime cap3 高胜率趋势/反转搜索 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            "唯一冻结 primary 满足 cap3 高胜率诊断目标；仍需稳健性和 live-executable 审计，不代表可实盘。"
            if primary_candidate.target_pass
            else "唯一冻结 primary 未能同时满足 full 与最近三个月 locked OOS 的 cap3 高胜率目标，当前为 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        f"- primary：`{primary_candidate.name}`；kind/styles：`{primary_kind}` / `{primary_candidate.styles}`。",
        f"- prefit：annual `{mult(primary_candidate.prefit['annual_multiple'])}`，DD `{pct(primary_candidate.prefit['max_dd'])}`，win `{pct(primary_candidate.prefit['win_rate'])}`，trades `{int(primary_candidate.prefit['trades'])}`，PF `{primary_candidate.prefit['profit_factor']:.3f}`。",
        f"- full：annual `{mult(full_metrics['annual_multiple'])}`，return `{pct(full_metrics['total_return'])}`，DD `{pct(full_metrics['max_dd'])}`，win `{pct(full_metrics['win_rate'])}`，trades `{int(full_metrics['trades'])}`，PF `{full_metrics['profit_factor']:.3f}`。",
        f"- locked OOS：annual `{mult(oos_metrics['annual_multiple'])}`，return `{pct(oos_metrics['total_return'])}`，DD `{pct(oos_metrics['max_dd'])}`，win `{pct(oos_metrics['win_rate'])}`，trades `{int(oos_metrics['trades'])}`，PF `{oos_metrics['profit_factor']:.3f}`。",
        f"- cap3 high-win gate：`{primary_candidate.target_pass}`。",
        "",
        "## 数据与协议",
        "",
        f"- Binance USD-M Futures `BNBUSDT` perpetual `1h`：`{quality['rows']}` 根闭合 K；UTC `{quality['first_ts']}` 至 `{quality['last_ts']}`；missing/duplicate=`{quality['missing_bars']}/{quality['duplicate_bars']}`。",
        f"- train：`{split['train_start']}` 至 `{split['train_end']}`；validation 至 `{split['validation_end']}`；locked OOS 至 `{split['full_end']}`。",
        "- prefit feature frame 物理排除 OOS；只评估一个预先落盘 primary。",
        "- 杠杆硬约束：所有组件 `fixed_leverage/max_leverage <= 3.0`。",
        "",
        "## 搜索覆盖",
        "",
    ]
    lines.extend(f"- {key}：`{value}`。" for key, value in counts.items())
    lines.extend(
        [
            "- 机制覆盖：趋势类 `ema_cross/macd_flip/donchian_break/bb_break/ema_pullback/keltner_break/squeeze_release/di_cross/momentum_break`；反转类 `bb_revert/rsi_reversal/stoch_reversal/cci_reversal/williams_reversal/vwap_revert/wick_reject`；并测试趋势+反转 ensemble。",
            "",
            "## 分片",
            "",
            "| Window | Annual | Return | DD | Win | Trades | PF |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | `{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | `{pct(row['win_rate'])}` | `{int(row['trades'])}` | `{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            (
                "该结果只是 cap3 high-win diagnostic hit；还需参数邻域、成本/延迟、逐 K 回撤、清算边界、重启恢复和生产状态机审计，完成前禁止 candidate/paper-live/live。"
                if primary_candidate.target_pass
                else "cap3 high-win gate 未通过，禁止 candidate、paper-live、dry-run、handoff 或 live。"
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
            json_safe({"status": status, "counts": counts, "primary": candidate_row(primary_candidate)}),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
