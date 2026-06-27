from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
MICRO_SCRIPT_DIR = THIS_DIR.parent.parent / "5m-micro-scalp" / "scripts"
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(MICRO_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(MICRO_SCRIPT_DIR))

from research_hype_5m_micro_scalp_relaxed_rounds import (  # type: ignore[reportMissingImports]  # noqa: E402
    ROUNDS,
    SEED,
    config_key,
    random_targeted_config,
)
from research_hype_5m_micro_scalp_search import (  # type: ignore[reportMissingImports]  # noqa: E402
    ScalpConfig,
    add_features,
    build_signal,
    simulate_trades,
)
from research_hype_5m_seeded_event_quality_v0 import (  # noqa: E402
    ARTIFACT_ROOT,
    DIAGNOSTIC_ROOT,
    RUN_DATE,
    pct,
    serializable,
    simulate_seed_event,
    validate_and_load,
)


FAMILY = "HYPE-5M-Event-Quality-Scoring"
VERSION = "HYPE-5M-Event-Quality-Scoring-Seeded-V1"
MODE = "strict_seed_generation_audit"

CONFIGS_PER_ROUND = 2000
MAX_SEED_CONFIGS = 100
MIN_TRAIN_DAYS = 60
MIN_SEED_TRADES = 40
PURGE = pd.Timedelta(hours=12)
QUANTILE = 0.80
CFG_WEIGHT = 0.875
SIDE_WEIGHT = 0.125
ALLOWED_STYLES = ("bb_revert", "macd_flip", "trend_rsi_snapback", "vwap_revert")

REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_seeded_v1_strict_seed_audit_{RUN_DATE}.json"
SUMMARY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_v1_strict_seed_audit_summary_{RUN_DATE}.csv"
MONTHLY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_v1_strict_seed_audit_monthly_{RUN_DATE}.csv"
TRADES_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_v1_strict_seed_audit_trades_{RUN_DATE}.csv"
SEEDS_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_v1_strict_seed_audit_selected_seeds_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-seeded-v1-strict-seed-audit-{RUN_DATE}.md"


@dataclass(slots=True)
class StrictEvent:
    event_id: int
    segment: str
    signal_idx: int
    entry_idx: int
    exit_idx: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    cfg_name: str
    style: str
    tp_bps: float
    sl_bps: float
    max_hold_bars: int
    cooldown_bars: int
    net_ret_1x: float
    reason: str


def build_strict_config_universe() -> list[ScalpConfig]:
    rng = random.Random(SEED)
    configs: list[ScalpConfig] = []
    seen: set[tuple[Any, ...]] = set()
    for spec in ROUNDS:
        idx = 0
        round_count = 0
        while round_count < CONFIGS_PER_ROUND:
            idx += 1
            cfg = random_targeted_config(rng, spec, idx)
            if cfg.entry_style not in ALLOWED_STYLES:
                continue
            key = config_key(cfg)
            if key in seen:
                continue
            configs.append(cfg)
            seen.add(key)
            round_count += 1
    return configs


def segment_bounds(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    rows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    cursor = start
    while cursor < end:
        next_month = min(pd.Timestamp((cursor + pd.offsets.MonthBegin(1)).normalize()), end)
        if next_month <= cursor:
            next_month = min(cursor + pd.offsets.MonthBegin(1), end)
        rows.append((cursor.strftime("%Y_%m"), cursor, next_month))
        cursor = next_month
    return rows


def first_month_start_after(ts: pd.Timestamp) -> pd.Timestamp:
    month_start = ts.normalize().replace(day=1)
    if ts == month_start:
        return month_start
    return pd.Timestamp(month_start + pd.offsets.MonthBegin(1))


def max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[:-1]
    return float(min(0.0, (equity / peak - 1.0).min()))


def metrics(returns: np.ndarray, days: float) -> dict[str, Any]:
    if len(returns) == 0:
        return {
            "trades": 0,
            "days": float(days),
            "trades_per_day": 0.0,
            "total_return_1x": 0.0,
            "annualized_1x": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_bps": 0.0,
            "max_drawdown_1x": 0.0,
        }
    total_return = float(np.prod(1.0 + returns) - 1.0)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    return {
        "trades": int(len(returns)),
        "days": float(days),
        "trades_per_day": float(len(returns) / max(days, 1e-9)),
        "total_return_1x": total_return,
        "annualized_1x": float((1.0 + total_return) ** (365.0 / max(days, 1e-9)) - 1.0) if total_return > -1 else -1.0,
        "win_rate": float((returns > 0).mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else math.inf,
        "avg_trade_bps": float(returns.mean() * 10000.0),
        "max_drawdown_1x": max_drawdown(returns),
    }


def config_trade_frame(frame: pd.DataFrame, configs: list[ScalpConfig]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for idx, cfg in enumerate(configs, start=1):
        signal = build_signal(frame, cfg)
        trades, _ = simulate_trades(frame, signal, cfg)
        for trade in trades:
            rows.append(
                {
                    "cfg_name": cfg.name,
                    "entry_ts": trade.entry_ts,
                    "net_ret_1x": trade.net_ret_1x,
                }
            )
        if idx % 500 == 0:
            print(f"config_eval_progress={idx}/{len(configs)} trade_rows={len(rows)}", flush=True)
    result = pd.DataFrame(rows)
    if result.empty:
        raise RuntimeError("strict config universe generated no trades")
    result["entry_ts"] = pd.to_datetime(result["entry_ts"], utc=True)
    return result


def train_config_metrics(config_trades: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    train = config_trades[config_trades["entry_ts"] < cutoff]
    rows: list[dict[str, Any]] = []
    for cfg_name, group in train.groupby("cfg_name"):
        returns = group["net_ret_1x"].to_numpy("float64")
        row = {"cfg_name": cfg_name}
        row.update(metrics(returns, max((cutoff - group["entry_ts"].min()).total_seconds() / 86400.0, 1.0)))
        rows.append(row)
    return pd.DataFrame(rows)


def select_seed_configs(config_trades: pd.DataFrame, cfg_by_name: dict[str, ScalpConfig], cutoff: pd.Timestamp) -> tuple[list[ScalpConfig], pd.DataFrame]:
    scored = train_config_metrics(config_trades, cutoff)
    if scored.empty:
        return [], scored
    pool = scored[
        (scored["trades"] >= MIN_SEED_TRADES)
        & (scored["total_return_1x"] > 0.0)
        & (scored["profit_factor"] >= 1.15)
        & (scored["max_drawdown_1x"] >= -0.25)
    ].copy()
    if pool.empty:
        return [], scored
    pool = pool.sort_values(["total_return_1x", "profit_factor"], ascending=[False, False]).head(MAX_SEED_CONFIGS)
    seeds = [cfg_by_name[str(name)] for name in pool["cfg_name"] if str(name) in cfg_by_name]
    return seeds, pool


def build_events_for_configs(
    frame: pd.DataFrame,
    configs: list[ScalpConfig],
    segment: str,
    signal_start: pd.Timestamp | None,
    signal_end: pd.Timestamp,
    event_id_start: int,
) -> pd.DataFrame:
    ts = frame["ts"]
    rows: list[StrictEvent] = []
    for cfg in configs:
        signal = build_signal(frame, cfg)
        signal_indices = np.flatnonzero(signal)
        if signal_start is not None:
            mask = (ts.iloc[signal_indices].to_numpy() >= signal_start) & (ts.iloc[signal_indices].to_numpy() < signal_end)
        else:
            mask = ts.iloc[signal_indices].to_numpy() < signal_end
        for signal_idx in signal_indices[mask]:
            side = int(signal[signal_idx])
            outcome = simulate_seed_event(frame, int(signal_idx), side, cfg)
            if outcome is None:
                continue
            rows.append(
                StrictEvent(
                    event_id=event_id_start + len(rows),
                    segment=segment,
                    signal_idx=int(signal_idx),
                    entry_idx=int(outcome["entry_idx"]),
                    exit_idx=int(outcome["exit_idx"]),
                    signal_ts=outcome["signal_ts"],
                    entry_ts=outcome["entry_ts"],
                    exit_ts=outcome["exit_ts"],
                    side=side,
                    cfg_name=cfg.name,
                    style=cfg.entry_style,
                    tp_bps=float(cfg.tp_bps),
                    sl_bps=float(cfg.sl_bps),
                    max_hold_bars=int(cfg.max_hold_bars),
                    cooldown_bars=int(cfg.cooldown_bars),
                    net_ret_1x=float(outcome["net_ret_1x"]),
                    reason=str(outcome["reason"]),
                )
            )
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame([asdict(row) for row in rows])
    result["signal_ts"] = pd.to_datetime(result["signal_ts"], utc=True)
    result["entry_ts"] = pd.to_datetime(result["entry_ts"], utc=True)
    result["exit_ts"] = pd.to_datetime(result["exit_ts"], utc=True)
    return result.sort_values(["signal_idx", "cfg_name"]).reset_index(drop=True)


def score_and_replay(train_events: pd.DataFrame, test_events: pd.DataFrame, candidate_id: str) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    if train_events.empty or test_events.empty or len(train_events) < 50:
        return [], pd.DataFrame()
    cfg_mean = train_events.groupby("cfg_name")["net_ret_1x"].mean()
    side_mean = train_events.groupby("side")["net_ret_1x"].mean()
    global_mean = float(train_events["net_ret_1x"].mean())
    scored = test_events.copy()
    scored["score"] = (
        CFG_WEIGHT * scored["cfg_name"].map(cfg_mean).fillna(global_mean)
        + SIDE_WEIGHT * scored["side"].map(side_mean).fillna(global_mean)
    )
    train_score = (
        CFG_WEIGHT * train_events["cfg_name"].map(cfg_mean).fillna(global_mean)
        + SIDE_WEIGHT * train_events["side"].map(side_mean).fillna(global_mean)
    )
    scored["threshold_q80"] = float(np.quantile(train_score, QUANTILE))
    selected = scored[scored["score"] >= scored["threshold_q80"]].copy()
    selected = selected.sort_values(["signal_idx", "score"], ascending=[True, False])
    selected = selected.drop_duplicates("signal_idx", keep="first").sort_values("signal_idx")

    trades: list[dict[str, Any]] = []
    blocked_until = -1
    for row in selected.itertuples(index=False):
        if int(row.entry_idx) <= blocked_until:
            continue
        trades.append(
            {
                "candidate_id": candidate_id,
                "segment": str(row.segment),
                "event_id": int(row.event_id),
                "signal_ts": pd.Timestamp(row.signal_ts),
                "entry_ts": pd.Timestamp(row.entry_ts),
                "exit_ts": pd.Timestamp(row.exit_ts),
                "side": int(row.side),
                "cfg_name": str(row.cfg_name),
                "style": str(row.style),
                "score": float(row.score),
                "reason": str(row.reason),
                "bars_held": int(row.exit_idx - row.entry_idx + 1),
                "net_ret_1x": float(row.net_ret_1x),
            }
        )
        blocked_until = int(row.exit_idx) + int(row.cooldown_bars)
    return trades, selected


def monthly_metrics(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for segment, seg_start, seg_end in segment_bounds(start, end):
        sub = trades[(trades["entry_ts"] >= seg_start) & (trades["entry_ts"] < seg_end)] if not trades.empty else pd.DataFrame()
        returns = sub["net_ret_1x"].to_numpy("float64") if not sub.empty else np.array([], dtype="float64")
        row = {"month": segment, "start": seg_start, "end": seg_end}
        row.update(metrics(returns, (seg_end - seg_start).total_seconds() / 86400.0))
        rows.append(row)
    return pd.DataFrame(rows)


def render_markdown(
    quality: dict[str, Any],
    summary: dict[str, Any],
    monthly: pd.DataFrame,
    seed_rows: pd.DataFrame,
    config_count: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> str:
    lines = [
        "# HYPE-5M-Event-Quality-Scoring Seeded V1 Strict Seed Audit",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
        f"- 配置宇宙：使用 relaxed-rounds 的固定随机生成器，禁用 previous-summary seeds；每轮 `{CONFIGS_PER_ROUND}` 个、共 `{config_count}` 个无数据配置。",
        f"- 严格 OOS 窗口：`{start}` 到 `{end}`；因数据从 `{quality['start_ts']}` 开始，先保留 `{MIN_TRAIN_DAYS}` 天最小训练期。",
        f"- 每个测试月只使用该月之前的数据筛 seed，再生成该月事件并用 `cfg_side_88_12 + q80` 交易。",
        f"- 严格 seed 审计结果：`{int(summary['trades'])}` 笔，收益 `{pct(float(summary['total_return_1x']))}`，PF `{float(summary['profit_factor']):.3f}`，单笔 `{float(summary['avg_trade_bps']):.2f} bps`，最大回撤 `{pct(float(summary['max_drawdown_1x']))}`。",
        "",
    ]
    if summary["trades"] == 0 or summary["total_return_1x"] <= 0:
        lines.append("结论：严格 seed 审计没有支持 V1 当前表现，V1 的固定 seed-universe 结果很可能包含显著 config-universe selection bias。")
    else:
        lines.append("结论：严格 seed 审计仍为正，但需要与固定 seed-universe V1 对比折损幅度；若收益/PF/回撤明显恶化，V1 仍不能进入 paper-live。")
    lines.extend(
        [
            "",
            "## 数据质量",
            "",
            f"- 数据范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
            f"- 行数：`{quality['rows']}`，缺口：`{quality['missing_bars']}`。",
            f"- raw/normalized 对齐：`{quality['raw_alignment']['same_ts_sequence']}`。",
            "",
            "## Monthly",
            "",
            "| month | selected seeds | trades | ret | PF | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    seed_count_by_month = seed_rows.groupby("segment")["cfg_name"].nunique().to_dict() if not seed_rows.empty else {}
    for _, row in monthly.iterrows():
        seed_count = int(seed_count_by_month.get(row["month"], 0))
        pf = "inf" if not np.isfinite(float(row["profit_factor"])) else f"{float(row['profit_factor']):.3f}"
        lines.append(
            f"| `{row['month']}` | {seed_count} | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{pf} | {float(row['avg_trade_bps']):.2f} | {pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## 与固定 seed-universe V1 的差异",
            "",
            "- 固定 seed-universe V1：`549` 笔，`287.61%` 收益，`1.425` PF，`26.33 bps` 单笔，`-16.30%` 最大回撤。",
            "- 本报告禁用了历史 summary seed，并每月滚动重新筛 seed。若表现显著下降，应视为 V1 live promotion blocker，而不是参数搜索问题。",
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_JSON}`",
            f"- Summary：`{SUMMARY_CSV}`",
            f"- Monthly：`{MONTHLY_CSV}`",
            f"- Trades：`{TRADES_CSV}`",
            f"- Selected seeds：`{SEEDS_CSV}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    raw_frame, quality = validate_and_load()
    frame = add_features(raw_frame)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)

    configs = build_strict_config_universe()
    cfg_by_name = {cfg.name: cfg for cfg in configs}
    print(f"strict_config_count={len(configs)}", flush=True)
    config_trades = config_trade_frame(frame, configs)

    data_start = pd.Timestamp(quality["start_ts"])
    data_end = pd.Timestamp(quality["end_ts"]) + pd.Timedelta(minutes=5)
    strict_start = first_month_start_after(data_start + pd.Timedelta(days=MIN_TRAIN_DAYS))
    strict_end = data_end

    all_trades: list[dict[str, Any]] = []
    selected_seed_rows: list[dict[str, Any]] = []
    event_id = 0
    for segment, test_start, test_end in segment_bounds(strict_start, strict_end):
        cutoff = test_start - PURGE
        seeds, seed_pool = select_seed_configs(config_trades, cfg_by_name, cutoff)
        if seed_pool.empty or not seeds:
            print(f"segment={segment} seeds=0 trades=0", flush=True)
            continue
        for rank, row in enumerate(seed_pool.itertuples(index=False), start=1):
            selected_seed_rows.append({"segment": segment, "rank": rank, **row._asdict()})
        train_events = build_events_for_configs(frame, seeds, segment, None, cutoff, event_id)
        event_id += len(train_events)
        test_events = build_events_for_configs(frame, seeds, segment, test_start, test_end, event_id)
        event_id += len(test_events)
        trades, _selected = score_and_replay(train_events, test_events, "strict_seed_v1")
        all_trades.extend(trades)
        print(
            f"segment={segment} seeds={len(seeds)} train_events={len(train_events)} "
            f"test_events={len(test_events)} trades={len(trades)}",
            flush=True,
        )

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        trades_df["entry_ts"] = pd.to_datetime(trades_df["entry_ts"], utc=True)
        trades_df["exit_ts"] = pd.to_datetime(trades_df["exit_ts"], utc=True)
    seed_df = pd.DataFrame(selected_seed_rows)
    monthly = monthly_metrics(trades_df, strict_start, strict_end)
    returns = trades_df["net_ret_1x"].to_numpy("float64") if not trades_df.empty else np.array([], dtype="float64")
    summary = {
        "version": VERSION,
        "mode": MODE,
        "strict_config_count": len(configs),
        "configs_per_round": CONFIGS_PER_ROUND,
        "strict_start": strict_start,
        "strict_end": strict_end,
        "min_train_days": MIN_TRAIN_DAYS,
        "max_seed_configs": MAX_SEED_CONFIGS,
        "min_seed_trades": MIN_SEED_TRADES,
        "score": f"{CFG_WEIGHT} cfg_mean + {SIDE_WEIGHT} side_mean",
        "quantile": QUANTILE,
        **metrics(returns, (strict_end - strict_start).total_seconds() / 86400.0),
    }

    pd.DataFrame([summary]).to_csv(SUMMARY_CSV, index=False)
    monthly.to_csv(MONTHLY_CSV, index=False)
    trades_df.to_csv(TRADES_CSV, index=False)
    seed_df.to_csv(SEEDS_CSV, index=False)
    report = {
        "run_date": RUN_DATE,
        "family": FAMILY,
        "version": VERSION,
        "mode": MODE,
        "quality": quality,
        "summary": summary,
        "monthly": monthly.to_dict(orient="records"),
        "artifact_paths": {
            "markdown": str(MARKDOWN_PATH),
            "json": str(REPORT_JSON),
            "summary": str(SUMMARY_CSV),
            "monthly": str(MONTHLY_CSV),
            "trades": str(TRADES_CSV),
            "selected_seeds": str(SEEDS_CSV),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(quality, summary, monthly, seed_df, len(configs), strict_start, strict_end), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=serializable), flush=True)


if __name__ == "__main__":
    main()
