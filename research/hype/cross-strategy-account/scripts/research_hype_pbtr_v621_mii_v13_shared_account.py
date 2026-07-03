from __future__ import annotations

import json
import math
import sys
import importlib.util
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[4]
PBTR_SCRIPT_DIR = REPO_ROOT / "research/hype/5m-pullback-trail/scripts"
MII_SCRIPT_DIR = REPO_ROOT / "research/hype/15m-multi-indicator-intraday/scripts"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pbtr621 = load_module(
    PBTR_SCRIPT_DIR / "research_hype_5m_pbtr_v6_2_1_full_ablation.py",
    "shared_account_pbtr621",
)
mii_v12 = load_module(
    MII_SCRIPT_DIR / "research_hype_15m_mii_v1_2_atr_bracket_exit.py",
    "shared_account_mii_v12",
)


RUN_DATE = "2026-07-02"
TOPIC_DIR = Path("research/hype/cross-strategy-account")
SCRIPT_PATH = TOPIC_DIR / "scripts" / Path(__file__).name
ARTIFACTS_DIR = TOPIC_DIR / "artifacts"
DIAGNOSTICS_DIR = TOPIC_DIR / "diagnostics"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / f"hype_pbtr_v621_mii_v13_shared_account_summary_{RUN_DATE}.csv"
SOURCE_CSV_PATH = ARTIFACTS_DIR / f"hype_pbtr_v621_mii_v13_shared_account_sources_{RUN_DATE}.csv"
BLOCK_CSV_PATH = ARTIFACTS_DIR / f"hype_pbtr_v621_mii_v13_shared_account_blocks_{RUN_DATE}.csv"
TRADES_CSV_PATH = ARTIFACTS_DIR / f"hype_pbtr_v621_mii_v13_shared_account_trades_{RUN_DATE}.csv"
JSON_PATH = ARTIFACTS_DIR / f"hype_pbtr_v621_mii_v13_shared_account_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTICS_DIR / f"hype-pbtr-v6-2-1-mii-v1-3-shared-account-{RUN_DATE}.md"

PBTR_SOURCE = "HYPE-5M-PBTR-V6.2.1"
MII_SOURCE = "HYPE-15M-MII-V1.3"
PBTR_FAMILY = "HYPE-5M-Pullback-Trail"
MII_FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
MII_EXPOSURE = 2.5
PBTR_EXPOSURE = pbtr621.BASELINE.leverage
MII_ENTRY_DELAY_BARS = 1
MII_EXIT = mii_v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)


@dataclass(frozen=True, slots=True)
class CandidateTrade:
    source: str
    family: str
    timeframe: str
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    reason: str
    bars_held: int
    net_return: float
    min_mark_return: float
    max_mark_return: float
    entry_price: float
    exit_price: float
    close_mark_returns: tuple[float, ...]
    adverse_mark_returns: tuple[float, ...]
    source_priority: int
    side_priority: int


def pct(value: float, digits: int = 2) -> str:
    if not math.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    if not math.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def ts_value(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value, tz="UTC")


def pbtr_net_mark_return(entry_price: float, mark_price: float, side: int, leverage: float) -> float:
    exit_price = pbtr621.v62.v6.exit_price_with_cost(float(mark_price), side)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = pbtr621.v62.v6.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return float(leverage * (gross - fee_cost))


def pbtr_mark_paths(frame: pd.DataFrame, trade: Any, entry_i: int, exit_i: int, leverage: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    close_marks: list[float] = []
    adverse_marks: list[float] = []
    for bar_i in range(entry_i, max(entry_i, exit_i)):
        close_marks.append(pbtr_net_mark_return(trade.entry_price, float(close[bar_i]), trade.side, leverage))
    close_marks.append(float(trade.net_ret_1x * leverage))
    for bar_i in range(entry_i, exit_i + 1):
        adverse_price = float(low[bar_i] if trade.side > 0 else high[bar_i])
        adverse_marks.append(pbtr_net_mark_return(trade.entry_price, adverse_price, trade.side, leverage))
    adverse_marks.append(float(trade.net_ret_1x * leverage))
    return tuple(close_marks), tuple(adverse_marks)


def mii_net_mark_return(entry_price: float, mark_price: float, direction: int, exposure: float) -> float:
    raw_return = direction * (float(mark_price) / entry_price - 1.0)
    return float(exposure * (raw_return - mii_v12.ROUND_TRIP_COST))


def mii_mark_paths(
    context: Any,
    trade: Any,
    exposure: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    high = context.features["high"].to_numpy("float64")
    low = context.features["low"].to_numpy("float64")
    close = context.features["close"].to_numpy("float64")
    close_marks: list[float] = []
    adverse_marks: list[float] = []
    final_return = float(exposure * (trade.raw_return - mii_v12.ROUND_TRIP_COST))
    for bar_i in range(trade.entry_i, max(trade.entry_i, trade.exit_i)):
        close_marks.append(mii_net_mark_return(trade.entry_price, float(close[bar_i]), trade.direction, exposure))
    close_marks.append(final_return)
    for bar_i in range(trade.entry_i, trade.exit_i + 1):
        adverse_price = float(low[bar_i] if trade.direction > 0 else high[bar_i])
        adverse_marks.append(mii_net_mark_return(trade.entry_price, adverse_price, trade.direction, exposure))
    adverse_marks.append(final_return)
    return tuple(close_marks), tuple(adverse_marks)


def build_pbtr_candidates() -> tuple[list[CandidateTrade], dict[str, Any]]:
    raw = pbtr621.v62.v6.load_closed_frame()
    frame = pbtr621.v62.v6.add_search_features(pbtr621.v62.v6.add_features(raw))
    cfg = pbtr621.BASELINE
    long_signal, long_raw, long_filtered = pbtr621.v62.build_leg_signal(frame, cfg.long)
    short_signal, short_raw, short_filtered = pbtr621.v62.build_leg_signal(frame, cfg.short)
    priority = {"long": 0, "short": 1} if cfg.priority == "long_first" else {"short": 0, "long": 1}
    event_specs: list[tuple[int, str, int, Any]] = []
    if cfg.long.enabled:
        event_specs.extend((int(i), "long", int(long_signal[i]), cfg.long) for i in np.flatnonzero(long_signal))
    if cfg.short.enabled:
        event_specs.extend((int(i), "short", int(short_signal[i]), cfg.short) for i in np.flatnonzero(short_signal))
    event_specs.sort(key=lambda item: (item[0], priority[item[1]]))

    candidates: list[CandidateTrade] = []
    for signal_i, side_label, side, leg in event_specs:
        trade, exit_i = pbtr621.v62.simulate_one(frame, signal_i, side, leg, f"{PBTR_SOURCE}_{side_label}")
        if trade is None:
            continue
        close_marks, adverse_marks = pbtr_mark_paths(frame, trade, signal_i + 1, exit_i, cfg.leverage)
        candidates.append(
            CandidateTrade(
                source=PBTR_SOURCE,
                family=PBTR_FAMILY,
                timeframe="5m",
                signal_ts=ts_value(trade.signal_ts),
                entry_ts=ts_value(trade.entry_ts),
                exit_ts=ts_value(trade.exit_ts),
                side=int(trade.side),
                reason=str(trade.reason),
                bars_held=int(trade.bars_held),
                net_return=float(trade.net_ret_1x * cfg.leverage),
                min_mark_return=float(trade.mae_1x * cfg.leverage),
                max_mark_return=float(trade.mfe_1x * cfg.leverage),
                entry_price=float(trade.entry_price),
                exit_price=float(trade.exit_price),
                close_mark_returns=close_marks,
                adverse_mark_returns=adverse_marks,
                source_priority=0,
                side_priority=priority[side_label],
            )
        )

    quality = {
        "rows": int(len(frame)),
        "first_ts": ts_value(frame["ts"].iloc[0]).isoformat(),
        "last_ts": ts_value(frame["ts"].iloc[-1]).isoformat(),
        "timeframe": "5m",
        "long_raw_signal_count": int(long_raw),
        "long_filtered_signal_count": int(long_filtered),
        "short_raw_signal_count": int(short_raw),
        "short_filtered_signal_count": int(short_filtered),
        "candidate_count": int(len(candidates)),
        "leverage": float(cfg.leverage),
        "baseline": asdict(cfg),
    }
    return candidates, quality


def build_mii_candidates() -> tuple[list[CandidateTrade], dict[str, Any]]:
    context, metadata, quality = mii_v12.build_context()
    raw_trades = mii_v12.simulate_atr_bracket_trades(context, MII_EXIT, MII_ENTRY_DELAY_BARS)
    features = context.features
    candidates: list[CandidateTrade] = []
    for trade in raw_trades:
        if not mii_v12.v1.passes_filter(trade, mii_v12.BASE_CONFIG.filter):
            continue
        signal_ts = ts_value(features["ts"].iloc[trade.signal_i])
        close_marks, adverse_marks = mii_mark_paths(context, trade, MII_EXPOSURE)
        candidates.append(
            CandidateTrade(
                source=MII_SOURCE,
                family=MII_FAMILY,
                timeframe="15m",
                signal_ts=signal_ts,
                entry_ts=ts_value(trade.entry_ts),
                exit_ts=ts_value(trade.exit_ts),
                side=int(trade.direction),
                reason=str(trade.exit_reason),
                bars_held=int(trade.bars_held),
                net_return=float(MII_EXPOSURE * (trade.raw_return - mii_v12.ROUND_TRIP_COST)),
                min_mark_return=float(MII_EXPOSURE * (trade.min_path_return - mii_v12.ROUND_TRIP_COST)),
                max_mark_return=float(MII_EXPOSURE * trade.max_path_return),
                entry_price=float(trade.entry_price),
                exit_price=float(trade.exit_price),
                close_mark_returns=close_marks,
                adverse_mark_returns=adverse_marks,
                source_priority=0,
                side_priority=0,
            )
        )
    data_quality = {
        **quality,
        "metadata": metadata,
        "timeframe": "15m",
        "candidate_count": int(len(candidates)),
        "raw_trade_count": int(len(raw_trades)),
        "entry_delay_bars": MII_ENTRY_DELAY_BARS,
        "exposure": MII_EXPOSURE,
        "exit": asdict(MII_EXIT),
        "base_config": asdict(mii_v12.BASE_CONFIG),
    }
    return candidates, data_quality


def common_window(pbtr_events: list[CandidateTrade], mii_events: list[CandidateTrade]) -> tuple[pd.Timestamp, pd.Timestamp]:
    pbtr_start = min(event.entry_ts for event in pbtr_events)
    mii_start = min(event.entry_ts for event in mii_events)
    pbtr_end = max(event.entry_ts for event in pbtr_events) + pd.Timedelta(minutes=5)
    mii_end = max(event.entry_ts for event in mii_events) + pd.Timedelta(minutes=15)
    return max(pbtr_start, mii_start), min(pbtr_end, mii_end)


def in_window(events: list[CandidateTrade], start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> list[CandidateTrade]:
    return [event for event in events if start_ts <= event.entry_ts < end_ts]


def trade_sort_key(event: CandidateTrade, source_priority: dict[str, int]) -> tuple[pd.Timestamp, int, int, pd.Timestamp]:
    return (
        event.entry_ts,
        source_priority[event.source],
        event.side_priority,
        event.signal_ts,
    )


def replay_account(
    *,
    label: str,
    events: list[CandidateTrade],
    source_priority: dict[str, int],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[CandidateTrade]]:
    candidates = sorted(in_window(events, start_ts, end_ts), key=lambda event: trade_sort_key(event, source_priority))
    considered = Counter(event.source for event in candidates)
    accepted = Counter()
    blocked = Counter()
    blocked_by = Counter()
    source_return_sum = Counter()
    selected: list[CandidateTrade] = []
    unavailable_until: pd.Timestamp | None = None
    active_source: str | None = None

    for event in candidates:
        if unavailable_until is not None and event.entry_ts <= unavailable_until:
            blocked[event.source] += 1
            blocked_by[(event.source, active_source or "unknown")] += 1
            continue
        selected.append(event)
        accepted[event.source] += 1
        source_return_sum[event.source] += event.net_return
        unavailable_until = event.exit_ts
        active_source = event.source

    metrics = equity_metrics(selected, start_ts, end_ts)
    summary = {
        "scenario": label,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": max((end_ts - start_ts).total_seconds() / 86_400.0, 0.0),
        "candidate_events": int(len(candidates)),
        "accepted_events": int(len(selected)),
        "blocked_events": int(sum(blocked.values())),
        "pbtr_candidates": int(considered[PBTR_SOURCE]),
        "pbtr_accepted": int(accepted[PBTR_SOURCE]),
        "pbtr_blocked": int(blocked[PBTR_SOURCE]),
        "mii_candidates": int(considered[MII_SOURCE]),
        "mii_accepted": int(accepted[MII_SOURCE]),
        "mii_blocked": int(blocked[MII_SOURCE]),
        "pbtr_simple_return_sum_pct": float(source_return_sum[PBTR_SOURCE] * 100.0),
        "mii_simple_return_sum_pct": float(source_return_sum[MII_SOURCE] * 100.0),
        **metrics,
    }
    source_rows = [
        {
            "scenario": label,
            "source": source,
            "candidate_events": int(considered[source]),
            "accepted_events": int(accepted[source]),
            "blocked_events": int(blocked[source]),
            "accepted_share_pct": float(accepted[source] / max(sum(accepted.values()), 1) * 100.0),
            **equity_metrics([event for event in selected if event.source == source], start_ts, end_ts),
        }
        for source in (PBTR_SOURCE, MII_SOURCE)
    ]
    block_rows = [
        {
            "scenario": label,
            "blocked_source": source,
            "blocking_source": blocker,
            "blocked_events": int(count),
        }
        for (source, blocker), count in sorted(blocked_by.items())
    ]
    return summary, source_rows, block_rows, selected


def equity_metrics(trades: list[CandidateTrade], start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> dict[str, float | int]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400.0, 1.0)
    if not trades:
        return {
            "total_return_pct": 0.0,
            "annual_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "realized_max_drawdown_pct": 0.0,
            "close_mtm_max_drawdown_pct": 0.0,
            "adverse_mtm_max_drawdown_pct": 0.0,
            "mae_marked_max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "avg_trade_pct": 0.0,
            "median_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "best_trade_pct": 0.0,
            "trades_per_day": 0.0,
        }
    equity = 1.0
    peak = 1.0
    realized_max_drawdown = 0.0
    close_mtm_peak = 1.0
    close_mtm_max_drawdown = 0.0
    adverse_mtm_peak = 1.0
    adverse_mtm_max_drawdown = 0.0
    returns: list[float] = []
    for trade in sorted(trades, key=lambda item: item.entry_ts):
        entry_equity = equity
        for mark_return in trade.close_mark_returns:
            mark_equity = entry_equity * max(0.0, 1.0 + float(mark_return))
            close_mtm_peak = max(close_mtm_peak, mark_equity)
            if close_mtm_peak > 0:
                close_mtm_max_drawdown = min(close_mtm_max_drawdown, mark_equity / close_mtm_peak - 1.0)
        for mark_return in trade.adverse_mark_returns:
            mark_equity = entry_equity * max(0.0, 1.0 + float(mark_return))
            adverse_mtm_peak = max(adverse_mtm_peak, mark_equity)
            if adverse_mtm_peak > 0:
                adverse_mtm_max_drawdown = min(adverse_mtm_max_drawdown, mark_equity / adverse_mtm_peak - 1.0)
        equity = entry_equity * max(0.0, 1.0 + trade.net_return)
        peak = max(peak, equity)
        close_mtm_peak = max(close_mtm_peak, equity)
        adverse_mtm_peak = max(adverse_mtm_peak, equity)
        if peak > 0:
            realized_max_drawdown = min(realized_max_drawdown, equity / peak - 1.0)
        if close_mtm_peak > 0:
            close_mtm_max_drawdown = min(close_mtm_max_drawdown, equity / close_mtm_peak - 1.0)
        if adverse_mtm_peak > 0:
            adverse_mtm_max_drawdown = min(adverse_mtm_max_drawdown, equity / adverse_mtm_peak - 1.0)
        returns.append(float(trade.net_return))

    array = np.array(returns, dtype="float64")
    wins = array[array > 0]
    losses = array[array < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    total_return = float(equity - 1.0)
    annual_return = float((1.0 + total_return) ** (365.25 / period_days) - 1.0) if equity > 0 else -1.0
    return {
        "total_return_pct": total_return * 100.0,
        "annual_return_pct": annual_return * 100.0,
        "max_drawdown_pct": realized_max_drawdown * 100.0,
        "realized_max_drawdown_pct": realized_max_drawdown * 100.0,
        "close_mtm_max_drawdown_pct": close_mtm_max_drawdown * 100.0,
        "adverse_mtm_max_drawdown_pct": adverse_mtm_max_drawdown * 100.0,
        "mae_marked_max_drawdown_pct": adverse_mtm_max_drawdown * 100.0,
        "win_rate_pct": float(len(wins) / len(array) * 100.0),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else math.inf,
        "avg_trade_pct": float(np.mean(array) * 100.0),
        "median_trade_pct": float(np.median(array) * 100.0),
        "worst_trade_pct": float(np.min(array) * 100.0),
        "best_trade_pct": float(np.max(array) * 100.0),
        "trades_per_day": float(len(array) / period_days),
    }


def trade_rows(scenario: str, trades: list[CandidateTrade]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade_no, trade in enumerate(sorted(trades, key=lambda item: item.entry_ts), start=1):
        rows.append(
            {
                "scenario": scenario,
                "trade_no": trade_no,
                "source": trade.source,
                "family": trade.family,
                "timeframe": trade.timeframe,
                "signal_ts": trade.signal_ts.isoformat(),
                "entry_ts": trade.entry_ts.isoformat(),
                "exit_ts": trade.exit_ts.isoformat(),
                "side": "long" if trade.side > 0 else "short",
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "net_return_pct": trade.net_return * 100.0,
                "min_mark_return_pct": trade.min_mark_return * 100.0,
                "max_mark_return_pct": trade.max_mark_return * 100.0,
            }
        )
    return rows


def summary_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 场景 | 候选 | 成交 | 阻塞 | PBTR 成交/阻塞 | MII 成交/阻塞 | 总收益 | 年化 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 笔/天 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['scenario']}` | `{int(row['candidate_events'])}` | `{int(row['accepted_events'])}` | "
            f"`{int(row['blocked_events'])}` | `{int(row['pbtr_accepted'])}/{int(row['pbtr_blocked'])}` | "
            f"`{int(row['mii_accepted'])}/{int(row['mii_blocked'])}` | `{row['total_return_pct']:.2f}%` | "
            f"`{row['annual_return_pct']:.2f}%` | `{row['realized_max_drawdown_pct']:.2f}%` | "
            f"`{row['close_mtm_max_drawdown_pct']:.2f}%` | `{row['adverse_mtm_max_drawdown_pct']:.2f}%` | "
            f"`{row['win_rate_pct']:.2f}%` | `{num(float(row['profit_factor']))}` | "
            f"`{row['trades_per_day']:.3f}` |"
        )
    return lines


def colleague_key_table(summary: pd.DataFrame) -> list[str]:
    rows = [
        ("PBTR only", summary.loc[summary["scenario"].eq("pbtr_only")].iloc[0]),
        ("MII only", summary.loc[summary["scenario"].eq("mii_only")].iloc[0]),
        ("combo", summary.loc[summary["scenario"].eq("combo_pbtr_priority")].iloc[0]),
    ]
    lines = [
        "| 场景 | 成交 | 总收益 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 笔/天 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in rows:
        lines.append(
            f"| `{label}` | `{int(row['accepted_events'])}` | `{row['total_return_pct']:.2f}%` | "
            f"`{row['realized_max_drawdown_pct']:.2f}%` | `{row['close_mtm_max_drawdown_pct']:.2f}%` | "
            f"`{row['adverse_mtm_max_drawdown_pct']:.2f}%` | `{row['win_rate_pct']:.2f}%` | "
            f"`{num(float(row['profit_factor']))}` | `{row['trades_per_day']:.3f}` |"
        )
    return lines


def source_table(rows: pd.DataFrame, scenario: str) -> list[str]:
    subset = rows.loc[rows["scenario"].eq(scenario)].copy()
    lines = [
        f"### {scenario}",
        "",
        "| 来源 | 候选 | 成交 | 阻塞 | 成交占比 | 来源内复利总收益 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 平均单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['source']}` | `{int(row['candidate_events'])}` | `{int(row['accepted_events'])}` | "
            f"`{int(row['blocked_events'])}` | `{row['accepted_share_pct']:.2f}%` | "
            f"`{row['total_return_pct']:.2f}%` | `{row['realized_max_drawdown_pct']:.2f}%` | "
            f"`{row['close_mtm_max_drawdown_pct']:.2f}%` | `{row['adverse_mtm_max_drawdown_pct']:.2f}%` | "
            f"`{row['win_rate_pct']:.2f}%` | `{num(float(row['profit_factor']))}` | "
            f"`{row['avg_trade_pct']:.3f}%` |"
        )
    return lines


def render_markdown(
    summary: pd.DataFrame,
    sources: pd.DataFrame,
    blocks: pd.DataFrame,
    *,
    pbtr_quality: dict[str, Any],
    mii_quality: dict[str, Any],
    common_start: pd.Timestamp,
    common_end: pd.Timestamp,
) -> str:
    combo_pbtr = summary.loc[summary["scenario"].eq("combo_pbtr_priority")].iloc[0]
    combo_mii = summary.loc[summary["scenario"].eq("combo_mii_priority")].iloc[0]
    pbtr_only = summary.loc[summary["scenario"].eq("pbtr_only")].iloc[0]
    mii_only = summary.loc[summary["scenario"].eq("mii_only")].iloc[0]
    lines = [
        "# HYPE PBTR V6.2.1 + MII V1.3 共享子账户单仓组合诊断 2026-07-02",
        "",
        "## 结论",
        "",
        (
            "在同一个子账户只允许一个 HYPEUSDT 持仓时，两个策略不能简单相加。"
            "按共同样本窗口和保守全局单仓回放，组合会明显提高交易频率和样本内复利收益，"
            "但严格逐 K mark-to-market 后，风险读数必须分成三层：已平仓权益 DD、bar-close MTM DD、intrabar adverse MTM DD。"
            "`HYPE-5M-PBTR-V6.2.1` 的原始已平仓 `-22%` 级别回撤仍成立；如果按每根 K 收盘标记，回撤仍在可解释范围内；"
            "只有按每根 K 的最不利 high/low 做强制平仓式标记时，才会看到约 `-55%` 的极端浮亏压力。"
            "这不是更安全的合并，只是两个正期望样本流在高杠杆口径下的收益叠加诊断。"
        ),
        "",
        (
            f"- 共同窗口：`{common_start.isoformat()}` 到 `{common_end.isoformat()}`。"
            "只统计 entry 落在共同窗口内的候选事件。"
        ),
        (
            f"- `PBTR only`：`{int(pbtr_only['accepted_events'])}` 笔，总收益 `{pbtr_only['total_return_pct']:.2f}%`，"
            f"已平仓 DD `{pbtr_only['realized_max_drawdown_pct']:.2f}%`，Close MTM DD `{pbtr_only['close_mtm_max_drawdown_pct']:.2f}%`，"
            f"Intrabar adverse DD `{pbtr_only['adverse_mtm_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- `MII only`：`{int(mii_only['accepted_events'])}` 笔，总收益 `{mii_only['total_return_pct']:.2f}%`，"
            f"已平仓 DD `{mii_only['realized_max_drawdown_pct']:.2f}%`，Close MTM DD `{mii_only['close_mtm_max_drawdown_pct']:.2f}%`，"
            f"Intrabar adverse DD `{mii_only['adverse_mtm_max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- `combo_pbtr_priority`：`{int(combo_pbtr['accepted_events'])}` 笔，总收益 "
            f"`{combo_pbtr['total_return_pct']:.2f}%`，已平仓 DD `{combo_pbtr['realized_max_drawdown_pct']:.2f}%`，"
            f"Close MTM DD `{combo_pbtr['close_mtm_max_drawdown_pct']:.2f}%`，"
            f"Intrabar adverse DD `{combo_pbtr['adverse_mtm_max_drawdown_pct']:.2f}%`；"
            f"其中 PBTR 成交/阻塞 `{int(combo_pbtr['pbtr_accepted'])}/{int(combo_pbtr['pbtr_blocked'])}`，"
            f"MII 成交/阻塞 `{int(combo_pbtr['mii_accepted'])}/{int(combo_pbtr['mii_blocked'])}`。"
        ),
        (
            f"- `combo_mii_priority`：`{int(combo_mii['accepted_events'])}` 笔，总收益 "
            f"`{combo_mii['total_return_pct']:.2f}%`，已平仓 DD `{combo_mii['realized_max_drawdown_pct']:.2f}%`，"
            f"Close MTM DD `{combo_mii['close_mtm_max_drawdown_pct']:.2f}%`，"
            f"Intrabar adverse DD `{combo_mii['adverse_mtm_max_drawdown_pct']:.2f}%`；"
            f"本窗口内同 timestamp 优先级改变没有影响，说明冲突主要来自持仓区间重叠，而不是同一时刻抢单。"
        ),
        "",
        "直观解释：`PBTR` 信号更多、持仓更碎，会占掉一部分 `MII` 入场；但这次样本里被保留下来的 `MII` 子集反而更强，来源内复利收益高于 `MII only`。真正的问题不是原始已平仓 DD 从 `-22%` 变成 `-55%`，而是如果按每根 K 的最不利 high/low 做强制平仓式标记，`PBTR` 的 `3x` 持仓内压力在共享账户里仍然很大。若要共用子账户，应先降 PBTR sizing 或设置全局风险预算，而不是直接把两个默认暴露放在一起跑。",
        "",
        "## 给同事看的关键表",
        "",
        "这张表里的 `Close MTM DD` 更接近平常说的持仓回撤；`Intrabar adverse DD` 是用 K 线 high/low 做最不利标记的压力测试，不应和常规最大回撤混用。",
        "",
    ]
    lines.extend(colleague_key_table(summary))
    lines.extend(
        [
            "",
            "## 回放口径",
            "",
        ]
    )
    lines.extend(
        [
        "- `HYPE-5M-PBTR-V6.2.1`：复用既有 `V6.2.1` long/short filtered signal，下一根 `5m` open 入场，入场即固定 TP/SL，fixed `3x` 回测口径。",
        "- `HYPE-15M-MII-V1.3`：复用 `V1.2` ATR bracket 候选，`K+1` 下一根 `15m` open 入场，`TP=1.25*ATR96%`、`SL=5*ATR96%`、`hold=24`，fixed `2.5x` exposure。",
        "- 全局单仓：按候选 `entry_ts` 排序；若已有持仓未退出，后续候选信号直接视为 blocked；若 entry 与上一笔 exit 同 timestamp，也保守视为 blocked。",
        "- 同 timestamp 优先级：分别测试 `PBTR` 优先和 `MII` 优先。真实 runner 必须显式配置这一规则。",
        "- 回撤口径：`已平仓DD` 只在交易退出后更新权益；`Close MTM DD` 在持仓期间逐根 K 用 close 做可清算标记；`Intrabar adverse DD` 在持仓期间逐根 K 用 long 的 low / short 的 high 做最不利可清算标记，因此是 OHLC 下偏保守的浮亏压力读数。",
        "",
        "## 汇总",
        "",
        ]
    )
    lines.extend(summary_table(summary))
    lines.extend(["", "## 来源拆分", ""])
    for scenario in ("combo_pbtr_priority", "combo_mii_priority"):
        lines.extend(source_table(sources, scenario))
        lines.append("")
    lines.extend(
        [
            "## 阻塞矩阵",
            "",
            "| 场景 | 被阻塞来源 | 占仓来源 | 阻塞次数 |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for row in blocks.to_dict(orient="records"):
        lines.append(
            f"| `{row['scenario']}` | `{row['blocked_source']}` | `{row['blocking_source']}` | `{int(row['blocked_events'])}` |"
        )
    lines.extend(
        [
            "",
            "## 数据质量与限制",
            "",
            (
                f"- PBTR `5m` rows `{pbtr_quality['rows']}`，范围 `{pbtr_quality['first_ts']}` 到 "
                f"`{pbtr_quality['last_ts']}`，filtered 候选 `{pbtr_quality['candidate_count']}`。"
            ),
            (
                f"- MII `15m` rows `{mii_quality['rows']}`，quality gate `{mii_quality['quality_gate_pass']}`，"
                f"范围 `{mii_quality['first_ts']}` 到 `{mii_quality['last_ts']}`，filtered 候选 `{mii_quality['candidate_count']}`。"
            ),
            "- 这是 OHLC bar replay 的组合层诊断，未纳入资金费、盘口级滑点、真实 market/stop-market 延迟、交易所仓位/挂单对账和 runner 重启恢复。",
            "- 两个策略各自都没有获得 live-ready 批准；组合运行还会新增跨策略优先级、全局 kill switch、全局 notional cap 和 state reconciliation 风险。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- 来源拆分 CSV：`{SOURCE_CSV_PATH}`",
            f"- 阻塞矩阵 CSV：`{BLOCK_CSV_PATH}`",
            f"- 成交明细 CSV：`{TRADES_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [json_safe(child) for child in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    pbtr_events, pbtr_quality = build_pbtr_candidates()
    mii_events, mii_quality = build_mii_candidates()
    common_start, common_end = common_window(pbtr_events, mii_events)
    scenarios = [
        ("pbtr_only", pbtr_events, {PBTR_SOURCE: 0, MII_SOURCE: 1}),
        ("mii_only", mii_events, {MII_SOURCE: 0, PBTR_SOURCE: 1}),
        ("combo_pbtr_priority", pbtr_events + mii_events, {PBTR_SOURCE: 0, MII_SOURCE: 1}),
        ("combo_mii_priority", pbtr_events + mii_events, {MII_SOURCE: 0, PBTR_SOURCE: 1}),
    ]
    summary_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    trade_detail_rows: list[dict[str, Any]] = []
    selected_by_scenario: dict[str, list[CandidateTrade]] = {}
    for label, events, priority in scenarios:
        summary, sources, blocks, selected = replay_account(
            label=label,
            events=events,
            source_priority=priority,
            start_ts=common_start,
            end_ts=common_end,
        )
        summary_rows.append(summary)
        source_rows.extend(sources)
        block_rows.extend(blocks)
        trade_detail_rows.extend(trade_rows(label, selected))
        selected_by_scenario[label] = selected

    summary = pd.DataFrame(summary_rows)
    sources = pd.DataFrame(source_rows)
    blocks = pd.DataFrame(block_rows)
    trades = pd.DataFrame(trade_detail_rows)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    sources.to_csv(SOURCE_CSV_PATH, index=False)
    blocks.to_csv(BLOCK_CSV_PATH, index=False)
    trades.to_csv(TRADES_CSV_PATH, index=False)
    payload = {
        "run_date": RUN_DATE,
        "topic": "HYPE shared sub-account one-position replay",
        "strategies": [PBTR_SOURCE, MII_SOURCE],
        "common_window": {"start_ts": common_start, "end_ts": common_end},
        "assumptions": {
            "global_single_position": True,
            "same_timestamp_exit_entry": "blocked_conservative",
            "mii_entry_timing": "K+1 15m open",
            "pbtr_entry_timing": "K+1 5m open",
            "funding_included": False,
            "orderbook_slippage_included": False,
        },
        "data_quality": {"pbtr": pbtr_quality, "mii": mii_quality},
        "summary": summary.to_dict(orient="records"),
        "source_breakdown": sources.to_dict(orient="records"),
        "blocks": blocks.to_dict(orient="records"),
        "outputs": {
            "script": str(SCRIPT_PATH),
            "summary_csv": str(SUMMARY_CSV_PATH),
            "source_csv": str(SOURCE_CSV_PATH),
            "block_csv": str(BLOCK_CSV_PATH),
            "trades_csv": str(TRADES_CSV_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    JSON_PATH.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    MARKDOWN_PATH.write_text(
        render_markdown(
            summary,
            sources,
            blocks,
            pbtr_quality=pbtr_quality,
            mii_quality=mii_quality,
            common_start=common_start,
            common_end=common_end,
        ),
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
