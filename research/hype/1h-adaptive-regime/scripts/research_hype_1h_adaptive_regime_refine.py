from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_1h_adaptive_regime_search as base  # noqa: E402


DATE_TAG = "2026-07-01"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
SOURCE_JSON = ARTIFACT_DIR / f"hype_1h_adaptive_regime_search_{DATE_TAG}.json"
SOURCE_PREFIT = ARTIFACT_DIR / f"hype_1h_adaptive_regime_prefit_{DATE_TAG}.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_prefit_{DATE_TAG}.csv"
RANKING_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_refine_top_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"hype-1h-adaptive-regime-refine-{DATE_TAG}.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dense prefit-only neighborhood refinement for HYPE 1h AR."
    )
    parser.add_argument("--neighbors", type=int, default=180_000)
    parser.add_argument("--seed", type=int, default=2026070102)
    parser.add_argument("--prefit-keep", type=int, default=600)
    parser.add_argument("--holdout-keep", type=int, default=240)
    parser.add_argument("--progress-every", type=int, default=2_000)
    return parser.parse_args()


def load_seeds() -> tuple[list[base.StrategyConfig], pd.DataFrame]:
    payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    source_rows = pd.read_csv(SOURCE_PREFIT)
    config_payload = payload["retained_single_configs"]
    configs = {
        name: base.StrategyConfig(**values) for name, values in config_payload.items()
    }
    frontier = source_rows[
        (source_rows["prefit_max_dd"] > base.TARGET_MAX_DD)
        & (source_rows["prefit_win_rate"] >= base.TARGET_WIN_RATE)
        & (source_rows["validation_total_return"] > 0.0)
        & (source_rows["validation_max_dd"] > base.TARGET_MAX_DD)
        & (source_rows["validation_win_rate"] >= base.TARGET_WIN_RATE)
    ]
    names: list[str] = []
    for table, column, count in (
        (source_rows, "prefit_score", 120),
        (source_rows, "prefit_annual_multiple", 100),
        (frontier, "prefit_annual_multiple", 120),
        (frontier, "validation_annual_multiple", 80),
    ):
        for name in table.sort_values(column, ascending=False)["name"].head(count):
            if name in configs and name not in names:
                names.append(name)
    seeds = [configs[name] for name in names]
    if not seeds:
        raise RuntimeError("No prefit-only seeds found in first-pass artifacts")
    return seeds, source_rows


def style_window(style: str, rng: random.Random) -> int:
    if style in {"bb_revert", "bb_break", "keltner_break", "squeeze_release"}:
        return rng.choice(base.BAND_WINDOWS)
    if style == "donchian_break":
        return rng.choice(base.DONCHIAN_WINDOWS)
    if style == "rsi_reversal":
        return rng.choice(base.RSI_WINDOWS)
    if style == "stoch_reversal":
        return rng.choice(base.STOCH_WINDOWS)
    if style in {"cci_reversal", "williams_reversal"}:
        return rng.choice(base.CCI_WINDOWS)
    if style == "vwap_revert":
        return rng.choice(base.VWAP_WINDOWS)
    return rng.choice(base.BAND_WINDOWS)


def mutate(
    seed: base.StrategyConfig,
    *,
    rng: random.Random,
    index: int,
) -> base.StrategyConfig:
    fields = [
        "side_mode",
        "ema_pair",
        "ema_htf",
        "indicator_window",
        "threshold_low",
        "threshold_high",
        "band_k",
        "pullback_atr",
        "roc_window",
        "roc_threshold_bps",
        "macd_set",
        "min_adx",
        "max_adx",
        "min_rvol",
        "min_atr_bps",
        "max_atr_bps",
        "min_dir_roc_bps",
        "max_dist_ema_bps",
        "htf_mode",
        "require_macd_turn",
        "require_body_dir",
        "max_aligned_funding_bps",
        "exit_kind",
        "tp_atr",
        "sl_atr",
        "trail_activation_atr",
        "trail_atr",
        "max_hold_bars",
        "cooldown_bars",
        "sizing_kind",
        "fixed_leverage",
        "risk_fraction",
        "max_leverage",
    ]
    changes = rng.sample(fields, k=rng.choice((1, 2, 2, 3, 3, 4, 5)))
    values: dict[str, Any] = {"name": f"HYPE_1H_AR_N{index:06d}"}
    for field in changes:
        if field == "side_mode":
            values[field] = rng.choice(("both", "long", "short"))
        elif field == "ema_pair":
            fast = rng.choice(base.EMA_VALUES[:-2])
            slow = rng.choice([value for value in base.EMA_VALUES if value > fast * 1.35])
            values["ema_fast"] = fast
            values["ema_slow"] = slow
        elif field == "ema_htf":
            values[field] = rng.choice((55, 89, 144, 233, 377))
        elif field == "indicator_window":
            values[field] = style_window(seed.style, rng)
        elif field == "threshold_low":
            if seed.style == "williams_reversal":
                values[field] = rng.choice((-95.0, -90.0, -85.0, -80.0, -70.0))
            elif seed.style == "squeeze_release":
                values[field] = rng.choice((-2.0, -1.5, -1.0, -0.5, 0.0))
            elif seed.style == "wick_reject":
                values[field] = rng.choice((0.15, 0.2, 0.25, 0.3, 0.35))
            else:
                values[field] = rng.choice((15.0, 20.0, 25.0, 30.0, 35.0, 40.0))
        elif field == "threshold_high":
            if seed.style == "williams_reversal":
                values[field] = rng.choice((-30.0, -20.0, -15.0, -10.0, -5.0))
            elif seed.style == "cci_reversal":
                values[field] = rng.choice((75.0, 100.0, 125.0, 150.0, 200.0))
            elif seed.style == "wick_reject":
                values[field] = rng.choice((0.65, 0.7, 0.75, 0.8, 0.85))
            else:
                values[field] = rng.choice((60.0, 65.0, 70.0, 75.0, 80.0, 85.0))
        elif field == "band_k":
            values[field] = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0))
        elif field == "pullback_atr":
            values[field] = rng.choice((-0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0))
        elif field == "roc_window":
            values[field] = rng.choice(base.ROC_WINDOWS)
        elif field == "roc_threshold_bps":
            values[field] = rng.choice((25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0))
        elif field == "macd_set":
            fast, slow, signal = rng.choice(base.MACD_SETS)
            values.update(macd_fast=fast, macd_slow=slow, macd_signal=signal)
        elif field == "min_adx":
            values[field] = rng.choice((0.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 40.0))
        elif field == "max_adx":
            values[field] = rng.choice((20.0, 24.0, 28.0, 32.0, 36.0, 40.0, 45.0, 55.0, 100.0))
        elif field == "min_rvol":
            values[field] = rng.choice((0.0, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0))
        elif field == "min_atr_bps":
            values[field] = rng.choice((0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0))
        elif field == "max_atr_bps":
            values[field] = rng.choice((175.0, 200.0, 250.0, 300.0, 400.0, 600.0, 10_000.0))
        elif field == "min_dir_roc_bps":
            values[field] = rng.choice((-10_000.0, -300.0, -200.0, -100.0, -50.0, 0.0, 50.0, 100.0, 200.0, 300.0))
        elif field == "max_dist_ema_bps":
            values[field] = rng.choice((200.0, 300.0, 500.0, 750.0, 1_000.0, 1_500.0, 2_500.0, 10_000.0))
        elif field == "htf_mode":
            values[field] = rng.choice(("none", "h4", "h12", "d1"))
        elif field in {"require_macd_turn", "require_body_dir"}:
            values[field] = not getattr(seed, field)
        elif field == "max_aligned_funding_bps":
            values[field] = rng.choice((0.5, 1.0, 2.0, 4.0, 8.0, 10_000.0))
        elif field == "exit_kind":
            values[field] = rng.choice(("fixed", "trailing"))
        elif field == "tp_atr":
            values[field] = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0))
        elif field == "sl_atr":
            values[field] = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0))
        elif field == "trail_activation_atr":
            values[field] = rng.choice((0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0))
        elif field == "trail_atr":
            values[field] = rng.choice((0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0))
        elif field == "max_hold_bars":
            values[field] = rng.choice((4, 6, 8, 12, 18, 24, 36, 48, 72, 96, 120, 168, 240, 336))
        elif field == "cooldown_bars":
            values[field] = rng.choice((0, 3, 6, 12, 18, 24, 36, 48))
        elif field == "sizing_kind":
            values[field] = rng.choice(("fixed", "risk"))
        elif field == "fixed_leverage":
            values[field] = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0))
        elif field == "risk_fraction":
            values[field] = rng.choice((0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03, 0.04))
        elif field == "max_leverage":
            values[field] = rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0))
    cfg = replace(seed, **values)
    if cfg.max_adx <= cfg.min_adx:
        cfg = replace(cfg, max_adx=100.0)
    if cfg.max_atr_bps <= cfg.min_atr_bps:
        cfg = replace(cfg, max_atr_bps=10_000.0)
    return cfg


def config_key(cfg: base.StrategyConfig) -> tuple[Any, ...]:
    values = asdict(cfg)
    values.pop("name")
    return tuple(values.items())


def report(
    *,
    seed_count: int,
    generated: int,
    evaluated: int,
    eligible: int,
    prefit_hits: int,
    finalists: list[base.Candidate],
    best: base.Candidate,
    slices: list[dict[str, Any]],
) -> str:
    full = best.full or base.empty_metrics(1.0)
    holdout = best.holdout or base.empty_metrics(1.0)
    locked_hits = sum(item.target_pass for item in finalists)
    lines = [
        "# HYPE-1H-Adaptive-Regime Pareto 邻域精调 - 2026-07-01",
        "",
        "## 结论",
        "",
        (
            "第二轮出现 locked hard-gate 命中，但仍需稳健性与实盘审计。"
            if locked_hits
            else "第二轮仍没有出现 locked hard-gate 命中，结论保持 `NO-GO / not promoted`。"
        ),
        "",
        f"- 输入 seed：`{seed_count}`；生成 unique neighbors：`{generated}`；可交易评估：`{evaluated}`；prefit eligible：`{eligible}`。",
        f"- prefit hard-shape observations：`{prefit_hits}`；locked target pass：`{locked_hits}/{len(finalists)}`。",
        "- seed 与邻域排序只使用第一轮 prefit CSV 的 train/validation 字段；第二轮 finalists 冻结后才读取 locked holdout。",
        "",
        "## 最佳冻结结果",
        "",
        f"- id：`{best.name}`；style：`{best.styles}`。",
        f"- full：annual `{base.mult(full['annual_multiple'])}`，return `{base.pct(full['total_return'])}`，DD `{base.pct(full['max_dd'])}`，win `{base.pct(full['win_rate'])}`，trades `{int(full['trades'])}`。",
        f"- locked holdout：annual `{base.mult(holdout['annual_multiple'])}`，return `{base.pct(holdout['total_return'])}`，DD `{base.pct(holdout['max_dd'])}`，win `{base.pct(holdout['win_rate'])}`，trades `{int(holdout['trades'])}`。",
        f"- target pass：`{best.target_pass}`。",
        "",
        "## 时间切片",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{base.mult(row['annual_multiple'])}` | `{base.pct(row['total_return'])}` | `{base.pct(row['max_dd'])}` | `{base.pct(row['win_rate'])}` | `{int(row['trades'])}` | `{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 状态",
            "",
            (
                "`hard-gate hit / robustness pending / not promoted`。"
                if locked_hits
                else "`NO-GO / not promoted`；不得标记 candidate、paper-live、dry-run、handoff 或 live。"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    seeds, _source_rows = load_seeds()
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=base.WARMUP_DAYS)
    usable = full_end - train_start
    train_end = train_start + usable * 0.55
    validation_end = train_start + usable * 0.775

    rng = random.Random(args.seed)
    generated: list[base.StrategyConfig] = []
    seen: set[tuple[Any, ...]] = set()
    attempts = 0
    while len(generated) < args.neighbors and attempts < args.neighbors * 3:
        attempts += 1
        cfg = mutate(
            rng.choice(seeds), rng=rng, index=len(generated)
        )
        key = config_key(cfg)
        if key in seen:
            continue
        seen.add(key)
        generated.append(cfg)
    print(
        f"seeds={len(seeds)} neighbors={len(generated)} attempts={attempts}", flush=True
    )

    retained: list[tuple[base.Candidate, base.StrategyConfig]] = []
    evaluated = 0
    eligible = 0
    prefit_hits = 0
    for index, cfg in enumerate(generated, start=1):
        signal = base.build_signal(frame, cfg)
        if int((signal != 0).sum()) < 6:
            continue
        trades = base.simulate_trades(
            frame, signal, cfg, funding_times, funding_cumulative
        )
        candidate = base.candidate_from_config(
            cfg, trades, train_start, train_end, validation_end
        )
        evaluated += 1
        if candidate is None:
            continue
        eligible += 1
        prefit_hits += int(candidate.prefit_pass)
        retained = base.retain_candidate(
            retained, (candidate, cfg), args.prefit_keep
        )
        if index % args.progress_every == 0:
            current = max(
                retained, key=lambda item: base.candidate_sort_key(item[0])
            )[0]
            print(
                f"refine {index}/{len(generated)} evaluated={evaluated} eligible={eligible} "
                f"prefit_hits={prefit_hits} retained={len(retained)} "
                f"best={current.name} ann={current.prefit['annual_multiple']:.3f} "
                f"dd={current.prefit['max_dd']:.3f} score={current.prefit_score:.3f}",
                flush=True,
            )
    retained = sorted(
        retained, key=lambda item: base.candidate_sort_key(item[0]), reverse=True
    )[: args.prefit_keep]
    config_map = {cfg.name: cfg for _candidate, cfg in retained}
    pd.DataFrame(
        [base.candidate_row(candidate, config_map) for candidate, _cfg in retained]
    ).to_csv(PREFIT_CSV, index=False)

    ensembles = base.make_ensembles(
        retained,
        frame,
        funding_times,
        funding_cumulative,
        train_start,
        train_end,
        validation_end,
    )
    finalists: list[tuple[base.Candidate, list[base.Trade]]] = []
    for candidate, cfg in retained[: args.holdout_keep]:
        trades = base.simulate_trades(
            frame,
            base.build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        finalists.append(
            (
                base.finalize_candidate(
                    candidate, trades, train_start, validation_end, full_end
                ),
                trades,
            )
        )
    for candidate, _pair, trades in ensembles[: args.holdout_keep]:
        finalists.append(
            (
                base.finalize_candidate(
                    candidate, trades, train_start, validation_end, full_end
                ),
                trades,
            )
        )
    finalists.sort(key=lambda item: base.final_sort_key(item[0]), reverse=True)
    if not finalists:
        raise RuntimeError("No refinement finalist survived")
    best, best_trades = finalists[0]
    pd.DataFrame(
        [base.candidate_row(candidate, config_map) for candidate, _ in finalists]
    ).to_csv(RANKING_CSV, index=False)
    slices = base.diagnostic_slices(
        best_trades, train_start, train_end, validation_end, full_end
    )
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(base.trade_rows(best_trades)).to_csv(TRADES_CSV, index=False)
    summary = {
        "family": "HYPE-1H-Adaptive-Regime",
        "phase": "prefit_pareto_neighborhood_refine",
        "status": (
            "hard_gate_hit_pending_robustness_not_promoted"
            if any(candidate.target_pass for candidate, _ in finalists)
            else "no_go_not_promoted"
        ),
        "data_quality": quality,
        "seed_count": len(seeds),
        "generated_neighbors": len(generated),
        "evaluated": evaluated,
        "eligible": eligible,
        "prefit_hits": prefit_hits,
        "retained": len(retained),
        "ensembles": len(ensembles),
        "locked_finalists": len(finalists),
        "locked_hits": sum(candidate.target_pass for candidate, _ in finalists),
        "best": base.candidate_row(best, config_map),
        "best_slices": slices,
        "top_20": [
            base.candidate_row(candidate, config_map)
            for candidate, _trades in finalists[:20]
        ],
        "retained_configs": {cfg.name: asdict(cfg) for _candidate, cfg in retained},
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        report(
            seed_count=len(seeds),
            generated=len(generated),
            evaluated=evaluated,
            eligible=eligible,
            prefit_hits=prefit_hits,
            finalists=[candidate for candidate, _ in finalists],
            best=best,
            slices=slices,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            base.json_safe(
                {
                    "status": summary["status"],
                    "seed_count": len(seeds),
                    "generated": len(generated),
                    "evaluated": evaluated,
                    "eligible": eligible,
                    "prefit_hits": prefit_hits,
                    "locked_hits": summary["locked_hits"],
                    "best": summary["best"],
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

