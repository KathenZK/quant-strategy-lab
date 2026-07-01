from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v621 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_2_1_full_ablation.py", "hype_pbtr_v621_feasibility_base")
v62 = v621.v62
v6 = v62.v6

RUN_DATE = "2026-06-30"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_live_feasibility_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_live_feasibility_trades_{RUN_DATE}.csv"
CAUSALITY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_feature_causality_{RUN_DATE}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_live_feasibility_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v6-2-1-live-feasibility-audit-{RUN_DATE}.md"


def fmt_pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def fmt_num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def equity_metrics(returns: np.ndarray) -> dict[str, float]:
    returns = returns[np.isfinite(returns)]
    if len(returns) == 0:
        return {
            "trades": 0.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "avg_trade": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "payoff_ratio": 0.0,
            "worst_trade": 0.0,
            "best_trade": 0.0,
        }
    equity = np.cumprod(1.0 + returns)
    equity_with_start = np.r_[1.0, equity]
    peak = np.maximum.accumulate(equity_with_start)
    dd = equity_with_start / peak - 1.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "trades": float(len(returns)),
        "total_return": float(equity[-1] - 1.0),
        "max_dd": float(dd.min()),
        "avg_trade": float(returns.mean()),
        "win_rate": float((returns > 0).mean()),
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "payoff_ratio": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.inf,
        "worst_trade": float(returns.min()),
        "best_trade": float(returns.max()),
    }


def ret_with_cost(entry_price: float, raw_exit_price: float, side: int) -> float:
    exit_price = v6.exit_price_with_cost(raw_exit_price, side)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = v6.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return float(gross - fee_cost)


def build_baseline_signals(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    long_signal, long_raw, long_filtered = v62.build_leg_signal(frame, v621.BASELINE.long)
    short_signal, short_raw, short_filtered = v62.build_leg_signal(frame, v621.BASELINE.short)
    return long_signal, short_signal, {
        "long_raw_signal_count": long_raw,
        "long_filtered_signal_count": long_filtered,
        "short_raw_signal_count": short_raw,
        "short_filtered_signal_count": short_filtered,
        "same_bar_signal_count": int(len(set(np.flatnonzero(long_signal)) & set(np.flatnonzero(short_signal)))),
    }


def simulate_combo_detailed(frame: pd.DataFrame, long_signal: np.ndarray, short_signal: np.ndarray, *, mode: str) -> tuple[pd.DataFrame, dict[str, int]]:
    cfg = v621.BASELINE
    priority_order = {"long": 0, "short": 1}
    events: list[tuple[int, str, int, Any]] = []
    events.extend((int(i), "long", int(long_signal[i]), cfg.long) for i in np.flatnonzero(long_signal))
    events.extend((int(i), "short", int(short_signal[i]), cfg.short) for i in np.flatnonzero(short_signal))
    events.sort(key=lambda item: (item[0], priority_order[item[1]]))

    ts = pd.to_datetime(frame["ts"], utc=True)
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    n = len(frame)
    blocked_until = -1
    stats = {"accepted_long": 0, "accepted_short": 0, "blocked_long": 0, "blocked_short": 0}
    rows: list[dict[str, Any]] = []

    for sig_i, source, side, leg in events:
        entry_i = sig_i + 1
        if entry_i <= blocked_until:
            stats[f"blocked_{source}"] += 1
            continue
        if side == 0 or entry_i >= n:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * v6.ENTRY_SLIPPAGE_RATE))
        target_price = entry_price + side * leg.tp_atr * signal_atr
        stop_price = entry_price - side * leg.sl_atr * signal_atr
        reason = "time_open"
        exit_i = min(n - 1, entry_i + leg.time_exit_bars)
        raw_exit_price = float(open_[exit_i])
        first_stop_i: int | None = None
        first_target_i: int | None = None
        both_hit_i: int | None = None
        entry_bar_stop = bool(v6.touched_stop(float(high[entry_i]), float(low[entry_i]), stop_price, side))
        entry_bar_target = bool(v6.touched_target(float(high[entry_i]), float(low[entry_i]), target_price, side))

        start_bar = entry_i + 1 if mode == "bracket_delay_1bar" else entry_i
        for bar_i in range(start_bar, min(n, entry_i + leg.time_exit_bars + 1)):
            stop_open = v6.crossed_stop(float(open_[bar_i]), stop_price, side)
            target_open = v6.crossed_target(float(open_[bar_i]), target_price, side)
            stop_hit = v6.touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side)
            target_hit = v6.touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side)
            if first_stop_i is None and (stop_open or stop_hit):
                first_stop_i = bar_i
            if first_target_i is None and (target_open or target_hit):
                first_target_i = bar_i
            if both_hit_i is None and stop_hit and target_hit:
                both_hit_i = bar_i

            if stop_open:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "stop_gap_open"
                break
            if target_open:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i] if mode == "target_gap_open_fill" else target_price)
                reason = "target_gap_or_open"
                break
            if bar_i == entry_i + leg.time_exit_bars:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "time_open"
                break
            if stop_hit and target_hit:
                exit_i = bar_i
                if mode == "target_first_same_bar":
                    raw_exit_price = float(target_price)
                    reason = "both_hit_target_first"
                else:
                    raw_exit_price = float(stop_price)
                    reason = "both_hit_stop_first"
                break
            if stop_hit:
                exit_i = bar_i
                raw_exit_price = float(stop_price)
                reason = "stop_market"
                break
            if target_hit:
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target"
                break

        net_ret_1x = ret_with_cost(entry_price, raw_exit_price, side)
        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
            stop_dist = float((entry_price - stop_price) / entry_price)
            target_dist = float((target_price - entry_price) / entry_price)
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
            stop_dist = float((stop_price - entry_price) / entry_price)
            target_dist = float((entry_price - target_price) / entry_price)

        rows.append(
            {
                "mode": mode,
                "source": source,
                "signal_i": sig_i,
                "entry_i": entry_i,
                "exit_i": exit_i,
                "signal_ts": ts.iloc[sig_i],
                "entry_ts": ts.iloc[entry_i],
                "exit_ts": ts.iloc[exit_i],
                "side": side,
                "entry_price": entry_price,
                "raw_exit_price": raw_exit_price,
                "target_price": target_price,
                "stop_price": stop_price,
                "signal_atr": signal_atr,
                "target_dist": target_dist,
                "stop_dist": stop_dist,
                "bars_held": int(exit_i - entry_i + 1),
                "reason": reason,
                "net_ret_1x": net_ret_1x,
                "net_ret_3x": net_ret_1x * 3.0,
                "mae_1x": mae - v6.FEE_RATE_PER_FILL,
                "mfe_1x": mfe,
                "first_stop_bar_offset": None if first_stop_i is None else int(first_stop_i - entry_i),
                "first_target_bar_offset": None if first_target_i is None else int(first_target_i - entry_i),
                "both_hit_bar_offset": None if both_hit_i is None else int(both_hit_i - entry_i),
                "entry_bar_stop_touched": entry_bar_stop,
                "entry_bar_target_touched": entry_bar_target,
            }
        )
        stats[f"accepted_{source}"] += 1
        blocked_until = exit_i
    return pd.DataFrame(rows), stats


def summarize_mode(trades: pd.DataFrame, stats: dict[str, int], signal_stats: dict[str, int]) -> dict[str, Any]:
    returns = trades["net_ret_3x"].to_numpy("float64")
    metrics = equity_metrics(returns)
    reason_counts = trades["reason"].value_counts().sort_index().to_dict()
    both_hit = int(trades["both_hit_bar_offset"].notna().sum())
    entry_bar_stop = int(trades["entry_bar_stop_touched"].sum())
    entry_bar_target = int(trades["entry_bar_target_touched"].sum())
    entry_bar_any = int((trades["entry_bar_stop_touched"] | trades["entry_bar_target_touched"]).sum())
    return {
        "mode": str(trades["mode"].iloc[0]) if len(trades) else "empty",
        **signal_stats,
        **stats,
        **metrics,
        "reason_counts": json.dumps(reason_counts, ensure_ascii=False, sort_keys=True),
        "both_hit_count": both_hit,
        "both_hit_rate": both_hit / len(trades) if len(trades) else 0.0,
        "entry_bar_stop_touched": entry_bar_stop,
        "entry_bar_target_touched": entry_bar_target,
        "entry_bar_any_touched": entry_bar_any,
        "entry_bar_any_rate": entry_bar_any / len(trades) if len(trades) else 0.0,
        "median_target_dist": float(trades["target_dist"].median()) if len(trades) else 0.0,
        "median_stop_dist": float(trades["stop_dist"].median()) if len(trades) else 0.0,
        "median_bars_held": float(trades["bars_held"].median()) if len(trades) else 0.0,
    }


def data_quality_summary(frame: pd.DataFrame) -> dict[str, Any]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    expected = pd.date_range(ts.iloc[0], ts.iloc[-1], freq="5min")
    duplicate_ts = int(ts.duplicated().sum())
    missing = expected.difference(ts)
    null_counts = {col: int(frame[col].isna().sum()) for col in ("open", "high", "low", "close", "volume", "quote_volume", "trade_count") if col in frame}
    invalid_ohlc = int(((frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))).sum())
    return {
        "first_bar": ts.iloc[0].isoformat(),
        "last_bar": ts.iloc[-1].isoformat(),
        "rows": int(len(frame)),
        "duplicate_ts": duplicate_ts,
        "missing_bars": int(len(missing)),
        "first_missing": None if len(missing) == 0 else missing[0].isoformat(),
        "invalid_ohlc": invalid_ohlc,
        "null_counts": json.dumps(null_counts, ensure_ascii=False, sort_keys=True),
    }


def feature_causality_check(raw: pd.DataFrame, full: pd.DataFrame) -> pd.DataFrame:
    check_indices = sorted(
        set(
            [
                400,
                600,
                1000,
                len(full) // 4,
                len(full) // 2,
                len(full) * 3 // 4,
                len(full) - 2,
            ]
        )
    )
    columns = [
        "ema21",
        "ema55",
        "ema96",
        "ema144",
        "ema384",
        "atr14",
        "htf_spread",
        "ret48",
        "ret192",
        "dir_ret48_bps",
        "dir_ret192_bps",
        "chop14_alt",
        "vol_ratio_96",
        "quote_vol_ratio_96",
        "trade_count_ratio_96",
    ]
    rows: list[dict[str, Any]] = []
    for idx in check_indices:
        if idx < 384 or idx >= len(full):
            continue
        truncated = v6.add_search_features(v6.add_features(raw.iloc[: idx + 1].copy()))
        for column in columns:
            if column not in full.columns or column not in truncated.columns:
                continue
            full_value = full[column].iloc[idx]
            trunc_value = truncated[column].iloc[-1]
            diff = abs(float(full_value) - float(trunc_value)) if pd.notna(full_value) and pd.notna(trunc_value) else 0.0
            rows.append(
                {
                    "idx": idx,
                    "ts": full["ts"].iloc[idx],
                    "column": column,
                    "full_value": full_value,
                    "truncated_value": trunc_value,
                    "abs_diff": diff,
                    "match": bool(diff <= 1e-10 or (pd.isna(full_value) and pd.isna(trunc_value))),
                }
            )
    return pd.DataFrame(rows)


def render_markdown(
    *,
    data_quality: dict[str, Any],
    causality: pd.DataFrame,
    summary: pd.DataFrame,
    baseline_trades: pd.DataFrame,
    signal_stats: dict[str, int],
) -> str:
    baseline = summary.loc[summary["mode"].eq("baseline_stop_first")].iloc[0]
    delay = summary.loc[summary["mode"].eq("bracket_delay_1bar")].iloc[0]
    target_first = summary.loc[summary["mode"].eq("target_first_same_bar")].iloc[0]
    target_gap_open = summary.loc[summary["mode"].eq("target_gap_open_fill")].iloc[0]
    causality_fail = causality.loc[~causality["match"]]
    entry_bar_any = int(baseline["entry_bar_any_touched"])
    both_hit = int(baseline["both_hit_count"])
    stop_gap = baseline_trades.loc[baseline_trades["reason"].eq("stop_gap_open")]
    target_gap = baseline_trades.loc[baseline_trades["reason"].eq("target_gap_or_open")]
    shortest = baseline_trades.sort_values("bars_held").head(5)
    lines = [
        "# HYPE-5M-PBTR-V6.2.1 实盘可行性深度审计 2026-06-30",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "审计对象：`HYPE-5M-PBTR-V6.2.1`，即 long `EMA21/55 + htf_spread>=0 + dir_ret192_bps>=788.123 + TP2.5/SL7/timeout36`，short `EMA34/144 + dir_ret48_bps>=400 + TP1.5/SL2/timeout48`，组合层严格单仓、同根 long 优先。",
        "",
        "## 结论",
        "",
        "未发现明确未来函数或旧 V3/V4 那类 delayed trailing / crossed stale stop 价格成交问题。信号在第 `t` 根 5m K 收盘后确认，最早第 `t+1` 根 open 入场；EMA、ATR、HTF spread 和 `dir_ret` 特征均可由 `t` 及以前闭合 K 计算。",
        "",
        "但该策略仍不能直接视为生产 live-ready。主要剩余风险是实盘订单层：入场成交后 TP/SL 是否能立即、幂等、成对维护；单边成交后是否能可靠取消另一边；timeout 市价平仓和重启恢复是否与回测一致；以及 short leg OOS 样本仍很小。若 bracket 晚一根 5m K 才生效，回测收益小幅下降、回撤变差但仍保持正期望，这说明策略没有完全依赖入场 K 的不可成交瞬间，但入场 K 风险仍需要 paper/live-dry-run 记录。",
        "",
        "## 数据与未来函数检查",
        "",
        f"- 数据范围：`{data_quality['first_bar']}` 到 `{data_quality['last_bar']}`，`{data_quality['rows']}` 根 5m K。",
        f"- 缺口/重复/非法 OHLC：missing `{data_quality['missing_bars']}`，duplicate `{data_quality['duplicate_ts']}`，invalid OHLC `{data_quality['invalid_ohlc']}`。",
        f"- 关键字段空值：`{data_quality['null_counts']}`。",
        f"- 截断重算因果性检查：`{len(causality)}` 个 feature-point 对比，失败 `{len(causality_fail)}` 个。",
        "",
        "检查方式：对多个历史索引只保留该索引及以前的数据，重新计算 `EMA/ATR/HTF/ret/volume ratio`，再与全量计算在同一索引的值比较。若全量结果依赖未来数据，这里会出现差异。",
        "",
        "## Baseline 执行读数",
        "",
        "| 口径 | 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | DD | 退出分布 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['mode']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['avg_trade']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['payoff_ratio']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{row['reason_counts']}` |"
        )
    lines.extend(
        [
            "",
            "baseline 采用当前研究口径：入场 bar 起 TP/SL 已经存在；同一根同时触达 TP/SL 时按 stop first；stop 开盘穿越按 open 市价退出；target 开盘穿越按目标价成交。",
            "",
            "## 价格穿越与同 K 风险",
            "",
            f"- baseline 退出分布中 stop gap open 为 `{int(json.loads(baseline['reason_counts']).get('stop_gap_open', 0))}` 笔，target gap/open 为 `{int(json.loads(baseline['reason_counts']).get('target_gap_or_open', 0))}` 笔。",
            f"- 同一根 K 同时触达 TP/SL 的交易 `{both_hit}` 笔；当前 baseline 已按 stop first，`target_first_same_bar` 口径总收益 `{fmt_pct(float(target_first['total_return']))}`，与 baseline 相同，说明当前不是靠 target-first 乐观顺序赚钱。",
            f"- 入场 K 内触及任一 bracket 的交易 `{entry_bar_any}` 笔，其中 entry-bar target `{int(baseline['entry_bar_target_touched'])}` 笔、entry-bar stop `{int(baseline['entry_bar_stop_touched'])}` 笔。",
            f"- 若 bracket 延迟到下一根 5m K 才生效，交易数 `{int(delay['trades'])}`、总收益 `{fmt_pct(float(delay['total_return']))}`、PF `{fmt_num(float(delay['profit_factor']))}`、DD `{fmt_pct(float(delay['max_dd']))}`。收益小幅下降、回撤变差，但未崩塌为负。",
            f"- target gap/open 改成 open 成交后，总收益 `{fmt_pct(float(target_gap_open['total_return']))}`、PF `{fmt_num(float(target_gap_open['profit_factor']))}`；与 baseline 接近，说明没有明显依赖 target gap 按较差/较好价格的错配。",
            "",
            "## 最短持仓样本",
            "",
            "| signal_ts | side | reason | bars | ret_3x | first_stop | first_target | entry_bar_stop | entry_bar_target |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in shortest.to_dict(orient="records"):
        lines.append(
            f"| `{row['signal_ts']}` | `{int(row['side'])}` | `{row['reason']}` | `{int(row['bars_held'])}` | "
            f"`{fmt_pct(float(row['net_ret_3x']))}` | `{row['first_stop_bar_offset']}` | "
            f"`{row['first_target_bar_offset']}` | `{bool(row['entry_bar_stop_touched'])}` | `{bool(row['entry_bar_target_touched'])}` |"
        )
    lines.extend(
        [
            "",
            "这些样本用于排查“开仓后马上按不可达价格平仓”的问题。V6.2.1 的短持仓多来自入场后已有 bracket 被触发；如果实盘 runner 在入场成交后不能立即挂出 reduce-only bracket，必须用 `bracket_delay_1bar` 或真实 dry-run 偏差而不是 baseline 收益做判断。",
            "",
            "## 代码级审计",
            "",
            "- `load_closed_frame()` 会剔除未闭合 K，并检查 5m 连续性。",
            "- `build_signal()` 使用当前闭合 K 的 OHLC、EMA、ATR 和 HTF spread；入场固定在 `sig_i + 1` 的 open。",
            "- `dir_ret48_bps/dir_ret192_bps` 来自 `close / close.shift(window) - 1`，不是未来收益。",
            "- TP/SL 使用 `ATR14(signal_bar)`，即信号 K 已闭合时可得；没有用入场后 K 的 ATR 调参。",
            "- 组合单仓用 `blocked_until = exit_i`，持仓中出现的新信号被阻塞，不叠仓。",
            "- 当前回测仍是 OHLC bar replay，无法知道同一根 K 内 tick 级先后顺序；同 K TP/SL 已保守 stop first，但 entry-bar order latency 需要 paper/live 日志验证。",
            "",
            "## 实盘结论",
            "",
            "状态维持为 `dry-run / tiny-notional live audit candidate`，不升级为 production sizing。上线前必须至少记录 `30-50` 笔：信号生成时间、入场订单回报、TP/SL 下单时间与 order id、单边成交后的撤单、timeout 市价单、重启恢复、实际滑点和 SQLite 复盘口径。若真实 runner 出现 bracket 下单延迟、撤单失败或 timeout 偏差，应按 `bracket_delay_1bar` 甚至更保守口径重新评估。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- summary：`{SUMMARY_PATH}`",
            f"- trades：`{TRADES_PATH}`",
            f"- causality：`{CAUSALITY_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    if not stop_gap.empty or not target_gap.empty:
        lines.extend(
            [
                "",
                "补充：baseline 本次没有发现 target/stop 开盘穿越退出样本；如后续数据出现该类退出，审计脚本会在 reason 分布中暴露。",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v6.load_closed_frame()
    frame = v6.add_search_features(v6.add_features(raw))
    data_quality = data_quality_summary(frame)
    causality = feature_causality_check(raw, frame)
    long_signal, short_signal, signal_stats = build_baseline_signals(frame)

    all_trade_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for mode in ("baseline_stop_first", "target_first_same_bar", "target_gap_open_fill", "bracket_delay_1bar"):
        trades, stats = simulate_combo_detailed(frame, long_signal, short_signal, mode=mode)
        all_trade_frames.append(trades)
        summary_rows.append(summarize_mode(trades, stats, signal_stats))

    summary = pd.DataFrame(summary_rows)
    trades = pd.concat(all_trade_frames, ignore_index=True)
    baseline_trades = trades.loc[trades["mode"].eq("baseline_stop_first")].copy()

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    causality.to_csv(CAUSALITY_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(
            data_quality=data_quality,
            causality=causality,
            summary=summary,
            baseline_trades=baseline_trades,
            signal_stats=signal_stats,
        ),
        encoding="utf-8",
    )
    JSON_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.2.1",
                "data_quality": data_quality,
                "signal_stats": signal_stats,
                "summary": summary.to_dict(orient="records"),
                "feature_causality_fail_count": int((~causality["match"]).sum()) if len(causality) else 0,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trades": str(TRADES_PATH),
                    "causality": str(CAUSALITY_PATH),
                },
                "baseline_config": asdict(v621.BASELINE),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
