"""High-win-rate hard-target search for SOL-1H-Adaptive-Regime.

Targets: annual equity multiple >= 10.0x, win rate >= 80%, max drawdown
strictly better than -20%. Selection uses train/validation only; the last
three months are the V1-era holdout, already unblinded on 2026-07-03, so
they are evaluated as REUSED holdout, never used for selection.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
BASE_SEARCH_PATH = SCRIPT_DIR / "research_sol_1h_adaptive_regime_search.py"

DATE_TAG = "2026-07-07"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_high_win_search_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"sol_1h_ar_high_win_prefit_{DATE_TAG}.csv"
RANKING_CSV = ARTIFACT_DIR / f"sol_1h_ar_high_win_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"sol_1h_ar_high_win_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"sol_1h_ar_high_win_top_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"sol-1h-ar-high-win-target-search-{DATE_TAG}.md"

TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20
STANDARD_SLICES = (
    ("last_1d", pd.Timedelta(days=1)),
    ("last_7d", pd.Timedelta(days=7)),
    ("last_1m", pd.Timedelta(days=30)),
    ("last_3m", pd.Timedelta(days=91)),
    ("last_6m", pd.Timedelta(days=182)),
    ("last_1y", pd.Timedelta(days=365)),
)


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location(
        "sol_1h_base_search", BASE_SEARCH_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load base search: {BASE_SEARCH_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply_high_win_overrides(engine: Any) -> None:
    engine.TARGET_ANNUAL_MULTIPLE = TARGET_ANNUAL_MULTIPLE
    engine.TARGET_WIN_RATE = TARGET_WIN_RATE
    engine.TARGET_MAX_DD = TARGET_MAX_DD
    engine.MIN_PREFIT_TRADES = 40
    engine.MIN_VALIDATION_TRADES = 10
    engine.MIN_HOLDOUT_TRADES = 12

    def high_win_prefit_score(
        train: dict[str, float],
        validation: dict[str, float],
        prefit: dict[str, float],
    ) -> float:
        if (
            prefit["trades"] < engine.MIN_PREFIT_TRADES
            or validation["trades"] < engine.MIN_VALIDATION_TRADES
        ):
            return -1e9
        log_ann = [
            math.log(min(max(item["annual_multiple"], 1e-9), 1e6))
            for item in (train, validation, prefit)
        ]
        dd_penalty = sum(
            max(0.0, -0.20 - item["max_dd"]) * 12.0
            for item in (train, validation, prefit)
        )
        win_shortfall = sum(
            max(0.0, TARGET_WIN_RATE - item["win_rate"]) * 8.0
            for item in (train, validation, prefit)
        )
        negative_penalty = 4.0 * sum(
            item["total_return"] <= 0.0 for item in (train, validation)
        )
        score = (
            0.7 * log_ann[2]
            + 0.8 * min(log_ann[0], log_ann[1])
            + 0.25 * min(prefit["profit_factor"], 5.0)
            + 2.5 * min(prefit["win_rate"], 0.90)
            - dd_penalty
            - win_shortfall
            - negative_penalty
        )
        if engine.prefit_gate(train, validation, prefit):
            score += 8.0
        return float(score)

    engine.prefit_score = high_win_prefit_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "High-win hard-target (10x / 80% / <20% DD) SOLUSDT 1h search "
            "over the frozen two-year research frame."
        )
    )
    parser.add_argument("--random-configs", type=int, default=600_000)
    parser.add_argument("--seed", type=int, default=20260707)
    parser.add_argument("--prefit-keep", type=int, default=600)
    parser.add_argument("--holdout-keep", type=int, default=250)
    parser.add_argument("--progress-every", type=int, default=20_000)
    parser.add_argument("--no-ensembles", action="store_true")
    return parser.parse_args()


def standard_slice_rows(
    engine: Any, trades: list[Any], full_end: pd.Timestamp
) -> list[dict[str, Any]]:
    rows = []
    for name, delta in STANDARD_SLICES:
        metric = engine.metrics(trades, full_end - delta, full_end)
        rows.append({"window": name, **metric})
    return rows


def hard_pass(engine: Any, metric: dict[str, float], min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= TARGET_WIN_RATE
        and metric["max_dd"] > TARGET_MAX_DD
    )


def pct(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def make_report(
    engine: Any,
    *,
    quality: dict[str, Any],
    split: dict[str, str],
    search_counts: dict[str, int],
    finalists: list[Any],
    best: Any,
    slices: list[dict[str, Any]],
    standard_slices: list[dict[str, Any]],
    last1y_pass_count: int,
) -> str:
    holdout = best.holdout or engine.empty_metrics(1.0)
    full = best.full or engine.empty_metrics(1.0)
    target_hits = sum(candidate.target_pass for candidate in finalists)
    prefit_hits = sum(candidate.prefit_pass for candidate in finalists)
    lines = [
        f"# SOL-1H-Adaptive-Regime 高胜率硬目标搜索 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "至少一个冻结 finalist 同时通过 full 与最近三个月 reused holdout 的三项硬门槛；这只允许进入稳健性和 live-executable 审计，不代表已可实盘。"
            if target_hits
            else "没有任何冻结 finalist 同时通过 full 与最近三个月 reused holdout 的三项硬门槛，本轮结论为 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        f"- finalists：`{len(finalists)}`；prefit pass：`{prefit_hits}`；reused-holdout target pass：`{target_hits}`；同时通过 last-1y 硬形状的 finalists：`{last1y_pass_count}`。",
        f"- 目标：年化权益倍率 `>= {TARGET_ANNUAL_MULTIPLE:.1f}x`（annual return `>= 900%`）、胜率 `>= {TARGET_WIN_RATE:.0%}`、最大回撤严格小于 `20%`。",
        "",
        "## OOS 状态声明",
        "",
        "- 最近三个月窗口已在 2026-07-03 的 V1 广搜揭盲，本轮属于 reused holdout，不是新鲜 locked OOS。",
        "- 本轮选择、打分、保留和 ensemble 仍只使用 train + validation；reused holdout 只对冻结 finalists 评估一次，不参与选择。",
        "- 即使命中硬门槛，也必须先补新鲜 forward 数据与 live-executable 审计，才能讨论 promotion。",
        "",
        "## 数据质量",
        "",
        f"- Binance USD-M Futures `SOLUSDT` perpetual `1h`：`{quality['rows']}` 根闭合 K（冻结研究帧，与 V1 相同）。",
        f"- UTC：`{quality['first_ts']}` 至 `{quality['last_ts']}`。",
        f"- missing=`{quality['missing_bars']}`，duplicate=`{quality['duplicate_bars']}`，funding rows=`{quality['funding_rows']}`。",
        "",
        "## 时间切分",
        "",
        f"- train：`{split['train_start']}` 至 `{split['train_end']}`。",
        f"- validation：`{split['train_end']}` 至 `{split['validation_end']}`。",
        f"- reused holdout（最近三个月，V1 已揭盲）：`{split['oos_start']}` 至 `{split['full_end']}`。",
        "",
        "## 执行与成本",
        "",
        "- 闭合 `1h` K 生成信号，下一根 open 市价入场；单仓、不加仓。",
        "- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。",
        "- trailing 仅在完整 K 结束后更新，更新后的 stop 从下一根 K 生效。",
        f"- fee `{engine.FEE_PER_FILL:.4%}/fill`，slippage `{engine.SLIPPAGE_PER_FILL:.4%}/fill`，另逐笔计入真实 Binance funding。",
        "",
        "## 搜索覆盖",
        "",
    ]
    lines.extend(f"- {key}：`{value}`。" for key, value in search_counts.items())
    lines.extend(
        [
            "- 打分向高胜率倾斜：win-rate 奖励封顶 `90%`，低于 `80%` 逐项罚分；机制面与 V1 广搜相同。",
            "",
            "## 最佳冻结 finalist",
            "",
            f"- id：`{best.name}`；kind/style：`{best.kind}` / `{best.styles}`。",
            f"- full：annual `{mult(full['annual_multiple'])}`，return `{pct(full['total_return'])}`，DD `{pct(full['max_dd'])}`，win `{pct(full['win_rate'])}`，trades `{int(full['trades'])}`，PF `{full['profit_factor']:.3f}`。",
            f"- reused holdout：annual `{mult(holdout['annual_multiple'])}`，return `{pct(holdout['total_return'])}`，DD `{pct(holdout['max_dd'])}`，win `{pct(holdout['win_rate'])}`，trades `{int(holdout['trades'])}`，PF `{holdout['profit_factor']:.3f}`。",
            f"- hard gate：`{best.target_pass}`。",
            "",
            "## 标准近期分片（锚定数据集末端，仅审计不选参）",
            "",
            "| Window | Annual | Return | DD | Win | Trades | PF |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in standard_slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | `{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | `{pct(row['win_rate'])}` | `{int(row['trades'])}` | `{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 时间切片（引擎标准窗口）",
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
                "硬门槛命中只进入延迟、成本、邻域、时间稳定性、fresh forward 与生产状态机审计；审计前禁止标记为 candidate/paper-live/live。"
                if target_hits
                else "reused-holdout hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。"
            ),
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{PREFIT_CSV.relative_to(ROOT)}`",
            f"- `{RANKING_CSV.relative_to(ROOT)}`",
            f"- `{SLICES_CSV.relative_to(ROOT)}`",
            f"- `{TRADES_CSV.relative_to(ROOT)}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_high_win_target_search.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    base = load_base()
    engine = base.load_engine()
    apply_high_win_overrides(engine)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=base.WARMUP_DAYS)
    oos_start = full_end - pd.DateOffset(months=base.LOCKED_OOS_MONTHS)
    if not train_start < oos_start < full_end:
        raise RuntimeError("Invalid train/holdout split")
    prefit_span = oos_start - train_start
    train_end = train_start + prefit_span * 0.65
    split = {
        "raw_start": raw_start.isoformat(),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "validation_end": oos_start.isoformat(),
        "oos_start": oos_start.isoformat(),
        "full_end": full_end.isoformat(),
    }
    print(f"data rows={len(frame)} split={split}", flush=True)

    rng = random.Random(args.seed)
    configs = [
        replace(cfg, name=f"HW_{base.sol_name(cfg.name)}")
        for cfg in engine.curated_configs()
    ]
    random_offset = len(configs)
    configs.extend(
        replace(
            engine.random_config(rng, index + random_offset),
            name=f"SOL_1H_AR_HW_R{index + random_offset:06d}",
        )
        for index in range(args.random_configs)
    )

    retained: list[tuple[Any, Any]] = []
    evaluated = 0
    eligible = 0
    prefit_passes = 0
    for index, cfg in enumerate(configs, start=1):
        signal = engine.build_signal(frame, cfg)
        if int(np.count_nonzero(signal)) < 6:
            continue
        trades = engine.simulate_trades(
            frame, signal, cfg, funding_times, funding_cumulative
        )
        candidate = engine.candidate_from_config(
            cfg, trades, train_start, train_end, oos_start
        )
        evaluated += 1
        if candidate is None:
            continue
        eligible += 1
        prefit_passes += int(candidate.prefit_pass)
        retained = engine.retain_candidate(retained, (candidate, cfg), args.prefit_keep)
        if index % args.progress_every == 0 and retained:
            current = max(
                retained, key=lambda item: engine.candidate_sort_key(item[0])
            )[0]
            print(
                f"search {index}/{len(configs)} evaluated={evaluated} "
                f"eligible={eligible} prefit_pass={prefit_passes} "
                f"retained={len(retained)} best={current.name} "
                f"score={current.prefit_score:.3f} "
                f"ann={current.prefit['annual_multiple']:.3f} "
                f"dd={current.prefit['max_dd']:.3f} "
                f"win={current.prefit['win_rate']:.3f}",
                flush=True,
            )
    retained = sorted(
        retained,
        key=lambda item: engine.candidate_sort_key(item[0]),
        reverse=True,
    )[: args.prefit_keep]
    if not retained:
        raise RuntimeError("No eligible SOL configs survived the prefit gates")
    config_map = {cfg.name: cfg for _candidate, cfg in retained}
    pd.DataFrame(
        [engine.candidate_row(candidate, config_map) for candidate, _cfg in retained]
    ).to_csv(PREFIT_CSV, index=False)
    print(
        f"single search done generated={len(configs)} evaluated={evaluated} "
        f"eligible={eligible} prefit_pass={prefit_passes} "
        f"retained={len(retained)}",
        flush=True,
    )

    ensembles: list[tuple[Any, tuple[Any, Any], list[Any]]] = []
    if not args.no_ensembles:
        ensembles = engine.make_ensembles(
            retained,
            frame,
            funding_times,
            funding_cumulative,
            train_start,
            train_end,
            oos_start,
        )
        print(f"ensembles retained={len(ensembles)}", flush=True)

    finalists: list[tuple[Any, list[Any]]] = []
    for candidate, cfg in retained[: args.holdout_keep]:
        trades = engine.simulate_trades(
            frame,
            engine.build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        finalists.append(
            (
                engine.finalize_candidate(
                    candidate, trades, train_start, oos_start, full_end
                ),
                trades,
            )
        )
    for candidate, _cfg_pair, trades in ensembles[: args.holdout_keep]:
        finalists.append(
            (
                engine.finalize_candidate(
                    candidate, trades, train_start, oos_start, full_end
                ),
                trades,
            )
        )
    # The reused holdout may validate a candidate but must never choose it.
    finalists.sort(key=lambda item: engine.candidate_sort_key(item[0]), reverse=True)
    best, best_trades = finalists[0]
    ranking = pd.DataFrame(
        [
            engine.candidate_row(candidate, config_map)
            for candidate, _trades in finalists
        ]
    )
    ranking.to_csv(RANKING_CSV, index=False)
    slices = engine.diagnostic_slices(
        best_trades, train_start, train_end, oos_start, full_end
    )
    standard_slices = standard_slice_rows(engine, best_trades, full_end)
    pd.DataFrame(slices + standard_slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(best_trades)).to_csv(TRADES_CSV, index=False)

    last1y_pass_count = 0
    for candidate, trades in finalists:
        if not candidate.target_pass:
            continue
        last1y = engine.metrics(trades, full_end - pd.Timedelta(days=365), full_end)
        last1y_pass_count += int(
            hard_pass(engine, last1y, engine.MIN_HOLDOUT_TRADES)
        )

    search_counts = {
        "curated_configs": len(configs) - args.random_configs,
        "random_configs": args.random_configs,
        "generated_configs": len(configs),
        "evaluated_configs": evaluated,
        "prefit_eligible": eligible,
        "prefit_pass_observations": prefit_passes,
        "retained_single": len(retained),
        "retained_ensembles": len(ensembles),
        "holdout_finalists": len(finalists),
        "reused_holdout_target_pass": sum(
            candidate.target_pass for candidate, _trades in finalists
        ),
        "last_1y_hard_pass_among_target_pass": last1y_pass_count,
    }
    used_names = set(best.config_names.split("+"))
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "family_id": "SOL-1H-AR",
        "run": "high_win_hard_target_search",
        "status": (
            "hard_gate_hit_on_reused_holdout_pending_fresh_oos_not_promoted"
            if any(candidate.target_pass for candidate, _ in finalists)
            else "no_go_not_promoted"
        ),
        "oos_disclosure": "last_three_months_reused_holdout_unblinded_2026-07-03",
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "annual_return": TARGET_ANNUAL_MULTIPLE - 1.0,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "split": split,
        "quality": quality,
        "search_counts": search_counts,
        "best": engine.candidate_row(best, config_map),
        "best_configs": {
            name: asdict(config_map[name]) for name in used_names if name in config_map
        },
        "top_20": [
            engine.candidate_row(candidate, config_map)
            for candidate, _trades in finalists[:20]
        ],
        "slices": slices,
        "standard_slices": standard_slices,
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        make_report(
            engine,
            quality=quality,
            split=split,
            search_counts=search_counts,
            finalists=[candidate for candidate, _trades in finalists],
            best=best,
            slices=slices,
            standard_slices=standard_slices,
            last1y_pass_count=last1y_pass_count,
        ),
        encoding="utf-8",
    )
    best_full = best.full or engine.empty_metrics(1.0)
    best_oos = best.holdout or engine.empty_metrics(1.0)
    print(
        f"best={best.name} target_pass={best.target_pass} "
        f"full_ann={best_full['annual_multiple']:.3f} "
        f"full_dd={best_full['max_dd']:.3f} "
        f"full_win={best_full['win_rate']:.3f} "
        f"oos_ann={best_oos['annual_multiple']:.3f} "
        f"oos_dd={best_oos['max_dd']:.3f} "
        f"oos_win={best_oos['win_rate']:.3f}",
        flush=True,
    )
    print(f"wrote {SUMMARY_JSON}", flush=True)
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
