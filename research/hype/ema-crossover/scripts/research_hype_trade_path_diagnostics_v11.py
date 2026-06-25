from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from plot_hype_ema_v6_trades import run_v6
from research_hype_ema_cross_strategy import build_features
from research_hype_ema_htf_rsi_exit_v9 import v8_clean_spec
from research_hype_ema_oscillator_top_exit_v10 import (
    V10Spec,
    add_oscillator_features,
    run_v10,
)
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_ema_volume_overlay_v8 import V8Spec, run_v8


REPORT_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_trade_path_diagnostics_v11.json")
DETAIL_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_trade_path_diagnostics_v11_detail.csv")
SUMMARY_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_trade_path_diagnostics_v11_summary.csv")
CATEGORY_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_trade_path_diagnostics_v11_categories.csv")


def v8_baseline_spec() -> V8Spec:
    return V8Spec(
        name="V8_full_exit_xrv2_mfe4_fb1_cd0",
        action="full_exit",
        exit_rvol=2.0,
        min_mfe_atr=4.0,
        fail_bars=1,
        cooldown_bars=0,
        wick_min=0.35,
    )


def v10_best_spec() -> V10Spec:
    return V10Spec(
        name="V10_osc_combo_only_h1_score3_mfe2_rsi75_68_25_32_j100_0_macd2",
        base_mode="osc_combo_only",
        osc_tf="h1",
        min_score=3,
        min_mfe_atr=2.0,
        long_rsi_arm=75,
        long_rsi_exit=68,
        short_rsi_arm=25,
        short_rsi_exit=32,
        kdj_j_high=100,
        kdj_j_low=0,
        kdj_drop=10.0,
        macd_bars=2,
    )


def trade_frame_from_result(strategy: str, trades: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(trades).copy()
    frame["strategy"] = strategy
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    if "direction" not in frame.columns:
        frame["direction"] = np.where(frame["side"].astype(str) == "long", 1, -1)
    if "side" not in frame.columns:
        frame["side"] = np.where(frame["direction"] > 0, "long", "short")
    return frame


def load_strategy_trades(frame: pd.DataFrame) -> pd.DataFrame:
    v6_trades, _ = run_v6(frame)
    v8_result = run_v8(frame, v8_baseline_spec(), collect_trades=True)
    v8_clean_result = run_v8(frame, v8_clean_spec(), collect_trades=True)
    v10_result = run_v10(frame, v10_best_spec(), collect_trades=True)
    return pd.concat(
        [
            trade_frame_from_result("V6_dynamic_3x", v6_trades),
            trade_frame_from_result("V8_baseline", v8_result["trades_detail"]),
            trade_frame_from_result("V8_clean_wick055", v8_clean_result["trades_detail"]),
            trade_frame_from_result("V10_osc_combo", v10_result["trades_detail"]),
        ],
        ignore_index=True,
        sort=False,
    )


def locate_index(ts_index: pd.DatetimeIndex, ts: pd.Timestamp) -> int:
    value = pd.Timestamp(ts)
    value = value.tz_localize("UTC") if value.tzinfo is None else value.tz_convert("UTC")
    idx = int(ts_index.searchsorted(value, side="left"))
    return min(max(idx, 0), len(ts_index) - 1)


def diagnose_trade(frame: pd.DataFrame, ts_index: pd.DatetimeIndex, trade: pd.Series) -> dict[str, Any]:
    direction = int(trade["direction"])
    entry_i = locate_index(ts_index, pd.Timestamp(trade["entry_ts"]))
    exit_i = locate_index(ts_index, pd.Timestamp(trade["exit_ts"]))
    if exit_i < entry_i:
        exit_i = entry_i

    segment = frame.iloc[entry_i : exit_i + 1]
    post_32 = frame.iloc[exit_i + 1 : min(exit_i + 33, len(frame))]
    post_96 = frame.iloc[exit_i + 1 : min(exit_i + 97, len(frame))]
    entry_price = float(trade["entry_price"])
    exit_price = float(trade["exit_price"])
    raw_pnl = float(trade.get("raw_pnl_pct", direction * (exit_price / entry_price - 1)))
    allocation = float(trade.get("allocation", 1.0))
    entry_atr = float(trade.get("entry_atr_pct", np.nan))
    if not np.isfinite(entry_atr) or entry_atr <= 0:
        entry_atr = float(frame.atr_pct672.iloc[max(entry_i - 1, 0)])

    if direction > 0:
        mfe = float((segment.high.max() / entry_price) - 1)
        adverse = float((segment.low.min() / entry_price) - 1)
        post_32_follow = 0.0 if post_32.empty else float((post_32.high.max() / exit_price) - 1)
        post_96_follow = 0.0 if post_96.empty else float((post_96.high.max() / exit_price) - 1)
        post_32_reverse = 0.0 if post_32.empty else float(1 - (post_32.low.min() / exit_price))
    else:
        mfe = float(1 - (segment.low.min() / entry_price))
        adverse = float((entry_price / segment.high.max()) - 1)
        post_32_follow = 0.0 if post_32.empty else float(1 - (post_32.low.min() / exit_price))
        post_96_follow = 0.0 if post_96.empty else float(1 - (post_96.low.min() / exit_price))
        post_32_reverse = 0.0 if post_32.empty else float((post_32.high.max() / exit_price) - 1)

    mfe = max(0.0, mfe)
    capture = raw_pnl / mfe if mfe > 0 else np.nan
    giveback = max(0.0, mfe - raw_pnl)
    mae_abs = abs(min(adverse, 0.0))
    atr = entry_atr if np.isfinite(entry_atr) and entry_atr > 0 else np.nan
    post_follow_atr = post_96_follow / atr if np.isfinite(atr) and atr > 0 else np.nan
    giveback_atr = giveback / atr if np.isfinite(atr) and atr > 0 else np.nan
    mae_atr = mae_abs / atr if np.isfinite(atr) and atr > 0 else np.nan
    mfe_atr = mfe / atr if np.isfinite(atr) and atr > 0 else np.nan

    if raw_pnl <= 0 and mae_atr >= 2:
        diagnosis = "bad_entry"
    elif raw_pnl > 0 and post_follow_atr >= 2:
        diagnosis = "early_exit"
    elif mfe_atr >= 4 and capture < 0.35:
        diagnosis = "late_exit_giveback"
    elif raw_pnl > 0 and capture >= 0.6:
        diagnosis = "good_capture"
    elif raw_pnl <= 0 and mfe_atr < 1:
        diagnosis = "no_follow_through"
    else:
        diagnosis = "mixed"

    return {
        "strategy": trade["strategy"],
        "entry_ts": trade["entry_ts"],
        "exit_ts": trade["exit_ts"],
        "side": trade["side"],
        "exit_reason": trade.get("exit_reason", ""),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "allocation": allocation,
        "raw_pnl_pct": raw_pnl,
        "pnl_pct": float(trade.get("pnl_pct", allocation * raw_pnl)),
        "hold_bars": int(exit_i - entry_i + 1),
        "entry_atr_pct": entry_atr,
        "mfe_pct": mfe,
        "mfe_atr": mfe_atr,
        "mae_pct": mae_abs,
        "mae_atr": mae_atr,
        "capture_ratio": capture,
        "giveback_pct": giveback,
        "giveback_atr": giveback_atr,
        "post_32_follow_pct": max(0.0, post_32_follow),
        "post_96_follow_pct": max(0.0, post_96_follow),
        "post_32_reverse_pct": max(0.0, post_32_reverse),
        "post_96_follow_atr": post_follow_atr,
        "diagnosis": diagnosis,
    }


def summarize(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    grouped = detail.groupby("strategy", sort=False)
    summary = grouped.agg(
        trades=("raw_pnl_pct", "size"),
        return_sum=("pnl_pct", "sum"),
        win_rate=("raw_pnl_pct", lambda s: float((s > 0).mean())),
        avg_raw_pnl=("raw_pnl_pct", "mean"),
        median_raw_pnl=("raw_pnl_pct", "median"),
        avg_mfe=("mfe_pct", "mean"),
        avg_mae=("mae_pct", "mean"),
        avg_capture=("capture_ratio", "mean"),
        median_capture=("capture_ratio", "median"),
        avg_giveback=("giveback_pct", "mean"),
        avg_post_96_follow=("post_96_follow_pct", "mean"),
        early_exit_rate=("diagnosis", lambda s: float((s == "early_exit").mean())),
        late_exit_rate=("diagnosis", lambda s: float((s == "late_exit_giveback").mean())),
        bad_entry_rate=("diagnosis", lambda s: float((s == "bad_entry").mean())),
        good_capture_rate=("diagnosis", lambda s: float((s == "good_capture").mean())),
    ).reset_index()

    categories = (
        detail.groupby(["strategy", "diagnosis"], sort=False)
        .agg(
            trades=("raw_pnl_pct", "size"),
            avg_raw_pnl=("raw_pnl_pct", "mean"),
            avg_mfe=("mfe_pct", "mean"),
            avg_capture=("capture_ratio", "mean"),
            avg_post_96_follow=("post_96_follow_pct", "mean"),
        )
        .reset_index()
    )
    return summary, categories


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_oscillator_features(add_volume_features(build_features(raw)))
    ts_index = pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))
    trades = load_strategy_trades(frame)
    detail = pd.DataFrame([diagnose_trade(frame, ts_index, trade) for _, trade in trades.iterrows()])
    summary, categories = summarize(detail)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    categories.to_csv(CATEGORY_PATH, index=False)
    report = {
        "data": {
            "start": str(pd.Timestamp(frame.ts.iloc[0])),
            "end": str(pd.Timestamp(frame.ts.iloc[-1])),
            "bars": int(len(frame)),
        },
        "summary": summary.to_dict(orient="records"),
        "categories": categories.to_dict(orient="records"),
        "top_early_exits": detail.sort_values("post_96_follow_atr", ascending=False).head(15).to_dict(orient="records"),
        "top_givebacks": detail.sort_values("giveback_atr", ascending=False).head(15).to_dict(orient="records"),
        "worst_entries": detail.sort_values("mae_atr", ascending=False).head(15).to_dict(orient="records"),
        "notes": [
            "MFE/MAE are raw price moves, before allocation.",
            "early_exit means profitable exit followed by >=2ATR same-direction move within 96 bars.",
            "late_exit_giveback means MFE >=4ATR but capture ratio <35%.",
            "bad_entry means losing trade with MAE >=2ATR.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"wrote={REPORT_PATH}")
    print(f"detail={DETAIL_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"categories={CATEGORY_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
