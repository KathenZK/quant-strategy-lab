from __future__ import annotations

import json
import random
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal, random_config
from research_hype_5m_pbtr_v2_ablation_slices import metric_with_sides
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import ENTRY_SLIPPAGE_RATE, EXIT_SLIPPAGE_RATE, FEE_RATE_PER_FILL
from research_hype_5m_positive_payoff_search import load_all_hype_5m


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")
SEED = 20260625
MAX_RANDOM_CONFIGS = 12000
TOP_KEEP = 120

REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_executable_broad_search.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_executable_broad_search_summary.csv")
SLICES_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_executable_broad_search_slices.csv")
MONTHLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_executable_broad_search_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-executable-broad-search-2026-06-25.md"
)

TARGET_ANNUALIZED = 20.0
TARGET_WIN_RATE = 0.50
TARGET_MAX_DD = -0.20
MIN_FULL_TRADES = 100


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "is_2025_05_30_to_2026_03_01", "start": start, "end": pd.Timestamp("2026-03-01T00:00:00Z")},
        {
            "name": "val_2026_03_01_to_2026_06_01",
            "start": pd.Timestamp("2026-03-01T00:00:00Z"),
            "end": pd.Timestamp("2026-06-01T00:00:00Z"),
        },
        {"name": "fwd_2026_06_01_to_latest", "start": pd.Timestamp("2026-06-01T00:00:00Z"), "end": end},
        {"name": "recent_3m", "start": max(start, end - pd.Timedelta(days=90)), "end": end},
        {"name": "recent_1m", "start": max(start, end - pd.Timedelta(days=30)), "end": end},
    ]


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    boundaries = pd.date_range(start.floor("D").replace(day=1), end, freq="MS", tz="UTC")
    rows: list[dict[str, Any]] = []
    current = start
    for boundary in boundaries:
        if boundary <= start:
            continue
        rows.append({"name": current.strftime("%Y_%m"), "start": current, "end": min(boundary, end)})
        current = boundary
    if current < end:
        rows.append({"name": current.strftime("%Y_%m"), "start": current, "end": end})
    return rows


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return bool(open_price <= stop_price if side > 0 else open_price >= stop_price)


def touched_stop(high_price: float, low_price: float, stop_price: float, side: int) -> bool:
    return bool(low_price <= stop_price if side > 0 else high_price >= stop_price)


def crossed_target(open_price: float, target_price: float, side: int) -> bool:
    return bool(open_price >= target_price if side > 0 else open_price <= target_price)


def touched_target(high_price: float, low_price: float, target_price: float, side: int) -> bool:
    return bool(high_price >= target_price if side > 0 else low_price <= target_price)


def apply_exit_cost(raw_exit_price: float, side: int) -> float:
    return float(raw_exit_price * (1.0 - side * EXIT_SLIPPAGE_RATE))


def simulate_executable_bracket(frame: pd.DataFrame, signal: np.ndarray, cfg: SearchConfig) -> tuple[list[Trade], dict[str, int]]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    reason_counts: dict[str, int] = {}
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or side == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        active_stop = entry_price - side * cfg.stop_atr * signal_atr
        target_price = entry_price + side * cfg.tp_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.max_hold_bars - 1)
        exit_i = end_i
        reason = "time"
        raw_exit_price = float(close[end_i])
        peak = entry_price
        trough = entry_price
        final_stop = active_stop

        for bar_i in range(entry_i, end_i + 1):
            # Conservative executable semantics: if a bar can hit both, assume stop first.
            if crossed_stop(float(open_[bar_i]), active_stop, side):
                exit_i = bar_i
                reason = "gap_stop_market"
                raw_exit_price = float(open_[bar_i])
                break
            if touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side):
                exit_i = bar_i
                reason = "stop_market"
                raw_exit_price = float(active_stop)
                break
            if crossed_target(float(open_[bar_i]), target_price, side):
                exit_i = bar_i
                reason = "gap_target_market"
                raw_exit_price = float(open_[bar_i])
                break
            if touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side):
                exit_i = bar_i
                reason = "target_limit"
                raw_exit_price = float(target_price)
                break
            if side > 0:
                peak = max(peak, float(high[bar_i]))
                if cfg.trail_atr > 0 and np.isfinite(atr[bar_i]):
                    active_stop = max(active_stop, peak - cfg.trail_atr * float(atr[bar_i]))
            else:
                trough = min(trough, float(low[bar_i]))
                if cfg.trail_atr > 0 and np.isfinite(atr[bar_i]):
                    active_stop = min(active_stop, trough + cfg.trail_atr * float(atr[bar_i]))
            final_stop = active_stop

        exit_price = apply_exit_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
        trades.append(
            Trade(
                config=cfg.name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        blocked_until = exit_i + cfg.cooldown_bars
        _ = final_stop
    return trades, reason_counts


def curated_configs() -> list[SearchConfig]:
    configs: list[SearchConfig] = []
    idx = 0
    for side_mode in ("both", "long", "short"):
        for ema_fast, ema_slow in ((9, 55), (12, 96), (21, 96), (34, 144), (55, 192), (96, 384)):
            for entry_style in (
                "breakout",
                "squeeze_breakout",
                "pullback_resume",
                "momentum",
                "cross_fresh",
                "channel_reclaim",
                "trend_rsi_rebound",
                "bb_reversion",
                "ema_deviation_revert",
            ):
                for stop_atr, tp_atr, trail_atr, hold in (
                    (0.75, 0.75, 0.0, 12),
                    (1.0, 1.0, 0.0, 12),
                    (1.0, 1.5, 0.0, 24),
                    (1.5, 2.0, 1.5, 24),
                    (2.0, 3.0, 2.0, 48),
                    (3.0, 4.0, 3.0, 48),
                    (3.0, 6.0, 4.0, 96),
                ):
                    idx += 1
                    configs.append(
                        SearchConfig(
                            name=f"HYPE_5M_EXEC_C{idx:05d}",
                            side_mode=side_mode,
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            entry_style=entry_style,
                            donchian=96,
                            roc_window=96,
                            min_regime_age=3,
                            max_regime_age=768,
                            breakout_buffer=0.002,
                            pullback_buffer=0.01,
                            max_dist_ema=0.08,
                            min_dir_roc=-0.0025,
                            min_dir_rsi=45.0,
                            max_dir_rsi=85.0,
                            min_adx=14.0,
                            max_chop=62.0,
                            max_atr_ratio=2.0,
                            min_rvol=0.6,
                            min_dir_cmf=-0.15,
                            require_macd=False,
                            require_obv=False,
                            require_htf=False,
                            min_efficiency=0.0,
                            stop_atr=stop_atr,
                            tp_atr=tp_atr,
                            trail_atr=trail_atr,
                            max_hold_bars=hold,
                            min_hold_bars=0,
                            exit_ema=0,
                            cooldown_bars=0,
                        )
                    )
    return configs


def mutation_configs(rng: random.Random, count: int) -> list[SearchConfig]:
    configs: list[SearchConfig] = []
    for idx in range(count):
        base = random_config(rng, idx)
        stop_atr = rng.choice([0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0])
        tp_atr = rng.choice([0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0])
        trail_atr = rng.choice([0.0, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
        configs.append(
            replace(
                base,
                name=f"HYPE_5M_EXEC_R{idx:05d}",
                stop_atr=stop_atr,
                tp_atr=tp_atr,
                trail_atr=trail_atr,
                max_hold_bars=rng.choice([3, 6, 9, 12, 18, 24, 36, 48, 72, 96]),
                min_hold_bars=0,
                exit_ema=0,
                cooldown_bars=rng.choice([0, 3, 6, 12, 24]),
            )
        )
    return configs


def row_for_config(frame: pd.DataFrame, cfg: SearchConfig, slices: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade], dict[str, int]]:
    signal = build_signal(frame, cfg)
    trades, reason_counts = simulate_executable_bracket(frame, signal, cfg)
    row: dict[str, Any] = {
        "name": cfg.name,
        "signals": int(np.count_nonzero(signal)),
        "trade_count": int(len(trades)),
        **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
        **{f"reason_{key}": value for key, value in reason_counts.items()},
    }
    slice_rows: list[dict[str, Any]] = []
    for item in slices:
        metrics = metric_with_sides(trades, 1.0, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            row[f"{item['name']}_{key}"] = value
        slice_rows.append({"name": cfg.name, "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
    full_ann = float(row["full_annualized_multiple"])
    full_win = float(row["full_win_rate"])
    full_dd = float(row["full_max_dd"])
    full_trades = int(row["full_trades"])
    row["hard_pass"] = bool(
        full_trades >= MIN_FULL_TRADES
        and full_ann >= TARGET_ANNUALIZED
        and full_win >= TARGET_WIN_RATE
        and full_dd >= TARGET_MAX_DD
    )
    row["recent_pass"] = bool(
        float(row["recent_3m_annualized_multiple"]) >= 1.0
        and float(row["recent_1m_annualized_multiple"]) >= 1.0
        and float(row["recent_3m_max_dd"]) >= -0.25
        and float(row["recent_1m_max_dd"]) >= -0.25
    )
    row["audit_pass"] = bool(
        row["hard_pass"]
        and row["recent_pass"]
        and int(row["val_2026_03_01_to_2026_06_01_trades"]) >= 20
        and int(row["fwd_2026_06_01_to_latest_trades"]) >= 5
        and float(row["val_2026_03_01_to_2026_06_01_profit_factor"]) >= 1.0
        and float(row["fwd_2026_06_01_to_latest_profit_factor"]) >= 1.0
    )
    row["score"] = (
        min(80.0, np.log(max(full_ann, 1e-9)) * 10.0)
        + 100.0 * full_win
        + 30.0 * max(full_dd, -1.0)
        + 12.0 * min(float(row["full_payoff_ratio"]), 5.0)
        + 8.0 * min(float(row["val_2026_03_01_to_2026_06_01_profit_factor"]), 5.0)
        + 8.0 * min(float(row["fwd_2026_06_01_to_latest_profit_factor"]), 5.0)
    )
    return row, slice_rows, trades, reason_counts


def monthly_rows(frame: pd.DataFrame, configs: list[SearchConfig]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for cfg in configs:
        signal = build_signal(frame, cfg)
        trades, _ = simulate_executable_bracket(frame, signal, cfg)
        for item in months:
            metrics = metric_with_sides(trades, 1.0, start=item["start"], end=item["end"])
            rows.append({"name": cfg.name, "month": item["name"], "month_start": item["start"], "month_end": item["end"], **metrics})
    return rows


def render_markdown(summary: pd.DataFrame, slices: pd.DataFrame, monthly: pd.DataFrame) -> str:
    hard = summary.loc[summary["hard_pass"].eq(True)].sort_values("score", ascending=False)
    audit = summary.loc[summary["audit_pass"].eq(True)].sort_values("score", ascending=False)
    top = summary.sort_values("score", ascending=False).head(20)

    def table(rows: pd.DataFrame) -> list[str]:
        output = [
            "| name | style | side | trades | ann | win | PF | payoff | maxDD | VAL PF | FWD PF | recent1m ann |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for item in rows.to_dict(orient="records"):
            output.append(
                f"| `{item['name']}` | `{item['cfg_entry_style']}` | `{item['cfg_side_mode']}` | "
                f"`{int(item['full_trades'])}` | `{mult(float(item['full_annualized_multiple']))}` | "
                f"`{pct(float(item['full_win_rate']))}` | `{num(float(item['full_profit_factor']))}` | "
                f"`{num(float(item['full_payoff_ratio']))}` | `{pct(float(item['full_max_dd']))}` | "
                f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
                f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | "
                f"`{mult(float(item['recent_1m_annualized_multiple']))}` |"
            )
        return output

    lines = [
        "# HYPE 5m executable broad search 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "目标：按实盘可执行口径重新搜索 Binance HYPE `5m` 策略，硬条件为年化 `>=20x`、胜率 `>=50%`、最大回撤优于 `-20%`。",
        "",
        "执行口径：",
        "",
        "- 所有信号只使用已收盘 K 线信息，下一根 K 的 open 入场。",
        "- 入场即有固定 TP/SL bracket；保护止损从入场第一根 K 起生效。",
        "- 可选 trailing stop 只在每根 K 结束后用已知 high/low/ATR 更新到下一根。",
        "- 同一根 K 同时触及 TP/SL 时按保守口径优先止损。",
        "- stop 被 open 跳空穿越时按 open 市价退出，不按旧 stop 价成交。",
        "- 成本使用实盘统计：手续费 `4.1466 bps/fill`、开仓滑点 `10.73 bps`、平仓滑点 `2.64 bps`。",
        "",
        f"搜索规模：curated + random，共 `{len(summary)}` 个配置。",
        "",
        "## 硬条件结果",
        "",
    ]
    if hard.empty:
        lines.append("没有找到全样本同时满足年化、胜率、回撤三项硬条件的配置。")
    else:
        lines.append(f"全样本硬条件命中 `{len(hard)}` 个配置：")
        lines.extend(table(hard.head(20)))
    lines.extend(["", "## 审计条件结果", ""])
    if audit.empty:
        lines.append("没有配置通过附加审计条件：近期窗口不亏、VAL/FWD PF 均不低于 `1`、且有最低交易数。")
    else:
        lines.append(f"审计条件命中 `{len(audit)}` 个配置：")
        lines.extend(table(audit.head(20)))
    lines.extend(["", "## 排名前 20", "", *table(top), "", "## 结论", ""])
    if audit.empty:
        if hard.empty:
            lines.append("本轮没有找到符合用户四项要求的可实盘候选。")
        else:
            lines.append("本轮出现全样本硬条件命中，但没有任何命中能通过 VAL/FWD 与近期窗口审计，因此不能视为真实可实盘策略。")
    else:
        lines.append("本轮存在通过初步审计的候选，但仍需逐笔订单路径、参数邻域和 walk-forward 复核后才能进入 paper-live。")
    lines.extend(
        [
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_executable_broad_search.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 切片 CSV：`{SLICES_PATH}`",
            f"- 月度 CSV：`{MONTHLY_PATH}`",
        ]
    )
    _ = slices
    _ = monthly
    return "\n".join(lines) + "\n"


def main() -> None:
    rng = random.Random(SEED)
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame = add_features(raw)
    slices = validation_slices(frame)
    configs = curated_configs() + mutation_configs(rng, MAX_RANDOM_CONFIGS)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    for idx, cfg in enumerate(configs, start=1):
        row, per_slices, _, _ = row_for_config(frame, cfg, slices)
        summary_rows.append(row)
        slice_rows.extend(per_slices)
        if idx % 1000 == 0:
            best = max(summary_rows, key=lambda item: float(item["score"]))
            print(f"progress={idx}/{len(configs)} best={best['name']} ann={best['full_annualized_multiple']:.2f} win={best['full_win_rate']:.3f} dd={best['full_max_dd']:.3f}")

    summary = pd.DataFrame(summary_rows).sort_values("score", ascending=False)
    slice_df = pd.DataFrame(slice_rows)
    top_names = summary.head(TOP_KEEP)["name"].tolist()
    cfg_by_name = {cfg.name: cfg for cfg in configs}
    monthly = pd.DataFrame(monthly_rows(frame, [cfg_by_name[name] for name in top_names if name in cfg_by_name]))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slice_df.to_csv(SLICES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, slice_df, monthly), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE 5m executable broad search",
                "seed": SEED,
                "max_random_configs": MAX_RANDOM_CONFIGS,
                "targets": {
                    "annualized_multiple": TARGET_ANNUALIZED,
                    "win_rate": TARGET_WIN_RATE,
                    "max_dd": TARGET_MAX_DD,
                    "min_full_trades": MIN_FULL_TRADES,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "hard_pass_count": int(summary["hard_pass"].sum()),
                "audit_pass_count": int(summary["audit_pass"].sum()),
                "top": summary.head(50).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.head(30).to_string(index=False))
    print(f"hard_pass={int(summary['hard_pass'].sum())} audit_pass={int(summary['audit_pass'].sum())}")


if __name__ == "__main__":
    main()
