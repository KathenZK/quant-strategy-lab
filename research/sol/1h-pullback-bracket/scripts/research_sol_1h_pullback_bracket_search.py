from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/1h-pullback-bracket"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
VCB_SEARCH_PATH = (
    ROOT
    / "research/sol/1h-volatility-compression-breakout/scripts"
    / "research_sol_1h_vcb_search.py"
)

DATE_TAG = "2026-07-13"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_pullback_bracket_search_{DATE_TAG}.json"
RANKING_CSV = ARTIFACT_DIR / f"sol_1h_pullback_bracket_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"sol_1h_pullback_bracket_slices_{DATE_TAG}.csv"
TRADES_CSV = (
    ARTIFACT_DIR / f"sol_1h_pullback_bracket_selected_trades_{DATE_TAG}.csv"
)
REPORT_MD = (
    DIAGNOSTIC_DIR / f"sol-1h-pullback-bracket-search-{DATE_TAG}.md"
)


@dataclass(frozen=True, slots=True)
class EntryConfig:
    ema_fast: int
    ema_slow: int
    trend_persist_bars: int
    max_pullback_atr: float
    confirm_window: int
    min_adx: float
    min_rvol: float
    rsi_confirm: float
    side_mode: str
    max_aligned_funding_bps: float


@dataclass(slots=True)
class Candidate:
    name: str
    entry: EntryConfig
    exit_config: Any
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]
    signal_count: int
    event_count: int
    hard_pass: bool


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def random_entry(rng: random.Random) -> EntryConfig:
    fast, slow = rng.choice(((21, 55), (34, 89), (55, 144)))
    return EntryConfig(
        ema_fast=fast,
        ema_slow=slow,
        trend_persist_bars=rng.choice((6, 12, 24, 48)),
        max_pullback_atr=rng.choice((0.5, 1.0, 1.5, 2.0)),
        confirm_window=rng.choice((1, 3, 6)),
        min_adx=rng.choice((0.0, 16.0, 24.0)),
        min_rvol=rng.choice((0.5, 1.0, 1.5)),
        rsi_confirm=rng.choice((45.0, 50.0, 55.0)),
        side_mode=rng.choice(("both", "long", "short")),
        max_aligned_funding_bps=rng.choice((1.0, 2.0, 10_000.0)),
    )


def random_exit(engine: Any, rng: random.Random, template: Any, index: int) -> Any:
    sizing_kind = rng.choices(("risk", "fixed"), weights=(0.75, 0.25), k=1)[0]
    return replace(
        template,
        name=f"SOL_1H_PB_R{index:05d}",
        style="pullback_recovery_bracket",
        side_mode="both",
        exit_kind="fixed",
        tp_atr=rng.choice((1.5, 2.0, 3.0, 4.0)),
        sl_atr=rng.choice((1.0, 1.5, 2.0)),
        max_hold_bars=rng.choice((12, 24, 48)),
        cooldown_bars=rng.choice((0, 6, 12, 24)),
        entry_delay_bars=1,
        sizing_kind=sizing_kind,
        fixed_leverage=rng.choice((1.0, 1.5, 2.0)),
        risk_fraction=rng.choice((0.003, 0.005, 0.0075, 0.01)),
        max_leverage=rng.choice((1.0, 1.5, 2.0, 3.0)),
    )


def persistent(mask: np.ndarray, bars: int) -> np.ndarray:
    return (
        pd.Series(mask.astype("int8")).rolling(bars).sum().to_numpy() >= bars
    )


def build_signal(
    frame: pd.DataFrame, cfg: EntryConfig
) -> tuple[np.ndarray, int]:
    close = frame["close"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    adx = frame["adx14"].to_numpy("float64")
    rvol = frame["rvol48"].to_numpy("float64")
    rsi = frame["rsi14"].to_numpy("float64")
    body = frame["body_atr"].to_numpy("float64")
    funding = frame["last_funding_rate"].to_numpy("float64") * 10_000.0
    long_trend = persistent(fast > slow, cfg.trend_persist_bars)
    short_trend = persistent(fast < slow, cfg.trend_persist_bars)
    signal = np.zeros(len(frame), dtype=np.int8)
    active_side = 0
    expires_at = -1
    event_count = 0

    for bar_i in range(1, len(frame)):
        long_depth = (
            (fast[bar_i] - low[bar_i]) / atr[bar_i]
            if np.isfinite(atr[bar_i]) and atr[bar_i] > 0.0
            else math.inf
        )
        short_depth = (
            (high[bar_i] - fast[bar_i]) / atr[bar_i]
            if np.isfinite(atr[bar_i]) and atr[bar_i] > 0.0
            else math.inf
        )
        long_arm = (
            cfg.side_mode in {"long", "both"}
            and long_trend[bar_i]
            and low[bar_i] <= fast[bar_i]
            and close[bar_i] > slow[bar_i]
            and 0.0 <= long_depth <= cfg.max_pullback_atr
        )
        short_arm = (
            cfg.side_mode in {"short", "both"}
            and short_trend[bar_i]
            and high[bar_i] >= fast[bar_i]
            and close[bar_i] < slow[bar_i]
            and 0.0 <= short_depth <= cfg.max_pullback_atr
        )
        if long_arm or short_arm:
            active_side = 1 if long_arm else -1
            expires_at = bar_i + cfg.confirm_window
            event_count += 1
            continue
        if active_side == 0:
            continue
        if bar_i > expires_at:
            active_side = 0
            continue
        if not (
            np.isfinite(adx[bar_i])
            and np.isfinite(rvol[bar_i])
            and adx[bar_i] >= cfg.min_adx
            and rvol[bar_i] >= cfg.min_rvol
        ):
            continue
        if active_side > 0:
            confirmed = (
                long_trend[bar_i]
                and close[bar_i] > fast[bar_i]
                and close[bar_i] > high[bar_i - 1]
                and body[bar_i] > 0.0
                and rsi[bar_i] >= cfg.rsi_confirm
            )
        else:
            confirmed = (
                short_trend[bar_i]
                and close[bar_i] < fast[bar_i]
                and close[bar_i] < low[bar_i - 1]
                and body[bar_i] < 0.0
                and rsi[bar_i] <= 100.0 - cfg.rsi_confirm
            )
        if not confirmed:
            continue
        if active_side * funding[bar_i] > cfg.max_aligned_funding_bps:
            continue
        signal[bar_i] = active_side
        active_side = 0
    return signal, event_count


def candidate_row(vcb: Any, candidate: Candidate) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": candidate.name,
        "score": candidate.score,
        "signal_count": candidate.signal_count,
        "event_count": candidate.event_count,
        "hard_pass": candidate.hard_pass,
        **{f"entry_{key}": value for key, value in asdict(candidate.entry).items()},
        **{
            f"exit_{key}": value
            for key, value in asdict(candidate.exit_config).items()
        },
        **{
            f"tail_{key}": value
            for key, value in vcb.tail_metrics(candidate.trades).items()
        },
    }
    for window, values in candidate.metrics.items():
        row.update({f"{window}_{key}": value for key, value in values.items()})
    return row


def main() -> None:
    rng = random.Random(20260713)
    vcb = load_module(VCB_SEARCH_PATH, "sol_1h_pullback_vcb")
    engine = vcb.load_engine()
    frame, funding, quality = vcb.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    template = engine.curated_configs()[0]

    candidates: list[Candidate] = []
    evaluated = 0
    eligible = 0
    hard_passes = 0
    for index in range(1, 1501):
        entry = random_entry(rng)
        exit_cfg = random_exit(engine, rng, template, index)
        signal, event_count = build_signal(frame, entry)
        signal_count = int(np.count_nonzero(signal))
        if signal_count < 20:
            continue
        evaluated += 1
        trades = engine.simulate_trades(
            frame,
            signal,
            exit_cfg,
            funding_times,
            funding_cumulative,
        )
        score, metrics, hard_pass = vcb.score_candidate(engine, trades)
        if score <= -1e8:
            continue
        eligible += 1
        hard_passes += int(hard_pass)
        candidates.append(
            Candidate(
                exit_cfg.name,
                entry,
                exit_cfg,
                trades,
                score,
                metrics,
                signal_count,
                event_count,
                hard_pass,
            )
        )
    candidates.sort(
        key=lambda item: (item.hard_pass, item.score), reverse=True
    )
    if not candidates:
        raise RuntimeError("No SOL 1h pullback candidate survived prefit gates")
    selected = candidates[0]
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [candidate_row(vcb, item) for item in candidates]
    ).to_csv(RANKING_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected.trades)).to_csv(TRADES_CSV, index=False)
    slices = [
        {
            "window": name,
            **engine.metrics(
                selected.trades, vcb.FULL_END - delta, vcb.FULL_END
            ),
        }
        for name, delta in vcb.STANDARD_SLICES
    ]
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    scenarios: list[dict[str, Any]] = []
    original_slippage = engine.SLIPPAGE_PER_FILL
    signal = build_signal(frame, selected.entry)[0]
    for name, delay, slippage in (
        ("base_k1_4bps", 1, 0.0004),
        ("delay_k2_4bps", 2, 0.0004),
        ("base_k1_8bps", 1, 0.0008),
    ):
        engine.SLIPPAGE_PER_FILL = slippage
        cfg = replace(selected.exit_config, entry_delay_bars=delay)
        trades = engine.simulate_trades(
            frame,
            signal,
            cfg,
            funding_times,
            funding_cumulative,
        )
        scenarios.append(
            {"scenario": name, "metrics": vcb.window_metrics(engine, trades)}
        )
    engine.SLIPPAGE_PER_FILL = original_slippage

    payload = {
        "family": "SOL-1H-Pullback-Bracket",
        "family_id": "SOL-1H-PB",
        "status": "explore_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_freeze_not_used_for_selection",
            "fresh_forward": "2026-07-03_to_2026-07-13_observation_only",
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": original_slippage,
            "funding": "actual_binance_history_per_trade",
        },
        "data_quality": quality,
        "counts": {
            "generated": 1500,
            "evaluated": evaluated,
            "eligible": eligible,
            "prefit_hard_pass": hard_passes,
        },
        "selected": candidate_row(vcb, selected),
        "top_20": [candidate_row(vcb, item) for item in candidates[:20]],
        "slices": slices,
        "scenarios": scenarios,
    }
    SUMMARY_JSON.write_text(
        json.dumps(vcb.json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metrics = selected.metrics
    tails = vcb.tail_metrics(selected.trades)
    lines = [
        "# SOL-1H-Pullback-Bracket 首轮搜索 - 2026-07-13",
        "",
        "## 结论",
        "",
        (
            "至少一个 prefit candidate 命中 `10x / 80% / <20% DD`，但 fresh forward 太短，仍不得 promotion。"
            if hard_passes
            else "没有 prefit candidate 命中 `10x / 80% / <20% DD`；本轮状态为 `explore / not promoted / not live-ready`。"
        ),
        "",
        f"- generated `1500`；evaluated `{evaluated}`；eligible `{eligible}`；prefit hard pass `{hard_passes}`。",
        "- 机制：EMA 趋势持续 → 回踩 arm → 恢复并突破前 K 确认 → 下一根 open + 即时 ATR bracket。",
        "",
        "## Prefit-only 选中观察",
        "",
        f"- id：`{selected.name}`；signals `{selected.signal_count}`；events `{selected.event_count}`；score `{selected.score:.3f}`。",
        f"- train：annual `{vcb.mult(metrics['train']['annual_multiple'])}`，DD `{vcb.pct(metrics['train']['max_dd'])}`，win `{vcb.pct(metrics['train']['win_rate'])}`，trades `{int(metrics['train']['trades'])}`。",
        f"- validation：annual `{vcb.mult(metrics['validation']['annual_multiple'])}`，DD `{vcb.pct(metrics['validation']['max_dd'])}`，win `{vcb.pct(metrics['validation']['win_rate'])}`，trades `{int(metrics['validation']['trades'])}`。",
        f"- prefit：annual `{vcb.mult(metrics['prefit']['annual_multiple'])}`，DD `{vcb.pct(metrics['prefit']['max_dd'])}`，win `{vcb.pct(metrics['prefit']['win_rate'])}`，trades `{int(metrics['prefit']['trades'])}`。",
        f"- reused holdout：annual `{vcb.mult(metrics['reused_holdout']['annual_multiple'])}`，return `{vcb.pct(metrics['reused_holdout']['total_return'])}`，DD `{vcb.pct(metrics['reused_holdout']['max_dd'])}`，trades `{int(metrics['reused_holdout']['trades'])}`。",
        f"- fresh forward：return `{vcb.pct(metrics['fresh_forward']['total_return'])}`，DD `{vcb.pct(metrics['fresh_forward']['max_dd'])}`，trades `{int(metrics['fresh_forward']['trades'])}`。",
        f"- full：annual `{vcb.mult(metrics['current_full']['annual_multiple'])}`，DD `{vcb.pct(metrics['current_full']['max_dd'])}`，win `{vcb.pct(metrics['current_full']['win_rate'])}`，trades `{int(metrics['current_full']['trades'])}`。",
        f"- prefit payoff `{tails['payoff']:.3f}`，avg win `{vcb.pct(tails['avg_win'])}`，avg loss `{vcb.pct(tails['avg_loss'])}`。",
        "",
        "## 标准近期分片（仅审计）",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{vcb.mult(row['annual_multiple'])}` | "
            f"`{vcb.pct(row['total_return'])}` | `{vcb.pct(row['max_dd'])}` | "
            f"`{vcb.pct(row['win_rate'])}` | `{int(row['trades'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 延迟与成本压力",
            "",
            "| Scenario | Prefit ann | Prefit DD | Holdout ann | Fresh return | Full ann | Full DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for scenario in scenarios:
        item = scenario["metrics"]
        lines.append(
            f"| `{scenario['scenario']}` | "
            f"`{vcb.mult(item['prefit']['annual_multiple'])}` | "
            f"`{vcb.pct(item['prefit']['max_dd'])}` | "
            f"`{vcb.mult(item['reused_holdout']['annual_multiple'])}` | "
            f"`{vcb.pct(item['fresh_forward']['total_return'])}` | "
            f"`{vcb.mult(item['current_full']['annual_multiple'])}` | "
            f"`{vcb.pct(item['current_full']['max_dd'])}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- reused holdout 不参与选择；fresh forward 仅约 10 天。",
            "- 首轮不登记版本，不进入 dry-run/live。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{RANKING_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-pullback-bracket/scripts/research_sol_1h_pullback_bracket_search.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"selected={selected.name} score={selected.score:.3f} "
        f"prefit_ann={metrics['prefit']['annual_multiple']:.4f} "
        f"holdout_ann={metrics['reused_holdout']['annual_multiple']:.4f} "
        f"fresh_return={metrics['fresh_forward']['total_return']:.4f} "
        f"full_ann={metrics['current_full']['annual_multiple']:.4f}",
        flush=True,
    )
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
