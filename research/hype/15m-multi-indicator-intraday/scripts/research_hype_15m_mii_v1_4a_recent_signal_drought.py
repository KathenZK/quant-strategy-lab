from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402
import research_hype_15m_mii_v1_3_signal_drought_diagnostic as drought  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402


FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
OUT_STEM = "hype_15m_mii_v1_4a_recent_signal_drought_2026-07-14"
RECENT_WINDOWS: tuple[tuple[str, pd.Timedelta], ...] = (
    ("1d", pd.Timedelta(days=1)),
    ("7d", pd.Timedelta(days=7)),
    ("15d", pd.Timedelta(days=15)),
    ("30d", pd.Timedelta(days=30)),
    ("90d", pd.Timedelta(days=90)),
)
VARIANTS: tuple[tuple[str, float, float, float], ...] = (
    ("v1_3", 1.0, 1.25, 5.0),
    ("v1_4", 0.85, 1.25, 5.0),
    ("v1_4a", 0.85, 1.40, 3.0),
)


def selected_signal_indices(
    context: v12.evolution.EvalContext,
    *,
    min_rvol96: float,
    tp_atr_mult: float,
    sl_atr_mult: float,
) -> set[int]:
    candidate = v12.AtrBracketCandidate(
        label=f"atr96_tp{tp_atr_mult}x_sl{sl_atr_mult}x_hold24",
        family="atr_bracket",
        atr_window=96,
        tp_atr_mult=tp_atr_mult,
        sl_atr_mult=sl_atr_mult,
        max_hold_bars=24,
    )
    raw_trades = v12.simulate_atr_bracket_trades(context, candidate, entry_delay_bars=1)
    filter_spec = replace(v12.BASE_CONFIG.filter, min_rvol96=min_rvol96)
    selected = v1.selected_trades_live(raw_trades, filter_spec)
    return {int(trade.signal_i) for trade in selected}


def funnel_window(
    context: v12.evolution.EvalContext,
    *,
    label: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    min_rvol96: float,
    final_indices: set[int],
) -> dict[str, Any]:
    features = context.features
    window_mask = (features["ts"] >= start_ts) & (features["ts"] < end_ts)
    window = features.loc[window_mask].copy()
    if window.empty:
        return {
            "window": label,
            "start_ts": start_ts.isoformat(),
            "end_ts": end_ts.isoformat(),
            "bars": 0,
        }

    raw = drought.raw_signal_mask(features).loc[window.index]
    direction = drought.direction_series(features).loc[window.index]
    atr_ok = window["atr_pct96"].between(0.0075, 0.028, inclusive="both")
    rvol_ok = window["rvol96"] >= min_rvol96
    macd_ok = (direction * window["macd_12_26_9_hist"]) >= 0
    final_mask = window.index.to_series().map(lambda idx: int(idx) in final_indices)

    raw_atr = raw & atr_ok
    raw_atr_rvol = raw_atr & rvol_ok
    raw_atr_rvol_macd = raw_atr_rvol & macd_ok

    atr_values = window["atr_pct96"].dropna()
    rvol_values = window["rvol96"].dropna()
    raw_rows = window.loc[raw]
    blocked_by_atr = window.loc[raw & ~atr_ok]
    blocked_by_rvol = window.loc[raw & atr_ok & ~rvol_ok]
    blocked_by_macd = window.loc[raw & atr_ok & rvol_ok & ~macd_ok]
    final_rows = window.loc[final_mask]

    return {
        "window": label,
        "start_ts": pd.Timestamp(window["ts"].min()).isoformat(),
        "end_ts": (pd.Timestamp(window["ts"].max()) + pd.Timedelta(minutes=15)).isoformat(),
        "bars": int(len(window)),
        "min_rvol96": min_rvol96,
        "raw_rsi_cross": int(raw.sum()),
        "pass_atr": int(raw_atr.sum()),
        "pass_atr_rvol": int(raw_atr_rvol.sum()),
        "pass_atr_rvol_macd": int(raw_atr_rvol_macd.sum()),
        "final_signals": int(final_mask.sum()),
        "blocked_by_atr": int(len(blocked_by_atr)),
        "blocked_by_rvol": int(len(blocked_by_rvol)),
        "blocked_by_macd": int(len(blocked_by_macd)),
        "atr_ok_rate_pct": round(float(atr_ok.mean() * 100.0), 2),
        "rvol_ok_rate_pct": round(float(rvol_ok.mean() * 100.0), 2),
        "atr_pct96_median": float(atr_values.median()) if len(atr_values) else None,
        "atr_pct96_latest": float(atr_values.iloc[-1]) if len(atr_values) else None,
        "rvol96_median": float(rvol_values.median()) if len(rvol_values) else None,
        "rvol96_latest": float(rvol_values.iloc[-1]) if len(rvol_values) else None,
        "last_raw_signal_ts": (
            pd.Timestamp(raw_rows["ts"].iloc[-1]).isoformat() if len(raw_rows) else None
        ),
        "last_final_signal_ts": (
            pd.Timestamp(final_rows["ts"].iloc[-1]).isoformat() if len(final_rows) else None
        ),
        "recent_raw_failures": [
            {
                "ts": pd.Timestamp(row["ts"]).isoformat(),
                "direction": int(direction.loc[idx]),
                "atr_pct96": float(row["atr_pct96"]),
                "rvol96": float(row["rvol96"]),
                "macd_hist": float(row["macd_12_26_9_hist"]),
                "atr_ok": bool(atr_ok.loc[idx]),
                "rvol_ok": bool(rvol_ok.loc[idx]),
                "macd_ok": bool(macd_ok.loc[idx]),
            }
            for idx, row in raw_rows.tail(12).iterrows()
        ],
    }


def latest_trade_rows(
    context: v12.evolution.EvalContext,
    *,
    min_rvol96: float,
    tp_atr_mult: float,
    sl_atr_mult: float,
    limit: int = 8,
) -> list[dict[str, Any]]:
    candidate = v12.AtrBracketCandidate(
        label=f"atr96_tp{tp_atr_mult}x_sl{sl_atr_mult}x_hold24",
        family="atr_bracket",
        atr_window=96,
        tp_atr_mult=tp_atr_mult,
        sl_atr_mult=sl_atr_mult,
        max_hold_bars=24,
    )
    raw_trades = v12.simulate_atr_bracket_trades(context, candidate, entry_delay_bars=1)
    filter_spec = replace(v12.BASE_CONFIG.filter, min_rvol96=min_rvol96)
    selected = v1.selected_trades_live(raw_trades, filter_spec)
    rows: list[dict[str, Any]] = []
    for trade in selected[-limit:]:
        rows.append(
            {
                "signal_ts": pd.Timestamp(context.features["ts"].iloc[trade.signal_i]).isoformat(),
                "entry_ts": pd.Timestamp(trade.entry_ts).isoformat(),
                "exit_ts": pd.Timestamp(trade.exit_ts).isoformat(),
                "direction": "long" if trade.direction == 1 else "short",
                "atr_pct96": float(trade.atr_pct96),
                "rvol96": float(trade.rvol96),
                "exit_reason": trade.exit_reason,
                "raw_return_pct": round(float(trade.raw_return * 100.0), 4),
            }
        )
    return rows


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    context, metadata, quality = drought.load_data_lake_context()
    if quality.get("gap_count", 0) or quality.get("duplicates", 0) or quality.get("critical_nulls", 0):
        raise RuntimeError(f"data-quality blocker: {quality}")

    end_ts = context.end_ts
    payload_variants: dict[str, Any] = {}
    print(
        f"data: {quality.get('first_ts') or metadata.get('start')} ~ "
        f"{quality.get('last_ts') or metadata.get('end')} rows={quality.get('rows')}"
    )

    for name, min_rvol96, tp_atr_mult, sl_atr_mult in VARIANTS:
        final_indices = selected_signal_indices(
            context,
            min_rvol96=min_rvol96,
            tp_atr_mult=tp_atr_mult,
            sl_atr_mult=sl_atr_mult,
        )
        windows = []
        for label, duration in RECENT_WINDOWS:
            start_ts = max(context.start_ts, end_ts - duration)
            row = funnel_window(
                context,
                label=label,
                start_ts=start_ts,
                end_ts=end_ts,
                min_rvol96=min_rvol96,
                final_indices=final_indices,
            )
            windows.append(row)
            print(
                f"{name:>6} {label:>4}  raw {row['raw_rsi_cross']:>3}  "
                f"atr {row['pass_atr']:>3}  atr+rvol {row['pass_atr_rvol']:>3}  "
                f"+macd {row['pass_atr_rvol_macd']:>3}  final {row['final_signals']:>3}  "
                f"atr_med {row['atr_pct96_median'] * 100 if row['atr_pct96_median'] else 0:.3f}%  "
                f"latest {row['atr_pct96_latest'] * 100 if row['atr_pct96_latest'] else 0:.3f}%"
            )
        payload_variants[name] = {
            "min_rvol96": min_rvol96,
            "tp_atr_mult": tp_atr_mult,
            "sl_atr_mult": sl_atr_mult,
            "windows": windows,
            "last_trades": latest_trade_rows(
                context,
                min_rvol96=min_rvol96,
                tp_atr_mult=tp_atr_mult,
                sl_atr_mult=sl_atr_mult,
            ),
        }

    # Focus on latest closed bars for the active dry-run version.
    features = context.features
    latest = features.tail(16).copy()
    latest_rows = []
    for idx, row in latest.iterrows():
        atr = float(row["atr_pct96"])
        rvol = float(row["rvol96"])
        rsi = float(row["rsi7"])
        prev_rsi = float(features["rsi7"].iloc[int(idx) - 1]) if int(idx) > 0 else np.nan
        direction = 0
        if np.isfinite(prev_rsi):
            if rsi > 40.0 and prev_rsi <= 40.0:
                direction = 1
            elif rsi < 60.0 and prev_rsi >= 60.0:
                direction = -1
        latest_rows.append(
            {
                "ts": pd.Timestamp(row["ts"]).isoformat(),
                "rsi7": rsi,
                "prev_rsi7": prev_rsi,
                "raw_cross": direction,
                "atr_pct96": atr,
                "rvol96": rvol,
                "macd_hist": float(row["macd_12_26_9_hist"]),
                "atr_ok_075": 0.0075 <= atr <= 0.028,
                "rvol_ok_085": rvol >= 0.85,
                "rvol_ok_100": rvol >= 1.0,
            }
        )

    payload = {
        "strategy_family": "HYPE-15M-Multi-Indicator-Intraday",
        "diagnostic_id": "HYPE-15M-MII V1.4A recent signal drought 2026-07-14",
        "active_dry_run_version": "HYPE-15M-MII-V1.4A",
        "data_quality": quality,
        "metadata": metadata,
        "cost_model": "Binance fee 0.001/fill + 4bps slippage/fill; funding not included in this funnel.",
        "selection_disclosure": (
            "Signal funnel audit only. No new parameter search. "
            "V1.4A differs from V1.4 only in TP/SL multiples; entry filters match V1.4."
        ),
        "variants": payload_variants,
        "latest_bars": latest_rows,
    }

    json_path = ARTIFACTS_DIR / f"{OUT_STEM}.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    v14a = payload_variants["v1_4a"]
    w90 = next(item for item in v14a["windows"] if item["window"] == "90d")
    w7 = next(item for item in v14a["windows"] if item["window"] == "7d")
    w30 = next(item for item in v14a["windows"] if item["window"] == "30d")
    last_trade = v14a["last_trades"][-1] if v14a["last_trades"] else None

    note = f"""# HYPE-15M-MII V1.4A 近期不开单诊断

日期：2026-07-14

## 结论

当前 dry-run 的 `HYPE-15M-MII-V1.4A` 最近不开仓，主因不是 runner 漏单，而是 **`ATR96% >= 0.75%` 波动率过滤把几乎所有 RSI 反转信号挡掉**。

- 最近 `7d`：RSI raw cross `{w7['raw_rsi_cross']}` 次，过 ATR `{w7['pass_atr']}` 次，最终信号 `{w7['final_signals']}` 次。
- 最近 `30d`：raw `{w30['raw_rsi_cross']}`，过 ATR `{w30['pass_atr']}`，最终 `{w30['final_signals']}`。
- 最近 `90d`：raw `{w90['raw_rsi_cross']}`，过 ATR `{w90['pass_atr']}`，最终 `{w90['final_signals']}`；ATR96% 中位 `{w90['atr_pct96_median'] * 100:.3f}%`，最新 `{w90['atr_pct96_latest'] * 100:.3f}%`。
- 最后一笔 V1.4A 研究开仓：`{last_trade['entry_ts'] if last_trade else '-'}`。

`min_rvol96=0.85`（相对 V1.3 的 `1.0`）不能解决当前干旱，因为卡点在 ATR，不在 RVOL。V1.4 与 V1.4A 入场漏斗相同；TP/SL 只影响已开仓后的出场，不会制造新入场信号。

## 数据口径

- Exchange / market / symbol / timeframe：Binance USD-M `HYPE/USDT:USDT` `15m`
- Source：标准数据湖 raw/normalized
- Range：见 artifact JSON `data_quality`
- Cost：fee `0.001`/fill + slippage `4 bps`/fill；本漏斗不计入 funding
- Entry timing：K+1 open
- Active dry-run：`HYPE-15M-MII-V1.4A`（`min_rvol96=0.85`，`TP=1.4*ATR96`，`SL=3.0*ATR96`）

## 决定

保持 `V1.4A` dry-run 规则不变。不要为了“最近几天开单”直接下调 `min_atr_pct96`；此前网格已证明放宽 ATR 会显著伤害收益和回撤。若要在低波动 regime 交易，应另开新版本搜索，而不是改当前 dry-run。

## 证据

- 脚本：[`research_hype_15m_mii_v1_4a_recent_signal_drought.py`](../scripts/research_hype_15m_mii_v1_4a_recent_signal_drought.py)
- 产物：[`{OUT_STEM}.json`](../artifacts/{OUT_STEM}.json)
"""
    note_path = NOTES_DIR / f"{OUT_STEM.replace('hype_15m_mii_', 'hype-15m-mii-').replace('_', '-')}.md"
    # Prefer readable markdown name.
    note_path = NOTES_DIR / "hype-15m-mii-v1-4a-recent-signal-drought-2026-07-14.md"
    note_path.write_text(note, encoding="utf-8")
    print(f"\nsummary -> {json_path}")
    print(f"note    -> {note_path}")


if __name__ == "__main__":
    main()
