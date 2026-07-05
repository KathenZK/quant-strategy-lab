from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import random
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_trx_1h_ar_v1_clean_strict_ablation_slices as strict_audit  # noqa: E402
import research_trx_1h_adaptive_regime_refine as refine  # noqa: E402
import research_trx_1h_adaptive_regime_search as search  # noqa: E402


base = search.load_engine()

FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
DATE_TAG = "2026-07-03"
REFINE_JSON = ARTIFACT_DIR / f"trx_1h_adaptive_regime_refine_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_recent_adaptation_search_{DATE_TAG}.json"
RANKING_CSV = ARTIFACT_DIR / f"trx_1h_ar_recent_adaptation_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_recent_adaptation_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"trx_1h_ar_recent_adaptation_top_trades_{DATE_TAG}.csv"
TRADE_AUDIT_CSV = ARTIFACT_DIR / f"trx_1h_ar_recent_adaptation_trade_audit_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"trx-1h-ar-recent-adaptation-search-{DATE_TAG}.md"

_WORK_FRAME: pd.DataFrame | None = None
_WORK_FUNDING_TIMES: Any = None
_WORK_FUNDING_CUMULATIVE: Any = None
_WORK_TRAIN_START: pd.Timestamp | None = None
_WORK_FULL_END: pd.Timestamp | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recent-adaptation diagnostic search for TRX 1h AR."
    )
    parser.add_argument("--random-configs", type=int, default=40_000)
    parser.add_argument("--neighbors", type=int, default=40_000)
    parser.add_argument("--seed", type=int, default=2026070317)
    parser.add_argument("--keep", type=int, default=600)
    parser.add_argument("--ensemble-legs", type=int, default=35)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=5_000)
    return parser.parse_args()


def pct(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 3) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def standard_windows(
    *,
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    candidates = [
        ("last_1d", full_end - pd.Timedelta(days=1)),
        ("last_7d", full_end - pd.Timedelta(days=7)),
        ("last_1m", full_end - pd.DateOffset(months=1)),
        ("last_3m", full_end - pd.DateOffset(months=3)),
        ("last_6m", full_end - pd.DateOffset(months=6)),
        ("last_1y", full_end - pd.DateOffset(years=1)),
    ]
    return [
        (name, max(train_start, start), full_end)
        for name, start in candidates
        if max(train_start, start) < full_end
    ]


def metric_bundle(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> dict[str, dict[str, float]]:
    return {
        name: base.metrics(trades, start, end)
        for name, start, end in standard_windows(
            train_start=train_start,
            full_end=full_end,
        )
    } | {"full": base.metrics(trades, train_start, full_end)}


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def shape_ok(metric: dict[str, float], *, min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= 10.0
        and metric["max_dd"] > -0.20
        and metric["win_rate"] >= 0.50
    )


def positive_ok(metric: dict[str, float], *, min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["total_return"] > 0.0
        and metric["max_dd"] > -0.20
        and metric["win_rate"] >= 0.50
    )


def recent_score(metrics: dict[str, dict[str, float]]) -> float:
    y1 = metrics["last_1y"]
    m6 = metrics["last_6m"]
    m3 = metrics["last_3m"]
    m1 = metrics["last_1m"]
    full = metrics["full"]
    score = 0.0
    for weight, metric in (
        (1.1, y1),
        (1.0, m6),
        (0.9, m3),
        (0.6, m1),
        (0.35, full),
    ):
        score += weight * math.log(max(metric["annual_multiple"], 1e-9))
        score += 0.4 * weight * min(metric["profit_factor"], 5.0)
        score += 0.5 * weight * metric["win_rate"]
        score -= 10.0 * weight * max(0.0, -0.20 - metric["max_dd"])
        score -= 3.0 * weight * max(0.0, -metric["total_return"])
    if shape_ok(y1, min_trades=24):
        score += 5.0
    if positive_ok(m6, min_trades=12):
        score += 2.0
    if positive_ok(m3, min_trades=6):
        score += 2.0
    if m1["trades"] >= 2 and m1["total_return"] >= 0.0:
        score += 1.0
    if y1["trades"] < 18:
        score -= 6.0
    return float(score)


def recent_hard_pass(metrics: dict[str, dict[str, float]]) -> bool:
    return bool(
        shape_ok(metrics["last_1y"], min_trades=24)
        and positive_ok(metrics["last_6m"], min_trades=12)
        and positive_ok(metrics["last_3m"], min_trades=6)
        and metrics["last_1m"]["trades"] >= 2
        and metrics["last_1m"]["total_return"] >= 0.0
        and metrics["last_1m"]["max_dd"] > -0.12
    )


def row_from_candidate(
    *,
    name: str,
    kind: str,
    styles: str,
    config_names: str,
    score: float,
    metrics: dict[str, dict[str, float]],
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "styles": styles,
        "config_names": config_names,
        "recent_score": score,
        "recent_hard_pass": recent_hard_pass(metrics),
        **flatten_metrics(metrics),
    }


def evaluate_config(
    cfg: Any,
) -> tuple[dict[str, Any] | None, Any]:
    if (
        _WORK_FRAME is None
        or _WORK_FUNDING_TIMES is None
        or _WORK_FUNDING_CUMULATIVE is None
        or _WORK_TRAIN_START is None
        or _WORK_FULL_END is None
    ):
        raise RuntimeError("Recent search worker state was not initialized")
    signal = base.build_signal(_WORK_FRAME, cfg)
    if int(np.count_nonzero(signal)) < 4:
        return None, cfg
    trades = base.simulate_trades(
        _WORK_FRAME,
        signal,
        cfg,
        _WORK_FUNDING_TIMES,
        _WORK_FUNDING_CUMULATIVE,
    )
    metrics = metric_bundle(
        trades,
        train_start=_WORK_TRAIN_START,
        full_end=_WORK_FULL_END,
    )
    if metrics["last_1y"]["trades"] < 6:
        return None, cfg
    score = recent_score(metrics)
    row = row_from_candidate(
        name=cfg.name,
        kind="single",
        styles=cfg.style,
        config_names=cfg.name,
        score=score,
        metrics=metrics,
    )
    return row, cfg


def load_seed_configs() -> list[Any]:
    configs: dict[str, Any] = {}
    if REFINE_JSON.exists():
        source = json.loads(REFINE_JSON.read_text(encoding="utf-8"))
        for name, values in source.get("retained_configs", {}).items():
            configs[name] = base.StrategyConfig(**values)
    return list(configs.values())


def generate_configs(args: argparse.Namespace, seeds: list[Any]) -> list[Any]:
    rng = random.Random(args.seed)
    configs: list[Any] = []
    seen: set[tuple[Any, ...]] = set()

    def add(cfg: Any) -> None:
        values = asdict(cfg)
        key = tuple((key, value) for key, value in values.items() if key != "name")
        if key in seen:
            return
        seen.add(key)
        configs.append(cfg)

    for seed_cfg in seeds:
        add(seed_cfg)
    for index in range(args.random_configs):
        cfg = base.random_config(rng, index)
        add(replace(cfg, name=f"TRX_1H_AR_REC_R{index:06d}"))
    if seeds:
        attempts = 0
        while attempts < args.neighbors * 3 and len(configs) < len(seeds) + args.random_configs + args.neighbors:
            attempts += 1
            cfg = refine.mutate(
                rng.choice(seeds),
                rng=rng,
                index=attempts,
            )
            add(replace(cfg, name=f"TRX_1H_AR_REC_N{attempts:06d}"))
    return configs


def retain(
    retained: list[tuple[dict[str, Any], Any]],
    item: tuple[dict[str, Any], Any],
    keep: int,
) -> list[tuple[dict[str, Any], Any]]:
    retained.append(item)
    if len(retained) > keep * 3:
        retained = sorted(
            retained,
            key=lambda pair: (
                int(pair[0]["recent_hard_pass"]),
                pair[0]["recent_score"],
                pair[0]["last_1y_annual_multiple"],
                pair[0]["last_6m_total_return"],
            ),
            reverse=True,
        )[:keep]
    return retained


def simulate_config(
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    cfg: Any,
) -> list[Any]:
    return base.simulate_trades(
        frame,
        base.build_signal(frame, cfg),
        cfg,
        funding_times,
        funding_cumulative,
    )


def evaluate_ensembles(
    retained: list[tuple[dict[str, Any], Any]],
    *,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
    ensemble_legs: int,
) -> list[tuple[dict[str, Any], tuple[Any, Any], list[Any]]]:
    trend = [
        item for item in retained if item[1].style in base.TREND_STYLES
    ][:ensemble_legs]
    reversion = [
        item for item in retained if item[1].style in base.REVERSION_STYLES
    ][:ensemble_legs]
    cache: dict[str, list[Any]] = {}

    def trades_for(cfg: Any) -> list[Any]:
        if cfg.name not in cache:
            cache[cfg.name] = simulate_config(
                frame,
                funding_times,
                funding_cumulative,
                cfg,
            )
        return cache[cfg.name]

    rows: list[tuple[dict[str, Any], tuple[Any, Any], list[Any]]] = []
    for trend_row, trend_cfg in trend:
        for rev_row, rev_cfg in reversion:
            merged = base.merge_trade_sets(
                trades_for(trend_cfg),
                trades_for(rev_cfg),
                trend_row["recent_score"],
                rev_row["recent_score"],
            )
            metrics = metric_bundle(
                merged,
                train_start=train_start,
                full_end=full_end,
            )
            score = recent_score(metrics)
            row = row_from_candidate(
                name=f"ENS_REC__{trend_cfg.name}__{rev_cfg.name}",
                kind="ensemble",
                styles=f"{trend_cfg.style}+{rev_cfg.style}",
                config_names=f"{trend_cfg.name}+{rev_cfg.name}",
                score=score,
                metrics=metrics,
            )
            rows.append((row, (trend_cfg, rev_cfg), merged))
    return sorted(
        rows,
        key=lambda item: (
            int(item[0]["recent_hard_pass"]),
            item[0]["recent_score"],
            item[0]["last_1y_annual_multiple"],
            item[0]["last_6m_total_return"],
        ),
        reverse=True,
    )


def metric_line(row: dict[str, Any], prefix: str) -> str:
    return (
        f"`{row[f'{prefix}_annual_multiple']:.3f}x` / "
        f"`{pct(row[f'{prefix}_total_return'])}` / "
        f"`{pct(row[f'{prefix}_max_dd'])}` / "
        f"`{pct(row[f'{prefix}_win_rate'])}` / "
        f"`{int(row[f'{prefix}_trades'])}`"
    )


def leverage_sweep(
    *,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    configs: list[Any],
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if any(cfg.sizing_kind != "fixed" for cfg in configs):
        return rows
    for leverage in (2.5, 3.0, 3.5, 4.0, 4.5, 5.0):
        scaled = [replace(cfg, fixed_leverage=leverage) for cfg in configs]
        component_trades: list[list[Any]] = []
        scores: list[float] = []
        for cfg in scaled:
            trades = simulate_config(frame, funding_times, funding_cumulative, cfg)
            component_trades.append(trades)
            scores.append(
                recent_score(
                    metric_bundle(
                        trades,
                        train_start=train_start,
                        full_end=full_end,
                    )
                )
            )
        if len(component_trades) == 1:
            trades = component_trades[0]
        else:
            trades = base.merge_trade_sets(
                component_trades[0],
                component_trades[1],
                scores[0],
                scores[1],
            )
        metrics = metric_bundle(
            trades,
            train_start=train_start,
            full_end=full_end,
        )
        rows.append(
            {
                "fixed_leverage": leverage,
                "recent_hard_pass": recent_hard_pass(metrics),
                **flatten_metrics(metrics),
            }
        )
    return rows


def report_markdown(
    *,
    quality: dict[str, Any],
    generated: int,
    evaluated: int,
    retained_count: int,
    ensemble_count: int,
    hard_hits: int,
    best: dict[str, Any],
    slices: list[dict[str, Any]],
    leverage_rows: list[dict[str, Any]],
    execution_audit: dict[str, Any],
) -> str:
    lines = [
        "# TRX-1H-Adaptive-Regime 近期适配搜索 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "本轮近期适配搜索没有找到可 promotion 版本。"
            if hard_hits == 0
            else "本轮出现近期 hard-gate 命中，但仍需新增 forward OOS 与生产 runner 审计。"
        ),
        "",
        f"- 数据：Binance USD-M Futures `TRXUSDT` perpetual `1h`，`{quality['rows']}` 根；missing/duplicate/critical null/OHLC violation 均为 `0`。",
        f"- 搜索：生成 unique configs `{generated}`，可评估/保留 `{evaluated}/{retained_count}`，ensemble `{ensemble_count}`，recent hard hits `{hard_hits}`。",
        "- 近期 hard gate：`1y annual>=10x / DD<20% / win>=50% / trades>=24`，且 `6m/3m` 正收益、DD<20%、win>=50%，`1m` 非负且至少 2 笔。",
        "",
        "## 最佳近期观察值",
        "",
        f"- id：`{best['name']}`；kind/style：`{best['kind']}` / `{best['styles']}`。",
        f"- recent hard pass：`{best['recent_hard_pass']}`；score：`{best['recent_score']:.3f}`。",
        "",
        "| Window | Annual / Return / DD / Win / Trades |",
        "| --- | --- |",
    ]
    for prefix in ("last_1d", "last_7d", "last_1m", "last_3m", "last_6m", "last_1y", "full"):
        lines.append(f"| `{prefix}` | {metric_line(best, prefix)} |")
    lines.extend(
        [
            "",
            "## 标准分片",
            "",
            "| Slice | UTC Start | Annual / Return / DD / Win / Trades |",
            "| --- | --- | --- |",
        ]
    )
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{row['start']}` | "
            f"`{row['annual_multiple']:.3f}x` / `{pct(row['total_return'])}` / "
            f"`{pct(row['max_dd'])}` / `{pct(row['win_rate'])}` / `{int(row['trades'])}` |"
        )
    lines.extend(
        [
            "",
            "## 曝光缩放边界",
            "",
            "| Fixed leverage | 1y annual / return / DD / win / trades | Full annual / return / DD / trades | Pass |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for row in leverage_rows:
        lines.append(
            f"| `{row['fixed_leverage']:.1f}x` | "
            f"`{row['last_1y_annual_multiple']:.3f}x` / `{pct(row['last_1y_total_return'])}` / "
            f"`{pct(row['last_1y_max_dd'])}` / `{pct(row['last_1y_win_rate'])}` / `{int(row['last_1y_trades'])}` | "
            f"`{row['full_annual_multiple']:.3f}x` / `{pct(row['full_total_return'])}` / "
            f"`{pct(row['full_max_dd'])}` / `{int(row['full_trades'])}` | "
            f"`{row['recent_hard_pass']}` |"
        )
    lines.extend(
        [
            "",
            "## 执行可行性复核",
            "",
            f"- 逐笔重放违规：`{execution_audit['violation_count']}`；merged 违规：`{execution_audit['merged_violation_count']}`。",
            f"- stop gap/open 按 open 成交：`{execution_audit['stop_gap_filled_at_open']}` 次。",
            f"- target gap 以 target 价记账：`{execution_audit['target_gap_modeled_at_target']}` 次。",
            "- 该搜索直接使用已解锁近期行情做适配排序，不能声称是新鲜 OOS；若要 promotion，必须冻结参数后等待新增 forward trades。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{RANKING_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{TRADE_AUDIT_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_recent_adaptation_search.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = search.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=search.WARMUP_DAYS)

    seeds = load_seed_configs()
    configs = generate_configs(args, seeds)
    print(f"seeds={len(seeds)} generated={len(configs)}", flush=True)

    global _WORK_FRAME
    global _WORK_FUNDING_TIMES
    global _WORK_FUNDING_CUMULATIVE
    global _WORK_TRAIN_START
    global _WORK_FULL_END
    _WORK_FRAME = frame
    _WORK_FUNDING_TIMES = funding_times
    _WORK_FUNDING_CUMULATIVE = funding_cumulative
    _WORK_TRAIN_START = train_start
    _WORK_FULL_END = full_end

    retained: list[tuple[dict[str, Any], Any]] = []
    evaluated = 0
    workers = max(1, args.workers)
    if workers == 1:
        results = map(evaluate_config, configs)
        pool = None
    else:
        pool = mp.get_context("fork").Pool(processes=workers)
        results = pool.imap(evaluate_config, configs, chunksize=64)
    try:
        for index, (row, cfg) in enumerate(results, start=1):
            if row is not None:
                evaluated += 1
                retained = retain(retained, (row, cfg), args.keep)
            if index % args.progress_every == 0 and retained:
                current = max(
                    retained,
                    key=lambda pair: (
                        int(pair[0]["recent_hard_pass"]),
                        pair[0]["recent_score"],
                    ),
                )[0]
                print(
                    f"recent {index}/{len(configs)} evaluated={evaluated} "
                    f"retained={len(retained)} best={current['name']} "
                    f"score={current['recent_score']:.3f} "
                    f"1y_ann={current['last_1y_annual_multiple']:.3f} "
                    f"3m_ret={current['last_3m_total_return']:.3f}",
                    flush=True,
                )
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    retained = sorted(
        retained,
        key=lambda pair: (
            int(pair[0]["recent_hard_pass"]),
            pair[0]["recent_score"],
            pair[0]["last_1y_annual_multiple"],
            pair[0]["last_6m_total_return"],
        ),
        reverse=True,
    )[: args.keep]
    ensembles = evaluate_ensembles(
        retained,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        train_start=train_start,
        full_end=full_end,
        ensemble_legs=args.ensemble_legs,
    )
    combined: list[tuple[dict[str, Any], tuple[Any, ...] | Any, list[Any] | None]] = [
        (row, cfg, None) for row, cfg in retained
    ]
    combined.extend((row, cfg_pair, trades) for row, cfg_pair, trades in ensembles)
    combined = sorted(
        combined,
        key=lambda item: (
            int(item[0]["recent_hard_pass"]),
            item[0]["recent_score"],
            item[0]["last_1y_annual_multiple"],
            item[0]["last_6m_total_return"],
        ),
        reverse=True,
    )
    if not combined:
        raise RuntimeError("No recent-adaptation candidate survived")

    best, cfg_or_pair, best_trades = combined[0]
    if best["kind"] == "single":
        assert best_trades is None
        best_cfgs = [cfg_or_pair]
        best_trades = simulate_config(frame, funding_times, funding_cumulative, cfg_or_pair)
        component_trades = {cfg_or_pair.name: best_trades}
    else:
        assert best_trades is not None
        best_cfgs = list(cfg_or_pair)
        component_trades = {
            cfg.name: simulate_config(frame, funding_times, funding_cumulative, cfg)
            for cfg in best_cfgs
        }

    pd.DataFrame([row for row, _cfg, _trades in combined]).to_csv(RANKING_CSV, index=False)
    slice_rows = [
        {"window": name, "start": start, "end": end, **base.metrics(best_trades, start, end)}
        for name, start, end in standard_windows(train_start=train_start, full_end=full_end)
    ]
    pd.DataFrame(slice_rows).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(base.trade_rows(best_trades)).to_csv(TRADES_CSV, index=False)
    audit_rows = strict_audit.trade_audit_rows(
        frame=frame,
        merged_trades=best_trades,
        component_trades=component_trades,
        configs=best_cfgs,
    )
    audit_frame = pd.DataFrame(audit_rows)
    audit_frame.to_csv(TRADE_AUDIT_CSV, index=False)
    leverage_rows = leverage_sweep(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        configs=best_cfgs,
        train_start=train_start,
        full_end=full_end,
    )
    execution_audit = {
        "audited_rows": int(len(audit_frame)),
        "merged_trades": int(len(best_trades)),
        "violation_count": int(audit_frame["violation_count"].sum()),
        "merged_violation_count": int(
            audit_frame.loc[audit_frame["scope"] == "merged", "violation_count"].sum()
        ),
        "stop_gap_filled_at_open": int(audit_frame["stop_gap_filled_at_open"].sum()),
        "target_gap_modeled_at_target": int(audit_frame["target_gap_modeled_at_target"].sum()),
    }
    hard_hits = int(sum(row["recent_hard_pass"] for row, _cfg, _trades in combined))
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "phase": "recent_adaptation_search",
        "status": (
            "recent_hard_hit_diagnostic_not_promoted"
            if hard_hits
            else "no_recent_hard_hit_not_promoted"
        ),
        "data_quality": quality,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "generated_configs": len(configs),
        "evaluated": evaluated,
        "retained": len(retained),
        "ensembles": len(ensembles),
        "recent_hard_hits": hard_hits,
        "best": best,
        "best_configs": [asdict(cfg) for cfg in best_cfgs],
        "best_slices": slice_rows,
        "best_leverage_sweep": leverage_rows,
        "execution_audit": execution_audit,
        "top_30": [row for row, _cfg, _trades in combined[:30]],
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        report_markdown(
            quality=quality,
            generated=len(configs),
            evaluated=evaluated,
            retained_count=len(retained),
            ensemble_count=len(ensembles),
            hard_hits=hard_hits,
            best=best,
            slices=slice_rows,
            leverage_rows=leverage_rows,
            execution_audit=execution_audit,
        ),
        encoding="utf-8",
    )
    print(json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
