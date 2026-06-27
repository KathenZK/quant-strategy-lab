from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass, fields
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

from research_hype_5m_event_quality_v0 import validate_and_load  # noqa: E402
from research_hype_5m_micro_scalp_search import ScalpConfig, add_features, build_signal  # noqa: E402


RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-event-quality-scoring")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SEED_SOURCE_PATH = Path(
    "research/hype/5m-micro-scalp/artifacts/"
    "hype_5m_micro_scalp_relaxed_rounds_summary_2026-06-26.csv"
)
REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_{RUN_DATE}.json"
SUMMARY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_summary_{RUN_DATE}.csv"
MONTHLY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_monthly_{RUN_DATE}.csv"
EVENTS_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_events_{RUN_DATE}.csv"
TOP_TRADES_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-seeded-event-quality-v0-{RUN_DATE}.md"

FEE_RATE_PER_FILL = 3.0578 / 7374.2110
ENTRY_SLIPPAGE_RATE = 10.73 / 10000.0
EXIT_SLIPPAGE_RATE = -2.64 / 10000.0

TRAIN_PREFIX = "train_2025_05_30_to_2026_03_01"
OOS_START = pd.Timestamp("2026-03-01T00:00:00Z")
QUANTILES = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95)
MAX_SEED_CONFIGS = 100


@dataclass(slots=True)
class SeedEvent:
    event_id: int
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


@dataclass(slots=True)
class ReplayTrade:
    candidate_id: str
    event_id: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    cfg_name: str
    style: str
    score: float
    reason: str
    bars_held: int
    net_ret_1x: float


INT_FIELDS = {"ema_fast", "ema_slow", "ema_htf", "donchian", "rsi_window", "max_hold_bars", "cooldown_bars"}
BOOL_FIELDS = {"require_trend", "require_htf", "require_macd_turn", "require_body_dir"}
FLOAT_FIELDS = {
    "rsi_low",
    "rsi_high",
    "bb_z",
    "vwap_dev_bps",
    "pullback_bps",
    "breakout_bps",
    "min_dir_roc_bps",
    "max_counter_roc_bps",
    "min_adx",
    "max_chop",
    "min_rvol",
    "min_atr_pct_bps",
    "max_atr_pct_bps",
    "max_dist_ema_bps",
    "wick_atr",
    "close_pos",
    "tp_bps",
    "sl_bps",
}


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def row_to_config(row: pd.Series) -> ScalpConfig:
    values: dict[str, Any] = {}
    for item in fields(ScalpConfig):
        raw = row[f"cfg_{item.name}"]
        if item.name in BOOL_FIELDS:
            values[item.name] = bool(raw) if isinstance(raw, bool | np.bool_) else str(raw).lower() == "true"
        elif item.name in INT_FIELDS:
            values[item.name] = int(float(raw))
        elif item.name in FLOAT_FIELDS:
            values[item.name] = float(raw)
        else:
            values[item.name] = str(raw)
    values["name"] = str(row["name"])
    return ScalpConfig(**values)


def select_seed_configs() -> tuple[list[ScalpConfig], pd.DataFrame]:
    if not SEED_SOURCE_PATH.exists():
        raise FileNotFoundError(SEED_SOURCE_PATH)
    summary = pd.read_csv(SEED_SOURCE_PATH)
    pool = summary[
        (summary[f"{TRAIN_PREFIX}_trades"] >= 40)
        & (summary[f"{TRAIN_PREFIX}_total_return"] > 0)
        & (summary[f"{TRAIN_PREFIX}_profit_factor"] >= 1.15)
        & (summary[f"{TRAIN_PREFIX}_max_dd"] >= -0.25)
    ].copy()
    pool = pool.sort_values(
        [f"{TRAIN_PREFIX}_total_return", f"{TRAIN_PREFIX}_profit_factor"],
        ascending=[False, False],
    ).head(MAX_SEED_CONFIGS)
    return [row_to_config(row) for _, row in pool.iterrows()], pool


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return bool(open_price <= stop_price if side > 0 else open_price >= stop_price)


def touched_stop(high_price: float, low_price: float, stop_price: float, side: int) -> bool:
    return bool(low_price <= stop_price if side > 0 else high_price >= stop_price)


def crossed_target(open_price: float, target_price: float, side: int) -> bool:
    return bool(open_price >= target_price if side > 0 else open_price <= target_price)


def touched_target(high_price: float, low_price: float, target_price: float, side: int) -> bool:
    return bool(high_price >= target_price if side > 0 else low_price <= target_price)


def simulate_seed_event(frame: pd.DataFrame, signal_idx: int, side: int, cfg: ScalpConfig) -> dict[str, Any] | None:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    entry_idx = signal_idx + 1
    if entry_idx >= len(frame):
        return None
    entry_price = float(open_[entry_idx] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
    target_price = entry_price * (1.0 + side * cfg.tp_bps / 10000.0)
    stop_price = entry_price * (1.0 - side * cfg.sl_bps / 10000.0)
    last_intrabar = min(len(frame) - 1, entry_idx + cfg.max_hold_bars - 1)
    timeout_idx = min(len(frame) - 1, entry_idx + cfg.max_hold_bars)
    exit_idx = timeout_idx
    raw_exit = float(open_[timeout_idx] if timeout_idx > last_intrabar else close[timeout_idx])
    reason = "time_open"
    for bar_idx in range(entry_idx, last_intrabar + 1):
        if crossed_stop(float(open_[bar_idx]), stop_price, side):
            exit_idx = bar_idx
            raw_exit = float(open_[bar_idx])
            reason = "gap_stop_market"
            break
        if touched_stop(float(high[bar_idx]), float(low[bar_idx]), stop_price, side):
            exit_idx = bar_idx
            raw_exit = float(stop_price)
            reason = "stop_market"
            break
        if crossed_target(float(open_[bar_idx]), target_price, side):
            exit_idx = bar_idx
            raw_exit = float(open_[bar_idx])
            reason = "gap_target_market"
            break
        if touched_target(float(high[bar_idx]), float(low[bar_idx]), target_price, side):
            exit_idx = bar_idx
            raw_exit = float(target_price)
            reason = "target_limit"
            break
    exit_price = raw_exit * (1.0 - side * EXIT_SLIPPAGE_RATE)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return {
        "entry_idx": int(entry_idx),
        "exit_idx": int(exit_idx),
        "signal_ts": pd.Timestamp(ts_ns[signal_idx], unit="ns", tz="UTC"),
        "entry_ts": pd.Timestamp(ts_ns[entry_idx], unit="ns", tz="UTC"),
        "exit_ts": pd.Timestamp(ts_ns[exit_idx], unit="ns", tz="UTC"),
        "net_ret_1x": float(gross - fee_cost),
        "reason": reason,
    }


def build_seed_events(frame: pd.DataFrame, configs: list[ScalpConfig]) -> pd.DataFrame:
    rows: list[SeedEvent] = []
    for cfg in configs:
        signal = build_signal(frame, cfg)
        for signal_idx in np.flatnonzero(signal):
            side = int(signal[signal_idx])
            outcome = simulate_seed_event(frame, int(signal_idx), side, cfg)
            if outcome is None:
                continue
            rows.append(
                SeedEvent(
                    event_id=len(rows),
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
        raise RuntimeError("no seeded events generated")
    events = pd.DataFrame([asdict(row) for row in rows])
    events["signal_ts"] = pd.to_datetime(events["signal_ts"], utc=True)
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    return events.sort_values(["signal_idx", "cfg_name"]).reset_index(drop=True)


def score_month(events: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    cfg_mean = train.groupby("cfg_name")["net_ret_1x"].mean()
    style_mean = train.groupby("style")["net_ret_1x"].mean()
    side_mean = train.groupby("side")["net_ret_1x"].mean()
    global_mean = float(train["net_ret_1x"].mean())
    scored = test.copy()
    scored["score"] = (
        0.70 * scored["cfg_name"].map(cfg_mean).fillna(global_mean)
        + 0.20 * scored["style"].map(style_mean).fillna(global_mean)
        + 0.10 * scored["side"].map(side_mean).fillna(global_mean)
    )
    train_score = (
        0.70 * train["cfg_name"].map(cfg_mean).fillna(global_mean)
        + 0.20 * train["style"].map(style_mean).fillna(global_mean)
        + 0.10 * train["side"].map(side_mean).fillna(global_mean)
    )
    for quantile in QUANTILES:
        scored[f"threshold_q{int(round(quantile * 100)):02d}"] = float(np.quantile(train_score, quantile))
    return scored


def walk_forward_score(events: pd.DataFrame) -> pd.DataFrame:
    scored_rows: list[pd.DataFrame] = []
    data_end = pd.Timestamp(events["signal_ts"].max()) + pd.Timedelta(minutes=5)
    for test_start in pd.date_range(OOS_START, data_end, freq="MS", tz="UTC"):
        test_end = min(test_start + pd.DateOffset(months=1), data_end)
        train = events[events["signal_ts"] < test_start - pd.Timedelta(hours=12)]
        test = events[(events["signal_ts"] >= test_start) & (events["signal_ts"] < test_end)]
        if len(train) < 50 or test.empty:
            continue
        scored = score_month(events, train, test)
        scored["segment"] = f"{test_start:%Y_%m}"
        scored["train_events"] = int(len(train))
        scored_rows.append(scored)
    if not scored_rows:
        raise RuntimeError("no scored OOS segments")
    return pd.concat(scored_rows, ignore_index=True)


def replay_selected(scored: pd.DataFrame, quantile: float, candidate_id: str) -> tuple[list[ReplayTrade], pd.DataFrame]:
    threshold_col = f"threshold_q{int(round(quantile * 100)):02d}"
    selected = scored[scored["score"] >= scored[threshold_col]].copy()
    selected = selected.sort_values(["signal_idx", "score"], ascending=[True, False])
    selected = selected.drop_duplicates("signal_idx", keep="first").sort_values("signal_idx")
    blocked_until = -1
    trades: list[ReplayTrade] = []
    for row in selected.itertuples(index=False):
        if int(row.entry_idx) <= blocked_until:
            continue
        trades.append(
            ReplayTrade(
                candidate_id=candidate_id,
                event_id=int(row.event_id),
                signal_ts=pd.Timestamp(row.signal_ts),
                entry_ts=pd.Timestamp(row.entry_ts),
                exit_ts=pd.Timestamp(row.exit_ts),
                side=int(row.side),
                cfg_name=str(row.cfg_name),
                style=str(row.style),
                score=float(row.score),
                reason=str(row.reason),
                bars_held=int(row.exit_idx - row.entry_idx + 1),
                net_ret_1x=float(row.net_ret_1x),
            )
        )
        blocked_until = int(row.exit_idx) + int(row.cooldown_bars)
    return trades, selected


def equity_max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[:-1]
    return float((equity / peak - 1.0).min())


def metrics(trades: list[ReplayTrade], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    returns = np.array([trade.net_ret_1x for trade in selected], dtype="float64")
    days = max((end - start).total_seconds() / 86400.0, 1e-9)
    total_return = float(np.prod(1.0 + returns) - 1.0) if len(returns) else 0.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    return {
        "trades": int(len(returns)),
        "days": float(days),
        "trades_per_day": float(len(returns) / days),
        "total_return_1x": total_return,
        "annualized_1x": float((1.0 + total_return) ** (365.0 / days) - 1.0) if total_return > -1 else -1.0,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else math.inf,
        "avg_trade_bps": float(returns.mean() * 10000.0) if len(returns) else 0.0,
        "max_drawdown_1x": equity_max_drawdown(returns),
    }


def monthly_metrics(candidate_id: str, trades: list[ReplayTrade], start: pd.Timestamp, end: pd.Timestamp) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start.floor("D").replace(day=1)
    while cursor < end:
        next_month = cursor + pd.offsets.MonthBegin(1)
        slice_start = max(start, cursor)
        slice_end = min(end, next_month)
        row = {"candidate_id": candidate_id, "month": slice_start.strftime("%Y_%m")}
        row.update(metrics(trades, slice_start, slice_end))
        rows.append(row)
        cursor = next_month
    return rows


def gate(row: dict[str, Any], monthly_rows: list[dict[str, Any]]) -> bool:
    active = [item for item in monthly_rows if item["trades"] > 0]
    negative = sum(1 for item in active if item["total_return_1x"] < 0)
    return bool(
        row["oos_trades"] >= 80
        and 0.50 <= row["oos_trades_per_day"] <= 5.0
        and row["oos_total_return_1x"] > 0
        and row["oos_profit_factor"] >= 1.15
        and row["oos_avg_trade_bps"] >= 5.0
        and row["oos_max_drawdown_1x"] >= -0.25
        and row["recent_30d_total_return_1x"] > 0
        and (not active or negative <= len(active) // 2)
    )


def run_evaluation(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[ReplayTrade], pd.DataFrame]:
    start = OOS_START
    end = pd.Timestamp(scored["signal_ts"].max()) + pd.Timedelta(minutes=5)
    summary_rows: list[dict[str, Any]] = []
    monthly_rows_all: list[dict[str, Any]] = []
    best_trades: list[ReplayTrade] = []
    best_selected = pd.DataFrame()
    best_return = -math.inf
    for quantile in QUANTILES:
        candidate_id = f"seeded_source_mean_q{int(round(quantile * 100)):02d}"
        trades, selected = replay_selected(scored, quantile, candidate_id)
        oos = metrics(trades, start, end)
        recent_90_start = max(start, end - pd.Timedelta(days=90))
        recent_30_start = max(start, end - pd.Timedelta(days=30))
        recent_90 = metrics(trades, recent_90_start, end)
        recent_30 = metrics(trades, recent_30_start, end)
        months = monthly_metrics(candidate_id, trades, start, end)
        monthly_rows_all.extend(months)
        row = {"candidate_id": candidate_id, "quantile": quantile, "selected_events": int(len(selected))}
        for key, value in oos.items():
            row[f"oos_{key}"] = value
        for key, value in recent_90.items():
            row[f"recent_90d_{key}"] = value
        for key, value in recent_30.items():
            row[f"recent_30d_{key}"] = value
        row["active_months"] = int(sum(1 for item in months if item["trades"] > 0))
        row["negative_active_months"] = int(
            sum(1 for item in months if item["trades"] > 0 and item["total_return_1x"] < 0)
        )
        row["paper_gate"] = gate(row, months)
        summary_rows.append(row)
        if row["oos_total_return_1x"] > best_return:
            best_return = float(row["oos_total_return_1x"])
            best_trades = trades
            best_selected = selected
    summary = pd.DataFrame(summary_rows).sort_values(
        ["paper_gate", "oos_total_return_1x", "recent_30d_total_return_1x"],
        ascending=[False, False, False],
    )
    return summary, pd.DataFrame(monthly_rows_all), best_trades, best_selected


def trade_frame(trades: list[ReplayTrade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(trade) for trade in trades])


def serializable(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return "inf" if value > 0 else "-inf"
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def render_markdown(
    quality: dict[str, Any],
    seed_pool: pd.DataFrame,
    events: pd.DataFrame,
    summary: pd.DataFrame,
    monthly: pd.DataFrame,
) -> str:
    top = summary.iloc[0].to_dict()
    pass_count = int(summary["paper_gate"].sum())
    lines = [
        "# HYPE-5M-Event-Quality-Scoring Seeded V0",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
    ]
    if pass_count:
        lines.append(f"- Seeded V0 找到 `{pass_count}` 个 paper-audit 级别候选。")
    else:
        lines.append("- Seeded V0 没有找到通过 paper gate 的候选。")
    lines.extend(
        [
            f"- 当前最佳：`{top['candidate_id']}`。",
            f"- OOS：`{int(top['oos_trades'])}` 笔，`{top['oos_trades_per_day']:.2f}` 笔/天，"
            f"收益 `{pct(top['oos_total_return_1x'])}`，PF `{num(top['oos_profit_factor'])}`，"
            f"最大回撤 `{pct(top['oos_max_drawdown_1x'])}`。",
            "",
            "注意：这是 seeded diagnostic。种子配置来自 `HYPE-5M-Micro-Scalp` 的历史搜索产物，",
            "本脚本只用 2026-03-01 前的 train 指标筛选 seed，但 config universe 本身仍来自既有研究，",
            "所以当前结论最多是 paper-audit 候选，不是 live-ready。",
            "",
            "## 数据质量",
            "",
            f"- 数据范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
            f"- 行数：`{quality['rows']}`，缺口：`{quality['missing_bars']}`。",
            f"- raw/normalized 对齐：`{quality['raw_alignment']['same_ts_sequence']}`。",
            f"- raw/normalized 最大差异：`{quality['raw_alignment']['max_abs_diff']}`。",
            "",
            "## 方法",
            "",
            f"- Seed source：`{SEED_SOURCE_PATH}`。",
            f"- Seed configs：从 relaxed summary 里仅按 `{TRAIN_PREFIX}` 指标选前 `{len(seed_pool)}` 个。",
            "- Seed 条件：train trades >= 40、train return > 0、train PF >= 1.15、train maxDD >= -25%。",
            "- OOS 起点：`2026-03-01 00:00:00+00:00`。",
            "- 每月 walk-forward：用测试月之前的 seed 事件收益估计 cfg/style/side source mean score。",
            "- 执行：闭合 K 信号、下一根 open 入场、固定 TP/SL、stop-first、open 穿越按 open 成交。",
            "",
            "## Seed 事件池",
            "",
            f"- 事件数：`{len(events)}`。",
            f"- unique signal bars：`{events['signal_idx'].nunique()}`。",
            f"- 平均独立事件收益：`{events['net_ret_1x'].mean() * 10000:.2f} bps`。",
            "",
            "## Ranking 结果",
            "",
            "| rank | candidate | trades | t/day | ret | PF | win | avg bps | DD | recent30 | gate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for rank, (_, row) in enumerate(summary.iterrows(), start=1):
        lines.append(
            f"| {rank} | `{row['candidate_id']}` | {int(row['oos_trades'])} | "
            f"{row['oos_trades_per_day']:.2f} | {pct(row['oos_total_return_1x'])} | "
            f"{num(row['oos_profit_factor'])} | {pct(row['oos_win_rate'])} | "
            f"{row['oos_avg_trade_bps']:.2f} | {pct(row['oos_max_drawdown_1x'])} | "
            f"{pct(row['recent_30d_total_return_1x'])} | {bool(row['paper_gate'])} |"
        )
    top_monthly = monthly[monthly["candidate_id"] == top["candidate_id"]]
    lines.extend(
        [
            "",
            "## 最佳候选月度",
            "",
            "| month | trades | ret | PF | win | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in top_monthly.iterrows():
        lines.append(
            f"| `{row['month']}` | {int(row['trades'])} | {pct(row['total_return_1x'])} | "
            f"{num(row['profit_factor'])} | {pct(row['win_rate'])} | "
            f"{row['avg_trade_bps']:.2f} | {pct(row['max_drawdown_1x'])} |"
        )
    lines.extend(
        [
            "",
            "## 保留产物",
            "",
            f"- JSON：`{REPORT_JSON}`",
            f"- Summary：`{SUMMARY_CSV}`",
            f"- Monthly：`{MONTHLY_CSV}`",
            f"- Events：`{EVENTS_CSV}`",
            f"- Top trades：`{TOP_TRADES_CSV}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    raw_frame, quality = validate_and_load()
    frame = add_features(raw_frame)
    seed_configs, seed_pool = select_seed_configs()
    events = build_seed_events(frame, seed_configs)
    scored = walk_forward_score(events)
    summary, monthly, best_trades, best_selected = run_evaluation(scored)

    events.to_csv(EVENTS_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    monthly.to_csv(MONTHLY_CSV, index=False)
    trade_frame(best_trades).to_csv(TOP_TRADES_CSV, index=False)
    best_selected.to_csv(
        ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_top_selected_events_{RUN_DATE}.csv",
        index=False,
    )

    report = {
        "run_date": RUN_DATE,
        "family": "HYPE-5M-Event-Quality-Scoring",
        "mode": "seeded_v0",
        "quality": quality,
        "seed_source_path": str(SEED_SOURCE_PATH),
        "seed_selection": {
            "train_prefix": TRAIN_PREFIX,
            "max_seed_configs": MAX_SEED_CONFIGS,
            "selected_seed_configs": int(len(seed_pool)),
            "rules": {
                f"{TRAIN_PREFIX}_trades": ">= 40",
                f"{TRAIN_PREFIX}_total_return": "> 0",
                f"{TRAIN_PREFIX}_profit_factor": ">= 1.15",
                f"{TRAIN_PREFIX}_max_dd": ">= -0.25",
            },
        },
        "event_count": int(len(events)),
        "unique_signal_bars": int(events["signal_idx"].nunique()),
        "paper_candidate_pass_count": int(summary["paper_gate"].sum()),
        "top_candidate": {key: serializable(value) for key, value in summary.iloc[0].to_dict().items()},
        "artifact_paths": {
            "summary": str(SUMMARY_CSV),
            "monthly": str(MONTHLY_CSV),
            "events": str(EVENTS_CSV),
            "top_trades": str(TOP_TRADES_CSV),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=serializable),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(quality, seed_pool, events, summary, monthly), encoding="utf-8")
    print(json.dumps(report["top_candidate"], ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
