from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "notes"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_leverage_summary_{RUN_ID}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_leverage_slices_{RUN_ID}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_leverage_trades_{RUN_ID}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_atr_dynamic_leverage_{RUN_ID}.json"
REPORT_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-3-atr-dynamic-leverage-{RUN_ID}.md"

MIN_LEVERAGE = 1.0
MAX_LEVERAGE = 3.0
MIN_ATR_PCT_BPS = 35.0  # V1.3 min_atr_pct_bps filter floor


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return f"{value:.2f}x"


def num(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.3f}"


def bps(value: float) -> str:
    return f"{value * 10000:.2f} bps"


def dynamic_leverage(
    atr_pct_bps: float,
    max_atr_pct_bps: float,
    *,
    min_leverage: float = MIN_LEVERAGE,
    max_leverage: float = MAX_LEVERAGE,
) -> float:
    """低波动高杠杆、高波动低杠杆。"""
    if not np.isfinite(atr_pct_bps):
        return min_leverage
    if max_atr_pct_bps <= MIN_ATR_PCT_BPS:
        return max_leverage
    normalized = (float(atr_pct_bps) - MIN_ATR_PCT_BPS) / (max_atr_pct_bps - MIN_ATR_PCT_BPS)
    leverage = max_leverage - normalized * (max_leverage - min_leverage)
    return float(np.clip(leverage, min_leverage, max_leverage))


def leverage_for_variant(
    variant: str,
    atr_pct_bps: float,
    *,
    max_atr_pct_bps: float,
) -> float:
    if variant == "fixed_1x":
        return 1.0
    if variant == "fixed_2x":
        return 2.0
    if variant == "fixed_3x":
        return 3.0
    if variant == "atr_dynamic_1x_3x":
        return dynamic_leverage(atr_pct_bps, max_atr_pct_bps)
    if variant == "atr_dynamic_2x_3x":
        return dynamic_leverage(atr_pct_bps, max_atr_pct_bps, min_leverage=2.0, max_leverage=3.0)
    raise ValueError(f"unknown variant: {variant}")


def leveraged_metrics(
    trades: list[engine.Trade],
    leverages: np.ndarray,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float | int | bool]:
    selected_idx = [i for i, trade in enumerate(trades) if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected_idx:
        return {
            "trades": 0,
            "trades_per_day": 0.0,
            "avg_leverage": 0.0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_account": 0.0,
            "worst_trade_account": 0.0,
            "best_trade_account": 0.0,
            "liquidation_path_count": 0,
            "bankrupt": False,
        }

    account_rets = np.array(
        [leverages[i] * trades[i].net_ret_1x for i in selected_idx],
        dtype=float,
    )
    account_maes = np.array(
        [leverages[i] * trades[i].mae_1x for i in selected_idx],
        dtype=float,
    )
    levs = np.array([leverages[i] for i in selected_idx], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    bankrupt = False
    liquidation_path_count = 0
    for ret, mae in zip(account_rets, account_maes, strict=True):
        if 1.0 + mae <= 0.0:
            liquidation_path_count += 1
        trough = equity * max(0.0, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        if 1.0 + ret <= 0.0:
            equity = 0.0
            max_dd = -1.0
            bankrupt = True
            break
        equity *= 1.0 + ret
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)

    wins = account_rets[account_rets > 0]
    losses = account_rets[account_rets <= 0]
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    return {
        "trades": int(len(selected_idx)),
        "trades_per_day": float(len(selected_idx) / days),
        "avg_leverage": float(levs.mean()),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((account_rets > 0).mean()),
        "profit_factor": profit_factor,
        "avg_trade_account": float(account_rets.mean()),
        "worst_trade_account": float(account_rets.min()),
        "best_trade_account": float(account_rets.max()),
        "liquidation_path_count": int(liquidation_path_count),
        "bankrupt": bankrupt,
    }


def trade_atr_pct_bps(frame: pd.DataFrame, trades: list[engine.Trade]) -> np.ndarray:
    atr_by_ts = dict(zip(frame["ts"], frame["atr_pct_bps"].astype(float)))
    values: list[float] = []
    for trade in trades:
        atr = atr_by_ts.get(trade.signal_ts)
        if atr is None:
            # fallback: signal bar is entry_ts - 5m
            atr = atr_by_ts.get(trade.entry_ts - pd.Timedelta(minutes=5), np.nan)
        values.append(float(atr))
    return np.array(values, dtype=float)


def calibrate_max_atr_pct_bps(signal_atr_bps: np.ndarray) -> float:
    finite = signal_atr_bps[np.isfinite(signal_atr_bps)]
    if len(finite) == 0:
        return 120.0
    p90 = float(np.percentile(finite, 90))
    return max(p90, MIN_ATR_PCT_BPS + 10.0)


def render_report(
    summary: pd.DataFrame,
    *,
    max_atr_pct_bps: float,
    signal_atr_bps: np.ndarray,
    quality: dict[str, Any],
) -> str:
    base = summary.loc[summary["variant"].eq("fixed_1x")].iloc[0]
    dyn = summary.loc[summary["variant"].eq("atr_dynamic_1x_3x")].iloc[0]
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.3 ATR 动态杠杆回测 2026-07-01",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "在 V1.3 信号、固定 `tp_bps=110` / `sl_bps=400` 不变的前提下，只改变账户杠杆层。",
        "",
        "## 动态杠杆规则",
        "",
        f"- `ATR14%` 取信号 K 的 `atr_pct_bps`（bps）。",
        f"- `atr_pct_bps <= {MIN_ATR_PCT_BPS:.1f}` → `{MAX_LEVERAGE:.1f}x`；"
        f"`atr_pct_bps >= {max_atr_pct_bps:.1f}` → `{MIN_LEVERAGE:.1f}x`；中间线性插值。",
        f"- 高波动降杠杆、低波动升杠杆；clip `[{MIN_LEVERAGE:.1f}x, {MAX_LEVERAGE:.1f}x]`。",
        f"- `max_atr_pct_bps` 锚点取 V1.3 成交信号 ATR 的 P90 = `{max_atr_pct_bps:.1f} bps`。",
        f"- 信号 ATR 分布：中位 `{np.median(signal_atr_bps):.1f}` bps，"
        f"P25 `{np.percentile(signal_atr_bps, 25):.1f}`，P75 `{np.percentile(signal_atr_bps, 75):.1f}` bps。",
        f"- 成本：fee `{FEE_RATE_PER_FILL}`/fill，slippage `{SLIPPAGE_RATE_PER_FILL * 10000:.1f} bps`/fill；"
        "杠杆放大 `net_ret_1x` 与路径内 `mae_1x`，不模拟 maintenance margin / 强平。",
        "",
        f"- 数据：`{quality['start_ts']}` → `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        "",
        "## 全样本对比",
        "",
        "| variant | trades | avg lev | ann | 总收益 | maxDD | PF | win | avg trade | worst | VAL PF | FWD PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary.sort_values("full_annualized_multiple", ascending=False).to_dict(orient="records"):
        lines.append(
            f"| `{item['variant']}` | `{int(item['full_trades'])}` | `{float(item['full_avg_leverage']):.3f}x` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{pct(float(item['full_total_return']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | `{num(float(item['full_profit_factor']))}` | "
            f"`{pct(float(item['full_win_rate']))}` | `{bps(float(item['full_avg_trade_account']))}` | "
            f"`{pct(float(item['full_worst_trade_account']))}` | "
            f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- V1.3 固定 `1x` 基线：ann `{mult(float(base['full_annualized_multiple']))}`，maxDD `{pct(float(base['full_max_dd']))}`。",
            f"- ATR 动态 `1x-3x`：平均杠杆 `{float(dyn['full_avg_leverage']):.3f}x`，"
            f"ann `{mult(float(dyn['full_annualized_multiple']))}`，maxDD `{pct(float(dyn['full_max_dd']))}`。",
            f"- 相对固定 `3x`：动态杠杆通常降低回撤，但也降低收益；本实验仅为杠杆层诊断，不构成 live-ready 或实盘仓位建议。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_atr_dynamic_leverage.py`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame_raw, quality = engine.load_hype_5m()
    parity = verify_raw_normalized_parity(frame_raw)
    engine.FEE_RATE_PER_FILL = FEE_RATE_PER_FILL
    engine.ENTRY_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL
    engine.EXIT_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL

    frame = engine.add_features(frame_raw)
    cfg = to_engine_config(v1_3_config())
    signal = engine.build_signal(frame, cfg)
    trades, reason_counts = engine.simulate_trades(frame, signal, cfg)
    signal_atr_bps = trade_atr_pct_bps(frame, trades)
    max_atr_pct_bps = calibrate_max_atr_pct_bps(signal_atr_bps)

    variants = [
        "fixed_1x",
        "fixed_2x",
        "fixed_3x",
        "atr_dynamic_1x_3x",
        "atr_dynamic_2x_3x",
    ]
    slices = engine.validation_slices(frame)
    rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    for variant in variants:
        leverages = np.array(
            [leverage_for_variant(variant, atr, max_atr_pct_bps=max_atr_pct_bps) for atr in signal_atr_bps],
            dtype=float,
        )
        row: dict[str, Any] = {
            "variant": variant,
            "max_atr_pct_bps_anchor": max_atr_pct_bps,
            "trade_count": len(trades),
            **{f"reason_{k}": v for k, v in reason_counts.items()},
        }
        for item in slices:
            metrics = leveraged_metrics(trades, leverages, start=item["start"], end=item["end"])
            for key, value in metrics.items():
                row[f"{item['name']}_{key}"] = value
            slice_rows.append({"variant": variant, "slice": item["name"], **metrics})
        rows.append(row)
        for trade, lev, atr in zip(trades, leverages, signal_atr_bps, strict=True):
            trade_rows.append(
                {
                    **asdict(trade),
                    "variant": variant,
                    "leverage": float(lev),
                    "signal_atr_pct_bps": float(atr),
                    "net_account_ret": float(lev * trade.net_ret_1x),
                    "mae_account": float(lev * trade.mae_1x),
                }
            )

    summary = pd.DataFrame(rows)
    slices_frame = pd.DataFrame(slice_rows)
    trades_frame = pd.DataFrame(trade_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices_frame.to_csv(SLICES_PATH, index=False)
    trades_frame.to_csv(TRADES_PATH, index=False)
    REPORT_PATH.write_text(
        render_report(summary, max_atr_pct_bps=max_atr_pct_bps, signal_atr_bps=signal_atr_bps, quality=quality),
        encoding="utf-8",
    )
    JSON_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "base_version": "HYPE-5M-Micro-Scalp-V1.3",
                "experiment": "atr_dynamic_leverage",
                "run_id": RUN_ID,
                "leverage_model": {
                    "min_leverage": MIN_LEVERAGE,
                    "max_leverage": MAX_LEVERAGE,
                    "min_atr_pct_bps": MIN_ATR_PCT_BPS,
                    "max_atr_pct_bps_anchor": max_atr_pct_bps,
                    "formula": "leverage = clip(3 - (atr_pct_bps - min) / (max - min) * 2, 1, 3)",
                },
                "data_quality": quality,
                "raw_normalized_parity": parity,
                "reason_counts": reason_counts,
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
    print(
        summary[
            [
                "variant",
                "full_trades",
                "full_avg_leverage",
                "full_annualized_multiple",
                "full_profit_factor",
                "full_max_dd",
            ]
        ].to_string(index=False)
    )
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
