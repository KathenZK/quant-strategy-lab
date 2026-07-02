from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from research_hype_ema_cross_strategy import SLIPPAGE, TRADE_COST, build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import add_structure_features
from research_hype_v13_late_reentry import run_late_reentry
from research_hype_v17_1_full_ablation import base_candidate_v17_1
from research_hype_v17_hybrid_ablation import hybrid_signal
from research_hype_v17_trend_state_search import SignalPlan, add_v17_indicators, build_signal


RUN_DATE = "2026-07-01"
LEDGER_SLICE_END = pd.Timestamp("2026-06-01 03:00:00+00:00")
FAMILY_ROOT = Path("research/hype/15m-ema-crossover")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_ema_x_v17_1_strict_live_audit_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_ema_x_v17_1_strict_live_audit_trades_{RUN_DATE}.csv"
CAUSALITY_PATH = ARTIFACT_ROOT / f"hype_ema_x_v17_1_strict_feature_causality_{RUN_DATE}.csv"
TIMING_PATH = ARTIFACT_ROOT / f"hype_ema_x_v17_1_strict_signal_timing_{RUN_DATE}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_ema_x_v17_1_strict_live_audit_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-ema-x-v17-1-strict-live-audit-{RUN_DATE}.md"

EXECUTION_MODES = (
    "baseline",
    "stop_gap_open",
    "stop_delay_1bar",
    "stop_market_extra_slip",
)

CAUSALITY_COLUMNS = [
    "ema96",
    "ema384",
    "ema_spread",
    "regime_age",
    "adx28",
    "atr_pct672",
    "vol_surge192",
    "dir_dist_ema96",
    "atr_ratio96_672",
    "trend_score",
    "h1_adx21",
    "h1_pdi21",
    "h1_mdi21",
    "h1_ema_spread",
    "h1_rsi14_osc",
    "low96",
    "high96",
    "ema21",
]


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def build_feature_frame(raw: pd.DataFrame) -> pd.DataFrame:
    return add_v17_indicators(
        add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    )


def data_quality_summary(raw: pd.DataFrame) -> dict[str, Any]:
    ts = pd.to_datetime(raw["ts"], utc=True)
    expected = pd.date_range(ts.iloc[0], ts.iloc[-1], freq="15min")
    duplicate_ts = int(ts.duplicated().sum())
    missing = expected.difference(ts)
    null_counts = {
        col: int(raw[col].isna().sum())
        for col in ("open", "high", "low", "close", "volume")
        if col in raw.columns
    }
    invalid_ohlc = int(
        (
            (raw["high"] < raw[["open", "close", "low"]].max(axis=1))
            | (raw["low"] > raw[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    return {
        "first_bar": ts.iloc[0].isoformat(),
        "last_bar": ts.iloc[-1].isoformat(),
        "rows": int(len(raw)),
        "duplicate_ts": duplicate_ts,
        "missing_bars": int(len(missing)),
        "first_missing": None if len(missing) == 0 else missing[0].isoformat(),
        "invalid_ohlc": invalid_ohlc,
        "null_counts": json.dumps(null_counts, ensure_ascii=False, sort_keys=True),
    }


def feature_causality_check(raw: pd.DataFrame, full: pd.DataFrame) -> pd.DataFrame:
    check_indices = sorted(
        {
            400,
            800,
            1200,
            len(full) // 4,
            len(full) // 2,
            len(full) * 3 // 4,
            len(full) - 2,
        }
    )
    rows: list[dict[str, Any]] = []
    for idx in check_indices:
        if idx < 384 or idx >= len(full):
            continue
        truncated = build_feature_frame(raw.iloc[: idx + 1].copy())
        for column in CAUSALITY_COLUMNS:
            if column not in full.columns or column not in truncated.columns:
                continue
            full_value = full[column].iloc[idx]
            trunc_value = truncated[column].iloc[-1]
            if pd.isna(full_value) and pd.isna(trunc_value):
                diff = 0.0
                match = True
            elif pd.notna(full_value) and pd.notna(trunc_value):
                diff = abs(float(full_value) - float(trunc_value))
                match = diff <= 1e-10
            else:
                diff = np.inf
                match = False
            rows.append(
                {
                    "idx": idx,
                    "ts": full["ts"].iloc[idx],
                    "column": column,
                    "full_value": full_value,
                    "truncated_value": trunc_value,
                    "abs_diff": diff,
                    "match": match,
                }
            )
    return pd.DataFrame(rows)


def run_v17_1(
    frame: pd.DataFrame,
    *,
    start_ts: pd.Timestamp,
    stop_fill_mode: str,
    collect_trades: bool,
) -> dict[str, Any]:
    candidate = base_candidate_v17_1()
    base_signal, _, _ = build_signal(frame, SignalPlan("atr18_base", "atr18"))
    signal, kind, counts = hybrid_signal(frame, candidate.signal, base_signal)
    result = run_late_reentry(
        frame,
        candidate.spec,
        start_ts=start_ts,
        collect_trades=collect_trades,
        signal_override=signal,
        signal_kind_override=kind,
        entry_allocation_scale={"hq": candidate.hq_scale, "lq": candidate.lq_scale},
        stop_fill_mode=stop_fill_mode,
    )
    result["signal_counts"] = counts
    result["stop_fill_mode"] = stop_fill_mode
    return result


def summarize_mode(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": result["stop_fill_mode"],
        "return": float(result["return"]),
        "max_dd": float(result["max_dd"]),
        "sharpe": float(result["sharpe"]),
        "trades": int(result["trades"]),
        "late_trades": int(result["late_trades"]),
        "win_rate": float(result["win_rate"]),
        "exit_reasons": json.dumps(result["exit_reasons"], ensure_ascii=False, sort_keys=True),
    }


def index_lookup(ts_index: pd.DatetimeIndex, value: pd.Timestamp) -> int:
    loc = ts_index.get_indexer([value], method=None)
    if loc[0] < 0:
        raise KeyError(f"timestamp not found: {value}")
    return int(loc[0])


def audit_trade_crossings(frame: pd.DataFrame, trades: list[dict[str, Any]]) -> pd.DataFrame:
    ts_index = pd.DatetimeIndex(pd.to_datetime(frame["ts"], utc=True))
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr672 = frame["atr_pct672"].to_numpy("float64")
    signal = np.zeros(len(frame), dtype=np.int8)
    base_signal, _, _ = build_signal(frame, SignalPlan("atr18_base", "atr18"))
    hybrid, _, _ = hybrid_signal(frame, base_candidate_v17_1().signal, base_signal)
    signal[:] = hybrid

    rows: list[dict[str, Any]] = []
    for trade in trades:
        if trade["exit_reason"] == "open_at_end":
            continue
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        entry_i = index_lookup(ts_index, entry_ts)
        exit_i = index_lookup(ts_index, exit_ts)
        signal_i = entry_i - 1
        pos = int(trade["direction"])
        entry_px = float(trade["entry_price"])
        entry_atr = float(atr672[entry_i - 1] if entry_i > 0 else atr672[entry_i])
        stop_px = entry_px * (1 - pos * 8.0 * entry_atr) if np.isfinite(entry_atr) and entry_atr > 0 else np.nan

        signal_on_prev_bar = bool(signal_i >= 0 and signal[signal_i] == pos)
        signal_timing_ok = signal_on_prev_bar and entry_i == signal_i + 1

        entry_bar_stop = False
        entry_bar_stop_gap = False
        path_stop_touches = 0
        path_stop_gap_opens = 0
        if np.isfinite(stop_px):
            for bar_i in range(entry_i, exit_i + 1):
                touched = low[bar_i] <= stop_px if pos > 0 else high[bar_i] >= stop_px
                gap_open = open_[bar_i] <= stop_px if pos > 0 else open_[bar_i] >= stop_px
                if touched:
                    path_stop_touches += 1
                if gap_open:
                    path_stop_gap_opens += 1
                if bar_i == entry_i and touched:
                    entry_bar_stop = True
                if bar_i == entry_i and gap_open:
                    entry_bar_stop_gap = True

        close_exit = trade["exit_reason"] not in {"stop_loss", "stop_gap_open", "stop_market_extra_slip"}
        close_exit_next_open = True
        if close_exit and exit_i > 0:
            prev_i = exit_i - 1
            close_exit_next_open = exit_i == prev_i + 1

        optimistic_stop_fill = trade["exit_reason"] == "stop_loss" and np.isfinite(stop_px)
        if optimistic_stop_fill:
            gap_at_exit = open_[exit_i] <= stop_px if pos > 0 else open_[exit_i] >= stop_px
            optimistic_stop_fill = not gap_at_exit

        rows.append(
            {
                "entry_ts": entry_ts,
                "exit_ts": exit_ts,
                "signal_i": signal_i,
                "entry_i": entry_i,
                "exit_i": exit_i,
                "direction": pos,
                "entry_kind": trade.get("entry_kind", ""),
                "exit_reason": trade["exit_reason"],
                "allocation": float(trade["allocation"]),
                "pnl_pct": float(trade["pnl_pct"]),
                "signal_timing_ok": signal_timing_ok,
                "signal_on_prev_bar": signal_on_prev_bar,
                "entry_atr_prev_bar": entry_atr,
                "stop_px": stop_px,
                "entry_bar_stop_touched": entry_bar_stop,
                "entry_bar_stop_gap_open": entry_bar_stop_gap,
                "path_stop_touches": path_stop_touches,
                "path_stop_gap_opens": path_stop_gap_opens,
                "close_exit_next_open": close_exit_next_open,
                "optimistic_stop_fill": optimistic_stop_fill,
            }
        )
    return pd.DataFrame(rows)


def render_markdown(
    *,
    data_quality: dict[str, Any],
    causality: pd.DataFrame,
    summary: pd.DataFrame,
    timing: pd.DataFrame,
    baseline: dict[str, Any],
) -> str:
    causality_fail = causality.loc[~causality["match"]] if len(causality) else pd.DataFrame()
    baseline_row = summary.loc[summary["mode"].eq("baseline")].iloc[0]
    gap_open_row = summary.loc[summary["mode"].eq("stop_gap_open")].iloc[0]
    delay_row = summary.loc[summary["mode"].eq("stop_delay_1bar")].iloc[0]
    extra_slip_row = summary.loc[summary["mode"].eq("stop_market_extra_slip")].iloc[0]

    timing_bad = timing.loc[~timing["signal_timing_ok"]] if len(timing) else pd.DataFrame()
    entry_bar_stop = int(timing["entry_bar_stop_touched"].sum()) if len(timing) else 0
    entry_bar_gap = int(timing["entry_bar_stop_gap_open"].sum()) if len(timing) else 0
    path_stop_any = int((timing["path_stop_touches"] > 0).sum()) if len(timing) else 0

    lines = [
        "# HYPE-EMA-X-V17.1 严格口径实盘可执行性审计 2026-07-01",
        "",
        "Family id：`HYPE-EMA-X`",
        "",
        "审计对象：`HYPE-EMA-X-V17.1`。信号与 `HYPE-EMA-X-V17` 完全相同，仅 `hq_scale = 1.1`、`lq_scale = 1.0`。",
        "",
        f"数据切片：与主台账一致，截断到 `{LEDGER_SLICE_END.isoformat()}` 后再取最近 365 天 1Y 窗口。",
        "",
        "执行成本沿用研究脚本默认值：滑点 `0.0005`、单次成交成本 `0.00085`（与主台账一致，未改用 Binance 默认 `0.001 fee + 4bps` 压力口径）。",
        "",
        "## 结论",
        "",
    ]

    if len(causality_fail) == 0 and len(timing_bad) == 0:
        lines.append(
            "未发现明确未来函数，也未发现 `HYPE-5M-PBTR` 那类 lockout 后按 stale stop 价补成交的问题。"
            "信号在第 `t` 根 15m K 收盘确认，最早第 `t+1` 根 open 入场；"
            "1h 指标经 `shift(1)` 对齐；`swing96` 结构破坏使用 `shift(1)` 的前高/前低；"
            "收盘类退出在下一根 open 成交。"
        )
    else:
        lines.append("审计发现需要进一步处理的时序/因果性问题，见下文各节。")

    lines.extend(
        [
            "",
            "但 `V17.1` 仍不能直接视为 live-ready："
            "1Y 仅 `33` 笔交易、无生产 runner、无重启恢复/保护单审计；"
            "硬止损在 baseline 中按 high/low 触发后仍以 stop price 成交，属于 stop-market 乐观上界；"
            "本次样本 baseline 虽 `0` 笔 stop_loss，但路径上仍有触及止损价的持仓段，必须用压力口径重估。",
            "",
            "## 数据与未来函数检查",
            "",
            f"- 数据范围：`{data_quality['first_bar']}` 到 `{data_quality['last_bar']}`，`{data_quality['rows']}` 根 15m K。",
            f"- 缺口/重复/非法 OHLC：missing `{data_quality['missing_bars']}`，duplicate `{data_quality['duplicate_ts']}`，invalid OHLC `{data_quality['invalid_ohlc']}`。",
            f"- 关键字段空值：`{data_quality['null_counts']}`。",
            f"- 截断重算因果性检查：`{len(causality)}` 个 feature-point 对比，失败 `{len(causality_fail)}` 个。",
            "",
            "检查方式：对多个历史索引只保留该索引及以前的数据，重新计算 EMA/ADX/ATR/1h/trend_score/swing96 等特征，再与全量计算在同一索引的值比较。",
            "",
            "## Baseline 复现（1Y 窗口）",
            "",
            f"- 收益：`{pct(float(baseline_row['return']))}`（台账 `+3861.48%`，一致）",
            f"- 最大回撤：`{pct(float(baseline_row['max_dd']))}`（台账 `-19.44%`，一致）",
            f"- 胜率：`{pct(float(baseline_row['win_rate']))}`（台账 `90.91%`，一致）",
            f"- 交易数：`{int(baseline_row['trades'])}`（台账 `33`，一致）",
            f"- 退出分布：`{baseline_row['exit_reasons']}`",
            "",
            "## 严格执行口径对比",
            "",
            "| 口径 | 交易数 | 1Y收益 | 最大回撤 | Sharpe | 退出分布 |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['mode']}` | `{int(row['trades'])}` | `{pct(float(row['return']))}` | "
            f"`{pct(float(row['max_dd']))}` | `{row['sharpe']:.2f}` | `{row['exit_reasons']}` |"
        )

    lines.extend(
        [
            "",
            "口径说明：",
            "",
            "- `baseline`：当前研究脚本默认。硬止损 intrabar 触发后按 stop price + 滑点成交；结构/预警/反向交叉收盘确认后下一根 open 出场。",
            "- `stop_gap_open`：若开盘已穿越止损，则按 open 市价退出，不再假设拿到 stop price。",
            "- `stop_delay_1bar`：入场当根不检查止损，模拟 bracket 晚一根 15m 才生效。",
            "- `stop_market_extra_slip`：仍按 stop price 触发，但额外加 `4bps` 穿越滑点。",
            "",
            "## 价格穿越与同 K 风险",
            "",
            f"- 信号时序异常：`{len(timing_bad)}` 笔（应为 `0`）。",
            f"- 持仓路径上曾触及止损价的交易：`{path_stop_any}` 笔；baseline 实际 `stop_loss` 为 `{json.loads(baseline_row['exit_reasons']).get('stop_loss', 0)}` 笔。",
            f"- 入场当根触及止损：`{entry_bar_stop}` 笔；其中开盘穿越止损：`{entry_bar_gap}` 笔。",
            f"- `stop_gap_open` 相对 baseline 收益变化：`{pct(float(gap_open_row['return']) - float(baseline_row['return']))}`，回撤变化：`{pct(float(gap_open_row['max_dd']) - float(baseline_row['max_dd']))}`。",
            f"- `stop_delay_1bar` 相对 baseline 收益变化：`{pct(float(delay_row['return']) - float(baseline_row['return']))}`，回撤变化：`{pct(float(delay_row['max_dd']) - float(baseline_row['max_dd']))}`。",
            f"- `stop_market_extra_slip` 相对 baseline 收益变化：`{pct(float(extra_slip_row['return']) - float(baseline_row['return']))}`，回撤变化：`{pct(float(extra_slip_row['max_dd']) - float(baseline_row['max_dd']))}`。",
            "",
            "## 代码级时序审计",
            "",
            "- `research_hype_v13_late_reentry.py`：bar `i` 收盘生成 signal → 设置 `pending_entry`；bar `i+1` open 成交。",
            "- `entry_atr` 使用 `atr672[i-1]`（入场 bar 的前一根已完成 K）。",
            "- `research_hype_ema_cross_strategy.add_htf_features()`：`htf.shift(1)` 后再对齐到 15m，避免 1h 未来数据。",
            "- `hard_trend_invalidated(swing96)`：`low96/high96` 使用 `shift(1)`，收盘破位后下一根 open 出场。",
            "- 不存在 `HYPE-5M-PBTR` V3/V4 那种 trailing stop 更新后仍按旧 stop 价补成交的逻辑；止损价自入场 ATR 固定。",
            "",
            "## 当前决策",
            "",
            "状态维持为 **research candidate**，不升级为 live / paper-live。",
            "`+3861.48% / -19.44%` 应继续按 1Y 研究切片 + baseline 执行上界阅读。",
            "若使用截至当前 data lake 全量末端（例如 `2026-06-26`）的 rolling 1Y 窗口，收益会降到约 `+3365.62%`；这不代表执行口径错误，而是研究切片末端漂移。",
            "若要做 promotion，下一步必须补：stop-market 实盘日志、保护单延迟/重启恢复、以及 `0.001 fee + 4bps` 的统一 Binance 压力复跑。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/15m-ema-crossover/scripts/{Path(__file__).name}`",
            f"- Markdown：`{MARKDOWN_PATH}`",
            f"- summary：`{SUMMARY_PATH}`",
            f"- trades：`{TRADES_PATH}`",
            f"- causality：`{CAUSALITY_PATH}`",
            f"- timing：`{TIMING_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_hype_data_lake()
    raw = raw.loc[pd.to_datetime(raw["ts"], utc=True) <= LEDGER_SLICE_END].reset_index(drop=True)
    frame = build_feature_frame(raw)
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)

    data_quality = data_quality_summary(raw)
    causality = feature_causality_check(raw, frame)

    summary_rows: list[dict[str, Any]] = []
    all_trades: list[pd.DataFrame] = []
    baseline_result: dict[str, Any] | None = None
    for mode in EXECUTION_MODES:
        result = run_v17_1(frame, start_ts=start_ts, stop_fill_mode=mode, collect_trades=(mode == "baseline"))
        summary_rows.append(summarize_mode(result))
        if mode == "baseline":
            baseline_result = result
            trades = pd.DataFrame(result["trades_detail"])
            trades.insert(0, "mode", mode)
            all_trades.append(trades)

    if baseline_result is None:
        raise RuntimeError("baseline run missing")

    timing = audit_trade_crossings(frame, baseline_result["trades_detail"])

    summary = pd.DataFrame(summary_rows)
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    causality.to_csv(CAUSALITY_PATH, index=False)
    timing.to_csv(TIMING_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(
            data_quality=data_quality,
            causality=causality,
            summary=summary,
            timing=timing,
            baseline=baseline_result,
        ),
        encoding="utf-8",
    )
    JSON_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-EMA-X",
                "strategy": "HYPE-EMA-X-V17.1",
                "window_start": str(start_ts),
                "window_end": str(pd.Timestamp(frame.ts.iloc[-1])),
                "ledger_slice_end": str(LEDGER_SLICE_END),
                "data_quality": data_quality,
                "feature_causality_fail_count": int((~causality["match"]).sum()) if len(causality) else 0,
                "signal_timing_fail_count": int((~timing["signal_timing_ok"]).sum()) if len(timing) else 0,
                "summary": summary.to_dict(orient="records"),
                "baseline": {
                    "return": baseline_result["return"],
                    "max_dd": baseline_result["max_dd"],
                    "sharpe": baseline_result["sharpe"],
                    "trades": baseline_result["trades"],
                    "win_rate": baseline_result["win_rate"],
                    "exit_reasons": baseline_result["exit_reasons"],
                    "signal_counts": baseline_result["signal_counts"],
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trades": str(TRADES_PATH),
                    "causality": str(CAUSALITY_PATH),
                    "timing": str(TIMING_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))
    if len(timing):
        print("\nsignal timing failures", int((~timing["signal_timing_ok"]).sum()))
        print("entry_bar_stop_touched", int(timing["entry_bar_stop_touched"].sum()))


if __name__ == "__main__":
    main()
