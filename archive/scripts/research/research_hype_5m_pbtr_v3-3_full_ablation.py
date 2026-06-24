from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade
from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
)
from research_hype_5m_pbtr_v3_ablation_audit import month_slices
from research_hype_5m_positive_payoff_search import load_all_hype_5m


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("reports/hype_5m_pbtr_v3-3_full_ablation.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v3-3_full_ablation_summary.csv")
SLICES_PATH = Path("reports/hype_5m_pbtr_v3-3_full_ablation_validation_slices.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v3-3_full_ablation_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v3-3_full_ablation_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v3-3_full_ablation_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/ablations/"
    "hype-5m-pbtr-v3-3-full-parameter-ablation-2026-06-24.md"
)


@dataclass(frozen=True, slots=True)
class V33Config:
    strategy_name: str = "HYPE-5M-PBTR-V3.3"
    timeframe: str = "5m"
    ema_fast: int = 21
    ema_slow: int = 96
    pullback_buffer: float = 0.01
    stop_atr: float = 0.5
    trail_atr: float = 0.75
    min_hold_bars: int = 9


V33_CONFIG = V33Config()


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "neg").replace("/", "_")


def add_minimal_features(frame: pd.DataFrame, cfg: V33Config) -> pd.DataFrame:
    result = frame.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    result[f"ema{cfg.ema_fast}"] = close.ewm(span=cfg.ema_fast, adjust=False, min_periods=cfg.ema_fast).mean()
    result[f"ema{cfg.ema_slow}"] = close.ewm(span=cfg.ema_slow, adjust=False, min_periods=cfg.ema_slow).mean()
    result["atr14"] = tr.rolling(14, min_periods=14).mean()
    return result


def build_signal(frame: pd.DataFrame, cfg: V33Config) -> np.ndarray:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    atr14 = frame["atr14"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    touched = np.where(direction > 0, low <= ema_fast * (1.0 + cfg.pullback_buffer), high >= ema_fast * (1.0 - cfg.pullback_buffer))
    reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
    candle = np.where(direction > 0, close > open_, close < open_)
    mask = (direction != 0) & touched & reclaimed & candle & np.isfinite(atr14)
    mask = np.nan_to_num(mask, nan=False).astype(bool)
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[mask] = direction[mask]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def simulate_trades(frame: pd.DataFrame, signal: np.ndarray, cfg: V33Config) -> list[Trade]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        atr_value = float(atr[sig_i])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        stop_price = entry_price - direction * cfg.stop_atr * atr_value
        sl = slice(entry_i, n)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        atr_seg = atr[sl]

        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            stop_levels = np.maximum(np.full(len(high_seg), stop_price), prev_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.minimum(np.full(len(low_seg), stop_price), prev_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels

        if cfg.min_hold_bars > 0:
            stop_hit[: cfg.min_hold_bars] = False
        hit_idx = np.flatnonzero(stop_hit)
        if len(hit_idx):
            offset = int(hit_idx[0])
            reason = "stop"
            raw_exit_price = float(stop_levels[offset])
        else:
            offset = len(close_seg) - 1
            reason = "time"
            raw_exit_price = float(close_seg[offset])

        path_high = high_seg[: offset + 1]
        path_low = low_seg[: offset + 1]
        if direction > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))

        exit_i = entry_i + offset
        exit_price = float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))
        gross = direction * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        trades.append(
            Trade(
                config=cfg.strategy_name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i
    return trades


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {
            "label": "baseline_v33",
            "family": "baseline",
            "parameter": "baseline",
            "value": "V3.3",
            "cfg": V33_CONFIG,
        }
    ]

    def add(parameter: str, value: Any, *, family: str = "single_parameter", **changes: Any) -> None:
        variants.append(
            {
                "label": f"{parameter}_{label_value(value)}",
                "family": family,
                "parameter": parameter,
                "value": value,
                "cfg": replace(V33_CONFIG, **changes),
            }
        )

    for value in (9, 13, 34, 55):
        add("ema_fast", value, family="trend_definition", ema_fast=value)
    for value in (55, 72, 144, 192, 384):
        add("ema_slow", value, family="trend_definition", ema_slow=value)
    for fast, slow in ((13, 72), (34, 144), (55, 192), (96, 384)):
        add("ema_pair", f"{fast}/{slow}", family="trend_definition", ema_fast=fast, ema_slow=slow)
    for value in (0.0, 0.0025, 0.005, 0.02, 0.03):
        add("pullback_buffer", value, family="entry_logic", pullback_buffer=value)
    for value in (0.25, 0.75, 1.0, 1.5, 99.0):
        add("stop_atr", value, family="exit_risk", stop_atr=value)
    for value in (0.0, 0.5, 1.0, 1.5, 2.0):
        add("trail_atr", value, family="exit_risk", trail_atr=value)
    for value in (0, 3, 6, 12, 18, 24):
        add("min_hold_bars", value, family="exit_risk", min_hold_bars=value)
    return variants


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    cuts = [
        ("full", start, end),
        ("2025_05_30_to_2025_09_01", start, pd.Timestamp("2025-09-01T00:00:00Z")),
        ("2025_09_01_to_2025_12_01", pd.Timestamp("2025-09-01T00:00:00Z"), pd.Timestamp("2025-12-01T00:00:00Z")),
        ("2025_12_01_to_2026_03_01", pd.Timestamp("2025-12-01T00:00:00Z"), pd.Timestamp("2026-03-01T00:00:00Z")),
        ("2026_03_01_to_2026_06_01", pd.Timestamp("2026-03-01T00:00:00Z"), pd.Timestamp("2026-06-01T00:00:00Z")),
        ("2026_06_01_to_2026_06_23", pd.Timestamp("2026-06-01T00:00:00Z"), end),
    ]
    return [{"name": name, "start": slice_start, "end": slice_end} for name, slice_start, slice_end in cuts]


def evaluate_variant(raw: pd.DataFrame, slices: list[dict[str, Any]], spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade], np.ndarray, pd.DataFrame]:
    cfg = spec["cfg"]
    frame = add_minimal_features(raw, cfg)
    signal = build_signal(frame, cfg)
    trades = simulate_trades(frame, signal, cfg)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    full_metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    summary = {
        "label": spec["label"],
        "family": spec["family"],
        "parameter": spec["parameter"],
        "value": spec["value"],
        "signal_count": int(np.count_nonzero(signal)),
        "trade_count": int(len(trades)),
        **{f"full_{key}": value for key, value in full_metrics.items()},
        **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
    }
    slice_rows: list[dict[str, Any]] = []
    min_win = 1.0
    min_pf = float("inf")
    worst_dd = 0.0
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        slice_rows.append({"label": spec["label"], "family": spec["family"], "parameter": spec["parameter"], "value": spec["value"], "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
        min_win = min(min_win, float(metrics["win_rate"]))
        min_pf = min(min_pf, float(metrics["profit_factor"]))
        worst_dd = min(worst_dd, float(metrics["max_dd"]))
    summary["min_slice_win_rate"] = min_win
    summary["min_slice_profit_factor"] = min_pf
    summary["worst_slice_max_dd"] = worst_dd
    return summary, slice_rows, trades, signal, frame


def baseline_time_slices(frame: pd.DataFrame, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling = pd.DataFrame([{"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in rolling_windows(frame)])
    weekly = pd.DataFrame([{"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in weekly_slices(frame)])
    monthly = pd.DataFrame([{"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in month_slices(frame)])
    return rolling, weekly, monthly


def row_for(summary: pd.DataFrame, label: str) -> pd.Series:
    return summary.loc[summary["label"].eq(label)].iloc[0]


def render_variant_table(rows: pd.DataFrame) -> list[str]:
    lines = ["| 变体 | 参数 | 值 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | Δ累计收益 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows.to_dict(orient="records"):
        lines.append(f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | `{int(row['full_trades'])}` | `{mult(float(row['full_annualized_multiple']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_profit_factor']))}` | `{num(float(row['full_payoff_ratio']))}` | `{pct(float(row['full_max_dd']))}` | `{pct(float(row['delta_full_total_return']))}` |")
    return lines


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = row_for(summary, "baseline_v33")
    variants = summary.loc[~summary["label"].eq("baseline_v33")].copy()
    ranked_bad = variants.sort_values("delta_full_total_return").head(12)
    ranked_good = variants.sort_values("delta_full_total_return", ascending=False).head(12)
    grouped_best = variants.sort_values("delta_full_total_return", ascending=False).groupby("parameter", sort=False).head(1)
    worst_week = weekly.sort_values("total_return").iloc[0]
    best_week = weekly.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly.sort_values("total_return").iloc[0]
    best_month = monthly.sort_values("total_return", ascending=False).iloc[0]

    no_trail = row_for(summary, "trail_atr_0p0")
    no_hold = row_for(summary, "min_hold_bars_0")
    tight_trail = row_for(summary, "trail_atr_0p5")
    hold_12 = row_for(summary, "min_hold_bars_12")
    stop_025 = row_for(summary, "stop_atr_0p25")

    lines = [
        "# HYPE-5M-PBTR-V3.3 全参数消融 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告以 `HYPE-5M-PBTR-V3.3` 为 baseline，只对 6 个有效策略参数做单因子消融。已从 V3.3 删除的兼容/关闭/保护参数不再作为参数测试对象。",
        "",
        "## 基线",
        "",
        "| 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{int(baseline['full_trades'])}` | `{mult(float(baseline['full_annualized_multiple']))}` | `{pct(float(baseline['full_total_return']))}` | `{pct(float(baseline['full_win_rate']))}` | `{num(float(baseline['full_payoff_ratio']))}` | `{num(float(baseline['full_profit_factor']))}` | `{pct(float(baseline['full_max_dd']))}` |",
        "",
        "## 伤害最大的改动",
        "",
        *render_variant_table(ranked_bad),
        "",
        "## 样本内改善最大的改动",
        "",
        *render_variant_table(ranked_good),
        "",
        "## 每个参数的最佳单因子结果",
        "",
        *render_variant_table(grouped_best),
        "",
        "## 核心参数判断",
        "",
        f"- `trail_atr` 是最核心退出参数：`trail_atr=0` 后交易数 `{int(no_trail['full_trades'])}`，PF `{num(float(no_trail['full_profit_factor']))}`，最大回撤 `{pct(float(no_trail['full_max_dd']))}`。",
        f"- `min_hold_bars` 仍是核心路径参数：`min_hold_bars=0` 后交易数 `{int(no_hold['full_trades'])}`，PF `{num(float(no_hold['full_profit_factor']))}`，最大回撤 `{pct(float(no_hold['full_max_dd']))}`。",
        f"- 当前样本里 `trail_atr=0.5` 是最强单因子收益增强之一：年化 `{mult(float(tight_trail['full_annualized_multiple']))}`，PF `{num(float(tight_trail['full_profit_factor']))}`，最大回撤 `{pct(float(tight_trail['full_max_dd']))}`。",
        f"- 当前样本里 `min_hold_bars=12` 继续增强收益：年化 `{mult(float(hold_12['full_annualized_multiple']))}`，PF `{num(float(hold_12['full_profit_factor']))}`，最大回撤 `{pct(float(hold_12['full_max_dd']))}`。",
        f"- 当前样本里 `stop_atr=0.25` 也增强收益，但这是更紧初始止损：年化 `{mult(float(stop_025['full_annualized_multiple']))}`，最大回撤 `{pct(float(stop_025['full_max_dd']))}`，需要 paper-live 验证是否更容易被噪声扫掉。",
        "",
        "## V3.3 时间切片",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rolling.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "周/月摘要：",
            "",
            f"- 周数：`{len(weekly)}`，盈利周 `{int((weekly['total_return'] > 0).sum())}/{len(weekly)}`，中位周收益 `{pct(float(weekly['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`；最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            f"- 月数：`{len(monthly)}`，盈利月 `{int((monthly['total_return'] > 0).sum())}/{len(monthly)}`，中位月收益 `{pct(float(monthly['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 结论",
            "",
            "V3.3 的 6 个参数都是真正参与行为的参数，不能再像 V3.2 中的兼容项那样直接删除。消融显示，`EMA21/EMA96 + pullback_buffer` 决定入场样本，`min_hold_bars + trail_atr` 决定收益路径，`stop_atr` 决定初始容错。",
            "",
            "`trail_atr=0.5`、`min_hold_bars=12`、`stop_atr=0.25` 在样本内继续给出更高收益，但它们都属于退出路径更激进/更紧的优化方向，不能仅凭单次样本内消融直接替代 V3.3。下一步若要升级，应把这些作为 `V3.4` 候选组合做组合消融、成本压力和 paper-live 对照。",
            "",
            "## 产物",
            "",
            f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v3-3_full_ablation.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 验证切片 CSV：`{SLICES_PATH}`",
            f"- 滚动切片 CSV：`{ROLLING_PATH}`",
            f"- 周切片 CSV：`{WEEKLY_PATH}`",
            f"- 月切片 CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    slices = validation_slices(raw)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    baseline_trades: list[Trade] = []
    baseline_frame: pd.DataFrame | None = None
    for spec in build_variants():
        summary, rows, trades, _signal, frame = evaluate_variant(raw, slices, spec)
        summary_rows.append(summary)
        slice_rows.extend(rows)
        if spec["label"] == "baseline_v33":
            baseline_trades = trades
            baseline_frame = frame

    summary_df = pd.DataFrame(summary_rows)
    baseline = summary_df.loc[summary_df["label"].eq("baseline_v33")].iloc[0]
    for column in ("full_total_return", "full_annualized_multiple", "full_equity_multiple", "full_max_dd", "full_win_rate", "full_profit_factor", "full_payoff_ratio"):
        summary_df[f"delta_{column}"] = summary_df[column] - baseline[column]
    slices_df = pd.DataFrame(slice_rows)
    if baseline_frame is None:
        raise RuntimeError("baseline frame was not captured")
    rolling_df, weekly_df, monthly_df = baseline_time_slices(baseline_frame, baseline_trades)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(SUMMARY_PATH, index=False)
    slices_df.to_csv(SLICES_PATH, index=False)
    rolling_df.to_csv(ROLLING_PATH, index=False)
    weekly_df.to_csv(WEEKLY_PATH, index=False)
    monthly_df.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary_df, rolling_df, weekly_df, monthly_df), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3",
                "definition": asdict(V33_CONFIG),
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "validation_slices": str(SLICES_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary_df.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary_df.sort_values("delta_full_total_return", ascending=False).head(12)[["label", "full_trades", "full_annualized_multiple", "full_win_rate", "full_profit_factor", "full_max_dd", "delta_full_total_return"]].to_string(index=False))


if __name__ == "__main__":
    main()
