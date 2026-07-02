from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

import research_hype_5m_micro_scalp_search as engine
from research_hype_5m_micro_scalp_v1_3_simplified_ablation import (
    FEE_RATE_PER_FILL,
    SLIPPAGE_RATE_PER_FILL,
    to_engine_config,
    v1_3_config,
)
from research_hype_5m_micro_scalp_v1_simplified_combo_search import verify_raw_normalized_parity


RUN_ID = "2026-07-01"
FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "research-notes"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_tp_summary_{RUN_ID}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_tp_slices_{RUN_ID}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_tp_trades_{RUN_ID}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_tp_{RUN_ID}.json"
REPORT_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-3-atr-dynamic-tp-{RUN_ID}.md"

TpMode = Literal["atr_abs", "atr_pct"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V1.3 ATR dynamic take-profit backtest vs fixed TP baseline.")
    parser.add_argument("--skip-raw-parity", action="store_true")
    return parser.parse_args()


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return f"{value:.2f}x"


def num(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.3f}"


def bps(value: float) -> str:
    return f"{value * 10000:.2f} bps"


def target_distance_bps(
    entry_price: float,
    target_price: float,
    side: int,
) -> float:
    return float(side * (target_price / entry_price - 1.0) * 10000.0)


def compute_target_price(
    *,
    entry_price: float,
    side: int,
    signal_atr: float,
    signal_atr_pct_bps: float,
    tp_mode: TpMode,
    tp_atr_mult: float,
    min_tp_bps: float,
    max_tp_bps: float,
) -> tuple[float, float]:
    if tp_mode == "atr_abs":
        raw_distance = tp_atr_mult * signal_atr
        target_price = entry_price + side * raw_distance
    else:
        tp_bps_raw = tp_atr_mult * signal_atr_pct_bps
        tp_bps_clamped = float(np.clip(tp_bps_raw, min_tp_bps, max_tp_bps))
        target_price = entry_price * (1.0 + side * tp_bps_clamped / 10000.0)
        return target_price, tp_bps_clamped

    implied_bps = target_distance_bps(entry_price, target_price, side)
    if implied_bps < min_tp_bps or implied_bps > max_tp_bps:
        implied_bps = float(np.clip(implied_bps, min_tp_bps, max_tp_bps))
        target_price = entry_price * (1.0 + side * implied_bps / 10000.0)
    return target_price, implied_bps


def simulate_trades_atr_tp(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: engine.ScalpConfig,
    *,
    tp_mode: TpMode,
    tp_atr_mult: float,
    min_tp_bps: float = 40.0,
    max_tp_bps: float = 250.0,
) -> tuple[list[engine.Trade], dict[str, int], list[dict[str, Any]]]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    atr_pct_bps = frame["atr_pct_bps"].to_numpy("float64")
    trades: list[engine.Trade] = []
    reason_counts: dict[str, int] = {}
    tp_diag: list[dict[str, Any]] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or side == 0:
            continue

        signal_atr = float(atr[sig_i])
        signal_atr_pct = float(atr_pct_bps[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0 or not np.isfinite(signal_atr_pct):
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * engine.ENTRY_SLIPPAGE_RATE))
        target_price, implied_tp_bps = compute_target_price(
            entry_price=entry_price,
            side=side,
            signal_atr=signal_atr,
            signal_atr_pct_bps=signal_atr_pct,
            tp_mode=tp_mode,
            tp_atr_mult=tp_atr_mult,
            min_tp_bps=min_tp_bps,
            max_tp_bps=max_tp_bps,
        )
        stop_price = entry_price * (1.0 - side * cfg.sl_bps / 10000.0)
        last_intrabar_i = min(n - 1, entry_i + cfg.max_hold_bars - 1)
        timeout_i = min(n - 1, entry_i + cfg.max_hold_bars)
        exit_i = timeout_i
        reason = "time_open"
        raw_exit_price = float(open_[timeout_i] if timeout_i > last_intrabar_i else close[timeout_i])

        for bar_i in range(entry_i, last_intrabar_i + 1):
            if engine.crossed_stop(float(open_[bar_i]), stop_price, side):
                exit_i = bar_i
                reason = "gap_stop_market"
                raw_exit_price = float(open_[bar_i])
                break
            if engine.touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side):
                exit_i = bar_i
                reason = "stop_market"
                raw_exit_price = float(stop_price)
                break
            if engine.crossed_target(float(open_[bar_i]), target_price, side):
                exit_i = bar_i
                reason = "gap_target_market"
                raw_exit_price = float(open_[bar_i])
                break
            if engine.touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side):
                exit_i = bar_i
                reason = "target_limit"
                raw_exit_price = float(target_price)
                break

        exit_price = engine.apply_exit_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = engine.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        path_end = max(entry_i, exit_i)
        path_high = high[entry_i : path_end + 1]
        path_low = low[entry_i : path_end + 1]
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))

        trades.append(
            engine.Trade(
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
                mae_1x=float(mae - engine.FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        tp_diag.append(
            {
                "entry_ts": pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                "side": side,
                "signal_atr": signal_atr,
                "signal_atr_pct_bps": signal_atr_pct,
                "implied_tp_bps": implied_tp_bps,
                "exit_reason": reason,
            }
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, reason_counts, tp_diag


def row_for_variant(
    frame: pd.DataFrame,
    name: str,
    trades: list[engine.Trade],
    reason_counts: dict[str, int],
    tp_diag: list[dict[str, Any]],
    slices: list[dict[str, Any]],
    *,
    tp_mode: str,
    tp_atr_mult: float,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "tp_mode": tp_mode,
        "tp_atr_mult": tp_atr_mult,
        "trade_count": len(trades),
        **{f"reason_{key}": value for key, value in reason_counts.items()},
    }
    if tp_diag:
        implied = np.array([item["implied_tp_bps"] for item in tp_diag], dtype=float)
        row["tp_bps_median"] = float(np.median(implied))
        row["tp_bps_p25"] = float(np.percentile(implied, 25))
        row["tp_bps_p75"] = float(np.percentile(implied, 75))
        row["target_hit_rate"] = float(np.mean([item["exit_reason"] in {"target_limit", "gap_target_market"} for item in tp_diag]))
    for item in slices:
        metrics = engine.metric_from_trades(trades, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            row[f"{item['name']}_{key}"] = value
    return row


def render_report(summary: pd.DataFrame, baseline_name: str) -> str:
    base = summary.loc[summary["name"].eq(baseline_name)].iloc[0]
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.3 ATR 动态止盈回测 2026-07-01",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "在 V1.3 入场/过滤/固定 SL 不变的前提下，将固定 `tp_bps=110` 替换为信号 K 的 ATR 动态止盈，并与基线对比。",
        "",
        "## 动态止盈口径",
        "",
        "- 信号仍用已收盘 K；入场仍为下一根 open + `4 bps` 不利滑点。",
        "- 止损保持 V1.3 固定 `sl_bps=400`。",
        "- `atr_abs`：`TP 距离 = tp_atr_mult × ATR14(signal bar)`。",
        "- `atr_pct`：`TP bps = clip(tp_atr_mult × atr_pct_bps, 40, 250)`，再换算目标价。",
        "- 目标价在入场时一次性确定，持仓内不 trailing；同 K 双触仍 stop-first。",
        f"- 成本：fee `{FEE_RATE_PER_FILL}`/fill，slippage `{SLIPPAGE_RATE_PER_FILL * 10000:.1f} bps`/fill。",
        "",
        "## V1.3 固定 TP 基线",
        "",
        f"- trades `{int(base['full_trades'])}`，ann `{mult(float(base['full_annualized_multiple']))}`，PF `{num(float(base['full_profit_factor']))}`。",
        f"- win `{pct(float(base['full_win_rate']))}`，avg `{bps(float(base['full_avg_trade']))}`，maxDD `{pct(float(base['full_max_dd']))}`。",
        f"- target hit `{pct(float(base.get('target_hit_rate', 0.0)))}`，VAL PF `{num(float(base['val_2026_03_01_to_2026_06_01_profit_factor']))}`，FWD PF `{num(float(base['fwd_2026_06_01_to_latest_profit_factor']))}`。",
        "",
        "## 对比表",
        "",
        "| variant | tp_mode | mult | trades | ann | PF | win | avg | maxDD | TP中位bps | target% | VAL PF | FWD PF |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary.sort_values("full_annualized_multiple", ascending=False).to_dict(orient="records"):
        lines.append(
            f"| `{item['name']}` | `{item['tp_mode']}` | `{item['tp_atr_mult']}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{num(float(item['full_profit_factor']))}` | "
            f"`{pct(float(item['full_win_rate']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | `{float(item.get('tp_bps_median', 110.0)):.1f}` | "
            f"`{pct(float(item.get('target_hit_rate', 0.0)))}` | "
            f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` |"
        )

    best = summary.loc[~summary["name"].eq(baseline_name)].sort_values("full_annualized_multiple", ascending=False).head(1)
    lines.extend(["", "## 结论", ""])
    if best.empty:
        lines.append("- 动态 TP 未超过固定 TP 基线。")
    else:
        row = best.iloc[0]
        delta_ann = float(row["full_annualized_multiple"]) - float(base["full_annualized_multiple"])
        delta_dd = float(row["full_max_dd"]) - float(base["full_max_dd"])
        lines.append(
            f"- 最佳动态 TP 为 `{row['name']}`（`{row['tp_mode']}` × `{row['tp_atr_mult']}`）："
            f"ann `{mult(float(row['full_annualized_multiple']))}`（Δ `{delta_ann:+.2f}x`），"
            f"maxDD `{pct(float(row['full_max_dd']))}`（Δ `{delta_dd * 100:+.2f}pp`），"
            f"target hit `{pct(float(row.get('target_hit_rate', 0.0)))}`。"
        )
    lines.extend(
        [
            "- 本实验只替换止盈模型；不构成 live-ready 证明。",
            "- 若推进实盘，还需审计 bracket 下单时 ATR 快照、最小价格精度、以及动态 TP 是否可在入场瞬间稳定挂出。",
            "",
            "## 产物",
            "",
            f"- Script：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_atr_dynamic_tp.py`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Trades CSV：`{TRADES_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame_raw, quality = engine.load_hype_5m()
    parity = None if args.skip_raw_parity else verify_raw_normalized_parity(frame_raw)
    engine.FEE_RATE_PER_FILL = FEE_RATE_PER_FILL
    engine.ENTRY_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL
    engine.EXIT_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL

    frame = engine.add_features(frame_raw)
    base_cfg = to_engine_config(v1_3_config())
    signal = engine.build_signal(frame, base_cfg)
    slices = engine.validation_slices(frame)

    variants: list[dict[str, Any]] = [
        {"name": "V1.3_fixed_tp_110bps", "tp_mode": "fixed", "tp_atr_mult": 0.0},
        {"name": "V1.3_atr_abs_x1.5", "tp_mode": "atr_abs", "tp_atr_mult": 1.5},
        {"name": "V1.3_atr_abs_x2.0", "tp_mode": "atr_abs", "tp_atr_mult": 2.0},
        {"name": "V1.3_atr_abs_x2.5", "tp_mode": "atr_abs", "tp_atr_mult": 2.5},
        {"name": "V1.3_atr_abs_x3.0", "tp_mode": "atr_abs", "tp_atr_mult": 3.0},
        {"name": "V1.3_atr_pct_x2.0", "tp_mode": "atr_pct", "tp_atr_mult": 2.0},
        {"name": "V1.3_atr_pct_x2.5", "tp_mode": "atr_pct", "tp_atr_mult": 2.5},
        {"name": "V1.3_atr_pct_x3.0", "tp_mode": "atr_pct", "tp_atr_mult": 3.0},
        {"name": "V1.3_atr_pct_x3.5", "tp_mode": "atr_pct", "tp_atr_mult": 3.5},
    ]

    rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    for variant in variants:
        name = str(variant["name"])
        cfg = replace(base_cfg, name=name)
        if variant["tp_mode"] == "fixed":
            trades, reason_counts = engine.simulate_trades(frame, signal, cfg)
            tp_diag = [
                {"implied_tp_bps": cfg.tp_bps, "exit_reason": trade.reason}
                for trade in trades
            ]
        else:
            trades, reason_counts, tp_diag = simulate_trades_atr_tp(
                frame,
                signal,
                cfg,
                tp_mode=variant["tp_mode"],
                tp_atr_mult=float(variant["tp_atr_mult"]),
            )
        row = row_for_variant(
            frame,
            name,
            trades,
            reason_counts,
            tp_diag,
            slices,
            tp_mode=str(variant["tp_mode"]),
            tp_atr_mult=float(variant["tp_atr_mult"]),
        )
        rows.append(row)
        for item in slices:
            slice_rows.append(
                {
                    "name": name,
                    "slice": item["name"],
                    **{key: row[f"{item['name']}_{key}"] for key in (
                        "trades",
                        "trades_per_day",
                        "annualized_multiple",
                        "profit_factor",
                        "win_rate",
                        "avg_trade",
                        "max_dd",
                        "total_return",
                    )},
                }
            )
        for trade, diag in zip(trades, tp_diag, strict=False):
            trade_rows.append({**asdict(trade), **diag, "variant": name})

    summary = pd.DataFrame(rows).sort_values("full_annualized_multiple", ascending=False)
    slices_frame = pd.DataFrame(slice_rows)
    trades_frame = pd.DataFrame(trade_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices_frame.to_csv(SLICES_PATH, index=False)
    trades_frame.to_csv(TRADES_PATH, index=False)
    REPORT_PATH.write_text(render_report(summary, "V1.3_fixed_tp_110bps"), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "base_version": "HYPE-5M-Micro-Scalp-V1.3",
                "experiment": "atr_dynamic_take_profit",
                "run_id": RUN_ID,
                "data_quality": quality,
                "raw_normalized_parity": parity,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "slippage_rate_per_fill": SLIPPAGE_RATE_PER_FILL,
                },
                "exit_model": {
                    "stop": "fixed sl_bps=400",
                    "take_profit": "signal-bar ATR dynamic with optional bps clip [40, 250] for atr_pct mode",
                },
                "variants": variants,
                "summary": summary.to_dict(orient="records"),
                "outputs": {
                    "markdown": str(REPORT_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                    "trades": str(TRADES_PATH),
                },
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary[["name", "full_trades", "full_annualized_multiple", "full_profit_factor", "full_max_dd", "tp_bps_median", "target_hit_rate"]].to_string(index=False))
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
